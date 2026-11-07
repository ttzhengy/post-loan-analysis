---
name: post-loan-analysis
description: "农户贷款贷后归因报告（面向管理农户信贷的客户经理）。基于农户贷款数据自动计算不良率、逾期、风险特征命中，并从基础风险指标组合中挖掘深层归因线索（获客激进、准入失守、建档造假、贷后空转等），输出商业简约白底青绿风格的单文件 HTML 报告 + 指标验算清单。报告中不出现 id、表名等技术数据。触发词：贷后归因、贷后分析、不良归因、风险归因、农户贷款、客户经理、五级分类、不良率、A70。"
name_zh: 贷后归因
tags: ['信贷', '贷后归因', '农户贷款']
version: 3.0.0
runEnv: windows,uos
---

# 农户贷款贷后归因报告

面向**管理农户信贷的客户经理**的贷后风险归因与经营建议报告。输入为农户贷款数据（parquet 或 CSV），
输出为单文件 HTML 报告 + 指标验算清单 + 一页纸摘要。

## 一、适用与约定

适用于农户贷款（业务品种 `A70` 开头）的存量资产质量归因：不良率测算、逾期结构、风险特征命中、
从基础指标组合中挖掘深层归因线索、管理建议。

**不适用**：贷前准入审批、单户财务比率分析、非农户贷款（`A` 开头但非 `70` 的品种）。

### 四条约定

1. **口径优先。** 农户贷款 = `BUS_BREED_CD` 以 `A70` 开头；不良 = 风险分类代码以 `3/4/5` 开头
   （次级/可疑/损失）；不良率 = 不良余额 ÷ 全部余额。任何分组指标先过滤农户贷款口径。
2. **报告去技术化。** 最终 HTML 面向客户经理，不出现表名、字段名、机构编码、客户经理 id、哈希值。
   机构与客户经理一律用业务化称呼（如「不良余额排名第 N 的机构」）。技术口径只保留在《指标验算清单》。
3. **不编数据。** 无数据文件的表不得虚构取值；对应指标改用机构级分析表预聚合口径，
   或标注「数据缺失，无法直接验证」。统计为 0 或 None 的指标不写入报告。
4. **主题数据驱动。** 基础特征只是原材料；报告主题必须由当期数据的组合命中情况产生，
   不得把规则名当结论硬写。0 条主题时走「指标监测式」退化分支，如实说明未见强组合信号。

## 二、数据源

### 2.1 数据位置

```
<项目根>/数字员工工作区/数据文件duckdb/parquet/
```

每表一个目录含 `part-*.parquet`，`_manifest.json` 含中文名与分类。

### 2.2 读取策略

| 类别 | 特征 | 示例 | 处理方式 |
|------|------|------|----------|
| 机构级分析表 | 小（1–112MB），已预聚合 | `S_00PF_PEAS_*_C4` ×16 | pandas `read_parquet` 全量载入 |
| 明细表-小 | <600MB | 逾期、客户档案、评分、任务 | `read_parquet(columns=…)` 只读必要列 |
| 明细表-大 | GB 级 | 凭证表、核销清收 | DuckDB `read_parquet` 全量聚合（3–10 秒） |

**通用规则**

- 所有大表读取必须带 `DATA_DAT=切片` 过滤（凭证表含 6 个月切片，不过滤会重复计数）
- 聚合统计优先用 DuckDB SQL 单次完成，避免 pandas 载入 GB 级表
- 征信 P1/P2/P3（`P_00CIE_CPS_INDECATE_*`）支持多头借贷/查询频次/不良记录/涉诉涉税特征

### 2.3 关键字段

