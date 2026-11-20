"use client";

import React, { useState, useMemo, useDeferredValue, useCallback, useRef, useEffect, memo } from 'react';
import {
  sanitizeReportUrl,
  getSafeSentimentScore,
  getFallbackReportData,
  resolveCategory,
  deduplicateReports,
  maskSensitiveData,
  maskAuthor,
  stripHtmlTags,
  type DailyReportData,
  type DefectReportItem,
} from '@/lib/reportCalculations';
import { isExternalUrl, safeJsonParse } from '@/lib/sanitizeUrl';
import ClientTimestamp from '@/components/ClientTimestamp';

export function formatSentimentPercent(score: unknown): number {
  const safe = getSafeSentimentScore(score, 0);
  return Math.min(100, Math.max(0, Math.round(safe * 100)));
}

/**
 * Normalizes vehicle brand name to standard canonical Korean representation.
 */
export function normalizeBrand(rawBrand?: string): string {
  if (!rawBrand || typeof rawBrand !== 'string') return '기타';
  const clean = rawBrand.trim();
  const lower = clean.toLowerCase();
  if (lower === 'hyundai' || lower === '현대' || lower.includes('현대')) return '현대';
  if (lower === 'kia' || lower === '기아' || lower.includes('기아')) return '기아';
  if (lower === 'genesis' || lower === '제네시스' || lower.includes('제네시스')) return '제네시스';
  if (lower === 'tesla' || lower === '테슬라' || lower.includes('테슬라')) return '테슬라';
  if (lower === 'mercedes' || lower === 'mercedes-benz' || lower === '벤츠' || lower.includes('벤츠')) return '벤츠';
  if (lower === 'bmw') return 'BMW';
  if (lower === 'byd') return 'BYD';
  if (lower === 'polestar' || lower === '폴스타') return '폴스타';
  if (lower === 'chevrolet' || lower === '쉐보레') return '쉐보레';
  if (lower === 'renault' || lower === '르노') return '르노';
  if (lower === 'kgm' || lower === '쌍용' || lower === 'kg mobility') return 'KGM';
  if (lower === 'other' || lower === '기타' || lower === 'etc') return '기타';
  return clean;
}

function isValidUtcCalendarDate(year: number, month: number, day: number): boolean {
  if (!Number.isInteger(year) || !Number.isInteger(month) || !Number.isInteger(day)) return false;
  if (month < 1 || month > 12 || day < 1 || day > 31) return false;
  const d = new Date(Date.UTC(year, month - 1, day));
  return (
    d.getUTCFullYear() === year &&
    d.getUTCMonth() === month - 1 &&
    d.getUTCDate() === day
  );
}

/**
 * Cross-browser safe date parser compatible with Safari/WebKit, ISO timestamps, and dot-separated Korean dates.
 */
export function parseSafeDate(rawDate?: string): number {
  if (!rawDate || typeof rawDate !== 'string') return 0;
  const trimmed = rawDate.trim();
  if (!trimmed) return 0;

  // Clean Korean date separators (e.g. "2026. 09. 08.", "2026년 9월 8일 14:30:00") while keeping space before time
  const cleaned = trimmed
    .replace(/년\s*/g, '-')
    .replace(/월\s*/g, '-')
    .replace(/일\s*/g, ' ')
    .trim();

  // Normalize dot/slash Y-M-D date separators (e.g. 2026. 09. 08. -> 2026-09-08) without mangling timezone offsets
  const normalized = cleaned
    .replace(/(\d{4})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{1,2})\.?/g, '$1-$2-$3')
    .replace(/\s+/g, ' ')
    .trim();

  // Match Y-M-D with optional time (HH:MM[:SS[.sss]]) and optional TZ (Z|[+-]HH[:]MM), rejecting calendar rollovers
  const dtMatch = normalized.match(
    /^(\d{4})-(\d{1,2})-(\d{1,2})(?:[T\s]+(\d{1,2}):(\d{2})(?::(\d{2})(?:\.(\d{1,9}))?)?\s*(Z|[+-]\d{2}:?\d{2})?)?$/i
  );
  if (dtMatch) {
    const year = Number(dtMatch[1]);
    const month = Number(dtMatch[2]);
    const day = Number(dtMatch[3]);
    if (!isValidUtcCalendarDate(year, month, day)) return 0;

    const yyyy = dtMatch[1];
    const mm = dtMatch[2].padStart(2, '0');
    const dd = dtMatch[3].padStart(2, '0');

    if (dtMatch[4] === undefined) {
      const ts = new Date(`${yyyy}-${mm}-${dd}T00:00:00Z`).getTime();
      return Number.isFinite(ts) && ts > 0 ? ts : 0;
    }

    const hour = Number(dtMatch[4]);
    const minute = Number(dtMatch[5]);
    const second = dtMatch[6] !== undefined ? Number(dtMatch[6]) : 0;
    if (hour < 0 || hour > 23 || minute < 0 || minute > 59 || second < 0 || second > 59) {
      return 0;
    }

    const hh = dtMatch[4].padStart(2, '0');
    const mi = dtMatch[5];
    const ss = (dtMatch[6] ?? '00').padStart(2, '0');
    const frac = dtMatch[7] ? `.${dtMatch[7].slice(0, 3)}` : '';
    let tz = dtMatch[8] ? dtMatch[8].toUpperCase() : 'Z';
    if (/^[+-]\d{4}$/.test(tz)) {
      tz = `${tz.slice(0, 3)}:${tz.slice(3)}`;
    }
    const iso = `${yyyy}-${mm}-${dd}T${hh}:${mi}:${ss}${frac}${tz}`;
    const ts = new Date(iso).getTime();
    return Number.isFinite(ts) && ts > 0 ? ts : 0;
  }

  // Fallback for RFC 2822 / standard date strings (reject bare integer strings like "2026")
  if (/^\d+$/.test(normalized)) return 0;
  const timestamp = new Date(normalized).getTime();
  if (Number.isFinite(timestamp) && timestamp > 0) {
    return timestamp;
  }

  return 0;
}

/**
 * Generates an array of page numbers with ellipsis for accessible pagination controls.
 */
export function getPaginationItems(current: number, total: number): Array<number | '...'> {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }
  if (current <= 4) {
    return [1, 2, 3, 4, 5, '...', total];
  }
  if (current >= total - 3) {
    return [1, '...', total - 4, total - 3, total - 2, total - 1, total];
  }
  return [1, '...', current - 1, current, current + 1, '...', total];
}

export interface DsiBreakdown {
  safety?: number;
  functional?: number;
  economic?: number;
  social?: number;
  convenience?: number;
  [key: string]: number | undefined;
}

export interface AdminDefectReportItem extends DefectReportItem {
  created_at?: string;
  dsi_breakdown?: DsiBreakdown;
  severity_index?: number;
  sentiment_polarity?: number;
  author?: string;
}

export interface AdminDailyReportData extends Omit<DailyReportData, 'reports'> {
  reports?: AdminDefectReportItem[];
}

interface AdminDashboardClientProps {
  initialData?: AdminDailyReportData | string | null;
}

type SortOption = 'critical' | 'recent' | 'negativity';
type ViewMode = 'cards' | 'table';

interface CategoryTab {
  code: string;
  label: string;
}

const SEVERITY_WEIGHT: Record<string, number> = {
  CRITICAL: 4,
  HIGH: 3,
  WARNING: 2,
  MEDIUM: 2,
  CAUTION: 1,
  LOW: 1,
  INFO: 0,
};

interface DefectReportWithTimestamp extends AdminDefectReportItem {
  _timestamp: number;
  _searchIndex: string;
  _spacelessIndex: string;
  _normalizedBrand: string;
}

const CATEGORY_TABS: CategoryTab[] = [
  { code: 'ALL', label: '전체' },
  { code: 'BATTERY_CHARGING', label: '배터리/충전' },
  { code: 'DRIVING_POWERTRAIN', label: '주행/모터/등판' },
  { code: 'BUILD_QUALITY', label: '단차/누수/마감' },
  { code: 'SOFTWARE_ELECTRONICS', label: 'OTA/소프트웨어' },
  { code: 'SERVICE_REPAIR_COST', label: 'AS/수리비' },
];

const SOURCE_OPTIONS = [
  { id: 'all', label: '전체 커뮤니티' },
  { id: 'bobaedream', label: '보배드림' },
  { id: 'dcinside', label: '디시인사이드' },
];

// Helper for category badge styling
function getCategoryBadgeClass(category: string) {
  switch (category) {
    case 'BATTERY_CHARGING':
      return 'bg-amber-100 text-amber-900 border-amber-300';
    case 'DRIVING_POWERTRAIN':
      return 'bg-orange-100 text-orange-900 border-orange-300';
    case 'BUILD_QUALITY':
      return 'bg-slate-100 text-slate-800 border-slate-300';
    case 'SOFTWARE_ELECTRONICS':
      return 'bg-purple-100 text-purple-900 border-purple-300';
    case 'SERVICE_REPAIR_COST':
      return 'bg-emerald-100 text-emerald-900 border-emerald-300';
    default:
      return 'bg-gray-100 text-gray-800 border-gray-300';
  }
}

// Helper for severity badge styling
function getSeverityBadge(severity: string) {
  const sev = String(severity || '').toUpperCase();
  if (sev.includes('CRITICAL')) {
    return (
      <span
        role="status"
        aria-label="심각도: 치명 (CRITICAL)"
        className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-700 text-white shadow-sm ring-1 ring-rose-600"
      >
        <svg className="w-3 h-3 animate-pulse motion-reduce:animate-none" width="12" height="12" focusable="false" aria-hidden="true" fill="currentColor" viewBox="0 0 20 20">
          <path
            fillRule="evenodd"
            d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
            clipRule="evenodd"
          />
        </svg>
        치명 (CRITICAL)
      </span>
    );
  }
  if (sev === 'HIGH') {
    return (
      <span
        role="status"
        aria-label="심각도: 높음 (HIGH)"
        className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-orange-700 text-white shadow-sm ring-1 ring-orange-600"
      >
        <svg className="w-3 h-3" width="12" height="12" focusable="false" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        높음 (HIGH)
      </span>
    );
  }
  if (sev === 'WARNING') {
    return (
      <span
        role="status"
        aria-label="심각도: 경고 (WARNING)"
        className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-400 text-slate-950 border border-amber-500 shadow-sm"
      >
        <svg className="w-3 h-3" width="12" height="12" focusable="false" aria-hidden="true" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
        </svg>
        경고 (WARNING)
      </span>
    );
  }
  if (sev === 'MEDIUM') {
    return (
      <span
        role="status"
        aria-label="심각도: 주의 (MEDIUM)"
        className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-950 border border-amber-400 shadow-sm"
      >
        <svg className="w-3 h-3 text-amber-800" width="12" height="12" focusable="false" aria-hidden="true" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
        </svg>
        주의 (MEDIUM)
      </span>
    );
  }
  if (sev === 'LOW') {
    return (
      <span
        role="status"
        aria-label="심각도: 낮음 (LOW)"
        className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-950 border border-emerald-300 shadow-sm"
      >
        <svg className="w-3 h-3 text-emerald-800" width="12" height="12" focusable="false" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7" />
        </svg>
        낮음 (LOW)
      </span>
    );
  }
  if (sev === 'INFO') {
    return (
      <span
        role="status"
        aria-label="심각도: 안정 (INFO)"
        className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-100 text-slate-900 border border-slate-300 shadow-sm"
      >
        <svg className="w-3 h-3 text-slate-700" width="12" height="12" focusable="false" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        안정 (INFO)
      </span>
    );
  }
  return (
    <span
      role="status"
      aria-label="심각도: 주의 (CAUTION)"
      className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-950 border border-amber-300 shadow-sm"
    >
      <svg className="w-3 h-3 text-amber-800" width="12" height="12" focusable="false" aria-hidden="true" fill="currentColor" viewBox="0 0 20 20">
        <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
      </svg>
      주의 (CAUTION)
    </span>
  );
}

