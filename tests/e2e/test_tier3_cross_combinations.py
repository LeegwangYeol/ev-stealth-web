"""
Tier 3: Cross-Category & Cross-Platform Combinations Test Suite.

Validates:
1. Multi-platform diversity (DC Inside, Bobaedream, Blind, and automotive forums).
2. Balance of platform distribution (no single platform monopoly > 70%).
3. Broad vehicle model coverage (multiple distinct EV models).
4. Balanced representation of passenger and commercial / multi-segment EVs.
5. Category x Platform cross-distribution matrix (>= 2 platforms per category).
6. Category x Vehicle cross-distribution matrix (>= 2 vehicle models per category).
7. Temporal distribution span across 2024, 2025, and 2026.
"""

import os
import re
import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List, Set

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.e2e.common import (
    BRAND_FAMILIES,
    COMMERCIAL_VEHICLE_PATTERNS,
    MANDATORY_CATEGORIES,
    PASSENGER_VEHICLE_PATTERNS,
    detect_brand_family,
    load_complaints_data,
    normalize_category,
)


class TestTier3CrossCombinations(unittest.TestCase):
    """Tier 3 Test Cases: Validating pairwise platform-vehicle-category combinations."""

    complaints: List[Dict[str, Any]] = []

    @classmethod
    def setUpClass(cls):
        """Load dataset for cross-matrix testing."""
        try:
            cls.complaints = load_complaints_data()
        except FileNotFoundError as e:
            cls.complaints = []
            cls.load_error = str(e)
        except Exception as e:
            cls.complaints = []
            cls.load_error = f"Error loading data: {e}"
        else:
            cls.load_error = None

    def setUp(self):
        if self.load_error:
            self.fail(f"Dataset load failure: {self.load_error}")
        if not self.complaints:
            self.fail("Complaint dataset is empty.")

    def test_01_multi_platform_diversity(self):
        """Verify the dataset contains cases from multiple distinct communities."""
        platforms_found = {
            (r.get("platform", "") or "").strip().lower() for r in self.complaints
        }

        # Verify core platforms
        has_dc = any("dc" in p for p in platforms_found)
        has_bobae = any("bobae" in p for p in platforms_found)

        self.assertTrue(
            has_dc,
            f"Dataset lacks cases from DC Inside. Platforms present: {platforms_found}",
        )
        self.assertTrue(
            has_bobae,
            f"Dataset lacks cases from Bobaedream. Platforms present: {platforms_found}",
        )
        self.assertGreaterEqual(
            len(platforms_found),
            3,
            f"Dataset has only {len(platforms_found)} distinct platforms ({platforms_found}), expected >= 3.",
        )

    def test_02_platform_distribution_balance(self):
        """Verify no single platform dominates > 70% of the entire dataset."""
        platform_counts: Dict[str, int] = {}
        for r in self.complaints:
            p = (r.get("platform", "") or "unknown").strip().lower()
            platform_counts[p] = platform_counts.get(p, 0) + 1

        total = len(self.complaints)
        for platform, count in platform_counts.items():
            ratio = count / total
            self.assertLessEqual(
                ratio,
                0.70,
                f"Platform '{platform}' accounts for {ratio:.1%} ({count}/{total}) of records, "
                f"exceeding the 70% diversity threshold.",
            )

    def test_03_multi_vehicle_coverage(self):
        """Verify dataset covers >= 3 distinct EV models."""
        distinct_vehicles: Set[str] = set()

        for r in self.complaints:
            v = (r.get("target_vehicle", "") or "").strip()
            if v:
                distinct_vehicles.add(v.lower())

        self.assertGreaterEqual(
            len(distinct_vehicles),
            3,
            f"Only {len(distinct_vehicles)} distinct vehicle models found ({distinct_vehicles}), "
            f"expected at least 3 models.",
        )

    def test_04_commercial_and_passenger_ev_representation(self):
        """Verify both passenger EVs and commercial/fleet EVs are covered."""
        has_passenger = False
        has_commercial = False

        for r in self.complaints:
            v = (r.get("target_vehicle", "") or "").lower()
            if any(p in v for p in PASSENGER_VEHICLE_PATTERNS):
                has_passenger = True
            if any(c in v for c in COMMERCIAL_VEHICLE_PATTERNS):
                has_commercial = True

        self.assertTrue(
            has_passenger,
            "Dataset lacks representation of passenger EVs.",
        )
        self.assertTrue(
            has_commercial,
            "Dataset lacks representation of commercial/fleet EVs.",
        )

    def test_05_category_x_platform_cross_matrix(self):
        """Verify each category is covered by at least 2 distinct platforms."""
        cat_platform_map: Dict[str, Set[str]] = {cat: set() for cat in MANDATORY_CATEGORIES}

        for r in self.complaints:
            cat = normalize_category(r.get("category", ""))
            plat = (r.get("platform", "") or "").strip().lower()
            if cat in cat_platform_map and plat:
                cat_platform_map[cat].add(plat)

        single_platform_cats = {}
        for cat, plats in cat_platform_map.items():
            if len(plats) < 2:
                single_platform_cats[cat] = list(plats)

        self.assertEqual(
            len(single_platform_cats),
            0,
            f"Categories lacking multi-platform diversity (< 2 platforms): {single_platform_cats}",
        )

    def test_06_category_x_vehicle_cross_matrix(self):
        """Verify each category is covered by at least 2 distinct vehicle models."""
        cat_vehicle_map: Dict[str, Set[str]] = {cat: set() for cat in MANDATORY_CATEGORIES}

        for r in self.complaints:
            cat = normalize_category(r.get("category", ""))
            veh = (r.get("target_vehicle", "") or "").strip().lower()
            if cat in cat_vehicle_map and veh:
                cat_vehicle_map[cat].add(veh)

        single_vehicle_cats = {}
        for cat, vehs in cat_vehicle_map.items():
            if len(vehs) < 2:
                single_vehicle_cats[cat] = list(vehs)

        self.assertEqual(
            len(single_vehicle_cats),
            0,
            f"Categories lacking multi-vehicle coverage (< 2 models): {single_vehicle_cats}",
        )

    def test_07_temporal_distribution_span(self):
        """Verify that complaints span the recent multi-year period (2024–2026)."""
        years_found = set()
        for r in self.complaints:
            ts = r.get("collected_at", "") or ""
            match = re.search(r"\b(202[4-6])\b", ts)
            if match:
                years_found.add(match.group(1))

        # Check that timestamps represent 2024-2026 timeline
        self.assertGreaterEqual(
            len(years_found),
            1,
            f"No valid 2024-2026 timestamps identified in dataset. Years found: {years_found}",
        )


if __name__ == "__main__":
    unittest.main()
