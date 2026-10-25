"""
tests/test_cycle18_frontend_remediation.py - Verification Test Suite for Wave 2
Frontend Component & Library Remediations.

Authoritative Directives:
- DISPATCH.md (sync18_worker_frontend_w2):
  1. getRegionById Korean regional alias mapping (17 divisions) and 2-letter provincial abbreviations.
  2. getModelById whitespace/hyphen query normalization.
  3. RecallPortalClient ?vin= query param parsing, auto-population, and 17-char Mode A lookup.
  4. AdminDashboardClient sr-only table link accessibility (tabIndex, aria-hidden, aria-label).
  5. getDailyReports.ts totalScraped nullish coalescing fix (0 preserves 0).
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from typing import Any, Dict


def _find_repo_root() -> Path:
    candidates = [
        Path(__file__).resolve().parent.parent,
        Path(__file__).resolve().parent.parent.parent,
        Path.cwd(),
        Path.cwd().parent,
    ]
    for p in candidates:
        if (p / "ev-stealth-web").is_dir() and (p / "src").is_dir():
            return p
        if (p / "src" / "lib" / "getSubsidyData.ts").is_file():
            return p.parent
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = _find_repo_root()
WEB_ROOT = PROJECT_ROOT / "ev-stealth-web" if (PROJECT_ROOT / "ev-stealth-web").is_dir() else PROJECT_ROOT
SRC_DIR = WEB_ROOT / "src"
LIB_DIR = SRC_DIR / "lib"
APP_DIR = SRC_DIR / "app"


def _eval_ts_node(script: str, timeout_sec: int = 30) -> Any:
    """Execute a Node.js snippet using tsx in WEB_ROOT to resolve TypeScript modules."""
    if not shutil.which("node"):
        raise unittest.SkipTest("Node.js runtime not installed on host environment.")

    proc = subprocess.run(
        ["npx", "--no-install", "tsx", "-e", script],
        cwd=str(WEB_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"tsx execution failed (exit code {proc.returncode}):\n{proc.stderr}\nStdout: {proc.stdout}")

    out_text = proc.stdout.strip()
    if not out_text:
        return None
    return json.loads(out_text)


class TestCycle18FrontendRemediations(unittest.TestCase):
    """Rigorous end-to-end unit tests verifying the 5 Wave 2 frontend fixes."""

    def test_01_regional_alias_resolution_all_17_divisions(self) -> None:
        """Verifies getRegionById correctly maps all 17 colloquial Korean regional aliases and abbreviations."""
        script = """
        import { getRegionById, calculateNetSubsidy } from './src/lib/getSubsidyData';

        const testCases = [
          { alias: '서울', expectedId: 'KR-11', expectedKo: '서울특별시' },
          { alias: '부산', expectedId: 'KR-26', expectedKo: '부산광역시' },
          { alias: '대구', expectedId: 'KR-27', expectedKo: '대구광역시' },
          { alias: '인천', expectedId: 'KR-28', expectedKo: '인천광역시' },
          { alias: '광주', expectedId: 'KR-29', expectedKo: '광주광역시' },
          { alias: '대전', expectedId: 'KR-30', expectedKo: '대전광역시' },
          { alias: '울산', expectedId: 'KR-31', expectedKo: '울산광역시' },
          { alias: '세종', expectedId: 'KR-36', expectedKo: '세종특별자치시' },
          { alias: '경기', expectedId: 'KR-41', expectedKo: '경기도' },
          { alias: '강원', expectedId: 'KR-42', expectedKo: '강원특별자치도' },
          { alias: '충북', expectedId: 'KR-43', expectedKo: '충청북도' },
          { alias: '충남', expectedId: 'KR-44', expectedKo: '충청남도' },
          { alias: '전북', expectedId: 'KR-45', expectedKo: '전북특별자치도' },
          { alias: '전남', expectedId: 'KR-46', expectedKo: '전라남도' },
          { alias: '경북', expectedId: 'KR-47', expectedKo: '경상북도' },
          { alias: '경남', expectedId: 'KR-48', expectedKo: '경상남도' },
          { alias: '제주', expectedId: 'KR-49', expectedKo: '제주특별자치도' },
          { alias: 'KR-50', expectedId: 'KR-36', expectedKo: '세종특별자치시' },
        ];

        const results = testCases.map(tc => {
          const region = getRegionById(tc.alias);
          return {
            alias: tc.alias,
            found: Boolean(region),
            regionId: region?.region_id,
            nameKo: region?.name_ko,
            expectedId: tc.expectedId,
            expectedKo: tc.expectedKo,
          };
        });

        // Also test calculateNetSubsidy with Busan alias
        const busanCalc = calculateNetSubsidy('ioniq-5-2026', '부산');

        console.log(JSON.stringify({ results, busanCalc: { regionId: busanCalc.regionId, regionName: busanCalc.regionName, localSubsidy: busanCalc.localSubsidyKrw } }));
        """
        data = _eval_ts_node(script)
        for item in data["results"]:
            with self.subTest(alias=item["alias"]):
                self.assertTrue(item["found"], f"getRegionById failed to resolve alias '{item['alias']}'")
                self.assertEqual(item["regionId"], item["expectedId"])
                self.assertEqual(item["nameKo"], item["expectedKo"])

        # Check Busan calculation is NOT Seoul fallback
        self.assertEqual(data["busanCalc"]["regionId"], "KR-26")
        self.assertEqual(data["busanCalc"]["regionName"], "부산광역시")
        self.assertEqual(data["busanCalc"]["localSubsidy"], 2500000)

    def test_02_model_query_normalization(self) -> None:
        """Verifies getModelById strips whitespace and hyphens for unspaced mobile queries."""
        script = """
        import { getModelById } from './src/lib/getSubsidyData';

        const testQueries = [
          { q: '아이오닉5', expectedId: 'ioniq-5-2026' },
          { q: '아이오닉 5', expectedId: 'ioniq-5-2026' },
          { q: 'ioniq5', expectedId: 'ioniq-5-2026' },
          { q: 'model3', expectedId: 'tesla-model-3-rwd' },
          { q: 'modely', expectedId: 'tesla-model-y-rwd' },
          { q: 'ev6', expectedId: 'kia-ev6-2026' },
          { q: 'ev3', expectedId: 'kia-ev3-2026' },
          { q: 'ev9', expectedId: 'kia-ev9-2026' },
          { q: 'torres', expectedId: 'kgm-torres-evx' },
          { q: 'casper', expectedId: 'hyundai-casper-ev' },
        ];

        const results = testQueries.map(tq => {
          const model = getModelById(tq.q);
          return {
            query: tq.q,
            found: Boolean(model),
            modelId: model?.model_id,
            nameKo: model?.name_ko,
            expectedId: tq.expectedId,
          };
        });

        console.log(JSON.stringify(results));
        """
        data = _eval_ts_node(script)
        for item in data:
            with self.subTest(query=item["query"]):
                self.assertTrue(item["found"], f"getModelById failed on query '{item['query']}'")
                self.assertEqual(item["modelId"], item["expectedId"])

    def test_03_daily_reports_zero_total_scraped_preservation(self) -> None:
        """Verifies calculateReportStatistics preserves total_scraped === 0 instead of falling back via falsy ||."""
        script = """
        import { calculateKPIs, calculateReportStatistics } from './src/lib/getDailyReports';

        const mockReports = [
          {
            id: 'mock_1',
            date: '2026-10-25',
            vehicle_model: '아이오닉 5',
            defect_category_ko: '충전',
            defect_category_key: 'charging',
            severity: 'CRITICAL',
            source: 'bobaedream',
            title: 'Mock Test 1',
            summary: 'Mock Summary 1',
            sentiment_score: 0.95,
            url: 'https://example.com/1',
          },
          {
            id: 'mock_2',
            date: '2026-10-25',
            vehicle_model: '아이오닉 5',
            defect_category_ko: '배터리',
            defect_category_key: 'battery',
            severity: 'WARNING',
            source: 'dcinside',
            title: 'Mock Test 2',
            summary: 'Mock Summary 2',
            sentiment_score: 0.85,
            url: 'https://example.com/2',
          }
        ];

        // Case A: explicit 0
        const statsWithZero = calculateKPIs(mockReports, { total_scraped: 0 });

        // Case B: undefined (should fall back to 2 * 7 = 14)
        const statsWithUndefined = calculateKPIs(mockReports, {});

        // Case C: positive number
        const statsWithPositive = calculateKPIs(mockReports, { total_scraped: 50 });

        console.log(JSON.stringify({
          zeroScraped: statsWithZero.total_scraped,
          undefinedScraped: statsWithUndefined.total_scraped,
          positiveScraped: statsWithPositive.total_scraped,
        }));
        """
        data = _eval_ts_node(script)
        self.assertEqual(data["zeroScraped"], 0, "total_scraped === 0 must be preserved via nullish coalescing")
        self.assertEqual(data["undefinedScraped"], 14, "undefined total_scraped should fall back to totalFiltered * 7")
        self.assertEqual(data["positiveScraped"], 50)

    def test_04_recall_portal_vin_query_parameter_wiring(self) -> None:
        """Verifies RecallPortalClient handles ?vin= deep link parameter and invokes Mode A lookup."""
        recall_client_path = APP_DIR / "recall-portal" / "RecallPortalClient.tsx"
        self.assertTrue(recall_client_path.exists())
        src = recall_client_path.read_text(encoding="utf-8")

        # 1. SearchParamsWatcherProps accepts onSelectVin
        self.assertIn("onSelectVin?: (vin: string) => void", src)

        # 2. SearchParamsWatcher checks ?vin= parameter
        self.assertIn("searchParams.get('vin')", src)
        self.assertIn("onSelectVin(vinParam)", src)

        # 3. handleSelectVinFromParams handles 17-char VIN
        self.assertIn("handleSelectVinFromParams", src)
        self.assertIn("cleanVin.length === 17", src)
        self.assertIn("decodeVinAndCheckRecalls(cleanVin, initialDatabase)", src)

        # 4. JSX passes onSelectVin to SearchParamsWatcher
        self.assertIn("onSelectVin={handleSelectVinFromParams}", src)

    def test_05_admin_dashboard_screen_reader_accessibility(self) -> None:
        """Verifies AdminDashboardClient sr-only table links are accessible to assistive tech."""
        admin_client_path = APP_DIR / "secret-admin-reports" / "AdminDashboardClient.tsx"
        self.assertTrue(admin_client_path.exists())
        src = admin_client_path.read_text(encoding="utf-8")

        # In sr-report link, ensure tabIndex={-1} and aria-hidden="true" are removed, and aria-label is present
        # Find sr-report row snippet
        self.assertIn("aria-label=\"게시글 원문 보기\"", src)
        self.assertNotIn("tabIndex={-1} aria-hidden=\"true\" className=\"sr-only\"", src)
        self.assertNotIn("tabIndex={-1}\n                      aria-hidden=\"true\"\n                      className=\"sr-only\"", src)

    def test_06_subsidy_tracker_client_uses_get_region_and_model(self) -> None:
        """Verifies SubsidyTrackerClient activeModel and activeRegionForCalc utilize canonical resolution helpers."""
        subsidy_client_path = APP_DIR / "subsidy-tracker" / "SubsidyTrackerClient.tsx"
        self.assertTrue(subsidy_client_path.exists())
        src = subsidy_client_path.read_text(encoding="utf-8")

        self.assertIn("const resolved = getModelById(q);", src)
        self.assertIn("const resolved = getRegionById(q);", src)


if __name__ == "__main__":
    unittest.main()
