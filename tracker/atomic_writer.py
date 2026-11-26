"""POSIX crash-durable atomic JSON writer.

Provides transactional file write guarantees via NamedTemporaryFile, flush,
fsync, atomic rename (os.replace), directory fsync, cross-process advisory locking (FileLock),
and corrupted payload isolation/quarantine routines.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
import contextlib
import dataclasses
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
import errno
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import stat
import tempfile
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

try:
    import fcntl
except ImportError:
    fcntl = None  # type: ignore

try:
    import msvcrt
except ImportError:
    msvcrt = None  # type: ignore

import shutil
import uuid
import weakref

logger = logging.getLogger(__name__)

_last_temp_dir_cleanup_time: float = -60.0
_last_dest_dir_cleanup_times: "OrderedDict[Tuple[str, str], float]" = OrderedDict()
_cleanup_meta_lock = threading.Lock()


def is_pid_alive(pid: Any) -> bool:
    """Check if process with given PID is currently running."""
    if isinstance(pid, bool):
        return False
    if isinstance(pid, float) and (math.isnan(pid) or math.isinf(pid)):
        return False
    try:
        pid_int = int(pid)
    except (ValueError, TypeError, OverflowError):
        return False
    if pid_int <= 0:
        return False
    try:
        os.kill(pid_int, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, OverflowError):
        return False


def read_lock_metadata(lock_path: Union[str, Path]) -> Tuple[Optional[int], Optional[float]]:
    """Read PID and timestamp metadata from lock file if present."""
    if not lock_path:
        return None, None
    try:
        lp = str(lock_path)
        if not lp.strip() or "\x00" in lp:
            return None, None
        if not os.path.isfile(lp) or os.path.getsize(lp) == 0:
            return None, None
        with open(lp, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(1024)
        pid = None
        ts = None
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("pid="):
                try:
                    parsed_pid = int(line.split("=", 1)[1])
                    if parsed_pid > 0:
                        pid = parsed_pid
                except (ValueError, TypeError):
                    pass
            elif line.startswith("time="):
                try:
                    parsed_ts = float(line.split("=", 1)[1])
                    if not math.isnan(parsed_ts) and not math.isinf(parsed_ts):
                        ts = parsed_ts
                except (ValueError, TypeError):
                    pass
        return pid, ts
    except (OSError, ValueError):
        return None, None


def durable_fsync(fd: int) -> None:
    """Flush file descriptor buffers to disk physical storage crash-durably.

    Invokes os.fsync(fd) to commit kernel dirty pages and filesystem metadata.
    On macOS (Darwin), additionally invokes fcntl(fd, F_FULLFSYNC) to guarantee
    that hardware drive controller caches are committed to physical non-volatile media.
    """
    os.fsync(fd)
    if fcntl is not None and hasattr(fcntl, "F_FULLFSYNC"):
        try:
            fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
        except OSError:
            pass


class FileLock:
    """Re-entrant cross-process and thread-safe advisory file lock with timeout, stale lock breaking, and backoff."""

    _local = threading.local()
    _process_locks: "weakref.WeakValueDictionary[str, threading.RLock]" = weakref.WeakValueDictionary()
    _meta_lock = threading.Lock()

    @staticmethod
    def _sanitize_float_param(
        value: Any,
        default: float,
        min_val: float,
        max_val: Optional[float] = None,
    ) -> float:
        """Normalize numeric lock timing parameters, guarding against bool, NaN, Inf, and overflow."""
        if value is None or isinstance(value, bool):
            return default
        try:
            f_val = float(value)
        except (ValueError, TypeError, OverflowError):
            return default
        if math.isnan(f_val) or math.isinf(f_val):
            return default
        bounded = max(min_val, f_val)
        return min(bounded, max_val) if max_val is not None else bounded

    def __init__(
        self,
        lock_path: Union[str, Path],
        timeout: float = 10.0,
        poll_interval: float = 0.02,
        stale_timeout: float = 300.0,
        fail_on_timeout: bool = False,
    ) -> None:
        if not lock_path or not str(lock_path).strip():
            raise ValueError("lock_path cannot be empty")
        self.lock_path = str(Path(lock_path).resolve())
        timeout_max = getattr(threading, "TIMEOUT_MAX", 9223372036.0)
        self.timeout = self._sanitize_float_param(timeout, 10.0, 0.0, timeout_max)
        self.poll_interval = self._sanitize_float_param(poll_interval, 0.02, 0.001, timeout_max)
        self.stale_timeout = self._sanitize_float_param(stale_timeout, 300.0, 0.1, timeout_max)
        self.fail_on_timeout = bool(fail_on_timeout)
        self.fd: Optional[int] = None
        self.acquired: bool = False
        self._thread_lock_depth: int = 0
        self._instance_depth: int = 0
        with self._meta_lock:
            lock_obj = self._process_locks.get(self.lock_path)
            if lock_obj is None:
                lock_obj = threading.RLock()
                self._process_locks[self.lock_path] = lock_obj
            self._thread_lock = lock_obj

    @property
    def _thread_locked(self) -> bool:
        """Return True if this instance currently holds its thread lock."""
        return self._thread_lock_depth > 0

    @property
    def is_locked(self) -> bool:
        """Return True if this lock is currently held by this thread."""
        return self.acquired and self.fd is not None

    def _sleep_bounded(self, start_time: float) -> None:
        """Sleep up to poll_interval without overshooting timeout."""
        remaining = self.timeout - (time.monotonic() - start_time)
        if remaining > 0.0:
            time.sleep(min(self.poll_interval, remaining))

    def _release_thread_lock(self) -> None:
        """Release one acquisition depth of the per-path thread RLock if held."""
        if self._thread_lock_depth > 0:
            self._thread_lock_depth -= 1
            try:
                self._thread_lock.release()
            except RuntimeError:
                pass

    def _inspect_stale_lock(self) -> Tuple[bool, Optional[int], bool, float]:
        """Inspect lock file metadata and mtime to determine whether it is stale."""
        holder_pid, holder_ts = read_lock_metadata(self.lock_path)
        now = time.time()
        try:
            mtime_age = max(0.0, now - os.path.getmtime(self.lock_path))
        except OSError:
            mtime_age = 0.0

        is_dead_holder = holder_pid is not None and not is_pid_alive(holder_pid)
        is_expired_holder = (
            (holder_ts is not None and (now - holder_ts) > self.stale_timeout)
            or (holder_ts is None and mtime_age > self.stale_timeout)
        )
        lock_age = max(0.0, mtime_age, (now - holder_ts) if holder_ts is not None else mtime_age)
        should_break = (
            (is_dead_holder and lock_age > self.stale_timeout)
            or (is_expired_holder and lock_age > self.stale_timeout)
            or (holder_pid is None and holder_ts is None and lock_age > self.stale_timeout)
        )
        return should_break, holder_pid, is_dead_holder, lock_age

    def __enter__(self) -> FileLock:
        acquired_thread = self._thread_lock.acquire(timeout=self.timeout)
        if not acquired_thread:
            if self.fail_on_timeout:
                raise TimeoutError(
                    f"Timeout ({self.timeout:.1f}s) acquiring thread lock on {self.lock_path}"
                )
            logger.warning(
                "Timeout (%.1fs) acquiring thread lock on %s. Proceeding defensively.",
                self.timeout,
                self.lock_path,
            )
            self.acquired = False
            return self

        self._thread_lock_depth += 1
        try:
            if not hasattr(self._local, "depths"):
                self._local.depths = {}
            if not hasattr(self._local, "fds"):
                self._local.fds = {}
            depth = self._local.depths.get(self.lock_path, 0)
            if depth > 0:
                self._local.depths[self.lock_path] = depth + 1
                self.fd = self._local.fds.get(self.lock_path)
                self.acquired = True
                self._instance_depth += 1
                return self

            os.makedirs(os.path.dirname(self.lock_path), exist_ok=True)
            flags = os.O_CREAT | os.O_RDWR
            if hasattr(os, "O_BINARY"):
                flags |= os.O_BINARY
            self.fd = os.open(self.lock_path, flags, 0o644)
            if fcntl is not None:
                start_time = time.monotonic()
                stale_breaks = 0
                while True:
                    try:
                        fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        # Inode verification: verify file was not unlinked and recreated under race condition
                        inode_invalid = False
                        try:
                            f_stat = os.fstat(self.fd)
                            p_stat = os.stat(self.lock_path)
                            inode_invalid = f_stat.st_nlink == 0 or (
                                f_stat.st_ino != 0 and (
                                    f_stat.st_ino != p_stat.st_ino or f_stat.st_dev != p_stat.st_dev
                                )
                            )
                        except OSError:
                            inode_invalid = True

                        if inode_invalid:
                            try:
                                os.close(self.fd)
                            except OSError:
                                pass
                            self.fd = None
                            if (time.monotonic() - start_time) >= self.timeout:
                                if self.fail_on_timeout:
                                    raise TimeoutError(
                                        f"Timeout ({self.timeout:.1f}s) acquiring lock on {self.lock_path}"
                                    )
                                logger.warning(
                                    "Timeout (%.1fs) acquiring lock on %s during inode verification. Proceeding defensively.",
                                    self.timeout,
                                    self.lock_path,
                                )
                                self.acquired = False
                                self._release_thread_lock()
                                break
                            self._sleep_bounded(start_time)
                            self.fd = os.open(self.lock_path, flags, 0o644)
                            continue
                        self.acquired = True
                        try:
                            os.lseek(self.fd, 0, os.SEEK_SET)
                            meta_bytes = f"pid={os.getpid()}\ntime={time.time()}\n".encode("utf-8")
                            os.write(self.fd, meta_bytes)
                            os.ftruncate(self.fd, len(meta_bytes))
                        except OSError:
                            pass
                        break
                    except (BlockingIOError, OSError) as exc:
                        if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK):
                            raise

                        # Check for stale lock from dead PID or expired timeout
                        should_break, holder_pid, is_dead_holder, lock_age = self._inspect_stale_lock()

                        if should_break:
                            logger.warning(
                                "Breaking stale lock on %s (holder pid=%s alive=%s, age=%.1fs > %.1fs)",
                                self.lock_path,
                                holder_pid,
                                holder_pid is not None and not is_dead_holder,
                                lock_age,
                                self.stale_timeout,
                            )
                            try:
                                os.close(self.fd)
                            except OSError:
                                pass
                            self.fd = None
                            unlink_ok = True
                            try:
                                os.unlink(self.lock_path)
                            except OSError:
                                unlink_ok = False
                            if stale_breaks > 0 or not unlink_ok:
                                if (time.monotonic() - start_time) >= self.timeout:
                                    if self.fail_on_timeout:
                                        raise TimeoutError(
                                            f"Timeout ({self.timeout:.1f}s) acquiring lock on {self.lock_path}"
                                        )
                                    logger.warning(
                                        "Timeout (%.1fs) acquiring lock on %s. Proceeding defensively.",
                                        self.timeout,
                                        self.lock_path,
                                    )
                                    self.acquired = False
                                    self._release_thread_lock()
                                    break
                                self._sleep_bounded(start_time)
                            stale_breaks += 1
                            self.fd = os.open(self.lock_path, flags, 0o644)
                            continue

                        if (time.monotonic() - start_time) >= self.timeout:
                            if self.fd is not None:
                                try:
                                    os.close(self.fd)
                                except OSError:
                                    pass
                                self.fd = None
                            if self.fail_on_timeout:
                                raise TimeoutError(
                                    f"Timeout ({self.timeout:.1f}s) acquiring lock on {self.lock_path}"
                                )
                            logger.warning(
                                "Timeout (%.1fs) acquiring lock on %s. Proceeding defensively.",
                                self.timeout,
                                self.lock_path,
                            )
                            self.acquired = False
                            self._release_thread_lock()
                            break
                        self._sleep_bounded(start_time)
            elif msvcrt is not None:
                start_time = time.monotonic()
                stale_breaks = 0
                while True:
                    try:
                        os.lseek(self.fd, 0, os.SEEK_SET)
                        msvcrt.locking(self.fd, msvcrt.LK_NBLCK, 1)
                        self.acquired = True
                        try:
                            meta_bytes = f"pid={os.getpid()}\ntime={time.time()}\n".encode("utf-8")
                            os.write(self.fd, meta_bytes)
                            os.ftruncate(self.fd, len(meta_bytes))
                        except OSError:
                            pass
                        break
                    except (BlockingIOError, OSError) as exc:
                        if exc.errno not in (errno.EACCES, getattr(errno, "EDEADLK", 36), getattr(errno, "EAGAIN", 11)):
                            raise
                        should_break, holder_pid, is_dead_holder, lock_age = self._inspect_stale_lock()

                        if should_break:
                            logger.warning(
                                "Breaking stale Windows lock on %s (pid %s dead=%s, age=%.1fs > %.1fs)",
                                self.lock_path,
                                holder_pid,
                                is_dead_holder,
                                lock_age,
                                self.stale_timeout,
                            )
                            try:
                                os.close(self.fd)
                            except OSError:
                                pass
                            self.fd = None
                            unlink_ok = True
                            try:
                                os.unlink(self.lock_path)
                            except OSError:
                                unlink_ok = False
                            if stale_breaks > 0 or not unlink_ok:
                                if (time.monotonic() - start_time) >= self.timeout:
                                    if self.fail_on_timeout:
                                        raise TimeoutError(
                                            f"Timeout ({self.timeout:.1f}s) acquiring Windows lock on {self.lock_path}"
                                        )
                                    logger.warning(
                                        "Timeout (%.1fs) acquiring Windows lock on %s. Proceeding defensively.",
                                        self.timeout,
                                        self.lock_path,
                                    )
                                    self.acquired = False
                                    self._release_thread_lock()
                                    break
                                self._sleep_bounded(start_time)
                            stale_breaks += 1
                            self.fd = os.open(self.lock_path, flags, 0o644)
                            continue
                        if (time.monotonic() - start_time) >= self.timeout:
                            if self.fd is not None:
                                try:
                                    os.close(self.fd)
                                except OSError:
                                    pass
                                self.fd = None
                            if self.fail_on_timeout:
                                raise TimeoutError(
                                    f"Timeout ({self.timeout:.1f}s) acquiring Windows lock on {self.lock_path}"
                                )
                            logger.warning(
                                "Timeout (%.1fs) acquiring Windows lock on %s. Proceeding defensively.",
                                self.timeout,
                                self.lock_path,
                            )
                            self.acquired = False
                            self._release_thread_lock()
                            break
                        self._sleep_bounded(start_time)
            else:
                self.acquired = True

            if self.acquired:
                self._local.depths[self.lock_path] = 1
                self._local.fds[self.lock_path] = self.fd
                self._instance_depth = 1
            return self
        except BaseException:
            if self.fd is not None:
                if self.acquired:
                    if fcntl is not None:
                        try:
                            fcntl.flock(self.fd, fcntl.LOCK_UN)
                        except OSError:
                            pass
                    elif msvcrt is not None:
                        try:
                            os.lseek(self.fd, 0, os.SEEK_SET)
                            msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)
                        except OSError:
                            pass
                try:
                    os.close(self.fd)
                except OSError:
                    pass
                self.fd = None
            self.acquired = False
            if hasattr(self._local, "depths") and self.lock_path in self._local.depths:
                del self._local.depths[self.lock_path]
            if hasattr(self._local, "fds") and self.lock_path in self._local.fds:
                del self._local.fds[self.lock_path]
            self._release_thread_lock()
            raise

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._instance_depth == 0 and self._thread_lock_depth == 0:
            return
        try:
            depth = getattr(self._local, "depths", {}).get(self.lock_path, 0)
            if depth > 1:
                self._local.depths[self.lock_path] = depth - 1
                if self._instance_depth > 0:
                    self._instance_depth -= 1
                    if self._instance_depth == 0:
                        self.acquired = False
                        self.fd = None
                return
            if hasattr(self._local, "depths") and self.lock_path in self._local.depths:
                del self._local.depths[self.lock_path]

            fd_to_close = getattr(self._local, "fds", {}).pop(self.lock_path, self.fd)
            if fd_to_close is not None:
                if self.acquired:
                    try:
                        os.ftruncate(fd_to_close, 0)
                    except OSError:
                        pass
                if fcntl is not None:
                    try:
                        fcntl.flock(fd_to_close, fcntl.LOCK_UN)
                    except OSError:
                        pass
                elif msvcrt is not None:
                    try:
                        os.lseek(fd_to_close, 0, os.SEEK_SET)
                        msvcrt.locking(fd_to_close, msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass
                try:
                    os.close(fd_to_close)
                except OSError:
                    pass
            self.fd = None
            self.acquired = False
            self._instance_depth = 0
        finally:
            self._release_thread_lock()

    def acquire(self) -> bool:
        """Explicit acquire method conforming to Lock protocol."""
        self.__enter__()
        return self.acquired

    def release(self) -> None:
        """Explicit release method conforming to Lock protocol."""
        self.__exit__(None, None, None)


def get_lock_path(target_path: Union[str, Path]) -> Path:
    """Return a deterministic temporary lock file path for a target file path."""
    dest = Path(target_path).resolve()
    digest = hashlib.sha256(str(dest).encode("utf-8")).hexdigest()[:16]
    return Path(tempfile.gettempdir()) / f".ev_atomic_{digest}.lock"


def _sanitize_max_age(max_age_seconds: Any, default: float = 3600.0) -> float:
    """Normalize max_age_seconds to a non-negative float (falling back on NaN/negative/bool)."""
    if max_age_seconds is None or isinstance(max_age_seconds, bool):
        return default
    try:
        val = float(max_age_seconds)
    except (ValueError, TypeError, OverflowError):
        return default
    if math.isnan(val) or val < 0.0:
        return default
    return val


def _normalize_prefixes(prefix: Union[str, tuple[str, ...], list[str], None]) -> tuple[str, ...]:
    """Normalize prefix input into a tuple of non-empty prefix strings."""
    if prefix is None:
        return ()
    raw = (prefix,) if isinstance(prefix, str) else tuple(prefix)
    return tuple(p for p in raw if isinstance(p, str) and p)


def cleanup_stale_temp_files(
    directory: Union[str, Path],
    prefix: Union[str, tuple[str, ...], list[str]] = (".tmp_", ".tmp_subsidy_", ".tmp_daily_"),
    max_age_seconds: float = 3600.0,
) -> int:
    """Defensively unlink orphaned temporary files older than max_age_seconds."""
    if not directory or not str(directory).strip() or "\x00" in str(directory):
        return 0
    try:
        d = Path(directory)
        if not d.is_dir():
            return 0
    except (OSError, ValueError):
        return 0
    prefixes = _normalize_prefixes(prefix)
    if not prefixes:
        return 0
    safe_max_age = _sanitize_max_age(max_age_seconds)
    cleaned = 0
    now = time.time()
    try:
        for entry in d.iterdir():
            if any(entry.name.startswith(p) for p in prefixes):
                try:
                    st = entry.lstat()
                    if stat.S_ISDIR(st.st_mode):
                        continue
                    if (now - st.st_mtime) > safe_max_age:
                        entry.unlink(missing_ok=True)
                        cleaned += 1
                except OSError:
                    pass
    except (OSError, ValueError):
        pass
    return cleaned


def cleanup_stale_lock_files(
    directory: Union[str, Path],
    prefix: Union[str, tuple[str, ...], list[str]] = (".ev_atomic_", ".sync_", ".subsidy_"),
    suffix: str = ".lock",
    max_age_seconds: float = 3600.0,
) -> int:
    """Defensively clean up orphaned advisory lock files older than max_age_seconds if unheld."""
    if not directory or not str(directory).strip() or "\x00" in str(directory):
        return 0
    try:
        d = Path(directory)
        if not d.is_dir():
            return 0
    except (OSError, ValueError):
        return 0
    safe_max_age = _sanitize_max_age(max_age_seconds)
    prefixes = _normalize_prefixes(prefix)
    if not prefixes:
        return 0
    cleaned = 0
    now = time.time()
    try:
        for entry in d.iterdir():
            name = entry.name
            if not name.endswith(suffix):
                continue
            if not any(name.startswith(p) for p in prefixes):
                continue
            if entry.is_symlink() or not entry.is_file():
                continue
            try:
                st = entry.stat()
                age = max(0.0, now - st.st_mtime)
                holder_pid, holder_ts = read_lock_metadata(entry)
                is_dead_holder = holder_pid is not None and not is_pid_alive(holder_pid)
                is_expired_holder = (
                    (holder_ts is not None and (now - holder_ts) > safe_max_age)
                    or (holder_ts is None and age > safe_max_age)
                )

                # Skip if file has an active, living holder
                if holder_pid is not None and not is_dead_holder:
                    continue

                # For locks without a confirmed dead holder, require expiration
                if not is_dead_holder:
                    if holder_ts is not None and (now - holder_ts) <= safe_max_age:
                        continue
                    if age <= safe_max_age:
                        continue

                # Skip if not confirmed dead holder and not expired
                if not is_dead_holder and not is_expired_holder:
                    continue

                # Test non-blocking flock to guarantee no active process holds it
                if fcntl is not None:
                    test_fd = None
                    try:
                        test_fd = os.open(str(entry), os.O_RDWR)
                        try:
                            fcntl.flock(test_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            entry.unlink(missing_ok=True)
                            cleaned += 1
                        except (BlockingIOError, OSError):
                            pass
                    except OSError:
                        pass
                    finally:
                        if test_fd is not None:
                            try:
                                fcntl.flock(test_fd, fcntl.LOCK_UN)
                            except OSError:
                                pass
                            try:
                                os.close(test_fd)
                            except OSError:
                                pass
                elif msvcrt is not None:
                    test_fd = None
                    try:
                        test_fd = os.open(str(entry), os.O_RDWR)
                        try:
                            os.lseek(test_fd, 0, os.SEEK_SET)
                            msvcrt.locking(test_fd, msvcrt.LK_NBLCK, 1)
                            try:
                                os.lseek(test_fd, 0, os.SEEK_SET)
                                msvcrt.locking(test_fd, msvcrt.LK_UNLCK, 1)
                            except OSError:
                                pass
                            try:
                                os.close(test_fd)
                            except OSError:
                                pass
                            test_fd = None
                            entry.unlink(missing_ok=True)
                            cleaned += 1
                        except (BlockingIOError, OSError):
                            pass
                    except OSError:
                        pass
                    finally:
                        if test_fd is not None:
                            try:
                                os.close(test_fd)
                            except OSError:
                                pass
                else:
                    entry.unlink(missing_ok=True)
                    cleaned += 1
            except OSError:
                pass
    except (OSError, ValueError):
        pass
    return cleaned


def is_corrupted_or_quarantined_filename(filename_or_path: Union[str, Path, None]) -> bool:
    """Return True if filename indicates a quarantined or corrupted payload."""
    if not filename_or_path:
        return False
    name = Path(filename_or_path).name.lower()
    return (
        ".corrupted" in name
        or ".corrupt_" in name
        or name.endswith(".corrupt")
    )


def quarantine_corrupted_file(
    file_path: Union[str, Path],
    suffix: Optional[str] = None,
) -> Optional[Path]:
    """Quarantine a corrupted cache or payload file by renaming it to an isolated filename.

    Supports standard timestamped pattern (.corrupt_YYYYMMDD_HHMMSS_ffffff.json)
    and custom suffix isolation (.corrupted).
    Guarantees atomic replace, avoids accidental overwrite of existing valid files,
    cross-device EXDEV fallback, POSIX directory fsync durability,
    and standard permissions (0o644).
    """
    if not file_path or not str(file_path).strip() or "\x00" in str(file_path):
        return None
    try:
        p = Path(file_path).resolve()
    except (OSError, ValueError):
        return None
    if not p.exists() or p.is_dir():
        return None
    if is_corrupted_or_quarantined_filename(p):
        return p
    try:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        safe_suffix = ""
        if suffix and isinstance(suffix, str):
            cleaned_suffix = suffix.strip()
            if (
                cleaned_suffix
                and cleaned_suffix not in (".", "..")
                and "/" not in cleaned_suffix
                and "\\" not in cleaned_suffix
                and ".." not in cleaned_suffix
                and "\x00" not in cleaned_suffix
            ):
                safe_suffix = cleaned_suffix
        if safe_suffix:
            s = safe_suffix if safe_suffix.startswith(".") else f".{safe_suffix}"
            if s == ".corrupted":
                target_name = f"{p.stem}.corrupt_{ts}.corrupted"
            else:
                target_name = f"{p.stem}{s}"
        else:
            target_name = f"{p.stem}.corrupt_{ts}{p.suffix}"

        quarantine_path = p.with_name(target_name)

        # Avoid accidental overwrite of valid existing files or destination collision
        if quarantine_path.exists() or quarantine_path.resolve() == p.resolve():
            counter = 1
            base_stem = quarantine_path.stem
            base_suffix = quarantine_path.suffix
            candidate = quarantine_path
            while candidate.exists() or candidate.resolve() == p.resolve():
                candidate = p.with_name(f"{base_stem}_{counter}{base_suffix}")
                counter += 1
            quarantine_path = candidate

        max_retries = 3
        for attempt in range(max_retries):
            try:
                os.replace(str(p), str(quarantine_path))
                break
            except OSError as exc:
                if exc.errno == errno.ENOENT:
                    # Concurrent worker or thread already moved/quarantined the file
                    return None
                if exc.errno == errno.EXDEV:
                    staging_path = None
                    try:
                        with tempfile.NamedTemporaryFile(
                            mode="wb",
                            dir=str(quarantine_path.parent),
                            delete=False,
                            prefix=".tmp_quarantine_",
                            suffix=".stage",
                        ) as qsf:
                            staging_path = Path(qsf.name)
                        shutil.copyfile(str(p), str(staging_path))
                        with open(staging_path, "rb+") as qsf_sync:
                            qsf_sync.flush()
                            durable_fsync(qsf_sync.fileno())
                        os.chmod(str(staging_path), 0o644)
                        os.replace(str(staging_path), str(quarantine_path))
                        staging_path = None
                        try:
                            os.unlink(str(p))
                        except OSError:
                            pass
                    except OSError:
                        shutil.copyfile(str(p), str(quarantine_path))
                        try:
                            with open(quarantine_path, "a+b") as qf:
                                durable_fsync(qf.fileno())
                        except OSError:
                            pass
                        try:
                            os.unlink(str(p))
                        except OSError:
                            pass
                    finally:
                        if staging_path and staging_path.exists():
                            try:
                                staging_path.unlink()
                            except OSError:
                                pass
                    break
                if (
                    exc.errno in (errno.EACCES, errno.EPERM, getattr(errno, "EBUSY", 16))
                    and attempt < max_retries - 1
                ):
                    time.sleep(0.02 * (2 ** attempt))
                    continue
                raise

        try:
            os.chmod(quarantine_path, 0o644)
        except OSError:
            pass

        # Directory fsync to ensure quarantine rename is crash-durably committed
        if os.name != "nt":
            dir_flags = os.O_RDONLY
            if hasattr(os, "O_DIRECTORY"):
                dir_flags |= os.O_DIRECTORY
            try:
                dir_fd = os.open(str(p.parent), dir_flags)
                try:
                    durable_fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except OSError:
                pass

        logger.warning("Quarantined corrupted file: %s -> %s", p, quarantine_path)
        return quarantine_path
    except OSError as exc:
        logger.warning("Failed to quarantine corrupted file %s: %s", p, exc)
        return None


def _decimal_to_finite_float(val: Decimal) -> float:
    """Convert a Decimal to a finite float, clamping NaN, Inf, and float-overflow to 0.0."""
    if val.is_nan() or val.is_infinite():
        return 0.0
    try:
        f_val = float(val)
    except (ValueError, TypeError, OverflowError):
        return 0.0
    if math.isnan(f_val) or math.isinf(f_val):
        return 0.0
    return f_val


def sanitize_nan_inf(obj: Any, seen: Optional[set[int]] = None) -> Any:
    """Recursively convert float/Decimal NaN and Inf to 0.0 to guarantee RFC 8259 JSON compliance.

    Guards against circular reference cycles, non-string keys, complex numbers,
    UUIDs, dates, and frozensets.
    """
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return 0.0
        return obj
    elif isinstance(obj, Decimal):
        return _decimal_to_finite_float(obj)
    elif isinstance(obj, complex):
        real_val = 0.0 if (math.isnan(obj.real) or math.isinf(obj.real)) else float(obj.real)
        imag_val = 0.0 if (math.isnan(obj.imag) or math.isinf(obj.imag)) else float(obj.imag)
        return {"real": real_val, "imag": imag_val}
    elif isinstance(obj, (bytes, bytearray)):
        return obj.decode("utf-8", errors="replace")
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, Path):
        return str(obj)
    elif isinstance(obj, Enum):
        return sanitize_nan_inf(obj.value, seen)
    elif isinstance(obj, uuid.UUID):
        return str(obj)

    if isinstance(obj, (dict, Mapping)):
        if seen is None:
            seen = set()
        obj_id = id(obj)
        if obj_id in seen:
            raise ValueError("Circular reference detected in dict structure")
        seen.add(obj_id)
        try:
            res = {}
            for k, v in obj.items():
                if isinstance(k, float) and (math.isnan(k) or math.isinf(k)):
                    sanitized_k = "0.0"
                elif isinstance(k, Decimal):
                    sanitized_k = "0.0" if (k.is_nan() or k.is_infinite()) else str(k)
                elif isinstance(k, (date, datetime)):
                    sanitized_k = k.isoformat()
                elif isinstance(k, Enum):
                    sanitized_k = str(k.value)
                elif isinstance(k, Path):
                    sanitized_k = str(k)
                elif isinstance(k, uuid.UUID):
                    sanitized_k = str(k)
                elif isinstance(k, (bytes, bytearray)):
                    sanitized_k = k.decode("utf-8", errors="replace")
                elif isinstance(k, (complex, tuple, frozenset)):
                    sanitized_k = str(k)
                else:
                    sanitized_k = k
                res[sanitized_k] = sanitize_nan_inf(v, seen)
            return res
        finally:
            seen.remove(obj_id)

    elif isinstance(obj, (list, tuple, set, frozenset)):
        if seen is None:
            seen = set()
        obj_id = id(obj)
        if obj_id in seen:
            raise ValueError("Circular reference detected in sequence structure")
        seen.add(obj_id)
        try:
            return [sanitize_nan_inf(v, seen) for v in obj]
        finally:
            seen.remove(obj_id)

    return obj


def _json_default(obj: Any) -> Any:
    """Serialize Path, datetime, date, set, frozenset, Enum, UUID, complex, dataclass, and custom dict objects."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, (set, frozenset)):
        return [sanitize_nan_inf(v) for v in obj]
    if isinstance(obj, Enum):
        return sanitize_nan_inf(obj.value)
    if isinstance(obj, Decimal):
        return _decimal_to_finite_float(obj)
    if isinstance(obj, complex):
        real_val = 0.0 if (math.isnan(obj.real) or math.isinf(obj.real)) else float(obj.real)
        imag_val = 0.0 if (math.isnan(obj.imag) or math.isinf(obj.imag)) else float(obj.imag)
        return {"real": real_val, "imag": imag_val}
    if isinstance(obj, (bytes, bytearray)):
        return obj.decode("utf-8", errors="replace")
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if not isinstance(obj, type):
        for meth in ("to_dict", "as_dict", "model_dump", "dict", "tolist", "item"):
            fn = getattr(obj, meth, None)
            if callable(fn):
                try:
                    return sanitize_nan_inf(fn())
                except TypeError:
                    pass
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return sanitize_nan_inf(dataclasses.asdict(obj))
    if isinstance(obj, Mapping):
        return sanitize_nan_inf(dict(obj))
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _sanitize_temp_prefix(temp_prefix: Any, default: str) -> str:
    """Ensure temporary file prefix stays strictly within target directory (no path traversal)."""
    if not temp_prefix or not isinstance(temp_prefix, str):
        return default
    cleaned = temp_prefix.strip()
    if not cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned or "\x00" in cleaned:
        return default
    return cleaned


