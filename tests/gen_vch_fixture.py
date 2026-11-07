#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_vch_fixture.py — 造凭证级合成 parquet，用于离线验证 combo_split

产出 <out>/G_00PF_PEAS_LN_VCH_DV/part-0.parquet，字段覆盖 combo_split 用到的全部列。
合成规律有明确真值，便于断言：
  credit(GRTE_MOD_CD=0100) × big(FORM_BAL_RMB>=50万) → 不良率最高
  单独 credit 或单独 big 抬升，但远小于交集
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import duckdb
except ImportError:  # pragma: no cover
    print("需要 duckdb: pip install duckdb", file=sys.stderr)
    sys.exit(2)


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/vchfix")
    d = out / "G_00PF_PEAS_LN_VCH_DV"
    d.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("INSTALL tpch; LOAD tpch;")   # 仅用于 random()，失败可忽略

    # 12 万凭证 / 约 6 万客户，两户一凭证再拆分，保证客户数 < 凭证数
    con.execute(f"""
    COPY (
      WITH base AS (
        SELECT
          '20260831' AS DATA_DAT,
          CASE WHEN random() < 0.6 THEN 'A701' ELSE 'A702' END AS BUS_BREED_CD,
          'C' || lpad(CAST(CAST(random()*60000 AS INT) AS VARCHAR), 7, '0') AS CUST_NO,
          CASE WHEN random() < 0.55 THEN '0100' ELSE '0200' END AS GRTE_MOD_CD,
          ROUND(random()*800000, 2) AS FORM_BAL_RMB,
          CASE WHEN random() < 0.5 THEN '1' ELSE '0' END AS CONT_LN_IND,
          CASE WHEN random() < 0.3 THEN 'CONT1' ELSE '' END AS CONTINUE_FLAG,
          CASE WHEN random() < 0.4 THEN '1' ELSE '0' END AS CYC_LN_IND,
          CASE WHEN random() < 0.5 THEN '01' ELSE '02' END AS RPAY_MOD_CD,
          CASE WHEN random() < 0.5 THEN '20230101' ELSE '20250601' END AS LN_DAT,
          CAST(FLOOR(random()*200) AS INT) AS EXD_DAYS
        FROM range(120000)
      ),
      flagged AS (
        SELECT *,
          -- 真值规律：信用 × 大额 → 不良概率 0.75；仅信用 0.18；仅大额 0.15；其余 0.03
          random() < CASE
            WHEN GRTE_MOD_CD='0100' AND FORM_BAL_RMB>=500000 THEN 0.75
            WHEN GRTE_MOD_CD='0100' THEN 0.18
            WHEN FORM_BAL_RMB>=500000 THEN 0.15
            ELSE 0.03 END AS is_npl
        FROM base
      )
      SELECT DATA_DAT, BUS_BREED_CD, CUST_NO, GRTE_MOD_CD, FORM_BAL_RMB,
             CONT_LN_IND, CONTINUE_FLAG, CYC_LN_IND, RPAY_MOD_CD, LN_DAT, EXD_DAYS,
             CASE WHEN is_npl THEN '3' ELSE '1' END AS RSK_CLS_CD
      FROM flagged
    ) TO '{d}/part-0.parquet' (FORMAT PARQUET)
    """)
    n = con.execute(f"SELECT COUNT(*), COUNT(DISTINCT CUST_NO) FROM '{d}/part-0.parquet'").fetchone()
    print(f"✅ {d}/part-0.parquet  凭证 {n[0]}  客户 {n[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
