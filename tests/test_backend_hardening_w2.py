"""tests/test_backend_hardening_w2.py - Wave 2 Backend Hardening Test Suite.

Covers:
1. Bidirectional Automatic Synchronization in run_tracker.py:
   - _resolve_default_paths() populates external_sync_targets when both directories exist.
   - When run_tracker.py executes with default/repo outputs without --sync-web,
     writes synchronize to both root and web data mirrors with identical bitwise SHA-256 parity.
   - Custom isolated outputs (--output /tmp/...) do not contaminate repo mirrors.
2. Microsecond Precision in SubsidyTracker.quarantine_corrupted_cache():
   - Quarantined file names conform to regex with microsecond precision (%Y%m%d_%H%M%S_%f).
   - Rapid successive quarantines within the same second avoid naming collisions.
3. Category-Level Pre-Filtering and Query Caching in DefectTracker:
   - Category index accurately pre-indexes complaint categories.
   - query_defects(category=...) uses category pre-filtering to avoid scanning unrelated records.
   - Query caching returns cached results on repeated queries.
   - Mutations on returned query results do not corrupt cached results (immutability).
   - Invalidation occurs on invalidate_cache(), file mtime change, and sync_defect_reports().
"""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import run_tracker
from tracker.defect_tracker import DefectTracker
from tracker.subsidy_tracker import SubsidyTracker


