"""
tests/test_frontend_math_a11y_sync5.py - Empirical Verification Test Suite for Next.js TypeScript
Math Functions under Adversarial Inputs & Static AST/Regex A11y Validations.

Authoritative Reference:
- ORIGINAL_REQUEST.md
- DISPATCH.md (sync5 wave 2 test specification)
- W3C WCAG 2.1 Level AA Accessibility Standards

Coverage:
1. Next.js TypeScript Math Function Stress Testing via Node.js Eval:
   - getDepreciationData.ts:
     * calculateTcoComparison(15000, 3, NaN, NaN, NaN) -> zero NaN or Infinity in outputs.
     * simulateBatteryHealth({ years: 3, vehicleEfficiencyKmPerKwh: NaN, packCapacityKwh: NaN }) -> zero NaN.
     * calculateDepreciation({ modelId: 'model-3', years: NaN, mileageKm: NaN, customPurchasePriceKrw: NaN }) -> valid outputs.
     * calculateSubsidyClawback(NaN, NaN, 'inter', NaN) -> zero NaN.
   - getSubsidyData.ts:
     * getPriceSubsidyRatio(NaN) -> valid numeric output (1.0).
     * getPriceSubsidyRatio(-1000) -> valid numeric output (1.0).
     * getPriceSubsidyRatio(54_999_999, 55_000_000, 84_999_999, 85_000_000) -> exact statutory ratio checks.
     * calculateNetSubsidy('ioniq-5-2026', 'KR-11', NaN) -> zero NaN.
   - getDailyReports.ts:
     * normalizeReport({ sentiment_score: NaN, negativity_score: NaN }, 0) -> finite score, zero NaN.
2. Static AST / Regex Accessibility (A11y) Validations across all .tsx files:
   - 0 occurrences of animate-pulse or animate-bounce without motion-reduce:animate-none.
   - 0 occurrences of role="progressbar" nested inside role="button" or <button>.
   - All <input id=...> have associated <label htmlFor=...>.
   - Mobile navigation drawer handles Escape key dismissal.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest
from typing import Any, Dict, List, Optional, Set, Tuple


def _find_project_root() -> Path:
    current = Path(__file__).resolve().parent
    for _ in range(5):
        if (current / "ev-stealth-web").is_dir():
            return current
        if (current / "src" / "app").is_dir():
            return current.parent
        current = current.parent
    return Path.cwd()


PROJECT_ROOT = _find_project_root()
WEB_ROOT = PROJECT_ROOT / "ev-stealth-web" if (PROJECT_ROOT / "ev-stealth-web" / "package.json").is_file() else PROJECT_ROOT
SRC_DIR = WEB_ROOT / "src"
APP_DIR = SRC_DIR / "app"
LIB_DIR = SRC_DIR / "lib"


def _eval_ts_node(script: str, timeout_sec: int = 30) -> Any:
    """
    Executes a Node.js snippet using jiti to resolve TypeScript files with alias mappings
    synchronously and accurately without transpilation skew.
    """
    if not shutil.which("node"):
        raise unittest.SkipTest("Node.js runtime not installed on host environment.")

    jiti_path = WEB_ROOT / "node_modules" / "jiti"
    pkg_path = WEB_ROOT / "package.json"

    if not jiti_path.exists():
        raise unittest.SkipTest(f"jiti not found at {jiti_path}")

    node_wrapper = f"""
    const Module = require('module');
    const path = require('path');
    const origResolve = Module._resolveFilename;
    Module._resolveFilename = function(request, parent, isMain, options) {{
        if (request.startsWith('@/')) {{
            request = request.replace('@/', path.resolve({json.dumps(str(SRC_DIR))}) + '/');
        }}
        return origResolve.call(this, request, parent, isMain, options);
    }};
    const createJITI = require({json.dumps(str(jiti_path))});
    const jiti = createJITI({json.dumps(str(pkg_path))});

    {script}
    """
    proc = subprocess.run(
        ["node", "-e", node_wrapper],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=timeout_sec,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Node execution failed with exit code {proc.returncode}:\n"
            f"STDOUT:\n{proc.stdout}\n"
            f"STDERR:\n{proc.stderr}"
        )

    lines = [
        line.strip()
        for line in proc.stdout.splitlines()
        if line.strip() and not line.strip().startswith("(") and not line.strip().startswith("Warning:")
    ]
    if not lines:
        raise ValueError(f"No JSON output from Node execution:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    return json.loads(lines[-1])


def _assert_no_none_or_nan(test_case: unittest.TestCase, obj: Any, path: str = "root") -> None:
    """Recursively asserts that a deserialized JSON object contains no None values (which represent NaN/Infinity)."""
    if obj is None:
        test_case.fail(f"Found None (serialized NaN/Infinity/undefined) at {path}")
    elif isinstance(obj, float):
        test_case.assertFalse(math.isnan(obj), f"Float NaN found at {path}")
        test_case.assertFalse(math.isinf(obj), f"Float Infinity found at {path}")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _assert_no_none_or_nan(test_case, v, f"{path}.{k}")
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            _assert_no_none_or_nan(test_case, item, f"{path}[{idx}]")


# ==============================================================================
# 1. TYPESCRIPT MATH ENGINE ADVERSARIAL VERIFICATION
# ==============================================================================

class TestTypeScriptMathAdversarialInputs(unittest.TestCase):
    """Verifies that Next.js TypeScript math functions handle adversarial inputs (NaN, Infinity, negative) cleanly."""

    @classmethod
    def setUpClass(cls):
        if not shutil.which("node"):
            raise unittest.SkipTest("Node.js runtime not installed on host.")
        if not (LIB_DIR / "getDepreciationData.ts").exists():
            raise FileNotFoundError(f"Missing getDepreciationData.ts at {LIB_DIR}")
        if not (LIB_DIR / "getSubsidyData.ts").exists():
            raise FileNotFoundError(f"Missing getSubsidyData.ts at {LIB_DIR}")
        if not (LIB_DIR / "getDailyReports.ts").exists():
            raise FileNotFoundError(f"Missing getDailyReports.ts at {LIB_DIR}")

    def test_01_calculate_tco_comparison_with_nan_inputs(self):
        """
        Invokes calculateTcoComparison(15000, 3, NaN, NaN, NaN) via Node.js eval.
        Asserts that no NaN, null, or Infinity appear anywhere in the output structure.
        """
        dep_path = json.dumps(str(LIB_DIR / "getDepreciationData.ts"))
        script = f"""
        const dep = jiti({dep_path});
        const res = dep.calculateTcoComparison(15000, 3, NaN, NaN, NaN);
        console.log(JSON.stringify(res));
        """
        res = _eval_ts_node(script)

        # 1. Check all top-level numeric fields
        self.assertIsInstance(res, dict)
        self.assertEqual(res.get("annualKm"), 15000)
        self.assertEqual(res.get("years"), 3)
        self.assertEqual(res.get("totalKm"), 45000)

        # Denominator & rate fallbacks
        self.assertIsNotNone(res.get("evEfficiencyKmPerKwh"))
        self.assertGreater(res["evEfficiencyKmPerKwh"], 0)
        self.assertIsNotNone(res.get("blendedElectricityTariffKrwPerKwh"))
        self.assertGreater(res["blendedElectricityTariffKrwPerKwh"], 0)

        # Financial outputs must be finite numbers
        for field in [
            "evFuelCostPerKm",
            "iceFuelCostPerKm",
            "evTotalFuelCostKrw",
            "iceTotalFuelCostKrw",
            "fuelSavingsKrw",
            "evTotalTaxKrw",
            "iceTotalTaxKrw",
            "taxSavingsKrw",
            "tollSavingsKrw",
            "parkingSavingsKrw",
            "maintenanceSavingsKrw",
            "totalAuxiliarySavingsKrw",
            "totalCumulativeSavingsKrw",
        ]:
            val = res.get(field)
            self.assertIsNotNone(val, f"Field {field} is None (indicates NaN/Infinity)")
            self.assertIsInstance(val, (int, float), f"Field {field} is not numeric: {val}")
            self.assertTrue(math.isfinite(val), f"Field {field} is not finite: {val}")

        # 2. Check yearly breakdown elements
        yearly = res.get("yearlyBreakdown", [])
        self.assertEqual(len(yearly), 3)
        for yr_idx, yr in enumerate(yearly, 1):
            self.assertEqual(yr["year"], yr_idx)
            for num_key in [
                "cumulativeKm",
                "evElectricityCostKrw",
                "iceFuelCostKrw",
                "evAutomobileTaxKrw",
                "iceAutomobileTaxKrw",
                "tollSavingsKrw",
                "parkingSavingsKrw",
                "maintenanceSavingsKrw",
                "annualNetSavingsKrw",
                "cumulativeNetSavingsKrw",
            ]:
                num_val = yr.get(num_key)
                self.assertIsNotNone(num_val, f"Year {yr_idx} field {num_key} is None")
                self.assertTrue(math.isfinite(num_val), f"Year {yr_idx} field {num_key} not finite: {num_val}")

        # 3. Exhaustive recursive validation across entire returned object tree
        _assert_no_none_or_nan(self, res)

    def test_02_simulate_battery_health_with_nan_inputs(self):
        """
        Invokes simulateBatteryHealth({ years: 3, vehicleEfficiencyKmPerKwh: NaN, packCapacityKwh: NaN }).
        Asserts that no NaN appears in any electro-chemical degradation or replacement cost metrics.
        """
        dep_path = json.dumps(str(LIB_DIR / "getDepreciationData.ts"))
        script = f"""
        const dep = jiti({dep_path});
        const res = dep.simulateBatteryHealth({{
            years: 3,
            vehicleEfficiencyKmPerKwh: NaN,
            packCapacityKwh: NaN
        }});
        console.log(JSON.stringify(res));
        """
        res = _eval_ts_node(script)

        self.assertIsInstance(res, dict)
        self.assertEqual(res.get("years"), 3)
        self.assertIn(res.get("chemistry"), ["LFP", "NCM_622", "NCM_811", "NCMA", "NCA"])

        # Electro-chemical metrics
        soh = res.get("sohPct")
        self.assertIsNotNone(soh)
        self.assertTrue(math.isfinite(soh))
        self.assertGreaterEqual(soh, 0.0)
        self.assertLessEqual(soh, 100.0)

        for metric in [
            "equivalentFullCycles",
            "calendarLossPct",
            "cyclicLossPct",
            "totalLossPct",
            "failureRiskPct",
            "winterRangeRetentionPct",
            "usedMarketValuationFactor",
        ]:
            val = res.get(metric)
            self.assertIsNotNone(val, f"Metric {metric} is None (indicates NaN)")
            self.assertTrue(math.isfinite(val), f"Metric {metric} is not finite: {val}")

        # Replacement costs estimate
        repl = res.get("replacementCostEstimate")
        self.assertIsInstance(repl, dict)
        self.assertIsNotNone(repl.get("totalNewInstalledKrw"))
        self.assertGreater(repl["totalNewInstalledKrw"], 0)

        # Full recursive tree validation
        _assert_no_none_or_nan(self, res)

    def test_03_get_price_subsidy_ratio_with_nan_and_adversarial_inputs(self):
        """
        Tests getPriceSubsidyRatio(msrpKrw) with adversarial inputs (NaN, negatives, infinities, boundaries).
        Asserts that output is strictly a valid numeric float/int, never NaN or outside [0.0, 1.0].
        """
        sub_path = json.dumps(str(LIB_DIR / "getSubsidyData.ts"))
        script = f"""
        const sub = jiti({sub_path});
        const results = {{
            ratioNaN: sub.getPriceSubsidyRatio(NaN),
            ratioNegative: sub.getPriceSubsidyRatio(-50000000),
            ratioZero: sub.getPriceSubsidyRatio(0),
            ratioBelow55M: sub.getPriceSubsidyRatio(54999999),
            ratioExact55M: sub.getPriceSubsidyRatio(55000000),
            ratioMidTier: sub.getPriceSubsidyRatio(70000000),
            ratioBelow85M: sub.getPriceSubsidyRatio(84999999),
            ratioExact85M: sub.getPriceSubsidyRatio(85000000),
            ratioAbove85M: sub.getPriceSubsidyRatio(120000000),
            ratioPosInf: sub.getPriceSubsidyRatio(Infinity),
            ratioNegInf: sub.getPriceSubsidyRatio(-Infinity)
        }};
        console.log(JSON.stringify(results));
        """
        res = _eval_ts_node(script)

        # NaN guard must return valid numeric ratio (1.0 default)
        self.assertEqual(res["ratioNaN"], 1.0)
        self.assertEqual(res["ratioNegative"], 1.0)
        self.assertEqual(res["ratioZero"], 1.0)
        self.assertEqual(res["ratioBelow55M"], 1.0)

        # Exact statutory boundaries
        self.assertEqual(res["ratioExact55M"], 0.5)
        self.assertEqual(res["ratioMidTier"], 0.5)
        self.assertEqual(res["ratioBelow85M"], 0.5)
        self.assertEqual(res["ratioExact85M"], 0.0)
        self.assertEqual(res["ratioAbove85M"], 0.0)

        # Infinities & non-finites are caught by !Number.isFinite guard and return 1.0
        self.assertEqual(res["ratioPosInf"], 1.0)
        self.assertEqual(res["ratioNegInf"], 1.0)

        _assert_no_none_or_nan(self, res)

    def test_04_get_daily_reports_normalize_report_adversarial_inputs(self):
        """
        Tests normalizeReport in getDailyReports.ts with adversarial inputs:
        { sentiment_score: NaN, negativity_score: NaN }.
        Asserts that sentiment_score is finite and defaults to a valid positive float.
        """
        rep_path = json.dumps(str(LIB_DIR / "getDailyReports.ts"))
        script = f"""
        const rep = jiti({rep_path});
        const out1 = rep.normalizeReport({{ sentiment_score: NaN, negativity_score: NaN }}, 0);
        const out2 = rep.normalizeReport({{ sentiment_score: -0.88 }}, 1);
        const out3 = rep.normalizeReport({{ negativity_score: 0.94 }}, 2);
        const out4 = rep.normalizeReport({{}}, 3);
        console.log(JSON.stringify({{ out1, out2, out3, out4 }}));
        """
        res = _eval_ts_node(script)

        self.assertIsNotNone(res["out1"]["sentiment_score"])
        self.assertTrue(math.isfinite(res["out1"]["sentiment_score"]))
        self.assertEqual(res["out1"]["sentiment_score"], 0.85)

        self.assertEqual(res["out2"]["sentiment_score"], 0.88)
        self.assertEqual(res["out3"]["sentiment_score"], 0.94)
        self.assertEqual(res["out4"]["sentiment_score"], 0.85)

        _assert_no_none_or_nan(self, res)

    def test_05_calculate_depreciation_adversarial_inputs(self):
        """
        Tests calculateDepreciation with NaN years, NaN mileage, and NaN customPurchasePriceKrw.
        Asserts that outputs are non-negative finite numbers with safe fallbacks.
        """
        dep_path = json.dumps(str(LIB_DIR / "getDepreciationData.ts"))
        script = f"""
        const dep = jiti({dep_path});
        const res = dep.calculateDepreciation({{
            modelId: 'model-3',
            years: NaN,
            mileageKm: NaN,
            customPurchasePriceKrw: NaN
        }});
        console.log(JSON.stringify(res));
        """
        res = _eval_ts_node(script)

        self.assertIsInstance(res, dict)
        self.assertEqual(res.get("years"), 0)
        self.assertEqual(res.get("mileageKm"), 0)
        self.assertGreater(res.get("basePurchasePriceKrw"), 0)
        self.assertGreater(res.get("adjustedResidualPct"), 0)
        self.assertGreater(res.get("estimatedResidualPriceKrw"), 0)

        _assert_no_none_or_nan(self, res)

    def test_06_calculate_subsidy_clawback_adversarial_inputs(self):
        """
        Tests calculateSubsidyClawback with NaN heldMonths.
        Asserts zero NaN/null values and proper tier fallback (tier 1: 70% clawback).
        """
        dep_path = json.dumps(str(LIB_DIR / "getDepreciationData.ts"))
        script = f"""
        const dep = jiti({dep_path});
        const res = dep.calculateSubsidyClawback(NaN, 5000000, 'inter', 6500000);
        console.log(JSON.stringify(res));
        """
        res = _eval_ts_node(script)

        self.assertEqual(res.get("heldMonths"), 0)
        self.assertTrue(math.isfinite(res.get("statutoryClawbackRate")))
        self.assertTrue(math.isfinite(res.get("effectiveClawbackRate")))
        self.assertTrue(math.isfinite(res.get("localClawbackKrw")))
        self.assertEqual(res.get("localClawbackKrw"), 3500000)
        self.assertTrue(math.isfinite(res.get("totalClawbackKrw")))
        self.assertEqual(res.get("totalClawbackKrw"), 3500000)

        _assert_no_none_or_nan(self, res)


# ==============================================================================
# 2. STATIC AST & REGEX ACCESSIBILITY (WCAG AA) VALIDATION
# ==============================================================================

class TestFrontendA11yStaticValidation(unittest.TestCase):
    """Static AST and regex checks across all Next.js TSX files in ev-stealth-web."""

    @classmethod
    def setUpClass(cls):
        if not APP_DIR.is_dir():
            raise FileNotFoundError(f"Missing app directory at {APP_DIR}")
        cls.tsx_files = list(APP_DIR.rglob("*.tsx"))
        if not cls.tsx_files:
            raise ValueError(f"No .tsx files found under {APP_DIR}")

    def test_01_animate_classes_require_motion_reduce(self):
        """
        WCAG 2.1 SC 2.3.3 (Animation from Interactions) Mandate:
        Asserts 0 occurrences of 'animate-pulse' or 'animate-bounce' without 'motion-reduce:animate-none'.
        """
        violations: List[Tuple[str, int, str]] = []

        for p in self.tsx_files:
            content = p.read_text(encoding="utf-8")
            lines = content.splitlines()
            for line_idx, line in enumerate(lines, 1):
                if "animate-pulse" in line or "animate-bounce" in line:
                    if "motion-reduce:animate-none" not in line:
                        violations.append((p.name, line_idx, line.strip()))

        if violations:
            msg = f"Found {len(violations)} animation occurrences without motion-reduce:animate-none:\n"
            for fn, ln, text in violations:
                msg += f"  - {fn}:{ln} -> {text}\n"
            self.fail(msg)

        self.assertEqual(len(violations), 0)

    def test_02_no_progressbar_nested_inside_button(self):
        """
        WAI-ARIA 1.2 Structure Mandate:
        Asserts 0 occurrences of role="progressbar" inside role="button" or <button>.
        Nesting interactive or live progressbars inside buttons confuses assistive technologies.
        """
        violations: List[Tuple[str, str]] = []

        for p in self.tsx_files:
            content = p.read_text(encoding="utf-8")
            # Parse tag hierarchy tracking ancestor roles
            tags = re.findall(r"<(/?[a-zA-Z0-9]+)([^>]*)>", content)
            role_stack: List[Tuple[str, Optional[str]]] = []

            for tag_name, attrs in tags:
                if tag_name.startswith("/"):
                    t = tag_name[1:]
                    if role_stack and role_stack[-1][0] == t:
                        role_stack.pop()
                elif attrs.endswith("/"):
                    # Self-closing tag
                    role_m = re.search(r'role=[\"\x27]([^\s\"\x27]+)[\"\x27]', attrs)
                    role = role_m.group(1) if role_m else None
                    if role == "progressbar":
                        for parent_tag, parent_role in role_stack:
                            if parent_role == "button" or parent_tag == "button":
                                violations.append((p.name, f"self-closing <{tag_name}> role=progressbar inside <{parent_tag}> role={parent_role}"))
                else:
                    role_m = re.search(r'role=[\"\x27]([^\s\"\x27]+)[\"\x27]', attrs)
                    role = role_m.group(1) if role_m else None
                    if role == "progressbar":
                        for parent_tag, parent_role in role_stack:
                            if parent_role == "button" or parent_tag == "button":
                                violations.append((p.name, f"<{tag_name}> role=progressbar inside <{parent_tag}> role={parent_role}"))
                    role_stack.append((tag_name, role))

        if violations:
            msg = f"Found {len(violations)} nested progressbar inside button violations:\n"
            for fn, desc in violations:
                msg += f"  - {fn}: {desc}\n"
            self.fail(msg)

        self.assertEqual(len(violations), 0)

    def test_03_all_inputs_with_id_have_associated_labels(self):
        """
        WCAG 2.1 SC 1.3.1 (Info and Relationships) & SC 4.1.2 (Name, Role, Value):
        Asserts that all <input id=...> have a matching <label htmlFor=...> in the same file.
        """
        missing_labels: List[Tuple[str, str]] = []

        for p in self.tsx_files:
            content = p.read_text(encoding="utf-8")
            inputs = re.findall(r"<input[^>]*>", content, re.DOTALL)
            for inp in inputs:
                m = re.search(r'id=[\"\x27]([^\s\"\x27]+)[\"\x27]', inp)
                if m:
                    input_id = m.group(1)
                    has_label = bool(
                        re.search(rf'htmlFor=[\"\x27]{re.escape(input_id)}[\"\x27]', content)
                        or re.search(rf'htmlFor=\{{{re.escape(input_id)}\}}', content)
                    )
                    if not has_label:
                        missing_labels.append((p.name, input_id))

        if missing_labels:
            msg = f"Found {len(missing_labels)} inputs with id but missing matching label htmlFor:\n"
            for fn, input_id in missing_labels:
                msg += f"  - {fn}: id='{input_id}'\n"
            self.fail(msg)

        self.assertEqual(len(missing_labels), 0)

    def test_04_mobile_drawer_handles_escape_key(self):
        """
        WCAG 2.1 SC 2.1.2 (No Keyboard Trap) & WAI-ARIA Dialog/Disclosure Design Pattern:
        Asserts that the mobile drawer in layout.tsx listens for the 'Escape' key to close itself.
        """
        layout_path = APP_DIR / "layout.tsx"
        self.assertTrue(layout_path.is_file(), f"layout.tsx not found at {layout_path}")

        content = layout_path.read_text(encoding="utf-8")

        # Must handle Escape key
        has_escape_handler = bool(
            "Escape" in content
            and ("mobile-nav-drawer" in content or "details" in content)
        )
        self.assertTrue(
            has_escape_handler,
            "layout.tsx must contain an Escape key listener to close mobile navigation drawer"
        )


if __name__ == "__main__":
    unittest.main()
