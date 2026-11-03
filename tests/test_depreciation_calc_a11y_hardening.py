"""
tests/test_depreciation_calc_a11y_hardening.py - Deep Audit & Hardening Test Suite
for EV Depreciation, Battery Electrochemical Modeling, Input Sanitization, and SVG A11y.

Coverage:
1. Depreciation calculation formula edge cases (0 years, 0 mileage, 500,000 km, extreme prices).
2. Battery health degradation modeling (SOH degradation, Arrhenius temperature effect, DCFC penalties).
3. Defensive handling of missing/partial model specifications without TypeErrors.
4. Input sanitization (numeric strings, negative prices, NaN propagation prevention, 10B KRW cap).
5. Statutory subsidy clawback and TCO economic engine resilience.
6. Accessible SVG chart semantics (title, desc, aria-labelledby, decorative aria-hidden).
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest

def _find_repo_root() -> Path:
    p = Path(__file__).resolve().parent
    while p != p.parent:
        if (p / "ev-stealth-web").is_dir() and (p / "data").is_dir():
            return p
        p = p.parent
    return Path("/Users/a7890/src/my-e-car")

PROJECT_ROOT = _find_repo_root()
WEB_ROOT = PROJECT_ROOT / "ev-stealth-web"


class TestDepreciationCalcAndA11yHardening(unittest.TestCase):
    """Deep adversarial and edge case audit for EV Depreciation Calculator engine."""

    def _run_node_ts(self, ts_code: str) -> dict:
        """Execute TypeScript code snippet via Node.js with experimental strip types."""
        cmd = [
            "node",
            "--no-warnings",
            "--experimental-strip-types",
            "-e",
            ts_code,
        ]
        proc = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, check=True)
        lines = [line.strip() for line in proc.stdout.splitlines() if line.strip().startswith("{") or line.strip().startswith("[")]
        if not lines:
            self.fail(f"No JSON output from Node:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
        return json.loads(lines[-1])

    def test_01_depreciation_zero_mileage_and_zero_years(self) -> None:
        """Verify calculateDepreciation handles 0 years, 0 mileage, and both at once."""
        code = """
import { calculateDepreciation as c1 } from './ev-stealth-web/src/lib/depreciationCalculations.ts';
import { calculateDepreciation as c2 } from './ev-stealth-web/src/lib/getDepreciationData.ts';

const resBothZero = c1({ years: 0, mileageKm: 0 });
const resZeroYears = c1({ years: 0, mileageKm: 45000 });
const resZeroMileage = c1({ years: 3, mileageKm: 0 });
const resLibBothZero = c2({ years: 0, mileageKm: 0 });

console.log(JSON.stringify({
  bothZeroResidualPct: resBothZero.adjustedResidualPct,
  bothZeroDepAmount: resBothZero.depreciationAmountKrw,
  bothZeroResidualPrice: resBothZero.estimatedResidualPriceKrw,
  bothZeroWarrantyExpired: resBothZero.warrantyStatus.isExpired,
  zeroYearsResidualPct: resZeroYears.adjustedResidualPct,
  zeroMileageResidualPct: resZeroMileage.adjustedResidualPct,
  parityResidualPct: resBothZero.adjustedResidualPct === resLibBothZero.adjustedResidualPct,
}));
"""
        out = self._run_node_ts(code)
        self.assertTrue(out["parityResidualPct"], "depreciationCalculations and getDepreciationData must match")
        self.assertGreaterEqual(out["bothZeroResidualPct"], 5.0)
        self.assertLessEqual(out["bothZeroResidualPct"], 99.0)
        self.assertGreaterEqual(out["bothZeroResidualPrice"], 0)
        self.assertGreaterEqual(out["bothZeroDepAmount"], 0)
        self.assertFalse(out["bothZeroWarrantyExpired"], "0-year vehicle must not have expired warranty")
        self.assertGreater(out["zeroMileageResidualPct"], 40.0, "0-km vehicle should maintain strong residual value")

    def test_02_depreciation_extreme_high_mileage(self) -> None:
        """Verify extreme high mileage (500k, 1M, 10M km) enforces floor and produces finite numbers."""
        code = """
