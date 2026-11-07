#!/usr/bin/env bash
# run_chain.sh — 单数据集全链路（signals → attribution → drill → narrative）
# 用法: bash tools/run_chain.sh <数据集目录> <输出目录>
#
# 输入：数据集目录下的 metrics.json / overview.json / org_risk.json /
#       features.json / cohort.json / signals.json
# 输出：输出目录下的全部中间产物 + narrative.json
# 渲染报告不在本脚本内，见 tools/build_preview.sh 或直接调用 render_report.py
set -uo pipefail
# 不用 -e：单步失败要能看到错误并继续排查，而不是静默退出
SRC="${1:?需要数据集目录}"
OUT="${2:?需要输出目录}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"

# 解释器探测：环境变量 → 包内 venv → 系统 python3
PY="${POST_LOAN_PY:-}"
[ -n "$PY" ] && [ -x "$PY" ] || PY=""
if [ -z "$PY" ]; then
  for cand in "$ROOT/.venv/bin/python" "$ROOT/venv/bin/python" "$(command -v python3)"; do
    [ -x "$cand" ] && { PY="$cand"; break; }
  done
fi
[ -n "$PY" ] || { echo "错误：未找到可用的 python3"; exit 2; }

[ -d "$SRC" ] || { echo "错误：数据集目录不存在: $SRC"; exit 2; }

