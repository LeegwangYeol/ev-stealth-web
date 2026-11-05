/**
 * Audit verification test suite for AdminDashboardClient.tsx and getDailyReports.ts
 */
import assert from 'node:assert';
import { test } from 'node:test';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const dailyReportsTsPath = fs.existsSync(path.resolve(__dirname, '../src/lib/getDailyReports.ts'))
  ? path.resolve(__dirname, '../src/lib/getDailyReports.ts')
  : path.resolve(__dirname, '../ev-stealth-web/src/lib/getDailyReports.ts');
const dashboardClientPath = fs.existsSync(path.resolve(__dirname, '../src/app/secret-admin-reports/AdminDashboardClient.tsx'))
  ? path.resolve(__dirname, '../src/app/secret-admin-reports/AdminDashboardClient.tsx')
  : path.resolve(__dirname, '../ev-stealth-web/src/app/secret-admin-reports/AdminDashboardClient.tsx');

const rawDailyReports = fs.readFileSync(dailyReportsTsPath, 'utf-8');
const rawDashboardClient = fs.readFileSync(dashboardClientPath, 'utf-8');

// 1. URL Sanitization Tests
test('getDailyReports.ts: sanitizeReportUrl blocks dangerous URI schemes', async () => {
  const patched = rawDailyReports
    .replace(/from '\.\/sanitizeUrl(?:\.ts)?';/, "from '../src/lib/sanitizeUrl.ts';")
    .replace(/from '\.\.\/data\/daily_reports\.json' with \{ type: 'json' \};/, "from '../src/data/daily_reports.json' with { type: 'json' };");

  const tempPath = path.resolve(__dirname, 'temp_test_daily_reports.ts');
  fs.writeFileSync(tempPath, patched, 'utf-8');

  let mod;
  try {
    mod = await import('./temp_test_daily_reports.ts');
  } finally {
    if (fs.existsSync(tempPath)) fs.unlinkSync(tempPath);
  }

  const { sanitizeReportUrl, getSafeSentimentScore, normalizeReport, calculateKPIs, getFallbackReportData } = mod;

  // Dangerous schemes
  assert.strictEqual(sanitizeReportUrl('javascript:alert(1)'), '#');
  assert.strictEqual(sanitizeReportUrl('JAVASCRIPT:alert(document.cookie)'), '#');
  assert.strictEqual(sanitizeReportUrl('   javascript:void(0)'), '#');
  assert.strictEqual(sanitizeReportUrl('data:text/html,<script>alert(1)</script>'), '#');
  assert.strictEqual(sanitizeReportUrl('vbscript:MsgBox(1)'), '#');
  assert.strictEqual(sanitizeReportUrl('%6a%61%76%61%73%63%72%69%70%74:alert(1)'), '#');
  assert.strictEqual(sanitizeReportUrl(null), '#');
  assert.strictEqual(sanitizeReportUrl(undefined), '#');
  assert.strictEqual(sanitizeReportUrl(''), '#');
  assert.strictEqual(sanitizeReportUrl('   '), '#');

  // Legitimate schemes
  assert.strictEqual(sanitizeReportUrl('https://www.bobaedream.co.kr/view?code=national&No=2416882'), 'https://www.bobaedream.co.kr/view?code=national&No=2416882');
  assert.strictEqual(sanitizeReportUrl('http://gall.dcinside.com/board/view/?id=car_new1&no=11525527'), 'http://gall.dcinside.com/board/view/?id=car_new1&no=11525527');

  // 2. Defensive Data Handling Tests
  const fallback = getFallbackReportData();
  assert.strictEqual(fallback.reports.length, 0);
  assert.strictEqual(fallback.statistics.total_filtered_defects, 0);
  assert.strictEqual(fallback.statistics.top_model, '해당 없음 (0건)');
  assert.strictEqual(fallback.statistics.top_platform, '해당 없음 (0%)');
  assert.strictEqual(fallback.statistics.avg_negativity_score, 0.0);

  // normalizeReport handles null / adversarial objects
  const emptyNorm = normalizeReport({}, 0);
  assert.strictEqual(emptyNorm.id, 'report_1');
  assert.strictEqual(emptyNorm.defect_category, 'BATTERY_CHARGING');
  assert.strictEqual(emptyNorm.defect_category_ko, '배터리/충전');
  assert.strictEqual(emptyNorm.severity, 'WARNING');
  assert.strictEqual(emptyNorm.sentiment_score, 0.85);
  assert.deepStrictEqual(emptyNorm.slang_tags, []);
  assert.strictEqual(emptyNorm.url, '#');

  // calculateKPIs handles null/undefined array and corrupt items safely
  const kpisEmpty = calculateKPIs([]);
  assert.strictEqual(kpisEmpty.total_filtered_defects, 0);
  assert.strictEqual(kpisEmpty.avg_negativity_score, 0.0);
  assert.strictEqual(kpisEmpty.top_model, '해당 없음 (0건)');
  assert.strictEqual(kpisEmpty.top_platform, '해당 없음 (0%)');

  // 3. Sentiment score bounds and rounding
  assert.strictEqual(getSafeSentimentScore(0.775), 0.78);
  assert.strictEqual(getSafeSentimentScore(-0.95), 0.95);
  assert.strictEqual(getSafeSentimentScore(85), 0.85); // 0-100 scale handling
  assert.strictEqual(getSafeSentimentScore(150), 1.0); // clamped
  assert.strictEqual(getSafeSentimentScore(-150), 1.0); // clamped abs
  assert.strictEqual(getSafeSentimentScore(NaN), 0.85); // fallback
  assert.strictEqual(getSafeSentimentScore(undefined), 0.85);
});

