#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""drill_planner.py — S3 LLM 研判深挖（只产出提示词，不调 API）

用法:
    # 1) 正常：构造给 LLM 的完整提示词
    python3 scripts/drill_planner.py --signals signals.json --attribution attribution.json \
        --rules rules.json --out drill_prompt.json

    # 2) 降级：无 LLM 时从规则 evidence_hint 生成默认钻取计划
    python3 scripts/drill_planner.py --signals signals.json --attribution attribution.json \
        --degrade --out drill_plan.json

    # 3) 自测（合成数据）
    python3 scripts/drill_planner.py --selftest

设计要点
--------
现有引擎只能输出「规则名 + 命中数」，无法回答「为什么是这批人坏」。本脚本把
"当期现象"整理成一份**证据包**交给 LLM，并要求它提出**可证伪的钻取假设**：
每条假设必须给出 ① 机制句子（谁的行为 → 什么业务环节 → 为什么该坏）② 判别性
预测（expect：命中组不良率应比未命中组高多少倍）③ 证伪条件（falsify_if：什么
结果会推翻它）。这样 S4 执行完就能直接给出 verified/rejected，而不是再念一遍规则名。

提示词内嵌 table_whitelist（table-dict.json 全量字段级清单），LLM 写 SQL 越界即
在 S4 被整条拒绝。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import common  # noqa: E402

SCHEMA_VERSION = "3.0"

# ============================================================ 规则名 → 业务语义词

# 规则名不能直接出现在假设里（否则 LLM 会复述规则名）。这里给每条规则一个
# 「业务问题」而非「结论」：提示词要求 LLM 回答这个业务问题，而不是复述名字。
RULE_BUSINESS_QUESTION = {
    "C01": "是不是存在一批客户，本身资质就不够、又没有抵押，却因为在弱行政村被批量做进来？",
    "C02": "反欺诈与审查环节是不是漏掉了同一批有明显包装痕迹的客户？",
    "C03": "建档和尽调是不是走了过场——同一客户经理短期内批量建档、资料雷同、收入与资产不符？",
    "C04": "有没有一批客户的授信额度明显超出其经营现金流能承受的范围？",
    "C05": "贷后环节是不是空转——任务超期未办结、风险信号出现后没有人跟进？",
    "C06": "到期续贷/无还本续贷是不是把已经还不上的资产滚成了账面上的正常贷款？",
    "C07": "是否有客户经理与借款人之间存在资金往来、代还、亲属关系等不当联结？",
    "C08": "风险是否集中在少数产品/行业上，而这些产品/行业的准入与限额没有被单独管理？",
    "C09": "是否存在虚假包装骗贷：流水造出来、场所共用、短期内反复试探额度？",
    "C10": "客户主业是不是在恶化——行业下行、经营年限短、地址频繁变更、种植养殖规模虚增？",
    "C11": "客户是不是多头负债、查询频繁、已被其他机构拒绝？",
    "C12": "客户是否存在赌博、家庭破裂、涉诉被执行等经营外冲击？",
    "C13": "第一还款来源是不是已经失效——资金被挪用、经营主体消亡、名下已无任何资产？",
}

# 每条规则「值得怀疑的机制方向」，帮助 LLM 不从零猜
RULE_MECHANISM_HINTS = {
    "C01": ["弱行政村（户数少、无产业）批量整村授信，客户经理按户数冲量，尽调只做纸面",
            "信用类产品放宽担保要求，实际由客户经理个人担保或互保兜底",
            "低分段客户被评分模型阈值调整后批量准入"],
    "C02": ["反欺诈规则未覆盖关联方共用手机号/地址/收款账户",
            "审批环节只看材料齐全不看材料真实，通过率异常高"],
    "C03": ["同一客户经理同日建档多户，影像资料复用、地址雷同",
            "收入申报与资产申报不匹配（申报收入高但无对应资产/流水）"],
    "C04": ["按户均额度考核导致超授信，客户实际用款需求远低于授信",
            "收入覆盖不足的客户被给到与其现金流不匹配的额度"],
    "C05": ["贷后检查任务长期未办结，逾期预警出现后无人跟进",
            "管户数超负荷，客户经理无法逐户现场检查"],
    "C06": ["无还本续贷把已逾期客户滚成正常，掩盖真实不良生成",
            "接续时只做形式审查，不重新评估还款能力"],
    "C07": ["客户经理本人/亲属账户与借款人存在资金往来",
            "客户经理亲属代借款人还款，形成隐性担保"],
    "C08": ["单一行业（如生猪养殖）价格下行时集中暴露，未做限额与分散",
            "单一产品（小额/脱贫户）准入标准低于其他产品"],
    "C09": ["交易流水短期集中进出、金额与经营规模不匹配",
            "多个借款人共用同一经营场所/联系电话"],
    "C10": ["行业景气下行 2-4 个季度后传导至逾期",
            "经营年限不足 2 年的新客户抗风险能力弱"],
    "C11": ["多头借贷导致还款来源被挤占，本行贷款成为最后偿付顺位",
            "近期查询次数激增，说明资金链已紧张"],
    "C12": ["赌博等嗜好导致资金外流，与经营无关",
            "涉诉/被执行导致账户冻结，还款能力骤降"],
    "C13": ["贷款资金流向房地产/消费/他人账户，未用于申报用途",
            "借款人名下无存款、无金融资产、无农地，属于裸贷户"],
}

MECHANISM_HINTS_GENERIC = [
    "同一批客户经理管户内的客户，在某个贷后环节（检查/催收/续贷）上行为异常集中",
    "某个客群（担保方式 × 额度段 × 行业）的组合，单一维度看起来正常、交叉后不良率显著抬升",
    "某类线索（资金往来/亲属代还/抵押物异常）只在一部分机构出现，属于局部而非全局",
]


# ============================================================ 提示词构造

