#!/usr/bin/env python3
"""theme_mining.py — 复合风险归因主题挖掘器（受约束搜索，非纯暴力）

思路（对齐目标：大范围深层次挖掘复合风险因素归因主题）：
  纯暴力遍历 63 特征 2-5 阶组合 ≈ 766 万，21 天且假阳性 7,660。
  改为三层漏斗：
    第1层 候选生成：特征→客户集合，两两 Jaccard 重叠预筛（只保留重叠显著的对）
    第2层 统计验证：交集客群不良率 lift（vs 全辖）、增量贡献（vs 单特征）、规模下限
    第3层 业务过滤：跨环节组合（贷前×贷后 / 准入×管理）优先，写入候选清单

用法:
    python3 scripts/theme_mining.py --data-dir 数据文件duckdb/parquet \\
        --slice 20260831 --out mining_candidates.json [--log query_log.md]
"""
import argparse
import json
import os
import sys
import time
from itertools import combinations

import duckdb

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ============ 特征池：feature_id → 客户集合判据 ============
# stage: 业务环节（贷前准入/贷中审查/贷后管理/管理与行为），跨环节组合更有复合归因意义
# mgr_expand: 经理级→客户级展开；need_map: 证件号→客户号映射；is_vch: 凭证级
FEATURE_POOL = {
    # ---- 贷前准入 ----
    3:  {"desc": "低评分准入(SCRE<600)", "table": "G_00PL_IDV_LN_CUST_ACARD_SCRE_DV",
         "key": "CUST_NO", "cond": "CAST(SCRE AS DOUBLE) < 600", "stage": "贷前准入"},
    16: {"desc": "信息录入失真(FAS虚增)", "table": "B_00DT_FAS_ANL_SITU_DOC_H",
         "key": "ID_CARD_NO", "need_map": True,
         "cond": "CAST(TOT_DPS AS DOUBLE) > 0 AND CAST(TOT_DPS AS DOUBLE)/NULLIF(CAST(TOT_AST AS DOUBLE),0) > 1",
         "stage": "贷前准入"},
    45: {"desc": "裸贷户(总资产=0)", "table": "B_00DT_FAS_ANL_SITU_DOC_H",
         "key": "ID_CARD_NO", "need_map": True,
         "cond": "CAST(TOT_AST AS DOUBLE) = 0", "stage": "贷前准入"},
    39: {"desc": "收入覆盖不足(年收入<5万)", "table": "B_00DT_FAS_FMLY_SITU_DOC_H",
         "key": "ID_CARD_NO", "need_map": True,
         "cond": "CAST(FMLY_ANNL_INCM AS DOUBLE) < 50000", "stage": "贷前准入"},
    22: {"desc": "多实体同址(地址交叉)", "table": "G_00PL_PEAS_LN_ADDR_CHEK_DV",
         "key": "CUST_NO", "cond": "MUL_ENTY_SAME_BUS_SITE_IND = '1'", "stage": "贷前准入"},
    # ---- 贷后管理 ----
    44: {"desc": "还款行为恶化(逾期本金>0)", "table": "G_00PL_IDV_LN_ARG_EXD_DV",
         "key": "FORM_NO", "is_vch": True,
         "cond": "CAST(EXD_CAP AS DOUBLE) > 0", "stage": "贷后管理"},
    9:  {"desc": "贷后任务未办结", "table": "B_00FT_PEAS_LN_DPSE_TASK_DTAL",
         "key": "CUST_NO", "cond": "BUS_STS IN ('00','50')", "stage": "贷后管理"},
    # ---- 管理与行为 ----
    17: {"desc": "客户经理与客户资金往来", "table": "S_00PF_PEAS_MGR_LN_RISK_C4",
         "key": "CUST_ID_NO", "mgr_expand": True,
         "cond": "CAST(COALESCE(NULLIF(FND_CLU_CNT_PEAS,'\\N'),'0') AS BIGINT) > 0",
         "stage": "管理与行为"},
    14: {"desc": "批量建档(同日≥5户)", "table": "S_00PF_PEAS_MGR_LN_RISK_C4",
         "key": "CUST_ID_NO", "mgr_expand": True,
         "cond": "CAST(COALESCE(NULLIF(SAME_DAT_CUST_CNT,'\\N'),'0') AS BIGINT) >= 5",
         "stage": "管理与行为"},
    # ---- 总览高恶化档位（产品/客群/产业） ----
    51: {"desc": "小额贷款(额度≤5万)", "table": "G_00PF_PEAS_LN_VCH_DV",
         "key": "CUST_NO", "vch_grp": True,
         "cond": "CAST(LN_AMT_RMB AS DOUBLE) <= 50000", "stage": "产品"},
    52: {"desc": "脱贫户", "table": "G_00PL_PEAS_DOC_INFO_DV",
         "key": "CUST_NO", "cond": "ADMI_SUBJ_TYP = '01'", "stage": "客群"},
    53: {"desc": "存量老资产(≤2023放款)", "table": "G_00PF_PEAS_LN_VCH_DV",
         "key": "CUST_NO", "vch_grp": True,
         "cond": "substr(LN_DAT,1,4) <= '2023'", "stage": "账龄"},
    54: {"desc": "居住1年及以下", "table": "G_00PL_PEAS_DOC_INFO_DV",
         "key": "CUST_NO", "cond": "CAST(COALESCE(CUR_PLCE_RES_YEAR,'0') AS BIGINT) <= 1",
         "stage": "客群"},
    55: {"desc": "抵押担保", "table": "G_00PF_PEAS_LN_VCH_DV",
         "key": "CUST_NO", "vch_grp": True,
         "cond": "GRTE_MOD_CD = '0201'", "stage": "产品"},
    # ---- 分析文档新增特征（风险特征关联组合分析.md 可数据化部分） ----
    15: {"desc": "调查造假(地址交叉不一致)", "table": "G_00PL_PEAS_LN_ADDR_CHEK_DV",
         "key": "CUST_NO",
         "cond": "(BUS_DIV_AND_BUS_DTAL_ADDR_INCY_IND = '1' OR PERM_DIV_AND_PERM_DTAL_ADDR_INCY_IND = '1')",
         "stage": "贷前准入"},
    34: {"desc": "征信查询过多(近6月>=10)", "table": "P_00CIE_CPS_INDECATE_SIMPLEPROCESS",
         "key": "CERTNO", "need_map": True, "map_from": "CERTNO",
         "cond": "CAST(COALESCE(NULLIF(Indicate_value,''),'0') AS DOUBLE) >= 10 AND Indicate_name = '近6个月征信查询次数'",
         "stage": "贷前准入"},
    35: {"desc": "有被拒贷记录", "table": "P_00CIE_CPS_INDECATE_SIMPLEPROCESS",
         "key": "CERTNO", "need_map": True, "map_from": "CERTNO",
         "cond": "CAST(COALESCE(NULLIF(Indicate_value,''),'0') AS DOUBLE) > 0 AND Indicate_name = '无信用记录，但有查询记录'",
         "stage": "贷前准入"},
    36: {"desc": "N年内不良记录", "table": "P_00CIE_CPS_INDECATE_SIMPLEPROCESS",
         "key": "CERTNO", "need_map": True, "map_from": "CERTNO",
         "cond": "CAST(COALESCE(NULLIF(Indicate_value,''),'0') AS DOUBLE) > 0 AND Indicate_name = '近两年累计逾期次数（个贷）'",
         "stage": "贷前准入"},
    2:  {"desc": "无抵押缓释(信用贷)", "table": "G_00PF_PEAS_LN_VCH_DV",
         "key": "CUST_NO", "vch_grp": True,
         "cond": "GRTE_MOD_CD = '0101'", "stage": "产品"},
    13: {"desc": "大额信用(信用且>30万)", "table": "G_00PF_PEAS_LN_VCH_DV",
         "key": "CUST_NO", "vch_grp": True,
         "cond": "GRTE_MOD_CD = '0101' AND CAST(LN_AMT_RMB AS DOUBLE) > 300000", "stage": "产品"},
    27: {"desc": "异地放款(发放机构异于常住)", "table": "G_00PF_PEAS_LN_VCH_DV",
         "key": "CUST_NO", "vch_grp": True,
         "cond": "substr(DISB_ORG_COD,1,4) NOT IN ('7961','7962','7963','7964')",
         "stage": "贷前准入"},
}


