#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""combo_split.py — 风险指标组合的**真实求交集 + 回库取数**

背景
----
旧链路里「多风险指标叠加」是假的：C01 的 `零散获客 AND 无抵押缓释` 这类组合，
每个 member 走的是同一张机构级预聚合表的不同指标，命中集合根本没有交集运算，
最后算出来的是「member 覆盖率算术平均」，于是不同组合得到相同不良率。

本模块做三件事，每一件都要求**从凭证表重新取数**，不复用 cohort.json /
attribution.comparisons 里任何既有数字：

1. `translate(feature)` —— 特征 → 凭证表可执行条件（SQL 片段）。
   只认能从凭证表自身字段判定的特征；判不了的（征信/工商/亲属关系）返回
   `None` 并给出 reason，绝不硬凑。
2. `split_sql(conds, slice_v)` —— 给定组合条件，产出一条 SQL，
   同时返回 hit / nonhit / universe 三组：
     hit      = 组内全部条件同时满足（AND）
     nonhit   = 在「其余条件都满足」但漏掉至少一个条件的人群
     universe = 全辖
   这样 hit 与 nonhit 在同一批客户上互补，且 hit+nonhit 恒等于 universe，
   不可能出现「命中+对照 > 全辖」的越界。
3. `screen(...)` —— 现象成立性判定：hit 的 lift、样本量、以及
   逐条件单独 lift 与组合 lift 的差（组合是否真的带来增量）。

口径约定
--------
* 客户级：一律 COUNT(DISTINCT CUST_NO)；
* 不良：RSK_CLS_CD 首位 3/4/5（与 core_metrics 一致）；
* 不良率：按余额加权 Σ(不良余额)/Σ(余额)，与全辖基线同口径；
* 单条 SQL 同时输出 grp∈{hit,nonhit,universe} 三行，避免多次往返口径漂移。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402

SCHEMA_VERSION = "3.1"

TABLE = "G_00PF_PEAS_LN_VCH_DV"

# 基础过滤：与 core_metrics / drill_planner 完全一致，改动须同步三处
# 注意：chg 口径下条件判定发生在 **对比时点**（客户在对比时点是什么状态），
# 不良判定发生在 **分析时点**，所以 CHG_CTE 里需要两份过滤条件。
BASE_WHERE = "DATA_DAT = '{slice}' AND BUS_BREED_CD LIKE 'A70%'"
NPL_EXPR = "substr(RSK_CLS_CD,1,1) IN ('3','4','5')"

# —— 口径（level）——
# vch : 截面存量不良率 Σ(分析时点不良余额)/Σ(分析时点余额)  ← 旧口径，保留向后兼容
# chg : 新增不良生成率 Σ(对比正常→分析不良的余额)/Σ(对比时点在贷余额)
#
# 为什么要有 chg
# --------------
# vch 分子混着历史包袱与账龄效应：一笔 2019 年放的历史不良会一直躺在分子里，
# 让「今年才变坏的客群」和「早就坏了的客群」不可比。归因要回答的是
# 「同期内谁**新**变坏」，所以分子必须限定为「对比时点正常 且 分析时点不良」。
# 分母用对比时点在贷余额（风险敞口基数），不是分析时点余额——否则
# 已核销/已结清的敞口会从分母消失，分母被系统性低估。
LEVELS = ("vch", "chg")

# ============================================================ 特征 → 凭证表条件
# 只列出**能由凭证表字段直接判定**的特征。value 是 SQL 布尔表达式。
# note 写清口径，报告里会原样引用，避免读者误以为这是征信口径。
FEATURE_COND = {
    # —— 担保 / 额度结构 ——
    2: {"cond": "GRTE_MOD_CD = '0100'",
        "desc": "纯信用（无抵押物担保）",
        "note": "GRTE_MOD_CD=0100，凭证表担保方式维度"},
    13: {"cond": "GRTE_MOD_CD = '0100' AND CAST(FORM_BAL_RMB AS DOUBLE) >= 500000",
         "desc": "大额纯信用（单笔余额≥50万且无抵押）",
         "note": "GRTE_MOD_CD=0100 且 FORM_BAL_RMB≥50万"},
    7: {"cond": "CAST(FORM_BAL_RMB AS DOUBLE) >= 300000",
        "desc": "单笔大额（余额≥30万）",
        "note": "以凭证余额作授信规模的代理变量；凭证表无授信额度字段"},
    6: {"cond": "GRTE_MOD_CD IN ('0200','0300','0400','9900')",
        "desc": "非信用类担保（保证/抵押/质押）",
        "note": "GRTE_MOD_CD≠0100，用于对照信用类"},

    # —— 产品 / 业务品种 ——
    12: {"cond": "BUS_BREED_CD LIKE 'A701%'",
         "desc": "特定品种 A701（小额信用类）",
         "note": "BUS_BREED_CD 前缀匹配，品种字典见 table-dict"},

    # —— 期限 / 发放时点 ——
    30: {"cond": "LN_DAT >= '20250101'",
         "desc": "近两年新发放（2025 年起）",
         "note": "LN_DAT 借款日期；经营年限无字段，用放款时点作代理"},

    # —— 逾期与还款 ——
    44: {"cond": "EXD_DAYS >= 1",
         "desc": "曾出现逾期（EXD_DAYS≥1）",
         "note": "逾期是五级分类的前置信号，非不良定义本身，可用于归因"},
    43: {"cond": "EXD_DAYS BETWEEN 1 AND 90",
         "desc": "短期逾期已出现但未达 90 天",
         "note": "逾期 1–90 天，风险信号出现但处置未跟上"},

    # —— 接续 ——
    10: {"cond": "CONT_LN_IND = '1'",
         "desc": "接续贷款（续贷/借新还旧）",
         "note": "CONT_LN_IND=1"},
    46: {"cond": "CONT_LN_IND = '1' AND CONTINUE_FLAG IS NOT NULL AND CONTINUE_FLAG <> ''",
         "desc": "有前手凭证的接续（可追溯借新还旧链条）",
         "note": "CONT_LN_IND=1 且有 CONTINUE_FLAG"},

    # —— 偿还方式 / 循环 ——
    56: {"cond": "CYC_LN_IND = '1'",
         "desc": "循环额度贷款",
         "note": "CYC_LN_IND=1"},
    58: {"cond": "RPAY_MOD_CD IN ('02','03')",
         "desc": "非等额还款方式（按月付息到期还本等）",
         "note": "RPAY_MOD_CD 非等额本息，到期集中还本压力"},
}

