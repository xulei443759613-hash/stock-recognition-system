from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, fields
from datetime import date, datetime
from pathlib import Path


ORDER_ACTIVE = "监控中"
ORDER_TRIGGERED = "已触发"
ORDER_EXPIRED = "已失效"
ORDER_CANCELLED = "已取消"

SIDE_BUY = "buy"
SIDE_SELL = "sell"
OP_LE = "<="
OP_GE = ">="


@dataclass
class BrokerConditionOrder:
    id: str
    stock_code: str
    stock_name: str | None
    side: str
    operator: str
    trigger_price: float
    shares: int = 100
    status: str = ORDER_ACTIVE
    broker: str = ""
    created_at: str = ""
    valid_until: str | None = None
    source: str = "manual"
    note: str = ""


@dataclass
class BrokerConditionCheck:
    order_id: str
    stock_code: str
    stock_name: str | None
    side: str
    operator: str
    trigger_price: float
    shares: int
    status: str
    triggered: bool
    current_price: float | None
    message: str
    warnings: list[str] = field(default_factory=list)


def create_broker_condition_order(
    stock_code: str,
    stock_name: str | None,
    side: str,
    operator: str,
    trigger_price: float,
    shares: int = 100,
    broker: str = "",
    created_at: str | None = None,
    valid_until: str | None = None,
    source: str = "manual",
    note: str = "",
) -> BrokerConditionOrder:
    normalized_side = _normalize_side(side)
    normalized_operator = _normalize_operator(operator)
    created = created_at or datetime.now().replace(microsecond=0).isoformat()
    return BrokerConditionOrder(
        id=_make_order_id(stock_code, normalized_side, normalized_operator, trigger_price, created),
        stock_code=stock_code,
        stock_name=stock_name,
        side=normalized_side,
        operator=normalized_operator,
        trigger_price=round(trigger_price, 2),
        shares=shares,
        broker=broker,
        created_at=created,
        valid_until=valid_until,
        source=source,
        note=note,
    )


def append_broker_condition_order(record_dir: str | Path, order: BrokerConditionOrder) -> Path:
    orders = load_broker_condition_orders(record_dir, include_inactive=True)
    existing_ids = {item.id for item in orders}
    if order.id not in existing_ids:
        orders.append(order)
    return save_broker_condition_orders(record_dir, orders)


def load_broker_condition_orders(
    record_dir: str | Path,
    include_inactive: bool = False,
) -> list[BrokerConditionOrder]:
    path = _orders_path(record_dir)
    if not path.exists():
        return []
    raw_items = json.loads(path.read_text(encoding="utf-8") or "[]")
    orders = [_order_from_dict(item) for item in raw_items if isinstance(item, dict)]
    if include_inactive:
        return orders
    return [item for item in orders if item.status == ORDER_ACTIVE]


def save_broker_condition_orders(record_dir: str | Path, orders: list[BrokerConditionOrder]) -> Path:
    record_path = Path(record_dir)
    record_path.mkdir(parents=True, exist_ok=True)
    path = _orders_path(record_path)
    path.write_text(json.dumps([asdict(item) for item in orders], ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def check_broker_condition_order(
    order: BrokerConditionOrder,
    current_price: float | None,
    as_of: str | None = None,
) -> BrokerConditionCheck:
    warnings: list[str] = []
    if current_price is None:
        return BrokerConditionCheck(
            order.id,
            order.stock_code,
            order.stock_name,
            order.side,
            order.operator,
            order.trigger_price,
            order.shares,
            order.status,
            False,
            None,
            "缺当前价，无法判断券商条件单是否触发",
            warnings,
        )

    expired = _is_expired(order.valid_until, as_of)
    if expired:
        return BrokerConditionCheck(
            order.id,
            order.stock_code,
            order.stock_name,
            order.side,
            order.operator,
            order.trigger_price,
            order.shares,
            ORDER_EXPIRED,
            False,
            current_price,
            f"条件单已过有效期 {order.valid_until}",
            warnings,
        )

    triggered = _is_triggered(order.operator, current_price, order.trigger_price)
    side_label = "买入" if order.side == SIDE_BUY else "卖出"
    if triggered:
        message = f"{side_label}条件已触发：现价 {current_price:.2f} {order.operator} {order.trigger_price:.2f}，数量 {order.shares} 股"
    else:
        distance = _distance_to_trigger(order.operator, current_price, order.trigger_price)
        message = f"{side_label}条件未触发：现价 {current_price:.2f}，触发价 {order.operator} {order.trigger_price:.2f}"
        if distance is not None:
            message += f"，距离约 {distance:.2f}%"
    if order.side == SIDE_SELL:
        warnings.append("卖出条件单需要已有持仓；若没有持仓，券商可能触发失败或无法成交")

    return BrokerConditionCheck(
        order.id,
        order.stock_code,
        order.stock_name,
        order.side,
        order.operator,
        order.trigger_price,
        order.shares,
        order.status,
        triggered,
        current_price,
        message,
        warnings,
    )


def _normalize_side(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"buy", "b", "买", "买入"}:
        return SIDE_BUY
    if normalized in {"sell", "s", "卖", "卖出"}:
        return SIDE_SELL
    raise ValueError("side 必须是 buy 或 sell")


def _normalize_operator(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"<=", "le", "lte", "less_equal", "小于等于"}:
        return OP_LE
    if normalized in {">=", "ge", "gte", "greater_equal", "大于等于"}:
        return OP_GE
    raise ValueError("operator 必须是 <= 或 >=")


def _is_triggered(operator: str, current_price: float, trigger_price: float) -> bool:
    if operator == OP_LE:
        return current_price <= trigger_price
    if operator == OP_GE:
        return current_price >= trigger_price
    return False


def _distance_to_trigger(operator: str, current_price: float, trigger_price: float) -> float | None:
    if trigger_price <= 0:
        return None
    if operator == OP_LE:
        return round((current_price - trigger_price) / trigger_price * 100, 2)
    if operator == OP_GE and current_price > 0:
        return round((trigger_price - current_price) / current_price * 100, 2)
    return None


def _is_expired(valid_until: str | None, as_of: str | None) -> bool:
    if not valid_until:
        return False
    try:
        valid_date = date.fromisoformat(valid_until[:10])
    except ValueError:
        return False
    if as_of:
        try:
            current_date = date.fromisoformat(as_of[:10])
        except ValueError:
            current_date = date.today()
    else:
        current_date = date.today()
    return current_date > valid_date


def _orders_path(record_dir: str | Path) -> Path:
    return Path(record_dir) / "broker-conditional-orders.json"


def _order_from_dict(raw: dict[str, object]) -> BrokerConditionOrder:
    allowed_fields = {field.name for field in fields(BrokerConditionOrder)}
    values = {key: value for key, value in raw.items() if key in allowed_fields}
    return BrokerConditionOrder(**values)


def _make_order_id(stock_code: str, side: str, operator: str, trigger_price: float, created_at: str) -> str:
    base = f"{stock_code}-{side}-{operator}-{trigger_price}-{created_at}"
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:8]
    return f"cond-{stock_code}-{digest}"
