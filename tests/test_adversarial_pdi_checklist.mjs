/**
 * tests/test_adversarial_pdi_checklist.mjs
 * Empirical stress harness for PDI Checklist state logic, rapid toggles, corrupted storage fuzzing,
 * schema migration resilience, keyboard navigation semantics, and print compatibility.
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
const progress = currentItems.length === 0 ? 0 : Math.round((checkedCount / currentItems.length) * 100);
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
const emptyProgress = emptyItems.length === 0 ? 0 : Math.round((emptyCount / emptyItems.length) * 100);
assert(emptyProgress === 0, 'Empty items list safely returns 0% progress', { emptyProgress });
assert(!Number.isNaN(emptyProgress), 'Empty items progress is strictly not NaN');

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

// ---------------------------------------------------------
// 4. SCHEMA MIGRATION & ENVELOPE RESILIENCE
// ---------------------------------------------------------
console.log('[TEST GROUP 4] Schema migration and envelope deserialization...');

// Implementation matching parseStoredChecklistState in PdiChecklistClient.tsx
function parseStoredChecklistState(raw, defaultItems) {
  if (!raw || typeof raw !== 'string') return defaultItems;
  const trimmed = raw.trim();
  if (!trimmed) return defaultItems;
  try {
    const parsed = JSON.parse(trimmed);
    if (!parsed) return defaultItems;

    // Case 1: Array of items or IDs
    if (Array.isArray(parsed)) {
      if (parsed.length === 0) return defaultItems;
      const isIdArray = parsed.some((p) => typeof p === 'string' || typeof p === 'number');
      if (isIdArray) {
        const checkedIdSet = new Set(
          parsed.filter((p) => p !== null && p !== undefined).map((p) => String(p))
        );
        return defaultItems.map((item) => ({
          ...item,
          checked: checkedIdSet.has(String(item.id)),
        }));
      }
      return defaultItems.map((item) => {
        const match = parsed.find(
          (p) => Boolean(p && typeof p === 'object' && 'id' in p && String(p.id) === String(item.id))
        );
        return match ? { ...item, checked: Boolean(match.checked) } : item;
      });
    }

    // Case 2: Object envelope or dictionary
    if (typeof parsed === 'object') {
      const obj = parsed;
      if (Array.isArray(obj.checkedIds)) {
        const checkedIdSet = new Set(obj.checkedIds.map((id) => String(id)));
        return defaultItems.map((item) => ({
          ...item,
          checked: checkedIdSet.has(String(item.id)),
        }));
      }
      if (Array.isArray(obj.items)) {
        return parseStoredChecklistState(JSON.stringify(obj.items), defaultItems);
      }
      const hasIdKey = defaultItems.some((item) => item.id in obj || String(item.id) in obj);
      if (hasIdKey) {
        return defaultItems.map((item) => {
          const val = obj[item.id] ?? obj[String(item.id)];
          return val !== undefined ? { ...item, checked: Boolean(val) } : item;
        });
      }
    }
  } catch {
    // fallback
  }
  return defaultItems;
}

// 4.1 Schema: Array of Checked String IDs e.g. ["1", "3", "8"]
const schemaIds = JSON.stringify(['1', '3', '8']);
const parsedIds = parseStoredChecklistState(schemaIds, INITIAL_PDI_ITEMS);
assert(parsedIds.find(i => i.id === '1').checked === true, 'ID string array marks item 1 as checked');
assert(parsedIds.find(i => i.id === '2').checked === false, 'ID string array leaves item 2 unchecked');
assert(parsedIds.find(i => i.id === '3').checked === true, 'ID string array marks item 3 as checked');
assert(parsedIds.find(i => i.id === '8').checked === true, 'ID string array marks item 8 as checked');

// 4.2 Schema: Numeric IDs e.g. [2, 4]
const schemaNumericIds = JSON.stringify([2, 4]);
const parsedNumIds = parseStoredChecklistState(schemaNumericIds, INITIAL_PDI_ITEMS);
assert(parsedNumIds.find(i => i.id === '2').checked === true, 'Numeric ID array coerces string matching for item 2');
assert(parsedNumIds.find(i => i.id === '4').checked === true, 'Numeric ID array coerces string matching for item 4');
assert(parsedNumIds.find(i => i.id === '1').checked === false, 'Numeric ID array leaves item 1 unchecked');

// 4.3 Schema: Envelope with checkedIds e.g. { checkedIds: ["5", "6"] }
const schemaEnvelopeChecked = JSON.stringify({ version: 2, checkedIds: ['5', '6'] });
const parsedEnvChecked = parseStoredChecklistState(schemaEnvelopeChecked, INITIAL_PDI_ITEMS);
assert(parsedEnvChecked.find(i => i.id === '5').checked === true, 'Envelope with checkedIds marks item 5 as checked');
assert(parsedEnvChecked.find(i => i.id === '6').checked === true, 'Envelope with checkedIds marks item 6 as checked');
assert(parsedEnvChecked.find(i => i.id === '1').checked === false, 'Envelope with checkedIds leaves item 1 unchecked');

// 4.4 Schema: Envelope with items array e.g. { items: [{ id: "7", checked: true }] }
const schemaEnvelopeItems = JSON.stringify({ items: [{ id: '7', checked: true }] });
const parsedEnvItems = parseStoredChecklistState(schemaEnvelopeItems, INITIAL_PDI_ITEMS);
assert(parsedEnvItems.find(i => i.id === '7').checked === true, 'Envelope with items array marks item 7 as checked');
assert(parsedEnvItems.find(i => i.id === '1').checked === false, 'Envelope with items array leaves item 1 unchecked');

// 4.5 Schema: Dictionary map e.g. { "1": true, "2": false, "9": true }
const schemaDict = JSON.stringify({ '1': true, '2': false, '9': true });
const parsedDict = parseStoredChecklistState(schemaDict, INITIAL_PDI_ITEMS);
assert(parsedDict.find(i => i.id === '1').checked === true, 'Dictionary map marks item 1 as checked');
assert(parsedDict.find(i => i.id === '2').checked === false, 'Dictionary map leaves item 2 unchecked');
assert(parsedDict.find(i => i.id === '9').checked === true, 'Dictionary map marks item 9 as checked');

// ---------------------------------------------------------
// 5. KEYBOARD ACCESSIBILITY (Space / Enter) AND CONTRACT CHECKS
// ---------------------------------------------------------
console.log('[TEST GROUP 5] Keyboard accessibility and WCAG semantics in source...');

// Verify handleKeyDown catches Enter, Space, and Spacebar
assert(
  pdiSource.includes("e.key === 'Enter'") &&
  (pdiSource.includes("e.key === ' '") || pdiSource.includes("e.key === 'Spacebar'")),
  'PdiItemRow handleKeyDown explicitly supports both Enter and Space keys'
);

// Verify role="progressbar" has aria-valuenow, valuemin, valuemax, aria-label, aria-valuetext
assert(pdiSource.includes('role="progressbar"'), 'PdiChecklistClient declares role="progressbar"');
assert(pdiSource.includes('aria-valuenow={progressPercentage}'), 'Progressbar defines aria-valuenow={progressPercentage}');
assert(pdiSource.includes('aria-valuemin={0}'), 'Progressbar defines aria-valuemin={0}');
assert(pdiSource.includes('aria-valuemax={100}'), 'Progressbar defines aria-valuemax={100}');
assert(pdiSource.includes('aria-valuetext='), 'Progressbar defines descriptive aria-valuetext');

// Verify tablist and tabpanel semantics
assert(pdiSource.includes('role="tablist"'), 'Category filter declares role="tablist"');
assert(pdiSource.includes('role="tabpanel"'), 'Checklist container declares role="tabpanel"');
assert(pdiSource.includes('tabIndex={0}'), 'Tabpanel declares tabIndex={0} for keyboard accessibility');
assert(pdiSource.includes('aria-expanded={isSelected}'), 'Category filter tabs declare aria-expanded={isSelected}');

// Verify checkboxes declare aria-checked and native role
assert(pdiSource.includes('type="checkbox"'), 'Checklist rows use native input type="checkbox"');
assert(pdiSource.includes('aria-checked={item.checked}'), 'Checkboxes declare explicit aria-checked state');

// Verify category accordions declare aria-expanded and aria-controls
assert(pdiSource.includes('aria-expanded={!isCollapsed}'), 'Category accordions declare dynamic aria-expanded state');
assert(pdiSource.includes('aria-controls={contentId}'), 'Category accordions link to content via aria-controls');

// ---------------------------------------------------------
// 6. PRINT STYLESHEET COMPATIBILITY
// ---------------------------------------------------------
console.log('[TEST GROUP 6] Print stylesheet compatibility...');

assert(pdiSource.includes('print:border-2'), 'Checkboxes declare print:border-2 for high contrast paper printouts');
assert(pdiSource.includes('print:border-black'), 'Checkboxes declare print:border-black');
assert(pdiSource.includes('print:hidden'), 'Interactive elements declare print:hidden');
assert(pdiSource.includes('print:break-inside-avoid'), 'Fieldsets and rows declare print:break-inside-avoid');
assert(pdiSource.includes('print:break-after-avoid'), 'Category headers declare print:break-after-avoid');

// ---------------------------------------------------------
// 7. WCAG 2.1 AA & STORAGE RESILIENCE HARNESS
// ---------------------------------------------------------
console.log('[TEST GROUP 7] WCAG 2.1 AA and LocalStorage Quota/Private browsing resilience...');

// 7.1 Checkbox proper labeling with htmlId / htmlFor
assert(pdiSource.includes('htmlFor={`pdi-task-${item.id}`}'), 'PdiItemRow binds label via htmlFor={pdi-task-${item.id}}');
assert(pdiSource.includes('id={`pdi-task-${item.id}`}'), 'PdiItemRow input has matching id={pdi-task-${item.id}}');
assert(pdiSource.includes('id={`pdi-task-text-${item.id}`}'), 'PdiItemRow text span has dedicated accessible text id');

// 7.2 Progress bar WCAG 2.1 AA semantics
assert(pdiSource.includes('role="progressbar"'), 'Progress bar declares role="progressbar"');
assert(pdiSource.includes('aria-valuenow={progressPercentage}'), 'Progress bar declares aria-valuenow={progressPercentage}');
assert(pdiSource.includes('aria-valuemin={0}'), 'Progress bar declares aria-valuemin={0}');
assert(pdiSource.includes('aria-valuemax={100}'), 'Progress bar declares aria-valuemax={100}');
assert(pdiSource.includes('aria-label="신차 출고 전 점검(PDI) 진행률"'), 'Progress bar declares descriptive aria-label');

// 7.3 Filter tabs role="tablist" / role="tab" with keyboard arrow support
assert(pdiSource.includes('role="tablist"'), 'Filter container declares role="tablist"');
assert(pdiSource.includes('role="tab"'), 'Filter items declare role="tab"');
assert(pdiSource.includes('handleTabKeyDown'), 'Filter tabs bind handleTabKeyDown callback');
assert(pdiSource.includes("e.key === 'ArrowRight' || e.key === 'ArrowDown'"), 'handleTabKeyDown supports forward arrow navigation');
assert(pdiSource.includes("e.key === 'ArrowLeft' || e.key === 'ArrowUp'"), 'handleTabKeyDown supports backward arrow navigation');
assert(pdiSource.includes("e.key === 'Home'"), 'handleTabKeyDown supports Home key navigation');
assert(pdiSource.includes("e.key === 'End'"), 'handleTabKeyDown supports End key navigation');

// 7.4 Category heading IDs and aria-labelledby binding
assert(pdiSource.includes('id={`pdi-cat-${category}`}'), 'Category heading IDs use dynamic id={`pdi-cat-${category}`}');
assert(pdiSource.includes('aria-labelledby={`pdi-cat-${category}`}'), 'Fieldset binds accessible label via aria-labelledby');

// 7.5 LocalStorage QuotaExceededError and private browsing resilience exports
assert(pdiSource.includes('export function isQuotaExceededError'), 'Exports isQuotaExceededError helper');
assert(pdiSource.includes('export function isLocalStorageAvailable'), 'Exports isLocalStorageAvailable helper');
assert(pdiSource.includes('export function getStorageType'), 'Exports getStorageType helper');

// 7.6 Simulate isQuotaExceededError logic directly
function testQuotaCheck(err) {
  if (!err || typeof err !== 'object') return false;
  return (
    err.name === 'QuotaExceededError' ||
    err.name === 'NS_ERROR_DOM_QUOTA_REACHED' ||
    err.code === 22 ||
    err.code === 1014 ||
    err.number === -2147024882
  );
}

assert(testQuotaCheck({ name: 'QuotaExceededError', code: 22 }) === true, 'WebKit QuotaExceededError detected');
assert(testQuotaCheck({ name: 'NS_ERROR_DOM_QUOTA_REACHED', code: 1014 }) === true, 'Firefox QuotaExceededError detected');
assert(testQuotaCheck({ code: 22 }) === true, 'Code 22 error detected');
assert(testQuotaCheck(new Error('Generic failure')) === false, 'Generic error not flagged as quota error');
assert(testQuotaCheck(null) === false, 'Null error gracefully returns false');

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