# 明确无法落到凭证表的特征 → 给出不可用原因（写进报告，不静默丢弃）
FEATURE_UNAVAILABLE = {
    1: "机构级零散获客率，凭证表无「零散」标识",
    3: "评分分值在评分表（G_00PL_IDV_LN_CUST_ACARD_SCRE_DV），不在凭证表",
    4: "建档质量在预聚合表 S_00PF_PEAS_LN_ARC_QLT_RSK_ORG_ANL_C4",
    5: "欺诈线索在 S_00PF_PEAS_LN_RSK_ORG_C4",
    8: "审批意见在 G_00PF_PEAS_LN_WHT_CHK_FLOW_INFO，需按申请书 JOIN",
    9: "贷后任务在 B_00FT_PEAS_LN_DPSE_TASK_DTAL，无凭证号关联",
    11: "客户经理风险为机构级预聚合",
    14: "同日建档数需客户经理维度聚合，凭证表不支持单行判定",
    15: "地址异常为机构级汇总",
    16: "资产负债在客户档案，需按客户 JOIN",
    17: "资金往来线索在 S_00PF_PEAS_MGR_LN_RISK_C4",
    18: "贷后检查结论表无数据",
    19: "管户数需客户经理聚合",
    20: "交易流水在 S_00PF_SA_ACCT_TR_CUST_SUM",
    21: "短期资金流入为流水级信号",
    22: "共用经营场所需地址交叉",
    23: "申请次数在评分表",
    24: "押品评估在 G_00PL_IDV_LN_MGG_HPROP_RSK_INFO_DV",
    25: "企业成立日期在 B_00DT_FAS_IDV_BUS_INFO_H",
    26: "AUM/存款在客户资产汇总表",
    27: "异地标识需地址比对",
    28: "行业分类在机构级汇总 S_00PF_PEAS_OCPRSK_ORG_C4",
    29: "地址变更在企业变更表",
    31: "农地面积在 B_00DT_FAS_ANL_SITU_DOC_H",
    32: "多头借贷在征信 P 表",
    33: "负债规模在征信 P 表",
    34: "查询次数在征信 P 表",
    35: "拒贷记录在征信 P 表",
    36: "不良记录在征信 P 表",
    37: "交易时段需流水级数据",
    38: "婚姻状态已哈希脱敏",
    39: "家庭收入在 B_00DT_FAS_FMLY_SITU_DOC_H",
    40: "涉税强执在征信 P 表",
    41: "涉诉在征信 P 表",
    42: "资金流向需放款后流水明细",
    45: "总资产在客户档案表",
    47: "接续情况在 G_00PF_PEAS_LN_LSTY_VCH_CONT_SITU_INFO",
    48: "上门催收在 B_00FT_PMC_P_DOORTASK_DTAL",
    49: "亲属关系在 G_00PL_IDV_CUST_RLN_INFO_H",
    50: "联村带户在 P_00FAS_GFAS_VAF_LOAN_MANAGE",
    51: "合同级信息在 G_00PF_IDV_LN_CTRT_DV",
    52: "核销清收在 G_00PF_IDV_LN_VCH_CAN_LQDT_SECS_DV",
    53: "账单在 G_00PL_IDV_LN_BILL_AMT",
    54: "机构树在 B_00DT_C4_ORG_TREE_H",
    55: "企业变更有独立表",
    57: "押品产权在 B_00DT_FNC_CUST_AST_AND_PROP_OWNR_RLN_H",
    59: "评分历史在 B_00DT_PRLN_SCRE_EVT_H",
    60: "不良变动在 B_00DT_UHLTH_LN_AMT_CHG_H",
    61: "家庭村居在 G_00PF_PEAS_LN_FMLY_SITU_INFO",
    62: "持有产品在 S_00PF_IDV_CUST_HOLD_PD_BAL_SUM",
    63: "担保关系在 S_00PL_IDV_LN_GRTE_RLN",
}


