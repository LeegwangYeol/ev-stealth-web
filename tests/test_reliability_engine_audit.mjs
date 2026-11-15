import assert from 'node:assert/strict';
import {
  normalizeReliabilityScore,
  aggregateCategoryComplaintCounts,
  getAggregatedCategoryList,
  calculateTrendDirection,
  calculateReliabilityKPIs,
  getAllEnrichedModels,
  getVerdictBadgeInfo,
  getDsiSeverityLevel,
  getGradeBadgeStyle,
  getModelReliabilityById,
  getDefectsForModel,
  getBrandReliabilityById,
  DEFAULT_CATEGORY_SEVERITY_WEIGHTS,
  DEFAULT_STEALTH_SCORE_WEIGHTS,
  calculateReliabilityConfidence,
  normalizeDefectFrequency,
  calculateWeightedDefectFrequency,
  deriveGradeFromStealthScore,
  deriveVerdictFromStealthScore,
  calculateStealthScore,
  getModelYearEvaluation,
  resolveBrandReliability,
  getSafeDefaultBrandReliability,
  getBrandWithFallback,
  getSafeDefaultModelReliability,
  aggregateQuarterlyDefectBreakdown,
  aggregateMonthlyDefectBreakdown,
  calculateModelYearDefectTrajectory,
  aggregateDefectTrendsByPeriod,
} from '../src/lib/reliabilityCalculations.ts';

import {
  getReliabilityTrendsData,
  calculateReliabilityKPIs as calculateKPIsFromData,
  getModelReliabilityById as getModelFromData,
  getBrandReliabilityById as getBrandFromData,
  calculateStealthScore as calculateScoreFromData,
} from '../src/lib/getReliabilityData.ts';

console.log('--- STARTING RELIABILITY ANALYTICS ENGINE AUDIT TESTS ---');

// ==========================================
// 1. RELIABILITY SCORE NORMALIZATION & MATH
// ==========================================
console.log('Test 1: normalizeReliabilityScore');
assert.equal(normalizeReliabilityScore(75.46), 75.5);
assert.equal(normalizeReliabilityScore('85.2'), 85.2, 'Numeric string parsed correctly');
assert.equal(normalizeReliabilityScore(-15), 0, 'Negative numbers clamped to 0');
assert.equal(normalizeReliabilityScore(150), 100, 'Values > 100 clamped to 100');
assert.equal(normalizeReliabilityScore(NaN, 50), 50, 'NaN falls back to fallback');
assert.equal(normalizeReliabilityScore(null, 42), 42, 'null falls back');
assert.equal(normalizeReliabilityScore(undefined, 0), 0, 'undefined falls back');
assert.equal(Object.is(normalizeReliabilityScore(-0.01), 0), true, 'No -0 negative zero');

// ==========================================
// 2. TREND CALCULATION & DIVISION BY ZERO
// ==========================================
console.log('Test 2: calculateTrendDirection');
const t1 = calculateTrendDirection(10, 0);
assert.equal(t1.direction, 'UP');
assert.equal(t1.percentageChange, 100);
assert.equal(t1.formattedChange, '+100.0%');

const t2 = calculateTrendDirection(0, 0);
assert.equal(t2.direction, 'STABLE');
assert.equal(t2.percentageChange, 0);

const t3 = calculateTrendDirection(-5, 0);
assert.equal(t3.direction, 'DOWN');
assert.equal(t3.percentageChange, -100);

const t4 = calculateTrendDirection(100.05, 100);
assert.equal(t4.direction, 'STABLE', 'Fluctuation within threshold is STABLE');

const t5 = calculateTrendDirection(150, 100);
assert.equal(t5.direction, 'UP');
assert.equal(t5.percentageChange, 50);

const t6 = calculateTrendDirection(50, 100);
assert.equal(t6.direction, 'DOWN');
assert.equal(t6.percentageChange, -50);

// ==========================================
// 3. STATISTICAL CONFIDENCE MATH & YEARS FACTOR
// ==========================================
console.log('Test 3: calculateReliabilityConfidence');
assert.equal(calculateReliabilityConfidence(0), 0.0, '0 complaints = 0.0 confidence');
assert.equal(calculateReliabilityConfidence(-5), 0.0, 'Negative complaints = 0.0');
assert.equal(calculateReliabilityConfidence(NaN), 0.0, 'NaN complaints = 0.0');
assert.equal(calculateReliabilityConfidence(50, 3), 1.0, '50 complaints at 3 yrs = 1.0');
assert.equal(calculateReliabilityConfidence(50, 1), 0.70, '1 yr coverage factor = 0.70');
assert.equal(calculateReliabilityConfidence(50, 2), 0.85, '2 yrs coverage factor = 0.85');
assert.equal(calculateReliabilityConfidence(50, '2'), 0.85, 'String year "2" parsed');
assert.equal(calculateReliabilityConfidence(50, 0), 0.0, '0 yrs tracking = 0.0 confidence');

