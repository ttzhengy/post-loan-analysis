#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mitigate.py — 风险下可贷：在已确认的高风险客群内，找「什么条件下还能放」

为什么需要这一步
----------------
只输出「哪类客户不良高」是半个结论。分行不能因为一个客群整体不良率高
就全部停贷 —— 普惠、涉农、首贷户都有考核指标，一刀切停贷本身是经营损失。
真实决策要回答的是：**在同一批高风险客户里，哪些仍然可以正常放、
哪些附条件放、哪些必须暂停新增**。

本模块做的事
------------
输入一个已确认的客群条件（组合现象 hit 条件，或单一维度分档），在其内部
再按「缓释因子」分层，输出三档处置：

  normal   照常放贷   —— 生成率不高于全辖基线的 tolerance 倍
  cond     附条件放贷 —— 生成率高于基线 tolerance 倍、低于 pause 倍
  pause    暂停新增   —— 生成率高于基线 pause 倍

同时必须给出两个数（缺一即无法用于决策）：

  protect_factor  保护性履约因子
      = 同客群内正常履约子群生成率 / 客群整体生成率。>1 说明「这个客群里
      仍有相当比例的低风险客户」，一刀切停贷会误伤这部分。
      该因子直接回应「停贷是不是过度反应」。

  mis_hit         误伤规模
      = pause 档里**至今正常**的客户余额。停贷的成本就是这个数。
      报告必须写，不能只写「风险高所以停」。

