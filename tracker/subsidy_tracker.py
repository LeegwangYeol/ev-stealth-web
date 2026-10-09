"""Core EV Subsidy Depletion Tracker Engine.

Orchestrates data harvesting, metric recalculations, 5-tier alert classifications,
nationwide aggregations, fallback resilience, and atomic persistence.
"""

from __future__ import annotations

from datetime import datetime, timezone
import http.client
import json
import logging
import math
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import urllib.error
import urllib.request

from tracker.atomic_writer import atomic_write_json, atomic_write_json_multiple
from tracker.report_generator import ReportGenerator
from tracker.subsidy_baseline import (
    COMMERCIAL_NATIONAL_CAP_KRW,
    DEFAULT_ALERT_THRESHOLDS,
    PASSENGER_NATIONAL_CAP_KRW,
    build_baseline_regions,
    build_initial_baseline,
    build_popular_models,
)
from tracker.subsidy_models import (
    AlertSeverity,
    CategoryMetrics,
    MunicipalityMetrics,
    NationwideSummary,
    PopularModelEntry,
    RegionRecord,
    SubsidyMetadata,
    SubsidyPayload,
)

logger = logging.getLogger("subsidy_tracker")

# Maximum bounded response read size (10MB) to prevent memory exhaustion
MAX_RESPONSE_BYTES: int = 10 * 1024 * 1024

try:
    from utils.http_client import robust_decode
except ImportError:
    try:
        from scrapers.common_utils import robust_decode
    except ImportError:
        def robust_decode(raw_bytes: bytes, declared_encoding: Optional[str] = None) -> str:
            """Decode raw bytes with graceful fallback across Korean and universal charsets."""
            if not raw_bytes:
                return ""
            encodings_to_try = [declared_encoding, "utf-8", "cp949", "euc-kr", "latin-1"]
            for enc in encodings_to_try:
                if not enc or not isinstance(enc, str):
                    continue
                try:
                    return raw_bytes.decode(enc)
                except (UnicodeDecodeError, LookupError):
                    continue
            return raw_bytes.decode("utf-8", errors="replace")

# Exported baseline aliases and getters matching interface specifications
get_baseline_regions = build_baseline_regions
get_baseline_models = build_popular_models
get_baseline_dataset = build_initial_baseline


def get_baseline_thresholds() -> Dict[str, Any]:
    """Return default 5-tier alert threshold configuration dictionary."""
    return DEFAULT_ALERT_THRESHOLDS


def calculate_depletion_rate(applied: Union[int, float], announced: Union[int, float]) -> float:
    """Calculate EV subsidy depletion rate as percentage with zero-division guard and negative clamping."""
    try:
        if announced is None or applied is None:
            return 0.0
        announced_val = float(announced)
        applied_val = float(applied)
        if math.isnan(announced_val) or math.isnan(applied_val) or math.isinf(announced_val) or math.isinf(applied_val):
            return 0.0
        if announced_val <= 0 or applied_val <= 0:
            return 0.0
        rate = round((applied_val / announced_val) * 100.0, 1)
        return max(0.0, rate)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def calculate_remaining_units(applied: Union[int, float], announced: Union[int, float]) -> int:
    """Calculate remaining quota units clamped at zero for over-subscription or negative values."""
    try:
        if announced is None or applied is None:
            return 0
        announced_f = float(announced)
        applied_f = float(applied)
        if math.isnan(announced_f) or math.isnan(applied_f) or math.isinf(announced_f) or math.isinf(applied_f):
            return 0
        safe_announced = max(0, int(announced_f))
        safe_applied = max(0, int(applied_f))
        return max(0, safe_announced - safe_applied)
    except (TypeError, ValueError, OverflowError):
        return 0


def classify_alert_tier(depletion_rate: float) -> str:
    """Classify depletion rate into standard 5-tier alert severity level."""
    return AlertSeverity.from_rate(depletion_rate).value


def calculate_price_cap_ratio(msrp: int) -> float:
    """Statutory 2026 Korean EV subsidy ratio tiers: 1.0 (<=55M), 0.5 (55M-85M), 0.0 (>85M)."""
    if msrp <= 55_000_000:
        return 1.0
    elif msrp <= 85_000_000:
        return 0.5
    return 0.0


