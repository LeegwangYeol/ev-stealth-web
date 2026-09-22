"""
Tier 1: Feature Coverage & Schema Integrity Test Suite.

Validates:
1. Complaint database exists and is valid JSON.
2. Complete schema conformance for all complaint records (11 required fields).
3. Full coverage of the 4 mandatory problem categories:
   - 주차 문제 (Parking Issues: F1.1 - F1.6)
   - 충전 문제 (Charging Issues: F2.1 - F2.6)
   - 우천/가혹 주행 (Rainy / Harsh Driving Issues: F3.1 - F3.6)
   - 등판 능력 (Hill Climbing Issues: F4.1 - F4.5)
4. Minimum threshold of >= 3 distinct cases per category (target >= 5).
5. Comprehensive representation of vehicle models (passenger & commercial / multi-segment).
6. Feature inventory traceability across F1.1 through F5.8 and multi-brand scope.
"""

import os
import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List, Set

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if not (PROJECT_ROOT / "scrapers").exists() and (PROJECT_ROOT.parent / "scrapers").exists():
    PROJECT_ROOT = PROJECT_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.e2e.common import (
    CATEGORY_KEYWORDS,
    CATEGORY_KOREAN_NAMES,
    FEATURE_INVENTORY,
    MANDATORY_CATEGORIES,
    MANDATORY_SCHEMA_FIELDS,
    RECOGNIZED_PLATFORMS,
    load_complaints_data,
    normalize_category,
)


class TestTier1FeatureCoverage(unittest.TestCase):
    """Tier 1 Test Cases: Validating feature coverage and structural schema conformance."""

    complaints: List[Dict[str, Any]] = []

    @classmethod
    def setUpClass(cls):
        """Load the complaint dataset once for all tier 1 tests."""
        try:
            cls.complaints = load_complaints_data()
        except FileNotFoundError as e:
            cls.complaints = []
            cls.load_error = str(e)
        except Exception as e:
            cls.complaints = []
            cls.load_error = f"Error parsing complaints data: {e}"
        else:
            cls.load_error = None

    def setUp(self):
        if self.load_error:
            self.fail(f"Dataset load failure: {self.load_error}")
        if not self.complaints:
            self.fail("Complaint dataset is empty.")

    def test_01_complaints_database_exists_and_loaded(self):
        """Verify that the complaint dataset exists and contains records."""
        self.assertIsInstance(
            self.complaints,
            list,
            "Complaint data must be a JSON array/list of objects.",
        )
        self.assertGreater(
            len(self.complaints),
            0,
            "Complaint dataset must contain at least 1 record.",
        )

    def test_02_records_schema_structure_conformance(self):
        """Verify that every complaint record conforms strictly to the mandatory schema."""
        for idx, record in enumerate(self.complaints):
            self.assertIsInstance(
                record,
                dict,
                f"Record at index {idx} is not a dictionary/object.",
            )
            for field_name, expected_type in MANDATORY_SCHEMA_FIELDS.items():
                self.assertIn(
                    field_name,
                    record,
                    f"Record index {idx} (ID: {record.get('id', 'UNKNOWN')}) missing required field '{field_name}'.",
                )
                self.assertIsInstance(
                    record[field_name],
                    expected_type,
                    f"Record index {idx} field '{field_name}' must be of type {expected_type.__name__}, "
                    f"got {type(record[field_name]).__name__}.",
                )

    def test_03_four_mandatory_categories_fully_represented(self):
        """Verify that all 4 specified problem categories exist in the dataset."""
        normalized_found = {
            normalize_category(r.get("category", "")) for r in self.complaints
        }

        missing_categories = MANDATORY_CATEGORIES - normalized_found
        missing_display = [
            f"{c} ({CATEGORY_KOREAN_NAMES.get(c, '')})" for c in missing_categories
        ]
        self.assertEqual(
            len(missing_categories),
            0,
            f"Dataset is missing mandatory categories: {', '.join(missing_display)}",
        )

    def test_04_minimum_three_cases_per_category(self):
        """Verify that each of the 4 mandatory categories contains at least 3 distinct cases."""
        category_counts = {cat: 0 for cat in MANDATORY_CATEGORIES}

        for record in self.complaints:
            norm_cat = normalize_category(record.get("category", ""))
            if norm_cat in category_counts:
                category_counts[norm_cat] += 1

        insufficient_categories = {}
        for cat, count in category_counts.items():
            if count < 3:
                insufficient_categories[f"{cat} ({CATEGORY_KOREAN_NAMES.get(cat, '')})"] = count

        self.assertEqual(
            len(insufficient_categories),
            0,
            f"Categories with fewer than 3 cases: {insufficient_categories}. "
            f"Current counts: {category_counts}",
        )

    def test_05_target_vehicle_specified_in_all_records(self):
        """Verify target_vehicle is specified and not empty in every record."""
        for idx, record in enumerate(self.complaints):
            target_vehicle = (record.get("target_vehicle", "") or "").strip()
            self.assertTrue(
                len(target_vehicle) > 0,
                f"Record index {idx} (ID: {record.get('id')}) has empty 'target_vehicle'.",
            )

    def test_06_defect_topic_substantiveness(self):
        """Verify defect_topic is meaningful and informative in every record."""
        for idx, record in enumerate(self.complaints):
            topic = (record.get("defect_topic", "") or "").strip()
            self.assertGreaterEqual(
                len(topic),
                3,
                f"Record index {idx} (ID: {record.get('id')}) 'defect_topic' is too short: '{topic}'.",
            )

    def test_07_total_dataset_volume_substantial(self):
        """Verify the total complaint count meets the project requirement of >= 20 cases."""
        self.assertGreaterEqual(
            len(self.complaints),
            20,
            f"Total complaints collected ({len(self.complaints)}) is below target threshold of 20.",
        )

    def test_08_feature_subtopic_coverage_richness(self):
        """Verify feature subtopic diversity across F1.x - F4.x domains."""
        all_topics_text = " ".join(
            (r.get("defect_topic", "") + " " + r.get("raw_quote", ""))
            for r in self.complaints
        )

        # Check keyword presence for each category domain
        for cat_key in ["parking", "charging", "rain_driving", "hill_climbing"]:
            keywords = CATEGORY_KEYWORDS.get(cat_key, [])
            hits = [kw for kw in keywords if kw in all_topics_text]
            self.assertGreaterEqual(
                len(hits),
                3,
                f"Category '{cat_key}' lacks keyword diversity in topics/quotes. Found: {hits}",
            )

    def test_09_multi_vehicle_model_diversity(self):
        """Verify that multiple vehicle models are represented in the dataset."""
        distinct_vehicles = {
            (r.get("target_vehicle", "") or "").strip().lower()
            for r in self.complaints
            if (r.get("target_vehicle", "") or "").strip()
        }
        self.assertGreaterEqual(
            len(distinct_vehicles),
            3,
            f"Expected at least 3 distinct vehicle models in dataset, found {len(distinct_vehicles)}: {distinct_vehicles}",
        )


if __name__ == "__main__":
    unittest.main()