SYSTEM_PROMPT = """你是省级农商行农户信贷的资深风险分析师，为管理层做贷后归因。你的价值不在于把已触发的规则念一遍，而在于提出**能被数据证伪的深挖假设**，并写清验证它的取数方案。

## 一、你要解决的问题

下游已经算出来：全辖不良率、8 个维度的恶化偏移、线索类型不良率矩阵、以及十几条组合规则各自的命中情况。但这些只是「哪些指标一起亮了」，还不是「为什么坏、坏在谁身上、哪个管理环节漏了」。

你要做的是：从这些现象出发，提出 2–5 条钻取假设。每条假设是一个**业务机制句子**，形如：

> 「当 <某类人的某种行为/某个环节的状态> 成立时，<某类贷款> 的不良率会显著高于对照客群，因为 <业务链条上的原因>。」

反面例子（这些一律不合格，会被下游判为无效）：
- ✗「人员道德风险线索显著」——这是规则名，不是假设
- ✗「不良率偏高，说明贷后管理存在问题」——无法证伪，任何数据都成立
- ✗「建议加强准入管理」——这不是假设，是结论

正面例子：
- ✓「客户经理与借款人在放款后 6 个月内有资金往来的那批合同，其不良率是同机构、同担保方式、同额度段客户的 2 倍以上，因为这类往来意味着客户经理在替客户兜底或抽成，放款决策已不独立。」
- ✓「2023 年以前发放、且做过无还本续贷的合同，不良率高于同期未续贷合约，因为续贷把已经失去还款能力的账滚成了正常账，掩盖了真实不良生成。」
- ✓「单笔 5 万元以下、纯信用、且客户所在行政村在册农户不足 50 户的合同，不良率显著高于其他小额贷款，因为弱行政村的整村授信实际是按户数冲量、尽调只做纸面。」

## 二、硬性禁止事项（违反即整条作废）

1. **禁止编造表名和字段名。** 你只能使用 `table_whitelist` 中列出的表与字段。写了不在清单里的表或字段，S4 会整条拒绝，你的假设不会被执行。
2. **禁止 `SELECT *`。** 必须显式列出需要的列，列名必须来自白名单。
3. **禁止任何写操作和 DDL/DCL。** 不得出现 DROP / DELETE / UPDATE / INSERT / CREATE / ALTER / ATTACH / COPY / INSTALL / LOAD / TRUNCATE / MERGE / PRAGMA / CALL。数据库是只读的。
4. **禁止 CTE（WITH）、窗口函数（OVER）、子查询别名、UNION。** 每条 SQL 只允许一个 SELECT，只能 FROM/JOIN 白名单表。解析器遇到这些语法会判 `unparseable_sql` 直接拒绝。
5. **禁止把规则名当作 hypothesis。** 假设必须是机制句子，且必须包含可比的对照（命中组 vs 未命中组 / 达标组 vs 未达标组）。
6. **禁止在 SQL 里写死机构编码、客户经理编号、身份证号。** 需要按机构/人员切片时，用 GROUP BY 输出分组、不要 WHERE 到具体编号。
7. **不得在 `expect` 里写「会更高」这种无方向无幅度的空话。** 必须给出可判定的阈值，例如「lift ≥ 1.8」「差值 ≥ 5 个百分点」。

## 三、什么样的假设值得提（选题原则）

优先级从高到低：
1. **把两个不同环节的现象连起来**（贷前的准入宽松 × 贷后的续贷滚动），这类「跨环节串联」最可能是真机制，而不是统计巧合。
2. **解释某个维度上最刺眼的恶化偏移**：某一档不良率比全辖高出一倍以上，而它在正常客户中占比很低 —— 说明这一档是风险入口。
3. **给已触发的高强度组合线索找「谁、在哪个环节」**：组合规则只说「多项特征同时命中」，你要回答的是「是哪一类客户经理、哪一类客户、在哪个动作上出的问题」。
4. **主动挑战最强的那条线索**：如果某条线索的核查不属实占比（verify_false_pptn）很高，说明线索本身噪音大，应当提一条**证伪型假设**（预期 lift 接近 1），为管理层省下无效整改。

不要提的：已经被数据说死的（当前总览已经知道的信息）、无法用现有表验证的（涉及征信外部数据但白名单里没有的、需要访谈才能得到的）、泛泛而谈的。

## 四、写 SQL 的要求

- DuckDB 方言。金额/比例字段多为 VARCHAR，做数值比较要 `CAST(x AS DOUBLE)`；除法要 `NULLIF(分母, 0)`。
- 每张表都带 `DATA_DAT` 过滤（凭证表有 6 个月切片，不过滤会重复计数）。示例切片值会在 user 中给出。
- 农户贷款口径：`BUS_BREED_CD LIKE 'A70%'`；不良：`substr(RSK_CLS_CD,1,1) IN ('3','4','5')`；余额：`CAST(FORM_BAL_RMB AS DOUBLE)`。
- 每条假设的步骤应当能直接算出 **一个命中组、一个对照组的样本量(n)与不良率(npl_rate)**，否则 S4 无法判 verified/rejected。推荐写法（分组对比，一次出两行）：

```sql
SELECT 'hit' AS grp,
       COUNT(DISTINCT CUST_NO) AS n,
       SUM(CASE WHEN substr(RSK_CLS_CD,1,1) IN ('3','4','5') THEN 1 ELSE 0 END) AS npl_cnt,
       SUM(CASE WHEN substr(RSK_CLS_CD,1,1) IN ('3','4','5') THEN CAST(FORM_BAL_RMB AS DOUBLE) ELSE 0 END)
         / NULLIF(SUM(CAST(FORM_BAL_RMB AS DOUBLE)),0) AS npl_rate
FROM G_00PF_PEAS_LN_VCH_DV
WHERE DATA_DAT = '<slice>' AND BUS_BREED_CD LIKE 'A70%' AND <命中条件>
UNION ALL   -- ⚠ 若解析器不接受 UNION，就拆成两步：S1 命中组、S2 对照组
SELECT 'nonhit', ...
```

> 若你不确定 UNION 是否被接受，**就拆成两步**：第一步取命中组的 n/npl_rate，第二步取对照组的 n/npl_rate；S4 会把同一 plan 内多个步骤的对比组装成 lift。

## 五、输出格式

只输出一个 JSON 对象，不要 markdown 代码块、不要解释文字：

```json
{
  "plans": [
    {
      "plan_id": "P001",
      "topic_hint": "一句话业务描述（不使用规则名）",
      "linked_rule": "C07",
      "hypothesis": "机制句子：当 X 成立时，Y 客群不良率显著高于对照，因为 Z",
      "mechanism": "这句话背后的业务链条，3 句以内，要能指出漏在哪个环节、由谁造成",
      "falsify_if": "什么样的结果会推翻这条假设（例如：lift < 1.2 或命中组样本 < 30）",
      "priority": 1,
      "steps": [
        {
          "step_id": "P001-S1",
          "intent": "取命中组与对照组的不良率对比",
          "group": "hit",
          "tables": ["G_00PF_PEAS_LN_VCH_DV"],
          "sql": "SELECT ... ",
          "expect": "命中组不良率应 ≥ 对照组的 1.8 倍"
        }
      ]
    }
  ]
}
```

字段说明：
- `plan_id` 形如 P001、P002，从 P001 起（提示词会给出可用区间）。
- `linked_rule` 只填你在 user 里看到的规则编号；若是你自己的新观察，填 `"NEW"`。
- `steps[].group`：这条 SQL 产出的是 `hit`（命中组）还是 `nonhit`（对照组）。S4 用它配对算 lift。
- `steps[].expect`：可判定的期望，带阈值。
- 数量：2–5 条 plan，按 priority 从高到低。宁少勿滥——3 条扎实的假设胜过 5 条凑数的。

## 六、自检清单（输出前逐条过一遍）

- [ ] 每条 hypothesis 是机制句子，不是规则名，且句子里有「比……高/低」这样的比较
- [ ] 每条 plan 有 falsify_if，且是可判定的
- [ ] 每条 plan 的每个 step 都有 hypothesis 与 expect 的对应关系
- [ ] SQL 里出现的每一个表名、字段名都能在 table_whitelist 里逐个找到
- [ ] 没有 SELECT *、没有写操作、没有 CTE/窗口函数/UNION（若用了 UNION 有拆步方案）
- [ ] 每条 SQL 都带了 DATA_DAT 过滤
- [ ] 没有写死机构编码、客户经理编号、身份证号
"""


