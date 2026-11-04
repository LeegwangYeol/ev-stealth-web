/**
 * Comprehensive Audit Test Suite for EV Recall Date Sorting, Manufacturer Aggregation,
 * and Completion Rate Computation Safeguards.
 * Verifies both recallCalculations.ts and getRecallData.ts.
 */

import assert from 'node:assert/strict';
import * as recallCalc from '../src/lib/recallCalculations.ts';
import * as getRecall from '../src/lib/getRecallData.ts';

console.log('================================================================');
console.log('🔬 AUDIT VERIFICATION: RECALL CALCULATIONS & DATA ENGINE');
console.log('================================================================\n');

let totalTests = 0;
let passedTests = 0;

function runTest(desc, fn) {
  totalTests++;
  try {
    fn();
    passedTests++;
    console.log(`  ✅ ${desc}`);
  } catch (err) {
    console.error(`  ❌ FAIL: ${desc}`);
    console.error(err);
    process.exitCode = 1;
  }
}

// ============================================================================
// 1. RECALL DATE SORTING & YEAR EXTRACTION EDGE CASES
// ============================================================================
console.log('--- [1. Recall Date Sorting & Year Extraction Edge Cases] ---');

runTest('parseRecallDate handles multiple standard and government formats', () => {
  const d1 = recallCalc.parseRecallDate('2024.03.18');
  assert.equal(d1.getUTCFullYear(), 2024);
  assert.equal(d1.getUTCMonth(), 2); // 0-indexed March
  assert.equal(d1.getUTCDate(), 18);

  const d2 = recallCalc.parseRecallDate('2021-02-24');
  assert.equal(d2.getUTCFullYear(), 2021);
  assert.equal(d2.getUTCMonth(), 1); // Feb
  assert.equal(d2.getUTCDate(), 24);

  const d3 = recallCalc.parseRecallDate('2023/05/19');
  assert.equal(d3.getUTCFullYear(), 2023);

  const d4 = recallCalc.parseRecallDate('20220110');
  assert.equal(d4.getUTCFullYear(), 2022);
});

runTest('parseRecallDate guards against invalid strings and extreme dates', () => {
  assert.equal(recallCalc.parseRecallDate(''), null);
  assert.equal(recallCalc.parseRecallDate('   '), null);
  assert.equal(recallCalc.parseRecallDate('invalid-date'), null);
  assert.equal(recallCalc.parseRecallDate('null'), null);
  assert.equal(recallCalc.parseRecallDate('undefined'), null);
  assert.equal(recallCalc.parseRecallDate('2024.99.99'), null);
  assert.equal(recallCalc.parseRecallDate('2024.13.01'), null);
  assert.equal(recallCalc.parseRecallDate('0000.00.00'), null);
  // Future dates beyond vehicle timeline bound (2040)
  assert.equal(recallCalc.parseRecallDate('2099-01-01'), null);
  // Past dates before automotive EV timeline bound (1990)
  assert.equal(recallCalc.parseRecallDate('1800-01-01'), null);
});

runTest('extractRecallYear extracts years from numbers, strings, and objects', () => {
  assert.equal(recallCalc.extractRecallYear(2024), 2024);
  assert.equal(recallCalc.extractRecallYear('2021 ~ 2024'), 2024);
  assert.equal(recallCalc.extractRecallYear('2024.03.18'), 2024);
  assert.equal(recallCalc.extractRecallYear('MOLIT-2024-0318'), 2024);

  // Campaign object extraction
  const mockCampaign = {
    id: 'RC-2024-HYUNDAI-ICCU',
    campaign_no: 'MOLIT-2024-0318 / NHTSA-24V-868',
    production_date_range: '2021.03.08 ~ 2024.03.04',
    target_model_years: '2021 ~ 2024',
  };
  assert.equal(recallCalc.extractRecallYear(mockCampaign), 2024);
});

runTest('extractRecallYear guards against NaN, negative, and future date anomalies', () => {
  assert.equal(recallCalc.extractRecallYear(NaN), undefined);
  assert.equal(recallCalc.extractRecallYear(Infinity), undefined);
  assert.equal(recallCalc.extractRecallYear(-2022), undefined);
  assert.equal(recallCalc.extractRecallYear(0), undefined);
  assert.equal(recallCalc.extractRecallYear(9999), undefined);
  assert.equal(recallCalc.extractRecallYear('invalid-year'), undefined);
  assert.equal(recallCalc.extractRecallYear('Year 9999 in future'), undefined);
  assert.equal(recallCalc.extractRecallYear(null), undefined);
  assert.equal(recallCalc.extractRecallYear(undefined), undefined);
});

