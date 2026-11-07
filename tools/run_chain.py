#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_chain.py — 单数据集全链路（signals → attribution → drill → narrative）

跨平台版：Windows / macOS / Linux 都直接跑，不依赖 bash。

用法
----
    python tools/run_chain.py <数据集目录> <输出目录>

环境变量（都可不设）
--------------------
    POST_LOAN_PY   指定解释器（默认用当前解释器，即运行本脚本的那个 python）
    DATA_DIR       真实数据目录（parquet/csv）。不设则整条链走 dry-run，
                   只校验 SQL、不产出任何数字 —— 绝不默认用 mock，
                   mock 的数字会混进报告被当成真实结论。
    BASE_SLICE     chg 口径的对比时点，如 20260331。不设则由 combo_split
                   自动取分析时点之前最近的一个可用切片。
    LEVEL          口径，chg（默认，不良生成率）/ vch（存量不良率）。
    COHORTS        客群 json 路径，传给 internal_external 做内部贡献分摊。
    SLICE          分析时点，默认 20260831。

退出码：0 成功；2 参数/环境错误；3 关键步骤失败。单个非关键步骤失败
只记警告不中断，便于一次看清全部问题。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Windows 控制台默认 GBK，直接 print 中文会抛 UnicodeEncodeError。
# 统一把标准输出改成 UTF-8，errors=replace 保证即使终端不支持也不会崩。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
RULES = ROOT / "references" / "rules.json"
TABLE_DICT = ROOT / "shared" / "table-dict.json"

SLICE_DEFAULT = "20260831"


def log(msg=""):
    print(msg or "", flush=True)


def step(title):
    log(f"── {title} ──")


def run(args, cwd=None, critical=False, quiet=False):
    """执行一步。critical=True 时失败退出，否则只记警告。

    args: list[str]，第 0 项是脚本路径或可执行名
    """
    cmd = [str(a) for a in args]
    if not quiet:
        log("   " + " ".join(Path(cmd[0]).name if i == 0 else c for i, c in enumerate(cmd)))
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None,
                          capture_output=True, text=True)
    if proc.stdout and not quiet:
        for line in proc.stdout.rstrip().splitlines():
            log("   " + line)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        if critical:
            log(f"❌ 失败（退出码 {proc.returncode}）")
            if err:
                log("   " + err.splitlines()[-1])
            sys.exit(3)
        log(f"   ⚠️  失败（退出码 {proc.returncode}，不中断链路）")
        if err:
            log("   " + err.splitlines()[-1])
        return False
    return True