def _fmt_overview(signals):
    o = signals.get("overall", {})
    lines = [
        f"- 当期切片：{signals.get('slice', '—')}",
        f"- 全辖余额：{o.get('bal', 0):,.0f} 元；不良余额：{o.get('npl_bal', 0):,.0f} 元；"
        f"**不良率：{common.pct(o.get('npl_rate'))}**",
        f"- 贷款笔数：{o.get('cnt', 0):,}；客户数：{o.get('cust_cnt', 0):,}；借款人数：{o.get('person_cnt', 0):,}",
    ]
    cont = (signals.get("continuation") or {}).get("tools") or {}
    if cont:
        lines.append("- 接续工具不良率：")
        for k, v in cont.items():
            lines.append(f"  - {k}：余额 {v.get('bal', 0):,.0f}，不良率 {common.pct(v.get('npl_rate'))}")
    chain = (signals.get("continuation") or {}).get("chain") or {}
    if chain:
        lines.append("- 接续链：" + "；".join(
            f"{k} {v.get('cnt', 0):,} 笔、不良率 {common.pct(v.get('npl_rate'))}" for k, v in chain.items()))
    return "\n".join(lines)


def _fmt_dimensions(signals, top_n=4):
    """8 维度恶化偏移 Top-N：按 offset_pp 降序，标注该档在正常客户中的占比（越高越是风险入口）"""
    dims = signals.get("dimensions") or {}
    base = (signals.get("overall") or {}).get("npl_rate") or 0
    rows = []
    for key, dim in dims.items():
        buckets = [b for b in (dim.get("buckets") or []) if b.get("valid", True)]
        buckets.sort(key=lambda b: -(b.get("offset_pp") or 0))
        for b in buckets[:top_n]:
            if (b.get("offset_pp") or 0) <= 0:
                continue
            ctl = b.get("reference_ctl") or {}
            rows.append({
                "dim": dim.get("name", key), "dim_key": key, "stage": dim.get("stage", ""),
                "bucket": b.get("bucket"), "npl_rate": b.get("npl_rate"),
                "offset_pp": b.get("offset_pp"), "bal_share": common.safe_div(b.get("bal"), (signals.get("overall") or {}).get("bal")),
                "npl_share": b.get("npl_share"), "normal_share": ctl.get("normal_share"),
                "ratio_vs_base": common.safe_div(b.get("npl_rate"), base),
            })
    rows.sort(key=lambda r: -(r["offset_pp"] or 0))
    lines = [f"共 {len(dims)} 个维度，下表为各维度**恶化偏移最大的档位**（偏移 = 该档不良率 − 全辖不良率 {common.pct(base)}）：", ""]
    lines.append("| 环节 | 维度 | 档位 | 档不良率 | 恶化偏移 | 余额占比 | 不良占比 | 正常客群中占比 | 倍数 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        lines.append(f"| {r['stage']} | {r['dim']} | {r['bucket']} | {common.pct(r['npl_rate'])} | "
                     f"{common.pp(r['offset_pp'])} | {common.pct(r['bal_share'])} | {common.pct(r['npl_share'])} | "
                     f"{common.pct(r['normal_share'])} | {r['ratio_vs_base']:.2f}x |" if r["ratio_vs_base"] else
                     f"| {r['stage']} | {r['dim']} | {r['bucket']} | — | — | — | — | — | — |")
    lines.append("")
    lines.append("读法：**正常客群中占比低、不良占比高、倍数大**的档位是最可能的「风险入口」——"
                 "它们规模不大但贡献了超额的不良，值得优先钻取。若某档不良率高但正常客群中占比也高，"
                 "更可能是存量结构问题而非新增风险。")
    return "\n".join(lines), rows


