"""Unit test suite for Cycle 17 backend hardening remediations.

Verifies:
1. DefectTracker polymorphic domain object and dictionary handling, category normalization.
2. SubsidyPayload and RegionRecord dictionary duck-typing and None safeguards.
3. build_initial_baseline dictionary metric duck-typing.
4. update_region_metrics and compute_nationwide_summary dictionary region support.
5. DSIBreakdown NaN/None safety and Korean spaced dot date parsing.
6. ReportGenerator case-insensitive status and fractional billion budget formatting.
7. BaseCrawler LSP compliance on BobaeDreamCrawler and DCInsideCrawler.
8. run_scraper _atomic_copy_file POSIX 0o644 permission enforcement.
9. json_writer read_daily_reports defensive error handling.
"""

import math
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from models.complaint import ComplaintRecord, DSIBreakdown
from tracker.defect_tracker import DefectTracker
from tracker.subsidy_models import (
    CategoryMetrics,
    NationwideSummary,
    PopularModelEntry,
    RegionRecord,
    SubsidyMetadata,
    SubsidyPayload,
)
from tracker.subsidy_baseline import build_initial_baseline
from tracker.subsidy_tracker import SubsidyTracker
from tracker.report_generator import ReportGenerator
from crawlers.bobaedream import BobaeDreamCrawler
from crawlers.dcinside import DCInsideCrawler
from run_scraper import _atomic_copy_file
from utils.json_writer import read_daily_reports


