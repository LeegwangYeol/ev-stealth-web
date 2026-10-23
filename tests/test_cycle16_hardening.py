"""
tests/test_cycle16_hardening.py - Comprehensive Cycle 16 Hardening, Boundary,
Accessibility, Invariants, and Mirror Parity Test Suite.

Authoritative Reference:
- ORIGINAL_REQUEST.md
- DISPATCH.md (Cycle 16 Hardening Test Suite Specification)
- Wave 1 Explorer Handoff Reports:
  - sync16_worker_sync_w1/handoff.md
  - sync16_explorer_a11y_w1/handoff.md
  - sync16_explorer_tests_w1/handoff.md
  - sync16_explorer_backend_w1/handoff.md
  - sync16_explorer_frontend_w1/handoff.md
  - sync16_spec_miner_parity_w1/handoff.md
- COLLABORATION.md

Coverage:
1. TestCycle16Wave1DataSyncAndMirrorParity:
   - test_01_triple_mirror_dataset_presence_and_permissions: 12 files across 3 mirror dirs with 0o644 mode.
   - test_02_triple_mirror_cryptographic_sha256_bitwise_parity: 100% hash parity per dataset and ev_subsidy == subsidy_depletion.
   - test_03_national_subsidy_metrics_conservation_invariants: total 148,510, applied 132,766, remaining 15,744, 89.4%.
   - test_04_statutory_budget_execution_invariants: total 2,105.1B, disbursed 1,893.4B KRW (89.94%).
   - test_05_category_breakdown_arithmetic_invariants: passenger, commercial, bus breakdown arithmetic equality.
   - test_06_critical_exhaustion_regions_bounds: exactly 4 regions >= 95.0% (Jeju, Gyeongbuk, Ulsan, Daegu).
   - test_07_verified_field_defect_reports_integrity: 3 verified defect reports with community URLs and negativity >= 0.90.

2. TestCycle16BackendRemediations:
   - test_08_subsidy_tracker_extreme_quota_and_bounds_resilience: depletion rate and remaining quota zero/negative/nan guards.
   - test_09_net_subsidy_calculation_extreme_price_cap_ratios: 2026 price cap ratios (1.0, 0.5, 0.0) and net subsidy safety.
   - test_10_report_generator_dict_and_dataclass_polymorphism_safety: briefing generators handle dicts and dataclasses seamlessly.
   - test_11_defect_tracker_cache_and_statistics_invariants: category_distribution always present, avg_negativity finite.
   - test_12_atomic_writer_resilience_and_permission_enforcement: atomic_write_json sanitizes NaN/Inf and enforces 0o644.

3. TestCycle16FrontendRemediationsAndContracts:
   - test_13_get_daily_reports_kpi_fallbacks_and_zero_state_resilience: 0-defect state returns '해당 없음 (0건)' and '해당 없음 (0%)'.
   - test_14_get_subsidy_data_custom_msrp_and_default_model_resilience: MSRP clamped to 10B KRW, default model/region fallback.
   - test_15_depreciation_engine_boundary_and_battery_health_resilience: temperature/mileage bounds and tier fallback.
   - test_16_recall_data_multi_segment_year_parsing_resilience: comma/hyphen/disjoint multi-segment year matching.

4. TestCycle16WCAGAccessibilityInvariants:
   - test_17_depreciation_calculator_clawback_status_live_region: clawback alert banner role="status" and aria-live="polite".
   - test_18_depreciation_calculator_chart_mode_aria_pressed: chart view mode buttons declare aria-pressed state.
   - test_19_recall_portal_accordion_toggle_accessible_labels: contextual campaign labels and focus-visible:ring-2 on reset buttons.
   - test_20_subsidy_tracker_emergency_ticker_landmark_and_accordion_labels: ticker landmark role="region" / aria-label and municipality labels.
   - test_21_heading_hierarchy_monotonicity_across_app_router: exactly one <h1> and monotonic heading sequence across routes.

5. TestCycle16TestTreeMirrorParity:
   - test_22_test_tree_bitwise_mirror_parity: 100% bitwise parity and 0o644 permissions across all test files.
   - test_23_test_cycle16_hardening_exact_mirror_parity: identical byte length and SHA-256 hash for test_cycle16_hardening.py.
   - test_24_backend_logic_mirror_parity: 100% parity across tracker/, crawlers/, models/, utils/, run_tracker.py.
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
import tempfile
from types import SimpleNamespace
import unittest
from typing import Any, Dict, List, Optional, Set, Tuple, Union


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

from models.complaint import ComplaintRecord
from tracker.atomic_writer import atomic_write_json
from tracker.defect_tracker import DefectTracker
from tracker.report_generator import ReportGenerator
from tracker.subsidy_models import MunicipalityMetrics, RegionRecord, SubsidyPayload, SubsidyMetadata, NationwideSummary
from tracker.subsidy_tracker import (
    SubsidyTracker,
    calculate_depletion_rate,
    calculate_remaining_units,
    calculate_price_cap_ratio,
    calculate_net_subsidy,
)


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
# Class 1: TestCycle16Wave1DataSyncAndMirrorParity
# ===========================================================================
class TestCycle16Wave1DataSyncAndMirrorParity(unittest.TestCase):
    """Validates data sync execution, 12-file mirror parity, POSIX permissions,
    quota invariants, critical regional alerts (Jeju, Gyeongbuk, Ulsan, Daegu),
    and verified community defect reports.
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
        """Asserts existence of all 12 files across 3 mirror locations and 0o644 POSIX permissions."""
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

        # Asserts ev_subsidy_data.json and subsidy_depletion_data.json have identical byte counts and matching hashes
        ev_sub_bytes = (PROJECT_ROOT / "data" / "ev_subsidy_data.json").read_bytes()
        dep_sub_bytes = (PROJECT_ROOT / "data" / "subsidy_depletion_data.json").read_bytes()
        self.assertEqual(len(ev_sub_bytes), len(dep_sub_bytes), "Byte counts must match between subsidy datasets")
        self.assertEqual(
            hashlib.sha256(ev_sub_bytes).hexdigest(),
            hashlib.sha256(dep_sub_bytes).hexdigest(),
            "SHA-256 hashes must match identically between ev_subsidy_data and subsidy_depletion_data",
        )

    def test_03_national_subsidy_metrics_conservation_invariants(self) -> None:
        """Asserts national quota volume invariants and conservation law: applied + remaining == announced."""
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

        # Conservation law
        self.assertEqual(
            total_applied + total_remaining,
            total_announced,
            f"Conservation violated: applied ({total_applied}) + remaining ({total_remaining}) != announced ({total_announced})",
        )

        # Depletion rate (132766 / 148510 = 89.3986... -> 89.4%)
        self.assertEqual(depletion_rate, 89.4, "National depletion rate must be 89.4%")
        expected_rate = round((total_applied / total_announced) * 100.0, 1)
        self.assertEqual(expected_rate, 89.4)

    def test_04_statutory_budget_execution_invariants(self) -> None:
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

    def test_05_category_breakdown_arithmetic_invariants(self) -> None:
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

    def test_06_critical_exhaustion_regions_bounds(self) -> None:
        """Asserts that exactly 4 regions have overall_depletion_rate >= 95.0%."""
        data_file = PROJECT_ROOT / "data" / "ev_subsidy_data.json"
        with open(data_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        regions = data.get("regions", [])
        critical_regs = [r for r in regions if r.get("overall_depletion_rate", 0.0) >= 95.0]

        self.assertEqual(len(critical_regs), 4, f"Expected exactly 4 critical regions, found {len(critical_regs)}")

        crit_map = {r["region_id"]: r for r in critical_regs}
        self.assertIn("KR-49", crit_map, "Jeju (KR-49) must be in critical regions")
        self.assertIn("KR-47", crit_map, "Gyeongbuk (KR-47) must be in critical regions")
        self.assertIn("KR-31", crit_map, "Ulsan (KR-31) must be in critical regions")
        self.assertIn("KR-27", crit_map, "Daegu (KR-27) must be in critical regions")

        self.assertEqual(crit_map["KR-49"]["overall_depletion_rate"], 99.0)
        self.assertEqual(crit_map["KR-47"]["overall_depletion_rate"], 97.3)
        self.assertEqual(crit_map["KR-31"]["overall_depletion_rate"], 96.5)
        self.assertEqual(crit_map["KR-27"]["overall_depletion_rate"], 96.4)

    def test_07_verified_field_defect_reports_integrity(self) -> None:
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


# ===========================================================================
# Class 2: TestCycle16BackendRemediations
# ===========================================================================
class TestCycle16BackendRemediations(unittest.TestCase):
    """Validates subsidy_tracker.py dict duck-typing and bounds, base_crawler.py
    ensure_warm_up signatures, report_generator.py dict duck-typing, and
    complaint.py NaN/None guards.
    """

    def setUp(self) -> None:
        self.tracker = SubsidyTracker()
        self.generator = ReportGenerator()
        self.defect_tracker = DefectTracker()

    def test_08_subsidy_tracker_extreme_quota_and_bounds_resilience(self) -> None:
        """Verifies calculate_depletion_rate and calculate_remaining_units handle extreme/corrupt boundaries."""
        # 1. calculate_depletion_rate
        self.assertEqual(calculate_depletion_rate(0, 0), 0.0)
        self.assertEqual(calculate_depletion_rate(100, 0), 0.0)
        self.assertEqual(calculate_depletion_rate(-10, 100), 0.0)
        self.assertEqual(calculate_depletion_rate(50, -100), 0.0)
        self.assertEqual(calculate_depletion_rate(float("nan"), 100), 0.0)
        self.assertEqual(calculate_depletion_rate(100, float("nan")), 0.0)
        self.assertEqual(calculate_depletion_rate(float("inf"), 100), 0.0)
        self.assertEqual(calculate_depletion_rate(100, float("inf")), 0.0)
        self.assertEqual(calculate_depletion_rate(None, 100), 0.0)  # type: ignore[arg-type]
        self.assertEqual(calculate_depletion_rate("invalid", 100), 0.0)  # type: ignore[arg-type]
        self.assertEqual(calculate_depletion_rate(50, 100), 50.0)

        # 2. calculate_remaining_units
        self.assertEqual(calculate_remaining_units(150, 100), 0, "Oversubscription must clamp to 0")
        self.assertEqual(calculate_remaining_units(100, 100), 0)
        self.assertEqual(calculate_remaining_units(50, -100), 0)
        self.assertEqual(calculate_remaining_units(float("nan"), 100), 0)
        self.assertEqual(calculate_remaining_units(None, 100), 0)  # type: ignore[arg-type]
        self.assertEqual(calculate_remaining_units(60, 100), 40)

    def test_09_net_subsidy_calculation_extreme_price_cap_ratios(self) -> None:
        """Verifies statutory 2026 price cap ratio boundaries (<=55M 1.0, 55M-85M 0.5, >85M 0.0) and net subsidy safety."""
        # 1. Price cap ratios
        self.assertEqual(calculate_price_cap_ratio(50_000_000), 1.0)
        self.assertEqual(calculate_price_cap_ratio(55_000_000), 1.0)
        self.assertEqual(calculate_price_cap_ratio(60_000_000), 0.5)
        self.assertEqual(calculate_price_cap_ratio(85_000_000), 0.5)
        self.assertEqual(calculate_price_cap_ratio(90_000_000), 0.0)
        self.assertEqual(calculate_price_cap_ratio(None), 0.0)  # type: ignore[arg-type]
        self.assertEqual(calculate_price_cap_ratio(float("nan")), 0.0)  # type: ignore[arg-type]
        self.assertEqual(calculate_price_cap_ratio(float("inf")), 0.0)  # type: ignore[arg-type]

        # 2. calculate_net_subsidy with extreme inputs
        res_valid = calculate_net_subsidy(6_500_000, 6_500_000, 4_000_000, 50_000_000)
        self.assertIsInstance(res_valid, dict)
        self.assertEqual(res_valid["total_subsidy_krw"], 10_500_000)
        self.assertEqual(res_valid["net_price_krw"], 39_500_000)

        res_none = calculate_net_subsidy(None, None, None, None)  # type: ignore[arg-type]
        self.assertEqual(res_none["total_subsidy_krw"], 0)
        self.assertEqual(res_none["net_price_krw"], 0)

    def test_10_report_generator_dict_and_dataclass_polymorphism_safety(self) -> None:
        """Verifies ReportGenerator.generate_subsidy_briefing and generate_defect_briefing handle dicts and dataclasses."""
        # 1. Defect briefing with ComplaintRecord dataclass and raw dict
        rec = ComplaintRecord(
            id="dc_20261024_001",
            source="dcinside",
            url="https://gall.dcinside.com/mgallery/board/view/?id=car_new1&no=1284920",
            title="ICCU 고장 제보",
            author="익명",
            created_at="2026-10-24 12:00:00",
            vehicle_brand="Hyundai",
            vehicle_model="Ioniq 5",
            defect_category="BATTERY_CHARGING",
            summary="고속도로 ICCU 고장",
            verbatim_quote="경고등 점등 및 동력 상실 발생",
            severity_index=9.5,
            is_authentic_defect=True,
        )
        rec_dict = {
            "id": "bd_20261024_002",
            "source": "bobaedream",
            "url": "https://www.bobaedream.co.kr/view?code=national&No=2291045",
            "title": "EV3 피쉬테일 제보",
            "vehicle_brand": "Kia",
            "vehicle_model": "EV3",
            "defect_category": "DRIVING_POWERTRAIN",
            "summary": "빗길 토션빔 접지력 상실",
            "verbatim_quote": "리어 털림 현상 심각",
            "severity_index": 8.0,
            "severity": "CRITICAL",
            "is_authentic_defect": True,
        }

        defect_briefing = self.generator.generate_defect_briefing([rec, rec_dict])
        self.assertIn("총 수집/분류 결함 건수**: 2건", defect_briefing)
        self.assertIn("Ioniq 5", defect_briefing)
        self.assertIn("EV3", defect_briefing)

        # 2. Subsidy briefing with dict metadata and dict nationwide summary
        payload_dict = SimpleNamespace(
            metadata={"generated_at": "2026-10-24T05:00:00Z"},
            regions=[
                {
                    "name_ko": "제주",
                    "overall_depletion_rate": 99.0,
                    "overall_status": "DEPLETED",
                    "categories": {"passenger": {"remaining_units": 40}},
                }
            ],
            nationwide_summary={
                "total_announced_units": 148510,
                "total_applied_units": 132766,
                "nationwide_depletion_rate": 89.4,
                "total_budget_billion_krw": 2105.1,
                "disbursed_budget_billion_krw": 1893.4,
                "category_totals": {
                    "passenger": {
                        "announced_units": 110400,
                        "applied_units": 97035,
                        "depletion_rate": 87.9,
                        "remaining_units": 13365,
                        "status": "CAUTION",
                    }
                },
            },
        )
        subsidy_briefing = self.generator.generate_subsidy_briefing(payload_dict)
        self.assertIn("2026-10-24T05:00:00Z", subsidy_briefing)
        self.assertIn("89.4%", subsidy_briefing)
        self.assertIn("148,510대", subsidy_briefing)
        self.assertIn("132,766대", subsidy_briefing)

    def test_11_defect_tracker_cache_and_statistics_invariants(self) -> None:
        """Verifies DefectTracker.get_statistics always populates category_distribution and finite avg_negativity."""
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "reports": [
                        {"id": "c1", "defect_category": "BATTERY_CHARGING", "negativity_score": 0.95},
                        {"id": "c2", "defect_category": "BATTERY_CHARGING", "negativity_score": float("nan")},
                        {"id": "c3", "defect_category": "SOFTWARE_ELECTRONICS", "negativity_score": 0.85},
                        {"id": "c4", "defect_category": "BODY", "negativity_score": float("inf")},
                    ]
                },
                f,
            )
            temp_path = f.name

        try:
            stats = self.defect_tracker.get_statistics(file_path=temp_path)
            self.assertIn("category_distribution", stats)
            self.assertIsInstance(stats["category_distribution"], dict)
            self.assertEqual(stats["category_distribution"]["BATTERY_CHARGING"], 2)
            self.assertEqual(stats["category_distribution"]["SOFTWARE_ELECTRONICS"], 1)

            avg_neg = stats["avg_negativity_score"]
            self.assertIsInstance(avg_neg, float)
            self.assertFalse(math.isnan(avg_neg), "avg_negativity_score must not be NaN")
            self.assertFalse(math.isinf(avg_neg), "avg_negativity_score must not be Inf")
            # Average of 0.95 and 0.85 = 0.90
            self.assertEqual(avg_neg, 0.90)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_12_atomic_writer_resilience_and_permission_enforcement(self) -> None:
        """Verifies atomic_write_json sanitizes NaN/Inf and enforces 0o644 permissions."""
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "test_payload.json"
            payload = {
                "nan_val": float("nan"),
                "inf_val": float("inf"),
                "nested": {"valid": 123.45, "nan": float("nan")},
            }
            atomic_write_json(payload, target)
            self.assertTrue(target.exists())

            # Verify permissions
            mode = oct(stat.S_IMODE(target.stat().st_mode))
            self.assertEqual(mode, "0o644")

            # Verify JSON load without NaN
            raw_text = target.read_text(encoding="utf-8")
            self.assertNotIn("NaN", raw_text)
            loaded = json.loads(raw_text)
            self.assertEqual(loaded["nan_val"], 0.0)
            self.assertEqual(loaded["inf_val"], 0.0)
            self.assertEqual(loaded["nested"]["nan"], 0.0)


