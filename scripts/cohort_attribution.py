#!/usr/bin/env python3
"""cohort_attribution.py — 客群归因 + 优质客户准入反推（DuckDB）

思路（对齐用户迭代方向）：
1. 归因主题 = 多个风险指标（至少）结合 → 每个指标定义可提取客户样本的判据
   → 取「交集」形成主题命中客群（而非只看机构级 metric）
2. 命中客群 vs 正常组客户（对照组）双向对照画像：
   - 命中组在哪些维度显著偏离正常组（风险画像）
   - 正常组在哪些维度显著区别于命中组（优质画像）
3. 管理措施侧重：通过不良客户特征的筛选，定向筛选出可准入的优质客户
   → 输出「准入候选客群」（正常组中满足优质特征的客户）及其特征清单

用法:
    python3 scripts/cohort_attribution.py --data-dir 数据文件duckdb/parquet \\
        --slice 20260831 --out cohort.json
"""
import argparse
import json
import os
import sys
import time

import duckdb

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ============ 指标判据配置：feature_id → 客户样本提取 SQL ============
# 每个判据定义一个客户集合；主题命中客群 = 各成员判据客户集合的「交集」
FEATURE_SAMPLES = {
    # 贷前准入
    3:  {"desc": "低评分准入", "table": "G_00PL_IDV_LN_CUST_ACARD_SCRE_DV",
         "key": "CUST_NO", "cond": "CAST(SCRE AS DOUBLE) < 600",
         "slice_col": "DATA_DAT", "slice_val": None,  # None=自动最新
         "dim": "贷前准入"},
    16: {"desc": "信息录入失真（FAS虚增）", "table": "B_00DT_FAS_ANL_SITU_DOC_H",
         "key": "ID_CARD_NO", "need_map": True,
         "cond": "CAST(TOT_DPS AS DOUBLE) > 0 AND CAST(TOT_DPS AS DOUBLE)/NULLIF(CAST(TOT_AST AS DOUBLE),0) > 1",
         "dim": "贷前准入"},
    45: {"desc": "裸贷户（总资产=0）", "table": "B_00DT_FAS_ANL_SITU_DOC_H",
         "key": "ID_CARD_NO", "need_map": True,
         "cond": "CAST(TOT_AST AS DOUBLE) = 0",
         "dim": "贷前准入"},
    39: {"desc": "收入覆盖不足", "table": "B_00DT_FAS_FMLY_SITU_DOC_H",
         "key": "ID_CARD_NO", "need_map": True,
         "cond": "CAST(FMLY_ANNL_INCM AS DOUBLE) < 50000",
         "dim": "贷前准入"},
    44: {"desc": "还款行为恶化", "table": "G_00PL_IDV_LN_ARG_EXD_DV",
         "key": "FORM_NO", "is_vch": True,
         "cond": "CAST(EXD_CAP AS DOUBLE) > 0",
         "dim": "贷后管理"},
    9:  {"desc": "贷后任务未办结", "table": "B_00FT_PEAS_LN_DPSE_TASK_DTAL",
         "key": "CUST_NO", "cond": "BUS_STS IN ('00','50')",
         "dim": "贷后管理"},
    # 管理与行为：客户经理资金往来线索（风险信号表口径，经理级→客户级展开）
    17: {"desc": "与客户资金往来", "table": "S_00PF_PEAS_MGR_LN_RISK_C4",
         "key": "CUST_ID_NO", "cond": "CAST(COALESCE(NULLIF(FND_CLU_CNT_PEAS,'\\N'),'0') AS BIGINT) > 0",
         "mgr_expand": True, "dim": "管理与行为"},
    14: {"desc": "批量建档（同日≥5户）", "table": "S_00PF_PEAS_MGR_LN_RISK_C4",
         "key": "CUST_ID_NO", "cond": "CAST(COALESCE(NULLIF(SAME_DAT_CUST_CNT,'\\N'),'0') AS BIGINT) >= 5",
         "mgr_expand": True, "dim": "管理与行为"},
}

