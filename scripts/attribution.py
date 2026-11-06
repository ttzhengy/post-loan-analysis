#!/usr/bin/env python3
"""attribution.py — 归因与决策建议（组合线索引擎，删除帕累托）

用法:
    python3 scripts/attribution.py --metrics metrics.json --org-risk org_risk.json \\
        --features features.json --out attribution.json

v2.0 变更：
- 删除帕累托指标（不再输出 pareto 块）
- 新增组合线索引擎：按 references/combination-insights.md 规则，
  从基础风险特征组合中挖掘深层线索本质（获客激进/准入失守/建档造假/贷后空转等）
- 机构/客户经理维度仅保留「Top N 画像」（用于报告风险画像章节），不叫帕累托
"""
import argparse
import json
import os
import sys
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 组合归因规则（与 references/combination-insights.md 一致）
COMBINATIONS = [
    {"rule_id": "C01", "name": "获客激进扩张", "essence": "冲规模批量获客，准入标准被稀释",
     "members": [1, 2, 3], "min_hits": 2,
     "evidence_fields": ["零散客户占比均值", "信用类余额占比均值", "低分段(<600)占比"]},
    {"rule_id": "C02", "name": "准入风控失守", "essence": "反欺诈与审查环节未有效拦截",
     "members": [5, 6, 8], "min_hits": 2,
     "evidence_fields": ["审批通过率", "线索类型数"]},
    {"rule_id": "C03", "name": "建档造假链条", "essence": "建档走过场、尽调形式化",
     "members": [4, 14, 15, 16], "min_hits": 2,
     "evidence_fields": ["异常建档客户占比均值", "同日建档>=5户经理数", "负债率>100%占比"]},
    {"rule_id": "C04", "name": "超额授信杠杆", "essence": "授信额度超客户承受能力",
     "members": [7, 13, 39], "min_hits": 2,
     "evidence_fields": ["超额授信余额占比均值", "大额信用余额占比均值"]},
    {"rule_id": "C05", "name": "贷后管理空转", "essence": "贷后监控缺失、风险信号漏处置",
     "members": [9, 18, 19], "min_hits": 2,
     "evidence_fields": ["未办结率", "平均管户数"]},
    {"rule_id": "C06", "name": "续贷接续断裂", "essence": "到期续贷环节风险滚动",
     "members": [10, 44], "min_hits": 1,
     "evidence_fields": ["无还本续贷不良率均值", "平均逾期天数"]},
    {"rule_id": "C07", "name": "人员道德风险", "essence": "客户经理能力/尽责/道德问题",
     "members": [11, 17], "min_hits": 1,
     "evidence_fields": ["高风险经理数", "触发资金往来线索经理数"]},
    {"rule_id": "C08", "name": "产品行业集中", "essence": "特定产品或行业系统性风险",
     "members": [12, 28], "min_hits": 1,
     "evidence_fields": ["产品不良率均值", "重点行业不良率均值"]},
    {"rule_id": "C09", "name": "客户欺诈包装", "essence": "虚假包装骗取贷款",
     "members": [20, 21, 22, 23, 25, 26, 27], "min_hits": 2,
     "evidence_fields": ["近12月交易金额中位数", "近12月流入金额中位数", "申请>=3次客户数"]},
    {"rule_id": "C10", "name": "客户经营恶化", "essence": "主业造血能力下降",
     "members": [28, 29, 30, 31], "min_hits": 2,
     "evidence_fields": ["重点行业不良率均值", "有农地记录占比"]},
    {"rule_id": "C11", "name": "客户高杠杆", "essence": "多头负债、资金链紧张",
     "members": [32, 33, 34, 35, 36], "min_hits": 2,
     "evidence_fields": []},
    {"rule_id": "C12", "name": "客户异常行为", "essence": "嗜好/家庭/司法异常",
     "members": [37, 38, 40, 41], "min_hits": 1,
     "evidence_fields": ["婚姻状态去重值数"]},
    {"rule_id": "C13", "name": "第一还款来源失效", "essence": "资金挪用、经营主体消亡",
     "members": [42, 43, 45], "min_hits": 1,
     "evidence_fields": ["线索不属实占比均值", "裸贷户占比"]},
]


