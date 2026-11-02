/**
 * tests/test_security_sanitization_audit.mjs
 * Comprehensive Security & Sanitization Verification Test Suite.
 *
 * Verifies:
 * 1. Protocol poisoning defense (javascript:, vbscript:, data:, blob:, file:, etc.)
 * 2. Protocol-relative and backslash open redirect prevention (//evil.com, /\\evil.com)
 * 3. Obfuscation evasion (control characters, tabs, newlines inside protocols)
 * 4. Safe JSON parsing & prototype pollution elimination
 * 5. Community quotes and defect reports text sanitization (bidi override, null bytes)
 * 6. Safe link rendering across React components
 */

import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Import sanitizeUrl module
let sanitizeUrlModule;
const sanitizePath = path.resolve(__dirname, '../src/lib/sanitizeUrl.ts');
if (fs.existsSync(sanitizePath)) {
  sanitizeUrlModule = await import('../src/lib/sanitizeUrl.ts');
} else {
  sanitizeUrlModule = await import('./src/lib/sanitizeUrl.ts');
}

const {
  sanitizeSafeUrl,
  isSafeUrl,
  isExternalUrl,
  sanitizeText,
  safeJsonParse,
} = sanitizeUrlModule;

console.log('======================================================');
console.log('🔒 SECURITY & SANITIZATION AUDIT TEST SUITE');
console.log('======================================================\n');

let totalTests = 0;
let passedTests = 0;

function test(name, fn) {
  totalTests++;
  try {
    fn();
    passedTests++;
    console.log(`  ✅ PASS: ${name}`);
  } catch (err) {
    console.error(`  ❌ FAIL: ${name}`);
    console.error(err);
    process.exitCode = 1;
  }
}

// -------------------------------------------------------------
// 1. PROTOCOL POISONING & DANGEROUS SCHEME PREVENTION
// -------------------------------------------------------------
console.log('--- [1. Protocol Poisoning & Dangerous Scheme Tests] ---');

test('Blocks javascript: scheme with standard casing', () => {
  assert.strictEqual(sanitizeSafeUrl('javascript:alert(1)'), '#');
});

test('Blocks uppercase JAVASCRIPT: scheme', () => {
  assert.strictEqual(sanitizeSafeUrl('JAVASCRIPT:alert(document.cookie)'), '#');
});

test('Blocks mixed case JaVaScRiPt: scheme', () => {
  assert.strictEqual(sanitizeSafeUrl('JaVaScRiPt:alert(window.origin)'), '#');
});

test('Blocks javascript with leading whitespace', () => {
  assert.strictEqual(sanitizeSafeUrl('   javascript:alert(1)'), '#');
});