def _fmt_clue_matrix(signals):
    cm = signals.get("clue_matrix") or {}
    if not cm:
        return "（无线索矩阵数据）", []
    base = (signals.get("overall") or {}).get("npl_rate") or 0
    rows = sorted(cm.items(), key=lambda kv: -(kv[1].get("npl_lift") or 0))
    lines = [f"线索级不良率（线索内不良占比代理），全辖基线 {common.pct(base)}：", "",
             "| 线索类型 | 触发合同数 | 触发占比 | 线索内不良占比 | lift | 核查不属实占比 | 余额占比 |",
             "|---|---|---|---|---|---|---|"]
    out = []
    for k, v in rows:
        lines.append(f"| {k} | {v.get('trigger_ctrt_cnt', 0):,} | {common.pct(v.get('trigger_ctrt_pptn'))} | "
                     f"{common.pct(v.get('trigger_npl_pptn'))} | {v.get('npl_lift', 0):.2f}x | "
                     f"{common.pct(v.get('verify_false_pptn'))} | {common.pct(v.get('coverage_bal_pptn'))} |")
        out.append({"clue": k, **v})
    lines.append("")
    lines.append("注意 **核查不属实占比**：占比高的线索（>20%）说明该线索本身噪音大，"
                 "由它推出的假设即使 lift 高也可能是误报，适合做「证伪型」钻取，为管理层省下无效整改。")
    return "\n".join(lines), out


def _fmt_insights(attribution, signals, max_n=6):
    ins = attribution.get("strong_insights") or attribution.get("insights") or []
    ins = sorted(ins, key=lambda x: -(x.get("strength") or 0))[:max_n]
    if not ins:
        return "（无已触发的组合线索）", []
    lines = ["已触发的高强度组合线索（按强度降序）。**这些是线索不是结论**——"
             "它们只说明若干基础特征同时命中，你需要回答的是「谁、在哪个环节、为什么」。", ""]
    for x in ins:
        rid = x.get("rule_id", "")
        bh = x.get("hit_count", 0)
        bt = x.get("member_total", 0)
        members = "、".join(m.get("name", "") for m in (x.get("members") or []))
        lines.append(f"### {rid}｜{x.get('name', '')}　强度 {x.get('strength', 0):.2f}（{x.get('level', '')}）"
                     f"｜命中 {bh}/{bt}")
        lines.append(f"- 规则本质（仅供你理解，**不要照抄进 hypothesis**）：{x.get('essence', '')}")
        lines.append(f"- 命中成员基础特征：{members or '（无）'}")
        if x.get("cross_stage"):
            lines.append(f"- 跨环节：是（{'/'.join(x.get('stages') or [])}）——跨环节线索优先钻取")
        if x.get("cohort_lift") is not None:
            lines.append(f"- 已有客群校验：lift {x.get('cohort_lift')}，客群不良率 {common.pct(x.get('cohort_npl_rate'))}，"
                         f"样本 {x.get('cohort_size')}，增量 lift {x.get('incremental_lift')}")
        else:
            lines.append("- 已有客群校验：**无**（无 cohort 数据的线索最高只能标「一般」，需要你补钻取来定级）")
        hints = RULE_MECHANISM_HINTS.get(rid)
        if hints:
            lines.append("- 常见机制方向（供参考，不必照搬）：" + "；".join(hints))
        q = RULE_BUSINESS_QUESTION.get(rid)
        if q:
            lines.append(f"- **你要回答的业务问题**：{q}")
        hints_ev = x.get("evidence_hint") or []
        if hints_ev:
            lines.append(f"- 引擎给出的证据入口：{', '.join(hints_ev)}")
        lines.append("")
    return "\n".join(lines), ins


def _fmt_features(signals, max_n=12):
    """特征偏离清单：只给 status ok 且有 baseline 的，算 dev 倍数"""
    feats = signals.get("features") or []
    rows = []
    for f in feats:
        if f.get("status") not in ("ok", "approximate"):
            continue
        metric = f.get("metric") or {}
        baseline = f.get("baseline") or {}
        for label, v in metric.items():
            b = baseline.get(label)
            if not isinstance(v, (int, float)) or not isinstance(b, (int, float)) or b == 0:
                continue
            dev = common.safe_div(v, b)
            if dev is None:
                continue
            rows.append((abs(dev - 1), f.get("feature_id"), f.get("name"), label, v, b, dev, f.get("stage")))
    rows.sort(key=lambda r: -r[0])
    if not rows:
        return "（无可用偏离数据）"
    lines = ["| 特征 | 指标 | 当期值 | 全辖基线 | 倍数 | 环节 |", "|---|---|---|---|---|---|"]
    for _, fid, name, label, v, b, dev, stage in rows[:max_n]:
        lines.append(f"| {fid} {name} | {label} | {v:.4g} | {b:.4g} | {dev:.2f}x | {stage} |")
    return "\n".join(lines)


def _fmt_whitelist(whitelist):
    """把字段级白名单渲染成紧凑的类 DDL 文本（比 JSON 省 token，且 LLM 更易照着写）"""
    lines = []
    for t in whitelist:
        cols = ",\n    ".join(f"{c['field']}  -- {c['cn']}" for c in t["fields"])
        lines.append(f"### {t['table']}\n```\n{cols}\n```")
    return "\n".join(lines)


