#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S4b2 apply_gate —— 把 topic_gate 的闸门结果写回 attribution.topic_selection

为什么需要这一步
----------------
narrative 的主题源是 `attribution.topic_selection`，而该字段在 S3 attribution
阶段就已定好（按规则强度排序），**完全不经过 S4b 的 topic_gate**。

结果是：topic_gate 认真做了两道校验、把不合格的主题全拦下，报告却照样把
它们写出来 —— 实测出现过「闸门 0 条 / 报告 5 条成因，且声称经数据验证成立」
的矛盾。闸门形同虚设，执行失败被包装成业务结论。

这一步把闸门结果写回主题源：
  · 只有 topic_gate.selection.topics 里的规则保留 decision='selected'
  · 其余降为 'rejected' 并写明闸门给出的理由
  · 证据链不健康（empty/failed）时，一律清空，不许任何主题进报告

用法
----
  python scripts/apply_gate.py --topic-gate topic_gate.json \
      --attribution attribution.json --evidence evidence.json \
      --out attribution.json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import common  # noqa: E402


def _gate_reason(g):
    """从闸门条目里摘出最该给业务看的一条拒绝理由。"""
    ph = g.get("phenomenon") or {}
    at = g.get("attribution") or {}
    if ph.get("passed") and not at.get("passed"):
        return at.get("status") or "attribution_rejected", at.get("reason") or ""
    if not ph.get("passed"):
        return ph.get("status") or "phenomenon_rejected", ph.get("reason") or ""
    return "rejected", ""


def apply_gate(topic_gate, attribution, evidence=None):
    """用闸门结果覆写 topic_selection。返回 (新 attribution, 统计)"""
    health = topic_gate.get("evidence_health") or {}
    status = (health.get("status") or "").lower()
    blocked = status in ("empty", "failed")

    sel = topic_gate.get("selection") or {}
    passed_ids = {t.get("rule_id") for t in (sel.get("topics") or []) if t.get("rule_id")}
    gated = {g.get("rule_id"): g for g in (topic_gate.get("gated") or [])}

    out_sel = []
    kept = dropped = 0
    for t in (attribution.get("topic_selection") or []):
        rid = t.get("rule_id")
        item = dict(t)
        if blocked:
            # 证据链不健康：任何主题都不许留下
            item["decision"] = "rejected"
            item["reason"] = "evidence_unavailable"
            item["gate_reason"] = health.get("note") or "证据链不可用"
            dropped += 1
            out_sel.append(item)
            continue
        if rid in passed_ids:
            item["decision"] = "selected"
            item["reason"] = "passed_topic_gate"
            kept += 1
        else:
            code, why = _gate_reason(gated.get(rid) or {})
            item["decision"] = "rejected"
            item["reason"] = code
            item["gate_reason"] = why or "未通过 topic_gate 两道校验"
            dropped += 1
        out_sel.append(item)

    # 按（是否入选, 强度）重排，让下游按优先级取
    out_sel.sort(key=lambda x: (x.get("decision") != "selected",
                                -(x.get("strength") or 0)))

    new_attr = dict(attribution)
    new_attr["topic_selection"] = out_sel
    new_attr["topic_gate_applied"] = {
        "evidence_health": health,
        "blocked": blocked,
        # gated_total = 真正进入证据闸门的条数（现象层通过、可做实测校验的那几条）
        # 与 rejected 区分开：rejected 是对全部 topic_selection 写回后判为拒绝的条数。
        "gated_total": len(gated),
        "selected": kept,
        "rejected": dropped,
    }
    return new_attr, {"selected": kept, "rejected": dropped, "blocked": blocked,
                      "evidence_status": status}


def main(argv=None):
    ap = argparse.ArgumentParser(description="把 topic_gate 结果写回 attribution.topic_selection")
    ap.add_argument("--topic-gate", required=True)
    ap.add_argument("--attribution", required=True)
    ap.add_argument("--evidence", help="仅用于日志，不参与判定")
    ap.add_argument("--out", default="attribution.json")
    args = ap.parse_args(argv)

    tg = common.read_json(args.topic_gate)
    attr = common.read_json(args.attribution)
    new_attr, st = apply_gate(tg, attr)
    common.write_json(args.out, new_attr)

    if st["blocked"]:
        print(f"⛔ 证据链 {st['evidence_status']}：全部 {st['rejected']} 条主题已清空，"
              f"报告将不输出管理结论")
    else:
        print(f"✅ 闸门写回：入选 {st['selected']} 条 / 排除 {st['rejected']} 条"
              f"（证据 {st['evidence_status']}） → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