# ===========================================================================
# Class 3: TestCycle16FrontendRemediationsAndContracts
# ===========================================================================
class TestCycle16FrontendRemediationsAndContracts(unittest.TestCase):
    """Validates getRecallData.ts brand union, holding period dynamic labels,
    export clawback national+local subtext, 0-defect fallback strings,
    and severity taxonomy mapping.
    """

    def test_13_get_daily_reports_kpi_fallbacks_and_zero_state_resilience(self) -> None:
        """Verifies calculateKPIs and loader fallback return '해당 없음 (0건)' and '해당 없음 (0%)' on 0 records."""
        script = """
        import { calculateKPIs } from './src/lib/getDailyReports';
        const kpis = calculateKPIs([]);
        console.log(JSON.stringify(kpis));
        """
        output = _eval_ts_node(script)
        self.assertEqual(output["total_filtered_defects"], 0)
        self.assertEqual(output["avg_negativity_score"], 0)
        self.assertEqual(output["top_model"], "해당 없음 (0건)")
        self.assertEqual(output["top_platform"], "해당 없음 (0%)")

        # Also inspect getDailyReports.ts catch fallback
        daily_src = (LIB_DIR / "getDailyReports.ts").read_text(encoding="utf-8")
        self.assertIn("해당 없음 (0건)", daily_src)
        self.assertIn("해당 없음 (0%)", daily_src)

    def test_14_get_subsidy_data_custom_msrp_and_default_model_resilience(self) -> None:
        """Verifies custom MSRP is clamped to 10 billion KRW ceiling and fallback model/region IDs."""
        script = """
        import { calculateNetSubsidy } from './src/lib/getSubsidyData';
        const resHuge = calculateNetSubsidy('ioniq-5-2026', 'KR-11', 15_000_000_000);
        const resDefault = calculateNetSubsidy('unknown-id-xyz', 'unknown-region-abc', 50_000_000);
        console.log(JSON.stringify({
            hugeMsrp: resHuge.msrpKrw,
            defaultModelId: resDefault.modelId,
            defaultRegionId: resDefault.regionId,
        }));
        """
        output = _eval_ts_node(script)
        self.assertEqual(output["hugeMsrp"], 10_000_000_000, "MSRP must be clamped to 10B KRW ceiling")
        self.assertEqual(output["defaultModelId"], "ioniq-5-2026")
        self.assertEqual(output["defaultRegionId"], "KR-11")

    def test_15_depreciation_engine_boundary_and_battery_health_resilience(self) -> None:
        """Verifies Arrhenius temperature bounds, extreme mileage bounds, and out-of-bounds battery tier fallback."""
        script = """
        import { simulateBatteryHealth } from './src/lib/getDepreciationData';
        const cold = simulateBatteryHealth({ years: 3, totalKm: 45000, ambientTempC: -30 });
        const hot = simulateBatteryHealth({ years: 3, totalKm: 45000, ambientTempC: 50 });
        const hugeKm = simulateBatteryHealth({ years: 5, totalKm: 1_000_000 });
        const outTier = simulateBatteryHealth({ years: 3, totalKm: 45000, packCapacityKwh: 300 });
        console.log(JSON.stringify({
            coldSoh: cold.sohPct,
            hotSoh: hot.sohPct,
            hugeKmSoh: hugeKm.sohPct,
            outTierId: outTier.replacementCostEstimate.tierId,
            outTierCost: outTier.replacementCostEstimate.estimatedCostKrw,
        }));
        """
        output = _eval_ts_node(script)
        self.assertGreater(output["coldSoh"], 0.0)
        self.assertLessEqual(output["coldSoh"], 100.0)
        self.assertGreater(output["hotSoh"], 0.0)
        self.assertLessEqual(output["hotSoh"], 100.0)
        self.assertGreater(output["hugeKmSoh"], 0.0)
        self.assertLessEqual(output["hugeKmSoh"], 100.0)
        self.assertEqual(output["outTierId"], "TIER_100KWH")
        self.assertGreater(output["outTierCost"], 0)

    def test_16_recall_data_multi_segment_year_parsing_resilience(self) -> None:
        """Verifies multi-segment year parsing (comma-delimited, hyphen-delimited, disjoint) in isYearMatchForCampaign."""
        script = """
        import { isYearMatchForCampaign } from './src/lib/getRecallData';
        console.log(JSON.stringify({
            commaMatch: isYearMatchForCampaign(2022, '2020, 2022, 2024'),
            commaMiss: isYearMatchForCampaign(2021, '2020, 2022, 2024'),
            rangeMatch: isYearMatchForCampaign(2023, '2021~2024'),
            rangeMiss: isYearMatchForCampaign(2025, '2021~2024'),
            hyphenMatch: isYearMatchForCampaign(2019, '2018-2020'),
            hyphenMiss: isYearMatchForCampaign(2021, '2018-2020'),
            mixed: isYearMatchForCampaign(2023, '2018, 2022~2025'),
        }));
        """
        output = _eval_ts_node(script)
        self.assertTrue(output["commaMatch"])
        self.assertFalse(output["commaMiss"])
        self.assertTrue(output["rangeMatch"])
        self.assertFalse(output["rangeMiss"])
        self.assertTrue(output["hyphenMatch"])
        self.assertFalse(output["hyphenMiss"])
        self.assertTrue(output["mixed"])


