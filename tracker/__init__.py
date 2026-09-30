"""EV Subsidy Depletion Tracker Package.

Modular components for South Korea EV Subsidy tracking, metrics computation,
alert threshold evaluation, and crash-durable atomic JSON persistence.
"""

from tracker.atomic_writer import atomic_write_json, atomic_write_json_multiple
from tracker.subsidy_baseline import (
    BUS_NATIONAL_CAP_KRW,
    COMMERCIAL_NATIONAL_CAP_KRW,
    DEFAULT_ALERT_THRESHOLDS,
    PASSENGER_NATIONAL_CAP_KRW,
    build_baseline_regions,
    build_historical_trajectory,
    build_initial_baseline,
    build_popular_models,
)
from tracker.subsidy_models import (
    AlertSeverity,
    AlertThresholdConfig,
    CategoryMetrics,
    HistoricalTrajectoryPoint,
    MunicipalityMetrics,
    NationwideSummary,
    PopularModelEntry,
    RegionRecord,
    SubsidyMetadata,
    SubsidyPayload,
)
from tracker.subsidy_tracker import (
    SubsidyTracker,
    calculate_depletion_rate,
    calculate_net_subsidy,
    calculate_price_cap_ratio,
    calculate_remaining_units,
    classify_alert_tier,
    get_baseline_dataset,
    get_baseline_models,
    get_baseline_regions,
    get_baseline_thresholds,
)

__all__ = [
    # Data Models
    "AlertSeverity",
    "AlertThresholdConfig",
    "CategoryMetrics",
    "HistoricalTrajectoryPoint",
    "MunicipalityMetrics",
    "NationwideSummary",
    "PopularModelEntry",
    "RegionRecord",
    "SubsidyMetadata",
    "SubsidyPayload",
    # Main Engine
    "SubsidyTracker",
    # Persistence
    "atomic_write_json",
    "atomic_write_json_multiple",
    # Statutory Caps & Defaults
    "PASSENGER_NATIONAL_CAP_KRW",
    "COMMERCIAL_NATIONAL_CAP_KRW",
    "BUS_NATIONAL_CAP_KRW",
    "DEFAULT_ALERT_THRESHOLDS",
    # Baseline Builders & Getters
    "build_baseline_regions",
    "build_historical_trajectory",
    "build_initial_baseline",
    "build_popular_models",
    "get_baseline_regions",
    "get_baseline_models",
    "get_baseline_thresholds",
    "get_baseline_dataset",
    # Calculation & Logic Functions
    "calculate_depletion_rate",
    "calculate_remaining_units",
    "classify_alert_tier",
    "calculate_price_cap_ratio",
    "calculate_net_subsidy",
]

