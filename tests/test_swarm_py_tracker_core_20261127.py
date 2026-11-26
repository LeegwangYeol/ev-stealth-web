"""Targeted regression tests for tracker core fixes (2026-11-27)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import time
import unittest

from tracker.atomic_writer import (
    _json_default,
    cleanup_stale_lock_files,
    cleanup_stale_temp_files,
    quarantine_corrupted_file,
    read_lock_metadata,
)
from tracker.defect_tracker import DefectTracker


class _ClassWithToDict:
    @classmethod
    def to_dict(cls) -> dict[str, str]:
        return {"should_not": "serialize_class"}


class TestSwarmPyTrackerCore20261127(unittest.TestCase):
    """Regression suite for 2026-11-27 tracker core hardening."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_quarantine_corrupted_file_guards_null_bytes_and_traversal_suffix(self) -> None:
        """quarantine_corrupted_file handles null bytes safely and sanitizes traversal suffixes."""
        self.assertIsNone(quarantine_corrupted_file("bad\x00path.json"))

        nested = self.test_dir / "nested"
        nested.mkdir(parents=True, exist_ok=True)
        for idx, unsafe_suffix in enumerate(("../escape", "sub/bad", "a\\b", "..", ".")):
            bad_file = nested / f"payload_{idx}.json"
            bad_file.write_text("{broken", encoding="utf-8")
            quarantined = quarantine_corrupted_file(bad_file, suffix=unsafe_suffix)
            self.assertIsNotNone(quarantined)
            assert quarantined is not None
            self.assertEqual(quarantined.parent, nested.resolve())
            self.assertIn(".corrupt_", quarantined.name)
            self.assertFalse(bad_file.exists())

    def test_cleanup_and_lock_metadata_null_byte_and_dir_guards(self) -> None:
        """Defensive lock/temp helpers reject null bytes cleanly and skip temp directories."""
        self.assertEqual(read_lock_metadata("bad\x00.lock"), (None, None))
        self.assertEqual(cleanup_stale_temp_files("bad\x00dir"), 0)
        self.assertEqual(cleanup_stale_lock_files("bad\x00dir"), 0)

        tmp_subdir = self.test_dir / ".tmp_keep_dir"
        tmp_subdir.mkdir()
        tmp_file = self.test_dir / ".tmp_stale_file.json"
        tmp_file.write_text("{}", encoding="utf-8")
        old_time = time.time() - 7200.0
        os.utime(tmp_subdir, (old_time, old_time))
        os.utime(tmp_file, (old_time, old_time))

        cleaned = cleanup_stale_temp_files(self.test_dir, max_age_seconds=3600.0)
        self.assertEqual(cleaned, 1)
        self.assertTrue(tmp_subdir.is_dir())
        self.assertFalse(tmp_file.exists())

    def test_json_default_rejects_class_objects(self) -> None:
        """_json_default does not invoke classmethod to_dict on type objects."""
        with self.assertRaises(TypeError):
            _json_default(_ClassWithToDict)

    def test_defect_tracker_rejects_and_quarantines_non_rfc8259_nan_inf_json(self) -> None:
        """DefectTracker rejects NaN/Infinity literals in JSON files and does not sync them."""
        root_dir = self.test_dir / "root_data"
        web_dir = self.test_dir / "web_data"
        root_dir.mkdir(parents=True, exist_ok=True)
        web_dir.mkdir(parents=True, exist_ok=True)

        nan_file = root_dir / "daily_reports.json"
        nan_file.write_text(
            '{"reports": [{"id": "1", "defect_category": "BATTERY", "negativity_score": NaN}]}',
            encoding="utf-8",
        )
        self.assertFalse(DefectTracker.validate_report_file(nan_file))
        self.assertFalse(DefectTracker._validate_report_bytes(nan_file.read_bytes()))

        dt = DefectTracker(root_data_dir=root_dir, web_data_dir=web_dir)
        self.assertEqual(dt.sync_defect_reports(web_dir=web_dir, quarantine_corrupted=True), [])
        self.assertFalse(nan_file.exists())
        self.assertFalse((web_dir / "daily_reports.json").exists())
        self.assertEqual(len(list(root_dir.glob("daily_reports.corrupt_*.json"))), 1)

    def test_load_full_report_data_invalidates_cache_on_quarantine(self) -> None:
        """Quarantining a previously cached report file clears stale in-memory cache."""
        report_file = self.test_dir / "daily_reports.json"
        report_file.write_text(
            json.dumps({"reports": [{"id": "cached-1", "defect_category": "BATTERY"}]}),
            encoding="utf-8",
        )
        dt = DefectTracker(root_data_dir=self.test_dir, web_data_dir=self.test_dir)
        self.assertEqual([r["id"] for r in dt.load_reports(file_path=report_file)], ["cached-1"])

        report_file.write_text('{"reports": [{"id": "bad", "negativity_score": Infinity}]}', encoding="utf-8")
        res = dt.load_full_report_data(file_path=report_file, quarantine_corrupted=True)
        self.assertEqual(res, {"reports": [], "statistics": {}})
        self.assertIsNone(dt._cached_reports)
        self.assertEqual(dt.load_reports(file_path=report_file), [])

    def test_get_statistics_sentiment_score_fallback_and_category_normalization(self) -> None:
        """get_statistics falls back to sentiment_score and normalizes blank top_defect_categories."""
        report_file = self.test_dir / "sentiment_fallback.json"
        report_file.write_text(
            json.dumps(
                {
                    "reports": [
                        {
                            "id": "r1",
                            "defect_category": "BATTERY_CHARGING",
                            "severity": "CRITICAL",
                            "sentiment_score": 0.9,
                        },
                        {
                            "id": "r2",
                            "defect_category": "BUILD_QUALITY",
                            "severity": "LOW",
                            "negativity_score": "  ",
                            "sentiment_score": 0.3,
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )
        dt = DefectTracker(root_data_dir=self.test_dir, web_data_dir=self.test_dir)
        stats = dt.get_statistics(file_path=report_file)
        self.assertEqual(stats["total_filtered_defects"], 2)
        self.assertEqual(stats["critical_defect_count"], 1)
        self.assertEqual(stats["avg_negativity_score"], 0.6)

        blank_cat_file = self.test_dir / "blank_top_cat.json"
        blank_cat_file.write_text(
            json.dumps(
                {
                    "reports": [{"id": "r1", "defect_category": "BATTERY"}],
                    "statistics": {"total_filtered_defects": 1},
                    "top_defect_categories": [{"category": "   ", "count": 1}],
                }
            ),
            encoding="utf-8",
        )
        stats_blank = dt.get_statistics(file_path=blank_cat_file)
        self.assertEqual(stats_blank["category_distribution"], {"UNKNOWN": 1})

    def test_sync_defect_reports_handles_null_byte_root_dir_safely(self) -> None:
        """sync_defect_reports returns [] cleanly when root_data_dir contains a null byte."""
        dt = DefectTracker(
            root_data_dir="bad\x00root",
            web_data_dir=self.test_dir / "web_data",
            public_data_dir="bad\x00public",
        )
        self.assertEqual(dt.sync_defect_reports(), [])


if __name__ == "__main__":
    unittest.main()
