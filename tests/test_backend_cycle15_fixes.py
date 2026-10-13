"""tests/test_backend_cycle15_fixes.py - Cycle 15 Proactive Backend Fixes Test Suite.

Comprehensive verification of Cycle 15 proactive backend remediations:
1. crawlers/bobaedream.py & crawlers/dcinside.py:
   - ensure_warm_up() signature parity with BaseCrawler (base_url: Optional[str] = None, force: bool = False).
   - Call compatibility with 0 arguments, positional string, keyword args, and bool positional arg.
   - Correct delegation to SafeHttpClient.warm_up_session() and polymorphic BaseCrawler compliance.
2. tracker/subsidy_tracker.py:
   - compute_nationwide_summary() resilience against float NaN, positive/negative Inf, None, and corrupt values.
   - Handling of plain dictionary category metrics (dict duck typing) alongside CategoryMetrics domain objects.
   - Guarantee that returned NationwideSummary metrics are non-negative, finite, and never throw exceptions.
3. models/complaint.py:
   - ComplaintRecord.date_str cleanly parses dot-separated ('YYYY.MM.DD') and slash-separated ('YYYY/MM/DD') dates.
   - Preservation of historical timestamps without improperly defaulting to today's date.
   - Robust fallback to today's date for corrupt/missing timestamps.
4. tracker/defect_tracker.py:
   - DefectTracker.get_statistics() ensures 'category_distribution' is always present when reading cached files.
   - Handles fallback from top_defect_categories and raw reports list.
   - Zero-crash protection against KeyError for downstream consumers.
"""

from __future__ import annotations

import inspect
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

# 1. Crawler imports
from crawlers.base_crawler import BaseCrawler
from crawlers.bobaedream import BobaeDreamCrawler, BOBAE_BASE_URL
from crawlers.dcinside import DCInsideCrawler, DC_BASE_URL

# Provide alias compatibility if needed
BobaedreamCrawler = BobaeDreamCrawler

# 2. Subsidy tracker imports
from tracker.subsidy_tracker import SubsidyTracker
from tracker.subsidy_models import RegionRecord, CategoryMetrics
from tracker.models.summary_model import NationwideSummary

# 3. Complaint record imports
from models.complaint import ComplaintRecord

# 4. Defect tracker imports
from tracker.defect_tracker import DefectTracker


# ==============================================================================
# Suite 1: Crawler ensure_warm_up Signature & Call Compatibility
# ==============================================================================

