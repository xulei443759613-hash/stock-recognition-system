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
.\run_stock_review.ps1 simulate-refresh --save-summary
.\run_stock_review.ps1 daily-timing
.\run_stock_review.ps1 alert
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
python -m stock_recognition_system.cli system-brief --format markdown --output records/system-brief.md
```

每日买入时机评估：

```powershell
python -m stock_recognition_system.cli daily-timing --account-value 34000
python -m stock_recognition_system.cli daily-timing --stock-code 002326 --format json
python -m stock_recognition_system.cli daily-timing --use-last-close
```

`daily-timing` 只读取模拟池中的股票。它按条件买入价、100 股亏损上限、计划止盈止损、盈亏比和技术指标排序，输出“可考虑条件单/等回踩/已触发转监控/仅模拟观察/回避”。条件单含义是低于或等于系统价位时提醒并人工确认，不是自动下单。

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
python -m stock_recognition_system.cli alert
python -m stock_recognition_system.cli portfolio
python -m stock_recognition_system.cli portfolio --use-buy-price
```

券商 App 条件单登记和检查：

```powershell
python -m stock_recognition_system.cli condition-add `
  --stock-code 603040 `
  --stock-name 新坐标 `
  --side buy `
  --operator "<=" `
  --trigger-price 70.50 `
  --shares 100
python -m stock_recognition_system.cli condition-list
python -m stock_recognition_system.cli condition-check --stock-code 603040
```

外部数据源边界：

```powershell
python -m stock_recognition_system.cli source-registry
python -m stock_recognition_system.cli source-registry --format json
python -m stock_recognition_system.cli research-wencai --query "今日强势但未涨停"
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
- `records/simulation_summaries.jsonl`：每日盘后模拟汇总数据库。
- `records/latest-simulation-summary.json`：最近一次盘后模拟汇总快照。
- `records/outcomes.jsonl`：复盘样本库。
- `records/session-summary.md`：项目状态摘要。
- `records/system-brief.md` / `records/system-brief.json`：给 Codex 或其他 AI 的项目级交接摘要。

`records/holdings.json` 和 `records/broker-conditional-orders.json` 是真实交易相关文件，默认加入 `.gitignore`，不要发给不可信 AI。

## 组合和动态止损

- `portfolio` 会汇总持仓数量、持仓市值、持仓占比、计划止损亏损和组合风险警告。
- 新手默认组合持仓占比上限为账户 30%，组合计划止损风险上限为账户 2%。
- 自动行情能提供高/低/收数据时，技术面会计算 ATR14，系统建议止损会把 ATR 动态止损作为候选之一。
- 技术面同时计算 RSI14 和 MACD；它们只作为短线辅助降级或提醒，不能单独把群消息升级为真实买入。
- `daily-timing` 是盘中或盘前的买入时机入口；`simulate-refresh --save-summary` 是盘后结算入口，两者不要混用。
- `alert` 是每日提醒入口，只读模拟池、真实持仓和券商条件单，不改写状态；需要结算模拟结果时继续用 `simulate-refresh`。
- 自动盘后任务应运行 `simulate-refresh --save-summary`，这样既刷新模拟池，也把当日汇总写入数据库。
- `source-registry` 用于查看外部数据源是否需要授权、能否参与决策、只能做研究还是可做行情证据。
- `research-wencai` 默认不联网，只生成研究占位 JSON，防止把问财候选直接当作买入信号。
- `system-brief` 是内部知识消化后的低 token 入口，适合在新线程或其他 AI 接手前先运行。

给其他 AI 的最短提示：

```text
这是股票群消息风控系统。请只基于 records/latest-review.json 和 records/simulations.json 总结风险，不要直接荐股，不要要求重仓，不要忽略止损。
```
