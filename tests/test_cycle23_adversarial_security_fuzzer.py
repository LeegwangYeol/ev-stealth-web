#!/usr/bin/env python3
"""tests/test_cycle23_adversarial_security_fuzzer.py
====================================================
Cycle 23 Adversarial Security Fuzzer
Author: Adversarial Security Fuzzer (Swarm Wave 3, Cycle 23)

Conducts exhaustive adversarial fuzz testing across:
1. tracker/subsidy_tracker.py
   - calculate_depletion_rate
   - calculate_remaining_units
   - calculate_price_cap_ratio
   - calculate_net_subsidy
   - _safe_int_metric & _metric_val
   - SubsidyTracker.calculate_category_metrics
   - SubsidyTracker.update_region_metrics
   - SubsidyTracker.compute_nationwide_summary
   - SubsidyTracker.load_cached_payload (corrupt JSON, null bytes, truncated bytes)
   - robust_decode (malformed charsets & binary injections)
2. ev-stealth-web/src/lib (via TypeScript/ESM fuzzer integration)
   - depreciationCalculations.ts
   - reliabilityCalculations.ts
   - subsidyCalculations.ts

Verifies boundary conditions:
- Negative numbers (-1, -100, -1e9, -Infinity)
- NaN and Infs
- Extremely large numbers exceeding 10 Billion KRW (10_000_000_001, 100B, 1e18)
- SQL/XSS injections (' OR '1'='1, <script>alert(1)</script>)
- Unicode null bytes (\\x00, \\u0000)
- Corrupt JSON payloads
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tracker.subsidy_tracker import (
    SubsidyTracker,
    calculate_depletion_rate,
    calculate_remaining_units,
    calculate_price_cap_ratio,
    calculate_net_subsidy,
    _safe_int_metric,
    _metric_val,
    robust_decode,
    classify_alert_tier,
)


class TestCycle23AdversarialSecurityFuzzer(unittest.TestCase):
    """Exhaustive adversarial fuzzing and boundary security verification."""

    ADVERSARIAL_NUMBERS = [
        float("-inf"),
        -1e18,
        -10_000_000_000,
        -50_000_000,
        -15_000,
        -100,
        -1,
        -0.00001,
        0,
        0.00001,
        1,
        15_000,
        55_000_000,
        85_000_000,
        85_000_001,
        100_000_000,
        10_000_000_000,
        10_000_000_001,  # > 10 Billion KRW boundary
        50_000_000_000,
        100_000_000_000,
        1e15,
        float("inf"),
        float("nan"),
    ]

    ADVERSARIAL_STRINGS = [
        "",
        "   ",
        "\t\r\n",
        "\x00",
        "null\x00byte",
        "\x00\x00\x00",
        "admin\x00",
        "' OR '1'='1",
        "'; DROP TABLE subsidies; --",
        "admin' --",
        "UNION SELECT null, username, password FROM users --",
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert(1)>",
        "javascript:void(0)",
        '"><svg/onload=alert(1)>',
        "%s%s%s%s%s%n",
        "{{7*7}}",
        "${7*7}",
        "\uffff",
        "\ufeff",
        "\u200b",
        "🚗⚡️🔋💰",
        "A" * 5000,
    ]

    def test_01_calculate_depletion_rate_boundary_and_fuzz(self) -> None:
        """Fuzz calculate_depletion_rate across negative, NaN, Inf, and malicious types."""
        for applied in self.ADVERSARIAL_NUMBERS:
            for announced in self.ADVERSARIAL_NUMBERS:
                rate = calculate_depletion_rate(applied, announced)
                self.assertFalse(math.isnan(rate), f"rate is NaN for ({applied}, {announced})")
                self.assertFalse(math.isinf(rate), f"rate is Inf for ({applied}, {announced})")
                self.assertGreaterEqual(rate, 0.0, f"rate is negative for ({applied}, {announced})")

        # Zero announced must never crash with ZeroDivisionError
        self.assertEqual(calculate_depletion_rate(100, 0), 0.0)
        self.assertEqual(calculate_depletion_rate(0, 0), 0.0)

        # Fuzz non-numeric and injection strings
        for s in self.ADVERSARIAL_STRINGS:
            self.assertEqual(calculate_depletion_rate(s, 100), 0.0)
            self.assertEqual(calculate_depletion_rate(100, s), 0.0)

    def test_02_calculate_remaining_units_clamping_and_extremes(self) -> None:
        """Fuzz calculate_remaining_units with over-subscription, negatives, and huge numbers."""
        for applied in self.ADVERSARIAL_NUMBERS:
            for announced in self.ADVERSARIAL_NUMBERS:
                rem = calculate_remaining_units(applied, announced)
                self.assertIsInstance(rem, int)
                self.assertGreaterEqual(rem, 0, f"remaining units negative for ({applied}, {announced})")

        # Over-subscription clamping
        self.assertEqual(calculate_remaining_units(2000, 1000), 0)
        self.assertEqual(calculate_remaining_units(10_000_000_001, 1000), 0)

        # Malicious strings & nulls
        for s in self.ADVERSARIAL_STRINGS:
            self.assertEqual(calculate_remaining_units(s, 1000), 0)
            self.assertEqual(calculate_remaining_units(1000, s), 0)

    def test_03_calculate_price_cap_ratio_statutory_bounds(self) -> None:
        """Verify statutory price cap tiers (<=55M: 1.0, 55M-85M: 0.5, >85M: 0.0) and edge cases."""
        # 100% eligibility
        self.assertEqual(calculate_price_cap_ratio(1), 1.0)
        self.assertEqual(calculate_price_cap_ratio(54_999_999), 1.0)
        self.assertEqual(calculate_price_cap_ratio(55_000_000), 1.0)

        # 50% eligibility
        self.assertEqual(calculate_price_cap_ratio(55_000_001), 0.5)
        self.assertEqual(calculate_price_cap_ratio(70_000_000), 0.5)
        self.assertEqual(calculate_price_cap_ratio(85_000_000), 0.5)

        # 0% luxury exclusion
        self.assertEqual(calculate_price_cap_ratio(85_000_001), 0.0)
        self.assertEqual(calculate_price_cap_ratio(100_000_000), 0.0)
        self.assertEqual(calculate_price_cap_ratio(10_000_000_001), 0.0)  # > 10 Billion KRW

        # Non-positive / invalid
        self.assertEqual(calculate_price_cap_ratio(0), 0.0)
        self.assertEqual(calculate_price_cap_ratio(-50_000_000), 0.0)
        self.assertEqual(calculate_price_cap_ratio(float("nan")), 0.0)
        self.assertEqual(calculate_price_cap_ratio(float("inf")), 0.0)

        for s in self.ADVERSARIAL_STRINGS:
            self.assertEqual(calculate_price_cap_ratio(s), 0.0)

    def test_04_calculate_net_subsidy_extremes_and_injections(self) -> None:
        """Fuzz calculate_net_subsidy with huge prices exceeding 10 Billion KRW and boundary inputs."""
        for msrp in [
            -1000, 0, 50_000_000, 70_000_000, 100_000_000,
            10_000_000_001, 100_000_000_000, float("nan"), float("inf"), None
        ]:
            for nat in [-500, 0, 6_500_000, 10_000_000_001, None]:
                for max_loc in [-500, 0, 1_500_000, 10_000_000_001, None]:
                    res = calculate_net_subsidy(nat, 6_500_000, max_loc, msrp)
                    self.assertIsInstance(res, dict)
                    self.assertGreaterEqual(res["net_price_krw"], 0)
                    self.assertGreaterEqual(res["total_subsidy_krw"], 0)
                    self.assertFalse(math.isnan(res["price_cap_ratio"]))

        # Check luxury exclusion for 10 Billion KRW vehicle
        super_luxury = calculate_net_subsidy(6_500_000, 6_500_000, 2_000_000, 10_000_000_001)
        self.assertEqual(super_luxury["total_subsidy_krw"], 0)
        self.assertEqual(super_luxury["net_price_krw"], 10_000_000_001)
        self.assertEqual(super_luxury["price_cap_ratio"], 0.0)

    def test_05_safe_metric_helpers(self) -> None:
        """Test _safe_int_metric and _metric_val on corrupt and adversarial objects."""
        for n in self.ADVERSARIAL_NUMBERS:
            val = _safe_int_metric(n, default=42)
            self.assertIsInstance(val, int)

        for s in self.ADVERSARIAL_STRINGS:
            self.assertEqual(_safe_int_metric(s, default=0), 0)

        # Corrupt and nested structures in _metric_val
        self.assertEqual(_metric_val(None, "key", 99), 99)
        self.assertEqual(_metric_val({}, "key", 99), 99)
        self.assertEqual(_metric_val({"key": 123}, "key", 99), 123)
        self.assertEqual(_metric_val("not_dict_or_obj", "key", 99), 99)

    def test_06_tracker_region_metrics_corrupt_resilience(self) -> None:
        """Test SubsidyTracker.update_region_metrics on null, non-dict, and malformed inputs."""
        tracker = SubsidyTracker()

        corrupt_inputs = [
            None,
            {},
            "string_payload",
            12345,
            {"categories": None},
            {"categories": {"passenger": None}},
            {"categories": {"passenger": {"announced_units": -10, "applied_units": float("nan")}}},
            {"municipalities": [None, "invalid", {"announced_units": float("inf")}]},
        ]

        for bad in corrupt_inputs:
            try:
                res = tracker.update_region_metrics(bad)
                self.assertIsNotNone(res)
            except Exception as exc:
                self.fail(f"update_region_metrics crashed unexpectedly on {bad}: {exc}")

    def test_07_compute_nationwide_summary_adversarial_matrix(self) -> None:
        """Test compute_nationwide_summary with sparse, corrupted, and injected region lists."""
        tracker = SubsidyTracker()

        corrupt_regions = [
            None,
            {},
            "invalid_region",
            42,
            {"categories": None},
            {
                "categories": {
                    "passenger": {
                        "announced_units": 1000,
                        "applied_units": 850,
                        "delivered_units": 500,
                        "total_budget_krw": 10_000_000_000,
                    },
                    "commercial": {
                        "announced_units": -50,
                        "applied_units": float("nan"),
                    },
                }
            },
            {
                "categories": {
                    "passenger": {
                        "announced_units": 10_000_000_001,  # extreme volume
                        "applied_units": 5_000_000_000,
                        "total_budget_krw": -1,
                    }
                }
            },
        ]

        summary = tracker.compute_nationwide_summary(corrupt_regions)
        self.assertIsNotNone(summary)
        self.assertGreaterEqual(summary.total_announced_units, 0)
        self.assertGreaterEqual(summary.total_applied_units, 0)
        self.assertFalse(math.isnan(summary.nationwide_depletion_rate))
        self.assertFalse(math.isinf(summary.nationwide_depletion_rate))

    def test_08_load_cached_payload_corrupted_json_and_byte_injections(self) -> None:
        """Test load_cached_payload resilience against truncated JSON, raw null bytes, and non-dicts."""
        tracker = SubsidyTracker(quarantine_corrupted=False)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # 1. Truncated JSON
            p_trunc = tmp_path / "trunc.json"
            p_trunc.write_text('{"regions": [{"region_id": "seoul"', encoding="utf-8")
            res_trunc = tracker.load_cached_payload(p_trunc)
            self.assertIsNone(res_trunc, "Truncated JSON must be discarded and return None")

            # 2. Binary null bytes and invalid UTF-8
            p_nulls = tmp_path / "nulls.json"
            p_nulls.write_bytes(b"\x00\xff\xfe\x00\x00" + b'{"test": 1}')
            res_nulls = tracker.load_cached_payload(p_nulls)
            self.assertIsNone(res_nulls, "Binary null bytes must be discarded and return None")

            # 3. Array instead of dict
            p_array = tmp_path / "array.json"
            p_array.write_text("[1, 2, 3]", encoding="utf-8")
            res_array = tracker.load_cached_payload(p_array)
            self.assertIsNone(res_array, "Array JSON must return None")

            # 4. Empty file
            p_empty = tmp_path / "empty.json"
            p_empty.write_text("", encoding="utf-8")
            res_empty = tracker.load_cached_payload(p_empty)
            self.assertIsNone(res_empty, "Empty file must return None")

    def test_09_robust_decode_adversarial_bytes(self) -> None:
        """Test robust_decode with malformed charsets, null bytes, and binary blobs."""
        # Empty
        self.assertEqual(robust_decode(b""), "")

        # Valid UTF-8 with null byte
        self.assertEqual(robust_decode(b"hello\x00world"), "hello\x00world")

        # Invalid start bytes
        res = robust_decode(b"\xff\xfe\xfa\xfb")
        self.assertIsInstance(res, str)

        # CP949 / EUC-KR Korean bytes
        korean_cp949 = "서울특별시 전기차 보조금".encode("cp949")
        self.assertEqual(robust_decode(korean_cp949), "서울특별시 전기차 보조금")

    def test_10_typescript_library_adversarial_security_fuzzer(self) -> None:
        """Execute and verify the full TypeScript lib fuzzer (tests/adversarial_security_fuzz_cycle23.mjs)."""
        fuzz_script = PROJECT_ROOT / "tests" / "adversarial_security_fuzz_cycle23.mjs"
        self.assertTrue(fuzz_script.exists(), f"Fuzz script missing at {fuzz_script}")

        proc = subprocess.run(
            ["npx", "tsx", str(fuzz_script)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=45,
        )

        sys.stdout.write(proc.stdout)
        if proc.stderr:
            sys.stderr.write(proc.stderr)

        self.assertEqual(
            proc.returncode,
            0,
            f"TypeScript adversarial security fuzzer failed (exit code {proc.returncode})"
        )
        self.assertIn("Total Assertions Evaluated:", proc.stdout)
        self.assertIn("Crashes / Exceptions:       0", proc.stdout)
        self.assertIn("NaN Value Leaks:            0", proc.stdout)


if __name__ == "__main__":
    unittest.main()
