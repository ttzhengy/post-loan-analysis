# 中间产物接口契约

本文件定义各脚本之间 JSON 的字段约定与计算公式，是**唯一的接口事实来源**。
改动任一脚本的输入输出结构，必须同步更新本文件，否则下游脚本会静默取到空值。

## 0. 全局约定

- 脚本分两类：**取数脚本**（`core_metrics_duckdb.py` / `core_overview_duckdb.py` / `org_risk.py` /
  `risk_features.py` / `cohort_attribution.py` / `theme_deep_dive_duckdb.py`）可用 duckdb / pyarrow / pandas；
  **计算与渲染脚本**（`signals.py` / `attribution.py` / `drill_*.py` / `narrative.py` / `render_report.py`）
  只用标准库，不引第三方依赖。
- 输入文件不存在 → 退出码 2，不猜。
- 数值异常（负余额、分母为 0）→ 写入 `warnings[]` 后继续。
- 中文输出统一 `ensure_ascii=False, indent=2`；字段名一律 `snake_case`。

## 1. 工作流（7 步）

```
S1 取数汇总      core_metrics_duckdb.py + core_overview_duckdb.py  → metrics.json / overview.json
S1b 机构级指标   org_risk.py                                       → org_risk.json
S1c 客群切分     cohort_attribution.py                             → cohort.json
S1d 基础特征     risk_features.py                                  → features.json
S2 归并扫线索    signals.py                                        → signals.json
S3 研判提示词    drill_planner.py                                  → drill_prompt.json
S4 按计划钻取    drill_executor.py                                 → evidence.json
S5 证据链提示词  narrative.py                                      → narrative_prompt.json
S6 渲染报告      render_report.py                                  → report.html / 验算清单 / summary.md
```

**LLM 边界**：脚本**只输出提示词**（`*_prompt.json`），由外部 Agent 调用模型，脚本内不调用任何 API。
无 LLM 结果时 S3/S5 必须能降级：`drill_plan` 用规则默认计划（`--degrade`），
`narrative` 用数据驱动模板（`--degrade`）。降级路径是全链路可离线跑通的前提。

## 2. metrics.json / overview.json / org_risk.json / features.json / cohort.json（取数阶段产出）

这五个文件由 S1 阶段脚本产出，是下游 signals.py 的全部输入。字段以实际产出为准。

### 2.1 metrics.json（core_metrics_duckdb.py）

```jsonc
{
  "schema_version":"3.0","slice":"20260831",
  "overall": {"bal":0,"npl_bal":0,"npl_rate":0,"cnt":0,"cust_cnt":0,"person_cnt":0,"exd_bal":0},
  "exd_seg": {"1-30天":{...},"31-90天":{...},"91-180天":{...},"180天以上":{...}},
  "by_org": [...], "by_mgr": [...], "by_breed": [...],
  "warnings": []
}
```

`exd_seg` 的键名固定为这四档中文标签。**下游按此键名生成 SQL 条件**，
`180天以上` 必须映射为 `EXD_DAYS > 180`，不可退化为 `> 0`。

### 2.2 overview.json（core_overview_duckdb.py）

```jsonc
{
  "schema_version":"3.0","slice":"20260831",
  "groups": {"normal":{...},"watch":{...},"bad":{...},"other":{...}},   // 四组对照
  "dimensions": {                        // 8 大维度
    "guarantee": {"name":"担保方式","stage":"贷前","buckets":[
      {"bucket":"信用","bal":0,"npl_bal":0,"npl_rate":0,"npl_share":0,
       "offset_pp":0.0,"reference_ctl":{"normal_share":0,"npl_share":0},"valid":true}]}
  },
  "overview_dives": {...},
  "warnings": []
}
```

维度键名固定 8 个：`guarantee` / `cust_type` / `industry` / `term` / `amount` /
`year` / `score` / `org`。`buckets[].valid=false` 表示该档样本量不足（余额低于全辖 0.1%），
下游不得参与排名。

### 2.3 org_risk.json（org_risk.py）

`dimensions` 结构与 overview.json 相同，另含 `tables.cont.summary` / `tables.cont.rows_all`
（接续工具明细）、线索长表 `rows_by_type`。缺失时 signals 的
`clue_matrix` / `continuation` 会降级，并在 `warnings[]` 注明。

### 2.4 features.json（risk_features.py）