def main():
    ap = argparse.ArgumentParser(description="归因与决策（组合线索引擎）")
    ap.add_argument("--metrics", required=True, help="core_metrics 输出")
    ap.add_argument("--org-risk", required=True, help="org_risk 输出")
    ap.add_argument("--features", required=True, help="risk_features 输出")
    ap.add_argument("--out", default="attribution.json")
    args = ap.parse_args()

    data = {}
    for key, path in (("metrics", args.metrics), ("org_risk", args.org_risk),
                      ("features", args.features)):
        if not os.path.exists(path):
            print(f"错误：输入文件不存在: {path}", file=sys.stderr)
            return 2
        with open(path, encoding="utf-8") as f:
            data[key] = json.load(f)

    metrics = data["metrics"]
    org_risk = data["org_risk"]
    features = data["features"]
    warnings = list(metrics.get("warnings", [])) + list(org_risk.get("warnings", [])) + list(features.get("warnings", []))

    overall = metrics.get("overall", {})
    total_npl = overall.get("npl_bal", 0) or 0
    total_bal = overall.get("bal", 0) or 0

    # ---------- 1. Top 画像（机构/经理/品种，按不良余额降序；不叫帕累托） ----------
    def top_by(rows, key="npl_bal", maxn=10):
        items = [r for r in rows if r.get(key, 0) > 0]
        items.sort(key=lambda x: -x.get(key, 0))
        out = []
        for i, r in enumerate(items[:maxn], 1):
            out.append({
                "rank": i,
                "group": r.get("group", ""),
                "bal": r.get("bal", 0),
                "npl_bal": r.get("npl_bal", 0),
                "npl_rate": r.get("npl_rate"),
                "cnt": r.get("cnt", 0),
            })
        return out

    top_org = top_by(metrics.get("by_org", []))
    top_mgr = top_by(metrics.get("by_mgr", []))
    top_breed = top_by(metrics.get("by_breed", []), maxn=8)

    # ---------- 2. 组合线索引擎 ----------
    feat_map = {f["feature_id"]: f for f in features.get("features", [])}
    insights = []
    for rule in COMBINATIONS:
        members = []
        for fid in rule["members"]:
            f = feat_map.get(fid)
            if f and f.get("metric") and f.get("status") in ("ok", "approximate"):
                members.append({"feature_id": fid, "name": f["name"], "metric": f["metric"]})
        if not members:
            continue
        hit_ratio = len(members) / len(rule["members"])
        if len(members) < rule["min_hits"]:
            continue
        # 证据字段
        evidence = []
        for ef in rule["evidence_fields"]:
            for m in members:
                if ef in m["metric"]:
                    evidence.append({ef: m["metric"][ef]})
                    break
        # 信号强度近似 = 命中占比
        strength = round(hit_ratio, 4)
        insights.append({
            "rule_id": rule["rule_id"],
            "name": rule["name"],
            "essence": rule["essence"],
            "members": members,
            "hit_count": len(members),
            "member_total": len(rule["members"]),
            "hit_ratio": hit_ratio,
            "strength": strength,
            "evidence": evidence,
            "level": "显著" if strength >= 0.5 else "一般" if strength >= 0.33 else "弱信号",
        })
    insights.sort(key=lambda x: -x["strength"])
    strong = [i for i in insights if i["level"] in ("显著", "一般")]

    # ---------- 2.5 关联相关表线索（clue 46-50）→ 证据链 ----------
    # 用途：根据归因主题在可能相关的表中寻找线索，整合为证据链（C 类表已接入 risk_features）
    clue_map = {f["feature_id"]: f for f in features.get("features", []) if f.get("status") == "clue"}
    # 线索 → 归因主题映射（组合规则与 clue 特征的业务关联）
    clue_theme_map = {
        46: ["C06"],   # 续贷凭证关系 → 续贷接续断裂
        47: ["C06"],   # 上年末接续 → 续贷接续断裂
        48: ["C05"],   # 上门催收 → 贷后管理空转
        49: ["C07"],   # 亲属信息 → 人员道德风险
        50: ["C01", "C10"],  # 联村带户 → 获客激进/经营恶化
        51: ["C04", "C06"],  # 个人贷款合同(A70补充) → 超额授信/续贷
        52: ["C13", "C04"],  # 核销清收证券化(A70补充) → 还款来源失效/超额授信
        53: ["C13", "C05"],  # 还款账单(A70补充) → 还款来源失效/贷后空转
        54: ["C01", "C02"],  # C4机构树 → 获客激进/准入失守（层级切片）
        55: ["C10"],         # 企业变更 → 经营恶化
        56: ["C04"],         # 循环额度 → 超额授信
        57: ["C04", "C13"],  # 押品产权人 → 超额授信/还款来源失效
        58: ["C05", "C06"],  # 凭证分类结果 → 贷后空转/续贷
        59: ["C02"],         # 评分结果历史 → 准入失守
        60: ["C13"],         # 不良金额变动 → 还款来源失效（平滑项）
        61: ["C01", "C10"],  # 家庭村居 → 获客激进/经营恶化
        62: ["C09", "C11"],  # 持有产品 → 欺诈包装/高杠杆（AUM）
        63: ["C04", "C13"],  # 担保关系 → 超额授信/还款来源失效
    }
    for ins in insights:
        rid = ins["rule_id"]
        related_clues = []
        for cid, themes in clue_theme_map.items():
            if rid in themes and cid in clue_map:
                c = clue_map[cid]
                related_clues.append({
                    "feature_id": cid,
                    "name": c["name"],
                    "table": c.get("table", ""),
                    "metric": c.get("metric", {}),
                    "note": c.get("note", ""),
                })
        ins["clues"] = related_clues
        # 业务化称呼：报告面向客户经理，证据链整合不得出现表名/技术标识
        def _biz_clue_name(c):
            return (c.get("name", "")
                    .replace("（证据线索）", "").replace("（A70补充线索）", "")
                    .replace("C4机构树", "机构层级结构"))
        ins["evidence_chain"] = {
            "base_indicators": [m["name"] for m in ins.get("members", [])],
            "related_table_clues": [c["name"] for c in related_clues],
            "summary": (f"由基础指标（{'、'.join(m['name'] for m in ins.get('members', [])[:3])}）"
                        f"组合触发，并在相关业务数据（{'、'.join(_biz_clue_name(c) for c in related_clues) or '无' }）"
                        f"中找到佐证线索。"),
        }

    # ---------- 3. 风险特征排序（主题候选素材） ----------
    feature_rank = []
    for f in features.get("features", []):
        if f["status"] != "ok":
            continue
        metric = f.get("metric", {})
        # 取第一个数值信号作为排序代理
        signal = None
        for v in metric.values():
            if isinstance(v, (int, float)):
                signal = float(v)
                break
        feature_rank.append({
            "feature_id": f["feature_id"], "name": f["name"], "dimension": f["dimension"],
            "stage": f["stage"], "metric": metric, "signal": signal,
            "status": f["status"], "note": f.get("note", ""),
        })
    feature_rank.sort(key=lambda x: -(x["signal"] if x["signal"] is not None else 0))

    # ---------- 4. 决策建议（按组合线索 + Top 画像生成） ----------
    actions = []
    idx = 0
    for ins in strong[:6]:
        idx += 1
        actions.append({
            "action_id": f"A-{idx:03d}",
            "quadrant": "立即整改" if ins["strength"] >= 0.5 else "例行优化",
            "dimension": "组合线索",
            "group": ins["name"],
            "action": f"针对「{ins['name']}」（{ins['essence']}）命中客群开展专项核查与分层处置："
                      f"先验证线索覆盖客群的不良差异，再按成员特征逐项整改",
            "owner": "{{待补：责任岗}}", "deadline": "{{待补：时限}}",
            "kpi": "专项核查覆盖率 / 不良差异验证",
            "baseline": "{{待补}}", "target": "100%",
            "contribution_pct": ins["strength"], "incomplete": True,
        })
    for r in top_org[:3]:
        idx += 1
        actions.append({
            "action_id": f"A-{idx:03d}", "quadrant": "例行优化",
            "dimension": "机构画像", "group": f"不良余额排名第{r['rank']}的机构",
            "action": "对高不良余额机构开展专项排查，压降不良敞口并复盘准入/贷后环节",
            "owner": "{{待补：责任岗}}", "deadline": "{{待补：时限}}",
            "kpi": "不良余额压降率", "baseline": f"当前不良余额 {r['npl_bal']:,.0f}",
            "target": "压降X%", "contribution_pct": None, "incomplete": True,
        })
    for r in top_mgr[:3]:
        idx += 1
        actions.append({
            "action_id": f"A-{idx:03d}", "quadrant": "例行优化",
            "dimension": "客户经理画像", "group": f"不良余额排名第{r['rank']}的客户经理",
            "action": "对高风险管户客户经理名单制管理：暂停新增、逐户排查、双人复核",
            "owner": "{{待补：责任岗}}", "deadline": "{{待补：时限}}",
            "kpi": "高风险经理排查覆盖率",
            "baseline": f"当前不良率 {r['npl_rate']:.2%}" if r["npl_rate"] is not None else "{{待补}}",
            "target": "100%", "contribution_pct": None, "incomplete": True,
        })

    result = {
        "schema_version": "2.0",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall": overall,
        "top": {"org": top_org, "mgr": top_mgr, "breed": top_breed},
        "insights": insights,
        "strong_insights": strong,
        "feature_rank": feature_rank,
        "actions": actions,
        "warnings": warnings,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ 归因与决策完成 → {args.out}")
    print(f"   总不良余额 {total_npl:,.2f} / 总余额 {total_bal:,.2f}")
    print(f"   组合线索 {len(insights)} 条（显著/一般 {len(strong)} 条）")
    for ins in strong[:6]:
        print(f"   {ins['rule_id']} {ins['name']} [{ins['level']}] 命中 {ins['hit_count']}/{ins['member_total']}")
    print(f"   Top 画像：机构 {len(top_org)} / 经理 {len(top_mgr)} / 品种 {len(top_breed)}")
    print(f"   决策动作 {len(actions)} 条")
    for w in warnings:
        print(f"   ⚠️ {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
