import assert from 'node:assert';
import { getSubsidyDatabase, getRegionById, getModelById, calculateNetSubsidy, getCategoryDepletion } from '../src/lib/getSubsidyData.ts';

console.log('--- Testing Subsidy Audit & Edge Cases ---');

// Test 1: getSubsidyDatabase returns valid data
const db = getSubsidyDatabase();
assert(db && Array.isArray(db.regions), 'Database regions should be array');
console.log('✓ Test 1 Passed: Database structure is valid');

// Test 2: Handling null / undefined / empty region lookups
assert.strictEqual(getRegionById(null), undefined);
assert.strictEqual(getRegionById(undefined), undefined);
assert.strictEqual(getRegionById(''), undefined);
assert.strictEqual(getRegionById('non-existent-xyz'), undefined);
console.log('✓ Test 2 Passed: Null / undefined / invalid region queries gracefully return undefined');

// Test 3: Handling null / undefined / empty model lookups
assert.strictEqual(getModelById(null), undefined);
assert.strictEqual(getModelById(undefined), undefined);
assert.strictEqual(getModelById(''), undefined);
assert.strictEqual(getModelById('non-existent-model'), undefined);
console.log('✓ Test 3 Passed: Null / undefined / invalid model queries gracefully return undefined');

// Test 4: calculateNetSubsidy with invalid/null parameters
const resultDefault = calculateNetSubsidy(null, null);
assert(resultDefault && typeof resultDefault.netPurchasePriceKrw === 'number', 'Should return fallback calculation result');
assert(Number.isFinite(resultDefault.netPurchasePriceKrw), 'Net purchase price must be finite');
assert(Number.isFinite(resultDefault.depletionRate), 'Depletion rate must be finite');
assert(resultDefault.netPurchasePriceKrw >= 0, 'Net price must be non-negative');
console.log('✓ Test 4 Passed: calculateNetSubsidy defaults gracefully on null inputs');

// Test 5: Depletion rate edge case: 0 announced units (zero division prevention)
const zeroQuotaCategory = {
  announced_units: 0,
  applied_units: 10,
  delivered_units: 0,
  remaining_units: 0,
  depletion_rate: undefined, // test fallback
};
const dummyRegion = {
  region_id: 'KR-TEST',
  iso_code: 'KR-TEST',
  name_ko: '테스트시',
  name_en: 'Test City',
  tier: 'province',
  overall_depletion_rate: 0,
  overall_status: 'HEALTHY',
  residency_requirement_days: 30,
  supplementary_budget_added: false,
  categories: {
    passenger: zeroQuotaCategory,
    commercial: zeroQuotaCategory,
    bus: zeroQuotaCategory,
  },
  notes: '',
};

const depletionZeroQuota = getCategoryDepletion(dummyRegion, 'passenger');
assert.strictEqual(depletionZeroQuota.depletionRate, 0, 'Depletion rate must be 0 when announced units is 0 without throwing');
assert.strictEqual(depletionZeroQuota.remainingUnits, 0);
console.log('✓ Test 5 Passed: Zero quota handled without division by zero');

// Test 6: Depletion rate edge case: positive announced units with undefined depletion_rate
const normalQuotaNoRate = {
  announced_units: 1000,
  applied_units: 850,
  delivered_units: 700,
  remaining_units: undefined,
  depletion_rate: undefined,
};
const dummyRegion2 = {
  ...dummyRegion,
  categories: {
    passenger: normalQuotaNoRate,
    commercial: normalQuotaNoRate,
    bus: normalQuotaNoRate,
  },
};

const calculatedDepletion = getCategoryDepletion(dummyRegion2, 'passenger');
assert.strictEqual(calculatedDepletion.depletionRate, 85, 'Should calculate 85% when depletion_rate was undefined');
assert.strictEqual(calculatedDepletion.remainingUnits, 150, 'Should calculate 150 remaining units when remaining_units was undefined');
console.log('✓ Test 6 Passed: Dynamic fallback calculates depletion rate and remaining units accurately');

console.log('ALL SUBSIDY AUDIT TESTS PASSED!');
