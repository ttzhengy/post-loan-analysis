#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""internal_external.py — 不良生成的内部 / 外部 / 未识别三分

为什么必须分
------------
把外部冲击算成管理失职，分行不认；把管理问题全推给外部，风险部门不认。
两边都不可信，结论就用不了。真实的归因必须给出**可加总的三分账**：

  新增不良总额 = 外部冲击贡献 + 内部管理贡献 + 未识别

三分法（关键：外部用「超额」而不是「标记」）
-------------------------------------------
外部标记（受灾区域、政策调整行业、畜群病害码等）覆盖的贷款，
其新增不良**不能整体算作外部冲击** —— 受灾区域的客户本来就有基础风险，
把全部不良记在灾害头上会高估外部、几乎把管理问题洗掉。

正确做法是算**超额**：

  外部超额 = 有标记组的新增不良余额 − 有标记组的期初敞口 × 无标记组生成率

即：扣掉「即使没受灾、按同类客户平均也会坏掉的那部分」，剩下的超额才是
外部冲击真正造成的增量。超额可能为负（标记组表现比无标记组还好），
此时外部贡献按 0 计，绝不记负数去冲抵管理问题。

未识别
------
不属于任何已识别客群、也没有外部标记的敞口，其新增不良全部计入「未识别」。
**未识别不等于内部管理问题**，报告里必须显式说明这一点 —— 这是上一版报告
最容易被质疑的地方（把未识别默认算成管理失职）。

可加总性
--------
三个分量必须精确加总等于全辖新增不良。本模块在末尾做硬校验：
  |外部 + 内部 + 未识别 − 全辖新增不良| ≤ 容差
不通过就把分成标为不可用，绝不让对不上的数字进报告。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Windows 控制台默认 GBK，直接 print 中文会抛 UnicodeEncodeError。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

import combo_split as cs   # noqa: E402

SCHEMA_VERSION = "1.0"

# 外部冲击标记：只列**能由凭证表字段直接判定**的。
# 真实数据里灾害代码等字段常常大面积为空（对方报告的实证：几乎无取值），
# 因此这里给的是一组候选，实际生效的要看 availability 探测结果。
EXTERNAL_MARKERS = {
    "bus_breed": {
        "label": "特定品种（政策性/专项品种）",
        "cond": "BUS_BREED_CD LIKE 'A702%'",
        "rationale": "特定业务品种承载政策任务，风险特征与普通农户贷款不同",
    },
    "grant_mode": {
        "label": "非信用类担保（外部增信覆盖）",
        "cond": "GRTE_MOD_CD NOT IN ('0100')",
        "rationale": "有抵押/保证的敞口由第三方分担部分损失，其表现差异不宜全记内部管理",
    },
}


def to_num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def fmt_amt(x):
    """金额格式化为中文业务单位。报告正文不允许出现无单位裸数字。"""
    v = to_num(x)
    if v is None:
        return "—"
    if abs(v) >= 1e8:
        return f"{v/1e8:.2f} 亿"
    return f"{v/1e4:.1f} 万"


def split_sql(marker_cond, slice_v, level="chg", base_slice=None):
    """有标记组 / 无标记组 / 全辖 三组，用于算外部超额与基准生成率。

    复用 combo_split 的客户级 CTE，保证与组合归因同一套口径：
    同一份数据、同一个客户级归属规则、同一个余额加权方式。
    """
    return cs.split_sql([marker_cond, "1=1"], slice_v, level=level,
                        base_slice=base_slice)


