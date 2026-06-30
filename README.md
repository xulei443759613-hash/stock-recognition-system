# Stock Recognition System

面向个人新手的股票群消息识别与风控系统。系统目标不是自动荐股或自动下单，而是把群内“金股”消息转成可核验、可打分、可复盘的结构化记录。

最终目标是形成一套个人风控决策辅助系统：识别股票消息、鉴别话术、采集市场数据、判断时机、生成条件式入场计划、校验止损止盈、控制仓位，并通过复盘评价群源质量。

## 核心原则

- 群消息只当线索，不当买卖指令。
- 当前价未知时，不输出可执行交易动作。
- 当前价超过目标价，不追。
- 当前价超过入场上沿，降级为观察或等待回踩。
- 14:30 后推送的消息降级，需要次日确认。
- 涨停后才看到，不追。
- 盈亏比低于 1.5，新手放弃。
- 官方公告、财报、交易所和巨潮资讯证据优先；群截图属于低可信证据。

## 快速运行

```powershell
cd stock-recognition-system
python examples/demo.py
python examples/source_quality_demo.py
```

也可以用命令行分析一条群消息：

```powershell
python -m stock_recognition_system.cli review `
  --message-file examples/group_message.txt `
  --push-time 14:40 `
  --current-price 21.90 `
  --five-day-change-pct 8.5 `
  --twenty-day-change-pct 18 `
  --account-value 10000 `
  --verified-claim 毛利率上升=true `
  --save
```

查看到期复盘任务：

```powershell
python -m stock_recognition_system.cli pending
```

记录一条复盘结果，并立刻更新群源评分：
```powershell
python -m stock_recognition_system.cli outcome `
  --stock-code 603991 `
  --stock-name 领先股份 `
  --source group `
  --push-date 2026-06-29 `
  --push-time 14:50 `
  --review-date 2026-07-04 `
  --action 放弃 `
  --signal-price 128.32 `
  --target-price 138.30 `
  --stop-loss 113.10 `
  --max-price 141.15 `
  --min-price 121.88 `
  --close-price 141.15 `
  --note "尾盘强推后次日涨停，但已超过目标价，系统不追高"
```

查看群源累计质量：
```powershell
python -m stock_recognition_system.cli source-score --source group
```

## 项目结构

```text
stock_recognition_system/    核心 Python 包
examples/                    示例
docs/                        规则和系统设计
records/                     每日记录和会话恢复
skills/                      导入的 Codex skill 说明
```

## 输出信号

- `放弃`
- `观察`
- `等待回踩`
- `模拟盘`
- `小仓位试错`
- `持有观察`
- `分批止盈`
- `止损/退出`

所有输出均为风控分析结果，不构成投资建议。

## 已实现能力

- 群消息解析：股票名、代码、入场区间、目标价、止损价、推荐逻辑。
- 红线检测：金股、必涨、内幕、控盘、游资、资金热度、服务团队转化、尾盘推送、免责声明矛盾。
- 硬性否决：缺当前价、超过目标、涨停、止损无效、跌破止损、价格结构无效。
- 证据核验：把推荐逻辑拆成已验证、未验证、反向证据、无法验证。
- 时机判断：入场区间、尾盘、大盘/板块弱势、短期涨幅、涨停状态。
- 技术面体检：5 日/20 日涨跌幅、均价结构、振幅、量比、破位风险。
- 盈亏比计算：当前价、入场下沿、入场上沿分别计算。
- 入场计划：只输出条件计划，不输出无条件买入指令。
- 止损止盈：校验止损价，提示分批止盈和跌破退出。
- 仓位管理：按仓位上限和单笔最大亏损共同限制。
- 复盘记录：支持追加完整 Markdown 分析报告。
- 复盘任务：自动生成次日、3 日、5 日、10 日跟踪事项。
- 复盘样本库：支持用 `outcome` 记录真实结果到 `records/outcomes.jsonl`。
- 群源评分：累计样本后统计达标率、止损率、尾盘率和追高样本。

## 数据源路线

第一阶段默认手动输入当前价，避免误把缺失数据当成机会。

后续可启用：

- AkShare：行情、涨跌幅、换手率、量比。
- Tushare：日线、财务、公告等规范化数据，需要 token。
- 巨潮资讯/交易所公告：优先用于核验公告、调研、财报。

项目只接数据，不接券商自动交易。

## 产品化文档

- `docs/PRODUCT_ROADMAP.md`: 稳定持续产品路线图。
- `docs/SKILL_EXPANSION_PLAN.md`: Codex/GitHub skill 和开源能力接入计划。
- `.github/workflows/ci.yml`: GitHub Actions 自动语法检查和单元测试。

## 短线模式自动行情

短线训练模式默认按 34,000 元账户、10% 训练仓、单笔最大亏损 0.5%、4-5 日观察周期计算。它只在主系统结论为“小仓位试错”、盈亏比达标、100 股一手成本和止损风险都可承受时，才允许进入短线计划。

可用公开行情接口自动补最近 20 个收盘价、最新日线收盘价、涨跌幅和换手率。系统优先尝试东方财富，失败时自动切换到腾讯行情；如果同时提供 `--push-date` 和 `--push-time`，系统会优先拉取腾讯分时价格，还原消息发出时的价格和当时涨跌幅：

```powershell
python -m stock_recognition_system.cli review `
  --message-file examples/group_message.txt `
  --push-date 2026-06-30 `
  --push-time 11:00 `
  --auto-market-data `
  --history-days 20 `
  --account-value 34000
```

手动传入的 `--current-price`、`--change-pct`、`--volume-ratio`、`--close-prices` 会优先覆盖自动行情，适合用券商截图价复盘消息发出时的真实价格。

兼容旧命令：`--auto-eastmoney` 仍可使用，内部同样会在东方财富失败时切换到腾讯行情。
