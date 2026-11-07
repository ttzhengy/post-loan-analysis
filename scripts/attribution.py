#!/usr/bin/env python3
"""attribution.py — 归因引擎 v3.0（双源规则库 + 完整强度公式 + 主题选择轨迹）

用法:
    python3 scripts/attribution.py --signals signals.json --rules references/rules.json \\
        --out attribution.json
    python3 scripts/attribution.py --signals signals.json      # rules 缺省取 ../references/rules.json
    python3 scripts/attribution.py --help

相对 v2.0 的实质变化（对应已诊断的 6 个缺陷）：
1. 强度不再等于 hit_ratio。改为 CONTRACT 第 3 节公式：
       breadth  = hit_count / total_members
       signal   = mean(norm(dev))  over hits,  norm(dev)=min(1, |dev|/SATURATION)
       strength = 0.6*breadth + 0.4*signal
   0.4 的强度分量此前从未实现，是「C01/C02/C03 永远霸榜」的根因。
2. 规则不再硬编码，改读 references/rules.json 的 manual + mined + derived 三段。
3. expr 支持 all_of / any_of / min_hits / min_any_hits / scale_max（一阶信号 + 低阶组合），
   成员池 > scale_max 时只枚举不超过 scale_max 阶的组合，避免组合爆炸。
4. cohort 校验（lift / 样本量）只作为允许升级为「显著」的门槛，不作为主分——
   理由见 README/交付说明：cohort 数据覆盖率极低（多数规则没有），若进主分会让
   有 cohort 的规则无条件压过结构性更强的规则；加成分 + 分级上限的做法既保住排序可比性，
   又保证「无 cohort 最高只能标一般」这条降级规则成立。
5. 输出 topic_selection[]：逐条记录进/出主题的理由，供预览版「主题生成轨迹」使用。
6. tie-break 显式实现：(-strength, -incremental_lift, -cohort_size, cross_stage, rule_id)，
   不再依赖 Python 稳定排序的隐式行为。

纯标准库。
"""
import argparse
import json
import math
import os
import sys
import time
from datetime import datetime
from itertools import combinations

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCHEMA_VERSION = "3.0"
DEFAULT_THRESHOLDS = {
    "saturation": 2.0,          # 偏离达基线的多少倍算满分
    "cohort_bonus_max": 0.15,   # cohort 加成上限
    "cohort_bonus_lift_span": 3.0,
    "significant": 0.5,
    "moderate": 0.3,
    "weak": 0.15,
    "min_cohort_size": 30,
    "min_lift": 1.5,
    "scale_max_default": 5,     # 组合阶数上限（防止 math.comb 爆炸）
}

LEVELS = ("显著", "一般", "弱信号", "淘汰")
LEVEL_OF = [(0.5, "显著"), (0.3, "一般"), (0.15, "弱信号")]


# =========================================================================
# 小工具
# =========================================================================
def _num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def _r(v, n=4):
    if v is None:
        return None
    return round(float(v), n)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# =========================================================================
# 规则加载（T3：双源/三源全部加载，总数与 rules.json 一致）
# =========================================================================
SOURCE_SECTIONS = ("manual", "mined", "derived")


def load_rules(rules_doc, warnings=None):
    """读 rules.json，返回 (rules, stats)。

    rules: list of dict，每条带归一化后的 expr / stages / cross_stage
    stats: {"manual": n, "mined": n, "derived": n, "total": n, "by_source": {...}}
    """
    warnings = warnings if warnings is not None else []
    rules = []
    stats = {s: 0 for s in SOURCE_SECTIONS}
    if not isinstance(rules_doc, dict):
        return rules, {"total": 0, **stats}

    # 兼容：整体就是一个 list（旧格式）
    if isinstance(rules_doc, list):
        sections = [("manual", rules_doc)]
    else:
        sections = [(s, rules_doc.get(s) or []) for s in SOURCE_SECTIONS]
        # 允许任意自定义段名
        for k, v in rules_doc.items():
            if k not in SOURCE_SECTIONS and isinstance(v, list) and v and isinstance(v[0], dict) \
                    and "rule_id" in v[0]:
                sections.append((k, v))
                stats.setdefault(k, 0)

    seen = set()
    for section, items in sections:
        if not isinstance(items, list):
            continue
        for raw in items:
            if not isinstance(raw, dict) or not raw.get("rule_id"):
                continue
            rid = str(raw["rule_id"])
            if rid in seen:
                warnings.append(f"规则 ID 重复，仅保留首条: {rid}")
                continue
            seen.add(rid)
            rule = normalize_rule(raw, section)
            rules.append(rule)
            stats[section] = stats.get(section, 0) + 1
            stats.setdefault("by_source", {})
            stats["by_source"][rule["source"]] = stats["by_source"].get(rule["source"], 0) + 1
    stats["total"] = len(rules)
    return rules, stats


def normalize_rule(raw, section):
    """兼容旧扁平 members → all_of + min_hits（CONTRACT 第 3 节末段）"""
    r = dict(raw)
    r["source"] = raw.get("source") or ("manual" if section == "manual" else "mined")
    r["section"] = section
    r.setdefault("version", 1)
    expr = raw.get("expr")
    if not isinstance(expr, dict):
        members = list(raw.get("members") or [])
        expr = {"all_of": members, "min_hits": raw.get("min_hits", len(members) or 1),
                "any_of": []}
        r["legacy_members"] = True
    expr = dict(expr)
    expr.setdefault("all_of", [])
    expr.setdefault("any_of", [])
    expr.setdefault("min_hits", len(expr["all_of"]))
    expr.setdefault("min_any_hits", 1)
    expr.setdefault("scale_max", DEFAULT_THRESHOLDS["scale_max_default"])
    # 成员 id 统一成 int（旧 members 是 int；json 里可能是字符串）
    expr["all_of"] = [_member_id(x) for x in expr["all_of"]]
    r["expr"] = expr
    if "stages" not in r or not r["stages"]:
        r["stages"] = []
    r.setdefault("cross_stage", False)
    r.setdefault("metrics", [])
    r.setdefault("evidence_hint", [])
    return r


def _member_id(x):
    """all_of 里可能混有 int（feature_id）或 dict（{"feature":...}/{"dim_bucket":...}）"""
    if isinstance(x, dict):
        return x
    n = _num(x)
    return int(n) if n is not None and float(n).is_integer() else x


