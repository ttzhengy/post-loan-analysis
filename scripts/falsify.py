#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""falsify.py — 归因假设的可证伪检验

为什么需要这一步
----------------
现在归因是「给现象挂规则」：组合命中客群不良率是全辖 N 倍 → 挂上
「准入风控失守」这条规则。规则和现象之间只有**相关性**（特征集合的
Jaccard 匹配），没有任何排除其他解释的动作。

因此结论停在「哪类客户坏得多」，到不了「为什么坏」，也无法回应
「你怎么知道不是别的原因」这个必然会被问到的问题。

可证伪的做法
------------
一个归因假设如果为真，除了「命中组不良率高」之外，还应该观察到一些
**额外的、独立的经验特征**。如果这些特征不出现，假设就被削弱或推翻。

本模块对每个假设做四类检验，每类都能给出一个明确的支持/反驳/中性结论：

1. 时间集中性检验（temporal_cluster）
   假设指向「某一时点后的准入/管理变化」→ 该客群的**新增不良应集中在
   那个时点之后**，且与对照组相比更集中。
   若新增不良在时间上均匀分布 → 这不是一次「管理变化」造成的，而是
   一直存在的结构性特征（如客群天然资质差），假设应下调为「结构性问题」。

2. 剂量反应检验（dose_response）
   假设指向「某风险因素越强问题越严重」（如额度越大、接续次数越多）
   → 该因素分档后，新增不良率应**单调上升**。
   若非单调或反向 → 该因素不是驱动因素，假设应推翻。

3. 行为分化检验（behavior_split）
   区分「准入问题」与「贷后问题」：
     · 准入问题 → 不良客户在**放款当时**的资质已劣于正常客户，
       表现为该客群内部**不同放款批次**的生成率无显著差异
       （因为放款时就已经决定了）
     · 贷后问题 → 生成率随**放款后经过时间**显著变化
   这是能区分「谁放进来的」和「谁没管住」的唯一可操作判据。

4. 对照组特征检验（control_profile）
   假设指向「客群本身的资质问题」→ 该客群在**非不良**部分上也应
   表现出与对照组一致的差异（即差异来自客群结构，不来自风险事件）。
   若该客群的正常客户与对照组正常客户无差异 → 说明差异确实来自
   风险事件本身，指向管理问题而非客群结构。

结论分级
--------
每项检验返回 support / refute / neutral / unavailable，四项汇总后给出
假设的总体证伪状态：
  survived    所有可执行检验均未反驳，且至少一项支持
  weakened    有反驳项但不足以推翻（如时间检验反驳但剂量反应支持）
  refuted     关键检验明确反驳
  untested    无可用检验项（缺数据），**不允许默认成立**

红线
----
本模块只做「用数据反驳假设」，**不做「用数据确认假设」**。
检验通过只说明「没有被这些检验推翻」，不等于证明。报告措辞必须
是「未发现反驳证据」，不能写成「已证明」。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Windows 控制台默认 GBK，直接 print 中文会抛 UnicodeEncodeError。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

import combo_split as cs   # noqa: E402

SCHEMA_VERSION = "1.0"

# 检验项的默认阈值。改这里会同时影响所有假设，不做 per-hypothesis 调参
# （per-hypothesis 阈值等于给每个假设量身定做标准，失去可比性）。
DEFAULT_CFG = {
    "min_bucket_n": 50,        # 单个分档最少客户数
    "temporal_share": 0.60,    # 时间集中性：某时段占比超过 60% 视为集中
    "dose_monotonic_min": 0.6,  # 剂量反应：相邻档递增的比例超过 60% 视为单调
    "dose_amplitude": 1.5,     # 剂量反应：最高档至少是最低档的多少倍才算有实质关系
    "behavior_ratio": 1.5,     # 行为分化：批次间生成率最大值/最小值超过 1.5 视为有分化
    "z_alpha": 0.05,           # 显著性水平
}


def to_num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _z_test(p1, n1, p2, n2):
    """两比例差异 z 检验，返回 (z, p_value)。"""
    if not all([n1, n2]) or n1 <= 0 or n2 <= 0:
        return None, None
    p = (p1 * n1 + p2 * n2) / (n1 + n2)
    se = (p * (1 - p) * (1 / n1 + 1 / n2)) ** 0.5
    if se == 0:
        return None, None
    z = (p1 - p2) / se
    # 正态近似双侧 p 值，避免引入 scipy
    import math
    pv = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return z, pv


