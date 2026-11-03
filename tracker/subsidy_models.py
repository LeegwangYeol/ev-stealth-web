"""Strongly typed models for EV Subsidy Depletion Tracking and Analytics.

This module provides data models matching the EV Subsidy Depletion JSON Schema
specifying regional quotas, depletion rates, 5-tier alert thresholds, and
popular vehicle price/subsidy matrices.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import math
from typing import Any, Dict, List, Optional, Union


def _safe_int(val: Any, default: int = 0) -> int:
    """Safely convert value to int, catching None, NaN, Inf, ValueError, TypeError, and OverflowError."""
    if val is None:
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return int(f)
    except (ValueError, TypeError, OverflowError):
        return default


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert value to float, catching None, NaN, Inf, ValueError, TypeError, and OverflowError."""
    if val is None:
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (ValueError, TypeError, OverflowError):
        return default


def _mapping_getitem(obj: Any, key: Any) -> Any:
    """Safely retrieve key value for Mapping protocol without exposing private methods."""
    if isinstance(key, str) and not key.startswith("_"):
        # 1. Direct attribute access (non-callable)
        if hasattr(obj, key):
            val = getattr(obj, key)
            if not callable(val):
                return val
        # 2. Known model-specific aliases
        aliases = getattr(obj, "_ALIASES", None)
        if aliases and key in aliases:
            target = aliases[key]
            if hasattr(obj, target):
                val = getattr(obj, target)
                if not callable(val):
                    return val
        # 3. Delegation for SubsidyPayload -> metadata fields
        if hasattr(obj, "metadata") and obj.metadata is not None:
            meta = obj.metadata
            if hasattr(meta, key) and not key.startswith("_"):
                val = getattr(meta, key)
                if not callable(val):
                    return val
            elif hasattr(meta, "__getitem__"):
                try:
                    return meta[key]
                except (KeyError, TypeError):
                    pass
    d = obj.to_dict()
    if key in d:
        return d[key]
    raise KeyError(key)


def _mapping_contains(obj: Any, key: Any) -> bool:
    """Check key containment for Mapping protocol without exposing private methods."""
    if isinstance(key, str) and not key.startswith("_"):
        if hasattr(obj, key):
            val = getattr(obj, key)
            if not callable(val):
                return True
        aliases = getattr(obj, "_ALIASES", None)
        if aliases and key in aliases:
            target = aliases[key]
            if hasattr(obj, target):
                val = getattr(obj, target)
                if not callable(val):
                    return True
        if hasattr(obj, "metadata") and obj.metadata is not None:
            meta = obj.metadata
            if hasattr(meta, key) and not key.startswith("_") and not callable(getattr(meta, key)):
                return True
            if hasattr(meta, "__contains__") and key in meta:
                return True
    return key in obj.to_dict()


