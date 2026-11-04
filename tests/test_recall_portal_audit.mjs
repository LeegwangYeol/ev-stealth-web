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
