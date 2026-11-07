#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_falsify.py — 可证伪检验模块的断言

覆盖：
  F1 时间集中性：集中 → support；均匀 → refute；不足三年 → unavailable
  F2 剂量反应：单调递增 → support；单调递减 → refute；无趋势 → neutral
  F3 行为分化：批次差异大 → 指向贷后；差异小 → 指向准入
  F4 客群资质对照：客群内正常客户也差 → 提示结构因素
  F5 汇总：全 unavailable → untested（不得默认成立）；有 refute → refuted
  F6 措辞红线：survived 必须写明「不等于已证明」
  F7 在线：真实 fixture 上四个检验都能跑出结论

用法：python3 tests/verify_falsify.py [--data-dir /tmp/vchfix3]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import falsify as F   # noqa: E402

CFG = dict(F.DEFAULT_CFG)


class Checker:
    def __init__(self):
        self.n = 0
        self.fail = []

    def ok(self, cond, label, detail=""):
        if cond:
            self.n += 1
            print(f"  ✅ {label}")
        else:
            self.fail.append(label)
            print(f"  ❌ {label} {detail}")

    def summary(self):
        total = self.n + len(self.fail)
        print(f"\n{'='*60}\n通过 {self.n}/{total}")
        for f in self.fail:
            print(f"  ✗ {f}")
        return 0 if not self.fail else 1


def _rows(years, rates, n=1000):
    """构造时间序列行：years/rates 等长。"""
    out = []
    for y, r in zip(years, rates):
        bal = 1e8
        out.append({"yr": y, "cohort_bal": bal, "cohort_npl": bal * r,
                    "cohort_n": n})
    return out


def test_temporal(c):
    print("\n[F1] 时间集中性")
    # 集中在最后一年
    r = F.check_temporal(_rows(["2022", "2023", "2024"], [0.01, 0.01, 0.12]), CFG)
    c.ok(r["verdict"] == "support", "集中在单一年份 → support", r["verdict"])

    # 均匀分布
    r = F.check_temporal(_rows(["2022", "2023", "2024"], [0.10, 0.10, 0.10]), CFG)
    c.ok(r["verdict"] == "refute", "各年均匀 → refute（不像一次性变化）", r["verdict"])
    c.ok("结构性" in r["reason"], "均匀时措辞指向结构性问题")

    # 年份不足
    r = F.check_temporal(_rows(["2023", "2024"], [0.1, 0.2]), CFG)
    c.ok(r["verdict"] == "unavailable", "仅两年 → unavailable", r["verdict"])

    # 无不良
    r = F.check_temporal(_rows(["2022", "2023", "2024"], [0, 0, 0]), CFG)
    c.ok(r["verdict"] == "unavailable", "无新增不良 → unavailable", r["verdict"])


def test_dose(c):
    print("\n[F2] 剂量反应")
    def mk(rates):
        return [{"bucket": f"b{i}", "n": 500, "tot_bal": 1e7,
                 "npl_bal": 1e7 * r} for i, r in enumerate(rates)]

    r = F.check_dose(mk([0.02, 0.05, 0.12, 0.25]), CFG)
    c.ok(r["verdict"] == "support", "单调递增 → support", r["verdict"])

    r = F.check_dose(mk([0.25, 0.12, 0.05, 0.02]), CFG)
    c.ok(r["verdict"] == "refute", "单调递减 → refute（方向相反）", r["verdict"])
    c.ok("方向与假设相反" in r["reason"], "递减时明确指出方向相反")

    r = F.check_dose(mk([0.10, 0.12, 0.09, 0.11]), CFG)
    c.ok(r["verdict"] == "neutral", "无趋势 → neutral", r["verdict"])

    # 乱序输入必须按语义顺序重排后再判（SQL GROUP BY 不保证顺序）
    shuffled = [{"bucket": "高档", "n": 500, "tot_bal": 1e7, "npl_bal": 1e7 * 0.30},
                {"bucket": "低档", "n": 500, "tot_bal": 1e7, "npl_bal": 1e7 * 0.05},
                {"bucket": "中档", "n": 500, "tot_bal": 1e7, "npl_bal": 1e7 * 0.15}]
    r = F.check_dose(shuffled, CFG)
    c.ok(r["verdict"] == "support",
         "乱序输入（高/低/中）按语义重排后判为递增", r["verdict"])

    # 样本不足
    rows = mk([0.02, 0.05, 0.12])
    for x in rows:
        x["n"] = 10
    r = F.check_dose(rows, CFG)
    c.ok(r["verdict"] == "unavailable", "样本不足 → unavailable", r["verdict"])


