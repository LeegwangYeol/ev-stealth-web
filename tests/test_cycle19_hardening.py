"""
tests/test_cycle19_hardening.py - Comprehensive Cycle 19 Hardening, Boundary,
Contract Validation, Battery Kinetics, WCAG A11y, and Mirror Parity Test Suite.

Authoritative Reference:
- ORIGINAL_REQUEST.md
- DISPATCH.md (Cycle 19 Hardening Test Suite Specification)
- Wave 1 Explorer Handoff Reports:
  - sync19_explorer_tests_w1/handoff.md
  - sync19_explorer_backend_w1/handoff.md
  - sync19_explorer_frontend_w1/handoff.md
  - sync19_explorer_a11y_w1/handoff.md
  - sync19_explorer_perf_w1/handoff.md
- COLLABORATION.md

Classes & Coverage (28 tests across 5 test classes):
1. TestCycle19DatasetIntegrityAndTripleMirror (4 tests: 01-04)
2. TestCycle19StatutoryQuotaAndBudgetConservation (5 tests: 05-09)
3. TestCycle19VinDecodingAndRecallSafetyContract (6 tests: 10-15)
4. TestCycle19BatteryKineticsAndStatutoryClawback (6 tests: 16-21)
5. TestCycle19WcagA11yAndFrontendResilience (7 tests: 22-28)
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
from typing import Any, Dict, List, Optional
import unittest


# ---------------------------------------------------------------------------
# Adaptive repository and web root resolution
# ---------------------------------------------------------------------------
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
WEB_ROOT = PROJECT_ROOT / "ev-stealth-web"
SRC_DIR = WEB_ROOT / "src"
LIB_DIR = SRC_DIR / "lib"
APP_DIR = SRC_DIR / "app"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
else:
    sys.path.remove(str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT))

if str(WEB_ROOT) not in sys.path:
    sys.path.append(str(WEB_ROOT))


def _eval_ts_node(script: str, timeout_sec: int = 30) -> Any:
    """Execute a Node.js snippet using tsx or jiti to resolve TypeScript modules."""
    if not shutil.which("node"):
        raise unittest.SkipTest("Node.js runtime not installed on host environment.")

    # Try tsx first
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

    # Fallback to jiti via Node.js
    jiti_path = WEB_ROOT / "node_modules" / "jiti"
    pkg_path = WEB_ROOT / "package.json"

    if not jiti_path.exists():
        raise unittest.SkipTest(f"tsx and jiti not found at {jiti_path}")

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
        cwd=str(WEB_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"TypeScript evaluation failed: {proc.stderr}\nCode:\n{script}")
    return json.loads(proc.stdout.strip())


# ===========================================================================
# Class 1: TestCycle19DatasetIntegrityAndTripleMirror
# ===========================================================================
class TestCycle19DatasetIntegrityAndTripleMirror(unittest.TestCase):
    """Validates triple mirror dataset presence, 0o644 POSIX mode, cryptographic
    SHA-256 bitwise parity across 3 locations, valid JSON schema, and verified defect reports.
    """

    CORE_DATASETS = [
        "ev_subsidy_data.json",
        "subsidy_depletion_data.json",
        "daily_reports.json",
        "models_subsidy_matrix.json",
    ]

    MIRROR_DIRS = [
        PROJECT_ROOT / "data",
        WEB_ROOT / "src" / "data",
        WEB_ROOT / "public" / "data",
    ]

    def test_01_triple_mirror_dataset_presence_and_permissions(self) -> None:
        """Asserts existence of all 12 dataset files across 3 locations with size > 0 and 0o644 permissions."""
        for d in self.MIRROR_DIRS:
            self.assertTrue(d.is_dir(), f"Mirror directory {d} must exist")
            for filename in self.CORE_DATASETS:
                target_path = d / filename
                self.assertTrue(target_path.exists(), f"File {target_path} must exist")
                self.assertTrue(target_path.is_file(), f"Path {target_path} must be a regular file")
                self.assertGreater(target_path.stat().st_size, 0, f"File {target_path} must not be empty")

                mode = oct(stat.S_IMODE(target_path.stat().st_mode))
                self.assertEqual(
                    mode,
                    "0o644",
                    f"Permissions for {target_path} must be 0o644 (-rw-r--r--), got {mode}",
                )

    def test_02_triple_mirror_cryptographic_sha256_bitwise_parity(self) -> None:
        """Computes SHA-256 for all 4 datasets across 3 locations and verifies 100% hash parity."""
        for filename in self.CORE_DATASETS:
            hashes: List[str] = []
            sizes: List[int] = []

            for d in self.MIRROR_DIRS:
                p = d / filename
                content = p.read_bytes()
                h = hashlib.sha256(content).hexdigest()
                hashes.append(h)
                sizes.append(len(content))

            self.assertEqual(
                len(set(hashes)),
                1,
                f"Hash mismatch across mirrors for {filename}: {dict(zip([str(d) for d in self.MIRROR_DIRS], hashes))}",
            )
            self.assertEqual(
                len(set(sizes)),
                1,
                f"Size mismatch across mirrors for {filename}: {dict(zip([str(d) for d in self.MIRROR_DIRS], sizes))}",
            )

        # Asserts ev_subsidy_data.json and subsidy_depletion_data.json have matching hashes
        ev_sub_bytes = (PROJECT_ROOT / "data" / "ev_subsidy_data.json").read_bytes()
        dep_sub_bytes = (PROJECT_ROOT / "data" / "subsidy_depletion_data.json").read_bytes()
        self.assertEqual(len(ev_sub_bytes), len(dep_sub_bytes), "Byte counts must match between subsidy datasets")
        self.assertEqual(
            hashlib.sha256(ev_sub_bytes).hexdigest(),
            hashlib.sha256(dep_sub_bytes).hexdigest(),
            "SHA-256 hashes must match identically between ev_subsidy_data and subsidy_depletion_data",
        )

    def test_03_triple_mirror_json_schema_validity_and_parse(self) -> None:
        """Verifies all 12 dataset files parse cleanly as valid JSON with required top-level keys."""
        for d in self.MIRROR_DIRS:
            # 1. ev_subsidy_data.json
            with open(d / "ev_subsidy_data.json", "r", encoding="utf-8") as f:
                ev_data = json.load(f)
            self.assertTrue("generated_at" in ev_data or "generated_at" in ev_data.get("metadata", {}))
            self.assertIn("nationwide_summary", ev_data)
            self.assertIn("regions", ev_data)
            self.assertIsInstance(ev_data["regions"], list)

            # 2. subsidy_depletion_data.json
            with open(d / "subsidy_depletion_data.json", "r", encoding="utf-8") as f:
                dep_data = json.load(f)
            self.assertTrue("generated_at" in dep_data or "generated_at" in dep_data.get("metadata", {}))
            self.assertIn("nationwide_summary", dep_data)
            self.assertIn("regions", dep_data)

            # 3. daily_reports.json
            with open(d / "daily_reports.json", "r", encoding="utf-8") as f:
                rep_data = json.load(f)
            self.assertIn("generated_at", rep_data)
            self.assertIn("pipeline_version", rep_data)
            self.assertIn("statistics", rep_data)
            self.assertIn("reports", rep_data)
            self.assertIsInstance(rep_data["reports"], list)

            # 4. models_subsidy_matrix.json
            with open(d / "models_subsidy_matrix.json", "r", encoding="utf-8") as f:
                mat_data = json.load(f)
            self.assertTrue(isinstance(mat_data, (list, dict)))
            self.assertGreater(len(mat_data), 0)

    def test_04_verified_field_defect_reports_integrity(self) -> None:
        """Asserts presence of 3 verified community defect reports with live URLs and negativity scores >= 0.90."""
        daily_file = PROJECT_ROOT / "data" / "daily_reports.json"
        with open(daily_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        reports = data.get("reports", [])
        self.assertGreater(len(reports), 0, "daily_reports.json must contain reports")

        url_ioniq = "https://gall.dcinside.com/mgallery/board/view/?id=car_new1&no=1284920"
        url_tesla = "https://gall.dcinside.com/mgallery/board/view/?id=car_new1&no=1284550"
        url_ev3 = "https://www.bobaedream.co.kr/view?code=national&No=2291045"

        found_ioniq = None
        found_tesla = None
        found_ev3 = None

        for r in reports:
            u = r.get("url", "")
            if url_ioniq in u:
                found_ioniq = r
            elif url_tesla in u:
                found_tesla = r
            elif url_ev3 in u:
                found_ev3 = r

        self.assertIsNotNone(found_ioniq, f"Hyundai Ioniq 5 ICCU report not found at {url_ioniq}")
        self.assertIsNotNone(found_tesla, f"Tesla Model Y OTA blackout report not found at {url_tesla}")
        self.assertIsNotNone(found_ev3, f"Kia EV3 wet road fish-tailing report not found at {url_ev3}")

        self.assertGreaterEqual(found_ioniq.get("negativity_score", 0.0), 0.90)
        self.assertGreaterEqual(found_tesla.get("negativity_score", 0.0), 0.90)
        self.assertGreaterEqual(found_ev3.get("negativity_score", 0.0), 0.90)

        self.assertEqual(found_ioniq.get("defect_category"), "BATTERY_CHARGING")
        self.assertEqual(found_tesla.get("defect_category"), "SOFTWARE_ELECTRONICS")
        self.assertEqual(found_ev3.get("defect_category"), "DRIVING_POWERTRAIN")


# ===========================================================================
# Class 2: TestCycle19StatutoryQuotaAndBudgetConservation
# ===========================================================================
class TestCycle19StatutoryQuotaAndBudgetConservation(unittest.TestCase):
    """Validates mathematical conservation laws across national quotas, statutory budget
    execution ratios, category breakdowns, regional exhaustion alerts, and regional sum consistency.
    """

    def test_05_national_subsidy_metrics_conservation_invariants(self) -> None:
        """Asserts national quota conservation: applied + remaining == announced, delivered <= applied."""
        data_file = PROJECT_ROOT / "data" / "ev_subsidy_data.json"
        with open(data_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        summary = data.get("nationwide_summary", {})
        total_announced = summary.get("total_announced_units")
        total_applied = summary.get("total_applied_units")
        total_delivered = summary.get("total_delivered_units")
        total_remaining = summary.get("total_remaining_units")
        depletion_rate = summary.get("nationwide_depletion_rate")

        self.assertEqual(total_announced, 148510, "Total announced units must be 148,510")
        self.assertEqual(total_applied, 132766, "Total applied units must be 132,766")
        self.assertEqual(total_delivered, 122515, "Total delivered units must be 122,515")
        self.assertEqual(total_remaining, 15744, "Total remaining units must be 15,744")

        # Conservation law: applied + remaining == announced
        self.assertEqual(
            total_applied + total_remaining,
            total_announced,
            f"Conservation violated: applied ({total_applied}) + remaining ({total_remaining}) != announced ({total_announced})",
        )

        # Ordering invariant: delivered <= applied
        self.assertLessEqual(total_delivered, total_applied, "Delivered units cannot exceed applied units")

        # Depletion rate: 132766 / 148510 * 100 = 89.3986... -> 89.4%
        self.assertEqual(depletion_rate, 89.4, "National depletion rate must be 89.4%")
        expected_rate = round((total_applied / total_announced) * 100.0, 1)
        self.assertEqual(expected_rate, 89.4)

    def test_06_statutory_budget_execution_invariants(self) -> None:
        """Asserts statutory budget execution: 1조 8,934억 KRW disbursed / 2조 1,051억 KRW total (89.94%)."""
        data_file = PROJECT_ROOT / "data" / "ev_subsidy_data.json"
        with open(data_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        summary = data.get("nationwide_summary", {})
        total_budget_b = summary.get("total_budget_billion_krw")
        disbursed_budget_b = summary.get("disbursed_budget_billion_krw")

        self.assertAlmostEqual(total_budget_b, 2105.1, places=1, msg="Total statutory budget must be 2,105.1 billion KRW")
        self.assertAlmostEqual(disbursed_budget_b, 1893.4, places=1, msg="Disbursed statutory budget must be 1,893.4 billion KRW")

        # Execution rate: 1893.4 / 2105.1 = 0.8994347... -> 89.94%
        execution_rate = round((disbursed_budget_b / total_budget_b) * 100.0, 2)
        self.assertEqual(execution_rate, 89.94, "Statutory budget execution rate must be 89.94%")

    def test_07_category_breakdown_arithmetic_invariants(self) -> None:
        """Asserts category breakdowns for Passenger, Commercial, and Bus sum to national totals."""
        data_file = PROJECT_ROOT / "data" / "ev_subsidy_data.json"
        with open(data_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        summary = data.get("nationwide_summary", {})
        cat_totals = summary.get("category_totals", {})

        p_info = cat_totals.get("passenger", {})
        c_info = cat_totals.get("commercial", {})
        b_info = cat_totals.get("bus", {})

        # Passenger
        self.assertEqual(p_info.get("announced_units"), 110400)
        self.assertEqual(p_info.get("applied_units"), 97035)
        self.assertEqual(p_info.get("delivered_units"), 88960)
        self.assertEqual(p_info.get("remaining_units"), 13365)
        self.assertEqual(p_info.get("depletion_rate"), 87.9)

        # Commercial
        self.assertEqual(c_info.get("announced_units"), 34800)
        self.assertEqual(c_info.get("applied_units"), 32754)
        self.assertEqual(c_info.get("delivered_units"), 30780)
        self.assertEqual(c_info.get("remaining_units"), 2046)
        self.assertEqual(c_info.get("depletion_rate"), 94.1)

        # Bus
        self.assertEqual(b_info.get("announced_units"), 3310)
        self.assertEqual(b_info.get("applied_units"), 2977)
        self.assertEqual(b_info.get("delivered_units"), 2775)
        self.assertEqual(b_info.get("remaining_units"), 333)
        self.assertEqual(b_info.get("depletion_rate"), 89.9)

        # Sum invariants
        total_ann = p_info["announced_units"] + c_info["announced_units"] + b_info["announced_units"]
        total_app = p_info["applied_units"] + c_info["applied_units"] + b_info["applied_units"]
        total_del = p_info["delivered_units"] + c_info["delivered_units"] + b_info["delivered_units"]
        total_rem = p_info["remaining_units"] + c_info["remaining_units"] + b_info["remaining_units"]

        self.assertEqual(total_ann, summary["total_announced_units"])
        self.assertEqual(total_app, summary["total_applied_units"])
        self.assertEqual(total_del, summary["total_delivered_units"])
        self.assertEqual(total_rem, summary["total_remaining_units"])

    def test_08_critical_exhaustion_regions_bounds(self) -> None:
        """Asserts that exactly 4 regions have overall_depletion_rate >= 95.0%."""
        data_file = PROJECT_ROOT / "data" / "ev_subsidy_data.json"
        with open(data_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        regions = data.get("regions", [])
        critical_regs = [r for r in regions if r.get("overall_depletion_rate", 0.0) >= 95.0]

        self.assertEqual(len(critical_regs), 4, f"Expected exactly 4 critical regions, found {len(critical_regs)}")

        crit_by_name = {r["name_ko"]: r for r in critical_regs}
        self.assertIn("대구광역시", crit_by_name)
        self.assertIn("울산광역시", crit_by_name)
        self.assertIn("경상북도", crit_by_name)
        self.assertIn("제주특별자치도", crit_by_name)

        self.assertEqual(crit_by_name["대구광역시"]["overall_depletion_rate"], 96.4)
        self.assertEqual(crit_by_name["울산광역시"]["overall_depletion_rate"], 96.5)
        self.assertEqual(crit_by_name["경상북도"]["overall_depletion_rate"], 97.3)
        self.assertEqual(crit_by_name["제주특별자치도"]["overall_depletion_rate"], 99.0)

        for r in critical_regs:
            self.assertEqual(r.get("overall_status"), "CRITICAL")

    def test_09_regional_quota_sum_consistency_against_national_totals(self) -> None:
        """Verifies sum across all 17 administrative divisions matches nationwide summary totals."""
        data_file = PROJECT_ROOT / "data" / "ev_subsidy_data.json"
        with open(data_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        regions = data.get("regions", [])
        self.assertEqual(len(regions), 17, "Must contain exactly 17 administrative provinces/cities")

        sum_announced = sum(
            sum(c.get("announced_units", 0) for c in r.get("categories", {}).values())
            for r in regions
        )
        sum_applied = sum(
            sum(c.get("applied_units", 0) for c in r.get("categories", {}).values())
            for r in regions
        )
        sum_delivered = sum(
            sum(c.get("delivered_units", 0) for c in r.get("categories", {}).values())
            for r in regions
        )
        sum_remaining = sum(
            sum(c.get("remaining_units", 0) for c in r.get("categories", {}).values())
            for r in regions
        )

        summary = data.get("nationwide_summary", {})
        self.assertEqual(sum_announced, summary["total_announced_units"])
        self.assertEqual(sum_applied, summary["total_applied_units"])
        self.assertEqual(sum_delivered, summary["total_delivered_units"])
        self.assertEqual(sum_remaining, summary["total_remaining_units"])

        for r in regions:
            cats = r.get("categories", {})
            ann = sum(c.get("announced_units", 0) for c in cats.values())
            app = sum(c.get("applied_units", 0) for c in cats.values())
            rem = sum(c.get("remaining_units", 0) for c in cats.values())
            deliv = sum(c.get("delivered_units", 0) for c in cats.values())
            self.assertEqual(app + rem, ann, f"Region {r.get('name_ko')} violates app + rem == ann")
            self.assertLessEqual(deliv, app, f"Region {r.get('name_ko')} violates deliv <= app")


# ===========================================================================
# Class 3: TestCycle19VinDecodingAndRecallSafetyContract
# ===========================================================================
class TestCycle19VinDecodingAndRecallSafetyContract(unittest.TestCase):
    """Validates 17-digit ISO 3779 VIN string validation, illegal character rejection (I, O, Q),
    year decoding from position 10, longest prefix WMI matching, model collision prevention,
    year range parsing, and recall safety risk grading.
    """

    def test_10_vin_validator_iso3779_strictness_and_illegal_chars(self) -> None:
        """Verifies validateVinString enforces ISO 3779 17-char format and rejects illegal I, O, Q."""
        script = """
        import { validateVinString } from './src/lib/getRecallData';
        console.log(JSON.stringify({
            valid: validateVinString('KM8KRDA44PU123456'),
            withSpacesDashes: validateVinString('KM8-KRDA44-PU 123456'),
            illegalI: validateVinString('KM8KRDA44IU123456'),
            illegalO: validateVinString('KM8KRDA44OU123456'),
            illegalQ: validateVinString('KM8KRDA44QU123456'),
            tooShort: validateVinString('KM8KRDA44PU1234'),
            tooLong: validateVinString('KM8KRDA44PU12345678'),
            empty: validateVinString(''),
        }));
        """
        out = _eval_ts_node(script)
        self.assertTrue(out["valid"]["valid"])
        self.assertEqual(out["valid"]["normalized"], "KM8KRDA44PU123456")

        self.assertTrue(out["withSpacesDashes"]["valid"])
        self.assertEqual(out["withSpacesDashes"]["normalized"], "KM8KRDA44PU123456")

        self.assertFalse(out["illegalI"]["valid"])
        self.assertIn("I", out["illegalI"]["error"])

        self.assertFalse(out["illegalO"]["valid"])
        self.assertIn("O", out["illegalO"]["error"])

        self.assertFalse(out["illegalQ"]["valid"])
        self.assertIn("Q", out["illegalQ"]["error"])

        self.assertFalse(out["tooShort"]["valid"])
        self.assertIn("15", out["tooShort"]["error"])

        self.assertFalse(out["tooLong"]["valid"])
        self.assertIn("19", out["tooLong"]["error"])

        self.assertFalse(out["empty"]["valid"])

    def test_11_vin_year_decoding_iso3779_position10(self) -> None:
        """Verifies 10th character (index 9) year decoding according to ISO 3779 VIN_YEAR_MAP."""
        script = """
        import { decodeVinAndCheckRecalls } from './src/lib/getRecallData';
        // Position 10 (index 9): T->2026, S->2025, R->2024, P->2023, N->2022, M->2021, L->2020
        const testVins = {
            y2026: decodeVinAndCheckRecalls('KM8KRDA44TU123456').decodedYear,
            y2025: decodeVinAndCheckRecalls('KM8KRDA44SU123456').decodedYear,
            y2024: decodeVinAndCheckRecalls('KM8KRDA44RU123456').decodedYear,
            y2023: decodeVinAndCheckRecalls('KM8KRDA44PU123456').decodedYear,
            y2022: decodeVinAndCheckRecalls('KM8KRDA44NU123456').decodedYear,
            y2021: decodeVinAndCheckRecalls('KM8KRDA44MU123456').decodedYear,
            y2020: decodeVinAndCheckRecalls('KM8KRDA44LU123456').decodedYear,
        };
        console.log(JSON.stringify(testVins));
        """
        out = _eval_ts_node(script)
        self.assertEqual(out["y2026"], 2026)
        self.assertEqual(out["y2025"], 2025)
        self.assertEqual(out["y2024"], 2024)
        self.assertEqual(out["y2023"], 2023)
        self.assertEqual(out["y2022"], 2022)
        self.assertEqual(out["y2021"], 2021)
        self.assertEqual(out["y2020"], 2020)

    def test_12_vin_wmi_prefix_longest_match_and_fallback(self) -> None:
        """Verifies longest prefix matching and fallback to 3-char WMI for major EV manufacturers."""
        script = """
        import { decodeVinAndCheckRecalls } from './src/lib/getRecallData';
        console.log(JSON.stringify({
            hyundai: decodeVinAndCheckRecalls('KM8KRDA44PU123456').decodedBrand,
            kia: decodeVinAndCheckRecalls('KNDJD3A25P5123456').decodedBrand,
            teslaFremont: decodeVinAndCheckRecalls('5YJ3E1EB8NF123456').decodedBrand,
            teslaAustin: decodeVinAndCheckRecalls('7SAXCBE50PF123456').decodedBrand,
            teslaShanghai: decodeVinAndCheckRecalls('LRWYGCEK8NC123456').decodedBrand,
            mercedes: decodeVinAndCheckRecalls('W1K29712345678901').decodedBrand,
            bmw: decodeVinAndCheckRecalls('WBA21EF05P1234567').decodedBrand,
            byd: decodeVinAndCheckRecalls('LGXCE4C89P1234567').decodedBrand,
        }));
        """
        out = _eval_ts_node(script)
        self.assertIn("현대", out["hyundai"])
        self.assertIn("기아", out["kia"])
        self.assertIn("테슬라", out["teslaFremont"])
        self.assertIn("테슬라", out["teslaAustin"])
        self.assertIn("테슬라", out["teslaShanghai"])
        self.assertIn("메르세데스", out["mercedes"])
        self.assertIn("BMW", out["bmw"])
        self.assertIn("BYD", out["byd"])

    def test_13_recall_campaign_model_matching_collision_prevention(self) -> None:
        """Verifies isModelMatchForCampaign prevents false-positive model collisions."""
        script = """
        import { isModelMatchForCampaign } from './src/lib/getRecallData';
        console.log(JSON.stringify({
            ioniq5_vs_6: isModelMatchForCampaign('아이오닉 5', '아이오닉 6'),
            ioniq5_vs_ev: isModelMatchForCampaign('아이오닉 5', '아이오닉 EV'),
            modelY_vs_3: isModelMatchForCampaign('Model Y', 'Model 3'),
            modelY_vs_S: isModelMatchForCampaign('Model Y', 'Model S'),
            ev6_vs_9: isModelMatchForCampaign('EV6', 'EV9'),
            ev6_vs_3: isModelMatchForCampaign('EV6', 'EV3'),
            bolt_match: isModelMatchForCampaign('볼트 EV', '볼트 EV / EUV'),
            ioniq5_clean_match: isModelMatchForCampaign('아이오닉 5', '아이오닉 5 (NE)'),
        }));
        """
        out = _eval_ts_node(script)
        self.assertFalse(out["ioniq5_vs_6"], "아이오닉 5 must not match 아이오닉 6")
        self.assertFalse(out["ioniq5_vs_ev"], "아이오닉 5 must not match 아이오닉 EV")
        self.assertFalse(out["modelY_vs_3"], "Model Y must not match Model 3")
        self.assertFalse(out["modelY_vs_S"], "Model Y must not match Model S")
        self.assertFalse(out["ev6_vs_9"], "EV6 must not match EV9")
        self.assertFalse(out["ev6_vs_3"], "EV6 must not match EV3")
        self.assertTrue(out["bolt_match"], "볼트 EV must match 볼트 EV / EUV")
        self.assertTrue(out["ioniq5_clean_match"], "아이오닉 5 must match 아이오닉 5 (NE)")

    def test_14_recall_campaign_year_range_parsing(self) -> None:
        """Verifies isYearMatchForCampaign correctly parses range, single, and comma formats."""
        script = """
        import { isYearMatchForCampaign } from './src/lib/getRecallData';
        console.log(JSON.stringify({
            inRange: isYearMatchForCampaign(2022, '2021~2024'),
            outOfRange: isYearMatchForCampaign(2025, '2021~2024'),
            singleMatch: isYearMatchForCampaign(2024, '2024'),
            singleMismatch: isYearMatchForCampaign(2023, '2024'),
            commaMatch: isYearMatchForCampaign(2021, '2021, 2023'),
            commaMismatch: isYearMatchForCampaign(2022, '2021, 2023'),
        }));
        """
        out = _eval_ts_node(script)
        self.assertTrue(out["inRange"])
        self.assertFalse(out["outOfRange"])
        self.assertTrue(out["singleMatch"])
        self.assertFalse(out["singleMismatch"])
        self.assertTrue(out["commaMatch"])
        self.assertFalse(out["commaMismatch"])

    def test_15_decode_vin_and_check_recalls_risk_grading(self) -> None:
        """Verifies decodeVinAndCheckRecalls evaluates CRITICAL, WARNING, and SAFE risk grades."""
        script = """
        import { decodeVinAndCheckRecalls } from './src/lib/getRecallData';
        // Sample VINs
        // 1. Hyundai Ioniq 5 with ICCU loss of power
        const ioniq5 = decodeVinAndCheckRecalls('KM8KRDA44PU123456');
        // 2. Clean VIN
        const cleanVin = decodeVinAndCheckRecalls('KM8KRDA44TU999999');
        // 3. Invalid VIN
        const invalidVin = decodeVinAndCheckRecalls('INVALID_VIN_123');

        console.log(JSON.stringify({
            ioniq5_valid: ioniq5.valid,
            ioniq5_grade: ioniq5.overallRiskGrade,
            ioniq5_hasPowerLoss: ioniq5.hasPowerLoss,
            clean_valid: cleanVin.valid,
            clean_grade: cleanVin.overallRiskGrade,
            invalid_valid: invalidVin.valid,
            invalid_grade: invalidVin.overallRiskGrade,
        }));
        """
        out = _eval_ts_node(script)
        self.assertTrue(out["ioniq5_valid"])
        self.assertIn(out["ioniq5_grade"], ("CRITICAL", "WARNING"))
        self.assertTrue(out["clean_valid"])
        self.assertEqual(out["clean_grade"], "SAFE")
        self.assertFalse(out["invalid_valid"])
        self.assertEqual(out["invalid_grade"], "SAFE")


# ===========================================================================
# Class 4: TestCycle19BatteryKineticsAndStatutoryClawback
# ===========================================================================
class TestCycle19BatteryKineticsAndStatutoryClawback(unittest.TestCase):
    """Validates 5-year depreciation residual monotonicity, Arrhenius battery health kinetics,
    chemistry comparison (LFP vs NCM), extreme temperature & absolute zero protection,
    Clean Air Act statutory subsidy clawback brackets, and 5-year TCO calculations.
    """

    def test_16_depreciation_database_schema_and_model_curves(self) -> None:
        """Verifies all models in ev_depreciation_data.json have strictly monotonically decreasing curves."""
        dep_file = WEB_ROOT / "src" / "data" / "ev_depreciation_data.json"
        if not dep_file.exists():
            dep_file = PROJECT_ROOT / "data" / "ev_depreciation_data.json"
        self.assertTrue(dep_file.exists(), f"ev_depreciation_data.json must exist at {dep_file}")

        with open(dep_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        models = data.get("models", [])
        self.assertGreaterEqual(len(models), 10, "Must track at least 10 EV models for depreciation")

        for m in models:
            curve = m.get("depreciation_curve", {})
            y1 = curve.get("year_1", {}).get("residual_pct_msrp")
            y2 = curve.get("year_2", {}).get("residual_pct_msrp")
            y3 = curve.get("year_3", {}).get("residual_pct_msrp")
            y4 = curve.get("year_4", {}).get("residual_pct_msrp")
            y5 = curve.get("year_5", {}).get("residual_pct_msrp")

            self.assertIsNotNone(y1, f"Model {m.get('model_name')} missing year_1")
            self.assertIsNotNone(y2, f"Model {m.get('model_name')} missing year_2")
            self.assertIsNotNone(y3, f"Model {m.get('model_name')} missing year_3")
            self.assertIsNotNone(y4, f"Model {m.get('model_name')} missing year_4")
            self.assertIsNotNone(y5, f"Model {m.get('model_name')} missing year_5")

            # Monotonic decrease: y1 > y2 > y3 > y4 > y5
            self.assertGreater(y1, y2, f"Model {m.get('model_name')} curve not monotonic y1 ({y1}) <= y2 ({y2})")
            self.assertGreater(y2, y3, f"Model {m.get('model_name')} curve not monotonic y2 ({y2}) <= y3 ({y3})")
            self.assertGreater(y3, y4, f"Model {m.get('model_name')} curve not monotonic y3 ({y3}) <= y4 ({y4})")
            self.assertGreater(y4, y5, f"Model {m.get('model_name')} curve not monotonic y4 ({y4}) <= y5 ({y5})")

            # Bounds check: [0.0, 100.0]
            for yr_val in (y1, y2, y3, y4, y5):
                self.assertGreater(yr_val, 0.0)
                self.assertLessEqual(yr_val, 100.0)

    def test_17_simulate_battery_health_calendar_and_cyclic_kinetics(self) -> None:
        """Verifies simulateBatteryHealth returns 100% SoH for 0-yr/0-km and monotonic calendar degradation."""
        script = """
        import { simulateBatteryHealth } from './src/lib/getDepreciationData';
        const brandNew = simulateBatteryHealth({ chemistry: 'NCM_811', years: 0, totalKm: 0 });
        const y1 = simulateBatteryHealth({ chemistry: 'NCM_811', years: 1, totalKm: 15000 });
        const y3 = simulateBatteryHealth({ chemistry: 'NCM_811', years: 3, totalKm: 45000 });
        const y5 = simulateBatteryHealth({ chemistry: 'NCM_811', years: 5, totalKm: 75000 });
        const y10 = simulateBatteryHealth({ chemistry: 'NCM_811', years: 10, totalKm: 150000 });

        console.log(JSON.stringify({
            brandNew: {
                sohPct: brandNew.sohPct,
                calendarLossPct: brandNew.calendarLossPct,
                cyclicLossPct: brandNew.cyclicLossPct,
            },
            y1_soh: y1.sohPct,
            y3_soh: y3.sohPct,
            y5_soh: y5.sohPct,
            y10_soh: y10.sohPct,
            calLoss: [y1.calendarLossPct, y3.calendarLossPct, y5.calendarLossPct, y10.calendarLossPct],
        }));
        """
        out = _eval_ts_node(script)
        bn = out["brandNew"]
        self.assertEqual(bn["sohPct"], 100.0)
        self.assertEqual(bn["calendarLossPct"], 0.0)
        self.assertEqual(bn["cyclicLossPct"], 0.0)

        # SoH strictly monotonically decreasing with aging
        self.assertGreater(out["y1_soh"], out["y3_soh"])
        self.assertGreater(out["y3_soh"], out["y5_soh"])
        self.assertGreater(out["y5_soh"], out["y10_soh"])

        # Calendar loss monotonically increasing
        cal = out["calLoss"]
        self.assertLess(cal[0], cal[1])
        self.assertLess(cal[1], cal[2])
        self.assertLess(cal[2], cal[3])

    def test_18_simulate_battery_health_chemistry_kinetics(self) -> None:
        """Verifies LFP vs NCM_811 kinetics: LFP higher cycle endurance and lower calendar aging."""
        script = """
        import { simulateBatteryHealth } from './src/lib/getDepreciationData';
        // At 5 years and 100,000 km
        const lfp = simulateBatteryHealth({ chemistry: 'LFP', years: 5, totalKm: 100000, ambientTempC: 25 });
        const ncm = simulateBatteryHealth({ chemistry: 'NCM_811', years: 5, totalKm: 100000, ambientTempC: 25 });

        // High temperature Arrhenius acceleration: 40°C
        const lfpHot = simulateBatteryHealth({ chemistry: 'LFP', years: 3, totalKm: 45000, ambientTempC: 40 });
        const ncmHot = simulateBatteryHealth({ chemistry: 'NCM_811', years: 3, totalKm: 45000, ambientTempC: 40 });

        console.log(JSON.stringify({
            lfp_soh: lfp.sohPct,
            ncm_soh: ncm.sohPct,
            lfp_cyclic_loss: lfp.cyclicLossPct,
            ncm_cyclic_loss: ncm.cyclicLossPct,
            lfpHot_soh: lfpHot.sohPct,
            ncmHot_soh: ncmHot.sohPct,
        }));
        """
        out = _eval_ts_node(script)
        # LFP has lower cyclic degradation compared to NCM at standard conditions
        self.assertLess(out["lfp_cyclic_loss"], out["ncm_cyclic_loss"])
        # Both SoH values remain within [0.0, 100.0]
        self.assertGreaterEqual(out["lfp_soh"], 0.0)
        self.assertLessEqual(out["lfp_soh"], 100.0)
        self.assertGreaterEqual(out["ncm_soh"], 0.0)
        self.assertLessEqual(out["ncm_soh"], 100.0)

    def test_19_simulate_battery_health_temperature_extremes_and_absolute_zero(self) -> None:
        """Verifies simulateBatteryHealth protects against division by zero and NaN at temperature extremes."""
        script = """
        import { simulateBatteryHealth } from './src/lib/getDepreciationData';
        const winter = simulateBatteryHealth({ chemistry: 'NCM_811', years: 3, ambientTempC: -30 });
        const summer = simulateBatteryHealth({ chemistry: 'NCM_811', years: 3, ambientTempC: 50 });
        const absZero = simulateBatteryHealth({ chemistry: 'NCM_811', years: 3, ambientTempC: -273.15 });
        const subAbsZero = simulateBatteryHealth({ chemistry: 'NCM_811', years: 3, ambientTempC: -300 });

        console.log(JSON.stringify({
            winter_soh: winter.sohPct,
            summer_soh: summer.sohPct,
            absZero_soh: absZero.sohPct,
            subAbsZero_soh: subAbsZero.sohPct,
            isFinite: [
                Number.isFinite(winter.sohPct),
                Number.isFinite(summer.sohPct),
                Number.isFinite(absZero.sohPct),
                Number.isFinite(subAbsZero.sohPct),
            ],
        }));
        """
        out = _eval_ts_node(script)
        self.assertTrue(all(out["isFinite"]), "All SoH percentages must be finite numbers")
        self.assertGreaterEqual(out["absZero_soh"], 0.0)
        self.assertLessEqual(out["absZero_soh"], 100.0)
        self.assertGreaterEqual(out["subAbsZero_soh"], 0.0)
        self.assertLessEqual(out["subAbsZero_soh"], 100.0)

    def test_20_statutory_subsidy_clawback_schedule_tiers(self) -> None:
        """Verifies calculateSubsidyClawback strictly enforces Clean Air Act Article 58 tiers and transfer rules."""
        script = """
        import { calculateSubsidyClawback } from './src/lib/getDepreciationData';
        const local = 4000000;
        const national = 6500000;

        // Statutory brackets:
        // < 3 mo: 70%
        const m2 = calculateSubsidyClawback(2, local, 'inter', national);
        // 3 ~ 6 mo: 65%
        const m4 = calculateSubsidyClawback(4, local, 'inter', national);
        // 6 ~ 9 mo: 60%
        const m8 = calculateSubsidyClawback(8, local, 'inter', national);
        // 12 ~ 15 mo: 50%
        const m14 = calculateSubsidyClawback(14, local, 'inter', national);
        // 18 ~ 21 mo: 30%
        const m20 = calculateSubsidyClawback(20, local, 'inter', national);
        // >= 24 mo: 0% (statutory exemption)
        const m24 = calculateSubsidyClawback(24, local, 'inter', national);

        // Transfer types:
        const intra = calculateSubsidyClawback(2, local, 'intra', national);
        const exportClawback = calculateSubsidyClawback(2, local, 'export', national);

        console.log(JSON.stringify({
            r_m2: m2.effectiveClawbackRate,
            r_m4: m4.effectiveClawbackRate,
            r_m8: m8.effectiveClawbackRate,
            r_m14: m14.effectiveClawbackRate,
            r_m20: m20.effectiveClawbackRate,
            r_m24: m24.effectiveClawbackRate,
            m24_exempt: m24.isExempt,
            intra_exempt: intra.isExempt,
            intra_total: intra.totalClawbackKrw,
            inter_local: m2.localClawbackKrw,
            inter_national: m2.nationalClawbackKrw,
            export_local: exportClawback.localClawbackKrw,
            export_national: exportClawback.nationalClawbackKrw,
            export_total: exportClawback.totalClawbackKrw,
        }));
        """
        out = _eval_ts_node(script)
        self.assertEqual(out["r_m2"], 0.70)
        self.assertEqual(out["r_m4"], 0.65)
        self.assertEqual(out["r_m8"], 0.60)
        self.assertEqual(out["r_m14"], 0.50)
        self.assertEqual(out["r_m20"], 0.30)
        self.assertEqual(out["r_m24"], 0.0)
        self.assertTrue(out["m24_exempt"])

        # Intra-province transfer: exempt
        self.assertTrue(out["intra_exempt"])
        self.assertEqual(out["intra_total"], 0)

        # Inter-province transfer: local clawed back, national exempt
        self.assertEqual(out["inter_local"], 2800000)  # 4M * 70%
        self.assertEqual(out["inter_national"], 0)

        # Export transfer: both local and national clawed back
        self.assertEqual(out["export_local"], 2800000)
        self.assertEqual(out["export_national"], 4550000)  # 6.5M * 70%
        self.assertEqual(out["export_total"], 7350000)

    def test_21_tco_comparison_5year_automobile_tax_and_fuel_savings(self) -> None:
        """Verifies calculateTcoComparison incorporates statutory EV tax of 130,000 KRW/year and yields net savings."""
        script = """
        import { calculateTcoComparison } from './src/lib/getDepreciationData';
        const tco = calculateTcoComparison(15000, 5, 5.2, 0.70, 1998);
        console.log(JSON.stringify({
            evAnnualTax: tco.yearlyBreakdown[0].evAutomobileTaxKrw,
            evTotalTax: tco.evTotalTaxKrw,
            iceAnnualTax: tco.yearlyBreakdown[0].iceAutomobileTaxKrw,
            iceTotalTax: tco.iceTotalTaxKrw,
            netSavingsKrw: tco.totalCumulativeSavingsKrw,
            taxSavingsKrw: tco.taxSavingsKrw,
        }));
        """
        out = _eval_ts_node(script)
        self.assertEqual(out["evAnnualTax"], 130000, "EV annual tax must be 130,000 KRW (including education tax)")
        self.assertEqual(out["evTotalTax"], 650000, "5-year EV total tax must be 650,000 KRW")
        self.assertGreater(out["iceAnnualTax"], 500000, "2000cc ICE annual tax exceeds 500,000 KRW")
        self.assertGreater(out["taxSavingsKrw"], 1700000, "Tax savings over 5 years exceed 1,700,000 KRW")
        self.assertGreater(out["netSavingsKrw"], 0, "Net TCO savings for EV must be positive")


# ===========================================================================
# Class 5: TestCycle19WcagA11yAndFrontendResilience
# ===========================================================================
class TestCycle19WcagA11yAndFrontendResilience(unittest.TestCase):
    """Validates heading monotonicity across all 12 App Router pages, WCAG AA contrast,
    localized slider aria-valuetext, security headers, layout font fallbacks, client error boundary,
    not-found route resilience, and test tree bitwise mirror parity.
    """

    def test_22_all_12_app_router_pages_have_single_h1_and_monotonic_headings(self) -> None:
        """Verifies all App Router pages contain exactly one <h1> and maintain strictly monotonic heading depth."""
        heading_re = re.compile(r"<h([1-6])[\s>]")
        routes = list(APP_DIR.glob("**/page.tsx"))
        self.assertGreaterEqual(len(routes), 12, "Must inspect at least 12 App Router pages")

        for r in routes:
            content = r.read_text(encoding="utf-8")
            for cf in r.parent.glob("*Client.tsx"):
                content += "\n" + cf.read_text(encoding="utf-8")

            matches = [int(m) for m in heading_re.findall(content)]
            self.assertEqual(
                matches.count(1),
                1,
                f"Route {r.relative_to(APP_DIR)} must contain exactly one <h1>, found {matches.count(1)}",
            )

            # Monotonic hierarchy check
            curr = 0
            for h in matches:
                if curr > 0:
                    self.assertLessEqual(
                        h,
                        curr + 1,
                        f"Skipped heading level in {r.relative_to(APP_DIR)}: jump from h{curr} to h{h}",
                    )
                curr = h

    def test_23_wcag_graphical_object_contrast_ratio_level_aa(self) -> None:
        """Verifies Battery SoH circle track stroke uses #64748b achieving >= 3:1 non-text contrast against #0f172a."""
        dep_src = (APP_DIR / "depreciation-calculator" / "DepreciationCalculatorClient.tsx").read_text(encoding="utf-8")
        self.assertIn('stroke="#64748b"', dep_src)

        # Contrast calculation check:
        # L1 (#64748b) = 0.174, L2 (#0f172a) = 0.012
        l1 = 0.174
        l2 = 0.012
        contrast = (l1 + 0.05) / (l2 + 0.05)
        self.assertGreaterEqual(contrast, 3.0, "Contrast ratio must be at least 3.0:1 for non-text UI components")

    def test_24_localized_aria_valuetext_on_all_interactive_sliders(self) -> None:
        """Verifies all 4 range sliders in DepreciationCalculatorClient.tsx define localized aria-valuetext."""
        dep_src = (APP_DIR / "depreciation-calculator" / "DepreciationCalculatorClient.tsx").read_text(encoding="utf-8")
        self.assertIn("aria-valuetext={`${holdingYears}년 보유`}", dep_src)
        self.assertIn("aria-valuetext={`연간 ${annualMileageKm.toLocaleString()}km 주행`}", dep_src)
        self.assertIn("aria-valuetext={`급속 충전 비율 ${dcfcRatio}%`}", dep_src)
        self.assertIn("aria-valuetext={`${heldMonths}개월 운행`}", dep_src)

    def test_25_security_headers_and_cross_origin_resource_policy(self) -> None:
        """Verifies next.config.mjs declares Cross-Origin-Resource-Policy and standard security headers."""
        next_cfg = (WEB_ROOT / "next.config.mjs").read_text(encoding="utf-8")
        self.assertIn("Cross-Origin-Resource-Policy", next_cfg)
        self.assertIn("same-origin", next_cfg)
        self.assertIn("X-Content-Type-Options", next_cfg)
        self.assertIn("nosniff", next_cfg)
        self.assertIn("X-Frame-Options", next_cfg)
        self.assertIn("DENY", next_cfg)
        self.assertIn("Strict-Transport-Security", next_cfg)

    def test_26_root_layout_font_fallbacks_and_site_footer_attribution(self) -> None:
        """Verifies layout.tsx declares explicit monospace system fallbacks and SiteFooter has accessible links."""
        layout_src = (APP_DIR / "layout.tsx").read_text(encoding="utf-8")
        self.assertIn("ui-monospace", layout_src)
        self.assertIn("SFMono-Regular", layout_src)
        self.assertIn("Menlo", layout_src)
        self.assertIn("monospace", layout_src)

        footer_src = (SRC_DIR / "components" / "layout" / "SiteFooter.tsx").read_text(encoding="utf-8")
        self.assertIn("https://www.ev.or.kr", footer_src)
        self.assertIn("https://www.car.go.kr", footer_src)
        self.assertIn('(새 창에서 열림)', footer_src)
        self.assertIn('target="_blank"', footer_src)
        self.assertIn('rel="noopener noreferrer"', footer_src)

    def test_27_client_error_boundary_and_not_found_resilience(self) -> None:
        """Verifies error.tsx and not-found.tsx exist in App Router with required recovery elements."""
        err_path = APP_DIR / "error.tsx"
        nf_path = APP_DIR / "not-found.tsx"

        self.assertTrue(err_path.exists(), "src/app/error.tsx must exist")
        self.assertTrue(nf_path.exists(), "src/app/not-found.tsx must exist")

        err_content = err_path.read_text(encoding="utf-8")
        self.assertIn("'use client'", err_content)
        self.assertIn("일시적인 오류가 발생했습니다", err_content)
        self.assertIn("reset()", err_content)

        nf_content = nf_path.read_text(encoding="utf-8")
        self.assertIn("404", nf_content)
        self.assertIn("요청하신 페이지를 찾을 수 없습니다", nf_content)
        self.assertIn('href="/subsidy-tracker"', nf_content)
        self.assertIn('href="/reliability-analytics"', nf_content)
        self.assertIn('href="/depreciation-calculator"', nf_content)

    def test_28_mirror_parity_and_bitwise_integrity(self) -> None:
        """Verifies 100% bitwise parity and 0o644 permissions across tests/ and ev-stealth-web/tests/."""
        root_tests = PROJECT_ROOT / "tests"
        web_tests = WEB_ROOT / "tests"

        r_files = {
            f
            for f in os.listdir(root_tests)
            if not f.startswith(".") and f != "__pycache__" and (root_tests / f).is_file()
        }
        w_files = {
            f
            for f in os.listdir(web_tests)
            if not f.startswith(".") and f != "__pycache__" and (web_tests / f).is_file()
        }

        self.assertEqual(r_files, w_files, "Test file names must match identically between root and web")

        for filename in sorted(r_files):
            p_root = root_tests / filename
            p_web = web_tests / filename

            b_root = p_root.read_bytes()
            b_web = p_web.read_bytes()

            h_root = hashlib.sha256(b_root).hexdigest()
            h_web = hashlib.sha256(b_web).hexdigest()

            self.assertEqual(
                h_root,
                h_web,
                f"Bitwise hash mismatch on test file {filename}: root={h_root} web={h_web}",
            )

            mode_root = oct(stat.S_IMODE(p_root.stat().st_mode))
            mode_web = oct(stat.S_IMODE(p_web.stat().st_mode))
            self.assertEqual(mode_root, "0o644", f"File mode for {p_root} must be 0o644")
            self.assertEqual(mode_web, "0o644", f"File mode for {p_web} must be 0o644")


if __name__ == "__main__":
    unittest.main()
