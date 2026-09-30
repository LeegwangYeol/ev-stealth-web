/**
 * tests/test_adversarial_routes_http.mjs
 * Empirical HTTP verification across all 12 Next.js App routes.
 */

const baseUrl = 'http://localhost:3009';

const routes = [
  '/',
  '/2026-latest',
  '/byd',
  '/depreciation-calculator',
  '/global-brands',
  '/hyundai-kia',
  '/pdi-checklist',
  '/recall-portal',
  '/reliability-analytics',
  '/secret-admin-reports',
  '/subsidy-tracker',
  '/tesla'
];

const results = [];
let allPassed = true;

for (const route of routes) {
  const url = `${baseUrl}${route}`;
  try {
    const start = performance.now();
    const res = await fetch(url);
    const duration = Math.round(performance.now() - start);
    const text = await res.text();

    const isOk = res.status === 200;
    const hasHtml = text.includes('<!DOCTYPE html>');
    const hasViewport = text.includes('viewport') || text.includes('width=device-width');
    const hasNextScripts = text.includes('/_next/static/');

    const passed = isOk && hasHtml && hasNextScripts;
    if (!passed) allPassed = false;

    results.push({
      route,
      status: res.status,
      sizeBytes: text.length,
      durationMs: duration,
      hasHtml,
      hasViewport,
      hasNextScripts,
      passed
    });
  } catch (err) {
    allPassed = false;
    results.push({
      route,
      error: err.message,
      passed: false
    });
  }
}

console.log('[HTTP ROUTE VERIFICATION MATRIX]');
console.table(results);

if (!allPassed) {
  console.error('[FAIL] One or more routes failed HTTP verification!');
  process.exit(1);
} else {
  console.log(`[PASS] All ${routes.length} routes served cleanly with 200 OK.`);
  process.exit(0);
}
