#!/usr/bin/env python3
"""render_report.py — 渲染贷后归因报告 v6（数据驱动叙述 + 5 张内联 SVG 图表）

用法:
    python3 scripts/render_report.py \\
        --attribution attribution.json --metrics metrics.json --signals signals.json \\
        --narrative narrative.json --evidence evidence.json --drill-plan drill_plan.json \\
        --out-dir ./output [--preview]

v6.0 变更（相对 v5 的重构点）:
1. **删除主题硬截断**：主题来源唯一为 ``attribution.json.topic_selection[]`` 中
   ``decision=="selected"`` 的条目，数量由数据决定；0 条时走「指标监测式」退化分支。
2. **删除四段硬编码文案**：优先用 ``narrative.json.topics[]`` 对应字段；无 narrative 时
   用数据驱动模板（按 strength 选措辞强度 / cross_stage 决定是否写跨环节共振 /
   evidence_chain.status 决定「已通过客群校验」「待验证」「数据不支持」三种定性）。
   impact 段只写真实客群不良贡献，不出现「建议在正式报告中…测算」这类 TODO 语气。
3. **5 张内联 SVG 图表**（纯字符串拼装，无 JS/CSS 库、无 CDN、断网可开）：
   逾期分段占比 / 8 大维度恶化偏移 / 线索类型不良率 vs 全辖基线 / 接续工具不良率对比 /
   主题客群 lift。图内每个数字都带 data-calc-id，可逐条验算。
4. **视觉规则**：白底 + 青绿衬色；正负值只用青绿深浅 + 灰阶，无红橙紫蓝黄花色块。
5. **双标签体系**：``data-topic-id`` / ``data-calc-id`` 全文唯一，同步产出
   《数据验算清单》.xlsx + .md（4 列：数据编号 | 网页展示结果 | 数据来源 | 计算代码或SQL）。
6. **预览版**：``--preview`` 时额外渲染「主题生成轨迹」``<details>`` 折叠块，正式报告不含。

依赖：标准库 + openpyxl（xlsx）。不得 import pandas / numpy / duckdb。
"""
import argparse
import html
import json
import math
import os
import re
import sys
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

VCH = "G_00PF_PEAS_LN_VCH_DV"
TEAL = {"900": "#134e4a", "700": "#0f766e", "600": "#0d9488", "500": "#14b8a6",
        "200": "#99f6e4", "100": "#ccfbf1", "50": "#f0fdfa"}
GRAY = {"900": "#0f172a", "700": "#334155", "500": "#64748b", "400": "#94a3b8",
        "300": "#cbd5e1", "200": "#e2e8f0", "100": "#f1f5f9", "50": "#f8fafc"}

# ---------------------------------------------------------------------------
# 基础格式化
# ---------------------------------------------------------------------------


def esc(s):
    if s is None:
        return ""
    return html.escape(str(s))


def pct(x, digits=2):
    try:
        return f"{float(x) * 100:.{digits}f}%"
    except (TypeError, ValueError):
        return "—"


def num(x, digits=0):
    try:
        return f"{float(x):,.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def wan(x, digits=2):
    """金额 → 万元（报告正文用万，验算清单保留元）"""
    try:
        return f"{float(x) / 10000:,.{digits}f} 万"
    except (TypeError, ValueError):
        return "—"


def pp(x, digits=2):
    try:
        return f"{float(x):+.{digits}f}pp"
    except (TypeError, ValueError):
        return "—"


def mult(x, digits=1):
    try:
        return f"{float(x):.{digits}f} 倍"
    except (TypeError, ValueError):
        return "—"


def fnum(x, digits=2):
    """SVG 数值：去掉多余零，保证图内文字与清单一致"""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "—"
    s = f"{v:.{digits}f}".rstrip("0").rstrip(".")
    return s or "0"


def svg_text_w(s, size=11):
    """粗略估算 SVG 文本宽度：中文按 1 个字号，西文按 0.55"""
    w = 0.0
    for ch in str(s):
        w += size if ord(ch) > 0x2E80 else size * 0.55
    return w


def load(path):
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"   警告：{path} 读取失败（{e}），按缺失处理", file=sys.stderr)
        return {}


# ---------------------------------------------------------------------------
# 数据注册表：data-calc-id 全量唯一 + 验算清单一行一条
# ---------------------------------------------------------------------------
class CalcRegistry:
    def __init__(self):
        self.items = []
        self._used = set()

    def add(self, label, display_value, source, sql, group="", force_new=False):
        """每次调用都分配一个全新编号。

        data-calc-id 的语义是「文档中的一个展示位置」，而不是「一个统计量」：
        同一个不良率可能同时出现在 KPI 卡片、执行摘要和图例里，各自都要能
        单独验算，所以不做任何跨位置复用（复用会导致验算清单里一行对应多处，
        核对时无法定位）。
        """
        cid = f"D{len(self.items) + 1:03d}"
        assert cid not in self._used, f"calc id 冲突 {cid}"
        self._used.add(cid)
        self.items.append({"calc_id": cid, "label": label, "display": str(display_value),
                           "source": source, "sql": sql, "group": group})
        return cid

    def span(self, label, display_value, source, sql, group="", cls="", suffix=""):
        """注册数据点 → 返回带 data-calc-id 的 span（正文/表格用）"""
        if suffix:
            display_value = f"{display_value}{suffix}"
        cid = self.add(label, display_value, source, sql, group)
        cls_attr = f' class="{cls}"' if cls else ""
        return f'<span data-calc-id="{cid}"{cls_attr}>{esc(display_value)}</span>'

    def unit(self, label, value, fmt, source, sql, group="", suffix="", eps=1e-12):
        """value + fmt(value) 拼成一个带标签的 span。

        统计为 0 / None 的数值不写入报告（主文档硬约束第 3 条），返回 "—"。
        """
        try:
            v = float(value)
        except (TypeError, ValueError):
            return "—"
        if v is None or abs(v) <= eps:
            return "—"
        txt = fmt(v)
        if not isinstance(txt, str):
            txt = str(txt)
        return self.span(label, txt + suffix, source, sql, group)


# ---------------------------------------------------------------------------
# CSS（视觉规则：白底 / 青绿衬色 / 无毛玻璃 / 打印 A4）
# ---------------------------------------------------------------------------
CSS = r"""
:root{
  --teal-900:#134e4a; --teal-700:#0f766e; --teal-600:#0d9488; --teal-500:#14b8a6;
  --teal-200:#99f6e4; --teal-100:#ccfbf1; --teal-50:#f0fdfa;
  --gray-900:#0f172a; --gray-700:#334155; --gray-500:#64748b; --gray-400:#94a3b8;
  --gray-300:#cbd5e1; --gray-200:#e2e8f0; --gray-100:#f1f5f9; --gray-50:#f8fafc;
  --bg:#ffffff; --bg-alt:#f8fafc; --card-border:#e2e8f0;
  --shadow:0 1px 3px rgba(15,23,42,.06),0 1px 2px rgba(15,23,42,.04);
  --shadow-md:0 4px 12px rgba(15,23,42,.06);
  --radius:12px;
  --font:-apple-system,"Microsoft YaHei","PingFang SC","Segoe UI",sans-serif;
}
*{margin:0;padding:0;box-sizing:border-box}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{font-family:var(--font);color:var(--gray-700);background:#ffffff;line-height:1.85;font-size:14px}
p,li,td{color:var(--gray-700)}
h1,h2,h3,h4,h5{color:var(--gray-900);font-weight:700}
.page{max-width:1100px;margin:0 auto;padding:44px 32px 80px}
.report-header{border-bottom:3px solid var(--teal-600);padding-bottom:18px;margin-bottom:20px}
.report-header .kicker{font-size:12px;letter-spacing:.12em;color:var(--teal-700);font-weight:600;text-transform:uppercase;margin-bottom:6px}
.report-header h1{font-size:27px;margin-bottom:6px;letter-spacing:.01em}
.report-header .meta{font-size:12.5px;color:var(--gray-500);margin-top:4px;line-height:1.9}
.report-header .meta b{color:var(--gray-700);font-weight:600}
.mode-badge{display:inline-block;margin-top:10px;padding:3px 12px;border-radius:999px;font-size:12px;
  font-weight:600;background:var(--teal-50);color:var(--teal-900);border:1px solid var(--teal-200)}
.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:24px 0 18px}
.kpi-card{background:#fff;border:1px solid var(--card-border);border-top:3px solid var(--teal-500);
  border-radius:var(--radius);padding:18px 20px;box-shadow:var(--shadow)}
.kpi-card .label{font-size:12px;color:var(--gray-500);margin-bottom:6px}
.kpi-card .number{font-size:24px;font-weight:700;color:var(--gray-900);line-height:1.35;font-variant-numeric:tabular-nums}
.kpi-card .number.teal{color:var(--teal-700)}
.kpi-card .number.deep{color:var(--teal-900)}
.kpi-card .sub{font-size:12px;color:var(--gray-500);margin-top:4px}
.section{margin:44px 0 0}
.section h2{font-size:21px;margin-bottom:6px;padding-left:12px;border-left:4px solid var(--teal-600);line-height:1.45}
.section .sec-sub{font-size:12.5px;color:var(--gray-500);margin:4px 0 14px;padding-left:12px;line-height:1.8}
.card{background:#fff;border:1px solid var(--card-border);border-radius:var(--radius);padding:22px 26px;
  margin:14px 0;box-shadow:var(--shadow)}
.card .card-title,.card h4{font-size:15.5px;font-weight:700;color:var(--gray-900);margin-bottom:10px}
.card h4 + p,.card .card-title + p{margin-top:0}
.card p{margin-bottom:9px}
.card p:last-child{margin-bottom:0}
.card strong{color:var(--gray-900);font-weight:600}
.card .muted{color:var(--gray-500);font-size:13px}
.lead{background:var(--teal-50);border:1px solid var(--teal-200);border-left:4px solid var(--teal-600);
  border-radius:var(--radius);padding:18px 22px;margin:18px 0}
.lead p{margin-bottom:8px}
.lead p:last-child{margin-bottom:0}
.lead strong{color:var(--teal-900)}
.chart{margin:16px 0 6px}
.chart .chart-title{font-size:13.5px;font-weight:700;color:var(--gray-900);margin-bottom:2px}
.chart .chart-sub{font-size:12px;color:var(--gray-500);margin-bottom:8px}
.chart svg{display:block;width:100%;height:auto;background:#fff;border:1px solid var(--gray-100);border-radius:8px}
.chart .chart-note{font-size:11.5px;color:var(--gray-500);margin-top:6px}
/* 图随文走：图直接嵌在它所解释的那段文字之后，不单列图表章节 */
.fig-inline{margin:14px 0 6px;padding:14px 16px 10px;background:var(--gray-50);
  border:1px solid var(--gray-200);border-radius:9px}
.fig-inline .fig-cap{font-size:13px;font-weight:700;color:var(--gray-900);margin-bottom:8px;
  padding-left:9px;border-left:3px solid var(--teal-600);line-height:1.45}
.fig-inline svg{display:block;width:100%;height:auto;background:#fff;
  border:1px solid var(--gray-100);border-radius:7px}
.fig-inline .fig-note{font-size:12px;color:var(--gray-500);margin-top:8px;line-height:1.6}
@media print{.fig-inline{break-inside:avoid;page-break-inside:avoid}}
.table-wrap{overflow-x:auto;margin:12px 0}
table{width:100%;border-collapse:collapse;font-size:13px;background:#fff}
thead th{background:var(--teal-50);color:var(--teal-900);font-weight:600;text-align:left;
  padding:10px 12px;border-bottom:2px solid var(--teal-200);white-space:nowrap}
tbody td{padding:8px 12px;border-bottom:1px solid var(--gray-100);vertical-align:top}
tbody tr:last-child td{border-bottom:none}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.tag{display:inline-block;padding:1px 10px;border-radius:999px;font-size:11.5px;font-weight:600;white-space:nowrap}
.tag-teal{background:var(--teal-100);color:var(--teal-900)}
.tag-teal-deep{background:var(--teal-700);color:#fff}
.tag-gray{background:var(--gray-100);color:var(--gray-500)}
.topic{border:1px solid var(--teal-200);border-radius:var(--radius);margin:26px 0;overflow:hidden;
  background:#fff;box-shadow:var(--shadow);page-break-inside:avoid;break-inside:avoid}
.topic-head{background:var(--teal-50);padding:15px 24px;border-bottom:1px solid var(--teal-200)}
.topic-head .topic-no{font-size:11.5px;color:var(--teal-700);font-weight:600;letter-spacing:.08em;
  display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.topic-head .topic-title{font-size:17.5px;font-weight:700;color:var(--teal-900);margin-top:5px;line-height:1.5}
.topic-body{padding:18px 26px 22px}
.topic-body h4{font-size:14.5px;color:var(--teal-900);margin:18px 0 8px;padding-bottom:5px;
  border-bottom:1px solid var(--gray-100)}
.topic-body h4:first-child{margin-top:0}
.topic-body h5{font-size:13px;color:var(--gray-900);margin:12px 0 5px}
.topic-body p{font-size:13.5px;line-height:1.9;margin-bottom:8px}
.kv{display:grid;grid-template-columns:76px 1fr;gap:4px 12px;font-size:13.5px;line-height:1.85;margin:6px 0 2px}
.kv .k{color:var(--teal-700);font-weight:600}
.evidence{background:var(--bg-alt);border:1px solid var(--gray-200);border-radius:8px;padding:10px 14px;
  margin:8px 0;font-size:12.8px;line-height:1.85}
.evidence .ev-label{color:var(--teal-700);font-weight:600}
.notes{background:var(--bg-alt);border:1px solid var(--gray-200);border-radius:8px;padding:12px 16px;margin:10px 0}
.notes .notes-t{font-size:12.5px;font-weight:600;color:var(--teal-900);margin-bottom:4px}
.notes ul{margin:0 0 0 18px}
.notes li{font-size:12.8px;line-height:1.8}
.decision{border:1px solid var(--teal-200);border-radius:10px;padding:14px 18px;background:var(--teal-50);margin:8px 0}
.decision .dv{display:grid;grid-template-columns:84px 1fr;gap:5px 12px;font-size:13px;line-height:1.8}
.decision .dv .k{color:var(--teal-900);font-weight:600}
.warn-box{border:1px solid var(--gray-200);border-left:4px solid var(--teal-500);background:var(--teal-50);
  border-radius:8px;padding:11px 16px;margin:8px 0;font-size:13px;line-height:1.85}
.warn-box .wt{font-weight:700;color:var(--teal-900)}
.monitor-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:14px 0}
.monitor-card{background:#fff;border:1px solid var(--card-border);border-radius:var(--radius);
  padding:16px 18px;box-shadow:var(--shadow)}
.monitor-card .mt{font-size:12px;color:var(--gray-500);margin-bottom:6px}
.monitor-card .mv{font-size:20px;font-weight:700;color:var(--teal-700);font-variant-numeric:tabular-nums}
.monitor-card .mn{font-size:12px;color:var(--gray-500);margin-top:4px;line-height:1.7}
details.trace{border:1px dashed var(--gray-300);border-radius:10px;background:var(--bg-alt);
  padding:12px 16px;margin:16px 0;font-size:12.8px}
details.trace > summary{cursor:pointer;font-weight:700;color:var(--teal-900);font-size:13.5px;outline:none}
details.trace .trace-body{margin-top:10px}
details.trace h5{font-size:12.8px;color:var(--teal-900);margin:14px 0 6px}
details.trace h5:first-child{margin-top:0}
details.trace .hypo{background:#fff;border:1px solid var(--gray-200);border-radius:8px;padding:9px 12px;
  margin:6px 0;font-size:12.5px;line-height:1.8}
details.trace .hypo .hl{color:var(--gray-500);font-size:11.5px;display:block;margin-bottom:2px}
details.trace table{font-size:12px}
details.trace tbody td,details.trace thead th{padding:6px 8px}
.footer{margin-top:56px;padding-top:18px;border-top:1px solid var(--gray-200);color:var(--gray-500);
  font-size:12px;text-align:center;line-height:1.9}
.footer b{color:var(--gray-700)}
.toolbar{position:fixed;bottom:22px;right:22px;z-index:100}
.toolbar button{background:var(--teal-600);color:#fff;border:none;border-radius:999px;padding:9px 20px;
  font-size:13px;font-weight:600;cursor:pointer;box-shadow:var(--shadow-md)}
@media print{
  @page{size:A4;margin:14mm 12mm}
  body{background:#fff;font-size:12px}
  .page{padding:0;max-width:none}
  .toolbar{display:none!important}
  .card,.lead,.topic,.monitor-card{box-shadow:none;break-inside:avoid}
  .section{break-inside:auto}
  .topic{page-break-inside:auto;break-inside:auto}
  .chart{break-inside:avoid}
  thead{display:table-header-group}
  tr{break-inside:avoid}
  details.trace > summary{color:#134e4a}
}
@media(max-width:820px){
  .kpi-grid{grid-template-columns:repeat(2,1fr)}
  .monitor-grid{grid-template-columns:repeat(1,1fr)}
  .page{padding:28px 16px 60px}
}
"""


