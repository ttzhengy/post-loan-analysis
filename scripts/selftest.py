#!/usr/bin/env python3
"""selftest.py — attribution/signals 引擎自测（纯标准库，不依赖任何真实数据）

    python3 scripts/selftest.py           # 跑 T1-T6
    python3 scripts/selftest.py -v        # 打印每一步明细

覆盖：
  T1 强度区分度：5 特征命中 2 个但偏离极大  vs  3 特征全命中但偏离极小
                 → 前者 strength 必须超过后者（证明 0.4 强度分量真的生效）
  T2 排序稳定性：同一份数据连跑 3 次，主题顺序必须完全一致
  T3 规则双源加载：manual + mined + derived 全部正确加载，总数与 rules.json 一致
  T4 降级：无 cohort 数据的规则不得出现在「显著」级
  T5 兼容：只有旧格式 features.json（无 baseline）时不崩，强度分量仍计算但写 warning
  T6 规则库字段自检：derived 规则引用的表/字段必须在 shared/table-dict.json 中真实存在
"""
import argparse
import copy
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import attribution as AT           # noqa: E402
import signals as SIG              # noqa: E402

RULES_PATH = os.path.join(ROOT, "references", "rules.json")
DICT_PATH = os.path.join(ROOT, "shared", "table-dict.json")

FAILED = []
PASSED = []


def check(name, cond, detail=""):
    if cond:
        PASSED.append(name)
        print(f"  ✅ {name}" + (f" — {detail}" if detail else ""))
    else:
        FAILED.append(name)
        print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))
    return cond


def load_rules_doc():
    with open(RULES_PATH, encoding="utf-8") as f:
        return json.load(f)


def feat(fid, name, metric, baseline, stage="贷前准入", status="ok"):
    return {"feature_id": fid, "name": name, "dimension": "客户", "stage": stage,
            "status": status, "metric": metric, "baseline": baseline}


def make_signals(features, npl_rate=0.05, clue=None, cont=None, dims=None):
    sig = {
        "schema_version": "3.0", "slice": "20260831",
        "overall": {"bal": 1_000_000_000, "npl_bal": 1_000_000_000 * npl_rate,
                    "npl_rate": npl_rate, "cnt": 1000, "cust_cnt": 900, "person_cnt": 890},
        "dimensions": dims or {},
        "clue_matrix": clue or {},
        "features": features,
        "continuation": cont or {"tools": {}, "chain": {
            "rolling": {"cnt": 0, "npl_rate": None}, "resolving": {"cnt": 0, "npl_rate": None}}},
        "warnings": [],
    }
    sig["baseline"] = {str(f["feature_id"]): f["baseline"] for f in features if f.get("baseline")}
    return sig


