"""
tests/test_frontend_cycle16_fixes.py - Verification tests for Cycle 16 Frontend Logic & Component Remediations.

Validates:
1. src/lib/getRecallData.ts: getModelsForBrand unions models from battery_profiles, vin_prefixes, vehicles, and recalls.
2. src/app/depreciation-calculator/DepreciationCalculatorClient.tsx:
   - Dynamic holding period labels (${holdingYears}개년 누적 절감액, ${holdingYears}년 종합 경제성 최종 판정).
   - Export clawback subtext formatting displaying national and local subsidy components.
3. src/lib/getDailyReports.ts:
   - Catch fallback returning '해당 없음 (0건)' and '해당 없음 (0%)'.
   - Severity tier taxonomy mapping for CRITICAL, HIGH, MEDIUM, LOW and preserving created_at and rich metadata.
4. src/app/secret-admin-reports/AdminDashboardClient.tsx:
   - SEVERITY_WEIGHT and getSeverityBadge supporting CRITICAL, HIGH, WARNING, MEDIUM, LOW, CAUTION, INFO.
   - Search filtering checking vehicle_brand.
5. src/types/subsidy.ts:
   - PopularModelEntry.regional_subsidy_samples includes local_subsidy_krw?: number.
6. src/app/subsidy-tracker/SubsidyTrackerClient.tsx:
   - fallbackSummary includes category_totals and disbursed_budget_billion_krw matching schema.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest
from typing import Any


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


def _eval_ts_node(script: str, timeout_sec: int = 30) -> Any:
    """Execute a Node.js snippet using jiti to resolve TypeScript modules in ev-stealth-web."""
    if not shutil.which("node"):
        raise unittest.SkipTest("Node.js runtime not installed on host environment.")

    jiti_path = WEB_ROOT / "node_modules" / "jiti"
    if not jiti_path.exists():
        raise unittest.SkipTest(f"jiti not found at {jiti_path}")

    node_wrapper = f"""
    const jiti = require('{jiti_path}')('{WEB_ROOT}', {{
        interopDefault: true,
        alias: {{
            '@': '{SRC_DIR}',
        }}
    }});
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
        raise RuntimeError(f"Node execution failed (code {proc.returncode}):\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}")
    return json.loads(proc.stdout.strip())


