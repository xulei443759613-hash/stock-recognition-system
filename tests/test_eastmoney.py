import unittest

from stock_recognition_system.eastmoney import parse_daily_klines, to_eastmoney_secid


class EastMoneyDataTests(unittest.TestCase):
    def test_parse_daily_klines_extracts_latest_fields(self) -> None:
        parsed = parse_daily_klines(
            [
                "2026-06-26,10.00,10.20,10.30,9.90,10000,10000000,4.00,1.49,0.15,2.10",
                "2026-06-29,10.20,10.52,10.60,10.10,12000,12600000,4.90,3.14,0.32,2.35",
            ]
        )

        self.assertEqual(parsed.close_prices, [10.20, 10.52])
        self.assertEqual(parsed.change_pct, 3.14)
        self.assertEqual(parsed.turnover_rate, 2.35)
        self.assertEqual(
            parsed.latest_raw,
            "2026-06-29,10.20,10.52,10.60,10.10,12000,12600000,4.90,3.14,0.32,2.35",
        )

    def test_to_eastmoney_secid_uses_exchange_prefix(self) -> None:
        self.assertEqual(to_eastmoney_secid("603991"), "1.603991")
        self.assertEqual(to_eastmoney_secid("000001"), "0.000001")


if __name__ == "__main__":
    unittest.main()