class TestCrawlerWarmUpCompatibility(unittest.TestCase):
    """Verifies ensure_warm_up signature parity and invocation compatibility on community crawlers."""

    def test_bobaedream_crawler_inheritance_and_signature(self) -> None:
        """BobaeDreamCrawler inherits from BaseCrawler and supports base_url and force parameters."""
        self.assertTrue(issubclass(BobaeDreamCrawler, BaseCrawler))
        sig = inspect.signature(BobaeDreamCrawler.ensure_warm_up)
        params = list(sig.parameters.keys())
        # Must accept self, and at least base_url and force (or arbitrary args)
        self.assertIn("self", params)
        self.assertIn("base_url", params)
        self.assertIn("force", params)

    def test_dcinside_crawler_inheritance_and_signature(self) -> None:
        """DCInsideCrawler inherits from BaseCrawler and supports base_url and force parameters."""
        self.assertTrue(issubclass(DCInsideCrawler, BaseCrawler))
        sig = inspect.signature(DCInsideCrawler.ensure_warm_up)
        params = list(sig.parameters.keys())
        self.assertIn("self", params)
        self.assertIn("base_url", params)
        self.assertIn("force", params)

    def test_bobaedream_warm_up_call_variants_without_type_error(self) -> None:
        """BobaeDreamCrawler.ensure_warm_up executes without TypeError across all calling conventions."""
        mock_client = MagicMock()
        crawler = BobaeDreamCrawler(client=mock_client)

        # 1. Call with zero arguments (default)
        crawler.ensure_warm_up()
        mock_client.warm_up_session.assert_called_with(BOBAE_BASE_URL)
        self.assertTrue(crawler._warmed_up)

        # 2. Repeated call when already warmed up should NOT call warm_up_session again
        mock_client.warm_up_session.reset_mock()
        crawler.ensure_warm_up()
        mock_client.warm_up_session.assert_not_called()

        # 3. Call with force=True keyword argument should re-warm session
        crawler.ensure_warm_up(force=True)
        mock_client.warm_up_session.assert_called_with(BOBAE_BASE_URL)

        # 4. Call with custom base_url string positional argument
        mock_client.warm_up_session.reset_mock()
        crawler.ensure_warm_up("https://custom.bobaedream.co.kr", force=True)
        mock_client.warm_up_session.assert_called_with("https://custom.bobaedream.co.kr")

        # 5. Call with bool positional argument (backward compatibility for force as first positional)
        mock_client.warm_up_session.reset_mock()
        crawler.ensure_warm_up(True)
        mock_client.warm_up_session.assert_called_with(BOBAE_BASE_URL)

    def test_dcinside_warm_up_call_variants_without_type_error(self) -> None:
        """DCInsideCrawler.ensure_warm_up executes without TypeError across all calling conventions."""
        mock_client = MagicMock()
        crawler = DCInsideCrawler(client=mock_client)

        # 1. Call with zero arguments (default)
        crawler.ensure_warm_up()
        mock_client.warm_up_session.assert_called_with(DC_BASE_URL)
        self.assertTrue(crawler._warmed_up)

        # 2. Repeated call when already warmed up should NOT call warm_up_session again
        mock_client.warm_up_session.reset_mock()
        crawler.ensure_warm_up()
        mock_client.warm_up_session.assert_not_called()

        # 3. Call with force=True keyword argument should re-warm session
        crawler.ensure_warm_up(force=True)
        mock_client.warm_up_session.assert_called_with(DC_BASE_URL)

        # 4. Call with custom base_url string positional argument
        mock_client.warm_up_session.reset_mock()
        crawler.ensure_warm_up("https://custom.dcinside.com", force=True)
        mock_client.warm_up_session.assert_called_with("https://custom.dcinside.com")

        # 5. Call with bool positional argument
        mock_client.warm_up_session.reset_mock()
        crawler.ensure_warm_up(True)
        mock_client.warm_up_session.assert_called_with(DC_BASE_URL)

    def test_crawler_polymorphic_compatibility_with_base_crawler(self) -> None:
        """Demonstrates polymorphism where BaseCrawler receiver accepts both crawler instances."""
        def polymorphic_runner(c: BaseCrawler, url: str) -> None:
            c.ensure_warm_up()
            c.ensure_warm_up(url)
            c.ensure_warm_up(base_url=url, force=True)

        mock_bobae_client = MagicMock()
        mock_dc_client = MagicMock()
        b_crawler = BobaeDreamCrawler(client=mock_bobae_client)
        d_crawler = DCInsideCrawler(client=mock_dc_client)

        polymorphic_runner(b_crawler, "https://test.bobaedream.co.kr")
        polymorphic_runner(d_crawler, "https://test.dcinside.com")

        self.assertTrue(mock_bobae_client.warm_up_session.called)
        self.assertTrue(mock_dc_client.warm_up_session.called)

    def test_base_crawler_fetch_post_and_warm_up_delegation(self) -> None:
        """Calling ensure_warm_up with base_url as implemented by BaseCrawler does not crash subclasses."""
        mock_client = MagicMock()
        crawler = BobaeDreamCrawler(client=mock_client)
        BaseCrawler.ensure_warm_up(crawler, "https://www.bobaedream.co.kr")
        self.assertTrue(crawler._warmed_up)

        # Verify fetch_post triggers ensure_warm_up
        mock_client.get.return_value = (
            200,
            "<div class='bodyCont'>배터리 충전 이슈 상세 본문 내용입니다.</div>",
            {},
        )
        result = crawler.fetch_post(
            "https://www.bobaedream.co.kr/view?code=national&No=123",
            board_code="national",
            post_id="123",
        )
        self.assertIsInstance(result, dict)


# ==============================================================================
# Suite 2: compute_nationwide_summary Robustness & Type Safety
# ==============================================================================

