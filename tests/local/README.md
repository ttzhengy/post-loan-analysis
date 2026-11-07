# tests/local —— 仅本地校验，不进交付包

## 为什么有这个目录

这个 skill 的运行环境是 **Windows**，没有 bash。所以任何 `.sh` 都不能出现在
skill 主体里，否则用户拿到包之后第一步就卡住。

正式的入口是 Python 版：

| 用途 | 正式入口（跨平台） |
|---|---|
| 单数据集全链路 | `python tools/run_chain.py <数据集目录> <输出目录>` |
| 4 数据集批量出报告 | `python tools/build_preview.py [输出根目录]` |

## 这里放的是什么

`run_chain.sh` / `build_preview.sh` 是上面两个 Python 入口的 bash 版本，
**只保留给 Linux/macOS 开发环境做交叉验证**：

1. 改完 Python 入口后，用同一份数据各跑一遍，比对中间产物；
2. 确认两套入口产出的数字一致，防止 Python 重写时漏掉环境变量、
   参数顺序、错误处理等细节。

## 比对方法

```bash
# Python 版
POST_LOAN_PY=.venv/bin/python DATA_DIR=/path/to/parquet BASE_SLICE=20260331 \
  python tools/run_chain.py synth/dataset_01 /tmp/chain_py

# bash 版
POST_LOAN_PY=.venv/bin/python DATA_DIR=/path/to/parquet BASE_SLICE=20260331 \
  bash tests/local/run_chain.sh synth/dataset_01 /tmp/chain_sh

# 逐文件比对（时间戳与浮点末位允许不同）
for f in combo_screen.json topic_gate.json signals.json mitigate.json internal_external.json; do
  diff <(python3 -m json.tool /tmp/chain_py/$f) \
       <(python3 -m json.tool /tmp/chain_sh/$f) | head -5
done
```

已知无害差异：

- `attribution.json` / `evidence.json` / `narrative.json` 的 `generated_at` 时间戳；
- `lift` 等聚合结果的浮点末位（DuckDB 并行聚合的求和顺序不同）。

## 打包时必须排除

交付包（zip / tar.gz）里**不允许**出现本目录。打包脚本请加：

```
--exclude=tests/local
--exclude=*.sh
```

`.sh` 一旦进了包，Windows 用户会看到一个跑不了的入口，比没有更糟。
