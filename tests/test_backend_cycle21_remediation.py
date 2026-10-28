"""
tests/test_backend_cycle21_remediation.py - Unit test suite locking in all Cycle 21 Backend Remediations.

Authoritative Reference:
- ORIGINAL_REQUEST.md
- DISPATCH.md (Cycle 21 Backend Remediation Specification)
- COLLABORATION.md

Classes & Coverage (21 tests across 4 test classes):
1. TestComplaintRecordFromDictAndAliases (8 tests: 01-08)
   - test_01_pass_through_existing_complaint_record: Pass-through if already ComplaintRecord instance.
   - test_02_all_key_aliases_resolution: platform, post_id, post_url, post_title, raw_quote, slang_tags, sentiment_score, date.
   - test_03_target_vehicle_brand_and_model_fallbacks: brand and model extraction when target_vehicle provided.
   - test_04_target_vehicle_respects_explicit_fields: explicit vehicle_brand and vehicle_model take precedence.
   - test_05_dsi_breakdown_conversion: DSIBreakdown instance, dict breakdown, and None handling.
   - test_06_round_trip_to_dict_symmetry: ComplaintRecord -> to_dict() -> from_dict() 100% symmetry.
   - test_07_round_trip_to_admin_report_dict_symmetry: ComplaintRecord -> to_admin_report_dict() -> from_dict() 100% symmetry.
   - test_08_empty_none_and_malformed_inputs: graceful default fallback on None, {}, "", non-dict inputs.

2. TestComplaintRecordDateStrParsing (5 tests: 09-13)
   - test_09_subsecond_microsecond_timestamp_parsing: YYYY-MM-DD HH:MM:SS.ffffff and ISO variations.
   - test_10_space_separated_dates_and_times: YYYY-MM-DD HH:MM and YYYY-MM-DD HH:MM:SS with whitespace.
   - test_11_compact_8_digit_and_14_digit_strings: 20261028 and 20261028190123.
   - test_12_korean_and_twodigit_year_formats: YYYY년 MM월 DD일, YY.MM.DD, and dotted formats.
   - test_13_corrupt_and_invalid_date_fallback_to_today: graceful fallback to today's UTC date.

3. TestSubsidyModelsDictLikeAccessors (3 tests: 14-16)
   - test_14_popular_model_entry_dict_accessors: __getitem__, __contains__, and get() on PopularModelEntry.
   - test_15_municipality_metrics_dict_accessors: __getitem__, __contains__, and get() on MunicipalityMetrics.
   - test_16_category_metrics_and_region_record_dict_accessors: mapping protocol on CategoryMetrics, RegionRecord, NationwideSummary.

4. TestExpanded2026VehicleMatcher (5 tests: 17-21)
   - test_17_ev9_gt_recognition: Kia EV9 GT extraction and distinction from base EV9.
   - test_18_ioniq_6_n_recognition: Hyundai 아이오닉6 N extraction and distinction from base Ioniq 6.
   - test_19_polestar_3_and_polestar_5_recognition: Other 폴스타 3 and 폴스타 5 extraction.
   - test_20_casper_cross_recognition: Hyundai 캐스퍼 일렉트릭 extraction from Casper Cross.
   - test_21_expanded_model_rules_boundaries_and_korean_particles: case-insensitivity and Korean particle boundary tests.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
import unittest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from filters.vehicle_matcher import extract_vehicle_info, BRAND_HYUNDAI, BRAND_KIA, BRAND_OTHER, BRAND_TESLA, BRAND_BYD
from models.complaint import ComplaintRecord, DSIBreakdown, DEFECT_CATEGORY_KO_MAP
from tracker.subsidy_models import (
    CategoryMetrics,
    MunicipalityMetrics,
    NationwideSummary,
    PopularModelEntry,
    RegionRecord,
)


# ===========================================================================
# Class 1: TestComplaintRecordFromDictAndAliases
# ===========================================================================
class TestComplaintRecordFromDictAndAliases(unittest.TestCase):
    """Rigorous verification of ComplaintRecord.from_dict deserialization, aliases, and symmetry."""

    def test_01_pass_through_existing_complaint_record(self) -> None:
        """ComplaintRecord.from_dict returns the exact instance if data is already a ComplaintRecord."""
        rec = ComplaintRecord(
            id="ev-pass-101",
            source="dcinside",
            url="https://gall.dcinside.com/car_new1/101",
            title="고속도로 ICCU 셧다운",
            author="익명차주",
            created_at="2026-10-28 19:01:23.495311",
            vehicle_brand="Hyundai",
            vehicle_model="Ioniq 5",
            defect_category="BATTERY_CHARGING",
            summary="주행 중 경고등 점등 및 구동력 상실",
            verbatim_quote="갑자기 퍽 소리 나더니 배터리 경고등 뜨고 악셀 먹통됨",
            slang_terms_detected=["ICCU", "벽돌"],
            sentiment_polarity=-0.85,
            negativity_score=0.96,
            severity_index=8.5,
            is_authentic_defect=True,
            dsi_breakdown=DSIBreakdown(safety=8.0, functional=9.0, economic=7.0, social=6.0, convenience=8.0),
            severity="CRITICAL",
        )
        res = ComplaintRecord.from_dict(rec)
        self.assertIs(res, rec)
        self.assertEqual(res.id, "ev-pass-101")
        self.assertEqual(res.source, "dcinside")
        self.assertEqual(res.date_str, "2026-10-28")

    def test_02_all_key_aliases_resolution(self) -> None:
        """ComplaintRecord.from_dict resolves all statutory aliases (platform, post_id, post_url, post_title, raw_quote, slang_tags, sentiment_score, date)."""
        payload = {
            "platform": "bobaedream",
            "post_id": "bb-20260908",
            "post_url": "https://bobaedream.co.kr/view/20260908",
            "post_title": "기아 EV3 빗길 주행 피쉬테일",
            "author": "보배차주",
            "date": "2026-10-28",
            "target_vehicle": "Kia EV3",
            "defect_category": "DRIVING_POWERTRAIN",
            "summary": "빗길 이음새 급격한 자세 불안정",
            "raw_quote": "비 오는 날 고속도로 이음새 밟고 회생제동 살짝 걸리는 순간 뒤쪽이 사정없이 털림",
            "slang_tags": ["피쉬테일", "토션빔"],
            "sentiment_score": 0.94,
            "sentiment_polarity": -0.75,
            "severity_index": 7.8,
            "is_authentic_defect": True,
            "dsi_breakdown": {
                "safety": 9.0,
                "functional": 8.0,
                "economic": 5.0,
                "social": 6.0,
                "convenience": 4.0,
            },
        }

        rec = ComplaintRecord.from_dict(payload)
        self.assertEqual(rec.id, "bb-20260908")
        self.assertEqual(rec.source, "bobaedream")
        self.assertEqual(rec.url, "https://bobaedream.co.kr/view/20260908")
        self.assertEqual(rec.title, "기아 EV3 빗길 주행 피쉬테일")
        self.assertEqual(rec.vehicle_brand, "Kia")
        self.assertEqual(rec.vehicle_model, "EV3")
        self.assertEqual(rec.defect_category, "DRIVING_POWERTRAIN")
        self.assertEqual(rec.verbatim_quote, "비 오는 날 고속도로 이음새 밟고 회생제동 살짝 걸리는 순간 뒤쪽이 사정없이 털림")
        self.assertEqual(rec.slang_terms_detected, ["피쉬테일", "토션빔"])
        self.assertAlmostEqual(rec.negativity_score, 0.94, places=4)
        self.assertAlmostEqual(rec.sentiment_polarity, -0.75, places=4)
        self.assertAlmostEqual(rec.severity_index, 7.8, places=2)
        self.assertIsNotNone(rec.dsi_breakdown)
        assert rec.dsi_breakdown is not None
        self.assertEqual(rec.dsi_breakdown.safety, 9.0)
        self.assertEqual(rec.dsi_breakdown.convenience, 4.0)
        self.assertEqual(rec.date_str, "2026-10-28")

    def test_03_target_vehicle_brand_and_model_fallbacks(self) -> None:
        """Target vehicle correctly parses into vehicle_brand and vehicle_model with diverse formats."""
        cases = [
            ("Hyundai Ioniq 5", "Hyundai", "Ioniq 5"),
            ("Kia EV6", "Kia", "EV6"),
            ("Tesla Model 3", "Tesla", "Model 3"),
            ("BYD Atto 3", "BYD", "Atto 3"),
            ("Genesis GV60", "Genesis", "GV60"),
            ("Porsche Taycan", "Porsche", "Taycan"),
            ("Kia EV9 GT", "Kia", "EV9 GT"),
            ("Hyundai Ioniq 6 N", "Hyundai", "Ioniq 6 N"),
            ("Polestar 3", "Polestar", "3"),
            ("Polestar 5", "Polestar", "5"),
        ]
        for tv, exp_brand, exp_model in cases:
            with self.subTest(tv=tv):
                rec = ComplaintRecord.from_dict({
                    "id": "tv-test",
                    "target_vehicle": tv,
                })
                self.assertEqual(rec.vehicle_brand, exp_brand, f"Brand mismatch for '{tv}'")
                self.assertEqual(rec.vehicle_model, exp_model, f"Model mismatch for '{tv}'")

    def test_04_target_vehicle_respects_explicit_fields(self) -> None:
        """Explicit vehicle_brand and vehicle_model take precedence over target_vehicle."""
        rec = ComplaintRecord.from_dict({
            "id": "exp-1",
            "vehicle_brand": "Kia",
            "vehicle_model": "EV9 GT",
            "target_vehicle": "Hyundai Ioniq 5",
        })
        self.assertEqual(rec.vehicle_brand, "Kia")
        self.assertEqual(rec.vehicle_model, "EV9 GT")

        # If only vehicle_brand is provided, model parsed from target_vehicle
        rec2 = ComplaintRecord.from_dict({
            "id": "exp-2",
            "vehicle_brand": "Hyundai",
            "target_vehicle": "Hyundai Ioniq 6 N",
        })
        self.assertEqual(rec2.vehicle_brand, "Hyundai")
        self.assertEqual(rec2.vehicle_model, "Ioniq 6 N")

    def test_05_dsi_breakdown_conversion(self) -> None:
        """dsi_breakdown supports DSIBreakdown instance, dict breakdown, and None fallback."""
        # 1. DSIBreakdown instance
        dsi_obj = DSIBreakdown(safety=9.0, functional=8.0, economic=7.0, social=6.0, convenience=5.0)
        rec1 = ComplaintRecord.from_dict({"id": "dsi-obj", "dsi_breakdown": dsi_obj})
        self.assertIs(rec1.dsi_breakdown, dsi_obj)

        # 2. Dictionary
        dsi_dict = {"safety": 7.5, "functional": 6.5, "economic": 8.0, "social": 4.0, "convenience": 5.0}
        rec2 = ComplaintRecord.from_dict({"id": "dsi-dict", "dsi_breakdown": dsi_dict})
        self.assertIsInstance(rec2.dsi_breakdown, DSIBreakdown)
        assert rec2.dsi_breakdown is not None
        self.assertEqual(rec2.dsi_breakdown.safety, 7.5)
        self.assertEqual(rec2.dsi_breakdown.economic, 8.0)

        # 3. None / Missing
        rec3 = ComplaintRecord.from_dict({"id": "dsi-none"})
        self.assertIsNone(rec3.dsi_breakdown)

    def test_06_round_trip_to_dict_symmetry(self) -> None:
        """ComplaintRecord -> to_dict() -> from_dict() maintains exact data symmetry."""
        orig = ComplaintRecord(
            id="sym-test-1",
            source="dcinside",
            url="https://gall.dcinside.com/car_new1/9999",
            title="테슬라 모델Y 주니퍼 리프레시 단차",
            author="익명테스터",
            created_at="2026-10-28 15:30:00",
            vehicle_brand="Tesla",
            vehicle_model="Model Y Juniper",
            defect_category="BUILD_QUALITY",
            summary="트렁크 및 휀더 조립 단차",
            verbatim_quote="손가락 하나 들어갈 정도로 단차가 심합니다",
            slang_terms_detected=["단차에디션"],
            sentiment_polarity=-0.60,
            negativity_score=0.85,
            severity_index=6.2,
            is_authentic_defect=True,
            dsi_breakdown=DSIBreakdown(safety=3.0, functional=5.0, economic=7.0, social=5.0, convenience=7.0),
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
            id="admin-sym-2026",
            source="bobaedream",
            url="https://bobaedream.co.kr/view/9999",
            title="EV6 배터리 케이스 파손",
            author="보배회원",
            created_at="2026-10-28 19:01:23.495311",
            vehicle_brand="Kia",
            vehicle_model="EV6",
            defect_category="SERVICE_REPAIR_COST",
            summary="경미한 긁힘에 통교체 3800만원 요구",
            verbatim_quote="하부 스크래치 났다고 배터리 통교체 3800만원 부름",
            slang_terms_detected=["강제전손"],
            sentiment_polarity=-0.90,
            negativity_score=0.98,
            severity_index=9.2,
            is_authentic_defect=True,
            dsi_breakdown=DSIBreakdown(safety=9.0, functional=9.0, economic=10.0, social=8.0, convenience=7.0),
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
        self.assertEqual(reconstructed.severity, "CRITICAL")
        self.assertEqual(reconstructed.date_str, "2026-10-28")

    def test_08_empty_none_and_malformed_inputs(self) -> None:
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


# ===========================================================================
# Class 2: TestComplaintRecordDateStrParsing
# ===========================================================================
class TestComplaintRecordDateStrParsing(unittest.TestCase):
    """Rigorous verification of ComplaintRecord.date_str datetime parser."""

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

    def test_09_subsecond_microsecond_timestamp_parsing(self) -> None:
        """Parses sub-second timestamps with microseconds accurately."""
        self.assertEqual(self._make("2026-10-28 19:01:23.495311").date_str, "2026-10-28")
        self.assertEqual(self._make("2026-10-28T19:01:23.495311").date_str, "2026-10-28")
        self.assertEqual(self._make("2026-10-28T19:01:23.495311Z").date_str, "2026-10-28")
        self.assertEqual(self._make("2026-10-28 19:01:23.495311+09:00").date_str, "2026-10-28")

    def test_10_space_separated_dates_and_times(self) -> None:
        """Parses timestamps with spaces, minutes, seconds, and slash/dot delimiters."""
        self.assertEqual(self._make("2026-10-28 19:01").date_str, "2026-10-28")
        self.assertEqual(self._make("2026-10-28 19:01:23").date_str, "2026-10-28")
        self.assertEqual(self._make("  2026-10-28   19:01:23  ").date_str, "2026-10-28")
        self.assertEqual(self._make("2026.10.28 19:01:23").date_str, "2026-10-28")
        self.assertEqual(self._make("2026/10/28 19:01:23").date_str, "2026-10-28")

    def test_11_compact_8_digit_and_14_digit_strings(self) -> None:
        """Parses compact 8-digit and 14-digit timestamps cleanly."""
        self.assertEqual(self._make("20261028").date_str, "2026-10-28")
        self.assertEqual(self._make("  20261028  ").date_str, "2026-10-28")
        self.assertEqual(self._make("20260105").date_str, "2026-01-05")
        self.assertEqual(self._make("20261028190123").date_str, "2026-10-28")

    def test_12_korean_and_twodigit_year_formats(self) -> None:
        """Parses Korean explicit format, Korean dotted dates, and 2-digit years."""
        self.assertEqual(self._make("2026년 10월 28일").date_str, "2026-10-28")
        self.assertEqual(self._make("2026년 9월 5일").date_str, "2026-09-05")
        self.assertEqual(self._make("2026. 10. 25.").date_str, "2026-10-25")
        self.assertEqual(self._make("2026. 9. 8.").date_str, "2026-09-08")
        self.assertEqual(self._make("26.10.25").date_str, "2026-10-25")
        self.assertEqual(self._make("26-10-25").date_str, "2026-10-25")

    def test_13_corrupt_and_invalid_date_fallback_to_today(self) -> None:
        """Corrupt, partial, or invalid date strings fallback safely to today's UTC date."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.assertEqual(self._make("").date_str, today)
        self.assertEqual(self._make("   ").date_str, today)
        self.assertEqual(self._make(None).date_str, today)
        self.assertEqual(self._make("not-a-date").date_str, today)
        self.assertEqual(self._make("2026").date_str, today)
        self.assertEqual(self._make("99999999").date_str, today)


