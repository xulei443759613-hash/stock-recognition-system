from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from stock_recognition_system.cli import main


class CliTests(unittest.TestCase):
    def test_review_can_output_json_for_ai_integration(self) -> None:
        raw = """
        【测试股份 300001】
        入场参考：9.8~10.2元
        目标参考：11元
        止损参考：9.5元
        参考逻辑：业绩增长
        """
        buffer = io.StringIO()

        with redirect_stdout(buffer):
            exit_code = main(
                [
                    "review",
                    "--message",
                    raw,
                    "--current-price",
                    "10",
                    "--account-value",
                    "34000",
                    "--format",
                    "json",
                ]
            )

        payload = json.loads(buffer.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["parsed"]["stock_code"], "300001")
        self.assertEqual(payload["training_plan"]["label"], "B档：轻仓训练100股")
        self.assertIn("report", payload)

    def test_review_can_output_compact_json(self) -> None:
        raw = """
        【测试股份 300001】
        入场参考：9.8~10.2元
        目标参考：11元
        止损参考：9.5元
        参考逻辑：业绩增长
        """
        buffer = io.StringIO()

        with redirect_stdout(buffer):
            exit_code = main(
                [
                    "review",
                    "--message",
                    raw,
                    "--current-price",
                    "10",
                    "--account-value",
                    "34000",
                    "--format",
                    "json-compact",
                ]
            )

        payload = json.loads(buffer.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["stock"]["code"], "300001")
        self.assertEqual(payload["decision"]["training_tier"], "B档：轻仓训练100股")
        self.assertNotIn("evidence_requirements", payload)

    def test_review_can_output_ai_brief(self) -> None:
        raw = """
        【测试股份 300001】
        入场参考：9.8~10.2元
        目标参考：11元
        止损参考：9.5元
        参考逻辑：业绩增长
        """
        buffer = io.StringIO()

        with redirect_stdout(buffer):
            exit_code = main(
                [
                    "review",
                    "--message",
                    raw,
                    "--current-price",
                    "10",
                    "--account-value",
                    "34000",
                    "--format",
                    "ai-brief",
                ]
            )

        output = buffer.getvalue().strip()
        self.assertEqual(exit_code, 0)
        self.assertIn("测试股份(300001)", output)
        self.assertLessEqual(len(output), 120)

    def test_holding_add_and_monitor_with_manual_price(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record_dir = Path(tmp)
            add_buffer = io.StringIO()
            with redirect_stdout(add_buffer):
                add_code = main(
                    [
                        "holding-add",
                        "--record-dir",
                        str(record_dir),
                        "--stock-code",
                        "300001",
                        "--stock-name",
                        "测试股份",
                        "--buy-price",
                        "10",
                        "--shares",
                        "100",
                        "--stop-loss",
                        "9.5",
                        "--take-profit",
                        "11",
                    ]
                )

            monitor_buffer = io.StringIO()
            with redirect_stdout(monitor_buffer):
                monitor_code = main(
                    [
                        "monitor",
                        "--record-dir",
                        str(record_dir),
                        "--stock-code",
                        "300001",
                        "--current-price",
                        "11.1",
                    ]
                )

            self.assertEqual(add_code, 0)
            self.assertEqual(monitor_code, 0)
            self.assertIn("已新增真实持仓", add_buffer.getvalue())
            self.assertIn("触发止盈", monitor_buffer.getvalue())

    def test_portfolio_command_reports_holdings_risk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record_dir = Path(tmp)
            with redirect_stdout(io.StringIO()):
                main(
                    [
                        "holding-add",
                        "--record-dir",
                        str(record_dir),
                        "--stock-code",
                        "300001",
                        "--stock-name",
                        "测试股份",
                        "--buy-price",
                        "10",
                        "--shares",
                        "100",
                        "--stop-loss",
                        "9.5",
                        "--take-profit",
                        "11",
                    ]
                )
            buffer = io.StringIO()

            with redirect_stdout(buffer):
                exit_code = main(["portfolio", "--record-dir", str(record_dir), "--account-value", "34000", "--use-buy-price"])

            self.assertEqual(exit_code, 0)
            self.assertIn("组合风险汇总", buffer.getvalue())
            self.assertIn("持仓数量：1", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
