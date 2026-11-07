#!/usr/bin/env bash
# build_preview.sh — 一键产出 4 份预览报告 + 验算清单
# 用法: bash tools/build_preview.sh [输出根目录，默认 /tmp/post_loan_preview]
#   合成数据只需链路可跑通；真实数据请先 export DATA_DIR=<parquet目录>，
#   否则钻取走 dry-run（不出数字），报告会显式标注证据未执行。
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
OUT_ROOT="${1:-/tmp/post_loan_preview}"

# 解释器探测：环境变量 → 包内 venv → 系统 python3
PY="${POST_LOAN_PY:-}"
[ -n "$PY" ] && [ -x "$PY" ] || PY=""
if [ -z "$PY" ]; then
  for cand in "$ROOT/.venv/bin/python" "$ROOT/venv/bin/python" "$(command -v python3)"; do
    [ -x "$cand" ] && { PY="$cand"; break; }
  done
fi
[ -n "$PY" ] || { echo "错误：未找到可用的 python3"; exit 2; }
echo "使用解释器: $PY"

if "$PY" -c "import openpyxl" 2>/dev/null; then
  echo "  openpyxl: 可用（将产出 xlsx 验算清单）"
else
  echo "  openpyxl: 缺失（只产出 md 验算清单）"
fi

mkdir -p "$OUT_ROOT"

for n in 01 02 03 04; do
  d="$ROOT/synth/dataset_$n"
  w="$OUT_ROOT/work_$n"
  [ -d "$d" ] || { echo ""; echo "跳过 dataset_$n：目录不存在"; continue; }
  echo ""
  echo "=========== dataset_$n ==========="
  bash "$HERE/run_chain.sh" "$d" "$w" >/dev/null 2>&1 || { echo "  链路失败，跳过"; continue; }

  ( cd "$w" && "$PY" "$ROOT/scripts/render_report.py" \
      --attribution attribution.json \
      --metrics metrics.json \
      --signals signals.json \
      --narrative narrative.json \
      --evidence evidence.json \
      --drill-plan drill_plan.json \
      --overview overview.json \
      --cohort cohort.json \
      --preview \
      --out-dir "$OUT_ROOT/report_$n" ) 2>&1 | sed 's/^/  /'
done

echo ""
echo "=========== 产物 ==========="
for n in 01 02 03 04; do
  f="$OUT_ROOT/report_$n/report.html"
  if [ -f "$f" ]; then
    sz=$(stat -c%s "$f")
    svg=$(grep -c '<svg' "$f" 2>/dev/null || echo 0)
    cid=$(grep -o 'data-calc-id' "$f" 2>/dev/null | wc -l)
    uniq_cid=$(grep -o 'data-calc-id="[^"]*"' "$f" 2>/dev/null | sort -u | wc -l)
    tid=$(grep -o 'data-topic-id' "$f" 2>/dev/null | wc -l)
    printf "  dataset_%s: %6d bytes | SVG %s | calc-id %s(唯一 %s) | topic-id %s\n" \
      "$n" "$sz" "$svg" "$cid" "$uniq_cid" "$tid"
  else
    echo "  dataset_$n: 未生成"
  fi
done
echo ""
echo "产物目录: $OUT_ROOT"
