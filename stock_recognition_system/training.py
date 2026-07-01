from __future__ import annotations

from .models import (
    EvidenceCheck,
    EvidenceStatus,
    OpportunityReview,
    ParsedSignal,
    RiskConfig,
    ShortTermPlan,
    SignalAction,
    SuggestedExitPlan,
    TrainingPlan,
    TrainingTier,
)


BLOCKING_VETO_KEYWORDS = ["超过目标价", "涨停", "跌破止损价", "价格结构无效", "止损价无效"]
LIGHT_TRAINING_MIN_RR = 1.3


def build_training_plan(
    action: SignalAction,
    parsed: ParsedSignal,
    current_price: float | None,
    hard_vetoes: list[str],
    red_flags: list[str],
    evidence_checks: list[EvidenceCheck],
    short_term_plan: ShortTermPlan | None,
    opportunity: OpportunityReview | None,
    suggested_exit: SuggestedExitPlan | None,
    config: RiskConfig,
    push_time: str | None = None,
    account_value: float | None = None,
) -> TrainingPlan:
    account = account_value or config.default_account_value
    reference = suggested_exit.reference_buy_price if suggested_exit else current_price or parsed.entry_low
    take_profit = suggested_exit.suggested_take_profit if suggested_exit else None
    stop_loss = suggested_exit.suggested_stop_loss if suggested_exit else parsed.stop_loss
    planned_cash, planned_loss, planned_profit = _planned_amounts(reference, take_profit, stop_loss, config)

    if _has_blocking_veto(hard_vetoes):
        return _plan(
            TrainingTier.D_ABANDON,
            False,
            0,
            reference,
            take_profit,
            stop_loss,
            planned_cash,
            planned_loss,
            planned_profit,
            reasons=["触发硬性否决，不进入训练仓"] + hard_vetoes,
            checklist=["不下单", "记录为剔除样本，后续只复盘价格是否先触发风险"],
        )

    a_blockers = _real_trade_blockers(
        parsed,
        current_price,
        hard_vetoes,
        red_flags,
        evidence_checks,
        suggested_exit,
        opportunity,
        config,
        push_time,
        account,
        require_current_entry_zone=True,
    )
    if short_term_plan and short_term_plan.allowed and not a_blockers:
        return _plan(
            TrainingTier.A_REAL_100,
            True,
            min(config.board_lot_shares, short_term_plan.max_shares),
            reference,
            take_profit,
            stop_loss,
            planned_cash,
            planned_loss,
            planned_profit,
            reasons=["严格短线条件已通过，可按训练仓执行 100 股"] + _clean_reasons(short_term_plan.reasons),
            checklist=_real_trade_checklist(config),
        )

    b_blockers = _real_trade_blockers(
        parsed,
        current_price,
        hard_vetoes,
        red_flags,
        evidence_checks,
        suggested_exit,
        opportunity,
        config,
        push_time,
        account,
        require_current_entry_zone=True,
    )
    if action != SignalAction.ABANDON and not b_blockers:
        return _plan(
            TrainingTier.B_LIGHT_100,
            True,
            config.board_lot_shares,
            reference,
            take_profit,
            stop_loss,
            planned_cash,
            planned_loss,
            planned_profit,
            reasons=[f"未达到 A 档严格短线标准，但满足轻仓训练：盈亏比不低于 {LIGHT_TRAINING_MIN_RR} 且单笔亏损受控"],
            checklist=_real_trade_checklist(config),
        )

    reasons = b_blockers or ["真实仓位条件不足，先用模拟盘验证规则"]
    if action == SignalAction.ABANDON:
        reasons.insert(0, "原始动作信号为放弃，不能直接买入")
    if hard_vetoes:
        reasons.extend(item for item in hard_vetoes if item not in reasons)

    return _plan(
        TrainingTier.C_SIMULATE,
        False,
        0,
        reference,
        take_profit,
        stop_loss,
        planned_cash,
        planned_loss,
        planned_profit,
        reasons=reasons,
        checklist=_simulate_checklist(),
    )


