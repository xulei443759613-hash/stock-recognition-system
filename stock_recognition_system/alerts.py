from __future__ import annotations

from dataclasses import dataclass

from .holdings import SELL_AMBIGUOUS, SELL_HOLD, SellSignal
from .simulation import SIM_OPEN, SIM_WAITING_ENTRY, SimulationPosition


@dataclass
class Alert:
    source: str
    item_id: str
    stock_code: str | None
    stock_name: str | None
    level: str
    message: str
    current_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None


def build_simulation_alerts(
    position: SimulationPosition,
    high_price: float | None = None,
    low_price: float | None = None,
    close_price: float | None = None,
) -> list[Alert]:
    alerts: list[Alert] = []
    if position.status == SIM_WAITING_ENTRY:
        if _touches_or_below(low_price, close_price, position.entry_price):
            alerts.append(
                Alert(
                    "simulation",
                    position.id,
                    position.stock_code,
                    position.stock_name,
                    "入场提醒",
                    f"价格触及模拟入场价 {position.entry_price:.2f}，需重新运行 review 决定是否升级",
                    close_price,
                    high_price,
                    low_price,
                )
            )
    elif position.status == SIM_OPEN:
        hit_target = _touches_or_above(high_price, close_price, position.take_profit)
        hit_stop = _touches_or_below(low_price, close_price, position.stop_loss)
        if hit_target and hit_stop:
            alerts.append(
                Alert(
                    "simulation",
                    position.id,
                    position.stock_code,
                    position.stock_name,
                    "顺序待查",
                    "模拟持仓同周期同时触及止盈和止损，需要查看分时顺序",
                    close_price,
                    high_price,
                    low_price,
                )
            )
        elif hit_stop:
            alerts.append(
                Alert(
                    "simulation",
                    position.id,
                    position.stock_code,
                    position.stock_name,
                    "止损提醒",
                    f"模拟持仓触及止损 {position.stop_loss:.2f}",
                    close_price,
                    high_price,
                    low_price,
                )
            )
        elif hit_target:
            alerts.append(
                Alert(
                    "simulation",
                    position.id,
                    position.stock_code,
                    position.stock_name,
                    "止盈提醒",
                    f"模拟持仓触及止盈 {position.take_profit:.2f}",
                    close_price,
                    high_price,
                    low_price,
                )
            )
    return alerts


def build_holding_alert(signal: SellSignal) -> Alert | None:
    if signal.action == SELL_HOLD:
        return None
    level = "顺序待查" if signal.action == SELL_AMBIGUOUS else signal.action
    return Alert(
        "holding",
        signal.holding_id,
        signal.stock_code,
        signal.stock_name,
        level,
        "；".join(signal.reasons) if signal.reasons else signal.action,
        signal.current_price,
        signal.high_price,
        signal.low_price,
    )


def _touches_or_above(primary: float | None, fallback: float | None, threshold: float) -> bool:
    return (primary is not None and primary >= threshold) or (fallback is not None and fallback >= threshold)


def _touches_or_below(primary: float | None, fallback: float | None, threshold: float) -> bool:
    return (primary is not None and primary <= threshold) or (fallback is not None and fallback <= threshold)
