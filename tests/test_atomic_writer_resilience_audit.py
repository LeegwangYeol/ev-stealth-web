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

    def test_09_cross_device_exdev_fallback_atomic_write(self) -> None:
        """atomic_write_json successfully falls back to copyfile when os.replace raises EXDEV."""
        target = self.test_dir / "exdev_target.json"
        original_replace = os.replace

        def mock_replace(src: str, dst: str) -> None:
            raise OSError(errno.EXDEV, "Cross-device link")

        with mock.patch("os.replace", side_effect=mock_replace):
            written = atomic_write_json({"cross_device": True, "value": 42}, target)

        self.assertTrue(written.exists())
        with open(written, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["cross_device"], True)
        self.assertEqual(data["value"], 42)

    def test_10_cross_device_exdev_fallback_quarantine_corrupted_file(self) -> None:
        """quarantine_corrupted_file falls back to copyfile when os.replace raises EXDEV."""
        corrupt_target = self.test_dir / "corrupted_payload.json"
        corrupt_target.write_text("{malformed json", encoding="utf-8")

        def mock_replace(src: str, dst: str) -> None:
            raise OSError(errno.EXDEV, "Cross-device link")

        with mock.patch("os.replace", side_effect=mock_replace):
            quarantined = quarantine_corrupted_file(corrupt_target)

        self.assertIsNotNone(quarantined)
        self.assertFalse(corrupt_target.exists(), "Original corrupted file must be unlinked")
        self.assertTrue(quarantined.exists(), "Quarantined file must exist")
        self.assertIn("corrupt_", quarantined.name)

    def test_11_disk_space_exhaustion_enospc_cleans_temp_file(self) -> None:
        """atomic_write_json cleanly catches ENOSPC and unlinks temporary file."""
        target = self.test_dir / "disk_full_test.json"
        target.write_text(json.dumps({"initial": "safe"}), encoding="utf-8")

        with mock.patch("os.fsync", side_effect=OSError(errno.ENOSPC, "No space left on device")):
            with self.assertRaises(OSError) as ctx:
                atomic_write_json({"update": "will_fail"}, target)
            self.assertEqual(ctx.exception.errno, errno.ENOSPC)

        # Original destination must remain uncorrupted
        with open(target, "r", encoding="utf-8") as f:
            intact_data = json.load(f)
        self.assertEqual(intact_data["initial"], "safe")

        # No orphaned temp files left in directory
        temp_files = list(self.test_dir.glob(".tmp_*"))
        self.assertEqual(len(temp_files), 0, "All temporary scratch files must be cleaned on ENOSPC")

    def test_12_windows_msvcrt_locking_fallback(self) -> None:
        """FileLock uses msvcrt.locking when fcntl is None (Windows environment)."""
        lock_path = self.test_dir / "windows_mock.lock"
        mock_msvcrt = mock.MagicMock()

        with mock.patch("tracker.atomic_writer.fcntl", None):
            with mock.patch("tracker.atomic_writer.msvcrt", mock_msvcrt):
                lock = FileLock(lock_path)
                with lock:
                    pass

        self.assertTrue(mock_msvcrt.locking.called)
        self.assertIsNone(lock.fd)

    def test_13_json_serialization_edge_cases_complex_nan_inf_uuid_bytes(self) -> None:
        """atomic_write_json correctly sanitizes complex numbers, NaNs, UUIDs, frozenset, and bytes."""
        import uuid
        test_uuid = uuid.uuid4()
        target = self.test_dir / "edge_cases.json"
        payload = {
            "complex_num": complex(3.0, 4.0),
            "complex_nan": complex(float("nan"), float("inf")),
            "uuid": test_uuid,
            "bytes_val": b"korean_\xec\x95\x88\xeb\x85\x95",
            "frozenset_val": frozenset([float("nan"), 10]),
            float("nan"): "nan_key_converted",
        }
        written = atomic_write_json(payload, target)
        with open(written, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["complex_num"], {"real": 3.0, "imag": 4.0})
        self.assertEqual(data["complex_nan"], {"real": 0.0, "imag": 0.0})
        self.assertEqual(data["uuid"], str(test_uuid))
        self.assertEqual(data["bytes_val"], "korean_안녕")
        self.assertIn(0.0, data["frozenset_val"])
        self.assertIn(10, data["frozenset_val"])
        self.assertIn("0.0", data)

    def test_14_circular_reference_detection_raises_value_error(self) -> None:
        """Circular references in dict or sequence structures raise ValueError instead of crashing."""
        # Dict self-cycle
        cyclic_dict: dict = {"name": "cycle"}
        cyclic_dict["self"] = cyclic_dict

        with self.assertRaises(ValueError) as ctx1:
            sanitize_nan_inf(cyclic_dict)
        self.assertIn("Circular reference detected", str(ctx1.exception))

        # List self-cycle
        cyclic_list: list = [1, 2]
        cyclic_list.append(cyclic_list)

        with self.assertRaises(ValueError) as ctx2:
            sanitize_nan_inf(cyclic_list)
        self.assertIn("Circular reference detected", str(ctx2.exception))

    def test_15_diamond_structure_no_false_circular_error(self) -> None:
        """Diamond DAG structures (shared child nodes) serialize successfully without false cycle error."""
        shared_child = {"leaf": 42, "nan_val": float("nan")}
        diamond_root = {
            "branch_a": shared_child,
            "branch_b": shared_child,
        }
        sanitized = sanitize_nan_inf(diamond_root)
        self.assertEqual(sanitized["branch_a"]["leaf"], 42)
        self.assertEqual(sanitized["branch_a"]["nan_val"], 0.0)
        self.assertEqual(sanitized["branch_b"]["leaf"], 42)
        self.assertEqual(sanitized["branch_b"]["nan_val"], 0.0)

    def test_16_read_daily_reports_empty_and_dir_handling(self) -> None:
        """read_daily_reports safely returns empty report dict for empty, whitespace, and directory paths."""
        self.assertEqual(read_daily_reports(""), {"reports": [], "statistics": {}})
        self.assertEqual(read_daily_reports("   "), {"reports": [], "statistics": {}})
        self.assertEqual(read_daily_reports(str(self.test_dir)), {"reports": [], "statistics": {}})

    def test_17_write_daily_reports_empty_path_validation(self) -> None:
        """write_daily_reports rejects empty or whitespace-only paths with ValueError."""
        with self.assertRaises(ValueError):
            write_daily_reports([], output_path="")
        with self.assertRaises(ValueError):
            write_daily_reports([], output_path="   ")

    def test_18_cleanup_stale_temp_files_with_multiple_prefixes(self) -> None:
        """cleanup_stale_temp_files cleans files with multiple prefixes (.tmp_, .tmp_daily_, .tmp_subsidy_)."""
        old_time = time.time() - 7200
        f1 = self.test_dir / ".tmp_old1.json"
        f1.write_text("{}", encoding="utf-8")
        os.utime(f1, (old_time, old_time))

        f2 = self.test_dir / ".tmp_daily_old2.json"
        f2.write_text("{}", encoding="utf-8")
        os.utime(f2, (old_time, old_time))

        f3 = self.test_dir / ".tmp_subsidy_old3.json"
        f3.write_text("{}", encoding="utf-8")
        os.utime(f3, (old_time, old_time))

        cleaned = cleanup_stale_temp_files(self.test_dir, max_age_seconds=3600.0)
        self.assertEqual(cleaned, 3)
        self.assertFalse(f1.exists())
        self.assertFalse(f2.exists())
        self.assertFalse(f3.exists())


if __name__ == "__main__":
    unittest.main()