# =========================================================================
# T1 强度区分度
# =========================================================================
def test_t1(verbose):
    print("\nT1 强度区分度：宽广度弱信号 vs 窄广度高强度")
    # 规则 A：5 个成员，min_hits=2 —— 只命中 2 个（广度 0.4），但偏离 10 倍基线（norm 打满 1.0）
    # 注意：命中阈值 hit_min_dev=0.20 是相对倍数，偏离 25% 刚算命中、10 倍则打满
    # 规则 B：3 个成员全命中（广度 1.0），但每个只偏离 1%（norm ≈ 0）
    # 两者的广度差正好是 0.6*(1.0-0.4)=0.36，而强度差最多 0.4 → 光靠广度 B 赢，
    # 只有强度分量真正生效时 A 才能反超（A=0.64  vs  B=0.60）。
    rule_wide = {
        "rule_id": "T1A", "name": "窄广度高强度", "essence": "", "source": "manual",
        "version": 1, "expr": {"all_of": [901, 902, 903, 904, 905], "min_hits": 2,
                               "any_of": [], "scale_max": 5},
        "stages": ["贷前准入"], "cross_stage": False,
    }
    # 规则 B：3 个成员，min_hits=2 —— 3 个全命中但每个只偏离 25%（刚过命中阈值，norm 极小）
    rule_narrow = {
        "rule_id": "T1B", "name": "宽广度弱信号", "essence": "", "source": "manual",
        "version": 1, "expr": {"all_of": [911, 912, 913], "min_hits": 2,
                               "any_of": [], "scale_max": 5},
        "stages": ["贷前准入"], "cross_stage": False,
    }
    features = [
        # A：偏离 10 倍（0.05 基线 → 0.55）
        feat(901, "A1", {"x": 0.55}, {"x": 0.05}),
        feat(902, "A2", {"x": 0.60}, {"x": 0.05}),
        # A 的其余 3 个成员无数据
        {"feature_id": 903, "name": "A3", "status": "data_missing", "stage": "贷前准入"},
        {"feature_id": 904, "name": "A4", "status": "data_missing", "stage": "贷前准入"},
        {"feature_id": 905, "name": "A5", "status": "data_missing", "stage": "贷前准入"},
        # B：3 个全命中但强度弱 —— 偏离 25%（0.05 → 0.0625），刚过 hit_min_dev=0.20
        feat(911, "B1", {"x": 0.0625}, {"x": 0.05}),
        feat(912, "B2", {"x": 0.0625}, {"x": 0.05}),
        feat(913, "B3", {"x": 0.0625}, {"x": 0.05}),
    ]
    sig = make_signals(features)
    doc = {"manual": [rule_wide, rule_narrow]}
    res = AT.run(sig, doc)
    by = {e["rule_id"]: e for e in res["insights"]}
    a, b = by["T1A"], by["T1B"]
    if verbose:
        for r in (a, b):
            print(f"     {r['rule_id']}: 广度={r['breadth']:.3f} 强度={r['signal']:.3f} "
                  f"strength={r['strength_raw']:.3f} 命中={r['hit_count']}/{r['member_total']}")
    check("T1-a 广度占优：B(全命中 3/3) 的广度 > A(仅命中 2/5)",
          b["breadth"] > a["breadth"], f"{b['breadth']:.3f} > {a['breadth']:.3f}")
    check("T1-b 强度占优：A 的 signal > B 的 signal",
          a["signal"] > b["signal"], f"{a['signal']:.3f} > {b['signal']:.3f}")
    check("T1-c A 的最终 strength 超过 B（0.4 强度分量生效）",
          a["strength_raw"] > b["strength_raw"],
          f"{a['strength_raw']:.3f} > {b['strength_raw']:.3f}；"
          f"广度差值仅 {0.6*(b['breadth']-a['breadth']):.3f} < 强度可带来的 0.4")
    check("T1-d 反证：若只算广度（0.6*广度，旧 hit_ratio 口径），A 会输给 B",
          0.6 * a["breadth"] < 0.6 * b["breadth"],
          f"旧口径 A={0.6*a['breadth']:.3f} < B={0.6*b['breadth']:.3f}，说明是强度分量反转了排序")

    # 边界：SATURATION 可配置 —— 饱和点越小，强度越早打满
    res_sat = AT.run(sig, doc, saturation=0.5)
    a2 = {e["rule_id"]: e for e in res_sat["insights"]}["T1A"]
    check("T1-e SATURATION 可配置（0.5 时 A 的 signal 打满 = 1.0）",
          abs(a2["signal"] - 1.0) < 1e-9, f"signal={a2['signal']}")


# =========================================================================
# T2 排序稳定性
# =========================================================================
def test_t2(verbose):
    print("\nT2 排序稳定性：同一份数据连跑 3 次")
    metrics, org_risk, overview, features = SIG.mock_inputs()
    sig = SIG.build_signals(metrics, org_risk, overview, features, slice_dt="20260831")
    doc = load_rules_doc()
    orders = []
    for i in range(3):
        res = AT.run(copy.deepcopy(sig), copy.deepcopy(doc))
        orders.append([t["rule_id"] for t in res["topic_selection"]])
        ins = [e["rule_id"] for e in res["insights"]]
        if i == 0:
            first_ins = ins
        else:
            check(f"T2-{i+1} insights 顺序与第 1 次一致", ins == first_ins)
    check("T2-1 三次 topic_selection 顺序完全一致",
          orders[0] == orders[1] == orders[2], f"{len(orders[0])} 条规则")
    check("T2-2 topic_selection 与 insights 的排序一致", orders[0] == first_ins)
    # tie-break 必须可复现：把输入顺序打乱，结果不许变
    shuffled = copy.deepcopy(doc)
    for k in ("manual", "mined", "derived"):
        shuffled[k] = list(reversed(shuffled[k]))
    res_shuf = AT.run(copy.deepcopy(sig), shuffled)
    shuf_order = [t["rule_id"] for t in res_shuf["topic_selection"]]
    check("T2-3 打乱 rules.json 段内顺序后结果不变（tie-break 显式生效）",
          shuf_order == orders[0])
    # 显式验证 tie-break 元组
    a = {"strength": 0.5, "incremental_lift": 1.2, "cohort_size": 100,
         "cross_stage": False, "rule_id": "C01"}
    b = {"strength": 0.5, "incremental_lift": 1.2, "cohort_size": 100,
         "cross_stage": True, "rule_id": "C02"}
    c = {"strength": 0.5, "incremental_lift": 1.2, "cohort_size": 100,
         "cross_stage": True, "rule_id": "C01"}
    check("T2-4 tie-break: 同分时 cross_stage=True 排前、再按 rule_id 升序",
          AT.rank_key(b) < AT.rank_key(a) and AT.rank_key(c) < AT.rank_key(b),
          f"{AT.rank_key(c)} < {AT.rank_key(b)} < {AT.rank_key(a)}")


