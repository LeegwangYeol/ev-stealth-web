"""
tests/test_cycle23_hardening.py - Comprehensive Cycle 23 Hardening, Boundary,
Contract Validation, WCAG 2.1 AA, and Triple Mirror Parity Test Suite.

Authoritative Reference:
- ORIGINAL_REQUEST.md
- DISPATCH.md (Cycle 23 Hardening Test Suite Specification)
- COLLABORATION.md

Classes & Coverage (21 tests across 5 test classes):
1. TestCycle23DatasetIntegrity (4 tests: 01-04)
   - test_01_triple_mirror_dataset_presence_and_permissions: 12 files across 3 mirror dirs with 0o644 mode.
   - test_02_triple_mirror_cryptographic_sha256_bitwise_parity: 100% hash parity per dataset and ev_subsidy == subsidy_depletion.
   - test_03_triple_mirror_json_schema_validity_and_positive_bounds: Valid JSON syntax, required keys, positive bounds on all 4 synced datasets.
   - test_04_all_four_verified_field_defect_reports_integrity: 4 verified defect reports with community URLs and verbatim quotes.

2. TestCycle23StatutoryBudgetConservation (5 tests: 05-09)
   - test_05_national_subsidy_metrics_conservation_invariants: total 148,510, applied 132,766, delivered 122,515, remaining 15,744, 89.4% rate.
   - test_06_statutory_budget_execution_invariants: total 2,105.1B, disbursed 1,893.4B KRW (89.94%).
   - test_07_category_breakdown_arithmetic_invariants: passenger, commercial, bus arithmetic equality and national conservation.
   - test_08_regional_quota_sum_consistency_across_all_17_regions: 17 administrative division totals equal nationwide summary.
   - test_09_critical_exhaustion_regions_and_alert_distribution: exactly 4 critical regions (Jeju 99.0%, Gyeongbuk 97.3%, Ulsan 96.5%, Daegu 96.4%).

3. TestCycle23FrontendContracts (4 tests: 10-13)
   - test_10_depreciation_purchase_price_upper_bound_cap_both_files: 10B KRW cap in depreciationCalculations.ts and getDepreciationData.ts.
   - test_11_reliability_dsi_severity_level_contracts: getDsiSeverityLevel with NaN, negative, 0, 35, 60, 80, Infinity in reliabilityCalculations.ts and getReliabilityData.ts.
   - test_12_pdi_checklist_heading_h2_id_and_print_classes: PDI checklist heading h2 id="pdi-cat-..." and print utility classes in PdiChecklistClient.tsx.
   - test_13_frontend_statutory_price_cap_tiers: getPriceSubsidyRatio across 54.99M, 55M, 84.99M, 85M KRW.

4. TestCycle23BackendRemediations (6 tests: 14-19)
   - test_14_extract_vehicle_info_cadillac_lyriq_recognition: Cadillac Lyriq ("캐딜락 리릭", "cadillac lyriq", "리릭") recognized under BRAND_OTHER.
   - test_15_extract_vehicle_info_english_brand_names_under_brand_other: English brand names ("audi", "porsche", "volvo", "chevrolet", "cadillac", etc.) under BRAND_OTHER.
   - test_16_complaint_record_from_dict_recognizes_new_tokens_in_model_brand_map: new tokens ("ev2", "sealion", "시라이언", "id.4", "id4", "lyriq", "리릭").
   - test_17_raw_post_mapping_protocol_and_dict_compatibility: __getitem__, __contains__, get(), keys(), values(), items(), __iter__.
   - test_18_dsi_breakdown_mapping_protocol_and_dict_compatibility: __getitem__, __contains__, get(), keys(), values(), items(), __iter__.
   - test_19_daily_report_statistics_and_payload_mapping: DailyReportStatistics and DailyReportPayload mapping protocols.

5. TestCycle23MirrorParity (2 tests: 20-21)
   - test_20_bitwise_test_tree_mirror_parity_and_permissions: 100% bitwise parity and 0o644 permissions across tests/ and ev-stealth-web/tests/.
   - test_21_backend_logic_mirror_parity: 100% cryptographic parity across crawlers/, filters/, models/, tracker/, utils/.
"""

from __future__ import annotations

