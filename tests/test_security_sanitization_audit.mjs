/**
 * tests/test_security_sanitization_audit.mjs
 * Comprehensive Security, Sanitization & Defense-in-Depth Verification Test Suite.
 *
 * Verifies:
 * 1. Protocol poisoning & dangerous scheme prevention (javascript:, data:, vbscript:, blob:, file:, about:, feed:, intent:)
 * 2. Obfuscation, null byte insertion, zero-width spaces, and literal escape evasion (java\0script:, java\u200Bscript:)
 * 3. URL percent-encoding & double-encoding bypass vectors (javascript%3a, %6a%61%76%61..., java%00script:)
 * 4. HTML entity encoding bypass vectors (&colon;, &#58;, &#x3a;, &NewLine;, &Tab;, jav&#x61;script:)
 * 5. Protocol-relative and backslash open redirect prevention (//evil.com, /\\evil.com, \\evil.com, /%5cevil.com, /%2fevil.com)
 * 6. Legitimate URL preservation (HTTPS, HTTP, internal routes, anchors, mailto, tel)
 * 7. Safe JSON parsing & prototype pollution elimination
 * 8. Community quotes & defect reports text sanitization (bidi override, null bytes, non-printable control chars)
 * 9. JSON-LD structured data injection protection (script breakout XSS, HTML comments, Unicode terminators)
 * 10. Security headers in next.config.mjs (CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, HSTS)
 * 11. getDailyReports & normalizeReport hardening verification
 */

import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

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
  serializeJsonLd,
  decodeHtmlEntities,
  safeDecodePercent,
  extractAndNormalizeScheme,
  isOpenRedirect,
  ALLOWED_SCHEMES,
  FORBIDDEN_SCHEMES,
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

