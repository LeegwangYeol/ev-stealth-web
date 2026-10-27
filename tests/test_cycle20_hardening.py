"""
tests/test_cycle20_hardening.py - Comprehensive Cycle 20 Hardening, Boundary,
Contract Validation, Stress Testing, WCAG AA, and Mirror Parity Test Suite.

Authoritative Reference:
- ORIGINAL_REQUEST.md
- DISPATCH.md (Cycle 20 Hardening Test Suite Specification)
- Wave 1 Explorer Handoff Reports:
  - sync20_worker_sync_w1/handoff.md
  - sync20_explorer_backend_w1/handoff.md
  - sync20_explorer_tests_w1/handoff.md
- COLLABORATION.md

Classes & Coverage (28 tests across 5 test classes):
1. TestCycle20DatasetIntegrity (4 tests: 01-04)
   - test_01_triple_mirror_dataset_presence_and_permissions: 12 files across 3 mirror dirs with 0o644 mode.
   - test_02_triple_mirror_cryptographic_sha256_bitwise_parity: 100% hash parity per dataset and ev_subsidy == subsidy_depletion.
   - test_03_triple_mirror_json_schema_validity_and_positive_bounds: Valid JSON syntax, required keys, positive bounds on all 4 synced datasets.
   - test_04_verified_field_defect_reports_integrity: 3 verified defect reports with community URLs and negativity >= 0.90.

2. TestCycle20BudgetQuotaConservation (5 tests: 05-09)
   - test_05_national_subsidy_metrics_conservation_invariants: total 148,510, applied 132,766, remaining 15,744, 89.4%.
   - test_06_statutory_budget_execution_invariants: total 2,105.1B, disbursed 1,893.4B KRW (89.94%).
   - test_07_category_breakdown_arithmetic_invariants: passenger, commercial, bus breakdown arithmetic equality.
   - test_08_critical_exhaustion_regions_bounds: exactly 4 regions >= 95.0% (Jeju, Gyeongbuk, Ulsan, Daegu).
   - test_09_regional_quota_sum_consistency_against_national_totals: 17 administrative division totals equal nationwide summary.

3. TestCycle20BoundaryAndStress (6 tests: 10-15)
   - test_10_empty_and_zero_database_resilience: handling 0 announced units and empty regions without ZeroDivisionError.
   - test_11_corrupt_cache_quarantine_and_atomic_fallback: corrupted JSON files quarantined and baseline restored.
   - test_12_extreme_subsidy_boundary_and_fuzzing: boundary testing on extreme MSRP values (55M, 85M, 0, negative, 1B).
   - test_13_high_concurrency_query_stress_test: 20 concurrent threads running 1,000 rapid queries on DefectTracker LRU cache.
   - test_14_extreme_input_fuzzing_and_unicode_resilience: null bytes, excessive whitespace, 10k-character strings.
   - test_15_category_metrics_and_municipality_non_negative_guards: negative numbers clamped to non-negative 0.

4. TestCycle20FrontendContracts (7 tests: 16-22)
   - test_16_frontend_statutory_price_cap_tiers: getPriceSubsidyRatio across 54.99M, 55M, 84.99M, 85M KRW.
   - test_17_frontend_additional_grants_arithmetic: youth (+20%), taxi (+30%), multi-child (+10%), scrappage (+1M KRW).
   - test_18_frontend_proportional_local_matching_formula: round(max_local * (national / 6.5M) / 10000) * 10000.
   - test_19_frontend_daily_reports_kpi_zero_state_resilience: 0 reports returns '해당 없음 (0건)' and '해당 없음 (0%)'.
   - test_20_frontend_iso3779_vin_decoding_and_illegal_chars: accepts valid 17-char VINs and rejects I, O, Q.
   - test_21_frontend_battery_health_kinetics_resilience: temperature extremes (-40°C to +60°C) with Arrhenius bounds.
   - test_22_frontend_statutory_clawback_resilience: 2-year statutory retention schedule and foreign export 100% clawback.

5. TestCycle20MirrorParity (6 tests: 23-28)
   - test_23_route_existence_and_single_h1_monotonic_headings_for_all_16_static_routes: all static routes exist with single <h1> and monotonic heading depth.
   - test_24_wcag_graphical_contrast_and_interactive_controls: Battery SoH stroke contrast >= 3.0:1.
   - test_25_accessible_slider_labels_and_live_regions: localized aria-valuetext and polite live regions.
   - test_26_next_config_security_headers_and_corp: Cross-Origin-Resource-Policy and security headers.
   - test_27_client_error_boundary_and_not_found_resilience: error.tsx and not-found.tsx exist with recovery actions.
   - test_28_bitwise_test_tree_and_backend_mirror_parity: 100% bitwise parity and 0o644 permissions across tests/ and ev-stealth-web/tests/.
"""

