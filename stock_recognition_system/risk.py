from __future__ import annotations

from .models import ExitPlan, ParsedSignal, PositionPlan, RiskConfig, RiskReward, SignalAction


def calculate_risk_reward(buy_price: float, target_price: float, stop_loss: float) -> RiskReward:
    upside_pct = (target_price - buy_price) / buy_price * 100
    downside_pct = (buy_price - stop_loss) / buy_price * 100
    ratio = None if downside_pct <= 0 else upside_pct / downside_pct
    return RiskReward(
        buy_price=buy_price,
        target_price=target_price,
        stop_loss=stop_loss,
        upside_pct=round(upside_pct, 2),
        downside_pct=round(downside_pct, 2),
        ratio=None if ratio is None else round(ratio, 2),
    )


def max_shares_by_loss(account_value: float, buy_price: float, stop_loss: float, max_loss_pct: float) -> int:
    per_share_risk = buy_price - stop_loss
    if per_share_risk <= 0:
        return 0
    max_loss = account_value * max_loss_pct
    return int(max_loss // per_share_risk)


def build_exit_plan(parsed: ParsedSignal) -> ExitPlan:
    take_profit: list[float] = []
    rules: list[str] = []

    if parsed.target_price is not None:
        take_profit.append(parsed.target_price)
        rules.append("接近目标价时至少分批止盈，不把目标价当成必达承诺")
    else:
        rules.append("缺目标价，不能制定止盈计划")

    if parsed.stop_loss is not None:
        rules.append("跌破止损价时退出，不加仓摊平")
    else:
        rules.append("缺止损价，不能做真实仓位")

    return ExitPlan(stop_loss=parsed.stop_loss, take_profit=take_profit, rules=rules)


def build_position_plan(
    action: SignalAction,
    parsed: ParsedSignal,
    current_price: float | None,
    config: RiskConfig,
    account_value: float | None = None,
) -> PositionPlan:
    if action in {SignalAction.ABANDON, SignalAction.OBSERVE, SignalAction.WAIT_PULLBACK, SignalAction.SIMULATE}:
        return PositionPlan(0.0, config.max_single_trade_loss_pct, note="当前信号不允许真实仓位")

    max_position_pct = config.small_test_position_cap if action == SignalAction.SMALL_TEST else config.verified_position_cap
    buy_price = current_price or parsed.entry_low
    if account_value is None or buy_price is None or parsed.stop_loss is None:
        return PositionPlan(
            max_position_pct,
            config.max_single_trade_loss_pct,
            note="缺账户金额、买入价或止损价，暂不计算股数",
        )

    risk_limited_shares = max_shares_by_loss(account_value, buy_price, parsed.stop_loss, config.max_single_trade_loss_pct)
    cash_limited_shares = int((account_value * max_position_pct) // buy_price)
    max_shares = max(0, min(risk_limited_shares, cash_limited_shares))
    return PositionPlan(
        max_position_pct=max_position_pct,
        max_loss_pct=config.max_single_trade_loss_pct,
        max_shares=max_shares,
        cash_needed=round(max_shares * buy_price, 2),
        note="按仓位上限和单笔最大亏损共同约束",
    )
