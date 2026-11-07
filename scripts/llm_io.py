#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""llm_io.py — LLM 提示词 / 结果的轻量读写与校验（纯标准库，不调 API）

用法:
    # 看提示词（system / user 分开展示）
    python3 scripts/llm_io.py --prompt-file drill_prompt.json --show user

    # 校验 LLM 返回是否符合 output_schema（drill_plan 或 narrative）
    python3 scripts/llm_io.py --schema drill --prompt-file drill_prompt.json --result-file llm.json
    python3 scripts/llm_io.py --schema narrative --prompt-file narrative_prompt.json --result-file llm.json

    # 填回：把合法结果写入 drill_plan.json / narrative.json；违规项写入 *_review.json
    python3 scripts/llm_io.py --schema narrative --prompt-file p.json --result-file llm.json \
        --fill narrative.json --review-note

    # 自测
    python3 scripts/llm_io.py --selftest

工作流中的位置
--------------
    S3 planner → drill_prompt.json ──(外部 Agent 调模型)──→ llm 返回 ──(llm_io 校验/落盘)──→ drill_plan.json → S4
    S5 narrative → narrative_prompt.json ──(外部 Agent 调模型)──→ llm 返回 ──(llm_io 校验/落盘)──→ narrative.json → S6
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import common  # noqa: E402

EMPTY_BOILERPLATE = ["深层结构性问题", "综合来看", "多维度叠加", "系统性特征", "并非单一孤立",
                     "同源共振", "具有系统性", "深层次问题"]
# 业务动作必须体现"经营代价/收益"的关键词
BUSINESS_TRADEOFF_KW = ["经营", "代价", "收益", "成本", "业务", "客户流失", "放款", "获客", "市场", "限额"]
DECISION_FIELDS = ["action", "owner", "deadline", "kpi", "baseline", "target"]


# ============================================================ 解析 LLM 原始返回


def parse_llm_result(text):
    """容忍 LLM 常见的包裹（```json ``` / 前后解释文字），抽出 JSON 对象。

    返回 (obj, warnings)
    """
    warnings = []
    if isinstance(text, (dict, list)):
        return text, warnings
    s = (text or "").strip()
    if not s:
        raise ValueError("LLM 返回为空")
    m = re.search(r"```(?:json)?\s*(.*?)```", s, re.S)
    if m:
        warnings.append("返回被 markdown 代码块包裹，已剥离")
        s = m.group(1).strip()
    if not s.startswith("{") and not s.startswith("["):
        i, j = s.find("{"), s.rfind("}")
        if i >= 0 and j > i:
            warnings.append("返回前后含解释文字，已截取最外层 JSON")
            s = s[i:j + 1]
    try:
        return json.loads(s), warnings
    except json.JSONDecodeError as e:
        raise ValueError(f"返回不是合法 JSON：{e}") from e


# ============================================================ 通用 schema 校验


def _check_required(obj, required, path, errs):
    for k in required:
        if k not in obj or obj[k] in (None, "", [], {}):
            errs.append(f"{path}.{k} 缺失或为空")


def _check_type(val, spec, path, errs):
    t = spec.get("type")
    if t == "string" and not isinstance(val, str):
        errs.append(f"{path} 应为字符串，实际 {type(val).__name__}")
    elif t == "array" and not isinstance(val, list):
        errs.append(f"{path} 应为数组，实际 {type(val).__name__}")
    elif t == "object" and not isinstance(val, dict):
        errs.append(f"{path} 应为对象，实际 {type(val).__name__}")
    elif t == "integer" and not isinstance(val, int):
        errs.append(f"{path} 应为整数，实际 {type(val).__name__}")
    if isinstance(val, str):
        if spec.get("maxLength") and len(val) > spec["maxLength"]:
            errs.append(f"{path} 超长（{len(val)} > {spec['maxLength']}）")
        if spec.get("minLength") and len(val) < spec["minLength"]:
            errs.append(f"{path} 过短（{len(val)} < {spec['minLength']}）")
        if spec.get("pattern") and not re.search(spec["pattern"], val):
            errs.append(f"{path} 不符合格式 {spec['pattern']}：{val}")
        if spec.get("enum") and val not in spec["enum"]:
            errs.append(f"{path} 取值不在枚举内：{val}")
    if isinstance(val, list):
        if spec.get("minItems") and len(val) < spec["minItems"]:
            errs.append(f"{path} 条数不足（{len(val)} < {spec['minItems']}）")
        if spec.get("maxItems") and len(val) > spec["maxItems"]:
            errs.append(f"{path} 条数超限（{len(val)} > {spec['maxItems']}）")
        item_spec = spec.get("items")
        if item_spec:
            for i, it in enumerate(val):
                _walk(it, item_spec, f"{path}[{i}]", errs)
    if isinstance(val, int) and spec.get("minimum") is not None and val < spec["minimum"]:
        errs.append(f"{path} 小于最小值 {spec['minimum']}")


