"""Defect Report Data Models and Serialization Schema.

Provides high-integrity data models for raw scraped posts, classified defect reports,
and daily structured JSON report synchronization.

Authoritative source:
- /Users/a7890/src/my-e-car/.agents/orchestrator_daily_monitor/PROJECT.md § Interface Contracts
- /Users/a7890/src/my-e-car/.agents/spec_miner_nlp_workflow/specifications.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
import re
from typing import Any, Dict, List, Optional, Union

from models.complaint import (
    CANONICAL_CATEGORIES,
    CATEGORY_ALIASES,
    DEFECT_CATEGORY_KO_MAP,
    VALID_BRANDS,
    VALID_SEVERITY_LEVELS,
    ComplaintRecord,
    DSIBreakdown,
    DailyReportPayload,
    DailyReportStatistics,
    RawPost,
    _safe_clamp,
    _safe_float,
    _safe_int,
    _safe_round,
    normalize_category,
    normalize_severity,
    parse_date_str,
    quarantine_entry,
    sanitize_string,
    validate_category,
    validate_report_entry,
    validate_severity,
)


@dataclass
class DefectReport(ComplaintRecord):
    """Primary Defect Report data record for verified community defect complaints."""

    @property
    def date_str(self) -> str:
        """Extract YYYY-MM-DD from created_at or default to today UTC."""
        return parse_date_str(self.created_at)

    @classmethod
    def from_dict(
        cls,
        data: Any,
        strict: bool = False,
        quarantine: bool = False,
    ) -> DefectReport:
        """Construct DefectReport from dict, ComplaintRecord, or other object with fallbacks."""
        rec = ComplaintRecord.from_dict(data, strict=strict, quarantine=quarantine)
        return cls(
            id=rec.id,
            source=rec.source,
            url=rec.url,
            title=rec.title,
            author=rec.author,
            created_at=rec.created_at,
            vehicle_brand=rec.vehicle_brand,
            vehicle_model=rec.vehicle_model,
            defect_category=rec.defect_category,
            summary=rec.summary,
            verbatim_quote=rec.verbatim_quote,
            slang_terms_detected=list(rec.slang_terms_detected or []),
            sentiment_polarity=rec.sentiment_polarity,
            negativity_score=rec.negativity_score,
            severity_index=rec.severity_index,
            is_authentic_defect=rec.is_authentic_defect,
            dsi_breakdown=DSIBreakdown.from_dict(rec.dsi_breakdown) if rec.dsi_breakdown else None,
            filter_reason=rec.filter_reason,
            severity=rec.severity,
            confidence_score=rec.confidence_score,
        )

    @classmethod
    def from_complaint_record(cls, record: ComplaintRecord) -> DefectReport:
        """Create DefectReport instance directly from ComplaintRecord."""
        return cls.from_dict(record)

    @classmethod
    def from_json(cls, json_str: Union[str, bytes], **kwargs: Any) -> DefectReport:
        """Safely parse JSON string into DefectReport with strict/quarantine options."""
        return cls.from_dict(json_str, **kwargs)


__all__ = [
    "DefectReport",
    "parse_date_str",
    "ComplaintRecord",
    "DSIBreakdown",
    "DailyReportStatistics",
    "DailyReportPayload",
    "RawPost",
    "CANONICAL_CATEGORIES",
    "CATEGORY_ALIASES",
    "DEFECT_CATEGORY_KO_MAP",
    "VALID_BRANDS",
    "VALID_SEVERITY_LEVELS",
    "validate_severity",
    "normalize_severity",
    "validate_category",
    "normalize_category",
    "validate_report_entry",
    "quarantine_entry",
    "sanitize_string",
]
