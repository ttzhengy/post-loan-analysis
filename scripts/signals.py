#!/usr/bin/env python3
"""signals.py — S2 分维度扫线索：把 S1 的 metrics/org_risk/overview/features 归并为 signals.json

用法:
    # 真实数据
    python3 scripts/signals.py --metrics metrics.json --org-risk org_risk.json \\
        --overview overview.json --features features.json --slice 20260831 \\
        --out signals.json

    # 无真实数据时自测（内置合成数据，覆盖四种情形）
    python3 scripts/signals.py --mock --out signals.json

产出结构见 shared/CONTRACT.md 第 2 节。相对旧流程，本脚本补齐三块此前缺失的数据：
  1. baseline   —— 全辖基线值（feature_id → {metric_label: baseline}），强度分量的必需输入
  2. clue_matrix—— 线索级不良率（来自 S_*_RSK_ORG_C4 长表，不再只取 RSK_LINE_TYP.nunique()）
  3. continuation—— 接续工具 / 接续链（来自 S_00PF_PEAS_CONT_QUAL_C4 与上年末接续情况表）

纯标准库；输入不存在退出码 2，不猜。
"""
import argparse
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCHEMA_VERSION = "3.0"

# ---------------------------------------------------------------------------
# 维度定义：把 overview.json 的 8 大维度收口成引用层需要的稳定 key
# overview 的 dimensions 是 {dim_group: {dim_name: [items]}}，这里做两层展平
# ---------------------------------------------------------------------------
DIM_STAGE = {
    "担保方式": "贷前", "期限档": "贷前", "额度档": "贷前", "还款方式": "贷前",
    "循环标识": "贷前", "主体类型": "贷前", "首贷与否": "贷前", "性别": "贷前",
    "居住年限": "贷前", "贷款用途": "贷前", "投向行业": "贷前",
    "放款年份": "贷前", "账龄(月)": "贷后", "接续标识": "贷后",
    "评分分段": "贷前", "客户经理": "贷后", "机构": "贷后",
}


def _num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def _load_json(path, label, warnings):
    if not path:
        return None
    if not os.path.exists(path):
        warnings.append(f"{label} 文件不存在，已跳过: {path}")
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        warnings.append(f"{label} 读取失败（{e}），已跳过: {path}")
        return None


# ---------------------------------------------------------------------------
# 1. overall
# ---------------------------------------------------------------------------
def build_overall(metrics, overview, warnings):
    overall = {}
    if isinstance(metrics, dict):
        m = metrics.get("overall") or {}
        for k in ("bal", "npl_bal", "npl_rate", "cnt", "cust_cnt", "person_cnt"):
            v = _num(m.get(k))
            if v is not None:
                overall[k] = v
    groups = (overview or {}).get("groups") or {}
    if "bal" not in overall and _num(groups.get("全部", {}).get("bal")) is not None:
        overall["bal"] = _num(groups["全部"]["bal"])
    if "npl_bal" not in overall and _num(groups.get("不良", {}).get("npl_bal")) is not None:
        overall["npl_bal"] = _num(groups["不良"]["npl_bal"])
    if overall.get("npl_rate") is None and overall.get("bal"):
        overall["npl_rate"] = round(overall.get("npl_bal", 0.0) / overall["bal"], 6)
    if not overall:
        warnings.append("overall 缺失：metrics.overall 与 overview.groups 均无可用数值")
    return overall


# ---------------------------------------------------------------------------
# 2. dimensions：展平 overview 的 8 大维度，计算 offset_pp / npl_share
# ---------------------------------------------------------------------------
def build_dimensions(overview, overall, warnings):
    dims_out = {}
    if not isinstance(overview, dict) or not overview.get("dimensions"):
        warnings.append("overview.dimensions 缺失：8 大维度为空，line-level 线索只能依赖 features")
        return dims_out
    base_rate = _num(overall.get("npl_rate")) or 0.0
    total_npl = _num(overall.get("npl_bal")) or 0.0

    for group, dims in overview["dimensions"].items():
        if not isinstance(dims, dict):
            continue
        # 兼容两种结构：
        #   旧/扁平：{group: {dim_name: [bucket, ...]}}
        #   现/对象：{group: {"name": "担保方式", "stage": "贷前", "buckets": [...]}}
        if isinstance(dims.get("buckets"), list):
            dim_items = [(dims.get("name") or group, dims.get("buckets"), dims.get("stage"))]
        else:
            dim_items = [(k, v, None) for k, v in dims.items() if isinstance(v, list)]
        for dim_name, items, dim_stage in dim_items:
            if not isinstance(items, list) or not items:
                continue
            # 维度中文名缺失时退回 group 名，避免把 "buckets" 当维度名显示
            if not dim_name or dim_name in ("buckets", "items", "values"):
                dim_name = group
            # 同一维度名可能出现在不同 group，用 group 前缀消歧
            key = dim_name if dim_name not in dims_out else f"{group}·{dim_name}"
            buckets = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                bal = _num(it.get("bal")) or 0.0
                npl = _num(it.get("npl_bal")) or 0.0
                rate = _num(it.get("npl_rate"))
                if rate is None and bal:
                    rate = npl / bal
                # 注意：overview 每档的 npl_bal 可能已经是"全体不良余额"口径，
                # 优先用 npl_rate，避免把全辖不良摊到每一档
                npl_share = (npl / total_npl) if total_npl and it.get("states") else (
                    _num(it.get("bad_share")) or 0.0)
                buckets.append({
                    "bucket": str(it.get("bucket") or it.get("dim_value") or ""),
                    "bal": round(bal, 2),
                    "npl_bal": round(npl, 2),
                    "npl_rate": round(rate, 6) if rate is not None else None,
                    "npl_share": round(npl_share, 6),
                    "offset_pp": round((rate - base_rate) * 100, 2) if rate is not None else None,
                    "reference_ctl": {
                        "normal_share": _num(it.get("normal_share")),
                        "npl_share": _num(it.get("bad_share")),
                    },
                    "valid": rate is not None and bal > 0,
                })
            if not buckets:
                continue
            dims_out[key] = {
                "name": dim_name,
                "group": group,
                "stage": dim_stage or DIM_STAGE.get(dim_name, "贷前"),
                "buckets": buckets,
            }
    if not dims_out:
        warnings.append("overview.dimensions 存在但无可解析档位")
    return dims_out


