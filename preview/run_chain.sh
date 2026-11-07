#!/usr/bin/env bash
# run_chain.sh — 全链路跑批（S1→S6），已被验证可用
# 用法: bash run_chain.sh <数据集目录> <输出目录>
set -uo pipefail
# 不用 -e：单步失败要能看到错误并继续排查，而不是静默退出
SRC="${1:?需要数据集目录}"
OUT="${2:?需要输出目录}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"

rm -rf "$OUT"; mkdir -p "$OUT"
cp "$SRC"/*.json "$OUT"/

cd "$OUT"
# 上游 signals 备份：clue_matrix/continuation 已算好，重算时继承避免降级
cp signals.json upstream.json

echo "── S2 signals ──"
python3 "$ROOT/scripts/signals.py" \
  --features features.json --metrics metrics.json \
  --org-risk org_risk.json --overview overview.json \
  --signals-in upstream.json --cohort cohort.json \
  --rules "$ROOT/references/rules.json" \
  --slice 20260831 --out signals.json

echo "── S3 attribution ──"
python3 "$ROOT/scripts/attribution.py" \
  --signals signals.json --rules "$ROOT/references/rules.json" \
  --out attribution.json

echo "── S3b drill_planner（提示词，不调 LLM）──"
python3 "$ROOT/scripts/drill_planner.py" \
  --signals signals.json --attribution attribution.json \
  --rules "$ROOT/references/rules.json" \
  --table-dict "$ROOT/shared/table-dict.json" \
  --out drill_prompt.json

# 降级路径：无 LLM 时用规则 evidence_hint 生成默认 drill_plan（单独输出到 drill_plan.json）
python3 "$ROOT/scripts/drill_planner.py" \
  --signals signals.json --attribution attribution.json \
  --rules "$ROOT/references/rules.json" \
  --table-dict "$ROOT/shared/table-dict.json" \
  --out drill_plan.json --degrade

echo "── S4 drill_executor（白名单校验 + mock 执行）──"
# degrade 模式产出的默认 plan 放在 drill_prompt.json 同级的 drill_plan.json
python3 "$ROOT/scripts/drill_executor.py" \
  --plan drill_plan.json --table-dict "$ROOT/shared/table-dict.json" \
  --mock-db --out evidence.json

echo "── S5 narrative（降级模板，不调 LLM）──"
python3 "$ROOT/scripts/narrative.py" \
  --evidence evidence.json --signals signals.json --attribution attribution.json \
  --out narrative_prompt.json

# 降级叙述单独输出，供渲染层在无 LLM 时使用
python3 "$ROOT/scripts/narrative.py" \
  --evidence evidence.json --signals signals.json --attribution attribution.json \
  --out narrative.json --degrade

echo "── 产物 ──"
ls -1 *.json | sed 's/^/   /'
