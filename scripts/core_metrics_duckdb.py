#!/usr/bin/env python3
"""core_metrics_duckdb.py — 核心指标计算（DuckDB/Parquet 版，替代 CSV 流式）

用法:
    python3 scripts/core_metrics_duckdb.py --data-dir "数据文件duckdb/parquet" \\
        --slice 20260831 --out metrics.json

口径（对齐《信贷基础概念速查》）：
- 农户贷款 = BUS_BREED_CD 以 'A70' 开头
- 不良 = RSK_CLS_CD 以 '3'/'4'/'5' 开头
- 不良率 = 不良余额(FORM_BAL_RMB) / 全部余额
- DuckDB 全量聚合，无采样误差，17GB 表秒级完成
"""
import argparse
import json
import os
import sys
import time
from collections import defaultdict

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


def parquet_glob(data_dir, table):
    return os.path.join(data_dir, table, "part-*.parquet").replace("\\", "/")


def main():
    ap = argparse.ArgumentParser(description="核心指标计算 (DuckDB)")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--slice", default="20260831")
    ap.add_argument("--out", default="metrics.json")
    ap.add_argument("--log", default="query_log.md", help="查询日志输出路径（内部记录，不落入报告）")
    args = ap.parse_args()

    qlog = QueryLog(path=args.log, title="查询日志（内部工作记录）")
    con = duckdb.connect()
    t_start = time.time()

    # 自动探测切片（若指定切片在表中不存在，用最新切片）
    vch_glob = parquet_glob(args.data_dir, "G_00PF_PEAS_LN_VCH_DV")
    try:
        available = con.execute(
            f"SELECT DISTINCT DATA_DAT FROM read_parquet('{vch_glob}') ORDER BY 1 DESC LIMIT 5"
        ).fetchall()
        available = [r[0] for r in available]
    except Exception as e:
        print(f"错误：无法读取凭证表 {e}", file=sys.stderr)
        return 2
    if not available:
        print("错误：凭证表无数据", file=sys.stderr)
        return 2
    slice_dt = args.slice if args.slice in available else available[0]
    if slice_dt != args.slice:
        qlog.add(stage="Step1 核心指标(DD)", table="G_00PF_PEAS_LN_VCH_DV",
                 query=f"指定切片 {args.slice} 不存在，自动改用 {slice_dt}",
                 result=f"可用切片: {available}", thought="DuckDB 自动探测最新切片")

    qlog.add(stage="Step1 核心指标(DD)", table="G_00PF_PEAS_LN_VCH_DV",
             query=f"全量聚合 DATA_DAT={slice_dt} 且 BUS_BREED_CD LIKE 'A70%'",
             result="待计算", thought="DuckDB 单条 SQL 完成分组聚合，替代 CSV 流式循环")

    # 单条 SQL 完成：总体 + 机构 + 客户经理 + 业务品种 + 担保方式 + 逾期分段
    # 去重口径：凭证数 vch_cnt=COUNT(DISTINCT FORM_NO)；客户数 cust_cnt=COUNT(DISTINCT CUST_NO)；
    # 个人数 person_cnt=COUNT(DISTINCT ID_CARD_NO)（经建档档案映射，同一证件多客户号归并）
    sql = f"""
    WITH v AS (
        SELECT v.*, d.ID_CARD_NO
        FROM read_parquet('{vch_glob}') v
        LEFT JOIN (
            SELECT CUST_NO, ID_CARD_NO
            FROM read_parquet('{parquet_glob(args.data_dir, "G_00PL_PEAS_DOC_INFO_DV")}')
            WHERE DATA_DAT = '{slice_dt}'
            GROUP BY CUST_NO, ID_CARD_NO
        ) d ON d.CUST_NO = v.CUST_NO
        WHERE v.DATA_DAT = '{slice_dt}' AND v.BUS_BREED_CD LIKE 'A70%'
    )
    SELECT
        COUNT(*) AS cnt,
        COUNT(DISTINCT FORM_NO) AS vch_cnt,
        COUNT(DISTINCT CUST_NO) AS cust_cnt,
        COUNT(DISTINCT ID_CARD_NO) AS person_cnt,
        COALESCE(SUM(CAST(FORM_BAL_RMB AS DOUBLE)),0) AS bal,
        COALESCE(SUM(CASE WHEN substr(RSK_CLS_CD,1,1) IN ('3','4','5') THEN CAST(FORM_BAL_RMB AS DOUBLE) ELSE 0 END),0) AS npl_bal,
        SUM(CASE WHEN substr(RSK_CLS_CD,1,1) IN ('3','4','5') THEN 1 ELSE 0 END) AS npl_cnt,
        COALESCE(SUM(CASE WHEN CAST(EXD_DAYS AS BIGINT) > 0 THEN CAST(FORM_BAL_RMB AS DOUBLE) ELSE 0 END),0) AS exd_bal,
        SUM(CASE WHEN CAST(EXD_DAYS AS BIGINT) > 0 THEN 1 ELSE 0 END) AS exd_cnt,
        SUM(CASE WHEN CAST(EXD_DAYS AS BIGINT) > 0 AND CAST(EXD_DAYS AS BIGINT) <= 30 THEN CAST(FORM_BAL_RMB AS DOUBLE) ELSE 0 END) AS seg_30,
        SUM(CASE WHEN CAST(EXD_DAYS AS BIGINT) > 30 AND CAST(EXD_DAYS AS BIGINT) <= 90 THEN CAST(FORM_BAL_RMB AS DOUBLE) ELSE 0 END) AS seg_90,
        SUM(CASE WHEN CAST(EXD_DAYS AS BIGINT) > 90 AND CAST(EXD_DAYS AS BIGINT) <= 180 THEN CAST(FORM_BAL_RMB AS DOUBLE) ELSE 0 END) AS seg_180,
        SUM(CASE WHEN CAST(EXD_DAYS AS BIGINT) > 180 THEN CAST(FORM_BAL_RMB AS DOUBLE) ELSE 0 END) AS seg_gt180
    FROM v
    """
    try:
        r = con.execute(sql).fetchone()
    except Exception as e:
        print(f"错误：聚合失败 {e}", file=sys.stderr)
        return 2

    (cnt, vch_cnt, cust_cnt, person_cnt, bal, npl_bal, npl_cnt, exd_bal, exd_cnt,
     seg_30, seg_90, seg_180, seg_gt180) = r

    # 分组汇总：机构 / 客户经理 / 业务品种 / 担保方式（含凭证/客户/个人去重口径）
    def group_sql(group_col, alias):
        return f"""
        SELECT COALESCE({group_col},'未知') AS grp,
               COUNT(*) AS cnt,
               COUNT(DISTINCT FORM_NO) AS vch_cnt,
               COUNT(DISTINCT v.CUST_NO) AS cust_cnt,
               COUNT(DISTINCT d.ID_CARD_NO) AS person_cnt,
               COALESCE(SUM(CAST(v.FORM_BAL_RMB AS DOUBLE)),0) AS bal,
               COALESCE(SUM(CASE WHEN substr(v.RSK_CLS_CD,1,1) IN ('3','4','5') THEN CAST(v.FORM_BAL_RMB AS DOUBLE) ELSE 0 END),0) AS npl_bal,
               SUM(CASE WHEN substr(v.RSK_CLS_CD,1,1) IN ('3','4','5') THEN 1 ELSE 0 END) AS npl_cnt
        FROM read_parquet('{vch_glob}') v
        LEFT JOIN (
            SELECT CUST_NO, ID_CARD_NO
            FROM read_parquet('{parquet_glob(args.data_dir, "G_00PL_PEAS_DOC_INFO_DV")}')
            WHERE DATA_DAT = '{slice_dt}'
            GROUP BY CUST_NO, ID_CARD_NO
        ) d ON d.CUST_NO = v.CUST_NO
        WHERE v.DATA_DAT = '{slice_dt}' AND v.BUS_BREED_CD LIKE 'A70%'
        GROUP BY 1
        """

    groups = {}
    for gname, gcol in [("by_org", "DISB_ORG_COD"), ("by_mgr", "MAGR_CD"),
                        ("by_breed", "substr(BUS_BREED_CD,1,5)"), ("by_grte", "GRTE_MOD_CD")]:
        try:
            rows = con.execute(group_sql(gcol, gname)).fetchall()
        except Exception as e:
            qlog.add(stage="Step1 核心指标(DD)", table="G_00PF_PEAS_LN_VCH_DV",
                     query=f"分组 {gname} (col={gcol})", result=f"ERROR {str(e)[:80]}",
                     thought="DuckDB 分组聚合失败")
            rows = []
        items = []
        for grp, c, vc, cc, pc, b, nb, nc in rows:
            items.append({
                "group": str(grp),
                "bal": round(float(b), 2),
                "npl_bal": round(float(nb), 2),
                "npl_rate": round(float(nb) / float(b), 6) if b else None,
                "cnt": int(c),
                "vch_cnt": int(vc),
                "npl_cnt": int(nc),
                "cust_cnt": int(cc),
                "person_cnt": int(pc),
            })
        items.sort(key=lambda x: -x["bal"])
        groups[gname] = items

    exd_seg = {
        "1-30天": {"bal": round(float(seg_30), 2),
                    "cnt": int(con.execute(f"""
                        SELECT COUNT(*) FROM read_parquet('{vch_glob}')
                        WHERE DATA_DAT='{slice_dt}' AND BUS_BREED_CD LIKE 'A70%'
                          AND CAST(EXD_DAYS AS BIGINT) > 0 AND CAST(EXD_DAYS AS BIGINT) <= 30""").fetchone()[0])},
        "31-90天": {"bal": round(float(seg_90), 2),
                     "cnt": int(con.execute(f"""
                        SELECT COUNT(*) FROM read_parquet('{vch_glob}')
                        WHERE DATA_DAT='{slice_dt}' AND BUS_BREED_CD LIKE 'A70%'
                          AND CAST(EXD_DAYS AS BIGINT) > 30 AND CAST(EXD_DAYS AS BIGINT) <= 90""").fetchone()[0])},
        "91-180天": {"bal": round(float(seg_180), 2),
                      "cnt": int(con.execute(f"""
                        SELECT COUNT(*) FROM read_parquet('{vch_glob}')
                        WHERE DATA_DAT='{slice_dt}' AND BUS_BREED_CD LIKE 'A70%'
                          AND CAST(EXD_DAYS AS BIGINT) > 90 AND CAST(EXD_DAYS AS BIGINT) <= 180""").fetchone()[0])},
        ">180天": {"bal": round(float(seg_gt180), 2),
                    "cnt": int(con.execute(f"""
                        SELECT COUNT(*) FROM read_parquet('{vch_glob}')
                        WHERE DATA_DAT='{slice_dt}' AND BUS_BREED_CD LIKE 'A70%'
                          AND CAST(EXD_DAYS AS BIGINT) > 180""").fetchone()[0])},
    }

    result = {
        "schema_version": "2.0-duckdb",
        "slice": slice_dt,
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "overall": {
            "bal": round(float(bal), 2),
            "npl_bal": round(float(npl_bal), 2),
            "npl_rate": round(float(npl_bal) / float(bal), 6) if bal else None,
            "exd_bal": round(float(exd_bal), 2),
            "cnt": int(cnt),
            "vch_cnt": int(vch_cnt),
            "npl_cnt": int(npl_cnt),
            "cust_cnt": int(cust_cnt),
            "person_cnt": int(person_cnt),
            "per_vch_bal": round(float(bal) / int(vch_cnt), 2) if vch_cnt else None,
            "per_cust_bal": round(float(bal) / int(cust_cnt), 2) if cust_cnt else None,
        },
        "by_org": groups["by_org"],
        "by_mgr": groups["by_mgr"],
        "by_breed": groups["by_breed"],
        "by_grte": groups["by_grte"],
        "exd_seg": exd_seg,
        "warnings": [] if bal else [f"切片 {slice_dt} 无农户贷款余额"],
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    qlog.add(stage="Step1 核心指标(DD)", table="G_00PF_PEAS_LN_VCH_DV",
             query=f"DATA_DAT={slice_dt} AND BUS_BREED_CD LIKE 'A70%'",
             result=(f"合同 {result['overall']['cnt']} 笔，余额 {result['overall']['bal']:,.2f}，"
                     f"不良率 {result['overall']['npl_rate']:.2%}") if result["overall"]["npl_rate"] is not None
             else f"切片 {slice_dt} 无数据",
             thought="DuckDB 单条 SQL 完成全量聚合，无采样误差")

    print(f"✅ 核心指标(DuckDB) 完成 → {args.out} | 耗时 {time.time()-t_start:.1f}s")
    print(f"   切片 {slice_dt}：合同 {result['overall']['cnt']} 笔，余额 {result['overall']['bal']:,.2f}，"
          f"不良率 {result['overall']['npl_rate']:.2%}" if result["overall"]["npl_rate"] is not None
          else f"   切片 {slice_dt}：无数据")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