# =========================================================================
# 信号表：feature / dim_bucket / clue / cont 四类可命中单元
# =========================================================================
STAGE_CANON = {
    "营销获客": "贷前", "贷前准入": "贷前", "贷中审查": "环节内", "征信核查": "贷前",
    "到期续贷": "贷后", "贷后管理": "贷后", "其他": "环节内",
    "客群结构": "贷前", "产品结构": "贷前", "账龄结构": "贷后", "机构管理": "贷后",
}


class SignalTable:
    """把 signals.json 展开成可求值的信号单元。

    单元 = {uid, kind, stage, metric(归一化偏离), raw, baseline, label}
    """

    def __init__(self, signals, warnings, hit_min_dev=0.20):
        self.signals = signals or {}
        self.warnings = warnings
        self.hit_min_dev = float(hit_min_dev)
        self.base_rate = _num((self.signals.get("overall") or {}).get("npl_rate"))
        self.units = {}          # uid -> unit
        self.features = {}       # feature_id -> unit
        self.dim_buckets = []    # list of units（维度档位）
        self.clues = {}          # clue_type -> unit
        self.cont = {}           # cont tool key -> unit
        self._build()

    # ---- feature ----
    def _build(self):
        sig = self.signals
        for f in sig.get("features") or []:
            if not isinstance(f, dict):
                continue
            fid = f.get("feature_id")
            status = f.get("status") or "ok"
            unit = {
                "kind": "feature", "uid": f"f{fid}", "feature_id": fid,
                "label": f.get("name", ""), "stage": f.get("stage", ""),
                "status": status,
                "metric": f.get("metric") or {}, "baseline": f.get("baseline") or {},
                "baseline_src": f.get("baseline_src", "inline"),
                "note": f.get("note", ""),
                "computable": status in ("ok", "approximate", "clue") and bool(f.get("metric")),
                "measured": status in ("ok", "approximate", "clue") and bool(f.get("metric")),
                "dev": None, "raw": None, "baseline_value": None, "dev_label": None,
                "score": None,
            }
            dev, raw, base, dlabel, _score = compute_deviation(unit, self.warnings)
            unit["raw"], unit["baseline_value"], unit["dev_label"] = raw, base, dlabel
            unit["dev"] = dev
            # ---- 命中判定：必须「超过」基线达阈值才算命中 ----
            # 关键修复：原实现只看 metric 非空就算命中，导致「值远低于基线」的
            # 正常特征也被当作命中，广度虚高到 1.0，弱信号数据集也能凑出主题。
            # 现在要求 dev >= hit_min_dev（相对基线偏离倍数），且方向为「高于基线」
            # （风险特征都是越高越差）；无基线时退化为「有值即命中」并降权标记。
            if dev is None:
                unit["hit"] = bool(f.get("metric"))
                unit["hit_by"] = "no_baseline_fallback"
            else:
                higher = (raw is not None and base is not None and raw > base)
                # 结构类指标（如接续占比、额度倍数）本身就是越高越差，同样适用
                unit["hit"] = bool(higher and dev >= self.hit_min_dev)
                unit["hit_by"] = f"dev={dev:.3f}>= {self.hit_min_dev}"
            self.features[fid] = unit
            self.units[unit["uid"]] = unit

        # ---- dim_bucket ----
        for dim_key, dim in (sig.get("dimensions") or {}).items():
            if not isinstance(dim, dict):
                continue
            for b in dim.get("buckets") or []:
                if not isinstance(b, dict) or not b.get("valid"):
                    continue
                rate = _num(b.get("npl_rate"))
                uid = f"dim:{dim_key}:{b.get('bucket')}"
                self.dim_buckets.append({
                    "kind": "dim_bucket", "uid": uid,
                    "dimension": dim_key, "dimension_name": dim.get("name", dim_key),
                    "bucket": b.get("bucket"),
                    "stage": dim.get("stage", ""),
                    "metric": {"npl_rate": rate, "bal": _num(b.get("bal")),
                               "offset_pp": _num(b.get("offset_pp"))},
                    "baseline": {"npl_rate": self.base_rate},
                    "raw": rate, "baseline_value": self.base_rate,
                    "dev": (abs(rate - self.base_rate) if (rate is not None and self.base_rate) else None),
                    "dev_label": "npl_rate", "computable": rate is not None,
                    "score": rate,
                })

        # ---- clue ----
        for ctype, c in (sig.get("clue_matrix") or {}).items():
            if not isinstance(c, dict):
                continue
            lift = _num(c.get("npl_lift"))
            self.clues[ctype] = {
                "kind": "clue", "uid": f"clue:{ctype}", "clue_type": ctype,
                "stage": "贷后", "lift": lift,
                "verify_false_pptn": _num(c.get("verify_false_pptn")),
                "trigger_npl_pptn": _num(c.get("trigger_npl_pptn")),
                "raw": c, "computable": lift is not None or _num(c.get("verify_false_pptn")) is not None,
            }

        # ---- continuation ----
        cont = sig.get("continuation") or {}
        for tool, t in (cont.get("tools") or {}).items():
            if not isinstance(t, dict):
                continue
            self.cont[tool] = {
                "kind": "cont_tool", "uid": f"cont:{tool}", "tool": tool,
                "stage": "贷后", "npl_rate": _num(t.get("npl_rate")),
                "bal": _num(t.get("bal")), "raw": t,
                # 接续工具是聚合单元（整张表一行），没有"基线"概念，
                # 其强度直接取不良率本身的严重程度（见 norm_of）
                "computable": _num(t.get("npl_rate")) is not None,
            }
        chain = cont.get("chain") or {}
        for key in ("rolling", "resolving"):
            c = chain.get(key) or {}
            self.cont[key] = {
                "kind": "cont_chain", "uid": f"cont:chain:{key}", "tool": key,
                "stage": "贷后", "npl_rate": _num(c.get("npl_rate")),
                "cnt": int(_num(c.get("cnt")) or 0), "raw": c,
                "computable": _num(c.get("npl_rate")) is not None,
            }

    # ---- 求值 ----
    def feature_unit(self, spec):
        """spec: int / "5" / {"feature_id": 5}"""
        if isinstance(spec, dict):
            spec = spec.get("feature_id", spec.get("feature"))
        n = _num(spec)
        fid = int(n) if n is not None else spec
        return self.features.get(fid)

    def clue_unit(self, clue_type):
        if clue_type in self.clues:
            return self.clues[clue_type]
        if isinstance(clue_type, str) and clue_type.upper().startswith("_ALL_"):
            return self.clues.get(clue_type)
        return None


