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

from tracker.atomic_writer import (
    FileLock,
    atomic_write_json,
    atomic_write_json_multiple,
    is_corrupted_or_quarantined_filename,
    quarantine_corrupted_file,
)
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


# ============================================================================
# Authoritative Statutory Regional Grouping Configuration
# ============================================================================

# Metropolitan Cities (8): 서울, 부산, 대구, 인천, 광주, 대전, 울산, 세종
METROPOLITAN_CITIES: Tuple[str, ...] = (
    "서울",
    "부산",
    "대구",
    "인천",
    "광주",
    "대전",
    "울산",
    "세종",
)

# Provinces (9): 경기, 강원, 충북, 충남, 전북, 전남, 경북, 경남, 제주
PROVINCES: Tuple[str, ...] = (
    "경기",
    "강원",
    "충북",
    "충남",
    "전북",
    "전남",
    "경북",
    "경남",
    "제주",
)

METROPOLITAN_CITY_CODES: Tuple[str, ...] = (
    "KR-11",  # 서울특별시
    "KR-26",  # 부산광역시
    "KR-27",  # 대구광역시
    "KR-28",  # 인천광역시
    "KR-29",  # 광주광역시
    "KR-30",  # 대전광역시
    "KR-31",  # 울산광역시
    "KR-36",  # 세종특별자치시
)

PROVINCE_CODES: Tuple[str, ...] = (
    "KR-41",  # 경기도
    "KR-42",  # 강원특별자치도
    "KR-43",  # 충청북도
    "KR-44",  # 충청남도
    "KR-45",  # 전북특별자치도
    "KR-46",  # 전라남도
    "KR-47",  # 경상북도
    "KR-48",  # 경상남도
    "KR-49",  # 제주특별자치도
)

REGIONAL_GROUP_METROPOLITAN: str = "metropolitan_cities"
REGIONAL_GROUP_PROVINCES: str = "provinces"
REGIONAL_GROUP_OTHER: str = "other"


def get_baseline_thresholds() -> Dict[str, Any]:
    """Return default 5-tier alert threshold configuration dictionary."""
    return DEFAULT_ALERT_THRESHOLDS


def calculate_depletion_rate(
    applied: Union[int, float] = 0,
    announced: Union[int, float, None] = None,
    clamp_100: bool = False,
    quota: Union[int, float, None] = None,
    clamp: bool = False,
    max_rate: Optional[float] = None,
) -> float:
    """Calculate EV subsidy depletion rate as percentage with zero-division guard and negative clamping.

    Formula:
        (applied / quota) * 100.0

    Args:
        applied: Number of received applications (int or float).
        announced: Total allocated quota units (legacy alias).
        clamp_100: If True, clamp result to [0.0, 100.0]. Defaults to False to track
                   over-exhaustion / waitlisted status (> 100.0%).
        quota: Total allocated quota units (standard naming). Takes precedence over announced if provided.
        clamp: Alias for clamp_100.
        max_rate: Optional upper bound ceiling for rate clamping.

    Returns:
        Depletion percentage rounded to 1 decimal place, guaranteed non-negative.
    """
    try:
        target_quota = quota if quota is not None else announced
        if target_quota is None or applied is None:
            return 0.0
        quota_val = float(target_quota)
        applied_val = float(applied)
        if math.isnan(quota_val) or math.isnan(applied_val) or math.isinf(quota_val) or math.isinf(applied_val):
            return 0.0
        if quota_val <= 0.0 or applied_val <= 0.0:
            return 0.0
        rate = round((applied_val / quota_val) * 100.0, 1)
        if math.isnan(rate) or math.isinf(rate):
            return 0.0
        rate = max(0.0, rate)
        if clamp_100 or clamp:
            rate = min(100.0, rate)
        if max_rate is not None:
            try:
                rate = min(float(max_rate), rate)
            except (ValueError, TypeError):
                pass
        return rate
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return 0.0


