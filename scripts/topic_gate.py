#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""topic_gate.py — 归因的两道可证伪校验 + 主题名额（不设下限）

背景
----
原来的 `attribution.topic_decision` 只按 strength 过阈值，不做任何与
「风险现象」的匹配检验，于是出现两类问题：
  1. 弱相关归因照样进主题（「不良率高 → 建议加强管理」这种无法证伪的话）
  2. 多个主题共用同一批数字，读者以为是多个独立发现

本模块只做两件事，都基于**实测数据**（combo_screen 的 phenomenon 结果 +
drill evidence 的 comparisons），不引用任何预聚合复用值：

第一道 `phenomenon_gate`：这个组合是否构成一个**风险现象**
    —— 在 combo_split.screen 里已算（lift / 样本 / 增量），这里只做复核与
       对外口径统一，不重复计算。

第二道 `attribution_gate`：现象与归因之间是否**确实相关/可解释**
    用钻取实测数字检验归因假设的三个可证伪条件：
      a) 方向一致：归因指向的客群，不良率必须真的更高（lift ≥ 门槛）
      b) 非平凡：对照组不能跟着一起高（否则是全辖共性，不是这个归因）
      c) 有区分度：归因客群与对照组的不良率差异，要显著大于组合内部的
         其它切分（否则真正的驱动是别的维度，这个归因是「搭便车」）
    三条全过 → `supported`；过部分 → `weak`；基本不过 → `rejected`。
    判定为 `weak` / `rejected` 的主题**不进报告**，从候选池补位。

第三件事 `select_topics`：按 strength 排序取前 N 个通过两道校验的主题。
    N 默认 10，但**不设下限** —— 通过几个报几个，绝不为了凑数放宽门槛。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402

SCHEMA_VERSION = "3.0"

# 第二道校验的门槛。全部可用 overrides 覆盖，便于真实数据调参而不改代码。
DEFAULT_ATTRIBUTION_GATE = {
    "min_lift": 1.5,          # 归因客群不良率至少是全辖的 1.5 倍
    "max_nonhit_lift": 1.35,  # 对照组不能也高（高于此值说明是全辖共性）
    "min_separation": 1.25,   # 归因客群 lift ÷ 对照组 lift 的分离度下限
    "min_n": 100,             # 归因客群样本下限
    "max_p_value": 0.05,      # 比例差异检验（正态近似）显著性水平
}

MAX_TOPICS_DEFAULT = 10


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _z_test_two_prop(p1, n1, p2, n2):
    """两组不良率的比例差异检验（正态近似），返回双侧 p 值。

    用不良**户数**近似二项分布：不良率按余额加权，这里退化为客户级
    不良占比做检验，仅用于判断「差异是否可能由抽样波动导致」，
    不作为不良率本身的点估计。样本不足时返回 None（不硬算）。
    """
    import math
    if not all(v is not None for v in (p1, n1, p2, n2)):
        return None
    if n1 <= 0 or n2 <= 0:
        return None
    p_pool = (p1 * n1 + p2 * n2) / (n1 + n2)
    if not (0 < p_pool < 1):
        return None
    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    if se <= 0:
        return None
    z = abs(p1 - p2) / se
    # 双侧 p 值，用 erfc 避免依赖 scipy
    return math.erfc(z / math.sqrt(2))


def phenomenon_gate(combo):
    """第一道复核：组合是否构成风险现象。

    combo 来自 combo_screen.phenomena[]（已通过 combo_split.screen），
    这里只做字段归一与口径说明，重新判定一律以 combo_split 为准，
    避免两处逻辑漂移。
    """
    m = combo.get("metrics") or {}
    ok = combo.get("status") == "phenomenon"
    return {
        "gate": "phenomenon",
        "passed": ok,
        "status": combo.get("status"),
        "reason": m.get("reason") or ("构成风险现象" if ok else "不构成风险现象"),
        "hit_n": m.get("hit_n"),
        "universe_n": m.get("universe_n"),
        "hit_rate": m.get("hit_rate"),
        "universe_rate": m.get("universe_rate"),
        "lift_vs_universe": m.get("lift_vs_universe"),
        "incremental_lift": m.get("incremental_lift"),
        "raw": combo,
    }