def calculate_net_subsidy(
    model_national: int,
    max_national: int,
    max_local: int,
    msrp: int,
) -> Dict[str, int]:
    """Calculate national subsidy, local subsidy, total subsidy, and net consumer purchase price."""
    ratio = calculate_price_cap_ratio(msrp)
    effective_national = int(round(model_national * ratio))
    if max_national > 0:
        local_ratio = min(1.0, max(0.0, model_national / max_national))
    else:
        local_ratio = 0.0
    effective_local = int(round(max_local * local_ratio * ratio))
    total_subsidy = effective_national + effective_local
    net_price = max(0, msrp - total_subsidy)
    return {
        "national_subsidy_krw": effective_national,
        "local_subsidy_krw": effective_local,
        "total_subsidy_krw": total_subsidy,
        "net_price_krw": net_price,
    }


def _metric_val(metric: Any, key: str, default: Any = 0) -> Any:
    """Safely extract metric attribute or dict key, supporting dict and dataclass instances."""
    if metric is None:
        return default
    if isinstance(metric, dict):
        return metric.get(key, default)
    return getattr(metric, key, default)


class SubsidyTracker:
    """Automated tracker for nationwide South Korea EV subsidy allocations and depletion."""

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        timeout_seconds: float = 5.0,
        cache_fallback_path: Optional[Union[str, Path]] = None,
        validate_cache: bool = False,
        quarantine_corrupted: bool = False,
        report_generator: Optional[ReportGenerator] = None,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.timeout_seconds = timeout_seconds
        self.cache_fallback_path = Path(cache_fallback_path) if cache_fallback_path else None
        self.validate_cache = validate_cache
        self.quarantine_corrupted = quarantine_corrupted
        self.report_generator = report_generator or ReportGenerator()

    def evaluate_status(self, depletion_rate: float) -> AlertSeverity:
        """Evaluate 5-tier alert severity from depletion percentage."""
        return AlertSeverity.from_rate(depletion_rate)

    def calculate_category_metrics(
        self,
        announced: int,
        applied: int,
        delivered: int,
        max_local_subsidy: int,
        national_cap: int = PASSENGER_NATIONAL_CAP_KRW,
        avg_per_unit_budget: int = 10_000_000,
    ) -> CategoryMetrics:
        """Safely compute metrics for a single category with boundary clamping."""
        depletion_rate = calculate_depletion_rate(applied, announced)
        delivery_rate = calculate_depletion_rate(delivered, announced)
        remaining_units = calculate_remaining_units(applied, announced)
        status = self.evaluate_status(depletion_rate).value

        safe_announced = max(0, announced) if announced is not None else 0
        safe_applied = max(0, applied) if applied is not None else 0
        total_budget = safe_announced * avg_per_unit_budget
        disbursed_budget = safe_applied * avg_per_unit_budget
        remaining_budget = max(0, total_budget - disbursed_budget)

        return CategoryMetrics(
            announced_units=announced,
            applied_units=applied,
            delivered_units=delivered,
            remaining_units=remaining_units,
            depletion_rate=depletion_rate,
            delivery_rate=delivery_rate,
            status=status,
            max_local_subsidy_krw=max_local_subsidy,
            max_total_subsidy_krw=max_local_subsidy + national_cap,
            total_budget_krw=total_budget,
            remaining_budget_krw=remaining_budget,
        )

    def update_region_metrics(self, region: RegionRecord) -> RegionRecord:
        """Recalculate overall status and depletion rates for a region."""
        total_announced = 0
        total_applied = 0

        for cat_name, cat in region.categories.items():
            total_announced += cat.announced_units
            total_applied += cat.applied_units
            cat.remaining_units = calculate_remaining_units(cat.applied_units, cat.announced_units)
            cat.depletion_rate = calculate_depletion_rate(cat.applied_units, cat.announced_units)
            cat.delivery_rate = calculate_depletion_rate(cat.delivered_units, cat.announced_units)
            cat.status = self.evaluate_status(cat.depletion_rate).value
            if cat.total_budget_krw > 0 and cat.announced_units > 0:
                unit_budget = cat.total_budget_krw / cat.announced_units
                cat.remaining_budget_krw = int(max(0, cat.total_budget_krw - (cat.applied_units * unit_budget)))

        # Recalculate municipalities if present
        if region.municipalities:
            for muni in region.municipalities:
                muni.remaining_units = calculate_remaining_units(muni.applied_units, muni.announced_units)
                muni.depletion_rate = calculate_depletion_rate(muni.applied_units, muni.announced_units)
                muni.status = self.evaluate_status(muni.depletion_rate).value

        # Overall depletion rate is weighted by volume across all categories
        overall_rate = calculate_depletion_rate(total_applied, total_announced)
        region.overall_depletion_rate = overall_rate
        region.overall_status = self.evaluate_status(overall_rate).value
        return region

    def compute_nationwide_summary(self, regions: List[RegionRecord]) -> NationwideSummary:
        """Aggregate totals across all tracked regions."""
        total_announced = 0
        total_applied = 0
        total_delivered = 0
        total_budget_krw = 0
        disbursed_budget_krw = 0

        cat_counts: Dict[str, Dict[str, int]] = {
            "passenger": {"announced": 0, "applied": 0, "delivered": 0},
            "commercial": {"announced": 0, "applied": 0, "delivered": 0},
            "bus": {"announced": 0, "applied": 0, "delivered": 0},
        }

        alert_counts: Dict[str, int] = {
            "healthy": 0,
            "caution": 0,
            "warning": 0,
            "critical": 0,
            "depleted": 0,
        }

        for r in regions:
            # Region overall status
            st_key = r.overall_status.lower()
            if st_key in alert_counts:
                alert_counts[st_key] += 1

            for c_name, c_data in r.categories.items():
                if c_name not in cat_counts:
                    cat_counts[c_name] = {"announced": 0, "applied": 0, "delivered": 0}

                cat_counts[c_name]["announced"] += c_data.announced_units
                cat_counts[c_name]["applied"] += c_data.applied_units
                cat_counts[c_name]["delivered"] += c_data.delivered_units

                total_announced += c_data.announced_units
                total_applied += c_data.applied_units
                total_delivered += c_data.delivered_units
                total_budget_krw += c_data.total_budget_krw
                disbursed_budget_krw += (c_data.total_budget_krw - c_data.remaining_budget_krw)

        total_remaining = calculate_remaining_units(total_applied, total_announced)
        nationwide_rate = calculate_depletion_rate(total_applied, total_announced)

        cat_totals = {}
        for c_name, counts in cat_counts.items():
            c_ann = counts["announced"]
            c_app = counts["applied"]
            c_del = counts["delivered"]
            c_rate = calculate_depletion_rate(c_app, c_ann)
            c_del_rate = calculate_depletion_rate(c_del, c_ann)
            cat_totals[c_name] = {
                "announced_units": c_ann,
                "applied_units": c_app,
                "delivered_units": c_del,
                "remaining_units": calculate_remaining_units(c_app, c_ann),
                "depletion_rate": c_rate,
                "delivery_rate": c_del_rate,
                "status": self.evaluate_status(c_rate).value,
            }

        return NationwideSummary(
            total_announced_units=total_announced,
            total_applied_units=total_applied,
            total_delivered_units=total_delivered,
            total_remaining_units=total_remaining,
            nationwide_depletion_rate=nationwide_rate,
            total_budget_billion_krw=round(total_budget_krw / 1_000_000_000, 1),
            disbursed_budget_billion_krw=max(0.0, round(disbursed_budget_krw / 1_000_000_000, 1)),
            category_totals=cat_totals,
            alert_region_counts=alert_counts,
        )

    def fetch_live_updates(
        self,
        max_retries: int = 3,
        backoff_base: float = 0.05,
    ) -> Optional[Dict[str, Any]]:
        """Attempt to fetch live data from remote endpoint with 3-attempt exponential backoff retry."""
        if not self.endpoint_url:
            logger.debug("No endpoint URL configured. Using validated baseline engine.")
            return None

        logger.info("Attempting live poll from %s (timeout=%.1fs)...", self.endpoint_url, self.timeout_seconds)
        closed_exc_ids: Set[int] = set()
        for attempt in range(1, max_retries + 1):
            try:
                req = urllib.request.Request(
                    self.endpoint_url,
                    headers={
                        "User-Agent": "MyECar-SubsidyTracker/1.0 (Automated Scheduled Task)",
                        "Accept-Encoding": "identity",
                    },
                )
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    if resp.status == 200:
                        raw_bytes = resp.read(MAX_RESPONSE_BYTES)
                        declared_encoding = None
                        if hasattr(resp, "headers") and hasattr(resp.headers, "get_content_charset"):
                            try:
                                charset = resp.headers.get_content_charset()
                                if isinstance(charset, str):
                                    declared_encoding = charset
                            except Exception:
                                pass
                        raw_data = robust_decode(raw_bytes, declared_encoding=declared_encoding)
                        if raw_data.startswith("\ufeff"):
                            raw_data = raw_data.lstrip("\ufeff")
                        return json.loads(raw_data)
                    logger.warning(
                        "Remote server returned non-200 status: %d (attempt %d/%d)",
                        resp.status,
                        attempt,
                        max_retries,
                    )
                    if attempt < max_retries:
                        backoff = backoff_base * (2 ** (attempt - 1))
                        time.sleep(backoff)
                        continue
                    return None
            except (
                urllib.error.URLError,
                urllib.error.HTTPError,
                TimeoutError,
                json.JSONDecodeError,
                UnicodeDecodeError,
                http.client.HTTPException,
                OSError,
                Exception,
            ) as exc:
                if hasattr(exc, "close") and id(exc) not in closed_exc_ids:
                    closed_exc_ids.add(id(exc))
                    try:
                        exc.close()
                    except Exception:
                        pass
                logger.warning("Live fetch attempt %d/%d failed: %s.", attempt, max_retries, exc)
                if attempt < max_retries:
                    backoff = backoff_base * (2 ** (attempt - 1))
                    time.sleep(backoff)
                    continue
                logger.warning("Live fetch failed: %s. Initiating graceful fallback.", exc)
                return None
        return None

    def quarantine_corrupted_cache(self, cache_path: Union[str, Path]) -> Optional[Path]:
        """Quarantine a corrupted cache file by renaming it with a timestamp suffix."""
        p = Path(cache_path)
        if not p.exists():
            return None
        try:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
            quarantine_path = p.with_name(f"{p.stem}.corrupt_{ts}{p.suffix}")
            p.rename(quarantine_path)
            logger.warning("Quarantined corrupted cache file: %s -> %s", p, quarantine_path)
            return quarantine_path
        except OSError as exc:
            logger.warning("Failed to quarantine corrupted cache file %s: %s", p, exc)
            return None

    def discard_corrupted_cache(self, cache_path: Union[str, Path]) -> bool:
        """Discard a corrupted cache file by removing it from disk."""
        p = Path(cache_path)
        if not p.exists():
            return False
        try:
            p.unlink()
            logger.warning("Discarded corrupted cache file: %s", p)
            return True
        except OSError as exc:
            logger.warning("Failed to discard corrupted cache file %s: %s", p, exc)
            return False

    def load_cached_payload(
        self,
        cache_path: Optional[Union[str, Path]] = None,
        validate: bool = False,
        quarantine: Optional[bool] = None,
    ) -> Optional[SubsidyPayload]:
        """Load and validate cached SubsidyPayload snapshot with corrupted file resilience.

        Hardened against:
        - Malformed/truncated JSON or invalid UTF-8 bytes.
        - Non-dictionary or missing root keys.
        - Invalid schema structures (non-list regions, missing categories).
        - Degenerate cache states.

        If corruption is detected:
        - Logs warning.
        - Quarantines or discards corrupted cache gracefully if quarantine is requested.
        - Gracefully discards invalid payload in memory and returns None (triggering fresh baseline computation).
        """
        target_path = Path(cache_path) if cache_path else self.cache_fallback_path
        if not target_path or not target_path.exists():
            return None

        should_quarantine = self.quarantine_corrupted if quarantine is None else quarantine

        try:
            logger.info("Loading cached snapshot from %s", target_path)
            with open(target_path, "r", encoding="utf-8") as f:
                cached_dict = json.load(f)

            if not isinstance(cached_dict, dict):
                raise ValueError(
                    f"Cache content must be a JSON object (dict), got {type(cached_dict).__name__}"
                )

            payload = SubsidyPayload.from_dict(cached_dict)

            if validate:
                if not payload.regions or len(payload.regions) < 17:
                    raise ValueError(
                        f"Invalid cache schema: expected >= 17 regions, found {len(payload.regions) if payload.regions else 0}"
                    )
                for idx, r in enumerate(payload.regions):
                    if not hasattr(r, "categories") or not isinstance(r.categories, dict):
                        raise ValueError(
                            f"Corrupted region record at index {idx}: missing categories dictionary"
                        )

            return payload
        except Exception as e:
            logger.warning(
                "Failed to load cache %s: %s. Gracefully discarding corrupted cache snapshot.",
                target_path,
                e,
            )
            if should_quarantine:
                self.quarantine_corrupted_cache(target_path)
            return None

    def execute_tracking_cycle(
        self,
        mock_network_failure: bool = False,
        validate_cache: Optional[bool] = None,
        quarantine_corrupted: Optional[bool] = None,
    ) -> Tuple[SubsidyPayload, bool]:
        """Run complete tracking cycle. Returns (payload, is_fallback_used)."""
        logger.info("Starting EV Subsidy tracking cycle...")

        should_validate = self.validate_cache if validate_cache is None else validate_cache
        should_quarantine = self.quarantine_corrupted if quarantine_corrupted is None else quarantine_corrupted

        live_data = None
        if not mock_network_failure and self.endpoint_url:
            live_data = self.fetch_live_updates()

        # If live_data exists and contains valid payload, use it
        if isinstance(live_data, dict) and "regions" in live_data:
            try:
                payload = SubsidyPayload.from_dict(live_data)
                if not payload.regions or len(payload.regions) < 17:
                    raise ValueError(
                        f"Invalid live data schema: expected >= 17 regions, found {len(payload.regions) if payload.regions else 0}"
                    )
                # Recalculate metrics to guarantee invariants
                for idx, r in enumerate(payload.regions):
                    payload.regions[idx] = self.update_region_metrics(r)
                payload.nationwide_summary = self.compute_nationwide_summary(payload.regions)
                payload.metadata.generated_at = datetime.now(timezone.utc).isoformat()
                logger.info("Successfully refreshed tracking data from live endpoint.")
                return payload, False
            except Exception as e:
                logger.warning("Error parsing live data: %s. Falling back to baseline.", e)

        # Fallback to local cached file if available, otherwise built-in baseline
        payload = None
        if self.cache_fallback_path and self.cache_fallback_path.exists():
            payload = self.load_cached_payload(
                cache_path=self.cache_fallback_path,
                validate=should_validate,
                quarantine=should_quarantine,
            )

        if payload is None:
            logger.info("Generating authoritative 2026 baseline dataset.")
            payload = build_initial_baseline()

        # Update timestamp and verify metrics
        try:
            for idx, r in enumerate(payload.regions):
                payload.regions[idx] = self.update_region_metrics(r)
            payload.nationwide_summary = self.compute_nationwide_summary(payload.regions)
            payload.metadata.generated_at = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            logger.warning("Structural anomaly updating region metrics: %s. Guaranteeing safe baseline fallback.", e)
            if should_quarantine and self.cache_fallback_path:
                self.quarantine_corrupted_cache(self.cache_fallback_path)
            payload = build_initial_baseline()
            for idx, r in enumerate(payload.regions):
                payload.regions[idx] = self.update_region_metrics(r)
            payload.nationwide_summary = self.compute_nationwide_summary(payload.regions)
            payload.metadata.generated_at = datetime.now(timezone.utc).isoformat()

        return payload, True

    def collect_and_save(
        self,
        sync_web: bool = False,
        output_path: Optional[Union[str, Path]] = None,
        dry_run: bool = False,
        quarantine_corrupted: bool = False,
        sync_defects: bool = False,
    ) -> SubsidyPayload:
        """Execute complete subsidy collection cycle and atomically save to disk.

        Conforms to PROJECT.md interface contract:
        SubsidyTracker.collect_and_save(
            sync_web: bool, output_path: Optional[str], dry_run: bool, sync_defects: bool
        ) -> SubsidyPayload
        """
        payload, fallback_used = self.execute_tracking_cycle(
            validate_cache=True,
            quarantine_corrupted=quarantine_corrupted,
        )

        if not dry_run:
            cwd = Path.cwd()
            destinations: List[Path] = []

            if output_path:
                primary = Path(output_path)
            elif self.cache_fallback_path:
                primary = Path(self.cache_fallback_path)
            elif (cwd / "src" / "data").exists():
                primary = cwd / "src" / "data" / "ev_subsidy_data.json"
            else:
                primary = cwd / "data" / "ev_subsidy_data.json"

            destinations.append(primary)

            # Ensure subsidy_depletion_data.json mirror parity
            if primary.name == "ev_subsidy_data.json":
                destinations.append(primary.parent / "subsidy_depletion_data.json")
            elif primary.name == "subsidy_depletion_data.json":
                destinations.append(primary.parent / "ev_subsidy_data.json")

            if sync_web:
                web_dir_env = os.getenv("EV_TRACKER_WEB_DIR")
                if web_dir_env:
                    web_dir = Path(web_dir_env)
                    destinations.append(web_dir / "ev_subsidy_data.json")
                    destinations.append(web_dir / "subsidy_depletion_data.json")
                elif (cwd / "src" / "data").exists():
                    destinations.append(cwd / "src" / "data" / "ev_subsidy_data.json")
                    destinations.append(cwd / "src" / "data" / "subsidy_depletion_data.json")
                    if (cwd.parent / "data").exists():
                        destinations.append(cwd.parent / "data" / "ev_subsidy_data.json")
                        destinations.append(cwd.parent / "data" / "subsidy_depletion_data.json")
                else:
                    destinations.append(cwd / "ev-stealth-web" / "src" / "data" / "ev_subsidy_data.json")
                    destinations.append(cwd / "ev-stealth-web" / "src" / "data" / "subsidy_depletion_data.json")

            # Deduplicate destinations preserving order
            unique_destinations: List[Path] = []
            seen_paths = set()
            for dst in destinations:
                resolved_key = str(dst.resolve()) if dst.exists() else str(dst.absolute())
                if resolved_key not in seen_paths:
                    seen_paths.add(resolved_key)
                    unique_destinations.append(dst)

            self.save_payload(payload, unique_destinations)

        if sync_defects:
            try:
                from run_tracker import sync_defect_reports

                web_dir_env = os.getenv("EV_TRACKER_WEB_DIR")
                web_dir = Path(web_dir_env) if web_dir_env else None
                sync_defect_reports(web_dir=web_dir, dry_run=dry_run, run_crawler=False)
            except Exception as e:
                logger.warning("Failed to synchronize defect reports in collect_and_save: %s", e)

        return payload

    def save_payload(
        self,
        payload: SubsidyPayload,
        destination_paths: List[Union[str, Path]],
        export_models_matrix: bool = True,
    ) -> List[Path]:
        """Atomically persist payload to all destination paths and export models matrix."""
        written = atomic_write_json_multiple(payload, destination_paths)
        for w in written:
            logger.info("Saved subsidy dataset: %s", w)

        if export_models_matrix:
            matrix_data = build_comprehensive_models_matrix()
            seen_matrix_dirs = set()
            for p in destination_paths:
                parent_dir = Path(p).parent.resolve()
                if parent_dir not in seen_matrix_dirs:
                    seen_matrix_dirs.add(parent_dir)
                    matrix_file = parent_dir / "models_subsidy_matrix.json"
                    try:
                        atomic_write_json(matrix_data, matrix_file)
                        logger.info("  ✓ Saved vehicle models matrix: %s", matrix_file)
                    except Exception as exc:
                        logger.warning("Failed to save models matrix to %s: %s", matrix_file, exc)

        return written

    def generate_briefing(self, payload: SubsidyPayload, fallback_used: bool = False) -> str:
        """Generate formatted executive markdown summary briefing."""
        return self.report_generator.generate_subsidy_briefing(payload, fallback_used=fallback_used)