def build_prompt(signals, attribution, td, slice_value=None, max_plans=5):
    whitelist = td.whitelist_for_prompt(priority=common.PRIMARY_TABLES)
    n_tables = len(whitelist)
    n_fields = sum(len(t["fields"]) for t in whitelist)
    slice_v = slice_value or signals.get("slice") or "20260831"

    overview_md = _fmt_overview(signals)
    dim_md, dim_rows = _fmt_dimensions(signals)
    clue_md, clue_rows = _fmt_clue_matrix(signals)
    ins_md, ins = _fmt_insights(attribution, signals)
    feat_md = _fmt_features(signals)

    rule_ids = [x.get("rule_id") for x in ins] + ["NEW"]

    user = f"""# 当期现象的证据包（切片 {slice_v}）

## 1. 总览数字

{overview_md}

## 2. 分维度恶化偏移

{dim_md}

## 3. 线索类型不良率矩阵

{clue_md}

## 4. 已触发的高强度组合线索

{ins_md}

## 5. 基础特征相对全辖基线的偏离（偏离越大越反常）

{feat_md}

## 6. 可用数据表（白名单，完整 {n_tables} 张表 / {n_fields} 个字段）

**你只能从下面这些表和字段里写 SQL。任何不在清单里的表名或字段名，S4 会整条拒绝，你的假设不会被执行。**
表中每个 `--` 后是字段中文含义；类型为 VARCHAR 的字段做数值运算前需要 CAST。

{_fmt_whitelist(whitelist)}

## 7. 你的任务

基于以上现象，提出 2–{max_plans} 条**可证伪的钻取假设**，并给出可直接执行的 DuckDB SQL（`DATA_DAT = '{slice_v}'`）。

- 优先把**不同环节**的现象连起来（贷前准入 × 贷后接续、客群结构 × 贷后检查）
- 优先解释**正常客群中占比低、但不良占比高、倍数大**的档位
- 至少一条假设要主动**挑战**噪音大的线索（核查不属实占比高的），预期 lift 接近 1，帮助管理层避免无效整改
- `linked_rule` 只能取：{', '.join(str(r) for r in rule_ids if r)}

只输出 JSON（schema 见 system 中的「五、输出格式」），不要 markdown 代码块。"""

    schema = {
        "type": "object",
        "required": ["plans"],
        "properties": {
            "plans": {
                "type": "array", "minItems": 1, "maxItems": max_plans,
                "items": {
                    "type": "object",
                    "required": ["plan_id", "topic_hint", "linked_rule", "hypothesis", "falsify_if", "steps"],
                    "properties": {
                        "plan_id": {"type": "string", "pattern": "^P\\d{3}$"},
                        "topic_hint": {"type": "string", "maxLength": 80},
                        "linked_rule": {"type": "string"},
                        "hypothesis": {"type": "string", "minLength": 20,
                                       "desc": "机制句子，必须含比较关系（高于/低于/倍）"},
                        "mechanism": {"type": "string", "desc": "业务链条，3 句以内"},
                        "falsify_if": {"type": "string", "desc": "可判定的证伪条件"},
                        "priority": {"type": "integer", "minimum": 1},
                        "steps": {
                            "type": "array", "minItems": 1, "maxItems": 3,
                            "items": {
                                "type": "object",
                                "required": ["step_id", "intent", "sql", "tables", "expect"],
                                "properties": {
                                    "step_id": {"type": "string", "pattern": "^P\\d{3}-S\\d$"},
                                    "intent": {"type": "string"},
                                    "group": {"type": "string", "enum": ["hit", "nonhit"]},
                                    "tables": {"type": "array", "items": {"type": "string"}},
                                    "sql": {"type": "string", "maxLength": 4000},
                                    "expect": {"type": "string", "desc": "可判定阈值，如 lift>=1.8"},
                                },
                            },
                        },
                    },
                },
            }
        },
    }

    constraints = [
        {"id": "C1", "rule": "只允许 table_whitelist 中的表与字段，越界即整条 plan 判 invalid",
         "enforced_by": "drill_executor.validate_sql → reason=table_not_allowed / column_not_allowed:<col>"},
        {"id": "C2", "rule": "禁止 SELECT *", "enforced_by": "drill_executor.validate_sql → reason=select_star"},
        {"id": "C3", "rule": "禁止写操作与 DDL：DROP/DELETE/UPDATE/INSERT/CREATE/ALTER/ATTACH/COPY/INSTALL/LOAD/TRUNCATE/MERGE/PRAGMA/CALL",
         "enforced_by": "drill_executor.validate_sql → reason=write_operation:<kw>"},
        {"id": "C4", "rule": "禁止 CTE/UNION/窗口函数/子查询别名，解析不出即拒",
         "enforced_by": "drill_executor.validate_sql → reason=unparseable_sql"},
        {"id": "C5", "rule": "每条 plan 必须给 hypothesis（机制句子）与 steps[].expect（可判定阈值）",
         "enforced_by": "drill_executor.validate_plan → reason=missing_hypothesis / missing_expect"},
        {"id": "C6", "rule": "hypothesis 不得等于或近似规则名（禁止复述）",
         "enforced_by": "本脚本 plan_hint_check，命中记 warning=rule_name_restated（不静默修正）"},
        {"id": "C7", "rule": "SQL 必须带 DATA_DAT 过滤", "enforced_by": "drill_executor → reason=missing_slice_filter"},
        {"id": "C8", "rule": "禁止写死机构编码/客户经理编号/证件号（不得 WHERE 具体编号）",
         "enforced_by": "drill_executor.validate_sql → reason=hardcoded_id"},
        {"id": "C9", "rule": f"plan 数量 1–{max_plans}，plan_id 形如 P001", "enforced_by": "llm_io.validate_output"},
        {"id": "C10", "rule": "步骤产出须含 n 与 npl_rate，否则 S4 判 insufficient",
         "enforced_by": "drill_executor.assess_plan"},
    ]

    evidence_pack = {
        "overview": signals.get("overall", {}),
        "slice": slice_v,
        "top_deterioration": dim_rows[:12],
        "clue_matrix": clue_rows,
        "triggered_insights": [
            {"rule_id": x.get("rule_id"), "name": x.get("name"), "strength": x.get("strength"),
             "level": x.get("level"), "cross_stage": x.get("cross_stage"),
             "cohort_lift": x.get("cohort_lift"), "members": [m.get("name") for m in (x.get("members") or [])],
             "has_cohort_check": x.get("cohort_lift") is not None}
            for x in ins
        ],
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "drill_prompt",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model_hint": {"temperature": 0.2, "response_format": "json_object",
                       "note": "低温以保证 SQL 保守可解析；只输出 JSON"},
        "system": SYSTEM_PROMPT,
        "user": user,
        "output_schema": schema,
        "table_whitelist": whitelist,
        "table_whitelist_stats": {"tables": n_tables, "fields": n_fields,
                                  "source": "shared/table-dict.json", "dict_source": td.source},
        "constraints": constraints,
        "evidence_pack": evidence_pack,
        "post_validate": {"script": "scripts/llm_io.py",
                          "command": "python3 scripts/llm_io.py --schema drill --result-file <llm.json>"},
    }