口径
----
默认沿用 combo_split 的 chg（不良生成率）口径：缓释结论必须建立在
「同期谁新变坏」上，而不是存量不良率 —— 存量口径下历史包袱会让一个
其实已经好转的客群看起来仍然很糟。vch 口径仅用于兼容与对照。
"""
from __future__ import annotations

import argparse
import json
import re
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

# 缓释因子：在客群内部继续分层的维度。
# 每个 = (凭证表可判定条件, 中文名, 语义说明)
# 只用凭证表字段，理由同 combo_split：判不了的维度宁可不出，不硬凑。
MITIGATORS = {
    "maturity": {
        "label": "剩余期限",
        # 用借款日期推算：距分析时点满 3 个月的算「有缓冲期」
        "note": "以借款日期距分析时点的月数近似剩余期限；凭证表无到期日字段",
        # 客户级按最早一笔借款日定档（缓冲期最短的那笔），保证只落一档
        "agg": "MIN(LN_DAT)",
        "buckets": [
            ("3 个月以上缓冲期", "{agg} <= '{m3}'"),
            ("3 个月内到期",     "{agg} > '{m3}'"),
        ],
    },
    "overdue": {
        "label": "当前逾期状态",
        "note": "EXD_DAYS 逾期天数，最直接的风险前置信号；"
                "该字段以 VARCHAR 落盘，比较前必须转整数",
        # 客户级定档：按该客户在客群内**最严重**的一笔凭证判定。
        # 多笔凭证下若逐笔判档再取 MAX，同一客户会同时落进「无逾期」和
        # 「已现逾期」两档，两档户数之和超过客群户数（实测多出 453 户）。
        "agg": "MAX(COALESCE(TRY_CAST(EXD_DAYS AS BIGINT),0))",
        "buckets": [
            ("至今无逾期", "{agg} = 0"),
            ("已现逾期",   "{agg} >= 1"),
        ],
    },
    "guarantee": {
        "label": "担保方式",
        "note": "GRTE_MOD_CD 担保方式维度，缓释能力差异的最主要来源",
        # 客户多笔凭证可能各用不同担保方式，按「缓释能力最弱的一笔」定档：
        # 纯信用的分值最小，用 MIN 取到纯信用前缀即为最弱，无纯信用则取到
        # 抵押/保证类编码。这样每个客户只会落进一档。
        "agg": "MIN(GRTE_MOD_CD)",
        "buckets": [
            ("有抵押物担保", "{agg} IN ('" + cs.GRTE_CODE_MORTGAGE
                             + "','" + cs.GRTE_CODE_GUARANTEE
                             + "','" + cs.GRTE_CODE_AGRI + "')"),
            ("纯信用",       "{agg} = '" + cs.GRTE_CODE_CREDIT + "'"),
        ],
    },
    "amount": {
        "label": "单笔金额",
        "note": "以凭证余额分层，金额越大单户风险敞口越集中",
        # 客户级敞口取最大一笔的余额定档，避免同一客户在三档里各命中一次
        "agg": "MAX(CAST(FORM_BAL_RMB AS DOUBLE))",
        "buckets": [
            ("小额（<10万）",   "{agg} < 100000"),
            ("中额（10~30万）", "{agg} >= 100000 AND {agg} < 300000"),
            ("大额（≥30万）",   "{agg} >= 300000"),
        ],
    },
    "continuation": {
        "label": "是否接续放款",
        "note": "CONT_LN_IND，接续放款把到期压力后移，风险化解程度不同",
        # 有任一笔接续即算接续客户：接续是需要复核的动作，宁可归入需关注档
        "agg": "MAX(COALESCE(CONT_LN_IND,'0'))",
        "buckets": [
            ("非接续（新发放）", "{agg} <> '1'"),
            ("接续放款",         "{agg} = '1'"),
        ],
    },
    "tenor": {
        "label": "循环额度",
        "note": "CYC_LN_IND，循环额度可反复支用，敞口不受单次审批约束",
        "agg": "MAX(COALESCE(CYC_LN_IND,'0'))",
        "buckets": [
            ("普通额度", "{agg} <> '1'"),
            ("循环额度", "{agg} = '1'"),
        ],
    },
}

DEFAULT_CFG = {
    "tolerance": 1.0,    # ≤ 基线 ×1.0 → 照常放贷
    "pause": 3.0,        # ≥ 基线 ×3.0 → 暂停新增；中间 = 附条件
    "min_bucket_n": 50,  # 分层样本下限，低于此不出结论
}


def bucket_conflicts(cohort_conds, bucket_cond):
    """判断某个缓释分档是否与客群条件互斥（交集恒为空）。

    为什么必须判
    ------------
    缓释因子如果和客群自身条件说的是同一件事，切出来必然是空集或全集。
    例：客群条件是「纯信用（GRTE_MOD_CD='0100'）」，再拿「有抵押物担保」
    去分层 —— 这个分档在结构上不可能有客户。此时若照常输出，
    报告会得到「有抵押物担保 0 户」，读者会误以为数据缺失或取数出错。

    更麻烦的是另一个方向：客群条件含 GRTE_MOD_CD='0100'，
    分档条件也是 GRTE_MOD_CD='0100'，切出来等于整个客群，
    这一档的生成率会与客群基线完全相同，看起来像「该分层无区分度」，
    实际上是同义反复。

    这里用字符串级的等价判定，覆盖字段等值与非等值两种方向。
    不做通用 SQL 求解 —— 那是另一个项目，且容易误判。
    """
    a = " ".join(cohort_conds).upper()
    b = bucket_cond.upper()

    # 先把 CAST(... AS DOUBLE) 抹平成裸字段名。**必须在去空格之前**做：
    # 一旦去掉空格，"FORM_BAL_RMB AS DOUBLE" 会粘成 "FORM_BAL_RMBASDOUBLE"，
    # AS 与字段名无法再切分，任何正则都匹配不回来了。
    def _norm(s):
        s = re.sub(r"CAST\(\s*([A-Z_0-9]+)\s+AS\s+[A-Z]+\s*\)", r"\1", s)
        s = re.sub(r"NOT\s+IN\s*\(\s*([^)]*)\)", r"NOTIN \1", s)
        return s.replace(" ", "").replace("(", "").replace(")", "")

    a, b = _norm(a), _norm(b)

    # 等值 vs 非等值冲突：客群限定 ='0101'，分档要求 NOT IN ('0101') 或 IN ('0201',...)
    for field in ("GRTE_MOD_CD", "CONT_LN_IND", "CYC_LN_IND", "RPAY_MOD_CD"):
        m_co = re.search(field + r"='([^']+)'", a)
        b_eq = re.search(field + r"='([^']+)'", b)
        b_ne = re.search(field + r"NOTIN'([^']+)'", b)
        # 分档是 IN(...) 白名单：客群锁定的值不在白名单里 → 交集为空
        b_in = re.search(field + r"IN'([^']+)'", b)
        if m_co and b_in:
            allowed = [x.strip().strip("'") for x in b_in.group(1).split(",")]
            if m_co.group(1) not in allowed:
                return True, (f"客群限定 {field}='{m_co.group(1)}'，"
                              f"分档白名单 {allowed} 不含该值，交集为空")
        if m_co and b_ne:
            # b_ne.group(1) 已是不含引号的裸值（正则捕获的是引号内部）
            if m_co.group(1) in [x.strip().strip("'") for x in b_ne.group(1).split(",")]:
                return True, f"客群限定 {field}='{m_co.group(1)}'，分档要求非该值，交集为空"
        # 客群限定某值，分档是该值的**补集**（含 <> 写法）
        b_ne2 = re.search(field + r"<>'([^']+)'", b)
        if m_co and b_ne2 and b_ne2.group(1) == m_co.group(1):
            return True, f"客群限定 {field}='{m_co.group(1)}'，分档要求不等于该值，交集为空"
        # 分档条件与客群条件完全相同 → 同义反复
        if m_co and b_eq and m_co.group(1) == b_eq.group(1) and a.count(field) >= 1:
            only_co = re.sub(field + r"='[^']+'", "", a).replace("AND", "").strip()
            if not only_co:
                return True, f"分档条件与客群条件完全相同（{field}），无区分意义"

    # 金额区间冲突：客群要求 >= X，分档要求 < X
    m_ge = re.search(r"FORM_BAL_RMB>=(\d+)", a)
    b_lt = re.search(r"FORM_BAL_RMB<(\d+)", b)
    if m_ge and b_lt and int(b_lt.group(1)) <= int(m_ge.group(1)):
        return True, f"客群要求余额≥{m_ge.group(1)}，分档要求<{b_lt.group(1)}，交集为空"
    m_le = re.search(r"FORM_BAL_RMB<=(\d+)", a)
    b_ge = re.search(r"FORM_BAL_RMB>=(\d+)", b)
    if m_le and b_ge and int(b_ge.group(1)) > int(m_le.group(1)):
        return True, f"客群要求余额≤{m_le.group(1)}，分档要求≥{b_ge.group(1)}，交集为空"

    return False, ""


def _agg_field(agg):
    """从聚合表达式里取出裸字段名：MAX(COALESCE(TRY_CAST(EXD_DAYS AS BIGINT),0))
    → EXD_DAYS。仅用于 bucket_conflicts 的字符串级冲突探测。
    """
    if not agg:
        return ""
    import re
    m = re.search(r"(EXD_DAYS|GRTE_MOD_CD|FORM_BAL_RMB|LN_DAT|CONT_LN_IND|CYC_LN_IND)", agg)
    return m.group(1) if m else ""


def usable_mitigators(cohort_conds, keys=None):
    """筛掉与客群条件冲突的缓释分档，返回 (可用分档, 被跳过及原因)。"""
    keys = keys or list(MITIGATORS)
    usable, skipped = [], []
    for key in keys:
        spec = MITIGATORS.get(key)
        if not spec:
            continue
        kept = []
        for label, cond in spec["buckets"]:
            # 冲突判定用「字段级原形」：把 {agg} 换回裸字段名，
            # 否则占位符会让等值/互斥比对失真。
            probe = cond.replace("{agg}", _agg_field(spec.get("agg"))).replace("{m3}", "0")
            hit_conflict, why = bucket_conflicts(cohort_conds, probe)
            if hit_conflict:
                skipped.append({"mitigator": key, "mitigator_label": spec["label"],
                                "bucket": label, "reason": why})
            else:
                kept.append((label, cond))
        if len(kept) < 2:
            # 剩下不足两档 = 这个维度切不开，整维不出
            if kept:
                skipped.append({
                    "mitigator": key, "mitigator_label": spec["label"],
                    "bucket": kept[0][0],
                    "reason": "该维度与客群条件冲突，剩余不足两档，不出结论"})
            continue
        usable.append({"key": key, "label": spec["label"], "note": spec["note"],
                       "agg": spec.get("agg"), "buckets": kept})
    return usable, skipped


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


def fmt_pct(x, nd=2):
    v = to_num(x)
    return "—" if v is None else f"{v*100:.{nd}f}%"


def _m3(slice_v):
    """分析时点往前推 3 个月的 YYYYMMDD，用于近似「3 个月内到期」。"""
    y, m = int(slice_v[:4]), int(slice_v[4:6])
    m -= 3
    if m <= 0:
        m += 12
        y -= 1
    d = min(int(slice_v[6:8]), 28)
    return f"{y:04d}{m:02d}{d:02d}"


def bucket_sql(base_conds, bucket_cond, slice_v, level="chg", base_slice=None,
               m3=None, agg=None):
    """客群内部的一个分层 → hit / universe 两组（universe 即整个客群）。

    客户级定档，不能逐笔判档再取 MAX
    --------------------------------
    客户可能持有多笔凭证：一笔无逾期、另一笔已逾期。
    若在凭证级判定分层条件、再对客户取 MAX(bucket_hit)，则
      「至今无逾期」= 该客户有任一笔 EXD_DAYS=0
      「已现逾期」  = 该客户有任一笔 EXD_DAYS>=1
    两档会同时命中同一个客户。实测两档户数之和 40496 超过客群 40043
    （多出 453 户重叠），各档占比失真、加总不为 100%。

    正确做法是**先聚合到客户级，再用聚合值判档**：
    每个维度声明一个 `agg` 表达式（如 overdue 用 MAX(EXD_DAYS)，
    amount 用 MAX(余额)），客户级只产生一个值，档位天然互斥。

    `agg` 各档共用；未提供时退回凭证级判定（仅供单档调用方使用）。
    """
    if not base_conds:
        raise ValueError("bucket_sql 需要客群条件（至少 1 条）")
    # 只替换 {m3}；{agg} 留到下面替换成客户级列名 agg_val。
    # 用 replace 而非 str.format：条件里可能含其它花括号（如 JSON 片段、
    # 正则量词），format 会当作占位符解析并抛 KeyError。
    b = bucket_cond.replace("{m3}", m3 or _m3(slice_v))

    cohort_and = " AND ".join("(" + c + ")" for c in base_conds)
    npl = cs.NPL_EXPR
    # 判档表达式：作用于客户级聚合值 agg_val（不是原始字段）。
    # cli/cli2 只带出 agg_val，所以 {agg} 必须先替换成 agg_val，
    # 否则会去引用底层字段而报 Binder Error。
    # 未声明 agg 的维度（无 {agg} 占位）无法在客户级判定，直接报错，
    # 不静默退回凭证级 —— 那正是跨档 bug 的来源。
    if "{agg}" not in bucket_cond:
        raise ValueError(
            f"分层条件未声明 {{agg}} 占位符，无法在客户级判档：{bucket_cond}")
    bucket_expr = "CASE WHEN (" + b.replace("{agg}", "agg_val") + ") THEN 1 ELSE 0 END"

    if level == "chg":
        if not base_slice:
            raise ValueError("chg 口径必须提供 base_slice（对比时点）")
        # 三层：凭证级打标 → 客户级聚合出 agg 值 → 用 agg 值判档（互斥）
        # bucket_hit 必须在 cli 之后算，否则又退回「逐笔判档再 MAX」的老问题。
        return f"""
