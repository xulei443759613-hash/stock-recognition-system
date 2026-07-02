from __future__ import annotations

import unittest

from stock_recognition_system.source_registry import build_research_stub, get_external_source, list_external_sources


class SourceRegistryTests(unittest.TestCase):
    def test_registry_contains_safe_boundaries_for_public_and_research_sources(self) -> None:
        sources = {source.source_id: source for source in list_external_sources()}

        self.assertTrue(sources["tencent_public"].enabled_by_default)
        self.assertTrue(sources["eastmoney_public"].can_drive_decision)
        self.assertFalse(sources["wencai_research"].enabled_by_default)
        self.assertFalse(sources["wencai_research"].can_drive_decision)
        self.assertEqual(sources["wencai_research"].decision_scope, "candidate_discovery_only")

    def test_unknown_source_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(KeyError, "Unknown external source"):
            get_external_source("missing")

    def test_research_stub_does_not_execute_external_query(self) -> None:
        payload = build_research_stub("wencai_research", "今日强势但未涨停")

        self.assertEqual(payload["status"], "disabled")
        self.assertFalse(payload["can_drive_decision"])
        self.assertEqual(payload["candidates"], [])
        self.assertIn("No external query was executed.", payload["warnings"])


if __name__ == "__main__":
    unittest.main()