rm -rf "$OUT"; mkdir -p "$OUT"
cp "$SRC"/*.json "$OUT"/ 2>/dev/null || { echo "错误：$SRC 下没有 json 文件"; exit 2; }

cd "$OUT"
# 上游 signals 备份：clue_matrix/continuation 已算好，重算时继承避免降级
[ -f signals.json ] && cp signals.json upstream.json

echo "── S2 signals ──"
"$PY" "$ROOT/scripts/signals.py" \
  --features features.json --metrics metrics.json \
  --org-risk org_risk.json --overview overview.json \
  $( [ -f upstream.json ] && echo "--signals-in upstream.json" ) \
  $( [ -f cohort.json ] && echo "--cohort cohort.json" ) \
  --rules "$ROOT/references/rules.json" \
  --slice 20260831 --out signals.json || { echo "signals 失败"; exit 3; }

echo "── S2b combo_split（组合真实求交 + 回库取数）──"
# 这一步取代旧的「复用 cohort/comparisons 数字」做法：每个风险指标组合都
# 重新回凭证表求交集，hit / nonhit / universe 三组由同一条 SQL 产出。
# 默认 chg（不良生成率）口径：归因回答的是「同期谁新变坏」，
# 存量不良率里混着历史包袱与账龄效应，不能用来解释「为什么会坏」。
# BASE_SLICE 不给时由脚本自动取分析时点之前的最近一个可用切片；
# 找不到对比时点会显式回退 vch 并把原因写进 warnings，不会静默降级。
BASE_SLICE="${BASE_SLICE:-}"
LEVEL="${LEVEL:-chg}"
if [ -n "${DATA_DIR:-}" ] && [ -d "${DATA_DIR:-}" ]; then
  echo "   模式：execute（真实查询 $DATA_DIR，口径 $LEVEL）"
  "$PY" "$ROOT/scripts/combo_split.py" \
    --signals signals.json --slice 20260831 --level "$LEVEL" \
    ${BASE_SLICE:+--base-slice "$BASE_SLICE"} \
    --data-dir "$DATA_DIR" \
    --rules "$ROOT/references/rules.json" \
    --out combo_screen.json || echo "   ⚠️ combo_split 失败（不中断链路）"
else
  echo "   模式：dry-run（未提供 DATA_DIR，仅产出候选组合与 SQL）"
  "$PY" "$ROOT/scripts/combo_split.py" \
    --signals signals.json --slice 20260831 --level "$LEVEL" \
    ${BASE_SLICE:+--base-slice "$BASE_SLICE"} \
    --rules "$ROOT/references/rules.json" \
    --out combo_screen.json || echo "   ⚠️ combo_split 失败（不中断链路）"
fi

echo "── S3 attribution ──"
"$PY" "$ROOT/scripts/attribution.py" \
  --signals signals.json --rules "$ROOT/references/rules.json" \
  --out attribution.json || { echo "attribution 失败"; exit 3; }

echo "── S3b drill_planner（提示词，不调 LLM）──"
"$PY" "$ROOT/scripts/drill_planner.py" \
  --signals signals.json --attribution attribution.json \
  --rules "$ROOT/references/rules.json" \
  --table-dict "$ROOT/shared/table-dict.json" \
  --out drill_prompt.json

# 降级路径：无 LLM 时用规则 evidence_hint 生成默认 drill_plan
"$PY" "$ROOT/scripts/drill_planner.py" \
  --signals signals.json --attribution attribution.json \
  --rules "$ROOT/references/rules.json" \
  --table-dict "$ROOT/shared/table-dict.json" \
  --out drill_plan.json --degrade

echo "── S4 drill_executor（白名单校验 + 真实执行）──"
# 有 --data-dir 时真实查 DuckDB；没有时只做白名单校验（dry-run），
# 绝不默认用 mock —— mock 的数字会混进报告被当成真实结论。
if [ -n "${DATA_DIR:-}" ] && [ -d "${DATA_DIR:-}" ]; then
  echo "   模式：execute（真实查询 $DATA_DIR）"
  "$PY" "$ROOT/scripts/drill_executor.py" \
    --plan drill_plan.json --table-dict "$ROOT/shared/table-dict.json" \
    --data-dir "$DATA_DIR" --slice 20260831 --metrics metrics.json --out evidence.json
else
  echo "   模式：dry-run（未提供 DATA_DIR，仅校验 SQL 白名单，不产出数字）"
  "$PY" "$ROOT/scripts/drill_executor.py" \
    --plan drill_plan.json --table-dict "$ROOT/shared/table-dict.json" \
    --dry-run --metrics metrics.json --out evidence.json
fi

echo "── S4b topic_gate（两道校验 + 主题名额）──"
# 第一道：组合是否构成风险现象（复用 combo_screen 的判定结果，不重算）
# 第二道：现象与归因是否确实相关/可解释（用钻取实测数字检验四个条件）
# 名额：上限 10，**不设下限** —— 通过几个报几个，不放宽门槛凑数。
"$PY" "$ROOT/scripts/topic_gate.py" \
  --combo-screen combo_screen.json --evidence evidence.json \
  --attribution attribution.json --max-topics 10 \
  --out topic_gate.json || echo "   ⚠️ topic_gate 失败（不中断链路）"

echo "── S4c mitigate（风险下可贷：高危客群内部缓释分层）──"
# 只回答「哪里不能放」是半个结论。这一步在已确认的高风险客群内部
# 再按担保/逾期/金额/接续等维度分层，给出「照常 / 附条件 / 暂停」三档，
# 并必须同时给出保护性履约敞口占比与暂停档潜在误伤规模。
# 客群来源：topic_gate 入选主题的 hit 条件；无入选主题时整步跳过。
if [ -f topic_gate.json ] && [ -n "${DATA_DIR:-}" ] && [ -d "${DATA_DIR:-}" ]; then
  "$PY" "$ROOT/scripts/mitigate_batch.py" \
    --topic-gate topic_gate.json --combo-screen combo_screen.json \
    --slice 20260831 --level "$LEVEL" \
    ${BASE_SLICE:+--base-slice "$BASE_SLICE"} \
    --data-dir "$DATA_DIR" --out mitigate.json \
    || echo "   ⚠️ mitigate 失败（不中断链路）"
else
  echo "   跳过：无 topic_gate.json 或未提供 DATA_DIR"
fi

echo "── S4d internal_external（内部 / 外部 / 未识别三分）──"
# 外部用「超额」而非「标记」：有标记组的实际新增不良减去
# 「按同口径基准生成率本来也会坏的部分」，剩下的超额才算外部冲击。
# 三分账必须精确加总等于全辖新增不良，否则标为 broken 不进报告。
if [ -n "${DATA_DIR:-}" ] && [ -d "${DATA_DIR:-}" ]; then
  "$PY" "$ROOT/scripts/internal_external.py" \
    --slice 20260831 --level "$LEVEL" \
    ${BASE_SLICE:+--base-slice "$BASE_SLICE"} \
    --data-dir "$DATA_DIR" \
    ${COHORTS:+--cohorts "$COHORTS"} \
    --out internal_external.json || echo "   ⚠️ internal_external 失败（不中断链路）"
else
  echo "   跳过：未提供 DATA_DIR"
fi

echo "── S5 narrative（降级模板，不调 LLM）──"
"$PY" "$ROOT/scripts/narrative.py" \
  --evidence evidence.json --signals signals.json --attribution attribution.json \
  --out narrative_prompt.json

# 降级叙述单独输出，供渲染层在无 LLM 时使用
"$PY" "$ROOT/scripts/narrative.py" \
  --evidence evidence.json --signals signals.json --attribution attribution.json \
  --out narrative.json --degrade

echo "── 产物 ──"
ls -1 *.json | sed 's/^/   /'
