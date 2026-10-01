/**
 * tests/test_challenger_fuzz_all.ts
 *
 * EMPIRICAL ADVERSARIAL STRESS & FUZZING HARNESS
 * Author: challenger_edge_cases
 *
 * Systematically exercises:
 * 1. VIN Decoder (getRecallData.ts)
 * 2. Subsidy Calculator & Tracker Logic (getSubsidyData.ts)
 * 3. Depreciation & Electrochemical Engine (getDepreciationData.ts)
 */

import * as recall from '../src/lib/getRecallData';
import * as subsidy from '../src/lib/getSubsidyData';
import * as depreciation from '../src/lib/getDepreciationData';

interface TestStats {
  total: number;
  passed: number;
  failed: number;
  bugsFound: string[];
}

const stats: TestStats = {
  total: 0,
  passed: 0,
  failed: 0,
  bugsFound: [],
};

function assert(condition: boolean, msg: string) {
  stats.total++;
  if (condition) {
    stats.passed++;
  } else {
    stats.failed++;
    console.error(`❌ [ASSERTION FAILURE] ${msg}`);
  }
}

function recordBug(id: string, description: string) {
  stats.bugsFound.push(`[${id}] ${description}`);
  console.warn(`🐛 [EMPIRICAL BUG FOUND] ${id}: ${description}`);
}

console.log('================================================================');
console.log('🚀 EMPIRICAL ADVERSARIAL CHALLENGE & FUZZING SUITE');
console.log('================================================================\n');

// ============================================================================
// PART 1: VIN DECODER FUZZING & ADVERSARIAL CASES (getRecallData.ts)
// ============================================================================
console.log('--- [PART 1: VIN Decoder Fuzzing & Stress Testing] ---');

// 1.1 Invalid lengths: 0, 1, 16, 18, 50, 1000 chars
const invalidLengthVins = [
  '',
  '   ',
  'K',
  'KM8KN4AE4NU12345',      // 16 chars
  'KM8KN4AE4NU1234567',     // 18 chars
  'A'.repeat(50),
  'A'.repeat(1000),
];

for (const vin of invalidLengthVins) {
  const v = recall.validateVinString(vin);
  assert(!v.valid, `validateVinString correctly rejects invalid length ${vin.trim().length}`);
  assert(v.error !== undefined && v.error.length > 0, `Descriptive error provided for length ${vin.trim().length}`);

  const decoded = recall.decodeVinAndCheckRecalls(vin);
  assert(!decoded.valid, `decodeVinAndCheckRecalls returns valid=false for length ${vin.trim().length}`);
  assert(decoded.overallRiskGrade === 'SAFE', `Risk grade defaults to SAFE for invalid VIN`);
  assert(decoded.recalls.length === 0, `Zero recalls returned for invalid VIN`);
}

// 1.2 Invalid characters (I, O, Q) per ISO 3779 standard
const invalidCharVins = [
  'KM8KN4AE4NI123456', // I at pos 11
  'KM8KN4AE4NO123456', // O at pos 11
  'KM8KN4AE4NQ123456', // Q at pos 11
  'IM8KN4AE4NU123456', // I at pos 1
  'OM8KN4AE4NU123456', // O at pos 1
  'QM8KN4AE4NU123456', // Q at pos 1
  'km8kn4ae4ni123456', // lowercase i
  'km8kn4ae4no123456', // lowercase o
  'km8kn4ae4nq123456', // lowercase q
];

for (const vin of invalidCharVins) {
  const v = recall.validateVinString(vin);
  assert(!v.valid, `validateVinString rejects forbidden char (I/O/Q) in "${vin}"`);
  assert(Boolean(v.error?.includes('I(아이)') || v.error?.includes('17자리')), `ISO 3779 diagnostic message provided`);

  const decoded = recall.decodeVinAndCheckRecalls(vin);
  assert(!decoded.valid, `decodeVinAndCheckRecalls returns valid=false for forbidden char: ${vin}`);
}

// 1.3 Special characters, Unicode, emojis, SQL injection, Null bytes
const adversarialPayloads = [
  'KM8KN4AE4NU12345!',
  'KM8KN4AE4NU12345@',
  'KM8KN4AE4NU12345#',
  'KM8KN4AE4NU1234\0',
  'KM8KN4AE4NU1234\n',
  'KM8KN4AE4NU1234\t',
  "KM8KN4'; DROP--",
  '<script>alert(1)</script>',
  'KM8KN4AE4NU123🚘',
  '현대아이오닉5전기차차대번호',
  'KM8KN4AE4NU1234\u200B', // zero-width space
  'KM8KN4AE4NU1234\uFEFF', // BOM
];

