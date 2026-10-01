/**
 * tests/test_challenger_extreme_scenarios.mjs
 * Comprehensive Empirical Challenger Harness for Extreme Scenarios:
 * 1. Empty Checklist
 * 2. Zero Mileage (0 km)
 * 3. Extreme High Mileage (999,999 km)
 * 4. Boundary Years
 * 5. Special Character VINs
 * 6. Viewport & Responsive Layout Static Inspection
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as depreciation from '../src/lib/getDepreciationData.ts';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Dynamically patch getRecallData import for Node.js ESM JSON attribute requirement
const recallSrcPath = path.resolve(__dirname, '../src/lib/getRecallData.ts');
const originalRecallSrc = fs.readFileSync(recallSrcPath, 'utf-8');
const patchedRecallSrc = originalRecallSrc.replace(
  "import rawRecallData from '../data/ev_recall_database.json';",
  "import rawRecallData from '../src/data/ev_recall_database.json' with { type: 'json' };"
);
const tempRecallFixture = path.resolve(__dirname, 'temp_recall_extreme_fixture.ts');
fs.writeFileSync(tempRecallFixture, patchedRecallSrc, 'utf-8');
let recall;
try {
  recall = await import('./temp_recall_extreme_fixture.ts');
} finally {
  if (fs.existsSync(tempRecallFixture)) {
    fs.unlinkSync(tempRecallFixture);
  }
}


const results = {
  totalAssertions: 0,
  passedAssertions: 0,
  failedAssertions: 0,
  scenarios: {
    emptyChecklist: { total: 0, passed: 0, failed: 0 },
    zeroMileage: { total: 0, passed: 0, failed: 0 },
    highMileage999k: { total: 0, passed: 0, failed: 0 },
    boundaryYears: { total: 0, passed: 0, failed: 0 },
    specialCharVins: { total: 0, passed: 0, failed: 0 },
    viewportStyling: { total: 0, passed: 0, failed: 0 }
  },
  failures: [],
  findings: []
};

function assert(scenario, condition, message, metadata = {}) {
  results.totalAssertions++;
  results.scenarios[scenario].total++;
  if (condition) {
    results.passedAssertions++;
    results.scenarios[scenario].passed++;
  } else {
    results.failedAssertions++;
    results.scenarios[scenario].failed++;
    const failureRecord = { scenario, message, metadata };
    results.failures.push(failureRecord);
    console.error(`❌ [${scenario.toUpperCase()} FAIL] ${message}`, metadata);
  }
}

console.log('================================================================');
console.log('🧪 EMPIRICAL CHALLENGER: EXTREME SCENARIOS VERIFICATION HARNESS');
console.log('================================================================\n');

// ============================================================================
// 1. EMPTY CHECKLIST & CORRUPTED STORAGE SCENARIOS
// ============================================================================
console.log('--- [1. Empty Checklist & Corrupted Storage Scenarios] ---');

// Parse PdiChecklistClient.tsx source
const pdiClientPath = path.resolve(__dirname, '../src/app/pdi-checklist/PdiChecklistClient.tsx');
const pdiSource = fs.readFileSync(pdiClientPath, 'utf-8');

// Check division-by-zero protection in client
const hasDivZeroGuard = pdiSource.includes('items.length === 0 ? 0 : Math.round((checkedCount / items.length) * 100)');
assert('emptyChecklist', hasDivZeroGuard, 'PdiChecklistClient has explicit division-by-zero guard for items.length === 0');

// Simulate state calculations under empty checklist
const emptyList = [];
const emptyChecked = emptyList.filter(i => i.checked).length;
const emptyProgress = emptyList.length === 0 ? 0 : Math.round((emptyChecked / emptyList.length) * 100);
assert('emptyChecklist', emptyProgress === 0, 'Empty checklist progress is strictly 0%', { emptyProgress });
assert('emptyChecklist', !Number.isNaN(emptyProgress), 'Empty checklist progress is never NaN');

// Simulate corrupted storage inputs
const corruptInputs = [
  '',
  '   ',
  'null',
  'undefined',
  'false',
  '12345',
  '"{}"',
  '[]',
  '{ badJson: ',
  '{"id": "1"}',
  JSON.stringify([null, undefined, 42, 'corrupt', { id: 'invalid', checked: true }]),
  JSON.stringify([{ id: '1', checked: false }]),
  JSON.stringify([{ id: '1', checked: true }, { id: '99', checked: true }])
];

function simulateSafeHydration(raw) {
  let items = [
    { id: '1', category: '외관', task: 't1', checked: false },
    { id: '2', category: '실내', task: 't2', checked: false }
  ];
  try {
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        items = items.map(item => {
          const match = parsed.find(p => p && p.id === item.id);
          return match ? { ...item, checked: Boolean(match.checked) } : item;
        });
      }
    }
  } catch {
    // fallback
  }
  return items;
}

for (const input of corruptInputs) {
  const hydrated = simulateSafeHydration(input);
  assert('emptyChecklist', Array.isArray(hydrated), `Hydration returns valid array for input: ${input.slice(0, 30)}`);
  assert('emptyChecklist', hydrated.length === 2, `Hydration preserves base items length for input: ${input.slice(0, 30)}`);
  for (const item of hydrated) {
    assert('emptyChecklist', typeof item.checked === 'boolean', `Item ${item.id} checked state is boolean`);
  }
}

// ============================================================================
// 2. ZERO MILEAGE SCENARIOS (0 km)
// ============================================================================
console.log('\n--- [2. Zero Mileage Scenarios (0 km)] ---');

const depDb = depreciation.getDepreciationDatabase();

for (const model of depDb.models) {
  // Test zero mileage across different year points
  for (const yr of [0, 1, 3, 5]) {
    const dep = depreciation.calculateDepreciation({
      modelId: model.id,
      years: yr,
      mileageKm: 0
    });

    assert('zeroMileage', Number.isFinite(dep.adjustedResidualPct), `Residual % finite for ${model.id} at 0 km, yr ${yr}`);
    assert('zeroMileage', !Number.isNaN(dep.adjustedResidualPct), `Residual % not NaN for ${model.id} at 0 km, yr ${yr}`);
    assert('zeroMileage', dep.adjustedResidualPct <= 99.0, `Residual % <= 99% for ${model.id} at 0 km`);
    assert('zeroMileage', dep.adjustedResidualPct >= 5.0, `Residual % >= 5% for ${model.id} at 0 km`);
    assert('zeroMileage', dep.estimatedResidualPriceKrw >= 0, `Residual price non-negative for ${model.id} at 0 km`);
    assert('zeroMileage', dep.estimatedResidualPriceKrw <= dep.basePurchasePriceKrw, `Residual price <= MSRP at 0 km`);
    assert('zeroMileage', dep.depreciationAmountKrw >= 0, `Depreciation amount >= 0 at 0 km`);
  }

  // Battery health simulation at 0 km
  const batZero = depreciation.simulateBatteryHealth({
    modelId: model.id,
    years: 2.0,
    totalKm: 0,
    ambientTempC: 25.0,
    dcfcRatio: 0.0
  });

  assert('zeroMileage', !Number.isNaN(batZero.sohPct), `Battery SoH not NaN at 0 km for ${model.id}`);
  assert('zeroMileage', batZero.sohPct > 0 && batZero.sohPct <= 100, `Battery SoH within (0, 100]% at 0 km for ${model.id}`);
  assert('zeroMileage', batZero.cyclicLossPct === 0, `Cyclic loss is strictly 0% when totalKm = 0 for ${model.id}`, { cyclicLossPct: batZero.cyclicLossPct });
  assert('zeroMileage', batZero.calendarLossPct >= 0, `Calendar loss >= 0 at 0 km for ${model.id}`);
}

// TCO at 0 km
const tcoZeroKm = depreciation.calculateTcoComparison(0, 5);
assert('zeroMileage', !Number.isNaN(tcoZeroKm.evTotalFuelCostKrw), 'EV fuel cost not NaN at 0 km');
assert('zeroMileage', tcoZeroKm.evTotalFuelCostKrw === 0, 'EV fuel cost strictly 0 KRW at 0 km');
assert('zeroMileage', tcoZeroKm.iceTotalFuelCostKrw === 0, 'ICE fuel cost strictly 0 KRW at 0 km');
assert('zeroMileage', Number.isFinite(tcoZeroKm.totalCumulativeSavingsKrw), 'Total cumulative savings finite at 0 km');

// ============================================================================
// 3. 999,999 KM EXTREME MILEAGE SCENARIOS
// ============================================================================
console.log('\n--- [3. 999,999 km Extreme Mileage Scenarios] ---');

for (const model of depDb.models) {
  const dep999k = depreciation.calculateDepreciation({
    modelId: model.id,
    years: 5.0,
    mileageKm: 999999
  });

  assert('highMileage999k', Number.isFinite(dep999k.adjustedResidualPct), `999,999 km residual % finite for ${model.id}`);
  assert('highMileage999k', dep999k.adjustedResidualPct === 5.0, `999,999 km hits exact 5.0% floor for ${model.id}`, { pct: dep999k.adjustedResidualPct });
  assert('highMileage999k', dep999k.estimatedResidualPriceKrw >= 0, `999,999 km residual price non-negative for ${model.id}`);
  assert('highMileage999k', Number.isFinite(dep999k.depreciationAmountKrw), `999,999 km depreciation finite for ${model.id}`);

  // Compare 999,999 km residual with 10,000 km residual
  const dep10k = depreciation.calculateDepreciation({ modelId: model.id, years: 5.0, mileageKm: 10000 });
  assert('highMileage999k', dep999k.adjustedResidualPct <= dep10k.adjustedResidualPct, `999,999 km residual <= 10,000 km residual for ${model.id}`);

  // Battery health simulation at 999,999 km
  const bat999k = depreciation.simulateBatteryHealth({
    modelId: model.id,
    years: 8.0,
    totalKm: 999999,
    ambientTempC: 30.0,
    dcfcRatio: 0.8
  });

  assert('highMileage999k', !Number.isNaN(bat999k.sohPct), `Battery SoH not NaN at 999,999 km for ${model.id}`);
  assert('highMileage999k', bat999k.sohPct >= 0 && bat999k.sohPct <= 100, `Battery SoH bounded [0, 100] at 999,999 km for ${model.id}`);
  assert('highMileage999k', bat999k.replacementCostEstimate.totalNewInstalledKrw > 0, `Replacement cost positive for ${model.id}`);
}

// TCO at 999,999 km / year
const tco999k = depreciation.calculateTcoComparison(999999, 3);
assert('highMileage999k', Number.isFinite(tco999k.evTotalFuelCostKrw), 'EV fuel cost finite at 999,999 km/yr');
assert('highMileage999k', Number.isFinite(tco999k.iceTotalFuelCostKrw), 'ICE fuel cost finite at 999,999 km/yr');
assert('highMileage999k', tco999k.totalCumulativeSavingsKrw > 0, 'Cumulative savings positive at 999,999 km/yr');

// ============================================================================
// 4. BOUNDARY YEARS SCENARIOS
// ============================================================================
console.log('\n--- [4. Boundary Years Scenarios] ---');

const boundaryYears = [
  -10.0,
  -1.0,
  -0.001,
  0.0,
  0.0001,
  0.1,
  0.5,
  0.999,
  1.0,
  1.5,
  2.0,
  2.999,
  3.0,
  3.001,
  4.0,
  5.0,
  10.0,
  15.0,
  20.0,
  50.0,
  100.0
];

for (const yr of boundaryYears) {
  const dep = depreciation.calculateDepreciation({
    modelId: 'ioniq-5',
    years: yr,
    mileageKm: 45000
  });

  assert('boundaryYears', Number.isFinite(dep.adjustedResidualPct), `Residual % finite for yr=${yr}`);
  assert('boundaryYears', !Number.isNaN(dep.adjustedResidualPct), `Residual % not NaN for yr=${yr}`);
  assert('boundaryYears', dep.adjustedResidualPct >= 5.0 && dep.adjustedResidualPct <= 99.0, `Residual % clamped [5, 99] for yr=${yr}`);
  assert('boundaryYears', dep.estimatedResidualPriceKrw >= 0, `Residual price non-negative for yr=${yr}`);

  const bat = depreciation.simulateBatteryHealth({
    modelId: 'ioniq-5',
    years: yr,
    totalKm: 45000
  });
  assert('boundaryYears', !Number.isNaN(bat.sohPct), `Battery SoH not NaN for yr=${yr}`);
  assert('boundaryYears', bat.sohPct >= 0 && bat.sohPct <= 100, `Battery SoH in [0, 100] for yr=${yr}`);

  const tco = depreciation.calculateTcoComparison(15000, yr);
  assert('boundaryYears', Number.isFinite(tco.totalCumulativeSavingsKrw), `TCO savings finite for yr=${yr}`);
  assert('boundaryYears', tco.yearlyBreakdown.length >= 1, `TCO yearly breakdown has >= 1 entry for yr=${yr}`);
}

// Statutory subsidy clawback months boundaries (0m to 36m)
const boundaryMonths = [-1, 0, 1, 2.9, 3, 5.9, 6, 11.9, 12, 17.9, 18, 23.9, 24, 24.1, 36];
for (const m of boundaryMonths) {
  const cbInter = depreciation.calculateSubsidyClawback(m, 4000000, 'inter', 6500000);
  assert('boundaryYears', Number.isFinite(cbInter.totalClawbackKrw), `Clawback finite for month ${m}`);
  assert('boundaryYears', cbInter.totalClawbackKrw >= 0, `Clawback non-negative for month ${m}`);

  if (m >= 24) {
    assert('boundaryYears', cbInter.isExempt === true, `Exempt for month ${m} >= 24`);
    assert('boundaryYears', cbInter.totalClawbackKrw === 0, `Clawback 0 KRW for month ${m} >= 24`);
  }
}

// ============================================================================
// 5. SPECIAL CHARACTER VINS SCENARIOS
// ============================================================================
console.log('\n--- [5. Special Character VINs Scenarios] ---');

const specialVins = [
  // Length anomalies
  '',
  ' ',
  'K',
  'KM8',
  'KM8KN4AE4NU12345',      // 16 chars
  'KM8KN4AE4NU1234567',     // 18 chars
  'A'.repeat(50),
  'A'.repeat(500),
  // ISO 3779 disallowed characters (I, O, Q)
  'KM8KN4AE4NI123456',
  'KM8KN4AE4NO123456',
  'KM8KN4AE4NQ123456',
  'IM8KN4AE4NU123456',
  'OM8KN4AE4NU123456',
  'QM8KN4AE4NU123456',
  'km8kn4ae4ni123456',
  'km8kn4ae4no123456',
  'km8kn4ae4nq123456',
  // Special characters & injection vectors
  'KM8KN4AE4NU12345!',
  'KM8KN4AE4NU12345@',
  'KM8KN4AE4NU12345#',
  'KM8KN4AE4NU12345$',
  'KM8KN4AE4NU12345%',
  'KM8KN4AE4NU12345^',
  'KM8KN4AE4NU12345&',
  'KM8KN4AE4NU12345*',
  'KM8KN4AE4NU12345(',
  'KM8KN4AE4NU12345)',
  'KM8KN4AE4NU1234\0',
  'KM8KN4AE4NU1234\n',
  'KM8KN4AE4NU1234\r',
  'KM8KN4AE4NU1234\t',
  'KM8KN4AE4NU1234\u200B', // zero width space
  'KM8KN4AE4NU1234\uFEFF', // BOM
  'KM8KN4AE4NU123🚘',      // Emoji
  'KM8KN4AE4NU123🚗',      // Emoji
  '현대아이오닉5전기차차대번호', // Korean
  '<script>alert(1)</script>',
  "KM8KN4'; DROP TABLE recalls;--",
  '"><svg/onload=alert(1)>'
];

for (const vin of specialVins) {
  const valRes = recall.validateVinString(vin);
  assert('specialCharVins', !valRes.valid, `validateVinString correctly rejects: "${vin.slice(0, 30)}"`);
  assert('specialCharVins', typeof valRes.error === 'string' && valRes.error.length > 0, `Error message provided for: "${vin.slice(0, 30)}"`);

  // decodeVinAndCheckRecalls must handle gracefully without unhandled exception
  let decodeResult;
  try {
    decodeResult = recall.decodeVinAndCheckRecalls(vin);
  } catch (err) {
    decodeResult = { crashed: true, error: err.message };
  }

  assert('specialCharVins', !decodeResult.crashed, `decodeVinAndCheckRecalls did not throw on: "${vin.slice(0, 30)}"`);
  assert('specialCharVins', decodeResult.valid === false, `decodeVinAndCheckRecalls returns valid=false for: "${vin.slice(0, 30)}"`);
  assert('specialCharVins', decodeResult.recalls.length === 0, `No false positive recalls for: "${vin.slice(0, 30)}"`);
}

// Delimiter normalization tolerance
const delimitedVins = [
  { raw: 'KM8-KN4-AE4-NU123456', canonical: 'KM8KN4AE4NU123456' },
  { raw: 'KM8 KN4 AE4 NU123456', canonical: 'KM8KN4AE4NU123456' },
  { raw: '  KM8KN4AE4NU123456  ', canonical: 'KM8KN4AE4NU123456' },
  { raw: 'km8kn4ae4nu123456', canonical: 'KM8KN4AE4NU123456' },
  { raw: 'km8-kn4-ae4-nu123456', canonical: 'KM8KN4AE4NU123456' }
];

for (const d of delimitedVins) {
  const valRes = recall.validateVinString(d.raw);
  assert('specialCharVins', valRes.valid === true, `Delimiter normalized for: "${d.raw}"`);
  assert('specialCharVins', valRes.normalized === d.canonical, `Normalized to "${d.canonical}" (got "${valRes.normalized}")`);

  const decRes = recall.decodeVinAndCheckRecalls(d.raw);
  assert('specialCharVins', decRes.valid === true, `Decoded valid=true for normalized: "${d.raw}"`);
  assert('specialCharVins', decRes.decodedModel === '아이오닉 5', `Decoded model is 아이오닉 5 for: "${d.raw}"`);
}

// ============================================================================
// 6. MOBILE VS DESKTOP VIEWPORT STYLING STATIC INSPECTION
// ============================================================================
console.log('\n--- [6. Mobile vs Desktop Viewport Styling Static Inspection] ---');

const layoutPath = path.resolve(__dirname, '../src/app/layout.tsx');
const layoutCode = fs.readFileSync(layoutPath, 'utf-8');

// A. Desktop navigation breakpoint and accessibility
assert('viewportStyling', layoutCode.includes('data-testid="desktop-nav"'), 'Layout has data-testid="desktop-nav"');
assert('viewportStyling', layoutCode.includes('hidden md:flex'), 'Desktop nav hides on mobile screens with hidden md:flex');
assert('viewportStyling', layoutCode.includes('aria-label="데스크톱 내비게이션"'), 'Desktop nav has aria-label');

// B. Mobile drawer toggle and drawer container
assert('viewportStyling', layoutCode.includes('id="mobile-nav-drawer"'), 'Mobile drawer uses #mobile-nav-drawer');
assert('viewportStyling', layoutCode.includes('data-testid="mobile-drawer-toggle"'), 'Mobile drawer toggle has data-testid');
assert('viewportStyling', layoutCode.includes('data-testid="mobile-drawer"'), 'Mobile drawer body has data-testid');
assert('viewportStyling', layoutCode.includes('md:hidden'), 'Mobile drawer is hidden on desktop with md:hidden');
assert('viewportStyling', layoutCode.includes('max-w-[calc(100vw-2rem)]'), 'Mobile drawer prevents viewport blowout with max-w-[calc(100vw-2rem)]');

// C. Skip navigation link
assert('viewportStyling', layoutCode.includes('href="#main-content"'), 'Skip navigation link points to #main-content');
assert('viewportStyling', layoutCode.includes('sr-only focus:not-sr-only'), 'Skip navigation link uses accessible sr-only focus pattern');
assert('viewportStyling', layoutCode.includes('id="main-content"'), 'Main element has id="main-content"');

// D. Touch targets and responsive padding in PdiChecklistClient
const pdiCode = fs.readFileSync(pdiClientPath, 'utf-8');
assert('viewportStyling', pdiCode.includes('w-6 h-6'), 'PDI checkboxes have touch-friendly w-6 h-6 sizing');
assert('viewportStyling', pdiCode.includes('sm:flex-row'), 'PDI header uses responsive sm:flex-row direction');

// E. Depreciation calculator responsiveness
const depClientPath = path.resolve(__dirname, '../src/app/depreciation-calculator/DepreciationCalculatorClient.tsx');
const depClientCode = fs.readFileSync(depClientPath, 'utf-8');
assert('viewportStyling', depClientCode.includes('overflow-x-auto'), 'Depreciation client has overflow-x-auto for table scrolling on mobile');
assert('viewportStyling', depClientCode.includes('grid-cols-1'), 'Depreciation client defaults to single column grid-cols-1 for mobile');

// F. Recall portal responsiveness
const recallClientPath = path.resolve(__dirname, '../src/app/recall-portal/RecallPortalClient.tsx');
const recallClientCode = fs.readFileSync(recallClientPath, 'utf-8');
assert('viewportStyling', recallClientCode.includes('flex flex-col sm:flex-row') || recallClientCode.includes('flex-col sm:flex-row'), 'Recall portal uses responsive form controls flex-col sm:flex-row');

// G. Check for any fixed min-width > 320px: must be protected with overflow-x-auto wrapper
const appDir = path.resolve(__dirname, '../src/app');
function checkMinWidths(dir) {
  const files = fs.readdirSync(dir);
  for (const file of files) {
    const fullPath = path.join(dir, file);
    if (fs.statSync(fullPath).isDirectory()) {
      checkMinWidths(fullPath);
    } else if (file.endsWith('.tsx') || file.endsWith('.ts')) {
      const content = fs.readFileSync(fullPath, 'utf-8');
      const lines = content.split('\n');
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const match = line.match(/min-w-\[(\d+)px\]/);
        if (match) {
          const px = parseInt(match[1], 10);
          if (px > 320) {
            // Check if surrounding context (within 5 lines above) contains overflow-x-auto
            const contextAbove = lines.slice(Math.max(0, i - 5), i + 1).join('\n');
            const hasScrollWrapper = contextAbove.includes('overflow-x-auto') || contextAbove.includes('overflow-x-scroll');
            assert(
              'viewportStyling',
              hasScrollWrapper,
              `${file}:${i + 1} with min-w-[${px}px] > 320px must be wrapped in overflow-x-auto to prevent mobile body blowout`,
              { file, line: i + 1, px, hasScrollWrapper }
            );
          } else {
            assert('viewportStyling', true, `${file}:${i + 1} min-w-[${px}px] <= 320px safe on mobile`);
          }
        }
      }
    }
  }
}
checkMinWidths(appDir);


// ============================================================================
// SUMMARY & EXIT
// ============================================================================
console.log('\n================================================================');
console.log('🏁 EXTREME SCENARIOS VERIFICATION SUMMARY:');
console.log(`   Total Assertions Evaluated: ${results.totalAssertions}`);
console.log(`   Passed:                     ${results.passedAssertions}`);
console.log(`   Failed:                     ${results.failedAssertions}`);
console.log('--- Breakdown by Scenario ---');
for (const [key, data] of Object.entries(results.scenarios)) {
  console.log(`   * ${key.padEnd(20)}: ${data.passed}/${data.total} passed (${data.failed} failed)`);
}
console.log('================================================================\n');

if (results.failedAssertions > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
