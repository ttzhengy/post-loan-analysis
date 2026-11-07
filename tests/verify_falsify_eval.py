#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_falsify_eval.py — falsify_if 条件对象化验收

核心不变量：
  1. 证伪条件可解析、可求值（不再是死字符串）
  2. 条件成立 → refuted，假设 nullified，不得进入结论
  3. 指标缺失 → indeterminate，**绝不允许退化成 survived**
  4. 回写字段完整，下游可读取假设状态
  5. 不使用 eval，只走白名单算子
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

import falsify_eval as fe   # noqa: E402


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


def main():
    c = Checker()
    print("\n[A] 自然语言条件解析")

    n = fe.normalize("lift < 1.2 或命中组样本 < 30")
    c.c(n is not None and len(n["any"]) == 2, "[A1] 解析出两个条件原子", str(n))
    if n:
        c.c(any(a["metric"] == "lift" and a["op"] == "<" and a["value"] == 1.2
                for a in n["any"]), "[A2] lift < 1.2 正确解析")
        c.c(any(a["metric"] == "hit_n" and a["value"] == 30 for a in n["any"]),
            "[A3] 样本 < 30 映射到 hit_n")

    n2 = fe.normalize("差异 < 1.5 倍或样本 < 30")
    c.c(n2 is not None and any(a["metric"] == "lift" and a["value"] == 1.5
                               for a in n2["any"]),
        "[A4] 「差异 < 1.5 倍」按 lift 口径解析", str(n2))

    c.c(fe.normalize("这句没有可判定的条件") is None,
        "[A5] 无法解析的文本返回 None，不静默当成无条件")

    print("\n[B] 条件对象直接传入")

    obj = {"any": [{"metric": "lift", "op": "<", "value": 1.2}]}
    c.c(fe.normalize(obj) is not None, "[B1] 已是对象则原样接受")

    bad = {"any": [{"metric": "DROP TABLE", "op": "<", "value": 1}]}
    c.c(fe.normalize(bad) is None, "[B2] 非白名单 metric 被拒（注入面）")

    bad2 = {"any": [{"metric": "lift", "op": "eval", "value": 1}]}
    c.c(fe.normalize(bad2) is None, "[B3] 非白名单算子被拒")

    print("\n[C] 求值三态")

    # hit 差于对照：lift=1.05 < 1.2 → 推翻
    st, d = fe.evaluate("lift < 1.2 或命中组样本 < 30",
                        {"n": 5000, "npl_rate": 0.21}, {"n": 20000, "npl_rate": 0.20})
    c.c(st == fe.STATUS_REFUTED, "[C1] lift 不达标 → refuted", f"{st} {d}")
    c.c(d.get("fired"), "[C2] 指出哪条条件触发推翻")

    # lift 达标、样本充足 → 未推翻
    st, d = fe.evaluate("lift < 1.2 或命中组样本 < 30",
                        {"n": 5000, "npl_rate": 0.40}, {"n": 20000, "npl_rate": 0.20})
    c.c(st == fe.STATUS_SURVIVED, "[C3] 条件全不成立 → survived", f"{st}")
    c.c("不等于已经证实" in (d.get("note") or ""),
        "[C4] survived 措辞明确「不等于证实」", d.get("note"))

    # 缺 npl_rate → 无法算 lift → indeterminate
    st, d = fe.evaluate("lift < 1.2", {"n": 5000}, {"n": 20000})
    c.c(st == fe.STATUS_INDETERMINATE,
        "[C5] 缺指标 → indeterminate（不得视为未推翻）", f"{st} {d}")
    c.c("缺数据不等于未被推翻" in (d.get("note") or ""),
        "[C6] indeterminate 明确写出「缺数据不等于未被推翻」", d.get("note"))

    # 条件为空
    st, d = fe.evaluate(None, {"n": 1, "npl_rate": 0.1}, {"n": 1, "npl_rate": 0.1})
    c.c(st == fe.STATUS_INDETERMINATE, "[C7] 空条件 → indeterminate", st)

    st, d = fe.evaluate({"any": []}, {}, {})
    c.c(st == fe.STATUS_INDETERMINATE, "[C8] 空条件对象 → indeterminate", st)

    print("\n[D] 指标计算")

    m = fe.metrics_from_comparison({"n": 1000, "npl_rate": 0.40},
                                   {"n": 4000, "npl_rate": 0.20})
    c.c(abs(m["lift"] - 2.0) < 1e-9, "[D1] lift = 2.0", m.get("lift"))
    c.c(abs(m["delta_pp"] - 20.0) < 1e-9, "[D2] delta_pp = 20", m.get("delta_pp"))
    c.c(m["p_value"] is not None and m["p_value"] < 0.05,
        "[D3] 显著差异 p < 0.05", m.get("p_value"))

    m2 = fe.metrics_from_comparison({"n": 10, "npl_rate": 0.1}, {"n": 10, "npl_rate": 0.1})
    c.c(m2["lift"] == 1.0, "[D4] 相同不良率 lift = 1.0", m2.get("lift"))

    m3 = fe.metrics_from_comparison({"n": 0, "npl_rate": None}, {"n": 0, "npl_rate": None})
    c.c(m3["lift"] is None, "[D5] 无数据时 lift 为 None（不是 0）", m3.get("lift"))

    print("\n[E] 回写")

    plan = {"plan_id": "P1", "falsify_if": "lift < 1.2"}
    out, st = fe.apply_to_plan(plan, {"n": 5000, "npl_rate": 0.10},
                               {"n": 20000, "npl_rate": 0.20})
    c.c(st == fe.STATUS_REFUTED, "[E1] 回写状态 refuted", st)
    c.c(out.get("falsify_result", {}).get("status") == fe.STATUS_REFUTED,
        "[E2] plan.falsify_result.status 已写入")
    c.c(out.get("hypothesis_status") == "nullified",
        "[E3] 假设状态置为 nullified", out.get("hypothesis_status"))
    c.c(plan.get("falsify_result") is None,
        "[E4] 不修改入参（返回新对象）")

    out2, st2 = fe.apply_to_plan({"falsify_if": "lift < 1.2"},
                                 {"n": 5000, "npl_rate": 0.40},
                                 {"n": 20000, "npl_rate": 0.20})
    c.c(out2.get("hypothesis_status") == "not_excluded",
        "[E5] 未推翻 → not_excluded（不是 confirmed）", out2.get("hypothesis_status"))

    out3, st3 = fe.apply_to_plan({"falsify_if": "lift < 1.2"}, {}, {})
    c.c(out3.get("hypothesis_status") == "undetermined",
        "[E6] 无法判定 → undetermined", out3.get("hypothesis_status"))

    print("\n[F] 安全：不使用 eval")

    src = Path(fe.__file__).read_text(encoding="utf-8")
    c.c("eval(" not in src.replace("falsify_eval(", ""),
        "[F1] 模块内无 eval 调用")
    c.c("exec(" not in src, "[F2] 模块内无 exec 调用")
    c.c("__import__" not in src, "[F3] 无动态导入")

    print("\n" + "=" * 56)
    total = c.ok + c.fail
    if c.fail == 0:
        print(f"通过 {c.ok}/{total}\n全部通过 ✅")
        return 0
    print(f"通过 {c.ok}/{total}，失败 {c.fail}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