| 字段 | 含义 | 所在表 |
|------|------|--------|
| `BUS_BREED_CD` | 业务品种（A70 开头 = 农户贷款） | 凭证/合同/账单 |
| `RSK_CLS_CD` / `VCH_RSK_CLS` | 风险分类（3/4/5 = 不良） | 凭证表、任务表 |
| `FORM_BAL_RMB` | 凭证余额折人民币 | 凭证表 |
| `EXD_DAYS` / `BILL_EXD_DAYS` | 逾期天数 | 凭证表、逾期表 |
| `CUST_NO` / `ID_CARD_NO` | 客户编码 / 证件号 | 全表 |
| `C4_ORG_NO` / `EIMO_ORG_NO` | 机构编码（成对出现） | 机构级分析表、凭证表 |
| `MAGR_CD` / `CUST_ID_NO` | 客户经理 | 凭证表、客户经理风险表 |
| `DATA_DAT` | 数据日期切片 | 拼接表/汇总表 |

完整表结构与字段字典见 [references/table-dictionary.md](references/table-dictionary.md)。

## 三、执行流程

链路、各步输入输出、字段约定与降级条件详见 [references/INTERFACES.md](references/INTERFACES.md)。
这里只给可执行的命令。

### Step 0 · 环境

```bash
pip install duckdb pyarrow pandas openpyxl
python3 scripts/analyze_parquet.py --data-dir "数字员工工作区/数据文件duckdb/parquet"
```

校验：parquet 目录存在、表可读、duckdb/pyarrow 可用、切片日期有效。

### Step 1 · 取数（4 个脚本，产出 5 个 JSON）

```bash
DATA="数字员工工作区/数据文件duckdb/parquet"

python3 scripts/core_metrics_duckdb.py   --data-dir "$DATA" --slice 20260831 --out metrics.json
python3 scripts/core_overview_duckdb.py  --data-dir "$DATA" --slice 20260831 --out overview.json
python3 scripts/org_risk.py              --data-dir "$DATA" --slice 20260831 --out org_risk.json
python3 scripts/risk_features.py         --data-dir "$DATA" --slice 20260831 --out features.json
python3 scripts/cohort_attribution.py    --data-dir "$DATA" --slice 20260831 --out cohort.json
```

| 脚本 | 产出 | 内容 |
|------|------|------|
| `core_metrics_duckdb.py` | `metrics.json` | 全辖余额/不良余额/不良率/凭证数/客户数；按机构、客户经理、品种、担保方式分组；逾期天数分段 |
| `core_overview_duckdb.py` | `overview.json` | 四组对照（正常/关注/不良/其他）+ 8 大维度 × 档位的余额占比、不良率、恶化偏移 |
| `org_risk.py` | `org_risk.json` | 16 张机构级风险表：合同/客户/余额占比、不良率、线索级不良率、接续工具明细 |
| `risk_features.py` | `features.json` | 45 项基础风险特征命中的多键 metric + **全辖基线字典** |
| `cohort_attribution.py` | `cohort.json` | 客群切分（5 个单特征客群 + 5 个条件型客群）：规模、不良率、lift |

`risk_features.py` 的基线口径：率类指标的全辖值用**余额加权**（`Σ(率×余额)/Σ余额`），
不是各机构率的简单平均——机构规模有差异时两者并不相等。

### Step 2 · 归并扫线索（`signals.py`）

```bash
python3 scripts/signals.py \
  --features features.json --metrics metrics.json \
  --org-risk org_risk.json --overview overview.json \
  --cohort cohort.json --rules references/rules.json \
  --slice 20260831 --out signals.json
```

把四份取数产物归并成一份 `signals.json`：8 大维度档位、线索级不良率矩阵、特征与基线、
接续链、以及每条规则可匹配到的客群校验值。

### Step 3 · 归因引擎（`attribution.py`）

```bash
python3 scripts/attribution.py --signals signals.json \
  --rules references/rules.json --out attribution.json
```

- 按规则库（manual 13 / mined 17 / derived 12，共 42 条）计算强度、广度、signal
- 主题选择：`selected` / `candidate` / `rejected` 三态，每条规则附拒绝原因
- 强度公式：`strength = signal × (0.7 + 0.3 × breadth)`，`breadth = max_i(coverage_i)`

