"""Data models for raw scraped posts, classified complaints, and daily report JSON schemas.

Authoritative source:
- /Users/a7890/src/my-e-car/.agents/orchestrator_daily_monitor/PROJECT.md § Interface Contracts
- /Users/a7890/src/my-e-car/.agents/spec_miner_nlp_workflow/specifications.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
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


@dataclass
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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RawPost:
        return cls(
            platform=str(data.get("platform", "unknown")),
            post_id=str(data.get("post_id", "")),
            url=str(data.get("url", "")),
            title=str(data.get("title", "")),
            content=str(data.get("content", "")),
            comments=list(data.get("comments", [])),
            created_at=str(data.get("created_at", "")),
            author=str(data.get("author", "")),
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
            "safety": round(self.safety, 2),
            "functional": round(self.functional, 2),
            "economic": round(self.economic, 2),
            "social": round(self.social, 2),
            "convenience": round(self.convenience, 2),
        }


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

    @property
    def defect_category_ko(self) -> str:
        return DEFECT_CATEGORY_KO_MAP.get(self.defect_category, "기타 결함")

    @property
    def severity_tier(self) -> str:
        """Map DSI score to 4 severity tiers."""
        if self.severity_index >= 8.0:
            return "CRITICAL"
        if self.severity_index >= 6.0:
            return "HIGH"
        if self.severity_index >= 4.0:
            return "MEDIUM"
        return "LOW"

    @property
    def sentiment_tier(self) -> str:
        """Map continuous polarity [-1.0, 1.0] to 4 tiers."""
        if self.sentiment_polarity >= 0.30:
            return "POSITIVE"
        if self.sentiment_polarity >= -0.29:
            return "NEUTRAL"
        if self.sentiment_polarity >= -0.69:
            return "NEGATIVE"
        return "STRONGLY_NEGATIVE"

    @property
    def date_str(self) -> str:
        """Extract YYYY-MM-DD from created_at or default to today."""
        if self.created_at:
            if len(self.created_at) >= 10 and self.created_at[4] == "-" and self.created_at[7] == "-":
                return self.created_at[:10]
            try:
                dt = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
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
            "slang_terms_detected": list(self.slang_terms_detected),
            "sentiment_polarity": round(self.sentiment_polarity, 4),
            "negativity_score": round(self.negativity_score, 4),
            "severity_index": round(self.severity_index, 2),
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
            "slang_tags": list(self.slang_terms_detected),
            "slang_terms_detected": list(self.slang_terms_detected),
            "sentiment_score": round(self.negativity_score, 4),
            "sentiment_polarity": round(self.sentiment_polarity, 4),
            "negativity_score": round(self.negativity_score, 4),
            "sentiment_tier": self.sentiment_tier,
            "severity": self.severity_tier,
            "severity_index": round(self.severity_index, 2),
            "is_authentic_defect": self.is_authentic_defect,
        }
        if self.dsi_breakdown:
            res["dsi_breakdown"] = self.dsi_breakdown.to_dict()
        return res


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
            "avg_negativity_score": round(self.avg_negativity_score, 2),
            "critical_defect_count": self.critical_defect_count,
        }


@dataclass
class DailyReportPayload:
    """Complete container for outputting daily_reports.json."""
    generated_at: str
    pipeline_version: str = "1.0.0"
    statistics: DailyReportStatistics = field(default_factory=DailyReportStatistics)
    reports: List[Dict[str, Any]] = field(default_factory=list)
    total_complaints_today: int = 0
    top_defect_categories: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "pipeline_version": self.pipeline_version,
            "statistics": self.statistics.to_dict(),
            "total_complaints_today": self.total_complaints_today,
            "top_defect_categories": list(self.top_defect_categories),
            "reports": list(self.reports),
        }