# ===========================================================================
# Class 4: TestCycle16WCAGAccessibilityInvariants
# ===========================================================================
class TestCycle16WCAGAccessibilityInvariants(unittest.TestCase):
    """Validates clawback live region, chart toggle aria-pressed, campaign
    accordion labels, reset button focus rings, and emergency ticker landmark semantics.
    """

    def test_17_depreciation_calculator_clawback_status_live_region(self) -> None:
        """DepreciationCalculatorClient.tsx statutory clawback alert banner must declare role='status' and aria-live='polite'."""
        dep_content = (APP_DIR / "depreciation-calculator" / "DepreciationCalculatorClient.tsx").read_text(encoding="utf-8")
        self.assertIn('role="status"', dep_content)
        self.assertIn('aria-live="polite"', dep_content)
        self.assertIn('aria-atomic="true"', dep_content)

    def test_18_depreciation_calculator_chart_mode_aria_pressed(self) -> None:
        """DepreciationCalculatorClient.tsx chart mode buttons must declare aria-pressed state."""
        dep_content = (APP_DIR / "depreciation-calculator" / "DepreciationCalculatorClient.tsx").read_text(encoding="utf-8")
        self.assertIn("aria-pressed={chartViewMode === 'price'}", dep_content)
        self.assertIn("aria-pressed={chartViewMode === 'percentage'}", dep_content)

    def test_19_recall_portal_accordion_toggle_accessible_labels(self) -> None:
        """RecallPortalClient.tsx campaign accordion toggles must declare contextual aria-labels and reset buttons visible focus."""
        rec_content = (APP_DIR / "recall-portal" / "RecallPortalClient.tsx").read_text(encoding="utf-8")
        self.assertIn("${campaign.target_model}", rec_content)
        self.assertIn("${campaign.defect_title}", rec_content)
        self.assertIn("focus-visible:ring-2", rec_content)
        self.assertIn("focus-visible:ring-blue-400", rec_content)

    def test_20_subsidy_tracker_emergency_ticker_landmark_and_accordion_labels(self) -> None:
        """SubsidyTrackerClient.tsx emergency ticker must declare role='region' / aria-label and municipality labels."""
        sub_content = (APP_DIR / "subsidy-tracker" / "SubsidyTrackerClient.tsx").read_text(encoding="utf-8")
        self.assertIn('role="region"', sub_content)
        self.assertIn('aria-label="보조금 긴급 소진 주의보"', sub_content)
        self.assertIn('role="alert"', sub_content)
        self.assertIn("${region.name_ko}", sub_content)

    def test_21_heading_hierarchy_monotonicity_across_app_router(self) -> None:
        """All App Router page routes must have exactly one <h1> and maintain monotonic heading sequence."""
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


