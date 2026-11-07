# 接口契约 v3.0（四个子代理的共同约束，不得单方面修改）

本文件由 Orchestrator 定义。任何子代理需要改动契约，必须在交付说明里**明确标注**，不得静默变更。

## 0. 全局约定

- Python **纯标准库**（`json`/`math`/`statistics`/`argparse`/`datetime`/`re`/`pathlib`）。
  唯一例外：C（渲染）不需要第三方库；A/B/D 也不得引入 numpy/pandas/pyyaml。
  原生处理数据的脚本（`core_metrics_duckdb.py` 等）保持原样，不在本次重构范围。
- 所有脚本：输入不存在 → 退出码 2，不猜；数值异常 → 写 `warnings[]`。
- 中文输出统一 `ensure_ascii=False, indent=2`。
- 字段名一律 `snake_case`。

## 1. 工作流（7 步）

```
S1 总览汇总      core_overview_duckdb.py + core_metrics_duckdb.py  → overview.json / metrics.json   [既有，不改]
S2 分维度扫线索   NEW signals.py     → signals.json                [A]
S3 LLM 研判深挖   NEW drill_planner.py → drill_prompt.json          [B，只出提示词]
S4 按计划钻取     NEW drill_executor.py → evidence.json             [B，白名单强校验]
S5 LLM 写证据链   NEW narrative.py    → narrative_prompt.json       [B，只出提示词]
S6 渲染报告       render_report.py    → report.html + 图表          [C，重构]
S7 验算清单       render_report.py    → 验算清单.xlsx/.md           [C，对齐 data-calc-id]
```

**LLM 边界（用户已确认）**：脚本**只输出提示词**（`*_prompt.json`），由外部 Agent 调用模型；脚本内**不调用任何 API**。
无 LLM 结果时，S4/S5 必须能降级：`drill_plan` 用规则默认计划，`narrative` 用数据驱动模板。

## 2. signals.json（A 产出）

```jsonc
{
  "schema_version": "3.0",
  "slice": "20260831",
  "overall": {"bal":0,"npl_bal":0,"npl_rate":0,"cnt":0,"cust_cnt":0,"person_cnt":0},
  "dimensions": {                       // 8 大维度
    "<dim_key>": {                      // guarantee/term/cust_type/industry/age/year/score/org...
      "name": "担保方式", "stage": "贷前",
      "buckets": [
        {"bucket":"信用","bal":0,"npl_bal":0,"npl_rate":0,"npl_share":0,
         "offset_pp":0.0,          // 恶化偏移 = 档不良率 - 全辖不良率
         "reference_ctl": {"normal_share":0,"npl_share":0},"valid":true}
      ]
    }
  },
  "clue_matrix": {                      // 来自 S_*_RSK_ORG_C4 长表，线索级（关键新增）
    "<clue_type>": {
      "trigger_ctrt_cnt":0,"trigger_ctrt_pptn":0,"trigger_cust_cnt":0,"trigger_bal":0,
      "trigger_npl_ctrt_cnt":0,"trigger_npl_pptn":0,     // 线索内不良占比 = 线索级不良率代理
      "verify_false_pptn":0,                            // 核查不属实占比
      "npl_lift":0.0,                                   // 线索不良率 / 全辖不良率
      "base_rate":0.0,"basis":"contract|bal","coverage_bal_pptn":0
    }
  },
  "features": [                          // 45+ 项基础特征，兼容旧 key
    {"feature_id":1,"name":"零散获客","dimension":"机构","stage":"贷前",
     "status":"ok|approximate|clue|data_missing",
     "metric":{"<label>": <number>}, "baseline":{"<label>": <number>},
     "numerator":0,"denominator":0,"note":""}
  ],
  "continuation": {                      // 接续链（新增）
    "tools": {"no_principal_renew":{"bal":0,"npl_bal":0,"npl_rate":0}, ...},
    "chain":  {"rolling":{"cnt":0,"npl_rate":0},"resolving":{"cnt":0,"npl_rate":0}}
  },
  "warnings": []
}
```

