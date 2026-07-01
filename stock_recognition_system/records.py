from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path

from .followup import append_follow_up_tasks
from .models import ReviewResult, SignalAction
from .risk import max_buy_price_for_ratio


def append_daily_record(record_dir: str | Path, stock_label: str, result: ReviewResult, summary: str) -> Path:
    record_dir = Path(record_dir)
    record_dir.mkdir(parents=True, exist_ok=True)
    path = record_dir / f"{datetime.now():%Y-%m-%d}.md"
    if not path.exists():
        path.write_text(f"# Stock Group Signal Records - {datetime.now():%Y-%m-%d}\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as file:
        file.write(f"\n## {datetime.now():%H:%M:%S} - {stock_label}\n\n")
        file.write(f"- signal: {result.action.value}\n")
        file.write(f"- confidence: {result.confidence}\n")
        file.write(f"- max_position_pct: {result.max_position_pct:.2%}\n")
        file.write(f"- summary: {summary}\n")
    return path


def append_review_report(record_dir: str | Path, result: ReviewResult, summary: str = "") -> Path:
    record_dir = Path(record_dir)
    record_dir.mkdir(parents=True, exist_ok=True)
    path = record_dir / f"{datetime.now():%Y-%m-%d}.md"
    if not path.exists():
        path.write_text(f"# Stock Group Signal Records - {datetime.now():%Y-%m-%d}\n", encoding="utf-8")

    parsed = result.parsed
    stock_label = "未知股票"
    if parsed and parsed.stock_name and parsed.stock_code:
        stock_label = f"{parsed.stock_name} {parsed.stock_code}"
    elif parsed and parsed.stock_code:
        stock_label = parsed.stock_code

    with path.open("a", encoding="utf-8") as file:
        file.write(f"\n\n---\n\n## {datetime.now():%H:%M:%S} - {stock_label}\n\n")
        if summary:
            file.write(f"> {summary}\n\n")
        file.write(result.report or f"- signal: {result.action.value}\n")
        file.write("\n")
    if result.follow_up_tasks:
        append_follow_up_tasks(record_dir, result.follow_up_tasks)
    return path


@dataclass
class SourceOutcome:
    action: SignalAction
    stock_code: str | None = None
    stock_name: str | None = None
    source: str = "group"
    push_date: str | None = None
    push_time: str | None = None
    review_date: str | None = None
    reached_target: bool = False
    hit_stop_loss: bool = False
    late_push: bool = False
    chased_after_target: bool = False
    signal_price: float | None = None
    target_price: float | None = None
    stop_loss: float | None = None
    max_price: float | None = None
    min_price: float | None = None
    close_price: float | None = None
    note: str = ""


NO_REAL_TRADE_ACTIONS = {
    SignalAction.ABANDON,
    SignalAction.OBSERVE,
    SignalAction.WAIT_PULLBACK,
    SignalAction.SIMULATE,
}


def append_source_outcome(record_dir: str | Path, outcome: SourceOutcome) -> Path:
    record_dir = Path(record_dir)
    record_dir.mkdir(parents=True, exist_ok=True)
    path = record_dir / "outcomes.jsonl"
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(_outcome_to_dict(outcome), ensure_ascii=False) + "\n")
    return path


def load_source_outcomes(record_dir: str | Path, source: str | None = None) -> list[SourceOutcome]:
    path = Path(record_dir) / "outcomes.jsonl"
    if not path.exists():
        return []

    outcomes: list[SourceOutcome] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            raw = json.loads(line)
            outcome = _outcome_from_dict(raw)
            if source is None or outcome.source == source:
                outcomes.append(outcome)
    return outcomes


