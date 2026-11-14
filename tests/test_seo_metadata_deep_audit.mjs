import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, '..');
const APP_DIR = path.resolve(PROJECT_ROOT, 'ev-stealth-web', 'src', 'app');

console.log('Starting Deep SEO, OpenGraph, JSON-LD, Robots, and Sitemap Audit...');

// 1. Audit public and private routes
const routesToAudit = [
  { folder: '', path: '/', isPrivate: false },
  { folder: 'subsidy-tracker', path: '/subsidy-tracker', isPrivate: false },
  { folder: 'depreciation-calculator', path: '/depreciation-calculator', isPrivate: false },
  { folder: 'recall-portal', path: '/recall-portal', isPrivate: false },
  { folder: 'reliability-analytics', path: '/reliability-analytics', isPrivate: false },
  { folder: 'pdi-checklist', path: '/pdi-checklist', isPrivate: false },
  { folder: 'secret-admin-reports', path: '/secret-admin-reports', isPrivate: true },
  { folder: 'byd', path: '/byd', isPrivate: false },
  { folder: 'tesla', path: '/tesla', isPrivate: false },
  { folder: 'hyundai-kia', path: '/hyundai-kia', isPrivate: false },
  { folder: 'global-brands', path: '/global-brands', isPrivate: false },
  { folder: '2026-latest', path: '/2026-latest', isPrivate: false },
];

for (const route of routesToAudit) {
  const filePath = route.folder
    ? path.join(APP_DIR, route.folder, 'page.tsx')
    : path.join(APP_DIR, 'page.tsx');

  assert.ok(fs.existsSync(filePath), `File does not exist: ${filePath}`);
  const content = fs.readFileSync(filePath, 'utf-8');

  // Verify export const metadata
  assert.match(content, /export const metadata:\s*Metadata\s*=\s*{/, `Metadata missing in ${route.path}`);

  // Title
  assert.match(content, /title:\s*['"]/, `Title missing in ${route.path}`);

  // Description
  assert.match(content, /description:\s*['"]/, `Description missing in ${route.path}`);

  // Keywords
  assert.match(content, /keywords:\s*\[/, `Keywords array missing in ${route.path}`);

  // Canonical alternates
  assert.match(content, /canonical:\s*['"][^'"]+['"]/, `Canonical URL missing in ${route.path}`);
  assert.ok(content.includes(`canonical: '${route.path}'`) || content.includes(`canonical: "${route.path}"`),
    `Canonical URL does not match route path '${route.path}' in ${filePath}`);

  // Hreflang alternates
  assert.match(content, /languages:\s*{/, `Hreflang languages missing in ${route.path}`);
  assert.match(content, /['"]ko-KR['"]:\s*['"][^'"]+['"]/, `ko-KR hreflang missing in ${route.path}`);
  assert.match(content, /['"]x-default['"]:\s*['"][^'"]+['"]/, `x-default hreflang missing in ${route.path}`);

  // OpenGraph
  assert.match(content, /openGraph:\s*{/, `OpenGraph missing in ${route.path}`);
  assert.ok(content.includes(`url: '${route.path}'`) || content.includes(`url: "${route.path}"`),
    `OpenGraph url does not match route path '${route.path}' in ${filePath}`);
  assert.match(content, /siteName:\s*['"]Global EV Hub['"]/, `OpenGraph siteName missing or invalid in ${route.path}`);
  assert.match(content, /images:\s*\[/, `OpenGraph images missing in ${route.path}`);

  // Twitter Card
  assert.match(content, /twitter:\s*{/, `Twitter metadata missing in ${route.path}`);
  assert.match(content, /card:\s*['"]summary_large_image['"]/, `Twitter card summary_large_image missing in ${route.path}`);

  // Robots indexing guard for private routes
  if (route.isPrivate) {
    assert.match(content, /index:\s*false/, `Private route ${route.path} must specify index: false`);
    assert.match(content, /follow:\s*false/, `Private route ${route.path} must specify follow: false`);
  } else {
    // Public routes must render JsonLd
    assert.match(content, /<JsonLd\s+data={/, `Public route ${route.path} must render <JsonLd data={...} />`);
  }

  console.log(`✔ Verified route: ${route.path.padEnd(25)} (Metadata, OG, Canonical, Hreflang, Twitter, Indexing)`);
}

// 2. Validate serializeJsonLd utility
const sanitizeUrlPath = path.resolve(PROJECT_ROOT, 'ev-stealth-web', 'src', 'lib', 'sanitizeUrl.ts');
assert.ok(fs.existsSync(sanitizeUrlPath), 'sanitizeUrl.ts exists');
const sanitizeContent = fs.readFileSync(sanitizeUrlPath, 'utf-8');
assert.match(sanitizeContent, /export function serializeJsonLd/, 'serializeJsonLd is exported');
assert.match(sanitizeContent, /replace\(\/<\/\s*g,\s*['"]\\\\u003c['"]\)/, 'serializeJsonLd neutralizes <');
assert.match(sanitizeContent, /replace\(\/>\/\s*g,\s*['"]\\\\u003e['"]\)/, 'serializeJsonLd neutralizes >');
assert.match(sanitizeContent, /replace\(\/&\/\s*g,\s*['"]\\\\u0026['"]\)/, 'serializeJsonLd neutralizes &');

// 3. Test robots.ts contract
const robotsPath = path.resolve(APP_DIR, 'robots.ts');
assert.ok(fs.existsSync(robotsPath), 'robots.ts exists');
const robotsContent = fs.readFileSync(robotsPath, 'utf-8');
assert.match(robotsContent, /export default function robots/, 'robots export exists');
assert.match(robotsContent, /userAgent:\s*['"]\*['"]/, 'robots covers all user agents');
assert.match(robotsContent, /'\/secret-admin-reports'/, 'robots blocks secret-admin-reports');
assert.match(robotsContent, /sitemap:\s*`\${baseUrl}\/sitemap\.xml`/, 'robots specifies canonical sitemap');

// 4. Test sitemap.ts contract
const sitemapPath = path.resolve(APP_DIR, 'sitemap.ts');
assert.ok(fs.existsSync(sitemapPath), 'sitemap.ts exists');
const sitemapContent = fs.readFileSync(sitemapPath, 'utf-8');
assert.match(sitemapContent, /export default function sitemap/, 'sitemap export exists');

// Verify all public routes are present in sitemap
for (const r of routesToAudit.filter(r => !r.isPrivate)) {
  const expectedFragment = r.path === '/' ? '`${baseUrl}`' : `\`\${baseUrl}${r.path}\``;
  assert.ok(sitemapContent.includes(expectedFragment), `Sitemap missing route: ${expectedFragment}`);
}
// Verify private route is strictly excluded from sitemap
assert.ok(!sitemapContent.includes('secret-admin-reports'), 'Private route secret-admin-reports must NOT be in sitemap');

console.log('\n✔ ALL DEEP SEO AUDIT CHECKS PASSED WITH 100% SUCCESS!');
