import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  extractHostname,
  isGovernmentDomain,
  isWhitelistedDomain,
  sanitizeSafeUrl,
  stripHtmlTags,
  sanitizeHtml,
} from '../src/lib/sanitizeUrl.ts';

import {
  sanitizeReportUrl as sanitizeReportUrlCalc,
  normalizeReport as normalizeReportCalc,
  calculateKPIs as calculateKPIsCalc,
  getSafeSentimentScore as getSafeSentimentScoreCalc,
} from '../src/lib/reportCalculations.ts';

import {
  sanitizeReportUrl as sanitizeReportUrlDaily,
  normalizeReport as normalizeReportDaily,
  calculateKPIs as calculateKPIsDaily,
  getDailyReports,
} from '../src/lib/getDailyReports.ts';

test('extractHostname rejects empty-userinfo @ in authority while allowing @ in path', () => {
  assert.equal(extractHostname('https://@ev.or.kr/steal'), '');
  assert.equal(extractHostname('http://@localhost:3000/admin'), '');
  assert.equal(extractHostname('@ev.or.kr'), '');
  assert.equal(extractHostname('https://user@ev.or.kr/steal'), '');
  assert.equal(isGovernmentDomain('https://@ev.or.kr/steal'), false);
  assert.equal(isWhitelistedDomain('https://@ev.or.kr/steal'), false);
  assert.equal(sanitizeSafeUrl('https://@ev.or.kr/steal'), '#');

  // Legitimate @ in URL path is preserved
  assert.equal(extractHostname('https://ev.or.kr/@official'), 'ev.or.kr');
  assert.equal(isGovernmentDomain('https://ev.or.kr/@official'), true);
});

test('stripHtmlTags completely strips nested/interleaved executable blocks and attributed closing tags in linear time', () => {
  assert.equal(stripHtmlTags('<scr<script></script>ipt>alert(1)</script>'), '');
  assert.equal(
    stripHtmlTags('&lt;scr&lt;script&gt;&lt;/script&gt;ipt&gt;alert(1)&lt;/script&gt;'),
    ''
  );
  assert.equal(stripHtmlTags('<script>alert(1)</script foo="bar">'), '');
  assert.equal(sanitizeHtml('정상 <svg><svg></svg>onload=alert(1)</svg> 보고'), '정상 보고');

  // ReDoS guard: thousands of unclosed closing/opening tags complete quickly
  const pathological = '</script '.repeat(5000) + '<script '.repeat(5000);
  const start = performance.now();
  const out = stripHtmlTags(pathological);
  const elapsedMs = performance.now() - start;
  assert.ok(elapsedMs < 250, `Expected linear runtime (<250ms), got ${elapsedMs.toFixed(1)}ms`);
  assert.equal(typeof out, 'string');
});

test('sanitizeReportUrl strips sensitive query and hash params on both external and relative URLs', () => {
  for (const fn of [sanitizeReportUrlCalc, sanitizeReportUrlDaily]) {
    assert.equal(
      fn('https://www.bobaedream.co.kr/view?code=national&token=secret123#access_token=abc'),
      'https://www.bobaedream.co.kr/view?code=national'
    );
    assert.equal(
      fn('/recall-portal?brand=hyundai&token=secret123#access_token=xyz&tab=list'),
      '/recall-portal?brand=hyundai#tab=list'
    );
    assert.equal(fn('/recall-portal?token=secret123#access_token=xyz'), '/recall-portal');
    assert.equal(fn('/recall-portal?brand=hyundai'), '/recall-portal?brand=hyundai');
    assert.equal(fn('http://127.0.0.1/internal'), '#');
    assert.equal(fn('http://[::ffff:127.0.0.1]/internal'), '#');
  }
});

test('normalizeReport guards defect_category_ko against prototype keys and sensitive leaks, and handles numeric edge cases', () => {
  for (const norm of [normalizeReportCalc, normalizeReportDaily]) {
    const protoAttempt = norm(
      {
        defect_category: 'BATTERY_CHARGING',
        defect_category_ko: '__proto__',
        sentiment_score: -0,
        severity_index: NaN,
        dsi_breakdown: { safety: NaN, functional: Infinity, economic: -0 },
      },
      NaN
    );
    assert.equal(protoAttempt.id, 'report_1');
    assert.equal(protoAttempt.defect_category, 'BATTERY_CHARGING');
    assert.equal(protoAttempt.defect_category_ko, '배터리/충전');
    assert.ok(Object.is(protoAttempt.sentiment_score, 0));
    assert.equal(protoAttempt.severity_index, undefined);
    assert.ok(Object.is(protoAttempt.dsi_breakdown?.safety, 0));
    assert.ok(Object.is(protoAttempt.dsi_breakdown?.functional, 0));
    assert.ok(Object.is(protoAttempt.dsi_breakdown?.economic, 0));

    const leakedCat = norm(
      {
        defect_category: 'BUILD_QUALITY',
        defect_category_ko: 'Bearer sk-proj-12345678901234567890123456',
      },
      0
    );
    assert.ok(!leakedCat.defect_category_ko.includes('sk-proj-'));

    const customCat = norm(
      {
        defect_category: 'BATTERY_CHARGING',
        defect_category_ko: '고전압 배터리 시스템',
      },
      0
    );
    assert.equal(customCat.defect_category_ko, '고전압 배터리 시스템');
  }

  for (const kpiFn of [calculateKPIsCalc, calculateKPIsDaily]) {
    const kpis = kpiFn([], {
      total_scraped: -0,
      critical_defect_count: NaN,
      avg_negativity_score: Infinity,
      duplicates_removed: -5,
    });
    assert.ok(Object.is(kpis.total_scraped, 0));
    assert.ok(Object.is(kpis.critical_defect_count, 0));
    assert.ok(Object.is(kpis.avg_negativity_score, 0));
    assert.ok(Object.is(kpis.duplicates_removed, 0));
  }

  assert.ok(Object.is(getSafeSentimentScoreCalc(-0, -0), 0));
  assert.equal(getSafeSentimentScoreCalc(Infinity, 0.5), 0.5);

  const loaded = getDailyReports();
  assert.ok(Array.isArray(loaded.reports));
  assert.ok(Number.isFinite(loaded.statistics.avg_negativity_score));
});