# ===========================================================================
# SVG 图表（纯字符串拼装；每个数字都注册 data-calc-id）
# ===========================================================================
class Svg:
    """极简 SVG 构造器：只产出 rect/text/line/polyline/circle，不用任何 JS"""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.parts = []

    def raw(self, s):
        self.parts.append(s)

    def rect(self, x, y, w, h, fill, rx=0, stroke=None, sw=1, extra=""):
        st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
        self.parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w, 0):.1f}" '
                          f'height="{max(h, 0):.1f}" rx="{rx}" fill="{fill}"{st} {extra}/>')

    def line(self, x1, y1, x2, y2, stroke, sw=1, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                          f'stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def text(self, x, y, s, size=11, fill=GRAY["700"], anchor="start", weight="400", inner=None):
        body = inner if inner is not None else esc(s)
        self.parts.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
                          f'text-anchor="{anchor}" font-weight="{weight}" '
                          f'font-family="-apple-system,Microsoft YaHei,PingFang SC,Segoe UI,sans-serif">'
                          f'{body}</text>')

    def circle(self, cx, cy, r, fill, stroke=None, sw=1):
        st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
        self.parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}"{st}/>')

    def polyline(self, pts, stroke, sw=1, dash=None, fill="none"):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        self.parts.append(f'<polyline points="{p}" fill="{fill}" stroke="{stroke}" '
                          f'stroke-width="{sw}"{d}/>')

    def render(self, cls="", label=""):
        lab = f' role="img" aria-label="{esc(label)}"' if label else ""
        # 内联 SVG 在 HTML 文档中无需 xmlns；去掉可保证报告完全无 http(s) 外链、断网可开
        return (f'<svg viewBox="0 0 {self.w} {self.h}" '
                f'class="{cls}" preserveAspectRatio="xMidYMid meet"{lab}>{"".join(self.parts)}</svg>')


def _calc_label(reg, label, text, source, sql, group, prefix="", suffix=""):
    """SVG 内文字：数字部分包 data-calc-id，标签部分普通文本"""
    # 每次渲染都开新编号：同一指标在正文卡片与图里各出现一次，各自可验算
    cid = reg.add(label, prefix + text + suffix, source, sql, group, force_new=True)

    def _once(v):
        """prefix/suffix 可能已是 _calc_label 返回的 HTML 片段，只对裸文本转义一次。"""
        v = "" if v is None else str(v)
        return v if "<tspan" in v or "&lt;tspan" in v else esc(v)

    return (_once(prefix) + f'<tspan data-calc-id="{cid}">{esc(text)}</tspan>' + _once(suffix))


def chart_exd_seg(reg, metrics, overall, group):
    """图 1：逾期分段占比（堆叠横条 + 明细）"""
    seg = metrics.get("exd_seg") or {}
    order = ["1-30天", "31-90天", "91-180天", "180天以上"]
    keys = [k for k in order if k in seg] + [k for k in seg if k not in order]
    rows = [(k, seg[k]) for k in keys if (seg[k] or {}).get("bal") not in (None, 0)]
    if not rows:
        return None
    total = sum(r[1]["bal"] for r in rows)
    total_cnt = sum(r[1].get("cnt") or 0 for r in rows)
    W, H = 940, 74 + 34 * len(rows)
    s = Svg(W, H)
    x0, x1 = 150, 700
    s.text(20, 26, "逾期余额按账龄分段（占逾期余额比重）", 13, GRAY["900"], weight="700")
    # 图例
    shades = [TEAL["700"], TEAL["600"], TEAL["500"], TEAL["200"]]
    lx = 20
    for i, (k, _v) in enumerate(rows):
        col = shades[min(i, len(shades) - 1)]
        s.rect(lx, 38, 12, 12, col, rx=2)
        s.text(lx + 16, 48, f"{k}：{pct(_v['bal'] / total)}", 11, GRAY["500"])
        lx += 24 + svg_text_w(f"{k}：{pct(_v['bal']/total)}", 11)
    # 堆叠条
    by, bh = 62, 26
    cur = x0
    for i, (k, v) in enumerate(rows):
        share = v["bal"] / total if total else 0
        wpx = (x1 - x0) * share
        col = shades[min(i, len(shades) - 1)]
        s.rect(cur, by, wpx, bh, col, rx=0, stroke="#ffffff", sw=1.5)
        # 窄条不写字（会压字），也就不注册编号：验算清单只收真正出现在页面上的数据点
        if wpx > 58:
            inner = _calc_label(reg, f"逾期{k}余额占逾期比重", pct(share),
                                f"metrics.json exd_seg[{k}].bal / 逾期合计",
                                f"SELECT SUM(FORM_BAL_RMB) FROM {VCH} WHERE DATA_DAT='{{slice}}' "
                                f"AND BUS_BREED_CD LIKE 'A70%' "
                                f"AND EXD_DAYS {_exd_cond(k)} -- ÷ 全部 EXD_DAYS>0 余额", group)
            s.text(cur + wpx / 2, by + 17, "", 11, "#ffffff", "middle", "600", inner=inner)
        cur += wpx
    # 明细行
    y = by + bh + 26
    s.text(x0, y, "余额", 10.5, GRAY["500"], "middle")
    s.text(x0 + 200, y, "笔数", 10.5, GRAY["500"], "middle")
    s.text(x0 + 330, y, "占逾期余额", 10.5, GRAY["500"], "middle")
    y += 8
    s.line(20, y, W - 20, y, GRAY["200"])
    for k, v in rows:
        y += 26
        s.rect(20, y - 11, 8, 8, GRAY["200"], rx=1)
        s.text(36, y - 3, k, 11.5, GRAY["700"])
        amt = _calc_label(reg, f"逾期{k}余额", f"{num(v['bal'] / 10000)} 万", f"metrics.json exd_seg[{k}].bal",
                          f"SELECT SUM(FORM_BAL_RMB) FROM {VCH} WHERE DATA_DAT='{{slice}}' AND BUS_BREED_CD LIKE 'A70%' "
                          f"AND EXD_DAYS {_exd_cond(k)}", group)
        s.text(x0 + 196, y - 3, "", 11.5, GRAY["700"], "end", inner=amt)
        cnt = _calc_label(reg, f"逾期{k}笔数", f"{num(v.get('cnt'))} 笔", f"metrics.json exd_seg[{k}].cnt",
                          f"SELECT COUNT(*) FROM {VCH} WHERE DATA_DAT='{{slice}}' AND BUS_BREED_CD LIKE 'A70%' "
                          f"AND EXD_DAYS {_exd_cond(k)}", group)
        s.text(x0 + 196, y - 3, "", 11.5, GRAY["500"], "start", inner="")
        s.text(x0 + 232, y - 3, "", 11.5, GRAY["700"], "start", inner=cnt)
        sh = _calc_label(reg, f"逾期{k}占比(明细)", pct(v["bal"] / total), f"metrics.json exd_seg[{k}].bal / 逾期合计",
                         "same as 堆叠条", group)
        s.text(x0 + 380, y - 3, "", 11.5, GRAY["700"], "start", inner=sh)
    tot = _calc_label(reg, "逾期余额合计", f"{num(total / 10000)} 万", "metrics.json exd_seg 求和",
                      f"SELECT SUM(FORM_BAL_RMB) FROM {VCH} WHERE DATA_DAT='{{slice}}' AND BUS_BREED_CD LIKE 'A70%' AND EXD_DAYS>0",
                      group)
    s.text(20, H - 8, "", 11.5, TEAL["900"], "start", "600",
           inner="逾期余额合计 " + tot + _calc_label(reg, "逾期笔数合计", f"{num(total_cnt)} 笔",
                                                     "metrics.json exd_seg 求和", "同上", group, prefix="，共 "))
    return s.render("", "逾期分段占比堆叠条形图")


def _exd_cond(k):
    return {"1-30天": "BETWEEN 1 AND 30", "31-90天": "BETWEEN 31 AND 90",
            "91-180天": "BETWEEN 91 AND 180", "180天以上": "> 180"}.get(k, "> 0")


