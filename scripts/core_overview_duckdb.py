#!/usr/bin/env python3
"""core_overview_duckdb.py — 完整总览 + 多维分类（含正常组对照）

定位（对齐 skill 迭代需求）：
1. 完整总览：不只输出不良/风险指标，而是同时输出 完整（全辖）、正常（非风险非不良）、
   关注、不良 四组数据作为相互参照；对照组对比揭示风险集中与偏移。
2. 多维分类总览：按 8 大维度 × 资产状态 分组统计，输出各组余额/笔数/客户数/占比/不良率，
   并给出「恶化档位」提示（该档不良率 vs 全辖不良率）。

8 大维度：
  产品与担保 / 客群与主体 / 产业与用途 / 时间与账龄 / 资产状态 /
  地理与区域 / 风险计量 / 管理与行为

用法:
    python3 scripts/core_overview_duckdb.py --data-dir "数据文件duckdb/parquet" \
        --slice 20260831 --out overview.json
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

# ============ 资产状态分组 ============
# 正常=分类10且无逾期；关注=20；不良=30/40/50
RSK_SQL = """
CASE
  WHEN RSK_CLS_CD = '10' AND COALESCE(CAST(EXD_DAYS AS BIGINT),0) = 0 THEN '正常'
  WHEN RSK_CLS_CD = '20' THEN '关注'
  WHEN RSK_CLS_CD IN ('30','40','50') THEN '不良'
  ELSE '其他'