def compute_deviation(unit, warnings):
    """特征相对 baseline 的偏离（相对倍数口径，不是绝对差）。

    返回 (dev, raw, baseline_value, label, score)
      dev  = |raw - baseline| / max(|baseline|, eps)    （相对倍数的"超出部分"）
             例：基线 0.05、现值 0.55 → dev = 10.0（偏离基线 10 倍）
                 基线 0.05、现值 0.0505 → dev = 0.01（偏离 1%）
      score= min(1, dev/SATURATION)                     （由调用方按 saturation 归一）

    为什么用相对倍数而非绝对差：
      「零散客户占比从 5% 升到 55%」与「余额从 8.6 亿到 8.65 亿」在业务上
      严重程度天差地别，绝对差会给出同样的 0.50，把量纲不同的指标拉平，
      导致真正的极端恶化淹没在噪声里。相对倍数才是"恶化程度"的正确度量。

    退化保护：
      - baseline 缺失 → dev=None，强度分量记 0，写 warning（T5）
      - baseline=0 且 raw=0 → dev=0（无偏离）
      - baseline=0 且 raw≠0 → dev 记 SATURATION 上限（从零起跳，视为满偏离），
        这是行业惯例：基线为零的指标一旦出现即属异常激增。
    """
    metric = unit.get("metric") or {}
    baseline = unit.get("baseline") or {}
    if not metric:
        return None, None, None, None, None

    eps = 1e-9
    best = None
    for label, val in metric.items():
        v = _num(val)
        if v is None:
            continue
        base = _num(baseline.get(label))
        if base is None:
            # 无对应基线：记录但不参与 signal 均值
            if best is None:
                best = (None, v, None, label, v, True)
            continue
        if abs(base) < eps:
            # 基线为零：出现即满偏离（而不是除零爆掉或被吞掉）
            dev = 0.0 if abs(v) < eps else 1e6
        else:
            dev = abs(v - base) / abs(base)
        if best is None or best[0] is None or dev > (best[0] or -1):
            best = (dev, v, base, label, v, False)

    if best is None:
        return None, None, None, None, None
    dev, v, base, label, _, no_baseline = best
    if no_baseline:
        warnings.append(
            f"特征「{unit.get('label')}」(id={unit.get('feature_id')}) 无全辖基线，强度分量记 0"
        )
        return None, v, None, label, v
    return dev, v, base, label, v


# =========================================================================
# 组合枚举（scale_max 防爆炸）
# =========================================================================
MAX_COMBOS = 5000


def combinations_count(n, k_max):
    if n <= 0:
        return 0
    return sum(math.comb(n, k) for k in range(1, min(k_max, n) + 1))


def min_hit_combos(candidates, min_hits, k_max):
    """枚举「至少 min_hits 个命中」的所有组合阶。

    修复（D 独立验证发现）：此前只枚举恰好 min_hits 阶，导致广度被系统性低估。
      breadth = hit_count / total_members。若一条 3 成员规则命中 3 个，
      正确广度是 3/3 = 1.0；旧实现只取 2 阶组合，最多拿到 2/3 = 0.667，
      规则强度被压低 0.2（0.6 权重 × 0.333），且成员越多低估越严重。

    因此这里枚举 [min_hits .. min(len(candidates), k_max)] 全部阶，
    由调用方的 better_eval 在候选组合间取 strength 最大者——
    全命中组合的 breadth 更高、signal 也更高（成员越多均值越稳），
    会自然胜出，不需要额外特判。

    k_max 控制枚举阶数上限，避免组合爆炸。
    """
    if not candidates:
        return []
    lo = max(1, min(min_hits, k_max))
    hi = min(len(candidates), max(k_max, lo))
    if len(candidates) < lo:
        return []
    out = []
    for k in range(lo, hi + 1):
        out.extend([list(c) for c in combinations(candidates, k)])
        if len(out) > MAX_COMBOS:
            break
    return out