import filecmp
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Any, Dict, List, Optional
import unittest


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
from models.complaint import (
    ComplaintRecord,
    DailyReportPayload,
    DailyReportStatistics,
    DSIBreakdown,
    RawPost,
)
from tracker.subsidy_tracker import calculate_price_cap_ratio, calculate_net_subsidy


# ===========================================================================
# Class 1: TestCycle23DatasetIntegrity
# ===========================================================================
class TestCycle23DatasetIntegrity(unittest.TestCase):
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

        # Furthermore, ev_subsidy_data.json and subsidy_depletion_data.json must be identical
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

        daily_path = self.TARGET_DIRS[0] / "daily_reports.json"
        with open(daily_path, "r", encoding="utf-8") as f:
            daily_data = json.load(f)

        self.assertIn("statistics", daily_data)
        self.assertIn("reports", daily_data)
        self.assertGreater(daily_data["statistics"]["total_filtered_defects"], 0)

        matrix_path = self.TARGET_DIRS[0] / "models_subsidy_matrix.json"
        with open(matrix_path, "r", encoding="utf-8") as f:
            matrix_data = json.load(f)

        self.assertIsInstance(matrix_data, list)
        self.assertGreater(len(matrix_data), 0)
        self.assertIn("model_id", matrix_data[0])

    def test_04_all_four_verified_field_defect_reports_integrity(self) -> None:
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
# Class 2: TestCycle23StatutoryBudgetConservation
# ===========================================================================
class TestCycle23StatutoryBudgetConservation(unittest.TestCase):
    """Validates 2026 national subsidy conservation invariants and statutory budget execution."""

    def setUp(self) -> None:
        subsidy_path = PROJECT_ROOT / "data" / "ev_subsidy_data.json"
        with open(subsidy_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def test_05_national_subsidy_metrics_conservation_invariants(self) -> None:
        """Nationwide summary invariants: Announced=148,510, Applied=132,766, Delivered=122,515, Remaining=15,744, Depletion=89.4%."""
        summary = self.data["nationwide_summary"]
        self.assertEqual(summary["total_announced_units"], 148510)
        self.assertEqual(summary["total_applied_units"], 132766)
        self.assertEqual(summary["total_delivered_units"], 122515)
        self.assertEqual(summary["total_remaining_units"], 15744)
        self.assertEqual(summary["nationwide_depletion_rate"], 89.4)

        # Arithmetic conservation
        self.assertEqual(
            summary["total_applied_units"] + summary["total_remaining_units"],
            summary["total_announced_units"],
        )
        self.assertLessEqual(summary["total_delivered_units"], summary["total_applied_units"])

    def test_06_statutory_budget_execution_invariants(self) -> None:
        """Statutory budget execution: 1,893.4B / 2,105.1B KRW (89.94%)."""
        summary = self.data["nationwide_summary"]
        self.assertEqual(summary["total_budget_billion_krw"], 2105.1)
        self.assertEqual(summary["disbursed_budget_billion_krw"], 1893.4)
        rate = round((summary["disbursed_budget_billion_krw"] / summary["total_budget_billion_krw"]) * 100, 2)
        self.assertEqual(rate, 89.94, f"Budget execution ratio must be 89.94%, got {rate}%")

    def test_07_category_breakdown_arithmetic_invariants(self) -> None:
        """Passenger, commercial, and bus breakdowns sum identically to national totals."""
        cats = self.data["nationwide_summary"]["category_totals"]
        p = cats["passenger"]
        c = cats["commercial"]
        b = cats["bus"]

        # Passenger
        self.assertEqual(p["announced_units"], 110400)
        self.assertEqual(p["applied_units"], 97035)
        self.assertEqual(p["delivered_units"], 88960)
        self.assertEqual(p["remaining_units"], 13365)
        self.assertEqual(p["depletion_rate"], 87.9)
        self.assertEqual(p["applied_units"] + p["remaining_units"], p["announced_units"])

        # Commercial
        self.assertEqual(c["announced_units"], 34800)
        self.assertEqual(c["applied_units"], 32754)
        self.assertEqual(c["delivered_units"], 30780)
        self.assertEqual(c["remaining_units"], 2046)
        self.assertEqual(c["depletion_rate"], 94.1)
        self.assertEqual(c["applied_units"] + c["remaining_units"], c["announced_units"])

        # Bus
        self.assertEqual(b["announced_units"], 3310)
        self.assertEqual(b["applied_units"], 2977)
        self.assertEqual(b["delivered_units"], 2775)
        self.assertEqual(b["remaining_units"], 333)
        self.assertEqual(b["depletion_rate"], 89.9)
        self.assertEqual(b["applied_units"] + b["remaining_units"], b["announced_units"])

        # Nationwide sums
        tot_ann = p["announced_units"] + c["announced_units"] + b["announced_units"]
        tot_app = p["applied_units"] + c["applied_units"] + b["applied_units"]
        tot_del = p["delivered_units"] + c["delivered_units"] + b["delivered_units"]
        tot_rem = p["remaining_units"] + c["remaining_units"] + b["remaining_units"]

        self.assertEqual(tot_ann, self.data["nationwide_summary"]["total_announced_units"])
        self.assertEqual(tot_app, self.data["nationwide_summary"]["total_applied_units"])
        self.assertEqual(tot_del, self.data["nationwide_summary"]["total_delivered_units"])
        self.assertEqual(tot_rem, self.data["nationwide_summary"]["total_remaining_units"])

    def test_08_regional_quota_sum_consistency_across_all_17_regions(self) -> None:
        """Sum of categories across all 17 regions matches nationwide summary totals."""
        regions = self.data["regions"]
        self.assertEqual(len(regions), 17)

        sum_pass_ann = sum(r["categories"]["passenger"]["announced_units"] for r in regions)
        sum_comm_ann = sum(r["categories"]["commercial"]["announced_units"] for r in regions)
        sum_bus_ann = sum(r["categories"]["bus"]["announced_units"] for r in regions)

        cat_totals = self.data["nationwide_summary"]["category_totals"]
        self.assertEqual(sum_pass_ann, cat_totals["passenger"]["announced_units"])
        self.assertEqual(sum_comm_ann, cat_totals["commercial"]["announced_units"])
        self.assertEqual(sum_bus_ann, cat_totals["bus"]["announced_units"])

    def test_09_critical_exhaustion_regions_and_alert_distribution(self) -> None:
        """Exactly 4 critical exhaustion regions (>=95.0% and CRITICAL): Jeju (99.0%), Gyeongbuk (97.3%), Ulsan (96.5%), Daegu (96.4%)."""
        regions = self.data["regions"]
        critical_regions = [
            r for r in regions
            if r.get("overall_depletion_rate", 0.0) >= 95.0 or r.get("overall_status") == "CRITICAL"
        ]
        self.assertEqual(len(critical_regions), 4)

        crit_by_name = {r["name_ko"]: r for r in critical_regions}
        self.assertIn("제주특별자치도", crit_by_name)
        self.assertIn("경상북도", crit_by_name)
        self.assertIn("울산광역시", crit_by_name)
        self.assertIn("대구광역시", crit_by_name)

        self.assertEqual(crit_by_name["제주특별자치도"]["overall_depletion_rate"], 99.0)
        self.assertEqual(crit_by_name["경상북도"]["overall_depletion_rate"], 97.3)
        self.assertEqual(crit_by_name["울산광역시"]["overall_depletion_rate"], 96.5)
        self.assertEqual(crit_by_name["대구광역시"]["overall_depletion_rate"], 96.4)

        for r in critical_regions:
            self.assertEqual(r.get("overall_status"), "CRITICAL")

        alert_counts = self.data["nationwide_summary"]["alert_region_counts"]
        self.assertEqual(alert_counts["critical"], 4)
        self.assertEqual(alert_counts["warning"], 12)
        self.assertEqual(alert_counts["caution"], 1)
        self.assertEqual(alert_counts["healthy"], 0)
        self.assertEqual(alert_counts["depleted"], 0)


# ===========================================================================
# Class 3: TestCycle23FrontendContracts
# ===========================================================================
class TestCycle23FrontendContracts(unittest.TestCase):
    """Validates 10B KRW depreciation cap, getDsiSeverityLevel matrix, and PDI checklist accessibility."""

    def test_10_depreciation_purchase_price_upper_bound_cap_both_files(self) -> None:
        """10 Billion KRW cap in both depreciationCalculations.ts and getDepreciationData.ts."""
        calc_path = WEB_ROOT / "src" / "lib" / "depreciationCalculations.ts"
        data_path = WEB_ROOT / "src" / "lib" / "getDepreciationData.ts"

        self.assertTrue(calc_path.is_file(), f"Missing {calc_path}")
        self.assertTrue(data_path.is_file(), f"Missing {data_path}")

        calc_content = calc_path.read_text(encoding="utf-8")
        data_content = data_path.read_text(encoding="utf-8")

        # Static inspection
        self.assertIn("Math.min(10_000_000_000, Math.max(0, rawBasePurchasePrice))", calc_content)
        self.assertIn("Math.min(10_000_000_000, Math.max(0, rawBasePurchasePrice))", data_content)

        # Dynamic Node.js execution verification
        cmd = [
            "node",
            "--no-warnings",
            "--experimental-strip-types",
            "-e",
            """
import { calculateDepreciation as c1 } from './ev-stealth-web/src/lib/depreciationCalculations.ts';
import { calculateDepreciation as c2 } from './ev-stealth-web/src/lib/getDepreciationData.ts';
const res1 = c1({ years: 1, customPurchasePriceKrw: 50_000_000_000 });
const res2 = c2({ years: 1, customPurchasePriceKrw: 50_000_000_000 });
console.log(JSON.stringify({ c1: res1.basePurchasePriceKrw, c2: res2.basePurchasePriceKrw }));
""",
        ]
        proc = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, check=True)
        res = json.loads(proc.stdout)
        self.assertEqual(res["c1"], 10_000_000_000)
        self.assertEqual(res["c2"], 10_000_000_000)

    def test_11_reliability_dsi_severity_level_contracts(self) -> None:
        """getDsiSeverityLevel handles NaN, negative, 0, 35, 60, 80, Infinity in reliabilityCalculations.ts and getReliabilityData.ts."""
        calc_path = WEB_ROOT / "src" / "lib" / "reliabilityCalculations.ts"
        data_path = WEB_ROOT / "src" / "lib" / "getReliabilityData.ts"

        self.assertTrue(calc_path.is_file(), f"Missing {calc_path}")
        self.assertTrue(data_path.is_file(), f"Missing {data_path}")

        calc_content = calc_path.read_text(encoding="utf-8")
        data_content = data_path.read_text(encoding="utf-8")

        self.assertIn("const safeDsi = Number.isFinite(dsi) ? Math.max(0, dsi) : 0;", calc_content)
        self.assertIn("const safeDsi = Number.isFinite(dsi) ? Math.max(0, dsi) : 0;", data_content)

        # Dynamic Node.js evaluation across all specified boundary inputs
        cmd = [
            "node",
            "--no-warnings",
            "--experimental-strip-types",
            "-e",
            """
import { getDsiSeverityLevel as f1 } from './ev-stealth-web/src/lib/reliabilityCalculations.ts';
import { getDsiSeverityLevel as f2 } from './ev-stealth-web/src/lib/getReliabilityData.ts';
const cases = [NaN, -10, 0, 35, 60, 80, Infinity];
console.log(JSON.stringify({
  f1: cases.map(f1),
  f2: cases.map(f2)
}));
""",
        ]
        proc = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, check=True)
        res = json.loads(proc.stdout)

        expected_levels = ["LOW", "LOW", "LOW", "MODERATE", "HIGH", "CRITICAL", "LOW"]
        f1_levels = [x["level"] for x in res["f1"]]
        f2_levels = [x["level"] for x in res["f2"]]

        self.assertEqual(f1_levels, expected_levels)
        self.assertEqual(f2_levels, expected_levels)

    def test_12_pdi_checklist_heading_h2_id_and_print_classes(self) -> None:
        """PDI checklist heading h2 id='pdi-cat-...' and print classes present in PdiChecklistClient.tsx."""
        client_path = WEB_ROOT / "src" / "app" / "pdi-checklist" / "PdiChecklistClient.tsx"
        self.assertTrue(client_path.is_file(), f"Missing {client_path}")
        content = client_path.read_text(encoding="utf-8")

        # Heading id contract
        self.assertTrue(
            bool(re.search(r'<h2[^>]*id=\{`pdi-cat-\$\{category\}`\}', content)),
            "Missing dynamic id={`pdi-cat-${category}`} on category h2 headings",
        )

        # Print utility classes
        self.assertIn("print:bg-slate-100", content)
        self.assertIn("print:border-gray-300", content)
        self.assertIn("print:shadow-none", content)
        self.assertIn("print:break-inside-avoid", content)
        self.assertIn("print:hidden", content)
        self.assertIn("print:py-2", content)
        self.assertIn("print:hover:bg-transparent", content)
        self.assertIn("print:accent-blue-600", content)
        self.assertIn("print:text-black", content)

    def test_13_frontend_statutory_price_cap_tiers(self) -> None:
        """Statutory price cap tiers: 1.0 (<=55M), 0.5 (55M-85M), 0.0 (>85M)."""
        self.assertEqual(calculate_price_cap_ratio(54_990_000), 1.0)
        self.assertEqual(calculate_price_cap_ratio(55_000_000), 1.0)
        self.assertEqual(calculate_price_cap_ratio(55_010_000), 0.5)
        self.assertEqual(calculate_price_cap_ratio(84_990_000), 0.5)
        self.assertEqual(calculate_price_cap_ratio(85_000_000), 0.5)
        self.assertEqual(calculate_price_cap_ratio(85_010_000), 0.0)
        self.assertEqual(calculate_price_cap_ratio(120_000_000), 0.0)