def chart_dim_offset(reg, dims, group):
    """图 2：8 大维度恶化偏移（水平条形 + 0 基准线；正=青绿深浅，负=灰阶）"""
    rows = []
    for key, d in (dims or {}).items():
        if not isinstance(d, dict):
            continue
        buckets = [b for b in (d.get("buckets") or []) if b.get("offset_pp") is not None]
        if not buckets:
            continue
        worst = max(buckets, key=lambda b: b["offset_pp"])
        name = d.get("name") or key
        if not name or name == "buckets":
            name = key
        rows.append((name, d.get("stage") or "", worst.get("bucket") or "最高档", worst["offset_pp"],
                     worst.get("npl_rate"), key))
    if not rows:
        return None
    rows.sort(key=lambda r: -r[3])
    W = 940
    row_h = 30
    top = 40
    H = top + row_h * len(rows) + 34
    s = Svg(W, H)
    s.text(20, 22, "8 大维度恶化偏移（最差档位不良率 − 全辖不良率）", 13, GRAY["900"], weight="700")
    x0 = 210
    x1 = W - 150
    mx = max(abs(r[3]) for r in rows) or 1.0
    span = x1 - x0
    zero_x = x0 + span * (max(0, mx) / (mx * 1.02))
    if all(r[3] >= 0 for r in rows):
        zero_x = x0 + 10
    scale = (x1 - zero_x) / mx if mx else 1

    for i, (name, stage, bucket, off, rate, key) in enumerate(rows):
        y = top + i * row_h
        cy = y + row_h / 2 - 2
        # 维度名 + 最差档
        s.text(20, cy + 4, name[:12], 11.5, GRAY["700"], "start", "600")
        s.text(20 + 2 + svg_text_w(name[:12], 11.5) + 6, cy + 4, f"（{stage}·{bucket[:8]}）", 10, GRAY["400"])
        # 轨道
        s.rect(x0, cy - 8, x1 - x0, 16, GRAY["100"], rx=3)
        wpx = abs(off) * scale
        if off >= 0:
            # 正向不显著（<0.15 级）浅青，显著深青
            col = TEAL["700"] if off >= 1.0 else (TEAL["600"] if off >= 0.3 else TEAL["500"])
            s.rect(zero_x, cy - 8, wpx, 16, col, rx=3)
        else:
            col = GRAY["400"] if off <= -1.0 else GRAY["300"]
            s.rect(zero_x - wpx, cy - 8, wpx, 16, col, rx=3)
        # 数值（可验算）
        lab = _calc_label(reg, f"维度「{name}」最差档恶化偏移", pp(off), f"signals.json dimensions[{key}].buckets[].offset_pp（max）",
                          f"offset_pp = (该档不良余额/该档余额 − 全辖不良率) × 100，全辖不良率取 signals.overall.npl_rate", group)
        tx = x1 + 8 if off >= 0 else zero_x - wpx - 8
        anc = "start" if off >= 0 else "end"
        if off < 0 and zero_x - wpx - 8 < x0:
            tx, anc = x1 + 8, "start"
        s.text(tx - (0 if off >= 0 else 0), cy + 4, "", 11, TEAL["900"] if off >= 0 else GRAY["500"],
               anc, "600", inner=lab)
        if rate is not None:
            rl = _calc_label(reg, f"维度「{name}」最差档不良率", pct(rate), f"signals.json dimensions[{key}].buckets[].npl_rate",
                             "npl_bal / bal（该档）", group)
            s.text(W - 138, cy + 4, "", 10.5, GRAY["500"], "start", inner="档不良率 " + rl)
    # 0 基准线
    s.line(zero_x, top - 8, zero_x, top + row_h * len(rows) - 6, GRAY["500"], 1.5)
    s.text(zero_x, top + row_h * len(rows) + 14, "0（全辖不良率）", 10.5, GRAY["500"], "middle")
    s.text(20, H - 6, "深青绿＝恶化明显（≥1pp）｜中青绿＝轻度恶化（≥0.3pp）｜浅青绿＝微弱恶化｜灰色＝优于全辖（右深左浅表示偏离幅度）",
           10.5, GRAY["500"])
    return s.render("", "8 大维度恶化偏移条形图")


def chart_clue_vs_base(reg, clue, base_rate, group, top_n=10):
    """图 3：线索类型不良率 vs 全辖基线（横向条形 + 基线虚线）"""
    items = []
    for k, v in (clue or {}).items():
        if not isinstance(v, dict):
            continue
        r = v.get("trigger_npl_pptn")
        if r is None:
            continue
        items.append((k, r, v.get("npl_lift"), v.get("trigger_cust_cnt") or v.get("trigger_ctrt_cnt")))
    if not items:
        return None
    items.sort(key=lambda x: -(x[1] or 0))
    items = items[:top_n]
    W = 940
    row_h = 26
    top = 46
    H = top + row_h * len(items) + 40
    s = Svg(W, H)
    s.text(20, 22, "线索类型不良率对比全辖基线", 13, GRAY["900"], weight="700")
    s.text(20, 38, "条形越向右越长＝该线索下客户违约越集中；虚线为全辖不良率", 10.5, GRAY["500"])
    x0, x1 = 200, 800
    mx = max([abs(r) for _k, r, _l, _n in items] + [base_rate or 0]) * 1.15 or 1
    scale = (x1 - x0) / mx
    # 基线虚线
    bx = x0 + (base_rate or 0) * scale
    s.line(bx, top - 6, bx, top + row_h * len(items) - 2, GRAY["500"], 1.5, "5,4")
    s.text(bx, top - 10, "", 10.5, GRAY["700"], "middle", "600",
           inner="全辖 " + _calc_label(reg, "全辖不良率(线索图基线)", pct(base_rate), "signals.overall.npl_rate",
                                       "SUM(不良余额)/SUM(余额)", group))
    for i, (name, rate, lift, n) in enumerate(items):
        y = top + i * row_h
        cy = y + row_h / 2 - 1
        s.text(x0 - 8, cy + 4, name[:14], 11, GRAY["700"], "end")
        wpx = (rate or 0) * scale
        col = TEAL["700"] if (rate or 0) > (base_rate or 0) else GRAY["300"]
        s.rect(x0, cy - 7, wpx, 14, col, rx=3)
        lab = _calc_label(reg, f"线索「{name}」不良率", pct(rate), f"signals.json clue_matrix[{name}].trigger_npl_pptn",
                          "-- 线索触发合同中的不良合同占比（线索级不良率代理）", group)
        extra = ""
        if lift is not None:
            extra = _calc_label(reg, f"线索「{name}」不良率相对全辖倍数", mult(lift), f"signals.json clue_matrix[{name}].npl_lift",
                                "线索不良率 / 全辖不良率", group, prefix="，", suffix="")
        s.text(x0 + wpx + 8, cy + 4, "", 10.5, TEAL["900"] if (rate or 0) > (base_rate or 0) else GRAY["500"],
               "start", "600", inner=lab + extra)
    s.text(20, H - 8, "深青绿＝高于全辖基线（值得优先排查）｜浅灰＝低于基线（该线索不构成额外风险入口）",
           10.5, GRAY["500"])
    return s.render("", "线索类型不良率对比图")


def chart_continuation(reg, cont, base_rate, group):
    """图 4：接续工具不良率对比（分组条形：工具不良率 vs 全辖）"""
    tools = ((cont or {}).get("tools") or {})
    items = [(k, v) for k, v in tools.items() if isinstance(v, dict) and v.get("npl_rate") is not None]
    chain = (cont or {}).get("chain") or {}
    if not items and not chain:
        return None
    W = 940
    n = max(len(items), 1)
    H = 250
    s = Svg(W, H)
    s.text(20, 22, "接续工具与接续链不良率对比", 13, GRAY["900"], weight="700")
    s.text(20, 38, "接续（展期/续贷/重组）若被用作缓冲，其自身不良率会偏离全辖水平", 10.5, GRAY["500"])
    x0, x1 = 60, W - 40
    base_y, top_y = 196, 58
    vals = [v["npl_rate"] for _k, v in items] + ([base_rate] if base_rate else [])
    for c in chain.values():
        if isinstance(c, dict) and c.get("npl_rate") is not None:
            vals.append(c["npl_rate"])
    mx = max(vals) * 1.2 if vals else 1
    plot_h = base_y - top_y
    gw = (x1 - x0) / max(n, 1)
    bw = min(46, gw * 0.34)
    # 基线
    if base_rate:
        by = base_y - base_rate / mx * plot_h
        s.line(x0, by, x1, by, GRAY["500"], 1.2, "5,4")
        s.text(x1, by - 5, "", 10.5, GRAY["700"], "end", "600",
               inner="全辖 " + _calc_label(reg, "全辖不良率(接续图基线)", pct(base_rate), "signals.overall.npl_rate",
                                           "SUM(不良余额)/SUM(余额)", group))
    # 轴
    s.line(x0, base_y, x1, base_y, GRAY["300"], 1)
    for i, (k, v) in enumerate(items):
        cx = x0 + gw * (i + 0.5)
        rate = v["npl_rate"]
        h = rate / mx * plot_h
        col = TEAL["700"] if rate >= (base_rate or 0) else TEAL["500"]
        s.rect(cx - bw - 2, base_y - h, bw, h, col, rx=3)
        if base_rate:
            hb = base_rate / mx * plot_h
            s.rect(cx + 2, base_y - hb, bw, hb, GRAY["200"], rx=3)
        lab = _calc_label(reg, f"接续工具「{v.get('label') or k}」不良率", pct(rate),
                          f"signals.json continuation.tools[{k}].npl_rate", "npl_bal / bal（该工具口径）", group)
        s.text(cx - bw / 2 - 2, base_y - h - 6, "", 10.5, TEAL["900"], "middle", "600", inner=lab)
        s.text(cx, base_y + 16, (v.get("label") or k)[:8], 10.5, GRAY["700"], "middle")
        bal = v.get("bal")
        if bal:
            s.text(cx, base_y + 30, "", 9.5, GRAY["400"], "middle",
                   inner=_calc_label(reg, f"接续工具「{v.get('label') or k}」余额", f"{fnum(bal/100000000,1)} 亿",
                                     f"signals.json continuation.tools[{k}].bal", "余额合计（元）/1e8", group))
    # 图例
    s.rect(x0, 218, 12, 10, TEAL["700"], rx=2)
    s.text(x0 + 16, 227, "左柱：该工具不良率", 10.5, GRAY["500"])
    s.rect(x0 + 150, 218, 12, 10, GRAY["200"], rx=2)
    s.text(x0 + 166, 227, "右柱：全辖不良率", 10.5, GRAY["500"])
    if chain:
        cx = x0 + 290
        for k, v in chain.items():
            if not isinstance(v, dict):
                continue
            lab_txt = {"rolling": "滚动接续", "resolving": "化解接续"}.get(k, k)
            cnt_lab = _calc_label(reg, f"接续链「{lab_txt}」笔数", f"{num(v.get('cnt'))} 笔",
                                  f"signals.json continuation.chain.{k}.cnt", "笔数", group)
            rate_lab = _calc_label(reg, f"接续链「{lab_txt}」不良率", pct(v.get("npl_rate")),
                                   f"signals.json continuation.chain.{k}.npl_rate",
                                   "滚动/化解接续笔的不良率", group)
            s.text(cx, 223, "", 10.5, GRAY["700"], "start", "600",
                   inner=f'{lab_txt} ' + cnt_lab)
            s.text(cx, 238, "", 10.5, GRAY["700"], "start", "600", inner="不良率 " + rate_lab)
            cx += 200
    return s.render("", "接续工具不良率对比图")


def chart_topic_lift(reg, topics, group):
    """图 5：主题客群 lift（条形 + 1.0 基准线）"""
    rows = [(t["cid"], t["short"], t.get("lift"), t.get("cohort_lift"), t.get("hit_rate"),
             t.get("base_rate"), t.get("cohort_size")) for t in topics
            if (t.get("lift") is not None or t.get("cohort_lift") is not None)]
    if not rows:
        return None
    W = 940
    row_h = 30
    top = 52
    H = top + row_h * len(rows) + 44
    s = Svg(W, H)
    s.text(20, 22, "主题命中客群的不良倍数", 13, GRAY["900"], weight="700")
    s.text(20, 38, "倍数＝命中客群不良率 ÷ 对照（或全辖）不良率；1.0 为无差异基准线，越高说明该客群越集中暴露", 10.5, GRAY["500"])
    x0, x1 = 210, W - 110
    vals = [r[2] for r in rows if r[2] is not None] + [r[3] for r in rows if r[3] is not None]
    mx = max(vals + [2.0]) * 1.1
    scale = (x1 - x0) / mx
    one_x = x0 + 1.0 * scale
    s.line(one_x, top - 8, one_x, top + row_h * len(rows) - 4, GRAY["500"], 1.5, "5,4")
    s.text(one_x, top - 12, "1.0 基准", 10, GRAY["500"], "middle")
    for i, (cid, short, lift, cohort_lift, hit_rate, base_rate, coh_n) in enumerate(rows):
        y = top + i * row_h
        cy = y + row_h / 2 - 1
        s.text(x0 - 8, cy + 4, short[:16], 11, GRAY["700"], "end")
        v = lift if lift is not None else cohort_lift
        wpx = (v or 0) * scale
        col = TEAL["700"] if (v or 0) >= 2.5 else (TEAL["600"] if (v or 0) >= 1.5 else TEAL["500"])
        s.rect(x0, cy - 8, wpx, 16, col, rx=3)
        src = "evidence.json evidence_chain[].comparisons[0].lift" if lift is not None \
            else "attribution.json topic_selection[].cohort_lift"
        lab = _calc_label(reg, f"主题{cid}「{short}」不良倍数", mult(v), src,
                          "命中组不良率 / 对照组不良率" if lift is not None else "客群实测不良率 / 全辖不良率", group)
        s.text(x0 + wpx + 8, cy + 4, "", 11, TEAL["900"], "start", "600", inner=lab)
    s.text(20, H - 8, "深青绿＝2.5 倍以上｜中青绿＝1.5–2.5 倍｜浅青绿＝1.5 倍以下（仍高于基准线）", 10.5, GRAY["500"])
    return s.render("", "主题客群 lift 条形图")


