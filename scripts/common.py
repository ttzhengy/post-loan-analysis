#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""common.py — B 组共享工具（纯标准库）

职责：
1. 表字典加载（shared/table-dict.json 是白名单唯一事实来源）
2. 合成样例数据（signals / attribution），供各脚本 --selftest 与 --mock-db 使用
3. 业务化清洗：报告面向客户经理，禁止出现表名/字段名/机构编码/客户经理ID
4. 数值格式化与 JSON 读写

不得引入第三方库。
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

# ---------------------------------------------------------------- 路径
ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / "shared"
TABLE_DICT_PATH = SHARED / "table-dict.json"
CONTRACT_PATH = ROOT / "references" / "INTERFACES.md"  # 中间产物接口契约

# ---------------------------------------------------------------- IO


def read_json(path):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"输入文件不存在: {p}")
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return str(p)


# ---------------------------------------------------------------- 表字典


class TableDict:
    """table-dict.json 的只读封装。白名单唯一事实来源。"""

    def __init__(self, path=None):
        raw = read_json(path or TABLE_DICT_PATH)
        self.source = raw.get("source", "")
        self.tables = raw.get("tables", {})
        # 表名大写规范键
        self._norm = {}
        for t, cols in self.tables.items():
            self._norm[t.upper()] = {
                "table": t,
                "fields": {c["field"].upper(): c for c in cols},
                "order": [c["field"] for c in cols],
            }

    def has_table(self, name):
        return name.upper() in self._norm

    def canonical(self, name):
        hit = self._norm.get(name.upper())
        return hit["table"] if hit else None

    def has_column(self, table, col):
        hit = self._norm.get(table.upper())
        if not hit:
            return False
        return col.upper() in hit["fields"]

    def field_cn(self, table, col):
        hit = self._norm.get(table.upper())
        if not hit:
            return ""
        c = hit["fields"].get(col.upper())
        return c.get("cn", "") if c else ""

    def all_columns(self):
        """全部表全部字段的大写集合（用于「全表共有列」判定，如 DATA_DAT/CUST_NO）"""
        s = set()
        for hit in self._norm.values():
            s.update(hit["fields"].keys())
        return s

    def whitelist_for_prompt(self, max_tables=None, priority=None):
        """给 LLM 的字段级白名单：[{table, cn, fields:[{field, cn, type}]}]

        priority: 表名列表，排在前面（LLM 注意力有限，优先给主表）
        """
        names = list(self.tables.keys())
        if priority:
            pri = [p.upper() for p in priority]
            names.sort(key=lambda t: (pri.index(t.upper()) if t.upper() in pri else 999,
                                      -len(self.tables[t])))
        if max_tables:
            names = names[:max_tables]
        out = []
        for t in names:
            out.append({
                "table": t,
                "fields": [{"field": c["field"], "cn": c.get("cn", ""), "type": c.get("type", "")}
                           for c in self.tables[t]],
            })
        return out


# 主表（LLM 写 SQL 时最可能用到的），用于提示词内排序
PRIMARY_TABLES = [
    "G_00PF_PEAS_LN_VCH_DV",
    "G_00PF_IDV_LN_VCH_DV",
    "G_00PL_PEAS_DOC_INFO_DV",
    "G_00PL_IDV_LN_ARG_EXD_DV",
    "G_00PL_IDV_LN_BILL_AMT",
    "G_00PL_IDV_LN_CUST_ACARD_SCRE_DV",
    "B_00FT_PEAS_LN_DPSE_TASK_DTAL",
    "S_00PL_IDV_LN_GRTE_RLN",
    "S_00PF_PEAS_LN_RSK_ORG_C4",
    "S_00PF_PEAS_LN_CCE_RSK_PSE_ORG_C4",
    "S_00PF_PEAS_MGR_LN_RISK_C4",
    "S_00PF_IDV_DP_CUST_SUM",
    "S_00PF_IDV_CUST_FA_SUM",
    "S_00PF_SA_ACCT_TR_CUST_SUM",
    "G_00PF_IDV_LN_VCH_CAN_LQDT_SECS_DV",
]


# ---------------------------------------------------------------- 业务化清洗