def is_depletion_over_exhausted(depletion_rate: Union[int, float]) -> bool:
    """Return True if depletion rate strictly exceeds 100.0% (over-exhaustion / waitlisted)."""
    try:
        r = float(depletion_rate)
        return not (math.isnan(r) or math.isinf(r)) and r > 100.0
    except (TypeError, ValueError, OverflowError):
        return False


def calculate_remaining_units(
    applied: Union[int, float] = 0,
    announced: Union[int, float, None] = None,
    quota: Union[int, float, None] = None,
) -> int:
    """Calculate remaining quota units clamped at zero: max(0, quota - applied).

    Args:
        applied: Number of received applications.
        announced: Total allocated quota units.
        quota: Standard alias for total allocated quota units.

    Returns:
        Remaining units as non-negative integer (clamped to 0 upon over-subscription).
    """
    try:
        target_quota = quota if quota is not None else announced
        if target_quota is None or applied is None:
            return 0
        quota_f = float(target_quota)
        applied_f = float(applied)
        if math.isnan(quota_f) or math.isnan(applied_f) or math.isinf(quota_f) or math.isinf(applied_f):
            return 0
        safe_quota = max(0, int(quota_f))
        safe_applied = max(0, int(applied_f))
        return max(0, safe_quota - safe_applied)
    except (TypeError, ValueError, OverflowError):
        return 0


def calculate_waitlist_units(
    applied: Union[int, float] = 0,
    announced: Union[int, float, None] = None,
    quota: Union[int, float, None] = None,
) -> int:
    """Calculate waitlisted/over-subscribed units beyond announced quota: max(0, applied - quota)."""
    try:
        target_quota = quota if quota is not None else announced
        if target_quota is None or applied is None:
            return 0
        quota_f = float(target_quota)
        applied_f = float(applied)
        if math.isnan(quota_f) or math.isnan(applied_f) or math.isinf(quota_f) or math.isinf(applied_f):
            return 0
        safe_quota = max(0, int(quota_f))
        safe_applied = max(0, int(applied_f))
        return max(0, safe_applied - safe_quota)
    except (TypeError, ValueError, OverflowError):
        return 0


def calculate_delivery_rate(
    delivered: Union[int, float] = 0,
    announced: Union[int, float, None] = None,
    quota: Union[int, float, None] = None,
    clamp_100: bool = False,
) -> float:
    """Calculate EV delivery rate percentage against announced quota: (delivered / quota) * 100."""
    return calculate_depletion_rate(applied=delivered, announced=announced, quota=quota, clamp_100=clamp_100)


def calculate_pending_deliveries(
    applied: Union[int, float] = 0,
    delivered: Union[int, float] = 0,
) -> int:
    """Calculate pending delivery units (applied - delivered) clamped at zero."""
    try:
        if applied is None or delivered is None:
            return 0
        applied_f = float(applied)
        delivered_f = float(delivered)
        if math.isnan(applied_f) or math.isnan(delivered_f) or math.isinf(applied_f) or math.isinf(delivered_f):
            return 0
        safe_applied = max(0, int(applied_f))
        safe_delivered = max(0, int(delivered_f))
        return max(0, safe_applied - safe_delivered)
    except (TypeError, ValueError, OverflowError):
        return 0


