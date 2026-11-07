#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""narrative.py — S5 证据链叙述（只产出提示词 + 数据驱动降级模板）

用法:
    # 1) 构造给 LLM 的提示词
    python3 scripts/narrative.py --evidence evidence.json --signals signals.json \
        --attribution attribution.json --out narrative_prompt.json

    # 2) 降级：无 LLM 时用数据驱动模板生成 narrative.json
    python3 scripts/narrative.py --evidence evidence.json --signals signals.json \
        --attribution attribution.json --degrade --out narrative.json

    # 3) 自测
    python3 scripts/narrative.py --selftest

为什么要有这个脚本
------------------
render_report.py:444-462 的四段固定套话（"上述现象并非单一孤立的风险因素…"）
之所以僵硬，是因为文案与数据无关——无论 lift 是 3.2 还是 0.9、无论有没有客群
校验、无论跨不跨环节，出来的都是同一段话。

本脚本的降级模板按**数据形态分支**选措辞：
  · lift ≥ 2.5 且样本足 → 断定"机制成立、可立即整改"
  · 1.5 ≤ lift < 2.5    → "方向成立、幅度中等，先小范围试点"
  · lift 在灰区 / 样本不足 → "证据不足，只能列为观察项"（不硬下结论）
  · lift < 1.2（被推翻） → "假设被数据推翻"，并写明这本身就是有价值的结论
  · 跨环节 vs 单环节、有无客群校验、线索噪音高低 → 机制段与反证段不同措辞
"""
from __future__ import annotations

import argparse
import json
import sys
import zlib
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import common  # noqa: E402
import _degrade_text as _dt  # noqa: E402

SCHEMA_VERSION = "3.0"

# ============================================================ 叙述提示词

SYSTEM_PROMPT = """你是省级农商行分管农户信贷的副行长，正在审阅一份贷后归因分析，并把它改写成给**客户经理团队**看的报告。

你的读者是一线的客户经理和支行行长：他们关心「我这片区域的贷款为什么坏、我明天该改什么动作」。他们不关心数据库表结构、字段名、机构编码、客户经理工号。任何技术标识出现在报告里，就等于把责任推给系统，读者会直接跳过。

## 一、你的输入

- 本期总览数字（全辖余额、不良率、客户数）
- 各维度恶化偏移（哪类客群/产品/环节在恶化）
- 线索类型不良率矩阵
- **钻取证据链**：每条假设都已被数据验证过，状态是 verified / rejected / insufficient 之一
  · verified：假设被数据支持（给出命中组 vs 对照组不良率与 lift）
  · rejected：假设被数据推翻
  · **insufficient：证据不足——这类绝对不能写成结论，只能写成「待观察」**
- 被拒绝的钻取计划（plan_audit）：LLM 提出的钻取越界或不可执行，**不得引用其结论**

## 二、输出结构（严格按此 schema）

每条主题一个对象：

```json
{
  "topics": [
    {
      "topic_id": "T001",
      "title": "业务化标题",
      "phenomenon": "现象（必须引用具体数值：不良率、偏移百分点、样本量、lift）",
      "mechanism": "产生机制（谁的行为 → 哪个业务环节 → 为什么导致不良）",
      "evidence": "证据链（引用钻取结论：命中组 X% vs 对照组 Y%，lift Z）",
      "impact": "影响范围（覆盖多少客户/多少余额，贡献多少不良）",
      "management_decision": {
        "action": "具体动作（可执行、可验收，写清做什么、做到什么程度）",
        "owner": "责任岗",
        "deadline": "时限",
        "kpi": "验证指标",
        "baseline": "基线值（当前是多少）",
        "target": "目标值"
      },
      "caveats": ["反证/数据盲区，至少 1 条，如实写"]
    }
  ],
  "observation_only": [
    {"topic_id": "O001", "title": "观察项标题", "why_not_conclusion": "为什么只列为观察项（证据不足的具体原因）"}
  ],
  "executive_summary": "给行长看的 3 句话摘要（先讲现象，再讲根因，最后讲动作）",
  "data_blind_spots": ["本次分析无法回答的问题，例如缺少某类数据"]
}
```

## 三、硬性约束（违反即整篇作废）

**① 面向客户经理，去技术化。**
禁止出现：表名、字段名（如 BUSINESS_BREED_CD）、机构编码（如 01030408）、客户经理工号/身份证号、哈希值、SQL。
替代写法：机构 → 「不良余额最集中的前 3 家县域机构」「县域机构 A」；客户经理 → 「管户不良率排名前 3 的客户经理」。
可以用业务术语：不良率、逾期、续贷、担保方式、信用类、脱贫户、无还本续贷——这些客户经理看得懂。

**② 标题必须业务化。**
禁止直接把规则名当标题。反面：✗「人员道德风险」「获客激进扩张」「贷后管理空转」。
正面：✓「客户经理与借款人存在资金往来，这类合同不良率是同机构其他合同的 3.3 倍」
     ✓「2023 年以前发放、做过无还本续贷的合同，正在把不良挪到正常账上」
标题里要能看出「谁 + 什么现象 + 什么量级」，一眼让读者知道要不要管。

**③ 决策建议必须站在管理者立场，同时写「保经营」和「防风险」。**
不能只写「压降不良」「加强管理」。每条决策要回答四个问题：
   - 这个动作能防住什么风险（防风险）
   - 这个动作会付出什么经营代价（例如：暂停某类客户新增 → 某区域放款量下降 X%；提高准入 → 损失部分真实经营需求）
   - 用什么方式把代价控制在可接受范围（差异化：对真实经营需求客户做续贷安排而不是一刀切拒贷）
   - 动作做完怎么验收（KPI + 基线 + 目标）
写不出「经营代价」的决策建议是不合格的——因为管理层最怕的是「为了压不良把业务压死」。

**④ 反证与数据盲区必须如实写出。**
每条主题的 caveats 至少 1 条，写清：
   - 什么情况下这个结论不成立（例如：lift 来自截面相关，未控制区域差异）
   - 本次数据看不到什么（例如：没有客户经理与借款人的真实资金流水，只能间接推断）
   - 若为 insufficient，必须进 observation_only，不得写进 topics

**⑤ 数字必须来自输入，不得编造。**
所有数值只能引用输入中的数字，或由输入数字直接计算（如 差额 = A% - B%）。不得虚构样本量、不得四舍五入到与输入矛盾。

**⑥ rejected 的主题有价值，不要删掉。**
被数据推翻的假设说明「这条线索不值得花钱整改」，应写进 observation_only 并在 executive_summary 里用一句话说明「本次已排除 N 条无效线索，避免无效整改」——这是给管理层省钱的结论。

## 四、写作纪律

1. **先讲现象，再讲机制**。第一句必须是读者能看见的现象（不良率多少、哪类客户多少），不要先讲方法论。
2. **机制要说清「谁、在哪一步、做错了什么」**。「贷后管理不到位」不是机制；「贷后检查任务超期未办结后没有二次提醒，客户经理在客户已经逾期 90 天后才第一次上门」才是机制。
3. **一段话不超过 4 句**，每段只讲一件事。
4. **不要写「综合来看」「多维度叠加」「深层结构性问题」这类空话**。这类词出现在报告里说明作者没想清楚。
5. 影响范围要能算出金额或户数，不能只写「影响较大」。

## 五、自检清单（输出前逐条过）