WITH b AS (
  SELECT CUST_NO, FORM_NO,
         CAST(FORM_BAL_RMB AS DOUBLE) AS bal0,
         CASE WHEN {npl} THEN 1 ELSE 0 END AS npl0,
         CASE WHEN {cohort_and} THEN 1 ELSE 0 END AS in_cohort,
         EXD_DAYS, GRTE_MOD_CD, LN_DAT, CONT_LN_IND, CYC_LN_IND,
         bal0 AS FORM_BAL_RMB
  FROM {cs.TABLE}
  WHERE DATA_DAT='{base_slice}' AND BUS_BREED_CD LIKE 'A70%'
),
cli AS (
  SELECT CUST_NO,
         MAX(in_cohort) AS in_cohort,
         {agg or 'MAX(FORM_NO)'} AS agg_val
  FROM b GROUP BY CUST_NO
),
cli2 AS (
  SELECT CUST_NO, in_cohort,
         CASE WHEN ({bucket_expr}) THEN 1 ELSE 0 END AS bucket_hit
  FROM cli
),
c AS (
  SELECT FORM_NO,
         CASE WHEN {npl} THEN 1 ELSE 0 END AS npl1,
         CAST(FORM_BAL_RMB AS DOUBLE) AS bal1
  FROM {cs.TABLE}
  WHERE DATA_DAT='{slice_v}' AND BUS_BREED_CD LIKE 'A70%'
),
tagged AS (
  SELECT cli2.CUST_NO, cli2.bucket_hit,
         SUM(CASE WHEN b.npl0=0 AND COALESCE(c.npl1,0)=1
                  THEN COALESCE(c.bal1, b.bal0) ELSE 0 END) AS npl_bal,
         SUM(CASE WHEN b.npl0=0 AND COALESCE(c.npl1,0)=1 THEN 1 ELSE 0 END) AS npl_vch_cnt,
         SUM(b.bal0) AS tot_bal
  FROM cli2 JOIN b ON b.CUST_NO = cli2.CUST_NO
  LEFT JOIN c ON c.FORM_NO = b.FORM_NO
  WHERE cli2.in_cohort = 1
  GROUP BY cli2.CUST_NO, cli2.bucket_hit
)
SELECT 'hit' AS grp, COUNT(*) AS n, SUM(npl_vch_cnt) AS npl_vch_cnt,
       SUM(npl_bal) AS npl_bal, SUM(tot_bal) AS tot_bal,
       SUM(npl_bal)/NULLIF(SUM(tot_bal),0) AS npl_rate