# =========================================================================
# T3 规则双源加载
# =========================================================================
def test_t3(verbose):
    print("\nT3 规则双源/三源加载：manual + mined + derived")
    doc = load_rules_doc()
    rules, stats = AT.load_rules(doc)
    expect = {k: len(doc.get(k) or []) for k in ("manual", "mined", "derived")}
    check("T3-1 manual 全部加载", stats["manual"] == expect["manual"] and expect["manual"] > 0,
          f"{stats['manual']}/{expect['manual']}")
    check("T3-2 mined 全部加载", stats["mined"] == expect["mined"] and expect["mined"] > 0,
          f"{stats['mined']}/{expect['mined']}")
    check("T3-3 derived 全部加载", stats["derived"] == expect["derived"],
          f"{stats['derived']}/{expect['derived']}")
    check("T3-4 总数与 rules.json 一致", stats["total"] == sum(expect.values()),
          f"{stats['total']} == {sum(expect.values())}")
    check("T3-5 derived ≥ 8 条", expect["derived"] >= 8, f"{expect['derived']} 条")
    ids = [r["rule_id"] for r in rules]
    check("T3-6 rule_id 无重复", len(ids) == len(set(ids)), f"{len(ids)} 个 id")
    check("T3-7 C01-C13 全部在 manual 段",
          all(f"C{i:02d}" in ids for i in range(1, 14)))
    check("T3-8 source 字段与段名一致",
          all(r["source"] == r["section"] for r in rules))
    # 旧扁平 members 兼容（CONTRACT 第 3 节末段）
    legacy = {"manual": [{"rule_id": "L01", "name": "旧格式", "members": [1, 2, 3],
                          "min_hits": 2, "evidence_fields": ["x"]}]}
    lr, _ = AT.load_rules(legacy)
    check("T3-9 旧扁平 members 自动转成 all_of + min_hits",
          lr[0]["expr"]["all_of"] == [1, 2, 3] and lr[0]["expr"]["min_hits"] == 2)
    if verbose:
        for r in rules:
            print(f"     {r['rule_id']:<4} [{r['source']:<7}] all_of={len(r['expr']['all_of'])} "
                  f"any_of={len(r['expr']['any_of'])} min_hits={r['expr']['min_hits']} "
                  f"scale_max={r['expr']['scale_max']}")
    return doc