def translate(feature_id, feature_name=""):
    """特征 → {cond, desc, note}；不可用返回 None（附 reason 由调用方取）"""
    c = FEATURE_COND.get(int(feature_id))
    if c:
        return dict(c, feature_id=int(feature_id), name=feature_name)
    return None


def unavailable_reason(feature_id):
    return FEATURE_UNAVAILABLE.get(int(feature_id), "该特征无法由凭证表字段判定")


# ============================================================ SQL 构造

# 聚合层对**客户级** CTE 求和：n=户数，不良余额/总余额为客户内已加总值
PROJ = [
    ("n", "COUNT(*)"),
    ("npl_vch_cnt", "SUM(npl_vch_cnt)"),
    ("npl_bal", "SUM(npl_bal)"),
    ("tot_bal", "SUM(tot_bal)"),
    ("npl_rate", "SUM(npl_bal) / NULLIF(SUM(tot_bal),0)"),
]


def _cte_vch(conds, slice_v, table=TABLE):
    """客户级归属 CTE（vch 截面口径）：每个客户只落一个组，杜绝 hit/nonhit 重叠。

    为什么必须做客户级归属
    ----------------------
    一个客户可能同时持有多笔凭证，其中一笔满足组合条件、另一笔不满足。
    若直接对凭证行分组，同一 CUST_NO 会同时出现在 hit 与 nonhit，
    hit + nonhit 必然 > 全辖客户数 —— 这就是真实报告里
    251,299 + 236,163 = 487,462 > 400,270 的成因。

    这里在**客户级**一次性聚合：hit_flag 判组合是否成立，
    余额与不良余额也在客户内加总。因此 `cli` 每行 = 一个客户，
    `COUNT(*)` 就是户数，`npl_rate` 是该组客户的余额加权不良率。

    hit ∪ nonhit = universe 且互斥，`hit_n + nonhit_n == universe_n`
    成为数学恒等式，可直接做硬校验。

    客户级判定口径（会写进报告，避免读者误解）：
      · 客户满足某条件 ⇔ 该客户**任一笔凭证**满足（EXISTS 语义）
      · 客户命中组合 ⇔ 组合内全部条件同时满足（AND）
      · 不良率仍按余额加权 Σ(不良余额)/Σ(余额)，分母限定在该客户组内
    """
    alland = " AND ".join("(" + c + ")" for c in conds)
    where = BASE_WHERE.format(slice=slice_v)
    return (
        "WITH cli AS (\n"
        "  SELECT CUST_NO,\n"
        "         MAX(CASE WHEN " + alland + " THEN 1 ELSE 0 END) AS hit_flag,\n"
        "         SUM(CASE WHEN " + NPL_EXPR + " THEN 1 ELSE 0 END) AS npl_vch_cnt,\n"
        "         SUM(CASE WHEN " + NPL_EXPR + " THEN CAST(FORM_BAL_RMB AS DOUBLE) ELSE 0 END) AS npl_bal,\n"
        "         SUM(CAST(FORM_BAL_RMB AS DOUBLE)) AS tot_bal\n"
        "  FROM " + table + "\n"
        "  WHERE " + where + "\n"
        "  GROUP BY CUST_NO\n"
        "),\n"
        "vch_tagged AS (\n"
        "  SELECT * FROM cli\n"
        ")\n"
    )


