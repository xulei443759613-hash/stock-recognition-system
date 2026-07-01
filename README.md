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
- 放弃真实仓位不等于删除机会；系统会给出机会评级、可执行价和复盘口径。
- 官方公告、财报、交易所和巨潮资讯证据优先；群截图属于低可信证据。

## 快速运行

```powershell
cd stock-recognition-system
.\run_stock_review.ps1
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

收到群消息后，也可以先输出证据采集计划，不做行情拉取：

```powershell
python -m stock_recognition_system.cli evidence-plan `
  --message-file examples/group_message.txt
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

把 C 档或暂不实盘的信号加入模拟观察池：

```powershell
python -m stock_recognition_system.cli review `
  --message-file examples/group_message.txt `
  --push-date 2026-07-01 `
  --push-time 10:57 `
  --current-price 21.37 `
  --account-value 34000 `
  --simulate
```

查看和更新模拟观察：

```powershell
python -m stock_recognition_system.cli simulate-list
python -m stock_recognition_system.cli simulate-refresh
python -m stock_recognition_system.cli alert
python -m stock_recognition_system.cli simulate-summary --all
python -m stock_recognition_system.cli simulate-update `
  --id sim-300821-xxxxxxxx `
  --as-of 2026-07-02 `
  --high-price 21.00 `
  --low-price 20.45 `
  --close-price 20.80
```

记录真实持仓并监控卖出信号：

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

给其他 AI 使用低 token 输出：

```powershell
python -m stock_recognition_system.cli review --message-file examples/group_message.txt --current-price 21.90 --format json-compact
python -m stock_recognition_system.cli review --message-file examples/group_message.txt --current-price 21.90 --format ai-brief
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
- 证据采集计划：自动把基金/社保、游资控盘、财务改善、评级、题材映射到应查来源和通过/否决标准。
- 时机判断：入场区间、尾盘、大盘/板块弱势、短期涨幅、涨停状态。
- 技术面体检：5 日/20 日涨跌幅、均价结构、振幅、量比、ATR14、RSI14、MACD、破位风险。
- 盈亏比计算：当前价、入场下沿、入场上沿分别计算。
- 关键价位：报告前部直接展示目标止盈、硬止损、短线 5%/8%/10% 止盈和综合可执行价。
- 系统建议止盈止损：综合参考买入价、原始目标/止损、账户亏损上限、近期支撑和波动，输出一个建议止盈价和一个建议止损价。
- 机会评级：把信号分成可小仓、模拟跟踪、等待更优价格、补证据观察、剔除机会。
- 训练档位：自动输出 A 档可实盘 100 股、B 档轻仓训练 100 股、C 档模拟观察、D 档放弃，并列出执行清单。
- 模拟观察池：`review --simulate` 自动创建纸面交易，`simulate-refresh` 自动拉取行情刷新状态，`simulate-summary` 汇总结果，`simulate-update` 支持手动按最高/最低/收盘价更新。
- 真实持仓监控：`holding-add` 记录真实持仓，`monitor` 批量检查止盈、止损和顺序待查。
- 提醒检查：`alert` 同时检查模拟观察池和真实持仓，触发入场、止盈、止损或顺序待查时输出提醒但不改写记录。
- 组合风险管理：`portfolio` 汇总真实持仓市值、持仓占比、计划止损亏损和组合风险警告。
- ATR 动态止损：自动行情包含高/低/收数据时，技术面会计算 ATR14，系统建议止损会纳入 ATR 候选。
- 低 token 输出：`json-compact` 输出核心字段，`ai-brief` 输出 120 字以内摘要，适合交给其他 AI。
- 入场计划：只输出条件计划，不输出无条件买入指令。
- 止损止盈：校验止损价，提示分批止盈和跌破退出。
- 仓位管理：按仓位上限和单笔最大亏损共同限制。
- 复盘记录：支持追加完整 Markdown 分析报告。
- 复盘任务：自动生成次日、3 日、5 日、10 日跟踪事项。
- 复盘样本库：支持用 `outcome` 记录真实结果到 `records/outcomes.jsonl`。
- 群源评分：累计样本后统计达标率、止损率、尾盘率、追高样本、可执行错失机会和非可执行上涨。

## 数据源路线

第一阶段默认手动输入当前价，避免误把缺失数据当成机会。

后续可启用：

- AkShare：行情、涨跌幅、换手率、量比。
- Tushare：日线、财务、公告等规范化数据，需要 token。
- 巨潮资讯/交易所公告：优先用于核验公告、调研、财报。

项目只接数据，不接券商自动交易。

## 产品化文档

- `AGENTS.md`: Codex 协作规范和完整交易系统约束。
- `docs/requirements.md`: 当前项目需求、输入输出和硬边界。
- `docs/architecture.md`: 当前模块架构和数据流。
- `docs/tasks.md`: 分阶段任务清单。
- `docs/PRODUCT_ROADMAP.md`: 稳定持续产品路线图。
- `docs/TRADING_SYSTEM_ADOPTION.md`: 完整交易系统规格在当前项目中的采纳计划。
- `docs/trading-system-spec.md`: 交易系统领域规格、指标、风控、回测和配置细则。
- `docs/EVIDENCE_PLAYBOOK.md`: 群消息证据采集、核验和否决标准。
- `docs/SKILL_EXPANSION_PLAN.md`: Codex/GitHub skill 和开源能力接入计划。
- `docs/RUNNING_AND_INTEGRATION.md`: 运行入口、skill/软件形态和其他 AI 对接方式。
- `config/config.yaml`: 长期配置模板，后续逐步接入代码。
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
