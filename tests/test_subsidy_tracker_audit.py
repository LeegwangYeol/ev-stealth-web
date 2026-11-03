"""Comprehensive Audit and Verification Test Suite for tracker/subsidy_tracker.py.

Verifies:
1. Depletion calculation math: (applied / quota) * 100, zero division guard, negative quota/applied.
2. Clamping of depletion rate to [0.0, 100.0] and handling over-exhaustion (>100% when waitlisted).
3. Remaining unit arithmetic: max(0, quota - applied) and delivered tracking (delivery rate, pending deliveries, waitlist units).
4. Regional grouping: Metropolitan cities (8: 서울, 부산, 대구, 인천, 광주, 대전, 울산, 세종), Provinces (9: 경기, 강원, 충북, 충남, 전북, 전남, 경북, 경남, 제주).
5. Fallback baseline data generation, error recovery when live fetch fails.
"""

from __future__ import annotations

import math
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from tracker.subsidy_models import AlertSeverity, RegionRecord, SubsidyPayload
from tracker.subsidy_tracker import (
    METROPOLITAN_CITIES,
    METROPOLITAN_CITY_CODES,
    PROVINCES,
    PROVINCE_CODES,
    REGIONAL_GROUP_METROPOLITAN,
    REGIONAL_GROUP_PROVINCES,
    SubsidyTracker,
    calculate_delivery_rate,
    calculate_depletion_rate,
    calculate_pending_deliveries,
    calculate_remaining_units,
    calculate_waitlist_units,
    classify_alert_tier,
    classify_region_group,
    generate_fallback_payload,
    get_baseline_dataset,
    get_baseline_regions,
    group_regions_by_category,
    group_regions_by_type,
    is_depletion_over_exhausted,
    is_metropolitan_city,
    is_province,
)