# =========================================================================
# 单条规则打分
# =========================================================================
def evaluate_rule(rule, sigtab, thr):
    """对一个规则求值，返回 evaluation dict。"""
    expr = rule["expr"]
    all_of = expr.get("all_of") or []
    any_of = expr.get("any_of") or []
    min_hits = int(expr.get("min_hits") or 0)
    min_any = max(1, int(expr.get("min_any_hits") or 1))
    scale_max = int(expr.get("scale_max") or thr["scale_max_default"])
    saturation = thr["saturation"]

    total_members = len(all_of) + len(any_of)
    diag = {
        "rule_id": rule["rule_id"], "name": rule["name"], "source": rule["source"],
        "total_members": total_members, "all_of_total": len(all_of),
        "any_of_total": len(any_of), "min_hits": min_hits,
        "min_any_hits": min_any, "scale_max": scale_max,
        "exploded": False,
    }
    if total_members == 0:
        return Evaluation(rule, diag).reject("empty_rule", "expr 无成员")

    # ---- all_of 求解：每个成员解析成若干候选 unit ----
    all_cands = []          # [(spec, unit, norm)]
    expandable = 0          # 会产生多档、需要两两以上的成员数
    for spec in all_of:
        units = [u for u in resolve_spec(spec, sigtab) if u is not None]
        if len(units) > 1:
            expandable += 1
        cands = [(spec, u, norm_of(u, saturation)) for u in units]
        all_cands.extend(cands)

    n_pool = len(all_cands)
    combos_needed = max(1, min_hits) if min_hits > 0 else 1
    est = combinations_count(max(n_pool, 1), max(combos_needed, scale_max))
    if n_pool > 0 and est > MAX_COMBOS and expandable > 1:
        diag["exploded"] = True
        diag["estimated_combos"] = est
        ev = Evaluation(rule, diag)
        ev.reject("scale_max_exceeded",
                  f"候选成员 {n_pool} 个、最大阶 {max(combos_needed, scale_max)}，"
                  f"组合数约 {est} 超过上限 {MAX_COMBOS}，按 scale_max 规则跳过计算")
        ev.strength_below = True
        return ev

    # 只保留可计算且（对特征）真实命中的成员做组合
    # 关键修复：特征类成员必须 hit=True 才算「命中」；此前只看可计算，
    # 导致「值远低于基线」的正常特征也计入广度，广度恒等于 1.0。
    def _is_hit(u):
        if u is None or not u.get("computable"):
            return False
        if u.get("kind") == "feature":
            return bool(u.get("hit"))
        return True

    usable_all = [c for c in all_cands if c[1] is not None and c[1].get("computable")]
    usable = [c for c in usable_all if _is_hit(c[1])]
    n_not_hit = len(usable_all) - len(usable)
    n_no_baseline = sum(1 for c in usable if c[1].get("kind") == "feature" and c[2] is None)
    if n_not_hit:
        diag.setdefault("not_hit", n_not_hit)

    if min_hits <= 0:
        # 纯 any_of 规则：all_of 为空，直接空组合 + any_of
        combo_list = [[]]
    else:
        combo_list = min_hit_combos(usable, min_hits, scale_max)
        # 命中不足也要留一条「最佳部分命中」用于计算广度（广度 < min_hits/total）
        if not combo_list and usable:
            combo_list = [sorted(usable, key=lambda c: -(c[2] or 0))[:min_hits]]

    # ---- any_of 求解 ----
    any_pool = []           # [(spec, unit, norm)] 按 norm 降序
    for spec in any_of:
        units = [u for u in resolve_spec(spec, sigtab) if u is not None and u.get("computable")]
        best = None
        for u in units:
            s = norm_of(u, saturation)
            if s is None:
                continue
            if best is None or s > best[2]:
                best = (spec, u, s)
        if best is not None:
            any_pool.append(best)
    any_pool.sort(key=lambda c: -c[2])

    any_selected = any_pool if len(any_pool) >= min_any else []

    # ---- 逐组合计算，取 strength 最大者 ----
    best = None
    for combo in combo_list:
        members = list(combo) + any_selected
        if not members:
            continue
        if min_hits > 0 and len([m for m in combo]) + (min_any if any_selected else 0) > scale_max:
            continue
        ev = Evaluation(rule, diag)
        ev.compute(members, total_members, thr, n_no_baseline)
        if best is None or better_eval(ev, best):
            best = ev

    if best is None:
        ev = Evaluation(rule, diag)
        missing = [label_of(sp) for sp in all_of + any_of
                   if not [u for u in resolve_spec(sp, sigtab, thr) if u.get("computable")]]
        if not usable and not any_pool:
            reason = "no_signal_data_missing" if missing else "no_signal"
            note = ("无可求值信号：成员在 signals.json 中无对应单元（"
                    + "、".join(missing[:6]) + ("…" if len(missing) > 6 else "") + "）")
        else:
            reason = "no_signal"
            note = "成员存在但均未达到条件阈值"
        ev.reject(reason, note)
        return ev

    if min_hits > 0 and best.hit_count < min_hits:
        best.reject("min_hits_not_met",
                    f"仅命中 {best.hit_count}/{total_members}，低于 min_hits={min_hits}")
    return best


def better_eval(a, b):
    """等 strength 时：signal 高者优先 → 命中成员多者优先 → 按成员标签字典序（决定性）"""
    if abs(a.strength - b.strength) > 1e-12:
        return a.strength > b.strength
    if abs(a.signal - b.signal) > 1e-12:
        return a.signal > b.signal
    if a.hit_count != b.hit_count:
        return a.hit_count > b.hit_count
    return ",".join(label_of(m[0]) for m in a.members) < ",".join(label_of(m[0]) for m in b.members)


def resolve_spec(spec, sigtab, thr=None):
    """把一个 expr 成员解析成候选 unit 列表。

    成员原语（CONTRACT 第 3 节 expr 之上，本引擎扩展 4 种条件式成员，
    均对应表中真实存在的字段组合，不做虚构）：
      int                    基础特征命中（features.json 的 feature_id）
      {"feature": id}        同上（显式写法，可带 min_value/max_value）
      {"dim_bucket": {...}}  维度档位命中：dimension + bucket/bucket_prefix + min_npl_rate
      {"clue": {...}}        线索级命中：clue_type(*) + condition
      {"cont": {...}}        接续/结构命中：tool + min_npl_rate / min_value / max_npl_rate
    """
    thr = thr or DEFAULT_THRESHOLDS
    if not isinstance(spec, dict):
        u = sigtab.feature_unit(spec)
        return [u] if u else []
    if "feature" in spec:
        u = sigtab.feature_unit(spec["feature"])
        if not u:
            return []
        if "min_value" in spec or "max_value" in spec:
            return [u] if feature_passes(u, spec) else []
        return [u]
    if "dim_bucket" in spec:
        return resolve_dim_bucket(spec["dim_bucket"], sigtab)
    if "clue" in spec:
        return resolve_clue(spec["clue"], sigtab)
    if "cont" in spec:
        return resolve_cont(spec["cont"], sigtab, thr)
    return []


def feature_passes(unit, spec):
    v = _num(unit.get("raw"))
    if v is None:
        return False
    if spec.get("min_value") is not None and v < float(spec["min_value"]):
        return False
    if spec.get("max_value") is not None and v > float(spec["max_value"]):
        return False
    return True


def resolve_dim_bucket(cfg, sigtab):
    """维度档位：同一维度多个档同时满足时只取最差档（该维度的风险代表）"""
    out = []
    for u in sigtab.dim_buckets:
        if cfg.get("dimension"):
            if u["dimension"] != cfg["dimension"] and u.get("dimension_name") != cfg["dimension"]:
                continue
        if cfg.get("bucket") and u.get("bucket") != cfg["bucket"]:
            continue
        if cfg.get("bucket_prefix") and not str(u.get("bucket", "")).startswith(str(cfg["bucket_prefix"])):
            continue
        if cfg.get("any_bucket") and cfg.get("dimension"):
            pass  # any_bucket 只按维度选，命中后由下面的排序取最差档
        if cfg.get("min_npl_rate") is not None:
            r = _num(u.get("raw"))
            if r is None or r < float(cfg["min_npl_rate"]):
                continue
        out.append(u)
    if len(out) > 1:
        out.sort(key=lambda u: -(_num(u.get("raw")) or 0))
        return out[:1]
    return out