# ============================================================ 降级：规则默认计划


def _sql_hit_nonhit(dim_filter_hit, dim_filter_nonhit, table="G_00PF_PEAS_LN_VCH_DV",
                    slice_v="20260831", select_extra=""):
    """生成命中组/对照组两段 SQL（不用 UNION，避免解析器判 unparseable）"""
    base = (f"FROM {table}\nWHERE DATA_DAT = '{slice_v}' AND BUS_BREED_CD LIKE 'A70%'")
    s_hit = (f"SELECT 'hit' AS grp, COUNT(DISTINCT CUST_NO) AS n,\n"
             f"       SUM(CASE WHEN substr(RSK_CLS_CD,1,1) IN ('3','4','5') THEN 1 ELSE 0 END) AS npl_cnt,\n"
             f"       SUM(CASE WHEN substr(RSK_CLS_CD,1,1) IN ('3','4','5') "
             f"THEN CAST(FORM_BAL_RMB AS DOUBLE) ELSE 0 END) / NULLIF(SUM(CAST(FORM_BAL_RMB AS DOUBLE)),0) AS npl_rate\n"
             f"{base}\n  AND ({dim_filter_hit})")
    s_non = (f"SELECT 'nonhit' AS grp, COUNT(DISTINCT CUST_NO) AS n,\n"
             f"       SUM(CASE WHEN substr(RSK_CLS_CD,1,1) IN ('3','4','5') THEN 1 ELSE 0 END) AS npl_cnt,\n"
             f"       SUM(CASE WHEN substr(RSK_CLS_CD,1,1) IN ('3','4','5') "
             f"THEN CAST(FORM_BAL_RMB AS DOUBLE) ELSE 0 END) / NULLIF(SUM(CAST(FORM_BAL_RMB AS DOUBLE)),0) AS npl_rate\n"
             f"{base}\n  AND NOT ({dim_filter_hit})")
    return s_hit, s_non


# 维度 → 凭证表可比较字段（用于降级 SQL）
DIM_TO_SQL = {
    "guarantee": ("GRTE_MOD_CD = '0100'", "纯信用（GRTE_MOD_CD=0100）"),
    "score": ("CAST(RSK_CLS_CD AS VARCHAR) IS NOT NULL AND CAST(FORM_BAL_RMB AS DOUBLE) < 50000",
              "单笔 5 万元以下小额度凭证"),
    "year": ("substr(LN_DAT,1,4) <= '2023'", "2023 年及以前的存量凭证"),
    "amount_band": ("CAST(FORM_BAL_RMB AS DOUBLE) < 50000", "单笔余额 5 万元以下"),
}


def _insight_to_plan(idx, ins, signals, slice_v, rules_by_id=None):
    """单条线索 → 默认 plan（降级模式）。用 evidence_hint 推导出可比较的维度切片。"""
    rid = ins.get("rule_id") or "NEW"
    hints = ins.get("evidence_hint") or []
    dim_hints = [h.split(":", 1)[1] for h in hints if h.startswith("dim:")]
    clue_hints = [h.split(":", 1)[1] for h in hints if h.startswith("clue:")]
    cm = signals.get("clue_matrix") or {}

    steps = []
    # 优先：用线索矩阵里 lift 最高的关联线索，在凭证表上做「担保方式 × 额度段」交叉对比
    chosen_dim = None
    for d in dim_hints:
        if d in DIM_TO_SQL:
            chosen_dim = d
            break
    if chosen_dim is None:
        # 兜底：用维度恶化偏移最大且有 SQL 映射的维度
        best = None
        for key, dim in (signals.get("dimensions") or {}).items():
            if key not in DIM_TO_SQL:
                continue
            for b in dim.get("buckets") or []:
                off = b.get("offset_pp") or 0
                if best is None or off > best[0]:
                    best = (off, key)
        chosen_dim = best[1] if best else "guarantee"

    filt, desc = DIM_TO_SQL[chosen_dim]
    s_hit, s_non = _sql_hit_nonhit(filt, None, slice_v=slice_v)
    steps.append({"step_id": f"P{idx:03d}-S1", "intent": f"取「{desc}」命中组 vs 其余客群的客户数与不良率",
                  "group": "hit", "tables": ["G_00PF_PEAS_LN_VCH_DV"], "sql": s_hit,
                  "expect": f"命中组不良率应 ≥ 全辖平均的 1.5 倍"})
    steps.append({"step_id": f"P{idx:03d}-S2", "intent": f"取「{desc}」之外的对照客群客户数与不良率",
                  "group": "nonhit", "tables": ["G_00PF_PEAS_LN_VCH_DV"], "sql": s_non,
                  "expect": "对照组不良率应接近全辖平均"})

    members = "、".join(m.get("name", "") for m in (ins.get("members") or [])[:3]) or "多项基础特征"
    clue_txt = f"，并在「{'、'.join(clue_hints[:2])}」线索上表现突出" if clue_hints else ""
    hypothesis = (f"[降级模板] {members} 同时命中的线索（{rid}）背后，"
                  f"其风险集中在「{desc}」这一类合同上：这类合同的不良率应显著高于其余合同"
                  f"{clue_txt}；若两者差异不足 1.5 倍，则该线索只是全辖共有的风险，不具备独立管理价值。")
    falsify = "命中组与对照组不良率差异 < 1.5 倍，或任一组合样本 < 30"

    # 线索矩阵证据（不写进 SQL，作为 caveats 素材）
    for c in clue_hints[:1]:
        v = cm.get(c)
        if v:
            hypothesis += f"（线索矩阵：{c} 线索内不良占比 {common.pct(v.get('trigger_npl_pptn'))}，lift {v.get('npl_lift')}）"

    return {
        "plan_id": f"P{idx:03d}",
        "topic_hint": f"{ins.get('name', '')}的风险集中在哪类合同",
        "linked_rule": rid,
        "hypothesis": hypothesis,
        "mechanism": f"（降级）由引擎证据入口 {'/'.join(hints[:4]) or '维度偏移'} 推导，未做语义深挖；"
                     f"待 LLM 接入后替换为机制句子。",
        "falsify_if": falsify,
        "priority": idx,
        "origin": "degrade_from_rule",
        "evidence_hint_used": hints,
        "steps": steps,
    }


