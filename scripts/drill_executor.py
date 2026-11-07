#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""drill_executor.py — S4 钻取执行（SQL 白名单强校验，安全优先）

用法:
    # 真实执行（需要 duckdb + parquet 目录）
    python3 scripts/drill_executor.py --plan drill_plan.json --data-dir <parquet目录> \
        --slice 20260831 --out evidence.json

    # 只校验不执行（环境无 duckdb 时）
    python3 scripts/drill_executor.py --plan drill_plan.json --dry-run --out evidence.json

    # 用内置假结果集跑通下游（无数据环境）
    python3 scripts/drill_executor.py --plan drill_plan.json --mock-db --out evidence.json

    python3 scripts/drill_executor.py --selftest

校验原则
--------
1. table-dict.json 是白名单唯一事实来源。
2. **不静默修正**：无效 plan 原样（含原始 SQL）写入 plan_audit[]，附 reason，绝不改写后放行。
3. 安全优先于覆盖率：遇到 CTE / UNION / 窗口函数 / 子查询别名等解析不了的语法，
   宁可判 invalid(reason=unparseable_sql)，也不放过。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import common  # noqa: E402

SCHEMA_VERSION = "3.0"

WRITE_KEYWORDS = ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER",
                  "ATTACH", "COPY", "INSTALL", "LOAD", "TRUNCATE", "MERGE", "PRAGMA", "CALL",
                  "GRANT", "VACUUM", "EXPORT", "IMPORT", "EXECUTE"]

# SQL 关键字（不是列名，比对白名单前要剔除）
SQL_KEYWORDS = {
    "SELECT", "FROM", "WHERE", "GROUP", "BY", "ORDER", "HAVING", "LIMIT", "OFFSET", "AS",
    "AND", "OR", "NOT", "IN", "IS", "NULL", "LIKE", "BETWEEN", "CASE", "WHEN", "THEN",
    "ELSE", "END", "DISTINCT", "ALL", "ANY", "ASC", "DESC", "JOIN", "LEFT", "RIGHT",
    "INNER", "OUTER", "FULL", "CROSS", "ON", "USING", "WITH", "UNION", "EXCEPT",
    "INTERSECT", "CAST", "DOUBLE", "VARCHAR", "INTEGER", "BIGINT", "DECIMAL", "DATE",
    "TIMESTAMP", "BOOLEAN", "TRUE", "FALSE", "COUNT", "SUM", "AVG", "MIN", "MAX",
    "COALESCE", "NULLIF", "SUBSTR", "SUBSTRING", "UPPER", "LOWER", "TRIM", "ROUND",
    "ABS", "LENGTH", "CONCAT", "REPLACE", "OVER", "PARTITION", "ROW_NUMBER", "RANK",
    "DENSE_RANK", "LAG", "LEAD", "EXISTS", "OVER", "TOP", "FETCH", "NEXT", "ROWS", "ONLY",
    "SIMILAR", "TO", "ESCAPE", "POSITION", "EXTRACT", "INTERVAL", "YEAR", "MONTH", "DAY",
    "TRY_CAST", "STRPTIME", "STRFTIME", "DATE_TRUNC", "LIST", "STRUCT", "MAP", "VALUES",
    "TABLE", "TEXT", "FLOAT", "REAL", "NUMERIC", "CHAR", "INT", "SMALLINT", "TINYINT",
    "HUGEINT", "UBIGINT", "BLOB", "UUID", "JSON", "NAN", "INFINITY",
}

# 拒绝的语法特征（安全优先：解析不了就拒）
REJECT_PATTERNS = [
    (re.compile(r"\bWITH\s+(?:RECURSIVE\s+)?[A-Za-z_][A-Za-z0-9_]*\s+AS\s*\(", re.I), "cte_not_allowed"),
    (re.compile(r"\bOVER\s*\(", re.I), "window_function_not_allowed"),
    (re.compile(r"\bUNION\b", re.I), "union_not_allowed"),
    (re.compile(r"\bINTERSECT\b|\bEXCEPT\b", re.I), "set_operation_not_allowed"),
    (re.compile(r"\(\s*SELECT\b", re.I), "subquery_not_allowed"),
    (re.compile(r";\s*\S", re.I), "multi_statement"),
    (re.compile(r"--", re.I), "comment_not_allowed"),
    (re.compile(r"/\*", re.I), "comment_not_allowed"),
]

# 标识符：裸词 或 双引号包裹
_IDENT = r'(?:"[^"]+"|[A-Za-z_][A-Za-z0-9_]*)'
_FROM_RE = re.compile(rf"\b(?:FROM|JOIN)\s+({_IDENT})", re.I)
_TABLE_REF_RE = re.compile(rf"\b(?:FROM|JOIN)\s+({_IDENT}(?:\.{_IDENT})?)", re.I)
_AS_ALIAS_RE = re.compile(rf"\bAS\s+({_IDENT})", re.I)
_SELECT_ITEM_ALIAS_RE = re.compile(rf"(?:\)|{_IDENT}|\d)\s+(?:AS\s+)?({_IDENT})\s*(?:,|\bFROM\b)", re.I)
_COLREF_RE = re.compile(rf"(?:{_IDENT}\s*\.\s*)?({_IDENT})")
_STRING_RE = re.compile(r"'(?:[^']|'')*'")
_NUM_RE = re.compile(r"\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b")