def _walk(obj, spec, path, errs):
    if not isinstance(spec, dict):
        return
    _check_type(obj, spec, path, errs)
    if spec.get("type") == "object" and isinstance(obj, dict):
        _check_required(obj, spec.get("required") or [], path, errs)
        for k, subspec in (spec.get("properties") or {}).items():
            if k in obj:
                _walk(obj[k], subspec, f"{path}.{k}", errs)


def validate_schema(obj, schema):
    errs = []
    _walk(obj, schema, "$", errs)
    return errs


# ============================================================ drill_plan 专项校验


def validate_drill_output(obj, prompt, td=None):
    """drill_plan 校验：schema 齐全性 + 禁令违反（表名/字段名/写操作/SELECT *）"""
    if isinstance(obj, list):
        obj = {"plans": obj}
    violations = []
    schema = (prompt or {}).get("output_schema") or {
        "type": "object", "required": ["plans"],
        "properties": {"plans": {"type": "array", "items": {"type": "object",
                                                            "required": ["plan_id", "topic_hint", "linked_rule",
                                                                         "hypothesis", "falsify_if", "steps"]}}}}
    errs = validate_schema(obj, schema)

    plans = (obj or {}).get("plans") if isinstance(obj, dict) else None
    if not isinstance(plans, list):
        return {"ok": False, "errors": errs + ["顶层缺少 plans 数组"], "violations": []}

    if td is None:
        try:
            td = common.TableDict()
        except Exception:
            td = None

    import drill_executor as dex
    seen = set()
    for p in plans:
        pid = p.get("plan_id", "?")
        if pid in seen:
            violations.append({"plan_id": pid, "code": "duplicate_plan_id"})
        seen.add(pid)
        for st in p.get("steps") or []:
            sql = st.get("sql") or ""
            if td is not None:
                v = dex.validate_sql(sql, td)
                if not v.ok:
                    violations.append({"plan_id": pid, "step_id": st.get("step_id"),
                                       "code": v.reason, "detail": v.detail})
            else:
                if re.search(r"\b(DROP|DELETE|INSERT|UPDATE|CREATE|ALTER)\b", sql, re.I):
                    violations.append({"plan_id": pid, "step_id": st.get("step_id"),
                                       "code": "write_operation"})
    blocking = [v for v in violations if v.get("code") in (
        "table_not_allowed", "select_star", "write_operation", "unparseable_sql", "missing_slice_filter",
        "hardcoded_id") or str(v.get("code", "")).startswith(("write_operation:", "column_not_allowed"))]
    return {"ok": not errs and not blocking, "errors": errs, "violations": violations,
            "blocking_count": len(blocking)}


# ============================================================ narrative 专项校验


def _narrative_texts(nar):
    """遍历叙述里所有面向读者的文本字段"""
    out = []

    def add(path, s):
        if isinstance(s, str):
            out.append((path, s))

    add("executive_summary", nar.get("executive_summary"))
    for i, t in enumerate(nar.get("topics") or []):
        for k in ("title", "phenomenon", "mechanism", "evidence", "impact"):
            add(f"topics[{i}].{k}", t.get(k))
        for k, val in (t.get("management_decision") or {}).items():
            add(f"topics[{i}].management_decision.{k}", val)
        for j, c in enumerate(t.get("caveats") or []):
            add(f"topics[{i}].caveats[{j}]", c)
    for i, o in enumerate(nar.get("observation_only") or []):
        add(f"observation_only[{i}].title", o.get("title"))
        add(f"observation_only[{i}].why_not_conclusion", o.get("why_not_conclusion"))
    for i, s in enumerate(nar.get("data_blind_spots") or []):
        add(f"data_blind_spots[{i}]", s)
    return out


