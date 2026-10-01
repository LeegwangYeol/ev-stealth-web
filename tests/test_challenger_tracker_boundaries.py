#!/usr/bin/env python3
"""tests/test_challenger_tracker_boundaries.py - Empirical Adversarial Boundary & Stress Verification Suite.

Comprehensive stress tests for EV Subsidy Depletion Tracker engine:
1. TestTrackerBoundaryNumbers:
   - Boundary numbers and division-by-zero protection.
   - Over-subscription rates (>100%), remaining quota clamping at 0.
   - Zero announced metrics and empty nationwide summaries.
2. TestPriceCapBoundariesAdversarial:
   - Exact statutory 2026 Korean EV subsidy ratio tiers:
     0, 54,999,999, 55,000,000, 55,000,001, 84,999,999, 85,000,000, 85,000,001, 100,000,000 KRW.
   - Exact financial subsidy amounts and net prices at each boundary point.
   - Monotonic property generator across -10M to 120M KRW.
3. TestCacheValidationAndQuarantineAdversarial:
   - Malformed payloads (truncated JSON, invalid binary UTF-8 bytes, non-dict root types).
   - Partial payloads (missing regions, non-list regions, <17 regions, string item in regions, missing categories).
   - Empty payloads (0-byte file, whitespace-only, empty dict {}).
   - Cache quarantine mechanics (.corrupt_<timestamp>.json) and discard routines.
   - Graceful recovery and baseline fallback under cache corruption.
4. TestAtomicWriterAndConcurrencyAdversarial:
   - Transactional atomic writes (single and multiple targets).
   - Error handling and temp file cleanup on non-serializable inputs.
   - Multi-threaded concurrency stress harness (16 workers) testing race conditions and torn-read prevention.
5. TestCliFlagsAdversarial:
   - CLI flags verification (--help, --dry-run, --verbose, --output, --sync-web).
   - Cache flags (--validate-cache, --no-validate-cache, --quarantine-corrupted, --no-quarantine-corrupted).
   - Rejection of unsupported flags (--force, --unknown-option) with exit code 2.
"""

from __future__ import annotations

import concurrent.futures
from datetime import datetime, timezone
import io
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from typing import Any, Dict, List, Optional, Tuple, Union

# Adaptive root detection
def _find_repo_root() -> Path:
    candidates = [
        Path(__file__).resolve().parent.parent,
        Path(__file__).resolve().parent.parent.parent,
        Path.cwd(),
        Path.cwd().parent,
    ]
    for p in candidates:
        if (p / "ev-stealth-web").is_dir() and (p / "data").is_dir():
            return p
    return Path(__file__).resolve().parent.parent

PROJECT_ROOT = _find_repo_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
WEB_ROOT = PROJECT_ROOT / "ev-stealth-web"
if str(WEB_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_ROOT))

import run_tracker
from tracker.atomic_writer import atomic_write_json, atomic_write_json_multiple
from tracker.subsidy_tracker import (
    calculate_depletion_rate,
    calculate_remaining_units,
    calculate_price_cap_ratio,
    calculate_net_subsidy,
    classify_alert_tier,
    SubsidyTracker,
)
from tracker.subsidy_models import (
    AlertSeverity,
    CategoryMetrics,
    RegionRecord,
    SubsidyPayload,
)

RUN_TRACKER_SCRIPT = PROJECT_ROOT / "run_tracker.py"
if not RUN_TRACKER_SCRIPT.exists() and (WEB_ROOT / "run_tracker.py").exists():
    RUN_TRACKER_SCRIPT = WEB_ROOT / "run_tracker.py"


# ==============================================================================
# 1. BOUNDARY NUMBERS AND DIVISION-BY-ZERO PROTECTION
# ==============================================================================