def attribution_gate(comparisons, cfg=None):
    """第二道校验：风险现象 与 归因假设 是否确实相关/可解释。

    comparisons: drill evidence 里该主题的 `comparisons`，
                 形如 [{"hit": {...}, "nonhit": {...}, "lift": x}]

    校验三件事（全部基于实测钻取数字）：
      a) 方向一致 —— 归因客群 lift ≥ min_lift
      b) 非平凡   —— 对照组 lift ≤ max_nonhit_lift（否则是全辖共性）
      c) 有区分度 —— 归因客群相对对照组的分离度 ≥ min_separation，
                     且比例差异检验 p ≤ max_p_value

    返回 status ∈ {supported, weak, rejected, insufficient}
    """
    cfg = {**DEFAULT_ATTRIBUTION_GATE, **(cfg or {})}
    if not comparisons:
        return {"gate": "attribution", "passed": False, "status": "insufficient",
                "reason": "无钻取实测数据，无法检验归因与现象的相关性"}

    cmp0 = comparisons[0] or {}
    hit = cmp0.get("hit") or {}
    nonhit = cmp0.get("nonhit") or {}
    hr, hnr = _num(hit.get("npl_rate")), _num(nonhit.get("npl_rate"))
    hn, nnn = _num(hit.get("n")), _num(nonhit.get("n"))
    lift = _num(cmp0.get("lift"))

    if hr is None or hnr is None or not hn or not nnn:
        return {"gate": "attribution", "passed": False, "status": "insufficient",
                "reason": "钻取结果缺少不良率或样本量"}

    if hn < cfg["min_n"]:
        return {"gate": "attribution", "passed": False, "status": "insufficient",
                "reason": f"归因客群样本 {hn:.0f} < {cfg['min_n']}", "hit_n": hn}

    # 对照组相对全辖的 lift
    uni_rate = None
    total_n = (hn or 0) + (nnn or 0)
    if total_n > 0:
        uni_rate = (hr * hn + hnr * nnn) / total_n
    nonhit_lift = (hnr / uni_rate) if (uni_rate and uni_rate > 0) else None
    separation = (lift / nonhit_lift) if (lift and nonhit_lift) else None
    p = _z_test_two_prop(hr, hn, hnr, nnn)

    checks = {
        "direction": {
            "ok": bool(lift is not None and lift >= cfg["min_lift"]),
            "value": round(lift, 4) if lift else None,
            "threshold": cfg["min_lift"],
            "desc": "归因指向的客群，不良率确实更高",
        },
        "non_trivial": {
            "ok": bool(nonhit_lift is not None and nonhit_lift <= cfg["max_nonhit_lift"]),
            "value": round(nonhit_lift, 4) if nonhit_lift else None,
            "threshold": cfg["max_nonhit_lift"],
            "desc": "对照组没有一起高，说明不是全辖共性",
        },
        "separation": {
            "ok": bool(separation is not None and separation >= cfg["min_separation"]),
            "value": round(separation, 4) if separation else None,
            "threshold": cfg["min_separation"],
            "desc": "归因客群与对照组有明确区分度",
        },
        "significance": {
            "ok": bool(p is not None and p <= cfg["max_p_value"]),
            "value": round(p, 6) if p is not None else None,
            "threshold": cfg["max_p_value"],
            "desc": "差异不太可能由抽样波动导致",
        },
    }

    passed_n = sum(1 for c in checks.values() if c["ok"])
    failed = [k for k, c in checks.items() if not c["ok"]]

    if passed_n == 4:
        status, reason = "supported", "方向、非平凡、区分度、显著性四项全部通过"
    elif checks["direction"]["ok"] and checks["separation"]["ok"]:
        status = "weak"
        reason = f"方向与区分度成立，但未通过：{'、'.join(_desc(k, checks) for k in failed)}"
    else:
        status = "rejected"
        reason = f"归因与现象相关性不足，未通过：{'、'.join(_desc(k, checks) for k in failed)}"
    return {
        "gate": "attribution",
        "passed": status == "supported",
        "status": status,
        "reason": reason,
        "checks": checks,
        "failed_checks": failed,
        "hit_n": hn, "nonhit_n": nnn,
        "hit_rate": round(hr, 6), "nonhit_rate": round(hnr, 6),
        "lift": round(lift, 4) if lift else None,
    }


def _desc(key, checks):
    cn = {"direction": "方向不一致", "non_trivial": "对照组同样偏高（全辖共性）",
          "separation": "区分度不足", "significance": "差异不显著"}
    return cn.get(key) or str(key)


