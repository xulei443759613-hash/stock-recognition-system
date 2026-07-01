import unittest
from unittest.mock import patch

from stock_recognition_system.eastmoney import EastMoneyDailyDataProvider, parse_daily_klines, parse_realtime_quote, to_eastmoney_secid


class EastMoneyDataTests(unittest.TestCase):
    def test_parse_daily_klines_extracts_latest_fields(self) -> None:
        parsed = parse_daily_klines(
            [
                "2026-06-26,10.00,10.20,10.30,9.90,10000,10000000,4.00,1.49,0.15,2.10",
                "2026-06-29,10.20,10.52,10.60,10.10,12000,12600000,4.90,3.14,0.32,2.35",
            ]
        )

        self.assertEqual(parsed.close_prices, [10.20, 10.52])
        self.assertEqual(parsed.high_prices, [10.30, 10.60])
        self.assertEqual(parsed.low_prices, [9.90, 10.10])
        self.assertEqual(parsed.change_pct, 3.14)
        self.assertEqual(parsed.turnover_rate, 2.35)
        self.assertEqual(
            parsed.latest_raw,
            "2026-06-29,10.20,10.52,10.60,10.10,12000,12600000,4.90,3.14,0.32,2.35",
        )

    def test_to_eastmoney_secid_uses_exchange_prefix(self) -> None:
        self.assertEqual(to_eastmoney_secid("603991"), "1.603991")
        self.assertEqual(to_eastmoney_secid("000001"), "0.000001")

    def test_parse_realtime_quote_scales_eastmoney_fields(self) -> None:
        parsed = parse_realtime_quote(
            {
                "data": {
                    "f43": 118549,
                    "f57": "600519",
                    "f58": "贵州茅台",
                    "f168": 32,
                    "f170": -79,
                }
            }
        )

        self.assertEqual(parsed.current_price, 1185.49)
        self.assertEqual(parsed.change_pct, -0.79)
        self.assertEqual(parsed.turnover_rate, 0.32)

    def test_parse_realtime_quote_keeps_decimal_values(self) -> None:
        parsed = parse_realtime_quote({"data": {"f43": "1185.49", "f168": "0.32", "f170": "-0.79"}})

        self.assertEqual(parsed.current_price, 1185.49)
        self.assertEqual(parsed.change_pct, -0.79)
        self.assertEqual(parsed.turnover_rate, 0.32)

    def test_provider_falls_back_to_realtime_when_kline_fails(self) -> None:
        with patch("stock_recognition_system.eastmoney._fetch_json") as fetch_json:
            fetch_json.side_effect = [
                ConnectionError("kline disconnected"),
                {"data": {"f43": 118549, "f57": "600519", "f58": "贵州茅台", "f168": 32, "f170": -79}},
            ]

            evidence = EastMoneyDailyDataProvider(close_count=2).get_evidence("600519")

        self.assertEqual(evidence.current_price, 1185.49)
        self.assertEqual(evidence.change_pct, -0.79)
        self.assertEqual(evidence.turnover_rate, 0.32)
        self.assertEqual(evidence.close_prices, [])
        self.assertTrue(any("K-line API failed" in warning for warning in evidence.data_warnings))
        self.assertTrue(any("实时行情降级" in warning for warning in evidence.data_warnings))


if __name__ == "__main__":
    unittest.main()