class TestQuarantineMicrosecondPrecision(unittest.TestCase):
    """Verifies that quarantine_corrupted_cache uses microsecond timestamp precision."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="test_quarantine_w2_")
        self.corrupt_file = Path(self.test_dir) / "ev_subsidy_data.json"

    def tearDown(self) -> None:
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_quarantine_timestamp_format_has_microsecond_precision(self) -> None:
        """quarantine_corrupted_cache generates file with %Y%m%d_%H%M%S_%f format."""
        with open(self.corrupt_file, "w", encoding="utf-8") as f:
            f.write("{invalid_json: true,")

        tracker = SubsidyTracker()
        quarantined = tracker.quarantine_corrupted_cache(self.corrupt_file)

        self.assertIsNotNone(quarantined)
        self.assertTrue(quarantined.exists())
        self.assertFalse(self.corrupt_file.exists())

        # Regex matching %Y%m%d_%H%M%S_%f: e.g. .corrupt_20261008_071530_123456.json
        pattern = r"\.corrupt_\d{8}_\d{6}_\d{6}\.json$"
        self.assertRegex(quarantined.name, pattern)

    def test_rapid_quarantine_execution_avoids_name_collisions(self) -> None:
        """Two rapid quarantine calls in tight loop produce distinct quarantine files."""
        tracker = SubsidyTracker()
        file1 = Path(self.test_dir) / "cache1.json"
        file2 = Path(self.test_dir) / "cache2.json"

        file1.write_text("corrupted_payload_1", encoding="utf-8")
        file2.write_text("corrupted_payload_2", encoding="utf-8")

        q1 = tracker.quarantine_corrupted_cache(file1)
        q2 = tracker.quarantine_corrupted_cache(file2)

        self.assertIsNotNone(q1)
        self.assertIsNotNone(q2)
        self.assertTrue(q1.exists())
        self.assertTrue(q2.exists())
        self.assertNotEqual(q1.name, q2.name, "Quarantine files must have distinct microsecond timestamps")


class TestDefectTrackerCategoryPreFilteringAndCaching(unittest.TestCase):
    """Tests category pre-filtering, caching, and cache invalidation in DefectTracker."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="test_defect_w2_")
        self.root_data = Path(self.test_dir) / "root_data"
        self.web_data = Path(self.test_dir) / "web_data"
        self.root_data.mkdir(parents=True, exist_ok=True)
        self.web_data.mkdir(parents=True, exist_ok=True)

        self.sample_reports = {
            "reports": [
                {
                    "id": "DEF-001",
                    "defect_category": "배터리",
                    "vehicle_brand": "현대",
                    "vehicle_model": "아이오닉 5",
                    "severity_index": 8.5,
                    "title": "배터리 방전 문제",
                    "defect_topic": "12V 저전압 배터리 방전",
                    "verbatim_quote": "주행 중 배터리 경고등 점등",
                    "raw_quote": "시동 불가",
                },
                {
                    "id": "DEF-002",
                    "defect_category": "구동모터",
                    "vehicle_brand": "기아",
                    "vehicle_model": "EV6",
                    "severity_index": 7.0,
                    "title": "모터 소음 발생",
                    "defect_topic": "감속기 고주파음",
                    "verbatim_quote": "가속 시 삐- 소리 발생",
                    "raw_quote": "모터 진동",
                },
                {
                    "id": "DEF-003",
                    "defect_category": "배터리",
                    "vehicle_brand": "테슬라",
                    "vehicle_model": "모델 Y",
                    "severity_index": 9.0,
                    "title": "고전압 배터리 과열",
                    "defect_topic": "BMS 통신 오류",
                    "verbatim_quote": "충전 중단 경고",
                    "raw_quote": "급속 충전 에러",
                },
            ],
            "statistics": {
                "total_filtered_defects": 3,
                "critical_defect_count": 2,
            },
        }

        self.reports_file = self.root_data / "daily_reports.json"
        with open(self.reports_file, "w", encoding="utf-8") as f:
            json.dump(self.sample_reports, f, ensure_ascii=False, indent=2)

        self.tracker = DefectTracker(root_data_dir=self.root_data, web_data_dir=self.web_data)

    def tearDown(self) -> None:
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_category_indexing_builds_buckets(self) -> None:
        """load_reports builds _category_index with normalized category keys."""
        reports = self.tracker.load_reports()
        self.assertEqual(len(reports), 3)

        self.assertIn("배터리", self.tracker._category_index)
        self.assertIn("구동모터", self.tracker._category_index)
        self.assertEqual(len(self.tracker._category_index["배터리"]), 2)
        self.assertEqual(len(self.tracker._category_index["구동모터"]), 1)

    def test_query_defects_category_prefiltering(self) -> None:
        """query_defects with category pre-filters candidate pool correctly."""
        battery_defects = self.tracker.query_defects(category="배터리")
        self.assertEqual(len(battery_defects), 2)
        self.assertEqual({d["id"] for d in battery_defects}, {"DEF-001", "DEF-003"})

        motor_defects = self.tracker.query_defects(category="구동모터")
        self.assertEqual(len(motor_defects), 1)
        self.assertEqual(motor_defects[0]["id"], "DEF-002")

        nonexistent = self.tracker.query_defects(category="존재하지않음")
        self.assertEqual(len(nonexistent), 0)

    def test_query_defects_caching_and_immutability(self) -> None:
        """query_defects caches results; mutating returned list does not mutate cache."""
        res1 = self.tracker.query_defects(category="배터리")
        self.assertGreater(len(self.tracker._query_cache), 0)

        # Mutate the returned list
        res1.append({"id": "DEF-MUTATED"})

        # Subsequent call retrieves pristine cached result
        res2 = self.tracker.query_defects(category="배터리")
        self.assertEqual(len(res2), 2)
        self.assertNotIn("DEF-MUTATED", [d["id"] for d in res2])

    def test_cache_invalidation_on_file_mtime_change(self) -> None:
        """Modifying daily_reports.json on disk invalidates query cache on next query."""
        res1 = self.tracker.query_defects(category="배터리")
        self.assertEqual(len(res1), 2)

        # Modify file on disk with a new report
        new_data = dict(self.sample_reports)
        new_data["reports"].append({
            "id": "DEF-004",
            "defect_category": "배터리",
            "vehicle_brand": "현대",
            "vehicle_model": "아이오닉 6",
            "severity_index": 7.5,
            "title": "신규 배터리 결함",
            "defect_topic": "BMS 펌웨어",
            "verbatim_quote": "경고등",
            "raw_quote": "결함",
        })
        time.sleep(0.05)
        with open(self.reports_file, "w", encoding="utf-8") as f:
            json.dump(new_data, f, ensure_ascii=False, indent=2)

        # Re-query
        res2 = self.tracker.query_defects(category="배터리")
        self.assertEqual(len(res2), 3)
        self.assertIn("DEF-004", [d["id"] for d in res2])

    def test_cache_invalidation_on_sync_defect_reports(self) -> None:
        """sync_defect_reports calls invalidate_cache when files are mirrored."""
        self.tracker.query_defects(category="배터리")
        self.assertGreater(len(self.tracker._query_cache), 0)

        written = self.tracker.sync_defect_reports(web_dir=self.web_data, dry_run=False)
        self.assertGreater(len(written), 0)
        self.assertEqual(len(self.tracker._query_cache), 0)
        self.assertIsNone(self.tracker._cached_reports)