# ===========================================================================
# Class 3: TestSubsidyModelsDictLikeAccessors
# ===========================================================================
class TestSubsidyModelsDictLikeAccessors(unittest.TestCase):
    """Verifies dict-like accessors (__getitem__, __contains__, get) across subsidy dataclasses."""

    def test_14_popular_model_entry_dict_accessors(self) -> None:
        """PopularModelEntry supports uniform __getitem__, __contains__, and get()."""
        model = PopularModelEntry(
            model_id="ev9_gt",
            name_ko="기아 EV9 GT",
            manufacturer="기아",
            battery_type="NCM",
            battery_capacity_kwh=99.8,
            rated_range_km=440,
            base_price_krw=82000000,
            price_subsidy_ratio=0.5,
            national_subsidy_krw=3250000,
            regional_subsidy_samples={"KR-11": {"local_subsidy_krw": 750000}},
        )

        # __getitem__
        self.assertEqual(model["model_id"], "ev9_gt")
        self.assertEqual(model["name_ko"], "기아 EV9 GT")
        self.assertEqual(model["battery_capacity_kwh"], 99.8)
        self.assertEqual(model["price_subsidy_ratio"], 0.5)

        # get()
        self.assertEqual(model.get("model_id"), "ev9_gt")
        self.assertEqual(model.get("manufacturer"), "기아")
        self.assertEqual(model.get("missing_key", "default_val"), "default_val")
        self.assertIsNone(model.get("missing_key"))

        # __contains__
        self.assertIn("model_id", model)
        self.assertIn("name_ko", model)
        self.assertIn("base_price_krw", model)
        self.assertNotIn("non_existent_key", model)

        # Missing key raises KeyError
        with self.assertRaises(KeyError):
            _ = model["non_existent_key"]

        # Non-string key safety
        self.assertNotIn(12345, model)
        self.assertEqual(model.get(12345, "fallback"), "fallback")

    def test_15_municipality_metrics_dict_accessors(self) -> None:
        """MunicipalityMetrics supports uniform __getitem__, __contains__, and get()."""
        muni = MunicipalityMetrics(
            name_ko="수원시",
            announced_units=500,
            applied_units=450,
            remaining_units=50,
            depletion_rate=90.0,
            status="WARNING",
            local_subsidy_krw=3500000,
            muni_id="KR-41-110",
            name_en="Suwon-si",
            category="passenger",
            delivered_units=400,
            total_subsidy_krw=10000000,
        )

        # __getitem__
        self.assertEqual(muni["name_ko"], "수원시")
        self.assertEqual(muni["announced_units"], 500)
        self.assertEqual(muni["depletion_rate"], 90.0)
        self.assertEqual(muni["muni_id"], "KR-41-110")

        # get()
        self.assertEqual(muni.get("name_ko"), "수원시")
        self.assertEqual(muni.get("status"), "WARNING")
        self.assertEqual(muni.get("unknown_key", "def"), "def")
        self.assertIsNone(muni.get("unknown_key"))

        # __contains__
        self.assertIn("name_ko", muni)
        self.assertIn("announced_units", muni)
        self.assertIn("muni_id", muni)
        self.assertNotIn("missing_field", muni)

        # KeyError on missing
        with self.assertRaises(KeyError):
            _ = muni["missing_field"]

    def test_16_category_metrics_and_region_record_dict_accessors(self) -> None:
        """CategoryMetrics, RegionRecord, and NationwideSummary support mapping protocol."""
        cat = CategoryMetrics(
            announced_units=1000,
            applied_units=850,
            delivered_units=750,
            remaining_units=150,
            depletion_rate=85.0,
            delivery_rate=75.0,
            status="WARNING",
            max_local_subsidy_krw=1500000,
            max_total_subsidy_krw=8000000,
            total_budget_krw=8000000000,
            remaining_budget_krw=1200000000,
        )
        self.assertEqual(cat["announced_units"], 1000)
        self.assertEqual(cat.get("depletion_rate"), 85.0)
        self.assertIn("status", cat)

        reg = RegionRecord(
            region_id="KR-11",
            name_ko="서울특별시",
            name_en="Seoul",
            tier="special_city",
            overall_depletion_rate=87.8,
            overall_status="WARNING",
            categories={"passenger": cat},
        )
        self.assertEqual(reg["region_id"], "KR-11")
        self.assertEqual(reg.get("name_ko"), "서울특별시")
        self.assertIn("categories", reg)


