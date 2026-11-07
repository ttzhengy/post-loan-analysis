#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_v2.py — 三项吸收改造的验收入口

覆盖：
  A. chg 不良生成率口径（combo_split）
      A1 生成率口径下 hit+nonhit == universe 仍成立（客户级归属不受口径影响）
      A2 universe 生成率 == 被标记 downgrade 的凭证余额 ÷ 期初敞口（手工核算）
      A3 chg 与 vch 给出不同数字（证明口径真的换了，不是换标签）
      A4 chg 口径下不良余额 ≤ 分析时点全辖不良余额（分子被限定为新增）
  B. 缓释分层（mitigate）
      B1 各分层维度户数之和 == 客群户数
      B2 保护性履约因子 ∈ [0,1] 且与分层敞口一致
      B3 误伤规模 == pause 档正常余额之和，且 ≤ pause 档总敞口
      B6 classify 三档边界正确
  C. 内外部拆分（internal_external）
      C1 外部超额不因标记组表现优于基准而为负（按 0 计）
      C2 三分账加总 == 全辖新增不良（容差内）
      C3 未识别 > 0 时明确不等于管理失职
      C4 外部贡献不超过全辖新增不良

用法：python3 tests/verify_v2.py [--data-dir /tmp/vchfix2] [--keep]
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import combo_split as cs        # noqa: E402
import internal_external as ie  # noqa: E402
import mitigate as mg           # noqa: E402


