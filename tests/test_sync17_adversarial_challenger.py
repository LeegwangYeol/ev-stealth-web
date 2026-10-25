"""tests/test_sync17_adversarial_challenger.py - Cycle 17 Adversarial Edge Cases & Fuzzing Challenger Suite.

Authored by sync17_challenger_edge_cases_w3 (Empirical Challenger, Wave 3).
Adversarially stresses and fuzzes the entire system against:
1. Extreme numeric inputs (0, negative, >100M KRW, 10^18 KRW, float NaN / +Inf / -Inf)
2. Corrupt date formats, empty strings, spaced dot strings ('YYYY. MM. DD.', 'YYYY. M. D.')
3. Raw dictionary payloads vs domain dataclass objects across all tracker and report functions
4. Unrecognized regional codes, invalid query parameters, and boundary conditions
5. Automated high-volume pseudorandom fuzzing generators and oracles
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import random
import re
import string
import sys
import tempfile
import unittest
from unittest.mock import patch
from typing import Any, Dict, List, Optional, Union

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Backend modules under test
from models.complaint import ComplaintRecord, DSIBreakdown, DailyReportPayload, DailyReportStatistics, RawPost
from tracker.defect_tracker import DefectTracker, _extract_val, _to_record_dict
from tracker.report_generator import ReportGenerator, _get_field, _metric_val, _safe_float_val, _safe_int_val
import tracker.subsidy_baseline as subsidy_baseline
from tracker.subsidy_models import (
    AlertSeverity,
    CategoryMetrics,
    MunicipalityMetrics,
    NationwideSummary,
    PopularModelEntry,
    RegionRecord,
    SubsidyMetadata,
    SubsidyPayload,
)
from tracker.subsidy_tracker import (
    SubsidyTracker,
    calculate_depletion_rate,
    calculate_price_cap_ratio,
    calculate_remaining_units,
    classify_alert_tier,
)


class TestExtremeNumericInputsAndBounds(unittest.TestCase):
    """Suite 1: Extreme numeric inputs, negative clamping, zero division, and IEEE 754 NaN/Inf resilience."""

    def test_01_calculate_depletion_rate_extreme_inputs(self) -> None:
        """calculate_depletion_rate handles 0, negatives, huge numbers, NaN, and Inf without throwing."""
        extreme_cases = [
            (0, 0, 0.0),
            (0, 100, 0.0),
            (100, 0, 0.0),
            (-50, 100, 0.0),
            (100, -50, 0.0),
            (-100, -100, 0.0),
            (None, 100, 0.0),
            (100, None, 0.0),
            (None, None, 0.0),
            (float("nan"), 100, 0.0),
            (100, float("nan"), 0.0),
            (float("nan"), float("nan"), 0.0),
            (float("inf"), 100, 0.0),
            (100, float("inf"), 0.0),
            (float("-inf"), 100, 0.0),
            (100, float("-inf"), 0.0),
        ]
        for applied, announced, expected in extreme_cases:
            with self.subTest(applied=applied, announced=announced):
                res = calculate_depletion_rate(applied, announced)
                self.assertIsInstance(res, float)
                self.assertEqual(res, expected)
                self.assertFalse(math.isnan(res))
                self.assertFalse(math.isinf(res))

        # Astronomical quota (10^15)
        rate_astro = calculate_depletion_rate(5 * 10**14, 10**15)
        self.assertEqual(rate_astro, 50.0)

        # Oversubscription (200 applied on 100 quota -> 200.0%)
        rate_over = calculate_depletion_rate(200, 100)
        self.assertEqual(rate_over, 200.0)

    def test_02_calculate_remaining_units_extreme_inputs(self) -> None:
        """calculate_remaining_units handles 0, negatives, oversubscription, and NaN/Inf."""
        remaining_cases = [
            (0, 0, 0),
            (0, 100, 100),
            (100, 0, 0),
            (-10, 100, 100),  # Negative applied is clamped to 0
            (100, -10, 0),    # Negative announced is clamped to 0
            (-10, -10, 0),
            (None, 100, 0),
            (100, None, 0),
            (None, None, 0),
            (float("nan"), 100, 0),
            (100, float("nan"), 0),
            (float("inf"), 100, 0),
            (100, float("inf"), 0),
            (200, 100, 0),    # Overapplied: clamped at 0
        ]
        for applied, announced, expected in remaining_cases:
            with self.subTest(applied=applied, announced=announced):
                rem = calculate_remaining_units(applied, announced)
                self.assertIsInstance(rem, int)
                self.assertEqual(rem, expected)

        # Huge values (10^12)
        rem_huge = calculate_remaining_units(7 * 10**11, 10**12)
        self.assertEqual(rem_huge, 3 * 10**11)

    def test_03_calculate_price_cap_ratio_statutory_tiers(self) -> None:
        """calculate_price_cap_ratio strictly adheres to 2026 Korean EV subsidy tiers."""
        # 1.0 tier (0 < MSRP <= 55,000,000 KRW)
        self.assertEqual(calculate_price_cap_ratio(30_000_000), 1.0)
        self.assertEqual(calculate_price_cap_ratio(55_000_000), 1.0)

        # 0.5 tier (55,000,001 to 85,000,000 KRW)
        self.assertEqual(calculate_price_cap_ratio(55_000_001), 0.5)
        self.assertEqual(calculate_price_cap_ratio(70_000_000), 0.5)
        self.assertEqual(calculate_price_cap_ratio(85_000_000), 0.5)

        # 0.0 tier (> 85,000,000 KRW)
        self.assertEqual(calculate_price_cap_ratio(85_000_001), 0.0)
        self.assertEqual(calculate_price_cap_ratio(100_000_000), 0.0)
        self.assertEqual(calculate_price_cap_ratio(1_000_000_000), 0.0)
        self.assertEqual(calculate_price_cap_ratio(10**15), 0.0)

        # Edge cases & invalid types (including non-positive MSRP guard)
        self.assertEqual(calculate_price_cap_ratio(0), 0.0)  # Non-positive guard
        self.assertEqual(calculate_price_cap_ratio(-50_000_000), 0.0)  # Negative price guard
        self.assertEqual(calculate_price_cap_ratio(None), 0.0)  # type: ignore[arg-type]
        self.assertEqual(calculate_price_cap_ratio(float("nan")), 0.0)  # type: ignore[arg-type]
        self.assertEqual(calculate_price_cap_ratio(float("inf")), 0.0)  # type: ignore[arg-type]

    def test_04_calculate_net_subsidy_extreme_inputs(self) -> None:
        """subsidy_baseline.calculate_net_subsidy handles zero, negative, extreme and None inputs."""
        # Standard case: 50M KRW (100% tier)
        net = subsidy_baseline.calculate_net_subsidy(6_500_000, 6_500_000, 3_500_000, 50_000_000)
        self.assertIsInstance(net, dict)
        self.assertEqual(net["total_subsidy_krw"], 10_000_000)
        self.assertEqual(net["net_price_krw"], 40_000_000)

        # 50% cap tier: 70M KRW
        net_half = subsidy_baseline.calculate_net_subsidy(6_500_000, 6_500_000, 3_500_000, 70_000_000)
        self.assertEqual(net_half["total_subsidy_krw"], 5_000_000)
        self.assertEqual(net_half["net_price_krw"], 65_000_000)

        # 0% cap tier: 90M KRW (>85M)
        net_zero = subsidy_baseline.calculate_net_subsidy(6_500_000, 6_500_000, 3_500_000, 90_000_000)
        self.assertEqual(net_zero["total_subsidy_krw"], 0)
        self.assertEqual(net_zero["net_price_krw"], 90_000_000)

        # None / NaN inputs
        net_none = subsidy_baseline.calculate_net_subsidy(None, None, None, None)  # type: ignore[arg-type]
        self.assertEqual(net_none["total_subsidy_krw"], 0)
        self.assertEqual(net_none["net_price_krw"], 0)

        net_nan = subsidy_baseline.calculate_net_subsidy(float("nan"), 1_000_000, 500_000, 50_000_000)  # type: ignore[arg-type]
        self.assertEqual(net_nan["total_subsidy_krw"], 0)

        # Extreme values (>100M KRW, 10^12 KRW)
        net_huge = subsidy_baseline.calculate_net_subsidy(10**9, 10**9, 10**9, 50_000_000)
        self.assertEqual(net_huge["total_subsidy_krw"], 2 * 10**9)

    def test_05_dsi_breakdown_nan_inf_none_resilience(self) -> None:
        """DSIBreakdown.to_dict() cleanses None, NaN, Inf, and strings into safe 0.0 floats."""
        dsi = DSIBreakdown(
            safety=float("nan"),
            functional=float("inf"),
            economic=float("-inf"),
            social=None,  # type: ignore[arg-type]
            convenience="corrupt_string",  # type: ignore[arg-type]
        )
        d = dsi.to_dict()
        self.assertEqual(d["safety"], 0.0)
        self.assertEqual(d["functional"], 0.0)
        self.assertEqual(d["economic"], 0.0)
        self.assertEqual(d["social"], 0.0)
        self.assertEqual(d["convenience"], 0.0)

        # Strict JSON serialization must succeed with allow_nan=False
        serialized = json.dumps(d, allow_nan=False)
        self.assertIn('"safety": 0.0', serialized)

    def test_06_complaint_record_severity_and_sentiment_tier_bounds(self) -> None:
        """ComplaintRecord severity_tier and sentiment_tier handle NaN, Inf, None and continuous boundaries."""
        # Severity Index tests
        c_nan = ComplaintRecord(
            id="c1", source="test", url="", title="", author="", created_at="",
            vehicle_brand="Hyundai", vehicle_model="Ioniq 5", defect_category="BATTERY_CHARGING",
            summary="", verbatim_quote="", severity_index=float("nan"),
        )
        self.assertEqual(c_nan.severity_tier, "LOW")

        c_inf = ComplaintRecord(
            id="c2", source="test", url="", title="", author="", created_at="",
            vehicle_brand="Hyundai", vehicle_model="Ioniq 5", defect_category="BATTERY_CHARGING",
            summary="", verbatim_quote="", severity_index=float("inf"),
        )
        self.assertEqual(c_inf.severity_tier, "LOW")

        c_none = ComplaintRecord(
            id="c3", source="test", url="", title="", author="", created_at="",
            vehicle_brand="Hyundai", vehicle_model="Ioniq 5", defect_category="BATTERY_CHARGING",
            summary="", verbatim_quote="", severity_index=None,  # type: ignore[arg-type]
        )
        self.assertEqual(c_none.severity_tier, "LOW")

        # Boundary values: 0, 3.99, 4.0, 5.99, 6.0, 7.99, 8.0, 10.0
        tiers = [
            (0.0, "LOW"),
            (3.99, "LOW"),
            (4.0, "MEDIUM"),
            (5.99, "MEDIUM"),
            (6.0, "HIGH"),
            (7.99, "HIGH"),
            (8.0, "CRITICAL"),
            (10.0, "CRITICAL"),
            (9999.0, "CRITICAL"),
        ]
        for score, expected_tier in tiers:
            rec = ComplaintRecord(
                id="c", source="test", url="", title="", author="", created_at="",
                vehicle_brand="Hyundai", vehicle_model="Ioniq 5", defect_category="BATTERY_CHARGING",
                summary="", verbatim_quote="", severity_index=score,
            )
            self.assertEqual(rec.severity_tier, expected_tier)

        # Sentiment Polarity tests
        polarities = [
            (float("nan"), "NEUTRAL"),
            (float("inf"), "NEUTRAL"),
            (None, "NEUTRAL"),
            (-1.0, "STRONGLY_NEGATIVE"),
            (-0.70, "STRONGLY_NEGATIVE"),
            (-0.69, "NEGATIVE"),
            (-0.30, "NEGATIVE"),
            (-0.29, "NEUTRAL"),
            (0.29, "NEUTRAL"),
            (0.30, "POSITIVE"),
            (1.0, "POSITIVE"),
        ]
        for pol, expected_sent in polarities:
            rec_p = ComplaintRecord(
                id="p", source="test", url="", title="", author="", created_at="",
                vehicle_brand="Tesla", vehicle_model="Model Y", defect_category="SOFTWARE_ELECTRONICS",
                summary="", verbatim_quote="", sentiment_polarity=pol,  # type: ignore[arg-type]
            )
            self.assertEqual(rec_p.sentiment_tier, expected_sent)


class TestDateParsingAndCorruptStrings(unittest.TestCase):
    """Suite 2: Corrupt dates, spaced dot dates, empty dates, and malformed strings."""

    def test_07_korean_spaced_dot_and_slash_date_parsing(self) -> None:
        """ComplaintRecord.date_str parses Korean spaced dot strings, compact dots, slashes, and dashes."""
        test_dates = [
            ("2026. 10. 25.", "2026-10-25"),
            ("2026. 9. 8.", "2026-09-08"),
            ("2026.10.25", "2026-10-25"),
            ("2026. 01. 05.", "2026-01-05"),
            ("2026/10/25", "2026-10-25"),
            ("2026/9/8", "2026-09-08"),
            ("2026-10-25", "2026-10-25"),
            ("2026. 10. 25 14:30:00", "2026-10-25"),
            ("2026/10/25 14:30:00", "2026-10-25"),
            ("2026-10-25 14:30:00", "2026-10-25"),
            ("2026-10-25T14:30:00Z", "2026-10-25"),
            ("2026-10-25T14:30:00+09:00", "2026-10-25"),
        ]
        for raw, expected in test_dates:
            with self.subTest(raw=raw):
                rec = ComplaintRecord(
                    id="date-test", source="bobaedream", url="", title="", author="",
                    created_at=raw, vehicle_brand="Hyundai", vehicle_model="Ioniq 5",
                    defect_category="BATTERY_CHARGING", summary="", verbatim_quote="",
                )
                self.assertEqual(rec.date_str, expected)

    def test_08_corrupt_date_fallback_to_today(self) -> None:
        """ComplaintRecord.date_str falls back to today's date for corrupt, empty, None, and garbage strings."""
        corrupt_inputs = [
            "",
            "   ",
            None,
            "not_a_date_at_all",
            "abc.def.ghi",
            "99999999",
            123456789,  # type: ignore[arg-type]
            [],  # type: ignore[arg-type]
        ]
        for c_input in corrupt_inputs:
            with self.subTest(c_input=c_input):
                rec = ComplaintRecord(
                    id="corrupt-date", source="dcinside", url="", title="", author="",
                    created_at=c_input,  # type: ignore[arg-type]
                    vehicle_brand="Kia", vehicle_model="EV6",
                    defect_category="DRIVING_POWERTRAIN", summary="", verbatim_quote="",
                )
                res = rec.date_str
                self.assertIsInstance(res, str)
                # Must be a valid 10-char date string format YYYY-MM-DD
                self.assertRegex(res, r"^\d{4}-\d{2}-\d{2}$")


