import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import * as recallCalc from '../src/lib/recallCalculations.ts';
import * as getRecall from '../src/lib/getRecallData.ts';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

console.log('================================================================');
console.log('🔬 RECALL PORTAL FRONTEND COMPREHENSIVE AUDIT TEST SUITE');
console.log('================================================================\n');

const recallPortalClientPath = join(__dirname, '../src/app/recall-portal/RecallPortalClient.tsx');
const recallPortalClientCode = readFileSync(recallPortalClientPath, 'utf8');

const exportWrapperPath = join(__dirname, '../src/components/RecallPortalClient.tsx');
const exportWrapperCode = readFileSync(exportWrapperPath, 'utf8');

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
// 1. VIN SEARCH INPUT FORMATTING, PATTERN & CHECKSUM VALIDATION
// ============================================================================
console.log('--- [1. VIN Search Input Formatting & Validation] ---');

runTest('VIN normalization removes hyphens, spaces, and uppercases characters', () => {
  const dirtyVin = '  km8-kn4-ae4-nu-123456  ';
  const val = recallCalc.validateVinString(dirtyVin);
  assert.equal(val.valid, true);
  assert.equal(val.normalized, 'KM8KN4AE4NU123456');
  assert.equal(val.normalized.length, 17);
});

runTest('VIN pattern enforces exactly 17 characters and disallows I, O, Q', () => {
  // Disallowed chars
  assert.equal(recallCalc.validateVinString('KM8KN4AE4NU12345I').valid, false);
  assert.equal(recallCalc.validateVinString('KM8KN4AE4NU12345O').valid, false);
  assert.equal(recallCalc.validateVinString('KM8KN4AE4NU12345Q').valid, false);

  // Boundary lengths
  assert.equal(recallCalc.validateVinString('KM8KN4AE4NU12345').valid, false); // 16 chars
  assert.equal(recallCalc.validateVinString('KM8KN4AE4NU1234567').valid, false); // 18 chars

  // Non-alphanumeric
  assert.equal(recallCalc.validateVinString('KM8KN4AE4NU12345@').valid, false);
});

runTest('ISO / US NHTSA check digit calculation (modulo 11 algorithm)', () => {
  // Verified check digit test vector: Mercedes W1K297123PF123456 (9th digit is '3')
  const checkDigit1 = recallCalc.calculateVinCheckDigit('W1K297123PF123456');
  assert.equal(checkDigit1, '3');

  const verify1 = recallCalc.verifyVinChecksum('W1K297123PF123456');
  assert.equal(verify1.isValidCheckDigit, true);
  assert.equal(verify1.expectedCheckDigit, '3');
  assert.equal(verify1.actualCheckDigit, '3');

  // Verify check digit X for remainder 10: KM8KN4AE4NU123456 (calc=X, actual=4)
  const checkDigitX = recallCalc.calculateVinCheckDigit('KM8KN4AE4NU123456');
  assert.equal(checkDigitX, 'X');
  const verifyX = recallCalc.verifyVinChecksum('KM8KN4AE4NU123456');
  assert.equal(verifyX.isValidCheckDigit, false);
  assert.equal(verifyX.expectedCheckDigit, 'X');
  assert.equal(verifyX.actualCheckDigit, '4');

  // getRecallData exports identical check digit functions
  assert.equal(getRecall.calculateVinCheckDigit('W1K297123PF123456'), '3');
  assert.equal(getRecall.verifyVinChecksum('W1K297123PF123456').isValidCheckDigit, true);
});

runTest('VIN input UI declares maxLength 17, counter, autocomplete off, and live status', () => {
  assert.ok(recallPortalClientCode.includes('maxLength={17}'), 'VIN input specifies maxLength 17');
  assert.ok(recallPortalClientCode.includes('{vinInput.replace(/[\\s-]/g, \'\').length}/17'), 'Live character counter present');
  assert.ok(recallPortalClientCode.includes('autoComplete="off"'), 'VIN input disables autocomplete');
  assert.ok(recallPortalClientCode.includes('spellCheck={false}'), 'VIN input disables spellCheck');
  assert.ok(recallPortalClientCode.includes('autoCapitalize="characters"'), 'VIN input autoCapitalizes characters');
  assert.ok(recallPortalClientCode.includes('aria-describedby={vinError ? "vin-error-feedback vin-format-hint" : "vin-format-hint"}'), 'Dynamic aria-describedby linkage');
  assert.ok(recallPortalClientCode.includes('id="vin-error-feedback" role="alert" aria-live="assertive"'), 'Error feedback uses role="alert"');
  assert.ok(recallPortalClientCode.includes('role="status" aria-live="polite" className="mt-2 text-xs text-emerald-400'), 'Success feedback uses role="status" and polite live region');
  assert.ok(recallPortalClientCode.includes('북미/ISO 9번째 체크섬 일치'), 'Checksum match indicator provided in UI');
});

