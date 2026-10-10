"""
tests/test_cycle12_hardening.py - Comprehensive Cycle 12 Hardening, Defensive Boundary,
Accessibility, Performance, and Triple Dataset Parity Test Suite.

Authoritative Reference:
- ORIGINAL_REQUEST.md
- DISPATCH.md (Cycle 12 Wave 2 Test Suite Specification)
- Wave 1 Explorer Handoff Reports:
  - sync12_explorer_backend_w1/handoff.md
  - sync12_explorer_frontend_w1/handoff.md
  - sync12_explorer_a11y_w1/handoff.md
  - sync12_explorer_perf_w1/handoff.md
  - sync12_explorer_parity_w1/handoff.md
- COLLABORATION.md

Coverage:
1. Backend utils/json_writer Hardening:
   - 0.0 negativity_score preservation (preventing falsy 0.5 default fallback).
   - Case-insensitive "CRITICAL" severity classification ("critical", "Critical", etc.).
   - Null and missing total_scraped handling in write_daily_reports (no TypeError crash).
   - Default serializer (_json_default) integration in write_daily_reports.

2. Backend tracker/subsidy_tracker Hardening:
   - calculate_price_cap_ratio null, NaN, Inf, and invalid type clamping to 0.0.
   - calculate_net_subsidy defensive boundaries on non-positive and null MSRP (non-negative net price).
   - Budget underflow guards: remaining budget bounded within [0, total_budget], non-negative disbursed budget.
   - Safe aggregation over null/None units in regional metrics.
   - public/data/ mirror destinations included in save_payload and run_tracker.

3. Backend tracker/defect_tracker Hardening:
   - Cache dictionary immutability in load_reports() and query_defects() preventing cache poisoning.
   - Whitespace query normalization for category, brand, model, and keyword filters.
   - Severity fallback for None severity_index with CRITICAL severity tier mapping.

4. Backend tracker/atomic_writer Hardening:
   - _json_default support for dataclass instances (via dataclasses.asdict) and frozenset (via list).
   - Support for datetime, date, Path, Enum, and set.

5. Frontend Logic, SSG, & Accessibility Hardening:
   - Dynamic multi-year benchmark deltas in DepreciationCalculatorClient (holdingYears-driven).
   - Positive/negative contrast styling for benchmark deltas (emerald vs rose).
   - Next.js 100% (12/12) static generation declarations (export const dynamic = 'force-static').
   - next.config.mjs Cache-Control headers for /data/:path* and X-DNS-Prefetch-Control.
   - WCAG 2.1 AA aria-labelledby landmark connections and explicit form control label pairings.
   - Dark mode contrast fix on regional grid heading in SubsidyTrackerClient.

6. Triple Mirror Dataset Parity:
   - 100% cryptographic SHA-256 bitwise parity across data/, ev-stealth-web/src/data/, and ev-stealth-web/public/data/.
   - POSIX 0644 mode compliance across all 12 dataset files.

7. Test Mirror Parity:
   - Bitwise parity between tests/test_cycle12_hardening.py and ev-stealth-web/tests/test_cycle12_hardening.py.
"""

from __future__ import annotations

import collections
import dataclasses
from datetime import date, datetime, timezone
from enum import Enum
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
import unittest
from typing import Any, Dict, List, Optional, Union

# Adaptive repository and web root resolution
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

from tracker.atomic_writer import _json_default, atomic_write_json
from tracker.defect_tracker import DefectTracker
from tracker.subsidy_models import RegionRecord, CategoryMetrics
from tracker.subsidy_tracker import (
    SubsidyTracker,
    calculate_price_cap_ratio,
    calculate_net_subsidy,
)
from utils.json_writer import (
    _safe_float,
    format_daily_report_payload,
    read_daily_reports,
    write_daily_reports,
)


