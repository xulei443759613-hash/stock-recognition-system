from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from stock_recognition_system import GroupMessage, MarketEvidence, StockRecognitionEngine
from stock_recognition_system.simulation import (
    SIM_AMBIGUOUS,
    SIM_OPEN,
    SIM_STOP_LOSS,
    SIM_TAKE_PROFIT,
    SIM_WAITING_ENTRY,
    load_simulations,
    open_simulation_from_result,
    summarize_simulations,
    update_simulation,
)


DONGYUE_MESSAGE = """
[玫瑰]【7月1号 上午金股】:

[爱心]【东岳硅材 300821】

入场参考：20.90~21.30元
目标参考：23.2元
止损参考：19.0元
参考逻辑：基金参与+游资高控盘+看基本面+盈利拐点+毛利率上升+现金流提升+行业内高评级
"""


class SimulationTests(unittest.TestCase):
    def test_opens_waiting_simulation_from_c_tier_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = StockRecognitionEngine().review(
                GroupMessage(raw_text=DONGYUE_MESSAGE, push_time="10:57", push_date="2026-07-01"),
                MarketEvidence(current_price=21.37),
                account_value=34000,
            )

            position = open_simulation_from_result(Path(tmp), result, push_date="2026-07-01", push_time="10:57")

            self.assertEqual(position.status, SIM_WAITING_ENTRY)
            self.assertEqual(position.entry_price, 20.5)
            self.assertEqual(position.take_profit, 22.14)
            self.assertEqual(position.stop_loss, 19.48)
            self.assertEqual(position.planned_loss_cash, 102.0)
            self.assertEqual(len(load_simulations(Path(tmp))), 1)

    def test_update_enters_and_then_takes_profit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = StockRecognitionEngine().review(
                GroupMessage(raw_text=DONGYUE_MESSAGE, push_time="10:57", push_date="2026-07-01"),
                MarketEvidence(current_price=21.37),
                account_value=34000,
            )
            position = open_simulation_from_result(Path(tmp), result, push_date="2026-07-01", push_time="10:57")

            entered = update_simulation(Path(tmp), position.id, high_price=21.0, low_price=20.45, close_price=20.8, as_of="2026-07-02")
            finished = update_simulation(Path(tmp), position.id, high_price=22.2, low_price=20.7, close_price=22.1, as_of="2026-07-03")

            self.assertEqual(entered.status, SIM_OPEN)
            self.assertEqual(entered.entry_triggered_date, "2026-07-02")
            self.assertEqual(finished.status, SIM_TAKE_PROFIT)
            self.assertEqual(finished.exit_date, "2026-07-03")

    def test_update_marks_ambiguous_when_target_and_stop_both_touch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = StockRecognitionEngine().review(
                GroupMessage(raw_text=DONGYUE_MESSAGE, push_time="10:57", push_date="2026-07-01"),
                MarketEvidence(current_price=21.37),
                account_value=34000,
            )
            position = open_simulation_from_result(Path(tmp), result, push_date="2026-07-01", push_time="10:57")

            updated = update_simulation(Path(tmp), position.id, high_price=22.2, low_price=19.4, close_price=20.0, as_of="2026-07-02")

            self.assertEqual(updated.status, SIM_AMBIGUOUS)
            self.assertEqual(updated.exit_date, "2026-07-02")

    def test_summarizes_simulation_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = StockRecognitionEngine().review(
                GroupMessage(raw_text=DONGYUE_MESSAGE, push_time="10:57", push_date="2026-07-01"),
                MarketEvidence(current_price=21.37),
                account_value=34000,
            )
            first = open_simulation_from_result(Path(tmp), result, push_date="2026-07-01", push_time="10:57")
            update_simulation(Path(tmp), first.id, high_price=22.2, low_price=20.4, close_price=22.1, as_of="2026-07-02")
            second = open_simulation_from_result(Path(tmp), result, push_date="2026-07-01", push_time="10:58")
            update_simulation(Path(tmp), second.id, high_price=20.8, low_price=19.4, close_price=19.5, as_of="2026-07-02")

            summary = summarize_simulations(load_simulations(Path(tmp), include_closed=True))

            self.assertEqual(summary["total"], 2)
            self.assertEqual(summary["closed"], 2)
            self.assertEqual(summary["by_status"][SIM_TAKE_PROFIT], 1)
            self.assertEqual(summary["by_status"][SIM_STOP_LOSS], 1)
            self.assertEqual(summary["planned_profit_cash"], 164.0)
            self.assertEqual(summary["planned_loss_cash"], 102.0)
            self.assertEqual(summary["net_planned_cash"], 62.0)


if __name__ == "__main__":
    unittest.main()