class TestPolymorphismAndDuckTypingAcrossTrackers(unittest.TestCase):
    """Suite 3: Raw dictionary payloads vs domain dataclass objects across all tracker functions."""

    def setUp(self) -> None:
        self.tracker = SubsidyTracker()
        self.report_gen = ReportGenerator()

    def test_09_compute_nationwide_summary_mixed_dict_and_dataclass(self) -> None:
        """compute_nationwide_summary seamlessly aggregates mixed lists of RegionRecord and raw dicts."""
        # 1. Full RegionRecord with CategoryMetrics
        r1 = RegionRecord(
            region_id="KR-11",
            name_ko="서울특별시",
            name_en="Seoul",
            overall_status="HEALTHY",
            overall_depletion_rate=50.0,
            categories={
                "passenger": CategoryMetrics.from_dict({
                    "announced_units": 1000,
                    "applied_units": 500,
                    "delivered_units": 400,
                    "remaining_units": 500,
                    "depletion_rate": 50.0,
                    "delivery_rate": 40.0,
                    "status": "HEALTHY",
                    "max_local_subsidy_krw": 1_500_000,
                    "max_total_subsidy_krw": 8_000_000,
                    "total_budget_krw": 8_000_000_000,
                    "remaining_budget_krw": 4_000_000_000,
                })
            },
        )

        # 2. RegionRecord with raw dictionary categories
        r2 = RegionRecord(
            region_id="KR-26",
            name_ko="부산광역시",
            name_en="Busan",
            overall_status="WARNING",
            overall_depletion_rate=80.0,
            categories={
                "passenger": {
                    "announced_units": 500,
                    "applied_units": 400,
                    "delivered_units": 350,
                    "remaining_units": 100,
                    "depletion_rate": 80.0,
                    "delivery_rate": 70.0,
                    "status": "WARNING",
                    "total_budget_krw": 4_000_000_000,
                    "remaining_budget_krw": 800_000_000,
                }
            },
        )

        # 3. Raw dictionary representing a region with dictionary categories
        r3_dict = {
            "region_id": "KR-49",
            "name_ko": "제주특별자치도",
            "name_en": "Jeju",
            "overall_status": "CRITICAL",
            "overall_depletion_rate": 99.0,
            "categories": {
                "passenger": {
                    "announced_units": 500,
                    "applied_units": 495,
                    "delivered_units": 450,
                    "remaining_units": 5,
                    "depletion_rate": 99.0,
                    "total_budget_krw": 5_000_000_000,
                    "remaining_budget_krw": 50_000_000,
                }
            },
        }

        # 4. Region with None categories
        r4_none_cats = RegionRecord(
            region_id="KR-41",
            name_ko="경기도",
            name_en="Gyeonggi",
            overall_status="HEALTHY",
            categories=None,  # type: ignore[arg-type]
        )

        # 5. Empty dictionary
        r5_empty: Dict[str, Any] = {}

        mixed_regions = [r1, r2, r3_dict, r4_none_cats, r5_empty]
        summary = self.tracker.compute_nationwide_summary(mixed_regions)

        self.assertIsInstance(summary, NationwideSummary)
        # Expected announced: 1000 + 500 + 500 = 2000
        self.assertEqual(summary.total_announced_units, 2000)
        # Expected applied: 500 + 400 + 495 = 1395
        self.assertEqual(summary.total_applied_units, 1395)
        # Expected delivered: 400 + 350 + 450 = 1200
        self.assertEqual(summary.total_delivered_units, 1200)
        # Expected remaining: 2000 - 1395 = 605
        self.assertEqual(summary.total_remaining_units, 605)
        # Expected depletion rate: round(1395 / 2000 * 100, 1) = 69.8%
        self.assertEqual(summary.nationwide_depletion_rate, 69.8)

        # Expected budgets: total = (8B + 4B + 5B) / 10^9 = 17.0B KRW
        self.assertEqual(summary.total_budget_billion_krw, 17.0)

        # Alert counts
        self.assertEqual(summary.alert_region_counts["critical"], 1)
        self.assertEqual(summary.alert_region_counts["warning"], 1)

    def test_10_update_region_metrics_duck_typing(self) -> None:
        """SubsidyTracker.update_region_metrics operates on RegionRecord or dict with duck-typed categories."""
        # Case A: RegionRecord
        rec = RegionRecord(
            region_id="KR-11",
            name_ko="서울특별시",
            categories={
                "passenger": CategoryMetrics.from_dict({
                    "announced_units": 100,
                    "applied_units": 50,
                    "delivered_units": 40,
                    "total_budget_krw": 1_000_000_000,
                })
            },
        )
        res_rec = self.tracker.update_region_metrics(rec)
        self.assertIsInstance(res_rec, RegionRecord)
        self.assertEqual(res_rec.categories["passenger"].announced_units, 100)
        self.assertEqual(res_rec.categories["passenger"].applied_units, 50)
        self.assertEqual(res_rec.categories["passenger"].remaining_units, 50)
        self.assertEqual(res_rec.categories["passenger"].depletion_rate, 50.0)
        self.assertEqual(res_rec.overall_depletion_rate, 50.0)

        # Case B: dict region
        dict_region = {
            "region_id": "KR-26",
            "name_ko": "부산광역시",
            "categories": {
                "passenger": {
                    "announced_units": 100,
                    "applied_units": 80,
                    "delivered_units": 70,
                    "total_budget_krw": 800_000_000,
                }
            },
        }
        res_dict = self.tracker.update_region_metrics(dict_region)
        self.assertIsInstance(res_dict, dict)
        self.assertEqual(res_dict["categories"]["passenger"]["announced_units"], 100)
        self.assertEqual(res_dict["categories"]["passenger"]["applied_units"], 80)
        self.assertEqual(res_dict["categories"]["passenger"]["remaining_units"], 20)
        self.assertEqual(res_dict["categories"]["passenger"]["depletion_rate"], 80.0)
        self.assertEqual(res_dict["overall_depletion_rate"], 80.0)
        self.assertEqual(res_dict["overall_status"], "WARNING")

    def test_11_build_initial_baseline_with_dict_regions(self) -> None:
        """subsidy_baseline.build_initial_baseline accepts raw dictionary regions cleanly."""
        dict_regions = [
            {
                "region_id": "KR-11",
                "name_ko": "서울특별시",
                "overall_status": "healthy",
                "categories": {
                    "passenger": {"announced_units": 1000, "applied_units": 800, "delivered_units": 700},
                    "commercial": {"announced_units": 500, "applied_units": 400, "delivered_units": 350},
                },
            }
        ]
        payload = subsidy_baseline.build_initial_baseline(regions=dict_regions)
        self.assertIsInstance(payload, SubsidyPayload)
        self.assertEqual(len(payload.regions), 1)
        # Verify nationwide summary accurately computed from dict category metrics
        self.assertEqual(payload.nationwide_summary.total_announced_units, 1500)
        self.assertEqual(payload.nationwide_summary.total_applied_units, 1200)
        self.assertEqual(payload.nationwide_summary.total_remaining_units, 300)
        self.assertEqual(payload.nationwide_summary.nationwide_depletion_rate, 80.0)

    def test_12_subsidy_payload_and_region_record_to_dict_polymorphism(self) -> None:
        """SubsidyPayload.to_dict() and RegionRecord.to_dict() succeed when containing raw dicts."""
        # RegionRecord with dict categories and None
        r = RegionRecord(
            region_id="KR-99",
            name_ko="테스트지역",
            categories={
                "passenger": {"announced_units": 100, "applied_units": 50}  # dict instead of CategoryMetrics
            },
        )
        r_dict = r.to_dict()
        self.assertIsInstance(r_dict, dict)
        self.assertEqual(r_dict["categories"]["passenger"]["announced_units"], 100)

        # RegionRecord with categories=None
        r_none = RegionRecord(region_id="KR-00", name_ko="무카테고리", categories=None)  # type: ignore[arg-type]
        r_none_dict = r_none.to_dict()
        self.assertEqual(r_none_dict["categories"], {})

        # SubsidyPayload with raw dict regions and models
        payload = SubsidyPayload(
            metadata=SubsidyMetadata.from_dict({"generated_at": "2026-10-25T00:00:00Z"}),
            alert_thresholds={},
            historical_depletion_trajectory=[],
            regions=[{"region_id": "KR-11", "name_ko": "서울"}],  # type: ignore[list-item]
            nationwide_summary={"total_announced_units": 1000},  # type: ignore[arg-type]
            popular_models_matrix=[{"model_id": "ioniq-5-2026"}],  # type: ignore[list-item]
        )
        p_dict = payload.to_dict()
        self.assertIsInstance(p_dict, dict)
        self.assertEqual(p_dict["regions"][0]["region_id"], "KR-11")
        self.assertEqual(p_dict["nationwide_summary"]["total_announced_units"], 1000)
        self.assertEqual(p_dict["popular_models_matrix"][0]["model_id"], "ioniq-5-2026")

    def test_13_report_generator_subsidy_briefing_case_insensitivity_and_floats(self) -> None:
        """ReportGenerator.generate_subsidy_briefing handles lowercase statuses and preserves fractional billions."""
        payload_dict = {
            "metadata": {"generated_at": "2026-10-25T04:00:00Z"},
            "nationwide_summary": {
                "total_announced_units": 148510,
                "total_applied_units": 132766,
                "total_delivered_units": 122515,
                "total_remaining_units": 15744,
                "nationwide_depletion_rate": 89.4,
                "total_budget_billion_krw": 2105.1,
                "disbursed_budget_billion_krw": 1893.4,
                "budget_execution_rate": 89.94,
                "category_totals": {
                    "passenger": {"announced_units": 110400, "applied_units": 97035, "delivered_units": 88960, "remaining_units": 13365, "depletion_rate": 87.9},
                    "commercial": {"announced_units": 34800, "applied_units": 32754, "delivered_units": 30780, "remaining_units": 2046, "depletion_rate": 94.1},
                    "bus": {"announced_units": 3310, "applied_units": 2977, "delivered_units": 2775, "remaining_units": 333, "depletion_rate": 89.9},
                },
            },
            "regions": [
                {
                    "name_ko": "제주특별자치도",
                    "overall_status": "critical",  # Lowercase status!
                    "overall_depletion_rate": 99.0,
                    "categories": {"passenger": {"remaining_units": 40}},
                },
                {
                    "name_ko": "경상북도",
                    "overall_status": "CRITICAL",
                    "overall_depletion_rate": 97.3,
                    "categories": {"passenger": {"remaining_units": 216}},
                },
                {
                    "name_ko": "대구광역시",
                    "overall_status": "warning",  # Lowercase warning!
                    "overall_depletion_rate": 96.4,
                    "categories": {"passenger": {"remaining_units": 204}},
                },
            ],
        }

        briefing = self.report_gen.generate_subsidy_briefing(payload_dict)  # type: ignore[arg-type]
        self.assertIsInstance(briefing, str)
        # Must preserve decimal fractional budget: 1,893.4억 원 and 2,105.1억 원
        self.assertIn("1,893.4억 원", briefing)
        self.assertIn("2,105.1억 원", briefing)
        # Must capture lowercase 'critical' status in critical exhaustion section
        self.assertIn("제주특별자치도", briefing)
        self.assertIn("경상북도", briefing)
        # Must capture lowercase 'warning' status in warning section
        self.assertIn("대구광역시", briefing)

    def test_14_defect_tracker_domain_and_dict_polymorphism(self) -> None:
        """DefectTracker handles ComplaintRecord and plain dictionaries across query and statistics."""
        tracker = DefectTracker()

        # Build list of mixed objects: ComplaintRecord, plain dict with defect_category, plain dict with legacy category
        c_obj = ComplaintRecord(
            id="c-obj-1", source="bobaedream", url="https://example.com/1", title="ICCU 터짐",
            author="tester1", created_at="2026-10-25", vehicle_brand="Hyundai", vehicle_model="Ioniq 5",
            defect_category="BATTERY_CHARGING", summary="고속도로 멈춤", verbatim_quote="ICCU 터짐",
            severity_index=9.5, negativity_score=0.96, severity="CRITICAL",
        )
        c_dict1 = {
            "id": "c-dict-1", "source": "dcinside", "url": "https://example.com/2", "title": "OTA 벽돌",
            "author": "tester2", "created_at": "2026-10-24", "vehicle_brand": "Tesla", "vehicle_model": "Model Y",
            "defect_category": "SOFTWARE_ELECTRONICS", "summary": "블랙아웃", "verbatim_quote": "벽돌됨",
            "severity_index": 8.5, "negativity_score": 0.95, "severity": "CRITICAL",
        }
        c_dict2 = {
            "id": "c-dict-2", "source": "bobaedream", "url": "https://example.com/3", "title": "빗길 뒤 털림",
            "author": "tester3", "created_at": "2026-10-23", "vehicle_brand": "Kia", "vehicle_model": "EV3",
            "category": "DRIVING_POWERTRAIN",  # Legacy key!
            "summary": "피쉬테일", "verbatim_quote": "가드레일 박을 뻔",
            "severity_index": 8.0, "negativity_score": 0.94, "severity": "CRITICAL",
        }

        # Verify helper extract and to_record_dict functions
        self.assertEqual(_extract_val(c_obj, "defect_category"), "BATTERY_CHARGING")
        self.assertEqual(_extract_val(c_dict1, "defect_category"), "SOFTWARE_ELECTRONICS")
        self.assertEqual(_extract_val(c_dict2, "category"), "DRIVING_POWERTRAIN")

        dict_from_obj = _to_record_dict(c_obj)
        self.assertIsInstance(dict_from_obj, dict)
        self.assertEqual(dict_from_obj["id"], "c-obj-1")

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as tf:
            json.dump({
                "reports": [_to_record_dict(c_obj), c_dict1, c_dict2],
                "statistics": {
                    "total_filtered_defects": 3,
                    "critical_defect_count": 3,
                    "avg_negativity_score": 0.95,
                    "category_distribution": {"BATTERY_CHARGING": 1, "SOFTWARE_ELECTRONICS": 1, "DRIVING_POWERTRAIN": 1},
                },
            }, tf)
            tf_path = Path(tf.name)

        try:
            # 1. Query by category (both BATTERY_CHARGING and DRIVING_POWERTRAIN)
            q_batt = tracker.query_defects(file_path=tf_path, category="BATTERY_CHARGING")
            self.assertEqual(len(q_batt), 1)
            self.assertEqual(q_batt[0]["id"], "c-obj-1")

            q_driv = tracker.query_defects(file_path=tf_path, category="DRIVING_POWERTRAIN")
            self.assertEqual(len(q_driv), 1)
            self.assertEqual(q_driv[0]["id"], "c-dict-2")

            # 2. Query with negative and zero limit
            self.assertEqual(tracker.query_defects(file_path=tf_path, limit=0), [])
            self.assertEqual(tracker.query_defects(file_path=tf_path, limit=-5), [])

            # 3. get_statistics
            stats = tracker.get_statistics(file_path=tf_path)
            self.assertIsInstance(stats, dict)
            self.assertEqual(stats["total_filtered_defects"], 3)
            self.assertIn("category_distribution", stats)
            self.assertIn("BATTERY_CHARGING", stats["category_distribution"])
            self.assertIn("SOFTWARE_ELECTRONICS", stats["category_distribution"])
            self.assertIn("DRIVING_POWERTRAIN", stats["category_distribution"])
            self.assertFalse(math.isnan(stats["avg_negativity_score"]))
            self.assertEqual(stats["avg_negativity_score"], 0.95)
        finally:
            if tf_path.exists():
                tf_path.unlink()