# ============================================================================
# 1. utils/json_writer Defensive Hardening
# ============================================================================
class TestCycle12JsonWriterDefensiveHardening(unittest.TestCase):
    """Verifies utils/json_writer fixes: 0.0 negativity score preservation,

    case-insensitive severity classification, safe total_scraped handling,
    and default serializer support.
    """

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="test_cycle12_writer_")
        self.output_file = Path(self.test_dir) / "daily_reports.json"

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_negativity_score_zero_not_overwritten_by_falsy_default(self) -> None:
        """When negativity_score is 0.0 (completely neutral/non-negative),

        it must NOT evaluate as falsy and fall back to 0.5.
        """
        # Case 1: negativity_score is float 0.0
        rec_zero_neg = {
            "id": "zero_neg_1",
            "title": "Completely quiet cabin",
            "negativity_score": 0.0,
            "severity_index": 1.0,
            "severity": "LOW",
            "is_authentic_defect": True,
        }
        payload = format_daily_report_payload([rec_zero_neg])
        payload_dict = payload.to_dict()
        saved_rec = payload_dict["reports"][0]
        self.assertEqual(saved_rec["negativity_score"], 0.0)
        self.assertEqual(payload_dict["statistics"]["avg_negativity_score"], 0.0)

        # Case 2: negativity_score is absent/None, but sentiment_score is 0.0
        rec_zero_sent = {
            "id": "zero_neg_2",
            "title": "Minor cosmetic panel gap",
            "sentiment_score": 0.0,
            "severity_index": 1.0,
            "severity": "LOW",
            "is_authentic_defect": True,
        }
        payload2 = format_daily_report_payload([rec_zero_sent])
        payload_dict2 = payload2.to_dict()
        saved_rec2 = payload_dict2["reports"][0]
        self.assertEqual(saved_rec2["sentiment_score"], 0.0)
        self.assertEqual(payload_dict2["statistics"]["avg_negativity_score"], 0.0)

        # Case 3: Both negativity_score and sentiment_score are None -> fallback to 0.5
        rec_none = {
            "id": "zero_neg_3",
            "title": "Unscored defect",
            "is_authentic_defect": True,
        }
        payload3 = format_daily_report_payload([rec_none])
        payload_dict3 = payload3.to_dict()
        self.assertEqual(payload_dict3["statistics"]["avg_negativity_score"], 0.5)

    def test_case_insensitive_critical_severity_classification(self) -> None:
        """Severity 'critical' in lowercase or mixed case must be correctly recognized

        as critical and increment critical_defect_count.
        """
        records = [
            # Lowercase 'critical'
            {
                "id": "crit_1_lower",
                "title": "Brake pressure loss",
                "severity": "critical",
                "severity_index": 0.0,
                "is_authentic_defect": True,
            },
            # Mixed case 'Critical'
            {
                "id": "crit_2_mixed",
                "title": "Inverter shutdown",
                "severity": "Critical",
                "severity_index": 0.0,
                "is_authentic_defect": True,
            },
            # Uppercase 'CRITICAL' via severity_tier
            {
                "id": "crit_3_tier",
                "title": "Battery thermal runaway",
                "severity_tier": "critical",
                "severity_index": 0.0,
                "is_authentic_defect": True,
            },
            # severity_index >= 8.0 regardless of severity string
            {
                "id": "crit_4_idx",
                "title": "High severity index failure",
                "severity": "medium",
                "severity_index": 8.5,
                "is_authentic_defect": True,
            },
            # Non-critical record
            {
                "id": "non_crit",
                "title": "Rattling speaker grille",
                "severity": "low",
                "severity_index": 2.0,
                "is_authentic_defect": True,
            },
        ]
        payload = format_daily_report_payload(records)
        stats = payload.to_dict()["statistics"]
        self.assertEqual(
            stats["critical_defect_count"],
            4,
            f"Expected exactly 4 critical defects, got {stats['critical_defect_count']}",
        )

    def test_write_daily_reports_safe_with_null_and_missing_total_scraped(self) -> None:
        """Existing file with total_scraped: null must NOT raise TypeError

        when merging new reports.
        """
        initial_payload = {
            "generated_at": "2026-10-10T00:00:00Z",
            "pipeline_version": "1.0.0",
            "statistics": {
                "total_scraped": None,  # Explicitly None
                "total_filtered_defects": 1,
            },
            "reports": [
                {
                    "id": "existing_rec_1",
                    "title": "Prior complaint",
                    "url": "https://example.com/prior",
                    "is_authentic_defect": True,
                }
            ],
        }
        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(initial_payload, f, ensure_ascii=False, indent=2)

        new_records = [
            {
                "id": "new_rec_1",
                "title": "Fresh defect",
                "url": "https://example.com/fresh",
                "is_authentic_defect": True,
            }
        ]

        # Scenario A: total_scraped passed as integer
        result_path = write_daily_reports(
            complaints=new_records,
            output_path=str(self.output_file),
            merge_existing=True,
            total_scraped=5,
        )
        self.assertEqual(result_path, str(self.output_file))
        saved = read_daily_reports(str(self.output_file))
        self.assertGreaterEqual(saved["statistics"]["total_scraped"], 2)

        # Reset with total_scraped: None again
        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(initial_payload, f, ensure_ascii=False, indent=2)

        # Scenario B: total_scraped passed as None (relies on max(existing, len(merged)))
        result_path_b = write_daily_reports(
            complaints=new_records,
            output_path=str(self.output_file),
            merge_existing=True,
            total_scraped=None,
        )
        self.assertEqual(result_path_b, str(self.output_file))
        saved_b = read_daily_reports(str(self.output_file))
        self.assertEqual(saved_b["statistics"]["total_scraped"], 2)

    def test_write_daily_reports_default_serializer_handles_complex_types(self) -> None:
        """write_daily_reports must cleanly serialize datetime, date, Path, Enum,

        set, frozenset, and dataclass objects without TypeError.
        """
        class SampleStatus(Enum):
            ACTIVE = "ACTIVE_DEFECT"

        @dataclasses.dataclass
        class DiagnosticMeta:
            firmware_rev: str
            ecu_code: int

        complex_record = {
            "id": "complex_record_1",
            "title": "Diagnostic report",
            "url": "https://example.com/diag",
            "is_authentic_defect": True,
            "discovered_at": datetime(2026, 10, 10, 15, 30, tzinfo=timezone.utc),
            "reported_date": date(2026, 10, 10),
            "source_path": Path("/var/log/ev_telemetry.log"),
            "status": SampleStatus.ACTIVE,
            "tags": {"CAN_BUS", "BATTERY"},
            "flags": frozenset(["URGENT", "VERIFIED"]),
            "diag_meta": DiagnosticMeta(firmware_rev="v2.4.1", ecu_code=1042),
        }

        written_path = write_daily_reports(
            complaints=[complex_record],
            output_path=str(self.output_file),
            merge_existing=False,
        )
        self.assertTrue(Path(written_path).exists())

        with open(self.output_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        rep = data["reports"][0]
        self.assertEqual(rep["discovered_at"], "2026-10-10T15:30:00+00:00")
        self.assertEqual(rep["reported_date"], "2026-10-10")
        self.assertEqual(rep["source_path"], "/var/log/ev_telemetry.log")
        self.assertEqual(rep["status"], "ACTIVE_DEFECT")
        self.assertCountEqual(rep["tags"], ["CAN_BUS", "BATTERY"])
        self.assertCountEqual(rep["flags"], ["URGENT", "VERIFIED"])
        self.assertEqual(rep["diag_meta"], {"firmware_rev": "v2.4.1", "ecu_code": 1042})


# ============================================================================
# 2. tracker/subsidy_tracker Defensive Hardening
# ============================================================================
class TestCycle12SubsidyTrackerDefensiveHardening(unittest.TestCase):
    """Verifies tracker/subsidy_tracker fixes: non-positive MSRP price cap ratio clamping,

    defensive calculate_net_subsidy boundaries, and budget underflow guards.
    """

    def test_price_cap_ratio_non_positive_and_null_clamping(self) -> None:
        """calculate_price_cap_ratio must return 0.0 for null, NaN, Inf, and invalid type inputs."""
        # None, NaN, Inf, and invalid inputs must safely return 0.0
        self.assertEqual(calculate_price_cap_ratio(None), 0.0)  # type: ignore[arg-type]
        self.assertEqual(calculate_price_cap_ratio("not_a_number"), 0.0)  # type: ignore[arg-type]
        self.assertEqual(calculate_price_cap_ratio(float("nan")), 0.0)  # type: ignore[arg-type]
        self.assertEqual(calculate_price_cap_ratio(float("inf")), 0.0)  # type: ignore[arg-type]

        # Statutory price cap tiers
        self.assertEqual(calculate_price_cap_ratio(50_000_000), 1.0)
        self.assertEqual(calculate_price_cap_ratio(55_000_000), 1.0)
        self.assertEqual(calculate_price_cap_ratio(55_000_001), 0.5)
        self.assertEqual(calculate_price_cap_ratio(70_000_000), 0.5)
        self.assertEqual(calculate_price_cap_ratio(85_000_000), 0.5)
        self.assertEqual(calculate_price_cap_ratio(85_000_001), 0.0)
        self.assertEqual(calculate_price_cap_ratio(120_000_000), 0.0)

    def test_calculate_net_subsidy_defensive_bounds(self) -> None:
        """calculate_net_subsidy must clamp net_price to non-negative 0 for non-positive or null MSRP."""
        # Zero MSRP -> net_price clamped to 0
        res_zero = calculate_net_subsidy(
            model_national=6_500_000,
            max_national=6_500_000,
            max_local=2_000_000,
            msrp=0,
        )
        self.assertEqual(res_zero["net_price_krw"], 0)

        # Negative MSRP -> net_price clamped to 0
        res_neg = calculate_net_subsidy(
            model_national=6_500_000,
            max_national=6_500_000,
            max_local=2_000_000,
            msrp=-50_000_000,
        )
        self.assertEqual(res_neg["net_price_krw"], 0)

        # None MSRP -> net_price clamped to 0
        res_none = calculate_net_subsidy(
            model_national=6_500_000,
            max_national=6_500_000,
            max_local=2_000_000,
            msrp=None,  # type: ignore[arg-type]
        )
        self.assertEqual(res_none["net_price_krw"], 0)

        # Valid MSRP under 55M
        res_valid = calculate_net_subsidy(
            model_national=6_500_000,
            max_national=6_500_000,
            max_local=2_000_000,
            msrp=50_000_000,
        )
        self.assertEqual(res_valid["national_subsidy_krw"], 6_500_000)
        self.assertEqual(res_valid["local_subsidy_krw"], 2_000_000)
        self.assertEqual(res_valid["total_subsidy_krw"], 8_500_000)
        self.assertEqual(res_valid["net_price_krw"], 41_500_000)

    def test_budget_clamping_and_underflow_guards(self) -> None:
        """Remaining budget must never exceed total budget or fall below 0,

        and disbursed budget must never be negative.
        """
        tracker = SubsidyTracker()

        cat_data = CategoryMetrics(
            announced_units=100,
            applied_units=-25,  # Negative applied units test
            delivered_units=0,
            remaining_units=100,
            depletion_rate=0.0,
            delivery_rate=0.0,
            status="HEALTHY",
            max_local_subsidy_krw=2_000_000,
            max_total_subsidy_krw=8_500_000,
            total_budget_krw=1_000_000_000,
            remaining_budget_krw=0,
        )
        region = RegionRecord(
            region_id="test_reg",
            name_ko="테스트시",
            categories={"passenger": cat_data},
        )

        tracker.update_region_metrics(region)
        # Remaining budget must be clamped to total_budget (cannot balloon above it)
        self.assertEqual(
            cat_data.remaining_budget_krw,
            1_000_000_000,
            "Remaining budget must not balloon above total budget when applied is negative",
        )

        # Test over-applied units (applied > announced)
        cat_data.applied_units = 150
        tracker.update_region_metrics(region)
        self.assertEqual(
            cat_data.remaining_budget_krw,
            0,
            "Remaining budget must not drop below 0 when applied exceeds announced",
        )

        # Test compute_nationwide_summary disbursed calculation
        cat_data.total_budget_krw = 500_000_000
        cat_data.remaining_budget_krw = 700_000_000  # Inverted case: remaining > total
        summary = tracker.compute_nationwide_summary([region])
        self.assertGreaterEqual(
            summary.disbursed_budget_billion_krw,
            0.0,
            "Nationwide disbursed budget must never be negative",
        )

    def test_public_data_mirror_destinations_included(self) -> None:
        """run_tracker and SubsidyTracker must include public/data/ targets."""
        import run_tracker

        paths = run_tracker._resolve_default_paths()
        external_targets = paths[4]
        target_strs = [str(p) for p in external_targets]

        public_subsidy = str(WEB_ROOT / "public" / "data" / "ev_subsidy_data.json")
        public_depletion = str(WEB_ROOT / "public" / "data" / "subsidy_depletion_data.json")

        self.assertIn(
            public_subsidy,
            target_strs,
            "ev-stealth-web/public/data/ev_subsidy_data.json must be in external_sync_targets",
        )
        self.assertIn(
            public_depletion,
            target_strs,
            "ev-stealth-web/public/data/subsidy_depletion_data.json must be in external_sync_targets",
        )


# ============================================================================
# 3. tracker/defect_tracker Defensive Hardening
# ============================================================================
class TestCycle12DefectTrackerDefensiveHardening(unittest.TestCase):
    """Verifies tracker/defect_tracker fixes: cache dictionary immutability,

    whitespace query normalization, and severity tier mapping for None severity_index.
    """

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="test_cycle12_defect_")
        self.data_file = Path(self.test_dir) / "daily_reports.json"
        self.sample_data = {
            "generated_at": "2026-10-10T00:00:00Z",
            "pipeline_version": "1.0.0",
            "reports": [
                {
                    "id": "def_1",
                    "title": "Brake caliper sticking",
                    "defect_category": "CHASSIS",
                    "vehicle_brand": "현대",
                    "vehicle_model": "아이오닉 5",
                    "severity": "CRITICAL",
                    "severity_index": None,
                    "is_authentic_defect": True,
                },
                {
                    "id": "def_2",
                    "title": "Center screen flickering",
                    "defect_category": "ELECTRONICS",
                    "vehicle_brand": "기아",
                    "vehicle_model": "EV6",
                    "severity": "LOW",
                    "severity_index": 2.0,
                    "is_authentic_defect": True,
                },
            ],
        }
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.sample_data, f, ensure_ascii=False, indent=2)
        self.tracker = DefectTracker(root_data_dir=self.test_dir, web_data_dir=self.test_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_cached_reports_immutability_in_load_reports(self) -> None:
        """Mutating the list returned by load_reports() must NOT mutate internal cache."""
        reports = self.tracker.load_reports(file_path=self.data_file)
        self.assertGreaterEqual(len(reports), 2)

        # Mutate dictionary in returned list
        reports[0]["defect_category"] = "MUTATED_CATEGORY"

        # Re-fetch from cache
        reports_fresh = self.tracker.load_reports(file_path=self.data_file)
        self.assertNotEqual(
            reports_fresh[0]["defect_category"],
            "MUTATED_CATEGORY",
            "Internal cached report dictionary was mutated by caller",
        )
        self.assertEqual(reports_fresh[0]["defect_category"], "CHASSIS")

    def test_query_cache_immutability_in_query_defects(self) -> None:
        """Mutating query results must NOT mutate cached query results in _query_cache."""
        res1 = self.tracker.query_defects(category="CHASSIS", file_path=self.data_file)
        self.assertEqual(len(res1), 1)

        # Mutate title in result
        res1[0]["title"] = "MUTATED_TITLE"

        # Query again with same parameters
        res2 = self.tracker.query_defects(category="CHASSIS", file_path=self.data_file)
        self.assertEqual(len(res2), 1)
        self.assertNotEqual(
            res2[0]["title"],
            "MUTATED_TITLE",
            "Query cache was corrupted by modifying returned dictionary",
        )
        self.assertEqual(res2[0]["title"], "Brake caliper sticking")

    def test_whitespace_query_filter_normalization(self) -> None:
        """Whitespace-only strings for category, brand, model, and keyword

        must be treated as unconstrained queries (equivalent to None).
        """
        # Whitespace category must not return []
        res_ws_cat = self.tracker.query_defects(category="   ", file_path=self.data_file)
        self.assertEqual(
            len(res_ws_cat),
            2,
            "Whitespace category must not filter out all defect records",
        )

        # Empty string category
        res_empty_cat = self.tracker.query_defects(category="", file_path=self.data_file)
        self.assertEqual(len(res_empty_cat), 2)

        # Whitespace brand
        res_ws_brand = self.tracker.query_defects(vehicle_brand="   ", file_path=self.data_file)
        self.assertEqual(len(res_ws_brand), 2)

        # Whitespace model
        res_ws_model = self.tracker.query_defects(vehicle_model="   ", file_path=self.data_file)
        self.assertEqual(len(res_ws_model), 2)

        # Whitespace keyword
        res_ws_kw = self.tracker.query_defects(keyword="   ", file_path=self.data_file)
        self.assertEqual(len(res_ws_kw), 2)

    def test_min_severity_fallback_for_none_severity_index(self) -> None:
        """When severity_index is None, CRITICAL severity maps to 9.0 and is retained

        under min_severity=8.0.
        """
        results = self.tracker.query_defects(min_severity=8.0, file_path=self.data_file)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "def_1")
        self.assertEqual(results[0]["severity"], "CRITICAL")


