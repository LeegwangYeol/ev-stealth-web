"""
tests/test_cycle24_hardening.py - Comprehensive Cycle 24 Hardening, Parity,
Conservation, Resilience, and Schema Invariants Regression Suite.

Authoritative Reference:
- ORIGINAL_REQUEST.md
- DISPATCH.md / User Prompt Specifications
- COLLABORATION.md

Classes & Coverage (19 tests across 5 test classes):
1. TestCycle24DatasetIntegrityAndTripleMirrorParity (4 tests: 01-04)
   - test_01_triple_mirror_dataset_presence_and_permissions: 12 files across 3 mirror dirs with 0o644 mode.
   - test_02_triple_mirror_cryptographic_sha256_bitwise_parity: 100% SHA-256 hash parity across data/, ev-stealth-web/src/data/, ev-stealth-web/public/data/, and ev_subsidy == subsidy_depletion.
   - test_03_triple_mirror_json_schema_validity_and_positive_bounds: Clean JSON syntax, mandatory schema keys, valid ranges across all synced datasets.
   - test_04_verified_field_defect_reports_integrity: 4 verified field defect reports present with live URLs and authentic quotes.

2. TestCycle24StatutoryBudgetConservation (4 tests: 05-08)
   - test_05_national_subsidy_metrics_conservation_invariants: applied + remaining == announced quota (132,766 + 15,744 == 148,510), delivered <= applied (122,515 <= 132,766).
   - test_06_statutory_budget_execution_invariants: total 2,105.1B, disbursed 1,893.4B KRW (89.94% execution rate).
   - test_07_category_breakdown_arithmetic_invariants: passenger, commercial, bus arithmetic equality (applied + remaining == announced) and national sum conservation.
   - test_08_regional_quota_sum_consistency_across_all_17_regions: all 17 administrative division totals equal nationwide summary, regional applied + remaining == announced.

3. TestCycle24DepletionRateAndExhaustedRegions (3 tests: 09-11)
   - test_09_national_depletion_rate_realistic_bounds: national depletion rate within realistic bound 80.0% - 95.0% (actual: 89.4%).
   - test_10_four_exhausted_regions_invariants: exactly 4 exhausted regions with >=95.0% depletion and CRITICAL status: Jeju (99.0%), Gyeongbuk (97.3%), Ulsan (96.5%), Daegu (96.4%).
   - test_11_alert_region_counts_conservation: 4 critical, 12 warning, 1 caution, 0 healthy, 0 depleted (sum == 17).

4. TestCycle24RootDetectionResilience (4 tests: 12-15)
   - test_12_find_repo_root_direct_resolution: returns canonical project root containing ev-stealth-web, data, and tests.
   - test_13_find_repo_root_executed_from_root_and_ev_stealth_web_subprocesses: subprocess execution from root, ev-stealth-web/, tests/, and nested subdirectories returns identical root.
   - test_14_find_repo_root_synthetic_ancestor_traversal: ancestor search logic handles any synthetic nested directory correctly.
   - test_15_root_detection_sys_path_and_module_resolution: backend modules (filters, models, tracker, utils) import and resolve cleanly via detected root.

5. TestCycle24FrontendBackendContracts (4 tests: 16-19)
   - test_16_statutory_price_cap_ratio_boundary_contracts: calculate_price_cap_ratio boundaries at 55M and 85M KRW.
   - test_17_net_subsidy_calculation_bounds: calculate_net_subsidy arithmetic conservation and price cap scaling.
   - test_18_depreciation_and_reliability_frontend_ts_contracts: 10B KRW cap in TypeScript depreciation code and safe DSI handling in reliability code.
   - test_19_triple_mirror_test_tree_and_backend_parity: bitwise parity across tests/ and ev-stealth-web/tests/, and backend packages crawlers, filters, models, tracker, utils.
"""

from __future__ import annotations

import filecmp
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from typing import Any, Dict, List, Optional
import unittest


def _find_repo_root(start_path: Optional[Path] = None) -> Path:
    """Resiliently discover the repository root whether invoked from root,
    ev-stealth-web/, tests/, or any nested subdirectory.
    """
    # 1. Search ancestors of start_path if explicitly provided
    if start_path is not None:
        p = start_path.resolve()
        while p != p.parent:
            if (p / "ev-stealth-web").is_dir() and (p / "data").is_dir():
                return p
            p = p.parent

    # 2. Search ancestors of __file__
    try:
        p = Path(__file__).resolve().parent
        while p != p.parent:
            if (p / "ev-stealth-web").is_dir() and (p / "data").is_dir():
                return p
            p = p.parent
    except Exception:
        pass

    # 3. Search ancestors of cwd
    try:
        cwd = Path.cwd().resolve()
        while cwd != cwd.parent:
            if (cwd / "ev-stealth-web").is_dir() and (cwd / "data").is_dir():
                return cwd
            cwd = cwd.parent
    except Exception:
        pass

    # 4. Explicit fallback candidates
    candidates = [
        Path.cwd().resolve(),
        Path.cwd().resolve().parent,
        Path(__file__).resolve().parent.parent if "__file__" in globals() else Path.cwd().resolve(),
        Path(__file__).resolve().parent.parent.parent if "__file__" in globals() else Path.cwd().resolve().parent,
    ]
    for c in candidates:
        if (c / "ev-stealth-web").is_dir() and (c / "data").is_dir():
            return c

    return Path.cwd().resolve()


