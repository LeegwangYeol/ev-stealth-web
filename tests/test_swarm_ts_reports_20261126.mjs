import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  sanitizeSafeUrl,
  parseSafeQueryParams,
  stripHtmlTags,
  sanitizeHtml,
} from '../src/lib/sanitizeUrl.ts';

import {
  sanitizeReportUrl as sanitizeReportUrlCalc,
  resolveCategory as resolveCategoryCalc,
  deduplicateReports as deduplicateReportsCalc,
} from '../src/lib/reportCalculations.ts';

import {
  sanitizeReportUrl as sanitizeReportUrlDaily,
  resolveCategory as resolveCategoryDaily,
  deduplicateReports as deduplicateReportsDaily,
} from '../src/lib/getDailyReports.ts';

test('stripHtmlTags blocks slash-delimited closing tags on executable blocks', () => {
  assert.equal(stripHtmlTags('<script>alert(1)</script/foo>'), '');
  assert.equal(stripHtmlTags('<style>body{background:red}</style/bar>'), '');
  assert.equal(stripHtmlTags('<svg><script>alert(1)</script/x></svg>'), '');
  assert.equal(sanitizeHtml('<p>안전</p><script>alert(1)</script/foo><p>보고</p>'), '안전\n보고');
});

test('stripHtmlTags strips entity-encoded control chars, bidi overrides, and whitespace-split javascript:', () => {
  assert.equal(stripHtmlTags('&#x202e;spoof'), 'spoof');
  assert.equal(stripHtmlTags('&#8238;rtl&#x2066;override'), 'rtloverride');
  assert.equal(stripHtmlTags('a&#x07;b&#x1b;c'), 'abc');
  assert.equal(stripHtmlTags('javascript&#x09;:alert(1)'), 'alert(1)');
  assert.equal(stripHtmlTags('javascript :alert(1)'), 'alert(1)');
});

test('stripHtmlTags handles deeply nested split executable tags in linear O(N) time', () => {
  const depth = 5000;
  const nested =
    '<scr'.repeat(depth) + '<script></script>' + 'ipt>alert(1)</script>'.repeat(depth);

  const t0 = performance.now();
  const out = stripHtmlTags(nested);
  const elapsedMs = performance.now() - t0;

  assert.equal(out, '');
  assert.ok(elapsedMs < 200, `Expected O(N) linear runtime (<200ms), got ${elapsedMs.toFixed(1)}ms`);

  // Alternating multi-tag nesting also stays bounded and leaves zero HTML tags
  const alt = '<scr<sty'.repeat(500) + 'le></style>ipt>alert(1)</script>'.repeat(500);
  const t1 = performance.now();
  const altOut = stripHtmlTags(alt);
  const altMs = performance.now() - t1;
  assert.ok(!altOut.includes('<') && !altOut.includes('>'));
  assert.ok(altMs < 200, `Expected bounded runtime (<200ms), got ${altMs.toFixed(1)}ms`);
});

test('sanitizeReportUrl strips sensitive tokens inside SPA hash-route queries', () => {
  for (const fn of [sanitizeReportUrlCalc, sanitizeReportUrlDaily]) {
    assert.equal(
      fn('https://www.bobaedream.co.kr/view#/callback?access_token=secret123&state=ok'),
      'https://www.bobaedream.co.kr/view#/callback?state=ok'
    );
    assert.equal(
      fn('https://www.bobaedream.co.kr/view#/callback?access_token=secret123'),
      'https://www.bobaedream.co.kr/view#/callback'
    );
    assert.equal(
      fn('/recall-portal#/oauth?token=secret123&page=2'),
      '/recall-portal#/oauth?page=2'
    );
    assert.equal(
      fn('/recall-portal#/oauth?id_token=xyz'),
      '/recall-portal#/oauth'
    );
    // Non-query hash fragments remain intact
    assert.equal(
      fn('https://www.bobaedream.co.kr/view?code=national#section-1'),
      'https://www.bobaedream.co.kr/view?code=national#section-1'
    );
  }
});

test('URL, query, and category helpers resist prototype pollution and open redirects', () => {
  assert.equal(sanitizeSafeUrl('/%2e%2e//evil.com'), '#');
  assert.equal(sanitizeSafeUrl('/..%2f/evil.com'), '#');
  assert.equal(
    sanitizeSafeUrl('https://ev.or.kr/path?%255f%255fproto%255f%255f=1&ok=2'),
    'https://ev.or.kr/path?ok=2'
  );

  const parsed = parseSafeQueryParams('?__proto__=bad&constructor=bad&prototype=bad&safe=ok');
  assert.equal(Object.getPrototypeOf(parsed), null);
  assert.deepEqual({ ...parsed }, { safe: 'ok' });

  for (const resolveFn of [resolveCategoryCalc, resolveCategoryDaily]) {
    const resolved = resolveFn('__proto__', 'constructor');
    assert.equal(resolved.code, 'BATTERY_CHARGING');
  }

  for (const dedupFn of [deduplicateReportsCalc, deduplicateReportsDaily]) {
    const { reports, summary } = dedupFn([
      { id: '1', source: 'clien', url: 'https://www.clien.net/service/board/park/1?utm_source=x' },
      { id: '1', source: 'clien', url: 'https://www.clien.net/service/board/park/1' },
      { id: '2', source: 'clien', url: 'http://[::ffff:127.0.0.1]/admin' },
    ]);
    assert.equal(summary.totalAfter, 2);
    assert.equal(summary.duplicatesRemoved, 1);
    assert.equal(reports[1].url, '#');
  }
});
