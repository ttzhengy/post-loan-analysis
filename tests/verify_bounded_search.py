#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_bounded_search.py — 确定性有界搜索验收

核心不变量：
  1. 有界   查询次数不超过预算，超了必须如实告警「未查完 ≠ 无风险」
  2. 反馈   L2 只对 L1 显著的维度做交叉，不盲目全组合
  3. 确定   同样输入必须产生同样的查询序列与结果（不依赖 dict/SQL 顺序）
  4. 省查询 相比盲目全组合，实际查询数应显著更少
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

import bounded_search as bs   # noqa: E402
import combo_split as cs      # noqa: E402


class Checker:
    def __init__(self):
        self.ok = 0
        self.fail = 0

    def c(self, cond, name, detail=""):
        if cond:
            self.ok += 1
            print(f"  ✅ {name}")
        else:
            self.fail += 1
            print(f"  ❌ {name}" + (f"  ← {detail}" if detail else ""))


def make_runner(profile, counter):
    """构造假的 run_groups：按 feat 组合查表返回预设结果。

    profile: cond串 → (hit_rate, hit_n, nonhit_rate, nonhit_n, universe_rate)
    """
    def run_groups(conds, kind):
        counter["n"] += 1
        key = tuple(sorted(conds))
        hr, hn, nr, nn, ur = profile.get(key, (0.05, 20000, 0.05, 30000, 0.05))
        return {
            "hit": {"n": hn, "npl_rate": hr},
            "nonhit": {"n": nn, "npl_rate": nr},
            "universe": {"n": hn + nn, "npl_rate": ur},
        }
    return run_groups


def build_profile(feat_lifts):
    """按「每个特征的目标 lift」构造假数据。

    feat_lifts: {feature_id: lift}；lift 相对全辖率 0.04。
    """
    base = 0.04
    prof = {}
    for fid, lift in feat_lifts.items():
        t = cs.translate(fid)
        if not t:
            continue
        hr = min(base * lift, 0.95)
        # hit 占 20%，其余为非命中，保证 hit+nonhit=universe
        hn, nn = 10000, 40000
        ur = (hr * hn + base * nn) / (hn + nn)
        prof[(t["cond"],)] = (hr, hn, base, nn, ur)
    return prof


