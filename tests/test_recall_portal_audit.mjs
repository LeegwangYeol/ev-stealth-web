import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

console.log('🧪 Starting EV Recall Portal Comprehensive Audit Test...');

const recallPortalClientPath = join(__dirname, '../src/app/recall-portal/RecallPortalClient.tsx');
const recallPortalClientCode = readFileSync(recallPortalClientPath, 'utf8');

const errorPath = join(__dirname, '../src/app/recall-portal/error.tsx');
const errorCode = readFileSync(errorPath, 'utf8');

const exportWrapperPath = join(__dirname, '../src/components/RecallPortalClient.tsx');
const exportWrapperCode = readFileSync(exportWrapperPath, 'utf8');

// ---------------------------------------------------------------------------
// 1. WCAG AA Accessibility Tests
// ---------------------------------------------------------------------------
console.log('Testing WCAG AA Accessibility requirements...');

// 1.1 Filter group button aria-labels
assert.ok(
  recallPortalClientCode.includes('aria-label={s.key === \'ALL\' ? \'배터리 셀 제조사 전체 보기\' : `배터리 셀 제조사 ${s.label} 필터`}'),
  'Supplier filter buttons must have descriptive accessible aria-labels'
);
assert.ok(
  recallPortalClientCode.includes('aria-label={f.key === \'ALL\' ? \'화재 리스크 상태 전체 보기\' : `화재 리스크 ${f.label} 필터`}'),
  'Fire status filter buttons must have descriptive accessible aria-labels'
);
assert.ok(
  recallPortalClientCode.includes('aria-label={rf.key === \'ALL\' ? \'위험 등급 전체 보기\' : `위험 등급 ${rf.label} 필터`}'),
  'Risk filter buttons must have descriptive accessible aria-labels'
);
assert.ok(
  recallPortalClientCode.includes('aria-label={rm.key === \'ALL\' ? \'조치 유형 전체 보기\' : `조치 유형 ${rm.label} 필터`}'),
  'Remedy filter buttons must have descriptive accessible aria-labels'
);

// 1.2 Form labels and button labels
assert.ok(
  recallPortalClientCode.includes('aria-label="차대번호 입력 초기화"'),
  'Reset button in VIN mode must have an accessible aria-label'
);
assert.ok(
  recallPortalClientCode.includes('등록된 제조사 없음'),
  'Brand select dropdown must display fallback option when no brands exist'
);
assert.ok(
  recallPortalClientCode.includes('등록된 모델 없음'),
  'Model select dropdown must display fallback option when no models exist'
);

// 1.3 Accordion aria-controls valid DOM reference (hidden={!isExpanded})
assert.ok(
  recallPortalClientCode.includes('hidden={!isExpanded}'),
  'Accordion details panel must remain in DOM with hidden attribute to preserve valid aria-controls'
);

// 1.4 Contrast ratios in error.tsx
assert.ok(
  !errorCode.includes('text-slate-500'),
  'error.tsx must not use borderline text-slate-500 on white background'
);
assert.ok(
  errorCode.includes('text-slate-600'),
  'error.tsx must use text-slate-600 for AA-compliant contrast on white background'
);

// 1.5 Accordion expansion keyboard accessibility (Escape to close and focus return)
assert.ok(
  recallPortalClientCode.includes("e.key === 'Escape' && isExpanded"),
  'RecallCard must handle Escape key press to close expansion details'
);
assert.ok(
  recallPortalClientCode.includes('toggleButtonRef.current?.focus()'),
  'RecallCard must return focus to the expand/collapse button on Escape'
);
assert.ok(
  recallPortalClientCode.includes('role="region"'),
  'Expanded details panel must use role="region" for landmark identification'
);
assert.ok(
  recallPortalClientCode.includes('aria-labelledby={`${panelIdPrefix}title-${campaign.id}`}'),
  'Expanded details panel must be labelled by campaign defect title'
);

// 1.6 Search inputs & landmark roles
assert.ok(
  recallPortalClientCode.includes('role="search" aria-label="배터리 제조사 및 모델 검색"'),
  'Battery search container must define a search landmark'
);
assert.ok(
  recallPortalClientCode.includes('role="search" aria-label="전기차 리콜 캠페인 검색"'),
  'Recall catalog search container must define a search landmark'
);
assert.ok(
  recallPortalClientCode.includes('type="search"'),
  'Search inputs must use type="search"'
);

