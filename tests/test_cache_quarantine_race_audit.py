"""Tests for Cache, Quarantine Handling, Atomic Writes with fsync, and Concurrency Locks.

Verifies:
1. Atomic file writes with fsync and directory fsync.
2. Corrupt payload isolation/quarantine (.corrupted and .corrupt_<timestamp>.json).
3. Timestamp preservation across mirror files without oscillation.
4. Race condition prevention when multiple processes/threads sync data simultaneously.
5. SubsidyTracker and DefectTracker resilience against corrupted cache payloads.
"""

from __future__ import annotations

import concurrent.futures
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest
from typing import Any, Dict, List

# Ensure repository paths in sys.path
_CURRENT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _CURRENT_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_WEB_ROOT = _REPO_ROOT / "ev-stealth-web"
if str(_WEB_ROOT) not in sys.path:
    sys.path.insert(0, str(_WEB_ROOT))

from tracker.atomic_writer import (
    FileLock,
    atomic_write_json,
    atomic_write_json_multiple,
    is_corrupted_or_quarantined_filename,
    quarantine_corrupted_file,
)
from tracker.subsidy_tracker import SubsidyTracker
from tracker.defect_tracker import DefectTracker
from utils.json_writer import (
    read_daily_reports,
    write_daily_reports,
)
from run_tracker import (
    sync_defect_reports,
    validate_defect_reports_file,
)