def test_behavior(c):
    print("\n[F3] 准入 vs 贷后")
    # 批次差异大 → 贷后
    r = F.check_behavior(_rows(["2022", "2023", "2024"], [0.30, 0.10, 0.04]), CFG)
    c.ok(r["verdict"] == "support_loan_after",
         "老批次明显更差 → 指向贷后", r["verdict"])

    # 批次差异小 → 准入
    r = F.check_behavior(_rows(["2022", "2023", "2024"], [0.10, 0.11, 0.10]), CFG)
    c.ok(r["verdict"] == "support_admission",
         "各批次接近 → 指向准入", r["verdict"])

    # 单批次
    r = F.check_behavior(_rows(["2024"], [0.1]), CFG)
    c.ok(r["verdict"] == "unavailable", "仅一个批次 → unavailable", r["verdict"])


def test_control(c):
    print("\n[F4] 客群资质对照")
    # 客群内正常客户逾期率也显著高
    rows = [{"grp": "cohort_normal", "n": 2000, "exd_n": 600},   # 30%
            {"grp": "all_normal", "n": 50000, "exd_n": 2500}]     # 5%
    r = F.check_control(rows, CFG)
    c.ok(r["verdict"] == "support_structural",
         "客群正常客户也差 → 提示结构因素", r["verdict"])

    # 无差异
    rows = [{"grp": "cohort_normal", "n": 2000, "exd_n": 100},
            {"grp": "all_normal", "n": 50000, "exd_n": 2500}]
    r = F.check_control(rows, CFG)
    c.ok(r["verdict"] == "neutral", "无差异 → neutral", r["verdict"])

    # 客群正常客户显著更好 → 风险集中于个体
    rows = [{"grp": "cohort_normal", "n": 5000, "exd_n": 1000},   # 20%
            {"grp": "all_normal", "n": 50000, "exd_n": 20000}]    # 40%
    r = F.check_control(rows, CFG)
    c.ok(r["verdict"] == "support_isolated",
         "客群正常客户显著更优 → 风险集中于个体", r["verdict"])
    c.ok("显著低于" in r["reason"], "区分「显著更好」与「无差异」的措辞")

    # 样本不足
    rows = [{"grp": "cohort_normal", "n": 10, "exd_n": 5},
            {"grp": "all_normal", "n": 50000, "exd_n": 2500}]
    r = F.check_control(rows, CFG)
    c.ok(r["verdict"] == "unavailable", "客群正常客户过少 → unavailable", r["verdict"])


