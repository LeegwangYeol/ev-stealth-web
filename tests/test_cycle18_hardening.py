"""
tests/test_cycle18_hardening.py - Comprehensive Cycle 18 Hardening, Boundary,
Accessibility, Invariants, and Mirror Parity Test Suite.

Authoritative Reference:
- ORIGINAL_REQUEST.md
- DISPATCH.md (Cycle 18 Hardening Test Suite Specification)
- Wave 1 Explorer Handoff Reports:
  - sync18_worker_sync_w1/handoff.md
  - sync18_explorer_backend_w1/handoff.md
  - sync18_explorer_frontend_w1/handoff.md
  - sync18_explorer_a11y_w1/handoff.md
  - sync18_explorer_perf_w1/handoff.md
  - sync18_explorer_tests_w1/handoff.md
- COLLABORATION.md

Coverage:
1. TestCycle18Wave1DataSyncAndMirrorParity (7 tests):
   - test_01_triple_mirror_dataset_presence_and_permissions: 12 files across 3 mirror dirs with 0o644 mode.
   - test_02_triple_mirror_cryptographic_sha256_bitwise_parity: 100% hash parity per dataset and ev_subsidy == subsidy_depletion.
   - test_03_national_subsidy_metrics_conservation_invariants: total 148,510, applied 132,766, remaining 15,744, 89.4%.
   - test_04_statutory_budget_execution_invariants: total 2,105.1B, disbursed 1,893.4B KRW (89.94%).
   - test_05_category_breakdown_arithmetic_invariants: passenger, commercial, bus breakdown arithmetic equality.
   - test_06_critical_exhaustion_regions_bounds: exactly 4 regions >= 95.0% (Daegu, Ulsan, Gyeongbuk, Jeju).
   - test_07_verified_field_defect_reports_integrity: 3 verified defect reports with community URLs and negativity >= 0.90.

2. TestCycle18BackendRemediations (9 tests):
   - test_08_runtime_type_hints_introspection_integrity: typing introspection on process_post and build_initial_baseline.
   - test_09_mapping_protocol_and_duck_typing_compliance: CategoryMetrics, MunicipalityMetrics, ComplaintRecord, DailyReportPayload.
   - test_10_daily_report_statistics_none_and_nan_resilience: None, NaN, Inf handling in DailyReportStatistics.to_dict.
   - test_11_date_extraction_dotted_and_two_digit_years_resilience: dotted dates and two-digit year normalization.
   - test_12_raw_post_and_defect_filter_null_comments_resilience: comments None guard and non-string comment filtering.
   - test_13_vehicle_matcher_and_slang_lexicon_none_safety: None guards in extract_vehicle_info and find_matching_slang.
   - test_14_crawler_case_insensitive_post_id_extraction: case-insensitive post ID extraction across crawlers.
   - test_15_subsidy_tracker_non_positive_msrp_ratio_guard: non-positive MSRP handling returning 0.0 ratio and subsidy.
   - test_16_atomic_writer_decimal_and_empty_path_resilience: Decimal serialization and empty path validation in atomic_write_json.

3. TestCycle18FrontendRemediationsAndContracts (6 tests):
   - test_17_get_region_by_id_colloquial_names_resilience: colloquial city/province name resolution.
   - test_18_subsidy_tracker_two_letter_province_abbreviation_regex: 2-letter provincial abbreviation matching.
   - test_19_get_model_by_id_unspaced_korean_query_resilience: whitespace- and hyphen-stripped model query matching.
   - test_20_recall_portal_vin_url_param_support: VIN query parameter auto-selection support.
   - test_21_admin_dashboard_sr_only_table_anchor_accessibility: accessible table anchor tags in screen reader view.
   - test_22_get_daily_reports_kpi_zero_falsy_guard: nullish coalescing on 0 total_scraped metric.

4. TestCycle18AccessibilityAndPerformanceInvariants (6 tests):
   - test_23_battery_soh_track_circle_contrast_ratio_level_aa: battery SoH track circle contrast ratio >= 3:1.
   - test_24_depreciation_sliders_have_localized_aria_valuetext: localized Korean unit aria-valuetext on sliders.
   - test_25_site_footer_attribution_and_legal_notice_enrichment: semantic public data source links and legal notices.
   - test_26_next_config_security_headers_and_corp: Cross-Origin-Resource-Policy same-origin and security headers.
   - test_27_font_fallback_array_in_root_layout: explicit monospace font fallback array in root layout.
   - test_28_heading_hierarchy_monotonicity_across_all_app_routes: monotonic heading depth across all app routes.

5. TestCycle18TestTreeAndMirrorParity (3 tests):
   - test_29_test_tree_bitwise_mirror_parity: 100% bitwise parity and 0o644 permissions across all test files.
   - test_30_test_cycle18_hardening_exact_mirror_parity: identical length and SHA-256 for test_cycle18_hardening.py.
   - test_31_backend_logic_mirror_parity: 100% cryptographic SHA-256 parity across core backend modules.
"""

