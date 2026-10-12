"""
tests/test_sync14_adversarial_challenger.py - Cycle 14 Adversarial Challenger Suite.

Empirical verification suite authored by sync14_challenger_backend_tests_w3.
Stress-tests:
1. NaN / Inf / None / Overflow inputs in ReportGenerator.generate_subsidy_briefing
2. Non-dict objects (RawPost, ComplaintRecord, duck-typed classes, mixed lists) in
   filter_raw_posts and generate_defect_briefing
3. Arbitrary, novel, unicode, and disjoint vehicle categories in subsidy_baseline.build_initial_baseline
"""

from __future__ import annotations

import math
from pathlib import Path
import sys
import unittest
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from filters.defect_filter import ContextualDefectFilter
from models.complaint import ComplaintRecord, RawPost
from tracker.defect_tracker import DefectTracker
from tracker.report_generator import ReportGenerator
import tracker.subsidy_baseline as subsidy_baseline
from tracker.subsidy_models import (
    AlertThresholdConfig,
    CategoryMetrics,
    MunicipalityMetrics,
    NationwideSummary,
    RegionRecord,
    SubsidyMetadata,
    SubsidyPayload,
)


class DummyCustomPost:
    """Arbitrary duck-typed object that is neither dict nor RawPost."""

    def __init__(self, post_id: str, title: str, content: str, platform: str = "custom_forum"):
        self.post_id = post_id
        self.title = title
        self.content = content
        self.platform = platform
        self.url = f"https://custom.example.com/{post_id}"
        self.comments = ["댓글 1", "댓글 2"]
        self.created_at = "2026-10-12T19:00:00Z"
        self.author = "custom_tester"


class DummyMinimalPost:
    """Duck-typed object with minimal attributes."""

    def __init__(self, id_val: str, text: str):
        self.id = id_val
        self.title = text


class TestAdversarialSubsidyBriefingNanInf(unittest.TestCase):
    """Stress tests ReportGenerator.generate_subsidy_briefing against extreme numeric inputs."""

    def setUp(self) -> None:
        self.generator = ReportGenerator()

    def test_all_metrics_nan_inf_none_in_summary_and_categories(self) -> None:
        """Briefing generator must handle all combinations of NaN, Inf, None, negative, and extreme integers."""
        extreme_values = [
            float("nan"),
            float("inf"),
            float("-inf"),
            None,
            -99999,
            10**18,
            "corrupted_string",
        ]

        for val in extreme_values:
            with self.subTest(val=val):
                cat_metric = CategoryMetrics(
                    announced_units=val,  # type: ignore[arg-type]
                    applied_units=val,  # type: ignore[arg-type]
                    delivered_units=val,  # type: ignore[arg-type]
                    remaining_units=val,  # type: ignore[arg-type]
                    depletion_rate=val,  # type: ignore[arg-type]
                    delivery_rate=val,  # type: ignore[arg-type]
                    status=val if isinstance(val, str) else "WARNING",  # type: ignore[arg-type]
                    max_local_subsidy_krw=0,
                    max_total_subsidy_krw=0,
                    total_budget_krw=val if isinstance(val, (int, float)) else 0,  # type: ignore[arg-type]
                    remaining_budget_krw=val if isinstance(val, (int, float)) else 0,  # type: ignore[arg-type]
                )

                summary = NationwideSummary(
                    total_announced_units=val,  # type: ignore[arg-type]
                    total_applied_units=val,  # type: ignore[arg-type]
                    total_delivered_units=val,  # type: ignore[arg-type]
                    total_remaining_units=val,  # type: ignore[arg-type]
                    nationwide_depletion_rate=val,  # type: ignore[arg-type]
                    total_budget_billion_krw=val,  # type: ignore[arg-type]
                    disbursed_budget_billion_krw=val,  # type: ignore[arg-type]
                    category_totals={
                        "passenger": cat_metric,
                        "commercial": cat_metric,
                        "bus": cat_metric,
                    },
                    alert_region_counts={"critical": 1, "warning": 1, "available": 0},
                )

                reg_critical = RegionRecord.from_dict({
                    "region_id": "KR-11",
                    "name_ko": "서울특별시",
                    "name_en": "Seoul",
                    "iso_code": "KR-11",
                    "overall_status": "CRITICAL",
                    "overall_depletion_rate": val,
                    "categories": {"passenger": cat_metric},
                    "municipalities": [],
                })

                reg_warning = RegionRecord.from_dict({
                    "region_id": "KR-26",
                    "name_ko": "부산광역시",
                    "name_en": "Busan",
                    "iso_code": "KR-26",
                    "overall_status": "WARNING",
                    "overall_depletion_rate": val,
                    "categories": {"passenger": cat_metric},
                    "municipalities": [],
                })

                payload = SubsidyPayload(
                    metadata=SubsidyMetadata(
                        version="1.0.0",
                        generated_at="2026-10-12T19:00:00Z",
                        policy_year=2026,
                        data_sources=["환경부"],
                        total_regions_tracked=2,
                        total_municipalities_tracked=0,
                    ),
                    alert_thresholds={},
                    nationwide_summary=summary,
                    regions=[reg_critical, reg_warning],
                    popular_models_matrix=[],
                    historical_depletion_trajectory=[],
                )

                briefing = self.generator.generate_subsidy_briefing(payload)
                self.assertIsInstance(briefing, str)
                self.assertIn("전국 전기차 보조금 소진 현황 일일 종합 브리핑", briefing)
                self.assertIn("서울특별시", briefing)
                self.assertIn("부산광역시", briefing)

    def test_empty_regions_and_none_category_totals(self) -> None:
        """Briefing generator must handle empty region lists and empty category totals without crashing."""
        summary = NationwideSummary(
            total_announced_units=0,
            total_applied_units=0,
            total_delivered_units=0,
            total_remaining_units=0,
            nationwide_depletion_rate=0.0,
            total_budget_billion_krw=0.0,
            disbursed_budget_billion_krw=0.0,
            category_totals={},
            alert_region_counts={},
        )
        payload = SubsidyPayload(
            metadata=SubsidyMetadata(
                version="1.0.0",
                generated_at="2026-10-12T19:00:00Z",
                policy_year=2026,
                data_sources=[],
                total_regions_tracked=0,
                total_municipalities_tracked=0,
            ),
            alert_thresholds={},
            nationwide_summary=summary,
            regions=[],
            popular_models_matrix=[],
            historical_depletion_trajectory=[],
        )
        briefing = self.generator.generate_subsidy_briefing(payload)
        self.assertIsInstance(briefing, str)
        self.assertIn("현재 접수 마감된 긴급 지자체 없음", briefing)
        self.assertIn("경고 지역 없음", briefing)