# ============================================================================
# 4. tracker/atomic_writer Dataclass & Frozenset Hardening
# ============================================================================
class TestCycle12AtomicWriterComplexSerialization(unittest.TestCase):
    """Verifies tracker/atomic_writer _json_default support for dataclasses and frozensets."""

    def test_json_default_supports_dataclass_and_frozenset(self) -> None:
        """_json_default must convert dataclasses and frozensets cleanly."""
        @dataclasses.dataclass
        class VehicleSpec:
            brand: str
            model: str
            battery_kwh: float

        spec = VehicleSpec(brand="Tesla", model="Model Y", battery_kwh=78.1)
        res_dc = _json_default(spec)
        self.assertEqual(
            res_dc,
            {"brand": "Tesla", "model": "Model Y", "battery_kwh": 78.1},
        )

        fz = frozenset(["alpha", "beta", "gamma"])
        res_fz = _json_default(fz)
        self.assertIsInstance(res_fz, list)
        self.assertCountEqual(res_fz, ["alpha", "beta", "gamma"])


# ============================================================================
# 5. Frontend Dynamic Benchmarks, SSG, & A11y Verification
# ============================================================================
class TestCycle12FrontendHardening(unittest.TestCase):
    """Verifies Next.js frontend fixes: dynamic benchmark calculation,

    force-static generation declarations, next.config.mjs headers, and WCAG AA landmarks.
    """

    def test_depreciation_calculator_dynamic_benchmarks_source(self) -> None:
        """DepreciationCalculatorClient.tsx must calculate dynamic multi-year benchmarks

        and apply contrast-safe positive/negative styles.
        """
        calc_client = APP_DIR / "depreciation-calculator" / "DepreciationCalculatorClient.tsx"
        self.assertTrue(calc_client.exists())
        content = calc_client.read_text(encoding="utf-8")

        # Must define dynamic benchmarks
        self.assertIn("currentEvBenchmark", content)
        self.assertIn("currentIceBenchmark", content)
        self.assertIn("evDiff", content)
        self.assertIn("iceDiff", content)

        # Must style positive vs negative conditionally
        self.assertIn("evDiff >= 0 ? 'text-emerald-700' : 'text-rose-600'", content)
        self.assertIn("iceDiff >= 0 ? 'text-amber-800' : 'text-rose-600'", content)

        # Must not contain obsolete hardcoded static 3-year deltas
        self.assertNotIn("(depResult.adjustedResidualPct - 58)", content)
        self.assertNotIn("(depResult.adjustedResidualPct - 64)", content)

    def test_all_12_next_pages_declare_force_static(self) -> None:
        """All 12 App Router pages must explicitly declare export const dynamic = 'force-static'."""
        page_paths = [
            APP_DIR / "page.tsx",
            APP_DIR / "pdi-checklist" / "page.tsx",
            APP_DIR / "2026-latest" / "page.tsx",
            APP_DIR / "byd" / "page.tsx",
            APP_DIR / "global-brands" / "page.tsx",
            APP_DIR / "hyundai-kia" / "page.tsx",
            APP_DIR / "tesla" / "page.tsx",
            APP_DIR / "depreciation-calculator" / "page.tsx",
            APP_DIR / "subsidy-tracker" / "page.tsx",
            APP_DIR / "reliability-analytics" / "page.tsx",
            APP_DIR / "recall-portal" / "page.tsx",
            APP_DIR / "secret-admin-reports" / "page.tsx",
        ]

        missing_static: List[str] = []
        for p in page_paths:
            self.assertTrue(p.exists(), f"Page {p} must exist")
            content = p.read_text(encoding="utf-8")
            if "export const dynamic = 'force-static';" not in content and 'export const dynamic = "force-static";' not in content:
                missing_static.append(p.name)

        self.assertEqual(
            missing_static,
            [],
            f"All 12 pages must declare 'force-static'. Missing: {missing_static}",
        )

    def test_next_config_cache_control_and_dns_prefetch(self) -> None:
        """next.config.mjs must contain X-DNS-Prefetch-Control and /data/:path* Cache-Control."""
        config_file = WEB_ROOT / "next.config.mjs"
        self.assertTrue(config_file.exists())
        content = config_file.read_text(encoding="utf-8")

        self.assertIn("X-DNS-Prefetch-Control", content)
        self.assertIn("'/data/:path*'", content)
        self.assertIn("max-age=3600, stale-while-revalidate=86400", content)

    def test_wcag_a11y_landmark_and_label_integrity(self) -> None:
        """All sections must have accessible names and form controls must have label pairings."""
        # 1. RecallPortalClient.tsx
        recall_content = (APP_DIR / "recall-portal" / "RecallPortalClient.tsx").read_text(encoding="utf-8")
        self.assertIn('aria-labelledby="recall-checker-heading"', recall_content)
        self.assertIn('id="recall-checker-heading"', recall_content)
        self.assertIn('aria-labelledby="search-result-heading"', recall_content)
        self.assertIn('id="search-result-heading"', recall_content)
        self.assertIn('aria-labelledby="battery-directory-heading"', recall_content)
        self.assertIn('id="battery-directory-heading"', recall_content)
        self.assertIn('aria-labelledby="all-recalls-heading"', recall_content)
        self.assertIn('id="all-recalls-heading"', recall_content)
        self.assertIn('htmlFor="battery-search-input"', recall_content)
        self.assertIn('id="battery-search-input"', recall_content)
        self.assertIn('htmlFor="recall-catalog-search-input"', recall_content)
        self.assertIn('id="recall-catalog-search-input"', recall_content)

        # 2. ReliabilityDashboardClient.tsx
        rel_content = (APP_DIR / "reliability-analytics" / "ReliabilityDashboardClient.tsx").read_text(encoding="utf-8")
        self.assertIn('aria-labelledby="reliability-hero-heading"', rel_content)
        self.assertIn('id="reliability-hero-heading"', rel_content)
        self.assertIn('aria-labelledby="charts-center-heading"', rel_content)
        self.assertIn('id="charts-center-heading"', rel_content)
        self.assertIn('aria-label="결함 통계 검색 및 다중 필터 제어판"', rel_content)
        self.assertIn('htmlFor="reliability-search-input"', rel_content)
        self.assertIn('id="reliability-search-input"', rel_content)
        self.assertIn('htmlFor="reliability-sort-select"', rel_content)
        self.assertIn('id="reliability-sort-select"', rel_content)
        self.assertIn('aria-labelledby="model-reliability-heading"', rel_content)
        self.assertIn('id="model-reliability-heading"', rel_content)
        self.assertIn('aria-labelledby="repair-cost-heading"', rel_content)
        self.assertIn('id="repair-cost-heading"', rel_content)
        self.assertIn('aria-labelledby="recall-banner-heading"', rel_content)
        self.assertIn('id="recall-banner-heading"', rel_content)

        # 3. DepreciationCalculatorClient.tsx
        dep_content = (APP_DIR / "depreciation-calculator" / "DepreciationCalculatorClient.tsx").read_text(encoding="utf-8")
        self.assertIn('aria-labelledby="vehicle-selector-heading"', dep_content)
        self.assertIn('id="vehicle-selector-heading"', dep_content)
        self.assertIn('aria-labelledby="simulation-controls-heading"', dep_content)
        self.assertIn('id="simulation-controls-heading"', dep_content)
        self.assertIn('aria-labelledby="depreciation-chart-heading"', dep_content)
        self.assertIn('id="depreciation-chart-heading"', dep_content)
        self.assertIn('aria-labelledby="battery-health-heading"', dep_content)
        self.assertIn('id="battery-health-heading"', dep_content)
        self.assertIn('aria-labelledby="clawback-calculator-heading"', dep_content)
        self.assertIn('id="clawback-calculator-heading"', dep_content)
        self.assertIn('aria-labelledby="tco-comparison-heading"', dep_content)
        self.assertIn('id="tco-comparison-heading"', dep_content)

        # 4. SubsidyTrackerClient.tsx
        sub_content = (APP_DIR / "subsidy-tracker" / "SubsidyTrackerClient.tsx").read_text(encoding="utf-8")
        self.assertIn('id="regional-grid-heading" className="text-xl sm:text-2xl font-bold text-white', sub_content)
        self.assertIn('htmlFor="grant-youth-buyer-checkbox"', sub_content)
        self.assertIn('id="grant-youth-buyer-checkbox"', sub_content)
        self.assertIn('htmlFor="grant-small-business-checkbox"', sub_content)
        self.assertIn('id="grant-small-business-checkbox"', sub_content)
        self.assertIn('htmlFor="grant-multi-child-checkbox"', sub_content)
        self.assertIn('id="grant-multi-child-checkbox"', sub_content)
        self.assertIn('htmlFor="grant-diesel-scrappage-checkbox"', sub_content)
        self.assertIn('id="grant-diesel-scrappage-checkbox"', sub_content)
        self.assertIn('htmlFor="region-sort-select"', sub_content)
        self.assertIn('id="region-sort-select"', sub_content)

        # 5. AdminDashboardClient.tsx
        adm_content = (APP_DIR / "secret-admin-reports" / "AdminDashboardClient.tsx").read_text(encoding="utf-8")
        self.assertIn('htmlFor="admin-defect-search-input"', adm_content)
        self.assertIn('id="admin-defect-search-input"', adm_content)


