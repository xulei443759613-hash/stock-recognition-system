from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from stock_recognition_system.broker_orders import (
    OP_GE,
    OP_LE,
    SIDE_BUY,
    SIDE_SELL,
    check_broker_condition_order,
    create_broker_condition_order,
    load_broker_condition_orders,
)
from stock_recognition_system.cli import main


class BrokerConditionOrderTests(unittest.TestCase):
    def test_buy_condition_triggers_when_price_is_below_threshold(self) -> None:
        order = create_broker_condition_order("603040", "新坐标", SIDE_BUY, OP_LE, 70.5, created_at="2026-07-02T10:00:38")

        check = check_broker_condition_order(order, current_price=70.4, as_of="2026-07-02")

        self.assertTrue(check.triggered)
        self.assertIn("买入条件已触发", check.message)

    def test_sell_condition_warns_when_it_may_require_holding(self) -> None:
        order = create_broker_condition_order("603040", "新坐标", SIDE_SELL, OP_GE, 74.0, created_at="2026-07-02T10:03:35")

        check = check_broker_condition_order(order, current_price=72.0, as_of="2026-07-02")

        self.assertFalse(check.triggered)
        self.assertTrue(any("已有持仓" in item for item in check.warnings))

    def test_cli_can_add_and_check_manual_condition_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record_dir = Path(tmp)
            add_buffer = io.StringIO()
            with redirect_stdout(add_buffer):
                add_code = main(
                    [
                        "condition-add",
                        "--record-dir",
                        str(record_dir),
                        "--stock-code",
                        "603040",
                        "--stock-name",
                        "新坐标",
                        "--side",
                        "buy",
                        "--operator",
                        "<=",
                        "--trigger-price",
                        "70.50",
                        "--created-at",
                        "2026-07-02T10:00:38",
                    ]
                )

            check_buffer = io.StringIO()
            with redirect_stdout(check_buffer):
                check_code = main(
                    [
                        "condition-check",
                        "--record-dir",
                        str(record_dir),
                        "--stock-code",
                        "603040",
                        "--current-price",
                        "70.40",
                    ]
                )

            self.assertEqual(add_code, 0)
            self.assertEqual(check_code, 0)
            self.assertEqual(len(load_broker_condition_orders(record_dir)), 1)
            self.assertIn("已触发", check_buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
