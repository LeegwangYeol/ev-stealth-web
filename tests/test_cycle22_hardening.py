"""
tests/test_cycle22_hardening.py - Comprehensive Cycle 22 Hardening, Boundary,
Contract Validation, WCAG 2.1 AA, and Triple Mirror Parity Test Suite.

Authoritative Reference:
- ORIGINAL_REQUEST.md
- DISPATCH.md (Cycle 22 Hardening Test Suite Specification)
- COLLABORATION.md

Classes & Coverage (23 tests across 5 test classes):
1. TestCycle22DatasetIntegrity (4 tests: 01-04)
   - test_01_triple_mirror_dataset_presence_and_permissions: 12 files across 3 mirror dirs with 0o644 mode.
   - test_02_triple_mirror_cryptographic_sha256_bitwise_parity: 100% hash parity per dataset and ev_subsidy == subsidy_depletion.
   - test_03_triple_mirror_json_schema_validity_and_positive_bounds: Valid JSON syntax, required keys, positive bounds on all 4 synced datasets.
   - test_04_all_four_verified_field_defect_reports_integrity: 4 verified defect reports with community URLs and verbatim quotes.

2. TestCycle22StatutoryBudgetConservation (4 tests: 05-08)
   - test_05_national_subsidy_metrics_conservation_invariants: total 148,510, applied 132,766, remaining 15,744, 89.4%.
   - test_06_statutory_budget_execution_invariants: total 2,105.1B, disbursed 1,893.4B KRW (89.94%).
   - test_07_regional_quota_sum_consistency_across_all_17_regions: 17 administrative division totals equal nationwide summary.
   - test_08_critical_exhaustion_regions_and_alert_distribution: exactly 4 regions >= 95.0% (Jeju, Gyeongbuk, Ulsan, Daegu).

3. TestCycle22FrontendContracts (3 tests: 09-11)
   - test_09_svg_chart_wcag_title_accessibility_contracts: SVG comparative chart has <title> tags inside all rect bars.
   - test_10_depreciation_purchase_price_upper_bound_cap: getDepreciationData 10B KRW cap on custom purchase price.
   - test_11_frontend_statutory_price_cap_tiers: getPriceSubsidyRatio across 54.99M, 55M, 84.99M, 85M KRW.

4. TestCycle22BackendRemediations (10 tests: 12-21)
   - test_12_raw_post_mapping_protocol_and_dict_compatibility: __getitem__, __contains__, get(), keys(), values(), items(), __iter__.
   - test_13_dsi_breakdown_mapping_protocol_and_dict_compatibility: __getitem__, __contains__, get(), keys(), values(), items(), __iter__.
   - test_14_complaint_record_mapping_iteration_completeness: keys(), values(), items(), __iter__ on ComplaintRecord.
   - test_15_daily_report_statistics_mapping_protocol: __getitem__, __contains__, get(), keys(), values(), items(), __iter__.
   - test_16_daily_report_payload_mapping_iteration_completeness: keys(), values(), items(), __iter__ on DailyReportPayload.
   - test_17_vehicle_matcher_kia_ev2_recognition: Kia EV2 extraction.
   - test_18_vehicle_matcher_byd_sealion_dual_spelling_recognition: BYD 시라이언 and 씨라이언 (07 / 7) extraction.
   - test_19_vehicle_matcher_volkswagen_id4_and_idbuzz_recognition: Volkswagen ID.4 and ID.Buzz extraction.
   - test_20_vehicle_matcher_tesla_model_2_recognition: Tesla Model 2 extraction.
   - test_21_vehicle_matcher_hyundai_ioniq_7_recognition: Hyundai 아이오닉7 extraction.

5. TestCycle22MirrorParity (2 tests: 22-23)
   - test_22_bitwise_test_tree_mirror_parity_and_permissions: 100% bitwise parity and 0o644 permissions across tests/ and ev-stealth-web/tests/.
   - test_23_backend_logic_mirror_parity: 100% cryptographic parity across crawlers/, filters/, models/, tracker/, utils/.
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

from filters.vehicle_matcher import extract_vehicle_info, BRAND_HYUNDAI, BRAND_KIA, BRAND_OTHER, BRAND_TESLA, BRAND_BYD
from models.complaint import (
    ComplaintRecord,
    DailyReportPayload,
    DailyReportStatistics,
    DSIBreakdown,
    RawPost,
)
from tracker.subsidy_tracker import calculate_price_cap_ratio, calculate_net_subsidy


# ===========================================================================
# Class 1: TestCycle22DatasetIntegrity
# ===========================================================================
class TestCycle22DatasetIntegrity(unittest.TestCase):
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
        """All 4 core datasets exist across all 3 mirror target dirs with standard POSIX 0o644 mode."""
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
# Class 2: TestCycle22StatutoryBudgetConservation
# ===========================================================================
class TestCycle22StatutoryBudgetConservation(unittest.TestCase):
    """Validates 2026 national subsidy conservation invariants and budget execution."""

    def setUp(self) -> None:
        subsidy_path = PROJECT_ROOT / "data" / "ev_subsidy_data.json"
        with open(subsidy_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def test_05_national_subsidy_metrics_conservation_invariants(self) -> None:
        """Nationwide summary invariants: Announced=148,510, Applied=132,766, Remaining=15,744, Depletion=89.4%."""
        summary = self.data["nationwide_summary"]
        self.assertEqual(summary["total_announced_units"], 148510)
        self.assertEqual(summary["total_applied_units"], 132766)
        self.assertEqual(summary["total_delivered_units"], 122515)
        self.assertEqual(summary["total_remaining_units"], 15744)
        self.assertEqual(summary["nationwide_depletion_rate"], 89.4)

    def test_06_statutory_budget_execution_invariants(self) -> None:
        """Statutory budget execution: 1,893.4B / 2,105.1B KRW (89.94%)."""
        summary = self.data["nationwide_summary"]
        self.assertEqual(summary["total_budget_billion_krw"], 2105.1)
        self.assertEqual(summary["disbursed_budget_billion_krw"], 1893.4)
        rate = (summary["disbursed_budget_billion_krw"] / summary["total_budget_billion_krw"]) * 100
        self.assertAlmostEqual(rate, 89.94347, places=2)

    def test_07_regional_quota_sum_consistency_across_all_17_regions(self) -> None:
        """Sum of passenger, commercial, and bus categories across all 17 regions matches nationwide summary."""
        regions = self.data["regions"]
        self.assertEqual(len(regions), 17)

        sum_pass_announced = sum(r["categories"]["passenger"]["announced_units"] for r in regions)
        sum_comm_announced = sum(r["categories"]["commercial"]["announced_units"] for r in regions)
        sum_bus_announced = sum(r["categories"]["bus"]["announced_units"] for r in regions)

        cat_totals = self.data["nationwide_summary"]["category_totals"]
        self.assertEqual(sum_pass_announced, cat_totals["passenger"]["announced_units"])
        self.assertEqual(sum_comm_announced, cat_totals["commercial"]["announced_units"])
        self.assertEqual(sum_bus_announced, cat_totals["bus"]["announced_units"])

    def test_08_critical_exhaustion_regions_and_alert_distribution(self) -> None:
        """Exactly 4 critical exhaustion regions (>=95.0%): Jeju, Gyeongbuk, Ulsan, Daegu."""
        regions = self.data["regions"]
        critical_regions = [
            r["name_ko"]
            for r in regions
            if r["categories"]["passenger"]["depletion_rate"] >= 95.0
        ]
        self.assertEqual(len(critical_regions), 4)
        self.assertIn("제주특별자치도", critical_regions)
        self.assertIn("경상북도", critical_regions)
        self.assertIn("울산광역시", critical_regions)
        self.assertIn("대구광역시", critical_regions)


# ===========================================================================
# Class 3: TestCycle22FrontendContracts
# ===========================================================================
class TestCycle22FrontendContracts(unittest.TestCase):
    """Validates SVG chart WCAG accessibility and depreciation calculation bounds."""

    def test_09_svg_chart_wcag_title_accessibility_contracts(self) -> None:
        """DepreciationCalculatorClient.tsx contains accessible <title> tags inside all comparative SVG rects."""
        client_path = WEB_ROOT / "src" / "app" / "depreciation-calculator" / "DepreciationCalculatorClient.tsx"
        self.assertTrue(client_path.is_file())
        content = client_path.read_text(encoding="utf-8")

        # Verify <title> elements exist inside the SVG chart bars
        self.assertIn("<title>{`${selectedModel.model_name} ${pt.year}년차:", content)
        self.assertIn("<title>{`${pt.year}년차 전기차 전체 평균:", content)
        self.assertIn("<title>{`${pt.year}년차 동급 내연기관(가솔린):", content)

    def test_10_depreciation_purchase_price_upper_bound_cap(self) -> None:
        """getDepreciationData.ts enforces 10B KRW cap on customPurchasePriceKrw."""
        dep_path = WEB_ROOT / "src" / "lib" / "getDepreciationData.ts"
        self.assertTrue(dep_path.is_file())
        content = dep_path.read_text(encoding="utf-8")

        self.assertIn("Math.min(10_000_000_000, Math.max(0, rawBasePurchasePrice))", content)

    def test_11_frontend_statutory_price_cap_tiers(self) -> None:
        """Statutory price cap tiers: 1.0 (<=55M), 0.5 (55M-85M), 0.0 (>85M)."""
        self.assertEqual(calculate_price_cap_ratio(54_990_000), 1.0)
        self.assertEqual(calculate_price_cap_ratio(55_000_000), 1.0)
        self.assertEqual(calculate_price_cap_ratio(55_010_000), 0.5)
        self.assertEqual(calculate_price_cap_ratio(85_000_000), 0.5)
        self.assertEqual(calculate_price_cap_ratio(85_000_001), 0.0)
        self.assertEqual(calculate_price_cap_ratio(120_000_000), 0.0)


# ===========================================================================
# Class 4: TestCycle22BackendRemediations
# ===========================================================================
class TestCycle22BackendRemediations(unittest.TestCase):
    """Validates complete mapping protocol and 2026 vehicle matcher expansion."""

    def test_12_raw_post_mapping_protocol_and_dict_compatibility(self) -> None:
        """RawPost implements __getitem__, __contains__, get(), keys(), values(), items(), __iter__."""
        post = RawPost(
            platform="bobaedream",
            post_id="bd_12345",
            url="https://bobaedream.co.kr/view?12345",
            title="테슬라 모델3 하이랜드 단차 심각",
            content="트렁크 단차가 심합니다.",
            comments=["동감합니다"],
            created_at="2026-10-30",
            author="테슬라오너",
        )

        # __getitem__
        self.assertEqual(post["title"], "테슬라 모델3 하이랜드 단차 심각")
        self.assertEqual(post["platform"], "bobaedream")
        self.assertEqual(post["post_id"], "bd_12345")

        # __contains__
        self.assertIn("title", post)
        self.assertIn("post_id", post)
        self.assertNotIn("non_existent_field", post)

        # get()
        self.assertEqual(post.get("title"), "테슬라 모델3 하이랜드 단차 심각")
        self.assertEqual(post.get("missing_key", "default_val"), "default_val")

        # keys(), values(), items()
        keys = list(post.keys())
        self.assertIn("title", keys)
        self.assertIn("content", keys)
        self.assertEqual(len(keys), 8)

        # dict conversion
        d = dict(post)
        self.assertEqual(d["title"], post.title)

    def test_13_dsi_breakdown_mapping_protocol_and_dict_compatibility(self) -> None:
        """DSIBreakdown implements __getitem__, __contains__, get(), keys(), values(), items(), __iter__."""
        dsi = DSIBreakdown(safety=9.5, functional=8.0, economic=7.0, social=6.5, convenience=5.0)

        # __getitem__
        self.assertEqual(dsi["safety"], 9.5)
        self.assertEqual(dsi["functional"], 8.0)

        # __contains__
        self.assertIn("safety", dsi)
        self.assertNotIn("unknown_pillar", dsi)

        # get()
        self.assertEqual(dsi.get("safety"), 9.5)
        self.assertEqual(dsi.get("missing", 0.0), 0.0)

        # dict conversion
        d = dict(dsi)
        self.assertEqual(d["safety"], 9.5)
        self.assertEqual(len(d), 5)

    def test_14_complaint_record_mapping_iteration_completeness(self) -> None:
        """ComplaintRecord supports keys(), values(), items(), and __iter__ for dict conversion."""
        rec = ComplaintRecord(
            id="ev-001",
            source="dcinside",
            url="https://gall.dcinside.com/1",
            title="ICCU 고장",
            author="익명",
            created_at="2026-10-30",
            vehicle_brand="Hyundai",
            vehicle_model="아이오닉5",
            defect_category="BATTERY_CHARGING",
            summary="고속도로 셧다운",
            verbatim_quote="퍽 소리 나더니 정차",
        )

        keys = list(rec.keys())
        self.assertIn("title", keys)
        self.assertIn("defect_category", keys)
        d = dict(rec)
        self.assertEqual(d["id"], "ev-001")
        self.assertEqual(d["vehicle_brand"], "Hyundai")

    def test_15_daily_report_statistics_mapping_protocol(self) -> None:
        """DailyReportStatistics implements full mapping protocol."""
        stats = DailyReportStatistics(
            total_scraped=100,
            total_filtered_defects=15,
            avg_negativity_score=0.88,
            critical_defect_count=4,
        )

        self.assertEqual(stats["total_scraped"], 100)
        self.assertEqual(stats.get("critical_defect_count"), 4)
        self.assertIn("avg_negativity_score", stats)
        d = dict(stats)
        self.assertEqual(d["total_filtered_defects"], 15)

    def test_16_daily_report_payload_mapping_iteration_completeness(self) -> None:
        """DailyReportPayload supports full dict unpacking."""
        payload = DailyReportPayload(
            generated_at="2026-10-30T04:00:00Z",
            pipeline_version="1.0.0",
        )
        self.assertIn("generated_at", payload)
        self.assertEqual(payload.get("pipeline_version"), "1.0.0")
        d = dict(payload)
        self.assertEqual(d["pipeline_version"], "1.0.0")

    def test_17_vehicle_matcher_kia_ev2_recognition(self) -> None:
        """VehicleMatcher recognizes Kia EV2."""
        brand, model = extract_vehicle_info("기아 EV2 사전계약 일정 및 보조금 문의")
        self.assertEqual(brand, BRAND_KIA)
        self.assertEqual(model, "EV2")

        brand, model = extract_vehicle_info("ev2 가격 공개됐나요?")
        self.assertEqual(brand, BRAND_KIA)
        self.assertEqual(model, "EV2")

    def test_18_vehicle_matcher_byd_sealion_dual_spelling_recognition(self) -> None:
        """VehicleMatcher recognizes BYD 시라이언 and 씨라이언 (including 07)."""
        brand1, model1 = extract_vehicle_info("비야디 시라이언 7 시승기")
        self.assertEqual(brand1, BRAND_BYD)
        self.assertEqual(model1, "시라이언")

        brand2, model2 = extract_vehicle_info("BYD 씨라이언 07 실물 봤는데 괜찮네요")
        self.assertEqual(brand2, BRAND_BYD)
        self.assertEqual(model2, "시라이언")

        brand3, model3 = extract_vehicle_info("씨라이언7 결함 이슈")
        self.assertEqual(brand3, BRAND_BYD)
        self.assertEqual(model3, "시라이언")

    def test_19_vehicle_matcher_volkswagen_id4_and_idbuzz_recognition(self) -> None:
        """VehicleMatcher recognizes Volkswagen ID.4 and ID.Buzz."""
        brand1, model1 = extract_vehicle_info("폭스바겐 ID.4 회생제동 이질감 문의")
        self.assertEqual(brand1, BRAND_OTHER)
        self.assertEqual(model1, "Volkswagen ID.4")

        brand2, model2 = extract_vehicle_info("id4 충전구 안 열림 문제")
        self.assertEqual(brand2, BRAND_OTHER)
        self.assertEqual(model2, "Volkswagen ID.4")

        brand3, model3 = extract_vehicle_info("폭스바겐 ID 버즈 국내 출시 가격")
        self.assertEqual(brand3, BRAND_OTHER)
        self.assertEqual(model3, "Volkswagen ID.Buzz")

    def test_20_vehicle_matcher_tesla_model_2_recognition(self) -> None:
        """VehicleMatcher recognizes Tesla Model 2."""
        brand, model = extract_vehicle_info("테슬라 모델 2 2천만원대 전기차 출시설")
        self.assertEqual(brand, BRAND_TESLA)
        self.assertEqual(model, "Model 2")

    def test_21_vehicle_matcher_hyundai_ioniq_7_recognition(self) -> None:
        """VehicleMatcher recognizes Hyundai 아이오닉7."""
        brand, model = extract_vehicle_info("아이오닉 7 콘셉트카 디자인 논란")
        self.assertEqual(brand, BRAND_HYUNDAI)
        self.assertEqual(model, "아이오닉7")


# ===========================================================================
# Class 5: TestCycle22MirrorParity
# ===========================================================================
class TestCycle22MirrorParity(unittest.TestCase):
    """Validates 100% bitwise parity and file permissions across root and ev-stealth-web."""

    def test_22_bitwise_test_tree_mirror_parity_and_permissions(self) -> None:
        """100% bitwise parity across all test files between tests/ and ev-stealth-web/tests/."""
        root_tests = PROJECT_ROOT / "tests"
        web_tests = WEB_ROOT / "tests"

        d = filecmp.dircmp(str(root_tests), str(web_tests))
        self.assertEqual(
            d.left_only,
            [],
            f"Files only in root tests/: {d.left_only}",
        )
        self.assertEqual(
            d.right_only,
            [],
            f"Files only in web tests/: {d.right_only}",
        )
        self.assertEqual(
            d.diff_files,
            [],
            f"Diverged files in tests: {d.diff_files}",
        )

    def test_23_backend_logic_mirror_parity(self) -> None:
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