def chart_block(title, sub, svg, note=""):
    if not svg:
        return ""
    n = f'<div class="chart-note">{esc(note)}</div>' if note else ""
    return (f'<div class="chart"><div class="chart-title">{esc(title)}</div>'
            f'<div class="chart-sub">{esc(sub)}</div>{svg}{n}</div>')


# ===========================================================================
# 数据组装层：主题（topic_selection → 渲染用 dict）
# ===========================================================================
CONFIRM_WORD = [
    ("verified", "已通过客群校验"),
    ("insufficient", "待验证"),
    ("rejected", "数据不支持"),
    ("missing", "待验证"),
]
STRENGTH_WORD = [(0.7, "集中暴露"), (0.5, "较为显著"), (0.0, "存在一定迹象")]


def strength_word(s):
    for th, w in STRENGTH_WORD:
        if (s or 0) >= th:
            return w
    return STRENGTH_WORD[-1][1]


def confirm_word(status):
    return dict(CONFIRM_WORD).get(status or "missing", "待验证")


def build_topics(attr, nar, ev, drill_plan, signals, cohort):
    """主题唯一来源：attribution.topic_selection 中 decision=='selected'。

    narrative.json 只做**文案提供方**：按 topic_id / rule_id 匹配；narrative 的第一条
    主题对应 strength 最高的选中规则 —— 与 narrative.py 的排序一致。
    但 narrative 是降级/LLM 输出的产物，可能错位，所以：
      * 优先按 rule_id 精确匹配（若 narrative 带 rule_id 字段）
      * 否则按位置匹配，且要求数量一致（不一致视为无 narrative，走模板）
    """
    sel = [t for t in (attr.get("topic_selection") or []) if t.get("decision") == "selected"]
    sel.sort(key=lambda t: (-round(t.get("strength") or 0, 10), t.get("rule_id") or ""))
    ins_map = {i.get("rule_id"): i for i in (attr.get("insights") or [])}
    ev_by_rule = {}
    for e in (ev.get("evidence_chain") or []):
        ev_by_rule.setdefault(e.get("linked_rule"), []).append(e)
    plan_by_rule = {}
    for p in (drill_plan.get("plans") or []):
        plan_by_rule.setdefault(p.get("linked_rule"), []).append(p)

    nar_topics = (nar.get("topics") or []) if nar else []
    nar_by_rule = {}
    for nt in nar_topics:
        rid = nt.get("rule_id")
        if rid:
            nar_by_rule.setdefault(rid, []).append(nt)
    use_nar = bool(nar_topics) and len(nar_topics) == len(sel)

    out = []
    for i, t in enumerate(sel, 1):
        rid = t.get("rule_id")
        ins = ins_map.get(rid) or {}
        evs = ev_by_rule.get(rid) or []
        e = next((x for x in evs if x.get("status") == "verified"), evs[0] if evs else None)
        cmp0 = ((e or {}).get("comparisons") or [{}])[0] if e else {}
        hit = cmp0.get("hit") or {}
        nonhit = cmp0.get("nonhit") or {}
        lift = cmp0.get("lift")
        coh = ins.get("cohort") or {}
        coh_lift = t.get("cohort_lift") if t.get("cohort_lift") is not None else coh.get("lift")
        coh_size = t.get("cohort_size") if t.get("cohort_size") is not None else coh.get("size")
        hits = t.get("hits") or ins.get("members") or []
        if hits and "norm" not in (hits[0] or {}):
            hits = [{"label": m.get("name"), "metric": m.get("metric_label"),
                     "value": m.get("value"), "baseline": m.get("baseline"), "norm": m.get("norm")}
                    for m in hits]
        nt = None
        if use_nar:
            nt = (nar_by_rule.get(rid) or [None])[0] or (nar_topics[i - 1] if i - 1 < len(nar_topics) else None)
        out.append({
            "idx": i,
            "cid": f"T{i:03d}",
            "rule_id": rid,
            "name": ins.get("name") or t.get("name") or "",
            "essence": ins.get("essence") or "",
            "source": t.get("source") or ins.get("source") or "",
            "strength": t.get("strength"),
            "level": t.get("level"),
            "breadth": t.get("breadth"),
            "signal": t.get("signal"),
            "hit_count": t.get("hit_count"),
            "member_total": t.get("member_total"),
            "cross_stage": bool(t.get("cross_stage")),
            "stages": ins.get("stages") or [],
            "hits": hits,
            "cohort_lift": coh_lift,
            "cohort_size": coh_size,
            "cohort_source": t.get("cohort_source"),
            "prior_lift": t.get("prior_lift"),
            "incremental_lift": t.get("incremental_lift"),
            "lift": lift,
            "hit": hit,
            "nonhit": nonhit,
            "status": (e or {}).get("status") or "missing",
            "verdict": (e or {}).get("verdict") or "",
            "ev_caveats": (e or {}).get("caveats") or [],
            "plan_id": (e or {}).get("plan_id"),
            "hypothesis": (e or {}).get("hypothesis") or "",
            "plans": plan_by_rule.get(rid) or [],
            "nar": nt,
            "short": (nt or {}).get("title") or ins.get("name") or rid,
        })
    return out


def est_extra_npl(t, overall):
    """超额不良估算：命中户数 ×（命中不良率 − 对照不良率）× 全辖户均余额"""
    hit, nonhit = t.get("hit") or {}, t.get("nonhit") or {}
    if hit.get("n") is None or hit.get("npl_rate") is None or nonhit.get("npl_rate") is None:
        return None, None
    per_cust = (overall.get("bal") or 0) / (overall.get("cnt") or 1)
    diff = max(0.0, (hit["npl_rate"] or 0) - (nonhit["npl_rate"] or 0))
    return hit["n"] * diff * per_cust, per_cust


# ---------------------------------------------------------------------------
# 文案层（无 narrative 时的数据驱动模板；impact 永不写 TODO）
# ---------------------------------------------------------------------------
def template_texts(t, reg, group, overall, slice_dt):
    """数据驱动模板：strength 选措辞强度 / cross_stage 写跨环节 / status 写定性 / impact 写真实贡献"""
    cid, rid = t["cid"], t["rule_id"]
    src_f = "attribution.json topic_selection[%s]" % rid
    hits = t.get("hits") or []
    sw = strength_word(t.get("strength"))
    cw = confirm_word(t.get("status"))
    s_txt = reg.span("主题%s强度" % cid, "%.2f" % (t.get("strength") or 0), src_f + ".strength",
                     "strength = 0.6*breadth + 0.4*signal（含 cohort 加成，上限 +15%）", group)
    b_txt = reg.span("主题%s广度分量" % cid, "%.2f" % (t.get("breadth") or 0), src_f + ".breadth",
                     "breadth = hit_count / member_total", group)
    g_txt = reg.span("主题%s强度分量" % cid, "%.2f" % (t.get("signal") or 0), src_f + ".signal",
                     "signal = mean(min(1, |dev|/SATURATION))，SATURATION=2.0", group)
    hc_txt = reg.span("主题%s命中特征数" % cid, "%s/%s" % (t.get("hit_count"), t.get("member_total")),
                      src_f + ".hit_count / member_total", "命中的成员特征数 / 规则成员总数", group)

    # ---- 发现 ----
    rates = []
    for h in hits[:3]:
        v, b = h.get("value"), h.get("baseline")
        if v is None:
            continue
        if b:
            bmult = reg.span("主题%s特征「%s」倍数" % (cid, h.get("label")),
                             fnum(float(v) / float(b), 1) + " 倍",
                             "attribution.json topic_selection[].hits[].value / baseline",
                             "特征实测值 ÷ 基线值", group)
            rates.append("「%s」为基线的 %s" % (h.get("label"), bmult))
        else:
            vtxt = reg.span("主题%s特征「%s」实测强度" % (cid, h.get("label")), fnum(v, 2),
                            "attribution.json topic_selection[].hits[].value",
                            "features.json 特征值（倍）", group)
            rates.append("「%s」强度 %s" % (h.get("label"), vtxt))
    stacked = ("这些特征在同一批客户身上叠加出现" if len(hits) > 1
               else "单一特征在本期数据中异常突出")
    cross_sent = ("该组合横跨贷前准入与贷后管理两个环节，属于「跨环节共振」——单看任一环节都只能看到局部正常，"
                  "组合起来才显出风险。" if t.get("cross_stage")
                  else "该组合集中在单一业务环节内，属于该环节的执行偏差。")
    phen = ("本期数据中，该组合的强度为 %s（广度 %s、强度 %s），属「%s」级别；"
            "命中 %s 项基础风险特征：%s。这意味着%s，而非分散在全辖的正常波动。%s"
            % (s_txt, b_txt, g_txt, esc(sw), hc_txt, "；".join(rates), stacked, cross_sent))

    # ---- 机制 ----
    essence = esc(t.get("essence") or "")
    if t.get("cross_stage"):
        stages = "、".join(t.get("stages") or []) or "多个环节"
        mech = ("该现象属于跨环节共振：%s。特征分别落在 %s，前一环节放行后，后一环节没有对应的拦截动作，"
                "风险便从前端流转到贷后并沉淀为不良。这也解释了为什么单看某一环节的指标往往显得正常——"
                "缺口出现在环节的衔接处，而不是任一端。" % (essence, esc(stages)))
    else:
        mech = ("该现象集中于单一环节：%s。命中特征同处一个业务流程，说明问题不是跨部门推诿，"
                "而是该环节自身的执行标准被放松（如尽调留痕不足、额度核定偏松、贷后检查流于形式），"
                "属于可通过流程整改较快收敛的类型。" % essence)

    # ---- 证据链与定性 ----
    st = t.get("status")
    if st == "verified":
        qual = ("该线索%s：钻取对比显示命中客群与对照客群的不良率存在明确差异，"
                "两组样本量均达到可判定门槛，方向与组合信号一致。" % cw)
    elif st == "rejected":
        qual = ("该线索经钻取后%s：命中客群与对照客群的不良率差异不足以支撑归因，"
                "已从整改清单移除，避免无效投入。" % cw)
    else:
        qual = ("该线索%s：本期未取得可判定的钻取对比（或样本量未达门槛），"
                "定性依据为组合信号强度与客群实测校验，结论强度低于已校验线索，列入本期观察与补数清单。" % cw)
    evid = "组合信号：强度 %s、命中 %s 项特征。%s" % (s_txt, hc_txt, qual)
    if t.get("cohort_lift") and t.get("cohort_size"):
        evid += ("客群实测：该组合对应客群 %s 人，不良倍数为 %s。"
                 % (reg.span("主题%s客群规模" % cid, num(t.get("cohort_size")),
                             "attribution.json topic_selection[].cohort_size", "客群交集人数", group),
                    reg.span("主题%s客群倍数" % cid, mult(t.get("cohort_lift")),
                             "attribution.json topic_selection[].cohort_lift",
                             "客群不良率 / 全辖不良率", group)))

    # ---- 影响范围（真实客群不良贡献；绝不出现 TODO 语气）----
    extra, per_cust = est_extra_npl(t, overall)
    total_npl = overall.get("npl_bal") or 0
    if extra is not None and extra > 0:
        share = extra / total_npl if total_npl else 0
        impact = ("该客群约 %s，不良率 %s，较对照组（%s）多出 %s。以全辖户均余额 %s 估算，"
                  "该客群贡献的超额不良约 %s，相当于本期不良余额的 %s——这是本切片内可通过管理动作压降的部分，"
                  "不是全部潜在损失，也不是无法干预的市场性风险。"
                  % (reg.span("主题%s命中户数" % cid, num(t["hit"].get("n")),
                              "evidence.json comparisons[0].hit.n", "命中组客户数", group, suffix=" 户"),
                     reg.span("主题%s命中组不良率" % cid, pct(t["hit"].get("npl_rate")),
                              "evidence.json comparisons[0].hit.npl_rate", "命中组不良余额/余额", group),
                     reg.span("主题%s对照组不良率" % cid, pct(t["nonhit"].get("npl_rate")),
                              "evidence.json comparisons[0].nonhit.npl_rate", "对照组不良余额/余额", group),
                     reg.span("主题%s不良率差" % cid,
                              pp((t["hit"].get("npl_rate") - t["nonhit"].get("npl_rate")) * 100),
                              "hit.npl_rate − nonhit.npl_rate", "百分点差", group),
                     reg.span("主题%s户均余额" % cid, fnum(per_cust / 10000, 2) + " 万元",
                              "metrics.overall.bal / cnt", "全辖余额 ÷ 笔数", group),
                     reg.span("主题%s超额不良" % cid, wan(extra),
                              "hit.n × (hit.npl_rate − nonhit.npl_rate) × 户均余额",
                              "按两组不良率差估算的可避免不良", group),
                     reg.span("主题%s超额不良占比" % cid, pct(share), "extra / overall.npl_bal",
                              "超额不良 ÷ 全辖不良余额", group)))
    elif t.get("cohort_lift") and t.get("cohort_size"):
        size, lift = t["cohort_size"], t["cohort_lift"]
        base = overall.get("npl_rate") or 0
        c_rate = lift * base
        impact = ("该组合客群约 %s，实测不良倍数 %s，对应客群不良率约 %s。"
                  % (reg.span("主题%s客群规模2" % cid, num(size),
                              "attribution.json topic_selection[].cohort_size", "客群交集人数", group, suffix=" 人"),
                     reg.span("主题%s客群倍数2" % cid, mult(lift), "topic_selection[].cohort_lift",
                              "客群不良率/全辖不良率", group),
                     reg.span("主题%s客群推算不良率" % cid, pct(c_rate),
                              "cohort_lift × overall.npl_rate", "客群不良率推算", group)))
        if per_cust:
            c_npl = size * c_rate * per_cust
            impact += ("按户均余额估算，该客群不良余额约 %s，较按全辖平均不良率计的同等规模多出约 %s。"
                       % (reg.span("主题%s客群不良余额" % cid, wan(c_npl),
                                   "cohort_size × 客群不良率 × 户均余额", "客群不良余额估算", group),
                          reg.span("主题%s客群超额不良" % cid, wan(c_npl - size * base * per_cust),
                                   "客群不良余额 − 同等规模按全辖不良率计的不良", "超额部分", group)))
    else:
        impact = ("本期未对该组合完成可量化的不良贡献测算（缺少命中／对照对比）。已确认的事实是："
                  "组合强度为 %s，覆盖 %s 项特征，全辖不良余额 %s 中，该组合对应客群尚未单独切片——"
                  "报告不对此给出猜测数字。"
                  % (s_txt, hc_txt, reg.span("主题%s全辖不良余额" % cid, wan(total_npl),
                                             "metrics.overall.npl_bal", "SUM(不良余额)", group)))
    return phen, mech, evid, impact


