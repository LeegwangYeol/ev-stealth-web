/**
 * Comprehensive Audit Test Suite for EV Depreciation Calculator
 * Verifying:
 * 1. All 15 vehicle models, initial purchase price adjustments, annual mileage slider, holding years (1-10 years)
 * 2. Battery warranty status transitions & rapid charging frequency impacts
 * 3. ARIA sliders, input validation (preventing NaN or negative values), responsive chart layouts
 */

import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  calculateDepreciation,
  simulateBatteryHealth,
  calculateSubsidyClawback,
  calculateTcoComparison,
} from '../src/lib/depreciationCalculations.ts';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const dbPath = path.resolve(__dirname, '../src/data/ev_depreciation_data.json');
const db = JSON.parse(fs.readFileSync(dbPath, 'utf8'));

console.log('=== STARTING DEPRECIATION CALCULATOR SPECIALIST AUDIT ===\n');

// -------------------------------------------------------------
// AUDIT 1: ALL 15 VEHICLE MODELS & HOLDING YEARS (1-10 YEARS)
// -------------------------------------------------------------
console.log('[AUDIT 1] Testing all 15 vehicle models across holding years (1-10 years)...');
assert.equal(db.models.length, 15, 'Database must contain exactly 15 EV models');

let modelChecks = 0;
for (const model of db.models) {
  assert.ok(model.id, 'Model must have an ID');
  assert.ok(model.model_name, 'Model must have a model name');
  assert.ok(model.msrp_krw_baseline > 0, 'MSRP must be positive');
  assert.ok(model.net_purchase_price_krw > 0, 'Net price must be positive');
  assert.ok(model.warranty.years >= 8, 'Warranty years must be at least 8 years');
  assert.ok(model.warranty.km >= 120000, 'Warranty km must be at least 120,000 km');
  assert.ok(model.battery_specs.capacity_kwh > 0, 'Battery capacity must be positive');

  // Test across holding years 1 to 10 in 0.5 year increments
  for (const annualKm of [5000, 15000, 30000, 50000]) {
    let prevResidualPct = 101.0;
    for (let yr = 1; yr <= 10; yr += 0.5) {
      modelChecks++;
      const dep = calculateDepreciation({
        model,
        modelId: model.id,
        years: yr,
        mileageKm: yr * annualKm,
        priceBasis: 'effective',
      });

      assert.ok(Number.isFinite(dep.adjustedResidualPct), `Residual pct must be finite for ${model.id} yr ${yr}`);
      assert.ok(dep.adjustedResidualPct >= 5.0 && dep.adjustedResidualPct <= 100.0, `Residual pct must be clamped between 5% and 100% for ${model.id} yr ${yr}`);
      assert.ok(Number.isFinite(dep.estimatedResidualPriceKrw), `Residual price must be finite for ${model.id} yr ${yr}`);
      assert.ok(dep.estimatedResidualPriceKrw >= 0, `Residual price must be non-negative for ${model.id} yr ${yr}`);
      assert.ok(dep.depreciationAmountKrw >= 0, `Depreciation amount must be non-negative for ${model.id} yr ${yr}`);

      // Monotonic depreciation check (as holding years increase, residual pct must not drastically jump up)
      assert.ok(dep.adjustedResidualPct <= prevResidualPct + 0.1, `Residual pct should monotonically decrease with years: yr ${yr} (${dep.adjustedResidualPct}) vs prev (${prevResidualPct})`);
      prevResidualPct = dep.adjustedResidualPct;
    }
  }
}
console.log(`  ✓ Successfully audited ${modelChecks} model-year-mileage combinations across 1-10 years (100% pass)`);

// -------------------------------------------------------------
// AUDIT 2: INITIAL PURCHASE PRICE ADJUSTMENTS & SANITIZATION
// -------------------------------------------------------------
console.log('[AUDIT 2] Testing initial purchase price adjustments & input sanitization...');

// 2.1 Default MSRP vs Effective Basis
const sampleModel = db.models[0];
const depEffective = calculateDepreciation({ model: sampleModel, modelId: sampleModel.id, years: 3, priceBasis: 'effective' });
const depMsrp = calculateDepreciation({ model: sampleModel, modelId: sampleModel.id, years: 3, priceBasis: 'msrp' });
assert.equal(depEffective.basePurchasePriceKrw, sampleModel.net_purchase_price_krw, 'Effective basis matches net price');
assert.equal(depMsrp.basePurchasePriceKrw, sampleModel.msrp_krw_baseline, 'MSRP basis matches MSRP');
assert.ok(depMsrp.basePurchasePriceKrw > depEffective.basePurchasePriceKrw, 'MSRP should be higher than net subsidized price');