def select_topics(gated, max_topics=MAX_TOPICS_DEFAULT):
    """按通过的候选排序取前 N 个。

    **不设下限**：通过几个就返回几个。不足 max_topics 时，在返回结构里
    明确写出 shortage 与原因，让报告如实交代「本期只有 N 个成立的主题」，
    绝不放宽门槛凑数。
    """
    # 入参允许两种形态：run() 产出的完整 gated 项（both_passed），
    # 或已预筛过的精简项（already passed）。两者都认，避免重复过滤导致清零。
    passed = [g for g in gated
              if g.get("both_passed") is True
              or (g.get("both_passed") is None and g.get("attribution", {}).get("passed"))]
    passed.sort(key=lambda g: -(_num(g.get("strength")) or 0))
    chosen = passed[:max_topics]
    for i, g in enumerate(chosen, 1):
        g["topic_id"] = f"T{i:03d}"
    dropped = passed[max_topics:]
    return {
        "topics": chosen,
        "count": len(chosen),
        "max_topics": max_topics,
        "candidates_passed": len(passed),
        "dropped_by_cap": len(dropped),
        "shortage": max(0, max_topics - len(chosen)),
        "shortage_note": (
            "" if len(chosen) >= max_topics else
            f"通过两道校验的候选只有 {len(chosen)} 个（上限 {max_topics}），"
            f"按门槛如实报告，未放宽条件凑数"
        ),
    }


def run(combo_screen, evidence, attributions, max_topics=MAX_TOPICS_DEFAULT, cfg=None):
    """串起两道校验，产出最终主题清单。

    combo_screen: combo_screen.json（含 phenomena[]）
    evidence:     evidence.json（含 evidence_chain[]，按 linked_rule 分组）
    attributions: attribution.json 的 topics[]（提供 strength/name/rule_id）
    """
    phenomena = combo_screen.get("phenomena") or []
    ev_by_rule = {}
    for e in (evidence.get("evidence_chain") or []):
        ev_by_rule.setdefault(e.get("linked_rule"), []).append(e)

    gated = []
    for t in attributions:
        rid = t.get("rule_id")
        # 第一道：这个归因对应的组合是否构成风险现象
        # 优先按规则里引用的组合匹配；匹配不到则如实记录
        combo = next((c for c in phenomena if rid in (c.get("linked_rules") or [])), None)
        ph = phenomenon_gate(combo) if combo else {
            "gate": "phenomenon", "passed": False, "status": "not_screened",
            "reason": "该规则的组合未进入 combo_screen 的现象清单（未做真实求交或未通过）",
        }
        evs = ev_by_rule.get(rid) or []
        verified = [x for x in evs if x.get("status") == "verified"] or evs
        cmp_all = []
        for x in verified:
            cmp_all.extend(x.get("comparisons") or [])
        at = attribution_gate(cmp_all, cfg)
        gated.append({
            "rule_id": rid, "name": t.get("name"), "strength": t.get("strength"),
            "level": t.get("level"), "phenomenon": ph, "attribution": at,
            "both_passed": bool(ph.get("passed") and at.get("passed")),
        })

    sel = select_topics([g for g in gated if g["both_passed"]], max_topics=max_topics)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "topic_gate",
        "criteria": {**DEFAULT_ATTRIBUTION_GATE, **(cfg or {})},
        "gated": gated,
        "selection": sel,
        "reject_reasons": _reason_summary(gated),
    }


def _reason_summary(gated):
    cnt = {}
    for g in gated:
        if g["both_passed"]:
            continue
        ph, at = g.get("phenomenon") or {}, g.get("attribution") or {}
        key = "现象未成立" if not ph.get("passed") else f"归因{at.get('status')}"
        cnt[key] = cnt.get(key, 0) + 1
    return cnt


def main(argv=None):
    import argparse
    import json

    ap = argparse.ArgumentParser(description="两道校验 + 主题名额")
    ap.add_argument("--combo-screen", required=True)
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--attribution", required=True)
    ap.add_argument("--max-topics", type=int, default=MAX_TOPICS_DEFAULT)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    doc = json.load(open(args.combo_screen, encoding="utf-8"))
    ev = json.load(open(args.evidence, encoding="utf-8"))
    at = json.load(open(args.attribution, encoding="utf-8"))
    res = run(doc, ev, at.get("topics") or [], max_topics=args.max_topics)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    s = res["selection"]
    print(f"✅ 主题闸门：候选 {len(res['gated'])} → 通过 {s['candidates_passed']} → 入选 {s['count']}"
          f"（上限 {s['max_topics']}）")
    if s["shortage"]:
        print(f"   注：{s['shortage_note']}")
    if res["reject_reasons"]:
        print(f"   淘汰原因：{res['reject_reasons']}")
    print(f"   → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
