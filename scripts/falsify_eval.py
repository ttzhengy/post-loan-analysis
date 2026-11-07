#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""falsify_eval.py — 把证伪条件从字符串变成可执行、可回写的条件对象

为什么需要这个模块
------------------
改造前 `falsify_if` 是一句自然语言：「lift < 1.2 或命中组样本 < 30」。
它出现在每个 drill plan 里，但**从来没有被任何代码读取或求值**：
  · 不可计算 —— 没有解析器，没人知道这句话怎么判定
  · 不可执行 —— 即使解析出来，也没有对应的实际指标绑定
  · 不可回写 —— 检验结果不会改变假设的状态，假设永远停在「待验证」

结果就是「可证伪」只是措辞，不是机制。一个假设即使被数据推翻，
报告里也不会体现。这正是评审指出的 P1 级缺陷。

条件对象的形状
--------------
{
  "any": [                      # any 内任一条件成立 → 假设被推翻
    {"metric": "lift",          "op": "<",  "value": 1.2},
    {"metric": "hit_n",         "op": "<",  "value": 30}
  ]
}

支持 metric（取自命中/对照组聚合结果）：
  lift        命中组不良率 / 对照组不良率
  hit_n       命中组客户数
  nonhit_n    对照组客户数
  hit_rate    命中组不良率
  nonhit_rate 对照组不良率
  delta_pp    命中组与对照组不良率之差（百分点）
  p_value     两组差异的显著性（z 检验）

设计取舍
--------
1. **只支持 any（或）**：证伪的语义是「任一硬条件不满足即推翻」，
   用与(and)会把推翻条件变得过严，等于变相保护假设。需要与关系时
   写成单条复合 metric，而不是引入 and 树。
2. **条件不可判定时返回 indeterminate，不返回「未推翻」**：
   缺 lift 就判「没被推翻」，是典型的确认偏误。无法判定必须如实说。
3. **不使用 eval**：条件来自 LLM 生成的 plan，任何形式的动态求值
   都是注入面。这里只做白名单算子和固定 metric 名。
