#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_fixture_eval.py — 造阳性/阴性夹具，判定「筛不出主题」是真零还是基率问题

为什么需要这套夹具
------------------
现实 fixture 的 universe 生成率是 32%，而真实贷后不良生成率只有 1%~4% 量级。
基率 32% 带来的直接后果：

    最优 lift 天花板 = 1 / 0.32 ≈ 3.1

也就是说，即使某个客群的不良率被打到 100%，相对全辖也只能是 3.1 倍。
而组合筛选门槛是 1.5 倍，看起来「够用」，但实际能达标的只有
真正被植入极强信号的那一小撮组合。于是「42 条候选全部 rejected」
既可能是「这批数据确实没有风险聚集」，也可能是「基率把 lift 压死了」，
**光看真实 fixture 无法区分**。

三项夹具
--------
1. null（阴性）
   客户属性与不良**完全独立**，任何组合都不该被判成现象。
   期望：phenomena_total == 0，且不产生任何「已确认」的归因。
   这是防止确认偏误的关键 —— 如果 null 数据也能筛出主题，
   说明阈值形同虚设。

2. planted（阳性）
   植入一个明确的子组：纯信用 + 大额，不良率约 12%，其余约 2%。
   期望：该子组被筛出，且 lift 显著、p 值达标。
   如果阳性夹具筛不出来，说明流程有假阴性 —— 真实数据里存在风险
   也会被漏掉。

3. weak（弱阳性 / 边界）
   植入一个很弱但真实存在的信号（约 1.6~1.8 倍）。
   期望：**可以**筛出，也可以不筛出，但必须与 null 的结果可区分，
   且不得给出「已确认」这种强结论。

判定口径
--------
每个夹具都以「流程自己的输出」为准（combo_screen.json 的 phenomena_total），
不在这里另算一套标准 —— 否则测的是夹具的真值，不是流程的判别力。
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import duckdb
except ImportError:  # pragma: no cover
    print("需要 duckdb: pip install duckdb", file=sys.stderr)
    sys.exit(2)

BASE_SLICE = "20260331"
CUR_SLICE = "20260831"
N_FORMS = 120000

# 各组夹具的信号强度：(纯信用+大额, 纯信用, 仅大额, 其余)
PRESETS = {
    # 阴性：所有格子的不良概率一致，与任何属性都无关
    "null":    (0.04, 0.04, 0.04, 0.04),
    # 阳性：强植入，纯信用+大额打到 12%，其余压在 2%
    "planted": (0.12, 0.02, 0.02, 0.02),
    # 弱阳性：真实但很弱
    "weak":    (0.065, 0.04, 0.04, 0.038),
}

SQL = """
COPY (
  WITH base AS (
    SELECT
      'C' || lpad(CAST(CAST(random()*60000 AS INT) AS VARCHAR), 7, '0') AS CUST_NO,
      'F' || lpad(CAST(i AS VARCHAR), 8, '0')                             AS FORM_NO,
      CASE WHEN random() < 0.6 THEN 'A701' ELSE 'A702' END                AS BUS_BREED_CD,
      CASE WHEN random() < 0.55 THEN '0101' ELSE '0201' END               AS GRTE_MOD_CD,
      ROUND(random()*800000, 2)                                           AS FORM_BAL_RMB,
      CASE WHEN random() < 0.5 THEN '1' ELSE '0' END                      AS CONT_LN_IND,
      CASE WHEN random() < 0.3 THEN 'CONT1' ELSE '' END                   AS CONTINUE_FLAG,
      CASE WHEN random() < 0.4 THEN '1' ELSE '0' END                      AS CYC_LN_IND,
      CASE WHEN random() < 0.5 THEN '01' ELSE '02' END                    AS RPAY_MOD_CD,
      CASE WHEN random() < 0.25 THEN '20220101'
           WHEN random() < 0.50 THEN '20230101'
           WHEN random() < 0.75 THEN '20240601'
           ELSE '20250601' END                                            AS LN_DAT,
      CAST(CAST(
        CASE WHEN random() < 0.70 THEN 0
             ELSE FLOOR(random()*200) + 1 END
      AS INT) AS VARCHAR)                                                 AS EXD_DAYS
    FROM range({n_forms}) t(i)
  ),
  attr AS (
    SELECT *,
      CASE
        WHEN GRTE_MOD_CD = '0101' AND FORM_BAL_RMB >= 500000 THEN {p_credit_big}
        WHEN GRTE_MOD_CD = '0101'                            THEN {p_credit}
        WHEN FORM_BAL_RMB >= 500000                          THEN {p_big}
        ELSE {p_other} END AS p_grade
    FROM base
  ),
  marked AS (
    SELECT *, CASE WHEN random() < p_grade THEN 1 ELSE 0 END AS will_grade FROM attr
  ),
  b AS (
    SELECT '{BASE}' AS DATA_DAT, CUST_NO, FORM_NO, BUS_BREED_CD, GRTE_MOD_CD,
           FORM_BAL_RMB, CONT_LN_IND, CONTINUE_FLAG, CYC_LN_IND, RPAY_MOD_CD,
           LN_DAT, EXD_DAYS, '1' AS RSK_CLS_CD, will_grade
    FROM marked
  ),
  c AS (
    SELECT '{CUR}' AS DATA_DAT, CUST_NO, FORM_NO, BUS_BREED_CD, GRTE_MOD_CD,
           ROUND(FORM_BAL_RMB * CASE WHEN will_grade = 1 THEN 0.95 ELSE 0.70 END, 2) AS FORM_BAL_RMB,
           CONT_LN_IND, CONTINUE_FLAG, CYC_LN_IND, RPAY_MOD_CD, LN_DAT, EXD_DAYS,
           CASE WHEN will_grade = 1 THEN '3' ELSE '1' END AS RSK_CLS_CD, will_grade
    FROM marked
  )
  SELECT DATA_DAT, BUS_BREED_CD, CUST_NO, FORM_NO, GRTE_MOD_CD, FORM_BAL_RMB,
         CONT_LN_IND, CONTINUE_FLAG, CYC_LN_IND, RPAY_MOD_CD, LN_DAT, EXD_DAYS, RSK_CLS_CD
  FROM b
  UNION ALL
  SELECT DATA_DAT, BUS_BREED_CD, CUST_NO, FORM_NO, GRTE_MOD_CD, FORM_BAL_RMB,
         CONT_LN_IND, CONTINUE_FLAG, CYC_LN_IND, RPAY_MOD_CD, LN_DAT, EXD_DAYS, RSK_CLS_CD
  FROM c
) TO '{out}' (FORMAT PARQUET)
"""