class TestTrackerBoundaryNumbers(unittest.TestCase):
    """Stress tests on boundary numbers and division-by-zero protection."""

    def test_calculate_depletion_rate_div0(self):
        """0 announced units must yield 0.0% without ZeroDivisionError."""
        self.assertEqual(calculate_depletion_rate(0, 0), 0.0)
        self.assertEqual(calculate_depletion_rate(100, 0), 0.0)
        self.assertEqual(calculate_depletion_rate(100, -10), 0.0)

    def test_calculate_depletion_rate_over_depletion(self):
        """>100% depletion should accurately return percentage without crash."""
        self.assertEqual(calculate_depletion_rate(150, 100), 150.0)
        self.assertEqual(calculate_depletion_rate(250, 100), 250.0)

    def test_calculate_remaining_units_clamping(self):
        """When applied > announced, remaining units must clamp to 0."""
        self.assertEqual(calculate_remaining_units(150, 100), 0)
        self.assertEqual(calculate_remaining_units(100, 100), 0)
        self.assertEqual(calculate_remaining_units(50, 100), 50)
        self.assertEqual(calculate_remaining_units(0, 0), 0)

    def test_calculate_net_subsidy_div0(self):
        """When max_national is 0, local_ratio must guard against ZeroDivisionError."""
        res = calculate_net_subsidy(model_national=6500000, max_national=0, max_local=1500000, msrp=50000000)
        self.assertIsInstance(res, dict)
        self.assertEqual(res["local_subsidy_krw"], 0)
        self.assertEqual(res["national_subsidy_krw"], 6500000)
        self.assertEqual(res["total_subsidy_krw"], 6500000)
        self.assertEqual(res["net_price_krw"], 43500000)

    def test_calculate_net_subsidy_zero_and_negative_msrp(self):
        """MSRP 0 or negative should not produce negative net price."""
        res_0 = calculate_net_subsidy(6500000, 6500000, 1500000, 0)
        self.assertEqual(res_0["net_price_krw"], 0)

        res_neg = calculate_net_subsidy(6500000, 6500000, 1500000, -1000000)
        self.assertEqual(res_neg["net_price_krw"], 0)

    def test_tracker_zero_announced_metrics(self):
        """CategoryMetrics and update_region_metrics with 0 announced units."""
        tracker = SubsidyTracker()
        cat = tracker.calculate_category_metrics(
            announced=0,
            applied=0,
            delivered=0,
            max_local_subsidy=1500000,
        )
        self.assertEqual(cat.depletion_rate, 0.0)
        self.assertEqual(cat.delivery_rate, 0.0)
        self.assertEqual(cat.remaining_units, 0)
        self.assertEqual(cat.status, "HEALTHY")

    def test_tracker_compute_nationwide_summary_empty_and_zero(self):
        """compute_nationwide_summary with 0 total announced units."""
        tracker = SubsidyTracker()
        empty_summary = tracker.compute_nationwide_summary([])
        self.assertEqual(empty_summary.total_announced_units, 0)
        self.assertEqual(empty_summary.nationwide_depletion_rate, 0.0)
        self.assertEqual(empty_summary.total_remaining_units, 0)

        # Region with 0 announced units in all categories
        zero_region = RegionRecord(
            region_id="KR-00",
            iso_code="KR-00",
            name_ko="테스트지역",
            name_en="TestRegion",
            tier="city",
            overall_depletion_rate=0.0,
            overall_status="HEALTHY",
            residency_requirement_days=30,
            supplementary_budget_added=False,
            categories={
                "passenger": CategoryMetrics(0, 0, 0, 0, 0.0, 0.0, "HEALTHY", 0, 0),
                "commercial": CategoryMetrics(0, 0, 0, 0, 0.0, 0.0, "HEALTHY", 0, 0),
                "bus": CategoryMetrics(0, 0, 0, 0, 0.0, 0.0, "HEALTHY", 0, 0),
            },
        )
        summary = tracker.compute_nationwide_summary([zero_region])
        self.assertEqual(summary.total_announced_units, 0)
        self.assertEqual(summary.nationwide_depletion_rate, 0.0)


# ==============================================================================
# 2. PRICE CAP BOUNDARIES ADVERSARIAL TESTS
# ==============================================================================

