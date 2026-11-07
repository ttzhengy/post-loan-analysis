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

# Windows 控制台默认 GBK，直接 print 中文会抛 UnicodeEncodeError。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

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

# ============================================================ 担保方式编码
# 唯一事实来源。改这里，全项目（combo_split / mitigate / internal_external /
# drill_planner / drill_executor）都跟着变，不允许各文件再硬编码一套。
#
# 为什么必须是 0101 而不是 0100
# ----------------------------
# 曾经的写法是 GRTE_MOD_CD = '0100'，但真实数据的担保编码里**没有 0100**，
# 信用是 0101。后果不是报错，而是静默命中 0 户：所有含担保特征的组合
# 命中数为 0，screen() 判 insufficient，报告里表现为「该客群无样本」。
# 这种错最难查 —— 不报错、不告警，只是结论全空。
#
# 编码取自 core_overview_duckdb.DIMENSIONS['产品与担保']['担保方式']['label_map']，
# 那份字典是从真实数据统计出来的，是项目里唯一有实测依据的版本。
GRTE_CODE_CREDIT = "0101"                      # 信用
GRTE_CODE_MORTGAGE = "0201"                    # 抵押
GRTE_CODE_GUARANTEE = "0202"                   # 保证
GRTE_CODE_AGRI = "0308"                        # 农担
# 复合码：01010201 信用(农担)、01010202 信用(保证)、0203 抵押(农担)
GRTE_CODE_ALL = ("0101", "0201", "0202", "0308", "01010201", "01010202", "0203")

# 「纯信用」= 主担保方式为信用，且没有叠加任何抵质押/保证/农担。
# 注意复合码（01010201 信用+农担、01010202 信用+保证）本质仍是信用类，
# 但严格意义的「无第二还款来源」要求不再有第三方增信，所以这里只取 0101 本身。
GRTE_CREDIT_ONLY = "GRTE_MOD_CD = '" + GRTE_CODE_CREDIT + "'"
# 非信用：抵押/保证/农担三类主担保方式
GRTE_NON_CREDIT = (
    "GRTE_MOD_CD IN ('" + GRTE_CODE_MORTGAGE + "','" + GRTE_CODE_GUARANTEE
    + "','" + GRTE_CODE_AGRI + "')"
)

# ============================================================ 类型转换
# parquet 全列以 VARCHAR 落盘，数值字段必须显式 CAST 才能比较。
# EXD_DAYS 在 table-dict 里标的是 INT，但实际数据是 VARCHAR ——
# 字典与实际类型不一致，以实测为准。字符串比较会静默出错：
#   '100' BETWEEN '1' AND '90'  → true（首位 '1' < '9'）
#   '5'   >= 1                  → 报错或隐式转换
# 所以凡数值字段一律走这里，不要直接写裸比较。
def _int(field):
    return ("TRY_CAST(" + field + " AS BIGINT)")

def _dec(field):
    return ("TRY_CAST(" + field + " AS DOUBLE)")

EXD = _int("EXD_DAYS")
BAL = _dec("FORM_BAL_RMB")