# ============================================================ 检验 1：时间集中性

def sql_temporal(cohort_conds, slice_v, base_slice, table=cs.TABLE):
    """按放款年份分组的客群/全辖 新增不良生成率。

    如果假设指向「某时点后的管理变化」，该客群的新增不良应集中在
    那个时点之后的放款批次上。若各年份生成率均匀 → 不是一次性变化，
    而是长期存在的结构性问题。
    """
    cond = " AND ".join("(" + c + ")" for c in cohort_conds)
    b = f"{base_slice}"
    c = f"{slice_v}"
    return f"""
WITH bb AS (
  SELECT CUST_NO, FORM_NO, substr(LN_DAT,1,4) AS yr,
         CAST(FORM_BAL_RMB AS DOUBLE) AS bal0,
         CASE WHEN substr(RSK_CLS_CD,1,1) IN ('3','4','5') THEN 1 ELSE 0 END AS npl0,
         CASE WHEN {cond.strip()} THEN 1 ELSE 0 END AS in_cohort
  FROM {table}
  WHERE DATA_DAT='{b}' AND BUS_BREED_CD LIKE 'A70%'
),
cc AS (
  SELECT FORM_NO,
         CASE WHEN substr(RSK_CLS_CD,1,1) IN ('3','4','5') THEN 1 ELSE 0 END AS npl1,
         CAST(FORM_BAL_RMB AS DOUBLE) AS bal1
  FROM {table}
  WHERE DATA_DAT='{c}' AND BUS_BREED_CD LIKE 'A70%'
),
chg AS (
  SELECT bb.CUST_NO, bb.yr, bb.in_cohort, bb.bal0,
         CASE WHEN bb.npl0=0 AND COALESCE(cc.npl1,0)=1
              THEN COALESCE(cc.bal1, bb.bal0) ELSE 0 END AS npl_bal,
         CASE WHEN bb.npl0=0 AND COALESCE(cc.npl1,0)=1 THEN 1 ELSE 0 END AS dn
  FROM bb LEFT JOIN cc ON cc.FORM_NO = bb.FORM_NO
)
SELECT yr,
       SUM(CASE WHEN in_cohort=1 THEN bal0 ELSE 0 END) AS cohort_bal,
       SUM(CASE WHEN in_cohort=1 THEN npl_bal ELSE 0 END) AS cohort_npl,
       SUM(bal0) AS all_bal, SUM(npl_bal) AS all_npl,
       COUNT(DISTINCT CASE WHEN in_cohort=1 THEN CUST_NO END) AS cohort_n
FROM chg
GROUP BY yr
ORDER BY yr
"""


def check_temporal(rows, cfg):
    """时间集中性判定。rows = [{yr, cohort_bal, cohort_npl, ...}]"""
    pts = []
    for r in rows:
        bal = to_num(r.get("cohort_bal")) or 0
        npl = to_num(r.get("cohort_npl")) or 0
        if bal <= 0:
            continue
        pts.append({"yr": r.get("yr"), "bal": bal, "npl_bal": npl,
                    "rate": npl / bal})
    if len(pts) < 3:
        return {"test": "temporal_cluster", "verdict": "unavailable",
                "reason": f"可用年份仅 {len(pts)} 个，无法判断时间分布"}

    tot_npl = sum(p["npl_bal"] for p in pts)
    if tot_npl <= 0:
        return {"test": "temporal_cluster", "verdict": "unavailable",
                "reason": "该客群无新增不良，无法做时间分布检验"}
    top = max(pts, key=lambda p: p["npl_bal"])
    share = top["npl_bal"] / tot_npl
    rates = [p["rate"] for p in pts]
    spread = (max(rates) / min(rates)) if min(rates) > 0 else None

    detail = "；".join(f"{p['yr']}年 {p['rate']:.2%}" for p in pts)
    if share >= cfg["temporal_share"]:
        return {"test": "temporal_cluster", "verdict": "support",
                "reason": f"新增不良集中在 {top['yr']} 年放款批次（占 {share:.1%}），"
                          f"符合「某时点后管理变化」的预期",
                "detail": detail, "top_share": round(share, 4),
                "yearly_rates": {p["yr"]: round(p["rate"], 6) for p in pts}}
    if spread is not None and spread < 1.3:
        return {"test": "temporal_cluster", "verdict": "refute",
                "reason": f"各年放款批次生成率接近（最大/最小 {spread:.2f} 倍），"
                          f"新增不良在时间上均匀分布，不像一次性管理变化，"
                          f"更可能是长期存在的结构性问题",
                "detail": detail, "top_share": round(share, 4),
                "yearly_rates": {p["yr"]: round(p["rate"], 6) for p in pts}}
    return {"test": "temporal_cluster", "verdict": "neutral",
            "reason": f"最大批次占比 {share:.1%}，年份间差异 {spread:.2f} 倍，"
                      f"未达集中判定也不会推翻", "detail": detail,
            "yearly_rates": {p["yr"]: round(p["rate"], 6) for p in pts}}


