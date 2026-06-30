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
