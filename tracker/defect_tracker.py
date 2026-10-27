"""tracker/defect_tracker.py - OOP Defect Tracking and Query Management Engine.

Provides clean OOP abstractions for:
- Synchronizing daily defect reports across root and web datasets with atomic safety and JSON/schema validation.
- Querying and filtering defect reports by category, vehicle brand/model, severity, and keyword.
- Integrating ScraperPipeline and ContextualDefectFilter for end-to-end defect harvesting and processing.
"""

from __future__ import annotations

from collections import OrderedDict
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

logger = logging.getLogger("defect_tracker")


def _extract_val(obj: Any, key: str, default: Any = None) -> Any:
    """Safely extract field from either a dict, a domain object, or a sequence."""
    if obj is None:
        return default
    if isinstance(obj, dict):
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


def _to_record_dict(obj: Any) -> Dict[str, Any]:
    """Convert a defect record (dict or domain object) safely to a dictionary."""
    if isinstance(obj, dict):
        return dict(obj)
    if hasattr(obj, "to_admin_report_dict") and callable(getattr(obj, "to_admin_report_dict")):
        return obj.to_admin_report_dict()
    if hasattr(obj, "to_dict") and callable(getattr(obj, "to_dict")):
        return obj.to_dict()
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    try:
        return dict(obj)
    except Exception:
        return {k: getattr(obj, k) for k in dir(obj) if not k.startswith("_")}


