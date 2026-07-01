# 股票交易决策系统 — 领域规格文档

> 本文档是 AGENTS.md 第 4 节"领域约束"的展开。Codex 在实现任何交易相关模块时，必须同时参考本文档中对应章节的具体规格。

---

## 1. 数据层规格

### 1.1 必需数据字段

#### 行情数据（OHLCV）

每个交易日的标准 K 线记录必须包含以下字段：

| 字段 | 类型 | 说明 | 校验规则 |
|------|------|------|---------|
| `date` | datetime | 交易日期 | 必须是交易日（非周末/非节假日）；带 Asia/Shanghai 时区 |
| `open` | float | 开盘价 | > 0；|open - prev_close| / prev_close < 0.2（涨停跌停不超过 20%） |
| `high` | float | 最高价 | >= max(open, close)；> 0 |
| `low` | float | 最低价 | <= min(open, close)；> 0 |
| `close` | float | 收盘价 | > 0 |
| `volume` | float | 成交量（股） | >= 0（停牌日可能为 0） |
| `amount` | float | 成交额（元） | >= 0 |
| `turnover` | float | 换手率（%） | >= 0；通常 < 50%，超过 30% 标记异常 |
| `pct_change` | float | 涨跌幅（%） | |pct_change| <= 20（主板）/ 30（创业板科创板） |

#### 复权数据

| 字段 | 说明 |
|------|------|
| `adj_factor` | 复权因子，由数据源提供 |
| `open_adj` | 前复权开盘价 = open * adj_factor / latest_adj_factor |
| `high_adj` | 前复权最高价 |
| `low_adj` | 前复权最低价 |
| `close_adj` | 前复权收盘价 |

复权策略默认使用前复权（qfq），原因：前复权后价格连续，适合技术分析；后复权适合计算长期收益率。回测和实盘必须使用同一种复权方式，在 config.yaml 中统一配置。

#### 基本面数据（按需获取）

| 字段 | 频率 | 说明 |
|------|------|------|
| `pe_ttm` | 每日更新 | 滚动市盈率 = 总市值 / 归母净利润TTM |
| `pb` | 每日更新 | 市净率 = 总市值 / 归母净资产 |
| `total_mv` | 每日更新 | 总市值（元） |
| `circ_mv` | 每日更新 | 流通市值（元） |
| `roe_ttm` | 季度更新 | 滚动净资产收益率 |
| `net_profit_yoy` | 季度更新 | 归母净利润同比增长率 |

### 1.2 数据源对比

| 数据源 | 覆盖范围 | 复权数据 | 基本面 | 限流 | 推荐用途 |
|--------|---------|---------|--------|------|---------|
| akshare | A股全市场 | 有（qfq/hfq） | 有 | 无明确限制 | 主数据源（免费） |
| tushare | A股全市场 | 有 | 有 | 需积分（2000+） | 备用数据源/基本面 |
| yfinance | 全球 | 有 | 部分 | 有请求频率限制 | 美股/港股 |
| baostock | A股 | 有 | 无 | 无 | 历史数据备份 |

### 1.3 数据质量校验规则

Codex 在实现数据获取模块时，必须对每条数据执行以下校验。校验失败的数据行应标记为 invalid 并记录日志，而非静默丢弃或用默认值填充。

**完整性校验**：
- 日期字段非空且为有效日期
- OHLCV 核心字段非空、非 NaN
- 字段类型正确（数值型而非字符串）

**逻辑一致性校验**：
- high >= max(open, close) >= min(open, close) >= low
- volume >= 0
- amount >= 0
- 当 volume > 0 时，amount > 0（有成交量必有成交额）

**连续性校验**：
- 日期序列应为连续交易日。遇到缺口（停牌）时标记为 `halted`，不插值不前填
- 复权因子应单调递增（除权除息日因子跳变属正常）

**异常值检测**：
- 涨跌幅超过 ±20%（主板）或 ±30%（创业板/科创板）标记为可疑
- 换手率超过 30% 标记为异常高换手
- 价格为 0 或负数标记为数据错误

### 1.4 缓存设计

```
cache/
├── daily/                      # 日线数据缓存
│   ├── 000001/                  # 股票代码
│   │   ├── 2024.csv            # 按年分文件
│   │   └── 2025.csv
│   └── 600519/
├── fundamental/                 # 基本面数据缓存
│   └── 000001.json
└── calendar/                    # 交易日历缓存
    └── 2025.json                # 记录交易日列表
```

缓存策略：每次获取数据时检查本地缓存，缓存有效期默认 1 天（盘中数据每日更新一次）。如果请求的日期范围在缓存内，直接读缓存；如果超出缓存范围，增量获取并追加。缓存文件头部记录数据获取时间和数据源版本。

---

## 2. 技术指标库规格

每个指标实现为一个独立函数，输入是 OHLCV DataFrame，输出是包含指标值的 Series 或 DataFrame。所有指标注册到 `IndicatorRegistry` 中，通过名称调用，方便配置化使用。

### 2.1 趋势类指标

#### 移动平均线（MA）