class TestSubsidyTrackerAudit(unittest.TestCase):
    """Test suite covering the 5 checklist audit domains for subsidy_tracker.py."""

    def setUp(self) -> None:
        self.tracker = SubsidyTracker()

    # ========================================================================
    # 1. Depletion calculation math & Zero-Division / Negative handling
    # ========================================================================

    def test_01_depletion_math_basic_and_rounding(self) -> None:
        """(applied / quota) * 100 rounded to 1 decimal place."""
        self.assertEqual(calculate_depletion_rate(50, 100), 50.0)
        self.assertEqual(calculate_depletion_rate(33, 100), 33.0)
        self.assertEqual(calculate_depletion_rate(1, 3), 33.3)
        self.assertEqual(calculate_depletion_rate(2, 3), 66.7)
        self.assertEqual(calculate_depletion_rate(applied=75, quota=150), 50.0)
        self.assertEqual(calculate_depletion_rate(applied=9890, announced=11500), 86.0)

    def test_02_depletion_math_zero_and_negative_quota(self) -> None:
        """Quota <= 0 or applied <= 0 must return 0.0 without ZeroDivisionError."""
        self.assertEqual(calculate_depletion_rate(0, 0), 0.0)
        self.assertEqual(calculate_depletion_rate(100, 0), 0.0)
        self.assertEqual(calculate_depletion_rate(100, -50), 0.0)
        self.assertEqual(calculate_depletion_rate(0, 100), 0.0)
        self.assertEqual(calculate_depletion_rate(-50, 100), 0.0)
        self.assertEqual(calculate_depletion_rate(-20, -50), 0.0)
        self.assertEqual(calculate_depletion_rate(applied=100, quota=0), 0.0)
        self.assertEqual(calculate_depletion_rate(applied=100, quota=-10), 0.0)

    def test_03_depletion_math_nan_inf_and_malformed(self) -> None:
        """Gracefully return 0.0 on NaN, Inf, None, and unparseable values."""
        self.assertEqual(calculate_depletion_rate(float("nan"), 100), 0.0)
        self.assertEqual(calculate_depletion_rate(50, float("nan")), 0.0)
        self.assertEqual(calculate_depletion_rate(float("inf"), 100), 0.0)
        self.assertEqual(calculate_depletion_rate(50, float("inf")), 0.0)
        self.assertEqual(calculate_depletion_rate(None, 100), 0.0)
        self.assertEqual(calculate_depletion_rate(50, None), 0.0)
        self.assertEqual(calculate_depletion_rate("corrupt", 100), 0.0)
        self.assertEqual(calculate_depletion_rate(50, "invalid"), 0.0)

    # ========================================================================
    # 2. Clamping and Over-exhaustion (>100% when waitlisted)
    # ========================================================================

    def test_04_depletion_over_exhaustion_unclamped_by_default(self) -> None:
        """Default calculate_depletion_rate preserves over-exhaustion (>100.0%)."""
        rate_125 = calculate_depletion_rate(125, 100)
        self.assertEqual(rate_125, 125.0)
        self.assertTrue(is_depletion_over_exhausted(rate_125))

        rate_250 = calculate_depletion_rate(250, 100)
        self.assertEqual(rate_250, 250.0)
        self.assertTrue(is_depletion_over_exhausted(rate_250))

        # Status for over-exhausted rates should classify as DEPLETED
        self.assertEqual(classify_alert_tier(rate_125), "DEPLETED")
        self.assertEqual(classify_alert_tier(rate_250), "DEPLETED")

    def test_05_depletion_clamping_to_100_when_requested(self) -> None:
        """clamp_100=True or clamp=True strictly restricts rate to [0.0, 100.0]."""
        self.assertEqual(calculate_depletion_rate(150, 100, clamp_100=True), 100.0)
        self.assertEqual(calculate_depletion_rate(250, 100, clamp=True), 100.0)
        self.assertEqual(calculate_depletion_rate(50, 100, clamp_100=True), 50.0)
        self.assertEqual(calculate_depletion_rate(-10, 100, clamp_100=True), 0.0)
        self.assertEqual(calculate_depletion_rate(applied=200, quota=100, clamp_100=True), 100.0)

    def test_06_waitlist_units_calculation(self) -> None:
        """calculate_waitlist_units returns max(0, applied - quota)."""
        self.assertEqual(calculate_waitlist_units(150, 100), 50)
        self.assertEqual(calculate_waitlist_units(100, 100), 0)
        self.assertEqual(calculate_waitlist_units(80, 100), 0)
        self.assertEqual(calculate_waitlist_units(applied=300, quota=200), 100)
        self.assertEqual(calculate_waitlist_units(-10, 100), 0)
        self.assertEqual(calculate_waitlist_units(100, -10), 100)
        self.assertEqual(calculate_waitlist_units(None, 100), 0)

    # ========================================================================
    # 3. Remaining unit arithmetic & delivered tracking
    # ========================================================================

    def test_07_remaining_units_clamping_and_arithmetic(self) -> None:
        """calculate_remaining_units returns max(0, quota - applied)."""
        self.assertEqual(calculate_remaining_units(40, 100), 60)
        self.assertEqual(calculate_remaining_units(100, 100), 0)
        self.assertEqual(calculate_remaining_units(150, 100), 0)
        self.assertEqual(calculate_remaining_units(applied=30, quota=100), 70)
        self.assertEqual(calculate_remaining_units(applied=120, quota=100), 0)
        self.assertEqual(calculate_remaining_units(-20, 100), 100)
        self.assertEqual(calculate_remaining_units(50, -10), 0)
        self.assertEqual(calculate_remaining_units(0, 0), 0)
        self.assertEqual(calculate_remaining_units(None, 100), 0)
        self.assertEqual(calculate_remaining_units(50, None), 0)

    def test_08_delivery_tracking_rates_and_pending(self) -> None:
        """Test delivered tracking: delivery rate and pending delivery arithmetic."""
        # 80 delivered out of 100 announced
        self.assertEqual(calculate_delivery_rate(80, 100), 80.0)
        self.assertEqual(calculate_delivery_rate(delivered=70, quota=100), 70.0)
        self.assertEqual(calculate_delivery_rate(0, 100), 0.0)
        self.assertEqual(calculate_delivery_rate(50, 0), 0.0)

        # Pending delivery units: max(0, applied - delivered)
        self.assertEqual(calculate_pending_deliveries(100, 80), 20)
        self.assertEqual(calculate_pending_deliveries(80, 80), 0)
        self.assertEqual(calculate_pending_deliveries(50, 80), 0)
        self.assertEqual(calculate_pending_deliveries(None, 50), 0)
        self.assertEqual(calculate_pending_deliveries(50, None), 0)

    def test_09_category_metrics_delivered_tracking(self) -> None:
        """SubsidyTracker.calculate_category_metrics computes both depletion and delivery rates."""
        metrics = self.tracker.calculate_category_metrics(
            announced=1000,
            applied=850,
            delivered=700,
            max_local_subsidy=3_000_000,
        )
        self.assertEqual(metrics.announced_units, 1000)
        self.assertEqual(metrics.applied_units, 850)
        self.assertEqual(metrics.delivered_units, 700)
        self.assertEqual(metrics.remaining_units, 150)
        self.assertEqual(metrics.depletion_rate, 85.0)
        self.assertEqual(metrics.delivery_rate, 70.0)
        self.assertEqual(metrics.status, "WARNING")

    # ========================================================================
    # 4. Regional grouping: Metropolitan Cities (8) vs Provinces (9)
    # ========================================================================

    def test_10_regional_grouping_classification(self) -> None:
        """Verify 8 Metropolitan Cities and 9 Provinces classification."""
        expected_metros = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종"]
        expected_provinces = ["경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]

        self.assertEqual(len(METROPOLITAN_CITIES), 8)
        self.assertEqual(len(PROVINCES), 9)
        self.assertEqual(list(METROPOLITAN_CITIES), expected_metros)
        self.assertEqual(list(PROVINCES), expected_provinces)

        for city in expected_metros:
            with self.subTest(city=city):
                self.assertTrue(is_metropolitan_city(city))
                self.assertFalse(is_province(city))
                self.assertEqual(classify_region_group(city), REGIONAL_GROUP_METROPOLITAN)

        for prov in expected_provinces:
            with self.subTest(province=prov):
                self.assertTrue(is_province(prov))
                self.assertFalse(is_metropolitan_city(prov))
                self.assertEqual(classify_region_group(prov), REGIONAL_GROUP_PROVINCES)

    def test_11_regional_grouping_by_iso_codes(self) -> None:
        """Verify classification by ISO codes."""
        for code in METROPOLITAN_CITY_CODES:
            with self.subTest(code=code):
                self.assertTrue(is_metropolitan_city(code))
                self.assertEqual(classify_region_group(code), REGIONAL_GROUP_METROPOLITAN)

        for code in PROVINCE_CODES:
            with self.subTest(code=code):
                self.assertTrue(is_province(code))
                self.assertEqual(classify_region_group(code), REGIONAL_GROUP_PROVINCES)

    def test_12_group_regions_by_type_all_17(self) -> None:
        """group_regions_by_type partitions 17 baseline regions into 8 metros and 9 provinces."""
        baseline_regions = get_baseline_regions()
        self.assertEqual(len(baseline_regions), 17)

        grouped = group_regions_by_type(baseline_regions)
        metros = grouped[REGIONAL_GROUP_METROPOLITAN]
        provinces = grouped[REGIONAL_GROUP_PROVINCES]

        self.assertEqual(len(metros), 8)
        self.assertEqual(len(provinces), 9)
        self.assertEqual(len(metros) + len(provinces), 17)

        metro_names = [r.name_ko for r in metros]
        self.assertTrue(any("서울" in n for n in metro_names))
        self.assertTrue(any("부산" in n for n in metro_names))
        self.assertTrue(any("대구" in n for n in metro_names))
        self.assertTrue(any("인천" in n for n in metro_names))
        self.assertTrue(any("광주" in n for n in metro_names))
        self.assertTrue(any("대전" in n for n in metro_names))
        self.assertTrue(any("울산" in n for n in metro_names))
        self.assertTrue(any("세종" in n for n in metro_names))

        prov_names = [r.name_ko for r in provinces]
        self.assertTrue(any("경기" in n for n in prov_names))
        self.assertTrue(any("강원" in n for n in prov_names))
        self.assertTrue(any("충청북" in n or "충북" in n for n in prov_names))
        self.assertTrue(any("충청남" in n or "충남" in n for n in prov_names))
        self.assertTrue(any("전북" in n for n in prov_names))
        self.assertTrue(any("전라남" in n or "전남" in n for n in prov_names))
        self.assertTrue(any("경상북" in n or "경북" in n for n in prov_names))
        self.assertTrue(any("경상남" in n or "경남" in n for n in prov_names))
        self.assertTrue(any("제주" in n for n in prov_names))

    def test_13_compute_regional_group_summaries(self) -> None:
        """SubsidyTracker.compute_regional_group_summaries computes aggregates per group."""
        summaries = self.tracker.compute_regional_group_summaries()
        self.assertIn("metropolitan_cities", summaries)
        self.assertIn("provinces", summaries)

        metro_sum = summaries["metropolitan_cities"]
        prov_sum = summaries["provinces"]

        self.assertEqual(metro_sum["region_count"], 8)
        self.assertEqual(prov_sum["region_count"], 9)
        self.assertGreater(metro_sum["total_announced_units"], 0)
        self.assertGreater(prov_sum["total_announced_units"], 0)
        self.assertGreaterEqual(metro_sum["total_delivered_units"], 0)
        self.assertGreaterEqual(prov_sum["total_delivered_units"], 0)
        self.assertGreaterEqual(metro_sum["depletion_rate"], 0.0)
        self.assertGreaterEqual(prov_sum["depletion_rate"], 0.0)

    # ========================================================================
    # 5. Fallback baseline data generation & Error recovery
    # ========================================================================

    def test_14_generate_fallback_payload_completeness(self) -> None:
        """generate_fallback_payload creates authoritative dataset with 17 regions and nationwide summary."""
        payload = generate_fallback_payload()
        self.assertIsInstance(payload, SubsidyPayload)
        self.assertEqual(len(payload.regions), 17)
        self.assertIsNotNone(payload.nationwide_summary)
        self.assertGreater(payload.nationwide_summary.total_announced_units, 0)
        self.assertGreater(payload.nationwide_summary.total_applied_units, 0)
        self.assertGreater(payload.nationwide_summary.total_delivered_units, 0)
        self.assertGreater(payload.nationwide_summary.nationwide_depletion_rate, 0.0)
        self.assertGreaterEqual(len(payload.popular_models_matrix), 8)

    @patch("urllib.request.urlopen")
    def test_15_network_fetch_failure_fallback_recovery(self, mock_urlopen: MagicMock) -> None:
        """SubsidyTracker gracefully falls back to baseline dataset when live network fetch fails."""
        mock_urlopen.side_effect = urllib.error.URLError("Network unreachable (503 Service Unavailable)")

        tracker = SubsidyTracker(endpoint_url="https://api.example.com/subsidy/live")
        payload, fallback_used = tracker.execute_tracking_cycle()

        self.assertTrue(fallback_used)
        self.assertIsInstance(payload, SubsidyPayload)
        self.assertEqual(len(payload.regions), 17)
        self.assertGreater(payload.nationwide_summary.total_announced_units, 0)


if __name__ == "__main__":
    unittest.main()