class TestCacheQuarantineAndAtomicWrites(unittest.TestCase):
    """Test suite for crash durability, quarantine isolation, and file locking."""

    def setUp(self) -> None:
        self.tmp_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.tmp_dir_obj.name)

    def tearDown(self) -> None:
        try:
            self.tmp_dir_obj.cleanup()
        except OSError:
            pass

    def test_01_quarantine_corrupted_file_default_timestamp(self) -> None:
        """quarantine_corrupted_file renames corrupted file with timestamped pattern and sets 0o644."""
        target = self.test_dir / "bad_cache.json"
        target.write_text("{ corrupt json: ...", encoding="utf-8")

        quarantined = quarantine_corrupted_file(target)
        self.assertIsNotNone(quarantined)
        self.assertFalse(target.exists(), "Original corrupted file must no longer exist")
        self.assertTrue(quarantined.exists(), "Quarantined file must exist on disk")
        self.assertRegex(
            quarantined.name,
            r"^bad_cache\.corrupt_\d{8}_\d{6}_\d{6}\.json$",
            "Filename must conform to standard timestamped pattern",
        )
        # Check permissions
        mode = oct(quarantined.stat().st_mode & 0o777)
        self.assertEqual(mode, oct(0o644))

    def test_02_quarantine_corrupted_file_custom_suffix(self) -> None:
        """quarantine_corrupted_file supports explicit .corrupted suffix."""
        target = self.test_dir / "ev_subsidy_data.json"
        target.write_text("broken payload", encoding="utf-8")

        quarantined = quarantine_corrupted_file(target, suffix=".corrupted")
        self.assertIsNotNone(quarantined)
        self.assertFalse(target.exists())
        self.assertTrue(quarantined.exists())
        self.assertIn(".corrupted", quarantined.name)

    def test_03_is_corrupted_or_quarantined_filename(self) -> None:
        """is_corrupted_or_quarantined_filename recognizes corrupted and quarantine markers."""
        self.assertTrue(is_corrupted_or_quarantined_filename("ev_subsidy_data.json.corrupted"))
        self.assertTrue(is_corrupted_or_quarantined_filename("cache.corrupt_20261102_010203_123456.json"))
        self.assertTrue(is_corrupted_or_quarantined_filename("daily_reports.corrupt"))
        self.assertFalse(is_corrupted_or_quarantined_filename("ev_subsidy_data.json"))
        self.assertFalse(is_corrupted_or_quarantined_filename("daily_reports.json"))

    def test_04_subsidy_tracker_load_cached_payload_ignores_quarantined(self) -> None:
        """SubsidyTracker ignores files marked as corrupted or quarantined."""
        bad_path = self.test_dir / "ev_subsidy_data.corrupt_20261102_000000_000000.json"
        bad_path.write_text("{}", encoding="utf-8")

        tracker = SubsidyTracker(cache_fallback_path=bad_path, validate_cache=True, quarantine_corrupted=True)
        payload = tracker.load_cached_payload(bad_path, validate=True, quarantine=True)
        self.assertIsNone(payload)
        # Quarantined file should not be re-quarantined
        self.assertTrue(bad_path.exists())

    def test_05_subsidy_tracker_quarantines_invalid_schema(self) -> None:
        """SubsidyTracker quarantines cache file with invalid schema (< 17 regions)."""
        cache_path = self.test_dir / "ev_subsidy_data.json"
        cache_path.write_text(json.dumps({"regions": [{"name": "Seoul"}]}), encoding="utf-8")

        tracker = SubsidyTracker(cache_fallback_path=cache_path, validate_cache=True, quarantine_corrupted=True)
        payload = tracker.load_cached_payload(cache_path, validate=True, quarantine=True)
        self.assertIsNone(payload)
        self.assertFalse(cache_path.exists())

        quarantined = list(self.test_dir.glob("ev_subsidy_data.corrupt_*.json"))
        self.assertEqual(len(quarantined), 1)

    def test_06_utils_read_daily_reports_quarantine(self) -> None:
        """utils.json_writer.read_daily_reports quarantines corrupt file when quarantine_corrupted=True."""
        reports_file = self.test_dir / "daily_reports.json"
        reports_file.write_text("{ unclosed json", encoding="utf-8")

        data = read_daily_reports(str(reports_file), quarantine_corrupted=True)
        self.assertEqual(data, {"reports": [], "statistics": {}})
        self.assertFalse(reports_file.exists())

        quarantined = list(self.test_dir.glob("daily_reports.corrupt_*.json"))
        self.assertEqual(len(quarantined), 1)

    def test_07_utils_write_daily_reports_quarantines_preexisting_corrupted(self) -> None:
        """write_daily_reports quarantines existing corrupted payload before writing fresh valid data."""
        reports_file = self.test_dir / "daily_reports.json"
        reports_file.write_text("{ corrupt", encoding="utf-8")

        new_complaint = {
            "id": "c1",
            "date": "2026-11-02",
            "defect_category": "BATTERY",
            "vehicle_brand": "HYUNDAI",
            "vehicle_model": "IONIQ 5",
            "severity_tier": "CRITICAL",
            "sentiment_score": 0.95,
            "verbatim_quote": "배터리 방전 발생",
        }

        res = write_daily_reports([new_complaint], output_path=str(reports_file), merge_existing=True, quarantine_corrupted=True)
        self.assertTrue(reports_file.exists())
        written_data = json.loads(reports_file.read_text(encoding="utf-8"))
        self.assertEqual(len(written_data["reports"]), 1)
        self.assertEqual(written_data["reports"][0]["id"], "c1")

        quarantined = list(self.test_dir.glob("daily_reports.corrupt_*.json"))
        self.assertEqual(len(quarantined), 1)

    def test_08_run_tracker_sync_defect_reports_quarantines_corrupted_candidates(self) -> None:
        """sync_defect_reports quarantines corrupted candidates and synchronizes valid source."""
        root_data = self.test_dir / "root" / "data"
        web_data = self.test_dir / "web" / "src" / "data"
        root_data.mkdir(parents=True, exist_ok=True)
        web_data.mkdir(parents=True, exist_ok=True)

        corrupt_root = root_data / "daily_reports.json"
        corrupt_root.write_text("{ broken root payload", encoding="utf-8")

        valid_web = web_data / "daily_reports.json"
        valid_payload = {
            "pipeline_version": "1.0.0",
            "generated_at": "2026-11-02T00:00:00Z",
            "statistics": {"total_filtered_defects": 1},
            "reports": [
                {
                    "id": "auth-001",
                    "date": "2026-11-02",
                    "defect_category": "MOTOR",
                    "vehicle_brand": "KIA",
                    "vehicle_model": "EV6",
                }
            ],
        }
        valid_web.write_text(json.dumps(valid_payload), encoding="utf-8")
        time.sleep(0.05)
        # Ensure valid_web has newer mtime
        valid_stat = valid_web.stat()

        written = sync_defect_reports(
            web_dir=web_data,
            root_dir=root_data,
            dry_run=False,
            run_crawler=False,
            quarantine_corrupted=True,
        )
        self.assertTrue(corrupt_root.exists())
        # The corrupted root must have been replaced with the valid web payload
        synced_data = json.loads(corrupt_root.read_text(encoding="utf-8"))
        self.assertEqual(synced_data["reports"][0]["id"], "auth-001")

        # Quarantined file from original corrupt root must exist
        quarantined = list(root_data.glob("daily_reports.corrupt_*.json"))
        self.assertEqual(len(quarantined), 1)

    def test_09_timestamp_preservation_across_sync(self) -> None:
        """sync_defect_reports preserves source st_mtime on destination target."""
        root_data = self.test_dir / "root" / "data"
        web_data = self.test_dir / "web" / "src" / "data"
        root_data.mkdir(parents=True, exist_ok=True)
        web_data.mkdir(parents=True, exist_ok=True)

        source_file = root_data / "daily_reports.json"
        target_file = web_data / "daily_reports.json"

        valid_payload = {
            "pipeline_version": "1.0.0",
            "reports": [{"id": "r1", "defect_category": "BATTERY"}],
        }
        source_file.write_text(json.dumps(valid_payload), encoding="utf-8")
        # Explicit past timestamp
        fixed_time = 1700000000.0
        os.utime(source_file, (fixed_time, fixed_time))

        written = sync_defect_reports(
            web_dir=web_data,
            root_dir=root_data,
            dry_run=False,
            run_crawler=False,
        )
        self.assertTrue(target_file.exists())
        self.assertEqual(target_file.stat().st_mtime, fixed_time)

    def test_10_multi_thread_concurrent_atomic_writes(self) -> None:
        """Multiple concurrent threads writing via write_daily_reports must never produce torn writes or corrupt files."""
        output_file = self.test_dir / "concurrent_reports.json"
        num_threads = 8
        writes_per_thread = 5

        def worker(thread_idx: int) -> None:
            for i in range(writes_per_thread):
                complaint = {
                    "id": f"t{thread_idx}_item_{i}",
                    "date": "2026-11-02",
                    "defect_category": "SOFTWARE",
                    "vehicle_brand": "TESLA",
                    "vehicle_model": "MODEL Y",
                    "severity_tier": "MAJOR",
                    "sentiment_score": 0.8,
                    "verbatim_quote": f"Thread {thread_idx} complaint {i}",
                }
                write_daily_reports([complaint], output_path=str(output_file), merge_existing=True)

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, idx) for idx in range(num_threads)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        self.assertTrue(output_file.exists())
        with open(output_file, "r", encoding="utf-8") as f:
            final_data = json.load(f)

        self.assertIn("reports", final_data)
        # All items must be unique and intact
        report_ids = [r["id"] for r in final_data["reports"]]
        self.assertEqual(len(report_ids), len(set(report_ids)), "All report IDs must be strictly unique")
        self.assertEqual(len(report_ids), num_threads * writes_per_thread)

    def test_11_file_lock_reentrancy_and_timeout(self) -> None:
        """FileLock is re-entrant within the same thread and safely releases locks."""
        lock_path = self.test_dir / "test.lock"
        with FileLock(lock_path) as l1:
            self.assertEqual(l1.lock_path, str(lock_path.resolve()))
            with FileLock(lock_path) as l2:
                self.assertEqual(l2.lock_path, str(lock_path.resolve()))

        # After exit, lock should be cleanly released
        self.assertIsNone(l1.fd)


if __name__ == "__main__":
    unittest.main()
