from __future__ import annotations

import unittest

from stock_recognition_system.evidence_playbook import build_evidence_requirements


class EvidencePlaybookTests(unittest.TestCase):
    def test_group_claims_map_to_clean_evidence_sources(self) -> None:
        requirements = build_evidence_requirements(
            ["基金参与", "游资高控盘", "毛利率上升", "现金流提升", "行业内高评级"],
            include_baseline=False,
        )
        by_claim = {item.claim: item for item in requirements}

        self.assertEqual(by_claim["基金参与"].category, "机构持仓")
        self.assertIn("巨潮资讯定期报告", by_claim["基金参与"].required_sources)
        self.assertIn("最近一期正式披露", "；".join(by_claim["基金参与"].pass_criteria))

        self.assertEqual(by_claim["游资高控盘"].category, "交易行为")
        self.assertEqual(by_claim["游资高控盘"].priority, "P0")
        self.assertIn("控盘/高控盘默认视为风险话术", "；".join(by_claim["游资高控盘"].notes))

        self.assertEqual(by_claim["毛利率上升"].category, "财务质量")
        self.assertEqual(by_claim["现金流提升"].category, "财务质量")
        self.assertIn("经营现金流", "；".join(by_claim["现金流提升"].collect))

        self.assertEqual(by_claim["行业内高评级"].category, "外部评级")
        self.assertIn("弱证据", "；".join(by_claim["行业内高评级"].notes))

    def test_baseline_requirements_are_first_and_deduplicated(self) -> None:
        requirements = build_evidence_requirements(["基金参与", "基金参与"])

        self.assertEqual([item.claim for item in requirements[:3]], ["消息时点价格", "20日价格结构", "账户承受力"])
        self.assertEqual([item.claim for item in requirements].count("基金参与"), 1)


if __name__ == "__main__":
    unittest.main()
