'use client';

import React, { useState, useEffect, useMemo, useCallback, memo } from 'react';
import Link from 'next/link';
import { safeJsonParse } from '@/lib/sanitizeUrl';

export type ChecklistItem = {
  id: string;
  category: string;
  task: string;
  warning?: string;
  checked: boolean;
};

export const INITIAL_PDI_ITEMS: ChecklistItem[] = [
  { id: '1', category: '외관 (도장 및 단차)', task: '앞/뒤 범퍼와 펜더 사이의 단차(벌어짐) 확인', warning: '테슬라와 초기형 현기차에서 빈번함', checked: false },
  { id: '2', category: '외관 (도장 및 단차)', task: '충전구 덮개가 꽉 닫히는지, 유격은 없는지 확인', checked: false },
  { id: '3', category: '외관 (도장 및 단차)', task: '하부 배터리팩 케이스 긁힘 및 찍힘 흔적 확인', warning: '인수 후 발견 시 차주 과실로 배터리 교환 불가(전손 위험)', checked: false },
  { id: '4', category: '실내 (시트 및 마감)', task: '시트 가죽 울음, 찢김, 박음질 불량 확인', checked: false },
  { id: '5', category: '실내 (시트 및 마감)', task: '전 좌석 안전벨트 체결 및 버튼 동작 정상 여부', checked: false },
  { id: '6', category: '시스템 (소프트웨어)', task: '메인 디스플레이 터치 먹통 및 재부팅 여부 확인', checked: false },
  { id: '7', category: '시스템 (소프트웨어)', task: '스마트폰 무선 충전 패드 작동 및 발열 체크', checked: false },
  { id: '8', category: '주행 및 하체', task: '핸들(스티어링 휠) 좌우 끝까지 돌릴 때 찌그덕/뚝 소음 확인', warning: '모델Y 컨트롤 암 부싱, 현기 전기차 등 고질병', checked: false },
  { id: '9', category: '주행 및 하체', task: '에어컨 및 히터 최대 가동 시 이음(백색가루/소음) 확인', warning: 'BYD 돌핀 백색가루, 테슬라 히트펌프 불량', checked: false },
];

export const STORAGE_KEY = 'ev_pdi_checklist_state_v1';
export const LEGACY_STORAGE_KEYS = ['ev_pdi_checklist_state', 'ev_pdi_checklist', 'pdi_checklist_state'] as const;

/**
 * Robust parser & schema migration helper:
 * Supports:
 * - Current schema: ChecklistItem[] (array of items with id & checked)
 * - Checked ID array schema: string[] | number[] (e.g. ['1', '3', '8'])
 * - Envelope schema: { items?: unknown[], checkedIds?: unknown[] }
 * - Dictionary schema: { [id: string]: boolean }
 *
 * Guarantees prototype pollution safety, dirty array isolation, and fallback integrity.
 */
export function parseStoredChecklistState(
  raw: unknown,
  defaultItems: ChecklistItem[]
): ChecklistItem[] {
  if (!raw || typeof raw !== 'string') return defaultItems;
  const trimmed = raw.trim();
  if (!trimmed) return defaultItems;

  try {
    const parsed = safeJsonParse<unknown>(trimmed, null);
    if (!parsed) return defaultItems;

    // Case 1: Array of items or primitive IDs
    if (Array.isArray(parsed)) {
      if (parsed.length === 0) return defaultItems;

      // Check if elements are primitive IDs (e.g. ['1', '3'] or [1, 3])
      const isIdArray = parsed.some((p) => typeof p === 'string' || typeof p === 'number');
      if (isIdArray) {
        const checkedIdSet = new Set(
          parsed
            .filter((p) => p !== null && p !== undefined)
            .map((p) => String(p))
        );
        return defaultItems.map((item) => ({
          ...item,
          checked: checkedIdSet.has(String(item.id)),
        }));
      }

      // Array of objects (e.g. [{ id: '1', checked: true }])
      return defaultItems.map((item) => {
        const match = parsed.find(
          (p: unknown): p is Partial<ChecklistItem> =>
            Boolean(p && typeof p === 'object' && 'id' in p && String((p as { id: unknown }).id) === String(item.id))
        );
        return match ? { ...item, checked: Boolean(match.checked) } : item;
      });
    }

    // Case 2: Object envelope or dictionary
    if (typeof parsed === 'object') {
      const obj = parsed as Record<string, unknown>;

      // Envelope with checkedIds array: { checkedIds: ['1', '3'] }
      if (Array.isArray(obj.checkedIds)) {
        const checkedIdSet = new Set(obj.checkedIds.map((id) => String(id)));
        return defaultItems.map((item) => ({
          ...item,
          checked: checkedIdSet.has(String(item.id)),
        }));
      }

      // Envelope with items array: { items: [...] }
      if (Array.isArray(obj.items)) {
        return parseStoredChecklistState(JSON.stringify(obj.items), defaultItems);
      }

      // Dictionary/map of id to boolean: { '1': true, '2': false }
      const hasIdKey = defaultItems.some((item) => item.id in obj || String(item.id) in obj);
      if (hasIdKey) {
        return defaultItems.map((item) => {
          const val = obj[item.id] ?? obj[String(item.id)];
          return val !== undefined ? { ...item, checked: Boolean(val) } : item;
        });
      }
    }
  } catch (e) {
    console.warn('[PDI Checklist] Corrupted storage recovery triggered:', e);
  }

  return defaultItems;
}