for (const vin of adversarialPayloads) {
  const v = recall.validateVinString(vin);
  assert(!v.valid, `validateVinString rejects payload: "${vin}"`);
  const decoded = recall.decodeVinAndCheckRecalls(vin);
  assert(!decoded.valid, `decodeVinAndCheckRecalls rejects payload without throwing: "${vin}"`);
}

// 1.4 Formatting tolerance: spaces and dashes should be stripped safely
const validWithDelimiters = [
  'KM8-KN4-AE4-NU123456',
  'KM8 KN4 AE4 NU123456',
  '  KM8KN4AE4NU123456  ',
  'km8kn4ae4nu123456', // lowercase normalization
];

for (const vin of validWithDelimiters) {
  const v = recall.validateVinString(vin);
  assert(v.valid, `validateVinString accepts and normalizes formatted VIN: "${vin}"`);
  assert(v.normalized === 'KM8KN4AE4NU123456', `Normalized to canonical KM8KN4AE4NU123456`);
}

// 1.5 Unknown WMI and prefix fallback
const unknownWmiVin = 'ZZZKN4AE4NU123456'; // ZZZ unknown
const unknownDecoded = recall.decodeVinAndCheckRecalls(unknownWmiVin);
assert(unknownDecoded.valid, `Unknown WMI passes syntax validation if valid 17 chars`);
assert(unknownDecoded.decodedBrand === '기타/미확인 브랜드', `Decoded brand fallback for unknown WMI`);
assert(unknownDecoded.decodedCountry === '미확인 국가', `Decoded country fallback for unknown WMI`);
assert(unknownDecoded.recalls.length === 0, `No false positive recalls for unknown WMI`);
assert(unknownDecoded.overallRiskGrade === 'SAFE', `Risk grade SAFE for unknown WMI`);

// 1.6 2022 Ioniq 5 VIN (KM8KN4AE4NU123456)
const ioniq5Vin = 'KM8KN4AE4NU123456';
const ioniq5Res = recall.decodeVinAndCheckRecalls(ioniq5Vin);
assert(ioniq5Res.valid, `2022 Ioniq 5 VIN valid`);
assert(ioniq5Res.decodedBrand === '현대자동차', `2022 Ioniq 5 brand decoded correctly: ${ioniq5Res.decodedBrand}`);
assert(ioniq5Res.decodedModel === '아이오닉 5', `2022 Ioniq 5 model decoded correctly: ${ioniq5Res.decodedModel}`);
assert(ioniq5Res.decodedYear === 2022, `2022 Ioniq 5 year decoded: ${ioniq5Res.decodedYear}`);
assert(ioniq5Res.batteryProfile !== undefined, `2022 Ioniq 5 battery profile matched`);
assert(ioniq5Res.recalls.length >= 1, `2022 Ioniq 5 has matching recalls (found ${ioniq5Res.recalls.length})`);
assert(
  ioniq5Res.recalls.some((r) => r.id === 'RC-2024-HYUNDAI-ICCU'),
  `2022 Ioniq 5 matches ICCU campaign RC-2024-HYUNDAI-ICCU`
);
assert(ioniq5Res.hasPowerLoss === true, `2022 Ioniq 5 flags power loss`);
assert(ioniq5Res.overallRiskGrade === 'WARNING' || ioniq5Res.overallRiskGrade === 'CRITICAL', `2022 Ioniq 5 risk grade WARNING/CRITICAL`);

// CRITICAL COLLISION PROTECTION: 2022 Ioniq 5 MUST NOT match 2018-2020 Kona/Ioniq EV Fire Recall
assert(
  !ioniq5Res.recalls.some((r) => r.id === 'RC-2021-HYUNDAI-KONA-FIRE'),
  `Collision Protection: 2022 Ioniq 5 must NOT match 2018-2020 Ioniq EV fire recall!`
);

