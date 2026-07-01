from __future__ import annotations

import unittest

from stock_recognition_system.models import MarketEvidence, ParsedSignal
from stock_recognition_system.technical import calculate_atr, calculate_macd, calculate_rsi, review_technical


class TechnicalIndicatorTests(unittest.TestCase):
    def test_calculates_atr(self) -> None:
        closes = [10, 10.2, 10.4, 10.3, 10.5, 10.7, 10.6, 10.8, 11.0, 10.9, 11.1, 11.3, 11.2, 11.4, 11.5]
        highs = [price + 0.2 for price in closes]
        lows = [price - 0.2 for price in closes]

        atr = calculate_atr(highs, lows, closes, period=14)

        self.assertIsNotNone(atr)
        self.assertGreater(atr, 0)

    def test_calculates_rsi(self) -> None:
        closes = [10, 10.2, 10.1, 10.5, 10.4, 10.8, 10.7, 11.0, 10.9, 11.3, 11.1, 11.5, 11.3, 11.7, 11.6]

        rsi = calculate_rsi(closes, period=14)

        self.assertIsNotNone(rsi)
        self.assertGreaterEqual(rsi, 0)
        self.assertLessEqual(rsi, 100)
        self.assertEqual(calculate_rsi([10.0] * 15, period=14), 50.0)

    def test_calculates_macd(self) -> None:
        closes = [10 + idx * 0.1 for idx in range(40)]

        macd = calculate_macd(closes)

        self.assertIsNotNone(macd)
        self.assertIn("macd_dif", macd)
        self.assertIn("macd_dea", macd)
        self.assertIn("macd_hist", macd)

    def test_review_technical_includes_atr_metrics(self) -> None:
        closes = [10 + idx * 0.1 for idx in range(40)]
        highs = [price + 0.2 for price in closes]
        lows = [price - 0.2 for price in closes]

        review = review_technical(
            ParsedSignal(stop_loss=9.5),
            MarketEvidence(current_price=11.5, close_prices=closes, high_prices=highs, low_prices=lows),
        )

        self.assertIn("atr14", review.metrics)
        self.assertIn("atr14_pct", review.metrics)
        self.assertIn("rsi14", review.metrics)
        self.assertIn("macd_dif", review.metrics)