# ============ 主题规则：多指标结合 → 命中客群 ============
# members: feature_id 列表；method: intersect=交集 / union=并集
COHORT_RULES = [
    {"rule_id": "G01", "name": "客户经理渎职风险", "essence": "建档失真+资金往来+低评分+批量建档",
     "members": [16, 17, 3, 14], "method": "intersect",
     "desc": "示例：信息录入失真 ∩ 客户经理资金往来 ∩ 低评分准入 ∩ 批量建档 → 客户经理渎职客群"},
    {"rule_id": "G02", "name": "弱质客群下沉", "essence": "低评分+收入不足+裸贷户",
     "members": [3, 39, 45], "method": "intersect",
     "desc": "低评分 ∩ 收入不足 ∩ 裸贷户 → 极端弱资质客群"},
    {"rule_id": "G03", "name": "贷后失控客群", "essence": "任务未办结+还款恶化",
     "members": [9, 44], "method": "intersect",
     "desc": "贷后任务未办结 ∩ 还款恶化 → 贷后失控客群"},
    {"rule_id": "G04", "name": "批量获客风险", "essence": "批量建档+低评分",
     "members": [14, 3], "method": "intersect",
     "desc": "批量建档客户经理 ∩ 低评分客户 → 批量获客风险"},

    # ---- 以下 G05~G09：SQL 条件型客群，直接对 cohort_base 列过滤 ----
    # 依据：本切片仅农户贷款(A70)，农户/个人凭证为同一批客户，客群只能按农贷内部属性切分
    {"rule_id": "G05", "name": "小额贷款客群", "essence": "户均借款金额5万元以下",
     "members": ["avg_amt < 50000"], "method": "condition",
     "match_dim": "额度档", "match_bucket": "5万以下",
     "desc": "户均额度 5 万以下 → 覆盖 M03/M04/M05/M06/M13/M16/M17"},
    {"rule_id": "G06", "name": "存量老资产客群", "essence": "最早一笔放款在2023年及以前",
     "members": ["fst_ln_year <= 2023"], "method": "condition",
     "match_dim": "放款年份", "match_bucket": "2023",
     "desc": "放款年份 2023 及以前 → 覆盖 M08/M09/M11/M14/M16"},
    {"rule_id": "G07", "name": "脱贫户客群", "essence": "经营主体类型为脱贫户",
     "members": ["ADMI_SUBJ_TYP = '01'"], "method": "condition",
     "match_dim": "主体类型", "match_bucket": "脱贫户",
     "desc": "主体类型 01 脱贫户 → 覆盖 M07/M15/M17"},
    {"rule_id": "G08", "name": "种养大户客群", "essence": "经营主体类型为种养大户",
     "members": ["ADMI_SUBJ_TYP = '06'"], "method": "condition",
     "match_dim": "主体类型", "match_bucket": "种养大户",
     "desc": "主体类型 06 种养大户 → 规模化经营风险"},
    {"rule_id": "G09", "name": "边缘户客群", "essence": "经营主体类型为边缘户或一般农户(已核)",
     "members": ["ADMI_SUBJ_TYP IN ('03','05')"], "method": "condition",
     "match_dim": "主体类型", "match_bucket": "边缘户",
     "desc": "主体类型 03/05 → 政策边缘群体，风险介于脱贫户与一般农户之间"},
]