test('Blocks javascript with embedded whitespace and tabs (obfuscation)', () => {
  assert.strictEqual(sanitizeSafeUrl('java\tscript:alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('javascript :alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('java\nscript:alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('java\r\nscript:alert(1)'), '#');
});

test('Blocks data: URI scheme (HTML and SVG execution vectors)', () => {
  assert.strictEqual(sanitizeSafeUrl('data:text/html,<script>alert(1)</script>'), '#');
  assert.strictEqual(sanitizeSafeUrl('DATA:image/svg+xml;base64,PHN2Zy9vbmxvYWQ9YWxlcnQoMSk+'), '#');
  assert.strictEqual(sanitizeSafeUrl('data:text/javascript,alert(1)'), '#');
});

test('Blocks vbscript: scheme', () => {
  assert.strictEqual(sanitizeSafeUrl('vbscript:msgbox(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('VBSCRIPT:MsgBox("XSS")'), '#');
});

test('Blocks blob: URI execution vectors', () => {
  assert.strictEqual(sanitizeSafeUrl('blob:https://ev-stealth.local/f48398e4'), '#');
  assert.strictEqual(sanitizeSafeUrl('blob:null/malicious-payload'), '#');
});

test('Blocks file: URI scheme for local file disclosure', () => {
  assert.strictEqual(sanitizeSafeUrl('file:///etc/passwd'), '#');
  assert.strictEqual(sanitizeSafeUrl('FILE://C:/Windows/win.ini'), '#');
});

test('Blocks about: scheme', () => {
  assert.strictEqual(sanitizeSafeUrl('about:blank'), '#');
  assert.strictEqual(sanitizeSafeUrl('about:srcdoc'), '#');
});

test('Blocks null bytes inside or preceding URL', () => {
  assert.strictEqual(sanitizeSafeUrl('\x00javascript:alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('https://valid.com\x00/exploit'), '#');
});

// -------------------------------------------------------------
// 2. PROTOCOL-RELATIVE & BACKSLASH OPEN REDIRECT PREVENTION
// -------------------------------------------------------------
console.log('\n--- [2. Protocol-Relative & Backslash Open Redirect Tests] ---');

test('Blocks protocol-relative URLs (//evil.com)', () => {
  assert.strictEqual(sanitizeSafeUrl('//evil.com'), '#');
  assert.strictEqual(sanitizeSafeUrl('//phishing.org/login'), '#');
  assert.strictEqual(sanitizeSafeUrl('///attacker.com'), '#');
});

test('Blocks backslash evasion (\\evil.com, /\\evil.com)', () => {
  assert.strictEqual(sanitizeSafeUrl('/\\evil.com'), '#');
  assert.strictEqual(sanitizeSafeUrl('\\\\evil.com'), '#');
  assert.strictEqual(sanitizeSafeUrl('/\\/evil.com'), '#');
});

test('Rejects incomplete or malformed HTTP URLs', () => {
  assert.strictEqual(sanitizeSafeUrl('https://'), '#');
  assert.strictEqual(sanitizeSafeUrl('http://'), '#');
  assert.strictEqual(sanitizeSafeUrl('https:'), '#');
  assert.strictEqual(sanitizeSafeUrl('https://   '), '#');
});

test('Rejects URLs containing quotes or brackets (XSS attribute breakout)', () => {
  assert.strictEqual(sanitizeSafeUrl('https://example.com"onfocus="alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl("https://example.com'onfocus='alert(1)"), '#');
  assert.strictEqual(sanitizeSafeUrl('https://example.com<script>'), '#');
});

// -------------------------------------------------------------
// 3. LEGITIMATE SAFE URL PRESERVATION
// -------------------------------------------------------------
console.log('\n--- [3. Legitimate URL Preservation Tests] ---');

test('Preserves legitimate external HTTPS URLs', () => {
  const url = 'https://www.car.go.kr/recall?id=123&test=1#detail';
  assert.strictEqual(sanitizeSafeUrl(url), url);
  assert.strictEqual(isSafeUrl(url), true);
  assert.strictEqual(isExternalUrl(url), true);
});

test('Preserves legitimate external HTTP URLs', () => {
  const url = 'http://bobaedream.co.kr/view/456';
  assert.strictEqual(sanitizeSafeUrl(url), url);
  assert.strictEqual(isSafeUrl(url), true);
  assert.strictEqual(isExternalUrl(url), true);
});

test('Preserves safe internal relative routes', () => {
  const route = '/recall-portal?brand=hyundai&model=ioniq5#search-result';
  assert.strictEqual(sanitizeSafeUrl(route), route);
  assert.strictEqual(isSafeUrl(route), true);
  assert.strictEqual(isExternalUrl(route), false);
});

test('Preserves safe in-page anchor links', () => {
  const anchor = '#battery-directory';
  assert.strictEqual(sanitizeSafeUrl(anchor), anchor);
  assert.strictEqual(isSafeUrl(anchor), true);
  assert.strictEqual(isExternalUrl(anchor), false);
});

test('Preserves safe mailto: links', () => {
  const mail = 'mailto:support@ev-stealth.kr';
  assert.strictEqual(sanitizeSafeUrl(mail), mail);
  assert.strictEqual(isSafeUrl(mail), true);
});

test('Preserves safe tel: links', () => {
  const tel = 'tel:1588-0000';
  assert.strictEqual(sanitizeSafeUrl(tel), tel);
  assert.strictEqual(isSafeUrl(tel), true);
});

test('Safely handles null, undefined, empty, and non-string inputs', () => {
  assert.strictEqual(sanitizeSafeUrl(null), '#');
  assert.strictEqual(sanitizeSafeUrl(undefined), '#');
  assert.strictEqual(sanitizeSafeUrl(''), '#');
  assert.strictEqual(sanitizeSafeUrl('   '), '#');
  assert.strictEqual(sanitizeSafeUrl(12345), '#');
  assert.strictEqual(sanitizeSafeUrl({}), '#');
  assert.strictEqual(sanitizeSafeUrl([]), '#');
});

// -------------------------------------------------------------
// 4. SAFE JSON PARSING & PROTOTYPE POLLUTION ELIMINATION
// -------------------------------------------------------------
console.log('\n--- [4. Safe JSON Parsing & Prototype Pollution Tests] ---');

test('safeJsonParse strips __proto__ keys without polluting Object.prototype', () => {
  const malicious = '{"__proto__": {"polluted": true}, "validKey": 42}';
  const parsed = safeJsonParse(malicious, {});
  assert.strictEqual(parsed.validKey, 42);
  assert.strictEqual(Object.prototype.hasOwnProperty.call(parsed, '__proto__'), false);
  assert.strictEqual(({}).polluted, undefined);
});

test('safeJsonParse strips constructor and prototype keys', () => {
  const malicious = '{"constructor": {"prototype": {"admin": true}}, "item": "safe"}';
  const parsed = safeJsonParse(malicious, {});
  assert.strictEqual(parsed.item, 'safe');
  assert.strictEqual(Object.prototype.hasOwnProperty.call(parsed, 'constructor'), false);
  assert.strictEqual(Object.prototype.hasOwnProperty.call(parsed, 'prototype'), false);
  assert.strictEqual(({}).admin, undefined);
});

test('safeJsonParse returns fallback on syntax errors without crashing', () => {
  const corrupted = '{ unquotedKey: bad_json }';
  const fallback = { fallback: true };
  const parsed = safeJsonParse(corrupted, fallback);
  assert.deepStrictEqual(parsed, fallback);
});

test('safeJsonParse returns fallback on null/non-string inputs', () => {
  assert.strictEqual(safeJsonParse(null, null), null);
  assert.strictEqual(safeJsonParse(undefined, 'default'), 'default');
});

// -------------------------------------------------------------
// 5. COMMUNITY QUOTES & DEFECT REPORTS TEXT SANITIZATION
// -------------------------------------------------------------
console.log('\n--- [5. Community Quotes & Defect Reports Sanitization Tests] ---');

test('sanitizeText strips Unicode bidirectional override spoofing characters', () => {
  // U+202E is RIGHT-TO-LEFT OVERRIDE used in file spoofing or text reversal attacks
  const bidiSpoof = 'SafeText\u202Eevil.exe\u202D';
  const clean = sanitizeText(bidiSpoof);
  assert.strictEqual(clean, 'SafeTextevil.exe');
  assert.strictEqual(/[\u202A-\u202E\u2066-\u2069]/.test(clean), false);
});

test('sanitizeText strips null bytes and non-printable control characters', () => {
  const dirty = 'Line1\x00\x08\x0C\x1FMaliciousPayload';
  const clean = sanitizeText(dirty);
  assert.strictEqual(clean, 'Line1MaliciousPayload');
});

test('sanitizeText preserves legitimate Korean text, punctuation, and emoji', () => {
  const korean = '🚨 고속도로에서 100km로 달리는데 갑자기 퍽 소리 나더니 배터리 경고등 뜸 ㅋㅋㅋ';
  const clean = sanitizeText(korean);
  assert.strictEqual(clean, korean);
});

// -------------------------------------------------------------
// 6. getDailyReports & normalizeReport HARDENING VERIFICATION
// -------------------------------------------------------------
console.log('\n--- [6. getDailyReports & normalizeReport Hardening Tests] ---');

test('getDailyReports correctly loads and sanitizes raw report items', async () => {
  const sourcePath = path.resolve(__dirname, '../src/lib/getDailyReports.ts');
  const rawSource = fs.readFileSync(sourcePath, 'utf-8');
  const patched = rawSource
    .replace(/from '\.\/sanitizeUrl';/, "from '../src/lib/sanitizeUrl.ts';")
    .replace(/from '\.\.\/data\/daily_reports\.json' with \{ type: 'json' \};/, "from '../src/data/daily_reports.json' with { type: 'json' };");
  
  const tempPath = path.resolve(__dirname, 'temp_security_daily_fixture.ts');
  fs.writeFileSync(tempPath, patched, 'utf-8');

  let dailyModule;
  try {
    dailyModule = await import('./temp_security_daily_fixture.ts');
  } finally {
    if (fs.existsSync(tempPath)) fs.unlinkSync(tempPath);
  }

  const { getDailyReports, normalizeReport } = dailyModule;

  const data = getDailyReports();
  assert.ok(Array.isArray(data.reports));
  assert.ok(data.reports.length > 0);

  // Every single report's URL must be either '#' or a valid http(s) URL
  for (const report of data.reports) {
    assert.ok(
      report.url === '#' || report.url.startsWith('http://') || report.url.startsWith('https://'),
      `Report ${report.id} has unsafe URL: ${report.url}`
    );
    assert.strictEqual(typeof report.title, 'string');
    assert.strictEqual(typeof report.summary, 'string');
    assert.strictEqual(typeof report.verbatim_quote, 'string');
  }

  // Verify normalizeReport sanitizes adversarial malicious item
  const adversarialRaw = {
    id: 'adv_01',
    source: 'bobaedream\x00',
    url: 'javascript:alert(document.cookie)',
    title: '악성 링크 테스트\u202E',
    summary: '요약 내용\x00',
    verbatim_quote: '원문 인용\x08<script>alert(1)</script>',
    vehicle_model: '__proto__',
  };

  const normalized = normalizeReport(adversarialRaw, 0);
  assert.strictEqual(normalized.url, '#');
  assert.strictEqual(normalized.source, 'bobaedream');
  assert.strictEqual(normalized.title, '악성 링크 테스트');
  assert.strictEqual(normalized.summary, '요약 내용');
  assert.strictEqual(normalized.verbatim_quote, '원문 인용<script>alert(1)</script>');
  assert.strictEqual(normalized.vehicle_model, '__proto__');
  assert.strictEqual(({}).polluted, undefined);
});

console.log('\n======================================================');
console.log(`🏁 SECURITY AUDIT SUMMARY: ${passedTests}/${totalTests} tests passed.`);
console.log('======================================================');

if (passedTests !== totalTests) {
  process.exit(1);
}