// 1.7 Live updates & status announcements
assert.ok(
  recallPortalClientCode.includes('role="status" aria-live="polite" className="mt-2 text-xs text-emerald-400'),
  'Valid VIN feedback must announce live status via role="status" and aria-live="polite"'
);
assert.ok(
  recallPortalClientCode.includes('tabIndex={-1}'),
  'search-result-section must allow programmatic focus via tabIndex={-1}'
);

// 1.8 High-contrast badges & status chips (WCAG AA/AAA compliant)
assert.ok(
  recallPortalClientCode.includes('text-rose-200 border-red-700'),
  'Critical fire badges must use high-contrast text-rose-200 on dark background'
);
assert.ok(
  recallPortalClientCode.includes('text-amber-200 border-amber-700'),
  'Resolved badges must use high-contrast text-amber-200 on dark background'
);
assert.ok(
  recallPortalClientCode.includes('text-emerald-200 border-emerald-700'),
  'Safe verification badges must use high-contrast text-emerald-200 on dark background'
);

// 1.9 Tablist Keyboard Navigation & WAI-ARIA 1.2 compliance
assert.ok(
  recallPortalClientCode.includes("handleModeKeyDown = (e: React.KeyboardEvent, currentMode: 'VIN' | 'MODEL')"),
  'RecallPortalClient must implement keyboard navigation handler for mode switcher tabs'
);
assert.ok(
  recallPortalClientCode.includes("e.key === 'ArrowRight' || e.key === 'ArrowDown'") &&
  recallPortalClientCode.includes("e.key === 'ArrowLeft' || e.key === 'ArrowUp'") &&
  recallPortalClientCode.includes("e.key === 'Home'") &&
  recallPortalClientCode.includes("e.key === 'End'"),
  'handleModeKeyDown must support ArrowLeft/Right/Up/Down and Home/End keys'
);
assert.ok(
  recallPortalClientCode.includes("tabIndex={activeCheckerMode === 'VIN' ? 0 : -1}") &&
  recallPortalClientCode.includes("tabIndex={activeCheckerMode === 'MODEL' ? 0 : -1}"),
  'Mode tabs must toggle tabIndex between 0 and -1 based on active selection (WAI-ARIA roving tabindex)'
);
assert.ok(
  recallPortalClientCode.includes('id="vin-checker-panel" role="tabpanel" aria-labelledby="vin-checker-tab" tabIndex={0}') &&
  recallPortalClientCode.includes('id="model-checker-panel" role="tabpanel" aria-labelledby="model-checker-tab" tabIndex={0}'),
  'Tabpanels must declare role="tabpanel", tabIndex={0}, and link back to tabs via aria-labelledby'
);

// 1.10 Touch Target Minimum Size (WCAG 2.5.5 / 2.5.8 Target Size)
assert.ok(
  recallPortalClientCode.includes('min-h-[44px]'),
  'RecallPortalClient must enforce min-h-[44px] touch target sizes across interactive elements'
);
const minH44Count = (recallPortalClientCode.match(/min-h-\[44px\]/g) || []).length;
assert.ok(
  minH44Count >= 20,
  `Expected at least 20 elements declaring min-h-[44px], found ${minH44Count}`
);

// 1.11 Filter Chips ARIA State & Grouping (WCAG 4.1.2 & 1.3.1)
assert.ok(
  recallPortalClientCode.includes('aria-pressed={selectedSupplierFilter === s.key}'),
  'Supplier filter buttons must declare aria-pressed state'
);
assert.ok(
  recallPortalClientCode.includes('aria-pressed={selectedFireStatusFilter === f.key}'),
  'Fire status filter buttons must declare aria-pressed state'
);
assert.ok(
  recallPortalClientCode.includes('aria-pressed={selectedRiskFilter === rf.key}'),
  'Risk filter buttons must declare aria-pressed state'
);
assert.ok(
  recallPortalClientCode.includes('aria-pressed={selectedRemedyFilter === rm.key}'),
  'Remedy filter buttons must declare aria-pressed state'
);
assert.ok(
  recallPortalClientCode.includes('role="group" aria-label="배터리 셀 제조사 필터"') &&
  recallPortalClientCode.includes('role="group" aria-label="화재 리스크 상태별 필터"') &&
  recallPortalClientCode.includes('role="group" aria-label="리콜 위험 등급별 필터"') &&
  recallPortalClientCode.includes('role="group" aria-label="시정 조치 유형별 필터"'),
  'Filter chip containers must declare role="group" and descriptive accessible aria-labels'
);