// 1.7 2019 Ioniq EV (Legacy Model)
const ioniqEvModelRes = recall.checkRecallsByModel('현대자동차', '아이오닉 EV', 2019);
assert(ioniqEvModelRes.valid, `Ioniq EV model lookup valid`);
assert(
  ioniqEvModelRes.recalls.some((r) => r.id === 'RC-2021-HYUNDAI-KONA-FIRE'),
  `2019 Ioniq EV matches Kona/Ioniq fire recall (RC-2021-HYUNDAI-KONA-FIRE)`
);
assert(
  !ioniqEvModelRes.recalls.some((r) => r.id === 'RC-2024-HYUNDAI-ICCU'),
  `Collision Protection: 2019 Ioniq EV must NOT match 2021-2024 ICCU recall!`
);
assert(ioniqEvModelRes.hasFireRisk === true, `2019 Ioniq EV flags fire risk`);
assert(ioniqEvModelRes.overallRiskGrade === 'CRITICAL', `2019 Ioniq EV overall risk grade CRITICAL`);

// 1.8 Model Y VIN (5YJYGDEE8NF123456 - Fremont, 2022 N)
const modelYVin = '5YJYGDEE8NF123456';
const modelYRes = recall.decodeVinAndCheckRecalls(modelYVin);
assert(modelYRes.valid, `Model Y VIN valid`);
assert(modelYRes.decodedBrand === '테슬라', `Model Y brand decoded: ${modelYRes.decodedBrand}`);
assert(modelYRes.decodedModel === '모델 Y', `Model Y model decoded: ${modelYRes.decodedModel}`);
assert(modelYRes.decodedYear === 2022, `Model Y year decoded: ${modelYRes.decodedYear}`);
assert(modelYRes.batteryProfile !== undefined, `Model Y battery profile matched`);
assert(
  modelYRes.recalls.some((r) => r.id === 'RC-2024-TESLA-AUTOPILOT'),
  `Model Y matches Tesla Autopilot recall (RC-2024-TESLA-AUTOPILOT)`
);
assert(
  !modelYRes.recalls.some((r) => r.brand !== '테슬라'),
  `Model Y must NOT match other brands`
);

// 1.9 Year Edge Cases (2016 'G', 2026 'T', 2030 'Y', future/unknown 'Z')
const vinYear2016 = 'KM8KN4AE4GU123456'; // G = 2016
assert(recall.decodeVinAndCheckRecalls(vinYear2016).decodedYear === 2016, `Year code G decodes to 2016`);

const vinYear2026 = 'KM8KN4AE4TU123456'; // T = 2026
assert(recall.decodeVinAndCheckRecalls(vinYear2026).decodedYear === 2026, `Year code T decodes to 2026`);

const vinYear2030 = 'KM8KN4AE4YU123456'; // Y = 2030
assert(recall.decodeVinAndCheckRecalls(vinYear2030).decodedYear === 2030, `Year code Y decodes to 2030`);

const vinYearUnknown = 'KM8KN4AE4ZU123456'; // Z is not in VIN_YEAR_MAP
const unknownYearRes = recall.decodeVinAndCheckRecalls(vinYearUnknown);
assert(unknownYearRes.valid, `Valid VIN with unknown year code passes validation`);
assert(unknownYearRes.decodedYear === undefined, `Unknown year code returns undefined decodedYear`);

// 1.10 Model Matcher Collision Unit Tests (isModelMatchForCampaign)
assert(recall.isModelMatchForCampaign('아이오닉 5', '아이오닉 5, 아이오닉 6') === true, '아이오닉 5 matches');
assert(recall.isModelMatchForCampaign('아이오닉 6', '아이오닉 5, 아이오닉 6') === true, '아이오닉 6 matches');
assert(recall.isModelMatchForCampaign('아이오닉 5', '코나 일렉트릭, 아이오닉 EV') === false, '아이오닉 5 != 아이오닉 EV');
assert(recall.isModelMatchForCampaign('아이오닉 EV', '아이오닉 5, 아이오닉 6') === false, '아이오닉 EV != 아이오닉 5');
assert(recall.isModelMatchForCampaign('모델 Y', '모델 3, 모델 Y') === true, '모델 Y matches');
assert(recall.isModelMatchForCampaign('모델 Y', '모델 3') === false, '모델 Y != 모델 3');
assert(recall.isModelMatchForCampaign('모델 3', '모델 Y') === false, '모델 3 != 모델 Y');
assert(recall.isModelMatchForCampaign('EV6', 'EV6, EV9') === true, 'EV6 matches');
assert(recall.isModelMatchForCampaign('EV6', 'EV9') === false, 'EV6 != EV9');
assert(recall.isModelMatchForCampaign('EV9', 'EV6') === false, 'EV9 != EV6');