// ============================================================================
// 2. FILTERS: BRAND SELECTOR, RECALL CATEGORIES & SEVERITY TAGS
// ============================================================================
console.log('\n--- [2. Filters: Brand Selector, Categories & Severity Tags] ---');

runTest('Mode B Brand selector populates distinct brands and triggers cascading model updates', () => {
  const db = getRecall.getRecallDatabase();
  const brands = recallCalc.getDistinctBrands(db);
  assert.ok(brands.length >= 6, `Expected at least 6 distinct brands, found ${brands.length}`);
  assert.ok(brands.includes('현대자동차'));
  assert.ok(brands.includes('테슬라'));
  assert.ok(brands.includes('기아'));
  assert.ok(brands.includes('메르세데스-벤츠'));

  const hyundaiModels = recallCalc.getModelsForBrand('현대자동차', db);
  assert.ok(hyundaiModels.length > 0);
  assert.ok(hyundaiModels.some((m) => m.includes('아이오닉')));

  // Code inspection for brand selector in Mode B
  assert.ok(recallPortalClientCode.includes('<select\n                      id="brand-select"'), 'Brand select dropdown present in Mode B');
  assert.ok(recallPortalClientCode.includes('getModelsForBrand(newBrand, initialDatabase)'), 'Cascades to update models on brand change');
});

runTest('Recalls catalog provides dedicated Brand filter selector', () => {
  assert.ok(
    recallPortalClientCode.includes('role="group" aria-label="제조사 브랜드별 리콜 필터"'),
    'Recalls catalog declares role="group" for brand filter'
  );
  assert.ok(
    recallPortalClientCode.includes('id="recall-brand-filter"'),
    'Recalls catalog has brand filter select element'
  );
  assert.ok(
    recallPortalClientCode.includes('selectedRecallBrandFilter'),
    'Recalls catalog uses selectedRecallBrandFilter state'
  );
});

runTest('Recall categories cover 배터리, 모터, 브레이크, and 소프트웨어', () => {
  // Category mapping
  assert.ok(recallPortalClientCode.includes('FIRE_HAZARD'), 'FIRE_HAZARD category present (배터리/화재)');
  assert.ok(recallPortalClientCode.includes('LOSS_OF_POWER'), 'LOSS_OF_POWER category present (모터/ICCU)');
  assert.ok(recallPortalClientCode.includes('BRAKE_STEERING'), 'BRAKE_STEERING category present (브레이크/제동)');
  assert.ok(recallPortalClientCode.includes('SOFTWARE_REGULATION'), 'SOFTWARE_REGULATION category present (소프트웨어)');

  // Enriched token search matches Korean category terms in defect titles and details
  const db = getRecall.getRecallDatabase();
  const batteryRecalls = db.recalls.filter((r) =>
    r.risk_level === 'FIRE_HAZARD' || r.defect_title.includes('배터리') || r.defect_detail.includes('배터리')
  );
  assert.ok(batteryRecalls.length > 0, 'Found official battery recalls');

  const motorRecalls = db.recalls.filter((r) =>
    r.risk_level === 'LOSS_OF_POWER' || r.defect_title.includes('ICCU') || r.defect_detail.includes('동력')
  );
  assert.ok(motorRecalls.length > 0, 'Found official motor/ICCU power loss recalls');

  const brakeRecalls = db.recalls.filter((r) =>
    r.risk_level === 'BRAKE_STEERING' || r.defect_title.includes('제동') || r.defect_detail.includes('브레이크')
  );
  assert.ok(brakeRecalls.length > 0, 'Found official brake/steering recalls');

  const softwareRecalls = db.recalls.filter((r) =>
    r.risk_level === 'SOFTWARE_REGULATION' || r.remedy_type === 'OTA_WIRELESS' || r.defect_title.includes('소프트웨어')
  );
  assert.ok(softwareRecalls.length > 0, 'Found official software recalls');
});

runTest('Severity tags and badges declare accessible WCAG AA contrast colors', () => {
  assert.ok(recallPortalClientCode.includes('text-rose-200 border-red-700'), 'Critical badge color');
  assert.ok(recallPortalClientCode.includes('text-amber-200 border-amber-700'), 'Warning badge color');
  assert.ok(recallPortalClientCode.includes('text-emerald-200 border-emerald-700'), 'Safe badge color');
});

// ============================================================================
// 3. TABLE ACCESSIBILITY, EXPANDABLE ROWS & MOBILE RESPONSIVENESS
// ============================================================================
console.log('\n--- [3. Table Accessibility, Expandable Rows & Mobile Responsiveness] ---');