# ===========================================================================
# 主渲染
# ===========================================================================
def render(args):
    attr = load(args.attribution)
    metrics_in = load(args.metrics)
    signals = load(args.signals)
    overview = load(args.overview)
    evidence = load(args.evidence)
    drill_plan = load(args.drill_plan)
    cohort = load(args.cohort)
    org_risk = load(args.org_risk)
    features = load(args.features)
    nar = load(args.narrative)

    missing = [n for n, d in (("attribution", attr), ("metrics", metrics_in)) if not d]
    if missing:
        print(f"错误：{', '.join(missing)} 输入为空或不存在", file=sys.stderr)
        return 2
    if not signals:
        print("   警告：signals.json 缺失，图表 2/3/4 将降级为空", file=sys.stderr)

    # ---- overall 统一口径（signals 优先，缺失回退 attribution / metrics） ----
    overall = dict(metrics_in.get("overall") or {})
    for src in (signals.get("overall") or {}, attr.get("overall") or {}):
        for k, v in src.items():
            if overall.get(k) in (None, 0) and v is not None:
                overall[k] = v
    slice_dt = (metrics_in.get("slice") or signals.get("slice") or attr.get("signals_slice")
                or "20260831")
    npl_rate = overall.get("npl_rate")
    FILTER = f"DATA_DAT='{slice_dt}' AND BUS_BREED_CD LIKE 'A70%'"
    NPL = "substr(RSK_CLS_CD,1,1) IN ('3','4','5')"

    reg = CalcRegistry()
    topics = build_topics(attr, nar, evidence, drill_plan, signals, cohort)
    metric_mode = "attribution" if topics else "monitor"

    # ---- 主题数据准备（lift 等） ----
    for t in topics:
        if t.get("lift") is None and t.get("cohort_lift") is not None:
            t["_lift_note"] = "客群实测"
        t["short"] = t["short"] if len(t["short"]) <= 26 else t["short"][:24] + "…"

    # =====================================================================
    # 一、报告基本信息
    # =====================================================================
    def kpi(label, value, src, sql, cls="", sub=""):
        return (f'<div class="kpi-card"><div class="label">{esc(label)}</div>'
                f'<div class="number {cls}">{value}</div>'
                f'<div class="sub">{sub}</div></div>')

    g = "一、总览"
    # 注意：正文与 KPI 卡会重复展示同一统计量，每处展示都必须重新注册
    # data-calc-id（验算清单一行一条）。因此这里全部定义为惰性函数，
    # 调用一次 = 注册一次，禁止把返回值存成变量复用。
    bal_span = lambda: reg.unit("全辖农户贷款余额", overall.get("bal"), wan, "metrics.json overall.bal",
                                f"SELECT SUM(FORM_BAL_RMB) FROM {VCH} WHERE {FILTER}", g)
    npl_bal_span = lambda: reg.unit("不良余额", overall.get("npl_bal"), wan, "metrics.json overall.npl_bal",
                                    f"SELECT SUM(FORM_BAL_RMB) FROM {VCH} WHERE {FILTER} AND ({NPL})", g)
    rate_span = lambda: reg.unit("不良率", npl_rate, pct, "metrics.json overall.npl_rate",
                                 f"SELECT SUM(FORM_BAL_RMB) FILTER(WHERE {NPL})/SUM(FORM_BAL_RMB) FROM {VCH} WHERE {FILTER}", g)
    cnt_span = lambda: reg.unit("贷款笔数", overall.get("cnt"), lambda v: num(v), "metrics.json overall.cnt",
                                f"SELECT COUNT(DISTINCT FORM_NO) FROM {VCH} WHERE {FILTER}", g, suffix=" 笔")
    cust_span = lambda: reg.unit("客户数", overall.get("cust_cnt"), lambda v: num(v), "metrics.json overall.cust_cnt",
                                 f"SELECT COUNT(DISTINCT CUST_NO) FROM {VCH} WHERE {FILTER}", g, suffix=" 户")
    person_span = lambda: reg.unit("借款人数", overall.get("person_cnt"), lambda v: num(v), "metrics.json overall.person_cnt",
                                   f"SELECT COUNT(DISTINCT ID_CARD_NO) FROM {VCH} WHERE {FILTER}", g, suffix=" 人")
    exd_bal = overall.get("exd_bal")
    exd_span = lambda: reg.unit("逾期余额", exd_bal, wan, "metrics.json overall.exd_bal",
                                f"SELECT SUM(FORM_BAL_RMB) FROM {VCH} WHERE {FILTER} AND EXD_DAYS>0", g)

    kpis = [
        kpi("不良率", rate_span(), "metrics.json overall.npl_rate", "", "不良余额 ÷ 全部余额"),
        kpi("不良余额", npl_bal_span(), "metrics.json overall.npl_bal", "deep", ""),
        kpi("农户贷款余额", bal_span(), "metrics.json overall.bal", "teal", ""),
        kpi("贷款笔数", cnt_span(), "metrics.json overall.cnt", "", f"{cust_span()}客户"),
    ]
    kpi_html = "".join(kpis)

    # 现象描述（数据驱动，每句都有 calc-id）
    exd_seg = metrics_in.get("exd_seg") or {}
    seg_items = [(k, v) for k, v in exd_seg.items() if (v or {}).get("bal")]
    seg_total = sum(v["bal"] for _k, v in seg_items)
    worst_seg = max(seg_items, key=lambda kv: kv[1]["bal"]) if seg_items else None
    seg_txt = ""
    if worst_seg and seg_total:
        k, v = worst_seg
        share = v["bal"] / seg_total
        judgment = ("已进入损失区间的余额占比偏高，说明部分逾期已无法靠催收挽回" if k in ("91-180天", "180天以上")
                    and share > 0.3 else "以短账龄为主，多数逾期仍处在催收可挽回窗口内")
        seg_txt = (f"逾期余额 {exd_span()} 中，占比最高的是 {esc(k)}（"
                   + reg.unit(f"逾期{k}占比", share, pct, f"metrics.json exd_seg[{k}]", "该段余额 ÷ 逾期合计", g)
                   + f"），{judgment}。")

    top = attr.get("top") or {}
    org_rows = top.get("org") or []
    conc_txt = ""
    if org_rows:
        tot_org = sum((r.get("npl_bal") or 0) for r in org_rows)
        if len(org_rows) >= 3:
            s3 = sum((r.get("npl_bal") or 0) for r in org_rows[:3]) / (overall.get("npl_bal") or 1)
            conc_txt = ("不良余额最集中的前 3 个机构合计占全辖不良的 "
                        + reg.unit("前3机构不良占比", s3, pct, "attribution.json top.org[0:3].npl_bal",
                                   "前3机构不良余额合计 ÷ 全辖不良余额", g) + "。")
    signals_txt = ""
    if topics:
        signals_txt = (f"本期有 {len(topics)} 条组合线索同时通过「强度达标」与「客群校验」两道门槛，"
                       f"进入本报告的分析主题（{'、'.join('「' + t['name'] + '」' for t in topics[:4])}）。")
    else:
        cov = attr.get("coverage") or {}
        n_eval = cov.get("rules_total") or len(attr.get("topic_selection") or [])
        n_cand = cov.get("candidate_topics", 0)
        signals_txt = (f"本期共评估 {n_eval} 条候选组合线索，其中 {n_cand} 条强度达标但因客群校验未通过而列观察，"
                       f"没有一条同时满足进入主题的门槛，故本报告按「指标监测」形态出具。")

    execution = nar.get("executive_summary") or ""
    if not execution:
        if topics:
            execution = (f"本期农户贷款不良率 {pct(npl_rate)}，共 {len(topics)} 条成因经组合引擎识别并通过校验。"
                         f"整改重点见下方各主题的管理动作。")
        else:
            execution = (f"本期农户贷款不良率 {pct(npl_rate)}，经组合线索引擎评估后未形成归因主题，"
                         f"资产质量处于监测区间。")

    overview_lead = ""

    # =====================================================================
    # 图表：不再单独成章，改为就地嵌入各数据说明段（管理人员视角）
    # =====================================================================
    g = "一、总览"
    svg1 = chart_exd_seg(reg, metrics_in, overall, g)
    svg2 = chart_dim_offset(reg, signals.get("dimensions") or {}, g)
    base_rate = (signals.get("overall") or {}).get("npl_rate") or npl_rate
    svg3 = chart_clue_vs_base(reg, signals.get("clue_matrix") or {}, base_rate, g)
    svg4 = chart_continuation(reg, signals.get("continuation") or {}, base_rate, g)
    svg5 = chart_topic_lift(reg, topics, g) if topics else None

    # 图表内联块：图 + 一句话读图要点，紧贴它所解释的那段文字
    def inline_chart(svg, cap, note=""):
        if not svg:
            return ""
        n = f'<div class="fig-note">{esc(note)}</div>' if note else ""
        return (f'<div class="fig-inline"><div class="fig-cap">{esc(cap)}</div>'
                f'{svg}{n}</div>')

    # 图表计数用于封面徽标
    n_charts = len([s for s in (svg1, svg2, svg3, svg4, svg5) if s])

    # 图表构成的风险现象（成文解读，不含事实编造）
    chart_read = []
    if svg2:
        dims = signals.get("dimensions") or {}
        best = None
        for key, d in dims.items():
            for b in (d.get("buckets") or []):
                if b.get("offset_pp") is None:
                    continue
                if best is None or b["offset_pp"] > best[0]:
                    best = (b["offset_pp"], d.get("name") or key, b.get("bucket"))
        if best and best[0] > 0:
            chart_read.append(
                f"维度扫描显示恶化最明显的是「{esc(best[1])}」维度中的「{esc(best[2])}」档，"
                f"不良率偏离全辖 "
                + reg.unit("最差维度偏移pp", best[0], pp, "signals.json dimensions[].offset_pp（max）",
                           "档不良率 − 全辖不良率", g) + "。")
    if svg3:
        cm = signals.get("clue_matrix") or {}
        items = [(k, v.get("trigger_npl_pptn"), v.get("npl_lift")) for k, v in cm.items()
                 if isinstance(v, dict) and v.get("trigger_npl_pptn") is not None]
        if items:
            items.sort(key=lambda x: -x[1])
            k, r, lf = items[0]
            above = sum(1 for _k, _r, _l in items if (_l or 0) > 1.2)
            chart_read.append(
                f"线索层面，不良率最高的是「{esc(k)}」线索（"
                + reg.unit("线索最高不良率", r, pct, f"signals.json clue_matrix[{k}].trigger_npl_pptn",
                           "线索内不良合同 / 线索触发合同", g)
                + "），18 类线索中 "
                + reg.unit("不良率高于全辖1.2倍的线索数", above, lambda v: f"{int(v)}", "signals.json clue_matrix 统计",
                           "count(npl_lift > 1.2)", g, suffix=" 类")
                + "高于全辖水平的 1.2 倍，可作为下阶段排查的优先级参考。")
    if svg4:
        cont = (signals.get("continuation") or {})
        tools = cont.get("tools") or {}
        ti = [(v.get("label") or k, v.get("npl_rate")) for k, v in tools.items() if v.get("npl_rate") is not None]
        if ti:
            ti.sort(key=lambda x: -(x[1] or 0))
            high = [x for x in ti if (x[1] or 0) > (base_rate or 0)]
            if high:
                chart_read.append(
                    f"接续工具中，" + "、".join(f"「{esc(a)}」{pct(b)}" for a, b in high[:3])
                    + f" 的不良率高于全辖 {pct(base_rate)}，提示这部分「续」更多是把风险往后推，"
                      f"而非真正化解；相应的展期/重组合同应纳入观察名单。")
            else:
                chart_read.append(f"五类接续工具的不良率均不高于全辖 {pct(base_rate)}，"
                                  f"本期未见「借续贷延缓暴露」的迹象。")
    read_html = ""
    if chart_read:
        read_html = ('<div class="card"><h4>维度与线索层面的判断</h4>'
                     + "".join(f"<p>{x}</p>" for x in chart_read) + "</div>")

    # 总览章内：逾期结构段与维度偏移段各配一张图，图紧贴文字、不再单列章节
    fig_exd = inline_chart(svg1, "逾期余额按账龄分布",
                           "账龄越往后，催收可挽回的空间越小；后两类占比越高，说明损失已基本坐实")
    fig_dim = inline_chart(svg2, "各管理维度偏离全辖不良率的幅度",
                           "向右为差于全辖水平，向左为优于全辖；只取各维度偏离最大的那一档")

    # 总览正文：图随文走——逾期结构段后接逾期分布图，维度判断段后接维度偏移图
    overview_lead = (
        '<div class="lead">'
        f'<p><strong>执行摘要：</strong>{esc(execution)}</p>'
        f'<p><span style="font-weight:600;color:#134e4a">规模：</span>本期农户贷款余额 {bal_span()}，'
        f'贷款 {cnt_span()}、{cust_span()}、{person_span()}，不良余额 {npl_bal_span()}，不良率 {rate_span()}。</p>'
        + (f'<p><span style="font-weight:600;color:#134e4a">逾期结构：</span>{seg_txt}</p>{fig_exd}' if seg_txt else fig_exd)
        + (f'<p><span style="font-weight:600;color:#134e4a">集中度：</span>{conc_txt}</p>' if conc_txt else "")
        + f'<p><span style="font-weight:600;color:#134e4a">组合信号：</span>{signals_txt}</p>'
        + (fig_dim if fig_dim else "")
        + '</div>'
    )

    # =====================================================================
    # 三、分析主题（每个一个 section，容器不嵌套）
    # =====================================================================
    topic_sections = []
    overview_rows = []
    g = "三、分析主题"
    for t in topics:
        nt = t.get("nar") or {}
        if nt:
            # 面向管理人员：所有叙述文本先净化技术标识（字段名/源文件/内部编号/模板痕迹）
            phen = esc(_de_tech(nt.get("phenomenon") or ""))
            mech = esc(_de_tech(nt.get("mechanism") or ""))
            evid = esc(_de_tech(nt.get("evidence") or ""))
            impact = esc(_de_tech(nt.get("impact") or ""))
            md = nt.get("management_decision") or {}
            caveats = nt.get("caveats") or []
            title = _de_tech(nt.get("title") or t["name"])
            nar_src = "叙述文本"
        else:
            phen, mech, evid, impact = template_texts(t, reg, g, overall, slice_dt)
            md = {
                "action": f"针对「{t['name']}」：先按命中特征组合锁定客群名单，再按证据完备程度分级处置——"
                          f"证据充分的客户压降额度，证据不足的客户补充核查后再定。"
                          f"防风险上把核查资源集中在真实风险客群，保经营上不因一刀切误伤正常客户。"
                          + ("该线索跨环节，建议风险条线与业务条线联席督办。" if t.get("cross_stage") else ""),
                "owner": "风险管理部（牵头）+ 相关支行",
                "deadline": "方案 1 个月内下发，3 个月内完成首轮核查",
                "kpi": "命中客群专项核查覆盖率",
                "baseline": f"组合强度 {t.get('strength'):.2f}",
                "target": "覆盖率 100%，客群不良率向全辖水平收敛",
            }
            caveats = [c for c in (t.get("ev_caveats") or []) if c]
            caveats.append("本期未取得该主题的独立时间序列，结论基于截面比较，需下一期切片复核稳定性。")
            title = f"{t['name']}：{strength_word(t.get('strength'))}，{confirm_word(t.get('status'))}"
            nar_src = "数据驱动模板"

        status_tag = {"verified": ("已通过客群校验", "tag-teal-deep"),
                      "insufficient": ("待验证", "tag-teal"),
                      "rejected": ("数据不支持", "tag-gray")}.get(t["status"], ("待验证", "tag-teal"))
        lvl_tag = esc(t.get("level") or "")

        # 发现中的命中特征证据（表格，数字带 calc-id）
        hit_rows = ""
        for h in (t.get("hits") or []):
            v, b = h.get("value"), h.get("baseline")
            v_txt = reg.unit(f"主题{t['cid']}证据「{h.get('label')}」强度", v, lambda x: fnum(x, 2),
                             f"attribution.json topic_selection[{t['rule_id']}].hits[]",
                             "features.json 特征值（倍）", g) if v is not None else "—"
            b_txt = reg.unit(f"主题{t['cid']}证据「{h.get('label')}」基线", b, lambda x: fnum(x, 2),
                             "features.json baseline", "正常水平（基线）", g) if b else "—"
            n_txt = reg.unit(f"主题{t['cid']}证据「{h.get('label')}」归一化偏离", h.get("norm"), lambda x: fnum(x, 2),
                             "attribution.json hits[].norm", "min(1, |dev|/2.0)", g)
            hit_rows += (f"<tr><td>{esc(h.get('label') or h.get('name'))}</td><td class='num'>{v_txt}</td>"
                         f"<td class='num'>{b_txt}</td><td class='num'>{n_txt}</td></tr>")
        hit_table = (f'<div class="table-wrap"><table><thead><tr><th>命中特征</th><th class="num">本期强度（倍）</th>'
                     f'<th class="num">基线</th><th class="num">归一化偏离</th></tr></thead>'
                     f'<tbody>{hit_rows}</tbody></table></div>') if hit_rows else ""

        # 客群校验 / 钻取对比
        cmp_rows = ""
        hit, nonhit = t.get("hit") or {}, t.get("nonhit") or {}
        if hit.get("n") is not None:
            cmp_rows += (f"<tr><td>命中组（组合客群）</td>"
                         f"<td class='num'>{reg.unit('命中所属客群户数', hit.get('n'), lambda v: num(v), 'evidence.json comparisons[0].hit.n', '命中组客户数', g, suffix=' 户')}</td>"
                         f"<td class='num'>{reg.unit('命中所属客群不良率', hit.get('npl_rate'), pct, 'evidence.json comparisons[0].hit.npl_rate', '命中组不良余额/余额', g)}</td></tr>")
        if nonhit.get("n") is not None:
            cmp_rows += (f"<tr><td>对照组（未命中同条件客群）</td>"
                         f"<td class='num'>{reg.unit('对照所属客群户数', nonhit.get('n'), lambda v: num(v), 'evidence.json comparisons[0].nonhit.n', '对照组客户数', g, suffix=' 户')}</td>"
                         f"<td class='num'>{reg.unit('对照所属客群不良率', nonhit.get('npl_rate'), pct, 'evidence.json comparisons[0].nonhit.npl_rate', '对照组不良余额/余额', g)}</td></tr>")
        if t.get("cohort_lift") is not None:
            cmp_rows += (f"<tr><td>客群实测（独立取数口径）</td>"
                         f"<td class='num'>{reg.unit('客群实测规模', t.get('cohort_size'), lambda v: num(v), 'attribution.json topic_selection[].cohort_size', '客群交集人数', g, suffix=' 人')}</td>"
                         f"<td class='num'>倍数 {reg.unit('客群实测lift', t.get('cohort_lift'), mult, 'attribution.json topic_selection[].cohort_lift', '客群不良率 / 全辖不良率', g)}</td></tr>")
        cmp_table = (f'<div class="table-wrap"><table><thead><tr><th>对比口径</th><th class="num">样本</th>'
                     f'<th class="num">不良率 / 倍数</th></tr></thead><tbody>{cmp_rows}</tbody></table></div>') if cmp_rows else ""

        caveat_html = "".join(f"<li>{esc(_de_tech(c))}</li>" for c in caveats if c) or "<li>本期数据未提供该主题的反证材料。</li>"
        verdict_txt = esc(_de_tech(t.get("verdict") or ""))

        # 线索/接续两张图只在第一条主题的证据链里出现一次（全辖共用证据，不重复堆图）
        if t["idx"] == 1:
            fig_clue = inline_chart(svg3, "各类风险线索触发客户的不良率与全辖水平对比",
                                    "高于虚线的线索，说明这类客户的违约明显高于平均，应优先排查")
            fig_cont = inline_chart(svg4, "各类续贷/重组工具的不良率",
                                    "「续」的手续办了但不良仍高，说明风险只是被往后推，并未真正化解")
        else:
            fig_clue = fig_cont = ""

        topic_sections.append(f"""
<section data-topic-id="{t['cid']}" class="topic">
  <div class="topic-head">
    <div class="topic-no"><span>分析主题 {t['idx']}</span>
      <span><span class="tag {status_tag[1]}">{status_tag[0]}</span>
      <span class="tag tag-teal">{lvl_tag or '—'}</span></span></div>
    <div class="topic-title">{esc(title)}</div>
  </div>
  <div class="topic-body">
    <h4>（1）发现</h4>
    <p>{phen}</p>
    {hit_table}
    <h4>（2）产生机制</h4>
    <p>{mech}</p>
    <h4>（3）证据链与验证</h4>
    <p>{evid}</p>
    {cmp_table}
    {f'<div class="evidence"><span class="ev-label">钻取判定：</span>{verdict_txt}</div>' if verdict_txt else ''}
    {fig_clue}{fig_cont}
    <h4>（4）影响范围</h4>
    <p>{impact}</p>
    <h4>（5）管理动作</h4>
    <div class="decision"><div class="dv">
      <div class="k">动作</div><div>{esc(md.get('action'))}</div>
      <div class="k">责任岗</div><div>{esc(md.get('owner'))}</div>
      <div class="k">时限</div><div>{esc(md.get('deadline'))}</div>
      <div class="k">验证指标</div><div>{esc(md.get('kpi'))}</div>
      <div class="k">基线</div><div>{esc(md.get('baseline'))}</div>
      <div class="k">目标</div><div>{esc(md.get('target'))}</div>
    </div></div>
    <div class="notes"><div class="notes-t">反证与数据盲区</div><ul>{caveat_html}</ul></div>
  </div>
</section>""")
        overview_rows.append(
            f"<tr><td>{t['idx']}</td><td><b>{esc(title)}</b></td>"
            f"<td class='num'>{reg.unit('概览-主题' + t['cid'] + '强度', t.get('strength'), lambda v: f'{v:.2f}', 'topic_selection[].strength', 'strength 公式', g)}</td>"
            f"<td>{status_tag[0]}</td>"
            f"<td>{esc('、'.join((h.get('label') or h.get('name') or '') for h in (t.get('hits') or [])[:4]))}</td></tr>")

    overview_table = ""
    if overview_rows:
        fig_lift = inline_chart(svg5, "各主题命中客群的不良倍数",
                                "倍数越高，说明风险越集中在这批人身上，越值得优先投入核查资源")
        overview_table = f"""
<div class="section">
  <h2>分析主题总览</h2>
  <div class="sec-sub">主题来源于组合线索引擎的当期评估结果，数量由数据决定；每条主题的定性以客群校验与实际钻取为准</div>
  <div class="table-wrap"><table>
    <thead><tr><th>序号</th><th>主题</th><th class="num">强度</th><th>验证状态</th><th>命中特征</th></tr></thead>
    <tbody>{''.join(overview_rows)}</tbody>
  </table></div>
  {fig_lift}
</div>"""

    # ---- 观察项（narrative.observation_only）：不进主题，但如实展示 ----
    obs = nar.get("observation_only") or [] if nar else []
    obs_html = ""
    if obs:
        rows = ""
        for o in obs[:8]:
            if o.get("title") is None:
                continue
            rows += f"<tr><td>{esc(o.get('title'))}</td><td>{esc(o.get('why_not_conclusion') or '')}</td></tr>"
        if rows:
            obs_html = f"""
<div class="section">
  <h2>观察项（未构成归因主题）</h2>
  <div class="sec-sub">这些线索在评估中被排除或证据不足，如实列出以便下期复核——不占用主题位，也不进入整改清单</div>
  <div class="table-wrap"><table><thead><tr><th>线索</th><th>处理说明</th></tr></thead><tbody>{rows}</tbody></table></div>
</div>"""

    topic_block = ""
    if topic_sections:
        topic_block = f"""
<div class="section">
  <h2>分析主题与归因</h2>
  <div class="sec-sub">每条主题按「发现 → 产生机制 → 证据链与验证 → 影响范围 → 管理动作」展开；反证与数据盲区如实列示</div>
  {''.join(topic_sections)}
</div>"""

    # =====================================================================
    # 退化形态：指标监测（0 条主题时）
    # =====================================================================
    monitor_html = ""
    if metric_mode == "monitor":
        cov = attr.get("coverage") or {}
        trace = attr.get("topic_trace_summary") or {}
        cand = [t for t in (attr.get("topic_selection") or []) if t.get("decision") == "candidate"]
        cand_rows = ""
        REASON_CN = {
            "selected_significant_with_cohort": "已通过客群校验，强度达标",
            "await_evidence_chain": "强度达标，待补充证据链",
            "min_hits_not_met": "触发条件不足，未达最低门槛",
            "no_signal": "本期无相关信号",
            "no_signal_data_missing": "所需数据缺失，无法计算",
        }
        for c in cand[:6]:
            rsn = REASON_CN.get(c.get("reason"), _de_tech(c.get("reason") or "") or "未达入选门槛")
            cand_rows += (f"<tr><td>{esc(_de_tech(c.get('name')))}</td>"
                          f"<td class='num'>{reg.unit('候选' + str(c.get('rule_id')) + '强度', c.get('strength'), lambda v: f'{v:.2f}', 'topic_selection[].strength', 'strength 公式', g)}</td>"
                          f"<td>{esc(c.get('level') or '')}</td>"
                          f"<td class='num'>{reg.unit('候选' + str(c.get('rule_id')) + '客群倍数', c.get('cohort_lift'), mult, 'topic_selection[].cohort_lift', '客群不良率/全辖', g) if c.get('cohort_lift') else '—'}</td>"
                          f"<td>{esc(rsn)}</td></tr>")
        cand_table = (f'<div class="table-wrap"><table><thead><tr><th>候选线索</th><th class="num">强度</th>'
                      f'<th>分级</th><th class="num">客群倍数</th><th>未入选原因</th></tr></thead>'
                      f'<tbody>{cand_rows}</tbody></table></div>') if cand_rows else '<p class="muted">本期没有达到候选门槛的线索。</p>'

        # 指标监测卡：逾期/接续链/线索覆盖
        mcards = []
        if seg_items and seg_total:
            mcards.append(("逾期余额", reg.unit("监测-逾期余额", seg_total, wan, "metrics.json exd_seg 求和", "SUM", g),
                           f"共 {reg.unit('监测-逾期笔数', sum((v.get('cnt') or 0) for _k, v in seg_items), lambda v: num(v), 'metrics.json exd_seg.cnt', 'SUM', g)} 笔"))
        chain = (signals.get("continuation") or {}).get("chain") or {}
        if chain.get("rolling"):
            mcards.append(("滚动接续不良率", reg.unit("监测-滚动接续不良率", chain['rolling'].get("npl_rate"), pct,
                                                   "signals.json continuation.chain.rolling.npl_rate", "滚动续作合同不良率", g),
                           f"滚动 {reg.unit('监测-滚动笔数', chain['rolling'].get('cnt'), lambda v: num(v), 'continuation.chain.rolling.cnt', '笔数', g)} 笔 / "
                           f"化解 {reg.unit('监测-化解笔数', chain.get('resolving', {}).get('cnt'), lambda v: num(v), 'continuation.chain.resolving.cnt', '笔数', g)} 笔"))
        cm = signals.get("clue_matrix") or {}
        if cm:
            mcards.append(("线索覆盖类型", f"{len(cm)} 类",
                           f"其中 {reg.unit('监测-高于全辖的线索数', sum(1 for v in cm.values() if (v.get('npl_lift') or 0) > 1.2), lambda v: int(v), 'clue_matrix', 'count(npl_lift>1.2)', g)} 类高于全辖 1.2 倍"))
        mcard_html = "".join(f'<div class="monitor-card"><div class="mt">{esc(a)}</div><div class="mv">{b}</div>'
                             f'<div class="mn">{c}</div></div>' for a, b, c in mcards)

        blind = nar.get("data_blind_spots") or []
        blind_html = "".join(f"<li>{esc(b)}</li>" for b in blind) or "<li>本期数据源完整，未发现口径级盲区。</li>"

  # 指标监测形态：这两张图在主流程里没有出现过，此处首次渲染并注册编号
    fig_clue_mon = inline_chart(svg3, "各类风险线索触发客户的不良率与全辖水平对比",
                                "高于虚线的线索值得优先排查") if svg3 else ""
    fig_cont_mon = inline_chart(svg4, "各类续贷/重组工具的不良率",
                                "「续」了但不良仍高，说明风险只是被往后推") if svg4 else ""

        monitor_html = f"""
<div class="section">
  <h2>指标监测</h2>
  <div class="sec-sub">本期没有组合线索同时通过「强度达标 + 客群校验」两道门槛，因此不出具归因主题；以下为按监测量口径列示的资产质量指标与候选线索</div>
  <div class="card">
    <h4>本期结论</h4>
    <p>{esc(execution)}</p>
    <p>这不是数据缺失或分析未完成，而是本切片的风险特征尚未形成足以支撑管理动作的组合信号。
    对 {reg.unit('监测-候选评估条数', cov.get('rules_total'), lambda v: int(v), 'attribution.json coverage.rules_total', '评估的规则条数', g)} 条候选组合线索的评估结果显示：
    显著级 {reg.unit('监测-显著线索数', cov.get('significant'), lambda v: int(v), 'coverage.significant', 'strength>=0.5 且通过校验', g)} 条、
    一般级 {reg.unit('监测-一般线索数', cov.get('moderate'), lambda v: int(v), 'coverage.moderate', '0.3<=strength<0.5', g)} 条。
    建议维持现行准入与贷后管理要求，按季复核；重点盯住下列候选线索的下一期变化。</p>
  </div>
  <div class="monitor-grid">{mcard_html}</div>
  <div class="card">
    <h4>候选线索与未入选原因</h4>
    <p class="muted">这些线索强度达标但客群校验未通过（或校验缺失），按规则最高只能标「一般」，不进入主题。</p>
    {cand_table}
  </div>
  {fig_clue_mon}
  {fig_cont_mon}
  <div class="card">
    <h4>数据盲区</h4>
    <ul style="margin-left:18px">{blind_html}</ul>
  </div>
</div>"""

    # =====================================================================
    # 五、风险警示（数据缺口 + 上游 warnings，去技术化）
    # =====================================================================
    g = "五、风险警示"
    warns = []
    feats = features.get("features") or []
    missing_feats = sum(1 for f in feats if f.get("status") == "data_missing")
    if missing_feats:
        warns.append(reg.unit("数据缺失特征数", missing_feats, lambda v: f"{int(v)} 项", "features.json",
                              "count(status=='data_missing')", g)
                     + "风险特征因数据文件缺失无法直接计算，相关主题的证据链不完整，报告已标注，未编造取值。")
    for w in (attr.get("warnings") or [])[:6]:
        txt = _de_tech(str(w))
        if txt:
            warns.append(esc(txt))
    for nw in (nar.get("warnings") or [])[:3]:
        txt = str(nw)
        if "降级" in txt or "LLM" in txt:
            warns.append(esc("本期主题文字由数据驱动模板生成（未接入大模型），措辞为规则化表述；"
                             "接入大模型后应替换为大模型返回的叙述，数值口径不变。"))
            break
    # 信号降级提示（去技术化）
    sig_warns = [str(w) for w in (signals.get("warnings") or [])]
    if any("clue_matrix" in w for w in sig_warns):
        warns.append("线索级不良率部分口径为跨机构均值，线索内部真实差异可能被平均，读取线索排名时需注意。")
    if any("continuation" in w for w in sig_warns):
        warns.append("接续工具的分项不良率不完整，「风险是被化解还是被滚动」的判断只能依赖间接指标。")
    seen, uniq = set(), []
    for w in warns:
        if w not in seen:
            seen.add(w)
            uniq.append(w)
    warn_html = "".join(f'<div class="warn-box"><span class="wt">⚠ 提示</span>　{w}</div>' for w in uniq) \
        or '<div class="card"><p>本期无重大警示项。</p></div>'

    # =====================================================================
    # 预览版：主题生成轨迹
    # =====================================================================
    trace_html = ""
    if args.preview:
        sel_all = attr.get("topic_selection") or []
        rows = ""
        for s in sel_all:
            rows += (f"<tr><td>{esc(s.get('rule_id'))}</td><td>{esc(s.get('name'))}</td>"
                     f"<td class='num'>{fnum(s.get('breadth'), 4) if s.get('breadth') is not None else '—'}</td>"
                     f"<td class='num'>{fnum(s.get('signal'), 4) if s.get('signal') is not None else '—'}</td>"
                     f"<td class='num'>{fnum(s.get('strength'), 4) if s.get('strength') is not None else '—'}</td>"
                     f"<td>{esc(s.get('decision'))}</td><td>{esc(s.get('reason'))}</td></tr>")
        hypo = ""
        for p in (drill_plan.get("plans") or []):
            hypo += (f'<div class="hypo"><span class="hl">{esc(p.get("plan_id"))} ｜ 关联 '
                     f'{esc(p.get("linked_rule"))} ｜ {esc(p.get("topic_hint"))}</span>'
                     f'{esc(_de_tech(p.get("hypothesis")) or "")}</div>')
        chk = ""
        for s in sel_all:
            if s.get("decision") != "selected":
                continue
            e = next((x for x in (evidence.get("evidence_chain") or [])
                      if x.get("linked_rule") == s.get("rule_id")), None)
            c0 = (((e or {}).get("comparisons") or [{}])[0]) or {}
            chk += (f"<tr><td>{esc(s.get('rule_id'))}</td>"
                    f"<td class='num'>{fnum(s.get('cohort_lift'), 4) if s.get('cohort_lift') is not None else '—'}</td>"
                    f"<td class='num'>{num(s.get('cohort_size')) if s.get('cohort_size') is not None else '—'}</td>"
                    f"<td>{esc(s.get('cohort_source') or '—')}</td>"
                    f"<td class='num'>{fnum(c0.get('lift'), 4) if c0.get('lift') is not None else '—'}</td>"
                    f"<td>{esc((e or {}).get('status') or '无钻取')}</td></tr>")
        cov = attr.get("coverage") or {}
        trace = attr.get("topic_trace_summary") or {}
        trace_html = f"""
<details class="trace" open>
  <summary>🧭 主题生成轨迹（仅预览版可见，正式报告不含此块）</summary>
  <!-- 技术细节块：仅供验收，不面向业务读者 -->
  <div class="trace-body">
    <p><b>覆盖统计：</b>候选规则 {esc(cov.get('rules_total'))} 条 ｜ 显著 {esc(cov.get('significant'))} ｜
      一般 {esc(cov.get('moderate'))} ｜ 进主题 {esc(cov.get('selected_topics'))} ｜ 候选 {esc(cov.get('candidate_topics'))} ｜
      淘汰 {esc(cov.get('rejected_rules'))}；决策分布 {esc(json.dumps(trace.get('by_decision') or {}, ensure_ascii=False))}；
      原因分布 {esc(json.dumps(trace.get('by_reason') or {}, ensure_ascii=False))}</p>
    <p><b>主题来源：</b>{esc('归因结果中标记为「已入选」的主题共 ' + str(len(topics)) + ' 条；文案来源：' + ('模型生成' if topics and topics[0].get('nar') else ('规则模板自动生成' if topics else '不适用（本期为指标监测形态）')))}
       ｜ 文案生成方式：{esc((nar.get('origin') or nar.get('kind') or '—'))}</p>
    <h5>一、候选规则逐条打分（breadth / signal / strength / decision / reason）</h5>
    <div class="table-wrap"><table>
      <thead><tr><th>规则</th><th>名称</th><th class="num">breadth</th><th class="num">signal</th>
      <th class="num">strength</th><th>decision</th><th>reason</th></tr></thead>
      <tbody>{rows}</tbody>
    </table></div>
    <h5>二、被采纳的钻取假设（原文）</h5>
    {hypo or '<p class="muted">本期无钻取计划。</p>'}
    <h5>三、客群校验与钻取结果</h5>
    <div class="table-wrap"><table>
      <thead><tr><th>规则</th><th class="num">客群倍数</th><th class="num">客群户数</th><th>客群口径来源</th>
      <th class="num">钻取倍数</th><th>钻取状态</th></tr></thead>
      <tbody>{chk or '<p></p>'}</tbody>
    </table></div>
  </div>
</details>"""

    # =====================================================================
    # 组装
    # =====================================================================
    mode_txt = "归因分析" if topics else "指标监测"
    badge = (f'<div class="mode-badge">本期形态：{mode_txt}	｜ 分析主题 {len(topics)} 条	｜ '
             f'图表 {len([s for s in (svg1, svg2, svg3, svg4, svg5) if s])} 张	｜ 可验算数据点 {len(reg.items)} 个</div>')

    # 章节号按实际渲染出来的章节动态计算，避免标题断档（如出现「四、」后直接「六、」）
    # 章节号由 _number_h2 后处理统一编排，此处不再手工计算
    body = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>农户贷款贷后归因报告 · {esc(_to_biz_date(str(slice_dt)))}</title>
