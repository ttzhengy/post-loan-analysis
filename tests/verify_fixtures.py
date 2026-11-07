#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_fixtures.py — 阴阳性夹具验收集（判定「筛不出主题」是真零还是假阴性）

背景
----
现实 fixture 的 universe 生成率是 32%，而真实贷后不良生成率只有 1%~4%。
基率过高会把 lift 天花板压低（天花板 ≈ 1/基率），于是「全部 rejected」
既可能是「数据里确实没有风险聚集」，也可能是「被基率压死了」。
单看一份数据无法区分，必须用**一阴一阳**两份夹具做对照。

三组夹具的期望
--------------
  null     客户属性与不良完全独立 → 不得筛出任何现象（否则阈值形同虚设）
  weak     植入很弱的真实信号     → 可筛可不筛，但不得强断
  planted  植入强信号             → **必须**筛出，否则是假阴性

判据取流程自己的输出（combo_screen.json 的 phenomena_total），
不另立标准 —— 否则测的是夹具真值，不是流程的判别力。

用法
----
    python tests/verify_fixtures.py                    # 生成夹具并全跑
    python tests/verify_fixtures.py --skip-gen         # 复用已有夹具
    python tests/verify_fixtures.py --only null        # 只跑一组
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

FIXTURES = {
    "null":    {"dir": "/tmp/fx_null",    "expect_phenomena": 0, "label": "阴性（无信号）"},
    "weak":    {"dir": "/tmp/fx_weak",    "expect_phenomena": None, "label": "弱阳性（边界）"},
    "planted": {"dir": "/tmp/fx_planted", "expect_phenomena": ">0", "label": "阳性（强植入）"},
}


def run_fixture(kind, skip_gen, py):
    cfg = FIXTURES[kind]
    fdir = Path(cfg["dir"])
    if not skip_gen or not fdir.exists():
        print(f"   生成夹具 {kind} …")
        r = subprocess.run([py, str(ROOT / "tests" / "gen_fixture_eval.py"), kind, str(fdir)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            return None, f"夹具生成失败：{r.stderr[-300:]}"

    out = Path(f"/tmp/e2e_fx_{kind}")
    if out.exists():
        subprocess.run(["rm", "-rf", str(out)])
    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "POST_LOAN_PY": py,
        "DATA_DIR": str(fdir),
        "BASE_SLICE": "20260331",
        "LEVEL": "chg",
    }
    r = subprocess.run(
        [py, str(ROOT / "tools" / "run_chain.py"), "synth/dataset_01", str(out)],
        capture_output=True, text=True, env=env)
    if r.returncode != 0:
        return None, f"链路失败：{(r.stdout + r.stderr)[-400:]}"

    try:
        cs = json.load(open(out / "combo_screen.json", encoding="utf-8"))
        tg = json.load(open(out / "topic_gate.json", encoding="utf-8"))
        narr = json.load(open(out / "narrative.json", encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"产物不可读：{exc}"

    return {
        "phenomena": cs.get("phenomena_total") or 0,
        "status": cs.get("status_summary") or {},
        "gate_selected": len(((tg.get("selection") or {}).get("topics")) or []),
        "topics": len(narr.get("topics") or []),
        "phenomena_detail": [
            {"features": [f.get("feature_id") for f in (p.get("features") or [])],
             "hit_n": (p.get("metrics") or {}).get("hit_n"),
             "lift": (p.get("metrics") or {}).get("lift_vs_baseline"),
             "kind": (p.get("metrics") or {}).get("phenomenon_kind") or "combo"}
            for p in (cs.get("phenomena") or [])],
    }, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-gen", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--py", default=sys.executable)
    args = ap.parse_args()

    kinds = [args.only] if args.only else list(FIXTURES)
    results, fails = {}, 0

    for k in kinds:
        cfg = FIXTURES[k]
        print(f"\n── {k}：{cfg['label']} ──")
        res, err = run_fixture(k, args.skip_gen, args.py)
        if err:
            print(f"  ❌ {err}")
            fails += 1
            continue
        assert res is not None
        results[k] = res
        print(f"   phenomena={res['phenomena']}  闸门选中={res['gate_selected']}  "
              f"报告主题={res['topics']}")
        print(f"   status={json.dumps(res['status'], ensure_ascii=False)}")
        for d in res["phenomena_detail"][:5]:
            print(f"     ✓ {d['kind']} feats={d['features']} n={d['hit_n']} lift={d['lift']}")

        exp = cfg["expect_phenomena"]
        if exp == 0 and res["phenomena"] != 0:
            print(f"  ❌ 阴性夹具筛出了 {res['phenomena']} 条现象，阈值形同虚设")
            fails += 1
        elif exp == ">0" and res["phenomena"] <= 0:
            print("  ❌ 阳性夹具未筛出任何现象 —— 假阴性，强信号被漏掉")
            fails += 1
        else:
            print("  ✅ 符合预期")

    # 交叉断言：阴性不得产生报告主题；阳性若筛出现象则应能走通到报告
    if "null" in results:
        if results["null"]["topics"] != 0:
            print(f"\n❌ 阴性夹具仍产出 {results['null']['topics']} 条主题（确认偏误）")
            fails += 1
        else:
            print("\n✅ 阴性夹具未产出任何主题")
    if "planted" in results and results["planted"]["phenomena"] > 0:
        if results["planted"]["topics"] == 0:
            print("⚠️  阳性夹具筛出现象但报告无主题 —— 下游闸门/叙述可能过严")
        else:
            print(f"✅ 阳性夹具端到端产出 {results['planted']['topics']} 条主题")

    print("\n" + "=" * 60)
    if fails:
        print(f"夹具验收失败 {fails} 项")
        return 1
    print("夹具验收全部通过 ✅")
    print("   阴性不误报 · 阳性不漏报 · 弱阳性不硬断")
    return 0


if __name__ == "__main__":
    sys.exit(main())