# ============================================================ 检验 2：剂量反应

def sql_dose_quantile(cohort_conds, slice_v, base_slice, field, table=cs.TABLE):
    """按客群内部三分位分档，而不是用固定金额断点。

    为什么必须用分位数
    ------------------
    固定断点（10万/30万/50万）在「余额≥50万」这类客群上会全部失效：
    前三档都是空集，只剩一档可用，剂量反应必然 unavailable。
    按客群自身分位数切，无论客群落在什么区间，都能切出三档可比样本。
    """
    cond = " AND ".join("(" + c + ")" for c in cohort_conds)
    if field == "FORM_BAL_RMB":
        expr = "TRY_CAST(FORM_BAL_RMB AS DOUBLE)"
    elif field == "EXD_DAYS":
        expr = "TRY_CAST(EXD_DAYS AS BIGINT)"
    else:
        expr = field
    return f"""
WITH bb AS (
  SELECT CUST_NO, FORM_NO, {expr} AS val,
         CAST(FORM_BAL_RMB AS DOUBLE) AS bal0,
         CASE WHEN substr(RSK_CLS_CD,1,1) IN ('3','4','5') THEN 1 ELSE 0 END AS npl0,
         CASE WHEN {cond.strip()} THEN 1 ELSE 0 END AS in_cohort
  FROM {table}
  WHERE DATA_DAT='{base_slice}' AND BUS_BREED_CD LIKE 'A70%'
),
cc AS (
  SELECT FORM_NO,
         CASE WHEN substr(RSK_CLS_CD,1,1) IN ('3','4','5') THEN 1 ELSE 0 END AS npl1,
         CAST(FORM_BAL_RMB AS DOUBLE) AS bal1
  FROM {table}
  WHERE DATA_DAT='{slice_v}' AND BUS_BREED_CD LIKE 'A70%'
),
chg AS (
  SELECT bb.CUST_NO, bb.val, bb.bal0, bb.in_cohort,
         CASE WHEN bb.npl0=0 AND COALESCE(cc.npl1,0)=1
              THEN COALESCE(cc.bal1, bb.bal0) ELSE 0 END AS npl_bal
  FROM bb LEFT JOIN cc ON cc.FORM_NO = bb.FORM_NO
),
co AS (SELECT * FROM chg WHERE in_cohort=1 AND val IS NOT NULL),
q AS (
  SELECT quantile_cont(val, 0.3333) AS p33,
         quantile_cont(val, 0.6667) AS p67
  FROM co
)
SELECT CASE WHEN co.val <= q.p33 THEN '低档'
            WHEN co.val <= q.p67 THEN '中档'
            ELSE '高档' END AS bucket,
       COUNT(DISTINCT co.CUST_NO) AS n,
       SUM(co.bal0) AS tot_bal, SUM(co.npl_bal) AS npl_bal
FROM co CROSS JOIN q
GROUP BY 1
"""


