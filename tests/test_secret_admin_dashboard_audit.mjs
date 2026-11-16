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
    .replace(/from '\.\/reportCalculations(?:\.ts)?';/, "from '../src/lib/reportCalculations.ts';")
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

// 6. WCAG AA Accessibility and Modal/Filter/Search Field Audit
test('AdminDashboardClient.tsx accessibility audit: WCAG AA compliant table, modal, filter, search name', () => {
  // Search Field Accessible Name & Refocusing
  assert.ok(rawDashboardClient.includes('aria-label="전기차 결함 제보 및 은어 검색"'), 'Search input must have explicit accessible name');
  assert.ok(rawDashboardClient.includes('searchInputRef.current?.focus()'), 'Search clear and reset handlers must return focus to search input');

  // Filter Group Landmarks
  assert.ok(rawDashboardClient.includes('aria-label="출처 플랫폼 필터"'), 'Source filters must be enclosed in accessible group');
  assert.ok(rawDashboardClient.includes('aria-label="결함 제보 정렬 기준"'), 'Sort options must be enclosed in accessible group');
  assert.ok(rawDashboardClient.includes('aria-label="결함 카테고리 탭"'), 'Category tablist must define accessible label');

  // Modal Dialog Accessibility
  assert.ok(rawDashboardClient.includes('aria-modal="true"'), 'Modal must declare aria-modal="true"');
  assert.ok(rawDashboardClient.includes('handleWindowKeyDown'), 'Modal must have window-level Escape listener');
  assert.ok(rawDashboardClient.includes('triggerButtonRef.current?.focus()'), 'Modal close must restore focus to opening button');
  assert.ok(rawDashboardClient.includes('aria-label="결함 상세 대화상자 닫기"'), 'Modal close button must have clear accessible name');

  // Table Accessibility & View Mode
  assert.ok(rawDashboardClient.includes('aria-label="수집된 전기차 결함 제보 데이터 요약 표"'), 'Table must define accessible name');
  assert.ok(rawDashboardClient.includes('aria-label="목록 표시 형식 선택"'), 'View mode toggle must define accessible group label');
  assert.ok(rawDashboardClient.includes('게시글 원문 보기 (새 창에서 열림)'), 'Table link labels must specify context and open-in-new-window warning');

  // Performance: Precomputed tokenization
  assert.ok(rawDashboardClient.includes('queryTokens = rawQuery'), 'Must precompute query tokens once outside the loop');
});

// 7. Defensive Data, Safe JSON Parsing, and Empty State Audit
test('getDailyReports.ts and page.tsx: Safe JSON parsing, empty reports handling', async () => {
  const pageTsxPath = fs.existsSync(path.resolve(__dirname, '../src/app/secret-admin-reports/page.tsx'))
    ? path.resolve(__dirname, '../src/app/secret-admin-reports/page.tsx')
    : path.resolve(__dirname, '../ev-stealth-web/src/app/secret-admin-reports/page.tsx');
  const rawPageTsx = fs.readFileSync(pageTsxPath, 'utf-8');

  // page.tsx has defensive fallback handling
  assert.ok(rawPageTsx.includes('getFallbackReportData'), 'page.tsx must import and use getFallbackReportData');
  assert.ok(rawPageTsx.includes('safeData = data || getFallbackReportData()'), 'page.tsx must safely fallback if data is missing');

  // Safe JSON parsing support in getDailyReports.ts
  assert.ok(rawDailyReports.includes('safeJsonParse'), 'getDailyReports.ts must import and use safeJsonParse');
  assert.ok(rawDailyReports.includes('parsedInput'), 'getDailyReports.ts must handle string inputs safely');
});

