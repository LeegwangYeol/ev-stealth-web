"""Test suite verifying tracker audit hardening.

Covers:
1. File locking race conditions, stale locks handling, and metadata tracking.
2. Safe JSON loading (UTF-8 BOM support) and quarantine logic.
3. Path resolution consistency across root repo and ev-stealth-web subdirectory.
"""

from __future__ import annotations

import errno
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

# Ensure repository paths are present in sys.path
_CURRENT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _CURRENT_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_WEB_ROOT = _REPO_ROOT / "ev-stealth-web"
if str(_WEB_ROOT) not in sys.path:
    sys.path.insert(0, str(_WEB_ROOT))

from tracker.atomic_writer import (
    FileLock,
    cleanup_stale_lock_files,
    cleanup_stale_temp_files,
    is_pid_alive,
    read_lock_metadata,
)
from tracker.defect_tracker import DefectTracker
from tracker.subsidy_models import SubsidyPayload
from tracker.subsidy_tracker import SubsidyTracker, _find_repo_root, export_models_subsidy_matrix
from run_tracker import (
    _find_repo_root as run_tracker_find_repo_root,
    _resolve_default_paths,
    validate_defect_reports_file,
)


class TestTrackerHardeningAudit(unittest.TestCase):
    """Rigorous audit tests for locking, safe JSON loading, quarantine, and path resolution."""

    def setUp(self) -> None:
        self.tmp_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.tmp_dir_obj.name)

    def tearDown(self) -> None:
        try:
            self.tmp_dir_obj.cleanup()
        except OSError:
            pass

    # =========================================================================
    # DOMAIN 1: File locking race conditions & stale locks handling
    # =========================================================================

    def test_01_file_lock_metadata_and_properties(self) -> None:
        """FileLock records PID & timestamp on acquire and clears on exit; is_locked and acquired work."""
        lock_path = self.test_dir / "meta_test.lock"
        lock = FileLock(lock_path)
        self.assertFalse(lock.is_locked)
        self.assertFalse(lock.acquired)

        with lock:
            self.assertTrue(lock.is_locked)
            self.assertTrue(lock.acquired)
            self.assertIsNotNone(lock.fd)
            pid, ts = read_lock_metadata(lock_path)
            self.assertEqual(pid, os.getpid())
            self.assertIsNotNone(ts)
            self.assertLessEqual(abs(time.time() - ts), 5.0)

        self.assertFalse(lock.is_locked)
        self.assertFalse(lock.acquired)
        self.assertIsNone(lock.fd)

    def test_02_file_lock_reentrancy_depth(self) -> None:
        """FileLock supports nested re-entrancy within the same thread maintaining single active lock."""
        lock_path = self.test_dir / "reentrant.lock"
        with FileLock(lock_path) as l1:
            self.assertTrue(l1.acquired)
            with FileLock(lock_path) as l2:
                self.assertTrue(l2.acquired)
                self.assertEqual(l1.fd, l2.fd)
            # Still locked on outer level
            self.assertTrue(l1.is_locked)
        self.assertFalse(l1.is_locked)

    def test_03_file_lock_breaks_stale_lock_from_dead_pid(self) -> None:
        """FileLock detects and breaks a stale lock held by a dead PID."""
        lock_path = self.test_dir / "dead_pid.lock"
        # Write metadata pointing to a guaranteed non-existent PID (9999999)
        dead_pid = 9999999
        self.assertFalse(is_pid_alive(dead_pid))
        lock_path.write_text(f"pid={dead_pid}\ntime={time.time() - 500}\n", encoding="utf-8")

        # When FileLock tries to acquire, it should notice the PID is dead and break the lock
        lock = FileLock(lock_path, timeout=2.0)
        with lock:
            self.assertTrue(lock.acquired)
            pid, ts = read_lock_metadata(lock_path)
            self.assertEqual(pid, os.getpid())

    def test_04_file_lock_breaks_expired_stale_lock_mtime(self) -> None:
        """FileLock detects and breaks an abandoned lock file older than stale_timeout."""
        lock_path = self.test_dir / "expired.lock"
        # Write an expired timestamp
        old_time = time.time() - 400.0
        lock_path.write_text(f"pid=1\ntime={old_time}\n", encoding="utf-8")
        os.utime(lock_path, (old_time, old_time))

        lock = FileLock(lock_path, timeout=2.0, stale_timeout=100.0)
        with lock:
            self.assertTrue(lock.acquired)
            pid, _ = read_lock_metadata(lock_path)
            self.assertEqual(pid, os.getpid())

    def test_05_file_lock_fail_on_timeout_flag(self) -> None:
        """FileLock raises TimeoutError when fail_on_timeout=True, and sets acquired=False when False."""
        lock_path = self.test_dir / "timeout_test.lock"

        # Mock fcntl.flock to simulate lock contention (EAGAIN)
        with mock.patch("fcntl.flock", side_effect=OSError(errno.EAGAIN, "Resource temporarily unavailable")):
            # With fail_on_timeout=True
            strict_lock = FileLock(lock_path, timeout=0.05, poll_interval=0.01, fail_on_timeout=True)
            with self.assertRaises(TimeoutError):
                with strict_lock:
                    pass

            # With fail_on_timeout=False (default defensive fallback)
            defensive_lock = FileLock(lock_path, timeout=0.05, poll_interval=0.01, fail_on_timeout=False)
            with defensive_lock:
                self.assertFalse(defensive_lock.acquired)

    def test_06_cleanup_stale_lock_files(self) -> None:
        """cleanup_stale_lock_files unlinks unheld lock files older than max_age_seconds."""
        old_lock = self.test_dir / ".ev_atomic_old123.lock"
        old_lock.write_text("", encoding="utf-8")
        old_time = time.time() - 7200.0
        os.utime(old_lock, (old_time, old_time))

        recent_lock = self.test_dir / ".ev_atomic_fresh.lock"
        recent_lock.write_text("", encoding="utf-8")

        cleaned = cleanup_stale_lock_files(self.test_dir, max_age_seconds=3600.0)
        self.assertEqual(cleaned, 1)
        self.assertFalse(old_lock.exists(), "Old unheld lock must be unlinked")
        self.assertTrue(recent_lock.exists(), "Fresh lock must be retained")

    def test_07_cleanup_stale_lock_files_preserves_held_locks(self) -> None:
        """cleanup_stale_lock_files never unlinks a lock file currently held by an active process."""
        held_lock_path = self.test_dir / ".sync_defect_reports.lock"
        old_time = time.time() - 7200.0

        with FileLock(held_lock_path):
            os.utime(held_lock_path, (old_time, old_time))
            cleaned = cleanup_stale_lock_files(self.test_dir, prefix=(".sync_",), max_age_seconds=3600.0)
            self.assertEqual(cleaned, 0)
            self.assertTrue(held_lock_path.exists(), "Held lock must NEVER be unlinked")

    # =========================================================================
    # DOMAIN 2: Safe JSON loading with try/except & quarantine logic
    # =========================================================================

    def test_08_validate_defect_reports_file_handles_utf8_bom(self) -> None:
        """validate_defect_reports_file successfully validates JSON with UTF-8 BOM."""
        bom_file = self.test_dir / "bom_reports.json"
        valid_payload = {
            "pipeline_version": "1.0.0",
            "reports": [{"id": "r1", "defect_category": "BATTERY"}],
        }
        # Write bytes with UTF-8 BOM
        bom_bytes = b"\xef\xbb\xbf" + json.dumps(valid_payload).encode("utf-8")
        bom_file.write_bytes(bom_bytes)

        self.assertTrue(validate_defect_reports_file(bom_file))

    def test_09_subsidy_tracker_load_cached_payload_handles_utf8_bom(self) -> None:
        """SubsidyTracker.load_cached_payload safely decodes cached snapshot with UTF-8 BOM."""
        cache_file = self.test_dir / "bom_cache.json"
        from tracker.subsidy_baseline import build_initial_baseline
        baseline = build_initial_baseline()
        bom_bytes = b"\xef\xbb\xbf" + json.dumps(baseline.to_dict()).encode("utf-8")
        cache_file.write_bytes(bom_bytes)

        tracker = SubsidyTracker(cache_fallback_path=cache_file, validate_cache=True)
        payload = tracker.load_cached_payload(cache_file, validate=True)
        self.assertIsNotNone(payload)
        self.assertGreaterEqual(len(payload.regions), 17)

    def test_10_defect_tracker_load_full_report_data_quarantines_corrupted(self) -> None:
        """DefectTracker.load_full_report_data quarantines corrupted files when quarantine_corrupted=True."""
        corrupt_file = self.test_dir / "corrupted_daily.json"
        corrupt_file.write_text("{ malformed: unclosed json", encoding="utf-8")

        tracker = DefectTracker(root_data_dir=self.test_dir, reports_file=corrupt_file)
        data = tracker.load_full_report_data(corrupt_file, quarantine_corrupted=True)

        self.assertEqual(data, {"reports": [], "statistics": {}})
        self.assertFalse(corrupt_file.exists(), "Original corrupted file must no longer exist")
        quarantined = list(self.test_dir.glob("corrupted_daily.corrupt_*.json"))
        self.assertEqual(len(quarantined), 1, "Quarantined snapshot must be created")

    def test_11_subsidy_models_from_json_robustness(self) -> None:
        """SubsidyPayload.from_json handles UTF-8 BOM bytes, strings, and raises ValueError on corrupted input."""
        from tracker.subsidy_baseline import build_initial_baseline
        sample_dict = build_initial_baseline().to_dict()
        raw_json = json.dumps(sample_dict)

        # 1. UTF-8 BOM bytes
        bom_bytes = b"\xef\xbb\xbf" + raw_json.encode("utf-8")
        p1 = SubsidyPayload.from_json(bom_bytes)
        self.assertGreaterEqual(len(p1.regions), 17)

        # 2. String with \ufeff prefix
        bom_str = "\ufeff" + raw_json
        p2 = SubsidyPayload.from_json(bom_str)
        self.assertGreaterEqual(len(p2.regions), 17)

        # 3. Malformed JSON raises ValueError with informative error
        with self.assertRaises(ValueError) as ctx:
            SubsidyPayload.from_json("{ corrupt json")
        self.assertIn("Failed to parse SubsidyPayload JSON", str(ctx.exception))

    # =========================================================================
    # DOMAIN 3: Path resolution consistency
    # =========================================================================

    def test_12_find_repo_root_consistency(self) -> None:
        """_find_repo_root consistently returns the canonical repository root from any working directory."""
        repo_root = _find_repo_root()
        self.assertTrue((repo_root / "data").is_dir())
        self.assertTrue((repo_root / "ev-stealth-web").is_dir())

        # run_tracker's repo root finder matches subsidy_tracker's
        rt_root = run_tracker_find_repo_root()
        self.assertEqual(repo_root.resolve(), rt_root.resolve())

    def test_13_subsidy_tracker_collect_and_save_canonical_paths(self) -> None:
        """SubsidyTracker.collect_and_save writes to valid canonical directories even when called in custom subfolder."""
        tracker = SubsidyTracker()
        custom_out = self.test_dir / "custom" / "ev_subsidy_data.json"

        # Execute tracking and save with explicit target
        payload = tracker.collect_and_save(output_path=custom_out, dry_run=False)
        self.assertIsNotNone(payload)
        self.assertTrue(custom_out.exists())
        # Parity mirror must also exist
        mirror_out = custom_out.parent / "subsidy_depletion_data.json"
        self.assertTrue(mirror_out.exists())

    def test_14_export_models_subsidy_matrix_canonical_resolution(self) -> None:
        """export_models_subsidy_matrix resolves target directories without creating rogue subdirs."""
        custom_target = self.test_dir / "models_dir"
        custom_target.mkdir(parents=True, exist_ok=True)

        written = export_models_subsidy_matrix(target_dirs=[custom_target])
        self.assertEqual(len(written), 1)
        self.assertTrue((custom_target / "models_subsidy_matrix.json").exists())

    def test_15_defect_tracker_initialization_path_resolution(self) -> None:
        """DefectTracker resolves canonical data directories without requiring cwd to be repo root."""
        dt = DefectTracker()
        self.assertTrue(dt.root_data_dir.is_dir())
        self.assertTrue(dt.web_data_dir.is_dir())
        self.assertEqual(dt.get_root_reports_path().name, "daily_reports.json")
        self.assertEqual(dt.get_web_reports_path().name, "daily_reports.json")


if __name__ == "__main__":
    unittest.main()
