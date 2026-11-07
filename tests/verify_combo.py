#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_combo.py — combo_split 的可重复验证（不依赖真实数据）

跑法：
    python3 tests/verify_combo.py

会做三件事：
  1. 用合成 parquet fixture 实测 SQL，断言客户级口径自洽
     （hit_n + nonhit_n == universe_n，且不超过全辖）
  2. 断言 screen() 四个判定分支正确
  3. 断言「组合无增量」会被拦下 —— 这是防「各组合不良率都一样」的核心

退出码 0 = 全通过。
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import combo_split as cs          # noqa: E402
import drill_executor as dx       # noqa: E402

_fail = []
_pass = []


def ck(cond, msg):
    (_pass if cond else _fail).append(msg)
    print(("  ✓ " if cond else "  ✗ ") + msg)


def main():
    duckdb = dx._load_duckdb()
    if duckdb is None:
        print("需要 duckdb：pip install duckdb")
        return 2

    tmp = Path(tempfile.mkdtemp(prefix="vchfix_"))
    print(f"── 生成 fixture → {tmp}")
    rc = __import__("subprocess").call([sys.executable, str(ROOT / "tests" / "gen_vch_fixture.py"), str(tmp)])
    if rc != 0:
        print("fixture 生成失败")
        return 2

    con = duckdb.connect()

    def q(sql):
        cols, rows, _ = dx.run_sql(con, sql, str(tmp))
        return {r[0]: dict(zip(cols, r)) for r in rows}

    print("\n── 1. 客户级口径自洽（核心：hit+nonhit 必须等于全辖）")
    conds = [cs.translate(2)["cond"], cs.translate(7)["cond"]]
    g = q(cs.split_sql(conds, "20260831"))
    hit, non, uni = g["hit"], g["nonhit"], g["universe"]
    ck(hit["n"] + non["n"] == uni["n"],
       f"hit {hit['n']} + nonhit {non['n']} == universe {uni['n']}")
    ck(hit["n"] <= uni["n"], f"命中 {hit['n']} 未越界（全辖 {uni['n']}）")
    ck(0 < hit["npl_rate"] < 1, f"命中组不良率 {hit['npl_rate']:.4f} 在 (0,1)")
    ck(hit["npl_rate"] > uni["npl_rate"], f"组合不良率高于全辖（{hit['npl_rate']:.4f} > {uni['npl_rate']:.4f}）")

    print("\n── 2. 组合 lift 应高于每个单条件")
    singles = []
    for fid in (2, 7):
        t = cs.translate(fid)
        sg = q(cs.single_sql(t["cond"], "20260831"))
        single_lift = sg["hit"]["npl_rate"] / sg["universe"]["npl_rate"]
        singles.append({"feature_id": fid, "name": t["desc"], "cond": t["cond"],
                        "hit": sg["hit"], "universe": sg["universe"]})
        print(f"     {t['desc']} 单条件 lift={single_lift:.3f}")
    st, m = cs.screen(hit, non, uni, singles)
    ck(m.get("incremental_lift") is not None,
       f"组合对最强单条件增量 = {m.get('incremental_lift')}")

    print("\n── 3. screen 四分支")
    u = {"n": 51781, "npl_rate": 0.10}
    st_a, _ = cs.screen({"n": 8000, "npl_rate": 0.60}, {"n": 43781, "npl_rate": 0.0088}, u,
                        [{"feature_id": 2, "name": "无抵押",
                          "hit": {"n": 20000, "npl_rate": 0.20}, "universe": u}])
    ck(st_a == "phenomenon", "强组合 → phenomenon")
    st_b, mb = cs.screen({"n": 20000, "npl_rate": 0.30}, {"n": 31781, "npl_rate": 0.0428}, u,
                         [{"feature_id": 2, "name": "无抵押",
                           "hit": {"n": 20000, "npl_rate": 0.30}, "universe": u}])
    ck(st_b == "weak_phenomenon", "组合=最强单条件 → weak_phenomenon（叠加无增量）")
    ck("叠加没有带来增量" in (mb.get("reason") or ""), "拒绝理由写明「叠加无增量」")
    st_c, _ = cs.screen({"n": 40000, "npl_rate": 0.5}, {"n": 30000, "npl_rate": 0.1}, u, [])
    ck(st_c == "broken", "hit+nonhit>universe → broken（口径作废）")
    st_d, _ = cs.screen({"n": 50, "npl_rate": 0.9}, {"n": 51731, "npl_rate": 0.1}, u, [])
    ck(st_d == "insufficient", "样本不足 → insufficient")

    print("\n── 4. 不可映射特征必须显式拒绝，不得硬凑")
    ck(cs.translate(32) is None, "多头借贷（征信口径）→ 不可映射")
    ck("征信" in cs.unavailable_reason(32), "拒绝理由说明原因（征信 P 表）")
    ck(cs.translate(2) is not None, "无抵押缓释 → 可映射")

    print("\n── 5. 第二道校验：现象 ↔ 归因 相关性（topic_gate）")
    import topic_gate as tg
    r1 = tg.attribution_gate([{"hit": {"n": 5000, "npl_rate": 0.45},
                               "nonhit": {"n": 45000, "npl_rate": 0.03}, "lift": 15.0}])
    ck(r1["status"] == "supported", "强归因（lift 15、对照 3%）→ supported")
    r2 = tg.attribution_gate([{"hit": {"n": 3000, "npl_rate": 0.12},
                               "nonhit": {"n": 47000, "npl_rate": 0.11}, "lift": 1.09}])
    ck(r2["status"] == "rejected", "对照组同样偏高（全辖共性）→ rejected")
    ck("区分度不足" in (r2.get("reason") or ""), "拒绝理由写明「区分度不足」")
    r3 = tg.attribution_gate([])
    ck(r3["status"] == "insufficient", "无钻取数据 → insufficient（不硬判）")
    r4 = tg.attribution_gate([{"hit": {"n": 20, "npl_rate": 0.9},
                               "nonhit": {"n": 45000, "npl_rate": 0.03}, "lift": 30}])
    ck(r4["status"] == "insufficient", "样本不足 → insufficient")

    print("\n── 6. 主题名额：上限 10 但**不设下限**")
    six = [{"both_passed": True, "strength": 0.9 - i * 0.05, "rule_id": f"R{i}"} for i in range(6)]
    s6 = tg.select_topics(six, 10)
    ck(s6["count"] == 6, f"只有 6 个通过 → 如实报 6 个（不是凑到 10）")
    ck(s6["shortage"] == 4, "shortage 正确记为 4")
    ck("未放宽条件凑数" in s6["shortage_note"], "缺口原因写明「未放宽条件凑数」")
    many = six + [{"both_passed": True, "strength": 0.1 + i * 0.001, "rule_id": f"X{i}"} for i in range(8)]
    s14 = tg.select_topics(many, 10)
    ck(s14["count"] == 10 and s14["dropped_by_cap"] == 4, "14 个通过 → 取前 10，另 4 个标记为名额溢出")

    print("\n── 7. 端到端：现象成立但归因弱 → 弃题")
    combo_doc = {"phenomena": [{"status": "phenomenon", "linked_rules": ["C01", "C02"],
                                "metrics": {"hit_n": 5000, "universe_n": 50000,
                                            "hit_rate": 0.45, "universe_rate": 0.08,
                                            "lift_vs_universe": 5.6, "incremental_lift": 2.1}}]}
    ev_doc = {"evidence_chain": [
        {"linked_rule": "C01", "status": "verified", "comparisons": [
            {"hit": {"n": 5000, "npl_rate": 0.45},
             "nonhit": {"n": 45000, "npl_rate": 0.03}, "lift": 15.0}]},
        {"linked_rule": "C02", "status": "verified", "comparisons": [
            {"hit": {"n": 3000, "npl_rate": 0.12},
             "nonhit": {"n": 47000, "npl_rate": 0.11}, "lift": 1.09}]},
    ]}
    at_doc = [{"rule_id": "C01", "name": "获客激进", "strength": 0.9, "level": "显著"},
              {"rule_id": "C02", "name": "准入失守", "strength": 0.8, "level": "显著"}]
    res = tg.run(combo_doc, ev_doc, at_doc, max_topics=10)
    ck(res["selection"]["count"] == 1, "两个现象成立，但只有归因也成立的 1 个入选")
    ck(res["selection"]["topics"][0]["rule_id"] == "C01", "入选的是归因得到支持的那一个")
    ck("归因rejected" in res["reject_reasons"], "被弃的题记为「归因rejected」")

    print("\n" + "=" * 60)
    print(f"结果：{len(_pass)} 通过 / {len(_fail)} 失败")
    if _fail:
        for f in _fail:
            print(f"  失败：{f}")
        return 1
    print("全部通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
