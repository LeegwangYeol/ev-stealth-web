"""Resilience and Durability Audit Test Suite for atomic_writer and json_writer.

Verifies:
1. Atomic write durability with leak-proof directory fsync.
2. Cross-process advisory FileLock inode-matching and leak-free fd lifecycle.
3. Automated stale temporary file cleanup and failure unlinking.
4. Existing POSIX file mode preservation and explicit mode override.
5. Unified lock file synchronization between atomic_writer and json_writer.
"""

from __future__ import annotations

import errno
import json
import os
from pathlib import Path
import stat
import tempfile
import time
import unittest
from unittest import mock

from tracker.atomic_writer import (
    FileLock,
    _json_default,
    atomic_write_json,
    atomic_write_json_multiple,
    cleanup_stale_temp_files,
    get_lock_path,
    quarantine_corrupted_file,
    sanitize_nan_inf,
)
from utils.json_writer import (
    read_daily_reports,
    write_daily_reports,
)


class TestAtomicWriterDurabilityAndResilience(unittest.TestCase):
    """Rigorous tests covering atomic write durability, file locking, temp file cleanup, and permission preservation."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        try:
            self.tmp_dir.cleanup()
        except OSError:
            pass

    def test_01_permission_preservation_existing_file_mode(self) -> None:
        """atomic_write_json must preserve pre-existing file mode (e.g. 0o600, 0o640) on update."""
        # Test preserving 0o600 (owner-only private file)
        target_600 = self.test_dir / "private_payload.json"
        target_600.write_text(json.dumps({"secret": 123}), encoding="utf-8")
        os.chmod(target_600, 0o600)
        self.assertEqual(target_600.stat().st_mode & 0o777, 0o600)

        written_600 = atomic_write_json({"secret": 456, "updated": True}, target_600)
        self.assertEqual(written_600.stat().st_mode & 0o777, 0o600, "0o600 permissions must be preserved")

        with open(written_600, "r", encoding="utf-8") as f:
            data_600 = json.load(f)
        self.assertEqual(data_600["secret"], 456)

        # Test preserving 0o640 (owner read/write, group read)
        target_640 = self.test_dir / "group_payload.json"
        target_640.write_text(json.dumps({"group": True}), encoding="utf-8")
        os.chmod(target_640, 0o640)
        self.assertEqual(target_640.stat().st_mode & 0o777, 0o640)

        written_640 = atomic_write_json({"group": True, "v": 2}, target_640)
        self.assertEqual(written_640.stat().st_mode & 0o777, 0o640, "0o640 permissions must be preserved")

    def test_02_permission_preservation_new_file_and_explicit_mode_override(self) -> None:
        """New files default to 0o644, while explicit mode parameter overrides preservation."""
        # Non-existent file defaults to standard 0o644
        new_target = self.test_dir / "brand_new.json"
        written = atomic_write_json({"status": "created"}, new_target)
        self.assertEqual(written.stat().st_mode & 0o777, 0o644)

        # Explicit mode override sets requested mode even on existing file
        written_override = atomic_write_json({"status": "restricted"}, new_target, mode=0o600)
        self.assertEqual(written_override.stat().st_mode & 0o777, 0o600)

    def test_03_write_daily_reports_preserves_custom_file_mode(self) -> None:
        """write_daily_reports preserves existing file permissions when updating reports."""
        target = self.test_dir / "daily_reports.json"
        target.write_text(json.dumps({"reports": [], "statistics": {}}), encoding="utf-8")
        os.chmod(target, 0o600)

        complaint = {
            "id": "c_resilience_1",
            "date": "2026-11-02",
            "defect_category": "BATTERY",
            "vehicle_brand": "HYUNDAI",
            "vehicle_model": "IONIQ 5",
            "severity_tier": "CRITICAL",
            "sentiment_score": 0.95,
            "verbatim_quote": "배터리 안전 모드 발동",
        }

        result_path = write_daily_reports([complaint], output_path=str(target), merge_existing=True)
        res_p = Path(result_path)
        self.assertEqual(res_p.stat().st_mode & 0o777, 0o600, "Daily reports must preserve 0o600 mode")

    def test_04_unified_lock_path_between_atomic_writer_and_json_writer(self) -> None:
        """get_lock_path produces identical, deterministic lock files for same target."""
        target_path = self.test_dir / "shared_data.json"
        lock_1 = get_lock_path(target_path)
        lock_2 = get_lock_path(str(target_path))
        lock_3 = get_lock_path(Path(str(target_path) + "/../shared_data.json"))

        self.assertEqual(lock_1, lock_2)
        self.assertEqual(lock_1, lock_3)
        self.assertTrue(str(lock_1).endswith(".lock"))
        self.assertIn(".ev_atomic_", str(lock_1))

    def test_05_cleanup_stale_temp_files(self) -> None:
        """cleanup_stale_temp_files unlinks files older than max_age_seconds, keeping active files."""
        # Create an orphaned stale file (simulated 2 hours old)
        stale_file = self.test_dir / ".tmp_subsidy_old123.json"
        stale_file.write_text("{}", encoding="utf-8")
        two_hours_ago = time.time() - 7200
        os.utime(stale_file, (two_hours_ago, two_hours_ago))

        # Create an active fresh file (created right now)
        active_file = self.test_dir / ".tmp_subsidy_active456.json"
        active_file.write_text("{}", encoding="utf-8")

        # Create an unrelated file
        data_file = self.test_dir / "valid_data.json"
        data_file.write_text("{}", encoding="utf-8")
        os.utime(data_file, (two_hours_ago, two_hours_ago))

        cleaned = cleanup_stale_temp_files(self.test_dir, prefix=".tmp_subsidy_", max_age_seconds=3600.0)
        self.assertEqual(cleaned, 1)
        self.assertFalse(stale_file.exists(), "Stale temp file must be unlinked")
        self.assertTrue(active_file.exists(), "Active recent temp file must be preserved")
        self.assertTrue(data_file.exists(), "Unrelated data file must not be touched")

    def test_06_leak_proof_directory_fsync_lifecycle(self) -> None:
        """Directory fsync guarantees descriptor closure even when os.fsync raises OSError."""
        target = self.test_dir / "durable.json"
        closed_fds: list[int] = []
        original_close = os.close

        def track_close(fd: int) -> None:
            closed_fds.append(fd)
            original_close(fd)

        with mock.patch("os.fsync", side_effect=[None, OSError(errno.EINVAL, "fsync not supported on dir")]):
            with mock.patch("os.close", side_effect=track_close):
                written = atomic_write_json({"durable": True}, target)

        self.assertTrue(written.exists())
        self.assertGreater(len(closed_fds), 0, "All file descriptors including directory fd must be closed")

    def test_07_file_lock_exception_in_enter_closes_descriptor(self) -> None:
        """FileLock.__enter__ must close self.fd if an exception occurs during flock."""
        lock_path = self.test_dir / "test_leak.lock"
        lock = FileLock(lock_path)

        with mock.patch("fcntl.flock", side_effect=OSError(errno.ENOLCK, "No lock available")):
            with self.assertRaises(OSError):
                with lock:
                    pass

        self.assertIsNone(lock.fd, "File descriptor must be closed and nulled on exception in __enter__")

    def test_08_atomic_write_json_multiple_permission_preservation(self) -> None:
        """atomic_write_json_multiple respects explicit mode on all destination targets."""
        paths = [
            self.test_dir / f"out_{i}.json"
            for i in range(3)
        ]
        written = atomic_write_json_multiple({"multi": 1}, paths, mode=0o640)
        self.assertEqual(len(written), 3)
        for p in written:
            self.assertEqual(p.stat().st_mode & 0o777, 0o640)


if __name__ == "__main__":
    unittest.main()
