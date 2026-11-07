#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bounded_search.py — 确定性有界搜索：用结果决定下一步查什么

为什么需要这个模块
------------------
改造前的候选生成是**盲目全组合枚举**：
    build_candidates() 取 8 个特征 → C(8,2)+C(8,3) = 84 条 → 截前 60 条
它完全不看数据，只按信号的 norm 强度排序。后果：

1. **盲打**：60 条里绝大多数注定无效（互斥、包含、无增量），
   真正的强组合可能排在 60 名之外，永远没被查询。
2. **查询量固定**：不管 3 个维度就有结论，还是 50 个维度都无结论，
   都要跑 60 条 SQL。数据量一大就是纯浪费。
3. **没有反馈**：第一层跑完的结果不参与第二层选题。这正是评审说的
   「缺的不是 LLM，是『看结果→改计划』的闭环」。

本模块的做法（确定性、有界、可复现）
--------------------------------
分三层，每层的候选集都由**上一层的结果**决定，不靠猜：

  L1  每个可映射特征单独 vs 父群/全辖
      → 按 lift 与显著性排序，筛出「值得继续挖」的维度
      → 这一层的结果直接就是现象候选（强度达标的单条件）

  L2  只对 L1 显著的维度做两两交叉
      → 交叉数有硬上限（默认 30），按 L1 强度降序取
      → 不做三阶：三阶的信噪比在基率 1%~4% 时基本不可控，
        且组合爆炸。若确需三阶，由 L2 结果再申请，不在本轮展开。

  L3  汇总：把 L1/L2 的现象按强度排序，交给下游闸门
      → LLM 只负责语义归因（这条现象在业务上意味着什么），
        不参与「查什么」「算不算现象」的判定

有界性
------
· 查询次数上限 query_budget（默认 40）硬约束，超了就停，并记录未完成项
· L2 交叉数上限 max_cross（默认 30）
· 每层都记录 skipped 与原因，保证「为什么没查」可追溯

确定性
------
· 排序键全部显式（lift 降序、p 值升序、feature_id 升序兜底），
  不依赖 SQL 返回顺序或 dict 迭代顺序
· 同样的输入必然产生同样的查询序列与同样的结果

红线
----
· 不用 LLM 决定查询路径 —— LLM 的选题不稳定、不可复现、无法验收
· 不在取数前用代理强度淘汰候选 —— 强度只用于**排序**，不用于**判定**
· 预算耗尽时必须如实报告「没查完」，不能把未查当成「无风险」
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

import combo_split as cs   # noqa: E402

SCHEMA_VERSION = "1.0"

DEFAULT_SEARCH = {
    # ---- 预算与规模 ----
    "query_budget": 40,        # 总查询次数硬上限（含 L1/L2）
    "max_cross": 30,           # L2 两两交叉数上限
    "max_features": 10,        # 参与搜索的特征数上限（按信号强度取前 N）
    # ---- 每层的准入 ----
    "l1_lift_floor": 1.3,      # L1 进入「值得继续挖」的 lift 下限（低于现象门槛，
                               # 因为这里只决定要不要展开，不是最终判定）
    "l1_max_p": 0.10,          # L1 的显著性宽松门（同上，非最终判定）
    "l2_min_parent_lift": 1.15,  # L2 交叉相对父群的 lift 下限
    # ---- 现象判定（复用 combo_split 口径，不在这里另立标准）----
    "phenomenon": dict(cs.DEFAULT_SCREEN),
}


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _log(msg, quiet=False):
    if not quiet:
        print(msg)