def _maybe_cleanup_global_temp_locks() -> None:
    """Throttled cleanup of stale lock files in system tempdir (outside per-file FileLock)."""
    global _last_temp_dir_cleanup_time
    if (time.monotonic() - _last_temp_dir_cleanup_time) > 60.0:
        with _cleanup_meta_lock:
            if (time.monotonic() - _last_temp_dir_cleanup_time) > 60.0:
                cleanup_stale_lock_files(tempfile.gettempdir(), max_age_seconds=3600.0)
                _last_temp_dir_cleanup_time = time.monotonic()


def _maybe_cleanup_dest_dir(dest_dir: Path, temp_prefix: str, interval_seconds: float = 60.0) -> None:
    """Throttled cleanup of orphaned temp/lock files in dest_dir to avoid directory sweeps on every write."""
    key = (str(dest_dir), temp_prefix)
    now = time.monotonic()
    with _cleanup_meta_lock:
        last = _last_dest_dir_cleanup_times.get(key)
        if last is not None and (now - last) <= interval_seconds:
            _last_dest_dir_cleanup_times.move_to_end(key)
            return
        _last_dest_dir_cleanup_times[key] = now
        _last_dest_dir_cleanup_times.move_to_end(key)
        while len(_last_dest_dir_cleanup_times) > 256:
            _last_dest_dir_cleanup_times.popitem(last=False)

    cleanup_stale_temp_files(dest_dir, prefix=temp_prefix, max_age_seconds=3600.0)
    cleanup_stale_lock_files(dest_dir, max_age_seconds=3600.0)