# ============================================================================
# 6. Triple Mirror Dataset Parity
# ============================================================================
class TestCycle12DatasetTripleMirrorParity(unittest.TestCase):
    """Verifies 100% cryptographic SHA-256 bitwise parity across all 4 datasets

    in data/, ev-stealth-web/src/data/, and ev-stealth-web/public/data/.
    """

    def test_all_four_datasets_triple_parity_shas(self) -> None:
        """All 4 synchronized datasets must be 100% bitwise identical across all 3 directories."""
        datasets = [
            "ev_subsidy_data.json",
            "subsidy_depletion_data.json",
            "daily_reports.json",
            "models_subsidy_matrix.json",
        ]

        dir_root = PROJECT_ROOT / "data"
        dir_src = WEB_ROOT / "src" / "data"
        dir_pub = WEB_ROOT / "public" / "data"

        for ds in datasets:
            p_root = dir_root / ds
            p_src = dir_src / ds
            p_pub = dir_pub / ds

            self.assertTrue(p_root.exists(), f"File {p_root} must exist")
            self.assertTrue(p_src.exists(), f"File {p_src} must exist")
            self.assertTrue(p_pub.exists(), f"File {p_pub} must exist")

            sha_root = hashlib.sha256(p_root.read_bytes()).hexdigest()
            sha_src = hashlib.sha256(p_src.read_bytes()).hexdigest()
            sha_pub = hashlib.sha256(p_pub.read_bytes()).hexdigest()

            self.assertEqual(
                sha_root,
                sha_src,
                f"Dataset parity mismatch between root and src for {ds}: {sha_root} vs {sha_src}",
            )
            self.assertEqual(
                sha_root,
                sha_pub,
                f"Dataset parity mismatch between root and public for {ds}: {sha_root} vs {sha_pub}",
            )

    def test_datasets_posix_permissions_0644(self) -> None:
        """All 12 dataset JSON files must have POSIX 0644 permissions."""
        datasets = [
            "ev_subsidy_data.json",
            "subsidy_depletion_data.json",
            "daily_reports.json",
            "models_subsidy_matrix.json",
        ]

        directories = [
            PROJECT_ROOT / "data",
            WEB_ROOT / "src" / "data",
            WEB_ROOT / "public" / "data",
        ]

        non_compliant: List[str] = []
        for d in directories:
            for ds in datasets:
                p = d / ds
                if p.exists():
                    mode = stat.S_IMODE(p.stat().st_mode)
                    if mode != 0o644:
                        non_compliant.append(f"{p}: {oct(mode)}")

        self.assertEqual(
            non_compliant,
            [],
            f"All dataset JSON files must have POSIX 0644 mode. Violations: {non_compliant}",
        )

    def test_datasets_json_schema_and_integrity(self) -> None:
        """All dataset files must be valid non-empty JSON with policy_year 2026."""
        datasets = [
            "ev_subsidy_data.json",
            "subsidy_depletion_data.json",
            "daily_reports.json",
            "models_subsidy_matrix.json",
        ]
        directories = [
            PROJECT_ROOT / "data",
            WEB_ROOT / "src" / "data",
            WEB_ROOT / "public" / "data",
        ]

        for d in directories:
            for ds in datasets:
                p = d / ds
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.assertIsInstance(data, (dict, list), f"{p} must parse to dict or list")
                if isinstance(data, dict):
                    if "metadata" in data and "policy_year" in data["metadata"]:
                        self.assertEqual(data["metadata"]["policy_year"], 2026)
                elif isinstance(data, list):
                    self.assertGreater(len(data), 0, f"{p} list must not be empty")


