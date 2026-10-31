/**
 * tests/adversarial_security_fuzz_cycle23.mjs
 * Cycle 23 Adversarial Security Fuzzer
 * Exhaustively stress-tests all input surfaces across ev-stealth-web/src/lib:
 * - depreciationCalculations.ts
 * - reliabilityCalculations.ts
 * - subsidyCalculations.ts
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const libDir = fs.existsSync(path.resolve(__dirname, '../src/lib'))
  ? path.resolve(__dirname, '../src/lib')
  : path.resolve(__dirname, '../ev-stealth-web/src/lib');

const dep = await import(pathToFileURL(path.resolve(libDir, 'depreciationCalculations.ts')).href);
const rel = await import(pathToFileURL(path.resolve(libDir, 'reliabilityCalculations.ts')).href);
const sub = await import(pathToFileURL(path.resolve(libDir, 'subsidyCalculations.ts')).href);

const suite = {
  totalAssertions: 0,
  passedAssertions: 0,
  failedAssertions: 0,
  crashes: 0,
  nanLeaks: 0,
  stateLeaks: 0,
  failures: []
};

function recordAssert(context, name, passed, metadata = {}) {
  suite.totalAssertions++;
  if (passed) {
    suite.passedAssertions++;
  } else {
    suite.failedAssertions++;
    suite.failures.push({ context, name, metadata });
    console.error(`❌ [ASSERTION FAILED] [${context}] ${name}`, metadata);
  }
}

// -------------------------------------------------------------
// ADVERSARIAL PAYLOAD CORPUS
// -------------------------------------------------------------
const ADVERSARIAL_NUMBERS = [
  -Infinity,
  -1e18,
  -10_000_000_000,
  -50_000_000,
  -15_000,
  -100,
  -1,
  -0.000001,
  0,
  0.000001,
  1,
  15_000,
  55_000_000,
  85_000_000,
  85_000_001,
  100_000_000,
  10_000_000_000, // 10 Billion KRW boundary
  10_000_000_001, // Exceeding 10 Billion KRW
  50_000_000_000,
  100_000_000_000,
  1e15,
  Number.MAX_SAFE_INTEGER,
  Infinity,
  NaN,
];

const ADVERSARIAL_STRINGS = [
  '',
  '   ',
  '\t\r\n',
  '\u0000',
  'null\u0000byte',
  '\x00\x00\x00',
  'admin\u0000',
  // SQL Injection payloads
  "' OR '1'='1",
  "'; DROP TABLE subsidies; --",
  "admin' --",
  "UNION SELECT null, username, password FROM users --",
  "1' ORDER BY 1--+",
  // XSS Injection payloads
  "<script>alert('XSS')</script>",
  "<img src=x onerror=alert(1)>",
  "javascript:void(0)",
  '"><svg/onload=alert(document.cookie)>',
  "<iframe src=\"javascript:alert('xss')\"></iframe>",
  // Format string & special symbols
  "%s%s%s%s%s%n",
  "{{7*7}}",
  "${7*7}",
  // Unicode control & edge characters
  "\uFFFF",
  "\uFEFF",
  "\u200B", // zero-width space
  "🚗⚡️🔋💰",
  "현대 아이오닉 5 롱레인지 AWD 2026",
  "A".repeat(10000), // Buffer/DoS string length
];

console.log('================================================================');
console.log('🛡️ CYCLE 23 ADVERSARIAL SECURITY FUZZER: EV-STEALTH-WEB/SRC/LIB');
console.log('================================================================');

// =============================================================
// SURFACE 1: DEPRECIATION CALCULATIONS
// =============================================================
console.log('\n--- [SURFACE 1: depreciationCalculations.ts] ---');

// 1.1 clamp()
for (const n of ADVERSARIAL_NUMBERS) {
  const clamped = dep.clamp(n, 5, 95);
  recordAssert('dep:clamp', `clamp(${n}) must not return NaN`, !Number.isNaN(clamped));
  recordAssert('dep:clamp', `clamp(${n}) must be finite`, Number.isFinite(clamped));
  recordAssert('dep:clamp', `clamp(${n}) must be bounded [5, 95]`, clamped >= 5 && clamped <= 95);
}

// 1.2 normalizeChemistry()
for (const s of ADVERSARIAL_STRINGS) {
  try {
    const chem = dep.normalizeChemistry(s);
    recordAssert('dep:normalizeChemistry', `normalizeChemistry must return valid BatteryChemistryType for payload`, ['LFP', 'NCM_622', 'NCM_811', 'NCMA', 'NCA'].includes(chem));
  } catch (err) {
    suite.crashes++;
    recordAssert('dep:normalizeChemistry', `Crashed on string payload`, false, { error: err.message, payload: s.slice(0, 30) });
  }
}

// 1.3 interpolateBaselineResidual()
for (const yr of ADVERSARIAL_NUMBERS) {
  for (const basis of ['msrp', 'effective', 'UNKNOWN', '', null, undefined]) {
    try {
      const res = dep.interpolateBaselineResidual(null, yr, basis);
      recordAssert('dep:interpolateBaselineResidual', `interpolateBaselineResidual must return finite residual for yr=${yr}`, Number.isFinite(res) && !Number.isNaN(res));
      recordAssert('dep:interpolateBaselineResidual', `interpolateBaselineResidual must be >= 10.0%`, res >= 10.0);
    } catch (err) {
      suite.crashes++;
      recordAssert('dep:interpolateBaselineResidual', `Crashed on yr=${yr}, basis=${basis}`, false, { error: err.message });
    }
  }
}

// 1.4 calculateDepreciation()
const depInputCorpus = [
  null,
  undefined,
  {},
  { years: -5, mileageKm: -10000 },
  { years: NaN, mileageKm: NaN, customPurchasePriceKrw: NaN },
  { years: Infinity, mileageKm: Infinity, customPurchasePriceKrw: Infinity },
  { years: 3, mileageKm: 45000, customPurchasePriceKrw: 10_000_000_001 }, // > 10 Billion KRW
  { years: 3, mileageKm: 45000, customPurchasePriceKrw: 50_000_000_000 }, // 50 Billion KRW
  { modelId: "' OR '1'='1", years: 3, mileageKm: 45000 },
  { modelId: "<script>alert(1)</script>", years: 3, mileageKm: 45000 },
  { modelId: "\u0000admin", years: 3, mileageKm: 45000 },
];

for (const input of depInputCorpus) {
  try {
    const res = dep.calculateDepreciation(input);
    recordAssert('dep:calculateDepreciation', 'Result must be an object', typeof res === 'object' && res !== null);
    recordAssert('dep:calculateDepreciation', 'adjustedResidualPct must not be NaN', !Number.isNaN(res.adjustedResidualPct));
    recordAssert('dep:calculateDepreciation', 'adjustedResidualPct must be finite', Number.isFinite(res.adjustedResidualPct));
    recordAssert('dep:calculateDepreciation', 'basePurchasePriceKrw must not exceed 10 Billion KRW', res.basePurchasePriceKrw <= 10_000_000_000);
    recordAssert('dep:calculateDepreciation', 'estimatedResidualPriceKrw must not be NaN', !Number.isNaN(res.estimatedResidualPriceKrw));
    recordAssert('dep:calculateDepreciation', 'depreciationAmountKrw must not be NaN', !Number.isNaN(res.depreciationAmountKrw));
    recordAssert('dep:calculateDepreciation', 'Residual floor must be at least 5.0%', res.adjustedResidualPct >= 5.0);
    recordAssert('dep:calculateDepreciation', 'Residual ceiling must be at most 99.0%', res.adjustedResidualPct <= 99.0);
  } catch (err) {
    suite.crashes++;
    recordAssert('dep:calculateDepreciation', `Crashed on input: ${JSON.stringify(input)}`, false, { error: err.message });
  }
}

// 1.5 simulateBatteryHealth()
for (const yr of [-10, 0, 3, 10, 100, NaN, Infinity]) {
  for (const km of [-5000, 0, 50000, 1e7, NaN, Infinity]) {
    for (const dcfc of [-1.0, 0.0, 0.5, 2.0, NaN, Infinity]) {
      for (const temp of [-60, 0, 25, 90, NaN, Infinity]) {
        for (const chem of ['LFP', 'NCM_811', "' OR 1=1 --", "<script>", "\u0000"]) {
          try {
            const res = dep.simulateBatteryHealth({
              years: yr,
              totalKm: km,
              dcfcRatio: dcfc,
              ambientTempC: temp,
              chemistry: chem,
            });
            recordAssert('dep:simulateBatteryHealth', 'sohPct must not be NaN', !Number.isNaN(res.sohPct));
            recordAssert('dep:simulateBatteryHealth', 'sohPct must be finite', Number.isFinite(res.sohPct));
            recordAssert('dep:simulateBatteryHealth', 'sohPct must be bounded [0, 100]', res.sohPct >= 0.0 && res.sohPct <= 100.0);
            recordAssert('dep:simulateBatteryHealth', 'totalLossPct must be finite', Number.isFinite(res.totalLossPct));
            recordAssert('dep:simulateBatteryHealth', 'grade must be a valid risk grade', ['GRADE_A', 'GRADE_B', 'GRADE_C', 'CRITICAL'].includes(res.grade));
          } catch (err) {
            suite.crashes++;
            recordAssert('dep:simulateBatteryHealth', `Crashed on yr=${yr}, km=${km}, dcfc=${dcfc}, temp=${temp}`, false, { error: err.message });
          }
        }
      }
    }
  }
}

// Null/undefined parameter check for simulateBatteryHealth
try {
  const nullRes = dep.simulateBatteryHealth(null);
  recordAssert('dep:simulateBatteryHealth:null', 'Handles null params safely without crash', typeof nullRes === 'object' && !Number.isNaN(nullRes.sohPct));
} catch (err) {
  suite.crashes++;
  recordAssert('dep:simulateBatteryHealth:null', 'Crashed on null params', false, { error: err.message });
}

// 1.6 calculateSubsidyClawback()
for (const months of [-12, 0, 1, 12, 23, 24, 48, NaN, Infinity, 1000]) {
  for (const loc of [-1000, 0, 1_500_000, 10_000_000_001, NaN, Infinity]) {
    for (const nat of [-1000, 0, 6_500_000, 10_000_000_001, NaN, Infinity]) {
      for (const tType of ['intra', 'inter', 'export', 'INVALID', "' OR '1'='1", null, undefined]) {
        try {
          const res = dep.calculateSubsidyClawback(months, loc, tType, nat);
          recordAssert('dep:calculateSubsidyClawback', 'totalClawbackKrw must not be NaN', !Number.isNaN(res.totalClawbackKrw));
          recordAssert('dep:calculateSubsidyClawback', 'totalClawbackKrw must be non-negative', res.totalClawbackKrw >= 0);
          recordAssert('dep:calculateSubsidyClawback', 'effectiveClawbackRate must be bounded [0, 1]', res.effectiveClawbackRate >= 0.0 && res.effectiveClawbackRate <= 1.0);
          if (months >= 24 || tType === 'intra') {
            recordAssert('dep:calculateSubsidyClawback', 'Must be exempt after 24m or intra transfer', res.isExempt === true && res.totalClawbackKrw === 0);
          }
        } catch (err) {
          suite.crashes++;
          recordAssert('dep:calculateSubsidyClawback', `Crashed on months=${months}, loc=${loc}, nat=${nat}`, false, { error: err.message });
        }
      }
    }
  }
}

// 1.7 calculateTcoComparison()
for (const km of [-10000, 0, 15000, 100000, NaN, Infinity, 1e9]) {
  for (const yr of [-5, 0, 1, 5, 10, 50, NaN, Infinity]) {
    for (const eff of [-5, 0, 5.2, 20, NaN, Infinity]) {
      try {
        const res = dep.calculateTcoComparison(km, yr, eff);
        recordAssert('dep:calculateTcoComparison', 'totalCumulativeSavingsKrw must not be NaN', !Number.isNaN(res.totalCumulativeSavingsKrw));
        recordAssert('dep:calculateTcoComparison', 'yearlyBreakdown must be a non-empty array', Array.isArray(res.yearlyBreakdown) && res.yearlyBreakdown.length > 0);
      } catch (err) {
        suite.crashes++;
        recordAssert('dep:calculateTcoComparison', `Crashed on km=${km}, yr=${yr}, eff=${eff}`, false, { error: err.message });
      }
    }
  }
}

// =============================================================
// SURFACE 2: RELIABILITY CALCULATIONS
// =============================================================
console.log('\n--- [SURFACE 2: reliabilityCalculations.ts] ---');

// 2.1 getAllEnrichedModels() with corrupt payloads
const corruptDatabases = [
  null,
  undefined,
  {},
  { brands: null },
  { brands: 'not_an_array' },
  { brands: [null, undefined, 42, 'str', {}, { models: null }, { models: [null, undefined, {}] }] },
  { brands: [{ name_ko: "<script>alert(1)</script>", models: [{ id: "m-1", name: "Inject' OR 1=1" }] }] },
];

for (const db of corruptDatabases) {
  try {
    const models = rel.getAllEnrichedModels(db);
    recordAssert('rel:getAllEnrichedModels', 'Must return an array without throwing', Array.isArray(models));
  } catch (err) {
    suite.crashes++;
    recordAssert('rel:getAllEnrichedModels', 'Crashed on corrupt db', false, { error: err.message });
  }
}

// 2.2 getVerdictBadgeInfo()
for (const v of [...ADVERSARIAL_STRINGS, 'BUY_SAFE', 'CAUTION', 'AVOID', null, undefined]) {
  try {
    const badge = rel.getVerdictBadgeInfo(v);
    recordAssert('rel:getVerdictBadgeInfo', 'Must return valid badge info object', typeof badge === 'object' && typeof badge.label === 'string');
  } catch (err) {
    suite.crashes++;
    recordAssert('rel:getVerdictBadgeInfo', `Crashed on verdict: ${v}`, false, { error: err.message });
  }
}

// 2.3 getDsiSeverityLevel()
for (const n of ADVERSARIAL_NUMBERS) {
  try {
    const sev = rel.getDsiSeverityLevel(n);
    recordAssert('rel:getDsiSeverityLevel', 'Level must be one of the 4 defined severity tiers', ['CRITICAL', 'HIGH', 'MODERATE', 'LOW'].includes(sev.level));
  } catch (err) {
    suite.crashes++;
    recordAssert('rel:getDsiSeverityLevel', `Crashed on DSI: ${n}`, false, { error: err.message });
  }
}

// 2.4 getGradeBadgeStyle()
for (const g of [...ADVERSARIAL_STRINGS, 'A+', 'A', 'B', 'C', 'D', 'F', null, undefined]) {
  try {
    const style = rel.getGradeBadgeStyle(g);
    recordAssert('rel:getGradeBadgeStyle', 'Style must contain bg, text, border strings', typeof style.bg === 'string' && typeof style.text === 'string' && typeof style.border === 'string');
  } catch (err) {
    suite.crashes++;
    recordAssert('rel:getGradeBadgeStyle', `Crashed on grade: ${g}`, false, { error: err.message });
  }
}

// 2.5 getModelReliabilityById(), getDefectsForModel(), getBrandReliabilityById()
for (const id of ADVERSARIAL_STRINGS) {
  try {
    const m = rel.getModelReliabilityById(id);
    const d = rel.getDefectsForModel(id);
    const b = rel.getBrandReliabilityById(id);
    recordAssert('rel:lookups', `Lookups must handle string without throwing: ${id.slice(0, 20)}`, Array.isArray(d));
  } catch (err) {
    suite.crashes++;
    recordAssert('rel:lookups', `Crashed on lookup query: ${id}`, false, { error: err.message });
  }
}

// =============================================================
// SURFACE 3: SUBSIDY CALCULATIONS
// =============================================================
console.log('\n--- [SURFACE 3: subsidyCalculations.ts] ---');

// 3.1 getPriceSubsidyRatio()
for (const n of ADVERSARIAL_NUMBERS) {
  const ratio = sub.getPriceSubsidyRatio(n);
  recordAssert('sub:getPriceSubsidyRatio', `Ratio must not be NaN for ${n}`, !Number.isNaN(ratio));
  recordAssert('sub:getPriceSubsidyRatio', `Ratio must be one of [0.0, 0.5, 1.0] for ${n}`, [0.0, 0.5, 1.0].includes(ratio));
  if (n <= 0 || !Number.isFinite(n) || n > 85_000_000) {
    recordAssert('sub:getPriceSubsidyRatio', `Ratio must be 0.0 for out-of-bound / luxury MSRP ${n}`, ratio === 0.0);
  }
  if (n > 0 && n <= 55_000_000) {
    recordAssert('sub:getPriceSubsidyRatio', `Ratio must be 1.0 for <= 55M MSRP ${n}`, ratio === 1.0);
  }
  if (n > 55_000_000 && n <= 85_000_000) {
    recordAssert('sub:getPriceSubsidyRatio', `Ratio must be 0.5 for 55M < MSRP <= 85M: ${n}`, ratio === 0.5);
  }
}

// 3.2 formatters
for (const n of ADVERSARIAL_NUMBERS) {
  try {
    const curr = sub.formatCurrencyKrw(n);
    const man = sub.formatManwon(n);
    const bil = sub.formatBillionKrw(n);
    const depRate = sub.formatDepletionRate(n);
    const badge = sub.getDepletionBadgeStyle(n);

    recordAssert('sub:formatters', `formatCurrencyKrw must be a string for ${n}`, typeof curr === 'string');
    recordAssert('sub:formatters', `formatManwon must be a string for ${n}`, typeof man === 'string');
    recordAssert('sub:formatters', `formatBillionKrw must be a string for ${n}`, typeof bil === 'string');
    recordAssert('sub:formatters', `formatDepletionRate must be a string for ${n}`, typeof depRate === 'string');
    recordAssert('sub:formatters', `getDepletionBadgeStyle must return AlertSeverity for ${n}`, ['HEALTHY', 'CAUTION', 'WARNING', 'CRITICAL', 'DEPLETED'].includes(badge.severity));
  } catch (err) {
    suite.crashes++;
    recordAssert('sub:formatters', `Formatter crashed on ${n}`, false, { error: err.message });
  }
}

// 3.3 calculateNetSubsidyPure()
const dummyModel = {
  model_id: 'test-ioniq-5',
  name_ko: '아이오닉 5 테스트',
  base_price_krw: 52_000_000,
  national_subsidy_krw: 6_500_000,
  price_subsidy_ratio: 1.0,
  battery_specs: { capacity_kwh: 77.4, chemistry: 'NCM' }
};

const dummyRegion = {
  region_id: 'seoul',
  name_ko: '서울특별시',
  name_en: 'Seoul',
  iso_code: 'KR-11',
  overall_depletion_rate: 65.5,
  overall_status: 'CAUTION',
  categories: {
    passenger: {
      announced_units: 1000,
      applied_units: 655,
      delivered_units: 500,
      remaining_units: 345,
      depletion_rate: 65.5,
      delivery_rate: 50.0,
      status: 'CAUTION',
      max_local_subsidy_krw: 1_500_000
    }
  }
};

for (const msrp of ADVERSARIAL_NUMBERS) {
  for (const opt of [
    undefined,
    {},
    { isYouthFirstTimeBuyer: true, isSmallBusinessOrTaxi: true, isMultiChildFamily: true, isOldDieselScrappage: true },
  ]) {
    try {
      const res = sub.calculateNetSubsidyPure(dummyModel, dummyRegion, msrp, opt);
      recordAssert('sub:calculateNetSubsidyPure', 'netPurchasePriceKrw must not be NaN', !Number.isNaN(res.netPurchasePriceKrw));
      recordAssert('sub:calculateNetSubsidyPure', 'netPurchasePriceKrw must be non-negative', res.netPurchasePriceKrw >= 0);
      recordAssert('sub:calculateNetSubsidyPure', 'totalSubsidyKrw must not be NaN', !Number.isNaN(res.totalSubsidyKrw));
      recordAssert('sub:calculateNetSubsidyPure', 'msrpKrw must not exceed 10 Billion KRW', res.msrpKrw <= 10_000_000_000);
    } catch (err) {
      suite.crashes++;
      recordAssert('sub:calculateNetSubsidyPure', `Crashed on msrp=${msrp}`, false, { error: err.message });
    }
  }
}

// Null model & region resiliency in calculateNetSubsidyPure
try {
  const nullRes = sub.calculateNetSubsidyPure(null, null);
  recordAssert('sub:calculateNetSubsidyPure:null', 'Safely handles null model and region without crashing', typeof nullRes === 'object' && !Number.isNaN(nullRes.netPurchasePriceKrw));
} catch (err) {
  suite.crashes++;
  recordAssert('sub:calculateNetSubsidyPure:null', 'Crashed on null model/region', false, { error: err.message });
}

// 3.4 calculateSubsidyStatistics()
const corruptSubsidyDatasets = [
  null,
  undefined,
  {},
  { nationwide_summary: null, regions: null },
  { nationwide_summary: { total_announced_units: -10, total_applied_units: NaN, nationwide_depletion_rate: Infinity } },
  { regions: [null, undefined, {}, { region_id: "<script>", overall_depletion_rate: 98.5 }, { overall_depletion_rate: NaN }] },
  { regions: [null, { overall_depletion_rate: 100 }, null, { overall_depletion_rate: 45 }] },
];

for (const ds of corruptSubsidyDatasets) {
  try {
    const stats = sub.calculateSubsidyStatistics(ds);
    recordAssert('sub:calculateSubsidyStatistics', 'Must return valid statistics object', typeof stats === 'object' && stats !== null);
    recordAssert('sub:calculateSubsidyStatistics', 'nationalDepletionRate must not be NaN', !Number.isNaN(stats.nationalDepletionRate));
    recordAssert('sub:calculateSubsidyStatistics', 'criticalRegions must be an array', Array.isArray(stats.criticalRegions));
  } catch (err) {
    suite.crashes++;
    recordAssert('sub:calculateSubsidyStatistics', 'Crashed on corrupt subsidy dataset', false, { error: err.message });
  }
}

// 3.5 getRegionByIdFromList() & getModelByIdFromList()
for (const s of ADVERSARIAL_STRINGS) {
  for (const list of [null, undefined, [], [null, {}], [{ region_id: 'seoul', iso_code: 'KR-11', name_ko: '서울', name_en: 'Seoul' }]]) {
    try {
      const matchedR = sub.getRegionByIdFromList(list, s);
      const matchedM = sub.getModelByIdFromList(list, s);
      recordAssert('sub:resolvers', 'Must safely resolve without throwing', matchedR === undefined || typeof matchedR === 'object');
    } catch (err) {
      suite.crashes++;
      recordAssert('sub:resolvers', `Crashed on query "${s.slice(0, 20)}"`, false, { error: err.message });
    }
  }
}

console.log('\n================================================================');
console.log('🏁 CYCLE 23 ADVERSARIAL SECURITY FUZZER RESULTS:');
console.log(`   Total Assertions Evaluated: ${suite.totalAssertions}`);
console.log(`   Passed:                     ${suite.passedAssertions}`);
console.log(`   Failed:                     ${suite.failedAssertions}`);
console.log(`   Crashes / Exceptions:       ${suite.crashes}`);
console.log(`   NaN Value Leaks:            ${suite.nanLeaks}`);
console.log('================================================================');

if (suite.failedAssertions > 0 || suite.crashes > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