# =========================================================================
# T4 降级：无 cohort 不得显著
# =========================================================================
def test_t4(verbose):
    print("\nT4 降级：无 cohort 校验的规则不得进「显著」")
    # 规则 R_A：成员 2 个全命中、偏离极大 → strength 很高，但无 cohort
    # 规则 R_B：成员全命中 + 偏离极大 + 带 cohort_lift → 可以进显著
    feat_hi = [feat(921, "H1", {"x": 0.95}, {"x": 0.05}),
               feat(922, "H2", {"x": 0.95}, {"x": 0.05})]
    rules = [
        {"rule_id": "R_A", "name": "无cohort高强", "essence": "", "source": "manual",
         "expr": {"all_of": [921, 922], "min_hits": 2, "any_of": [], "scale_max": 5},
         "stages": ["贷前准入"], "cross_stage": False},
        {"rule_id": "R_B", "name": "有cohort高强", "essence": "", "source": "mined",
         "expr": {"all_of": [921, 922], "min_hits": 2, "any_of": [], "scale_max": 5},
         "stages": ["贷前准入"], "cross_stage": False},
         # R_B/C/D 的当期证据走 signals.cohort_validation，而 rules.json 里的
         # cohort_lift 只是历史先验，不再参与校验（见 cohort_of 的文档）
        {"rule_id": "R_C", "name": "cohort lift 不足", "essence": "", "source": "mined",
         "expr": {"all_of": [921, 922], "min_hits": 2, "any_of": [], "scale_max": 5},
         "stages": ["贷前准入"], "cross_stage": False},
        {"rule_id": "R_D", "name": "cohort 样本不足", "essence": "", "source": "mined",
         "expr": {"all_of": [921, 922], "min_hits": 2, "any_of": [], "scale_max": 5},
         "stages": ["贷前准入"], "cross_stage": False},
    ]
    sig_t4 = make_signals(feat_hi)
    sig_t4["cohort_validation"] = {
        "R_B": {"lift": 13.7, "size": 65, "npl_rate": 0.57},
        "R_C": {"lift": 1.1, "size": 500, "npl_rate": 0.055},
        "R_D": {"lift": 5.0, "size": 7, "npl_rate": 0.25},
    }
    res = AT.run(sig_t4, {"manual": rules})
    by = {e["rule_id"]: e for e in res["insights"]}
    if verbose:
        for k, e in by.items():
            print(f"     {k}: strength={e['strength']:.3f} level={e['level']} reason={e['reason']}")
    check("T4-0 R_A 原始 strength 已达显著线（>=0.5）",
          by["R_A"]["strength_raw"] >= 0.5, f"{by['R_A']['strength_raw']:.3f}")
    check("T4-1 无 cohort 的高分规则被压到「一般」", by["R_A"]["level"] == "一般",
          f"level={by['R_A']['level']} reason={by['R_A']['reason']}")
    check("T4-2 无 cohort 的拒绝理由标记 no_cohort_validation",
          by["R_A"]["reason"] == "no_cohort_validation")
    check("T4-3 有达标 cohort 的规则可以进「显著」", by["R_B"]["level"] == "显著",
          f"strength={by['R_B']['strength']:.3f}")
    check("T4-4 cohort lift 不足 → 一般 + lift_insufficient",
          by["R_C"]["level"] == "一般" and by["R_C"]["reason"] == "lift_insufficient")
    check("T4-5 cohort 样本不足 → 一般 + sample_too_small",
          by["R_D"]["level"] == "一般" and by["R_D"]["reason"] == "sample_too_small")
    check("T4-6 「显著」集合里没有任何无 cohort 的规则",
          all(e["cohort"].get("source") for e in res["strong_insights"]),
          f"显著 {len(res['strong_insights'])} 条")
    check("T4-7 topic_selection 里 R_A 不是 selected",
          next(t for t in res["topic_selection"] if t["rule_id"] == "R_A")["decision"] != "selected")
    # 全量 mock 数据也要满足这条
    metrics, org_risk, overview, features = SIG.mock_inputs()
    sig = SIG.build_signals(metrics, org_risk, overview, features, slice_dt="20260831")
    res2 = AT.run(sig, load_rules_doc())
    bad = [e["rule_id"] for e in res2["strong_insights"] if not e["cohort"].get("lift")]
    check("T4-8 mock 全量数据下，显著级里无 cohort 的规则数为 0", not bad,
          f"违规规则: {bad}" if bad else "—")