def check_dose(rows, cfg):
    """剂量反应判定。相邻档是否有超过阈值的比例在递增。

    注意：必须按「低→中→高」的语义顺序排列，不能依赖 SQL 返回顺序。
    GROUP BY 不保证输出顺序，实测返回过 高/低/中 的乱序，
    直接按返回顺序判断单调性会得出与事实相反的结论。
    """
    order = {"低档": 0, "中档": 1, "高档": 2}
    pts = []
    for r in rows:
        bal = to_num(r.get("tot_bal")) or 0
        npl = to_num(r.get("npl_bal")) or 0
        n = to_num(r.get("n")) or 0
        if bal <= 0 or n < cfg["min_bucket_n"]:
            continue
        pts.append({"bucket": r.get("bucket"), "n": int(n),
                    "rate": npl / bal,
                    "_o": order.get(str(r.get("bucket")), 9)})
    pts.sort(key=lambda p: p["_o"])
    if len(pts) < 3:
        return {"test": "dose_response", "verdict": "unavailable",
                "reason": f"通过样本量门槛的分档仅 {len(pts)} 个，无法判断单调性"}

    ups = sum(1 for a, b in zip(pts, pts[1:]) if b["rate"] > a["rate"])
    ratio = ups / (len(pts) - 1)
    detail = "；".join(f"{p['bucket']} {p['rate']:.2%}(n={p['n']})" for p in pts)

    # 仅看「相邻递增比例」在小样本下太宽松：3 个相邻对里有 2 个递增就是 0.67，
    # [10%, 12%, 9%, 11%] 这种来回波动也会被判成单调。
    # 加三条硬条件补齐：
    #   1) 首尾必须递增（整体趋势向上）
    #   2) 最高档必须出现在最后（剂量关系的定义就是「越强越差」，
    #      最高点落在中间说明关系非单调）
    #   3) 最高档至少是最低档的 1.5 倍（10%→12% 这种噪声不算剂量关系）
    first_last_up = pts[-1]["rate"] > pts[0]["rate"]
    lo_rate = min(p["rate"] for p in pts)
    hi_rate = max(p["rate"] for p in pts)
    amplitude = (hi_rate / lo_rate) if lo_rate > 0 else None
    peak_at_end = pts[-1]["rate"] >= hi_rate * 0.999
    has_trend = (amplitude is not None and amplitude >= cfg["dose_amplitude"])

    if (ratio >= cfg["dose_monotonic_min"] and first_last_up
            and has_trend and peak_at_end):
        return {"test": "dose_response", "verdict": "support",
                "reason": f"{ups}/{len(pts)-1} 个相邻区间递增，最高档位于末端，"
                          f"为最低档的 {(amplitude or 0):.2f} 倍，"
                          f"符合「该因素越强问题越严重」的预期",
                "detail": detail, "monotonic_ratio": round(ratio, 3),
                "amplitude": round(amplitude or 0, 3)}
    rev = sum(1 for a, b in zip(pts, pts[1:]) if b["rate"] < a["rate"])
    if rev / (len(pts) - 1) >= cfg["dose_monotonic_min"] and pts[-1]["rate"] < pts[0]["rate"]:
        return {"test": "dose_response", "verdict": "refute",
                "reason": f"{rev}/{len(pts)-1} 个相邻区间生成率**递减**，"
                          f"方向与假设相反，该因素不是驱动因素",
                "detail": detail, "monotonic_ratio": round(ratio, 3)}
    return {"test": "dose_response", "verdict": "neutral",
            "reason": f"分档生成率无稳定上升趋势（{ups}/{len(pts)-1} 递增，"
                      f"首尾{'上升' if first_last_up else '下降'}，"
                      f"幅度 {amplitude:.2f} 倍），"
                      f"该因素与风险的剂量关系不成立，但不排除其他机制",
            "detail": detail, "monotonic_ratio": round(ratio, 3),
            "amplitude": round(amplitude, 3) if amplitude else None}


# ============================================================ 检验 3：行为分化