# ---------------------------------------------------------------------------
# 3. clue_matrix：线索级不良率（关键修复：不再只取 RSK_LINE_TYP.nunique()）
# ---------------------------------------------------------------------------
# org_risk.json 的 tables.rsk/cce.summary 是**跨机构均值**，只有 rate 类字段可用；
# 真正的计数口径来自 features[5]/features[43] 的 metric。
def _clue_counters(features, warnings):
    """从 features 中捞线索相关的计数（触发合同数 / 不良占比等）"""
    out = {}
    if not isinstance(features, dict):
        return out
    for f in features.get("features", []):
        if f.get("feature_id") in (5, 43) and isinstance(f.get("metric"), dict):
            # features[5] 欺诈敞口 / features[43] 风险信号 —— 只做兜底，不拆到线索类型
            out.setdefault("_fallback", []).append(f.get("metric"))
    return out


def _looks_enriched(clue_matrix):
    """判断 clue_matrix 是否已经带线索级 lift（而非降级的均值壳）。
    降级壳的特征：条目名形如 _ALL_RSK 且所有 npl_lift 为 None。
    """
    if not isinstance(clue_matrix, dict) or not clue_matrix:
        return False
    real = [k for k in clue_matrix if not str(k).startswith("_ALL_")]
    if not real:
        return False
    return any((v or {}).get("npl_lift") is not None for v in clue_matrix.values())


def build_clue_matrix(org_risk, features, overall, warnings):
    """线索级不良率矩阵。

    org_risk.json 只给 summary（mean/p50/max），给不出「哪个线索类型不良率高」，
    因此这里优先读 org_risk 里可选的 rows_by_type（如果 org_risk 升级后提供），
    否则用 summary 里的率类指标 + features 的线索特征构造一个降级的 clue_matrix，
    并在 warnings 里说明口径。
    """
    clue = {}
    base_rate = _num(overall.get("npl_rate"))
    tables = (org_risk or {}).get("tables") or {}
    rate_keys = {
        "rsk": ("PEAS_LN_UHLTH_CTRT_PPTN", "PEAS_LN_CTRT_PPTN"),
        "cce": ("PEAS_LN_UHLTH_CTRT_PPTN", "PEAS_LN_CTRT_PPTN"),
    }
    any_rows = False
    for key, (npl_key, trig_key) in rate_keys.items():
        tbl = tables.get(key) or {}
        rows = tbl.get("rows_by_type")
        if isinstance(rows, list) and rows:
            any_rows = True
            for r in rows:
                ctype = str(r.get("RSK_LINE_TYP") or r.get("clue_type") or "").strip()
                if not ctype:
                    continue
                trig = _num(r.get(trig_key)) or 0.0
                npl_pptn = _num(r.get(npl_key)) or 0.0
                # 线索内不良率代理：触发合同里有多少是不良
                npl_rate = _num(r.get("clue_npl_rate"))
                if npl_rate is None and trig:
                    npl_rate = npl_pptn
                entry = {
                    "trigger_ctrt_cnt": int(_num(r.get("PEAS_LN_CTRT_CNT")) or 0),
                    "trigger_ctrt_pptn": round(trig, 6),
                    "trigger_cust_cnt": int(_num(r.get("PEAS_LN_CUST_CNT")) or 0),
                    "trigger_bal": round(_num(r.get("PEAS_LN_BAL")) or 0.0, 2),
                    "trigger_npl_ctrt_cnt": int(_num(r.get("PEAS_LN_UHLTH_CTRT_CNT")) or 0),
                    "trigger_npl_pptn": round(npl_pptn, 6),
                    "verify_false_pptn": round(_num(r.get("NO_LN_CTRT_PPTN")) or 0.0, 6),
                    "npl_lift": None,
                    "base_rate": None, "basis": "contract",
                    "coverage_bal_pptn": round(_num(r.get("PEAS_LN_BAL_PPTN")) or 0.0, 6),
                    "source_table": key,
                }
                if base_rate:
                    entry["base_rate"] = base_rate
                    entry["npl_lift"] = round(npl_rate / base_rate, 4) if base_rate else None
                clue.setdefault(ctype, entry)
    if not any_rows:
        warnings.append(
            "clue_matrix 降级：org_risk.json 未提供 rows_by_type（按 RSK_LINE_TYP 的明细行），"
            "只能给到跨机构均值；建议 org_risk.py 增加 rows_by_type 输出以恢复线索级不良率"
        )
        # 退而求其次：用 summary 的均值构造一个「全线索合计」条目，保证下游有 baseline 可比
        for key in ("rsk", "cce"):
            s = (tables.get(key) or {}).get("summary") or {}
            if not s:
                continue
            trig_pptn = _num(s.get("PEAS_LN_CTRT_PPTN"))
            npl_pptn = _num(s.get("PEAS_LN_UHLTH_CTRT_PPTN"))
            if trig_pptn is None and npl_pptn is None:
                continue
            clue[f"_ALL_{key.upper()}"] = {
                "trigger_ctrt_cnt": 0, "trigger_ctrt_pptn": trig_pptn,
                "trigger_cust_cnt": 0, "trigger_bal": 0.0,
                "trigger_npl_ctrt_cnt": 0,
                "trigger_npl_pptn": npl_pptn,
                "verify_false_pptn": _num(s.get("NO_LN_CTRT_PPTN")) or 0.0,
                "npl_lift": round(npl_pptn / base_rate, 4) if (npl_pptn is not None and base_rate) else None,
                "base_rate": base_rate, "basis": "contract",
                "coverage_bal_pptn": _num(s.get("PEAS_LN_BAL_PPTN")) or 0.0,
                "source_table": key, "degraded": True,
            }
    return clue