runTest('sortRecallsByDate sorts campaigns descending and ascending deterministically', () => {
  const cOld = {
    id: 'RC-2021-OLD',
    campaign_no: 'MOLIT-2021-0224',
    production_date_range: '2018.01.01 ~ 2020.12.31',
    target_model_years: '2018 ~ 2020',
  };
  const cNew = {
    id: 'RC-2024-NEW',
    campaign_no: 'MOLIT-2024-0814',
    production_date_range: '2022.01.10 ~ 2024.06.30',
    target_model_years: '2022 ~ 2024',
  };
  const cMid = {
    id: 'RC-2023-MID',
    campaign_no: 'MOLIT-2023-0519',
    production_date_range: '2023.01.01 ~ 2023.10.23',
    target_model_years: '2023',
  };
  const cInvalid = {
    id: 'RC-INVALID',
    campaign_no: 'NO-DATE-UNKNOWN',
    production_date_range: 'UNKNOWN',
    target_model_years: 'UNKNOWN',
  };

  const unsorted = [cOld, cInvalid, cNew, cMid];

  // Descending (newest first)
  const desc = recallCalc.sortRecallsByDate(unsorted, 'desc');
  assert.equal(desc[0].id, 'RC-2024-NEW');
  assert.equal(desc[1].id, 'RC-2023-MID');
  assert.equal(desc[2].id, 'RC-2021-OLD');
  assert.equal(desc[3].id, 'RC-INVALID'); // Invalid sorts to the bottom

  // Ascending (oldest first)
  const asc = recallCalc.sortRecallsByDate(unsorted, 'asc');
  assert.equal(asc[0].id, 'RC-2021-OLD');
  assert.equal(asc[1].id, 'RC-2023-MID');
  assert.equal(asc[2].id, 'RC-2024-NEW');
  assert.equal(asc[3].id, 'RC-INVALID');

  // Verify pure function (no mutation)
  assert.equal(unsorted[0].id, 'RC-2021-OLD');
});

runTest('isYearMatchForCampaign strictly guards against NaN, negative numbers, and future dates', () => {
  // NaN must return false
  assert.equal(recallCalc.isYearMatchForCampaign(NaN, '2021 ~ 2024'), false);
  // Negative years must return false
  assert.equal(recallCalc.isYearMatchForCampaign(-2022, '2021 ~ 2024'), false);
  // Year 0 must return false
  assert.equal(recallCalc.isYearMatchForCampaign(0, '2021 ~ 2024'), false);
  // Extreme future year 9999 must return false
  assert.equal(recallCalc.isYearMatchForCampaign(9999, '2021 ~ 2024'), false);

  // Normal matching
  assert.equal(recallCalc.isYearMatchForCampaign(2022, '2021 ~ 2024'), true);
  assert.equal(recallCalc.isYearMatchForCampaign(2020, '2021 ~ 2024'), false);
  assert.equal(recallCalc.isYearMatchForCampaign(2022, '2021, 2022, 2023'), true);

  // Open-ended future ranges
  assert.equal(recallCalc.isYearMatchForCampaign(2024, '2022 ~ 현재'), true);
  assert.equal(recallCalc.isYearMatchForCampaign(2021, '2022 ~ 현재'), false);

  // Reverse ranges
  assert.equal(recallCalc.isYearMatchForCampaign(2022, '2024 ~ 2021'), true);

  // Undefined/null year (unspecified year check) matches all
  assert.equal(recallCalc.isYearMatchForCampaign(undefined, '2021 ~ 2024'), true);
});

// ============================================================================
// 2. MANUFACTURER AGGREGATION & CASING DISCREPANCIES
// ============================================================================
console.log('\n--- [2. Manufacturer Aggregation & Casing Discrepancies] ---');

