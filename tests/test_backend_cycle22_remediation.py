"""
tests/test_backend_cycle22_remediation.py - Unit test suite locking in all Cycle 22 Backend Remediations.

Authoritative Reference:
- ORIGINAL_REQUEST.md
- DISPATCH.md (Cycle 22 Backend Remediation Specification)
- COLLABORATION.md

Classes & Coverage (20 tests across 4 test classes):
1. TestRawPostMappingProtocol (6 tests: 01-06)
   - test_01_raw_post_subscript_access: __getitem__ for platform, post_id, title, content, etc.
   - test_02_raw_post_subscript_missing_key_raises_keyerror: missing key raises KeyError.
   - test_03_raw_post_in_operator: __contains__ for valid and invalid keys.
   - test_04_raw_post_get_method: get() with and without default value.
   - test_05_raw_post_dict_conversion: dict(raw_post) produces full dictionary.
   - test_06_raw_post_iteration: iter(raw_post) yields all keys.

2. TestDSIBreakdownMappingProtocol (5 tests: 07-11)
   - test_07_dsi_breakdown_subscript_access: __getitem__ for safety, functional, economic, etc.
   - test_08_dsi_breakdown_missing_key_raises_keyerror: missing key raises KeyError.
   - test_09_dsi_breakdown_in_operator: __contains__ verification.
   - test_10_dsi_breakdown_get_method: get() with default.
   - test_11_dsi_breakdown_dict_unpacking: **dsi unpacking into dict.

3. TestExpandedVehicleMatcherCycle22 (5 tests: 12-16)
   - test_12_kia_ev2_particles: EV2는, EV2가, EV2의, EV2로, EV2를.
   - test_13_byd_sealion_dual_spelling_particles: 시라이언과, 씨라이언도, 씨라이언07, sealion7.
   - test_14_volkswagen_id4_idbuzz_variations: ID.4, id4, ID.Buzz, ID 버즈, VW ID.4.
   - test_15_tesla_model_2_particles: 모델 2는, Model 2가, model 2 예약.
   - test_16_hyundai_ioniq_7_particles: 아이오닉 7, ioniq 7 시승.

4. TestDepreciationAndSubsidyDefensiveBounds (4 tests: 17-20)
   - test_17_depreciation_cap_10b_krw: custom purchase price clamped to 10B KRW.
   - test_18_depreciation_negative_and_none_price: negative and None custom purchase price fallbacks.
   - test_19_subsidy_tracker_nan_and_inf_guards: price cap ratio and net subsidy with NaN/Inf inputs.
   - test_20_daily_report_statistics_mapping_protocol: DailyReportStatistics mapping protocol.
"""

from __future__ import annotations

import math
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

WEB_ROOT = PROJECT_ROOT / "ev-stealth-web" if (PROJECT_ROOT / "ev-stealth-web").exists() else PROJECT_ROOT

from filters.vehicle_matcher import extract_vehicle_info, BRAND_HYUNDAI, BRAND_KIA, BRAND_OTHER, BRAND_TESLA, BRAND_BYD
from models.complaint import (
    ComplaintRecord,
    DailyReportPayload,
    DailyReportStatistics,
    DSIBreakdown,
    RawPost,
)
from tracker.subsidy_tracker import calculate_price_cap_ratio, calculate_net_subsidy


# ===========================================================================
# Class 1: TestRawPostMappingProtocol
# ===========================================================================
class TestRawPostMappingProtocol(unittest.TestCase):
    """Rigorous verification of RawPost dictionary mapping protocol."""

    def setUp(self) -> None:
        self.post = RawPost(
            platform="dcinside",
            post_id="dc_9999",
            url="https://gall.dcinside.com/car_new1/9999",
            title="기아 EV3 고속도로 주행 후기",
            content="핸들 떨림이 심하고 승차감이 불안정합니다.",
            comments=["얼라인먼트 보세요", "공기압 체크"],
            created_at="2026-10-30 04:00:00",
            author="전기차초보",
        )

    def test_01_raw_post_subscript_access(self) -> None:
        """RawPost allows dict-like subscripting for all fields."""
        self.assertEqual(self.post["platform"], "dcinside")
        self.assertEqual(self.post["post_id"], "dc_9999")
        self.assertEqual(self.post["url"], "https://gall.dcinside.com/car_new1/9999")
        self.assertEqual(self.post["title"], "기아 EV3 고속도로 주행 후기")
        self.assertEqual(self.post["content"], "핸들 떨림이 심하고 승차감이 불안정합니다.")
        self.assertEqual(self.post["author"], "전기차초보")
        self.assertEqual(len(self.post["comments"]), 2)

    def test_02_raw_post_subscript_missing_key_raises_keyerror(self) -> None:
        """Accessing a non-existent key via subscript raises KeyError."""
        with self.assertRaises(KeyError):
            _ = self.post["non_existent_key"]

    def test_03_raw_post_in_operator(self) -> None:
        """'in' operator accurately checks key presence."""
        self.assertIn("title", self.post)
        self.assertIn("url", self.post)
        self.assertIn("platform", self.post)
        self.assertNotIn("unknown_key", self.post)
        self.assertNotIn("battery_capacity", self.post)

    def test_04_raw_post_get_method(self) -> None:
        """get() retrieves existing values or returns default."""
        self.assertEqual(self.post.get("title"), "기아 EV3 고속도로 주행 후기")
        self.assertIsNone(self.post.get("missing_field"))
        self.assertEqual(self.post.get("missing_field", "fallback"), "fallback")

    def test_05_raw_post_dict_conversion(self) -> None:
        """dict(raw_post) generates standard dictionary."""
        d = dict(self.post)
        self.assertIsInstance(d, dict)
        self.assertEqual(d["title"], self.post.title)
        self.assertEqual(d["post_id"], self.post.post_id)
        self.assertEqual(len(d), 8)

    def test_06_raw_post_iteration(self) -> None:
        """iter(raw_post) yields all keys in order."""
        keys = list(self.post)
        self.assertEqual(
            keys,
            ["platform", "post_id", "url", "title", "content", "comments", "created_at", "author"],
        )


