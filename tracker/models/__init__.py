"""tracker/models/__init__.py - Modular models package.

Provides re-exports for all EV Subsidy domain models, metric containers,
and summary aggregators.
"""

from __future__ import annotations

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

__all__ = [
    "AlertSeverity",
    "AlertThresholdConfig",
    "CategoryMetrics",
    "HistoricalTrajectoryPoint",
    "MunicipalityMetrics",
    "NationwideSummary",
    "PopularModelEntry",
    "RegionRecord",
    "RegionSubsidy",
    "SubsidyMetadata",
    "SubsidyPayload",
    "SubsidySnapshot",
    "VehicleSubsidy",
]