runTest('View toggles allow switching between Card View and Table View in both directories', () => {
  // Battery Directory view switcher
  assert.ok(
    recallPortalClientCode.includes('role="group" aria-label="배터리 제원 보기 방식 선택"'),
    'Battery directory provides view switcher'
  );
  assert.ok(
    recallPortalClientCode.includes('batteryViewMode === \'table\''),
    'Battery directory renders BatterySafetyTableView when table mode active'
  );
  assert.ok(
    recallPortalClientCode.includes('<BatterySafetyTableView profiles={displayedBatteryProfiles} />'),
    'BatterySafetyTableView is dynamically rendered'
  );

  // Recalls Catalog view switcher
  assert.ok(
    recallPortalClientCode.includes('role="group" aria-label="리콜 캠페인 목록 보기 방식 선택"'),
    'Recalls catalog provides view switcher'
  );
  assert.ok(
    recallPortalClientCode.includes('recallViewMode === \'table\''),
    'Recalls catalog renders RecallTableView when table mode active'
  );
  assert.ok(
    recallPortalClientCode.includes('<RecallTableView'),
    'RecallTableView is dynamically rendered'
  );
});

runTest('Table components follow WAI-ARIA and semantic HTML standards', () => {
  // Semantic table structure in BatterySafetyTableView
  assert.ok(recallPortalClientCode.includes('<caption className="sr-only">'), 'Tables declare accessible caption');
  assert.ok(recallPortalClientCode.includes('<th scope="col"'), 'Column headers declare scope="col"');
  assert.ok(recallPortalClientCode.includes('<th scope="row"'), 'Row headers declare scope="row"');

  // Scroll containers declare region landmark and focusability
  assert.ok(
    recallPortalClientCode.includes('role="region"'),
    'Scroll container declares role="region"'
  );
  assert.ok(
    recallPortalClientCode.includes('tabIndex={0}'),
    'Scroll container allows keyboard focus via tabIndex={0}'
  );
});

runTest('Expandable table rows preserve valid aria-controls and handle Escape key navigation', () => {
  // Valid DOM reference preservation
  assert.ok(
    recallPortalClientCode.includes('hidden={!isExpanded}'),
    'Expandable row details must stay in DOM with hidden={!isExpanded} to preserve valid aria-controls'
  );

  // Keyboard navigation & Escape handling
  assert.ok(
    recallPortalClientCode.includes('e.key === \'Escape\' && isExpanded'),
    'Escape key dismisses expanded table row'
  );
  assert.ok(
    recallPortalClientCode.includes('id={`table-toggle-${campaign.id}`}'),
    'Toggle buttons declare predictable IDs for focus restoration'
  );

  // Detail container region landmark
  assert.ok(
    recallPortalClientCode.includes('aria-labelledby={`table-toggle-${campaign.id}`}'),
    'Table detail panel links back to button via aria-labelledby'
  );
});

runTest('Touch targets in Table and Card views enforce min-h-[44px] standard', () => {
  assert.ok(
    recallPortalClientCode.includes('min-h-[44px] min-w-[44px]'),
    'Table row expand buttons declare min-h-[44px] min-w-[44px]'
  );
  const minH44Occurrences = (recallPortalClientCode.match(/min-h-\[44px\]/g) || []).length;
  assert.ok(
    minH44Occurrences >= 25,
    `Expected at least 25 min-h-[44px] interactive elements, found ${minH44Occurrences}`
  );
});

runTest('Mobile horizontal scroll indicators guide small-screen users', () => {
  assert.ok(
    recallPortalClientCode.includes('가로 스크롤 ↔'),
    'Horizontal scroll indicator present for mobile viewports'
  );
  assert.ok(
    recallPortalClientCode.includes('overflow-x-auto table-scroll-container'),
    'Table containers declare overflow-x-auto and custom scroll styles'
  );
});

// ============================================================================
// 4. COMPONENT RE-EXPORT WRAPPER INTEGRITY
// ============================================================================
console.log('\n--- [4. Component Re-Export Wrapper Integrity] ---');

runTest('src/components/RecallPortalClient.tsx re-exports all views and prop types', () => {
  assert.ok(exportWrapperCode.includes('RecallCard'), 'Re-exports RecallCard');
  assert.ok(exportWrapperCode.includes('BatterySafetyCard'), 'Re-exports BatterySafetyCard');
  assert.ok(exportWrapperCode.includes('BatterySafetyTableView'), 'Re-exports BatterySafetyTableView');
  assert.ok(exportWrapperCode.includes('RecallTableView'), 'Re-exports RecallTableView');
  assert.ok(exportWrapperCode.includes('RecallCardProps'), 'Re-exports RecallCardProps');
  assert.ok(exportWrapperCode.includes('BatterySafetyCardProps'), 'Re-exports BatterySafetyCardProps');
  assert.ok(exportWrapperCode.includes('BatterySafetyTableViewProps'), 'Re-exports BatterySafetyTableViewProps');
  assert.ok(exportWrapperCode.includes('RecallTableViewProps'), 'Re-exports RecallTableViewProps');
});

console.log('\n================================================================');
console.log(`🏁 RECALL PORTAL AUDIT SUITE FINISHED: ${passedTests}/${totalTests} PASSED`);
console.log('================================================================\n');

if (passedTests !== totalTests) {
  process.exit(1);
} else {
  process.exit(0);
}