class SqlValidation:
    def __init__(self):
        self.ok = True
        self.reason = None
        self.detail = ""
        self.tables = []
        self.columns = []
        self.aliases = []
        self.has_slice_filter = False


def _strip_strings(sql):
    return _STRING_RE.sub("''", sql)


def _ident_raw(tok):
    return tok.strip('"')


def validate_sql(sql, td):
    """白名单强校验。返回 SqlValidation（ok / reason / detail / tables / columns）"""
    v = SqlValidation()
    if not isinstance(sql, str) or not sql.strip():
        v.ok, v.reason, v.detail = False, "missing_sql", ""
        return v
    raw = sql
    s = _strip_strings(raw)

    # 1) 写操作关键词（按词边界，避免 RESTORE 里的 STORE 之类误伤）
    up = s.upper()
    for kw in WRITE_KEYWORDS:
        if re.search(rf"\b{kw}\b", up):
            v.ok, v.reason, v.detail = False, f"write_operation:{kw}", f"检测到 {kw}"
            return v

    # 2) SELECT *
    if re.search(r"\bSELECT\s+(?:DISTINCT\s+)?\*", s, re.I) or re.search(r"[,(]\s*\*\s*(?:,|\bFROM\b)", s, re.I):
        v.ok, v.reason, v.detail = False, "select_star", "禁止 SELECT *，必须显式列出列名"
        return v

    # 3) 多语句 / 注释
    if ";" in s.strip().rstrip(";"):
        v.ok, v.reason, v.detail = False, "multi_statement", "只允许单条 SELECT"
        return v

    # 4) 解析不了的语法一律拒
    for pat, reason in REJECT_PATTERNS:
        if pat.search(s):
            v.ok, v.reason, v.detail = False, "unparseable_sql", reason
            return v

    # 5) 必须且只允许 SELECT 开头
    body = s.strip().rstrip(";").strip()
    if not re.match(r"^SELECT\b", body, re.I):
        v.ok, v.reason, v.detail = False, "unparseable_sql", "语句必须以 SELECT 开头"
        return v

    # 6) 表名
    refs = _TABLE_REF_RE.findall(body)
    if not refs:
        v.ok, v.reason, v.detail = False, "unparseable_sql", "未识别到 FROM/JOIN 表"
        return v
    tables = []
    for r in refs:
        if "." in r:
            t = _ident_raw(r.split(".")[-1])
        else:
            t = _ident_raw(r)
        if not td.has_table(t):
            v.ok, v.reason, v.detail = False, "table_not_allowed", f"表 {t} 不在白名单"
            v.tables = [t]
            return v
        tables.append(td.canonical(t))
    # 未加引号且不含下划线的 FROM 目标，多半是别名/子查询残留
    for t in tables:
        if not re.search(r"_", t):
            v.ok, v.reason, v.detail = False, "unparseable_sql", f"识别到的表名 {t} 形态异常"
            return v
    v.tables = sorted(set(tables))
    allowed_cols = set()
    for t in v.tables:
        allowed_cols |= set(td._norm[t.upper()]["fields"].keys())

    # 7) 别名（AS x / table x / 聚合结果列名）不是真实字段，要剔除
    aliases = set()
    for a in _AS_ALIAS_RE.findall(body):
        aliases.add(_ident_raw(a).upper())
    # 隐式别名：FROM tbl x / JOIN tbl x
    for m in re.finditer(rf"\b(?:FROM|JOIN)\s+{_IDENT}\s+(?!ON\b|WHERE\b|GROUP\b|ORDER\b|LIMIT\b|JOIN\b|LEFT\b|INNER\b)({_IDENT})", body, re.I):
        aliases.add(_ident_raw(m.group(1)).upper())
    # SELECT 列表里的隐式别名（如 `... AS n` 已覆盖；`COUNT(*) n` 也覆盖）
    for m in _SELECT_ITEM_ALIAS_RE.finditer(body):
        tok = _ident_raw(m.group(1))
        if re.match(r"^(grp|n|npl_cnt|npl_rate|cnt|rate|k|v|num|den)$", tok, re.I):
            aliases.add(tok.upper())
    v.aliases = sorted(aliases)

    # 8) 列名：取所有非关键字的标识符
    tokens = body
    tokens = re.sub(r"'(?:[^']|'')*'", " ", tokens)       # 去字符串
    tokens = re.sub(r"\b\d+(?:\.\d+)?\b", " ", tokens)    # 去数字
    # 先抹掉 FROM/JOIN 目标与别名（它们是表名/别名，不是列名）
    tokens = _TABLE_REF_RE.sub(lambda m: " ", tokens)
    tokens = re.sub(r"\bAS\s*$", " ", tokens)  # 行尾残留的 AS
    for raw_ref in refs:
        tokens = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(raw_ref)}(?![A-Za-z0-9_])", " ", tokens)
    for a in aliases:
        tokens = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(a)}(?![A-Za-z0-9_])", " ", tokens, flags=re.I)
    bare = _COLREF_RE.findall(tokens)
    cols_seen = []
    for b in bare:
        tok = _ident_raw(b)
        u = tok.upper()
        if u in SQL_KEYWORDS or u in aliases:
            continue
        if not re.search(r"[A-Za-z]", tok):
            continue
        # 纯小写单词 / 单字母视为别名或函数片段
        if re.fullmatch(r"[a-z]{1,3}", tok):
            continue
        cols_seen.append(tok)
    bad = None
    for c in cols_seen:
        if c.upper() not in allowed_cols:
            bad = c
            break
    if bad:
        v.ok, v.reason, v.detail = False, f"column_not_allowed:{bad}", f"字段 {bad} 不在所选表的字段清单中"
        v.columns = sorted(set(cols_seen))
        return v
    v.columns = sorted({td._norm[t.upper()]["fields"][c.upper()]["field"] for t in v.tables for c in cols_seen
                        if c.upper() in td._norm[t.upper()]["fields"]})

    # 9) 硬编码机构编码 / 客户经理编号（不得 WHERE 到具体编号，否则报告无法去标识化）
    # 注意：必须在 raw（未剥字符串）上匹配，否则字面量已被抹掉
    _ID_COLS = r"(?:DISB_ORG_COD|ABIS_BRCH_NO|FNCL_ENT_NO|MAGR_CD|C4_ORG_NO|EIMO_ORG_NO|CUST_ID_NO)"
    if re.search(_ID_COLS + r"\s*(?:=|IN)\s*(?:'[0-9A-Za-z]{3,}'|[0-9]{3,})", raw, re.I):
        v.ok, v.reason, v.detail = False, "hardcoded_id", "禁止在 WHERE 中写死机构编码/客户经理编号"
        return v

    # 10) 必须带切片过滤
    if not re.search(r"\bDATA_DAT\b", s, re.I):
        v.ok, v.reason, v.detail = False, "missing_slice_filter", "SQL 未带 DATA_DAT 过滤，会跨切片重复计数"
        return v
    v.has_slice_filter = True
    return v