def parquet_glob(data_dir, table):
    return os.path.join(data_dir, table, "part-*.parquet").replace("\\", "/")


def latest_slice(con, data_dir, table):
    try:
        return con.execute(f"SELECT max(DATA_DAT) FROM read_parquet('{parquet_glob(data_dir, table)}')").fetchone()[0]
    except Exception:
        return None


def extract_sample(con, data_dir, cfg, qlog):
    """提取特征客户集合（返回 set）"""
    tbl = cfg["table"]
    sl = cfg.get("slice_val") or latest_slice(con, data_dir, tbl)
    if cfg.get("mgr_expand"):
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
        return {r[0] for r in con.execute(sql2).fetchall()}
    if cfg.get("is_vch"):
        sql = f"""SELECT DISTINCT FORM_NO AS K FROM read_parquet('{parquet_glob(data_dir, tbl)}')
                  WHERE ({cfg['cond']})"""
        rows = con.execute(sql).fetchall()
        return {r[0] for r in rows}
    if cfg.get("vch_grp"):
        sql = f"""SELECT DISTINCT CUST_NO AS K FROM read_parquet('{parquet_glob(data_dir, tbl)}')
                  WHERE ({cfg['cond']})"""
        if sl:
            sql += f" AND DATA_DAT = '{sl}'"
        return {r[0] for r in con.execute(sql).fetchall()}
    if cfg.get("need_map"):
        sl2 = latest_slice(con, data_dir, "G_00PL_PEAS_DOC_INFO_DV")
        map_from = cfg.get("map_from", "ID_CARD_NO")  # 默认 ID_CARD_NO，征信表为 CERTNO
        sql = f"""SELECT DISTINCT m.CUST_NO AS K
                  FROM read_parquet('{parquet_glob(data_dir, tbl)}') f
                  JOIN read_parquet('{parquet_glob(data_dir, "G_00PL_PEAS_DOC_INFO_DV")}') m
                    ON m.ID_CARD_NO = f.{map_from} AND m.DATA_DAT = '{sl2}'
                  WHERE ({cfg['cond']})"""
        if sl:
            sql += f" AND f.DATA_DAT = '{sl}'"
        return {r[0] for r in con.execute(sql).fetchall()}
    sql = f"""SELECT DISTINCT {cfg['key']} AS K FROM read_parquet('{parquet_glob(data_dir, tbl)}')
              WHERE ({cfg['cond']})"""
    if sl:
        sql += f" AND DATA_DAT = '{sl}'"
    return {r[0] for r in con.execute(sql).fetchall()}


