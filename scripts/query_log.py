# -*- coding: utf-8 -*-
"""query_log.py — 查询日志记录（内部工作记录，不落入最终报告）

用途：记录每次查询的表、过滤条件、结果与查询思路，供复盘与可追溯。
输出：query_log.md（默认在 out-dir 下），以追加方式记录。
注意：本文件仅为日志工具，最终 report.html 不含这些内容。
"""
import os
from datetime import datetime


class QueryLog:
    def __init__(self, path=None, title="查询日志（内部工作记录）"):
        self.path = path
        self.title = title
        self.entries = []

    def ensure_file(self):
        if not self.path:
            return
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                f.write(f"# {self.title}\n\n> 本文件为查询过程留痕：记录中间数据、过滤条件与查询思路，仅供复盘，不落入最终报告。\n\n")

    def add(self, stage, table, query, result, thought):
        """记录一条查询日志"""
        entry = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stage": stage,
            "table": table,
            "query": query,
            "result": result,
            "thought": thought,
        }
        self.entries.append(entry)
        if self.path:
            self.ensure_file()
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(f"### [{entry['time']}] {stage}\n")
                f.write(f"- 查询表：{table}\n")
                f.write(f"- 过滤/查询：{query}\n")
                f.write(f"- 结果：{result}\n")
                f.write(f"- 思路：{thought}\n\n")

    def save(self):
        """独立保存（若未指定 path 则返回 entries 供调用方自行处理）"""
        return self.entries
