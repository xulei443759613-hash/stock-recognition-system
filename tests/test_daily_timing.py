from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from stock_recognition_system.cli import main
from stock_recognition_system.daily_timing import (
    ACTION_AVOID,
    ACTION_CONSIDER,
    ACTION_WAIT,
    evaluate_daily_buy_timing,
)
from stock_recognition_system.models import MarketEvidence
from stock_recognition_system.simulation import SIM_OPEN, SIM_TAKE_PROFIT, SIM_WAITING_ENTRY, SimulationPosition, save_simulations


def _position(status: str = SIM_WAITING_ENTRY) -> SimulationPosition:
    return SimulationPosition(
        id="sim-002326-test",
        stock_code="002326",
        stock_name="永太科技",
        source="group",
        push_date="2026-07-02",
        push_time="09:30",
        created_at="2026-07-02T09:49:15",
        training_tier="C档：模拟观察",
        action="观察",
        status=status,
        entry_price=27.63,
        take_profit=29.84,
        stop_loss=26.25,
        shares=100,
        last_close_price=27.72,
    )


class DailyTimingTests(unittest.TestCase):
    def test_near_entry_can_consider_condition_order(self) -> None:
        evidence = MarketEvidence(
            current_price=27.72,
            change_pct=1.2,
            close_prices=[25.8, 26.1, 26.4, 26.9, 27.2, 27.72],
        )

        decision = evaluate_daily_buy_timing(_position(), evidence, account_value=34000)

        self.assertEqual(decision.action, ACTION_CONSIDER)
        self.assertEqual(decision.suggested_buy_price, 27.68)
        self.assertLessEqual(decision.planned_loss_cash, 170)
        self.assertGreaterEqual(decision.suggested_risk_reward, 1.5)
        self.assertIn("止损", " ".join(decision.required_checks))

    def test_limit_up_is_hard_avoid_even_if_stock_is_mentioned(self) -> None:
        evidence = MarketEvidence(current_price=28.62, change_pct=10.0, is_limit_up=True)

        decision = evaluate_daily_buy_timing(_position(SIM_OPEN), evidence, account_value=34000)

        self.assertEqual(decision.action, ACTION_AVOID)
        self.assertIn("涨停", " ".join(decision.reasons))

    def test_above_buy_ceiling_waits_for_pullback(self) -> None:
        evidence = MarketEvidence(current_price=28.5, change_pct=3.0)

        decision = evaluate_daily_buy_timing(_position(), evidence, account_value=34000)

        self.assertEqual(decision.action, ACTION_WAIT)
        self.assertGreater(decision.distance_to_buy_pct, 0)

    def test_closed_simulation_does_not_reopen_original_plan(self) -> None:
        evidence = MarketEvidence(current_price=27.72, change_pct=1.2)

        decision = evaluate_daily_buy_timing(_position(SIM_TAKE_PROFIT), evidence, account_value=34000)

        self.assertEqual(decision.action, ACTION_AVOID)
        self.assertIn("已结束", " ".join(decision.reasons))

    def test_cli_daily_timing_can_use_last_close_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record_dir = Path(tmp)
            save_simulations(record_dir, [_position()])
            buffer = io.StringIO()

            with redirect_stdout(buffer):
                exit_code = main(
                    [
                        "daily-timing",
                        "--record-dir",
                        str(record_dir),
                        "--use-last-close",
                        "--format",
                        "json",
                    ]
                )

        payload = json.loads(buffer.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["decisions"][0]["stock_code"], "002326")
        self.assertEqual(payload["decisions"][0]["action"], ACTION_CONSIDER)


if __name__ == "__main__":
    unittest.main()