`baseline` 是**强度分量的必需输入**（特征值相对全辖基线的偏离）。缺失时该特征强度分量记 0 并在 note 标注。

## 3. rules.json（A 产出，双源）

```jsonc
{
  "schema_version":"3.0",
  "manual": [                            // 原 C01–C13 迁移
    {"rule_id":"C01","name":"获客激进扩张","essence":"...","source":"manual","version":1,
     "expr":{"all_of":[1,2,3],"min_hits":2,"any_of":[]},
     "cross_stage":false,"stages":["贷前"],
     "metrics":["零散客户占比均值","信用类余额占比均值","低分段(<600)占比"],
     "evidence_hint":["dim:guarantee","clue:..."]}
  ],
  "mined": [                             // theme_mining + 表结构新推导
    {"rule_id":"M01","name":"...","essence":"...","source":"mined|derived",
     "version":1,"expr":{"all_of":[34,36],"min_hits":2,"any_of":[],"scale_max":5},
     "cross_stage":false,"stages":["贷前","贷后"],
     "cohort_lift":13.72,"cohort_npl_rate":0.5692,"cohort_size":65,"incremental_lift":1.10,
     "metrics":[],"evidence_hint":["clue:RSK_LINE_TYP:反欺诈"]}
  ]
}
```

`linear` 兼容：旧扁平 `members` 列表视为 `all_of` 且 `min_hits` 沿用旧值。

**强度公式（必须照此实现）**：

```
breadth = max_i(coverage_i)                              # 广度分量：命中客群的业务量占比
        coverage 来源：feature 的 numerator/denominator、dim_bucket 的 bal/总余额、
                       clue 的 coverage_bal_pptn、cont 的 bal/总余额
        缺失时退回 hit_count / total_members（仅作为兜底，会写入 diag）
signal  = mean_i( norm(dev_i) )  对命中成员             # 强度分量
        norm(dev) = min(1.0, |dev| / SATURATION)         # dev = 特征值相对 baseline 的偏离
        SATURATION 默认 2.0（即偏离达基线 2 倍计满）
strength = signal * (0.7 + 0.3*breadth)
若 cohort 校验存在：strength *= (1 + 0.15*min(1, (cohort_lift-1)/3))  # 最多 +15%
tie-break: (-strength, -incremental_lift, -cohort_size, cross_stage, rule_id)
```

> **为什么不是 `0.6*breadth + 0.4*signal`**：广度权重 0.6 会让「几乎无偏离但覆盖满」的规则
> 压过「强偏离但覆盖有限」的规则（实测 D04 lift=1.11 排在 M13 lift=3.68 之前）。
> 风险归因的主线是找偏离，因此 signal 乘性主导，breadth 仅在 0.7~1.0 区间做调节。
> 另注意旧式 breadth = hit_count/total_members 由「规则写了几条成员」决定，
> 单成员规则只要命中就恒为 1.0，与现象是否普遍无关，故不再直接用于打分。

分级：`>=0.5 显著`、`>=0.30 一般`、`>=0.15 弱信号`、`<0.15 淘汰`。
**无 cohort 校验数据的线索，最高只能标「一般」**，不得进「显著」。

## 4. drill_prompt.json / drill_plan.json（B 产出）

`drill_prompt.json`：脚本给 LLM 的**完整提示词**，含 `system`、`user`、`output_schema`、`table_whitelist`（从 table-dict.json 取，字段级清单）、`constraints`。

`drill_plan.json`（LLM 返回或被降级生成）：
```jsonc
{"schema_version":"3.0","plans":[
  {"plan_id":"P001","topic_hint":"<规则名或自由文本>","linked_rule":"C07",
   "hypothesis":"客户经理与客户存在资金往来时，小额贷款的不良更集中",
   "steps":[{"step_id":"P001-S1","intent":"取命中与未命中客群的不良率对比",
             "sql":"SELECT ... FROM <白名单表> WHERE ...","tables":["G_00PF_PEAS_LN_VCH_DV"],
             "expect":"命中组不良率应显著高于未命中组"}]}]}
```

