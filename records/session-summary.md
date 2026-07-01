# Session Summary

Date: 2026-06-30

## 用户设定

- 新手个人投资者。
- 使用群内“金股”消息作为观察线索。
- 需要 AI 做核验、打分、防追高、仓位保护和复盘。

## 已导入规则

- 群消息只当线索。
- 超过目标不追。
- 缺当前价不输出可执行动作。
- 尾盘推送降级。
- 盈亏比低于 1.5 新手放弃。
- 连续记录 20-30 条后再评价群源。

## 当前扩展

- 已增加统一 Markdown 风控报告。
- 已增加证据核验状态：已验证、未验证、反向证据、无法验证。
- 已增加时机判断：入场区间、尾盘、短期涨幅、大盘和板块弱势。
- 已增加条件式入场计划、止损止盈计划、仓位计划。
- 已增加 AkShare/Tushare 可选数据源适配器。
- 已增加群源质量评分函数。
- 已增加技术面体检：5 日/20 日涨跌幅、均价结构、振幅、量比。
- 已增加复盘任务：次日、3 日、5 日、10 日跟踪。
- 已增加命令行入口：`python -m stock_recognition_system.cli review`。
- 已增加产品路线图：`docs/PRODUCT_ROADMAP.md`。
- 已增加 skill 扩展计划：`docs/SKILL_EXPANSION_PLAN.md`。
- 已增加单元测试和 GitHub Actions CI。
- 已支持按消息日期生成复盘任务。

## 下一步优先级

1. 用真实群消息持续记录 20 条以上。
2. 手动补当前价和 1/3/5/10 日结果。
3. 再决定是否安装 AkShare 或 Tushare 接入行情。
4. 保持不接自动交易。
5. 建立真实样本库后再调整评分阈值。
6. 优先接入行情数据的消息时价格，不用当前价格替代历史判断。

## 2026-07-01 短线模式收尾

- Codex 命令执行已恢复，`compileall` 和单元测试可以正常运行。
- 已完成 4-5 日短线训练计划：按 34,000 元账户、10% 训练仓、单笔最大亏损 0.5%、100 股一手门槛、最低盈亏比 1.8 进行过滤。
- 已接入双日线数据源：`EastMoneyDailyDataProvider` 优先，`TencentDailyDataProvider` 兜底；CLI 支持 `--auto-market-data --history-days 20` 自动补当前日线收盘价、涨跌幅、换手率和近期收盘价，`--auto-eastmoney` 保留为兼容参数。
- 规则保持保守：主系统不是“小仓位试错”、一手成本超训练仓、一手止损风险超上限、盈亏比不足、涨停或追高时，短线模式不允许真实买入。

## 2026-07-01 产品闭环调优

- 已增加复盘样本库 `records/outcomes.jsonl`，用追加写入保存真实复盘结果。
- CLI 新增 `outcome` 命令，用于记录目标触达、止损触发、尾盘推送、追高样本和复盘价格。
- CLI 新增 `source-score` 命令，用于按群源统计样本数、目标触达率、止损率、尾盘率和追高率。
- 样本少于 20 条时仍只观察，不把少量样本当成策略有效证明。

## 2026-07-01 消息时价格自动化

- 根据石英股份 603688 的 2026-06-30 11:00 群消息，接入腾讯分时分钟线。
- `--auto-market-data` 在存在 `--push-date` 和 `--push-time` 且未手动传 `--current-price` 时，自动使用消息发出时之前最近一分钟价格。
- 分时价格同步写入当时涨跌幅和涨停状态，避免使用次日或收盘行情污染历史消息判断。
- 石英股份样本自动取到 2026-06-30 11:00 价格 82.90，系统结论仍为放弃，核心原因是话术风险、当前价高于入场上沿、盈亏比不足和一手风险超训练仓。

## 2026-07-01 东方财富接口降级

- 确认东方财富官网可访问，但 `push2his.eastmoney.com` K 线历史接口在当前环境会被服务端断开。
- `EastMoneyDailyDataProvider` 已改为 K 线优先；K 线失败时降级到 `push2.eastmoney.com` 实时行情接口。
- 实时接口只提供当前价、涨跌幅、换手率，不提供历史收盘价序列；系统会写入数据警告，CLI 继续使用腾讯行情兜底历史数据。

## 2026-07-01 证据采集剧本

- 新增 `stock_recognition_system/evidence_playbook.py`，把群消息逻辑映射为应查来源、采集字段、通过标准和否决标准。
- 新增 CLI `evidence-plan`，不拉行情也能先输出证据采集计划。
- 风控报告新增“证据采集计划”章节。
- GitHub/开源能力判断：当前优先使用 GitHub Actions、AkShare/Tushare 数据层和 pandas 样本统计；Tushare data skill 需要 token 后再接入；Qlib/OpenBB/backtrader 暂缓到复盘样本足够后。
- 东岳硅材 300821 样本验证：消息时点价 21.37，系统结论仍为放弃。

## 2026-07-01 机会评级和错失复盘

- 新增 `stock_recognition_system/opportunity.py`，把“真实仓位动作”和“机会观察价值”分开。
- 风控报告新增“机会评级”章节，输出评级、状态、可执行价、需要回撤幅度和错失机会复盘口径。
- 东岳硅材 300821 在 21.37 时仍不允许真实仓位，但评级为 C/等待更优价格，训练模式综合可执行价为 20.50。
- `records.score_source_quality` 新增可执行错失率、非可执行上涨率、顺序待查率。
- `outcome` 命令记录复盘后会立即输出机会复盘分类。