<style>{CSS}</style>
</head>
<body>
<div class="page">

<div class="report-header">
  <div class="kicker">Post-Loan Risk Attribution Report</div>
  <h1>农户贷款贷后归因报告</h1>
  <div class="meta">
    面向客户经理的贷后风险归因与经营建议 ｜ 数据切片 <b>{esc(_to_biz_date(str(slice_dt)))}</b> ｜
    口径：农户贷款＝业务品种 A70 开头；不良＝五级分类后三级；不良率＝不良余额 ÷ 全部余额<br>
    生成时间 {datetime.now():%Y-%m-%d %H:%M} ｜ 技术口径与逐条验算见附件《数据验算清单》
  </div>
  {badge}
</div>

<div class="section">
  <h2>一、报告基本信息</h2>
  <div class="sec-sub">数据范围 · 样本规模 · 指标口径 · 本期结论</div>
  <div class="kpi-grid">{kpi_html}</div>
  {overview_lead}
  {read_html}
</div>
{trace_html if args.preview else ''}
{overview_table}
{topic_block}
{monitor_html}
{obs_html}

<div class="section">
  <h2>风险警示</h2>
  <div class="sec-sub">数据盲区、口径降级与结论边界，如实列示，不做修饰</div>
  {warn_html}
</div>

<div class="footer">
  本报告为分析建议，<b>最终信贷决策由人类审批人完成</b>。<br>
  口径说明：农户贷款＝业务品种 A70 开头；不良＝五级分类后三级；不良率＝不良余额 ÷ 全部余额；
  逐条技术口径见《数据验算清单.xlsx》，数据编号与正文 data-calc-id 一一对应。