def resolve_clue(cfg, sigtab):
    """线索级条件。

    verify_false_high：核查不属实占比 ≥30% 且线索内不良占比 ≥1%（同向高位 → 核查失效）
    lift_high        ：线索不良率 lift ≥ 2.0
    """
    ctype = cfg.get("clue_type") or "*"
    cond = cfg.get("condition")
    items = [u for u in sigtab.clues.values() if u.get("computable")]
    if ctype != "*":
        items = [u for u in items if u.get("clue_type") == ctype]
    out = []
    for u in items:
        vf = u.get("verify_false_pptn")
        npl = u.get("trigger_npl_pptn")
        if cond == "verify_false_high":
            if vf is None or npl is None or vf < 0.30 or npl < 0.01:
                continue
        elif cond == "lift_high":
            if u.get("lift") is None or u["lift"] < 2.0:
                continue
        out.append(u)
    out.sort(key=lambda u: -(u.get("lift") or 0))
    return out[:3]


def resolve_cont(cfg, sigtab, thr):
    """接续/结构类条件。

    min_npl_rate : 该工具/结构的客群不良率下限
    min_value    : 结构指标下限（倍数、占比）
    max_npl_rate : 不良率上限（配合 min_value 表达「投入大、结果差」的反向条件）
    """
    tool = cfg.get("tool")
    if not tool:
        return []
    u = sigtab.cont.get(tool)
    if not u or not u.get("computable"):
        return []
    rate = _num(u.get("npl_rate"))
    raw = u.get("raw") or {}
    if cfg.get("min_npl_rate") is not None:
        if rate is None or rate < float(cfg["min_npl_rate"]):
            return []
    if cfg.get("min_value") is not None:
        v = _num(raw.get("value"))
        if v is None or v < float(cfg["min_value"]):
            return []
    if cfg.get("max_npl_rate") is not None and rate is not None:
        if rate > float(cfg["max_npl_rate"]):
            return []
    return [u]


def norm_of(unit, saturation):
    """单成员归一化强度 ∈ [0,1]。无基线/不可算 → None（不参与 signal 均值）"""
    if unit is None or saturation <= 0:
        return None
    kind = unit.get("kind")
    if kind in ("feature", "dim_bucket"):
        dev = unit.get("dev")
        if dev is None:
            return None
        return min(1.0, float(dev) / saturation)
    if kind == "clue":
        # 线索级：不良率 lift 高多少倍，就是偏离基线多少倍（lift=3 即偏离 2 倍基线）
        lift = unit.get("lift")
        if lift is None:
            return None
        return min(1.0, abs(lift - 1.0) / saturation)
    if kind in ("cont_tool", "cont_chain"):
        # 聚合单元没有 cohort 基线可用；信号大小 = 命中成员自身的严重程度。
        # 用 SATURATION 作为"满分不良率"的参照（默认 2.0 时，>2% 已属高位），
        # 无 npl_rate 时再看 value（结构指标）
        rate = unit.get("npl_rate")
        if rate is not None:
            return min(1.0, abs(rate) / saturation)
        v = _num((unit.get("raw") or {}).get("value"))
        return None if v is None else min(1.0, abs(v) / saturation)
    return None


class Evaluation:
    """单条规则一次求值的完整结果"""

    def __init__(self, rule, diag):
        self.rule = rule
        self.diag = diag
        self.strength = 0.0
        self.breadth = 0.0
        self.signal = 0.0
        self.hit_count = 0
        self.members = []            # [(spec, unit, norm)]
        self.n_no_baseline = 0
        self.reject_reason = None
        self.reject_note = ""

    def compute(self, members, total_members, thr, n_no_baseline=0):
        self.members = members
        self.hit_count = len(members)
        self.breadth = self.hit_count / total_members if total_members else 0.0
        norms = [m[2] for m in members if m[2] is not None]
        self.signal = sum(norms) / len(norms) if norms else 0.0
        self.strength = 0.6 * self.breadth + 0.4 * self.signal
        self.n_no_baseline = n_no_baseline
        return self

    def reject(self, reason, note=""):
        self.reject_reason = reason
        self.reject_note = note
        return self

    def hit_detail(self):
        out = []
        for spec, u, n in self.members:
            d = {"kind": u.get("kind"), "ref": label_of(spec)}
            if u.get("kind") == "feature":
                d.update({"feature_id": u.get("feature_id"), "name": u.get("label"),
                          "stage": u.get("stage"), "metric_label": u.get("dev_label"),
                          "value": _r(u.get("raw"), 6), "baseline": _r(u.get("baseline_value"), 6),
                          "dev": _r(u.get("dev"), 6), "norm": _r(n, 4)})
            elif u.get("kind") == "dim_bucket":
                d.update({"dimension": u.get("dimension_name"), "bucket": u.get("bucket"),
                          "value": _r(u.get("raw"), 6), "baseline": _r(u.get("baseline_value"), 6),
                          "offset_pp": _r((u.get("metric") or {}).get("offset_pp"), 2),
                          "norm": _r(n, 4)})
            elif u.get("kind") == "clue":
                d.update({"clue_type": u.get("clue_type"),
                          "npl_lift": _r(u.get("lift"), 4),
                          "verify_false_pptn": _r(u.get("verify_false_pptn"), 4),
                          "norm": _r(n, 4)})
            else:
                d.update({"tool": u.get("tool"), "npl_rate": _r(u.get("npl_rate"), 6),
                          "norm": _r(n, 4)})
            out.append(d)
        return out

    def stages(self):
        st = set(self.rule.get("stages") or [])
        for _, u, _ in self.members:
            if u.get("stage"):
                st.add(u["stage"])
        return sorted(st)


def label_of(spec):
    if isinstance(spec, dict):
        if "feature" in spec:
            return f"feature:{spec.get('feature_id', spec.get('feature'))}"
        if "dim_bucket" in spec:
            c = spec["dim_bucket"]
            return f"dim:{c.get('dimension')}:{c.get('bucket') or c.get('bucket_prefix') or '*'}"
        if "clue" in spec:
            return f"clue:{spec['clue'].get('clue_type')}"
        if "cont" in spec:
            return f"cont:{spec['cont'].get('tool')}"
    return f"feature:{spec}"


def compute_cross_stage(rule, stages):
    """cross_stage = 成员 stage 覆盖「贷前」和「贷后」，或跨越两类以上管理环节"""
    canon = {STAGE_CANON.get(s, s) for s in stages}
    if "贷前" in canon and "贷后" in canon:
        return True
    declared = rule.get("stages") or []
    declared_canon = {STAGE_CANON.get(s, s) for s in declared}
    if "贷前" in declared_canon and "贷后" in declared_canon:
        return True
    return bool(rule.get("cross_stage"))


