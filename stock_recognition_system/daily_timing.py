from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from statistics import mean

from .models import MarketEvidence, RiskConfig
from .simulation import CLOSED_STATUSES, SIM_OPEN, SimulationPosition
from .technical import calculate_atr, calculate_macd, calculate_rsi


ACTION_CONSIDER = "consider_condition_order"
ACTION_WAIT = "wait_pullback"
ACTION_MONITOR = "monitor_existing"
ACTION_SIMULATE = "simulate_only"
ACTION_AVOID = "avoid"


ACTION_LABELS = {
    ACTION_CONSIDER: "可考虑条件单",
    ACTION_WAIT: "等回踩",
    ACTION_MONITOR: "已触发，转监控",
    ACTION_SIMULATE: "仅模拟观察",
    ACTION_AVOID: "回避",
}


@dataclass
class DailyBuyTiming:
    stock_code: str | None
    stock_name: str | None
    action: str
    action_label: str
    score: int
    current_price: float | None
    change_pct: float | None
    suggested_buy_price: float | None
    buy_zone_low: float | None
    buy_zone_high: float | None
    stop_loss: float
    take_profit: float
    current_risk_reward: float | None = None
    suggested_risk_reward: float | None = None
    planned_loss_cash: float | None = None
    planned_profit_cash: float | None = None
    distance_to_buy_pct: float | None = None
    status: str = ""
    source: str = ""
    push_date: str | None = None
    push_time: str | None = None
    technical_metrics: dict[str, float] = field(default_factory=dict)
    background_notes: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    required_checks: list[str] = field(default_factory=list)
    data_warnings: list[str] = field(default_factory=list)


@dataclass
class DailyBuyTimingReport:
    account_value: float
    training_loss_cap: float
    hard_loss_cap: float
    generated_at: str
    decisions: list[DailyBuyTiming]


def build_daily_buy_timing_report(
    positions: list[SimulationPosition],
    evidence_by_code: dict[str, MarketEvidence],
    account_value: float | None = None,
    config: RiskConfig | None = None,
    generated_at: datetime | None = None,
) -> DailyBuyTimingReport:
    config = config or RiskConfig()
    account = account_value or config.default_account_value
    decisions = [
        evaluate_daily_buy_timing(
            position,
            evidence_by_code.get(position.stock_code or "", MarketEvidence()),
            account_value=account,
            config=config,
        )
        for position in positions
    ]
    decisions.sort(key=_decision_sort_key)
    return DailyBuyTimingReport(
        account_value=account,
        training_loss_cap=round(account * config.short_term_max_trade_loss_pct, 2),
        hard_loss_cap=round(account * config.max_single_trade_loss_pct, 2),
        generated_at=(generated_at or datetime.now()).replace(microsecond=0).isoformat(),
        decisions=decisions,
    )


