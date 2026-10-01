"""
tests/test_adversarial_depreciation_engine.py - Adversarial & Stress Testing Suite
for EV Depreciation, Electrochemical Battery Health, Subsidy Clawback, and TCO.

Empirically validates:
1. Extreme & Boundary Inputs:
   - 0 km vs 1,000,000 km annual mileage (and up to 5,000,000 km cumulative).
   - 0% DC fast charging vs 100% DC fast charging.
   - Extreme cold weather (-30°C) vs extreme hot desert conditions (+45°C).
   - Zero subsidies (MSRP = net purchase price) vs maximum local+national subsidies.
   - Fractional ownership durations (0.1, 0.5, 2.5, 5.0, 5.5 years).
   - Early resale clawback boundaries (1d, 89d, 90d, 364d, 729d, 730d) across intra, inter, and export.
2. Numerical Stability & Anomalies:
   - Detection of NaN, Infinity, negative residual values, and curve inversions.
   - Empirical verification of hardened invariants for edge-case bugs:
     * LFP battery chemistry monotonic ramp preventing Year 3.00 curve inversion.
     * simulateBatteryHealth non-negative mileage clamping preventing negative km NaN.
     * calculateTcoComparison safe years rounding ensuring fractional year handling.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import shutil
import subprocess
import unittest
from typing import Any, Dict, List, Optional


def find_ts_engine_path() -> Path:
    current_file = Path(__file__).resolve()
    candidates = [
        current_file.parent.parent / "src" / "lib" / "getDepreciationData.ts",
        current_file.parent.parent / "ev-stealth-web" / "src" / "lib" / "getDepreciationData.ts",
        current_file.parent.parent.parent / "ev-stealth-web" / "src" / "lib" / "getDepreciationData.ts",
        Path.cwd() / "src" / "lib" / "getDepreciationData.ts",
        Path.cwd() / "ev-stealth-web" / "src" / "lib" / "getDepreciationData.ts",
        Path.cwd().parent / "ev-stealth-web" / "src" / "lib" / "getDepreciationData.ts",
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    raise FileNotFoundError(f"getDepreciationData.ts not found in: {candidates}")


def find_json_db_path() -> Path:
    current_file = Path(__file__).resolve()
    candidates = [
        current_file.parent.parent / "src" / "data" / "ev_depreciation_data.json",
        current_file.parent.parent / "ev-stealth-web" / "src" / "data" / "ev_depreciation_data.json",
        current_file.parent.parent.parent / "ev-stealth-web" / "src" / "data" / "ev_depreciation_data.json",
        Path.cwd() / "src" / "data" / "ev_depreciation_data.json",
        Path.cwd() / "ev-stealth-web" / "src" / "data" / "ev_depreciation_data.json",
        Path.cwd().parent / "ev-stealth-web" / "src" / "data" / "ev_depreciation_data.json",
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    raise FileNotFoundError(f"ev_depreciation_data.json not found in: {candidates}")


TS_ENGINE_PATH = find_ts_engine_path()
JSON_DB_PATH = find_json_db_path()

with open(JSON_DB_PATH, "r", encoding="utf-8") as f:
    DATABASE_JSON = json.load(f)


class AdversarialDepreciationEngineTest(unittest.TestCase):
    """Executes empirical stress tests directly against TypeScript getDepreciationData.ts using Node.js."""

    @classmethod
    def setUpClass(cls):
        if not shutil.which("node"):
            raise unittest.SkipTest("Node.js runtime not installed on host.")
        # Verify Node version
        proc = subprocess.run(["node", "--version"], capture_output=True, text=True)
        if proc.returncode != 0:
            raise unittest.SkipTest("Node.js probe failed.")

    def run_ts_eval(self, expr: str) -> Any:
        """Evaluates a JavaScript expression importing the TypeScript engine via Node native strip-types."""
        ts_path = str(TS_ENGINE_PATH)
        cmd = [
            "node",
            "--experimental-strip-types",
            "-e",
            f"""
            import * as engine from '{ts_path}';
            const res = ({expr});
            console.log(JSON.stringify(res));
            """,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if proc.returncode != 0:
            raise RuntimeError(f"Node execution failed with code {proc.returncode}:\n{proc.stderr}")

        lines = [
            line.strip()
            for line in proc.stdout.splitlines()
            if line.strip().startswith("{") or line.strip().startswith("[") or line.strip() in ("true", "false") or line.strip().replace(".", "", 1).isdigit()
        ]
        if not lines:
            raise ValueError(f"No JSON output from Node execution:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
        return json.loads(lines[-1])

    # ==========================================================================
    # 1. ANNUAL MILEAGE EXTREMES (0 km vs 1,000,000 km)
    # ==========================================================================

    def test_01_mileage_boundary_zero_km(self):
        """0 km annual mileage: validates no division by zero, positive residual, and pure calendar aging."""
        # A. Depreciation calculation with 0 km
        res = self.run_ts_eval("engine.calculateDepreciation({ modelId: 'model-3', years: 1.0, mileageKm: 0 })")
        self.assertFalse(math.isnan(res["adjustedResidualPct"]))
        self.assertFalse(math.isinf(res["adjustedResidualPct"]))
        self.assertGreaterEqual(res["adjustedResidualPct"], 5.0)
        self.assertLessEqual(res["adjustedResidualPct"], 99.0)
        self.assertGreater(res["estimatedResidualPriceKrw"], 0)
        self.assertGreater(res["depreciationAmountKrw"], 0)
        self.assertEqual(res["warrantyStatus"]["remainingKm"], 160000)

        # B. Battery simulation with 0 km
        bat = self.run_ts_eval("engine.simulateBatteryHealth({ years: 3.0, totalKm: 0, chemistry: 'NCM_811' })")
        self.assertEqual(bat["totalKm"], 0)
        self.assertEqual(bat["equivalentFullCycles"], 0)
        self.assertEqual(bat["cyclicLossPct"], 0.0)
        self.assertGreater(bat["calendarLossPct"], 0.0)
        self.assertGreater(bat["sohPct"], 95.0)
        self.assertIn(bat["grade"], ["GRADE_A"])

        # C. TCO calculation with 0 km
        tco = self.run_ts_eval("engine.calculateTcoComparison(0, 3)")
        self.assertEqual(tco["totalKm"], 0)
        self.assertEqual(tco["evTotalFuelCostKrw"], 0)
        self.assertEqual(tco["iceTotalFuelCostKrw"], 0)
        self.assertEqual(tco["fuelSavingsKrw"], 0)
        # Auxiliary and tax savings should still be accrued
        self.assertEqual(tco["totalAuxiliarySavingsKrw"], 600000 * 3)
        self.assertGreater(tco["totalCumulativeSavingsKrw"], 0)

    def test_02_mileage_boundary_one_million_km(self):
        """1,000,000 km annual mileage: validates bounded clamping, no overflow, and grade classification."""
        # A. Depreciation calculation with 1,000,000 km
        res = self.run_ts_eval("engine.calculateDepreciation({ modelId: 'model-3', years: 1.0, mileageKm: 1000000 })")
        self.assertFalse(math.isnan(res["adjustedResidualPct"]))
        self.assertFalse(math.isinf(res["adjustedResidualPct"]))
        # Clamped to statutory safety floor (5.0%)
        self.assertEqual(res["adjustedResidualPct"], 5.0)
        self.assertGreater(res["estimatedResidualPriceKrw"], 0)
        self.assertEqual(res["warrantyStatus"]["isExpired"], True)
        self.assertEqual(res["warrantyStatus"]["remainingKm"], 0)

        # B. Battery simulation with 1,000,000 km
        bat = self.run_ts_eval("engine.simulateBatteryHealth({ years: 1.0, totalKm: 1000000, chemistry: 'NCM_811' })")
        self.assertFalse(math.isnan(bat["sohPct"]))
        self.assertGreaterEqual(bat["sohPct"], 0.0)
        self.assertLessEqual(bat["sohPct"], 100.0)
        self.assertGreater(bat["equivalentFullCycles"], 2000)
        self.assertGreater(bat["cyclicLossPct"], 20.0)

        # C. Multi-year extreme mileage: 5 years @ 1,000,000 km/yr = 5,000,000 km
        bat_5m = self.run_ts_eval("engine.simulateBatteryHealth({ years: 5.0, totalKm: 5000000, chemistry: 'NCM_811' })")
        self.assertEqual(bat_5m["sohPct"], 0.0)  # clamped at 0.0%
        self.assertEqual(bat_5m["grade"], "CRITICAL")
        self.assertFalse(math.isnan(bat_5m["totalLossPct"]))

        # D. TCO calculation with 1,000,000 km/yr for 5 years
        tco = self.run_ts_eval("engine.calculateTcoComparison(1000000, 5)")
        self.assertEqual(tco["totalKm"], 5000000)
        self.assertGreater(tco["fuelSavingsKrw"], 0)
        self.assertFalse(math.isnan(tco["totalCumulativeSavingsKrw"]))
        self.assertFalse(math.isinf(tco["totalCumulativeSavingsKrw"]))

    # ==========================================================================
    # 2. DC FAST CHARGING EXTREMES (0% vs 100%)
    # ==========================================================================

    def test_03_dcfc_ratio_zero_vs_hundred_percent(self):
        """0% vs 100% DCFC: confirms strictly monotonic increase in cyclic aging and degradation strain."""
        for chem in ["LFP", "NCM_622", "NCM_811", "NCMA", "NCA"]:
            slow = self.run_ts_eval(f"engine.simulateBatteryHealth({{ years: 3.0, totalKm: 60000, chemistry: '{chem}', dcfcRatio: 0.0 }})")
            fast = self.run_ts_eval(f"engine.simulateBatteryHealth({{ years: 3.0, totalKm: 60000, chemistry: '{chem}', dcfcRatio: 1.0 }})")

            # Calendar aging is identical
            self.assertAlmostEqual(slow["calendarLossPct"], fast["calendarLossPct"], delta=0.01)

            # Cyclic aging and total loss are strictly higher under 100% DCFC
            self.assertGreater(fast["cyclicLossPct"], slow["cyclicLossPct"])
            self.assertGreaterEqual(fast["totalLossPct"], slow["totalLossPct"])
            self.assertLessEqual(fast["sohPct"], slow["sohPct"])

            # Valid range assertions
            self.assertGreaterEqual(fast["sohPct"], 0.0)
            self.assertLessEqual(fast["sohPct"], 100.0)
            self.assertFalse(math.isnan(fast["sohPct"]))

    # ==========================================================================
    # 3. TEMPERATURE EXTREMES (-30°C vs +45°C)
    # ==========================================================================

    def test_04_temperature_extremes_minus_30_vs_plus_45(self):
        """Extreme cold (-30°C) vs extreme desert heat (+45°C): verifies Arrhenius vs cold-plating behavior."""
        for chem in ["LFP", "NCM_811"]:
            cold = self.run_ts_eval(f"engine.simulateBatteryHealth({{ years: 3.0, totalKm: 45000, chemistry: '{chem}', ambientTempC: -30.0 }})")
            ref = self.run_ts_eval(f"engine.simulateBatteryHealth({{ years: 3.0, totalKm: 45000, chemistry: '{chem}', ambientTempC: 25.0 }})")
            hot = self.run_ts_eval(f"engine.simulateBatteryHealth({{ years: 3.0, totalKm: 45000, chemistry: '{chem}', ambientTempC: 45.0 }})")

            # 1. Calendar loss increases with temperature according to Arrhenius kinetics
            self.assertLess(cold["calendarLossPct"], ref["calendarLossPct"])
            self.assertLess(ref["calendarLossPct"], hot["calendarLossPct"])

            # 2. Cold-temperature cyclic loss has sensitivity gamma penalty (lithium plating)
            self.assertGreater(cold["cyclicLossPct"], ref["cyclicLossPct"])

            # 3. Overall SoH bounds
            for r in (cold, ref, hot):
                self.assertGreaterEqual(r["sohPct"], 0.0)
                self.assertLessEqual(r["sohPct"], 100.0)
                self.assertFalse(math.isnan(r["sohPct"]))
                self.assertFalse(math.isinf(r["sohPct"]))

    # ==========================================================================
    # 4. ZERO SUBSIDIES VS MAXIMUM SUBSIDY
    # ==========================================================================

    def test_05_subsidy_extremes_zero_vs_maximum(self):
        """Zero subsidy (MSRP = net purchase price) vs maximum local+national subsidy."""
        # A. Zero subsidy clawback
        cb_zero = self.run_ts_eval("engine.calculateSubsidyClawback(6, 0, 'inter', 0)")
        self.assertEqual(cb_zero["localClawbackKrw"], 0)
        self.assertEqual(cb_zero["nationalClawbackKrw"], 0)
        self.assertEqual(cb_zero["totalClawbackKrw"], 0)
        self.assertEqual(cb_zero["statutoryClawbackRate"], 0.60)

        # B. Maximum subsidy (e.g., 12,000,000 KRW local + 8,000,000 KRW national)
        # Inter-province: only local is clawed back
        cb_inter = self.run_ts_eval("engine.calculateSubsidyClawback(2, 12000000, 'inter', 8000000)")
        self.assertEqual(cb_inter["statutoryClawbackRate"], 0.70)
        self.assertEqual(cb_inter["localClawbackKrw"], 8400000)
        self.assertEqual(cb_inter["nationalClawbackKrw"], 0)
        self.assertEqual(cb_inter["totalClawbackKrw"], 8400000)

        # Export: both local and national clawed back
        cb_export = self.run_ts_eval("engine.calculateSubsidyClawback(2, 12000000, 'export', 8000000)")
        self.assertEqual(cb_export["localClawbackKrw"], 8400000)
        self.assertEqual(cb_export["nationalClawbackKrw"], 5600000)
        self.assertEqual(cb_export["totalClawbackKrw"], 14000000)

        # C. Zero subsidy depreciation: effective basis equals msrp basis when purchase price overridden
        dep_msrp = self.run_ts_eval("engine.calculateDepreciation({ modelId: 'model-3', years: 2.0, priceBasis: 'msrp' })")
        dep_custom = self.run_ts_eval(f"engine.calculateDepreciation({{ modelId: 'model-3', years: 2.0, priceBasis: 'effective', customPurchasePriceKrw: {dep_msrp['basePurchasePriceKrw']} }})")
        self.assertEqual(dep_msrp["basePurchasePriceKrw"], dep_custom["basePurchasePriceKrw"])

    # ==========================================================================
    # 5. FRACTIONAL OWNERSHIP DURATIONS (0.1, 0.5, 2.5, 5.0, 5.5 years)
    # ==========================================================================

    def test_06_fractional_ownership_durations_depreciation(self):
        """Fractional durations (0.1, 0.5, 2.5, 5.0, 5.5 years) in depreciation interpolation."""
        fractions = [0.1, 0.5, 1.25, 2.5, 3.75, 5.0, 5.5]
        for m in DATABASE_JSON["models"]:
            model_id = m["id"]
            for yr in fractions:
                res = self.run_ts_eval(f"engine.calculateDepreciation({{ modelId: '{model_id}', years: {yr} }})")
                self.assertFalse(math.isnan(res["adjustedResidualPct"]), f"NaN at {yr} for {model_id}")
                self.assertFalse(math.isinf(res["adjustedResidualPct"]), f"Inf at {yr} for {model_id}")
                self.assertGreaterEqual(res["adjustedResidualPct"], 5.0)
                self.assertLessEqual(res["adjustedResidualPct"], 99.0)
                self.assertGreater(res["estimatedResidualPriceKrw"], 0)
                self.assertGreater(res["depreciationAmountKrw"], 0)

    # ==========================================================================
    # 6. EARLY RESALE CLAWBACK BOUNDARIES (1d, 89d, 90d, 364d, 729d, 730d)
    # ==========================================================================

    def test_07_clawback_boundaries_calendar_months(self):
        """Standard calendar conversion (days / (365/12)) matching statutory tiers."""
        local_s = 4000000
        nat_s = 6500000

        # Day 1 (~0.033 mos): Tier [0, 3) -> 70%
        cb_1 = self.run_ts_eval(f"engine.calculateSubsidyClawback(1 / (365/12), {local_s}, 'inter', {nat_s})")
        self.assertEqual(cb_1["statutoryClawbackRate"], 0.70)
        self.assertEqual(cb_1["localClawbackKrw"], 2800000)
        self.assertEqual(cb_1["nationalClawbackKrw"], 0)
        self.assertFalse(cb_1["isExempt"])

        # Day 89 (~2.926 mos): Tier [0, 3) -> 70%
        cb_89 = self.run_ts_eval(f"engine.calculateSubsidyClawback(89 / (365/12), {local_s}, 'inter', {nat_s})")
        self.assertEqual(cb_89["statutoryClawbackRate"], 0.70)
        self.assertEqual(cb_89["localClawbackKrw"], 2800000)
        self.assertFalse(cb_89["isExempt"])

        # Day 90:
        # Under 30 days/month (90/30 = 3.000 mos): Tier [3, 6) -> 65%
        # Under 365/12 days/month (90/30.417 = 2.959 mos): Tier [0, 3) -> 70%
        cb_90_exact_3m = self.run_ts_eval(f"engine.calculateSubsidyClawback(3.0, {local_s}, 'inter', {nat_s})")
        self.assertEqual(cb_90_exact_3m["statutoryClawbackRate"], 0.65)
        self.assertEqual(cb_90_exact_3m["localClawbackKrw"], 2600000)

        # Day 364 (11.967 mos): 1 day before 1 year -> Tier [9, 12) -> 55%
        cb_364 = self.run_ts_eval(f"engine.calculateSubsidyClawback(364 / (365/12), {local_s}, 'inter', {nat_s})")
        self.assertEqual(cb_364["statutoryClawbackRate"], 0.55)
        self.assertEqual(cb_364["localClawbackKrw"], 2200000)
        self.assertFalse(cb_364["isExempt"])

        # Day 729 (23.967 mos): 1 day before 2 years -> Tier [21, 24) -> 20%
        cb_729 = self.run_ts_eval(f"engine.calculateSubsidyClawback(729 / (365/12), {local_s}, 'inter', {nat_s})")
        self.assertEqual(cb_729["statutoryClawbackRate"], 0.20)
        self.assertEqual(cb_729["localClawbackKrw"], 800000)
        self.assertFalse(cb_729["isExempt"])

        # Day 730 (24.000 mos): 24-month boundary -> Tier >=24 -> 0%, 100% EXEMPT
        cb_730 = self.run_ts_eval(f"engine.calculateSubsidyClawback(24.0, {local_s}, 'inter', {nat_s})")
        self.assertEqual(cb_730["statutoryClawbackRate"], 0.00)
        self.assertEqual(cb_730["localClawbackKrw"], 0)
        self.assertEqual(cb_730["totalClawbackKrw"], 0)
        self.assertTrue(cb_730["isExempt"])

        # Intra-province transfer: always exempt (0 KRW) across all days
        cb_intra_1 = self.run_ts_eval(f"engine.calculateSubsidyClawback(1 / (365/12), {local_s}, 'intra', {nat_s})")
        cb_intra_729 = self.run_ts_eval(f"engine.calculateSubsidyClawback(729 / (365/12), {local_s}, 'intra', {nat_s})")
        self.assertTrue(cb_intra_1["isExempt"])
        self.assertEqual(cb_intra_1["totalClawbackKrw"], 0)
        self.assertTrue(cb_intra_729["isExempt"])
        self.assertEqual(cb_intra_729["totalClawbackKrw"], 0)

    # ==========================================================================
    # 7. ADVERSARIAL STRESS FINDINGS & HARDENED INVARIANTS VERIFICATION
    # ==========================================================================

    def test_08_hardened_lfp_curve_monotonicity_at_year_3(self):
        """VERIFICATION 1: Monotonicity preserved for LFP vehicles across Year 3.0 boundary.
        
        Smooth monotonic ramp (years - 2.0 clamped between 0.0 and 1.0) eliminates
        the discrete step bonus jump. As the vehicle ages from 2.99y to 3.00y,
        adjusted residual percentage decreases monotonically:
        r(3.00) <= r(2.99).
        """
        r_299 = self.run_ts_eval("engine.calculateDepreciation({ modelId: 'model-y-rwd', years: 2.99 })")
        r_300 = self.run_ts_eval("engine.calculateDepreciation({ modelId: 'model-y-rwd', years: 3.00 })")

        # Empirically verify monotonicity holds (no inversion)
        is_monotonic = r_300["adjustedResidualPct"] <= r_299["adjustedResidualPct"]
        self.assertTrue(
            is_monotonic,
            f"Expected monotonicity between 2.99y and 3.00y for Model Y RWD, but got r(2.99)={r_299['adjustedResidualPct']}, r(3.00)={r_300['adjustedResidualPct']}"
        )
        self.assertEqual(r_299["adjustedResidualPct"], 72.1)
        self.assertEqual(r_300["adjustedResidualPct"], 72.0)

    def test_09_hardened_battery_health_negative_km_resilience(self):
        """VERIFICATION 2: simulateBatteryHealth safely clamps negative totalKm to 0.
        
        Math.max(0, mileage) prevents negative base in Math.pow(equivalentFullCycles, w).
        Ensures sohPct and cyclicLossPct are valid numbers (not NaN/null).
        """
        res = self.run_ts_eval("engine.simulateBatteryHealth({ years: 1.0, totalKm: -100, chemistry: 'NCM_811' })")
        self.assertIsNotNone(
            res["sohPct"],
            "Expected sohPct to be a valid number (not NaN/null) on negative totalKm"
        )
        self.assertIsNotNone(
            res["cyclicLossPct"],
            "Expected cyclicLossPct to be a valid number (not NaN/null) on negative totalKm"
        )
        self.assertEqual(res["totalKm"], 0)
        self.assertEqual(res["cyclicLossPct"], 0)
        self.assertEqual(res["sohPct"], 98.2)

    def test_10_hardened_tco_fractional_years_handling(self):
        """VERIFICATION 3: calculateTcoComparison handles fractional years safely.
        
        Using Math.max(1, Math.round(years)) guarantees that fractional ownership
        durations (years < 1.0) produce at least 1 yearly breakdown record and positive
        cumulative savings, rather than truncating to 0.
        """
        tco_01 = self.run_ts_eval("engine.calculateTcoComparison(15000, 0.1)")
        self.assertGreaterEqual(len(tco_01["yearlyBreakdown"]), 1)
        self.assertGreater(tco_01["totalCumulativeSavingsKrw"], 0)
        self.assertEqual(tco_01["totalKm"], 15000)

        tco_25 = self.run_ts_eval("engine.calculateTcoComparison(15000, 2.5)")
        self.assertGreaterEqual(len(tco_25["yearlyBreakdown"]), 2)
        self.assertEqual(len(tco_25["yearlyBreakdown"]), 3)
        self.assertEqual(tco_25["totalKm"], 45000)
        self.assertGreater(tco_25["totalCumulativeSavingsKrw"], 0)


if __name__ == "__main__":
    unittest.main()