class TestAdversarialNonDictObjectsInDefects(unittest.TestCase):
    """Stress tests filter_raw_posts and generate_defect_briefing with non-dict objects."""

    def setUp(self) -> None:
        self.generator = ReportGenerator()
        self.defect_tracker = DefectTracker(filter_engine=ContextualDefectFilter())

    def test_filter_raw_posts_polymorphic_inputs(self) -> None:
        """filter_raw_posts must seamlessly process RawPost, ComplaintRecord, custom classes, and dicts."""
        # 1. Authentic defect RawPost
        post_raw = RawPost(
            platform="dcinside",
            post_id="post_adv_1",
            url="https://gall.dcinside.com/mgallery/board/view/?id=car_new1&no=123",
            title="고속도로 주행 중 ICCU 경고등 뜨고 동력상실 시동 꺼짐",
            content="어제 현대 아이오닉5 몰고 가다가 퍽 소리와 함께 경고등 뜨고 시동 꺼짐. 진짜 긴급 견인 입고함.",
            comments=["위험했네요", "ICCU 교체 받으세요"],
            created_at="2026-10-12T18:00:00Z",
            author="tester1",
        )

        # 2. Authentic defect in dictionary form
        dict_raw = {
            "platform": "bobaedream",
            "post_id": "post_adv_2",
            "url": "https://www.bobaedream.co.kr/view?code=national&No=456",
            "title": "기아 EV6 배터리 팩 파손 충전 불가 ICCU 결함",
            "content": "EV6 주행 중 배터리 전원 차단되고 악셀 먹통됨. 서비스센터 가니 ICCU 터졌다고 함.",
            "comments": [],
            "created_at": "2026-10-12T18:05:00Z",
            "author": "tester2",
        }

        # 3. Authentic defect in custom duck-typed object form
        custom_raw = DummyCustomPost(
            post_id="post_adv_3",
            title="테슬라 모델Y OTA 업데이트 후 MCU 블랙아웃 벽돌 먹통",
            content="테슬라 모델Y 주행 중 네비 화면 꺼지고 MCU 블랙아웃 됨. 깜빡이 소리도 안 나고 먹통.",
        )

        # 4. Authentic defect in ComplaintRecord instance passed as raw post candidate
        record_as_post = ComplaintRecord(
            id="post_adv_4",
            source="clien",
            url="https://www.clien.net/service/board/cm_car/789",
            title="제네시스 GV60 전자식 기어 변속 불량 시동 꺼짐",
            author="tester4",
            created_at="2026-10-12T18:10:00Z",
            vehicle_brand="제네시스",
            vehicle_model="GV60",
            defect_category="SOFTWARE_ELECTRONICS",
            summary="기어 변속 먹통 및 시동 꺼짐",
            verbatim_quote="기어가 안 들어가서 긴급 출동 부름",
            severity_index=8.5,
            is_authentic_defect=True,
        )

        # 5. Minimal duck-typed object
        minimal_raw = DummyMinimalPost(
            id_val="post_adv_5",
            text="아이오닉 6 주행 중 배터리 방전 시동 꺼짐",
        )

        mixed_inputs = [post_raw, dict_raw, custom_raw, record_as_post, minimal_raw]
        filtered = self.defect_tracker.filter_raw_posts(mixed_inputs)

        self.assertIsInstance(filtered, list)
        # All authentic defects should be captured without raising exceptions
        self.assertGreaterEqual(len(filtered), 2)
        for r in filtered:
            self.assertTrue(getattr(r, "is_authentic_defect", False))

    def test_generate_defect_briefing_polymorphism_and_nan_severity(self) -> None:
        """generate_defect_briefing must seamlessly handle ComplaintRecord objects, dicts, and NaN/Inf severities."""
        rec_domain_1 = ComplaintRecord(
            id="cr_1",
            source="dcinside",
            url="https://example.com/1",
            title="아이오닉 5 ICCU 동력상실",
            author="driver1",
            created_at="2026-10-12T19:00:00Z",
            vehicle_brand="현대",
            vehicle_model="아이오닉 5",
            defect_category="BATTERY_CHARGING",
            summary="ICCU 파손",
            verbatim_quote="퍽 소리",
            severity_index=9.5,
            is_authentic_defect=True,
        )

        rec_domain_nan = ComplaintRecord(
            id="cr_nan",
            source="bobaedream",
            url="https://example.com/nan",
            title="EV9 조향각 센서 이상",
            author="driver2",
            created_at="2026-10-12T19:05:00Z",
            vehicle_brand="기아",
            vehicle_model="EV9",
            defect_category="CHASSIS_STEERING",
            summary="핸들 잠김",
            verbatim_quote="핸들 안 돌아감",
            severity_index=float("nan"),
            is_authentic_defect=True,
        )

        rec_dict = {
            "id": "cr_dict",
            "source": "clien",
            "url": "https://example.com/dict",
            "title": "Model 3 히트펌프 고장",
            "vehicle_brand": "테슬라",
            "vehicle_model": "Model 3",
            "defect_category": "THERMAL_HVAC",
            "severity_index": 7.5,
            "is_authentic_defect": True,
        }

        # 1. Pure list of ComplaintRecord instances
        briefing_pure = self.generator.generate_defect_briefing([rec_domain_1, rec_domain_nan])
        self.assertIn("아이오닉 5", briefing_pure)
        self.assertIn("BATTERY_CHARGING", briefing_pure)
        self.assertIn("CHASSIS_STEERING", briefing_pure)

        # 2. Mixed list of ComplaintRecord and dict
        briefing_mixed = self.generator.generate_defect_briefing([rec_domain_1, rec_domain_nan, rec_dict])
        self.assertIn("총 수집/분류 결함 건수**: 3건", briefing_mixed)
        self.assertIn("테슬라 Model 3", briefing_mixed)

        # 3. Payload dict with statistics containing NaN and Inf avg_negativity_score
        payload_dict = {
            "reports": [rec_domain_1, rec_dict],
            "statistics": {
                "critical_defect_count": float("nan"),  # Should fallback safely
                "avg_negativity_score": float("inf"),  # Should format cleanly
            },
            "generated_at": "2026-10-12T19:00:00Z",
        }
        briefing_dict = self.generator.generate_defect_briefing(payload_dict)
        self.assertIn("대한민국 EV 실생활 결함", briefing_dict)