def validate_narrative(nar, td=None, prompt=None):
    """narrative 校验：字段齐全 + 去技术化 + 禁规则名标题 + 经营代价 + caveats + 空话"""
    if td is None:
        try:
            td = common.TableDict()
        except Exception:
            td = None
    violations = []
    errors = []

    for k in ("topics", "observation_only", "executive_summary", "data_blind_spots"):
        if k not in nar:
            errors.append(f"顶层缺 {k}")
    if isinstance(nar.get("topics"), list) and not nar["topics"] and not nar.get("observation_only"):
        errors.append("topics 与 observation_only 同时为空，报告将无内容")

    rn_raw = ((prompt or {}).get("forbidden_patterns") or {}).get("rule_names", [])
    rule_names = {(i.get("name") if isinstance(i, dict) else str(i)).strip() for i in rn_raw if i}
    rule_names |= set(RULE_NAMES_DEFAULT)
    rule_names.discard("")

    for t in nar.get("topics") or []:
        tid = t.get("topic_id", "?")
        for k in ("topic_id", "title", "phenomenon", "mechanism", "evidence", "impact",
                  "management_decision", "caveats"):
            if k not in t or t.get(k) in (None, "", []):
                errors.append(f"{tid}.{k} 缺失")
        md = t.get("management_decision") or {}
        missing = [f for f in DECISION_FIELDS if not md.get(f)]
        if missing:
            violations.append({"topic_id": tid, "code": "incomplete_decision",
                               "detail": "缺 " + ",".join(missing)})
        if md.get("action") and not any(kw in md["action"] for kw in BUSINESS_TRADEOFF_KW):
            violations.append({"topic_id": tid, "code": "no_business_tradeoff",
                               "detail": "action 未提及经营代价/收益，只讲压降风险"})
        cav = t.get("caveats") or []
        if not cav:
            violations.append({"topic_id": tid, "code": "missing_caveats", "detail": "反证/盲区为空"})
        title = (t.get("title") or "").strip()
        if title and title in rule_names:
            violations.append({"topic_id": tid, "code": "rule_name_as_title", "detail": title})
        elif title and any(title.startswith(rn) and len(title) - len(rn) < 4 for rn in rule_names if rn):
            violations.append({"topic_id": tid, "code": "rule_name_as_title",
                               "detail": f"标题近似规则名：{title}"})

    # 全文扫描：技术标识 / 空话
    for path, s in _narrative_texts(nar):
        clean, hits = common.sanitize_text(s, td)
        techn = [h for h in hits if h["type"] in ("table_name", "field_name") or
                 (h["type"] == "id_like" and len(str(h.get("value", ""))) >= 6)]
        if techn:
            violations.append({"path": path, "code": "technical_identifier",
                               "detail": ",".join(f"{h['type']}:{h['value']}" for h in techn[:4])})
        for b in EMPTY_BOILERPLATE:
            if b in s:
                violations.append({"path": path, "code": "empty_boilerplate", "detail": b})

    incomplete = bool(errors or any(v["code"] in ("incomplete_decision", "missing_caveats", "technical_identifier")
                                    for v in violations))
    return {
        "ok": not errors and not violations,
        "incomplete": incomplete,
        "errors": errors,
        "violations": violations,
        "violation_codes": sorted({v["code"] for v in violations}),
    }


RULE_NAMES_DEFAULT = ["人员道德风险", "获客激进扩张", "准入风控失守", "建档造假链条", "超额授信杠杆",
                      "贷后管理空转", "续贷接续断裂", "产品行业集中", "客户欺诈包装", "客户经营恶化",
                      "客户高杠杆", "客户异常行为", "第一还款来源失效"]


# ============================================================ 落盘