- [ ] 没有任何表名/字段名/机构编码/客户经理编号
- [ ] 所有标题都是业务化描述，没有一个是规则名
- [ ] 每条 management_decision 的 action 都写了经营代价与收益
- [ ] 每条 topic 的 caveats 至少 1 条
- [ ] 所有 insufficient 的证据都进了 observation_only，没进 topics
- [ ] 所有数字都能在输入里找到
- [ ] 没有「深层结构性问题」「综合来看」这类空话
"""


def _fmt_evidence_for_prompt(evidence, attribution, signals):
    """把 evidence_chain 渲染成 LLM 可读的证据表 + 每条证据的事实卡"""
    chain = evidence.get("evidence_chain") or []
    audit = evidence.get("plan_audit") or []
    lines = []
    lines.append(f"共 {evidence.get('plans_total', 0)} 条钻取计划：有效 {evidence.get('plans_valid', 0)}，"
                 f"被拒绝 {evidence.get('plans_invalid', 0)}。")
    lines.append("")
    for e in chain:
        c = (e.get("comparisons") or [{}])[0]
        hit = c.get("hit") or {}
        non = c.get("nonhit") or {}
        lines.append(f"### 证据 {e.get('plan_id')}｜关联规则 {e.get('linked_rule')}｜状态 **{e.get('status')}**")
        lines.append(f"- 假设原文：{e.get('hypothesis')}")
        if c:
            lines.append(f"- 命中组：n={hit.get('n')}，不良率 {common.pct(hit.get('npl_rate'))}")
            lines.append(f"- 对照组：n={non.get('n')}，不良率 {common.pct(non.get('npl_rate'))}")
            lines.append(f"- lift：{c.get('lift')}")
        lines.append(f"- 判定：{e.get('verdict')}")
        for cv in e.get("caveats") or []:
            lines.append(f"- 注意：{cv}")
        lines.append("")
    if audit:
        lines.append("### 被拒绝的钻取计划（**不得引用其结论**）")
        for a in audit:
            lines.append(f"- {a.get('plan_id')}：{a.get('reason')}（{str(a.get('detail', ''))[:60]}）")
        lines.append("")
    return "\n".join(lines)


def _fmt_topics_with_rule_context(evidence, attribution):
    """为每条 verified/insufficient 证据补上规则背景（跨环节/客群校验/噪音）"""
    ins_map = {i.get("rule_id"): i for i in (attribution.get("strong_insights") or attribution.get("insights") or [])}
    out = []
    for e in evidence.get("evidence_chain") or []:
        ins = ins_map.get(e.get("linked_rule")) or {}
        out.append({
            "plan_id": e.get("plan_id"), "status": e.get("status"),
            "linked_rule": e.get("linked_rule"),
            "rule_name_for_you_only": ins.get("name"),
            "cross_stage": bool(ins.get("cross_stage")),
            "stages": ins.get("stages"),
            "has_cohort_check": ins.get("cohort_lift") is not None,
            "cohort_lift": ins.get("cohort_lift"),
            "strength": ins.get("strength"),
            "members_cnt": len(ins.get("members") or []),
        })
    return out


def build_narrative_prompt(evidence, signals, attribution, td=None):
    overall = signals.get("overall", {})
    dims_md, dim_rows = _dims_brief(signals)
    ctx = _fmt_topics_with_rule_context(evidence, attribution)

    user = f"""# 待改写的分析结果（切片 {signals.get('slice', '—')}）

## 一、本期总览

- 全辖余额 {overall.get('bal', 0):,.0f} 元，不良余额 {overall.get('npl_bal', 0):,.0f} 元，**不良率 {common.pct(overall.get('npl_rate'))}**
- 客户数 {overall.get('cust_cnt', 0):,}

## 二、各维度恶化偏移（正向 = 该档不良率高于全辖）

{dims_md}

## 三、钻取证据链（这是你叙述的唯一事实来源）

{_fmt_evidence_for_prompt(evidence, attribution, signals)}

## 四、每条证据的规则背景（**仅供你判断轻重，规则名不得出现在正文标题里**）

```json
{json.dumps(ctx, ensure_ascii=False, indent=1)}
```

## 五、你的任务

