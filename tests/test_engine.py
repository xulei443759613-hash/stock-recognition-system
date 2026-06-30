from __future__ import annotations

import unittest

from stock_recognition_system import GroupMessage, MarketEvidence, StockRecognitionEngine


SHIYING_MESSAGE = """
[玫瑰]【6月30号 上午金股】:

[爱心]【石英股份 603688】

入场参考：80.80~82.45元
目标参考：89.8元
止损参考：73.5元
参考逻辑：控盘程度极高+基金参与+社保加仓+游资高控盘+社保参与，材料

【阿牛智投苏浩  证书编号A0460622070003：以上信息不包含交易时机和仓位指导，不构成投资建议，不擅长操作的请咨询公司服务团队。投资有风险，入市须谨慎。山东阿牛智投资本管理有限公司 91370100724977116F】
"""

LINGXIAN_MESSAGE = """
[玫瑰]【6月29号 下午金股】:

[爱心]【领先股份 603991】

入场参考：124.45~126.95元
目标参考：138.3元
止损参考：113.1元
参考逻辑：控盘程度极高+游资高控盘++盈利拐点+困境反转+收入稳健增长，先进封装

【阿牛智投苏浩  证书编号A0460622070003：以上信息不包含交易时机和仓位指导，不构成投资建议，不擅长操作的请咨询公司服务团队。投资有风险，入市须谨慎。山东阿牛智投资本管理有限公司 91370100724977116F】
"""


class EngineDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = StockRecognitionEngine()

    def test_low_risk_reward_is_abandoned_even_without_current_price(self) -> None:
        result = self.engine.review(GroupMessage(raw_text=SHIYING_MESSAGE, push_time="11:00"))

        self.assertEqual(result.action.value, "放弃")
        self.assertIn("缺当前价，不能输出可执行动作", result.hard_vetoes)
        self.assertTrue(any("盈亏比不足" in reason for reason in result.reasons))
        self.assertEqual(result.max_position_pct, 0.0)

    def test_late_signal_abandoned_when_message_time_price_is_bad(self) -> None:
        evidence = MarketEvidence(current_price=128.32, data_warnings=["message-time inferred price"])
        result = self.engine.review(
            GroupMessage(raw_text=LINGXIAN_MESSAGE, push_time="14:50", push_date="2026-06-29"),
            evidence,
        )

        self.assertEqual(result.action.value, "放弃")
        self.assertTrue(any("14:30 后推送" in flag for flag in result.red_flags))
        self.assertAlmostEqual(result.risk_rewards["current_price"].ratio, 0.66)
        self.assertTrue(any("最高买入价：123.18" in item for item in result.entry_plan.conditions))
        self.assertEqual(result.follow_up_tasks[0].due_date, "2026-06-30")

    def test_abandons_after_target_or_limit_up(self) -> None:
        raw = """
        【测试股份 300001】
        入场参考：10~11元
        目标参考：12元
        止损参考：9元
        参考逻辑：业绩增长
        """
        over_target = self.engine.review(GroupMessage(raw_text=raw), MarketEvidence(current_price=12.5))
        limit_up = self.engine.review(GroupMessage(raw_text=raw), MarketEvidence(current_price=10.5, is_limit_up=True))

        self.assertEqual(over_target.action.value, "放弃")
        self.assertEqual(limit_up.action.value, "放弃")
        self.assertTrue(any("超过目标价" in item for item in over_target.hard_vetoes))
        self.assertTrue(any("涨停" in item for item in limit_up.hard_vetoes))


if __name__ == "__main__":
    unittest.main()
