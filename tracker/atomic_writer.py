"""POSIX crash-durable atomic JSON writer.

Provides transactional file write guarantees via NamedTemporaryFile, flush,
fsync, and atomic rename (os.replace).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
import json
import logging
import os
from pathlib import Path
import tempfile
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


def _json_default(obj: Any) -> Any:
    """Serialize Path, datetime, date, set, Enum, and to_dict objects to valid JSON primitives."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, set):
        return list(obj)
    if isinstance(obj, Enum):
        return obj.value
    if hasattr(obj, "to_dict") and callable(getattr(obj, "to_dict")):
        return obj.to_dict()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def atomic_write_json(
    data: Any,
    target_path: Union[str, Path],
    indent: int = 2,
    ensure_ascii: bool = False,
    default: Optional[Callable[[Any], Any]] = None,
) -> Path:
    """Atomically write data as JSON to target_path using crash-durable semantics.

    Steps:
    1. Resolve target directory and create if not existing.
    2. Write JSON to NamedTemporaryFile in the same filesystem directory.
    3. Flush application buffers and issue OS fsync on file descriptor.
    4. Atomically swap temp file with target using os.replace.
    5. Clean up temporary file in finally block if replacement fails.

    Args:
        data: Python dictionary, list, or object providing a `to_dict()` method.
        target_path: Target destination path.
        indent: JSON indentation spaces.
        ensure_ascii: Whether to escape non-ASCII characters.
        default: Optional custom serializer function. Defaults to `_json_default`.

    Returns:
        Path: The absolute path of the written file.
    """
    dest = Path(target_path).resolve()
    dest_dir = dest.parent
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Convert object with to_dict if present
    if hasattr(data, "to_dict") and callable(getattr(data, "to_dict")):
        payload = data.to_dict()
    else:
        payload = data

    serializer = default if default is not None else _json_default
    temp_name: Optional[str] = None
    try:
        # Create temp file in the same directory to ensure atomic os.replace across filesystem boundaries
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=str(dest_dir),
            delete=False,
            encoding="utf-8",
            prefix=".tmp_subsidy_",
            suffix=".json",
        ) as tf:
            temp_name = tf.name
            json.dump(payload, tf, ensure_ascii=ensure_ascii, indent=indent, default=serializer)
            tf.flush()
            os.fsync(tf.fileno())

        try:
            os.chmod(temp_name, 0o644)
        except OSError:
            pass
        os.replace(temp_name, dest)
        temp_name = None  # Replaced successfully
        logger.debug("Atomically wrote %s", dest)
        return dest
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
) -> List[Path]:
    """Atomically write data as JSON to multiple target paths."""
    written_paths: List[Path] = []
    for p in target_paths:
        written = atomic_write_json(data, p, indent=indent, ensure_ascii=ensure_ascii, default=default)
        written_paths.append(written)
    return written_paths
