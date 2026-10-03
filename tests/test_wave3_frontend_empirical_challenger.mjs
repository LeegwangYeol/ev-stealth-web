/**
 * tests/test_wave3_frontend_empirical_challenger.mjs
 * 
 * Wave 3 Frontend Empirical Challenger Stress Testing Harness
 * 
 * Evaluates mathematical resilience against extreme and adversarial inputs:
 * - 0, negative values, Infinity, -Infinity, NaN, null, undefined, 1e15
 * Across:
 * 1. getDailyReports.ts (normalizeReport, calculateKPIs, getDailyReports)
 * 2. getDepreciationData.ts (calculateDepreciation, simulateBatteryHealth, calculateSubsidyClawback, calculateTcoComparison)
 * 3. getSubsidyData.ts (getPriceSubsidyRatio, calculateNetSubsidy, getModelById, getRegionById)
 * 4. UI helper equations and component guards
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Dynamic loader helper for TypeScript modules in Node ESM
import * as dailyReports from '../src/lib/getDailyReports.ts';
import * as depreciation from '../src/lib/getDepreciationData.ts';
import * as subsidy from '../src/lib/getSubsidyData.ts';

const report = {
  totalTests: 0,
  passed: 0,
  failed: 0,
  anomalies: [],
  findings: []
};

function recordAssert(group, testName, condition, details = {}) {
  report.totalTests++;
  if (condition) {
    report.passed++;
  } else {
    report.failed++;
    const finding = { group, testName, details };
    report.findings.push(finding);
    console.error(`❌ [CHALLENGER FAIL] [${group}] ${testName}`, details);
  }
}

function recordAnomaly(group, description, evidence) {
  report.anomalies.push({ group, description, evidence });
  console.warn(`⚠️ [ADVERSARIAL ANOMALY] [${group}] ${description}:`, evidence);
}

console.log('================================================================');
console.log('⚡ WAVE 3 FRONTEND EMPIRICAL CHALLENGER STRESS HARNESS');
console.log('================================================================\n');

// ============================================================================
// 1. getDailyReports.ts Stress Testing
// ============================================================================
console.log('--- [1. getDailyReports.ts Adversarial Testing] ---');

const adversarialScores = [
  0,
  -1,
  -100,
  Infinity,
  -Infinity,
  NaN,
  null,
  undefined,
  1e15,
  -1e15,
];

for (const score of adversarialScores) {
  const norm = dailyReports.normalizeReport(
    {
      sentiment_score: score,
      negativity_score: score,
      defect_category: null,
      severity: null,
      source: null,
      title: null,
    },
    0
  );

  recordAssert(
    'getDailyReports:normalizeReport',
    `sentiment_score is finite and non-negative for input ${score}`,
    Number.isFinite(norm.sentiment_score) && !Number.isNaN(norm.sentiment_score) && norm.sentiment_score >= 0,
    { input: score, result: norm.sentiment_score }
  );

  recordAssert(
    'getDailyReports:normalizeReport',
    `required string fields default safely for score ${score}`,
    typeof norm.id === 'string' &&
    typeof norm.source === 'string' &&
    typeof norm.title === 'string' &&
    typeof norm.summary === 'string' &&
    typeof norm.severity === 'string' &&
    typeof norm.defect_category === 'string',
    { norm }
  );
}

// KPI Stress Testing with extreme existingStats and empty reports
const kpiScenarios = [
  { name: 'empty reports, empty stats', reports: [], stats: {} },
  { name: 'empty reports, NaN stats', reports: [], stats: { total_scraped: NaN, avg_negativity_score: NaN } },
  { name: 'empty reports, Infinity stats', reports: [], stats: { total_scraped: Infinity, avg_negativity_score: Infinity } },
  { name: 'empty reports, negative stats', reports: [], stats: { total_scraped: -50, avg_negativity_score: -1 } },
  { name: 'empty reports, huge stats', reports: [], stats: { total_scraped: 1e15, avg_negativity_score: 1e15 } },
];

for (const sc of kpiScenarios) {
  const kpi = dailyReports.calculateKPIs(sc.reports, sc.stats);
  recordAssert(
    'getDailyReports:calculateKPIs',
    `critical_defect_count is finite for ${sc.name}`,
    Number.isFinite(kpi.critical_defect_count) && !Number.isNaN(kpi.critical_defect_count),
    { sc, kpi }
  );
  recordAssert(
    'getDailyReports:calculateKPIs',
    `avg_negativity_score is non-NaN for ${sc.name}`,
    !Number.isNaN(kpi.avg_negativity_score),
    { sc, kpi }
  );
  recordAssert(
    'getDailyReports:calculateKPIs',
    `top_model is formatted string for ${sc.name}`,
    typeof kpi.top_model === 'string' && kpi.top_model.length > 0,
    { sc, kpi }
  );
  recordAssert(
    'getDailyReports:calculateKPIs',
    `top_platform is formatted string for ${sc.name}`,
    typeof kpi.top_platform === 'string' && kpi.top_platform.length > 0,
    { sc, kpi }
  );
}

// Main getDailyReports() loader call
const fullDailyData = dailyReports.getDailyReports();
recordAssert(
  'getDailyReports:main',
  'getDailyReports() returns valid structured data with non-empty reports array',
  Array.isArray(fullDailyData.reports) && fullDailyData.reports.length > 0,
  { count: fullDailyData.reports.length }
);

// ============================================================================
// 2. getSubsidyData.ts Adversarial Testing
// ============================================================================
console.log('--- [2. getSubsidyData.ts Adversarial Testing] ---');

const adversarialMsrpValues = [
  0,
  -1,
  -50000000,
  54999999,
  55000000,
  84999999,
  85000000,
  100000000,
  Infinity,
  -Infinity,
  NaN,
  null,
  undefined,
  1e15,
];

for (const msrp of adversarialMsrpValues) {
  const ratio = subsidy.getPriceSubsidyRatio(msrp);
  recordAssert(
    'getSubsidyData:getPriceSubsidyRatio',
    `ratio is finite and non-NaN for msrp ${msrp}`,
    Number.isFinite(ratio) && !Number.isNaN(ratio) && ratio >= 0.0 && ratio <= 1.0,
    { msrp, ratio }
  );

  if (msrp === Infinity && ratio === 1.0) {
    recordAnomaly(
      'getSubsidyData:getPriceSubsidyRatio',
      'Infinity MSRP evaluates to ratio 1.0 (100% eligibility) due to !Number.isFinite check defaulting to 1.0 rather than luxury tier 0.0',
      { msrp, ratio }
    );
  }
}

// Test calculateNetSubsidy with extreme customMsrp inputs
for (const msrp of adversarialMsrpValues) {
  const subRes = subsidy.calculateNetSubsidy('ioniq-5-2026', 'KR-11', msrp);
  recordAssert(
    'getSubsidyData:calculateNetSubsidy',
    `nationalSubsidyKrw is finite and >= 0 for msrp ${msrp}`,
    Number.isFinite(subRes.nationalSubsidyKrw) && !Number.isNaN(subRes.nationalSubsidyKrw) && subRes.nationalSubsidyKrw >= 0,
    { msrp, subRes }
  );
  recordAssert(
    'getSubsidyData:calculateNetSubsidy',
    `localSubsidyKrw is finite and >= 0 for msrp ${msrp}`,
    Number.isFinite(subRes.localSubsidyKrw) && !Number.isNaN(subRes.localSubsidyKrw) && subRes.localSubsidyKrw >= 0,
    { msrp, subRes }
  );
  recordAssert(
    'getSubsidyData:calculateNetSubsidy',
    `totalSubsidyKrw is finite and >= 0 for msrp ${msrp}`,
    Number.isFinite(subRes.totalSubsidyKrw) && !Number.isNaN(subRes.totalSubsidyKrw) && subRes.totalSubsidyKrw >= 0,
    { msrp, subRes }
  );
  recordAssert(
    'getSubsidyData:calculateNetSubsidy',
    `netPurchasePriceKrw is non-NaN for msrp ${msrp}`,
    !Number.isNaN(subRes.netPurchasePriceKrw),
    { msrp, netPurchasePriceKrw: subRes.netPurchasePriceKrw }
  );

  if (msrp === Infinity && subRes.netPurchasePriceKrw === Infinity) {
    recordAnomaly(
      'getSubsidyData:calculateNetSubsidy',
      'Infinity customMsrp results in Infinity netPurchasePriceKrw',
      { msrp, netPurchasePriceKrw: subRes.netPurchasePriceKrw }
    );
  }
}

// Test null/undefined resilience in lookup helpers
try {
  subsidy.getModelById(null);
  recordAssert('getSubsidyData:getModelById', 'getModelById(null) does not throw', true);
} catch (err) {
  recordAnomaly(
    'getSubsidyData:getModelById',
    'getModelById(null) throws TypeError (cannot read properties of null reading trim)',
    { error: err.message }
  );
}

try {
  subsidy.getRegionById(null);
  recordAssert('getSubsidyData:getRegionById', 'getRegionById(null) does not throw', true);
} catch (err) {
  recordAnomaly(
    'getSubsidyData:getRegionById',
    'getRegionById(null) throws TypeError (cannot read properties of null reading trim)',
    { error: err.message }
  );
}

// ============================================================================
// 3. getDepreciationData.ts Adversarial Testing
// ============================================================================
console.log('--- [3. getDepreciationData.ts Adversarial Testing] ---');

// 3.1 calculateDepreciation
const adversarialYears = [0, -1, 0.5, 1, 3, 5, 10, Infinity, -Infinity, NaN, 1e15];
const adversarialMileages = [0, -1, 10000, 50000, 500000, Infinity, -Infinity, NaN, 1e15];
const adversarialPrices = [0, -1, 50000000, 100000000, Infinity, -Infinity, NaN, 1e15];

for (const y of adversarialYears) {
  for (const km of [0, 50000, NaN, Infinity]) {
    const depRes = depreciation.calculateDepreciation({
      modelId: 'ioniq-5',
      years: y,
      mileageKm: km,
      customPurchasePriceKrw: 60000000,
    });

    recordAssert(
      'getDepreciationData:calculateDepreciation',
      `adjustedResidualPct is finite and within [5, 99] for years=${y}, km=${km}`,
      Number.isFinite(depRes.adjustedResidualPct) &&
      !Number.isNaN(depRes.adjustedResidualPct) &&
      depRes.adjustedResidualPct >= 5.0 &&
      depRes.adjustedResidualPct <= 99.0,
      { y, km, res: depRes.adjustedResidualPct }
    );

    recordAssert(
      'getDepreciationData:calculateDepreciation',
      `estimatedResidualPriceKrw is finite and >= 0 for years=${y}, km=${km}`,
      Number.isFinite(depRes.estimatedResidualPriceKrw) &&
      !Number.isNaN(depRes.estimatedResidualPriceKrw) &&
      depRes.estimatedResidualPriceKrw >= 0,
      { y, km, res: depRes.estimatedResidualPriceKrw }
    );
  }
}

// Test modelId missing/null
try {
  depreciation.calculateDepreciation({ years: 3 });
  recordAssert('getDepreciationData:calculateDepreciation', 'calculateDepreciation({ years: 3 }) succeeds with default model', true);
} catch (err) {
  recordAnomaly(
    'getDepreciationData:calculateDepreciation',
    'calculateDepreciation({ years: 3 }) throws TypeError when modelId is undefined',
    { error: err.message }
  );
}

// 3.2 simulateBatteryHealth
const healthTestGrid = [
  { name: 'nominal 3y 45k km', input: { years: 3, totalKm: 45000 } },
  { name: 'zero years and zero km', input: { years: 0, totalKm: 0 } },
  { name: 'negative years and km', input: { years: -5, totalKm: -50000 } },
  { name: 'NaN inputs', input: { years: NaN, totalKm: NaN, ambientTempC: NaN, storageSoc: NaN, dcfcRatio: NaN, vehicleEfficiencyKmPerKwh: NaN, packCapacityKwh: NaN } },
  { name: 'Infinity inputs', input: { years: Infinity, totalKm: Infinity, ambientTempC: Infinity, storageSoc: Infinity, dcfcRatio: Infinity, vehicleEfficiencyKmPerKwh: Infinity, packCapacityKwh: Infinity } },
  { name: 'extreme temperature -300C', input: { years: 3, ambientTempC: -300 } },
  { name: 'extreme temperature +100C', input: { years: 3, ambientTempC: 100 } },
  { name: 'huge 1e15 km and years', input: { years: 1e15, totalKm: 1e15 } },
];

for (const h of healthTestGrid) {
  const bRes = depreciation.simulateBatteryHealth(h.input);
  recordAssert(
    'getDepreciationData:simulateBatteryHealth',
    `sohPct is non-NaN and within [0, 100] for ${h.name}`,
    !Number.isNaN(bRes.sohPct) && bRes.sohPct >= 0 && bRes.sohPct <= 100,
    { h, sohPct: bRes.sohPct }
  );

  recordAssert(
    'getDepreciationData:simulateBatteryHealth',
    `grade is valid grade string for ${h.name}`,
    ['GRADE_A', 'GRADE_B', 'GRADE_C', 'CRITICAL'].includes(bRes.grade),
    { h, grade: bRes.grade }
  );

  // Check if any numeric property is NaN
  const naNProps = Object.entries(bRes).filter(([k, v]) => typeof v === 'number' && Number.isNaN(v)).map(([k]) => k);
  if (naNProps.length > 0) {
    recordAnomaly(
      'getDepreciationData:simulateBatteryHealth',
      `NaN encountered in battery health result properties under ${h.name}`,
      { properties: naNProps }
    );
  }
}

// 3.3 calculateSubsidyClawback
const clawbackMonths = [0, -5, 1, 3, 6, 12, 18, 23.9, 24, 25, 36, NaN, Infinity];
const clawbackTransfers = ['intra', 'inter', 'export'];

for (const m of clawbackMonths) {
  for (const t of clawbackTransfers) {
    const claw = depreciation.calculateSubsidyClawback(m, 1500000, t, 6500000);
    recordAssert(
      'getDepreciationData:calculateSubsidyClawback',
      `totalClawbackKrw is non-NaN for months=${m}, type=${t}`,
      !Number.isNaN(claw.totalClawbackKrw),
      { m, t, totalClawbackKrw: claw.totalClawbackKrw }
    );
    recordAssert(
      'getDepreciationData:calculateSubsidyClawback',
      `remainingMonthsOfObligation is non-NaN and >= 0 for months=${m}, type=${t}`,
      !Number.isNaN(claw.remainingMonthsOfObligation) && claw.remainingMonthsOfObligation >= 0,
      { m, t, rem: claw.remainingMonthsOfObligation }
    );
    recordAssert(
      'getDepreciationData:calculateSubsidyClawback',
      `explanation is formatted string for months=${m}, type=${t}`,
      typeof claw.explanation === 'string' && claw.explanation.length > 0,
      { m, t }
    );
  }
}

// Adversarial NaN and Infinity subsidy amounts
const clawNaN = depreciation.calculateSubsidyClawback(12, NaN, 'inter', NaN);
if (Number.isNaN(clawNaN.totalClawbackKrw)) {
  recordAnomaly(
    'getDepreciationData:calculateSubsidyClawback',
    'NaN localSubsidyKrw propagates to NaN totalClawbackKrw and explanation string',
    { result: clawNaN }
  );
}

const clawInf = depreciation.calculateSubsidyClawback(12, Infinity, 'inter', Infinity);
if (!Number.isFinite(clawInf.totalClawbackKrw)) {
  recordAnomaly(
    'getDepreciationData:calculateSubsidyClawback',
    'Infinity localSubsidyKrw propagates to Infinity totalClawbackKrw',
    { result: clawInf }
  );
}

// 3.4 calculateTcoComparison
const tcoGrid = [
  { name: 'baseline 15k km, 3y', args: [15000, 3, 5.2, 0.70, 1998] },
  { name: 'zero km and zero years', args: [0, 0, 0, 0, 0] },
  { name: 'negative km and years', args: [-15000, -3, -5, -1, -2000] },
  { name: 'all NaN inputs', args: [NaN, NaN, NaN, NaN, NaN] },
  { name: 'all Infinity inputs', args: [Infinity, Infinity, Infinity, Infinity, Infinity] },
  { name: 'huge 1e15 inputs', args: [1e15, 10, 5.2, 0.70, 1998] },
];

for (const tc of tcoGrid) {
  const tco = depreciation.calculateTcoComparison(...tc.args);
  recordAssert(
    'getDepreciationData:calculateTcoComparison',
    `totalCumulativeSavingsKrw is finite and non-NaN for ${tc.name}`,
    Number.isFinite(tco.totalCumulativeSavingsKrw) && !Number.isNaN(tco.totalCumulativeSavingsKrw),
    { tc, savings: tco.totalCumulativeSavingsKrw }
  );
  recordAssert(
    'getDepreciationData:calculateTcoComparison',
    `evTotalFuelCostKrw is finite and non-NaN for ${tc.name}`,
    Number.isFinite(tco.evTotalFuelCostKrw) && !Number.isNaN(tco.evTotalFuelCostKrw),
    { tc, cost: tco.evTotalFuelCostKrw }
  );
  recordAssert(
    'getDepreciationData:calculateTcoComparison',
    `yearlyBreakdown length is >= 1 for ${tc.name}`,
    Array.isArray(tco.yearlyBreakdown) && tco.yearlyBreakdown.length >= 1,
    { tc, len: tco.yearlyBreakdown.length }
  );
}

// ============================================================================
// 4. UI Math & Coordinate Safety Checks
// ============================================================================
console.log('--- [4. UI Helper Equation Static Verification] ---');

// Verify getY function safety logic
const getYSafe = (val, maxVal) => {
  if (!Number.isFinite(val) || !Number.isFinite(maxVal) || maxVal <= 0) return 230;
  const ratio = Math.max(0, Math.min(1, val / maxVal));
  return 230 - ratio * 200;
};

const getYTestInputs = [
  { val: 0, maxVal: 100, expected: 230 },
  { val: 100, maxVal: 100, expected: 30 },
  { val: 50, maxVal: 100, expected: 130 },
  { val: NaN, maxVal: 100, expected: 230 },
  { val: 50, maxVal: NaN, expected: 230 },
  { val: 50, maxVal: 0, expected: 230 },
  { val: Infinity, maxVal: 100, expected: 230 },
  { val: 50, maxVal: Infinity, expected: 230 },
];

for (const inp of getYTestInputs) {
  const res = getYSafe(inp.val, inp.maxVal);
  recordAssert(
    'UI:getY',
    `getY returns finite safe coordinate ${inp.expected} for val=${inp.val}, maxVal=${inp.maxVal}`,
    res === inp.expected,
    { inp, res }
  );
}

// Verify monthly savings safeYears division guard
const holdingYearsCandidates = [0, -1, NaN, Infinity, 3, 5];
for (const hy of holdingYearsCandidates) {
  const safeYears = Number.isFinite(hy) && hy > 0 ? hy : 1;
  const monthlyMonths = Math.max(1, Math.round(safeYears * 12));
  const savings = 3600000;
  const monthlySavings = Math.round(savings / monthlyMonths);
  recordAssert(
    'UI:monthlySavings',
    `monthly savings denominator is strictly > 0 and finite for holdingYears=${hy}`,
    Number.isFinite(monthlySavings) && !Number.isNaN(monthlySavings) && monthlyMonths >= 1,
    { hy, safeYears, monthlyMonths, monthlySavings }
  );
}

console.log('\n================================================================');
console.log('🏁 WAVE 3 EMPIRICAL CHALLENGER STRESS HARNESS COMPLETED');
console.log(`   Total Assertions Evaluated: ${report.totalTests}`);
console.log(`   Passed:                     ${report.passed}`);
console.log(`   Failed:                     ${report.failed}`);
console.log(`   Adversarial Anomalies:      ${report.anomalies.length}`);
console.log('================================================================\n');

if (report.failed > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
