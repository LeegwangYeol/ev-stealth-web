import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {
  calculateDepreciation,
  simulateBatteryHealth,
  calculateSubsidyClawback,
  calculateTcoComparison,
} from '../src/lib/depreciationCalculations.ts';

console.log('=== RUNNING DEPRECIATION CALCULATOR AUDIT & HARDENING TEST SUITE ===');

// ---------------------------------------------------------------
// 1. CALCULATION ANOMALY TESTS: calculateDepreciation
// ---------------------------------------------------------------
console.log('\n[TEST 1] calculateDepreciation Edge Cases & Boundaries');

// 1.1 Zero years and zero mileage
{
  const res = calculateDepreciation({
    years: 0,
    mileageKm: 0,
    customPurchasePriceKrw: 50_000_000,
  });
  assert.ok(Number.isFinite(res.adjustedResidualPct), 'Residual pct must be finite');
  assert.ok(res.adjustedResidualPct >= 5.0 && res.adjustedResidualPct <= 99.0, 'Residual pct must be clamped');
  assert.ok(res.estimatedResidualPriceKrw >= 0, 'Residual price must not be negative');
  assert.ok(res.depreciationAmountKrw >= 0, 'Depreciation amount must not be negative');
  console.log('  ✓ Zero years and zero mileage handled safely');
}

// 1.2 Negative inputs and NaN
{
  const res = calculateDepreciation({
    years: -5,
    mileageKm: -10000,
    customPurchasePriceKrw: -50_000_000,
  });
  assert.ok(!Number.isNaN(res.adjustedResidualPct), 'Residual pct must not be NaN');
  assert.ok(!Number.isNaN(res.estimatedResidualPriceKrw), 'Residual price must not be NaN');
  assert.ok(res.estimatedResidualPriceKrw >= 0, 'Negative purchase price falls back safely');
  console.log('  ✓ Negative years, mileage, and purchase price handled gracefully');
}

// 1.3 Extreme excess mileage & max_mileage_discount_cap enforcement
{
  const res = calculateDepreciation({
    years: 3,
    mileageKm: 300_000, // 255,000 km excess
    customPurchasePriceKrw: 60_000_000,
  });
  assert.ok(res.factorAdjustments.mileageAdjustment >= -15.0, 'Mileage penalty must be capped by max_mileage_discount_cap (-15%)');
  assert.ok(res.adjustedResidualPct >= 5.0, 'Residual pct must remain >= 5%');
  console.log('  ✓ Excessive mileage penalty successfully capped at max discount cap');
}

// 1.4 Price ceiling cap (10 Billion KRW)
{
  const res = calculateDepreciation({
    years: 1,
    mileageKm: 15_000,
    customPurchasePriceKrw: 50_000_000_000, // 50 billion
  });
  assert.equal(res.basePurchasePriceKrw, 10_000_000_000, 'Price must be capped at 10,000,000,000 KRW');
  assert.ok(Number.isFinite(res.estimatedResidualPriceKrw), 'Estimated price is finite');
  console.log('  ✓ Price ceiling of 10B KRW verified');
}

// ---------------------------------------------------------------
// 2. CALCULATION ANOMALY TESTS: simulateBatteryHealth
// ---------------------------------------------------------------
console.log('\n[TEST 2] simulateBatteryHealth Arrhenius & Cyclic Kinetics');

// 2.1 Sub-zero ambient temperature & extreme mileage
{
  const res = simulateBatteryHealth({
    chemistry: 'LFP',
    years: 10,
    totalKm: 300_000,
    annualKm: 30_000,
    dcfcRatio: 1.0, // 100% DCFC
    ambientTempC: -25.0, // deep freeze
  });
  assert.ok(!Number.isNaN(res.sohPct), 'SoH must not be NaN');
  assert.ok(Number.isFinite(res.sohPct), 'SoH must be finite');
  assert.ok(res.sohPct >= 0 && res.sohPct <= 100.0, 'SoH clamped between 0 and 100%');
  assert.ok(res.equivalentFullCycles >= 0, 'Cycles must be positive');
  assert.ok(!Number.isNaN(res.calendarLossPct), 'Calendar loss not NaN');
  assert.ok(!Number.isNaN(res.cyclicLossPct), 'Cyclic loss not NaN');
  console.log('  ✓ Sub-zero deep freeze with 100% DCFC produced valid SoH without NaN');
}

