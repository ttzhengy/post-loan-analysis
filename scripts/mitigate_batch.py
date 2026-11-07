#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mitigate_batch.py — 对 topic_gate 选中的主题逐个做缓释分层

为什么需要这一层
----------------
mitigate.py 处理**一个**客群，但报告里通常有多个已确认主题。
如果只挑一个做缓释，等于只给了部分答案。本模块读 topic_gate.json 的
入选主题清单，按 rule_id 回到 combo_screen.json 取该主题对应的
组合条件（也就是它 hit 的那批客户），逐个跑缓释分层。

客群条件从哪来
--------------
topic_gate 只记录 rule_id 与校验结论，不含 SQL。组合条件在
combo_screen.json 的 phenomena[] 里（每个现象带 linked_rules），
因此按 linked_rules 反查即可。查不到的如实跳过并记录，不猜测。
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
import mitigate as mg      # noqa: E402

SCHEMA_VERSION = "1.0"


def resolve_cohorts(topic_gate, combo_screen):
    """入选主题 → 客群条件。返回 (cohorts, skipped)。"""
    topics = ((topic_gate.get("selection") or {}).get("topics")) or []
    phenomena = combo_screen.get("phenomena") or []
    by_rule = {}
    for p in phenomena:
        for rid in (p.get("linked_rules") or []):
            by_rule.setdefault(rid, p)

    cohorts, skipped = [], []
    for t in topics:
        rid = t.get("rule_id")
        p = by_rule.get(rid)
        if not p:
            skipped.append({"rule_id": rid, "name": t.get("name"),
                            "reason": "combo_screen 里没有该规则对应的组合条件"})
            continue
        conds = p.get("conds") or []
        if len(conds) < 1:
            skipped.append({"rule_id": rid, "name": t.get("name"),
                            "reason": "组合条件为空"})
            continue
        label = t.get("name") or "+".join(
            f.get("desc") or f.get("name") or str(f.get("feature_id"))
            for f in (p.get("features") or []))
        cohorts.append({
            "rule_id": rid, "label": label, "conds": conds,
            "features": p.get("features"), "strength": t.get("strength"),
            "hit_n": ((p.get("metrics") or {}).get("hit_n")),
            "hit_rate": ((p.get("metrics") or {}).get("hit_rate")),
        })
    return cohorts, skipped


def run_one(con, dx, cohort, args, cfg):
    """对单个客群跑缓释分层，返回 summary 结构。"""
    def _q(sql):
        cols, rws, _ = dx.run_sql(con, sql, args.data_dir)
        return {r[0]: dict(zip(cols, r)) for r in rws}

    base_g = _q(mg.group_sql(cohort["conds"], args.slice, args.level, args.base_slice))
    cohort_hit = base_g.get("hit") or {}
    cohort_rate = mg.to_num(cohort_hit.get("npl_rate"))
    if not (mg.to_num(cohort_hit.get("n")) or 0):
        return {"label": cohort["label"], "error": "客群基准取数失败"}

    m3 = mg._m3(args.slice)
    tiers, warnings = [], []

    # 先筛掉与客群条件结构冲突的缓释维度：拿「担保方式」去切一个
    # 「本来就全是纯信用」的客群，切出来必然是单档空集，照常输出会让
    # 读者误判成数据缺失。冲突的分档记进 skipped 并说明原因。
    usable, conflict_skip = mg.usable_mitigators(cohort["conds"], args.mitigators)
    for s in conflict_skip:
        warnings.append(f"{s['mitigator_label']}·{s['bucket']} 已跳过：{s['reason']}")

    for spec in usable:
        for label, cond in spec["buckets"]:
            g = _q(mg.bucket_sql(cohort["conds"], cond, args.slice,
                                 args.level, args.base_slice, m3))
            hit = g.get("hit") or {}
            n = mg.to_num(hit.get("n")) or 0
            rate = mg.to_num(hit.get("npl_rate"))
            if n < cfg["min_bucket_n"]:
                warnings.append(f"{spec['label']}·{label} 样本 {n:.0f} 户不足门槛")
                continue
            tier, multiple = mg.classify(rate, cohort_rate, cfg)
            tiers.append({
                "mitigator": spec["key"], "mitigator_label": spec["label"],
                "label": label, "cond": cond, "note": spec["note"],
                "n": int(n), "rate": round(rate, 6) if rate is not None else None,
                "tot_bal": round(mg.to_num(hit.get("tot_bal")) or 0, 2),
                "npl_bal": round(mg.to_num(hit.get("npl_bal")) or 0, 2),
                "multiple": round(multiple, 3) if multiple else None,
                "tier": tier,
            })

    summary = mg.summarize(tiers, cfg)
    summary["warnings"] = summary.get("warnings", []) + warnings
    summary["conflict_skipped"] = conflict_skip
    summary["usable_mitigators"] = [u["key"] for u in usable]
    return {
        "rule_id": cohort["rule_id"], "label": cohort["label"],
        "conds": cohort["conds"],
        "cohort_n": int(mg.to_num(cohort_hit.get("n")) or 0),
        "cohort_rate": round(cohort_rate, 6) if cohort_rate is not None else None,
        "cohort_bal": round(mg.to_num(cohort_hit.get("tot_bal")) or 0, 2),
        "summary": summary,
        "narrative": mg.build_report_block(summary, cohort["label"]),
    }