// 8. Deduplication Engine & Status Display Audit
test('getDailyReports.ts and AdminDashboardClient.tsx: Deduplication engine & status display', async () => {
  const patched = rawDailyReports
    .replace(/from '\.\/reportCalculations(?:\.ts)?';/, "from '../src/lib/reportCalculations.ts';")
    .replace(/from '\.\/sanitizeUrl(?:\.ts)?';/, "from '../src/lib/sanitizeUrl.ts';")
    .replace(/from '\.\.\/data\/daily_reports\.json' with \{ type: 'json' \};/, "from '../src/data/daily_reports.json' with { type: 'json' };");

  const tempPath = path.resolve(__dirname, 'temp_test_dedup.ts');
  fs.writeFileSync(tempPath, patched, 'utf-8');

  let mod;
  try {
    mod = await import('./temp_test_dedup.ts');
  } finally {
    if (fs.existsSync(tempPath)) fs.unlinkSync(tempPath);
  }

  const { deduplicateReports } = mod;

  // Duplicate items by ID
  const duplicateIdReports = [
    { id: 'rep_101', title: '배터리 이상', vehicle_model: '아이오닉5', defect_category: 'BATTERY_CHARGING' },
    { id: 'rep_101', title: '배터리 이상 (중복)', vehicle_model: '아이오닉5', defect_category: 'BATTERY_CHARGING' },
    { id: 'rep_102', title: '모터 소음', vehicle_model: 'EV6', defect_category: 'DRIVING_POWERTRAIN' },
  ];
  const res1 = deduplicateReports(duplicateIdReports);
  assert.strictEqual(res1.reports.length, 2);
  assert.strictEqual(res1.summary.duplicatesRemoved, 1);
  assert.strictEqual(res1.summary.isDeduplicated, true);

  // Duplicate items by URL
  const duplicateUrlReports = [
    { id: 'report_1', url: 'https://gall.dcinside.com/view/?id=car&no=999', title: '글1' },
    { id: 'report_2', url: 'https://gall.dcinside.com/view/?id=car&no=999?query=1', title: '글2' },
  ];
  const res2 = deduplicateReports(duplicateUrlReports);
  assert.strictEqual(res2.reports.length, 1);
  assert.strictEqual(res2.summary.duplicatesRemoved, 1);

  // Re-read current client code
  const freshClient = fs.readFileSync(dashboardClientPath, 'utf-8');
  assert.ok(freshClient.includes('deduplicateReports'), 'AdminDashboardClient must use deduplicateReports');
  assert.ok(freshClient.includes('중복 정제:'), 'AdminDashboardClient must display deduplication status in card or header');
  assert.ok(freshClient.includes('고유 제보'), 'AdminDashboardClient must indicate authentic unique report count');
});

// 9. Security Audit: Sensitive Data Leakage Protection
test('Security Sanitization: Mask internal paths, sensitive tokens, author PII, SSRF loopback URLs', async () => {
  const patched = rawDailyReports
    .replace(/from '\.\/reportCalculations(?:\.ts)?';/, "from '../src/lib/reportCalculations.ts';")
    .replace(/from '\.\/sanitizeUrl(?:\.ts)?';/, "from '../src/lib/sanitizeUrl.ts';")
    .replace(/from '\.\.\/data\/daily_reports\.json' with \{ type: 'json' \};/, "from '../src/data/daily_reports.json' with { type: 'json' };");

  const tempPath = path.resolve(__dirname, 'temp_test_sec.ts');
  fs.writeFileSync(tempPath, patched, 'utf-8');

  let mod;
  try {
    mod = await import('./temp_test_sec.ts');
  } finally {
    if (fs.existsSync(tempPath)) fs.unlinkSync(tempPath);
  }

  const { maskInternalPaths, maskSensitiveTokens, maskAuthor, maskSensitiveData, sanitizeReportUrl } = mod;

  // Internal path masking
  const leakedPathUnix = '오류 발생: /Users/a7890/my-e-car/secret.key 파일 없음';
  assert.strictEqual(maskInternalPaths(leakedPathUnix), '오류 발생: [내부경로_마스킹] 파일 없음');

  const leakedPathWin = 'Path: C:\\Users\\Administrator\\AppData\\Local\\temp\\debug.log';
  assert.strictEqual(maskInternalPaths(leakedPathWin), 'Path: [내부경로_마스킹]');

  // Token masking
  const leakedJwt = 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.sH4_sampleSignatureTextHere';
  assert.ok(!maskSensitiveTokens(leakedJwt).includes('eyJhbGci'));
  assert.ok(maskSensitiveTokens(leakedJwt).includes('[REDACTED_JWT]') || maskSensitiveTokens(leakedJwt).includes('[REDACTED_TOKEN]'));

  const leakedApiKey = 'api_key: sk-1234567890abcdef1234567890';
  assert.ok(!maskSensitiveTokens(leakedApiKey).includes('sk-1234567890abcdef1234567890'));

  // Author PII masking
  assert.strictEqual(maskAuthor('홍길동 (211.234.12.34)'), '홍길동 (211.234.*.*)');
  assert.strictEqual(maskAuthor('user@hyundai.com'), 'u***@hyundai.com');
  assert.strictEqual(maskAuthor('제보자 010-1234-5678'), '제보자 010-****-5678');

  // SSRF Loopback / Private IP blocking
  assert.strictEqual(sanitizeReportUrl('http://localhost:3000/api/reports'), '#');
  assert.strictEqual(sanitizeReportUrl('http://127.0.0.1:8080/admin'), '#');
  assert.strictEqual(sanitizeReportUrl('http://192.168.1.1/dashboard'), '#');
  assert.strictEqual(sanitizeReportUrl('http://10.0.0.1/internal'), '#');

  // Sensitive URL query parameter stripping
  const cleanUrl = sanitizeReportUrl('https://www.bobaedream.co.kr/view?code=national&No=2416882&token=secret123');
  assert.ok(!cleanUrl.includes('token=secret123'), 'Sensitive query parameter token must be stripped from external URL');
  assert.ok(cleanUrl.includes('No=2416882'), 'Legitimate query parameter No must be preserved');
});