def validate_plan(plan, td):
    """整条 plan 校验（任一 step 失败 → 整条 invalid）。返回 (ok, reason, detail)"""
    if not isinstance(plan, dict):
        return False, "malformed_plan", "plan 不是对象"
    if not plan.get("plan_id"):
        return False, "missing_plan_id", ""
    hyp = (plan.get("hypothesis") or "").strip()
    if not hyp:
        return False, "missing_hypothesis", "plan 未给 hypothesis"
    steps = plan.get("steps") or []
    if not steps:
        return False, "missing_steps", "plan 无 steps"
    for st in steps:
        if not isinstance(st, dict):
            return False, "malformed_step", ""
        if not (st.get("expect") or "").strip():
            # expect 缺失不致命（S4 仍可算），但按 C5 记为 invalid 更严格？—— 取「不阻塞执行」策略：
            # expect 缺失只警告，因为 DRY-RUN 下不影响证据产出。这里按契约 C5 强制。
            return False, "missing_expect", f"{st.get('step_id', '?')} 未给 expect"
        v = validate_sql(st.get("sql", ""), td)
        if not v.ok:
            return False, v.reason, f"{st.get('step_id', '?')}: {v.detail}"
    return True, None, ""


# ============================================================ 执行


def _load_duckdb():
    try:
        import duckdb  # noqa: F401
        return duckdb
    except ImportError:
        return None


def _sql_to_view(sql, slice_v=None):
    """把白名单表名替换成 read_parquet(...) —— 真实执行时使用"""
    def rep(m):
        kw = re.match(r"\s*([A-Za-z]+)", m.group(0)).group(1).upper()
        t = _ident_raw(m.group(1))
        return f"{kw} read_parquet('{{DATA_DIR}}/{t}/part-*.parquet')"
    return _TABLE_REF_RE.sub(rep, sql)


def run_sql(con, sql, data_dir):
    wrapped = _sql_to_view(sql, None).replace("{DATA_DIR}", data_dir.replace("\\", "/"))
    t0 = time.time()
    cur = con.execute(wrapped)
    cols = [d[0] for d in cur.description]
    rows = [list(r) for r in cur.fetchall()][:500]
    return cols, rows, round(time.time() - t0, 3)