# ============================================================================
# 7. Test Mirror Parity
# ============================================================================
class TestCycle12TestMirrorParity(unittest.TestCase):
    """Verifies that test_cycle12_hardening.py is mirrored bitwise identically

    between tests/ and ev-stealth-web/tests/ with POSIX 0644 permissions.
    """

    def test_cycle12_hardening_mirror_parity(self) -> None:
        """tests/test_cycle12_hardening.py and ev-stealth-web/tests/test_cycle12_hardening.py

        must be bitwise identical.
        """
        root_test = PROJECT_ROOT / "tests" / "test_cycle12_hardening.py"
        web_test = WEB_ROOT / "tests" / "test_cycle12_hardening.py"

        self.assertTrue(root_test.exists(), f"{root_test} must exist")
        self.assertTrue(web_test.exists(), f"{web_test} must exist")

        sha_root = hashlib.sha256(root_test.read_bytes()).hexdigest()
        sha_web = hashlib.sha256(web_test.read_bytes()).hexdigest()

        self.assertEqual(
            sha_root,
            sha_web,
            f"test_cycle12_hardening.py mismatch: {sha_root} != {sha_web}",
        )

        mode_root = stat.S_IMODE(root_test.stat().st_mode)
        mode_web = stat.S_IMODE(web_test.stat().st_mode)
        self.assertEqual(mode_root, 0o644, f"{root_test} mode must be 0644")
        self.assertEqual(mode_web, 0o644, f"{web_test} mode must be 0644")


if __name__ == "__main__":
    unittest.main()
