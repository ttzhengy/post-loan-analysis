---
name: post-loan-analysis
description: "农户贷款贷后归因报告（面向管理农户信贷的客户经理）。基于农户贷款数据自动计算不良率、逾期、风险特征命中，并从基础风险指标组合中挖掘深层归因线索（获客激进、准入失守、建档造假、贷后空转等），输出商业简约白底青绿风格的单文件HTML报告 + 指标验算清单。报告中不出现 id、表名等技术数据。触发词：贷后归因、贷后分析、不良归因、风险归因、农户贷款、客户经理、五级分类、不良率、A70。"
name_zh: 贷后归因
tags: ['信贷','贷后归因','农户贷款']
version: 2.0.0
runEnv: windows,uos
created_by:yuaotian
---

# 农户贷款贷后归因报告

面向**管理农户信贷的客户经理**的贷后风险归因与经营建议报告。输入为农户贷款数据文件（CSV），输出为单文件 HTML 报告 + 一页纸摘要 + 指标验算清单。

## 一、适用与硬性约定

适用于农户贷款（业务品种 A70 开头）的存量资产质量归因：不良率测算、逾期结构、基础风险特征命中、**从基础指标组合中挖掘深层归因线索**、管理建议。

**不适用**：贷前准入审批、单户财务比率分析、非农户贷款（A 开头非 70 的品种）。

### 五条硬性约定

1. **口径优先。** 农户贷款 = `BUS_BREED_CD` 以 `A70` 开头；不良 = 风险分类代码以 `3/4/5` 开头（次级/可疑/损失）；不良率 = 不良余额 ÷ 全部余额。任何分组指标均先过滤农户贷款口径。
2. **报告去技术化。** 最终 HTML 报告面向客户经理，**禁止出现表名、字段名、机构编码、客户经理 id、哈希值等技术数据**；机构/客户经理一律用业务化称呼（如「不良余额排名第 N 的机构」「排名第 N 的客户经理」）。技术口径只保留在《指标验算清单.md》。
3. **不编数据。** 无数据文件的表（征信P表、企业、地址交叉检验、贷后检查任务、电话催收等）不得虚构取值；对应风险指标改用机构级分析表预聚合口径，或标注「数据缺失，无法直接验证」。**统计为 0 或 None 的指标不写入报告**，避免出现无意义的 0 值。
4. **深层归因。** 45 项风险大类只是基础指标；必须按 `references/combination-insights.md` 的组合规则，从基础指标**同时命中的组合现象**中挖掘更深层线索本质。报告主题由**当期数据驱动**，严禁把规则名当结论硬写。
5. **DuckDB 全量聚合 + 只读必要列。** 数据已转 parquet（10G，原 CSV 86G 已清理），全部取数通过 DuckDB/parquet 完成：17GB 凭证表全量聚合秒级完成（core_metrics_duckdb.py）；风险特征计算用 pandas 读 parquet 列子集（risk_features.py）；机构级分析表（S_*_C4）小文件可直接全量载入。

## 二、数据源

### 2.1 数据文件位置

```
<项目根>/数字员工工作区/数据文件duckdb/parquet/
```

61 张 parquet 表（每表一个目录含 part-*.parquet，共约 10GB），`_manifest.json` 含中文名/分类。**原 CSV 数据目录（86.6G）已删除**，旧 CSV 版脚本（core_metrics.py / theme_deep_dive.py / check_env.py / cross_join.py / scan_keys.py）已清理。

### 2.2 表规模与读取策略（DuckDB 内存优化核心）

| 类别         | 特征              | 示例                                                                | 处理方式                                                |
| ---------- | --------------- | ----------------------------------------------------------------- | --------------------------------------------------- |
| **机构级分析表** | 小（1–112MB），已预聚合 | S_00PF_PEAS_*_C4 ×16                                              | pandas `read_parquet` 全量载入                          |
| **明细表-小**  | <600MB          | 逾期、客户档案、评分、任务                                                     | pandas `read_parquet(columns=…)` 只读必要列             |
| **明细表-大**  | GB 级            | G_00PF_PEAS_LN_VCH_DV(17GB)、G_00PF_IDV_LN_VCH_DV(16GB)、核销清收(18GB) | DuckDB `read_parquet` 全量聚合（3–10 秒），**不再流式/采样** |

**通用规则**：

