import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  sanitizeSafeUrl,
  isPrototypePollutionKey,
  parseSafeQueryParams,
  safeJsonParse,
  serializeJsonLd,
} from '../src/lib/sanitizeUrl.ts';

import {
  resolveCategory as resolveCategoryCalc,
  normalizeReport as normalizeReportCalc,
  calculateKPIs as calculateKPIsCalc,
  sanitizeReportUrl as sanitizeReportUrlCalc,
} from '../src/lib/reportCalculations.ts';

import {
  resolveCategory as resolveCategoryDaily,
  normalizeReport as normalizeReportDaily,
  calculateKPIs as calculateKPIsDaily,
  sanitizeReportUrl as sanitizeReportUrlDaily,
  getDailyReports,
} from '../src/lib/getDailyReports.ts';

test('resolveCategory and normalizeReport reject bracketed, dotted, and percent-encoded prototype pollution keys', () => {
  const vectors = [
    '__proto__',
    '__proto__[polluted]',
    'constructor.prototype',
    'constructor[prototype]',
    '%5f%5fproto%5f%5f',
    'Object.prototype',
    '__defineGetter__',
  ];

  for (const vector of vectors) {
    assert.equal(isPrototypePollutionKey(vector), true, `Expected ${vector} to be flagged`);

    for (const resolveFn of [resolveCategoryCalc, resolveCategoryDaily]) {
      const resolved = resolveFn(vector, vector);
      assert.equal(resolved.code, 'BATTERY_CHARGING');
      assert.equal(resolved.ko, '배터리/충전');
    }

    for (const normFn of [normalizeReportCalc, normalizeReportDaily]) {
      const normalized = normFn(
        {
          defect_category: 'BATTERY_CHARGING',
          defect_category_ko: vector,
        },
        0
      );
      assert.equal(normalized.defect_category, 'BATTERY_CHARGING');
      assert.equal(normalized.defect_category_ko, '배터리/충전');
    }
  }
});

test('calculateKPIs trims whitespace around CRITICAL severity and handles malformed numeric fields', () => {
  for (const kpiFn of [calculateKPIsCalc, calculateKPIsDaily]) {
    const stats = kpiFn([
      {
        id: '1',
        source: 'dcinside',
        date: '2026-11-27',
        title: 't1',
        summary: 's1',
        verbatim_quote: 'q1',
        vehicle_model: 'EV6',
        defect_category: 'BATTERY_CHARGING',
        defect_category_ko: '배터리/충전',
        severity: ' critical ',
        sentiment_score: 0.9,
        slang_tags: [],
        url: 'https://gall.dcinside.com/board/view/?id=car_new1&no=1',
      },
      {
        id: '2',
        source: 'bobaedream',
        date: '2026-11-27',
        title: 't2',
        summary: 's2',
        verbatim_quote: 'q2',
        vehicle_model: '아이오닉5',
        defect_category: 'BUILD_QUALITY',
        defect_category_ko: '단차/누수/마감',
        severity: 'WARNING',
        sentiment_score: -0,
        slang_tags: [],
        url: 'https://www.bobaedream.co.kr/view?code=national&No=2',
      },
    ]);

    assert.equal(stats.total_filtered_defects, 2);
    assert.equal(stats.critical_defect_count, 1);
    assert.equal(stats.avg_negativity_score, 0.45);
  }
});

test('URL sanitization, SSRF, open-redirect, and JSON prototype-pollution guards hold on edge cases', () => {
  assert.equal(sanitizeSafeUrl('/a/b/..%2f..%2f//evil.com'), '#');
  assert.equal(sanitizeSafeUrl('/%2e%2e%5c/evil.com'), '#');
  assert.equal(sanitizeSafeUrl('https://ev.or.kr%40evil.com'), '#');
  assert.equal(sanitizeSafeUrl('https:evil.com'), '#');
  assert.equal(sanitizeSafeUrl('/search?q=javascript:alert(1)'), '#');

  for (const fn of [sanitizeReportUrlCalc, sanitizeReportUrlDaily]) {
    assert.equal(fn('http://0177.0.0.1/admin'), '#');
    assert.equal(fn('http://[2001:db8::1]/admin'), '#');
    assert.equal(fn('http://[2001:0:4136:e378:8000:63bf:3fff:fdd2]/'), '#');
    assert.equal(
      fn('https://www.bobaedream.co.kr/view?code=1&token=abc&__proto__=1#access_token=xyz&ok=1'),
      'https://www.bobaedream.co.kr/view?code=1#ok=1'
    );
  }

  const parsedJson = safeJsonParse(
    '{"__proto__":{"polluted":true},"constructor":{"prototype":{"x":1}},"ok":1}'
  );
  assert.equal(({}).polluted, undefined);
  assert.equal(parsedJson.ok, 1);

  const ld = serializeJsonLd({
    __proto__: { evil: true },
    text: '</script><script>alert(1)</script>',
  });
  assert.ok(!ld.includes('</script>'));
  assert.ok(!ld.includes('__proto__'));

  const q = parseSafeQueryParams('?a[__proto__]=1&constructor.prototype.x=2&model=ev3');
  assert.equal(Object.getPrototypeOf(q), null);
  assert.deepEqual({ ...q }, { model: 'ev3' });

  const daily = getDailyReports();
  assert.ok(daily.reports.length > 0);
  assert.equal(daily.statistics.total_filtered_defects, daily.reports.length);
});