def check_behavior(vintage_rows, cfg):
    """准入 vs 贷后：不同放款批次的生成率差异。

    准入问题 → 放款当时定生死，各批次内部表现应相对一致（差异小）
    贷后问题 → 放款后经过时间越长暴露越多，批次间差异应显著
    """
    pts = []
    for r in vintage_rows:
        bal = to_num(r.get("cohort_bal")) or 0
        npl = to_num(r.get("cohort_npl")) or 0
        n = to_num(r.get("cohort_n")) or 0
        if bal <= 0 or n < cfg["min_bucket_n"]:
            continue
        pts.append({"yr": r.get("yr"), "n": int(n), "rate": npl / bal})
    if len(pts) < 2:
        return {"test": "behavior_split", "verdict": "unavailable",
                "reason": f"可用批次仅 {len(pts)} 个，无法区分准入与贷后"}

    rates = [p["rate"] for p in pts]
    lo, hi = min(rates), max(rates)
    ratio = (hi / lo) if lo > 0 else None
    detail = "；".join(f"{p['yr']} {p['rate']:.2%}" for p in pts)

    if ratio is None:
        return {"test": "behavior_split", "verdict": "neutral",
                "reason": "存在零生成率批次，无法计算比值", "detail": detail}

    if ratio >= cfg["behavior_ratio"]:
        return {"test": "behavior_split", "verdict": "support_loan_after",
                "reason": f"不同放款批次生成率差异达 {ratio:.2f} 倍，"
                          f"老批次明显更差 → 与「贷后管理缺位、暴露随时间累积」"
                          f"更一致，而非一次性准入失守",
                "detail": detail, "batch_ratio": round(ratio, 3)}
    return {"test": "behavior_split", "verdict": "support_admission",
            "reason": f"不同放款批次生成率差异仅 {ratio:.2f} 倍，"
                      f"批次间表现接近 → 问题在放款当时就已决定，"
                      f"指向准入环节而非贷后管理",
            "detail": detail, "batch_ratio": round(ratio, 3)}


# ============================================================ 检验 4：对照组特征

def sql_control(cohort_conds, slice_v, base_slice, table=cs.TABLE):
    """客群内正常客户 vs 全辖正常客户的行为特征差异。

    用逾期比例作为「非不良客户的风险余量」代理：
    若客群内**正常客户**的逾期比例也与全辖正常客户有巨大差异，
    说明该客群是「整体资质差」（结构性问题），不只是不良那几个坏。
    """
    cond = " AND ".join("(" + c + ")" for c in cohort_conds)
    npl = "substr(RSK_CLS_CD,1,1) IN ('3','4','5')"
    return f"""
SELECT 'cohort_normal' AS grp,
       COUNT(DISTINCT CUST_NO) AS n,
       COUNT(DISTINCT CASE WHEN TRY_CAST(EXD_DAYS AS BIGINT) > 0 THEN CUST_NO END) AS exd_n
FROM {table}
WHERE DATA_DAT='{slice_v}' AND BUS_BREED_CD LIKE 'A70%'
  AND NOT ({npl}) AND ({cond})
UNION ALL
SELECT 'all_normal' AS grp,
       COUNT(DISTINCT CUST_NO) AS n,
       COUNT(DISTINCT CASE WHEN TRY_CAST(EXD_DAYS AS BIGINT) > 0 THEN CUST_NO END) AS exd_n
FROM {table}
WHERE DATA_DAT='{slice_v}' AND BUS_BREED_CD LIKE 'A70%'
  AND NOT ({npl})
"""