def search(signal_rows, run_groups, cfg=None, quiet=False):
    """执行确定性有界搜索。

    signal_rows: [{"feature_id", "name", "norm"}]，由上游信号表给出
    run_groups:  callable(conds: list[str], kind: str) -> {"hit","nonhit","universe"}
                 由调用方绑定数据库；kind ∈ {"single","combo","parent"}

    返回结构化的搜索结果，包含：
      l1   每个特征的单维结果（含是否显著）
      l2   两两交叉结果
      phenomena  通过现象判定的候选（L1/L2 合并，按强度排序）
      budget     查询预算使用情况（used/total/exhausted）
      skipped    未执行项及原因
    """
    cfg = {**DEFAULT_SEARCH, **(cfg or {})}
    budget = int(cfg["query_budget"])
    used = 0
    skipped = []
    l1, l2, phenomena = [], [], []

    # ---------- 选取参与搜索的特征 ----------
    # 只取「可映射」（有 SQL 表达式）的特征，按信号强度降序。
    # 强度只用于排序，不用于淘汰 —— 淘汰由实测算出的 lift 决定。
    usable = []
    for r in signal_rows or []:
        fid = r.get("feature_id")
        if fid is None or not cs.translate(fid):
            continue
        usable.append(r)
    usable.sort(key=lambda r: (-(_num(r.get("norm")) or 0), r.get("feature_id") or 0))
    if len(usable) > cfg["max_features"]:
        skipped.append({"stage": "feature_cap",
                        "dropped": [r.get("feature_id") for r in usable[cfg["max_features"]:]],
                        "reason": f"特征数超过上限 {cfg['max_features']}，按信号强度截断"})
        usable = usable[:cfg["max_features"]]

    # ==================== L1：单维 vs 基线 ====================
    _log(f"── L1 单维扫描（{len(usable)} 个特征，预算 {budget}）", quiet)
    for r in usable:
        fid = r["feature_id"]
        t = cs.translate(fid)
        if t is None:          # 理论上已被上面的过滤排除，双保险
            skipped.append({"stage": "L1", "feature_id": fid,
                            "reason": "该特征无可用 SQL 表达式"})
            continue
        if used >= budget:
            skipped.append({"stage": "L1", "feature_id": fid,
                            "reason": "查询预算耗尽，未执行"})
            continue
        try:
            g = run_groups([t["cond"]], "single")
        except Exception as exc:      # noqa: BLE001
            skipped.append({"stage": "L1", "feature_id": fid,
                            "reason": f"取数失败：{exc}"})
            used += 1
            continue
        used += 1
        # 单维现象判定：复用 combo_split.screen 的口径，is_single=True
        st, m = cs.screen(g.get("hit"), g.get("nonhit"), g.get("universe"),
                          [{"feature_id": fid, "name": t.get("desc") or t.get("name"),
                            "cond": t["cond"], "hit": g.get("hit"),
                            "nonhit": g.get("nonhit"), "universe": g.get("universe")}],
                          level="chg", is_single=True)
        item = {
            "feature_id": fid,
            "name": t.get("desc") or t.get("name"),
            "cond": t["cond"],
            "status": st,
            "lift": (m or {}).get("lift_vs_baseline"),
            "lift_vs_universe": (m or {}).get("lift_vs_universe"),
            "p_value": (m or {}).get("p_value"),
            "hit_n": (m or {}).get("hit_n"),
            "baseline_used": (m or {}).get("baseline_used"),
            "reason": (m or {}).get("reason"),
            "metrics": m,
        }
        l1.append(item)
        if st == "phenomenon":
            phenomena.append({
                "kind": "single", "features": [fid], "conds": [t["cond"]],
                "name": item["name"], "lift": item["lift"],
                "p_value": item["p_value"], "hit_n": item["hit_n"],
                "baseline_used": item["baseline_used"],
            })
        _log(f"   L1 {fid:>3} {str(item['name'])[:18]:<18} "
             f"lift={item['lift'] if item['lift'] is not None else '—':>6} "
             f"p={item['p_value']} → {st}", quiet)

    # ---------- 选出「值得继续挖」的维度 ----------
    expandable = [x for x in l1
                  if (x["lift"] or 0) >= cfg["l1_lift_floor"]
                  and x["p_value"] is not None
                  and x["p_value"] <= cfg["l1_max_p"]]
    # 显式排序：lift 降序 → p 升序 → feature_id 升序（保证确定性）
    expandable.sort(key=lambda x: (-(x["lift"] or 0), x["p_value"] or 1, x["feature_id"]))
    if len(expandable) < 2:
        skipped.append({"stage": "L2",
                        "reason": f"只有 {len(expandable)} 个维度达到展开门槛"
                                  f"（lift≥{cfg['l1_lift_floor']} 且 p≤{cfg['l1_max_p']}），"
                                  f"不做交叉"})

    # ==================== L2：仅对显著维度两两交叉 ====================
    pairs = []
    for i in range(len(expandable)):
        for j in range(i + 1, len(expandable)):
            pairs.append((expandable[i], expandable[j]))
    if len(pairs) > cfg["max_cross"]:
        skipped.append({"stage": "L2", "dropped": len(pairs) - cfg["max_cross"],
                        "reason": f"交叉数 {len(pairs)} 超过上限 {cfg['max_cross']}，"
                                  f"按 L1 强度截断"})
        pairs = pairs[:cfg["max_cross"]]

    _log(f"── L2 交叉（{len(pairs)} 对，已用预算 {used}/{budget}）", quiet)
    for a, b in pairs:
        if used >= budget:
            skipped.append({"stage": "L2",
                            "pair": [a["feature_id"], b["feature_id"]],
                            "reason": "查询预算耗尽，未执行"})
            continue
        conds = [a["cond"], b["cond"]]
        # 条件去重后不足 2 条 → 实际是单条件，已由 L1 覆盖
        if len({c.strip() for c in conds}) < 2:
            skipped.append({"stage": "L2", "pair": [a["feature_id"], b["feature_id"]],
                            "reason": "两个条件的 SQL 完全相同，等价于单条件，不重复查"})
            continue
        conflict, why = cs.conds_conflict(conds)
        if conflict:
            skipped.append({"stage": "L2", "pair": [a["feature_id"], b["feature_id"]],
                            "reason": f"逻辑互斥：{why}"})
            continue
        # 条件蕴含：一条完全包含另一条，求交后等于其中一条，白跑一遍
        # 只会拿回与单条件相同的数字，然后被判「叠加无增量」。
        subsumed, swhy = cs.conds_subsumed(conds)
        if subsumed:
            skipped.append({"stage": "L2", "pair": [a["feature_id"], b["feature_id"]],
                            "reason": f"条件冗余：{swhy}，求交等价于单条件"})
            continue
        try:
            g = run_groups(conds, "combo")
            # 父群 = 去掉第二个条件，用于判「叠加是否带来增量」
            pg = run_groups([a["cond"]], "parent")
            used += 2
        except Exception as exc:      # noqa: BLE001
            skipped.append({"stage": "L2", "pair": [a["feature_id"], b["feature_id"]],
                            "reason": f"取数失败：{exc}"})
            used += 1
            continue
        st, m = cs.screen(g.get("hit"), g.get("nonhit"), g.get("universe"),
                          [{"feature_id": a["feature_id"], "name": a["name"],
                            "cond": a["cond"], "hit": g.get("hit"),
                            "nonhit": g.get("nonhit"), "universe": g.get("universe")},
                           {"feature_id": b["feature_id"], "name": b["name"],
                            "cond": b["cond"], "hit": g.get("hit"),
                            "nonhit": g.get("nonhit"), "universe": g.get("universe")}],
                          level="chg", parent=pg.get("hit"))
        item = {
            "features": [a["feature_id"], b["feature_id"]],
            "conds": conds,
            "status": st,
            "lift": (m or {}).get("lift_vs_baseline"),
            "p_value": (m or {}).get("p_value"),
            "incremental_lift": (m or {}).get("incremental_lift"),
            "hit_n": (m or {}).get("hit_n"),
            "baseline_used": (m or {}).get("baseline_used"),
            "reason": (m or {}).get("reason"),
            "metrics": m,
        }
        l2.append(item)
        if st == "phenomenon":
            phenomena.append({
                "kind": "combo", "features": [a["feature_id"], b["feature_id"]],
                "conds": conds,
                "name": f"{a['name']} + {b['name']}",
                "lift": item["lift"], "p_value": item["p_value"],
                "hit_n": item["hit_n"], "baseline_used": item["baseline_used"],
            })
        _log(f"   L2 {a['feature_id']}+{b['feature_id']:<3} "
             f"lift={item['lift'] if item['lift'] is not None else '—':>6} "
             f"incr={item['incremental_lift']} → {st}", quiet)

    # ==================== L3：汇总 ====================
    # 排序显式化，保证下游顺序确定
    phenomena.sort(key=lambda x: (-(x.get("lift") or 0),
                                  x.get("p_value") if x.get("p_value") is not None else 1,
                                  tuple(x.get("features") or [])))

    exhausted = used >= budget
    result = {
        "schema_version": SCHEMA_VERSION,
        "kind": "bounded_search",
        "criteria": cfg,
        "l1": l1,
        "l2": l2,
        "phenomena": phenomena,
        "phenomena_total": len(phenomena),
        "budget": {
            "used": used,
            "total": budget,
            "remaining": max(budget - used, 0),
            "exhausted": exhausted,
        },
        "skipped": skipped,
        "summary": {
            "L1_tested": len(l1),
            "L1_significant": len(expandable),
            "L2_tested": len(l2),
            "L2_crossed": len(pairs),
            "phenomena": len(phenomena),
            "by_kind": {
                "single": sum(1 for p in phenomena if p["kind"] == "single"),
                "combo": sum(1 for p in phenomena if p["kind"] == "combo"),
            },
        },
        # 预算耗尽时必须显式告警：未查完 ≠ 无风险
        "warnings": ([f"查询预算 {budget} 已耗尽，仍有候选未执行 —— "
                      f"未执行的维度不代表没有风险"]
                     if exhausted else []),
    }
    return result