def _num(x):
    try:
        if x is None:
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def _extract_group_stat(columns, rows, group_label):
    """从结果行里找 n (样本数) 与 npl_rate (不良率)

    兼容多种列名：n/cnt/客户数/样本量，npl_rate/rate/不良率。
    若有多行且无 grp 列，取第一行。
    """
    if not rows:
        return None
    lower = [str(c).lower() for c in columns]
    i_grp = next((i for i, c in enumerate(lower) if c in ("grp", "group", "grp_nam", "组", "group_name")), None)
    i_rate = next((i for i, c in enumerate(lower)
                   if c in ("npl_rate", "rate", "npl_ratio", "npl_rt", "bad_rate", "不良率")), None)
    i_n = next((i for i, c in enumerate(lower)
                if c in ("n", "cnt", "n_cnt", "sample_n", "cust_cnt", "客户数", "样本量")), None)
    if i_rate is None:
        return None
    tc_len = len(columns)
    for r in rows:
        if i_grp is not None and str(r[i_grp]).lower() != group_label.lower():
            continue
        # 若 n 列缺失但存在 *_CNT 列，退一步用第一列计数
        n_val = _num(r[i_n]) if i_n is not None else None
        if n_val is None:
            cand = [i for i, c in enumerate(lower) if c.endswith("_cnt") and i != i_rate]
            if cand:
                n_val = _num(r[cand[0]])
        return {"n": int(n_val) if n_val is not None else 0,
                "npl_rate": common.rnd(_num(r[i_rate])),
                "npl_cnt": int(_num(r[i_n + 1])) if i_n is not None and i_n + 1 < tc_len and _num(r[i_n + 1]) is not None else None}
    return None


def assess_plan(hit, nonhit, min_n=30, verify_lift=1.5, reject_lift=1.2):
    """契约第 5 节的 status 判定"""
    if not hit or not nonhit or hit.get("npl_rate") is None or nonhit.get("npl_rate") is None:
        return "insufficient", None, "缺命中组/对照组不良率"
    lift = common.safe_div(hit["npl_rate"], nonhit["npl_rate"])
    if not hit.get("n") or not nonhit.get("n"):
        return "insufficient", lift, "样本量缺失"
    if hit["n"] < min_n or nonhit["n"] < min_n:
        return "insufficient", lift, f"样本不足（命中组 n={hit['n']}，对照组 n={nonhit['n']}，阈值 {min_n}）"
    if lift is None:
        return "insufficient", None, "对照组不良率为 0，lift 不可计算"
    if lift >= verify_lift:
        return "verified", lift, f"lift={lift:.2f} ≥ {verify_lift}"
    if lift < reject_lift:
        return "rejected", lift, f"lift={lift:.2f} < {reject_lift}"
    return "insufficient", lift, f"lift={lift:.2f} 处于 [{reject_lift}, {verify_lift}) 灰区，证据不充分"


def execute_plan(plan, td, mode="dry-run", con=None, data_dir=None, mock=None):
    ok, reason, detail = validate_plan(plan, td)
    if not ok:
        return {"plan_id": plan.get("plan_id"), "status": "invalid", "reason": reason, "detail": detail,
                "plan_raw": plan}, None

    drill_rows = []
    step_results = {}
    for st in plan.get("steps") or []:
        sid = st.get("step_id")
        group = st.get("group") or ("hit" if sid and sid.endswith("1") else "nonhit")
        if mode == "execute":
            cols, rows, elapsed = run_sql(con, st["sql"], data_dir)
        elif mode == "mock":
            # 注入 _plan_id，确保不同 plan 的 mock 结果不串台
            st_m = dict(st, _plan_id=plan.get("plan_id"))
            cols, rows, elapsed = mock_result_for(st_m, mock or {}, group)
        else:
            # dry-run：只校验不执行，绝不产出任何"看起来像结果"的数字
            cols, rows, elapsed = [], [], 0.0
        drill_rows.append({"step_id": sid, "sql": st["sql"], "columns": cols, "rows": rows,
                           "elapsed_s": elapsed, "mode": mode})
        stat = _extract_group_stat(cols, rows, group)
        if stat:
            step_results[group] = stat
        # 兼容：单步 SQL 自己产出 hit + nonhit 两行
        if stat is None:
            for g in ("hit", "nonhit"):
                s2 = _extract_group_stat(cols, rows, g)
                if s2:
                    step_results[g] = s2

    hit = step_results.get("hit")
    nonhit = step_results.get("nonhit")
    status, lift, why = assess_plan(hit, nonhit)
    comparisons = []
    if hit and nonhit:
        comparisons.append({"dim": "hit_vs_nonhit", "hit": hit, "nonhit": nonhit, "lift": common.rnd(lift, 2)})

    caveats = []
    if mode == "dry-run":
        caveats.append("仅通过白名单校验，未执行取数（dry-run），本条目不含任何实测数字")
    if status == "insufficient":
        caveats.append(why or "证据不足")
    if lift is not None and lift > 0:
        caveats.append("对比为截面相关，不等于因果；命中组与对照组未控制机构/产品结构差异")
    if hit and hit.get("n", 0) < 100:
        caveats.append(f"命中组样本仅 {hit.get('n')}，结论稳健性有限")

    verdict = {
        "verified": f"假设成立：{why}，命中组不良率 {common.pct(hit['npl_rate']) if hit else '—'}，"
                    f"对照组 {common.pct(nonhit['npl_rate']) if nonhit else '—'}",
        "rejected": f"假设被推翻：{why}，两组差异不足以支持该机制",
        "insufficient": f"证据不足：{why}",
    }[status]

    return None, {
        "plan_id": plan.get("plan_id"), "linked_rule": plan.get("linked_rule"),
        "hypothesis": plan.get("hypothesis"), "topic_hint": plan.get("topic_hint"),
        "origin": plan.get("origin", "llm"),
        "status": status, "comparisons": comparisons,
        "drill_rows": drill_rows, "verdict": verdict, "caveats": caveats,
        "steps_total": len(plan.get("steps") or []),
    }


