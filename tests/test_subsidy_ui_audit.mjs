import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { getBadgeStyle, getStatusLabel } from '../src/lib/subsidyCalculations.ts';

console.log('--- Testing Subsidy UI Client & Table Comprehensive Audit ---');

// Test 1: getBadgeStyle & getStatusLabel Mapping & Edge Cases
console.log('Testing Test 1: Status badge label & styling mapper');
const statusExpectations = [
  { input: 'HEALTHY', expectedLabel: '🟢 안정', containsStyle: 'bg-emerald-950 text-emerald-200' },
  { input: 'AVAILABLE', expectedLabel: '🟢 안정', containsStyle: 'bg-emerald-950 text-emerald-200' },
  { input: 'available', expectedLabel: '🟢 안정', containsStyle: 'bg-emerald-950 text-emerald-200' },
  { input: 'CAUTION', expectedLabel: '🟡 주의', containsStyle: 'bg-amber-950 text-amber-200' },
  { input: 'WARNING', expectedLabel: '🟠 경고', containsStyle: 'bg-orange-950 text-orange-200' },
  { input: 'CRITICAL', expectedLabel: '🔴 마감임박', containsStyle: 'bg-rose-950 text-rose-200' },
  { input: 'DANGER', expectedLabel: '🔴 마감임박', containsStyle: 'bg-rose-950 text-rose-200' },
  { input: 'EMERGENCY', expectedLabel: '🔴 마감임박', containsStyle: 'bg-rose-950 text-rose-200' },
  { input: 'DEPLETED', expectedLabel: '🔒 소진', containsStyle: 'bg-slate-950 text-slate-100' },
  { input: 'CLOSED', expectedLabel: '🔒 소진', containsStyle: 'bg-slate-950 text-slate-100' },
  { input: 'EXHAUSTED', expectedLabel: '🔒 소진', containsStyle: 'bg-slate-950 text-slate-100' },
  { input: 'END', expectedLabel: '🔒 소진', containsStyle: 'bg-slate-950 text-slate-100' },
  { input: null, expectedLabel: '🟢 안정', containsStyle: 'bg-emerald-950 text-emerald-200' },
  { input: undefined, expectedLabel: '🟢 안정', containsStyle: 'bg-emerald-950 text-emerald-200' },
  { input: '', expectedLabel: '🟢 안정', containsStyle: 'bg-emerald-950 text-emerald-200' },
];

for (const testCase of statusExpectations) {
  const label = getStatusLabel(testCase.input);
  const style = getBadgeStyle(testCase.input);
  assert.strictEqual(label, testCase.expectedLabel, `Failed label for status: ${testCase.input}`);
  assert(style.includes(testCase.containsStyle), `Failed style for status: ${testCase.input}. Got: ${style}`);
}
console.log('✓ Test 1 Passed: All badge styles and status labels accurately resolved with resilient edge-case handling');

