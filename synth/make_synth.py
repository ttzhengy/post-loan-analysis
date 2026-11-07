#!/usr/bin/env python3
"""make_synth.py — 合成测试数据生成器（纯标准库）

用途：沙箱环境下没有真实 parquet 数据（10GB 在用户本地），生成 4 套
差异极大的合成 JSON 数据集，用于验证「报告主题是否真的随数据变化」。

构造意图（对应 preview/README.md）：
  dataset_01  获客与准入失守  → 期望触发 C01/C02 类 & 管理端线索
  dataset_02  接续滚动与道德风险 → 期望触发 C06/C07 类 & 接续链线索
  dataset_03  全弱信号        → 期望退化为「指标监测式」，0 个主题
  dataset_04  缺 cohort 数据  → 期望降级标注，不得出现「显著」

用法：
  python3 synth/make_synth.py --out synth/dataset_01 --profile p1
  python3 synth/make_synth.py --all --outdir synth
"""
import argparse
import json
import math
import os
import random

# ---------------------------------------------------------------- 工具


def w(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


# ---------------------------------------------------------------- 特征库
# (feature_id, name, dimension, stage)
FEATURE_LIB = [
    (1, "零散获客", "机构", "贷前"),
    (2, "无抵押缓释", "机构", "贷前"),
    (3, "低评分准入", "机构", "贷前"),
    (4, "建档不规范", "机构", "贷前"),
    (5, "欺诈风险敞口", "机构", "贷前"),
    (6, "信用负债敞口", "机构", "贷前"),
    (7, "超额授信", "机构", "贷前"),
    (8, "审查质量", "机构", "贷前"),
    (9, "贷后管理不到位", "机构", "贷后"),
    (10, "接续不到位", "机构", "贷后"),
    (11, "高风险客户经理", "客户经理", "贷后"),
    (12, "高风险产品", "机构", "贷前"),
    (13, "大额信用风险", "机构", "贷前"),
    (14, "批量建档", "客户经理", "贷前"),
    (15, "调查造假", "客户经理", "贷前"),
    (16, "信息录入失真", "客户经理", "贷前"),
    (17, "与客户资金往来", "客户经理", "贷后"),
    (18, "贷后检查流于形式", "客户经理", "贷后"),
    (19, "管户负担过重", "客户经理", "贷后"),
    (20, "虚假经营流水", "客户", "贷后"),
    (21, "短期资金异常", "客户", "贷后"),
    (22, "共用经营场所", "客户", "贷前"),
    (23, "频繁试探申请", "客户", "贷前"),
    (24, "押品高评高贷", "客户", "贷前"),
    (25, "买壳新注册", "客户", "贷前"),
    (26, "AUM不匹配", "客户", "贷后"),
    (27, "异地风险", "客户", "贷前"),
    (28, "行业性风险", "机构", "贷前"),
    (29, "地址频繁变更", "客户", "贷后"),
    (30, "经营年限不足", "客户", "贷前"),
    (31, "虚增面积收入", "客户", "贷前"),
    (32, "多头借贷", "客户", "贷前"),
    (33, "负债不匹配", "客户", "贷前"),
    (34, "征信查询过多", "客户", "贷前"),
    (35, "被拒贷记录", "客户", "贷前"),
    (36, "N年内不良记录", "客户", "贷前"),
    (37, "赌博嗜好", "客户", "贷后"),
    (38, "家庭劣变", "客户", "贷后"),
    (39, "收入覆盖不足", "客户", "贷前"),
    (40, "涉税强执", "客户", "贷后"),
    (41, "涉诉", "客户", "贷后"),
    (42, "资金挪用", "客户", "贷后"),
    (43, "风险信号未处置", "客户", "贷后"),
    (44, "还款行为恶化", "客户", "贷后"),
    (45, "裸贷户", "客户", "贷后"),
]

# 每个 profile 给每项特征一个 (值, 基线) —— 决定强度分量
# 值/基线 偏离越大，强度分量越高
PROFILES = {
    # P1：获客激进 + 准入失守（贷前端）
    "p1": {
        "desc": "获客激进与准入失守：贷前特征普遍失控，贷后相对正常",
        "overall": {"bal": 8.62e9, "npl_bal": 3.41e8, "npl_rate": 0.0396,
                    "cnt": 412877, "cust_cnt": 286431, "person_cnt": 271058,
                    "vch_cnt": 398442, "exd_bal": 5.12e8},
        "hot": {1: 3.4, 2: 3.1, 3: 2.9, 5: 2.4, 6: 2.2, 8: 2.6, 14: 2.5, 23: 2.0},
        "cold": {9, 10, 11, 17, 18, 19, 42, 43, 44},
        "cohort": {1: 1.9, 2: 1.6, 3: 2.2, 5: 1.4, 8: 1.8},
        "clue_hot": ["零散获客", "无抵押缓释", "低评分准入"],
        "cont_hot": "RNEW",
        "dim_hot": {"guarantee": "信用", "cust_type": "新客户", "score": "低分段"},
    },
    # P2：接续滚动 + 人员道德（贷后端）
    "p2": {
        "desc": "接续滚动与道德风险：贷后环节失控，接续工具被当作风险缓冲",
        "overall": {"bal": 8.62e9, "npl_bal": 5.87e8, "npl_rate": 0.0681,
                    "cnt": 412877, "cust_cnt": 286431, "person_cnt": 271058,
                    "vch_cnt": 398442, "exd_bal": 9.31e8},
        "hot": {9: 3.5, 10: 3.3, 11: 3.2, 17: 3.6, 18: 2.9, 19: 2.4,
                42: 2.8, 43: 3.0, 44: 3.1, 41: 2.2},
        "cold": {1, 2, 3, 4, 5, 8, 14, 15, 23},
        "cohort": {10: 2.4, 11: 2.8, 17: 3.1, 44: 2.0},
        "clue_hot": ["高风险客户经理", "接续不到位", "风险信号未处置"],
        "cont_hot": "BAD_AGN",
        "dim_hot": {"year": "续贷客户", "org": "高风险机构", "score": "低分段"},
    },
    # P3：全弱信号 —— 一切正常，不应产生任何主题
    "p3": {
        "desc": "全弱信号：资产质量平稳，所有特征均在基线附近",
        "overall": {"bal": 8.62e9, "npl_bal": 8.62e7, "npl_rate": 0.0100,
                    "cnt": 412877, "cust_cnt": 286431, "person_cnt": 271058,
                    "vch_cnt": 398442, "exd_bal": 1.02e8},
        "hot": {},
        "cold": set(range(1, 46)),
        "cohort": {},
        "clue_hot": [],
        "cont_hot": None,
        "dim_hot": {},
    },
    # P4：同 P1 但完全没有 cohort 校验数据 —— 验证降级
    "p4": {
        "desc": "缺客群校验数据：线索命中但无法验证不良差异，应降级为「一般」",
        "overall": {"bal": 8.62e9, "npl_bal": 3.41e8, "npl_rate": 0.0396,
                    "cnt": 412877, "cust_cnt": 286431, "person_cnt": 271058,
                    "vch_cnt": 398442, "exd_bal": 5.12e8},
        "hot": {1: 3.4, 2: 3.1, 3: 2.9, 5: 2.4, 8: 2.6, 14: 2.5},
        "cold": {9, 10, 11, 17, 44},
        "cohort": None,  # ← 关键：无校验
        "clue_hot": ["零散获客", "低评分准入"],
        "cont_hot": "RNEW",
        "dim_hot": {"guarantee": "信用", "score": "低分段"},
    },
}

DIMS = {
    "guarantee": ("担保方式", "贷前", ["信用", "保证", "抵押", "质押"]),
    "cust_type": ("客户类型", "贷前", ["新客户", "存量客户", "脱贫户", "新型经营主体"]),
    "industry": ("投向行业", "贷前", ["种植业", "养殖业", "农产品加工", "商贸流通", "其他"]),
    "term": ("贷款期限", "贷前", ["1年以内", "1-3年", "3年以上"]),
    "amount": ("放款金额", "贷前", ["5万以下", "5-20万", "20-50万", "50万以上"]),
    "year": ("放款年份", "贷后", ["2023以前", "2023", "2024", "2025", "2026"]),
    "score": ("评分分段", "贷前", ["低分段", "中分段", "高分段"]),
    "org": ("机构分布", "管理", ["高风险机构", "正常机构"]),
}


def build_signals(profile_key):
    p = PROFILES[profile_key]
    ov = p["overall"]
    base_rate = ov["npl_rate"]
    rnd = random.Random(hash(profile_key) & 0xFFFF)

    # ---- dimensions
    dims = {}
    for dk, (dname, stage, buckets) in DIMS.items():
        rows = []
        hot_bucket = p["dim_hot"].get(dk)
        w_rest = 1.0 / max(1, len(buckets) - (1 if hot_bucket else 0))
        for b in buckets:
            share = 0.55 if b == hot_bucket else w_rest * 0.92
            r = clamp(base_rate * (2.6 if b == hot_bucket else rnd.uniform(0.55, 1.05)),
                      0.0001, 0.95)
            rows.append({
                "bucket": b,
                "bal": round(ov["bal"] * share, 2),
                "npl_bal": round(ov["bal"] * share * r, 2),
                "npl_rate": round(r, 6),
                "npl_share": round(share, 4),
                "offset_pp": round((r - base_rate) * 100, 4),
                "reference_ctl": {"normal_share": round(1 - r, 4),
                                  "npl_share": round(r, 4)},
                "valid": True,
            })
        dims[dk] = {"name": dname, "stage": stage, "buckets": rows}

    # ---- clue_matrix（线索级不良率，来自 S_*_RSK_ORG_C4 长表）
    clue_matrix = {}
    all_clue_names = [
        "零散获客", "无抵押缓释", "低评分准入", "建档不规范", "欺诈风险敞口",
        "超额授信", "审查质量", "贷后管理不到位", "接续不到位", "高风险客户经理",
        "高风险产品", "大额信用风险", "多头借贷", "征信查询过多", "涉诉",
        "风险信号未处置", "裸贷户", "资金挪用",
    ]
    for cn in all_clue_names:
        is_hot = cn in p["clue_hot"]
        lift = rnd.uniform(2.2, 4.5) if is_hot else rnd.uniform(0.6, 1.15)
        trig_pptn = rnd.uniform(0.06, 0.22) if is_hot else rnd.uniform(0.01, 0.05)
        verify_false = (rnd.uniform(0.05, 0.18) if is_hot
                        else rnd.uniform(0.25, 0.55))
        clue_matrix[cn] = {
            "trigger_ctrt_cnt": int(ov["cnt"] * trig_pptn),
            "trigger_ctrt_pptn": round(trig_pptn, 6),
            "trigger_cust_cnt": int(ov["cust_cnt"] * trig_pptn * 0.9),
            "trigger_bal": round(ov["bal"] * trig_pptn * 1.1, 2),
            "trigger_npl_ctrt_cnt": int(ov["cnt"] * trig_pptn * base_rate * lift),
            "trigger_npl_pptn": round(clamp(base_rate * lift, 0, 0.95), 6),
            "verify_false_pptn": round(verify_false, 6),
            "npl_lift": round(lift, 4),
            "base_rate": base_rate,
            "basis": "contract",
            "coverage_bal_pptn": round(trig_pptn * 1.1, 6),
        }

    # ---- features
    # 语义约定（关键）：feature.metric「<特征>强度」是一个**倍数型指标**，
    #   = 当期实测值 / 全辖正常水平。baseline 恒为 1.0。
    #   < 1.0 表示优于正常；≈1.0 表示正常；> 1.0 表示恶化，倍数即恶化程度。
    # 命中阈值 hit_min_dev=0.20 是「相对基线偏离 ≥20%」，即 metric ≥ 1.20。
    # 冷特征必须落在「正常区间」：0.80 ~ 1.15（高于阈值以下，不命中）
    feats = []
    for fid, name, dim, stage in FEATURE_LIB:
        dev = p["hot"].get(fid)
        if dev is not None:
            metric_val = round(dev, 4)          # 热特征：1.9~3.6 倍，明显恶化
        else:
            metric_val = round(rnd.uniform(0.80, 1.15), 4)   # 冷特征：正常区间
        label = f"{name}强度"
        feats.append({
            "feature_id": fid, "name": name, "dimension": dim, "stage": stage,
            "status": "ok",
            "metric": {label: metric_val},
            "baseline": {label: 1.0},
            "numerator": int(ov["cnt"] * min(0.9, max(0.01, metric_val - 1) * 0.12)),
            "denominator": ov["cnt"],
            "note": "合成数据：metric 为倍数型强度（实测/正常水平），baseline=1.0",
        })

    # ---- continuation
    tools = {}
    for tk, tname in [("no_principal_renew", "无还本续贷"),
                      ("one_click_renew", "一键续贷"),
                      ("extension", "展期"),
                      ("restructure_normal", "非不良重组"),
                      ("restructure_bad", "不良重组")]:
        hot = (p["cont_hot"] == {
            "CTNU": "no_principal_renew", "ONE_CTNU": "one_click_renew",
            "RNEW": "extension", "NOT_BAD_AGN": "restructure_normal",
            "BAD_AGN": "restructure_bad"}.get(p["cont_hot"]))
        r = clamp(base_rate * (3.2 if hot else rnd.uniform(0.5, 1.2)), 0.0001, 0.95)
        bal = ov["bal"] * (0.13 if hot else rnd.uniform(0.01, 0.05))
        tools[tk] = {"label": tname, "bal": round(bal, 2),
                     "npl_bal": round(bal * r, 2), "npl_rate": round(r, 6)}
    chain = {
        "rolling": {"cnt": int(ov["cnt"] * (0.18 if profile_key == "p2" else 0.04)),
                    "npl_rate": round(clamp(base_rate * (2.4 if profile_key == "p2" else 0.9),
                                            0.0001, 0.95), 6)},
        "resolving": {"cnt": int(ov["cnt"] * 0.03),
                      "npl_rate": round(clamp(base_rate * 0.55, 0.0001, 0.95), 6)},
    }

    return {
        "schema_version": "3.0", "slice": "20260831",
        "profile": profile_key, "profile_desc": p["desc"],
        "overall": ov, "dimensions": dims, "clue_matrix": clue_matrix,
        "features": feats, "continuation": {"tools": tools, "chain": chain},
        "cohort_available": p["cohort"] is not None,
        "warnings": [] if p["cohort"] is not None else ["无客群级校验数据，线索级结论降级"],
    }


def build_cohort(profile_key, signals):
    p = PROFILES[profile_key]
    if p["cohort"] is None:
        return None
    base = signals["overall"]["npl_rate"]
    out = {"schema_version": "3.0", "cohorts": []}
    for fid, lift in p["cohort"].items():
        name = next((n for i, n, _, _ in FEATURE_LIB if i == fid), str(fid))
        npl_rate = clamp(base * lift, 0.0001, 0.95)
        out["cohorts"].append({
            "feature_id": fid, "name": name,
            "size": 12000 + fid * 137,
            "npl_rate": round(npl_rate, 6),
            "lift": round(lift, 4),
            "incremental_lift": round(1 + (lift - 1) * 0.25, 4),
            "npl_share": round(clamp(npl_rate * 0.6, 0, 1), 4),
        })
    return out


def build_metrics(signals):
    ov = signals["overall"]
    return {
        "schema_version": "3.0", "slice": "20260831",
        "overall": dict(ov),
        "exd_seg": {
            "1-30天": {"bal": ov["exd_bal"] * 0.42, "cnt": 1520},
            "31-90天": {"bal": ov["exd_bal"] * 0.27, "cnt": 880},
            "91-180天": {"bal": ov["exd_bal"] * 0.19, "cnt": 430},
            "180天以上": {"bal": ov["exd_bal"] * 0.12, "cnt": 210},
        },
        "by_org": [{"group": f"机构{i:02d}", "bal": ov["bal"] * (0.14 - i * 0.008),
                    "npl_bal": ov["npl_bal"] * (0.19 - i * 0.014),
                    "npl_rate": ov["npl_rate"] * (1.7 - i * 0.15),
                    "cnt": int(ov["cnt"] * 0.09)} for i in range(1, 9)],
        "by_mgr": [{"group": f"M{i:03d}", "bal": ov["bal"] * 0.02,
                    "npl_bal": ov["npl_bal"] * (0.11 - i * 0.007),
                    "npl_rate": ov["npl_rate"] * (2.1 - i * 0.18),
                    "cnt": int(ov["cnt"] * 0.006)} for i in range(1, 9)],
        "by_breed": [{"group": "A7001", "bal": ov["bal"] * 0.46,
                      "npl_bal": ov["npl_bal"] * 0.51,
                      "npl_rate": ov["npl_rate"] * 1.1, "cnt": int(ov["cnt"] * 0.4)},
                     {"group": "A7002", "bal": ov["bal"] * 0.33,
                      "npl_bal": ov["npl_bal"] * 0.29,
                      "npl_rate": ov["npl_rate"] * 0.88, "cnt": int(ov["cnt"] * 0.35)},
                     {"group": "A7003", "bal": ov["bal"] * 0.21,
                      "npl_bal": ov["npl_bal"] * 0.20,
                      "npl_rate": ov["npl_rate"] * 0.95, "cnt": int(ov["cnt"] * 0.25)}],
        "warnings": [],
    }


def build_features_j(signals):
    return {"schema_version": "3.0", "slice": "20260831",
            "features": signals["features"], "warnings": []}


def build_org_risk(signals):
    return {"schema_version": "3.0", "slice": "20260831",
            "dimensions": {k: {"name": v["name"], "stage": v["stage"],
                               "buckets": v["buckets"]}
                           for k, v in signals["dimensions"].items()},
            "warnings": []}


def build_overview(signals):
    ov = signals["overall"]
    base = ov["npl_rate"]
    return {
        "schema_version": "3.0", "slice": "20260831",
        "groups": {
            "normal": {"bal": ov["bal"] * 0.93, "cnt": int(ov["cnt"] * 0.94),
                       "cust_cnt": int(ov["cust_cnt"] * 0.95), "npl_rate": 0.0},
            "watch": {"bal": ov["bal"] * 0.031, "cnt": int(ov["cnt"] * 0.03),
                      "cust_cnt": int(ov["cust_cnt"] * 0.03),
                      "npl_rate": round(base * 0.5, 6)},
            "bad": {"bal": ov["npl_bal"], "cnt": int(ov["cnt"] * 0.026),
                    "cust_cnt": int(ov["cust_cnt"] * 0.018), "npl_rate": 1.0},
            "other": {"bal": ov["bal"] * 0.02, "cnt": int(ov["cnt"] * 0.004),
                      "cust_cnt": int(ov["cust_cnt"] * 0.002), "npl_rate": 0.0},
        },
        "dimensions": {k: {"name": v["name"], "stage": v["stage"],
                           "buckets": v["buckets"]}
                       for k, v in signals["dimensions"].items()},
        "overview_dives": [],
        "warnings": [],
    }


def emit(profile_key, outdir):
    sig = build_signals(profile_key)
    w(os.path.join(outdir, "signals.json"), sig)
    w(os.path.join(outdir, "metrics.json"), build_metrics(sig))
    w(os.path.join(outdir, "features.json"), build_features_j(sig))
    w(os.path.join(outdir, "org_risk.json"), build_org_risk(sig))
    w(os.path.join(outdir, "overview.json"), build_overview(sig))
    coh = build_cohort(profile_key, sig)
    if coh is not None:
        w(os.path.join(outdir, "cohort.json"), coh)
    else:
        # 显式写一个空壳，验证下游降级分支
        w(os.path.join(outdir, "cohort.json"),
          {"schema_version": "3.0", "cohorts": [],
           "warnings": ["无客群级校验数据"]})
    return sig


DATASETS = [
    ("dataset_01", "p1"),
    ("dataset_02", "p2"),
    ("dataset_03", "p3"),
    ("dataset_04", "p4"),
]


def main():
    ap = argparse.ArgumentParser(description="合成测试数据生成器")
    ap.add_argument("--out", help="单套输出目录")
    ap.add_argument("--profile", default="p1", choices=sorted(PROFILES))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--outdir", default="synth")
    args = ap.parse_args()

    if args.all:
        for name, prof in DATASETS:
            d = os.path.join(args.outdir, name)
            sig = emit(prof, d)
            print(f"✅ {name} ← {prof} ({PROFILES[prof]['desc'][:28]}…) "
                  f"npl_rate={sig['overall']['npl_rate']:.4f} "
                  f"clue_hot={len(PROFILES[prof]['clue_hot'])} "
                  f"cohort={'有' if PROFILES[prof]['cohort'] is not None else '无'}")
    else:
        if not args.out:
            ap.error("需要 --out 或 --all")
        sig = emit(args.profile, args.out)
        print(f"✅ {args.out} ← {args.profile}")
        print(f"   npl_rate={sig['overall']['npl_rate']:.4f} "
              f"features={len(sig['features'])} "
              f"clue_matrix={len(sig['clue_matrix'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
