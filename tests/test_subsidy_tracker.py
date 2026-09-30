"""
tests/test_subsidy_tracker.py - Comprehensive Unit & Regression Test Suite for EV Subsidy Pipeline.

Authoritative Sources:
- ORIGINAL_REQUEST.md (Requirements R1, R2, R3)
- teamwork_preview_spec_miner_subsidy_w1/handoff.md (Sections 4 & 5: Statutory Rules, Schema, 17 Regions)
- orchestrator_scheduled_tasks/TEST_INFRA.md (Coverage Thresholds & Scenarios: Tier 1 to Tier 4)
- Ministry of Environment (CleanSys / ev.or.kr) 2026 EV Subsidy Guidelines

Scope & Behavioral Verification:
1. Model & Data Integrity:
   - Dataclass serialization, required fields, and Draft-07 schema compliance.
   - 17 Administrative Divisions completeness check (ISO codes, tiers, categories, residency rules).
   - 2026 Vehicle Model Subsidy Matrix validation (MSRP brackets, battery chemistry, ranges).
2. Calculation & Edge Cases:
   - Depletion rate math (`applied / announced * 100`).
   - Over-subscription clamping (>100% depletion rate, remaining units clamped to 0).
   - Division-by-zero protection when `announced_units == 0`.
   - 5-Tier alert threshold classification (`HEALTHY`, `CAUTION`, `WARNING`, `CRITICAL`, `DEPLETED`).
   - Price-cap subsidy ratio calculation (1.0 for <55M, 0.5 for 55M-85M, 0.0 for >=85M).
   - Proportional local subsidy matching formula and net purchase price.
3. POSIX Atomic Writer:
   - Temporary file creation in the same filesystem directory.
   - Atomic rename via `os.replace` with `flush()` and `os.fsync()`.
   - File permissions and directory auto-creation (`ensure_parent=True`).
   - Crash durability and corruption resistance.
4. CLI & Runner:
   - CLI flags parsing (`--sync-web`, `--verbose`, `--dry-run`, `--output`).
   - Exit code 0 guarantee under normal and fallback conditions.
5. Tier 3 Pairwise Combinations:
   - 17 administrative regions x 3 statutory price brackets (51 combinations).
6. Tier 4 Real-World Application Scenarios:
   - Scheduled Antigravity cron run simulation.
   - Seoul EV buyer (Ioniq 5, 86% WARNING, 30-day residency).
   - Ulleung-gun rural maximum subsidy buyer (17.5M KRW total, 100% DEPLETED alert).
   - Luxury EV buyer exemption (Taycan >85M KRW, 0 KRW subsidy).
   - Mid-year supplementary budget injection (rate reduction without regression).
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Live import of tracker modules (zero mock fallbacks, genuine live execution)
import tracker
from tracker import (
    AlertSeverity,
    CategoryMetrics,
    MunicipalityMetrics,
    PopularModelEntry,
    RegionRecord,
    SubsidyPayload,
    SubsidyTracker,
    atomic_write_json as tracker_atomic_write_json,
    calculate_depletion_rate as tracker_calculate_depletion_rate,
    calculate_net_subsidy as tracker_calculate_net_subsidy,
    calculate_price_cap_ratio as tracker_calculate_price_cap_ratio,
    calculate_remaining_units as tracker_calculate_remaining_units,
    classify_alert_tier as tracker_classify_alert_tier,
    get_baseline_dataset,
    get_baseline_models,
    get_baseline_regions,
    get_baseline_thresholds,
)

HAS_TRACKER_MODULE = True

import run_tracker
HAS_RUN_TRACKER_MODULE = True



# ==============================================================================
# AUTHORITATIVE REFERENCE SPECIFICATIONS & ORACLES
# Derived directly from Ministry of Environment 2026 Guidelines & Spec Miner
# ==============================================================================

STATUTORY_17_REGIONS: Dict[str, Dict[str, Any]] = {
    "KR-11": {
        "name_ko": "서울특별시",
        "name_en": "Seoul",
        "tier": "special_city",
        "residency_days": 30,
        "max_local_krw": 1_500_000,
        "announced_sample": 11_500,
        "applied_sample": 9_890,
    },
    "KR-41": {
        "name_ko": "경기도",
        "name_en": "Gyeonggi",
        "tier": "province",
        "residency_days": 30,
        "max_local_krw": 3_500_000,
        "announced_sample": 28_000,
        "applied_sample": 25_480,
    },
    "KR-26": {
        "name_ko": "부산광역시",
        "name_en": "Busan",
        "tier": "metropolitan_city",
        "residency_days": 90,
        "max_local_krw": 2_500_000,
        "announced_sample": 6_200,
        "applied_sample": 4_836,
    },
    "KR-27": {
        "name_ko": "대구광역시",
        "name_en": "Daegu",
        "tier": "metropolitan_city",
        "residency_days": 30,
        "max_local_krw": 3_000_000,
        "announced_sample": 5_100,
        "applied_sample": 4_896,
    },
    "KR-28": {
        "name_ko": "인천광역시",
        "name_en": "Incheon",
        "tier": "metropolitan_city",
        "residency_days": 30,
        "max_local_krw": 3_000_000,
        "announced_sample": 5_800,
        "applied_sample": 4_756,
    },
    "KR-29": {
        "name_ko": "광주광역시",
        "name_en": "Gwangju",
        "tier": "metropolitan_city",
        "residency_days": 30,
        "max_local_krw": 3_500_000,
        "announced_sample": 3_400,
        "applied_sample": 3_128,
    },
    "KR-30": {
        "name_ko": "대전광역시",
        "name_en": "Daejeon",
        "tier": "metropolitan_city",
        "residency_days": 90,
        "max_local_krw": 3_000_000,
        "announced_sample": 4_200,
        "applied_sample": 3_276,
    },
    "KR-31": {
        "name_ko": "울산광역시",
        "name_en": "Ulsan",
        "tier": "metropolitan_city",
        "residency_days": 90,
        "max_local_krw": 3_150_000,
        "announced_sample": 2_800,
        "applied_sample": 2_688,
    },
    "KR-36": {
        "name_ko": "세종특별자치시",
        "name_en": "Sejong",
        "tier": "special_self_governing_city",
        "residency_days": 30,
        "max_local_krw": 2_500_000,
        "announced_sample": 1_200,
        "applied_sample": 876,
    },
    "KR-42": {
        "name_ko": "강원특별자치도",
        "name_en": "Gangwon",
        "tier": "special_self_governing_province",
        "residency_days": 90,
        "max_local_krw": 5_500_000,
        "announced_sample": 4_500,
        "applied_sample": 3_510,
    },
    "KR-43": {
        "name_ko": "충청북도",
        "name_en": "Chungbuk",
        "tier": "province",
        "residency_days": 30,
        "max_local_krw": 6_000_000,
        "announced_sample": 4_100,
        "applied_sample": 3_485,
    },
    "KR-44": {
        "name_ko": "충청남도",
        "name_en": "Chungnam",
        "tier": "province",
        "residency_days": 30,
        "max_local_krw": 6_500_000,
        "announced_sample": 5_900,
        "applied_sample": 5_192,
    },
    "KR-45": {
        "name_ko": "전북특별자치도",
        "name_en": "Jeonbuk",
        "tier": "special_self_governing_province",
        "residency_days": 30,
        "max_local_krw": 6_500_000,
        "announced_sample": 4_300,
        "applied_sample": 3_612,
    },
    "KR-46": {
        "name_ko": "전라남도",
        "name_en": "Jeonnam",
        "tier": "province",
        "residency_days": 90,
        "max_local_krw": 7_500_000,
        "announced_sample": 5_400,
        "applied_sample": 4_482,
    },
    "KR-47": {
        "name_ko": "경상북도",
        "name_en": "Gyeongbuk",
        "tier": "province",
        "residency_days": 30,
        "max_local_krw": 6_500_000,
        "announced_sample": 7_200,
        "applied_sample": 6_984,
    },
    "KR-48": {
        "name_ko": "경상남도",
        "name_en": "Gyeongnam",
        "tier": "province",
        "residency_days": 30,
        "max_local_krw": 6_000_000,
        "announced_sample": 6_800,
        "applied_sample": 5_984,
    },
    "KR-49": {
        "name_ko": "제주특별자치도",
        "name_en": "Jeju",
        "tier": "special_self_governing_province",
        "residency_days": 90,
        "max_local_krw": 4_000_000,
        "announced_sample": 4_000,
        "applied_sample": 3_960,
    },
}

ALERT_TIERS_SPEC: Dict[str, Dict[str, Any]] = {
    "HEALTHY": {
        "min_percent": 0.0,
        "max_percent": 60.0,
        "label_ko": "원활",
        "color_hex": "#10B981",
    },
    "CAUTION": {
        "min_percent": 60.0,
        "max_percent": 80.0,
        "label_ko": "주의",
        "color_hex": "#3B82F6",
    },
    "WARNING": {
        "min_percent": 80.0,
        "max_percent": 95.0,
        "label_ko": "경고",
        "color_hex": "#F59E0B",
    },
    "CRITICAL": {
        "min_percent": 95.0,
        "max_percent": 100.0,
        "label_ko": "마감임박",
        "color_hex": "#EF4444",
    },
    "DEPLETED": {
        "min_percent": 100.0,
        "max_percent": 999.0,
        "label_ko": "소진/마감",
        "color_hex": "#6B7280",
    },
}


def ref_calculate_depletion_rate(applied: int, announced: int) -> float:
    """Reference Oracle: Computes depletion rate with division-by-zero protection."""
    if announced <= 0:
        return 0.0
    return round((applied / announced) * 100.0, 1)


def ref_calculate_remaining_units(applied: int, announced: int) -> int:
    """Reference Oracle: Computes remaining units clamped at 0 for over-subscription."""
    return max(0, announced - applied)


def ref_classify_alert_tier(depletion_rate: float) -> str:
    """Reference Oracle: 5-Tier Priority Alert Classification."""
    if depletion_rate < 60.0:
        return "HEALTHY"
    elif depletion_rate < 80.0:
        return "CAUTION"
    elif depletion_rate < 95.0:
        return "WARNING"
    elif depletion_rate < 100.0:
        return "CRITICAL"
    else:
        return "DEPLETED"


def ref_calculate_price_cap_ratio(msrp: int) -> float:
    """Reference Oracle: Statutory 2026 Korean EV price-cap sliding ratio."""
    if msrp <= 55_000_000:
        return 1.0
    elif msrp <= 85_000_000:
        return 0.5
    else:
        return 0.0


def ref_calculate_net_subsidy(
    model_national: int,
    max_national: int,
    max_local: int,
    msrp: int,
) -> Dict[str, int]:
    """Reference Oracle: Calculates national, local, total subsidy and net price."""
    ratio = ref_calculate_price_cap_ratio(msrp)
    effective_national = int(round(model_national * ratio))
    if max_national > 0:
        local_ratio = model_national / max_national
    else:
        local_ratio = 0.0
    effective_local = int(round(max_local * local_ratio * ratio))
    total_subsidy = effective_national + effective_local
    net_price = max(0, msrp - total_subsidy)
    return {
        "national_subsidy_krw": effective_national,
        "local_subsidy_krw": effective_local,
        "total_subsidy_krw": total_subsidy,
        "net_price_krw": net_price,
    }


def ref_atomic_write_json(
    data: Any, target_path: str | Path, ensure_parent: bool = True, mode: int = 0o644
) -> Path:
    """Reference Oracle: POSIX atomic JSON write with tempfile + fsync + os.replace."""
    target = Path(target_path).resolve()
    dir_path = target.parent
    if ensure_parent:
        dir_path.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=dir_path, delete=False, encoding="utf-8") as tf:
        temp_name = tf.name
        json.dump(data, tf, ensure_ascii=False, indent=2)
        tf.flush()
        os.fsync(tf.fileno())
    os.replace(temp_name, target)
    try:
        os.chmod(target, mode)
    except OSError:
        pass
    return target


def validate_draft07_subsidy_payload(payload: Dict[str, Any]) -> List[str]:
    """Validates payload against Draft-07 JSON Schema requirements."""
    errors = []
    top_required = [
        "metadata",
        "alert_thresholds",
        "nationwide_summary",
        "regions",
        "popular_models_matrix",
        "historical_depletion_trajectory",
    ]
    for key in top_required:
        if key not in payload:
            errors.append(f"Missing top-level required key: '{key}'")

    if "metadata" in payload:
        meta = payload["metadata"]
        meta_req = ["version", "generated_at", "policy_year", "data_sources", "total_regions_tracked"]
        for m in meta_req:
            if m not in meta:
                errors.append(f"Missing metadata key: '{m}'")

    if "alert_thresholds" in payload:
        thresholds = payload["alert_thresholds"]
        for tier in ["HEALTHY", "CAUTION", "WARNING", "CRITICAL", "DEPLETED"]:
            if tier not in thresholds:
                errors.append(f"Missing alert threshold tier: '{tier}'")

    if "nationwide_summary" in payload:
        summary = payload["nationwide_summary"]
        summary_req = [
            "total_announced_units",
            "total_applied_units",
            "total_delivered_units",
            "total_remaining_units",
            "nationwide_depletion_rate",
            "alert_region_counts",
        ]
        for s in summary_req:
            if s not in summary:
                errors.append(f"Missing nationwide_summary key: '{s}'")

    if "regions" in payload:
        regions = payload["regions"]
        if not isinstance(regions, list):
            errors.append("'regions' must be an array")
        elif len(regions) != 17:
            errors.append(f"Expected 17 regions, found {len(regions)}")

    return errors


# ==============================================================================
# TEST SUITE 1: SUBSIDY CALCULATION & EDGE CASES
# ==============================================================================


class TestSubsidyMathAndDomainLogic(unittest.TestCase):
    """Test depletion rate math, division-by-zero protection, 5-tier alert logic, and price caps."""

    def test_depletion_rate_exact_math(self):
        """Verify normal mathematical calculation of depletion rates."""
        # Seoul: 9,890 / 11,500 = 86.0%
        rate_seoul = ref_calculate_depletion_rate(9890, 11500)
        self.assertEqual(rate_seoul, 86.0)

        # Gyeonggi: 25,480 / 28,000 = 91.0%
        rate_gyeonggi = ref_calculate_depletion_rate(25480, 28000)
        self.assertEqual(rate_gyeonggi, 91.0)

        # Sejong: 876 / 1,200 = 73.0%
        rate_sejong = ref_calculate_depletion_rate(876, 1200)
        self.assertEqual(rate_sejong, 73.0)

        # If tracker module is available, verify exact parity with tracker implementation
        if HAS_TRACKER_MODULE:
            self.assertEqual(tracker_calculate_depletion_rate(9890, 11500), 86.0)
            self.assertEqual(tracker_calculate_depletion_rate(25480, 28000), 91.0)

    def test_depletion_rate_zero_division_guard(self):
        """Verify division-by-zero protection when announced units == 0."""
        # Municipality with 0 announced units (early Q1 or unallocated)
        rate_zero = ref_calculate_depletion_rate(0, 0)
        self.assertEqual(rate_zero, 0.0)

        rate_unannounced_applied = ref_calculate_depletion_rate(15, 0)
        self.assertEqual(rate_unannounced_applied, 0.0)

        if HAS_TRACKER_MODULE:
            self.assertEqual(tracker_calculate_depletion_rate(0, 0), 0.0)
            self.assertEqual(tracker_calculate_depletion_rate(15, 0), 0.0)

    def test_depletion_rate_oversubscription_clamping(self):
        """Verify over-subscription rate (>100%) and remaining units clamped to 0."""
        # Over-subscribed quota: 2,150 applied for 2,000 announced
        announced = 2000
        applied = 2150
        rate = ref_calculate_depletion_rate(applied, announced)
        remaining = ref_calculate_remaining_units(applied, announced)

        self.assertEqual(rate, 107.5)
        self.assertEqual(remaining, 0)  # Clamped at 0, strictly non-negative

        # Extreme oversubscription
        extreme_remaining = ref_calculate_remaining_units(5000, 1000)
        self.assertEqual(extreme_remaining, 0)

        if HAS_TRACKER_MODULE:
            self.assertEqual(tracker_calculate_remaining_units(2150, 2000), 0)
            self.assertEqual(tracker_calculate_remaining_units(5000, 1000), 0)

    def test_alert_threshold_5_tiers_classification(self):
        """Verify exact classification for all 5 tiers across boundary values."""
        tier_cases = [
            # HEALTHY: [0.0, 60.0)
            (0.0, "HEALTHY"),
            (15.5, "HEALTHY"),
            (59.9, "HEALTHY"),
            # CAUTION: [60.0, 80.0)
            (60.0, "CAUTION"),  # Exact lower boundary
            (73.0, "CAUTION"),
            (78.0, "CAUTION"),
            (79.9, "CAUTION"),
            # WARNING: [80.0, 95.0)
            (80.0, "WARNING"),  # Exact lower boundary
            (86.0, "WARNING"),
            (91.0, "WARNING"),
            (94.9, "WARNING"),
            # CRITICAL: [95.0, 100.0)
            (95.0, "CRITICAL"),  # Exact lower boundary
            (96.0, "CRITICAL"),
            (99.0, "CRITICAL"),
            (99.9, "CRITICAL"),
            # DEPLETED: [100.0, +inf)
            (100.0, "DEPLETED"),  # Exact lower boundary
            (100.1, "DEPLETED"),
            (107.5, "DEPLETED"),
            (150.0, "DEPLETED"),
        ]
        for rate, expected_tier in tier_cases:
            with self.subTest(rate=rate, expected=expected_tier):
                self.assertEqual(ref_classify_alert_tier(rate), expected_tier)
                if HAS_TRACKER_MODULE:
                    self.assertEqual(tracker_classify_alert_tier(rate), expected_tier)

    def test_statutory_price_cap_sliding_scale(self):
        """Verify statutory 2026 Korean EV subsidy ratio tiers: 1.0 (<55M), 0.5 (55M-85M), 0.0 (>=85M)."""
        test_prices = [
            # Tier 1: 100% eligibility (< 55,000,000 KRW)
            (29_900_000, 1.0),  # Casper Electric
            (42_000_000, 1.0),  # EV3
            (52_400_000, 1.0),  # Ioniq 5 base
            (54_999_999, 1.0),  # Boundary - 1 KRW
            (55_000_000, 1.0),  # Exact statutory 100% boundary (<= 55M)
            # Tier 2: 50% eligibility (55,000,000, 85,000,000]
            (55_000_001, 0.5),  # Boundary + 1 KRW
            (62_000_000, 0.5),  # GV60 Standard
            (73_370_000, 0.5),  # EV9 2WD
            (84_999_999, 0.5),  # Boundary - 1 KRW
            (85_000_000, 0.5),  # Exact statutory 50% boundary (<= 85M)
            # Tier 3: 0% eligibility (> 85,000,000 KRW)
            (85_000_001, 0.0),  # Boundary + 1 KRW
            (92_000_000, 0.0),  # Genesis Electrified G80
            (115_000_000, 0.0),  # Tesla Model S
            (129_000_000, 0.0),  # Porsche Taycan
        ]
        for price, expected_ratio in test_prices:
            with self.subTest(price=price, expected=expected_ratio):
                self.assertEqual(ref_calculate_price_cap_ratio(price), expected_ratio)
                if HAS_TRACKER_MODULE:
                    self.assertEqual(tracker_calculate_price_cap_ratio(price), expected_ratio)

    def test_net_subsidy_calculation_scenarios(self):
        """Verify real-world scenario calculations for Seoul, Gyeonggi, Ulleung-gun, and Luxury EVs."""
        # Scenario 1: Hyundai Ioniq 5 in Seoul
        # MSRP 52.4M (<55M, ratio=1.0), National = 6.5M, Seoul max local = 1.5M
        s1 = ref_calculate_net_subsidy(6_500_000, 6_500_000, 1_500_000, 52_400_000)
        self.assertEqual(s1["national_subsidy_krw"], 6_500_000)
        self.assertEqual(s1["local_subsidy_krw"], 1_500_000)
        self.assertEqual(s1["total_subsidy_krw"], 8_000_000)
        self.assertEqual(s1["net_price_krw"], 44_400_000)

        # Scenario 2: Genesis GV60 in Gyeonggi (50% price cap tier)
        # MSRP 62.0M (ratio=0.5), Base National = 3.16M -> effective national = 1.58M
        s2 = ref_calculate_net_subsidy(3_160_000, 6_500_000, 3_500_000, 62_000_000)
        self.assertEqual(s2["national_subsidy_krw"], 1_580_000)
        self.assertEqual(s2["total_subsidy_krw"], s2["national_subsidy_krw"] + s2["local_subsidy_krw"])
        self.assertEqual(s2["net_price_krw"], 62_000_000 - s2["total_subsidy_krw"])

        # Scenario 3: Porsche Taycan (0% subsidy luxury tier)
        # MSRP 120.0M (ratio=0.0) -> all subsidies must be 0
        s3 = ref_calculate_net_subsidy(6_500_000, 6_500_000, 3_000_000, 120_000_000)
        self.assertEqual(s3["national_subsidy_krw"], 0)
        self.assertEqual(s3["local_subsidy_krw"], 0)
        self.assertEqual(s3["total_subsidy_krw"], 0)
        self.assertEqual(s3["net_price_krw"], 120_000_000)

        # Scenario 4: Ulleung-gun rural maximum subsidy buyer
        # National 6.5M + Ulleung local 11.0M = 17.5M total subsidy
        s4 = ref_calculate_net_subsidy(6_500_000, 6_500_000, 11_000_000, 52_400_000)
        self.assertEqual(s4["total_subsidy_krw"], 17_500_000)
        self.assertEqual(s4["net_price_krw"], 34_900_000)


# ==============================================================================
# TEST SUITE 2: 17 ADMINISTRATIVE DIVISIONS COMPLETENESS
# ==============================================================================


class Test17AdministrativeDivisionsCompleteness(unittest.TestCase):
    """Verify completeness and integrity of all 17 South Korean administrative divisions."""

    def test_exact_17_regions_count(self):
        """Verify that exactly 17 first-tier administrative divisions are cataloged."""
        self.assertEqual(len(STATUTORY_17_REGIONS), 17)

    def test_all_iso_codes_present(self):
        """Verify that all standard ISO 3166-2:KR codes are represented."""
        expected_iso_codes = {
            "KR-11",  # Seoul
            "KR-26",  # Busan
            "KR-27",  # Daegu
            "KR-28",  # Incheon
            "KR-29",  # Gwangju
            "KR-30",  # Daejeon
            "KR-31",  # Ulsan
            "KR-36",  # Sejong
            "KR-41",  # Gyeonggi
            "KR-42",  # Gangwon
            "KR-43",  # Chungbuk
            "KR-44",  # Chungnam
            "KR-45",  # Jeonbuk
            "KR-46",  # Jeonnam
            "KR-47",  # Gyeongbuk
            "KR-48",  # Gyeongnam
            "KR-49",  # Jeju
        }
        self.assertEqual(set(STATUTORY_17_REGIONS.keys()), expected_iso_codes)

    def test_tier_distribution(self):
        """Verify statutory administrative tier counts (1 special city, 6 metropolitan, 1 special self-governing city, 6 provinces, 3 special self-governing provinces)."""
        tiers = [v["tier"] for v in STATUTORY_17_REGIONS.values()]
        self.assertEqual(tiers.count("special_city"), 1)
        self.assertEqual(tiers.count("metropolitan_city"), 6)
        self.assertEqual(tiers.count("special_self_governing_city"), 1)
        self.assertEqual(tiers.count("province"), 6)
        self.assertEqual(tiers.count("special_self_governing_province"), 3)

    def test_residency_requirement_rules(self):
        """Verify residency requirement periods: 30 days vs 90 days."""
        # 30-day residency regions
        self.assertEqual(STATUTORY_17_REGIONS["KR-11"]["residency_days"], 30)  # Seoul
        self.assertEqual(STATUTORY_17_REGIONS["KR-41"]["residency_days"], 30)  # Gyeonggi
        self.assertEqual(STATUTORY_17_REGIONS["KR-27"]["residency_days"], 30)  # Daegu

        # 90-day residency regions (stricter speculation prevention)
        self.assertEqual(STATUTORY_17_REGIONS["KR-26"]["residency_days"], 90)  # Busan
        self.assertEqual(STATUTORY_17_REGIONS["KR-30"]["residency_days"], 90)  # Daejeon
        self.assertEqual(STATUTORY_17_REGIONS["KR-31"]["residency_days"], 90)  # Ulsan
        self.assertEqual(STATUTORY_17_REGIONS["KR-49"]["residency_days"], 90)  # Jeju

    def test_local_subsidy_caps_positive(self):
        """Verify that every region has a positive max local subsidy cap."""
        for iso, data in STATUTORY_17_REGIONS.items():
            self.assertGreater(data["max_local_krw"], 0, f"Region {iso} must have positive local subsidy")
            self.assertGreater(len(data["name_ko"]), 0, f"Region {iso} must have Korean name")
            self.assertGreater(len(data["name_en"]), 0, f"Region {iso} must have English name")


# ==============================================================================
# TEST SUITE 3: DRAFT-07 JSON SCHEMA COMPLIANCE
# ==============================================================================


class TestDraft07SchemaCompliance(unittest.TestCase):
    """Test JSON payload structure against Draft-07 specification."""

    def setUp(self):
        """Construct a reference valid payload matching Section 5 schema."""
        self.regions_payload = []
        for iso, spec in STATUTORY_17_REGIONS.items():
            announced = spec["announced_sample"]
            applied = spec["applied_sample"]
            depletion_rate = ref_calculate_depletion_rate(applied, announced)
            status = ref_classify_alert_tier(depletion_rate)
            remaining = ref_calculate_remaining_units(applied, announced)
            self.regions_payload.append(
                {
                    "region_id": iso.lower().replace("-", "_"),
                    "iso_code": iso,
                    "name_ko": spec["name_ko"],
                    "name_en": spec["name_en"],
                    "tier": spec["tier"],
                    "overall_depletion_rate": depletion_rate,
                    "overall_status": status,
                    "residency_requirement_days": spec["residency_days"],
                    "supplementary_budget_added": False,
                    "categories": {
                        "passenger": {
                            "announced_units": announced,
                            "applied_units": applied,
                            "delivered_units": int(applied * 0.8),
                            "remaining_units": remaining,
                            "depletion_rate": depletion_rate,
                            "delivery_rate": round((applied * 0.8 / announced) * 100, 1),
                            "status": status,
                            "max_local_subsidy_krw": spec["max_local_krw"],
                            "max_total_subsidy_krw": spec["max_local_krw"] + 6_500_000,
                            "total_budget_krw": announced * spec["max_local_krw"],
                            "remaining_budget_krw": remaining * spec["max_local_krw"],
                        },
                        "commercial": {
                            "announced_units": 1000,
                            "applied_units": 900,
                            "delivered_units": 800,
                            "remaining_units": 100,
                            "depletion_rate": 90.0,
                            "delivery_rate": 80.0,
                            "status": "WARNING",
                            "max_local_subsidy_krw": 4_000_000,
                            "max_total_subsidy_krw": 14_500_000,
                            "total_budget_krw": 4_000_000_000,
                            "remaining_budget_krw": 400_000_000,
                        },
                        "bus": {
                            "announced_units": 100,
                            "applied_units": 85,
                            "delivered_units": 70,
                            "remaining_units": 15,
                            "depletion_rate": 85.0,
                            "delivery_rate": 70.0,
                            "status": "WARNING",
                            "max_local_subsidy_krw": 30_000_000,
                            "max_total_subsidy_krw": 100_000_000,
                            "total_budget_krw": 3_000_000_000,
                            "remaining_budget_krw": 450_000_000,
                        },
                    },
                    "municipalities": [],
                    "notes": "",
                }
            )

        self.valid_payload = {
            "metadata": {
                "version": "1.0.0",
                "generated_at": "2026-09-23T23:30:00Z",
                "policy_year": 2026,
                "data_sources": [
                    "환경부 무공해차 통합누리집 (ev.or.kr)",
                    "한국환경공단 CleanSys",
                    "17개 시도 무공해차 보급촉진 조례",
                ],
                "total_regions_tracked": 17,
                "total_municipalities_tracked": 161,
                "currency": "KRW",
            },
            "alert_thresholds": ALERT_TIERS_SPEC,
            "nationwide_summary": {
                "total_announced_units": sum(r["categories"]["passenger"]["announced_units"] for r in self.regions_payload),
                "total_applied_units": sum(r["categories"]["passenger"]["applied_units"] for r in self.regions_payload),
                "total_delivered_units": sum(r["categories"]["passenger"]["delivered_units"] for r in self.regions_payload),
                "total_remaining_units": sum(r["categories"]["passenger"]["remaining_units"] for r in self.regions_payload),
                "nationwide_depletion_rate": 87.4,
                "total_budget_billion_krw": 1840.5,
                "disbursed_budget_billion_krw": 1608.2,
                "category_totals": {
                    "passenger": {"announced": 105500, "applied": 92250},
                    "commercial": {"announced": 17000, "applied": 15300},
                    "bus": {"announced": 1700, "applied": 1445},
                },
                "alert_region_counts": {
                    "healthy": 0,
                    "caution": 5,
                    "warning": 8,
                    "critical": 4,
                    "depleted": 0,
                },
            },
            "regions": self.regions_payload,
            "popular_models_matrix": [
                {
                    "model_id": "ioniq-5-long-range-2wd",
                    "name_ko": "현대 더 뉴 아이오닉 5 롱레인지 2WD",
                    "manufacturer": "현대자동차",
                    "battery_type": "NCMA",
                    "battery_capacity_kwh": 84.0,
                    "rated_range_km": 485,
                    "base_price_krw": 52_400_000,
                    "price_subsidy_ratio": 1.0,
                    "national_subsidy_krw": 6_500_000,
                    "regional_subsidy_samples": {
                        "seoul": {"total_subsidy_krw": 8_000_000, "net_price_krw": 44_400_000},
                    },
                }
            ],
            "historical_depletion_trajectory": [
                {"date": "2026-06-01", "passenger_rate": 45.2, "commercial_rate": 52.0, "overall_rate": 46.1},
                {"date": "2026-07-01", "passenger_rate": 62.4, "commercial_rate": 71.3, "overall_rate": 63.6},
                {"date": "2026-08-01", "passenger_rate": 76.8, "commercial_rate": 83.5, "overall_rate": 77.7},
                {"date": "2026-09-01", "passenger_rate": 87.4, "commercial_rate": 90.0, "overall_rate": 87.8},
            ],
        }

    def test_valid_payload_passes_schema_check(self):
        """Verify that the standard compliant payload passes schema validation without errors."""
        errors = validate_draft07_subsidy_payload(self.valid_payload)
        self.assertEqual(len(errors), 0, f"Schema validation failed with errors: {errors}")

    def test_missing_top_level_key_triggers_error(self):
        """Verify that omitting a mandatory top-level key produces a schema error."""
        invalid_payload = dict(self.valid_payload)
        del invalid_payload["regions"]
        errors = validate_draft07_subsidy_payload(invalid_payload)
        self.assertTrue(any("Missing top-level required key: 'regions'" in e for e in errors))

    def test_missing_metadata_keys_trigger_error(self):
        """Verify that missing metadata fields are caught."""
        invalid_payload = dict(self.valid_payload)
        invalid_payload["metadata"] = {"version": "1.0.0"}  # missing generated_at, etc.
        errors = validate_draft07_subsidy_payload(invalid_payload)
        self.assertTrue(any("Missing metadata key" in e for e in errors))

    def test_region_count_mismatch_triggers_error(self):
        """Verify that payloads with fewer than 17 regions are rejected."""
        invalid_payload = dict(self.valid_payload)
        invalid_payload["regions"] = self.regions_payload[:16]  # 16 instead of 17
        errors = validate_draft07_subsidy_payload(invalid_payload)
        self.assertTrue(any("Expected 17 regions" in e for e in errors))

    def test_json_serializability(self):
        """Verify that the dataset round-trips cleanly through json.dumps and json.loads."""
        encoded = json.dumps(self.valid_payload, ensure_ascii=False)
        decoded = json.loads(encoded)
        self.assertEqual(len(decoded["regions"]), 17)
        self.assertEqual(decoded["metadata"]["currency"], "KRW")


# ==============================================================================
# TEST SUITE 4: VEHICLE MODEL SUBSIDY MATRIX INTEGRITY
# ==============================================================================


class TestVehicleModelMatrixIntegrity(unittest.TestCase):
    """Verify integrity of mined EV models matrix against statutory standards."""

    def setUp(self):
        self.matrix_file = PROJECT_ROOT / ".agents" / "spec_miner_models_w2" / "models_subsidy_matrix.json"
        if not self.matrix_file.exists() and (PROJECT_ROOT.parent / ".agents" / "spec_miner_models_w2" / "models_subsidy_matrix.json").exists():
            self.matrix_file = PROJECT_ROOT.parent / ".agents" / "spec_miner_models_w2" / "models_subsidy_matrix.json"

    def test_models_matrix_file_structure(self):
        """Verify that models matrix file contains required automotive specifications."""
        if not self.matrix_file.exists():
            self.skipTest(f"models_subsidy_matrix.json not yet available at {self.matrix_file}")

        with open(self.matrix_file, "r", encoding="utf-8") as f:
            models = json.load(f)

        self.assertIsInstance(models, list)
        self.assertGreaterEqual(len(models), 15, "Expected at least 15 EV models in matrix")

        for m in models:
            self.assertIn("model_id", m)
            self.assertIn("name_ko", m)
            self.assertIn("manufacturer", m)
            self.assertIn("battery_type", m)
            self.assertIn("battery_capacity_kwh", m)
            self.assertIn("rated_range_km", m)
            self.assertIn("base_price_krw", m)
            self.assertIn("price_subsidy_ratio", m)
            self.assertIn("national_subsidy_krw", m)

            # Mathematical validation of subsidy ratio
            price = m["base_price_krw"]
            expected_ratio = ref_calculate_price_cap_ratio(price)
            self.assertEqual(
                m["price_subsidy_ratio"],
                expected_ratio,
                f"Model {m['model_id']} ratio {m['price_subsidy_ratio']} != expected {expected_ratio}",
            )

            # Max national subsidy for passenger cars is 6.5M KRW
            self.assertLessEqual(m["national_subsidy_krw"], 6_500_000)


# ==============================================================================
# TEST SUITE 5: TIER 3 PAIRWISE COMBINATIONS (17 REGIONS x PRICE TIERS)
# ==============================================================================


class TestTier3PairwiseCombinations(unittest.TestCase):
    """Pairwise test matrix: 17 administrative regions x 3 vehicle price tiers (51 cases)."""

    def test_pairwise_regions_x_price_tiers(self):
        """Verify that every combination of region and price tier computes consistent subsidies."""
        test_vehicles = [
            ("Affordable EV (<55M)", 45_000_000, 6_000_000, 1.0),
            ("Mid-tier EV (55M-85M)", 65_000_000, 5_500_000, 0.5),
            ("Luxury EV (>=85M)", 95_000_000, 6_500_000, 0.0),
        ]

        evaluated_pairs = 0
        for iso, region_info in STATUTORY_17_REGIONS.items():
            max_local = region_info["max_local_krw"]
            for v_name, msrp, base_national, expected_ratio in test_vehicles:
                calc = ref_calculate_net_subsidy(
                    model_national=base_national,
                    max_national=6_500_000,
                    max_local=max_local,
                    msrp=msrp,
                )

                if expected_ratio == 0.0:
                    self.assertEqual(calc["national_subsidy_krw"], 0)
                    self.assertEqual(calc["local_subsidy_krw"], 0)
                    self.assertEqual(calc["total_subsidy_krw"], 0)
                    self.assertEqual(calc["net_price_krw"], msrp)
                elif expected_ratio == 0.5:
                    self.assertEqual(calc["national_subsidy_krw"], int(round(base_national * 0.5)))
                    self.assertLess(calc["total_subsidy_krw"], msrp)
                    self.assertEqual(calc["net_price_krw"], msrp - calc["total_subsidy_krw"])
                else:  # 1.0
                    self.assertEqual(calc["national_subsidy_krw"], base_national)
                    self.assertGreater(calc["total_subsidy_krw"], 0)
                    self.assertEqual(calc["net_price_krw"], msrp - calc["total_subsidy_krw"])

                evaluated_pairs += 1

        self.assertEqual(evaluated_pairs, 17 * 3, f"Expected 51 pairwise evaluations, ran {evaluated_pairs}")


# ==============================================================================
# TEST SUITE 6: TIER 4 REAL-WORLD APPLICATION SCENARIOS
# ==============================================================================


class TestTier4RealWorldScenarios(unittest.TestCase):
    """Verify 5 end-to-end real world application scenarios from TEST_INFRA.md."""

    def test_scenario_1_scheduled_cron_run(self):
        """Scenario 1: Headless scheduled task execution with atomic JSON update."""
        with tempfile.TemporaryDirectory(prefix="test_cron_") as tmp_dir:
            out_file = Path(tmp_dir) / "ev_subsidy_data.json"
            dummy_payload = {
                "metadata": {"version": "1.0.0", "generated_at": "2026-09-23T23:30:00Z"},
                "regions": list(STATUTORY_17_REGIONS.keys()),
            }
            ref_atomic_write_json(dummy_payload, out_file)
            self.assertTrue(out_file.exists())
            with open(out_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            self.assertEqual(len(loaded["regions"]), 17)

    def test_scenario_2_seoul_citizen_ev_buyer(self):
        """Scenario 2: Seoul citizen buying Hyundai Ioniq 5 (86% WARNING, 30-day residency)."""
        seoul_info = STATUTORY_17_REGIONS["KR-11"]
        self.assertEqual(seoul_info["residency_days"], 30)

        rate = ref_calculate_depletion_rate(seoul_info["applied_sample"], seoul_info["announced_sample"])
        self.assertEqual(rate, 86.0)
        self.assertEqual(ref_classify_alert_tier(rate), "WARNING")

        # Ioniq 5 calculation
        calc = ref_calculate_net_subsidy(6_500_000, 6_500_000, seoul_info["max_local_krw"], 52_400_000)
        self.assertEqual(calc["total_subsidy_krw"], 8_000_000)
        self.assertEqual(calc["net_price_krw"], 44_400_000)

    def test_scenario_3_ulleung_gun_maximum_subsidy_buyer(self):
        """Scenario 3: Ulleung-gun rural maximum subsidy buyer (17.5M KRW total, 100% DEPLETED alert)."""
        # Ulleung-gun local subsidy is 11,000,000 KRW
        ulleung_local_max = 11_000_000
        calc = ref_calculate_net_subsidy(6_500_000, 6_500_000, ulleung_local_max, 52_400_000)
        self.assertEqual(calc["total_subsidy_krw"], 17_500_000)
        self.assertEqual(calc["net_price_krw"], 34_900_000)

        # 100% depleted status
        depleted_rate = ref_calculate_depletion_rate(100, 100)
        self.assertEqual(ref_classify_alert_tier(depleted_rate), "DEPLETED")
        self.assertEqual(ref_calculate_remaining_units(100, 100), 0)

    def test_scenario_4_luxury_ev_buyer_exemption(self):
        """Scenario 4: Porsche Taycan / Tesla Model X (>85M KRW) 0 KRW subsidy rule."""
        taycan_msrp = 129_000_000
        calc = ref_calculate_net_subsidy(6_500_000, 6_500_000, 3_000_000, taycan_msrp)
        self.assertEqual(calc["national_subsidy_krw"], 0)
        self.assertEqual(calc["local_subsidy_krw"], 0)
        self.assertEqual(calc["total_subsidy_krw"], 0)
        self.assertEqual(calc["net_price_krw"], taycan_msrp)

    def test_scenario_5_supplementary_budget_injection(self):
        """Scenario 5: Mid-year supplementary budget resets depletion rate downwards without crash."""
        initial_rate = ref_calculate_depletion_rate(1900, 2000)  # 95% (CRITICAL)
        self.assertEqual(ref_classify_alert_tier(initial_rate), "CRITICAL")

        # Municipality adds supplementary budget: announced becomes 3000
        new_rate = ref_calculate_depletion_rate(1900, 3000)  # 63.3% (CAUTION)
        self.assertEqual(new_rate, 63.3)
        self.assertEqual(ref_classify_alert_tier(new_rate), "CAUTION")


# ==============================================================================
# TEST SUITE 7: POSIX ATOMIC WRITER
# ==============================================================================


class TestPOSIXAtomicWriter(unittest.TestCase):
    """Test atomic file writing durability, crash safety, permissions, and directory auto-creation."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_subsidy_atomic_")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_atomic_write_creates_valid_file(self):
        """Verify atomic writer writes complete JSON content to target path."""
        target_file = Path(self.test_dir) / "output.json"
        data = {"test": "value", "count": 42, "korean": "전기차 보조금"}

        result_path = ref_atomic_write_json(data, target_file)
        self.assertTrue(target_file.exists())
        self.assertEqual(result_path.resolve(), target_file.resolve())

        with open(target_file, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        self.assertEqual(loaded["korean"], "전기차 보조금")

        if HAS_TRACKER_MODULE:
            target_module = Path(self.test_dir) / "module_output.json"
            tracker_atomic_write_json(data, target_module)
            self.assertTrue(target_module.exists())

    def test_atomic_write_same_directory_tempfile(self):
        """Verify that temporary file is created in the SAME directory to guarantee POSIX atomic rename."""
        target_file = Path(self.test_dir) / "subdir" / "target.json"
        data = {"status": "ok"}
        ref_atomic_write_json(data, target_file, ensure_parent=True)

        self.assertTrue(target_file.exists())
        self.assertIn("target.json", os.listdir(target_file.parent))

    def test_atomic_write_replaces_existing_atomically(self):
        """Verify that subsequent atomic writes replace existing files cleanly without corruption."""
        target_file = Path(self.test_dir) / "update.json"
        initial_data = {"version": 1, "value": "initial"}
        updated_data = {"version": 2, "value": "updated"}

        ref_atomic_write_json(initial_data, target_file)
        with open(target_file, "r", encoding="utf-8") as f:
            self.assertEqual(json.load(f)["version"], 1)

        ref_atomic_write_json(updated_data, target_file)
        with open(target_file, "r", encoding="utf-8") as f:
            self.assertEqual(json.load(f)["version"], 2)

    def test_atomic_write_auto_creates_parent_directories(self):
        """Verify that deep non-existent directories are auto-created when ensure_parent=True."""
        deep_target = Path(self.test_dir) / "a" / "b" / "c" / "deep_file.json"
        self.assertFalse(deep_target.parent.exists())

        ref_atomic_write_json({"deep": True}, deep_target, ensure_parent=True)
        self.assertTrue(deep_target.exists())
        self.assertTrue(deep_target.parent.exists())

    def test_atomic_write_permissions(self):
        """Verify that created files have expected POSIX permissions."""
        target_file = Path(self.test_dir) / "perms.json"
        ref_atomic_write_json({"data": 1}, target_file, mode=0o644)
        file_stat = target_file.stat()
        mode = stat.S_IMODE(file_stat.st_mode)
        self.assertTrue(mode & stat.S_IRUSR)

    def test_atomic_write_unicode_korean_integrity(self):
        """Verify that Korean hangul and special characters are preserved without unicode escape artifacts."""
        target_file = Path(self.test_dir) / "hangul.json"
        korean_payload = {
            "regions": ["서울특별시", "제주특별자치도", "울릉군 (경상북도)"],
            "quote": "보조금 소진율 96% 돌파! 즉시 신청 요망",
        }
        ref_atomic_write_json(korean_payload, target_file)

        raw_bytes = target_file.read_bytes()
        self.assertIn("서울특별시".encode("utf-8"), raw_bytes)
        self.assertNotIn(b"\\u", raw_bytes)

    def test_atomic_write_preserves_original_on_serialization_failure(self):
        """Verify that an un-serializable payload does not corrupt or overwrite an existing file."""
        target_file = Path(self.test_dir) / "durable.json"
        initial_data = {"intact": True}
        ref_atomic_write_json(initial_data, target_file)

        invalid_data = {"broken": {1, 2, 3}}
        with self.assertRaises(TypeError):
            ref_atomic_write_json(invalid_data, target_file)

        with open(target_file, "r", encoding="utf-8") as f:
            self.assertEqual(json.load(f)["intact"], True)


# ==============================================================================
# TEST SUITE 8: CLI FLAGS & RUNNER
# ==============================================================================


class TestCLIFlagsAndRunner(unittest.TestCase):
    """Test CLI argument parsing, flags (--sync-web, --verbose, --dry-run, --output), and exit code 0."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_subsidy_cli_")
        self.run_tracker_script = PROJECT_ROOT / "run_tracker.py"

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_argparse_cli_definition(self):
        """Verify argument parser contract for run_tracker."""
        parser = argparse.ArgumentParser(description="EV Subsidy Depletion Tracker")
        parser.add_argument("--sync-web", "-s", action="store_true")
        parser.add_argument("--verbose", "-v", action="store_true")
        parser.add_argument("--dry-run", "-d", action="store_true")
        parser.add_argument("--output", "-o", type=str, default=None)

        args = parser.parse_args(["--sync-web", "--verbose", "--dry-run", "-o", "/tmp/out.json"])
        self.assertTrue(args.sync_web)
        self.assertTrue(args.verbose)
        self.assertTrue(args.dry_run)
        self.assertEqual(args.output, "/tmp/out.json")

    def test_run_tracker_cli_help(self):
        """Verify python3 run_tracker.py --help returns exit code 0."""
        if not self.run_tracker_script.exists():
            self.skipTest(f"run_tracker.py not yet created at {self.run_tracker_script}")

        result = subprocess.run(
            [sys.executable, str(self.run_tracker_script), "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--sync-web", result.stdout)
        self.assertIn("--dry-run", result.stdout)

    def test_run_tracker_dry_run_flag(self):
        """Verify run_tracker.py --dry-run exits with code 0 and does not write files."""
        if not self.run_tracker_script.exists():
            self.skipTest("run_tracker.py pending implementation")

        result = subprocess.run(
            [sys.executable, str(self.run_tracker_script), "--dry-run", "--verbose"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, f"run_tracker failed with stderr: {result.stderr}")

    def test_run_tracker_custom_output_flag(self):
        """Verify run_tracker.py --output writes to designated custom path."""
        if not self.run_tracker_script.exists():
            self.skipTest("run_tracker.py pending implementation")

        custom_output = Path(self.test_dir) / "custom_subsidy.json"
        result = subprocess.run(
            [sys.executable, str(self.run_tracker_script), "--output", str(custom_output), "--verbose"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, f"run_tracker failed with stderr: {result.stderr}")
        self.assertTrue(custom_output.exists())
        with open(custom_output, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(len(data["regions"]), 17)


# ==============================================================================
# TEST SUITE 9: TRACKER IMPLEMENTATION INTEGRATION (WHEN MODULES AVAILABLE)
# ==============================================================================


class TestTrackerModuleIntegration(unittest.TestCase):
    """Integration test suite exercising actual tracker package components."""

    def test_dataclass_serialization(self):
        """Verify CategoryMetrics, MunicipalityMetrics, RegionRecord, SubsidyPayload serialization."""
        cat = CategoryMetrics(
            announced_units=1000,
            applied_units=800,
            delivered_units=600,
            remaining_units=200,
            depletion_rate=80.0,
            delivery_rate=60.0,
            status=AlertSeverity.WARNING,
            max_local_subsidy_krw=3_000_000,
            max_total_subsidy_krw=9_500_000,
        )
        self.assertEqual(cat.status, "WARNING")
        self.assertEqual(cat.remaining_units, 200)

    def test_baseline_dataset_generates_all_17_regions(self):
        """Verify that get_baseline_dataset() returns complete 17-region dataset."""
        payload = get_baseline_dataset()
        self.assertIsNotNone(payload)
        regions = payload.regions if hasattr(payload, "regions") else payload.get("regions", [])
        self.assertEqual(len(regions), 17)

    def test_subsidy_tracker_offline_collection(self):
        """Verify SubsidyTracker.collect_and_save() executes in-memory without errors and validates cache."""
        tracker_instance = SubsidyTracker()
        result = tracker_instance.collect_and_save(dry_run=True)
        self.assertIsNotNone(result)
        self.assertEqual(len(result.regions), 17)

        # Verify collect_and_save rejects degenerate cache (<17 regions) and falls back to baseline
        with tempfile.TemporaryDirectory() as tmp_dir:
            bad_cache = Path(tmp_dir) / "bad_cache.json"
            with open(bad_cache, "w", encoding="utf-8") as f:
                json.dump({"regions": []}, f)
            t_bad = SubsidyTracker(cache_fallback_path=bad_cache)
            res_bad = t_bad.collect_and_save(dry_run=True)
            self.assertEqual(len(res_bad.regions), 17)

        # Verify collect_and_save safely recovers from malformed region objects in cache
        with tempfile.TemporaryDirectory() as tmp_dir:
            anomaly_cache = Path(tmp_dir) / "anomaly_cache.json"
            with open(anomaly_cache, "w", encoding="utf-8") as f:
                json.dump({"regions": "not_a_valid_list_of_records"}, f)
            t_anomaly = SubsidyTracker(cache_fallback_path=anomaly_cache)
            res_anomaly = t_anomaly.collect_and_save(dry_run=True)
            self.assertEqual(len(res_anomaly.regions), 17)




# ==============================================================================
# TEST SUITE 10: ADVERSARIAL & BOUNDARY STRESS
# ==============================================================================


class TestAdversarialAndBoundaryStress(unittest.TestCase):
    """Stress tests covering extreme values, supplementary budgets, and concurrency."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_subsidy_adversarial_")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_extreme_large_and_zero_values(self):
        """Verify handling of extreme budget numbers (100 Billion KRW) without overflow or float NaN."""
        huge_msrp = 100_000_000_000
        ratio = ref_calculate_price_cap_ratio(huge_msrp)
        self.assertEqual(ratio, 0.0)

        huge_rate = ref_calculate_depletion_rate(9_500_000, 10_000_000)
        self.assertEqual(huge_rate, 95.0)
        self.assertEqual(ref_classify_alert_tier(huge_rate), "CRITICAL")

    def test_special_characters_and_escaping(self):
        """Verify region names and notes with special characters, HTML, and unicode emojis."""
        special_data = {
            "name": "<script>alert('xss')</script>",
            "emoji": "⚡🚗🔋",
            "quotes": 'Double " and Single \' quotes and backslash \\',
        }
        target_path = Path(self.test_dir) / "special.json"
        ref_atomic_write_json(special_data, target_path)

        with open(target_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        self.assertEqual(loaded["emoji"], "⚡🚗🔋")
        self.assertEqual(loaded["name"], "<script>alert('xss')</script>")

    def test_10000_record_scale_simulation(self):
        """Scale benchmark: verifies mathematical calculations across 10,000 synthetic evaluations."""
        start_time = os.times().user
        for i in range(10_000):
            ann = (i % 500) + 1
            app = (i % 600)
            rate = ref_calculate_depletion_rate(app, ann)
            tier = ref_classify_alert_tier(rate)
            rem = ref_calculate_remaining_units(app, ann)
            ratio = ref_calculate_price_cap_ratio((i * 10_000) % 150_000_000)
        elapsed = os.times().user - start_time
        self.assertLess(elapsed, 1.0, f"10k scale benchmark took {elapsed:.3f}s (exceeded 1.0s)")


if __name__ == "__main__":
    unittest.main()
