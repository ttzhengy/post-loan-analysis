#!/usr/bin/env python3
"""render_report.py — 渲染贷后归因报告 v5（对齐《报告html标签说明.doc》）

用法:
    python3 scripts/render_report.py --attribution attribution.json \\
        --metrics metrics.json --org-risk org_risk.json --features features.json \\
        --out-dir ./output

v5.0 变更：
- HTML 使用 data-topic-id（T001…）标记每个分析主题容器
- 所有统计数据/比较判断用 <span data-calc-id="D001…"> 标记，全文唯一
- 生成《数据验算清单.xlsx》：数据编号 | 网页展示结果 | 数据来源 | 计算代码或SQL
- 报告结构对齐《报告模板.doc》：基本信息→主题概览→归因与分析→风险警示
"""
import argparse
import html
import json
import os
import sys
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def esc(s):
    if s is None:
        return ""
    return html.escape(str(s))


def pct(x, digits=2):
    try:
        return f"{float(x) * 100:.{digits}f}%"
    except (TypeError, ValueError):
        return "—"


def num(x, digits=2):
    try:
        return f"{float(x):,.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def wan(x, digits=2):
    try:
        return f"{float(x) / 10000:,.{digits}f} 万"
    except (TypeError, ValueError):
        return "—"


# ============ 数据注册表：分配 data-calc-id 并记录验算来源 ============
class CalcRegistry:
    def __init__(self):
        self.items = []   # (calc_id, label, display_value, source, sql)

    def add(self, label, display_value, source, sql):
        calc_id = f"D{len(self.items) + 1:03d}"
        self.items.append({
            "calc_id": calc_id,
            "label": label,
            "display": display_value,
            "source": source,
            "sql": sql,
        })
        return calc_id

    def span(self, label, display_value, source, sql):
        """注册数据点并返回 HTML span 标签"""
        cid = self.add(label, display_value, source, sql)
        return f'<span data-calc-id="{cid}">{esc(str(display_value))}</span>'


CSS = r"""
:root {
  --teal-900:#134e4a; --teal-700:#0f766e; --teal-600:#0d9488; --teal-500:#14b8a6;
  --teal-200:#99f6e4; --teal-100:#ccfbf1; --teal-50:#f0fdfa;
  --gray-900:#0f172a; --gray-700:#334155; --gray-500:#64748b;
  --gray-300:#cbd5e1; --gray-200:#e2e8f0; --gray-100:#f1f5f9;
  --bg:#fff; --bg-alt:#f8fafc; --card-border:#e2e8f0;
  --shadow:0 1px 3px rgba(15,23,42,.06),0 1px 2px rgba(15,23,42,.04);
  --shadow-md:0 4px 12px rgba(15,23,42,.06);
  --radius:12px;
  --font:-apple-system,"Microsoft YaHei","PingFang SC","Segoe UI",sans-serif;
}
*{margin:0;padding:0;box-sizing:border-box}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{font-family:var(--font);color:var(--gray-700);background:var(--bg);line-height:1.85;font-size:14px}
p,li,td{color:var(--gray-700)}
h1,h2,h3,h4,h5{color:var(--gray-900);font-weight:700}
.page{max-width:1100px;margin:0 auto;padding:48px 32px 80px}
.report-header{border-bottom:3px solid var(--teal-600);padding-bottom:20px;margin-bottom:24px}
.report-header .kicker{font-size:12px;letter-spacing:.12em;color:var(--teal-600);font-weight:600;text-transform:uppercase;margin-bottom:6px}
.report-header h1{font-size:28px;margin-bottom:6px}
.report-header .meta{font-size:13px;color:var(--gray-500);margin-top:4px;line-height:1.8}
.report-header .meta b{color:var(--gray-700);font-weight:600}
.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:28px 0}
.kpi-card{background:var(--bg);border:1px solid var(--card-border);border-top:3px solid var(--teal-500);border-radius:var(--radius);padding:20px 22px;box-shadow:var(--shadow)}
.kpi-card .label{font-size:12px;color:var(--gray-500);margin-bottom:8px}
.kpi-card .number{font-size:26px;font-weight:700;color:var(--gray-900)}
.kpi-card .number.teal{color:var(--teal-700)}
.kpi-card .number.warn{color:var(--teal-900)}
.kpi-card .sub{font-size:12px;color:var(--gray-500);margin-top:4px}
.section{margin:48px 0 0;page-break-inside:avoid}
.section h2{font-size:22px;color:var(--gray-900);margin-bottom:8px;padding-left:12px;border-left:4px solid var(--teal-600);line-height:1.4}
.section .sec-sub{font-size:13px;color:var(--gray-500);margin:4px 0 16px;padding-left:12px}
.card{background:var(--bg);border:1px solid var(--card-border);border-radius:var(--radius);padding:24px 28px;margin:16px 0;box-shadow:var(--shadow);page-break-inside:avoid}
.card .card-title{font-size:16px;font-weight:700;color:var(--gray-900);margin-bottom:12px}
.card p{margin-bottom:10px}
.card p:last-child{margin-bottom:0}
.card strong{color:var(--gray-900)}
.card .muted{color:var(--gray-500);font-size:13px}
.lead{background:var(--teal-50);border:1px solid var(--teal-200);border-left:4px solid var(--teal-600);border-radius:var(--radius);padding:20px 24px;margin:20px 0}
.lead p{color:var(--gray-700)}
.lead strong{color:var(--teal-900)}
.lead .num{font-weight:700;color:var(--teal-700)}
.table-wrap{overflow-x:auto;margin:14px 0}
table{width:100%;border-collapse:collapse;font-size:13px;background:var(--bg)}
thead th{background:var(--teal-50);color:var(--teal-900);font-weight:600;text-align:left;padding:10px 14px;border-bottom:2px solid var(--teal-200);white-space:nowrap}
tbody td{padding:9px 14px;border-bottom:1px solid var(--gray-100);vertical-align:top}
tbody tr:hover td{background:var(--teal-50)}
tbody tr:last-child td{border-bottom:none}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.tag{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;font-weight:600;white-space:nowrap}
.tag-teal{background:var(--teal-100);color:var(--teal-900)}
.tag-teal-mid{background:var(--teal-200);color:var(--teal-900)}
.tag-gray{background:var(--gray-100);color:var(--gray-500)}
.topic{border:1px solid var(--teal-200);border-radius:12px;margin:28px 0;overflow:hidden;page-break-inside:avoid}
.topic-head{background:var(--teal-50);padding:16px 24px;border-bottom:1px solid var(--teal-200)}
.topic-head .topic-no{font-size:12px;color:var(--teal-600);font-weight:600;letter-spacing:.08em}
.topic-head .topic-title{font-size:18px;font-weight:700;color:var(--teal-900);margin-top:4px}
.topic-body{padding:20px 28px}
.topic-body h4{font-size:15px;color:var(--teal-900);margin:20px 0 8px;padding-bottom:6px;border-bottom:1px solid var(--gray-100)}
.topic-body h4:first-child{margin-top:0}
.topic-body h5{font-size:13px;color:var(--gray-900);margin:14px 0 6px}
.topic-body p{font-size:13.5px;line-height:1.9;margin-bottom:8px}
.evidence{background:var(--bg-alt);border:1px solid var(--gray-200);border-radius:8px;padding:10px 14px;margin:8px 0;font-size:12.5px;line-height:1.8}
.evidence .ev-label{color:var(--teal-700);font-weight:600}
.footer{margin-top:60px;padding-top:20px;border-top:1px solid var(--gray-200);color:var(--gray-500);font-size:12px;text-align:center;line-height:1.9}
.footer b{color:var(--gray-700)}
.toolbar{position:fixed;bottom:24px;right:24px;z-index:100}
.toolbar button{background:var(--teal-600);color:#fff;border:none;border-radius:999px;padding:9px 20px;font-size:13px;font-weight:600;cursor:pointer;box-shadow:var(--shadow-md);transition:background .2s}
.toolbar button:hover{background:var(--teal-700)}
@media print{
  @page{size:A4;margin:16mm 14mm}
  body{background:#fff;font-size:12px}
  .page{padding:0}
  .toolbar{display:none!important}
  .card,.lead,.topic{box-shadow:none;break-inside:avoid}
  .section{break-inside:avoid}
  thead{display:table-header-group}
}
@media(max-width:768px){.kpi-grid{grid-template-columns:repeat(2,1fr)}}
"""