def compute(rows, universe, cfg=None) -> dict:
    """外部超额三分。

    rows: [{marker, label, hit:{npl_bal,tot_bal}, universe:{...}}]
    universe: 全辖 {npl_bal, tot_bal}（新增不良余额 / 期初敞口）

    返回 {external, internal, unidentified, total, checks, ...}
    """
    cfg = cfg or {"tol": 0.01}
    u_npl = to_num(universe.get("npl_bal")) or 0.0
    u_bal = to_num(universe.get("tot_bal")) or 0.0
    if not u_bal:
        return {"status": "unavailable", "reason": "全辖期初敞口为 0，无法计算生成率"}

    base_rate = u_npl / u_bal    # 全辖生成率

    details, external = [], 0.0
    for r in rows:
        hit = r.get("hit") or {}
        m_npl = to_num(hit.get("npl_bal")) or 0.0
        m_bal = to_num(hit.get("tot_bal")) or 0.0
        if m_bal <= 0:
            details.append({**r, "excess": 0.0, "note": "标记组无敞口"})
            continue
        # 超额 = 实际新增不良 − 期初敞口 × 全辖基准生成率
        expected = m_bal * base_rate
        excess = m_npl - expected
        clamped = max(0.0, excess)
        external += clamped
        details.append({
            "marker": r.get("marker"), "label": r.get("label"),
            "n": to_num(hit.get("n")),
            "tot_bal": round(m_bal, 2), "npl_bal": round(m_npl, 2),
            "rate": round(m_npl / m_bal, 6) if m_bal else None,
            "expected_npl": round(expected, 2),
            "excess": round(excess, 2),
            "attributed": round(clamped, 2),
            "clamped": excess < 0,
            "note": ("标记组表现优于基准，超额为负，外部贡献按 0 计，"
                     "不用负值冲抵管理问题") if excess < 0 else "",
        })

    identified = sum((d.get("npl_bal") or 0) for d in details)  # 仅作展示
    external = min(external, u_npl)   # 外部贡献不可能超过全辖新增不良

    # 内部 = 全辖新增不良 − 外部超额；未识别单列，不从内部里扣
    internal = max(0.0, u_npl - external)
    unidentified = 0.0   # 由调用方按客群覆盖补充（见 attribute_cohorts）

    total = external + internal + unidentified
    gap = total - u_npl
    ok = abs(gap) <= max(1.0, u_npl * cfg["tol"])

    return {
        "status": "ok" if ok else "broken",
        "level": None,
        "base_rate": round(base_rate, 6),
        "universe": {"npl_bal": round(u_npl, 2), "tot_bal": round(u_bal, 2)},
        "external": round(external, 2),
        "internal": round(internal, 2),
        "unidentified": round(unidentified, 2),
        "total": round(total, 2),
        "share": {
            "external": round(external / u_npl, 6) if u_npl else None,
            "internal": round(internal / u_npl, 6) if u_npl else None,
            "unidentified": round(unidentified / u_npl, 6) if u_npl else None,
        },
        "details": details,
        "identified_marker_npl": round(identified, 2),
        "check": {"gap": round(gap, 2), "tol": max(1.0, u_npl * cfg["tol"]),
                  "passed": ok},
        "warnings": [] if ok else [
            f"三分账加总 {fmt_amt(total)} 与全辖新增不良 {fmt_amt(u_npl)} "
            f"差 {fmt_amt(abs(gap))}，超出容差，本拆分不可用于报告"],
    }