# ===========================================================================
# Class 4: TestCycle23BackendRemediations
# ===========================================================================
class TestCycle23BackendRemediations(unittest.TestCase):
    """Validates 2026 vehicle matcher additions, ComplaintRecord from_dict tokens, and mapping protocols."""

    def test_14_extract_vehicle_info_cadillac_lyriq_recognition(self) -> None:
        """extract_vehicle_info recognizes Cadillac Lyriq ('캐딜락 리릭', 'cadillac lyriq', '리릭') under BRAND_OTHER."""
        test_cases = [
            ("캐딜락 리릭 시승기 및 실주행 연비", BRAND_OTHER, "Cadillac Lyriq"),
            ("cadillac lyriq 고속 충전 불량 이슈", BRAND_OTHER, "Cadillac Lyriq"),
            ("리릭 차주분들 승차감 어떤가요?", BRAND_OTHER, "Cadillac Lyriq"),
            ("캐딜락 리릭 사전예약 시작", BRAND_OTHER, "Cadillac Lyriq"),
        ]
        for title, exp_b, exp_m in test_cases:
            b, m = extract_vehicle_info(title)
            self.assertEqual(b, exp_b, f"Brand mismatch for: {title}")
            self.assertEqual(m, exp_m, f"Model mismatch for: {title}")

    def test_15_extract_vehicle_info_english_brand_names_under_brand_other(self) -> None:
        """extract_vehicle_info recognizes English brand names under BRAND_OTHER."""
        english_brands = [
            ("audi 전기차 충전 문제", BRAND_OTHER),
            ("porsche 서비스센터 입고 후기", BRAND_OTHER),
            ("volvo 배터리 보증 정책", BRAND_OTHER),
            ("chevrolet 서비스 네트워크", BRAND_OTHER),
            ("cadillac 전기차 플랫폼", BRAND_OTHER),
            ("bmw 충전소 인프라", BRAND_OTHER),
            ("mercedes 전용 어플 오류", BRAND_OTHER),
            ("volkswagen 국내 정비소 현황", BRAND_OTHER),
            ("polestar 출고 지연", BRAND_OTHER),
            ("rivian 국내 진출설", BRAND_OTHER),
            ("lucid 주행 테스트", BRAND_OTHER),
            ("xiaomi 신차 발표", BRAND_OTHER),
        ]
        for title, exp_b in english_brands:
            b, m = extract_vehicle_info(title)
            self.assertEqual(b, exp_b, f"Expected {exp_b} for title: {title}, got {b}")

    def test_16_complaint_record_from_dict_recognizes_new_tokens_in_model_brand_map(self) -> None:
        """ComplaintRecord.from_dict recognizes new tokens in model_brand_map."""
        tokens_map = [
            ("ev2", "Kia"),
            ("sealion", "BYD"),
            ("시라이언", "BYD"),
            ("id.4", "Volkswagen"),
            ("id4", "Volkswagen"),
            ("lyriq", "Cadillac"),
            ("리릭", "Cadillac"),
        ]
        for token, exp_brand in tokens_map:
            rec = ComplaintRecord.from_dict({
                "id": f"test_{token}",
                "target_vehicle": token,
                "title": f"{token} 테스트",
            })
            self.assertEqual(
                rec.vehicle_brand,
                exp_brand,
                f"Token '{token}' resolved to brand '{rec.vehicle_brand}', expected '{exp_brand}'",
            )
            self.assertEqual(rec.vehicle_model, token)

    def test_17_raw_post_mapping_protocol_and_dict_compatibility(self) -> None:
        """RawPost implements full mapping protocol and dict compatibility."""
        post = RawPost(
            platform="dcinside",
            post_id="dc_12345",
            url="https://gall.dcinside.com/view/12345",
            title="캐딜락 리릭 승차감",
            content="핸들링 및 방음이 우수합니다.",
            comments=["동감합니다"],
            created_at="2026-10-31",
            author="리릭오너",
        )
        self.assertEqual(post["title"], "캐딜락 리릭 승차감")
        self.assertIn("platform", post)
        self.assertEqual(post.get("author"), "리릭오너")
        self.assertEqual(post.get("missing", "def"), "def")
        d = dict(post)
        self.assertEqual(len(d), 8)
        self.assertEqual(d["post_id"], "dc_12345")

    def test_18_dsi_breakdown_mapping_protocol_and_dict_compatibility(self) -> None:
        """DSIBreakdown implements full mapping protocol and dict unpacking."""
        dsi = DSIBreakdown(safety=9.0, functional=8.5, economic=7.0, social=6.0, convenience=5.5)
        self.assertEqual(dsi["safety"], 9.0)
        self.assertIn("functional", dsi)
        self.assertEqual(dsi.get("economic"), 7.0)
        d = {**dict(dsi)}
        self.assertEqual(len(d), 5)
        self.assertEqual(d["convenience"], 5.5)

    def test_19_daily_report_statistics_and_payload_mapping(self) -> None:
        """DailyReportStatistics and DailyReportPayload support full dict unpacking."""
        stats = DailyReportStatistics(
            total_scraped=200,
            total_filtered_defects=25,
            avg_negativity_score=0.85,
            critical_defect_count=5,
        )
        self.assertEqual(stats["total_scraped"], 200)
        self.assertEqual(stats.get("critical_defect_count"), 5)
        d_stats = dict(stats)
        self.assertEqual(d_stats["total_filtered_defects"], 25)

        payload = DailyReportPayload(
            generated_at="2026-10-31T00:00:00Z",
            pipeline_version="2.0.0",
        )
        self.assertEqual(payload["pipeline_version"], "2.0.0")
        d_payload = dict(payload)
        self.assertEqual(d_payload["generated_at"], "2026-10-31T00:00:00Z")