### Step 4 · 钻取（`drill_planner.py` → `drill_executor.py`）

```bash
# 生成给 LLM 的钻取提示词
python3 scripts/drill_planner.py --signals signals.json --attribution attribution.json \
  --rules references/rules.json --table-dict shared/table-dict.json --out drill_prompt.json

# 无 LLM 时的降级计划
python3 scripts/drill_planner.py --signals signals.json --attribution attribution.json \
  --rules references/rules.json --table-dict shared/table-dict.json \
  --out drill_plan.json --degrade

# 执行（SQL 白名单强校验）
python3 scripts/drill_executor.py --plan drill_plan.json \
  --table-dict shared/table-dict.json --mock-db --out evidence.json
```

### Step 5 · 叙述（`narrative.py`）

```bash
# 给 LLM 的提示词
python3 scripts/narrative.py --evidence evidence.json --signals signals.json \
  --attribution attribution.json --out narrative_prompt.json

# 无 LLM 时的降级模板
python3 scripts/narrative.py --evidence evidence.json --signals signals.json \
  --attribution attribution.json --out narrative.json --degrade
```

**LLM 边界**：脚本只输出提示词，由外部 Agent 调用模型，脚本内不调用任何 API。
无 LLM 结果时 Step 4/5 必须走 `--degrade`，这是全链路离线跑通的前提。

### Step 6 · 渲染报告（`render_report.py`）

```bash
python3 scripts/render_report.py \
  --attribution attribution.json --metrics metrics.json --signals signals.json \
  --narrative narrative.json --evidence evidence.json --drill-plan drill_plan.json \
  --overview overview.json --cohort cohort.json \
  --out-dir ./output
```

产出三件：

- `report.html` — 单文件自包含，断网可开、可打印
  - 每个主题用 `<section data-topic-id="T001…">` 标记，编号全文唯一、容器不嵌套
  - 每个统计数据用 `<span data-calc-id="D001…">` 标记，编号全文唯一
  - 结构：总览 → 成因分析 → 资产质量现象 → 管理策略 → 风险警示
- `数据验算清单.xlsx` / `.md` — 与 `data-calc-id` 一一对应，4 列：
  数据编号 | 网页展示结果 | 数据来源 | 计算代码或SQL
- `summary.md` — 一页纸摘要

### 一键跑通

Windows / macOS / Linux 一致，全部用 Python 入口（不依赖 bash）：

```bat
python tools\run_chain.py synth\dataset_01 work01      :: 单数据集全链路
python tools\build_preview.py                          :: 4 数据集批量出报告
```

```bash
python tools/run_chain.py synth/dataset_01 /tmp/work01  # 同上，Linux/macOS
python tools/build_preview.py
```

解释器：默认用运行 `run_chain.py` 的那个 Python；需要指定时设环境变量
`POST_LOAN_PY`。**不再依赖 shell 探测 `.venv` / `venv`** —— Windows 下
`.venv\Scripts\python.exe` 与 POSIX 的路径完全不同，靠猜容易出错。

真实数据：设 `DATA_DIR=<parquet目录>`；可选 `BASE_SLICE`（chg 口径对比时点）、
`LEVEL`（chg/vch）、`SLICE`（分析时点）、`COHORTS`。不设 `DATA_DIR` 时整条链
走 dry-run，只校验 SQL、不产出任何数字，报告会显式标注证据未执行。

## 四、报告结构

报告第一屏是总览 + 成因链，不是统计表格、不是 Top N 排行、不是基础风险清单。
评分/排行/基础清单只放《指标验算清单》。方法论见 [references/attribution-methodology.md](references/attribution-methodology.md)。