def fill_result(schema_kind, result, out_path, prompt=None, td=None):
    """把校验通过的（或带审查标记的）结果落成下游可读文件。

    - drill：包成 drill_plan.json（契约第 4 节）
    - narrative：若 prompt 里有 evidence_pack 则透传，否则直接写
    违规项不丢弃，写入 <out>.review.json 供人工复核。
    """
    if schema_kind == "drill":
        doc = {"schema_version": "3.0", "kind": "drill_plan", "origin": "llm",
               "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
               "plans": result.get("plans", []) if isinstance(result, dict) else result}
        rep = validate_drill_output(doc, prompt, td)
        body = {"report": rep}
    else:
        doc = dict(result)
        doc.setdefault("schema_version", "3.0")
        doc["kind"] = "narrative"
        doc["origin"] = "llm"
        rep = validate_narrative(doc, td, prompt)
        body = {"report": rep}

    review_path = str(out_path) + ".review.json"
    if body["report"].get("ok"):
        common.write_json(out_path, doc)
        return {"written": str(out_path), "review": None, "report": body["report"]}
    common.write_json(out_path, doc)   # 仍然落盘（不静默丢弃），但附审查文件
    common.write_json(review_path, {"source": str(out_path), **body["report"],
                                    "note": "该文件记录 LLM 返回中的违规项，需人工复核后才可进入渲染"})
    return {"written": str(out_path), "review": review_path, "report": body["report"]}


# ============================================================ selftest


def selftest():
    ck = common.Checker("llm_io selftest")
    td = common.TableDict()

    print("── 原始返回解析 ──")
    wrapped = '好的，以下是结果：\n```json\n{"plans": [{"plan_id": "P001"}]}\n```\n以上。'
    obj, w = parse_llm_result(wrapped)
    ck.check(obj["plans"][0]["plan_id"] == "P001", "能剥离 markdown 代码块与前后解释", ";".join(w))
    obj2, _ = parse_llm_result('{"a": 1}')
    ck.check(obj2 == {"a": 1}, "纯 JSON 直通")
    try:
        parse_llm_result("not json at all")
        ck.check(False, "非法返回应报错")
    except ValueError as e:
        ck.check(True, "非法返回报错", str(e)[:40])

    print("\n── drill_plan 校验 ──")
    good = {"plans": [{"plan_id": "P001", "topic_hint": "资金往来", "linked_rule": "C07",
                       "hypothesis": "资金往来客群不良率应高于对照组 2 倍以上", "falsify_if": "lift<1.2",
                       "steps": [{"step_id": "P001-S1", "intent": "取数", "group": "hit",
                                  "tables": ["G_00PF_PEAS_LN_VCH_DV"],
                                  "sql": "SELECT 'hit' AS grp, COUNT(DISTINCT CUST_NO) AS n, 0.1 AS npl_rate "
                                         "FROM G_00PF_PEAS_LN_VCH_DV WHERE DATA_DAT='20260831'",
                                  "expect": "lift>=2"}]}]}
    r = validate_drill_output(good, None, td)
    ck.check(r["ok"], "合法 drill 返回 → ok")
    bad = json.loads(json.dumps(good))
    bad["plans"][0]["steps"][0]["sql"] = "SELECT * FROM NOT_A_TABLE WHERE DATA_DAT='1'"
    r2 = validate_drill_output(bad, None, td)
    ck.check(not r2["ok"], f"越界返回 → 拒（{r2['violations'][0]['code']}）")
    missing = {"plans": [{"plan_id": "P001"}]}
    r3 = validate_drill_output(missing, None, td)
    ck.check(not r3["ok"] and any("hypothesis" in e for e in r3["errors"]), "缺 hypothesis → 字段错误")

    print("\n── narrative 校验 ──")
    import narrative as nv
    signals, attribution = common.synth_signals(), common.synth_attribution()
    import drill_planner as dpl
    import drill_executor as dex
    ev = dex.build_evidence(dpl.build_degrade_plan(signals, attribution), td, mode="mock")
    nar = nv.build_degrade_narrative(ev, signals, attribution, td)
    r4 = validate_narrative(nar, td)
    ck.check(r4["ok"], f"降级生成的 narrative 通过校验 {r4['violation_codes']}")

    broken = json.loads(json.dumps(nar))
    broken["topics"][0]["title"] = "人员道德风险"
    broken["topics"][0]["management_decision"]["action"] = "压降不良"
    broken["topics"][0]["caveats"] = []
    broken["topics"][0]["phenomenon"] = "FORM_BAL_RMB 字段异常，机构 01030408 不良率偏高"
    broken["executive_summary"] = "综合来看，存在深层结构性问题。"
    r5 = validate_narrative(broken, td)
    codes = r5["violation_codes"]
    for c in ("rule_name_as_title", "no_business_tradeoff", "missing_caveats",
              "technical_identifier", "empty_boilerplate"):
        ck.check(c in codes, f"抓出 {c}")
    ck.check(r5["incomplete"], "违规 → incomplete=true")

    print("\n── 填回（不丢弃违规结果）──")
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        p1 = Path(tmp) / "narrative.json"
        out = fill_result("narrative", nar, p1, None, td)
        ck.check(Path(out["written"]).exists() and out["review"] is None, "合法结果直接落盘，无 review 文件")
        p2 = Path(tmp) / "narrative_bad.json"
        out2 = fill_result("narrative", broken, p2, None, td)
        ck.check(Path(out2["written"]).exists() and out2["review"] and Path(out2["review"]).exists(),
                 "违规结果仍落盘 + 生成 .review.json")
    return ck.summary()