function getSourceBadge(source: string, url: string) {
  const lower = (source || '').toLowerCase();
  const isBobae = lower.includes('bobae');
  const isDc = lower.includes('dc');
  const badgeText = isBobae
    ? '보배드림'
    : isDc
    ? '디시인사이드'
    : lower.includes('clien')
    ? '클리앙'
    : lower.includes('ppomppu')
    ? '뽐뿌'
    : source && source !== 'N/A'
    ? source
    : '커뮤니티';
  const badgeColor = isBobae
    ? 'bg-blue-50 text-blue-900 border-blue-200 hover:bg-blue-100'
    : 'bg-indigo-50 text-indigo-900 border-indigo-200 hover:bg-indigo-100';

  const safeUrl = sanitizeReportUrl(url);
  const isExternal = isExternalUrl(safeUrl);

  if (!isExternal) {
    return (
      <span
        title={`출처: ${badgeText} (원문 링크 없음)`}
        className={`inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-md border font-semibold ${badgeColor}`}
      >
        <span>{badgeText}</span>
      </span>
    );
  }

  return (
    <a
      href={safeUrl}
      target="_blank"
      rel="noopener noreferrer"
      title={`${badgeText} 원문 게시물 바로가기 (새 창에서 열림)`}
      aria-label={`${badgeText} 원문 게시물 바로가기 (새 창에서 열림)`}
      className={`inline-flex items-center justify-center gap-1 text-xs px-2.5 py-1.5 min-h-[44px] rounded-md border font-semibold transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${badgeColor}`}
    >
      <span>{badgeText}</span>
      <span className="sr-only"> (새 창에서 열림)</span>
      <svg className="w-3 h-3 opacity-70" width="12" height="12" focusable="false" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="2"
          d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
        />
      </svg>
    </a>
  );
}

