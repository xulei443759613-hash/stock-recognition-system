from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from pathlib import Path

from .simulation import SimulationPosition


HOLDING_OPEN = "持有中"
HOLDING_CLOSED = "已关闭"
SELL_HOLD = "继续持有"
SELL_TAKE_PROFIT = "触发止盈"
SELL_STOP_LOSS = "触发止损"
SELL_AMBIGUOUS = "顺序待查"
SELL_DATA_MISSING = "缺行情"


@dataclass
class Holding:
    id: str
    stock_code: str
    stock_name: str | None
    buy_price: float
    shares: int
    buy_date: str | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    source: str = "manual"
    status: str = HOLDING_OPEN
    note: str = ""
    created_at: str = ""


@dataclass
class SellSignal:
    holding_id: str
    stock_code: str
    stock_name: str | None
    action: str
    current_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    pnl_cash: float | None = None
    pnl_pct: float | None = None
    reasons: list[str] = field(default_factory=list)


def create_holding(
    stock_code: str,
    stock_name: str | None,
    buy_price: float,
    shares: int,
    buy_date: str | None = None,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    source: str = "manual",
    note: str = "",
) -> Holding:
    created_at = datetime.now().replace(microsecond=0).isoformat()
    return Holding(
        id=_make_holding_id(stock_code, buy_date, created_at),
        stock_code=stock_code,
        stock_name=stock_name,
        buy_price=buy_price,
        shares=shares,
        buy_date=buy_date,
        stop_loss=stop_loss,
        take_profit=take_profit,
        source=source,
        note=note,
        created_at=created_at,
    )


def create_holding_from_simulation(position: SimulationPosition, buy_date: str | None = None, shares: int | None = None) -> Holding:
    if not position.stock_code:
        raise ValueError("模拟记录缺股票代码，不能升级为持仓")
    return create_holding(
        stock_code=position.stock_code,
        stock_name=position.stock_name,
        buy_price=position.entry_price,
        shares=shares or 100,
        buy_date=buy_date or position.entry_triggered_date or position.push_date,
        stop_loss=position.stop_loss,
        take_profit=position.take_profit,
        source=f"simulation:{position.id}",
        note="由模拟观察池升级为真实持仓记录",
    )


def append_holding(record_dir: str | Path, holding: Holding) -> Path:
    holdings = load_holdings(record_dir, include_closed=True)
    holdings.append(holding)
    return save_holdings(record_dir, holdings)


def load_holdings(record_dir: str | Path, include_closed: bool = False) -> list[Holding]:
    path = _holdings_path(record_dir)
    if not path.exists():
        return []
    raw_items = json.loads(path.read_text(encoding="utf-8") or "[]")
    holdings = [_holding_from_dict(item) for item in raw_items if isinstance(item, dict)]
    if include_closed:
        return holdings
    return [item for item in holdings if item.status == HOLDING_OPEN]


def save_holdings(record_dir: str | Path, holdings: list[Holding]) -> Path:
    record_dir = Path(record_dir)
    record_dir.mkdir(parents=True, exist_ok=True)
    path = _holdings_path(record_dir)
    path.write_text(json.dumps([asdict(item) for item in holdings], ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def monitor_holding(
    holding: Holding,
    current_price: float | None,
    high_price: float | None = None,
    low_price: float | None = None,
) -> SellSignal:
    if current_price is None and high_price is None and low_price is None:
        return SellSignal(
            holding.id,
            holding.stock_code,
            holding.stock_name,
            SELL_DATA_MISSING,
            reasons=["缺当前价或日内高低价，不能判断卖出信号"],
        )

    mark_price = current_price or high_price or low_price
    pnl_cash = round((mark_price - holding.buy_price) * holding.shares, 2) if mark_price is not None else None
    pnl_pct = round((mark_price - holding.buy_price) / holding.buy_price * 100, 2) if mark_price is not None and holding.buy_price > 0 else None

    hit_stop = holding.stop_loss is not None and _touches_or_below(low_price, current_price, holding.stop_loss)
    hit_target = holding.take_profit is not None and _touches_or_above(high_price, current_price, holding.take_profit)

    reasons: list[str] = []
    if hit_stop and hit_target:
        action = SELL_AMBIGUOUS
        reasons.append("同一周期同时触及止损和止盈，需要查看分时顺序")
    elif hit_stop:
        action = SELL_STOP_LOSS
        reasons.append(f"价格触及止损 {holding.stop_loss:.2f}")
    elif hit_target:
        action = SELL_TAKE_PROFIT
        reasons.append(f"价格触及止盈 {holding.take_profit:.2f}")
    else:
        action = SELL_HOLD
        reasons.append("未触发止盈或止损，继续按计划监控")

    return SellSignal(
        holding.id,
        holding.stock_code,
        holding.stock_name,
        action,
        current_price=current_price,
        high_price=high_price,
        low_price=low_price,
        pnl_cash=pnl_cash,
        pnl_pct=pnl_pct,
        reasons=reasons,
    )


def find_holding(holdings: list[Holding], holding_id: str) -> Holding | None:
    return next((item for item in holdings if item.id == holding_id), None)


def _touches_or_above(primary: float | None, fallback: float | None, threshold: float) -> bool:
    return (primary is not None and primary >= threshold) or (fallback is not None and fallback >= threshold)


def _touches_or_below(primary: float | None, fallback: float | None, threshold: float) -> bool:
    return (primary is not None and primary <= threshold) or (fallback is not None and fallback <= threshold)


def _make_holding_id(stock_code: str, buy_date: str | None, created_at: str) -> str:
    base = f"{stock_code}-{buy_date or 'nodate'}-{created_at}"
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:8]
    return f"hold-{stock_code}-{digest}"


def _holdings_path(record_dir: str | Path) -> Path:
    return Path(record_dir) / "holdings.json"


def _holding_from_dict(raw: dict[str, object]) -> Holding:
    allowed_fields = {field.name for field in fields(Holding)}
    values = {key: value for key, value in raw.items() if key in allowed_fields}
    return Holding(**values)