# =========================================================================
# cohort 校验 + 分级（T4：无 cohort 最高只能「一般」）
# =========================================================================
def cohort_of(rule, ev, thr, signals=None):
    """规则的 cohort 校验数据。

    **关键区分「先验」与「当期证据」**：
      - `cohort_lift` 写在 rules.json 里的，是从**历史切片**（20260831）挖出来的
        先验统计量，它描述的是「这个组合历史上有多强」，不是「当期有多强」。
        若直接拿它当权重，等于把历史结论固化进当期报告 —— M01 会永远排第一。
        所以它只用于 tie-break 置顶参考，**不参与 strength 打分**。
      - 真正的当期证据来自 `signals.cohort_validation`（同切片实测的交集不良率），
        或命中的 clue 单元（同切片线索级不良率）。
    返回 {source, lift, size, npl_rate, incremental_lift, valid, basis, prior_lift}
    """
    prior_lift = _num(rule.get("cohort_lift"))     # 先验，仅 rank 参考
    lift = None
    size = None
    npl_rate = None
    source = None

    # 1) 当期实测校验（优先）：signals.cohort_validation[rule_id]
    if isinstance(signals, dict):
        cv = (signals.get("cohort_validation") or {}).get(rule.get("rule_id"))
        if isinstance(cv, dict) and _num(cv.get("lift")) is not None:
            lift = _num(cv.get("lift"))
            size = _num(cv.get("size"))
            npl_rate = _num(cv.get("npl_rate"))
            source = "signals_measured"

    # 2) 命中 clue 单元的线索级不良率（同切片，可当客群校验）
    if lift is None:
        for _, u, _ in ev.members:
            if u.get("kind") == "clue" and u.get("lift") is not None:
                lift = u.get("lift")
                raw = u.get("raw") or {}
                npl_rate = _num(raw.get("trigger_npl_pptn"))
                cnt = _num(raw.get("trigger_ctrt_cnt"))
                size = cnt if cnt else None
                source = "clue"
                break

    if lift is None:
        return {"source": None, "lift": None, "size": size, "npl_rate": npl_rate,
                "incremental_lift": _r(rule.get("incremental_lift"), 4),
                "prior_lift": prior_lift,
                "valid": False, "basis": ""}

    valid = lift >= thr["min_lift"] and (size is None or size >= thr["min_cohort_size"])
    return {
        "source": source, "lift": round(float(lift), 4),
        "size": int(size) if size is not None else None,
        "npl_rate": _r(npl_rate, 6),
        "incremental_lift": _r(rule.get("incremental_lift"), 4),
        "prior_lift": prior_lift,
        "valid": bool(valid),
        "basis": rule.get("cohort_basis", ""),
    }


def grade(ev, cohort, thr):
    """返回 (level, strength_final, reason)

    分级规则（CONTRACT 第 3 节）：
      >=0.5 显著 / >=0.30 一般 / >=0.15 弱信号 / <0.15 淘汰
      且「无 cohort 校验数据的线索最高只能标一般」——包括三种情形：
        a) 完全无 cohort 数据
        b) 有 cohort 但 lift < min_lift
        c) 有 cohort 但样本量 < min_cohort_size
    """
    raw = ev.strength
    has_cohort = cohort.get("lift") is not None
    bonus = 0.0
    if has_cohort:
        bonus = thr["cohort_bonus_max"] * min(
            1.0, max(0.0, (cohort["lift"] - 1.0) / thr["cohort_bonus_lift_span"]))
    final = raw * (1.0 + bonus)

    if ev.reject_reason:
        return "淘汰", raw, ev.reject_reason

    if final >= thr["significant"]:
        if not has_cohort:
            return "一般", raw, "no_cohort_validation"
        if not cohort.get("valid"):
            reason = ("lift_insufficient" if cohort["lift"] < thr["min_lift"]
                      else "sample_too_small")
            return "一般", raw, reason
        return "显著", raw, None

    if final >= thr["moderate"]:
        return "一般", raw, None
    if final >= thr["weak"]:
        return "弱信号", raw, "strength_below_threshold"
    return "淘汰", raw, "strength_below_threshold"


def topic_decision(level, ev, cohort, thr):
    """CONTRACT 第 7 节进主题条件。

    本引擎拿不到 evidence_chain（B 产出），因此按「无钻取数据」分支：
      显著 且 strength>=0.5                     → selected（可直接进主题）
      一般 且 strength>=0.30                    → candidate（需 evidence_chain 验证后才进主题）
    其余 → rejected，reason 写明是哪一条卡住的。
    """
    if level == "显著" and ev.strength >= thr["significant"]:
        return "selected", "selected_significant_with_cohort"
    if level == "一般" and ev.strength >= thr["moderate"]:
        return "candidate", "await_evidence_chain"
    if ev.reject_reason:
        return "rejected", ev.reject_reason
    if level == "一般" and not cohort.get("lift") and ev.strength >= thr["moderate"]:
        return "rejected", "await_evidence_chain"
    return "rejected", "strength_below_threshold"


# =========================================================================
# 排序 / 主流程
# =========================================================================
def rank_key(item):
    """tie-break: (-strength, -incremental_lift, -cohort_size, cross_stage, -prior_lift, rule_id)

    注意：prior_lift（rules.json 里的历史 cohort_lift）只用于**强度完全并列时**
    打平，绝不进入 strength 计算，否则历史结论会固化当期报告。
    """
    return (
        -round(item["strength"], 10),
        -round(item["incremental_lift"] or 0.0, 10),
        -round(float(item["cohort_size"] or 0), 10),
        0 if item["cross_stage"] else 1,     # cross_stage=True 排前面
        -round(float(item.get("prior_lift") or 0.0), 10),
        item["rule_id"],
    )


def selection_key(t):
    """topic_selection 与 insights 使用同一套 tie-break（含 prior_lift 打平项）"""
    return (
        -round(t["strength"] or 0.0, 10),
        -round(t["incremental_lift"] or 0.0, 10),
        -round(float(t["cohort_size"] or 0), 10),
        0 if t["cross_stage"] else 1,
        -round(float(t.get("prior_lift") or 0.0), 10),
        t["rule_id"],
    )


