#!/usr/bin/env python3
"""theme_deep_dive_duckdb.py — 主题深挖（DuckDB/Parquet 版，替代 CSV）

用法:
    python3 scripts/theme_deep_dive_duckdb.py --attribution attribution.json \\
        --data-dir "数字员工工作区/数据文件duckdb/parquet" \\
        --out deep_dive.json [--log query_log.md]

定位（对齐五步流程第3步）：生成归因主题后，根据主题命中的基础特征，
提取命中客户样本集合，反向联查账单、核销、担保、存款、金融资产等关联表，
计算「命中组 vs 全辖」的指标差异，验证主题相关性与证据链。

v2.0 DuckDB：配置驱动 SQL 三段式（样本提取 → 关联聚合 → 分组对比）。
每张表自动探测最新 DATA_DAT 切片，全量聚合无采样误差。
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

try:
    from query_log import QueryLog
except ImportError:
    class QueryLog:
        def __init__(self, path=None, title=""):
            self.path = path
            self.entries = []
        def add(self, stage, table, query, result, thought):
            self.entries.append({"stage": stage, "table": table, "query": query,
                                 "result": result, "thought": thought})
        def save(self):
            return self.entries


# ============ 驱动特征配置：样本判据（SQL WHERE 片段） ============
# key: 表 | join_key: 样本键 | cust_key: 映射后客户键 | condition: 命中判据
SAMPLE_FEATURES = {
    3:  {"table": "G_00PL_IDV_LN_CUST_ACARD_SCRE_DV", "join_key": "CUST_NO",
         "condition": "CAST(SCRE AS DOUBLE) < 600",
         "desc": "低评分准入（SCRE<600）客户"},
    9:  {"table": "B_00FT_PEAS_LN_DPSE_TASK_DTAL", "join_key": "CUST_NO",
         "condition": "BUS_STS IN ('00','50')",
         "desc": "贷后任务未办结客户"},
    16: {"table": "B_00DT_FAS_ANL_SITU_DOC_H", "join_key": "ID_CARD_NO", "need_id_map": True,
         "condition": "CAST(TOT_DPS AS DOUBLE) > 0 AND CAST(TOT_DPS AS DOUBLE)/NULLIF(CAST(TOT_AST AS DOUBLE),0) > 1",
         "desc": "信息失真（负债>资产）客户"},
    39: {"table": "B_00DT_FAS_FMLY_SITU_DOC_H", "join_key": "ID_CARD_NO", "need_id_map": True,
         "condition": "CAST(FMLY_ANNL_INCM AS DOUBLE) < 50000",
         "desc": "收入覆盖不足（年收入<5万）客户"},
    44: {"table": "G_00PL_IDV_LN_ARG_EXD_DV", "join_key": "FORM_NO", "is_vch": True,
         "condition": "CAST(EXD_CAP AS DOUBLE) > 0",
         "desc": "还款恶化（逾期本金>0）凭证"},
    45: {"table": "B_00DT_FAS_ANL_SITU_DOC_H", "join_key": "ID_CARD_NO", "need_id_map": True,
         "condition": "CAST(TOT_AST AS DOUBLE) = 0",
         "desc": "裸贷户（总资产=0）客户"},
}

# ============ 总览驱动样本（来自 core_overview 高恶化档位，独立于归因主题） ============
# 用途：把完整总览中发现的高不良率档位（小额/脱贫户/存量/居住短/抵押）作为深挖样本，
# 反向联查关联表，验证「哪类产品/客群在恶化」背后的行为证据（账单/核销/存款/担保等）。
OVERVIEW_SAMPLES = {
    "OV01": {"table": "G_00PF_PEAS_LN_VCH_DV", "join_key": "CUST_NO", "is_vch_grp": True,
             "condition": "CAST(LN_AMT_RMB AS DOUBLE) <= 50000",
             "desc": "小额贷款客户（单笔额度≤5万，档不良率8.16%）"},
    "OV02": {"table": "G_00PL_PEAS_DOC_INFO_DV", "join_key": "CUST_NO",
             "condition": "ADMI_SUBJ_TYP = '01'",
             "desc": "脱贫户客户（档不良率5.24%）"},
    "OV03": {"table": "G_00PF_PEAS_LN_VCH_DV", "join_key": "CUST_NO", "is_vch_grp": True,
             "condition": "substr(LN_DAT,1,4) <= '2023'",
             "desc": "存量老资产客户（2023年及以前放款，档不良率28.93%+）"},
    "OV04": {"table": "G_00PL_PEAS_DOC_INFO_DV", "join_key": "CUST_NO",
             "condition": "CAST(COALESCE(CUR_PLCE_RES_YEAR,'0') AS BIGINT) <= 1",
             "desc": "居住1年及以下客户（档不良率13.53%）"},
    "OV05": {"table": "G_00PF_PEAS_LN_VCH_DV", "join_key": "CUST_NO", "is_vch_grp": True,
             "condition": "GRTE_MOD_CD = '0201'",
             "desc": "抵押担保客户（档不良率20.86%）"},
}

# ============ 关联表配置：深挖目标（SQL 异常判据） ============
LINK_TABLES = {
    "凭证不良": {
        "table": "G_00PF_PEAS_LN_VCH_DV", "join_key": "CUST_NO",
        "condition": "substr(RSK_CLS_CD,1,1) IN ('3','4','5')",
        "desc": "名下有不良凭证（风险分类3/4/5）的客户占比",
    },
    "账单逾期": {
        "table": "G_00PL_IDV_LN_BILL_AMT", "join_key": "CUST_NO",
        "condition": "COALESCE(BILL_EXD_DAT,'') <> ''",
        "desc": "有转逾期日期账单的客户占比",
    },
    "核销暴露": {
        "table": "G_00PF_IDV_LN_VCH_CAN_LQDT_SECS_DV", "join_key": "CUST_NO",
        "condition": "CAST(CAN_CAP AS DOUBLE) > 0",
        "desc": "有核销本金记录的客户占比",
    },
    "无担保贷款": {
        "table": "S_00PL_IDV_LN_GRTE_RLN", "join_key": "CUST_NO",
        "condition": "COALESCE(GRTE_CTRT_GRTE,'') = ''",
        "desc": "担保合同担保方式为空（无担保）的客户占比",
    },
    "低存款": {
        "table": "S_00PF_IDV_DP_CUST_SUM", "join_key": "CUST_NO",
        "condition": "CAST(COALESCE(RMB_DP_BAL,'0') AS DOUBLE) <= 0",
        "desc": "存款余额≤0 的客户占比",
    },
    "低金融资产": {
        "table": "S_00PF_IDV_CUST_FA_SUM", "join_key": "CUST_NO",
        "condition": "CAST(COALESCE(FA_BAL,'0') AS DOUBLE) <= 0",
        "desc": "金融资产余额≤0 的客户占比",
    },
    "合同金额偏高": {
        "table": "G_00PF_IDV_LN_CTRT_DV", "join_key": "CUST_NO",
        "condition": "CAST(CTRT_AMT_RMB AS DOUBLE) > 1000000",
        "desc": "单笔合同金额>100万的客户占比",
    },
    "交易活跃": {
        "table": "S_00PF_SA_ACCT_TR_CUST_SUM", "join_key": "CUST_NO",
        "condition": "CAST(COALESCE(YEAR_TR_BAL_L1YER_ACLT,'0') AS DOUBLE) > 1000000",
        "desc": "近12月交易金额>100万的客户占比",
    },
    "有亲属关系": {
        "table": "G_00PL_IDV_CUST_RLN_INFO_H", "join_key": "CUST_NO",
        "condition": "COALESCE(RLN_TYP_CD,'') <> ''",
        "desc": "有亲属关系记录的客户占比",
    },
}

# 凭证级关联表（样本为凭证集合时用）
LINK_TABLES_FORM = {
    "逾期暴露": {
        "table": "G_00PL_IDV_LN_ARG_EXD_DV", "join_key": "FORM_NO",
        "condition": "CAST(EXD_CAP AS DOUBLE) > 0",
        "desc": "有逾期本金（EXD_CAP>0）的凭证占比",
    },
}


def parquet_glob(data_dir, table):
    return os.path.join(data_dir, table, "part-*.parquet").replace("\\", "/")


def latest_slice(con, data_dir, table):
    """自动探测每张表的最新 DATA_DAT 切片"""
    try:
        return con.execute(
            f"SELECT max(DATA_DAT) FROM read_parquet('{parquet_glob(data_dir, table)}')"
        ).fetchone()[0]
    except Exception:
        return None


def build_sample(con, data_dir, cfg, qlog):
    """SQL ① 样本提取：返回 (set, is_cust, desc)"""
    tbl = cfg["table"]
    sl = latest_slice(con, data_dir, tbl)
    t0 = time.time()
    if cfg.get("is_vch"):
        sql = f"""SELECT DISTINCT {cfg['join_key']} AS K FROM read_parquet('{parquet_glob(data_dir, tbl)}')
                  WHERE {cfg['condition']}"""
        rows = con.execute(sql).fetchall()
        sample = {r[0] for r in rows}
        is_cust = False
    elif cfg.get("is_vch_grp"):
        # 从凭证表按客户分组取客户集合（客户级深挖样本）
        sql = f"""SELECT DISTINCT {cfg['join_key']} AS K FROM read_parquet('{parquet_glob(data_dir, tbl)}')
                  WHERE ({cfg['condition']})"""
        if sl:
            sql += f" AND DATA_DAT = '{sl}'"
        rows = con.execute(sql).fetchall()
        sample = {r[0] for r in rows}
        is_cust = True
    elif cfg.get("need_id_map"):
        # 证件号 → 客户号（经建档档案映射）
        sl2 = latest_slice(con, data_dir, "G_00PL_PEAS_DOC_INFO_DV")
        sql = f"""SELECT DISTINCT m.CUST_NO AS K
                  FROM read_parquet('{parquet_glob(data_dir, tbl)}') f
                  JOIN read_parquet('{parquet_glob(data_dir, "G_00PL_PEAS_DOC_INFO_DV")}') m
                    ON m.ID_CARD_NO = f.ID_CARD_NO AND m.DATA_DAT = '{sl2}'
                  WHERE ({cfg['condition']})"""
        if sl:
            sql += f" AND f.DATA_DAT = '{sl}'"
        rows = con.execute(sql).fetchall()
        sample = {r[0] for r in rows}
        is_cust = True
    else:
        sql = f"""SELECT DISTINCT {cfg['join_key']} AS K FROM read_parquet('{parquet_glob(data_dir, tbl)}')
                  WHERE {cfg['condition']}"""
        if sl:
            sql += f" AND DATA_DAT = '{sl}'"
        rows = con.execute(sql).fetchall()
        sample = {r[0] for r in rows}
        is_cust = True
    qlog.add(stage="Step4 主题深挖(DD)", table=tbl,
             query=f"样本提取: {cfg['desc']} (slice={sl})",
             result=f"样本 {len(sample)} 个 | {time.time()-t0:.1f}s",
             thought="DuckDB 配置驱动 SQL 提取命中样本")
    return sample, is_cust, cfg["desc"]


def deep_dive_one(con, data_dir, sample, is_cust, qlog):
    """SQL ②③ 关联聚合 + 分组对比"""
    results = []
    tables = LINK_TABLES if is_cust else LINK_TABLES_FORM
    for link_name, cfg in tables.items():
        tbl = cfg["table"]
        sl = latest_slice(con, data_dir, tbl)
        t0 = time.time()
        # ② 关联聚合：按客户/凭证键 判断异常
        agg = f"""SELECT {cfg['join_key']} AS K,
                         MAX(CASE WHEN {cfg['condition']} THEN 1 ELSE 0 END) AS abn
                  FROM read_parquet('{parquet_glob(data_dir, tbl)}')
                  WHERE {cfg['join_key']} IS NOT NULL"""
        if sl:
            agg += f" AND DATA_DAT = '{sl}'"
        agg += " GROUP BY 1"
        # ③ 分组对比：LEFT JOIN 命中样本
        sql = f"""WITH agg AS ({agg})
                  SELECT COUNT(*) AS all_cnt,
                         SUM(CASE WHEN s.K IS NOT NULL THEN 1 ELSE 0 END) AS hit_cnt,
                         AVG(a.abn) AS all_rate,
                         AVG(CASE WHEN s.K IS NOT NULL THEN a.abn END) AS hit_rate
                  FROM agg a LEFT JOIN (SELECT * FROM (VALUES {','.join(f"('{k}')" for k in list(sample)[:200000])}) t(K)) s
                    ON s.K = a.K"""
        try:
            r = con.execute(sql).fetchone()
        except Exception as e:
            qlog.add(stage="Step4 主题深挖(DD)", table=tbl,
                     query=f"分组对比: {link_name}",
                     result=f"ERROR {str(e)[:80]}", thought="DuckDB JOIN 执行失败")
            continue
        all_cnt, hit_cnt, all_rate, hit_rate = r
        if not all_cnt or not hit_cnt:
            continue
        hit_abn = float(hit_rate or 0)
        all_abn = float(all_rate or 0)
        results.append({
            "link_table": link_name,
            "desc": cfg["desc"],
            "hit_cnt": int(hit_cnt),
            "all_cnt": int(all_cnt),
            "hit_rate": round(hit_abn, 4),
            "all_rate": round(all_abn, 4),
            "diff": round(hit_abn - all_abn, 4),
            "diff_pct": round((hit_abn - all_abn) * 100, 2),
        })
        qlog.add(stage="Step4 主题深挖(DD)", table=tbl,
                 query=f"关联 {link_name} (slice={sl})",
                 result=f"命中组 {hit_abn:.2%} vs 全辖 {all_abn:.2%} | {time.time()-t0:.1f}s",
                 thought="DuckDB 全量聚合，无采样误差")
    return results


def main():
    ap = argparse.ArgumentParser(description="主题深挖 DuckDB 版")
    ap.add_argument("--attribution", required=True)
    ap.add_argument("--data-dir", required=True,
                    default=r"C:\文档文件\繁星杯\决赛\数字员工工作区\数据文件duckdb\parquet")
    ap.add_argument("--out", default="deep_dive.json")
    ap.add_argument("--log", default="query_log.md")
    args = ap.parse_args()

    qlog = QueryLog(path=args.log, title="查询日志（DuckDB 内部工作记录）")
    con = duckdb.connect()
    t_start = time.time()

    with open(args.attribution, encoding="utf-8") as f:
        attr = json.load(f)

    deep_dive = []
    for ins in attr.get("strong_insights", [])[:6]:
        member_ids = [m.get("feature_id") for m in ins.get("members", [])]
        sampled = False
        topic_result = {"rule_id": ins["rule_id"], "name": ins["name"],
                        "essence": ins.get("essence", ""), "dives": []}
        for fid in member_ids:
            cfg = SAMPLE_FEATURES.get(fid)
            if not cfg:
                continue
            sample, is_cust, desc = build_sample(con, args.data_dir, cfg, qlog)
            if not sample:
                continue
            dives = deep_dive_one(con, args.data_dir, sample, is_cust, qlog)
            if dives:
                topic_result["dives"].append({
                    "sample_feature": fid,
                    "sample_desc": desc,
                    "sample_size": len(sample),
                    "links": dives,
                })
                sampled = True
        if sampled:
            deep_dive.append(topic_result)

    # 总览驱动样本深挖（独立于归因主题，来自 core_overview 高恶化档位）
    overview_dives = []
    for ov_id, cfg in OVERVIEW_SAMPLES.items():
        sample, is_cust, desc = build_sample(con, args.data_dir, cfg, qlog)
        if not sample:
            continue
        dives = deep_dive_one(con, args.data_dir, sample, is_cust, qlog)
        if dives:
            overview_dives.append({
                "ov_id": ov_id,
                "sample_desc": desc,
                "sample_size": len(sample),
                "links": dives,
            })

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"schema_version": "2.0-duckdb", "deep_dive": deep_dive,
                   "overview_dives": overview_dives},
                  f, ensure_ascii=False, indent=2)

    print(f"✅ 主题深挖(DuckDB) 完成 → {args.out} | 总耗时 {time.time()-t_start:.1f}s")
    for t in deep_dive:
        print(f"  [{t['rule_id']}] {t['name']}")
        for d in t["dives"]:
            print(f"    样本: {d['sample_desc']} ({d['sample_size']})")
            for link in d["links"]:
                print(f"      {link['link_table']}: 命中组 {link['hit_rate']:.2%} vs 全辖 {link['all_rate']:.2%} "
                      f"(diff {link['diff_pct']:+.2f}pp)")
    if overview_dives:
        print("  [总览驱动样本]")
        for d in overview_dives:
            print(f"    {d['ov_id']} {d['sample_desc']} ({d['sample_size']})")
            for link in d["links"][:4]:
                print(f"      {link['link_table']}: 命中组 {link['hit_rate']:.2%} vs 全辖 {link['all_rate']:.2%} "
                      f"(diff {link['diff_pct']:+.2f}pp)")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