| 章节 | 内容 | 数据来源 |
|------|------|----------|
| 一、总览 | 口径说明 + KPI + 4 个现象描述（逾期结构/风险集中度/组合信号/平滑项） | metrics + insights |
| 二、成因分析 | 每条成因：可能的成因 → 触发特征组合 → 证据链 → 待验证项 | strong_insights |
| 三、资产质量现象分析 | 表观不良 vs 真实生成、平滑项暴露（展期/续贷/核销/转让）、逾期→不良迁移缓冲 | overall + exd_seg |
| 四、管理策略建议 | 四象限动作，6 字段（动作/责任岗/时限/验证指标/基线/目标） | actions |
| 五、风险警示 | 数据缺失、证据不足、口径降级提示 | warnings |

**报告纪律**

- 不单列 Top10 排行：集中度只在总览用一句话描述
- 不单列基础风险清单：45 项基础特征只作为成因的证据
- 成因必须带证据链：每条给「现象 → 直接原因 → 管理根因 → 可干预点」，标注依据等级
- 慎下因果：汇总级只做可加分解（流量桥/结构分解/漏斗），因果表述注明滞后期假设
- 主动暴露平滑项：展期/无还本续贷/核销/批量转让同时影响规模与不良读数

## 五、视觉规则

1. **白底简约**：页面 `#ffffff`，备用区 `#f8fafc`；无深色主题、无背景动效
2. **衬色唯一为青绿（teal）**：主 `#0f766e` / `#14b8a6`，浅 `#ccfbf1` / `#f0fdfa`，深字 `#134e4a`
3. **不得有其他花色块**：红/橙/紫/蓝/黄一律禁止。状态只用青绿深浅 + 灰阶表达，
   警示用「⚠ 提示」文字 + 浅青绿底卡片，不用红色块
4. **文字层级**：标题 `#0f172a`、正文 `#334155`、次要 `#64748b`
5. **卡片**：白底 + `1px solid #e2e8f0` 边框 + 轻阴影 + 12px 圆角
6. **表格**：表头浅青绿底 + 深青绿字，行间细线 `#f1f5f9`，数字列右对齐
7. **图表**：条形图青绿渐变，轨道灰
8. **打印友好**：`@media print` A4 适配，白底、去阴影、表头跨页重复

实现集中在 `scripts/render_report.py` 顶部 `CSS` 常量。

## 六、反模式

1. **忘记过滤 A70** — 把个人贷款混入农户统计，口径全错
2. **大表全量读入内存** — GB 级表必须走 DuckDB 聚合
3. **把逾期当不良** — 逾期 ≠ 不良，不良只算风险分类 3/4/5
4. **用缺失表硬算** — 无数据文件的表用机构级预聚合口径或标缺失，不得编造
5. **忽略切片** — 凭证表含 6 个切片，不指定 `DATA_DAT` 会重复计数
6. **用笔数代替金额** — 贡献度按不良余额计算，不用合同数
7. **报告出现技术数据** — 表名/id/字段名只进验算清单
8. **写死主题** — 主题必须由数据驱动
9. **报告出现 0 统计** — 统计为 0/None 的指标不展示
10. **给不同口径的指标硬套全辖不良率当基线** — 只有「不良率」类指标与全辖不良率同构。
    通过率、未办结率、逾期占比的分母语义完全不同，套用会得到假的强度值
11. **维度档位不做最小样本过滤** — 余额极小的档位（如单笔 2000 元）恰好 100% 不良时，
    会顶到排名第一。余额低于全辖 0.1% 的档位必须标 `valid=false` 排除
12. **把不良定义来源字段当解释变量** — 五级分类、核销状态本身就是不良的判定依据，
    用它们算不良率分布属循环论证

## 七、自检清单