- 所有大表读取必须带 `DATA_DAT=切片` 过滤（凭证表含 6 个月切片，不过滤会重复计数）
- `risk_features.py` 读 parquet 时可 `nrows` 采样或全量（视表大小）
- 聚合统计优先用 DuckDB SQL 单次完成（避免 pandas 载入 GB 级表）
- 征信 P1/P2/P3（P_00CIE_CPS_INDECATE_*）已有数据，支持多头借贷/查询频次/不良记录/涉诉涉税特征

### 2.3 关键字段速查（技术口径，仅脚本使用，不出现于报告）

| 字段                       | 含义               | 所在表            |
| ------------------------ | ---------------- | -------------- |
| BUS_BREED_CD             | 业务品种（A70开头=农户贷款） | 凭证/合同/账单/白名单流程 |
| RSK_CLS_CD / VCH_RSK_CLS | 风险分类（3/4/5=不良）   | 凭证表、任务表        |
| FORM_BAL_RMB             | 凭证余额折人民币         | 凭证表            |
| EXD_DAYS / BILL_EXD_DAYS | 逾期天数             | 凭证表、逾期表        |
| CUST_NO / ID_CARD_NO     | 客户编码/证件号         | 全表             |
| C4_ORG_NO / EIMO_ORG_NO  | 机构编码（成对出现）       | 机构级分析表、凭证表     |
| MAGR_CD / CUST_ID_NO     | 客户经理             | 凭证表、客户经理风险表    |
| DATA_DAT                 | 数据日期切片           | 拼接表/汇总表        |

完整表结构与字段字典见 [references/table-dictionary.md](references/table-dictionary.md)。

## 三、执行流程

### Step 0 · 环境与依赖

```bash
pip install duckdb pyarrow pandas openpyxl
python3 scripts/analyze_parquet.py --data-dir "数字员工工作区/数据文件duckdb/parquet"
```

校验：parquet 目录存在、61 张表可读、duckdb/pyarrow 可用、切片日期有效。

### Step 1 · 核心指标计算（`scripts/core_metrics_duckdb.py`）

```bash
python3 scripts/core_metrics_duckdb.py --data-dir "数字员工工作区/数据文件duckdb/parquet" \
    --slice 20260831 --out metrics.json
```

DuckDB 单条 SQL 全量聚合凭证表（17GB，秒级完成），仅保留 `DATA_DAT=切片` 行，输出：全辖余额/不良余额/不良率/行数/凭证数（去重 FORM_NO）/客户数（去重 CUST_NO）/个人数（去重 ID_CARD_NO，经建档档案映射）/逾期余额；按机构、客户经理、业务品种、担保方式分组（每组含凭证/客户/个人去重口径）；按逾期天数分段。

### Step 2 · 机构级风险指标（`scripts/org_risk.py`）

```bash
python3 scripts/org_risk.py --data-dir "数字员工工作区/数据文件duckdb/parquet" \
    --slice 20260831 --out org_risk.json
```

读 16 张 S_00PF_PEAS_*_C4 小表（parquet 优先），输出各风险类型维度的合同/客户/余额占比、不良率、还原核销不良率。

### Step 3 · 基础风险特征命中（`scripts/risk_features.py`）

```bash
python3 scripts/risk_features.py --data-dir "数字员工工作区/数据文件duckdb/parquet" \
    --slice 20260831 --out features.json
```

对 45 项基础风险特征逐项计算命中统计（parquet 优先，pandas 读列子集）；**征信 P1/P2/P3 已纳入**：特征 6/32-36/40/41（信用负债敞口、多头借贷、多头+负债不匹配、查询次数过多、被拒贷记录、N 年内不良、涉税强执呆账冻结、涉诉）从 data_missing 转为实际计算。无数据表的特征（贷后检查任务、交易时段、企业关联等）标 `data_missing`。命中判据见 [references/risk-features-map.md](references/risk-features-map.md)。**统计为 0/None 的指标不写入 metric**。

### Step 4 · 深层归因（`scripts/attribution.py`）

```bash
python3 scripts/attribution.py --metrics metrics.json --org-risk org_risk.json \
    --features features.json --out attribution.json
```