def classify_region_group(region: Union[RegionRecord, Dict[str, Any], str, None]) -> str:
    """Classify region into 'metropolitan_cities', 'provinces', or 'other'.

    Groups:
    - Metropolitan cities (8): 서울, 부산, 대구, 인천, 광주, 대전, 울산, 세종
    - Provinces (9): 경기, 강원, 충북, 충남, 전북, 전남, 경북, 경남, 제주
    """
    if region is None:
        return REGIONAL_GROUP_OTHER

    if isinstance(region, str):
        ident = region.strip()
        if not ident:
            return REGIONAL_GROUP_OTHER
        if ident in METROPOLITAN_CITY_CODES:
            return REGIONAL_GROUP_METROPOLITAN
        if ident in PROVINCE_CODES:
            return REGIONAL_GROUP_PROVINCES
        for city in METROPOLITAN_CITIES:
            if city in ident:
                return REGIONAL_GROUP_METROPOLITAN
        for prov in PROVINCES:
            if prov in ident:
                return REGIONAL_GROUP_PROVINCES
        ident_lower = ident.lower()
        if any(c in ident_lower for c in ("seoul", "busan", "daegu", "incheon", "gwangju", "daejeon", "ulsan", "sejong")):
            return REGIONAL_GROUP_METROPOLITAN
        if any(p in ident_lower for p in ("gyeonggi", "gangwon", "chungbuk", "chungnam", "jeonbuk", "jeonnam", "gyeongbuk", "gyeongnam", "jeju")):
            return REGIONAL_GROUP_PROVINCES
        return REGIONAL_GROUP_OTHER

    iso_code = _metric_val(region, "iso_code", "") or _metric_val(region, "region_id", "")
    iso_str = str(iso_code).strip()
    if iso_str in METROPOLITAN_CITY_CODES:
        return REGIONAL_GROUP_METROPOLITAN
    if iso_str in PROVINCE_CODES:
        return REGIONAL_GROUP_PROVINCES

    name_ko = str(_metric_val(region, "name_ko", "")).strip()
    for city in METROPOLITAN_CITIES:
        if city in name_ko:
            return REGIONAL_GROUP_METROPOLITAN
    for prov in PROVINCES:
        if prov in name_ko:
            return REGIONAL_GROUP_PROVINCES

    name_en = str(_metric_val(region, "name_en", "")).strip().lower()
    if any(c in name_en for c in ("seoul", "busan", "daegu", "incheon", "gwangju", "daejeon", "ulsan", "sejong")):
        return REGIONAL_GROUP_METROPOLITAN
    if any(p in name_en for p in ("gyeonggi", "gangwon", "chungbuk", "chungnam", "jeonbuk", "jeonnam", "gyeongbuk", "gyeongnam", "jeju")):
        return REGIONAL_GROUP_PROVINCES

    tier = str(_metric_val(region, "tier", "")).strip().lower()
    if tier in ("special_city", "metropolitan_city", "special_self_governing_city"):
        return REGIONAL_GROUP_METROPOLITAN
    if tier in ("province", "special_self_governing_province"):
        return REGIONAL_GROUP_PROVINCES

    return REGIONAL_GROUP_OTHER


def is_metropolitan_city(region: Union[RegionRecord, Dict[str, Any], str, None]) -> bool:
    """Return True if region is one of the 8 Metropolitan cities."""
    return classify_region_group(region) == REGIONAL_GROUP_METROPOLITAN


def is_province(region: Union[RegionRecord, Dict[str, Any], str, None]) -> bool:
    """Return True if region is one of the 9 Provinces."""
    return classify_region_group(region) == REGIONAL_GROUP_PROVINCES


def group_regions_by_type(
    regions: Optional[List[Union[RegionRecord, Dict[str, Any]]]] = None,
) -> Dict[str, List[Any]]:
    """Group 17 administrative regions into Metropolitan cities (8) and Provinces (9).

    Returns:
    {
        "metropolitan_cities": [서울, 부산, 대구, 인천, 광주, 대전, 울산, 세종],
        "provinces": [경기, 강원, 충북, 충남, 전북, 전남, 경북, 경남, 제주],
    }
    """
    if regions is None:
        regions = build_baseline_regions()

    grouped: Dict[str, List[Any]] = {
        REGIONAL_GROUP_METROPOLITAN: [],
        REGIONAL_GROUP_PROVINCES: [],
    }

    for r in regions:
        grp = classify_region_group(r)
        if grp == REGIONAL_GROUP_METROPOLITAN:
            grouped[REGIONAL_GROUP_METROPOLITAN].append(r)
        elif grp == REGIONAL_GROUP_PROVINCES:
            grouped[REGIONAL_GROUP_PROVINCES].append(r)
        else:
            if "other" not in grouped:
                grouped["other"] = []
            grouped["other"].append(r)

    return grouped


group_regions_by_category = group_regions_by_type


