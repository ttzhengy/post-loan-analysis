#!/usr/bin/env python3
"""org_risk.py — 机构级风险指标（读 16 张 S_00PF_PEAS_*_C4 表）

用法:
    python3 scripts/org_risk.py --data-dir "数字员工工作区/数据文件" \\
        --slice 20260831 --out org_risk.json

说明：机构级分析表已按 C4 机构树预聚合合同/客户/余额/不良/不良率/还原核销不良率/生成率，
机构维度风险指标直接查表，避免扫描 17GB 凭证表。
"""
import argparse
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd

ORG_TABLES = {
    "divr": "S_00PF_PEAS_DIVR_RSK_C4.csv",
    "nmgg": "S_00PF_PEAS_NMGG_RLSE_RSK_ORG_C4.csv",
    "acard": "S_00PF_PEAS_ACARD_SCRE_RSK_ORG_C4.csv",
    "arc": "S_00PF_PEAS_LN_ARC_QLT_RSK_ORG_ANL_C4.csv",
    "over": "S_00PF_PEAS_OVER_FL_AC_RSK_C4.csv",
    "lrg": "S_00PF_PEAS_LN_LRG_CR_ORG_ANL_C4.csv",
    "biz": "S_00PF_PEAS_LN_BIZ_TYP_ORG_ANL_C4.csv",
    "ocp": "S_00PF_PEAS_OCPRSK_ORG_C4.csv",
    "rsk": "S_00PF_PEAS_LN_RSK_ORG_C4.csv",
    "cce": "S_00PF_PEAS_LN_CCE_RSK_PSE_ORG_C4.csv",
    "mgg": "S_00PF_PEAS_MGG_RSK_C4.csv",
    "addr": "S_00PF_PEAS_ADDR_RSK_ORG_SUM_C4.csv",
    "hrz": "S_00PF_PEAS_HRZ_MGR_LN_ANL_C4.csv",
    "cont": "S_00PF_PEAS_CONT_QUAL_C4.csv",
    "spc": "S_00PF_PEAS_LN_SPC_ORG_ANL_C4.csv",
    "mgr": "S_00PF_PEAS_MGR_LN_RISK_C4.csv",
}

# 每张表的关键指标列（用于汇总输出）
KEY_COLS = {
    "divr": ["DIVR_CTRT_RATE", "DIVR_LN_BAL_RATE", "DIVR_UHLTH_LN_RATE", "UHLTH_LN_RATE"],
    "nmgg": ["GRTE_CTRT_PPTN", "GRTE_BAL_PPTN", "GRTE_UHLTH_RATE", "ALL_UHLTH_RATE"],
    "acard": ["RSK_CTRT_PPTN", "RSK_BAL_PPTN", "RSK_UHLTH_RATE", "ALL_UHLTH_RATE", "ALL_ACARD_SCRE_AVER_VLU"],
    "arc": ["TRS_RAT_CNT_PEAS", "TRS_RAT_BAL_PEAS", "TRS_RAT_NPL_PEAS", "TTL_RAT_NPL_PEAS"],
    "over": ["RSK_CTRT_PPTN", "RSK_BAL_PPTN", "RSK_UHLTH_RATE", "ALL_UHLTH_RATE"],
    "lrg": ["LRG_RAT_CNT_PEAS", "LRG_RAT_BAL_PEAS", "LRG_RAT_NPL_PEAS", "TTL_RAT_NPL_PEAS"],
    "biz": ["BIZ_RAT_CNT_PEAS", "BIZ_RAT_BAL_PEAS", "BIZ_RAT_NPL_PEAS", "TTL_RAT_NPL_PEAS"],
    "ocp": ["KEY_OCP_CTRT_PPTN", "KEY_OCP_BAL_PPTN", "KEY_OCP_UHLTH_RATE", "UHLTH_RATE"],
    "rsk": ["PEAS_LN_CTRT_PPTN", "PEAS_LN_BAL_PPTN", "PEAS_LN_UHLTH_CTRT_PPTN", "LN_UHLTH_CTRT_PPTN"],
    "cce": ["PEAS_LN_CTRT_PPTN", "PEAS_LN_BAL_PPTN", "PEAS_LN_UHLTH_CTRT_PPTN", "LN_UHLTH_CTRT_PPTN"],
    "mgg": ["RSK_CTRT_PPTN", "RSK_LN_BAL_PPTN", "RSK_UHLTH_RATE", "UHLTH_RATE"],
    "addr": ["ADDR_RSK_CTRT_PPTN", "ADDR_RSK_BAL_PPTN", "ADDR_RSK_UHLTH_RATE", "UHLTH_RATE"],
    "hrz": ["HRZ_CUST_MGR_CNT", "HRZ_RAT_NPL_PEAS", "HRZ_CUR_RAT_NPL_PEAS", "TOT_CUR_BAL_NPL_PEAS"],
    "cont": ["CTNU_LN_BAL", "CTNU_LN_BAD_RATE", "ONE_CTNU_LN_BAL"],
    "spc": ["SPC_RAT_CNT_PEAS", "SPC_RAT_BAL_PEAS", "SPC_RAT_NPL_PEAS", "TTL_RAT_NPL_PEAS"],
    "mgr": ["CUR_RAT_NPL_PEAS", "CUR_BAL_NPL_PEAS", "CUR_RAT_OD_PEAS", "SAME_DAT_CUST_CNT", "FND_CLU_CNT_PEAS"],
}