def test_aggregate(c):
    print("\n[F5] 汇总与红线")
    # 全部 unavailable → untested
    checks = [{"test": "temporal_cluster", "verdict": "unavailable"},
              {"test": "dose_response", "verdict": "unavailable"}]
    a = F.aggregate(checks)
    c.ok(a["status"] == "untested", "全 unavailable → untested", a["status"])
    c.ok("不得视为成立" in a["note"], "untested 明确说明不得默认成立")

    # 有 refute → refuted
    checks = [{"test": "temporal_cluster", "verdict": "refute"},
              {"test": "dose_response", "verdict": "support"}]
    a = F.aggregate(checks)
    c.ok(a["status"] == "refuted", "含 refute → refuted（一票否决）", a["status"])

    # 有 support 无 refute → survived
    checks = [{"test": "temporal_cluster", "verdict": "support"},
              {"test": "dose_response", "verdict": "neutral"}]
    a = F.aggregate(checks)
    c.ok(a["status"] == "survived", "有支持无反驳 → survived", a["status"])
    c.ok("不等于已证明" in a["note"], "survived 必须写明不等于已证明")

    # 全 neutral → weakened
    checks = [{"test": "temporal_cluster", "verdict": "neutral"},
              {"test": "dose_response", "verdict": "neutral"}]
    a = F.aggregate(checks)
    c.ok(a["status"] == "weakened", "全中性 → weakened", a["status"])

    # support_structural 不计入支持分
    checks = [{"test": "control_profile", "verdict": "support_structural"}]
    a = F.aggregate(checks)
    c.ok(a["status"] == "weakened",
         "仅结构性提示不算支持", a["status"])

    print("\n[F6] 措辞红线")
    txt = F.build_narrative("测试假设",
                            [{"test": "temporal_cluster", "verdict": "support",
                              "reason": "集中"}],
                            {"status": "survived", "note": "1 项检验未发现反驳且支持假设；"
                             "注意这只能说明「未被推翻」，不等于已证明"})
    c.ok("不等于已证实" in txt, "survived 叙事含「不等于已证实」")
    # 只要没有「已证明：」「已证明该」这类肯定表述即可；
    # 「不等于已证实」本身包含"已证"字样，属于允许的否定式。
    import re as _re
    bad = _re.search(r"已证明[^，。；]{0,6}(假设|结论|成立|为真)", txt)
    c.ok(bad is None, "叙事中不出现「已证明…成立/为真」的肯定表述",
         bad.group(0) if bad else "")

    txt = F.build_narrative("测试假设", [], {"status": "untested", "note": "x"})
    c.ok("待验证" in txt, "untested 叙事写明待验证")

    txt = F.build_narrative("测试假设",
                            [{"test": "dose_response", "verdict": "refute",
                              "reason": "方向相反"}],
                            {"status": "refuted", "note": "x"})
    c.ok("不应作为结论引用" in txt, "refuted 叙事明确不可引用")


def test_online(c, data_dir):
    print(f"\n[F7] 在线（数据 {data_dir}）")
    import drill_executor as dx
    duckdb = dx._load_duckdb()
    if duckdb is None:
        print("  ⚠️  duckdb 未安装，跳过")
        return False
    con = duckdb.connect()

    conds = [F.cs.GRTE_CREDIT_ONLY,
             F.cs.FEATURE_COND[13]["cond"]]
    from types import SimpleNamespace
    args = SimpleNamespace(slice="20260831", base_slice="20260331",
                           data_dir=data_dir)
    h = F.run_one(con, dx, "纯信用大额客群", conds, args, dict(F.DEFAULT_CFG))

    c.ok(len(h["checks"]) >= 3, "在线：至少跑出 3 项检验", len(h["checks"]))
    c.ok(h["aggregate"]["status"] in
         ("survived", "refuted", "weakened", "untested"),
         "在线：汇总状态合法", h["aggregate"]["status"])
    av = [x for x in h["checks"] if x["verdict"] != "unavailable"]
    c.ok(len(av) >= 3, "在线：至少 3 项可用（未被数据不足挡掉）",
         f"可用 {len(av)}/{len(h['checks'])}")
    for x in h["checks"]:
        print(f"     {x['test']:20} {x['verdict']:20} {str(x.get('reason',''))[:60]}")
    return True


def main():
    data_dir = None
    for i, a in enumerate(sys.argv):
        if a == "--data-dir" and i + 1 < len(sys.argv):
            data_dir = sys.argv[i + 1]
    c = Checker()
    test_temporal(c)
    test_dose(c)
    test_behavior(c)
    test_control(c)
    test_aggregate(c)

    online = False
    if data_dir and Path(data_dir).exists():
        online = test_online(c, data_dir)
    else:
        print("\n[F7] 跳过在线测试（未提供 --data-dir）")

    rc = c.summary()
    if not online and rc == 0:
        print("\n注意：只跑了离线断言，在线部分未验证。")
    return rc


if __name__ == "__main__":
    sys.exit(main())