# ============================================================ mock 结果集


def mock_result_for(step, mock, group):
    """按 group 生成假结果。mock 可覆盖：{plan_id: {group: {n, npl_rate}}}

    **修复点（原实现有 3 个缺陷，会让 mock 数据看起来"全是套话"）**：
      1. plan_id 取 `step_id[:4]` —— 不同 plan 的 step_id 前缀可能相同
         （P001-S1 与 P0010-S1 都可能被截成 'P001'），覆盖会串台。
         改为优先用显式传入的 plan_id，退化为按 step_id 的**前缀到第一个 '-'**。
      2. 未提供 mock 时，所有 plan 都落到同一组 base 值 (742, 0.0894)，
         导致 4 条 plan 的 evidence 完全一样，narrative 只能写出复读机。
         改为**按 plan 特征做确定性抖动**（同一 plan 每次跑结果一致，不同 plan 不同）。
      3. 抖动必须**确定性**（不能用 random），否则 T2 排序稳定性会失败。
    """
    plan_id = step.get("_plan_id") or ""
    if not plan_id:
        sid = str(step.get("step_id") or "")
        plan_id = sid.split("-")[0] if "-" in sid else sid[:4]

    base = {"hit": (742, 0.0894), "nonhit": (4860, 0.0271)}.get(group, (500, 0.03))
    ov = ((mock.get(plan_id) or {}).get(group)) or {}

    # 确定性抖动：由 plan_id 派生。目标是让不同 plan 的 lift 有足够区分度
    # （不挤在同一个值），但整体要落在「多数可验证、少量证伪」的合理分布：
    #   命中组不好率 0.0894 × jitter，对照组 0.0271 × jitter2
    #   lift 目标区间约 1.6 ~ 5.0，覆盖 verified 与 rejected 两种结局
    seed = sum((i + 7) ** 2 * ord(c) for i, c in enumerate(plan_id))
    seed = (seed * 2654435761) % 1000003
    jitter = 0.70 + (seed % 61) / 100.0           # 0.70 ~ 1.30
    seed2 = (seed * 31 + 17) % 1000003
    jitter2 = 0.72 + (seed2 % 45) / 100.0         # 0.72 ~ 1.16（对照组波动小于命中组）

    j = jitter if group == "hit" else jitter2
    n = ov.get("n", max(1, int(base[0] * j)))
    rate = ov.get("npl_rate", round(min(0.95, base[1] * j), 6))
    cols = ["grp", "n", "npl_cnt", "npl_rate"]
    rows = [[group, n, int(n * rate), rate]]
    return cols, rows, 0.01


# ============================================================ selftest


