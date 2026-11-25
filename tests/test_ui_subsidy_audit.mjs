import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const clientPath = path.resolve('src/app/subsidy-tracker/SubsidyTrackerClient.tsx');
const tablePath = path.resolve('src/components/subsidy/SubsidyTableView.tsx');

const clientCode = fs.readFileSync(clientPath, 'utf8');
const tableCode = fs.readFileSync(tablePath, 'utf8');

// 1. Zone filter toggle contract: clicking active zone toggles back to 'ALL' and 'ALL' has accurate aria-label
assert.ok(
  clientCode.includes("setZoneFilter((prev) => (zone === 'ALL' || prev === zone ? 'ALL' : zone))"),
  'handleSelectZone must toggle active zone back to ALL'
);
assert.ok(
  clientCode.includes("zone.id === 'ALL'") && clientCode.includes("'전국 전체 권역 보기'"),
  'ALL zone button must declare accurate non-toggleable aria-label'
);

// 2. Native WebKit search cancel icon suppression when custom clear button is rendered
assert.ok(
  clientCode.includes('[&::-webkit-search-cancel-button]:hidden'),
  'Search input must suppress native webkit cancel button to avoid overlapping custom clear button'
);

// 3. Safe non-negative fallback for custom MSRP base price
assert.ok(
  clientCode.includes('toSafeNonNeg(activeModel?.base_price_krw)'),
  'Custom MSRP calculation fallback must guard negative/non-finite model base price via toSafeNonNeg'
);

// 4. Whitespace-safe regionKey derivation in both grid and table views
assert.ok(
  clientCode.includes("typeof regionItem.region_id === 'string' && regionItem.region_id.trim()"),
  'SubsidyTrackerClient must trim region_id before using it as React key / DOM ID seed'
);
assert.ok(
  tableCode.includes("typeof region.region_id === 'string' && region.region_id.trim()"),
  'SubsidyTableView must trim region_id before using it as React key / DOM ID seed'
);

console.log('ALL ui-subsidy REGRESSION AUDIT CHECKS PASSED!');