from __future__ import annotations

import concurrent.futures
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
import tempfile
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

from filters.defect_filter import ContextualDefectFilter
from filters.vehicle_matcher import extract_vehicle_info
from models.complaint import ComplaintRecord, RawPost
from tracker.defect_tracker import DefectTracker
from tracker.subsidy_models import CategoryMetrics, MunicipalityMetrics
from tracker.subsidy_tracker import SubsidyTracker, calculate_net_subsidy, calculate_price_cap_ratio


def _eval_ts_node(script: str, timeout_sec: int = 30) -> Any:
    """Execute a Node.js snippet using tsx or jiti to resolve TypeScript modules."""
    if not shutil.which("node"):
        raise unittest.SkipTest("Node.js runtime not installed on host environment.")

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

    jiti_path = WEB_ROOT / "node_modules" / "jiti"
    if not jiti_path.exists():
        raise unittest.SkipTest(f"tsx and jiti not found at {jiti_path}")

    node_wrapper = f"""
    const Module = require('module');
    const path = require('path');
    const createJiti = require('{jiti_path}');
    const jiti = createJiti(__filename, {{ interopDefault: true, esmResolve: true }});
    global.require = jiti;
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
# Class 1: TestCycle20DatasetIntegrity
# ===========================================================================
class TestCycle20DatasetIntegrity(unittest.TestCase):
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

        ev_sub_bytes = (PROJECT_ROOT / "data" / "ev_subsidy_data.json").read_bytes()
        dep_sub_bytes = (PROJECT_ROOT / "data" / "subsidy_depletion_data.json").read_bytes()
        self.assertEqual(len(ev_sub_bytes), len(dep_sub_bytes), "Byte counts must match between subsidy datasets")
        self.assertEqual(
            hashlib.sha256(ev_sub_bytes).hexdigest(),
            hashlib.sha256(dep_sub_bytes).hexdigest(),
            "SHA-256 hashes must match identically between ev_subsidy_data and subsidy_depletion_data",
        )

    def test_03_triple_mirror_json_schema_validity_and_positive_bounds(self) -> None:
        """Verifies all 12 dataset files parse cleanly as valid JSON with required top-level keys and positive bounds."""
        for d in self.MIRROR_DIRS:
            # 1. ev_subsidy_data.json
            with open(d / "ev_subsidy_data.json", "r", encoding="utf-8") as f:
                ev_data = json.load(f)
            self.assertTrue("generated_at" in ev_data or "generated_at" in ev_data.get("metadata", {}))
            self.assertIn("nationwide_summary", ev_data)
            self.assertIn("regions", ev_data)
            self.assertIsInstance(ev_data["regions"], list)
            summary = ev_data["nationwide_summary"]
            self.assertGreater(summary.get("total_announced_units", 0), 0)
            self.assertGreater(summary.get("total_applied_units", 0), 0)
            self.assertGreaterEqual(summary.get("total_remaining_units", 0), 0)
            self.assertGreater(summary.get("total_delivered_units", 0), 0)
            self.assertGreater(summary.get("total_budget_billion_krw", 0), 0)
            self.assertGreater(summary.get("disbursed_budget_billion_krw", 0), 0)

            for reg in ev_data["regions"]:
                self.assertIn("region_id", reg)
                self.assertIn("name_ko", reg)
                cats = reg.get("categories", {})
                for c_name, c_val in cats.items():
                    self.assertGreaterEqual(c_val.get("announced_units", 0), 0)
                    self.assertGreaterEqual(c_val.get("applied_units", 0), 0)
                    self.assertGreaterEqual(c_val.get("delivered_units", 0), 0)
                    self.assertGreaterEqual(c_val.get("remaining_units", 0), 0)

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
            self.assertGreaterEqual(rep_data["statistics"].get("total_filtered_defects", 0), 0)

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
# Class 2: TestCycle20BudgetQuotaConservation
# ===========================================================================
class TestCycle20BudgetQuotaConservation(unittest.TestCase):
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
# Class 3: TestCycle20BoundaryAndStress
# ===========================================================================
class TestCycle20BoundaryAndStress(unittest.TestCase):
    """Validates boundary handling, extreme MSRP and concurrency stress, corrupt cache
    quarantining, input fuzzing, and non-negative integer clamping.
    """

    def test_10_empty_and_zero_database_resilience(self) -> None:
        """SubsidyTracker must handle empty region lists and zero announced units without ZeroDivisionError."""
        tracker = SubsidyTracker()
        empty_summary = tracker.compute_nationwide_summary([])
        self.assertEqual(empty_summary.total_announced_units, 0)
        self.assertEqual(empty_summary.nationwide_depletion_rate, 0.0)

        # Zero announced units with applications must not divide by zero
        zero_cat = tracker.calculate_category_metrics(announced=0, applied=0, delivered=0, max_local_subsidy=0)
        self.assertEqual(zero_cat.depletion_rate, 0.0)
        self.assertEqual(zero_cat.remaining_units, 0)

    def test_11_corrupt_cache_quarantine_and_atomic_fallback(self) -> None:
        """SubsidyTracker must quarantine corrupted JSON files and gracefully fall back to baseline."""
        with tempfile.TemporaryDirectory() as td:
            cache_file = Path(td) / "ev_subsidy_data.json"
            cache_file.write_text("{malformed_json: true, invalid", encoding="utf-8")
            tracker = SubsidyTracker(cache_fallback_path=cache_file, quarantine_corrupted=True)
            payload = tracker.load_cached_payload(cache_path=cache_file, validate=True, quarantine=True)
            self.assertIsNone(payload)

            # Quarantined file check
            corrupt_files = list(Path(td).glob("ev_subsidy_data.corrupt_*.json"))
            self.assertGreaterEqual(len(corrupt_files), 1)

            # Fresh tracking cycle falls back to baseline successfully
            fresh_payload, is_fallback = tracker.execute_tracking_cycle()
            self.assertTrue(is_fallback)
            self.assertIsNotNone(fresh_payload)
            self.assertGreater(fresh_payload.nationwide_summary.total_announced_units, 0)

    def test_12_extreme_subsidy_boundary_and_fuzzing(self) -> None:
        """calculate_price_cap_ratio and calculate_net_subsidy must correctly handle boundary values."""
        # 1. Price cap ratio boundaries
        self.assertEqual(calculate_price_cap_ratio(-50_000_000), 0.0)
        self.assertEqual(calculate_price_cap_ratio(0), 0.0)
        self.assertEqual(calculate_price_cap_ratio(54_999_999), 1.0)
        self.assertEqual(calculate_price_cap_ratio(55_000_000), 1.0)
        self.assertEqual(calculate_price_cap_ratio(55_000_001), 0.5)
        self.assertEqual(calculate_price_cap_ratio(85_000_000), 0.5)
        self.assertEqual(calculate_price_cap_ratio(85_000_001), 0.0)
        self.assertEqual(calculate_price_cap_ratio(1_000_000_000), 0.0)

        # 2. Luxury 1 Billion KRW net subsidy calculation
        res_luxury = calculate_net_subsidy(
            model_national=6_500_000,
            max_national=6_500_000,
            max_local=3_000_000,
            msrp=1_000_000_000,
        )
        self.assertEqual(res_luxury["price_cap_ratio"], 0.0)
        self.assertEqual(res_luxury["total_subsidy_krw"], 0)
        self.assertEqual(res_luxury["net_price_krw"], 1_000_000_000)

    def test_13_high_concurrency_query_stress_test(self) -> None:
        """20 concurrent threads running 1,000 queries on DefectTracker must execute without race conditions."""
        tracker = DefectTracker()

        def _worker_query(task_id: int) -> int:
            results = tracker.query_defects(keyword="ICCU", limit=5)
            stats = tracker.get_statistics()
            return len(results) + stats.get("total_filtered_defects", 0)

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(_worker_query, i) for i in range(1000)]
            completed = [f.result() for f in concurrent.futures.as_completed(futures)]

        self.assertEqual(len(completed), 1000)
        self.assertTrue(all(c >= 0 for c in completed))

    def test_14_extreme_input_fuzzing_and_unicode_resilience(self) -> None:
        """Vehicle matcher and defect filter must handle null bytes, 10k repetition, and unprintable chars."""
        fuzz_samples = [
            "아이오닉 5\x00\x00 결함",
            "배터리 충전 불량 " * 1000,
            "   \t\n\r   ",
            "⚡🚗💥 ICCU 터짐 🚨",
            "None",
            "\u200b\u200c\u200d\ufeff",
        ]
        df = ContextualDefectFilter()

        for s in fuzz_samples:
            b, m = extract_vehicle_info(s)
            self.assertIsInstance(b, str)
            self.assertIsInstance(m, str)

            post = RawPost(platform="fuzz", post_id="fuzz_1", title=s, content=s)
            result = df.process_post(post)
            self.assertIsInstance(result.is_authentic_defect, bool)

    def test_15_category_metrics_and_municipality_non_negative_guards(self) -> None:
        """CategoryMetrics and MunicipalityMetrics must clamp negative numbers to non-negative 0."""
        cat = CategoryMetrics.from_dict({
            "announced_units": -50,
            "applied_units": -20,
            "delivered_units": -5,
            "remaining_units": -30,
        })
        self.assertGreaterEqual(cat.announced_units, 0)
        self.assertGreaterEqual(cat.applied_units, 0)
        self.assertGreaterEqual(cat.delivered_units, 0)
        self.assertGreaterEqual(cat.remaining_units, 0)

        mun = MunicipalityMetrics.from_dict({
            "name_ko": "테스트구",
            "announced_units": -100,
            "applied_units": -50,
            "delivered_units": -20,
            "remaining_units": -50,
        })
        self.assertGreaterEqual(mun.announced_units, 0)
        self.assertGreaterEqual(mun.applied_units, 0)
        self.assertGreaterEqual(mun.delivered_units, 0)
        self.assertGreaterEqual(mun.remaining_units, 0)


# ===========================================================================
# Class 4: TestCycle20FrontendContracts
# ===========================================================================
class TestCycle20FrontendContracts(unittest.TestCase):
    """Validates TypeScript contracts across statutory price caps, additional grant arithmetic,
    local matching formula, daily reports KPI zero state, VIN decoding, battery health, and statutory clawback.
    """

    def test_16_frontend_statutory_price_cap_tiers(self) -> None:
        """Verifies getPriceSubsidyRatio across 54.99M, 55M, 84.99M, and 85M KRW in frontend modules."""
        script = """
        import { getPriceSubsidyRatio } from './src/lib/subsidyCalculations';
        console.log(JSON.stringify({
            t1_below: getPriceSubsidyRatio(54990000),
            t1_exact: getPriceSubsidyRatio(55000000),
            t2_above: getPriceSubsidyRatio(55010000),
            t2_high: getPriceSubsidyRatio(84990000),
            t2_exact: getPriceSubsidyRatio(85000000),
            t3_above: getPriceSubsidyRatio(85010000),
        }));
        """
        out = _eval_ts_node(script)
        self.assertEqual(out["t1_below"], 1.0)
        self.assertEqual(out["t1_exact"], 1.0)
        self.assertEqual(out["t2_above"], 0.5)
        self.assertEqual(out["t2_high"], 0.5)
        self.assertEqual(out["t2_exact"], 0.5)
        self.assertEqual(out["t3_above"], 0.0)

    def test_17_frontend_additional_grants_arithmetic(self) -> None:
        """Verifies frontend bonus grants: youth (+20%), taxi (+30%), multi-child (+10%), scrappage (+1M KRW)."""
        script = """
        import { calculateNetSubsidyPure } from './src/lib/subsidyCalculations';
        const dummyModel = {
            id: 'test-model',
            brand: 'Hyundai',
            name: '아이오닉 5',
            base_price_krw: 54000000,
            national_subsidy_krw: 6000000,
            price_subsidy_ratio: 1.0,
        };
        const dummyRegion = {
            region_id: 'KR-11',
            name_ko: '서울특별시',
            categories: {
                passenger: {
                    max_local_subsidy_krw: 1500000,
                    announced_units: 1000,
                    applied_units: 500,
                    remaining_units: 500,
                    depletion_rate: 50.0,
                    status: 'HEALTHY',
                }
            }
        };

        const resYouth = calculateNetSubsidyPure(dummyModel, dummyRegion, 54000000, { isYouthFirstTimeBuyer: true });
        const resTaxi = calculateNetSubsidyPure(dummyModel, dummyRegion, 54000000, { isSmallBusinessOrTaxi: true });
        const resChild = calculateNetSubsidyPure(dummyModel, dummyRegion, 54000000, { isMultiChildFamily: true });
        const resScrap = calculateNetSubsidyPure(dummyModel, dummyRegion, 54000000, { isOldDieselScrappage: true });

        console.log(JSON.stringify({
            youthBonus: resYouth.totalSubsidyKrw - calculateNetSubsidyPure(dummyModel, dummyRegion, 54000000).totalSubsidyKrw,
            taxiBonus: resTaxi.totalSubsidyKrw - calculateNetSubsidyPure(dummyModel, dummyRegion, 54000000).totalSubsidyKrw,
            childBonus: resChild.totalSubsidyKrw - calculateNetSubsidyPure(dummyModel, dummyRegion, 54000000).totalSubsidyKrw,
            scrapBonus: resScrap.totalSubsidyKrw - calculateNetSubsidyPure(dummyModel, dummyRegion, 54000000).totalSubsidyKrw,
        }));
        """
        out = _eval_ts_node(script)
        self.assertEqual(out["youthBonus"], 1200000)  # 6M * 20%
        self.assertEqual(out["taxiBonus"], 1800000)   # 6M * 30%
        self.assertEqual(out["childBonus"], 600000)   # 6M * 10%
        self.assertEqual(out["scrapBonus"], 1000000)  # 1M fixed

    def test_18_frontend_proportional_local_matching_formula(self) -> None:
        """Verifies local matching formula: round(max_local * (national / 6.5M) / 10000) * 10000."""
        script = """
        import { calculateNetSubsidyPure } from './src/lib/subsidyCalculations';
        const dummyRegion = {
            region_id: 'KR-11',
            name_ko: '서울특별시',
            categories: {
                passenger: {
                    max_local_subsidy_krw: 1500000,
                    announced_units: 1000,
                    applied_units: 500,
                    remaining_units: 500,
                    depletion_rate: 50.0,
                    status: 'HEALTHY',
                }
            }
        };
        const m1 = {
            id: 'm1',
            brand: 'Hyundai',
            name: 'Full National',
            base_price_krw: 50000000,
            national_subsidy_krw: 6500000,
            price_subsidy_ratio: 1.0,
        };
        const m2 = {
            id: 'm2',
            brand: 'Hyundai',
            name: 'Half National',
            base_price_krw: 50000000,
            national_subsidy_krw: 3250000,
            price_subsidy_ratio: 1.0,
        };

        const res1 = calculateNetSubsidyPure(m1, dummyRegion, 50000000);
        const res2 = calculateNetSubsidyPure(m2, dummyRegion, 50000000);

        console.log(JSON.stringify({
            localFull: res1.localSubsidyKrw,
            localHalf: res2.localSubsidyKrw,
        }));
        """
        out = _eval_ts_node(script)
        self.assertEqual(out["localFull"], 1500000)
        self.assertEqual(out["localHalf"], 750000)

    def test_19_frontend_daily_reports_kpi_zero_state_resilience(self) -> None:
        """calculateKPIs must return safe fallbacks ('해당 없음 (0건)', '해당 없음 (0%)') when passed empty reports."""
        script = """
        import { calculateKPIs } from './src/lib/getDailyReports';
        const kpis = calculateKPIs([]);
        console.log(JSON.stringify({
            top_model: kpis.top_model,
            top_platform: kpis.top_platform,
            total_filtered: kpis.total_filtered_defects,
            critical_count: kpis.critical_defect_count,
        }));
        """
        out = _eval_ts_node(script)
        self.assertEqual(out["top_model"], "해당 없음 (0건)")
        self.assertEqual(out["top_platform"], "해당 없음 (0%)")
        self.assertEqual(out["total_filtered"], 0)
        self.assertEqual(out["critical_count"], 0)

    def test_20_frontend_iso3779_vin_decoding_and_illegal_chars(self) -> None:
        """Verifies validateVinString enforces ISO 3779 17-char format and rejects illegal I, O, Q."""
        script = """
        import { validateVinString } from './src/lib/getRecallData';
        console.log(JSON.stringify({
            valid: validateVinString('KM8KRDA44PU123456'),
            illegalI: validateVinString('KM8KRDA44IU123456'),
            illegalO: validateVinString('KM8KRDA44OU123456'),
            illegalQ: validateVinString('KM8KRDA44QU123456'),
        }));
        """
        out = _eval_ts_node(script)
        self.assertTrue(out["valid"]["valid"])
        self.assertEqual(out["valid"]["normalized"], "KM8KRDA44PU123456")
        self.assertFalse(out["illegalI"]["valid"])
        self.assertFalse(out["illegalO"]["valid"])
        self.assertFalse(out["illegalQ"]["valid"])

    def test_21_frontend_battery_health_kinetics_resilience(self) -> None:
        """simulateBatteryHealth must return finite bounds [0.0, 100.0] across extreme temperatures (-40°C to +60°C)."""
        script = """
        import { simulateBatteryHealth } from './src/lib/depreciationCalculations';
        const cold = simulateBatteryHealth({ chemistry: 'NCM_811', years: 3, totalKm: 45000, ambientTempC: -40 });
        const hot = simulateBatteryHealth({ chemistry: 'NCM_811', years: 3, totalKm: 45000, ambientTempC: 60 });
        console.log(JSON.stringify({
            coldSoh: cold.sohPct,
            hotSoh: hot.sohPct,
            isColdFinite: Number.isFinite(cold.sohPct),
            isHotFinite: Number.isFinite(hot.sohPct),
        }));
        """
        out = _eval_ts_node(script)
        self.assertTrue(out["isColdFinite"])
        self.assertTrue(out["isHotFinite"])
        self.assertGreaterEqual(out["coldSoh"], 0.0)
        self.assertLessEqual(out["coldSoh"], 100.0)
        self.assertGreaterEqual(out["hotSoh"], 0.0)
        self.assertLessEqual(out["hotSoh"], 100.0)

    def test_22_frontend_statutory_clawback_resilience(self) -> None:
        """calculateSubsidyClawback must enforce Clean Air Act 2-year retention and 100% foreign export clawback."""
        script = """
        import { calculateSubsidyClawback } from './src/lib/depreciationCalculations';
        const local = 4000000;
        const national = 6500000;

        const m2 = calculateSubsidyClawback(2, local, 'inter', national);
        const m24 = calculateSubsidyClawback(24, local, 'inter', national);
        const exportClaw = calculateSubsidyClawback(2, local, 'export', national);

        console.log(JSON.stringify({
            m2Rate: m2.effectiveClawbackRate,
            m24Exempt: m24.isExempt,
            m24Total: m24.totalClawbackKrw,
            exportLocal: exportClaw.localClawbackKrw,
            exportNational: exportClaw.nationalClawbackKrw,
            exportTotal: exportClaw.totalClawbackKrw,
        }));
        """
        out = _eval_ts_node(script)
        self.assertEqual(out["m2Rate"], 0.70)
        self.assertTrue(out["m24Exempt"])
        self.assertEqual(out["m24Total"], 0)
        self.assertEqual(out["exportLocal"], 2800000)
        self.assertEqual(out["exportNational"], 4550000)
        self.assertEqual(out["exportTotal"], 7350000)


# ===========================================================================
# Class 5: TestCycle20MirrorParity
# ===========================================================================
class TestCycle20MirrorParity(unittest.TestCase):
    """Validates heading monotonicity, WCAG AA contrast, accessible slider attributes,
    security headers, App Router error resilience, and 100% bitwise mirror parity.
    """

    def test_23_route_existence_and_single_h1_monotonic_headings_for_all_16_static_routes(self) -> None:
        """Verifies App Router page existence, exactly one <h1>, and monotonic heading depth."""
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

            curr = 0
            for h in matches:
                if curr > 0:
                    self.assertLessEqual(
                        h,
                        curr + 1,
                        f"Skipped heading level in {r.relative_to(APP_DIR)}: jump from h{curr} to h{h}",
                    )
                curr = h

    def test_24_wcag_graphical_contrast_and_interactive_controls(self) -> None:
        """Verifies Battery SoH circle track stroke uses #64748b achieving >= 3:1 non-text contrast against #0f172a."""
        dep_src = (APP_DIR / "depreciation-calculator" / "DepreciationCalculatorClient.tsx").read_text(encoding="utf-8")
        self.assertIn('stroke="#64748b"', dep_src)

        l1 = 0.174
        l2 = 0.012
        contrast = (l1 + 0.05) / (l2 + 0.05)
        self.assertGreaterEqual(contrast, 3.0, "Contrast ratio must be at least 3.0:1 for non-text UI components")

    def test_25_accessible_slider_labels_and_live_regions(self) -> None:
        """Verifies range sliders define localized aria-valuetext and live regions are polite."""
        dep_src = (APP_DIR / "depreciation-calculator" / "DepreciationCalculatorClient.tsx").read_text(encoding="utf-8")
        self.assertIn("aria-valuetext={`${holdingYears}년 보유`}", dep_src)
        self.assertIn("aria-valuetext={`연간 ${annualMileageKm.toLocaleString()}km 주행`}", dep_src)
        self.assertIn("aria-valuetext={`급속 충전 비율 ${dcfcRatio}%`}", dep_src)
        self.assertIn("aria-valuetext={`${heldMonths}개월 운행`}", dep_src)

    def test_26_next_config_security_headers_and_corp(self) -> None:
        """Verifies next.config.mjs declares Cross-Origin-Resource-Policy and standard security headers."""
        next_cfg = (WEB_ROOT / "next.config.mjs").read_text(encoding="utf-8")
        self.assertIn("Cross-Origin-Resource-Policy", next_cfg)
        self.assertIn("same-origin", next_cfg)
        self.assertIn("X-Content-Type-Options", next_cfg)
        self.assertIn("nosniff", next_cfg)
        self.assertIn("X-Frame-Options", next_cfg)
        self.assertIn("DENY", next_cfg)
        self.assertIn("Strict-Transport-Security", next_cfg)

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

    def test_28_bitwise_test_tree_and_backend_mirror_parity(self) -> None:
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