class TestAutomatedGenerativeFuzzing(unittest.TestCase):
    """Suite 4: Automated Generative Fuzzing Harness."""

    def test_15_fuzz_calculate_depletion_rate_1000_cycles(self) -> None:
        """Fuzz calculate_depletion_rate with 1,000 pseudorandom adversarial pairs."""
        rng = random.Random(42)
        random_candidates = [
            0, -1, -999999, 1, 100, 1000, 10**6, 10**12, 10**18,
            float("nan"), float("inf"), float("-inf"), None,
            "100", "-50", "abc", 1e-10, -1e-10, 0.00001,
        ]

        for _ in range(1000):
            # Either pick a special candidate or a random float
            if rng.random() < 0.5:
                applied = rng.choice(random_candidates)
            else:
                applied = rng.uniform(-1e12, 1e12)

            if rng.random() < 0.5:
                announced = rng.choice(random_candidates)
            else:
                announced = rng.uniform(-1e12, 1e12)

            rate = calculate_depletion_rate(applied, announced)
            self.assertIsInstance(rate, float)
            self.assertFalse(math.isnan(rate), f"Returned NaN on applied={applied}, announced={announced}")
            self.assertFalse(math.isinf(rate), f"Returned Inf on applied={applied}, announced={announced}")
            self.assertGreaterEqual(rate, 0.0, f"Returned negative rate {rate} on applied={applied}, announced={announced}")

    def test_16_fuzz_calculate_remaining_units_1000_cycles(self) -> None:
        """Fuzz calculate_remaining_units with 1,000 pseudorandom adversarial pairs."""
        rng = random.Random(84)
        candidates = [
            0, -1, -1000, 1, 100, 1000, 10**9,
            float("nan"), float("inf"), float("-inf"), None,
            "0", "999", "invalid", 0.5, -0.5,
        ]

        for _ in range(1000):
            applied = rng.choice(candidates) if rng.random() < 0.5 else rng.randint(-10000, 100000)
            announced = rng.choice(candidates) if rng.random() < 0.5 else rng.randint(-10000, 100000)

            rem = calculate_remaining_units(applied, announced)
            self.assertIsInstance(rem, int)
            self.assertGreaterEqual(rem, 0, f"Returned negative remaining units {rem} on applied={applied}, announced={announced}")

    def test_17_fuzz_complaint_record_date_parsing_1000_cycles(self) -> None:
        """Fuzz ComplaintRecord.date_str with 1,000 randomized date and garbage strings."""
        rng = random.Random(168)
        supported_delimiters = [".", " . ", "-", "/", " / ", " - "]

        for _ in range(1000):
            mode = rng.randint(1, 5)
            if mode == 1:
                # Valid randomized calendar date with supported delimiters
                y = rng.randint(2020, 2030)
                m = rng.randint(1, 12)
                d = rng.randint(1, 28)
                delim = rng.choice(supported_delimiters)
                trailing = "." if rng.random() < 0.5 else ""
                created_at = f"{y}{delim}{m}{delim}{d}{trailing}"
                expected = f"{y:04d}-{m:02d}-{d:02d}"
            elif mode == 2:
                # Random ASCII/Korean/Unicode garbage
                length = rng.randint(0, 50)
                created_at = "".join(rng.choice(string.printable + "가나다라마바사!@#$%^&*()") for _ in range(length))
                expected = None  # May match regex or fallback
            elif mode == 3:
                # Out-of-range months/days
                created_at = f"{rng.randint(2020, 2030)}.{rng.randint(13, 99)}.{rng.randint(32, 99)}"
                expected = None
            elif mode == 4:
                # None or numbers
                created_at = rng.choice([None, 0, -1, 12345678, float("nan")])  # type: ignore[assignment]
                expected = None
            else:
                # Whitespace variations
                created_at = " " * rng.randint(0, 20)
                expected = None

            rec = ComplaintRecord(
                id="fuzz", source="fuzz", url="", title="", author="",
                created_at=created_at, vehicle_brand="BYD", vehicle_model="Atto 3",
                defect_category="BATTERY_CHARGING", summary="", verbatim_quote="",
            )
            parsed = rec.date_str
            self.assertIsInstance(parsed, str)
            self.assertRegex(parsed, r"^\d{4}-\d{2}-\d{2}$", f"Failed parsing date for input: {repr(created_at)}")
            if expected is not None:
                self.assertEqual(parsed, expected)


if __name__ == "__main__":
    unittest.main()
