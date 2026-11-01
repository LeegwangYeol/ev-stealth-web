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
    DEFECT_CATEGORY_KO_MAP,
    VALID_BRANDS,
    ComplaintRecord,
    DSIBreakdown,
    DailyReportPayload,
    DailyReportStatistics,
    RawPost,
    _safe_float,
    _safe_int,
    _safe_round,
)


def parse_date_str(created_at: Any) -> str:
    """Extract YYYY-MM-DD from created_at or default safely to today (UTC).

    Guarantees calendar validity and never raises uncaught exceptions.
    """
    today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if created_at is None:
        return today_iso
    s = str(created_at).strip()
    if not s:
        return today_iso

    current_year = datetime.now(timezone.utc).year

    def _validate_date(year: int, month: int, day: int) -> Optional[str]:
        try:
            if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                dt = datetime(year, month, day)
                return dt.strftime("%Y-%m-%d")
        except (ValueError, OverflowError):
            pass
        return None

    # 1. Handle Korean explicit date format e.g. "2026년 10월 27일" or "2026년 9월 8일"
    match_kr = re.search(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일?", s)
    if match_kr:
        v = _validate_date(int(match_kr.group(1)), int(match_kr.group(2)), int(match_kr.group(3)))
        if v:
            return v

    # 2. Handle timestamps with space, sub-second microseconds, or standard ISO formats
    match_ts = re.search(
        r"(\d{4})\s*[./\-]\s*(\d{1,2})\s*[./\-]\s*(\d{1,2})(?:[\sT]+\d{1,2}:\d{1,2}(?::\d{1,2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?(?:[^\d]|$)",
        s,
    )
    if match_ts:
        v = _validate_date(int(match_ts.group(1)), int(match_ts.group(2)), int(match_ts.group(3)))
        if v:
            return v

    # 3. Handle 8-digit compact dates e.g. "20261028" or "20261028190123"
    match_compact = re.search(
        r"(?:^|[^\d])((?:19|20)\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?:\d{4,6})?(?:$|[^\d])",
        s,
    )
    if match_compact:
        v = _validate_date(int(match_compact.group(1)), int(match_compact.group(2)), int(match_compact.group(3)))
        if v:
            return v

    # 4. Handle Korean 2-digit year patterns e.g. "26.10.25" or "26-10-25"
    match_2 = re.search(r"(?:^|[^\d])(\d{2})\s*[./\-]\s*(\d{1,2})\s*[./\-]\s*(\d{1,2})", s)
    if match_2:
        yy = int(match_2.group(1))
        y = 2000 + yy if yy < 70 else 1900 + yy
        v = _validate_date(y, int(match_2.group(2)), int(match_2.group(3)))
        if v:
            return v

    # 5. Handle month-day only format e.g. "10.28" or "10-28" (DCInside current-year posts)
    match_md = re.search(r"^(0[1-9]|1[0-2])[./\-](0[1-9]|[12]\d|3[01])$", s)
    if match_md:
        v = _validate_date(current_year, int(match_md.group(1)), int(match_md.group(2)))
        if v:
            return v

    # 6. Normalization fallback
    norm_date = s.replace("/", "-").replace(".", "-")
    if len(norm_date) >= 10 and norm_date[4] == "-" and norm_date[7] == "-":
        try:
            y_val, m_val, d_val = int(norm_date[:4]), int(norm_date[5:7]), int(norm_date[8:10])
            v = _validate_date(y_val, m_val, d_val)
            if v:
                return v
        except (ValueError, TypeError):
            pass
    try:
        dt = datetime.fromisoformat(norm_date.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass

    return today_iso


@dataclass
class DefectReport(ComplaintRecord):
    """Primary Defect Report data record for verified community defect complaints."""

    @property
    def date_str(self) -> str:
        """Extract YYYY-MM-DD from created_at or default to today UTC."""
        return parse_date_str(self.created_at)

    @classmethod
    def from_dict(cls, data: Any) -> DefectReport:
        """Construct DefectReport from dict, ComplaintRecord, or other object with fallbacks."""
        rec = ComplaintRecord.from_dict(data)
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
            dsi_breakdown=rec.dsi_breakdown,
            filter_reason=rec.filter_reason,
            severity=rec.severity,
        )

    @classmethod
    def from_complaint_record(cls, record: ComplaintRecord) -> DefectReport:
        """Create DefectReport instance directly from ComplaintRecord."""
        return cls.from_dict(record)
