# 运行与集成说明

## 文件位置

项目根目录：

```text
C:\Users\Administrator\Documents\Codex\2026-06-30\wo-x\stock-recognition-system
```

核心代码：

- `stock_recognition_system/`：可运行 Python 软件包。
- `stock_recognition_system/cli.py`：命令行入口。
- `records/`：报告、模拟观察池、复盘样本。
- `skills/`：项目内保留的 skill 思路文档。
- `docs/`：设计、任务和运行说明。

## 怎么运行

根目录已经有两个启动脚本：

```powershell
.\run_stock_review.ps1
.\run_stock_review.ps1 simulate-list
.\run_stock_review.ps1 simulate-refresh
.\run_stock_review.ps1 simulate-summary --all
```

也可以直接用 Python：

```powershell
python -m stock_recognition_system.cli review `
  --message-file examples/group_message.txt `
  --current-price 21.90 `
  --account-value 34000 `
  --simulate
```

输出 JSON 给其他 AI：

```powershell
python -m stock_recognition_system.cli review `
  --message-file examples/group_message.txt `
  --current-price 21.90 `
  --account-value 34000 `
  --format json `
  --output records/latest-review.json
```

低 token 输出：

```powershell
python -m stock_recognition_system.cli review `
  --message-file examples/group_message.txt `
  --current-price 21.90 `
  --format json-compact
python -m stock_recognition_system.cli review `
  --message-file examples/group_message.txt `
  --current-price 21.90 `
  --format ai-brief
```

真实持仓与卖出监控：

```powershell
python -m stock_recognition_system.cli holding-add `
  --stock-code 300001 `
  --stock-name 测试股份 `
  --buy-price 10.00 `
  --shares 100 `
  --stop-loss 9.50 `
  --take-profit 11.00
python -m stock_recognition_system.cli holding-list
python -m stock_recognition_system.cli monitor
```

从模拟观察池升级为真实持仓记录：

```powershell
python -m stock_recognition_system.cli holding-add `
  --from-simulation-id sim-300821-xxxxxxxx `
  --buy-date 2026-07-02 `
  --shares 100
```

## 推荐形态

最合理的形态是“三层”：

1. 可运行软件：当前 Python 包和 CLI 是主系统，负责行情、规则、模拟观察和记录。
2. 轻量 skill：只保存工作流、命令和安全边界，用来节省 Codex/其他 AI 的上下文。
3. 结构化接口：用 `--format json-compact`、`--format ai-brief`、`records/simulations.json`、`records/outcomes.jsonl` 给其他 AI、表格或后续 Web UI 使用。

不要把整套系统只做成 skill。skill 适合省 token 和指导 AI；但行情拉取、模拟池、复盘统计必须是可运行软件，否则无法稳定自动化。

## 其他 AI 对接

其他 AI 只需要读取这些文件：

- `records/latest-review.json`：单次识别结果。
- `records/simulations.json`：模拟观察池。
- `records/outcomes.jsonl`：复盘样本库。
- `records/session-summary.md`：项目状态摘要。

`records/holdings.json` 是真实持仓文件，默认加入 `.gitignore`，不要发给不可信 AI。

给其他 AI 的最短提示：

```text
这是股票群消息风控系统。请只基于 records/latest-review.json 和 records/simulations.json 总结风险，不要直接荐股，不要要求重仓，不要忽略止损。
```
