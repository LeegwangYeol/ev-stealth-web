"""Tests for ComplaintRecord.from_dict and ComplaintRecord.date_str enhancements (Sync21).

Verifies:
1. Symmetric ComplaintRecord.from_dict classmethod:
   - Pass-through when data is already ComplaintRecord.
   - Key aliases:
     - source / platform
     - post_id / id
     - url / post_url
     - title / post_title
     - verbatim_quote / raw_quote
     - slang_terms_detected / slang_tags
     - negativity_score / sentiment_score
     - dsi_breakdown from dict or DSIBreakdown instance
     - fallback vehicle_brand and vehicle_model if target_vehicle is provided.
2. Robust ComplaintRecord.date_str parsing:
   - Timestamps with space (e.g. YYYY-MM-DD HH:MM).
   - Sub-second microsecond timestamps (2026-10-28 19:01:23.495311).
   - 8-digit compact dates (20261028).
   - Fallback to today on invalid or partial strings.
3. Both root models.complaint and ev-stealth-web/models/complaint parity.
"""

from __future__ import annotations

from datetime import datetime, timezone
import unittest
from typing import Any

from models.complaint import ComplaintRecord, DSIBreakdown, DEFECT_CATEGORY_KO_MAP


class TestSync21ComplaintFromDict(unittest.TestCase):
    """Test suite for ComplaintRecord.from_dict symmetric deserialization."""

    def test_01_pass_through_existing_complaint_record(self) -> None:
        """ComplaintRecord.from_dict returns the exact instance if data is already ComplaintRecord."""
        rec = ComplaintRecord(
            id="ev-101",
            source="dcinside",
            url="https://example.com/101",
            title="충전 속도 저하",
            author="익명",
            created_at="2026-10-28 19:01:23.495311",
            vehicle_brand="Hyundai",
            vehicle_model="Ioniq 5",
            defect_category="BATTERY_CHARGING",
            summary="급속 충전 불량",
            verbatim_quote="100kW 충전기에서 30kW밖에 안 나옵니다.",
            slang_terms_detected=["벽돌", "충전먹통"],
            sentiment_polarity=-0.65,
            negativity_score=0.82,
            severity_index=6.5,
            is_authentic_defect=True,
            dsi_breakdown=DSIBreakdown(safety=4.0, functional=8.0, economic=6.0, social=2.0, convenience=7.0),
            filter_reason="",
            severity="HIGH",
        )
        result = ComplaintRecord.from_dict(rec)
        self.assertIs(result, rec)
        self.assertEqual(result.id, "ev-101")
        self.assertEqual(result.source, "dcinside")
        self.assertEqual(result.date_str, "2026-10-28")

    def test_02_key_aliases_resolution(self) -> None:
        """ComplaintRecord.from_dict maps all statutory key aliases accurately."""
        payload = {
            "platform": "bobaedream",            # alias for source
            "post_id": "bb-9988",                # alias for id
            "post_url": "https://bobaedream.co.kr/view/9988", # alias for url
            "post_title": "테슬라 모델Y 단차 심각", # alias for title
            "author": "보배차주",
            "created_at": "20261028",
            "target_vehicle": "Tesla Model Y",   # fallback for brand & model
            "defect_category": "BUILD_QUALITY",
            "summary": "트렁크 및 휀더 단차",
            "raw_quote": "단차가 손가락 하나 들어갈 정도입니다.", # alias for verbatim_quote
            "slang_tags": ["단차에디션", "조립불량"], # alias for slang_terms_detected
            "sentiment_score": 0.78,             # alias for negativity_score
            "sentiment_polarity": -0.55,
            "severity_index": 5.2,
            "is_authentic_defect": True,
            "dsi_breakdown": {
                "safety": 2.0,
                "functional": 4.0,
                "economic": 7.0,
                "social": 5.0,
                "convenience": 6.0,
            },
        }

        rec = ComplaintRecord.from_dict(payload)
        self.assertEqual(rec.id, "bb-9988")
        self.assertEqual(rec.source, "bobaedream")
        self.assertEqual(rec.url, "https://bobaedream.co.kr/view/9988")
        self.assertEqual(rec.title, "테슬라 모델Y 단차 심각")
        self.assertEqual(rec.vehicle_brand, "Tesla")
        self.assertEqual(rec.vehicle_model, "Model Y")
        self.assertEqual(rec.defect_category, "BUILD_QUALITY")
        self.assertEqual(rec.verbatim_quote, "단차가 손가락 하나 들어갈 정도입니다.")
        self.assertEqual(rec.slang_terms_detected, ["단차에디션", "조립불량"])
        self.assertAlmostEqual(rec.negativity_score, 0.78, places=4)
        self.assertAlmostEqual(rec.sentiment_polarity, -0.55, places=4)
        self.assertAlmostEqual(rec.severity_index, 5.2, places=2)
        self.assertIsNotNone(rec.dsi_breakdown)
        assert rec.dsi_breakdown is not None
        self.assertEqual(rec.dsi_breakdown.safety, 2.0)
        self.assertEqual(rec.dsi_breakdown.economic, 7.0)
        self.assertEqual(rec.date_str, "2026-10-28")

    def test_03_target_vehicle_fallbacks(self) -> None:
        """Target vehicle correctly parses into vehicle_brand and vehicle_model with various inputs."""
        cases = [
            ("Hyundai Ioniq 5", "Hyundai", "Ioniq 5"),
            ("Kia EV6", "Kia", "EV6"),
            ("Tesla Model 3", "Tesla", "Model 3"),
            ("BYD Atto 3", "BYD", "Atto 3"),
            ("Mercedes-Benz EQE 350", "Mercedes-Benz", "EQE 350"),
            ("Genesis GV60", "Genesis", "GV60"),
            ("Porsche Taycan", "Porsche", "Taycan"),
            ("Other 전기차", "Other", "전기차"),
            ("현대 아이오닉5", "Hyundai", "아이오닉5"),
            ("기아 EV9", "Kia", "EV9"),
            ("Ioniq 6", "Hyundai", "Ioniq 6"),
            ("Model Y", "Tesla", "Model Y"),
            ("샤오미 SU7", "샤오미", "SU7"),
        ]
        for tv, exp_brand, exp_model in cases:
            with self.subTest(tv=tv):
                rec = ComplaintRecord.from_dict({
                    "id": "tv-test",
                    "target_vehicle": tv,
                })
                self.assertEqual(rec.vehicle_brand, exp_brand, f"Brand mismatch for target_vehicle '{tv}'")
                self.assertEqual(rec.vehicle_model, exp_model, f"Model mismatch for target_vehicle '{tv}'")

    def test_04_target_vehicle_respects_explicit_fields(self) -> None:
        """Explicit vehicle_brand and vehicle_model take precedence over target_vehicle."""
        rec = ComplaintRecord.from_dict({
            "id": "exp-1",
            "vehicle_brand": "Tesla",
            "vehicle_model": "Model 3 Highland",
            "target_vehicle": "Hyundai Ioniq 5",
        })
        self.assertEqual(rec.vehicle_brand, "Tesla")
        self.assertEqual(rec.vehicle_model, "Model 3 Highland")

        # If only model is missing
        rec2 = ComplaintRecord.from_dict({
            "id": "exp-2",
            "vehicle_brand": "Kia",
            "target_vehicle": "Kia EV6 GT",
        })
        self.assertEqual(rec2.vehicle_brand, "Kia")
        self.assertEqual(rec2.vehicle_model, "EV6 GT")

    def test_05_dsi_breakdown_passthrough_and_dict(self) -> None:
        """dsi_breakdown supports both DSIBreakdown instances and nested dictionaries."""
        # DSIBreakdown instance
        dsi_obj = DSIBreakdown(safety=9.0, functional=7.0, economic=5.0, social=3.0, convenience=1.0)
        rec1 = ComplaintRecord.from_dict({"id": "dsi-1", "dsi_breakdown": dsi_obj})
        self.assertIs(rec1.dsi_breakdown, dsi_obj)

        # Dictionary
        dsi_dict = {"safety": 8.5, "functional": 6.2, "economic": 4.1, "social": 2.0, "convenience": 5.5}
        rec2 = ComplaintRecord.from_dict({"id": "dsi-2", "dsi_breakdown": dsi_dict})
        self.assertIsInstance(rec2.dsi_breakdown, DSIBreakdown)
        assert rec2.dsi_breakdown is not None
        self.assertEqual(rec2.dsi_breakdown.safety, 8.5)
        self.assertEqual(rec2.dsi_breakdown.convenience, 5.5)

        # None / Missing
        rec3 = ComplaintRecord.from_dict({"id": "dsi-3"})
        self.assertIsNone(rec3.dsi_breakdown)

    def test_06_round_trip_to_dict_symmetry(self) -> None:
        """ComplaintRecord -> to_dict() -> from_dict() maintains exact data symmetry."""
        orig = ComplaintRecord(
            id="sym-1",
            source="bobaedream",
            url="https://example.com/sym1",
            title="모터 인버터 소음",
            author="테스터",
            created_at="2026-10-28 12:30:00",
            vehicle_brand="Kia",
            vehicle_model="EV6",
            defect_category="DRIVING_POWERTRAIN",
            summary="고주파음 발생",
            verbatim_quote="가속 시 삐- 소리가 지속됩니다.",
            slang_terms_detected=["귀신소리", "모터음"],
            sentiment_polarity=-0.45,
            negativity_score=0.68,
            severity_index=4.5,
            is_authentic_defect=True,
            dsi_breakdown=DSIBreakdown(safety=3.0, functional=6.0, economic=4.0, social=2.0, convenience=7.0),
        )
        d = orig.to_dict()
        reconstructed = ComplaintRecord.from_dict(d)
        self.assertEqual(reconstructed.id, orig.id)
        self.assertEqual(reconstructed.source, orig.source)
        self.assertEqual(reconstructed.url, orig.url)
        self.assertEqual(reconstructed.title, orig.title)
        self.assertEqual(reconstructed.author, orig.author)
        self.assertEqual(reconstructed.created_at, orig.created_at)
        self.assertEqual(reconstructed.vehicle_brand, orig.vehicle_brand)
        self.assertEqual(reconstructed.vehicle_model, orig.vehicle_model)
        self.assertEqual(reconstructed.defect_category, orig.defect_category)
        self.assertEqual(reconstructed.verbatim_quote, orig.verbatim_quote)
        self.assertEqual(reconstructed.slang_terms_detected, orig.slang_terms_detected)
        self.assertAlmostEqual(reconstructed.sentiment_polarity, orig.sentiment_polarity, places=4)
        self.assertAlmostEqual(reconstructed.negativity_score, orig.negativity_score, places=4)
        self.assertAlmostEqual(reconstructed.severity_index, orig.severity_index, places=2)
        self.assertEqual(reconstructed.is_authentic_defect, orig.is_authentic_defect)

    def test_07_round_trip_to_admin_report_dict_symmetry(self) -> None:
        """ComplaintRecord -> to_admin_report_dict() -> from_dict() maintains exact data symmetry."""
        orig = ComplaintRecord(
            id="admin-sym-1",
            source="dcinside",
            url="https://example.com/admin1",
            title="ICC-U 충전 불량",
            author="익명작성자",
            created_at="2026-10-28 19:01:23.495311",
            vehicle_brand="Hyundai",
            vehicle_model="Ioniq 5",
            defect_category="BATTERY_CHARGING",
            summary="완속 충전 불가",
            verbatim_quote="ICCU 터졌습니다.",
            slang_terms_detected=["ICCU", "벽돌"],
            sentiment_polarity=-0.85,
            negativity_score=0.92,
            severity_index=8.8,
            is_authentic_defect=True,
            dsi_breakdown=DSIBreakdown(safety=8.0, functional=9.0, economic=8.0, social=6.0, convenience=9.0),
            severity="CRITICAL",
        )
        admin_d = orig.to_admin_report_dict()
        reconstructed = ComplaintRecord.from_dict(admin_d)
        self.assertEqual(reconstructed.id, orig.id)
        self.assertEqual(reconstructed.source, orig.source)
        self.assertEqual(reconstructed.title, orig.title)
        self.assertEqual(reconstructed.vehicle_brand, orig.vehicle_brand)
        self.assertEqual(reconstructed.vehicle_model, orig.vehicle_model)
        self.assertEqual(reconstructed.defect_category, orig.defect_category)
        self.assertEqual(reconstructed.verbatim_quote, orig.verbatim_quote)
        self.assertEqual(reconstructed.slang_terms_detected, orig.slang_terms_detected)
        self.assertEqual(reconstructed.severity, "CRITICAL")
        self.assertEqual(reconstructed.date_str, "2026-10-28")

    def test_08_empty_none_and_corrupt_inputs(self) -> None:
        """ComplaintRecord.from_dict gracefully defaults on empty, None, or non-dict inputs."""
        for invalid_input in [None, {}, "", 12345, []]:
            with self.subTest(invalid=invalid_input):
                rec = ComplaintRecord.from_dict(invalid_input)
                self.assertIsInstance(rec, ComplaintRecord)
                self.assertEqual(rec.id, "")
                self.assertEqual(rec.source, "unknown")
                self.assertEqual(rec.vehicle_brand, "")
                self.assertEqual(rec.vehicle_model, "")
                self.assertTrue(rec.is_authentic_defect)
                self.assertIsNone(rec.dsi_breakdown)


