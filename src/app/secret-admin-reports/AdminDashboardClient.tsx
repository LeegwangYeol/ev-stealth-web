"use client";

import React, { useState, useMemo, useDeferredValue, useCallback, useRef, useEffect, memo } from 'react';
import {
  sanitizeReportUrl,
  getSafeSentimentScore,
  getFallbackReportData,
  type DailyReportData,
  type DefectReportItem,
} from '@/lib/getDailyReports';
import { isExternalUrl, safeJsonParse } from '@/lib/sanitizeUrl';
import ClientTimestamp from '@/components/ClientTimestamp';

export function formatSentimentPercent(score: unknown): number {
  const safe = getSafeSentimentScore(score, 0);
  return Math.min(100, Math.max(0, Math.round(safe * 100)));
}

/**
 * Cross-browser safe date parser compatible with Safari/WebKit, ISO timestamps, and dot-separated Korean dates.
 */
export function parseSafeDate(rawDate?: string): number {
  if (!rawDate || typeof rawDate !== 'string') return 0;
  const trimmed = rawDate.trim();
  if (!trimmed) return 0;

  // 1. Cross-browser normalizer: replace dots and slashes with hyphens (e.g. 2026.09.08 -> 2026-09-08)
  const normalized = trimmed.replace(/\./g, '-').replace(/\//g, '-');

  // 2. Date-only format "YYYY-MM-DD" -> parse consistently as UTC midnight across all browsers
  if (/^\d{4}-\d{2}-\d{2}$/.test(normalized)) {
    const timestamp = new Date(`${normalized}T00:00:00Z`).getTime();
    if (Number.isFinite(timestamp) && timestamp > 0) return timestamp;
  }

  // 3. Normalize "YYYY-MM-DD HH:mm:ss" -> ISO format
  if (/^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}/.test(normalized)) {
    const isoLike = normalized.replace(/\s+/, 'T') + (normalized.includes('+') || normalized.endsWith('Z') ? '' : 'Z');
    const timestamp = new Date(isoLike).getTime();
    if (Number.isFinite(timestamp) && timestamp > 0) return timestamp;
  }

  // 4. Full ISO 8601 strings or standard date fallback
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
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-700 text-white shadow-sm ring-1 ring-rose-600">
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
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-orange-700 text-white shadow-sm ring-1 ring-orange-600">
        높음 (HIGH)
      </span>
    );
  }
  if (sev === 'WARNING') {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-400 text-slate-950 border border-amber-500 shadow-sm">
        경고 (WARNING)
      </span>
    );
  }
  if (sev === 'MEDIUM') {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-950 border border-amber-400 shadow-sm">
        주의 (MEDIUM)
      </span>
    );
  }
  if (sev === 'LOW') {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-950 border border-emerald-300 shadow-sm">
        낮음 (LOW)
      </span>
    );
  }
  if (sev === 'INFO') {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-100 text-slate-900 border border-slate-300 shadow-sm">
        안정 (INFO)
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-950 border border-amber-300 shadow-sm">
      주의 (CAUTION)
    </span>
  );
}