```
公式：MA(n) = close.rolling(n).mean()
参数：n = 周期，常用值 [5, 10, 20, 60, 120, 250]
信号：
  - 金叉：短期MA上穿长期MA（如MA5上穿MA20）→ 买入信号
  - 死叉：短期MA下穿长期MA → 卖出信号
  - 多头排列：MA5 > MA10 > MA20 > MA60 → 强趋势
注意：MA具有滞后性，周期越长滞后越大。250日MA（年线）常被视为牛熊分界线。
```

#### 指数移动平均线（EMA）

```
公式：EMA(n) = close.ewm(span=n, adjust=False).mean()
参数：n = 周期，常用值 [12, 20, 26, 50, 200]
特点：比MA赋予近期数据更大权重，反应更快但噪声也更多。
```

#### MACD（异同移动平均线）

```
公式：
  DIF = EMA(12) - EMA(26)
  DEA = EMA(DIF, 9)
  MACD柱 = (DIF - DEA) * 2
参数：fast=12, slow=26, signal=9（默认值，可配置）
信号：
  - DIF上穿DEA → 金叉，买入
  - DIF下穿DEA → 死叉，卖出
  - MACD柱由负转正 → 动量转强
  - 顶背离：价格创新高但MACD未创新高 → 卖出预警
  - 底背离：价格创新低但MACD未创新低 → 买入预警
注意：背离信号可能提前出现，需配合趋势确认。MACD在震荡市中信号频繁且错误率高。
```

#### ADX（平均趋向指数）

```
公式：
  +DI = EMA(+DM, n) / ATR(n) * 100
  -DI = EMA(-DM, n) / ATR(n) * 100
  DX = |+DI - -DI| / (+DI + -DI) * 100
  ADX = EMA(DX, n)
参数：n = 14（默认）
用途：判断趋势强度，不指示方向。
  - ADX > 25 → 趋势明显（适合趋势策略）
  - ADX < 20 → 震荡市（趋势策略不适用，考虑均值回归策略）
注意：ADX 是滞后指标，ADX 上升只说明趋势在加强，不预测方向。
```

### 2.2 动量类指标

#### RSI（相对强弱指数）

```
公式：
  delta = close.diff()
  gain = delta.where(delta > 0, 0)
  loss = -delta.where(delta < 0, 0)
  rs = EMA(gain, n) / EMA(loss, n)    # Wilder smoothing
  RSI = 100 - 100 / (1 + rs)
参数：n = 6 / 12 / 14（常用），默认 14
信号：
  - RSI > 70 → 超买（可能回调）
  - RSI < 30 → 超卖（可能反弹）
  - RSI在50以上 → 多头占优
注意：超买超卖不等于反转信号，强势股可能长期处于超买区。需配合趋势判断。
```

#### KDJ（随机指标）

```
公式：
  RSV = (close - lowest(n)) / (highest(n) - lowest(n)) * 100
  K = SMA(RSV, m1)          # m1=3
  D = SMA(K, m2)            # m2=3
  J = 3*K - 2*D
参数：n=9, m1=3, m2=3（默认）
信号：
  - K上穿D且J<50 → 金叉，买入
  - K下穿D且J>50 → 死叉，卖出
  - J > 100 → 极度超买
  - J < 0 → 极度超卖
注意：KDJ在趋势行情中容易钝化（反复金叉死叉），震荡市效果更好。
```

#### CCI（商品通道指数）

```
公式：
  TP = (high + low + close) / 3
  MA_TP = TP.rolling(n).mean()
  MD = TP.rolling(n).apply(lambda x: abs(x - x.mean()).mean())
  CCI = (TP - MA_TP) / (0.015 * MD)
参数：n = 20（默认）
信号：
  - CCI > +100 → 超买
  - CCI < -100 → 超卖
  - CCI上穿 +100 → 突破买入
  - CCI下穿 -100 → 突破卖出
```

### 2.3 波动率类指标

#### 布林带（Bollinger Bands）

```
公式：
  中轨 = MA(close, n)
  上轨 = 中轨 + k * std(close, n)
  下轨 = 中轨 - k * std(close, n)
  %B = (close - 下轨) / (上轨 - 下轨)
  带宽 = (上轨 - 下轨) / 中轨
参数：n=20, k=2（默认）
信号：
  - 收盘价触及下轨 → 超卖（可能反弹）
  - 收盘价触及上轨 → 超买（可能回调）
  - 带宽收窄至历史低位 → 变盘在即（波动率扩张预警）
  - %B < 0 → 价格跌破下轨，强超卖
注意：带宽收窄后方向不确定，需配合成交量和其他指标判断方向。
```

#### ATR（真实波幅）

```
公式：
  TR = max(high - low, abs(high - prev_close), abs(low - prev_close))
  ATR = EMA(TR, n)    # Wilder smoothing
参数：n = 14（默认）
用途：
  - 止损设置：止损价 = 入场价 - k * ATR（常用 k=2 或 3）
  - 仓位计算：根据ATR决定每笔交易的金额大小（波动大→仓位小）
  - 趋势过滤：ATR上升表示波动加剧
注意：ATR是绝对值，不同价位的股票ATR不可直接比较。用 ATR/close 做归一化。
```

### 2.4 成交量类指标

#### OBV（能量潮）

```
公式：
  若 close > prev_close：OBV += volume
  若 close < prev_close：OBV -= volume
  若 close == prev_close：OBV 不变
信号：
  - 价格上涨但OBV下降 → 顶背离，量价不配合，卖出预警
  - 价格下跌但OBV上升 → 底背离，有资金承接，买入预警
```