class Checker:
    def __init__(self):
        self.pass_n = 0
        self.fail = []

    def ok(self, cond, label, detail=""):
        if cond:
            self.pass_n += 1
            print(f"  ✅ {label}")
        else:
            self.fail.append(f"{label} {detail}")
            print(f"  ❌ {label} {detail}")

    def summary(self):
        total = self.pass_n + len(self.fail)
        print(f"\n{'='*60}\n通过 {self.pass_n}/{total}")
        for f in self.fail:
            print(f"  ✗ {f}")
        return 0 if not self.fail else 1


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def run_offline(c: Checker):
    """不依赖 duckdb 的纯逻辑断言。"""
    print("\n[B] 缓释分层（纯逻辑）")
    # B6 classify 边界
    cfg = {"tolerance": 1.0, "pause": 3.0}
    c.ok(mg.classify(0.05, 0.10, cfg)[0] == "normal", "生成率为基线 0.5 倍 → 照常放贷")
    c.ok(mg.classify(0.10, 0.10, cfg)[0] == "normal", "等于基线 → 照常放贷（闭区间）")
    c.ok(mg.classify(0.20, 0.10, cfg)[0] == "cond", "基线 2 倍 → 附条件放贷")
    c.ok(mg.classify(0.30, 0.10, cfg)[0] == "pause", "基线 3 倍 → 暂停新增（闭区间）")
    c.ok(mg.classify(0.31, 0.10, cfg)[0] == "pause", "基线 3.1 倍 → 暂停新增")
    c.ok(mg.classify(None, 0.10, cfg)[0] == "unknown", "生成率缺失 → 不出结论")
    c.ok(mg.classify(0.10, 0, cfg)[0] == "unknown", "基线为 0 → 不出结论（不做除零猜测）")

    # B2/B3 summarize
    tiers = [
        {"label": "A", "tier": "pause",  "n": 100, "tot_bal": 1000.0, "npl_bal": 300.0, "rate": 0.30},
        {"label": "B", "tier": "cond",   "n": 200, "tot_bal": 2000.0, "npl_bal": 400.0, "rate": 0.20},
        {"label": "C", "tier": "normal", "n": 700, "tot_bal": 7000.0, "npl_bal": 350.0, "rate": 0.05},
    ]
    s = mg.summarize(tiers, cfg)
    c.ok(abs(s["protect_factor"] - 0.70) < 1e-6,
         "保护性履约因子 = 照常档敞口占比（7000/10000=0.70）", f"实得 {s['protect_factor']}")
    c.ok(abs(s["mis_hit"] - 700.0) < 1e-6,
         "误伤规模 = 暂停档正常余额（1000-300=700）", f"实得 {s['mis_hit']}")
    c.ok(s["mis_hit"] <= 1000.0, "误伤规模不超过暂停档总敞口")
    c.ok(0.0 <= s["protect_factor"] <= 1.0, "保护因子落在 [0,1]")

    # 空分层
    s0 = mg.summarize([], cfg)
    c.ok(s0["protect_factor"] is None and s0["warnings"],
         "无分层通过门槛时不给因子，且给出提示")

    # B5 缓释维度与客群条件冲突时必须整维不出
    credit_cohort = [cs.GRTE_CREDIT_ONLY, cs.FEATURE_COND[13]["cond"]]
    usable, skipped = mg.usable_mitigators(credit_cohort)
    keys = {u["key"] for u in usable}
    c.ok("guarantee" not in keys,
         "[B5] 纯信用客群不再用担保方式分层（必然单档空集）",
         f"usable={sorted(keys)}")
    c.ok(any(s["mitigator"] == "guarantee" for s in skipped),
         "[B5] 担保维度跳过时记录原因")
    c.ok(len(keys) >= 2,
         "[B5] 仍有其他维度可用（不能因为一个维度冲突就整块放弃）",
         f"usable={sorted(keys)}")
    # 担保方式用在非限定客群上应该正常可用
    usable2, _ = mg.usable_mitigators(["EXD_DAYS >= 1"])
    c.ok("guarantee" in {u["key"] for u in usable2},
         "[B5] 客群未限定担保方式时，担保维度正常可用")
    # 金额冲突
    conflict, why = mg.bucket_conflicts(
        ["CAST(FORM_BAL_RMB AS DOUBLE) >= 500000"], "CAST(FORM_BAL_RMB AS DOUBLE) < 100000")
    c.ok(conflict, "[B5] 客群≥50万 vs 分档<10万 判为冲突", why)

    # ---- 编码与类型防回归 ----
    print("\n[D] 编码与类型防回归")
    # D1 担保编码必须是真实存在的 0101，不能是 0100
    c.ok(cs.GRTE_CODE_CREDIT == "0101",
         "[D1] 信用担保编码为 0101（真实数据无 0100）", cs.GRTE_CODE_CREDIT)
    all_conds = " ".join(v["cond"] for v in cs.FEATURE_COND.values())
    c.ok("'0100'" not in all_conds,
         "[D1] FEATURE_COND 中不含不存在的 0100 编码")
    # D2 纯信用条件必须用 0101
    c.ok("0101" in cs.FEATURE_COND[2]["cond"],
         "[D2] 特征 2 纯信用使用 0101", cs.FEATURE_COND[2]["cond"])
    # D3 非信用条件不能与纯信用重叠
    c.ok(cs.conds_conflict([cs.FEATURE_COND[2]["cond"], cs.FEATURE_COND[6]["cond"]])[0],
         "[D3] 纯信用与非信用互斥（编码正确时仍然成立）")
    # D4 数值字段必须 CAST 后才能比较
    for fid in (43, 44):
        cond = cs.FEATURE_COND[fid]["cond"]
        c.ok("CAST" in cond.upper(),
             f"[D4] 特征 {fid} 的 EXD_DAYS 比较前已 CAST", cond)
    c.ok("EXD_DAYS >= 1" not in all_conds and "EXD_DAYS BETWEEN" not in all_conds,
         "[D4] 不存在裸 EXD_DAYS 比较")
    # D5 余额比较也要 CAST（FORM_BAL_RMB 是 DECIMAL，但为对齐口径统一 TRY_CAST）
    c.ok("CAST" in cs.FEATURE_COND[7]["cond"].upper(),
         "[D5] 特征 7 的余额比较已 CAST", cs.FEATURE_COND[7]["cond"])
    # D6 mitigate 的逾期维度必须 CAST（EXD_DAYS 是 VARCHAR），
    # 且必须走客户级 agg 定档 —— 否则多笔客户会同时落进两档。
    ov_agg = mg.MITIGATORS["overdue"].get("agg") or ""
    ov = " ".join(c for _, c in mg.MITIGATORS["overdue"]["buckets"])
    c.ok("CAST" in ov_agg.upper(), "[D6] 缓释逾期分层已 CAST",
         f"agg={ov_agg}")
    c.ok("{agg}" in ov, "[D6] 缓释逾期分层走客户级 agg 定档（两档互斥）", ov)

    # B7 冲突过滤后仍能产出有效分层（本次真实场景）
    tiers_ok = [
        {"label": "至今无逾期", "tier": "normal", "n": 400, "tot_bal": 4000.0, "npl_bal": 100.0},
        {"label": "已现逾期",   "tier": "pause",  "n": 100, "tot_bal": 1000.0, "npl_bal": 600.0},
    ]
    s_ok = mg.summarize(tiers_ok, cfg)
    c.ok(s_ok["protect_factor"] == 0.8, "[B7] 逾期维度分层给出合理保护因子",
         f"实得 {s_ok['protect_factor']}")

    print("\n[C] 内外部拆分（纯逻辑）")
    # C1 标记组表现优于基准 → 超额为负 → 按 0 计
    rows = [{"marker": "m", "label": "测试标记",
             "hit": {"n": 100, "tot_bal": 1000.0, "npl_bal": 10.0, "npl_rate": 0.01}}]
    uni = {"n": 10000, "tot_bal": 100000.0, "npl_bal": 5000.0, "npl_rate": 0.05}
    r = ie.compute(rows, uni)
    c.ok(r["external"] == 0.0, "标记组优于基准时外部贡献为 0（不用负数冲抵）", f"实得 {r['external']}")
    c.ok(r["details"][0]["excess"] < 0, "超额原值保留为负，便于追溯")
    c.ok(r["details"][0]["clamped"] is True, "标记了 clamped 说明已归零")

    # C2 三分加总
    c.ok(r["check"]["passed"], "三分账加总 == 全辖新增不良", f"gap={r['check']['gap']}")
    c.ok(abs(r["external"] + r["internal"] + r["unidentified"] - 5000.0) < 1.0,
         "external+internal+unidentified 精确等于全辖 5000")

    # C4 外部不超过全辖
    rows2 = [{"marker": "m", "label": "极端标记",
              "hit": {"n": 100, "tot_bal": 100000.0, "npl_bal": 9000.0}}]
    r2 = ie.compute(rows2, uni)
    c.ok(r2["external"] <= 5000.0, "外部贡献不超过全辖新增不良（封顶）", f"实得 {r2['external']}")

    # C3 未识别措辞
    txt = ie.build_narrative(r)
    c.ok("不等于管理失职" in txt or r["unidentified"] == 0,
         "未识别部分明确说明不等于管理失职")
    c.ok("亿" in txt or "万" in txt or "未形成" in txt,
         "金额以中文业务单位呈现", txt[:60])

    # 无客群时全部计入未识别
    r3 = ie.attribute_cohorts(dict(r), [], uni)
    c.ok(r3["internal"] == 0.0 and r3["unidentified"] > 0,
         "无已确认客群时内部贡献全部计入未识别")

    # 有客群时按敞口占比分摊
    cohorts = [{"label": "客群甲", "n": 500, "tot_bal": 50000.0, "npl_bal": 3000.0}]
    r4 = ie.attribute_cohorts(dict(r), cohorts, uni)
    c.ok(r4["cohort_share"] and len(r4["cohort_share"]) == 1, "客群贡献落到具体客群")
    c.ok(r4["check"]["passed"], "带客群拆分后加总仍自洽", f"gap={r4['check']['gap']}")