export default function AdminDashboardClient({ initialData }: AdminDashboardClientProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Debounce search query input (150ms debounce) for buttery smooth typing and low CPU usage
  useEffect(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }
    debounceTimerRef.current = setTimeout(() => {
      setDebouncedQuery(searchQuery);
    }, 150);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [searchQuery]);

  const deferredSearchQuery = useDeferredValue(debouncedQuery);
  const [selectedCategory, setSelectedCategory] = useState('ALL');
  const [selectedSource, setSelectedSource] = useState('all');
  const [selectedBrand, setSelectedBrand] = useState('ALL');
  const [selectedDateRange, setSelectedDateRange] = useState('ALL');
  const [sortBy, setSortBy] = useState<SortOption>('critical');
  const [viewMode, setViewMode] = useState<ViewMode>('cards');
  const [pageSize, setPageSize] = useState<number>(10);

  // Accessible Modal Dialog State & Focus Management
  const [activeModalReport, setActiveModalReport] = useState<DefectReportWithTimestamp | null>(null);
  const triggerButtonRef = useRef<HTMLElement | null>(null);
  const modalRef = useRef<HTMLDivElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const focusReturnTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (focusReturnTimerRef.current) {
        clearTimeout(focusReturnTimerRef.current);
      }
    };
  }, []);

  const handleOpenModal = useCallback((report: DefectReportWithTimestamp, triggerEl?: HTMLElement) => {
    triggerButtonRef.current =
      triggerEl || (document.activeElement instanceof HTMLElement ? document.activeElement : null);
    setActiveModalReport(report);
  }, []);

  const handleCloseModal = useCallback(() => {
    setActiveModalReport(null);
    if (focusReturnTimerRef.current) {
      clearTimeout(focusReturnTimerRef.current);
    }
    // Keyboard accessibility: return focus to the trigger element that opened the dialog
    focusReturnTimerRef.current = setTimeout(() => {
      if (triggerButtonRef.current?.isConnected) {
        triggerButtonRef.current?.focus();
      } else {
        searchInputRef.current?.focus();
      }
    }, 0);
  }, []);

  // Window-level Escape key listener & focus containment guard while modal is open
  useEffect(() => {
    if (!activeModalReport) return;

    const handleWindowKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        handleCloseModal();
      }
    };

    const handleDocumentFocusIn = (e: FocusEvent) => {
      const target = e.target as Node | null;
      if (modalRef.current && target && !modalRef.current.contains(target)) {
        e.stopPropagation();
        (closeButtonRef.current ?? modalRef.current).focus();
      }
    };

    window.addEventListener('keydown', handleWindowKeyDown);
    document.addEventListener('focusin', handleDocumentFocusIn);
    return () => {
      window.removeEventListener('keydown', handleWindowKeyDown);
      document.removeEventListener('focusin', handleDocumentFocusIn);
    };
  }, [activeModalReport, handleCloseModal]);

  // Trap focus inside modal & keyboard dismissibility
  const handleModalKeyDown = useCallback((e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      handleCloseModal();
      return;
    }

    if (e.key === 'Tab' && modalRef.current) {
      const focusableElements = Array.from(
        modalRef.current.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
      ).filter((el) => el.offsetParent !== null || el === document.activeElement);

      if (focusableElements.length === 0) {
        e.preventDefault();
        modalRef.current.focus();
        return;
      }

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      if (e.shiftKey) {
        if (
          document.activeElement === firstElement ||
          document.activeElement === modalRef.current ||
          !modalRef.current.contains(document.activeElement)
        ) {
          e.preventDefault();
          lastElement.focus();
        }
      } else {
        if (document.activeElement === lastElement || !modalRef.current.contains(document.activeElement)) {
          e.preventDefault();
          firstElement.focus();
        }
      }
    }
  }, [handleCloseModal]);

  // Focus close button on mount & body scroll lock
  useEffect(() => {
    if (activeModalReport) {
      const prevOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      closeButtonRef.current?.focus();

      return () => {
        document.body.style.overflow = prevOverflow;
      };
    }
    return undefined;
  }, [activeModalReport]);

  // Keyboard arrow navigation for Category Tabs (WAI-ARIA APG pattern)
  const handleCategoryKeyDown = useCallback((e: React.KeyboardEvent, currentIndex: number) => {
    const count = CATEGORY_TABS.length;
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
      const nextTab = CATEGORY_TABS[nextIndex].code;
      setSelectedCategory(nextTab);
      document.getElementById(`category-tab-${nextTab}`)?.focus();
    }
  }, []);

  // Safe JSON parsing and fallback resolution for initialData
  const safeData = useMemo(() => {
    let parsed: unknown = initialData;
    if (typeof initialData === 'string') {
      parsed = safeJsonParse<AdminDailyReportData>(initialData, getFallbackReportData());
    }
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? (parsed as AdminDailyReportData)
      : getFallbackReportData();
  }, [initialData]);

  // Deduplicate and process reports with high-performance memoization
  const { dedupedReports, duplicatesRemovedCount } = useMemo(() => {
    const rawList = Array.isArray(safeData?.reports) ? safeData.reports : [];
    const dedupResult = deduplicateReports(rawList);
    const existingDedup = safeData?.statistics?.duplicates_removed ?? 0;
    return {
      dedupedReports: dedupResult.reports,
      duplicatesRemovedCount: Math.max(dedupResult.summary.duplicatesRemoved, existingDedup),
    };
  }, [safeData?.reports, safeData?.statistics?.duplicates_removed]);

  const reports = useMemo<DefectReportWithTimestamp[]>(() => {
    return dedupedReports
      .filter((r): r is AdminDefectReportItem => Boolean(r && typeof r === 'object'))
      .map((r, idx) => {
        const rawCreatedAt = typeof r.created_at === 'string' ? r.created_at : '';
        const rawDateField = typeof r.date === 'string' ? r.date : '';
        const parsedCreatedAt = parseSafeDate(rawCreatedAt);
        const parsed = parsedCreatedAt > 0 ? parsedCreatedAt : parseSafeDate(rawDateField);
        const catInfo = resolveCategory(r.defect_category, r.defect_category_ko);
        const catCode = catInfo.code;
        const catKo = catInfo.ko;

        // Safe JSON parsing for slang tags if stringified
        let rawSlang: unknown = r.slang_tags;
        if (typeof rawSlang === 'string') {
          const trimmed = rawSlang.trim();
          if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
            rawSlang = safeJsonParse<string[]>(trimmed, []);
          } else if (trimmed.length > 0) {
            rawSlang = trimmed.split(',').map((s: string) => s.trim()).filter(Boolean);
          } else {
            rawSlang = [];
          }
        }
        const slangList = (Array.isArray(rawSlang) ? rawSlang : [])
          .filter((t): t is string => typeof t === 'string' && t.trim().length > 0)
          .map((t) => maskSensitiveData(t.trim()));

        // Safe JSON parsing for DSI breakdown if stringified
        let rawDsi: unknown = r.dsi_breakdown;
        if (typeof rawDsi === 'string') {
          const trimmedDsi = rawDsi.trim();
          if (trimmedDsi.startsWith('{') && trimmedDsi.endsWith('}')) {
            rawDsi = safeJsonParse<DsiBreakdown>(trimmedDsi, {});
          }
        }
        const safeDsi: DsiBreakdown | undefined = rawDsi && typeof rawDsi === 'object' && !Array.isArray(rawDsi)
          ? {
              safety: typeof (rawDsi as Record<string, unknown>).safety === 'number' && Number.isFinite((rawDsi as Record<string, unknown>).safety) ? (rawDsi as Record<string, unknown>).safety as number : 0,
              functional: typeof (rawDsi as Record<string, unknown>).functional === 'number' && Number.isFinite((rawDsi as Record<string, unknown>).functional) ? (rawDsi as Record<string, unknown>).functional as number : 0,
              economic: typeof (rawDsi as Record<string, unknown>).economic === 'number' && Number.isFinite((rawDsi as Record<string, unknown>).economic) ? (rawDsi as Record<string, unknown>).economic as number : 0,
              social: typeof (rawDsi as Record<string, unknown>).social === 'number' && Number.isFinite((rawDsi as Record<string, unknown>).social) ? (rawDsi as Record<string, unknown>).social as number : 0,
              convenience: typeof (rawDsi as Record<string, unknown>).convenience === 'number' && Number.isFinite((rawDsi as Record<string, unknown>).convenience) ? (rawDsi as Record<string, unknown>).convenience as number : 0,
            }
          : undefined;

        const maskedTitle = maskSensitiveData(stripHtmlTags(r.title || '전기차 결함 제보'));
        const maskedSummary = maskSensitiveData(stripHtmlTags(r.summary || '결함 상세 내용 요약'));
        const maskedQuote = maskSensitiveData(stripHtmlTags(r.verbatim_quote || '원문 없음'));
        const maskedAuthor = r.author ? maskAuthor(stripHtmlTags(r.author)) : '익명 제보자';
        const cleanModel = maskSensitiveData(stripHtmlTags(r.vehicle_model || '')).trim() || '미상 모델';
        const normBrand = normalizeBrand(r.vehicle_brand);
        const cleanBrand = maskSensitiveData(stripHtmlTags(r.vehicle_brand || '')).trim() || normBrand;

        const searchTokens = [
          maskedTitle,
          maskedSummary,
          maskedQuote,
          cleanModel,
          cleanBrand,
          normBrand,
          maskedAuthor,
          r.id ? String(r.id) : '',
          catKo,
          ...slangList,
        ];
        const searchIndex = searchTokens.join(' ').toLowerCase();
        const spacelessIndex = searchIndex.replace(/\s+/g, '');

        // Standardize clean display date YYYY-MM-DD (validating calendar bounds)
        const rawDateStr = (rawDateField || (rawCreatedAt ? rawCreatedAt.slice(0, 10) : '')).trim();
        const ymdMatch = rawDateStr.match(/^(\d{4})[.\-/\s년]+(\d{1,2})[.\-/\s월]+(\d{1,2})/);
        let displayDate = parsed > 0 ? new Date(parsed).toISOString().slice(0, 10) : '날짜 미상';
        if (ymdMatch) {
          const candidateYmd = `${ymdMatch[1]}-${ymdMatch[2].padStart(2, '0')}-${ymdMatch[3].padStart(2, '0')}`;
          if (parseSafeDate(candidateYmd) > 0) {
            displayDate = candidateYmd;
          }
        }

        return {
          ...r,
          id: r.id ? String(r.id) : `report_${idx + 1}`,
          date: displayDate,
          source: (r.source || '').toLowerCase() || 'bobaedream',
          url: sanitizeReportUrl(r.url),
          defect_category: catCode,
          defect_category_ko: catKo,
          vehicle_model: cleanModel,
          vehicle_brand: cleanBrand,
          title: maskedTitle,
          summary: maskedSummary,
          verbatim_quote: maskedQuote,
          author: maskedAuthor,
          slang_tags: slangList,
          dsi_breakdown: safeDsi,
          sentiment_score: getSafeSentimentScore(r.sentiment_score, 0.85),
          severity: r.severity || 'WARNING',
          _timestamp: Number.isFinite(parsed) ? parsed : 0,
          _searchIndex: searchIndex,
          _spacelessIndex: spacelessIndex,
          _normalizedBrand: normBrand,
        };
      });
  }, [dedupedReports]);

  const rawStats = safeData?.statistics;
  const statistics = useMemo(() => {
    const totalScraped = typeof rawStats?.total_scraped === 'number' && Number.isFinite(rawStats.total_scraped)
      ? Math.max(0, rawStats.total_scraped)
      : Math.max(0, reports.length * 7);

    const totalFiltered = typeof rawStats?.total_filtered_defects === 'number' && Number.isFinite(rawStats.total_filtered_defects)
      ? Math.max(0, rawStats.total_filtered_defects)
      : reports.length;

    const criticalCount = typeof rawStats?.critical_defect_count === 'number' && Number.isFinite(rawStats.critical_defect_count)
      ? Math.max(0, rawStats.critical_defect_count)
      : reports.filter((r) => String(r.severity || '').toUpperCase() === 'CRITICAL').length;

    const avgScore = typeof rawStats?.avg_negativity_score === 'number' && Number.isFinite(rawStats.avg_negativity_score)
      ? getSafeSentimentScore(rawStats.avg_negativity_score, 0.85)
      : (reports.length > 0
          ? Number((reports.reduce((acc, r) => acc + (typeof r.sentiment_score === 'number' && Number.isFinite(r.sentiment_score) ? r.sentiment_score : 0), 0) / reports.length).toFixed(2))
          : 0.0);

    let computedTopModel = '해당 없음 (0건)';
    let computedTopPlatform = '해당 없음 (0%)';
    if (reports.length > 0 && (!rawStats?.top_model || !rawStats?.top_platform)) {
      const modelFreq = new Map<string, number>();
      const sourceFreq = new Map<string, number>();
      for (const r of reports) {
        const modelName = r.vehicle_model || '미상 모델';
        modelFreq.set(modelName, (modelFreq.get(modelName) || 0) + 1);
        const srcLower = (r.source || '').toLowerCase();
        const srcName = srcLower.includes('bobae')
          ? '보배드림'
          : srcLower.includes('dc')
          ? '디시인사이드'
          : r.source || '기타';
        sourceFreq.set(srcName, (sourceFreq.get(srcName) || 0) + 1);
      }
      const topModelEntry = Array.from(modelFreq.entries()).sort((a, b) => b[1] - a[1])[0];
      if (topModelEntry) computedTopModel = topModelEntry[0];
      const topSrcEntry = Array.from(sourceFreq.entries()).sort((a, b) => b[1] - a[1])[0];
      if (topSrcEntry) computedTopPlatform = topSrcEntry[0];
    }

    return {
      total_scraped: totalScraped,
      total_filtered_defects: totalFiltered,
      avg_negativity_score: avgScore,
      critical_defect_count: criticalCount,
      top_model: rawStats?.top_model || computedTopModel,
      top_platform: rawStats?.top_platform || computedTopPlatform,
    };
  }, [rawStats, reports]);

  const safeScore = getSafeSentimentScore(statistics.avg_negativity_score, 0.0);

  // Calculate dynamic category and source counts in a single O(N) pass
  const { categoryCounts, sourceCounts } = useMemo(() => {
    const catCounts: Record<string, number> = { ALL: reports.length };
    for (const cat of CATEGORY_TABS) {
      if (cat.code !== 'ALL') catCounts[cat.code] = 0;
    }
    const srcCounts: Record<string, number> = { all: reports.length };
    for (const src of SOURCE_OPTIONS) {
      if (src.id !== 'all') srcCounts[src.id] = 0;
    }

    const catLabelMap = new Map(CATEGORY_TABS.map((c) => [c.label, c.code]));

    for (const r of reports) {
      // Category count
      const catCode = r.defect_category;
      if (catCounts[catCode] !== undefined) {
        catCounts[catCode]++;
      } else {
        const mappedCode = catLabelMap.get(r.defect_category_ko);
        if (mappedCode && catCounts[mappedCode] !== undefined) {
          catCounts[mappedCode]++;
        }
      }

      // Source count
      const srcId = (r.source || '').toLowerCase();
      if (srcCounts[srcId] !== undefined) {
        srcCounts[srcId]++;
      }
    }
    return { categoryCounts: catCounts, sourceCounts: srcCounts };
  }, [reports]);

  // Dynamic brand aggregation with normalized naming and counts
  const { availableBrands, brandCounts } = useMemo(() => {
    const counts: Record<string, number> = { ALL: reports.length };
    for (const r of reports) {
      const b = r._normalizedBrand;
      counts[b] = (counts[b] || 0) + 1;
    }
    const brandOrder = ['현대', '기아', '제네시스', '테슬라', '벤츠', 'BMW', 'BYD', '폴스타', '기타'];
    const existing = Object.keys(counts).filter((k) => k !== 'ALL');
    existing.sort((a, b) => {
      const idxA = brandOrder.indexOf(a);
      const idxB = brandOrder.indexOf(b);
      if (idxA !== -1 && idxB !== -1) return idxA - idxB;
      if (idxA !== -1) return -1;
      if (idxB !== -1) return 1;
      return a.localeCompare(b);
    });
    return { availableBrands: existing, brandCounts: counts };
  }, [reports]);

  // Dynamic date aggregation with presets (최근 7일, 최근 30일) and specific dates
  const { availableDates, dateCounts, maxReportTimestamp } = useMemo(() => {
    const counts: Record<string, number> = { ALL: reports.length, RECENT_7D: 0, RECENT_30D: 0 };
    let maxTs = 0;
    for (const r of reports) {
      if (r._timestamp > maxTs) maxTs = r._timestamp;
      const d = r.date;
      if (d) counts[d] = (counts[d] || 0) + 1;
    }

    const sevenDaysMs = 7 * 24 * 60 * 60 * 1000;
    const thirtyDaysMs = 30 * 24 * 60 * 60 * 1000;
    for (const r of reports) {
      if (maxTs > 0 && r._timestamp > 0) {
        if (r._timestamp >= maxTs - sevenDaysMs) counts.RECENT_7D++;
        if (r._timestamp >= maxTs - thirtyDaysMs) counts.RECENT_30D++;
      }
    }

    const dates = Object.keys(counts)
      .filter((k) => /^\d{4}-\d{2}-\d{2}$/.test(k))
      .sort((a, b) => b.localeCompare(a));

    return { availableDates: dates, dateCounts: counts, maxReportTimestamp: maxTs };
  }, [reports]);

  // Filtered and sorted reports with fast precomputed index and optimized tokenization
  const filteredReports = useMemo(() => {
    const rawQuery = deferredSearchQuery.trim().toLowerCase().slice(0, 200);
    const selectedCategoryLabel =
      selectedCategory !== 'ALL'
        ? CATEGORY_TABS.find((c) => c.code === selectedCategory)?.label
        : undefined;

    // Precompute query tokens ONCE outside the report loop for high-performance large list filtering
    const queryTokens = rawQuery
      ? rawQuery
          .split(/\s+/)
          .filter(Boolean)
          .map((token) => {
            const cleanToken = token.replace(/^#+/, '');
            const spacelessToken = cleanToken.replace(/\s+/g, '');
            return { token, cleanToken, spacelessToken };
          })
      : [];

    return reports
      .filter((report) => {
        // Category filter
        if (selectedCategory !== 'ALL') {
          const catMatch =
            report.defect_category === selectedCategory ||
            (selectedCategoryLabel !== undefined && report.defect_category_ko === selectedCategoryLabel);
          if (!catMatch) return false;
        }

        // Source filter
        if (selectedSource !== 'all') {
          if ((report.source || '').toLowerCase() !== selectedSource.toLowerCase()) {
            return false;
          }
        }

        // Brand filter
        if (selectedBrand !== 'ALL') {
          if (report._normalizedBrand !== selectedBrand) {
            return false;
          }
        }

        // Date filter
        if (selectedDateRange !== 'ALL') {
          if (selectedDateRange === 'RECENT_7D') {
            const cutoff = maxReportTimestamp - 7 * 24 * 60 * 60 * 1000;
            if (maxReportTimestamp <= 0 || report._timestamp <= 0 || report._timestamp < cutoff) return false;
          } else if (selectedDateRange === 'RECENT_30D') {
            const cutoff = maxReportTimestamp - 30 * 24 * 60 * 60 * 1000;
            if (maxReportTimestamp <= 0 || report._timestamp <= 0 || report._timestamp < cutoff) return false;
          } else {
            if (report.date !== selectedDateRange) return false;
          }
        }

        // Search query filter: Korean spacing-tolerant, multi-keyword, and hashtag resilient
        if (queryTokens.length > 0) {
          const allTokensMatch = queryTokens.every(({ token, cleanToken, spacelessToken }) => {
            // 1. Direct index match
            if (report._searchIndex.includes(token) || (cleanToken && report._searchIndex.includes(cleanToken))) {
              return true;
            }
            // 2. Korean spacing-tolerant match (e.g. 아이오닉 5 <-> 아이오닉5)
            if (spacelessToken && report._spacelessIndex.includes(spacelessToken)) {
              return true;
            }
            // 3. Vehicle brand match
            const matchBrand = (report.vehicle_brand || '').toLowerCase().includes(token);
            if (matchBrand || (cleanToken && (report.vehicle_brand || '').toLowerCase().includes(cleanToken))) {
              return true;
            }
            return false;
          });

          if (!allTokensMatch) {
            return false;
          }
        }

        return true;
      })
      .sort((a, b) => {
        if (sortBy === 'critical') {
          const sevA = String(a.severity || '').trim().toUpperCase();
          const sevB = String(b.severity || '').trim().toUpperCase();
          const weightA = Object.prototype.hasOwnProperty.call(SEVERITY_WEIGHT, sevA)
            ? SEVERITY_WEIGHT[sevA]
            : 0;
          const weightB = Object.prototype.hasOwnProperty.call(SEVERITY_WEIGHT, sevB)
            ? SEVERITY_WEIGHT[sevB]
            : 0;
          if (weightB !== weightA) return weightB - weightA;
          if ((b.sentiment_score || 0) !== (a.sentiment_score || 0)) {
            return (b.sentiment_score || 0) - (a.sentiment_score || 0);
          }
          if (b._timestamp !== a._timestamp) {
            return b._timestamp - a._timestamp;
          }
          return String(b.id).localeCompare(String(a.id));
        }

        if (sortBy === 'recent') {
          if (b._timestamp !== a._timestamp) {
            return b._timestamp - a._timestamp;
          }
          const sevA = String(a.severity || '').trim().toUpperCase();
          const sevB = String(b.severity || '').trim().toUpperCase();
          const weightA = SEVERITY_WEIGHT[sevA] ?? 0;
          const weightB = SEVERITY_WEIGHT[sevB] ?? 0;
          if (weightB !== weightA) return weightB - weightA;
          if ((b.sentiment_score || 0) !== (a.sentiment_score || 0)) {
            return (b.sentiment_score || 0) - (a.sentiment_score || 0);
          }
          return String(b.id).localeCompare(String(a.id));
        }

        if (sortBy === 'negativity') {
          if ((b.sentiment_score || 0) !== (a.sentiment_score || 0)) {
            return (b.sentiment_score || 0) - (a.sentiment_score || 0);
          }
          if (b._timestamp !== a._timestamp) {
            return b._timestamp - a._timestamp;
          }
          return String(b.id).localeCompare(String(a.id));
        }

        return 0;
      });
  }, [reports, selectedCategory, selectedSource, selectedBrand, selectedDateRange, maxReportTimestamp, deferredSearchQuery, sortBy]);

  // Pagination State (WCAG AA Compliant Navigation)
  const [currentPage, setCurrentPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(filteredReports.length / pageSize));

  // Auto-reset to first page when filtering, sorting, or page size changes
  useEffect(() => {
    setCurrentPage(1);
  }, [selectedCategory, selectedSource, selectedBrand, selectedDateRange, deferredSearchQuery, sortBy, pageSize]);

  // Ensure current page bounds (strictly bounded between 1 and totalPages)
  const validCurrentPage = Math.max(1, Math.min(currentPage, totalPages));

  const paginatedReports = useMemo(() => {
    const start = (validCurrentPage - 1) * pageSize;
    return filteredReports.slice(start, start + pageSize);
  }, [filteredReports, validCurrentPage, pageSize]);

  const handleResetFilters = useCallback(() => {
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    setSearchQuery('');
    setDebouncedQuery('');
    setSelectedCategory('ALL');
    setSelectedSource('all');
    setSelectedBrand('ALL');
    setSelectedDateRange('ALL');
    setSortBy('critical');
    setCurrentPage(1);
    searchInputRef.current?.focus();
  }, []);

  const handleClearSearch = useCallback(() => {
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    setSearchQuery('');
    setDebouncedQuery('');
    searchInputRef.current?.focus();
  }, []);

  const handleTagClick = useCallback((tag: unknown) => {
    if (typeof tag !== 'string') return;
    const clean = tag.replace(/^[#\s]+/, '').trim().slice(0, 50);
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    setSearchQuery(clean);
    setDebouncedQuery(clean);
  }, []);

  return (
    <div className="space-y-6">
      {/* Confidential Header Bar */}
      <header aria-label="관리자 결함 모니터링 헤더" className="bg-slate-900 border border-slate-800 text-slate-100 rounded-2xl p-6 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 -mt-4 -mr-4 w-40 h-40 bg-rose-600/10 rounded-full blur-3xl pointer-events-none" />
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30">
                <svg className="w-3 h-3" width="12" height="12" focusable="false" aria-hidden="true" fill="currentColor" viewBox="0 0 20 20">
                  <path
                    fillRule="evenodd"
                    d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z"
                    clipRule="evenodd"
                  />
                </svg>
                CONFIDENTIAL · 사내 관리자 전용
              </span>
              {reports.length === 0 ? (
                <span
                  role="status"
                  aria-label="파이프라인 상태: 데이터 동기화 대기 중"
                  className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/20 text-amber-300 border border-amber-500/30"
                >
                  <span className="relative flex h-2 w-2" aria-hidden="true">
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-400" />
                  </span>
                  데이터 동기화 대기 중
                </span>
              ) : (
                <span
                  role="status"
                  aria-label="파이프라인 상태: 파이프라인 정상 가동"
                  className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                >
                  <span className="relative flex h-2 w-2" aria-hidden="true">
                    <span className="animate-ping motion-reduce:animate-none absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400" />
                  </span>
                  파이프라인 정상 가동
                </span>
              )}
              {/* Deduplication Status Badge */}
              <span
                role="status"
                aria-label={`데이터 정제 상태: ${
                  duplicatesRemovedCount > 0
                    ? `중복 ${duplicatesRemovedCount}건 정제 완료 (고유성 100%)`
                    : '중복 0건 (고유 제보 100% 검증)'
                }`}
                className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30"
              >
                <svg className="w-3 h-3 text-cyan-300" width="12" height="12" focusable="false" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {duplicatesRemovedCount > 0
                  ? `중복 ${duplicatesRemovedCount}건 정제 완료`
                  : '중복 0건 · 고유 제보 100%'}
              </span>
            </div>
            <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-white">
              일일 전기차(EV) 결함 모니터링
            </h1>
            <p className="text-sm text-slate-300 mt-1">
              국내 주요 커뮤니티(보배드림, 디시인사이드) 실시간 부정 피드백 및 날것의 결함 제보 수집 대시보드
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 text-xs text-slate-300">
            <div className="bg-slate-800/80 px-3 py-2 rounded-lg border border-slate-700">
              <span className="block text-slate-300 font-mono">파이프라인 버전</span>
              <span className="font-semibold text-slate-200">v{safeData?.pipeline_version || '1.0.0'}</span>
            </div>
            <div className="bg-slate-800/80 px-3 py-2 rounded-lg border border-slate-700">
              <span className="block text-slate-300 font-mono">최종 수집 시각</span>
              <ClientTimestamp
                isoString={safeData?.generated_at}
                className="font-semibold text-slate-200"
              />
            </div>
          </div>
        </div>
      </header>

      {/* 4 KPI Summary Cards */}
      <section aria-labelledby="kpi-summary-heading">
        <h2 id="kpi-summary-heading" className="sr-only">주요 결함 모니터링 통계 지표</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Total Defects */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm hover:shadow-md transition">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-800 tracking-wider uppercase">
              전체 수집 결함
            </span>
            <div className="w-9 h-9 rounded-xl bg-blue-100 text-blue-800 flex items-center justify-center font-bold">
              <svg className="w-5 h-5" width="20" height="20" focusable="false" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-black text-slate-900">
              {statistics.total_filtered_defects}
            </span>
            <span className="text-sm font-semibold text-slate-800">건 분석</span>
          </div>
          <div className="mt-2 text-xs text-slate-800 flex items-center justify-between">
            <span>스크랩 대상: {statistics.total_scraped}건</span>
            <span className="text-blue-700 font-semibold">
              유효율 {statistics.total_scraped > 0 ? Math.min(100, Math.max(0, Math.round((statistics.total_filtered_defects / statistics.total_scraped) * 100))) : 0}%
            </span>
          </div>
          <div className="mt-1 text-[11px] text-cyan-800 font-medium flex items-center gap-1">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-cyan-600" aria-hidden="true" />
            <span>
              {duplicatesRemovedCount > 0
                ? `중복 정제: ${duplicatesRemovedCount}건 제거 (순수 결함 고유 보장)`
                : '중복 정제 완료 · 100% 고유 결함 검증'}
            </span>
          </div>
        </div>

        {/* Card 2: Critical Issues */}
        <div className="bg-white rounded-2xl p-5 border border-rose-200 bg-gradient-to-br from-white to-rose-50/30 shadow-sm hover:shadow-md transition">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-rose-800 tracking-wider uppercase">
              치명적 안전 결함
            </span>
            <div className="w-9 h-9 rounded-xl bg-rose-100 text-rose-800 flex items-center justify-center font-bold">
              <svg className="w-5 h-5" width="20" height="20" focusable="false" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-black text-rose-700">
              {statistics.critical_defect_count}
            </span>
            <span className="text-sm font-bold text-rose-800">건 위험</span>
          </div>
          <div className="mt-2 text-xs text-rose-800 font-semibold">
            동력상실 · 화재위험 · 급제동 긴급 모니터링
          </div>
        </div>

        {/* Card 3: Avg Negativity Score */}
        <div className="bg-white rounded-2xl p-5 border border-amber-200 bg-gradient-to-br from-white to-amber-50/20 shadow-sm hover:shadow-md transition">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-amber-800 tracking-wider uppercase">
              평균 부정 감성 지수
            </span>
            <div className="w-9 h-9 rounded-xl bg-amber-100 text-amber-800 flex items-center justify-center font-bold">
              <svg className="w-5 h-5" width="20" height="20" focusable="false" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M13 10V3L4 14h7v7l9-11h-7z"
                />
              </svg>
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-black text-slate-900">
              {Math.round(safeScore * 100)}%
            </span>
            <span
              role="status"
              aria-label={`부정 감성 평가: ${
                reports.length === 0
                  ? '데이터 없음'
                  : safeScore >= 0.8
                  ? '극도로 부정적'
                  : safeScore >= 0.6
                  ? '부정적 우세'
                  : safeScore >= 0.4
                  ? '중립적'
                  : '안정'
              }`}
              className={`text-xs font-bold px-2 py-0.5 rounded ${
                reports.length === 0
                  ? 'bg-slate-100 text-slate-800'
                  : safeScore >= 0.8
                  ? 'bg-rose-100 text-rose-900 border border-rose-300'
                  : safeScore >= 0.6
                  ? 'bg-amber-100 text-amber-950 border border-amber-300'
                  : safeScore >= 0.4
                  ? 'bg-slate-100 text-slate-900 border border-slate-300'
                  : 'bg-emerald-100 text-emerald-950 border border-emerald-300'
              }`}
            >
              {reports.length === 0
                ? '데이터 없음'
                : safeScore >= 0.8
                ? '극도로 부정적'
                : safeScore >= 0.6
                ? '부정적 우세'
                : safeScore >= 0.4
                ? '중립적'
                : '안정'}
            </span>
          </div>
          <div
            role="progressbar"
            aria-valuenow={Math.round(safeScore * 100)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="평균 부정 감성 지수"
            aria-valuetext={`${Math.round(safeScore * 100)}%`}
            className="mt-2 w-full bg-slate-200 rounded-full h-2 overflow-hidden border border-slate-300"
          >
            <div
              className="bg-amber-600 h-2 rounded-full transition-all duration-500"
              style={{ width: `${Math.round(safeScore * 100)}%` }}
            />
          </div>
        </div>

        {/* Card 4: Top Platform & Model */}
        <div className="bg-white rounded-2xl p-5 border border-indigo-200 bg-gradient-to-br from-white to-indigo-50/20 shadow-sm hover:shadow-md transition">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-indigo-900 tracking-wider uppercase">
              최다 제보 차종 / 플랫폼
            </span>
            <div className="w-9 h-9 rounded-xl bg-indigo-100 text-indigo-800 flex items-center justify-center font-bold">
              <svg className="w-5 h-5" width="20" height="20" focusable="false" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
                />
              </svg>
            </div>
          </div>
          <div className="mt-3">
            <div className="text-xl font-extrabold text-slate-900 truncate" title={statistics.top_model}>
              {statistics.top_model}
            </div>
            <div className="text-xs text-indigo-900 font-semibold mt-1 flex items-center gap-1">
              <span>출처:</span>
              <span>{statistics.top_platform}</span>
            </div>
          </div>
        </div>
      </div>
    </section>

      {/* Filter and Search Bar Section */}
      <section aria-label="결함 제보 필터 및 검색 제어판" className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm space-y-4">
        {/* Search & Sort Row */}
        <div className="flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between">
          {/* Full-text search input with WCAG search landmark and accessible description */}
          <div role="search" aria-label="전기차 결함 제보 및 은어 검색" className="relative flex-1">
            <label htmlFor="admin-defect-search-input" className="sr-only">전기차 결함 제보 및 은어 검색</label>
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-600">
              <svg className="w-4 h-4" width="16" height="16" focusable="false" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
            </div>
            <input
              id="admin-defect-search-input"
              ref={searchInputRef}
              type="search"
              value={searchQuery}
              maxLength={200}
              onChange={(e) => setSearchQuery(e.target.value.slice(0, 200))}
              onKeyDown={(e) => {
                if (e.key === 'Escape' && searchQuery) {
                  e.preventDefault();
                  setSearchQuery('');
                }
              }}
              aria-describedby="admin-defect-search-hint"
              aria-label="전기차 결함 제보 및 은어 검색"
              placeholder="제목, 요약, 실차주 원문 코멘트, 차종, 은어(#ICCU폭탄 등) 실시간 검색..."
              className="w-full pl-10 pr-10 py-2.5 min-h-[44px] text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 focus:bg-white transition placeholder-slate-600"
            />
            <span id="admin-defect-search-hint" className="sr-only">
              검색어를 입력하면 실시간으로 목록이 필터링됩니다. ESC 키를 누르면 입력한 검색어가 초기화됩니다.
            </span>
            {searchQuery && (
              <button
                type="button"
                onClick={handleClearSearch}
                className="absolute inset-y-0 right-0 pr-3 min-w-[44px] min-h-[44px] flex items-center justify-center text-slate-700 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1 rounded-lg"
                title="검색어 지우기"
                aria-label="검색어 지우기"
              >
                <svg className="w-4 h-4" width="16" height="16" focusable="false" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>

          {/* Controls Row: Sort, View Mode, and Page Size */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Sort Selector */}
            <div role="group" aria-label="결함 제보 정렬 기준" className="flex items-center gap-1.5">
              <span className="text-xs font-semibold text-slate-700 whitespace-nowrap">정렬:</span>
              <div className="inline-flex rounded-xl bg-slate-100 p-1 border border-slate-200 text-xs font-semibold">
                <button
                  type="button"
                  aria-pressed={sortBy === 'critical'}
                  onClick={() => setSortBy('critical')}
                  className={`px-3 py-1.5 min-h-[44px] inline-flex items-center gap-1.5 rounded-lg transition focus:outline-none focus:ring-2 focus:ring-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1 ${
                    sortBy === 'critical'
                      ? 'bg-white text-rose-700 font-bold shadow-sm ring-1 ring-slate-200'
                      : 'text-slate-700 hover:text-slate-900'
                  }`}
                >
                  {sortBy === 'critical' && <span className="w-1.5 h-1.5 rounded-full bg-rose-600" aria-hidden="true" />}
                  치명도순
                </button>
                <button
                  type="button"
                  aria-pressed={sortBy === 'recent'}
                  onClick={() => setSortBy('recent')}
                  className={`px-3 py-1.5 min-h-[44px] inline-flex items-center gap-1.5 rounded-lg transition focus:outline-none focus:ring-2 focus:ring-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1 ${
                    sortBy === 'recent'
                      ? 'bg-white text-blue-700 font-bold shadow-sm ring-1 ring-slate-200'
                      : 'text-slate-700 hover:text-slate-900'
                  }`}
                >
                  {sortBy === 'recent' && <span className="w-1.5 h-1.5 rounded-full bg-blue-600" aria-hidden="true" />}
                  최신수집순
                </button>
                <button
                  type="button"
                  aria-pressed={sortBy === 'negativity'}
                  onClick={() => setSortBy('negativity')}
                  className={`px-3 py-1.5 min-h-[44px] inline-flex items-center gap-1.5 rounded-lg transition focus:outline-none focus:ring-2 focus:ring-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1 ${
                    sortBy === 'negativity'
                      ? 'bg-white text-amber-800 font-bold shadow-sm ring-1 ring-slate-200'
                      : 'text-slate-700 hover:text-slate-900'
                  }`}
                >
                  {sortBy === 'negativity' && <span className="w-1.5 h-1.5 rounded-full bg-amber-600" aria-hidden="true" />}
                  부정점수순
                </button>
              </div>
            </div>

            {/* View Mode Toggle: Cards vs Table */}
            <div role="group" aria-label="목록 표시 형식 선택" className="flex items-center gap-1">
              <div className="inline-flex rounded-xl bg-slate-100 p-1 border border-slate-200 text-xs font-semibold">
                <button
                  type="button"
                  aria-pressed={viewMode === 'cards'}
                  onClick={() => setViewMode('cards')}
                  title="카드 보기 형식으로 전환"
                  aria-label="카드 보기 형식으로 전환"
                  className={`px-2.5 py-1.5 min-h-[44px] inline-flex items-center gap-1 rounded-lg transition focus:outline-none focus:ring-2 focus:ring-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1 ${
                    viewMode === 'cards'
                      ? 'bg-white text-slate-900 shadow-sm font-bold ring-1 ring-slate-200'
                      : 'text-slate-700 hover:text-slate-900'
                  }`}
                >
                  <svg className="w-3.5 h-3.5" width="14" height="14" focusable="false" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                  </svg>
                  <span>카드</span>
                </button>
                <button
                  type="button"
                  aria-pressed={viewMode === 'table'}
                  onClick={() => setViewMode('table')}
                  title="데이터 테이블 보기 형식으로 전환"
                  aria-label="데이터 테이블 보기 형식으로 전환"
                  className={`px-2.5 py-1.5 min-h-[44px] inline-flex items-center gap-1 rounded-lg transition focus:outline-none focus:ring-2 focus:ring-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1 ${
                    viewMode === 'table'
                      ? 'bg-white text-slate-900 shadow-sm font-bold ring-1 ring-slate-200'
                      : 'text-slate-700 hover:text-slate-900'
                  }`}
                >
                  <svg className="w-3.5 h-3.5" width="14" height="14" focusable="false" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                  <span>테이블</span>
                </button>
              </div>
            </div>

            {/* Page Size Selector */}
            <div className="flex items-center gap-1 text-xs">
              <label htmlFor="admin-page-size-select" className="sr-only">페이지당 표시 개수</label>
              <select
                id="admin-page-size-select"
                value={pageSize}
                onChange={(e) => {
                  const next = Number(e.target.value);
                  if (Number.isFinite(next) && next > 0) setPageSize(next);
                }}
                className="min-h-[44px] px-2 py-1.5 bg-slate-100 text-slate-800 rounded-xl border border-slate-200 font-semibold focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 cursor-pointer"
                aria-label="페이지당 표시 제보 개수 선택"
              >
                <option value={10}>10개씩</option>
                <option value={25}>25개씩</option>
                <option value={50}>50개씩</option>
              </select>
            </div>
          </div>
        </div>

        {/* Category Tabs */}
        <div role="tablist" aria-label="결함 카테고리 탭" className="flex items-center gap-1.5 overflow-x-auto pb-1 pt-1 scrollbar-none text-xs">
          {CATEGORY_TABS.map((tab, idx) => {
            const isSelected = selectedCategory === tab.code;
            const count = categoryCounts[tab.code] || 0;
            return (
              <button
                key={tab.code}
                id={`category-tab-${tab.code}`}
                aria-controls="reports-tabpanel"
                type="button"
                role="tab"
                aria-selected={isSelected}
                tabIndex={isSelected ? 0 : -1}
                aria-label={`${tab.label} 카테고리 (${count}건)`}
                onKeyDown={(e) => handleCategoryKeyDown(e, idx)}
                onClick={() => setSelectedCategory(tab.code)}
                className={`px-3 py-2 min-h-[44px] rounded-xl font-semibold whitespace-nowrap transition flex items-center gap-1.5 focus:outline-none focus:ring-2 focus:ring-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 ${
                  isSelected
                    ? 'bg-slate-900 text-white shadow-sm ring-1 ring-slate-900'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200 hover:text-slate-900'
                }`}
              >
                <span>{tab.label}</span>
                <span
                  className={`text-[11px] px-1.5 py-0.5 rounded-full ${
                    isSelected ? 'bg-slate-700 text-slate-200' : 'bg-slate-200 text-slate-700'
                  }`}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Community Source, Brand, and Date Selector Controls */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-100 text-xs">
          <div className="flex flex-wrap items-center gap-3 md:gap-4">
            {/* Source Platform Filter */}
            <div role="group" aria-label="출처 플랫폼 필터" className="flex flex-wrap items-center gap-1.5">
              <span className="font-semibold text-slate-700 whitespace-nowrap">출처 플랫폼:</span>
              <div className="flex flex-wrap items-center gap-1">
                {SOURCE_OPTIONS.map((src) => {
                  const isSelected = selectedSource === src.id;
                  const count = sourceCounts[src.id] || 0;
                  return (
                    <button
                      key={src.id}
                      type="button"
                      aria-pressed={isSelected}
                      aria-label={`${src.label} 필터 (${count}건)`}
                      onClick={() => setSelectedSource(src.id)}
                      className={`px-2.5 py-1 min-h-[44px] rounded-lg font-medium transition flex items-center gap-1 border focus:outline-none focus:ring-2 focus:ring-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1 ${
                        isSelected
                          ? 'bg-blue-600 text-white border-blue-600 shadow-sm font-semibold'
                          : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
                      }`}
                    >
                      <span>{src.label}</span>
                      <span
                        className={`text-[10px] px-1 rounded ${
                          isSelected ? 'bg-blue-800 text-white' : 'bg-slate-100 text-slate-700'
                        }`}
                      >
                        {count}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Vehicle Brand Filter */}
            <div className="flex items-center gap-1.5">
              <label htmlFor="admin-brand-filter" className="font-semibold text-slate-700 whitespace-nowrap">
                차량 브랜드:
              </label>
              <select
                id="admin-brand-filter"
                value={selectedBrand}
                onChange={(e) => setSelectedBrand(e.target.value)}
                aria-label="차량 브랜드 필터 선택"
                className="min-h-[44px] px-2.5 py-1.5 bg-slate-100 text-slate-800 rounded-xl border border-slate-200 font-semibold focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 cursor-pointer"
              >
                <option value="ALL">전체 브랜드 ({reports.length}건)</option>
                {availableBrands.map((brand) => (
                  <option key={brand} value={brand}>
                    {brand} ({brandCounts[brand] || 0}건)
                  </option>
                ))}
              </select>
            </div>

            {/* Collection Date Filter */}
            <div className="flex items-center gap-1.5">
              <label htmlFor="admin-date-filter" className="font-semibold text-slate-700 whitespace-nowrap">
                수집 일자:
              </label>
              <select
                id="admin-date-filter"
                value={selectedDateRange}
                onChange={(e) => setSelectedDateRange(e.target.value)}
                aria-label="수집 일자 필터 선택"
                className="min-h-[44px] px-2.5 py-1.5 bg-slate-100 text-slate-800 rounded-xl border border-slate-200 font-semibold focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 cursor-pointer"
              >
                <option value="ALL">전체 기간 ({reports.length}건)</option>
                <option value="RECENT_7D">최근 7일 ({dateCounts['RECENT_7D'] || 0}건)</option>
                <option value="RECENT_30D">최근 30일 ({dateCounts['RECENT_30D'] || 0}건)</option>
                <optgroup label="특정 수집 일자">
                  {availableDates.map((d) => (
                    <option key={d} value={d}>
                      {d} ({dateCounts[d] || 0}건)
                    </option>
                  ))}
                </optgroup>
              </select>
            </div>
          </div>

          {/* Active filter counter & reset button */}
          <div className="flex items-center gap-3">
            <span
              aria-live="polite"
              aria-atomic="true"
              className="text-slate-700 font-medium"
            >
              결과 <strong className="text-slate-900 font-bold">{filteredReports.length}</strong>건
              {duplicatesRemovedCount > 0 && (
                <span className="text-[11px] text-cyan-800 ml-1.5 font-semibold">
                  (중복 {duplicatesRemovedCount}건 필터링 완료)
                </span>
              )}
            </span>
            {(searchQuery || selectedCategory !== 'ALL' || selectedSource !== 'all' || selectedBrand !== 'ALL' || selectedDateRange !== 'ALL') && (
              <button
                type="button"
                onClick={handleResetFilters}
                aria-label="모든 검색 및 카테고리 필터 초기화"
                className="text-xs text-rose-700 hover:text-rose-800 font-semibold underline min-h-[44px] inline-flex items-center gap-1 focus:outline-none focus:ring-2 focus:ring-rose-600 focus-visible:ring-2 focus-visible:ring-rose-500 focus-visible:ring-offset-1 rounded-lg px-2"
              >
                <svg className="w-3 h-3" width="12" height="12" focusable="false" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                  />
                </svg>
                필터 초기화
              </button>
            )}
          </div>
        </div>
      </section>

      {/* Reports List */}
      <div
        id="reports-tabpanel"
        role="tabpanel"
        aria-labelledby={`category-tab-${selectedCategory}`}
        tabIndex={0}
        className="focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-2xl"
      >
        {/* Screen Reader Accessible Live Result Announcement */}
        <div
          aria-live="polite"
          aria-atomic="true"
          className="sr-only"
        >
          {selectedCategory !== 'ALL' || searchQuery || selectedSource !== 'all' || selectedBrand !== 'ALL' || selectedDateRange !== 'ALL'
            ? `필터링된 결과: 총 ${filteredReports.length}건의 결함 제보`
            : `전체 수집된 결함 제보: 총 ${filteredReports.length}건`}
        </div>

        {/* Screen Reader Accessible Summary Table for Defect Reports (always present for screen readers) */}
        <div className={viewMode === 'table' ? 'overflow-x-auto table-scroll-container rounded-2xl border border-slate-200 bg-white shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2' : 'sr-only focus-within:not-sr-only focus-within:overflow-x-auto focus-within:bg-white focus-within:p-2 focus-within:rounded-2xl focus-within:border focus-within:border-slate-200'} tabIndex={viewMode === 'table' ? 0 : undefined} role={viewMode === 'table' ? 'region' : undefined} aria-label={viewMode === 'table' ? '결함 제보 요약 데이터 테이블' : undefined}>
          {viewMode === 'table' && (
            <div className="sm:hidden flex items-center justify-between px-3 py-1.5 text-[11px] font-medium text-slate-600 bg-slate-50 border-b border-slate-200 select-none" aria-hidden="true"><span>← 좌우로 밀어서 전체 제보 내역 확인</span><span className="text-[10px] text-blue-700 font-semibold">가로 스크롤 ↔</span></div>
          )}
          <table aria-label="수집된 전기차 결함 제보 데이터 요약 표" className="w-full min-w-[760px] text-left text-xs text-slate-800 border-collapse">
            <caption>
              {filteredReports.length === 0
                ? `카테고리: ${CATEGORY_TABS.find((c) => c.code === selectedCategory)?.label || '전체'}, 수집된 결함 제보 없음 (총 0건)`
                : `카테고리: ${CATEGORY_TABS.find((c) => c.code === selectedCategory)?.label || '전체'}, 총 ${filteredReports.length}건 중 ${validCurrentPage}페이지 (${(validCurrentPage - 1) * pageSize + 1} - ${Math.min(validCurrentPage * pageSize, filteredReports.length)}건)`}
            </caption>
            <thead className="bg-slate-100 text-slate-900 font-bold border-b border-slate-200">
              <tr>
                <th scope="col" className="px-3 py-3">번호</th>
                <th scope="col" className="px-3 py-3">날짜</th>
                <th scope="col" className="px-3 py-3">차종</th>
                <th scope="col" className="px-3 py-3">분류</th>
                <th scope="col" className="px-3 py-3">심각도</th>
                <th scope="col" className="px-3 py-3">출처</th>
                <th scope="col" className="px-3 py-3">제목</th>
                <th scope="col" className="px-3 py-3">분석 요약</th>
                <th scope="col" className="px-3 py-3">부정 감성</th>
                {viewMode === 'table' && <th scope="col" className="px-3 py-3 text-right">관리</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {paginatedReports.length === 0 ? (
                <tr>
                  <td colSpan={viewMode === 'table' ? 10 : 9} className="text-center py-8 text-slate-700 text-sm">
                    일치하는 결함 제보 데이터가 없습니다. (원문 링크 없음)
                  </td>
                </tr>
              ) : (
                paginatedReports.map((report, idx) => {
                  const safeUrl = sanitizeReportUrl(report.url);
                  const isExt = isExternalUrl(safeUrl);
                  const overallIdx = (validCurrentPage - 1) * pageSize + idx + 1;
                  return (
                    <tr key={`report-row-${report.id}`} className="hover:bg-slate-50 transition border-b border-slate-100">
                      <th scope="row" className="px-3 py-3 font-semibold text-slate-900 whitespace-nowrap">
                        제보 #{overallIdx}
                      </th>
                      <td className="px-3 py-3 text-slate-800 whitespace-nowrap font-mono text-xs">{report.date}</td>
                      <td className="px-3 py-3 text-slate-900 font-semibold whitespace-nowrap">{report.vehicle_model}</td>
                      <td className="px-3 py-3 whitespace-nowrap">
                        <span role="status" aria-label={`결함 분류: ${report.defect_category_ko}`} className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold border ${getCategoryBadgeClass(report.defect_category)}`}>
                          {report.defect_category_ko}
                        </span>
                      </td>
                      <td className="px-3 py-3 whitespace-nowrap">{getSeverityBadge(report.severity)}</td>
                      <td className="px-3 py-3 whitespace-nowrap">{getSourceBadge(report.source || 'N/A', safeUrl)}</td>
                      <td className="px-3 py-3 text-slate-900 font-medium max-w-xs" title={report.title}>
                        <div className="flex items-center gap-1.5 min-w-0">
                          <span id={`report-table-title-${report.id}`} className="truncate"><span>{report.title}</span></span>
                          {isExt ? (
                            <a
                              href={safeUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              aria-label="게시글 원문 보기"
                              aria-describedby={`report-table-title-${report.id}`}
                              title="게시글 원문 보기 (새 창에서 열림)"
                              className="shrink-0 inline-flex items-center min-h-[44px] px-2 py-1 focus:bg-blue-700 focus:text-white rounded focus:outline-none focus:ring-2 focus:ring-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 text-blue-700 underline text-xs font-semibold"
                            >
                              (원문 링크)
                            </a>
                          ) : (
                            <span className="shrink-0 text-slate-600 text-xs">(원문 링크 없음)</span>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-3 text-slate-800 text-xs max-w-sm truncate" title={report.summary}>
                        {report.summary}
                      </td>
                      <td className="px-3 py-3 whitespace-nowrap text-xs">
                        <span className="font-mono font-bold text-rose-700" aria-label={`부정 감성 지수: ${formatSentimentPercent(report.sentiment_score)}%`}>
                          {formatSentimentPercent(report.sentiment_score)}%
                        </span>
                        <span className="ml-1 text-[10px] font-semibold px-1 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200" aria-hidden="true">
                          {formatSentimentPercent(report.sentiment_score) >= 80
                            ? '극도 부정'
                            : formatSentimentPercent(report.sentiment_score) >= 60
                            ? '높음'
                            : formatSentimentPercent(report.sentiment_score) >= 40
                            ? '보통'
                            : '낮음'}
                        </span>
                      </td>
                      {viewMode === 'table' && (
                        <td className="px-3 py-3 whitespace-nowrap text-right">
                          <button
                            type="button"
                            aria-haspopup="dialog"
                            aria-label={`제보 #${overallIdx} (${report.vehicle_model}) 결함 상세 분석 및 DSI 지표 모달 열기`}
                            onClick={(e) => handleOpenModal(report, e.currentTarget)}
                            className="px-2.5 py-1 min-h-[44px] inline-flex items-center gap-1 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-200 transition focus:outline-none focus:ring-2 focus:ring-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1"
                          >
                            상세 분석
                          </button>
                        </td>
                      )}
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {reports.length === 0 ? (
          <div className="bg-white rounded-2xl p-12 border border-slate-200 text-center space-y-3" role="status">
            <div className="w-12 h-12 rounded-full bg-amber-50 text-amber-700 mx-auto flex items-center justify-center">
              <svg className="w-6 h-6" width="24" height="24" focusable="false" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
            <h2 className="text-base font-bold text-slate-800">수집된 결함 리포트 데이터가 없습니다</h2>
            <p className="text-xs text-slate-700 max-w-sm mx-auto">
              현재 등록된 결함 리포트 데이터가 없거나 수집 파이프라인 동기화가 진행 중입니다. 데이터 수집 완료 후 자동으로 업데이트됩니다.
            </p>
          </div>
        ) : filteredReports.length === 0 ? (
          <div className="bg-white rounded-2xl p-12 border border-slate-200 text-center space-y-3" role="status" aria-live="polite">
            <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-700 mx-auto flex items-center justify-center">
              <svg className="w-6 h-6" width="24" height="24" focusable="false" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
            <h2 className="text-base font-bold text-slate-800">일치하는 결함 리포트가 없습니다</h2>
            <p className="text-xs text-slate-700 max-w-sm mx-auto">
              선택한 카테고리나 검색어와 일치하는 커뮤니티 결함 코멘트가 없습니다. 검색어를 변경하거나 필터를 초기화해 보세요.
            </p>
            <button
              type="button"
              onClick={handleResetFilters}
              className="mt-2 inline-flex items-center gap-1 px-4 py-2 min-h-[44px] rounded-xl text-xs font-semibold bg-slate-900 text-white hover:bg-slate-800 transition focus:outline-none focus:ring-2 focus:ring-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
            >
              모든 필터 초기화
            </button>
          </div>
        ) : (
          <section aria-labelledby="admin-defect-reports-list-heading" className="space-y-4">
            <h2 id="admin-defect-reports-list-heading" className="sr-only">수집된 결함 제보 상세 목록</h2>
            {viewMode === 'cards' && (
              <div className="space-y-4">
                {paginatedReports.map((report: DefectReportWithTimestamp) => (
                  <DefectReportCard
                    key={report.id}
                    report={report}
                    onTagClick={handleTagClick}
                    onOpenModal={handleOpenModal}
                  />
                ))}
              </div>
            )}

            {/* Accessible Pagination Navigation Component */}
            <nav aria-label="결함 제보 목록 페이지 탐색" className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-6 border-t border-slate-200">
              <div className="text-xs text-slate-700 font-medium" aria-live="polite">
                전체 <strong className="text-slate-900 font-bold">{filteredReports.length}</strong>건 중{' '}
                <span className="font-semibold text-slate-900">{Math.min((validCurrentPage - 1) * pageSize + 1, filteredReports.length)}</span>
                -
                <span className="font-semibold text-slate-900">{Math.min(validCurrentPage * pageSize, filteredReports.length)}</span>건 표시
                (페이지 <strong className="text-slate-900 font-bold">{validCurrentPage}</strong> / {totalPages})
              </div>

              {totalPages > 1 && (
                <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="페이지 선택">
                  {totalPages > 5 && (
                    <button
                      type="button"
                      onClick={() => setCurrentPage(1)}
                      disabled={validCurrentPage === 1}
                      aria-label="첫 페이지로 이동"
                      className="px-2.5 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-xl text-xs font-semibold border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition focus:outline-none focus:ring-2 focus:ring-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
                    >
                      <span aria-hidden="true">&laquo;</span>
                      <span className="sr-only">첫 페이지로 이동</span>
                    </button>
                  )}

                  <button
                    type="button"
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    disabled={validCurrentPage === 1}
                    aria-label="이전 페이지로 이동"
                    className="px-3 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-xl text-xs font-semibold border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition focus:outline-none focus:ring-2 focus:ring-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
                  >
                    <span aria-hidden="true">&larr;</span>
                    <span className="ml-1">이전</span>
                  </button>

                  {getPaginationItems(validCurrentPage, totalPages).map((pageNum, idx) => {
                    if (pageNum === '...') {
                      return (
                        <span key={`ellipsis-${idx}`} className="px-2 py-1 text-slate-600 select-none text-xs" aria-hidden="true">
                          …
                        </span>
                      );
                    }
                    const isCurrent = validCurrentPage === pageNum;
                    return (
                      <button
                        key={`page-${pageNum}`}
                        type="button"
                        onClick={() => setCurrentPage(pageNum as number)}
                        aria-current={isCurrent ? 'page' : undefined}
                        aria-label={isCurrent ? `현재 ${pageNum}페이지` : `${pageNum}페이지로 이동`}
                        className={`min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-xl text-xs font-bold transition focus:outline-none focus:ring-2 focus:ring-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 ${
                          isCurrent
                            ? 'bg-slate-900 text-white shadow-sm ring-1 ring-slate-800'
                            : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-100'
                        }`}
                      >
                        {pageNum}
                      </button>
                    );
                  })}

                  <button
                    type="button"
                    onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                    disabled={validCurrentPage === totalPages}
                    aria-label="다음 페이지로 이동"
                    className="px-3 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-xl text-xs font-semibold border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition focus:outline-none focus:ring-2 focus:ring-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
                  >
                    <span className="mr-1">다음</span>
                    <span aria-hidden="true">&rarr;</span>
                  </button>

                  {totalPages > 5 && (
                    <button
                      type="button"
                      onClick={() => setCurrentPage(totalPages)}
                      disabled={validCurrentPage === totalPages}
                      aria-label="마지막 페이지로 이동"
                      className="px-2.5 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-xl text-xs font-semibold border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition focus:outline-none focus:ring-2 focus:ring-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
                    >
                      <span className="sr-only">마지막 페이지로 이동</span>
                      <span aria-hidden="true">&raquo;</span>
                    </button>
                  )}
                </div>
              )}
            </nav>
          </section>
        )}
      </div>

      {/* Accessible Detail Modal Dialog for Admin Defect Inspection */}
      {activeModalReport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 overflow-y-auto">
          {/* Backdrop overlay */}
          <div
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm"
            aria-hidden="true"
            onClick={handleCloseModal}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="defect-modal-title"
            aria-describedby="defect-modal-desc"
            ref={modalRef}
            onKeyDown={handleModalKeyDown}
            className="bg-white rounded-3xl max-w-2xl w-full max-h-[calc(100vh-2rem)] overflow-y-auto p-6 sm:p-8 shadow-2xl border border-slate-200 space-y-6 relative focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 my-4 sm:my-8 z-10"
            tabIndex={-1}
          >
            {/* Modal Header */}
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-bold border ${getCategoryBadgeClass(
                      activeModalReport.defect_category
                    )}`}
                  >
                    {activeModalReport.defect_category_ko}
                  </span>
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-bold bg-slate-900 text-white">
                    {activeModalReport.vehicle_model}
                  </span>
                  {getSeverityBadge(activeModalReport.severity)}
                </div>
                <h2 id="defect-modal-title" className="text-xl font-extrabold text-slate-900 mt-2 break-words">
                  {activeModalReport.title}
                </h2>
              </div>

              <button
                ref={closeButtonRef}
                type="button"
                onClick={handleCloseModal}
                aria-label="결함 상세 대화상자 닫기"
                className="p-2 min-w-[44px] min-h-[44px] rounded-xl text-slate-700 hover:text-slate-900 hover:bg-slate-100 flex items-center justify-center transition focus:outline-none focus:ring-2 focus:ring-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
              >
                <svg className="w-5 h-5" width="20" height="20" focusable="false" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Modal Description & Content */}
            <div id="defect-modal-desc" className="space-y-4">
              <div>
                <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">결함 상세 요약</h3>
                <p className="text-sm text-slate-800 leading-relaxed bg-slate-50 p-3.5 rounded-xl border border-slate-200 break-words">
                  {activeModalReport.summary}
                </p>
              </div>

              <div>
                <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">실차주 원문 코멘트</h3>
                <blockquote className="text-xs text-slate-700 italic border-l-2 border-slate-300 pl-3 py-1 bg-slate-50/50 rounded-r-xl whitespace-pre-line break-words">
                  &ldquo;{activeModalReport.verbatim_quote}&rdquo;
                </blockquote>
              </div>

              {/* DSI Breakdown Grid */}
              <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200 space-y-3">
                <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                  <svg className="w-4 h-4 text-blue-600" width="16" height="16" focusable="false" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  DSI 다면 결함 심각도 지표 (Defect Severity Index)
                </h3>
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-center text-xs">
                  <div className="bg-white p-2.5 rounded-xl border border-slate-200">
                    <span className="block text-slate-700 text-[11px] font-medium">안전성</span>
                    <span className="font-extrabold text-slate-900 text-sm">{activeModalReport.dsi_breakdown?.safety ?? 0}</span>
                  </div>
                  <div className="bg-white p-2.5 rounded-xl border border-slate-200">
                    <span className="block text-slate-700 text-[11px] font-medium">기능성</span>
                    <span className="font-extrabold text-slate-900 text-sm">{activeModalReport.dsi_breakdown?.functional ?? 0}</span>
                  </div>
                  <div className="bg-white p-2.5 rounded-xl border border-slate-200">
                    <span className="block text-slate-700 text-[11px] font-medium">경제성</span>
                    <span className="font-extrabold text-slate-900 text-sm">{activeModalReport.dsi_breakdown?.economic ?? 0}</span>
                  </div>
                  <div className="bg-white p-2.5 rounded-xl border border-slate-200">
                    <span className="block text-slate-700 text-[11px] font-medium">사회성</span>
                    <span className="font-extrabold text-slate-900 text-sm">{activeModalReport.dsi_breakdown?.social ?? 0}</span>
                  </div>
                  <div className="bg-white p-2.5 rounded-xl border border-slate-200 col-span-2 sm:col-span-1">
                    <span className="block text-slate-700 text-[11px] font-medium">편의성</span>
                    <span className="font-extrabold text-slate-900 text-sm">{activeModalReport.dsi_breakdown?.convenience ?? 0}</span>
                  </div>
                </div>
              </div>

              {/* Telemetry Details */}
              <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-700 pt-2 border-t border-slate-100">
                <div>
                  <span>작성자: </span>
                  <strong className="text-slate-800">{activeModalReport.author || '익명 제보자'}</strong>
                </div>
                <div>
                  <span>수집 일자: </span>
                  <strong className="text-slate-800 font-mono">{activeModalReport.date}</strong>
                </div>
                <div>
                  <span>부정 감성 지수: </span>
                  <strong className="text-rose-700 font-mono">{formatSentimentPercent(activeModalReport.sentiment_score)}%</strong>
                </div>
              </div>
            </div>

            {/* Modal Actions */}
            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={handleCloseModal}
                className="px-4 py-2 min-h-[44px] rounded-xl text-xs font-semibold text-slate-800 bg-slate-100 hover:bg-slate-200 transition focus:outline-none focus:ring-2 focus:ring-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
              >
                닫기 (Esc)
              </button>
              {(() => {
                const safeModalUrl = sanitizeReportUrl(activeModalReport.url);
                const isExt = isExternalUrl(safeModalUrl);
                if (!isExt) return null;
                return (
                  <a
                    href={safeModalUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={`'${activeModalReport.title}' 원문 게시물 바로가기 (새 창에서 열림)`}
                    className="px-4 py-2 min-h-[44px] inline-flex items-center gap-1.5 rounded-xl text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 transition focus:outline-none focus:ring-2 focus:ring-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
                  >
                    <span>원문 링크 바로가기</span>
                    <span className="sr-only"> (새 창에서 열림)</span>
                    <svg className="w-3.5 h-3.5" width="14" height="14" focusable="false" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                  </a>
                );
              })()}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

interface DefectReportCardProps {
  report: DefectReportWithTimestamp;
  onTagClick: (tag: unknown) => void;
  onOpenModal: (report: DefectReportWithTimestamp, triggerEl?: HTMLButtonElement) => void;
}

const DefectReportCard = memo(function DefectReportCard({
  report,
  onTagClick,
  onOpenModal,
}: DefectReportCardProps) {
  const safeSentimentPct = formatSentimentPercent(report.sentiment_score);
  const safeUrl = sanitizeReportUrl(report.url);
  const isExternal = isExternalUrl(safeUrl);

  const handleOpenModalClick = useCallback((e: React.MouseEvent<HTMLButtonElement>) => {
    onOpenModal(report, e.currentTarget);
  }, [onOpenModal, report]);

  return (
    <div className="bg-white rounded-2xl p-5 md:p-6 border border-slate-200 shadow-sm hover:shadow-md transition space-y-4">
      {/* Header Badges Row */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          {/* Category Badge */}
          <span
            role="status"
            aria-label={`결함 분류: ${report.defect_category_ko}`}
            className={`inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-bold border ${getCategoryBadgeClass(
              report.defect_category
            )}`}
          >
            {report.defect_category_ko}
          </span>

          {/* Vehicle Model Pill */}
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-bold bg-slate-900 text-white">
            {report.vehicle_model}
          </span>

          {/* Severity Badge */}
          {getSeverityBadge(report.severity)}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Detailed Inspection Modal Trigger */}
          <button
            type="button"
            aria-haspopup="dialog"
            aria-label={`제보 #${report.id} (${report.vehicle_model}) 결함 심층 분석 및 DSI 지표 모달 열기`}
            onClick={handleOpenModalClick}
            className="px-2.5 py-1.5 min-h-[44px] inline-flex items-center gap-1 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-200 transition focus:outline-none focus:ring-2 focus:ring-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1"
            title="결함 상세 분석 및 DSI 지표 모달 열기"
          >
            <svg className="w-3.5 h-3.5 text-slate-600" width="14" height="14" focusable="false" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
            <span>심층 분석</span>
          </button>

          {/* Community Source Badge with URL Link */}
          {getSourceBadge(report.source || 'N/A', safeUrl)}

          {/* Date */}
          <span className="text-xs text-slate-800 font-mono font-medium">{report.date}</span>
        </div>
      </div>

      {/* Title */}
      <div>
        <h3 className="text-base md:text-lg font-extrabold text-slate-900 transition break-words">
          {isExternal ? (
            <a
              href={safeUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:underline hover:text-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded inline-flex items-center py-2 min-h-[44px]"
            >
              {report.title}
              <span className="sr-only"> (새 창에서 열림)</span>
            </a>
          ) : (
            <span className="text-slate-900">{report.title}</span>
          )}
        </h3>
      </div>

      {/* Defect Summary */}
      <p className="text-sm text-slate-800 leading-relaxed font-medium bg-slate-50/70 p-3.5 rounded-xl border border-slate-200 break-words">
        {report.summary}
      </p>

      {/* Verbatim Quote */}
      <div className="relative pl-4 border-l-2 border-slate-400 text-xs text-slate-800 italic whitespace-pre-line break-words">
        <span className="text-slate-800 font-serif text-sm mr-1">&ldquo;</span>
        {report.verbatim_quote}
        <span className="text-slate-800 font-serif text-sm ml-1">&rdquo;</span>
      </div>

      {/* Footer Details: Slang Tags & Sentiment Meter */}
      <div className="pt-2 border-t border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
        {/* Slang Keywords */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-slate-800 font-medium">탐지 키워드:</span>
          {(report.slang_tags || []).length === 0 ? (
            <span className="text-slate-600">없음</span>
          ) : (
            (report.slang_tags || []).map((tag, idx) => {
              const tagStr = String(tag);
              return (
                <button
                  type="button"
                  key={`tag-${idx}-${tagStr}`}
                  onClick={() => onTagClick(tagStr)}
                  aria-label={`'${tagStr}' 키워드로 검색 필터링`}
                  className="px-2.5 py-1 min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-full bg-slate-100 text-slate-800 text-[11px] font-semibold border border-slate-200 hover:bg-blue-50 hover:text-blue-800 hover:border-blue-300 transition cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1"
                  title={`'${tagStr}' 키워드로 검색 필터링`}
                >
                  #{tagStr}
                </button>
              );
            })
          )}
        </div>

        {/* Sentiment Meter */}
        <div className="flex items-center gap-2 sm:self-end">
          <span className="text-slate-800 font-medium">부정 감성 강도:</span>
          <div
            role="progressbar"
            aria-valuenow={safeSentimentPct}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`리포트 ${report.id} 부정 감성 강도`}
            aria-valuetext={`${safeSentimentPct}% (${safeSentimentPct >= 80 ? '극도 부정' : safeSentimentPct >= 60 ? '높음' : safeSentimentPct >= 40 ? '보통' : '낮음'})`}
            className="w-24 bg-slate-200 rounded-full h-2 overflow-hidden border border-slate-300"
          >
            <div
              className={`h-2 rounded-full ${
                safeSentimentPct >= 80
                  ? 'bg-rose-700'
                  : safeSentimentPct >= 60
                  ? 'bg-orange-600'
                  : safeSentimentPct >= 40
                  ? 'bg-amber-500'
                  : 'bg-emerald-600'
              }`}
              style={{ width: `${safeSentimentPct}%` }}
            />
          </div>
          <span className="font-bold text-rose-700 font-mono" aria-hidden="true">
            {safeSentimentPct}%
          </span>
          <span className="text-[11px] font-semibold px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200" aria-hidden="true">
            {safeSentimentPct >= 80 ? '극도 부정' : safeSentimentPct >= 60 ? '높음' : safeSentimentPct >= 40 ? '보통' : '낮음'}
          </span>
        </div>
      </div>
    </div>
  );
});