def jaccard(a, b):
    inter = len(a & b)
    if not inter:
        return 0.0
    union = len(a | b)
    return inter / union if union else 0.0


def lift_of(con, cohort_set, slice_dt, qlog):
    """计算客群不良率 lift（vs 全辖不良率）"""
    if not cohort_set:
        return None, None, None, None
    # 用凭证表算客群不良率
    ph = ",".join(f"('{k}')" for k in list(cohort_set)[:200000])
    con.execute("DROP TABLE IF EXISTS tmp_mining_members")
    con.execute(f"CREATE TEMP TABLE tmp_mining_members AS SELECT * FROM (VALUES {ph}) t(CUST_NO)")
    try:
        r = con.execute(f"""
            SELECT COUNT(DISTINCT v.CUST_NO),
                   SUM(CASE WHEN v.RSK_CLS_CD IN ('30','40','50') THEN 1 ELSE 0 END)
            FROM read_parquet('{parquet_glob(con, '')}' )
            """).fetchone()  # placeholder，下方覆盖
    except Exception:
        pass
    # 直接查 cohort 客户在凭证表的不良
    vch_glob = parquet_glob(os.path.dirname(os.path.dirname(parquet_glob("", ""))) + "", "")
    return None, None, None, None


def main():
    ap = argparse.ArgumentParser(description="复合风险归因主题挖掘器")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--slice", default="20260831")
    ap.add_argument("--out", default="mining_candidates.json")
    ap.add_argument("--log", default="query_log.md")
    ap.add_argument("--min-jaccard", type=float, default=0.02, help="Jaccard 预筛阈值")
    ap.add_argument("--min-lift", type=float, default=1.5, help="组合 lift 下限")
    ap.add_argument("--min-size", type=int, default=30, help="交集客群规模下限")
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

    # 切片
    vch_glob = parquet_glob(args.data_dir, "G_00PF_PEAS_LN_VCH_DV")
    avail = con.execute(f"SELECT DISTINCT DATA_DAT FROM read_parquet('{vch_glob}') ORDER BY 1 DESC LIMIT 3").fetchall()
    slice_dt = args.slice if any(r[0] == args.slice for r in avail) else avail[0][0]

    # 全辖不良率基线（客户级：有不良凭证客户 / 全部客户）
    base = con.execute(f"""
        WITH v AS (
            SELECT CUST_NO,
                   MAX(CASE WHEN RSK_CLS_CD IN ('30','40','50') THEN 1 ELSE 0 END) AS has_npl
            FROM read_parquet('{vch_glob}')
            WHERE DATA_DAT = '{slice_dt}' AND BUS_BREED_CD LIKE 'A70%'
            GROUP BY 1
        )
        SELECT COUNT(*), COALESCE(SUM(has_npl),0) FROM v
    """).fetchone()
    total_cust, total_bad = int(base[0]), int(base[1])
    base_bad_rate = total_bad / total_cust if total_cust else 0
    print(f"全辖：客户 {total_cust} / 不良 {total_bad} / 不良率 {base_bad_rate:.4f}")

    # 1) 特征→客户集合
    sets = {}
    for fid, cfg in FEATURE_POOL.items():
        s = extract_sample(con, args.data_dir, cfg, qlog)
        if len(s) >= 5:
            sets[fid] = s
    print(f"特征池：{len(sets)} 个特征客户集合")

    # 2) Jaccard 预筛（两两）
    fids = list(sets.keys())
    pairs = []
    for a, b in combinations(fids, 2):
        j = jaccard(sets[a], sets[b])
        if j >= args.min_jaccard:
            pairs.append((a, b, j))
    pairs.sort(key=lambda x: -x[2])
    print(f"Jaccard≥{args.min_jaccard} 的候选对：{len(pairs)}")

    # 3) 交集 lift 验证
    candidates = []
    for a, b, j in pairs[:300]:
        inter = sets[a] & sets[b]
        if len(inter) < args.min_size:
            continue
        # 交集客群不良率（直接用集合查凭证表，分批避免超长）
        ph = ",".join(f"('{k}')" for k in list(inter)[:200000])
        con.execute("DROP TABLE IF EXISTS tmp_mining_members")
        con.execute(f"CREATE TEMP TABLE tmp_mining_members AS SELECT * FROM (VALUES {ph}) t(CUST_NO)")
        r = con.execute(f"""
            SELECT COUNT(DISTINCT v.CUST_NO),
                   SUM(CASE WHEN v.RSK_CLS_CD IN ('30','40','50') THEN 1 ELSE 0 END)
            FROM read_parquet('{vch_glob}') v
            JOIN tmp_mining_members m ON m.CUST_NO = v.CUST_NO
            WHERE v.DATA_DAT = '{slice_dt}' AND v.BUS_BREED_CD LIKE 'A70%'
        """).fetchone()
        inter_cust, inter_bad = int(r[0]), int(r[1] or 0)
        if inter_cust < args.min_size:
            continue
        inter_bad_rate = inter_bad / inter_cust if inter_cust else 0
        lift = inter_bad_rate / base_bad_rate if base_bad_rate else 0
        if lift < args.min_lift:
            continue
        # 单特征 lift
        def feat_lift(s):
            ph2 = ",".join(f"('{k}')" for k in list(s)[:200000])
            con.execute("DROP TABLE IF EXISTS tmp_mining_f")
            con.execute(f"CREATE TEMP TABLE tmp_mining_f AS SELECT * FROM (VALUES {ph2}) t(CUST_NO)")
            r2 = con.execute(f"""
                SELECT COUNT(DISTINCT v.CUST_NO),
                       SUM(CASE WHEN v.RSK_CLS_CD IN ('30','40','50') THEN 1 ELSE 0 END)
                FROM read_parquet('{vch_glob}') v
                JOIN tmp_mining_f f ON f.CUST_NO = v.CUST_NO
                WHERE v.DATA_DAT = '{slice_dt}' AND v.BUS_BREED_CD LIKE 'A70%'
            """).fetchone()
            return (float(r2[1] or 0) / r2[0]) / base_bad_rate if r2[0] else 0
        lift_a = feat_lift(sets[a])
        lift_b = feat_lift(sets[b])
        incr = lift / max(lift_a, lift_b, 0.0001)  # 增量贡献
        cross_stage = FEATURE_POOL[a]["stage"] != FEATURE_POOL[b]["stage"]
        candidates.append({
            "combo": f"{FEATURE_POOL[a]['desc']} ∩ {FEATURE_POOL[b]['desc']}",
            "fid_a": a, "fid_b": b,
            "stage_a": FEATURE_POOL[a]["stage"], "stage_b": FEATURE_POOL[b]["stage"],
            "cross_stage": cross_stage,
            "jaccard": round(j, 4),
            "cohort_size": inter_cust,
            "bad_cnt": inter_bad,
            "bad_rate": round(inter_bad_rate, 4),
            "lift": round(lift, 2),
            "lift_a": round(lift_a, 2), "lift_b": round(lift_b, 2),
            "increment": round(incr, 2),
            "suggest_theme": None,
        })
    candidates.sort(key=lambda x: -x["lift"])
    print(f"显著候选（lift≥{args.min_lift}，规模≥{args.min_size}）：{len(candidates)}")

    # 输出 Top
    for c in candidates[:20]:
        tag = "跨环节" if c["cross_stage"] else "同环节"
        print(f"  [{c['combo']}] 客群{c['cohort_size']} 不良率{c['bad_rate']:.2%} "
              f"lift={c['lift']}x (单特征 {c['lift_a']}x/{c['lift_b']}x) {tag}")

    result = {
        "schema_version": "5.0-mining",
        "slice": slice_dt,
        "base": {"total_cust": total_cust, "total_bad": total_bad,
                 "bad_rate": round(base_bad_rate, 6)},
        "feature_cnt": len(sets),
        "pair_cnt": len(pairs),
        "params": {"min_jaccard": args.min_jaccard, "min_lift": args.min_lift,
                   "min_size": args.min_size},
        "candidates": candidates,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ 主题挖掘 完成 → {args.out} | 耗时 {time.time()-t_start:.1f}s")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