def generate_fallback_payload() -> SubsidyPayload:
    """Generate authoritative verified 2026 fallback baseline dataset with updated metrics."""
    payload = build_initial_baseline()
    tracker = SubsidyTracker()
    for idx, r in enumerate(payload.regions):
        payload.regions[idx] = tracker.update_region_metrics(r)
    payload.nationwide_summary = tracker.compute_nationwide_summary(payload.regions)
    payload.metadata.generated_at = datetime.now(timezone.utc).isoformat()
    return payload


def classify_alert_tier(depletion_rate: float) -> str:
    """Classify depletion rate into standard 5-tier alert severity level."""
    return AlertSeverity.from_rate(depletion_rate).value


def calculate_price_cap_ratio(msrp: int) -> float:
    """Statutory 2026 Korean EV subsidy ratio tiers: 1.0 (<=55M), 0.5 (55M-85M), 0.0 (>85M)."""
    try:
        if msrp is None:
            return 0.0
        f_msrp = float(msrp)
        if math.isnan(f_msrp) or math.isinf(f_msrp):
            return 0.0
        safe_msrp = int(f_msrp)
    except (ValueError, TypeError, OverflowError):
        return 0.0

    if safe_msrp <= 0:
        return 0.0
    elif safe_msrp <= 55_000_000:
        return 1.0
    elif safe_msrp <= 85_000_000:
        return 0.5
    return 0.0


def calculate_net_subsidy(
    model_national: int,
    max_national: int,
    max_local: int,
    msrp: int,
) -> Dict[str, Union[int, float]]:
    """Calculate national subsidy, local subsidy, total subsidy, and net consumer purchase price."""
    try:
        if msrp is None:
            safe_msrp = 0
        else:
            f_msrp = float(msrp)
            safe_msrp = 0 if (math.isnan(f_msrp) or math.isinf(f_msrp)) else max(0, int(f_msrp))
    except (ValueError, TypeError, OverflowError):
        safe_msrp = 0

    try:
        safe_model_nat = max(0, int(model_national)) if model_national is not None else 0
    except (ValueError, TypeError, OverflowError):
        safe_model_nat = 0

    try:
        safe_max_nat = max(0, int(max_national)) if max_national is not None else 0
    except (ValueError, TypeError, OverflowError):
        safe_max_nat = 0

    try:
        safe_max_loc = max(0, int(max_local)) if max_local is not None else 0
    except (ValueError, TypeError, OverflowError):
        safe_max_loc = 0

    ratio = calculate_price_cap_ratio(safe_msrp)
    effective_national = int(round(safe_model_nat * ratio))
    if safe_max_nat > 0:
        local_ratio = min(1.0, max(0.0, safe_model_nat / safe_max_nat))
    else:
        local_ratio = 0.0
    effective_local = int(round(safe_max_loc * local_ratio * ratio))
    total_subsidy = effective_national + effective_local
    net_price = max(0, safe_msrp - total_subsidy)
    return {
        "national_subsidy_krw": effective_national,
        "local_subsidy_krw": effective_local,
        "total_subsidy_krw": total_subsidy,
        "net_price_krw": net_price,
        "price_cap_ratio": ratio,
    }


def _metric_val(metric: Any, key: str, default: Any = 0) -> Any:
    """Safely extract metric attribute or dict key, supporting dict, Mapping, and dataclass instances."""
    if metric is None:
        return default
    if hasattr(metric, "get") and callable(getattr(metric, "get")):
        val = metric.get(key, default)
        return default if val is None else val
    val = getattr(metric, key, default)
    return default if val is None else val