// ============================================================================
// PART 2: SUBSIDY CALCULATOR & TRACKER BOUNDARY TESTS (getSubsidyData.ts)
// ============================================================================
console.log('\n--- [PART 2: Subsidy Calculator & Tracker Boundary Testing] ---');

// 2.1 Price Cap Ratio Boundaries
assert(subsidy.getPriceSubsidyRatio(0) === 1.0, 'MSRP 0 KRW -> 1.0 (100% eligibility)');
assert(subsidy.getPriceSubsidyRatio(54_999_999) === 1.0, 'MSRP 54,999,999 KRW -> 1.0');
assert(subsidy.getPriceSubsidyRatio(55_000_000) === 0.5, 'MSRP 55,000,000 KRW -> 0.5 (50% boundary)');
assert(subsidy.getPriceSubsidyRatio(84_999_999) === 0.5, 'MSRP 84,999,999 KRW -> 0.5');
assert(subsidy.getPriceSubsidyRatio(85_000_000) === 0.0, 'MSRP 85,000,000 KRW -> 0.0 (0% luxury exclusion)');
assert(subsidy.getPriceSubsidyRatio(100_000_000) === 0.0, 'MSRP 100M KRW -> 0.0');
assert(subsidy.getPriceSubsidyRatio(-1_000_000) === 1.0, 'Negative MSRP defaults safely to 1.0 without crash');

// 2.2 Boundary MSRPs in calculateNetSubsidy
const testMsrps = [
  -50_000_000,
  0,
  1,
  10_000_000,
  54_999_999,
  55_000_000,
  84_999_999,
  85_000_000,
  150_000_000,
  10_000_000_000, // 10 Billion KRW
];

for (const msrp of testMsrps) {
  const res = subsidy.calculateNetSubsidy('ioniq-5-2026', 'KR-11', msrp);
  assert(Number.isFinite(res.nationalSubsidyKrw), `National subsidy finite for MSRP ${msrp}`);
  assert(Number.isFinite(res.localSubsidyKrw), `Local subsidy finite for MSRP ${msrp}`);
  assert(Number.isFinite(res.totalSubsidyKrw), `Total subsidy finite for MSRP ${msrp}`);
  assert(Number.isFinite(res.netPurchasePriceKrw), `Net purchase price finite for MSRP ${msrp}`);
  assert(res.netPurchasePriceKrw >= 0, `Net purchase price never negative for MSRP ${msrp}`);
  assert(res.totalSubsidyKrw >= 0, `Total subsidy never negative for MSRP ${msrp}`);
}

// 2.3 Options permutations
const optionPermutations = [
  {},
  { isYouthFirstTimeBuyer: true },
  { isSmallBusinessOrTaxi: true },
  { isMultiChildFamily: true },
  { isOldDieselScrappage: true },
  {
    isYouthFirstTimeBuyer: true,
    isSmallBusinessOrTaxi: true,
    isMultiChildFamily: true,
    isOldDieselScrappage: true,
  },
];

for (const opt of optionPermutations) {
  const res = subsidy.calculateNetSubsidy('ioniq-5-2026', 'KR-11', undefined, opt);
  assert(Number.isFinite(res.additionalGrantsKrw), `Additional grants finite`);
  assert(res.additionalGrantsKrw >= 0, `Additional grants non-negative`);
  assert(res.netPurchasePriceKrw >= 0, `Net purchase price non-negative with options`);
}

// 2.4 Luxury exclusion with options
const luxuryWithOptions = subsidy.calculateNetSubsidy('ioniq-5-2026', 'KR-11', 90_000_000, {
  isYouthFirstTimeBuyer: true,
  isSmallBusinessOrTaxi: true,
  isMultiChildFamily: true,
  isOldDieselScrappage: true,
});
assert(luxuryWithOptions.nationalSubsidyKrw === 0, 'Luxury vehicle receives 0 national subsidy');
assert(luxuryWithOptions.localSubsidyKrw === 0, 'Luxury vehicle receives 0 local subsidy');
assert(luxuryWithOptions.additionalGrantsKrw === 0, 'Luxury vehicle receives 0 percentage-based grants');
assert(luxuryWithOptions.totalSubsidyKrw === 0, 'Luxury vehicle total subsidy is 0');
assert(luxuryWithOptions.netPurchasePriceKrw === 90_000_000, 'Luxury vehicle net price equals MSRP');