def atomic_write_json(
    data: Any,
    target_path: Union[str, Path],
    indent: int = 2,
    ensure_ascii: bool = False,
    default: Optional[Callable[[Any], Any]] = None,
    preserve_mtime: Optional[float] = None,
    mode: Optional[int] = None,
    preserve_permissions: bool = True,
    temp_prefix: str = ".tmp_subsidy_",
    _pre_encoded_content: Optional[bytes] = None,
) -> Path:
    """Atomically write data as JSON to target_path using crash-durable semantics.

    Steps:
    1. Resolve target directory and create if not existing.
    2. Acquire advisory FileLock to prevent race conditions during multi-process execution.
    3. Defensively prune orphaned temp files older than 1 hour in target directory.
    4. Write JSON to NamedTemporaryFile in the same filesystem directory.
    5. Flush application buffers and issue OS fsync on file descriptor.
    6. Preserve existing POSIX permissions (st_mode) or enforce standard mode (0o644).
    7. Atomically swap temp file with target using os.replace.
    8. Optionally preserve st_mtime.
    9. Issue directory fsync on parent directory for durability with leak-proof descriptor handling.
    10. Clean up temporary file in finally block if replacement fails.

    Args:
        data: Python dictionary, list, or object providing a `to_dict()` method.
        target_path: Target destination path.
        indent: JSON indentation spaces.
        ensure_ascii: Whether to escape non-ASCII characters.
        default: Optional custom serializer function. Defaults to `_json_default`.
        preserve_mtime: Optional float timestamp to preserve on destination.
        mode: Optional explicit POSIX mode (e.g. 0o644). Overrides preserve_permissions.
        preserve_permissions: Whether to retain mode and ownership of existing target file.
        temp_prefix: Prefix for temporary scratch file. Defaults to '.tmp_subsidy_'.
        _pre_encoded_content: Optional pre-serialized UTF-8 JSON bytes to skip redundant serialization.

    Returns:
        Path: The absolute path of the written file.
    """
    if not target_path or not str(target_path).strip():
        raise ValueError("target_path cannot be empty")
    dest = Path(target_path).resolve()
    if dest.is_dir():
        raise IsADirectoryError(f"Target path is an existing directory: {dest}")
    dest_dir = dest.parent
    dest_dir.mkdir(parents=True, exist_ok=True)

    temp_prefix = _sanitize_temp_prefix(temp_prefix, ".tmp_subsidy_")

    if _pre_encoded_content is None:
        # Convert object with to_dict / as_dict / model_dump / dataclass if present
        if not isinstance(data, type) and hasattr(data, "to_dict") and callable(getattr(data, "to_dict")):
            payload = data.to_dict()
        elif not isinstance(data, type) and hasattr(data, "as_dict") and callable(getattr(data, "as_dict")):
            payload = data.as_dict()
        elif not isinstance(data, type) and hasattr(data, "model_dump") and callable(getattr(data, "model_dump")):
            payload = data.model_dump()
        elif dataclasses.is_dataclass(data) and not isinstance(data, type):
            payload = dataclasses.asdict(data)
        else:
            payload = data

        payload = sanitize_nan_inf(payload)
    else:
        payload = None

    # Determine POSIX permission target
    target_mode = mode
    if target_mode is None:
        if preserve_permissions and dest.exists():
            try:
                target_mode = dest.stat().st_mode & 0o777
            except OSError:
                target_mode = 0o644
        else:
            target_mode = 0o644

    serializer = default if default is not None else _json_default
    temp_name: Optional[str] = None
    lock_file = get_lock_path(dest)

    _maybe_cleanup_global_temp_locks()

    with FileLock(lock_file):
        try:
            if mode is None and preserve_permissions and dest.exists():
                try:
                    target_mode = dest.stat().st_mode & 0o777
                except OSError:
                    target_mode = 0o644

            _maybe_cleanup_dest_dir(dest_dir, temp_prefix)

            # Create temp file in the same directory to ensure atomic os.replace across filesystem boundaries
            if _pre_encoded_content is not None:
                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    dir=str(dest_dir),
                    delete=False,
                    prefix=temp_prefix,
                    suffix=".json",
                ) as tf:
                    temp_name = tf.name
                    tf.write(_pre_encoded_content)
                    tf.flush()
                    durable_fsync(tf.fileno())
            else:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    dir=str(dest_dir),
                    delete=False,
                    encoding="utf-8",
                    prefix=temp_prefix,
                    suffix=".json",
                ) as tf:
                    temp_name = tf.name
                    json.dump(payload, tf, ensure_ascii=ensure_ascii, indent=indent, default=serializer, allow_nan=False)
                    tf.flush()
                    durable_fsync(tf.fileno())

            try:
                os.chmod(temp_name, target_mode)
            except OSError:
                pass

            if preserve_permissions and dest.exists():
                try:
                    st = dest.stat()
                    if hasattr(os, "chown") and os.geteuid() == 0:
                        try:
                            os.chown(temp_name, st.st_uid, st.st_gid)
                        except OSError:
                            pass
                except OSError:
                    pass

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    os.replace(temp_name, dest)
                    break
                except OSError as exc:
                    if exc.errno == errno.EXDEV:
                        staging_name = None
                        try:
                            with tempfile.NamedTemporaryFile(
                                mode="wb",
                                dir=str(dest_dir),
                                delete=False,
                                prefix=temp_prefix,
                                suffix=".stage",
                            ) as sf:
                                staging_name = sf.name
                            shutil.copyfile(temp_name, staging_name)
                            with open(staging_name, "rb+") as sf_sync:
                                sf_sync.flush()
                                durable_fsync(sf_sync.fileno())
                            os.chmod(staging_name, target_mode)
                            os.replace(staging_name, dest)
                            staging_name = None
                        except OSError:
                            # Direct copy fallback if directory does not permit temporary replacement
                            shutil.copyfile(temp_name, str(dest))
                            try:
                                with open(dest, "a+b") as df:
                                    durable_fsync(df.fileno())
                            except OSError:
                                pass
                        finally:
                            if staging_name and os.path.exists(staging_name):
                                try:
                                    os.unlink(staging_name)
                                except OSError:
                                    pass
                            try:
                                os.unlink(temp_name)
                            except OSError:
                                pass
                        break
                    if (
                        exc.errno in (errno.EACCES, errno.EPERM, getattr(errno, "EBUSY", 16))
                        and attempt < max_retries - 1
                    ):
                        time.sleep(0.02 * (2 ** attempt))
                        continue
                    raise

            temp_name = None  # Replaced or copied successfully

            if (
                preserve_mtime is not None
                and isinstance(preserve_mtime, (int, float))
                and not isinstance(preserve_mtime, bool)
                and not (math.isnan(preserve_mtime) or math.isinf(preserve_mtime))
            ):
                try:
                    os.utime(dest, (preserve_mtime, preserve_mtime))
                except (OSError, ValueError, OverflowError, TypeError):
                    pass

            # Directory fsync to commit the replacement to disk with leak-proof fd lifecycle
            if os.name != "nt":
                dir_flags = os.O_RDONLY
                if hasattr(os, "O_DIRECTORY"):
                    dir_flags |= os.O_DIRECTORY
                try:
                    dir_fd = os.open(str(dest_dir), dir_flags)
                    try:
                        durable_fsync(dir_fd)
                    finally:
                        os.close(dir_fd)
                except OSError:
                    pass

            logger.debug("Atomically wrote %s", dest)
            return dest
        except OSError as e:
            if e.errno in (errno.ENOSPC, getattr(errno, "EDQUOT", errno.ENOSPC)):
                logger.error("Disk space or quota exhausted (errno %d) during atomic write to %s: %s", e.errno, dest, e)
            else:
                logger.error("Failed atomic write to %s: %s", dest, e)
            raise
        except Exception as e:
            logger.error("Failed atomic write to %s: %s", dest, e)
            raise
        finally:
            if temp_name and os.path.exists(temp_name):
                try:
                    os.unlink(temp_name)
                except OSError:
                    pass


