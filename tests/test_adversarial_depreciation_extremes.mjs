/**
 * tests/test_adversarial_depreciation_extremes.mjs
 * Comprehensive empirical stress harness for extreme inputs, boundary conditions,
 * and mathematical robustness on the EV depreciation & TCO engine.
 */

import * as engine from '../src/lib/getDepreciationData.ts';

const db = engine.getDepreciationDatabase();
console.log(`[DEP HARNESS] Loaded database with ${db.models.length} models, ${db.battery_replacement_costs.length} battery tiers.`);

const suiteResults = {
  totalTests: 0,
  passed: 0,
  failed: 0,
  findings: []
};

function assert(condition, message, metadata = {}) {
  suiteResults.totalTests++;
  if (condition) {
    suiteResults.passed++;
  } else {
    suiteResults.failed++;
    suiteResults.findings.push({ message, metadata });
    console.error(`[FAIL] ${message}`, metadata);
  }
}

// ---------------------------------------------------------
// 1. EXTREME MILEAGE INPUTS (0 km, 500,000 km, 1,000,000 km, negative)
// ---------------------------------------------------------
console.log('[TEST GROUP 1] Testing extreme mileage inputs...');

const testMileages = [
  0,
  1,
  500,
  15000,
  50000,
  100000,
  200000,
  500000,
  1000000,
  5000000,
  -5000 // adversarial negative mileage
];

for (const model of db.models) {
  for (const km of testMileages) {
    const res = engine.calculateDepreciation({
      modelId: model.id,
      years: 3.0,
      mileageKm: km
    });

    assert(!Number.isNaN(res.adjustedResidualPct), `adjustedResidualPct must not be NaN for ${model.id} at ${km} km`, { model: model.id, km, res });
    assert(Number.isFinite(res.adjustedResidualPct), `adjustedResidualPct must be finite for ${model.id} at ${km} km`, { model: model.id, km, res });
    assert(!Number.isNaN(res.estimatedResidualPriceKrw), `estimatedResidualPriceKrw must not be NaN at ${km} km`);
    assert(res.adjustedResidualPct >= 5.0, `Residual floor must be at least 5.0% even at extreme mileage ${km} km`, { res: res.adjustedResidualPct });
    assert(res.adjustedResidualPct <= 99.0, `Residual ceiling must not exceed 99.0% even at 0 or negative mileage`, { res: res.adjustedResidualPct });
    assert(res.estimatedResidualPriceKrw >= 0, `Residual price must be non-negative`, { price: res.estimatedResidualPriceKrw });
    assert(res.depreciationAmountKrw >= 0, `Depreciation amount must be non-negative`, { dep: res.depreciationAmountKrw });
  }
}

// Verify high mileage monotonicity (500,000 km vs 15,000 km)
for (const model of db.models) {
  const normal = engine.calculateDepreciation({ modelId: model.id, years: 3.0, mileageKm: 45000 });
  const extreme = engine.calculateDepreciation({ modelId: model.id, years: 3.0, mileageKm: 500000 });
  assert(
    extreme.adjustedResidualPct <= normal.adjustedResidualPct,
    `500,000 km residual (${extreme.adjustedResidualPct}%) must be <= 45,000 km residual (${normal.adjustedResidualPct}%) for ${model.id}`
  );
}

// ---------------------------------------------------------
// 2. EXTREME PURCHASE PRICES (0 KRW, 1 KRW, 100 Billion KRW, negative)
// ---------------------------------------------------------
console.log('[TEST GROUP 2] Testing extreme purchase prices...');

const testPrices = [
  0,
  1,
  1000,
  10000000,
  60000000,
  100000000,
  1000000000,      // 1 billion KRW
  100000000000,    // 100 billion KRW (extreme luxury hypercar)
  -50000000        // negative price
];

for (const price of testPrices) {
  const res = engine.calculateDepreciation({
    modelId: 'ioniq-5',
    years: 3.0,
    customPurchasePriceKrw: price
  });

  assert(!Number.isNaN(res.estimatedResidualPriceKrw), `estimatedResidualPriceKrw must not be NaN for price ${price}`);
  assert(!Number.isNaN(res.depreciationAmountKrw), `depreciationAmountKrw must not be NaN for price ${price}`);
  
  if (price === 0) {
    assert(res.estimatedResidualPriceKrw === 0, 'Zero purchase price results in 0 residual price');
    assert(res.depreciationAmountKrw === 0, 'Zero purchase price results in 0 depreciation amount');
  }

  if (price > 0) {
    assert(res.estimatedResidualPriceKrw > 0, `Positive purchase price yields positive residual price`);
    assert(res.estimatedResidualPriceKrw <= price, `Residual price must be <= purchase price`);
  }
}

// ---------------------------------------------------------
// 3. EXTREME TEMPERATURES & FAST CHARGING BATTERY SOH
// ---------------------------------------------------------
console.log('[TEST GROUP 3] Testing extreme battery degradation conditions...');

const testTemps = [-50, -30, -10, 0, 25, 45, 60, 80]; // extreme sub-zero to extreme heat
const testDcfc = [-0.5, 0.0, 0.2, 0.5, 0.8, 1.0, 1.5, 2.0]; // includes out-of-bounds ratios

