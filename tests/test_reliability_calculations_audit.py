"""
Audit & Hardening Test Suite for Reliability Calculations & Data Loaders:
- ev-stealth-web/src/lib/reliabilityCalculations.ts
- ev-stealth-web/src/lib/getReliabilityData.ts

Validates:
1. Reliability score normalization bounds (0 to 100).
2. Category complaint counts aggregation bugs (e.g., duplicate categories, undefined counts).
3. Trend direction calculation edge cases (division by previous period = 0).
4. Substring model matching edge case with empty IDs or names.
5. High-level Reliability KPI summary aggregation.
"""

import json
import subprocess
import unittest
from pathlib import Path


def _find_project_root() -> Path:
    p = Path(__file__).resolve()
    for parent in [p.parent, p.parent.parent, p.parent.parent.parent]:
        if (parent / "ev-stealth-web" / "src").is_dir():
            return parent
    if (Path.cwd() / "ev-stealth-web").is_dir():
        return Path.cwd()
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = _find_project_root()
WEB_ROOT = PROJECT_ROOT / "ev-stealth-web"


class TestReliabilityCalculationsAudit(unittest.TestCase):
    """Deep unit and boundary test suite for reliability calculations."""

    @classmethod
    def setUpClass(cls):
        cls.calc_path = WEB_ROOT / "src" / "lib" / "reliabilityCalculations.ts"
        cls.data_path = WEB_ROOT / "src" / "lib" / "getReliabilityData.ts"
        if not cls.calc_path.is_file() or not cls.data_path.is_file():
            raise FileNotFoundError("Reliability source files missing")

    def _run_node_ts(self, ts_code: str) -> dict:
        cmd = [
            "node",
            "--no-warnings",
            "--experimental-strip-types",
            "-e",
            ts_code,
        ]
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(proc.stdout)

    def test_01_score_normalization_bounds_and_fallbacks(self):
        """1. Reliability score normalization strictly bounds between 0 and 100."""
        code = """
import * as rel from './ev-stealth-web/src/lib/reliabilityCalculations.ts';
import * as data from './ev-stealth-web/src/lib/getReliabilityData.ts';

const inputs = [
  -100, -0.1, 0, 0.05, 50.45, 99.99, 100, 100.1, 150,
  NaN, Infinity, -Infinity, null, undefined, "invalid", {}
];

const resultsRel = inputs.map(x => rel.normalizeReliabilityScore(x, 42.5));
const resultsData = inputs.map(x => data.normalizeReliabilityScore(x, 42.5));

console.log(JSON.stringify({ resultsRel, resultsData }));
"""
        res = self._run_node_ts(code)
        for target in [res["resultsRel"], res["resultsData"]]:
            # Numerical bounds
            self.assertEqual(target[0], 0)  # -100 -> 0
            self.assertEqual(target[1], 0)  # -0.1 -> 0
            self.assertEqual(target[2], 0)  # 0 -> 0
            self.assertEqual(target[3], 0.1)  # 0.05 -> 0.1
            self.assertEqual(target[4], 50.5)  # 50.45 -> 50.5
            self.assertEqual(target[5], 100)  # 99.99 -> 100
            self.assertEqual(target[6], 100)  # 100 -> 100
            self.assertEqual(target[7], 100)  # 100.1 -> 100
            self.assertEqual(target[8], 100)  # 150 -> 100

            # Fallbacks on non-finite or invalid inputs
            for i in range(9, len(target)):
                self.assertEqual(target[i], 42.5, f"Input index {i} failed safe fallback")

    def test_02_category_complaint_counts_aggregation_dedup_and_undefined(self):
        """2. Category complaint counts aggregation merges duplicates and handles undefined/null."""
        code = """
import * as rel from './ev-stealth-web/src/lib/reliabilityCalculations.ts';

const rawInputs = [
  { category: 'BATTERY_CHARGING', count: 10 },
  { category: 'battery_charging', count: 15 },
  { category: ' Battery_Charging ', count: 5 },
  { category: 'BATTERY_CHARGING', count: undefined },
  { category: 'DRIVING_POWERTRAIN', count: null },
  { category: 'DRIVING_POWERTRAIN', count: 20 },
  { category: 'SOFTWARE_ELECTRONICS', count: -5 },
  null,
  undefined,
];

const agg = rel.aggregateCategoryComplaintCounts(rawInputs);
const list = rel.getAggregatedCategoryList(rawInputs);

// Zero count edge case
const zeroAgg = rel.aggregateCategoryComplaintCounts([
  { category: 'CAT_A', count: 0 },
  { category: 'CAT_B', count: undefined }
]);

console.log(JSON.stringify({ agg, list, zeroAgg }));
"""
        res = self._run_node_ts(code)
        agg = res["agg"]
        # BATTERY_CHARGING merged 10 + 15 + 5 + 0 = 30
        self.assertIn("BATTERY_CHARGING", agg)
        self.assertEqual(agg["BATTERY_CHARGING"]["count"], 30)

        # DRIVING_POWERTRAIN = 0 + 20 = 20
        self.assertIn("DRIVING_POWERTRAIN", agg)
        self.assertEqual(agg["DRIVING_POWERTRAIN"]["count"], 20)

        # SOFTWARE_ELECTRONICS: negative count (-5) clamped to 0
        self.assertIn("SOFTWARE_ELECTRONICS", agg)
        self.assertEqual(agg["SOFTWARE_ELECTRONICS"]["count"], 0)

        # Total is 50, BATTERY is 30/50 = 60%, DRIVING is 20/50 = 40%
        self.assertEqual(agg["BATTERY_CHARGING"]["percentage"], 60.0)
        self.assertEqual(agg["DRIVING_POWERTRAIN"]["percentage"], 40.0)
        self.assertEqual(agg["SOFTWARE_ELECTRONICS"]["percentage"], 0.0)

        # Sorted list check
        list_items = res["list"]
        self.assertEqual(list_items[0]["category"], "BATTERY_CHARGING")
        self.assertEqual(list_items[1]["category"], "DRIVING_POWERTRAIN")

        # Zero total count does not produce NaN%
        zero_agg = res["zeroAgg"]
        self.assertEqual(zero_agg["CAT_A"]["percentage"], 0.0)
        self.assertEqual(zero_agg["CAT_B"]["percentage"], 0.0)

    def test_03_trend_direction_calculation_division_by_zero_edge_cases(self):
        """3. Trend direction handles previous = 0, current = 0, negative values without division by zero."""
        code = """
import * as rel from './ev-stealth-web/src/lib/reliabilityCalculations.ts';

const cases = [
  rel.calculateTrendDirection(10, 0),     // previous = 0, current > 0 -> UP +100%
  rel.calculateTrendDirection(0, 0),      // previous = 0, current = 0 -> STABLE 0%
  rel.calculateTrendDirection(-5, 0),     // previous = 0, current < 0 -> DOWN -100%
  rel.calculateTrendDirection(15, 10),    // +50% -> UP
  rel.calculateTrendDirection(5, 10),     // -50% -> DOWN
  rel.calculateTrendDirection(10.05, 10), // +0.5% (above default 0.1% threshold) -> UP
  rel.calculateTrendDirection(10.005, 10),// +0.05% (below 0.1% threshold) -> STABLE
  rel.calculateTrendDirection(NaN, 10),   // non-finite current -> safe 0 -> DOWN -100%
  rel.calculateTrendDirection(10, NaN),   // non-finite previous -> safe 0 -> UP +100%
];

console.log(JSON.stringify(cases));
"""
        cases = self._run_node_ts(code)

        # 1. previous = 0, current = 10 -> UP, 100%, isIncrease = true
        self.assertEqual(cases[0]["direction"], "UP")
        self.assertEqual(cases[0]["percentageChange"], 100)
        self.assertTrue(cases[0]["isIncrease"])

        # 2. previous = 0, current = 0 -> STABLE, 0%, isStable = true (no NaN)
        self.assertEqual(cases[1]["direction"], "STABLE")
        self.assertEqual(cases[1]["percentageChange"], 0)
        self.assertTrue(cases[1]["isStable"])

        # 3. previous = 0, current = -5 -> DOWN, -100%, isDecrease = true
        self.assertEqual(cases[2]["direction"], "DOWN")
        self.assertEqual(cases[2]["percentageChange"], -100)
        self.assertTrue(cases[2]["isDecrease"])

        # 4. +50%
        self.assertEqual(cases[3]["direction"], "UP")
        self.assertEqual(cases[3]["percentageChange"], 50)

        # 5. -50%
        self.assertEqual(cases[4]["direction"], "DOWN")
        self.assertEqual(cases[4]["percentageChange"], -50)

        # 6. +0.5% > threshold
        self.assertEqual(cases[5]["direction"], "UP")

        # 7. +0.05% <= threshold -> STABLE
        self.assertEqual(cases[6]["direction"], "STABLE")
        self.assertEqual(cases[6]["percentageChange"], 0)

        # 8 & 9. Non-finite inputs
        self.assertEqual(cases[7]["direction"], "DOWN")
        self.assertEqual(cases[8]["direction"], "UP")

    def test_04_model_lookup_empty_id_substring_bug_fixed(self):
        """4. getModelReliabilityById does not falsely match models with empty id or name."""
        code = """
import * as rel from './ev-stealth-web/src/lib/reliabilityCalculations.ts';

const mockDb = {
  metadata: { version: '1.0' },
  repair_cost_matrix: [],
  brands: [{
    id: 'test_brand',
    name_ko: '테스트',
    name_en: 'Test',
    country: 'KR',
    overall_dsi: 50,
    total_reports: 10,
    critical_issue_rate: 10,
    category_distribution: {},
    models: [
      { id: '', name: '', segment: 'SUV', brand_id: 'test_brand', overall_grade: 'A', avg_dsi: 50, top_category: 'BATTERY_CHARGING', year_evaluations: [] },
      { id: 'valid_model', name: 'Valid Model', segment: 'Sedan', brand_id: 'test_brand', overall_grade: 'A', avg_dsi: 50, top_category: 'BATTERY_CHARGING', year_evaluations: [] }
    ]
  }]
};

const lookupNonExistent = rel.getModelReliabilityById('arbitrary_query', mockDb);
const lookupValid = rel.getModelReliabilityById('valid_model', mockDb);

console.log(JSON.stringify({
  lookupNonExistent: lookupNonExistent ? lookupNonExistent.id : null,
  lookupValid: lookupValid ? lookupValid.id : null
}));
"""
        res = self._run_node_ts(code)
        self.assertIsNone(res["lookupNonExistent"], "Empty ID model falsely matched arbitrary query")
        self.assertEqual(res["lookupValid"], "valid_model")

    def test_05_calculate_reliability_kpis(self):
        """5. calculateReliabilityKPIs computes bounded KPIs from master trends data."""
        code = """
import * as rel from './ev-stealth-web/src/lib/reliabilityCalculations.ts';
import * as data from './ev-stealth-web/src/lib/getReliabilityData.ts';

const db = data.getReliabilityTrendsData();
const kpis = rel.calculateReliabilityKPIs(db);

console.log(JSON.stringify(kpis));
"""
        kpis = self._run_node_ts(code)
        self.assertGreaterEqual(kpis["totalAnalyzedPosts"], 1000)
        self.assertGreaterEqual(kpis["trackedBrandsCount"], 9)
        self.assertGreaterEqual(kpis["trackedModelsCount"], 20)
        self.assertGreater(kpis["industryAvgDsi"], 0)
        self.assertLessEqual(kpis["industryAvgDsi"], 100)
        self.assertTrue(bool(kpis["topDefectCategory"]))


if __name__ == "__main__":
    unittest.main()
