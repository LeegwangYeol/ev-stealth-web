/**
 * tests/test_adversarial_pdi_checklist.mjs
 * Empirical stress harness for PDI Checklist state logic, rapid toggles, and corrupted storage fuzzing.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Extract INITIAL_PDI_ITEMS directly from PdiChecklistClient.tsx source
const pdiSource = fs.readFileSync(path.resolve(__dirname, '../src/app/pdi-checklist/PdiChecklistClient.tsx'), 'utf-8');
const match = pdiSource.match(/export const INITIAL_PDI_ITEMS: ChecklistItem\[\] = (\[[\s\S]*?\n\]);/);
if (!match) {
  throw new Error('Failed to extract INITIAL_PDI_ITEMS from PdiChecklistClient.tsx');
}

// Evaluate cleanly as JS object
const INITIAL_PDI_ITEMS = eval(match[1]);
console.log(`[PDI HARNESS] Extracted ${INITIAL_PDI_ITEMS.length} default PDI checklist items from PdiChecklistClient.tsx.`);

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
// 1. RAPID TOGGLE STRESS TEST (10,000 toggles)
// ---------------------------------------------------------
console.log('[TEST GROUP 1] Rapid state toggles (10,000 operations)...');

let currentItems = [...INITIAL_PDI_ITEMS];

function toggleCheck(items, id) {
  return items.map((item) =>
    item.id === id ? { ...item, checked: !item.checked } : item
  );
}

// Toggle item '1' exactly 10,000 times (even number -> must return to false)
for (let i = 0; i < 10000; i++) {
  currentItems = toggleCheck(currentItems, '1');
}

const item1 = currentItems.find((i) => i.id === '1');
assert(item1.checked === false, '10,000 toggles of item 1 must result in checked === false', { checked: item1.checked });

// Toggle item '1' once more -> must be true
currentItems = toggleCheck(currentItems, '1');
assert(currentItems.find((i) => i.id === '1').checked === true, 'Odd number of toggles must result in checked === true');

// Rapid random toggles across all items
for (let i = 0; i < 50000; i++) {
  const randomId = String(Math.floor(Math.random() * INITIAL_PDI_ITEMS.length) + 1);
  currentItems = toggleCheck(currentItems, randomId);
}

// Progress calculation verification
const checkedCount = currentItems.filter((i) => i.checked).length;
const progress = Math.round((checkedCount / currentItems.length) * 100);
assert(!Number.isNaN(progress), 'Progress must be a valid number after 50,000 random toggles', { progress, checkedCount });
assert(progress >= 0 && progress <= 100, `Progress ${progress}% must be bounded within [0, 100]`);

// ---------------------------------------------------------
// 2. CORRUPTED LOCALSTORAGE RECOVERY SIMULATION
// ---------------------------------------------------------
console.log('[TEST GROUP 2] Corrupted storage deserialization recovery...');

function simulateHydration(savedRawString) {
  let loadedItems = INITIAL_PDI_ITEMS;
  try {
    if (savedRawString) {
      const parsed = JSON.parse(savedRawString);
      if (Array.isArray(parsed)) {
        loadedItems = INITIAL_PDI_ITEMS.map((item) => {
          const match = parsed.find((p) => p && p.id === item.id);
          return match ? { ...item, checked: Boolean(match.checked) } : item;
        });
      }
    }
  } catch (e) {
    // Graceful fallback to initial
    loadedItems = INITIAL_PDI_ITEMS;
  }
  return loadedItems;
}

// A. Syntax Error / Broken JSON
const corrupted1 = '{ bad: "json", ';
const res1 = simulateHydration(corrupted1);
assert(res1.length === INITIAL_PDI_ITEMS.length, 'Broken JSON recovers to default items count');
assert(res1.every(i => !i.checked), 'Broken JSON results in unchecked default items');

// B. Non-Array JSON (object or primitive)
const corrupted2 = '{"id": "1", "checked": true}';
const res2 = simulateHydration(corrupted2);
assert(res2.length === INITIAL_PDI_ITEMS.length, 'Object JSON recovers to default items count');
assert(res2.every(i => !i.checked), 'Object JSON does not crash array handling');

// C. Array with nulls or primitives
const corrupted3 = '[null, 123, "string", {"id": "1", "checked": 1}]';
const res3 = simulateHydration(corrupted3);
assert(res3.length === INITIAL_PDI_ITEMS.length, 'Dirty array recovers cleanly');
assert(res3.find(i => i.id === '1').checked === true, 'Dirty array correctly casts truthy checked value');
assert(res3.find(i => i.id === '2').checked === false, 'Dirty array leaves missing items unchecked');

// D. Empty list edge case in progress bar (division by zero test)
const emptyItems = [];
const emptyCount = emptyItems.filter(i => i.checked).length;
const emptyProgress = Math.round((emptyCount / emptyItems.length) * 100);
if (Number.isNaN(emptyProgress)) {
  console.log('[EDGE CASE OBSERVED] Empty items array causes NaN in progress calculation (0 / 0 = NaN)');
  suiteResults.findings.push({
    type: 'POTENTIAL_NAN_ON_EMPTY_LIST',
    detail: 'If items array is empty, (checkedCount / items.length) * 100 yields NaN'
  });
}

// ---------------------------------------------------------
// 3. CATEGORY AGGREGATION & UNIQUENESS
// ---------------------------------------------------------
console.log('[TEST GROUP 3] Category grouping integrity...');
const categories = Array.from(new Set(INITIAL_PDI_ITEMS.map((i) => i.category)));
assert(categories.length === 4, `Expected 4 distinct categories, got ${categories.length}`, categories);
for (const cat of categories) {
  const catItems = INITIAL_PDI_ITEMS.filter(i => i.category === cat);
  assert(catItems.length >= 2, `Category "${cat}" has at least 2 items`, { count: catItems.length });
}

console.log('\n======================================================');
console.log(`[PDI HARNESS FINISHED] Total tests: ${suiteResults.totalTests}`);
console.log(`Passed: ${suiteResults.passed}, Failed: ${suiteResults.failed}`);
console.log(`Findings count: ${suiteResults.findings.length}`);
console.log('======================================================');

if (suiteResults.failed > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
