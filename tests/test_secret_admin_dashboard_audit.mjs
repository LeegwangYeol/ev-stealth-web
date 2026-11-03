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

const dailyReportsTsPath = path.resolve(__dirname, '../ev-stealth-web/src/lib/getDailyReports.ts');
const dashboardClientPath = path.resolve(__dirname, '../ev-stealth-web/src/app/secret-admin-reports/AdminDashboardClient.tsx');

const rawDailyReports = fs.readFileSync(dailyReportsTsPath, 'utf-8');
const rawDashboardClient = fs.readFileSync(dashboardClientPath, 'utf-8');

// 1. URL Sanitization Tests
test('getDailyReports.ts: sanitizeReportUrl blocks dangerous URI schemes', async () => {
  const patched = rawDailyReports
    .replace(/from '\.\/sanitizeUrl';/, "from '../ev-stealth-web/src/lib/sanitizeUrl.ts';")
    .replace(/from '\.\.\/data\/daily_reports\.json' with \{ type: 'json' \};/, "from '../ev-stealth-web/src/data/daily_reports.json' with { type: 'json' };");

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
});