END
"""

# ============ 维度配置（expr 为 DuckDB SQL 表达式；label_map 为值翻译） ============
DIMENSIONS = {
    "产品与担保": {
        "担保方式": {
            "expr": "GRTE_MOD_CD",
            "label_map": {"0101": "信用", "0201": "抵押", "0202": "保证",
                          "0308": "农担", "01010201": "信用(农担)",
                          "01010202": "信用(保证)", "0203": "抵押(农担)"},
        },
        "期限档": {
            "expr": "LN_TERM_CLS_CD",
            "label_map": {"102": "1年以内", "205": "1-5年", "305": "5年以上"},
        },
        "额度档": {
            "expr": """CASE
                WHEN CAST(LN_AMT_RMB AS DOUBLE) <= 50000 THEN '5万以下'
                WHEN CAST(LN_AMT_RMB AS DOUBLE) <= 100000 THEN '5-10万'
                WHEN CAST(LN_AMT_RMB AS DOUBLE) <= 300000 THEN '10-30万'
                WHEN CAST(LN_AMT_RMB AS DOUBLE) <= 1000000 THEN '30-100万'
                ELSE '100万以上' END""",
        },
        "还款方式": {
            "expr": "RPAY_MOD_CD",
            "label_map": {"01": "一次还本", "02": "分期还本", "04": "等额本息",
                          "05": "等额本金", "11": "其他"},
        },
        "循环标识": {
            "expr": "CYC_LN_IND",
            "label_map": {"1": "循环", "0": "非循环"},
        },
    },
    "客群与主体": {
        "主体类型": {
            "expr": "COALESCE(ADMI_SUBJ_TYP,'未知')",
            "label_map": {"01": "脱贫户", "03": "边缘户", "04": "一般农户",
                          "05": "一般农户(已核)", "06": "种养大户"},
        },
        "首贷与否": {
            # 客户在本切片凭证笔数（base 已预计算 v_per_cust_cnt）
            "expr": """CASE WHEN v_per_cust_cnt = 1 THEN '单笔凭证' ELSE '多笔凭证' END""",
        },
        "性别": {
            "expr": "COALESCE(SEX,'未知')",  # 哈希，仅分布
        },
        "居住年限": {
            "expr": """CASE
                WHEN CAST(COALESCE(CUR_PLCE_RES_YEAR,'0') AS BIGINT) <= 1 THEN '1年及以下'
                WHEN CAST(COALESCE(CUR_PLCE_RES_YEAR,'0') AS BIGINT) <= 5 THEN '2-5年'
                ELSE '5年以上' END""",
        },
    },
    "产业与用途": {
        "贷款用途": {
            "expr": "LN_USE_CLS_CD",
            "label_map": {"01": "生产经营", "02": "农业生产", "03": "消费",
                          "04": "其他", "14": "综合"},
        },
        "投向行业": {
            "expr": "LN_IVST_DIRE_OCPCLS_CD",
            "label_map": {"A001": "种植", "A201": "养殖", "E210": "农业综合",
                          "E902": "非农经营", "E302": "个体经营", "E205": "林果",
                          "D701": "其他"},
        },
    },
    "时间与账龄": {
        "放款年份": {
            "expr": "substr(COALESCE(LN_DAT,''),1,4)",
        },
        "账龄(月)": {
            "expr": """CASE
                WHEN CAST(EXD_DAYS AS BIGINT) <= 0 THEN '未逾期'
                WHEN CAST(EXD_DAYS AS BIGINT) <= 30 THEN 'M1(1-30天)'
                WHEN CAST(EXD_DAYS AS BIGINT) <= 60 THEN 'M2(31-60天)'
                WHEN CAST(EXD_DAYS AS BIGINT) <= 90 THEN 'M3(61-90天)'
                WHEN CAST(EXD_DAYS AS BIGINT) <= 180 THEN 'M4-M6(91-180天)'
                ELSE 'M6+(>180天)' END""",
        },
        "接续标识": {
            "expr": "CONT_LN_IND",
            "label_map": {"1": "接续", "0": "新发放"},
        },
    },
    "资产状态": {
        "五级分类": {
            "expr": "RSK_CLS_CD",
            "label_map": {"10": "正常", "20": "关注", "30": "次级", "40": "可疑", "50": "损失"},
        },
        "核销状态": {
            "expr": "COALESCE(CAN_STS_CD,'未核销')",
        },
    },
    "地理与区域": {
        "发放机构(省)": {
            "expr": "substr(COALESCE(DISB_ORG_COD,''),1,2)",
        },
        "省份(建档)": {
            "expr": "COALESCE(PROV_NO,'未知')",
        },
    },
    "风险计量": {
        "内部评级": {
            "expr": "COALESCE(INTL_GRD_CLS_CD,'未知')",
        },
        "评分分段": {
            "expr": """CASE
                WHEN SCRE IS NULL OR CAST(SCRE AS DOUBLE) = 0 THEN '无评分'
                WHEN CAST(SCRE AS DOUBLE) < 600 THEN '低(<600)'
                WHEN CAST(SCRE AS DOUBLE) < 700 THEN '中(600-700)'
                ELSE '高(>=700)' END""",
        },
    },
    "管理与行为": {
        "客户经理维度": {
            "expr": "CASE WHEN MAGR_CD IS NULL OR MAGR_CD = '' THEN '无' ELSE '有经理' END",
        },
        "代理渠道": {
            "expr": "COALESCE(AGENT_CTG_CD,'无代理')",
        },
    },
}

# 维度配置中涉及建档档案字段的维度，需要 JOIN 建档档案
NEED_DOC = {"主体类型", "性别", "居住年限", "省份(建档)"}
NEED_SCRE = {"评分分段"}


def main():
    ap = argparse.ArgumentParser(description="完整总览 + 多维分类（DuckDB）")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--slice", default="20260831")
    ap.add_argument("--out", default="overview.json")
    args = ap.parse_args()

    con = duckdb.connect()
    t_start = time.time()
    PQ = args.data_dir
    vch_glob = os.path.join(PQ, "G_00PF_PEAS_LN_VCH_DV", "part-*.parquet").replace("\\", "/")
    doc_glob = os.path.join(PQ, "G_00PL_PEAS_DOC_INFO_DV", "part-*.parquet").replace("\\", "/")
    scre_glob = os.path.join(PQ, "G_00PL_IDV_LN_CUST_ACARD_SCRE_DV", "part-*.parquet").replace("\\", "/")

    # 自动探测切片
    try:
        avail = con.execute(f"SELECT DISTINCT DATA_DAT FROM read_parquet('{vch_glob}') ORDER BY 1 DESC LIMIT 3").fetchall()
        avail = [r[0] for r in avail]
    except Exception as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
    slice_dt = args.slice if args.slice in avail else avail[0]
    scre_dt = "20260802"  # 评分表最新月切（近似）

    # 主表：凭证 + 建档档案（取主体字段）+ 评分（最新切片）
    base = f"""
    SELECT v.*, d.ADMI_SUBJ_TYP, d.SEX, d.CUR_PLCE_RES_YEAR, d.PROV_NO,
           s.SCRE,
           COUNT(*) OVER (PARTITION BY v.CUST_NO) AS v_per_cust_cnt
    FROM read_parquet('{vch_glob}') v
    LEFT JOIN (SELECT DISTINCT CUST_NO, ADMI_SUBJ_TYP, SEX, CUR_PLCE_RES_YEAR, PROV_NO
               FROM read_parquet('{doc_glob}') WHERE DATA_DAT = '{slice_dt}') d
      ON d.CUST_NO = v.CUST_NO
    LEFT JOIN (SELECT CUST_NO, MAX(SCRE) AS SCRE
               FROM read_parquet('{scre_glob}')
               WHERE DATA_DAT = '{scre_dt}' GROUP BY 1) s
      ON s.CUST_NO = v.CUST_NO
    WHERE v.DATA_DAT = '{slice_dt}' AND v.BUS_BREED_CD LIKE 'A70%'
    """
    base_w = f"WITH base AS ({base}) "

    # 1) 总体四组对照
    sql_tot = base_w + f"""
    SELECT {RSK_SQL} AS grp,
           COUNT(*) AS cnt,
           COUNT(DISTINCT FORM_NO) AS vch_cnt,
           COUNT(DISTINCT CUST_NO) AS cust_cnt,
           COALESCE(SUM(CAST(FORM_BAL_RMB AS DOUBLE)),0) AS bal,
           COALESCE(SUM(CASE WHEN RSK_CLS_CD IN ('30','40','50') THEN CAST(FORM_BAL_RMB AS DOUBLE) ELSE 0 END),0) AS npl_bal
    FROM base GROUP BY 1
    """
    rows = con.execute(sql_tot).fetchall()
    groups = {}
    for grp, cnt, vch, cust, bal, npl in rows:
        groups[grp] = {"cnt": int(cnt), "vch_cnt": int(vch), "cust_cnt": int(cust),
                       "bal": round(float(bal), 2), "npl_bal": round(float(npl), 2)}
    total_bal = sum(g["bal"] for g in groups.values())
    for g in groups.values():
        g["bal_share"] = round(g["bal"] / total_bal, 4) if total_bal else None
        g["npl_rate"] = round(g["npl_bal"] / g["bal"], 6) if g["bal"] else None

    # 2) 维度 × 状态 分组
    dims_out = {}
    for dim_group, dims in DIMENSIONS.items():
        dims_out[dim_group] = {}
        for dim_name, cfg in dims.items():
            expr = cfg["expr"]
            # 若维度用到建档/评分字段，确保 base 已含（base 始终含，无碍）
            sql = base_w + f"""
            SELECT {expr} AS dv, {RSK_SQL} AS grp,
                   COUNT(*) AS cnt,
                   COUNT(DISTINCT v.FORM_NO) AS vch_cnt,
                   COUNT(DISTINCT v.CUST_NO) AS cust_cnt,
                   COALESCE(SUM(CAST(v.FORM_BAL_RMB AS DOUBLE)),0) AS bal,
                   COALESCE(SUM(CASE WHEN v.RSK_CLS_CD IN ('30','40','50') THEN CAST(v.FORM_BAL_RMB AS DOUBLE) ELSE 0 END),0) AS npl_bal
            FROM base v GROUP BY 1,2
            """
            try:
                rows = con.execute(sql).fetchall()
            except Exception as e:
                dims_out[dim_group][dim_name] = {"error": str(e)[:80]}
                continue
            # 整理：每个档位 → {正常/关注/不良: {bal, cnt, ...}}
            buckets = {}
            for dv, grp, cnt, vch, cust, bal, npl in rows:
                key = str(dv)
                if key in cfg.get("label_map", {}):
                    key = cfg["label_map"][key]
                buckets.setdefault(key, {})[grp] = {
                    "cnt": int(cnt), "vch_cnt": int(vch), "cust_cnt": int(cust),
                    "bal": round(float(bal), 2), "npl_bal": round(float(npl), 2),
                }
            # 计算每档：合计余额、不良率、恶化偏移（档不良率 - 全辖不良率）
            out_items = []
            all_npl_rate = groups.get("不良", {}).get("npl_rate")
            total_bal_all = groups.get("正常", {}).get("bal", 0) + groups.get("关注", {}).get("bal", 0) + groups.get("不良", {}).get("bal", 0)
            # 档位过多时只保留余额 Top 12 + 其余归"其他"
            TOP_N = 12
            if len(buckets) > TOP_N:
                sorted_keys = sorted(buckets.keys(), key=lambda k: -sum(s.get("bal", 0) for s in buckets[k].values()))
                keep = sorted_keys[:TOP_N]
                other = sorted_keys[TOP_N:]
                if other:
                    agg = {}
                    for k in other:
                        for grp, st in buckets[k].items():
                            agg.setdefault(grp, {"cnt": 0, "vch_cnt": 0, "cust_cnt": 0, "bal": 0.0, "npl_bal": 0.0})
                            a = agg[grp]
                            a["cnt"] += st["cnt"]; a["vch_cnt"] += st["vch_cnt"]; a["cust_cnt"] += st["cust_cnt"]
                            a["bal"] += st["bal"]; a["npl_bal"] += st["npl_bal"]
                    buckets = {k: buckets[k] for k in keep}
                    buckets["其他"] = agg
            for dv, states in sorted(buckets.items(), key=lambda x: -(sum(s.get("bal", 0) for s in x[1].values()))):
                bal_sum = sum(s.get("bal", 0) for s in states.values())
                npl_sum = sum(s.get("npl_bal", 0) for s in states.values())
                npl_rate = npl_sum / bal_sum if bal_sum else None
                # 正常组占比（对照组）
                normal_bal = states.get("正常", {}).get("bal", 0)
                bad_bal = states.get("不良", {}).get("bal", 0)
                item = {
                    "dim_value": dv,
                    "bal": round(bal_sum, 2),
                    "bal_share": round(bal_sum / total_bal_all, 4) if total_bal_all else None,
                    "cnt": sum(s.get("cnt", 0) for s in states.values()),
                    "npl_rate": round(npl_rate, 6) if npl_rate is not None else None,
                    "normal_bal": round(normal_bal, 2),
                    "bad_bal": round(bad_bal, 2),
                    "normal_share": round(normal_bal / bal_sum, 4) if bal_sum else None,
                    "bad_share": round(bad_bal / bal_sum, 4) if bal_sum else None,
                    "states": states,
                }
                # 恶化偏移：档不良率 vs 全辖不良率（全辖口径=全部余额含不良）
                if npl_rate is not None and total_bal_all:
                    item["npl_offset_pp"] = round((npl_rate - groups.get("不良", {}).get("npl_bal", 0) / total_bal_all if total_bal_all else 0) * 100, 2)
                out_items.append(item)
            dims_out[dim_group][dim_name] = out_items

    result = {
        "schema_version": "3.0-overview",
        "slice": slice_dt,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "groups": groups,
        "total_bal": round(total_bal, 2),
        "dimensions": dims_out,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ 完整总览(DuckDB) 完成 → {args.out} | 耗时 {time.time()-t_start:.1f}s")
    print(f"   切片 {slice_dt}：正常 {groups.get('正常',{}).get('bal',0):,.0f} / 关注 {groups.get('关注',{}).get('bal',0):,.0f} / 不良 {groups.get('不良',{}).get('bal',0):,.0f}")
    print(f"   维度组 {len(dims_out)} 个")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
