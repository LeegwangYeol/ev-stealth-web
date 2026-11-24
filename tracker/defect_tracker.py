"""tracker/defect_tracker.py - OOP Defect Tracking and Query Management Engine.

Provides clean OOP abstractions for:
- Synchronizing daily defect reports across root and web datasets with atomic safety and JSON/schema validation.
- Querying and filtering defect reports by category, vehicle brand/model, severity, and keyword.
- Integrating ScraperPipeline and ContextualDefectFilter for end-to-end defect harvesting and processing.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
import dataclasses
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import shutil
import tempfile
import threading
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import unicodedata

logger = logging.getLogger("defect_tracker")

_SEVERITY_TIER_MAP: Dict[str, float] = {
    "CRITICAL": 9.0,
    "HIGH": 7.0,
    "WARNING": 7.0,
    "MEDIUM": 5.0,
    "CAUTION": 4.0,
    "LOW": 3.0,
    "INFO": 1.0,
}


def _norm_text(val: Any) -> str:
    """Unwrap Enum values and normalize non-ASCII text (e.g. Hangul NFD/NFC) to NFC."""
    unwrapped = getattr(val, "value", val)
    if unwrapped is None:
        return ""
    text = unwrapped if isinstance(unwrapped, str) else str(unwrapped)
    return text if text.isascii() else unicodedata.normalize("NFC", text)


def _extract_category(obj: Any, uppercase: bool = True, allow_non_str: bool = False) -> str:
    """Extract normalized defect category, falling back across keys if blank/whitespace."""
    for key in ("defect_category", "category"):
        raw_cat = _extract_val(obj, key)
        raw_cat = getattr(raw_cat, "value", raw_cat)
        if raw_cat is None:
            continue
        if isinstance(raw_cat, str):
            stripped = _norm_text(raw_cat).strip()
            if stripped:
                return stripped.upper() if uppercase else stripped
        elif allow_non_str:
            stripped = _norm_text(raw_cat).strip()
            if stripped:
                return stripped.upper() if uppercase else stripped
    return "UNKNOWN"


def _extract_val(obj: Any, key: str, default: Any = None) -> Any:
    """Safely extract field from either a dict/Mapping, a domain object, or a sequence."""
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        val = obj.get(key, default)
    elif hasattr(obj, key):
        val = getattr(obj, key, default)
    elif hasattr(obj, "__getitem__"):
        try:
            val = obj[key]
        except (KeyError, TypeError, IndexError):
            val = default
    else:
        val = default
    return default if val is None else val


def _extract_first_non_blank(obj: Any, *keys: str) -> str:
    """Return the first non-None, non-whitespace-only normalized text value across candidate keys."""
    for key in keys:
        val = _extract_val(obj, key)
        if val is None:
            continue
        text = _norm_text(val)
        if text.strip():
            return text
    return ""


def _to_record_dict(obj: Any) -> Dict[str, Any]:
    """Convert a defect record (dict or domain object) safely to a dictionary."""
    if obj is None:
        return {}
    if isinstance(obj, Mapping):
        return dict(obj)
    if hasattr(obj, "to_admin_report_dict") and callable(getattr(obj, "to_admin_report_dict")):
        return obj.to_admin_report_dict()
    if hasattr(obj, "to_dict") and callable(getattr(obj, "to_dict")):
        return obj.to_dict()
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    try:
        return dict(obj)
    except Exception:
        out: Dict[str, Any] = {}
        for k in dir(obj):
            if k.startswith("_"):
                continue
            try:
                val = getattr(obj, k)
            except Exception:
                continue
            if not callable(val):
                out[k] = val
        return out


_CURRENT_DIR = Path(__file__).resolve().parent


def _find_repo_root() -> Path:
    """Locate canonical repository root from module file location and active working directory."""
    candidates = [
        _CURRENT_DIR,
        _CURRENT_DIR.parent,
        _CURRENT_DIR.parent.parent,
        Path.cwd(),
        Path.cwd().parent,
    ]
    for c in candidates:
        if (c / "data").is_dir() and (c / "ev-stealth-web").is_dir():
            return c
    for c in candidates:
        if (c / "data").is_dir() or (c / "ev-stealth-web" / "src" / "data").is_dir():
            return c
    return _CURRENT_DIR.parent


def _is_project_data_dir(path: Path, cwd: Path) -> bool:
    """Check if the path points to the real project data directory."""
    try:
        resolved = path.resolve()
        repo_root = _find_repo_root()
        candidate_dirs = [
            repo_root / "data",
            repo_root / "ev-stealth-web" / "src" / "data",
            repo_root / "ev-stealth-web" / "public" / "data",
            repo_root / "public" / "data",
            cwd / "data",
            cwd.parent / "data",
            cwd / "ev-stealth-web" / "src" / "data",
            cwd / "src" / "data",
        ]
        for cand in candidate_dirs:
            if cand.exists() and resolved == cand.resolve():
                return True
    except Exception:
        pass
    return False

try:
    from run_scraper import ScraperPipeline
except ImportError:
    try:
        from ev_stealth_web.run_scraper import ScraperPipeline  # type: ignore
    except ImportError:
        ScraperPipeline = None

try:
    from filters.defect_filter import ContextualDefectFilter
except ImportError:
    try:
        from ev_stealth_web.filters.defect_filter import ContextualDefectFilter  # type: ignore
    except ImportError:
        ContextualDefectFilter = None

try:
    from models.complaint import ComplaintRecord, RawPost
except ImportError:
    try:
        from ev_stealth_web.models.complaint import ComplaintRecord, RawPost  # type: ignore
    except ImportError:
        ComplaintRecord = None  # type: ignore
        RawPost = None  # type: ignore


class DefectTracker:
    """Clean OOP Engine for syncing, querying, filtering, and reporting EV defect reports."""

    def __init__(
        self,
        root_data_dir: Optional[Union[str, Path]] = None,
        web_data_dir: Optional[Union[str, Path]] = None,
        public_data_dir: Optional[Union[str, Path]] = None,
        pipeline: Optional[Any] = None,
        filter_engine: Optional[Any] = None,
        reports_file: Optional[Union[str, Path]] = None,
        base_dir: Optional[Union[str, Path]] = None,
        **kwargs: Any,
    ) -> None:
        self.reports_file: Optional[Path] = (
            Path(reports_file) if reports_file and str(reports_file).strip() else None
        )
        repo_root = _find_repo_root()
        cwd = Path.cwd()
        if root_data_dir:
            self.root_data_dir = Path(root_data_dir)
        elif (repo_root / "data").exists():
            self.root_data_dir = repo_root / "data"
        elif (cwd / "data").exists():
            self.root_data_dir = cwd / "data"
        elif (cwd.parent / "data").exists():
            self.root_data_dir = cwd.parent / "data"
        else:
            self.root_data_dir = repo_root / "data"

        if web_data_dir:
            self.web_data_dir = Path(web_data_dir)
        elif (repo_root / "ev-stealth-web" / "src" / "data").exists():
            self.web_data_dir = repo_root / "ev-stealth-web" / "src" / "data"
        elif (cwd / "src" / "data").exists():
            self.web_data_dir = cwd / "src" / "data"
        elif (cwd / "ev-stealth-web" / "src" / "data").exists():
            self.web_data_dir = cwd / "ev-stealth-web" / "src" / "data"
        else:
            self.web_data_dir = repo_root / "ev-stealth-web" / "src" / "data"

        if public_data_dir:
            self.public_data_dir: Optional[Path] = Path(public_data_dir)
        elif web_data_dir and (Path(web_data_dir).parent / "public" / "data").exists():
            self.public_data_dir = Path(web_data_dir).parent / "public" / "data"
        elif web_data_dir and (Path(web_data_dir).parent.parent / "public" / "data").exists():
            self.public_data_dir = Path(web_data_dir).parent.parent / "public" / "data"
        elif root_data_dir is not None and not _is_project_data_dir(self.root_data_dir, cwd):
            self.public_data_dir = None
        elif (repo_root / "ev-stealth-web" / "public" / "data").exists():
            self.public_data_dir = repo_root / "ev-stealth-web" / "public" / "data"
        elif (repo_root / "public" / "data").exists():
            self.public_data_dir = repo_root / "public" / "data"
        elif (cwd / "ev-stealth-web" / "public" / "data").exists():
            self.public_data_dir = cwd / "ev-stealth-web" / "public" / "data"
        elif (cwd / "public" / "data").exists():
            self.public_data_dir = cwd / "public" / "data"
        elif (cwd.parent / "ev-stealth-web" / "public" / "data").exists():
            self.public_data_dir = cwd.parent / "ev-stealth-web" / "public" / "data"
        else:
            self.public_data_dir = None

        self._pipeline = pipeline
        self._filter_engine = filter_engine

        # Caching and category pre-filtering index structures (thread-safe LRU)
        self._cache_lock = threading.Lock()
        self._cached_reports_mtime: Optional[float] = None
        self._cached_reports_sig: Optional[Tuple[int, int]] = None
        self._cached_reports_path: Optional[Path] = None
        self._cached_is_primary: bool = False
        self._cached_reports: Optional[List[Dict[str, Any]]] = None
        self._cached_full_data: Optional[Dict[str, Any]] = None
        self._category_index: Dict[str, List[Dict[str, Any]]] = {}
        self._query_cache: OrderedDict[Tuple[Any, ...], List[Dict[str, Any]]] = OrderedDict()

    @property
    def pipeline(self) -> Any:
        """Lazily initialize ScraperPipeline if not explicitly provided."""
        if self._pipeline is None and ScraperPipeline is not None:
            self._pipeline = ScraperPipeline()
        return self._pipeline

    @pipeline.setter
    def pipeline(self, pipeline: Any) -> None:
        self._pipeline = pipeline

    @property
    def filter_engine(self) -> Any:
        """Lazily initialize ContextualDefectFilter if not explicitly provided."""
        if self._filter_engine is None and ContextualDefectFilter is not None:
            self._filter_engine = ContextualDefectFilter()
        return self._filter_engine

    @filter_engine.setter
    def filter_engine(self, engine: Any) -> None:
        self._filter_engine = engine

    @staticmethod
    def _validate_report_payload(data: Any) -> bool:
        """Return True if parsed JSON payload is a dict with a 'reports' list of dicts."""
        return (
            isinstance(data, dict)
            and "reports" in data
            and isinstance(data["reports"], list)
            and all(isinstance(r, dict) for r in data["reports"])
        )

    @classmethod
    def _validate_and_load_report_file(
        cls, file_path: Optional[Union[str, Path]]
    ) -> Optional[Dict[str, Any]]:
        """Validate and parse target report JSON file in a single pass, returning parsed dict or None."""
        from tracker.atomic_writer import is_corrupted_or_quarantined_filename

        if not file_path or not str(file_path).strip():
            return None
        p: Optional[Path] = None
        try:
            p = Path(file_path)
            if is_corrupted_or_quarantined_filename(p):
                return None
            if not p.is_file() or p.stat().st_size == 0:
                return None
            with open(p, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            if not cls._validate_report_payload(data):
                return None
            return data
        except Exception as exc:
            logger.warning("Defect report validation failed for %s: %s", p or file_path, exc)
            return None

    @classmethod
    def _validate_report_bytes(cls, raw_bytes: bytes) -> bool:
        """Validate already-read report bytes in memory without re-opening the file."""
        if not raw_bytes:
            return False
        try:
            data = json.loads(raw_bytes.decode("utf-8-sig"))
            return cls._validate_report_payload(data)
        except Exception:
            return False

    @staticmethod
    def validate_report_file(file_path: Optional[Union[str, Path]]) -> bool:
        """Validate that target file exists, contains valid JSON, and has a 'reports' list key."""
        return DefectTracker._validate_and_load_report_file(file_path) is not None

    def get_root_reports_path(self) -> Path:
        """Resolve path to root daily_reports.json."""
        return self.root_data_dir / "daily_reports.json"

    def get_web_reports_path(self) -> Path:
        """Resolve path to web daily_reports.json."""
        return self.web_data_dir / "daily_reports.json"

    def get_public_reports_path(self) -> Optional[Path]:
        """Resolve path to public daily_reports.json."""
        if self.public_data_dir:
            return self.public_data_dir / "daily_reports.json"
        return None

    def _candidate_report_paths_by_mtime(self) -> List[Path]:
        """Return existing candidate report paths sorted by mtime descending (without parsing JSON)."""
        existing: List[Tuple[float, Path]] = []
        for p in (self.get_root_reports_path(), self.get_web_reports_path(), self.get_public_reports_path()):
            if p is None:
                continue
            try:
                if p.is_file():
                    existing.append((p.stat().st_mtime, p))
            except OSError:
                continue
        existing.sort(key=lambda item: item[0], reverse=True)
        return [cand for _, cand in existing]

    def _resolve_and_load_primary_reports(self) -> Tuple[Optional[Path], Optional[Dict[str, Any]]]:
        """Resolve active authoritative defect reports file and return (path, data) from one JSON parse."""
        if self.reports_file:
            loaded = self._validate_and_load_report_file(self.reports_file)
            if loaded is not None:
                return self.reports_file, loaded

        for cand in self._candidate_report_paths_by_mtime():
            loaded = self._validate_and_load_report_file(cand)
            if loaded is not None:
                return cand, loaded
        return None, None

    def resolve_primary_reports_path(self) -> Optional[Path]:
        """Find the active authoritative defect reports file between root, web, and public."""
        if self.reports_file and self.validate_report_file(self.reports_file):
            return self.reports_file

        for cand in self._candidate_report_paths_by_mtime():
            if self.validate_report_file(cand):
                return cand
        return None

    def load_full_report_data(
        self,
        file_path: Optional[Union[str, Path]] = None,
        quarantine_corrupted: bool = True,
    ) -> Dict[str, Any]:
        """Load complete defect report dataset including statistics and metadata."""
        from tracker.atomic_writer import (
            FileLock,
            get_lock_path,
            is_corrupted_or_quarantined_filename,
            quarantine_corrupted_file,
        )

        if file_path is not None and not str(file_path).strip():
            return {"reports": [], "statistics": {}}

        try:
            target = Path(file_path) if file_path else self.resolve_primary_reports_path()
            target_exists = bool(target and target.exists())
        except (OSError, ValueError) as exc:
            logger.warning("Invalid defect report path %r: %s", file_path, exc)
            return {"reports": [], "statistics": {}}

        if not target or not target_exists:
            logger.warning("No defect report file found to load.")
            return {"reports": [], "statistics": {}}

        if is_corrupted_or_quarantined_filename(target):
            logger.error("Target defect report file %s is marked as corrupted/quarantined.", target)
            return {"reports": [], "statistics": {}}

        def _read_and_validate() -> Dict[str, Any]:
            if not target.is_file() or target.stat().st_size == 0:
                raise ValueError(f"Defect report file {target} is missing, a directory, or empty.")
            with open(target, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            if (
                not isinstance(data, dict)
                or "reports" not in data
                or not isinstance(data.get("reports"), list)
                or not all(isinstance(r, dict) for r in data["reports"])
            ):
                raise ValueError(f"Defect report file {target} failed post-read schema validation.")
            return data

        try:
            return _read_and_validate()
        except Exception as exc:
            logger.error("Failed to read defect report %s: %s", target, exc)
            if quarantine_corrupted:
                lock_file = get_lock_path(target)
                with FileLock(lock_file, timeout=5.0, fail_on_timeout=False):
                    if target.exists() and not is_corrupted_or_quarantined_filename(target):
                        try:
                            return _read_and_validate()
                        except Exception:
                            quarantine_corrupted_file(target)
            return {"reports": [], "statistics": {}}

    def invalidate_cache(self) -> None:
        """Invalidate in-memory report cache, category index, and query results."""
        with self._cache_lock:
            self._cached_reports_mtime = None
            self._cached_reports_sig = None
            self._cached_reports_path = None
            self._cached_is_primary = False
            self._cached_reports = None
            self._cached_full_data = None
            self._category_index.clear()
            self._query_cache.clear()

    def _build_category_index(self, reports: List[Any]) -> None:
        """Pre-filter and index defect reports into category buckets for O(1) candidate lookup."""
        self._category_index.clear()
        for r in reports:
            cat_norm = _extract_category(r, uppercase=True, allow_non_str=False)
            if cat_norm not in self._category_index:
                self._category_index[cat_norm] = []
            self._category_index[cat_norm].append(r)

    def _ensure_reports_loaded(
        self,
        file_path: Optional[Union[str, Path]] = None,
        copy_dicts: bool = False,
    ) -> Optional[List[Dict[str, Any]]]:
        """Ensure in-memory report cache and category index are up to date; optionally return copied dicts."""
        is_primary = file_path is None
        if file_path is not None and (not str(file_path).strip() or "\x00" in str(file_path)):
            return [] if copy_dicts else None

        can_fast_primary = (
            is_primary
            and "resolve_primary_reports_path" not in self.__dict__
            and type(self).resolve_primary_reports_path is DefectTracker.resolve_primary_reports_path
            and "validate_report_file" not in self.__dict__
            and type(self).validate_report_file is DefectTracker.validate_report_file
            and "load_full_report_data" not in self.__dict__
            and type(self).load_full_report_data is DefectTracker.load_full_report_data
        )

        # Fast stat-only cache hit check for primary path before any JSON parsing
        if can_fast_primary:
            with self._cache_lock:
                cached_path = self._cached_reports_path if (self._cached_reports is not None and self._cached_is_primary) else None
                cached_mtime = self._cached_reports_mtime
                cached_sig = self._cached_reports_sig
            if cached_path is not None:
                newest_candidates = self._candidate_report_paths_by_mtime()
                expected_primary = self.reports_file if (self.reports_file and self.reports_file.is_file()) else (newest_candidates[0] if newest_candidates else None)
                if expected_primary is not None:
                    try:
                        expected_resolved = expected_primary.resolve()
                    except (OSError, ValueError):
                        expected_resolved = expected_primary
                    if expected_resolved == cached_path:
                        try:
                            cur_stat = cached_path.stat()
                            if cur_stat.st_mtime == cached_mtime and (cur_stat.st_mtime_ns, cur_stat.st_size) == cached_sig:
                                with self._cache_lock:
                                    if (
                                        self._cached_reports is not None
                                        and self._cached_reports_path == cached_path
                                        and self._cached_reports_mtime == cached_mtime
                                        and self._cached_reports_sig == cached_sig
                                    ):
                                        return [_to_record_dict(r) for r in self._cached_reports] if copy_dicts else None
                        except (OSError, ValueError):
                            pass

        preloaded_data: Optional[Dict[str, Any]] = None
        try:
            if file_path is not None:
                raw_target = Path(file_path)
            elif can_fast_primary:
                raw_target, preloaded_data = self._resolve_and_load_primary_reports()
            else:
                raw_target = self.resolve_primary_reports_path()
        except (OSError, ValueError):
            return [] if copy_dicts else None
        target: Optional[Path] = None
        if raw_target is not None:
            try:
                target = raw_target.resolve()
            except (OSError, ValueError):
                target = raw_target

        pre_stat: Optional[os.stat_result] = None
        target_exists = False
        if target:
            try:
                target_exists = target.exists()
            except (OSError, ValueError):
                target_exists = False
        if target and target_exists:
            try:
                pre_stat = target.stat()
                current_mtime = pre_stat.st_mtime
                current_sig = (pre_stat.st_mtime_ns, pre_stat.st_size)
                with self._cache_lock:
                    if (
                        self._cached_reports is not None
                        and self._cached_reports_path == target
                        and self._cached_reports_mtime == current_mtime
                        and self._cached_reports_sig == current_sig
                    ):
                        if is_primary:
                            self._cached_is_primary = True
                        return [_to_record_dict(r) for r in self._cached_reports] if copy_dicts else None
            except (OSError, ValueError):
                pre_stat = None

        data = preloaded_data if preloaded_data is not None else self.load_full_report_data(file_path=target)
        reports = data.get("reports", [])

        with self._cache_lock:
            post_exists = False
            if target:
                try:
                    post_exists = target.exists()
                except (OSError, ValueError):
                    post_exists = False
            if target and post_exists:
                try:
                    post_stat = target.stat()
                    # Guard against TOCTOU: if file changed while reading, retain pre_stat so next read reloads
                    effective_stat = (
                        pre_stat
                        if (
                            pre_stat is not None
                            and (post_stat.st_mtime_ns != pre_stat.st_mtime_ns or post_stat.st_size != pre_stat.st_size)
                        )
                        else post_stat
                    )
                    self._cached_reports_mtime = effective_stat.st_mtime
                    self._cached_reports_sig = (effective_stat.st_mtime_ns, effective_stat.st_size)
                    self._cached_reports_path = target
                    self._cached_is_primary = is_primary
                except (OSError, ValueError):
                    self._cached_reports_mtime = None
                    self._cached_reports_sig = None
                    self._cached_reports_path = None
                    self._cached_is_primary = False
            else:
                self._cached_reports_mtime = None
                self._cached_reports_sig = None
                self._cached_reports_path = None
                self._cached_is_primary = False

            self._cached_reports = reports
            self._cached_full_data = data
            self._build_category_index(reports)
            self._query_cache.clear()
            return [_to_record_dict(r) for r in self._cached_reports] if copy_dicts else None

    def load_reports(self, file_path: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
        """Load and return list of defect reports from target or primary path with mtime caching."""
        result = self._ensure_reports_loaded(file_path=file_path, copy_dicts=True)
        return result if result is not None else []

    def query_defects(
        self,
        category: Optional[str] = None,
        vehicle_brand: Optional[str] = None,
        vehicle_model: Optional[str] = None,
        min_severity: Optional[float] = None,
        keyword: Optional[str] = None,
        limit: Optional[int] = None,
        file_path: Optional[Union[str, Path]] = None,
        reports: Optional[Union[List[Any], List[Dict[str, Any]]]] = None,
    ) -> List[Dict[str, Any]]:
        """Query and filter defect reports with category pre-filtering and query caching."""
        norm_limit: Optional[int] = None
        if limit is not None and not isinstance(limit, bool):
            try:
                norm_limit = int(limit)
                if norm_limit <= 0:
                    return []
            except (ValueError, TypeError, OverflowError):
                norm_limit = None

        norm_min_sev: Optional[float] = None
        if min_severity is not None and not isinstance(min_severity, bool):
            try:
                f_sev = float(min_severity)
                norm_min_sev = f_sev if not (math.isnan(f_sev) or math.isinf(f_sev)) else None
            except (ValueError, TypeError, OverflowError):
                norm_min_sev = None

        candidate_source: Optional[List[Any]] = None
        if reports is None:
            if "load_reports" not in self.__dict__ and type(self).load_reports is DefectTracker.load_reports:
                if file_path is not None and (not str(file_path).strip() or "\x00" in str(file_path)):
                    return []
                self._ensure_reports_loaded(file_path=file_path, copy_dicts=False)
                use_cache = True
            else:
                candidate_source = self.load_reports(file_path=file_path)
                use_cache = False
        else:
            candidate_source = list(reports)
            use_cache = False

        cat_raw = getattr(category, "value", category)
        cat_upper = (
            _norm_text(cat_raw).strip().upper()
            if (cat_raw and isinstance(cat_raw, str) and cat_raw.strip())
            else None
        )
        brand_raw = getattr(vehicle_brand, "value", vehicle_brand)
        brand_lower = (
            _norm_text(brand_raw).strip().lower()
            if (brand_raw and isinstance(brand_raw, str) and brand_raw.strip())
            else None
        )
        model_raw = getattr(vehicle_model, "value", vehicle_model)
        model_lower = (
            _norm_text(model_raw).strip().lower()
            if (model_raw and isinstance(model_raw, str) and model_raw.strip())
            else None
        )
        kw_raw = getattr(keyword, "value", keyword)
        kw_lower = (
            _norm_text(kw_raw).strip().lower()
            if (kw_raw and isinstance(kw_raw, str) and kw_raw.strip())
            else None
        )

        resolved_req_path: Optional[Path] = None
        if file_path is not None:
            try:
                resolved_req_path = Path(file_path).resolve()
            except (OSError, ValueError):
                try:
                    resolved_req_path = Path(file_path)
                except (TypeError, ValueError):
                    return []

        cache_key: Optional[Tuple[Any, ...]] = None
        candidate_pool: Optional[List[Any]] = None
        if use_cache:
            with self._cache_lock:
                # Verify cache wasn't invalidated or swapped to a different file by another thread
                target_mismatch = (
                    (resolved_req_path is not None and self._cached_reports_path != resolved_req_path)
                    or (resolved_req_path is None and not self._cached_is_primary)
                )
                if self._cached_reports is None or target_mismatch:
                    use_cache = False
                else:
                    cache_key = (
                        str(self._cached_reports_path),
                        self._cached_reports_mtime,
                        self._cached_reports_sig,
                        cat_upper,
                        brand_lower,
                        model_lower,
                        norm_min_sev,
                        kw_lower,
                        norm_limit,
                    )
                    if cache_key in self._query_cache:
                        self._query_cache.move_to_end(cache_key)
                        return [dict(r) for r in self._query_cache[cache_key]]

                    # Category-level pre-filtering: use pre-indexed category bucket if specified
                    # Always source candidate_pool from the same atomic cache snapshot as cache_key
                    if cat_upper is not None:
                        candidate_pool = list(self._category_index.get(cat_upper, []))
                    else:
                        candidate_pool = list(self._cached_reports)

            if candidate_pool is None:
                candidate_pool = (
                    list(candidate_source)
                    if candidate_source is not None
                    else self.load_reports(file_path=file_path)
                )
        else:
            candidate_pool = list(candidate_source or [])

        filtered: List[Dict[str, Any]] = []

        for r in candidate_pool:
            # Category filter (re-verify for defensive assurance, normalizing missing/None to UNKNOWN)
            if cat_upper:
                item_cat = _extract_category(r, uppercase=True, allow_non_str=False)
                if item_cat != cat_upper:
                    continue

            # Brand filter
            if brand_lower:
                brand_val = _extract_first_non_blank(r, "vehicle_brand", "brand")
                if brand_lower not in brand_val.lower():
                    continue

            # Model filter
            if model_lower:
                model_val = _extract_first_non_blank(r, "vehicle_model", "model")
                if model_lower not in model_val.lower():
                    continue

            # Severity filter
            if norm_min_sev is not None:
                sev = _extract_val(r, "severity_index")
                effective_sev: Optional[float] = None
                if sev is not None and not isinstance(sev, bool):
                    try:
                        effective_sev = float(sev)
                        if math.isnan(effective_sev) or math.isinf(effective_sev):
                            effective_sev = None
                    except (ValueError, TypeError, OverflowError):
                        effective_sev = None

                if effective_sev is None:
                    raw_tier = _extract_first_non_blank(r, "severity", "severity_tier").strip().upper()
                    effective_sev = _SEVERITY_TIER_MAP.get(raw_tier, 0.0)

                if effective_sev < norm_min_sev:
                    continue

            # Keyword search across title, defect_topic, summary, verbatim_quote, and raw_quote
            if kw_lower:
                combined_text = _norm_text(
                    " ".join([
                        str(_extract_val(r, "title", "")),
                        str(_extract_val(r, "defect_topic", "")),
                        str(_extract_val(r, "summary", "")),
                        str(_extract_val(r, "verbatim_quote", "")),
                        str(_extract_val(r, "raw_quote", "")),
                    ])
                ).lower()
                if kw_lower not in combined_text:
                    continue

            filtered.append(r)
            if norm_limit is not None and len(filtered) >= norm_limit:
                break

        # Thread-safe true LRU cache with promotion and bounded eviction
        result = [_to_record_dict(r) for r in filtered]
        if use_cache and cache_key is not None:
            with self._cache_lock:
                if (
                    self._cached_reports is not None
                    and str(self._cached_reports_path) == cache_key[0]
                    and self._cached_reports_mtime == cache_key[1]
                    and self._cached_reports_sig == cache_key[2]
                ):
                    self._query_cache[cache_key] = result
                    self._query_cache.move_to_end(cache_key)
                    while len(self._query_cache) > 1024:
                        self._query_cache.popitem(last=False)

        return [dict(r) for r in result]

    def get_statistics(self, file_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """Return high-level statistics and category breakdown for defect reports."""
        full_data: Optional[Dict[str, Any]] = None
        if file_path is not None and (not str(file_path).strip() or "\x00" in str(file_path)):
            full_data = {"reports": [], "statistics": {}}
        elif (
            "load_full_report_data" not in self.__dict__
            and type(self).load_full_report_data is DefectTracker.load_full_report_data
        ):
            self._ensure_reports_loaded(file_path=file_path, copy_dicts=False)
            resolved_req_path: Optional[Path] = None
            if file_path is not None:
                try:
                    resolved_req_path = Path(file_path).resolve()
                except (OSError, ValueError):
                    try:
                        resolved_req_path = Path(file_path)
                    except (TypeError, ValueError):
                        full_data = {"reports": [], "statistics": {}}
            if full_data is None:
                with self._cache_lock:
                    target_mismatch = (
                        (resolved_req_path is not None and self._cached_reports_path != resolved_req_path)
                        or (resolved_req_path is None and not self._cached_is_primary)
                    )
                    if not target_mismatch:
                        full_data = self._cached_full_data
        if full_data is None:
            full_data = self.load_full_report_data(file_path=file_path)
        stats = _extract_val(full_data, "statistics")
        if stats and isinstance(stats, dict):
            stat_copy = dict(stats)
            for int_key in ("total_filtered_defects", "critical_defect_count"):
                raw_cnt = stat_copy.get(int_key)
                if raw_cnt is not None:
                    if isinstance(raw_cnt, bool):
                        stat_copy[int_key] = 0
                    else:
                        try:
                            f_cnt = float(raw_cnt)
                            stat_copy[int_key] = 0 if (math.isnan(f_cnt) or math.isinf(f_cnt)) else int(f_cnt)
                        except (ValueError, TypeError, OverflowError):
                            stat_copy[int_key] = 0
            raw_avg = stat_copy.get("avg_negativity_score")
            if raw_avg is not None:
                if isinstance(raw_avg, bool):
                    stat_copy["avg_negativity_score"] = 0.0
                else:
                    try:
                        f_avg = float(raw_avg)
                        if math.isnan(f_avg) or math.isinf(f_avg):
                            stat_copy["avg_negativity_score"] = 0.0
                        else:
                            rounded_avg = round(f_avg, 2)
                            stat_copy["avg_negativity_score"] = 0.0 if rounded_avg == 0.0 else rounded_avg
                    except (ValueError, TypeError, OverflowError):
                        stat_copy["avg_negativity_score"] = 0.0

            # Ensure category_distribution is always populated
            if "category_distribution" not in stat_copy or not isinstance(stat_copy["category_distribution"], dict):
                cat_dist: Dict[str, int] = {}
                fd_dist = _extract_val(full_data, "category_distribution")
                if fd_dist and isinstance(fd_dist, dict):
                    for k, v in fd_dist.items():
                        if isinstance(v, bool):
                            continue
                        try:
                            f_v = float(v)
                            if not (math.isnan(f_v) or math.isinf(f_v)):
                                cat_dist[str(k)] = int(f_v)
                        except (ValueError, TypeError, OverflowError):
                            pass
                elif _extract_val(full_data, "top_defect_categories"):
                    top_cats = _extract_val(full_data, "top_defect_categories")
                    if isinstance(top_cats, list):
                        for item in top_cats:
                            if isinstance(item, dict) and "category" in item and "count" in item:
                                raw_item_cnt = item["count"]
                                if isinstance(raw_item_cnt, bool):
                                    continue
                                try:
                                    f_v = float(raw_item_cnt)
                                    if not (math.isnan(f_v) or math.isinf(f_v)):
                                        cat_dist[str(item["category"])] = int(f_v)
                                except (ValueError, TypeError, OverflowError):
                                    pass
                    elif isinstance(top_cats, dict):
                        for k, v in top_cats.items():
                            if isinstance(v, bool):
                                continue
                            try:
                                f_v = float(v)
                                if not (math.isnan(f_v) or math.isinf(f_v)):
                                    cat_dist[str(k)] = int(f_v)
                            except (ValueError, TypeError, OverflowError):
                                pass

                if not cat_dist:
                    reports = _extract_val(full_data, "reports", [])
                    if isinstance(reports, (list, tuple)):
                        for r in reports:
                            cat = _extract_category(r, uppercase=False, allow_non_str=True)
                            cat_dist[cat] = cat_dist.get(cat, 0) + 1

                stat_copy["category_distribution"] = cat_dist
            else:
                stat_copy["category_distribution"] = dict(stat_copy["category_distribution"])

            return stat_copy

        # Compute on-the-fly from reports list
        reports = _extract_val(full_data, "reports", [])
        if not isinstance(reports, (list, tuple)):
            reports = []
        total = len(reports)
        critical_count = 0
        negativities: List[float] = []
        category_counts: Dict[str, int] = {}

        for r in reports:
            cat = _extract_category(r, uppercase=False, allow_non_str=True)
            category_counts[cat] = category_counts.get(cat, 0) + 1

            dsi = _extract_val(r, "severity_index")
            effective_dsi: Optional[float] = None
            if dsi is not None and not isinstance(dsi, bool):
                try:
                    f_dsi = float(dsi)
                    if not (math.isnan(f_dsi) or math.isinf(f_dsi)):
                        effective_dsi = f_dsi
                except (ValueError, TypeError, OverflowError):
                    effective_dsi = None

            sev_str = _extract_first_non_blank(r, "severity_tier", "severity").strip().upper()
            is_critical = (
                sev_str == "CRITICAL"
                or (effective_dsi is not None and effective_dsi >= 7.0)
            )
            if is_critical:
                critical_count += 1

            neg = _extract_val(r, "negativity_score")
            if neg is not None and not isinstance(neg, bool):
                try:
                    f_neg = float(neg)
                    if not (math.isnan(f_neg) or math.isinf(f_neg)):
                        negativities.append(f_neg)
                except (ValueError, TypeError, OverflowError):
                    pass

        avg_neg = (sum(negativities) / len(negativities)) if negativities else 0.0
        if math.isnan(avg_neg) or math.isinf(avg_neg):
            avg_neg = 0.0
        rounded_avg = round(avg_neg, 2)

        return {
            "total_filtered_defects": total,
            "critical_defect_count": critical_count,
            "avg_negativity_score": 0.0 if rounded_avg == 0.0 else rounded_avg,
            "category_distribution": category_counts,
        }

    def filter_raw_posts(self, raw_posts: Optional[List[Any]]) -> List[Any]:
        """Process raw posts through ContextualDefectFilter and return authentic defect complaints."""
        if not self.filter_engine:
            raise RuntimeError("ContextualDefectFilter is not available in environment.")
        if not raw_posts:
            return []

        filtered_defects: List[Any] = []
        for post_item in raw_posts:
            try:
                if RawPost is not None:
                    if isinstance(post_item, RawPost):
                        post_obj = post_item
                    elif isinstance(post_item, Mapping):
                        post_obj = RawPost.from_dict(dict(post_item))
                    else:
                        raw_comments = getattr(post_item, "comments", None)
                        if isinstance(raw_comments, str):
                            norm_comments = [raw_comments] if raw_comments.strip() else []
                        elif isinstance(raw_comments, (list, tuple)):
                            norm_comments = list(raw_comments)
                        else:
                            norm_comments = []
                        post_obj = RawPost(
                            platform=str(getattr(post_item, "platform", None) or "unknown"),
                            post_id=str(getattr(post_item, "post_id", None) or getattr(post_item, "id", None) or ""),
                            url=str(getattr(post_item, "url", None) or ""),
                            title=str(getattr(post_item, "title", None) or ""),
                            content=str(getattr(post_item, "content", None) or ""),
                            comments=norm_comments,
                            created_at=str(getattr(post_item, "created_at", None) or ""),
                            author=str(getattr(post_item, "author", None) or ""),
                        )
                    record = self.filter_engine.process_post(post_obj)
                else:
                    record = self.filter_engine.process_post(post_item)

                is_auth = getattr(record, "is_authentic_defect", False)
                if is_auth:
                    filtered_defects.append(record)
            except Exception as exc:
                p_id = (
                    (post_item.get("post_id") or post_item.get("id"))
                    if isinstance(post_item, Mapping)
                    else getattr(post_item, "post_id", getattr(post_item, "id", None))
                )
                logger.warning("Error filtering post %s: %s", p_id, exc)

        return filtered_defects

    def harvest_defects(self, sources: str = "all", limit: int = 20) -> Tuple[List[Any], Dict[str, Any]]:
        """Harvest and classify defect complaints using ScraperPipeline."""
        if not self.pipeline:
            raise RuntimeError("ScraperPipeline is not available in environment.")

        raw_posts, stats = self.pipeline.harvest(sources, limit=limit)
        defects = self.pipeline.filter_defects(raw_posts)
        return defects, stats

    def sync_defect_reports(
        self,
        web_dir: Optional[Union[str, Path]] = None,
        dry_run: bool = False,
        run_crawler: bool = False,
        quarantine_corrupted: bool = True,
        lock_timeout: float = 15.0,
        stale_timeout: float = 60.0,
    ) -> List[str]:
        """Synchronize defect reports between root data/, web src/data/, and public/data/ with atomic safety and validation.

        Validates source file JSON syntax and 'reports' key schema before any file replacement.
        Guarantees that corrupt files are NEVER propagated and isolates corrupted files when quarantine_corrupted is True.
        Protected by FileLock to eliminate concurrent sync races.
        """
        from tracker.atomic_writer import (
            FileLock,
            cleanup_stale_lock_files,
            durable_fsync,
            is_corrupted_or_quarantined_filename,
            quarantine_corrupted_file,
        )

        logger.info("DefectTracker: Synchronizing defect reports (daily_reports.json)...")
        if dry_run:
            logger.info("[DRY-RUN] DefectTracker sync skipped file persistence.")
            return []

        # Resolve paths
        has_web_dir = bool(web_dir and str(web_dir).strip())
        root_path = self.get_root_reports_path()
        web_path = (Path(web_dir) / "daily_reports.json") if has_web_dir else self.get_web_reports_path()

        public_path: Optional[Path] = None
        if has_web_dir and (Path(web_dir).parent / "public" / "data").exists():
            public_path = Path(web_dir).parent / "public" / "data" / "daily_reports.json"
        elif has_web_dir and (Path(web_dir).parent.parent / "public" / "data").exists():
            public_path = Path(web_dir).parent.parent / "public" / "data" / "daily_reports.json"
        else:
            public_path = self.get_public_reports_path()

        written_paths: List[str] = []
        quarantined_any = False
        sync_lock_path = root_path.parent / ".sync_defect_reports.lock"
        cleanup_stale_lock_files(root_path.parent, prefix=(".sync_",), max_age_seconds=stale_timeout)
        if web_path.parent != root_path.parent and web_path.parent.is_dir():
            cleanup_stale_lock_files(web_path.parent, prefix=(".sync_",), max_age_seconds=stale_timeout)

        try:
            with FileLock(sync_lock_path, timeout=lock_timeout, stale_timeout=stale_timeout):
                if run_crawler and self.pipeline:
                    try:
                        res = self.pipeline.run(
                            sources="all",
                            limit=10,
                            sync_web=True,
                            web_dir=web_dir,
                            dry_run=dry_run,
                        )
                        if isinstance(res, dict):
                            written_paths.extend(res.get("written_paths", []))
                    except Exception as exc:
                        logger.warning(
                            "Crawler execution in sync_defect_reports encountered: %s. Falling back to mirror synchronization.",
                            exc,
                        )

                known_paths: List[Path] = [p for p in [root_path, web_path, public_path] if p is not None]
                candidate_paths: List[Path] = [p for p in known_paths if p.exists()]

                def _safe_mtime(p: Path) -> float:
                    try:
                        return p.stat().st_mtime
                    except OSError:
                        return -1.0

                candidate_paths.sort(key=_safe_mtime, reverse=True)

                use_builtin_validator = (
                    "validate_report_file" not in self.__dict__
                    and type(self).validate_report_file is DefectTracker.validate_report_file
                )
                source_path: Optional[Path] = None
                cached_source_bytes: Optional[bytes] = None
                for cand in candidate_paths:
                    if is_corrupted_or_quarantined_filename(cand):
                        continue
                    if use_builtin_validator:
                        try:
                            if cand.is_file() and cand.stat().st_size > 0:
                                raw_bytes = cand.read_bytes()
                                if self._validate_report_bytes(raw_bytes):
                                    source_path = cand
                                    cached_source_bytes = raw_bytes
                                    break
                        except Exception as exc:
                            logger.warning("Defect report validation failed for %s: %s", cand, exc)
                    elif self.validate_report_file(cand):
                        source_path = cand
                        break
                    if quarantine_corrupted:
                        if quarantine_corrupted_file(cand) is not None:
                            quarantined_any = True

                if not source_path:
                    logger.error(
                        "No candidate defect report file is valid among %s. Aborting sync to prevent corruption propagation.",
                        candidate_paths,
                    )
                    return []

                target_paths: List[Path] = []
                seen_targets: Set[str] = {str(Path(source_path).resolve())}
                for p in known_paths:
                    resolved_p = str(Path(p).resolve())
                    if resolved_p not in seen_targets and (p.parent.exists() or p.parent.parent.exists()):
                        seen_targets.add(resolved_p)
                        target_paths.append(p)

                if source_path and target_paths:
                    try:
                        source_stat = source_path.stat()
                        source_bytes = cached_source_bytes if cached_source_bytes is not None else source_path.read_bytes()
                        source_hash = hashlib.sha256(source_bytes).hexdigest()
                    except Exception as e:
                        logger.error("Failed to inspect source defect report %s: %s", source_path, e)
                        return []

                    for tgt in target_paths:
                        if tgt.exists():
                            if is_corrupted_or_quarantined_filename(tgt):
                                continue
                            tgt_bytes: Optional[bytes] = None
                            try:
                                tgt_bytes = tgt.read_bytes()
                                h_tgt = hashlib.sha256(tgt_bytes).hexdigest()
                                if h_tgt == source_hash:
                                    try:
                                        tgt_stat = tgt.stat()
                                        if tgt_stat.st_mtime != source_stat.st_mtime:
                                            os.utime(tgt, (source_stat.st_atime, source_stat.st_mtime))
                                    except OSError:
                                        pass
                                    logger.debug("Skipping redundant defect report sync for %s (SHA-256 match)", tgt)
                                    continue
                            except Exception as e:
                                logger.warning("Error inspecting target %s: %s", tgt, e)

                            is_tgt_valid = (
                                self._validate_report_bytes(tgt_bytes)
                                if (use_builtin_validator and tgt_bytes is not None)
                                else self.validate_report_file(tgt)
                            )
                            if not is_tgt_valid:
                                if quarantine_corrupted:
                                    if quarantine_corrupted_file(tgt) is not None:
                                        quarantined_any = True

                        temp_name = None
                        try:
                            tgt.parent.mkdir(parents=True, exist_ok=True)
                            with tempfile.NamedTemporaryFile("wb", dir=str(tgt.parent), delete=False, prefix=".tmp_sync_") as tf:
                                temp_name = tf.name
                                tf.write(source_bytes)
                                tf.flush()
                                durable_fsync(tf.fileno())
                            try:
                                os.chmod(temp_name, 0o644)
                            except OSError:
                                pass
                            os.replace(temp_name, tgt)
                            temp_name = None
                            # Preserve original source timestamp to prevent oscillation
                            try:
                                os.utime(tgt, (source_stat.st_atime, source_stat.st_mtime))
                            except OSError:
                                pass
                            # Directory fsync to commit new target file
                            if os.name != "nt":
                                dir_flags = os.O_RDONLY
                                if hasattr(os, "O_DIRECTORY"):
                                    dir_flags |= os.O_DIRECTORY
                                try:
                                    dir_fd = os.open(str(tgt.parent), dir_flags)
                                    try:
                                        durable_fsync(dir_fd)
                                    finally:
                                        os.close(dir_fd)
                                except OSError:
                                    pass

                            written_paths.append(str(tgt))
                            logger.info("  ✓ Successfully synchronized defect reports: %s -> %s", source_path, tgt)
                        except Exception as e:
                            logger.warning("Failed to synchronize defect report to %s: %s", tgt, e)
                        finally:
                            if temp_name and os.path.exists(temp_name):
                                try:
                                    os.unlink(temp_name)
                                except OSError:
                                    pass
        finally:
            if written_paths or quarantined_any:
                self.invalidate_cache()

        deduped_written: List[str] = []
        for p_str in written_paths:
            if p_str not in deduped_written:
                deduped_written.append(p_str)

        return deduped_written


__all__ = ["DefectTracker"]