def run(signals, rules_doc, saturation=None, overrides=None):
    warnings = list(signals.get("warnings") or [])
    thr = dict(DEFAULT_THRESHOLDS)
    for k, v in ((rules_doc or {}).get("thresholds") or {}).items():
        if isinstance(v, (int, float)) and k in thr:
            thr[k] = v
    if saturation is not None:
        thr["saturation"] = float(saturation)
    if overrides:
        thr.update({k: v for k, v in overrides.items() if v is not None})

    rules, stats = load_rules(rules_doc, warnings)
    if not rules:
        warnings.append("rules.json 为空或无法解析：没有任何规则可评估")

    sigtab = SignalTable(signals, warnings)

    evals = []
    topic_selection = []
    for rule in rules:
        ev = evaluate_rule(rule, sigtab, thr)
        coh = cohort_of(rule, ev, thr, signals=signals)
        level, strength_final, reason = grade(ev, coh, thr)
        cross = compute_cross_stage(rule, ev.stages())
        decision, dec_reason = topic_decision(level, ev, coh, thr)
        hits = ev.hit_detail()
        item = {
            "rule_id": rule["rule_id"], "name": rule["name"], "essence": rule.get("essence", ""),
            "source": rule["source"], "version": rule.get("version", 1),
            "strength": _r(strength_final, 4),
            "strength_raw": _r(ev.strength, 4),
            "breadth": _r(ev.breadth, 4),
            "signal": _r(ev.signal, 4),
            "hit_count": ev.hit_count,
            "member_total": ev.diag["total_members"],
            "level": level,
            "cross_stage": cross,
            "stages": ev.stages(),
            "cohort": coh,
            "incremental_lift": coh.get("incremental_lift"),
            "cohort_size": coh.get("size"),
            "prior_lift": coh.get("prior_lift"),
            "members": hits,
            "metrics": [h.get("metric_label") or h.get("name") or h.get("bucket") or h.get("tool")
                        for h in hits],
            "evidence_hint": rule.get("evidence_hint", []),
            "reason": reason,
            "note": ev.reject_note,
            "exploded": bool(ev.diag.get("exploded")),
        }
        evals.append(item)
        topic_selection.append({
            "rule_id": rule["rule_id"], "name": rule["name"], "source": rule["source"],
            "decision": decision, "reason": dec_reason,
            "level": level, "strength": item["strength"], "strength_raw": item["strength_raw"],
            "breadth": item["breadth"], "signal": item["signal"],
            "hit_count": item["hit_count"], "member_total": item["member_total"],
            "saturation": thr["saturation"], "min_hits": rule["expr"].get("min_hits"),
            "scale_max": rule["expr"].get("scale_max"),
            "cohort_lift": coh.get("lift"), "cohort_size": coh.get("size"),
            "incremental_lift": coh.get("incremental_lift"),
            "prior_lift": coh.get("prior_lift"), "cohort_source": coh.get("source"),
            "cohort_valid": coh.get("valid"), "cohort_source": coh.get("source"),
            "cross_stage": cross, "exploded": item["exploded"],
            "hits": [
                {
                    "ref": h.get("ref"), "kind": h.get("kind"),
                    "label": h.get("name") or h.get("bucket") or h.get("clue_type") or h.get("tool"),
                    "metric": h.get("metric_label"),
                    "value": h.get("value", h.get("npl_rate", h.get("npl_lift"))),
                    "baseline": h.get("baseline"),
                    "norm": h.get("norm"),
                } for h in hits
            ],
        })

    evals.sort(key=rank_key)
    topic_selection.sort(key=selection_key)
    for i, e in enumerate(evals, 1):
        e["rank"] = i

    strong = [e for e in evals if e["level"] == "显著"]
    moderate = [e for e in evals if e["level"] == "一般"]
    weak = [e for e in evals if e["level"] == "弱信号"]
    selected = [t for t in topic_selection if t["decision"] == "selected"]
    candidates = [t for t in topic_selection if t["decision"] == "candidate"]
    rejected = [t for t in topic_selection if t["decision"] == "rejected"]

    # 主题同源检测：命中成员高度重叠的主题实际上是同一资产的不同切面，
    # 报告里应合并叙述，否则读者会误以为是多个独立发现。
    for i, a in enumerate(selected):
        a_refs = {str(h.get("ref")) for h in (a.get("hits") or []) if h.get("ref")}
        if not a_refs:
            continue
        same = []
        for b in selected[i + 1:]:
            b_refs = {str(h.get("ref")) for h in (b.get("hits") or []) if h.get("ref")}
            if not b_refs:
                continue
            overlap = a_refs & b_refs
            jac = len(overlap) / len(a_refs | b_refs)
            if jac >= 0.5:
                same.append({"rule_id": b.get("rule_id"), "name": b.get("name"),
                             "jaccard": round(jac, 3), "shared": sorted(overlap)})
        if same:
            a["same_source_as"] = same

    # 主题选择轨迹汇总：拒绝原因分布（给预览版渲染用）
    reason_count = {}
    for t in topic_selection:
        key = t["reason"] or "unknown"
        reason_count[key] = reason_count.get(key, 0) + 1

    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "signals_slice": signals.get("slice"),
        "overall": signals.get("overall") or {},
        "thresholds": thr,
        "strength_formula": {
            "expression": "strength = signal * (0.7 + 0.3*breadth)",
            "breadth": "max_i(coverage_i)，成员覆盖率最大值（feature=numerator/denominator，"
                       "dim_bucket=该档余额/总余额，clue=coverage_bal_pptn，cont=余额/总余额）",
            "signal": "mean_i( min(1, |dev_i| / SATURATION) ) over hits",
            "cohort_bonus": "strength *= (1 + 0.15*min(1,(cohort_lift-1)/3))，仅当存在 cohort 校验",
            "levels": {"显著": thr["significant"], "一般": thr["moderate"],
                       "弱信号": thr["weak"]},
            "degrade_rule": "无 cohort 校验（或 lift/sample 不达标）的规则最高只能标「一般」",
        },
        "rule_stats": stats,
        "coverage": {
            "rules_total": stats.get("total", 0),
            "by_source": stats.get("by_source", {}),
            "significant": len(strong), "moderate": len(moderate), "weak": len(weak),
            "selected_topics": len(selected), "candidate_topics": len(candidates),
            "rejected_rules": len(rejected),
            "features_seen": len(sigtab.features),
            "features_computable": sum(1 for u in sigtab.features.values() if u.get("computable")),
            "clue_types": len(sigtab.clues), "cont_units": len(sigtab.cont),
        },
        # —— 兼容层：render_report 旧版本读 insights / strong_insights / top / actions ——
        "insights": evals,
        "strong_insights": strong,
        "moderate_insights": moderate,
        "weak_insights": weak,
        "feature_rank": feature_rank(sigtab, thr),
        # —— v3 新增 ——
        "topic_selection": topic_selection,
        "topic_trace_summary": {
            "by_decision": {"selected": len(selected), "candidate": len(candidates),
                            "rejected": len(rejected)},
            "by_reason": reason_count,
        },
        "topics": selected,
        "top": {"org": [], "mgr": [], "breed": []},
        "actions": build_actions(strong + moderate),
        "warnings": warnings,
    }
    return result


