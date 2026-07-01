# Skill Expansion Plan

## 筛选原则

只接能提升风控、数据核验、复盘和工程质量的 skill 或开源库。任何直接荐股、自动交易、承诺收益、隐藏网络请求、保存凭据的代码都不接入。

接入前检查：

1. README、许可证、维护活跃度。
2. 数据来源和更新时间。
3. 是否包含自动交易或券商下单代码。
4. 是否要求 API key，是否安全保存。
5. 是否有隐藏网络请求。
6. 先用 `examples/` 样本和测试验证。

## 可利用方向

### Codex Skills

- 数据分析 skill：用于 CSV/Excel 样本分析、群源统计、复盘表整理。
- 文档/报告 skill：用于生成每周复盘报告和 HTML 报告。
- 浏览器控制 skill：用于核验公告页面、行情页面和投顾主体页面。
- skill-creator：当本项目规则稳定后，沉淀成 `stock-signal-risk-review` 专用 skill。

当前限制：OpenAI 官方 skills 列表接口本次请求返回 403 或服务中断，暂未自动安装新 skill。

### GitHub Skills

GitHub Skills 更适合提升工程协作能力，而不是直接提升股票判断。当前阶段可用它们保护规则质量，不把它们当选股知识库：

- GitHub Actions：自动运行测试和语法检查。
- CodeQL/安全扫描：后续接入 API key 和外部数据源前使用。
- Pull request review 工作流：规则变更必须经过测试样本验证。
- Markdown 文档技能：产品文档、复盘文档、用户说明保持一致。

本项目已先接入 GitHub Actions CI。

### 开源数据和分析库

- AkShare：A 股行情、历史 K 线、资金流、龙虎榜、财务数据。
- Tushare：规范化行情、财务、公告数据，需要 token；GitHub 上有官方数据 Skill，可在取得 token 后接入 Codex 工作流。
- OpenBB：金融数据研究平台，适合后续做跨市场数据研究。
- backtrader：策略回测框架，只用于历史复盘，不用于自动交易。
- pandas/NumPy：样本统计、群源质量评分、批量复盘。

参考入口：

- GitHub Skills: https://skills.github.com/
- GitHub Actions: https://docs.github.com/actions
- CodeQL: https://codeql.github.com/
- AkShare: https://github.com/akfamily/akshare
- Tushare data skill: https://github.com/waditu/tushare-data
- Tushare: https://tushare.pro/document/2
- OpenBB: https://github.com/OpenBB-finance/OpenBB
- backtrader: https://github.com/mementum/backtrader

## 推荐接入顺序

1. GitHub Actions：先保证每次改规则不破坏底线。
2. AkShare：读取当前价、分钟线、日线、量比、换手率。
3. 证据采集剧本：把群消息逻辑映射到公告、财报、龙虎榜、研报等核验路径。
4. 巨潮资讯/交易所公告：核验财报、调研、公告。
5. Tushare：补规范化历史行情和财务数据；token 到位后再考虑安装官方 data skill。
6. pandas/NumPy：统计 50 条以上复盘样本，验证群源质量和规则命中率。
7. OpenBB/backtrader/Qlib：只在样本足够后做研究、回测或量化实验。

## 当前阶段结论

34,000 元账户、4-5 日短线训练目标下，不建议优先引入重型量化框架。当前最有价值的是：

- 把每条群消息拆成可验证证据。
- 用消息时点价格还原是否已经追高。
- 记录 1日、3日、5日真实结果。
- 累计样本后再判断群源是否值得继续观察。

## 能力边界

- skill 只能增强数据采集、核验、报告和测试。
- 最终动作仍由本项目硬性规则拦截。
- 缺数据时降级。
- 数据源冲突时标记冲突，不自动采信。
