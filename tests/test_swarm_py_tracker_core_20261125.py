"""Targeted regression tests for tracker core fixes (2026-11-25)."""

from __future__ import annotations

import json
import math
from pathlib import Path
import tempfile
from types import MappingProxyType
import unicodedata
import unittest

from tracker.defect_tracker import DefectTracker


class TestSwarmPyTrackerCore20261125(unittest.TestCase):
    """Regression suite for 2026-11-25 tracker core hardening."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_validate_report_file_handles_none_empty_and_null_byte(self) -> None:
        """validate_report_file safely returns False on None, empty/whitespace, and null-byte paths."""
        self.assertFalse(DefectTracker.validate_report_file(None))
        self.assertFalse(DefectTracker.validate_report_file(""))
        self.assertFalse(DefectTracker.validate_report_file("   "))
        self.assertFalse(DefectTracker.validate_report_file("bad\x00path.json"))

    def test_null_byte_file_path_does_not_crash_or_leak_cache(self) -> None:
        """load_reports, query_defects, and get_statistics return empty results on null-byte paths."""
        valid_file = self.test_dir / "valid.json"
        valid_file.write_text(
            json.dumps(
                {
                    "reports": [
                        {
                            "id": "r1",
                            "defect_category": "BATTERY",
                            "severity": "CRITICAL",
                            "negativity_score": 0.8,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        dt = DefectTracker(root_data_dir=self.test_dir, web_data_dir=self.test_dir)
        self.assertEqual(len(dt.load_reports(file_path=valid_file)), 1)

        self.assertEqual(dt.load_reports(file_path="bad\x00.json"), [])
        self.assertEqual(dt.query_defects(file_path="bad\x00.json"), [])
        self.assertEqual(
            dt.get_statistics(file_path="bad\x00.json"),
            {
                "total_filtered_defects": 0,
                "critical_defect_count": 0,
                "avg_negativity_score": 0.0,
                "category_distribution": {},
            },
        )
        # Existing valid cache remains intact
        self.assertEqual(len(dt.load_reports(file_path=valid_file)), 1)

    def test_whitespace_primary_fields_fallback_and_mapping_support(self) -> None:
        """Whitespace-only brand/model/severity fields fall back to secondary keys, including on MappingProxyType."""
        records = [
            MappingProxyType(
                {
                    "id": "m1",
                    "defect_category": "ICCU",
                    "vehicle_brand": "   ",
                    "brand": "Hyundai",
                    "vehicle_model": "\t ",
                    "model": "IONIQ 5",
                    "severity": "   ",
                    "severity_tier": "CRITICAL",
                    "title": "ICCU warning",
                }
            )
        ]
        dt = DefectTracker(root_data_dir=self.test_dir, web_data_dir=self.test_dir)
        res = dt.query_defects(
            vehicle_brand="hyundai",
            vehicle_model="ioniq 5",
            min_severity=8.0,
            reports=records,
        )
        self.assertEqual([r["id"] for r in res], ["m1"])

        report_file = self.test_dir / "ws_sev.json"
        report_file.write_text(
            json.dumps(
                {
                    "reports": [
                        {
                            "id": "s1",
                            "defect_category": "ICCU",
                            "severity_tier": "   ",
                            "severity": "CRITICAL",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        stats = dt.get_statistics(file_path=report_file)
        self.assertEqual(stats["critical_defect_count"], 1)

    def test_unicode_nfd_nfc_hangul_query_matching(self) -> None:
        """query_defects matches Hangul regardless of NFD vs NFC normalization."""
        nfc_brand = "현대"
        nfd_brand = unicodedata.normalize("NFD", nfc_brand)
        nfc_model = "아이오닉5"
        nfd_model = unicodedata.normalize("NFD", nfc_model)
        nfc_cat = "배터리"
        nfd_cat = unicodedata.normalize("NFD", nfc_cat)
        nfc_kw = "충전불가"
        nfd_kw = unicodedata.normalize("NFD", nfc_kw)

        report_file = self.test_dir / "hangul_nfd.json"
        report_file.write_text(
            json.dumps(
                {
                    "reports": [
                        {
                            "id": "h1",
                            "defect_category": nfd_cat,
                            "vehicle_brand": nfd_brand,
                            "vehicle_model": nfd_model,
                            "title": f"급속 {nfd_kw} 증상",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        dt = DefectTracker(root_data_dir=self.test_dir, web_data_dir=self.test_dir)
        res = dt.query_defects(
            category=nfc_cat,
            vehicle_brand=nfc_brand,
            vehicle_model=nfc_model,
            keyword=nfc_kw,
            file_path=report_file,
        )
        self.assertEqual([r["id"] for r in res], ["h1"])

    def test_get_statistics_normalizes_negative_zero_avg(self) -> None:
        """get_statistics normalizes -0.0 avg_negativity_score to +0.0."""
        precomputed_file = self.test_dir / "precomputed_neg_zero.json"
        precomputed_file.write_text(
            json.dumps(
                {
                    "reports": [{"id": "1", "defect_category": "BATTERY"}],
                    "statistics": {
                        "total_filtered_defects": 1,
                        "critical_defect_count": 0,
                        "avg_negativity_score": -0.001,
                    },
                }
            ),
            encoding="utf-8",
        )
        computed_file = self.test_dir / "computed_neg_zero.json"
        computed_file.write_text(
            json.dumps(
                {
                    "reports": [
                        {"id": "1", "defect_category": "BATTERY", "negativity_score": -0.001},
                    ]
                }
            ),
            encoding="utf-8",
        )

        dt = DefectTracker(root_data_dir=self.test_dir, web_data_dir=self.test_dir)
        s1 = dt.get_statistics(file_path=precomputed_file)
        s2 = dt.get_statistics(file_path=computed_file)
        self.assertEqual(s1["avg_negativity_score"], 0.0)
        self.assertEqual(s2["avg_negativity_score"], 0.0)
        self.assertGreater(math.copysign(1.0, s1["avg_negativity_score"]), 0.0)
        self.assertGreater(math.copysign(1.0, s2["avg_negativity_score"]), 0.0)

    def test_whitespace_reports_file_and_web_dir_ignored(self) -> None:
        """Whitespace-only reports_file and web_dir do not resolve to '.' directory."""
        root_dir = self.test_dir / "root_data"
        web_dir = self.test_dir / "web_data"
        root_dir.mkdir(parents=True, exist_ok=True)
        web_dir.mkdir(parents=True, exist_ok=True)

        (root_dir / "daily_reports.json").write_text(
            json.dumps({"reports": [{"id": "1", "defect_category": "BATTERY"}]}),
            encoding="utf-8",
        )
        dt = DefectTracker(root_data_dir=root_dir, web_data_dir=web_dir, reports_file="   ")
        self.assertIsNone(dt.reports_file)
        written = dt.sync_defect_reports(web_dir="   ")
        self.assertEqual(written, [str(web_dir / "daily_reports.json")])


if __name__ == "__main__":
    unittest.main()
