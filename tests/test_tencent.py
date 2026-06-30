import unittest

from stock_recognition_system.tencent import parse_tencent_daily_payload, to_tencent_symbol


class TencentDataTests(unittest.TestCase):
    def test_parse_tencent_daily_payload_extracts_close_and_quote_fields(self) -> None:
        symbol = "sh603991"
        payload = {
            "data": {
                symbol: {
                    "qfqday": [
                        ["2026-06-29", "129.480", "128.320", "133.000", "121.880", "71664.000"],
                        ["2026-06-30", "128.200", "141.150", "141.150", "124.130", "79345.000"],
                    ],
                    "qt": {
                        symbol: [
                            "1",
                            "领先股份",
                            "603991",
                            "141.15",
                            "128.32",
                            "128.20",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "20260630161408",
                            "12.83",
                            "10.00",
                            "141.15",
                            "124.13",
                            "141.15/79345/1075425025",
                            "79345",
                            "107543",
                            "8.86",
                        ]
                    },
                }
            }
        }

        parsed = parse_tencent_daily_payload(payload, symbol)

        self.assertEqual(parsed.close_prices, [128.32, 141.15])
        self.assertEqual(parsed.current_price, 141.15)
        self.assertEqual(parsed.change_pct, 10.00)
        self.assertEqual(parsed.turnover_rate, 8.86)
        self.assertEqual(parsed.latest_raw, ["2026-06-30", "128.200", "141.150", "141.150", "124.130", "79345.000"])

    def test_to_tencent_symbol_uses_exchange_prefix(self) -> None:
        self.assertEqual(to_tencent_symbol("603991"), "sh603991")
        self.assertEqual(to_tencent_symbol("000001"), "sz000001")


if __name__ == "__main__":
    unittest.main()