# =========================================================================
# T5 兼容：旧格式 features.json（无 baseline）
# =========================================================================
def test_t5(verbose):
    print("\nT5 兼容：旧格式 features.json（无 baseline、只有 metric）")
    # 模拟 risk_features.py v2.0 的原始输出：只有 feature_id/name/status/metric，无 baseline
    old_features = {
        "schema_version": "2.0", "slice": "20260831", "warnings": [],
        "features": [
            {"feature_id": 1, "name": "零散获客风险", "dimension": "机构", "stage": "营销获客",
             "status": "ok", "table": "S_00PF_PEAS_DIVR_RSK_C4",
             "metric": {"零散客户占比均值": 0.51, "零散不良率均值": 0.062}},
            {"feature_id": 2, "name": "无抵押缓释风险", "dimension": "机构", "stage": "营销获客",
             "status": "ok", "metric": {"信用类余额占比均值": 0.45}},
            {"feature_id": 3, "name": "低评分准入风险", "dimension": "机构", "stage": "贷前准入",
             "status": "ok", "metric": {"低分段(<600)占比": 0.18}},
        ],
    }
    old_metrics = {"schema_version": "2.0", "slice": "20260831",
                   "overall": {"bal": 1_000_000_000, "npl_bal": 62_000_000, "npl_rate": 0.062},
                   "warnings": []}
    sig = SIG.build_signals(old_metrics, None, None, old_features, slice_dt="20260831")
    check("T5-1 无 baseline 的旧 features 不崩溃", isinstance(sig, dict) and sig.get("slice"))
    bsrc = {f["feature_id"]: f.get("baseline_src") for f in sig["features"]}
    check("T5-2 无全辖基线的特征被标记 baseline_src=missing",
          bsrc.get(2) == "missing", f"feature 2 → {bsrc.get(2)}")
    check("T5-3 率类特征按全辖不良率回填基线（不编造，取同口径）",
          sig["features"][0].get("baseline", {}).get("零散不良率均值") == 0.062,
          f"baseline={sig['features'][0].get('baseline')}")
    check("T5-4 signals.warnings 里写明缺基线的原因",
          any("基线" in w or "baseline" in w for w in sig["warnings"]),
          next((w for w in sig["warnings"] if "基线" in w), ""))

    doc = {"manual": [{"rule_id": "C01", "name": "获客激进扩张", "essence": "",
                       "expr": {"all_of": [1, 2, 3], "min_hits": 2, "any_of": [],
                                "scale_max": 5},
                       "stages": ["营销获客"], "cross_stage": False}]}
    res = AT.run(sig, doc)
    e = res["insights"][0]
    if verbose:
        print(f"     C01: 广度={e['breadth']:.3f} 强度={e['signal']:.3f} "
              f"strength={e['strength_raw']:.3f} 命中={e['hit_count']}/{e['member_total']}")
    check("T5-5 旧格式下规则仍能出分（不抛异常）", e["hit_count"] >= 2)
    check("T5-6 强度分量照算（无 baseline 的成员不参与 signal 均值）",
          e["signal"] >= 0 and e["breadth"] > 0, f"signal={e['signal']:.3f}")
    check("T5-7 attribution.warnings 记录了缺基线",
          any("基线" in w for w in res["warnings"]),
          next((w for w in res["warnings"] if "基线" in w), ""))
    # 完全没有任何 baseline 的场景：signal 必须记 0 且写 warning
    bare = copy.deepcopy(old_features)
    for f in bare["features"]:
        f["metric"] = {"mystery_metric": 999.0}
    sig_bare = SIG.build_signals(None, None, None, bare, slice_dt="20260831")
    res_bare = AT.run(sig_bare, doc)
    e_bare = res_bare["insights"][0]
    check("T5-8 全无 baseline 时强度分量记 0、广度照算",
          e_bare["signal"] == 0 and e_bare["breadth"] > 0,
          f"signal={e_bare['signal']} breadth={e_bare['breadth']:.3f}")
    check("T5-9 全无 baseline 时写了 warning",
          any("无全辖基线" in w or "baseline" in w for w in res_bare["warnings"]))
    # 只有三个 feature 文件、其他全缺：signals 不得崩
    sig_min = SIG.build_signals(None, None, None, old_features, slice_dt="")
    check("T5-10 只有 features 输入（metrics/overview/org_risk 全缺）也能产出结构完整的 signals",
          all(k in sig_min for k in ("overall", "dimensions", "clue_matrix",
                                     "features", "continuation", "warnings")))