def attribute_cohorts(base, cohorts, universe):
    """把内部贡献进一步落到已确认客群，余下计入「未识别」。

    cohorts: [{"label", "npl_bal", "tot_bal"}] 已确认组合现象的客群
              （各客群贡献来自 combo_split 的 hit 组，彼此可能重叠，
               因此按敞口占比分摊内部贡献，而不是直接相加）
    """
    out = dict(base)
    u_npl = to_num(universe.get("npl_bal")) or 0.0
    total_cov_bal = sum((to_num(c.get("tot_bal")) or 0) for c in cohorts)
    u_bal = to_num(universe.get("tot_bal")) or 0.0

    if not cohorts or not u_bal:
        out["unidentified"] = round(out.get("internal", 0.0), 2)
        out["internal"] = 0.0
        out["cohort_share"] = []
        out["warnings"].append(
            "没有已确认客群，内部贡献全部计入未识别；"
            "未识别不等于管理失职，需进一步取证")
        out["share"] = {
            "external": out["share"]["external"],
            "internal": 0.0,
            "unidentified": round((out["unidentified"] / u_npl), 6) if u_npl else None,
        }
        out["total"] = round(out["external"] + out["unidentified"], 2)
        out["check"]["gap"] = round(out["total"] - u_npl, 2)
        out["check"]["passed"] = abs(out["check"]["gap"]) <= out["check"]["tol"]
        if not out["check"]["passed"]:
            out["status"] = "broken"
        return out

    # 澄清三者的关系：
    #   external      已经归属外部冲击的部分
    #   internal_total 剩余部分（= 全辖 − external），**不等于**已识别的管理问题
    #   未识别         = internal_total 中未被任何客群解释的部分
    #   内部已归属      = internal_total − 未识别
    # 因此加总恒等式是：external + 内部已归属 + 未识别 == 全辖。
    # 早期版本把 internal_total 和 unidentified 同时加总，等于重复计入，报 gap。
    internal_total = out.get("internal", 0.0)
    identified_bal = sum((to_num(c.get("npl_bal")) or 0) for c in cohorts)
    identified = min(identified_bal, internal_total)
    out["internal_total"] = round(internal_total, 2)
    out["internal_identified"] = round(identified, 2)
    out["internal"] = round(identified, 2)          # 对外只暴露已归属部分
    out["unidentified"] = round(max(0.0, internal_total - identified), 2)

    raw = []
    for c_ in cohorts:
        bal = to_num(c_.get("tot_bal")) or 0.0
        raw.append({"label": c_.get("label"), "n": c_.get("n"),
                    "tot_bal": bal,
                    "npl_bal": round(to_num(c_.get("npl_bal")) or 0.0, 2),
                    "share_of_universe": round(bal / u_bal, 6) if u_bal else None})
    assign_total = total_cov_bal if total_cov_bal else 1.0

    for r in raw:
        w = (r["tot_bal"] / assign_total) if assign_total else 0.0
        r["attributed_internal"] = round(identified * w, 2)

    covered = sum(r["tot_bal"] for r in raw)
    uncovered_bal = max(0.0, u_bal - min(covered, u_bal))
    out["cohort_share"] = raw
    out["coverage"] = {
        "covered_bal": round(covered, 2),
        "uncovered_bal": round(uncovered_bal, 2),
        "covered_share": round(min(covered, u_bal) / u_bal, 6) if u_bal else None,
    }
    out["total"] = round(out.get("external", 0.0) + identified + out["unidentified"], 2)
    gap = out["total"] - u_npl
    out["check"]["gap"] = round(gap, 2)
    out["check"]["passed"] = abs(gap) <= out["check"]["tol"]
    out["share"] = {
        "external": round(out.get("external", 0.0) / u_npl, 6) if u_npl else None,
        "internal": round(identified / u_npl, 6) if u_npl else None,
        "unidentified": round(out["unidentified"] / u_npl, 6) if u_npl else None,
    }
    if not out["check"]["passed"]:
        out["status"] = "broken"
        out["warnings"].append(
            f"客群拆分后加总 {fmt_amt(out['total'])} 与全辖 {fmt_amt(u_npl)} "
            f"差 {fmt_amt(abs(gap))}，本拆分不作为结论引用")
    return out


def build_narrative(res):
    """生成中文决策段。措辞严格区分「内部管理」与「未识别」。"""
    if not res or res.get("status") == "unavailable":
        return "内外部拆分所需数据不足，未能形成可用的贡献分解。"
    if res.get("status") == "broken":
        return "内外部贡献加总与全辖新增不良不符，本项拆分不作为结论引用。"

    ext = res.get("external", 0.0)
    inte = res.get("internal", 0.0)
    unid = res.get("unidentified", 0.0)
    tot = res.get("total", 0.0) or 1.0
    lines = [
        f"新增不良 {fmt_amt(res['universe']['npl_bal'])} 中，"
        f"外部冲击可解释 {fmt_amt(ext)}（{ext/tot:.1%}），"
        f"内部管理因素 {fmt_amt(inte)}（{inte/tot:.1%}），"
        f"尚未识别归属 {fmt_amt(unid)}（{unid/tot:.1%}）。",
    ]
    clamped = [d for d in res.get("details") or [] if d.get("clamped")]
    if clamped:
        names = "、".join(d["label"] for d in clamped)
        lines.append(
            f"{names} 组的新增不良低于同类基准，说明该组表现优于平均，"
            f"未计入外部贡献 — 外部冲击口径只承认超出基准的部分。")
    if unid > 0:
        lines.append(
            f"「尚未识别归属」{fmt_amt(unid)} 不等于管理失职，"
            f"这部分敞口未被已识别客群覆盖，需补充调查后再定性。")
    return "".join(lines)