// 2.5 Resilient Fallbacks on non-existent IDs
const unknownModelRes = subsidy.calculateNetSubsidy('non-existent-ev-model', 'KR-11');
assert(unknownModelRes.modelId !== undefined, 'Non-existent model falls back to default safely');

const unknownRegionRes = subsidy.calculateNetSubsidy('ioniq-5-2026', 'KR-NON-EXISTENT');
assert(unknownRegionRes.regionId !== undefined, 'Non-existent region falls back to default safely');

const emptyIdsRes = subsidy.calculateNetSubsidy('', '');
assert(emptyIdsRes.modelId !== undefined && emptyIdsRes.regionId !== undefined, 'Empty IDs fall back safely');

// 2.6 All 17 Regions check
const allRegions = subsidy.getAllRegions();
assert(allRegions.length === 17, `Exactly 17 regions loaded`);
for (const reg of allRegions) {
  const calc = subsidy.calculateNetSubsidy('ioniq-5-2026', reg.region_id);
  assert(calc.localSubsidyKrw > 0, `Local subsidy positive for ${reg.name_ko}`);
  assert(calc.depletionRate >= 0, `Depletion rate non-negative for ${reg.name_ko}`);
}


// ============================================================================
// PART 3: DEPRECIATION ENGINE EXTREME INPUTS (getDepreciationData.ts)
// ============================================================================
console.log('\n--- [PART 3: Depreciation Engine Extreme Inputs & Stress Testing] ---');

// 3.1 Extreme Mileage: 0 km, 500,000 km, 5,000,000 km, negative km
const mileageCases = [
  -50000,
  0,
  1,
  15000,
  100000,
  500000,
  1000000,
  5000000,
];

for (const km of mileageCases) {
  const dep = depreciation.calculateDepreciation({
    modelId: 'ioniq-5',
    years: 3.0,
    mileageKm: km,
  });

  assert(Number.isFinite(dep.adjustedResidualPct), `Adjusted residual finite for mileage ${km}km`);
  assert(Number.isFinite(dep.estimatedResidualPriceKrw), `Residual price finite for mileage ${km}km`);
  assert(dep.adjustedResidualPct >= 5.0 && dep.adjustedResidualPct <= 99.0, `Residual clamped 5% - 99% (got ${dep.adjustedResidualPct}%)`);
  assert(dep.estimatedResidualPriceKrw >= 0, `Residual price non-negative for mileage ${km}km`);
}

// 3.2 Extreme Years: negative, 0, fractional, large
const yearCases = [
  -2.0,
  0.0,
  0.0001,
  0.5,
  1.0,
  3.0,
  5.0,
  7.5,
  10.0,
  20.0,
  50.0,
  100.0,
];

for (const yr of yearCases) {
  const dep = depreciation.calculateDepreciation({
    modelId: 'model-3',
    years: yr,
  });

  assert(Number.isFinite(dep.adjustedResidualPct), `Adjusted residual finite for year ${yr}`);
  assert(Number.isFinite(dep.estimatedResidualPriceKrw), `Residual price finite for year ${yr}`);
  assert(dep.adjustedResidualPct >= 5.0 && dep.adjustedResidualPct <= 99.0, `Residual clamped 5% - 99% for year ${yr}`);
}

// 3.3 Extreme MSRP
const msrpCases = [
  0,
  1,
  10_000_000,
  50_000_000,
  1_000_000_000,
  100_000_000_000, // 100 Billion KRW
];

for (const m of msrpCases) {
  const dep = depreciation.calculateDepreciation({
    modelId: 'ioniq-5',
    years: 2.0,
    customPurchasePriceKrw: m,
  });

  assert(Number.isFinite(dep.estimatedResidualPriceKrw), `Residual price finite for custom MSRP ${m}`);
  assert(dep.estimatedResidualPriceKrw >= 0, `Residual price non-negative for custom MSRP ${m}`);
}

// 3.4 Electrochemical Battery Health Simulator Extreme Inputs
const batValidExtremes = [
  { years: 0.1, totalKm: 0, dcfcRatio: 0.0, ambientTempC: 25.0 },
  { years: 10.0, totalKm: 500000, dcfcRatio: 1.0, ambientTempC: 45.0 },
  { years: 15.0, totalKm: 1000000, dcfcRatio: 1.0, ambientTempC: -30.0 },
  { years: 20.0, totalKm: 2000000, dcfcRatio: 2.0, ambientTempC: 60.0 }, // Over-bound DCFC and temp
];