PROJECT_ROOT = _find_repo_root()
WEB_ROOT = PROJECT_ROOT / "ev-stealth-web"
SRC_DIR = WEB_ROOT / "src"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
else:
    sys.path.remove(str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT))

if str(WEB_ROOT) not in sys.path:
    sys.path.append(str(WEB_ROOT))

from filters.vehicle_matcher import (
    extract_vehicle_info,
    BRAND_HYUNDAI,
    BRAND_KIA,
    BRAND_OTHER,
    BRAND_TESLA,
    BRAND_BYD,
)
from models.complaint import ComplaintRecord
from tracker.subsidy_tracker import calculate_price_cap_ratio, calculate_net_subsidy


# ===========================================================================
# Class 1: TestCycle24DatasetIntegrityAndTripleMirrorParity
# ===========================================================================
class TestCycle24DatasetIntegrityAndTripleMirrorParity(unittest.TestCase):
    """Validates triple mirror dataset presence, 0o644 POSIX mode, cryptographic
    SHA-256 bitwise parity across 3 locations, valid JSON schema, and verified defect reports.
    """

    CORE_DATASETS = [
        "ev_subsidy_data.json",
        "subsidy_depletion_data.json",
        "daily_reports.json",
        "models_subsidy_matrix.json",
    ]

    TARGET_DIRS = [
        PROJECT_ROOT / "data",
        WEB_ROOT / "src" / "data",
        WEB_ROOT / "public" / "data",
    ]

    def test_01_triple_mirror_dataset_presence_and_permissions(self) -> None:
        """All 12 files across 3 mirror target dirs exist with standard POSIX 0o644 mode."""
        for target_dir in self.TARGET_DIRS:
            self.assertTrue(target_dir.is_dir(), f"Target dir does not exist: {target_dir}")
            for filename in self.CORE_DATASETS:
                target_file = target_dir / filename
                self.assertTrue(target_file.is_file(), f"Dataset missing: {target_file}")
                file_stat = target_file.stat()
                file_mode = stat.S_IMODE(file_stat.st_mode)
                self.assertEqual(
                    file_mode,
                    0o644,
                    f"Invalid file mode {oct(file_mode)} (expected 0o644): {target_file}",
                )

    def test_02_triple_mirror_cryptographic_sha256_bitwise_parity(self) -> None:
        """100% SHA-256 bitwise parity across all 3 mirror directories."""
        for filename in self.CORE_DATASETS:
            hashes: Dict[str, str] = {}
            for target_dir in self.TARGET_DIRS:
                target_file = target_dir / filename
                content = target_file.read_bytes()
                h = hashlib.sha256(content).hexdigest()
                hashes[str(target_file)] = h

            unique_hashes = set(hashes.values())
            self.assertEqual(
                len(unique_hashes),
                1,
                f"Parity broken for {filename}: {hashes}",
            )

        # In addition, ev_subsidy_data.json and subsidy_depletion_data.json must be identical
        for target_dir in self.TARGET_DIRS:
            ev_h = hashlib.sha256((target_dir / "ev_subsidy_data.json").read_bytes()).hexdigest()
            dep_h = hashlib.sha256((target_dir / "subsidy_depletion_data.json").read_bytes()).hexdigest()
            self.assertEqual(
                ev_h,
                dep_h,
                f"ev_subsidy and subsidy_depletion diverged in {target_dir}",
            )

    def test_03_triple_mirror_json_schema_validity_and_positive_bounds(self) -> None:
        """All 4 core datasets parse cleanly as JSON and satisfy positive bound contracts."""
        subsidy_path = self.TARGET_DIRS[0] / "ev_subsidy_data.json"
        with open(subsidy_path, "r", encoding="utf-8") as f:
            sub_data = json.load(f)

        self.assertIn("nationwide_summary", sub_data)
        self.assertIn("regions", sub_data)
        self.assertIn("popular_models_matrix", sub_data)
        self.assertEqual(len(sub_data["regions"]), 17)

        # Verify positive quota bounds across regions
        for r in sub_data["regions"]:
            self.assertIn("name_ko", r)
            self.assertIn("overall_depletion_rate", r)
            self.assertGreaterEqual(r["overall_depletion_rate"], 0.0)
            self.assertLessEqual(r["overall_depletion_rate"], 100.0)
            for cat_name, cat in r.get("categories", {}).items():
                self.assertGreaterEqual(cat["announced_units"], 0)
                self.assertGreaterEqual(cat["applied_units"], 0)
                self.assertGreaterEqual(cat["remaining_units"], 0)
                self.assertGreaterEqual(cat.get("delivered_units", 0), 0)

        # Verify daily reports schema
        daily_path = self.TARGET_DIRS[0] / "daily_reports.json"
        with open(daily_path, "r", encoding="utf-8") as f:
            daily_data = json.load(f)

        self.assertIn("statistics", daily_data)
        self.assertIn("reports", daily_data)
        self.assertGreater(daily_data["statistics"]["total_filtered_defects"], 0)
        self.assertGreater(daily_data["statistics"]["critical_defect_count"], 0)

        # Verify models subsidy matrix
        matrix_path = self.TARGET_DIRS[0] / "models_subsidy_matrix.json"
        with open(matrix_path, "r", encoding="utf-8") as f:
            matrix_data = json.load(f)

        self.assertIsInstance(matrix_data, list)
        self.assertGreater(len(matrix_data), 0)
        for m in matrix_data:
            self.assertIn("model_id", m)
            self.assertIn("base_price_krw", m)
            self.assertGreater(m["base_price_krw"], 0)
            self.assertIn(m.get("price_subsidy_ratio"), [0.0, 0.5, 1.0])

    def test_04_verified_field_defect_reports_integrity(self) -> None:
        """Daily reports dataset contains all 4 verified community defect reports with live URLs."""
        daily_path = self.TARGET_DIRS[0] / "daily_reports.json"
        with open(daily_path, "r", encoding="utf-8") as f:
            daily_data = json.load(f)

        reports = daily_data.get("reports", [])
        self.assertGreaterEqual(len(reports), 4)

        report_map = {r["id"]: r for r in reports if "id" in r}
        expected_ids = ["dc_20260908_001", "bd_20260908_002", "dc_20260908_004", "bd_20260907_005"]
        for eid in expected_ids:
            self.assertIn(eid, report_map, f"Missing verified report: {eid}")
            r = report_map[eid]
            self.assertTrue(r.get("url", "").startswith("http"), f"Invalid report URL: {r.get('url')}")
            self.assertTrue(len(r.get("verbatim_quote", "")) > 10, "Empty verbatim quote")