def build(kind, out_dir):
    p_cb, p_c, p_b, p_o = PRESETS[kind]
    d = out_dir / "G_00PF_PEAS_LN_VCH_DV"
    d.mkdir(parents=True, exist_ok=True)
    target = d / "part-0.parquet"
    con = duckdb.connect()
    con.execute(SQL.format(
        n_forms=N_FORMS, p_credit_big=p_cb, p_credit=p_c,
        p_big=p_b, p_other=p_o,
        BASE=BASE_SLICE, CUR=CUR_SLICE, out=str(target)))
    return con, target


def universe_rate(con, target):
    """按 chg 口径算全辖生成率 —— 与流程同口径，不另立标准。"""
    r = con.execute(f"""
        WITH b AS (
          SELECT FORM_NO, CAST(FORM_BAL_RMB AS DOUBLE) bal0,
                 CASE WHEN substr(RSK_CLS_CD,1,1) IN ('3','4','5') THEN 1 ELSE 0 END npl0
          FROM read_parquet('{target}') WHERE DATA_DAT='{BASE_SLICE}' AND BUS_BREED_CD LIKE 'A70%'
        ), c AS (
          SELECT FORM_NO, CAST(FORM_BAL_RMB AS DOUBLE) bal1,
                 CASE WHEN substr(RSK_CLS_CD,1,1) IN ('3','4','5') THEN 1 ELSE 0 END npl1
          FROM read_parquet('{target}') WHERE DATA_DAT='{CUR_SLICE}' AND BUS_BREED_CD LIKE 'A70%'
        )
        SELECT SUM(CASE WHEN b.npl0=0 AND COALESCE(c.npl1,0)=1
                        THEN COALESCE(c.bal1, b.bal0) ELSE 0 END) AS npl,
               SUM(b.bal0) AS tot
        FROM b LEFT JOIN c ON c.FORM_NO = b.FORM_NO
    """).fetchone()
    return (r[0] / r[1]) if r[1] else None


def planted_rate(con, target):
    """纯信用+大额子组的生成率，用来确认植入是否生效。"""
    r = con.execute(f"""
        WITH b AS (
          SELECT FORM_NO, GRTE_MOD_CD, CAST(FORM_BAL_RMB AS DOUBLE) bal0,
                 CASE WHEN substr(RSK_CLS_CD,1,1) IN ('3','4','5') THEN 1 ELSE 0 END npl0
          FROM read_parquet('{target}') WHERE DATA_DAT='{BASE_SLICE}' AND BUS_BREED_CD LIKE 'A70%'
        ), c AS (
          SELECT FORM_NO, CAST(FORM_BAL_RMB AS DOUBLE) bal1,
                 CASE WHEN substr(RSK_CLS_CD,1,1) IN ('3','4','5') THEN 1 ELSE 0 END npl1
          FROM read_parquet('{target}') WHERE DATA_DAT='{CUR_SLICE}' AND BUS_BREED_CD LIKE 'A70%'
        ), j AS (
          SELECT b.*, COALESCE(c.npl1,0) npl1, COALESCE(c.bal1,b.bal0) bal1
          FROM b LEFT JOIN c ON c.FORM_NO = b.FORM_NO
        )
        SELECT SUM(CASE WHEN npl0=0 AND npl1=1 THEN bal1 ELSE 0 END) / NULLIF(SUM(bal0),0)
        FROM j WHERE GRTE_MOD_CD='0101' AND bal0 >= 500000
    """).fetchone()
    return r[0]


def main():
    kind = sys.argv[1] if len(sys.argv) > 1 else "null"
    out_dir = Path(sys.argv[2] if len(sys.argv) > 2 else f"/tmp/fixture_{kind}")
    if kind not in PRESETS:
        print(f"未知类型 {kind}，可选：{', '.join(PRESETS)}", file=sys.stderr)
        return 2

    con, target = build(kind, out_dir)
    ur = universe_rate(con, target)
    pr = planted_rate(con, target)
    print(f"✅ {kind} → {target}")
    print(f"   universe 生成率：{ur:.2%}")
    print(f"   纯信用+大额子组：{pr:.2%}"
          + (f"（lift {(pr/ur):.2f}）" if ur else ""))
    if ur:
        print(f"   lift 天花板 1/{ur:.4f} = {1/ur:.2f} 倍")
    return 0


if __name__ == "__main__":
    sys.exit(main())