// ==========================================
// 4. DEFECT FREQUENCY & WEIGHTED CALCULATIONS
// ==========================================
console.log('Test 4: normalizeDefectFrequency & calculateWeightedDefectFrequency');
assert.equal(normalizeDefectFrequency(0, 10000), 0.0, '0 complaints gives 0.0');
assert.equal(normalizeDefectFrequency(10, 0), 0.0, '0 fleet volume prevents div by zero');
assert.equal(normalizeDefectFrequency(50, 10000, 1000), 5.0, '50 / 10000 * 1000 = 5.0');
assert.equal(normalizeDefectFrequency('50', '10000', 1000), 5.0, 'String volume and complaints parsed');

// Weighted frequency with case-insensitive custom weights
const weighted1 = calculateWeightedDefectFrequency(
  [
    { category: 'battery_charging', count: 10 },
    { category: 'build_quality', count: 10 },
  ],
  10000,
  { battery_charging: 3.0 } // custom weight in lowercase
);
// Total weighted: 10 * 3.0 + 10 * 0.7 = 37. per 10,000 * 1000 = 3.7
assert.equal(weighted1, 3.7, 'Case-insensitive custom weight used correctly');

// Empty complaints
assert.equal(calculateWeightedDefectFrequency([], 10000), 0.0);

// ==========================================
// 5. STEALTH SCORE COMPOSITE & GRADING
// ==========================================
console.log('Test 5: calculateStealthScore & deriveGradeFromStealthScore');
// Grade thresholds: 90 A+, 80 A, 68 B, 50 C, 35 D, <35 F
assert.equal(deriveGradeFromStealthScore(95), 'A+');
assert.equal(deriveGradeFromStealthScore(82), 'A');
assert.equal(deriveGradeFromStealthScore(70), 'B');
assert.equal(deriveGradeFromStealthScore(50.0), 'C', 'Neutral baseline 50.0 gets Grade C');
assert.equal(deriveGradeFromStealthScore(36.0), 'D', '36.0 gets Grade D');
assert.equal(deriveGradeFromStealthScore(20), 'F');

// 0-complaint model evaluation:
const zeroComplaintScore = calculateStealthScore({
  dsi: 0,
  incidentRate: 0,
  criticalIssueRate: 0,
  totalComplaints: 0,
});
assert.equal(zeroComplaintScore.confidenceScore, 0.0, '0 complaints has 0% confidence');
assert.equal(zeroComplaintScore.recommendedVerdict, 'CAUTION', 'Low confidence defaults to CAUTION');
assert.equal(zeroComplaintScore.stealthScore, 50.0, 'Anchored to neutral 50.0 baseline');
assert.equal(zeroComplaintScore.overallGrade, 'C', 'Neutral 50.0 baseline receives Grade C');

// Untested car with custom volume input:
const volumeScore = calculateStealthScore({
  dsi: 40,
  incidentRate: 15,
  criticalIssueRate: 5,
  totalComplaints: 20,
  fleetOrSalesVolume: 50000,
  baselineScale: 1000,
});
assert.equal(volumeScore.normalizedDefectFrequency, 0.4, '20 / 50000 * 1000 = 0.4');

// ==========================================
// 6. SINGLE-BRAND DATASET & MISSING METRICS KPIS
// ==========================================
console.log('Test 6: calculateReliabilityKPIs with single-brand & missing metrics');
const singleBrandDb = {
  metadata: {
    version: '1.0.0',
    // total_records_analyzed and avg_industry_dsi omitted!
  },
  repair_cost_matrix: [],
  brands: [
    {
      id: 'hyundai',
      name_ko: '현대',
      name_en: 'Hyundai',
      country: 'KR',
      overall_dsi: 58.2,
      total_reports: 268,
      critical_issue_rate: 22.4,
      category_distribution: {
        BATTERY_CHARGING: { count: 110, percentage: 41.0 },
        DRIVING_POWERTRAIN: { count: 158, percentage: 59.0 },
      },
      models: [
        { id: 'ioniq5', name: '아이오닉 5', segment: 'CUV', brand_id: 'hyundai', overall_grade: 'C', avg_dsi: 51.4, year_evaluations: [], top_category: 'DRIVING_POWERTRAIN' },
        { id: 'ioniq6', name: '아이오닉 6', segment: '세단', brand_id: 'hyundai', overall_grade: 'B', avg_dsi: 39.8, year_evaluations: [], top_category: 'DRIVING_POWERTRAIN' },
      ],
    },
  ],
};