def _cte_chg(conds, slice_v, base_slice, table=TABLE):
    """客户级归属 CTE（chg 不良生成率口径）：两期凭证表按凭证号对齐。

    口径定义
    --------
    hit_flag   : 客户在**对比时点**任一笔凭证满足全部组合条件
                 （条件判定在对比时点做——归因要看的是「放贷当时/期初是什么状态
                 的客群后来变坏了」，而不是「已经变坏之后才呈现什么状态」，
                 后者会引入状态反演：不良客户的逾期天数、五级分类天然异常）
    npl_bal    : 对比时点**正常**且分析时点**不良**的凭证，在分析时点的不良余额
    tot_bal    : 对比时点的在贷余额（风险敞口基数）
    npl_vch_cnt: 由 normal 转为不良的凭证笔数

    为什么分子取分析时点余额、分母取对比时点余额
    --------------------------------------------
    分子是「这笔敞口最终坏成了多少」，自然用分析时点余额；
    分母是「期初有多少敞口暴露在风险下」，必须用对比时点余额。
    若分母也用分析时点余额，已结清/已核销的正常敞口会消失，
    分母被系统性低估，生成率虚高。

    左表（base）是骨架：只有在对比时点存在的凭证才有资格进分母。
    分析时点新增发放的凭证不进分母（它们的生成率要到下一期才可观测）。
    """
    alland = " AND ".join("(" + c + ")" for c in conds)
    base_where = BASE_WHERE.format(slice=base_slice)
    cur_where = BASE_WHERE.format(slice=slice_v)
    return (
        "WITH b AS (\n"
        "  SELECT CUST_NO, FORM_NO,\n"
        "         CAST(FORM_BAL_RMB AS DOUBLE) AS bal0,\n"
        "         CASE WHEN " + NPL_EXPR + " THEN 1 ELSE 0 END AS npl0,\n"
        "         CASE WHEN " + alland + " THEN 1 ELSE 0 END AS cond_hit\n"
        "  FROM " + table + "\n"
        "  WHERE " + base_where + "\n"
        "),\n"
        "c AS (\n"
        "  SELECT FORM_NO,\n"
        "         CAST(FORM_BAL_RMB AS DOUBLE) AS bal1,\n"
        "         CASE WHEN " + NPL_EXPR + " THEN 1 ELSE 0 END AS npl1\n"
        "  FROM " + table + "\n"
        "  WHERE " + cur_where + "\n"
        "),\n"
        # 客户级：只要在对比时点有任一笔凭证满足组合，即归入 hit
        "cli AS (\n"
        "  SELECT CUST_NO, MAX(cond_hit) AS hit_flag\n"
        "  FROM b GROUP BY CUST_NO\n"
        "),\n"
        # 凭证级对齐：对比正常 → 分析不良 才算新增不良
        "chg AS (\n"
        "  SELECT b.CUST_NO,\n"
        "         b.bal0,\n"
        "         CASE WHEN b.npl0 = 0 AND COALESCE(c.npl1,0) = 1\n"
        "              THEN COALESCE(c.bal1, b.bal0) ELSE 0 END AS npl1_bal,\n"
        "         CASE WHEN b.npl0 = 0 AND COALESCE(c.npl1,0) = 1 THEN 1 ELSE 0 END AS downgrade_vch\n"
        "  FROM b LEFT JOIN c ON c.FORM_NO = b.FORM_NO\n"
        "),\n"
        "vch_tagged AS (\n"
        "  SELECT g.CUST_NO, g.hit_flag,\n"
        "         SUM(x.downgrade_vch) AS npl_vch_cnt,\n"
        "         SUM(x.npl1_bal)      AS npl_bal,\n"
        "         SUM(x.bal0)          AS tot_bal\n"
        "  FROM cli g JOIN chg x ON x.CUST_NO = g.CUST_NO\n"
        "  GROUP BY g.CUST_NO, g.hit_flag\n"
        ")\n"
    )


def _cte(conds, slice_v, table=TABLE, level="vch", base_slice=None):
    if level == "chg":
        if not base_slice:
            raise ValueError("chg 口径必须提供 base_slice（对比时点）")
        return _cte_chg(conds, slice_v, base_slice, table)
    return _cte_vch(conds, slice_v, table)


def _agg(grp_label, where_extra=""):
    cols = ",\n       ".join(expr + " AS " + alias for alias, expr in PROJ)
    return ("SELECT '" + grp_label + "' AS grp,\n       " + cols + "\n"
            "FROM vch_tagged" + (("\nWHERE " + where_extra) if where_extra else ""))


def split_sql(conds, slice_v, table=TABLE, level="vch", base_slice=None):
    """组合条件 → 一条 SQL，输出 hit / nonhit / universe 三行（客户级归属）。

    conds: list[str] 布尔表达式，长度 >= 2（单条件是单维分析，不构成组合）
    hit     : 该客户至少一笔凭证同时满足全部条件
    nonhit  : 其余客户（含一笔都不满足的）
    universe: 全部有凭证的客户

    三个分组由同一 CTE 派生，避免多次扫描不同快照导致口径漂移。
    level="chg" 时 npl_rate 是**不良生成率**而非存量不良率，语义由
    result["level"] 显式记录，下游渲染必须据此改变措辞。
    """
    if len(conds) < 2:
        raise ValueError("split_sql 需要至少 2 个条件（单条件是单维分析，不构成组合）")
    parts = [
        _agg("hit", "hit_flag = 1"),
        _agg("nonhit", "hit_flag = 0"),
        _agg("universe"),
    ]
    body = "\nUNION ALL\n".join(parts)
    return (_cte(conds, slice_v, table, level, base_slice)
            + "SELECT * FROM (\n" + body + "\n) t\n"
            + "ORDER BY CASE grp WHEN 'hit' THEN 1 WHEN 'nonhit' THEN 2 ELSE 3 END")