def run_online(c: Checker, data_dir: str, keep: bool):
    """依赖 duckdb + fixture 的断言。"""
    import drill_executor as dx
    duckdb = dx._load_duckdb()
    if duckdb is None:
        print("\n⚠️  duckdb 未安装，跳过在线断言")
        return False
    con = duckdb.connect()

    def q(sql):
        cols, rws, _ = dx.run_sql(con, sql, data_dir)
        return {r[0]: dict(zip(cols, r)) for r in rws}

    base, cur = "20260331", "20260831"
    conds = [cs.FEATURE_COND[2]["cond"], cs.FEATURE_COND[13]["cond"]]

    # B8/A5 组合候选不能包含逻辑互斥的条件对
    conflict, why = cs.conds_conflict([cs.FEATURE_COND[2]["cond"], cs.FEATURE_COND[6]["cond"]])
    c.ok(conflict, "[A5] 纯信用 与 非信用 判为互斥", why)
    conflict2, why2 = cs.conds_conflict([cs.FEATURE_COND[2]["cond"], cs.FEATURE_COND[13]["cond"]])
    c.ok(not conflict2, "[A5] 纯信用 与 大额纯信用（包含关系）不判互斥", why2)
    # 13 是 2 的子集，AND 起来仍非空 —— 但字符串不同，属"包含"而非"互斥"
    # 这里断言的是 conds_conflict 不该把它误判成空集
    conflict3, _ = cs.conds_conflict([cs.FEATURE_COND[2]["cond"], cs.FEATURE_COND[44]["cond"]])
    c.ok(not conflict3, "[A5] 纯信用 与 曾逾期 不冲突（不同字段）")

    print("\n[A] chg 不良生成率口径（数据 /tmp/vchfix2）")
    gv = q(cs.split_sql(conds, cur, level="vch"))
    gc = q(cs.split_sql(conds, cur, level="chg", base_slice=base))

    # A1 客户级归属在两种口径下都自洽
    for tag, g in (("vch", gv), ("chg", gc)):
        h = _num((g.get("hit") or {}).get("n")) or 0
        n = _num((g.get("nonhit") or {}).get("n")) or 0
        u = _num((g.get("universe") or {}).get("n")) or 0
        c.ok(abs(h + n - u) <= max(1, u * 0.005),
             f"[A1] {tag} 口径 hit+nonhit==universe", f"{h:.0f}+{n:.0f}vs{u:.0f}")

    # A3 两口径数字必须不同
    rv = _num((gv.get("universe") or {}).get("npl_rate"))
    rc = _num((gc.get("universe") or {}).get("npl_rate"))
    c.ok(rv is not None and rc is not None and abs(rv - rc) > 1e-6,
         "[A3] chg 与 vch 给出不同比率（口径真的换了）", f"vch={rv} chg={rc}")

    # A2 手工核算 universe 生成率
    manual = con.execute(f"""
      WITH b AS (
        SELECT FORM_NO, CAST(FORM_BAL_RMB AS DOUBLE) AS bal0,
               CASE WHEN substr(RSK_CLS_CD,1,1) IN ('3','4','5') THEN 1 ELSE 0 END AS npl0
        FROM read_parquet('{data_dir.rstrip("/")}/{cs.TABLE}/*.parquet')
        WHERE DATA_DAT='{base}' AND BUS_BREED_CD LIKE 'A70%'
      ), c AS (
        SELECT FORM_NO, CAST(FORM_BAL_RMB AS DOUBLE) AS bal1,
               CASE WHEN substr(RSK_CLS_CD,1,1) IN ('3','4','5') THEN 1 ELSE 0 END AS npl1
        FROM read_parquet('{data_dir.rstrip("/")}/{cs.TABLE}/*.parquet')
        WHERE DATA_DAT='{cur}' AND BUS_BREED_CD LIKE 'A70%'
      )
      SELECT SUM(CASE WHEN b.npl0=0 AND COALESCE(c.npl1,0)=1
                      THEN COALESCE(c.bal1,b.bal0) ELSE 0 END) AS npl,
             SUM(b.bal0) AS tot
      FROM b LEFT JOIN c ON c.FORM_NO=b.FORM_NO
    """).fetchone()
    m_rate = (manual[0] / manual[1]) if manual[1] else None
    c.ok(m_rate is not None and rc is not None and abs(m_rate - rc) < max(1e-6, (rc or 0) * 0.02),
         "[A2] universe 生成率与独立核算一致（2% 内）", f"手算={m_rate} 模块={rc}")

    # A4 chg 分子 ≤ vch 分子（新增不良必然 ≤ 现存不良）
    chg_npl = _num((gc.get("universe") or {}).get("npl_bal")) or 0
    vch_npl = _num((gv.get("universe") or {}).get("npl_bal")) or 0
    c.ok(chg_npl <= vch_npl * 1.001,
         "[A4] 新增不良余额 ≤ 存量不良余额", f"chg={chg_npl:.0f} vch={vch_npl:.0f}")

    print("\n[B] 缓释分层（在线）")
    gbase = q(mg.group_sql(conds, cur, level="chg", base_slice=base))
    cohort_n = _num((gbase.get("hit") or {}).get("n")) or 0
    c.ok(cohort_n > 0, "客群基线取到样本", f"n={cohort_n}")

    tiers = []
    # 用「逾期状态」维度：担保方式对这个纯信用客群恒为单档，会被冲突过滤掉
    usable, conf_skip = mg.usable_mitigators(conds)
    c.ok(bool(conf_skip), "[B5] 在线：担保维度因客群限定纯信用被跳过",
         f"skipped={[s['bucket'] for s in conf_skip]}")
    pick = next((u for u in usable if u["key"] == "overdue"), usable[0] if usable else None)
    c.ok(pick is not None, "[B5] 在线：仍有可用缓释维度")
    _pick_agg = (pick or {}).get("agg")
    for label, cond in ((pick or {}).get("buckets") or []):
        g = q(mg.bucket_sql(conds, cond, cur, "chg", base, agg=_pick_agg))
        hit = g.get("hit") or {}
        n = _num(hit.get("n")) or 0
        if not n:
            continue
        tiers.append({"label": label, "n": n,
                      "tot_bal": _num(hit.get("tot_bal")) or 0,
                      "npl_bal": _num(hit.get("npl_bal")) or 0,
                      "rate": _num(hit.get("npl_rate"))})
    # B1 分层户数加总
    s_sum = sum(t["n"] for t in tiers)
    c.ok(abs(s_sum - cohort_n) <= max(1, cohort_n * 0.01),
         "[B1] 逾期维度各档户数和 == 客群户数", f"{s_sum:.0f} vs {cohort_n:.0f}")
    # B4 分层生成率必须能区分（不是同一个数字）
    if len(tiers) >= 2:
        rates = {round(t["rate"] or 0, 6) for t in tiers}
        c.ok(len(rates) == len(tiers),
             "[B4] 各档生成率彼此不同（分层真的在区分）", f"rates={rates}")

    print("\n[C] 内外部拆分（在线）")
    uni_rows = q(cs.split_sql(["1=1", "1=1"], cur, level="chg", base_slice=base))
    uni = uni_rows.get("universe") or {}
    rows = []
    for key, spec in ie.EXTERNAL_MARKERS.items():
        g = q(ie.split_sql(spec["cond"], cur, "chg", base))
        hit = g.get("hit") or {}
        if (_num(hit.get("tot_bal")) or 0) > 0:
            rows.append({"marker": key, "label": spec["label"], "hit": hit})
    res = ie.compute(rows, uni)
    c.ok(res["check"]["passed"],
         "[C2] 三分账加总自洽", f"gap={res['check']['gap']}")
    c.ok(res["external"] <= (_num(uni.get("npl_bal")) or 0) * 1.001,
         "[C4] 外部贡献不超过全辖新增不良")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/tmp/vchfix2")
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    c = Checker()
    run_offline(c)

    dd = Path(args.data_dir)
    online = False
    if dd.exists():
        online = run_online(c, str(dd), args.keep)
    else:
        print(f"\n⚠️  未找到 fixture 目录 {dd}，跳过在线断言")
        print("   生成：python3 tests/gen_vch_fixture.py " + str(dd))

    rc = c.summary()
    if not online and rc == 0:
        print("\n注意：只跑了离线断言，在线部分未验证。")
    return rc


if __name__ == "__main__":
    sys.exit(main())