class TestComputeNationwideSummaryRobustness(unittest.TestCase):
    """Verifies compute_nationwide_summary resilience against NaN, Inf, and dict metric structures."""

    def setUp(self) -> None:
        self.tracker = SubsidyTracker()

    def test_compute_nationwide_summary_with_nan_and_inf_category_metrics(self) -> None:
        """compute_nationwide_summary does not raise ValueError/OverflowError when given NaN and Inf values."""
        cat_nan = CategoryMetrics(
            announced_units=float("nan"),
            applied_units=float("nan"),
            delivered_units=float("nan"),
            remaining_units=0,
            depletion_rate=0.0,
            delivery_rate=0.0,
            status="HEALTHY",
            max_local_subsidy_krw=0,
            max_total_subsidy_krw=0,
            total_budget_krw=float("nan"),
            remaining_budget_krw=float("nan"),
        )
        cat_inf = CategoryMetrics(
            announced_units=float("inf"),
            applied_units=float("inf"),
            delivered_units=float("inf"),
            remaining_units=0,
            depletion_rate=0.0,
            delivery_rate=0.0,
            status="HEALTHY",
            max_local_subsidy_krw=0,
            max_total_subsidy_krw=0,
            total_budget_krw=float("inf"),
            remaining_budget_krw=float("inf"),
        )
        cat_neg_inf = CategoryMetrics(
            announced_units=-float("inf"),
            applied_units=-float("inf"),
            delivered_units=-float("inf"),
            remaining_units=0,
            depletion_rate=0.0,
            delivery_rate=0.0,
            status="HEALTHY",
            max_local_subsidy_krw=0,
            max_total_subsidy_krw=0,
            total_budget_krw=-float("inf"),
            remaining_budget_krw=-float("inf"),
        )

        r_nan = RegionRecord(region_id="r_nan", name_ko="NaN지역", categories={"passenger": cat_nan})
        r_inf = RegionRecord(region_id="r_inf", name_ko="Inf지역", categories={"commercial": cat_inf})
        r_neg_inf = RegionRecord(region_id="r_neg_inf", name_ko="NegInf지역", categories={"bus": cat_neg_inf})

        # Must execute cleanly without exception
        summary = self.tracker.compute_nationwide_summary([r_nan, r_inf, r_neg_inf])

        self.assertIsInstance(summary, NationwideSummary)
        # All aggregated counters must be non-negative finite numbers
        self.assertEqual(summary.total_announced_units, 0)
        self.assertEqual(summary.total_applied_units, 0)
        self.assertEqual(summary.total_delivered_units, 0)
        self.assertEqual(summary.total_remaining_units, 0)
        self.assertEqual(summary.nationwide_depletion_rate, 0.0)
        self.assertFalse(math.isnan(summary.total_budget_billion_krw))
        self.assertFalse(math.isinf(summary.total_budget_billion_krw))
        self.assertFalse(math.isnan(summary.disbursed_budget_billion_krw))
        self.assertFalse(math.isinf(summary.disbursed_budget_billion_krw))

    def test_compute_nationwide_summary_with_dictionary_categories(self) -> None:
        """compute_nationwide_summary handles plain dictionary metrics without AttributeError."""
        # When categories are raw dictionaries instead of CategoryMetrics domain objects
        r_dict = RegionRecord(
            region_id="r_dict",
            name_ko="딕셔너리지역",
            categories={
                "passenger": {
                    "announced_units": 1000,
                    "applied_units": 450,
                    "delivered_units": 300,
                    "total_budget_krw": 10_000_000_000,
                    "remaining_budget_krw": 5_500_000_000,
                },
                "commercial": {
                    "announced_units": "200",  # String number coercion
                    "applied_units": "50",
                    "delivered_units": "25",
                    "total_budget_krw": "2000000000",
                    "remaining_budget_krw": "1500000000",
                },
                "bus": {
                    "announced_units": None,
                    "applied_units": float("nan"),
                    "delivered_units": "corrupt_string",
                    "total_budget_krw": float("inf"),
                    "remaining_budget_krw": None,
                },
            },
        )

        summary = self.tracker.compute_nationwide_summary([r_dict])

        self.assertIsInstance(summary, NationwideSummary)
        self.assertEqual(summary.total_announced_units, 1200)
        self.assertEqual(summary.total_applied_units, 500)
        self.assertEqual(summary.total_delivered_units, 325)
        self.assertEqual(summary.total_remaining_units, 700)
        # 500 / 1200 * 100 = 41.7%
        self.assertEqual(summary.nationwide_depletion_rate, 41.7)
        self.assertGreaterEqual(summary.total_budget_billion_krw, 12.0)
        self.assertGreaterEqual(summary.disbursed_budget_billion_krw, 5.0)

    def test_compute_nationwide_summary_mixed_valid_and_adversarial_records(self) -> None:
        """Aggregates mixed valid, adversarial, and edge-case regions correctly."""
        valid_cat = CategoryMetrics(
            announced_units=500,
            applied_units=250,
            delivered_units=100,
            remaining_units=250,
            depletion_rate=50.0,
            delivery_rate=20.0,
            status="HEALTHY",
            max_local_subsidy_krw=5_000_000,
            max_total_subsidy_krw=10_000_000,
            total_budget_krw=5_000_000_000,
            remaining_budget_krw=2_500_000_000,
        )
        r_valid = RegionRecord(region_id="seoul", name_ko="서울특별시", categories={"passenger": valid_cat})

        r_adversarial = RegionRecord(
            region_id="adv",
            name_ko="변칙지역",
            categories={
                "passenger": {"announced_units": float("nan"), "applied_units": 100, "delivered_units": 50},
                "commercial": {"announced_units": -50, "applied_units": -10, "delivered_units": -5},
            },
        )

        summary = self.tracker.compute_nationwide_summary([r_valid, r_adversarial])

        self.assertEqual(summary.total_announced_units, 500)
        self.assertEqual(summary.total_applied_units, 350)
        self.assertEqual(summary.total_delivered_units, 150)
        self.assertEqual(summary.total_remaining_units, 150)
        # 350 / 500 * 100 = 70.0%
        self.assertEqual(summary.nationwide_depletion_rate, 70.0)

    def test_compute_nationwide_summary_empty_inputs(self) -> None:
        """compute_nationwide_summary returns zero-initialized summary on empty list or dict."""
        sum_list = self.tracker.compute_nationwide_summary([])
        self.assertEqual(sum_list.total_announced_units, 0)
        self.assertEqual(sum_list.total_applied_units, 0)
        self.assertEqual(sum_list.nationwide_depletion_rate, 0.0)

        sum_dict = self.tracker.compute_nationwide_summary({})
        self.assertEqual(sum_dict.total_announced_units, 0)
        self.assertEqual(sum_dict.total_applied_units, 0)
        self.assertEqual(sum_dict.nationwide_depletion_rate, 0.0)


