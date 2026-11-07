#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_preview.py — 一键产出 4 份预览报告 + 验算清单

跨平台版：Windows / macOS / Linux 都直接跑，不依赖 bash。

用法
----
    python tools/build_preview.py [输出根目录，默认 <临时目录>/post_loan_preview]

合成数据只需链路可跑通；真实数据请先设环境变量 DATA_DIR=<parquet目录>，
否则钻取走 dry-run（不出数字），报告会显式标注证据未执行。
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Windows 控制台默认 GBK，直接 print 中文会抛 UnicodeEncodeError。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
SCRIPTS = ROOT / "scripts"


def main():
    py = os.environ.get("POST_LOAN_PY") or sys.executable
    out_root = Path(sys.argv[1] if len(sys.argv) > 1
                    else Path(tempfile.gettempdir()) / "post_loan_preview").resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    print(f"解释器: {py}")
    try:
        import openpyxl  # noqa: F401
        print("  openpyxl: 可用（将产出 xlsx 验算清单）")
    except ImportError:
        print("  openpyxl: 缺失（只产出 md 验算清单）")

    env = dict(os.environ, POST_LOAN_PY=py)
    results = {}

    for n in ("01", "02", "03", "04"):
        d = ROOT / "synth" / f"dataset_{n}"
        w = out_root / f"work_{n}"
        print(f"\n=========== dataset_{n} ===========")
        if not d.is_dir():
            print(f"跳过 dataset_{n}：目录不存在")
            continue

        proc = subprocess.run([py, str(TOOLS / "run_chain.py"), str(d), str(w)],
                              capture_output=True, text=True, env=env)
        if proc.returncode != 0:
            print(f"  链路失败（退出码 {proc.returncode}），跳过")
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()
            if tail:
                print("  " + tail[-1])
            continue

        rep = subprocess.run(
            [py, str(SCRIPTS / "render_report.py"),
             "--attribution", "attribution.json",
             "--metrics", "metrics.json",
             "--signals", "signals.json",
             "--narrative", "narrative.json",
             "--evidence", "evidence.json",
             "--drill-plan", "drill_plan.json",
             "--overview", "overview.json",
             "--cohort", "cohort.json",
             "--preview",
             "--out-dir", str(out_root / f"report_{n}")],
            cwd=str(w), capture_output=True, text=True, env=env)
        for line in (rep.stdout or "").rstrip().splitlines():
            print("  " + line)
        if rep.returncode != 0:
            err = (rep.stderr or "").strip().splitlines()
            print(f"  渲染失败（退出码 {rep.returncode}）" + (f"：{err[-1]}" if err else ""))
            continue
        results[n] = out_root / f"report_{n}" / "report.html"

    print("\n=========== 产物 ===========")
    for n in ("01", "02", "03", "04"):
        f = results.get(n)
        if not f or not f.exists():
            print(f"  dataset_{n}: 未生成")
            continue
        html = f.read_text(encoding="utf-8", errors="ignore")
        cids = set()
        import re
        for m in re.finditer(r'data-calc-id="([^"]*)"', html):
            cids.add(m.group(1))
        print(f"  dataset_{n}: {f.stat().st_size:>7} bytes | "
              f"SVG {html.count('<svg')} | "
              f"calc-id {html.count('data-calc-id')}(唯一 {len(cids)}) | "
              f"topic-id {html.count('data-topic-id')}")
    print(f"\n产物目录: {out_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
