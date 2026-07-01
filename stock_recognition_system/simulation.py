from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from pathlib import Path

from .models import ReviewResult, TrainingTier


SIM_WAITING_ENTRY = "等待入场"
SIM_OPEN = "模拟持仓"
SIM_TAKE_PROFIT = "模拟止盈"
SIM_STOP_LOSS = "模拟止损"
SIM_AMBIGUOUS = "顺序待查"
CLOSED_STATUSES = {SIM_TAKE_PROFIT, SIM_STOP_LOSS, SIM_AMBIGUOUS}
ACTIVE_STATUSES = {SIM_WAITING_ENTRY, SIM_OPEN}


@dataclass
class SimulationUpdate:
    as_of: str | None = None
    high_price: float | None = None
    low_price: float | None = None
    close_price: float | None = None
    status_after: str = ""
    note: str = ""


@dataclass
class SimulationPosition:
    id: str
    stock_code: str | None
    stock_name: str | None
    source: str
    push_date: str | None
    push_time: str | None
    created_at: str
    training_tier: str
    action: str
    status: str
    entry_price: float
    take_profit: float
    stop_loss: float
    shares: int = 100
    planned_cash: float | None = None
    planned_profit_cash: float | None = None
    planned_loss_cash: float | None = None
    entry_triggered_date: str | None = None
    exit_date: str | None = None
    last_close_price: float | None = None
    note: str = ""
    updates: list[SimulationUpdate] = field(default_factory=list)


def open_simulation_from_result(
    record_dir: str | Path,
    result: ReviewResult,
    source: str = "group",
    push_date: str | None = None,
    push_time: str | None = None,
    now: datetime | None = None,
) -> SimulationPosition:
    if not result.training_plan:
        raise ValueError("缺训练档位，不能创建模拟观察")
    if result.training_plan.tier == TrainingTier.D_ABANDON:
        raise ValueError("D 档放弃不进入模拟观察")

    entry = result.training_plan.reference_buy_price
    take_profit = result.training_plan.suggested_take_profit
    stop_loss = result.training_plan.suggested_stop_loss
    if entry is None or take_profit is None or stop_loss is None:
        raise ValueError("缺模拟买入价、止盈价或止损价，不能创建模拟观察")

    created_at = (now or datetime.now()).replace(microsecond=0).isoformat()
    parsed = result.parsed
    current_price = result.opportunity_review.current_price if result.opportunity_review else None
    status = SIM_WAITING_ENTRY if current_price is not None and current_price > entry * 1.01 else SIM_OPEN
    entry_triggered_date = None if status == SIM_WAITING_ENTRY else push_date
    position = SimulationPosition(
        id=_make_simulation_id(parsed.stock_code if parsed else None, push_date, push_time, created_at),
        stock_code=parsed.stock_code if parsed else None,
        stock_name=parsed.stock_name if parsed else None,
        source=source,
        push_date=push_date,
        push_time=push_time,
        created_at=created_at,
        training_tier=result.training_plan.label,
        action=result.action.value,
        status=status,
        entry_price=entry,
        take_profit=take_profit,
        stop_loss=stop_loss,
        shares=result.training_plan.max_shares or 100,
        planned_cash=result.training_plan.planned_cash,
        planned_profit_cash=result.training_plan.planned_profit_cash,
        planned_loss_cash=result.training_plan.planned_loss_cash,
        entry_triggered_date=entry_triggered_date,
        note="系统自动创建的模拟观察",
    )
    positions = load_simulations(record_dir, include_closed=True)
    positions.append(position)
    save_simulations(record_dir, positions)
    return position


def update_simulation(
    record_dir: str | Path,
    simulation_id: str,
    high_price: float | None = None,
    low_price: float | None = None,
    close_price: float | None = None,
    as_of: str | None = None,
    note: str = "",
) -> SimulationPosition:
    positions = load_simulations(record_dir, include_closed=True)
    for position in positions:
        if position.id != simulation_id:
            continue
        _apply_update(position, high_price, low_price, close_price, as_of, note)
        save_simulations(record_dir, positions)
        return position
    raise ValueError(f"未找到模拟观察：{simulation_id}")


def summarize_simulations(positions: list[SimulationPosition]) -> dict[str, object]:
    total = len(positions)
    by_status: dict[str, int] = {}
    active = 0
    closed = 0
    planned_profit = 0.0
    planned_loss = 0.0
    for position in positions:
        by_status[position.status] = by_status.get(position.status, 0) + 1
        if position.status in ACTIVE_STATUSES:
            active += 1
        if position.status in CLOSED_STATUSES:
            closed += 1
        if position.status == SIM_TAKE_PROFIT and position.planned_profit_cash is not None:
            planned_profit += position.planned_profit_cash
        if position.status == SIM_STOP_LOSS and position.planned_loss_cash is not None:
            planned_loss += position.planned_loss_cash
    return {
        "total": total,
        "active": active,
        "closed": closed,
        "by_status": by_status,
        "planned_profit_cash": round(planned_profit, 2),
        "planned_loss_cash": round(planned_loss, 2),
        "net_planned_cash": round(planned_profit - planned_loss, 2),
    }