import { calculateDepreciation } from './ev-stealth-web/src/lib/depreciationCalculations.ts';

const res500k = calculateDepreciation({ years: 3, mileageKm: 500_000 });
const res1M = calculateDepreciation({ years: 3, mileageKm: 1_000_000 });
const res10M = calculateDepreciation({ years: 3, mileageKm: 10_000_000 });

console.log(JSON.stringify({
  res500kFloor: res500k.adjustedResidualPct,
  res1MFloor: res1M.adjustedResidualPct,
  res10MFloor: res10M.adjustedResidualPct,
  is500kFinite: Number.isFinite(res500k.depreciationAmountKrw),
  is10MFinite: Number.isFinite(res10M.depreciationAmountKrw),
  is10MPriceNonNegative: res10M.estimatedResidualPriceKrw >= 0,
}));
"""
        out = self._run_node_ts(code)
        self.assertEqual(out["res500kFloor"], 5.0, "500,000 km residual rate hits statutory 5.0% floor")
        self.assertEqual(out["res1MFloor"], 5.0, "1,000,000 km residual rate hits statutory 5.0% floor")
        self.assertEqual(out["res10MFloor"], 5.0, "10,000,000 km residual rate hits statutory 5.0% floor")
        self.assertTrue(out["is500kFinite"])
        self.assertTrue(out["is10MFinite"])
        self.assertTrue(out["is10MPriceNonNegative"])

    def test_03_depreciation_extreme_prices_and_string_parsing(self) -> None:
        """Verify numeric strings, 0 KRW, negative prices, and 10B KRW cap."""
        code = """
import { calculateDepreciation } from './ev-stealth-web/src/lib/depreciationCalculations.ts';

const resZero = calculateDepreciation({ years: 2, customPurchasePriceKrw: 0 });
const resNeg = calculateDepreciation({ years: 2, customPurchasePriceKrw: -10_000_000 });
const resString = calculateDepreciation({ years: 2, customPurchasePriceKrw: "60000000" as any });
const resHigh = calculateDepreciation({ years: 2, customPurchasePriceKrw: 50_000_000_000 });

console.log(JSON.stringify({
  zeroBase: resZero.basePurchasePriceKrw,
  zeroRes: resZero.estimatedResidualPriceKrw,
  negBase: resNeg.basePurchasePriceKrw,
  stringBase: resString.basePurchasePriceKrw,
  highBase: resHigh.basePurchasePriceKrw,
}));
"""
        out = self._run_node_ts(code)
        self.assertEqual(out["zeroBase"], 0)
        self.assertEqual(out["zeroRes"], 0)
        self.assertEqual(out["negBase"], 54_100_000, "Negative price falls back to default MSRP")
        self.assertEqual(out["stringBase"], 60_000_000, "Numeric string '60000000' correctly parsed")
        self.assertEqual(out["highBase"], 10_000_000_000, "Price above 10B capped at 10B KRW")

    def test_04_battery_health_arrhenius_temperature_extremes(self) -> None:
        """Verify Arrhenius temperature kinetics: calendar loss increases monotonically with temperature."""
        code = """
import { simulateBatteryHealth } from './ev-stealth-web/src/lib/depreciationCalculations.ts';

const tCold = simulateBatteryHealth({ years: 3, ambientTempC: -20 });
const tRef = simulateBatteryHealth({ years: 3, ambientTempC: 25 });
const tHot = simulateBatteryHealth({ years: 3, ambientTempC: 45 });
const tExtremeHot = simulateBatteryHealth({ years: 3, ambientTempC: 60 });

