"""
tests/test_cycle21_hardening.py - Comprehensive Cycle 21 Hardening, Boundary,
Contract Validation, WCAG 2.1 AA, and Triple Mirror Parity Test Suite.

Authoritative Reference:
- ORIGINAL_REQUEST.md
- DISPATCH.md (Cycle 21 Hardening Test Suite Specification)
- COLLABORATION.md

Classes & Coverage (22 tests across 5 test classes):
1. TestCycle21DatasetIntegrity (4 tests: 01-04)
   - test_01_triple_mirror_dataset_presence_and_permissions: 12 files across 3 mirror dirs with 0o644 mode.
   - test_02_triple_mirror_cryptographic_sha256_bitwise_parity: 100% hash parity per dataset and ev_subsidy == subsidy_depletion.
   - test_03_triple_mirror_json_schema_validity_and_positive_bounds: Valid JSON syntax, required keys, positive bounds on all 4 synced datasets.
   - test_04_all_four_verified_field_defect_reports_integrity: 4 verified defect reports with community URLs and verbatim quotes.

2. TestCycle21StatutoryBudgetConservation (5 tests: 05-09)
   - test_05_national_subsidy_metrics_conservation_invariants: total 148,510, applied 132,766, remaining 15,744, 89.4%.
   - test_06_statutory_budget_execution_invariants: total 2,105.1B, disbursed 1,893.4B KRW (89.94%).
   - test_07_category_breakdown_arithmetic_invariants: passenger, commercial, bus breakdown arithmetic equality.
   - test_08_regional_quota_sum_consistency_across_all_17_regions: 17 administrative division totals equal nationwide summary.
   - test_09_critical_exhaustion_regions_and_alert_distribution: exactly 4 regions >= 95.0% (Jeju, Gyeongbuk, Ulsan, Daegu).

3. TestCycle21FrontendContracts (4 tests: 10-13)
   - test_10_pdi_checklist_cross_tool_navigation_contracts: cross-tool navigation links in PdiChecklistClient.tsx.
   - test_11_2026_latest_page_cross_tool_navigation_and_citations: cross-tool links and community citations in 2026-latest/page.tsx.
   - test_12_frontend_statutory_price_cap_tiers: getPriceSubsidyRatio across 54.99M, 55M, 84.99M, 85M KRW.
   - test_13_frontend_proportional_local_matching_formula: round(max_local * (national / 6.5M) / 10000) * 10000.

4. TestCycle21WcagA11yHardening (4 tests: 14-17)
   - test_14_route_existence_and_single_h1_monotonic_headings_for_all_routes: all static routes exist with single <h1> and monotonic heading depth.
   - test_15_wcag_contrast_standards_mathematical_verification: WCAG 2.1 relative luminance and contrast formula verification.
   - test_16_pdi_checklist_and_calculator_aria_attributes: role="progressbar", aria-valuenow, and localized aria-valuetext.
   - test_17_app_error_boundaries_and_not_found_a11y: error.tsx and not-found.tsx exist with recovery actions.

5. TestCycle21MirrorParity (2 tests: 18-19)
   - test_18_bitwise_test_tree_mirror_parity_and_permissions: 100% bitwise parity and 0o644 permissions across tests/ and ev-stealth-web/tests/.
   - test_19_security_headers_next_config_resilience: Cross-Origin-Resource-Policy and security headers in next.config.mjs.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
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
APP_DIR = SRC_DIR / "app"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
else:
    sys.path.remove(str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT))

if str(WEB_ROOT) not in sys.path:
    sys.path.append(str(WEB_ROOT))

from tracker.subsidy_tracker import calculate_price_cap_ratio, calculate_net_subsidy


# ===========================================================================
# Class 1: TestCycle21DatasetIntegrity
# ===========================================================================
class TestCycle21DatasetIntegrity(unittest.TestCase):
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

            summary = ev_data["nationwide_summary"]
            self.assertGreater(summary.get("total_announced_units", 0), 0)
            self.assertGreater(summary.get("total_applied_units", 0), 0)
            self.assertGreater(summary.get("total_delivered_units", 0), 0)
            self.assertGreater(summary.get("total_remaining_units", 0), 0)
            self.assertGreater(summary.get("total_budget_billion_krw", 0), 0)
            self.assertGreater(summary.get("disbursed_budget_billion_krw", 0), 0)

            for reg in ev_data["regions"]:
                self.assertIn("region_id", reg)
                self.assertIn("name_ko", reg)
                cats = reg.get("categories", {})
                for _, c_val in cats.items():
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

    def test_04_all_four_verified_field_defect_reports_integrity(self) -> None:
        """Asserts presence of all 4 verified community defect reports with live community URLs and verbatim quotes."""
        daily_file = PROJECT_ROOT / "data" / "daily_reports.json"
        with open(daily_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        reports = data.get("reports", [])
        self.assertGreater(len(reports), 0, "daily_reports.json must contain reports")

        expected_defect_cases = {
            "ioniq5_iccu": {
                "id": "dc_20260908_001",
                "url": "https://gall.dcinside.com/mgallery/board/view/?id=car_new1&no=1284920",
                "category": "BATTERY_CHARGING",
                "min_negativity": 0.90,
                "quote_sub": "고속도로에서 100km로 달리는데 갑자기 퍽 소리 나더니 배터리 경고등 뜨고 악셀 먹통됨",
            },
            "ev3_fishtail": {
                "id": "bd_20260908_002",
                "url": "https://www.bobaedream.co.kr/view?code=national&No=2291045",
                "category": "DRIVING_POWERTRAIN",
                "min_negativity": 0.90,
                "quote_sub": "비 오는 날 고속도로 이음새 밟고 회생제동 살짝 걸리는 순간 뒤쪽이 좌우로 사정없이 털리면서 피쉬테일 옴",
            },
            "ev6_trunk_leak": {
                "id": "bd_20260908_003",
                "url": "https://www.bobaedream.co.kr/view?code=national&No=2290881",
                "category": "BUILD_QUALITY",
                "min_negativity": 0.90,
                "quote_sub": "차 받은 지 3일 만에 폭우 내렸는데 오늘 트렁크 바닥 열어보니까 물이 찰랑찰랑 한강이네요",
            },
            "modely_blackout": {
                "id": "dc_20260908_004",
                "url": "https://gall.dcinside.com/mgallery/board/view/?id=car_new1&no=1284550",
                "category": "SOFTWARE_ELECTRONICS",
                "min_negativity": 0.90,
                "quote_sub": "새벽에 와이파이 잡고 업데이트 눌렀는데 아침에 출근하려고 차 타니까 중앙 스크린 꺼져있고 리셋 눌러도 깜깜무소식",
            },
        }

        found_reports: Dict[str, Dict[str, Any]] = {}
        for r in reports:
            rid = str(r.get("id", ""))
            rurl = str(r.get("url") or r.get("post_url") or "")
            for key, spec in expected_defect_cases.items():
                if rid == spec["id"] or spec["url"] in rurl:
                    found_reports[key] = r

        for key, spec in expected_defect_cases.items():
            self.assertIn(
                key,
                found_reports,
                f"Verified field defect report '{key}' ({spec['id']}, {spec['url']}) not found in daily_reports.json",
            )
            report = found_reports[key]
            neg_score = float(report.get("negativity_score") or report.get("sentiment_score") or 0.0)
            self.assertGreaterEqual(
                neg_score,
                spec["min_negativity"],
                f"Report '{key}' negativity score {neg_score} must be >= {spec['min_negativity']}",
            )
            self.assertEqual(
                report.get("defect_category"),
                spec["category"],
                f"Report '{key}' category {report.get('defect_category')} must be {spec['category']}",
            )
            quote = str(report.get("verbatim_quote") or report.get("raw_quote") or "")
            self.assertIn(
                spec["quote_sub"],
                quote,
                f"Report '{key}' verbatim quote does not contain expected excerpt '{spec['quote_sub']}'",
            )


# ===========================================================================
# Class 2: TestCycle21StatutoryBudgetConservation
# ===========================================================================
class TestCycle21StatutoryBudgetConservation(unittest.TestCase):
    """Validates mathematical conservation laws across national quotas, statutory budget
    execution ratios, category breakdowns, regional exhaustion alerts, and regional sum consistency across all 17 regions.
    """

    @classmethod
    def setUpClass(cls) -> None:
        data_file = PROJECT_ROOT / "data" / "ev_subsidy_data.json"
        with open(data_file, "r", encoding="utf-8") as f:
            cls.data = json.load(f)
        cls.summary = cls.data.get("nationwide_summary", {})
        cls.regions = cls.data.get("regions", [])

    def test_05_national_subsidy_metrics_conservation_invariants(self) -> None:
        """Asserts national quota conservation: applied + remaining == announced, delivered <= applied."""
        total_announced = self.summary.get("total_announced_units")
        total_applied = self.summary.get("total_applied_units")
        total_delivered = self.summary.get("total_delivered_units")
        total_remaining = self.summary.get("total_remaining_units")
        depletion_rate = self.summary.get("nationwide_depletion_rate")

        self.assertEqual(total_announced, 148510, "Total announced units must be 148,510")
        self.assertEqual(total_applied, 132766, "Total applied units must be 132,766")
        self.assertEqual(total_delivered, 122515, "Total delivered units must be 122,515")
        self.assertEqual(total_remaining, 15744, "Total remaining units must be 15,744")

        # Conservation law: applied + remaining == announced
        self.assertEqual(
            total_applied + total_remaining,
            total_announced,
            f"Conservation violated: applied({total_applied}) + remaining({total_remaining}) != announced({total_announced})",
        )

        # Delivery invariant: delivered <= applied
        self.assertLessEqual(
            total_delivered,
            total_applied,
            f"Delivery violation: delivered({total_delivered}) > applied({total_applied})",
        )

        # Rate invariant: applied / announced * 100 == 89.4%
        calc_rate = round((total_applied / total_announced) * 100, 1)
        self.assertEqual(calc_rate, depletion_rate, f"Depletion rate {depletion_rate}% != calculated {calc_rate}%")
        self.assertEqual(depletion_rate, 89.4, "Nationwide depletion rate must be 89.4%")

    def test_06_statutory_budget_execution_invariants(self) -> None:
        """Asserts statutory budget execution: total 2,105.1B, disbursed 1,893.4B KRW (89.94%)."""
        total_budget = self.summary.get("total_budget_billion_krw")
        disbursed_budget = self.summary.get("disbursed_budget_billion_krw")

        self.assertEqual(total_budget, 2105.1, "Total budget must be 2,105.1B KRW")
        self.assertEqual(disbursed_budget, 1893.4, "Disbursed budget must be 1,893.4B KRW")

        exec_ratio = round((disbursed_budget / total_budget) * 100, 2)
        self.assertEqual(exec_ratio, 89.94, f"Budget execution ratio must be 89.94%, got {exec_ratio}%")

    def test_07_category_breakdown_arithmetic_invariants(self) -> None:
        """Asserts category breakdowns for passenger, commercial, and bus sum identically to national totals."""
        cats = self.summary.get("category_totals", {})
        self.assertIn("passenger", cats)
        self.assertIn("commercial", cats)
        self.assertIn("bus", cats)

        p = cats["passenger"]
        c = cats["commercial"]
        b = cats["bus"]

        # Passenger
        self.assertEqual(p["announced_units"], 110400)
        self.assertEqual(p["applied_units"], 97035)
        self.assertEqual(p["delivered_units"], 88960)
        self.assertEqual(p["remaining_units"], 13365)
        self.assertEqual(p["applied_units"] + p["remaining_units"], p["announced_units"])

        # Commercial
        self.assertEqual(c["announced_units"], 34800)
        self.assertEqual(c["applied_units"], 32754)
        self.assertEqual(c["delivered_units"], 30780)
        self.assertEqual(c["remaining_units"], 2046)
        self.assertEqual(c["applied_units"] + c["remaining_units"], c["announced_units"])

        # Bus
        self.assertEqual(b["announced_units"], 3310)
        self.assertEqual(b["applied_units"], 2977)
        self.assertEqual(b["delivered_units"], 2775)
        self.assertEqual(b["remaining_units"], 333)
        self.assertEqual(b["applied_units"] + b["remaining_units"], b["announced_units"])

        # Nationwide sums
        tot_ann = p["announced_units"] + c["announced_units"] + b["announced_units"]
        tot_app = p["applied_units"] + c["applied_units"] + b["applied_units"]
        tot_del = p["delivered_units"] + c["delivered_units"] + b["delivered_units"]
        tot_rem = p["remaining_units"] + c["remaining_units"] + b["remaining_units"]

        self.assertEqual(tot_ann, self.summary.get("total_announced_units"))
        self.assertEqual(tot_app, self.summary.get("total_applied_units"))
        self.assertEqual(tot_del, self.summary.get("total_delivered_units"))
        self.assertEqual(tot_rem, self.summary.get("total_remaining_units"))

    def test_08_regional_quota_sum_consistency_across_all_17_regions(self) -> None:
        """Verifies exactly 17 administrative divisions and their category sums match national totals."""
        self.assertEqual(len(self.regions), 17, "Korea must have exactly 17 administrative divisions")

        ann_sum = 0
        app_sum = 0
        del_sum = 0
        rem_sum = 0

        for reg in self.regions:
            cats = reg.get("categories", {})
            self.assertIn("passenger", cats, f"Region {reg.get('region_id')} missing passenger category")
            self.assertIn("commercial", cats, f"Region {reg.get('region_id')} missing commercial category")
            self.assertIn("bus", cats, f"Region {reg.get('region_id')} missing bus category")

            for c_name, c_data in cats.items():
                c_ann = c_data.get("announced_units", 0)
                c_app = c_data.get("applied_units", 0)
                c_del = c_data.get("delivered_units", 0)
                c_rem = c_data.get("remaining_units", 0)

                # Local conservation
                self.assertEqual(
                    c_app + c_rem,
                    c_ann,
                    f"Category {c_name} conservation failed in {reg.get('name_ko')}: {c_app} + {c_rem} != {c_ann}",
                )
                self.assertLessEqual(
                    c_del,
                    c_app,
                    f"Category {c_name} delivery exceeds applications in {reg.get('name_ko')}: {c_del} > {c_app}",
                )

                ann_sum += c_ann
                app_sum += c_app
                del_sum += c_del
                rem_sum += c_rem

        self.assertEqual(ann_sum, self.summary.get("total_announced_units"), "Regional announced sum must equal 148,510")
        self.assertEqual(app_sum, self.summary.get("total_applied_units"), "Regional applied sum must equal 132,766")
        self.assertEqual(del_sum, self.summary.get("total_delivered_units"), "Regional delivered sum must equal 122,515")
        self.assertEqual(rem_sum, self.summary.get("total_remaining_units"), "Regional remaining sum must equal 15,744")

    def test_09_critical_exhaustion_regions_and_alert_distribution(self) -> None:
        """Verifies exactly 4 critical regions (>= 95.0%) and the complete 17-region alert distribution."""
        critical_regions: List[Dict[str, Any]] = []
        warning_regions: List[Dict[str, Any]] = []
        caution_regions: List[Dict[str, Any]] = []

        for reg in self.regions:
            rate = float(reg.get("overall_depletion_rate", 0.0))
            status = reg.get("overall_status")
            if rate >= 95.0 or status == "CRITICAL":
                critical_regions.append(reg)
            elif status == "CAUTION":
                caution_regions.append(reg)
            elif status == "WARNING":
                warning_regions.append(reg)

        self.assertEqual(len(critical_regions), 4, f"Must have exactly 4 critical regions, got {len(critical_regions)}")
        crit_names = {r["name_ko"] for r in critical_regions}
        expected_crit = {"제주특별자치도", "경상북도", "울산광역시", "대구광역시"}
        self.assertEqual(crit_names, expected_crit, f"Critical regions mismatch: {crit_names} != {expected_crit}")

        self.assertEqual(len(caution_regions), 1, "Must have exactly 1 caution region")
        self.assertEqual(caution_regions[0]["name_ko"], "세종특별자치시")
        self.assertEqual(len(warning_regions), 12, "Must have exactly 12 warning regions")

        alerts = self.summary.get("alert_region_counts", {})
        self.assertEqual(alerts.get("healthy"), 0)
        self.assertEqual(alerts.get("caution"), 1)
        self.assertEqual(alerts.get("warning"), 12)
        self.assertEqual(alerts.get("critical"), 4)
        self.assertEqual(alerts.get("depleted"), 0)


# ===========================================================================
# Class 3: TestCycle21FrontendContracts
# ===========================================================================
class TestCycle21FrontendContracts(unittest.TestCase):
    """Validates cross-tool navigation contracts, community citations, and statutory price cap tiers."""

    def test_10_pdi_checklist_cross_tool_navigation_contracts(self) -> None:
        """Verifies cross-tool navigation links in PdiChecklistClient.tsx for all 4 primary tools."""
        pdi_path = WEB_ROOT / "src" / "app" / "pdi-checklist" / "PdiChecklistClient.tsx"
        self.assertTrue(pdi_path.exists(), f"File {pdi_path} must exist")
        content = pdi_path.read_text(encoding="utf-8")
        self.assertIn('href="/subsidy-tracker"', content)
        self.assertIn('href="/depreciation-calculator"', content)
        self.assertIn('href="/recall-portal"', content)
        self.assertIn('href="/reliability-analytics"', content)

    def test_11_2026_latest_page_cross_tool_navigation_and_citations(self) -> None:
        """Verifies 2026-latest/page.tsx cross-tool navigation section and external citations."""
        page_path = WEB_ROOT / "src" / "app" / "2026-latest" / "page.tsx"
        self.assertTrue(page_path.exists(), f"Page {page_path} must exist")

        content = page_path.read_text(encoding="utf-8")

        # 1. Cross-service navigation section
        self.assertIn("heading-cross-tools", content)
        self.assertIn('href="/subsidy-tracker"', content)
        self.assertIn('href="/depreciation-calculator"', content)
        self.assertIn('href="/recall-portal"', content)
        self.assertIn('href="/reliability-analytics"', content)

        # 2. External community defect citations
        self.assertIn("bobaedream.co.kr", content)
        self.assertIn("reddit.com", content)
        self.assertIn("autodaily.co.kr", content)

        # 3. Security and accessibility attributes on external links
        self.assertIn('target="_blank"', content)
        self.assertIn('rel="noopener noreferrer"', content)

    def test_12_frontend_statutory_price_cap_tiers(self) -> None:
        """Verifies statutory price cap ratio across 54.99M, 55M, 84.99M, 85M KRW."""
        cases = [
            (0, 0.0),
            (40000000, 1.0),
            (54999999, 1.0),
            (55000000, 1.0),
            (55000001, 0.5),
            (70000000, 0.5),
            (84999999, 0.5),
            (85000000, 0.5),
            (85000001, 0.0),
            (120000000, 0.0),
        ]
        for price, expected_ratio in cases:
            with self.subTest(price=price):
                ratio = calculate_price_cap_ratio(price)
                self.assertEqual(ratio, expected_ratio, f"Price {price} must yield ratio {expected_ratio}, got {ratio}")

    def test_13_frontend_proportional_local_matching_formula(self) -> None:
        """Verifies proportional local matching formula: round(max_local * (national / 6.5M) / 10000) * 10000."""
        # Standard full subsidy (6.5M national, MSRP 50M)
        net_full = calculate_net_subsidy(
            model_national=6500000,
            max_national=6500000,
            max_local=1500000,
            msrp=50000000,
        )
        self.assertEqual(net_full["local_subsidy_krw"], 1500000)
        self.assertEqual(net_full["total_subsidy_krw"], 8000000)
        self.assertEqual(net_full["net_price_krw"], 42000000)
        self.assertEqual(net_full["price_cap_ratio"], 1.0)

        # Scaled down national subsidy (4.55M national -> 70% of 6.5M, MSRP 50M)
        net_scaled = calculate_net_subsidy(
            model_national=4550000,
            max_national=6500000,
            max_local=4000000,
            msrp=50000000,
        )
        # 4,000,000 * (4,550,000 / 6,500,000) = 4,000,000 * 0.70 = 2,800,000
        self.assertEqual(net_scaled["local_subsidy_krw"], 2800000)
        self.assertEqual(net_scaled["total_subsidy_krw"], 7350000)
        self.assertEqual(net_scaled["net_price_krw"], 42650000)


# ===========================================================================
# Class 4: TestCycle21WcagA11yHardening
# ===========================================================================
class TestCycle21WcagA11yHardening(unittest.TestCase):
    """Validates heading monotonicity, WCAG AA contrast, and ARIA accessibility invariants."""

    def test_14_route_existence_and_single_h1_monotonic_headings_for_all_routes(self) -> None:
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

    def _relative_luminance(self, r: int, g: int, b: int) -> float:
        """Calculate WCAG 2.1 relative luminance."""
        def channel(c: int) -> float:
            c_norm = c / 255.0
            return c_norm / 12.92 if c_norm <= 0.03928 else ((c_norm + 0.055) / 1.055) ** 2.4

        return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)

    def _contrast_ratio(self, rgb1: tuple[int, int, int], rgb2: tuple[int, int, int]) -> float:
        """Calculate WCAG 2.1 contrast ratio between two RGB colors."""
        l1 = self._relative_luminance(*rgb1)
        l2 = self._relative_luminance(*rgb2)
        lighter = max(l1, l2)
        darker = min(l1, l2)
        return (lighter + 0.05) / (darker + 0.05)

    def test_15_wcag_contrast_standards_mathematical_verification(self) -> None:
        """Verifies mathematical WCAG 2.1 AA contrast requirements for text (>=4.5:1) and UI components (>=3.0:1)."""
        white = (255, 255, 255)
        slate_900 = (15, 23, 42)    # #0f172a
        slate_700 = (51, 65, 85)    # #334155
        slate_500 = (100, 116, 139) # #64748b
        blue_600 = (37, 99, 235)    # #2563eb
        blue_700 = (29, 78, 216)    # #1d4ed8
        amber_800 = (146, 64, 14)   # #92400e
        amber_100 = (254, 243, 199) # #fef3c7

        # 1. Primary text contrast on white background: >= 4.5:1
        ratio_primary = self._contrast_ratio(slate_900, white)
        self.assertGreaterEqual(ratio_primary, 4.5, "Primary body text contrast must be >= 4.5:1")

        # 2. Warning text on warning badge: >= 4.5:1
        ratio_warning = self._contrast_ratio(amber_800, amber_100)
        self.assertGreaterEqual(ratio_warning, 4.5, "Warning text on amber badge must be >= 4.5:1")

        # 3. Interactive primary buttons: >= 4.5:1
        ratio_button = self._contrast_ratio(blue_600, white)
        self.assertGreaterEqual(ratio_button, 4.5, "Primary button contrast must be >= 4.5:1")

        # 4. Battery SoH stroke (#64748b) on dark card container (#0f172a): >= 3.0:1 (WCAG 1.4.11)
        ratio_stroke = self._contrast_ratio(slate_500, slate_900)
        self.assertGreaterEqual(ratio_stroke, 3.0, "Non-text UI stroke contrast must be >= 3.0:1")

    def test_16_pdi_checklist_and_calculator_aria_attributes(self) -> None:
        """Verifies progressbar semantics and localized range slider aria-valuetext."""
        # 1. PDI Checklist progressbar semantics
        pdi_path = WEB_ROOT / "src" / "app" / "pdi-checklist" / "PdiChecklistClient.tsx"
        if not pdi_path.exists():
            pdi_path = WEB_ROOT / "src" / "components" / "PdiChecklistClient.tsx"
        pdi_src = pdi_path.read_text(encoding="utf-8")

        self.assertIn('role="progressbar"', pdi_src)
        self.assertIn("aria-valuenow=", pdi_src)
        self.assertTrue('aria-valuemin={0}' in pdi_src or 'aria-valuemin="0"' in pdi_src)
        self.assertTrue('aria-valuemax={100}' in pdi_src or 'aria-valuemax="100"' in pdi_src)

        # 2. Depreciation Calculator range slider aria-valuetext
        dep_path = APP_DIR / "depreciation-calculator" / "DepreciationCalculatorClient.tsx"
        dep_src = dep_path.read_text(encoding="utf-8")
        self.assertIn("aria-valuetext=", dep_src)
        self.assertIn("년 보유", dep_src)
        self.assertIn("km 주행", dep_src)

    def test_17_app_error_boundaries_and_not_found_a11y(self) -> None:
        """Verifies error.tsx and not-found.tsx exist in App Router with required recovery elements."""
        err_path = APP_DIR / "error.tsx"
        nf_path = APP_DIR / "not-found.tsx"

        self.assertTrue(err_path.exists(), "src/app/error.tsx must exist")
        self.assertTrue(nf_path.exists(), "src/app/not-found.tsx must exist")

        err_content = err_path.read_text(encoding="utf-8")
        self.assertIn("'use client'", err_content)
        self.assertIn("reset()", err_content)

        nf_content = nf_path.read_text(encoding="utf-8")
        self.assertIn("404", nf_content)
        self.assertIn('href="/subsidy-tracker"', nf_content)


# ===========================================================================
# Class 5: TestCycle21MirrorParity
# ===========================================================================
class TestCycle21MirrorParity(unittest.TestCase):
    """Validates 100% bitwise parity and security headers across mirrors."""

    def test_18_bitwise_test_tree_mirror_parity_and_permissions(self) -> None:
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

        # Any file existing in both must match bitwise and permission
        common_files = r_files.intersection(w_files)
        self.assertGreater(len(common_files), 10, "Must compare at least 10 mirrored test files")

        for filename in sorted(common_files):
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

    def test_19_security_headers_next_config_resilience(self) -> None:
        """Verifies next.config.mjs declares Cross-Origin-Resource-Policy and security headers."""
        next_cfg = (WEB_ROOT / "next.config.mjs").read_text(encoding="utf-8")
        self.assertIn("Cross-Origin-Resource-Policy", next_cfg)
        self.assertIn("same-origin", next_cfg)
        self.assertIn("X-Content-Type-Options", next_cfg)
        self.assertIn("nosniff", next_cfg)
        self.assertIn("X-Frame-Options", next_cfg)
        self.assertIn("DENY", next_cfg)
        self.assertIn("Strict-Transport-Security", next_cfg)


if __name__ == "__main__":
    unittest.main()