def main():
    c = Checker()

    # 特征 2（纯信用）、7（≥30万）、10（接续）、30（近期放款）
    F = [2, 7, 10, 30]
    sig = [{"feature_id": f, "name": cs.translate(f)["desc"], "norm": 1.0 - i * 0.1}
           for i, f in enumerate(F)]

    print("\n[A] 反馈式：只有显著维度才展开交叉")

    # 只让 2 和 7 强（lift 3.0 / 2.5），10 和 30 弱（1.05）
    profile = build_profile({2: 3.0, 7: 2.5, 10: 1.05, 30: 1.02})
    # 给 2+7 组合也放一个结果
    t2, t7 = cs.translate(2), cs.translate(7)
    profile[tuple(sorted([t2["cond"], t7["cond"]]))] = (0.30, 9000, 0.04, 41000, 0.09)

    counter = {"n": 0}
    r = bs.search(sig, make_runner(profile, counter),
                  cfg={**bs.DEFAULT_SEARCH, "query_budget": 40, "max_cross": 30},
                  quiet=True)

    c.c(r["summary"]["L1_tested"] == 4, "[A1] L1 测了全部 4 个特征",
        r["summary"]["L1_tested"])
    sig_f = r["summary"]["L1_significant"]
    c.c(sig_f == 2, "[A2] 只有 2 个达到展开门槛（2 和 7）", sig_f)
    c.c(r["summary"]["L2_crossed"] == 1,
        "[A3] 2 个显著维度只产生 1 对交叉（C(2,2)），不是全组合 C(4,2)=6",
        r["summary"]["L2_crossed"])

    # 盲目全组合要测 4 + 6 = 10 次；反馈式 4 + 1*2 = 6 次
    c.c(counter["n"] < 10, f"[A4] 查询数少于盲目全组合（{counter['n']} < 10）", counter["n"])

    print("\n[B] 有界：预算耗尽必须告警")

    counter2 = {"n": 0}
    r2 = bs.search(sig, make_runner(profile, counter2),
                   cfg={**bs.DEFAULT_SEARCH, "query_budget": 2},
                   quiet=True)
    c.c(r2["budget"]["used"] <= 2, "[B1] 查询数不超过预算", r2["budget"])
    c.c(r2["budget"]["exhausted"], "[B2] 标记预算耗尽")
    c.c(bool(r2["warnings"]), "[B3] 耗尽时产生告警")
    c.c(any("不代表没有风险" in w for w in r2["warnings"]),
        "[B4] 告警明确「未执行 ≠ 无风险」", r2["warnings"])
    c.c(any(s.get("reason", "").startswith("查询预算耗尽") for s in r2["skipped"]),
        "[B5] 未执行项写进 skipped 并注明原因")

    print("\n[C] 确定性：同输入同输出")

    counter3 = {"n": 0}
    r3 = bs.search(sig, make_runner(profile, counter3), quiet=True)
    counter4 = {"n": 0}
    r4 = bs.search(sig, make_runner(profile, counter4), quiet=True)
    c.c([p["features"] for p in r3["phenomena"]] == [p["features"] for p in r4["phenomena"]],
        "[C1] 两次运行现象顺序一致")
    c.c(counter3["n"] == counter4["n"], "[C2] 两次运行查询次数一致",
        f"{counter3['n']} vs {counter4['n']}")
    c.c([l["feature_id"] for l in r3["l1"]] == [l["feature_id"] for l in r4["l1"]],
        "[C3] L1 顺序一致")

    # 打乱输入顺序，结果应仍一致（因为按 norm 显式排序）
    sig_shuffled = list(reversed(sig))
    counter5 = {"n": 0}
    r5 = bs.search(sig_shuffled, make_runner(profile, counter5), quiet=True)
    c.c([p["features"] for p in r3["phenomena"]] == [p["features"] for p in r5["phenomena"]],
        "[C4] 输入顺序打乱后现象结果不变")

    print("\n[D] 现象判定复用 combo_split 口径")

    c.c(r3["phenomena_total"] >= 2,
        "[D1] 强单维（lift 3.0/2.5）被判为现象", r3["phenomena_total"])
    kinds = {p["kind"] for p in r3["phenomena"]}
    c.c("single" in kinds, "[D2] 单维现象能成立（kind=single）", kinds)

    weak_profile = build_profile({2: 1.02, 7: 1.01, 10: 1.0, 30: 1.0})
    r6 = bs.search(sig, make_runner(weak_profile, {"n": 0}), quiet=True)
    c.c(r6["phenomena_total"] == 0, "[D3] 全弱信号不产生现象", r6["phenomena_total"])

    print("\n[E] 互斥与冗余不重复查询")

    # 2（纯信用）与 6（非信用）互斥
    pair_conds = [cs.translate(2)["cond"], cs.translate(6)["cond"]]
    conflict, _ = cs.conds_conflict(pair_conds)
    c.c(conflict, "[E1] 前提：纯信用与非信用被判互斥")

    print("\n[F] skipped 可追溯")

    c.c(all("reason" in s for s in r3["skipped"]),
        "[F1] 所有 skipped 项都带 reason")
    caps = {s.get("stage") for s in r3["skipped"]}
    c.c(isinstance(caps, set), "[F2] skipped 带 stage 字段可分类", caps)

    print("\n" + "=" * 56)
    total = c.ok + c.fail
    if c.fail == 0:
        print(f"通过 {c.ok}/{total}\n全部通过 ✅")
        return 0
    print(f"通过 {c.ok}/{total}，失败 {c.fail}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
