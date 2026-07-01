from __future__ import annotations

import unittest

from stock_recognition_system import GroupMessage, MarketEvidence, StockRecognitionEngine


DONGYUE_MESSAGE = """
[玫瑰]【7月1号 上午金股】:

[爱心]【东岳硅材 300821】

入场参考：20.90~21.30元
目标参考：23.2元
止损参考：19.0元
参考逻辑：基金参与+游资高控盘+看基本面+盈利拐点+毛利率上升+现金流提升+行业内高评级
"""


class OpportunityReviewTests(unittest.TestCase):
    def test_low_risk_reward_is_kept_as_wait_for_better_price(self) -> None:
        result = StockRecognitionEngine().review(
            GroupMessage(raw_text=DONGYUE_MESSAGE, push_time="10:57", push_date="2026-07-01"),
            MarketEvidence(current_price=21.37),
            account_value=34000,
        )

        self.assertEqual(result.action.value, "放弃")
        self.assertIsNotNone(result.opportunity_review)
        self.assertEqual(result.opportunity_review.rating, "C")
        self.assertEqual(result.opportunity_review.status, "等待更优价格")
        self.assertEqual(result.opportunity_review.executable_max_buy_price, 20.5)
        self.assertEqual(result.opportunity_review.required_pullback_pct, 4.07)
        self.assertIn("机会评级", result.report)
        self.assertIn("训练模式综合可执行价：20.50", result.report)

    def test_verified_low_risk_case_is_a_level_opportunity(self) -> None:
        raw = """
        【测试股份 300001】
        入场参考：9.8~10.2元
        目标参考：13元
        止损参考：9.5元
        参考逻辑：业绩增长
        """
        result = StockRecognitionEngine().review(
            GroupMessage(raw_text=raw, push_time="10:30"),
            MarketEvidence(current_price=10.0, verified_claims={"业绩增长": True}, close_prices=[10.0] * 20),
            account_value=34000,
        )

        self.assertEqual(result.action.value, "小仓位试错")
        self.assertEqual(result.opportunity_review.rating, "A")
        self.assertTrue(result.opportunity_review.real_trade_allowed)


if __name__ == "__main__":
    unittest.main()