const kpis = calculateReliabilityKPIs(singleBrandDb);
assert.equal(kpis.trackedBrandsCount, 1, '1 tracked brand');
assert.equal(kpis.trackedModelsCount, 2, '2 tracked models');
assert.equal(kpis.totalAnalyzedPosts, 268, 'Dynamically summed reports when meta is missing');
assert.equal(kpis.industryAvgDsi, 58.2, 'Dynamic single-brand average DSI matches brand DSI');
assert.equal(kpis.topDefectCategory, 'DRIVING_POWERTRAIN', 'Top category correctly identified');

// 0-complaint empty DB
const emptyKpis = calculateReliabilityKPIs(null);
assert.equal(emptyKpis.trackedBrandsCount, 0);
assert.equal(emptyKpis.totalAnalyzedPosts, 0);
assert.equal(emptyKpis.industryAvgDsi, 0);
assert.equal(emptyKpis.topDefectCategory, 'NONE', 'Empty DB has NONE for top category');

// ==========================================
// 7. MODEL RELIABILITY ID RESOLUTION
// ==========================================
console.log('Test 7: getModelReliabilityById priority');
const modelsTestDb = {
  metadata: { version: '1.0' },
  repair_cost_matrix: [],
  brands: [
    {
      id: 'kia',
      name_ko: '기아',
      name_en: 'Kia',
      country: 'KR',
      overall_dsi: 50,
      total_reports: 10,
      critical_issue_rate: 10,
      category_distribution: {},
      models: [
        { id: 'ev', name: 'EV', segment: '준중형', brand_id: 'kia', overall_grade: 'B', avg_dsi: 40, year_evaluations: [], top_category: 'BATTERY_CHARGING' },
        { id: 'ev6', name: 'EV6', segment: '중형 CUV', brand_id: 'kia', overall_grade: 'C', avg_dsi: 55, year_evaluations: [], top_category: 'DRIVING_POWERTRAIN' },
      ],
    },
  ],
};

const ev6Match = getModelReliabilityById('ev6', modelsTestDb);
assert.equal(ev6Match?.id, 'ev6', 'Exact ID ev6 preferred over partial ev');

const evMatch = getModelReliabilityById('ev', modelsTestDb);
assert.equal(evMatch?.id, 'ev', 'Exact ID ev matched');

// ==========================================
// 8. QUARTERLY DEFECT BREAKDOWN ALGORITHM
// ==========================================
console.log('Test 8: aggregateQuarterlyDefectBreakdown');
const sampleQuarterlyInputs = [
  { date: '2024-01-15', category: 'BATTERY_CHARGING', count: 12, dsiScore: 80 },
  { date: '2024-03-20', category: 'DRIVING_POWERTRAIN', count: 8, dsiScore: 60 },
  { date: '2024-04-10', category: 'BATTERY_CHARGING', count: 15, dsiScore: 70 }, // Q2
  { date: '2024-06-25', category: 'SOFTWARE_ELECTRONICS', count: 5, dsiScore: 40 }, // Q2
  { date: '2024-07-02', category: 'BATTERY_CHARGING', count: 30, dsiScore: 85 }, // Q3
  { date: '2024-11-18', category: 'COLD_WEATHER', count: 10, dsiScore: 65 }, // Q4
];

const quarters = aggregateQuarterlyDefectBreakdown(sampleQuarterlyInputs);
assert.equal(quarters.length, 4, '4 quarters generated');
assert.equal(quarters[0].periodKey, '2024-Q1');
assert.equal(quarters[0].totalComplaints, 20); // 12 + 8
assert.equal(quarters[0].topCategory, 'BATTERY_CHARGING');
assert.equal(quarters[0].trendFromPrevious.direction, 'STABLE', 'First quarter has STABLE trend');

assert.equal(quarters[1].periodKey, '2024-Q2');
assert.equal(quarters[1].totalComplaints, 20); // 15 + 5
assert.equal(quarters[1].trendFromPrevious.direction, 'STABLE', 'Q2 has 0% change from Q1');

assert.equal(quarters[2].periodKey, '2024-Q3');
assert.equal(quarters[2].totalComplaints, 30);
assert.equal(quarters[2].trendFromPrevious.direction, 'UP');
assert.equal(quarters[2].trendFromPrevious.percentageChange, 50, '+50% from Q2');

assert.equal(quarters[3].periodKey, '2024-Q4');
assert.equal(quarters[3].totalComplaints, 10);
assert.equal(quarters[3].trendFromPrevious.direction, 'DOWN');
assert.equal(quarters[3].trendFromPrevious.percentageChange, -66.7, 'Downtrend in Q4');

// Moving averages check
// Q1: 20
// Q2: (20 + 20) / 2 = 20
// Q3: (20 + 20 + 30) / 3 = 23.3
// Q4: (20 + 30 + 10) / 3 = 20.0
assert.equal(quarters[2].movingAverage3Q, 23.3);
assert.equal(quarters[3].movingAverage3Q, 20.0);