def evaluate_daily_buy_timing(
    position: SimulationPosition,
    evidence: MarketEvidence,
    account_value: float | None = None,
    config: RiskConfig | None = None,
) -> DailyBuyTiming:
    config = config or RiskConfig()
    account = account_value or config.default_account_value
    lot = position.shares or config.board_lot_shares
    training_loss_cap = account * config.short_term_max_trade_loss_pct
    hard_loss_cap = account * config.max_single_trade_loss_pct
    current = _current_price(position, evidence)
    change_pct = _change_pct(evidence, current)
    metrics = _technical_metrics(evidence, current)

    reasons: list[str] = []
    required_checks = [
        "实盘只允许 100 股训练仓，成交后立即设置止损/止盈提醒",
        "下单前确认实时价格仍在条件价以内，且未快速拉升或涨停",
        "群消息只作线索，基本面/公告/行业信息未核验前不加仓",
    ]
    background_notes = _background_notes(position)
    data_warnings = list(evidence.data_warnings)

    stop_loss = _round_price(position.stop_loss)
    take_profit = _round_price(position.take_profit)
    buy_zone_low: float | None = None
    buy_zone_high: float | None = None
    suggested_buy: float | None = None
    suggested_rr: float | None = None
    planned_loss: float | None = None
    planned_profit: float | None = None
    distance_to_buy: float | None = None
    current_rr = _risk_reward(current, stop_loss, take_profit)

    if current is None:
        return DailyBuyTiming(
            stock_code=position.stock_code,
            stock_name=position.stock_name,
            action=ACTION_AVOID,
            action_label=ACTION_LABELS[ACTION_AVOID],
            score=0,
            current_price=None,
            change_pct=change_pct,
            suggested_buy_price=None,
            buy_zone_low=None,
            buy_zone_high=None,
            stop_loss=stop_loss,
            take_profit=take_profit,
            current_risk_reward=None,
            suggested_risk_reward=None,
            status=position.status,
            source=position.source,
            push_date=position.push_date,
            push_time=position.push_time,
            technical_metrics=metrics,
            background_notes=background_notes,
            reasons=["没有可用当前价，不能估算今日买入时机"],
            required_checks=required_checks,
            data_warnings=data_warnings,
        )

    buy_zone_high = _max_buy_price(position, training_loss_cap, config)
    if buy_zone_high is not None:
        buy_zone_low = _round_price(max(stop_loss * 1.01, buy_zone_high * 0.985))
        suggested_buy = buy_zone_high
        suggested_rr = _risk_reward(suggested_buy, stop_loss, take_profit)
        planned_loss = _cash_loss(suggested_buy, stop_loss, lot)
        planned_profit = _cash_profit(suggested_buy, take_profit, lot)
        if suggested_buy > 0:
            distance_to_buy = round((current - suggested_buy) / suggested_buy * 100, 2)

    score = 50
    hard_veto = False

    if position.status in CLOSED_STATUSES:
        score -= 45
        hard_veto = True
        reasons.append(f"模拟记录已结束：{position.status}，不再按原计划开新仓")

    if current <= stop_loss:
        score -= 40
        hard_veto = True
        reasons.append("现价已到达或跌破计划止损价，结构失效")

    if current >= take_profit * 0.995:
        score -= 35
        hard_veto = True
        reasons.append("现价已接近或超过计划止盈价，属于追高区域")

    if evidence.is_limit_up or _looks_limit_up(position.stock_code, change_pct):
        score -= 40
        hard_veto = True
        reasons.append("涨停或接近涨停，硬性禁止追涨")

    if buy_zone_high is None or buy_zone_low is None:
        score -= 35
        hard_veto = True
        reasons.append("按止损、止盈和账户亏损上限推不出合格买入价")
    elif current > buy_zone_high:
        gap = (current - buy_zone_high) / buy_zone_high * 100
        score -= min(30, int(gap * 5) + 5)
        reasons.append(f"现价高于条件买入上限，至少等回落约 {gap:.2f}%")
    elif current < buy_zone_low:
        score -= 18
        reasons.append("现价低于安全买入区下沿，需先观察是否止跌企稳")
    else:
        score += 25
        reasons.append("现价落在风险收益比和一手亏损都合格的买入区")

    if current_rr is not None:
        if current_rr >= 2.0:
            score += 10
            reasons.append("按现价测算风险收益比大于 2")
        elif current_rr >= config.min_risk_reward_ratio:
            score += 5
            reasons.append("按现价测算风险收益比合格")
        else:
            score -= 18
            reasons.append("按现价测算风险收益比不足")

    current_loss = _cash_loss(current, stop_loss, lot)
    if current_loss is not None:
        if current_loss <= training_loss_cap:
            score += 8
            reasons.append(f"100 股止损亏损约 {current_loss:.0f} 元，未超过训练上限")
        elif current_loss <= hard_loss_cap:
            score -= 10
            reasons.append(f"100 股止损亏损约 {current_loss:.0f} 元，高于训练上限，需等更低价")
        else:
            score -= 25
            hard_veto = True
            reasons.append(f"100 股止损亏损约 {current_loss:.0f} 元，超过账户硬上限")

    score += _technical_score_adjustment(metrics, current, reasons)
    if change_pct is not None:
        if change_pct >= 7:
            score -= 15
            reasons.append("当日涨幅过大，即使未涨停也不适合新手追入")
        elif change_pct >= 4:
            score -= 8
            reasons.append("当日涨幅偏大，优先等分时回踩")
        elif change_pct <= -5:
            score -= 8
            reasons.append("当日跌幅偏大，先确认不是破位下跌")

    score = max(0, min(100, score))
    action = _choose_action(position, hard_veto, score, current, buy_zone_low, buy_zone_high)
    if action == ACTION_CONSIDER:
        required_checks.append("更稳妥做法：设置价格小于等于条件买入价的半自动提醒，人工二次确认后再下单")
    elif action == ACTION_WAIT and buy_zone_high is not None:
        required_checks.append(f"只在价格回到 {buy_zone_high:.2f} 元以内时重新评估")
    elif action == ACTION_MONITOR:
        required_checks.append("若已有真实持仓，改用 monitor 命令检查卖出信号；若未买，不追高补票")

    return DailyBuyTiming(
        stock_code=position.stock_code,
        stock_name=position.stock_name,
        action=action,
        action_label=ACTION_LABELS[action],
        score=score,
        current_price=_round_price(current),
        change_pct=None if change_pct is None else round(change_pct, 2),
        suggested_buy_price=suggested_buy,
        buy_zone_low=buy_zone_low,
        buy_zone_high=buy_zone_high,
        stop_loss=stop_loss,
        take_profit=take_profit,
        current_risk_reward=current_rr,
        suggested_risk_reward=suggested_rr,
        planned_loss_cash=planned_loss,
        planned_profit_cash=planned_profit,
        distance_to_buy_pct=distance_to_buy,
        status=position.status,
        source=position.source,
        push_date=position.push_date,
        push_time=position.push_time,
        technical_metrics=metrics,
        background_notes=background_notes,
        reasons=reasons,
        required_checks=required_checks,
        data_warnings=data_warnings,
    )


