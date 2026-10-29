"""Data models for raw scraped posts, classified complaints, and daily report JSON schemas.

Authoritative source:
- /Users/a7890/src/my-e-car/.agents/orchestrator_daily_monitor/PROJECT.md § Interface Contracts
- /Users/a7890/src/my-e-car/.agents/spec_miner_nlp_workflow/specifications.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
import re
from typing import Any, Dict, List, Optional


DEFECT_CATEGORY_KO_MAP: Dict[str, str] = {
    "BATTERY_CHARGING": "배터리/충전",
    "DRIVING_POWERTRAIN": "주행/모터/등판",
    "BUILD_QUALITY": "단차/누수/마감",
    "SOFTWARE_ELECTRONICS": "OTA/소프트웨어/먹통",
    "SERVICE_REPAIR_COST": "AS/수리비",
}

CANONICAL_CATEGORIES = list(DEFECT_CATEGORY_KO_MAP.keys())

VALID_BRANDS = ["Hyundai", "Kia", "Tesla", "BYD", "Other"]


def _safe_round(val: Any, decimals: int = 4, default: float = 0.0) -> float:
    """Safely round numeric value, catching None, NaN, Inf, and non-numeric inputs."""
    if val is None:
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return round(f, decimals)
    except (ValueError, TypeError, OverflowError):
        return default


def _safe_int(val: Any, default: int = 0) -> int:
    """Safely convert value to int, catching None, NaN, Inf, and non-numeric inputs."""
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
    """Safely convert value to float, catching None, NaN, Inf, and non-numeric inputs."""
    if val is None:
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (ValueError, TypeError, OverflowError):
        return default



@dataclass(init=False)
class RawPost:
    """Raw post extracted by scraper modules."""
    platform: str
    post_id: str
    url: str
    title: str
    content: str
    comments: List[str] = field(default_factory=list)
    created_at: str = ""
    author: str = ""

    def __init__(
        self,
        platform: str = "",
        post_id: str = "",
        url: str = "",
        title: str = "",
        content: str = "",
        comments: Optional[List[Any]] = None,
        created_at: str = "",
        author: str = "",
        id: Optional[str] = None,
        source: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self.platform = str(source or platform or "unknown")
        self.post_id = str(id if id is not None else (post_id if post_id is not None else ""))
        self.url = str(url or "")
        self.title = str(title or "")
        self.content = str(content or "")
        self.comments = (
            [str(c) for c in comments if c is not None]
            if isinstance(comments, (list, tuple, set))
            else []
        )
        self.created_at = str(created_at or "")
        self.author = str(author or "")

    @property
    def id(self) -> str:
        return self.post_id

    @property
    def source(self) -> str:
        return self.platform

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform,
            "post_id": self.post_id,
            "url": self.url,
            "title": self.title,
            "content": self.content,
            "comments": list(self.comments),
            "created_at": self.created_at,
            "author": self.author,
        }

    def __getitem__(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError:
            d = self.to_dict()
            if key in d:
                return d[key]
            raise KeyError(key) from None

    def __contains__(self, key: Any) -> bool:
        return hasattr(self, str(key)) or key in self.to_dict()

    def get(self, key: str, default: Any = None) -> Any:
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

    @classmethod
    def from_dict(cls, data: Any) -> RawPost:
        if isinstance(data, cls):
            return data
        def _get(k: str, default: Any = "") -> Any:
            if isinstance(data, dict):
                return data.get(k, default)
            return getattr(data, k, default)
        raw_comments = _get("comments")
        comments = (
            [str(c) for c in raw_comments if c is not None]
            if isinstance(raw_comments, (list, tuple, set))
            else []
        )
        pid = _get("post_id", None)
        if pid is None or (isinstance(pid, str) and not pid.strip()):
            pid = _get("id", None)
        post_id = str(pid) if pid is not None else ""

        return cls(
            platform=str(_get("source") or _get("platform") or "unknown"),
            post_id=post_id,
            url=str(_get("url") or ""),
            title=str(_get("title") or ""),
            content=str(_get("content") or ""),
            comments=comments,
            created_at=str(_get("created_at") or _get("created_at=") or ""),
            author=str(_get("author") or ""),
        )


@dataclass
class DSIBreakdown:
    """5-dimensional breakdown of Defect Severity Index."""
    safety: float = 0.0
    functional: float = 0.0
    economic: float = 0.0
    social: float = 0.0
    convenience: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "safety": _safe_round(self.safety, 2),
            "functional": _safe_round(self.functional, 2),
            "economic": _safe_round(self.economic, 2),
            "social": _safe_round(self.social, 2),
            "convenience": _safe_round(self.convenience, 2),
        }

    def __getitem__(self, key: str) -> float:
        try:
            val = getattr(self, key)
            if isinstance(val, (int, float)):
                return float(val)
        except AttributeError:
            pass
        d = self.to_dict()
        if key in d:
            return d[key]
        raise KeyError(key) from None

    def __contains__(self, key: Any) -> bool:
        return hasattr(self, str(key)) or key in self.to_dict()

    def get(self, key: str, default: Any = None) -> Any:
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

    @classmethod
    def from_dict(cls, data: Any) -> Optional[DSIBreakdown]:
        """Convert dict or DSIBreakdown instance safely into a DSIBreakdown object."""
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            return None
        return cls(
            safety=_safe_float(data.get("safety", 0.0)),
            functional=_safe_float(data.get("functional", 0.0)),
            economic=_safe_float(data.get("economic", 0.0)),
            social=_safe_float(data.get("social", 0.0)),
            convenience=_safe_float(data.get("convenience", 0.0)),
        )


@dataclass
class ComplaintRecord:
    """Classified & filtered defect complaint record."""
    id: str
    source: str
    url: str
    title: str
    author: str
    created_at: str
    vehicle_brand: str
    vehicle_model: str
    defect_category: str
    summary: str
    verbatim_quote: str
    slang_terms_detected: List[str] = field(default_factory=list)
    sentiment_polarity: float = 0.0
    negativity_score: float = 0.0
    severity_index: float = 0.0
    is_authentic_defect: bool = True
    dsi_breakdown: Optional[DSIBreakdown] = None
    filter_reason: str = ""
    severity: Optional[str] = None

    @property
    def defect_category_ko(self) -> str:
        return DEFECT_CATEGORY_KO_MAP.get(self.defect_category, "기타 결함")

    @property
    def severity_tier(self) -> str:
        """Map DSI score to 4 severity tiers or return explicit severity."""
        if self.severity:
            return str(self.severity).strip().upper()
        if self.severity_index is None:
            return "LOW"
        try:
            val = float(self.severity_index)
            if math.isnan(val) or math.isinf(val):
                return "LOW"
        except (ValueError, TypeError, OverflowError):
            return "LOW"

        if val >= 8.0:
            return "CRITICAL"
        if val >= 6.0:
            return "HIGH"
        if val >= 4.0:
            return "MEDIUM"
        return "LOW"

    @property
    def sentiment_tier(self) -> str:
        """Map continuous polarity [-1.0, 1.0] to 4 tiers."""
        if self.sentiment_polarity is None:
            return "NEUTRAL"
        try:
            val = float(self.sentiment_polarity)
            if math.isnan(val) or math.isinf(val):
                return "NEUTRAL"
        except (ValueError, TypeError, OverflowError):
            return "NEUTRAL"

        if val >= 0.30:
            return "POSITIVE"
        if val >= -0.29:
            return "NEUTRAL"
        if val >= -0.69:
            return "NEGATIVE"
        return "STRONGLY_NEGATIVE"

    @property
    def date_str(self) -> str:
        """Extract YYYY-MM-DD from created_at or default to today."""
        if self.created_at:
            s = str(self.created_at).strip()
            # 1. Handle Korean explicit date format e.g. "2026년 10월 27일" or "2026년 9월 8일"
            match_kr = re.search(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일?", s)
            if match_kr:
                y, m, d = match_kr.group(1), match_kr.group(2).zfill(2), match_kr.group(3).zfill(2)
                return f"{y}-{m}-{d}"

            # 2. Handle timestamps with space, sub-second microseconds, or standard ISO formats
            # e.g. "2026-10-28 19:01:23.495311", "2026-10-28 19:01", "2026. 10. 25 14:30:00"
            match_ts = re.search(
                r"(\d{4})\s*[./\-]\s*(\d{1,2})\s*[./\-]\s*(\d{1,2})(?:[\sT]+\d{1,2}:\d{1,2}(?::\d{1,2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?(?:[^\d]|$)",
                s,
            )
            if match_ts:
                y, m, d = match_ts.group(1), match_ts.group(2).zfill(2), match_ts.group(3).zfill(2)
                if 1 <= int(m) <= 12 and 1 <= int(d) <= 31:
                    return f"{y}-{m}-{d}"

            # 3. Handle 8-digit compact dates e.g. "20261028" or "20261028190123"
            match_compact = re.search(
                r"(?:^|[^\d])((?:19|20)\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?:\d{4,6})?(?:$|[^\d])",
                s,
            )
            if match_compact:
                y, m, d = match_compact.group(1), match_compact.group(2), match_compact.group(3)
                return f"{y}-{m}-{d}"

            # 4. Handle Korean 2-digit year patterns e.g. "26.10.25" or "26-10-25"
            match_2 = re.search(r"(?:^|[^\d])(\d{2})\s*[./\-]\s*(\d{1,2})\s*[./\-]\s*(\d{1,2})", s)
            if match_2:
                yy, m, d = int(match_2.group(1)), match_2.group(2).zfill(2), match_2.group(3).zfill(2)
                if 1 <= int(m) <= 12 and 1 <= int(d) <= 31:
                    y = f"20{yy:02d}" if yy < 70 else f"19{yy:02d}"
                    return f"{y}-{m}-{d}"

            # 5. Normalization fallback
            norm_date = s.replace("/", "-").replace(".", "-")
            if len(norm_date) >= 10 and norm_date[4] == "-" and norm_date[7] == "-":
                try:
                    y_str, m_str, d_str = norm_date[:4], norm_date[5:7], norm_date[8:10]
                    if 1 <= int(m_str) <= 12 and 1 <= int(d_str) <= 31:
                        return f"{y_str}-{m_str}-{d_str}"
                except (ValueError, TypeError):
                    pass
            try:
                dt = datetime.fromisoformat(norm_date.replace("Z", "+00:00"))
                return dt.strftime("%Y-%m-%d")
            except Exception:
                pass
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def to_dict(self) -> Dict[str, Any]:
        """Format matching PROJECT.md § Interface Contract 1 (Scraper ↔ Filter)."""
        return {
            "id": self.id,
            "source": self.source,
            "url": self.url,
            "title": self.title,
            "author": self.author,
            "created_at": self.created_at,
            "vehicle_brand": self.vehicle_brand,
            "vehicle_model": self.vehicle_model,
            "defect_category": self.defect_category,
            "summary": self.summary,
            "verbatim_quote": self.verbatim_quote,
            "slang_terms_detected": list(self.slang_terms_detected or []),
            "sentiment_polarity": _safe_round(self.sentiment_polarity, 4),
            "negativity_score": _safe_round(self.negativity_score, 4),
            "severity_index": _safe_round(self.severity_index, 2),
            "is_authentic_defect": self.is_authentic_defect,
        }

    def to_admin_report_dict(self) -> Dict[str, Any]:
        """Format matching PROJECT.md § Interface Contract 2 (Admin Page & daily_reports.json)."""
        res = {
            "id": self.id,
            "source": self.source,
            "platform": self.source,
            "url": self.url,
            "post_url": self.url,
            "title": self.title,
            "post_title": self.title,
            "author": self.author,
            "date": self.date_str,
            "created_at": self.created_at,
            "vehicle_brand": self.vehicle_brand,
            "vehicle_model": self.vehicle_model,
            "target_vehicle": f"{self.vehicle_brand} {self.vehicle_model}".strip(),
            "defect_category": self.defect_category,
            "defect_category_ko": self.defect_category_ko,
            "summary": self.summary,
            "verbatim_quote": self.verbatim_quote,
            "raw_quote": self.verbatim_quote,
            "slang_tags": list(self.slang_terms_detected or []),
            "slang_terms_detected": list(self.slang_terms_detected or []),
            "sentiment_score": _safe_round(self.negativity_score, 4),
            "sentiment_polarity": _safe_round(self.sentiment_polarity, 4),
            "negativity_score": _safe_round(self.negativity_score, 4),
            "sentiment_tier": self.sentiment_tier,
            "severity": self.severity_tier,
            "severity_index": _safe_round(self.severity_index, 2),
            "is_authentic_defect": self.is_authentic_defect,
        }
        if self.dsi_breakdown:
            res["dsi_breakdown"] = self.dsi_breakdown.to_dict()
        return res

    @classmethod
    def from_dict(cls, data: Any) -> ComplaintRecord:
        """Construct ComplaintRecord from dict or ComplaintRecord instance with aliases and fallbacks."""
        if isinstance(data, cls):
            return data
        if not isinstance(data, (dict, object)) or data is None:
            data = {}

        def _get(key: str, default: Any = None) -> Any:
            if isinstance(data, dict):
                return data.get(key, default)
            return getattr(data, key, default)

        def _get_str(*keys: str, default: str = "") -> str:
            for k in keys:
                val = _get(k)
                if val is not None and str(val).strip() != "":
                    return str(val).strip()
            for k in keys:
                val = _get(k)
                if val is not None:
                    return str(val)
            return default

        # 1. post_id / id
        rec_id = _get_str("id", "post_id")

        # 2. source / platform
        source = _get_str("source", "platform", default="unknown")

        # 3. url / post_url
        url = _get_str("url", "post_url")

        # 4. title / post_title
        title = _get_str("title", "post_title")

        # 5. author
        author = _get_str("author")

        # 6. created_at (support date alias)
        created_at = _get_str("created_at", "date")

        # 7. vehicle_brand & vehicle_model with target_vehicle fallback
        brand = _get_str("vehicle_brand")
        model = _get_str("vehicle_model")
        target_veh = _get_str("target_vehicle")
        if (not brand or not model) and target_veh:
            brand_map = {
                "mercedes-benz": "Mercedes-Benz",
                "mercedes": "Mercedes-Benz",
                "benz": "Mercedes-Benz",
                "hyundai": "Hyundai",
                "현대": "Hyundai",
                "kia": "Kia",
                "기아": "Kia",
                "tesla": "Tesla",
                "테슬라": "Tesla",
                "byd": "BYD",
                "비야디": "BYD",
                "genesis": "Genesis",
                "제네시스": "Genesis",
                "porsche": "Porsche",
                "포르쉐": "Porsche",
                "bmw": "BMW",
                "audi": "Audi",
                "아우디": "Audi",
                "chevrolet": "Chevrolet",
                "쉐보레": "Chevrolet",
                "polestar": "Polestar",
                "폴스타": "Polestar",
                "volvo": "Volvo",
                "볼보": "Volvo",
                "volkswagen": "Volkswagen",
                "폭스바겐": "Volkswagen",
                "rivian": "Rivian",
                "리비안": "Rivian",
                "lucid": "Lucid",
                "루시드": "Lucid",
                "other": "Other",
                "기타": "Other",
            }
            model_brand_map = {
                "ioniq": "Hyundai",
                "아이오닉": "Hyundai",
                "casper": "Hyundai",
                "캐스퍼": "Hyundai",
                "porter": "Hyundai",
                "포터": "Hyundai",
                "ev3": "Kia",
                "ev4": "Kia",
                "ev5": "Kia",
                "ev6": "Kia",
                "ev9": "Kia",
                "niro": "Kia",
                "니로": "Kia",
                "bongo": "Kia",
                "봉고": "Kia",
                "ray": "Kia",
                "레이": "Kia",
                "model 3": "Tesla",
                "model y": "Tesla",
                "model s": "Tesla",
                "model x": "Tesla",
                "cybertruck": "Tesla",
                "t4k": "BYD",
                "atto": "BYD",
                "seal": "BYD",
                "dolphin": "BYD",
                "gv60": "Genesis",
                "gv70": "Genesis",
                "g80": "Genesis",
                "taycan": "Porsche",
                "타이칸": "Porsche",
            }
            parsed_brand = ""
            parsed_model = ""
            tv_lower = target_veh.lower()
            for b_key, b_val in brand_map.items():
                if tv_lower == b_key:
                    parsed_brand = b_val
                    parsed_model = ""
                    break
                elif tv_lower.startswith(b_key + " "):
                    parsed_brand = b_val
                    parsed_model = target_veh[len(b_key):].strip()
                    break

            if not parsed_brand:
                for m_key, m_b in model_brand_map.items():
                    if tv_lower == m_key or tv_lower.startswith(m_key + " ") or tv_lower.startswith(m_key):
                        parsed_brand = m_b
                        parsed_model = target_veh
                        break

            if not parsed_brand:
                parts = target_veh.split(None, 1)
                if len(parts) == 2:
                    parsed_brand = parts[0]
                    parsed_model = parts[1]
                else:
                    parsed_brand = "Other"
                    parsed_model = parts[0]

            if not brand and parsed_brand:
                brand = parsed_brand
            if not model and parsed_model:
                model = parsed_model

        # 8. defect_category (support category or Korean category alias)
        defect_cat = _get_str("defect_category", "category")
        if not defect_cat:
            cat_ko = _get_str("defect_category_ko")
            if cat_ko:
                for k, v in DEFECT_CATEGORY_KO_MAP.items():
                    if v == cat_ko:
                        defect_cat = k
                        break

        # 9. summary
        summary = _get_str("summary")

        # 10. verbatim_quote / raw_quote
        verbatim_quote = _get_str("verbatim_quote", "raw_quote")

        # 11. slang_terms_detected / slang_tags
        raw_slang = _get("slang_terms_detected")
        if raw_slang is None:
            raw_slang = _get("slang_tags")
        if raw_slang is None:
            raw_slang = _get("slang_terms")
        slang_terms: List[str] = (
            [str(s) for s in raw_slang if s is not None]
            if isinstance(raw_slang, (list, tuple, set))
            else []
        )

        # 12. sentiment_polarity
        polarity = _safe_float(_get("sentiment_polarity"), 0.0)

        # 13. negativity_score / sentiment_score
        raw_neg = _get("negativity_score")
        if raw_neg is None:
            raw_neg = _get("sentiment_score")
        negativity = _safe_float(raw_neg, 0.0)

        # 14. severity_index
        sev_idx = _safe_float(_get("severity_index"), 0.0)

        # 15. is_authentic_defect
        raw_auth = _get("is_authentic_defect")
        is_auth = bool(raw_auth) if raw_auth is not None else True

        # 16. dsi_breakdown: convert from dict or pass through DSIBreakdown instance
        raw_dsi = _get("dsi_breakdown")
        if isinstance(raw_dsi, DSIBreakdown):
            dsi = raw_dsi
        elif isinstance(raw_dsi, dict):
            dsi = DSIBreakdown.from_dict(raw_dsi)
        else:
            dsi = None

        # 17. filter_reason
        filter_reason = _get_str("filter_reason")

        # 18. severity (support severity_tier alias)
        raw_sev = _get("severity")
        if raw_sev is None:
            raw_sev = _get("severity_tier")
        severity = str(raw_sev).strip() if raw_sev is not None else None

        return cls(
            id=rec_id,
            source=source,
            url=url,
            title=title,
            author=author,
            created_at=created_at,
            vehicle_brand=brand,
            vehicle_model=model,
            defect_category=defect_cat,
            summary=summary,
            verbatim_quote=verbatim_quote,
            slang_terms_detected=slang_terms,
            sentiment_polarity=polarity,
            negativity_score=negativity,
            severity_index=sev_idx,
            is_authentic_defect=is_auth,
            dsi_breakdown=dsi,
            filter_reason=filter_reason,
            severity=severity,
        )

    def __getitem__(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError:
            d = self.to_admin_report_dict()
            if key in d:
                return d[key]
            raise KeyError(key) from None

    def __contains__(self, key: Any) -> bool:
        return hasattr(self, str(key)) or key in self.to_admin_report_dict()

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return self.to_admin_report_dict().keys()

    def values(self):
        return self.to_admin_report_dict().values()

    def items(self):
        return self.to_admin_report_dict().items()

    def __iter__(self):
        return iter(self.to_admin_report_dict())


@dataclass
class DailyReportStatistics:
    """Summary statistics for daily report payload."""
    total_scraped: int = 0
    total_filtered_defects: int = 0
    avg_negativity_score: float = 0.0
    critical_defect_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_scraped": self.total_scraped,
            "total_filtered_defects": self.total_filtered_defects,
            "avg_negativity_score": _safe_round(self.avg_negativity_score, 2),
            "critical_defect_count": self.critical_defect_count,
        }

    def __getitem__(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError:
            d = self.to_dict()
            if key in d:
                return d[key]
            raise KeyError(key) from None

    def __contains__(self, key: Any) -> bool:
        return hasattr(self, str(key)) or key in self.to_dict()

    def get(self, key: str, default: Any = None) -> Any:
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

    @classmethod
    def from_dict(cls, data: Any) -> DailyReportStatistics:
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            return cls()
        return cls(
            total_scraped=max(0, _safe_int(data.get("total_scraped", 0))),
            total_filtered_defects=max(0, _safe_int(data.get("total_filtered_defects", 0))),
            avg_negativity_score=_safe_float(data.get("avg_negativity_score", 0.0)),
            critical_defect_count=max(0, _safe_int(data.get("critical_defect_count", 0))),
        )


@dataclass
class DailyReportPayload:
    """Complete container for outputting daily_reports.json."""
    generated_at: str
    pipeline_version: str = "1.0.0"
    statistics: DailyReportStatistics = field(default_factory=DailyReportStatistics)
    reports: List[Dict[str, Any]] = field(default_factory=list)
    total_complaints_today: int = 0
    top_defect_categories: List[Dict[str, Any]] = field(default_factory=list)

    def __getitem__(self, key: str) -> Any:
        d = self.to_dict()
        if key not in d:
            raise KeyError(key)
        return d[key]

    def __contains__(self, key: Any) -> bool:
        return key in self.to_dict()

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)

    def keys(self):
        return self.to_dict().keys()

    def values(self):
        return self.to_dict().values()

    def items(self):
        return self.to_dict().items()

    def __iter__(self):
        return iter(self.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "pipeline_version": self.pipeline_version,
            "statistics": self.statistics.to_dict(),
            "total_complaints_today": self.total_complaints_today,
            "top_defect_categories": list(self.top_defect_categories),
            "reports": list(self.reports),
        }

    @classmethod
    def from_dict(cls, data: Any) -> DailyReportPayload:
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            return cls(generated_at=datetime.now(timezone.utc).isoformat())

        gen_at = str(data.get("generated_at") or datetime.now(timezone.utc).isoformat())
        pipe_ver = str(data.get("pipeline_version") or "1.0.0")

        raw_stats = data.get("statistics")
        if isinstance(raw_stats, DailyReportStatistics):
            stats = raw_stats
        elif isinstance(raw_stats, dict):
            stats = DailyReportStatistics.from_dict(raw_stats)
        else:
            stats = DailyReportStatistics()

        raw_reports = data.get("reports")
        reports = [r for r in raw_reports if isinstance(r, dict)] if isinstance(raw_reports, (list, tuple)) else []

        raw_cats = data.get("top_defect_categories")
        top_cats = [c for c in raw_cats if isinstance(c, dict)] if isinstance(raw_cats, (list, tuple)) else []

        tot_complaints = _safe_int(data.get("total_complaints_today", len(reports)))

        return cls(
            generated_at=gen_at,
            pipeline_version=pipe_ver,
            statistics=stats,
            reports=reports,
            total_complaints_today=tot_complaints,
            top_defect_categories=top_cats,
        )