class TestFrontendCycle16Fixes(unittest.TestCase):
    """Systematic test suite verifying all 6 Cycle 16 frontend remediations."""

    def setUp(self) -> None:
        self.recall_lib_path = SRC_DIR / "lib" / "getRecallData.ts"
        self.daily_reports_lib_path = SRC_DIR / "lib" / "getDailyReports.ts"
        self.depreciation_client_path = SRC_DIR / "app" / "depreciation-calculator" / "DepreciationCalculatorClient.tsx"
        self.admin_client_path = SRC_DIR / "app" / "secret-admin-reports" / "AdminDashboardClient.tsx"
        self.subsidy_types_path = SRC_DIR / "types" / "subsidy.ts"
        self.subsidy_client_path = SRC_DIR / "app" / "subsidy-tracker" / "SubsidyTrackerClient.tsx"

        for p in [
            self.recall_lib_path,
            self.daily_reports_lib_path,
            self.depreciation_client_path,
            self.admin_client_path,
            self.subsidy_types_path,
            self.subsidy_client_path,
        ]:
            self.assertTrue(p.exists(), f"Target file does not exist: {p}")

        self.recall_lib_code = self.recall_lib_path.read_text(encoding="utf-8")
        self.daily_reports_lib_code = self.daily_reports_lib_path.read_text(encoding="utf-8")
        self.depreciation_client_code = self.depreciation_client_path.read_text(encoding="utf-8")
        self.admin_client_code = self.admin_client_path.read_text(encoding="utf-8")
        self.subsidy_types_code = self.subsidy_types_path.read_text(encoding="utf-8")
        self.subsidy_client_code = self.subsidy_client_path.read_text(encoding="utf-8")

    # -------------------------------------------------------------------------
    # 1. getModelsForBrand Recall Model Inclusivity
    # -------------------------------------------------------------------------
    def test_get_models_for_brand_source_code_checks(self) -> None:
        """Verify getModelsForBrand includes db.recalls target_model and handles db.vehicles."""
        self.assertIn("db.recalls", self.recall_lib_code)
        self.assertIn("target_model", self.recall_lib_code)
        self.assertIn("vehicles", self.recall_lib_code)

    def test_get_models_for_brand_runtime_inclusivity(self) -> None:
        """Verify getModelsForBrand returns recall models for BMW, Tesla, and BYD via node."""
        script = """
        const recall = jiti('./src/lib/getRecallData.ts');
        const bmwModels = recall.getModelsForBrand('BMW');
        const teslaModels = recall.getModelsForBrand('테슬라');
        const bydModels = recall.getModelsForBrand('BYD');
        const emptyModels = recall.getModelsForBrand('');
        const nullModels = recall.getModelsForBrand(null);

        // Custom database with vehicles array
        const customDb = {
            battery_profiles: [],
            vin_prefixes: [],
            vehicles: [
                { brand: 'CustomEV', model_name: 'CustomModel1' },
                { brand: 'CustomEV', model: 'CustomModel2' }
            ],
            recalls: [
                { brand: 'CustomEV', target_model: 'RecallModelA, RecallModelB (2025)' }
            ]
        };
        const customModels = recall.getModelsForBrand('CustomEV', customDb);

        console.log(JSON.stringify({
            bmwModels,
            teslaModels,
            bydModels,
            emptyModels,
            nullModels,
            customModels,
        }));
        """
        res = _eval_ts_node(script)

        # BMW must include iX and i7 from recall campaigns
        self.assertIn("iX", res["bmwModels"], "BMW models must include 'iX' from recalls")
        self.assertIn("i7", res["bmwModels"], "BMW models must include 'i7' from recalls")

        # Tesla must include 모델 S and 모델 X from recall campaigns
        self.assertIn("모델 S", res["teslaModels"], "Tesla models must include '모델 S' from recalls")
        self.assertIn("모델 X", res["teslaModels"], "Tesla models must include '모델 X' from recalls")

        # BYD must include 아토 3 and 돌핀
        self.assertIn("아토 3", res["bydModels"], "BYD models must include '아토 3'")
        self.assertIn("돌핀", res["bydModels"], "BYD models must include '돌핀'")

        # Edge cases
        self.assertEqual(res["emptyModels"], [], "Empty brand must return []")
        self.assertEqual(res["nullModels"], [], "Null brand must return []")

        # Custom DB with vehicles and recalls
        self.assertIn("CustomModel1", res["customModels"])
        self.assertIn("CustomModel2", res["customModels"])
        self.assertIn("RecallModelA", res["customModels"])
        self.assertIn("RecallModelB", res["customModels"])

    # -------------------------------------------------------------------------
    # 2. Dynamic Holding Period & Export Clawback Subtext in DepreciationCalculatorClient
    # -------------------------------------------------------------------------
    def test_depreciation_dynamic_holding_period_labels(self) -> None:
        """Verify dynamic holding period interpolation in aria announcer and summary card."""
        # Announcer
        self.assertIn("{holdingYears}개년 누적 절감액은", self.depreciation_client_code)
        # Card heading
        self.assertIn("{holdingYears}년 종합 경제성 최종 판정:", self.depreciation_client_code)
        # Card description
        self.assertIn("{holdingYears}개년 누적 운행비 절감액을 합산한", self.depreciation_client_code)

        # Ensure no hardcoded 5년 in those specific callouts
        self.assertNotIn("5개년 누적 절감액은", self.depreciation_client_code)
        self.assertNotIn("5년 종합 경제성 최종 판정:", self.depreciation_client_code)

    def test_depreciation_export_clawback_subtext_breakdown(self) -> None:
        """Verify export clawback subtext formatting showing national and local subsidies."""
        self.assertIn("clawbackResult.nationalClawbackKrw > 0", self.depreciation_client_code)
        self.assertIn("국비: ${clawbackResult.nationalClawbackKrw.toLocaleString()}원, 지방비: ${clawbackResult.localClawbackKrw.toLocaleString()}원", self.depreciation_client_code)
        self.assertIn("지방비: ${clawbackResult.localClawbackKrw.toLocaleString()}원", self.depreciation_client_code)

    # -------------------------------------------------------------------------
    # 3. getDailyReports Severity Tier & Metadata Preservation & Zero Fallback
    # -------------------------------------------------------------------------
    def test_daily_reports_severity_level_and_normalize(self) -> None:
        """Verify getDailyReports maps CRITICAL, HIGH, MEDIUM, LOW properly and preserves created_at."""
        script = """
        const daily = jiti('./src/lib/getDailyReports.ts');

        const testItems = [
            { id: '1', severity: 'CRITICAL', created_at: '2026-10-24T01:00:00Z', author: 'tester1', severity_index: 8.5 },
            { id: '2', severity: 'HIGH', created_at: '2026-10-24T02:00:00Z', author: 'tester2', severity_index: 6.5 },
            { id: '3', severity: 'MEDIUM', created_at: '2026-10-24T03:00:00Z', author: 'tester3', severity_index: 4.5 },
            { id: '4', severity: 'LOW', created_at: '2026-10-24T04:00:00Z', author: 'tester4', severity_index: 2.5 },
            { id: '5', severity: 'WARNING', created_at: '2026-10-24T05:00:00Z' },
            { id: '6', severity: 'CAUTION', created_at: '2026-10-24T06:00:00Z' },
        ];

        const normalized = testItems.map((item, idx) => daily.normalizeReport(item, idx));

        console.log(JSON.stringify({
            severities: normalized.map(n => n.severity),
            createdAts: normalized.map(n => n.created_at),
            authors: normalized.map(n => n.author),
            severityIndices: normalized.map(n => n.severity_index),
        }));
        """
        res = _eval_ts_node(script)
        self.assertEqual(res["severities"], ["CRITICAL", "HIGH", "MEDIUM", "LOW", "WARNING", "CAUTION"])
        self.assertEqual(res["createdAts"][0], "2026-10-24T01:00:00Z")
        self.assertEqual(res["createdAts"][1], "2026-10-24T02:00:00Z")
        self.assertEqual(res["authors"][0], "tester1")
        self.assertEqual(res["severityIndices"][0], 8.5)

    def test_daily_reports_catch_fallback_zero_state(self) -> None:
        """Verify catch fallback in getDailyReports returns 0 count and '해당 없음'."""
        self.assertIn("top_model: '해당 없음 (0건)'", self.daily_reports_lib_code)
        self.assertIn("top_platform: '해당 없음 (0%)'", self.daily_reports_lib_code)
        self.assertIn("total_filtered_defects: 0", self.daily_reports_lib_code)

    # -------------------------------------------------------------------------
    # 4. AdminDashboardClient Severity Weight, Badges, and Brand Search
    # -------------------------------------------------------------------------
    def test_admin_dashboard_severity_weight_and_badges(self) -> None:
        """Verify AdminDashboardClient SEVERITY_WEIGHT has all tiers and getSeverityBadge handles them."""
        # SEVERITY_WEIGHT
        self.assertIn("CRITICAL: 4", self.admin_client_code)
        self.assertIn("HIGH: 3", self.admin_client_code)
        self.assertIn("MEDIUM: 2", self.admin_client_code)
        self.assertIn("LOW: 1", self.admin_client_code)

        # getSeverityBadge
        self.assertIn("sev === 'HIGH'", self.admin_client_code)
        self.assertIn("sev === 'MEDIUM'", self.admin_client_code)
        self.assertIn("sev === 'LOW'", self.admin_client_code)

    def test_admin_dashboard_brand_search_filter(self) -> None:
        """Verify AdminDashboardClient search includes vehicle_brand."""
        self.assertIn("matchBrand", self.admin_client_code)
        self.assertIn("report.vehicle_brand", self.admin_client_code)

    # -------------------------------------------------------------------------
    # 5. PopularModelEntry local_subsidy_krw Field in types/subsidy.ts
    # -------------------------------------------------------------------------
    def test_popular_model_entry_local_subsidy_type(self) -> None:
        """Verify regional_subsidy_samples contains local_subsidy_krw?: number."""
        self.assertIn("local_subsidy_krw?: number;", self.subsidy_types_code)

    # -------------------------------------------------------------------------
    # 6. SubsidyTrackerClient fallbackSummary Schema
    # -------------------------------------------------------------------------
    def test_subsidy_tracker_fallback_summary(self) -> None:
        """Verify SubsidyTrackerClient fallbackSummary matches EVSubsidyDataset schema."""
        self.assertIn("disbursed_budget_billion_krw: 0", self.subsidy_client_code)
        self.assertIn("category_totals: {", self.subsidy_client_code)
        self.assertNotIn("total_disbursed_units", self.subsidy_client_code)


if __name__ == "__main__":
    unittest.main()
