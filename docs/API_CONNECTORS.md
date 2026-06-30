# API Connectors

第一阶段只接数据，不接券商交易。

## 推荐顺序

1. 手动输入当前价：最安全，适合测试流程。
2. AkShare：行情、K 线、资金流、龙虎榜、财务数据。
3. Tushare Pro：规范化历史行情、财务、公告，需要 token。
4. 巨潮资讯/交易所公告：用于验证公告、财报和调研。

## 数据层输出

所有数据源最终都转换成 `MarketEvidence`：

```python
MarketEvidence(
    current_price=21.90,
    change_pct=3.2,
    is_limit_up=False,
    close_prices=[20.1, 20.6, 21.0, 21.5, 21.9],
    verified_claims={"毛利率上升": True},
    data_warnings=["manual data"]
)
```

## 当前适配器

- `ManualDataProvider`：手动输入当前价、涨跌幅、涨停状态，默认推荐。
- `AkShareDataProvider`：可选，安装 AkShare 后读取 A 股实时行情。
- `TushareDataProvider`：可选，安装 Tushare 并配置 token 后读取日线数据。
- `MergedDataProvider`：按顺序尝试多个数据源，失败时保留警告。

示例：

```python
from stock_recognition_system.data_sources import ManualDataProvider

provider = ManualDataProvider(current_price=21.90, change_pct=3.2, is_limit_up=False)
evidence = provider.get_evidence("300497")
```

## 边界

- 不自动下单。
- 不把新闻或群消息当 A 级证据。
- 数据缺失时降级，不用模型记忆补事实。
- API 失败时记录 `data_warnings`，不把失败静默吞掉。
- 近期收盘价可先手动填入 `close_prices`，后续由行情接口自动补全。

## 东方财富日线接口

当前已接入 `EastMoneyDailyDataProvider`，用于拉取最近日线 K 线并转换为 `MarketEvidence`。它提供：

- 最新日线收盘价：作为缺少手动价时的 `current_price`。
- 最新涨跌幅：用于涨停/追高风险检查。
- 换手率：用于短线热度和风险提示。
- 最近 N 个收盘价：用于 5 日/20 日均线、振幅和破位检查。

命令行使用：

```powershell
python -m stock_recognition_system.cli review `
  --message-file examples/group_message.txt `
  --auto-market-data `
  --history-days 20
```

边界：东方财富公共接口只做行情辅助和风控核验，不用于自动交易；消息发出时的分钟价格仍应优先用券商截图、分时接口或手动记录复盘。

## 腾讯行情备用接口

当前 CLI 的自动行情采用双源策略：

1. 优先调用 `EastMoneyDailyDataProvider`。
2. 东方财富失败、断连或无日线数据时，自动切换 `TencentDailyDataProvider`。

腾讯行情 provider 从 `web.ifzq.gtimg.cn` 拉取前复权日线，转换为同一个 `MarketEvidence`。它提供最近 N 个收盘价、最新日线收盘价、涨跌幅、换手率。数据源只用于风控核验，不用于自动下单。
