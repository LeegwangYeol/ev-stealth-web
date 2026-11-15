/**
 * Comprehensive Audit Test Suite for Reliability Analytics UI Client
 * Tests:
 * 1. WCAG 2.1 AA Compliance: Tablist APG Pattern (aria-selected, aria-controls, hidden panels, key navigation)
 * 2. Heatmap Matrix Selection isolation (only selected model's year is highlighted, avoiding cross-model highlighting)
 * 3. Screen Reader Alternatives for Data Visualizations (Heatmap, Brand Bar Chart, Category Stacked Bar)
 * 4. SVG Chart Accessibility (role="img"/role="group", <title>, <desc>, keyboard-focusable interactive elements)
 * 5. Touch Targets (min 44px for interactive buttons)
 * 6. Responsive Table Horizontal Scroll containers with role="region" and tabIndex={0}
 * 7. Edge-case Math Guards (safe DSI subtraction, NaN guards, zero-division prevention)
 */

import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const CLIENT_FILE = path.resolve(__dirname, '../src/app/reliability-analytics/ReliabilityDashboardClient.tsx');
const PAGE_FILE = path.resolve(__dirname, '../src/app/reliability-analytics/page.tsx');

console.log('🧪 Starting Reliability Dashboard UI Client Audit Test Suite...');

const clientCode = fs.readFileSync(CLIENT_FILE, 'utf-8');
const pageCode = fs.readFileSync(PAGE_FILE, 'utf-8');

// Test 1: Page metadata, JSON-LD schema, and Suspense Boundary
console.log('Test 1: Validating page.tsx Static Pre-rendering & Schema.org Metadata...');
assert(pageCode.includes('export const dynamic = \'force-static\''), 'page.tsx must enforce static generation');
assert(pageCode.includes('WebApplication'), 'JSON-LD must define WebApplication schema');
assert(pageCode.includes('Suspense'), 'page.tsx must provide Suspense fallback for client dashboard');

// Test 2: WCAG APG Tabs Pattern
console.log('Test 2: Validating WAI-ARIA 1.2 APG Tabs Pattern Implementation...');
assert(clientCode.includes('role="tablist"'), 'Chart section must define role="tablist"');
assert(clientCode.includes('role="tab"'), 'Tab buttons must have role="tab"');
assert(clientCode.includes('aria-controls="chart-tabpanel"'), 'Tab buttons must reference matching chart-tabpanel');
assert(clientCode.includes('id="chart-tabpanel"'), 'chart-tabpanel must exist in DOM');
assert(clientCode.includes('aria-labelledby={`chart-tab-${activeChartTab}`}'), 'Tabpanel must have dynamic aria-labelledby pointing to active tab');
assert(clientCode.includes('handleChartTabKeyDown'), 'Tablist must implement keyboard navigation handler');

// Test 3: Heatmap Row Selection Isolation
console.log('Test 3: Validating Heatmap Selection Logic and Memoization Props...');
assert(
  clientCode.includes('selectedYear={hoveredCell?.modelName === model.name ? hoveredCell.year : null}'),
  'HeatmapRow must receive model-specific selectedYear to avoid highlighting all models on year click'
);
assert(clientCode.includes('React.memo(function HeatmapRow'), 'HeatmapRow must be memoized with React.memo');

// Test 4: Screen Reader Accessible Table Alternatives for Visual Charts
console.log('Test 4: Validating Screen Reader Alternatives for Data Visualizations...');
assert(clientCode.includes('전기차 제조사 브랜드별 결함 심각도 지수 랭킹 데이터 표'), 'Brand ranking must provide sr-only data table');
assert(clientCode.includes('전기차 결함 부문별 산업 점유율 데이터 표'), 'Category share must provide sr-only data table');
assert(clientCode.includes('caption className="sr-only"'), 'Data tables must include sr-only captions');

// Test 5: SVG Accessibility
console.log('Test 5: Validating SVG Chart Semantics & Keyboard Focusability...');
assert(clientCode.includes('<title id="brand-dsi-svg-title">'), 'Brand DSI SVG must have accessible <title>');
assert(clientCode.includes('<desc id="brand-dsi-svg-desc">'), 'Brand DSI SVG must have accessible <desc>');
assert(clientCode.includes('aria-labelledby="brand-dsi-svg-title brand-dsi-svg-desc"'), 'SVG must bind title & desc via aria-labelledby');
assert(clientCode.includes('role="button"'), 'Interactive SVG elements must have explicit role="button"');

// Test 6: Mobile Touch Target Heights
console.log('Test 6: Validating Mobile Touch Target Minimum Dimensions (min-h-[44px])...');
assert(clientCode.includes('min-h-[44px] inline-flex items-center justify-center'), 'Interactive buttons must support min 44px touch target');

// Test 7: Horizontal Scroll Regions Accessibility
console.log('Test 7: Validating Accessible Horizontal Scroll Containers...');
assert(clientCode.includes('role="region"'), 'Scroll containers must declare role="region"');
assert(clientCode.includes('tabIndex={0}'), 'Scroll containers must be keyboard-focusable with tabIndex={0}');
assert(clientCode.includes('table-scroll-container'), 'Scroll containers must use custom scroll utility class');

// Test 8: Math Guard Verification
console.log('Test 8: Validating Math Boundary Guards (NaN & Zero Division)...');
assert(clientCode.includes('safeDsiA'), 'Head-to-head durability summary must sanitize safeDsiA');
assert(clientCode.includes('safeDsiB'), 'Head-to-head durability summary must sanitize safeDsiB');
assert(clientCode.includes('Math.abs(safeDsiB - safeDsiA).toFixed(1)'), 'Head-to-head durability must calculate absolute difference without NaN');

console.log('✅ ALL RELIABILITY DASHBOARD UI CLIENT AUDIT TESTS PASSED SUCCESSFULLY!');
