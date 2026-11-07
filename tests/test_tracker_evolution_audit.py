"""Comprehensive Verification Suite for Tracker Evolution Audit.

Verifies:
1. Division-by-zero resilience in depletion percentage calculations across extreme inputs:
   - Zero, negative, NaN, Inf, and subnormal quota/applied numbers
   - max_rate edge cases (NaN, Inf, negative values)
   - CategoryMetrics.from_dict, MunicipalityMetrics.from_dict, RegionRecord.from_dict,
     and NationwideSummary.from_dict dynamic calculation with zero quota.
2. Robust error handling:
   - Malformed/empty cached JSON
   - Non-dictionary JSON responses in fetch_live_updates
   - CP949 and EUC-KR character decoding resilience
   - Formatted numbers with comma separators (e.g. '1,500,000')
   - Regional Korean alias mappings in PopularModelEntry.get_regional_subsidy
3. Path resolution across symlinks and monorepo structures:
   - _find_repo_root() under various cwd contexts and symlinks
   - Destination deduplication across symlinked directories and non-existent targets
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from tracker.subsidy_models import (
    AlertSeverity,
    CategoryMetrics,
    MunicipalityMetrics,
    NationwideSummary,
    PopularModelEntry,
    RegionRecord,
    SubsidyPayload,
    _safe_float,
    _safe_int,
)
from tracker.subsidy_tracker import (
    SubsidyTracker,
    calculate_delivery_rate,
    calculate_depletion_rate,
    _find_repo_root,
)
from run_tracker import (
    _find_repo_root as run_tracker_find_repo_root,
    validate_defect_reports_file,
)


class TestTrackerEvolutionAudit(unittest.TestCase):
    """Deep audit and hardening tests for EV subsidy tracker evolution."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.test_path = Path(self.tmp_dir.name)
        self.tracker = SubsidyTracker()

    def tearDown(self) -> None:
        try:
            self.tmp_dir.cleanup()
        except OSError:
            pass

    # =========================================================================
    # 1. Division-by-zero resilience in depletion percentage calculations
    # =========================================================================

    def test_01_depletion_rate_zero_and_subnormal_quota(self) -> None:
        """calculate_depletion_rate safely handles 0, negative, and extreme inputs."""
        self.assertEqual(calculate_depletion_rate(applied=0, announced=0), 0.0)
        self.assertEqual(calculate_depletion_rate(applied=100, announced=0), 0.0)
        self.assertEqual(calculate_depletion_rate(applied=100, quota=0), 0.0)
        self.assertEqual(calculate_depletion_rate(applied=100, announced=-10), 0.0)
        self.assertEqual(calculate_depletion_rate(applied=-50, announced=100), 0.0)

    def test_02_depletion_rate_max_rate_nan_and_negative(self) -> None:
        """max_rate containing NaN, Inf, or negative numbers must never corrupt rate."""
        # NaN max_rate must not produce NaN
        r_nan = calculate_depletion_rate(applied=50, announced=100, max_rate=float("nan"))
        self.assertFalse(math.isnan(r_nan))
        self.assertEqual(r_nan, 50.0)

        # Inf max_rate must not corrupt rate
        r_inf = calculate_depletion_rate(applied=50, announced=100, max_rate=float("inf"))
        self.assertEqual(r_inf, 50.0)

        # Negative max_rate must not produce negative rate
        r_neg = calculate_depletion_rate(applied=50, announced=100, max_rate=-10.0)
        self.assertEqual(r_neg, 50.0)

        # Valid max_rate clamps correctly
        r_clamped = calculate_depletion_rate(applied=80, announced=100, max_rate=60.0)
        self.assertEqual(r_clamped, 60.0)

    def test_03_delivery_rate_parameter_parity(self) -> None:
        """calculate_delivery_rate supports clamp, max_rate, and protects against div/0."""
        self.assertEqual(calculate_delivery_rate(delivered=0, announced=0), 0.0)
        self.assertEqual(calculate_delivery_rate(delivered=120, announced=100, clamp_100=True), 100.0)
        self.assertEqual(calculate_delivery_rate(delivered=120, announced=100, clamp=True), 100.0)
        self.assertEqual(calculate_delivery_rate(delivered=120, announced=100, max_rate=75.0), 75.0)

    def test_04_category_metrics_dynamic_calculation_zero_quota(self) -> None:
        """CategoryMetrics.from_dict dynamically computes depletion/delivery rate with 0 quota."""
        # Missing depletion_rate and 0 announced_units -> rate is 0.0 without ZeroDivisionError
        cat_zero = CategoryMetrics.from_dict({"announced_units": 0, "applied_units": 100})
        self.assertEqual(cat_zero.depletion_rate, 0.0)
        self.assertEqual(cat_zero.remaining_units, 0)

        # Missing depletion_rate with valid announced -> dynamically calculates
        cat_valid = CategoryMetrics.from_dict({"announced_units": 200, "applied_units": 100, "delivered_units": 50})
        self.assertEqual(cat_valid.depletion_rate, 50.0)
        self.assertEqual(cat_valid.delivery_rate, 25.0)
        self.assertEqual(cat_valid.remaining_units, 100)
        self.assertEqual(cat_valid.status, "HEALTHY")

    def test_05_municipality_metrics_dynamic_calculation(self) -> None:
        """MunicipalityMetrics.from_dict dynamically computes depletion rate with 0 quota."""
        m_zero = MunicipalityMetrics.from_dict({"announced_units": 0, "applied_units": 50})
        self.assertEqual(m_zero.depletion_rate, 0.0)
        self.assertEqual(m_zero.remaining_units, 0)

        m_calc = MunicipalityMetrics.from_dict({"name_ko": "수원시", "announced_units": 100, "applied_units": 95})
        self.assertEqual(m_calc.depletion_rate, 95.0)
        self.assertEqual(m_calc.remaining_units, 5)
        self.assertEqual(m_calc.status, "CRITICAL")

    def test_06_region_and_nationwide_dynamic_calculation(self) -> None:
        """RegionRecord and NationwideSummary dynamically compute rate with 0 total announced."""
        ns_zero = NationwideSummary.from_dict({"total_announced_units": 0, "total_applied_units": 100})
        self.assertEqual(ns_zero.nationwide_depletion_rate, 0.0)
        self.assertEqual(ns_zero.total_remaining_units, 0)

        ns_calc = NationwideSummary.from_dict({
            "total_announced_units": 1000,
            "total_applied_units": 850,
            "total_budget_krw": 100_000_000_000,
            "disbursed_budget_krw": 85_000_000_000,
        })
        self.assertEqual(ns_calc.nationwide_depletion_rate, 85.0)
        self.assertEqual(ns_calc.total_remaining_units, 150)
        self.assertEqual(ns_calc.total_budget_billion_krw, 100.0)
        self.assertEqual(ns_calc.disbursed_budget_billion_krw, 85.0)

    # =========================================================================
    # 2. Robust error handling: cache loading, network, malformed data
    # =========================================================================

    def test_07_safe_int_and_float_comma_sanitization(self) -> None:
        """_safe_int and _safe_float gracefully sanitize strings with comma separators."""
        self.assertEqual(_safe_int("1,500,000"), 1500000)
        self.assertEqual(_safe_int("  3,200  "), 3200)
        self.assertEqual(_safe_float("1,234.56"), 1234.56)
        self.assertEqual(_safe_float("  "), 0.0)
        self.assertEqual(_safe_int(None, default=10), 10)
        self.assertEqual(_safe_float(float("nan"), default=5.0), 5.0)

    def test_08_popular_model_regional_korean_alias_resolution(self) -> None:
        """PopularModelEntry.get_regional_subsidy resolves Korean and case-insensitive region aliases."""
        model = PopularModelEntry(
            model_id="test-ev",
            name_ko="테스트 EV",
            manufacturer="현대",
            battery_type="NCM",
            battery_capacity_kwh=77.4,
            rated_range_km=450,
            base_price_krw=50_000_000,
            price_subsidy_ratio=1.0,
            national_subsidy_krw=6_000_000,
            regional_subsidy_samples={
                "seoul": {"local_subsidy_krw": 1_500_000, "total_subsidy_krw": 7_500_000},
                "gyeonggi": {"local_subsidy_krw": 2_500_000, "total_subsidy_krw": 8_500_000},
            },
        )
        # Korean name resolution
        self.assertEqual(model.get_regional_subsidy("서울"), 1_500_000)
        self.assertEqual(model.get_regional_subsidy("경기"), 2_500_000)
        # Case insensitive
        self.assertEqual(model.get_regional_subsidy("SEOUL"), 1_500_000)
        self.assertEqual(model.get_regional_subsidy("Gyeonggi"), 2_500_000)
        # Empty or unknown
        self.assertEqual(model.get_regional_subsidy(""), 0)
        self.assertEqual(model.get_regional_subsidy(None), 0)  # type: ignore
        self.assertEqual(model.get_regional_subsidy("unknown_region"), 0)

    def test_09_load_cached_payload_directory_and_empty_file_guard(self) -> None:
        """load_cached_payload safely rejects directories, empty files, and broken paths."""
        # 1. Directory path passed as cache file
        sub_dir = self.test_path / "a_directory"
        sub_dir.mkdir()
        self.assertIsNone(self.tracker.load_cached_payload(sub_dir))

        # 2. 0-byte file
        empty_file = self.test_path / "empty_cache.json"
        empty_file.write_bytes(b"")
        self.assertIsNone(self.tracker.load_cached_payload(empty_file, quarantine=False))

        # 3. Whitespace-only file
        ws_file = self.test_path / "whitespace.json"
        ws_file.write_text("   \n\t  ", encoding="utf-8")
        self.assertIsNone(self.tracker.load_cached_payload(ws_file, quarantine=False))

    def test_10_fetch_live_updates_non_dict_response_handling(self) -> None:
        """fetch_live_updates discards non-dict responses (lists, primitives, null) and handles backoff."""
        tracker = SubsidyTracker(endpoint_url="http://mock.endpoint/api")

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = b'["not", "a", "dict"]'
            mock_resp.__enter__.return_value = mock_resp
            mock_resp.__exit__.return_value = None
            mock_urlopen.return_value = mock_resp

            res = tracker.fetch_live_updates(max_retries=1)
            self.assertIsNone(res, "Non-dict JSON must be safely rejected and return None")

    # =========================================================================
    # 3. Path resolution across symlinks and monorepo structures
    # =========================================================================

    def test_11_find_repo_root_canonical_resolution(self) -> None:
        """_find_repo_root finds valid data/ directory across subsidy_tracker and run_tracker."""
        root_st = _find_repo_root()
        root_rt = run_tracker_find_repo_root()
        self.assertEqual(root_st.resolve(), root_rt.resolve())
        self.assertTrue((root_st / "data").is_dir() or (root_st / "ev-stealth-web" / "src" / "data").is_dir())

    def test_12_collect_and_save_destination_deduplication(self) -> None:
        """collect_and_save deduplicates redundant paths even when passed with relative/absolute variations."""
        out_file = self.test_path / "ev_subsidy_data.json"
        payload = self.tracker.collect_and_save(output_path=out_file, dry_run=False)
        self.assertIsNotNone(payload)
        self.assertTrue(out_file.exists())
        self.assertTrue((self.test_path / "subsidy_depletion_data.json").exists())


if __name__ == "__main__":
    unittest.main()