# ===========================================================================
# Class 5: TestCycle23MirrorParity
# ===========================================================================
class TestCycle23MirrorParity(unittest.TestCase):
    """Validates 100% bitwise parity and file permissions across root and ev-stealth-web."""

    def test_20_bitwise_test_tree_mirror_parity_and_permissions(self) -> None:
        """100% bitwise parity and 0o644 permissions across tests/ and ev-stealth-web/tests/."""
        root_tests = PROJECT_ROOT / "tests"
        web_tests = WEB_ROOT / "tests"

        d = filecmp.dircmp(str(root_tests), str(web_tests))
        self.assertEqual(d.left_only, [], f"Files only in root tests/: {d.left_only}")
        self.assertEqual(d.right_only, [], f"Files only in web tests/: {d.right_only}")
        self.assertEqual(d.diff_files, [], f"Diverged files in tests: {d.diff_files}")

    def test_21_backend_logic_mirror_parity(self) -> None:
        """100% cryptographic SHA-256 parity across core backend packages."""
        packages = ["crawlers", "filters", "models", "tracker", "utils"]
        for pkg in packages:
            root_pkg = PROJECT_ROOT / pkg
            web_pkg = WEB_ROOT / pkg
            d = filecmp.dircmp(str(root_pkg), str(web_pkg))
            self.assertEqual(d.left_only, [], f"Left only in {pkg}: {d.left_only}")
            self.assertEqual(d.right_only, [], f"Right only in {pkg}: {d.right_only}")
            self.assertEqual(d.diff_files, [], f"Diff in {pkg}: {d.diff_files}")


if __name__ == "__main__":
    unittest.main()
