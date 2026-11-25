import assert from 'node:assert/strict';
import { test } from 'node:test';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, '..');

const REL_CLIENT_PATH = path.join(PROJECT_ROOT, 'src/app/reliability-analytics/ReliabilityDashboardClient.tsx');
const ADMIN_CLIENT_PATH = path.join(PROJECT_ROOT, 'src/app/secret-admin-reports/AdminDashboardClient.tsx');

const relSource = fs.readFileSync(REL_CLIENT_PATH, 'utf-8');
const adminSource = fs.readFileSync(ADMIN_CLIENT_PATH, 'utf-8');

test('ReliabilityDashboardClient: resolveBrandId prevents gm->kgm false match & uses resolveBrandReliability', async () => {
  assert.ok(relSource.includes('resolveBrandReliability'), 'Must reuse resolveBrandReliability');
  assert.ok(relSource.includes('/(?:^|[^a-z])gm(?:[^a-z]|$)/.test(clean)'), 'Fallback gm check must use word boundaries');

  // Verify resolveBrandReliability behavior directly with KGM before GM
  const { resolveBrandReliability } = await import('../src/lib/reliabilityCalculations.ts');
  const mockDb = {
    metadata: { version: '1.0' },
    repair_cost_matrix: [],
    brands: [
      {
        id: 'kg-mobility',
        name_ko: 'KG모빌리티',
        name_en: 'KGM',
        country: 'KR',
        overall_dsi: 42,
        total_reports: 15,
        critical_issue_rate: 4,
        category_distribution: {},
        models: [],
      },
      {
        id: 'gm-chevrolet',
        name_ko: 'GM 쉐보레',
        name_en: 'GM Chevrolet',
        country: 'US',
        overall_dsi: 55,
        total_reports: 25,
        critical_issue_rate: 8,
        category_distribution: {},
        models: [],
      },
    ],
  };

  assert.equal(resolveBrandReliability('gm', mockDb)?.id, 'gm-chevrolet');
  assert.equal(resolveBrandReliability('kgm', mockDb)?.id, 'kg-mobility');
});

test('ReliabilityDashboardClient: radar focus ring, touch targets, and PII/XSS text sanitization', () => {
  assert.ok(relSource.includes('focusedRadarCategory'), 'Must track focusedRadarCategory independently of pinnedRadarCategory');
  assert.ok(relSource.includes('(isActive || isFocused)'), 'Must render SVG focus rings when focused even if another category is pinned');
  assert.ok(relSource.includes('min-w-[44px] min-h-[44px] inline-flex items-center justify-center bg-slate-800'), 'Heatmap detail close button must enforce >= 44x44px touch target');
  assert.ok(relSource.includes('sanitizeAndMaskText(evalData.raw_quote)'), 'HeatmapRow must sanitize and mask raw_quote');
  assert.ok(relSource.includes('sanitizeAndMaskText(evalData.primary_defect)'), 'HeatmapRow must sanitize and mask primary_defect');
  assert.ok(relSource.includes('sanitizeAndMaskText(item.critical_warning)'), 'RepairCostMatrixRow must sanitize and mask critical_warning');
  assert.ok(relSource.includes('sanitizeAndMaskText(rawFirstQuote)'), 'ModelCardItem must sanitize and mask raw_quote');
});

test('AdminDashboardClient: comprehensive PII masking on text/IDs, styled caption, and long-title overflow guard', () => {
  assert.ok(adminSource.includes('function maskReportPii('), 'Must define maskReportPii helper');
  assert.ok(adminSource.includes('maskReportPii(r.title)'), 'Must mask PII and HTML in report title');
  assert.ok(adminSource.includes('maskReportPii(r.summary)'), 'Must mask PII and HTML in report summary');
  assert.ok(adminSource.includes('maskReportPii(r.verbatim_quote)'), 'Must mask PII and HTML in verbatim_quote');
  assert.ok(adminSource.includes('maskReportPii(r.vehicle_model)'), 'Must mask PII and HTML in vehicle_model');
  assert.ok(adminSource.includes('maskReportPii(r.vehicle_brand)'), 'Must mask PII and HTML in vehicle_brand');
  assert.ok(adminSource.includes('maskReportPii(rawSafeId)'), 'Must mask PII and HTML in string report IDs');
  assert.ok(adminSource.includes('maskReportPii(rawStats.top_model)'), 'Must mask PII and HTML in top_model KPI');
  assert.ok(adminSource.includes('maskReportPii(rawStats.top_platform)'), 'Must mask PII and HTML in top_platform KPI');
  assert.ok(adminSource.includes('<caption>'), 'Table caption must preserve literal <caption> tag');
  assert.ok(adminSource.includes('max-w-full break-words'), 'Card title anchor must prevent horizontal overflow on long tokens');
});