def check_control(rows, cfg):
    """客群内正常客户 vs 全辖正常客户的逾期率对比。"""
    g = {r.get("grp"): r for r in rows}
    a, b = g.get("cohort_normal"), g.get("all_normal")
    if not a or not b:
        return {"test": "control_profile", "verdict": "unavailable",
                "reason": "对照组取数失败"}
    na, nb = to_num(a.get("n")) or 0, to_num(b.get("n")) or 0
    if na < cfg["min_bucket_n"] or nb <= 0:
        return {"test": "control_profile", "verdict": "unavailable",
                "reason": f"客群内正常客户仅 {na:.0f} 户，样本不足"}
    pa = (to_num(a.get("exd_n")) or 0) / na
    pb = (to_num(b.get("exd_n")) or 0) / nb
    z, pv = _z_test(pa, na, pb, nb)
    detail = f"客群内正常客户逾期率 {pa:.2%}(n={na:.0f})，全辖正常客户 {pb:.2%}(n={nb:.0f})"
    if z is None:
        return {"test": "control_profile", "verdict": "neutral", "detail": detail}

    ratio = (pa / pb) if pb else None
    significant = (pv is not None and pv <= cfg["z_alpha"])
    p_str = f"{pv:.3f}" if pv is not None else "—"

    if significant and ratio is not None and ratio >= 1.3:
        return {"test": "control_profile", "verdict": "support_structural",
                "reason": f"客群内**正常客户**的逾期率显著高于全辖（比值 {ratio:.2f}，"
                          f"p={p_str}），说明该客群整体资质偏弱，不是个别客户出了问题，"
                          f"差异含结构成分",
                "detail": detail, "ratio": round(ratio, 3),
                "p_value": round(pv, 4) if pv is not None else None}

    if significant and ratio is not None and ratio < 1:
        # 客群内正常客户反而比全辖更好 —— 这是「对比性证据」：
        # 说明该客群的风险完全集中在少数变坏的客户上，客群本身不差。
        return {"test": "control_profile", "verdict": "support_isolated",
                "reason": f"客群内**正常客户**的逾期率显著低于全辖正常客户"
                          f"（{pa:.2%} vs {pb:.2%}，p={p_str}），"
                          f"说明该客群整体资质尚可，风险集中在少数变坏的客户上，"
                          f"指向个体风险事件而非客群结构",
                "detail": detail, "ratio": round(ratio, 3),
                "p_value": round(pv, 4) if pv is not None else None}

    return {"test": "control_profile", "verdict": "neutral",
            "reason": f"客群内正常客户与全辖正常客户无显著差异（{pa:.2%} vs {pb:.2%}，"
                      f"p={p_str}），差异主要来自风险事件本身，不指向客群整体资质",
            "detail": detail, "p_value": round(pv, 4) if pv is not None else None}


# ============================================================ 汇总

VERDICT_WEIGHT = {"refute": -2, "support": 1, "support_admission": 1,
                  "support_loan_after": 1, "support_structural": 0,
                  "support_isolated": 1,
                  "neutral": 0, "unavailable": 0}


def aggregate(checks):
    """四个检验汇总成假设级证伪状态。

    support_structural 权重 0：它反驳的是「管理问题」这个方向，
    但同时也在解释现象，所以既不加分也不减分，只在叙事里体现。
    """
    usable = [c for c in checks if c.get("verdict") != "unavailable"]
    refuted = [c for c in usable if c.get("verdict") == "refute"]
    supports = [c for c in usable if VERDICT_WEIGHT.get(c.get("verdict"), 0) > 0]

    if not usable:
        return {"status": "untested",
                "note": "没有任何可执行的检验项（缺数据），假设不得视为成立"}
    if refuted:
        return {"status": "refuted",
                "note": f"{len(refuted)} 项检验明确反驳："
                        + "；".join(c["test"] for c in refuted)}
    if supports:
        return {"status": "survived",
                "note": f"{len(supports)} 项检验未发现反驳且支持假设；"
                        f"注意这只能说明「未被推翻」，不等于已证明"}
    return {"status": "weakened",
            "note": "无反驳项但也无支持项，假设证据不足，降级为待验证"}


def build_narrative(hypothesis, checks, agg):
    """生成中文结论段。措辞严格区分「未被推翻」与「已证明」。"""
    names = {"temporal_cluster": "时间集中性", "dose_response": "剂量反应",
             "behavior_split": "准入与贷后区分", "control_profile": "客群资质对照"}
    lines = []
    if agg["status"] == "untested":
        return f"「{hypothesis}」缺少可执行的检验项，暂不纳入结论，列为待验证。"
    if agg["status"] == "refuted":
        lines.append(f"「{hypothesis}」被数据反驳：")
        for c in checks:
            if c.get("verdict") == "refute":
                lines.append(f"· {names.get(c['test'], c['test'])}：{c.get('reason')}")
        lines.append("该假设不应作为结论引用。")
        return "".join(lines)

    lines.append(f"「{hypothesis}」{agg['note']}。")
    for c in checks:
        v = c.get("verdict")
        if v == "unavailable":
            continue
        tag = {"support": "支持", "support_admission": "支持（指向准入）",
               "support_loan_after": "支持（指向贷后）",
               "support_structural": "提示结构性因素",
               "support_isolated": "支持（风险集中于个体）",
               "neutral": "中性", "refute": "反驳"}.get(v, v)
        lines.append(f"· {names.get(c['test'], c['test'])}［{tag}］：{c.get('reason')}")
    if agg["status"] == "survived":
        lines.append("以上仅为未发现反驳证据，不等于已证实；"
                     "如需定性结论，还需补充审批过程与贷后处置数据。")
    return "".join(lines)