# ---------------------------------------------------------------------------
# 4. features + baseline
# ---------------------------------------------------------------------------
def build_features(features, warnings):
    """归一化 features 并补 baseline。

    旧 features.json 没有 baseline 字段 → 记 baseline_src="missing"，
    下游 attribution 对该特征强度分量记 0 并写 warning。
    """
    out = []
    if not isinstance(features, dict) or not features.get("features"):
        warnings.append("features.json 缺失或为空：无基础特征，规则引擎将只能依赖维度/线索信号")
        return out
    n_missing_baseline = 0
    for f in features.get("features", []):
        if not isinstance(f, dict):
            continue
        fid = f.get("feature_id")
        metric = {k: _num(v) for k, v in (f.get("metric") or {}).items() if _num(v) is not None}
        baseline = {k: _num(v) for k, v in (f.get("baseline") or {}).items() if _num(v) is not None}
        if baseline:
            bsrc = "inline"
        else:
            baseline, bsrc = _infer_baseline(fid, metric)
            if not baseline:
                bsrc = "missing"
                n_missing_baseline += 1
        note = f.get("note") or ""
        if bsrc == "missing" and metric:
            note = (note + "；" if note else "") + "无全辖基线，强度分量记 0"
        item = {
            "feature_id": fid, "name": f.get("name", ""),
            "dimension": f.get("dimension", ""), "stage": f.get("stage", ""),
            "status": f.get("status", "ok"),
            "metric": metric, "baseline": baseline, "baseline_src": bsrc,
            "numerator": _num(f.get("numerator")), "denominator": _num(f.get("denominator")),
            "table": f.get("table", ""), "note": note,
        }
        out.append(item)
    if n_missing_baseline:
        warnings.append(f"{n_missing_baseline} 个特征无全辖基线（baseline），其强度分量将记 0")
    return out


# 全辖基线推断表：不是编数据，而是把「该特征的 metric 天然对应的全辖口径」登记下来。
# 结构：feature_id -> [(metric_label, 全辖字典路径, 换算说明)]
# 全辖字典由 signals 自己算（全辖不良率、全辖信用余额占比=1 等），取不到就留空。
BASELINE_RULES = {
    # 率类特征：全辖基线就是全辖不良率（同一口径下"该特征命中率"不可能低于不良率，
    # 因此用"若干特征共享同一全辖分母"的做法：基线取全辖不良率，作为景气基准）
    1: [("零散不良率均值", "npl_rate")],
    2: [("信用类不良率均值", "npl_rate")],
    4: [("异常建档不良率均值", "npl_rate")],
    43: [("线索内不良率", "npl_rate")],
}


def _infer_baseline(fid, metric):
    """按特征语义推断全辖基线。返回 ({label: value}, src)。

    只对「本身就是率、且全辖口径必然同构」的指标做推断，其余一律 missing，
    宁缺勿错——extrapolate 一个假 baseline 会让强度分量失真。
    """
    rules = BASELINE_RULES.get(fid)
    if not rules:
        return {}, "missing"
    return {}, "deferred"  # 由 enrich_baseline() 用 overall 填


def enrich_baseline(feature_list, overall):
    """用 overall + 维度数据回填 baseline（两遍：先收基线，再逐特征匹配）"""
    npl_rate = _num(overall.get("npl_rate"))
    for f in feature_list:
        if f.get("baseline"):
            continue
        rules = BASELINE_RULES.get(f.get("feature_id"))
        if not rules or npl_rate is None:
            continue
        filled = {}
        for label, ref in rules:
            if ref == "npl_rate" and label in (f.get("metric") or {}):
                filled[label] = npl_rate
        if filled:
            f["baseline"] = filled
            f["baseline_src"] = "overall_npl_rate"


# ---------------------------------------------------------------------------
# 5. continuation：接续工具 + 接续链
# ---------------------------------------------------------------------------
# S_00PF_PEAS_CONT_QUAL_C4 的 5 类接续工具 → 统一 key
CONT_TOOLS = {
    "no_principal_renew": {"bal": "CTNU_LN_BAL", "npl_bal": "CTNU_LN_BAD_BAL", "rate": "CTNU_LN_BAD_RATE"},
    "one_click_renew": {"bal": "ONE_CTNU_LN_BAL", "npl_bal": "ONE_CTNU_LN_BAD_BAL", "rate": "ONE_CTNU_LN_BAD_RATE"},
    "extension": {"bal": "RNEW_LN_BAL", "npl_bal": "RNEW_LN_BAD_BAL", "rate": "RNEW_LN_BAD_RATE"},
    "non_npl_restructure": {"bal": "NOT_BAD_AGN_LN_BAL", "npl_bal": "NOT_BAD_AGN_LN_BAD_BAL", "rate": "NOT_BAD_AGN_LN_BAD_RATE"},
    "npl_restructure": {"bal": "BAD_AGN_LN_BAL", "npl_bal": "BAD_AGN_LN_BAD_BAL", "rate": "BAD_AGN_LN_BAD_RATE"},
}


