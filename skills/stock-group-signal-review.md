# Imported Skill: Stock Group Signal Review

本项目已导入 `stock-group-signal-review` 的核心思想：

- 群消息低可信。
- 先核验再计算。
- 数据缺失则降级。
- 当前价超过目标不追。
- 尾盘推送降级。
- 新手仓位上限保守。
- 每日记录和复盘群源。

项目内实现位置：

- `stock_recognition_system/parser.py`
- `stock_recognition_system/rules.py`
- `stock_recognition_system/risk.py`
- `stock_recognition_system/engine.py`
- `stock_recognition_system/records.py`
- `stock_recognition_system/reporting.py`
- `stock_recognition_system/technical.py`
- `stock_recognition_system/daily_timing.py`
- `stock_recognition_system/followup.py`
- `stock_recognition_system/cli.py`

常用命令：

```powershell
python -m stock_recognition_system.cli review --message-file examples/group_message.txt --current-price 21.90 --account-value 34000 --simulate
python -m stock_recognition_system.cli daily-timing --account-value 34000
python -m stock_recognition_system.cli condition-check --stock-code 603040
python -m stock_recognition_system.cli simulate-refresh --save-summary
python -m stock_recognition_system.cli monitor
```

`daily-timing` 只评估已经进入模拟观察池的股票，输出条件买入价、买入区间、止损止盈和当日动作。`可考虑条件单` 不等于现价买入，只表示价格回到系统条件价以内后可以人工二次确认。

券商 App 中已经手动设置的条件单记录在 `records/broker-conditional-orders.json`，该文件不应提交或外发。用 `condition-add` 登记，用 `condition-check` 或 `alert` 检查。