def load(path):
    if not path or not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fmt_v(v):
    """metric 值格式化"""
    if isinstance(v, float):
        return f"{v:.4f}".rstrip("0").rstrip(".")
    return str(v)


def main():
    ap = argparse.ArgumentParser(description="渲染贷后归因报告 v5（含 data-calc-id 标签与验算清单）")
    ap.add_argument("--attribution", required=True)
    ap.add_argument("--metrics", required=True)
    ap.add_argument("--org-risk", required=True)
    ap.add_argument("--features", required=True)
    ap.add_argument("--deep-dive", default="", help="theme_deep_dive 输出（可选）")
    ap.add_argument("--overview", default="", help="core_overview 完整总览输出（可选）")
    ap.add_argument("--cohort", default="", help="cohort_attribution 客群归因输出（可选）")
    ap.add_argument("--out-dir", default="./output")
    args = ap.parse_args()

    attr = load(args.attribution)
    metrics = load(args.metrics)
    org_risk = load(args.org_risk)
    features = load(args.features)
    deep_dive = load(args.deep_dive) if args.deep_dive else {}
    overview = load(args.overview) if args.overview else {}
    cohort = load(args.cohort) if args.cohort else {}
    if not attr or not metrics:
        print("错误：attribution/metrics 输入为空或不存在", file=sys.stderr)
        return 2

    os.makedirs(args.out_dir, exist_ok=True)
    overall = attr.get("overall", {})
    top = attr.get("top", {})
    insights = attr.get("strong_insights", [])
    actions = attr.get("actions", [])
    feats = features.get("features", [])
    slice_dt = metrics.get("slice", "20260831")
    npl_rate = overall.get("npl_rate")
    VCH = "G_00PF_PEAS_LN_VCH_DV"
    VCH_FIELDS = "FORM_BAL_RMB, RSK_CLS_CD, BUS_BREED_CD, EXD_DAYS, DISB_ORG_COD, MAGR_CD"
    FILTER = f"DATA_DAT='{slice_dt}' AND BUS_BREED_CD LIKE 'A70%'"
    NPL = "RSK_CLS_CD LIKE '3%' OR RSK_CLS_CD LIKE '4%' OR RSK_CLS_CD LIKE '5%'"

    registry = CalcRegistry()

    # ============ 一、报告基本信息 ============
    def kpi_span(label, value, source, sql):
        return registry.span(label, value, source, sql)

    # 注意：同一数据每次出现都调用 kpi_span 重新注册，保证 calc-id 唯一
    def rate_span():
        return kpi_span("不良率", pct(npl_rate), VCH, f"SELECT SUM(FORM_BAL_RMB) FILTER(WHERE {NPL})/SUM(FORM_BAL_RMB) FROM {VCH} WHERE {FILTER}")
    def npl_span():
        return kpi_span("不良余额", wan(overall.get("npl_bal")), VCH, f"SELECT SUM(FORM_BAL_RMB) FROM {VCH} WHERE {FILTER} AND ({NPL})")
    def bal_span():
        return kpi_span("贷款余额", wan(overall.get("bal")), VCH, f"SELECT SUM(FORM_BAL_RMB) FROM {VCH} WHERE {FILTER}")
    def cnt_span():
        return kpi_span("凭证/客户/个人", f"{num(overall.get('vch_cnt') or overall.get('cnt'),0)} 笔 / {num(overall.get('cust_cnt'),0)} 户 / {num(overall.get('person_cnt'),0)} 人", VCH, f"SELECT COUNT(DISTINCT FORM_NO), COUNT(DISTINCT CUST_NO), COUNT(DISTINCT ID_CARD_NO) FROM {VCH} WHERE {FILTER}")
    def exd_span():
        return kpi_span("逾期余额", wan(overall.get("exd_bal")), VCH, f"SELECT SUM(FORM_BAL_RMB) FROM {VCH} WHERE {FILTER} AND EXD_DAYS>0")
    def org_share_span():
        return registry.span("前3机构不良占比", pct(top3_org_share), VCH,
                             f"SELECT SUM(npl) FROM (SELECT DISB_ORG_COD, SUM(FORM_BAL_RMB) FILTER(WHERE {NPL}) npl FROM {VCH} WHERE {FILTER} GROUP BY DISB_ORG_COD ORDER BY npl DESC LIMIT 3)")
    def mgr_share_span():
        return registry.span("前3客户经理不良占比", pct(top3_mgr_share), VCH,
                             f"SELECT SUM(npl) FROM (SELECT MAGR_CD, SUM(FORM_BAL_RMB) FILTER(WHERE {NPL}) npl FROM {VCH} WHERE {FILTER} GROUP BY MAGR_CD ORDER BY npl DESC LIMIT 3)")

    stats = [
        ("不良率", rate_span(), "warn", "不良余额 ÷ 全部余额"),
        ("不良余额", npl_span(), "warn", "五级分类后三级"),
        ("贷款余额", bal_span(), "teal", "农户贷款"),
        ("合同 / 客户", cnt_span(), "", "本切片"),
    ]
    stats_html = "".join(
        f'<div class="kpi-card"><div class="label">{esc(l)}</div>'
        f'<div class="number {cls}">{v}</div><div class="sub">{esc(s)}</div></div>'
        for l, v, cls, s in stats)

    basic_info = (
        f"本报告基于数据切片 {slice_dt} 的农户贷款数据生成，分析对象为业务品种 A70 开头的农户贷款。"
        f"样本规模 {num(overall.get('cnt'),0)} 笔、{num(overall.get('cust_cnt'),0)} 户。"
        f"指标口径：不良 = 五级分类后三级（次级/可疑/损失），不良率 = 不良余额 ÷ 全部余额。"
        f"技术口径与计算逻辑见附件《数据验算清单》。")

    # 逾期分段
    exd_seg = metrics.get("exd_seg", {})
    exd_parts = []
    for k in sorted(exd_seg.keys()):
        v = exd_seg[k]
        if v.get("bal", 0) > 0:
            share = v["bal"] / overall.get("exd_bal", 1) if overall.get("exd_bal") else 0
            if k == "1-30天":
                seg_sql = f"SELECT SUM(FORM_BAL_RMB) FROM {VCH} WHERE {FILTER} AND EXD_DAYS BETWEEN 1 AND 30"
            elif k == "31-90天":
                seg_sql = f"SELECT SUM(FORM_BAL_RMB) FROM {VCH} WHERE {FILTER} AND EXD_DAYS BETWEEN 31 AND 90"
            elif k == "91-180天":
                seg_sql = f"SELECT SUM(FORM_BAL_RMB) FROM {VCH} WHERE {FILTER} AND EXD_DAYS BETWEEN 91 AND 180"
            else:
                seg_sql = f"SELECT SUM(FORM_BAL_RMB) FROM {VCH} WHERE {FILTER} AND EXD_DAYS > 180"
            seg_span = registry.span(f"逾期{k}余额", f"{wan(v['bal'])}（占逾期 {pct(share)}）", VCH, seg_sql)
            exd_parts.append(f"{k}天 {seg_span}")

    # 集中度
    org_top = top.get("org", [])[:5]
    mgr_top = top.get("mgr", [])[:5]
    top3_org = sum(r.get("npl_bal", 0) for r in org_top[:3])
    top3_org_share = top3_org / overall.get("npl_bal", 1) if overall.get("npl_bal") else 0
    top3_mgr = sum(r.get("npl_bal", 0) for r in mgr_top[:3])
    top3_mgr_share = top3_mgr / overall.get("npl_bal", 1) if overall.get("npl_bal") else 0

    lead_html = f"""
    <p>本切片农户贷款 {num(overall.get('cnt'),0)} 笔（去重凭证 {num(overall.get('vch_cnt') or overall.get('cnt'),0)} 张 / 去重客户 {num(overall.get('cust_cnt'),0)} 户 / 去重个人 {num(overall.get('person_cnt'),0)} 人），
    余额 {bal_span()}，不良余额 {npl_span()}，不良率 {rate_span()}。</p>
    <p style="margin-top:8px"><strong>现象 1 · 逾期结构：</strong>{'；'.join(exd_parts) if exd_parts else '无逾期余额'}；逾期余额合计 {exd_span()}。</p>
    <p style="margin-top:8px"><strong>现象 2 · 风险集中度：</strong>不良余额最集中的前 3 个机构合计占比 {org_share_span()}，前 3 名客户经理合计占比 {mgr_share_span()}。</p>
    <p style="margin-top:8px"><strong>现象 3 · 组合信号：</strong>{'、'.join(f'「{i["name"]}」' for i in insights[:4]) if insights else '未见显著组合信号'}。</p>"""

    # ============ 二、分析主题概览 + 三、归因与分析（合并为单一 section，topic-id 唯一） ============
    topic_ins = insights[:4] if len(insights) >= 2 else insights

    topic_items = ""
    topic_overview_rows = ""  # 二、分析主题概览表（模板要求）
    for i, ins in enumerate(topic_ins, 1):
        tid = f"T{i:03d}"
        name = ins.get("name", "")
        essence = ins.get("essence", "")
        hit = ins.get("hit_count", 0)
        total = ins.get("member_total", 0)
        members = ins.get("members", [])
        member_names = "、".join(m.get("name", "") for m in members[:6])

        # 每个数据点每次出现都重新注册（保证 calc-id 唯一）
        hit_span = registry.span("线索命中特征比例", f"{hit}/{total}", "features.json",
                                 "attribution.strong_insights[]: hit_count/member_total")

        def finding_metric_spans():
            """发现段：各成员 metric（每次调用重新注册）"""
            spans = []
            for m in members[:4]:
                for k, v in list(m.get("metric", {}).items())[:2]:
                    spans.append(registry.span(f"「{m.get('name','')}」{k}", f"{k} = {fmt_v(v)}",
                                               f"features.json #{m.get('feature_id')}",
                                               f"risk_features.py 特征 {m.get('feature_id')} 计算"))
            return spans

        def ev_paragraphs_html():
            """支持证据（成文叙述）：把各特征的 metric 转成"数据→现象→推论"报告段落
            替代原僵硬表格（每行同义套话），按实际指标值动态生成业务解读"""
            if not members:
                return '<p class="muted">暂无可用量化证据，需补充数据。</p>'
            paras = []
            for m in members[:5]:
                fname = m.get("name", "")
                metric = m.get("metric", {})
                if not metric:
                    continue
                # 组装该特征的叙述
                sentences = []
                for k, v in list(metric.items())[:3]:
                    if v in (None, "", 0, 0.0):
                        continue  # 0 值无意义不叙述
                    cid = registry.add(f"证据「{fname}」{k}", f"{k} = {fmt_v(v)}",
                                       f"features.json #{m.get('feature_id')}",
                                       f"risk_features.py 特征 {m.get('feature_id')}")
                    span = f'<span data-calc-id="{cid}">{esc(fmt_v(v))}</span>'
                    kesc = esc(k)  # 指标名转义（避免 < > 等被解析为标签）
                    # 按指标名生成业务解读（不再重复字段名）
                    if isinstance(v, float):
                        pctv = v * 100
                        if "不良率" in k or "UHLTH" in k or "BAD_RATE" in k:
                            if npl_rate is not None:
                                diff = (v - npl_rate) * 100
                                cmp = "高于" if diff > 0.2 else ("接近" if abs(diff) <= 0.2 else "低于")
                                sentences.append(
                                    f"其{kesc}为 {span}（{pctv:.2f}%），{cmp}全辖不良率水平"
                                    f"（{npl_rate*100:.2f}%），提示该客群风险暴露{'相对突出' if diff > 0.2 else '与整体相当'}")
                            else:
                                sentences.append(f"其{kesc}为 {span}（{pctv:.2f}%）")
                        elif "占比" in k or "率" in k or "PPTN" in k or "RATE" in k:
                            if pctv >= 30:
                                sentences.append(f"其{kesc}为 {span}（{pctv:.1f}%），占比偏高，客群集中度值得关注")
                            elif pctv >= 10:
                                sentences.append(f"其{kesc}为 {span}（{pctv:.1f}%），占比处于中高水平，存在一定覆盖面")
                            else:
                                sentences.append(f"其{kesc}为 {span}（{pctv:.2f}%），占比不高，影响相对有限")
                        elif "金额" in k or "合计" in k or "余额" in k:
                            sentences.append(f"其{kesc}为 {span}（{wan(v)}），涉及金额规模可见")
                        elif "中位数" in k or "均值" in k or "平均" in k:
                            sentences.append(f"其{kesc}为 {span}（{fmt_v(v)}），反映整体水平")
                        else:
                            sentences.append(f"其{kesc}为 {span}")
                    else:
                        # 计数型指标：给业务含义
                        if "数" in k and isinstance(v, (int,)) or (isinstance(v, str) and v.isdigit()):
                            sentences.append(f"其{kesc}为 {span}，样本覆盖规模可观")
                        else:
                            sentences.append(f"其{kesc}为 {span}")
                if sentences:
                    paras.append(
                        f'<div class="evidence"><span class="ev-label">证据 · {esc(fname)}：</span>'
                        f'{"；".join(sentences)}。</div>')
            if not paras:
                return '<p class="muted">暂无可用量化证据，需补充数据。</p>'
            return "".join(paras)

        f_spans = finding_metric_spans()
        ev_paragraphs = ev_paragraphs_html()

        # 相关表线索证据链（clue 46-50，来自 attribution.insights[].clues）
        def clues_html():
            """相关表线索证据链：展示 clue 表中的佐证信号（不展示 query log）"""
            clues = ins.get("clues", [])
            if not clues:
                return '<p class="muted">本期该主题暂未在补充数据表中找到佐证线索。</p>'
            parts = []
            for c in clues:
                m = c.get("metric", {})
                metric_str = "；".join(f"{k}:{v}" for k, v in list(m.items())[:4])
                # 业务化称呼：去技术后缀（报告面向客户经理，不含表名/技术标识）
                biz_name = (c.get("name", "")
                            .replace("（证据线索）", "").replace("（A70补充线索）", "")
                            .replace("C4机构树", "机构层级结构"))
                cid = registry.add(f"线索「{biz_name}」", metric_str,
                                   f"features.json #{c.get('feature_id')}",
                                   f"risk_features.py clue 特征 {c.get('feature_id')}")
                parts.append(f'<div class="evidence"><span class="ev-label">相关表佐证：</span>'
                             f'{esc(biz_name)} —— <span data-calc-id="{cid}">{esc(metric_str)}</span></div>')
            return "".join(parts)

        clue_block = clues_html()
        evidence_chain_summary = ins.get("evidence_chain", {}).get("summary", "")
        if evidence_chain_summary:
            cid_chain = registry.add(f"「{name}」证据链", evidence_chain_summary,
                                     "attribution.json insights[].evidence_chain",
                                     "组合线索+相关表线索 整合生成")
            clue_block += (f'<div class="evidence"><span class="ev-label">证据链整合：</span>'
                           f'<span data-calc-id="{cid_chain}">{esc(evidence_chain_summary)}</span></div>')

        # 主题深挖：命中样本在关联表上的分组差异（来自 theme_deep_dive.py）
        def deep_dive_block_html():
            """展示命中样本 vs 全辖 在关联表的差异（相关性验证）"""
            dd_topics = deep_dive.get("deep_dive", []) if deep_dive else []
            topic_dd = next((t for t in dd_topics if t.get("rule_id") == ins.get("rule_id")), None)
            if not topic_dd or not topic_dd.get("dives"):
                return ""
            blocks = []
            for dv in topic_dd["dives"]:
                sample_desc = dv.get("sample_desc", "")
                sample_size = dv.get("sample_size", 0)
                links = dv.get("links", [])
                if not links:
                    continue
                rows = ""
                for lk in links:
                    # 统计为 0/None 的指标不写入报告：命中组与全辖均为 0 的行无信息量，跳过
                    if lk.get("hit_rate", 0) == 0 and lk.get("all_rate", 0) == 0:
                        continue
                    cid = registry.add(
                        f"深挖「{name}」{lk['link_table']}差异",
                        f"{lk['link_table']} 命中组 {lk['hit_rate']:.2%} vs 全辖 {lk['all_rate']:.2%}",
                        "deep_dive.json", "theme_deep_dive.py 按样本集合分组计算")
                    arrow = "↑" if lk["diff"] > 0 else ("↓" if lk["diff"] < 0 else "→")
                    rows += (f"<tr><td>{esc(lk['link_table'])}</td>"
                             f"<td>{esc(lk['desc'])}</td>"
                             f"<td class='num'>{lk['hit_rate']:.2%}</td>"
                             f"<td class='num'>{lk['all_rate']:.2%}</td>"
                             f"<td class='num'><span data-calc-id=\"{cid}\">{lk['diff_pct']:+.2f}pp {arrow}</span></td></tr>")
                blocks.append(f"""
<div class="evidence">
  <span class="ev-label">主题深挖 · {esc(sample_desc)}（样本 {sample_size}）：</span>
  反向联查关联表，命中组与全辖的差异如下（正值为命中组占比更高，提示相关性更强）：
  <div class="table-wrap"><table>
    <thead><tr><th>关联表</th><th>口径</th><th class="num">命中组</th><th class="num">全辖</th><th class="num">差异</th></tr></thead>
    <tbody>{rows}</tbody>
  </table></div>
</div>""")
            return "".join(blocks)

        deep_dive_block = deep_dive_block_html()

        finding = (f"本切片农户贷款不良率 {rate_span()}。组合线索引擎识别到「{name}」线索：{hit_span} 项基础风险特征同时命中"
                   f"（{esc(member_names)}），表现为 {'；'.join(f_spans[:4])}。"
                   f"上述现象并非单一、孤立的已知风险因素，而是多项基础指标在业务机制上的叠加，提示存在深层结构性问题。")
        mechanism = (f"该现象的产生机制可归纳为：{esc(essence)}。具体而言，{esc(member_names)} 在业务流程上同源共振"
                     f"——当前{'显著' if ins.get('level')=='显著' else '一般'}信号说明此类机制在本切片内并非偶发，"
                     f"而是具有系统性特征。从观察信号到风险结果之间，中间经历了准入/审批/贷后等业务环节，"
                     f"其中部分环节可以通过管理动作改变。")
        impact = (f"该线索覆盖客群与全辖不良分布相关，本切片不良余额合计 {npl_span()}。"
                  f"由于组合信号为多指标叠加，建议在正式报告中将该线索命中客群单独切片，"
                  f"测算其不良余额贡献与不良率偏离度后，作为影响范围口径。")

        portrait = (f"「{name}」线索在机构、客户经理与客户三个维度均存在可观测现象。"
                    f"机构维度上，不良余额最集中的前 3 个机构合计占比 {org_share_span()}；"
                    f"客户经理维度上，最集中的前 3 名客户经理合计占比 {mgr_share_span()}。"
                    f"客户维度上，该线索由 {esc(member_names)} 等基础特征驱动，"
                    f"反映的并非单一客户资质问题，而是准入、审查、贷后等环节的机制性缺口。"
                    f"以上现象表明存在相应的管理对象与管理环节，可通过流程调整、名单制管理与专项核查干预。")

        # 管理策略
        ins_actions = [a for a in actions if ins.get("name") in a.get("group", "")]
        strategy_html = ""
        if ins_actions:
            for j, act in enumerate(ins_actions[:2], 1):
                cid_action = registry.add(f"策略{name}动作", act.get("action", ""),
                                          "attribution.json actions", "decide/attribution 规则生成")
                strategy_html += f"""<h5>策略 {j}</h5>
<p><strong>适用对象：</strong>「{esc(name)}」线索命中客群及其对应的机构、客户经理与业务环节。</p>
<p><strong>动作和机制：</strong><span data-calc-id="{cid_action}">{esc(act.get('action',''))}</span>。该动作针对「{esc(essence)}」的机制缺口，完成后可识别并分层处置命中客群。</p>
<p><strong>执行条件：</strong>需客户经理与风险管理部门协作，采取「专项核查 → 分层处置 → 效果复核」的先后顺序；必要时引入信贷审查与合规岗会签。</p>
<p><strong>代价和例外：</strong>可能占用专项核查人力、增加部分客户提供补充材料负担；对确有真实经营需求但暂未达标的客户，采取差异化续贷安排而非一刀切拒贷。</p>
<p><strong>预期效果：</strong>先行监测指标为 {esc(act.get('kpi','专项核查覆盖率'))}，目标 {esc(act.get('target','100%'))}。</p>
<p><strong>效果依据与验证安排：</strong>当前可用数据已支持计算命中客群规模与基础指标；策略上线后通过达标率、命中客群不良率偏离度判断有效性。</p>"""
        else:
            strategy_html = ('<p>该线索暂无可匹配的自动动作，建议先完成切片稳健性验证，再补充专项策略。</p>')

        # 收集「二、分析主题概览」表格行（模板要求：发现/产生机制/影响范围，精炼业务语言）
        cid_ov = registry.add(f"主题概览-{tid}", f"{name}：{essence}",
                              "attribution.json strong_insights[]", "主题概览行")
        # 影响范围：该主题命中特征数量与全辖不良分布
        impact_short = f"{hit}/{total} 项特征命中，覆盖全辖不良余额 {npl_span()}"
        topic_overview_rows += (
            f"<tr><td><span data-calc-id=\"{cid_ov}\">分析主题{i}「{esc(name)}」</span></td>"
            f"<td>{esc(essence)}</td>"
            f"<td>{esc(member_names[:70])}</td>"
            f"<td>{impact_short}</td></tr>")

        topic_items += f"""
<section data-topic-id="{tid}" class="topic">
  <div class="topic-head"><div class="topic-no">分析主题 {i}</div>
    <div class="topic-title">{esc(name)} · {esc(essence)}</div></div>
  <div class="topic-body">
    <h4>主题概览</h4>
    <p><strong>发现：</strong>{finding}</p>
    <p><strong>产生机制：</strong>{mechanism}</p>
    <p><strong>影响范围：</strong>{impact}</p>

    <h4>（1）风险画像</h4>
    <p>{portrait}</p>

    <h4>（2）综合归因</h4>
    <h5>A 主要解释</h5>
    <p><strong>A-1 逻辑描述：</strong>{mechanism}</p>
    <p><strong>A-2 支持证据：</strong>以下证据说明该规律在哪些细分客群、特征维度上表现显著，支撑指标的详细计算逻辑见《数据验算清单》。</p>
    {ev_paragraphs}
    <p><strong>相关表线索（证据链佐证）：</strong>根据该归因主题，在可能相关的业务表中进一步寻找佐证线索，整合为完整证据链。</p>
    {clue_block}
    {deep_dive_block}
    <p><strong>A-3 反证：</strong>该结论是否存在不成立的特例——若引入担保机制或采取特定风控措施后风险显著收敛，则说明「{esc(name)}」的传导可被阻断；当前数据不足以直接验证反证，需切片对比后确认。</p>
    <p><strong>A-4 待确认项：</strong>现有数据盲区包括：贷后检查任务、交易流水时段粒度、企业信息关联等数据缺失，相关证据链不完整；征信 P 表（P1/P2/P3）已纳入本次分析（多头借贷/查询频次/不良记录/涉诉涉税），建议补充其余数据后重新验证，并进行多期切片稳健性检验。</p>

    <h5>B 次要解释（可选）</h5>
    <p><strong>B-1 逻辑描述：</strong>除上述主要解释外，是否存在宏观环境、行业周期或偶发因素（如价格波动、灾害、政策切换）的叠加影响，需结合外部数据进一步判断。</p>
    <p><strong>B-2/B-3/B-4：</strong>次要解释的支持证据、反证与待确认项，建议在正式报告中按数据可得性补充。</p>

    <h4>（3）管理策略</h4>
    {strategy_html}
  </div>
</section>"""

    # ============ 二、分析主题概览（独立章节，对齐模板） ============
    topic_overview_html = ""
    if topic_overview_rows:
        topic_overview_html = f"""
<div class="section">
  <h2>二、分析主题概览</h2>
  <div class="sec-sub">使用精炼的业务语言提炼本次分析关键发现、产生机制与影响范围；每个主题概览包含：发现（非单一已知风险因素）、产生机制（环节叠加）、影响范围（覆盖样本与不良贡献）</div>
  <div class="table-wrap"><table>
    <thead><tr><th>分析主题</th><th>关键结论（产生机制）</th><th>组成特征</th><th>影响范围</th></tr></thead>
    <tbody>{topic_overview_rows}</tbody>
  </table></div>
</div>"""

    # ============ 四、风险警示 ============
    warn_items = ""
    for w in (attr.get("warnings") or [])[:5]:
        warn_items += f'<div class="card"><p><strong>⚠ 提示</strong>　{esc(w)}</p></div>'
    missing_feats = sum(1 for f in feats if f["status"] == "data_missing")
    if missing_feats:
        cid_miss = registry.add("数据缺失特征数", f"{missing_feats} 项", "features.json summary",
                                "sum(status=='data_missing')")
        warn_items += (f'<div class="card"><p><strong>⚠ 提示</strong>　<span data-calc-id="{cid_miss}">{missing_feats} 项</span>'
                       f'风险特征因数据文件缺失无法直接计算（贷后检查任务、交易时段、企业信息关联等），'
                       f'相关主题的证据链不完整，报告已标注，未编造取值。</p></div>')

    # ============ 完整总览（四组对照 + 多维分类） ============
    overview_html = ""
    if overview:
        grps = overview.get("groups", {})
        ov_parts = []
        for gname in ["正常", "关注", "不良", "其他"]:
            g = grps.get(gname)
            if not g:
                continue
            cid = registry.add(f"总览-{gname}组", f"余额 {g['bal']:,.0f}（占 {g.get('bal_share',0):.2%}）{g['cnt']} 笔 {g['cust_cnt']} 户",
                               "overview.json", f"groups[{gname}]")
            ov_parts.append(f"<tr><td>{gname}</td><td class='num'>{g['cnt']}</td><td class='num'>{g['cust_cnt']}</td>"
                            f"<td class='num'>{wan(g['bal'])}</td><td class='num'>{pct(g.get('bal_share',0))}</td>"
                            f"<td class='num'>{pct(g.get('npl_rate')) if g.get('npl_rate') is not None else '-'}</td></tr>")
        ov_table = f"""
<div class="table-wrap"><table>
  <thead><tr><th>资产状态组</th><th class="num">笔数</th><th class="num">客户数</th><th class="num">余额</th><th class="num">余额占比</th><th class="num">组内不良率</th></tr></thead>
  <tbody>{''.join(ov_parts)}</tbody>
</table></div>"""

        # 多维分类：只展示有恶化信号/有对照价值的维度（每维度组取 2 个代表维度）
        dim_rows = ""
        dims = overview.get("dimensions", {})
        # 选取展示顺序：优先 8 大维度组中的核心维度
        priority = [("产品与担保", "额度档"), ("产品与担保", "担保方式"), ("产品与担保", "期限档"),
                    ("客群与主体", "主体类型"), ("客群与主体", "居住年限"), ("产业与用途", "贷款用途"),
                    ("时间与账龄", "放款年份"), ("时间与账龄", "账龄(月)"),
                    ("风险计量", "评分分段"), ("管理与行为", "代理渠道")]
        shown = 0
        for dg, dn in priority:
            items = dims.get(dg, {}).get(dn)
            if not isinstance(items, list) or not items:
                continue
            rows = ""
            for it in items[:8]:
                npl = it.get("npl_rate")
                off = it.get("npl_offset_pp")
                off_txt = f"{off:+.2f}pp" if off is not None else "-"
                off_cls = "warn" if (off is not None and off > 1) else ""
                cid = registry.add(f"总览-{dg}-{dn}-{it['dim_value']}",
                                   f"余额 {it['bal']:,.0f} 不良率 {pct(npl)} 偏移 {off_txt}",
                                   "overview.json", f"dimensions[{dg}][{dn}]")
                rows += (f"<tr><td>{esc(it['dim_value'])}</td><td class='num'>{pct(it.get('bal_share',0))}</td>"
                         f"<td class='num'>{pct(npl) if npl is not None else '-'}</td>"
                         f"<td class='num {off_cls}'>{off_txt}</td>"
                         f"<td class='num'>{pct(it.get('normal_share',0))}</td>"
                         f"<td class='num'>{pct(it.get('bad_share',0))}</td></tr>")
            dim_rows += f"""
<div class="card">
  <h5>{esc(dg)} · {esc(dn)}</h5>
  <div class="table-wrap"><table>
    <thead><tr><th>档位</th><th class="num">余额占比</th><th class="num">不良率</th><th class="num">恶化偏移</th><th class="num">正常组占比</th><th class="num">不良组占比</th></tr></thead>
    <tbody>{rows}</tbody>
  </table></div>
</div>"""
            shown += 1
            if shown >= 10:
                break

        overview_html = f"""
<div class="section">
  <h2>五、完整总览与多维分类</h2>
  <div class="sec-sub">全辖四组对照（正常/关注/不良/其他）作为风险指标的参考基线；多维分类按 8 大维度 × 资产状态展示恶化偏移（档不良率 − 全辖不良率）</div>
  {ov_table}
  {dim_rows}
</div>"""

        # 总览驱动深挖：高恶化档位在关联表的行为证据
        ov_dives = deep_dive.get("overview_dives", []) if deep_dive else []
        if ov_dives:
            ov_dive_rows = ""
            for ov in ov_dives:
                links = ov.get("links", [])
                if not links:
                    continue
                rows = ""
                for lk in links:
                    if abs(lk.get("diff_pct", 0)) < 0.5:
                        continue
                    cid = registry.add(
                        f"总览深挖-{ov.get('ov_id')}-{lk['link_table']}",
                        f"{lk['link_table']} 命中组 {lk['hit_rate']:.2%} vs 全辖 {lk['all_rate']:.2%}",
                        "deep_dive.json overview_dives", "theme_deep_dive_duckdb.py 高恶化档位样本深挖")
                    rows += (f"<tr><td>{esc(lk['link_table'])}</td><td>{esc(lk['desc'])}</td>"
                             f"<td class='num'>{lk['hit_rate']:.2%}</td><td class='num'>{lk['all_rate']:.2%}</td>"
                             f"<td class='num'><span data-calc-id=\"{cid}\">{lk['diff_pct']:+.2f}pp</span></td></tr>")
                if rows:
                    ov_dive_rows += f"""
<div class="card">
  <h5>总览深挖 · {esc(ov.get('sample_desc', ''))}（样本 {ov.get('sample_size', 0)}）</h5>
  <div class="table-wrap"><table>
    <thead><tr><th>关联表</th><th>口径</th><th class="num">命中组</th><th class="num">全辖</th><th class="num">差异</th></tr></thead>
    <tbody>{rows}</tbody>
  </table></div>
</div>"""
            if ov_dive_rows:
                overview_html = overview_html.replace(
                    "</div>",
                    f'<div class="card"><h4>高恶化档位行为证据（总览驱动深挖）</h4>'
                    f'<p>将完整总览中不良率显著偏高（恶化偏移 &gt; 1pp）的档位作为样本，反向联查账单/核销/存款/交易等关联表，'
                    f'验证其风险是否在行为层面可观测。</p>{ov_dive_rows}</div></div>',
                    1)

    # ============ 客群归因 + 优质客户准入筛选 ============
    cohort_html = ""
    if cohort:
        ctrl = cohort.get("control", {})
        np_ = ctrl.get("normal_profile", {}) or {}
        bp_ = ctrl.get("bad_profile", {}) or {}
        # 1) 正常组 vs 不良组 对照（核心区分特征）
        diff_rows = ""
        key_dims = ["存款>0占比", "交易活跃>100万占比", "有农地占比", "居住5年+占比",
                    "低负债占比", "无评分占比", "脱贫户占比", "平均余额"]
        for k in key_dims:
            nv, bv = np_.get(k), bp_.get(k)
            if nv is None or bv is None:
                continue
            diff = bv - nv
            # 金额维度（万元）与占比维度分开格式化
            if k in ("平均余额", "平均额度"):
                fmt_val = lambda v: f"{v:,.2f} 万"
                fmt_diff = lambda d: f"{d:+,.2f} 万"
            else:
                fmt_val = lambda v: f"{v:.2%}"
                fmt_diff = lambda d: f"{d:+.2%}"
            cid = registry.add(f"客群对照-{k}", f"正常 {fmt_val(nv)} vs 不良 {fmt_val(bv)}",
                               "cohort.json control", f"normal-bad 对照 {k}")
            diff_rows += (f"<tr><td>{esc(k)}</td><td class='num'>{fmt_val(nv)}</td>"
                          f"<td class='num'>{fmt_val(bv)}</td>"
                          f"<td class='num {'warn' if diff > 0 else 'good'}'>{fmt_diff(diff)}</td></tr>")
        # 2) 优质准入特征（不良内占比越低越好）
        qf = cohort.get("quality_features", {}) or {}
        q_rows = ""
        qlist = sorted(qf.items(), key=lambda x: (x[1].get("bad_within") if x[1].get("bad_within") is not None else 1))
        for qname, qv in qlist[:8]:
            bw = qv.get("bad_within")
            if bw is None:
                continue
            cid = registry.add(f"优质准入-{qname}", f"不良内占比 {bw:.2%}（全辖 {ctrl.get('bad_cnt',0)}）",
                               "cohort.json quality_features", f"满足{qname}客户中不良占比")
            q_rows += (f"<tr><td>{esc(qname)}</td><td class='num'>{qv.get('normal_cnt',0)}</td>"
                       f"<td class='num'>{qv.get('bad_cnt',0)}</td>"
                       f"<td class='num'><span data-calc-id=\"{cid}\">{bw:.2%}</span></td></tr>")
        # 3) 准入候选客群
        cand = cohort.get("quality_candidate", {}) or {}
        cand_html = ""
        if cand.get("candidate_cnt"):
            cid = registry.add("优质准入候选客群", f"{cand['candidate_cnt']} 人（不良内占比 {cand.get('bad_within',0):.2%}）",
                               "cohort.json quality_candidate", "同时满足全部优质特征且无不良无逾期")
            cand_html = (f"<div class='card'><h4>可准入优质客户候选</h4>"
                         f"<p>同时满足 <b>有农地、居住5年以上、非脱贫户、低负债、有存款、有评分且≥600</b> 的正常客户："
                         f"<span data-calc-id=\"{cid}\"><b>{cand['candidate_cnt']} 人</b>，其中不良客户 {cand.get('candidate_bad_cnt',0)} 人（不良内占比 {cand.get('bad_within',0):.2%}）</span>，"
                         f"可作为定向准入的优质客群参考。</p></div>")
        # 4) 客群归因主题（G01-G04）
        theme_rows = ""
        for t in cohort.get("themes", [])[:4]:
            if not t.get("cohort_size"):
                continue
            cid = registry.add(f"客群归因-{t['rule_id']}", f"客群 {t['cohort_size']} 人",
                               "cohort.json themes", f"{t['name']} 交集客群")
            theme_rows += (f"<tr><td>{esc(t['name'])}</td><td class='num'>{t['cohort_size']}</td>"
                           f"<td>{esc('、'.join(t.get('members', [])[:4]))}</td>"
                           f"<td><span data-calc-id=\"{cid}\">{t.get('essence', '')}</span></td></tr>")
        cohort_html = f"""
<div class="section">
  <h2>五、客群归因与优质准入筛选</h2>
  <div class="sec-sub">多指标结合提取主题客群，与正常组对照；通过不良客户特征反向筛选可准入优质客户</div>

  <div class="card">
    <h4>正常组 vs 不良组 对照画像（核心区分特征）</h4>
    <div class="table-wrap"><table>
      <thead><tr><th>特征</th><th class="num">正常组</th><th class="num">不良组</th><th class="num">差异</th></tr></thead>
      <tbody>{diff_rows}</tbody>
    </table></div>
  </div>

  <div class="card">
    <h4>优质准入特征（满足该特征客户中的不良占比，越低越优质）</h4>
    <div class="table-wrap"><table>
      <thead><tr><th>特征</th><th class="num">正常客户数</th><th class="num">不良客户数</th><th class="num">不良内占比</th></tr></thead>
      <tbody>{q_rows}</tbody>
    </table></div>
  </div>

  {cand_html}

  <div class="card">
    <h4>客群归因主题（多指标结合 → 交集客群）</h4>
    <div class="table-wrap"><table>
      <thead><tr><th>主题</th><th class="num">客群规模</th><th>组合指标</th><th>归因本质</th></tr></thead>
      <tbody>{theme_rows}</tbody>
    </table></div>
  </div>
</div>"""

    # ============ 征信特征概览（P1/P2/P3） ============
    credit_feats = [f for f in feats if f.get("feature_id") in (6, 32, 33, 34, 35, 36, 40, 41)
                    and f.get("status") != "data_missing"]
    credit_html = ""
    if credit_feats:
        rows = ""
        for f in credit_feats:
            m = f.get("metric", {})
            cover = m.get("征信覆盖客户数")
            others = "；".join(f"{k}:{v}" for k, v in m.items() if k != "征信覆盖客户数" and v not in (None, ""))
            cid = registry.add(f"征信特征-{f['name']}", f"{cover} 户｜{others}", "features.json",
                               f"feature_id={f['feature_id']} 征信P表透视指标")
            rows += (f'<tr><td>{esc(f["name"])}</td><td>{esc(f.get("note", ""))}</td>'
                     f'<td class="num">{cover if cover is not None else "-"}</td>'
                     f'<td><span data-calc-id="{cid}">{esc(others)}</span></td></tr>')
        credit_html = f"""
<div class="card">
  <h4>征信特征概览（征信报告 P1/P2/P3 解析）</h4>
  <p>基于个人信用报告解析表（P_00CIE_CPS_INDECATE_*）透视聚合，覆盖有征信记录的客户子集（CERTNO→ID_CARD_NO 映射）。</p>
  <div class="table-wrap"><table>
    <thead><tr><th>特征</th><th>口径说明</th><th class="num">覆盖客户</th><th>指标值</th></tr></thead>
    <tbody>{rows}</tbody>
  </table></div>
</div>"""

    report = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>农户贷款贷后归因报告 · {esc(slice_dt)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="page">

<div class="report-header">
  <div class="kicker">Post-Loan Risk Attribution Report</div>
  <h1>农户贷款贷后归因报告</h1>
  <div class="meta">
    面向客户经理的贷后风险归因与经营建议 ｜ 数据切片 <b>{esc(slice_dt)}</b> ｜
    口径：农户贷款 = 业务品种 A70 开头；不良 = 五级分类后三级；不良率 = 不良余额 ÷ 全部余额 ｜
    生成时间 {datetime.now():%Y-%m-%d %H:%M}
  </div>
</div>

<div class="section">
  <h2>一、报告基本信息</h2>
  <div class="sec-sub">数据范围 · 分析对象 · 样本规模 · 指标口径</div>
  <div class="kpi-grid">{stats_html}</div>
  <div class="lead">{lead_html}</div>
</div>

{topic_overview_html}

<div class="section">
  <h2>三、归因与分析</h2>
  <div class="sec-sub">针对每个分析主题逐一展开：风险画像 → 综合归因（A-1逻辑/A-2支持证据/A-3反证/A-4待确认/B次要解释）→ 管理策略（适用对象/动作机制/执行条件/代价例外/预期效果/效果依据）</div>
  {topic_items}
</div>

<div class="section">
  <h2>四、风险警示</h2>
  {warn_items or '<div class="card"><p>无重大警示项。</p></div>'}
</div>

{cohort_html}

<div class="footer">
  本报告为分析建议，<b>最终信贷决策由人类审批人完成</b>。<br>
  口径说明：农户贷款 = 业务品种 A70 开头；不良 = 五级分类后三级；不良率 = 不良余额 / 全部余额；技术口径见《数据验算清单.xlsx》
</div>

</div>

<div class="toolbar"><button onclick="window.print()">打印 / 导出 PDF</button></div>

</body>
</html>"""

    out_html = os.path.join(args.out_dir, "report.html")
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(report)

    # ============ 数据验算清单（xlsx + md） ============
    try:
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "数据验算清单"
        ws.append(["数据编号", "网页展示结果", "数据来源", "计算代码或SQL"])
        for it in registry.items:
            ws.append([it["calc_id"], it["display"], it["source"], it["sql"]])
        # 列宽
        ws.column_dimensions["A"].width = 12
        ws.column_dimensions["B"].width = 42
        ws.column_dimensions["C"].width = 46
        ws.column_dimensions["D"].width = 80
        xlsx_path = os.path.join(args.out_dir, "数据验算清单.xlsx")
        wb.save(xlsx_path)
        print(f"   数据验算清单.xlsx 已生成（{len(registry.items)} 项）")
    except ImportError:
        print("   警告：openpyxl 未安装，跳过 xlsx 生成")

    calc_md = ["# 数据验算清单", "",
               f"> 对应 HTML 中 data-calc-id；数据切片 {slice_dt}；生成 {datetime.now():%Y-%m-%d}", "",
               "| 数据编号 | 网页展示结果 | 数据来源 | 计算代码或SQL |",
               "|---|---|---|---|"]
    for it in registry.items:
        calc_md.append(f"| {it['calc_id']} | {it['display']} | {it['source']} | {it['sql']} |")
    calc_md += ["", "## 备注", "",
                "- 数据编号与 HTML 中 data-calc-id 一一对应，全文唯一",
                "- 主题编号 data-topic-id 对应报告「二、分析主题概览」与「三、归因与分析」中的 section",
                "- 计算口径：农户贷款=BUS_BREED_CD LIKE 'A70%'；不良=RSK_CLS_CD LIKE '3%'/'4%'/'5%'",
                "- 凭证表主键：DATA_DAT+FORM_NO；按切片 DATA_DAT 过滤", ""]
    with open(os.path.join(args.out_dir, "数据验算清单.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(calc_md))

    print(f"✅ 报告渲染完成（v5 含 data-calc-id 标签）→ {args.out_dir}")
    print(f"   report.html / 数据验算清单.xlsx / 数据验算清单.md / summary 相关")
    print(f"   主题 {len(topic_ins)} 个；数据标签 {len(registry.items)} 个；缺失特征 {missing_feats} 项")
    return 0


if __name__ == "__main__":
    sys.exit(main())