FROM tagged WHERE bucket_hit = 1
UNION ALL
SELECT 'universe' AS grp, COUNT(*) AS n, SUM(npl_vch_cnt) AS npl_vch_cnt,
       SUM(npl_bal) AS npl_bal, SUM(tot_bal) AS tot_bal,
       SUM(npl_bal)/NULLIF(SUM(tot_bal),0) AS npl_rate
FROM tagged
"""

    # vch 口径：单期，同样必须「客户级聚合后判档」，否则多笔客户会跨档
    return f"""
WITH b AS (
  SELECT CUST_NO,
         MAX(CASE WHEN {cohort_and} THEN 1 ELSE 0 END) AS in_cohort,
         {agg or 'MAX(FORM_NO)'} AS agg_val,
         SUM(CASE WHEN {npl} THEN 1 ELSE 0 END) AS npl_vch_cnt,
         SUM(CASE WHEN {npl} THEN CAST(FORM_BAL_RMB AS DOUBLE) ELSE 0 END) AS npl_bal,
         SUM(CAST(FORM_BAL_RMB AS DOUBLE)) AS tot_bal
  FROM {cs.TABLE}
  WHERE DATA_DAT='{slice_v}' AND BUS_BREED_CD LIKE 'A70%'
  GROUP BY CUST_NO
),
b2 AS (
  SELECT *, CASE WHEN ({bucket_expr}) THEN 1 ELSE 0 END AS bucket_hit
  FROM b
)
SELECT 'hit' AS grp, COUNT(*) AS n, SUM(npl_vch_cnt) AS npl_vch_cnt,
       SUM(npl_bal) AS npl_bal, SUM(tot_bal) AS tot_bal,
       SUM(npl_bal)/NULLIF(SUM(tot_bal),0) AS npl_rate