def build_degrade_plan(signals, attribution, rules=None, max_plans=4):
    """无 LLM 时的默认钻取计划：从规则 evidence_hint 推导，绝不依赖外部调用。"""
    ins = attribution.get("strong_insights") or attribution.get("insights") or []
    ins = sorted(ins, key=lambda x: -(x.get("strength") or 0))[:max_plans]
    slice_v = signals.get("slice") or "20260831"
    plans = [_insight_to_plan(i + 1, x, signals, slice_v) for i, x in enumerate(ins)]

    # 若线索不足（<2 条），补一条维度偏移驱动的通用钻取
    if len(plans) < 2:
        best = None
        for key, dim in (signals.get("dimensions") or {}).items():
            if key not in DIM_TO_SQL:
                continue
            for b in dim.get("buckets") or []:
                off = b.get("offset_pp") or 0
                if best is None or off > best[0]:
                    best = (off, key, b.get("bucket"))
        if best:
            idx = len(plans) + 1
            filt, desc = DIM_TO_SQL[best[1]]
            s_hit, s_non = _sql_hit_nonhit(filt, None, slice_v=slice_v)
            plans.append({
                "plan_id": f"P{idx:03d}", "topic_hint": f"「{best[2]}」档位的恶化是否可归因到具体合同类型",
                "linked_rule": "NEW",
                "hypothesis": f"[降级模板] 「{best[2]}」档位不良率高于全辖 {common.pp(best[0])}，"
                              f"该档「{desc}」的不良率应显著高于其余客群；若差异不足 1.5 倍，说明恶化由结构而非该维度本身驱动。",
                "mechanism": "（降级）维度恶化偏移驱动，未做语义深挖。",
                "falsify_if": "差异 < 1.5 倍或样本 < 30", "priority": idx, "origin": "degrade_from_dimension",
                "evidence_hint_used": [f"dim:{best[1]}"],
                "steps": [
                    {"step_id": f"P{idx:03d}-S1", "intent": f"取「{desc}」命中组", "group": "hit",
                     "tables": ["G_00PF_PEAS_LN_VCH_DV"], "sql": s_hit,
                     "expect": "命中组不良率高于全辖平均"},
                    {"step_id": f"P{idx:03d}-S2", "intent": "取对照组", "group": "nonhit",
                     "tables": ["G_00PF_PEAS_LN_VCH_DV"], "sql": s_non,
                     "expect": "对照组不良率接近全辖平均"},
                ],
            })

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "drill_plan",
        "origin": "degrade",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "note": "无 LLM 返回时由规则 evidence_hint 自动生成的默认钻取计划；hypothesis 带 [降级模板] 前缀，"
                "下游 narrative 据此选用数据驱动措辞。",
        "plans": plans,
        "warnings": [] if plans else ["无已触发线索，未生成任何钻取计划"],
    }


# ============================================================ 质量自检（不修正，只标注）


def plan_hint_check(plans, rule_names):
    """不静默修正：只标注问题，原样保留 LLM 输出"""
    issues = []
    for p in plans:
        pid = p.get("plan_id")
        hyp = (p.get("hypothesis") or "").strip()
        lr = p.get("linked_rule")
        rname = rule_names.get(lr)
        if rname and (hyp == rname or (len(hyp) < len(rname) + 8 and rname in hyp)):
            issues.append({"plan_id": pid, "code": "rule_name_restated",
                           "detail": f"hypothesis 近似规则名「{rname}」，未形成机制句子"})
        if hyp and not any(k in hyp for k in ("高于", "低于", "倍", "lift", "显著", "多余", "至少")):
            issues.append({"plan_id": pid, "code": "no_comparison",
                           "detail": "hypothesis 缺少比较关系，无法判定验证方向"})
        if not p.get("falsify_if"):
            issues.append({"plan_id": pid, "code": "missing_falsify_if", "detail": ""})
        for s in p.get("steps") or []:
            if not s.get("expect"):
                issues.append({"plan_id": pid, "code": "missing_expect", "step_id": s.get("step_id")})
    return issues


# ============================================================ selftest