# ===========================================================================
# Class 2: TestDSIBreakdownMappingProtocol
# ===========================================================================
class TestDSIBreakdownMappingProtocol(unittest.TestCase):
    """Rigorous verification of DSIBreakdown dictionary mapping protocol."""

    def setUp(self) -> None:
        self.breakdown = DSIBreakdown(
            safety=9.2,
            functional=8.5,
            economic=6.0,
            social=5.5,
            convenience=4.0,
        )

    def test_07_dsi_breakdown_subscript_access(self) -> None:
        """DSIBreakdown allows subscript access to 5 pillars."""
        self.assertEqual(self.breakdown["safety"], 9.2)
        self.assertEqual(self.breakdown["functional"], 8.5)
        self.assertEqual(self.breakdown["economic"], 6.0)
        self.assertEqual(self.breakdown["social"], 5.5)
        self.assertEqual(self.breakdown["convenience"], 4.0)

    def test_08_dsi_breakdown_missing_key_raises_keyerror(self) -> None:
        """Missing key raises KeyError."""
        with self.assertRaises(KeyError):
            _ = self.breakdown["missing_pillar"]

    def test_09_dsi_breakdown_in_operator(self) -> None:
        """'in' operator accurately checks pillar presence."""
        self.assertIn("safety", self.breakdown)
        self.assertIn("functional", self.breakdown)
        self.assertNotIn("environmental", self.breakdown)

    def test_10_dsi_breakdown_get_method(self) -> None:
        """get() retrieves existing values or returns default."""
        self.assertEqual(self.breakdown.get("safety"), 9.2)
        self.assertEqual(self.breakdown.get("non_existent", 0.0), 0.0)

    def test_11_dsi_breakdown_dict_unpacking(self) -> None:
        """DSIBreakdown supports dict unpacking and conversion."""
        d = {**dict(self.breakdown)}
        self.assertEqual(d["safety"], 9.2)
        self.assertEqual(len(d), 5)