# ==============================================================================
# Suite 3: ComplaintRecord Dot and Slash Date Parsing
# ==============================================================================

class TestComplaintRecordDateParsing(unittest.TestCase):
    """Verifies ComplaintRecord.date_str parses dot and slash date formats without defaulting to today."""

    def test_dot_separated_date_parsing(self) -> None:
        """Dot-separated dates ('YYYY.MM.DD' with optional time) are correctly extracted as 'YYYY-MM-DD'."""
        c1 = ComplaintRecord(
            id="dot_1",
            source="bobaedream",
            url="https://www.bobaedream.co.kr/view?No=100",
            title="배터리 방전 결함",
            author="익명1",
            created_at="2024.05.10 12:34:56",
            vehicle_brand="현대",
            vehicle_model="아이오닉 5",
            defect_category="BATTERY_CHARGING",
            summary="충전기 체결 시 방전 발생",
            verbatim_quote="완속 충전기에 꽂아두었는데 아침에 12V 배터리가 완전 방전되어 문도 안 열렸습니다.",
        )
        self.assertEqual(c1.date_str, "2024-05-10")

        c2 = ComplaintRecord(
            id="dot_2",
            source="dcinside",
            url="https://gall.dcinside.com/board/view/?id=car&no=200",
            title="모터 소음 문제",
            author="익명2",
            created_at="2023.12.31",
            vehicle_brand="기아",
            vehicle_model="EV6",
            defect_category="POWERTRAIN_MOTOR",
            summary="고주파 모터 소음",
            verbatim_quote="가속 페달을 살짝만 밟아도 삐- 하는 고주파 소음이 심하게 발생해서 귀가 먹먹합니다.",
        )
        self.assertEqual(c2.date_str, "2023-12-31")

    def test_slash_separated_date_parsing(self) -> None:
        """Slash-separated dates ('YYYY/MM/DD' with optional time) are correctly extracted as 'YYYY-MM-DD'."""
        c1 = ComplaintRecord(
            id="slash_1",
            source="dcinside",
            url="https://gall.dcinside.com/board/view/?id=car&no=300",
            title="ICC BMS 경고등 점등",
            author="익명3",
            created_at="2024/07/15 08:20:00",
            vehicle_brand="제네시스",
            vehicle_model="GV60",
            defect_category="BATTERY_CHARGING",
            summary="주행 중 경고등 점등 및 출력 제한",
            verbatim_quote="고속도로 주행 도중 갑자기 경고등이 뜨더니 속도가 60km 이하로 제한되어 견인했습니다.",
        )
        self.assertEqual(c1.date_str, "2024-07-15")

        c2 = ComplaintRecord(
            id="slash_2",
            source="bobaedream",
            url="https://www.bobaedream.co.kr/view?No=400",
            title="내비게이션 블랙아웃",
            author="익명4",
            created_at="2025/01/01",
            vehicle_brand="테슬라",
            vehicle_model="Model Y",
            defect_category="SOFTWARE_ELECTRONICS",
            summary="화면 꺼짐 후 재부팅",
            verbatim_quote="운행 중에 디스플레이 화면이 갑자기 검게 변하고 먹통이 되어서 계기판도 안 보였습니다.",
        )
        self.assertEqual(c2.date_str, "2025-01-01")

    def test_hyphen_and_iso_standard_date_parsing_remains_intact(self) -> None:
        """Standard hyphen ('YYYY-MM-DD') and ISO formats continue to parse accurately."""
        c_hyphen = ComplaintRecord(
            id="hyphen_1",
            source="test",
            url="http://test.com/1",
            title="타이틀",
            author="작성자",
            created_at="2024-03-20",
            vehicle_brand="현대",
            vehicle_model="아이오닉 6",
            defect_category="BRAKING_SYSTEM",
            summary="회생제동 오류",
            verbatim_quote="회생제동 레벨을 최대로 설정했는데도 전혀 제동이 걸리지 않아 앞차를 박을 뻔했습니다.",
        )
        self.assertEqual(c_hyphen.date_str, "2024-03-20")

        c_iso = ComplaintRecord(
            id="iso_1",
            source="test",
            url="http://test.com/2",
            title="타이틀",
            author="작성자",
            created_at="2024-06-18T14:30:00Z",
            vehicle_brand="기아",
            vehicle_model="EV9",
            defect_category="BODY_CHASSIS",
            summary="도어 래치 결함",
            verbatim_quote="전자식 도어 래치가 잠금 해제되지 않아 차량에서 내리지 못하고 갇히는 사고가 있었습니다.",
        )
        self.assertEqual(c_iso.date_str, "2024-06-18")

    def test_date_str_fallback_on_corrupt_or_empty_input(self) -> None:
        """Corrupt or missing created_at strings gracefully fall back to today's date format."""
        c_empty = ComplaintRecord(
            id="empty_1",
            source="test",
            url="http://test.com/3",
            title="타이틀",
            author="작성자",
            created_at="",
            vehicle_brand="현대",
            vehicle_model="아이오닉 5",
            defect_category="BATTERY_CHARGING",
            summary="서머리",
            verbatim_quote="충전구 덮개가 닫히지 않고 고정 걸쇠가 부러져서 세차나 비 오는 날 운행이 불안합니다.",
        )
        # Format must be YYYY-MM-DD
        self.assertEqual(len(c_empty.date_str), 10)
        self.assertEqual(c_empty.date_str[4], "-")
        self.assertEqual(c_empty.date_str[7], "-")

        c_none = ComplaintRecord(
            id="none_1",
            source="test",
            url="http://test.com/4",
            title="타이틀",
            author="작성자",
            created_at=None,  # type: ignore[arg-type]
            vehicle_brand="현대",
            vehicle_model="아이오닉 5",
            defect_category="BATTERY_CHARGING",
            summary="서머리",
            verbatim_quote="충전구 덮개가 닫히지 않고 고정 걸쇠가 부러져서 세차나 비 오는 날 운행이 불안합니다.",
        )
        self.assertEqual(len(c_none.date_str), 10)