# ============================================================ 特征 → 凭证表条件
# 只列出**能由凭证表字段直接判定**的特征。value 是 SQL 布尔表达式。
# note 写清口径，报告里会原样引用，避免读者误以为这是征信口径。
FEATURE_COND = {
    # —— 担保 / 额度结构 ——
    2: {"cond": GRTE_CREDIT_ONLY,
        "desc": "纯信用（无抵押物担保）",
        "note": "GRTE_MOD_CD=" + GRTE_CODE_CREDIT + "（信用），凭证表担保方式维度"},
    13: {"cond": GRTE_CREDIT_ONLY + " AND " + BAL + " >= 500000",
         "desc": "大额纯信用（单笔余额≥50万且无抵押）",
         "note": "GRTE_MOD_CD=" + GRTE_CODE_CREDIT + " 且 FORM_BAL_RMB≥50万"},
    7: {"cond": BAL + " >= 300000",
        "desc": "单笔大额（余额≥30万）",
        "note": "以凭证余额作授信规模的代理变量；凭证表无授信额度字段"},
    6: {"cond": GRTE_NON_CREDIT,
        "desc": "非信用类担保（保证/抵押/质押）",
        "note": "GRTE_MOD_CD∈{0201,0202,0308}，用于对照信用类"},

    # —— 产品 / 业务品种 ——
    12: {"cond": "BUS_BREED_CD LIKE 'A701%'",
         "desc": "特定品种 A701（小额信用类）",
         "note": "BUS_BREED_CD 前缀匹配，品种字典见 table-dict"},

    # —— 期限 / 发放时点 ——
    30: {"cond": "LN_DAT >= '20250101'",
         "desc": "近两年新发放（2025 年起）",
         "note": "LN_DAT 借款日期；经营年限无字段，用放款时点作代理"},

    # —— 逾期与还款 ——
    44: {"cond": EXD + " >= 1",
         "desc": "曾出现逾期（EXD_DAYS≥1）",
         "note": "逾期是五级分类的前置信号，非不良定义本身，可用于归因；"
                 "EXD_DAYS 以 VARCHAR 落盘，比较前显式转整数"},
    43: {"cond": EXD + " BETWEEN 1 AND 90",
         "desc": "短期逾期已出现但未达 90 天",
         "note": "逾期 1–90 天，风险信号出现但处置未跟上；"
                 "EXD_DAYS 以 VARCHAR 落盘，必须 CAST 后比较，"
                 "否则字符串比较会把 '100' 判进 1~90 区间"},

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
    """单条件 → 客户级 hit / nonhit / universe 三行。

    必须带 nonhit：screen() 需要三组才能做口径自洽校验（hit+nonhit=universe）
    与显著性检验。之前只给 hit / universe 两组，导致单条件在 screen 里
    一律因「缺少分组结果」判 insufficient —— 单条件现象通道等于没接通。
    """
    body = "\nUNION ALL\n".join([
        _agg("hit", "hit_flag = 1"),
        _agg("nonhit", "hit_flag = 0"),
        _agg("universe"),
    ])
    return (_cte([cond], slice_v, table, level, base_slice)
            + "SELECT * FROM (\n" + body + "\n) t\n"
            + "ORDER BY CASE grp WHEN 'hit' THEN 1 WHEN 'nonhit' THEN 2 ELSE 3 END")


# ============================================================ 现象成立性判定

DEFAULT_SCREEN = {
    "min_hit_n": 200,          # 命中客户数下限
    "min_hit_share": 0.002,    # 命中占全辖比下限（0.2%）
    "lift_floor": 1.5,         # 相对基准（父群优先）的 lift 下限
    "singleton_margin": 1.15,  # 组合 lift 应至少比最强单条件 lift 高 15%
    "nonhit_max_lift": 1.3,    # 对照组的 lift 上限，太高说明条件不具区分性
    "max_p_value": 0.05,       # 与基准组差异的双侧检验 p 值上限
    # 命中组占比超过此值时，全辖已被命中组自身拉高，不能再作基线。
    # 此时改用非命中组 —— 换对照组，不是降门槛。
    "share_baseline_max": 0.25,
}


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _z_test_two_prop(p1, n1, p2, n2):
    """两比例差异检验（双侧 z 检验），返回 p 值。

    为什么必须要
    ------------
    固定「lift ≥ 1.5」这种门槛完全忽略样本量：不良率 3~5% 时，
    30 个样本只有 1~2 个坏样本，lift 再高也是噪声。
    改用 z 检验给 p 值，配合样本量与绝对差一起判断。
    """
    import math
    if not n1 or not n2 or n1 <= 0 or n2 <= 0:
        return None
    p_pool = (p1 * n1 + p2 * n2) / (n1 + n2)
    if p_pool <= 0 or p_pool >= 1:
        return None
    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    if se <= 0:
        return None
    z = (p1 - p2) / se
    # 双侧：2 * (1 - Φ(|z|))
    return round(math.erfc(abs(z) / math.sqrt(2)), 6)


def screen(hit, nonhit, universe, singles, cfg=None, level="vch", parent=None,
           is_single=False):
    """判定「这是不是一个真正的风险现象」。

    返回 status ∈ {phenomenon, weak_phenomenon, insufficient, broken}
      broken      : 口径不自洽（hit+nonhit≠universe，或命中超全辖）→ 证据作废
      insufficient: 样本不足 / 统计不显著
      weak_phenomenon: 有样本但 lift 不够，或组合未超过最强单条件
      phenomenon  : 通过

    比较基准：父群优先，全辖为辅
    ------------------------------
    原实现只用「相对全辖」的 lift。全辖率本身是混合群体的加权结果，
    任何子群相对它都会被稀释 —— 全辖 32% 时，子群甚至可能全部落在
    1.5 倍以下，而子群之间的差异其实很显著。

    正确基准是「去掉最后一个条件的父群」：
      「接续贷 + 循环额度」应该跟「接续贷 + 非循环额度」或「接续贷」比，
      而不是跟全辖比。
    `parent` 传入 {"n","npl_rate"} 时按父群判定；缺省时退回全辖口径
    （保持对已有调用方的兼容），并在 metrics 里标明用了哪个基准。
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

    # 基线选择：父群 > 非命中组（大占比时）> 全辖
    #
    # 为什么不能无条件用全辖
    # ---------------------
    # 全辖 = 命中组 + 非命中组。当命中组占比很高时，全辖率被命中组自己拉高，
    # lift 变成「自己比自己」，必然趋近 1。实测过一个占比 38.9% 的客群：
    # 命中组 7.45%、非命中组 1.83%（真实差距 4.08 倍），但相对全辖只有 1.50 倍，
    # 恰好卡在门槛上被判 weak_phenomenon。这不是「没有风险」，是**基线选错**。
    # 命中组占比超过 share_baseline_max 时，全辖已不可作为对照，
    # 改用非命中组 —— 换的是正确的对照组，不是调低门槛。
    par_n = _num((parent or {}).get("n"))
    par_rate = _num((parent or {}).get("npl_rate"))
    use_parent = bool(par_n and par_rate and par_n > 0)
    share = uh / uu if uu else 0
    if use_parent:
        base_rate, base_n, base_name = par_rate, par_n, "父群"
    elif share > cfg["share_baseline_max"] and non_rate:
        # 命中组占比过高，全辖被自身污染，退到非命中组做基线
        base_rate, base_n, base_name = non_rate, un, "非命中组"
    else:
        base_rate, base_n, base_name = uni_rate, uu, "全辖"
    base_lift = (hit_rate / base_rate) if base_rate else None
    # 与基准组的显著性：父群口径下，对照 = 父群去掉命中部分
    if use_parent:
        assert par_n is not None and par_rate is not None
        cmp_n = max(par_n - uh, 0)
        cmp_bad_rate = ((par_rate * par_n - hit_rate * uh) / cmp_n) if cmp_n > 0 else None
    else:
        cmp_n, cmp_bad_rate = un, non_rate
    p_value = (_z_test_two_prop(hit_rate, uh, cmp_bad_rate, cmp_n)
               if (cmp_bad_rate is not None and cmp_n and cmp_n > 0) else None)

    single_lifts = []
    for s in singles or []:
        r = _num((s.get("hit") or {}).get("npl_rate"))
        ur = _num((s.get("universe") or {}).get("npl_rate")) or uni_rate
        if r is not None and ur:
            # 单条件 lift 必须用与组合**相同**的基线口径，否则「增量」是两个
            # 不同分母的比值，毫无意义。实测：组合用非命中组算出 4.08 倍，
            # 单条件却用全辖算出 1.50 倍，增量算成 1.00，于是把一个真实
            # 4 倍差距的现象判成「叠加没有增量」。
            single_lifts.append({
                "feature_id": s.get("feature_id"), "name": s.get("name"),
                "cond": s.get("cond"),
                "lift": r / base_rate if base_rate else None,
                "lift_vs_universe": r / ur,
                "n": (s.get("hit") or {}).get("n")})
    single_lifts.sort(key=lambda x: -(x["lift"] or 0))
    best_single = single_lifts[0] if single_lifts else None
    # 同一口径下比较组合 vs 最强单条件
    incremental = (base_lift / best_single["lift"]
                   if (best_single and best_single["lift"] and base_lift) else None)

    metrics = {
        "level": level,
        "hit_n": uh, "nonhit_n": un, "universe_n": uu, "hit_share": round(share, 6),
        "hit_rate": round(hit_rate, 6), "nonhit_rate": round(non_rate, 6),
        "universe_rate": round(uni_rate, 6),
        "lift_vs_nonhit": round(lift, 4) if lift else None,
        "lift_vs_universe": round(uni_lift, 4) if uni_lift else None,
        "baseline_used": base_name,
        "baseline_rate": round(base_rate, 6) if base_rate else None,
        "lift_vs_baseline": round(base_lift, 4) if base_lift else None,
        "p_value": p_value,
        "singles": single_lifts, "best_single": best_single,
        "incremental_lift": round(incremental, 4) if incremental else None,
    }

    rate_word = "生成率" if level == "chg" else "不良率"
    if uh < cfg["min_hit_n"] or share < cfg["min_hit_share"]:
        return "insufficient", {**metrics,
                                "reason": f"命中 {uh:.0f} 户（占比 {share:.2%}）低于门槛 "
                                          f"{cfg['min_hit_n']} 户 / {cfg['min_hit_share']:.1%}"}
    # 统计显著性：p 值太大说明差异可能是噪声，不能当现象
    if p_value is not None and p_value > cfg["max_p_value"]:
        return "insufficient", {**metrics,
                                "reason": f"与{base_name}的差异不显著（p={p_value:.3f} > "
                                          f"{cfg['max_p_value']}），样本不足以支撑该现象"}
    if base_lift is None or base_lift < cfg["lift_floor"]:
        return "weak_phenomenon", {**metrics,
                                   "reason": f"组合{rate_word} {hit_rate:.2%} 为{base_name}的 "
                                             f"{base_lift:.2f} 倍，低于门槛 {cfg['lift_floor']}，"
                                             f"不构成独立风险现象"}
    if incremental is not None and best_single and incremental < cfg["singleton_margin"]:
        # 只有真正的组合才做「组合 vs 单条件」增量检验。
        # 单条件候选拿自己跟自己比，增量恒为 1.0，必然被判「没有增量」，
        # 那会让「自身强度达标」的单条件永远出不来。用 is_single 显式区分，
        # 不靠 singles 的长度猜（可能是两成员但其中一个冗余）。
        if not is_single:
            return "weak_phenomenon", {**metrics,
                                       "reason": f"组合相对{base_name}的 lift {base_lift:.2f} 仅为最强单条件"
                                                 f"「{best_single['name']}」({best_single['lift']:.2f}) 的 "
                                                 f"{incremental:.2f} 倍，叠加没有带来增量，"
                                                 f"该现象由单条件主导，不成立为组合现象"}
    return "phenomenon", metrics


# ============================================================ 组合生成

def conds_subsumed(conds):
    """判断组合里是否存在条件蕴含（一条完全包含另一条）。

    为什么必须判
    ------------
    「纯信用且余额≥50万」(13) 与「余额≥30万」(7) 求交后**等于 13 本身** ——
    7 被 13 完全蕴含。这类组合送进库白跑一遍，拿回的数字与 13 完全相同，
    然后被判「叠加无增量」，看起来像发现了什么，其实只是重复计算。

    实测（planted 夹具）：13+7 与 13+2 的 hit_n 都恰好等于 13 单独的 20247，
    lift 恒为 1.00，白白消耗 4 次查询。

    判定方式：同字段上的阈值型条件（>= / > / <= / <）比较边界；
    若一条的可行域包含另一条，则后者冗余。
    只做同字段单条件的包含判断，不做通用布尔求解。
    """
    import re
    by_field = {}

    def _atoms(c):
        """把条件拆成若干原子约束 (字段, 算子, 值)。

        复合条件「A = '1' AND X >= 5」必须拆开逐个记，否则只取到第一个约束，
        「13 包含 7」这类蕴含就识别不出来。
        字段名允许被 TRY_CAST(...AS DOUBLE) 包裹。
        """
        out = []
        # 阈值约束要处理两种写法：
        #   X >= 5                           → 直接匹配
        #   TRY_CAST(X AS DOUBLE) >= 5       → 字段名被 CAST 包裹
        for m in re.finditer(r"CAST\s*\(\s*([A-Z_]+)\s+AS\s+[A-Z_]+[^)]*\)\s*"
                             r"(>=|<=|!=|>|<)\s*([0-9.]+)", c.upper()):
            out.append((m.group(1), m.group(2), float(m.group(3))))
        stripped = re.sub(r"CAST\s*\(\s*[A-Z_]+\s+AS\s+[A-Z_]+[^)]*\)", " ", c.upper())
        for m in re.finditer(r"([A-Z_]+)\s*(>=|<=|!=|>|<)\s*([0-9.]+)", stripped):
            out.append((m.group(1), m.group(2), float(m.group(3))))
        for m in re.finditer(r"([A-Z_]+)\s*(?:=\s*'([^']*)'|(\bIN\b)\s*\(([^)]+)\))",
                             c.upper()):
            if m.group(2) is not None:
                out.append((m.group(1), "=", m.group(2)))
            elif m.group(3):
                vals = tuple(v.strip().strip("'") for v in m.group(4).split(","))
                out.append((m.group(1), "IN", vals))
        return out

    atoms = [(c, a) for c in conds for a in _atoms(c)]
    for _c, (f, op, v) in atoms:
        by_field.setdefault(f, []).append((op, v, _c))

    for _f, items in by_field.items():
        if len(items) < 2:
            continue
        for i, (op1, v1, c1) in enumerate(items):
            for j, (op2, v2, c2) in enumerate(items):
                if i == j or c1 == c2:
                    continue
                if op1 == "=" and op2 == "=":
                    if v1 == v2:
                        return True, "两条条件含相同字段取值约束，后者冗余"
                    continue
                if op1 == "IN" and op2 == "IN":
                    if isinstance(v1, tuple) and isinstance(v2, tuple) and set(v2) <= set(v1):
                        return True, f"条件「{c2}」的取值集合被「{c1}」包含"
                    continue
                if op1 == "IN" and op2 == "=":
                    if isinstance(v1, tuple) and v2 in v1:
                        return True, f"条件「{c2}」的取值被「{c1}」包含"
                    continue
                if not isinstance(v1, float) or not isinstance(v2, float):
                    continue
                # c1 的可行域是否包含 c2
                lo1 = -float("inf") if op1 in (">", ">=") else v1
                hi1 = float("inf") if op1 in ("<", "<=") else v1
                lo2 = -float("inf") if op2 in (">", ">=") else v2
                hi2 = float("inf") if op2 in ("<", "<=") else v2
                if lo1 <= lo2 and hi1 >= hi2:
                    return True, f"条件「{c2}」的可行域被「{c1}」完全包含"
    return False, ""


def conds_conflict(conds):
    """判断一组条件是否逻辑互斥（交集恒为空）。

    为什么必须判
    ------------
    特征 2（纯信用 GRTE_MOD_CD='0101'）与特征 6（非信用
    GRTE_MOD_CD IN ('0201','0202','0308')）是两个互斥集合，
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
                # 排序后再格式化：set 的迭代顺序受哈希随机化影响，
                # 不排序会导致同样的输入每次生成不同的提示文字，输出不可复现。
                shown = [sorted(s) for s in eq_sets]
                return True, f"字段 {f} 的取值集合互不重叠（{shown}），交集恒为空"
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
    single_candidates = {}   # feature_id → 已算过的单条件结果，避免重复取数
    for c in cands:
        sql = split_sql(c["conds"], args.slice, level=args.level, base_slice=args.base_slice)
        c["sql"] = sql
        groups = _q(sql)   # {grp: row-dict}
        singles = []
        for f in c["features"]:
            sg = single_candidates.get(f["feature_id"])
            if sg is None:
                sg = _q(single_sql(f["cond"], args.slice, level=args.level,
                                   base_slice=args.base_slice))
                single_candidates[f["feature_id"]] = sg
            singles.append({"feature_id": f["feature_id"], "name": f["name"],
                            "cond": f["cond"], "hit": sg.get("hit"),
                            "nonhit": sg.get("nonhit"), "universe": sg.get("universe")})
        # 父群基线：去掉最后一个条件后的客群（组合 size>=2 才有意义）。
        # 「接续贷 + 循环额度」该跟「接续贷」比，而不是跟全辖比 ——
        # 全辖率是混合群体的加权结果，会把子群差异稀释掉。
        parent = None
        if len(c["conds"]) >= 2:
            try:
                p_sql = split_sql(c["conds"][:-1], args.slice, level=args.level,
                                  base_slice=args.base_slice)
                p_groups = _q(p_sql)
                parent = p_groups.get("hit")     # 父群条件全命中即父群整体
            except Exception:
                parent = None
        status, metrics = screen(groups.get("hit"), groups.get("nonhit"),
                                 groups.get("universe"), singles, level=args.level,
                                 parent=parent)
        c.update({"status": status, "metrics": metrics})
        if status == "phenomenon":
            passed.append(c)

    # ---------------- 单条件现象通道 ----------------
    # 为什么需要这一段
    # --------------
    # 候选池只有 2 阶和 3 阶组合，**没有任何单条件候选**。于是出现这种情况：
    # 单条件「纯信用且≥50万」自身就有 4 倍强度，但它只能作为某个组合的成员
    # 出现；而组合一旦包含一个冗余条件（如「余额≥30万」被「≥50万」蕴含），
    # incremental_lift 就等于 1.0，被判「叠加无增量，由单条件主导」而否决。
    # 结果是：**越强的单条件，越容易被判成「没有组合增量」，越出不来**。
    # 这不是筛选严格，是把真实风险挡在门外。单条件强度达标时也应作为现象成立。
    covered = {tuple(sorted(f["feature_id"] for f in c["features"])) for c in passed}
    for fid, sg in single_candidates.items():
        if (fid,) in covered:
            continue
        name, cond = None, None
        for cc in cands:
            for f in cc["features"]:
                if f["feature_id"] == fid:
                    name, cond = f["name"], f["cond"]
                    break
            if name:
                break
        if not cond:
            continue
        try:
            st, m = screen(sg.get("hit"), sg.get("nonhit"), sg.get("universe"),
                           [{"feature_id": fid, "name": name, "cond": cond,
                             "hit": sg.get("hit"), "nonhit": sg.get("nonhit"),
                             "universe": sg.get("universe")}],
                           level=args.level, is_single=True)
        except Exception:
            continue
        if st != "phenomenon":
            continue
        # 单条件没有「组合增量」一说，把口径标明，避免下游误读成组合现象
        m = {**m, "phenomenon_kind": "single",
             "reason": f"单条件自身{('生成率' if args.level == 'chg' else '不良率')} "
                       f"即达门槛，不依赖组合叠加"}
        passed.append({"features": [{"feature_id": fid, "name": name, "cond": cond}],
                       "conds": [cond], "combo_size": 1,
                       "sql": single_sql(cond, args.slice, level=args.level,
                                         base_slice=args.base_slice),
                       "status": "phenomenon", "metrics": m})

    passed.sort(key=lambda x: -((x["metrics"] or {}).get("lift_vs_baseline")
                                or (x["metrics"] or {}).get("lift_vs_universe") or 0))

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
