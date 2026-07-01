from __future__ import annotations

from statistics import mean

from .models import MarketEvidence, ParsedSignal, TechnicalReview, TechnicalStatus


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
