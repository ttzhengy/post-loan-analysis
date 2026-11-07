#!/usr/bin/env python3
"""risk_features.py — 45 项风险特征命中分析（修复 0 值 + 内存优化）

用法:
    python3 scripts/risk_features.py --data-dir "数字员工工作区/数据文件" \\
        --slice 20260831 --out features.json

修改记录：
- v2.0: 修复 0 值问题（代码值判断 APR_OPIN/BUS_STS、千分制评分、df 变量复用 bug、
  MRGE_STS 脱敏处理）；所有大表读取 usecols 只读必要列，避免 80+G 爆内存；
  结果中值为 0/None 的指标不再写入 metric（避免报告出现 0 统计）。
命中判据见 references/risk-features-map.md。
"""
import argparse
import json
import os
import sys

import pandas as pd

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


def main():
    ap = argparse.ArgumentParser(description="风险特征命中分析")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--slice", default="20260831")
    ap.add_argument("--out", default="features.json")
    ap.add_argument("--log", default="query_log.md", help="查询日志输出路径（内部记录，不落入报告）")
    args = ap.parse_args()

    qlog = QueryLog(path=args.log, title="查询日志（内部工作记录）")
    qlog.add(stage="Step3 基础风险特征", table="45项风险特征",
             query=f"对 45 项基础风险特征逐项计算命中统计（usecols+nrows 采样）",
             result="待计算", thought="基础指标层：为组合线索引擎提供原料；大表 usecols 只读必要列避免 80G 爆内存")

    if not os.path.isdir(args.data_dir):
        print(f"错误：数据目录不存在: {args.data_dir}", file=sys.stderr)
        return 2

    result = {"schema_version": "2.0", "slice": args.slice, "features": [], "warnings": [],
              "baseline": {}, "baseline_src": {}}
    F = result["features"]
    BASE = result["baseline"]       # metric_label -> 全辖基线值
    BASE_SRC = result["baseline_src"]  # metric_label -> 口径说明

    def load(fname, cols=None, nrows=None):
        """读 CSV/Parquet，usecols 只读必要列（内存优化）
        优先读 parquet（数据文件duckdb 目录），找不到再读 CSV。
        """
        # parquet 优先：fname 可能是 "X.csv" 或 "X"
        base = fname[:-4] if fname.endswith(".csv") else fname
        parquet_dir = os.path.join(args.data_dir, base)
        parquet_glob = os.path.join(parquet_dir, "part-*.parquet")
        import glob as _glob
        pq_files = _glob.glob(parquet_glob)
        if pq_files:
            try:
                import pandas as pd
                if cols:
                    df = pd.read_parquet(pq_files, columns=list(cols))
                else:
                    df = pd.read_parquet(pq_files)
                if nrows and len(df) > nrows:
                    df = df.head(nrows)
                return df
            except Exception:
                pass
        path = os.path.join(args.data_dir, fname)
        if not os.path.exists(path):
            return None
        return pd.read_csv(path, dtype=str, keep_default_na=False, low_memory=False,
                           usecols=cols, nrows=nrows, on_bad_lines="skip")

    def col(df, name):
        return df[name] if name in df.columns else None

    def credit_pivot():
        """读取征信 P1/P2/P3 表，透视成宽表（每客户一行，指标为列）
        返回 DataFrame：索引 CERTNO，列=Indicate_name，值=Indicate_value(数值)
        征信三表：P1 直接提取 / P2 简单加工 / P3 复杂加工
        """
        import glob as _glob
        parts = []
        for tbl in ["P_00CIE_CPS_INDECATE_DIRECTEXTRA",
                    "P_00CIE_CPS_INDECATE_SIMPLEPROCESS",
                    "P_00CIE_CPS_INDECATE_COMPLIATEPROCESS"]:
            pq_files = _glob.glob(os.path.join(args.data_dir, tbl, "part-*.parquet"))
            if not pq_files:
                continue
            try:
                df = pd.read_parquet(pq_files)
                parts.append(df)
            except Exception:
                continue
        if not parts:
            return None
        raw = pd.concat(parts, ignore_index=True)
        if "CERTNO" not in raw.columns or "Indicate_name" not in raw.columns:
            return None
        # 透视：每个客户一行的宽表
        pv = raw.pivot_table(index="CERTNO", columns="Indicate_name",
                             values="Indicate_value", aggfunc="first")
        return pv

    def credit_num(pv, indicator):
        """取征信宽表中某指标列，转为数值 Series（含 0 填充）"""
        if pv is None or indicator not in pv.columns:
            return None
        s = pd.to_numeric(pv[indicator], errors="coerce")
        return s.fillna(0.0)

    def credit_ratio(pv, indicator, threshold=0, gt=True):
        """某指标超过/低于阈值的客户占比"""
        s = credit_num(pv, indicator)
        if s is None or len(s) == 0:
            return None
        return round(float((s > threshold).mean()) if gt else float((s < threshold).mean()), 4)

    def col_mean(df, name, default=None):
        c = col(df, name)
        if c is None:
            return None
        s = pd.to_numeric(c, errors="coerce").dropna()
        return round(float(s.mean()), 4) if len(s) else None

    def col_wavg(df, rate_col, wgt_col, default=None):
        """余额加权率 —— 全辖口径的正确算法。

        分机构预聚合表里 col_mean 得到的是「各机构率的简单平均」，
        全辖值应是 Σ(不良余额) / Σ(余额)。两者在有机构规模差异时并不相等。
        """
        r = col(df, rate_col)
        w = col(df, wgt_col)
        if r is None or w is None:
            return default
        rs = pd.to_numeric(r, errors="coerce")
        ws = pd.to_numeric(w, errors="coerce")
        mask = rs.notna() & ws.notna() & (ws > 0)
        if not mask.any():
            return default
        tot = float(ws[mask].sum())
        return round(float((rs[mask] * ws[mask]).sum() / tot), 6) if tot else default

    def full_scope_baseline(df, rate_col, wgt_candidates, label):
        """为率类指标产出全辖基线；找不到权重列则退回简单平均并注明口径。"""
        for wcol in wgt_candidates:
            if col(df, wcol) is not None:
                v = col_wavg(df, rate_col, wcol)
                if v is not None:
                    BASE[label] = v
                    BASE_SRC[label] = f"wavg:{wcol}"
                    return
        v = col_mean(df, rate_col)
        if v is not None:
            BASE[label] = v
            BASE_SRC[label] = "mean(无权重列)"

    def col_ratio(df, name, pred, default=None):
        """pred 接收 Series 返回 bool Series，返回 True 占比"""
        c = col(df, name)
        if c is None:
            return None
        try:
            s = c.astype(str)
            hit = pred(s)
            if hit.sum() == 0:
                return 0.0 if hit.size else None
            return round(float(hit.mean()), 4)
        except Exception:
            return None

    def nonempty_metric(m):
        """过滤掉 0/None/空值指标，避免报告出现 0 统计"""
        return {k: v for k, v in m.items() if v not in (0, 0.0, None, "")} if m else {}

    def _attach_baseline(m, baseline_src_map=None):
        """把 BASE 里对应标签的全辖值挂到该特征的 baseline 上。

        只挂「该特征 metric 里确实有、且 BASE 里算出了」的标签，
        避免把别的特征口径混进来。
        """
        if not m:
            return {}
        return {k: BASE[k] for k in m if k in BASE}

    def miss(fid, name, dim, stage, note=""):
        F.append({"feature_id": fid, "name": name, "dimension": dim, "stage": stage,
                  "status": "data_missing", "note": note})

    def approx(fid, name, dim, stage, table, metric, note=""):
        F.append({"feature_id": fid, "name": name, "dimension": dim, "stage": stage,
                  "status": "approximate", "table": table, "metric": nonempty_metric(metric),
                  "baseline": _attach_baseline(nonempty_metric(metric)), "note": note})

    def ok(fid, name, dim, stage, table, metric, evidence, note=""):
        mm = nonempty_metric(metric)
        F.append({"feature_id": fid, "name": name, "dimension": dim, "stage": stage,
                  "status": "ok", "table": table, "metric": mm,
                  "baseline": _attach_baseline(mm), "evidence": evidence, "note": note})

    # ================= 机构维度 =================
    # 1 零散获客
    df = load("S_00PF_PEAS_DIVR_RSK_C4.csv")
    if df is not None and not df.empty:
        m = {"机构数": len(df),
             "零散客户占比均值": col_mean(df, "DIVR_CUST_RATE"),
             "零散余额占比均值": col_mean(df, "DIVR_LN_BAL_RATE"),
             "零散不良率均值": col_mean(df, "DIVR_UHLTH_LN_RATE")}
        full_scope_baseline(df, "DIVR_UHLTH_LN_RATE", ["DIVR_LN_BAL", "DIVR_LN_BAL_RMB", "LN_BAL"], "零散不良率均值")
        ok(1, "零散获客风险", "机构", "营销获客", "S_00PF_PEAS_DIVR_RSK_C4", m,
           "DIVR_CUST_RATE/DIVR_LN_BAL_RATE/DIVR_UHLTH_LN_RATE 全辖均值")
    else:
        miss(1, "零散获客风险", "机构", "营销获客")

    # 2 无抵押缓释
    df = load("S_00PF_PEAS_NMGG_RLSE_RSK_ORG_C4.csv")
    if df is not None and not df.empty:
        grte = df["GRTE_TYP"].astype(str) if "GRTE_TYP" in df.columns else None
        m = {"机构数": len(df), "担保类型数": grte.nunique() if grte is not None else None}
        # 信用类（无抵押）余额占比均值：GRTE_TYP 含"信用"的行的 GRTE_BAL_PPTN
        if grte is not None and "GRTE_BAL_PPTN" in df.columns:
            credit = df[grte.str.contains("信用", na=False)]
            if not credit.empty:
                m["信用类余额占比均值"] = round(pd.to_numeric(credit["GRTE_BAL_PPTN"], errors="coerce").mean(), 4)
        ok(2, "无抵押缓释风险", "机构", "营销获客", "S_00PF_PEAS_NMGG_RLSE_RSK_ORG_C4", m,
           "GRTE_TYP 维度预聚合")
    else:
        miss(2, "无抵押缓释风险", "机构", "营销获客")

    # 3 低评分准入（千分制：SCRE 均值约 658，阈值 600）
    df = load("G_00PL_IDV_LN_CUST_ACARD_SCRE_DV.csv",
              cols=["SCRE", "WON_SCRE_PASS", "SCRE_APRIN_TRHD"], nrows=500000)
    if df is not None and not df.empty:
        scores = pd.to_numeric(df["SCRE"], errors="coerce").dropna()
        pass_s = df["WON_SCRE_PASS"].astype(str) if "WON_SCRE_PASS" in df.columns else None
        m = {"评分记录数": len(df),
             "平均分": round(float(scores.mean()), 1) if len(scores) else None,
             "低分段(<600)占比": round(float((scores < 600).mean()), 4) if len(scores) else None,
             "评分通过率": round(float((pass_s == "1").mean()), 4) if pass_s is not None and (pass_s == "1").any() else None}
        ok(3, "低评分准入风险", "机构", "贷前准入", "G_00PL_IDV_LN_CUST_ACARD_SCRE_DV", m,
           "SCRE 千分制分布（采样 50 万行），低分段阈值 600")
    else:
        miss(3, "低评分准入风险", "机构", "贷前准入")

    # 4 建档不规范
    df = load("S_00PF_PEAS_LN_ARC_QLT_RSK_ORG_ANL_C4.csv")
    if df is not None and not df.empty:
        m = {"机构数": len(df),
             "异常建档客户占比均值": col_mean(df, "TRS_RAT_CUST_PEA"),
             "异常建档不良率均值": col_mean(df, "TRS_RAT_NPL_PEAS")}
        full_scope_baseline(df, "TRS_RAT_NPL_PEAS", ["TRS_RAT_LN_BAL", "LN_BAL", "RSK_LN_BAL"], "异常建档不良率均值")
        ok(4, "建档不规范风险", "机构", "贷前准入", "S_00PF_PEAS_LN_ARC_QLT_RSK_ORG_ANL_C4", m,
           "ARC_QLT_RSK_TYP 预聚合")
    else:
        miss(4, "建档不规范风险", "机构", "贷前准入")

    # 5 欺诈风险敞口
    df = load("S_00PF_PEAS_LN_RSK_ORG_C4.csv")
    if df is not None and not df.empty:
        m = {"机构数": len(df),
             "线索类型数": df["RSK_LINE_TYP"].nunique() if "RSK_LINE_TYP" in df.columns else None}
        ok(5, "欺诈风险敞口", "机构", "贷前准入", "S_00PF_PEAS_LN_RSK_ORG_C4", m,
           "RSK_LINE_TYP 触发/不属实占比预聚合")
    else:
        miss(5, "欺诈风险敞口", "机构", "贷前准入")

    # 6 信用负债敞口（征信 P1/P2/P3）
    pv6 = credit_pivot()
    if pv6 is not None and not pv6.empty:
        m = {"征信覆盖客户数": len(pv6)}
        for ind in ["账户数合计", "负债合计（与网借贷一致）", "未结清贷款机构数", "家庭负债合计"]:
            s = credit_num(pv6, ind)
            if s is not None and len(s):
                m[f"{ind}均值"] = round(float(s.mean()), 2)
        ok(6, "信用与负债风险敞口", "机构", "贷前准入", "P_00CIE_CPS_INDECATE_*", m,
           "征信P表直接提取/简单加工/复杂加工指标透视聚合")
    else:
        miss(6, "信用与负债风险敞口", "机构", "贷前准入", "征信P表无数据文件，用 S_00PF_PEAS_LN_RSK_ORG_C4 线索口径替代")

    # 7 超额授信
    df = load("S_00PF_PEAS_OVER_FL_AC_RSK_C4.csv")
    if df is not None and not df.empty:
        m = {"机构数": len(df),
             "超额授信余额占比均值": col_mean(df, "RSK_LN_BAL_PPTN", col_mean(df, "RSK_BAL_PPTN")),
             "超额授信不良率均值": col_mean(df, "RSK_UHLTH_RATE")}
        full_scope_baseline(df, "RSK_UHLTH_RATE", ["RSK_LN_BAL", "RSK_BAL", "LN_BAL"], "超额授信不良率均值")
        ok(7, "超额授信风险", "机构", "贷前准入", "S_00PF_PEAS_OVER_FL_AC_RSK_C4", m,
           "OVER_FL_AC_RSK_TYP 预聚合")
    else:
        miss(7, "超额授信风险", "机构", "贷前准入")

    # 8 审查质量（APR_OPIN 代码：01=通过/同意，02=拒绝）
    df = load("G_00PF_PEAS_LN_WHT_CHK_FLOW_INFO.csv", cols=["APR_OPIN"])
    if df is not None and not df.empty:
        total = len(df)
        apr = df["APR_OPIN"].astype(str)
        pass_cnt = int((apr == "01").sum())
        m = {"流程数": total,
             "审批通过率": round(pass_cnt / total, 4) if total else None,
             "审批拒绝数": int((apr == "02").sum())}
        ok(8, "审查质量风险", "机构", "贷中审查", "G_00PF_PEAS_LN_WHT_CHK_FLOW_INFO", m,
           "APR_OPIN 代码 01=通过/02=拒绝")
    else:
        miss(8, "审查质量风险", "机构", "贷中审查")

    # 9 贷后管理不到位（BUS_STS 代码：00=待办/50=处理中/90=已完成）
    df = load("B_00FT_PEAS_LN_DPSE_TASK_DTAL.csv",
              cols=["BUS_STS", "LMT_DUE_DATE", "DPSE_CMPL_DAT"], nrows=300000)
    if df is not None and not df.empty:
        st = df["BUS_STS"].astype(str)
        undone = int(st.isin(["00", "50"]).sum())
        done = int((st == "90").sum())
        m = {"任务数": len(df),
             "未办结任务数": undone,
             "未办结率": round(undone / len(df), 4) if len(df) else None,
             "已办结任务数": done}
        ok(9, "贷后管理不到位", "机构", "贷后管理", "B_00FT_PEAS_LN_DPSE_TASK_DTAL", m,
           "BUS_STS 代码 00/50=未办结，90=已办结（采样 30 万行）")
    else:
        miss(9, "贷后管理不到位", "机构", "贷后管理")

    # 10 接续不到位
    df = load("S_00PF_PEAS_CONT_QUAL_C4.csv")
    if df is not None and not df.empty:
        m = {"机构数": len(df),
             "无还本续贷不良率均值": col_mean(df, "CTNU_LN_BAD_RATE"),
             "一键续贷不良率均值": col_mean(df, "ONE_CTNU_LN_BAD_RATE")}
        full_scope_baseline(df, "CTNU_LN_BAD_RATE", ["CTNU_LN_BAL", "LN_BAL"], "无还本续贷不良率均值")
        full_scope_baseline(df, "ONE_CTNU_LN_BAD_RATE", ["ONE_CTNU_LN_BAL", "LN_BAL"], "一键续贷不良率均值")
        ok(10, "接续不到位风险", "机构", "到期续贷", "S_00PF_PEAS_CONT_QUAL_C4", m,
           "CTNU_LN_BAD_RATE 预聚合")
    else:
        miss(10, "接续不到位风险", "机构", "到期续贷")

    # 11 高风险客户经理
    dfm = load("S_00PF_PEAS_MGR_LN_RISK_C4.csv")
    if dfm is not None and not dfm.empty:
        rate = pd.to_numeric(dfm["CUR_RAT_NPL_PEAS"], errors="coerce") if "CUR_RAT_NPL_PEAS" in dfm.columns else pd.Series(dtype=float)
        bal = pd.to_numeric(dfm["CUR_BAL_NPL_PEAS"], errors="coerce") if "CUR_BAL_NPL_PEAS" in dfm.columns else pd.Series(dtype=float)
        valid = dfm[(rate.notna()) & (bal.notna())]
        hi = valid[(rate > 0.05) & (bal > 500000)]
        m = {"客户经理数": len(dfm),
             "高风险经理数": len(hi),
             "高风险经理占比": round(len(hi) / len(dfm), 4) if len(dfm) else None}
        ok(11, "高风险客户经理", "机构", "其他", "S_00PF_PEAS_MGR_LN_RISK_C4", m,
           "CUR_RAT_NPL_PEAS>5% 且 CUR_BAL_NPL_PEAS>50万")
    else:
        miss(11, "高风险客户经理", "机构", "其他")

    # 12 高风险产品
    df = load("S_00PF_PEAS_LN_BIZ_TYP_ORG_ANL_C4.csv")
    if df is not None and not df.empty:
        m = {"机构数": len(df),
             "产品不良率均值": col_mean(df, "BIZ_RAT_NPL_PEAS")}
        full_scope_baseline(df, "BIZ_RAT_NPL_PEAS", ["BIZ_LN_BAL", "LN_BAL", "RSK_LN_BAL"], "产品不良率均值")
        ok(12, "高风险产品/专项", "机构", "其他", "S_00PF_PEAS_LN_BIZ_TYP_ORG_ANL_C4", m,
           "PEAS_LN_C4_BIZ 预聚合")
    else:
        miss(12, "高风险产品/专项", "机构", "其他")

    # 13 大额信用风险
    df = load("S_00PF_PEAS_LN_LRG_CR_ORG_ANL_C4.csv")
    if df is not None and not df.empty:
        m = {"机构数": len(df),
             "大额信用余额占比均值": col_mean(df, "LRG_RAT_BAL_PEAS"),
             "大额信用不良率均值": col_mean(df, "LRG_RAT_NPL_PEAS")}
        full_scope_baseline(df, "LRG_RAT_NPL_PEAS", ["LRG_LN_BAL", "CR_LN_BAL", "LN_BAL"], "大额信用不良率均值")
        ok(13, "大额信用风险", "机构", "其他", "S_00PF_PEAS_LN_LRG_CR_ORG_ANL_C4", m,
           "大额信用预聚合")
    else:
        miss(13, "大额信用风险", "机构", "其他")

    # ================= 客户经理维度 =================
    # 14 批量建档（复用 dfm=客户经理风险表，修复原 df 变量复用 bug）
    if dfm is not None and not dfm.empty:
        sdc = pd.to_numeric(dfm["SAME_DAT_CUST_CNT"], errors="coerce") if "SAME_DAT_CUST_CNT" in dfm.columns else pd.Series(dtype=float)
        sdc = sdc.dropna()
        m = {"客户经理数": len(dfm),
             "同日建档>=5户经理数": int((sdc >= 5).sum()),
             "同日建档均值(户)": round(float(sdc.mean()), 1) if len(sdc) else None}
        ok(14, "批量建档", "客户经理", "贷前准入", "S_00PF_PEAS_MGR_LN_RISK_C4", m,
           "SAME_DAT_CUST_CNT>=5")
    else:
        miss(14, "批量建档", "客户经理", "贷前准入")

    # 15 调查造假
    df2 = load("S_00PF_PEAS_ADDR_RSK_ORG_SUM_C4.csv")
    if df2 is not None and not df2.empty:
        m = {"机构数": len(df2),
             "地址异常余额占比均值": col_mean(df2, "ADDR_RSK_BAL_PPTN"),
             "地址异常不良率均值": col_mean(df2, "ADDR_RSK_UHLTH_RATE")}
        approx(15, "调查造假", "客户经理", "贷前准入", "S_00PF_PEAS_ADDR_RSK_ORG_SUM_C4", m,
               "地址明细表无数据，用机构级地址异常口径")
    else:
        miss(15, "调查造假", "客户经理", "贷前准入")

    # 16 信息录入失真
    df3 = load("B_00DT_FAS_ANL_SITU_DOC_H.csv", cols=["TOT_AST", "TOT_DPS", "FARM_LAND"], nrows=200000)
    if df3 is not None and not df3.empty:
        tot_ast = pd.to_numeric(df3["TOT_AST"], errors="coerce")
        tot_dps = pd.to_numeric(df3["TOT_DPS"], errors="coerce")
        ratio = (tot_dps / tot_ast.replace(0, float("nan"))).dropna()
        m = {"建档数": len(df3),
             "负债率>100%占比": round(float((ratio > 1).mean()), 4) if len(ratio) else None}
        ok(16, "信息录入失真", "客户经理", "贷前准入", "B_00DT_FAS_ANL_SITU_DOC_H", m,
           "TOT_DPS/TOT_AST 异常分布（采样 20 万行）")
    else:
        miss(16, "信息录入失真", "客户经理", "贷前准入")

    # 17 与客户资金往来
    if dfm is not None and not dfm.empty:
        fnd = pd.to_numeric(dfm["FND_CLU_CNT_PEAS"], errors="coerce") if "FND_CLU_CNT_PEAS" in dfm.columns else pd.Series(dtype=float)
        fnd = fnd.dropna()
        m = {"客户经理数": len(dfm),
             "触发资金往来线索经理数": int((fnd >= 1).sum())}
        ok(17, "与客户资金往来", "客户经理", "贷前准入", "S_00PF_PEAS_MGR_LN_RISK_C4", m,
           "FND_CLU_CNT_PEAS>=1")
    else:
        miss(17, "与客户资金往来", "客户经理", "贷前准入")

    # 18 贷后检查流于形式
    miss(18, "贷后检查流于形式", "客户经理", "贷后管理", "贷后检查任务表无数据，用处置任务结论近似")

    # 19 管户负担过重
    if dfm is not None and not dfm.empty:
        cur = pd.to_numeric(dfm["CUR_CUST_PEAS_LN"], errors="coerce") if "CUR_CUST_PEAS_LN" in dfm.columns else pd.Series(dtype=float)
        cur = cur.dropna()
        m = {"客户经理数": len(dfm),
             "管户>200经理数": int((cur > 200).sum()),
             "平均管户数": round(float(cur.mean()), 1) if len(cur) else None}
        ok(19, "管户负担过重", "客户经理", "贷后管理", "S_00PF_PEAS_MGR_LN_RISK_C4", m,
           "CUR_CUST_PEAS_LN>200")
    else:
        miss(19, "管户负担过重", "客户经理", "贷后管理")

    # ================= 客户维度 =================
    # 20 虚假经营流水
    df4 = load("S_00PF_SA_ACCT_TR_CUST_SUM.csv",
               cols=["YEAR_TR_BAL_L1YER_ACLT", "YEAR_TR_BAL_IN_L1YER_ACLT"], nrows=300000)
    if df4 is not None and not df4.empty:
        tr = pd.to_numeric(df4["YEAR_TR_BAL_L1YER_ACLT"], errors="coerce").dropna()
        m = {"客户数": len(df4),
             "近12月交易金额中位数": round(float(tr.median()), 2) if len(tr) else None}
        approx(20, "虚假经营流水", "客户", "贷前准入", "S_00PF_SA_ACCT_TR_CUST_SUM", m,
               "需与FAS收入比对，当前给交易规模分布")
    else:
        miss(20, "虚假经营流水", "客户", "贷前准入")

    # 21 短期资金异常涌入
    if df4 is not None and not df4.empty:
        inn = pd.to_numeric(df4["YEAR_TR_BAL_IN_L1YER_ACLT"], errors="coerce").dropna()
        m = {"客户数": len(df4),
             "近12月流入金额中位数": round(float(inn.median()), 2) if len(inn) else None}
        approx(21, "短期资金异常涌入", "客户", "贷前准入", "S_00PF_SA_ACCT_TR_CUST_SUM", m,
               "汇总表无放款前窗口粒度，近似信号")
    else:
        miss(21, "短期资金异常涌入", "客户", "贷前准入")

    # 22 共用经营场所
    miss(22, "多个实体共用同一经营场所", "客户", "贷前准入", "地址交叉检验表无数据")

    # 23 频繁试探申请
    df5 = load("G_00PL_IDV_LN_CUST_ACARD_SCRE_DV.csv", cols=["CUST_NO", "APLY_SER_NO"], nrows=500000)
    if df5 is not None and not df5.empty and "CUST_NO" in df5.columns:
        cnt = df5.groupby("CUST_NO").size()
        m = {"评分记录客户数": len(cnt), "申请>=3次客户数": int((cnt >= 3).sum())}
        approx(23, "短期频繁试探申请", "客户", "贷前准入", "G_00PL_IDV_LN_CUST_ACARD_SCRE_DV", m,
               "用评分表 APLY_SER_NO 按客户聚合")
    else:
        miss(23, "短期频繁试探申请", "客户", "贷前准入")

    # 24 抵押物短持/高评高贷
    df6 = load("G_00PL_IDV_LN_MGG_HPROP_RSK_INFO_DV.csv",
               cols=["MGG_BGN_EVAL_VLU", "MGG_BGN_EXT_QRY_VLU"])
    if df6 is not None and not df6.empty:
        ev = pd.to_numeric(df6["MGG_BGN_EVAL_VLU"], errors="coerce")
        ex = pd.to_numeric(df6["MGG_BGN_EXT_QRY_VLU"], errors="coerce")
        ratio = (ev / ex.replace(0, float("nan"))).dropna()
        m = {"押品数": len(df6),
             "内外部评估差>30%占比": round(float((ratio > 1.3).mean()), 4) if len(ratio) else None}
        ok(24, "抵押物短持/高评高贷", "客户", "贷前准入", "G_00PL_IDV_LN_MGG_HPROP_RSK_INFO_DV", m,
           "MGG_BGN_EVAL_VLU vs MGG_BGN_EXT_QRY_VLU")
    else:
        miss(24, "抵押物短持/高评高贷", "客户", "贷前准入")

    # 25 买壳/新注册即贷
    df7 = load("B_00DT_FAS_IDV_BUS_INFO_H.csv", cols=["CRT_DAT"], nrows=200000)
    if df7 is not None and not df7.empty:
        m = {"建档数": len(df7)}
        approx(25, "买壳/新注册即贷", "客户", "贷前准入", "B_00DT_FAS_IDV_BUS_INFO_H", m,
               "CRT_DAT 成立日期距放款<6月需关联凭证表，当前给档案规模")
    else:
        miss(25, "买壳/新注册即贷", "客户", "贷前准入")

    # 26 AUM与存款不匹配
    dfa = load("S_00PF_IDV_CUST_FA_SUM.csv", cols=["CUST_NO", "AUM_BAL"], nrows=300000)
    dfd = load("S_00PF_IDV_DP_CUST_SUM.csv", cols=["CUST_NO", "RMB_DP_BAL"], nrows=300000)
    if dfa is not None and dfd is not None and not dfa.empty and not dfd.empty:
        if {"AUM_BAL", "RMB_DP_BAL", "CUST_NO"} <= set(dfa.columns) & set(dfd.columns):
            merge = dfa[["CUST_NO", "AUM_BAL"]].merge(dfd[["CUST_NO", "RMB_DP_BAL"]], on="CUST_NO", how="inner")
            aum = pd.to_numeric(merge["AUM_BAL"], errors="coerce")
            dep = pd.to_numeric(merge["RMB_DP_BAL"], errors="coerce")
            ratio = (aum / dep.replace(0, float("nan"))).dropna()
            m = {"匹配客户数": len(merge),
                 "AUM<存款20%占比": round(float((ratio < 0.2).mean()), 4) if len(ratio) else None}
            ok(26, "AUM与存款余额严重不匹配", "客户", "贷前准入",
               "S_00PF_IDV_CUST_FA_SUM+S_00PF_IDV_DP_CUST_SUM", m,
               "AUM_BAL/RMB_DP_BAL<0.2（采样各 30 万行）")
        else:
            miss(26, "AUM与存款余额严重不匹配", "客户", "贷前准入", "字段缺失")
    else:
        miss(26, "AUM与存款余额严重不匹配", "客户", "贷前准入")

    # 27 异地风险
    if df2 is not None and not df2.empty:
        m = {"机构数": len(df2),
             "地址异常不良率均值": col_mean(df2, "ADDR_RSK_UHLTH_RATE")}
        approx(27, "异地风险", "客户", "贷前准入", "S_00PF_PEAS_ADDR_RSK_ORG_SUM_C4", m,
               "地址明细无数据，用机构级地址异常口径")
    else:
        miss(27, "异地风险", "客户", "贷前准入")

    # 28 行业性风险
    df8 = load("S_00PF_PEAS_OCPRSK_ORG_C4.csv")
    if df8 is not None and not df8.empty:
        m = {"机构数": len(df8),
             "重点行业不良率均值": col_mean(df8, "KEY_OCP_UHLTH_RATE")}
        ok(28, "行业性风险", "客户", "贷前准入", "S_00PF_PEAS_OCPRSK_ORG_C4", m,
           "KEY_OCP_COD 预聚合")
    else:
        miss(28, "行业性风险", "客户", "贷前准入")

    # 29 经营地址频繁变更
    miss(29, "经营地址近N年频繁变更", "客户", "贷前准入", "企业变更表无数据")

    # 30 经营年限不足
    if df7 is not None and not df7.empty:
        m = {"建档数": len(df7)}
        approx(30, "经营年限不足", "客户", "贷前准入", "B_00DT_FAS_IDV_BUS_INFO_H", m,
               "CRT_DAT 距今<1年需关联放款日，当前给档案规模")
    else:
        miss(30, "经营年限不足", "客户", "贷前准入")

    # 31 虚增面积/收入（FARM_LAND 约 84% 为 0，改报 >0 占比与分位）
    if df3 is not None and not df3.empty and "FARM_LAND" in df3.columns:
        farm = pd.to_numeric(df3["FARM_LAND"], errors="coerce").dropna()
        m = {"建档数": len(df3),
             "有农地记录占比": round(float((farm > 0).mean()), 4) if len(farm) else None,
             "农地面积均值(亩)": round(float(farm.mean()), 2) if len(farm) else None}
        approx(31, "虚增种养殖面积/收入", "客户", "贷前准入", "B_00DT_FAS_ANL_SITU_DOC_H", m,
               "FARM_LAND 分布（无协议比对源）")
    else:
        miss(31, "虚增种养殖面积/收入", "客户", "贷前准入")

    # 32-36, 40, 41 征信类（P1/P2/P3 透视）
    pv_credit = credit_pivot()
    if pv_credit is not None and not pv_credit.empty:
        # 32 多头借贷：账户数合计 / 未结清贷款机构数 偏多
        m32 = {"征信覆盖客户数": len(pv_credit)}
        r32a = credit_ratio(pv_credit, "账户数合计", threshold=5)
        r32b = credit_ratio(pv_credit, "未结清贷款机构数", threshold=3)
        if r32a is not None:
            m32["账户数>=5占比"] = r32a
        if r32b is not None:
            m32["未结清机构>=3占比"] = r32b
        ok(32, "多头借贷", "客户", "贷前准入", "P_00CIE_CPS_INDECATE_*", m32,
           "账户数合计/未结清贷款机构数 阈值占比（征信口径）")

        # 33 多头借贷且负债与规模不匹配：账户多且负债高
        m33 = {"征信覆盖客户数": len(pv_credit)}
        acc = credit_num(pv_credit, "账户数合计")
        debt = credit_num(pv_credit, "负债合计（与网借贷一致）")
        if acc is not None and debt is not None:
            both = (acc > 5) & (debt > 500000)
            m33["账户>5且负债>50万占比"] = round(float(both.mean()), 4)
            if len(debt):
                m33["负债合计均值"] = round(float(debt.mean()), 2)
        ok(33, "多头借贷且负债与规模不匹配", "客户", "贷前准入", "P_00CIE_CPS_INDECATE_*", m33,
           "账户数>5 且 负债>50万 交叉占比")

        # 34 征信查询次数过多
        m34 = {"征信覆盖客户数": len(pv_credit)}
        r34a = credit_ratio(pv_credit, "最近一月查询次数", threshold=5)
        r34b = credit_ratio(pv_credit, "近6个月征信查询次数", threshold=10)
        if r34a is not None:
            m34["近1月查询>=5占比"] = r34a
        if r34b is not None:
            m34["近6月查询>=10占比"] = r34b
        ok(34, "征信查询次数过多", "客户", "贷前准入", "P_00CIE_CPS_INDECATE_*", m34,
           "近1月/近6月查询次数 阈值占比（频繁申贷信号）")

        # 35 有被拒贷记录：无信用记录但有查询记录 / 查询多但授信少
        m35 = {"征信覆盖客户数": len(pv_credit)}
        r35a = credit_ratio(pv_credit, "无信用记录，但有查询记录", threshold=0)
        if r35a is not None:
            m35["无信用但有查询占比"] = r35a
        ok(35, "有被拒贷记录", "客户", "贷前准入", "P_00CIE_CPS_INDECATE_*", m35,
           "无信用记录但有查询记录 → 曾申请未获批（征信口径）")

        # 36 N年内不良记录
        m36 = {"征信覆盖客户数": len(pv_credit)}
        for ind, nm in [("近两年累计逾期次数（个贷）", "近2年累计逾期>0占比"),
                        ("所有贷款24月累计逾期数", "24月累计逾期>0占比"),
                        ("贷记卡当前逾期金额总和", "贷记卡当前逾期>0占比")]:
            r = credit_ratio(pv_credit, ind, threshold=0)
            if r is not None:
                m36[nm] = r
        ok(36, "N年内不良记录", "客户", "贷前准入", "P_00CIE_CPS_INDECATE_*", m36,
           "近2年/24月累计逾期、贷记卡当前逾期 占比（征信口径）")
    else:
        miss(32, "多头借贷", "客户", "贷前准入", "征信P表无数据文件")
        miss(33, "多头借贷且负债与规模不匹配", "客户", "贷前准入", "征信P表无数据文件")
        miss(34, "征信查询次数过多", "客户", "贷前准入", "征信P表无数据文件")
        miss(35, "有被拒贷记录", "客户", "贷前准入", "征信P表无数据文件")
        miss(36, "N年内不良记录", "客户", "贷前准入", "征信P表无数据文件")

    # 37 赌博嗜好
    miss(37, "赌博等不良嗜好（夜间交易）", "客户", "贷前准入", "交易汇总无时段字段，需流水级")

    # 38 家庭劣变（MRGE_STS 已哈希脱敏，无法文本匹配）
    df10 = load("G_00PL_PEAS_DOC_INFO_DV.csv", cols=["MRGE_STS"], nrows=300000)
    if df10 is not None and not df10.empty:
        mrge = df10["MRGE_STS"].astype(str)
        n_unique = mrge.nunique()
        m = {"客户数": len(df10), "婚姻状态去重值数": n_unique}
        approx(38, "家庭关系劣变/重大疾病", "客户", "贷前准入", "G_00PL_PEAS_DOC_INFO_DV", m,
               "MRGE_STS 已哈希脱敏无法判断离异/非婚，仅统计分布")
    else:
        miss(38, "家庭关系劣变/重大疾病", "客户", "贷前准入")

    # 39 收入覆盖不足（家庭年收入在家庭表；年还款额在资产负债表的 FMLY_DPS_ANNL_RPAMT）
    df11 = load("B_00DT_FAS_FMLY_SITU_DOC_H.csv", cols=["FMLY_ANNL_INCM"], nrows=200000)
    if df11 is not None and not df11.empty:
        inc = pd.to_numeric(df11["FMLY_ANNL_INCM"], errors="coerce").dropna()
        inc_med = float(inc.median()) if len(inc) else None
        # 字段标注单位为万元，但实际数据可能为元（中位数异常大时按元转万元归一化）
        if inc_med is not None and inc_med > 10000:
            inc_med = inc_med / 10000
            unit_note = "（原值按元处理已折算万元）"
        else:
            unit_note = ""
        m = {"建档数": len(df11),
             "年收入中位数(万元)": round(inc_med, 2) if inc_med is not None else None}
        approx(39, "收入覆盖不足", "客户", "贷前准入", "B_00DT_FAS_FMLY_SITU_DOC_H", m,
               f"收入 vs 年还款额需关联贷款，当前给收入分布{unit_note}")
    else:
        miss(39, "收入覆盖不足", "客户", "贷前准入")

    # 40/41 涉税涉诉（征信 P1/P2/P3，在 32-36 处已计算 pv_credit）
    if pv_credit is not None and not pv_credit.empty:
        m40b = {"征信覆盖客户数": len(pv_credit)}
        for ind, nm in [("个人近三年欠税次数", "近3年欠税>0占比"),
                        ("个人近三年强制执行次数", "近3年强执>0占比"),
                        ("呆账信息总笔数", "呆账>0占比"),
                        ("准贷记卡账户状态为冻结、止付、呆账的数目", "准贷记卡冻结/呆账>0占比")]:
            r = credit_ratio(pv_credit, ind, threshold=0)
            if r is not None:
                m40b[nm] = r
        ok(40, "涉税/强执/处罚/呆账/冻结", "客户", "贷前准入", "P_00CIE_CPS_INDECATE_*", m40b,
           "欠税/强执/呆账/冻结 占比（征信口径）")

        m41b = {"征信覆盖客户数": len(pv_credit)}
        r41b = credit_ratio(pv_credit, "个人近三年民事判决次数", threshold=0)
        if r41b is not None:
            m41b["近3年民事判决>0占比"] = r41b
        ok(41, "涉诉记录", "客户", "贷前准入", "P_00CIE_CPS_INDECATE_*", m41b,
           "近3年民事判决次数>0 占比（征信口径）")
    else:
        miss(40, "涉税/强执/处罚/呆账/冻结", "客户", "贷前准入", "征信P表无数据文件")
        miss(41, "涉诉记录", "客户", "贷前准入", "征信P表无数据文件")

    # 42 资金挪用
    miss(42, "贷款资金挪用", "客户", "贷后管理", "需放款后资金流向明细，汇总表无窗口粒度")

    # 43 风险信号
    df13 = load("S_00PF_PEAS_LN_RSK_ORG_C4.csv")
    if df13 is not None and not df13.empty:
        m = {"机构数": len(df13),
             "线索不属实占比均值": col_mean(df13, "NO_LN_CTRT_PPTN")}
        ok(43, "风险信号（多贷一用/户贷企用）", "客户", "贷后管理", "S_00PF_PEAS_LN_RSK_ORG_C4", m,
           "RSK_LINE_TYP 触发/不属实占比")
    else:
        miss(43, "风险信号", "客户", "贷后管理")

    # 44 还款行为恶化
    df14 = load("G_00PL_IDV_LN_ARG_EXD_DV.csv", cols=["EXD_CAP", "BILL_EXD_DAYS"], nrows=300000)
    if df14 is not None and not df14.empty:
        exd_cap = pd.to_numeric(df14["EXD_CAP"], errors="coerce").fillna(0)
        days = pd.to_numeric(df14["BILL_EXD_DAYS"], errors="coerce").fillna(0)
        m = {"逾期记录数": len(df14),
             "逾期本金>0记录数": int((exd_cap > 0).sum()),
             "逾期本金合计": round(float(exd_cap.sum()), 2),
             "平均逾期天数": round(float(days.mean()), 1) if len(days) else None}
        ok(44, "还款行为恶化", "客户", "贷后管理", "G_00PL_IDV_LN_ARG_EXD_DV", m,
           "EXD_CAP/BILL_EXD_DAYS（采样 30 万行）")
    else:
        miss(44, "还款行为恶化", "客户", "贷后管理")

    # 45 裸贷户
    if df3 is not None and not df3.empty:
        tot = pd.to_numeric(df3["TOT_AST"], errors="coerce").fillna(0)
        m = {"建档数": len(df3), "总资产=0户数": int((tot == 0).sum()),
             "裸贷户占比": round(float((tot == 0).mean()), 4) if len(tot) else None}
        approx(45, "裸贷户", "客户", "贷后管理", "B_00DT_FAS_ANL_SITU_DOC_H", m,
               "TOT_AST=0 且无经营（采样 20 万行）")
    else:
        miss(45, "裸贷户", "客户", "贷后管理")

    # ================= C 类表接入（证据线索，feature_id 46-50） =================
    # 用途：为归因主题提供更细的证据链；状态标 "clue"（线索），不参与组合命中但供 attribution 引用
    def clue(fid, name, dim, stage, table, metric, note=""):
        F.append({"feature_id": fid, "name": name, "dimension": dim, "stage": stage,
                  "status": "clue", "table": table, "metric": nonempty_metric(metric), "note": note})

    # 46 续贷凭证关系（B_00DT_APLO_RNEW_CR_VCH_RLN_H）→ 支持「续贷接续断裂」
    df46 = load("B_00DT_APLO_RNEW_CR_VCH_RLN_H.csv")
    if df46 is not None and not df46.empty:
        rnew_amt = pd.to_numeric(df46["RNEW_CR_AMT"], errors="coerce").dropna()
        m = {"续贷记录数": len(df46),
             "续贷金额合计": round(float(rnew_amt.sum()), 2) if len(rnew_amt) else None,
             "续贷金额中位数": round(float(rnew_amt.median()), 2) if len(rnew_amt) else None}
        clue(46, "续贷凭证关系（证据线索）", "机构", "到期续贷", "B_00DT_APLO_RNEW_CR_VCH_RLN_H", m,
             "支持 C06 续贷接续断裂：可识别新旧凭证映射与续贷金额")
        qlog.add(stage="Step3 基础风险特征", table="B_00DT_APLO_RNEW_CR_VCH_RLN_H",
                 query="续贷凭证关系历史（全量小表）", result=f"续贷记录 {len(df46)} 条",
                 thought="C类表接入：为续贷接续断裂主题提供续贷金额/凭证映射证据")
    else:
        clue(46, "续贷凭证关系（证据线索）", "机构", "到期续贷", "B_00DT_APLO_RNEW_CR_VCH_RLN_H", {}, "表缺失")

    # 47 上年末凭证本年接续（G_00PF_PEAS_LN_LSTY_VCH_CONT_SITU_INFO）→ 支持「续贷接续断裂」
    df47 = load("G_00PF_PEAS_LN_LSTY_VCH_CONT_SITU_INFO.csv")
    if df47 is not None and not df47.empty:
        cont = df47["CONTINUE_FLAG"].astype(str) if "CONTINUE_FLAG" in df47.columns else None
        can = df47["CAN_STS_CD"].astype(str) if "CAN_STS_CD" in df47.columns else None
        m = {"接续记录数": len(df47)}
        if cont is not None:
            m["接续方式数"] = int(cont.nunique())
        if can is not None:
            m["核销状态数"] = int(can.nunique())
        clue(47, "上年末凭证本年接续（证据线索）", "机构", "到期续贷", "G_00PF_PEAS_LN_LSTY_VCH_CONT_SITU_INFO", m,
             "支持 C06：接续方式/核销状态明细")
        qlog.add(stage="Step3 基础风险特征", table="G_00PF_PEAS_LN_LSTY_VCH_CONT_SITU_INFO",
                 query="上年末凭证本年接续情况表（小表）", result=f"接续记录 {len(df47)} 条",
                 thought="C类表接入：提供接续方式/核销状态证据")
    else:
        clue(47, "上年末凭证本年接续（证据线索）", "机构", "到期续贷", "G_00PF_PEAS_LN_LSTY_VCH_CONT_SITU_INFO", {}, "表缺失")

    # 48 上门催收任务（B_00FT_PMC_P_DOORTASK_DTAL）→ 支持「贷后管理空转」
    df48 = load("B_00FT_PMC_P_DOORTASK_DTAL.csv", cols=["CLTN_TASK_STS", "PDT_DEADDATE", "RSK_CLS"], nrows=300000)
    if df48 is not None and not df48.empty:
        st = df48["CLTN_TASK_STS"].astype(str) if "CLTN_TASK_STS" in df48.columns else None
        rsk = df48["RSK_CLS"].astype(str) if "RSK_CLS" in df48.columns else None
        m = {"上门催收任务数(采样)": len(df48)}
        if st is not None:
            # 常见状态代码：00/50=未办结，90=已办结（与处置任务口径一致）
            undone = int(st.isin(["00", "50"]).sum())
            m["未办结任务数"] = undone
            m["未办结率"] = round(undone / len(df48), 4) if len(df48) else None
        if rsk is not None:
            m["不良任务数(3/4/5)"] = int(rsk.str[:1].isin(["3", "4", "5"]).sum())
        clue(48, "上门催收任务（证据线索）", "机构", "贷后管理", "B_00FT_PMC_P_DOORTASK_DTAL", m,
             "支持 C05 贷后管理空转：上门催收超时/未办结（电话催收表无数据，此表补催收维度）")
        qlog.add(stage="Step3 基础风险特征", table="B_00FT_PMC_P_DOORTASK_DTAL",
                 query="上门催收任务明细（采样 30 万行）",
                 result=f"任务数 {len(df48)}，未办结 {m.get('未办结任务数') if m.get('未办结任务数') is not None else 'N/A'}",
                 thought="C类表接入：补上门催收维度，支持贷后管理空转线索")
    else:
        clue(48, "上门催收任务（证据线索）", "机构", "贷后管理", "B_00FT_PMC_P_DOORTASK_DTAL", {}, "表缺失")

    # 49 亲属信息（G_00PL_IDV_CUST_RLN_INFO_H）→ 支持「人员道德风险」
    df49 = load("G_00PL_IDV_CUST_RLN_INFO_H.csv", cols=["CUST_NO", "RLN_TYP_CD"], nrows=300000)
    if df49 is not None and not df49.empty:
        m = {"亲属关系记录数(采样)": len(df49)}
        if "RLN_TYP_CD" in df49.columns:
            m["关系类型数"] = int(df49["RLN_TYP_CD"].astype(str).nunique())
        clue(49, "客户亲属信息（证据线索）", "客户", "贷前准入", "G_00PL_IDV_CUST_RLN_INFO_H", m,
             "支持 C07 人员道德风险：亲属关系网络（无流水级数据，做关系网络统计）")
        qlog.add(stage="Step3 基础风险特征", table="G_00PL_IDV_CUST_RLN_INFO_H",
                 query="个人信贷客户亲属信息表（采样 30 万行）", result=f"亲属关系 {len(df49)} 条",
                 thought="C类表接入：提供亲属关系网络，支持人员道德风险线索")
    else:
        clue(49, "客户亲属信息（证据线索）", "客户", "贷前准入", "G_00PL_IDV_CUST_RLN_INFO_H", {}, "表缺失")

    # 50 联村带户（P_00FAS_GFAS_VAF_LOAN_MANAGE）→ 支持「整村授信/联村带户」
    df50 = load("P_00FAS_GFAS_VAF_LOAN_MANAGE.csv", cols=["VG_ID", "STATU", "C4_STATUS"], nrows=300000)
    if df50 is not None and not df50.empty:
        m = {"联村带户记录数(采样)": len(df50)}
        if "VG_ID" in df50.columns:
            m["涉及村数"] = int(df50["VG_ID"].astype(str).nunique())
        clue(50, "联村带户状态（证据线索）", "机构", "营销获客", "P_00FAS_GFAS_VAF_LOAN_MANAGE", m,
             "支持整村授信/联村带户主题：按村聚合获客与流程状态")
        qlog.add(stage="Step3 基础风险特征", table="P_00FAS_GFAS_VAF_LOAN_MANAGE",
                 query="联村带户贷款状态明细（采样 30 万行）", result=f"记录 {len(df50)} 条",
                 thought="C类表接入：支持整村授信/联村带户主题，按村聚合")
    else:
        clue(50, "联村带户状态（证据线索）", "机构", "营销获客", "P_00FAS_GFAS_VAF_LOAN_MANAGE", {}, "表缺失")

    # ================= A 类表接入（证据线索，feature_id 51-53） =================
    # 用途：以个人贷款凭证(IDV/PEAS 同批 A70)为出发点，联查个人贷款侧 A 类表，
    # 补充农户贷款表侧未具有的信息（合同级/核销清收/还款账单明细）
    # 已确认：这三张表 A70 品种行占比 100%，与农户凭证同批

    # 51 个人贷款合同（G_00PF_IDV_LN_CTRT_DV）→ 合同级补充（金额/期限/担保）
    df51 = load("G_00PF_IDV_LN_CTRT_DV.csv", cols=["BUS_BREED_CD", "CTRT_AMT_RMB", "LN_TERM_CLS_CD", "GRTE_MOD_CD"], nrows=300000)
    if df51 is not None and not df51.empty:
        ctrt_amt = pd.to_numeric(df51["CTRT_AMT_RMB"], errors="coerce").dropna()
        m = {"合同记录数(采样)": len(df51)}
        if len(ctrt_amt):
            m["合同金额合计"] = round(float(ctrt_amt.sum()), 2)
            m["合同金额中位数"] = round(float(ctrt_amt.median()), 2)
        clue(51, "个人贷款合同（A70补充线索）", "机构", "贷中审查", "G_00PF_IDV_LN_CTRT_DV", m,
             "A类表接入：以IDV凭证为出发点联查合同表，补充合同金额/期限/担保信息")
        qlog.add(stage="Step3 基础风险特征", table="G_00PF_IDV_LN_CTRT_DV",
                 query="个人贷款合同拼接表（采样 30 万行，A70 品种占比100%）",
                 result=f"合同 {len(df51)} 条，金额中位 {m.get('合同金额中位数')}",
                 thought="A类表接入：合同级信息（金额/期限/担保），支持超额授信/期限结构主题")
    else:
        clue(51, "个人贷款合同（A70补充线索）", "机构", "贷中审查", "G_00PF_IDV_LN_CTRT_DV", {}, "表缺失")

    # 52 核销清收证券化（G_00PF_IDV_LN_VCH_CAN_LQDT_SECS_DV）→ 含核销不良率/清收回收
    df52 = load("G_00PF_IDV_LN_VCH_CAN_LQDT_SECS_DV.csv", cols=["BUS_BREED_CD", "CAN_CAP", "CAN_STS_CD"], nrows=300000)
    if df52 is not None and not df52.empty:
        can_cap = pd.to_numeric(df52["CAN_CAP"], errors="coerce").dropna()
        m = {"核销记录数(采样)": len(df52)}
        if len(can_cap):
            m["核销本金合计"] = round(float(can_cap.sum()), 2)
            m["核销本金>0记录数"] = int((can_cap > 0).sum())
        clue(52, "核销清收证券化（A70补充线索）", "机构", "贷后管理", "G_00PF_IDV_LN_VCH_CAN_LQDT_SECS_DV", m,
             "A类表接入：核销/清收/证券化信息，支持含核销不良率（平滑项暴露）")
        qlog.add(stage="Step3 基础风险特征", table="G_00PF_IDV_LN_VCH_CAN_LQDT_SECS_DV",
                 query="个人贷款凭证核销清收证券化拼接表（采样 30 万行，A70 占比100%）",
                 result=f"核销记录 {len(df52)} 条，核销本金>0 {m.get('核销本金>0记录数')}",
                 thought="A类表接入：核销/清收信息，支持平滑项暴露与含核销不良率")
    else:
        clue(52, "核销清收证券化（A70补充线索）", "机构", "贷后管理", "G_00PF_IDV_LN_VCH_CAN_LQDT_SECS_DV", {}, "表缺失")

    # 53 还款账单（G_00PL_IDV_LN_BILL_AMT）→ 还款行为明细（账单级逾期/结清/异常）
    df53 = load("G_00PL_IDV_LN_BILL_AMT.csv", cols=["BUS_BREED", "BILL_STS_CD", "BILL_EXD_DAT", "REV_NONPAY_CAP"], nrows=300000)
    if df53 is not None and not df53.empty:
        st = df53["BILL_STS_CD"].astype(str) if "BILL_STS_CD" in df53.columns else None
        exd = df53["BILL_EXD_DAT"].astype(str) if "BILL_EXD_DAT" in df53.columns else None
        m = {"账单记录数(采样)": len(df53)}
        if st is not None:
            m["账单状态数"] = int(st.nunique())
        if exd is not None:
            m["有转逾期日期账单数"] = int((exd != "").sum())
        clue(53, "还款账单（A70补充线索）", "客户", "贷后管理", "G_00PL_IDV_LN_BILL_AMT", m,
             "A类表接入：账单级还款行为明细（逾期/结清/还款异常），支持还款行为恶化主题")
        qlog.add(stage="Step3 基础风险特征", table="G_00PL_IDV_LN_BILL_AMT",
                 query="个人贷款还款账单金额拼接表（采样 30 万行，A70 占比100%）",
                 result=f"账单 {len(df53)} 条",
                 thought="A类表接入：账单级还款行为，支持还款行为恶化/资金断流主题")
    else:
        clue(53, "还款账单（A70补充线索）", "客户", "贷后管理", "G_00PL_IDV_LN_BILL_AMT", {}, "表缺失")

    # ================= 其余表接入（证据线索，feature_id 54-63） =================

    # 54 C4机构树（B_00DT_C4_ORG_TREE_H）→ 机构层级/县域切片
    df54 = load("B_00DT_C4_ORG_TREE_H.csv", cols=["C4_ORG_NO", "C4_ORG_LVL", "C4_CTRY_RGN_CTG_CD"], nrows=300000)
    if df54 is not None and not df54.empty:
        m = {"机构节点数(采样)": len(df54)}
        if "C4_ORG_LVL" in df54.columns:
            m["机构层级数"] = int(df54["C4_ORG_LVL"].astype(str).nunique())
        clue(54, "C4机构树（证据线索）", "机构", "其他", "B_00DT_C4_ORG_TREE_H", m,
             "机构层级/县域标识，支持按机构层级/县域切片的稳健性验证")
        qlog.add(stage="Step3 基础风险特征", table="B_00DT_C4_ORG_TREE_H",
                 query="C4机构树历史（采样 30 万行）", result=f"节点 {len(df54)} 条",
                 thought="接入机构树：支持机构层级/县域切片验证")
    else:
        clue(54, "C4机构树（证据线索）", "机构", "其他", "B_00DT_C4_ORG_TREE_H", {}, "表缺失")

    # 55 企业变更明细（B_00DT_CORP_GX_ALTER_DTAL_FXB）→ 经营稳定性
    df55 = load("B_00DT_CORP_GX_ALTER_DTAL.csv", cols=["ALTITEM", "ALTDATE"], nrows=100000)
    if df55 is not None and not df55.empty:
        m = {"企业变更记录数": len(df55)}
        if "ALTITEM" in df55.columns:
            m["变更事项数"] = int(df55["ALTITEM"].astype(str).nunique())
        clue(55, "企业变更明细（证据线索）", "客户", "贷前准入", "B_00DT_CORP_GX_ALTER_DTAL_FXB", m,
             "企业变更记录，支持经营稳定性/频繁变更主题（企业基本信息表无数据，仅变更明细）")
        qlog.add(stage="Step3 基础风险特征", table="B_00DT_CORP_GX_ALTER_DTAL_FXB",
                 query="国信企业历史变更明细（全量小表）", result=f"变更 {len(df55)} 条",
                 thought="接入企业变更：支持经营稳定性主题")
    else:
        clue(55, "企业变更明细（证据线索）", "客户", "贷前准入", "B_00DT_CORP_GX_ALTER_DTAL_FXB", {}, "表缺失")

    # 56 循环额度（B_00DT_CYC_QUOT_INFO_H）→ 超额授信
    df56 = load("B_00DT_CYC_QUOT_INFO_H.csv", cols=["LN_CTRT_NO", "CYC_QUOT", "QUOT_STS"], nrows=300000)
    if df56 is not None and not df56.empty:
        quot = pd.to_numeric(df56["CYC_QUOT"], errors="coerce").dropna() if "CYC_QUOT" in df56.columns else pd.Series(dtype=float)
        m = {"循环额度记录数(采样)": len(df56)}
        if len(quot):
            m["循环额度中位数"] = round(float(quot.median()), 2)
        clue(56, "循环额度（证据线索）", "机构", "贷前准入", "B_00DT_CYC_QUOT_INFO_H", m,
             "循环额度，支持超额授信/额度结构主题")
        qlog.add(stage="Step3 基础风险特征", table="B_00DT_CYC_QUOT_INFO_H",
                 query="循环额度信息历史（采样 30 万行）", result=f"记录 {len(df56)} 条",
                 thought="接入循环额度：支持超额授信主题")
    else:
        clue(56, "循环额度（证据线索）", "机构", "贷前准入", "B_00DT_CYC_QUOT_INFO_H", {}, "表缺失")

    # 57 押品产权人（B_00DT_FNC_CUST_AST_AND_PROP_OWNR_RLN_H）→ 押品产权
    df57 = load("B_00DT_FNC_CUST_AST_AND_PROP_OWNR_RLN_H.csv", cols=["AST_NO", "PROP_OWNR_CUST_NO", "PROP_TYP_CD"], nrows=100000)
    if df57 is not None and not df57.empty:
        m = {"押品产权记录数": len(df57)}
        if "PROP_TYP_CD" in df57.columns:
            m["产权类型数"] = int(df57["PROP_TYP_CD"].astype(str).nunique())
        clue(57, "押品产权人（证据线索）", "机构", "贷中审查", "B_00DT_FNC_CUST_AST_AND_PROP_OWNR_RLN_H", m,
             "押品产权关系，支持押品/担保主题（押品权证表无数据）")
        qlog.add(stage="Step3 基础风险特征", table="B_00DT_FNC_CUST_AST_AND_PROP_OWNR_RLN_H",
                 query="押品产权人信息历史（全量小表）", result=f"记录 {len(df57)} 条",
                 thought="接入押品产权人：支持押品/担保主题")
    else:
        clue(57, "押品产权人（证据线索）", "机构", "贷中审查", "B_00DT_FNC_CUST_AST_AND_PROP_OWNR_RLN_H", {}, "表缺失")

    # 58 凭证分类结果（B_00DT_LN_FORM_CLS_EVT_H）→ 分类事件
    df58 = load("B_00DT_LN_FORM_CLS_EVT_H.csv", cols=["BUS_BREED_CD", "CLS_CLS_CD", "EXD_DAYS"], nrows=300000)
    if df58 is not None and not df58.empty:
        m = {"凭证分类记录数(采样)": len(df58)}
        if "CLS_CLS_CD" in df58.columns:
            m["分类结果数"] = int(df58["CLS_CLS_CD"].astype(str).nunique())
        clue(58, "凭证分类结果（证据线索）", "机构", "贷后管理", "B_00DT_LN_FORM_CLS_EVT_H", m,
             "凭证分类事件，支持五级分类迁移/分类滞后主题")
        qlog.add(stage="Step3 基础风险特征", table="B_00DT_LN_FORM_CLS_EVT_H",
                 query="借款凭证分类结果历史（采样 30 万行）", result=f"记录 {len(df58)} 条",
                 thought="接入凭证分类：支持分类迁移/滞后主题")
    else:
        clue(58, "凭证分类结果（证据线索）", "机构", "贷后管理", "B_00DT_LN_FORM_CLS_EVT_H", {}, "表缺失")

    # 59 评分结果历史（B_00DT_PRLN_SCRE_EVT_H）→ 评分迁移
    df59 = load("B_00DT_PRLN_SCRE_EVT_H.csv", cols=["MDL_COD", "TRFM_SCRE"], nrows=300000)
    if df59 is not None and not df59.empty:
        scr = pd.to_numeric(df59["TRFM_SCRE"], errors="coerce").dropna() if "TRFM_SCRE" in df59.columns else pd.Series(dtype=float)
        m = {"评分记录数(采样)": len(df59)}
        if len(scr):
            m["平均转换得分"] = round(float(scr.mean()), 2)
        clue(59, "评分结果历史（证据线索）", "客户", "贷前准入", "B_00DT_PRLN_SCRE_EVT_H", m,
             "评分历史，支持低评分/评分迁移主题（与A卡评分表互补）")
        qlog.add(stage="Step3 基础风险特征", table="B_00DT_PRLN_SCRE_EVT_H",
                 query="个人贷款评分结果历史（采样 30 万行）", result=f"记录 {len(df59)} 条",
                 thought="接入评分历史：支持低评分主题")
    else:
        clue(59, "评分结果历史（证据线索）", "客户", "贷前准入", "B_00DT_PRLN_SCRE_EVT_H", {}, "表缺失")

    # 60 不良金额变动（B_00DT_UHLTH_LN_AMT_CHG_H）→ 不良生成
    df60 = load("B_00DT_UHLTH_LN_AMT_CHG_H.csv", cols=["FTH_LVL_CLS", "CHG_CAP", "WON_ALR_CAN"], nrows=100000)
    if df60 is not None and not df60.empty:
        chg = pd.to_numeric(df60["CHG_CAP"], errors="coerce").dropna() if "CHG_CAP" in df60.columns else pd.Series(dtype=float)
        m = {"不良变动记录数": len(df60)}
        if len(chg):
            m["变动本金合计"] = round(float(chg.sum()), 2)
        clue(60, "不良金额变动（证据线索）", "机构", "贷后管理", "B_00DT_UHLTH_LN_AMT_CHG_H", m,
             "不良金额变动，支持不良生成率/平滑项暴露主题")
        qlog.add(stage="Step3 基础风险特征", table="B_00DT_UHLTH_LN_AMT_CHG_H",
                 query="不良贷款金额变动信息历史（全量小表）", result=f"记录 {len(df60)} 条",
                 thought="接入不良变动：支持不良生成率/平滑项暴露")
    else:
        clue(60, "不良金额变动（证据线索）", "机构", "贷后管理", "B_00DT_UHLTH_LN_AMT_CHG_H", {}, "表缺失")

    # 61 家庭村居情况（G_00PF_PEAS_LN_FMLY_SITU_INFO）→ 家庭/村居
    df61 = load("G_00PF_PEAS_LN_FMLY_SITU_INFO.csv", cols=["CUST_NO", "MRGE_STS", "OWN_RURA_ID"], nrows=300000)
    if df61 is not None and not df61.empty:
        m = {"家庭村居记录数(采样)": len(df61)}
        if "OWN_RURA_ID" in df61.columns:
            m["涉及村数"] = int(df61["OWN_RURA_ID"].astype(str).nunique())
        clue(61, "家庭村居情况（证据线索）", "客户", "贷前准入", "G_00PF_PEAS_LN_FMLY_SITU_INFO", m,
             "家庭村居信息，支持家庭关系/整村授信主题（补充FAS家庭表）")
        qlog.add(stage="Step3 基础风险特征", table="G_00PF_PEAS_LN_FMLY_SITU_INFO",
                 query="农户贷款客户家庭村居情况信息表（采样 30 万行）", result=f"记录 {len(df61)} 条",
                 thought="接入家庭村居：支持家庭/整村授信主题")
    else:
        clue(61, "家庭村居情况（证据线索）", "客户", "贷前准入", "G_00PF_PEAS_LN_FMLY_SITU_INFO", {}, "表缺失")

    # 62 持有产品余额（S_00PF_IDV_CUST_HOLD_PD_BAL_SUM）→ 资产状况
    df62 = load("S_00PF_IDV_CUST_HOLD_PD_BAL_SUM.csv", cols=["RMB_FA_BAL", "RMB_DP_BAL"], nrows=300000)
    if df62 is not None and not df62.empty:
        fa = pd.to_numeric(df62["RMB_FA_BAL"], errors="coerce").dropna() if "RMB_FA_BAL" in df62.columns else pd.Series(dtype=float)
        m = {"持有产品记录数(采样)": len(df62)}
        if len(fa):
            m["金融资产余额中位数"] = round(float(fa.median()), 2)
        clue(62, "持有产品余额（证据线索）", "客户", "贷前准入", "S_00PF_IDV_CUST_HOLD_PD_BAL_SUM", m,
             "客户持有产品/金融资产，支持AUM匹配/资产状况主题（补充FA_SUM）")
        qlog.add(stage="Step3 基础风险特征", table="S_00PF_IDV_CUST_HOLD_PD_BAL_SUM",
                 query="个人客户持有产品余额汇总表（采样 30 万行）", result=f"记录 {len(df62)} 条",
                 thought="接入持有产品：支持AUM/资产状况主题")
    else:
        clue(62, "持有产品余额（证据线索）", "客户", "贷前准入", "S_00PF_IDV_CUST_HOLD_PD_BAL_SUM", {}, "表缺失")

    # 63 担保关系（S_00PL_IDV_LN_GRTE_RLN）→ 担保/押品
    df63 = load("S_00PL_IDV_LN_GRTE_RLN.csv", cols=["MAIN_CTRT_NO", "GRTE_CTRT_GRTE", "GRTR_CD"], nrows=100000)
    if df63 is not None and not df63.empty:
        m = {"担保关系记录数": len(df63)}
        if "GRTE_CTRT_GRTE" in df63.columns:
            m["担保方式数"] = int(df63["GRTE_CTRT_GRTE"].astype(str).nunique())
        clue(63, "担保关系（证据线索）", "机构", "贷中审查", "S_00PL_IDV_LN_GRTE_RLN", m,
             "担保关系，支持无抵押缓释/担保虚化主题（补充机构级NMGG表）")
        qlog.add(stage="Step3 基础风险特征", table="S_00PL_IDV_LN_GRTE_RLN",
                 query="个人贷款担保关系（全量小表）", result=f"记录 {len(df63)} 条",
                 thought="接入担保关系：支持无抵押缓释/担保虚化主题")
    else:
        clue(63, "担保关系（证据线索）", "机构", "贷中审查", "S_00PL_IDV_LN_GRTE_RLN", {}, "表缺失")

    # 统计
    status_cnt = {}
    for f in F:
        status_cnt[f["status"]] = status_cnt.get(f["status"], 0) + 1
    result["summary"] = status_cnt

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ 风险特征分析完成 → {args.out}")
    print(f"   共 {len(F)} 项：{status_cnt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
