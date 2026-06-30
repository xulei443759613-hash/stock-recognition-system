from __future__ import annotations

from .models import ParsedSignal, RiskConfig, ShortTermPlan, SignalAction
from .risk import max_buy_price_for_ratio


def build_short_term_plan(
    action: SignalAction,
    parsed: ParsedSignal,
    current_price: float | None,
    config: RiskConfig,
    account_value: float | None = None,
) -> ShortTermPlan:
    account = account_value or config.default_account_value
    training_bucket = round(account * config.short_term_training_bucket_pct, 2)
    max_position_cash = round(min(training_bucket, account * config.short_term_position_cap), 2)
    max_trade_loss_cash = round(account * config.short_term_max_trade_loss_pct, 2)
    buy_price = current_price or parsed.entry_low
    reasons: list[str] = []

    if action != SignalAction.SMALL_TEST:
        reasons.append(f"当前系统信号为{action.value}，短线模式不允许真实买入")
    if buy_price is None:
        reasons.append("缺当前价或可用买入价")
    if parsed.stop_loss is None:
        reasons.append("缺止损价")
    if parsed.target_price is None:
        reasons.append("缺目标价")

    min_lot_cash = round(buy_price * config.board_lot_shares, 2) if buy_price is not None else None
    min_lot_risk_cash = None
    if buy_price is not None and parsed.stop_loss is not None:
        min_lot_risk_cash = round(max(0.0, buy_price - parsed.stop_loss) * config.board_lot_shares, 2)
        if min_lot_risk_cash <= 0:
            reasons.append("止损价不低于买入价，风险结构无效")
        elif min_lot_risk_cash > max_trade_loss_cash:
            reasons.append(f"买 100 股触发止损约亏 {min_lot_risk_cash:.2f}，超过单笔上限 {max_trade_loss_cash:.2f}")

    if min_lot_cash is not None and min_lot_cash > max_position_cash:
        reasons.append(f"买 100 股约需 {min_lot_cash:.2f}，超过训练仓上限 {max_position_cash:.2f}")

    if buy_price is not None and parsed.target_price is not None and parsed.stop_loss is not None:
        max_buy = max_buy_price_for_ratio(
            parsed.target_price,
            parsed.stop_loss,
            config.short_term_min_risk_reward_ratio,
        )
        if max_buy is not None and buy_price > max_buy:
            reasons.append(
                f"短线模式要求盈亏比不低于 {config.short_term_min_risk_reward_ratio}，最高买入价 {max_buy:.2f}"
            )

    max_shares = 0
    cash_needed = 0.0
    if buy_price is not None and min_lot_cash and min_lot_risk_cash and min_lot_risk_cash > 0:
        cash_lots = int(max_position_cash // min_lot_cash)
        risk_lots = int(max_trade_loss_cash // min_lot_risk_cash)
        max_lots = max(0, min(cash_lots, risk_lots))
        max_shares = max_lots * config.board_lot_shares
        cash_needed = round(max_shares * buy_price, 2)
        if max_shares <= 0 and not any("买 100 股" in reason for reason in reasons):
            reasons.append("训练仓或亏损上限不足以买入 100 股")

    take_profit_5 = round(buy_price * 1.05, 2) if buy_price is not None else None
    take_profit_8 = round(buy_price * 1.08, 2) if buy_price is not None else None
    take_profit_10 = round(buy_price * 1.10, 2) if buy_price is not None else None
    allowed = not reasons and max_shares >= config.board_lot_shares

    return ShortTermPlan(
        enabled=True,
        allowed=allowed,
        account_value=account,
        training_bucket=training_bucket,
        max_position_cash=max_position_cash,
        max_trade_loss_cash=max_trade_loss_cash,
        buy_price=buy_price,
        min_lot_shares=config.board_lot_shares,
        min_lot_cash=min_lot_cash,
        min_lot_risk_cash=min_lot_risk_cash,
        max_shares=max_shares,
        cash_needed=cash_needed,
        stop_loss=parsed.stop_loss,
        take_profit_5_pct=take_profit_5,
        take_profit_8_pct=take_profit_8,
        take_profit_10_pct=take_profit_10,
        max_holding_days=config.short_term_max_holding_days,
        exit_rule=f"{config.short_term_max_holding_days} 天内未达到目标则退出；跌破止损立即退出",
        reasons=reasons,
    )