def feature_rank(sigtab, thr):
    """特征按归一化强度排序（报告「风险画像」素材，不再是规则）"""
    rows = []
    for u in sigtab.features.values():
        if not u.get("computable"):
            continue
        n = norm_of(u, thr["saturation"])
        rows.append({
            "feature_id": u.get("feature_id"), "name": u.get("label"),
            "dimension": "", "stage": u.get("stage"), "metric": u.get("metric"),
            "baseline": u.get("baseline"), "dev": _r(u.get("dev"), 6),
            "norm": _r(n, 4), "status": u.get("status"), "note": u.get("note", ""),
        })
    rows.sort(key=lambda r: (-(r["norm"] or 0), str(r["feature_id"])))
    return rows


def build_actions(items):
    """动作草案：给「做什么 + 拿什么验证」；责任岗/时限由 narrative/人工补"""
    actions = []
    for i, e in enumerate(items[:8], 1):
        coh = e.get("cohort") or {}
        actions.append({
            "action_id": f"A-{i:03d}",
            "quadrant": "立即整改" if e["level"] == "显著" else "例行优化",
            "linked_rule": e["rule_id"],
            "dimension": "组合线索",
            "group": e["name"],
            "action": f"针对「{e['name']}」：先按命中特征组合取数验证客群不良差异，"
                      f"再按证据缺口分级处置（{e['essence']}）",
            "verify_with": e.get("evidence_hint", []),
            "owner": "{{待补：责任岗}}", "deadline": "{{待补：时限}}",
            "kpi": "客群不良率差异验证 / 专项核查覆盖率",
            "baseline": (f"命中客群不良率 {coh['npl_rate']:.2%}、lift {coh['lift']}"
                         if coh.get("lift") and coh.get("npl_rate") is not None
                         else "{{待补：需客群校验}}"),
            "target": "{{待补}}",
            "incomplete": True,
        })
    return actions


def default_rules_path():
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, "..", "references", "rules.json"),
                 os.path.join(here, "rules.json")):
        if os.path.exists(cand):
            return os.path.normpath(cand)
    return ""


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="归因引擎 v3.0：signals.json + rules.json → attribution.json"
                    "（0.6*广度+0.4*强度、cohort 降级、主题选择轨迹）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n"
               "  python3 scripts/attribution.py --signals signals.json --out attribution.json\n"
               "  python3 scripts/attribution.py --signals signals.json --rules references/rules.json \\\n"
               "      --saturation 1.5 --min-lift 1.8 --verbose")
    ap.add_argument("--signals", required=True, help="signals.py 输出 signals.json")
    ap.add_argument("--rules", default=None,
                    help="规则库 rules.json（缺省取 ../references/rules.json）")
    ap.add_argument("--out", default="attribution.json")
    ap.add_argument("--saturation", type=float, default=None,
                    help="强度饱和点：偏离达基线的多少倍计满分（默认 2.0）")
    ap.add_argument("--min-lift", type=float, default=None,
                    help="cohort 进「显著」的最低 lift（默认 1.5）")
    ap.add_argument("--min-cohort-size", type=float, default=None,
                    help="cohort 最低样本量（默认 30）")
    ap.add_argument("--rules-out", default="", help="可选：把实际使用的 rules.json 副本另存")
    ap.add_argument("--verbose", action="store_true", help="打印每条规则的得分与拒绝理由")
    args = ap.parse_args(argv)

    rules_path = args.rules or default_rules_path()
    if not os.path.exists(args.signals):
        print(f"错误：输入文件不存在: {args.signals}", file=sys.stderr)
        return 2
    if rules_path and not os.path.exists(rules_path):
        print(f"错误：规则库不存在: {rules_path}", file=sys.stderr)
        return 2
    try:
        signals = load_json(args.signals)
    except (json.JSONDecodeError, OSError) as e:
        print(f"错误：signals.json 解析失败: {e}", file=sys.stderr)
        return 2
    rules_doc = {}
    if rules_path:
        try:
            rules_doc = load_json(rules_path)
        except (json.JSONDecodeError, OSError) as e:
            print(f"错误：rules.json 解析失败: {e}", file=sys.stderr)
            return 2
    else:
        print("警告：未找到 rules.json，将在空规则库上运行", file=sys.stderr)

    result = run(signals, rules_doc, saturation=args.saturation,
                 overrides={"min_lift": args.min_lift, "min_cohort_size": args.min_cohort_size})
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    if args.rules_out:
        with open(args.rules_out, "w", encoding="utf-8") as f:
            json.dump(rules_doc, f, ensure_ascii=False, indent=2)

    cov = result["coverage"]
    print(f"✅ 归因完成 → {args.out}（规则 {cov['rules_total']} 条："
          + "、".join(f"{k} {v}" for k, v in cov["by_source"].items()) + "）")
    print(f"   显著 {cov['significant']} / 一般 {cov['moderate']} / 弱信号 {cov['weak']}"
          f" → 进主题 {cov['selected_topics']}、候选 {cov['candidate_topics']}、"
          f"淘汰 {cov['rejected_rules']}")
    if args.verbose:
        for e in result["insights"]:
            print(f"   {e['rank']:>2}. {e['rule_id']:<4} {e['name'][:16]:<18} "
                  f"[{e['level']}] S={e['strength']:.3f} "
                  f"(广{e['breadth']:.2f} + 强{e['signal']:.2f}) "
                  f"{e['hit_count']}/{e['member_total']} "
                  f"{'cross ' if e['cross_stage'] else '      '}"
                  f"{e['reason'] or ''}")
    for w in result["warnings"][:8]:
        print(f"   ⚠️ {w}")
    if len(result["warnings"]) > 8:
        print(f"   ⚠️ …… 另有 {len(result['warnings']) - 8} 条 warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