# =========================================================================
# T6 规则库字段自检
# =========================================================================
def test_t6(verbose, doc):
    print("\nT6 规则库字段自检：derived 引用的表/字段必须在 table-dict.json 中")
    if not os.path.exists(DICT_PATH):
        check("T6-0 shared/table-dict.json 存在", False, DICT_PATH)
        return
    with open(DICT_PATH, encoding="utf-8") as f:
        tables = json.load(f)["tables"]
    bad = []
    n_field_refs = 0
    for r in doc.get("derived") or []:
        d = r.get("derivation") or {}
        for t in d.get("tables") or []:
            if t not in tables:
                bad.append(f"{r['rule_id']} 表不存在: {t}")
        for ref in d.get("fields") or []:
            n_field_refs += 1
            if "." not in ref:
                bad.append(f"{r['rule_id']} 字段未带表名: {ref}")
                continue
            t, f = ref.split(".", 1)
            if t not in tables:
                bad.append(f"{r['rule_id']} 表不存在: {t}")
            elif f not in {c["field"] for c in tables[t]}:
                bad.append(f"{r['rule_id']} 字段不存在: {ref}")
    check("T6-1 derived 规则引用的表与字段全部在 table-dict.json 中",
          not bad, f"校验 {n_field_refs} 个字段引用" if not bad else "; ".join(bad[:5]))
    check("T6-2 每条 derived 规则都有 derivation（tables/fields/logic/direction）",
          all(all(k in (r.get("derivation") or {})
                  for k in ("tables", "fields", "logic", "direction"))
              for r in doc.get("derived") or []))
    check("T6-3 mined 规则的 cohort_lift 全部带 cohort_basis（可追溯来源）",
          all(r.get("cohort_basis") for r in doc.get("mined") or []))
    ids = [r["rule_id"] for r in doc.get("derived") or []]
    if verbose:
        print(f"     derived: {len(ids)} 条 {ids}")
    check("T6-4 derived 条数 ≥ 8", len(ids) >= 8, f"{len(ids)} 条")


# =========================================================================
# CLI 冒烟：--help 与 end-to-end 子进程调用
# =========================================================================
def test_cli(tmpdir):
    print("\nT7 CLI 冒烟")
    for script in ("signals.py", "attribution.py"):
        p = subprocess.run([sys.executable, os.path.join(HERE, script), "--help"],
                           capture_output=True, text=True)
        check(f"T7-1 {script} --help 可用", p.returncode == 0 and "usage" in p.stdout.lower(),
              p.stderr[-200:] if p.returncode != 0 else "")
    sig_path = os.path.join(tmpdir, "signals.json")
    attr_path = os.path.join(tmpdir, "attribution.json")
    p1 = subprocess.run([sys.executable, os.path.join(HERE, "signals.py"), "--mock",
                         "--out", sig_path], capture_output=True, text=True)
    check("T7-2 signals.py --mock 端到端跑通", p1.returncode == 0 and os.path.exists(sig_path),
          p1.stderr[-300:] if p1.returncode != 0 else "")
    p2 = subprocess.run([sys.executable, os.path.join(HERE, "attribution.py"),
                         "--signals", sig_path, "--rules", RULES_PATH,
                         "--out", attr_path], capture_output=True, text=True)
    check("T7-3 attribution.py 端到端跑通", p2.returncode == 0 and os.path.exists(attr_path),
          p2.stderr[-300:] if p2.returncode != 0 else "")
    if os.path.exists(attr_path):
        with open(attr_path, encoding="utf-8") as f:
            res = json.load(f)
        check("T7-4 产出 schema_version=3.0", res.get("schema_version") == "3.0")
        check("T7-5 产出含 topic_selection[] 且逐条有 decision/reason",
              bool(res.get("topic_selection")) and all(
                  t.get("decision") in ("selected", "candidate", "rejected") and t.get("reason")
                  for t in res["topic_selection"]))
    p3 = subprocess.run([sys.executable, os.path.join(HERE, "attribution.py"),
                         "--signals", os.path.join(tmpdir, "nope.json")],
                        capture_output=True, text=True)
    check("T7-6 输入不存在退出码 2", p3.returncode == 2, f"exit={p3.returncode}")


def main():
    ap = argparse.ArgumentParser(description="attribution/signals 引擎自测")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    if not os.path.exists(RULES_PATH):
        print(f"错误：规则库不存在 {RULES_PATH}", file=sys.stderr)
        return 2

    print("=" * 72)
    print("attribution 引擎自测（T1-T7）")
    print("=" * 72)
    test_t1(args.verbose)
    test_t2(args.verbose)
    doc = test_t3(args.verbose)
    test_t4(args.verbose)
    test_t5(args.verbose)
    test_t6(args.verbose, doc)
    with tempfile.TemporaryDirectory() as td:
        test_cli(td)

    print("\n" + "=" * 72)
    print(f"结果：{len(PASSED)} 通过 / {len(FAILED)} 失败")
    if FAILED:
        print("失败项：")
        for f in FAILED:
            print(f"  - {f}")
        return 1
    print("全部通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