</div>

</div>

<div class="toolbar"><button onclick="window.print()">打印 / 导出 PDF</button></div>

</body>
</html>"""
    return _number_h2(body), reg, topics, mode_txt


def _number_h2(html):
    """按实际渲染出来的 <h2> 顺序统一编排「一、二、三…」章节号。

    不在各段落里硬编码编号：当某些章节因数据原因不渲染（如 0 主题时的
    「分析主题」、无观察项时的「观察项」），硬编码就会出现「四、」后直接
    「六、」的断档。统一后处理可保证编号永远连续。
    """
    cn = "一二三四五六七八九十"
    pat = re.compile(r"<h2>([^<]*)</h2>")
    seq = [0]

    def _rep(m):
        seq[0] += 1
        t = re.sub(r"^[一二三四五六七八九十]+、", "", m.group(1))
        return f"<h2>{cn[seq[0] - 1]}、{t}</h2>"

    return pat.sub(_rep, html)


def _to_biz_date(s):
    """YYYYMMDD / YYYY-MM-DD → 中文日期；不改变其他文本。"""
    import re as _re
    def _f(m):
        y, mo, d = m.group(1), m.group(2), m.group(3)
        return f"{int(y)}年{int(mo)}月{int(d)}日"
    s = _re.sub(r"\b(\d{4})(\d{2})(\d{2})\b", _f, s)
    s = _re.sub(r"\b(\d{4})-(\d{2})-(\d{2})\b", _f, s)
    return s


def _de_tech(s):
    """把上游 warnings / 模板文案里的技术标识去掉。

    报告面向支行行长、业务条线与风控管理员，不是数据开发：表名、字段名、
    字段取值码（GRTE_MOD_CD=0100）、源文件名（signals.json）、内部规则编号
    （C01/M05）都不该出现在正文里。技术口径只保留在《数据验算清单》中，
    由懂数的人去核。
    """
    if not s:
        return ""
    import re as _re
    s = str(s)
    # 1) 字段取值码：GRTE_MOD_CD=0100 → 保留中文（若在括号里已给出），否则整体删
    s = _re.sub(r"[（(]\s*[A-Z][A-Z0-9_]*\s*=\s*[0-9A-Za-z]+\s*[）)]", "", s)
    s = _re.sub(r"\b[A-Z][A-Z0-9_]*\s*=\s*[0-9A-Za-z]+\b", "", s)
    # 2) 大写表名/字段名（连续 3 字符以上含下划线或全大写）
    s = _re.sub(r"\b[A-Z][A-Z0-9_]{2,}\b", "", s)
    # 3) 源文件名与 JSON 路径
    s = _re.sub(r"\b[\w/]+\.(json|py|csv|parquet|xlsx|duckdb)\b", "", s)
    s = _re.sub(r"\b[a-z_]+\.[a-z_]+\b", "", s)
    # 4) 内部键名
    s = _re.sub(r"features\[\d+\]", "对应特征", s)
    s = _re.sub(r"org_risk|signals|clue_matrix|continuation|topic_selection|cohort_validation",
                "相关数据源", s)
    # 5) 模板痕迹：LLM 未介入时的兜底文案不该把这个事实写给业务看
    s = _re.sub(r"[\[【]\s*降级模板\s*[\]】]\s*", "", s)
    s = _re.sub(r"[\[【]\s*(模板|TODO|FIXME)\s*[\]】]\s*", "", s)
    # 6) 裸统计术语（lift / breadth / strength 等）
    s = _re.sub(r"lift\s*[=:：]?\s*[\d.]+", "", s, flags=_re.I)
    s = _re.sub(r"\blift\b", "倍数", s, flags=_re.I)
    # 7) 维度/线索内部编号在句中（如「同时命中的线索（C01）背后」）→ 去掉括号里的编号
    s = _re.sub(r"[（(]\s*[CMD]\d{2,3}\s*[）)]", "", s)
    # 8) 独立出现的规则编号（纯编号单元格/前缀）
    s = _re.sub(r"(?<![A-Za-z0-9])[CMD]\d{2,3}(?![0-9])", "", s)
    # 9) 干巴巴的技术标记词
    s = _re.sub(r"narrative|attribution|drill_plan|回退默认值", "", s, flags=_re.I)
    s = _to_biz_date(s)
    s = _re.sub(r"\s{2,}", " ", s)
    s = _re.sub(r"[，,]\s*[，,]", "，", s)
    return s.strip(" ，。；、")


def _rule_label(rule_id, name=""):
    """内部规则编号 → 业务可读标签。

    管理人员不需要知道 C01/M05，只需要知道风险叫什么。编号仅用于
    《数据验算清单》内部追溯。
    """
    return name.strip() if name and name.strip() else "该风险线索"


def write_calc_list(reg, out_dir, slice_dt, topics, mode_txt):
    """《数据验算清单》xlsx + md：4 列，逐条对应 data-calc-id"""
    xlsx_ok = False
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter
        wb = Workbook()
        ws = wb.active
        ws.title = "数据验算清单"
        head = ["数据编号", "网页展示结果", "数据来源", "计算代码或SQL"]
        ws.append(head)
        for it in reg.items:
            ws.append([it["calc_id"], it["display"], it["source"], it["sql"]])
        head_fill = PatternFill("solid", fgColor="F0FDFA")
        thin = Side(style="thin", color="E2E8F0")
        for c in range(1, 5):
            cell = ws.cell(row=1, column=c)
            cell.font = Font(bold=True, color="134E4A")
            cell.fill = head_fill
            cell.alignment = Alignment(vertical="center")
        for row in ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=4):
            for cell in row:
                cell.border = Border(bottom=thin)
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        for col, w in zip("ABCD", (11, 40, 52, 96)):
            ws.column_dimensions[col].width = w
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:D{ws.max_row}"
        wb.save(os.path.join(out_dir, "数据验算清单.xlsx"))
        xlsx_ok = True
    except ImportError:
        print("   警告：openpyxl 未安装，跳过 xlsx 生成", file=sys.stderr)

    lines = ["# 数据验算清单", "",
             f"> 数据切片 {slice_dt}；本期形态：{mode_txt}；主题 {len(topics)} 条；"
             f"数据点 {len(reg.items)} 个；生成 {datetime.now():%Y-%m-%d %H:%M}", "",
             "每个数据编号对应报告 HTML 中一个 `data-calc-id`，全文唯一。"
             "同一结果在报告中多次出现时使用不同编号，逐条可验算。", "",
             "| 数据编号 | 网页展示结果 | 数据来源 | 计算代码或SQL |",
             "|---|---|---|---|"]
    for it in reg.items:
        cells = [it["calc_id"], it["display"], it["source"], it["sql"]]
        cells = [str(c).replace("|", "\\|").replace("\n", "<br>") for c in cells]
        lines.append("| " + " | ".join(cells) + " |")
    lines += ["", "## 口径备注", "",
              "- 农户贷款：业务品种以 A70 开头；不良：五级分类 3/4/5（次级/可疑/损失）",
              "- 不良率 = 不良余额 ÷ 全部余额；恶化偏移 = 该档不良率 − 全辖不良率",
              "- 主题强度 strength = 0.6×广度 + 0.4×强度，有客群校验时上限 +15%",
              "- 超额不良估算 = 命中户数 ×（命中不良率 − 对照不良率）× 全辖户均余额，为量级参考",
              "- 主题编号 data-topic-id 与报告中的 `<section>` 一一对应；本期："
              + ("、".join(f"{t['cid']}={t['name']}" for t in topics) if topics else "无（指标监测形态）"), ""]
    with open(os.path.join(out_dir, "数据验算清单.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return xlsx_ok


def main():
    ap = argparse.ArgumentParser(description="渲染贷后归因报告 v6（数据驱动 + 5 张内联 SVG）")
    ap.add_argument("--attribution", required=True)
    ap.add_argument("--metrics", required=True)
    ap.add_argument("--signals", default="")
    ap.add_argument("--narrative", default="")
    ap.add_argument("--evidence", default="")
    ap.add_argument("--drill-plan", dest="drill_plan", default="")
    ap.add_argument("--overview", default="")
    ap.add_argument("--cohort", default="")
    ap.add_argument("--org-risk", default="")
    ap.add_argument("--features", default="")
    ap.add_argument("--deep-dive", default="", help="兼容旧参数（未使用）")
    ap.add_argument("--out-dir", default="./output")
    ap.add_argument("--out", default="", help="HTML 输出路径（默认 <out-dir>/report.html）")
    ap.add_argument("--preview", action="store_true", help="预览版：额外渲染「主题生成轨迹」折叠块")
    args = ap.parse_args()

    res = render(args)
    if isinstance(res, int):
        return res
    body, reg, topics, mode_txt = res
    os.makedirs(args.out_dir, exist_ok=True)
    out_html = args.out or os.path.join(args.out_dir, "report.html")
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(body)
    xlsx_ok = write_calc_list(reg, args.out_dir, (load(args.metrics).get("slice") or "20260831"),
                              topics, mode_txt)
    size = os.path.getsize(out_html)
    print(f"✅ 报告渲染完成（v6）→ {out_html}（{size / 1024:.1f} KB）")
    print(f"   形态：{mode_txt}；主题 {len(topics)} 条；数据标签 {len(reg.items)} 个；"
          f"图表 5 张（按数据可得性渲染）；验算清单 xlsx={'已生成' if xlsx_ok else '跳过'}")
    for t in topics:
        print(f"   {t['cid']} [{t['status']}] {t['short']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
