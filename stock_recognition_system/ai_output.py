from __future__ import annotations

from .models import ReviewResult


def build_compact_review(result: ReviewResult) -> dict[str, object]:
    parsed = result.parsed
    rr = result.risk_rewards.get("current_price") or result.risk_rewards.get("entry_low")
    opportunity = result.opportunity_review
    exit_plan = result.suggested_exit_plan
    training = result.training_plan

    return {
        "stock": {
            "name": parsed.stock_name if parsed else None,
            "code": parsed.stock_code if parsed else None,
        },
        "decision": {
            "action": result.action.value,
            "confidence": result.confidence,
            "training_tier": training.label if training else None,
            "real_100_shares_allowed": training.real_trade_allowed if training else False,
        },
        "prices": {
            "current": opportunity.current_price if opportunity else None,
            "entry_low": parsed.entry_low if parsed else None,
            "entry_high": parsed.entry_high if parsed else None,
            "target": parsed.target_price if parsed else None,
            "hard_stop": parsed.stop_loss if parsed else None,
            "system_buy": exit_plan.reference_buy_price if exit_plan else None,
            "system_take_profit": exit_plan.suggested_take_profit if exit_plan else None,
            "system_stop_loss": exit_plan.suggested_stop_loss if exit_plan else None,
            "executable_max_buy": opportunity.executable_max_buy_price if opportunity else None,
        },
        "risk": {
            "risk_reward": rr.ratio if rr else None,
            "planned_profit_cash": training.planned_profit_cash if training else None,
            "planned_loss_cash": training.planned_loss_cash if training else None,
            "max_position_pct": result.max_position_pct,
        },
        "top_reasons": result.reasons[:5],
        "watch_conditions": opportunity.watch_conditions[:5] if opportunity else [],
        "next_checks": result.next_checks[:5],
    }


def build_ai_brief(result: ReviewResult, max_chars: int = 120) -> str:
    compact = build_compact_review(result)
    stock = compact["stock"]
    decision = compact["decision"]
    prices = compact["prices"]
    risk = compact["risk"]
    reasons = "；".join(str(item) for item in compact["top_reasons"][:2])
    text = (
        f"{stock.get('name') or '-'}({stock.get('code') or '-'}) "
        f"{decision.get('action')} {decision.get('training_tier') or '-'}；"
        f"现价{_fmt(prices.get('current'))} 买{_fmt(prices.get('system_buy'))} "
        f"止盈{_fmt(prices.get('system_take_profit'))} 止损{_fmt(prices.get('system_stop_loss'))}；"
        f"盈亏比{_fmt(risk.get('risk_reward'))}；{reasons}"
    )
    return text if len(text) <= max_chars else text[: max_chars - 1] + "…"


def _fmt(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)