def build_comprehensive_models_matrix() -> List[Dict[str, Any]]:
    """Build comprehensive 2026 Korean EV models matrix (18 models) with statutory subsidy specs."""
    baseline_models = build_popular_models()
    models_dict_list: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()

    for m in baseline_models:
        m_dict = m.to_dict() if hasattr(m, "to_dict") else dict(m)
        # Ensure price_subsidy_ratio matches statutory calculation
        m_dict["price_subsidy_ratio"] = calculate_price_cap_ratio(m_dict["base_price_krw"])
        models_dict_list.append(m_dict)
        seen_ids.add(m_dict["model_id"])

    additional_models = [
        {
            "model_id": "ioniq-6-2026",
            "name_ko": "현대 아이오닉 6 롱레인지 2WD (2026)",
            "manufacturer": "현대자동차",
            "battery_type": "NCM 삼원계 (SK온 77.4kWh)",
            "battery_capacity_kwh": 77.4,
            "rated_range_km": 524,
            "base_price_krw": 52_000_000,
            "price_subsidy_ratio": 1.0,
            "national_subsidy_krw": 6_500_000,
            "regional_subsidy_samples": {
                "seoul": {"local_subsidy_krw": 1_500_000, "total_subsidy_krw": 8_000_000, "net_price_krw": 44_000_000},
                "gyeonggi_avg": {"local_subsidy_krw": 2_600_000, "total_subsidy_krw": 9_100_000, "net_price_krw": 42_900_000},
            },
        },
        {
            "model_id": "genesis-gv60-2026",
            "name_ko": "제네시스 GV60 스탠다드 2WD (2026)",
            "manufacturer": "제네시스",
            "battery_type": "NCM 삼원계 (SK온 77.4kWh)",
            "battery_capacity_kwh": 77.4,
            "rated_range_km": 451,
            "base_price_krw": 64_900_000,
            "price_subsidy_ratio": 0.5,
            "national_subsidy_krw": 3_150_000,
            "regional_subsidy_samples": {
                "seoul": {"local_subsidy_krw": 727_000, "total_subsidy_krw": 3_877_000, "net_price_krw": 61_023_000},
                "gyeonggi_avg": {"local_subsidy_krw": 1_260_000, "total_subsidy_krw": 4_410_000, "net_price_krw": 60_490_000},
            },
        },
        {
            "model_id": "bmw-i4-edrive40",
            "name_ko": "BMW i4 eDrive40 (2026)",
            "manufacturer": "BMW",
            "battery_type": "NCM 삼원계 (삼성SDI 83.9kWh)",
            "battery_capacity_kwh": 83.9,
            "rated_range_km": 429,
            "base_price_krw": 78_200_000,
            "price_subsidy_ratio": 0.5,
            "national_subsidy_krw": 2_120_000,
            "regional_subsidy_samples": {
                "seoul": {"local_subsidy_krw": 489_000, "total_subsidy_krw": 2_609_000, "net_price_krw": 75_591_000},
                "gyeonggi_avg": {"local_subsidy_krw": 848_000, "total_subsidy_krw": 2_968_000, "net_price_krw": 75_232_000},
            },
        },
        {
            "model_id": "audi-q4-e-tron",
            "name_ko": "아우디 Q4 40 e-트론 (2026)",
            "manufacturer": "아우디",
            "battery_type": "NCM 삼원계 (LG엔솔 82kWh)",
            "battery_capacity_kwh": 82.0,
            "rated_range_km": 411,
            "base_price_krw": 61_700_000,
            "price_subsidy_ratio": 0.5,
            "national_subsidy_krw": 1_980_000,
            "regional_subsidy_samples": {
                "seoul": {"local_subsidy_krw": 457_000, "total_subsidy_krw": 2_437_000, "net_price_krw": 59_263_000},
                "gyeonggi_avg": {"local_subsidy_krw": 792_000, "total_subsidy_krw": 2_772_000, "net_price_krw": 58_928_000},
            },
        },
        {
            "model_id": "polestar-4-long-range",
            "name_ko": "폴스타 4 롱레인지 싱글모터 (2026)",
            "manufacturer": "폴스타",
            "battery_type": "NCM 삼원계 (CATL 100kWh)",
            "battery_capacity_kwh": 100.0,
            "rated_range_km": 511,
            "base_price_krw": 66_900_000,
            "price_subsidy_ratio": 0.5,
            "national_subsidy_krw": 2_250_000,
            "regional_subsidy_samples": {
                "seoul": {"local_subsidy_krw": 519_000, "total_subsidy_krw": 2_769_000, "net_price_krw": 64_131_000},
                "gyeonggi_avg": {"local_subsidy_krw": 900_000, "total_subsidy_krw": 3_150_000, "net_price_krw": 63_750_000},
            },
        },
        {
            "model_id": "genesis-electrified-g80",
            "name_ko": "제네시스 일렉트리파이드 G80 (2026)",
            "manufacturer": "제네시스",
            "battery_type": "NCM 삼원계 (SK온 94.5kWh)",
            "battery_capacity_kwh": 94.5,
            "rated_range_km": 475,
            "base_price_krw": 89_190_000,
            "price_subsidy_ratio": 0.0,
            "national_subsidy_krw": 0,
            "regional_subsidy_samples": {
                "seoul": {"local_subsidy_krw": 0, "total_subsidy_krw": 0, "net_price_krw": 89_190_000},
                "gyeonggi_avg": {"local_subsidy_krw": 0, "total_subsidy_krw": 0, "net_price_krw": 89_190_000},
            },
        },
        {
            "model_id": "benz-eqe-350",
            "name_ko": "메르세데스-벤츠 EQE 350+ (2026)",
            "manufacturer": "메르세데스-벤츠",
            "battery_type": "NCM 삼원계 (CATL 90.6kWh)",
            "battery_capacity_kwh": 90.6,
            "rated_range_km": 471,
            "base_price_krw": 103_800_000,
            "price_subsidy_ratio": 0.0,
            "national_subsidy_krw": 0,
            "regional_subsidy_samples": {
                "seoul": {"local_subsidy_krw": 0, "total_subsidy_krw": 0, "net_price_krw": 103_800_000},
                "gyeonggi_avg": {"local_subsidy_krw": 0, "total_subsidy_krw": 0, "net_price_krw": 103_800_000},
            },
        },
        {
            "model_id": "porsche-taycan",
            "name_ko": "포르쉐 타이칸 (2026)",
            "manufacturer": "포르쉐",
            "battery_type": "NCM 삼원계 (LG엔솔 105kWh)",
            "battery_capacity_kwh": 105.0,
            "rated_range_km": 500,
            "base_price_krw": 129_900_000,
            "price_subsidy_ratio": 0.0,
            "national_subsidy_krw": 0,
            "regional_subsidy_samples": {
                "seoul": {"local_subsidy_krw": 0, "total_subsidy_krw": 0, "net_price_krw": 129_900_000},
                "gyeonggi_avg": {"local_subsidy_krw": 0, "total_subsidy_krw": 0, "net_price_krw": 129_900_000},
            },
        },
    ]

    for am in additional_models:
        if am["model_id"] not in seen_ids:
            am["price_subsidy_ratio"] = calculate_price_cap_ratio(am["base_price_krw"])
            models_dict_list.append(am)
            seen_ids.add(am["model_id"])

    return models_dict_list