class TestPriceCapBoundariesAdversarial(unittest.TestCase):
    """Adversarially stress-tests statutory 2026 Korean EV subsidy price cap boundary values.

    Statutory Tiers:
    - Tier 1 (100% subsidy / ratio 1.0): MSRP <= 55,000,000 KRW
    - Tier 2 (50% subsidy / ratio 0.5): 55,000,000 KRW < MSRP <= 85,000,000 KRW
    - Tier 3 (0% subsidy / luxury exemption / ratio 0.0): MSRP > 85,000,000 KRW

    Boundary checkpoints:
    [0, 54,999,999, 55,000,000, 55,000,001, 84,999,999, 85,000,000, 85,000,001, 100,000,000 KRW]
    """

    EXACT_BOUNDARIES_TEST_MATRIX = [
        # (msrp_krw, expected_ratio, tier_label)
        (0, 1.0, "Tier 1: 100% (Zero MSRP boundary)"),
        (54_999_999, 1.0, "Tier 1: 100% (1 KRW below 55M threshold)"),
        (55_000_000, 1.0, "Tier 1: 100% (Exact statutory 55M threshold)"),
        (55_000_001, 0.5, "Tier 2: 50% (1 KRW above 55M threshold)"),
        (84_999_999, 0.5, "Tier 2: 50% (1 KRW below 85M threshold)"),
        (85_000_000, 0.5, "Tier 2: 50% (Exact statutory 85M threshold)"),
        (85_000_001, 0.0, "Tier 3: 0% (1 KRW above 85M threshold)"),
        (100_000_000, 0.0, "Tier 3: 0% (Luxury EV 100M KRW)"),
    ]

    def test_price_cap_ratio_exact_boundaries(self):
        """calculate_price_cap_ratio must strictly return 1.0, 0.5, or 0.0 at all statutory boundary points."""
        for msrp, expected_ratio, label in self.EXACT_BOUNDARIES_TEST_MATRIX:
            with self.subTest(msrp=msrp, expected=expected_ratio, label=label):
                actual_ratio = calculate_price_cap_ratio(msrp)
                self.assertEqual(
                    actual_ratio,
                    expected_ratio,
                    f"Boundary violation at {msrp:,} KRW ({label}): got ratio {actual_ratio}, expected {expected_ratio}",
                )

    def test_net_subsidy_exact_boundaries_financial_integrity(self):
        """calculate_net_subsidy must compute accurate financial amounts without consumer deficits."""
        # Parameters: Seoul baseline (max national 6.5M, max local 1.5M, model national 6.5M)
        model_nat = 6_500_000
        max_nat = 6_500_000
        max_loc = 1_500_000

        # Sub-check at 0 KRW
        res_0 = calculate_net_subsidy(model_nat, max_nat, max_loc, 0)
        self.assertEqual(res_0["national_subsidy_krw"], 6_500_000)
        self.assertEqual(res_0["local_subsidy_krw"], 1_500_000)
        self.assertEqual(res_0["total_subsidy_krw"], 8_000_000)
        self.assertEqual(res_0["net_price_krw"], 0)

        # Sub-check at 54,999,999 KRW (100% tier)
        res_54m = calculate_net_subsidy(model_nat, max_nat, max_loc, 54_999_999)
        self.assertEqual(res_54m["total_subsidy_krw"], 8_000_000)
        self.assertEqual(res_54m["net_price_krw"], 54_999_999 - 8_000_000)

        # Sub-check at 55,000,000 KRW (Exact 100% boundary)
        res_55m = calculate_net_subsidy(model_nat, max_nat, max_loc, 55_000_000)
        self.assertEqual(res_55m["national_subsidy_krw"], 6_500_000)
        self.assertEqual(res_55m["local_subsidy_krw"], 1_500_000)
        self.assertEqual(res_55m["total_subsidy_krw"], 8_000_000)
        self.assertEqual(res_55m["net_price_krw"], 47_000_000)

        # Sub-check at 55,000,001 KRW (Exact 50% boundary entry)
        res_55m_plus = calculate_net_subsidy(model_nat, max_nat, max_loc, 55_000_001)
        self.assertEqual(res_55m_plus["national_subsidy_krw"], 3_250_000)
        self.assertEqual(res_55m_plus["local_subsidy_krw"], 750_000)
        self.assertEqual(res_55m_plus["total_subsidy_krw"], 4_000_000)
        self.assertEqual(res_55m_plus["net_price_krw"], 55_000_001 - 4_000_000)

        # Sub-check at 84,999,999 KRW (50% tier upper boundary - 1)
        res_84m = calculate_net_subsidy(model_nat, max_nat, max_loc, 84_999_999)
        self.assertEqual(res_84m["total_subsidy_krw"], 4_000_000)
        self.assertEqual(res_84m["net_price_krw"], 84_999_999 - 4_000_000)

        # Sub-check at 85,000,000 KRW (Exact 50% boundary)
        res_85m = calculate_net_subsidy(model_nat, max_nat, max_loc, 85_000_000)
        self.assertEqual(res_85m["national_subsidy_krw"], 3_250_000)
        self.assertEqual(res_85m["local_subsidy_krw"], 750_000)
        self.assertEqual(res_85m["total_subsidy_krw"], 4_000_000)
        self.assertEqual(res_85m["net_price_krw"], 81_000_000)

        # Sub-check at 85,000,001 KRW (Exact luxury exemption entry)
        res_85m_plus = calculate_net_subsidy(model_nat, max_nat, max_loc, 85_000_001)
        self.assertEqual(res_85m_plus["national_subsidy_krw"], 0)
        self.assertEqual(res_85m_plus["local_subsidy_krw"], 0)
        self.assertEqual(res_85m_plus["total_subsidy_krw"], 0)
        self.assertEqual(res_85m_plus["net_price_krw"], 85_000_001)

        # Sub-check at 100,000,000 KRW (Luxury EV)
        res_100m = calculate_net_subsidy(model_nat, max_nat, max_loc, 100_000_000)
        self.assertEqual(res_100m["national_subsidy_krw"], 0)
        self.assertEqual(res_100m["local_subsidy_krw"], 0)
        self.assertEqual(res_100m["total_subsidy_krw"], 0)
        self.assertEqual(res_100m["net_price_krw"], 100_000_000)

    def test_property_generator_price_cap_monotonicity(self):
        """Generator property: ratio must be monotonically non-increasing and net_price >= 0 across wide range."""
        previous_ratio = 1.0
        # Sample 260 distinct price points from -10M to 120M in steps of 500k KRW
        for price in range(-10_000_000, 120_000_001, 500_000):
            ratio = calculate_price_cap_ratio(price)
            self.assertIn(ratio, (1.0, 0.5, 0.0))
            if price <= 55_000_000:
                self.assertEqual(ratio, 1.0)
            elif price <= 85_000_000:
                self.assertEqual(ratio, 0.5)
            else:
                self.assertEqual(ratio, 0.0)

            # Monotonic non-increasing property
            self.assertLessEqual(
                ratio,
                previous_ratio,
                f"Monotonicity inversion at price {price:,} KRW: ratio {ratio} > previous {previous_ratio}",
            )
            previous_ratio = ratio

            # Net subsidy non-negative price guarantee
            net_res = calculate_net_subsidy(6_500_000, 6_500_000, 1_500_000, price)
            self.assertGreaterEqual(net_res["net_price_krw"], 0)