for (const p of batValidExtremes) {
  const health = depreciation.simulateBatteryHealth(p);
  assert(Number.isFinite(health.sohPct), `SoH finite for extreme battery input (got ${health.sohPct}%)`);
  assert(health.sohPct >= 0.0 && health.sohPct <= 100.0, `SoH clamped between 0% and 100%`);
  assert(health.grade !== undefined, `Grade assigned for extreme input: ${health.grade}`);
}

// 3.4.1 EMPIRICAL BUG DETECTION: Negative TotalKm in simulateBatteryHealth
const negKmHealth = depreciation.simulateBatteryHealth({ years: 1.0, totalKm: -10000 });
if (Number.isNaN(negKmHealth.sohPct)) {
  recordBug(
    'BUG-DEPR-01',
    'simulateBatteryHealth evaluates Math.pow(equivalentFullCycles, w) where equivalentFullCycles < 0, resulting in NaN for cyclicLossPct and sohPct, incorrectly defaulting to Pristine GRADE_A.'
  );
}

// 3.5 Subsidy Clawback Schedule Extreme Boundaries
const clawbackMonths = [0, 1, 2, 3, 5.9, 6, 11.9, 12, 17.9, 18, 23.9, 24, 25, 48, 120];
for (const m of clawbackMonths) {
  const cbInter = depreciation.calculateSubsidyClawback(m, 4_000_000, 'inter', 6_500_000);
  assert(Number.isFinite(cbInter.totalClawbackKrw), `Clawback finite for month ${m}`);
  assert(cbInter.totalClawbackKrw >= 0, `Clawback non-negative for month ${m}`);

  if (m >= 24) {
    assert(cbInter.totalClawbackKrw === 0, `After 24 months, clawback must be 0 KRW`);
  }
}

// 3.6 TCO Calculator (Positional arguments & fractional years)
const tcoNormal = depreciation.calculateTcoComparison(20000, 5, 5.2, 0.70, 1998);
assert(Number.isFinite(tcoNormal.totalKm), 'TCO totalKm finite');
assert(Number.isFinite(tcoNormal.evTotalFuelCostKrw), 'TCO EV fuel cost finite');
assert(Number.isFinite(tcoNormal.iceTotalFuelCostKrw), 'TCO ICE fuel cost finite');
assert(Number.isFinite(tcoNormal.totalCumulativeSavingsKrw), 'TCO cumulative savings finite');

// 3.6.1 EMPIRICAL BUG DETECTION: Fractional years in calculateTcoComparison
const tcoFractional = depreciation.calculateTcoComparison(20000, 0.5);
if (tcoFractional.yearlyBreakdown.length === 0 && tcoFractional.totalCumulativeSavingsKrw === 0) {
  recordBug(
    'BUG-DEPR-02',
    'calculateTcoComparison uses `for (let y = 1; y <= years; y++)`, which completely skips calculations when years < 1 (e.g. 0.5 years returns empty yearlyBreakdown and 0 KRW savings).'
  );
}

// 3.7 LFP Battery Chemistry Bonus Jump at Year 3.00
const lfpY299 = depreciation.calculateDepreciation({ modelId: 'model-y-rwd', years: 2.99 });
const lfpY300 = depreciation.calculateDepreciation({ modelId: 'model-y-rwd', years: 3.00 });
const residualDiff = lfpY300.adjustedResidualPct - lfpY299.adjustedResidualPct;
if (residualDiff > 0) {
  recordBug(
    'BUG-DEPR-03',
    `LFP chemistry curve inversion at Year 3.0: residual jumps upward from ${lfpY299.adjustedResidualPct}% at Year 2.99 to ${lfpY300.adjustedResidualPct}% at Year 3.00 due to discrete step +0.01 bonus.`
  );
}


// ============================================================================
// FINAL SUMMARY
// ============================================================================
console.log('\n================================================================');
console.log(`🏁 TEST EXECUTION COMPLETE:`);
console.log(`   Total Assertions: ${stats.total}`);
console.log(`   Passed:           ${stats.passed}`);
console.log(`   Failed:           ${stats.failed}`);
console.log(`   Empirical Bugs Found: ${stats.bugsFound.length}`);
if (stats.bugsFound.length > 0) {
  console.log(`\n🐛 DETECTED CODEBASE DEFECTS / ANOMALIES:`);
  stats.bugsFound.forEach((b) => console.log(`   * ${b}`));
}
console.log('================================================================\n');

if (stats.failed > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