# 表名形态：G_00PF_PEAS_LN_VCH_DV / S_00PF_PEAS_LN_RSK_ORG_C4
_TABLE_RE = re.compile(r"\b[A-Z][A-Z0-9]{0,3}_[A-Z0-9]{2,}(?:_[A-Z0-9]+){1,}\b")
_FIELD_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,}(?:_[A-Z0-9]+)+\b")
# 常见字段名（去技术化的最小词典，覆盖高频字段）
_COMMON_FIELDS = {
    "BUS_BREED_CD", "RSK_CLS_CD", "FORM_BAL_RMB", "EXD_DAYS", "BILL_EXD_DAYS",
    "CUST_NO", "ID_CARD_NO", "MAGR_CD", "DATA_DAT", "FORM_NO", "CTRT_NO",
    "GRTE_MOD_CD", "LN_AMT_RMB", "SCRE", "LN_DAT", "MATU_DAT", "RSK_LINE_TYP",
    "PEAS_LN_UHLTH_RATE", "LN_UHLTH_RATE", "EXD_CAP", "LN_USE_CD",
}
# 机构编码 / 客户经理ID / 哈希
_ID_PATTERNS = [
    (re.compile(r"\b\d{6,}(?:0\d)?\b"), "〔机构编码〕"),
    (re.compile(r"\b[0-9a-f]{16,}\b", re.I), "〔哈希值〕"),
    (re.compile(r"\b[A-Z]{3,5}\d{6,}\b"), "〔机构编码〕"),
]


def sanitize_text(text, td=None):
    """把文本里可能出现的表名/字段名/编码替换成业务化占位。

    返回 (清洗后文本, 命中列表)。命中列表用于审计（不静默：交给调用方决定记录或告警）。
    判定顺序：已知表名 > 已知字段名 > 形态兜底，避免 RSK_CLS_CD 这类字段被误判成表。
    """
    if not isinstance(text, str):
        return text, []
    hits = []

    known_tables = set(td.tables.keys()) if td is not None else set()
    known_fields = set()
    if td is not None:
        known_fields = td.all_columns()

    def _sub(m):
        tok = m.group(0)
        up = tok.upper()
        if up in known_tables:
            hits.append({"type": "table_name", "value": tok})
            return "〔业务数据表〕"
        if up in known_fields or up in _COMMON_FIELDS:
            hits.append({"type": "field_name", "value": tok})
            return "〔字段〕"
        # 形态像表名（含 4 个以上下划线段）才兜底判表；否则保留
        if tok.count("_") >= 3:
            hits.append({"type": "table_name", "value": tok})
            return "〔业务数据表〕"
        return tok

    out = text
    # 先把已知表名整词替换（优先级最高，避免被字段正则吃掉）
    for t in sorted(known_tables, key=len, reverse=True):
        pat = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(t) + r"(?![A-Za-z0-9_])")
        if pat.search(out):
            hits.append({"type": "table_name", "value": t, "count": len(pat.findall(out))})
            out = pat.sub("〔业务数据表〕", out)

    out = _FIELD_RE.sub(_sub, out)
    for pat, rep in _ID_PATTERNS:
        for m in pat.finditer(out):
            hits.append({"type": "id_like", "value": m.group(0)})
        out = pat.sub(rep, out)
    return out, hits


# ---------------------------------------------------------------- 数值


def pct(x, nd=2):
    try:
        return f"{float(x) * 100:.{nd}f}%"
    except (TypeError, ValueError):
        return "—"


def pp(x, nd=2):
    try:
        return f"{float(x) * 100:+.{nd}f}pp"
    except (TypeError, ValueError):
        return "—"


def safe_div(a, b):
    try:
        a = float(a)
        b = float(b)
        return a / b if b else None
    except (TypeError, ValueError):
        return None


def rnd(x, nd=4):
    if x is None:
        return None
    if isinstance(x, bool):
        return x
    try:
        v = float(x)
    except (TypeError, ValueError):
        return x
    if math.isnan(v) or math.isinf(v):
        return None
    return round(v, nd)


# ---------------------------------------------------------------- 合成样例数据