class TestAdversarialBaselineArbitraryCategories(unittest.TestCase):
    """Stress tests subsidy_baseline.build_initial_baseline with arbitrary, novel vehicle categories."""

    def test_arbitrary_novel_and_disjoint_categories(self) -> None:
        """build_initial_baseline must handle arbitrary and disjoint vehicle categories without KeyError."""
        orig_fn = subsidy_baseline.build_baseline_regions

        try:
            # Construct synthetic baseline regions with diverse custom categories
            synthetic_regions = orig_fn()

            # Add arbitrary novel categories
            # Region 0 gets two novel categories
            synthetic_regions[0].categories["two_wheeler"] = subsidy_baseline._calc_cat(100, 80, 50, 100)
            synthetic_regions[0].categories["electric_truck"] = subsidy_baseline._calc_cat(50, 45, 40, 500)

            # Region 1 gets different novel categories
            synthetic_regions[1].categories["hydrogen_special"] = subsidy_baseline._calc_cat(20, 10, 5, 2000)
            synthetic_regions[1].categories["micro_ev"] = subsidy_baseline._calc_cat(30, 25, 20, 50)

            # Region 2 gets a unicode category and symbol category
            synthetic_regions[2].categories["특수목적_구급차"] = subsidy_baseline._calc_cat(10, 5, 2, 1500)
            synthetic_regions[2].categories["EV-VTOL"] = subsidy_baseline._calc_cat(5, 5, 1, 5000)

            subsidy_baseline.build_baseline_regions = lambda: synthetic_regions

            payload = subsidy_baseline.build_initial_baseline()
            cat_totals = payload.nationwide_summary.category_totals

            # All standard categories must still exist
            self.assertIn("passenger", cat_totals)
            self.assertIn("commercial", cat_totals)
            self.assertIn("bus", cat_totals)

            # All novel categories must be aggregated dynamically
            self.assertIn("two_wheeler", cat_totals)
            self.assertIn("electric_truck", cat_totals)
            self.assertIn("hydrogen_special", cat_totals)
            self.assertIn("micro_ev", cat_totals)
            self.assertIn("특수목적_구급차", cat_totals)
            self.assertIn("EV-VTOL", cat_totals)

            # Metrics verification
            two_wheeler = cat_totals["two_wheeler"]
            self.assertEqual(two_wheeler.announced_units, 100)
            self.assertEqual(two_wheeler.applied_units, 80)
            self.assertEqual(two_wheeler.depletion_rate, 80.0)

            ev_vtol = cat_totals["EV-VTOL"]
            self.assertEqual(ev_vtol.announced_units, 5)
            self.assertEqual(ev_vtol.applied_units, 5)
            self.assertEqual(ev_vtol.depletion_rate, 100.0)
            self.assertEqual(ev_vtol.status, "DEPLETED")

            # Check that total announced reflects the additions
            self.assertGreater(payload.nationwide_summary.total_announced_units, 0)
        finally:
            subsidy_baseline.build_baseline_regions = orig_fn

    def test_hundred_arbitrary_categories_stress(self) -> None:
        """build_initial_baseline must scale to 100 arbitrary categories across all regions without crashing."""
        orig_fn = subsidy_baseline.build_baseline_regions

        try:
            regions = orig_fn()
            # Distribute 100 custom categories across the 17 regions
            for i in range(100):
                cat_name = f"custom_vehicle_class_{i:03d}"
                region_idx = i % len(regions)
                regions[region_idx].categories[cat_name] = subsidy_baseline._calc_cat(
                    announced=10 + i,
                    applied=5 + (i // 2),
                    delivered=2,
                    max_local=100 + i,
                )

            subsidy_baseline.build_baseline_regions = lambda: regions
            payload = subsidy_baseline.build_initial_baseline()
            cat_totals = payload.nationwide_summary.category_totals

            self.assertEqual(len(cat_totals), 3 + 100)
            for i in range(100):
                cat_name = f"custom_vehicle_class_{i:03d}"
                self.assertIn(cat_name, cat_totals)
                self.assertEqual(cat_totals[cat_name].announced_units, 10 + i)
        finally:
            subsidy_baseline.build_baseline_regions = orig_fn


if __name__ == "__main__":
    unittest.main()