# ============ 对照画像维度（命中组 vs 正常组） ============
# 每个维度：SQL 表达式（cohort_base 已物化，使用其实际列）
# cohort_base 列：CUST_NO, avg_bal, avg_amt, has_exd, has_npl, CUR_PLCE_RES_YEAR,
#                 ADMI_SUBJ_TYP, FARM_LAND, TOT_DPS, RMB_DP_BAL, FA_BAL, YEAR_TR_BAL_L1YER_ACLT, SCRE
PROFILE_DIMS = {
    "平均余额": "AVG(avg_bal)",
    "平均额度": "AVG(avg_amt)",
    "有逾期凭证占比": "AVG(has_exd)",
    "不良凭证占比": "AVG(has_npl)",
    "无评分占比": "AVG(CASE WHEN SCRE IS NULL OR CAST(SCRE AS DOUBLE) = 0 THEN 1 ELSE 0 END)",
    "低评分(<600)占比": "AVG(CASE WHEN SCRE IS NOT NULL AND CAST(SCRE AS DOUBLE) > 0 AND CAST(SCRE AS DOUBLE) < 600 THEN 1 ELSE 0 END)",
    "居住5年+占比": "AVG(CASE WHEN CAST(COALESCE(CUR_PLCE_RES_YEAR,'0') AS BIGINT) >= 5 THEN 1 ELSE 0 END)",
    "有农地占比": "AVG(CASE WHEN CAST(COALESCE(FARM_LAND,'0') AS DOUBLE) > 0 THEN 1 ELSE 0 END)",
    "低负债占比": "AVG(CASE WHEN CAST(COALESCE(TOT_DPS,'0') AS DOUBLE) <= 0 THEN 1 ELSE 0 END)",
    "脱贫户占比": "AVG(CASE WHEN ADMI_SUBJ_TYP = '01' THEN 1 ELSE 0 END)",
    "种养大户占比": "AVG(CASE WHEN ADMI_SUBJ_TYP = '06' THEN 1 ELSE 0 END)",
    "存款>0占比": "AVG(CASE WHEN CAST(COALESCE(RMB_DP_BAL,'0') AS DOUBLE) > 0 THEN 1 ELSE 0 END)",
    "金融资产>0占比": "AVG(CASE WHEN CAST(COALESCE(FA_BAL,'0') AS DOUBLE) > 0 THEN 1 ELSE 0 END)",
    "交易活跃>100万占比": "AVG(CASE WHEN CAST(COALESCE(YEAR_TR_BAL_L1YER_ACLT,'0') AS DOUBLE) > 1000000 THEN 1 ELSE 0 END)",
}

# 优质准入画像（正常组显著特征，用于反推可准入优质客户）
# 注意：cohort_base 已物化，字段平铺（无表别名），直接引用列名
QUALITY_DIMS = {
    "有农地": "CAST(COALESCE(FARM_LAND,'0') AS DOUBLE) > 0",
    "居住5年以上": "CAST(COALESCE(CUR_PLCE_RES_YEAR,'0') AS BIGINT) >= 5",
    "非脱贫户": "COALESCE(ADMI_SUBJ_TYP,'') <> '01'",
    "低负债": "CAST(COALESCE(TOT_DPS,'0') AS DOUBLE) <= 0",
    "有存款": "CAST(COALESCE(RMB_DP_BAL,'0') AS DOUBLE) > 0",
    "有评分且>=600": "SCRE IS NOT NULL AND CAST(SCRE AS DOUBLE) >= 600",
    "有农地且存款>0": "CAST(COALESCE(FARM_LAND,'0') AS DOUBLE) > 0 AND CAST(COALESCE(RMB_DP_BAL,'0') AS DOUBLE) > 0",
}


def parquet_glob(data_dir, table):
    return os.path.join(data_dir, table, "part-*.parquet").replace("\\", "/")


def latest_slice(con, data_dir, table):
    try:
        return con.execute(f"SELECT max(DATA_DAT) FROM read_parquet('{parquet_glob(data_dir, table)}')").fetchone()[0]
    except Exception:
        return None