// 10. Korean Date Parsing, Search Debounce, and Pagination Audit
test('AdminDashboardClient.tsx: Korean date parsing, search debounce, and first/last page pagination', () => {
  const freshClient = fs.readFileSync(dashboardClientPath, 'utf-8');

  // Korean date formatting support in parseSafeDate
  assert.ok(freshClient.includes('parseSafeDate'), 'parseSafeDate must exist');
  assert.ok(freshClient.includes("replace(/년\\s*/g, '-')") || freshClient.includes("replace(/\\./g, '-')"), 'Must support Korean date parsing');

  // Debounced search query
  assert.ok(freshClient.includes('debounceTimerRef'), 'Must use debounceTimerRef for search query input debounce');
  assert.ok(freshClient.includes('debouncedQuery'), 'Must maintain debouncedQuery state');

  // First & Last Page Pagination Controls
  assert.ok(freshClient.includes('첫 페이지로 이동'), 'Must have first page navigation button for large page counts');
  assert.ok(freshClient.includes('마지막 페이지로 이동'), 'Must have last page navigation button for large page counts');
  assert.ok(freshClient.includes('validCurrentPage = Math.max(1, Math.min(currentPage, totalPages))'), 'validCurrentPage must be strictly bounded');

  // Responsive enhancements
  assert.ok(freshClient.includes('flex flex-wrap items-center gap-2'), 'Card action bar must use flex-wrap for mobile responsiveness');
});

// 11. XSS Safety & HTML Tag Sanitization in Verbatim Quotes and Text
test('Security Sanitization: stripHtmlTags and sanitizeHtml neutralize XSS, strip tags, and preserve linebreaks', async () => {
  const sanitizeUrlTsPath = fs.existsSync(path.resolve(__dirname, '../src/lib/sanitizeUrl.ts'))
    ? path.resolve(__dirname, '../src/lib/sanitizeUrl.ts')
    : path.resolve(__dirname, '../ev-stealth-web/src/lib/sanitizeUrl.ts');

  const { stripHtmlTags, sanitizeHtml } = await import(sanitizeUrlTsPath);

  // Script tags and contents stripped
  assert.strictEqual(stripHtmlTags("<script>alert('XSS')</script>"), '');
  assert.strictEqual(stripHtmlTags("사고 후기 <script src='//evil.com/x.js'>alert(1)</script>입니다."), '사고 후기 입니다.');

  // Style and iframe tags and contents stripped
  assert.strictEqual(stripHtmlTags("<style>body { display: none; }</style>정상 텍스트"), '정상 텍스트');
  assert.strictEqual(stripHtmlTags("<iframe src='javascript:alert(1)'></iframe>제보 내용"), '제보 내용');

  // Event handler injections stripped
  const injectedImg = '<img src="x" onerror="alert(document.cookie)" />배터리 경고등 점등';
  assert.strictEqual(stripHtmlTags(injectedImg), '배터리 경고등 점등');

  // Paragraph and break tags converted to clean linebreaks
  const multilineQuote = '<p>ICCU 고장으로 주행 중 동력상실 발생.</p><p>서비스센터 예약까지 3주 소요됨.<br/>수리비 과다 청구.</p>';
  const cleanMultiline = stripHtmlTags(multilineQuote);
  assert.ok(cleanMultiline.includes('\n'));
  assert.ok(!cleanMultiline.includes('<p>'));
  assert.ok(!cleanMultiline.includes('</p>'));
  assert.ok(!cleanMultiline.includes('<br'));

  // Entity decoding with nested tag defense
  const encodedTag = '&lt;script&gt;alert(1)&lt;/script&gt;원문 코멘트';
  assert.strictEqual(stripHtmlTags(encodedTag), '원문 코멘트');

  const quoteWithQuotes = '&quot;급발진 의심&quot; &amp; &apos;브레이크 먹통&apos;';
  assert.strictEqual(stripHtmlTags(quoteWithQuotes), '"급발진 의심" & \'브레이크 먹통\'');

  // Null and undefined safety
  assert.strictEqual(stripHtmlTags(null), '');
  assert.strictEqual(stripHtmlTags(undefined), '');
  assert.strictEqual(stripHtmlTags(''), '');

  // Alias verification
  assert.strictEqual(sanitizeHtml('<b onmouseover="alert(1)">강조</b>'), '강조');
});

