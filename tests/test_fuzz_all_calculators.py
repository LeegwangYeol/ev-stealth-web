#!/usr/bin/env python3
"""
tests/test_fuzz_all_calculators.py - Empirical Adversarial Fuzzing Suite
========================================================================
Author: sync11_challenger_backend_tests_w3 (Empirical Challenger)

Empirically fuzzes and stress-tests all analytical calculators across
the backend and math libraries:
1. Subsidy Calculators (tracker/subsidy_tracker.py)
   - calculate_depletion_rate
   - calculate_remaining_units
   - calculate_price_cap_ratio
   - calculate_net_subsidy
   - SubsidyTracker.compute_nationwide_summary
2. Depreciation & Battery Electrochemical Calculators (getDepreciationData.ts)
   - simulateBatteryHealth (fuzzing years, mileage, chemistry, DCFC ratio, temp)
   - calculateSubsidyClawback (fuzzing held months, local/national subsidies, transfer types)
3. Defect & Floating-Point Sanitization Calculators (utils/json_writer.py & tracker/defect_tracker.py)
   - _safe_float (fuzzing NaN, Inf, string literals, extreme types)
   - DefectTracker.query_defects (fuzzing min_severity, categories, adversarial queries)
   - DefectTracker.get_statistics (fuzzing null severity indices, corrupted records)
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import unittest
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
WEB_ROOT = PROJECT_ROOT / "ev-stealth-web" if (PROJECT_ROOT / "ev-stealth-web").exists() else PROJECT_ROOT

from tracker.subsidy_tracker import (
    SubsidyTracker,
    calculate_depletion_rate,
    calculate_remaining_units,
    calculate_price_cap_ratio,
    calculate_net_subsidy,
    get_baseline_dataset,
)
from tracker.defect_tracker import DefectTracker
from utils.json_writer import _safe_float


def _eval_ts_node(script: str, timeout_sec: int = 15) -> Any:
    """Execute TypeScript snippet in ev-stealth-web environment and return parsed JSON."""
    src_dir = WEB_ROOT / "src"
    try:
        proc = subprocess.run(
            ["npx", "--no-install", "tsx", "-e", script],
            cwd=str(WEB_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout.strip())
    except Exception:
        pass

    # Node.js fallback with jiti
    jiti_path = WEB_ROOT / "node_modules" / "jiti"
    pkg_path = WEB_ROOT / "package.json"
    if not jiti_path.exists():
        raise unittest.SkipTest(f"jiti not found at {jiti_path}")

    node_wrapper = f"""
    const Module = require('module');
    const path = require('path');
    const origResolve = Module._resolveFilename;
    Module._resolveFilename = function(request, parent, isMain, options) {{
        if (request.startsWith('./src/')) {{
            request = path.resolve({json.dumps(str(WEB_ROOT))}, request);
        }}
        return origResolve.call(this, request, parent, isMain, options);
    }};
    const createJITI = require({json.dumps(str(jiti_path))});
    const jiti = createJITI({json.dumps(str(pkg_path))});

    {script}
    """
    proc = subprocess.run(
        ["node", "-e", node_wrapper],
        cwd=str(WEB_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Node execution failed (code {proc.returncode}):\n{proc.stderr}")
    return json.loads(proc.stdout.strip())


class TestFuzzSubsidyCalculators(unittest.TestCase):
    """Fuzzes subsidy calculation algorithms against extreme, degenerate, and boundary inputs."""

    def setUp(self) -> None:
        random.seed(42)

    def test_fuzz_calculate_depletion_rate(self) -> None:
        """Fuzz calculate_depletion_rate across 2,000 pseudo-random & boundary inputs."""
        boundary_values = [
            0, 1, -1, 100, 1000, 1000000, 1e9, 1e18,
            float("nan"), float("inf"), float("-inf"), None, "0", "100", "invalid"
        ]

        for applied in boundary_values:
            for announced in boundary_values:
                res = calculate_depletion_rate(applied, announced)  # type: ignore
                self.assertIsInstance(res, float)
                self.assertFalse(math.isnan(res), f"NaN returned for ({applied}, {announced})")
                self.assertFalse(math.isinf(res), f"Inf returned for ({applied}, {announced})")
                self.assertGreaterEqual(res, 0.0, f"Negative depletion rate for ({applied}, {announced})")

        for _ in range(1000):
            rand_applied = random.uniform(-1e6, 1e7)
            rand_announced = random.uniform(-1e6, 1e7)
            res = calculate_depletion_rate(rand_applied, rand_announced)
            self.assertIsInstance(res, float)
            self.assertFalse(math.isnan(res))
            self.assertFalse(math.isinf(res))
            self.assertGreaterEqual(res, 0.0)

    def test_fuzz_calculate_remaining_units(self) -> None:
        """Fuzz calculate_remaining_units across 2,000 pseudo-random & boundary inputs."""
        boundary_values = [
            0, 1, -1, 50, 100, 5000, 1000000, 1e9,
            float("nan"), float("inf"), float("-inf"), None, "50", "abc"
        ]

        for applied in boundary_values:
            for announced in boundary_values:
                res = calculate_remaining_units(applied, announced)  # type: ignore
                self.assertIsInstance(res, int)
                self.assertGreaterEqual(res, 0, f"Negative remaining units for ({applied}, {announced})")

        for _ in range(1000):
            rand_applied = random.uniform(-1000, 100000)
            rand_announced = random.uniform(-1000, 100000)
            res = calculate_remaining_units(rand_applied, rand_announced)
            self.assertIsInstance(res, int)
            self.assertGreaterEqual(res, 0)

    def test_fuzz_calculate_price_cap_ratio(self) -> None:
        """Fuzz calculate_price_cap_ratio across regulatory threshold boundaries and random prices."""
        # Exact statutory transitions
        self.assertEqual(calculate_price_cap_ratio(0), 1.0)
        self.assertEqual(calculate_price_cap_ratio(55_000_000), 1.0)
        self.assertEqual(calculate_price_cap_ratio(55_000_001), 0.5)
        self.assertEqual(calculate_price_cap_ratio(85_000_000), 0.5)
        self.assertEqual(calculate_price_cap_ratio(85_000_001), 0.0)

        # Negative and non-finite numbers safely return bounded floats
        self.assertEqual(calculate_price_cap_ratio(-10_000_000), 1.0)
        self.assertEqual(calculate_price_cap_ratio(float("nan")), 0.0)  # type: ignore
        self.assertEqual(calculate_price_cap_ratio(float("inf")), 0.0)  # type: ignore

        for _ in range(1000):
            rand_price = random.uniform(-1e8, 2e8)
            ratio = calculate_price_cap_ratio(int(rand_price))
            self.assertIn(ratio, (0.0, 0.5, 1.0))

    def test_fuzz_calculate_net_subsidy(self) -> None:
        """Fuzz calculate_net_subsidy verifying division-by-zero safety and non-negative net price."""
        boundary_nationals = [0, 3_000_000, 6_500_000]
        boundary_max_nationals = [0, 6_500_000]
        boundary_locals = [0, 1_500_000, 10_000_000]
        boundary_prices = [0, 30_000_000, 55_000_000, 80_000_000, 120_000_000]

        for mod_nat in boundary_nationals:
            for max_nat in boundary_max_nationals:
                for max_loc in boundary_locals:
                    for p in boundary_prices:
                        res = calculate_net_subsidy(mod_nat, max_nat, max_loc, p)
                        self.assertIn("net_price_krw", res)
                        self.assertIn("total_subsidy_krw", res)
                        self.assertIn("national_subsidy_krw", res)
                        self.assertIn("local_subsidy_krw", res)
                        self.assertGreaterEqual(res["net_price_krw"], 0)
                        self.assertGreaterEqual(res["total_subsidy_krw"], 0)

        # Fuzz 500 randomized combinations
        for _ in range(500):
            mod_nat = random.randint(0, 10_000_000)
            max_nat = random.randint(0, 10_000_000)
            max_loc = random.randint(0, 15_000_000)
            p = random.randint(0, 150_000_000)
            res = calculate_net_subsidy(mod_nat, max_nat, max_loc, p)
            self.assertGreaterEqual(res["net_price_krw"], 0)
            self.assertGreaterEqual(res["total_subsidy_krw"], 0)

    def test_fuzz_compute_nationwide_summary(self) -> None:
        """Fuzz compute_nationwide_summary verifying non-negative disbursed budget billion KRW."""
        tracker = SubsidyTracker()
        baseline = get_baseline_dataset()
        regions = baseline.regions

        # Mutate regional budgets and counts randomly to test aggregation edge cases
        for r in regions:
            cat = r.categories.get("passenger")
            if cat:
                cat.applied_units = random.randint(0, 10000)
                cat.delivered_units = random.randint(0, cat.applied_units)
                cat.total_budget_krw = random.randint(0, 100_000_000_000)
                # Test both normal and over-budget remaining values
                cat.remaining_budget_krw = random.randint(0, cat.total_budget_krw + 10_000_000_000)

        summary = tracker.compute_nationwide_summary(regions)
        self.assertGreaterEqual(summary.disbursed_budget_billion_krw, 0.0)
        self.assertGreaterEqual(summary.nationwide_depletion_rate, 0.0)
        self.assertGreaterEqual(summary.total_remaining_units, 0)


class TestFuzzSafeFloatAndDefectTracker(unittest.TestCase):
    """Fuzzes _safe_float and DefectTracker against adversarial payloads, NaN, Inf, and types."""

    def test_fuzz_safe_float_comprehensive(self) -> None:
        """Fuzz _safe_float with 1,000 random degenerate, extreme, and malformed inputs."""
        nan_inputs = [
            float("nan"), math.nan, "nan", "NaN", "NAN", "  nan  ",
            float("inf"), float("-inf"), math.inf, -math.inf, "inf", "-inf", "Infinity", "-Infinity",
            None, [], {}, object(), b"raw_bytes"
        ]

        for bad in nan_inputs:
            val = _safe_float(bad, default=0.0)
            self.assertEqual(val, 0.0, f"Failed to clamp bad input {bad!r}")
            self.assertFalse(math.isnan(val))
            self.assertFalse(math.isinf(val))

        # Check defensive handling when default itself is NaN or Inf
        self.assertEqual(_safe_float(float("nan"), default=float("nan")), 0.0)
        self.assertEqual(_safe_float(float("inf"), default=float("inf")), 0.0)

        # Fuzz standard random floats and numeric strings
        for _ in range(1000):
            expected = random.uniform(-1e9, 1e9)
            self.assertAlmostEqual(_safe_float(expected), expected, places=5)
            self.assertAlmostEqual(_safe_float(str(expected)), expected, places=5)

    def test_fuzz_defect_tracker_query_defects(self) -> None:
        """Fuzz DefectTracker query_defects with 500 randomized query parameters."""
        tracker = DefectTracker()
        fuzz_categories = ["", "   ", "전기", "배터리", "구동", "UNKNOWN", "🔥⚡", "SELECT * FROM defects", None]
        fuzz_brands = ["", "현대", "기아", "테슬라", "BYD", "UNKNOWN", None]
        fuzz_severities = [-100.0, -1.0, 0.0, 3.5, 7.0, 9.0, 10.0, 100.0, float("nan"), float("inf"), None]
        fuzz_limits = [-50, -1, 0, 1, 10, 100, 1000, 10000]

        for _ in range(500):
            cat = random.choice(fuzz_categories)
            brand = random.choice(fuzz_brands)
            min_sev = random.choice(fuzz_severities)
            lim = random.choice(fuzz_limits)

            results = tracker.query_defects(
                category=cat,  # type: ignore
                vehicle_brand=brand,  # type: ignore
                min_severity=min_sev,  # type: ignore
                limit=lim,
            )
            self.assertIsInstance(results, list)
            for r in results:
                self.assertIsInstance(r, dict)
                self.assertTrue("id" in r or "defect_id" in r)

    def test_fuzz_defect_tracker_corrupted_records_statistics(self) -> None:
        """Verify get_statistics() handles records with null, NaN, or non-float severity indices."""
        import tempfile
        tracker = DefectTracker()
        records = [
            {"id": "D1", "severity": "CRITICAL", "severity_index": None, "vehicle_brand": "현대"},
            {"id": "D2", "severity": "HIGH", "severity_index": "invalid", "vehicle_brand": "기아"},
            {"id": "D3", "severity": "LOW", "severity_index": float("nan"), "vehicle_brand": "테슬라"},
            {"id": "D4", "severity": "CRITICAL", "severity_index": 9.5, "vehicle_brand": "현대"},
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"reports": records}, f)
            tmp_path = f.name

        try:
            stats = tracker.get_statistics(file_path=tmp_path)
            self.assertEqual(stats["total_filtered_defects"], 4)
            self.assertGreaterEqual(stats["critical_defect_count"], 2)  # D1 and D4
            self.assertIn("category_distribution", stats)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


class TestFuzzTypeScriptCalculators(unittest.TestCase):
    """Fuzzes TypeScript client library calculators in getDepreciationData.ts via Node/tsx."""

    def test_fuzz_simulate_battery_health_extremes(self) -> None:
        """Fuzz simulateBatteryHealth with boundary and extreme inputs via TypeScript evaluator."""
        script = """
        import { simulateBatteryHealth } from './src/lib/getDepreciationData';

        const inputs = [
            { years: 0, totalKm: 0 },
            { years: 0, totalKm: 100000 },
            { years: -5, totalKm: -1000 },
            { years: 1, totalKm: 15000, chemistry: 'LFP', dcfcRatio: 0, avgAmbientTempC: 25 },
            { years: 5, totalKm: 150000, chemistry: 'NMC', dcfcRatio: 1.0, avgAmbientTempC: 45 },
            { years: 10, totalKm: 1000000, chemistry: 'UNKNOWN', dcfcRatio: -0.5, avgAmbientTempC: -30 },
            { years: 20, totalKm: 2000000, chemistry: 'LFP', dcfcRatio: 2.0, avgAmbientTempC: 60 }
        ];

        const results = inputs.map(inp => ({
            input: inp,
            out: simulateBatteryHealth(inp as any)
        }));

        console.log(JSON.stringify(results));
        """
        results = _eval_ts_node(script)
        self.assertIsInstance(results, list)

        for item in results:
            out = item["out"]
            inp = item["input"]
            self.assertIn("sohPct", out)
            self.assertIn("calendarLossPct", out)
            self.assertIn("cyclicLossPct", out)
            self.assertIn("totalLossPct", out)
            self.assertIn("grade", out)

            # SOH invariants
            self.assertGreaterEqual(out["sohPct"], 0.0)
            self.assertLessEqual(out["sohPct"], 100.0)
            self.assertGreaterEqual(out["totalLossPct"], 0.0)

            # Zero year check
            if inp.get("years") == 0:
                self.assertEqual(out["calendarLossPct"], 0.0)

    def test_fuzz_subsidy_clawback_extremes(self) -> None:
        """Fuzz calculateSubsidyClawback with boundary held months and subsidies."""
        script = """
        import { calculateSubsidyClawback } from './src/lib/getDepreciationData';

        const testCases = [
            { months: -5, local: 5000000, type: 'intra', nat: 3000000 },
            { months: 0, local: 5000000, type: 'intra', nat: 3000000 },
            { months: 1, local: 4000000, type: 'intra', nat: 3000000 },
            { months: 3, local: 4000000, type: 'intra', nat: 3000000 },
            { months: 6, local: 4000000, type: 'inter', nat: 3000000 },
            { months: 12, local: 4000000, type: 'export', nat: 3000000 },
            { months: 23, local: 4000000, type: 'inter', nat: 3000000 },
            { months: 24, local: 4000000, type: 'intra', nat: 3000000 },
            { months: 36, local: 4000000, type: 'export', nat: 3000000 },
            { months: 12, local: 0, type: 'intra', nat: 0 },
            { months: 12, local: -1000000, type: 'intra', nat: -1000000 },
        ];

        const results = testCases.map(tc => ({
            input: tc,
            out: calculateSubsidyClawback(tc.months, tc.local, tc.type as any, tc.nat)
        }));

        console.log(JSON.stringify(results));
        """
        results = _eval_ts_node(script)
        self.assertIsInstance(results, list)

        for item in results:
            out = item["out"]
            inp = item["input"]
            self.assertIn("totalClawbackKrw", out)
            self.assertIn("effectiveClawbackRate", out)
            self.assertIn("isExempt", out)
            self.assertGreaterEqual(out["totalClawbackKrw"], 0)
            self.assertGreaterEqual(out["effectiveClawbackRate"], 0)
            self.assertLessEqual(out["effectiveClawbackRate"], 1.0)

            # Beyond 24 months, clawback rate is 0
            if inp["months"] >= 24:
                self.assertEqual(out["totalClawbackKrw"], 0)
                self.assertEqual(out["effectiveClawbackRate"], 0)


if __name__ == "__main__":
    unittest.main()