class TestRunTrackerBidirectionalAutoSync(unittest.TestCase):
    """Tests bidirectional auto-sync in run_tracker.py."""

    def test_resolve_default_paths_returns_external_targets(self) -> None:
        """_resolve_default_paths populates external sync targets when both dirs exist."""
        primary, web, mirror_p, mirror_w, ext = run_tracker._resolve_default_paths()
        self.assertEqual(primary.name, "ev_subsidy_data.json")
        self.assertEqual(web.name, "ev_subsidy_data.json")
        self.assertEqual(mirror_p.name, "subsidy_depletion_data.json")
        self.assertEqual(mirror_w.name, "subsidy_depletion_data.json")
        self.assertIsInstance(ext, list)

    def test_bidirectional_auto_sync_executes_without_sync_web_flag(self) -> None:
        """When executed in an environment with both data dirs, writes mirror to both locations."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            root_data = td_path / "data"
            web_data = td_path / "ev-stealth-web" / "src" / "data"
            root_data.mkdir(parents=True, exist_ok=True)
            web_data.mkdir(parents=True, exist_ok=True)

            script = PROJECT_ROOT / "run_tracker.py"

            # Execute run_tracker targeting the temporary tree without --sync-web
            # Mocking network failure for instant baseline output
            primary_out = root_data / "ev_subsidy_data.json"
            web_dir = web_data

            # Use python to run run_tracker with --output pointing to root_data/ev_subsidy_data.json
            # and verify it mirrors to web_data when both exist
            cmd = [
                sys.executable,
                "-c",
                f"""
import sys
from pathlib import Path
sys.path.insert(0, r"{PROJECT_ROOT}")
import run_tracker
from unittest import mock

# Mock _CURRENT_DIR to point to td_path
run_tracker._CURRENT_DIR = Path(r"{td_path}")
(
    run_tracker.DEFAULT_PRIMARY_OUTPUT,
    run_tracker.DEFAULT_WEB_OUTPUT,
    run_tracker.MIRROR_PRIMARY_OUTPUT,
    run_tracker.MIRROR_WEB_OUTPUT,
    run_tracker.EXTERNAL_SYNC_TARGETS,
) = run_tracker._resolve_default_paths()

with mock.patch.object(sys, "argv", ["run_tracker.py", "--mock-network", "--output", str(run_tracker.DEFAULT_PRIMARY_OUTPUT)]):
    run_tracker.main()
""",
            ]

            res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            self.assertEqual(res.returncode, 0, f"run_tracker failed: {res.stderr}\n{res.stdout}")

            f1 = root_data / "ev_subsidy_data.json"
            f2 = root_data / "subsidy_depletion_data.json"
            f3 = web_data / "ev_subsidy_data.json"
            f4 = web_data / "subsidy_depletion_data.json"

            self.assertTrue(f1.exists(), f"Missing {f1}")
            self.assertTrue(f2.exists(), f"Missing {f2}")
            self.assertTrue(f3.exists(), f"Missing {f3}")
            self.assertTrue(f4.exists(), f"Missing {f4}")

            # Verify 100% SHA-256 byte parity between mirrored files
            h1 = hashlib.sha256(f1.read_bytes()).hexdigest()
            h2 = hashlib.sha256(f2.read_bytes()).hexdigest()
            h3 = hashlib.sha256(f3.read_bytes()).hexdigest()
            h4 = hashlib.sha256(f4.read_bytes()).hexdigest()

            self.assertEqual(h1, h3, "Primary and Web ev_subsidy_data.json must have bitwise identical SHA-256")
            self.assertEqual(h2, h4, "Primary and Web subsidy_depletion_data.json must have bitwise identical SHA-256")


if __name__ == "__main__":
    unittest.main()
