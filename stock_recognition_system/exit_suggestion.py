from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from .models import MarketEvidence, OpportunityReview, ParsedSignal, RiskConfig, SuggestedExitPlan
from .technical import calculate_atr


def build_suggested_exit_plan(
    parsed: ParsedSignal,
    evidence: MarketEvidence,
    opportunity: OpportunityReview | None,
    config: RiskConfig,
    account_value: float | None = None,
) -> SuggestedExitPlan:
    reference = _reference_buy_price(parsed, evidence, opportunity)
    if reference is None:
        return SuggestedExitPlan(
            None,
            None,
            None,
            warnings=["缺参考买入价，无法综合推荐止盈止损"],
        )

    account = account_value or config.default_account_value
    stop_candidates = _stop_candidates(parsed, evidence, reference, account, config)
    if not stop_candidates:
        return SuggestedExitPlan(
            reference,
            None,
            None,
            warnings=["缺有效止损候选，不能推荐止盈止损"],
        )

    suggested_stop = max(price for price, _ in stop_candidates)
    stop_basis = [note for price, note in stop_candidates if price == suggested_stop]
    target_candidates = _target_candidates(parsed, reference, suggested_stop, config, opportunity)
    suggested_target = target_candidates[0][0]
    target_basis = [target_candidates[0][1]]

    reward = suggested_target - reference
    risk = reference - suggested_stop
    reward_pct = round(reward / reference * 100, 2) if reference > 0 else None
    risk_pct = round(risk / reference * 100, 2) if reference > 0 else None
    ratio = round(reward / risk, 2) if risk > 0 else None
    max_loss_per_lot = round(risk * config.board_lot_shares, 2) if risk > 0 else None

    warnings: list[str] = []
    if parsed.target_price is not None and suggested_target > parsed.target_price:
        warnings.append("建议止盈价高于群消息目标价，需确认上方空间是否真实存在")
    if ratio is not None and ratio < config.min_risk_reward_ratio:
        warnings.append(f"建议价位盈亏比 {ratio:.2f} 低于 {config.min_risk_reward_ratio}，不适合真实仓位")
    if opportunity and not opportunity.real_trade_allowed:
        warnings.append("当前不允许真实仓位，建议止盈止损仅用于等待条件和模拟复盘")

    return SuggestedExitPlan(
        reference_buy_price=reference,
        suggested_take_profit=suggested_target,
        suggested_stop_loss=suggested_stop,
        reward_pct=reward_pct,
        risk_pct=risk_pct,
        risk_reward_ratio=ratio,
        max_loss_per_lot=max_loss_per_lot,
        basis=target_basis + stop_basis,
        warnings=warnings,
    )


def _reference_buy_price(
    parsed: ParsedSignal,
    evidence: MarketEvidence,
    opportunity: OpportunityReview | None,
) -> float | None:
    current = evidence.current_price
    executable = opportunity.executable_max_buy_price if opportunity else None
    if current is not None and executable is not None and current > executable:
        return executable
    return current or parsed.entry_low


def _stop_candidates(
    parsed: ParsedSignal,
    evidence: MarketEvidence,
    reference: float,
    account: float,
    config: RiskConfig,
) -> list[tuple[float, str]]:
    candidates: list[tuple[float, str]] = []

    if parsed.stop_loss is not None and parsed.stop_loss < reference:
        candidates.append((_round_price(parsed.stop_loss), "原始止损价有效"))

    short_term_stop = _price_times(reference, "0.95")
    if short_term_stop < reference:
        candidates.append((short_term_stop, "4-5 日短线训练按约 5% 回撤控制止损"))

    risk_cap_stop = _round_decimal(
        Decimal(str(reference))
        - Decimal(str(account)) * Decimal(str(config.short_term_max_trade_loss_pct)) / Decimal(str(config.board_lot_shares))
    )
    if risk_cap_stop < reference:
        candidates.append((risk_cap_stop, "按账户单笔最大亏损和 100 股一手反推止损"))

    support_stop = _support_stop(evidence.close_prices, reference)
    if support_stop is not None:
        candidates.append((support_stop, "按近 5 日收盘支撑下沿预留约 2%"))

    volatility_stop = _volatility_stop(evidence.close_prices, reference)
    if volatility_stop is not None:
        candidates.append((volatility_stop, "按近期平均波动估算止损"))

    atr_stop = _atr_stop(evidence, reference)
    if atr_stop is not None:
        candidates.append((atr_stop, "按 ATR14 动态波动止损"))

    return [(price, note) for price, note in candidates if 0 < price < reference]


def _target_candidates(
    parsed: ParsedSignal,
    reference: float,
    stop_loss: float,
    config: RiskConfig,
    opportunity: OpportunityReview | None,
) -> list[tuple[float, str]]:
    baseline_target = _price_times(reference, "1.08")
    min_rr_target = _round_decimal(
        Decimal(str(reference))
        + (Decimal(str(reference)) - Decimal(str(stop_loss))) * Decimal(str(config.min_risk_reward_ratio))
    )
    target = max(baseline_target, min_rr_target)
    basis = "按短线 8% 目标和最低盈亏比共同反推"

    if opportunity and opportunity.real_trade_allowed and parsed.target_price is not None and parsed.target_price >= target:
        target = min(parsed.target_price, _price_times(reference, "1.10"))
        basis = "原始目标价不低于系统最低要求，按 10% 以内短线目标收敛"

    if parsed.target_price is not None and baseline_target <= parsed.target_price < min_rr_target:
        target = min_rr_target
        basis = "原始目标价不足以覆盖最低盈亏比，按最低盈亏比反推"

    return [(_round_price(target), basis)]


def _support_stop(close_prices: list[float], reference: float) -> float | None:
    prices = [price for price in close_prices[-5:] if price > 0]
    if not prices:
        return None
    support = min(prices)
    stop = _price_times(support, "0.98")
    return stop if stop < reference else None


def _volatility_stop(close_prices: list[float], reference: float) -> float | None:
    prices = [price for price in close_prices if price > 0]
    if len(prices) < 3:
        return None
    changes = [abs(prices[idx] / prices[idx - 1] - 1) for idx in range(1, len(prices))]
    avg_change = sum(changes) / len(changes)
    stop_pct = min(0.06, max(0.03, avg_change * 1.5))
    stop = _round_decimal(Decimal(str(reference)) * (Decimal("1") - Decimal(str(stop_pct))))
    return stop if stop < reference else None


def _atr_stop(evidence: MarketEvidence, reference: float) -> float | None:
    atr = calculate_atr(evidence.high_prices, evidence.low_prices, evidence.close_prices, 14)
    if atr is None or atr <= 0:
        return None
    stop = _round_decimal(Decimal(str(reference)) - Decimal(str(atr)) * Decimal("1.5"))
    return stop if stop < reference else None


def _round_price(value: float) -> float:
    return _round_decimal(Decimal(str(value)))


def _price_times(price: float, multiplier: str) -> float:
    return _round_decimal(Decimal(str(price)) * Decimal(multiplier))


def _round_decimal(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