FROM b2 WHERE in_cohort = 1 AND bucket_hit = 1
UNION ALL
SELECT 'universe' AS grp, COUNT(*) AS n, SUM(npl_vch_cnt) AS npl_vch_cnt,
       SUM(npl_bal) AS npl_bal, SUM(tot_bal) AS tot_bal,
       SUM(npl_bal)/NULLIF(SUM(tot_bal),0) AS npl_rate
FROM b2 WHERE in_cohort = 1
"""


def group_sql(base_conds, slice_v, level="chg", base_slice=None):
    """整个客群（不切分层）的 hit / universe 两组，用作分层对比的基线。

    注意这里传的是同一组客群条件，universe 恒等于 hit；
    调用方取 hit 即为客群整体，用来做分层对比的基准生成率。
    """
    inner = list(base_conds)
    if len(inner) < 2:
        inner = inner + ["1=1"]
    return cs.split_sql(inner, slice_v, level=level, base_slice=base_slice)


def classify(rate, base_rate, cfg=None):
    """按生成率相对全辖基线的倍数判处置档。

    用 EPS 兜住浮点误差：0.30/0.10 在二进制里是 2.9999999999999996，
    直接 >= 3.0 会判成「附条件」，与业务口径（正好 3 倍即暂停）不符。
    """
    cfg = {**DEFAULT_CFG, **(cfg or {})}
    if rate is None or not base_rate:
        return "unknown", None
    multiples = rate / base_rate
    eps = 1e-9
    if multiples <= cfg["tolerance"] + eps:
        return "normal", multiples
    if multiples >= cfg["pause"] - eps:
        return "pause", multiples
    return "cond", multiples


def summarize(tiers, cfg=None):
    """把各分层结果汇总成决策表 + 保护性因子 + 误伤规模。

    tiers: [{bucket, label, n, hit_n, rate, tot_bal, npl_bal, multiple, tier}]
    """
    cfg = {**DEFAULT_CFG, **(cfg or {})}
    out = {"tiers": tiers, "tier_balance": {}, "protect_factor": None,
           "mis_hit": None, "warnings": []}

    for t in tiers:
        tier = t.get("tier") or "unknown"
        out["tier_balance"].setdefault(tier, {"n": 0, "bal": 0.0, "npl_bal": 0.0})
        out["tier_balance"][tier]["n"] += t.get("n") or 0
        out["tier_balance"][tier]["bal"] += t.get("tot_bal") or 0
        out["tier_balance"][tier]["npl_bal"] += t.get("npl_bal") or 0

    # 保护性履约因子：能照常放的那部分敞口占比
    tot_bal = sum((t.get("tot_bal") or 0) for t in tiers) or 0
    normal_bal = sum((t.get("tot_bal") or 0) for t in tiers
                     if t.get("tier") == "normal") or 0
    if tot_bal:
        out["protect_factor"] = round(normal_bal / tot_bal, 4)

    # 误伤规模：pause 档里当前仍正常的客户余额
    mis = 0.0
    for t in tiers:
        if t.get("tier") != "pause":
            continue
        bal = t.get("npl_bal") or 0
        mis += (t.get("tot_bal") or 0) - bal
    out["mis_hit"] = round(mis, 2)

    if not tiers:
        out["warnings"].append("没有任何分层通过样本量门槛，无法给出缓释建议")
    if out["protect_factor"] is not None and out["protect_factor"] > 0.5:
        out["warnings"].append(
            f"客群内有 {out['protect_factor']:.1%} 的敞口按生成率属正常水平，"
            f"整体停贷会造成较大误伤，应优先采用分层准入")
    return out


def build_report_block(summary, cohort_label="该客群"):
    """生成可直接进报告的中文决策段（不含技术标识）。"""
    if not summary or not summary.get("tiers"):
        return "该客群内部分层样本均不足，未形成可执行的准入差异建议。"

    order = {"pause": 0, "cond": 1, "normal": 2, "unknown": 3}
    tiers = sorted(summary["tiers"], key=lambda t: (order.get(t.get("tier"), 9),
                                                    -(t.get("rate") or 0)))
    name = {"normal": "照常放贷", "cond": "附条件放贷", "pause": "暂停新增",
            "unknown": "数据不足"}
    lines = []
    for t in tiers:
        lines.append(
            f"| {t.get('label')} | {t.get('n'):,} | {fmt_amt(t.get('tot_bal'))} | "
            f"{fmt_pct(t.get('rate'))} | "
            f"{('%.1f' % t['multiple']) if t.get('multiple') else '—'} 倍 | "
            f"{name.get(t.get('tier'), '—')} |")
    pf = summary.get("protect_factor")
    mis = summary.get("mis_hit")
    tail = []
    if pf is not None:
        tail.append(f"客群内 {pf:.1%} 的敞口按新增不良生成率仍处正常水平，"
                    f"整体停贷将误伤这部分客户，建议以分层准入替代一刀切。")
    if mis:
        tail.append(f"暂停新增档内当前仍正常的贷款余额 {fmt_amt(mis)}，"
                    f"即为该处置的潜在误伤规模，需一并评估。")
    return "\n".join(lines) + ("\n\n" + "".join(tail) if tail else "")


def main():
    ap = argparse.ArgumentParser(description="风险下可贷：高风险客群内部缓释分层")
    ap.add_argument("--conds", nargs="+", required=True,
                    help="客群条件（SQL 布尔表达式，来自 combo_split 的 hit 条件）")
    ap.add_argument("--label", default="高风险客群", help="客群中文名，进报告用")
    ap.add_argument("--slice", default="20260831")
    ap.add_argument("--level", default="chg", choices=list(cs.LEVELS))
    ap.add_argument("--base-slice", default=None)
    ap.add_argument("--data-dir", help="CSV/parquet 目录；给了才真执行")
    ap.add_argument("--mitigators", nargs="*", default=list(MITIGATORS),
                    help=f"启用哪些缓释因子，可选：{', '.join(MITIGATORS)}")
    ap.add_argument("--tolerance", type=float, default=DEFAULT_CFG["tolerance"])
    ap.add_argument("--pause", type=float, default=DEFAULT_CFG["pause"])
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cfg = {"tolerance": args.tolerance, "pause": args.pause,
           "min_bucket_n": DEFAULT_CFG["min_bucket_n"]}

    result = {
        "schema_version": SCHEMA_VERSION,
        "kind": "mitigation",
        "cohort": {"label": args.label, "conds": args.conds},
        "slice": args.slice, "level": args.level, "base_slice": args.base_slice,
        "criteria": cfg, "mitigators": {}, "summary": None,
        "narrative": "", "warnings": [],
    }

    bucket_defs = []
    m3 = _m3(args.slice)
    usable, conflict_skip = usable_mitigators(args.conds, args.mitigators)
    for s in conflict_skip:
        result["warnings"].append(
            f"{s['mitigator_label']}·{s['bucket']} 已跳过：{s['reason']}")
    result["conflict_skipped"] = conflict_skip

    for spec in usable:
        for label, cond in spec["buckets"]:
            bucket_defs.append({"mitigator": spec["key"], "label": label, "cond": cond,
                                "note": spec["note"], "agg": spec.get("agg")})
        result["mitigators"][spec["key"]] = {
            "label": spec["label"], "note": spec["note"],
            "buckets": [b[0] for b in spec["buckets"]]}
    for key in args.mitigators:
        spec = MITIGATORS.get(key)
        if spec and key not in result["mitigators"]:
            # 整维被冲突过滤掉，仍记录一下，便于追溯
            result["mitigators"][key] = {
                "label": spec["label"], "note": spec["note"],
                "buckets": [], "skipped": "与客群条件冲突，未使用"}

    if not args.data_dir:
        for b in bucket_defs:
            b["sql"] = bucket_sql(args.conds, b["cond"], args.slice,
                                  args.level, args.base_slice, m3,
                                  agg=b.get("agg"))
        result["plan"] = bucket_defs
        result["summary"] = {"tiers": [], "protect_factor": None, "mis_hit": None,
                             "warnings": ["dry-run：未连接数据源，仅产出分层 SQL"]}
        result["narrative"] = "（dry-run，未取数，不产出结论）"
        json.dump(result, open(args.out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print(f"✅ 缓释分层方案 {len(bucket_defs)} 个（dry-run）→ {args.out}")
        return 0

    import drill_executor as dx
    duckdb = dx._load_duckdb()
    if duckdb is None:
        result["warnings"].append("duckdb 未安装，无法执行")
        result["summary"] = {"tiers": [], "warnings": ["duckdb 缺失"]}
        json.dump(result, open(args.out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        return 2
    con = duckdb.connect()

    if args.level == "chg" and not args.base_slice:
        result["warnings"].append("chg 口径未给 base_slice，本模块无法自动探测，回退 vch")
        args.level = "vch"

    def _q(sql):
        cols, rws, _ = dx.run_sql(con, sql, args.data_dir)
        return {r[0]: dict(zip(cols, r)) for r in rws}

    # 客群整体基线（整个高风险客群的生成率与敞口）
    base_groups = _q(group_sql(args.conds, args.slice, args.level, args.base_slice))
    cohort_hit = base_groups.get("hit") or {}
    cohort_rate = to_num(cohort_hit.get("npl_rate"))
    cohort_bal = to_num(cohort_hit.get("tot_bal")) or 0.0
    result["cohort"]["n"] = cohort_hit.get("n")
    result["cohort"]["rate"] = cohort_rate
    result["cohort"]["bal"] = cohort_bal

    tiers = []
    for b in bucket_defs:
        g = _q(bucket_sql(args.conds, b["cond"], args.slice,
                          args.level, args.base_slice, m3,
                          agg=b.get("agg")))
        hit = g.get("hit") or {}
        n = to_num(hit.get("n")) or 0
        rate = to_num(hit.get("npl_rate"))
        if n < cfg["min_bucket_n"]:
            result["warnings"].append(
                f"「{b['label']}」样本 {n:.0f} 户低于门槛 {cfg['min_bucket_n']}，不出结论")
            continue
        tier, multiple = classify(rate, cohort_rate, cfg)
        tiers.append({
            "mitigator": b["mitigator"], "label": b["label"],
            "note": b["note"], "cond": b["cond"],
            "n": int(n), "rate": round(rate, 6) if rate is not None else None,
            "tot_bal": round(to_num(hit.get("tot_bal")) or 0, 2),
            "npl_bal": round(to_num(hit.get("npl_bal")) or 0, 2),
            "multiple": round(multiple, 3) if multiple else None,
            "tier": tier,
        })

    # 每个分层维度内部必须自洽：各档户数之和 == 客群户数（容差 1%）
    for key in result["mitigators"]:
        sub = [t for t in tiers if t["mitigator"] == key]
        if len(sub) < 2:
            continue
        s = sum(t["n"] for t in sub)
        cn = to_num(cohort_hit.get("n")) or 0
        if cn and abs(s - cn) > max(1, cn * 0.01):
            result["warnings"].append(
                f"「{MITIGATORS[key]['label']}」各档户数和 {s:.0f} 与客群 {cn:.0f} 不符"
                f"（差 {s-cn:+.0f}），该维度分层未覆盖全部客户，结论需谨慎")

    summary = summarize(tiers, cfg)
    result["summary"] = summary
    result["narrative"] = build_report_block(summary, args.label)

    json.dump(result, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    bytier = {}
    for t in tiers:
        bytier[t["tier"]] = bytier.get(t["tier"], 0) + 1
    print(f"✅ 缓释分层完成：{len(tiers)} 档 → {bytier}")
    if summary.get("protect_factor") is not None:
        print(f"   保护性履约敞口占比 {summary['protect_factor']:.1%}，"
              f"暂停档潜在误伤 {fmt_amt(summary.get('mis_hit'))}")
    print(f"   → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
