from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from stock_recognition_system.holdings import (
    SELL_AMBIGUOUS,
    SELL_HOLD,
    SELL_STOP_LOSS,
    SELL_TAKE_PROFIT,
    append_holding,
    create_holding,
    load_holdings,
    monitor_holding,
)


class HoldingTests(unittest.TestCase):
    def test_append_and_load_holding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            holding = create_holding(
                "300001",
                "测试股份",
                buy_price=10.0,
                shares=100,
                buy_date="2026-07-01",
                stop_loss=9.5,
                take_profit=11.0,
            )
            append_holding(Path(tmp), holding)

            loaded = load_holdings(Path(tmp))

            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].stock_code, "300001")
            self.assertEqual(loaded[0].shares, 100)

    def test_monitor_holding_sell_signals(self) -> None:
        holding = create_holding("300001", "测试股份", 10.0, 100, stop_loss=9.5, take_profit=11.0)

        self.assertEqual(monitor_holding(holding, current_price=10.2).action, SELL_HOLD)
        self.assertEqual(monitor_holding(holding, current_price=11.1).action, SELL_TAKE_PROFIT)
        self.assertEqual(monitor_holding(holding, current_price=9.4).action, SELL_STOP_LOSS)
        self.assertEqual(
            monitor_holding(holding, current_price=10.0, high_price=11.1, low_price=9.4).action,
            SELL_AMBIGUOUS,
        )