# ==============================================================================
# 3. CACHE VALIDATION AND QUARANTINE LOGIC ADVERSARIAL TESTS
# ==============================================================================

class TestCacheValidationAndQuarantineAdversarial(unittest.TestCase):
    """Adversarially stress-tests cache validation and quarantine resilience against corrupted payloads."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_malformed_truncated_json_quarantine(self):
        """Truncated JSON must be caught, quarantined, and discarded from memory gracefully."""
        bad_file = self.cache_dir / "truncated.json"
        bad_file.write_text('{"metadata": {"version": "1.0.0"', encoding="utf-8")

        tracker = SubsidyTracker(cache_fallback_path=bad_file, validate_cache=True, quarantine_corrupted=True)
        payload = tracker.load_cached_payload(bad_file, validate=True, quarantine=True)

        self.assertIsNone(payload, "Truncated JSON must return None payload")
        self.assertFalse(bad_file.exists(), "Original corrupted file must be renamed/moved")
        quarantined = list(self.cache_dir.glob("truncated.corrupt_*.json"))
        self.assertEqual(len(quarantined), 1, "Expected exactly 1 quarantined file")
        self.assertEqual(quarantined[0].read_text(encoding="utf-8"), '{"metadata": {"version": "1.0.0"')

    def test_malformed_binary_garbage_quarantine(self):
        """Invalid non-UTF-8 binary bytes must trigger graceful quarantine."""
        bad_file = self.cache_dir / "binary_garbage.json"
        bad_file.write_bytes(b"\x00\xff\xfe\x12\x34\xaa\xbb\xcc")

        tracker = SubsidyTracker(cache_fallback_path=bad_file, validate_cache=True, quarantine_corrupted=True)
        payload = tracker.load_cached_payload(bad_file, validate=True, quarantine=True)

        self.assertIsNone(payload)
        self.assertFalse(bad_file.exists())
        quarantined = list(self.cache_dir.glob("binary_garbage.corrupt_*.json"))
        self.assertEqual(len(quarantined), 1)

    def test_malformed_non_dict_root_payloads(self):
        """Non-dict JSON payloads (list, string, integer, null) must be quarantined."""
        non_dict_cases = [
            ("json_array.json", "[1, 2, 3, 4]"),
            ("json_string.json", '"plain text string"'),
            ("json_int.json", "42"),
            ("json_null.json", "null"),
        ]
        tracker = SubsidyTracker(validate_cache=True, quarantine_corrupted=True)
        for fname, content in non_dict_cases:
            with self.subTest(file=fname):
                bad_file = self.cache_dir / fname
                bad_file.write_text(content, encoding="utf-8")

                payload = tracker.load_cached_payload(bad_file, validate=True, quarantine=True)
                self.assertIsNone(payload)
                self.assertFalse(bad_file.exists())
                stem = bad_file.stem
                quarantined = list(self.cache_dir.glob(f"{stem}.corrupt_*.json"))
                self.assertEqual(len(quarantined), 1)

    def test_partial_payload_fewer_than_17_regions(self):
        """Payload with fewer than 17 regions must fail schema validation and be quarantined."""
        bad_file = self.cache_dir / "partial_regions.json"
        partial_data = {
            "metadata": {"version": "1.0.0"},
            "regions": [
                {
                    "region_id": "KR-11",
                    "iso_code": "KR-11",
                    "name_ko": "서울",
                    "name_en": "Seoul",
                    "tier": "special_city",
                    "overall_depletion_rate": 50.0,
                    "overall_status": "HEALTHY",
                    "residency_requirement_days": 30,
                    "supplementary_budget_added": False,
                    "categories": {},
                }
            ],
        }
        bad_file.write_text(json.dumps(partial_data), encoding="utf-8")

        tracker = SubsidyTracker(cache_fallback_path=bad_file, validate_cache=True, quarantine_corrupted=True)
        payload = tracker.load_cached_payload(bad_file, validate=True, quarantine=True)

        self.assertIsNone(payload)
        self.assertFalse(bad_file.exists())
        quarantined = list(self.cache_dir.glob("partial_regions.corrupt_*.json"))
        self.assertEqual(len(quarantined), 1)

    def test_partial_payload_corrupted_region_items(self):
        """Payload where regions contain non-dict items (strings or missing categories) must be quarantined."""
        bad_file = self.cache_dir / "corrupted_items.json"
        # 17 items, but strings instead of objects
        corrupt_data = {
            "metadata": {"version": "1.0.0"},
            "regions": ["corrupted_region_record_string"] * 17,
        }
        bad_file.write_text(json.dumps(corrupt_data), encoding="utf-8")

        tracker = SubsidyTracker(cache_fallback_path=bad_file, validate_cache=True, quarantine_corrupted=True)
        payload = tracker.load_cached_payload(bad_file, validate=True, quarantine=True)

        self.assertIsNone(payload)
        self.assertFalse(bad_file.exists())
        quarantined = list(self.cache_dir.glob("corrupted_items.corrupt_*.json"))
        self.assertEqual(len(quarantined), 1)

    def test_empty_payload_quarantine(self):
        """0-byte empty file, whitespace-only, and empty dict {} must be rejected and quarantined."""
        empty_cases = [
            ("empty_zero_byte.json", ""),
            ("whitespace_only.json", "   \n\t  \n"),
            ("empty_dict.json", "{}"),
        ]
        tracker = SubsidyTracker(validate_cache=True, quarantine_corrupted=True)
        for fname, content in empty_cases:
            with self.subTest(file=fname):
                bad_file = self.cache_dir / fname
                bad_file.write_text(content, encoding="utf-8")

                payload = tracker.load_cached_payload(bad_file, validate=True, quarantine=True)
                self.assertIsNone(payload)
                self.assertFalse(bad_file.exists())
                stem = bad_file.stem
                quarantined = list(self.cache_dir.glob(f"{stem}.corrupt_*.json"))
                self.assertEqual(len(quarantined), 1)

    def test_quarantine_flag_false_leaves_corrupted_file_untouched(self):
        """When quarantine=False, corrupted cache file is discarded in memory but NOT renamed on disk."""
        bad_file = self.cache_dir / "no_quarantine.json"
        bad_file.write_text("invalid json content", encoding="utf-8")

        tracker = SubsidyTracker(cache_fallback_path=bad_file, validate_cache=True, quarantine_corrupted=False)
        payload = tracker.load_cached_payload(bad_file, validate=True, quarantine=False)

        self.assertIsNone(payload)
        self.assertTrue(bad_file.exists(), "File must still exist when quarantine is False")
        self.assertEqual(bad_file.read_text(encoding="utf-8"), "invalid json content")
        quarantined = list(self.cache_dir.glob("no_quarantine.corrupt_*.json"))
        self.assertEqual(len(quarantined), 0)

    def test_discard_corrupted_cache_routine(self):
        """discard_corrupted_cache must unlink existing files and return True, or False if non-existent."""
        target = self.cache_dir / "to_discard.json"
        target.write_text("corrupt", encoding="utf-8")

        tracker = SubsidyTracker()
        self.assertTrue(tracker.discard_corrupted_cache(target))
        self.assertFalse(target.exists())

        # Discarding already deleted file should return False
        self.assertFalse(tracker.discard_corrupted_cache(target))

    def test_execute_tracking_cycle_end_to_end_corruption_recovery(self):
        """execute_tracking_cycle must recover cleanly to 17-region baseline when cache is corrupted."""
        bad_cache = self.cache_dir / "ev_subsidy_data.json"
        bad_cache.write_text('{"regions": ["bad_record"]}', encoding="utf-8")

        tracker = SubsidyTracker(
            cache_fallback_path=bad_cache,
            validate_cache=True,
            quarantine_corrupted=True,
        )
        payload, fallback_used = tracker.execute_tracking_cycle(mock_network_failure=True)

        self.assertTrue(fallback_used, "Fallback must be marked as used")
        self.assertIsNotNone(payload)
        self.assertEqual(len(payload.regions), 17, "Baseline must contain exactly 17 regions")
        self.assertEqual(payload.nationwide_summary.total_announced_units, 148510)
        self.assertGreater(payload.nationwide_summary.disbursed_budget_billion_krw, 0.0)
        self.assertFalse(bad_cache.exists(), "Corrupted cache must be quarantined")
        quarantined = list(self.cache_dir.glob("ev_subsidy_data.corrupt_*.json"))
        self.assertEqual(len(quarantined), 1)


# ==============================================================================
# 4. ATOMIC FILE OPERATIONS AND CONCURRENCY SAFETY TESTS
# ==============================================================================

class TestAtomicWriterAndConcurrencyAdversarial(unittest.TestCase):
    """Stress tests atomic writer routines and verifies race condition resilience."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.target_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_atomic_write_json_single_and_multiple(self):
        """atomic_write_json and atomic_write_json_multiple write valid JSON cleanly."""
        data = {"status": "ok", "count": 1234, "items": ["a", "b", "c"]}
        dest1 = self.target_dir / "dest1.json"
        dest2 = self.target_dir / "sub" / "dest2.json"

        # Single write
        out1 = atomic_write_json(data, dest1)
        self.assertEqual(out1, dest1.resolve())
        self.assertTrue(dest1.exists())
        with open(dest1, "r", encoding="utf-8") as f:
            self.assertEqual(json.load(f), data)

        # Multiple writes
        dest3 = self.target_dir / "dest3.json"
        written = atomic_write_json_multiple(data, [dest2, dest3])
        self.assertEqual(len(written), 2)
        for d in (dest2, dest3):
            self.assertTrue(d.exists())
            with open(d, "r", encoding="utf-8") as f:
                self.assertEqual(json.load(f), data)

    def test_atomic_write_failure_cleans_up_temp_file(self):
        """Non-serializable object must fail atomic write, clean up temp file, and preserve target."""
        target = self.target_dir / "stable.json"
        target.write_text('{"initial": "clean"}', encoding="utf-8")

        non_serializable_object = {"invalid": lambda x: x}

        with self.assertRaises(TypeError):
            atomic_write_json(non_serializable_object, target)

        # Original target file must remain intact
        self.assertTrue(target.exists())
        self.assertEqual(target.read_text(encoding="utf-8"), '{"initial": "clean"}')

        # No temporary files should be leaked
        tmp_files = list(self.target_dir.glob(".tmp_subsidy_*"))
        self.assertEqual(len(tmp_files), 0, f"Leaked temporary files detected: {tmp_files}")

    def test_high_concurrency_stress_harness(self):
        """16 concurrent threads repeatedly writing to the same file must never produce torn reads or corrupt JSON."""
        target_file = self.target_dir / "concurrent_subsidy.json"
        num_threads = 16
        iterations_per_thread = 10

        errors: List[str] = []

        def worker(thread_id: int):
            for i in range(iterations_per_thread):
                payload = {
                    "thread_id": thread_id,
                    "iteration": i,
                    "payload_data": list(range(100)),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                try:
                    atomic_write_json(payload, target_file)
                except Exception as exc:
                    errors.append(f"Writer error in thread {thread_id}, iteration {i}: {exc}")

        def reader(stop_event):
            while not stop_event.is_set():
                if target_file.exists():
                    try:
                        with open(target_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        if not isinstance(data, dict) or "thread_id" not in data:
                            errors.append(f"Corrupt read data structure: {data}")
                    except json.JSONDecodeError as exc:
                        errors.append(f"Torn read / JSONDecodeError detected during concurrent writes: {exc}")
                    except FileNotFoundError:
                        pass

        import threading
        stop_reader = threading.Event()
        reader_thread = threading.Thread(target=reader, args=(stop_reader,))
        reader_thread.start()

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, tid) for tid in range(num_threads)]
            for future in concurrent.futures.as_completed(futures):
                future.result()

        stop_reader.set()
        reader_thread.join(timeout=5)

        self.assertEqual(len(errors), 0, f"Concurrency errors occurred: {errors[:5]}")
        self.assertTrue(target_file.exists())
        with open(target_file, "r", encoding="utf-8") as f:
            final_data = json.load(f)
        self.assertIn("thread_id", final_data)

        # Zero leftover temporary files
        tmp_files = list(self.target_dir.glob(".tmp_subsidy_*"))
        self.assertEqual(len(tmp_files), 0, f"Leftover temp files: {tmp_files}")