def build_feature_sample(con, data_dir, cfg, qlog):
    """按指标判据提取客户集合（返回 set）
    支持 mgr_expand：经理级样本（CUST_ID_NO）→ 经凭证表 MAGR_CD 展开为名下客户集合
    """
    tbl = cfg["table"]
    sl = cfg.get("slice_val") or latest_slice(con, data_dir, tbl)
    if cfg.get("mgr_expand"):
        # 先取命中经理集合，再经凭证表 MAGR_CD 映射到客户
        sql = f"""SELECT DISTINCT {cfg['key']} AS K FROM read_parquet('{parquet_glob(data_dir, tbl)}')
                  WHERE ({cfg['cond']})"""
        if sl:
            sql += f" AND DATA_DAT = '{sl}'"
        mgrs = {r[0] for r in con.execute(sql).fetchall()}
        if not mgrs:
            return set()
        ph = ",".join(f"'{k}'" for k in list(mgrs)[:50000])
        sql2 = f"""SELECT DISTINCT CUST_NO FROM read_parquet('{parquet_glob(data_dir, 'G_00PF_PEAS_LN_VCH_DV')}')
                   WHERE DATA_DAT = '{sl}' AND MAGR_CD IN ({ph})"""
        sample = {r[0] for r in con.execute(sql2).fetchall()}
        qlog.add(stage="客群归因", table=tbl, query=f"样本(经理展开): {cfg['desc']}",
                 result=f"经理 {len(mgrs)} → 客户 {len(sample)}", thought="经理级→客户级展开")
        return sample
    if cfg.get("need_map"):
        sl2 = latest_slice(con, data_dir, "G_00PL_PEAS_DOC_INFO_DV")
        sql = f"""SELECT DISTINCT m.CUST_NO AS K
                  FROM read_parquet('{parquet_glob(data_dir, tbl)}') f
                  JOIN read_parquet('{parquet_glob(data_dir, "G_00PL_PEAS_DOC_INFO_DV")}') m
                    ON m.ID_CARD_NO = f.ID_CARD_NO AND m.DATA_DAT = '{sl2}'
                  WHERE ({cfg['cond']})"""
        if sl:
            sql += f" AND f.DATA_DAT = '{sl}'"
    else:
        sql = f"""SELECT DISTINCT {cfg['key']} AS K FROM read_parquet('{parquet_glob(data_dir, tbl)}')
                  WHERE ({cfg['cond']})"""
        if sl:
            sql += f" AND DATA_DAT = '{sl}'"
    rows = con.execute(sql).fetchall()
    sample = {r[0] for r in rows}
    qlog.add(stage="客群归因", table=tbl, query=f"样本: {cfg['desc']}",
             result=f"{len(sample)} 个", thought="指标判据提取客户集合")
    return sample