function getSourceBadge(source: string, url: string) {
  const isBobae = (source || '').toLowerCase().includes('bobae');
  const badgeText = isBobae ? '보배드림' : '디시인사이드';
  const badgeColor = isBobae
    ? 'bg-blue-50 text-blue-900 border-blue-200 hover:bg-blue-100'
    : 'bg-indigo-50 text-indigo-900 border-indigo-200 hover:bg-indigo-100';

  const safeUrl = sanitizeReportUrl(url);
  const isExternal = safeUrl.startsWith('http://') || safeUrl.startsWith('https://');

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
      className={`inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-md border font-semibold transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${badgeColor}`}
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
  const deferredSearchQuery = useDeferredValue(searchQuery);
  const [selectedCategory, setSelectedCategory] = useState('ALL');
  const [selectedSource, setSelectedSource] = useState('all');
  const [sortBy, setSortBy] = useState<SortOption>('critical');
  const [viewMode, setViewMode] = useState<ViewMode>('cards');
  const [pageSize, setPageSize] = useState<number>(10);

  // Accessible Modal Dialog State & Focus Management
  const [activeModalReport, setActiveModalReport] = useState<DefectReportWithTimestamp | null>(null);
  const triggerButtonRef = useRef<HTMLButtonElement | null>(null);
  const modalRef = useRef<HTMLDivElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  const handleOpenModal = useCallback((report: DefectReportWithTimestamp, triggerEl?: HTMLButtonElement) => {
    if (triggerEl) {
      triggerButtonRef.current = triggerEl;
    }
    setActiveModalReport(report);
  }, []);

  const handleCloseModal = useCallback(() => {
    setActiveModalReport(null);
    // Keyboard accessibility: return focus to the trigger element that opened the dialog
    setTimeout(() => {
      triggerButtonRef.current?.focus();
    }, 0);
  }, []);

  // Window-level Escape key listener to close modal from anywhere in the document
  useEffect(() => {
    if (!activeModalReport) return;

    const handleWindowKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        handleCloseModal();
      }
    };

    window.addEventListener('keydown', handleWindowKeyDown);
    return () => {
      window.removeEventListener('keydown', handleWindowKeyDown);
    };
  }, [activeModalReport, handleCloseModal]);

  // Trap focus inside modal & keyboard dismissibility
  const handleModalKeyDown = useCallback((e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      handleCloseModal();
      return;
    }

    if (e.key === 'Tab' && modalRef.current) {
      const focusableElements = modalRef.current.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      );
      if (focusableElements.length === 0) return;

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === firstElement || !modalRef.current.contains(document.activeElement)) {
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

  const reports = useMemo<DefectReportWithTimestamp[]>(() => {
    const rawList = Array.isArray(safeData?.reports) ? safeData.reports : [];
    return rawList
      .filter((r): r is AdminDefectReportItem => Boolean(r && typeof r === 'object'))
      .map((r, idx) => {
        const rawDate = r.created_at || r.date;
        const parsed = parseSafeDate(rawDate);
        const catCode = r.defect_category || 'BATTERY_CHARGING';
        const catKo = r.defect_category_ko || '기타 결함';

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
          .map((t) => t.trim());

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

        const searchTokens = [
          r.title || '',
          r.summary || '',
          r.verbatim_quote || '',
          r.vehicle_model || '',
          r.vehicle_brand || '',
          r.author || '',
          r.id ? String(r.id) : '',
          catKo,
          ...slangList,
        ];
        const searchIndex = searchTokens.join(' ').toLowerCase();
        const spacelessIndex = searchIndex.replace(/\s+/g, '');

        // Standardize clean display date YYYY-MM-DD
        const displayDate = r.date
          ? r.date.replace(/[./]/g, '-')
          : (r.created_at ? r.created_at.slice(0, 10).replace(/[./]/g, '-') : '2026-09-30');

        return {
          ...r,
          id: r.id ? String(r.id) : `report_${idx + 1}`,
          date: displayDate,
          source: (r.source || '').toLowerCase() || 'bobaedream',
          url: sanitizeReportUrl(r.url),
          defect_category: catCode,
          defect_category_ko: catKo,
          vehicle_model: r.vehicle_model || '미상 모델',
          title: r.title || '전기차 결함 제보',
          summary: r.summary || '결함 상세 내용 요약',
          verbatim_quote: r.verbatim_quote || '원문 없음',
          slang_tags: slangList,
          dsi_breakdown: safeDsi,
          sentiment_score: getSafeSentimentScore(r.sentiment_score, 0.85),
          severity: r.severity || 'WARNING',
          _timestamp: Number.isFinite(parsed) ? parsed : 0,
          _searchIndex: searchIndex,
          _spacelessIndex: spacelessIndex,
        };
      });
  }, [safeData?.reports]);

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

    return {
      total_scraped: totalScraped,
      total_filtered_defects: totalFiltered,
      avg_negativity_score: avgScore,
      critical_defect_count: criticalCount,
      top_model: rawStats?.top_model || (reports.length > 0 ? '아이오닉5' : '해당 없음 (0건)'),
      top_platform: rawStats?.top_platform || (reports.length > 0 ? '보배드림' : '해당 없음 (0%)'),
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

  // Filtered and sorted reports with fast precomputed index and optimized tokenization
  const filteredReports = useMemo(() => {
    const rawQuery = deferredSearchQuery.trim().toLowerCase().slice(0, 200);

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
            report.defect_category_ko ===
              CATEGORY_TABS.find((c) => c.code === selectedCategory)?.label;
          if (!catMatch) return false;
        }

        // Source filter
        if (selectedSource !== 'all') {
          if ((report.source || '').toLowerCase() !== selectedSource.toLowerCase()) {
            return false;
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
          return b._timestamp - a._timestamp;
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
          return (b.sentiment_score || 0) - (a.sentiment_score || 0);
        }

        if (sortBy === 'negativity') {
          if ((b.sentiment_score || 0) !== (a.sentiment_score || 0)) {
            return (b.sentiment_score || 0) - (a.sentiment_score || 0);
          }
          return b._timestamp - a._timestamp;
        }

        return 0;
      });
  }, [reports, selectedCategory, selectedSource, deferredSearchQuery, sortBy]);

  // Pagination State (WCAG AA Compliant Navigation)
  const [currentPage, setCurrentPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(filteredReports.length / pageSize));

  // Auto-reset to first page when filtering, sorting, or page size changes
  useEffect(() => {
    setCurrentPage(1);
  }, [selectedCategory, selectedSource, deferredSearchQuery, sortBy, pageSize]);

  // Ensure current page bounds
  const validCurrentPage = Math.min(currentPage, totalPages);

  const paginatedReports = useMemo(() => {
    const start = (validCurrentPage - 1) * pageSize;
    return filteredReports.slice(start, start + pageSize);
  }, [filteredReports, validCurrentPage, pageSize]);

  const handleResetFilters = useCallback(() => {
    setSearchQuery('');
    setSelectedCategory('ALL');
    setSelectedSource('all');
    setSortBy('critical');
    setCurrentPage(1);
    searchInputRef.current?.focus();
  }, []);

  const handleClearSearch = useCallback(() => {
    setSearchQuery('');
    searchInputRef.current?.focus();
  }, []);

  const handleTagClick = useCallback((tag: unknown) => {
    if (typeof tag !== 'string') return;
    const clean = tag.replace(/^[#\s]+/, '').trim().slice(0, 50);
    setSearchQuery(clean);
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
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/20 text-amber-300 border border-amber-500/30">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400" aria-hidden="true" />
                  데이터 동기화 대기 중
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping motion-reduce:animate-none" aria-hidden="true" />
                  파이프라인 정상 가동
                </span>
              )}
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
              유효율 {Math.round((statistics.total_filtered_defects / Math.max(statistics.total_scraped || 0, 1)) * 100)}%
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
              className="w-full pl-10 pr-10 py-2.5 min-h-[44px] text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus:bg-white transition placeholder-slate-600"
            />
            <span id="admin-defect-search-hint" className="sr-only">
              검색어를 입력하면 실시간으로 목록이 필터링됩니다. ESC 키를 누르면 입력한 검색어가 초기화됩니다.
            </span>
            {searchQuery && (
              <button
                type="button"
                onClick={handleClearSearch}
                className="absolute inset-y-0 right-0 pr-3 min-w-[44px] min-h-[44px] flex items-center justify-center text-slate-700 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
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
                  className={`px-3 py-1.5 min-h-[44px] inline-flex items-center rounded-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                    sortBy === 'critical'
                      ? 'bg-white text-rose-700 font-semibold shadow-sm'
                      : 'text-slate-700 hover:text-slate-900'
                  }`}
                >
                  치명도순
                </button>
                <button
                  type="button"
                  aria-pressed={sortBy === 'recent'}
                  onClick={() => setSortBy('recent')}
                  className={`px-3 py-1.5 min-h-[44px] inline-flex items-center rounded-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                    sortBy === 'recent'
                      ? 'bg-white text-blue-700 font-semibold shadow-sm'
                      : 'text-slate-700 hover:text-slate-900'
                  }`}
                >
                  최신수집순
                </button>
                <button
                  type="button"
                  aria-pressed={sortBy === 'negativity'}
                  onClick={() => setSortBy('negativity')}
                  className={`px-3 py-1.5 min-h-[44px] inline-flex items-center rounded-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                    sortBy === 'negativity'
                      ? 'bg-white text-amber-800 shadow-sm'
                      : 'text-slate-700 hover:text-slate-900'
                  }`}
                >
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
                  className={`px-2.5 py-1.5 min-h-[44px] inline-flex items-center gap-1 rounded-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                    viewMode === 'cards'
                      ? 'bg-white text-slate-900 shadow-sm font-bold'
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
                  className={`px-2.5 py-1.5 min-h-[44px] inline-flex items-center gap-1 rounded-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                    viewMode === 'table'
                      ? 'bg-white text-slate-900 shadow-sm font-bold'
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
                onChange={(e) => setPageSize(Number(e.target.value))}
                className="min-h-[44px] px-2 py-1.5 bg-slate-100 text-slate-800 rounded-xl border border-slate-200 font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 cursor-pointer"
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
                onKeyDown={(e) => handleCategoryKeyDown(e, idx)}
                onClick={() => setSelectedCategory(tab.code)}
                className={`px-3 py-2 min-h-[44px] rounded-xl font-semibold whitespace-nowrap transition flex items-center gap-1.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                  isSelected
                    ? 'bg-slate-900 text-white shadow-sm'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200 hover:text-slate-900'
                }`}
              >
                <span>{tab.label}</span>
                <span
                  className={`text-[11px] px-1.5 py-0.2 rounded-full ${
                    isSelected ? 'bg-slate-700 text-slate-200' : 'bg-slate-200 text-slate-700'
                  }`}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Community Source Selector Badges */}
        <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-100 text-xs">
          <div role="group" aria-label="출처 플랫폼 필터" className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-slate-700">출처 플랫폼:</span>
            <div className="flex flex-wrap items-center gap-1.5">
              {SOURCE_OPTIONS.map((src) => {
                const isSelected = selectedSource === src.id;
                const count = sourceCounts[src.id] || 0;
                return (
                  <button
                    key={src.id}
                    type="button"
                    aria-pressed={isSelected}
                    onClick={() => setSelectedSource(src.id)}
                    className={`px-2.5 py-1 min-h-[44px] rounded-lg font-medium transition flex items-center gap-1 border focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                      isSelected
                        ? 'bg-blue-600 text-white border-blue-600 shadow-sm'
                        : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
                    }`}
                  >
                    <span>{src.label}</span>
                    <span
                      className={`text-[10px] px-1 rounded ${
                        isSelected ? 'bg-blue-700 text-blue-100' : 'bg-slate-100 text-slate-700'
                      }`}
                    >
                      {count}
                    </span>
                  </button>
                );
              })}
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
            </span>
            {(searchQuery || selectedCategory !== 'ALL' || selectedSource !== 'all') && (
              <button
                type="button"
                onClick={handleResetFilters}
                aria-label="모든 검색 및 카테고리 필터 초기화"
                className="text-xs text-rose-600 hover:text-rose-700 font-semibold underline min-h-[44px] inline-flex items-center gap-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-500 rounded px-1"
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
          {selectedCategory !== 'ALL' || searchQuery || selectedSource !== 'all'
            ? `필터링된 결과: 총 ${filteredReports.length}건의 결함 제보`
            : `전체 수집된 결함 제보: 총 ${filteredReports.length}건`}
        </div>

        {/* Screen Reader Accessible Summary Table for Defect Reports (always present for screen readers) */}
        <div className={viewMode === 'table' ? 'overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm' : 'sr-only'} tabIndex={viewMode === 'table' ? 0 : undefined} role={viewMode === 'table' ? 'region' : undefined} aria-label={viewMode === 'table' ? '결함 제보 요약 데이터 테이블' : undefined}>
          <table aria-label="수집된 전기차 결함 제보 데이터 요약 표" className="w-full text-left text-xs text-slate-800 border-collapse">
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
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold border ${getCategoryBadgeClass(report.defect_category)}`}>
                          {report.defect_category_ko}
                        </span>
                      </td>
                      <td className="px-3 py-3 whitespace-nowrap">{getSeverityBadge(report.severity)}</td>
                      <td className="px-3 py-3 whitespace-nowrap">{getSourceBadge(report.source || 'N/A', report.url)}</td>
                      <td className="px-3 py-3 text-slate-900 font-medium max-w-xs truncate" title={report.title}>
                        <span>{report.title}</span>
                        {isExt ? (
                          <a
                            href={report.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            aria-label="게시글 원문 보기"
                            title="게시글 원문 보기 (새 창에서 열림)"
                            className="focus:inline-block focus:px-2 focus:py-0.5 focus:bg-blue-700 focus:text-white focus:rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ml-1 text-blue-700 underline text-xs font-semibold"
                          >
                            (원문 링크)
                          </a>
                        ) : (
                          <span className="text-slate-600 ml-1 text-xs">(원문 링크 없음)</span>
                        )}
                      </td>
                      <td className="px-3 py-3 text-slate-800 text-xs max-w-sm truncate" title={report.summary}>
                        {report.summary}
                      </td>
                      <td className="px-3 py-3 whitespace-nowrap font-mono font-bold text-rose-700 text-xs">
                        {formatSentimentPercent(report.sentiment_score)}%
                      </td>
                      {viewMode === 'table' && (
                        <td className="px-3 py-3 whitespace-nowrap text-right">
                          <button
                            type="button"
                            aria-haspopup="dialog"
                            aria-label={`제보 #${overallIdx} (${report.vehicle_model}) 결함 상세 분석 및 DSI 지표 모달 열기`}
                            onClick={(e) => handleOpenModal(report, e.currentTarget)}
                            className="px-2.5 py-1 min-h-[44px] inline-flex items-center gap-1 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-200 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
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
              className="mt-2 inline-flex items-center gap-1 px-4 py-2 min-h-[44px] rounded-xl text-xs font-semibold bg-slate-900 text-white hover:bg-slate-800 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
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
                  <button
                    type="button"
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    disabled={validCurrentPage === 1}
                    aria-label="이전 페이지로 이동"
                    className="px-3 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-xl text-xs font-semibold border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
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
                        aria-label={`${pageNum}페이지로 이동`}
                        className={`min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-xl text-xs font-bold transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
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
                    className="px-3 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-xl text-xs font-semibold border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                  >
                    <span className="mr-1">다음</span>
                    <span aria-hidden="true">&rarr;</span>
                  </button>
                </div>
              )}
            </nav>
          </section>
        )}
      </div>

      {/* Accessible Detail Modal Dialog for Admin Defect Inspection */}
      {activeModalReport && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm overflow-y-auto"
          onClick={handleCloseModal}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="defect-modal-title"
            aria-describedby="defect-modal-desc"
            ref={modalRef}
            onKeyDown={handleModalKeyDown}
            onClick={(e) => e.stopPropagation()}
            className="bg-white rounded-3xl max-w-2xl w-full p-6 sm:p-8 shadow-2xl border border-slate-200 space-y-6 relative focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 my-8"
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
                <h2 id="defect-modal-title" className="text-xl font-extrabold text-slate-900 mt-2">
                  {activeModalReport.title}
                </h2>
              </div>

              <button
                ref={closeButtonRef}
                type="button"
                onClick={handleCloseModal}
                aria-label="결함 상세 대화상자 닫기"
                className="p-2 min-w-[44px] min-h-[44px] rounded-xl text-slate-700 hover:text-slate-900 hover:bg-slate-100 flex items-center justify-center transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
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
                <p className="text-sm text-slate-800 leading-relaxed bg-slate-50 p-3.5 rounded-xl border border-slate-200">
                  {activeModalReport.summary}
                </p>
              </div>

              <div>
                <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">실차주 원문 코멘트</h3>
                <blockquote className="text-xs text-slate-700 italic border-l-2 border-slate-300 pl-3 py-1 bg-slate-50/50 rounded-r-xl">
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
                  <div className="bg-white p-2.5 rounded-xl border border-slate-200">
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
                className="px-4 py-2 min-h-[44px] rounded-xl text-xs font-semibold text-slate-800 bg-slate-100 hover:bg-slate-200 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              >
                닫기 (Esc)
              </button>
              {(() => {
                const safeModalUrl = sanitizeReportUrl(activeModalReport.url);
                const isExt = safeModalUrl.startsWith('http://') || safeModalUrl.startsWith('https://');
                if (!isExt) return null;
                return (
                  <a
                    href={safeModalUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={`'${activeModalReport.title}' 원문 게시물 바로가기 (새 창에서 열림)`}
                    className="px-4 py-2 min-h-[44px] inline-flex items-center gap-1.5 rounded-xl text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
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
  const isExternal = safeUrl.startsWith('http://') || safeUrl.startsWith('https://');

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

        <div className="flex items-center gap-2">
          {/* Detailed Inspection Modal Trigger */}
          <button
            type="button"
            aria-haspopup="dialog"
            onClick={handleOpenModalClick}
            className="px-2.5 py-1.5 min-h-[44px] inline-flex items-center gap-1 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-200 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            title="결함 상세 분석 및 DSI 지표 모달 열기"
          >
            <svg className="w-3.5 h-3.5 text-slate-600" width="14" height="14" focusable="false" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
            <span>심층 분석</span>
          </button>

          {/* Community Source Badge with URL Link */}
          {getSourceBadge(report.source || 'N/A', report.url)}

          {/* Date */}
          <span className="text-xs text-slate-800 font-mono font-medium">{report.date}</span>
        </div>
      </div>

      {/* Title */}
      <div>
        <h3 className="text-base md:text-lg font-extrabold text-slate-900 transition">
          {isExternal ? (
            <a
              href={safeUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:underline hover:text-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
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
      <p className="text-sm text-slate-800 leading-relaxed font-medium bg-slate-50/70 p-3.5 rounded-xl border border-slate-200">
        {report.summary}
      </p>

      {/* Verbatim Quote */}
      <div className="relative pl-4 border-l-2 border-slate-400 text-xs text-slate-800 italic">
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
                  className="px-2.5 py-1 min-h-[44px] inline-flex items-center rounded-full bg-slate-100 text-slate-800 text-[11px] font-semibold border border-slate-200 hover:bg-blue-50 hover:text-blue-800 hover:border-blue-300 transition cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
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
            aria-valuetext={`${safeSentimentPct}%`}
            className="w-24 bg-slate-200 rounded-full h-2 overflow-hidden border border-slate-300"
          >
            <div
              className="bg-rose-700 h-2 rounded-full"
              style={{ width: `${safeSentimentPct}%` }}
            />
          </div>
          <span className="font-bold text-rose-700 font-mono">
            {safeSentimentPct}%
          </span>
        </div>
      </div>
    </div>
  );
});