def synth_signals():
    """合成 signals.json（对应 CONTRACT 第 2 节），用于 --selftest/--mock-db。

    刻意包含：
    - 8 个维度，部分档位恶化明显（信用/小额/脱贫户/存量老资产）
    - 线索矩阵里若干高 lift 线索（资金往来、替还、房产异常）
    - 特征命中（零散获客/信用占比/低评分/贷后任务未办结/接续）
    """
    return {
        "schema_version": "3.0",
        "slice": "20260831",
        "overall": {"bal": 8_640_000_000, "npl_bal": 268_000_000, "npl_rate": 0.03102,
                    "cnt": 156_800, "cust_cnt": 121_400, "person_cnt": 118_900},
        "dimensions": {
            "guarantee": {
                "name": "担保方式", "stage": "贷前",
                "buckets": [
                    {"bucket": "信用", "bal": 1_420_000_000, "npl_bal": 82_300_000, "npl_rate": 0.05796,
                     "npl_share": 0.3071, "offset_pp": 0.02694, "reference_ctl": {"normal_share": 0.148, "npl_share": 0.307}, "valid": True},
                    {"bucket": "保证", "bal": 2_180_000_000, "npl_bal": 71_200_000, "npl_rate": 0.03266,
                     "npl_share": 0.2657, "offset_pp": 0.00164, "reference_ctl": {"normal_share": 0.256, "npl_share": 0.266}, "valid": True},
                    {"bucket": "抵押", "bal": 3_960_000_000, "npl_bal": 96_100_000, "npl_rate": 0.02427,
                     "npl_share": 0.3586, "offset_pp": -0.00675, "reference_ctl": {"normal_share": 0.472, "npl_share": 0.359}, "valid": True},
                    {"bucket": "农担", "bal": 1_080_000_000, "npl_bal": 18_400_000, "npl_rate": 0.01704,
                     "npl_share": 0.0687, "offset_pp": -0.01398, "reference_ctl": {"normal_share": 0.124, "npl_share": 0.069}, "valid": True},
                ],
            },
            "amount_band": {
                "name": "额度分段", "stage": "贷前",
                "buckets": [
                    {"bucket": "5万以下", "bal": 980_000_000, "npl_bal": 79_900_000, "npl_rate": 0.08153,
                     "npl_share": 0.2981, "offset_pp": 0.05051, "reference_ctl": {"normal_share": 0.099, "npl_share": 0.298}, "valid": True},
                    {"bucket": "5-10万", "bal": 1_760_000_000, "npl_bal": 61_300_000, "npl_rate": 0.03483,
                     "npl_share": 0.2287, "offset_pp": 0.00381, "reference_ctl": {"normal_share": 0.203, "npl_share": 0.229}, "valid": True},
                    {"bucket": "10-30万", "bal": 3_100_000_000, "npl_bal": 82_400_000, "npl_rate": 0.02658,
                     "npl_share": 0.3075, "offset_pp": -0.00444, "reference_ctl": {"normal_share": 0.372, "npl_share": 0.308}, "valid": True},
                    {"bucket": "30万以上", "bal": 2_800_000_000, "npl_bal": 44_400_000, "npl_rate": 0.01586,
                     "npl_share": 0.1657, "offset_pp": -0.01516, "reference_ctl": {"normal_share": 0.326, "npl_share": 0.166}, "valid": True},
                ],
            },
            "cust_type": {
                "name": "主体类型", "stage": "贷前",
                "buckets": [
                    {"bucket": "脱贫户", "bal": 640_000_000, "npl_bal": 33_500_000, "npl_rate": 0.05234,
                     "npl_share": 0.1250, "offset_pp": 0.02132, "reference_ctl": {"normal_share": 0.068, "npl_share": 0.125}, "valid": True},
                    {"bucket": "一般农户", "bal": 7_000_000_000, "npl_bal": 214_000_000, "npl_rate": 0.03057,
                     "npl_share": 0.7985, "offset_pp": -0.00045, "reference_ctl": {"normal_share": 0.858, "npl_share": 0.799}, "valid": True},
                    {"bucket": "新型经营主体", "bal": 1_000_000_000, "npl_bal": 20_500_000, "npl_rate": 0.0205,
                     "npl_share": 0.0765, "offset_pp": -0.01052, "reference_ctl": {"normal_share": 0.074, "npl_share": 0.076}, "valid": True},
                ],
            },
            "year": {
                "name": "放款年份", "stage": "贷后",
                "buckets": [
                    {"bucket": "2023年及以前", "bal": 1_020_000_000, "npl_bal": 61_400_000, "npl_rate": 0.0602,
                     "npl_share": 0.2291, "offset_pp": 0.02918, "reference_ctl": {"normal_share": 0.104, "npl_share": 0.229}, "valid": True},
                    {"bucket": "2024年", "bal": 2_260_000_000, "npl_bal": 81_900_000, "npl_rate": 0.03624,
                     "npl_share": 0.3056, "offset_pp": 0.00522, "reference_ctl": {"normal_share": 0.256, "npl_share": 0.306}, "valid": True},
                    {"bucket": "2025年", "bal": 3_120_000_000, "npl_bal": 79_200_000, "npl_rate": 0.02538,
                     "npl_share": 0.2955, "offset_pp": -0.00564, "reference_ctl": {"normal_share": 0.372, "npl_share": 0.296}, "valid": True},
                    {"bucket": "2026年", "bal": 2_240_000_000, "npl_bal": 45_500_000, "npl_rate": 0.02031,
                     "npl_share": 0.1698, "offset_pp": -0.01071, "reference_ctl": {"normal_share": 0.268, "npl_share": 0.170}, "valid": True},
                ],
            },
            "industry": {
                "name": "投向行业", "stage": "贷前",
                "buckets": [
                    {"bucket": "生猪养殖", "bal": 720_000_000, "npl_bal": 43_600_000, "npl_rate": 0.06056,
                     "npl_share": 0.1627, "offset_pp": 0.02954, "reference_ctl": {"normal_share": 0.077, "npl_share": 0.163}, "valid": True},
                    {"bucket": "粮食种植", "bal": 2_900_000_000, "npl_bal": 67_400_000, "npl_rate": 0.02324,
                     "npl_share": 0.2515, "offset_pp": -0.00778, "reference_ctl": {"normal_share": 0.349, "npl_share": 0.251}, "valid": True},
                    {"bucket": "非农经营", "bal": 1_780_000_000, "npl_bal": 68_900_000, "npl_rate": 0.03871,
                     "npl_share": 0.2571, "offset_pp": 0.00769, "reference_ctl": {"normal_share": 0.198, "npl_share": 0.257}, "valid": True},
                    {"bucket": "其他", "bal": 3_240_000_000, "npl_bal": 88_100_000, "npl_rate": 0.02719,
                     "npl_share": 0.3287, "offset_pp": -0.00383, "reference_ctl": {"normal_share": 0.376, "npl_share": 0.329}, "valid": True},
                ],
            },
            "score": {
                "name": "评分分段", "stage": "贷前",
                "buckets": [
                    {"bucket": "<600", "bal": 540_000_000, "npl_bal": 48_200_000, "npl_rate": 0.08926,
                     "npl_share": 0.1799, "offset_pp": 0.05824, "reference_ctl": {"normal_share": 0.053, "npl_share": 0.180}, "valid": True},
                    {"bucket": "600-679", "bal": 2_140_000_000, "npl_bal": 77_300_000, "npl_rate": 0.03612,
                     "npl_share": 0.2884, "offset_pp": 0.0051, "reference_ctl": {"normal_share": 0.253, "npl_share": 0.288}, "valid": True},
                    {"bucket": ">=680", "bal": 5_960_000_000, "npl_bal": 142_500_000, "npl_rate": 0.02391,
                     "npl_share": 0.5317, "offset_pp": -0.00711, "reference_ctl": {"normal_share": 0.694, "npl_share": 0.532}, "valid": True},
                ],
            },
            "term": {
                "name": "期限", "stage": "贷前",
                "buckets": [
                    {"bucket": "1年及以内", "bal": 5_180_000_000, "npl_bal": 140_200_000, "npl_rate": 0.02707,
                     "npl_share": 0.5231, "offset_pp": -0.00395, "reference_ctl": {"normal_share": 0.612, "npl_share": 0.523}, "valid": True},
                    {"bucket": "1-3年", "bal": 2_760_000_000, "npl_bal": 91_600_000, "npl_rate": 0.03319,
                     "npl_share": 0.3418, "offset_pp": 0.00217, "reference_ctl": {"normal_share": 0.316, "npl_share": 0.342}, "valid": True},
                    {"bucket": "3年以上", "bal": 700_000_000, "npl_bal": 36_200_000, "npl_rate": 0.05171,
                     "npl_share": 0.1351, "offset_pp": 0.02069, "reference_ctl": {"normal_share": 0.072, "npl_share": 0.135}, "valid": True},
                ],
            },
            "org": {
                "name": "机构", "stage": "贷后",
                "buckets": [
                    {"bucket": "县域机构A", "bal": 1_240_000_000, "npl_bal": 61_200_000, "npl_rate": 0.04935,
                     "npl_share": 0.2284, "offset_pp": 0.01833, "reference_ctl": {"normal_share": 0.129, "npl_share": 0.228}, "valid": True},
                    {"bucket": "县域机构B", "bal": 1_680_000_000, "npl_bal": 55_400_000, "npl_rate": 0.03298,
                     "npl_share": 0.2067, "offset_pp": 0.00196, "reference_ctl": {"normal_share": 0.181, "npl_share": 0.207}, "valid": True},
                    {"bucket": "县域机构C", "bal": 2_900_000_000, "npl_bal": 82_700_000, "npl_rate": 0.02852,
                     "npl_share": 0.3086, "offset_pp": -0.0025, "reference_ctl": {"normal_share": 0.352, "npl_share": 0.309}, "valid": True},
                    {"bucket": "县域机构D", "bal": 2_820_000_000, "npl_bal": 68_700_000, "npl_rate": 0.02436,
                     "npl_share": 0.2563, "offset_pp": -0.00666, "reference_ctl": {"normal_share": 0.338, "npl_share": 0.256}, "valid": True},
                ],
            },
            "use": {
                "name": "贷款用途", "stage": "贷前",
                "buckets": [
                    {"bucket": "生产经营", "bal": 6_900_000_000, "npl_bal": 198_000_000, "npl_rate": 0.0287,
                     "npl_share": 0.7388, "offset_pp": -0.00232, "reference_ctl": {"normal_share": 0.786, "npl_share": 0.739}, "valid": True},
                    {"bucket": "消费", "bal": 1_740_000_000, "npl_bal": 70_000_000, "npl_rate": 0.04023,
                     "npl_share": 0.2612, "offset_pp": 0.00921, "reference_ctl": {"normal_share": 0.214, "npl_share": 0.261}, "valid": True},
                ],
            },
        },
        "clue_matrix": {
            "资金往来": {"trigger_ctrt_cnt": 3180, "trigger_ctrt_pptn": 0.0203, "trigger_cust_cnt": 2740,
                      "trigger_bal": 268_000_000, "trigger_npl_ctrt_cnt": 612, "trigger_npl_pptn": 0.1925,
                      "verify_false_pptn": 0.041, "npl_lift": 6.2, "base_rate": 0.0310, "basis": "contract",
                      "coverage_bal_pptn": 0.031},
            "亲属代还": {"trigger_ctrt_cnt": 2010, "trigger_ctrt_pptn": 0.0128, "trigger_cust_cnt": 1780,
                      "trigger_bal": 152_000_000, "trigger_npl_ctrt_cnt": 298, "trigger_npl_pptn": 0.1483,
                      "verify_false_pptn": 0.062, "npl_lift": 4.78, "base_rate": 0.0310, "basis": "contract",
                      "coverage_bal_pptn": 0.018},
            "抵押物异常": {"trigger_ctrt_cnt": 1240, "trigger_ctrt_pptn": 0.0079, "trigger_cust_cnt": 1010,
                       "trigger_bal": 340_000_000, "trigger_npl_ctrt_cnt": 141, "trigger_npl_pptn": 0.1137,
                       "verify_false_pptn": 0.083, "npl_lift": 3.67, "base_rate": 0.0310, "basis": "contract",
                       "coverage_bal_pptn": 0.039},
            "交易异常": {"trigger_ctrt_cnt": 5210, "trigger_ctrt_pptn": 0.0332, "trigger_cust_cnt": 4470,
                      "trigger_bal": 410_000_000, "trigger_npl_ctrt_cnt": 396, "trigger_npl_pptn": 0.076,
                      "verify_false_pptn": 0.21, "npl_lift": 2.45, "base_rate": 0.0310, "basis": "contract",
                      "coverage_bal_pptn": 0.047},
            "逾期预警": {"trigger_ctrt_cnt": 8920, "trigger_ctrt_pptn": 0.0569, "trigger_cust_cnt": 7540,
                      "trigger_bal": 520_000_000, "trigger_npl_ctrt_cnt": 388, "trigger_npl_pptn": 0.0435,
                      "verify_false_pptn": 0.31, "npl_lift": 1.4, "base_rate": 0.0310, "basis": "contract",
                      "coverage_bal_pptn": 0.060},
        },
        "features": [
            {"feature_id": 1, "name": "零散获客", "dimension": "机构", "stage": "贷前", "status": "ok",
             "metric": {"零散客户占比均值": 0.412}, "baseline": {"零散客户占比均值": 0.286},
             "numerator": 41, "denominator": 100, "note": "按行政村户数<50 判定"},
            {"feature_id": 2, "name": "无抵押缓释", "dimension": "担保", "stage": "贷前", "status": "ok",
             "metric": {"信用类余额占比均值": 0.164}, "baseline": {"信用类余额占比均值": 0.121},
             "numerator": 0, "denominator": 0, "note": ""},
            {"feature_id": 3, "name": "低评分准入", "dimension": "客户", "stage": "贷前", "status": "ok",
             "metric": {"低分段(<600)占比": 0.0625}, "baseline": {"低分段(<600)占比": 0.053},
             "numerator": 0, "denominator": 0, "note": ""},
            {"feature_id": 4, "name": "建档不规范", "dimension": "机构", "stage": "贷前", "status": "ok",
             "metric": {"异常建档客户占比均值": 0.073}, "baseline": {"异常建档客户占比均值": 0.041},
             "numerator": 0, "denominator": 0, "note": ""},
            {"feature_id": 9, "name": "贷后管理不到位", "dimension": "贷后", "stage": "贷后", "status": "ok",
             "metric": {"未办结率": 0.318}, "baseline": {"未办结率": 0.205}, "numerator": 0, "denominator": 0, "note": ""},
            {"feature_id": 10, "name": "接续不到位", "dimension": "贷后", "stage": "贷后", "status": "ok",
             "metric": {"无还本续贷不良率均值": 0.0672}, "baseline": {"无还本续贷不良率均值": 0.0310},
             "numerator": 0, "denominator": 0, "note": ""},
            {"feature_id": 11, "name": "高风险客户经理", "dimension": "客户经理", "stage": "贷后", "status": "ok",
             "metric": {"高风险经理数": 37}, "baseline": {"高风险经理数": 9}, "numerator": 37, "denominator": 412, "note": ""},
            {"feature_id": 12, "name": "高风险产品", "dimension": "产品", "stage": "贷前", "status": "ok",
             "metric": {"产品不良率均值": 0.0588}, "baseline": {"产品不良率均值": 0.031}, "numerator": 0, "denominator": 0, "note": ""},
            {"feature_id": 17, "name": "与客户资金往来", "dimension": "客户经理", "stage": "贷后", "status": "ok",
             "metric": {"触发资金往来线索经理数": 22}, "baseline": {"触发资金往来线索经理数": 4},
             "numerator": 22, "denominator": 412, "note": ""},
            {"feature_id": 28, "name": "行业性风险", "dimension": "行业", "stage": "贷前", "status": "ok",
             "metric": {"重点行业不良率均值": 0.0606}, "baseline": {"重点行业不良率均值": 0.031}, "numerator": 0, "denominator": 0, "note": ""},
            {"feature_id": 44, "name": "还款行为恶化", "dimension": "客户", "stage": "贷后", "status": "ok",
             "metric": {"平均逾期天数": 46.2}, "baseline": {"平均逾期天数": 12.4}, "numerator": 0, "denominator": 0, "note": ""},
            {"feature_id": 45, "name": "裸贷户", "dimension": "客户", "stage": "贷后", "status": "ok",
             "metric": {"裸贷户占比": 0.0185}, "baseline": {"裸贷户占比": 0.0072}, "numerator": 0, "denominator": 0, "note": ""},
            {"feature_id": 46, "name": "续贷凭证关系（证据线索）", "dimension": "贷后", "stage": "贷后", "status": "clue",
             "metric": {"同名续贷凭证占比": 0.286}, "baseline": {}, "numerator": 0, "denominator": 0, "note": ""},
            {"feature_id": 48, "name": "上门催收（证据线索）", "dimension": "贷后", "stage": "贷后", "status": "clue",
             "metric": {"催收任务数": 12480}, "baseline": {}, "numerator": 0, "denominator": 0, "note": ""},
            {"feature_id": 49, "name": "亲属信息（证据线索）", "dimension": "客户", "stage": "贷后", "status": "clue",
             "metric": {"有亲属关系记录占比": 0.412}, "baseline": {}, "numerator": 0, "denominator": 0, "note": ""},
        ],
        "continuation": {
            "tools": {
                "no_principal_renew": {"bal": 620_000_000, "npl_bal": 41_700_000, "npl_rate": 0.06726},
                "no_repay_renew": {"bal": 380_000_000, "npl_bal": 20_100_000, "npl_rate": 0.05289},
            },
            "chain": {"rolling": {"cnt": 4180, "npl_rate": 0.0712}, "resolving": {"cnt": 2210, "npl_rate": 0.0244}},
        },
        "warnings": ["合成样例数据（--selftest），非真实业务数据"],
    }


