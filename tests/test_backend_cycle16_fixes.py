"""
Cycle 16 Wave 2 Backend Proactive Remediation Regression Tests.

Validates the 4 proactive backend fixes:
1. Dict duck-typing for municipalities in SubsidyTracker.update_region_metrics().
2. BaseCrawler.ensure_warm_up() signature alignment and boolean URL type guards.
3. Dict duck-typing in ReportGenerator.generate_subsidy_briefing() for metadata and nationwide summary.
4. ComplaintRecord robustness against None, NaN, and Inf numeric attributes.
"""

import math
import unittest
from types import SimpleNamespace
from typing import Any, Dict

from crawlers.base_crawler import BaseCrawler
from models.complaint import ComplaintRecord
from tracker.report_generator import ReportGenerator
from tracker.subsidy_models import MunicipalityMetrics, RegionRecord
from tracker.subsidy_tracker import SubsidyTracker
from utils.http_client import SafeHttpClient


class TestBackendCycle16Fixes(unittest.TestCase):
    """Regression test suite for Cycle 16 backend proactive remediations."""

    def setUp(self) -> None:
        self.tracker = SubsidyTracker()
        self.generator = ReportGenerator()

    # -------------------------------------------------------------------------
    # Fix 1: Dict Duck-Typing for Municipalities in SubsidyTracker
    # -------------------------------------------------------------------------
    def test_update_region_metrics_with_dict_municipalities(self) -> None:
        """SubsidyTracker.update_region_metrics correctly calculates metrics for dict municipalities."""
        region = RegionRecord(
            region_id="KR-11",
            name_ko="서울",
            municipalities=[
                {
                    "name_ko": "강남구",
                    "announced_units": 100,
                    "applied_units": 60,
                    "delivered_units": 40,
                },
                {
                    "name_ko": "서초구",
                    "announced_units": 50,
                    "applied_units": 50,
                },
            ],
        )

        res = self.tracker.update_region_metrics(region)
        self.assertIs(res, region)
        self.assertEqual(len(res.municipalities), 2)

        gangnam = res.municipalities[0]
        self.assertIsInstance(gangnam, dict)
        self.assertEqual(gangnam["announced_units"], 100)
        self.assertEqual(gangnam["applied_units"], 60)
        self.assertEqual(gangnam["delivered_units"], 40)
        self.assertEqual(gangnam["remaining_units"], 40)
        self.assertEqual(gangnam["depletion_rate"], 60.0)
        self.assertEqual(gangnam["status"], "CAUTION")

        seocho = res.municipalities[1]
        self.assertIsInstance(seocho, dict)
        self.assertEqual(seocho["announced_units"], 50)
        self.assertEqual(seocho["applied_units"], 50)
        self.assertEqual(seocho["remaining_units"], 0)
        self.assertEqual(seocho["depletion_rate"], 100.0)
        self.assertEqual(seocho["status"], "DEPLETED")

    def test_update_region_metrics_with_dataclass_municipalities(self) -> None:
        """SubsidyTracker.update_region_metrics preserves existing behavior for MunicipalityMetrics."""
        muni = MunicipalityMetrics(
            name_ko="수원시",
            announced_units=200,
            applied_units=150,
            delivered_units=100,
        )
        region = RegionRecord(
            region_id="KR-41",
            name_ko="경기",
            municipalities=[muni],
        )

        res = self.tracker.update_region_metrics(region)
        self.assertEqual(res.municipalities[0].remaining_units, 50)
        self.assertEqual(res.municipalities[0].depletion_rate, 75.0)
        self.assertEqual(res.municipalities[0].status, "CAUTION")

    def test_calculate_category_metrics_nan_inf_safety(self) -> None:
        """SubsidyTracker.calculate_category_metrics safely sanitizes NaN and Inf inputs."""
        metrics = self.tracker.calculate_category_metrics(
            announced=float("nan"),  # type: ignore[arg-type]
            applied=100,
            delivered=float("inf"),  # type: ignore[arg-type]
            max_local_subsidy=4000000,
        )
        self.assertEqual(metrics.announced_units, 0)
        self.assertEqual(metrics.applied_units, 100)
        self.assertEqual(metrics.delivered_units, 0)
        self.assertIsInstance(metrics.total_budget_krw, int)

    # -------------------------------------------------------------------------
    # Fix 2: BaseCrawler ensure_warm_up Signature Alignment & Type Checking
    # -------------------------------------------------------------------------
    def test_base_crawler_ensure_warm_up_variants(self) -> None:
        """BaseCrawler.ensure_warm_up handles keyword args, boolean URLs, and zero-args safely."""
        class MockHttpClient:
            def __init__(self) -> None:
                self.warmed_urls = []

            def warm_up_session(self, url: str) -> None:
                self.warmed_urls.append(url)

        class ConcreteCrawler(BaseCrawler):
            def parse_post_detail(self, html_content: str, post_url: str, **kwargs: Any) -> Dict[str, Any]:
                return {}

        mock_client = MockHttpClient()
        crawler = ConcreteCrawler(client=mock_client)  # type: ignore[arg-type]

        # 1. Zero arguments
        crawler.ensure_warm_up()
        self.assertFalse(crawler._warmed_up)
        self.assertEqual(len(mock_client.warmed_urls), 0)

        # 2. force=True keyword argument without url
        crawler.ensure_warm_up(force=True)
        self.assertFalse(crawler._warmed_up)
        self.assertEqual(len(mock_client.warmed_urls), 0)

        # 3. Positional boolean True should not pollute URL or call warm_up_session with 'True'
        crawler.ensure_warm_up(True)
        self.assertFalse(crawler._warmed_up)
        self.assertEqual(len(mock_client.warmed_urls), 0)

        # 4. Valid base URL warms up successfully
        crawler.ensure_warm_up("https://example.com")
        self.assertTrue(crawler._warmed_up)
        self.assertEqual(mock_client.warmed_urls, ["https://example.com"])

        # 5. Subsequent call without force does not re-warm
        crawler.ensure_warm_up("https://example.com/other")
        self.assertEqual(len(mock_client.warmed_urls), 1)

        # 6. Subsequent call with force=True re-warms
        crawler.ensure_warm_up("https://example.com/forced", force=True)
        self.assertEqual(mock_client.warmed_urls, ["https://example.com", "https://example.com/forced"])

    # -------------------------------------------------------------------------
    # Fix 3: Dict Duck-Typing in ReportGenerator.generate_subsidy_briefing
    # -------------------------------------------------------------------------
    def test_generate_subsidy_briefing_with_dict_metadata_and_summary(self) -> None:
        """ReportGenerator.generate_subsidy_briefing extracts KPI metrics from dictionary payloads."""
        payload = SimpleNamespace(
            metadata={"generated_at": "2026-10-24T05:00:00Z"},
            regions=[
                {
                    "name_ko": "제주",
                    "overall_depletion_rate": 99.0,
                    "overall_status": "DEPLETED",
                    "categories": {
                        "passenger": {"remaining_units": 40}
                    },
                },
                {
                    "name_ko": "강원",
                    "overall_depletion_rate": 88.0,
                    "overall_status": "WARNING",
                    "categories": {
                        "passenger": {"remaining_units": 500}
                    },
                },
            ],
            nationwide_summary={
                "total_announced_units": 148510,
                "total_applied_units": 132766,
                "nationwide_depletion_rate": 89.4,
                "total_budget_billion_krw": 2105.1,
                "disbursed_budget_billion_krw": 1893.4,
                "category_totals": {
                    "passenger": {
                        "announced_units": 110400,
                        "applied_units": 97035,
                        "depletion_rate": 87.9,
                        "remaining_units": 13365,
                        "status": "CAUTION",
                    }
                },
            },
        )

        briefing = self.generator.generate_subsidy_briefing(payload)
        self.assertIn("2026-10-24T05:00:00Z", briefing)
        self.assertIn("89.4%", briefing)
        self.assertIn("148,510대", briefing)
        self.assertIn("132,766대", briefing)
        self.assertIn("1,893억 원", briefing)
        self.assertIn("2,105억 원", briefing)
        self.assertIn("제주 (99.0%, 잔여: 40대)", briefing)
        self.assertIn("강원 (88.0%, 잔여: 500대)", briefing)
        self.assertIn("110,400대", briefing)
        self.assertIn("97,035대", briefing)

    # -------------------------------------------------------------------------
    # Fix 4: ComplaintRecord Robustness Against None, NaN, and Inf Scores
    # -------------------------------------------------------------------------
    def test_complaint_record_none_and_nan_resilience(self) -> None:
        """ComplaintRecord severity_tier, sentiment_tier, and serializers handle None and NaN."""
        rec = ComplaintRecord(
            id="dc_test_001",
            source="dcinside",
            url="https://gall.dcinside.com/mgallery/board/view/?id=car_new1&no=999999",
            title="테스트 결함 글",
            author="익명",
            created_at="2026-10-24 12:00:00",
            vehicle_brand="Hyundai",
            vehicle_model="Ioniq 5",
            defect_category="BATTERY_CHARGING",
            summary="배터리 충전 테스트 요약",
            verbatim_quote="충전 중 이상 경고등이 점등되었습니다.",
            sentiment_polarity=None,
            negativity_score=None,
            severity_index=None,
        )

        # 1. Properties with None
        self.assertEqual(rec.severity_tier, "LOW")
        self.assertEqual(rec.sentiment_tier, "NEUTRAL")

        # 2. to_dict with None
        d = rec.to_dict()
        self.assertEqual(d["sentiment_polarity"], 0.0)
        self.assertEqual(d["negativity_score"], 0.0)
        self.assertEqual(d["severity_index"], 0.0)

        # 3. to_admin_report_dict with None
        admin_d = rec.to_admin_report_dict()
        self.assertEqual(admin_d["severity"], "LOW")
        self.assertEqual(admin_d["sentiment_tier"], "NEUTRAL")
        self.assertEqual(admin_d["sentiment_score"], 0.0)
        self.assertEqual(admin_d["sentiment_polarity"], 0.0)
        self.assertEqual(admin_d["negativity_score"], 0.0)
        self.assertEqual(admin_d["severity_index"], 0.0)

        # 4. Properties with NaN and Inf
        rec_nan = ComplaintRecord(
            id="dc_test_002",
            source="dcinside",
            url="https://gall.dcinside.com/mgallery/board/view/?id=car_new1&no=999998",
            title="NaN 테스트",
            author="익명",
            created_at="2026-10-24",
            vehicle_brand="Kia",
            vehicle_model="EV6",
            defect_category="DRIVING_POWERTRAIN",
            summary="주행 테스트",
            verbatim_quote="모터 진동 발생",
            sentiment_polarity=float("nan"),
            negativity_score=float("inf"),
            severity_index=float("nan"),
        )
        self.assertEqual(rec_nan.severity_tier, "LOW")
        self.assertEqual(rec_nan.sentiment_tier, "NEUTRAL")
        admin_nan = rec_nan.to_admin_report_dict()
        self.assertEqual(admin_nan["sentiment_score"], 0.0)
        self.assertEqual(admin_nan["sentiment_polarity"], 0.0)
        self.assertEqual(admin_nan["severity_index"], 0.0)


if __name__ == "__main__":
    unittest.main()
