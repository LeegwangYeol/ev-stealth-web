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

    def test_06_stealth_score_weighting_and_smoothing(self):
        """6. Stealth score weighting formula computes weighted defect penalties and smoothing."""
        code = """
import * as rel from './ev-stealth-web/src/lib/reliabilityCalculations.ts';
import * as data from './ev-stealth-web/src/lib/getReliabilityData.ts';

// Model A: Excellent reliability, high sample
const modelA = rel.calculateStealthScore({
  dsi: 20,
  incidentRate: 10,
  criticalIssueRate: 5,
  totalComplaints: 100,
  yearsEvaluated: 3,
  baselineIndustryDsi: 64.2
});

// Model B: Severe defects, high sample
const modelB = rel.calculateStealthScore({
  dsi: 90,
  incidentRate: 45,
  criticalIssueRate: 50,
  totalComplaints: 80,
  yearsEvaluated: 3,
  baselineIndustryDsi: 64.2
});

// Model C: Custom weights
const modelC = rel.calculateStealthScore({
  dsi: 40,
  incidentRate: 20,
  criticalIssueRate: 10,
  totalComplaints: 60,
  yearsEvaluated: 3,
  weights: { dsiWeight: 0.70, incidentWeight: 0.20, criticalWeight: 0.10 }
});

// Model D: Invalid/negative weights fallback
const modelD = rel.calculateStealthScore({
  dsi: 50,
  weights: { dsiWeight: -1, incidentWeight: 0, criticalWeight: 0 }
});

console.log(JSON.stringify({ modelA, modelB, modelC, modelD }));
"""
        res = self._run_node_ts(code)
        mA = res["modelA"]
        # defectPenalty = 0.5*20 + 0.3*10 + 0.2*5 = 10 + 3 + 1 = 14
        self.assertEqual(mA["defectPenalty"], 14.0)
        self.assertEqual(mA["rawStealthScore"], 86.0)
        self.assertEqual(mA["stealthScore"], 86.0)
        self.assertEqual(mA["confidenceScore"], 1.0)
        self.assertEqual(mA["recommendedVerdict"], "BUY_SAFE")
        self.assertEqual(mA["overallGrade"], "A")
        self.assertTrue(mA["isHighConfidence"])

        mB = res["modelB"]
        # defectPenalty = 0.5*90 + 0.3*45 + 0.2*50 = 45 + 13.5 + 10 = 68.5
        self.assertEqual(mB["defectPenalty"], 68.5)
        self.assertEqual(mB["rawStealthScore"], 31.5)
        self.assertEqual(mB["stealthScore"], 31.5)
        self.assertEqual(mB["recommendedVerdict"], "AVOID")
        self.assertEqual(mB["overallGrade"], "F")

        mC = res["modelC"]
        # custom: 0.70*40 + 0.20*20 + 0.10*10 = 28 + 4 + 1 = 33
        self.assertEqual(mC["defectPenalty"], 33.0)
        self.assertEqual(mC["rawStealthScore"], 67.0)

        mD = res["modelD"]
        # invalid weights fall back to default weights without NaN
        self.assertEqual(mD["defectPenalty"], 25.0)
        self.assertEqual(mD["rawStealthScore"], 75.0)

    def test_07_defect_frequency_normalizers(self):
        """7. Defect frequency normalizers handle zero complaints, zero volume, and category weighting."""
        code = """
import * as rel from './ev-stealth-web/src/lib/reliabilityCalculations.ts';

const cases = [
  rel.normalizeDefectFrequency(0, 1000),      // 0 complaints -> 0.0
  rel.normalizeDefectFrequency(10, 0),         // 0 volume -> 0.0 (prevents division by zero)
  rel.normalizeDefectFrequency(10, -500),      // negative volume -> 0.0
  rel.normalizeDefectFrequency(-5, 1000),      // negative complaints -> 0.0
  rel.normalizeDefectFrequency(NaN, 1000),     // non-finite complaints -> 0.0
  rel.normalizeDefectFrequency(25, 5000, 1000),// 25 / 5000 * 1000 = 5.0
];

const catInputs = [
  { category: 'BATTERY_CHARGING', count: 10 },  // weight 2.5 -> 25
  { category: 'BUILD_QUALITY', count: 10 },     // weight 0.7 -> 7
];

const weightedWithVolume = rel.calculateWeightedDefectFrequency(catInputs, 1000); // (25 + 7) / 1000 * 1000 = 32.0
const weightedAvgMult = rel.calculateWeightedDefectFrequency(catInputs);          // (25 + 7) / 20 = 1.6
const weightedZero = rel.calculateWeightedDefectFrequency([]);                    // 0.0

console.log(JSON.stringify({ cases, weightedWithVolume, weightedAvgMult, weightedZero }));
"""
        res = self._run_node_ts(code)
        cases = res["cases"]
        self.assertEqual(cases[0], 0.0)
        self.assertEqual(cases[1], 0.0)
        self.assertEqual(cases[2], 0.0)
        self.assertEqual(cases[3], 0.0)
        self.assertEqual(cases[4], 0.0)
        self.assertEqual(cases[5], 5.0)

        self.assertEqual(res["weightedWithVolume"], 32.0)
        self.assertEqual(res["weightedAvgMult"], 1.6)
        self.assertEqual(res["weightedZero"], 0.0)

    def test_08_reliability_confidence_algorithm(self):
        """8. calculateReliabilityConfidence produces strictly bounded statistical confidence [0, 1]."""
        code = """
import * as rel from './ev-stealth-web/src/lib/reliabilityCalculations.ts';

const confs = [
  rel.calculateReliabilityConfidence(0),          // 0 complaints -> 0.0
  rel.calculateReliabilityConfidence(-10),        // negative -> 0.0
  rel.calculateReliabilityConfidence(NaN),        // NaN -> 0.0
  rel.calculateReliabilityConfidence(null),       // null -> 0.0
  rel.calculateReliabilityConfidence(50, 3),      // threshold met (50) & 3+ yrs -> 1.0
  rel.calculateReliabilityConfidence(100, 5),     // high sample -> 1.0
  rel.calculateReliabilityConfidence(10, 1),      // 10 complaints, 1 yr -> ~0.4273
  rel.calculateReliabilityConfidence(50, 0),      // 0 years -> 0.0
];

console.log(JSON.stringify(confs));
"""
        confs = self._run_node_ts(code)
        self.assertEqual(confs[0], 0.0)
        self.assertEqual(confs[1], 0.0)
        self.assertEqual(confs[2], 0.0)
        self.assertEqual(confs[3], 0.0)
        self.assertEqual(confs[4], 1.0)
        self.assertEqual(confs[5], 1.0)
        self.assertGreater(confs[6], 0.3)
        self.assertLess(confs[6], 0.6)
        self.assertEqual(confs[7], 0.0)

    def test_09_boundary_conditions_zero_complaints_unknown_brand_missing_year(self):
        """9. Boundary conditions: 0 complaints anchors to baseline, unknown brand & missing year return safe fallbacks."""
        code = """
import * as rel from './ev-stealth-web/src/lib/reliabilityCalculations.ts';
import * as data from './ev-stealth-web/src/lib/getReliabilityData.ts';

const db = data.getReliabilityTrendsData();

// 1. Zero complaints model: confidence = 0.0, smoothed score anchors safely to industry baseline
const zeroComplaintsScore = rel.calculateStealthScore({
  dsi: 10,
  incidentRate: 0,
  criticalIssueRate: 0,
  totalComplaints: 0,
  baselineIndustryDsi: 64.2
});

// 2. Unknown brand lookup
const unknownBrandA = rel.getBrandReliabilityById('nonexistent_brand_xyz', db);
const unknownBrandB = rel.resolveBrandReliability('unknown_car_maker', db);
const brandWithFallback = rel.getBrandWithFallback('nonexistent_brand_xyz', undefined, db);

// 3. Missing year data
const missingYearEval = rel.getModelYearEvaluation('ioniq5', 1980, db); // Year 1980 does not exist
const validYearEval = rel.getModelYearEvaluation('ioniq5', 2021, db);   // Year 2021 exists
const unknownModelEval = rel.getModelYearEvaluation('ghost_model', 2023, db);
const missingDefects = rel.getDefectsForModel('ghost_model', db);

console.log(JSON.stringify({
  zeroComplaintsScore,
  unknownBrandA: unknownBrandA || null,
  unknownBrandB: unknownBrandB || null,
  brandWithFallbackId: brandWithFallback.id,
  brandWithFallbackDsi: brandWithFallback.overall_dsi,
  missingYearEval: missingYearEval || null,
  validYearEvalExists: Boolean(validYearEval),
  validYearEvalDsi: validYearEval ? validYearEval.dsi_score : null,
  unknownModelEval: unknownModelEval || null,
  missingDefectsLength: missingDefects.length
}));
"""
        res = self._run_node_ts(code)
        zScore = res["zeroComplaintsScore"]
        # Raw is 95, but confidence is 0.0, so smoothed score is 35.8 (100 - 64.2)
        self.assertEqual(zScore["confidenceScore"], 0.0)
        self.assertEqual(zScore["rawStealthScore"], 95.0)
        self.assertEqual(zScore["stealthScore"], 35.8)
        self.assertEqual(zScore["recommendedVerdict"], "CAUTION")
        self.assertFalse(zScore["isHighConfidence"])

        # Unknown brand safely returns undefined or fallback
        self.assertIsNone(res["unknownBrandA"])
        self.assertIsNone(res["unknownBrandB"])
        self.assertEqual(res["brandWithFallbackId"], "nonexistent_brand_xyz")
        self.assertEqual(res["brandWithFallbackDsi"], 50.0)

        # Missing year data
        self.assertIsNone(res["missingYearEval"])
        self.assertTrue(res["validYearEvalExists"])
        self.assertEqual(res["validYearEvalDsi"], 88.0)
        self.assertIsNone(res["unknownModelEval"])
        self.assertEqual(res["missingDefectsLength"], 0)

    def test_10_safe_default_fallbacks(self):
        """10. Safe default fallback builders return fully-formed non-throwing domain objects."""
        code = """
import * as rel from './ev-stealth-web/src/lib/reliabilityCalculations.ts';

const brand = rel.getSafeDefaultBrandReliability('lucid');
const model = rel.getSafeDefaultModelReliability('gravity', 'lucid');

console.log(JSON.stringify({ brand, model }));
"""
        res = self._run_node_ts(code)
        brand = res["brand"]
        self.assertEqual(brand["id"], "lucid")
        self.assertEqual(brand["total_reports"], 0)
        self.assertEqual(brand["overall_dsi"], 50.0)
        self.assertEqual(brand["models"], [])
        self.assertIn("BATTERY_CHARGING", brand["category_distribution"])

        model = res["model"]
        self.assertEqual(model["id"], "gravity")
        self.assertEqual(model["brand_id"], "lucid")
        self.assertEqual(model["overall_grade"], "C")
        self.assertEqual(model["year_evaluations"], [])


if __name__ == "__main__":
    unittest.main()