console.log(JSON.stringify({
  coldLoss: tCold.calendarLossPct,
  refLoss: tRef.calendarLossPct,
  hotLoss: tHot.calendarLossPct,
  extremeHotLoss: tExtremeHot.calendarLossPct,
  monotonic: tCold.calendarLossPct < tRef.calendarLossPct && tRef.calendarLossPct < tHot.calendarLossPct && tHot.calendarLossPct < tExtremeHot.calendarLossPct,
  sohColdBounded: tCold.sohPct >= 0 && tCold.sohPct <= 100,
  sohHotBounded: tHot.sohPct >= 0 && tHot.sohPct <= 100,
}));
"""
        out = self._run_node_ts(code)
        self.assertTrue(out["monotonic"], "Calendar loss must strictly increase with temperature via Arrhenius factor")
        self.assertTrue(out["sohColdBounded"])
        self.assertTrue(out["sohHotBounded"])

    def test_05_battery_health_dcfc_strain_penalties(self) -> None:
        """Verify DC fast charging penalties: higher DCFC ratio increases cyclic degradation."""
        code = """
import { simulateBatteryHealth } from './ev-stealth-web/src/lib/depreciationCalculations.ts';

const slowCharge = simulateBatteryHealth({ years: 3, totalKm: 60000, dcfcRatio: 0.0 });
const medCharge = simulateBatteryHealth({ years: 3, totalKm: 60000, dcfcRatio: 0.5 });
const fastCharge = simulateBatteryHealth({ years: 3, totalKm: 60000, dcfcRatio: 1.0 });

console.log(JSON.stringify({
  slowLoss: slowCharge.cyclicLossPct,
  medLoss: medCharge.cyclicLossPct,
  fastLoss: fastCharge.cyclicLossPct,
  sohSlow: slowCharge.sohPct,
  sohFast: fastCharge.sohPct,
  cyclicMonotonic: slowCharge.cyclicLossPct < medCharge.cyclicLossPct && medCharge.cyclicLossPct < fastCharge.cyclicLossPct,
  sohMonotonic: slowCharge.sohPct > fastCharge.sohPct,
}));
"""
        out = self._run_node_ts(code)
        self.assertTrue(out["cyclicMonotonic"], "Cyclic loss must increase as DCFC ratio increases")
        self.assertTrue(out["sohMonotonic"], "Fast charging should accelerate SOH loss relative to slow charging")

    def test_06_model_defensive_fallbacks_without_type_errors(self) -> None:
        """Verify incomplete/partial model objects do not throw TypeErrors."""
        code = """
import { calculateDepreciation, simulateBatteryHealth } from './ev-stealth-web/src/lib/depreciationCalculations.ts';

// Model missing warranty, battery_specs, factor_weights
const partialModel = { id: 'test-partial', model_name: 'Partial' } as any;

const depRes = calculateDepreciation({ years: 2, model: partialModel });
const batRes = simulateBatteryHealth({ years: 2, packCapacityKwh: 60 });

console.log(JSON.stringify({
  depSuccess: typeof depRes === 'object' && depRes !== null,
  batSuccess: typeof batRes === 'object' && batRes !== null,
  remainingYears: depRes.warrantyStatus.remainingYears,
  defenseTier: depRes.defenseTier,
  sohPct: batRes.sohPct,
}));
"""
        out = self._run_node_ts(code)
        self.assertTrue(out["depSuccess"])
        self.assertTrue(out["batSuccess"])
        self.assertGreaterEqual(out["sohPct"], 0)

    def test_07_subsidy_clawback_string_and_boundary_resilience(self) -> None:
        """Verify subsidy clawback string parsing, 100M cap, and statutory exemptions."""
        code = """
import { calculateSubsidyClawback } from './ev-stealth-web/src/lib/depreciationCalculations.ts';

const cbString = calculateSubsidyClawback("18" as any, "4000000" as any, "inter", "6000000" as any);
const cb24m = calculateSubsidyClawback(24, 4000000, "inter", 6000000);
const cbIntra = calculateSubsidyClawback(6, 4000000, "intra", 6000000);
const cbCap = calculateSubsidyClawback(6, 500_000_000, "export", 500_000_000);

