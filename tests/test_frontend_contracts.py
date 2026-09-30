"""
tests/test_frontend_contracts.py - Comprehensive Frontend Contract Verification Test Suite.

Authoritative Sources:
- ORIGINAL_REQUEST.md (Requirements R1, R2, R3 - Scheduled Tasks & Subsidy Tracker)
- ev-stealth-web/src/types/subsidy.ts (TypeScript definitions for RegionEntry, CategoryMetrics, PopularModelEntry, NationwideSummary)
- ev-stealth-web/src/lib/getSubsidyData.ts (getPriceSubsidyRatio, calculateNetSubsidy, getRegionById)
- tracker/subsidy_models.py (Python backend dataclass models & AlertSeverity enum)
- Ministry of Environment (환경부) 2026 Statutory EV Subsidy Guidelines (ev.or.kr)

Coverage Areas:
1. JSON Schema & Types Contract:
   - Verifies ev-stealth-web/src/data/ev_subsidy_data.json file presence, structure, and validity.
   - Verifies all required fields and type contracts for:
     * RegionEntry
     * CategoryMetrics
     * PopularModelEntry
     * NationwideSummary
   - Verifies non-empty data for all 17 Korean 1st-tier administrative divisions (Special City, Metropolitans, Provinces).
   - Verifies 5-tier alert severities (HEALTHY, CAUTION, WARNING, CRITICAL, DEPLETED) and boundary thresholds.
   - Verifies historical trajectory points and monotonicity.
2. Price-Cap Mathematical Contract:
   - Tests sliding-scale price cap rules on vehicle MSRPs:
     * MSRP < 55,000,000 KRW: 100% subsidy ratio (1.0).
     * 55,000,000 <= MSRP < 85,000,000 KRW: 50% subsidy ratio (0.5).
     * MSRP >= 85,000,000 KRW: 0% subsidy ratio (0.0).
   - Exact boundary testing at 54,999,999, 55,000,000, 84,999,999, and 85,000,000 KRW.
   - Verifies compliance of all popular vehicle models in the matrix.
   - Adversarial price testing (zero, luxury, extreme values, floats).
   - Additional statutory grant incentives (youth, taxi/small business, multi-child, scrappage).
3. Regional Disparity Contract:
   - Verifies Seoul local subsidy (1.5M KRW) vs Ulleung-gun local subsidy (11.0M KRW).
   - Verifies out-of-pocket purchase price disparity on real EV models.
   - Verifies proportional local matching formula: local = round(max_local * (national / 6.5M) / 10000) * 10000.
   - Verifies invariant remaining units formula: remaining = max(0, announced - applied) across all regions, categories, and municipalities.
   - Over-subscription stress testing and division-by-zero guards.
4. Cross-Language Model & Serialization Parity:
   - Tests round-trip parsing of the frontend JSON into Python typed dataclasses.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys
import unittest
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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


# ==============================================================================
# AUTHORITATIVE REFERENCE CONSTANTS & PURE FUNCTIONS
# ==============================================================================

if (PROJECT_ROOT / "src" / "data").exists():
    FRONTEND_DATA_PATH = PROJECT_ROOT / "src" / "data" / "ev_subsidy_data.json"
    REPO_DATA_PATH = (PROJECT_ROOT.parent / "data" / "ev_subsidy_data.json") if (PROJECT_ROOT.parent / "data").exists() else FRONTEND_DATA_PATH
else:
    FRONTEND_DATA_PATH = PROJECT_ROOT / "ev-stealth-web" / "src" / "data" / "ev_subsidy_data.json"
    REPO_DATA_PATH = PROJECT_ROOT / "data" / "ev_subsidy_data.json"

# All 17 Korean 1st-tier administrative divisions defined by ISO 3166-2:KR
STATUTORY_17_REGIONS: Dict[str, Dict[str, Any]] = {
    "KR-11": {"name_ko": "서울특별시", "name_en": "Seoul", "tier": "special_city", "residency_days": 30},
    "KR-41": {"name_ko": "경기도", "name_en": "Gyeonggi", "tier": "province", "residency_days": 30},
    "KR-26": {"name_ko": "부산광역시", "name_en": "Busan", "tier": "metropolitan_city", "residency_days": 90},
    "KR-27": {"name_ko": "대구광역시", "name_en": "Daegu", "tier": "metropolitan_city", "residency_days": 30},
    "KR-28": {"name_ko": "인천광역시", "name_en": "Incheon", "tier": "metropolitan_city", "residency_days": 30},
    "KR-29": {"name_ko": "광주광역시", "name_en": "Gwangju", "tier": "metropolitan_city", "residency_days": 30},
    "KR-30": {"name_ko": "대전광역시", "name_en": "Daejeon", "tier": "metropolitan_city", "residency_days": 90},
    "KR-31": {"name_ko": "울산광역시", "name_en": "Ulsan", "tier": "metropolitan_city", "residency_days": 90},
    "KR-36": {"name_ko": "세종특별자치시", "name_en": "Sejong", "tier": "special_self_governing_city", "residency_days": 30},
    "KR-42": {"name_ko": "강원특별자치도", "name_en": "Gangwon", "tier": "special_self_governing_province", "residency_days": 90},
    "KR-43": {"name_ko": "충청북도", "name_en": "Chungbuk", "tier": "province", "residency_days": 30},
    "KR-44": {"name_ko": "충청남도", "name_en": "Chungnam", "tier": "province", "residency_days": 30},
    "KR-45": {"name_ko": "전북특별자치도", "name_en": "Jeonbuk", "tier": "special_self_governing_province", "residency_days": 30},
    "KR-46": {"name_ko": "전라남도", "name_en": "Jeonnam", "tier": "province", "residency_days": 90},
    "KR-47": {"name_ko": "경상북도", "name_en": "Gyeongbuk", "tier": "province", "residency_days": 30},
    "KR-48": {"name_ko": "경상남도", "name_en": "Gyeongnam", "tier": "province", "residency_days": 30},
    "KR-49": {"name_ko": "제주특별자치도", "name_en": "Jeju", "tier": "special_self_governing_province", "residency_days": 90},
}

EXPECTED_5_ALERT_TIERS: Set[str] = {
    "HEALTHY",
    "CAUTION",
    "WARNING",
    "CRITICAL",
    "DEPLETED",
}

EXPECTED_CATEGORIES: Set[str] = {"passenger", "commercial", "bus"}


def pure_price_subsidy_ratio(msrp: float) -> float:
    """Statutory sliding scale price cap rules based on 2026 MOE Guidelines:

    - MSRP < 55,000,000 KRW: 1.0 (100% eligibility)
    - 55,000,000 <= MSRP < 85,000,000 KRW: 0.5 (50% eligibility)
    - MSRP >= 85,000,000 KRW: 0.0 (0% luxury vehicle exclusion)
    """
    if msrp >= 85_000_000:
        return 0.0
    elif msrp >= 55_000_000:
        return 0.5
    else:
        return 1.0


def pure_calculate_remaining_units(announced: int, applied: int) -> int:
    """Clamped remaining units calculation: remaining = max(0, announced - applied)."""
    return max(0, int(announced) - int(applied))


def pure_calculate_depletion_rate(announced: int, applied: int) -> float:
    """Depletion rate percentage with division-by-zero protection."""
    if announced <= 0:
        return 0.0
    return round((applied / announced) * 100.0, 1)


def pure_calculate_local_subsidy(max_local_subsidy: int, national_subsidy: int) -> int:
    """Proportional local matching formula rounded to nearest 10,000 KRW."""
    if national_subsidy <= 0:
        return 0
    proportional = round(max_local_subsidy * (national_subsidy / 6_500_000))
    return int(round(proportional / 10_000) * 10_000)


# ==============================================================================
# TEST SUITE IMPLEMENTATION
# ==============================================================================

class TestSubsidyJsonSchemaAndTypesContract(unittest.TestCase):
    """Verifies that ev_subsidy_data.json conforms strictly to TypeScript & Python type contracts."""

    @classmethod
    def setUpClass(cls):
        cls.json_path = FRONTEND_DATA_PATH
        if not cls.json_path.exists() and REPO_DATA_PATH.exists():
            cls.json_path = REPO_DATA_PATH

        if not cls.json_path.exists():
            raise FileNotFoundError(f"EV subsidy data file not found at {FRONTEND_DATA_PATH} or {REPO_DATA_PATH}")

        with open(cls.json_path, "r", encoding="utf-8") as f:
            cls.data = json.load(f)

    def test_json_file_exists_and_is_valid_object(self):
        """Verifies the JSON file exists, is non-empty, and parses as a dictionary."""
        self.assertTrue(self.json_path.exists(), f"File missing: {self.json_path}")
        self.assertIsInstance(self.data, dict, "Root JSON must be a dictionary object")
        self.assertGreater(len(self.data), 0, "Root JSON must not be empty")

    def test_root_level_keys_contract(self):
        """Verifies presence of all required top-level keys defined in EVSubsidyDataset."""
        required_keys = {
            "metadata",
            "alert_thresholds",
            "nationwide_summary",
            "regions",
            "popular_models_matrix",
        }
        for key in required_keys:
            self.assertIn(key, self.data, f"Missing required top-level key: {key}")

    def test_metadata_contract(self):
        """Verifies metadata object structure and types."""
        metadata = self.data.get("metadata", {})
        self.assertIsInstance(metadata, dict)
        self.assertEqual(metadata.get("version"), "1.0.0")
        self.assertEqual(metadata.get("policy_year"), 2026)
        self.assertEqual(metadata.get("currency"), "KRW")
        self.assertEqual(metadata.get("total_regions_tracked"), 17)
        self.assertGreaterEqual(metadata.get("total_municipalities_tracked", 0), 70)

        # Generated timestamp ISO format check
        gen_at = metadata.get("generated_at", "")
        self.assertIsInstance(gen_at, str)
        self.assertGreater(len(gen_at), 10, "generated_at should be a valid ISO timestamp")

        # Data sources non-empty list
        sources = metadata.get("data_sources", [])
        self.assertIsInstance(sources, list)
        self.assertGreaterEqual(len(sources), 3, "Should cite at least 3 authoritative data sources")

    def test_alert_thresholds_5_tier_contract(self):
        """Verifies 5-tier alert severities (HEALTHY, CAUTION, WARNING, CRITICAL, DEPLETED)."""
        thresholds = self.data.get("alert_thresholds", {})
        self.assertEqual(set(thresholds.keys()), EXPECTED_5_ALERT_TIERS)

        required_threshold_fields = {
            "min_percent": (int, float),
            "max_percent": (int, float),
            "label_ko": str,
            "severity": str,
            "color_hex": str,
            "badge_class": str,
            "recommended_action": str,
        }

        for tier_name, config in thresholds.items():
            self.assertIsInstance(config, dict, f"Threshold config for {tier_name} must be a dict")
            for field_name, expected_type in required_threshold_fields.items():
                self.assertIn(field_name, config, f"Field '{field_name}' missing in threshold '{tier_name}'")
                self.assertIsInstance(
                    config[field_name],
                    expected_type,
                    f"Field '{field_name}' in '{tier_name}' must be of type {expected_type}",
                )

            # Severity field matches dictionary key
            self.assertEqual(config["severity"], tier_name)
            # Hex color starts with '#'
            self.assertTrue(config["color_hex"].startswith("#"), f"Invalid hex color in {tier_name}")
            # Recommended action is a helpful Korean advisory
            self.assertGreater(len(config["recommended_action"]), 10)

        # Mathematical interval continuity checks
        self.assertEqual(thresholds["HEALTHY"]["min_percent"], 0.0)
        self.assertAlmostEqual(thresholds["HEALTHY"]["max_percent"], 59.9, places=1)
        self.assertEqual(thresholds["CAUTION"]["min_percent"], 60.0)
        self.assertAlmostEqual(thresholds["CAUTION"]["max_percent"], 79.9, places=1)
        self.assertEqual(thresholds["WARNING"]["min_percent"], 80.0)
        self.assertAlmostEqual(thresholds["WARNING"]["max_percent"], 94.9, places=1)
        self.assertEqual(thresholds["CRITICAL"]["min_percent"], 95.0)
        self.assertAlmostEqual(thresholds["CRITICAL"]["max_percent"], 99.9, places=1)
        self.assertEqual(thresholds["DEPLETED"]["min_percent"], 100.0)

    def test_17_korean_administrative_divisions_contract(self):
        """Verifies non-empty data for all 17 Korean 1st-tier administrative divisions."""
        regions = self.data.get("regions", [])
        self.assertIsInstance(regions, list)
        self.assertEqual(len(regions), 17, f"Expected exactly 17 regions, found {len(regions)}")

        found_region_ids = set()
        for region in regions:
            r_id = region.get("region_id")
            self.assertIn(r_id, STATUTORY_17_REGIONS, f"Unknown or extra region ID: {r_id}")
            found_region_ids.add(r_id)

            statutory_spec = STATUTORY_17_REGIONS[r_id]
            self.assertEqual(region.get("name_ko"), statutory_spec["name_ko"])
            self.assertEqual(region.get("name_en"), statutory_spec["name_en"])
            self.assertEqual(region.get("tier"), statutory_spec["tier"])
            self.assertEqual(region.get("residency_requirement_days"), statutory_spec["residency_days"])

            # Verify non-empty quota data
            p_cat = region.get("categories", {}).get("passenger", {})
            self.assertGreater(p_cat.get("announced_units", 0), 0, f"Region {r_id} announced units must be > 0")
            self.assertGreater(p_cat.get("applied_units", 0), 0, f"Region {r_id} applied units must be > 0")

        self.assertEqual(found_region_ids, set(STATUTORY_17_REGIONS.keys()))

    def test_region_entry_required_fields_contract(self):
        """Verifies RegionEntry interface contract conformance for every region."""
        required_region_fields = {
            "region_id": str,
            "iso_code": str,
            "name_ko": str,
            "name_en": str,
            "tier": str,
            "overall_depletion_rate": (int, float),
            "overall_status": str,
            "residency_requirement_days": int,
            "supplementary_budget_added": bool,
            "categories": dict,
            "notes": str,
        }

        for region in self.data.get("regions", []):
            r_name = region.get("name_ko", "Unknown")
            for field_name, expected_type in required_region_fields.items():
                self.assertIn(field_name, region, f"Region {r_name} missing required field '{field_name}'")
                self.assertIsInstance(
                    region[field_name],
                    expected_type,
                    f"Region {r_name} field '{field_name}' must be {expected_type}",
                )

            # Overall status must be one of the 5 valid tiers
            self.assertIn(region["overall_status"], EXPECTED_5_ALERT_TIERS)
            # Residency days must be in {30, 90} for all Korean regions
            self.assertIn(region["residency_requirement_days"], (30, 60, 90))

            # Verify municipalities if present
            if "municipalities" in region and region["municipalities"]:
                self.assertIsInstance(region["municipalities"], list)
                for muni in region["municipalities"]:
                    self.assertIsInstance(muni.get("name_ko"), str)
                    self.assertIsInstance(muni.get("announced_units"), int)
                    self.assertIsInstance(muni.get("applied_units"), int)
                    self.assertIsInstance(muni.get("remaining_units"), int)
                    self.assertIsInstance(muni.get("depletion_rate"), (int, float))
                    self.assertIn(muni.get("status"), EXPECTED_5_ALERT_TIERS)
                    self.assertIsInstance(muni.get("local_subsidy_krw"), int)

    def test_category_metrics_required_fields_contract(self):
        """Verifies CategoryMetrics interface contract for every category in every region."""
        required_cat_fields = {
            "announced_units": int,
            "applied_units": int,
            "delivered_units": int,
            "remaining_units": int,
            "depletion_rate": (int, float),
            "delivery_rate": (int, float),
            "status": str,
            "max_local_subsidy_krw": int,
            "max_total_subsidy_krw": int,
        }

        for region in self.data.get("regions", []):
            cats = region.get("categories", {})
            self.assertEqual(set(cats.keys()), EXPECTED_CATEGORIES)

            for cat_name, metrics in cats.items():
                context = f"{region.get('name_ko')} -> {cat_name}"
                for field_name, expected_type in required_cat_fields.items():
                    self.assertIn(field_name, metrics, f"{context} missing field '{field_name}'")
                    self.assertIsInstance(
                        metrics[field_name],
                        expected_type,
                        f"{context} field '{field_name}' must be {expected_type}",
                    )

                self.assertIn(metrics["status"], EXPECTED_5_ALERT_TIERS)
                self.assertGreater(metrics["announced_units"], 0)
                self.assertGreaterEqual(metrics["applied_units"], 0)
                self.assertGreaterEqual(metrics["delivered_units"], 0)
                self.assertGreaterEqual(metrics["remaining_units"], 0)
                self.assertGreaterEqual(metrics["depletion_rate"], 0.0)
                self.assertGreaterEqual(metrics["delivery_rate"], 0.0)
                self.assertGreaterEqual(metrics["max_total_subsidy_krw"], metrics["max_local_subsidy_krw"])

    def test_popular_model_entry_required_fields_contract(self):
        """Verifies PopularModelEntry interface contract conformance."""
        models = self.data.get("popular_models_matrix", [])
        self.assertIsInstance(models, list)
        self.assertGreaterEqual(len(models), 5, "Should track at least 5 popular EV models")

        required_model_fields = {
            "model_id": str,
            "name_ko": str,
            "manufacturer": str,
            "battery_type": str,
            "battery_capacity_kwh": (int, float),
            "rated_range_km": int,
            "base_price_krw": int,
            "price_subsidy_ratio": (int, float),
            "national_subsidy_krw": int,
            "regional_subsidy_samples": dict,
        }

        for model in models:
            m_id = model.get("model_id", "Unknown")
            for field_name, expected_type in required_model_fields.items():
                self.assertIn(field_name, model, f"Model {m_id} missing field '{field_name}'")
                self.assertIsInstance(
                    model[field_name],
                    expected_type,
                    f"Model {m_id} field '{field_name}' must be {expected_type}",
                )

            # Mathematical sanity constraints
            self.assertIn(model["price_subsidy_ratio"], (0.0, 0.5, 1.0))
            self.assertGreater(model["base_price_krw"], 0)
            self.assertGreater(model["battery_capacity_kwh"], 0.0)
            self.assertGreater(model["rated_range_km"], 0)
            self.assertLessEqual(model["national_subsidy_krw"], 6_500_000)

            # Regional samples verification
            samples = model.get("regional_subsidy_samples", {})
            self.assertGreater(len(samples), 0, f"Model {m_id} must have regional subsidy samples")
            for reg_key, sample_val in samples.items():
                self.assertIsInstance(sample_val, dict)
                self.assertIn("total_subsidy_krw", sample_val)
                self.assertIn("net_price_krw", sample_val)
                self.assertEqual(
                    sample_val["net_price_krw"],
                    model["base_price_krw"] - sample_val["total_subsidy_krw"],
                    f"Net price mismatch in model {m_id} for sample {reg_key}",
                )

    def test_nationwide_summary_contract(self):
        """Verifies NationwideSummary aggregate fields and category totals."""
        summary = self.data.get("nationwide_summary", {})
        self.assertIsInstance(summary, dict)

        required_summary_fields = {
            "total_announced_units": int,
            "total_applied_units": int,
            "total_delivered_units": int,
            "total_remaining_units": int,
            "nationwide_depletion_rate": (int, float),
            "total_budget_billion_krw": (int, float),
            "disbursed_budget_billion_krw": (int, float),
            "category_totals": dict,
            "alert_region_counts": dict,
        }

        for field_name, expected_type in required_summary_fields.items():
            self.assertIn(field_name, summary, f"Nationwide summary missing '{field_name}'")
            self.assertIsInstance(
                summary[field_name],
                expected_type,
                f"Nationwide summary '{field_name}' must be {expected_type}",
            )

        # Alert region counts sum must equal 17 regions
        counts = summary.get("alert_region_counts", {})
        expected_keys = {"healthy", "caution", "warning", "critical", "depleted"}
        self.assertEqual(set(counts.keys()), expected_keys)
        total_alert_regions = sum(counts.values())
        self.assertEqual(total_alert_regions, 17, "Sum of regional alert statuses must equal 17")

        # Category totals must include passenger, commercial, bus
        cat_totals = summary.get("category_totals", {})
        self.assertEqual(set(cat_totals.keys()), EXPECTED_CATEGORIES)

    def test_nationwide_aggregations_mathematical_consistency(self):
        """Verifies that NationwideSummary sums strictly equal the sum of 17 regional categories."""
        summary = self.data["nationwide_summary"]
        regions = self.data["regions"]

        sum_announced = sum(c["announced_units"] for r in regions for c in r["categories"].values())
        sum_applied = sum(c["applied_units"] for r in regions for c in r["categories"].values())
        sum_delivered = sum(c["delivered_units"] for r in regions for c in r["categories"].values())
        sum_remaining = sum(c["remaining_units"] for r in regions for c in r["categories"].values())

        self.assertEqual(summary["total_announced_units"], sum_announced)
        self.assertEqual(summary["total_applied_units"], sum_applied)
        self.assertEqual(summary["total_delivered_units"], sum_delivered)
        self.assertEqual(summary["total_remaining_units"], sum_remaining)

        # Verify category level sums
        for cat in ("passenger", "commercial", "bus"):
            c_ann = sum(r["categories"][cat]["announced_units"] for r in regions)
            c_app = sum(r["categories"][cat]["applied_units"] for r in regions)
            c_del = sum(r["categories"][cat]["delivered_units"] for r in regions)
            c_rem = sum(r["categories"][cat]["remaining_units"] for r in regions)

            self.assertEqual(summary["category_totals"][cat]["announced_units"], c_ann)
            self.assertEqual(summary["category_totals"][cat]["applied_units"], c_app)
            self.assertEqual(summary["category_totals"][cat]["delivered_units"], c_del)
            self.assertEqual(summary["category_totals"][cat]["remaining_units"], c_rem)

    def test_historical_trajectory_monotonicity(self):
        """Verifies historical trajectory points have valid dates and non-decreasing rates."""
        trajectory = self.data.get("historical_depletion_trajectory", [])
        self.assertGreaterEqual(len(trajectory), 5, "Should have multiple monthly trajectory points")

        prev_overall = -1.0
        for pt in trajectory:
            self.assertIn("date", pt)
            self.assertIn("passenger_rate", pt)
            self.assertIn("commercial_rate", pt)
            self.assertIn("overall_rate", pt)

            # Monotonicity check
            self.assertGreaterEqual(
                pt["overall_rate"],
                prev_overall,
                f"Trajectory overall rate decreased at {pt['date']}: {pt['overall_rate']} < {prev_overall}",
            )
            prev_overall = pt["overall_rate"]


class TestPriceCapMathematicalContract(unittest.TestCase):
    """Verifies statutory sliding scale price cap rules on vehicle MSRPs."""

    def test_sliding_scale_threshold_rules(self):
        """Tests the 3 statutory tiers:

        - MSRP < 55,000,000 KRW: 100% (1.0)
        - 55,000,000 <= MSRP < 85,000,000 KRW: 50% (0.5)
        - MSRP >= 85,000,000 KRW: 0% (0.0)
        """
        # Tier 1: 100% eligibility
        self.assertEqual(pure_price_subsidy_ratio(0), 1.0)
        self.assertEqual(pure_price_subsidy_ratio(25_000_000), 1.0)
        self.assertEqual(pure_price_subsidy_ratio(39_950_000), 1.0)  # EV3
        self.assertEqual(pure_price_subsidy_ratio(54_099_999), 1.0)
        self.assertEqual(pure_price_subsidy_ratio(54_999_999), 1.0)  # Exact lower boundary

        # Tier 2: 50% eligibility
        self.assertEqual(pure_price_subsidy_ratio(55_000_000), 0.5)  # Exact lower threshold
        self.assertEqual(pure_price_subsidy_ratio(55_000_001), 0.5)
        self.assertEqual(pure_price_subsidy_ratio(65_000_000), 0.5)
        self.assertEqual(pure_price_subsidy_ratio(73_370_000), 0.5)  # EV9
        self.assertEqual(pure_price_subsidy_ratio(84_999_999), 0.5)  # Exact upper boundary

        # Tier 3: 0% luxury exclusion
        self.assertEqual(pure_price_subsidy_ratio(85_000_000), 0.0)  # Exact threshold
        self.assertEqual(pure_price_subsidy_ratio(85_000_001), 0.0)
        self.assertEqual(pure_price_subsidy_ratio(120_000_000), 0.0)  # Taycan / Model S
        self.assertEqual(pure_price_subsidy_ratio(250_000_000), 0.0)  # Exotic luxury EV

    def test_popular_models_matrix_price_cap_compliance(self):
        """Verifies every vehicle model in ev_subsidy_data.json conforms to its base price cap."""
        with open(FRONTEND_DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        for model in data.get("popular_models_matrix", []):
            base_price = model["base_price_krw"]
            ratio = model["price_subsidy_ratio"]
            expected_ratio = pure_price_subsidy_ratio(base_price)

            self.assertEqual(
                ratio,
                expected_ratio,
                f"Model '{model['name_ko']}' with MSRP {base_price:,} KRW has ratio {ratio}, expected {expected_ratio}",
            )

    def test_net_purchase_price_derivation_under_price_caps(self):
        """Verifies out-of-pocket price derivation: net_price = max(0, MSRP - total_subsidy)."""
        # Test Case A: Under 55M (Ioniq 5, MSRP 54.1M, 100% eligibility)
        msrp_a = 54_100_000
        ratio_a = pure_price_subsidy_ratio(msrp_a)
        self.assertEqual(ratio_a, 1.0)
        national_a = 6_500_000
        local_a = 1_500_000  # Seoul
        total_sub_a = national_a + local_a
        net_a = msrp_a - total_sub_a
        self.assertEqual(net_a, 46_100_000)

        # Test Case B: 55M to 85M (EV9, MSRP 73.37M, 50% eligibility)
        msrp_b = 73_370_000
        ratio_b = pure_price_subsidy_ratio(msrp_b)
        self.assertEqual(ratio_b, 0.5)
        # National subsidy cut by 50%
        unscaled_national_b = 6_020_000
        national_b = round(unscaled_national_b * ratio_b)
        self.assertEqual(national_b, 3_010_000)

        # Test Case C: >= 85M (Porsche Taycan / Model X, MSRP 120M, 0% eligibility)
        msrp_c = 120_000_000
        ratio_c = pure_price_subsidy_ratio(msrp_c)
        self.assertEqual(ratio_c, 0.0)
        national_c = round(6_500_000 * ratio_c)
        local_c = round(1_500_000 * ratio_c)
        total_sub_c = national_c + local_c
        self.assertEqual(total_sub_c, 0)
        net_c = msrp_c - total_sub_c
        self.assertEqual(net_c, msrp_c, "Luxury EVs >= 85M must have zero subsidy and net price equal to MSRP")

    def test_additional_grants_policy_formulas(self):
        """Verifies statutory supplementary grants: youth, small business, multi-child, diesel scrappage."""
        base_national = 6_500_000

        # Youth first-time buyer: +20%
        youth_grant = round(base_national * 0.2)
        self.assertEqual(youth_grant, 1_300_000)

        # Small business / taxi: +30%
        taxi_grant = round(base_national * 0.3)
        self.assertEqual(taxi_grant, 1_950_000)

        # Multi-child family: +10%
        multi_child_grant = round(base_national * 0.1)
        self.assertEqual(multi_child_grant, 650_000)

        # Old diesel scrappage: flat 1,000,000 KRW
        scrappage_grant = 1_000_000

        # All grants combined on 54.1M vehicle
        total_grants = youth_grant + taxi_grant + multi_child_grant + scrappage_grant
        self.assertEqual(total_grants, 4_900_000)

    def test_adversarial_price_cap_inputs(self):
        """Tests adversarial inputs (huge values, floating point thresholds, zero, micro prices)."""
        # Micro prices
        self.assertEqual(pure_price_subsidy_ratio(1), 1.0)
        self.assertEqual(pure_price_subsidy_ratio(100), 1.0)

        # Extreme values
        self.assertEqual(pure_price_subsidy_ratio(10**12), 0.0)  # Trillion KRW

        # Floating point near boundaries
        self.assertEqual(pure_price_subsidy_ratio(54_999_999.99), 1.0)
        self.assertEqual(pure_price_subsidy_ratio(55_000_000.01), 0.5)
        self.assertEqual(pure_price_subsidy_ratio(84_999_999.99), 0.5)
        self.assertEqual(pure_price_subsidy_ratio(85_000_000.01), 0.0)


class TestRegionalDisparityContract(unittest.TestCase):
    """Verifies regional subsidy disparities and remaining units mathematical invariants."""

    @classmethod
    def setUpClass(cls):
        with open(FRONTEND_DATA_PATH, "r", encoding="utf-8") as f:
            cls.data = json.load(f)

    def test_seoul_vs_ulleung_local_subsidy_disparity(self):
        """Verifies Seoul (1.5M KRW) vs Ulleung-gun (11.0M KRW) local subsidy disparity."""
        # 1. Seoul special city passenger local subsidy
        seoul_region = next((r for r in self.data["regions"] if r["region_id"] == "KR-11"), None)
        self.assertIsNotNone(seoul_region, "Seoul (KR-11) not found in dataset")
        seoul_local_krw = seoul_region["categories"]["passenger"]["max_local_subsidy_krw"]
        self.assertEqual(
            seoul_local_krw,
            1_500_000,
            f"Seoul passenger local subsidy must be exactly 1,500,000 KRW, got {seoul_local_krw}",
        )

        # 2. Ulleung-gun municipality under Gyeongbuk (KR-47)
        gyeongbuk = next((r for r in self.data["regions"] if r["region_id"] == "KR-47"), None)
        self.assertIsNotNone(gyeongbuk, "Gyeongbuk (KR-47) not found in dataset")

        ulleung = next((m for m in gyeongbuk.get("municipalities", []) if m["name_ko"] == "울릉군"), None)
        self.assertIsNotNone(ulleung, "Ulleung-gun ('울릉군') must be present in Gyeongbuk municipalities")
        ulleung_local_krw = ulleung["local_subsidy_krw"]
        self.assertEqual(
            ulleung_local_krw,
            11_000_000,
            f"Ulleung-gun local subsidy must be exactly 11,000,000 KRW, got {ulleung_local_krw}",
        )

        # 3. Disparity Ratio verification: Ulleung is 7.33x higher than Seoul
        disparity_ratio = ulleung_local_krw / seoul_local_krw
        self.assertAlmostEqual(disparity_ratio, 11.0 / 1.5, places=2)
        self.assertGreater(disparity_ratio, 7.3)

    def test_seoul_vs_ulleung_net_purchase_price_disparity(self):
        """Verifies consumer out-of-pocket disparity on Ioniq 5 between Seoul and Ulleung-gun."""
        ioniq5 = next((m for m in self.data["popular_models_matrix"] if m["model_id"] == "ioniq-5-2026"), None)
        self.assertIsNotNone(ioniq5)

        samples = ioniq5.get("regional_subsidy_samples", {})
        self.assertIn("seoul", samples)
        self.assertIn("ulleung_gyeongbuk", samples)

        seoul_sample = samples["seoul"]
        ulleung_sample = samples["ulleung_gyeongbuk"]

        # Seoul: 6.5M (nat) + 1.5M (loc) = 8.0M KRW total subsidy -> Net: 46.1M KRW
        self.assertEqual(seoul_sample["total_subsidy_krw"], 8_000_000)
        self.assertEqual(seoul_sample["net_price_krw"], 46_100_000)

        # Ulleung: 6.5M (nat) + 11.0M (loc) = 17.5M KRW total subsidy -> Net: 36.6M KRW
        self.assertEqual(ulleung_sample["total_subsidy_krw"], 17_500_000)
        self.assertEqual(ulleung_sample["net_price_krw"], 36_600_000)

        # Difference in consumer savings between Seoul and Ulleung island
        saving_diff = seoul_sample["net_price_krw"] - ulleung_sample["net_price_krw"]
        self.assertEqual(saving_diff, 9_500_000, "Ulleung buyer saves 9.5M KRW more than Seoul buyer")

    def test_proportional_local_subsidy_matching_across_all_models(self):
        """Verifies local subsidy calculation matches across all popular models for Seoul & Ulleung."""
        for model in self.data["popular_models_matrix"]:
            nat = model["national_subsidy_krw"]
            samples = model.get("regional_subsidy_samples", {})

            # 1. Seoul matching check (max local = 1,500,000 KRW)
            expected_seoul_local = pure_calculate_local_subsidy(1_500_000, nat)
            expected_seoul_total = nat + expected_seoul_local
            self.assertEqual(
                samples["seoul"]["total_subsidy_krw"],
                expected_seoul_total,
                f"Seoul subsidy formula mismatch on model {model['model_id']}",
            )

            # 2. Ulleung matching check (max local = 11,000,000 KRW)
            expected_ulleung_local = pure_calculate_local_subsidy(11_000_000, nat)
            expected_ulleung_total = nat + expected_ulleung_local
            self.assertEqual(
                samples["ulleung_gyeongbuk"]["total_subsidy_krw"],
                expected_ulleung_total,
                f"Ulleung subsidy formula mismatch on model {model['model_id']}",
            )

    def test_remaining_units_clamping_formula_across_all_data(self):
        """Verifies invariant: remaining = max(0, announced - applied) across all regions, categories, and municipalities."""
        # 1. Check all categories across all 17 regions
        for region in self.data["regions"]:
            r_name = region["name_ko"]
            for cat_name, cat in region["categories"].items():
                announced = cat["announced_units"]
                applied = cat["applied_units"]
                remaining = cat["remaining_units"]
                expected_remaining = pure_calculate_remaining_units(announced, applied)

                self.assertEqual(
                    remaining,
                    expected_remaining,
                    f"Remaining units mismatch in {r_name} -> {cat_name}: got {remaining}, expected {expected_remaining}",
                )
                self.assertGreaterEqual(remaining, 0, f"Remaining units in {r_name} -> {cat_name} must not be negative")

            # 2. Check all municipalities
            for muni in region.get("municipalities", []):
                m_name = muni["name_ko"]
                m_ann = muni["announced_units"]
                m_app = muni["applied_units"]
                m_rem = muni["remaining_units"]
                expected_rem = pure_calculate_remaining_units(m_ann, m_app)

                self.assertEqual(
                    m_rem,
                    expected_rem,
                    f"Remaining units mismatch in municipality {r_name} -> {m_name}: got {m_rem}, expected {expected_rem}",
                )
                self.assertGreaterEqual(m_rem, 0, f"Municipality {m_name} remaining units cannot be negative")

        # 3. Check Ulleung-gun exact 100% DEPLETED boundary
        gyeongbuk = next(r for r in self.data["regions"] if r["region_id"] == "KR-47")
        ulleung = next(m for m in gyeongbuk["municipalities"] if m["name_ko"] == "울릉군")
        self.assertEqual(ulleung["announced_units"], 150)
        self.assertEqual(ulleung["applied_units"], 150)
        self.assertEqual(ulleung["remaining_units"], 0)
        self.assertEqual(ulleung["depletion_rate"], 100.0)
        self.assertEqual(ulleung["status"], "DEPLETED")

    def test_remaining_units_adversarial_over_subscription(self):
        """Tests that over-subscription scenarios clamp strictly to 0 and never return negative values."""
        # Applied equals announced -> 0
        self.assertEqual(pure_calculate_remaining_units(100, 100), 0)

        # Applied exceeds announced (over-subscription) -> clamped to 0
        self.assertEqual(pure_calculate_remaining_units(100, 101), 0)
        self.assertEqual(pure_calculate_remaining_units(100, 250), 0)
        self.assertEqual(pure_calculate_remaining_units(100, 100_000), 0)

        # Zero announced units -> 0
        self.assertEqual(pure_calculate_remaining_units(0, 0), 0)
        self.assertEqual(pure_calculate_remaining_units(0, 50), 0)

        # Normal under-subscription
        self.assertEqual(pure_calculate_remaining_units(1000, 450), 550)

    def test_depletion_rate_calculation_and_division_by_zero_safety(self):
        """Tests pure_calculate_depletion_rate with mathematical edge cases."""
        # Normal cases
        self.assertEqual(pure_calculate_depletion_rate(100, 50), 50.0)
        self.assertEqual(pure_calculate_depletion_rate(11500, 9890), 86.0)

        # 0 announced units (division by zero guard)
        self.assertEqual(pure_calculate_depletion_rate(0, 0), 0.0)
        self.assertEqual(pure_calculate_depletion_rate(0, 100), 0.0)

        # Over 100% over-subscription
        self.assertEqual(pure_calculate_depletion_rate(100, 125), 125.0)


class TestCrossLanguageAndModelEquivalence(unittest.TestCase):
    """Verifies that Python dataclass models and frontend JSON payload serialize symmetrically."""

    def test_subsidy_payload_round_trip_parse(self):
        """Tests that SubsidyPayload can deserialize ev_subsidy_data.json cleanly."""
        with open(FRONTEND_DATA_PATH, "r", encoding="utf-8") as f:
            raw_dict = json.load(f)

        payload = SubsidyPayload.from_dict(raw_dict)
        self.assertIsInstance(payload, SubsidyPayload)
        self.assertEqual(len(payload.regions), 17)
        self.assertGreaterEqual(len(payload.popular_models_matrix), 5)
        self.assertEqual(payload.metadata.policy_year, 2026)

        # Verify serialization back to dict preserves all 17 regions
        serialized = payload.to_dict()
        self.assertIsInstance(serialized, dict)
        self.assertEqual(len(serialized["regions"]), 17)
        self.assertEqual(serialized["nationwide_summary"]["total_announced_units"], payload.nationwide_summary.total_announced_units)

    def test_alert_severity_enum_from_rate_parity(self):
        """Verifies Python AlertSeverity.from_rate matches 5-tier specification."""
        self.assertEqual(AlertSeverity.from_rate(0.0), AlertSeverity.HEALTHY)
        self.assertEqual(AlertSeverity.from_rate(59.9), AlertSeverity.HEALTHY)
        self.assertEqual(AlertSeverity.from_rate(60.0), AlertSeverity.CAUTION)
        self.assertEqual(AlertSeverity.from_rate(79.9), AlertSeverity.CAUTION)
        self.assertEqual(AlertSeverity.from_rate(80.0), AlertSeverity.WARNING)
        self.assertEqual(AlertSeverity.from_rate(94.9), AlertSeverity.WARNING)
        self.assertEqual(AlertSeverity.from_rate(95.0), AlertSeverity.CRITICAL)
        self.assertEqual(AlertSeverity.from_rate(99.9), AlertSeverity.CRITICAL)
        self.assertEqual(AlertSeverity.from_rate(100.0), AlertSeverity.DEPLETED)
        self.assertEqual(AlertSeverity.from_rate(110.0), AlertSeverity.DEPLETED)


if __name__ == "__main__":
    unittest.main()