def build_continuation(org_risk, features, overall, warnings):
    """接续工具不良率 + 接续链形态。

    org_risk.json 的 tables.cont.summary 是跨机构均值，能读到 CTNU_LN_BAD_RATE 等；
    但 5 类工具的余额/不良余额在 summary 里不齐（KEY_COLS 只取了 CTNU_LN_BAL / ONE_CTNU_LN_BAL）。
    因此这里：能用 summary 的率就用，余额缺失的记为 None 并由 attribution 降级。
    """
    out = {"tools": {}, "chain": {"rolling": {"cnt": 0, "npl_rate": None},
                                  "resolving": {"cnt": 0, "npl_rate": None}},
           "degraded": []}
    s = ((org_risk or {}).get("tables", {}).get("cont") or {}).get("summary") or {}
    detail = ((org_risk or {}).get("tables", {}).get("cont") or {}).get("rows_all")
    if isinstance(detail, list) and detail:
        # 有明细行：按列求和算余额加权不良率
        for key, cols in CONT_TOOLS.items():
            bal = sum(_num(r.get(cols["bal"])) or 0.0 for r in detail if isinstance(r, dict))
            npl = sum(_num(r.get(cols["npl_bal"])) or 0.0 for r in detail if isinstance(r, dict))
            if bal <= 0:
                continue
            out["tools"][key] = {"bal": round(bal, 2), "npl_bal": round(npl, 2),
                                 "npl_rate": round(npl / bal, 6)}
    else:
        out["degraded"].append(
            "continuation.tools 降级：org_risk.json 未提供 cont.rows_all 明细，"
            "5 类接续工具的余额/不良余额不全，只能用跨机构均值的率口径"
        )
        for key, cols in CONT_TOOLS.items():
            rate = _num(s.get(cols["rate"]))
            bal = _num(s.get(cols["bal"]))
            if rate is None and bal is None:
                continue
            item = {"bal": round(bal, 2) if bal is not None else None,
                    "npl_bal": None,
                    "npl_rate": round(rate, 6) if rate is not None else None,
                    "source": "org_risk.summary.mean"}
            out["tools"][key] = item
    sum_rate = _num(s.get("BAD_RATE_SUM"))
    if not out["tools"] and sum_rate is None:
        warnings.append("continuation 缺失：S_00PF_PEAS_CONT_QUAL_C4 无数据")

    # 接续链：来自 features[47]（上年末凭证本年接续，CONTINUE_FLAG 分布）
    cont_feat = None
    if isinstance(features, dict):
        for f in features.get("features", []):
            if f.get("feature_id") == 47:
                cont_feat = f
                break
    chain = out["chain"]
    if cont_feat and isinstance(cont_feat.get("metric"), dict):
        m = cont_feat["metric"]
        rolling = _num(m.get("滚动接续记录数")) or _num(m.get("接续记录数")) or 0
        resolving = _num(m.get("化解接续记录数")) or 0
        chain["rolling"] = {"cnt": int(rolling),
                            "npl_rate": _num(m.get("滚动接续不良率"))}
        chain["resolving"] = {"cnt": int(resolving),
                              "npl_rate": _num(m.get("化解接续不良率"))}
        if "滚动接续记录数" not in m:
            out["degraded"].append(
                "continuation.chain 降级：features[47] 只有 CONTINUE_FLAG 去重值数，"
                "缺「滚动/化解」分组计数，需在 risk_features.py 按 CONTINUE_FLAG 分组补算"
            )
    else:
        out["degraded"].append("continuation.chain 缺失：features[47] 不可用")
    for d in out["degraded"]:
        warnings.append(d)
    return out


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 5.5 cohort_validation：把 cohort.json（客群级实测）按规则折算成当期校验
# ---------------------------------------------------------------------------
def build_cohort_validation(cohort, rules_doc, warnings):
    """把 cohort.json 的「单特征客群实测」折算成「规则级客群校验」。

    为什么需要这一步：
      rules.json 里的 cohort_lift 是历史切片挖出来的先验，不能当当期证据。
      当期证据必须来自同切片的客群实测 —— cohort.json 给的是**单特征**客群的
      不良率/lift，而规则是**多特征组合**。这里做保守折算：

        rule_lift = Π(feature_lift) ** (1/n)      几何平均，抑制单特征暴击
        rule_npl  = 全辖不良率 × rule_lift        与 lift 保持口径一致
        rule_size = min(成员客群规模)              交集不可能大于最小组成集

      这是**下界估计**：真实交集客群的 lift 通常高于几何平均（正相关叠加），
      所以折算值偏保守 —— 宁可低估，不虚报「已通过校验」。

    无 cohort.json 或无任何成员有实测 → 返回 {}，下游自动降级（最高「一般」）。
    """
    out = {}
    if not isinstance(cohort, dict):
        return out
    items = cohort.get("cohorts") or []
    if not items:
        return out
    by_fid = {}
    for it in items:
        fid = it.get("feature_id")
        lift = _num(it.get("lift"))
        if fid is None or lift is None or lift <= 0:
            continue
        by_fid[int(fid)] = {
            "lift": lift,
            "size": _num(it.get("size")),
            "npl_rate": _num(it.get("npl_rate")),
            "check": it.get("check"),
        }
    if not by_fid:
        return out

    base_rate = _num(((cohort or {}).get("overall") or {}).get("npl_rate"))
    if base_rate is None:
        # cohort.json 未带 overall，用 cohort 内 lift×npl_rate 反推不靠谱；
        # 交给调用方补 base_rate
        base_rate = None

    rules = []
    if isinstance(rules_doc, dict):
        for sec in ("manual", "mined", "derived"):
            rules.extend(rules_doc.get(sec) or [])
        for k, v in rules_doc.items():
            if k not in ("manual", "mined", "derived", "thresholds") \
                    and isinstance(v, list) and v and isinstance(v[0], dict):
                rules.extend(v)
    elif isinstance(rules_doc, list):
        rules = rules_doc

    for r in rules:
        rid = r.get("rule_id")
        members = list((r.get("expr") or {}).get("all_of") or [])
        members += list((r.get("expr") or {}).get("any_of") or [])
        members = [int(m) for m in members if isinstance(m, (int, float))]
        hits = [by_fid[m] for m in members if m in by_fid]
        if not hits:
            continue
        # 至少一半成员有实测才做折算，否则样本不代表性
        if len(hits) * 2 < len(members) and len(hits) < 2:
            continue
        geo = 1.0
        for h in hits:
            geo *= max(1e-6, h["lift"])
        rule_lift = geo ** (1.0 / len(hits))
        sizes = [h["size"] for h in hits if h["size"]]
        out[rid] = {
            "lift": round(rule_lift, 4),
            "size": int(min(sizes)) if sizes else None,
            "npl_rate": (round(base_rate * rule_lift, 6) if base_rate else None),
            "basis": "cohort_geomean",
            "member_lifts": {str(m): round(by_fid[m]["lift"], 4)
                             for m in members if m in by_fid},
            "measured_features": len(hits),
            "total_features": len(members),
            "check": next((h["check"] for h in hits if h.get("check")), None),
        }
    if out:
        warnings.append(
            f"cohort_validation：{len(out)} 条规则由 cohort.json 折算（几何平均，下界估计）；"
            "真实交集客群 lift 通常更高"
        )
    return out