console.log(JSON.stringify({
  stringHeldMonths: cbString.heldMonths,
  stringLocalReceived: cbString.localSubsidyReceivedKrw,
  cb24mExempt: cb24m.isExempt,
  cb24mTotal: cb24m.totalClawbackKrw,
  cbIntraExempt: cbIntra.isExempt,
  cbIntraTotal: cbIntra.totalClawbackKrw,
  cbCapLocal: cbCap.localSubsidyReceivedKrw,
  cbCapNational: cbCap.nationalSubsidyReceivedKrw,
}));
"""
        out = self._run_node_ts(code)
        self.assertEqual(out["stringHeldMonths"], 18)
        self.assertEqual(out["stringLocalReceived"], 4_000_000)
        self.assertTrue(out["cb24mExempt"], "24+ months must be exempt")
        self.assertEqual(out["cb24mTotal"], 0)
        self.assertTrue(out["cbIntraExempt"], "Intra-city transfer must be exempt")
        self.assertEqual(out["cbIntraTotal"], 0)
        self.assertEqual(out["cbCapLocal"], 100_000_000, "Subsidies capped at 100M KRW")
        self.assertEqual(out["cbCapNational"], 100_000_000)

    def test_08_tco_calculation_resilience(self) -> None:
        """Verify TCO string parsing, 0 annual km, and max 30-year cap."""
        code = """
import { calculateTcoComparison } from './ev-stealth-web/src/lib/depreciationCalculations.ts';

const tcoString = calculateTcoComparison("15000" as any, "3" as any, "5.2" as any, "0.7" as any, "1998" as any);
const tcoZeroKm = calculateTcoComparison(0, 3);
const tcoHighYears = calculateTcoComparison(15000, 50);

console.log(JSON.stringify({
  stringAnnualKm: tcoString.annualKm,
  stringYears: tcoString.years,
  zeroKmFuelSavings: tcoZeroKm.fuelSavingsKrw,
  zeroKmTaxSavings: tcoZeroKm.taxSavingsKrw,
  highYearsCap: tcoHighYears.years,
  breakdownLength: tcoHighYears.yearlyBreakdown.length,
}));
"""
        out = self._run_node_ts(code)
        self.assertEqual(out["stringAnnualKm"], 15000)
        self.assertEqual(out["stringYears"], 3)
        self.assertEqual(out["zeroKmFuelSavings"], 0, "0 km results in 0 fuel savings")
        self.assertGreater(out["zeroKmTaxSavings"], 0, "EV tax savings exist even at 0 km")
        self.assertEqual(out["highYearsCap"], 30, "Years capped at 30 to prevent unbounded computation")
        self.assertLessEqual(out["breakdownLength"], 31)

    def test_09_depreciation_calculator_client_a11y_svg_audit(self) -> None:
        """Verify DepreciationCalculatorClient.tsx implements required WCAG AA SVG tags and aria attributes."""
        client_path = WEB_ROOT / "src" / "app" / "depreciation-calculator" / "DepreciationCalculatorClient.tsx"
        self.assertTrue(client_path.exists(), f"Client component must exist at {client_path}")
        code = client_path.read_text(encoding="utf-8")

        # 1. SVG Chart Accessibility
        self.assertIn('aria-labelledby="dep-chart-title dep-chart-desc"', code, "SVG must link title and desc via aria-labelledby")
        self.assertIn('id="dep-chart-title"', code, "SVG must contain title element")
        self.assertIn('id="dep-chart-desc"', code, "SVG must contain desc element")
        self.assertIn('role="img"', code, "SVG must have role='img'")
        self.assertIn('aria-hidden="true"', code, "Legend color squares must have aria-hidden='true'")

        # 2. Radial SOH Gauge Accessibility
        self.assertIn('role="progressbar"', code, "SOH gauge must have role='progressbar'")
        self.assertIn('aria-valuenow=', code, "SOH gauge must have aria-valuenow")
        self.assertIn('aria-valuetext=', code, "SOH gauge must have aria-valuetext")

        # 3. Input Sanitization Feedback
        self.assertIn('role="alert"', code, "Inline validation for price bounds must have role='alert'")
        self.assertIn('Number(customPriceInput) < 0', code, "Negative price check in UI")
        self.assertIn('Number(customPriceInput) > 10_000_000_000', code, "10B cap check in UI")


if __name__ == "__main__":
    unittest.main()