/**
 * Detects whether an exception is a QuotaExceededError across major browsers:
 * - WebKit / Safari: QuotaExceededError (code 22)
 * - Gecko / Firefox: NS_ERROR_DOM_QUOTA_REACHED (code 1014)
 * - Chromium / Edge: QuotaExceededError (code 22)
 */
export function isQuotaExceededError(err: unknown): boolean {
  if (!err || typeof err !== 'object') return false;
  const e = err as { name?: string; code?: number; number?: number };
  return (
    e.name === 'QuotaExceededError' ||
    e.name === 'NS_ERROR_DOM_QUOTA_REACHED' ||
    e.code === 22 ||
    e.code === 1014 ||
    e.number === -2147024882
  );
}

/**
 * Checks if localStorage is functional and not blocked by private browsing or security policies.
 */
export function isLocalStorageAvailable(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    const storage = window.localStorage;
    if (!storage) return false;
    const testKey = '__pdi_storage_probe__';
    storage.setItem(testKey, '1');
    storage.removeItem(testKey);
    return true;
  } catch {
    return false;
  }
}

/**
 * Determines current active storage medium for UX transparency.
 */
export function getStorageType(): 'localStorage' | 'sessionStorage' | 'memory' {
  if (typeof window === 'undefined') return 'memory';
  if (isLocalStorageAvailable()) return 'localStorage';
  try {
    if (window.sessionStorage) {
      const testKey = '__pdi_session_probe__';
      window.sessionStorage.setItem(testKey, '1');
      window.sessionStorage.removeItem(testKey);
      return 'sessionStorage';
    }
  } catch {
    // Restricted private mode or security policy
  }
  return 'memory';
}

/**
 * Safely loads state from storage (localStorage with fallback to sessionStorage),
 * automatically migrating legacy keys if found.
 * Highly resilient against SSR, private browsing SecurityError, and corrupted JSON.
 */
export function loadChecklistFromStorage(defaultItems: ChecklistItem[]): ChecklistItem[] {
  if (typeof window === 'undefined') return defaultItems;

  // 1. Attempt primary localStorage
  try {
    if (window.localStorage) {
      const primary = window.localStorage.getItem(STORAGE_KEY);
      if (primary) {
        return parseStoredChecklistState(primary, defaultItems);
      }

      // Check legacy keys and auto-migrate
      for (const legacyKey of LEGACY_STORAGE_KEYS) {
        const legacyVal = window.localStorage.getItem(legacyKey);
        if (legacyVal) {
          const migrated = parseStoredChecklistState(legacyVal, defaultItems);
          try {
            window.localStorage.setItem(STORAGE_KEY, JSON.stringify(migrated));
            window.localStorage.removeItem(legacyKey);
          } catch {
            // Ignore migration write errors in restricted/quota environments
          }
          return migrated;
        }
      }
    }
  } catch (e) {
    console.warn('[PDI Checklist] Failed to load checklist from localStorage:', e);
  }

  // 2. Secondary fallback: sessionStorage (for private browsing or localStorage disabled)
  try {
    if (window.sessionStorage) {
      const sessionVal = window.sessionStorage.getItem(STORAGE_KEY);
      if (sessionVal) {
        return parseStoredChecklistState(sessionVal, defaultItems);
      }
    }
  } catch {
    // Ignore sessionStorage errors
  }

  return defaultItems;
}

