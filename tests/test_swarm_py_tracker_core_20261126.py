"""Targeted regression tests for tracker core fixes (2026-11-26)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tracker.defect_tracker import DefectTracker


class TestSwarmPyTrackerCore20261126(unittest.TestCase):
    """Regression suite for 2026-11-26 tracker core hardening."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_null_byte_reports_file_does_not_crash_on_warm_cache_reload(self) -> None:
        """Warm fast-path cache check handles null-byte or invalid reports_file without ValueError."""
        root_dir = self.test_dir / "root_data"
        web_dir = self.test_dir / "web_data"
        root_dir.mkdir(parents=True, exist_ok=True)
        web_dir.mkdir(parents=True, exist_ok=True)

        (root_dir / "daily_reports.json").write_text(
            json.dumps({"reports": [{"id": "r1", "defect_category": "BATTERY"}]}),
            encoding="utf-8",
        )
        dt = DefectTracker(
            root_data_dir=root_dir,
            web_data_dir=web_dir,
            reports_file="invalid\x00reports.json",
        )
        first = dt.load_reports()
        second = dt.load_reports()
        self.assertEqual([r["id"] for r in first], ["r1"])
        self.assertEqual([r["id"] for r in second], ["r1"])

    def test_candidate_report_paths_skips_null_byte_configured_dirs(self) -> None:
        """_candidate_report_paths_by_mtime skips invalid paths raising ValueError."""
        web_dir = self.test_dir / "web_data"
        web_dir.mkdir(parents=True, exist_ok=True)
        web_file = web_dir / "daily_reports.json"
        web_file.write_text(
            json.dumps({"reports": [{"id": "w1", "defect_category": "ICCU"}]}),
            encoding="utf-8",
        )
        dt = DefectTracker(
            root_data_dir="bad\x00root",
            web_data_dir=web_dir,
            public_data_dir="bad\x00public",
        )
        self.assertEqual(dt._candidate_report_paths_by_mtime(), [web_file])
        self.assertEqual([r["id"] for r in dt.load_reports()], ["w1"])

    def test_sync_defect_reports_rejects_null_byte_web_dir_safely(self) -> None:
        """sync_defect_reports returns [] cleanly instead of crashing when web_dir contains null byte."""
        root_dir = self.test_dir / "root_data"
        root_dir.mkdir(parents=True, exist_ok=True)
        (root_dir / "daily_reports.json").write_text(
            json.dumps({"reports": [{"id": "r1", "defect_category": "BATTERY"}]}),
            encoding="utf-8",
        )
        dt = DefectTracker(root_data_dir=root_dir, web_data_dir=self.test_dir / "web_data")
        self.assertEqual(dt.sync_defect_reports(web_dir="bad\x00web_dir"), [])

    def test_get_statistics_sanitizes_category_distribution_values(self) -> None:
        """get_statistics coerces valid counts and strips bool/NaN/Inf/overflow in category_distribution."""
        report_file = self.test_dir / "stats_dist.json"
        report_file.write_text(
            json.dumps(
                {
                    "reports": [{"id": "1", "defect_category": "BATTERY"}],
                    "statistics": {
                        "total_filtered_defects": 1,
                        "critical_defect_count": 0,
                        "avg_negativity_score": 0.4,
                        "category_distribution": {
                            "BATTERY": "3",
                            "BOOL_BAD": True,
                            "STR_BAD": "not_a_number",
                            "OVERFLOW_BAD": "1e500",
                            "VALID_FLOAT": 2.0,
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        dt = DefectTracker(root_data_dir=self.test_dir, web_data_dir=self.test_dir)
        stats = dt.get_statistics(file_path=report_file)
        self.assertEqual(stats["category_distribution"], {"BATTERY": 3, "VALID_FLOAT": 2})


if __name__ == "__main__":
    unittest.main()