runTest('normalizeManufacturer handles Korean/English aliases and casing differences', () => {
  assert.equal(recallCalc.normalizeManufacturer('Hyundai'), '현대자동차');
  assert.equal(recallCalc.normalizeManufacturer('hyundai'), '현대자동차');
  assert.equal(recallCalc.normalizeManufacturer('HYUNDAI'), '현대자동차');
  assert.equal(recallCalc.normalizeManufacturer('현대'), '현대자동차');
  assert.equal(recallCalc.normalizeManufacturer('현대차'), '현대자동차');
  assert.equal(recallCalc.normalizeManufacturer('현대자동차'), '현대자동차');

  assert.equal(recallCalc.normalizeManufacturer('Kia'), '기아');
  assert.equal(recallCalc.normalizeManufacturer('kia'), '기아');
  assert.equal(recallCalc.normalizeManufacturer('KIA'), '기아');

  assert.equal(recallCalc.normalizeManufacturer('Tesla'), '테슬라');
  assert.equal(recallCalc.normalizeManufacturer('tesla'), '테슬라');

  assert.equal(recallCalc.normalizeManufacturer('Mercedes'), '메르세데스-벤츠');
  assert.equal(recallCalc.normalizeManufacturer('benz'), '메르세데스-벤츠');
  assert.equal(recallCalc.normalizeManufacturer('Mercedes-Benz'), '메르세데스-벤츠');
  assert.equal(recallCalc.normalizeManufacturer('벤츠'), '메르세데스-벤츠');

  assert.equal(recallCalc.normalizeManufacturer('BMW'), 'BMW');
  assert.equal(recallCalc.normalizeManufacturer('bmw'), 'BMW');

  assert.equal(recallCalc.normalizeManufacturer('BYD'), 'BYD');
  assert.equal(recallCalc.normalizeManufacturer('byd'), 'BYD');

  assert.equal(recallCalc.normalizeManufacturer('Chevy'), '쉐보레');
  assert.equal(recallCalc.normalizeManufacturer('Chevrolet'), '쉐보레');

  assert.equal(recallCalc.normalizeManufacturer('Polestar'), '폴스타');
  assert.equal(recallCalc.normalizeManufacturer('Porsche'), '포르쉐');

  // Edge cases
  assert.equal(recallCalc.normalizeManufacturer(''), '');
  assert.equal(recallCalc.normalizeManufacturer(null), '');
  assert.equal(recallCalc.normalizeManufacturer('CustomBrand'), 'CustomBrand');
});

runTest('checkRecallsByModel seamlessly matches English and Korean manufacturer queries', () => {
  const db = getRecall.getRecallDatabase();

  // 1. Querying with English 'Hyundai' matches '현대자동차'
  const hyundaiRes = recallCalc.checkRecallsByModel('Hyundai', '아이오닉 5', 2022, db);
  assert.equal(hyundaiRes.valid, true);
  assert.ok(hyundaiRes.recalls.length >= 1, 'Hyundai query matches ICCU recall');
  assert.ok(hyundaiRes.recalls.some((r) => r.id === 'RC-2024-HYUNDAI-ICCU'));
  assert.equal(hyundaiRes.decodedCountry, '대한민국');

  // 2. Querying with shorthand '현대'
  const hyundaiShortRes = recallCalc.checkRecallsByModel('현대', '아이오닉 5', 2022, db);
  assert.equal(hyundaiShortRes.valid, true);
  assert.ok(hyundaiShortRes.recalls.length >= 1);

  // 3. Querying with English 'Tesla' matches '테슬라'
  const teslaRes = recallCalc.checkRecallsByModel('Tesla', '모델 Y', 2022, db);
  assert.equal(teslaRes.valid, true);
  assert.ok(teslaRes.recalls.some((r) => r.id === 'RC-2024-TESLA-AUTOPILOT'));

  // 4. Querying with English 'Kia' matches '기아'
  const kiaRes = recallCalc.checkRecallsByModel('Kia', 'EV6', 2022, db);
  assert.equal(kiaRes.valid, true);
  assert.ok(kiaRes.recalls.some((r) => r.id === 'RC-2024-KIA-ICCU'));

  // 5. Querying with 'Benz' matches '메르세데스-벤츠'
  const benzRes = recallCalc.checkRecallsByModel('Benz', 'EQE 350+', 2023, db);
  assert.equal(benzRes.valid, true);
  assert.ok(benzRes.recalls.some((r) => r.id === 'RC-2024-BENZ-EQE-FARASIS'));
});