```jsonc
{
  "schema_version":"2.0","slice":"20260831",
  "baseline": {"零散不良率均值":0.0231, ...},      // 全辖口径基线字典（label → 值）
  "baseline_src": {"零散不良率均值":"wavg:DIVR_LN_BAL"},  // 口径说明
  "features": [
    {"feature_id":1,"name":"零散获客风险","dimension":"机构","stage":"营销获客",
     "status":"ok|approximate|data_missing","table":"S_00PF_...",
     "metric":{"<label>":<number>},"baseline":{"<label>":<number>},
     "evidence":"...","note":""}
  ],
  "warnings":[]
}
```

**基线口径**：率类指标的全辖值用**余额加权**（`Σ(率×余额)/Σ余额`），
不是各机构率的简单平均——机构规模有差异时两者并不相等。
`metric` 与 `baseline` 是多键混合字典，键名随表结构变化，下游必须按语义匹配，不得按 `feature_id` 硬编码。

### 2.5 cohort.json（cohort_attribution.py）

```jsonc
{
  "schema_version":"3.0",
  "cohorts":[
    {"feature_id":1,"name":"零散获客","size":12137,"npl_rate":0.0876,
     "lift":1.8841,"incremental_lift":null,"npl_share":0.12,
     "condition":{...},"match_dim":"...","match_bucket":"..."}
  ]
}
```

`condition` 型客群带 `match_dim` / `match_bucket`，signals 按
`(维度名, 档位)` 匹配到对应规则；无 `condition` 的客群按 `feature_id` 匹配。

## 3. signals.json（signals.py 产出）

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

`baseline` 是**强度分量的必需输入**（特征值相对全辖基线的偏离）。

取值优先级与语义（`baseline_src` 字段记录来源）：

| baseline_src | 含义 |
|---|---|
| `inline` | 特征自带 baseline（或从 features.json 顶层 `baseline` 字典按标签匹配） |
| `overall_npl` | 指标含「不良率」，基线取全辖不良率 |
| `normal_1_0` | 倍数型指标（`强度`/`倍数`/`指数`），基线恒为 1.0 |
| `not_applicable` | 计数类指标（机构数/任务数等），无基线概念，不计入缺失 |
| `unavailable` | 口径与全辖不良率不同构（通过率/逾期占比等），强度分量记 0 |

**只有「不良率」类可以套用全辖不良率**。通过率、未办结率等分母语义完全不同，套用会得到假的强度值。

## 4. rules.json（人工维护，双源）

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
breadth = max_i( coverage_i )                             # 广度分量：成员覆盖率的最大值
        coverage_i 按成员类型取：feature → numerator/denominator
                              dim_bucket → 该档余额/总余额
                              clue → coverage_bal_pptn
                              cont → 余额/总余额
        单成员规则不再自动 breadth=1.0（旧口径 hit_count/total_members 已废弃）
signal  = mean_i( norm(dev_i) )  对命中成员             # 强度分量
        norm(dev) = min(1.0, |dev| / SATURATION)         # dev = 特征值相对 baseline 的偏离
        SATURATION 默认 2.0（即偏离达基线 2 倍计满）
strength = signal * (0.7 + 0.3 * breadth)                # signal 乘性主导，breadth 仅调节
若 cohort 校验存在：strength *= (1 + 0.15*min(1, (cohort_lift-1)/3))  # 最多 +15%
tie-break: (-strength, -incremental_lift, -cohort_size, cross_stage, rule_id)
```

分级：`>=0.5 显著`、`>=0.30 一般`、`>=0.15 弱信号`、`<0.15 淘汰`。
**无 cohort 校验数据的线索，最高只能标「一般」**，不得进「显著」。

## 5. drill_prompt.json / drill_plan.json（drill_planner.py 产出）

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

## 6. evidence.json（drill_executor.py 产出）

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

## 7. narrative_prompt.json / narrative.json（narrative.py 产出）

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

## 8. report.html / 验算清单（render_report.py 产出）

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

## 9. 预览版验收口径

`preview/` 下 4 套合成数据集各一份完整 HTML：
- `dataset_01.html` / `dataset_02.html` 主题集**必须不同**
- `dataset_03.html` 全弱信号 → 退化形态
- `dataset_04.html` 缺 cohort → 降级标注
每份内嵌**「本次主题生成轨迹」折叠块**（仅预览版有）：每条规则的广度/强度分量、进/出理由、LLM 钻取假设原文。
另出 `preview/README.md` 说明四套数据构造意图与预期差异。