def main():
    if len(sys.argv) < 3:
        log(__doc__)
        return 2

    src = Path(sys.argv[1]).expanduser().resolve()
    out = Path(sys.argv[2]).expanduser().resolve()
    if not src.is_dir():
        log(f"错误：数据集目录不存在: {src}")
        return 2

    py = os.environ.get("POST_LOAN_PY") or sys.executable
    data_dir = os.environ.get("DATA_DIR") or ""
    base_slice = os.environ.get("BASE_SLICE") or ""
    level = os.environ.get("LEVEL") or "chg"
    cohorts = os.environ.get("COHORTS") or ""
    slice_v = os.environ.get("SLICE") or SLICE_DEFAULT

    if data_dir and not Path(data_dir).is_dir():
        log(f"错误：DATA_DIR 不是目录: {data_dir}")
        return 2
    execute = bool(data_dir)

    log(f"解释器: {py}")
    log(f"数据集: {src}")
    log(f"输出:   {out}")
    log(f"模式:   {'execute（真实查询 ' + data_dir + '）' if execute else 'dry-run（未设 DATA_DIR，只校验不产数字）'}")
    log(f"口径:   {level}" + (f"，对比时点 {base_slice}" if base_slice else ""))
    log()

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    jsons = list(src.glob("*.json"))
    if not jsons:
        log(f"错误：{src} 下没有 json 文件")
        return 2
    for f in jsons:
        shutil.copy2(f, out / f.name)

    # 上游 signals 备份：clue_matrix/continuation 已算好，重算时继承避免降级
    if (out / "signals.json").exists():
        shutil.copy2(out / "signals.json", out / "upstream.json")

    step("S2 signals")
    args = [py, SCRIPTS / "signals.py",
            "--features", "features.json", "--metrics", "metrics.json",
            "--org-risk", "org_risk.json", "--overview", "overview.json",
            "--rules", RULES, "--slice", slice_v, "--out", "signals.json"]
    if (out / "upstream.json").exists():
        args += ["--signals-in", "upstream.json"]
    if (out / "cohort.json").exists():
        args += ["--cohort", "cohort.json"]
    run(args, cwd=out, critical=True)

    step("S2b combo_split（组合真实求交 + 回库取数）")
    log("   默认 chg（不良生成率）口径：归因回答「同期谁新变坏」，")
    log("   存量不良率混着历史包袱与账龄效应，不用于解释「为什么会坏」。")
    args = [py, SCRIPTS / "combo_split.py",
            "--signals", "signals.json", "--slice", slice_v, "--level", level,
            "--rules", RULES, "--out", "combo_screen.json"]
    if base_slice:
        args += ["--base-slice", base_slice]
    if execute:
        args += ["--data-dir", data_dir]
    run(args, cwd=out)

    step("S3 attribution")
    run([py, SCRIPTS / "attribution.py", "--signals", "signals.json",
         "--rules", RULES, "--out", "attribution.json"], cwd=out, critical=True)

    step("S3b drill_planner（提示词，不调 LLM）")
    common = [py, SCRIPTS / "drill_planner.py", "--signals", "signals.json",
              "--attribution", "attribution.json", "--rules", RULES,
              "--table-dict", TABLE_DICT]
    run(common + ["--out", "drill_prompt.json"], cwd=out)
    # 降级路径：无 LLM 时用规则 evidence_hint 生成默认 drill_plan
    run(common + ["--out", "drill_plan.json", "--degrade"], cwd=out)

    step("S4 drill_executor（白名单校验 + 真实执行）")
    log(f"   模式：{'execute（真实查询 ' + data_dir + '）' if execute else 'dry-run（仅校验 SQL 白名单，不产数字）'}")
    ex = [py, SCRIPTS / "drill_executor.py", "--plan", "drill_plan.json",
          "--table-dict", TABLE_DICT, "--metrics", "metrics.json",
          "--out", "evidence.json"]
    if execute:
        ex += ["--data-dir", data_dir, "--slice", slice_v]
    else:
        ex += ["--dry-run"]
    run(ex, cwd=out)

    step("S4b topic_gate（两道校验 + 主题名额）")
    run([py, SCRIPTS / "topic_gate.py", "--combo-screen", "combo_screen.json",
         "--evidence", "evidence.json", "--attribution", "attribution.json",
         "--max-topics", "10", "--out", "topic_gate.json"], cwd=out)

    step("S4c mitigate（风险下可贷：高危客群内部缓释分层）")
    log("   只回答「哪里不能放」是半个结论。这一步在已确认的高风险客群内部")
    log("   再分层，给出「照常 / 附条件 / 暂停」三档，并给出保护性履约敞口")
    log("   占比与暂停档潜在误伤规模。")
    if execute and (out / "topic_gate.json").exists():
        args = [py, SCRIPTS / "mitigate_batch.py",
                "--topic-gate", "topic_gate.json",
                "--combo-screen", "combo_screen.json",
                "--slice", slice_v, "--level", level,
                "--data-dir", data_dir, "--out", "mitigate.json"]
        if base_slice:
            args += ["--base-slice", base_slice]
        run(args, cwd=out)
    else:
        log("   跳过：无 topic_gate.json 或未设 DATA_DIR")

    step("S4d internal_external（内部 / 外部 / 未识别三分）")
    log("   外部用「超额」而非「标记」：有标记组的实际新增不良减去按基准")
    log("   生成率本来也会坏的部分，剩余超额才算外部冲击。三分账必须精确")
    log("   加总等于全辖新增不良，否则标 broken 不进报告。")
    if execute:
        args = [py, SCRIPTS / "internal_external.py",
                "--slice", slice_v, "--level", level,
                "--data-dir", data_dir, "--out", "internal_external.json"]
        if base_slice:
            args += ["--base-slice", base_slice]
        if cohorts:
            args += ["--cohorts", cohorts]
        run(args, cwd=out)
    else:
        log("   跳过：未设 DATA_DIR")

    step("S4e falsify（归因假设的可证伪检验）")
    log("   归因不能停在「哪类客户坏得多」。这一步对每个入选主题做四项检验：")
    log("   时间集中性、剂量反应、准入与贷后区分、客群资质对照。")
    log("   只有「未被推翻」的假设才进结论，被反驳的明确写出反驳理由。")
    if execute and (out / "topic_gate.json").exists() and base_slice:
        run([py, SCRIPTS / "falsify.py",
             "--topic-gate", "topic_gate.json",
             "--combo-screen", "combo_screen.json",
             "--slice", slice_v, "--base-slice", base_slice,
             "--data-dir", data_dir, "--out", "falsify.json"], cwd=out)
    else:
        log("   跳过：无 topic_gate.json / 未设 DATA_DIR / 缺 BASE_SLICE")

    step("S5 narrative（降级模板，不调 LLM）")
    nar = [py, SCRIPTS / "narrative.py", "--evidence", "evidence.json",
           "--signals", "signals.json", "--attribution", "attribution.json"]
    run(nar + ["--out", "narrative_prompt.json"], cwd=out)
    run(nar + ["--out", "narrative.json", "--degrade"], cwd=out)

    step("产物")
    for f in sorted(out.glob("*.json")):
        log(f"   {f.name}")
    log()
    log(f"✅ 链路完成 → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
