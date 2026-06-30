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