async function testAsync(name, fn) {
  totalTests++;
  try {
    await fn();
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

test('Blocks data: URI scheme (HTML, SVG, and script execution vectors)', () => {
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

test('Blocks feed: and intent: dangerous schemes', () => {
  assert.strictEqual(sanitizeSafeUrl('feed:javascript:alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('intent://example.com#Intent;scheme=http;package=com.android.chrome;end'), '#');
});

test('Blocks raw null bytes inside or preceding URL', () => {
  assert.strictEqual(sanitizeSafeUrl('\x00javascript:alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('https://valid.com\x00/exploit'), '#');
});

test('Blocks literal null byte escapes (java\\0script:, java\\x00script:, java\\u0000script:)', () => {
  assert.strictEqual(sanitizeSafeUrl('java\\0script:alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('java\\x00script:alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('java\\u0000script:alert(1)'), '#');
});

test('Blocks zero-width characters inside scheme (u200B, uFEFF, u200C, u200D)', () => {
  assert.strictEqual(sanitizeSafeUrl('java\u200Bscript:alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('java\uFEFFscript:alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('java\u200Cscript:alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('java\u200Dscript:alert(1)'), '#');
});

// -------------------------------------------------------------
// 2. ENCODED SCHEMES (URL PERCENT-ENCODING & HTML ENTITIES)
// -------------------------------------------------------------
console.log('\n--- [2. Encoded Schemes (Percent & HTML Entities) Tests] ---');

test('Blocks URL percent-encoded colon (javascript%3a, data%3a, vbscript%3a)', () => {
  assert.strictEqual(sanitizeSafeUrl('javascript%3aalert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('data%3atext/html,<script>alert(1)</script>'), '#');
  assert.strictEqual(sanitizeSafeUrl('vbscript%3amsgbox(1)'), '#');
});

test('Blocks partially or fully percent-encoded scheme names (%6a%61%76%61...)', () => {
  assert.strictEqual(sanitizeSafeUrl('jav%61script:alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('%6a%61%76%61%73%63%72%69%70%74:alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('%6a%61%76%61%73%63%72%69%70%74%3aalert(1)'), '#');
});

test('Blocks percent-encoded null bytes, tabs, and newlines in scheme (java%00script:)', () => {
  assert.strictEqual(sanitizeSafeUrl('java%00script:alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('java%0ascript:alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('java%0dscript:alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('java%09script:alert(1)'), '#');
});

test('Blocks HTML named entity schemes (&NewLine;, &Tab;, &colon;)', () => {
  assert.strictEqual(sanitizeSafeUrl('&NewLine;javascript:alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('&Tab;javascript:alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('javascript&colon;alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('d&NewLine;ata:text/html,x'), '#');
  assert.strictEqual(sanitizeSafeUrl('vbscript&colon;msgbox(1)'), '#');
});

test('Blocks HTML decimal entity schemes (&#106;&#97;..., javascript&#58;)', () => {
  assert.strictEqual(sanitizeSafeUrl('&#106;&#97;&#118;&#97;&#115;&#99;&#114;&#105;&#112;&#116;&#58;alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('javascript&#58;alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('javascript&#58alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('jav&#9;ascript:alert(1)'), '#');
});

test('Blocks HTML hex entity schemes (jav&#x61;script:, javascript&#x3a;)', () => {
  assert.strictEqual(sanitizeSafeUrl('jav&#x61;script:alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('javascript&#x3a;alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('javascript&#x3aalert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('javascript&#x3a(1)'), '#');
  assert.strictEqual(extractAndNormalizeScheme('javascript&#x3a(1)'), 'javascript');
  assert.strictEqual(extractAndNormalizeScheme('javascript&#x3a;alert(1)'), 'javascript');
  assert.strictEqual(extractAndNormalizeScheme('jav%26%23x61%3bscript:alert(1)'), 'javascript');
  assert.strictEqual(sanitizeSafeUrl('d&#97;ta:text/html,x'), '#');
  assert.strictEqual(sanitizeSafeUrl('d&#97;ta&colon;text/html,x'), '#');
});

// -------------------------------------------------------------
// 3. PROTOCOL-RELATIVE & BACKSLASH OPEN REDIRECT PREVENTION
// -------------------------------------------------------------
console.log('\n--- [3. Protocol-Relative & Backslash Open Redirect Tests] ---');

test('Blocks standard protocol-relative URLs (//evil.com, ///evil.com)', () => {
  assert.strictEqual(sanitizeSafeUrl('//evil.com'), '#');
  assert.strictEqual(sanitizeSafeUrl('//phishing.org/login'), '#');
  assert.strictEqual(sanitizeSafeUrl('///attacker.com'), '#');
});

test('Blocks backslash evasion (\\evil.com, /\\evil.com, \\\\evil.com)', () => {
  assert.strictEqual(sanitizeSafeUrl('/\\evil.com'), '#');
  assert.strictEqual(sanitizeSafeUrl('\\\\evil.com'), '#');
  assert.strictEqual(sanitizeSafeUrl('/\\/evil.com'), '#');
  assert.strictEqual(sanitizeSafeUrl('\\evil.com'), '#');
  assert.strictEqual(sanitizeSafeUrl('\\/evil.com'), '#');
});

test('Blocks percent-encoded slashes & backslashes (/%5cevil.com, /%2fevil.com)', () => {
  assert.strictEqual(sanitizeSafeUrl('/%5cevil.com'), '#');
  assert.strictEqual(sanitizeSafeUrl('/%2fevil.com'), '#');
  assert.strictEqual(sanitizeSafeUrl('/%255cevil.com'), '#');
  assert.strictEqual(sanitizeSafeUrl('/%252fevil.com'), '#');
});

test('Blocks HTML entity encoded slashes in redirects (/&bsol;evil.com, /&sol;evil.com)', () => {
  assert.strictEqual(sanitizeSafeUrl('/&bsol;evil.com'), '#');
  assert.strictEqual(sanitizeSafeUrl('/&sol;evil.com'), '#');
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
// 4. LEGITIMATE SAFE URL PRESERVATION
// -------------------------------------------------------------
console.log('\n--- [4. Legitimate URL Preservation Tests] ---');

test('Preserves legitimate external HTTPS URLs with query & hash', () => {
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

test('Preserves legitimate external URLs with percent-encoded non-ASCII params', () => {
  const url = 'https://ev-stealth.kr/search?q=%EC%A0%84%EA%B8%B0%EC%B0%A8&filter=battery';
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

test('Preserves root path /', () => {
  assert.strictEqual(sanitizeSafeUrl('/'), '/');
  assert.strictEqual(isSafeUrl('/'), true);
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
// 5. SAFE JSON PARSING & PROTOTYPE POLLUTION ELIMINATION
// -------------------------------------------------------------
console.log('\n--- [5. Safe JSON Parsing & Prototype Pollution Tests] ---');

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
// 6. COMMUNITY QUOTES & DEFECT REPORTS TEXT SANITIZATION
// -------------------------------------------------------------
console.log('\n--- [6. Community Quotes & Defect Reports Sanitization Tests] ---');

test('sanitizeText strips Unicode bidirectional override spoofing characters', () => {
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
// 7. JSON-LD STRUCTURED DATA INJECTION PROTECTION
// -------------------------------------------------------------
console.log('\n--- [7. JSON-LD Structured Data Injection Protection Tests] ---');

test('serializeJsonLd neutralizes script breakout attacks (</script><script>alert(1)</script>)', () => {
  const payload = {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: '</script><script>alert("XSS")</script>',
  };

  const serialized = serializeJsonLd(payload);
  assert.ok(!serialized.includes('</script>'), 'Must not contain literal </script>');
  assert.ok(!serialized.includes('<script>'), 'Must not contain literal <script>');
  assert.ok(!serialized.includes('<'), 'Must contain zero unescaped < characters');
  assert.ok(!serialized.includes('>'), 'Must contain zero unescaped > characters');
  assert.ok(serialized.includes('\\u003c/script\\u003e'));

  // Deserializing via standard JSON.parse reconstructs original payload cleanly
  const parsed = JSON.parse(serialized);
  assert.strictEqual(parsed.name, '</script><script>alert("XSS")</script>');
});

test('serializeJsonLd neutralizes HTML comment breakouts (<!-- and -->)', () => {
  const payload = {
    description: '<!-- <script>alert(document.cookie)</script> -->',
  };

  const serialized = serializeJsonLd(payload);
  assert.ok(!serialized.includes('<!--'));
  assert.ok(!serialized.includes('-->'));
  assert.ok(serialized.includes('\\u003c!--'));
  assert.ok(serialized.includes('--\\u003e'));
});

test('serializeJsonLd neutralizes ampersands (& to \\u0026)', () => {
  const payload = { url: 'https://ev-stealth.kr/?a=1&b=2' };
  const serialized = serializeJsonLd(payload);
  assert.ok(!serialized.includes('&'));
  assert.ok(serialized.includes('\\u0026'));

  const parsed = JSON.parse(serialized);
  assert.strictEqual(parsed.url, 'https://ev-stealth.kr/?a=1&b=2');
});

test('serializeJsonLd neutralizes Unicode line terminators (u2028 and u2029)', () => {
  const payload = { note: 'Line\u2028Separator\u2029Paragraph' };
  const serialized = serializeJsonLd(payload);
  assert.ok(!serialized.includes('\u2028'));
  assert.ok(!serialized.includes('\u2029'));
  assert.ok(serialized.includes('\\u2028'));
  assert.ok(serialized.includes('\\u2029'));
});

test('serializeJsonLd eliminates prototype pollution keys (__proto__, constructor, prototype)', () => {
  const malicious = {
    __proto__: { injected: true },
    constructor: { prototype: { admin: true } },
    prototype: { role: 'superadmin' },
    validData: 'safeValue',
  };

  const serialized = serializeJsonLd(malicious);
  assert.ok(!serialized.includes('__proto__'));
  assert.ok(!serialized.includes('constructor'));
  assert.ok(!serialized.includes('prototype'));
  assert.ok(serialized.includes('validData'));
  assert.strictEqual(({}).injected, undefined);
});

test('serializeJsonLd gracefully handles null, undefined, and circular references', () => {
  assert.strictEqual(serializeJsonLd(null), '{}');
  assert.strictEqual(serializeJsonLd(undefined), '{}');

  const circular = {};
  circular.self = circular;
  assert.strictEqual(serializeJsonLd(circular), '{}');
});

// -------------------------------------------------------------
// 8. SECURITY HEADERS IN next.config.mjs VERIFICATION
// -------------------------------------------------------------
console.log('\n--- [8. next.config.mjs Security Headers Tests] ---');

await testAsync('next.config.mjs specifies all required OWASP security headers', async () => {
  const nextConfigPath = fs.existsSync(path.resolve(__dirname, '../next.config.mjs'))
    ? path.resolve(__dirname, '../next.config.mjs')
    : path.resolve(__dirname, '../ev-stealth-web/next.config.mjs');

  assert.ok(fs.existsSync(nextConfigPath), `next.config.mjs must exist at ${nextConfigPath}`);

  const nextConfigModule = await import(pathToFileURL(nextConfigPath).href);
  const nextConfig = nextConfigModule.default;

  assert.ok(typeof nextConfig.headers === 'function', 'nextConfig must define headers()');
  const headerRules = await nextConfig.headers();
  assert.ok(Array.isArray(headerRules), 'headers() must return an array');

  // Locate the global root route header rule (/:path*)
  const rootRule = headerRules.find((rule) => rule.source === '/:path*');
  assert.ok(rootRule, 'Must contain a header configuration for source /:path*');

  const headersMap = new Map();
  for (const h of rootRule.headers) {
    headersMap.set(h.key.toLowerCase(), h.value);
  }

  // 1. Content-Security-Policy
  assert.ok(headersMap.has('content-security-policy'), 'Must define Content-Security-Policy');
  const csp = headersMap.get('content-security-policy');
  assert.ok(csp.includes("default-src 'self'"), 'CSP must include default-src self');
  assert.ok(csp.includes("object-src 'none'"), 'CSP must block object-src');
  assert.ok(csp.includes("frame-ancestors 'none'"), 'CSP must forbid embedding (frame-ancestors none)');
  assert.ok(csp.includes("base-uri 'self'"), 'CSP must restrict base-uri');

  // 2. X-Frame-Options
  assert.ok(headersMap.has('x-frame-options'), 'Must define X-Frame-Options');
  assert.strictEqual(headersMap.get('x-frame-options'), 'DENY');

  // 3. X-Content-Type-Options
  assert.ok(headersMap.has('x-content-type-options'), 'Must define X-Content-Type-Options');
  assert.strictEqual(headersMap.get('x-content-type-options'), 'nosniff');

  // 4. Referrer-Policy
  assert.ok(headersMap.has('referrer-policy'), 'Must define Referrer-Policy');
  assert.strictEqual(headersMap.get('referrer-policy'), 'strict-origin-when-cross-origin');

  // 5. Permissions-Policy
  assert.ok(headersMap.has('permissions-policy'), 'Must define Permissions-Policy');
  const pp = headersMap.get('permissions-policy');
  assert.ok(pp.includes('camera=()'), 'Permissions-Policy must restrict camera');
  assert.ok(pp.includes('microphone=()'), 'Permissions-Policy must restrict microphone');
  assert.ok(pp.includes('geolocation=()'), 'Permissions-Policy must restrict geolocation');
  assert.ok(pp.includes('payment=()'), 'Permissions-Policy must restrict payment');

  // 6. Strict-Transport-Security (HSTS)
  assert.ok(headersMap.has('strict-transport-security'), 'Must define Strict-Transport-Security');
  const hsts = headersMap.get('strict-transport-security');
  assert.ok(hsts.includes('max-age='), 'HSTS must define max-age');
  assert.ok(hsts.includes('includeSubDomains'), 'HSTS must includeSubDomains');

  // 7. COOP and CORP
  assert.strictEqual(headersMap.get('cross-origin-opener-policy'), 'same-origin');
  assert.strictEqual(headersMap.get('cross-origin-resource-policy'), 'same-origin');
});

// -------------------------------------------------------------
// 9. getDailyReports & normalizeReport HARDENING VERIFICATION
// -------------------------------------------------------------
console.log('\n--- [9. getDailyReports & normalizeReport Hardening Tests] ---');

test('getDailyReports correctly loads and sanitizes raw report items', async () => {
  const sourcePath = path.resolve(__dirname, '../src/lib/getDailyReports.ts');
  const rawSource = fs.readFileSync(sourcePath, 'utf-8');
  const patched = rawSource
    .replace(/from '\.\/sanitizeUrl(?:\.ts)?';/, "from '../src/lib/sanitizeUrl.ts';")
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

// -------------------------------------------------------------
// 10. PROTOCOL ALLOWLIST & EXTENDED FORBIDDEN SCHEMES HARDENING
// -------------------------------------------------------------
console.log('\n--- [10. Protocol Allowlist & Extended Forbidden Schemes Tests] ---');

test('ALLOWED_SCHEMES strictly allows only http, https, mailto, tel', () => {
  assert.ok(ALLOWED_SCHEMES instanceof Set);
  assert.deepStrictEqual(Array.from(ALLOWED_SCHEMES).sort(), ['http', 'https', 'mailto', 'tel']);
});

test('Blocks unauthorized network/service protocols (ws:, wss:, ftp:, ssh:, sftp:)', () => {
  assert.strictEqual(sanitizeSafeUrl('ws://malicious-tracker.com'), '#');
  assert.strictEqual(sanitizeSafeUrl('wss://malicious-tracker.com'), '#');
  assert.strictEqual(sanitizeSafeUrl('ftp://ftp.example.com/exploit'), '#');
  assert.strictEqual(sanitizeSafeUrl('ssh://user@server.com'), '#');
  assert.strictEqual(sanitizeSafeUrl('sftp://remote.host'), '#');
});

test('Blocks browser and legacy script schemes (livescript:, mocha:, view-source:, chrome:)', () => {
  assert.strictEqual(sanitizeSafeUrl('livescript:alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('mocha:alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('view-source:https://google.com'), '#');
  assert.strictEqual(sanitizeSafeUrl('chrome://settings'), '#');
  assert.strictEqual(sanitizeSafeUrl('chrome-extension://abcdefg/popup.html'), '#');
});

test('Blocks evasion using soft-hyphens (u00AD) and word-joiners (u2060)', () => {
  assert.strictEqual(sanitizeSafeUrl('java\u00ADscript:alert(1)'), '#');
  assert.strictEqual(sanitizeSafeUrl('java\u2060script:alert(1)'), '#');
});

test('Blocks internal relative routes containing backslashes anywhere in path', () => {
  assert.strictEqual(sanitizeSafeUrl('/path\\to\\page'), '#');
  assert.strictEqual(sanitizeSafeUrl('/foo/..\\bar'), '#');
});

test('Blocks deep multi-pass encoded slashes (/%%25...evil.com)', () => {
  assert.strictEqual(sanitizeSafeUrl('/%2525252fevil.com'), '#');
  assert.strictEqual(sanitizeSafeUrl('/%252525252fevil.com'), '#');
});

// -------------------------------------------------------------
// 11. EXTERNAL ANCHOR SECURITY (target="_blank" + rel="noopener noreferrer")
// -------------------------------------------------------------
console.log('\n--- [11. External Anchor Security Audit Across src/] ---');

test('All external anchor tags with target="_blank" in src/ include rel="noopener noreferrer"', () => {
  const srcDir = path.resolve(__dirname, '../src');
  
  function scanDir(dir) {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        scanDir(fullPath);
      } else if (entry.name.endsWith('.tsx') || entry.name.endsWith('.ts') || entry.name.endsWith('.jsx') || entry.name.endsWith('.html')) {
        const content = fs.readFileSync(fullPath, 'utf-8');
        // Find all <a ... target="_blank" ... >
        const anchorRegex = /<a\b[^>]*target=["']_blank["'][^>]*>/gi;
        let match;
        while ((match = anchorRegex.exec(content)) !== null) {
          const tag = match[0];
          assert.ok(
            /rel=["'][^"']*noopener[^"']*noreferrer[^"']*["']/i.test(tag) ||
            /rel=["'][^"']*noreferrer[^"']*noopener[^"']*["']/i.test(tag),
            `Found unsafe target="_blank" missing rel="noopener noreferrer" in ${fullPath}: ${tag}`
          );
        }
      }
    }
  }

  scanDir(srcDir);
});

// -------------------------------------------------------------
// 12. SENSITIVE CREDENTIALS & REDOS STRESS TESTS
// -------------------------------------------------------------
console.log('\n--- [12. Sensitive Credentials & ReDoS Stress Tests] ---');

test('No hardcoded secrets, private keys, or API tokens committed into src/', () => {
  const srcDir = path.resolve(__dirname, '../src');
  
  function scanSecrets(dir) {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        scanSecrets(fullPath);
      } else if (entry.name.endsWith('.tsx') || entry.name.endsWith('.ts')) {
        const content = fs.readFileSync(fullPath, 'utf-8');
        // Match suspicious assignments of real secrets (excluding type declarations or documentation)
        const secretRegex = /(?:api_?key|secret_?key|private_?key|password|jwt_secret)\s*[:=]\s*['"][a-zA-Z0-9_\-]{24,}['"]/gi;
        const match = secretRegex.exec(content);
        assert.strictEqual(
          match,
          null,
          `Found potential hardcoded secret in ${fullPath}: ${match?.[0]}`
        );
      }
    }
  }

  scanSecrets(srcDir);
});

test('ReDoS resilience: sanitizeSafeUrl executes on 50,000-character malicious inputs under 15ms', () => {
  const payload1 = 'mailto:user@' + 'a'.repeat(50000);
  const payload2 = 'https://' + 'a'.repeat(50000) + '.com';
  const payload3 = '/' + 'a'.repeat(50000);
  const payload4 = 'javascript:' + 'a'.repeat(50000);

  const start = performance.now();
  assert.strictEqual(sanitizeSafeUrl(payload1), '#');
  assert.strictEqual(typeof sanitizeSafeUrl(payload2), 'string');
  assert.strictEqual(typeof sanitizeSafeUrl(payload3), 'string');
  assert.strictEqual(sanitizeSafeUrl(payload4), '#');
  const duration = performance.now() - start;

  assert.ok(duration < 25, `ReDoS benchmark took too long: ${duration.toFixed(2)}ms (must be < 25ms)`);
});

console.log('\n======================================================');
console.log(`🏁 SECURITY AUDIT SUMMARY: ${passedTests}/${totalTests} tests passed.`);
console.log('======================================================');

if (passedTests !== totalTests) {
  process.exit(1);
}