def atomic_write_json_multiple(
    data: Any,
    target_paths: List[Union[str, Path]],
    indent: int = 2,
    ensure_ascii: bool = False,
    default: Optional[Callable[[Any], Any]] = None,
    preserve_mtime: Optional[float] = None,
    mode: Optional[int] = None,
    preserve_permissions: bool = True,
) -> List[Path]:
    """Atomically write data as JSON to multiple target paths with single-pass serialization."""
    paths = list(target_paths) if target_paths is not None else []
    if not paths:
        return []

    # Validate target_paths early to fail fast on invalid arguments
    for p in paths:
        if not p or not str(p).strip():
            raise ValueError("target_path cannot be empty")
        resolved = Path(p).resolve()
        if resolved.is_dir():
            raise IsADirectoryError(f"Target path is an existing directory: {resolved}")

    # Serialize and sanitize once across all destination writes
    if not isinstance(data, type) and hasattr(data, "to_dict") and callable(getattr(data, "to_dict")):
        payload = data.to_dict()
    elif not isinstance(data, type) and hasattr(data, "as_dict") and callable(getattr(data, "as_dict")):
        payload = data.as_dict()
    elif not isinstance(data, type) and hasattr(data, "model_dump") and callable(getattr(data, "model_dump")):
        payload = data.model_dump()
    elif dataclasses.is_dataclass(data) and not isinstance(data, type):
        payload = dataclasses.asdict(data)
    else:
        payload = data

    payload = sanitize_nan_inf(payload)
    serializer = default if default is not None else _json_default
    encoded = json.dumps(
        payload,
        ensure_ascii=ensure_ascii,
        indent=indent,
        default=serializer,
        allow_nan=False,
    ).encode("utf-8")

    written_paths: List[Path] = []
    for p in paths:
        written = atomic_write_json(
            payload,
            p,
            indent=indent,
            ensure_ascii=ensure_ascii,
            default=serializer,
            preserve_mtime=preserve_mtime,
            mode=mode,
            preserve_permissions=preserve_permissions,
            _pre_encoded_content=encoded,
        )
        written_paths.append(written)
    return written_paths


