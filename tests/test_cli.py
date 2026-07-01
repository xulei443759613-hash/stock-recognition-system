from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout

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


if __name__ == "__main__":
    unittest.main()