1. 所有凭证级指标是否都过滤了 `BUS_BREED_CD LIKE 'A70%'`？
2. 不良判定是否用 `RSK_CLS_CD LIKE '3%'/'4%'/'5%'`（非仅逾期）？
3. 是否指定了切片日期，且无重复计数？
4. 大表是否走 DuckDB 聚合，未全量载入内存？
5. 无数据表的特征是否标 `data_missing` 而非编造？
6. 报告中是否出现 0/None 统计？（应为 0 处）
7. 报告是否含 id/表名等技术数据？（应为 0 处）
8. 主题是否由数据驱动，未写死？
9. 视觉是否白底、仅青绿衬色、无其他花色块？
10. `report.html` 断网可开、可打印？验算清单每个指标有表名 + 字段 + 计算逻辑？

## 八、文件清单

### 脚本（`scripts/`）

| 文件 | 用途 |
|------|------|
| `analyze_parquet.py` | parquet 表概览（行数/列数/键字段） |
| `core_metrics_duckdb.py` | 核心指标（不良率/分组/逾期结构） |
| `core_overview_duckdb.py` | 总览 + 8 大维度恶化偏移 |
| `org_risk.py` | 机构级风险指标（16 张 `S_*_C4` 表） |
| `risk_features.py` | 45 项基础风险特征 + 全辖基线 |
| `cohort_attribution.py` | 客群切分 + 优质准入反推 |
| `signals.py` | 归并扫线索（S2） |
| `attribution.py` | 归因引擎（S3） |
| `drill_planner.py` | 钻取提示词 / 降级计划（S3b） |
| `drill_executor.py` | SQL 白名单校验 + 钻取执行（S4） |
| `narrative.py` | 证据链提示词 / 降级模板（S5） |
| `render_report.py` | HTML 报告 + 验算清单 + 摘要（S6） |
| `theme_mining.py` | 复合主题挖掘（Jaccard 预筛 + lift 验证） |
| `theme_deep_dive_duckdb.py` | 主题深挖（样本 → 关联 → 分组对比） |
| `selftest.py` | 引擎自测（不依赖真实数据） |
| `common.py` | 共享工具（表字典加载、JSON IO） |
| `llm_io.py` | 提示词/结果读写与校验 |
| `_degrade_text.py` | 降级叙述文案引擎 |
| `jargon.py` | 术语业务化替换 |
| `query_log.py` | 查询日志（内部记录，不入报告） |

### 参考（`references/`）

| 文件 | 用途 |
|------|------|
| `INTERFACES.md` | **中间产物接口契约**：各 JSON 字段约定与计算公式 |
| `rules.json` | 双源规则库（manual / mined / derived 共 42 条） |
| `risk-features-map.md` | 45 项特征 → 表/字段/命中判据映射 |
| `combination-insights.md` | 组合归因规则库 |
| `attribution-methodology.md` | 归因方法论（流量桥/结构分解/平滑项/证据链） |
| `decision-actions.md` | 四象限决策动作库 |
| `table-dictionary.md` | 表结构字典 |

### 其他

| 路径 | 用途 |
|------|------|
| `shared/table-dict.json` | 字段白名单唯一事实来源（`drill_executor` 强校验依赖） |
| `tools/run_chain.py` | 单数据集全链路（跨平台） |
| `tools/build_preview.py` | 4 数据集批量出报告（跨平台） |
| `tools/PREVIEW-CRITERIA.md` | 合成数据验收口径 |
| `synth/` | 4 套合成数据集 + 生成脚本 |
| `tests/local/` | **仅本地校验**，bash 版入口，不进交付包 |

## 九、依赖

`duckdb`（聚合）+ `pyarrow`（parquet）+ `pandas`（特征计算）+ `openpyxl`（xlsx 验算清单）+ 标准库。

金额用 `float` 保留 2 位（输出时格式化）。大表用 DuckDB SQL 全量聚合。

脚本行为约定：

- 输入文件不存在 → 退出码 2，不猜
- 必填字段缺失 → 写 `{{待补}}` + 标 `degraded: true`，继续
- 数值异常（负余额、分母 0）→ 记入 `warnings[]`
- 统计为 0/None 的指标不写入 metric