def _is_project_data_dir(path: Path, cwd: Path) -> bool:
    """Check if the path points to the real project data directory."""
    try:
        resolved = path.resolve()
        for cand in [cwd / "data", cwd.parent / "data"]:
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
        self.reports_file: Optional[Path] = Path(reports_file) if reports_file else None
        cwd = Path.cwd()
        if root_data_dir:
            self.root_data_dir = Path(root_data_dir)
        elif (cwd / "data").exists():
            self.root_data_dir = cwd / "data"
        elif (cwd.parent / "data").exists():
            self.root_data_dir = cwd.parent / "data"
        else:
            self.root_data_dir = cwd / "data"

        if web_data_dir:
            self.web_data_dir = Path(web_data_dir)
        elif (cwd / "src" / "data").exists():
            self.web_data_dir = cwd / "src" / "data"
        elif (cwd / "ev-stealth-web" / "src" / "data").exists():
            self.web_data_dir = cwd / "ev-stealth-web" / "src" / "data"
        else:
            self.web_data_dir = cwd / "ev-stealth-web" / "src" / "data"

        if public_data_dir:
            self.public_data_dir: Optional[Path] = Path(public_data_dir)
        elif web_data_dir and (Path(web_data_dir).parent / "public" / "data").exists():
            self.public_data_dir = Path(web_data_dir).parent / "public" / "data"
        elif web_data_dir and (Path(web_data_dir).parent.parent / "public" / "data").exists():
            self.public_data_dir = Path(web_data_dir).parent.parent / "public" / "data"
        elif root_data_dir is not None and not _is_project_data_dir(self.root_data_dir, cwd):
            self.public_data_dir = None
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
        self._cached_reports_path: Optional[Path] = None
        self._cached_reports: Optional[List[Dict[str, Any]]] = None
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
    def validate_report_file(file_path: Union[str, Path]) -> bool:
        """Validate that target file exists, contains valid JSON, and has a 'reports' list key."""
        p = Path(file_path)
        try:
            if not p.is_file() or p.stat().st_size == 0:
                return False
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return False
            if "reports" not in data or not isinstance(data["reports"], list):
                return False
            if not all(isinstance(r, dict) for r in data["reports"]):
                return False
            return True
        except Exception as exc:
            logger.warning("Defect report validation failed for %s: %s", p, exc)
            return False

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

    def resolve_primary_reports_path(self) -> Optional[Path]:
        """Find the active authoritative defect reports file between root, web, and public."""
        if self.reports_file and self.validate_report_file(self.reports_file):
            return self.reports_file

        candidates = [
            p for p in [self.get_root_reports_path(), self.get_web_reports_path(), self.get_public_reports_path()]
            if p is not None and self.validate_report_file(p)
        ]
        if not candidates:
            return None
        try:
            candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        except Exception:
            pass
        return candidates[0]

    def load_full_report_data(self, file_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """Load complete defect report dataset including statistics and metadata."""
        target = Path(file_path) if file_path else self.resolve_primary_reports_path()
        if not target or not target.exists():
            logger.warning("No defect report file found to load.")
            return {"reports": [], "statistics": {}}

        if not self.validate_report_file(target):
            logger.error("Target defect report file %s failed schema validation.", target)
            return {"reports": [], "statistics": {}}

        try:
            with open(target, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.error("Failed to read defect report %s: %s", target, exc)
            return {"reports": [], "statistics": {}}

    def invalidate_cache(self) -> None:
        """Invalidate in-memory report cache, category index, and query results."""
        with self._cache_lock:
            self._cached_reports_mtime = None
            self._cached_reports_path = None
            self._cached_reports = None
            self._category_index.clear()
            self._query_cache.clear()

    def _build_category_index(self, reports: List[Any]) -> None:
        """Pre-filter and index defect reports into category buckets for O(1) candidate lookup."""
        self._category_index.clear()
        for r in reports:
            raw_cat = _extract_val(r, "defect_category") or _extract_val(r, "category")
            if raw_cat and isinstance(raw_cat, str) and raw_cat.strip():
                cat_norm = raw_cat.upper().strip()
            else:
                cat_norm = "UNKNOWN"
            if cat_norm not in self._category_index:
                self._category_index[cat_norm] = []
            self._category_index[cat_norm].append(r)

    def load_reports(self, file_path: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
        """Load and return list of defect reports from target or primary path with mtime caching."""
        target = Path(file_path) if file_path else self.resolve_primary_reports_path()
        if target and target.exists():
            try:
                current_mtime = target.stat().st_mtime
                with self._cache_lock:
                    if (
                        self._cached_reports is not None
                        and self._cached_reports_path == target
                        and self._cached_reports_mtime == current_mtime
                    ):
                        return [_to_record_dict(r) for r in self._cached_reports]
            except OSError:
                pass

        data = self.load_full_report_data(file_path=target)
        reports = data.get("reports", [])

        with self._cache_lock:
            if target and target.exists():
                try:
                    self._cached_reports_mtime = target.stat().st_mtime
                    self._cached_reports_path = target
                except OSError:
                    self._cached_reports_mtime = None
                    self._cached_reports_path = None
            else:
                self._cached_reports_mtime = None
                self._cached_reports_path = None

            self._cached_reports = reports
            self._build_category_index(reports)
            self._query_cache.clear()
            return [_to_record_dict(r) for r in self._cached_reports]

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
        if limit is not None:
            try:
                norm_limit = int(limit)
                if norm_limit <= 0:
                    return []
            except (ValueError, TypeError):
                norm_limit = None

        norm_min_sev: Optional[float] = None
        if min_severity is not None:
            try:
                f_sev = float(min_severity)
                norm_min_sev = f_sev if not (math.isnan(f_sev) or math.isinf(f_sev)) else None
            except (ValueError, TypeError):
                norm_min_sev = None

        if reports is None:
            loaded_reports = self.load_reports(file_path=file_path)
            candidate_source = loaded_reports
            use_cache = True
        else:
            candidate_source = list(reports)
            use_cache = False

        cat_upper = category.strip().upper() if (category and isinstance(category, str) and category.strip()) else None
        brand_lower = vehicle_brand.strip().lower() if (vehicle_brand and isinstance(vehicle_brand, str) and vehicle_brand.strip()) else None
        model_lower = vehicle_model.strip().lower() if (vehicle_model and isinstance(vehicle_model, str) and vehicle_model.strip()) else None
        kw_lower = keyword.strip().lower() if (keyword and isinstance(keyword, str) and keyword.strip()) else None

        if use_cache:
            with self._cache_lock:
                cache_key = (
                    str(self._cached_reports_path),
                    self._cached_reports_mtime,
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
                if cat_upper is not None:
                    candidate_pool = list(self._category_index.get(cat_upper, []))
                else:
                    candidate_pool = list(candidate_source)
        else:
            candidate_pool = list(candidate_source)

        filtered: List[Dict[str, Any]] = []

        for r in candidate_pool:
            # Category filter (re-verify for defensive assurance, normalizing missing/None to UNKNOWN)
            if cat_upper:
                raw_cat = _extract_val(r, "defect_category") or _extract_val(r, "category")
                item_cat = (raw_cat.upper().strip() if (raw_cat and isinstance(raw_cat, str) and raw_cat.strip()) else "UNKNOWN")
                if item_cat != cat_upper:
                    continue

            # Brand filter
            brand_val = _extract_val(r, "vehicle_brand") or _extract_val(r, "brand") or ""
            if brand_lower and brand_lower not in str(brand_val).lower():
                continue

            # Model filter
            model_val = _extract_val(r, "vehicle_model") or _extract_val(r, "model") or ""
            if model_lower and model_lower not in str(model_val).lower():
                continue

            # Severity filter
            if norm_min_sev is not None:
                sev = _extract_val(r, "severity_index")
                effective_sev: Optional[float] = None
                if sev is not None:
                    try:
                        effective_sev = float(sev)
                        if math.isnan(effective_sev) or math.isinf(effective_sev):
                            effective_sev = None
                    except (ValueError, TypeError):
                        effective_sev = None

                if effective_sev is None:
                    raw_tier = str(_extract_val(r, "severity") or _extract_val(r, "severity_tier") or "").strip().upper()
                    tier_map = {
                        "CRITICAL": 9.0,
                        "HIGH": 7.0,
                        "WARNING": 7.0,
                        "MEDIUM": 5.0,
                        "CAUTION": 4.0,
                        "LOW": 3.0,
                        "INFO": 1.0,
                    }
                    effective_sev = tier_map.get(raw_tier, 0.0)

                if effective_sev < norm_min_sev:
                    continue

            # Keyword search across title, defect_topic, summary, verbatim_quote, and raw_quote
            if kw_lower:
                combined_text = " ".join([
                    str(_extract_val(r, "title", "")),
                    str(_extract_val(r, "defect_topic", "")),
                    str(_extract_val(r, "summary", "")),
                    str(_extract_val(r, "verbatim_quote", "")),
                    str(_extract_val(r, "raw_quote", "")),
                ]).lower()
                if kw_lower not in combined_text:
                    continue

            filtered.append(r)
            if norm_limit is not None and len(filtered) >= norm_limit:
                break

        # Thread-safe true LRU cache with promotion and bounded eviction
        if use_cache:
            with self._cache_lock:
                self._query_cache[cache_key] = [_to_record_dict(r) for r in filtered]
                self._query_cache.move_to_end(cache_key)
                while len(self._query_cache) > 1024:
                    self._query_cache.popitem(last=False)

        return [_to_record_dict(r) for r in filtered]

    def get_statistics(self, file_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """Return high-level statistics and category breakdown for defect reports."""
        def _get_val(obj: Any, key: str, default: Any = None) -> Any:
            if obj is None:
                return default
            if isinstance(obj, dict):
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

        full_data = self.load_full_report_data(file_path=file_path)
        stats = _get_val(full_data, "statistics")
        if stats and isinstance(stats, dict):
            stat_copy = dict(stats)
            raw_avg = stat_copy.get("avg_negativity_score")
            if raw_avg is not None:
                try:
                    f_avg = float(raw_avg)
                    if math.isnan(f_avg) or math.isinf(f_avg):
                        stat_copy["avg_negativity_score"] = 0.0
                    else:
                        stat_copy["avg_negativity_score"] = round(f_avg, 2)
                except (ValueError, TypeError, OverflowError):
                    stat_copy["avg_negativity_score"] = 0.0

            # Ensure category_distribution is always populated
            if "category_distribution" not in stat_copy or not isinstance(stat_copy["category_distribution"], dict):
                cat_dist: Dict[str, int] = {}
                fd_dist = _get_val(full_data, "category_distribution")
                if fd_dist and isinstance(fd_dist, dict):
                    for k, v in fd_dist.items():
                        try:
                            cat_dist[str(k)] = int(v)
                        except (ValueError, TypeError):
                            pass
                elif _get_val(full_data, "top_defect_categories"):
                    top_cats = _get_val(full_data, "top_defect_categories")
                    if isinstance(top_cats, list):
                        for item in top_cats:
                            if isinstance(item, dict) and "category" in item and "count" in item:
                                try:
                                    cat_dist[str(item["category"])] = int(item["count"])
                                except (ValueError, TypeError):
                                    pass
                    elif isinstance(top_cats, dict):
                        for k, v in top_cats.items():
                            try:
                                cat_dist[str(k)] = int(v)
                            except (ValueError, TypeError):
                                pass

                if not cat_dist:
                    reports = _get_val(full_data, "reports", [])
                    if isinstance(reports, list):
                        for r in reports:
                            raw_cat = _get_val(r, "defect_category", None) or _get_val(r, "category", None)
                            cat = str(raw_cat).strip() if (raw_cat and str(raw_cat).strip()) else "UNKNOWN"
                            cat_dist[cat] = cat_dist.get(cat, 0) + 1

                stat_copy["category_distribution"] = cat_dist

            return stat_copy

        # Compute on-the-fly from reports list
        reports = _get_val(full_data, "reports", [])
        total = len(reports)
        critical_count = 0
        negativities: List[float] = []
        category_counts: Dict[str, int] = {}

        for r in reports:
            raw_cat = _get_val(r, "defect_category", None)
            if raw_cat is None:
                raw_cat = _get_val(r, "category", None)
            cat = str(raw_cat).strip() if (raw_cat and str(raw_cat).strip()) else "UNKNOWN"
            category_counts[cat] = category_counts.get(cat, 0) + 1

            dsi = _get_val(r, "severity_index")
            effective_dsi: Optional[float] = None
            if dsi is not None:
                try:
                    f_dsi = float(dsi)
                    if not (math.isnan(f_dsi) or math.isinf(f_dsi)):
                        effective_dsi = f_dsi
                except (ValueError, TypeError, OverflowError):
                    effective_dsi = None

            sev_raw = _get_val(r, "severity_tier") or _get_val(r, "severity") or ""
            sev_str = str(sev_raw).strip().upper()
            is_critical = (
                sev_str == "CRITICAL"
                or (effective_dsi is not None and effective_dsi >= 7.0)
            )
            if is_critical:
                critical_count += 1

            neg = _get_val(r, "negativity_score")
            if neg is not None:
                try:
                    f_neg = float(neg)
                    if not (math.isnan(f_neg) or math.isinf(f_neg)):
                        negativities.append(f_neg)
                except (ValueError, TypeError, OverflowError):
                    pass

        avg_neg = (sum(negativities) / len(negativities)) if negativities else 0.0
        if math.isnan(avg_neg) or math.isinf(avg_neg):
            avg_neg = 0.0

        return {
            "total_filtered_defects": total,
            "critical_defect_count": critical_count,
            "avg_negativity_score": round(avg_neg, 2),
            "category_distribution": category_counts,
        }

    def filter_raw_posts(self, raw_posts: List[Any]) -> List[Any]:
        """Process raw posts through ContextualDefectFilter and return authentic defect complaints."""
        if not self.filter_engine:
            raise RuntimeError("ContextualDefectFilter is not available in environment.")

        filtered_defects: List[Any] = []
        for post_item in raw_posts:
            try:
                if RawPost is not None:
                    if isinstance(post_item, RawPost):
                        post_obj = post_item
                    elif isinstance(post_item, dict):
                        post_obj = RawPost.from_dict(post_item)
                    else:
                        post_obj = RawPost(
                            platform=str(getattr(post_item, "platform", "unknown")),
                            post_id=str(getattr(post_item, "post_id", getattr(post_item, "id", ""))),
                            url=str(getattr(post_item, "url", "")),
                            title=str(getattr(post_item, "title", "")),
                            content=str(getattr(post_item, "content", "")),
                            comments=list(getattr(post_item, "comments", [])),
                            created_at=str(getattr(post_item, "created_at", "")),
                            author=str(getattr(post_item, "author", "")),
                        )
                    record = self.filter_engine.process_post(post_obj)
                else:
                    record = self.filter_engine.process_post(post_item)

                is_auth = getattr(record, "is_authentic_defect", False)
                if is_auth:
                    filtered_defects.append(record)
            except Exception as exc:
                p_id = getattr(post_item, "post_id", getattr(post_item, "id", None)) if not isinstance(post_item, dict) else (post_item.get("post_id") or post_item.get("id"))
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
    ) -> List[str]:
        """Synchronize defect reports between root data/, web src/data/, and public/data/ with atomic safety and validation.

        Validates source file JSON syntax and 'reports' key schema before any file replacement.
        Guarantees that corrupt files are NEVER propagated.
        """
        logger.info("DefectTracker: Synchronizing defect reports (daily_reports.json)...")
        if dry_run:
            logger.info("[DRY-RUN] DefectTracker sync skipped file persistence.")
            return []

        # Resolve paths
        root_path = self.get_root_reports_path()
        web_path = (Path(web_dir) / "daily_reports.json") if web_dir else self.get_web_reports_path()

        public_path: Optional[Path] = None
        if web_dir and (Path(web_dir).parent / "public" / "data").exists():
            public_path = Path(web_dir).parent / "public" / "data" / "daily_reports.json"
        elif web_dir and (Path(web_dir).parent.parent / "public" / "data").exists():
            public_path = Path(web_dir).parent.parent / "public" / "data" / "daily_reports.json"
        else:
            public_path = self.get_public_reports_path()

        written_paths: List[str] = []

        if run_crawler and self.pipeline:
            try:
                res = self.pipeline.run(
                    sources="all",
                    limit=10,
                    sync_web=True,
                    web_dir=web_dir,
                    dry_run=dry_run,
                )
                written_paths.extend(res.get("written_paths", []))
            except Exception as exc:
                logger.warning(
                    "Crawler execution in sync_defect_reports encountered: %s. Falling back to mirror synchronization.",
                    exc,
                )

        known_paths: List[Path] = [p for p in [root_path, web_path, public_path] if p is not None]
        candidate_paths: List[Path] = [p for p in known_paths if p.exists()]
        try:
            candidate_paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        except Exception:
            pass

        source_path: Optional[Path] = None
        for cand in candidate_paths:
            if self.validate_report_file(cand):
                source_path = cand
                break

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

        if source_path and target_paths and self.validate_report_file(source_path):
            try:
                source_stat = source_path.stat()
                h_src = hashlib.sha256()
                with open(source_path, "rb") as sf:
                    while chunk := sf.read(65536):
                        h_src.update(chunk)
                source_hash = h_src.hexdigest()
            except Exception as e:
                logger.error("Failed to inspect source defect report %s: %s", source_path, e)
                return []

            for tgt in target_paths:
                if tgt.exists():
                    try:
                        h_tgt = hashlib.sha256()
                        with open(tgt, "rb") as tf_in:
                            while chunk := tf_in.read(65536):
                                h_tgt.update(chunk)
                        if h_tgt.hexdigest() == source_hash:
                            try:
                                tgt_stat = tgt.stat()
                                if tgt_stat.st_mtime != source_stat.st_mtime:
                                    os.utime(tgt, (source_stat.st_atime, source_stat.st_mtime))
                            except OSError:
                                pass
                            logger.debug("Skipping redundant defect report sync for %s (SHA-256 match)", tgt)
                            continue
                    except Exception as e:
                        logger.warning("Error verifying SHA-256 on target %s: %s", tgt, e)

                temp_name = None
                try:
                    tgt.parent.mkdir(parents=True, exist_ok=True)
                    with tempfile.NamedTemporaryFile("wb", dir=str(tgt.parent), delete=False, prefix=".tmp_sync_") as tf:
                        temp_name = tf.name
                        with open(source_path, "rb") as sf:
                            shutil.copyfileobj(sf, tf)
                        tf.flush()
                        os.fsync(tf.fileno())
                    try:
                        os.chmod(temp_name, 0o644)
                    except OSError:
                        pass
                    os.replace(temp_name, tgt)
                    # Preserve original source timestamp to prevent oscillation
                    try:
                        os.utime(tgt, (source_stat.st_atime, source_stat.st_mtime))
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

        if written_paths:
            self.invalidate_cache()

        deduped_written: List[str] = []
        for p_str in written_paths:
            if p_str not in deduped_written:
                deduped_written.append(p_str)

        return deduped_written


__all__ = ["DefectTracker"]