def score_source_quality(outcomes: list[SourceOutcome]) -> dict[str, object]:
    total = len(outcomes)
    if total == 0:
        return {"sample_size": 0, "grade": "无样本", "notes": ["没有复盘记录"]}

    target_hits = sum(1 for item in outcomes if item.reached_target)
    stop_hits = sum(1 for item in outcomes if item.hit_stop_loss)
    late_pushes = sum(1 for item in outcomes if item.late_push)
    chase_cases = sum(1 for item in outcomes if item.chased_after_target)
    abandon_count = sum(1 for item in outcomes if item.action == SignalAction.ABANDON)
    missed_reviews = [classify_opportunity_outcome(item) for item in outcomes]
    no_trade_target_hits = sum(1 for item in missed_reviews if item["status"] in {"可执行错失", "非可执行上涨", "顺序待查"})
    actionable_misses = sum(1 for item in missed_reviews if item["status"] == "可执行错失")
    non_actionable_runups = sum(1 for item in missed_reviews if item["status"] == "非可执行上涨")
    ambiguous_misses = sum(1 for item in missed_reviews if item["status"] == "顺序待查")

    notes: list[str] = []
    score = 60
    score += int(25 * target_hits / total)
    score -= int(30 * stop_hits / total)
    score -= int(20 * late_pushes / total)
    score -= int(20 * chase_cases / total)

    if total < 20:
        notes.append("样本少于 20 条，只能观察，不能评价群源优劣")
    if stop_hits / total >= 0.3:
        notes.append("止损触发比例偏高")
    if late_pushes / total >= 0.3:
        notes.append("尾盘推送比例偏高")
    if chase_cases:
        notes.append("存在超过目标或涨停后推送的追高样本")
    if abandon_count / total >= 0.5:
        notes.append("系统放弃比例较高，群消息噪声偏多")
    if actionable_misses:
        notes.append("存在可执行错失机会，需要复查机会评级和回撤提醒")
    if non_actionable_runups:
        notes.append("存在放弃后上涨但未回到可执行价的样本，不应简单归因于系统过保守")
    if ambiguous_misses:
        notes.append("存在同时触及止损和目标的样本，需要查看分时顺序")

    score = max(0, min(100, score))
    if total < 20:
        grade = "样本不足"
    elif score >= 75:
        grade = "可继续观察"
    elif score >= 55:
        grade = "谨慎观察"
    else:
        grade = "建议远离"

    return {
        "sample_size": total,
        "grade": grade,
        "score": score,
        "target_hit_rate": round(target_hits / total, 4),
        "stop_loss_rate": round(stop_hits / total, 4),
        "late_push_rate": round(late_pushes / total, 4),
        "chase_case_rate": round(chase_cases / total, 4),
        "no_trade_target_hit_rate": round(no_trade_target_hits / total, 4),
        "actionable_missed_rate": round(actionable_misses / total, 4),
        "non_actionable_runup_rate": round(non_actionable_runups / total, 4),
        "ambiguous_missed_rate": round(ambiguous_misses / total, 4),
        "notes": notes,
    }


def classify_opportunity_outcome(
    outcome: SourceOutcome,
    min_ratio: float = 1.5,
    short_term_min_ratio: float = 1.8,
    account_value: float = 34000.0,
    max_trade_loss_pct: float = 0.005,
    lot_shares: int = 100,
) -> dict[str, object]:
    if outcome.action not in NO_REAL_TRADE_ACTIONS:
        return {"status": "已执行或可执行", "executable_max_buy_price": None}
    if not outcome.reached_target:
        return {"status": "未触达目标", "executable_max_buy_price": None}
    if outcome.target_price is None or outcome.stop_loss is None:
        return {"status": "缺复盘价格结构", "executable_max_buy_price": None}

    max_buy = max_buy_price_for_ratio(outcome.target_price, outcome.stop_loss, min_ratio)
    short_max_buy = max_buy_price_for_ratio(outcome.target_price, outcome.stop_loss, short_term_min_ratio)
    one_lot_loss_max_buy = round(outcome.stop_loss + account_value * max_trade_loss_pct / lot_shares, 2)
    executable_candidates = [item for item in [short_max_buy, one_lot_loss_max_buy] if item is not None]
    executable_max_buy = min(executable_candidates) if executable_candidates else max_buy

    if executable_max_buy is None:
        return {"status": "缺可执行价", "executable_max_buy_price": None}

    signal_was_executable = outcome.signal_price is not None and outcome.signal_price <= executable_max_buy
    pulled_back_to_executable = outcome.min_price is not None and outcome.min_price <= executable_max_buy
    touched_stop = outcome.min_price is not None and outcome.min_price <= outcome.stop_loss

    if touched_stop and pulled_back_to_executable:
        status = "顺序待查"
    elif signal_was_executable or pulled_back_to_executable:
        status = "可执行错失"
    else:
        status = "非可执行上涨"

    return {
        "status": status,
        "executable_max_buy_price": executable_max_buy,
        "signal_price": outcome.signal_price,
        "min_price": outcome.min_price,
        "target_price": outcome.target_price,
        "stop_loss": outcome.stop_loss,
    }


def _outcome_to_dict(outcome: SourceOutcome) -> dict[str, object]:
    raw = asdict(outcome)
    raw["action"] = outcome.action.value
    return raw


def _outcome_from_dict(raw: dict[str, object]) -> SourceOutcome:
    allowed_fields = {field.name for field in fields(SourceOutcome)}
    values = {key: value for key, value in raw.items() if key in allowed_fields}
    values["action"] = parse_signal_action(str(values.get("action", SignalAction.OBSERVE.value)))
    return SourceOutcome(**values)


def parse_signal_action(value: str) -> SignalAction:
    normalized = value.strip()
    for action in SignalAction:
        if normalized in {action.name, action.value}:
            return action
    raise ValueError(f"unknown signal action: {value}")