class AlertSeverity(str, Enum):
    """5-tier alert severity levels for EV subsidy depletion."""

    HEALTHY = "HEALTHY"
    CAUTION = "CAUTION"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    DEPLETED = "DEPLETED"

    @classmethod
    def from_rate(cls, rate: Any) -> AlertSeverity:
        """Determine alert severity tier based on depletion percentage."""
        r = _safe_float(rate, default=0.0)
        if r >= 100.0:
            return cls.DEPLETED
        elif r >= 95.0:
            return cls.CRITICAL
        elif r >= 80.0:
            return cls.WARNING
        elif r >= 60.0:
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

    def __getitem__(self, key: Any) -> Any:
        return _mapping_getitem(self, key)

    def __contains__(self, key: Any) -> bool:
        return _mapping_contains(self, key)

    def get(self, key: Any, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return self.to_dict().keys()

    def values(self):
        return self.to_dict().values()

    def items(self):
        return self.to_dict().items()

    def __iter__(self):
        return iter(self.to_dict())

    def __len__(self) -> int:
        return len(self.to_dict())

    @classmethod
    def from_dict(cls, data: Any) -> AlertThresholdConfig:
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            data = {}
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

    _ALIASES = {
        "announced": "announced_units",
        "applied": "applied_units",
        "delivered": "delivered_units",
        "remaining": "remaining_units",
        "rate": "depletion_rate",
        "local_subsidy": "max_local_subsidy_krw",
        "max_local_subsidy": "max_local_subsidy_krw",
        "total_subsidy": "max_total_subsidy_krw",
        "max_total_subsidy": "max_total_subsidy_krw",
        "total_budget": "total_budget_krw",
        "remaining_budget": "remaining_budget_krw",
    }

    def __getitem__(self, key: Any) -> Any:
        return _mapping_getitem(self, key)

    def __contains__(self, key: Any) -> bool:
        return _mapping_contains(self, key)

    def get(self, key: Any, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return self.to_dict().keys()

    def values(self):
        return self.to_dict().values()

    def items(self):
        return self.to_dict().items()

    def __iter__(self):
        return iter(self.to_dict())

    def __len__(self) -> int:
        return len(self.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Any) -> CategoryMetrics:
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            data = {}
        return cls(
            announced_units=max(0, _safe_int(data.get("announced_units", data.get("announced", 0)))),
            applied_units=max(0, _safe_int(data.get("applied_units", data.get("applied", 0)))),
            delivered_units=max(0, _safe_int(data.get("delivered_units", data.get("delivered", 0)))),
            remaining_units=max(0, _safe_int(data.get("remaining_units", data.get("remaining", 0)))),
            depletion_rate=max(0.0, _safe_float(data.get("depletion_rate", data.get("rate", 0.0)))),
            delivery_rate=max(0.0, _safe_float(data.get("delivery_rate", 0.0))),
            status=str(data.get("status") or "HEALTHY"),
            max_local_subsidy_krw=max(0, _safe_int(data.get("max_local_subsidy_krw", data.get("local_subsidy_krw", 0)))),
            max_total_subsidy_krw=max(0, _safe_int(data.get("max_total_subsidy_krw", data.get("total_subsidy_krw", 0)))),
            total_budget_krw=max(0, _safe_int(data.get("total_budget_krw", data.get("total_budget", 0)))),
            remaining_budget_krw=max(0, _safe_int(data.get("remaining_budget_krw", data.get("remaining_budget", 0)))),
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
    muni_id: str = ""
    name_en: str = ""
    category: str = "passenger"
    delivered_units: Optional[int] = 0
    total_subsidy_krw: int = 0

    _ALIASES = {
        "id": "muni_id",
        "code": "muni_id",
        "name": "name_ko",
        "announced": "announced_units",
        "applied": "applied_units",
        "remaining": "remaining_units",
        "delivered": "delivered_units",
        "rate": "depletion_rate",
        "local_subsidy": "local_subsidy_krw",
        "total_subsidy": "total_subsidy_krw",
    }

    def __getitem__(self, key: Any) -> Any:
        return _mapping_getitem(self, key)

    def __contains__(self, key: Any) -> bool:
        return _mapping_contains(self, key)

    def get(self, key: Any, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return self.to_dict().keys()

    def values(self):
        return self.to_dict().values()

    def items(self):
        return self.to_dict().items()

    def __iter__(self):
        return iter(self.to_dict())

    def __len__(self) -> int:
        return len(self.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Any) -> MunicipalityMetrics:
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            data = {}
        return cls(
            name_ko=str(data.get("name_ko") or data.get("name") or ""),
            announced_units=max(0, _safe_int(data.get("announced_units", data.get("announced", 0)))),
            applied_units=max(0, _safe_int(data.get("applied_units", data.get("applied", 0)))),
            remaining_units=max(0, _safe_int(data.get("remaining_units", data.get("remaining", 0)))),
            depletion_rate=max(0.0, _safe_float(data.get("depletion_rate", data.get("rate", 0.0)))),
            status=str(data.get("status") or "HEALTHY"),
            local_subsidy_krw=max(0, _safe_int(data.get("local_subsidy_krw", data.get("local_subsidy", 0)))),
            muni_id=str(data.get("muni_id") or data.get("id") or data.get("code") or ""),
            name_en=str(data.get("name_en") or ""),
            category=str(data.get("category") or "passenger"),
            delivered_units=max(0, _safe_int(data.get("delivered_units", data.get("delivered", 0)))),
            total_subsidy_krw=max(0, _safe_int(data.get("total_subsidy_krw", data.get("total_subsidy", 0)))),
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
    last_updated: str = ""
    code: Optional[str] = None

    _ALIASES = {
        "id": "region_id",
        "name": "name_ko",
        "region_name": "name_ko",
        "depletion_rate": "overall_depletion_rate",
        "status": "overall_status",
        "residency_days": "residency_requirement_days",
    }

    def __post_init__(self):
        if self.code and not self.iso_code:
            self.iso_code = self.code
        if self.code and not self.region_id:
            self.region_id = self.code
        if self.iso_code and not self.region_id:
            self.region_id = self.iso_code
        if self.region_id and not self.iso_code:
            self.iso_code = self.region_id
        if (self.region_id or self.iso_code) and not self.code:
            self.code = self.region_id or self.iso_code
        if self.categories is None:
            self.categories = {}
        if self.municipalities is None:
            self.municipalities = []

    def __getitem__(self, key: Any) -> Any:
        return _mapping_getitem(self, key)

    def __contains__(self, key: Any) -> bool:
        return _mapping_contains(self, key)

    def get(self, key: Any, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return self.to_dict().keys()

    def values(self):
        return self.to_dict().values()

    def items(self):
        return self.to_dict().items()

    def __iter__(self):
        return iter(self.to_dict())

    def __len__(self) -> int:
        return len(self.to_dict())

    def get_category(self, category_name: str = "passenger") -> Optional[CategoryMetrics]:
        """Safely retrieve category metrics (e.g. passenger, commercial, bus)."""
        if not self.categories or not isinstance(self.categories, dict):
            return None
        return self.categories.get(category_name)

    def get_remaining_units(self, category_name: str = "passenger") -> int:
        """Safely get remaining quota units for category, defaulting to 0."""
        cat = self.get_category(category_name)
        if cat is None:
            return 0
        if isinstance(cat, dict):
            return max(0, _safe_int(cat.get("remaining_units", 0)))
        return max(0, _safe_int(getattr(cat, "remaining_units", 0)))

    def get_depletion_rate(self, category_name: str = "passenger") -> float:
        """Safely get depletion rate for category, falling back to overall_depletion_rate."""
        cat = self.get_category(category_name)
        if cat is None:
            return self.overall_depletion_rate
        if isinstance(cat, dict):
            return max(0.0, _safe_float(cat.get("depletion_rate", self.overall_depletion_rate)))
        return max(0.0, _safe_float(getattr(cat, "depletion_rate", self.overall_depletion_rate)))

    def get_local_subsidy(self, category_name: str = "passenger") -> int:
        """Safely get max local subsidy KRW for category."""
        cat = self.get_category(category_name)
        if cat is None:
            return 0
        if isinstance(cat, dict):
            return max(0, _safe_int(cat.get("max_local_subsidy_krw", cat.get("local_subsidy_krw", 0))))
        return max(0, _safe_int(getattr(cat, "max_local_subsidy_krw", getattr(cat, "local_subsidy_krw", 0))))

    def get_total_subsidy(self, category_name: str = "passenger") -> int:
        """Safely get max total subsidy KRW for category."""
        cat = self.get_category(category_name)
        if cat is None:
            return 0
        if isinstance(cat, dict):
            return max(0, _safe_int(cat.get("max_total_subsidy_krw", cat.get("total_subsidy_krw", 0))))
        return max(0, _safe_int(getattr(cat, "max_total_subsidy_krw", getattr(cat, "total_subsidy_krw", 0))))

    def get_municipality(self, muni_name_or_id: str) -> Optional[MunicipalityMetrics]:
        """Safely lookup lower-tier municipality by ID or name (Korean/English)."""
        if not self.municipalities or not isinstance(self.municipalities, (list, tuple)):
            return None
        target = str(muni_name_or_id).strip().lower()
        for m in self.municipalities:
            if isinstance(m, dict):
                m_id = str(m.get("muni_id", "")).strip().lower()
                m_ko = str(m.get("name_ko", "")).strip().lower()
                m_en = str(m.get("name_en", "")).strip().lower()
                if target in (m_id, m_ko, m_en):
                    return MunicipalityMetrics.from_dict(m)
            elif hasattr(m, "muni_id"):
                if target in (
                    str(m.muni_id).strip().lower(),
                    str(m.name_ko).strip().lower(),
                    str(m.name_en).strip().lower(),
                ):
                    return m
        return None

    def is_critical(self) -> bool:
        """Return True if overall status is CRITICAL or DEPLETED (depletion >= 95%)."""
        return str(self.overall_status).strip().upper() in ("CRITICAL", "DEPLETED") or self.overall_depletion_rate >= 95.0

    def is_warning(self) -> bool:
        """Return True if overall status is WARNING (depletion 80% to 94.9%)."""
        return str(self.overall_status).strip().upper() == "WARNING" or (80.0 <= self.overall_depletion_rate < 95.0)

    def is_depleted(self) -> bool:
        """Return True if overall status is DEPLETED or depletion >= 100%."""
        return str(self.overall_status).strip().upper() == "DEPLETED" or self.overall_depletion_rate >= 100.0

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "region_id": self.region_id,
            "iso_code": self.iso_code,
            "code": self.code or self.region_id or self.iso_code,
            "name_ko": self.name_ko,
            "name_en": self.name_en,
            "tier": self.tier,
            "overall_depletion_rate": self.overall_depletion_rate,
            "overall_status": self.overall_status,
            "residency_requirement_days": self.residency_requirement_days,
            "supplementary_budget_added": self.supplementary_budget_added,
            "categories": {k: v.to_dict() if hasattr(v, "to_dict") else v for k, v in (self.categories or {}).items()},
            "notes": self.notes,
            "last_updated": self.last_updated,
        }
        if self.municipalities:
            result["municipalities"] = [m.to_dict() if hasattr(m, "to_dict") else m for m in self.municipalities]
        return result

    @classmethod
    def from_dict(cls, data: Any) -> RegionRecord:
        if isinstance(data, cls):
            return data
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
        elif isinstance(cats_raw, (list, tuple)):
            for cat_data in cats_raw:
                if isinstance(cat_data, dict):
                    c_name = str(cat_data.get("category", "") or cat_data.get("name", "")).strip().lower()
                    if c_name:
                        cats[c_name] = CategoryMetrics.from_dict(cat_data)

        munis = []
        munis_raw = data.get("municipalities") or []
        if isinstance(munis_raw, (list, tuple)):
            for muni_data in munis_raw:
                if isinstance(muni_data, MunicipalityMetrics):
                    munis.append(muni_data)
                elif isinstance(muni_data, dict):
                    munis.append(MunicipalityMetrics.from_dict(muni_data))

        code_val = str(data.get("code") or data.get("region_id") or data.get("id") or "")
        return cls(
            region_id=str(data.get("region_id") or data.get("code") or data.get("id") or ""),
            iso_code=str(data.get("iso_code") or data.get("code") or data.get("region_id") or ""),
            name_ko=str(data.get("name_ko") or data.get("name") or data.get("region_name") or ""),
            name_en=str(data.get("name_en") or ""),
            tier=str(data.get("tier") or "province"),
            overall_depletion_rate=max(0.0, _safe_float(data.get("overall_depletion_rate", data.get("depletion_rate", 0.0)))),
            overall_status=str(data.get("overall_status") or data.get("status") or "HEALTHY"),
            residency_requirement_days=max(0, _safe_int(data.get("residency_requirement_days", data.get("residency_days", 30)), default=30)),
            supplementary_budget_added=bool(data.get("supplementary_budget_added", False)),
            categories=cats,
            municipalities=munis,
            notes=str(data.get("notes") or ""),
            last_updated=str(data.get("last_updated") or ""),
            code=code_val or None,
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

    _ALIASES = {
        "id": "model_id",
        "name": "name_ko",
        "model_name": "name_ko",
        "brand": "manufacturer",
        "maker": "manufacturer",
        "price": "base_price_krw",
        "base_price": "base_price_krw",
        "national_subsidy": "national_subsidy_krw",
        "subsidy": "national_subsidy_krw",
        "capacity": "battery_capacity_kwh",
        "capacity_kwh": "battery_capacity_kwh",
        "range": "rated_range_km",
        "range_km": "rated_range_km",
        "samples": "regional_subsidy_samples",
    }

    def __getitem__(self, key: Any) -> Any:
        return _mapping_getitem(self, key)

    def __contains__(self, key: Any) -> bool:
        return _mapping_contains(self, key)

    def get(self, key: Any, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return self.to_dict().keys()

    def values(self):
        return self.to_dict().values()

    def items(self):
        return self.to_dict().items()

    def __iter__(self):
        return iter(self.to_dict())

    def __len__(self) -> int:
        return len(self.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def get_regional_subsidy(self, region_code: str, subsidy_type: str = "local_subsidy_krw") -> int:
        """Safely retrieve local subsidy for a region code, handling missing or malformed samples."""
        if not self.regional_subsidy_samples or not isinstance(self.regional_subsidy_samples, dict):
            return 0
        entry = self.regional_subsidy_samples.get(region_code)
        if entry is None:
            code_upper = str(region_code).strip().upper()
            for k, v in self.regional_subsidy_samples.items():
                if str(k).strip().upper() == code_upper:
                    entry = v
                    break
        if entry is None:
            return 0
        if isinstance(entry, (int, float)):
            return max(0, _safe_int(entry, 0))
        if isinstance(entry, dict):
            val = entry.get(subsidy_type, entry.get("local_subsidy_krw", entry.get("subsidy_krw", 0)))
            return max(0, _safe_int(val, 0))
        return 0

    def calculate_total_subsidy(self, region_code: str) -> int:
        """Calculate total national + local subsidy for this vehicle model in a given region."""
        return max(0, self.national_subsidy_krw) + self.get_regional_subsidy(region_code)

    def calculate_final_price(self, region_code: str) -> int:
        """Calculate final out-of-pocket price after total subsidies."""
        return max(0, self.base_price_krw - self.calculate_total_subsidy(region_code))

    def get_subsidy(self, region_code: str) -> int:
        """Alias for calculate_total_subsidy."""
        return self.calculate_total_subsidy(region_code)

    @classmethod
    def from_dict(cls, data: Any) -> PopularModelEntry:
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            data = {}
        reg_samples = data.get("regional_subsidy_samples")
        if not isinstance(reg_samples, dict):
            reg_samples = {}
        return cls(
            model_id=str(data.get("model_id") or data.get("id") or ""),
            name_ko=str(data.get("name_ko") or data.get("name") or data.get("model_name") or ""),
            manufacturer=str(data.get("manufacturer") or data.get("brand") or data.get("maker") or ""),
            battery_type=str(data.get("battery_type") or ""),
            battery_capacity_kwh=max(0.0, _safe_float(data.get("battery_capacity_kwh", data.get("capacity_kwh", 0.0)))),
            rated_range_km=max(0, _safe_int(data.get("rated_range_km", data.get("range_km", 0)))),
            base_price_krw=max(0, _safe_int(data.get("base_price_krw", data.get("price_krw", data.get("price", 0))))),
            price_subsidy_ratio=max(0.0, min(1.0, _safe_float(data.get("price_subsidy_ratio", 1.0), default=1.0))),
            national_subsidy_krw=max(0, _safe_int(data.get("national_subsidy_krw", data.get("national_subsidy", 0)))),
            regional_subsidy_samples=reg_samples,
        )


@dataclass
class HistoricalTrajectoryPoint:
    """Monthly historical progress record of subsidy depletion."""

    date: str
    passenger_rate: float
    commercial_rate: float
    overall_rate: float

    def __getitem__(self, key: Any) -> Any:
        return _mapping_getitem(self, key)

    def __contains__(self, key: Any) -> bool:
        return _mapping_contains(self, key)

    def get(self, key: Any, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return self.to_dict().keys()

    def values(self):
        return self.to_dict().values()

    def items(self):
        return self.to_dict().items()

    def __iter__(self):
        return iter(self.to_dict())

    def __len__(self) -> int:
        return len(self.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Any) -> HistoricalTrajectoryPoint:
        if isinstance(data, cls):
            return data
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

    _ALIASES = {
        "announced": "total_announced_units",
        "announced_units": "total_announced_units",
        "total_announced": "total_announced_units",
        "applied": "total_applied_units",
        "applied_units": "total_applied_units",
        "total_applied": "total_applied_units",
        "delivered": "total_delivered_units",
        "delivered_units": "total_delivered_units",
        "total_delivered": "total_delivered_units",
        "remaining": "total_remaining_units",
        "remaining_units": "total_remaining_units",
        "total_remaining": "total_remaining_units",
        "depletion_rate": "nationwide_depletion_rate",
        "rate": "nationwide_depletion_rate",
        "total_budget": "total_budget_billion_krw",
        "disbursed_budget": "disbursed_budget_billion_krw",
    }

    def __getitem__(self, key: Any) -> Any:
        return _mapping_getitem(self, key)

    def __contains__(self, key: Any) -> bool:
        return _mapping_contains(self, key)

    def get(self, key: Any, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return self.to_dict().keys()

    def values(self):
        return self.to_dict().values()

    def items(self):
        return self.to_dict().items()

    def __iter__(self):
        return iter(self.to_dict())

    def __len__(self) -> int:
        return len(self.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_announced_units": self.total_announced_units,
            "total_applied_units": self.total_applied_units,
            "total_delivered_units": self.total_delivered_units,
            "total_remaining_units": self.total_remaining_units,
            "nationwide_depletion_rate": self.nationwide_depletion_rate,
            "total_budget_billion_krw": self.total_budget_billion_krw,
            "disbursed_budget_billion_krw": self.disbursed_budget_billion_krw,
            "total_budget_krw": self.total_budget_krw,
            "disbursed_budget_krw": self.disbursed_budget_krw,
            "category_totals": {
                k: v.to_dict() if hasattr(v, "to_dict") else v
                for k, v in self.category_totals.items()
            },
            "alert_region_counts": self.alert_region_counts,
        }

    @property
    def disbursed_budget_krw(self) -> int:
        """Disbursed statutory budget in KRW (non-negative)."""
        val = self.disbursed_budget_billion_krw
        if val is None:
            return 0
        try:
            f = float(val)
            if math.isnan(f) or math.isinf(f):
                return 0
            return max(0, int(round(f * 1_000_000_000)))
        except (ValueError, TypeError, OverflowError):
            return 0

    @property
    def total_budget_krw(self) -> int:
        """Total statutory budget in KRW (non-negative)."""
        val = self.total_budget_billion_krw
        if val is None:
            return 0
        try:
            f = float(val)
            if math.isnan(f) or math.isinf(f):
                return 0
            return max(0, int(round(f * 1_000_000_000)))
        except (ValueError, TypeError, OverflowError):
            return 0

    @classmethod
    def from_dict(cls, data: Any) -> NationwideSummary:
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            data = {}
        cat_totals = {}
        cat_totals_raw = data.get("category_totals")
        if not isinstance(cat_totals_raw, dict):
            cat_totals_raw = {}
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
            total_announced_units=max(0, _safe_int(data.get("total_announced_units", data.get("announced", 0)))),
            total_applied_units=max(0, _safe_int(data.get("total_applied_units", data.get("applied", 0)))),
            total_delivered_units=max(0, _safe_int(data.get("total_delivered_units", data.get("delivered", 0)))),
            total_remaining_units=max(0, _safe_int(data.get("total_remaining_units", data.get("remaining", 0)))),
            nationwide_depletion_rate=max(0.0, _safe_float(data.get("nationwide_depletion_rate", data.get("depletion_rate", 0.0)))),
            total_budget_billion_krw=max(0.0, _safe_float(data.get("total_budget_billion_krw", data.get("total_budget", 0.0)))),
            disbursed_budget_billion_krw=max(0.0, _safe_float(data.get("disbursed_budget_billion_krw", data.get("disbursed_budget", 0.0)))),
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

    def __getitem__(self, key: Any) -> Any:
        return _mapping_getitem(self, key)

    def __contains__(self, key: Any) -> bool:
        return _mapping_contains(self, key)

    def get(self, key: Any, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return self.to_dict().keys()

    def values(self):
        return self.to_dict().values()

    def items(self):
        return self.to_dict().items()

    def __iter__(self):
        return iter(self.to_dict())

    def __len__(self) -> int:
        return len(self.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Any) -> SubsidyMetadata:
        if isinstance(data, cls):
            return data
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

    _ALIASES = {
        "summary": "nationwide_summary",
        "models": "popular_models_matrix",
        "popular_models": "popular_models_matrix",
        "vehicles": "popular_models_matrix",
        "trajectory": "historical_depletion_trajectory",
        "history": "historical_depletion_trajectory",
        "thresholds": "alert_thresholds",
    }

    def __getitem__(self, key: Any) -> Any:
        return _mapping_getitem(self, key)

    def __contains__(self, key: Any) -> bool:
        return _mapping_contains(self, key)

    def get(self, key: Any, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return self.to_dict().keys()

    def values(self):
        return self.to_dict().values()

    def items(self):
        return self.to_dict().items()

    def __iter__(self):
        return iter(self.to_dict())

    def __len__(self) -> int:
        return len(self.to_dict())

    def get_region(self, region_id_or_name: str) -> Optional[RegionRecord]:
        """Find region by region_id, iso_code, code, or Korean/English name."""
        if not self.regions or not isinstance(self.regions, (list, tuple)):
            return None
        target = str(region_id_or_name).strip().lower()
        for r in self.regions:
            if isinstance(r, dict):
                r_id = str(r.get("region_id", "") or r.get("code", "")).strip().lower()
                r_iso = str(r.get("iso_code", "")).strip().lower()
                r_ko = str(r.get("name_ko", "")).strip().lower()
                r_en = str(r.get("name_en", "")).strip().lower()
                if target in (r_id, r_iso, r_ko, r_en):
                    return RegionRecord.from_dict(r)
            elif hasattr(r, "region_id"):
                if target in (
                    str(r.region_id).strip().lower(),
                    str(r.iso_code).strip().lower(),
                    str(getattr(r, "code", "") or "").strip().lower(),
                    str(r.name_ko).strip().lower(),
                    str(r.name_en).strip().lower(),
                ):
                    return r
        return None

    def get_model(self, model_id_or_name: str) -> Optional[PopularModelEntry]:
        """Find popular vehicle model by model_id or Korean name."""
        if not self.popular_models_matrix or not isinstance(self.popular_models_matrix, (list, tuple)):
            return None
        target = str(model_id_or_name).strip().lower()
        for m in self.popular_models_matrix:
            if isinstance(m, dict):
                m_id = str(m.get("model_id", "") or m.get("id", "")).strip().lower()
                m_ko = str(m.get("name_ko", "") or m.get("name", "")).strip().lower()
                if target in (m_id, m_ko):
                    return PopularModelEntry.from_dict(m)
            elif hasattr(m, "model_id"):
                if target in (
                    str(m.model_id).strip().lower(),
                    str(m.name_ko).strip().lower(),
                ):
                    return m
        return None

    def get_vehicle(self, model_id_or_name: str) -> Optional[PopularModelEntry]:
        """Alias for get_model."""
        return self.get_model(model_id_or_name)

    def get_critical_regions(self) -> List[RegionRecord]:
        """Return list of regions categorized as CRITICAL or DEPLETED (depletion rate >= 95%)."""
        if not self.regions or not isinstance(self.regions, (list, tuple)):
            return []
        res = []
        for r in self.regions:
            st = str(r.get("overall_status", "") if hasattr(r, "get") else getattr(r, "overall_status", "")).strip().upper()
            rate = _safe_float(r.get("overall_depletion_rate", 0.0) if hasattr(r, "get") else getattr(r, "overall_depletion_rate", 0.0))
            if st in ("CRITICAL", "DEPLETED") or rate >= 95.0:
                res.append(r if isinstance(r, RegionRecord) else RegionRecord.from_dict(r))
        return res

    def get_warning_regions(self) -> List[RegionRecord]:
        """Return list of regions categorized as WARNING (depletion rate 80% to 94.9%)."""
        if not self.regions or not isinstance(self.regions, (list, tuple)):
            return []
        res = []
        for r in self.regions:
            st = str(r.get("overall_status", "") if hasattr(r, "get") else getattr(r, "overall_status", "")).strip().upper()
            rate = _safe_float(r.get("overall_depletion_rate", 0.0) if hasattr(r, "get") else getattr(r, "overall_depletion_rate", 0.0))
            if st == "WARNING" or (80.0 <= rate < 95.0):
                res.append(r if isinstance(r, RegionRecord) else RegionRecord.from_dict(r))
        return res

    def get_healthy_regions(self) -> List[RegionRecord]:
        """Return list of regions categorized as HEALTHY or CAUTION (depletion rate < 80%)."""
        if not self.regions or not isinstance(self.regions, (list, tuple)):
            return []
        res = []
        for r in self.regions:
            st = str(r.get("overall_status", "") if hasattr(r, "get") else getattr(r, "overall_status", "")).strip().upper()
            rate = _safe_float(r.get("overall_depletion_rate", 0.0) if hasattr(r, "get") else getattr(r, "overall_depletion_rate", 0.0))
            if st not in ("CRITICAL", "DEPLETED", "WARNING") and rate < 80.0:
                res.append(r if isinstance(r, RegionRecord) else RegionRecord.from_dict(r))
        return res

    def total_regions(self) -> int:
        """Total count of regions in this payload."""
        return len(self.regions) if isinstance(self.regions, (list, tuple)) else 0

    def total_models(self) -> int:
        """Total count of popular vehicle models in this payload."""
        return len(self.popular_models_matrix) if isinstance(self.popular_models_matrix, (list, tuple)) else 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict() if hasattr(self.metadata, "to_dict") else self.metadata,
            "alert_thresholds": {
                k: v.to_dict() if hasattr(v, "to_dict") else v
                for k, v in self.alert_thresholds.items()
            },
            "nationwide_summary": (
                self.nationwide_summary.to_dict()
                if hasattr(self.nationwide_summary, "to_dict")
                else self.nationwide_summary
            ),
            "regions": [r.to_dict() if hasattr(r, "to_dict") else r for r in self.regions],
            "popular_models_matrix": [
                m.to_dict() if hasattr(m, "to_dict") else m for m in self.popular_models_matrix
            ],
            "historical_depletion_trajectory": [
                h.to_dict() if hasattr(h, "to_dict") else h
                for h in self.historical_depletion_trajectory
            ],
        }

    @classmethod
    def from_json(cls, json_str_or_bytes: Union[str, bytes]) -> SubsidyPayload:
        """Parse SubsidyPayload directly from a JSON string or bytes."""
        import json
        data = json.loads(json_str_or_bytes)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Any) -> SubsidyPayload:
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            data = {}
        meta_dict = data.get("metadata")
        if isinstance(meta_dict, SubsidyMetadata):
            metadata = meta_dict
        else:
            metadata = SubsidyMetadata.from_dict(meta_dict if isinstance(meta_dict, dict) else {})

        alert_thresholds = {}
        at_dict = data.get("alert_thresholds") or data.get("thresholds") or {}
        if isinstance(at_dict, dict):
            for k, v in at_dict.items():
                if isinstance(v, AlertThresholdConfig):
                    alert_thresholds[k] = v
                elif isinstance(v, dict):
                    alert_thresholds[k] = AlertThresholdConfig.from_dict(v)

        ns_dict = data.get("nationwide_summary") or data.get("summary")
        if isinstance(ns_dict, NationwideSummary):
            summary = ns_dict
        else:
            summary = NationwideSummary.from_dict(ns_dict if isinstance(ns_dict, dict) else {})

        regions_raw = data.get("regions") or data.get("regional_subsidies") or []
        if not isinstance(regions_raw, (list, tuple)):
            regions_raw = []
        regions = [
            RegionRecord.from_dict(r) if isinstance(r, dict) else r
            for r in regions_raw
            if isinstance(r, (dict, RegionRecord))
        ]

        models_raw = data.get("popular_models_matrix") or data.get("vehicles") or data.get("popular_models") or data.get("models") or []
        if not isinstance(models_raw, (list, tuple)):
            models_raw = []
        models = [
            PopularModelEntry.from_dict(m) if isinstance(m, dict) else m
            for m in models_raw
            if isinstance(m, (dict, PopularModelEntry))
        ]

        history_raw = data.get("historical_depletion_trajectory") or data.get("trajectory") or data.get("history") or []
        if not isinstance(history_raw, (list, tuple)):
            history_raw = []
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


# =============================================================================
# Domain Interoperability Aliases
# =============================================================================
RegionSubsidy = RegionRecord
VehicleSubsidy = PopularModelEntry
SubsidySnapshot = SubsidyPayload

__all__ = [
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
    # Aliases
    "RegionSubsidy",
    "VehicleSubsidy",
    "SubsidySnapshot",
]
