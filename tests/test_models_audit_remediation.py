"""Comprehensive audit and verification test suite for models/complaint.py and models/defect_report.py.

Verifies:
1. Data class definitions, serialization/deserialization methods (to_dict, to_admin_report_dict, from_dict).
2. Date parsing (ISO 8601, Korean formats YYYY년 MM월 DD일, 2-digit Korean years, dotted with trailing dots, compacted 8-digit and 6-digit, numeric epoch timestamps, calendar validation).
3. Field validation: severity levels (CRITICAL, HIGH, MEDIUM, LOW), category tags, sentiment score bounds [-1.0, 1.0].
4. Immutability, default factory handling, copy resilience.
"""

from __future__ import annotations

import copy
from datetime import date, datetime, timezone
import json
import math
import unittest
from typing import Any, Dict, List

from models.complaint import (
    CANONICAL_CATEGORIES,
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
    validate_category,
    validate_severity,
)
from models.defect_report import DefectReport


class TestModelDateParsingAudit(unittest.TestCase):
    """Exhaustive validation of parse_date_str across ISO 8601, Korean formats, dotted, compacted, and edge cases."""

    def test_iso_8601_variants(self) -> None:
        """Verify standard ISO 8601, T-separated, and timezone offset formats."""
        self.assertEqual(parse_date_str("2026-10-28"), "2026-10-28")
        self.assertEqual(parse_date_str("2026-10-28T14:30:00Z"), "2026-10-28")
        self.assertEqual(parse_date_str("2026-10-28T14:30:00.123456Z"), "2026-10-28")
        self.assertEqual(parse_date_str("2026-10-28T23:59:59+09:00"), "2026-10-28")
        self.assertEqual(parse_date_str("2026-10-28 14:30:00"), "2026-10-28")
        self.assertEqual(parse_date_str("2026-10-28 14:30:00.456"), "2026-10-28")

    def test_korean_date_formats(self) -> None:
        """Verify explicit Korean formats (YYYY년 MM월 DD일 and YY년 MM월 DD일) with optional spaces and day-of-week."""
        # 4-digit Korean year
        self.assertEqual(parse_date_str("2026년 10월 27일"), "2026-10-27")
        self.assertEqual(parse_date_str("2026년 9월 8일"), "2026-09-08")
        self.assertEqual(parse_date_str("2026년10월27일"), "2026-10-27")
        self.assertEqual(parse_date_str("2026년 10월 27일 (월)"), "2026-10-27")
        self.assertEqual(parse_date_str("2026년 10월 27일 15시 30분"), "2026-10-27")

        # 2-digit Korean year
        self.assertEqual(parse_date_str("26년 10월 27일"), "2026-10-27")
        self.assertEqual(parse_date_str("26년 9월 8일"), "2026-09-08")
        self.assertEqual(parse_date_str("26년 10월 27일 (화)"), "2026-10-27")

    def test_dotted_and_slashed_formats(self) -> None:
        """Verify dotted timestamps with trailing dots, spaces, slashes, and 2-digit year."""
        self.assertEqual(parse_date_str("2026.10.27"), "2026-10-27")
        self.assertEqual(parse_date_str("2026. 10. 27"), "2026-10-27")
        self.assertEqual(parse_date_str("2026. 10. 27."), "2026-10-27")
        self.assertEqual(parse_date_str("2026.10.27."), "2026-10-27")
        self.assertEqual(parse_date_str("26.10.25"), "2026-10-25")
        self.assertEqual(parse_date_str("26. 10. 25."), "2026-10-25")
        self.assertEqual(parse_date_str("2026/10/27"), "2026-10-27")
        self.assertEqual(parse_date_str("2026/09/08 12:00:00"), "2026-09-08")
        self.assertEqual(parse_date_str("26/10/25"), "2026-10-25")

    def test_month_day_only_format(self) -> None:
        """Verify MM.DD or MM-DD maps safely to current year."""
        current_year = datetime.now(timezone.utc).year
        self.assertEqual(parse_date_str("10.28"), f"{current_year}-10-28")
        self.assertEqual(parse_date_str("05-15"), f"{current_year}-05-15")
        self.assertEqual(parse_date_str("12/31"), f"{current_year}-12-31")

    def test_compact_numeric_dates(self) -> None:
        """Verify 8-digit and 6-digit compacted dates."""
        self.assertEqual(parse_date_str("20261028"), "2026-10-28")
        self.assertEqual(parse_date_str("20261028190123"), "2026-10-28")
        self.assertEqual(parse_date_str("261028"), "2026-10-28")

    def test_native_datetime_and_epoch_timestamps(self) -> None:
        """Verify datetime/date objects and numeric epoch timestamps."""
        d_obj = date(2026, 11, 4)
        dt_obj = datetime(2026, 11, 4, 18, 30, tzinfo=timezone.utc)
        self.assertEqual(parse_date_str(d_obj), "2026-11-04")
        self.assertEqual(parse_date_str(dt_obj), "2026-11-04")

        # 1730100000 is 2024-10-28 07:20:00 UTC
        self.assertEqual(parse_date_str(1730100000), "2024-10-28")
        # Millisecond timestamp
        self.assertEqual(parse_date_str(1730100000000), "2024-10-28")

    def test_calendar_validation_and_invalid_date_fallbacks(self) -> None:
        """Invalid calendar days (e.g. Feb 31, non-leap Feb 29) safely fall back to today."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.assertEqual(parse_date_str("2026-02-31"), today)
        self.assertEqual(parse_date_str("2026-02-29"), today)  # 2026 is not a leap year
        self.assertEqual(parse_date_str("2024-02-29"), "2024-02-29")  # 2024 is a leap year
        self.assertEqual(parse_date_str("2026-13-45"), today)
        self.assertEqual(parse_date_str("99999999"), today)
        self.assertEqual(parse_date_str("not-a-date"), today)
        self.assertEqual(parse_date_str(""), today)
        self.assertEqual(parse_date_str(None), today)
        self.assertEqual(parse_date_str("2026"), today)
        self.assertEqual(parse_date_str("2026-04"), today)


class TestModelFieldValidationAudit(unittest.TestCase):
    """Audits severity levels, category tags, and sentiment score bounds [-1.0, 1.0]."""

    def test_severity_levels_validation_and_normalization(self) -> None:
        """Verify VALID_SEVERITY_LEVELS, validate_severity, and normalize_severity."""
        self.assertEqual(VALID_SEVERITY_LEVELS, ["CRITICAL", "HIGH", "MEDIUM", "LOW"])

        # validate_severity
        self.assertTrue(validate_severity("CRITICAL"))
        self.assertTrue(validate_severity("high"))
        self.assertTrue(validate_severity("  MEDIUM  "))
        self.assertTrue(validate_severity("low\n"))
        self.assertFalse(validate_severity("UNKNOWN"))
        self.assertFalse(validate_severity(None))
        self.assertFalse(validate_severity(123))

        # normalize_severity from string
        self.assertEqual(normalize_severity("CRITICAL"), "CRITICAL")
        self.assertEqual(normalize_severity("high"), "HIGH")
        self.assertEqual(normalize_severity("WARNING"), "HIGH")
        self.assertEqual(normalize_severity("caution"), "MEDIUM")
        self.assertEqual(normalize_severity("INFO"), "LOW")

        # normalize_severity from severity_index
        self.assertEqual(normalize_severity(None, severity_index=8.5), "CRITICAL")
        self.assertEqual(normalize_severity(None, severity_index=6.5), "HIGH")
        self.assertEqual(normalize_severity(None, severity_index=4.5), "MEDIUM")
        self.assertEqual(normalize_severity(None, severity_index=2.0), "LOW")
        self.assertEqual(normalize_severity(None, severity_index=float("nan")), "LOW")

    def test_category_tags_validation_and_normalization(self) -> None:
        """Verify CANONICAL_CATEGORIES, validate_category, and normalize_category."""
        self.assertEqual(
            set(CANONICAL_CATEGORIES),
            {"BATTERY_CHARGING", "DRIVING_POWERTRAIN", "BUILD_QUALITY", "SOFTWARE_ELECTRONICS", "SERVICE_REPAIR_COST"},
        )
        self.assertTrue(validate_category("BATTERY_CHARGING"))
        self.assertTrue(validate_category("battery_charging"))
        self.assertTrue(validate_category("배터리/충전"))
        self.assertFalse(validate_category("INVALID_CAT"))
        self.assertFalse(validate_category(None))

        # normalize_category
        self.assertEqual(normalize_category("battery_charging"), "BATTERY_CHARGING")
        self.assertEqual(normalize_category("배터리/충전"), "BATTERY_CHARGING")
        self.assertEqual(normalize_category("OTA/소프트웨어/먹통"), "SOFTWARE_ELECTRONICS")
        self.assertEqual(normalize_category("unknown_category"), "BUILD_QUALITY")

    def test_sentiment_score_bounds_clamping(self) -> None:
        """Verify sentiment_polarity is strictly bounded [-1.0, 1.0] and negativity is [0.0, 1.0]."""
        # _safe_clamp
        self.assertEqual(_safe_clamp(-1.5, -1.0, 1.0), -1.0)
        self.assertEqual(_safe_clamp(2.5, -1.0, 1.0), 1.0)
        self.assertEqual(_safe_clamp(0.42, -1.0, 1.0), 0.42)
        self.assertEqual(_safe_clamp(float("nan"), -1.0, 1.0, default=0.0), 0.0)

        # ComplaintRecord __post_init__ clamping
        rec = ComplaintRecord(
            id="c1",
            source="dcinside",
            url="https://example.com/1",
            title="테스트",
            author="작성자",
            created_at="2026-10-28",
            vehicle_brand="Kia",
            vehicle_model="EV6",
            defect_category="BATTERY_CHARGING",
            summary="요약",
            verbatim_quote="인용문",
            sentiment_polarity=2.5,  # Exceeds max
            negativity_score=1.8,   # Exceeds max
        )
        self.assertEqual(rec.sentiment_polarity, 1.0)

        # to_dict & to_admin_report_dict enforce bounds
        d = rec.to_dict()
        self.assertAlmostEqual(d["sentiment_polarity"], 1.0)
        self.assertAlmostEqual(d["negativity_score"], 1.0)

        admin_d = rec.to_admin_report_dict()
        self.assertAlmostEqual(admin_d["sentiment_polarity"], 1.0)
        self.assertAlmostEqual(admin_d["sentiment_score"], 1.0)

        # from_dict clamping
        from_d = ComplaintRecord.from_dict({
            "id": "c2",
            "sentiment_polarity": -5.0,
            "negativity_score": 3.0,
        })
        self.assertEqual(from_d.sentiment_polarity, -1.0)
        self.assertEqual(from_d.negativity_score, 1.0)


class TestModelDataclassesAndSerializationAudit(unittest.TestCase):
    """Audits dataclass definitions, to_dict, to_admin_report_dict, and from_dict symmetry."""

    def test_raw_post_dictionary_protocol_and_serialization(self) -> None:
        """RawPost implements mapping protocol and serializes comments cleanly."""
        raw = RawPost(
            platform="dcinside",
            post_id="post-123",
            url="https://example.com/post-123",
            title="고장 문의",
            content="모터 경고등",
            comments=["댓글 1", "댓글 2"],
            created_at="2026-10-28",
            author="익명",
        )
        self.assertEqual(raw["platform"], "dcinside")
        self.assertEqual(raw.get("post_id"), "post-123")
        self.assertIn("title", raw)
        self.assertEqual(len(raw), 8)

        d = raw.to_dict()
        self.assertEqual(d["post_id"], "post-123")
        self.assertEqual(d["comments"], ["댓글 1", "댓글 2"])

        # from_dict
        restored = RawPost.from_dict(d)
        self.assertEqual(restored.post_id, raw.post_id)
        self.assertEqual(restored.comments, raw.comments)

    def test_dsi_breakdown_resilience(self) -> None:
        """DSIBreakdown safely handles NaN, Inf, None, and duck-typed objects."""
        dsi = DSIBreakdown(
            safety=float("nan"),
            functional=float("inf"),
            economic=None,  # type: ignore[arg-type]
            social=5.5555,
            convenience="bad_val",  # type: ignore[arg-type]
        )
        d = dsi.to_dict()
        self.assertEqual(d["safety"], 0.0)
        self.assertEqual(d["functional"], 0.0)
        self.assertEqual(d["economic"], 0.0)
        self.assertEqual(d["social"], 5.56)
        self.assertEqual(d["convenience"], 0.0)

        # Mapping protocol
        self.assertEqual(dsi["social"], 5.56)
        self.assertEqual(dsi["safety"], 0.0)

        # from_dict with object having .get()
        class CustomDictWrapper:
            def get(self, k: str, default: Any = 0.0) -> Any:
                return {"safety": 7.5, "functional": 8.0}.get(k, default)

        wrapped = DSIBreakdown.from_dict(CustomDictWrapper())
        self.assertIsNotNone(wrapped)
        self.assertEqual(wrapped.safety, 7.5)
        self.assertEqual(wrapped.functional, 8.0)

    def test_complaint_record_and_defect_report_roundtrip(self) -> None:
        """ComplaintRecord and DefectReport maintain exact roundtrip symmetry."""
        record = ComplaintRecord(
            id="c-roundtrip-1",
            source="bobaedream",
            url="https://example.com/c1",
            title="ICC-U 충전 불량",
            author="차주1",
            created_at="2026-10-28 14:30:00",
            vehicle_brand="Hyundai",
            vehicle_model="Ioniq 5",
            defect_category="BATTERY_CHARGING",
            summary="충전 안됨",
            verbatim_quote="ICCU 먹통입니다.",
            slang_terms_detected=["ICCU", "벽돌"],
            sentiment_polarity=-0.75,
            negativity_score=0.88,
            severity_index=8.2,
            is_authentic_defect=True,
            dsi_breakdown=DSIBreakdown(safety=8.0, functional=9.0, economic=7.0, social=6.0, convenience=8.0),
            severity="CRITICAL",
            confidence_score=0.95,
        )

        # DefectReport creation from ComplaintRecord
        report = DefectReport.from_complaint_record(record)
        self.assertEqual(report.id, record.id)
        self.assertEqual(report.canonical_severity, "CRITICAL")
        self.assertEqual(report.date_str, "2026-10-28")
        self.assertEqual(report.confidence_score, 0.95)

        # to_admin_report_dict
        admin_d = report.to_admin_report_dict()
        self.assertEqual(admin_d["target_vehicle"], "Hyundai Ioniq 5")
        self.assertEqual(admin_d["defect_category_ko"], "배터리/충전")
        self.assertEqual(admin_d["severity"], "CRITICAL")
        self.assertEqual(admin_d["date"], "2026-10-28")

        # from_dict reconstruction
        reconstructed = DefectReport.from_dict(admin_d)
        self.assertEqual(reconstructed.id, record.id)
        self.assertEqual(reconstructed.vehicle_brand, "Hyundai")
        self.assertEqual(reconstructed.vehicle_model, "Ioniq 5")
        self.assertEqual(reconstructed.defect_category, "BATTERY_CHARGING")
        self.assertEqual(reconstructed.canonical_severity, "CRITICAL")
        self.assertEqual(reconstructed.confidence_score, 0.95)

    def test_daily_report_payload_polymorphic_serialization(self) -> None:
        """DailyReportPayload.to_dict safely serializes ComplaintRecord/DefectReport objects in reports."""
        rec = ComplaintRecord(
            id="poly-1",
            source="dcinside",
            url="https://example.com/p1",
            title="소음 결함",
            author="익명",
            created_at="2026-10-28",
            vehicle_brand="Tesla",
            vehicle_model="Model Y",
            defect_category="DRIVING_POWERTRAIN",
            summary="모터 소음",
            verbatim_quote="가속 시 삐 소리",
        )
        payload = DailyReportPayload(
            generated_at="2026-10-28T00:00:00Z",
            reports=[rec],  # List of ComplaintRecord objects
            statistics=DailyReportStatistics(total_scraped=50, total_filtered_defects=1),
        )
        d = payload.to_dict()
        self.assertEqual(len(d["reports"]), 1)
        self.assertIsInstance(d["reports"][0], dict)
        self.assertEqual(d["reports"][0]["id"], "poly-1")

        # Must be cleanly JSON serializable with allow_nan=False
        serialized_json = json.dumps(d, allow_nan=False)
        self.assertIn('"id": "poly-1"', serialized_json)


class TestModelImmutabilityAndCopyResilience(unittest.TestCase):
    """Audits default factory independence, copy isolation, and absence of shared mutable state."""

    def test_slang_terms_detected_default_factory_independence(self) -> None:
        """slang_terms_detected is an independent list for every ComplaintRecord instance."""
        r1 = ComplaintRecord(
            id="c-def-1", source="s", url="", title="", author="", created_at="",
            vehicle_brand="Kia", vehicle_model="EV6", defect_category="BUILD_QUALITY",
            summary="", verbatim_quote="",
        )
        r2 = ComplaintRecord(
            id="c-def-2", source="s", url="", title="", author="", created_at="",
            vehicle_brand="Kia", vehicle_model="EV6", defect_category="BUILD_QUALITY",
            summary="", verbatim_quote="",
        )
        r1.slang_terms_detected.append("독립검증1")
        self.assertIn("독립검증1", r1.slang_terms_detected)
        self.assertNotIn("독립검증1", r2.slang_terms_detected)

    def test_null_slang_terms_detected_defensive_initialization(self) -> None:
        """Passing None for slang_terms_detected converts to a fresh empty list."""
        rec = ComplaintRecord(
            id="c-null", source="s", url="", title="", author="", created_at="",
            vehicle_brand="Kia", vehicle_model="EV6", defect_category="BUILD_QUALITY",
            summary="", verbatim_quote="",
            slang_terms_detected=None,  # type: ignore[arg-type]
        )
        self.assertEqual(rec.slang_terms_detected, [])
        rec.slang_terms_detected.append("추가")
        self.assertEqual(rec.slang_terms_detected, ["추가"])

    def test_copy_resilience_and_isolation(self) -> None:
        """copy.deepcopy and to_dict produce isolated structures without cross-mutation."""
        orig = ComplaintRecord(
            id="c-orig", source="s", url="", title="", author="", created_at="",
            vehicle_brand="Tesla", vehicle_model="Model 3", defect_category="SOFTWARE_ELECTRONICS",
            summary="", verbatim_quote="",
            slang_terms_detected=["벽돌"],
            dsi_breakdown=DSIBreakdown(safety=5.0, functional=5.0),
        )
        cloned = copy.deepcopy(orig)
        cloned.slang_terms_detected.append("먹통")
        cloned.dsi_breakdown.safety = 10.0

        self.assertEqual(orig.slang_terms_detected, ["벽돌"])
        self.assertEqual(orig.dsi_breakdown.safety, 5.0)
        self.assertEqual(cloned.slang_terms_detected, ["벽돌", "먹통"])
        self.assertEqual(cloned.dsi_breakdown.safety, 10.0)


if __name__ == "__main__":
    unittest.main()