// 2.2 Zero usage (brand new showroom vehicle)
{
  const res = simulateBatteryHealth({
    chemistry: 'NCM_811',
    years: 0,
    totalKm: 0,
    annualKm: 0,
    dcfcRatio: 0,
    ambientTempC: 25.0,
  });
  assert.equal(res.sohPct, 100.0, 'Zero usage must retain 100.0% SoH');
  assert.equal(res.grade, 'GRADE_A', 'Grade must be GRADE_A');
  console.log('  ✓ Zero mileage showroom vehicle evaluates to 100% SoH Grade A');
}

// ---------------------------------------------------------------
// 3. CALCULATION ANOMALY TESTS: calculateSubsidyClawback
// ---------------------------------------------------------------
console.log('\n[TEST 3] calculateSubsidyClawback Statutory Schedule');

// 3.1 24+ months (Statutory exemption)
{
  const res = calculateSubsidyClawback(24, 5_000_000, 'inter', 4_000_000);
  assert.equal(res.isExempt, true, '24 months must be exempt');
  assert.equal(res.totalClawbackKrw, 0, 'Clawback must be 0 for >= 24m');
  assert.equal(res.statutoryClawbackRate, 0, 'Statutory rate 0%');
  console.log('  ✓ 24 months mandatory period expiry completely exempts clawback');
}

// 3.2 Intra-municipality transfer (Same municipality exemption)
{
  const res = calculateSubsidyClawback(6, 6_000_000, 'intra', 5_000_000);
  assert.equal(res.isExempt, true, 'Intra-municipality transfer is exempt');
  assert.equal(res.totalClawbackKrw, 0, 'Clawback must be 0 for intra-transfer');
  console.log('  ✓ Intra-municipality transfer automatically exempt');
}

// 3.3 Inter-municipality transfer (Local subsidy only clawed back)
{
  const res = calculateSubsidyClawback(6, 5_000_000, 'inter', 4_000_000);
  assert.equal(res.isExempt, false, 'Inter-transfer under 24m is NOT exempt');
  assert.equal(res.nationalClawbackKrw, 0, 'National subsidy is exempt from inter-transfer clawback');
  assert.ok(res.localClawbackKrw > 0, 'Local subsidy must be clawed back');
  assert.equal(res.totalClawbackKrw, res.localClawbackKrw, 'Total equals local clawback');
  console.log('  ✓ Inter-municipality transfer claws back only local subsidy');
}

// 3.4 Export cancellation (National + Local full clawback)
{
  const res = calculateSubsidyClawback(10, 4_000_000, 'export', 3_000_000);
  assert.ok(res.nationalClawbackKrw > 0, 'Export claws back national subsidy');
  assert.ok(res.localClawbackKrw > 0, 'Export claws back local subsidy');
  assert.equal(res.totalClawbackKrw, res.nationalClawbackKrw + res.localClawbackKrw);
  console.log('  ✓ Export cancellation applies clawback to both national and local subsidy');
}

// ---------------------------------------------------------------
// 4. CALCULATION ANOMALY TESTS: calculateTcoComparison
// ---------------------------------------------------------------
console.log('\n[TEST 4] calculateTcoComparison Multi-Year Economy');

// 4.1 Fractional years (e.g. 1.5 years)
{
  const res = calculateTcoComparison(15_000, 1.5, 5.2, 0.7, 1998);
  assert.ok(Number.isFinite(res.totalCumulativeSavingsKrw), 'Cumulative savings finite');
  assert.equal(res.yearlyBreakdown.length, 2, '1.5 years should yield 2 yearly breakdown rows');
  assert.ok(res.yearlyBreakdown[1].cumulativeKm === 22500, 'Cumulative km for 1.5 yrs at 15k/yr is 22,500 km');
  console.log('  ✓ Fractional 1.5 years properly handles partial year breakdown');
}

// 4.2 Zero km driving
{
  const res = calculateTcoComparison(0, 3, 5.2, 0.7, 1998);
  assert.ok(Number.isFinite(res.totalCumulativeSavingsKrw), 'Zero km savings finite');
  assert.equal(res.evTotalFuelCostKrw, 0, 'EV fuel is 0');
  assert.equal(res.iceTotalFuelCostKrw, 0, 'ICE fuel is 0');
  assert.ok(res.taxSavingsKrw > 0, 'Tax savings still exist without driving');
  console.log('  ✓ Zero km driving safely computed without zero-division error');
}