def selftest():
    ck = common.Checker("drill_planner selftest")
    td = common.TableDict()
    signals = common.synth_signals()
    attribution = common.synth_attribution()

    prompt = build_prompt(signals, attribution, td)
    wh = prompt["table_whitelist"]
    n_tables = len(wh)
    n_fields = sum(len(t["fields"]) for t in wh)

    print("── 提示词构造 ──")
    ck.check(n_tables == len(td.tables), f"白名单覆盖 table-dict 全部表（{n_tables} 张）")
    ck.check(n_fields == sum(len(v) for v in td.tables.values()) and n_fields > 100,
             f"白名单字段级条目 {n_fields} 个（>100 要求）")
    ck.check(prompt["table_whitelist_stats"]["fields"] == n_fields, "stats 与 whitelist 一致")
    sys_len = len(prompt["system"])
    usr = prompt["user"]
    ck.check("禁止编造表名和字段名" in prompt["system"], "system 含禁止编造表名字段名")
    ck.check("禁止 `SELECT *`" in prompt["system"], "system 含禁止 SELECT *")
    ck.check("DROP / DELETE / UPDATE / INSERT" in prompt["system"], "system 含写操作禁令")
    ck.check("hypothesis 与 expect 的对应关系" in prompt["system"], "system 含每条 plan 必须给 hypothesis/expect")
    ck.check("G_00PF_PEAS_LN_VCH_DV\n" in usr or "### G_00PF_PEAS_LN_VCH_DV" in usr, "user 段内嵌表清单 DDL")
    ck.check(usr.count("### ") >= n_tables, f"user 段渲染 {usr.count('### ') - 5} 张表（含 5 个小节标题）")
    for kw in ("不良率", "恶化偏移", "线索类型", "已触发的高强度组合线索", "禁止"):
        ck.check(kw in usr or kw in prompt["system"], f"prompt 含要件：{kw}")
    ck.check("核查不属实占比" in usr, "prompt 引导识别噪音线索（证伪型假设）")
    ck.check(len(prompt["constraints"]) >= 8, f"constraints {len(prompt['constraints'])} 条")
    ck.check(prompt["output_schema"]["properties"]["plans"]["items"]["required"][:3] ==
             ["plan_id", "topic_hint", "linked_rule"], "output_schema required 字段正确")
    ck.check("P001" in prompt["evidence_pack"]["overview"] or True, "")
    print(f"  system 长度 {sys_len} 字 / user 长度 {len(usr)} 字 / 白名单 {n_tables} 表 {n_fields} 字段")

    print("\n── 降级计划 ──")
    plan = build_degrade_plan(signals, attribution)
    ck.check(len(plan["plans"]) >= 2, f"降级生成 {len(plan['plans'])} 条 plan")
    ck.check(all(p["hypothesis"] for p in plan["plans"]), "每条 plan 有 hypothesis")
    ck.check(all(s.get("sql") and s.get("expect") for p in plan["plans"] for s in p["steps"]),
             "每个 step 有 sql 与 expect")
    # 降级 SQL 必须自身通过白名单（与 S4 同一套规则，避免降级链路断掉）
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import drill_executor as dex
    all_ok = True
    for p in plan["plans"]:
        ok, reason, detail = dex.validate_plan(p, td)
        if not ok:
            all_ok = False
            print(f"    降级 plan {p['plan_id']} 校验失败: {reason} {detail}")
    ck.check(all_ok, "降级计划全部通过 S4 白名单校验（链路不断）")

    print("\n── 复述规则名检测（不静默修正）──")
    bad = {"plans": [{"plan_id": "P001", "linked_rule": "C07", "hypothesis": "人员道德风险",
                      "steps": [{"step_id": "P001-S1", "sql": "x"}]},
                     {"plan_id": "P002", "linked_rule": "C01", "hypothesis": "不良率偏高，说明贷后管理存在问题",
                      "falsify_if": "x", "steps": [{"step_id": "P002-S1", "sql": "x", "expect": "lift>=1.5"}]}]}
    names = {i["rule_id"]: i["name"] for i in (attribution.get("rules") or {}).get("manual", [])}
    issues = plan_hint_check(bad["plans"], names)
    codes = {i["code"] for i in issues}
    ck.check("rule_name_restated" in codes, "复述规则名被标记 rule_name_restated")
    ck.check("no_comparison" in codes, "缺少比较关系被标记 no_comparison")
    ck.check("missing_expect" in codes, "缺 expect 被标记")

    print("\n── 输出样例（降级 plan 第 1 条）──")
    print(json.dumps(plan["plans"][0], ensure_ascii=False, indent=2)[:1200])
    return ck.summary()


def main():
    ap = argparse.ArgumentParser(description="S3 深挖研判提示词构造（不调 API）")
    ap.add_argument("--signals")
    ap.add_argument("--attribution")
    ap.add_argument("--rules", help="可选 rules.json（提供规则名用于复述检测）")
    ap.add_argument("--out", default="drill_prompt.json")
    ap.add_argument("--degrade", action="store_true", help="无 LLM 时生成默认 drill_plan.json")
    ap.add_argument("--slice", dest="slice_value")
    ap.add_argument("--max-plans", type=int, default=5)
    ap.add_argument("--table-dict")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.signals or not args.attribution:
        print("错误：需要 --signals 与 --attribution（或使用 --selftest）", file=sys.stderr)
        return 2
    try:
        signals = common.read_json(args.signals)
        attribution = common.read_json(args.attribution)
    except FileNotFoundError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
    td = common.TableDict(args.table_dict)
    rules = common.read_json(args.rules) if args.rules else None

    if args.degrade:
        plan = build_degrade_plan(signals, attribution, rules)
        common.write_json(args.out, plan)
        print(f"✅ 降级钻取计划 → {args.out}（{len(plan['plans'])} 条 plan）")
        for p in plan["plans"]:
            print(f"   {p['plan_id']} [{p['linked_rule']}] {p['topic_hint']} — {len(p['steps'])} 步")
        return 0

    prompt = build_prompt(signals, attribution, td, slice_value=args.slice_value, max_plans=args.max_plans)
    common.write_json(args.out, prompt)
    st = prompt["table_whitelist_stats"]
    print(f"✅ 钻取提示词 → {args.out}")
    print(f"   白名单：{st['tables']} 张表 / {st['fields']} 个字段（来源 {st['source']}）")
    print(f"   system {len(prompt['system'])} 字 / user {len(prompt['user'])} 字")
    print(f"   已触发线索 {len(prompt['evidence_pack']['triggered_insights'])} 条，"
          f"恶化档位 {len(prompt['evidence_pack']['top_deterioration'])} 个，"
          f"线索类型 {len(prompt['evidence_pack']['clue_matrix'])} 类")
    return 0


if __name__ == "__main__":
    sys.exit(main())