def single_sql(cond, slice_v, table=TABLE, level="vch", base_slice=None):
    """单条件 → 客户级 hit / universe 两行（用于「组合 vs 单条件」增量检验）"""
    body = "\nUNION ALL\n".join([_agg("hit", "hit_flag = 1"), _agg("universe")])
    return (_cte([cond], slice_v, table, level, base_slice)
            + "SELECT * FROM (\n" + body + "\n) t\n"
            + "ORDER BY CASE grp WHEN 'hit' THEN 1 ELSE 2 END")


# ============================================================ 现象成立性判定

DEFAULT_SCREEN = {
    "min_hit_n": 200,          # 命中客户数下限
    "min_hit_share": 0.002,    # 命中占全辖比下限（0.2%）
    "lift_floor": 1.5,         # 组合整体 lift 下限
    "singleton_margin": 1.15,  # 组合 lift 应至少比最强单条件 lift 高 15%
    "nonhit_max_lift": 1.3,    # 对照组的 lift 上限，太高说明条件不具区分性
}


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def screen(hit, nonhit, universe, singles, cfg=None, level="vch"):
    """判定「这是不是一个真正的风险现象」。

    返回 status ∈ {phenomenon, weak_phenomenon, insufficient, broken}
      broken      : 口径不自洽（hit+nonhit≠universe，或命中超全辖）→ 证据作废
      insufficient: 样本不足
      weak_phenomenon: 有样本但 lift 不够，或组合未超过最强单条件
      phenomenon  : 通过

    额外返回 `incremental_lift` = 组合 lift / 最强单条件 lift，
    这是「叠加是否真的有增量」的判据，直接回应「每个组合不良率都一样」。
    """
    cfg = {**DEFAULT_SCREEN, **(cfg or {})}
    if not all([hit, nonhit, universe]):
        return "insufficient", {"reason": "缺少分组结果"}
    uh, un = _num(hit.get("n")), _num(nonhit.get("n"))
    uu = _num(universe.get("n"))
    if uh is None or un is None or uu is None or uu <= 0:
        return "insufficient", {"reason": "分组客户数缺失"}

    # —— 口径自洽（数学硬校验，不看 lift）——
    if abs((uh + un) - uu) > max(1, uu * 0.005):
        return "broken", {"reason": f"口径不自洽：命中 {uh:.0f} + 对照 {un:.0f} = {uh+un:.0f}，"
                                    f"全辖 {uu:.0f}（差 {uh+un-uu:+.0f}），证据作废"}
    if uh > uu * 1.001:
        return "broken", {"reason": f"命中 {uh:.0f} 户 > 全辖 {uu:.0f} 户，取数口径有误"}

    hit_rate = _num(hit.get("npl_rate"))
    non_rate = _num(nonhit.get("npl_rate"))
    uni_rate = _num(universe.get("npl_rate"))
    if hit_rate is None or non_rate is None or not uni_rate:
        return "insufficient", {"reason": "不良率缺失或全辖不良率为 0"}

    lift = hit_rate / non_rate if non_rate else None
    uni_lift = hit_rate / uni_rate if uni_rate else None
    share = uh / uu

    single_lifts = []
    for s in singles or []:
        r = _num((s.get("hit") or {}).get("npl_rate"))
        ur = _num((s.get("universe") or {}).get("npl_rate")) or uni_rate
        if r is not None and ur:
            single_lifts.append({"feature_id": s.get("feature_id"), "name": s.get("name"),
                                 "cond": s.get("cond"), "lift": r / ur, "n": (s.get("hit") or {}).get("n")})
    single_lifts.sort(key=lambda x: -(x["lift"] or 0))
    best_single = single_lifts[0] if single_lifts else None
    incremental = (uni_lift / best_single["lift"]) if best_single and best_single["lift"] else None

    metrics = {
        "level": level,
        "hit_n": uh, "nonhit_n": un, "universe_n": uu, "hit_share": round(share, 6),
        "hit_rate": round(hit_rate, 6), "nonhit_rate": round(non_rate, 6),
        "universe_rate": round(uni_rate, 6),
        "lift_vs_nonhit": round(lift, 4) if lift else None,
        "lift_vs_universe": round(uni_lift, 4) if uni_lift else None,
        "singles": single_lifts, "best_single": best_single,
        "incremental_lift": round(incremental, 4) if incremental else None,
    }

    rate_word = "生成率" if level == "chg" else "不良率"
    if uh < cfg["min_hit_n"] or share < cfg["min_hit_share"]:
        return "insufficient", {**metrics,
                                "reason": f"命中 {uh:.0f} 户（占比 {share:.2%}）低于门槛 "
                                          f"{cfg['min_hit_n']} 户 / {cfg['min_hit_share']:.1%}"}
    if uni_lift is None or uni_lift < cfg["lift_floor"]:
        return "weak_phenomenon", {**metrics,
                                   "reason": f"组合{rate_word} {hit_rate:.2%} 为全辖的 {uni_lift:.2f} 倍，"
                                             f"低于门槛 {cfg['lift_floor']}，不构成独立风险现象"}
    if incremental is not None and best_single and incremental < cfg["singleton_margin"]:
        return "weak_phenomenon", {**metrics,
                                   "reason": f"组合 lift {uni_lift:.2f} 仅为最强单条件"
                                             f"「{best_single['name']}」({best_single['lift']:.2f}) 的 "
                                             f"{incremental:.2f} 倍，叠加没有带来增量，"
                                             f"该现象由单条件主导，不成立为组合现象"}
    return "phenomenon", metrics