def export_models_subsidy_matrix(target_dirs: Optional[List[Union[str, Path]]] = None) -> List[Path]:
    """Atomically export comprehensive 2026 EV models subsidy matrix (>=15 models) to target directories."""
    matrix_data = build_comprehensive_models_matrix()
    if target_dirs is None:
        cwd = Path.cwd()
        candidates = [
            cwd / "data",
            cwd / "ev-stealth-web" / "src" / "data",
            cwd / "src" / "data",
            cwd.parent / "data",
        ]
        target_dirs = [c for c in candidates if c.exists()]
        if not target_dirs:
            target_dirs = [cwd / "data"]

    written_paths: List[Path] = []
    for d in target_dirs:
        dest_dir = Path(d).resolve()
        dest_file = dest_dir / "models_subsidy_matrix.json"
        try:
            w = atomic_write_json(matrix_data, dest_file)
            written_paths.append(w)
            logger.info("  ✓ Successfully exported models matrix to %s", dest_file)
        except Exception as exc:
            logger.warning("Failed to export models matrix to %s: %s", dest_file, exc)

    return written_paths


__all__ = [
    "SubsidyTracker",
    "get_baseline_regions",
    "get_baseline_models",
    "get_baseline_thresholds",
    "get_baseline_dataset",
    "calculate_depletion_rate",
    "calculate_remaining_units",
    "classify_alert_tier",
    "calculate_price_cap_ratio",
    "calculate_net_subsidy",
    "build_comprehensive_models_matrix",
    "export_models_subsidy_matrix",
    "_metric_val",
]