def format_daily_buy_timing_report(report: DailyBuyTimingReport) -> str:
    lines = [
        "每日买入时机评估",
        f"生成时间：{report.generated_at}",
        f"账户金额：{report.account_value:.2f}；100股训练亏损上限：{report.training_loss_cap:.2f}；硬上限：{report.hard_loss_cap:.2f}",
        "原则：只评估你提到并进入模拟池的股票；输出是条件与提醒，不是自动下单。",
        "",
    ]
    if not report.decisions:
        lines.append("没有可评估的模拟观察记录。先用 review --simulate 把群消息加入观察池。")
        return "\n".join(lines)

    counts: dict[str, int] = {}
    for item in report.decisions:
        counts[item.action] = counts.get(item.action, 0) + 1
    lines.append(
        "今日摘要："
        f"可考虑条件单 {counts.get(ACTION_CONSIDER, 0)} 只；"
        f"等回踩 {counts.get(ACTION_WAIT, 0)} 只；"
        f"转监控 {counts.get(ACTION_MONITOR, 0)} 只；"
        f"仅模拟 {counts.get(ACTION_SIMULATE, 0)} 只；"
        f"回避 {counts.get(ACTION_AVOID, 0)} 只。"
    )
    if counts.get(ACTION_CONSIDER, 0) == 0:
        lines.append("当前没有合格的条件单候选；不要为了交易而交易。")
    lines.append("")

    for idx, item in enumerate(report.decisions, start=1):
        title = item.stock_name or "-"
        code = item.stock_code or "-"
        lines.append(f"{idx}. {title} {code} | {item.action_label} | {item.score}分")
        lines.append(
            "   "
            f"现价 {_fmt(item.current_price)}"
            f"；涨跌幅 {_fmt_pct(item.change_pct)}"
            f"；条件买入 <= {_fmt(item.suggested_buy_price)}"
            f"；买入区 {_fmt(item.buy_zone_low)}-{_fmt(item.buy_zone_high)}"
        )
        lines.append(
            "   "
            f"止损 {_fmt(item.stop_loss)}"
            f"；止盈 {_fmt(item.take_profit)}"
            f"；现价盈亏比 {_fmt_ratio(item.current_risk_reward)}"
            f"；条件价盈亏比 {_fmt_ratio(item.suggested_risk_reward)}"
        )
        if item.planned_loss_cash is not None or item.planned_profit_cash is not None:
            lines.append(
                "   "
                f"按条件价100股：计划亏损 {_fmt_cash(item.planned_loss_cash)}"
                f"；计划盈利 {_fmt_cash(item.planned_profit_cash)}"
            )
        for reason in item.reasons[:4]:
            lines.append(f"   - {reason}")
        if item.data_warnings:
            lines.append(f"   数据提醒：{'；'.join(item.data_warnings[:2])}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _current_price(position: SimulationPosition, evidence: MarketEvidence) -> float | None:
    if evidence.current_price is not None:
        return evidence.current_price
    prices = [price for price in evidence.close_prices if price > 0]
    if prices:
        return prices[-1]
    return position.last_close_price


def _change_pct(evidence: MarketEvidence, current: float | None) -> float | None:
    if evidence.change_pct is not None:
        return evidence.change_pct
    prices = [price for price in evidence.close_prices if price > 0]
    if current is None or len(prices) < 2:
        return None
    previous = prices[-2]
    if previous <= 0:
        return None
    return (current - previous) / previous * 100


def _max_buy_price(position: SimulationPosition, loss_cap: float, config: RiskConfig) -> float | None:
    entry = position.entry_price
    stop_loss = position.stop_loss
    take_profit = position.take_profit
    if entry <= 0 or stop_loss <= 0 or take_profit <= stop_loss:
        return None
    max_by_entry = entry * 1.01
    max_by_loss = stop_loss + loss_cap / (position.shares or config.board_lot_shares)
    min_rr = config.min_risk_reward_ratio
    max_by_rr = (take_profit + min_rr * stop_loss) / (1 + min_rr)
    value = min(max_by_entry, max_by_loss, max_by_rr)
    if value <= stop_loss:
        return None
    return _floor_price(value)


def _risk_reward(price: float | None, stop_loss: float, take_profit: float) -> float | None:
    if price is None or price <= stop_loss or take_profit <= price:
        return None
    return round((take_profit - price) / (price - stop_loss), 2)


def _cash_loss(price: float | None, stop_loss: float, shares: int) -> float | None:
    if price is None or price <= stop_loss:
        return None
    return round((price - stop_loss) * shares, 2)


def _cash_profit(price: float | None, take_profit: float, shares: int) -> float | None:
    if price is None or take_profit <= price:
        return None
    return round((take_profit - price) * shares, 2)


def _technical_metrics(evidence: MarketEvidence, current: float | None) -> dict[str, float]:
    metrics: dict[str, float] = {}
    prices = [price for price in evidence.close_prices if price > 0]
    if len(prices) >= 5:
        metrics["ma5"] = round(mean(prices[-5:]), 4)
    if len(prices) >= 20:
        metrics["ma20"] = round(mean(prices[-20:]), 4)
        if prices[-20] > 0 and current is not None:
            metrics["twenty_day_change_pct"] = round((current - prices[-20]) / prices[-20] * 100, 2)
    if len(prices) >= 6 and prices[-6] > 0 and current is not None:
        metrics["five_day_change_pct"] = round((current - prices[-6]) / prices[-6] * 100, 2)
    rsi14 = calculate_rsi(prices, 14)
    if rsi14 is not None:
        metrics["rsi14"] = rsi14
    macd = calculate_macd(prices)
    if macd is not None:
        metrics.update(macd)
    atr14 = calculate_atr(evidence.high_prices, evidence.low_prices, evidence.close_prices, 14)
    if atr14 is not None and current is not None and current > 0:
        metrics["atr14"] = atr14
        metrics["atr14_pct"] = round(atr14 / current * 100, 2)
    if evidence.volume_ratio is not None:
        metrics["volume_ratio"] = round(evidence.volume_ratio, 2)
    if evidence.turnover_rate is not None:
        metrics["turnover_rate"] = round(evidence.turnover_rate, 2)
    return metrics


def _technical_score_adjustment(metrics: dict[str, float], current: float, reasons: list[str]) -> int:
    score = 0
    ma5 = metrics.get("ma5")
    ma20 = metrics.get("ma20")
    if ma5 is not None and ma20 is not None:
        if current >= ma5 >= ma20:
            score += 8
            reasons.append("短线价格在 5 日和 20 日均线上方，趋势结构尚可")
        elif current < ma20:
            score -= 12
            reasons.append("现价低于 20 日均线，短线结构偏弱")
    elif ma5 is not None:
        if current >= ma5:
            score += 3
        else:
            score -= 5
            reasons.append("现价低于 5 日均线，先等企稳")

    rsi14 = metrics.get("rsi14")
    if rsi14 is not None:
        if rsi14 >= 80:
            score -= 12
            reasons.append("RSI14 过热，追入性价比下降")
        elif rsi14 <= 25:
            score -= 8
            reasons.append("RSI14 过弱，先排除破位下跌")

    if metrics.get("macd_hist", 0) > 0 and metrics.get("macd_dif", 0) > metrics.get("macd_dea", 0):
        score += 4
    elif metrics.get("macd_hist", 0) < 0 and metrics.get("macd_dif", 0) < metrics.get("macd_dea", 0):
        score -= 6
        reasons.append("MACD 动能偏弱，买入时机降级")

    if metrics.get("five_day_change_pct", 0) >= 15:
        score -= 10
        reasons.append("5 日涨幅偏大，短线追高风险上升")
    if metrics.get("twenty_day_change_pct", 0) >= 30:
        score -= 10
        reasons.append("20 日涨幅偏大，优先等回踩")
    if metrics.get("atr14_pct", 0) >= 6:
        score -= 8
        reasons.append("ATR 波动偏大，止损距离和仓位必须更保守")
    if metrics.get("volume_ratio", 0) >= 3:
        score -= 8
        reasons.append("量比过高，可能是情绪脉冲，不适合直接追")
    return score


def _choose_action(
    position: SimulationPosition,
    hard_veto: bool,
    score: int,
    current: float,
    buy_zone_low: float | None,
    buy_zone_high: float | None,
) -> str:
    if hard_veto:
        return ACTION_AVOID
    if buy_zone_low is None or buy_zone_high is None:
        return ACTION_AVOID
    if current > buy_zone_high:
        gap_pct = (current - buy_zone_high) / buy_zone_high * 100
        if gap_pct <= 0.5 and score >= 35:
            return ACTION_CONSIDER
        if position.status == SIM_OPEN:
            return ACTION_MONITOR
        return ACTION_WAIT
    if score < 30:
        return ACTION_AVOID
    if current < buy_zone_low:
        return ACTION_SIMULATE
    if score >= 60:
        return ACTION_CONSIDER
    return ACTION_SIMULATE


def _looks_limit_up(stock_code: str | None, change_pct: float | None) -> bool:
    if change_pct is None:
        return False
    threshold = 19.5 if stock_code and stock_code.startswith(("300", "688")) else 9.5
    return change_pct >= threshold


def _background_notes(position: SimulationPosition) -> list[str]:
    notes = [
        f"来源：{position.source or 'unknown'}",
        f"推送：{position.push_date or '-'} {position.push_time or '-'}",
        f"训练档位：{position.training_tier}",
    ]
    if position.note:
        notes.append(position.note)
    notes.append("公司基本面、公告、行业景气度仍需接入正式数据源核验")
    return notes


def _decision_sort_key(item: DailyBuyTiming) -> tuple[int, int, str]:
    priority = {
        ACTION_CONSIDER: 0,
        ACTION_WAIT: 1,
        ACTION_MONITOR: 2,
        ACTION_SIMULATE: 3,
        ACTION_AVOID: 4,
    }.get(item.action, 9)
    return priority, -item.score, item.stock_code or ""


def _round_price(value: float) -> float:
    return round(value + 1e-9, 2)


def _floor_price(value: float) -> float:
    return int((value + 1e-9) * 100) / 100


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def _fmt_pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}%"


def _fmt_ratio(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def _fmt_cash(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}元"
