# 任务 C / D 任务书（等 A、B 交付后启用）

## 前置

A 交付：`scripts/signals.py`、`references/rules.json`、`scripts/attribution.py`(v3.0)、`scripts/selftest.py`
B 交付：`scripts/drill_planner.py`、`scripts/drill_executor.py`、`scripts/narrative.py`、`scripts/llm_io.py`
已备好：`synth/make_synth.py`（4 套合成数据）、`preview/README.md`（验收口径）、`shared/CONTRACT.md`

---

## 任务 C：渲染与图表工程师（DeepSeek V4 Flash）

### 目标
重写 `scripts/render_report.py`，把报告从「固定四段套话」改成「数据 + narrative 驱动」，
并补上缺失的图表能力。**保留 data-topic-id / data-calc-id 双标签体系**（这是该 skill 最大资产）。

### 必做的 6 件事

1. **删掉硬截断**
   `render_report.py:284` 的 `topic_ins = insights[:4] if len(insights) >= 2 else insights`
   必须删除。改为读 `attribution.json` 的 `topic_selection[]`，只取 `decision=="selected"` 的。
   主题数量由数据决定，**0 条时走退化分支**（渲染「指标监测式」）。

2. **删掉四段硬编码文案**
   `render_report.py:444-462` 的 `finding` / `mechanism` / `impact` / `portrait` 是字符串模板。
   改为优先读 `narrative.json`（B 产出）的对应字段；无 narrative 时用**数据驱动模板**：
   - 按 `strength` 高低选措辞强度（≥0.7 用「集中暴露」、0.5–0.7 用「较为显著」、<0.5 用「存在一定迹象」）
   - 按 `cross_stage` 决定是否写「跨环节共振」
   - 按 `evidence_chain.status` 决定是否写「已通过客群校验」/「待验证」
   - **`impact` 段绝不能出现「建议在正式报告中…测算」这种 TODO 语气**，必须写真实客群不良贡献

3. **补 5 张图表（内联 SVG，单文件自包含）**
   - 逾期分段占比（堆叠横条）
   - 8 大维度恶化偏移（水平条形 + 0 基准线 + 正负着色，但**仍只能用青绿色系深浅 + 灰阶**，不能用红）
   - 线索类型不良率 vs 全辖基线（散点或条形 + 基线虚线）
   - 接续工具不良率对比（分组条形）
   - 主题客群 lift（条形）
   SVG 直接由 Python 字符串拼，不引 CDN、不引 JS 图表库。

4. **视觉规则不能破**
   白底 `#ffffff`、衬色仅青绿（`#0f766e`/`#14b8a6`/`#ccfbf1`/`#f0fdfa`/`#134e4a`）、
   无红橙紫蓝黄花色块、无毛玻璃/发光/hover 位移、`@media print` A4 适配。详见 `post-loan-analysis.md` 第五章。

5. **预览版「主题生成轨迹」折叠块**
   仅当传入 `--preview` 时渲染。用 `<details>` 折叠，内容：
   - 每条候选规则一行：rule_id / name / breadth / signal / strength / decision / reason
   - 钻取假设原文（来自 `drill_prompt.json` 或 `drill_plan.json`）
   - 客群校验：lift / n / status
   正式报告不含此块。

6. **验算清单对齐**
   `数据验算清单.xlsx` / `.md` 必须与 HTML 中每个 `data-calc-id` 一一对应，4 列：
   **数据编号 | 网页展示结果 | 数据来源 | 计算代码或SQL**。
   新增图表里的数字**也要**注册 calc-id（图表是数据展示，必须可验算）。

### 交付物
- `scripts/render_report.py`（重写）
- `preview/build_preview.sh`（一键跑 4 套数据出 4 份 HTML）
- `preview/dataset_0{1..4}.html`（4 份真实产物）
- `preview/README.md`（补充实测结论）

### 完成标准
- 4 份 HTML 全部生成，每份 >80KB（证明有实质内容 + 图表）
- `grep -c "data-calc-id" preview/dataset_01.html` > 50
- `dataset_01` 与 `dataset_02` 的主题标题集合**不相交**
- `dataset_03` 报告里出现「指标监测」，主题数 0
- HTML 内无 `<script src=`、无 `http://`、无 `https://`（断网可开证明）
- 把 4 份 HTML 的主题标题列表贴进交付说明

---

## 任务 D：验证工程师（DeepSeek V4 Flash）

### 目标
**独立**验证 A/B/C 的交付，不许相信它们的自测。自己写验证脚本，自己造对抗用例。

### 必做的验证

1. **T1 主题随数据变（最高优先级）**
   跑 A 的 `attribution.py` 分别处理 `synth/dataset_01` 和 `synth/dataset_02`，
   对比输出的 `topic_selection` 中被选中规则的 `rule_id` 集合，**两者必须不同**。
   同时用**旧版** `attribution.py`（从 `/tmp/post-loan-analysis/scripts/attribution.py` 取）
   跑同样两套数据，证明旧版给出相同结果 —— 这是「缺陷已修复」的对照证据。

2. **T2 强度区分度**
   构造两个极端用例：
   - U1：5 成员规则命中 2 个，但这两个成员偏离基线 3 倍
   - U2：3 成员规则全部命中，但偏离基线只有 0.1
   断言 `strength(U1) > strength(U2)` 或至少 `signal(U1) > signal(U2)` 且 `U1.strength` 显著高于旧版纯 hit_ratio 算法给出的值。

3. **T3 白名单强校验**
   往 `drill_plan.json` 里塞三条恶意 plan：
   - 表名不存在（`FROM FAKE_TABLE`）
   - 字段名不存在（`SELECT NOT_A_FIELD FROM G_00PF_PEAS_LN_VCH_DV`）
   - 写操作（`DELETE FROM ...`）
   断言三条全部被判 invalid，reason 正确，且**没有被静默修正**。

4. **T4 降级链路**
   `dataset_04`（无 cohort）跑完整链路，断言：
   - 不崩
   - 无主题标记为「显著」
   - 报告里有降级说明

5. **T5 标签完整性**
   解析 `preview/dataset_01.html`：
   - 所有 `data-calc-id` 值唯一（无重复）
   - 所有 `data-topic-id` 值唯一且不嵌套
   - 验算清单行数 ≥ HTML 中 calc-id 数量

6. **T6 断网自包含**
   断言 HTML 中无外部资源引用。

7. **T7 语法与可运行性**
   全部脚本 `python3 -m py_compile` 通过；所有 `--help` 可用。

### 交付物
- `tests/verify.py`（纯标准库，一条命令跑全部 T1–T7，输出 PASS/FAIL 表）
- `tests/REPORT.md`（真实验证报告，含每项的实测值与判定）

### 完成标准
- `python3 tests/verify.py` 输出全 PASS，把真实输出贴进交付说明
- 若有 FAIL，如实报告，**不要为了全绿而放宽断言**