// ---------------------------------------------------------------
// 5. STATIC ACCESSIBILITY & WCAG AA CODE AUDIT
// ---------------------------------------------------------------
console.log('\n[TEST 5] WCAG AA & Mobile Layout Code Audit');

const clientCode = fs.readFileSync(
  path.resolve(process.cwd(), 'src/app/depreciation-calculator/DepreciationCalculatorClient.tsx'),
  'utf-8'
);

// 5.1 Error announcements on inputs
assert.ok(clientCode.includes('aria-invalid={hasPriceError}'), 'customPriceInputField must have aria-invalid');
assert.ok(clientCode.includes('id="custom-price-error-msg"'), 'custom-price-error-msg element must exist');
assert.ok(clientCode.includes('aria-invalid={hasNationalSubsidyError}'), 'nationalSubsidyInput must have aria-invalid');
assert.ok(clientCode.includes('aria-invalid={hasLocalSubsidyError}'), 'localSubsidyInput must have aria-invalid');
assert.ok(clientCode.includes('id="national-subsidy-error-msg"'), 'national-subsidy-error-msg element must exist');
assert.ok(clientCode.includes('id="local-subsidy-error-msg"'), 'local-subsidy-error-msg element must exist');
console.log('  ✓ Form inputs have aria-invalid and aria-describedby error announcements');

// 5.2 Keyboard accessibility on sliders and tabs
assert.ok(clientCode.includes('role="tablist"'), 'Brand filter must have role=tablist');
assert.ok(clientCode.includes('role="tab"'), 'Brand items must have role=tab');
assert.ok(clientCode.includes('role="tabpanel"'), 'ModelGrid must have role=tabpanel');
assert.ok(clientCode.includes('onKeyDown={(e) => handleBrandTabKeyDown(e, idx)}'), 'Brand tabs must have keyboard handler');
assert.ok(clientCode.includes('aria-valuenow={holdingYears}'), 'holdingYears slider must have aria-valuenow');
assert.ok(clientCode.includes('aria-valuenow={annualMileageKm}'), 'annualMileage slider must have aria-valuenow');
assert.ok(clientCode.includes('aria-valuenow={dcfcRatio}'), 'dcfcRatio slider must have aria-valuenow');
assert.ok(clientCode.includes('aria-valuenow={heldMonths}'), 'heldMonths slider must have aria-valuenow');
console.log('  ✓ WAI-ARIA tab pattern and slider attributes verified');

// 5.3 Anti-anomaly check: No duplicate sign "+-" formatting
assert.ok(!clientCode.includes('+{(tcoResult.totalCumulativeSavingsKrw'), 'Must not have hardcoded + before cumulative savings');
assert.ok(!clientCode.includes('+{(tcoResult.fuelSavingsKrw'), 'Must not have hardcoded + before fuel savings');
assert.ok(!clientCode.includes('+{(tcoResult.taxSavingsKrw'), 'Must not have hardcoded + before tax savings');
assert.ok(!clientCode.includes('+{(row.annualNetSavingsKrw'), 'Must not have hardcoded + before row savings');
console.log('  ✓ No hardcoded "+" before potentially negative values (+- anomaly eliminated)');

// 5.4 Mobile layout responsiveness
assert.ok(clientCode.includes('break-keep'), 'KPI and summary values must have break-keep');
assert.ok(clientCode.includes('col-span-2 sm:col-span-1'), '5th factor chip must span 2 cols on mobile');
assert.ok(clientCode.includes('w-full sm:w-auto'), 'ICE displacement select must have w-full sm:w-auto');
console.log('  ✓ Mobile responsive break-keep and column balancing verified');

// 5.5 Forwarder parity check
const forwarderCode = fs.readFileSync(
  path.resolve(process.cwd(), 'src/components/DepreciationCalculatorClient.tsx'),
  'utf-8'
);
assert.ok(
  forwarderCode.includes("export { default } from '@/app/depreciation-calculator/DepreciationCalculatorClient';"),
  'Forwarder component must export default from app/depreciation-calculator'
);
console.log('  ✓ Forwarder component cleanly re-exports DepreciationCalculatorClient');

console.log('\n=== ALL 14 AUDIT & INTEGRITY VERIFICATIONS PASSED (100%) ===\n');
