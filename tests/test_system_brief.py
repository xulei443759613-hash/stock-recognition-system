from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from stock_recognition_system.system_brief import build_system_brief, build_system_brief_markdown


class SystemBriefTests(unittest.TestCase):
    def test_builds_project_level_brief_without_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            brief = build_system_brief(Path(tmp))

        self.assertEqual(brief["project"]["name"], "stock-recognition-system")
        self.assertEqual(brief["current_state"]["simulation_summary"]["total"], 0)
        self.assertIn("review_group_message", [item["scenario"] for item in brief["input_contracts"]])
        self.assertIn("wencai_research", brief["external_source_policy"]["research_only_sources"])

    def test_reads_latest_simulation_summary_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record_dir = Path(tmp)
            (record_dir / "latest-simulation-summary.json").write_text(
                json.dumps({"date": "2026-07-02", "generated_at": "2026-07-02T15:30:00", "source": "unit-test"}),
                encoding="utf-8",
            )

            brief = build_system_brief(record_dir)

        self.assertEqual(brief["current_state"]["latest_simulation_summary"]["date"], "2026-07-02")

    def test_markdown_contains_operational_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            markdown = build_system_brief_markdown(Path(tmp))

        self.assertIn("# Stock Recognition System Brief", markdown)
        self.assertIn("## Input Contracts", markdown)
        self.assertIn("## External Source Policy", markdown)


if __name__ == "__main__":
    unittest.main()