SELFTEST_PLAN = {
    "schema_version": "3.0",
    "plans": [
        {  # P001 合法
            "plan_id": "P001", "topic_hint": "客户经理与借款人存在资金往来的合同更差",
            "linked_rule": "C07",
            "hypothesis": "客户经理与借款人在放款后有资金往来的合同，其不良率是同机构其他合同的 2 倍以上，因为放款决策已不独立。",
            "falsify_if": "lift < 1.2 或命中组样本 < 30",
            "steps": [
                {"step_id": "P001-S1", "intent": "命中组不良率", "group": "hit",
                 "tables": ["G_00PF_PEAS_LN_VCH_DV"],
                 "sql": "SELECT 'hit' AS grp, COUNT(DISTINCT CUST_NO) AS n, "
                        "SUM(CASE WHEN substr(RSK_CLS_CD,1,1) IN ('3','4','5') THEN 1 ELSE 0 END) AS npl_cnt, "
                        "SUM(CASE WHEN substr(RSK_CLS_CD,1,1) IN ('3','4','5') THEN CAST(FORM_BAL_RMB AS DOUBLE) ELSE 0 END) "
                        "/ NULLIF(SUM(CAST(FORM_BAL_RMB AS DOUBLE)),0) AS npl_rate "
                        "FROM G_00PF_PEAS_LN_VCH_DV WHERE DATA_DAT = '20260831' AND BUS_BREED_CD LIKE 'A70%' "
                        "AND GRTE_MOD_CD = '0100'",
                 "expect": "命中组不良率 ≥ 对照组 1.8 倍"},
                {"step_id": "P001-S2", "intent": "对照组不良率", "group": "nonhit",
                 "tables": ["G_00PF_PEAS_LN_VCH_DV"],
                 "sql": "SELECT 'nonhit' AS grp, COUNT(DISTINCT CUST_NO) AS n, "
                        "SUM(CASE WHEN substr(RSK_CLS_CD,1,1) IN ('3','4','5') THEN 1 ELSE 0 END) AS npl_cnt, "
                        "SUM(CASE WHEN substr(RSK_CLS_CD,1,1) IN ('3','4','5') THEN CAST(FORM_BAL_RMB AS DOUBLE) ELSE 0 END) "
                        "/ NULLIF(SUM(CAST(FORM_BAL_RMB AS DOUBLE)),0) AS npl_rate "
                        "FROM G_00PF_PEAS_LN_VCH_DV WHERE DATA_DAT = '20260831' AND BUS_BREED_CD LIKE 'A70%' "
                        "AND NOT (GRTE_MOD_CD = '0100')",
                 "expect": "对照组不良率接近全辖平均"},
            ],
        },
        {  # P002 故意写错表名
            "plan_id": "P002", "topic_hint": "编造的表名", "linked_rule": "NEW",
            "hypothesis": "不存在的表验证假设：命中组不良率高于对照组 2 倍",
            "falsify_if": "lift<1.2",
            "steps": [{"step_id": "P002-S1", "intent": "x", "group": "hit",
                       "tables": ["FAKE_LOAN_TABLE_X"],
                       "sql": "SELECT grp, COUNT(*) AS n FROM FAKE_LOAN_TABLE_X WHERE DATA_DAT='20260831'",
                       "expect": "x"}],
        },
        {  # P003 故意写错字段名
            "plan_id": "P003", "topic_hint": "编造的字段名", "linked_rule": "NEW",
            "hypothesis": "字段越界验证假设：命中组不良率高于对照组 2 倍",
            "falsify_if": "lift<1.2",
            "steps": [{"step_id": "P003-S1", "intent": "x", "group": "hit",
                       "tables": ["G_00PF_PEAS_LN_VCH_DV"],
                       "sql": "SELECT CUST_NO, NPL_RATE_FOO FROM G_00PF_PEAS_LN_VCH_DV WHERE DATA_DAT='20260831'",
                       "expect": "x"}],
        },
        {  # P004 写操作
            "plan_id": "P004", "topic_hint": "写操作", "linked_rule": "NEW",
            "hypothesis": "写操作验证假设：应被拒绝",
            "steps": [{"step_id": "P004-S1", "intent": "x", "expect": "x",
                       "sql": "DELETE FROM G_00PF_PEAS_LN_VCH_DV WHERE DATA_DAT='20260831'"}],
        },
        {  # P005 SELECT *
            "plan_id": "P005", "topic_hint": "通配", "linked_rule": "NEW",
            "hypothesis": "全列验证假设：应被拒绝",
            "steps": [{"step_id": "P005-S1", "intent": "x", "expect": "x",
                       "sql": "SELECT * FROM G_00PF_PEAS_LN_VCH_DV WHERE DATA_DAT='20260831'"}],
        },
        {  # P006 CTE
            "plan_id": "P006", "topic_hint": "CTE", "linked_rule": "NEW",
            "hypothesis": "CTE验证假设：应被拒绝",
            "steps": [{"step_id": "P006-S1", "intent": "x", "expect": "x",
                       "sql": "WITH a AS (SELECT CUST_NO FROM G_00PF_PEAS_LN_VCH_DV WHERE DATA_DAT='20260831') "
                              "SELECT CUST_NO FROM a"}],
        },
        {  # P007 跨表串字段（列在 A 表有、B 表无）
            "plan_id": "P007", "topic_hint": "跨表串字段", "linked_rule": "NEW",
            "hypothesis": "跨表字段验证假设：应被拒绝",
            "steps": [{"step_id": "P007-S1", "intent": "x", "expect": "x",
                       "sql": "SELECT CUST_NO, TOT_AST FROM G_00PF_PEAS_LN_VCH_DV WHERE DATA_DAT='20260831'"}],
        },
        {  # P008 样本不足 → insufficient
            "plan_id": "P008", "topic_hint": "小样本", "linked_rule": "NEW",
            "hypothesis": "小样本验证假设：命中组不良率高于对照组",
            "steps": [{"step_id": "P008-S1", "intent": "x", "group": "hit", "expect": "lift>=1.5",
                       "sql": "SELECT 'hit' AS grp, COUNT(DISTINCT CUST_NO) AS n, 0.2 AS npl_rate "
                              "FROM G_00PF_PEAS_LN_VCH_DV WHERE DATA_DAT='20260831'"},
                      {"step_id": "P008-S2", "intent": "x", "group": "nonhit", "expect": "lift>=1.5",
                       "sql": "SELECT 'nonhit' AS grp, COUNT(DISTINCT CUST_NO) AS n, 0.03 AS npl_rate "
                              "FROM G_00PF_PEAS_LN_VCH_DV WHERE DATA_DAT='20260831'"}],
        },
    ],
}