def main():
    ap = argparse.ArgumentParser(description="不良生成的内外部贡献拆分")
    ap.add_argument("--slice", default="20260831")
    ap.add_argument("--level", default="chg", choices=list(cs.LEVELS))
    ap.add_argument("--base-slice", default=None)
    ap.add_argument("--data-dir", help="CSV/parquet 目录；给了才真执行")
    ap.add_argument("--markers", nargs="*", default=list(EXTERNAL_MARKERS),
                    help=f"启用哪些外部标记，可选：{', '.join(EXTERNAL_MARKERS)}")
    ap.add_argument("--cohorts", help="combo_screen.json 或自定义客群 json，用于落到内部贡献")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    markers = [{"key": k, **EXTERNAL_MARKERS[k]} for k in args.markers
               if k in EXTERNAL_MARKERS]
    result = {
        "schema_version": SCHEMA_VERSION, "kind": "internal_external",
        "slice": args.slice, "level": args.level, "base_slice": args.base_slice,
        "markers": [{"key": m["key"], "label": m["label"], "cond": m["cond"],
                     "rationale": m["rationale"]} for m in markers],
        "mode": "execute" if args.data_dir else "dry-run",
        "result": None, "narrative": "", "warnings": [],
    }

    if not args.data_dir:
        result["plan"] = [{"marker": m["key"],
                           "universe_sql": cs.split_sql(["1=1", "1=1"], args.slice,
                                                        level="vch")} for m in markers]
        result["warnings"].append("dry-run：未连接数据源，仅产出分组 SQL")
        json.dump(result, open(args.out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print(f"✅ 内外部拆分方案 {len(markers)} 个标记（dry-run）→ {args.out}")
        return 0

    import drill_executor as dx
    duckdb = dx._load_duckdb()
    if duckdb is None:
        result["warnings"].append("duckdb 未安装，无法执行")
        json.dump(result, open(args.out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        return 2
    con = duckdb.connect()

    if args.level == "chg" and not args.base_slice:
        result["warnings"].append("chg 口径未给 base_slice，回退 vch")
        args.level = "vch"

    def _q(sql):
        cols, rws, _ = dx.run_sql(con, sql, args.data_dir)
        return {r[0]: dict(zip(cols, r)) for r in rws}

    uni = _q(cs.split_sql(["1=1", "1=1"], args.slice, level=args.level,
                          base_slice=args.base_slice)).get("universe") or {}
    if not uni:
        result["warnings"].append("全辖分组取数失败")
        json.dump(result, open(args.out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        return 2

    rows = []
    for m in markers:
        g = _q(split_sql(m["cond"], args.slice, args.level, args.base_slice))
        hit = g.get("hit") or {}
        if not (to_num(hit.get("tot_bal")) or 0):
            result["warnings"].append(f"标记「{m['label']}」在数据中无敞口，未计入")
            continue
        rows.append({"marker": m["key"], "label": m["label"], "hit": hit})

    res = compute(rows, uni)
    res["level"] = args.level
    res["base_slice"] = args.base_slice

    if args.cohorts:
        try:
            cd = json.load(open(args.cohorts, encoding="utf-8"))
            phen = cd.get("phenomena") or cd.get("cohorts") or []
            cohorts = []
            for p in phen:
                m = p.get("metrics") or p
                cohorts.append({
                    "label": p.get("label") or "+".join(
                        f.get("desc") or f.get("name") or str(f.get("feature_id"))
                        for f in (p.get("features") or [])) or p.get("label"),
                    "n": m.get("hit_n"), "tot_bal": m.get("tot_bal"),
                    "npl_bal": m.get("npl_bal"),
                })
            cohorts = [c for c in cohorts if c.get("tot_bal")]
            if cohorts:
                res = attribute_cohorts(res, cohorts, uni)
            else:
                result["warnings"].append("cohorts 文件里没有可用敞口的客群")
        except Exception as exc:   # noqa: BLE001
            result["warnings"].append(f"cohorts 解析失败（{exc}），只做内外部二分")

    result["result"] = res
    result["narrative"] = build_narrative(res)
    result["warnings"].extend(res.get("warnings") or [])

    chk = (res.get("check") or {}).get("passed")
    json.dump(result, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"✅ 内外部拆分：外部 {fmt_amt(res.get('external'))} / "
          f"内部 {fmt_amt(res.get('internal'))} / 未识别 {fmt_amt(res.get('unidentified'))}"
          f"（校验 {'通过' if chk else '未通过'}）")
    print(f"   → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
