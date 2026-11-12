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
    RegionSubsidy,
    SubsidyMetadata,
    SubsidyPayload,
    SubsidySnapshot,
    VehicleSubsidy,
)
from tracker.defect_tracker import DefectTracker
from tracker.report_generator import ReportGenerator, format_currency_krw, format_percentage
from tracker.subsidy_tracker import (
    SubsidyTracker,
    calculate_delivery_rate,
    calculate_depletion_rate,
    calculate_depletion_velocity,
    calculate_net_subsidy,
    calculate_pending_deliveries,
    calculate_price_cap_ratio,
    calculate_remaining_units,
    calculate_waitlist_units,
    classify_alert_tier,
    classify_region_group,
    get_baseline_dataset,
    get_baseline_models,
    get_baseline_regions,
    get_baseline_thresholds,
    predict_exhaustion_date,
    predict_exhaustion_days,
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
    # Model Aliases
    "RegionSubsidy",
    "VehicleSubsidy",
    "SubsidySnapshot",
    # Main Engines & Formatters
    "SubsidyTracker",
    "DefectTracker",
    "ReportGenerator",
    "format_currency_krw",
    "format_percentage",
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
    "calculate_waitlist_units",
    "calculate_delivery_rate",
    "calculate_pending_deliveries",
    "calculate_depletion_velocity",
    "predict_exhaustion_days",
    "predict_exhaustion_date",
    "classify_alert_tier",
    "classify_region_group",
    "calculate_price_cap_ratio",
    "calculate_net_subsidy",
]