- **组合线索引擎**：按 `references/combination-insights.md` 的 13 条规则，从 45 项基础特征中识别深层线索（获客激进/准入失守/建档造假/超额授信/贷后空转/续贷断裂/人员道德/产品行业集中/客户欺诈/经营恶化/高杠杆/异常行为/还款来源失效），输出命中特征与证据字段。
- **相关表线索关联（证据链）**：根据归因主题在 C 类表（续贷凭证关系、接续表、上门催收、亲属信息、联村带户）中寻找佐证线索，整合为 `evidence_chain`（基础指标 + 相关表线索 + 整合说明）。
- **Top 画像**：机构/客户经理/业务品种按不良余额排序（不再输出帕累托指标）。
- **决策建议**：按「贡献度 × 可干预性」生成四象限动作（动作库见 [references/decision-actions.md](references/decision-actions.md)）。

### Step 4.5 · 完整总览 + 多维分类（`scripts/core_overview_duckdb.py`）

```bash
python3 scripts/core_overview_duckdb.py --data-dir "数字员工工作区/数据文件duckdb/parquet" \
    --slice 20260831 --out overview.json
```

- **四组对照**：按资产状态输出 正常（分类10且无逾期）/ 关注（20）/ 不良（30/40/50）/ 其他 四组的 余额/笔数/客户数/占比，作为风险指标的**参考对照组**。
- **8 大维度 × 资产状态**：产品与担保（担保方式/期限/额度/还款方式/循环）、客群与主体（主体类型/首贷/性别/居住年限）、产业与用途（贷款用途/投向行业）、时间与账龄（放款年份/逾期账龄/接续）、资产状态（五级分类/核销）、地理与区域（机构/省份）、风险计量（内部评级/评分分段）、管理与行为（客户经理/代理渠道）。
- 每档输出：余额占比、不良率、**恶化偏移**（档不良率 − 全辖不良率）、正常组占比、不良组占比，直接揭示「哪类产品/客群/产业在恶化」。

### Step 5 · 渲染报告（`scripts/render_report.py`）

```bash
python3 scripts/render_report.py --attribution attribution.json \
    --metrics metrics.json --org-risk org_risk.json --features features.json \
    --deep-dive deep_dive.json --overview overview.json --cohort cohort.json \
    --out-dir ./output
```

### Step 6 · 客群归因 + 优质准入反推（`scripts/cohort_attribution.py`）

```bash
python3 scripts/cohort_attribution.py --data-dir "数字员工工作区/数据文件duckdb/parquet" \
    --slice 20260831 --out cohort.json
```

- **多指标结合 → 交集客群**：每个主题由多个风险指标（至少）定义客户判据，取交集形成主题命中客群（如「客户经理渎职」= 信息失真 ∩ 资金往来 ∩ 低评分 ∩ 批量建档）。
- **正常组对照画像**：命中客群 vs 正常组（无不良无逾期）逐维对照（存款/交易/农地/评分/居住年限等 14 维），输出差异。
- **优质准入反推**：通过不良客户特征反向筛选可准入优质客户——输出各特征组合的「不良内占比」（越低越优质），并给出同时满足全部优质特征的可准入候选客群规模。

### Step 7 · 复合归因主题挖掘（`scripts/theme_mining.py`）

```bash
python3 scripts/theme_mining.py --data-dir "数字员工工作区/数据文件duckdb/parquet" \
    --slice 20260831 --out mining_candidates.json
```

- **三层漏斗（受约束搜索，非纯暴力）**：
  1. 特征→客户集合（14+ 个），两两 Jaccard 重叠 ≥ 0.02 预筛（766 万全组合 → 几十对）
  2. 交集客群不良率 lift ≥ 1.5、规模 ≥ 30、增量贡献（组合 vs 单特征）
  3. 跨环节组合优先（贷前×贷后 / 管理×产品），人工命名后沉淀到规则库
- 产出：mining_candidates.json（全部显著候选 + lift/增量指标），候选规则自动追加到 [references/combination-insights.md](references/combination-insights.md) 第三节

产出三件：

- `report.html` — 单文件自包含 HTML，**对齐《报告模板.doc》分点论据格式**并**遵守《报告html标签说明.doc》标签规范**：
  - 每个分析主题用 `<section data-topic-id="T001…">` 标记，**主题编号全文唯一、容器不嵌套**；主题标题正常展示
  - 所有统计数据/比较判断（金额、笔数、比例、变化幅度、排名、"最高/高于"等）用 `<span data-calc-id="D001…">` 标记，**数据编号全文唯一**；同一结果重复出现时使用不同编号
  - 报告结构：报告基本信息 → 分析主题与归因分析（发现/产生机制/影响范围 → 风险画像 → 综合归因 A-1~A-4/B → **相关表线索证据链** → 管理策略 6 维度）→ 风险警示
  - **面向客户经理，不含 id/表名等技术数据**；白底青绿商业简约风；断网可开、可打印