// Test 2: WCAG AA Color Contrast Ratio Verification
console.log('Testing Test 2: Contrast Ratio Verification for WCAG 2.1 AA Compliance');
function getRelativeLuminance(r, g, b) {
  const [rs, gs, bs] = [r, g, b].map((c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
}

function getContrastRatio(rgb1, rgb2) {
  const l1 = getRelativeLuminance(...rgb1);
  const l2 = getRelativeLuminance(...rgb2);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

// Tailwind color definitions used in badges:
// emerald-950: rgb(2, 44, 34), emerald-200: rgb(167, 243, 208)
// amber-950: rgb(69, 26, 3), amber-200: rgb(253, 230, 138)
// orange-950: rgb(67, 20, 7), orange-200: rgb(254, 215, 170)
// rose-950: rgb(76, 5, 25), rose-200: rgb(254, 205, 211)
// slate-950: rgb(2, 6, 23), slate-100: rgb(241, 245, 249)

const badgeColorPairs = [
  { name: 'HEALTHY (emerald)', bg: [2, 44, 34], text: [167, 243, 208] },
  { name: 'CAUTION (amber)', bg: [69, 26, 3], text: [253, 230, 138] },
  { name: 'WARNING (orange)', bg: [67, 20, 7], text: [254, 215, 170] },
  { name: 'CRITICAL (rose)', bg: [76, 5, 25], text: [254, 205, 211] },
  { name: 'DEPLETED (slate)', bg: [2, 6, 23], text: [241, 245, 249] },
];

for (const pair of badgeColorPairs) {
  const ratio = getContrastRatio(pair.bg, pair.text);
  assert(ratio >= 4.5, `${pair.name} contrast ratio ${ratio.toFixed(2)}:1 must meet WCAG AA minimum 4.5:1`);
  assert(ratio >= 7.0, `${pair.name} contrast ratio ${ratio.toFixed(2)}:1 must meet WCAG AAA standard 7.0:1`);
}
console.log('✓ Test 2 Passed: All status badge color pairs exceed WCAG 2.1 AAA requirement (> 7:1 ratio)');

// Test 3: Static Code Analysis of SubsidyTableView.tsx for WCAG Standards
console.log('Testing Test 3: Static Code Analysis of SubsidyTableView.tsx');
const tableViewCode = fs.readFileSync(path.resolve('src/components/subsidy/SubsidyTableView.tsx'), 'utf-8');

// Check aria-sort on th headers
assert(tableViewCode.includes("aria-sort={getSortAria('NAME', sortOption)}"), 'Missing aria-sort on NAME header');
assert(tableViewCode.includes("aria-sort={getSortAria('REMAINING', sortOption)}"), 'Missing aria-sort on REMAINING header');
assert(tableViewCode.includes("aria-sort={getSortAria('DEPLETION', sortOption)}"), 'Missing aria-sort on DEPLETION header');
assert(tableViewCode.includes("aria-sort={getSortAria('LOCAL_SUBSIDY', sortOption)}"), 'Missing aria-sort on LOCAL_SUBSIDY header');

// Check table scope attributes
assert(tableViewCode.includes('scope="col"'), 'Missing scope="col" on column headers');
assert(tableViewCode.includes('scope="row"'), 'Missing scope="row" on row headers');

// Check caption element for screen readers
assert(tableViewCode.includes('<caption className="sr-only">'), 'Missing caption for table accessibility');

// Check mobile responsiveness features
assert(tableViewCode.includes('sticky left-0'), 'Missing sticky column for mobile scroll');
assert(tableViewCode.includes('shadow-[2px_0_8px_rgba(0,0,0,0.4)]'), 'Missing sticky column drop shadow indicator');
assert(tableViewCode.includes('overflow-x-auto'), 'Missing overflow-x-auto table container');
assert(tableViewCode.includes('table-scroll-container'), 'Missing table-scroll-container class');

// Check touch targets (min-h-[44px])
assert(tableViewCode.includes('min-h-[44px]'), 'Missing touch target sizing (min-h-[44px]) on interactive table buttons');

console.log('✓ Test 3 Passed: SubsidyTableView conforms to WCAG 2.1 AA (aria-sort, scope, caption, sticky column, touch targets)');

// Test 4: Static Code Analysis of SubsidyTrackerClient.tsx for Search Debouncing & Empty State
console.log('Testing Test 4: Static Code Analysis of SubsidyTrackerClient.tsx');
const clientCode = fs.readFileSync(path.resolve('src/app/subsidy-tracker/SubsidyTrackerClient.tsx'), 'utf-8');

// Check search debouncing
assert(clientCode.includes('debouncedQuery'), 'Missing debouncedQuery state in SubsidyTrackerClient');
assert(clientCode.includes('useDeferredValue(debouncedQuery)'), 'deferredSearchQuery must be hooked to debouncedQuery');

// Check persistent filter feedback status element for aria-describedby
assert(clientCode.includes('id="filter-feedback-status"'), 'Missing id="filter-feedback-status" for input aria-describedby');
assert(clientCode.includes('role="status"'), 'Missing role="status" on filter feedback');
assert(clientCode.includes('aria-live="polite"'), 'Missing aria-live="polite" on filter feedback');

// Check diagnostic empty-state chips
assert(clientCode.includes('Diagnostic Filter Chips'), 'Missing diagnostic empty state filter chips');
assert(clientCode.includes('handleClearZoneFilter'), 'Missing handleClearZoneFilter callback');
assert(clientCode.includes('handleClearAlertFilter'), 'Missing handleClearAlertFilter callback');
assert(clientCode.includes('handleClearSupplementaryFilter'), 'Missing handleClearSupplementaryFilter callback');

// Check unique sub-municipality IDs (preventing ID collisions between Grid and Table views)
assert(clientCode.includes('muni-details-card-'), 'Missing unique muni-details-card- prefix in RegionCard');
assert(tableViewCode.includes('muni-details-table-'), 'Missing unique muni-details-table- prefix in SubsidyTableView');

console.log('✓ Test 4 Passed: SubsidyTrackerClient debouncing, persistent aria-describedby, and empty-state diagnostics verified');

console.log('\n========================================');
console.log('ALL SUBSIDY UI CLIENT & TABLE AUDIT TESTS PASSED WITH 100% SUCCESS!');
console.log('========================================');
