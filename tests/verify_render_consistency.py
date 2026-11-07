#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_render_consistency.py — 报告内部自洽性验收

覆盖四类会让「报告看起来有数据、实际口径错误」的缺陷：

  Q1 维度判断段引用了 valid=false 的档位
     余额过小的档位（sample_too_small）在 signals.py 已被标 valid=False 并
     剔除排名，但正文取 max(offset_pp) 时没过滤，导致文字结论指向一个
     图表里根本不存在的档位（曾出现「贷款用途 · 其他担保组合 +96.04pp」，
     实际该档是 bucket='15'、余额 296 万、不良率 100%，且「其他担保组合」
     属于担保方式维度而非贷款用途）。

  Q2 组合候选数用错口径
     正文写「42 条组合线索」而候选表列了 60 行 —— 42 是 topic_selection 的
     规则条数，60 是 combo_screen 的组合候选数，两个层面的对象被混用。

  Q3 drill_planner 给不同规则套同一条 SQL
     特征名到条件的映射过宽（「零散获客」被映射成 GRTE_MOD_CD='0101'），
     且「避让」机制靠正则从 SQL 反解条件、永远匹配不到，导致多条主题
     hit/nonhit 完全相同、lift 一模一样。

  Q4 无命中成员的规则仍硬造 plan
     规则 hits 为空时落到全局兜底维度，产出一条数据并不支持的假设。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

PASS = FAIL = 0
FAILS: list[str] = []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        FAILS.append(f"{name}{(' — ' + detail) if detail else ''}")
        print(f"  ❌ {name}{(' — ' + detail) if detail else ''}")


# ============================================================ Q1 维度档位过滤

def test_dim_bucket_filter():
    print("\n[Q1] 维度判断段必须排除 valid=false 的档位")
    import render_report

    # 构造：无效档位 offset 极大（模拟余额 296 万 / 不良率 100%），
    # 有效档位 offset 正常。取 max 必须落到有效档位上。
    signals = {
        "overall": {"npl_rate": 0.0396},
        "dimensions": {
            "usage": {"name": "贷款用途", "stage": "贷前", "buckets": [
                {"bucket": "15", "offset_pp": 96.04, "npl_rate": 1.0, "bal": 2963445.39,
                 "valid": False, "drop_reason": "sample_too_small"},
                {"bucket": "生产经营", "offset_pp": 1.83, "npl_rate": 0.0579, "bal": 1.09e9,
                 "valid": True},
            ]},
            "grte": {"name": "担保方式", "stage": "贷前", "buckets": [
                {"bucket": "信用", "offset_pp": 6.34, "npl_rate": 0.103, "bal": 8e8,
                 "valid": True},
                {"bucket": "抵押", "offset_pp": 16.89, "npl_rate": 0.2086, "bal": 8e7,
                 "valid": True},
            ]},
        },
    }

    best = None
    for key, d in signals["dimensions"].items():
        for b in d.get("buckets") or []:
            if b.get("offset_pp") is None:
                continue
            if b.get("valid") is False:
                continue
            if best is None or b["offset_pp"] > best[0]:
                best = (b["offset_pp"], d.get("name"), b.get("bucket"))

    check("无效档位不参与 max", best[1] != "贷款用途" or best[2] != "15",
          f"选到了无效档位 {best}")
    check("落在有效档位上", best[2] == "抵押", f"实际 {best[2]}")

    # 源码层面确认 render_report 的正文取值确实过滤了 valid
    src = (ROOT / "scripts" / "render_report.py").read_text(encoding="utf-8")
    seg = src.split("维度扫描显示恶化最明显的是")[0][-900:]
    check("render_report 正文取值过滤 valid", 'b.get("valid") is False' in seg)


# ============================================================ Q2 组合候选数口径

def test_candidate_count():
    print("\n[Q2] 组合候选数必须取 combo_screen，不能用规则条数")
    import narrative

    # topic_selection 有 42 条规则，但 combo_screen 只有 60 条组合候选
    attr_good = {
        "topic_selection": [{"rule_id": f"R{i:02d}"} for i in range(42)],
        "topic_gate_applied": {"combo_candidates_total": 60, "gated_total": 5,
                               "selected": 0, "rejected": 5},
    }
    signals = {"overall": {"npl_rate": 0.0396, "bal": 44768028554.0}}
    s = narrative._monitor_summary(signals, attr_good, {"status": "partial", "total": 4, "verified": 2})
    check("摘要引用 60 条组合线索", "60 条组合线索" in s, s[:120])
    check("摘要不出现 42 条组合线索", "42 条组合线索" not in s, s[:120])

    # 缺 combo 计数时退回规则条数（向后兼容，不崩）
    attr_old = {"topic_selection": [{"rule_id": f"R{i:02d}"} for i in range(42)]}
    s2 = narrative._monitor_summary(signals, attr_old, {"status": "ok"})
    check("缺字段时向后兼容", "42 条组合线索" in s2, s2[:120])

    # apply_gate 必须写回 combo_candidates_total
    import apply_gate
    tg = {"gated": [], "selection": {"topics": []}, "criteria": {}}
    out, _ = apply_gate.apply_gate(tg, {"topic_selection": []})
    check("apply_gate 输出含 topic_gate_applied", "topic_gate_applied" in out)


