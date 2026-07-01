from __future__ import annotations

from .models import EvidenceCheck, EvidenceStatus, MarketEvidence, OpportunityReview, ParsedSignal, RiskConfig, SignalAction
from .risk import max_buy_price_for_ratio


BLOCKING_VETO_KEYWORDS = ["超过目标价", "涨停", "跌破止损价", "价格结构无效", "止损价无效"]


def build_opportunity_review(
    action: SignalAction,
    parsed: ParsedSignal,
    evidence: MarketEvidence,
    evidence_checks: list[EvidenceCheck],
    hard_vetoes: list[str],
    risk_rewards: dict,
    config: RiskConfig,
    account_value: float | None = None,
) -> OpportunityReview:
    account = account_value or config.default_account_value
    max_buy = None
    short_max_buy = None
    one_lot_loss_max_buy = None
    executable_max_buy = None
    reasons: list[str] = []
    watch_conditions: list[str] = []
    missed_rules: list[str] = [
        "如果后续触达目标但从未回到可执行买入价，记录为非可执行上涨，不视为系统错过。",
        "如果后续先回到可执行买入价且未触发止损，再触达目标，记录为可执行错失机会。",
        "如果期间同时触达止损和目标，需要人工查看分时顺序，不能只用最高/最低价下结论。",
    ]

    if parsed.target_price is not None and parsed.stop_loss is not None:
        max_buy = max_buy_price_for_ratio(parsed.target_price, parsed.stop_loss, config.min_risk_reward_ratio)
        short_max_buy = max_buy_price_for_ratio(
            parsed.target_price,
            parsed.stop_loss,
            config.short_term_min_risk_reward_ratio,
        )
        max_loss_cash = account * config.short_term_max_trade_loss_pct
        one_lot_loss_max_buy = round(parsed.stop_loss + max_loss_cash / config.board_lot_shares, 2)
        candidates = [item for item in [short_max_buy, one_lot_loss_max_buy] if item is not None]
        executable_max_buy = min(candidates) if candidates else None

    current_rr = risk_rewards.get("current_price") or risk_rewards.get("entry_low")
    current_price = evidence.current_price
    required_pullback_pct = None
    if current_price is not None and executable_max_buy is not None and current_price > executable_max_buy:
        required_pullback_pct = round((current_price - executable_max_buy) / current_price * 100, 2)

    if current_price is None:
        rating = "待数据"
        status = "缺消息时点价格，只能保留线索"
        score = 20
        reasons.append("缺当前价或消息时点价，不能判断是否错失机会")
    elif _has_blocking_veto(hard_vetoes):
        rating = "D"
        status = "剔除机会"
        score = 20
        reasons.extend(hard_vetoes)
    elif action == SignalAction.SMALL_TEST:
        rating = "A"
        status = "可小仓试错"
        score = 80
        reasons.append("价格、证据和仓位约束未触发主要否决")
    elif action == SignalAction.SIMULATE:
        rating = "B"
        status = "模拟跟踪"
        score = 65
        reasons.append("条件接近可执行，但仍需先模拟验证")
    elif current_rr and current_rr.ratio is not None and current_rr.ratio < config.min_risk_reward_ratio:
        rating = "C"
        status = "等待更优价格"
        score = 50
        reasons.append(f"当前盈亏比 {current_rr.ratio:.2f} 低于 {config.min_risk_reward_ratio}")
    elif action == SignalAction.WAIT_PULLBACK:
        rating = "B"
        status = "等待回踩"
        score = 60
        reasons.append("价格脱离入场上沿，等待回到区间内")
    else:
        rating = "C"
        status = "补证据观察"
        score = 45
        reasons.append("尚未满足真实仓位条件")

    if max_buy is not None:
        watch_conditions.append(f"普通风控最高买入价不高于 {max_buy:.2f}")
    if short_max_buy is not None:
        watch_conditions.append(f"4-5 日短线最高买入价不高于 {short_max_buy:.2f}")
    if one_lot_loss_max_buy is not None:
        watch_conditions.append(f"100 股止损亏损不超上限的买入价不高于 {one_lot_loss_max_buy:.2f}")
    if executable_max_buy is not None:
        watch_conditions.append(f"训练模式综合可执行价不高于 {executable_max_buy:.2f}")
    if required_pullback_pct is not None:
        watch_conditions.append(f"当前价需至少回撤约 {required_pullback_pct:.2f}% 才重新评估")
    if any(item.status == EvidenceStatus.UNVERIFIED for item in evidence_checks):
        watch_conditions.append("补齐 P0/P1 证据后再提升评级")
    if action == SignalAction.ABANDON and rating in {"B", "C"}:
        watch_conditions.append("当前为放弃真实仓位，但保留观察和复盘")

    return OpportunityReview(
        rating=rating,
        status=status,
        score=score,
        real_trade_allowed=action == SignalAction.SMALL_TEST,
        current_price=current_price,
        max_buy_price=max_buy,
        short_term_max_buy_price=short_max_buy,
        one_lot_loss_max_buy_price=one_lot_loss_max_buy,
        executable_max_buy_price=executable_max_buy,
        required_pullback_pct=required_pullback_pct,
        reasons=reasons,
        watch_conditions=watch_conditions,
        missed_review_rules=missed_rules,
    )


def _has_blocking_veto(hard_vetoes: list[str]) -> bool:
    return any(any(keyword in item for keyword in BLOCKING_VETO_KEYWORDS) for item in hard_vetoes)