#### 成交量比率（VR）

```
公式：
  AV = n日内上涨日成交量之和
  BV = n日内下跌日成交量之和
  VR = AV / BV * 100
参数：n = 26（默认）
信号：
  - VR > 150 → 偏强（但 200 以上注意过热）
  - VR < 70 → 偏弱
  - VR 在 80-150 之间 → 正常
```

#### 量比

```
公式：量比 = 当日成交量 / 过去5日平均成交量
信号：
  - 量比 > 2.0 → 显著放量
  - 量比 1.5-2.0 → 温和放量
  - 量比 0.5-1.0 → 缩量
  - 量比 < 0.5 → 极度缩量
注意：放量本身不构成买卖信号，需结合价格方向判断。放量上涨和放量下跌含义完全不同。
```

### 2.5 指标实现规范

每个指标函数必须遵循以下接口契约：

```python
from typing import Protocol
import pandas as pd

class IndicatorFunc(Protocol):
    def __call__(self, df: pd.DataFrame, **params: float | int) -> pd.Series | pd.DataFrame:
        """
        计算技术指标

        Parameters
        ----------
        df : pd.DataFrame
            OHLCV 数据，必须包含 date, open, high, low, close, volume 列
        **params : dict
            指标参数，如 n=14, fast=12 等

        Returns
        -------
        pd.Series | pd.DataFrame
            单值指标返回 Series，多值指标（如布林带）返回 DataFrame
            返回值的 index 与输入 df 对齐
            前 n-1 个值为 NaN（预热期），不可用

        Raises
        ------
        ValueError
            输入数据不足（行数 < 最大参数周期）或缺少必需列
        """
        ...
```

所有指标注册到 `IndicatorRegistry`，通过名称字符串调用：

```python
# 注册
registry = IndicatorRegistry()
registry.register("macd", macd_indicator, default_params={"fast": 12, "slow": 26, "signal": 9})
registry.register("rsi", rsi_indicator, default_params={"n": 14})

# 调用（配置驱动）
result = registry.calculate("macd", df, fast=12, slow=26, signal=9)
```

---

## 3. 信号生成规则

### 3.1 信号数据结构

