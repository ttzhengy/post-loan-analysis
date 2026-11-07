#!/usr/bin/env bash
# build_preview.sh — 一键产出 4 份预览 HTML + 验算清单
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"

# 优先用带 openpyxl 的 venv（xlsx 验算清单需要）；没有则退回系统 python（只出 md）
PY="/tmp/venv/bin/python"
[ -x "$PY" ] || PY="/tmp/venv/bin/python"
[ -x "$PY" ] || PY="python3"
echo "使用解释器: $PY"
"$PY" -c "import openpyxl" 2>/dev/null && echo "  openpyxl: 可用（将产出 xlsx）" || echo "  openpyxl: 缺失（只产出 md 验算清单）"

for n in 01 02 03 04; do
  d="$ROOT/synth/dataset_$n"
  w="/tmp/preview_work_$n"
  echo ""
  echo "=========== dataset_$n ==========="
  bash "$HERE/run_chain.sh" "$d" "$w" >/dev/null 2>&1 || { echo "链路失败"; continue; }

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
      --out-dir "$HERE/dataset_$n" ) 2>&1 | sed 's/^/  /'

  # 报告与验算清单统一放到 preview/dataset_0N/
done

echo ""
echo "=========== 产物 ==========="
for n in 01 02 03 04; do
  if [ -f "$HERE/dataset_$n/report.html" ]; then
    sz=$(stat -c%s "$HERE/dataset_$n/report.html")
    svg=$(grep -c '<svg' "$HERE/dataset_$n/report.html" 2>/dev/null || echo 0)
    cid=$(grep -o 'data-calc-id' "$HERE/dataset_$n/report.html" 2>/dev/null | wc -l)
    tid=$(grep -o 'data-topic-id' "$HERE/dataset_$n/report.html" 2>/dev/null | wc -l)
    printf "  dataset_%s: %6d bytes | SVG %s 张 | calc-id %s | topic-id %s\n" "$n" "$sz" "$svg" "$cid" "$tid"
  else
    echo "  dataset_$n: 未生成"
  fi
done