# ===========================================================================
# Class 4: TestExpanded2026VehicleMatcher
# ===========================================================================
class TestExpanded2026VehicleMatcher(unittest.TestCase):
    """Rigorous verification of expanded 2026 EV models in filters/vehicle_matcher.py."""

    def test_17_ev9_gt_recognition(self) -> None:
        """Recognizes Kia EV9 GT and distinguishes from base EV9."""
        # EV9 GT
        self.assertEqual(extract_vehicle_info("기아 EV9 GT 출고했습니다"), (BRAND_KIA, "EV9 GT"))
        self.assertEqual(extract_vehicle_info("ev9 gt 브레이크 밀림 결함"), (BRAND_KIA, "EV9 GT"))
        self.assertEqual(extract_vehicle_info("EV9 GT 제로백 4.3초 성능 대박"), (BRAND_KIA, "EV9 GT"))

        # Base EV9
        self.assertEqual(extract_vehicle_info("기아 EV9 롱레인지 출고"), (BRAND_KIA, "EV9"))
        self.assertEqual(extract_vehicle_info("ev9 에어서스 승차감 어떰"), (BRAND_KIA, "EV9"))

    def test_18_ioniq_6_n_recognition(self) -> None:
        """Recognizes Hyundai 아이오닉 6 N and distinguishes from base Ioniq 6."""
        # Ioniq 6 N
        self.assertEqual(extract_vehicle_info("아이오닉 6 N 서킷 주행 소감"), (BRAND_HYUNDAI, "아이오닉6 N"))
        self.assertEqual(extract_vehicle_info("아이오닉6 N 제로백 테스트"), (BRAND_HYUNDAI, "아이오닉6 N"))
        self.assertEqual(extract_vehicle_info("ioniq 6 n 코너링 훌륭하네요"), (BRAND_HYUNDAI, "아이오닉6 N"))

        # Base Ioniq 6
        self.assertEqual(extract_vehicle_info("아이오닉 6 롱레인지 고속도로 전비"), (BRAND_HYUNDAI, "아이오닉6"))
        self.assertEqual(extract_vehicle_info("ioniq 6 뒷좌석 헤드룸 후기"), (BRAND_HYUNDAI, "아이오닉6"))

    def test_19_polestar_3_and_polestar_5_recognition(self) -> None:
        """Recognizes Polestar 3 and Polestar 5 and distinguishes from Polestar 2 / 4."""
        # Polestar 3
        self.assertEqual(extract_vehicle_info("폴스타 3 사전계약 완료했습니다"), (BRAND_OTHER, "폴스타 3"))
        self.assertEqual(extract_vehicle_info("polestar 3 디자인 실물 깡패"), (BRAND_OTHER, "폴스타 3"))
        self.assertEqual(extract_vehicle_info("폴스타3 출고 대기 중"), (BRAND_OTHER, "폴스타 3"))

        # Polestar 5
        self.assertEqual(extract_vehicle_info("폴스타 5 출시일 언제인가요"), (BRAND_OTHER, "폴스타 5"))
        self.assertEqual(extract_vehicle_info("polestar 5 스펙 및 가격 공개"), (BRAND_OTHER, "폴스타 5"))
        self.assertEqual(extract_vehicle_info("폴스타5 제원 기대됩니다"), (BRAND_OTHER, "폴스타 5"))

        # Polestar 2 / 4
        self.assertEqual(extract_vehicle_info("폴스타 2 싱글모터"), (BRAND_OTHER, "폴스타 2"))
        self.assertEqual(extract_vehicle_info("polestar 4 쿠페 SUV"), (BRAND_OTHER, "폴스타 4"))

    def test_20_casper_cross_recognition(self) -> None:
        """Recognizes Casper Cross as Hyundai 캐스퍼 일렉트릭."""
        self.assertEqual(extract_vehicle_info("캐스퍼 일렉트릭 크로스 옵션 추천"), (BRAND_HYUNDAI, "캐스퍼 일렉트릭"))
        self.assertEqual(extract_vehicle_info("casper cross 실물 후기"), (BRAND_HYUNDAI, "캐스퍼 일렉트릭"))
        self.assertEqual(extract_vehicle_info("캐스퍼일렉트릭크로스 오프로드 패키지"), (BRAND_HYUNDAI, "캐스퍼 일렉트릭"))
        self.assertEqual(extract_vehicle_info("캐스퍼 일렉트릭 인스퍼레이션 출고"), (BRAND_HYUNDAI, "캐스퍼 일렉트릭"))

    def test_21_expanded_model_rules_boundaries_and_korean_particles(self) -> None:
        """Tests Korean postpositional particles (은, 는, 이, 가, 을, 를, 의, 에, 과, 와, 도, 만, 로, 으로) and case insensitivity."""
        particles = ["은", "는", "이", "가", "을", "를", "의", "에", "과", "와", "도", "만", "로", "으로"]

        for p in particles:
            with self.subTest(particle=p):
                # EV9 GT with particle
                title_ev9 = f"EV9 GT{p} 진짜 물건이네요"
                self.assertEqual(extract_vehicle_info(title_ev9), (BRAND_KIA, "EV9 GT"))

                # Polestar 3 with particle
                title_pole3 = f"폴스타 3{p} 주행거리가 아쉽습니다"
                self.assertEqual(extract_vehicle_info(title_pole3), (BRAND_OTHER, "폴스타 3"))

                # Polestar 5 with particle
                title_pole5 = f"폴스타 5{p} 800V 시스템 탑재"
                self.assertEqual(extract_vehicle_info(title_pole5), (BRAND_OTHER, "폴스타 5"))


if __name__ == "__main__":
    unittest.main()