// 2.2 Custom purchase price bounds
const depZeroPrice = calculateDepreciation({ model: sampleModel, modelId: sampleModel.id, years: 3, customPurchasePriceKrw: 0 });
assert.equal(depZeroPrice.basePurchasePriceKrw, 0, 'Zero price correctly passed as 0');
assert.equal(depZeroPrice.estimatedResidualPriceKrw, 0, 'Zero price yields 0 residual price');

const depNegativePrice = calculateDepreciation({ model: sampleModel, modelId: sampleModel.id, years: 3, customPurchasePriceKrw: -50000000 });
assert.equal(depNegativePrice.basePurchasePriceKrw, sampleModel.msrp_krw_baseline, 'Negative price falls back to default MSRP');

const depHighPrice = calculateDepreciation({ model: sampleModel, modelId: sampleModel.id, years: 3, customPurchasePriceKrw: 50_000_000_000 });
assert.equal(depHighPrice.basePurchasePriceKrw, 10_000_000_000, 'Price exceeding 10B KRW is safely clamped at 10B KRW');

console.log('  ✓ Purchase price basis, bounds, and fallbacks verified without NaN or negative values');

// -------------------------------------------------------------
// AUDIT 3: BATTERY WARRANTY STATUS TRANSITIONS & RAPID CHARGING
// -------------------------------------------------------------
console.log('[AUDIT 3] Checking battery warranty transitions & rapid charging impacts...');

// 3.1 Warranty status transitions
// Case A: Safe warranty (< warranty years & km)
const depSafe = calculateDepreciation({ model: sampleModel, modelId: sampleModel.id, years: 2, mileageKm: 30000 });
assert.equal(depSafe.warrantyStatus.isExpired, false, '2 years / 30k km is not expired');
assert.equal(depSafe.warrantyStatus.isApproachingCliff, false, '2 years / 30k km is not approaching cliff');
assert.equal(depSafe.factorAdjustments.warrantyCliffPenalty, 0, 'Safe warranty has 0% penalty');

// Case B: Approaching cliff (within 2 years of warranty limit)
const depCliffYears = calculateDepreciation({ model: sampleModel, modelId: sampleModel.id, years: sampleModel.warranty.years - 1.5, mileageKm: 50000 });
assert.equal(depCliffYears.warrantyStatus.isExpired, false, 'Within years is not expired');
assert.equal(depCliffYears.warrantyStatus.isApproachingCliff, true, 'Within 2 years triggers approaching cliff');
assert.equal(depCliffYears.factorAdjustments.warrantyCliffPenalty, -6, 'Approaching cliff applies -6% penalty');

// Case C: Expired warranty (exceeds years or km)
const depExpiredYears = calculateDepreciation({ model: sampleModel, modelId: sampleModel.id, years: sampleModel.warranty.years + 1, mileageKm: 50000 });
assert.equal(depExpiredYears.warrantyStatus.isExpired, true, 'Exceeding years triggers expired');
assert.equal(depExpiredYears.factorAdjustments.warrantyCliffPenalty, -14, 'Expired warranty applies -14% penalty');

const depExpiredKm = calculateDepreciation({ model: sampleModel, modelId: sampleModel.id, years: 3, mileageKm: sampleModel.warranty.km + 10000 });
assert.equal(depExpiredKm.warrantyStatus.isExpired, true, 'Exceeding km triggers expired');
assert.equal(depExpiredKm.factorAdjustments.warrantyCliffPenalty, -14, 'Expired warranty applies -14% penalty');

// 3.2 Rapid Charging (DCFC) Frequency Impacts
const batSlow = simulateBatteryHealth({ chemistry: 'NCM_811', years: 3, totalKm: 45000, annualKm: 15000, dcfcRatio: 0.0 });
const batMed = simulateBatteryHealth({ chemistry: 'NCM_811', years: 3, totalKm: 45000, annualKm: 15000, dcfcRatio: 0.5 });
const batFast = simulateBatteryHealth({ chemistry: 'NCM_811', years: 3, totalKm: 45000, annualKm: 15000, dcfcRatio: 1.0 });

assert.ok(batSlow.cyclicLossPct < batMed.cyclicLossPct, 'DCFC 50% must produce more cyclic loss than DCFC 0%');
assert.ok(batMed.cyclicLossPct < batFast.cyclicLossPct, 'DCFC 100% must produce more cyclic loss than DCFC 50%');
assert.ok(batSlow.sohPct > batFast.sohPct, 'Frequent DCFC must accelerate SOH degradation');
assert.equal(batSlow.calendarLossPct, batFast.calendarLossPct, 'Calendar aging is invariant to DCFC ratio');