/**
 * Safely writes checklist state to storage with QuotaExceeded recovery and private browsing fallbacks.
 * 1. Writes to localStorage.
 * 2. On QuotaExceededError, purges legacy keys and retries once.
 * 3. On persistent QuotaExceededError or SecurityError (private browsing), falls back to sessionStorage.
 */
export function saveChecklistToStorage(items: ChecklistItem[]): boolean {
  if (typeof window === 'undefined') return false;

  const serialized = JSON.stringify(items);

  // 1. Try localStorage
  try {
    if (window.localStorage) {
      try {
        window.localStorage.setItem(STORAGE_KEY, serialized);
        return true;
      } catch (err) {
        if (isQuotaExceededError(err)) {
          // Attempt quota recovery: purge legacy keys
          for (const legacyKey of LEGACY_STORAGE_KEYS) {
            try {
              window.localStorage.removeItem(legacyKey);
            } catch {
              // Ignore
            }
          }
          // Retry write after purge
          try {
            window.localStorage.setItem(STORAGE_KEY, serialized);
            return true;
          } catch {
            // Fall through to sessionStorage
          }
        }
      }
    }
  } catch (e) {
    console.warn('[PDI Checklist] Failed to save checklist to localStorage:', e);
  }

  // 2. Fallback to sessionStorage
  try {
    if (window.sessionStorage) {
      window.sessionStorage.setItem(STORAGE_KEY, serialized);
      return true;
    }
  } catch {
    // In-memory fallback will preserve state for active React session
  }

  return false;
}

/**
 * Clears current checklist state from localStorage and cleans up any legacy keys.
 */
export function clearChecklistFromStorage(): boolean {
  if (typeof window === 'undefined') return false;
  let cleared = false;
  try {
    if (window.localStorage) {
      window.localStorage.removeItem(STORAGE_KEY);
      for (const legacyKey of LEGACY_STORAGE_KEYS) {
        window.localStorage.removeItem(legacyKey);
      }
      cleared = true;
    }
  } catch (e) {
    console.warn('[PDI Checklist] Failed to clear checklist localStorage:', e);
  }

  try {
    if (window.sessionStorage) {
      window.sessionStorage.removeItem(STORAGE_KEY);
      cleared = true;
    }
  } catch {
    // Ignore sessionStorage clear errors
  }

  return cleared;
}

export interface PdiItemRowProps {
  item: ChecklistItem;
  onToggle: (id: string) => void;
}

export const PdiItemRow = memo(function PdiItemRow({ item, onToggle }: PdiItemRowProps) {
  // WCAG AA Keyboard Navigation: Space and Enter both toggle checklist items
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
      e.preventDefault();
      onToggle(item.id);
    }
  };

  return (
    <label
      htmlFor={`pdi-task-${item.id}`}
      className="flex items-start min-h-[48px] p-4 hover:bg-slate-50 cursor-pointer transition-colors rounded-xl focus-within:ring-2 focus-within:ring-blue-500 print:py-2 print:hover:bg-transparent print:break-inside-avoid"
    >
      <input
        id={`pdi-task-${item.id}`}
        type="checkbox"
        checked={item.checked}
        aria-checked={item.checked}
        aria-label={item.task}
        aria-describedby={item.warning ? `pdi-warning-${item.id}` : undefined}
        onChange={() => onToggle(item.id)}
        onKeyDown={handleKeyDown}
        className="mt-1 w-6 h-6 text-blue-600 bg-gray-100 border-slate-400 hover:border-slate-500 rounded focus:ring-blue-500 focus-visible:ring-2 focus-visible:ring-blue-500 print:accent-blue-600 print:border-2 print:border-black print:rounded-none print:w-5 print:h-5 print:bg-white cursor-pointer"
      />
      <span className="ml-4 flex-1">
        <span
          id={`pdi-task-text-${item.id}`}
          className={`block text-lg font-medium ${item.checked ? 'text-slate-600 line-through' : 'text-slate-900'} print:text-base print:text-black`}
        >
          {item.task}
        </span>
        {item.warning && (
          <span
            id={`pdi-warning-${item.id}`}
            role="note"
            className={`block mt-1 text-sm font-medium ${item.checked ? 'text-slate-600 line-through' : 'text-red-800'} print:text-xs print:text-red-800 print:font-semibold`}
          >
            <span aria-hidden="true">⚠️ </span>주의: {item.warning}
          </span>
        )}
      </span>
    </label>
  );
});