# ==============================================================================
# 5. CLI FLAGS ADVERSARIAL TESTS
# ==============================================================================

class TestCliFlagsAdversarial(unittest.TestCase):
    """Adversarially tests run_tracker.py CLI parameters and error code contracts."""

    def test_cli_help_flag(self):
        """--help must exit with 0 and display standard argument documentation."""
        res = subprocess.run(
            [sys.executable, str(RUN_TRACKER_SCRIPT), "--help"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("--output", res.stdout)
        self.assertIn("--sync-web", res.stdout)
        self.assertIn("--verbose", res.stdout)
        self.assertIn("--dry-run", res.stdout)
        self.assertIn("--validate-cache", res.stdout)
        self.assertIn("--quarantine-corrupted", res.stdout)

    def test_cli_dry_run_flag(self):
        """--dry-run must exit with 0 and emit executive summary without modifying default files."""
        res = subprocess.run(
            [sys.executable, str(RUN_TRACKER_SCRIPT), "--dry-run", "--mock-network"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("[대한민국 2026 전국 지자체 전기차 보조금 실시간 소진율 모니터링]", res.stdout)

    def test_cli_verbose_debug_logging(self):
        """--verbose must emit DEBUG logs showing configuration parameters."""
        res = subprocess.run(
            [sys.executable, str(RUN_TRACKER_SCRIPT), "--dry-run", "--mock-network", "--verbose"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(res.returncode, 0)
        combined = res.stdout + res.stderr
        self.assertIn("Configuration: dry_run=True", combined)

    def test_cli_custom_output_redirection(self):
        """--output <path> must write the JSON dataset to the designated path."""
        with tempfile.TemporaryDirectory() as td:
            custom_out = Path(td) / "custom_subsidy.json"
            res = subprocess.run(
                [
                    sys.executable,
                    str(RUN_TRACKER_SCRIPT),
                    "--output",
                    str(custom_out),
                    "--mock-network",
                ],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(res.returncode, 0, f"Error: {res.stderr}")
            self.assertTrue(custom_out.exists())
            with open(custom_out, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(len(data["regions"]), 17)

    def test_cli_quarantine_corrupted_flags(self):
        """Verify --quarantine-corrupted and --no-quarantine-corrupted CLI flags."""
        with tempfile.TemporaryDirectory() as td:
            corrupt_file = Path(td) / "bad.json"
            corrupt_file.write_text("invalid json", encoding="utf-8")

            # 1. With --quarantine-corrupted (default)
            res = subprocess.run(
                [
                    sys.executable,
                    str(RUN_TRACKER_SCRIPT),
                    "--output",
                    str(corrupt_file),
                    "--mock-network",
                    "--quarantine-corrupted",
                    "--dry-run",
                ],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(res.returncode, 0)
            self.assertFalse(corrupt_file.exists())
            quarantined = list(Path(td).glob("*.corrupt_*"))
            self.assertEqual(len(quarantined), 1)

        with tempfile.TemporaryDirectory() as td:
            corrupt_file = Path(td) / "bad.json"
            corrupt_file.write_text("invalid json", encoding="utf-8")

            # 2. With --no-quarantine-corrupted
            res = subprocess.run(
                [
                    sys.executable,
                    str(RUN_TRACKER_SCRIPT),
                    "--output",
                    str(corrupt_file),
                    "--mock-network",
                    "--no-quarantine-corrupted",
                    "--dry-run",
                ],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(res.returncode, 0)
            self.assertTrue(corrupt_file.exists(), "Original file must be kept when quarantine is disabled")
            quarantined = list(Path(td).glob("*.corrupt_*"))
            self.assertEqual(len(quarantined), 0)

    def test_cli_unrecognized_flags_exit_code_2(self):
        """Unsupported flags (e.g. --force, --arbitrary-arg) must trigger exit code 2."""
        for bad_flag in ("--force", "--unsupported-option", "--dryrun"):
            with self.subTest(flag=bad_flag):
                res = subprocess.run(
                    [sys.executable, str(RUN_TRACKER_SCRIPT), bad_flag],
                    cwd=str(PROJECT_ROOT),
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(
                    res.returncode,
                    2,
                    f"Expected exit code 2 for unsupported flag {bad_flag}, got {res.returncode}",
                )
                self.assertIn("unrecognized arguments", res.stderr)


if __name__ == "__main__":
    unittest.main()