// 1.12 Form Fieldset & Semantic Grouping in Mode B (WCAG 1.3.1)
assert.ok(
  recallPortalClientCode.includes('<fieldset className="grid grid-cols-1 sm:grid-cols-3 gap-4 border-0 p-0 m-0">') &&
  recallPortalClientCode.includes('<legend className="sr-only">제조사, 모델, 생산 연식 선택 필터</legend>'),
  'Mode B form must enclose brand, model, and year dropdowns in a semantic <fieldset> with <legend>'
);

// 1.13 Keyboard Dismiss Shortcuts (Escape Key)
assert.ok(
  recallPortalClientCode.includes("e.key === 'Escape' && vinInput"),
  'VIN input must support Escape key to clear input and reset search'
);
assert.ok(
  recallPortalClientCode.includes("e.key === 'Escape' && batterySearch"),
  'Battery search input must support Escape key to clear query'
);
assert.ok(
  recallPortalClientCode.includes("e.key === 'Escape' && recallSearch"),
  'Recall search input must support Escape key to clear query'
);

// 1.14 Dual Error and Format Hint Linkage on VIN Input (WCAG 1.3.1 & 3.3.1)
assert.ok(
  recallPortalClientCode.includes('aria-describedby={vinError ? "vin-error-feedback vin-format-hint" : "vin-format-hint"}'),
  'VIN input must dynamically link aria-describedby to both format hint and error feedback'
);
assert.ok(
  recallPortalClientCode.includes('id="vin-format-hint" className="sr-only"'),
  'vin-format-hint must provide accessible instructions for screen readers'
);
assert.ok(
  recallPortalClientCode.includes('id="vin-error-feedback" role="alert" aria-live="assertive"'),
  'vin-error-feedback must announce validation failures with role="alert" and aria-live="assertive"'
);

// 1.15 SVG Icons Accessibility
const svgTags = recallPortalClientCode.match(/<svg\b[^>]*>/g) || [];
assert.ok(svgTags.length >= 8, `Expected at least 8 SVGs in RecallPortalClient, found ${svgTags.length}`);
for (const tag of svgTags) {
  assert.ok(
    tag.includes('aria-hidden="true"') && tag.includes('focusable="false"'),
    `SVG tag must declare aria-hidden="true" and focusable="false": ${tag}`
  );
}

