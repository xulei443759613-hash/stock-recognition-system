from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path

from stock_recognition_system.models import SignalAction
from stock_recognition_system.records import (
    SourceOutcome,
    append_source_outcome,
    load_source_outcomes,
    parse_signal_action,
    score_source_quality,
)


class SourceOutcomeRecordTests(unittest.TestCase):
    def test_append_and_load_source_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record_dir = Path(tmp)
            append_source_outcome(
                record_dir,
                SourceOutcome(
                    action=SignalAction.SMALL_TEST,
                    stock_code="300001",
                    source="test-group",
                    push_date="2026-07-01",
                    reached_target=True,
                    signal_price=10.0,
                    target_price=11.0,
                    max_price=11.2,
                ),
            )
            append_source_outcome(
                record_dir,
                SourceOutcome(action=SignalAction.ABANDON, stock_code="603991", source="other-group", late_push=True),
            )

            loaded = load_source_outcomes(record_dir, source="test-group")

            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].action, SignalAction.SMALL_TEST)
            self.assertEqual(loaded[0].stock_code, "300001")
            self.assertTrue(loaded[0].reached_target)

    def test_source_quality_score_uses_recorded_outcomes(self) -> None:
        outcomes = [
            SourceOutcome(SignalAction.SMALL_TEST, reached_target=True),
            SourceOutcome(SignalAction.WAIT_PULLBACK, hit_stop_loss=True),
            SourceOutcome(SignalAction.ABANDON, late_push=True, chased_after_target=True),
            SourceOutcome(SignalAction.ABANDON),
        ]

        score = score_source_quality(outcomes)

        self.assertEqual(score["sample_size"], 4)
        self.assertEqual(score["target_hit_rate"], 0.25)
        self.assertEqual(score["stop_loss_rate"], 0.25)
        self.assertEqual(score["late_push_rate"], 0.25)
        self.assertEqual(score["chase_case_rate"], 0.25)
        self.assertEqual(score["grade"], "样本不足")

    def test_parse_signal_action_accepts_name_and_value(self) -> None:
        self.assertEqual(parse_signal_action("SMALL_TEST"), SignalAction.SMALL_TEST)
        self.assertEqual(parse_signal_action(SignalAction.ABANDON.value), SignalAction.ABANDON)

    def test_load_ignores_future_outcome_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record_dir = Path(tmp)
            path = record_dir / "outcomes.jsonl"
            path.write_text(
                json.dumps({"action": "ABANDON", "source": "group", "future_field": "ignored"}, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )

            loaded = load_source_outcomes(record_dir)

            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].action, SignalAction.ABANDON)
            self.assertEqual(loaded[0].source, "group")


if __name__ == "__main__":
    unittest.main()
