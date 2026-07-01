from __future__ import annotations

import unittest

from stock_recognition_system.holdings import create_holding
from stock_recognition_system.portfolio import build_portfolio_risk_report


class PortfolioTests(unittest.TestCase):
    def test_builds_portfolio_risk_report(self) -> None:
        holdings = [
            create_holding("300001", "测试股份A", 10.0, 100, stop_loss=9.5, take_profit=11.0),
            create_holding("300002", "测试股份B", 20.0, 100, stop_loss=18.0, take_profit=23.0),
        ]

        report = build_portfolio_risk_report(
            holdings,
            current_prices={"300001": 10.5, "300002": 21.0},
            account_value=34000,
        )

        self.assertEqual(report.holdings_count, 2)
        self.assertEqual(report.total_market_value, 3150.0)
        self.assertEqual(report.total_planned_loss_cash, 400.0)
        self.assertEqual(report.exposure_pct, 9.26)
        self.assertEqual(report.planned_loss_pct, 1.18)
        self.assertTrue(any("300002 单票止损风险" in warning for warning in report.warnings))