def build_base(con, data_dir, slice_dt, qlog):
    """构建客户级宽表（凭证主键 CUST_NO 聚合 + 建档/FAS/存款/FA/交易 JOIN）"""
    vch_glob = parquet_glob(data_dir, "G_00PF_PEAS_LN_VCH_DV")
    doc_glob = parquet_glob(data_dir, "G_00PL_PEAS_DOC_INFO_DV")
    fas_glob = parquet_glob(data_dir, "B_00DT_FAS_ANL_SITU_DOC_H")
    dp_glob = parquet_glob(data_dir, "S_00PF_IDV_DP_CUST_SUM")
    fa_glob = parquet_glob(data_dir, "S_00PF_IDV_CUST_FA_SUM")
    tr_glob = parquet_glob(data_dir, "S_00PF_SA_ACCT_TR_CUST_SUM")
    scre_glob = parquet_glob(data_dir, "G_00PL_IDV_LN_CUST_ACARD_SCRE_DV")
    scre_dt = latest_slice(con, data_dir, "G_00PL_IDV_LN_CUST_ACARD_SCRE_DV")
    sl2 = latest_slice(con, data_dir, "G_00PL_PEAS_DOC_INFO_DV")

    # 分步构建（避免复杂相关子查询）：先建档映射，再 FAS 按证件关联
    sql = f"""
    CREATE TEMP TABLE cohort_base AS
    WITH v AS (
        SELECT CUST_NO,
               AVG(CAST(FORM_BAL_RMB AS DOUBLE)) AS avg_bal,
               AVG(CAST(LN_AMT_RMB AS DOUBLE)) AS avg_amt,
               MAX(CASE WHEN CAST(COALESCE(EXD_DAYS,'0') AS BIGINT) > 0 THEN 1 ELSE 0 END) AS has_exd,
               MAX(CASE WHEN RSK_CLS_CD IN ('30','40','50') THEN 1 ELSE 0 END) AS has_npl,
               MIN(TRY_CAST(SUBSTR(LN_DAT,1,4) AS BIGINT)) AS fst_ln_year
        FROM read_parquet('{vch_glob}')
        WHERE DATA_DAT = '{slice_dt}' AND BUS_BREED_CD LIKE 'A70%'
        GROUP BY 1
    ),
    doc AS (
        SELECT DISTINCT CUST_NO, ID_CARD_NO, CUR_PLCE_RES_YEAR, ADMI_SUBJ_TYP
        FROM read_parquet('{doc_glob}') WHERE DATA_DAT = '{sl2}'
    ),
    fas AS (
        SELECT ID_CARD_NO, MAX(CAST(COALESCE(FARM_LAND,'0') AS DOUBLE)) FARM_LAND,
               MAX(CAST(COALESCE(TOT_DPS,'0') AS DOUBLE)) TOT_DPS
        FROM read_parquet('{fas_glob}') GROUP BY 1
    )
    SELECT v.CUST_NO, v.avg_bal, v.avg_amt, v.has_exd, v.has_npl, v.fst_ln_year,
           d.CUR_PLCE_RES_YEAR, d.ADMI_SUBJ_TYP,
           f.FARM_LAND, f.TOT_DPS,
           dp.RMB_DP_BAL,
           f2.FA_BAL,
           tr.YEAR_TR_BAL_L1YER_ACLT,
           s.SCRE
    FROM v
    LEFT JOIN doc d ON d.CUST_NO = v.CUST_NO
    LEFT JOIN fas f ON f.ID_CARD_NO = d.ID_CARD_NO
    LEFT JOIN (SELECT CUST_NO, MAX(CAST(COALESCE(RMB_DP_BAL,'0') AS DOUBLE)) RMB_DP_BAL FROM read_parquet('{dp_glob}') WHERE DATA_DAT='{slice_dt}' GROUP BY 1) dp ON dp.CUST_NO = v.CUST_NO
    LEFT JOIN (SELECT CUST_NO, MAX(CAST(COALESCE(FA_BAL,'0') AS DOUBLE)) FA_BAL FROM read_parquet('{fa_glob}') WHERE DATA_DAT='{slice_dt}' GROUP BY 1) f2 ON f2.CUST_NO = v.CUST_NO
    LEFT JOIN (SELECT CUST_NO, MAX(CAST(COALESCE(YEAR_TR_BAL_L1YER_ACLT,'0') AS DOUBLE)) YEAR_TR_BAL_L1YER_ACLT FROM read_parquet('{tr_glob}') WHERE DATA_DAT='{slice_dt}' GROUP BY 1) tr ON tr.CUST_NO = v.CUST_NO
    LEFT JOIN (SELECT CUST_NO, MAX(CAST(SCRE AS DOUBLE)) SCRE FROM read_parquet('{scre_glob}') WHERE DATA_DAT='{scre_dt}' GROUP BY 1) s ON s.CUST_NO = v.CUST_NO
    """
    try:
        con.execute(sql)
    except Exception as e:
        qlog.add(stage="客群归因", table="cohort_base", query="构建客户宽表",
                 result=f"ERROR {str(e)[:120]}", thought="DuckDB 建表失败")
        print(f"错误：cohort_base 构建失败 {str(e)[:120]}", file=sys.stderr)
        return False
    qlog.add(stage="客群归因", table="cohort_base",
             query="构建客户级宽表（凭证+建档+FAS+存款+FA+交易+评分）",
             result="OK", thought="客户级对照画像基础表")
    return True