# ============================================================ 组合生成

def conds_conflict(conds):
    """判断一组条件是否逻辑互斥（交集恒为空）。

    为什么必须判
    ------------
    特征 2（纯信用 GRTE_MOD_CD='0100'）与特征 6（非信用
    GRTE_MOD_CD IN ('0200','0300','0400','9900')）是两个互斥集合，
    组合起来交集恒为空。旧版 build_candidates 只检查 cond **字符串**是否
    完全相同，于是把这类组合也送进库，白跑一遍 SQL 后拿到空集，
    最后报「insufficient：不良率缺失」—— 真正的错误（条件互斥）
    被伪装成数据问题，读者会以为数据不全。

    这类假组合在真实数据上同样是纯浪费：45 个特征里成对互斥的不止一组。

    判定方式：同一字段在两条条件里分别取了互不重叠的取值集合。
    只做集合级判断，不做通用布尔求解。
    """
    import re
    fields = ("GRTE_MOD_CD", "CONT_LN_IND", "CYC_LN_IND", "RPAY_MOD_CD",
              "BUS_BREED_CD")
    for f in fields:
        eq_sets = []      # 出现 = 'x' 的条件：取值集合只有一个元素
        ne_sets = []      # 出现 NOT IN 的条件：补集
        for c in conds:
            u = c.upper()
            if f not in u:
                continue
            m_eq = re.findall(f + r"\s*=\s*'([^']+)'", u)
            m_in = re.findall(f + r"\s+IN\s*\(([^)]+)\)", u)
            m_notin = re.findall(f + r"\s+NOT\s+IN\s*\(([^)]+)\)", u)
            m_like = re.findall(f + r"\s+LIKE\s+'([^']+)'", u)
            if m_eq:
                eq_sets.append(set(m_eq))
            if m_in:
                eq_sets.append({x.strip().strip("'") for x in m_in[0].split(",")})
            if m_notin:
                ne_sets.append({x.strip().strip("'") for x in m_notin[0].split(",")})
            if m_like:
                # 前缀匹配：A701% 与 A702% 互斥
                eq_sets.append({m_like[0]})

        if len(eq_sets) >= 2:
            inter = set.intersection(*eq_sets)
            if not inter:
                return True, f"字段 {f} 的取值集合互不重叠（{eq_sets}），交集恒为空"
            # 前缀互斥：A701 与 A702 都不互为前缀
            if all(len(s) == 1 for s in eq_sets):
                vals = [next(iter(s)) for s in eq_sets]
                if all(not (a.startswith(b) or b.startswith(a))
                       for a in vals for b in vals if a is not b):
                    return True, f"字段 {f} 的匹配前缀互斥（{vals}），交集恒为空"
        # 等值 AND NOT IN 同值 → 空集
        for s in eq_sets:
            for n in ne_sets:
                if s <= n:
                    return True, f"字段 {f} 同时要求等于与不等于 {sorted(s)}，交集恒为空"
    return False, ""


def build_candidates(signal_rows, max_combo=3, min_signal=0.0, max_candidates=200, max_feat=8):
    """从可映射特征里生成二/三组合候选。

    signal_rows: [{"feature_id", "name", "norm"(0-1 归一化强度)}]，按 norm 降序
    规则：只取可映射特征；两两组合 + 三三组合；跳过 cond 完全相同的对
    （如 13 已包含 2 的条件，组合起来等于单条件），以及**逻辑互斥**的对
    （如 2 纯信用 与 6 非信用，交集恒为空）。

    min_signal 默认 0：强度只用于**排序**，不用来**淘汰**。
    是否构成风险现象由 screen() 用实测算出的 lift 判定 —— 在取数之前
    用代理强度砍掉候选，等于用口径可疑的数字做筛选，与「不复用可疑口径」相悖。
    """
    usable = []
    for r in signal_rows:
        fid = r.get("feature_id")
        if fid is None:
            continue
        if not translate(fid):
            continue
        if (r.get("norm") or 0) < min_signal:
            continue
        usable.append(r)
    usable.sort(key=lambda r: -(r.get("norm") or 0))
    usable = usable[:max_feat]   # 限制组合规模，避免组合爆炸

    cands = []
    n = len(usable)
    for i in range(n):
        for j in range(i + 1, n):
            cands.append((usable[i], usable[j]))
    if max_combo >= 3:
        for i in range(n):
            for j in range(i + 1, n):
                for k in range(j + 1, n):
                    cands.append((usable[i], usable[j], usable[k]))

    out = []
    skipped_conflict = []
    for combo in cands:
        conds = [translate(c["feature_id"])["cond"] for c in combo]
        # 条件去重后不足 2 条 → 实际是单条件，不算组合
        if len({c.strip() for c in conds}) < 2:
            continue
        # 逻辑互斥 → 交集恒为空，不送库
        conflict, why = conds_conflict(conds)
        if conflict:
            skipped_conflict.append({
                "features": [c["feature_id"] for c in combo],
                "reason": why})
            continue
        out.append({
            "features": [{"feature_id": c["feature_id"], "name": c.get("name"),
                          "cond": translate(c["feature_id"])["cond"],
                          "desc": translate(c["feature_id"])["desc"]} for c in combo],
            "conds": conds,
            "combo_size": len(combo),
            "sum_norm": round(sum((c.get("norm") or 0) for c in combo), 4),
        })
    out.sort(key=lambda x: (-x["sum_norm"], -x["combo_size"]))
    return out[:max_candidates], skipped_conflict