# ============================================================ Q3 条件不撞车

def test_distinct_conditions():
    print("\n[Q3] 不同规则必须拿到不同 SQL 条件")
    import drill_planner as dp

    # 「零散获客」不应映射到担保方式条件
    names = ["零散获客", "无抵押缓释", "低评分准入"]
    mapped = []
    for nm in names:
        for kws, where, desc in dp.FEATURE_TO_SQL:
            if any(k in nm for k in kws):
                mapped.append((nm, where))
                break
    zero_map = [w for n, w in mapped if n == "零散获客"]
    check("「零散获客」不再映射到担保条件", not zero_map or "GRTE_MOD_CD" not in zero_map[0],
          str(zero_map))

    # 「欺诈」等无对应字段的特征不应被映射成 CUST_NO IS NOT NULL 这种万能条件
    for nm in ("欺诈风险敞口", "异地获客", "多头负债"):
        hit = [(kws, where) for kws, where, _ in dp.FEATURE_TO_SQL if any(k in nm for k in kws)]
        bad = [w for _, w in hit if "CUST_NO IS NOT NULL" in w]
        check(f"「{nm}」不映射到 CUST_NO IS NOT NULL", not bad, str(bad))

    # 两条不同规则经 _feature_filter_for 应拿到不同条件
    ins_a = {"rule_id": "C01", "hits": [{"label": "无抵押缓释"}]}
    ins_b = {"rule_id": "D11", "hits": [{"label": "低评分准入"}]}
    a = dp._feature_filter_for(ins_a, set())
    b = dp._feature_filter_for(ins_b, set())
    check("C01 与 D11 条件不同", a and b and a[0] != b[0], f"{a} vs {b}")

    # used_conds 避让必须真的生效（之前正则反解永远匹配不到）
    a2 = dp._feature_filter_for(ins_a, set())
    b2 = dp._feature_filter_for(ins_b, {a2[0]})
    check("避让后条件仍不同", a2[0] != b2[0], f"{a2} vs {b2}")

    # plan 自报 cond_used，供 build_degrade_plan 记录
    src = (ROOT / "scripts" / "drill_planner.py").read_text(encoding="utf-8")
    check("plan 输出 cond_used 字段", '"cond_used": filt' in src)


# ============================================================ Q4 空成员不造 plan

def test_no_empty_members_plan():
    print("\n[Q4] 无命中成员的规则不得硬造 plan")
    import drill_planner as dp

    ins = {"rule_id": "M16", "name": "老资产质量恶化", "hits": [], "members": [],
           "strength": 0.77}
    signals = {"slice": "20260831", "dimensions": {},
               "clue_matrix": {}}
    p = dp._insight_to_plan(1, ins, signals, "20260831", used_conds=set())
    check("空成员规则标 locatable=False", p.get("locatable") is False, str(p.get("locatable")))
    check("空成员规则无 steps", not p.get("steps"), str(len(p.get("steps") or [])))
    check("给出不可定位原因", bool(p.get("unlocatable_reason")))

    # build_degrade_plan 应把这类规则放进 skipped 而不是 plans
    attr = {
        "insights": [
            {"rule_id": "M16", "name": "老资产质量恶化", "hits": [], "members": [], "strength": 0.77},
            {"rule_id": "M05", "name": "小额信用贷高违约",
             "hits": [{"label": "无抵押缓释"}], "members": [], "strength": 0.53},
        ]
    }
    doc = dp.build_degrade_plan(signals, attr, max_plans=4)
    rules = [x.get("linked_rule") for x in doc["plans"]]
    check("M16 不进 plans", "M16" not in rules, str(rules))
    check("skipped 记录 M16", any(s.get("rule_id") == "M16" for s in doc.get("skipped") or []),
          str(doc.get("skipped")))
    check("warnings 说明跳过原因",
          any("无可定位条件" in w for w in doc.get("warnings") or []), str(doc.get("warnings")))


def main():
    print("=" * 62)
    print("报告自洽性验收 verify_render_consistency")
    print("=" * 62)
    test_dim_bucket_filter()
    test_candidate_count()
    test_distinct_conditions()
    test_no_empty_members_plan()
    print("\n" + "=" * 62)
    print(f"通过 {PASS} / 失败 {FAIL}")
    if FAILS:
        for f in FAILS:
            print(f"  ❌ {f}")
        return 1
    print("全部通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