"""
from __future__ import annotations

import math

# 允许的比较算子 —— 白名单，不做任何动态求值
OPS = {
    "<":  lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">":  lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "==": lambda a, b: abs(a - b) < 1e-9,
}

METRICS = {"lift", "hit_n", "nonhit_n", "hit_rate", "nonhit_rate",
           "delta_pp", "p_value"}

# 推翻判定的三态
STATUS_REFUTED = "refuted"          # 条件成立 → 假设被推翻
STATUS_SURVIVED = "survived"        # 条件不成立 → 假设未被推翻
STATUS_INDETERMINATE = "indeterminate"  # 数据不足，无法判定
STATUS_INVALID = "invalid"          # 条件对象本身有错


def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def z_test_two_prop(p1, n1, p2, n2):
    """两比例 z 检验，返回 p 值（双侧）。样本不足返回 None。"""
    n1, n2 = _num(n1), _num(n2)
    p1, p2 = _num(p1), _num(p2)
    if not all([n1, n2, p1, p2]) or n1 <= 0 or n2 <= 0:
        return None
    assert n1 is not None and n2 is not None and p1 is not None and p2 is not None
    pool = (p1 * n1 + p2 * n2) / (n1 + n2)
    se = (pool * (1 - pool) * (1 / n1 + 1 / n2)) ** 0.5
    if se <= 0:
        return None
    z = (p1 - p2) / se
    return 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))


def metrics_from_comparison(hit, nonhit):
    """从命中组/对照组聚合结果算出可判定的指标字典。

    hit/nonhit 是「跑完 SQL 得到的那一行」，形如
    {"n": 17715, "npl_rate": 0.409, "npl_bal": ..., "tot_bal": ...}
    """
    hr, nr = _num((hit or {}).get("npl_rate")), _num((nonhit or {}).get("npl_rate"))
    hn, nn = _num((hit or {}).get("n")), _num((nonhit or {}).get("n"))
    m = {
        "hit_n": hn, "nonhit_n": nn,
        "hit_rate": hr, "nonhit_rate": nr,
    }
    m["lift"] = (hr / nr) if (hr is not None and nr) else None
    m["delta_pp"] = ((hr - nr) * 100) if (hr is not None and nr is not None) else None
    m["p_value"] = z_test_two_prop(hr, hn, nr, nn)
    return m


def normalize(cond):
    """把各种写法的证伪条件统一成 {"any":[{metric,op,value}]}。

    接受：
      · 已是条件对象           → 原样返回（做合法性校验）
      · 单个条件字典           → 包成 any
      · 旧版自然语言字符串     → 尝试解析常见句式，解析不了返回 None
    """
    if cond is None:
        return None
    if isinstance(cond, dict):
        if "any" in cond:
            # 注意不能写 `{...} or None`：空 dict 是真值，`or None` 不生效，
            # 会返回 {"any": []} 让调用方误以为「条件已提供但全通过」。
            items = [x for x in (cond.get("any") or []) if _valid_atom(x)]
            if not items:
                return None
            return {"any": items}
        return {"any": [cond]} if _valid_atom(cond) else None
    if isinstance(cond, str):
        return parse_text(cond)
    return None


def _valid_atom(a):
    return (isinstance(a, dict)
            and a.get("metric") in METRICS
            and a.get("op") in OPS
            and _num(a.get("value")) is not None)


def parse_text(text):
    """解析旧版自然语言证伪条件。

    只认几种固定句式，不做自由语义解析。解析不出来的返回 None ——
    调用方据此把该假设标为 indeterminate，**不能当作「未被推翻」**。
    """
    import re

    if not text:
        return None
    s = str(text).replace("，", ",").replace("或", ",")
    atoms = []
    for frag in s.split(","):
        frag = frag.strip()
        if not frag:
            continue
        low = frag.lower()
        # lift < 1.2 / 倍数 < 1.5 / 差异 < 1.5 倍
        m = re.search(r"(lift|倍数|差异)\s*(<=|>=|<|>|==)\s*([0-9.]+)", low)
        if m:
            op = m.group(2)
            val = float(m.group(3))
            # 「差异 < 1.5 倍」语义上就是 lift 低于 1.5
            atoms.append({"metric": "lift", "op": op, "value": val})
            continue
        # 样本 < 30 / 样本数 < 30 / 命中组样本 < 30
        m = re.search(r"样本\s*(?:数)?\s*(<=|>=|<|>|==)\s*([0-9]+)", low)
        if m:
            atoms.append({"metric": "hit_n", "op": m.group(1), "value": int(m.group(2))})
            continue
        # p 值 > 0.05
        m = re.search(r"p\s*值?\s*(<=|>=|<|>|==)\s*([0-9.]+)", low)
        if m:
            atoms.append({"metric": "p_value", "op": m.group(1), "value": float(m.group(2))})
            continue
    return {"any": atoms} if atoms else None


def evaluate(cond, hit, nonhit):
    """对一条假设求值证伪条件，返回 (status, detail)。

    status:
      refuted        有任一条件成立 → 假设被推翻
      survived       全部条件都不成立 → 未被推翻（注意：不等于证明）
      indeterminate  数据不足或条件不可解析 → **不得视为未推翻**
      invalid        条件对象本身不合法
    """
    norm = normalize(cond)
    if not norm or not norm.get("any"):
        return STATUS_INDETERMINATE, {
            "reason": "证伪条件为空或无法解析为可判定条件，",
            "note": "不能据此认为假设成立"}

    m = metrics_from_comparison(hit, nonhit)
    fired, unknown = [], []
    for a in norm["any"]:
        v = m.get(a["metric"])
        if v is None:
            unknown.append(a)
            continue
        if OPS[a["op"]](v, a["value"]):
            fired.append({**a, "actual": round(v, 6)})

    if fired:
        return STATUS_REFUTED, {
            "fired": fired,
            "reason": "；".join(
                f"{f['metric']} 实际 {f['actual']} {f['op']} 阈值 {f['value']}"
                for f in fired)}

    if unknown:
        return STATUS_INDETERMINATE, {
            "unknown": unknown,
            "reason": ("部分证伪条件无法取到指标（"
                       + ", ".join(u["metric"] for u in unknown)
                       + "），无法判定"),
            "note": "缺数据不等于未被推翻"}

    return STATUS_SURVIVED, {
        "metrics": {k: (round(v, 6) if isinstance(v, float) else v)
                    for k, v in m.items() if v is not None},
        "reason": "全部证伪条件均未成立",
        "note": "未发现推翻证据，不等于已经证实"}


def apply_to_plan(plan, hit, nonhit):
    """把求值结果回写进 plan，返回 (plan, status)。

    回写字段：
      falsify_result.status    refuted / survived / indeterminate / invalid
      falsify_result.detail    判定依据（可直接进报告）
      falsify_result.metrics   实际算出的指标
      hypothesis_status        假设级状态，供下游闸门读取
    """
    status, detail = evaluate(plan.get("falsify_if"), hit, nonhit)
    plan = dict(plan)
    plan["falsify_result"] = {"status": status, **detail}
    plan["hypothesis_status"] = _hypothesis_status(status)
    return plan, status


def _hypothesis_status(falsify_status):
    """证伪状态 → 假设状态。只有 survived 才允许「待验证→未排除」。"""
    return {
        STATUS_REFUTED: "nullified",        # 已推翻，不得作为结论
        STATUS_SURVIVED: "not_excluded",    # 未被排除，仍需外部证据
        STATUS_INDETERMINATE: "undetermined",
        STATUS_INVALID: "undetermined",
    }.get(falsify_status, "undetermined")