def main():
    ap = argparse.ArgumentParser(description="对入选主题批量做缓释分层")
    ap.add_argument("--topic-gate", required=True)
    ap.add_argument("--combo-screen", required=True)
    ap.add_argument("--slice", default="20260831")
    ap.add_argument("--level", default="chg", choices=list(cs.LEVELS))
    ap.add_argument("--base-slice", default=None)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--mitigators", nargs="*", default=list(mg.MITIGATORS))
    ap.add_argument("--tolerance", type=float, default=mg.DEFAULT_CFG["tolerance"])
    ap.add_argument("--pause", type=float, default=mg.DEFAULT_CFG["pause"])
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cfg = {"tolerance": args.tolerance, "pause": args.pause,
           "min_bucket_n": mg.DEFAULT_CFG["min_bucket_n"]}

    tg = json.load(open(args.topic_gate, encoding="utf-8"))
    cs_doc = json.load(open(args.combo_screen, encoding="utf-8"))
    cohorts, skipped = resolve_cohorts(tg, cs_doc)

    result = {
        "schema_version": SCHEMA_VERSION, "kind": "mitigation_batch",
        "slice": args.slice, "level": args.level, "base_slice": args.base_slice,
        "criteria": cfg, "mitigators": list(args.mitigators),
        "cohorts_total": len(cohorts), "cohorts": [],
        "skipped": skipped, "warnings": [],
    }

    if not cohorts:
        result["warnings"].append(
            "没有可做缓释的客群（入选主题均无对应组合条件），"
            "本报告只给出风险方向，不给出可贷条件建议")
        json.dump(result, open(args.out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print(f"⚠️ 无可缓释客群 → {args.out}")
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
        result["warnings"].append("chg 口径需 base_slice，未提供则回退 vch")
        args.level = "vch"

    for c in cohorts:
        try:
            result["cohorts"].append(run_one(con, dx, c, args, cfg))
        except Exception as exc:   # noqa: BLE001
            result["warnings"].append(f"客群「{c['label']}」处理失败：{exc}")

    json.dump(result, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    done = [c for c in result["cohorts"] if not c.get("error")]
    tiers_n = sum(len((c.get("summary") or {}).get("tiers") or []) for c in done)
    print(f"✅ 缓释批量完成：{len(done)}/{len(cohorts)} 个客群，共 {tiers_n} 个分层"
          f"（跳过 {len(skipped)}）→ {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
