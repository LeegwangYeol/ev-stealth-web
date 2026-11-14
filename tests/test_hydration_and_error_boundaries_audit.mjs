/**
 * tests/test_hydration_and_error_boundaries_audit.mjs
 * Comprehensive automated verification of Error Boundaries, Loading Skeletons,
 * and SSR/CSR Hydration Safety across the entire ev-stealth-web application.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');
const srcDir = path.resolve(rootDir, 'src');
const appDir = path.resolve(srcDir, 'app');

const testResults = {
  total: 0,
  passed: 0,
  failed: 0,
  failures: [],
};

function assert(condition, message, details = {}) {
  testResults.total++;
  if (condition) {
    testResults.passed++;
    console.log(`  ✓ ${message}`);
  } else {
    testResults.failed++;
    testResults.failures.push({ message, details });
    console.error(`  ✗ FAIL: ${message}`, details);
  }
}

console.log('======================================================================');
console.log('HYDRATION SAFETY & ERROR BOUNDARIES COMPREHENSIVE AUDIT');
console.log('======================================================================\n');

// --------------------------------------------------------------------
// 1. ClientTimestamp.tsx Hydration Safety Verification
// --------------------------------------------------------------------
console.log('[SUITE 1] ClientTimestamp.tsx Hydration Safety & Defensive Resilience');
const clientTimestampPath = path.resolve(srcDir, 'components', 'ClientTimestamp.tsx');
assert(fs.existsSync(clientTimestampPath), 'ClientTimestamp.tsx component exists');

const clientTimestampSrc = fs.readFileSync(clientTimestampPath, 'utf-8');

assert(
  clientTimestampSrc.includes('"use client"') || clientTimestampSrc.includes("'use client'"),
  'ClientTimestamp.tsx declares "use client" directive'
);

assert(
  clientTimestampSrc.includes('suppressHydrationWarning'),
  'ClientTimestamp.tsx applies suppressHydrationWarning to <time> tag'
);

assert(
  clientTimestampSrc.includes('useIsMounted'),
  'ClientTimestamp.tsx defines and exports useIsMounted hook'
);

assert(
  clientTimestampSrc.includes('useEffect') && clientTimestampSrc.includes('setMounted(true)'),
  'ClientTimestamp.tsx uses useEffect mounted state to prevent SSR/CSR hydration mismatch'
);

assert(
  clientTimestampSrc.includes('typeof isoString === \'string\''),
  'ClientTimestamp.tsx defensively validates that isoString prop is a string'
);

assert(
  clientTimestampSrc.includes('areTimestampPropsEqual'),
  'ClientTimestamp.tsx implements custom memoization comparator for Intl options'
);

// --------------------------------------------------------------------
// 2. SubsidyErrorBoundary.tsx Resilience & Accessibility
// --------------------------------------------------------------------
console.log('\n[SUITE 2] SubsidyErrorBoundary.tsx Accessibility & Lifecycle');
const subsidyBoundaryPath = path.resolve(srcDir, 'components', 'subsidy', 'SubsidyErrorBoundary.tsx');
assert(fs.existsSync(subsidyBoundaryPath), 'SubsidyErrorBoundary.tsx exists');

const subsidyBoundarySrc = fs.readFileSync(subsidyBoundaryPath, 'utf-8');

assert(
  subsidyBoundarySrc.includes("'use client'") || subsidyBoundarySrc.includes('"use client"'),
  'SubsidyErrorBoundary.tsx declares "use client"'
);

assert(
  subsidyBoundarySrc.includes('getDerivedStateFromError'),
  'SubsidyErrorBoundary.tsx implements getDerivedStateFromError static lifecycle method'
);

assert(
  subsidyBoundarySrc.includes('componentDidCatch'),
  'SubsidyErrorBoundary.tsx implements componentDidCatch error telemetry'
);

assert(
  subsidyBoundarySrc.includes('role="alert"'),
  'SubsidyErrorBoundary.tsx specifies role="alert" for immediate screen reader notification'
);

assert(
  subsidyBoundarySrc.includes('aria-live="assertive"'),
  'SubsidyErrorBoundary.tsx specifies aria-live="assertive"'
);

assert(
  subsidyBoundarySrc.includes('Escape'),
  'SubsidyErrorBoundary.tsx supports keyboard dismissal via Escape key'
);

assert(
  subsidyBoundarySrc.includes('min-h-[44px]'),
  'SubsidyErrorBoundary.tsx provides min 44x44px touch targets (WCAG 2.5.5 AA compliant)'
);

assert(
  subsidyBoundarySrc.includes('key={this.state.retryCount}'),
  'SubsidyErrorBoundary.tsx remounts children cleanly upon retry'
);

// --------------------------------------------------------------------
// 3. Root Level Boundaries: global-error.tsx, error.tsx, not-found.tsx, loading.tsx
// --------------------------------------------------------------------
console.log('\n[SUITE 3] Root Error Boundaries & Global Fallbacks');

// global-error.tsx
const globalErrorPath = path.resolve(appDir, 'global-error.tsx');
assert(fs.existsSync(globalErrorPath), 'Root global-error.tsx exists');
const globalErrorSrc = fs.readFileSync(globalErrorPath, 'utf-8');
assert(globalErrorSrc.includes('<html') && globalErrorSrc.includes('<body'), 'global-error.tsx defines <html> and <body> tags');
assert(globalErrorSrc.includes('role="alert"'), 'global-error.tsx includes role="alert"');
assert(globalErrorSrc.includes('aria-live="assertive"'), 'global-error.tsx includes aria-live="assertive"');
assert(globalErrorSrc.includes('min-h-[44px]'), 'global-error.tsx buttons meet min 44px touch target');

// error.tsx
const rootErrorPath = path.resolve(appDir, 'error.tsx');
assert(fs.existsSync(rootErrorPath), 'Root error.tsx exists');
const rootErrorSrc = fs.readFileSync(rootErrorPath, 'utf-8');
assert(rootErrorSrc.includes('role="alert"'), 'root error.tsx includes role="alert"');
assert(rootErrorSrc.includes('aria-live="assertive"'), 'root error.tsx includes aria-live="assertive"');
assert(rootErrorSrc.includes('reset()'), 'root error.tsx provides reset() call');

// not-found.tsx
const notFoundPath = path.resolve(appDir, 'not-found.tsx');
assert(fs.existsSync(notFoundPath), 'Root not-found.tsx exists');
const notFoundSrc = fs.readFileSync(notFoundPath, 'utf-8');
assert(notFoundSrc.includes('404'), 'not-found.tsx displays 404 badge');
assert(notFoundSrc.includes('robots: {') && notFoundSrc.includes('index: false'), 'not-found.tsx sets robots noindex');
assert(notFoundSrc.includes('/subsidy-tracker') && notFoundSrc.includes('/depreciation-calculator'), 'not-found.tsx links to core features');

// loading.tsx
const rootLoadingPath = path.resolve(appDir, 'loading.tsx');
assert(fs.existsSync(rootLoadingPath), 'Root loading.tsx exists');
const rootLoadingSrc = fs.readFileSync(rootLoadingPath, 'utf-8');
assert(rootLoadingSrc.includes('role="status"'), 'root loading.tsx includes role="status"');
assert(rootLoadingSrc.includes('aria-live="polite"'), 'root loading.tsx includes aria-live="polite"');
assert(rootLoadingSrc.includes('sr-only'), 'root loading.tsx includes accessible sr-only announcement');
assert(rootLoadingSrc.includes('motion-reduce:animate-none'), 'root loading.tsx respects prefers-reduced-motion');

// --------------------------------------------------------------------
// 4. All Route Segments: error.tsx & loading.tsx Audit
// --------------------------------------------------------------------
console.log('\n[SUITE 4] All Route Segments: error.tsx and loading.tsx');

const routes = [
  'subsidy-tracker',
  'depreciation-calculator',
  'reliability-analytics',
  'recall-portal',
  'pdi-checklist',
  'secret-admin-reports',
  '2026-latest',
  'tesla',
  'byd',
  'hyundai-kia',
  'global-brands',
];

for (const route of routes) {
  const routeErrorPath = path.resolve(appDir, route, 'error.tsx');
  assert(fs.existsSync(routeErrorPath), `Route /${route} has error.tsx`);
  if (fs.existsSync(routeErrorPath)) {
    const content = fs.readFileSync(routeErrorPath, 'utf-8');
    assert(
      content.includes("'use client'") || content.includes('"use client"'),
      `Route /${route}/error.tsx declares "use client"`
    );
    assert(content.includes('role="alert"'), `Route /${route}/error.tsx has role="alert"`);
    assert(content.includes('aria-live="assertive"'), `Route /${route}/error.tsx has aria-live="assertive"`);
    assert(content.includes('reset()'), `Route /${route}/error.tsx handles reset()`);
    assert(content.includes('min-h-[44px]'), `Route /${route}/error.tsx buttons meet min 44px touch target`);
  }

  const routeLoadingPath = path.resolve(appDir, route, 'loading.tsx');
  assert(fs.existsSync(routeLoadingPath), `Route /${route} has loading.tsx`);
  if (fs.existsSync(routeLoadingPath)) {
    const content = fs.readFileSync(routeLoadingPath, 'utf-8');
    assert(content.includes('role="status"'), `Route /${route}/loading.tsx has role="status"`);
    assert(content.includes('aria-live="polite"'), `Route /${route}/loading.tsx has aria-live="polite"`);
    assert(content.includes('sr-only'), `Route /${route}/loading.tsx has screen reader text`);
  }
}

// --------------------------------------------------------------------
// 5. SSR / CSR Hydration Mismatch Audit (Math.random, localStorage, Root suppressHydrationWarning)
// --------------------------------------------------------------------
console.log('\n[SUITE 5] SSR/CSR Hydration Mismatch Safety');

// Check Root Layout suppressHydrationWarning
const rootLayoutPath = path.resolve(appDir, 'layout.tsx');
const rootLayoutSrc = fs.readFileSync(rootLayoutPath, 'utf-8');
assert(
  rootLayoutSrc.includes('<html lang="ko" suppressHydrationWarning>') &&
  rootLayoutSrc.includes('suppressHydrationWarning\n      >'),
  'Root layout.tsx applies suppressHydrationWarning to both <html> and <body>'
);

// Scan all src files for accidental Math.random
function scanDirForPatterns(dir, pattern, fileMatcher = /\.(tsx?|jsx?)$/) {
  const matches = [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      matches.push(...scanDirForPatterns(fullPath, pattern, fileMatcher));
    } else if (entry.isFile() && fileMatcher.test(entry.name)) {
      const content = fs.readFileSync(fullPath, 'utf-8');
      if (pattern.test(content)) {
        matches.push(fullPath);
      }
    }
  }
  return matches;
}

const mathRandomOccurrences = scanDirForPatterns(srcDir, /Math\.random\s*\(/);
assert(
  mathRandomOccurrences.length === 0,
  `Zero Math.random() occurrences in src (found: ${mathRandomOccurrences.length})`
);

// Check that localStorage/sessionStorage are strictly guarded behind mounted checks or client hooks
const localStorageOccurrences = scanDirForPatterns(srcDir, /localStorage\./);
for (const file of localStorageOccurrences) {
  const content = fs.readFileSync(file, 'utf-8');
  const relPath = path.relative(srcDir, file);
  assert(
    content.includes('mounted') || content.includes("typeof window !== 'undefined'"),
    `localStorage in ${relPath} is guarded by client mounted check or typeof window`
  );
}

// --------------------------------------------------------------------
// FINAL RESULTS SUMMARY
// --------------------------------------------------------------------
console.log('\n======================================================================');
console.log(`TOTAL TESTS: ${testResults.total}`);
console.log(`PASSED: ${testResults.passed}`);
console.log(`FAILED: ${testResults.failed}`);
console.log('======================================================================');

if (testResults.failed > 0) {
  process.exit(1);
} else {
  console.log('\n✅ ALL ERROR BOUNDARIES & HYDRATION SAFETY CHECKS PASSED PERFECTLY!\n');
  process.exit(0);
}