runTest('getModelsForBrand returns models across casing and alias differences', () => {
  const db = getRecall.getRecallDatabase();

  const hyundaiModels = recallCalc.getModelsForBrand('Hyundai', db);
  assert.ok(hyundaiModels.length > 0, 'Hyundai returns models');
  assert.ok(hyundaiModels.includes('아이오닉 5'));

  const teslaModels = recallCalc.getModelsForBrand('tesla', db);
  assert.ok(teslaModels.length > 0, 'Tesla returns models');
  assert.ok(teslaModels.includes('모델 Y'));

  const kiaModels = recallCalc.getModelsForBrand('KIA', db);
  assert.ok(kiaModels.length > 0, 'KIA returns models');
  assert.ok(kiaModels.includes('EV6'));
});

runTest('getDistinctBrands returns normalized deduplicated brand list', () => {
  const db = getRecall.getRecallDatabase();
  const brands = recallCalc.getDistinctBrands(db);

  assert.ok(brands.includes('현대자동차'));
  assert.ok(brands.includes('기아'));
  assert.ok(brands.includes('테슬라'));
  assert.ok(brands.includes('메르세데스-벤츠'));
  assert.ok(brands.includes('BMW'));

  // No duplicate casing or raw aliases
  assert.ok(!brands.includes('hyundai'));
  assert.ok(!brands.includes('Tesla'));
});

// ============================================================================
// 3. COMPLETION RATE COMPUTATION SAFEGUARDS (DIVISION BY ZERO)
// ============================================================================
console.log('\n--- [3. Completion Rate Computation Safeguards (Division by Zero)] ---');

runTest('calculateRecallCompletionRate strictly guards against division by zero', () => {
  // Zero total units -> MUST NOT throw or produce NaN / Infinity
  assert.equal(recallCalc.calculateRecallCompletionRate(100, 0), 0);
  assert.equal(recallCalc.calculateRecallCompletionRate(0, 0), 0);

  // Negative values
  assert.equal(recallCalc.calculateRecallCompletionRate(50, -100), 0);
  assert.equal(recallCalc.calculateRecallCompletionRate(-50, 100), 0);

  // NaN and Infinity
  assert.equal(recallCalc.calculateRecallCompletionRate(NaN, 100), 0);
  assert.equal(recallCalc.calculateRecallCompletionRate(50, NaN), 0);
  assert.equal(recallCalc.calculateRecallCompletionRate(50, Infinity), 0);
  assert.equal(recallCalc.calculateRecallCompletionRate(Infinity, 100), 0);

  // Normal calculations
  assert.equal(recallCalc.calculateRecallCompletionRate(500, 1000), 50.0);
  assert.equal(recallCalc.calculateRecallCompletionRate(333, 1000), 33.3);

  // Overflow clamp
  assert.equal(recallCalc.calculateRecallCompletionRate(1500, 1000), 100.0);
});

runTest('calculateCampaignResolutionRate guards against zero campaigns', () => {
  assert.equal(recallCalc.calculateCampaignResolutionRate(0, 0), 0);
  assert.equal(recallCalc.calculateCampaignResolutionRate(5, 0), 0);
  assert.equal(recallCalc.calculateCampaignResolutionRate(3, 12), 25.0);
  assert.equal(recallCalc.calculateCampaignResolutionRate(12, 12), 100.0);
});

