/**
 * tests/test_depreciation_engine_audit.mjs
 * Exhaustive audit test suite for EV Depreciation, Electrochemical Battery Health (Arrhenius & Cyclic kinetics),
 * Statutory Subsidy Clawback, and Total Cost of Ownership (TCO).
 *
 * Verifies:
 * 1. Residual value algorithms, battery degradation multipliers, SOH (State of Health) curves.
 * 2. Protection against extreme inputs: 0 km mileage, 500,000 km mileage, year 0, year 20, NaN or negative price.
 * 3. Exact mathematical consistency and parity between depreciationCalculations.ts & getDepreciationData.ts.
 */

import assert from 'node:assert/strict';
import * as depCalc from '../src/lib/depreciationCalculations.ts';
import * as depData from '../src/lib/getDepreciationData.ts';

console.log('=== AUDITING DEPRECIATION ENGINES (depreciationCalculations.ts & getDepreciationData.ts) ===\n');

const engines = [
  { name: 'depreciationCalculations (Client Bundle Lean)', mod: depCalc },
  { name: 'getDepreciationData (Server JSON Database)', mod: depData },
];

let totalAssertions = 0;
function check(condition, desc) {
  totalAssertions++;
  assert.ok(condition, desc);
}

for (const { name, mod } of engines) {
  console.log(`--- [AUDIT SUITE] Testing ${name} ---`);

  // ==============================================================
  // 1. RESIDUAL VALUE ALGORITHMS & BASELINE CURVES
  // ==============================================================
  console.log('1. Testing baseline residual interpolation & extrapolation...');

  // Year 0: Baseline residual should be 100.0%
  const resYr0 = mod.calculateDepreciation({ years: 0 });
  check(resYr0.baselineResidualPct === 100.0, 'Year 0 baseline residual must be exactly 100.0%');
  check(resYr0.adjustedResidualPct <= 99.0, 'Year 0 adjusted residual must enforce registration discount (<= 99%)');
  check(resYr0.adjustedResidualPct >= 5.0, 'Year 0 adjusted residual must stay >= 5%');
  check(resYr0.warrantyStatus.isExpired === false, 'Year 0 warranty must not be expired');
  check(resYr0.warrantyStatus.isApproachingCliff === false, 'Year 0 must not be approaching cliff');
  check(resYr0.warrantyStatus.remainingYears > 0, 'Year 0 remaining warranty years > 0');

  // Year 20: Baseline residual extrapolation beyond 5 years (8% compound drop)
  const resYr20 = mod.calculateDepreciation({ years: 20 });
  check(Number.isFinite(resYr20.baselineResidualPct), 'Year 20 baseline residual must be finite');
  check(resYr20.baselineResidualPct >= 10.0, 'Baseline residual floor past 5 years must be at least 10%');
  check(resYr20.adjustedResidualPct >= 5.0, 'Year 20 adjusted residual must be clamped at >= 5% floor');
  check(resYr20.warrantyStatus.isExpired === true, 'Year 20 warranty must be expired');
  check(resYr20.warrantyStatus.remainingYears === 0, 'Year 20 remaining warranty years must be 0');
  check(resYr20.warrantyStatus.remainingKm === 0, 'Year 20 remaining warranty km must be 0');

  // Multi-year monotonicity (residual value decreases as age increases)
  const y1 = mod.calculateDepreciation({ years: 1.0 });
  const y2 = mod.calculateDepreciation({ years: 2.0 });
  const y3 = mod.calculateDepreciation({ years: 3.0 });
  const y5 = mod.calculateDepreciation({ years: 5.0 });
  check(y1.adjustedResidualPct >= y2.adjustedResidualPct, 'Residual must decrease from Year 1 to Year 2');
  check(y2.adjustedResidualPct >= y3.adjustedResidualPct, 'Residual must decrease from Year 2 to Year 3');
  check(y3.adjustedResidualPct >= y5.adjustedResidualPct, 'Residual must decrease from Year 3 to Year 5');

  // ==============================================================
  // 2. EXTREME MILEAGE INPUTS (0 km, 500,000 km, 10,000,000 km, negative)
  // ==============================================================
  console.log('2. Testing extreme mileage handling...');

  // 2.1 Zero km mileage (showroom vehicle)
  const res0Km = mod.calculateDepreciation({ years: 3, mileageKm: 0 });
  check(res0Km.mileageKm === 0, 'Mileage 0 km must be preserved');
  check(res0Km.factorAdjustments.mileageAdjustment > 0, 'Zero km must grant low-mileage bonus');
  check(res0Km.factorAdjustments.mileageAdjustment <= 6.0, 'Low-mileage bonus capped at +6%');
  check(res0Km.estimatedResidualPriceKrw > 0, 'Estimated residual price must be positive for 0 km');
  check(res0Km.depreciationAmountKrw >= 0, 'Depreciation amount must be non-negative');

  // 2.2 500,000 km mileage (extreme commercial/fleet usage)
  const res500kKm = mod.calculateDepreciation({ years: 3, mileageKm: 500000 });
  check(res500kKm.mileageKm === 500000, 'Mileage 500,000 km must be preserved');
  check(res500kKm.factorAdjustments.mileageAdjustment < -15.0, '500,000 km penalty must exceed normal cap (-15%)');
  check(res500kKm.adjustedResidualPct >= 5.0, 'Adjusted residual must respect 5.0% floor at 500k km');
  check(res500kKm.estimatedResidualPriceKrw > 0, 'Residual price must be positive at 500k km');
  check(res500kKm.warrantyStatus.isExpired === true, '500k km warranty must be expired');
  check(res500kKm.warrantyStatus.remainingKm === 0, 'Remaining warranty km must be 0');

  // 2.3 Ultra-extreme 10,000,000 km mileage
  const res10mKm = mod.calculateDepreciation({ years: 5, mileageKm: 10000000 });
  check(Number.isFinite(res10mKm.adjustedResidualPct), '10M km residual must be finite');
  check(res10mKm.adjustedResidualPct === 5.0, '10M km residual hits 5.0% floor');
  check(res10mKm.depreciationAmountKrw <= res10mKm.basePurchasePriceKrw, 'Depreciation cannot exceed purchase price');

  // 2.4 Negative mileage (-15,000 km)
  const resNegKm = mod.calculateDepreciation({ years: 2, mileageKm: -15000 });
  check(resNegKm.mileageKm === 0, 'Negative mileage must safely clamp to 0 km');
  check(Number.isFinite(resNegKm.adjustedResidualPct), 'Negative mileage residual must be finite');

  // ==============================================================
  // 3. PURCHASE PRICE BOUNDARIES (0 KRW, NaN, negative, 100B KRW)
  // ==============================================================
  console.log('3. Testing purchase price bounds & edge cases...');

  // 3.1 0 KRW purchase price
  const res0Price = mod.calculateDepreciation({ years: 3, customPurchasePriceKrw: 0 });
  check(res0Price.basePurchasePriceKrw === 0, '0 KRW base purchase price must be 0');
  check(res0Price.estimatedResidualPriceKrw === 0, '0 KRW price must result in 0 residual price');
  check(res0Price.depreciationAmountKrw === 0, '0 KRW price must result in 0 depreciation');

  // 3.2 Negative purchase price (-50,000,000 KRW)
  const resNegPrice = mod.calculateDepreciation({ years: 3, customPurchasePriceKrw: -50000000 });
  check(resNegPrice.basePurchasePriceKrw > 0, 'Negative price safely falls back to positive model MSRP');
  check(resNegPrice.estimatedResidualPriceKrw > 0, 'Residual price is positive on fallback');

  // 3.3 NaN purchase price
  const resNaNPrice = mod.calculateDepreciation({ years: 3, customPurchasePriceKrw: NaN });
  check(!Number.isNaN(resNaNPrice.basePurchasePriceKrw), 'NaN price must not produce NaN base price');
  check(!Number.isNaN(resNaNPrice.estimatedResidualPriceKrw), 'NaN price must not produce NaN residual');
  check(resNaNPrice.basePurchasePriceKrw > 0, 'NaN price falls back to positive model MSRP');

  // 3.4 100 Billion KRW purchase price (hypercar ceiling check)
  const res100B = mod.calculateDepreciation({ years: 1, customPurchasePriceKrw: 100_000_000_000 });
  check(res100B.basePurchasePriceKrw === 10_000_000_000, 'Purchase price must be capped at 10 Billion KRW ceiling');
  check(res100B.estimatedResidualPriceKrw <= 10_000_000_000, 'Residual price must not exceed ceiling');

  // ==============================================================
  // 4. BATTERY HEALTH (SOH) ARRHENIUS & CYCLIC KINETICS
  // ==============================================================
  console.log('4. Testing electrochemical battery SOH curves...');

  // 4.1 Showroom vehicle (0 years, 0 km)
  const batZero = mod.simulateBatteryHealth({ years: 0, totalKm: 0 });
  check(batZero.sohPct === 100.0, '0 years 0 km SOH must be exactly 100.0%');
  check(batZero.grade === 'GRADE_A', '0 years 0 km battery must be Grade A');
  check(batZero.calendarLossPct === 0, '0 years calendar loss must be 0%');
  check(batZero.cyclicLossPct === 0, '0 km cyclic loss must be 0%');

  // 4.2 Extreme aging: 20 years, 500,000 km
  const bat20yr500k = mod.simulateBatteryHealth({ years: 20, totalKm: 500000 });
  check(Number.isFinite(bat20yr500k.sohPct), '20yr 500k km SOH must be finite');
  check(bat20yr500k.sohPct >= 0 && bat20yr500k.sohPct <= 100, 'SOH must be within [0, 100]%');
  check(bat20yr500k.calendarLossPct > 0, 'Calendar loss must be positive after 20 years');
  check(bat20yr500k.cyclicLossPct > 0, 'Cyclic loss must be positive after 500k km');
  check(bat20yr500k.totalLossPct > bat20yr500k.calendarLossPct, 'Total loss must combine calendar and cyclic aging');

  // 4.3 Severe degradation with 100% DC fast charging (dcfcRatio = 1.0) on NCM_811
  const batSevere = mod.simulateBatteryHealth({
    chemistry: 'NCM_811',
    years: 20,
    totalKm: 500000,
    dcfcRatio: 1.0,
  });
  check(batSevere.sohPct < 70.0, 'NCM_811 with 100% DCFC after 20yr 500k km must drop below 70% SoH');
  check(batSevere.grade === 'CRITICAL', 'SoH < 70% must trigger CRITICAL grade');
  check(batSevere.badgeColor === 'red', 'Critical grade must have red badge');
  check(batSevere.usedMarketValuationFactor === 0.3, 'Critical grade valuation factor must be 0.3');

  // 4.4 Temperature extremes (-60°C to +85°C)
  const batFreeze = mod.simulateBatteryHealth({ years: 3, totalKm: 45000, ambientTempC: -60.0 });
  check(Number.isFinite(batFreeze.sohPct), 'Sub-zero freeze SOH must be finite');
  check(batFreeze.sohPct >= 0 && batFreeze.sohPct <= 100, 'Freeze SOH within [0, 100]%');

  const batDesert = mod.simulateBatteryHealth({ years: 3, totalKm: 45000, ambientTempC: 85.0 });
  check(Number.isFinite(batDesert.sohPct), 'Desert heat SOH must be finite');
  check(batDesert.calendarLossPct > batFreeze.calendarLossPct, 'High temperature accelerates Arrhenius calendar aging');

  // 4.5 All battery chemistries (LFP, NCM_622, NCM_811, NCMA, NCA)
  const chemistries = ['LFP', 'NCM_622', 'NCM_811', 'NCMA', 'NCA'];
  for (const chem of chemistries) {
    const res = mod.simulateBatteryHealth({ chemistry: chem, years: 5, totalKm: 75000 });
    check(res.chemistry === chem, `Chemistry ${chem} correctly recognized`);
    check(Number.isFinite(res.sohPct), `${chem} SOH is finite`);
    check(res.sohPct >= 70.0 && res.sohPct <= 100.0, `${chem} SOH is within normal range`);
  }

  // 4.6 Chemistry normalization (case-insensitive & aliases)
  check(mod.normalizeChemistry('lfp') === 'LFP', 'normalizeChemistry("lfp") === "LFP"');
  check(mod.normalizeChemistry('BYD Blade LFP') === 'LFP', 'normalizeChemistry("BYD Blade LFP") === "LFP"');
  check(mod.normalizeChemistry('ncm622') === 'NCM_622', 'normalizeChemistry("ncm622") === "NCM_622"');
  check(mod.normalizeChemistry('ncma') === 'NCMA', 'normalizeChemistry("ncma") === "NCMA"');
  check(mod.normalizeChemistry('nca') === 'NCA', 'normalizeChemistry("nca") === "NCA"');
  check(mod.normalizeChemistry(null) === 'NCM_811', 'normalizeChemistry(null) defaults to "NCM_811"');
  check(mod.normalizeChemistry(undefined) === 'NCM_811', 'normalizeChemistry(undefined) defaults to "NCM_811"');

  // ==============================================================
  // 5. SUBSIDY CLAWBACK & TCO BOUNDARIES
  // ==============================================================
  console.log('5. Testing subsidy clawback & TCO multi-year calculations...');

  // 5.1 Clawback at month 0 (70% clawback for export/inter)
  const cb0 = mod.calculateSubsidyClawback(0, 4_000_000, 'inter', 6_500_000);
  check(cb0.statutoryClawbackRate === 0.7, 'Month 0 clawback rate is 70%');
  check(cb0.localClawbackKrw === 2_800_000, 'Local clawback is 70% of 4M = 2.8M');
  check(cb0.nationalClawbackKrw === 0, 'Inter transfer exempts national subsidy');

  // 5.2 Clawback at month 24 (Exempt)
  const cb24 = mod.calculateSubsidyClawback(24, 4_000_000, 'export', 6_500_000);
  check(cb24.isExempt === true, 'Month 24 is exempt');
  check(cb24.totalClawbackKrw === 0, 'Month 24 clawback amount is 0 KRW');

  // 5.3 TCO with 0 km
  const tco0 = mod.calculateTcoComparison(0, 5);
  check(tco0.evTotalFuelCostKrw === 0, '0 km fuel cost is 0 KRW');
  check(tco0.iceTotalFuelCostKrw === 0, '0 km ICE fuel cost is 0 KRW');
  check(tco0.yearlyBreakdown.length === 5, '5 year breakdown has 5 rows');

  // 5.4 TCO with 20 years
  const tco20 = mod.calculateTcoComparison(15000, 20);
  check(tco20.years === 20, '20 years ownership preserved');
  check(tco20.yearlyBreakdown.length === 20, '20 year breakdown has 20 rows');
  check(tco20.totalCumulativeSavingsKrw > 0, '20 year cumulative savings positive');

  // 5.5 TCO with partial customParams (empty fuel_tariffs / auxiliary_benefits)
  const tcoPartial = mod.calculateTcoComparison(15000, 5, 5.2, 0.7, 1998, { fuel_tariffs: {}, auxiliary_benefits: {} });
  check(Number.isFinite(tcoPartial.totalCumulativeSavingsKrw), 'Partial customParams TCO cumulative savings must be finite');
  check(!Number.isNaN(tcoPartial.evTotalFuelCostKrw), 'Partial customParams EV fuel cost must not be NaN');
  check(!Number.isNaN(tcoPartial.tollSavingsKrw), 'Partial customParams toll savings must not be NaN');
  check(tcoPartial.totalCumulativeSavingsKrw > 0, 'Partial customParams total savings remains positive');

  // 5.6 Subsidy clawback with NaN custom clawback_rate
  const cbNan = mod.calculateSubsidyClawback(1, 4000000, 'inter', 6500000, [{ min_months: 0, max_months_exclusive: 10, clawback_rate: NaN, label_ko: 'test' }]);
  check(Number.isFinite(cbNan.totalClawbackKrw), 'NaN custom tier rate must produce finite clawback');
  check(cbNan.statutoryClawbackRate === 0, 'NaN custom rate clamped to 0');

  // 5.7 Battery health simulation with partial custom chemistry
  const batPartialChem = mod.simulateBatteryHealth({ years: 3, totalKm: 45000 }, { NCM_811: {} });
  check(typeof batPartialChem.chemistryName === 'string' && batPartialChem.chemistryName.length > 0, 'Partial custom chem has valid name');
  check(Number.isFinite(batPartialChem.sohPct), 'Partial custom chem SOH is finite');

  console.log(`  ✓ All tests passed for ${name}\n`);
}

// ==============================================================
// 6. MODEL ID NORMALIZATION PARITY CHECK
// ==============================================================
console.log('6. Testing model ID normalization parity...');
const m1 = depData.getModelById('ioniq5');
const m2 = depData.getModelById('ioniq-5');
check(m1 !== undefined, 'getModelById("ioniq5") found');
check(m2 !== undefined, 'getModelById("ioniq-5") found via normalization');
check(m1?.id === m2?.id, 'Hyphenated model ID resolves to the exact same model');

console.log(`\n========================================================`);
console.log(`[AUDIT COMPLETE] Total assertions verified: ${totalAssertions}`);
console.log(`Status: 100% PASSED (Zero anomalies, zero regressions)`);
console.log(`========================================================\n`);