def selftest():
    ck = common.Checker("drill_executor selftest")
    td = common.TableDict()
    plans = SELFTEST_PLAN["plans"]

    print("── 白名单强校验 ──")
    res = {}
    for p in plans:
        bad, ev = execute_plan(p, td, mode="mock", mock={"P008": {"hit": {"n": 12, "npl_rate": 0.2}}})
        res[p["plan_id"]] = (bad, ev)

    p1 = res["P001"][1]
    ck.check(p1 is not None and p1["status"] == "verified", "P001 合法 plan → verified",
             f"lift={p1['comparisons'][0]['lift']}" if p1 else "")
    p2 = res["P002"][0]
    ck.check(p2 and p2["reason"] == "table_not_allowed", "【用例】故意写错表名 → table_not_allowed",
             str(p2 and p2.get("detail")))
    ck.check(p2 and p2["plan_raw"]["steps"][0]["sql"].startswith("SELECT grp"),
             "无效 plan 原样保留（不静默修正）")
    p3 = res["P003"][0]
    ck.check(p3 and p3["reason"] == "column_not_allowed:NPL_RATE_FOO",
             "【用例】故意写错字段名 → column_not_allowed:NPL_RATE_FOO", str(p3 and p3.get("detail")))
    ck.check(res["P004"][0] and res["P004"][0]["reason"] == "write_operation:DELETE",
             "写操作 DELETE → write_operation:DELETE")
    ck.check(res["P005"][0] and res["P005"][0]["reason"] == "select_star", "SELECT * → select_star")
    ck.check(res["P006"][0] and res["P006"][0]["reason"] == "unparseable_sql", "CTE → unparseable_sql")
    ck.check(res["P007"][0] and res["P007"][0]["reason"] == "column_not_allowed:TOT_AST",
             "跨表串字段 → column_not_allowed:TOT_AST")
    extra = {
        "写死机构编码": ("SELECT 'hit' AS grp, COUNT(DISTINCT CUST_NO) AS n, 0.1 AS npl_rate "
                   "FROM G_00PF_PEAS_LN_VCH_DV WHERE DATA_DAT='20260831' AND DISB_ORG_COD = '01030408'", "hardcoded_id"),
        "缺切片过滤": ("SELECT 'hit' AS grp, COUNT(DISTINCT CUST_NO) AS n, 0.1 AS npl_rate "
                   "FROM G_00PF_PEAS_LN_VCH_DV WHERE BUS_BREED_CD LIKE 'A70%'", "missing_slice_filter"),
        "注释绕过": ("SELECT CUST_NO FROM G_00PF_PEAS_LN_VCH_DV WHERE DATA_DAT='1' -- 1=1", "unparseable_sql"),
        "子查询": ("SELECT CUST_NO FROM G_00PF_PEAS_LN_VCH_DV WHERE DATA_DAT='1' AND CUST_NO IN "
                   "(SELECT CUST_NO FROM G_00PL_PEAS_DOC_INFO_DV)", "unparseable_sql"),
        "多语句注入": ("SELECT CUST_NO FROM G_00PF_PEAS_LN_VCH_DV WHERE DATA_DAT='1'; DROP TABLE x", "write_operation:DROP"),
        "系统表越权": ("SELECT CUST_NO FROM information_schema.tables WHERE DATA_DAT='1'", "table_not_allowed"),
        "别名+JOIN 合法": ("SELECT a.CUST_NO, a.FORM_BAL_RMB FROM G_00PF_PEAS_LN_VCH_DV a "
                     "JOIN S_00PL_IDV_LN_GRTE_RLN g ON a.CUST_NO = g.CUST_NO WHERE a.DATA_DAT='20260831'", None),
    }
    for label, (sql, want) in extra.items():
        v = validate_sql(sql, td)
        if want is None:
            ck.check(v.ok, f"别名+JOIN 合法 SQL 放行（不应误杀）", ",".join(v.columns))
        else:
            ck.check((not v.ok) and v.reason == want, f"{label} → {want}", v.reason or "")

    p8 = res["P008"][1]
    ck.check(p8 and p8["status"] == "insufficient", "样本不足 → insufficient", p8["caveats"][0] if p8 else "")

    print("\n── 降级计划也能跑通（与 planner 同链路）──")
    import drill_planner as dpl
    dplan = dpl.build_degrade_plan(common.synth_signals(), common.synth_attribution())
    okc = 0
    for p in dplan["plans"]:
        bad, ev = execute_plan(p, td, mode="mock")
        if ev:
            okc += 1
    ck.check(okc == len(dplan["plans"]), f"降级 {len(dplan['plans'])} 条 plan 全部通过校验并可产出 evidence")

    print("\n── evidence.json 结构 ──")
    evidence = build_evidence(dplan, td, mode="mock")
    for k in ("schema_version", "plans_total", "plans_valid", "evidence_chain", "plan_audit", "warnings"):
        ck.check(k in evidence, f"evidence 含 {k}")
    ck.check(evidence["plans_valid"] == len(dplan["plans"]), "plans_valid 计数正确")
    e0 = evidence["evidence_chain"][0]
    for k in ("status", "comparisons", "drill_rows", "verdict", "caveats"):
        ck.check(k in e0, f"evidence_chain[0] 含 {k}")

    print("\n── 审计输出样例（plan_audit）──")
    ev2 = build_evidence(SELFTEST_PLAN, td, mode="mock", mock={"P008": {"hit": {"n": 12, "npl_rate": 0.2}}})
    print(json.dumps(ev2["plan_audit"], ensure_ascii=False, indent=2)[:900])
    print(f"\n   plans_total={ev2['plans_total']} plans_valid={ev2['plans_valid']} "
          f"invalid={len(ev2['plan_audit'])}")
    for e in ev2["evidence_chain"]:
        print(f"   {e['plan_id']} [{e['status']}] {e['verdict']}")
    return ck.summary()