- `数据验算清单.xlsx` / `数据验算清单.md` — 与 HTML 中 data-calc-id 一一对应，4 列：**数据编号 | 网页展示结果 | 数据来源 | 计算代码或SQL**；数据来源标明表名与字段，SQL 给出可执行口径
- `summary.md` — 一页纸摘要（含每个主题的发现/机制/影响范围）

**查询日志（内部记录，不落入报告）**：各脚本通过 `--log query_log.md` 输出查询过程留痕——记录查询表、过滤条件、结果与查询思路，供复盘与可追溯；query_log.md 独立于 report.html，**不包含在最终报告中**。

**文字生成要求**（v4）：每条论据必须给出「数据 → 现象 → 推论 → 归因」的完整文字说明，面向客户经理可读；发现段引用具体数值，机制段说明业务逻辑，证据段给验证维度表，反证/待确认段如实标注数据盲区。

## 四、报告结构（现象 → 成因 → 证据链，对齐归因方法论）

> 报告**第一屏是总览 + 成因链**，不是统计表格、不是 Top N 排行、不是基础风险清单。
> 评分/排行/基础清单只放《指标验算清单.md》。方法论详见 [references/attribution-methodology.md](references/attribution-methodology.md)。

| 报告章节       | 内容                                        | 数据来源                     |
| ---------- | ----------------------------------------- | ------------------------ |
| 一、总览       | 口径说明 + KPI + 4 个现象描述（逾期结构/风险集中度/组合信号/平滑项） | metrics + top + insights |
| 二、成因分析     | 每条成因：**可能的成因 → 触发特征组合 → 证据链 → 待验证项**      | strong_insights          |
| 三、资产质量现象分析 | 表观不良 vs 真实生成、平滑项暴露（展期/续贷/核销/转让）、逾期→不良迁移缓冲 | overall + exd_seg        |
| 四、管理策略建议   | 四象限动作，6 字段（动作/责任岗/时限/验证指标/基线/目标）          | actions                  |
| 五、风险警示     | 数据缺失、证据不足、口径降级提示                          | warnings                 |

**报告纪律**（内化自《归因方法论》《10个主题》）：

- **不单列 Top10 排行**：集中度只在总览用一句话描述（如"前 3 机构合计占比 X%"）
- **不单列基础风险清单**：45 项基础特征只作为成因的证据，不单独成表
- **总览放大**：口径先固定（首页放口径说明）、给全景画像、描述可观察现象
- **成因必须带证据链**：每条成因给"现象→直接原因→管理根因→可干预点"，标注依据等级
- **慎下因果**：汇总级只做可加分解（流量桥/结构分解/漏斗），因果表述注明滞后期假设
- **主动暴露平滑项**：展期/无还本续贷/核销/批量转让同时影响规模与不良读数，结论建立在不良生成率上

## 五、视觉规则（强制 · 商业简约 · 白底 · 青绿衬色）

1. **商业风 · 简约 · 白底**：页面背景 `#ffffff`，备用区 `#f8fafc`；无深色主题、无背景动效、无鼠标特效。
2. **衬色唯一为青绿色系（teal）**：主衬色 `#0f766e` / `#14b8a6`，浅衬色 `#ccfbf1` / `#f0fdfa`，深字色 `#134e4a`。
3. **不得有其他花色块**：红/橙/紫/蓝/黄等一律禁止。状态表达只用青绿深浅 + 灰阶（重要=深青绿、一般=中青绿、次要/缺失=灰）；警示用「⚠ 提示」文字 + 浅青绿底卡片，不用红色块。
4. **文字层级**：标题 `#0f172a`、正文 `#334155`、次要 `#64748b`。
5. **卡片**：白底 + `1px solid #e2e8f0` 边框 + 轻阴影 + 12px 圆角；无毛玻璃/发光/hover 位移。
6. **表格**：表头浅青绿底 `#f0fdfa` + 深青绿字，行间细线 `#f1f5f9`，数字列右对齐。
7. **图表**：条形图青绿渐变（`#14b8a6 → #0f766e`），轨道灰；不引入其他颜色。
8. **打印友好**：`@media print` A4 适配，白底、去阴影、表头跨页重复；提供「打印 / 导出 PDF」按钮。

实现统一集中在 `scripts/render_report.py` 顶部 `CSS` 常量。

## 六、常见错误（反模式）

