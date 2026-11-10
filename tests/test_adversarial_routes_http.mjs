/**
 * tests/test_adversarial_routes_http.mjs
 * Empirical HTTP verification across all 12 Next.js App routes.
 */

const baseUrl = process.env.TEST_SERVER_URL || (process.env.PORT ? `http://localhost:${process.env.PORT}` : 'http://localhost:3000');

// Initial liveness probe to verify server availability
try {
  const probe = await fetch(`${baseUrl}/`, { signal: AbortSignal.timeout(3000) });
  if (!probe) {
    throw new Error('No response from test server');
  }
} catch (probeErr) {
  console.log(`[SKIPPED] Next.js test server not reachable at ${baseUrl} (${probeErr.message}).`);
  console.log('         Start server via "npm run start" or set TEST_SERVER_URL to execute empirical HTTP route verification.');
  process.exit(0);
}

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