class TestCycle17BackendRemediation(unittest.TestCase):
    """Test suite for Cycle 17 backend remediations."""

    def test_01_defect_tracker_domain_objects_and_category_normalization(self):
        """Test DefectTracker supports ComplaintRecord objects and normalizes category."""
        tracker = DefectTracker()
        complaint = ComplaintRecord(
            id="test-101",
            source="dcinside",
            url="https://gall.dcinside.com/board/view/?id=car_new1&no=1001",
            title="테슬라 배터리 방전 결함",
            author="tester",
            created_at="2026. 10. 25.",
            vehicle_brand="Tesla",
            vehicle_model="Model Y",
            defect_category="BATTERY_CHARGING",
            summary="배터리 방전 문제",
            verbatim_quote="배터리가 너무 빨리 닳아요",
            severity_index=8.5,
        )

        dict_report = {
            "id": "test-102",
            "source": "bobaedream",
            "url": "https://www.bobaedream.co.kr/view?code=national&No=2001",
            "title": "현대 아이오닉 감속기 누유",
            "author": "tester2",
            "created_at": "2026-10-24",
            "vehicle_brand": "Hyundai",
            "vehicle_model": "Ioniq 5",
            "category": "DRIVING_POWERTRAIN",  # Legacy "category" naming
            "summary": "감속기 누유 발생",
            "verbatim_quote": "오일이 새네요",
            "severity_index": 7.2,
        }

        mixed_reports = [complaint, dict_report]

        # 1. Verify _build_category_index handles mixed objects without error
        tracker._build_category_index(mixed_reports)
        self.assertIn("BATTERY_CHARGING", tracker._category_index)
        self.assertIn("DRIVING_POWERTRAIN", tracker._category_index)
        self.assertEqual(len(tracker._category_index["BATTERY_CHARGING"]), 1)
        self.assertEqual(len(tracker._category_index["DRIVING_POWERTRAIN"]), 1)

        # 2. Verify query_defects handles domain objects and dicts seamlessly
        with patch.object(tracker, "load_reports", return_value=mixed_reports):
            # Query by category
            res_battery = tracker.query_defects(category="BATTERY_CHARGING")
            self.assertEqual(len(res_battery), 1)
            self.assertEqual(res_battery[0]["id"], "test-101")
            self.assertIsInstance(res_battery[0], dict)

            # Query by brand
            res_tesla = tracker.query_defects(vehicle_brand="tesla")
            self.assertEqual(len(res_tesla), 1)
            self.assertEqual(res_tesla[0]["vehicle_brand"], "Tesla")

            # Query by keyword in quote/summary
            res_oil = tracker.query_defects(keyword="누유")
            self.assertEqual(len(res_oil), 1)
            self.assertEqual(res_oil[0]["id"], "test-102")

            # Query by severity
            res_high_sev = tracker.query_defects(min_severity=8.0)
            self.assertEqual(len(res_high_sev), 1)
            self.assertEqual(res_high_sev[0]["id"], "test-101")

    def test_02_subsidy_models_dict_duck_typing_and_none_guard(self):
        """Test SubsidyPayload.to_dict handles raw dicts and RegionRecord handles None categories."""
        # 1. RegionRecord with categories=None
        rec = RegionRecord(
            region_id="KR-11",
            iso_code="KR-11",
            name_ko="서울특별시",
            name_en="Seoul",
            tier=1,
            overall_depletion_rate=85.0,
            overall_status="WARNING",
            residency_requirement_days=30,
            supplementary_budget_added=False,
            categories=None,  # type: ignore
        )
        rec_dict = rec.to_dict()
        self.assertEqual(rec_dict["categories"], {})

        # 2. SubsidyPayload with dict regions and popular_models_matrix
        payload = SubsidyPayload(
            metadata=SubsidyMetadata(
                version="1.0.0",
                generated_at="2026-10-25T00:00:00Z",
                policy_year=2026,
                data_sources=["K-EV"],
                total_regions_tracked=1,
                total_municipalities_tracked=1,
            ),
            alert_thresholds={},
            nationwide_summary=NationwideSummary(
                total_announced_units=1000,
                total_applied_units=800,
                total_delivered_units=700,
                total_remaining_units=200,
                nationwide_depletion_rate=80.0,
                total_budget_billion_krw=10.0,
                disbursed_budget_billion_krw=8.0,
                category_totals={},
                alert_region_counts={},
            ),
            regions=[{"region_id": "KR-11", "name_ko": "서울"}],  # Raw dict!
            popular_models_matrix=[{"model_id": "ioniq-5-2026", "rank": 1}],  # Raw dict!
            historical_depletion_trajectory=[],
        )

        p_dict = payload.to_dict()
        self.assertEqual(p_dict["regions"][0]["region_id"], "KR-11")
        self.assertEqual(p_dict["popular_models_matrix"][0]["model_id"], "ioniq-5-2026")

    def test_03_subsidy_baseline_duck_typing(self):
        """Test build_initial_baseline handles dict regions and dict category metrics."""
        dict_regions = [
            {
                "region_id": "KR-11",
                "overall_status": "warning",
                "municipalities": [{"muni_id": "1101"}],
                "categories": {
                    "passenger": {
                        "announced_units": 100,
                        "applied_units": 90,
                        "delivered_units": 85,
                        "total_budget_krw": 1000000,
                        "remaining_budget_krw": 100000,
                    }
                },
            }
        ]

        payload = build_initial_baseline(dict_regions)
        summary = payload.nationwide_summary
        self.assertEqual(summary.total_announced_units, 100)
        self.assertEqual(summary.total_applied_units, 90)
        self.assertEqual(summary.total_delivered_units, 85)
        self.assertEqual(summary.nationwide_depletion_rate, 90.0)
        self.assertEqual(summary.total_remaining_units, 10)

    def test_04_subsidy_tracker_dict_duck_typing(self):
        """Test update_region_metrics and compute_nationwide_summary with dict payloads."""
        tracker = SubsidyTracker()
        raw_region = {
            "region_id": "KR-11",
            "categories": {
                "passenger": {
                    "announced_units": 100,
                    "applied_units": 95,
                    "delivered_units": 90,
                    "total_budget_krw": 1000000,
                }
            },
            "municipalities": [
                {
                    "name": "종로구",
                    "announced_units": 50,
                    "applied_units": 48,
                    "delivered_units": 45,
                }
            ],
        }

        updated = tracker.update_region_metrics(raw_region)
        self.assertIsInstance(updated, dict)
        self.assertEqual(updated["overall_depletion_rate"], 95.0)
        self.assertEqual(updated["overall_status"], "CRITICAL")
        self.assertEqual(updated["categories"]["passenger"]["remaining_units"], 5)
        self.assertEqual(updated["municipalities"][0]["status"], "CRITICAL")

        # Nationwide summary with dict regions
        summary = tracker.compute_nationwide_summary([updated])
        self.assertEqual(summary.total_announced_units, 100)
        self.assertEqual(summary.total_applied_units, 95)
        self.assertEqual(summary.nationwide_depletion_rate, 95.0)

    def test_05_dsi_breakdown_nan_guard_and_korean_spaced_date(self):
        """Test DSIBreakdown to_dict guards NaN/None and ComplaintRecord parses spaced dot dates."""
        # 1. NaN and None in DSIBreakdown
        dsi = DSIBreakdown(
            safety=float("nan"),
            functional=float("inf"),
            economic=None,  # type: ignore
            social=3.456,
            convenience=4.0,
        )
        dsi_dict = dsi.to_dict()
        self.assertEqual(dsi_dict["safety"], 0.0)
        self.assertEqual(dsi_dict["functional"], 0.0)
        self.assertEqual(dsi_dict["economic"], 0.0)
        self.assertEqual(dsi_dict["social"], 3.46)
        self.assertEqual(dsi_dict["convenience"], 4.0)

        # 2. Spaced dot dates
        comp1 = ComplaintRecord(
            id="d-1",
            source="dc",
            url="http://example.com/1",
            title="title",
            author="auth",
            created_at="2026. 10. 25.",
            vehicle_brand="Tesla",
            vehicle_model="Model 3",
            defect_category="BATTERY_CHARGING",
            summary="sum",
            verbatim_quote="quote",
        )
        self.assertEqual(comp1.date_str, "2026-10-25")

        comp2 = ComplaintRecord(
            id="d-2",
            source="dc",
            url="http://example.com/2",
            title="title",
            author="auth",
            created_at="2026. 9. 8. 14:30:00",
            vehicle_brand="Kia",
            vehicle_model="EV6",
            defect_category="BATTERY_CHARGING",
            summary="sum",
            verbatim_quote="quote",
        )
        self.assertEqual(comp2.date_str, "2026-09-08")

    def test_06_report_generator_case_insensitive_status_and_float_budget(self):
        """Test ReportGenerator case-insensitive matching and float budget precision."""
        gen = ReportGenerator()
        payload = {
            "regions": [
                {
                    "name_ko": "제주특별자치도",
                    "overall_status": "critical",  # Lowercase!
                    "overall_depletion_rate": 99.0,
                    "categories": {"passenger": {"remaining_units": 55}},
                },
                {
                    "name_ko": "울산광역시",
                    "overall_status": "warning",  # Lowercase!
                    "overall_depletion_rate": 88.0,
                    "categories": {"passenger": {"remaining_units": 150}},
                },
            ],
            "nationwide_summary": {
                "nationwide_depletion_rate": 89.4,
                "total_announced_units": 148510,
                "total_applied_units": 132766,
                "disbursed_budget_billion_krw": 1893.4,  # Float with 0.4!
                "total_budget_billion_krw": 2105.1,      # Float with 0.1!
                "category_totals": {},
            },
        }

        briefing = gen.generate_subsidy_briefing(payload)
        # Verify critical region captured
        self.assertIn("제주특별자치도", briefing)
        self.assertIn("울산광역시", briefing)
        # Verify float budget precision preserved
        self.assertIn("1,893.4억 원", briefing)
        self.assertIn("2,105.1억 원", briefing)

    def test_07_crawler_lsp_compliance_and_mobile_fallback(self):
        """Test BaseCrawler LSP compliance with extra kwargs on BobaeDream and DCInside."""
        bobae = BobaeDreamCrawler()
        dc = DCInsideCrawler()

        # Mock client.get
        with patch.object(bobae.client, "get", return_value=(200, "<html><title>테스트</title><body>본문</body></html>", {})):
            with patch.object(bobae, "parse_post_detail", return_value={"title": "성공"}):
                res = bobae.fetch_post(
                    "https://www.bobaedream.co.kr/view?code=national&No=123",
                    referer="https://custom.referer.com",
                    custom_arg="extra_val",
                )
                self.assertEqual(res, {"title": "성공"})

        with patch.object(dc.client, "get", return_value=(200, "<html><title>DC</title><body>내용</body></html>", {})):
            with patch.object(dc, "parse_post_detail", return_value={"title": "DC성공"}):
                res_dc = dc.fetch_post(
                    "https://gall.dcinside.com/board/view/?id=car_new1&no=555",
                    referer="https://custom.dc.com",
                    custom_arg="dc_val",
                )
                self.assertEqual(res_dc, {"title": "DC성공"})

    def test_08_atomic_copy_posix_permissions(self):
        """Test _atomic_copy_file enforces 0o644 mode on destination file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "source.txt"
            dst = Path(tmpdir) / "sub" / "dest.txt"
            src.write_text("test content", encoding="utf-8")

            res_path = _atomic_copy_file(src, dst)
            self.assertTrue(Path(res_path).exists())
            mode = stat.S_IMODE(os.stat(res_path).st_mode)
            self.assertEqual(mode, 0o644)

    def test_09_json_writer_defensive_read(self):
        """Test read_daily_reports handles non-existent and malformed files safely."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Non-existent file
            non_existent = Path(tmpdir) / "does_not_exist.json"
            res1 = read_daily_reports(str(non_existent))
            self.assertEqual(res1, {"reports": [], "statistics": {}})

            # 2. Corrupted JSON file
            corrupt_file = Path(tmpdir) / "corrupt.json"
            corrupt_file.write_text("{ broken json: ...", encoding="utf-8")
            res2 = read_daily_reports(str(corrupt_file))
            self.assertEqual(res2, {"reports": [], "statistics": {}})


if __name__ == "__main__":
    unittest.main()