每个信号是一个标准化对象，包含完整的可追溯信息：

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class SignalType(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"

class SignalStrength(Enum):
    STRONG = 3
    MEDIUM = 2
    WEAK = 1

@dataclass
class Signal:
    stock_code: str                    # 股票代码
    date: datetime                     # 信号日期
    signal_type: SignalType            # 信号类型
    indicator_name: str                # 触发指标名称
    strength: SignalStrength           # 信号强度
    reason: str                        # 人类可读的触发原因
    indicator_value: float             # 指标当前值
    reference_value: float | None      # 参考值（如均线值、阈值）
    metadata: dict                     # 额外信息（如参数快照）
```

### 3.2 信号生成器接口

每个指标可以生成多个信号生成器。例如 MACD 可以生成金叉信号、死叉信号、背离信号：

```python
class SignalGenerator(Protocol):
    def generate(self, df: pd.DataFrame, indicator_result: pd.Series | pd.DataFrame,
                 **params) -> list[Signal]:
        """
        从指标计算结果生成交易信号

        只生成当日新出现的信号（如"今日金叉"），不生成历史信号。
        金叉定义：昨天 DIF < DEA，今天 DIF >= DEA。
        """
        ...
```

### 3.3 信号强度评级

| 级别 | 定义 | 典型场景 |
|------|------|---------|
| STRONG (3) | 多重条件共振 | 金叉 + 放量 + 趋势向上 |
| MEDIUM (2) | 单一明确信号 | 金叉，无其他配合 |
| WEAK (1) | 边缘信号 | 接近金叉但尚未确认 |

### 3.4 信号去重与冷却

- **信号去重**：同一指标在同一交易日只生成一个信号（取最强）
- **信号冷却**：同一信号类型在 N 个交易日内不重复触发（默认 N=5），避免频繁信号
- **信号有效期**：信号生成后 M 个交易日内有效（默认 M=3），过期信号不再参与决策

---

## 4. 决策引擎设计

### 4.1 决策流程

决策引擎接收当日所有信号，按以下流程产出最终决策：

```
所有信号 → 过滤（冷却/有效期）→ 分组（买入组/卖出组）→ 冲突检测
→ 多信号融合打分 → 风控检查 → 输出决策
```

### 4.2 多信号融合方法

提供三种融合方式，通过配置选择：

**加权投票法**（默认）：
```
score = Σ(signal_strength_i * weight_i) / Σ(weight_i)
score > buy_threshold → 买入
score < sell_threshold → 卖出
否则 → 持有
```

| 指标类别 | 默认权重 | 说明 |
|---------|---------|------|
| 趋势类（MA/MACD/ADX） | 0.30 | 趋势是主要驱动力 |
| 动量类（RSI/KDJ/CCI） | 0.25 | 动量确认趋势 |
| 波动率类（布林带） | 0.15 | 辅助参考 |
| 成交量类（OBV/VR/量比） | 0.20 | 量价配合验证 |
| 基本面类（PE/PB） | 0.10 | 长期安全边际 |

**条件组合法**：
```
买入条件 = (MACD金叉) AND (RSI < 70) AND (成交量放大)
卖出条件 = (MACD死叉) OR (RSI > 80) OR (止损触发)
条件可配置为 JSON/YAML 规则
```

**打分排序法**：
```
对股票池中所有股票计算综合得分，取 Top N 作为买入候选。
得分 = 趋势分 * 0.4 + 动量分 * 0.3 + 量价分 * 0.3
```

### 4.3 冲突处理规则

当同一股票同时出现买入和卖出信号时，按以下优先级处理：

1. 止损信号 > 所有其他信号（止损永远优先）
2. 风控否决信号 > 策略信号
3. 强信号 > 弱信号
4. 趋势类信号 > 动量类信号（趋势为王）
5. 若强度相同，默认持有不动（避免频繁交易）

### 4.4 决策输出结构

```python
@dataclass
class Decision:
    stock_code: str
    date: datetime
    action: str                      # "buy" | "sell" | "hold"
    position_pct: float              # 建议仓位比例 (0-1)
    entry_price: float | None        # 建议入场价
    stop_loss_price: float | None    # 止损价
    take_profit_price: float | None  # 止盈价
    confidence: float               # 决策信心度 (0-1)
    triggered_signals: list[Signal] # 触发的信号列表
    risk_check_result: dict          # 风控检查结果
    reasoning: str                   # 决策推理过程（人类可读）
```

### 4.5 决策可解释性要求

每条决策的 `reasoning` 字段必须包含：
- 触发了哪些信号（如"MACD金叉 + RSI超卖反弹 + 成交量放量1.8倍"）
- 综合得分和各分项得分
- 风控检查是否通过，不通过原因
- 参考的技术指标数值

---

## 5. 风控体系规格

### 5.1 风控层级

风控分为三层，由内到外依次执行：

**第一层：个股风控**
- 止损止盈检查
- 单股仓位上限
- 股票黑名单过滤

**第二层：组合风控**
- 总仓位上限
- 行业集中度限制
- 相关性限制（避免持有高度相关的股票组合）

**第三层：系统性风控**
- 大盘状态判断（熊市减仓/空仓）
- 回撤控制（组合回撤超过阈值时减仓）
- 黑天鹅熔断（单日跌幅超过阈值时暂停交易）

### 5.2 止损止盈规则

提供多种止损方式，通过配置选择：

**固定百分比止损**（默认，适合新手）：
```
止损价 = 买入价 * (1 - stop_loss_pct)    # 默认 5%
止盈价 = 买入价 * (1 + take_profit_pct)  # 默认 15%
```

**ATR 动态止损**（趋势跟踪推荐）：
```
止损价 = 买入价 - k * ATR(n)    # k=2, n=14
止盈价 = 买入价 + 2 * k * ATR(n)  # 盈亏比 2:1
```

**移动止损（Trailing Stop）**：
```
止损价 = max(历史最高价 - k * ATR(n), 买入价 - initial_stop)
随着价格上涨，止损价跟随上移，不会回退
```

**均线止损**：
```
止损条件：收盘价跌破 MA(n)（常用 n=20）
适用于趋势跟踪策略
```

### 5.3 仓位管理方法

**固定比例法**（默认）：
```
每笔仓位 = 总资金 * single_position_pct  # 默认 10%
总仓位上限 = 总资金 * max_total_position   # 默认 70%
```

**凯利公式简化版**：
```
f = win_rate * avg_win / avg_loss - (1 - win_rate)
仓位 = min(f * kelly_fraction, max_single_position)
# kelly_fraction 通常取 0.25-0.5（ quarter/half Kelly）
注意：需要足够的回测数据来估计胜率和盈亏比
```

**波动率倒数加权**：
```
仓位 ∝ 1 / ATR
波动大的股票分配更小仓位，使各股票贡献的波动大致相等
```

### 5.4 风控参数建议（新手配置）

```yaml
risk:
  # 个股风控
  single_position_max: 0.15          # 单股最多15%
  stop_loss_method: "fixed_pct"       # 止损方式
  stop_loss_pct: 0.05                # 止损5%
  take_profit_pct: 0.15               # 止盈15%
  
  # 组合风控
  max_total_position: 0.60            # 总仓位上限60%
  max_industry_exposure: 0.30         # 单行业上限30%
  max_correlation: 0.7                # 持仓间最大相关系数
  
  # 系统性风控
  market_regime_filter: true          # 启用大盘状态过滤
  bear_market_max_position: 0.20      # 熊市仓位上限20%
  max_drawdown_threshold: 0.15        # 最大回撤阈值15%
  drawdown_reduce_ratio: 0.50         # 回撤超阈值时减仓比例
  
  # 熔断
  daily_loss_circuit_breaker: 0.05    # 单日亏损5%暂停交易
  consecutive_loss_limit: 3          # 连续亏损3次暂停
```

### 5.5 股票池筛选

系统支持动态股票池筛选，每日运行一次：

| 过滤条件 | 阈值 | 说明 |
|---------|------|------|
| ST/\*ST | 排除 | 风险警示股 |
| 上市天数 | < 60天排除 | 次新股波动大 |
| 日均成交额 | < 5000万排除 | 流动性不足 |
| 日均换手率 | < 0.3%排除 | 流动性极差 |
| 涨跌停 | 当日排除 | 无法交易 |
| 退市风险 | 排除 | 财务退市风险标识 |

---

## 6. 市场状态识别

### 6.1 大盘状态分类

系统需要判断当前市场处于什么状态，并在不同状态下使用不同策略：

| 状态 | 定义 | 策略倾向 | 仓位建议 |
|------|------|---------|---------|
| 强牛市 | MA60 以上且 MA60 上行 | 趋势跟随，持股为主 | 60-80% |
| 弱牛市 | MA60 以上但 MA60 平或下行 | 谨慎做多 | 40-60% |
| 震荡市 | MA60 附近反复 | 区间操作，低买高卖 | 20-40% |
| 弱熊市 | MA60 以下但跌幅收窄 | 轻仓反弹，快进快出 | 10-20% |
| 强熊市 | MA60 以下且持续下跌 | 空仓或仅持有抗跌品种 | 0-10% |

### 6.2 判断指标

| 指标 | 计算 | 判断规则 |
|------|------|---------|
| 指数均线 | 上证指数 MA60 | 在上方=多头，在下方=空头 |
| 均线斜率 | MA60 的5日变化率 | >0 上升趋势，<0 下降趋势 |
| 市场广度 | 站上MA20的股票占比 | >60%偏多，<40%偏空 |
| 涨跌家数比 | 每日上涨/下跌家数 | 连续>2偏多，<0.5偏空 |
| 成交量趋势 | 5日均量/20日均量 | >1.2放量，<0.8缩量 |

### 6.3 市场状态切换规则

状态切换不能仅凭一天的数据，需要连续 N 天确认（默认 N=3），避免频繁切换：

```
当前状态 = "弱牛市"
连续3天满足"强牛市"条件 → 切换为"强牛市"
连续3天满足"震荡市"条件 → 切换为"震荡市"
不足3天 → 维持当前状态
```

### 6.4 状态影响策略选择

```python
# 伪代码：不同市场状态下的策略权重调整
if market_state == "strong_bull":
    strategy_weights = {"trend_following": 0.7, "mean_reversion": 0.1, "breakout": 0.2}
elif market_state == "range_bound":
    strategy_weights = {"trend_following": 0.2, "mean_reversion": 0.6, "breakout": 0.2}
elif market_state == "strong_bear":
    strategy_weights = {"trend_following": 0.1, "mean_reversion": 0.2, "breakout": 0.1}
    # 强熊市主要策略是空仓
```

---

## 7. 多时间框架分析

### 7.1 三级时间框架

系统在生成决策时，同时检查三个时间级别的趋势，避免"逆大势做小势"：

| 级别 | 周期 | 用途 | 权重 |
|------|------|------|------|
| 大趋势 | 周线/月线 | 判断主趋势方向 | 50% |
| 中趋势 | 日线 | 日常信号生成 | 35% |
| 小趋势 | 60分钟线 | 精确入场时机 | 15% |

### 7.2 三屏交易法

参考 Alexander Elder 的三屏交易系统：

```
第一屏（周线）：判断大趋势
  - 周线MACD柱状图上升 → 只做多
  - 周线MACD柱状图下降 → 只做空（或空仓）

第二屏（日线）：寻找回调位置
  - 大趋势向上时，等待日线回调（RSI回落、触及均线）
  - 大趋势向下时，等待日线反弹

第三屏（小时线）：精确入场
  - 回调到位后，小时线出现反转信号时入场
```

### 7.3 多时间框架信号对齐

只有当三个时间框架的趋势方向一致时，信号强度才升级为 STRONG。方向不一致时降级为 WEAK 或不发信号：

```
周线上行 + 日线金叉 + 小时线突破 → STRONG 买入
周线上行 + 日线金叉 + 小时线下行 → MEDIUM 买入
周线下行 + 日线金叉 → WEAK 买入（逆势，风险高）
```

---

## 8. 回测方法论

### 8.1 回测流程

```
1. 准备历史数据（前复权，已校验）
2. 初始化组合（初始资金、手续费率、滑点）
3. 按日期遍历：
   a. 更新市场状态
   b. 获取当日信号
   c. 决策引擎生成决策
   d. 模拟成交（按次日开盘价成交，更真实）
   e. 更新持仓和净值
   f. 风控检查（止损止盈、仓位调整）
4. 计算绩效指标
5. 生成回测报告
```

### 8.2 成交价格模拟

回测中的成交价不能使用信号当日的收盘价（那是未来数据），应使用信号日次日的开盘价（或指定滑点）：

```
信号日 T 日收盘后生成信号
成交日 T+1 日开盘价成交
成交价 = T+1 开盘价 * (1 + slippage)  # 买入加滑点
成交价 = T+1 开盘价 * (1 - slippage)  # 卖出减滑点
```

### 8.3 交易成本参数

```yaml
backtest:
  commission_rate: 0.00025       # 佣金费率（万分之2.5）
  commission_min: 5.0             # 最低佣金5元
  stamp_tax: 0.0005               # 印花税万分之5（卖出收取）
  transfer_fee: 0.00002           # 过户费万分之0.2（沪市）
  slippage: 0.001                 # 滑点0.1%
```

### 8.4 未来函数检测

未来函数是回测中最隐蔽的陷阱。系统必须自动检测以下情况：

| 检测项 | 方法 |
|--------|------|
| 使用未来收盘价 | 信号计算只用 [0:t] 数据，不允许访问 [t+1:] |
| 指标参数预热 | 指标值前 n-1 个必须为 NaN，不可用 0 填充 |
| 财报数据使用时点 | Q1财报在4月30日前不可用（公布前不知数据） |
| 幸存者偏差 | 股票池必须包含已退市股票 |
| 前视偏差 | 不允许使用"全期最优参数" |

检测方法：在回测的每个时间步 t，检查所有计算是否只使用了 `df.iloc[:t+1]` 的数据。任何访问 `df.iloc[t+1:]` 的操作都是未来函数。

### 8.5 样本内外分离

参数优化必须使用样本内外分离，防止过拟合：

```
数据划分：
  样本内（训练集）2018-2021 → 用于参数优化
  样本外（测试集）2022-2023 → 验证优化后的参数

验证标准：
  样本外收益率 / 样本内收益率 > 0.5 → 参数较稳健
  样本外最大回撤 / 样本内最大回撤 < 2.0 → 风控稳健
  否则 → 参数可能过拟合，需要简化
```

### 8.6 Walk-Forward 分析

对于更严格的验证，使用滚动窗口分析：

```
窗口1：训练2018-2019 → 测试2020
窗口2：训练2019-2020 → 测试2021
窗口3：训练2020-2021 → 测试2022
窗口4：训练2021-2022 → 测试2023

最终评估4个测试窗口的综合表现。
如果4个窗口都盈利 → 策略较稳健
如果某些窗口大幅亏损 → 策略对市场状态敏感，需标注适用场景
```

### 8.7 绩效指标计算公式

| 指标 | 公式 | 合格标准 |
|------|------|---------|
| 年化收益率 | (最终净值 / 初始资金) ^ (252 / 交易天数) - 1 | > 15% |
| 最大回撤 | max(1 - 净值 / 前期最高净值) | < 20% |
| 夏普比率 | (年化收益 - 无风险利率) / 年化波动率 | > 1.0 |
| 索提诺比率 | (年化收益 - 无风险利率) / 年化下行波动率 | > 1.5 |
| 胜率 | 盈利交易数 / 总交易数 | > 40% |
| 盈亏比 | 平均盈利 / 平均亏损 | > 1.5 |
| 卡尔玛比率 | 年化收益率 / 最大回撤 | > 1.0 |
| 收益回撤比 | 年化收益率 / 最大回撤 | > 0.75 |

无风险利率默认取 2.5%（参考十年期国债收益率），可在配置中修改。

---

## 9. 决策策略库

### 9.1 策略注册器设计

所有策略实现统一接口，注册到 `StrategyRegistry`，通过配置切换：

```python
class Strategy(Protocol):
    name: str                          # 策略名称
    required_indicators: list[str]      # 依赖的指标列表
    
    def generate_signals(self, df: pd.DataFrame, 
                         market_state: str,
                         **params) -> list[Signal]:
        """
        生成交易信号
        
        Parameters
        ----------
        df : OHLCV 数据
        market_state : 当前市场状态
        **params : 策略参数
        
        Returns
        -------
        list[Signal]
        """
        ...
```

### 9.2 内置策略清单

#### P0 — 核心策略

**趋势跟踪策略（Trend Following）**
```
适用市场：强牛市、弱牛市
核心逻辑：MA 多头排列 + MACD 金叉
买入条件：
  1. MA5 > MA20（短期趋势向上）
  2. MACD 金叉（DIF 上穿 DEA）
  3. 成交量 > 5日均量
卖出条件：
  1. MA5 下穿 MA20，或
  2. MACD 死叉，或
  3. 止损/止盈触发
参数：ma_short=5, ma_long=20, macd=(12,26,9)
```

**均线交叉策略（MA Crossover）**
```
适用市场：有趋势的市场（非强震荡）
核心逻辑：短期均线上穿/下穿长期均线
买入条件：MA(short) 上穿 MA(long)
卖出条件：MA(short) 下穿 MA(long)
参数：short=5, long=20（保守）/ short=10, long=60（稳健）
注意：震荡市中频繁假突破，必须配合 ADX 过滤（ADX>25 才交易）
```

#### P1 — 增强策略

**均值回归策略（Mean Reversion）**
```
适用市场：震荡市
核心逻辑：价格偏离均线后回归
买入条件：
  1. 收盘价跌破布林带下轨
  2. RSI < 30（超卖）
  3. 次日成交量缩量（恐慌抛售结束）
卖出条件：
  1. 价格回归到布林带中轨，或
  2. RSI > 50，或
  3. 止损触发（价格继续跌破下轨一定幅度）
参数：bb_n=20, bb_k=2, rsi_n=14, rsi_threshold=30
注意：趋势市中均值回归策略会持续亏损，必须用 ADX < 20 过滤
```

**突破策略（Breakout）**
```
适用市场：震荡转趋势的转折点
核心逻辑：价格突破前期高点/低点
买入条件：
  1. 收盘价突破过去 N 日最高价
  2. 成交量放大（量比 > 1.5）
  3. 布林带带宽处于收缩状态（波动率压缩后突破更可信）
卖出条件：
  1. 跌破过去 N 日最低价，或
  2. 止损/止盈触发
参数：lookback=20, volume_ratio_threshold=1.5
```

**动量策略（Momentum）**
```
适用市场：牛市
核心逻辑：强者恒强，买入近期涨幅最大的股票
买入条件：
  1. 过去 20 日涨幅排名前 10%
  2. RSI 在 50-70 之间（有动量但未超买）
  3. 成交量持续放大
卖出条件：
  1. 排名跌出前 30%，或
  2. RSI > 80，或
  3. 止损触发
参数：lookback=20, top_pct=0.1
```

#### P2 — 可选策略

**多因子策略（Multi-Factor）**
```
因子：
  - 技术因子：动量、波动率、换手率
  - 基本面因子：PE、PB、ROE
  - 规模因子：流通市值
打分：各因子打分后加权求和，买入综合得分最高的N只股票
```

### 9.3 策略适用性矩阵

| 策略 \ 市场状态 | 强牛市 | 弱牛市 | 震荡市 | 弱熊市 | 强熊市 |
|-----------------|--------|--------|--------|--------|--------|
| 趋势跟踪 | 适用 | 适用 | 不适用 | 不适用 | 不适用 |
| 均线交叉 | 适用 | 勉强 | 不适用 | 不适用 | 不适用 |
| 均值回归 | 不适用 | 勉强 | 适用 | 勉强 | 不适用 |
| 突破 | 适用 | 适用 | 适用 | 不适用 | 不适用 |
| 动量 | 适用 | 适用 | 不适用 | 不适用 | 不适用 |

---

## 10. 报告模板规格

### 10.1 日报模板

每日盘后生成的决策报告，输出为 HTML 格式：

```
═══════════════════════════════════════════════
  股票决策日报 — {date}
  策略版本：{version}  市场状态：{market_state}
═══════════════════════════════════════════════

【一、市场概况】
  上证指数：{price}  涨跌幅：{pct_change}%
  市场广度：{breadth}% 股票站上MA20
  市场状态：{state} → 建议仓位：{suggested_position}%

【二、持仓检查】
  持仓股票    成本价    现价    盈亏%    止损价    距止损    操作建议
  {code}     {cost}   {now}   {pnl}   {stop}   {dist}   {action}
  ...

【三、今日信号】
  股票代码    信号类型    指标      原因                    强度
  {code}     买入       MACD金叉  DIF上穿DEA，成交量放大    STRONG
  ...

【四、买入候选】
  排名  股票代码   综合得分   趋势分   动量分   量价分   建议仓位
  1    {code}    {score}   {t}     {m}     {v}     {pct}
  ...

【五、风控状态】
  总仓位：{current}% / {max}% （{status}）
  今日回撤：{drawdown}%
  风险提示：{warnings}

【六、决策日志】
  {timestamp} - 获取数据：{source}
  {timestamp} - 计算指标：{indicators}
  {timestamp} - 生成信号：{count} 个
  {timestamp} - 风控检查：{result}
  {timestamp} - 生成报告
```

### 10.2 回测报告模板

```
═══════════════════════════════════════════════
  回测报告
  策略：{strategy_name}
  回测区间：{start_date} ~ {end_date}（{days} 交易日）
  股票池：{pool_description}
═══════════════════════════════════════════════

【一、绩效概览】
  指标              数值       基准(沪深300)    评价
  年化收益率         {val}      {benchmark}      {grade}
  最大回撤           {val}      {benchmark}      {grade}
  夏普比率           {val}      {benchmark}      {grade}
  胜率              {val}      -               {grade}
  盈亏比            {val}      -               {grade}
  
  净值曲线图（plotly 交互图）

【二、交易统计】
  总交易次数：{count}
  盈利交易：{win_count}（{win_rate}%）
  亏损交易：{loss_count}（{loss_rate}%）
  平均持仓天数：{avg_days}
  最大连续盈利：{max_win_streak}
  最大连续亏损：{max_loss_streak}

【三、月度收益分布】
  月份      收益率     是否跑赢基准
  {month}  {return}  {outperform}
  ...

【四、回撤分析】
  最大回撤：{max_dd}%（{peak_date} → {trough_date}，恢复用时 {days} 天）
  回撤持续期分布图

【五、参数敏感性分析】
  参数组合          样本内收益    样本外收益    稳定性
  {param_set}      {in_sample}   {out_sample}  {stability}
  ...

【六、结论与建议】
  策略适用市场：{applicable_markets}
  主要风险：{risks}
  改进方向：{suggestions}
```

---

## 11. 配置系统规格

### 11.1 配置文件结构

所有可配置参数集中在 `config/config.yaml`，按模块组织。Codex 不应在代码中硬编码任何业务参数。

```yaml
# config.yaml 结构概览
data:
  source: "akshare"                 # 数据源
  adjust: "qfq"                     # 复权方式
  cache_dir: "cache/"
  cache_ttl_hours: 24               # 缓存有效期
  
indicators:
  ma:                               # 每个指标的参数
    periods: [5, 10, 20, 60, 120]
  macd:
    fast: 12
    slow: 26
    signal: 9
  rsi:
    n: 14
    overbought: 70
    oversold: 30
  boll:
    n: 20
    k: 2.0
  kdj:
    n: 9
    m1: 3
    m2: 3
  atr:
    n: 14

signals:
  cooldown_days: 5                  # 信号冷却期
  valid_days: 3                     # 信号有效期
  dedup: true                       # 同指标同日去重

strategy:
  active_strategies:                # 启用的策略列表
    - name: "trend_following"
      weight: 0.4
      params: {ma_short: 5, ma_long: 20}
    - name: "mean_reversion"
      weight: 0.3
      params: {bb_n: 20, bb_k: 2.0}
    - name: "breakout"
      weight: 0.3
      params: {lookback: 20}
  
  decision_method: "weighted_vote"  # 融合方式
  buy_threshold: 0.6               # 买入阈值
  sell_threshold: 0.4              # 卖出阈值

risk:
  # 见 5.4 节的详细配置

market_state:
  index_code: "000001.SH"           # 大盘指数（上证指数）
  ma_period: 60                     # 趋势均线周期
  confirm_days: 3                   # 状态切换确认天数
  breadth_ma: 20                    # 市场广度均线

multi_timeframe:
  weekly_weight: 0.50
  daily_weight: 0.35
  hourly_weight: 0.15
  enable: true

backtest:
  initial_capital: 1000000          # 初始资金
  commission_rate: 0.00025
  stamp_tax: 0.0005
  slippage: 0.001
  risk_free_rate: 0.025

report:
  output_dir: "reports/"
  formats: ["html", "csv"]
  language: "zh-CN"
```

### 11.2 配置校验

系统启动时必须校验配置文件的完整性和合法性：

- 必填项检查：缺少必填配置时报错并提示具体字段
- 类型检查：数值型参数不能是字符串
- 范围检查：概率类参数在 [0,1] 范围内；周期类参数为正整数
- 一致性检查：策略依赖的指标必须在 indicators 中有定义；策略的权重之和为 1.0
- 合理性警告：止损百分比 < 1% 或 > 20% 时给出警告

---

## 12. 数据流与接口定义

### 12.1 系统数据流

```
交易日历 → 数据获取层 → 数据校验 → 缓存
                                    ↓
                         指标计算层 → 信号生成层
                              ↑              ↓
                    市场状态识别 → 决策引擎 ← 多时间框架分析
                                        ↓
                                    风控层 → 最终决策
                                        ↓
                                    报告生成层
```

### 12.2 模块间接口

所有模块间通过 dataclass 或 TypedDict 传递数据，不使用裸 dict，确保类型安全：

```python
# 数据层输出
@dataclass
class StockData:
    code: str
    name: str
    ohlcv: pd.DataFrame          # 标准OHLCV数据
    fundamentals: dict | None    # 基本面数据（可选）
    data_quality: dict           # 数据质量报告

# 指标层输出
@dataclass  
class IndicatorResult:
    code: str
    date: datetime
    indicators: dict[str, float]  # {"macd_dif": 0.12, "rsi": 45.3, ...}
    raw_values: dict[str, pd.Series | pd.DataFrame]  # 原始指标序列

# 信号层输出（见 3.1 节的 Signal）
# 决策层输出（见 4.4 节的 Decision）

# 风控层输入输出
@dataclass
class RiskCheckResult:
    passed: bool
    checks: list[dict]            # [{"check": "stop_loss", "passed": true, "reason": ""}]
    adjusted_position: float | None  # 风控调整后的建议仓位
    warnings: list[str]

# 报告层
@dataclass
class ReportData:
    date: datetime
    market_state: str
    decisions: list[Decision]
    holdings: list[dict]
    risk_status: RiskCheckResult
    signals: list[Signal]
    backtest_summary: dict | None  # 回测模式下附加
```

### 12.3 主流程伪代码

```python
def run_daily(config: Config) -> ReportData:
    """每日运行主流程"""
    # 1. 获取数据
    calendar = get_trading_calendar(config.data)
    stocks = filter_stock_pool(config.risk)  # 股票池筛选
    stock_data = {code: fetch_data(code, config.data) for code in stocks}
    
    # 2. 市场状态
    index_data = fetch_data(config.market_state.index_code, config.data)
    market_state = detect_market_state(index_data, config.market_state)
    
    # 3. 指标计算 + 信号生成
    all_signals = []
    for code, data in stock_data.items():
        indicators = calculate_indicators(data, config.indicators)
        signals = generate_signals(data, indicators, market_state, config.signals)
        
        # 多时间框架分析
        if config.multi_timeframe.enable:
            weekly_signals = analyze_timeframe(code, "weekly", config)
            signals = align_timeframes(signals, weekly_signals)
        
        all_signals.extend(signals)
    
    # 4. 决策
    decisions = []
    for code in stocks:
        signals = [s for s in all_signals if s.stock_code == code]
        decision = decision_engine.decide(signals, market_state, config.strategy)
        
        # 5. 风控
        risk_result = risk_manager.check(decision, portfolio, config.risk)
        if risk_result.passed:
            decision = apply_risk_adjustment(decision, risk_result)
            decisions.append(decision)
    
    # 6. 报告
    report = build_report(decisions, market_state, portfolio, config.report)
    return report
```