# ============================================================ 主流程

def run_one(con, dx, hypothesis, cohort_conds, args, cfg):
    """对单个假设执行全部检验。"""
    def _q(sql):
        cols, rws, _ = dx.run_sql(con, sql, args.data_dir)
        return [dict(zip(cols, r)) for r in rws]

    checks = []
    temporal_rows = []
    try:
        temporal_rows = _q(sql_temporal(cohort_conds, args.slice,
                                        args.base_slice))
        checks.append(check_temporal(temporal_rows, cfg))
    except Exception as exc:   # noqa: BLE001
        checks.append({"test": "temporal_cluster", "verdict": "unavailable",
                       "reason": f"取数失败：{exc}"})

    if temporal_rows:
        checks.append(check_behavior(temporal_rows, cfg))

    try:
        dose_rows = _q(sql_dose_quantile(cohort_conds, args.slice,
                                         args.base_slice, "FORM_BAL_RMB"))
        checks.append(check_dose(dose_rows, cfg))
    except Exception as exc:   # noqa: BLE001
        checks.append({"test": "dose_response", "verdict": "unavailable",
                       "reason": f"取数失败：{exc}"})

    try:
        ctrl_rows = _q(sql_control(cohort_conds, args.slice, args.base_slice))
        checks.append(check_control(ctrl_rows, cfg))
    except Exception as exc:   # noqa: BLE001
        checks.append({"test": "control_profile", "verdict": "unavailable",
                       "reason": f"取数失败：{exc}"})

    agg = aggregate(checks)
    return {
        "hypothesis": hypothesis,
        "cohort_conds": cohort_conds,
        "checks": checks,
        "aggregate": agg,
        "narrative": build_narrative(hypothesis, checks, agg),
    }


def main():
    ap = argparse.ArgumentParser(description="归因假设的可证伪检验")
    ap.add_argument("--topic-gate", required=True)
    ap.add_argument("--combo-screen", required=True)
    ap.add_argument("--slice", default="20260831")
    ap.add_argument("--base-slice", required=True)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cfg = dict(DEFAULT_CFG)

    tg = json.load(open(args.topic_gate, encoding="utf-8"))
    cs_doc = json.load(open(args.combo_screen, encoding="utf-8"))
    topics = ((tg.get("selection") or {}).get("topics")) or []
    phenomena = cs_doc.get("phenomena") or []
    by_rule = {}
    for p in phenomena:
        for rid in (p.get("linked_rules") or []):
            by_rule.setdefault(rid, p)

    result = {
        "schema_version": SCHEMA_VERSION, "kind": "falsification",
        "slice": args.slice, "base_slice": args.base_slice,
        "criteria": cfg, "hypotheses": [], "skipped": [],
        "summary": {}, "warnings": [],
    }

    import drill_executor as dx
    duckdb = dx._load_duckdb()
    if duckdb is None:
        result["warnings"].append("duckdb 未安装，无法执行")
        json.dump(result, open(args.out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        return 2
    con = duckdb.connect()

    for t in topics:
        rid = t.get("rule_id")
        p = by_rule.get(rid)
        if not p or not (p.get("conds")):
            result["skipped"].append({"rule_id": rid, "name": t.get("name"),
                                      "reason": "无对应组合条件，无法定位客群"})
            continue
        name = t.get("name") or rid
        try:
            h = run_one(con, dx, name, p["conds"], args, cfg)
            result["hypotheses"].append(h)
        except Exception as exc:   # noqa: BLE001
            result["warnings"].append(f"假设「{name}」检验失败：{exc}")

    cnt = {}
    for h in result["hypotheses"]:
        s = h["aggregate"]["status"]
        cnt[s] = cnt.get(s, 0) + 1
    result["summary"] = {"total": len(result["hypotheses"]), "by_status": cnt}

    json.dump(result, open(args.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"✅ 可证伪检验：{len(result['hypotheses'])} 个假设 → {cnt}")
    for h in result["hypotheses"]:
        print(f"   [{h['aggregate']['status']}] {h['hypothesis']}")
    print(f"   → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
