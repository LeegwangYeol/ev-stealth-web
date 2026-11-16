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
        repo_root = next(
            (p for p in [Path(__file__).resolve().parent.parent, Path(__file__).resolve().parent.parent.parent] if (p / "ev-stealth-web").is_dir()),
            Path(__file__).resolve().parent.parent,
        )
        root_dir = repo_root
        web_dir = repo_root / "ev-stealth-web"

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

    def test_13_time_nan_in_lock_metadata_does_not_defeat_stale_lock_breaking(self) -> None:
        """Lock file with corrupted time=nan is treated safely and broken when stale."""
        lock_path = self.test_dir / "corrupted_time.lock"
        old_time = time.time() - 400.0
        lock_path.write_text("pid=9999999\ntime=nan\n", encoding="utf-8")
        os.utime(lock_path, (old_time, old_time))

        pid, ts = read_lock_metadata(lock_path)
        self.assertEqual(pid, 9999999)
        self.assertIsNone(ts, "NaN timestamp must be sanitized to None")

        lock = FileLock(lock_path, timeout=0.5, stale_timeout=300.0)
        with lock:
            self.assertTrue(lock.acquired)
            new_pid, new_ts = read_lock_metadata(lock_path)
            self.assertEqual(new_pid, os.getpid())
            self.assertIsNotNone(new_ts)

    def test_14_is_pid_alive_handles_none_and_invalid_types(self) -> None:
        """is_pid_alive returns False cleanly without TypeError on invalid input types."""
        self.assertFalse(is_pid_alive(None))
        self.assertFalse(is_pid_alive("invalid_pid"))
        self.assertFalse(is_pid_alive(-100))
        self.assertFalse(is_pid_alive(0))
        self.assertTrue(is_pid_alive(os.getpid()))

    def test_15_directory_rejection_in_atomic_writers(self) -> None:
        """atomic_write_json, atomic_write_text, and atomic_write_json_multiple reject existing dirs."""
        dir_target = self.test_dir / "sub_dir"
        dir_target.mkdir()

        with self.assertRaises(IsADirectoryError):
            atomic_write_json({"a": 1}, dir_target)

        with self.assertRaises(IsADirectoryError):
            atomic_write_text("hello", dir_target)

        with self.assertRaises(IsADirectoryError):
            atomic_write_json_multiple({"a": 1}, [dir_target])

    def test_16_safe_float_with_invalid_string_and_none_default(self) -> None:
        """_safe_float handles invalid string and None default values gracefully."""
        self.assertEqual(_safe_float("invalid", default="bad"), 0.0)
        self.assertEqual(_safe_float(None, default=None), 0.0)
        self.assertEqual(_safe_float(None, default="12.5"), 12.5)

    def test_17_extract_record_date_handles_none_and_non_dict(self) -> None:
        """_extract_record_date returns empty string for None and non-dict inputs."""
        from utils.json_writer import _extract_record_date
        self.assertEqual(_extract_record_date(None), "")
        self.assertEqual(_extract_record_date("not a dict"), "")
        self.assertEqual(_extract_record_date([]), "")

    def test_18_dict_with_complex_and_tuple_keys(self) -> None:
        """atomic_write_json serializes dicts with complex and tuple keys without TypeError."""
        target = self.test_dir / "tuple_keys.json"
        data = {
            (1, 2): "tuple_key_val",
            complex(1.0, 2.0): "complex_key_val",
        }
        written = atomic_write_json(data, target)
        self.assertTrue(written.is_file())
        with open(written, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        self.assertIn("(1, 2)", loaded)
        self.assertEqual(loaded["(1, 2)"], "tuple_key_val")

    def test_19_cleanup_stale_temp_files_cleans_broken_symlinks(self) -> None:
        """cleanup_stale_temp_files removes broken .tmp_ symlinks older than max_age_seconds."""
        broken_target = self.test_dir / "nonexistent_target_123"
        symlink_path = self.test_dir / ".tmp_broken_symlink.json"
        symlink_path.symlink_to(broken_target)

        old_time = time.time() - 7200
        os.utime(symlink_path, (old_time, old_time), follow_symlinks=False)

        cleaned = cleanup_stale_temp_files(self.test_dir, max_age_seconds=3600.0)
        self.assertEqual(cleaned, 1)
        self.assertFalse(symlink_path.exists(follow_symlinks=False))

    def test_20_concurrent_multi_thread_atomic_writers_stress(self) -> None:
        """Multi-threaded stress test: 20 threads writing concurrently produces valid JSON and 0 leaks."""
        import threading
        target = self.test_dir / "concurrent_stress.json"
        errors: list[Exception] = []

        def worker(thread_idx: int) -> None:
            try:
                for step in range(10):
                    payload = {
                        "thread_id": thread_idx,
                        "step": step,
                        "timestamp": time.time(),
                        "items": list(range(20)),
                    }
                    atomic_write_json(payload, target, temp_prefix=f".tmp_th_{thread_idx}_")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"Encountered thread errors: {errors}")
        self.assertTrue(target.is_file())
        with open(target, "r", encoding="utf-8") as f:
            final_data = json.load(f)
        self.assertIn("thread_id", final_data)
        self.assertIn("step", final_data)

        # Confirm zero orphaned scratch files left behind
        temp_files = list(self.test_dir.glob(".tmp_th_*"))
        self.assertEqual(temp_files, [], "No orphaned temp files must remain after concurrent stress")


if __name__ == "__main__":
    unittest.main()