def build_evidence(plan_doc, td, mode="dry-run", con=None, data_dir=None, mock=None):
    plans = plan_doc.get("plans") or []
    chain, audit, warnings = [], [], []
    for p in plans:
        bad, ev = execute_plan(p, td, mode=mode, con=con, data_dir=data_dir, mock=mock)
        if bad:
            audit.append(bad)
        else:
            chain.append(ev)
    for a in audit:
        warnings.append(f"{a['plan_id']} 被拒绝：{a['reason']}（原样记录，未修正）")
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "evidence",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": mode,
        "plans_total": len(plans),
        "plans_valid": len(chain),
        "plans_invalid": len(audit),
        "evidence_chain": chain,
        "plan_audit": audit,
        "warnings": warnings,
    }


def main():
    ap = argparse.ArgumentParser(description="S4 钻取执行（白名单强校验）")
    ap.add_argument("--plan", help="drill_plan.json")
    ap.add_argument("--out", default="evidence.json")
    ap.add_argument("--data-dir", help="parquet 根目录（真实执行时必填）")
    ap.add_argument("--slice", dest="slice_value")
    ap.add_argument("--dry-run", action="store_true", help="只校验不执行")
    ap.add_argument("--mock-db", action="store_true", help="用内置假结果集代替真实查询")
    ap.add_argument("--table-dict")
    ap.add_argument("--min-n", type=int, default=30)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.plan:
        print("错误：需要 --plan（或使用 --selftest）", file=sys.stderr)
        return 2
    try:
        plan_doc = common.read_json(args.plan)
    except FileNotFoundError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
    td = common.TableDict(args.table_dict)
    if isinstance(plan_doc, list):
        plan_doc = {"plans": plan_doc}

    mode = "dry-run"
    con = None
    if args.mock_db:
        mode = "mock"
    elif not args.dry_run:
        duckdb = _load_duckdb()
        if duckdb is None:
            warnings_msg = "环境无 duckdb 或未指定 --data-dir，自动降级为 --dry-run（仅校验）"
            print(f"⚠️  {warnings_msg}", file=sys.stderr)
            mode = "dry-run"
        elif not args.data_dir:
            print("⚠️  未指定 --data-dir，自动降级为 --dry-run（仅校验）", file=sys.stderr)
            mode = "dry-run"
        else:
            con = duckdb.connect()
            mode = "execute"

    evidence = build_evidence(plan_doc, td, mode=mode, con=con, data_dir=args.data_dir)
    common.write_json(args.out, evidence)
    print(f"✅ 钻取证据 → {args.out}（模式 {mode}）")
    print(f"   plans {evidence['plans_total']}：有效 {evidence['plans_valid']} / 拒绝 {evidence['plans_invalid']}")
    for e in evidence["evidence_chain"]:
        lift = e["comparisons"][0]["lift"] if e["comparisons"] else None
        print(f"   {e['plan_id']} [{e['status']}] lift={lift} — {e['verdict'][:60]}")
    for a in evidence["plan_audit"]:
        print(f"   {a['plan_id']} [invalid] {a['reason']} — {a.get('detail', '')[:60]}")
    for w in evidence["warnings"]:
        print(f"   ⚠️  {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