// ==========================================
// 9. MONTHLY DEFECT BREAKDOWN ALGORITHM
// ==========================================
console.log('Test 9: aggregateMonthlyDefectBreakdown');
const sampleMonthlyInputs = [
  { year: 2024, month: 1, category: 'BATTERY_CHARGING', count: 5 },
  { year: 2024, month: 2, category: 'BATTERY_CHARGING', count: 10 },
  { year: 2024, month: 3, category: 'DRIVING_POWERTRAIN', count: 20 },
];
const months = aggregateMonthlyDefectBreakdown(sampleMonthlyInputs);
assert.equal(months.length, 3);
assert.equal(months[0].periodKey, '2024-01');
assert.equal(months[0].monthLabel, '2024년 1월');
assert.equal(months[1].trendFromPrevious.direction, 'UP');
assert.equal(months[1].trendFromPrevious.percentageChange, 100);
assert.equal(months[2].movingAverage3M, 11.7, '(5 + 10 + 20) / 3 = 11.7');

// ==========================================
// 10. MODEL YEAR TRAJECTORY ALGORITHM
// ==========================================
console.log('Test 10: calculateModelYearDefectTrajectory');
const ioniq5Evals = [
  { year: 2021, verdict: 'AVOID', dsi_score: 88, incident_rate: 42.5, primary_defect: 'ICCU 폭파', estimated_repair_cost: '600만', chronic_symptoms: ['ICCU 파손', '12V 방전'], raw_quote: '' },
  { year: 2022, verdict: 'CAUTION', dsi_score: 74, incident_rate: 31.0, primary_defect: 'ICCU 과열', estimated_repair_cost: '500만', chronic_symptoms: ['ICCU 파손', '완속 과열'], raw_quote: '' },
  { year: 2023, verdict: 'CAUTION', dsi_score: 55, incident_rate: 18.5, primary_defect: '방전 개선', estimated_repair_cost: '300만', chronic_symptoms: ['12V 방전'], raw_quote: '' },
  { year: 2024, verdict: 'BUY_SAFE', dsi_score: 28, incident_rate: 7.2, primary_defect: '안정화', estimated_repair_cost: '100만', chronic_symptoms: [], raw_quote: '' },
  { year: 2025, verdict: 'BUY_SAFE', dsi_score: 18, incident_rate: 4.1, primary_defect: '신형 배터리', estimated_repair_cost: '80만', chronic_symptoms: [], raw_quote: '' },
];

const trajectory = calculateModelYearDefectTrajectory(ioniq5Evals, { id: 'ioniq5', name: '아이오닉 5' });
assert.equal(trajectory.initialDsi, 88);
assert.equal(trajectory.latestDsi, 18);
assert.equal(trajectory.peakRiskYear, 2021);
assert.equal(trajectory.safestYear, 2025);
assert.equal(trajectory.trajectoryVerdict, 'RAPIDLY_IMPROVING', '88 -> 18 DSI drop classified as RAPIDLY_IMPROVING');
assert.ok(trajectory.chronicCategories.includes('ICCU 파손'), 'Recurring ICCU symptom caught as chronic');
assert.ok(trajectory.chronicCategories.includes('12V 방전'), 'Recurring 12V symptom caught as chronic');
assert.equal(trajectory.yearOverYearProgression.length, 5);
assert.equal(trajectory.yearOverYearProgression[4].trendFromPreviousYear.direction, 'DOWN');

// Empty evaluations trajectory
const emptyTraj = calculateModelYearDefectTrajectory([]);
assert.equal(emptyTraj.trajectoryVerdict, 'STABLE');
assert.equal(emptyTraj.trackedYears.length, 0);

// ==========================================
// 11. MASTER DATA VERIFICATION
// ==========================================
console.log('Test 11: Master Data Verification');
const masterData = getReliabilityTrendsData();
assert.ok(masterData.brands.length >= 9, 'At least 9 brands loaded');
const masterKpis = calculateKPIsFromData();
assert.ok(masterKpis.totalAnalyzedPosts >= 1000, 'Over 1000 posts analyzed');
assert.ok(masterKpis.trackedModelsCount >= 20, 'Over 20 models analyzed');

const modelFromData = getModelFromData('ioniq5');
assert.ok(modelFromData, '아이오닉 5 loaded from master database');
assert.equal(modelFromData?.brand_name_ko, '현대자동차');

const brandFromData = getBrandFromData('tesla');
assert.ok(brandFromData, 'Tesla loaded from master database');

console.log('--- ALL 11 AUDIT SUITES PASSED FLAWLESSLY! ---');