// 1.16 Mathematical Color Contrast Verification (WCAG 1.4.3 Level AA & AAA)
function calculateLuminance(r, g, b) {
  const [rs, gs, bs] = [r, g, b].map((c) => {
    c = c / 255;
    return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
}

function calculateContrast(hex1, hex2) {
  const parseHex = (h) => {
    const clean = h.replace('#', '');
    return [
      parseInt(clean.substring(0, 2), 16),
      parseInt(clean.substring(2, 4), 16),
      parseInt(clean.substring(4, 6), 16),
    ];
  };
  const [r1, g1, b1] = parseHex(hex1);
  const [r2, g2, b2] = parseHex(hex2);
  const l1 = calculateLuminance(r1, g1, b1);
  const l2 = calculateLuminance(r2, g2, b2);
  const brighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (brighter + 0.05) / (darker + 0.05);
}

const contrastChecks = [
  { name: 'rose-200 on red-950', fg: '#fecdd3', bg: '#450a0a', minRatio: 4.5 },
  { name: 'amber-200 on amber-950', fg: '#fde68a', bg: '#451a03', minRatio: 4.5 },
  { name: 'emerald-200 on emerald-950', fg: '#a7f3d0', bg: '#022c22', minRatio: 4.5 },
  { name: 'blue-200 on blue-950', fg: '#bfdbfe', bg: '#172554', minRatio: 4.5 },
  { name: 'placeholder-slate-400 on slate-900', fg: '#94a3b8', bg: '#0f172a', minRatio: 4.5 },
  { name: 'text-slate-300 on slate-950', fg: '#cbd5e1', bg: '#020617', minRatio: 4.5 },
  { name: 'text-blue-400 on slate-950', fg: '#60a5fa', bg: '#020617', minRatio: 4.5 },
  { name: 'text-emerald-400 on slate-950', fg: '#34d399', bg: '#020617', minRatio: 4.5 },
  { name: 'text-red-400 on slate-950', fg: '#f87171', bg: '#020617', minRatio: 4.5 },
];

for (const { name, fg, bg, minRatio } of contrastChecks) {
  const ratio = calculateContrast(fg, bg);
  assert.ok(
    ratio >= minRatio,
    `Color contrast for ${name} (${ratio.toFixed(2)}:1) failed to meet required ${minRatio}:1`
  );
}

console.log('✅ WCAG AA Accessibility tests passed!');

// ---------------------------------------------------------------------------
// 2. Logic Bugs & Edge Cases Tests
// ---------------------------------------------------------------------------
console.log('Testing Logic Bugs, Special Character Resiliency, and Null Safety...');

// 2.1 Resilient search normalization helper
assert.ok(
  recallPortalClientCode.includes('function normalizeSearchText(text?: string | null): string'),
  'RecallPortalClient must define normalizeSearchText helper'
);

// 2.2 Mode B validation failure message must NOT mention VIN
assert.ok(
  recallPortalClientCode.includes("checkResult.mode === 'MODEL' ? '차종 선택 검증 안내' : '차대번호(VIN) 유효성 검증 실패'"),
  'Mode B validation alert badge must be distinct from VIN error'
);
assert.ok(
  recallPortalClientCode.includes("checkResult.mode === 'MODEL' ? '차종 선택 요령:' : '올바른 차대번호 확인 및 입력 요령:'"),
  'Mode B validation alert must provide car model selection guidance instead of VIN tips'
);

// 2.3 Empty state rendering
assert.ok(
  recallPortalClientCode.includes('데이터베이스에 등록된 배터리 제원 정보가 없습니다'),
  'Battery directory must distinguish empty DB from search-filtered empty state'
);
assert.ok(
  recallPortalClientCode.includes('데이터베이스에 등록된 리콜 캠페인 정보가 없습니다'),
  'Recalls directory must distinguish empty DB from search-filtered empty state'
);

// 2.4 Null vehicle names & defensive fallbacks
assert.ok(
  recallPortalClientCode.includes("const targetModel = campaign.target_model || '해당 차종'"),
  'RecallCard must handle null or empty target_model safely'
);
assert.ok(
  recallPortalClientCode.includes("const modelName = p.model_name || '차종 미상'"),
  'BatterySafetyCard must handle null or empty model_name safely'
);

console.log('✅ Logic Bugs & Edge Cases tests passed!');

// ---------------------------------------------------------------------------
// 3. Performance & Memoization Tests
// ---------------------------------------------------------------------------
console.log('Testing Performance, Virtualization & Memoization...');

// 3.1 Progressive virtualization constants and state
assert.ok(
  recallPortalClientCode.includes('PAGE_SIZE_BATTERIES = 12'),
  'RecallPortalClient must define PAGE_SIZE_BATTERIES for chunked DOM rendering'
);
assert.ok(
  recallPortalClientCode.includes('PAGE_SIZE_RECALLS = 10'),
  'RecallPortalClient must define PAGE_SIZE_RECALLS for chunked DOM rendering'
);
assert.ok(
  recallPortalClientCode.includes('displayedBatteryProfiles = useMemo('),
  'Battery profiles must be windowed via displayedBatteryProfiles slice'
);
assert.ok(
  recallPortalClientCode.includes('displayedRecalls = useMemo('),
  'Recalls must be windowed via displayedRecalls slice'
);

// 3.2 Component deduplication
assert.ok(
  recallPortalClientCode.includes('panelIdPrefix="campaign-search-detail-"'),
  'checkResult must reuse the memoized RecallCard with distinct panelIdPrefix'
);
assert.ok(
  recallPortalClientCode.includes('panelIdPrefix="campaign-list-detail-"'),
  'Recalls directory must reuse the memoized RecallCard with distinct panelIdPrefix'
);

// 3.3 Component export wrapper symmetry
assert.ok(
  exportWrapperCode.includes('BatterySafetyCard'),
  'src/components/RecallPortalClient.tsx must re-export BatterySafetyCard'
);

console.log('✅ Performance & Memoization tests passed!');
console.log('🎉 All Recall Portal audit verifications passed successfully!');