def _safe_int_metric(val: Any, default: int = 0) -> int:
    """Safely cast value to int, gracefully handling NaN, Inf, None, float strings, and invalid types."""
    if type(val) is int:
        return val
    if val is None:
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return int(f)
    except (ValueError, TypeError, OverflowError):
        return default


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
        safe_announced = max(0, _safe_int_metric(announced, 0))
        safe_applied = max(0, _safe_int_metric(applied, 0))
        safe_delivered = max(0, _safe_int_metric(delivered, 0))
        safe_max_local = max(0, _safe_int_metric(max_local_subsidy, 0))
        safe_national_cap = max(0, _safe_int_metric(national_cap, PASSENGER_NATIONAL_CAP_KRW))
        safe_unit_budget = max(0, _safe_int_metric(avg_per_unit_budget, 10_000_000))

        depletion_rate = calculate_depletion_rate(safe_applied, safe_announced)
        delivery_rate = calculate_depletion_rate(safe_delivered, safe_announced)
        remaining_units = calculate_remaining_units(safe_applied, safe_announced)
        status = self.evaluate_status(depletion_rate).value

        total_budget = safe_announced * safe_unit_budget
        disbursed_budget = safe_applied * safe_unit_budget
        remaining_budget = max(0, total_budget - disbursed_budget)

        return CategoryMetrics(
            announced_units=safe_announced,
            applied_units=safe_applied,
            delivered_units=safe_delivered,
            remaining_units=remaining_units,
            depletion_rate=depletion_rate,
            delivery_rate=delivery_rate,
            status=status,
            max_local_subsidy_krw=safe_max_local,
            max_total_subsidy_krw=safe_max_local + safe_national_cap,
            total_budget_krw=total_budget,
            remaining_budget_krw=remaining_budget,
        )

    def update_region_metrics(self, region: Union[RegionRecord, Dict[str, Any]]) -> Union[RegionRecord, Dict[str, Any]]:
        """Recalculate overall status and depletion rates for a region."""
        if region is None:
            return {}
        if not isinstance(region, dict) and not hasattr(region, "__dict__"):
            return region

        total_announced = 0
        total_applied = 0

        cats = region.get("categories") if isinstance(region, dict) else getattr(region, "categories", {})
        for cat_name, cat in (cats or {}).items():
            safe_ann = max(0, _safe_int_metric(_metric_val(cat, "announced_units", 0), 0))
            safe_app = max(0, _safe_int_metric(_metric_val(cat, "applied_units", 0), 0))
            safe_del = max(0, _safe_int_metric(_metric_val(cat, "delivered_units", 0), 0))
            rem_units = calculate_remaining_units(safe_app, safe_ann)
            dep_rate = calculate_depletion_rate(safe_app, safe_ann)
            del_rate = calculate_depletion_rate(safe_del, safe_ann)
            st_val = self.evaluate_status(dep_rate).value

            safe_total_budget = max(0, _safe_int_metric(_metric_val(cat, "total_budget_krw", 0), 0))
            if safe_total_budget > 0 and safe_ann > 0:
                unit_budget = safe_total_budget / safe_ann
                rem_budget = safe_total_budget - (safe_app * unit_budget)
                safe_rem_budget = min(safe_total_budget, max(0, _safe_int_metric(rem_budget, 0)))
            else:
                cat_rem = max(0, _safe_int_metric(_metric_val(cat, "remaining_budget_krw", 0), 0))
                safe_rem_budget = min(safe_total_budget, cat_rem) if safe_total_budget > 0 else cat_rem

            if hasattr(cat, "announced_units"):
                cat.announced_units = safe_ann
                cat.applied_units = safe_app
                cat.delivered_units = safe_del
                cat.remaining_units = rem_units
                cat.depletion_rate = dep_rate
                cat.delivery_rate = del_rate
                cat.status = st_val
                cat.total_budget_krw = safe_total_budget
                cat.remaining_budget_krw = safe_rem_budget
            elif isinstance(cat, dict):
                cat["announced_units"] = safe_ann
                cat["applied_units"] = safe_app
                cat["delivered_units"] = safe_del
                cat["remaining_units"] = rem_units
                cat["depletion_rate"] = dep_rate
                cat["delivery_rate"] = del_rate
                cat["status"] = st_val
                cat["total_budget_krw"] = safe_total_budget
                cat["remaining_budget_krw"] = safe_rem_budget

            total_announced += safe_ann
            total_applied += safe_app

        # Recalculate municipalities if present
        munis = region.get("municipalities") if isinstance(region, dict) else getattr(region, "municipalities", None)
        if munis:
            for muni in munis:
                safe_m_ann = max(0, _safe_int_metric(_metric_val(muni, "announced_units", 0), 0))
                safe_m_app = max(0, _safe_int_metric(_metric_val(muni, "applied_units", 0), 0))
                safe_m_del = max(0, _safe_int_metric(_metric_val(muni, "delivered_units", 0), 0))
                m_rem = calculate_remaining_units(safe_m_app, safe_m_ann)
                m_dep = calculate_depletion_rate(safe_m_app, safe_m_ann)
                m_stat = self.evaluate_status(m_dep).value

                if hasattr(muni, "announced_units"):
                    muni.announced_units = safe_m_ann
                    muni.applied_units = safe_m_app
                    if hasattr(muni, "delivered_units"):
                        muni.delivered_units = safe_m_del
                    muni.remaining_units = m_rem
                    muni.depletion_rate = m_dep
                    muni.status = m_stat
                elif isinstance(muni, dict):
                    muni["announced_units"] = safe_m_ann
                    muni["applied_units"] = safe_m_app
                    if "delivered_units" in muni or (hasattr(muni, "get") and muni.get("delivered_units") is not None):
                        muni["delivered_units"] = safe_m_del
                    muni["remaining_units"] = m_rem
                    muni["depletion_rate"] = m_dep
                    muni["status"] = m_stat

        # Overall depletion rate is weighted by volume across all categories
        overall_rate = calculate_depletion_rate(total_applied, total_announced)
        st_eval = self.evaluate_status(overall_rate).value
        if isinstance(region, dict):
            region["overall_depletion_rate"] = overall_rate
            region["overall_status"] = st_eval
        elif hasattr(region, "__dict__"):
            region.overall_depletion_rate = overall_rate
            region.overall_status = st_eval
        return region

    def compute_nationwide_summary(self, regions: List[Any]) -> NationwideSummary:
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
            st_raw = r.get("overall_status") if isinstance(r, dict) else getattr(r, "overall_status", "")
            if hasattr(st_raw, "value"):
                st_raw = st_raw.value
            st_str = str(st_raw or "").strip()
            if "." in st_str:
                st_str = st_str.split(".")[-1]
            st_key = st_str.lower()
            if st_key in alert_counts:
                alert_counts[st_key] += 1

            r_cats = (r.get("categories") if isinstance(r, dict) else getattr(r, "categories", None)) or {}
            for c_name, c_data in r_cats.items():
                if c_name not in cat_counts:
                    cat_counts[c_name] = {"announced": 0, "applied": 0, "delivered": 0}

                c_ann = max(0, _safe_int_metric(_metric_val(c_data, "announced_units", 0), 0))
                c_app = max(0, _safe_int_metric(_metric_val(c_data, "applied_units", 0), 0))
                c_del = max(0, _safe_int_metric(_metric_val(c_data, "delivered_units", 0), 0))
                c_tot_b = max(0, _safe_int_metric(_metric_val(c_data, "total_budget_krw", 0), 0))
                c_rem_raw = max(0, _safe_int_metric(_metric_val(c_data, "remaining_budget_krw", 0), 0))
                c_rem_b = min(c_tot_b, c_rem_raw) if c_tot_b > 0 else c_rem_raw

                cat_counts[c_name]["announced"] += c_ann
                cat_counts[c_name]["applied"] += c_app
                cat_counts[c_name]["delivered"] += c_del

                total_announced += c_ann
                total_applied += c_app
                total_delivered += c_del
                total_budget_krw += c_tot_b
                disbursed_budget_krw += max(0, c_tot_b - c_rem_b)

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
                    resp_status = getattr(resp, "status", getattr(resp, "code", 200))
                    if resp_status == 200:
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
                        resp_status,
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
                if hasattr(exc, "fp") and exc.fp:
                    try:
                        exc.fp.close()
                    except Exception:
                        pass
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

    def quarantine_corrupted_cache(
        self,
        cache_path: Union[str, Path],
        suffix: Optional[str] = None,
    ) -> Optional[Path]:
        """Quarantine a corrupted cache file by renaming it with a timestamp suffix or custom suffix."""
        return quarantine_corrupted_file(cache_path, suffix=suffix)

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
        - Quarantined / corrupted filename markers (.corrupted, .corrupt_).
        - Degenerate cache states.

        If corruption is detected:
        - Logs warning.
        - Quarantines or discards corrupted cache gracefully if quarantine is requested.
        - Gracefully discards invalid payload in memory and returns None (triggering fresh baseline computation).
        """
        target_path = Path(cache_path) if cache_path else self.cache_fallback_path
        if not target_path or not target_path.exists():
            return None

        if is_corrupted_or_quarantined_filename(target_path):
            logger.warning("Ignoring quarantined/corrupted cache path %s", target_path)
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
                    r_cats = r.get("categories") if isinstance(r, dict) else getattr(r, "categories", None)
                    if r_cats is None or not isinstance(r_cats, dict):
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

                # Ensure historical trajectory is chronologically sorted and deduplicated
                if payload.historical_depletion_trajectory:
                    seen_dates: Set[str] = set()
                    sorted_pts = sorted(
                        payload.historical_depletion_trajectory,
                        key=lambda pt: getattr(pt, "date", "") or (pt.get("date", "") if isinstance(pt, dict) else ""),
                    )
                    deduped_history = []
                    for pt in sorted_pts:
                        d = getattr(pt, "date", "") or (pt.get("date", "") if isinstance(pt, dict) else "")
                        if d and d not in seen_dates:
                            seen_dates.add(d)
                            deduped_history.append(pt)
                    payload.historical_depletion_trajectory = (
                        deduped_history if len(deduped_history) >= 2 else build_initial_baseline().historical_depletion_trajectory
                    )
                else:
                    payload.historical_depletion_trajectory = build_initial_baseline().historical_depletion_trajectory

                if not payload.popular_models_matrix:
                    payload.popular_models_matrix = build_popular_models()
                if not payload.alert_thresholds:
                    payload.alert_thresholds = build_initial_baseline().alert_thresholds

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
        quarantine_corrupted: Optional[bool] = None,
        sync_defects: bool = False,
    ) -> SubsidyPayload:
        """Execute complete subsidy collection cycle and atomically save to disk.

        Conforms to PROJECT.md interface contract:
        SubsidyTracker.collect_and_save(
            sync_web: bool, output_path: Optional[str], dry_run: bool, sync_defects: bool
        ) -> SubsidyPayload
        """
        should_quarantine = self.quarantine_corrupted if quarantine_corrupted is None else quarantine_corrupted
        payload, fallback_used = self.execute_tracking_cycle(
            validate_cache=True,
            quarantine_corrupted=should_quarantine,
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
                    if (cwd / "public" / "data").exists():
                        destinations.append(cwd / "public" / "data" / "ev_subsidy_data.json")
                        destinations.append(cwd / "public" / "data" / "subsidy_depletion_data.json")
                else:
                    destinations.append(cwd / "ev-stealth-web" / "src" / "data" / "ev_subsidy_data.json")
                    destinations.append(cwd / "ev-stealth-web" / "src" / "data" / "subsidy_depletion_data.json")
                    if (cwd / "ev-stealth-web" / "public" / "data").exists():
                        destinations.append(cwd / "ev-stealth-web" / "public" / "data" / "ev_subsidy_data.json")
                        destinations.append(cwd / "ev-stealth-web" / "public" / "data" / "subsidy_depletion_data.json")
                    if (cwd / "public" / "data").exists():
                        destinations.append(cwd / "public" / "data" / "ev_subsidy_data.json")
                        destinations.append(cwd / "public" / "data" / "subsidy_depletion_data.json")

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
        # Deduplicate paths preserving order
        unique_destinations: List[Path] = []
        seen_paths = set()
        for dst in destination_paths:
            target = Path(dst)
            resolved_key = str(target.resolve()) if target.exists() else str(target.absolute())
            if resolved_key not in seen_paths:
                seen_paths.add(resolved_key)
                unique_destinations.append(target)

        written = atomic_write_json_multiple(payload, unique_destinations)
        for w in written:
            logger.info("Saved subsidy dataset: %s", w)

        if export_models_matrix:
            matrix_data = build_comprehensive_models_matrix()
            seen_matrix_dirs = set()
            for p in unique_destinations:
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

    def group_regions(
        self,
        regions: Optional[List[Union[RegionRecord, Dict[str, Any]]]] = None,
    ) -> Dict[str, List[Any]]:
        """Group regions into metropolitan cities (8) and provinces (9)."""
        return group_regions_by_type(regions)

    def compute_regional_group_summaries(
        self,
        regions: Optional[List[Union[RegionRecord, Dict[str, Any]]]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Compute aggregate metrics for Metropolitan Cities (8) and Provinces (9)."""
        grouped = self.group_regions(regions)
        summaries: Dict[str, Dict[str, Any]] = {}
        for group_name, reg_list in grouped.items():
            tot_ann = 0
            tot_app = 0
            tot_del = 0
            for r in reg_list:
                cats = (r.get("categories") if isinstance(r, dict) else getattr(r, "categories", None)) or {}
                for c in cats.values():
                    tot_ann += max(0, _safe_int_metric(_metric_val(c, "announced_units", 0), 0))
                    tot_app += max(0, _safe_int_metric(_metric_val(c, "applied_units", 0), 0))
                    tot_del += max(0, _safe_int_metric(_metric_val(c, "delivered_units", 0), 0))
            rem = calculate_remaining_units(tot_app, tot_ann)
            rate = calculate_depletion_rate(tot_app, tot_ann)
            del_rate = calculate_delivery_rate(tot_del, tot_ann)
            pending_del = calculate_pending_deliveries(tot_app, tot_del)
            waitlist = calculate_waitlist_units(tot_app, tot_ann)
            summaries[group_name] = {
                "region_count": len(reg_list),
                "total_announced_units": tot_ann,
                "total_applied_units": tot_app,
                "total_delivered_units": tot_del,
                "total_remaining_units": rem,
                "total_pending_deliveries": pending_del,
                "total_waitlist_units": waitlist,
                "depletion_rate": rate,
                "delivery_rate": del_rate,
                "status": self.evaluate_status(rate).value,
                "regions": [
                    _metric_val(r, "name_ko", "") or _metric_val(r, "region_id", "")
                    for r in reg_list
                ],
            }
        return summaries

    def get_fallback_payload(self) -> SubsidyPayload:
        """Return fresh authoritative fallback baseline dataset."""
        return generate_fallback_payload()