1. **忘记过滤 A70** — 把个人贷款混入农户贷款统计，口径全错
2. **用全量凭证表** — 17GB 直接读入内存会 OOM；必须切片 + 流式 + usecols
3. **把逾期当不良** — 逾期≠不良，不良率只算风险分类 3/4/5
4. **用缺失表硬算** — 征信P表无数据，信用负债类特征须用 S_*_C4 预聚合口径或标注缺失
5. **忽略切片** — 凭证表含 6 个切片，不指定 DATA_DAT 会重复计数
6. **用笔数代替金额** — 贡献度按不良余额（金额）计算，不用合同数
7. **报告出现技术数据** — id、表名、字段名只进《指标验算清单》，不进面向客户经理的报告
8. **写死主题** — 分析主题必须由组合线索引擎数据驱动，不得把规则名当必然结论
9. **报告出现 0 统计** — 统计为 0/None 的指标不展示，避免误导

## 七、自检清单

1. 所有凭证级指标是否都过滤了 `BUS_BREED_CD LIKE 'A70%'`？
2. 不良判定是否用 `RSK_CLS_CD LIKE '3%'/'4%'/'5%'`（非仅逾期）？
3. 是否指定了切片日期（默认 20260831）且无重复计数？
4. 大表是否流式 + usecols，未全量载入内存？
5. 无数据表的特征是否标注 `data_missing` 而非编造？
6. 报告中是否出现 0/None 统计？（应为 0 处）
7. **报告是否含 id/表名等技术数据？**（应为 0 处；只允许出现在《指标验算清单》）
8. 组合线索是否由数据驱动，未写死主题？
9. **视觉规则**：报告是否白底、衬色仅青绿色系、无其他花色块？打印是否白底可读？
10. report.html 断网可开、可打印？指标验算清单每个指标有表名+字段+计算逻辑？

## 八、脚本与参考文件

| 文件                                      | 用途                                |
| --------------------------------------- | --------------------------------- |
| `scripts/analyze_parquet.py`            | parquet 表概览（行数/列数/键字段）             |
| `scripts/core_metrics_duckdb.py`        | 核心指标（不良率/分组/逾期结构，DuckDB 全量聚合+去重口径） |
| `scripts/org_risk.py`                   | 机构级风险指标（S_*_C4 ×16 表，parquet 优先）   |
| `scripts/risk_features.py`              | 45 项基础风险特征命中（parquet 优先，含征信特征）   |
| `scripts/attribution.py`                | 组合线索引擎 + Top 画像 + 决策建议（无帕累托）      |
| `scripts/render_report.py`              | HTML 报告 + 指标验算清单 + 摘要（白底青绿，无技术数据） |
| `scripts/theme_deep_dive_duckdb.py`     | 主题深挖（DuckDB SQL 三段式：样本→关联→分组对比）  |
| `scripts/core_overview_duckdb.py`       | 完整总览 + 多维分类（四组对照 + 8 大维度恶化偏移）  |
| `scripts/cohort_attribution.py`         | 客群归因 + 优质准入反推（多指标交集客群 + 正常组对照） |
| `scripts/theme_mining.py`               | 复合归因主题挖掘器（Jaccard 预筛 + 交集 lift 验证，三层漏斗） |
| `references/table-dictionary.md`        | 62 张表结构字典 + 61 张有数据文件清单（2026-11-06 扩至 61，+12 全新 +1 更名）           |
| `references/risk-features-map.md`       | 45 项基础特征 → 表/字段/命中判据映射            |
| `references/combination-insights.md`    | 组合归因规则库（深层线索，数据驱动）                |
| `references/attribution-methodology.md` | 归因方法论（流量桥/结构分解/平滑项/证据链/动作6字段）     |
| `references/decision-actions.md`        | 四象限决策动作库                          |

## 九、依赖策略

`duckdb`（全量聚合）+ `pyarrow`（parquet 读取）+ `pandas`（特征计算）+ `openpyxl`（验算清单）+ 标准库。金额用 `float` 保留 2 位（输出时格式化），大表用 DuckDB SQL 全量聚合（17GB 凭证表 3–10 秒），不再流式/采样。

脚本行为约定：

- 输入文件不存在 → 退出码 2，不猜
- 必填字段缺失 → 写 `{{待补}}` + 标 `degraded: true`，继续
- 数值异常（负余额、分母 0）→ 记入 `warnings[]`
- 统计为 0/None 的指标不写入 metric（避免报告出现 0 统计）
