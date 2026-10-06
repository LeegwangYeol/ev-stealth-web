"""tracker/defect_tracker.py - OOP Defect Tracking and Query Management Engine.

Provides clean OOP abstractions for:
- Synchronizing daily defect reports across root and web datasets with atomic safety and JSON/schema validation.
- Querying and filtering defect reports by category, vehicle brand/model, severity, and keyword.
- Integrating ScraperPipeline and ContextualDefectFilter for end-to-end defect harvesting and processing.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("defect_tracker")

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
        pipeline: Optional[Any] = None,
        filter_engine: Optional[Any] = None,
    ) -> None:
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

        self._pipeline = pipeline
        self._filter_engine = filter_engine

    @property
    def pipeline(self) -> Any:
        """Lazily initialize ScraperPipeline if not explicitly provided."""
        if self._pipeline is None and ScraperPipeline is not None:
            self._pipeline = ScraperPipeline()
        return self._pipeline

    @property
    def filter_engine(self) -> Any:
        """Lazily initialize ContextualDefectFilter if not explicitly provided."""
        if self._filter_engine is None and ContextualDefectFilter is not None:
            self._filter_engine = ContextualDefectFilter()
        return self._filter_engine

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

    def resolve_primary_reports_path(self) -> Optional[Path]:
        """Find the active authoritative defect reports file between root and web."""
        root_path = self.get_root_reports_path()
        web_path = self.get_web_reports_path()

        root_valid = self.validate_report_file(root_path)
        web_valid = self.validate_report_file(web_path)

        if root_valid and web_valid:
            try:
                if root_path.stat().st_mtime >= web_path.stat().st_mtime:
                    return root_path
                return web_path
            except Exception:
                return root_path
        elif root_valid:
            return root_path
        elif web_valid:
            return web_path
        return None

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

    def load_reports(self, file_path: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
        """Load and return list of defect reports from target or primary path."""
        data = self.load_full_report_data(file_path=file_path)
        return data.get("reports", [])

    def query_defects(
        self,
        category: Optional[str] = None,
        vehicle_brand: Optional[str] = None,
        vehicle_model: Optional[str] = None,
        min_severity: Optional[float] = None,
        keyword: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Query and filter defect reports by multiple criteria."""
        reports = self.load_reports()
        filtered: List[Dict[str, Any]] = []

        cat_upper = category.upper().strip() if category else None
        brand_lower = vehicle_brand.lower().strip() if vehicle_brand else None
        model_lower = vehicle_model.lower().strip() if vehicle_model else None
        kw_lower = keyword.lower().strip() if keyword else None

        for r in reports:
            # Category filter
            if cat_upper and r.get("defect_category", "").upper() != cat_upper:
                continue

            # Brand filter
            if brand_lower and brand_lower not in (r.get("vehicle_brand") or "").lower():
                continue

            # Model filter
            if model_lower and model_lower not in (r.get("vehicle_model") or "").lower():
                continue

            # Severity filter
            if min_severity is not None:
                sev = r.get("severity_index", 0.0)
                try:
                    if float(sev) < min_severity:
                        continue
                except (ValueError, TypeError):
                    continue

            # Keyword search across title, defect_topic, and verbatim_quote
            if kw_lower:
                combined_text = " ".join([
                    str(r.get("title", "")),
                    str(r.get("defect_topic", "")),
                    str(r.get("verbatim_quote", "")),
                    str(r.get("raw_quote", "")),
                ]).lower()
                if kw_lower not in combined_text:
                    continue

            filtered.append(r)
            if limit is not None and len(filtered) >= limit:
                break

        return filtered

    def get_statistics(self, file_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """Return high-level statistics and category breakdown for defect reports."""
        full_data = self.load_full_report_data(file_path=file_path)
        stats = full_data.get("statistics")
        if stats and isinstance(stats, dict):
            return dict(stats)

        # Compute on-the-fly from reports list
        reports = full_data.get("reports", [])
        total = len(reports)
        critical_count = 0
        negativities: List[float] = []
        category_counts: Dict[str, int] = {}

        for r in reports:
            cat = r.get("defect_category", "UNKNOWN")
            category_counts[cat] = category_counts.get(cat, 0) + 1

            dsi = r.get("severity_index", 0.0)
            try:
                if float(dsi) >= 7.0:
                    critical_count += 1
            except (ValueError, TypeError):
                pass

            neg = r.get("negativity_score")
            if neg is not None:
                try:
                    negativities.append(float(neg))
                except (ValueError, TypeError):
                    pass

        avg_neg = (sum(negativities) / len(negativities)) if negativities else 0.0

        return {
            "total_filtered_defects": total,
            "critical_defect_count": critical_count,
            "avg_negativity_score": round(avg_neg, 2),
            "category_distribution": category_counts,
        }

    def filter_raw_posts(self, raw_posts: List[Dict[str, Any]]) -> List[Any]:
        """Process raw posts through ContextualDefectFilter and return authentic defect complaints."""
        if not self.filter_engine:
            raise RuntimeError("ContextualDefectFilter is not available in environment.")

        filtered_defects: List[Any] = []
        for post_dict in raw_posts:
            try:
                if RawPost is not None:
                    post_obj = RawPost.from_dict(post_dict)
                    record = self.filter_engine.process_post(post_obj)
                else:
                    record = self.filter_engine.process_post(post_dict)

                is_auth = getattr(record, "is_authentic_defect", False)
                if is_auth:
                    filtered_defects.append(record)
            except Exception as exc:
                logger.warning("Error filtering post %s: %s", post_dict.get("id"), exc)

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
        """Synchronize defect reports between root data/ and web src/data/ with atomic safety and validation.

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
                return written_paths
            except Exception as exc:
                logger.warning(
                    "Crawler execution in sync_defect_reports encountered: %s. Falling back to mirror synchronization.",
                    exc,
                )

        root_exists = root_path.exists()
        web_exists = web_path.exists()

        source_path: Optional[Path] = None
        target_paths: List[Path] = []

        if root_exists and web_exists:
            try:
                root_stat = root_path.stat()
                web_stat = web_path.stat()
                if root_stat.st_mtime >= web_stat.st_mtime:
                    primary, secondary = root_path, web_path
                else:
                    primary, secondary = web_path, root_path
            except Exception:
                primary, secondary = root_path, web_path

            # Strict validation: Only accept source if valid JSON and contains 'reports' key
            if self.validate_report_file(primary):
                source_path = primary
                target_paths = [secondary]
            elif self.validate_report_file(secondary):
                logger.warning(
                    "Primary candidate %s failed schema validation. Falling back to valid secondary %s.",
                    primary,
                    secondary,
                )
                source_path = secondary
                target_paths = [primary]
            else:
                logger.error(
                    "Both candidate defect report sources (%s, %s) are corrupted or invalid. Aborting sync.",
                    primary,
                    secondary,
                )
                return []
        elif root_exists and not web_exists:
            if self.validate_report_file(root_path):
                source_path = root_path
                target_paths = [web_path]
            else:
                logger.error("Root defect reports file %s is corrupt or invalid. Aborting sync.", root_path)
                return []
        elif web_exists and not root_exists:
            if self.validate_report_file(web_path):
                source_path = web_path
                target_paths = [root_path]
            else:
                logger.error("Web defect reports file %s is corrupt or invalid. Aborting sync.", web_path)
                return []

        if source_path and target_paths and self.validate_report_file(source_path):
            for tgt in target_paths:
                temp_name = None
                try:
                    tgt.parent.mkdir(parents=True, exist_ok=True)
                    with tempfile.NamedTemporaryFile("wb", dir=str(tgt.parent), delete=False, prefix=".tmp_sync_") as tf:
                        temp_name = tf.name
                        with open(source_path, "rb") as sf:
                            shutil.copyfileobj(sf, tf)
                        tf.flush()
                        os.fsync(tf.fileno())
                    os.replace(temp_name, tgt)
                    written_paths.append(str(tgt))
                    logger.info("  ✓ Successfully synchronized defect reports: %s -> %s", source_path, tgt)
                except Exception as e:
                    logger.warning("Failed to synchronize defect report to %s: %s", tgt, e)
                finally:
                    if temp_name and os.path.exists(temp_name):
                        os.unlink(temp_name)

        return written_paths


__all__ = ["DefectTracker"]