def generate_fallback_payload() -> SubsidyPayload:
    """Generate authoritative verified 2026 fallback baseline dataset with updated metrics."""
    payload = build_initial_baseline()
    tracker = SubsidyTracker()
    for idx, r in enumerate(payload.regions):
        payload.regions[idx] = tracker.update_region_metrics(r)
    payload.nationwide_summary = tracker.compute_nationwide_summary(payload.regions)
    payload.metadata.generated_at = datetime.now(timezone.utc).isoformat()
    return payload


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
            cwd / "ev-stealth-web" / "public" / "data",
            cwd / "src" / "data",
            cwd / "public" / "data",
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
    "calculate_waitlist_units",
    "calculate_delivery_rate",
    "calculate_pending_deliveries",
    "is_depletion_over_exhausted",
    "classify_alert_tier",
    "calculate_price_cap_ratio",
    "calculate_net_subsidy",
    "build_comprehensive_models_matrix",
    "export_models_subsidy_matrix",
    "classify_region_group",
    "is_metropolitan_city",
    "is_province",
    "group_regions_by_type",
    "group_regions_by_category",
    "generate_fallback_payload",
    "METROPOLITAN_CITIES",
    "PROVINCES",
    "METROPOLITAN_CITY_CODES",
    "PROVINCE_CODES",
    "REGIONAL_GROUP_METROPOLITAN",
    "REGIONAL_GROUP_PROVINCES",
    "_metric_val",
]