def main():
    ap = argparse.ArgumentParser(description="LLM 提示词/结果读写与校验（不调 API）")
    ap.add_argument("--prompt-file", help="*_prompt.json")
    ap.add_argument("--result-file", help="LLM 返回的 json/txt")
    ap.add_argument("--schema", choices=["drill", "narrative", "raw"], help="校验器")
    ap.add_argument("--show", choices=["system", "user", "schema", "all"], help="打印提示词")
    ap.add_argument("--fill", help="把结果填回到该路径")
    ap.add_argument("--print-result", action="store_true", help="打印 LLM 返回")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    prompt = common.read_json(args.prompt_file) if args.prompt_file else None
    if args.show:
        if not prompt:
            print("错误：--show 需要 --prompt-file", file=sys.stderr)
            return 2
        if args.show in ("system", "all"):
            print("=" * 30, "SYSTEM", "=" * 30)
            print(prompt.get("system", ""))
        if args.show in ("user", "all"):
            print("=" * 30, "USER", "=" * 30)
            print(prompt.get("user", ""))
        if args.show in ("schema", "all"):
            print("=" * 30, "SCHEMA", "=" * 30)
            print(json.dumps(prompt.get("output_schema", {}), ensure_ascii=False, indent=2))
        return 0

    if not args.result_file:
        print("错误：需要 --result-file（或 --show / --selftest）", file=sys.stderr)
        return 2
    try:
        text = Path(args.result_file).read_text(encoding="utf-8")
    except FileNotFoundError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
    try:
        obj, warns = parse_llm_result(text)
    except ValueError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1
    for w in warns:
        print(f"⚠️  {w}")
    if args.print_result:
        print(json.dumps(obj, ensure_ascii=False, indent=2)[:3000])

    kind = args.schema or ("drill" if prompt and prompt.get("kind") == "drill_prompt" else "narrative")
    td = None
    try:
        td = common.TableDict()
    except Exception:
        pass
    if kind == "drill":
        rep = validate_drill_output(obj, prompt, td)
    elif kind == "narrative":
        rep = validate_narrative(obj if isinstance(obj, dict) else {}, td, prompt)
    else:
        errs = validate_schema(obj, (prompt or {}).get("output_schema") or {})
        rep = {"ok": not errs, "errors": errs, "violations": []}

    print(("✅ 校验通过" if rep.get("ok") else "❌ 校验未通过") + f"（{kind}）")
    for e in rep.get("errors") or []:
        print(f"   ✗ 字段：{e}")
    seen = set()
    for v in rep.get("violations") or []:
        key = (v.get("code"), v.get("plan_id") or v.get("topic_id") or v.get("path"))
        if key in seen:
            continue
        seen.add(key)
        print(f"   ✗ 违规：{v.get('code')} — {v.get('plan_id') or v.get('topic_id') or v.get('path')} {v.get('detail', '')}")

    if args.fill:
        out = fill_result(kind, obj, args.fill, prompt, td)
        print(f"📝 已写入 {out['written']}" + (f"；违规项见 {out['review']}" if out["review"] else ""))
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