def build_simulation_summary_record(
    positions: list[SimulationPosition],
    as_of: str | None = None,
    source: str = "manual",
    generated_at: datetime | None = None,
) -> dict[str, object]:
    generated = (generated_at or datetime.now()).replace(microsecond=0).isoformat()
    return {
        "date": as_of or generated[:10],
        "generated_at": generated,
        "source": source,
        "summary": summarize_simulations(positions),
        "active_positions": [_summary_position(item) for item in positions if item.status in ACTIVE_STATUSES],
        "closed_positions": [_summary_position(item) for item in positions if item.status in CLOSED_STATUSES],
    }


def append_simulation_summary_record(
    record_dir: str | Path,
    positions: list[SimulationPosition],
    as_of: str | None = None,
    source: str = "manual",
    generated_at: datetime | None = None,
) -> tuple[Path, dict[str, object]]:
    record_dir = Path(record_dir)
    record_dir.mkdir(parents=True, exist_ok=True)
    record = build_simulation_summary_record(positions, as_of=as_of, source=source, generated_at=generated_at)
    path = record_dir / "simulation_summaries.jsonl"
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")
    latest_path = record_dir / "latest-simulation-summary.json"
    latest_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path, record


def load_simulations(
    record_dir: str | Path,
    status: str | None = None,
    include_closed: bool = False,
) -> list[SimulationPosition]:
    path = _simulation_path(record_dir)
    if not path.exists():
        return []
    raw_items = json.loads(path.read_text(encoding="utf-8") or "[]")
    positions = [_position_from_dict(item) for item in raw_items]
    if status:
        return [item for item in positions if item.status == status]
    if include_closed:
        return positions
    return [item for item in positions if item.status in ACTIVE_STATUSES]


def save_simulations(record_dir: str | Path, positions: list[SimulationPosition]) -> Path:
    record_dir = Path(record_dir)
    record_dir.mkdir(parents=True, exist_ok=True)
    path = _simulation_path(record_dir)
    path.write_text(json.dumps([_position_to_dict(item) for item in positions], ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _apply_update(
    position: SimulationPosition,
    high_price: float | None,
    low_price: float | None,
    close_price: float | None,
    as_of: str | None,
    note: str,
) -> None:
    if close_price is not None:
        position.last_close_price = close_price

    if position.status in CLOSED_STATUSES:
        position.updates.append(
            SimulationUpdate(as_of, high_price, low_price, close_price, position.status, note or "已结束，未改变状态")
        )
        return

    if position.status == SIM_WAITING_ENTRY:
        if _touches_or_below(low_price, close_price, position.entry_price):
            position.status = SIM_OPEN
            position.entry_triggered_date = as_of
        else:
            position.updates.append(SimulationUpdate(as_of, high_price, low_price, close_price, position.status, note))
            return

    hit_target = _touches_or_above(high_price, close_price, position.take_profit)
    hit_stop = _touches_or_below(low_price, close_price, position.stop_loss)

    if hit_target and hit_stop:
        position.status = SIM_AMBIGUOUS
        position.exit_date = as_of
    elif hit_stop:
        position.status = SIM_STOP_LOSS
        position.exit_date = as_of
    elif hit_target:
        position.status = SIM_TAKE_PROFIT
        position.exit_date = as_of

    position.updates.append(SimulationUpdate(as_of, high_price, low_price, close_price, position.status, note))


def _touches_or_above(primary: float | None, fallback: float | None, threshold: float) -> bool:
    return (primary is not None and primary >= threshold) or (fallback is not None and fallback >= threshold)


def _touches_or_below(primary: float | None, fallback: float | None, threshold: float) -> bool:
    return (primary is not None and primary <= threshold) or (fallback is not None and fallback <= threshold)


def _make_simulation_id(stock_code: str | None, push_date: str | None, push_time: str | None, created_at: str) -> str:
    base = f"{stock_code or 'unknown'}-{push_date or 'nodate'}-{push_time or 'notime'}-{created_at}"
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:8]
    return f"sim-{stock_code or 'unknown'}-{digest}"


def _simulation_path(record_dir: str | Path) -> Path:
    return Path(record_dir) / "simulations.json"


def _summary_position(position: SimulationPosition) -> dict[str, object]:
    return {
        "id": position.id,
        "stock_code": position.stock_code,
        "stock_name": position.stock_name,
        "status": position.status,
        "entry_price": position.entry_price,
        "take_profit": position.take_profit,
        "stop_loss": position.stop_loss,
        "shares": position.shares,
        "last_close_price": position.last_close_price,
        "entry_triggered_date": position.entry_triggered_date,
        "exit_date": position.exit_date,
        "planned_profit_cash": position.planned_profit_cash,
        "planned_loss_cash": position.planned_loss_cash,
    }


def _position_to_dict(position: SimulationPosition) -> dict[str, object]:
    return asdict(position)


def _position_from_dict(raw: dict[str, object]) -> SimulationPosition:
    allowed_fields = {field.name for field in fields(SimulationPosition)}
    values = {key: value for key, value in raw.items() if key in allowed_fields}
    raw_updates = values.get("updates") or []
    values["updates"] = [_update_from_dict(item) for item in raw_updates if isinstance(item, dict)]
    return SimulationPosition(**values)


def _update_from_dict(raw: dict[str, object]) -> SimulationUpdate:
    allowed_fields = {field.name for field in fields(SimulationUpdate)}
    values = {key: value for key, value in raw.items() if key in allowed_fields}
    return SimulationUpdate(**values)
