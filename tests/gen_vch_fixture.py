#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_vch_fixture.py — 造凭证级合成 parquet，用于离线验证 combo_split

产出 <out>/G_00PF_PEAS_LN_VCH_DV/part-0.parquet，**含两个切片**（对比时点 + 分析时点），
字段覆盖 combo_split 全部口径用到的列。

真值设计
--------
同一批凭证在对比时点（base_slice=20260331）**全部正常**，在分析时点（20260831）
有确定比例转为不良。因此：

  · vch 口径（存量不良率）：分子分母都取 20260831，是「谁现在坏了」
  · chg 口径（不良生成率）：分子 = 对比正常→分析不良，分母 = 对比时点在贷余额

两种口径在同一份数据上会给出**不同但都可验证**的数字，这正是要测的：
chg 口径下 universe 生成率应等于「被标记为 downgrade 的凭证余额 ÷ 全部对比时点余额」，
且 hit + nonhit 仍恒等于 universe（客户级归属不受口径影响）。

真值规律（生成概率）：
  信用 × 大额 → 0.75；仅信用 → 0.18；仅大额 → 0.15；其余 → 0.03
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

SQL = """
COPY (
  WITH base AS (
    SELECT
      'C' || lpad(CAST(CAST(random()*60000 AS INT) AS VARCHAR), 7, '0') AS CUST_NO,
      'F' || lpad(CAST(i AS VARCHAR), 8, '0')                              AS FORM_NO,
      CASE WHEN random() < 0.6 THEN 'A701' ELSE 'A702' END                 AS BUS_BREED_CD,
      CASE WHEN random() < 0.55 THEN '0100' ELSE '0200' END                AS GRTE_MOD_CD,
      ROUND(random()*800000, 2)                                            AS FORM_BAL_RMB,
      CASE WHEN random() < 0.5 THEN '1' ELSE '0' END                       AS CONT_LN_IND,
      CASE WHEN random() < 0.3 THEN 'CONT1' ELSE '' END                    AS CONTINUE_FLAG,
      CASE WHEN random() < 0.4 THEN '1' ELSE '0' END                       AS CYC_LN_IND,
      CASE WHEN random() < 0.5 THEN '01' ELSE '02' END                     AS RPAY_MOD_CD,
      CASE WHEN random() < 0.5 THEN '20230101' ELSE '20250601' END         AS LN_DAT,
      CAST(FLOOR(random()*200) AS INT)                                     AS EXD_DAYS
    FROM range(120000) t(i)
  ),
  -- 两层物化：DuckDB 不允许在同一 SELECT 里对带副作用的表达式（random()）
  -- 既取别名又立刻引用，所以先把属性落成 real 表再算概率
  attr AS (
    SELECT *,
      CASE
        WHEN GRTE_MOD_CD = '0100' AND FORM_BAL_RMB >= 500000 THEN 0.75
        WHEN GRTE_MOD_CD = '0100' THEN 0.18
        WHEN FORM_BAL_RMB  >= 500000 THEN 0.15
        ELSE 0.03 END AS p_grade
    FROM base
  ),
  marked AS (
    SELECT *, CASE WHEN random() < p_grade THEN 1 ELSE 0 END AS will_grade FROM attr
  ),
  -- 对比时点：全部正常（RSK_CLS_CD='1'），记录期初敞口
  b AS (
    SELECT '{BASE}' AS DATA_DAT, CUST_NO, FORM_NO, BUS_BREED_CD, GRTE_MOD_CD,
           FORM_BAL_RMB, CONT_LN_IND, CONTINUE_FLAG, CYC_LN_IND, RPAY_MOD_CD,
           LN_DAT, EXD_DAYS, '1' AS RSK_CLS_CD, will_grade
    FROM marked
  ),
  -- 分析时点：转为不良的置 '3'，余额按 0.92~1.0 折损；未转不良的余额部分归还
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


def main():
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/vchfix")
    d = out_dir / "G_00PF_PEAS_LN_VCH_DV"
    d.mkdir(parents=True, exist_ok=True)
    target = d / "part-0.parquet"
    con = duckdb.connect()
    con.execute(SQL.format(BASE=BASE_SLICE, CUR=CUR_SLICE, out=str(target)))

    rows = con.execute(f"""
        SELECT DATA_DAT, COUNT(*) , COUNT(DISTINCT CUST_NO),
               ROUND(SUM(CAST(FORM_BAL_RMB AS DOUBLE))/1e8, 2)
        FROM '{target}' GROUP BY 1 ORDER BY 1
    """).fetchall()
    for r in rows:
        print(f"  {r[0]}: 凭证 {r[1]:>7}  客户 {r[2]:>6}  余额 {r[3]} 亿")
    print(f"✅ {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