for (const temp of testTemps) {
  for (const dcfc of testDcfc) {
    const bRes = engine.simulateBatteryHealth({
      modelId: 'ev6',
      years: 4.0,
      totalKm: 120000,
      ambientTempC: temp,
      dcfcRatio: dcfc
    });

    assert(!Number.isNaN(bRes.sohPct), `sohPct must not be NaN at temp=${temp}, dcfc=${dcfc}`);
    assert(bRes.sohPct >= 0 && bRes.sohPct <= 100, `sohPct must be between 0 and 100% (got ${bRes.sohPct})`);
    assert(!Number.isNaN(bRes.calendarLossPct), `calendarLossPct must not be NaN at temp=${temp}`);
    assert(!Number.isNaN(bRes.cyclicLossPct), `cyclicLossPct must not be NaN at temp=${temp}`);
    assert(typeof bRes.grade === 'string', `Grade must be a valid string`);
    assert(bRes.replacementCostEstimate.totalNewInstalledKrw > 0, 'Replacement cost must be positive');
  }
}

// Unknown battery chemistry fallback
const unknownChemRes = engine.simulateBatteryHealth({
  chemistry: 'NON_EXISTENT_SODIUM_GRAPHENE',
  years: 3.0,
  totalKm: 45000
});
assert(!Number.isNaN(unknownChemRes.sohPct), 'Unknown chemistry must not produce NaN');
assert(unknownChemRes.chemistry === 'NCM_811', 'Unknown chemistry safely defaults to NCM_811', unknownChemRes);

// ---------------------------------------------------------
// 4. STATUTORY SUBSIDY CLAWBACK SCHEDULE BOUNDARIES
// ---------------------------------------------------------
console.log('[TEST GROUP 4] Testing subsidy clawback boundary conditions...');

const testMonths = [-5, 0, 0.5, 2.9, 3.0, 5.9, 6.0, 11.9, 12.0, 17.9, 18.0, 23.9, 24.0, 24.1, 36.0, 60.0];

for (const m of testMonths) {
  for (const transfer of ['intra', 'inter', 'export']) {
    const cb = engine.calculateSubsidyClawback(m, 4000000, transfer, 6500000);
    
    assert(!Number.isNaN(cb.totalClawbackKrw), `totalClawbackKrw must not be NaN at ${m} months`);
    assert(cb.totalClawbackKrw >= 0, `totalClawbackKrw must be non-negative at ${m} months`);

    if (m >= 24) {
      assert(cb.isExempt === true, `At ${m} months (>= 24), clawback must be fully EXEMPT`);
      assert(cb.totalClawbackKrw === 0, `At ${m} months, total clawback amount must be 0 KRW`);
      assert(cb.statutoryClawbackRate === 0, `At ${m} months, statutory rate must be 0`);
    }

    if (transfer === 'intra') {
      assert(cb.isExempt === true, `Intra-city transfer must be EXEMPT regardless of month (${m}m)`);
      assert(cb.totalClawbackKrw === 0, `Intra-city transfer clawback must be 0 KRW (${m}m)`);
    }

    if (transfer === 'inter' && m < 24 && m >= 0) {
      assert(cb.nationalClawbackKrw === 0, `Inter-city transfer MUST NOT claw back national subsidy`);
      assert(cb.localClawbackKrw >= 0, `Local clawback must be >= 0`);
    }

    if (transfer === 'export' && m < 24 && m >= 0) {
      assert(cb.nationalClawbackKrw > 0, `Overseas export MUST claw back national subsidy if < 24 months`);
      assert(cb.localClawbackKrw > 0, `Overseas export MUST claw back local subsidy if < 24 months`);
    }
  }
}

// ---------------------------------------------------------
// 5. 5-YEAR TCO BOUNDARY TESTING
// ---------------------------------------------------------
console.log('[TEST GROUP 5] Testing TCO calculator extreme bounds...');

const extremeKmList = [0, 500, 15000, 100000, 500000];
const extremeYearsList = [0.1, 1, 3, 5, 10];

for (const km of extremeKmList) {
  for (const yr of extremeYearsList) {
    const tco = engine.calculateTcoComparison(km, yr);
    assert(!Number.isNaN(tco.totalCumulativeSavingsKrw), `TCO savings must not be NaN at ${km} km, ${yr} yrs`);
    assert(!Number.isNaN(tco.fuelSavingsKrw), `Fuel savings must not be NaN`);
    assert(!Number.isNaN(tco.taxSavingsKrw), `Tax savings must not be NaN`);
    assert(tco.yearlyBreakdown.length >= 1, `Yearly breakdown has at least 1 entry`);
    for (const row of tco.yearlyBreakdown) {
      assert(!Number.isNaN(row.cumulativeNetSavingsKrw), `Yearly cumulative savings must not be NaN`);
    }
  }
}

console.log('\n======================================================');
console.log(`[DEP HARNESS FINISHED] Total tests: ${suiteResults.totalTests}`);
console.log(`Passed: ${suiteResults.passed}, Failed: ${suiteResults.failed}`);
console.log(`Findings count: ${suiteResults.findings.length}`);
console.log('======================================================');

if (suiteResults.failed > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