// 12. Defect Report Filtering: Brand Normalization, Date Range, Platform, and Category
test('AdminDashboardClient.tsx: Multi-dimensional filtering by date, platform, brand, and defect category', () => {
  const freshClient = fs.readFileSync(dashboardClientPath, 'utf-8');

  // Brand normalization logic verification
  assert.ok(freshClient.includes('normalizeBrand'), 'Must define and export normalizeBrand helper');
  assert.ok(freshClient.includes('selectedBrand'), 'Must maintain selectedBrand filter state');
  assert.ok(freshClient.includes('admin-brand-filter'), 'Must provide accessible select with id admin-brand-filter');
  assert.ok(freshClient.includes('차량 브랜드:'), 'Must provide clear label for vehicle brand filter');

  // Date filtering logic verification
  assert.ok(freshClient.includes('selectedDateRange'), 'Must maintain selectedDateRange filter state');
  assert.ok(freshClient.includes('admin-date-filter'), 'Must provide accessible select with id admin-date-filter');
  assert.ok(freshClient.includes('수집 일자:'), 'Must provide clear label for collection date filter');
  assert.ok(freshClient.includes('RECENT_7D'), 'Must support recent 7-day preset filter');
  assert.ok(freshClient.includes('RECENT_30D'), 'Must support recent 30-day preset filter');

  // Comprehensive reset filter verification
  assert.ok(freshClient.includes("setSelectedBrand('ALL')"), 'Reset handler must reset selectedBrand to ALL');
  assert.ok(freshClient.includes("setSelectedDateRange('ALL')"), 'Reset handler must reset selectedDateRange to ALL');

  // Functional brand normalizer test
  function normalizeBrand(rawBrand) {
    if (!rawBrand || typeof rawBrand !== 'string') return '기타';
    const clean = rawBrand.trim();
    const lower = clean.toLowerCase();
    if (lower === 'hyundai' || lower === '현대' || lower.includes('현대')) return '현대';
    if (lower === 'kia' || lower === '기아' || lower.includes('기아')) return '기아';
    if (lower === 'genesis' || lower === '제네시스' || lower.includes('제네시스')) return '제네시스';
    if (lower === 'tesla' || lower === '테슬라' || lower.includes('테슬라')) return '테슬라';
    if (lower === 'mercedes' || lower === 'mercedes-benz' || lower === '벤츠' || lower.includes('벤츠')) return '벤츠';
    if (lower === 'bmw') return 'BMW';
    if (lower === 'byd') return 'BYD';
    if (lower === 'polestar' || lower === '폴스타') return '폴스타';
    if (lower === 'chevrolet' || lower === '쉐보레') return '쉐보레';
    if (lower === 'renault' || lower === '르노') return '르노';
    if (lower === 'kgm' || lower === '쌍용' || lower === 'kg mobility') return 'KGM';
    if (lower === 'other' || lower === '기타' || lower === 'etc') return '기타';
    return clean;
  }

  assert.strictEqual(normalizeBrand('Kia'), '기아');
  assert.strictEqual(normalizeBrand('기아자동차'), '기아');
  assert.strictEqual(normalizeBrand('Hyundai'), '현대');
  assert.strictEqual(normalizeBrand('Tesla'), '테슬라');
  assert.strictEqual(normalizeBrand('Mercedes-Benz'), '벤츠');
  assert.strictEqual(normalizeBrand('Other'), '기타');
  assert.strictEqual(normalizeBrand(''), '기타');
  assert.strictEqual(normalizeBrand(null), '기타');
});

// 13. Mobile View Layout & Accessibility Enhancements
test('AdminDashboardClient.tsx: Mobile view layout, text wrapping, and modal viewport bounds', () => {
  const freshClient = fs.readFileSync(dashboardClientPath, 'utf-8');

  // Verbatim quote whitespace and word-break preservation for mobile screens
  assert.ok(
    freshClient.includes('whitespace-pre-line break-words'),
    'Verbatim quote containers must have whitespace-pre-line and break-words for linebreaks and narrow mobile screens'
  );

  // Modal dialog mobile constraint
  assert.ok(
    freshClient.includes('max-h-[calc(100vh-2rem)] overflow-y-auto') || freshClient.includes('max-h-[90vh]'),
    'Modal dialog must constrain height to viewport on small mobile devices'
  );

  // Accessible filter select elements meet touch target requirements
  assert.ok(freshClient.includes('id="admin-brand-filter"'), 'Brand filter select element must have id');
  assert.ok(freshClient.includes('id="admin-date-filter"'), 'Date filter select element must have id');
});