runTest('aggregateRecallsByManufacturer aggregates campaigns with completion rate safeguards', () => {
  const mockRecalls = [
    {
      id: 'R1',
      brand: 'Hyundai',
      status: 'RESOLVED',
      affected_kdm_units: 50000,
      risk_level: 'LOSS_OF_POWER',
    },
    {
      id: 'R2',
      brand: '현대',
      status: 'ACTIVE',
      affected_kdm_units: 30000,
      risk_level: 'FIRE_HAZARD',
    },
    {
      id: 'R3',
      brand: 'Tesla',
      status: 'ACTIVE',
      affected_kdm_units: 10000,
      risk_level: 'SOFTWARE_REGULATION',
    },
    {
      id: 'R4',
      brand: '테슬라',
      status: 'RESOLVED',
      affected_kdm_units: 15000,
      risk_level: 'SOFTWARE_REGULATION',
    },
  ];

  const summary = recallCalc.aggregateRecallsByManufacturer(mockRecalls);

  // Both 'Hyundai' and '현대' aggregated under '현대자동차'
  assert.ok(summary['현대자동차'] !== undefined);
  assert.equal(summary['현대자동차'].totalCampaigns, 2);
  assert.equal(summary['현대자동차'].activeCampaigns, 1);
  assert.equal(summary['현대자동차'].resolvedCampaigns, 1);
  assert.equal(summary['현대자동차'].fireHazards, 1);
  assert.equal(summary['현대자동차'].lossOfPower, 1);
  assert.equal(summary['현대자동차'].affectedUnits, 80000);
  assert.equal(summary['현대자동차'].completionRatePct, 50.0);

  // Both 'Tesla' and '테슬라' aggregated under '테슬라'
  assert.ok(summary['테슬라'] !== undefined);
  assert.equal(summary['테슬라'].totalCampaigns, 2);
  assert.equal(summary['테슬라'].activeCampaigns, 1);
  assert.equal(summary['테슬라'].resolvedCampaigns, 1);
  assert.equal(summary['테슬라'].completionRatePct, 50.0);
});

runTest('calculateRecallKPIs aggregates brandDistribution canonically with zero division guards', () => {
  const db = getRecall.getRecallDatabase();
  const kpis = recallCalc.calculateRecallKPIs(db);

  assert.ok(kpis.totalCampaigns > 0);
  assert.ok(Number.isFinite(kpis.otaRemedyRatePct));
  assert.ok(kpis.otaRemedyRatePct >= 0 && kpis.otaRemedyRatePct <= 100);
  assert.ok(Number.isFinite(kpis.campaignResolutionRatePct));

  // Verify brandDistribution uses canonical names
  assert.ok(kpis.brandDistribution['현대자동차'] > 0);
  assert.ok(kpis.brandDistribution['기아'] > 0);
  assert.ok(kpis.brandDistribution['테슬라'] > 0);
  assert.equal(kpis.brandDistribution['Hyundai'], undefined);
  assert.equal(kpis.brandDistribution['Tesla'], undefined);

  // Test empty database (division by zero safeguard in calculateRecallKPIs)
  const emptyKpis = recallCalc.calculateRecallKPIs({
    metadata: { version: '1.0.0', updated_at: '', total_campaigns: 0, total_affected_vehicles_kdm: 0, active_fire_campaigns: 0, ota_remedy_rate_pct: 0 },
    vin_prefixes: [],
    battery_profiles: [],
    recalls: [],
  });
  assert.equal(emptyKpis.totalCampaigns, 0);
  assert.equal(emptyKpis.otaRemedyRatePct, 0);
  assert.equal(emptyKpis.campaignResolutionRatePct, 0);
  assert.equal(emptyKpis.totalAffectedVehiclesKdm, 0);
});

// ============================================================================
// 4. PARITY CHECK: getRecallData.ts EXPORTS & PARITY
// ============================================================================
console.log('\n--- [4. Parity Verification between recallCalculations and getRecallData] ---');

runTest('getRecallData exports all new functions with identical behavior', () => {
  assert.equal(typeof getRecall.normalizeManufacturer, 'function');
  assert.equal(typeof getRecall.parseRecallDate, 'function');
  assert.equal(typeof getRecall.extractRecallYear, 'function');
  assert.equal(typeof getRecall.sortRecallsByDate, 'function');
  assert.equal(typeof getRecall.calculateRecallCompletionRate, 'function');
  assert.equal(typeof getRecall.calculateCampaignResolutionRate, 'function');
  assert.equal(typeof getRecall.aggregateRecallsByManufacturer, 'function');

  // Functional equivalence test
  assert.equal(getRecall.normalizeManufacturer('Hyundai'), recallCalc.normalizeManufacturer('Hyundai'));
  assert.equal(getRecall.calculateRecallCompletionRate(50, 0), recallCalc.calculateRecallCompletionRate(50, 0));
  assert.equal(getRecall.isYearMatchForCampaign(NaN, '2021 ~ 2024'), recallCalc.isYearMatchForCampaign(NaN, '2021 ~ 2024'));
});

console.log('\n================================================================');
console.log(`🏁 RECALL AUDIT SUITE FINISHED: ${passedTests}/${totalTests} PASSED`);
console.log('================================================================\n');

if (passedTests !== totalTests) {
  process.exit(1);
}