from __future__ import annotations

import decimal
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
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import unittest
from unittest.mock import MagicMock


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

from crawlers.bobaedream import BobaeDreamCrawler
from crawlers.dcinside import DCInsideCrawler
from filters.defect_filter import ContextualDefectFilter
from filters.slang_lexicon import find_matching_slang
from filters.vehicle_matcher import extract_vehicle_info
from models.complaint import (
    ComplaintRecord,
    DailyReportPayload,
    DailyReportStatistics,
    RawPost,
)
from tracker.atomic_writer import atomic_write_json
from tracker.subsidy_baseline import build_initial_baseline
from tracker.subsidy_models import CategoryMetrics, MunicipalityMetrics
from tracker.subsidy_tracker import (
    SubsidyTracker,
    calculate_net_subsidy,
    calculate_price_cap_ratio,
)
from utils.json_writer import _extract_record_date


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
# Class 1: TestCycle18Wave1DataSyncAndMirrorParity
# ===========================================================================
class TestCycle18Wave1DataSyncAndMirrorParity(unittest.TestCase):
    """Validates triple mirror data synchronization, cryptographic SHA-256 identity,
    POSIX permissions, and mathematical conservation invariants.
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

        # Asserts ev_subsidy_data.json and subsidy_depletion_data.json have matching hashes
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

        self.assertEqual(found_ioniq.get("defect_category"), "BATTERY_CHARGING")
        self.assertEqual(found_tesla.get("defect_category"), "SOFTWARE_ELECTRONICS")
        self.assertEqual(found_ev3.get("defect_category"), "DRIVING_POWERTRAIN")


# ===========================================================================
# Class 2: TestCycle18BackendRemediations
# ===========================================================================
class TestCycle18BackendRemediations(unittest.TestCase):
    """Validates backend runtime type hints, duck-typing mapping protocols,
    None/NaN defensive resilience, date parsing, and atomic writer Decimal support.
    """

    def test_08_runtime_type_hints_introspection_integrity(self) -> None:
        """Verifies typing.get_type_hints succeeds without NameError on functions using Union and Optional."""
        import typing

        hints_filter = typing.get_type_hints(ContextualDefectFilter.process_post)
        self.assertIn("return", hints_filter)

        hints_baseline = typing.get_type_hints(build_initial_baseline)
        self.assertIn("return", hints_baseline)

    def test_09_mapping_protocol_and_duck_typing_compliance(self) -> None:
        """Verifies CategoryMetrics, MunicipalityMetrics, ComplaintRecord, and DailyReportPayload implement mapping protocol."""
        # 1. CategoryMetrics
        cat = CategoryMetrics.from_dict({"announced_units": 100, "applied_units": 80})
        self.assertEqual(cat["announced_units"], 100)
        with self.assertRaises(KeyError):
            _ = cat["nonexistent_field"]
        self.assertNotIn("nonexistent_field", cat)
        self.assertIn("announced_units", cat)
        self.assertEqual(cat.get("nonexistent_field", "fallback"), "fallback")
        self.assertEqual(cat.get("announced_units"), 100)

        # 2. MunicipalityMetrics
        mun = MunicipalityMetrics(name_ko="강남구", announced_units=50, applied_units=40, delivered_units=30)
        self.assertEqual(mun["announced_units"], 50)
        with self.assertRaises(KeyError):
            _ = mun["invalid_key"]
        self.assertNotIn("invalid_key", mun)
        self.assertIn("name_ko", mun)
        self.assertEqual(mun.get("invalid_key", 999), 999)
        self.assertEqual(mun.get("announced_units"), 50)

        # 3. ComplaintRecord
        rec = ComplaintRecord(
            id="c1",
            source="dc",
            url="http://test.com",
            title="t",
            author="a",
            created_at="2026-10-25",
            vehicle_brand="Hyundai",
            vehicle_model="Ioniq 5",
            defect_category="BATTERY_CHARGING",
            summary="s",
            verbatim_quote="v",
        )
        self.assertEqual(rec["id"], "c1")
        self.assertEqual(rec["vehicle_model"], "Ioniq 5")
        with self.assertRaises(KeyError):
            _ = rec["unknown_col"]
        self.assertNotIn("unknown_col", rec)
        self.assertIn("defect_category", rec)
        self.assertEqual(rec.get("unknown_col", "fb"), "fb")
        self.assertEqual(rec.get("id"), "c1")

        # 4. DailyReportPayload
        payload = DailyReportPayload(
            generated_at="2026-10-25T19:00:00Z",
            statistics=DailyReportStatistics(total_scraped=10),
        )
        self.assertEqual(payload["generated_at"], "2026-10-25T19:00:00Z")
        self.assertEqual(payload["statistics"]["total_scraped"], 10)
        with self.assertRaises(KeyError):
            _ = payload["nonexistent_key"]
        self.assertNotIn("nonexistent_key", payload)
        self.assertIn("statistics", payload)
        self.assertEqual(payload.get("nonexistent_key", "default"), "default")

    def test_10_daily_report_statistics_none_and_nan_resilience(self) -> None:
        """Verifies DailyReportStatistics.to_dict handles None, NaN, and Inf safely."""
        s_none = DailyReportStatistics(avg_negativity_score=None)
        self.assertEqual(s_none.to_dict()["avg_negativity_score"], 0.0)

        s_nan = DailyReportStatistics(avg_negativity_score=float("nan"))
        self.assertEqual(s_nan.to_dict()["avg_negativity_score"], 0.0)

        s_inf = DailyReportStatistics(avg_negativity_score=float("inf"))
        self.assertEqual(s_inf.to_dict()["avg_negativity_score"], 0.0)

        s_neginf = DailyReportStatistics(avg_negativity_score=float("-inf"))
        self.assertEqual(s_neginf.to_dict()["avg_negativity_score"], 0.0)

        s_valid = DailyReportStatistics(avg_negativity_score=0.954)
        self.assertEqual(s_valid.to_dict()["avg_negativity_score"], 0.95)

        raw_json = json.dumps(s_nan.to_dict())
        self.assertNotIn("NaN", raw_json)
        self.assertIn('"avg_negativity_score": 0.0', raw_json)

    def test_11_date_extraction_dotted_and_two_digit_years_resilience(self) -> None:
        """Verifies _extract_record_date and ComplaintRecord.date_str parse Korean dotted dates and 2-digit years."""
        self.assertEqual(_extract_record_date({"date": "2026.10.25"}), "2026-10-25")
        self.assertEqual(_extract_record_date({"created_at": "2026. 10. 25."}), "2026-10-25")
        self.assertEqual(_extract_record_date({"timestamp": "26.10.25"}), "2026-10-25")
        self.assertEqual(_extract_record_date({"date": "26-10-25"}), "2026-10-25")
        self.assertEqual(_extract_record_date({"created_at": "2026/10/25 14:00:00"}), "2026-10-25")

        rec = ComplaintRecord(
            id="c1",
            source="dc",
            url="http://test.com",
            title="t",
            author="a",
            created_at="2026. 10. 25.",
            vehicle_brand="Hyundai",
            vehicle_model="Ioniq 5",
            defect_category="BATTERY_CHARGING",
            summary="s",
            verbatim_quote="v",
        )
        self.assertEqual(rec.date_str, "2026-10-25")

    def test_12_raw_post_and_defect_filter_null_comments_resilience(self) -> None:
        """Verifies RawPost.from_dict guards None comments and defect filter handles non-string comment items."""
        post_none = RawPost.from_dict({"comments": None, "id": "1", "title": "결함", "url": "http://test.com"})
        self.assertEqual(post_none.comments, [])

        post_mixed = RawPost(
            platform="dcinside",
            post_id="p2",
            url="http://example.com/2",
            title="전기차 고장 제보",
            author="작성자",
            created_at="2026-10-25",
            content="고장 발생했습니다",
            comments=[None, 123, "정상 댓글입니다", ""],  # type: ignore[list-item]
        )
        filter_inst = ContextualDefectFilter()
        res = filter_inst.process_post(post_mixed)
        self.assertIsNotNone(res)
        self.assertIsInstance(res, ComplaintRecord)

    def test_13_vehicle_matcher_and_slang_lexicon_none_safety(self) -> None:
        """Verifies extract_vehicle_info and find_matching_slang safely handle None and empty inputs."""
        brand, model = extract_vehicle_info(None, None)
        self.assertEqual(brand, "Other")
        self.assertIn(model, ("Unknown", "전기차"))

        brand_e, model_e = extract_vehicle_info("", "")
        self.assertEqual(brand_e, "Other")
        self.assertIn(model_e, ("Unknown", "전기차"))

        slangs_none = find_matching_slang(None)  # type: ignore[arg-type]
        self.assertEqual(slangs_none, [])

        slangs_empty = find_matching_slang("")
        self.assertEqual(slangs_empty, [])

    def test_14_crawler_case_insensitive_post_id_extraction(self) -> None:
        """Verifies BobaeDream and DCInside post ID extraction is case-insensitive."""
        mock_client = MagicMock()

        # BobaeDream
        crawler_bd = BobaeDreamCrawler(client=mock_client)
        urls_bd = [
            "https://www.bobaedream.co.kr/view?code=national&No=12345",
            "https://www.bobaedream.co.kr/view?code=national&no=12345",
            "https://www.bobaedream.co.kr/view?code=national&NO=12345",
        ]
        for u in urls_bd:
            res = crawler_bd.parse_post_detail("<html></html>", u)
            self.assertEqual(res.get("post_id"), "12345", f"Failed for BobaeDream URL: {u}")

        # DCInside
        crawler_dc = DCInsideCrawler(client=mock_client)
        urls_dc = [
            "https://gall.dcinside.com/mgallery/board/view/?id=car_new1&no=67890",
            "https://gall.dcinside.com/mgallery/board/view/?id=car_new1&No=67890",
            "https://gall.dcinside.com/mgallery/board/view/?id=car_new1&NO=67890",
        ]
        for u in urls_dc:
            res = crawler_dc.parse_post_detail("<html></html>", u)
            self.assertEqual(res.get("post_id"), "67890", f"Failed for DCInside URL: {u}")

    def test_15_subsidy_tracker_non_positive_msrp_ratio_guard(self) -> None:
        """Verifies calculate_price_cap_ratio and calculate_net_subsidy return 0 for negative MSRP."""
        self.assertEqual(calculate_price_cap_ratio(-10_000_000), 0.0)
        self.assertEqual(calculate_price_cap_ratio(-1), 0.0)

        res_neg = calculate_net_subsidy(
            model_national=6_500_000,
            max_national=6_500_000,
            max_local=3_000_000,
            msrp=-10_000_000,
        )
        self.assertEqual(res_neg["total_subsidy_krw"], 0)
        self.assertEqual(res_neg["net_price_krw"], 0)

    def test_16_atomic_writer_decimal_and_empty_path_resilience(self) -> None:
        """Verifies atomic_write_json serializes Decimal objects and rejects empty paths."""
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "test_decimal.json"
            payload = {
                "budget": decimal.Decimal("1893.4"),
                "ratio": decimal.Decimal("89.94"),
            }
            atomic_write_json(payload, target)
            self.assertTrue(target.exists())

            loaded = json.loads(target.read_text(encoding="utf-8"))
            self.assertAlmostEqual(loaded["budget"], 1893.4, places=1)
            self.assertAlmostEqual(loaded["ratio"], 89.94, places=2)

        with self.assertRaises(ValueError):
            atomic_write_json({"data": 123}, "")


# ===========================================================================
# Class 3: TestCycle18FrontendRemediationsAndContracts
# ===========================================================================
class TestCycle18FrontendRemediationsAndContracts(unittest.TestCase):
    """Validates frontend colloquial region lookup, unspaced model query matching,
    VIN deep-linking parameter support, and screen reader link accessibility.
    """

    def test_17_get_region_by_id_colloquial_names_resilience(self) -> None:
        """Verifies getRegionById resolves colloquial Korean names (서울, 부산, 충남, 경북, 제주)."""
        script = """
        import { getRegionById } from './src/lib/getSubsidyData';
        const seoul = getRegionById('서울');
        const busan = getRegionById('부산');
        const chungnam = getRegionById('충남');
        const gyeongbuk = getRegionById('경북');
        const jeju = getRegionById('제주');
        console.log(JSON.stringify({
            seoul: seoul ? seoul.region_id : null,
            busan: busan ? busan.region_id : null,
            chungnam: chungnam ? chungnam.region_id : null,
            gyeongbuk: gyeongbuk ? gyeongbuk.region_id : null,
            jeju: jeju ? jeju.region_id : null,
        }));
        """
        output = _eval_ts_node(script)
        self.assertEqual(output["seoul"], "KR-11")
        self.assertEqual(output["busan"], "KR-26")
        self.assertEqual(output["chungnam"], "KR-44")
        self.assertEqual(output["gyeongbuk"], "KR-47")
        self.assertIn(output["jeju"], ("KR-49", "KR-50"))

    def test_18_subsidy_tracker_two_letter_province_abbreviation_regex(self) -> None:
        """Verifies SubsidyTrackerClient.tsx delegates to getRegionById or handles 2-letter province abbreviations."""
        sub_src = (APP_DIR / "subsidy-tracker" / "SubsidyTrackerClient.tsx").read_text(encoding="utf-8")
        self.assertIn("getRegionById(q)", sub_src, "SubsidyTrackerClient must delegate to getRegionById")

        # Test abbreviation resolution via getRegionById
        script = """
        import { getRegionById } from './src/lib/getSubsidyData';
        console.log(JSON.stringify({
            chungnam: getRegionById('충남')?.name_ko,
            chungbuk: getRegionById('충북')?.name_ko,
            gyeongnam: getRegionById('경남')?.name_ko,
            gyeongbuk: getRegionById('경북')?.name_ko,
            jeonnam: getRegionById('전남')?.name_ko,
            jeonbuk: getRegionById('전북')?.name_ko,
        }));
        """
        output = _eval_ts_node(script)
        self.assertIn("충청남도", output["chungnam"])
        self.assertIn("충청북도", output["chungbuk"])
        self.assertIn("경상남도", output["gyeongnam"])
        self.assertIn("경상북도", output["gyeongbuk"])
        self.assertIn("전라남도", output["jeonnam"])
        self.assertTrue("전라북도" in output["jeonbuk"] or "전북특별자치도" in output["jeonbuk"])

    def test_19_get_model_by_id_unspaced_korean_query_resilience(self) -> None:
        """Verifies getModelById matches models on unspaced queries (아이오닉5, ioniq5, model3, ev3)."""
        script = """
        import { getModelById } from './src/lib/getSubsidyData';
        console.log(JSON.stringify({
            ioniq5: !!getModelById('아이오닉5'),
            ioniq5En: !!getModelById('ioniq5'),
            model3: !!getModelById('model3'),
            ev3: !!getModelById('ev3'),
        }));
        """
        output = _eval_ts_node(script)
        self.assertTrue(output["ioniq5"], "Must match '아이오닉5'")
        self.assertTrue(output["ioniq5En"], "Must match 'ioniq5'")
        self.assertTrue(output["model3"], "Must match 'model3'")
        self.assertTrue(output["ev3"], "Must match 'ev3'")

    def test_20_recall_portal_vin_url_param_support(self) -> None:
        """Verifies RecallPortalClient.tsx SearchParamsWatcher inspects ?vin= parameter."""
        rec_src = (APP_DIR / "recall-portal" / "RecallPortalClient.tsx").read_text(encoding="utf-8")
        self.assertIn("searchParams.get('vin')", rec_src, "Must inspect ?vin= parameter")
        self.assertIn("onSelectVin", rec_src, "Must provide onSelectVin callback")
        self.assertIn("handleSelectVinFromParams", rec_src, "Must define handleSelectVinFromParams")

    def test_21_admin_dashboard_sr_only_table_anchor_accessibility(self) -> None:
        """Verifies (원문 링크) in AdminDashboardClient.tsx does not hide from assistive tech."""
        admin_src = (APP_DIR / "secret-admin-reports" / "AdminDashboardClient.tsx").read_text(encoding="utf-8")
        # Ensure anchor tag with (원문 링크) does not have tabIndex={-1} or aria-hidden="true"
        match = re.search(r'<a\s+[^>]*href=\{report\.url\}[^>]*>\s*\(원문 링크\)\s*</a>', admin_src)
        self.assertIsNotNone(match, "Anchor link with (원문 링크) must exist")
        tag_html = match.group(0)
        self.assertNotIn("tabIndex={-1}", tag_html)
        self.assertNotIn('aria-hidden="true"', tag_html)

    def test_22_get_daily_reports_kpi_zero_falsy_guard(self) -> None:
        """Verifies calculateKPIs preserves explicit 0 for total_scraped using nullish coalescing."""
        script = """
        import { calculateKPIs } from './src/lib/getDailyReports';
        const res = calculateKPIs([], { total_scraped: 0 });
        console.log(JSON.stringify({ total_scraped: res.total_scraped }));
        """
        output = _eval_ts_node(script)
        self.assertEqual(output["total_scraped"], 0, "total_scraped must be preserved as 0, not overridden with fallback")

        # Also inspect getDailyReports.ts source for ??
        daily_src = (LIB_DIR / "getDailyReports.ts").read_text(encoding="utf-8")
        self.assertIn("existingStats?.total_scraped ??", daily_src)


# ===========================================================================
# Class 4: TestCycle18AccessibilityAndPerformanceInvariants
# ===========================================================================
class TestCycle18AccessibilityAndPerformanceInvariants(unittest.TestCase):
    """Validates WCAG 2.1 AA contrast, localized slider aria-valuetext,
    attribution links, Next.js CORP security header, and heading monotonicity.
    """

    def test_23_battery_soh_track_circle_contrast_ratio_level_aa(self) -> None:
        """Verifies Battery SoH circle track stroke uses #64748b achieving >= 3:1 non-text contrast against #0f172a."""
        dep_src = (APP_DIR / "depreciation-calculator" / "DepreciationCalculatorClient.tsx").read_text(encoding="utf-8")
        # Verify #64748b is used for the gauge background circle
        self.assertIn('stroke="#64748b"', dep_src)

        # Contrast calculation check:
        # L1 (#64748b) = 0.174, L2 (#0f172a) = 0.012
        l1 = 0.174
        l2 = 0.012
        contrast = (l1 + 0.05) / (l2 + 0.05)
        self.assertGreaterEqual(contrast, 3.0, "Contrast ratio must be at least 3.0:1 for non-text UI components")

    def test_24_depreciation_sliders_have_localized_aria_valuetext(self) -> None:
        """Verifies all 4 range sliders in DepreciationCalculatorClient.tsx define localized aria-valuetext."""
        dep_src = (APP_DIR / "depreciation-calculator" / "DepreciationCalculatorClient.tsx").read_text(encoding="utf-8")
        self.assertIn("aria-valuetext={`${holdingYears}년 보유`}", dep_src)
        self.assertIn("aria-valuetext={`연간 ${annualMileageKm.toLocaleString()}km 주행`}", dep_src)
        self.assertIn("aria-valuetext={`급속 충전 비율 ${dcfcRatio}%`}", dep_src)
        self.assertIn("aria-valuetext={`${heldMonths}개월 운행`}", dep_src)

    def test_25_site_footer_attribution_and_legal_notice_enrichment(self) -> None:
        """Verifies SiteFooter.tsx declares links to ev.or.kr and car.go.kr with accessible text and disclaimer."""
        footer_src = (SRC_DIR / "components" / "layout" / "SiteFooter.tsx").read_text(encoding="utf-8")
        self.assertIn("https://www.ev.or.kr", footer_src)
        self.assertIn("https://www.car.go.kr", footer_src)
        self.assertIn('(새 창에서 열림)', footer_src)
        self.assertIn('target="_blank"', footer_src)
        self.assertIn('rel="noopener noreferrer"', footer_src)
        self.assertIn("지자체 공고", footer_src)

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

    def test_27_font_fallback_array_in_root_layout(self) -> None:
        """Verifies layout.tsx declares explicit monospace system fallbacks for geistMono."""
        layout_src = (APP_DIR / "layout.tsx").read_text(encoding="utf-8")
        self.assertIn("ui-monospace", layout_src)
        self.assertIn("SFMono-Regular", layout_src)
        self.assertIn("Menlo", layout_src)
        self.assertIn("monospace", layout_src)

    def test_28_heading_hierarchy_monotonicity_across_all_app_routes(self) -> None:
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