# ============================================================ CLI

def main():
    import argparse
    import drill_executor as dx
    import duckdb

    ap = argparse.ArgumentParser(description="确定性有界搜索")
    ap.add_argument("--signals", required=True, help="signals.json")
    ap.add_argument("--slice", default="20260831")
    ap.add_argument("--base-slice", required=True)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--level", default="chg")
    ap.add_argument("--budget", type=int, default=DEFAULT_SEARCH["query_budget"])
    ap.add_argument("--max-cross", type=int, default=DEFAULT_SEARCH["max_cross"])
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    sig = json.load(open(args.signals, encoding="utf-8"))
    rows = []
    # 信号表结构：dimensions / features 里带 feature_id 与 norm
    for key in ("features", "signals", "rows"):
        for r in (sig.get(key) or []):
            if isinstance(r, dict) and r.get("feature_id") is not None:
                rows.append(r)
    if not rows:
        for _dim, d in (sig.get("dimensions") or {}).items():
            for b in (d.get("buckets") or []):
                if b.get("feature_id") is not None:
                    rows.append(b)

    con = duckdb.connect()

    def run_groups(conds, kind):
        sql = cs.split_sql(conds, args.slice, level=args.level,
                           base_slice=args.base_slice) if len(conds) > 1 else \
              cs.single_sql(conds[0], args.slice, level=args.level,
                            base_slice=args.base_slice)
        cols, rws, _ = dx.run_sql(con, sql, args.data_dir)
        return {r[0]: dict(zip(cols, r)) for r in rws}

    cfg = {**DEFAULT_SEARCH, "query_budget": args.budget, "max_cross": args.max_cross}
    res = search(rows, run_groups, cfg=cfg)
    json.dump(res, open(args.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    b = res["budget"]
    print(f"✅ 有界搜索：L1 {res['summary']['L1_tested']} / "
          f"显著 {res['summary']['L1_significant']} / "
          f"L2 {res['summary']['L2_tested']} / "
          f"现象 {res['phenomena_total']}（预算 {b['used']}/{b['total']}）")
    for p in res["phenomena"][:8]:
        print(f"   [{p['kind']}] {p['name']} lift={p['lift']}")
    if res["warnings"]:
        for w in res["warnings"]:
            print(f"   ⚠️  {w}")
    print(f"   → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
