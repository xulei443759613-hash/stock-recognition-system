from __future__ import annotations

import unittest

from stock_recognition_system.alerts import build_holding_alert, build_simulation_alerts
from stock_recognition_system.holdings import create_holding, monitor_holding
from stock_recognition_system.simulation import SIM_OPEN, SIM_WAITING_ENTRY, SimulationPosition


def _position(status: str) -> SimulationPosition:
    return SimulationPosition(
        id="sim-1",
        stock_code="300001",
        stock_name="Test Stock",
        source="group",
        push_date="2026-07-01",
        push_time="10:00",
        created_at="2026-07-01T10:00:00",
        training_tier="C",
        action="observe",
        status=status,
        entry_price=10.0,
        take_profit=11.0,
        stop_loss=9.5,
    )


class AlertTests(unittest.TestCase):
    def test_waiting_simulation_triggers_entry_alert(self) -> None:
        alerts = build_simulation_alerts(_position(SIM_WAITING_ENTRY), high_price=10.3, low_price=9.98, close_price=10.1)

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].level, "入场提醒")
        self.assertIn("10.00", alerts[0].message)

    def test_open_simulation_triggers_take_profit_or_stop_loss_alert(self) -> None:
        target_alerts = build_simulation_alerts(_position(SIM_OPEN), high_price=11.1, low_price=10.2, close_price=10.8)
        stop_alerts = build_simulation_alerts(_position(SIM_OPEN), high_price=10.4, low_price=9.4, close_price=9.6)

        self.assertEqual(target_alerts[0].level, "止盈提醒")
        self.assertEqual(stop_alerts[0].level, "止损提醒")

    def test_open_simulation_marks_ambiguous_when_both_exit_prices_touch(self) -> None:
        alerts = build_simulation_alerts(_position(SIM_OPEN), high_price=11.1, low_price=9.4, close_price=10.0)

        self.assertEqual(alerts[0].level, "顺序待查")

    def test_holding_alert_returns_only_for_sell_signal(self) -> None:
        holding = create_holding("300001", "Test Stock", 10.0, 100, stop_loss=9.5, take_profit=11.0)

        self.assertIsNone(build_holding_alert(monitor_holding(holding, current_price=10.2)))
        alert = build_holding_alert(monitor_holding(holding, current_price=11.1))

        self.assertIsNotNone(alert)
        self.assertEqual(alert.level, "触发止盈")


if __name__ == "__main__":
    unittest.main()