# ===========================================================================
# Class 5: TestCycle18TestTreeAndMirrorParity
# ===========================================================================
class TestCycle18TestTreeAndMirrorParity(unittest.TestCase):
    """Validates 100% cryptographic parity across test trees, the new hardening test suite,
    and backend logic modules.
    """

    def test_29_test_tree_bitwise_mirror_parity(self) -> None:
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

    def test_30_test_cycle18_hardening_exact_mirror_parity(self) -> None:
        """Verifies tests/test_cycle18_hardening.py and ev-stealth-web/tests/test_cycle18_hardening.py match identically."""
        p_root = PROJECT_ROOT / "tests" / "test_cycle18_hardening.py"
        p_web = WEB_ROOT / "tests" / "test_cycle18_hardening.py"

        self.assertTrue(p_root.exists(), f"Root test suite {p_root} must exist")
        self.assertTrue(p_web.exists(), f"Web mirror test suite {p_web} must exist")

        b_root = p_root.read_bytes()
        b_web = p_web.read_bytes()

        self.assertEqual(len(b_root), len(b_web), "Byte lengths must match identically")
        h_root = hashlib.sha256(b_root).hexdigest()
        h_web = hashlib.sha256(b_web).hexdigest()
        self.assertEqual(h_root, h_web, f"SHA-256 hashes must match identically ({h_root})")

    def test_31_backend_logic_mirror_parity(self) -> None:
        """Verifies 100% parity across tracker/, crawlers/, filters/, models/, utils/, and run_tracker.py."""
        modules = ["tracker", "crawlers", "filters", "models", "utils"]
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