# ==============================================================================
# Suite 4: DefectTracker category_distribution in Cached Statistics
# ==============================================================================

class TestDefectTrackerCachedStatistics(unittest.TestCase):
    """Verifies DefectTracker.get_statistics() ensures 'category_distribution' is always present in cache returns."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.tracker = DefectTracker(
            root_data_dir=str(self.temp_path),
            web_data_dir=str(self.temp_path),
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_category_distribution_populated_when_cache_has_top_defect_categories(self) -> None:
        """get_statistics() populates category_distribution from root top_defect_categories list."""
        cache_data = {
            "statistics": {
                "total_scraped": 150,
                "total_filtered_defects": 30,
                "avg_negativity_score": 0.85,
                "critical_defect_count": 5,
            },
            "top_defect_categories": [
                {"category": "BATTERY_CHARGING", "count": 18},
                {"category": "SOFTWARE_ELECTRONICS", "count": 8},
                {"category": "POWERTRAIN_MOTOR", "count": 4},
            ],
            "reports": [],
        }
        report_file = self.temp_path / "daily_reports.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f)

        stats = self.tracker.get_statistics(file_path=str(report_file))

        self.assertIn("category_distribution", stats)
        self.assertIsInstance(stats["category_distribution"], dict)
        self.assertEqual(stats["category_distribution"]["BATTERY_CHARGING"], 18)
        self.assertEqual(stats["category_distribution"]["SOFTWARE_ELECTRONICS"], 8)
        self.assertEqual(stats["category_distribution"]["POWERTRAIN_MOTOR"], 4)

    def test_category_distribution_populated_from_reports_when_top_categories_missing(self) -> None:
        """get_statistics() falls back to counting raw reports when top_defect_categories is missing."""
        cache_data = {
            "statistics": {
                "total_scraped": 80,
                "total_filtered_defects": 3,
                "avg_negativity_score": 0.92,
                "critical_defect_count": 1,
            },
            # top_defect_categories is missing completely
            "reports": [
                {"id": "1", "defect_category": "BATTERY_CHARGING"},
                {"id": "2", "defect_category": "BATTERY_CHARGING"},
                {"id": "3", "defect_category": "BRAKING_SYSTEM"},
            ],
        }
        report_file = self.temp_path / "daily_reports.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f)

        stats = self.tracker.get_statistics(file_path=str(report_file))

        self.assertIn("category_distribution", stats)
        self.assertIsInstance(stats["category_distribution"], dict)
        self.assertEqual(stats["category_distribution"]["BATTERY_CHARGING"], 2)
        self.assertEqual(stats["category_distribution"]["BRAKING_SYSTEM"], 1)

    def test_category_distribution_present_even_on_empty_cache_file(self) -> None:
        """get_statistics() returns a dictionary for category_distribution even when cache statistics has no categories."""
        cache_data = {
            "statistics": {
                "total_scraped": 0,
                "total_filtered_defects": 0,
                "avg_negativity_score": 0.0,
                "critical_defect_count": 0,
            },
            "reports": [],
        }
        report_file = self.temp_path / "daily_reports.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f)

        stats = self.tracker.get_statistics(file_path=str(report_file))

        self.assertIn("category_distribution", stats)
        self.assertIsInstance(stats["category_distribution"], dict)
        self.assertEqual(stats["category_distribution"], {})


# ==============================================================================
# Suite 5: run_tracker.py Preservation of --web-dir Under auto_bidirectional
# ==============================================================================

class TestRunTrackerWebDirPreservation(unittest.TestCase):
    """Verifies run_tracker.py preserves explicit --web-dir even when auto_bidirectional is enabled."""

    def test_run_tracker_script_inspect_web_dir_guard(self) -> None:
        """Inspects run_tracker.py source to ensure line 476 does not require args.sync_web for web_dir."""
        run_tracker_path = Path(__file__).resolve().parent.parent / "run_tracker.py"
        with open(run_tracker_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Under auto_bidirectional, if args.web_dir is set, it must be honored
        self.assertIn("if args.web_dir:", content)
        # The outdated conditional was 'if args.sync_web and args.web_dir:'
        self.assertNotIn("if args.sync_web and args.web_dir:", content)


if __name__ == "__main__":
    unittest.main()
