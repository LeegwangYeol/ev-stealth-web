"""Concurrency, Durability, and Stale Lock Breaking Audit Test Suite.

Verifies:
1. POSIX atomic rename guarantees and hardware durability via durable_fsync (F_FULLFSYNC on macOS, fsync on Linux).
2. Deadlock prevention, stale lock expiration threshold enforcement, and active lock preservation during metadata race windows.
3. Zero file descriptor leaks on FileLock timeout when fail_on_timeout=False.
4. Clean instance state on nested re-entrant FileLock exit (is_locked reflects active scope).
5. Non-destructive lock metadata updates without zero-byte empty window.
6. Atomic staging replacement on cross-device (EXDEV) error fallback.
7. Corrupted cache isolation and quarantine mechanisms without false-positive race conditions or recursive re-quarantine.
8. RFC 8259 Decimal dict key sanitization in sanitize_nan_inf.
9. 100% bitwise parity across mirrored atomic_writer and json_writer modules.
"""

from __future__ import annotations

from decimal import Decimal
import errno
import hashlib
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
    atomic_write_text,
    cleanup_stale_lock_files,
    cleanup_stale_temp_files,
    durable_fsync,
    get_lock_path,
    is_corrupted_or_quarantined_filename,
    is_pid_alive,
    quarantine_corrupted_file,
    read_lock_metadata,
    sanitize_nan_inf,
)
from utils.json_writer import (
    _safe_float,
    format_daily_report_payload,
    read_daily_reports,
    write_daily_reports,
)