## 2026-07-01 系统建议止盈止损

- 新增 `stock_recognition_system/exit_suggestion.py`，输出系统建议止盈价和系统建议止损价。
- 建议价位基于参考买入价、原始目标/止损、账户单笔亏损上限、近 5 日支撑和近期波动综合计算。
- 报告前部“关键价位”会显示系统建议止盈价、系统建议止损价和建议盈亏比。
- 东岳硅材样本：参考等待买入价 20.50，建议止盈 22.14，建议止损 19.48。

## 2026-07-01 训练档位

- 新增 `stock_recognition_system/training.py`，把结论自动分为 A 档可实盘 100 股、B 档轻仓训练 100 股、C 档模拟观察、D 档放弃。
- 报告新增“训练档位”章节，输出是否允许真实 100 股、参考买入价、系统止盈止损、预计盈利亏损和执行清单。
- B 档用于解决“系统过于保守导致什么都做不了”的问题：不放松硬性否决，但在价格、止损、100 股亏损和轻仓盈亏比达标时允许 100 股训练。
- 东岳硅材 21.37 口径保持 C 档，因为当前价高于训练可执行价；到 20.50 附近才重新评估。

## 2026-07-01 模拟观察池

- 新增 `stock_recognition_system/simulation.py`，支持 `review --simulate` 自动创建纸面交易。
- 新增 `simulate-list`、`simulate-update`、`simulate-refresh` 和 `simulate-summary`，可手动或自动更新等待入场、模拟持仓、模拟止盈、模拟止损和顺序待查，并汇总模拟净额。
- 模拟观察不假设追高成交；如果当前价高于系统参考买入价，先记录为“等待入场”。
- 对新手操作建议：真实下单前先让 C/B 档样本在模拟池跑出一批结果，用可执行错失率和模拟止损率判断规则是否需要放宽或收紧。

## 2026-07-01 运行入口和 AI 对接

- 新增根目录启动脚本 `run_stock_review.ps1` 和 `run_stock_review.bat`，用于直接查看可用命令或转发 CLI 参数。
- `review` 命令新增 `--format json`，可把完整结构化识别结果输出给其他 AI 或自动化脚本。
- 新增 `docs/RUNNING_AND_INTEGRATION.md`，明确系统应保持“可运行软件 + 轻量 skill + JSON/records 接口”的三层形态。

## 2026-07-01 GLM 5.2 建议采纳

- 采纳 P0：`review --format json-compact` 输出核心字段，`review --format ai-brief` 输出 120 字以内摘要，用于节省其他 AI 对接 token。
- 采纳 P0：新增 `stock_recognition_system/holdings.py`，支持真实持仓记录和卖出监控。
- 新增 CLI：`holding-add`、`holding-list`、`monitor`。`monitor` 会检查止盈、止损、同周期同时触发的顺序待查，也支持手动价格输入。
- `holding-add --from-simulation-id` 支持把模拟观察池中的记录升级为真实持仓记录。
- `records/holdings.json` 加入 `.gitignore`，避免真实持仓误提交。

## 2026-07-01 组合风险和 ATR

- 新增 `stock_recognition_system/portfolio.py` 和 `portfolio` 命令，汇总真实持仓市值、持仓占比、计划止损亏损、组合风险警告。
- `RiskConfig` 新增新手组合约束：总持仓占比默认不超过 30%，组合计划止损风险默认不超过 2%。
- 腾讯/东方财富日线 provider 现在保留高价、低价、收盘价序列。
- 技术面新增 ATR14 计算；系统建议止损在有足够数据时纳入 ATR 动态止损候选。

## 2026-07-01 提醒和动量指标

- 新增 `stock_recognition_system/alerts.py` 和 `alert` 命令，统一检查模拟观察池与真实持仓，触发入场、止盈、止损或顺序待查时输出提醒。
- `alert` 只读检查，不改写模拟状态；结算模拟仍使用 `simulate-refresh`。
- 技术面新增 RSI14 和 MACD。RSI/MACD 只作为辅助提醒或降级因子，不单独把群消息升级为真实买入。
- RSI 边界已处理：横盘无涨跌时返回 50，避免把横盘误判成超买。

## 2026-07-01 盘后模拟数据库

- `simulate-refresh` 新增 `--save-summary`，刷新模拟观察池后会追加写入 `records/simulation_summaries.jsonl`。
- 同步更新 `records/latest-simulation-summary.json`，供其他 AI、表格或未来 UI 直接读取最近一次盘后汇总。
- 盘后自动化应在工作日 15:30 后运行：`simulate-refresh --save-summary`、`alert`、`simulate-summary --all`。

## 2026-07-01 完整交易系统规格纳入

- 已导入 `AGENTS.md`、`docs/trading-system-spec.md`、`config/config.yaml`。
- 已新增 `docs/requirements.md`、`docs/architecture.md`、`docs/tasks.md`、`docs/TRADING_SYSTEM_ADOPTION.md`。
- 当前项目定位明确为完整交易系统的第一阶段：群消息识别、数据核验、风控建议、复盘闭环。
- 不立即引入完整回测/策略注册器，避免对新手风控工具过度工程化。
- 下一阶段优先级：配置加载、数据质量对象、行业集中度、样本增强。
