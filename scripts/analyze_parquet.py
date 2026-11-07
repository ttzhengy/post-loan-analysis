#!/usr/bin/env python3
"""analyze_parquet.py — 用 DuckDB 分析 parquet 数据文件（替代 CSV 方式）

用法:
    python3 scripts/analyze_parquet.py [--data-dir ...] [--out ...]

产出:
    - 全部表概览（行数/列数/键字段/数据日期范围/样例）
    - 表间关联键核对（CUST_NO/ID_CARD_NO/FORM_NO/机构键）
"""
import argparse
import json
import os
import sys

import duckdb

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MANIFEST = "_manifest.json"


def main():
    ap = argparse.ArgumentParser(description="DuckDB parquet 表分析")
    ap.add_argument("--data-dir", default=r"C:\文档文件\繁星杯\决赛\数字员工工作区\数据文件duckdb\parquet")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    data_dir = args.data_dir
    con = duckdb.connect()

    # 1) 发现所有表目录（每个目录一个 parquet 表）
    tables = sorted(d for d in os.listdir(data_dir)
                    if os.path.isdir(os.path.join(data_dir, d)) and not d.startswith("_"))
    print(f"发现 {len(tables)} 张 parquet 表目录\n")

    # 2) 加载 manifest 补充中文名/分类
    manifest = {}
    mp = os.path.join(os.path.dirname(data_dir.rstrip("/\\")), MANIFEST)
    if os.path.exists(mp):
        manifest = json.load(open(mp, encoding="utf-8"))
    elif os.path.exists(os.path.join(data_dir, MANIFEST)):
        manifest = json.load(open(os.path.join(data_dir, MANIFEST), encoding="utf-8"))
    print(f"manifest 表条目: {len(manifest)}")

    # 3) 逐表注册视图 + 统计
    summary = []
    for t in tables:
        glob_path = os.path.join(data_dir, t, "part-*.parquet").replace("\\", "/")
        view = t.replace("-", "_")
        try:
            con.execute(f"CREATE OR REPLACE VIEW {view} AS SELECT * FROM read_parquet('{glob_path}')")
        except Exception as e:
            summary.append({"table": t, "error": str(e)[:100]})
            continue
        # 行数、列数
        cols = [r[0] for r in con.execute(f"DESCRIBE {view}").fetchall()]
        try:
            row_cnt = con.execute(f"SELECT count(*) FROM {view}").fetchone()[0]
        except Exception:
            row_cnt = -1
        # 键字段存在性
        key_hit = {k: (k in cols) for k in
                   ["CUST_NO", "ID_CARD_NO", "FORM_NO", "CUST_CD", "CUST_ID_NO", "C4_ORG_NO",
                    "EIMO_ORG_NO", "ORG_NO", "FNCL_ENT_NO", "DATA_DAT", "BUS_NO", "LAW_NO",
                    "CERT_NO", "CERTNO", "AST_NO", "ENTID_GX"]}
        present_keys = [k for k, v in key_hit.items() if v]
        # 数据日期
        date_vals = ""
        if "DATA_DAT" in cols:
            try:
                date_vals = str(con.execute(
                    f"SELECT string_agg(DISTINCT CAST(DATA_DAT AS VARCHAR), ',') FROM (SELECT DATA_DAT FROM {view} LIMIT 2000)").fetchone()[0])
            except Exception:
                pass
        info = manifest.get(t, {})
        summary.append({
            "table": t,
            "cn": info.get("cn", ""),
            "category": info.get("category", ""),
            "rows": row_cnt,
            "cols": len(cols),
            "keys": present_keys,
            "dates": (date_vals[:60] if date_vals else ""),
            "sample": str(cols[:8]),
        })

    # 4) 输出
    out_lines = []
    out_lines.append(f"{'表名':<46}{'中文名':<28}{'行数':<12}{'列数':<5}{'键字段'}")
    for s in summary:
        if "error" in s:
            out_lines.append(f"{s['table']:<46}ERROR: {s['error']}")
            continue
        out_lines.append(f"{s['table']:<46}{s['cn']:<28}{s['rows']:<12}{s['cols']:<5}{','.join(s['keys'])}")
    text = "\n".join(out_lines)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"\n完整 JSON 已保存: {args.out}")
    else:
        print(text)

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