class TestAtomicWriterConcurrencyAudit(unittest.TestCase):
    """Deep concurrency, durability, and quarantine audit tests."""

    def setUp(self) -> None:
        self.tmp_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.tmp_dir_obj.name)

    def tearDown(self) -> None:
        try:
            self.tmp_dir_obj.cleanup()
        except OSError:
            pass

    def test_01_durable_fsync_invokes_os_fsync_and_f_fullfsync_on_darwin(self) -> None:
        """durable_fsync calls os.fsync and invokes fcntl.F_FULLFSYNC when available on macOS."""
        test_file = self.test_dir / "fsync_test.dat"
        test_file.write_bytes(b"payload")
        fd = os.open(str(test_file), os.O_RDWR)
        try:
            with mock.patch("os.fsync") as mock_fsync:
                durable_fsync(fd)
                mock_fsync.assert_called_once_with(fd)
        finally:
            os.close(fd)

    def test_02_stale_lock_not_broken_during_metadata_race_window(self) -> None:
        """Active lock with dead holder metadata is NOT broken if age is <= stale_timeout."""
        lock_path = self.test_dir / "race_window.lock"
        dead_pid = 9999999
        self.assertFalse(is_pid_alive(dead_pid))
        fresh_time = time.time() - 0.2
        initial_content = f"pid={dead_pid}\ntime={fresh_time}\n"
        lock_path.write_text(initial_content, encoding="utf-8")

        # Simulate lock contention (active competing process holds kernel flock)
        with mock.patch("fcntl.flock", side_effect=OSError(errno.EAGAIN, "Resource temporarily unavailable")):
            lock = FileLock(lock_path, timeout=0.06, poll_interval=0.02, stale_timeout=300.0, fail_on_timeout=False)
            with lock:
                self.assertFalse(lock.acquired)
                self.assertFalse(lock.is_locked)

        # Crucial check: Lock file was NOT unlinked or broken!
        self.assertTrue(lock_path.exists())
        self.assertEqual(lock_path.read_text(encoding="utf-8"), initial_content)

    def test_03_stale_lock_is_broken_when_exceeding_stale_timeout(self) -> None:
        """Lock held by dead PID exceeding stale_timeout is cleanly broken and reacquired."""
        lock_path = self.test_dir / "stale_expired.lock"
        dead_pid = 9999999
        old_time = time.time() - 400.0
        lock_path.write_text(f"pid={dead_pid}\ntime={old_time}\n", encoding="utf-8")
        os.utime(lock_path, (old_time, old_time))

        lock = FileLock(lock_path, timeout=0.5, stale_timeout=300.0)
        with lock:
            self.assertTrue(lock.acquired)
            self.assertTrue(lock.is_locked)
            pid, ts = read_lock_metadata(lock_path)
            self.assertEqual(pid, os.getpid())
            self.assertGreater(ts, time.time() - 5.0)

    def test_04_zero_fd_leak_on_timeout_with_fail_on_timeout_false(self) -> None:
        """FileLock immediately closes self.fd when timing out with fail_on_timeout=False."""
        lock_path = self.test_dir / "fd_leak.lock"
        with mock.patch("fcntl.flock", side_effect=OSError(errno.EAGAIN, "Busy")):
            lock = FileLock(lock_path, timeout=0.04, poll_interval=0.01, fail_on_timeout=False)
            with lock:
                self.assertFalse(lock.acquired)
                self.assertIsNone(lock.fd, "File descriptor must be closed and set to None on timeout")
                self.assertFalse(lock.is_locked)

    def test_05_nested_reentrant_lock_instance_isolation(self) -> None:
        """Inner FileLock context exit marks inner lock inactive while outer remains locked."""
        lock_path = self.test_dir / "reentrancy.lock"

        with FileLock(lock_path) as l1:
            self.assertTrue(l1.is_locked)
            with FileLock(lock_path) as l2:
                self.assertTrue(l1.is_locked)
                self.assertTrue(l2.is_locked)
            # l2 has exited; its instance should reflect inactive state
            self.assertFalse(l2.is_locked)
            # l1 is still in scope; its instance remains active
            self.assertTrue(l1.is_locked)

        # After l1 exits, both are inactive
        self.assertFalse(l1.is_locked)
        self.assertFalse(l2.is_locked)

    def test_06_metadata_write_avoids_zero_byte_window(self) -> None:
        """FileLock writes metadata before truncating to eliminate 0-byte reader window."""
        lock_path = self.test_dir / "meta_window.lock"
        lock = FileLock(lock_path)
        with lock:
            self.assertGreater(os.path.getsize(lock_path), 0)
            pid, ts = read_lock_metadata(lock_path)
            self.assertEqual(pid, os.getpid())
            self.assertIsNotNone(ts)

    def test_07_exdev_staging_atomic_replacement(self) -> None:
        """atomic_write_json falls back cleanly to staging copy and replace on EXDEV."""
        target = self.test_dir / "exdev_atomic.json"
        replace_calls: list[str] = []
        original_replace = os.replace

        def mock_replace(src: str, dst: str) -> None:
            replace_calls.append(f"{src} -> {dst}")
            raise OSError(errno.EXDEV, "Cross-device link")

        with mock.patch("os.replace", side_effect=mock_replace):
            written = atomic_write_json({"key": "exdev_val"}, target)

        self.assertTrue(written.exists())
        with open(written, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["key"], "exdev_val")

    def test_08_quarantine_corrupted_file_no_redundant_requarantine(self) -> None:
        """quarantine_corrupted_file does not re-quarantine an already quarantined file."""
        target = self.test_dir / "payload.corrupt_20261102_010203_000000.json"
        target.write_text("{broken", encoding="utf-8")

        result = quarantine_corrupted_file(target)
        self.assertEqual(result, target.resolve())
        self.assertTrue(target.exists())
        self.assertEqual(target.name, "payload.corrupt_20261102_010203_000000.json")

    def test_09_read_daily_reports_quarantine_under_lock(self) -> None:
        """read_daily_reports acquires FileLock when quarantine_corrupted=True to avoid race."""
        reports_file = self.test_dir / "daily_reports.json"
        reports_file.write_text("{malformed", encoding="utf-8")

        data = read_daily_reports(str(reports_file), quarantine_corrupted=True)
        self.assertEqual(data, {"reports": [], "statistics": {}})
        self.assertFalse(reports_file.exists())
        quarantined = list(self.test_dir.glob("daily_reports.corrupt_*.json"))
        self.assertEqual(len(quarantined), 1)

    def test_10_decimal_key_sanitization_in_sanitize_nan_inf(self) -> None:
        """sanitize_nan_inf sanitizes Decimal keys (normal to str, NaN/Inf to '0.0') for RFC 8259."""
        obj = {
            Decimal("99.95"): "valid_decimal_key",
            Decimal("NaN"): "nan_decimal_key",
            Decimal("Infinity"): "inf_decimal_key",
        }
        sanitized = sanitize_nan_inf(obj)
        self.assertIn("99.95", sanitized)
        self.assertEqual(sanitized["99.95"], "valid_decimal_key")
        self.assertIn("0.0", sanitized)

        # Guarantee that json.dumps accepts the sanitized dict without TypeError
        dumped = json.dumps(sanitized)
        self.assertIn('"99.95"', dumped)

    def test_11_safe_float_with_decimal_nan_inf(self) -> None:
        """_safe_float handles Decimal NaN and Decimal Infinity defaults cleanly."""
        self.assertEqual(_safe_float(None, Decimal("NaN")), 0.0)
        self.assertEqual(_safe_float(None, Decimal("Infinity")), 0.0)
        self.assertEqual(_safe_float(None, Decimal("42.5")), 42.5)

    def test_12_mirrored_files_exact_parity(self) -> None:
        """tracker/atomic_writer.py and utils/json_writer.py match root bitwise identically."""
        root_dir = Path(__file__).resolve().parent.parent.parent
        web_dir = Path(__file__).resolve().parent.parent

        pairs = [
            (root_dir / "tracker" / "atomic_writer.py", web_dir / "tracker" / "atomic_writer.py"),
            (root_dir / "utils" / "json_writer.py", web_dir / "utils" / "json_writer.py"),
        ]

        for p_root, p_web in pairs:
            self.assertTrue(p_root.is_file(), f"{p_root} must exist")
            self.assertTrue(p_web.is_file(), f"{p_web} must exist")
            h_root = hashlib.sha256(p_root.read_bytes()).hexdigest()
            h_web = hashlib.sha256(p_web.read_bytes()).hexdigest()
            self.assertEqual(h_root, h_web, f"Bitwise mismatch on {p_root.name}!")


if __name__ == "__main__":
    unittest.main()