class TestSync21ComplaintDateParsing(unittest.TestCase):
    """Test suite for ComplaintRecord.date_str robust parsing."""

    def _make(self, created_at: Any) -> ComplaintRecord:
        return ComplaintRecord(
            id="date-test",
            source="dcinside",
            url="",
            title="",
            author="",
            created_at=created_at,
            vehicle_brand="Hyundai",
            vehicle_model="Ioniq 5",
            defect_category="BATTERY_CHARGING",
            summary="",
            verbatim_quote="",
        )

    def test_01_timestamp_with_space_and_seconds(self) -> None:
        """Parses timestamps with space e.g. YYYY-MM-DD HH:MM and YYYY-MM-DD HH:MM:SS."""
        self.assertEqual(self._make("2026-10-28 19:01").date_str, "2026-10-28")
        self.assertEqual(self._make("2026-10-28 19:01:23").date_str, "2026-10-28")
        self.assertEqual(self._make("  2026-10-28   19:01:23  ").date_str, "2026-10-28")
        self.assertEqual(self._make("2026.10.28 19:01:23").date_str, "2026-10-28")
        self.assertEqual(self._make("2026/10/28 19:01:23").date_str, "2026-10-28")

    def test_02_subsecond_timestamps(self) -> None:
        """Parses timestamps with microsecond sub-seconds (2026-10-28 19:01:23.495311)."""
        self.assertEqual(self._make("2026-10-28 19:01:23.495311").date_str, "2026-10-28")
        self.assertEqual(self._make("2026-10-28T19:01:23.495311").date_str, "2026-10-28")
        self.assertEqual(self._make("2026-10-28T19:01:23.495311Z").date_str, "2026-10-28")
        self.assertEqual(self._make("2026-10-28 19:01:23.495311+09:00").date_str, "2026-10-28")

    def test_03_compact_8_digit_dates(self) -> None:
        """Parses 8-digit compact dates (20261028) and 14-digit compact timestamps."""
        self.assertEqual(self._make("20261028").date_str, "2026-10-28")
        self.assertEqual(self._make("  20261028  ").date_str, "2026-10-28")
        self.assertEqual(self._make("20260105").date_str, "2026-01-05")
        self.assertEqual(self._make("20261028190123").date_str, "2026-10-28")

    def test_04_korean_and_twodigit_year_dates(self) -> None:
        """Parses Korean explicit format, Korean dotted dates, and 2-digit years."""
        self.assertEqual(self._make("2026년 10월 28일").date_str, "2026-10-28")
        self.assertEqual(self._make("2026년 9월 5일").date_str, "2026-09-05")
        self.assertEqual(self._make("2026. 10. 25.").date_str, "2026-10-25")
        self.assertEqual(self._make("2026. 9. 8.").date_str, "2026-09-08")
        self.assertEqual(self._make("26.10.25").date_str, "2026-10-25")
        self.assertEqual(self._make("26-10-25").date_str, "2026-10-25")

    def test_05_fallback_to_today_on_invalid_or_partial_strings(self) -> None:
        """Corrupt, partial, or invalid dates cleanly fallback to today's UTC date."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.assertEqual(self._make("").date_str, today)
        self.assertEqual(self._make("   ").date_str, today)
        self.assertEqual(self._make(None).date_str, today)
        self.assertEqual(self._make("2026").date_str, today)
        self.assertEqual(self._make("2026-04").date_str, today)
        self.assertEqual(self._make("99999999").date_str, today)
        self.assertEqual(self._make("123456789").date_str, today)
        self.assertEqual(self._make("not-a-date").date_str, today)


if __name__ == "__main__":
    unittest.main()