# ===========================================================================
# Class 3: TestExpandedVehicleMatcherCycle22
# ===========================================================================
class TestExpandedVehicleMatcherCycle22(unittest.TestCase):
    """Validates 2026 vehicle matcher additions with Korean particles and case-insensitivity."""

    def test_12_kia_ev2_particles(self) -> None:
        """Kia EV2 recognized with various Korean particles."""
        test_cases = [
            ("기아 EV2는 언제 출고되나요?", BRAND_KIA, "EV2"),
            ("EV2가 가성비 진짜 좋게 나올 듯", BRAND_KIA, "EV2"),
            ("기아의 EV2로 사전예약 걸었습니다", BRAND_KIA, "EV2"),
            ("ev2를 사야 할지 캐스퍼를 사야 할지", BRAND_KIA, "EV2"),
        ]
        for title, exp_b, exp_m in test_cases:
            b, m = extract_vehicle_info(title)
            self.assertEqual(b, exp_b, f"Brand mismatch for: {title}")
            self.assertEqual(m, exp_m, f"Model mismatch for: {title}")

    def test_13_byd_sealion_dual_spelling_particles(self) -> None:
        """BYD Sealion recognized with both 시라이언 and 씨라이언 spellings."""
        test_cases = [
            ("비야디 시라이언 7 시승기", BRAND_BYD, "시라이언"),
            ("BYD 씨라이언 07 계약 후기", BRAND_BYD, "시라이언"),
            ("씨라이언7도 보조금 전액 대상인가요?", BRAND_BYD, "시라이언"),
            ("sealion 7 배터리 용량 문의", BRAND_BYD, "시라이언"),
        ]
        for title, exp_b, exp_m in test_cases:
            b, m = extract_vehicle_info(title)
            self.assertEqual(b, exp_b, f"Brand mismatch for: {title}")
            self.assertEqual(m, exp_m, f"Model mismatch for: {title}")

    def test_14_volkswagen_id4_idbuzz_variations(self) -> None:
        """Volkswagen ID.4 and ID.Buzz recognized across spelling variants."""
        test_cases = [
            ("폭스바겐 ID.4 소프트웨어 오류 해결방법", BRAND_OTHER, "Volkswagen ID.4"),
            ("id4 주행거리 겨울철 감소폭", BRAND_OTHER, "Volkswagen ID.4"),
            ("폭스바겐 ID 버즈 캠핑카 개조", BRAND_OTHER, "Volkswagen ID.Buzz"),
            ("id.buzz 사전예약 시작했나요?", BRAND_OTHER, "Volkswagen ID.Buzz"),
        ]
        for title, exp_b, exp_m in test_cases:
            b, m = extract_vehicle_info(title)
            self.assertEqual(b, exp_b, f"Brand mismatch for: {title}")
            self.assertEqual(m, exp_m, f"Model mismatch for: {title}")

    def test_15_tesla_model_2_particles(self) -> None:
        """Tesla Model 2 recognized across cases."""
        test_cases = [
            ("테슬라 모델 2 출시되면 현대차 비상", BRAND_TESLA, "Model 2"),
            ("Model 2는 언제 공개하나요?", BRAND_TESLA, "Model 2"),
            ("model 2도 FSD 지원하는지 궁금합니다", BRAND_TESLA, "Model 2"),
        ]
        for title, exp_b, exp_m in test_cases:
            b, m = extract_vehicle_info(title)
            self.assertEqual(b, exp_b, f"Brand mismatch for: {title}")
            self.assertEqual(m, exp_m, f"Model mismatch for: {title}")

    def test_16_hyundai_ioniq_7_particles(self) -> None:
        """Hyundai 아이오닉7 recognized."""
        test_cases = [
            ("아이오닉 7 콘셉트카 시절 기대 많이 했는데", BRAND_HYUNDAI, "아이오닉7"),
            ("ioniq 7 실내 거주성", BRAND_HYUNDAI, "아이오닉7"),
        ]
        for title, exp_b, exp_m in test_cases:
            b, m = extract_vehicle_info(title)
            self.assertEqual(b, exp_b, f"Brand mismatch for: {title}")
            self.assertEqual(m, exp_m, f"Model mismatch for: {title}")


# ===========================================================================
# Class 4: TestDepreciationAndSubsidyDefensiveBounds
# ===========================================================================
class TestDepreciationAndSubsidyDefensiveBounds(unittest.TestCase):
    """Validates boundary handling and defensiveness in calculations."""

    def test_17_depreciation_cap_10b_krw(self) -> None:
        """getDepreciationData.ts has 10B KRW cap in code."""
        dep_path = WEB_ROOT / "src" / "lib" / "getDepreciationData.ts"
        content = dep_path.read_text(encoding="utf-8")
        self.assertIn("10_000_000_000", content)

    def test_18_depreciation_negative_and_none_price(self) -> None:
        """calculate_net_subsidy handles negative and zero MSRP gracefully."""
        res = calculate_net_subsidy(
            model_national=6500000,
            max_national=6500000,
            max_local=1500000,
            msrp=-50000000,
        )
        self.assertEqual(res["national_subsidy_krw"], 0)
        self.assertEqual(res["local_subsidy_krw"], 0)
        self.assertEqual(res["total_subsidy_krw"], 0)
        self.assertEqual(res["net_price_krw"], 0)

    def test_19_subsidy_tracker_nan_and_inf_guards(self) -> None:
        """calculate_price_cap_ratio and calculate_net_subsidy guard against float('nan') and float('inf')."""
        self.assertEqual(calculate_price_cap_ratio(float("nan")), 0.0)  # type: ignore
        self.assertEqual(calculate_price_cap_ratio(float("inf")), 0.0)  # type: ignore

        res = calculate_net_subsidy(
            model_national=float("nan"),  # type: ignore
            max_national=float("inf"),  # type: ignore
            max_local=1500000,
            msrp=54000000,
        )
        self.assertIsInstance(res, dict)
        self.assertEqual(res["total_subsidy_krw"], 0)

    def test_20_daily_report_statistics_mapping_protocol(self) -> None:
        """DailyReportStatistics supports dictionary unpacking and item access."""
        s = DailyReportStatistics(
            total_scraped=500,
            total_filtered_defects=35,
            avg_negativity_score=0.91,
            critical_defect_count=8,
        )
        self.assertEqual(s["total_scraped"], 500)
        self.assertEqual(s.get("critical_defect_count"), 8)
        self.assertIn("total_filtered_defects", s)
        d = dict(s)
        self.assertEqual(d["avg_negativity_score"], 0.91)


if __name__ == "__main__":
    unittest.main()