def synth_attribution():
    """合成 attribution.json（CONTRACT 第 3 节 + attribution.py v2 兼容字段）"""
    s = synth_signals()
    feats = {f["feature_id"]: f for f in s["features"]}

    def members(ids):
        out = []
        for i in ids:
            f = feats.get(i)
            if f:
                out.append({"feature_id": i, "name": f["name"], "metric": f["metric"]})
        return out

    manual = [
        {"rule_id": "C01", "name": "获客激进扩张", "essence": "机构为冲规模批量获客，准入标准被稀释",
         "source": "manual", "version": 1, "expr": {"all_of": [1, 2, 3], "min_hits": 2, "any_of": []},
         "cross_stage": False, "stages": ["贷前"],
         "metrics": ["零散客户占比均值", "信用类余额占比均值", "低分段(<600)占比"],
         "evidence_hint": ["dim:guarantee", "dim:score", "dim:org", "clue:资金往来", "feat:1", "feat:2", "feat:3"]},
        {"rule_id": "C05", "name": "贷后管理空转", "essence": "贷后监控缺失、风险信号漏处置",
         "source": "manual", "version": 1, "expr": {"all_of": [9, 18, 19], "min_hits": 1, "any_of": []},
         "cross_stage": True, "stages": ["贷前", "贷后"],
         "metrics": ["未办结率"],
         "evidence_hint": ["feat:9", "clue:逾期预警", "clue_matrix:逾期预警", "dim:year"]},
        {"rule_id": "C06", "name": "续贷接续断裂", "essence": "到期续贷环节风险滚动",
         "source": "manual", "version": 1, "expr": {"all_of": [10, 44], "min_hits": 1, "any_of": []},
         "cross_stage": True, "stages": ["贷后"],
         "metrics": ["无还本续贷不良率均值", "平均逾期天数"],
         "evidence_hint": ["feat:10", "feat:44", "clue:46", "clue:亲属代还"]},
        {"rule_id": "C07", "name": "人员道德风险", "essence": "客户经理能力/尽责/道德问题",
         "source": "manual", "version": 1, "expr": {"all_of": [11, 17], "min_hits": 1, "any_of": []},
         "cross_stage": False, "stages": ["贷后"],
         "metrics": ["高风险经理数", "触发资金往来线索经理数"],
         "evidence_hint": ["feat:11", "feat:17", "clue:资金往来", "clue:亲属代还", "clue:49"]},
        {"rule_id": "C10", "name": "客户经营恶化", "essence": "主业造血能力下降",
         "source": "manual", "version": 1, "expr": {"all_of": [28, 29, 30, 31], "min_hits": 1, "any_of": []},
         "cross_stage": False, "stages": ["贷前"],
         "metrics": ["重点行业不良率均值"],
         "evidence_hint": ["feat:28", "dim:industry", "clue:交易异常"]},
    ]
    mined = [
        {"rule_id": "M01", "name": "低分小额客群叠加信用敞口", "essence": "低评分准入 + 小额高频 + 纯信用，三重弱点叠加",
         "source": "mined", "version": 1, "expr": {"all_of": [3, 2], "min_hits": 2, "any_of": []},
         "cross_stage": False, "stages": ["贷前"],
         "cohort_lift": 2.86, "cohort_npl_rate": 0.0891, "cohort_size": 4820, "incremental_lift": 1.34,
         "metrics": ["低分段(<600)占比"], "evidence_hint": ["dim:score", "dim:amount_band", "clue:资金往来"]},
    ]

    def ins(rule, strength, level):
        ms = members(rule["expr"].get("all_of", []))
        return {"rule_id": rule["rule_id"], "name": rule["name"], "essence": rule["essence"],
                "members": ms, "hit_count": len(ms), "member_total": len(rule["expr"].get("all_of", [])),
                "hit_ratio": round(len(ms) / max(1, len(rule["expr"].get("all_of", []))), 4),
                "strength": strength, "level": level, "source": rule["source"],
                "cross_stage": rule["cross_stage"], "stages": rule["stages"],
                "cohort_lift": rule.get("cohort_lift"),
                "cohort_npl_rate": rule.get("cohort_npl_rate"),
                "cohort_size": rule.get("cohort_size"),
                "incremental_lift": rule.get("incremental_lift"),
                "evidence_hint": rule["evidence_hint"],
                "clues": []}

    insights = [
        ins(manual[3], 0.72, "显著"),
        ins(manual[2], 0.61, "显著"),
        ins(manual[1], 0.55, "显著"),
        ins(manual[0], 0.48, "一般"),
        ins(mined[0], 0.41, "一般"),
        ins(manual[4], 0.31, "一般"),
    ]
    return {
        "schema_version": "3.0",
        "generated_at": "2026-11-06T00:00:00",
        "overall": s["overall"],
        "rules": {"manual": manual, "mined": mined},
        "insights": insights,
        "strong_insights": [i for i in insights if i["level"] in ("显著", "一般")],
        "top": {
            "org": [{"rank": 1, "group": "县域机构A", "bal": 1_240_000_000, "npl_bal": 61_200_000, "npl_rate": 0.0494, "cnt": 21400},
                    {"rank": 2, "group": "县域机构C", "bal": 2_900_000_000, "npl_bal": 82_700_000, "npl_rate": 0.0285, "cnt": 48900}],
            "mgr": [{"rank": 1, "group": "客户经理(编号已脱敏)", "bal": 42_000_000, "npl_bal": 8_600_000, "npl_rate": 0.2048, "cnt": 780}],
            "breed": [],
        },
        "actions": [],
        "warnings": ["合成样例数据（--selftest）"],
    }


# ---------------------------------------------------------------- selftest 公共断言


class Checker:
    def __init__(self, title):
        self.title = title
        self.items = []

    def check(self, cond, label, detail=""):
        self.items.append((bool(cond), label, detail))
        mark = "PASS" if cond else "FAIL"
        print(f"  [{mark}] {label}" + (f" — {detail}" if detail else ""))
        return bool(cond)

    def summary(self):
        bad = [i for i in self.items if not i[0]]
        print(f"\n{self.title}: {len(self.items) - len(bad)}/{len(self.items)} 项通过")
        if bad:
            for _, label, detail in bad:
                print(f"  ✗ {label} {detail}")
        return 0 if not bad else 1
