"""POSIX crash-durable atomic JSON writer.

Provides transactional file write guarantees via NamedTemporaryFile, flush,
fsync, atomic rename (os.replace), directory fsync, cross-process advisory locking (FileLock),
and corrupted payload isolation/quarantine routines.
"""

from __future__ import annotations

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
import tempfile
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Union

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

logger = logging.getLogger(__name__)


def is_pid_alive(pid: int) -> bool:
    """Check if process with given PID is currently running."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def read_lock_metadata(lock_path: Union[str, Path]) -> Tuple[Optional[int], Optional[float]]:
    """Read PID and timestamp metadata from lock file if present."""
    try:
        lp = str(lock_path)
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
                    pid = int(line.split("=", 1)[1])
                except ValueError:
                    pass
            elif line.startswith("time="):
                try:
                    ts = float(line.split("=", 1)[1])
                except ValueError:
                    pass
        return pid, ts
    except OSError:
        return None, None


class FileLock:
    """Re-entrant cross-process and thread-safe advisory file lock with timeout, stale lock breaking, and backoff."""

    _local = threading.local()
    _process_locks: Dict[str, threading.RLock] = {}
    _meta_lock = threading.Lock()

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
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.stale_timeout = stale_timeout
        self.fail_on_timeout = fail_on_timeout
        self.fd: Optional[int] = None
        self.acquired: bool = False
        with self._meta_lock:
            if self.lock_path not in self._process_locks:
                self._process_locks[self.lock_path] = threading.RLock()
            self._thread_lock = self._process_locks[self.lock_path]

    @property
    def is_locked(self) -> bool:
        """Return True if this lock is currently held by this thread."""
        return self.acquired and self.fd is not None

    def __enter__(self) -> FileLock:
        self._thread_lock.acquire()
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
                return self

            os.makedirs(os.path.dirname(self.lock_path), exist_ok=True)
            flags = os.O_CREAT | os.O_RDWR
            if hasattr(os, "O_BINARY"):
                flags |= os.O_BINARY
            self.fd = os.open(self.lock_path, flags, 0o644)
            if fcntl is not None:
                start_time = time.monotonic()
                while True:
                    try:
                        fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        # Inode verification: verify file was not unlinked and recreated under race condition
                        try:
                            f_stat = os.fstat(self.fd)
                            p_stat = os.stat(self.lock_path)
                            if f_stat.st_ino != 0 and (
                                f_stat.st_ino != p_stat.st_ino or f_stat.st_dev != p_stat.st_dev
                            ):
                                os.close(self.fd)
                                self.fd = os.open(self.lock_path, flags, 0o644)
                                continue
                        except OSError:
                            os.close(self.fd)
                            self.fd = os.open(self.lock_path, flags, 0o644)
                            continue
                        self.acquired = True
                        try:
                            os.ftruncate(self.fd, 0)
                            os.lseek(self.fd, 0, os.SEEK_SET)
                            meta_bytes = f"pid={os.getpid()}\ntime={time.time()}\n".encode("utf-8")
                            os.write(self.fd, meta_bytes)
                        except OSError:
                            pass
                        break
                    except (BlockingIOError, OSError) as exc:
                        if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK):
                            raise

                        # Check for stale lock from dead PID or expired timeout
                        holder_pid, holder_ts = read_lock_metadata(self.lock_path)
                        now = time.time()
                        is_dead_holder = holder_pid is not None and not is_pid_alive(holder_pid)
                        is_expired_holder = (
                            holder_ts is not None and (now - holder_ts) > self.stale_timeout
                        )
                        try:
                            mtime_age = now - os.path.getmtime(self.lock_path)
                        except OSError:
                            mtime_age = 0.0

                        if is_dead_holder or (is_expired_holder and mtime_age > self.stale_timeout):
                            logger.warning(
                                "Breaking stale lock on %s (holder pid=%s alive=%s, age=%.1fs > %.1fs)",
                                self.lock_path,
                                holder_pid,
                                not is_dead_holder,
                                mtime_age,
                                self.stale_timeout,
                            )
                            try:
                                os.close(self.fd)
                            except OSError:
                                pass
                            try:
                                os.unlink(self.lock_path)
                            except OSError:
                                pass
                            self.fd = os.open(self.lock_path, flags, 0o644)
                            continue

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
                            break
                        time.sleep(self.poll_interval)
            elif msvcrt is not None:
                start_time = time.monotonic()
                while True:
                    try:
                        os.lseek(self.fd, 0, os.SEEK_SET)
                        msvcrt.locking(self.fd, msvcrt.LK_NBLCK, 1)
                        self.acquired = True
                        try:
                            os.ftruncate(self.fd, 0)
                            os.lseek(self.fd, 0, os.SEEK_SET)
                            meta_bytes = f"pid={os.getpid()}\ntime={time.time()}\n".encode("utf-8")
                            os.write(self.fd, meta_bytes)
                        except OSError:
                            pass
                        break
                    except (BlockingIOError, OSError) as exc:
                        if exc.errno not in (errno.EACCES, getattr(errno, "EDEADLK", 36), getattr(errno, "EAGAIN", 11)):
                            raise
                        holder_pid, holder_ts = read_lock_metadata(self.lock_path)
                        if holder_pid is not None and not is_pid_alive(holder_pid):
                            logger.warning("Breaking stale Windows lock on %s (pid %s dead)", self.lock_path, holder_pid)
                            try:
                                os.close(self.fd)
                                os.unlink(self.lock_path)
                            except OSError:
                                pass
                            self.fd = os.open(self.lock_path, flags, 0o644)
                            continue
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
                            break
                        time.sleep(self.poll_interval)
            else:
                self.acquired = True

            self._local.depths[self.lock_path] = 1
            self._local.fds[self.lock_path] = self.fd
            return self
        except BaseException:
            if self.fd is not None:
                try:
                    os.close(self.fd)
                except OSError:
                    pass
                self.fd = None
            self.acquired = False
            self._thread_lock.release()
            raise

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        try:
            depth = getattr(self._local, "depths", {}).get(self.lock_path, 0)
            if depth > 1:
                self._local.depths[self.lock_path] = depth - 1
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
        finally:
            self._thread_lock.release()


def get_lock_path(target_path: Union[str, Path]) -> Path:
    """Return a deterministic temporary lock file path for a target file path."""
    dest = Path(target_path).resolve()
    digest = hashlib.sha256(str(dest).encode("utf-8")).hexdigest()[:16]
    return Path(tempfile.gettempdir()) / f".ev_atomic_{digest}.lock"


def cleanup_stale_temp_files(
    directory: Union[str, Path],
    prefix: Union[str, tuple[str, ...], list[str]] = (".tmp_", ".tmp_subsidy_", ".tmp_daily_"),
    max_age_seconds: float = 3600.0,
) -> int:
    """Defensively unlink orphaned temporary files older than max_age_seconds."""
    d = Path(directory)
    if not d.is_dir():
        return 0
    cleaned = 0
    now = time.time()
    prefixes = (prefix,) if isinstance(prefix, str) else tuple(prefix)
    try:
        for entry in d.iterdir():
            if any(entry.name.startswith(p) for p in prefixes) and entry.is_file():
                try:
                    if (now - entry.stat().st_mtime) > max_age_seconds:
                        entry.unlink(missing_ok=True)
                        cleaned += 1
                except OSError:
                    pass
    except OSError:
        pass
    return cleaned


def cleanup_stale_lock_files(
    directory: Union[str, Path],
    prefix: Union[str, tuple[str, ...], list[str]] = (".ev_atomic_", ".sync_", ".subsidy_"),
    suffix: str = ".lock",
    max_age_seconds: float = 3600.0,
) -> int:
    """Defensively clean up orphaned advisory lock files older than max_age_seconds if unheld."""
    d = Path(directory)
    if not d.is_dir():
        return 0
    cleaned = 0
    now = time.time()
    prefixes = (prefix,) if isinstance(prefix, str) else tuple(prefix)
    try:
        for entry in d.iterdir():
            if not entry.is_file():
                continue
            if not entry.name.endswith(suffix):
                continue
            if not any(entry.name.startswith(p) for p in prefixes):
                continue
            try:
                st = entry.stat()
                age = now - st.st_mtime
                if age <= max_age_seconds:
                    continue

                # Check if file has an active holder
                holder_pid, holder_ts = read_lock_metadata(entry)
                if holder_pid and is_pid_alive(holder_pid) and age < (max_age_seconds * 2):
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
                else:
                    entry.unlink(missing_ok=True)
                    cleaned += 1
            except OSError:
                pass
    except OSError:
        pass
    return cleaned


def is_corrupted_or_quarantined_filename(filename_or_path: Union[str, Path]) -> bool:
    """Return True if filename indicates a quarantined or corrupted payload."""
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
    Guarantees atomic replace, cross-device EXDEV fallback, POSIX directory fsync durability,
    and standard permissions (0o644).
    """
    p = Path(file_path)
    if not p.exists() or p.is_dir():
        return None
    try:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        if suffix:
            s = suffix if suffix.startswith(".") else f".{suffix}"
            if s == ".corrupted":
                quarantine_path = p.with_name(f"{p.stem}.corrupt_{ts}.corrupted")
            else:
                quarantine_path = p.with_name(f"{p.stem}{s}")
        else:
            quarantine_path = p.with_name(f"{p.stem}.corrupt_{ts}{p.suffix}")

        try:
            os.replace(str(p), str(quarantine_path))
        except OSError as exc:
            if exc.errno == errno.EXDEV:
                shutil.copyfile(str(p), str(quarantine_path))
                try:
                    with open(quarantine_path, "a+b") as qf:
                        os.fsync(qf.fileno())
                except OSError:
                    pass
                try:
                    os.unlink(str(p))
                except OSError:
                    pass
            else:
                raise

        try:
            os.chmod(quarantine_path, 0o644)
        except OSError:
            pass

        # Directory fsync to ensure quarantine rename is crash-durably committed
        try:
            dir_fd = os.open(str(p.parent), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass

        logger.warning("Quarantined corrupted file: %s -> %s", p, quarantine_path)
        return quarantine_path
    except OSError as exc:
        logger.warning("Failed to quarantine corrupted file %s: %s", p, exc)
        return None


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
        if obj.is_nan() or obj.is_infinite():
            return 0.0
        return float(obj)
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
        return obj.value
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
                elif isinstance(k, (date, datetime)):
                    sanitized_k = k.isoformat()
                elif isinstance(k, Enum):
                    sanitized_k = str(k.value)
                elif isinstance(k, Path):
                    sanitized_k = str(k)
                elif isinstance(k, uuid.UUID):
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
        return obj.value
    if isinstance(obj, Decimal):
        if obj.is_nan() or obj.is_infinite():
            return 0.0
        return float(obj)
    if isinstance(obj, complex):
        real_val = 0.0 if (math.isnan(obj.real) or math.isinf(obj.real)) else float(obj.real)
        imag_val = 0.0 if (math.isnan(obj.imag) or math.isinf(obj.imag)) else float(obj.imag)
        return {"real": real_val, "imag": imag_val}
    if isinstance(obj, (bytes, bytearray)):
        return obj.decode("utf-8", errors="replace")
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if hasattr(obj, "to_dict") and callable(getattr(obj, "to_dict")):
        return sanitize_nan_inf(obj.to_dict())
    if hasattr(obj, "as_dict") and callable(getattr(obj, "as_dict")):
        return sanitize_nan_inf(obj.as_dict())
    if hasattr(obj, "model_dump") and callable(getattr(obj, "model_dump")):
        return sanitize_nan_inf(obj.model_dump())
    if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
        return sanitize_nan_inf(obj.dict())
    if hasattr(obj, "tolist") and callable(getattr(obj, "tolist")):
        return sanitize_nan_inf(obj.tolist())
    if hasattr(obj, "item") and callable(getattr(obj, "item")):
        return sanitize_nan_inf(obj.item())
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return sanitize_nan_inf(dataclasses.asdict(obj))
    if isinstance(obj, Mapping):
        return {k: sanitize_nan_inf(v) for k, v in obj.items()}
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


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

    Returns:
        Path: The absolute path of the written file.
    """
    if not target_path or not str(target_path).strip():
        raise ValueError("target_path cannot be empty")
    dest = Path(target_path).resolve()
    dest_dir = dest.parent
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Convert object with to_dict / as_dict / model_dump / dataclass if present
    if hasattr(data, "to_dict") and callable(getattr(data, "to_dict")):
        payload = data.to_dict()
    elif hasattr(data, "as_dict") and callable(getattr(data, "as_dict")):
        payload = data.as_dict()
    elif hasattr(data, "model_dump") and callable(getattr(data, "model_dump")):
        payload = data.model_dump()
    elif dataclasses.is_dataclass(data) and not isinstance(data, type):
        payload = dataclasses.asdict(data)
    else:
        payload = data

    payload = sanitize_nan_inf(payload)

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

    with FileLock(lock_file):
        try:
            cleanup_stale_temp_files(dest_dir, prefix=temp_prefix, max_age_seconds=3600.0)
            cleanup_stale_lock_files(dest_dir, max_age_seconds=3600.0)
            cleanup_stale_lock_files(tempfile.gettempdir(), max_age_seconds=3600.0)

            # Create temp file in the same directory to ensure atomic os.replace across filesystem boundaries
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
                os.fsync(tf.fileno())

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

            try:
                os.replace(temp_name, dest)
            except OSError as exc:
                if exc.errno == errno.EXDEV:
                    # Fallback for cross-device or overlayfs filesystems
                    shutil.copyfile(temp_name, str(dest))
                    try:
                        with open(dest, "a+b") as df:
                            os.fsync(df.fileno())
                    except OSError:
                        pass
                    try:
                        os.unlink(temp_name)
                    except OSError:
                        pass
                else:
                    raise

            temp_name = None  # Replaced or copied successfully

            if preserve_mtime is not None:
                try:
                    os.utime(dest, (preserve_mtime, preserve_mtime))
                except OSError:
                    pass

            # Directory fsync to commit the replacement to disk with leak-proof fd lifecycle
            try:
                dir_fd = os.open(str(dest_dir), os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
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
    """Atomically write data as JSON to multiple target paths."""
    written_paths: List[Path] = []
    for p in target_paths:
        written = atomic_write_json(
            data,
            p,
            indent=indent,
            ensure_ascii=ensure_ascii,
            default=default,
            preserve_mtime=preserve_mtime,
            mode=mode,
            preserve_permissions=preserve_permissions,
        )
        written_paths.append(written)
    return written_paths