**白名单强校验（用户已确认强制）**：`drill_executor.py` 必须
1. 解析 SQL，提取所有 `FROM`/`JOIN` 表名与列名；
2. 任一表名不在 `table-dict.json` → 整条 plan 判 `invalid`，`reason="table_not_allowed"`；
3. 任一列名不在该表字段清单 → 判 `invalid`，`reason="column_not_allowed:<col>"`；
4. 出现 `DROP|DELETE|UPDATE|INSERT|CREATE|ALTER|ATTACH|COPY|INSTALL|LOAD` → 直接拒绝（只读库）；
5. **不静默修正**，无效的 plan 原样记录在 `evidence.json.plan_audit[]`。

## 5. evidence.json（B 产出）

```jsonc
{"schema_version":"3.0","plans_total":0,"plans_valid":0,
 "evidence_chain":[{"plan_id":"P001","linked_rule":"C07","hypothesis":"...",
   "status":"verified|rejected|insufficient",
   "comparisons":[{"dim":"hit_vs_nonhit","hit":{"n":0,"npl_rate":0},
                   "nonhit":{"n":0,"npl_rate":0},"lift":0.0}],
   "drill_rows":[{"sql":"...","columns":[],"rows":[]}],
   "verdict":"...","caveats":["..."]}],
 "plan_audit":[{"plan_id":"P002","status":"invalid","reason":"column_not_allowed:FOO"}],
 "warnings":[]}
```

`status` 规则：有对比且 `lift>=1.5` 且样本 `n>=30` → `verified`；`lift<1.2` → `rejected`；样本不足或无对比 → `insufficient`。

## 6. narrative_prompt.json / narrative.json（B 产出）

`narrative_prompt.json` 的 `output_schema` 要求 LLM 每条主题输出：
```jsonc
{"topic_id":"T001","title":"...",                    // 业务化标题，禁止规则名当标题
 "phenomenon":"现象（引具体数值）","mechanism":"产生机制",
 "evidence":"证据链（含钻取结论）","impact":"影响范围（客群规模/不良贡献）",
 "management_decision":{"action":"...","owner":"...","deadline":"...",
   "kpi":"...","baseline":"...","target":"..."},
 "caveats":["反证/数据盲区"]}
```

**管理者立场要求（用户明确）**：决策建议必须同时满足「保经营」+「防风险」，写明动作的**经营代价与收益**，不能只写"压降不良"。

## 7. render_report.py（C 产出）

**必须有图表**（用户明确）。约束：单文件自包含、断网可开、**内联 SVG**，不引任何 CDN/JS 框架。

最低图表清单：
1. 逾期分段占比（堆叠条）
2. 8 大维度恶化偏移（水平条形，标 0 基准线）
3. 线索类型不良率 vs 全辖基线（散点/条形）
4. 接续工具不良率对比（条形）
5. 主题客群 lift（条形）

**保留并加强**：`data-topic-id` / `data-calc-id` 双标签全文唯一，S7 验算清单逐条对应。

**去硬编码**（针对已诊断缺陷）：删除现有四段固定套话（`render_report.py:444-462`），文案由 `narrative.json` 提供；无 narrative 时用数据驱动模板（按 lift 高低/跨环节/有无校验选择措辞）。

**主题数量动态**：不得 `insights[:4]` 硬截断。进入主题的条件是：`strength>=0.30` **且** (`evidence_chain.status=="verified"` **或** 无钻取数据时 `strength>=0.5`)。数量由数据决定，0 条时退化为「指标监测式」。

## 8. 预览版（C 产出）

`preview/` 下 4 套合成数据集各一份完整 HTML：
- `dataset_01.html` / `dataset_02.html` 主题集**必须不同**
- `dataset_03.html` 全弱信号 → 退化形态
- `dataset_04.html` 缺 cohort → 降级标注
每份内嵌**「本次主题生成轨迹」折叠块**（仅预览版有）：每条规则的广度/强度分量、进/出理由、LLM 钻取假设原文。
另出 `preview/README.md` 说明四套数据构造意图与预期差异。