def main():
    ap = argparse.ArgumentParser(description="风险指标组合真实求交 + 回库取数")
    ap.add_argument("--signals", help="signals.json（取特征强度）")
    ap.add_argument("--slice", default="20260831")
    ap.add_argument("--level", default="chg", choices=list(LEVELS),
                    help="口径：chg=不良生成率（默认，归因主口径）/ vch=存量不良率")
    ap.add_argument("--base-slice", default=None,
                    help="chg 口径的对比时点，如 20260331；缺省时从可用切片自动取上一个")
    ap.add_argument("--out", help="输出 combo_screen.json")
    ap.add_argument("--data-dir", help="CSV 目录；给了才真执行，否则 dry-run")
    ap.add_argument("--max-combo", type=int, default=3)
    ap.add_argument("--max-candidates", type=int, default=60)
    ap.add_argument("--top", type=int, default=40, help="最多向下游交付多少个通过筛选的现象")
    ap.add_argument("--rules", help="rules.json；用于把现象挂到归因规则上（Jaccard 匹配）")
    args = ap.parse_args()

    # 从 rules.json 提取每条规则引用的特征集合，用于「现象 ↔ 归因规则」匹配
    args.rule_features = {}
    if args.rules:
        try:
            rd = json.load(open(args.rules, encoding="utf-8"))
            # rules.json 有三个分节：manual / mined / derived
            all_rules = []
            for sect in ("manual", "mined", "derived"):
                all_rules.extend(rd.get(sect) or [])
            all_rules.extend(rd.get("rules") or [])
            for r in all_rules:
                expr = r.get("expr") or {}
                ids = expr.get("all_of") or expr.get("any_of") or r.get("members") or []
                feats = []
                for x in ids:
                    try:
                        feats.append(int(x))
                    except (TypeError, ValueError):
                        continue
                if feats:
                    args.rule_features[r.get("rule_id")] = feats
        except Exception as exc:   # noqa: BLE001
            print(f"⚠️  rules.json 解析失败（{exc}），现象不会挂到规则上")

    sig = json.load(open(args.signals, encoding="utf-8"))
    rows = []
    src = sig.get("feature_rank") or sig.get("features") or []
    if isinstance(src, dict):
        src = list(src.values())
    for u in src:
        # norm/strength 优先；否则用 metric 里最大偏离作强度代理
        norm = u.get("norm")
        if norm is None:
            norm = u.get("strength")
        if norm is None:
            metric = u.get("metric") or {}
            base = u.get("baseline") or {}
            devs = []
            for k, v in metric.items():
                b = base.get(k)
                if isinstance(v, (int, float)) and isinstance(b, (int, float)) and b:
                    devs.append(abs(v - b) / abs(b))
            norm = min(1.0, max(devs) / 3.0) if devs else 0.0
        rows.append({"feature_id": u.get("feature_id"), "name": u.get("name") or u.get("label"),
                     "norm": norm})
    cands, conflicts = build_candidates(rows, max_combo=args.max_combo,
                                        max_candidates=args.max_candidates)

    result = {
        "schema_version": SCHEMA_VERSION,
        "kind": "combo_screen",
        "slice": args.slice,
        "level": args.level,
        "base_slice": args.base_slice,
        "rate_label": "不良生成率" if args.level == "chg" else "不良率",
        "mode": "execute" if args.data_dir else "dry-run",
        "criteria": DEFAULT_SCREEN,
        "mappable_features": sorted(FEATURE_COND),
        "unmappable_features": FEATURE_UNAVAILABLE,
        "candidates_total": len(cands),
        "conflict_skipped_total": len(conflicts),
        "conflict_skipped": conflicts[:50],
        "candidates": [],
        "warnings": [],
    }

    def _emit_dry(extra_warn=None):
        for c in cands:
            c["sql"] = split_sql(c["conds"], args.slice, level=args.level,
                                 base_slice=args.base_slice)
        result["candidates"] = cands
        if extra_warn:
            result["warnings"].append(extra_warn)
        json.dump(result, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    if not args.data_dir:
        # dry-run：只产出 SQL，不产出任何数字（避免 mock 静默进报告）
        result["mode"] = "dry-run"
        _emit_dry("dry-run：未连接数据源，仅产出候选组合与 SQL，无任何实测数字")
        print(f"✅ 组合候选 {len(cands)} 个（dry-run，未取数）→ {args.out}")
        return 0

    import drill_executor as dx   # 复用同一套白名单表名 → read_parquet 替换与执行逻辑

    duckdb = dx._load_duckdb()
    if duckdb is None:
        result["warnings"].append("duckdb 未安装，无法执行；改用 dry-run 输出")
        result["mode"] = "dry-run"
        _emit_dry()
        print(f"⚠️  duckdb 未安装，组合候选 {len(cands)} 个仅产出 SQL → {args.out}")
        return 2
    con = duckdb.connect()

    # —— chg 口径必须确认对比时点真实存在，否则生成率会静默变成空值 ——
    if args.level == "chg":
        try:
            vch_glob = f"{args.data_dir.rstrip('/')}/{TABLE}/*.parquet"
            avail = [r[0] for r in con.execute(
                f"SELECT DISTINCT DATA_DAT FROM read_parquet('{vch_glob}') "
                f"ORDER BY 1 DESC LIMIT 12").fetchall()]
        except Exception as exc:   # noqa: BLE001
            result["warnings"].append(f"无法探测可用切片（{exc}），chg 口径回退为 vch")
            args.level = "chg_disabled"
            avail = []
        if args.level == "chg":
            if not args.base_slice:
                prior = [d for d in avail if d < args.slice]
                if not prior:
                    result["warnings"].append(
                        f"凭证表只有 {avail}，找不到 {args.slice} 之前的对比时点；"
                        f"不良生成率口径无法成立，本次回退为存量不良率（vch）")
                    args.level = "vch"
                else:
                    args.base_slice = prior[0]
                    result["warnings"].append(
                        f"未指定 --base-slice，自动取上一个可用切片 {args.base_slice}")
            elif args.base_slice not in avail:
                result["warnings"].append(
                    f"指定的对比时点 {args.base_slice} 在凭证表中不存在（可用 {avail}），"
                    f"回退为存量不良率（vch）")
                args.level = "vch"
    result["level"] = args.level
    result["base_slice"] = args.base_slice
    result["rate_label"] = "不良生成率" if args.level == "chg" else "不良率"

    def _q(sql):
        cols, rws, _ = dx.run_sql(con, sql, args.data_dir)
        return {r[0]: dict(zip(cols, r)) for r in rws}

    passed = []
    for c in cands:
        sql = split_sql(c["conds"], args.slice, level=args.level, base_slice=args.base_slice)
        c["sql"] = sql
        groups = _q(sql)   # {grp: row-dict}
        singles = []
        for f in c["features"]:
            sg = _q(single_sql(f["cond"], args.slice, level=args.level,
                               base_slice=args.base_slice))
            singles.append({"feature_id": f["feature_id"], "name": f["name"],
                            "cond": f["cond"], "hit": sg.get("hit"), "universe": sg.get("universe")})
        status, metrics = screen(groups.get("hit"), groups.get("nonhit"),
                                 groups.get("universe"), singles, level=args.level)
        c.update({"status": status, "metrics": metrics})
        if status == "phenomenon":
            passed.append(c)

    passed.sort(key=lambda x: -((x["metrics"] or {}).get("lift_vs_universe") or 0))

    # 把通过的现象挂到「引用同一组特征」的归因规则上，供 topic_gate 第一道校验
    # 匹配。匹配依据是特征集合的 Jaccard（>=0.6），不做文字相似度猜测。
    rule_feats = args.rule_features or {}
    for c in passed:
        cfeat = {f["feature_id"] for f in c["features"]}
        linked = []
        for rid, feats in rule_feats.items():
            rfeat = set(feats or [])
            if not rfeat or not cfeat:
                continue
            jac = len(cfeat & rfeat) / len(cfeat | rfeat)
            if jac >= 0.6:
                linked.append({"rule_id": rid, "jaccard": round(jac, 3)})
        c["linked_rules"] = [x["rule_id"] for x in linked]
        c["linked_detail"] = linked

    result["candidates"] = cands
    result["phenomena"] = passed[:args.top]
    result["phenomena_total"] = len(passed)
    reason_count = {}
    for c in cands:
        reason_count[c["status"]] = reason_count.get(c["status"], 0) + 1
    result["status_summary"] = reason_count
    json.dump(result, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"✅ 组合筛选完成：候选 {len(cands)} → 成立现象 {len(passed)}（交付 {len(result['phenomena'])}）")
    print(f"   分布：{reason_count}")
    print(f"   → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
