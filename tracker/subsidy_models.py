"""Strongly typed models for EV Subsidy Depletion Tracking and Analytics.

This module provides data models matching the EV Subsidy Depletion JSON Schema
specifying regional quotas, depletion rates, 5-tier alert thresholds, and
popular vehicle price/subsidy matrices.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


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
        return cls(
            announced_units=int(data.get("announced_units", 0)),
            applied_units=int(data.get("applied_units", 0)),
            delivered_units=int(data.get("delivered_units", 0)),
            remaining_units=int(data.get("remaining_units", 0)),
            depletion_rate=float(data.get("depletion_rate", 0.0)),
            delivery_rate=float(data.get("delivery_rate", 0.0)),
            status=str(data.get("status", "HEALTHY")),
            max_local_subsidy_krw=int(data.get("max_local_subsidy_krw", 0)),
            max_total_subsidy_krw=int(data.get("max_total_subsidy_krw", 0)),
            total_budget_krw=int(data.get("total_budget_krw", 0)),
            remaining_budget_krw=int(data.get("remaining_budget_krw", 0)),
        )


@dataclass
class MunicipalityMetrics:
    """Metrics for lower-tier administrative units (cities/counties within provinces)."""

    name_ko: str
    announced_units: int
    applied_units: int
    remaining_units: int
    depletion_rate: float
    status: str
    local_subsidy_krw: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MunicipalityMetrics:
        return cls(
            name_ko=str(data.get("name_ko", "")),
            announced_units=int(data.get("announced_units", 0)),
            applied_units=int(data.get("applied_units", 0)),
            remaining_units=int(data.get("remaining_units", 0)),
            depletion_rate=float(data.get("depletion_rate", 0.0)),
            status=str(data.get("status", "HEALTHY")),
            local_subsidy_krw=int(data.get("local_subsidy_krw", 0)),
        )


@dataclass
class RegionRecord:
    """Record for a 1st-tier administrative division (Province / Metropolitan City)."""

    region_id: str
    iso_code: str
    name_ko: str
    name_en: str
    tier: str
    overall_depletion_rate: float
    overall_status: str
    residency_requirement_days: int
    supplementary_budget_added: bool
    categories: Dict[str, CategoryMetrics]
    municipalities: List[MunicipalityMetrics] = field(default_factory=list)
    notes: str = ""

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
        cats = {}
        for cat_name, cat_data in data.get("categories", {}).items():
            if isinstance(cat_data, CategoryMetrics):
                cats[cat_name] = cat_data
            else:
                cats[cat_name] = CategoryMetrics.from_dict(cat_data)

        munis = []
        for muni_data in data.get("municipalities", []):
            if isinstance(muni_data, MunicipalityMetrics):
                munis.append(muni_data)
            else:
                munis.append(MunicipalityMetrics.from_dict(muni_data))

        return cls(
            region_id=str(data.get("region_id", "")),
            iso_code=str(data.get("iso_code", "")),
            name_ko=str(data.get("name_ko", "")),
            name_en=str(data.get("name_en", "")),
            tier=str(data.get("tier", "province")),
            overall_depletion_rate=float(data.get("overall_depletion_rate", 0.0)),
            overall_status=str(data.get("overall_status", "HEALTHY")),
            residency_requirement_days=int(data.get("residency_requirement_days", 30)),
            supplementary_budget_added=bool(data.get("supplementary_budget_added", False)),
            categories=cats,
            municipalities=munis,
            notes=str(data.get("notes", "")),
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
        return cls(
            model_id=str(data.get("model_id", "")),
            name_ko=str(data.get("name_ko", "")),
            manufacturer=str(data.get("manufacturer", "")),
            battery_type=str(data.get("battery_type", "")),
            battery_capacity_kwh=float(data.get("battery_capacity_kwh", 0.0)),
            rated_range_km=int(data.get("rated_range_km", 0)),
            base_price_krw=int(data.get("base_price_krw", 0)),
            price_subsidy_ratio=float(data.get("price_subsidy_ratio", 1.0)),
            national_subsidy_krw=int(data.get("national_subsidy_krw", 0)),
            regional_subsidy_samples=data.get("regional_subsidy_samples", {}),
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
        return cls(
            date=str(data.get("date", "")),
            passenger_rate=float(data.get("passenger_rate", 0.0)),
            commercial_rate=float(data.get("commercial_rate", 0.0)),
            overall_rate=float(data.get("overall_rate", 0.0)),
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
        cat_totals = {}
        for k, v in data.get("category_totals", {}).items():
            if isinstance(v, CategoryMetrics):
                cat_totals[k] = v
            elif isinstance(v, dict):
                cat_totals[k] = CategoryMetrics.from_dict(v)
            else:
                cat_totals[k] = v

        return cls(
            total_announced_units=int(data.get("total_announced_units", 0)),
            total_applied_units=int(data.get("total_applied_units", 0)),
            total_delivered_units=int(data.get("total_delivered_units", 0)),
            total_remaining_units=int(data.get("total_remaining_units", 0)),
            nationwide_depletion_rate=float(data.get("nationwide_depletion_rate", 0.0)),
            total_budget_billion_krw=float(data.get("total_budget_billion_krw", 0.0)),
            disbursed_budget_billion_krw=float(data.get("disbursed_budget_billion_krw", 0.0)),
            category_totals=cat_totals,
            alert_region_counts=data.get("alert_region_counts", {}),
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
        return cls(
            version=str(data.get("version", "1.0.0")),
            generated_at=str(data.get("generated_at", "")),
            policy_year=int(data.get("policy_year", 2026)),
            data_sources=list(data.get("data_sources", [])),
            total_regions_tracked=int(data.get("total_regions_tracked", 17)),
            total_municipalities_tracked=int(data.get("total_municipalities_tracked", 0)),
            currency=str(data.get("currency", "KRW")),
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
        metadata = SubsidyMetadata.from_dict(data.get("metadata", {}))

        alert_thresholds = {}
        for k, v in data.get("alert_thresholds", {}).items():
            if isinstance(v, AlertThresholdConfig):
                alert_thresholds[k] = v
            elif isinstance(v, dict):
                alert_thresholds[k] = AlertThresholdConfig(**v)

        summary = NationwideSummary.from_dict(data.get("nationwide_summary", {}))

        regions = [
            RegionRecord.from_dict(r) if isinstance(r, dict) else r
            for r in data.get("regions", [])
        ]

        models = [
            PopularModelEntry.from_dict(m) if isinstance(m, dict) else m
            for m in data.get("popular_models_matrix", [])
        ]

        history = [
            HistoricalTrajectoryPoint.from_dict(h) if isinstance(h, dict) else h
            for h in data.get("historical_depletion_trajectory", [])
        ]

        return cls(
            metadata=metadata,
            alert_thresholds=alert_thresholds,
            nationwide_summary=summary,
            regions=regions,
            popular_models_matrix=models,
            historical_depletion_trajectory=history,
        )