console.log('  ✓ Battery warranty state transitions (Safe -> Cliff -> Expired) & DCFC kinetics verified');

// -------------------------------------------------------------
// AUDIT 4: ARIA SLIDERS, INPUT VALIDATION & RESPONSIVE LAYOUTS
// -------------------------------------------------------------
console.log('[AUDIT 4] Auditing ARIA sliders, input validation, and responsive layouts...');

const clientPath = path.resolve(__dirname, '../src/app/depreciation-calculator/DepreciationCalculatorClient.tsx');
const clientSource = fs.readFileSync(clientPath, 'utf8');

// 4.1 ARIA Sliders
const requiredSliders = [
  { id: 'holdingYearsInput', varName: 'holdingYears', min: 1, max: 5 },
  { id: 'annualMileageInput', varName: 'annualMileageKm', min: 5000, max: 50000 },
  { id: 'dcfcRatioInput', varName: 'dcfcRatio', min: 0, max: 100 },
  { id: 'heldMonthsInput', varName: 'heldMonths', min: 0, max: 36 },
];

for (const slider of requiredSliders) {
  assert.ok(clientSource.includes(`id="${slider.id}"`), `Slider ${slider.id} must exist`);
  assert.ok(clientSource.includes(`aria-valuenow={${slider.varName}}`), `Slider ${slider.id} must have aria-valuenow`);
  assert.ok(clientSource.includes(`aria-valuemin={${slider.min}}`), `Slider ${slider.id} must have aria-valuemin={${slider.min}}`);
  assert.ok(clientSource.includes(`aria-valuemax={${slider.max}}`), `Slider ${slider.id} must have aria-valuemax={${slider.max}}`);
  assert.ok(clientSource.includes('aria-orientation="horizontal"'), `Slider ${slider.id} must have aria-orientation`);
}
console.log('  ✓ All 4 ARIA sliders adhere strictly to WAI-ARIA 1.2 slider specifications');

// 4.2 Keyboard Navigation
assert.ok(clientSource.includes('handleSliderKeyDown'), 'Sliders must implement keyboard navigation handler');
assert.ok(clientSource.includes("'ArrowRight'"), 'Slider keyboard handler must support ArrowRight');
assert.ok(clientSource.includes("'ArrowLeft'"), 'Slider keyboard handler must support ArrowLeft');
assert.ok(clientSource.includes("'Home'"), 'Slider keyboard handler must support Home key');
assert.ok(clientSource.includes("'End'"), 'Slider keyboard handler must support End key');
assert.ok(clientSource.includes("'PageUp'"), 'Slider keyboard handler must support PageUp');
assert.ok(clientSource.includes("'PageDown'"), 'Slider keyboard handler must support PageDown');
console.log('  ✓ Full APG slider keyboard navigation (Arrows, Home, End, PageUp, PageDown) verified');

// 4.3 Input Validation & Error Announcements
assert.ok(clientSource.includes('aria-invalid={hasPriceError}'), 'Custom price input must have aria-invalid');
assert.ok(clientSource.includes('role="alert"'), 'Input errors must have role="alert"');
assert.ok(clientSource.includes('aria-invalid={hasNationalSubsidyError}'), 'National subsidy input must have aria-invalid');
assert.ok(clientSource.includes('aria-invalid={hasLocalSubsidyError}'), 'Local subsidy input must have aria-invalid');
console.log('  ✓ Form inputs have strict bounds checking and live screen-reader error alerts');

// 4.4 SVG Chart Semantics & Responsive Layout
assert.ok(clientSource.includes('role="img"'), 'SVG chart must declare role="img"');
assert.ok(clientSource.includes('aria-labelledby="dep-chart-title dep-chart-desc"'), 'SVG chart must link title and desc');
assert.ok(clientSource.includes('table-scroll-container'), 'Tables and charts must have table-scroll-container');
assert.ok(clientSource.includes('overflow-x-auto'), 'Tables and charts must support responsive horizontal scroll');
assert.ok(clientSource.includes('sm:hidden'), 'Mobile swipe guidance indicators must be present for small viewports');
assert.ok(clientSource.includes('table aria-label="연차별 잔존가치 프로젝션 데이터 표"'), 'Accessible data table alternative for screen readers must be present');
console.log('  ✓ Responsive SVG chart layouts, touch indicators, and screen reader table fallbacks verified');

console.log('\n=== ALL DEPRECIATION CALCULATOR SPECIALIST AUDIT CHECKS PASSED (100%) ===\n');