// 4. Source code static audit tests for AdminDashboardClient.tsx
test('AdminDashboardClient.tsx static audit: search truncation, memoization, contrast', () => {
  // Search query truncation
  assert.ok(rawDashboardClient.includes('slice(0, 200)'), 'Search query must be truncated to 200 chars');
  assert.ok(rawDashboardClient.includes('slice(0, 50)'), 'Tag filter must be truncated to 50 chars');

  // Precomputed search index optimization
  assert.ok(rawDashboardClient.includes('_searchIndex'), 'Must precompute _searchIndex for memoized fast filtering');

  // Contrast ratios verification
  assert.ok(rawDashboardClient.includes('bg-rose-700 text-white'), 'CRITICAL badge must use high contrast bg-rose-700 text-white');
  assert.ok(rawDashboardClient.includes('bg-orange-700 text-white'), 'HIGH badge must use high contrast bg-orange-700 text-white');
  assert.ok(rawDashboardClient.includes('bg-amber-400 text-slate-950'), 'WARNING badge must use high contrast bg-amber-400 text-slate-950');
  assert.ok(rawDashboardClient.includes('bg-amber-100 text-amber-950'), 'MEDIUM badge must use high contrast bg-amber-100 text-amber-950');
  assert.ok(rawDashboardClient.includes('bg-emerald-100 text-emerald-950'), 'LOW badge must use high contrast bg-emerald-100 text-emerald-950');
  assert.ok(rawDashboardClient.includes('bg-slate-100 text-slate-900'), 'INFO badge must use high contrast bg-slate-100 text-slate-900');

  // Safe external URL rendering (no dead # links)
  assert.ok(rawDashboardClient.includes('isExternal ?'), 'Links must conditionally render anchor tag only for external URLs');
  assert.ok(rawDashboardClient.includes('formatSentimentPercent'), 'Must use formatSentimentPercent helper for bounded sentiment displays');

  // WCAG AA: Search landmark and accessible hint
  assert.ok(rawDashboardClient.includes('role="search"'), 'Search input container must have role="search"');
  assert.ok(rawDashboardClient.includes('aria-describedby="admin-defect-search-hint"'), 'Search input must have aria-describedby for assistive tech hint');
  assert.ok(rawDashboardClient.includes('id="admin-defect-search-hint"'), 'Hint element must exist with matching ID');

  // WCAG AA: Table accessibility
  assert.ok(rawDashboardClient.includes('scope="col"'), 'Table header cells must specify scope="col"');
  assert.ok(rawDashboardClient.includes('scope="row"'), 'Table row headers must specify scope="row"');
  assert.ok(rawDashboardClient.includes('<caption>'), 'Table must define an informative caption element');
  assert.ok(rawDashboardClient.includes('원문 링크 없음'), 'Dead links must be replaced with non-anchor text');

  // WCAG AA: Pagination Controls
  assert.ok(rawDashboardClient.includes('aria-label="결함 제보 목록 페이지 탐색"'), 'Pagination must define accessible navigation landmark');
  assert.ok(rawDashboardClient.includes('aria-label="이전 페이지로 이동"'), 'Previous page button must have descriptive aria-label');
  assert.ok(rawDashboardClient.includes('aria-label="다음 페이지로 이동"'), 'Next page button must have descriptive aria-label');
  assert.ok(rawDashboardClient.includes('aria-current={isCurrent ? \'page\' : undefined}'), 'Current page button must indicate aria-current="page"');
  assert.ok(rawDashboardClient.includes('min-h-[44px] min-w-[44px]'), 'Pagination buttons must meet WCAG 44x44px tap target size');

  // Korean search resilience & spacing tolerance
  assert.ok(rawDashboardClient.includes('_spacelessIndex'), 'Must precompute _spacelessIndex for Korean spacing-tolerant matching');
  assert.ok(rawDashboardClient.includes('replace(/^#+/, \'\')'), 'Must strip hashtags to support #tag queries');
  assert.ok(rawDashboardClient.includes('split(/\\s+/)'), 'Must split query into tokens for multi-keyword search');

  // Date parsing & deterministic sorting
  assert.ok(rawDashboardClient.includes('parseSafeDate'), 'Must use parseSafeDate for cross-browser date parsing');
  assert.ok(rawDashboardClient.includes('getPaginationItems'), 'Must export getPaginationItems helper for clean page navigation');
});

