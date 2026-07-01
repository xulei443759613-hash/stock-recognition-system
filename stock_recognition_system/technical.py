from __future__ import annotations

from statistics import mean

from .models import MarketEvidence, ParsedSignal, TechnicalReview, TechnicalStatus


def calculate_ema(values: list[float], period: int) -> list[float]:
    prices = [value for value in values if value > 0]
    if not prices or period <= 0:
        return []
    alpha = 2 / (period + 1)
    ema_values = [prices[0]]
    for price in prices[1:]:
        ema_values.append(price * alpha + ema_values[-1] * (1 - alpha))
    return ema_values


def calculate_rsi(close_prices: list[float], period: int = 14) -> float | None:
    prices = [price for price in close_prices if price > 0]
    if len(prices) < period + 1:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for idx in range(len(prices) - period, len(prices)):
        change = prices[idx] - prices[idx - 1]
        gains.append(max(0.0, change))
        losses.append(max(0.0, -change))
    avg_gain = mean(gains)
    avg_loss = mean(losses)
    if avg_gain == 0 and avg_loss == 0:
        return 50.0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 2)


def calculate_macd(close_prices: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict[str, float] | None:
    prices = [price for price in close_prices if price > 0]
    if len(prices) < slow + signal:
        return None
    fast_ema = calculate_ema(prices, fast)
    slow_ema = calculate_ema(prices, slow)
    length = min(len(fast_ema), len(slow_ema))
    dif_values = [fast_ema[-length + idx] - slow_ema[-length + idx] for idx in range(length)]
    dea_values = calculate_ema(dif_values, signal)
    if not dea_values:
        return None
    dif = dif_values[-1]
    dea = dea_values[-1]
    hist = (dif - dea) * 2
    return {"macd_dif": round(dif, 4), "macd_dea": round(dea, 4), "macd_hist": round(hist, 4)}


def calculate_atr(high_prices: list[float], low_prices: list[float], close_prices: list[float], period: int = 14) -> float | None:
    highs = [price for price in high_prices if price > 0]
    lows = [price for price in low_prices if price > 0]
    closes = [price for price in close_prices if price > 0]
    length = min(len(highs), len(lows), len(closes))
    if length < period + 1:
        return None

    highs = highs[-length:]
    lows = lows[-length:]
    closes = closes[-length:]
    true_ranges: list[float] = []
    for idx in range(1, length):
        high = highs[idx]
        low = lows[idx]
        previous_close = closes[idx - 1]
        true_ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    if len(true_ranges) < period:
        return None
    return round(mean(true_ranges[-period:]), 4)


def review_technical(parsed: ParsedSignal, evidence: MarketEvidence) -> TechnicalReview:
    score = 60
    notes: list[str] = []
    metrics: dict[str, float] = {}

    prices = [price for price in evidence.close_prices if price > 0]
    current = evidence.current_price or (prices[-1] if prices else None)

    if current is None:
        return TechnicalReview(TechnicalStatus.NEUTRAL, 40, ["缺当前价，技术面无法确认"], metrics)

    if parsed.stop_loss is not None and current <= parsed.stop_loss:
        return TechnicalReview(TechnicalStatus.WEAK, 0, ["当前价已到或跌破止损价"], metrics)

    if evidence.five_day_change_pct is not None:
        metrics["five_day_change_pct"] = evidence.five_day_change_pct
        if evidence.five_day_change_pct >= 20:
            score -= 30
            notes.append("5 日涨幅过大，追高风险高")
        elif evidence.five_day_change_pct >= 12:
            score -= 15
            notes.append("5 日涨幅偏大，降低执行优先级")
        elif evidence.five_day_change_pct <= -12:
            score -= 20
            notes.append("5 日跌幅偏大，先确认是否破位")

    if evidence.twenty_day_change_pct is not None:
        metrics["twenty_day_change_pct"] = evidence.twenty_day_change_pct
        if evidence.twenty_day_change_pct >= 35:
            score -= 25
            notes.append("20 日涨幅过大，可能处于高位博弈")
        elif evidence.twenty_day_change_pct <= -20:
            score -= 15
            notes.append("20 日走势较弱，谨慎观察")

    if len(prices) >= 5:
        ma5 = mean(prices[-5:])
        metrics["ma5"] = round(ma5, 4)
        if current < ma5:
            score -= 10
            notes.append("当前价低于 5 日均价，短线偏弱")
        else:
            score += 5
            notes.append("当前价高于 5 日均价")

    if len(prices) >= 20:
        ma20 = mean(prices[-20:])
        metrics["ma20"] = round(ma20, 4)
        if current < ma20:
            score -= 15
            notes.append("当前价低于 20 日均价，趋势确认不足")
        elif len(prices) >= 5 and metrics.get("ma5", 0) >= ma20:
            score += 10
            notes.append("5 日均价不低于 20 日均价，趋势结构尚可")

        high_20 = max(prices[-20:])
        low_20 = min(prices[-20:])
        if low_20 > 0:
            range_pct = (high_20 - low_20) / low_20 * 100
            metrics["twenty_day_range_pct"] = round(range_pct, 2)
            if range_pct >= 45:
                score -= 15
                notes.append("20 日振幅过大，不适合新手追涨")

    atr14 = calculate_atr(evidence.high_prices, evidence.low_prices, evidence.close_prices, 14)
    if atr14 is not None:
        metrics["atr14"] = atr14
        atr_pct = atr14 / current * 100 if current > 0 else 0
        metrics["atr14_pct"] = round(atr_pct, 2)
        if atr_pct >= 8:
            score -= 15
            notes.append("ATR 波动偏大，止损距离和仓位必须收紧")
        elif atr_pct >= 5:
            score -= 8
            notes.append("ATR 波动中等，优先使用动态止损")

    rsi14 = calculate_rsi(prices, 14)
    if rsi14 is not None:
        metrics["rsi14"] = rsi14
        recent_20d_change = evidence.twenty_day_change_pct
        if recent_20d_change is None and len(prices) >= 20 and prices[-20] > 0:
            recent_20d_change = (current - prices[-20]) / prices[-20] * 100
        rsi_overheat_context = (evidence.five_day_change_pct is not None and evidence.five_day_change_pct >= 12) or (
            recent_20d_change is not None and recent_20d_change >= 20
        )
        if rsi14 >= 80:
            score -= 10 if rsi_overheat_context else 5
            if rsi_overheat_context:
                notes.append("RSI14 进入高位且近期涨幅偏大，追涨风险上升")
            else:
                notes.append("RSI14 偏强，作为辅助提醒，不单独否决")
        elif rsi14 >= 70:
            if rsi_overheat_context:
                score -= 5
                notes.append("RSI14 偏高且近期涨幅偏大，降低买入优先级")
            else:
                notes.append("RSI14 偏强，需等待分时回踩确认")
        elif rsi14 <= 25:
            score -= 8
            notes.append("RSI14 偏低，先确认是否弱势下跌")

    macd = calculate_macd(prices)
    if macd is not None:
        metrics.update(macd)
        if macd["macd_hist"] < 0 and macd["macd_dif"] < macd["macd_dea"]:
            score -= 8
            notes.append("MACD 位于弱势区，短线信号降级")
        elif macd["macd_hist"] > 0 and macd["macd_dif"] > macd["macd_dea"]:
            score += 5
            notes.append("MACD 短线动能为正，仅作为辅助确认")

    if evidence.volume_ratio is not None:
        metrics["volume_ratio"] = evidence.volume_ratio
        if evidence.volume_ratio >= 3:
            score -= 10
            notes.append("量比过高，可能存在短线情绪放大")

    score = max(0, min(100, score))
    if score <= 35:
        status = TechnicalStatus.WEAK
    elif score <= 60:
        status = TechnicalStatus.NEUTRAL
    elif any("涨幅过大" in item or "高位" in item for item in notes):
        status = TechnicalStatus.OVERHEATED
    else:
        status = TechnicalStatus.HEALTHY

    if not notes:
        notes.append("技术面未发现明显过热或破位信号")
    return TechnicalReview(status, score, notes, metrics)