# ===========================================================================
# Class 5: TestCycle16TestTreeMirrorParity
# ===========================================================================
class TestCycle16TestTreeMirrorParity(unittest.TestCase):
    """Validates 100% bitwise data parity, test tree parity, and backend code mirror parity."""

    def test_22_test_tree_bitwise_mirror_parity(self) -> None:
        """Verifies 100% bitwise parity and 0o644 permissions across all test files between tests/ and ev-stealth-web/tests/."""
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

    def test_23_test_cycle16_hardening_exact_mirror_parity(self) -> None:
        """Verifies tests/test_cycle16_hardening.py and ev-stealth-web/tests/test_cycle16_hardening.py match identically."""
        p_root = PROJECT_ROOT / "tests" / "test_cycle16_hardening.py"
        p_web = WEB_ROOT / "tests" / "test_cycle16_hardening.py"

        self.assertTrue(p_root.exists(), f"Root test suite {p_root} must exist")
        self.assertTrue(p_web.exists(), f"Web mirror test suite {p_web} must exist")

        b_root = p_root.read_bytes()
        b_web = p_web.read_bytes()

        self.assertEqual(len(b_root), len(b_web), "Byte lengths must match identically")
        h_root = hashlib.sha256(b_root).hexdigest()
        h_web = hashlib.sha256(b_web).hexdigest()
        self.assertEqual(h_root, h_web, f"SHA-256 hashes must match identically ({h_root})")

    def test_24_backend_logic_mirror_parity(self) -> None:
        """Verifies 100% parity across tracker/, crawlers/, models/, utils/, and run_tracker.py."""
        modules = ["tracker", "crawlers", "models", "utils"]
        for mod in modules:
            root_mod = PROJECT_ROOT / mod
            web_mod = WEB_ROOT / mod
            self.assertTrue(root_mod.is_dir(), f"Root module {root_mod} must exist")
            self.assertTrue(web_mod.is_dir(), f"Web module {web_mod} must exist")

            r_py = {f for f in os.listdir(root_mod) if f.endswith(".py")}
            w_py = {f for f in os.listdir(web_mod) if f.endswith(".py")}
            self.assertEqual(r_py, w_py, f"Python files in module {mod} must match identically")

            for f in r_py:
                p_root = root_mod / f
                p_web = web_mod / f
                h_root = hashlib.sha256(p_root.read_bytes()).hexdigest()
                h_web = hashlib.sha256(p_web.read_bytes()).hexdigest()
                self.assertEqual(
                    h_root,
                    h_web,
                    f"Hash mismatch on {mod}/{f}: root={h_root} web={h_web}",
                )

        # Check run_tracker.py
        rt_root = PROJECT_ROOT / "run_tracker.py"
        rt_web = WEB_ROOT / "run_tracker.py"
        self.assertTrue(rt_root.is_file())
        self.assertTrue(rt_web.is_file())
        self.assertEqual(
            hashlib.sha256(rt_root.read_bytes()).hexdigest(),
            hashlib.sha256(rt_web.read_bytes()).hexdigest(),
            "run_tracker.py must match identically between root and web",
        )


if __name__ == "__main__":
    unittest.main()
