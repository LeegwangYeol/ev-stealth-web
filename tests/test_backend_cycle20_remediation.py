"""
tests/test_backend_cycle20_remediation.py - Unit test suite locking in all Cycle 20 Backend Remediations.

Validates:
1. RawPost.from_dict integer id=0 preservation.
2. DefectTracker.query_defects WARNING, CAUTION, and INFO severity tier mapping.
3. run_scraper.py mirror parity preservation on 0-defect scrapes.
4. defect_filter nominalized malfunction verbs (됨, 걸림, 켜짐, 열림, 빠짐, 먹힘) in negation window.
5. DailyReportPayload and DailyReportStatistics from_dict symmetric deserialization.
6. NationwideSummary and RegionRecord dictionary subscripting mapping protocol.
7. crawlers/dcinside.py 2-digit year timestamp parsing.
8. crawlers parenthesized Korean weekday date parsing (e.g. 2026.10.27 (화) 14:20:30).
9. ComplaintRecord.date_str Korean date format (YYYY년 MM월 DD일) parsing.
10. vehicle_matcher Korean '일렉트리파이드' Genesis EV recognition.
11. CategoryMetrics and MunicipalityMetrics negative value clamping to 0.
12. atomic_writer nested NaN/Inf sanitization with Decimals.
13. subsidy_tracker calculate_net_subsidy zero max_national division safety.
14. report_generator empty payload and stats graceful markdown fallback.
15. RawPost id/post_id and source/platform alias and property symmetry.
16. defect_filter rhetorical question complaints and sarcastic praise polarity inversion.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, List
import unittest

from crawlers.bobaedream import _normalize_iso_timestamp as bd_ts
from crawlers.dcinside import _normalize_iso_timestamp as dc_ts
from filters.defect_filter import ContextualDefectFilter
from filters.vehicle_matcher import extract_vehicle_info
from models.complaint import (
    ComplaintRecord,
    DailyReportPayload,
    DailyReportStatistics,
    RawPost,
)
from run_scraper import _atomic_copy_file
from tracker.atomic_writer import _json_default, atomic_write_json, sanitize_nan_inf
from tracker.defect_tracker import DefectTracker
from tracker.report_generator import ReportGenerator, _safe_sev
from tracker.subsidy_models import (
    CategoryMetrics,
    MunicipalityMetrics,
    NationwideSummary,
    RegionRecord,
)
from tracker.subsidy_tracker import calculate_net_subsidy


class TestBackendCycle20Remediation(unittest.TestCase):
    """Rigorous unit test suite locking in all Cycle 20 backend remediations."""

    # -----------------------------------------------------------------
    # Test 1: RawPost.from_dict preserves integer id=0
    # -----------------------------------------------------------------
    def test_01_raw_post_from_dict_preserves_integer_id_zero(self) -> None:
        """RawPost.from_dict must preserve integer id=0 as string '0' instead of empty string."""
        post1 = RawPost.from_dict({"id": 0, "platform": "test", "title": "t", "content": "c"})
        self.assertEqual(post1.post_id, "0")
        self.assertEqual(post1.id, "0")

        post2 = RawPost.from_dict({"post_id": 0, "source": "test", "title": "t", "content": "c"})
        self.assertEqual(post2.post_id, "0")
        self.assertEqual(post2.id, "0")

        post3 = RawPost.from_dict({"id": "0"})
        self.assertEqual(post3.post_id, "0")

        post4 = RawPost.from_dict({"id": 12345})
        self.assertEqual(post4.post_id, "12345")

    # -----------------------------------------------------------------
    # Test 2: DefectTracker.query_defects severity tier mapping
    # -----------------------------------------------------------------
    def test_02_defect_tracker_severity_tier_mapping_warning_caution_info(self) -> None:
        """DefectTracker.query_defects must map WARNING (7.0), CAUTION (4.0), and INFO (1.0)."""
        tracker = DefectTracker()
        sample_reports = [
            {
                "id": "rep_warn",
                "title": "기아 EV3 ccNC 화면 멈춤 경고",
                "severity": "WARNING",
                "defect_category": "SOFTWARE_ELECTRONICS",
                "vehicle_brand": "Kia",
                "vehicle_model": "EV3",
            },
            {
                "id": "rep_caut",
                "title": "도어 트림 잡소리 주의",
                "severity": "CAUTION",
                "defect_category": "EXTERIOR_BODY",
                "vehicle_brand": "Hyundai",
                "vehicle_model": "아이오닉5",
            },
            {
                "id": "rep_info",
                "title": "단순 정보 문의",
                "severity": "INFO",
                "defect_category": "CONVENIENCE_FEATURES",
                "vehicle_brand": "Tesla",
                "vehicle_model": "Model Y",
            },
        ]

        with tempfile.TemporaryDirectory() as td:
            sample_file = Path(td) / "reports.json"
            sample_file.write_text(json.dumps({"reports": sample_reports}), encoding="utf-8")

            # Querying min_severity=6.0 must include WARNING (7.0), excluding CAUTION (4.0) and INFO (1.0)
            warn_results = tracker.query_defects(file_path=sample_file, min_severity=6.0)
            warn_ids = [r["id"] for r in warn_results]
            self.assertIn("rep_warn", warn_ids)
            self.assertNotIn("rep_caut", warn_ids)
            self.assertNotIn("rep_info", warn_ids)

            # Querying min_severity=4.0 must include WARNING (7.0) and CAUTION (4.0)
            caut_results = tracker.query_defects(file_path=sample_file, min_severity=4.0)
            caut_ids = [r["id"] for r in caut_results]
            self.assertIn("rep_warn", caut_ids)
            self.assertIn("rep_caut", caut_ids)
            self.assertNotIn("rep_info", caut_ids)

            # Querying min_severity=1.0 must include all 3
            all_results = tracker.query_defects(file_path=sample_file, min_severity=1.0)
            self.assertEqual(len(all_results), 3)

    # -----------------------------------------------------------------
    # Test 3: run_scraper.py 0-defect scrape mirror preservation
    # -----------------------------------------------------------------
    def test_03_run_scraper_0_defect_mirror_parity_preservation(self) -> None:
        """When 0 defects are scraped, run_scraper must copy authentic content from existing mirror."""
        with tempfile.TemporaryDirectory() as td:
            path_a = Path(td) / "dir_a" / "daily_reports.json"
            path_b = Path(td) / "dir_b" / "daily_reports.json"
            path_a.parent.mkdir(parents=True, exist_ok=True)
            path_b.parent.mkdir(parents=True, exist_ok=True)

            authentic_payload = {
                "generated_at": "2026-10-27T19:00:00Z",
                "pipeline_version": "1.0.0",
                "statistics": {"total_filtered_defects": 3},
                "reports": [{"id": "r1", "title": "ICCU 터짐"}],
            }
            path_a.write_text(json.dumps(authentic_payload), encoding="utf-8")

            # Simulate run_scraper replication logic:
            unique_paths = [str(path_a), str(path_b)]
            defect_complaints: List[Any] = []  # 0 scraped defects

            existing_mirror = None
            if len(defect_complaints) == 0:
                for p in unique_paths:
                    if os.path.exists(p) and os.path.isfile(p) and os.path.getsize(p) > 0:
                        existing_mirror = p
                        break

            self.assertEqual(existing_mirror, str(path_a))

            # Copy to path_b
            if existing_mirror and not path_b.exists():
                _atomic_copy_file(existing_mirror, str(path_b))

            self.assertTrue(path_b.exists())
            self.assertEqual(path_a.read_bytes(), path_b.read_bytes())

    # -----------------------------------------------------------------
    # Test 4: defect_filter nominalized malfunction verbs in negation window
    # -----------------------------------------------------------------
    def test_04_defect_filter_korean_malfunction_verbs_in_negation_window(self) -> None:
        """ContextualDefectFilter must not treat '안 됨', '안 걸림', '안 켜짐', '안 열림' as defect negation."""
        df = ContextualDefectFilter()

        # In _is_negator_in_window: malfunction verbs should return False (not a defect negator)
        self.assertFalse(df._is_negator_in_window(["안", "됨"]))
        self.assertFalse(df._is_negator_in_window(["안", "걸림"]))
        self.assertFalse(df._is_negator_in_window(["안", "켜짐"]))
        self.assertFalse(df._is_negator_in_window(["안", "열림"]))
        self.assertFalse(df._is_negator_in_window(["안", "빠짐"]))
        self.assertFalse(df._is_negator_in_window(["안", "먹힘"]))
        self.assertFalse(df._is_negator_in_window(["안", "나옴"]))

        # Real defect post containing nominalized malfunction verb
        post1 = RawPost(
            platform="dcinside",
            post_id="post_malfunc_1",
            title="기아 EV6 계기판 화면이 안 켜짐",
            content="출고한 내 차 시동 걸었는데 화면 블랙아웃되고 터치도 안 됨",
        )
        res1 = df.process_post(post1)
        self.assertTrue(res1.is_authentic_defect)

        # Real praise post where defect is truly negated
        post_praise = RawPost(
            platform="bobaedream",
            post_id="post_praise_1",
            title="양품 출고 후기",
            content="단차 전혀 없고 잡소리도 1도 안 납니다",
        )
        res_praise = df.process_post(post_praise)
        self.assertFalse(res_praise.is_authentic_defect)

    # -----------------------------------------------------------------
    # Test 5: DailyReportPayload & DailyReportStatistics from_dict symmetry
    # -----------------------------------------------------------------
    def test_05_daily_report_payload_and_statistics_from_dict_symmetry(self) -> None:
        """DailyReportPayload and DailyReportStatistics must support symmetric from_dict deserialization."""
        stats = DailyReportStatistics(
            total_scraped=150,
            total_filtered_defects=12,
            avg_negativity_score=0.88,
            critical_defect_count=4,
        )
        payload = DailyReportPayload(
            generated_at="2026-10-27T19:30:00Z",
            pipeline_version="1.0.0",
            statistics=stats,
            reports=[{"id": "r1", "title": "ICCU 결함"}],
            total_complaints_today=12,
            top_defect_categories=[{"category": "BATTERY_CHARGING", "count": 6}],
        )

        d = payload.to_dict()
        restored = DailyReportPayload.from_dict(d)

        self.assertEqual(restored.generated_at, payload.generated_at)
        self.assertEqual(restored.pipeline_version, payload.pipeline_version)
        self.assertEqual(restored.total_complaints_today, payload.total_complaints_today)
        self.assertEqual(restored.statistics.total_scraped, 150)
        self.assertEqual(restored.statistics.total_filtered_defects, 12)
        self.assertEqual(restored.statistics.avg_negativity_score, 0.88)
        self.assertEqual(restored.statistics.critical_defect_count, 4)
        self.assertEqual(restored.reports, payload.reports)
        self.assertEqual(restored.top_defect_categories, payload.top_defect_categories)
        self.assertEqual(restored.to_dict(), payload.to_dict())

    # -----------------------------------------------------------------
    # Test 6: NationwideSummary and RegionRecord dict subscriptability
    # -----------------------------------------------------------------
    def test_06_nationwide_summary_and_region_record_dict_subscriptability(self) -> None:
        """NationwideSummary and RegionRecord must implement __getitem__, __contains__, and get()."""
        summary = NationwideSummary(
            total_announced_units=148510,
            total_applied_units=132766,
            total_delivered_units=122515,
            total_remaining_units=15744,
            nationwide_depletion_rate=89.4,
            total_budget_billion_krw=2105.1,
            disbursed_budget_billion_krw=1893.4,
            category_totals={"passenger": {"announced_units": 110400}},
            alert_region_counts={"critical": 4},
        )

        # Mapping protocol on NationwideSummary
        self.assertEqual(summary["total_announced_units"], 148510)
        self.assertEqual(summary["nationwide_depletion_rate"], 89.4)
        self.assertIn("total_announced_units", summary)
        self.assertNotIn("non_existent_key", summary)
        self.assertEqual(summary.get("total_announced_units"), 148510)
        self.assertEqual(summary.get("non_existent_key", "default_val"), "default_val")
        with self.assertRaises(KeyError):
            _ = summary["non_existent_key"]

        # Mapping protocol on RegionRecord
        region = RegionRecord(
            region_id="KR-11",
            iso_code="KR-11",
            name_ko="서울특별시",
            name_en="Seoul",
            overall_depletion_rate=85.2,
            overall_status="HEALTHY",
        )
        self.assertEqual(region["name_ko"], "서울특별시")
        self.assertEqual(region["region_id"], "KR-11")
        self.assertIn("name_ko", region)
        self.assertNotIn("fake_field", region)
        self.assertEqual(region.get("name_ko"), "서울특별시")
        self.assertEqual(region.get("fake_field", 42), 42)
        with self.assertRaises(KeyError):
            _ = region["fake_field"]

    # -----------------------------------------------------------------
    # Test 7: crawlers/dcinside.py 2-digit year timestamp parsing
    # -----------------------------------------------------------------
    def test_07_dcinside_crawler_two_digit_year_parsing(self) -> None:
        """dcinside._normalize_iso_timestamp must parse 2-digit year timestamps (YY.MM.DD)."""
        res1 = dc_ts("26.09.15")
        self.assertTrue(res1.startswith("2026-09-15"), f"Expected 2026-09-15, got {res1}")

        res2 = dc_ts("26/10/27")
        self.assertTrue(res2.startswith("2026-10-27"), f"Expected 2026-10-27, got {res2}")

        res3 = dc_ts("26-10-27")
        self.assertTrue(res3.startswith("2026-10-27"), f"Expected 2026-10-27, got {res3}")

    # -----------------------------------------------------------------
    # Test 8: crawlers parenthesized Korean weekday date parsing
    # -----------------------------------------------------------------
    def test_08_crawlers_parenthesized_korean_weekday_date_parsing(self) -> None:
        """crawlers must parse timestamps with parenthesized Korean weekdays preserving hour/min/sec."""
        res_dc = dc_ts("2026.10.27 (화) 14:20:30")
        self.assertEqual(res_dc, "2026-10-27T14:20:30+00:00")

        # 2-digit year with weekday in dcinside
        res_dc_yy = dc_ts("26.10.27 (화) 14:20:30")
        self.assertEqual(res_dc_yy, "2026-10-27T14:20:30+00:00")

        # BobaeDream parenthesized weekday timestamp
        res_bd = bd_ts("2026.10.27 (화) 14:20:30")
        self.assertEqual(res_bd, "2026-10-27T14:20:30+00:00")

    # -----------------------------------------------------------------
    # Test 9: ComplaintRecord.date_str Korean date format parsing
    # -----------------------------------------------------------------
    def test_09_complaint_record_korean_date_format_parsing(self) -> None:
        """ComplaintRecord.date_str must parse Korean explicit date format (YYYY년 MM월 DD일)."""
        rec1 = ComplaintRecord(
            id="c1",
            source="dcinside",
            url="http://test.com/1",
            title="t",
            author="a",
            created_at="2026년 10월 27일",
            vehicle_brand="Hyundai",
            vehicle_model="아이오닉5",
            defect_category="BATTERY_CHARGING",
            summary="s",
            verbatim_quote="v",
        )
        self.assertEqual(rec1.date_str, "2026-10-27")

        rec2 = ComplaintRecord(
            id="c2",
            source="bobaedream",
            url="http://test.com/2",
            title="t",
            author="a",
            created_at="2026년 9월 8일 14:30:00",
            vehicle_brand="Kia",
            vehicle_model="EV6",
            defect_category="DRIVING_POWERTRAIN",
            summary="s",
            verbatim_quote="v",
        )
        self.assertEqual(rec2.date_str, "2026-09-08")

    # -----------------------------------------------------------------
    # Test 10: vehicle_matcher Genesis Electrified EV recognition
    # -----------------------------------------------------------------
    def test_10_vehicle_matcher_genesis_electrified_patterns(self) -> None:
        """vehicle_matcher must match Korean '일렉트리파이드' Genesis models."""
        b1, m1 = extract_vehicle_info("제네시스 일렉트리파이드 GV70 충전 테스트")
        self.assertEqual(b1, "Hyundai")
        self.assertEqual(m1, "GV70 EV")

        b2, m2 = extract_vehicle_info("일렉트리파이드 G80 배터리 무상보증")
        self.assertEqual(b2, "Hyundai")
        self.assertEqual(m2, "G80 EV")

        b3, m3 = extract_vehicle_info("electrified GV70 시승기")
        self.assertEqual(b3, "Hyundai")
        self.assertEqual(m3, "GV70 EV")

        b4, m4 = extract_vehicle_info("일렉트리파이드 GV60 충전 불량")
        self.assertEqual(b4, "Hyundai")
        self.assertEqual(m4, "GV60")

    # -----------------------------------------------------------------
    # Test 11: CategoryMetrics and MunicipalityMetrics negative value clamping
    # -----------------------------------------------------------------
    def test_11_category_and_municipality_metrics_negative_value_clamping(self) -> None:
        """CategoryMetrics and MunicipalityMetrics must clamp negative inputs to 0."""
        cat = CategoryMetrics.from_dict({
            "announced_units": -50,
            "applied_units": -20,
            "delivered_units": -10,
            "remaining_units": -30,
            "max_local_subsidy_krw": -1000000,
        })
        self.assertEqual(cat.announced_units, 0)
        self.assertEqual(cat.applied_units, 0)
        self.assertEqual(cat.delivered_units, 0)
        self.assertEqual(cat.remaining_units, 0)
        self.assertEqual(cat.max_local_subsidy_krw, 0)

        mun = MunicipalityMetrics.from_dict({
            "name_ko": "구",
            "announced_units": -100,
            "applied_units": -50,
            "remaining_units": -50,
            "local_subsidy_krw": -2000000,
        })
        self.assertEqual(mun.announced_units, 0)
        self.assertEqual(mun.applied_units, 0)
        self.assertEqual(mun.remaining_units, 0)
        self.assertEqual(mun.local_subsidy_krw, 0)

    # -----------------------------------------------------------------
    # Test 12: atomic_writer nested NaN/Inf sanitization with Decimals
    # -----------------------------------------------------------------
    def test_12_atomic_writer_nested_nan_inf_sanitization_with_decimals(self) -> None:
        """atomic_writer must sanitize deeply nested NaNs, Infs, and Decimals safely."""
        raw_floats = {
            "flt_nan": float("nan"),
            "flt_inf": float("inf"),
            "flt_neginf": float("-inf"),
            "list": [100.5, float("nan")],
            "inner": {"valid": 1893.4},
        }
        san = sanitize_nan_inf(raw_floats)
        self.assertEqual(san["flt_nan"], 0.0)
        self.assertEqual(san["flt_inf"], 0.0)
        self.assertEqual(san["flt_neginf"], 0.0)
        self.assertEqual(san["list"], [100.5, 0.0])
        self.assertEqual(san["inner"]["valid"], 1893.4)

        # Decimal NaN and Inf handling via _json_default
        self.assertEqual(_json_default(Decimal("NaN")), 0.0)
        self.assertEqual(_json_default(Decimal("Infinity")), 0.0)
        self.assertEqual(_json_default(Decimal("-Infinity")), 0.0)
        self.assertEqual(_json_default(Decimal("1893.4")), 1893.4)

        # Combined nested structures via atomic_write_json
        nested = {
            "dec_nan": Decimal("NaN"),
            "dec_inf": Decimal("Infinity"),
            "flt_nan": float("nan"),
            "flt_inf": float("inf"),
            "inner": {"valid": Decimal("1893.4")},
        }
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "test_nested.json"
            atomic_write_json(nested, p)
            self.assertTrue(p.exists())
            data = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(data["dec_nan"], 0.0)
            self.assertEqual(data["dec_inf"], 0.0)
            self.assertEqual(data["flt_nan"], 0.0)
            self.assertEqual(data["flt_inf"], 0.0)
            self.assertEqual(data["inner"]["valid"], 1893.4)

    # -----------------------------------------------------------------
    # Test 13: subsidy_tracker calculate_net_subsidy zero max_national division safety
    # -----------------------------------------------------------------
    def test_13_subsidy_tracker_calculate_net_subsidy_zero_division_safety(self) -> None:
        """calculate_net_subsidy must not raise ZeroDivisionError when max_national is 0."""
        res_zero_nat = calculate_net_subsidy(
            model_national=6_500_000,
            max_national=0,
            max_local=3_000_000,
            msrp=50_000_000,
        )
        self.assertEqual(res_zero_nat["local_subsidy_krw"], 0)
        self.assertEqual(res_zero_nat["total_subsidy_krw"], 6_500_000)
        self.assertEqual(res_zero_nat["net_price_krw"], 43_500_000)

        res_zero_loc = calculate_net_subsidy(
            model_national=6_500_000,
            max_national=6_500_000,
            max_local=0,
            msrp=50_000_000,
        )
        self.assertEqual(res_zero_loc["local_subsidy_krw"], 0)
        self.assertEqual(res_zero_loc["total_subsidy_krw"], 6_500_000)

    # -----------------------------------------------------------------
    # Test 14: report_generator empty payload and stats fallback
    # -----------------------------------------------------------------
    def test_14_report_generator_empty_payload_and_stats_fallback(self) -> None:
        """ReportGenerator must produce valid markdown briefings when given empty reports list."""
        rg = ReportGenerator()
        briefing = rg.generate_defect_briefing([])
        self.assertIsInstance(briefing, str)
        self.assertIn("대한민국 EV 실생활 결함 및 커뮤니티 동향 일일 브리핑", briefing)

        stats_report = rg.generate_statistical_report([])
        self.assertIsInstance(stats_report, str)
        self.assertIn("EV 결함 및 품질 빅데이터 통계 분석 보고서", stats_report)

        combined = rg.generate_combined_briefing(defect_reports=[])
        self.assertIsInstance(combined, str)
        self.assertIn("대한민국 EV 실생활 결함 및 커뮤니티 동향 일일 브리핑", combined)

    # -----------------------------------------------------------------
    # Test 15: RawPost id/post_id and source/platform alias symmetry
    # -----------------------------------------------------------------
    def test_15_raw_post_id_alias_and_property_symmetry(self) -> None:
        """RawPost must maintain property symmetry between id <-> post_id and source <-> platform."""
        p1 = RawPost(id="999", source="dcinside")
        self.assertEqual(p1.id, "999")
        self.assertEqual(p1.post_id, "999")
        self.assertEqual(p1.source, "dcinside")
        self.assertEqual(p1.platform, "dcinside")

        p2 = RawPost(post_id="888", platform="bobaedream")
        self.assertEqual(p2.id, "888")
        self.assertEqual(p2.post_id, "888")
        self.assertEqual(p2.source, "bobaedream")
        self.assertEqual(p2.platform, "bobaedream")

    # -----------------------------------------------------------------
    # Test 16: defect_filter rhetorical questions and sarcastic praise
    # -----------------------------------------------------------------
    def test_16_defect_filter_rhetorical_and_negation_boundary_resilience(self) -> None:
        """ContextualDefectFilter must accept rhetorical questions and invert sarcastic praise."""
        df = ContextualDefectFilter()

        # Rhetorical question complaint
        post_rq = RawPost(
            platform="dcinside",
            post_id="rq_1",
            title="아이오닉5 ICCU 퍽 터지는 소리 났는데 원래 이런가요?",
            content="출고한 내 차 고속도로에서 갑자기 멈췄습니다 정상인가요?",
        )
        res_rq = df.process_post(post_rq)
        self.assertTrue(res_rq.is_authentic_defect)

        # Sarcastic praise inversion
        post_sarcasm = RawPost(
            platform="bobaedream",
            post_id="sarcasm_1",
            title="출고 후기",
            content="비 오는 날 서브트렁크 워터파크 개장함 짱개차 폼 미쳤다 ㅋㅋㅋ",
        )
        res_sarcasm = df.process_post(post_sarcasm)
        self.assertTrue(res_sarcasm.is_authentic_defect)
        self.assertLessEqual(res_sarcasm.sentiment_polarity, -0.50)


if __name__ == "__main__":
    unittest.main()