def load_table(data_dir, fname, slice_dt):
    # parquet 优先：fname 可能是 "X.csv" 或 "X"
    base = fname[:-4] if fname.endswith(".csv") else fname
    import glob
    pq_files = glob.glob(os.path.join(data_dir, base, "part-*.parquet"))
    if pq_files:
        try:
            df = pd.read_parquet(pq_files)
            if "DATA_DAT" in df.columns:
                df = df[df["DATA_DAT"] == slice_dt]
            return df
        except Exception:
            pass
    path = os.path.join(data_dir, fname)
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, dtype=str, keep_default_na=False, low_memory=False)
    if "DATA_DAT" in df.columns:
        df = df[df["DATA_DAT"] == slice_dt]
    return df


def main():
    ap = argparse.ArgumentParser(description="机构级风险指标")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--slice", default="20260831")
    ap.add_argument("--out", default="org_risk.json")
    args = ap.parse_args()

    if not os.path.isdir(args.data_dir):
        print(f"错误：数据目录不存在: {args.data_dir}", file=sys.stderr)
        return 2

    result = {
        "schema_version": "1.0",
        "slice": args.slice,
        "tables": {},
        "summary": {},
        "warnings": [],
    }

    def f(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    for key, fname in ORG_TABLES.items():
        df = load_table(args.data_dir, fname, args.slice)
        if df is None or df.empty:
            result["warnings"].append(f"{fname} 缺失或切片 {args.slice} 无数据")
            continue

        cols = KEY_COLS.get(key, [])
        # 汇总（全辖，跨机构按余额加权/平均）
        rec = {"rows": len(df)}
        summary = {}
        for c in cols:
            if c not in df.columns:
                continue
            vals = pd.to_numeric(df[c], errors="coerce").dropna()
            if vals.empty:
                continue
            rec[c] = {
                "mean": round(float(vals.mean()), 6),
                "p50": round(float(vals.median()), 6),
                "max": round(float(vals.max()), 6),
                "org_max": str(df.loc[vals.idxmax(), "C4_ORG_NO"]) if "C4_ORG_NO" in df.columns else None,
            }
            summary[c] = rec[c]["mean"]

        # 机构明细（前 20 高风险：按第一列关键率降序）
        detail = []
        if cols:
            first = cols[0]
            if first in df.columns:
                df2 = df.copy()
                df2[first] = pd.to_numeric(df2[first], errors="coerce")
                df2 = df2.dropna(subset=[first]).sort_values(first, ascending=False).head(20)
                for _, r in df2.iterrows():
                    item = {
                        "org": r.get("C4_ORG_NO", ""),
                        "org_name": r.get("C4_ORG_NAM", ""),
                        "lv": r.get("C4_ORG_LVL", ""),
                    }
                    for c in cols:
                        if c in r:
                            item[c] = f(r[c])
                    detail.append(item)

        result["tables"][key] = {"file": fname, "rows": rec.pop("rows"), "summary": rec, "top20": detail}
        result["summary"][key] = summary

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ 机构级风险指标完成 → {args.out}")
    for key in ORG_TABLES:
        if key in result["tables"]:
            print(f"   {key}: {result['tables'][key]['rows']} 行")
    for w in result["warnings"]:
        print(f"   ⚠️ {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
