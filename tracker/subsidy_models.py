"""Strongly typed models for EV Subsidy Depletion Tracking and Analytics.

This module provides data models matching the EV Subsidy Depletion JSON Schema
specifying regional quotas, depletion rates, 5-tier alert thresholds, and
popular vehicle price/subsidy matrices.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


def _safe_int(val: Any, default: int = 0) -> int:
    """Safely convert value to int, catching None, ValueError, and TypeError."""
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert value to float, catching None, ValueError, and TypeError."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


class AlertSeverity(str, Enum):
    """5-tier alert severity levels for EV subsidy depletion."""

    HEALTHY = "HEALTHY"
    CAUTION = "CAUTION"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    DEPLETED = "DEPLETED"

    @classmethod
    def from_rate(cls, rate: float) -> AlertSeverity:
        """Determine alert severity tier based on depletion percentage."""
        if rate >= 100.0:
            return cls.DEPLETED
        elif rate >= 95.0:
            return cls.CRITICAL
        elif rate >= 80.0:
            return cls.WARNING
        elif rate >= 60.0:
            return cls.CAUTION
        else:
            return cls.HEALTHY


@dataclass
class AlertThresholdConfig:
    """Configuration for an alert threshold tier."""

    min_percent: float
    max_percent: float
    label_ko: str
    severity: str
    color_hex: str
    badge_class: str
    recommended_action: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AlertThresholdConfig:
        return cls(
            min_percent=_safe_float(data.get("min_percent", 0.0)),
            max_percent=_safe_float(data.get("max_percent", 0.0)),
            label_ko=str(data.get("label_ko", "")),
            severity=str(data.get("severity", "")),
            color_hex=str(data.get("color_hex", "")),
            badge_class=str(data.get("badge_class", "")),
            recommended_action=str(data.get("recommended_action", "")),
        )


@dataclass
class CategoryMetrics:
    """Metrics for a specific vehicle category (passenger, commercial, bus)."""

    announced_units: int
    applied_units: int
    delivered_units: int
    remaining_units: int
    depletion_rate: float
    delivery_rate: float
    status: str
    max_local_subsidy_krw: int
    max_total_subsidy_krw: int
    total_budget_krw: int = 0
    remaining_budget_krw: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CategoryMetrics:
        if not isinstance(data, dict):
            data = {}
        return cls(
            announced_units=_safe_int(data.get("announced_units", 0)),
            applied_units=_safe_int(data.get("applied_units", 0)),
            delivered_units=_safe_int(data.get("delivered_units", 0)),
            remaining_units=_safe_int(data.get("remaining_units", 0)),
            depletion_rate=_safe_float(data.get("depletion_rate", 0.0)),
            delivery_rate=_safe_float(data.get("delivery_rate", 0.0)),
            status=str(data.get("status") or "HEALTHY"),
            max_local_subsidy_krw=_safe_int(data.get("max_local_subsidy_krw", 0)),
            max_total_subsidy_krw=_safe_int(data.get("max_total_subsidy_krw", 0)),
            total_budget_krw=_safe_int(data.get("total_budget_krw", 0)),
            remaining_budget_krw=_safe_int(data.get("remaining_budget_krw", 0)),
        )


@dataclass
class MunicipalityMetrics:
    """Metrics for lower-tier administrative units (cities/counties within provinces)."""

    name_ko: str = ""
    announced_units: int = 0
    applied_units: int = 0
    remaining_units: int = 0
    depletion_rate: float = 0.0
    status: str = "HEALTHY"
    local_subsidy_krw: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MunicipalityMetrics:
        if not isinstance(data, dict):
            data = {}
        return cls(
            name_ko=str(data.get("name_ko") or ""),
            announced_units=_safe_int(data.get("announced_units", 0)),
            applied_units=_safe_int(data.get("applied_units", 0)),
            remaining_units=_safe_int(data.get("remaining_units", 0)),
            depletion_rate=_safe_float(data.get("depletion_rate", 0.0)),
            status=str(data.get("status") or "HEALTHY"),
            local_subsidy_krw=_safe_int(data.get("local_subsidy_krw", 0)),
        )


@dataclass
class RegionRecord:
    """Record for a 1st-tier administrative division (Province / Metropolitan City)."""

    region_id: str = ""
    iso_code: str = ""
    name_ko: str = ""
    name_en: str = ""
    tier: str = "province"
    overall_depletion_rate: float = 0.0
    overall_status: str = "HEALTHY"
    residency_requirement_days: int = 30
    supplementary_budget_added: bool = False
    categories: Dict[str, CategoryMetrics] = field(default_factory=dict)
    municipalities: List[MunicipalityMetrics] = field(default_factory=list)
    notes: str = ""
    code: Optional[str] = None

    def __post_init__(self):
        if self.code and not self.iso_code:
            self.iso_code = self.code
        if self.code and not self.region_id:
            self.region_id = self.code
        if self.iso_code and not self.region_id:
            self.region_id = self.iso_code

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "region_id": self.region_id,
            "iso_code": self.iso_code,
            "name_ko": self.name_ko,
            "name_en": self.name_en,
            "tier": self.tier,
            "overall_depletion_rate": self.overall_depletion_rate,
            "overall_status": self.overall_status,
            "residency_requirement_days": self.residency_requirement_days,
            "supplementary_budget_added": self.supplementary_budget_added,
            "categories": {k: v.to_dict() if hasattr(v, "to_dict") else v for k, v in self.categories.items()},
            "notes": self.notes,
        }
        if self.municipalities:
            result["municipalities"] = [m.to_dict() if hasattr(m, "to_dict") else m for m in self.municipalities]
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RegionRecord:
        if not isinstance(data, dict):
            data = {}
        cats = {}
        cats_raw = data.get("categories") or {}
        if isinstance(cats_raw, dict):
            for cat_name, cat_data in cats_raw.items():
                if isinstance(cat_data, CategoryMetrics):
                    cats[cat_name] = cat_data
                elif isinstance(cat_data, dict):
                    cats[cat_name] = CategoryMetrics.from_dict(cat_data)

        munis = []
        munis_raw = data.get("municipalities") or []
        if isinstance(munis_raw, (list, tuple)):
            for muni_data in munis_raw:
                if isinstance(muni_data, MunicipalityMetrics):
                    munis.append(muni_data)
                elif isinstance(muni_data, dict):
                    munis.append(MunicipalityMetrics.from_dict(muni_data))

        return cls(
            region_id=str(data.get("region_id") or data.get("code") or ""),
            iso_code=str(data.get("iso_code") or data.get("code") or ""),
            name_ko=str(data.get("name_ko") or ""),
            name_en=str(data.get("name_en") or ""),
            tier=str(data.get("tier") or "province"),
            overall_depletion_rate=_safe_float(data.get("overall_depletion_rate", 0.0)),
            overall_status=str(data.get("overall_status") or "HEALTHY"),
            residency_requirement_days=_safe_int(data.get("residency_requirement_days", 30), default=30),
            supplementary_budget_added=bool(data.get("supplementary_budget_added", False)),
            categories=cats,
            municipalities=munis,
            notes=str(data.get("notes") or ""),
        )


@dataclass
class PopularModelEntry:
    """EV model specification, pricing, and regional subsidy samples."""

    model_id: str
    name_ko: str
    manufacturer: str
    battery_type: str
    battery_capacity_kwh: float
    rated_range_km: int
    base_price_krw: int
    price_subsidy_ratio: float
    national_subsidy_krw: int
    regional_subsidy_samples: Dict[str, Dict[str, int]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PopularModelEntry:
        if not isinstance(data, dict):
            data = {}
        return cls(
            model_id=str(data.get("model_id") or ""),
            name_ko=str(data.get("name_ko") or ""),
            manufacturer=str(data.get("manufacturer") or ""),
            battery_type=str(data.get("battery_type") or ""),
            battery_capacity_kwh=_safe_float(data.get("battery_capacity_kwh", 0.0)),
            rated_range_km=_safe_int(data.get("rated_range_km", 0)),
            base_price_krw=_safe_int(data.get("base_price_krw", 0)),
            price_subsidy_ratio=_safe_float(data.get("price_subsidy_ratio", 1.0), default=1.0),
            national_subsidy_krw=_safe_int(data.get("national_subsidy_krw", 0)),
            regional_subsidy_samples=data.get("regional_subsidy_samples") or {},
        )


@dataclass
class HistoricalTrajectoryPoint:
    """Monthly historical progress record of subsidy depletion."""

    date: str
    passenger_rate: float
    commercial_rate: float
    overall_rate: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> HistoricalTrajectoryPoint:
        if not isinstance(data, dict):
            data = {}
        return cls(
            date=str(data.get("date") or ""),
            passenger_rate=_safe_float(data.get("passenger_rate", 0.0)),
            commercial_rate=_safe_float(data.get("commercial_rate", 0.0)),
            overall_rate=_safe_float(data.get("overall_rate", 0.0)),
        )


@dataclass
class NationwideSummary:
    """Nationwide aggregates across all 17 regions."""

    total_announced_units: int
    total_applied_units: int
    total_delivered_units: int
    total_remaining_units: int
    nationwide_depletion_rate: float
    total_budget_billion_krw: float
    disbursed_budget_billion_krw: float
    category_totals: Dict[str, Any]
    alert_region_counts: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_announced_units": self.total_announced_units,
            "total_applied_units": self.total_applied_units,
            "total_delivered_units": self.total_delivered_units,
            "total_remaining_units": self.total_remaining_units,
            "nationwide_depletion_rate": self.nationwide_depletion_rate,
            "total_budget_billion_krw": self.total_budget_billion_krw,
            "disbursed_budget_billion_krw": self.disbursed_budget_billion_krw,
            "category_totals": {
                k: v.to_dict() if hasattr(v, "to_dict") else v
                for k, v in self.category_totals.items()
            },
            "alert_region_counts": self.alert_region_counts,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> NationwideSummary:
        if not isinstance(data, dict):
            data = {}
        cat_totals = {}
        cat_totals_raw = data.get("category_totals") or {}
        if isinstance(cat_totals_raw, dict):
            for k, v in cat_totals_raw.items():
                if isinstance(v, CategoryMetrics):
                    cat_totals[k] = v
                elif isinstance(v, dict):
                    cat_totals[k] = CategoryMetrics.from_dict(v)
                else:
                    cat_totals[k] = v

        alert_region_counts = data.get("alert_region_counts")
        if not isinstance(alert_region_counts, dict):
            alert_region_counts = {}

        return cls(
            total_announced_units=_safe_int(data.get("total_announced_units", 0)),
            total_applied_units=_safe_int(data.get("total_applied_units", 0)),
            total_delivered_units=_safe_int(data.get("total_delivered_units", 0)),
            total_remaining_units=_safe_int(data.get("total_remaining_units", 0)),
            nationwide_depletion_rate=_safe_float(data.get("nationwide_depletion_rate", 0.0)),
            total_budget_billion_krw=_safe_float(data.get("total_budget_billion_krw", 0.0)),
            disbursed_budget_billion_krw=_safe_float(data.get("disbursed_budget_billion_krw", 0.0)),
            category_totals=cat_totals,
            alert_region_counts=alert_region_counts,
        )


@dataclass
class SubsidyMetadata:
    """Metadata describing the dataset generation context."""

    version: str
    generated_at: str
    policy_year: int
    data_sources: List[str]
    total_regions_tracked: int
    total_municipalities_tracked: int
    currency: str = "KRW"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SubsidyMetadata:
        if not isinstance(data, dict):
            data = {}
        ds = data.get("data_sources")
        data_sources = list(ds) if isinstance(ds, (list, tuple, set)) else []
        return cls(
            version=str(data.get("version") or "1.0.0"),
            generated_at=str(data.get("generated_at") or ""),
            policy_year=_safe_int(data.get("policy_year", 2026), default=2026),
            data_sources=data_sources,
            total_regions_tracked=_safe_int(data.get("total_regions_tracked", 17), default=17),
            total_municipalities_tracked=_safe_int(data.get("total_municipalities_tracked", 0)),
            currency=str(data.get("currency") or "KRW"),
        )


@dataclass
class SubsidyPayload:
    """Root data structure conforming to the EV Subsidy JSON Schema."""

    metadata: SubsidyMetadata
    alert_thresholds: Dict[str, AlertThresholdConfig]
    nationwide_summary: NationwideSummary
    regions: List[RegionRecord]
    popular_models_matrix: List[PopularModelEntry]
    historical_depletion_trajectory: List[HistoricalTrajectoryPoint]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "alert_thresholds": {
                k: v.to_dict() if hasattr(v, "to_dict") else v
                for k, v in self.alert_thresholds.items()
            },
            "nationwide_summary": self.nationwide_summary.to_dict(),
            "regions": [r.to_dict() for r in self.regions],
            "popular_models_matrix": [m.to_dict() for m in self.popular_models_matrix],
            "historical_depletion_trajectory": [
                h.to_dict() if hasattr(h, "to_dict") else h
                for h in self.historical_depletion_trajectory
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SubsidyPayload:
        if not isinstance(data, dict):
            data = {}
        meta_dict = data.get("metadata")
        metadata = SubsidyMetadata.from_dict(meta_dict if isinstance(meta_dict, dict) else {})

        alert_thresholds = {}
        at_dict = data.get("alert_thresholds") or {}
        if isinstance(at_dict, dict):
            for k, v in at_dict.items():
                if isinstance(v, AlertThresholdConfig):
                    alert_thresholds[k] = v
                elif isinstance(v, dict):
                    alert_thresholds[k] = AlertThresholdConfig.from_dict(v)

        ns_dict = data.get("nationwide_summary")
        summary = NationwideSummary.from_dict(ns_dict if isinstance(ns_dict, dict) else {})

        regions_raw = data.get("regions") or []
        regions = [
            RegionRecord.from_dict(r) if isinstance(r, dict) else r
            for r in regions_raw
            if isinstance(r, (dict, RegionRecord))
        ]

        models_raw = data.get("popular_models_matrix") or []
        models = [
            PopularModelEntry.from_dict(m) if isinstance(m, dict) else m
            for m in models_raw
            if isinstance(m, (dict, PopularModelEntry))
        ]

        history_raw = data.get("historical_depletion_trajectory") or []
        history = [
            HistoricalTrajectoryPoint.from_dict(h) if isinstance(h, dict) else h
            for h in history_raw
            if isinstance(h, (dict, HistoricalTrajectoryPoint))
        ]

        return cls(
            metadata=metadata,
            alert_thresholds=alert_thresholds,
            nationwide_summary=summary,
            regions=regions,
            popular_models_matrix=models,
            historical_depletion_trajectory=history,
        )