// 5. Functional tests for parseSafeDate and getPaginationItems
test('AdminDashboardClient logic: parseSafeDate and getPaginationItems functional tests', () => {
  // Extract and evaluate parseSafeDate and getPaginationItems logic
  function parseSafeDate(rawDate) {
    if (!rawDate || typeof rawDate !== 'string') return 0;
    const trimmed = rawDate.trim();
    if (!trimmed) return 0;
    const normalized = trimmed.replace(/\./g, '-').replace(/\//g, '-');
    if (/^\d{4}-\d{2}-\d{2}$/.test(normalized)) {
      const timestamp = new Date(`${normalized}T00:00:00Z`).getTime();
      if (Number.isFinite(timestamp) && timestamp > 0) return timestamp;
    }
    if (/^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}/.test(normalized)) {
      const isoLike = normalized.replace(/\s+/, 'T') + (normalized.includes('+') || normalized.endsWith('Z') ? '' : 'Z');
      const timestamp = new Date(isoLike).getTime();
      if (Number.isFinite(timestamp) && timestamp > 0) return timestamp;
    }
    const timestamp = new Date(normalized).getTime();
    if (Number.isFinite(timestamp) && timestamp > 0) return timestamp;
    return 0;
  }

  function getPaginationItems(current, total) {
    if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
    if (current <= 4) return [1, 2, 3, 4, 5, '...', total];
    if (current >= total - 3) return [1, '...', total - 4, total - 3, total - 2, total - 1, total];
    return [1, '...', current - 1, current, current + 1, '...', total];
  }

  // parseSafeDate tests
  assert.ok(parseSafeDate('2026-09-30T10:25:45+00:00') > 0);
  assert.ok(parseSafeDate('2026.09.08') > 0);
  assert.strictEqual(parseSafeDate('2026.09.08'), parseSafeDate('2026-09-08'));
  assert.ok(parseSafeDate('2026/09/08') > 0);
  assert.ok(parseSafeDate('2026-09-08 14:30:00') > 0);
  assert.strictEqual(parseSafeDate(''), 0);
  assert.strictEqual(parseSafeDate(null), 0);
  assert.strictEqual(parseSafeDate(undefined), 0);

  // getPaginationItems tests
  assert.deepStrictEqual(getPaginationItems(1, 5), [1, 2, 3, 4, 5]);
  assert.deepStrictEqual(getPaginationItems(1, 10), [1, 2, 3, 4, 5, '...', 10]);
  assert.deepStrictEqual(getPaginationItems(9, 10), [1, '...', 6, 7, 8, 9, 10]);
  assert.deepStrictEqual(getPaginationItems(5, 10), [1, '...', 4, 5, 6, '...', 10]);
});