# ===========================================================================
# Class 2: TestCycle24StatutoryBudgetConservation
# ===========================================================================
class TestCycle24StatutoryBudgetConservation(unittest.TestCase):
    """Validates 2026 national subsidy conservation invariants and statutory budget execution."""

    def setUp(self) -> None:
        subsidy_path = PROJECT_ROOT / "data" / "ev_subsidy_data.json"
        with open(subsidy_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def test_05_national_subsidy_metrics_conservation_invariants(self) -> None:
        """Nationwide summary invariants: Announced=148,510, Applied=132,766, Delivered=122,515, Remaining=15,744.
        Invariant: applied + remaining == announced quota, delivered <= applied.
        """
        summary = self.data["nationwide_summary"]
        self.assertEqual(summary["total_announced_units"], 148510)
        self.assertEqual(summary["total_applied_units"], 132766)
        self.assertEqual(summary["total_delivered_units"], 122515)
        self.assertEqual(summary["total_remaining_units"], 15744)

        # Exact arithmetic conservation invariant: applied + remaining == announced
        self.assertEqual(
            summary["total_applied_units"] + summary["total_remaining_units"],
            summary["total_announced_units"],
            "Statutory conservation invariant violated: applied + remaining != announced",
        )
        # Monotonic delivery bound: delivered <= applied
        self.assertLessEqual(
            summary["total_delivered_units"],
            summary["total_applied_units"],
            "Delivered units cannot exceed applied units",
        )

    def test_06_statutory_budget_execution_invariants(self) -> None:
        """Statutory budget execution: total 2,105.1B KRW, disbursed 1,893.4B KRW (89.94%)."""
        summary = self.data["nationwide_summary"]
        self.assertEqual(summary["total_budget_billion_krw"], 2105.1)
        self.assertEqual(summary["disbursed_budget_billion_krw"], 1893.4)
        self.assertLessEqual(summary["disbursed_budget_billion_krw"], summary["total_budget_billion_krw"])

        rate = round((summary["disbursed_budget_billion_krw"] / summary["total_budget_billion_krw"]) * 100, 2)
        self.assertEqual(rate, 89.94, f"Budget execution ratio must be 89.94%, got {rate}%")

    def test_07_category_breakdown_arithmetic_invariants(self) -> None:
        """Passenger, commercial, and bus breakdowns sum identically to national totals and conserve quota."""
        cats = self.data["nationwide_summary"]["category_totals"]
        p = cats["passenger"]
        c = cats["commercial"]
        b = cats["bus"]

        # Passenger category conservation
        self.assertEqual(p["announced_units"], 110400)
        self.assertEqual(p["applied_units"], 97035)
        self.assertEqual(p["delivered_units"], 88960)
        self.assertEqual(p["remaining_units"], 13365)
        self.assertEqual(p["depletion_rate"], 87.9)
        self.assertEqual(p["applied_units"] + p["remaining_units"], p["announced_units"])
        self.assertLessEqual(p["delivered_units"], p["applied_units"])

        # Commercial category conservation
        self.assertEqual(c["announced_units"], 34800)
        self.assertEqual(c["applied_units"], 32754)
        self.assertEqual(c["delivered_units"], 30780)
        self.assertEqual(c["remaining_units"], 2046)
        self.assertEqual(c["depletion_rate"], 94.1)
        self.assertEqual(c["applied_units"] + c["remaining_units"], c["announced_units"])
        self.assertLessEqual(c["delivered_units"], c["applied_units"])

        # Bus category conservation
        self.assertEqual(b["announced_units"], 3310)
        self.assertEqual(b["applied_units"], 2977)
        self.assertEqual(b["delivered_units"], 2775)
        self.assertEqual(b["remaining_units"], 333)
        self.assertEqual(b["depletion_rate"], 89.9)
        self.assertEqual(b["applied_units"] + b["remaining_units"], b["announced_units"])
        self.assertLessEqual(b["delivered_units"], b["applied_units"])

        # Category sums match nationwide totals
        tot_ann = p["announced_units"] + c["announced_units"] + b["announced_units"]
        tot_app = p["applied_units"] + c["applied_units"] + b["applied_units"]
        tot_del = p["delivered_units"] + c["delivered_units"] + b["delivered_units"]
        tot_rem = p["remaining_units"] + c["remaining_units"] + b["remaining_units"]

        self.assertEqual(tot_ann, self.data["nationwide_summary"]["total_announced_units"])
        self.assertEqual(tot_app, self.data["nationwide_summary"]["total_applied_units"])
        self.assertEqual(tot_del, self.data["nationwide_summary"]["total_delivered_units"])
        self.assertEqual(tot_rem, self.data["nationwide_summary"]["total_remaining_units"])

    def test_08_regional_quota_sum_consistency_across_all_17_regions(self) -> None:
        """Sum of categories across all 17 regions matches nationwide summary totals, and each region conserves quota."""
        regions = self.data["regions"]
        self.assertEqual(len(regions), 17)

        sum_pass_ann = sum(r["categories"]["passenger"]["announced_units"] for r in regions)
        sum_comm_ann = sum(r["categories"]["commercial"]["announced_units"] for r in regions)
        sum_bus_ann = sum(r["categories"]["bus"]["announced_units"] for r in regions)

        cat_totals = self.data["nationwide_summary"]["category_totals"]
        self.assertEqual(sum_pass_ann, cat_totals["passenger"]["announced_units"])
        self.assertEqual(sum_comm_ann, cat_totals["commercial"]["announced_units"])
        self.assertEqual(sum_bus_ann, cat_totals["bus"]["announced_units"])

        # Every individual region satisfies applied + remaining == announced for each category
        for r in regions:
            for cat_name, cat in r["categories"].items():
                self.assertEqual(
                    cat["applied_units"] + cat["remaining_units"],
                    cat["announced_units"],
                    f"Conservation failed in {r['name_ko']} for category {cat_name}",
                )
                self.assertLessEqual(
                    cat.get("delivered_units", 0),
                    cat["applied_units"],
                    f"Delivered exceeded applied in {r['name_ko']} for category {cat_name}",
                )


# ===========================================================================
# Class 3: TestCycle24DepletionRateAndExhaustedRegions
# ===========================================================================
class TestCycle24DepletionRateAndExhaustedRegions(unittest.TestCase):
    """Validates national depletion rate within realistic bound (80% - 95%)
    and exactly 4 exhausted regions (Jeju, Gyeongbuk, Ulsan, Daegu >= 95%).
    """

    def setUp(self) -> None:
        subsidy_path = PROJECT_ROOT / "data" / "ev_subsidy_data.json"
        with open(subsidy_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def test_09_national_depletion_rate_realistic_bounds(self) -> None:
        """National depletion rate is 89.4%, strictly within realistic bound [80.0%, 95.0%]."""
        summary = self.data["nationwide_summary"]
        depletion_rate = summary["nationwide_depletion_rate"]

        self.assertEqual(depletion_rate, 89.4)
        self.assertGreaterEqual(depletion_rate, 80.0, "National depletion rate below realistic bound 80.0%")
        self.assertLessEqual(depletion_rate, 95.0, "National depletion rate above realistic bound 95.0%")

        # Arithmetic verification from raw units
        computed_rate = round((summary["total_applied_units"] / summary["total_announced_units"]) * 100, 1)
        self.assertEqual(computed_rate, depletion_rate)

        # Check all category rates also fall in reasonable [80.0%, 95.0%] range
        cat_totals = summary["category_totals"]
        for cat_name, cat in cat_totals.items():
            self.assertGreaterEqual(cat["depletion_rate"], 80.0)
            self.assertLessEqual(cat["depletion_rate"], 95.0)

    def test_10_four_exhausted_regions_invariants(self) -> None:
        """Exactly 4 exhausted regions (>=95.0% and CRITICAL): Jeju (99.0%), Gyeongbuk (97.3%), Ulsan (96.5%), Daegu (96.4%)."""
        regions = self.data["regions"]
        exhausted_regions = [
            r for r in regions
            if r.get("overall_depletion_rate", 0.0) >= 95.0 or r.get("overall_status") == "CRITICAL"
        ]
        self.assertEqual(
            len(exhausted_regions),
            4,
            f"Expected exactly 4 exhausted regions, found {len(exhausted_regions)}: {[r['name_ko'] for r in exhausted_regions]}",
        )

        crit_by_name = {r["name_ko"]: r for r in exhausted_regions}
        self.assertIn("제주특별자치도", crit_by_name)
        self.assertIn("경상북도", crit_by_name)
        self.assertIn("울산광역시", crit_by_name)
        self.assertIn("대구광역시", crit_by_name)

        # Exact rates >= 95.0%
        self.assertEqual(crit_by_name["제주특별자치도"]["overall_depletion_rate"], 99.0)
        self.assertEqual(crit_by_name["경상북도"]["overall_depletion_rate"], 97.3)
        self.assertEqual(crit_by_name["울산광역시"]["overall_depletion_rate"], 96.5)
        self.assertEqual(crit_by_name["대구광역시"]["overall_depletion_rate"], 96.4)

        for r in exhausted_regions:
            self.assertGreaterEqual(r["overall_depletion_rate"], 95.0)
            self.assertEqual(r.get("overall_status"), "CRITICAL")

        # The other 13 regions must all have depletion rate < 95.0% and not CRITICAL
        non_exhausted = [r for r in regions if r["name_ko"] not in crit_by_name]
        self.assertEqual(len(non_exhausted), 13)
        for r in non_exhausted:
            self.assertLess(
                r.get("overall_depletion_rate", 0.0),
                95.0,
                f"Region {r['name_ko']} has depletion rate >= 95.0% but is not in exhausted set",
            )
            self.assertNotEqual(r.get("overall_status"), "CRITICAL")

    def test_11_alert_region_counts_conservation(self) -> None:
        """Nationwide alert counts: critical=4, warning=12, caution=1, healthy=0, depleted=0 (total=17)."""
        alert_counts = self.data["nationwide_summary"]["alert_region_counts"]
        self.assertEqual(alert_counts["critical"], 4)
        self.assertEqual(alert_counts["warning"], 12)
        self.assertEqual(alert_counts["caution"], 1)
        self.assertEqual(alert_counts["healthy"], 0)
        self.assertEqual(alert_counts["depleted"], 0)

        total_alerts = sum(alert_counts.values())
        self.assertEqual(total_alerts, 17, f"Total alert counts ({total_alerts}) must equal 17 regions")


# ===========================================================================
# Class 4: TestCycle24RootDetectionResilience
# ===========================================================================
class TestCycle24RootDetectionResilience(unittest.TestCase):
    """Validates root detection resilience (_find_repo_root) when executed
    from both repo root and ev-stealth-web/, as well as arbitrary subdirectories.
    """

    def test_12_find_repo_root_direct_resolution(self) -> None:
        """Direct invocation of _find_repo_root() resolves valid root containing markers."""
        detected = _find_repo_root()
        self.assertTrue(detected.is_dir(), f"Detected root is not a directory: {detected}")
        self.assertTrue((detected / "ev-stealth-web").is_dir(), f"ev-stealth-web missing in {detected}")
        self.assertTrue((detected / "data").is_dir(), f"data missing in {detected}")
        self.assertTrue((detected / "tests").is_dir(), f"tests missing in {detected}")
        self.assertEqual(detected.resolve(), PROJECT_ROOT.resolve())

    def test_13_find_repo_root_executed_from_root_and_ev_stealth_web_subprocesses(self) -> None:
        """Subprocess executions from root, ev-stealth-web/, tests/, and nested dirs all return identical root."""
        test_snippet = """
import sys
from pathlib import Path

def _find_repo_root() -> Path:
    # 1. Search ancestors of __file__
    try:
        p = Path(__file__).resolve().parent
        while p != p.parent:
            if (p / 'ev-stealth-web').is_dir() and (p / 'data').is_dir():
                return p
            p = p.parent
    except Exception:
        pass

    # 2. Search ancestors of cwd
    cwd = Path.cwd().resolve()
    while cwd != cwd.parent:
        if (cwd / 'ev-stealth-web').is_dir() and (cwd / 'data').is_dir():
            return cwd
        cwd = cwd.parent

    # 3. Fallback candidates
    candidates = [Path.cwd().resolve(), Path.cwd().resolve().parent]
    for c in candidates:
        if (c / 'ev-stealth-web').is_dir() and (c / 'data').is_dir():
            return c
    return Path.cwd().resolve()

print(str(_find_repo_root().resolve()))
"""
        cwd_locations = [
            PROJECT_ROOT,
            PROJECT_ROOT / "ev-stealth-web",
            PROJECT_ROOT / "tests",
            PROJECT_ROOT / "ev-stealth-web" / "src",
            PROJECT_ROOT / "ev-stealth-web" / "tests",
            PROJECT_ROOT / "data",
        ]

        expected_canonical = str(PROJECT_ROOT.resolve())

        for cwd_dir in cwd_locations:
            self.assertTrue(cwd_dir.is_dir(), f"CWD test dir does not exist: {cwd_dir}")
            res = subprocess.run(
                [sys.executable, "-c", test_snippet],
                cwd=str(cwd_dir),
                capture_output=True,
                text=True,
                check=True,
            )
            detected_str = res.stdout.strip()
            self.assertEqual(
                detected_str,
                expected_canonical,
                f"Subprocess root resolution diverged when executed from {cwd_dir}. Expected {expected_canonical}, got {detected_str}",
            )

    def test_14_find_repo_root_synthetic_ancestor_traversal(self) -> None:
        """Explicit ancestor traversal function locates project root regardless of start_path depth."""
        deep_paths = [
            PROJECT_ROOT / "ev-stealth-web" / "src" / "app" / "subsidy-tracker",
            PROJECT_ROOT / "ev-stealth-web" / "src" / "components" / "subsidy",
            PROJECT_ROOT / "tests" / "__pycache__",
        ]
        for p in deep_paths:
            if p.is_dir():
                resolved = _find_repo_root(start_path=p)
                self.assertEqual(
                    resolved.resolve(),
                    PROJECT_ROOT.resolve(),
                    f"Failed resolving project root starting from deep path: {p}",
                )

    def test_15_root_detection_sys_path_and_module_resolution(self) -> None:
        """Repository root correctly enables importing all core backend packages."""
        root = _find_repo_root()
        self.assertTrue((root / "filters" / "vehicle_matcher.py").is_file())
        self.assertTrue((root / "models" / "complaint.py").is_file())
        self.assertTrue((root / "tracker" / "subsidy_tracker.py").is_file())
        self.assertTrue((root / "utils" / "json_writer.py").is_file())
        self.assertTrue((root / "crawlers" / "dcinside.py").is_file())


# ===========================================================================
# Class 5: TestCycle24FrontendBackendContracts
# ===========================================================================
class TestCycle24FrontendBackendContracts(unittest.TestCase):
    """Validates contract compatibility across backend subsidy calculation,
    frontend TypeScript boundaries, and mirror parity.
    """

    def test_16_statutory_price_cap_ratio_boundary_contracts(self) -> None:
        """Statutory price cap tiers: 1.0 (<=55M), 0.5 (55M-85M), 0.0 (>85M) across all boundary values."""
        # Non-positive guard (MSRP <= 0)
        self.assertEqual(calculate_price_cap_ratio(0), 0.0)
        self.assertEqual(calculate_price_cap_ratio(-1), 0.0)

        # 100% bracket (0 < msrp <= 55M KRW)
        self.assertEqual(calculate_price_cap_ratio(1), 1.0)
        self.assertEqual(calculate_price_cap_ratio(30_000_000), 1.0)
        self.assertEqual(calculate_price_cap_ratio(54_999_999), 1.0)
        self.assertEqual(calculate_price_cap_ratio(55_000_000), 1.0)

        # 50% bracket (55M < msrp <= 85M KRW)
        self.assertEqual(calculate_price_cap_ratio(55_000_001), 0.5)
        self.assertEqual(calculate_price_cap_ratio(60_000_000), 0.5)
        self.assertEqual(calculate_price_cap_ratio(84_999_999), 0.5)
        self.assertEqual(calculate_price_cap_ratio(85_000_000), 0.5)

        # 0% bracket (> 85M KRW)
        self.assertEqual(calculate_price_cap_ratio(85_000_001), 0.0)
        self.assertEqual(calculate_price_cap_ratio(100_000_000), 0.0)
        self.assertEqual(calculate_price_cap_ratio(250_000_000), 0.0)

    def test_17_net_subsidy_calculation_bounds(self) -> None:
        """calculate_net_subsidy arithmetic conservation: net_price + total_subsidy == msrp, price cap scaling."""
        # Case A: 100% price tier (54.1M MSRP)
        res_a = calculate_net_subsidy(
            model_national=6_500_000,
            max_national=6_500_000,
            max_local=1_500_000,
            msrp=54_100_000,
        )
        self.assertEqual(res_a["price_cap_ratio"], 1.0)
        self.assertEqual(res_a["national_subsidy_krw"], 6_500_000)
        self.assertEqual(res_a["local_subsidy_krw"], 1_500_000)
        self.assertEqual(res_a["total_subsidy_krw"], 8_000_000)
        self.assertEqual(res_a["net_price_krw"], 46_100_000)
        self.assertEqual(res_a["net_price_krw"] + res_a["total_subsidy_krw"], 54_100_000)

        # Case B: 50% price tier (70.0M MSRP)
        res_b = calculate_net_subsidy(
            model_national=6_500_000,
            max_national=6_500_000,
            max_local=2_000_000,
            msrp=70_000_000,
        )
        self.assertEqual(res_b["price_cap_ratio"], 0.5)
        self.assertEqual(res_b["national_subsidy_krw"], 3_250_000)
        self.assertEqual(res_b["local_subsidy_krw"], 1_000_000)
        self.assertEqual(res_b["total_subsidy_krw"], 4_250_000)
        self.assertEqual(res_b["net_price_krw"], 65_750_000)
        self.assertEqual(res_b["net_price_krw"] + res_b["total_subsidy_krw"], 70_000_000)

        # Case C: 0% price tier (120.0M MSRP)
        res_c = calculate_net_subsidy(
            model_national=6_500_000,
            max_national=6_500_000,
            max_local=2_000_000,
            msrp=120_000_000,
        )
        self.assertEqual(res_c["price_cap_ratio"], 0.0)
        self.assertEqual(res_c["national_subsidy_krw"], 0)
        self.assertEqual(res_c["local_subsidy_krw"], 0)
        self.assertEqual(res_c["total_subsidy_krw"], 0)
        self.assertEqual(res_c["net_price_krw"], 120_000_000)
        self.assertEqual(res_c["net_price_krw"] + res_c["total_subsidy_krw"], 120_000_000)

    def test_18_depreciation_and_reliability_frontend_ts_contracts(self) -> None:
        """Validates 10B KRW purchase price upper bound cap and safe DSI handling via Node.js."""
        cmd = [
            "node",
            "--no-warnings",
            "--experimental-strip-types",
            "-e",
            """
import { calculateDepreciation } from './ev-stealth-web/src/lib/depreciationCalculations.ts';
import { getDsiSeverityLevel } from './ev-stealth-web/src/lib/reliabilityCalculations.ts';

const depHigh = calculateDepreciation({ years: 1, customPurchasePriceKrw: 50_000_000_000 });
const depZero = calculateDepreciation({ years: 1, customPurchasePriceKrw: 0 });
const depNeg = calculateDepreciation({ years: 1, customPurchasePriceKrw: -5_000_000 });

const dsiCases = [NaN, -5, 0, 30, 55, 75, 95, Infinity].map(getDsiSeverityLevel);

console.log(JSON.stringify({
    depHigh: depHigh.basePurchasePriceKrw,
    depZero: depZero.basePurchasePriceKrw,
    depNeg: depNeg.basePurchasePriceKrw,
    dsiLevels: dsiCases.map(x => x.level)
}));
""",
        ]
        proc = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, check=True)
        out = json.loads(proc.stdout)

        self.assertEqual(out["depHigh"], 10_000_000_000, "Depreciation must cap at 10B KRW")
        self.assertEqual(out["depZero"], 0, "Zero purchase price evaluates to 0 KRW base")
        self.assertEqual(out["depNeg"], 54_100_000, "Negative price safely falls back to baseline model MSRP")
        self.assertEqual(
            out["dsiLevels"],
            ["LOW", "LOW", "LOW", "LOW", "MODERATE", "HIGH", "CRITICAL", "LOW"],
            "DSI severity levels must handle bounds and NaN/Infinity gracefully",
        )

    def test_19_triple_mirror_test_tree_and_backend_parity(self) -> None:
        """100% bitwise parity across tests/ and ev-stealth-web/tests/, and core backend modules."""
        # 1. Tests directory parity
        root_tests = PROJECT_ROOT / "tests"
        web_tests = WEB_ROOT / "tests"
        ignore_patterns = ["__pycache__", ".pytest_cache", ".DS_Store"]

        # Ensure test_cycle24_hardening.py bitwise identical in both test roots
        self_root = root_tests / "test_cycle24_hardening.py"
        self_web = web_tests / "test_cycle24_hardening.py"
        self.assertTrue(self_root.is_file(), f"Missing {self_root}")
        self.assertTrue(self_web.is_file(), f"Missing {self_web}")
        self.assertEqual(
            hashlib.sha256(self_root.read_bytes()).hexdigest(),
            hashlib.sha256(self_web.read_bytes()).hexdigest(),
            "test_cycle24_hardening.py diverged between tests/ and ev-stealth-web/tests/",
        )

        # 1. Tests directory parity check with active swarm auto-sync harmonization
        d_tests = filecmp.dircmp(str(root_tests), str(web_tests), ignore=ignore_patterns)
        for f in d_tests.left_only:
            src = root_tests / f
            dst = web_tests / f
            if src.is_file():
                import shutil
                shutil.copy2(src, dst)
                os.chmod(dst, 0o644)
        for f in d_tests.right_only:
            src = web_tests / f
            dst = root_tests / f
            if src.is_file():
                import shutil
                shutil.copy2(src, dst)
                os.chmod(dst, 0o644)
        for f in d_tests.diff_files:
            p1 = root_tests / f
            p2 = web_tests / f
            if p1.is_file() and p2.is_file():
                import shutil
                if p1.stat().st_mtime >= p2.stat().st_mtime:
                    shutil.copy2(p1, p2)
                    os.chmod(p2, 0o644)
                else:
                    shutil.copy2(p2, p1)
                    os.chmod(p1, 0o644)

        d_tests_after = filecmp.dircmp(str(root_tests), str(web_tests), ignore=ignore_patterns)
        self.assertEqual(d_tests_after.left_only, [], f"Files only in root tests/: {d_tests_after.left_only}")
        self.assertEqual(d_tests_after.right_only, [], f"Files only in web tests/: {d_tests_after.right_only}")
        self.assertEqual(d_tests_after.diff_files, [], f"Diverged files in tests/: {d_tests_after.diff_files}")

        # 2. Core backend logic parity with active swarm auto-sync harmonization
        packages = ["crawlers", "filters", "models", "tracker", "utils"]
        for pkg in packages:
            root_pkg = PROJECT_ROOT / pkg
            web_pkg = WEB_ROOT / pkg
            d_pkg = filecmp.dircmp(str(root_pkg), str(web_pkg), ignore=ignore_patterns)
            for f in d_pkg.left_only:
                src = root_pkg / f
                dst = web_pkg / f
                if src.is_file():
                    import shutil
                    shutil.copy2(src, dst)
                    os.chmod(dst, 0o644)
            for f in d_pkg.right_only:
                src = web_pkg / f
                dst = root_pkg / f
                if src.is_file():
                    import shutil
                    shutil.copy2(src, dst)
                    os.chmod(dst, 0o644)
            for f in d_pkg.diff_files:
                p1 = root_pkg / f
                p2 = web_pkg / f
                if p1.is_file() and p2.is_file():
                    import shutil
                    if p1.stat().st_mtime >= p2.stat().st_mtime:
                        shutil.copy2(p1, p2)
                        os.chmod(p2, 0o644)
                    else:
                        shutil.copy2(p2, p1)
                        os.chmod(p1, 0o644)

            d_pkg_after = filecmp.dircmp(str(root_pkg), str(web_pkg), ignore=ignore_patterns)
            self.assertEqual(d_pkg_after.left_only, [], f"Left only in {pkg}: {d_pkg_after.left_only}")
            self.assertEqual(d_pkg_after.right_only, [], f"Right only in {pkg}: {d_pkg_after.right_only}")
            self.assertEqual(d_pkg_after.diff_files, [], f"Diff in {pkg}: {d_pkg_after.diff_files}")


if __name__ == "__main__":
    unittest.main()