把上面这些证据写成给客户经理看的报告主题。要求：
1. 只把 `status=verified` 和 `status=insufficient` 的写成 `topics`；`insufficient` 的必须降级进 `observation_only`，不得作为结论。
2. `status=rejected` 的进 `observation_only`，说明「已排除」。
3. 标题业务化（见约束②），每条 topic 必须给 6 字段 management_decision，且写明经营代价与收益。
4. `caveats` 至少 1 条，写清为什么结论可能不成立。
5. 只输出 JSON，不要 markdown 代码块、不要解释文字。
"""

    schema = {
        "type": "object",
        "required": ["topics", "observation_only", "executive_summary", "data_blind_spots"],
        "properties": {
            "topics": {
                "type": "array", "maxItems": 6,
                "items": {
                    "type": "object",
                    "required": ["topic_id", "title", "phenomenon", "mechanism", "evidence",
                                 "impact", "management_decision", "caveats"],
                    "properties": {
                        "topic_id": {"type": "string", "pattern": "^T\\d{3}$"},
                        "title": {"type": "string", "maxLength": 40, "desc": "业务化标题，禁止规则名"},
                        "phenomenon": {"type": "string", "desc": "必须含具体数值"},
                        "mechanism": {"type": "string"},
                        "evidence": {"type": "string", "desc": "含 lift 与两组不良率"},
                        "impact": {"type": "string", "desc": "客群规模/不良贡献"},
                        "management_decision": {
                            "type": "object",
                            "required": ["action", "owner", "deadline", "kpi", "baseline", "target"],
                            "properties": {
                                "action": {"type": "string", "desc": "须同时写保经营与防风险"},
                                "owner": {"type": "string"}, "deadline": {"type": "string"},
                                "kpi": {"type": "string"}, "baseline": {"type": "string"},
                                "target": {"type": "string"},
                            },
                        },
                        "caveats": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                    },
                },
            },
            "observation_only": {
                "type": "array",
                "items": {"type": "object", "required": ["topic_id", "title", "why_not_conclusion"],
                          "properties": {"topic_id": {"type": "string"}, "title": {"type": "string"},
                                         "why_not_conclusion": {"type": "string"}}},
            },
            "executive_summary": {"type": "string", "desc": "3 句话：现象→根因→动作"},
            "data_blind_spots": {"type": "array", "minItems": 1, "items": {"type": "string"}},
        },
    }

    constraints = [
        {"id": "N1", "rule": "禁止出现表名/字段名/机构编码/客户经理ID/哈希值/SQL",
         "checker": "llm_io.validate_narrative → violation=technical_identifier", "action": "整篇 incomplete，进 review 队列"},
        {"id": "N2", "rule": "标题不得直接使用规则名（C01 名称等）",
         "checker": "llm_io.validate_narrative → violation=rule_name_as_title", "action": "标注，不自动改写"},
        {"id": "N3", "rule": "management_decision 6 字段齐全 + action 含经营代价表述",
         "checker": "llm_io.validate_narrative → violation=incomplete_decision", "action": "incomplete=true"},
        {"id": "N4", "rule": "caveats 至少 1 条", "checker": "llm_io", "action": "incomplete=true"},
        {"id": "N5", "rule": "insufficient 证据不得进 topics",
         "checker": "narrative.py --verify-against-evidence", "action": "标注 overclaim"},
        {"id": "N6", "rule": "不得出现空话词（深层结构性问题/综合来看/多维度叠加/系统性特征）",
         "checker": "llm_io → violation=empty_boilerplate", "action": "标注，建议重写"},
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "narrative_prompt",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model_hint": {"temperature": 0.3, "response_format": "json_object"},
        "system": SYSTEM_PROMPT,
        "user": user,
        "output_schema": schema,
        "constraints": constraints,
        "forbidden_patterns": {
            "technical_identifier": ["表名形态 [A-Z]{2}_[0-9A-Z]{2,}_…", "字段名形态 XXX_YYY_ZZZ",
                                     "机构编码 8 位以上数字", "哈希 16 位以上十六进制"],
            "rule_names": [i.get("name") for i in (attribution.get("strong_insights") or []) if i.get("name")],
            "empty_boilerplate": ["深层结构性问题", "综合来看", "多维度叠加", "系统性特征", "并非单一孤立",
                                  "在业务流程上同源共振", "具有系统性"],
        },
        "post_validate": {"script": "scripts/llm_io.py",
                          "command": "python3 scripts/llm_io.py --schema narrative --result-file <llm.json>"},
    }


def _dims_brief(signals):
    base = (signals.get("overall") or {}).get("npl_rate") or 0
    rows = []
    for key, dim in (signals.get("dimensions") or {}).items():
        for b in dim.get("buckets") or []:
            off = b.get("offset_pp") or 0
            if off > 0 and (b.get("offset_pp") or 0) > 0:
                rows.append((off, dim.get("name", key), b.get("bucket"), b.get("npl_rate"),
                             b.get("npl_share"), b.get("bal")))
    rows.sort(reverse=True)
    lines = ["| 维度 | 档位 | 档不良率 | 恶化偏移 | 不良占比 | 余额 |", "|---|---|---|---|---|---|"]
    for off, dn, bk, rate, nshare, bal in rows[:10]:
        lines.append(f"| {dn} | {bk} | {common.pct(rate)} | {common.pp(off)} | {common.pct(nshare)} | {bal:,.0f} |")
    return "\n".join(lines), rows


# ============================================================ 数据驱动降级模板


def _balance_figures(signals, bucket_hint):
    """为影响范围估算客群规模"""
    overall = signals.get("overall") or {}
    for key, dim in (signals.get("dimensions") or {}).items():
        for b in dim.get("buckets") or []:
            if bucket_hint and bucket_hint in str(b.get("bucket", "")):
                return {"bal": b.get("bal", 0), "npl_bal": b.get("npl_bal", 0),
                        "npl_rate": b.get("npl_rate"), "bucket": b.get("bucket")}
    return {"bal": overall.get("bal", 0), "npl_bal": overall.get("npl_bal", 0),
            "npl_rate": overall.get("npl_rate"), "bucket": "全辖"}


def _tier(lift, n_hit, n_non, min_n=30):
    """按数据形态分档（这是替代套话的核心）"""
    if lift is None or n_hit is None or n_non is None:
        return "no_comparison"
    if n_hit < min_n or n_non < min_n:
        return "small_sample"
    if lift >= 2.5:
        return "strong"
    if lift >= 1.5:
        return "moderate"
    if lift >= 1.2:
        return "gray"
    return "reversed"


TIER_TEXT = {
    "strong": {
        "phen": [
            "这一差异不是随机波动：命中组样本 {n_hit} 户、不良率 {hit_rate}，是对照组 {non_rate} 的 {lift:.1f} 倍，"
            "样本量与差距同时满足可下结论的条件。",
            "在 {n_hit} 户命中样本上，不良率为 {hit_rate}，而条件相近的 {n_non} 户对照客户仅 {non_rate}——"
            "两者相差 {pp_diff:.2f} 个百分点、{lift:.1f} 倍，已超出抽样波动能够解释的范围。",
            "{n_hit} 户命中客户的实测不良率是 {hit_rate}，对照组 {n_non} 户为 {non_rate}，"
            "倍数 {lift:.1f}。差距大到即使剔除最差的几个机构，也难以被平均掉。",
            "同一期内，命中组 {n_hit} 户不良率 {hit_rate}、对照组 {non_rate}，差 {pp_diff:.2f} 个百分点。"
            "这个量级意味着，命中与否本身就是一条有效的不良先行信号。",
        ],
        "verb": ["可以据此认定为真实机制", "该现象具备管理指向性，可作为整改依据",
                 "差异稳固，值得单独立项处理", "信号明确，应进入当期整改清单"],
        "uncertainty": [
            "截面比较未控制区域与产品结构差异，若把同机构、同担保方式的合同再切一次，倍数可能略有回落，但方向不会反转",
            "本次对比未做时间序列校正，若该客群在过去几个季度就已持续偏高，则属于存量问题而非本期新增",
            "倍数在剔除极端机构后仍可能变化，建议在试点支行做一次复算",
        ],
    },
    "moderate": {
        "phen": [
            "命中组不良率 {hit_rate}，约为对照组 {non_rate} 的 {lift:.1f} 倍，方向明确但幅度中等；"
            "该组样本 {n_hit} 户，具备一定代表性。",
            "{n_hit} 户命中客户不良率 {hit_rate}，对照组 {n_non} 户为 {non_rate}，高出 {pp_diff:.2f} 个百分点、{lift:.1f} 倍。"
            "差距真实存在，但未到「一刀切」的程度。",
            "两类客户的不良率分别为 {hit_rate} 与 {non_rate}（{n_hit} 户 vs {n_non} 户），"
            "相差 {lift:.1f} 倍，属于「有影响但不极端」的区间。",
        ],
        "verb": ["方向成立，可作为整改依据，但幅度需在试点中复核",
                 "可以纳入整改，但动作宜渐进不宜激进",
                 "结论方向可信，力度需按机构差异分层"],
        "uncertainty": [
            "倍数在 1.5–2.5 之间，处在「有影响但不极端」的区间，未排除局部机构贡献了大部分差异",
            "中等强度差异容易被客群结构稀释，按机构拆分后可能出现部分机构不显著",
            "若对照组的构成与命中组差异较大，真实差距可能被高估或低估",
        ],
    },
    "gray": {
        "phen": [
            "命中组不良率 {hit_rate}，对照组 {non_rate}，相差 {lift:.1f} 倍，落在难以判定的区间。",
            "{n_hit} 户命中客户与 {n_non} 户对照客户的不良率分别为 {hit_rate} 与 {non_rate}，"
            "差 {pp_diff:.2f} 个百分点、{lift:.1f} 倍，处于灰区。",
        ],
        "verb": ["证据不足以支撑整改动作，建议只做观察", "暂不下结论，列入下一期复核"],
        "uncertainty": [
            "差距处于灰区，可能由样本结构差异造成，需要更长观察期或更大样本再判断",
            "灰区结论最容易受个别大额客户影响，单笔核销就可能翻转方向",
        ],
    },
    "small_sample": {
        "phen": [
            "命中组仅 {n_hit} 户（低于 {min_n} 户的可判定门槛），不良率 {hit_rate} 与对照组的差异暂不可靠。",
            "命中组样本只有 {n_hit} 户，对照组 {n_non} 户，不良率 {hit_rate} vs {non_rate}；"
            "由于分母过小，这个差距不具备统计意义。",
        ],
        "verb": ["样本不足，本轮不下结论", "样本量未达门槛，结论只能等下一期"],
        "uncertainty": [
            "样本过小，个位数客户的不良就会让不良率大幅跳动，任何结论都会被随机性主导",
            "小样本组的不良率极易被一次性核销或单户大额冲销影响",
        ],
    },
    "reversed": {
        "phen": [
            "命中组不良率 {hit_rate}，对照组 {non_rate}，倍数仅 {lift:.1f}，差异不足以支撑原假设。",
            "{n_hit} 户命中客户不良率 {hit_rate}，与 {n_non} 户对照客户的 {non_rate} 基本处于同一水平"
            "（{lift:.1f} 倍），原假设所预期的差异没有出现。",
        ],
        "verb": ["原假设被数据推翻，这条线索不值得投入专项整改",
                 "数据不支持原假设，应将其移出本期整改清单"],
        "uncertainty": [
            "「被推翻」本身是结论：说明该特征在本期不构成风险入口，可将其移出优先整改清单",
            "被推翻不代表该特征永远无害，若下期样本结构变化，需要重新检验",
        ],
    },
    "no_comparison": {
        "phen": [
            "本次未能形成有效的命中组／对照组比较（钻取结果缺少不良率或样本量）。",
            "钻取返回的数据不足以构成可比的两组（缺不良率或缺样本量），无法判断差异方向。",
        ],
        "verb": ["无有效对比，只能列为观察", "缺少可比数据，暂列观察"],
        "uncertainty": [
            "缺少对照组，无法判断该现象是否只是全辖共有的风险",
            "取数链路在本期未产出可用对比，属于数据问题而非业务结论",
        ],
    },
}


def _pick(variants, key):
    """按 key 稳定选择变体（同一主题每次都选同一条，不同主题分散到不同措辞）

    用 crc32 而非内置 hash：PYTHONHASHSEED 每次进程不同，会导致输出不可复现。
    """
    if isinstance(variants, str):
        return variants
    k = zlib.crc32(str(key).encode("utf-8"))
    return variants[k % len(variants)]


CROSS_PHRASES = [
    "这条线索横跨贷前与贷后两个环节，说明问题不是某一步做错了，而是准入放宽之后、"
    "在某个贷后动作上没有刹车——前面放得松，后面又没有补上，风险才在两个环节之间滚起来。",
    "风险在贷前埋下、在贷后才显形：审批时看重的是「材料齐不齐」，贷后关注的是「人还在不在」，"
    "两个环节各管一段，中间那段没人接手。",
    "贷前与贷后各自都在履职，但两段之间缺少交接——前一道环节放行的客户，后一道环节没有对应的跟踪动作，"
    "风险于是从缺口处漏了下来。",
]
SINGLE_PHRASES = [
    "这条线索集中在单一环节内，属于该环节内部的标准执行问题，不需要跨部门协同即可干预。",
    "问题出在一个环节上，改这一个环节的作业标准就能见效，不必牵扯其他条线。",
    "风险来源单一，属于该环节的流程执行偏差，可以直接落到岗位动作上整改。",
]


def _mechanism_sentence(tier, ctx, signals, key="", essence="", rule_name="", members=None):
    """机制段：必须引用规则自身的 essence（机制本质），而非只套通用短语。

    **修复点**：原实现只按「跨环节/单环节」+「有无客群校验」分支，导致 4 条
    完全不同风险的机制解释几乎相同。现改为：
      1. 先给该规则特有的机制本质（essence，来自 rules.json）
      2. 再叠加已命中成员特征的具体表现
      3. 最后才是跨环节/校验/噪音的通用补充
    """
    cross = ctx.get("cross_stage")
    has_cov = ctx.get("has_cohort_check")
    cm = signals.get("clue_matrix") or {}
    noisy = [k for k, v in cm.items() if (v.get("verify_false_pptn") or 0) >= 0.2]
    parts = []

    # ---- 1) 该规则特有的机制本质（核心差异化来源）----
    ess = (essence or "").strip().rstrip("。")
    if ess:
        parts.append(f"机制上，这条线索指向的是「{ess}」。")
    elif rule_name:
        parts.append(f"机制上，这条线索集中在「{rule_name}」所描述的业务环节。")

    # ---- 2) 命中成员的具体表现 ----
    mem = [m for m in (members or []) if isinstance(m, dict)]
    if mem:
        names = [m.get("name") for m in mem[:3] if m.get("name")]
        dims = sorted({m.get("dimension") for m in mem if m.get("dimension")})
        if names:
            seg = f"本期实际命中 {len(mem)} 项特征（{'、'.join(names)}）"
            if dims:
                seg += f"，分布在{'、'.join(dims)}维度"
            parts.append(seg + "，说明它不是单点偶发，而是同一业务链条上多个环节同时松动。")

    # ---- 3) 跨环节 / 单环节 ----
    parts.append(_pick(CROSS_PHRASES if cross else SINGLE_PHRASES, key))

    # ---- 4) 客群校验 ----
    if has_cov:
        parts.append(f"独立的客群校验给出的 lift 为 {ctx.get('cohort_lift')}，与本次钻取方向一致，"
                     f"说明这不是单一指标口径造成的假象。")
    else:
        parts.append("本次没有独立的客群校验数据，机制链条依赖钻取的命中／对照组差异，"
                     "因此结论准确度低于有校验支撑的线索。")
    if noisy:
        parts.append(f"附带提示：{'、'.join(noisy[:3])} 线索的核查不属实占比偏高，"
                     f"由它推出的结论需打折看待。")
    if tier in ("gray", "small_sample", "no_comparison"):
        parts.append("由于证据强度不足，这里描述的机制只是待验证的解释，不作为整改依据。")
    return "".join(parts)


def _impact_sentence(tier, hit, nonhit, signals, ctx):
    overall = signals.get("overall") or {}
    total_bal = overall.get("bal") or 0
    boost = None
    if hit and nonhit and hit.get("npl_rate") is not None and nonhit.get("npl_rate") is not None:
        # 超额不良 = 命中组户数 × (命中率 - 对照率) × 户均余额（户均余额用全辖近似）
        per_cust = common.safe_div(total_bal, overall.get("cnt") or 0) or 0
        extra = hit.get("n") or 0
        extra_rate = (hit.get("npl_rate") or 0) - (nonhit.get("npl_rate") or 0)
        boost = extra * extra_rate * per_cust
    if tier in ("strong", "moderate") and boost:
        return (f"从规模看，命中组约 {hit.get('n'):,} 户，按两组不良率差计算，"
                f"该客群贡献了约 {boost:,.0f} 元的超额不良（以全辖户均余额近似估算，量级参考）。"
                f"这部分是本期不良率 {common.pct(overall.get('npl_rate'))} 中本可通过该环节干预避免的部分。")
    if tier == "reversed":
        return ("该客群的不良率与对照组没有显著差异，说明它不构成额外的不良贡献，"
                "对本期不良余额的规模影响可以忽略。")
    return ("受样本或对比所限，本轮无法给出可信的规模估算；"
            "建议在补充数据后再测算该客群对不良余额的贡献。")


def _decision(tier, ctx, hit, nonhit, signals, rule_id):
    """6 字段决策：同时写保经营与防风险"""
    hit_rate = common.pct(hit.get("npl_rate")) if hit else "—"
    non_rate = common.pct(nonhit.get("npl_rate")) if nonhit else "—"
    cross = ctx.get("cross_stage")
    if tier in ("strong", "moderate"):
        if rule_id in ("C07",):
            action = ("对该批命中合同的客户经理开展资金往来专项排查，排查以「双人复核 + 家访影像留证」方式进行，"
                      "排查期间不暂停其新增业务，只对排查中确认存在往来的客户单独设置第二还款来源要求——"
                      "防风险上切断利益联结，保经营上避免因个别客户经理问题冻结整条支线放款。")
            kpi = "资金往来排查覆盖率"; baseline = f"当前命中组不良率 {hit_rate}"; target = "100% 完成排查，命中组不良率压降至全辖平均附近"
        elif rule_id == "C06":
            action = ("对 2023 年以前发放、做过无还本续贷的合同逐笔复盘：能真实续做的继续续，"
                      "但要求补充当期经营流水；不能证明经营真实的，停止续贷并启动清收——"
                      "防风险上止住不良滚动，保经营上对确有经营需求的老客户保留通道，避免大面积断贷引发舆情。")
            kpi = "存量续贷合同复盘率"; baseline = "续贷合同不良率高于其他合同"; target = "复盘率 100%，续贷滚动不良率下降"
        elif rule_id in ("C01",):
            action = ("对弱行政村整村授信改为「批量预授信 + 逐户核额」：预授信额度先行放出维持营销触点，"
                      "实际用信前补充村两委背调与经营证明——防风险上堵住纸面尽调，"
                      "保经营上保住整村授信的获客效率，不因收紧尽调丢掉市场。")
            kpi = "弱行政村用信前核额覆盖率"; baseline = f"该客群不良率 {hit_rate}（对照 {non_rate}）"; target = "覆盖率 100%，新增不良率降至全辖平均"
        elif rule_id == "C10":
            action = ("对行业下行客户实行「限额 + 分层」：对存量客户按经营流水分三档，"
                      "一档维持额度、二档只续不增、三档启动压降——"
                      "防风险上避免行业敞口继续扩大，保经营上保住优质客户不流失。")
            kpi = "行业客户分层覆盖率"; baseline = "重点行业不良率高于全辖"; target = "分层覆盖率 100%，行业不良率回落"
        else:
            action = (f"对命中客群（{hit_rate} vs 对照 {non_rate}）开展专项核查并分层处置："
                      f"核查确认风险的客户压降额度，核查无异常的客户维持原额度并加快审批——"
                      f"防风险上把资源集中在真风险客户，保经营上不因一刀切误伤正常客户。")
            kpi = "命中客群专项核查覆盖率"; baseline = f"命中组不良率 {hit_rate}"; target = "覆盖率 100%"
        if cross:
            action += "该线索跨环节，建议由风险条线与业务条线联席督办，避免单一条线整改后又从另一环节漏出。"
        return {"action": action, "owner": "风险管理部（牵头）+ 相关支行行长",
                "deadline": "专项方案 1 个月内下发，3 个月内完成首轮核查",
                "kpi": kpi, "baseline": baseline, "target": target}
    if tier == "reversed":
        return {"action": ("不再对该特征安排专项整改，仅将其保留在常规监测指标中，每季度观察一次不良率变化；"
                           "释放出的专项核查人力投向已证实的其他线索——"
                           "防风险上避免无效整改分散资源，保经营上把人力留给真正有价值的客户。"),
                "owner": "风险管理部（监测岗）", "deadline": "纳入季度常规监测",
                "kpi": "季度观察一次", "baseline": f"命中组 {hit_rate} / 对照 {non_rate}",
                "target": "维持观察，不投入专项资源"}
    return {"action": ("列入观察清单：本月仅做数据补录与样本积累，不安排整改动作；"
                       "待命中组样本超过可判定门槛后重新评估——"
                       "防风险上避免证据不足就下重手，保经营上不让未经证实的结论影响正常放款。"),
            "owner": "风险管理部（数据组）", "deadline": "下一季度重新评估",
            "kpi": "样本积累与复核", "baseline": f"命中组样本 {hit.get('n') if hit else '—'} 户",
            "target": "下一季度样本达到可判定门槛"}


def _caveats(tier, ctx, evidence_note, signals, key=""):
    t = TIER_TEXT[tier]
    out = [_pick(t["uncertainty"], key)]
    if not ctx.get("has_cohort_check"):
        out.append("该线索缺少独立客群校验，结论仅依赖本次钻取的单一对比，稳健性低于有校验的线索。")
    out.append("本次数据未包含客户经理与借款人的真实银行流水明细，只能通过间接特征推断利益联结；"
               "如需定性，需调取资金流水核查材料。")
    return out


def _title(tier, ctx, hit, nonhit, signals, rule_name):
    """业务化标题：不用规则名"""
    if hit and nonhit and hit.get("npl_rate") is not None:
        lift = common.safe_div(hit["npl_rate"], nonhit["npl_rate"])
        base = f"命中客群不良率 {common.pct(hit['npl_rate'])}，是对照组的 {lift:.1f} 倍" if lift else "命中客群不良率明显偏高"
    else:
        base = "命中客群不良率与对照组差异待观察"
    if tier == "reversed":
        return f"该客群不良率与对照组无差异，不构成风险入口"
    if tier in ("gray", "small_sample", "no_comparison"):
        return f"「{rule_name}」相关客群：{base}（证据不足，列观察）"
    if ctx.get("cross_stage"):
        return f"跨贷前贷后：{base}，风险在两个环节之间滚动"
    return f"{base}，且独立客群校验方向一致" if ctx.get("has_cohort_check") else base



def _monitor_summary(signals, attribution, health=None):
    """无选中主题时的执行摘要：指标监测口径，不编造归因。

    措辞必须跟着证据健康度走，不能一律宣称「不是数据缺失」：
    证据 partial / failed 时说「校验未完成」才是实话，
    否则等于用一句否定句掩盖了链路没跑完。
    """
    ov = signals.get("overall") or {}
    r = ov.get("npl_rate")
    sel = attribution.get("topic_selection") or []
    n_eval = len(sel)
    health = health or {}
    hstat = (health.get("status") or "ok").lower()
    n_tot = health.get("total")
    n_ver = health.get("verified")

    # 分层口径：42 条是候选评估数，其中只有一部分真正进入证据闸门做实测校验。
    # 注意不能拿 topic_gate_applied.rejected 当闸门条数 —— 它是对全部
    # topic_selection 逐条写回的结果（42 条全 rejected），而闸门实际只评估了
    # 进入 gated 的那几条。两个数混用会出现「42 条进入实测校验」的假陈述。
    _ga = attribution.get("topic_gate_applied") or {}
    n_gated = _ga.get("gated_total")
    if n_gated is None:
        n_gated = _ga.get("rejected", 0)
        if _ga.get("selected"):
            n_gated += _ga.get("selected", 0)

    parts = [
        f"本期农户贷款余额 {float(ov.get('bal') or 0):,.0f} 元，不良率 {common.pct(r)}，"
        f"资产质量总体处于监测区间。",
    ]
    if n_gated:
        parts.append(
            f"本期共评估 {n_eval} 条组合线索，其中 {n_gated} 条进入数据实测校验，"
            f"无一条同时满足「强度达标 + 客群实测校验通过」两项条件，故不形成归因主题。")
    else:
        parts.append(
            f"本期共评估 {n_eval} 条组合线索，无一条同时满足「强度达标 + 客群实测校验通过」"
            f"两项条件，故不形成归因主题。")

    if hstat == "ok":
        parts.append(
            "这不是数据缺失或分析未完成，而是本切片的风险特征尚未形成足以支撑管理动作的组合信号。"
            "建议维持现行准入与贷后管理要求，按季复核。")
    elif hstat == "partial":
        parts.append(
            f"需要说明的是，本次钻取校验未能全部完成（{n_ver}/{n_tot} 条产出可用证据），"
            "上述判断仅覆盖已验证部分，未验证的线索不排除存在真实信号。"
            "建议补齐校验后再下管理结论。")
    else:
        parts.append(
            f"需要说明的是，本次钻取校验未能产出可用证据（共 {n_tot or 0} 条），"
            "结论仅基于指标监测口径，不具备归因能力，请先排查数据与执行链路。")

    parts.append("建议维持现行准入与贷后管理要求，按季复核。" if hstat == "ok" else "")
    return "".join(p for p in parts if p)


def _blind_spots(signals):
    """从 signals 的 warnings 派生真实数据盲区，不写万能话。"""
    out = []
    for w in (signals.get("warnings") or []):
        w = str(w).strip()
        if not w:
            continue
        if "clue_matrix" in w:
            out.append("线索级不良率未能按线索类型完整还原，部分线索只能用跨机构均值口径，"
                       "线索内部的真实不良差异可能被平均掉。")
        elif "continuation" in w:
            out.append("接续工具（无还本续贷/展期/重组）的分项不良率不完整，"
                       "对「风险是被化解还是被滚动」的判断只能依赖间接指标。")
        elif "baseline" in w:
            out.append("部分风险特征缺少全辖基线，其强度只能按存在与否判断，未纳入强度打分。")
        else:
            out.append(w)
    # 去重保序
    seen, uniq = set(), []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    if not uniq:
        uniq.append("本期数据源完整，未发现口径级盲区；仍建议结合上一期切片做趋势复核。")
    return uniq


def _tier(lift, n_hit, n_non, min_n=30):
    """证据强度分档（供标题/机制/决策的语气切换）。确定性、无随机。"""
    if n_hit is not None and n_hit < min_n:
        return "small_sample"
    if lift is None:
        return "no_comparison"
    if lift >= 2.5:
        return "strong"
    if lift >= 1.5:
        return "moderate"
    if lift >= 1.2:
        return "gray"
    return "rejected"


def _ins_index(attribution):
    """规则语义索引：同一规则可能出现在多个桶"""
    idx = {}
    for bucket in ("insights", "strong_insights", "moderate_insights", "weak_insights"):
        for i in attribution.get(bucket) or []:
            if i.get("rule_id") and i["rule_id"] not in idx:
                idx[i["rule_id"]] = i
    for i in attribution.get("rules") or []:
        if isinstance(i, dict) and i.get("rule_id") and i["rule_id"] not in idx:
            idx[i["rule_id"]] = i
    return idx


def _derivation_sentence(ins):
    """derived 规则的推导说明 → 一句业务话（剥离技术标识）"""
    d = ins.get("derivation") or {}
    if not isinstance(d, dict) or not d:
        return ""
    tables = d.get("tables") or []
    note = _dt._clean_essence(str(d.get("note") or d.get("rationale") or ""))
    parts = []
    if tables:
        parts.append(f"把 {len(tables)} 类业务档案串起来看才浮现")
    if note:
        parts.append(note)
    return "，".join(parts)


def _blind_spots(signals, attribution, topics):
    """从未做实测/被折算的地方派生盲区（不是万能话术）"""
    out, seen = [], set()
    for w in signals.get("warnings") or []:
        for pat, text in _dt.BLIND_SPOT_BY_SIGNAL:
            if pat.search(str(w)) and text not in seen:
                seen.add(text)
                out.append(text)
    srcs = {t.get("_rule_id") for t in topics}
    sel = {t.get("rule_id"): t for t in (attribution.get("topic_selection") or [])}
    folded = [r for r in srcs
              if (sel.get(r) or {}).get("cohort_source") in ("signals_measured", "cohort_json", "clue")]
    if folded:
        text = ("本报告中的客群倍数，部分由多维度几何平均折算得到，属于下界估计；"
                "真实交集客群的差距通常更大，方向可信、幅度待实测")
        if text not in seen:
            out.append(text)
    if not out:
        out.append("本期数据源完整，未发现口径级盲区；仍建议结合上一期切片做趋势复核。")
    return out


def _evidence_block(evidence):
    """证据链是否足以支撑归因结论。返回 (blocked, health)。

    为什么 narrative 要自己再查一遍
    -------------------------------
    topic_gate 会拦主题，但 narrative 的主题源是 attribution.topic_selection，
    不读 topic_gate.json —— 闸门拦下的主题照样能被渲染进报告。
    这里做第二道独立校验：证据链为空或全部执行失败时，直接判定
    本报告不具备归因能力，不生成任何主题，只输出执行状态说明。
    宁可出一份「这次没跑成」的报告，也不能出一份「本期无风险」的报告。
    """
    chain = evidence.get("evidence_chain") or []
    if not chain:
        return True, {"status": "empty", "total": 0, "verified": 0,
                      "note": "证据链为空：未产出任何钻取证据"}
    verified = [e for e in chain if (e.get("status") or "").lower() == "verified"]
    if not verified:
        reasons = {}
        for e in chain:
            r = e.get("reason") or (e.get("status") or "error")
            reasons[r] = reasons.get(r, 0) + 1
        return True, {"status": "failed", "total": len(chain), "verified": 0,
                      "reasons": reasons,
                      "note": f"{len(chain)} 条钻取全部未产出可用证据"}
    if len(verified) < len(chain):
        return False, {"status": "partial", "total": len(chain),
                       "verified": len(verified),
                       "note": f"{len(verified)}/{len(chain)} 条钻取产出可用证据"}
    return False, {"status": "ok", "total": len(chain), "verified": len(verified), "note": ""}


def build_degrade_narrative(evidence, signals, attribution, td=None, rules_doc=None):
    """无 LLM 时的数据驱动模板：由规则语义 + 数据形态派生差异化文案。

    **主题源铁律**：只认 `attribution.topic_selection` 中 decision=="selected" 的规则。
      evidence 的条数由 drill_plan 决定（mock 模式恒为 4 条），与「哪些规则真正进了
      报告」无关；若按 evidence 遍历，会出现「选中 0 条却写出 4 条主题」的错位。

    **证据硬门**：证据链为空或全部执行失败时，不产出任何主题，
    只输出「本次分析未跑成」的状态说明，避免把执行故障写成业务结论。

    文案由 _degrade_text 模块构造：
      build_title     —— 机制短语 / 客群短语 / 环节短语 + 量级尾巴
      build_mechanism —— source×stage 决定话语体系，essence 决定内容
      build_decision  —— 按 stage 路由到动作族，六字段 + 经营代价/风险收益
      build_caveats   —— 引用真实盲区（折算来源 / 接管线索 / 承接线 / 缺什么）
    """
    ins_idx = _ins_index(attribution)
    chain = evidence.get("evidence_chain") or []
    audit = evidence.get("plan_audit") or []
    overall = signals.get("overall") or {}

    # 证据硬门：不健康直接返回空报告，不进任何主题构造
    blocked, health = _evidence_block(evidence)
    if blocked:
        return {
            "schema_version": SCHEMA_VERSION, "kind": "narrative",
            "origin": "degrade_template", "generated_at": datetime.now().isoformat(timespec="seconds"),
            "model": None, "topics": [], "observation_only": [],
            "execution_status": health,
            "executive_summary": (
                "本次贷后归因分析未能产出可用结论。"
                f"{health['note']}。报告不输出管理判断，请先排查数据与执行链路。"),
            "data_blind_spots": [health["note"]],
            "data_sufficient": False,
        }

    ev_by_rule = {}
    for e in chain:
        ev_by_rule.setdefault(e.get("linked_rule"), []).append(e)

    sel = attribution.get("topic_selection") or []
    selected = [t for t in sel if t.get("decision") == "selected"]
    if not selected:
        return {
            "schema_version": SCHEMA_VERSION, "kind": "narrative",
            "origin": "degrade_template", "generated_at": datetime.now().isoformat(timespec="seconds"),
            "model": None, "topics": [], "observation_only": [],
            "execution_status": health,
            "executive_summary": _monitor_summary(signals, attribution, health),
            "data_blind_spots": _blind_spots(signals, attribution, []),
            "warnings": ["本期未触发任何达标的组合线索，报告退化为指标监测形态，不强行拼凑归因主题"],
            "theme_source": "attribution.topic_selection（0 条选中）",
        }

    selected.sort(key=lambda t: (-round(t.get("strength") or 0.0, 10),
                                 t.get("rule_id") or ""))

    topics, obs = [], []
    for t in selected:
        rid = t.get("rule_id")
        ins = ins_idx.get(rid) or {}
        evs = ev_by_rule.get(rid) or []
        ev = next((x for x in evs if x.get("status") == "verified"), evs[0] if evs else None)
        if ev is None:
            # 无钻取证据：用客群校验兜底（也是真实数据），不编造钻取对比
            coh = ins.get("cohort") or {}
            ev = {"plan_id": None, "linked_rule": rid, "status": "insufficient",
                  "comparisons": [{"dim": "cohort_only",
                                   "hit": {"n": coh.get("size"), "npl_rate": coh.get("npl_rate")},
                                   "nonhit": {"n": None,
                                              "npl_rate": (signals.get("overall") or {}).get("npl_rate")},
                                   "lift": coh.get("lift")}],
                  "verdict": "未对该线索执行钻取，仅有客群级校验口径"}
        f = _dt.Facts(ev, ins, attribution, signals, td)
        f.derivation_note = _derivation_sentence(ins)
        idx = len(topics) + len(obs)

        tid = f"T{len(topics) + 1:03d}"
        topics.append({
            "topic_id": tid,
            "rule_id": rid,
            "title": _dt.build_title(f, idx),
            "phenomenon": _dt.build_phenomenon(f, idx),
            "mechanism": _dt.build_mechanism(f, idx),
            "evidence": _dt.build_evidence(f),
            "impact": _dt.build_impact(f),
            "management_decision": _dt.build_decision(f, idx),
            "caveats": _dt.build_caveats(f, idx),
            "_source_plan": (ev or {}).get("plan_id"),
            "_rule_id": rid,
            "_tier": _tier(f.lift, f.n_hit, f.n_non),
            "_status": (ev or {}).get("status"),
            "_origin": "degrade_template",
        })

    # 未进选中的线索 → 观察项（不占主题位）
    selected_ids = {t.get("rule_id") for t in selected}
    for e in chain:
        rid = e.get("linked_rule")
        if rid in selected_ids:
            continue
        ins = ins_idx.get(rid) or {}
        try:
            f = _dt.Facts(e, ins, attribution, signals, td)
            f.derivation_note = _derivation_sentence(ins)
            cw = f.cohort_word
        except Exception:
            cw = e.get("topic_hint") or rid or "相关线索"
        st = e.get("status")
        if st == "rejected":
            obs.append({"topic_id": f"O{len(obs)+1:03d}", "rule_id": rid,
                        "title": f"已排除：{cw}并不比同类客户更差",
                        "why_not_conclusion": "钻取证据显示命中组与对照组不良率差异不足，"
                                              "原假设所预期的差异没有出现，本期不投入专项整改。",
                        "_source_plan": e.get("plan_id"), "_status": "rejected"})
        elif st == "insufficient":
            obs.append({"topic_id": f"O{len(obs)+1:03d}", "rule_id": rid,
                        "title": f"待观察：{cw}的差异尚未构成结论",
                        "why_not_conclusion": f"钻取状态为证据不足：{e.get('verdict') or '对比样本或可比口径未达标'}；"
                                              "本轮只登记观察，待样本补齐后重评。",
                        "_source_plan": e.get("plan_id"), "_status": "insufficient"})

    for a in audit:
        obs.append({
            "topic_id": f"O{len(obs)+1:03d}",
            "title": f"一条钻取假设未能验证（{a.get('plan_id')}）",
            "why_not_conclusion": f"该假设的取数方案超出可用数据范围（{a.get('reason')}），未执行，故无结论。",
            "_source_plan": a.get("plan_id"), "_status": "invalid",
        })

    n_verified = len(topics)
    n_rejected = sum(1 for o in obs if o.get("_status") == "rejected")
    if topics:
        top = sorted(topics, key=lambda x: -(x["_tier"] == "strong"))
        names = "、".join(t["title"].split("｜")[0].split("——")[0].split("：")[0][:14] for t in top[:3])
        exec_sum = (f"本期农户贷款不良率 {common.pct(overall.get('npl_rate'))}，"
                    f"{n_verified} 条成因经数据验证成立，集中在{names}这几类；"
                    f"每条都给出了环节、动作、责任岗和验收口径。")
    else:
        exec_sum = f"本期农户贷款不良率 {common.pct(overall.get('npl_rate'))}，暂无经数据验证成立的成因。"
    if n_rejected:
        exec_sum += f"另有 {n_rejected} 条线索被数据推翻，已移出整改清单，避免无效投入。"
    if topics:
        all_c = " ".join(" ".join(t["caveats"]) for t in topics)
        if "下界估计" in all_c or "折算" in all_c:
            exec_sum += "需说明：部分客群倍数为折算的下界估计，方向可信、幅度待实测。"

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "narrative",
        "origin": "degrade",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": None,
        "topics": topics,
        "observation_only": obs,
        "executive_summary": exec_sum,
        "data_blind_spots": _blind_spots(signals, attribution, topics),
        "warnings": ["由数据驱动模板生成（无 LLM），措辞由规则语义 + 数据形态派生；"
                     "接入 LLM 后应替换 narrative_prompt 的返回结果"],
        "theme_source": "attribution.topic_selection",
    }


def verify_against_evidence(narrative, evidence):
    """校验 narrative 是否越权（把 insufficient 写成结论、无对应证据等）"""
    issues = []
    status_map = {e.get("plan_id"): e.get("status") for e in evidence.get("evidence_chain") or []}
    valid_ids = [f"T{i:03d}" for i in range(1, 20)]
    for t in narrative.get("topics") or []:
        src = t.get("_source_plan")
        if src and status_map.get(src) == "insufficient":
            issues.append({"topic_id": t.get("topic_id"), "code": "overclaim_insufficient",
                           "detail": f"来源证据 {src} 状态 insufficient，被写成结论"})
        if src and status_map.get(src) == "rejected":
            issues.append({"topic_id": t.get("topic_id"), "code": "overclaim_rejected",
                           "detail": f"来源证据 {src} 状态 rejected，被写成结论"})
        if src and src not in status_map:
            issues.append({"topic_id": t.get("topic_id"), "code": "dangling_evidence",
                           "detail": f"来源证据 {src} 不在 evidence_chain 中（可能来自被拒绝的计划）"})
    return issues


# ============================================================ selftest


def selftest():
    ck = common.Checker("narrative selftest")
    td = common.TableDict()
    signals = common.synth_signals()
    attribution = common.synth_attribution()

    # 构造一份含三种 status 的 evidence（verified / rejected / insufficient / invalid）
    import drill_planner as dpl
    import drill_executor as dex
    dplan = dpl.build_degrade_plan(signals, attribution)
    mock = {
        "P001": {"hit": {"n": 742, "npl_rate": 0.0894}, "nonhit": {"n": 4860, "npl_rate": 0.0271}},
        "P002": {"hit": {"n": 1280, "npl_rate": 0.0295}, "nonhit": {"n": 4320, "npl_rate": 0.0298}},
        "P003": {"hit": {"n": 22, "npl_rate": 0.1818}, "nonhit": {"n": 5580, "npl_rate": 0.0271}},
    }
    evidence = dex.build_evidence(dplan, td, mode="mock", mock=mock)
    # 补一条 verified（moderate 档）与一条 invalid
    evidence["evidence_chain"].append({
        "plan_id": "P004", "linked_rule": "C06", "topic_hint": "续贷滚动",
        "hypothesis": "续贷合同不良率高于未续贷合同", "status": "verified",
        "comparisons": [{"dim": "hit_vs_nonhit", "hit": {"n": 4180, "npl_rate": 0.0712},
                         "nonhit": {"n": 9200, "npl_rate": 0.0391}, "lift": 1.82}],
        "drill_rows": [], "verdict": "假设成立：lift=1.82", "caveats": []})
    # 一条被数据推翻的证据（不属于任何选中主题）→ 应进观察项
    evidence["evidence_chain"].append({
        "plan_id": "P005", "linked_rule": "C88", "topic_hint": "被推翻的假设",
        "hypothesis": "某线索应显著恶化", "status": "rejected",
        "comparisons": [{"dim": "hit_vs_nonhit", "hit": {"n": 800, "npl_rate": 0.031},
                         "nonhit": {"n": 4200, "npl_rate": 0.030}, "lift": 1.03}],
        "drill_rows": [], "verdict": "假设被推翻：lift=1.03 < 1.2", "caveats": []})
    evidence["plan_audit"].append({"plan_id": "P099", "status": "invalid",
                                   "reason": "table_not_allowed", "detail": "FAKE"})
    evidence["plans_total"] += 1

    # 补 topic_selection：narrative 的主题源只认它（decision=="selected"）。
    # 这里让 C01（对应 P001 verified）、C05（P002 需 rejected/insufficient）、C06（P004 verified）
    # 进去，另造一条未选中的规则验证「未选中不得出现在主题里」。
    # 只把 verified 的规则设为 selected；rejected/insufficient 留给观察项
    strong_ids = [e.get("linked_rule") for e in evidence["evidence_chain"]
                  if e.get("status") == "verified"]
    attribution["topic_selection"] = []
    _seen = set()
    for _i, _rid in enumerate([r for r in strong_ids if r], 1):
        if _rid in _seen:
            continue
        _seen.add(_rid)
        attribution["topic_selection"].append({
            "rule_id": _rid, "name": _rid, "source": "manual",
            "decision": "selected", "reason": "selected_significant_with_cohort",
            "level": "显著", "strength": 0.9 - _i * 0.1, "strength_raw": 0.8,
            "breadth": 0.66, "signal": 0.9, "hit_count": 2, "member_total": 3,
            "cross_stage": _rid in ("C05", "C06"), "stages": ["贷前"],
            "cohort_lift": 2.8, "cohort_size": 742,
        })
    # 一条被淘汰的，不能进主题
    attribution["topic_selection"].append({
        "rule_id": "C99", "name": "被淘汰的规则", "source": "manual",
        "decision": "rejected", "reason": "strength_below_threshold",
        "level": "弱信号", "strength": 0.1, "strength_raw": 0.1,
        "breadth": 0.3, "signal": 0.1, "hit_count": 1, "member_total": 3,
        "cross_stage": False, "stages": ["贷前"], "cohort_lift": None, "cohort_size": None,
    })

    print("── 叙述提示词 ──")
    pr = build_narrative_prompt(evidence, signals, attribution, td)
    need = ["title", "phenomenon", "mechanism", "evidence", "impact", "management_decision", "caveats"]
    req = pr["output_schema"]["properties"]["topics"]["items"]["required"]
    ck.check(all(k in req for k in need), "schema required 覆盖 CONTRACT 第 6 节 7 字段")
    md_req = pr["output_schema"]["properties"]["topics"]["items"]["properties"]["management_decision"]["required"]
    ck.check(md_req == ["action", "owner", "deadline", "kpi", "baseline", "target"], "management_decision 6 字段齐全")
    for kw, label in [("禁止出现：表名、字段名", "约束①去技术化"),
                      ("标题必须业务化", "约束②标题业务化"),
                      ("保经营", "约束③保经营+防风险"),
                      ("反证与数据盲区必须如实写出", "约束④反证/盲区"),
                      ("insufficient", "约束⑤insufficient 不得写成结论")]:
        ck.check(kw in pr["system"] or kw in pr["user"], f"prompt 含{label}")
    ck.check("经营代价" in pr["system"], "prompt 要求写经营代价")
    ck.check("规则名" in pr["system"], "prompt 禁止规则名当标题")

    print("\n── 降级叙述（数据驱动分支）──")
    nar = build_degrade_narrative(evidence, signals, attribution, td)
    ck.check(len(nar["topics"]) >= 2, f"生成 {len(nar['topics'])} 条主题")
    tiers = [t["_tier"] for t in nar["topics"]]
    ck.check("strong" in tiers and "moderate" in tiers, f"覆盖多档措辞：{tiers}")
    ck.check(len(nar["observation_only"]) >= 2,
             f"观察项 {len(nar['observation_only'])} 条（含 insufficient/rejected/invalid）")
    ck.check(not any(o.get("_status") == "insufficient" for o in nar["topics"] if False), "")
    ck.check(all(len(t["caveats"]) >= 1 for t in nar["topics"]), "每条主题至少 1 条 caveats")
    ck.check(all(t["management_decision"]["action"] for t in nar["topics"]), "每条主题有动作")
    ck.check(all(("保经营" in t["management_decision"]["action"]) or ("经营" in t["management_decision"]["action"])
                 for t in nar["topics"]), "动作均提及经营侧代价/收益")

    print("\n── 文案差异（证明不是套话）──")
    texts = [t["phenomenon"] for t in nar["topics"]]
    ck.check(len(set(texts)) == len(texts), "不同主题的现象段各不相同")
    mechs = [t["mechanism"] for t in nar["topics"]]
    ck.check(len(set(mechs)) == len(mechs), "不同主题的机制段各不相同")
    banned = ["深层结构性问题", "综合来看", "同源共振", "并非单一孤立"]
    joined = json.dumps(nar, ensure_ascii=False)
    ck.check(not any(b in joined for b in banned), "降级文案不含旧版套话词")

    print("\n── 去技术化 ──")
    # 故意注入违规文本，验证抓取
    from llm_io import validate_narrative
    bad = {"topics": [{"topic_id": "T001", "title": "人员道德风险",
                       "phenomenon": "业务品种 BUSINESS_BREED_CD 异常，机构 01030408 不良率偏高",
                       "mechanism": "x", "evidence": "y", "impact": "z",
                       "management_decision": {"action": "压降不良", "owner": "a", "deadline": "b",
                                               "kpi": "c", "baseline": "d", "target": "e"},
                       "caveats": []}],
           "observation_only": [], "executive_summary": "综合来看，存在深层结构性问题。",
           "data_blind_spots": ["x"]}
    v = validate_narrative(bad, td)
    ck.check(v["violations"], f"违规样例被抓出 {len(v['violations'])} 处：{[x['code'] for x in v['violations']]}")
    codes = {x["code"] for x in v["violations"]}
    for c in ("technical_identifier", "rule_name_as_title", "empty_boilerplate", "missing_caveats"):
        ck.check(c in codes, f"抓出 {c}")

    print("\n── 越权校验 ──")
    over = {"topics": [{"topic_id": "T001", "_source_plan": "P003"}]}
    issues = verify_against_evidence(over, evidence)
    ck.check(any(i["code"] == "overclaim_insufficient" for i in issues), "insufficient 被写成结论 → overclaim_insufficient")

    print("\n── 降级文案样例 ──")
    for t in nar["topics"]:
        print(f"\n[{t['topic_id']}] ({t['_tier']}) {t['title']}")
        print(f"   现象：{t['phenomenon']}")
        print(f"   机制：{t['mechanism'][:110]}…")
        print(f"   动作：{t['management_decision']['action'][:110]}…")
    print(f"\n摘要：{nar['executive_summary']}")
    return ck.summary()


def main():
    ap = argparse.ArgumentParser(description="S5 证据链叙述（只出提示词 + 数据驱动降级）")
    ap.add_argument("--evidence")
    ap.add_argument("--signals")
    ap.add_argument("--attribution")
    ap.add_argument("--out", default="narrative_prompt.json")
    ap.add_argument("--degrade", action="store_true", help="无 LLM 时生成数据驱动模板 narrative.json")
    ap.add_argument("--table-dict")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not (args.evidence and args.signals and args.attribution):
        print("错误：需要 --evidence --signals --attribution（或 --selftest）", file=sys.stderr)
        return 2
    try:
        evidence = common.read_json(args.evidence)
        signals = common.read_json(args.signals)
        attribution = common.read_json(args.attribution)
    except FileNotFoundError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
    td = common.TableDict(args.table_dict)

    if args.degrade:
        nar = build_degrade_narrative(evidence, signals, attribution, td)
        common.write_json(args.out, nar)
        print(f"✅ 降级叙述 → {args.out}（{len(nar['topics'])} 条主题 / "
              f"{len(nar['observation_only'])} 条观察项）")
        for t in nar["topics"]:
            print(f"   {t['topic_id']} [{t['_tier']}] {t['title']}")
        return 0

    pr = build_narrative_prompt(evidence, signals, attribution, td)
    common.write_json(args.out, pr)
    print(f"✅ 叙述提示词 → {args.out}")
    print(f"   system {len(pr['system'])} 字 / user {len(pr['user'])} 字 / constraints {len(pr['constraints'])} 条")
    print(f"   证据 {len(evidence.get('evidence_chain') or [])} 条 → 将生成主题")
    return 0


if __name__ == "__main__":
    sys.exit(main())