def _real_trade_blockers(
    parsed: ParsedSignal,
    current_price: float | None,
    hard_vetoes: list[str],
    red_flags: list[str],
    evidence_checks: list[EvidenceCheck],
    suggested_exit: SuggestedExitPlan | None,
    opportunity: OpportunityReview | None,
    config: RiskConfig,
    push_time: str | None,
    account: float,
    require_current_entry_zone: bool,
) -> list[str]:
    blockers: list[str] = []
    reference = suggested_exit.reference_buy_price if suggested_exit else current_price or parsed.entry_low
    stop_loss = suggested_exit.suggested_stop_loss if suggested_exit else parsed.stop_loss
    take_profit = suggested_exit.suggested_take_profit if suggested_exit else parsed.target_price
    planned_cash, planned_loss, _ = _planned_amounts(reference, take_profit, stop_loss, config)
    max_position_cash = round(min(account * config.short_term_training_bucket_pct, account * config.short_term_position_cap), 2)
    max_trade_loss_cash = round(account * config.short_term_max_trade_loss_pct, 2)

    if any("缺当前价" in item for item in hard_vetoes) or current_price is None:
        blockers.append("缺消息时点价或当前价，不能真实下单")
    if parsed.target_price is None or parsed.stop_loss is None:
        blockers.append("缺群消息目标价或止损价，不能真实训练")
    if suggested_exit is None or suggested_exit.suggested_take_profit is None or suggested_exit.suggested_stop_loss is None:
        blockers.append("缺系统建议止盈止损，不能真实训练")
    if suggested_exit and suggested_exit.risk_reward_ratio is not None and suggested_exit.risk_reward_ratio < LIGHT_TRAINING_MIN_RR:
        blockers.append(f"系统建议盈亏比 {suggested_exit.risk_reward_ratio:.2f} 低于轻仓训练下限 {LIGHT_TRAINING_MIN_RR}")
    if suggested_exit and suggested_exit.risk_reward_ratio is None:
        blockers.append("系统建议盈亏比不可计算")
    if planned_cash is not None and planned_cash > max_position_cash:
        blockers.append(f"买 100 股约需 {planned_cash:.2f}，超过训练仓上限 {max_position_cash:.2f}")
    if planned_loss is None or planned_loss <= 0:
        blockers.append("按建议止损无法形成有效亏损边界")
    elif planned_loss > max_trade_loss_cash:
        blockers.append(f"买 100 股触发止损约亏 {planned_loss:.2f}，超过单笔上限 {max_trade_loss_cash:.2f}")
    if _has_contradicted_evidence(evidence_checks):
        blockers.append("存在反向证据，不能真实训练")
    if _has_severe_red_flag(red_flags):
        blockers.append("存在严重营销话术，不能真实训练")
    if push_time and push_time[-5:] >= config.late_push_time:
        blockers.append("尾盘推送，真实训练至少等次日确认")
    if _is_waiting_price(current_price, reference, opportunity):
        blockers.append("当前价高于训练可执行价，只能设到价提醒")
    if require_current_entry_zone and current_price is not None and parsed.entry_low is not None and parsed.entry_high is not None:
        if current_price < parsed.entry_low:
            blockers.append("当前价低于入场区间，需先确认不是走弱")
        elif current_price > parsed.entry_high:
            blockers.append("当前价高于入场区间，不能追")
    return _dedupe(blockers)


def _planned_amounts(
    reference: float | None,
    take_profit: float | None,
    stop_loss: float | None,
    config: RiskConfig,
) -> tuple[float | None, float | None, float | None]:
    if reference is None:
        return None, None, None
    planned_cash = round(reference * config.board_lot_shares, 2)
    planned_loss = None
    planned_profit = None
    if stop_loss is not None:
        planned_loss = round(max(0.0, reference - stop_loss) * config.board_lot_shares, 2)
    if take_profit is not None:
        planned_profit = round(max(0.0, take_profit - reference) * config.board_lot_shares, 2)
    return planned_cash, planned_loss, planned_profit


def _plan(
    tier: TrainingTier,
    real_trade_allowed: bool,
    max_shares: int,
    reference: float | None,
    take_profit: float | None,
    stop_loss: float | None,
    planned_cash: float | None,
    planned_loss: float | None,
    planned_profit: float | None,
    reasons: list[str],
    checklist: list[str],
) -> TrainingPlan:
    return TrainingPlan(
        tier=tier,
        label=tier.value,
        real_trade_allowed=real_trade_allowed,
        max_shares=max_shares,
        reference_buy_price=reference,
        suggested_take_profit=take_profit,
        suggested_stop_loss=stop_loss,
        planned_cash=planned_cash,
        planned_loss_cash=planned_loss,
        planned_profit_cash=planned_profit,
        reasons=_dedupe(reasons),
        checklist=checklist,
    )


def _has_blocking_veto(hard_vetoes: list[str]) -> bool:
    return any(any(keyword in item for keyword in BLOCKING_VETO_KEYWORDS) for item in hard_vetoes)


def _has_contradicted_evidence(evidence_checks: list[EvidenceCheck]) -> bool:
    return any(item.status == EvidenceStatus.CONTRADICTED for item in evidence_checks)


def _has_severe_red_flag(red_flags: list[str]) -> bool:
    return any(item.startswith("严重话术") for item in red_flags)


def _is_waiting_price(current_price: float | None, reference: float | None, opportunity: OpportunityReview | None) -> bool:
    if current_price is None or reference is None:
        return False
    if current_price > reference * 1.01:
        return True
    executable = opportunity.executable_max_buy_price if opportunity else None
    return executable is not None and current_price > executable * 1.01


def _real_trade_checklist(config: RiskConfig) -> list[str]:
    return [
        "不设置无条件自动买入，只在参考价附近人工确认",
        "只买 100 股，成交后立刻记录止损价和止盈价",
        "触发止损必须退出，不用补仓摊低成本",
        f"{config.short_term_max_holding_days} 天内未触达止盈且走弱，按计划退出",
        "买前复查公告、板块和大盘是否出现明显利空",
    ]


def _simulate_checklist() -> list[str]:
    return [
        "不下真实订单",
        "在观察池记录模拟买入价、止盈价、止损价",
        "跟踪次日、3 日、5 日最高价和最低价",
        "若回到参考买入价附近，重新运行系统再决定是否升级",
    ]


def _clean_reasons(reasons: list[str]) -> list[str]:
    return [item for item in reasons if item]


def _dedupe(items: list[str]) -> list[str]:
    deduped: list[str] = []
    for item in items:
        if item and item not in deduped:
            deduped.append(item)
    return deduped