export default function PdiChecklistClient() {
  const [items, setItems] = useState<ChecklistItem[]>(INITIAL_PDI_ITEMS);
  const [mounted, setMounted] = useState(false);
  const [storageType, setStorageType] = useState<'localStorage' | 'sessionStorage' | 'memory'>('localStorage');

  // Safe client mounting check: hydrate from localStorage after mount with schema migration
  useEffect(() => {
    setMounted(true);
    setStorageType(getStorageType());
    const loaded = loadChecklistFromStorage(INITIAL_PDI_ITEMS);
    setItems(loaded);
  }, []);

  // Cross-tab synchronization via storage event (handles updates and resets)
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) {
        if (!e.newValue) {
          // Another tab cleared or reset storage -> synchronize to initial defaults
          setItems(INITIAL_PDI_ITEMS);
          return;
        }
        try {
          const updated = parseStoredChecklistState(e.newValue, INITIAL_PDI_ITEMS);
          setItems(updated);
        } catch {
          // Ignore concurrent write issues
        }
      }
    };
    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  // Save changes to localStorage after mounted
  useEffect(() => {
    if (!mounted) return;
    saveChecklistToStorage(items);
  }, [items, mounted]);

  const toggleCheck = useCallback((id: string) => {
    setItems((prev) =>
      prev.map((item) =>
        item.id === id ? { ...item, checked: !item.checked } : item
      )
    );
  }, []);

  const resetChecklist = useCallback(() => {
    if (typeof window !== 'undefined' && window.confirm('체크리스트 상태를 초기화하시겠습니까?')) {
      setItems(INITIAL_PDI_ITEMS);
      clearChecklistFromStorage();
    }
  }, []);

  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  // Collapsed categories state for accordion disclosure (empty = all open by default)
  const [collapsedCategories, setCollapsedCategories] = useState<Record<string, boolean>>({});

  const toggleCategoryCollapse = useCallback((cat: string) => {
    setCollapsedCategories((prev) => ({
      ...prev,
      [cat]: !prev[cat],
    }));
  }, []);

  const isAllChecked = useMemo(() => items.length > 0 && items.every((i) => i.checked), [items]);

  const toggleAllItems = useCallback(() => {
    setItems((prev) => {
      const allChecked = prev.length > 0 && prev.every((i) => i.checked);
      const nextChecked = !allChecked;
      return prev.map((item) => ({ ...item, checked: nextChecked }));
    });
  }, []);

  // Memoized category sets and filtered count calculations
  const categories = useMemo(() => Array.from(new Set(items.map((i) => i.category))), [items]);
  const checkedCount = useMemo(() => items.filter((i) => i.checked).length, [items]);
  const totalItems = items.length;

  // Guard against division by zero (items.length === 0 ? 0 : Math.round((checkedCount / items.length) * 100))
  const progress = useMemo(() => {
    return items.length === 0 ? 0 : Math.round((checkedCount / items.length) * 100);
  }, [checkedCount, items.length]);
  const progressPercentage = progress;

  const allCategories = useMemo(() => ['ALL', ...categories], [categories]);

  const handleTabKeyDown = useCallback((e: React.KeyboardEvent, currentIndex: number) => {
    const count = allCategories.length;
    let nextIndex = -1;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      nextIndex = (currentIndex + 1) % count;
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      nextIndex = (currentIndex - 1 + count) % count;
    } else if (e.key === 'Home') {
      e.preventDefault();
      nextIndex = 0;
    } else if (e.key === 'End') {
      e.preventDefault();
      nextIndex = count - 1;
    }
    if (nextIndex !== -1) {
      const nextCat = allCategories[nextIndex];
      setSelectedCategory(nextCat);
      document.getElementById(`pdi-tab-${nextIndex}`)?.focus();
    }
  }, [allCategories]);

  // Memoized category statistics
  const categoryStats = useMemo(() => {
    const stats: Record<string, { total: number; checked: number }> = {};
    for (const cat of categories) {
      stats[cat] = { total: 0, checked: 0 };
    }
    for (const item of items) {
      if (stats[item.category]) {
        stats[item.category].total += 1;
        if (item.checked) stats[item.category].checked += 1;
      }
    }
    return stats;
  }, [items, categories]);

  // Memoized items grouped by category to eliminate redundant array filters during rendering
  const itemsByCategory = useMemo(() => {
    const map = new Map<string, ChecklistItem[]>();
    for (const cat of categories) {
      map.set(cat, []);
    }
    for (const item of items) {
      const list = map.get(item.category);
      if (list) list.push(item);
    }
    return map;
  }, [items, categories]);

  return (
    <div className="max-w-4xl mx-auto py-6 sm:py-10 space-y-8 print:py-0 print:space-y-4 print:max-w-none">
      <header className="border-b pb-6 print:pb-3 print:border-black print:mb-2">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-4xl font-extrabold text-slate-900 mb-2 print:text-xl print:mb-1 print:text-black">
              전기차 신차 인수(PDI) 체크리스트 ✅
            </h1>
            <p className="text-base sm:text-lg text-gray-600 print:text-xs print:text-gray-700">
              호갱 당하지 않는 방법! 탁송 차량을 인수증에 서명하기 전에 반드시 아래 결함 항목들을 체크하세요.
            </p>
          </div>
          {mounted && (
            <div className="flex flex-wrap items-center gap-2 self-start sm:self-auto print:hidden">
              <button
                onClick={() => window.print()}
                type="button"
                className="px-3.5 py-2 min-h-[44px] text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm transition flex items-center gap-1.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
              >
                <svg className="w-4 h-4" width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 9V2h12v7M6 18H4a2 2 0 01-2-2v-5a2 2 0 012-2h16a2 2 0 012 2v5a2 2 0 01-2 2h-2m-4 0v5H8v-5m6-3h2m-6 0h.01" />
                </svg>
                인쇄 / PDF 저장
              </button>
              <button
                onClick={toggleAllItems}
                type="button"
                aria-pressed={isAllChecked}
                className={`px-3.5 py-2 min-h-[44px] text-xs font-semibold border rounded-lg shadow-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 ${
                  isAllChecked
                    ? 'bg-blue-50 text-blue-700 border-blue-300 hover:bg-blue-100'
                    : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'
                }`}
              >
                {isAllChecked ? '전체 해제' : '전체 선택'}
              </button>
              <button
                onClick={resetChecklist}
                type="button"
                className="px-3.5 py-2 min-h-[44px] text-xs font-semibold text-slate-700 hover:text-red-700 bg-white hover:bg-red-50 border border-slate-300 hover:border-slate-400 rounded-lg shadow-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
              >
                체크리스트 초기화
              </button>
            </div>
          )}
        </div>
        {/* Print-only inspection meta box for physical delivery inspection */}
        <div className="hidden print:grid print:grid-cols-2 print:gap-3 print:my-4 print:p-3 print:border print:border-gray-300 print:rounded-lg print:text-xs print:text-black">
          <div><span className="font-semibold">차량 모델 / 트림:</span> __________________________</div>
          <div><span className="font-semibold">차대번호 (VIN):</span> __________________________</div>
          <div><span className="font-semibold">인수 점검 일시:</span> __________________________</div>
          <div><span className="font-semibold">인수 점검자 (서명):</span> __________________________</div>
        </div>
        <div className="mt-3 flex items-center gap-2 text-xs text-slate-700 print:hidden">
          <span
            aria-hidden="true"
            className={`w-2.5 h-2.5 rounded-full ${
              !mounted
                ? 'bg-slate-400'
                : storageType === 'localStorage'
                ? 'bg-emerald-600'
                : 'bg-amber-500'
            }`}
          />
          <span>
            {!mounted
              ? '초기화 중...'
              : storageType === 'localStorage'
              ? '로컬 저장소 동기화 활성화됨 (새로고침 시 체크 상태 유지)'
              : storageType === 'sessionStorage'
              ? '세션 임시 저장소 활성화됨 (비공개 브라우징 모드 대응)'
              : '메모리 저장소 사용 중 (브라우저 저장소 제한)'}
          </span>
        </div>
        {/* Screen Reader Dynamic Progression Announcement (always in DOM for reliable a11y announcements) */}
        <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
          {mounted
            ? `신차 검수 진행률 ${progress}%, 총 ${totalItems}개 중 ${checkedCount}개 완료`
            : '신차 검수 준비 중'}
        </div>
      </header>

      <div className="sticky top-0 bg-white/90 backdrop-blur-md p-4 rounded-xl border border-gray-200 shadow-sm z-10 space-y-3 print:hidden">
        <div className="flex justify-between items-center">
          <span className="font-semibold text-slate-800">검수 진행률 ({checkedCount}/{items.length})</span>
          <span className={`font-bold ${isAllChecked ? 'text-emerald-700' : 'text-blue-700'}`}>{progress}%</span>
        </div>
        <div
          role="progressbar"
          aria-valuenow={progressPercentage}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="신차 출고 전 점검(PDI) 진행률"
          aria-valuetext={`${progressPercentage}% 검수 완료 (총 ${items.length}개 중 ${checkedCount}개 확인)`}
          className="w-full bg-slate-200 border border-slate-300 rounded-full h-3 overflow-hidden"
        >
          <div
            className={`h-3 rounded-full transition-all duration-500 ease-out ${
              isAllChecked ? 'bg-emerald-600' : 'bg-blue-600'
            }`}
            style={{ width: `${progressPercentage}%` }}
          />
        </div>

        {/* Category Filter Chips with visible focus rings */}
        <div
          role="tablist"
          aria-orientation="horizontal"
          aria-label="체크리스트 카테고리 필터"
          className="flex flex-wrap items-center gap-2 pt-2 border-t border-gray-100"
        >
          {(() => {
            const isSelected = selectedCategory === 'ALL';
            return (
              <button
                id="pdi-tab-0"
                type="button"
                role="tab"
                aria-selected={isSelected}
                aria-expanded={isSelected}
                aria-controls="pdi-checklist-tabpanel"
                tabIndex={isSelected ? 0 : -1}
                onKeyDown={(e) => handleTabKeyDown(e, 0)}
                onClick={() => setSelectedCategory('ALL')}
                className={`px-3 py-1.5 min-h-[44px] inline-flex items-center rounded-lg text-xs font-semibold border transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 ${
                  isSelected
                    ? 'bg-blue-700 text-white border-blue-700'
                    : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'
                }`}
              >
                전체 ({items.length})
              </button>
            );
          })()}
          {categories.map((cat, idx) => {
            const count = categoryStats[cat]?.total || 0;
            const checked = categoryStats[cat]?.checked || 0;
            const isSelected = selectedCategory === cat;
            const tabIndex = idx + 1;
            return (
              <button
                key={cat}
                id={`pdi-tab-${tabIndex}`}
                type="button"
                role="tab"
                aria-selected={isSelected}
                aria-expanded={isSelected}
                aria-controls="pdi-checklist-tabpanel"
                tabIndex={isSelected ? 0 : -1}
                onKeyDown={(e) => handleTabKeyDown(e, tabIndex)}
                onClick={() => setSelectedCategory(cat)}
                className={`px-3 py-1.5 min-h-[44px] inline-flex items-center rounded-lg text-xs font-semibold border transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 ${
                  isSelected
                    ? 'bg-blue-700 text-white border-blue-700'
                    : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'
                }`}
              >
                {cat} ({checked}/{count})
              </button>
            );
          })}
        </div>
      </div>

      <div
        id="pdi-checklist-tabpanel"
        role="tabpanel"
        aria-labelledby={`pdi-tab-${Math.max(0, allCategories.indexOf(selectedCategory))}`}
        tabIndex={0}
        className="space-y-6 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-2xl"
      >
        {categories.map((category, idx) => {
          const isCategoryActive = selectedCategory === 'ALL' || selectedCategory === category;
          const isCollapsed = Boolean(collapsedCategories[category]);
          const contentId = `pdi-category-items-${idx}`;
          const headerId = `pdi-cat-${category}`;
          return (
            <fieldset
              key={category}
              aria-labelledby={`pdi-cat-${category}`}
              className={`${isCategoryActive ? 'block' : 'hidden print:block'} bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden print:border-gray-300 print:shadow-none print:break-inside-avoid`}
            >
              <legend className="sr-only">{category} 신차 출고 전 점검(PDI) 항목</legend>
              <h2
                id={`pdi-cat-${category}`}
                className="bg-slate-50 print:bg-slate-100 border-b border-gray-200 text-xl font-bold text-slate-800 print:text-black print:text-sm print:border-black print:break-after-avoid"
              >
                <button
                  type="button"
                  onClick={() => toggleCategoryCollapse(category)}
                  aria-expanded={!isCollapsed}
                  aria-controls={contentId}
                  aria-label={`${category} 점검 항목 ${!isCollapsed ? '접기' : '펼치기'}`}
                  className="w-full p-4 flex items-center justify-between text-left text-slate-800 hover:text-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-t-2xl transition print:p-2 print:hover:text-black"
                >
                  <span>{category}</span>
                  <span className="flex items-center gap-2 text-xs font-normal text-slate-600 print:hidden">
                    <span>({categoryStats[category]?.checked || 0}/{categoryStats[category]?.total || 0} 완료)</span>
                    <svg
                      className={`w-5 h-5 transform transition-transform duration-200 ${!isCollapsed ? 'rotate-180' : ''}`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                    </svg>
                  </span>
                </button>
              </h2>
              <div
                id={contentId}
                role="region"
                aria-labelledby={headerId}
                className={`divide-y divide-gray-100 ${isCollapsed ? 'hidden print:block' : 'block'}`}
              >
                {(itemsByCategory.get(category) || []).map((item) => (
                  <PdiItemRow key={item.id} item={item} onToggle={toggleCheck} />
                ))}
              </div>
            </fieldset>
          );
        })}
      </div>

      {progress === 100 && (
        <section
          role="status"
          aria-live="polite"
          aria-labelledby="pdi-completion-title"
          className="bg-emerald-50 border border-emerald-300 text-emerald-950 p-6 rounded-2xl text-center shadow-sm animate-pulse motion-reduce:animate-none print:bg-white print:border-black print:text-black print:animate-none"
        >
          <h2 id="pdi-completion-title" className="text-2xl font-bold mb-2 text-emerald-900">🎉 검수 완료!</h2>
          <p className="text-emerald-800 font-medium">모든 항목을 확인하셨습니다. 이상이 없다면 안심하고 인수증에 서명하세요.</p>
        </section>
      )}

      {/* 💡 신차 인수 후 추천 서비스 (Recommended EV Services) */}
      <section aria-labelledby="heading-recommended-services" className="pt-8 border-t border-gray-200 print:hidden">
        <div className="mb-6">
          <h2 id="heading-recommended-services" className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <span aria-hidden="true">💡</span> 신차 인수 후 추천 서비스
          </h2>
          <p className="text-sm text-slate-600 mt-1">
            신차 인수를 성공적으로 마치셨나요? 보조금 수령 확인부터 향후 차량 유지관리까지 필수 서비스를 이용해보세요.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Link
            href="/subsidy-tracker"
            prefetch={true}
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-amber-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
          >
            <div className="flex items-center gap-2 text-amber-800 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">⚡</span>
              <span>지자체 보조금 실시간 소진율 추적기</span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              환경부 및 17개 지자체별 실시간 전기차 보조금 소진율과 마감 임박 경보를 확인합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-amber-800 font-semibold mt-3 group-hover:underline">
              보조금 소진율 확인하기 &rarr;
            </span>
          </Link>

          <Link
            href="/depreciation-calculator"
            prefetch={true}
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-emerald-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
          >
            <div className="flex items-center gap-2 text-emerald-700 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">📉</span>
              <span>전기차 감가율 및 배터리 수명 시뮬레이터</span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              보조금 수령 후 5년간의 예상 잔존가치, 배터리 잔존성능(SoH), 연차별 총소유비용(TCO)을 정밀 계산합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-emerald-700 font-semibold mt-3 group-hover:underline">
              감가율 계산하기 &rarr;
            </span>
          </Link>

          <Link
            href="/reliability-analytics"
            prefetch={false}
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-blue-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >
            <div className="flex items-center gap-2 text-blue-700 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">📊</span>
              <span>실차주 결함 통계 및 고질병 랭킹</span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              실제 차주들의 결함 신고 데이터와 고질병 위험도 랭킹, 부품별 수리비 통계를 분석합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-blue-700 font-semibold mt-3 group-hover:underline">
              결함 통계 조회하기 &rarr;
            </span>
          </Link>

          <Link
            href="/recall-portal"
            prefetch={false}
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-rose-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-500"
          >
            <div className="flex items-center gap-2 text-rose-700 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">🚨</span>
              <span>공식 리콜 및 배터리 제조사 조회</span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              차대번호(VIN) 17자리 또는 모델명으로 국토교통부 공식 리콜 조치 여부 및 탑재 배터리 제조사를 즉시 조회합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-rose-700 font-semibold mt-3 group-hover:underline">
              리콜 및 배터리 확인하기 &rarr;
            </span>
          </Link>
        </div>
      </section>
    </div>
  );
}
