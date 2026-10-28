"""Unit tests for Sync 21 uniform dict-like accessors on subsidy models.

Verifies uniform mapping protocol (__getitem__, __contains__, get) across:
- PopularModelEntry
- MunicipalityMetrics
- CategoryMetrics
- RegionRecord
- NationwideSummary
"""

import unittest
from tracker.subsidy_models import (
    CategoryMetrics,
    MunicipalityMetrics,
    NationwideSummary,
    PopularModelEntry,
    RegionRecord,
)


class TestSubsidyModelsDictAccess(unittest.TestCase):
    """Test suite verifying mapping protocol adherence on subsidy dataclasses."""

    def test_popular_model_entry_dict_access(self):
        """PopularModelEntry must support __getitem__, __contains__, and get()."""
        model = PopularModelEntry(
            model_id="ioniq5_standard",
            name_ko="아이오닉 5 스탠다드",
            manufacturer="현대",
            battery_type="NCM",
            battery_capacity_kwh=58.2,
            rated_range_km=370,
            base_price_krw=50000000,
            price_subsidy_ratio=1.0,
            national_subsidy_krw=6500000,
            regional_subsidy_samples={"KR-11": {"local_subsidy_krw": 1500000}},
        )

        # __getitem__ existing attributes
        self.assertEqual(model["model_id"], "ioniq5_standard")
        self.assertEqual(model["name_ko"], "아이오닉 5 스탠다드")
        self.assertEqual(model["battery_capacity_kwh"], 58.2)
        self.assertEqual(model["regional_subsidy_samples"]["KR-11"]["local_subsidy_krw"], 1500000)

        # get() existing attributes
        self.assertEqual(model.get("model_id"), "ioniq5_standard")
        self.assertEqual(model.get("name_ko"), "아이오닉 5 스탠다드")

        # __contains__ existing attributes
        self.assertIn("model_id", model)
        self.assertIn("name_ko", model)
        self.assertIn("regional_subsidy_samples", model)

        # Missing attributes
        self.assertNotIn("non_existent_key", model)
        self.assertEqual(model.get("non_existent_key", "default_val"), "default_val")
        self.assertIsNone(model.get("non_existent_key"))

        with self.assertRaises(KeyError):
            _ = model["non_existent_key"]

        # Non-string keys handling
        self.assertNotIn(999, model)
        self.assertEqual(model.get(999, "fallback"), "fallback")
        with self.assertRaises(KeyError):
            _ = model[999]

    def test_municipality_metrics_dict_access(self):
        """MunicipalityMetrics must support uniform __getitem__, __contains__, and get()."""
        muni = MunicipalityMetrics(
            name_ko="성남시",
            announced_units=350,
            applied_units=300,
            remaining_units=50,
            depletion_rate=85.7,
            status="WARNING",
            local_subsidy_krw=3000000,
            muni_id="KR-41-131",
            name_en="Seongnam-si",
            category="passenger",
            delivered_units=280,
            total_subsidy_krw=9500000,
        )

        # __getitem__ existing attributes
        self.assertEqual(muni["name_ko"], "성남시")
        self.assertEqual(muni["announced_units"], 350)
        self.assertEqual(muni["depletion_rate"], 85.7)
        self.assertEqual(muni["muni_id"], "KR-41-131")

        # get() existing attributes
        self.assertEqual(muni.get("name_ko"), "성남시")
        self.assertEqual(muni.get("status"), "WARNING")

        # __contains__ existing attributes
        self.assertIn("name_ko", muni)
        self.assertIn("announced_units", muni)
        self.assertIn("muni_id", muni)

        # Missing attributes
        self.assertNotIn("unknown_metric", muni)
        self.assertEqual(muni.get("unknown_metric", 123), 123)
        self.assertIsNone(muni.get("unknown_metric"))

        with self.assertRaises(KeyError):
            _ = muni["unknown_metric"]

        # Non-string keys handling
        self.assertNotIn(100, muni)
        self.assertEqual(muni.get(100, "default"), "default")
        with self.assertRaises(KeyError):
            _ = muni[100]

    def test_category_metrics_dict_access(self):
        """CategoryMetrics must support uniform __getitem__, __contains__, and get()."""
        cat = CategoryMetrics(
            announced_units=1200,
            applied_units=900,
            delivered_units=850,
            remaining_units=300,
            depletion_rate=75.0,
            delivery_rate=70.8,
            status="CAUTION",
            max_local_subsidy_krw=4000000,
            max_total_subsidy_krw=10500000,
        )

        self.assertEqual(cat["announced_units"], 1200)
        self.assertEqual(cat.get("announced_units"), 1200)
        self.assertIn("announced_units", cat)
        self.assertNotIn("missing_field", cat)
        self.assertEqual(cat.get("missing_field", "default"), "default")
        with self.assertRaises(KeyError):
            _ = cat["missing_field"]

    def test_region_record_dict_access(self):
        """RegionRecord must support uniform __getitem__, __contains__, and get()."""
        region = RegionRecord(
            region_id="KR-41",
            iso_code="KR-41",
            name_ko="경기도",
            name_en="Gyeonggi-do",
            overall_depletion_rate=88.5,
            overall_status="WARNING",
        )

        self.assertEqual(region["name_ko"], "경기도")
        self.assertEqual(region.get("name_ko"), "경기도")
        self.assertIn("name_ko", region)
        self.assertNotIn("invalid_col", region)
        self.assertEqual(region.get("invalid_col", 777), 777)
        with self.assertRaises(KeyError):
            _ = region["invalid_col"]

    def test_nationwide_summary_dict_access(self):
        """NationwideSummary must support uniform __getitem__, __contains__, and get()."""
        summary = NationwideSummary(
            total_announced_units=150000,
            total_applied_units=130000,
            total_delivered_units=120000,
            total_remaining_units=20000,
            nationwide_depletion_rate=86.7,
            total_budget_billion_krw=2200.0,
            disbursed_budget_billion_krw=1900.0,
            category_totals={},
            alert_region_counts={"WARNING": 5},
        )

        self.assertEqual(summary["total_announced_units"], 150000)
        self.assertEqual(summary.get("total_announced_units"), 150000)
        self.assertIn("total_announced_units", summary)
        self.assertNotIn("non_existent_key", summary)
        self.assertEqual(summary.get("non_existent_key", "default"), "default")
        with self.assertRaises(KeyError):
            _ = summary["non_existent_key"]


if __name__ == "__main__":
    unittest.main()