# 6. 组装
# ---------------------------------------------------------------------------
def build_signals(metrics=None, org_risk=None, overview=None, features=None,
                  slice_dt="", extra_warnings=None, upstream=None,
                  cohort=None, rules_doc=None):
    warnings = list(extra_warnings or [])
    for src, name in ((metrics, "metrics"), (org_risk, "org_risk"),
                      (overview, "overview"), (features, "features")):
        if isinstance(src, dict):
            warnings.extend(src.get("warnings") or [])

    overall = build_overall(metrics, overview, warnings)
    dimensions = build_dimensions(overview, overall, warnings)
    clue_matrix = build_clue_matrix(org_risk, features, overall, warnings)
    feat_list = build_features(features, warnings)
    enrich_baseline(feat_list, overall)
    continuation = build_continuation(org_risk, features, overall, warnings)

    # ---- 上游 signals 直通：clue_matrix / continuation 已算好的直接继承 ----
    # 场景：S1 阶段已由真数据生成过完整 signals.json（含 clue_matrix），
    # S2 重跑时若 org_risk 仍无 rows_by_type，不应把已有结果降级掉。
    if isinstance(upstream, dict):
        ups_clue = upstream.get("clue_matrix") or {}
        ups_cont = upstream.get("continuation") or {}
        upgraded = False
        if ups_clue and _looks_enriched(ups_clue):
            if not _looks_enriched(clue_matrix):
                clue_matrix = ups_clue
                upgraded = True
                warnings.append(
                    "clue_matrix 继承自上游 signals.json（含线索级 lift），"
                    "当前 org_risk 未提供 rows_by_type，未重新计算"
                )
        if ups_cont.get("tools") and (ups_cont.get("chain") or {}).get("rolling", {}).get("cnt"):
            if not any((continuation.get("tools") or {}).get(k, {}).get("npl_rate")
                       for k in continuation.get("tools") or {}):
                continuation = ups_cont
                upgraded = True
                warnings.append("continuation 继承自上游 signals.json，未重新计算")
        # 8 维度同理：上游若已带 buckets 且有恶化偏移，直接继承
        ups_dims = upstream.get("dimensions") or {}
        if ups_dims and not dimensions:
            dimensions = ups_dims
            upgraded = True
            warnings.append("dimensions 继承自上游 signals.json，未重新计算")

    if not slice_dt:
        for src in (overview, metrics, features, org_risk):
            if isinstance(src, dict) and src.get("slice"):
                slice_dt = str(src["slice"])
                break

    cohort_validation = build_cohort_validation(cohort, rules_doc, warnings)
    if cohort_validation and not overall.get("npl_rate"):
        # 回填 base_rate，让 npl_rate 折算口径可用
        for v in cohort_validation.values():
            if v.get("npl_rate") is None:
                v["npl_rate"] = None

    return {
        "schema_version": SCHEMA_VERSION,
        "slice": slice_dt,
        "cohort_validation": cohort_validation,
        "overall": overall,
        "dimensions": dimensions,
        "clue_matrix": clue_matrix,
        "features": feat_list,
        "continuation": continuation,
        "baseline": {str(f["feature_id"]): f["baseline"] for f in feat_list if f.get("baseline")},
        "coverage": {
            "dimensions": len(dimensions),
            "clue_types": len(clue_matrix),
            "features": len(feat_list),
            "features_with_baseline": sum(1 for f in feat_list if f.get("baseline")),
            "continuation_tools": len(continuation.get("tools") or {}),
        },
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# 7. --mock：内置合成数据（覆盖 ① 宽广度弱信号 ② 窄广度高强度 ③ 强 cohort ④ 无线索校验）
# ---------------------------------------------------------------------------
def mock_inputs():
    """构造四种情形，供 selftest 与 --mock 使用。

    情形① 宽广度弱信号：C01(1,2,3) 与 C03(4,14,15,16) 全命中，但每个 metric 只比基线高 5%~10%
    情形② 窄广度高强度：C11(32,33,34,35,36) 只有 32/34 命中，但偏离达 4~5 倍
    情形③ 强 cohort：规则 M01 有 cohort_lift=13.72 / n=65
    情形④ 无线索校验：D01/D03 等 derived 规则没有 cohort 字段
    """
    npl = 0.0526
    overview = {
        "schema_version": "3.0-overview", "slice": "20260831",
        "groups": {"全部": {"bal": 5_200_000_000, "npl_bal": 273_520_000},
                   "正常": {"bal": 4_600_000_000},
                   "关注": {"bal": 326_480_000},
                   "不良": {"bal": 273_520_000}},
        "dimensions": {
            "产品与担保": {
                "担保方式": [
                    {"dim_value": "信用", "bal": 1_820_000_000, "npl_bal": 163_800_000,
                     "npl_rate": 0.09, "normal_share": 0.31, "bad_share": 0.60},
                    {"dim_value": "抵押", "bal": 2_600_000_000, "npl_bal": 52_000_000,
                     "npl_rate": 0.02, "normal_share": 0.52, "bad_share": 0.19},
                    {"dim_value": "保证", "bal": 780_000_000, "npl_bal": 57_720_000,
                     "npl_rate": 0.074, "normal_share": 0.17, "bad_share": 0.21},
                ],
                "额度档": [
                    {"dim_value": "5万以下", "bal": 1_680_000_000, "npl_bal": 168_000_000,
                     "npl_rate": 0.10, "normal_share": 0.29, "bad_share": 0.61},
                    {"dim_value": "5-10万", "bal": 1_560_000_000, "npl_bal": 62_400_000,
                     "npl_rate": 0.04, "normal_share": 0.31, "bad_share": 0.23},
                    {"dim_value": "10-30万", "bal": 1_300_000_000, "npl_bal": 31_200_000,
                     "npl_rate": 0.024, "normal_share": 0.27, "bad_share": 0.11},
                ],
                "循环标识": [
                    {"dim_value": "循环", "bal": 900_000_000, "npl_bal": 63_000_000,
                     "npl_rate": 0.07, "normal_share": 0.17, "bad_share": 0.23},
                    {"dim_value": "非循环", "bal": 4_300_000_000, "npl_bal": 210_520_000,
                     "npl_rate": 0.049, "normal_share": 0.83, "bad_share": 0.77},
                ],
            },
            "客群与主体": {
                "主体类型": [
                    {"dim_value": "脱贫户", "bal": 620_000_000, "npl_bal": 74_400_000,
                     "npl_rate": 0.12, "normal_share": 0.10, "bad_share": 0.27},
                    {"dim_value": "一般农户", "bal": 4_580_000_000, "npl_bal": 199_120_000,
                     "npl_rate": 0.0435, "normal_share": 0.90, "bad_share": 0.73},
                ],
            },
            "时间与账龄": {
                "放款年份": [
                    {"dim_value": "2022", "bal": 420_000_000, "npl_bal": 58_800_000,
                     "npl_rate": 0.14, "normal_share": 0.07, "bad_share": 0.21},
                    {"dim_value": "2023", "bal": 680_000_000, "npl_bal": 68_000_000,
                     "npl_rate": 0.10, "normal_share": 0.12, "bad_share": 0.25},
                    {"dim_value": "2024", "bal": 1_500_000_000, "npl_bal": 78_000_000,
                     "npl_rate": 0.052, "normal_share": 0.29, "bad_share": 0.29},
                    {"dim_value": "2025", "bal": 2_600_000_000, "npl_bal": 68_720_000,
                     "npl_rate": 0.0264, "normal_share": 0.52, "bad_share": 0.25},
                ],
            },
        },
    }
    metrics = {
        "schema_version": "2.0", "slice": "20260831",
        "overall": {"bal": 5_200_000_000, "npl_bal": 273_520_000, "npl_rate": npl,
                    "cnt": 268_000, "cust_cnt": 201_000, "person_cnt": 198_500},
        "warnings": [],
    }
    org_risk = {
        "schema_version": "1.0", "slice": "20260831",
        "tables": {
            "rsk": {"rows": 12, "summary": {"PEAS_LN_CTRT_PPTN": 0.061, "PEAS_LN_UHLTH_CTRT_PPTN": 0.073,
                                            "NO_LN_CTRT_PPTN": 0.42},
                    "rows_by_type": [
                        {"RSK_LINE_TYP": "反欺诈", "PEAS_LN_CTRT_CNT": 9_800, "PEAS_LN_CTRT_PPTN": 0.0366,
                         "PEAS_LN_CUST_CNT": 8_100, "PEAS_LN_BAL": 210_000_000,
                         "PEAS_LN_UHLTH_CTRT_CNT": 2_156, "PEAS_LN_UHLTH_CTRT_PPTN": 0.0256,
                         "NO_LN_CTRT_PPTN": 0.61, "clue_npl_rate": 0.22,
                         "PEAS_LN_BAL_PPTN": 0.0404},
                        {"RSK_LINE_TYP": "多头借贷", "PEAS_LN_CTRT_CNT": 14_200, "PEAS_LN_CTRT_PPTN": 0.053,
                         "PEAS_LN_CUST_CNT": 11_900, "PEAS_LN_BAL": 380_000_000,
                         "PEAS_LN_UHLTH_CTRT_CNT": 1_988, "PEAS_LN_UHLTH_CTRT_PPTN": 0.0236,
                         "NO_LN_CTRT_PPTN": 0.28, "clue_npl_rate": 0.14,
                         "PEAS_LN_BAL_PPTN": 0.0731},
                        {"RSK_LINE_TYP": "户贷企用", "PEAS_LN_CTRT_CNT": 2_400, "PEAS_LN_CTRT_PPTN": 0.009,
                         "PEAS_LN_CUST_CNT": 1_950, "PEAS_LN_BAL": 120_000_000,
                         "PEAS_LN_UHLTH_CTRT_CNT": 612, "PEAS_LN_UHLTH_CTRT_PPTN": 0.0073,
                         "NO_LN_CTRT_PPTN": 0.18, "clue_npl_rate": 0.255,
                         "PEAS_LN_BAL_PPTN": 0.0231},
                    ]},
            "cce": {"rows": 6, "summary": {"PEAS_LN_CTRT_PPTN": 0.031, "PEAS_LN_UHLTH_CTRT_PPTN": 0.041},
                    "rows_by_type": [
                        {"RSK_LINE_TYP": "关注类线索", "PEAS_LN_CTRT_CNT": 3_100, "PEAS_LN_CTRT_PPTN": 0.0116,
                         "PEAS_LN_CUST_CNT": 2_700, "PEAS_LN_BAL": 150_000_000,
                         "PEAS_LN_UHLTH_CTRT_CNT": 620, "PEAS_LN_UHLTH_CTRT_PPTN": 0.0074,
                         "NO_LN_CTRT_PPTN": 0.55, "clue_npl_rate": 0.20,
                         "PEAS_LN_BAL_PPTN": 0.0288},
                    ]},
            "cont": {"rows": 18, "summary": {"CTNU_LN_BAL": 420_000_000, "CTNU_LN_BAD_RATE": 0.031,
                                             "ONE_CTNU_LN_BAL": 260_000_000, "ONE_CTNU_LN_BAD_RATE": 0.019,
                                             "RNEW_LN_BAD_RATE": 0.042,
                                             "NOT_BAD_AGN_LN_BAD_RATE": 0.086,
                                             "BAD_AGN_LN_BAD_RATE": 0.412,
                                             "BAD_RATE_SUM": 0.058},
                    "rows_all": [
                        {"CTNU_LN_BAL": 420_000_000, "CTNU_LN_BAD_BAL": 13_020_000,
                         "ONE_CTNU_LN_BAL": 260_000_000, "ONE_CTNU_LN_BAD_BAL": 4_940_000,
                         "RNEW_LN_BAL": 180_000_000, "RNEW_LN_BAD_BAL": 7_560_000,
                         "NOT_BAD_AGN_LN_BAL": 96_000_000, "NOT_BAD_AGN_LN_BAD_BAL": 8_256_000,
                         "BAD_AGN_LN_BAL": 44_000_000, "BAD_AGN_LN_BAD_BAL": 18_128_000},
                        {"CTNU_LN_BAL": 130_000_000, "CTNU_LN_BAD_BAL": 5_200_000,
                         "ONE_CTNU_LN_BAL": 88_000_000, "ONE_CTNU_LN_BAD_BAL": 1_760_000,
                         "RNEW_LN_BAL": 62_000_000, "RNEW_LN_BAD_BAL": 3_100_000,
                         "NOT_BAD_AGN_LN_BAL": 31_000_000, "NOT_BAD_AGN_LN_BAD_BAL": 3_410_000,
                         "BAD_AGN_LN_BAL": 15_000_000, "BAD_AGN_LN_BAD_BAL": 6_600_000},
                    ]},
        },
        "warnings": [],
    }

    def feat(fid, name, dim, stage, metric, baseline, status="ok", table="", note=""):
        return {"feature_id": fid, "name": name, "dimension": dim, "stage": stage,
                "status": status, "metric": metric, "baseline": baseline,
                "table": table, "note": note}

    features = {"schema_version": "2.0", "slice": "20260831", "features": [
        # —— 情形① 宽广度弱信号：C01 / C03 全命中但只轻微偏离基线
        feat(1, "零散获客风险", "机构", "营销获客",
             {"零散客户占比均值": 0.482, "零散余额占比均值": 0.451, "零散不良率均值": 0.0555},
             {"零散客户占比均值": 0.46, "零散余额占比均值": 0.43, "零散不良率均值": 0.0526}),
        feat(2, "无抵押缓释风险", "机构", "营销获客",
             {"信用类余额占比均值": 0.3605, "信用类不良率均值": 0.0895},
             {"信用类余额占比均值": 0.35, "信用类不良率均值": 0.082}),
        feat(3, "低评分准入风险", "机构", "贷前准入",
             {"低分段(<600)占比": 0.1288, "评分通过率": 0.945},
             {"低分段(<600)占比": 0.122, "评分通过率": 0.94}),
        feat(4, "建档不规范风险", "机构", "贷前准入",
             {"异常建档客户占比均值": 0.152, "异常建档不良率均值": 0.0722},
             {"异常建档客户占比均值": 0.145, "异常建档不良率均值": 0.068}),
        feat(14, "批量建档", "客户经理", "贷前准入",
             {"同日建档>=5户经理数": 34, "经理总数": 420},
             {"同日建档>=5户经理数": 32, "经理总数": 420}),
        feat(15, "调查造假", "客户经理", "贷前准入",
             {"地址异常合同占比均值": 0.0385},
             {"地址异常合同占比均值": 0.036}, status="approximate",
             table="S_00PF_PEAS_ADDR_RSK_ORG_SUM_C4"),
        feat(16, "信息录入失真", "客户经理", "贷前准入",
             {"FAS资产与农行金融资产偏差": 0.5215},
             {"FAS资产与农行金融资产偏差": 0.50}),
        # —— 情形② 窄广度高强度：C11 只有 32/34 命中，但偏离 4~5 倍
        feat(32, "多头借贷", "客户", "贷前准入",
             {"账户数>=5占比": 0.412, "未结清机构>=3占比": 0.366},
             {"账户数>=5占比": 0.088, "未结清机构>=3占比": 0.072}),
        feat(33, "多头借贷且负债与规模不匹配", "客户", "贷前准入",
             {"账户>5且负债>50万占比": 0.082},
             {"账户>5且负债>50万占比": 0.079}),
        feat(34, "征信查询次数过多", "客户", "贷前准入",
             {"近1月查询>=5占比": 0.648, "近6月查询>=10占比": 0.702},
             {"近1月查询>=5占比": 0.135, "近6月查询>=10占比": 0.148}),
        feat(35, "有被拒贷记录", "客户", "贷前准入",
             {"无信用但有查询占比": 0.0612},
             {"无信用但有查询占比": 0.058}),
        feat(36, "N年内不良记录", "客户", "贷前准入",
             {"近2年累计逾期>0占比": 0.054},
             {"近2年累计逾期>0占比": 0.050}),
        # —— 其余成员（部分缺失 → 用于验证 data_missing 不参与计算）
        feat(5, "欺诈风险敞口", "机构", "贷前准入", {}, {}, status="data_missing"),
        feat(6, "信用与负债风险敞口", "机构", "贷前准入", {}, {}, status="data_missing"),
        feat(8, "审查质量风险", "机构", "贷中审查",
             {"白名单审批通过率": 0.962}, {"白名单审批通过率": 0.951}, status="approximate"),
        feat(9, "贷后管理不到位", "机构", "贷后管理", {}, {}, status="data_missing"),
        feat(17, "与客户资金往来", "客户经理", "贷前准入",
             {"触发资金往来线索经理数": 27, "经理总数": 420},
             {"触发资金往来线索经理数": 9, "经理总数": 420}),
        feat(44, "还款行为恶化", "客户", "贷后管理",
             {"逾期未结清账单占比": 0.091}, {"逾期未结清账单占比": 0.070}),
        feat(47, "上年末凭证本年接续（证据线索）", "机构", "到期续贷",
             {"接续记录数": 8200, "滚动接续记录数": 6410, "滚动接续不良率": 0.062,
              "化解接续记录数": 1790, "化解接续不良率": 0.021},
             {}, status="clue", table="G_00PF_PEAS_LN_LSTY_VCH_CONT_SITU_INFO"),
    ], "warnings": []}
    return metrics, org_risk, overview, features


def write_json(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="S2 分维度扫线索：把 metrics/org_risk/overview/features 归并为 signals.json"
                    "（补齐 baseline / clue_matrix / continuation）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n"
               "  python3 scripts/signals.py --metrics metrics.json --org-risk org_risk.json \\\n"
               "      --overview overview.json --features features.json --out signals.json\n"
               "  python3 scripts/signals.py --mock --out signals.json")
    ap.add_argument("--metrics", help="core_metrics 输出 metrics.json")
    ap.add_argument("--org-risk", dest="org_risk", help="org_risk.py 输出 org_risk.json")
    ap.add_argument("--overview", help="core_overview 输出 overview.json")
    ap.add_argument("--features", help="risk_features.py 输出 features.json")
    ap.add_argument("--slice", default="", help="切片日期（缺省从输入文件读）")
    ap.add_argument("--signals-in", dest="signals_in", default="",
                    help="上游 signals.json（可选）：clue_matrix/continuation/dimensions "
                         "已算好且当前输入缺明细时直接继承，避免降级")
    ap.add_argument("--cohort", default="", help="cohort.json（客群级实测，用于生成 cohort_validation）")
    ap.add_argument("--rules", default="", help="rules.json（折算 cohort_validation 时按规则成员取交集口径）")
    ap.add_argument("--out", default="signals.json")
    ap.add_argument("--mock", action="store_true",
                    help="用内置合成数据跑通（覆盖宽广度弱信号/窄广度高强度/强 cohort/无线索校验四种情形）")
    ap.add_argument("--strict", action="store_true", help="任一输入缺失即以退出码 2 退出（默认降级继续）")
    args = ap.parse_args(argv)

    if args.mock:
        metrics, org_risk, overview, features = mock_inputs()
        warnings = ["--mock 模式：使用内置合成数据，不可用于真实结论"]
        sig = build_signals(metrics, org_risk, overview, features,
                            slice_dt=args.slice or "20260831", extra_warnings=warnings)
        write_json(sig, args.out)
        print(f"✅ signals（mock）→ {args.out}")
        _summary(sig)
        return 0

    provided = [args.metrics, args.org_risk, args.overview, args.features]
    if not any(provided):
        ap.print_help()
        print("\n错误：未提供任何输入文件（或用 --mock 跑通）", file=sys.stderr)
        return 2

    missing = [p for p in provided if p and not os.path.exists(p)]
    if missing:
        for p in missing:
            print(f"错误：输入文件不存在: {p}", file=sys.stderr)
        if args.strict:
            return 2

    warnings = []
    metrics = _load_json(args.metrics, "metrics", warnings)
    org_risk = _load_json(args.org_risk, "org_risk", warnings)
    overview = _load_json(args.overview, "overview", warnings)
    features = _load_json(args.features, "features", warnings)
    if not any(x is not None for x in (metrics, org_risk, overview, features)):
        print("错误：所有输入文件均不可读，无可归并的信号", file=sys.stderr)
        return 2

    upstream = _load_json(args.signals_in, "signals_in", warnings) if args.signals_in else None
    cohort = _load_json(args.cohort, "cohort", warnings) if args.cohort else None
    rules_doc = _load_json(args.rules, "rules", warnings) if args.rules else None
    # cohort.json 里的 overall 可能缺 npl_rate，从 metrics/overview 补
    if isinstance(cohort, dict) and cohort and not (cohort.get("overall") or {}).get("npl_rate"):
        _m = metrics or {}
        _ov = overview or {}
        _rate = (_m.get("overall") or {}).get("npl_rate") or (_ov.get("overall") or {}).get("npl_rate")
        if _rate is not None:
            cohort = dict(cohort)
            cohort["overall"] = dict(cohort.get("overall") or {}, npl_rate=_rate)
    sig = build_signals(metrics, org_risk, overview, features,
                        slice_dt=args.slice, extra_warnings=warnings,
                        upstream=upstream, cohort=cohort, rules_doc=rules_doc)
    # 继承来的字段在 schema 里留痕，便于下游判断是否用了降级/继承口径
    if isinstance(upstream, dict):
        inherited = []
        for k in ("clue_matrix", "continuation", "dimensions"):
            if sig.get(k) == upstream.get(k) and upstream.get(k):
                inherited.append(k)
        sig.setdefault("provenance", {})["inherited_from_upstream"] = inherited
    write_json(sig, args.out)
    print(f"✅ signals 归并完成 → {args.out}")
    _summary(sig)
    return 0


def _summary(sig):
    c = sig.get("coverage", {})
    ov = sig.get("overall") or {}
    print(f"   切片 {sig.get('slice')}｜余额 {ov.get('bal'):,.0f}｜不良率 "
          f"{(ov.get('npl_rate') or 0):.2%}" if ov.get("bal") else "   全辖指标缺失")
    print(f"   维度 {c.get('dimensions')} / 线索类型 {c.get('clue_types')} / 特征 {c.get('features')}"
          f"（其中有基线 {c.get('features_with_baseline')}）/ 接续工具 {c.get('continuation_tools')}")
    for w in sig.get("warnings", [])[:10]:
        print(f"   ⚠️ {w}")
    if len(sig.get("warnings", [])) > 10:
        print(f"   ⚠️ …… 另有 {len(sig['warnings']) - 10} 条 warning，见 outputs.warnings")


if __name__ == "__main__":
    sys.exit(main())