def atomic_write_text(
    content: str,
    target_path: Union[str, Path],
    encoding: str = "utf-8",
    preserve_mtime: Optional[float] = None,
    mode: Optional[int] = None,
    preserve_permissions: bool = True,
    temp_prefix: str = ".tmp_text_",
) -> Path:
    """Atomically write string content to target_path using crash-durable semantics.

    Steps:
    1. Resolve target directory and create if not existing.
    2. Acquire advisory FileLock to prevent race conditions during multi-process execution.
    3. Defensively prune orphaned temp files older than 1 hour in target directory.
    4. Write content to NamedTemporaryFile in the same filesystem directory with explicit encoding.
    5. Flush application buffers and issue OS fsync on file descriptor.
    6. Preserve existing POSIX permissions (st_mode) or enforce standard mode (0o644).
    7. Atomically swap temp file with target using os.replace.
    8. Optionally preserve st_mtime.
    9. Issue directory fsync on parent directory for durability with leak-proof descriptor handling.
    10. Clean up temporary file in finally block if replacement fails.

    Args:
        content: String content to write.
        target_path: Target destination path.
        encoding: File character encoding, defaults to "utf-8".
        preserve_mtime: Optional float timestamp to preserve on destination.
        mode: Optional explicit POSIX mode (e.g. 0o644). Overrides preserve_permissions.
        preserve_permissions: Whether to retain mode and ownership of existing target file.
        temp_prefix: Prefix for temporary scratch file. Defaults to '.tmp_text_'.

    Returns:
        Path: The absolute path of the written file.
    """
    if not target_path or not str(target_path).strip():
        raise ValueError("target_path cannot be empty")
    dest = Path(target_path).resolve()
    if dest.is_dir():
        raise IsADirectoryError(f"Target path is an existing directory: {dest}")
    dest_dir = dest.parent
    dest_dir.mkdir(parents=True, exist_ok=True)

    if not isinstance(content, str):
        content = str(content)
    temp_prefix = _sanitize_temp_prefix(temp_prefix, ".tmp_text_")

    # Determine POSIX permission target
    target_mode = mode
    if target_mode is None:
        if preserve_permissions and dest.exists():
            try:
                target_mode = dest.stat().st_mode & 0o777
            except OSError:
                target_mode = 0o644
        else:
            target_mode = 0o644

    temp_name: Optional[str] = None
    lock_file = get_lock_path(dest)

    _maybe_cleanup_global_temp_locks()

    with FileLock(lock_file):
        try:
            if mode is None and preserve_permissions and dest.exists():
                try:
                    target_mode = dest.stat().st_mode & 0o777
                except OSError:
                    target_mode = 0o644

            _maybe_cleanup_dest_dir(dest_dir, temp_prefix)

            suffix = dest.suffix if dest.suffix else ".txt"
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=str(dest_dir),
                delete=False,
                encoding=encoding,
                prefix=temp_prefix,
                suffix=suffix,
            ) as tf:
                temp_name = tf.name
                tf.write(content)
                tf.flush()
                durable_fsync(tf.fileno())

            try:
                os.chmod(temp_name, target_mode)
            except OSError:
                pass

            if preserve_permissions and dest.exists():
                try:
                    st = dest.stat()
                    if hasattr(os, "chown") and os.geteuid() == 0:
                        try:
                            os.chown(temp_name, st.st_uid, st.st_gid)
                        except OSError:
                            pass
                except OSError:
                    pass

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    os.replace(temp_name, dest)
                    break
                except OSError as exc:
                    if exc.errno == errno.EXDEV:
                        staging_name = None
                        try:
                            with tempfile.NamedTemporaryFile(
                                mode="w",
                                dir=str(dest_dir),
                                delete=False,
                                encoding=encoding,
                                prefix=temp_prefix,
                                suffix=".stage",
                            ) as sf:
                                staging_name = sf.name
                            shutil.copyfile(temp_name, staging_name)
                            with open(staging_name, "rb+") as sf_sync:
                                sf_sync.flush()
                                durable_fsync(sf_sync.fileno())
                            os.chmod(staging_name, target_mode)
                            os.replace(staging_name, dest)
                            staging_name = None
                        except OSError:
                            shutil.copyfile(temp_name, str(dest))
                            try:
                                with open(dest, "a+b") as df:
                                    durable_fsync(df.fileno())
                            except OSError:
                                pass
                        finally:
                            if staging_name and os.path.exists(staging_name):
                                try:
                                    os.unlink(staging_name)
                                except OSError:
                                    pass
                            try:
                                os.unlink(temp_name)
                            except OSError:
                                pass
                        break
                    if (
                        exc.errno in (errno.EACCES, errno.EPERM, getattr(errno, "EBUSY", 16))
                        and attempt < max_retries - 1
                    ):
                        time.sleep(0.02 * (2 ** attempt))
                        continue
                    raise

            temp_name = None

            if (
                preserve_mtime is not None
                and isinstance(preserve_mtime, (int, float))
                and not isinstance(preserve_mtime, bool)
                and not (math.isnan(preserve_mtime) or math.isinf(preserve_mtime))
            ):
                try:
                    os.utime(dest, (preserve_mtime, preserve_mtime))
                except (OSError, ValueError, OverflowError, TypeError):
                    pass

            if os.name != "nt":
                dir_flags = os.O_RDONLY
                if hasattr(os, "O_DIRECTORY"):
                    dir_flags |= os.O_DIRECTORY
                try:
                    dir_fd = os.open(str(dest_dir), dir_flags)
                    try:
                        durable_fsync(dir_fd)
                    finally:
                        os.close(dir_fd)
                except OSError:
                    pass

            logger.debug("Atomically wrote text to %s", dest)
            return dest
        except OSError as e:
            if e.errno in (errno.ENOSPC, getattr(errno, "EDQUOT", errno.ENOSPC)):
                logger.error("Disk space or quota exhausted (errno %d) during atomic text write to %s: %s", e.errno, dest, e)
            else:
                logger.error("Failed atomic text write to %s: %s", dest, e)
            raise
        except Exception as e:
            logger.error("Failed atomic text write to %s: %s", dest, e)
            raise
        finally:
            if temp_name and os.path.exists(temp_name):
                try:
                    os.unlink(temp_name)
                except OSError:
                    pass