def profile_cohort(con, cohort_set, label, qlog):
    """对客群集合计算画像维度（均值/占比）
    用临时表存储客群集合，JOIN 替代 IN（避免超长 IN 列表）
    """
    if not cohort_set:
        return None
    con.execute("DROP TABLE IF EXISTS tmp_cohort_members")
    ph = ",".join(f"('{k}')" for k in list(cohort_set)[:200000])
    con.execute(f"CREATE TEMP TABLE tmp_cohort_members AS SELECT * FROM (VALUES {ph}) t(CUST_NO)")
    sel = ", ".join(f"({expr}) AS d{i}" for i, (nm, expr) in enumerate(PROFILE_DIMS.items()))
    sql = f"""SELECT {sel} FROM cohort_base b JOIN tmp_cohort_members m ON m.CUST_NO = b.CUST_NO"""
    try:
        row = con.execute(sql).fetchone()
    except Exception as e:
        qlog.add(stage="客群归因", table="cohort_base", query=f"画像 {label}", result=f"ERROR {str(e)[:80]}", thought="")
        return None
    return {nm: (round(float(v), 4) if v is not None else None)
            for (nm, _), v in zip(PROFILE_DIMS.items(), row)}


def main():
    ap = argparse.ArgumentParser(description="客群归因 + 优质客户准入反推")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--slice", default="20260831")
    ap.add_argument("--out", default="cohort.json")
    ap.add_argument("--log", default="query_log.md")
    args = ap.parse_args()

    try:
        from query_log import QueryLog
    except ImportError:
        class QueryLog:
            def __init__(self, path=None, title=""):
                self.entries = []
            def add(self, stage, table, query, result, thought):
                self.entries.append({"stage": stage, "table": table, "query": query,
                                     "result": result, "thought": thought})

    qlog = QueryLog(path=args.log, title="查询日志（内部工作记录）")
    con = duckdb.connect()
    t_start = time.time()

    # 自动切片
    avail = con.execute(f"SELECT DISTINCT DATA_DAT FROM read_parquet('{parquet_glob(args.data_dir, 'G_00PF_PEAS_LN_VCH_DV')}') ORDER BY 1 DESC LIMIT 3").fetchall()
    slice_dt = args.slice if any(r[0] == args.slice for r in avail) else avail[0][0]

    # 构建客户宽表
    if not build_base(con, args.data_dir, slice_dt, qlog):
        return 2

    # 正常组：无不良、无逾期（对照组）
    normal_sql = "SELECT DISTINCT CUST_NO FROM cohort_base WHERE has_npl = 0 AND has_exd = 0"
    normal_set = {r[0] for r in con.execute(normal_sql).fetchall()}
    bad_sql = "SELECT DISTINCT CUST_NO FROM cohort_base WHERE has_npl = 1"
    bad_set = {r[0] for r in con.execute(bad_sql).fetchall()}
    print(f"对照组：正常 {len(normal_set)} / 不良 {len(bad_set)}")

    # 正常组/不良组画像：直接在 cohort_base 上按条件聚合（避免超长集合 JOIN）
    def profile_by_cond(cond):
        sel = ", ".join(f"({expr}) AS d{i}" for i, (nm, expr) in enumerate(PROFILE_DIMS.items()))
        row = con.execute(f"SELECT {sel} FROM cohort_base WHERE {cond}").fetchone()
        return {nm: (round(float(v), 4) if v is not None else None)
                for (nm, _), v in zip(PROFILE_DIMS.items(), row)}

    normal_profile = profile_by_cond("has_npl = 0 AND has_exd = 0")
    bad_profile = profile_by_cond("has_npl = 1")
    print(f"正常组画像：有农地 {normal_profile.get('有农地占比')} | 有存款 {normal_profile.get('存款>0占比')} | 不良凭证 {normal_profile.get('不良凭证占比')}")

    # 主题客群
    themes = []
    for rule in COHORT_RULES:
        # condition 型：整条 SQL 条件直接对 cohort_base 过滤
        if rule["method"] == "condition":
            cond = " AND ".join(str(c) for c in rule["members"])
            sql = f"SELECT DISTINCT CUST_NO FROM cohort_base WHERE {cond}"
            try:
                con.execute("DROP TABLE IF EXISTS tmp_cohort_cond")
                con.execute(f"CREATE TEMP TABLE tmp_cohort_cond AS {sql}")
                n = con.execute("SELECT COUNT(*) FROM tmp_cohort_cond").fetchone()[0]
                con.execute("DROP TABLE IF EXISTS tmp_cohort_members")
                con.execute("CREATE TEMP TABLE tmp_cohort_members AS SELECT CUST_NO FROM tmp_cohort_cond")
                sel = ", ".join(f"({expr}) AS d{i}" for i, (nm, expr) in enumerate(PROFILE_DIMS.items()))
                row = con.execute(
                    f"SELECT {sel} FROM cohort_base b JOIN tmp_cohort_members m ON m.CUST_NO = b.CUST_NO"
                ).fetchone()
                cohort_profile = ({nm: (round(float(v), 4) if v is not None else None)
                                   for (nm, _), v in zip(PROFILE_DIMS.items(), row)}
                                  if row else None)
            except Exception as e:
                qlog.add(stage="客群归因", table="cohort_base", query=rule["name"],
                         result=f"ERROR {str(e)[:80]}", thought="condition 型客群失败")
                continue
            if not row:
                continue
            diff = {}
            if cohort_profile and normal_profile:
                for k in PROFILE_DIMS:
                    cv, nv = cohort_profile.get(k), normal_profile.get(k)
                    if cv is not None and nv is not None:
                        diff[k] = round(cv - nv, 4)
            # 客群自身不良率与 lift（余额加权）
            npl_rate, lift = None, None
            try:
                r = con.execute(
                    "SELECT SUM(CASE WHEN has_npl=1 THEN avg_bal ELSE 0 END)*1.0/"
                    "NULLIF(SUM(avg_bal),0) FROM cohort_base WHERE " + cond
                ).fetchone()[0]
                b = con.execute(
                    "SELECT SUM(CASE WHEN has_npl=1 THEN avg_bal ELSE 0 END)*1.0/"
                    "NULLIF(SUM(avg_bal),0) FROM cohort_base"
                ).fetchone()[0]
                if r is not None:
                    npl_rate = round(float(r), 6)
                    lift = round(float(r) / float(b), 4) if b else None
            except Exception:
                pass
            themes.append({
                "rule_id": rule["rule_id"], "name": rule["name"], "essence": rule["essence"],
                "desc": rule["desc"], "members": [str(c) for c in rule["members"]],
                "member_sizes": {str(rule["members"][0]): int(n)},
                "cohort_size": int(n), "cohort_profile": cohort_profile,
                "normal_profile": normal_profile, "diff_vs_normal": diff,
                "npl_rate": npl_rate, "lift": lift,
                "match_dim": rule.get("match_dim"), "match_bucket": rule.get("match_bucket"),
            })
            print(f"  [{rule['rule_id']}] {rule['name']}: 客群 {n}")
            qlog.add(stage="客群归因", table="cohort_base", query=f"{rule['name']}：{cond}",
                     result=f"客群 {n}", thought="condition-型客群")
            continue

        sets = []
        for fid in rule["members"]:
            cfg = FEATURE_SAMPLES.get(fid)
            if not cfg:
                continue
            s = build_feature_sample(con, args.data_dir, cfg, qlog)
            if s:
                sets.append(s)
        if not sets:
            continue
        # 交集
        if rule["method"] == "intersect":
            cohort = set.intersection(*sets)
        else:
            cohort = set.union(*sets)
        # 主题客群画像
        cohort_profile = profile_cohort(con, cohort, rule["name"], qlog)
        # 对照差异：命中组 vs 正常组
        diff = {}
        if cohort_profile and normal_profile:
            for k in PROFILE_DIMS:
                cv, nv = cohort_profile.get(k), normal_profile.get(k)
                if cv is not None and nv is not None:
                    diff[k] = round(cv - nv, 4)
        themes.append({
            "rule_id": rule["rule_id"],
            "name": rule["name"],
            "essence": rule["essence"],
            "desc": rule["desc"],
            "members": [FEATURE_SAMPLES[fid]["desc"] for fid in rule["members"] if fid in FEATURE_SAMPLES],
            "member_sizes": {FEATURE_SAMPLES[fid]["desc"]: len(sets[i]) for i, fid in enumerate(rule["members"]) if fid in FEATURE_SAMPLES and i < len(sets)},
            "cohort_size": len(cohort),
            "cohort_profile": cohort_profile,
            "normal_profile": normal_profile,
            "diff_vs_normal": diff,
        })
        print(f"  [{rule['rule_id']}] {rule['name']}: 客群 {len(cohort)}")

    # 优质准入反推：正常组中满足优质特征的客户，输出特征组合命中率对比
    quality = {}
    for qname, qexpr in QUALITY_DIMS.items():
        sql = f"SELECT COUNT(*) FROM cohort_base WHERE {qexpr}"
        n_total = con.execute(sql).fetchone()[0]
        sql_n = f"SELECT COUNT(*) FROM cohort_base WHERE {qexpr} AND has_npl = 0 AND has_exd = 0"
        n_normal = con.execute(sql_n).fetchone()[0]
        sql_b = f"SELECT COUNT(*) FROM cohort_base WHERE {qexpr} AND has_npl = 1"
        n_bad = con.execute(sql_b).fetchone()[0]
        quality[qname] = {
            "total_cnt": int(n_total),
            "normal_cnt": int(n_normal),
            "bad_cnt": int(n_bad),
            "normal_rate": round(n_normal / n_total, 4) if n_total else None,
            "bad_rate": round(n_bad / n_total, 4) if n_total else None,
            "bad_within": round(n_bad / (n_normal + n_bad), 4) if (n_normal + n_bad) else None,
        }
        print(f"  优质特征 [{qname}]: 不良内占比 {quality[qname]['bad_within']:.2%}")

    # 准入候选客群：满足全部优质特征的正常客户（可准入优质客户）
    all_conds = " AND ".join(f"({e})" for e in QUALITY_DIMS.values())
    sql_cand = f"SELECT COUNT(*) FROM cohort_base WHERE {all_conds} AND has_npl = 0 AND has_exd = 0"
    cand_cnt = con.execute(sql_cand).fetchone()[0]
    sql_cand_b = f"SELECT COUNT(*) FROM cohort_base WHERE {all_conds} AND has_npl = 1"
    cand_bad = con.execute(sql_cand_b).fetchone()[0]

    result = {
        "schema_version": "4.0-cohort",
        "slice": slice_dt,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "control": {
            "normal_cnt": len(normal_set),
            "bad_cnt": len(bad_set),
            "normal_profile": normal_profile,
            "bad_profile": bad_profile,
        },
        "themes": themes,
        "quality_features": quality,
        "quality_candidate": {
            "desc": "同时满足全部优质特征的正常客户（可准入候选）",
            "candidate_cnt": int(cand_cnt),
            "candidate_bad_cnt": int(cand_bad),
            "bad_within": round(cand_bad / (cand_cnt + cand_bad), 4) if (cand_cnt + cand_bad) else None,
        },
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ 客群归因 完成 → {args.out} | 耗时 {time.time()-t_start:.1f}s")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
