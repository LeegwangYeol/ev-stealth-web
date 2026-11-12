'use client';

import React, { useState, useMemo, useRef, useEffect, useDeferredValue, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { useSearchParams } from 'next/navigation';
import {
  EVSubsidyDataset,
  AlertSeverity,
  AlertThresholdConfig,
  CategoryMetrics,
  SubsidyCalculatorOptions,
  RegionEntry,
  PopularModelEntry,
} from '@/types/subsidy';
import { getRegionById, getModelById } from '@/lib/getSubsidyData';
import { sortRegions, calculateNetSubsidyPure } from '@/lib/subsidyCalculations';
import type { RegionSortOption } from '@/lib/subsidyCalculations';
import ClientTimestamp from '@/components/ClientTimestamp';
import SubsidyErrorBoundary from '@/components/subsidy/SubsidyErrorBoundary';
import SubsidyBadge from '@/components/subsidy/SubsidyBadge';
import SubsidyProgressBar from '@/components/subsidy/SubsidyProgressBar';

// Pure Helper: Badge styling with opaque solid backgrounds for compliant WCAG AA contrast (> 7:1)
export const getBadgeStyle = (status?: AlertSeverity | string | null): string => {
  const normalized = (status || '').toUpperCase();
  switch (normalized) {
    case 'HEALTHY':
    case 'AVAILABLE':
    case 'available':
      return 'bg-emerald-950 text-emerald-200 border-emerald-400';
    case 'CAUTION':
      return 'bg-amber-950 text-amber-200 border-amber-400';
    case 'WARNING':
      return 'bg-orange-950 text-orange-200 border-orange-400';
    case 'CRITICAL':
      return 'bg-rose-950 text-rose-200 border-rose-400 animate-pulse motion-reduce:animate-none';
    case 'DEPLETED':
      return 'bg-slate-950 text-slate-100 border-slate-400';
    default:
      return 'bg-emerald-950 text-emerald-200 border-emerald-400';
  }
};

// Pure Helper: Status badge labels with accessible visual indicator
export const getStatusLabel = (status?: AlertSeverity | string | null): string => {
  const normalized = (status || '').toUpperCase();
  switch (normalized) {
    case 'HEALTHY':
    case 'AVAILABLE':
      return '🟢 안정';
    case 'CAUTION':
      return '🟡 주의';
    case 'WARNING':
      return '🟠 경고';
    case 'CRITICAL':
      return '🔴 마감임박';
    case 'DEPLETED':
      return '🔒 소진';
    default:
      return '🟢 안정';
  }
};

const SubsidyTableView = dynamic(() => import('@/components/subsidy/SubsidyTableView'), {
  ssr: true,
  loading: () => (
    <div
      role="status"
      aria-live="polite"
      className="bg-slate-900 border border-slate-800 rounded-2xl p-12 text-center text-slate-300 animate-pulse motion-reduce:animate-none"
    >
      <div className="text-sm font-semibold text-slate-300">표 형식 데이터를 불러오는 중...</div>
    </div>
  ),
});

const SubsidyFaqAccordion = dynamic(() => import('@/components/subsidy/SubsidyFaqAccordion'), {
  ssr: true,
});

interface SubsidyTrackerClientProps {
  initialData: EVSubsidyDataset;
}

type CategoryType = 'passenger' | 'commercial' | 'bus';
type ZoneFilter = 'ALL' | 'CAPITAL' | 'YEONGNAM' | 'HONAM' | 'CHUNGCHEONG' | 'GANGWON_JEJU';
export type SortOption = RegionSortOption;

const CATEGORY_TABS: { id: CategoryType; label: string; icon: string }[] = [
  { id: 'passenger', label: '전기승용 (승용차)', icon: '🚗' },
  { id: 'commercial', label: '전기화물 (소형/특장)', icon: '🚚' },
  { id: 'bus', label: '전기승합 (버스)', icon: '🚌' },
];

const ZONE_FILTERS: { id: ZoneFilter; label: string }[] = [
  { id: 'ALL', label: '전국 전체' },
  { id: 'CAPITAL', label: '수도권 (서울/경기/인천)' },
  { id: 'YEONGNAM', label: '영남권 (부산/대구/울산/경북/경남)' },
  { id: 'HONAM', label: '호남권 (광주/전남/전북)' },
  { id: 'CHUNGCHEONG', label: '충청권 (대전/세종/충남/충북)' },
  { id: 'GANGWON_JEJU', label: '강원/제주' },
];

const isSortOption = (v: string): v is SortOption =>
  ['DEPLETION_DESC', 'DEPLETION_ASC', 'REMAINING_ASC', 'REMAINING_DESC', 'LOCAL_SUBSIDY_DESC', 'LOCAL_SUBSIDY_ASC', 'NAME_ASC', 'NAME_DESC'].includes(v);

// Hoisted brand regexes to module scope to avoid re-allocating RegExp objects on every render
export const BRAND_PREFIX_REGEX = /^(현대|기아|테슬라|KGM|비야디|BYD)\s+/;

// Pure Helper: Zone categorizer
const getRegionZone = (isoCode: string): ZoneFilter => {
  switch (isoCode) {
    case 'KR-11': // 서울
    case 'KR-41': // 경기
    case 'KR-28': // 인천
      return 'CAPITAL';
    case 'KR-26': // 부산
    case 'KR-27': // 대구
    case 'KR-31': // 울산
    case 'KR-47': // 경북
    case 'KR-48': // 경남
      return 'YEONGNAM';
    case 'KR-29': // 광주
    case 'KR-45': // 전북
    case 'KR-46': // 전남
      return 'HONAM';
    case 'KR-30': // 대전
    case 'KR-36': // 세종
    case 'KR-43': // 충북
    case 'KR-44': // 충남
      return 'CHUNGCHEONG';
    case 'KR-42': // 강원
    case 'KR-49': // 제주
      return 'GANGWON_JEJU';
    default:
      return 'ALL';
  }
};

const FALLBACK_SUMMARY: EVSubsidyDataset['nationwide_summary'] = Object.freeze({
  total_announced_units: 0,
  total_applied_units: 0,
  total_delivered_units: 0,
  total_remaining_units: 0,
  nationwide_depletion_rate: 0,
  total_budget_billion_krw: 0,
  disbursed_budget_billion_krw: 0,
  category_totals: {
    passenger: { announced_units: 0, applied_units: 0, delivered_units: 0, remaining_units: 0, depletion_rate: 0, delivery_rate: 0, status: 'HEALTHY' as AlertSeverity },
    commercial: { announced_units: 0, applied_units: 0, delivered_units: 0, remaining_units: 0, depletion_rate: 0, delivery_rate: 0, status: 'HEALTHY' as AlertSeverity },
    bus: { announced_units: 0, applied_units: 0, delivered_units: 0, remaining_units: 0, depletion_rate: 0, delivery_rate: 0, status: 'HEALTHY' as AlertSeverity },
  },
  alert_region_counts: {
    healthy: 0,
    caution: 0,
    warning: 0,
    critical: 0,
    depleted: 0,
  },
});

const FALLBACK_THRESHOLDS: Record<AlertSeverity, AlertThresholdConfig> = Object.freeze({
  HEALTHY: {
    min_percent: 0.0,
    max_percent: 59.9,
    label_ko: '원활 (신청 여유)',
    severity: 'HEALTHY',
    color_hex: '#10B981',
    badge_class: 'bg-emerald-950 text-emerald-200 border-emerald-400',
    recommended_action: '보조금 잔여량이 충분하여 신청 접수 후 통상 1~2주 내 교부 결정됩니다.',
  },
  CAUTION: {
    min_percent: 60.0,
    max_percent: 79.9,
    label_ko: '주의 (소진 가속)',
    severity: 'CAUTION',
    color_hex: '#F59E0B',
    badge_class: 'bg-amber-950 text-amber-200 border-amber-400',
    recommended_action: '출고 예정 시기가 1~2개월 이내인 경우 조속한 서류 접수를 권장합니다.',
  },
  WARNING: {
    min_percent: 80.0,
    max_percent: 94.9,
    label_ko: '경고 (마감 임박)',
    severity: 'WARNING',
    color_hex: '#F97316',
    badge_class: 'bg-orange-950 text-orange-200 border-orange-400',
    recommended_action: '잔여 예산 소진이 임박했습니다. 즉시 출고 가능한 실재고 매칭이 필요합니다.',
  },
  CRITICAL: {
    min_percent: 95.0,
    max_percent: 99.9,
    label_ko: '위험 (잔여 극소)',
    severity: 'CRITICAL',
    color_hex: '#EF4444',
    badge_class: 'bg-rose-950 text-rose-200 border-rose-400 animate-pulse motion-reduce:animate-none',
    recommended_action: '선착순 마감 직전입니다. 담당 지자체 문의 및 추경 예산 편성 여부를 확인하세요.',
  },
  DEPLETED: {
    min_percent: 100.0,
    max_percent: 999.0,
    label_ko: '마감 (접수 종료)',
    severity: 'DEPLETED',
    color_hex: '#94A3B8',
    badge_class: 'bg-slate-950 text-slate-100 border-slate-400',
    recommended_action: '2026년 공고 예산이 전액 소진되었습니다. 취소분 대기 접수 또는 차년도 사업을 준비하세요.',
  },
});

const FALLBACK_CATEGORY_METRICS: Readonly<CategoryMetrics> = Object.freeze({
  status: 'HEALTHY' as AlertSeverity,
  announced_units: 0,
  applied_units: 0,
  delivered_units: 0,
  remaining_units: 0,
  depletion_rate: 0,
  delivery_rate: 0,
  max_local_subsidy_krw: 0,
  max_total_subsidy_krw: 0,
});

// ============================================================================
// Sub-Component: Memoized Tracker Header Banner & Nationwide Stat Cards
// (Isolated from typing and filter toggles to prevent re-render cascades)
// ============================================================================
interface TrackerHeaderProps {
  summary: EVSubsidyDataset['nationwide_summary'];
  generatedAt?: string;
  criticalRegions: RegionEntry[];
  onSelectCriticalRegion: (nameKo: string, regionId: string) => void;
}

const TrackerHeader = React.memo(function TrackerHeader({
  summary,
  generatedAt,
  criticalRegions,
  onSelectCriticalRegion,
}: TrackerHeaderProps) {
  return (
    <section aria-labelledby="tracker-heading" className="bg-slate-900 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-2xl relative overflow-hidden">
      <div className="absolute top-0 right-0 w-96 h-96 bg-gradient-to-bl from-amber-500/10 via-blue-500/5 to-transparent rounded-full blur-3xl pointer-events-none" />

      <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
        <div className="flex flex-wrap items-center gap-2">
          <span
            role="status"
            aria-label="실시간 스케줄러 동기화 상태: 정상"
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-950 border border-emerald-500/50 text-emerald-300 text-xs font-semibold tracking-wide"
          >
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping motion-reduce:animate-none inline-block" aria-hidden="true" />
            실시간 스케줄러 동기화 완료
          </span>
          <span className="text-xs text-slate-300">
            기준: 2026년 환경부 무공해차 통합누리집 (ev.or.kr)
          </span>
        </div>
        <span className="text-xs text-slate-300">
          데이터 갱신 시각:{' '}
          <ClientTimestamp
            isoString={generatedAt}
            options={{
              month: 'long',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            }}
          />
        </span>
      </div>

      <div className="max-w-3xl space-y-3">
        <h1 id="tracker-heading" className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white flex items-center gap-3">
          <span className="text-amber-400 text-3xl sm:text-4xl" aria-hidden="true">⚡</span>
          전국 지자체별 전기차 실시간 보조금 소진율 추적기
        </h1>
        <p className="text-slate-300 text-sm sm:text-base leading-relaxed">
          전국 17개 광역시도 및 73개 주요 지자체의 <strong>전기승용·화물·승합 공고 쿼터</strong>, 접수·출고 현황, 실시간 소진율을 5단계 경보로 감시합니다. 출고 전 <strong>내 거주지 잔여 예산</strong>을 확인하고 실구매 체감가를 원스톱으로 산출하세요.
        </p>
      </div>

      {/* Live Nationwide Stat Cards - Responsive Grid on Mobile (320px+) & Solid Opaque Backgrounds */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 sm:gap-4 mt-8 pt-6 border-t border-slate-800">
        <div className="bg-slate-950 border border-slate-800 rounded-2xl p-4 flex flex-col justify-between">
          <div className="text-xs font-medium text-slate-300">전국 평균 소진율</div>
          <div className="text-2xl sm:text-3xl font-extrabold text-amber-400 mt-1">
            {(Number.isFinite(summary?.nationwide_depletion_rate) ? summary.nationwide_depletion_rate : 0).toFixed(1)}%
          </div>
          <div className="text-[11px] text-slate-300 mt-1">
            전체 카테고리 종합
          </div>
        </div>

        <div className="bg-slate-950 border border-slate-800 rounded-2xl p-4 flex flex-col justify-between">
          <div className="text-xs font-medium text-slate-300">총 공고 대수</div>
          <div className="text-2xl sm:text-3xl font-extrabold text-slate-100 mt-1">
            {(Number.isFinite(summary?.total_announced_units) ? Math.max(0, summary.total_announced_units) : 0).toLocaleString()}
            <span className="text-xs font-normal text-slate-300 ml-1">대</span>
          </div>
          <div className="text-[11px] text-slate-300 mt-1">
            총 배정 예산 {(Number.isFinite(summary?.total_budget_billion_krw) ? Math.max(0, summary.total_budget_billion_krw) : 0).toLocaleString()}억 원
          </div>
        </div>

        <div className="bg-slate-950 border border-slate-800 rounded-2xl p-4 flex flex-col justify-between">
          <div className="text-xs font-medium text-slate-300">총 접수 대수</div>
          <div className="text-2xl sm:text-3xl font-extrabold text-blue-400 mt-1">
            {(Number.isFinite(summary?.total_applied_units) ? Math.max(0, summary.total_applied_units) : 0).toLocaleString()}
            <span className="text-xs font-normal text-slate-300 ml-1">대</span>
          </div>
          <div className="text-[11px] text-slate-300 mt-1">
            출고 완료: {(Number.isFinite(summary?.total_delivered_units) ? Math.max(0, summary.total_delivered_units) : 0).toLocaleString()}대
          </div>
        </div>

        <div className="bg-slate-950 border border-slate-800 rounded-2xl p-4 flex flex-col justify-between">
          <div className="text-xs font-medium text-slate-300">전국 잔여 대수</div>
          <div className="text-2xl sm:text-3xl font-extrabold text-emerald-400 mt-1">
            {(Number.isFinite(summary?.total_remaining_units) ? Math.max(0, summary.total_remaining_units) : 0).toLocaleString()}
            <span className="text-xs font-normal text-slate-300 ml-1">대</span>
          </div>
          <div className="text-[11px] text-slate-300 mt-1">
            잔여율 {(100 - (Number.isFinite(summary?.nationwide_depletion_rate) ? summary.nationwide_depletion_rate : 0)).toFixed(1)}%
          </div>
        </div>

        <div className="sm:col-span-2 lg:col-span-1 bg-rose-950 border border-rose-500/50 rounded-2xl p-4 flex flex-col justify-between">
          <div className="text-xs font-medium text-rose-300">긴급 마감 위험 지역</div>
          <div className="text-2xl sm:text-3xl font-extrabold text-rose-400 mt-1">
            {(Number.isFinite(summary?.alert_region_counts?.critical) ? summary.alert_region_counts.critical : 0) +
              (Number.isFinite(summary?.alert_region_counts?.depleted) ? summary.alert_region_counts.depleted : 0)}
            <span className="text-xs font-normal text-rose-300 ml-1">개 시도</span>
          </div>
          <div className="text-[11px] text-rose-300 mt-1">
            소진율 95% 이상 극소량
          </div>
        </div>
      </div>

      {/* Emergency Alert Ticker for Critical Municipalities */}
      {criticalRegions.length > 0 && (
        <div
          role="region"
          aria-label="보조금 긴급 소진 주의보"
          className="mt-6 bg-rose-950 border border-rose-500/50 rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs sm:text-sm"
        >
          <div className="flex flex-wrap items-center gap-2 text-rose-200">
            <div role="alert" className="flex items-center gap-1.5">
              <span className="text-base" aria-hidden="true">🚨</span>
              <strong className="text-rose-100 font-semibold">마감 임박 특보 (소진율 95% 초과):</strong>
            </div>
            <div className="flex flex-wrap gap-1.5 ml-1">
              {criticalRegions.map((crit) => (
                <button
                  key={crit.region_id}
                  type="button"
                  onClick={() => onSelectCriticalRegion(crit.name_ko, crit.region_id)}
                  aria-label={`${crit.name_ko} 소진율 ${(Number.isFinite(crit.categories?.passenger?.depletion_rate) ? crit.categories.passenger.depletion_rate : 0).toFixed(1)}%, 보조금 계산기로 이동`}
                  className="px-2.5 py-1.5 min-h-[44px] inline-flex items-center rounded bg-rose-900 border border-rose-500/50 text-rose-200 hover:bg-rose-800 hover:text-white transition font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
                  title={`${crit.name_ko} 보조금 계산기로 이동`}
                >
                  {crit.name_ko} ({(Number.isFinite(crit.categories?.passenger?.depletion_rate) ? crit.categories.passenger.depletion_rate : 0).toFixed(1)}%)
                </button>
              ))}
            </div>
          </div>
          <a
            href="#subsidy-calculator"
            className="text-amber-300 hover:text-amber-200 underline font-semibold shrink-0 rounded px-2 py-2 min-h-[44px] flex items-center focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
          >
            내 차 실구매가 즉시 계산 &rarr;
          </a>
        </div>
      )}
    </section>
  );
});

// ============================================================================
// Sub-Component: Memoized 5-Tier Alert Legend Section
// (Isolated from search typing to eliminate re-renders on keystrokes)
// ============================================================================
interface AlertLegendSectionProps {
  thresholds: Record<AlertSeverity, AlertThresholdConfig>;
  alertFilter: AlertSeverity | 'ALL';
  onSelectAlertFilter: (key: AlertSeverity) => void;
}

const AlertLegendSection = React.memo(function AlertLegendSection({
  thresholds,
  alertFilter,
  onSelectAlertFilter,
}: AlertLegendSectionProps) {
  return (
    <section aria-labelledby="subsidy-alert-legend-heading" className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h2 id="subsidy-alert-legend-heading" className="text-sm font-bold text-slate-300 flex items-center gap-2">
          <span aria-hidden="true">🛡️</span> 전국 지자체 보조금 소진 5단계 경보 기준
        </h2>
        <span className="text-xs text-slate-300">배지 클릭 시 해당 경보 지역만 필터링</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5">
        {(Object.keys(thresholds) as AlertSeverity[]).map((key) => {
          const t = thresholds[key];
          const isSelected = alertFilter === key;
          return (
            <button
              key={key}
              type="button"
              aria-pressed={isSelected}
              aria-label={`${t?.label_ko || key} 경보 필터 ${isSelected ? '해제' : '적용'}`}
              onClick={() => onSelectAlertFilter(key)}
              className={`p-3 min-h-[44px] rounded-xl border text-left transition flex flex-col justify-between focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 ${
                isSelected
                  ? 'ring-2 ring-amber-400 ' + getBadgeStyle(key)
                  : 'bg-slate-950 hover:bg-slate-800 border-slate-800 text-slate-300'
              }`}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className={`text-xs px-2 py-0.5 rounded font-semibold border ${getBadgeStyle(key)}`}>
                  {getStatusLabel(key)}
                </span>
                <span className={`text-[11px] font-medium ${isSelected ? 'text-slate-100 font-semibold' : 'text-slate-300'}`}>{(t?.min_percent ?? 0)}%~{(t?.max_percent ?? 100)}%</span>
              </div>
              <div className={`text-[11px] line-clamp-2 mt-2 leading-relaxed ${isSelected ? 'text-slate-100' : 'text-slate-300'}`}>
                {t?.recommended_action || ''}
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
});

// ============================================================================
// Main Export: SubsidyTrackerClient Component
// ============================================================================
export default function SubsidyTrackerClient({ initialData }: SubsidyTrackerClientProps) {
  const searchParams = useSearchParams();
  const urlRegion = searchParams?.get('region') || '';
  const urlModel = searchParams?.get('model') || '';

  // Top-Level State
  const [selectedCategory, setSelectedCategory] = useState<CategoryType>('passenger');
  const [zoneFilter, setZoneFilter] = useState<ZoneFilter>('ALL');
  const [alertFilter, setAlertFilter] = useState<AlertSeverity | 'ALL'>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortOption, setSortOption] = useState<SortOption>('DEPLETION_DESC');
  const [viewMode, setViewMode] = useState<'grid' | 'table'>('grid');
  const [supplementaryOnly, setSupplementaryOnly] = useState(false);
  const [expandedRegions, setExpandedRegions] = useState<Record<string, boolean>>({});

  // Performance Optimization: Non-blocking search typing via useDeferredValue
  const deferredSearchQuery = useDeferredValue(searchQuery);

  // Calculator State & Ref
  const calculatorRef = useRef<HTMLDivElement>(null);
  // Default to server baseline to eliminate hydration mismatch risks with query strings
  const [selectedModelId, setSelectedModelId] = useState<string>(
    initialData?.popular_models_matrix?.[0]?.model_id || 'ioniq-5-2026'
  );
  const [selectedRegionId, setSelectedRegionId] = useState<string>(
    initialData?.regions?.[0]?.region_id || 'KR-11'
  );

  // Sync selectedModelId and selectedRegionId on query param navigation
  useEffect(() => {
    if (urlModel) {
      const canonical = getModelById(urlModel)?.model_id;
      setSelectedModelId(canonical || urlModel);
    }
    if (urlRegion) {
      const canonical = getRegionById(urlRegion)?.region_id;
      setSelectedRegionId(canonical || urlRegion);
    }
  }, [urlModel, urlRegion]);

  const regions = useMemo(() => (Array.isArray(initialData?.regions) ? initialData.regions : []), [initialData?.regions]);
  const models = useMemo(() => (Array.isArray(initialData?.popular_models_matrix) ? initialData.popular_models_matrix : []), [initialData?.popular_models_matrix]);

  const summary = useMemo(() => initialData?.nationwide_summary || FALLBACK_SUMMARY, [initialData?.nationwide_summary]);
  const thresholds = useMemo(() => initialData?.alert_thresholds || FALLBACK_THRESHOLDS, [initialData?.alert_thresholds]);

  // Optimized Filtered & Sorted Regions (dependent on deferredSearchQuery to keep typing responsive)
  const filteredRegions = useMemo(() => {
    const trimmedQuery = deferredSearchQuery.trim().toLowerCase();

    const filtered = regions.filter((region) => {
      // Category Metrics
      const catMetrics: CategoryMetrics | undefined = region.categories?.[selectedCategory];
      if (!catMetrics) return false;

      // Zone filter
      if (zoneFilter !== 'ALL' && getRegionZone(region.iso_code) !== zoneFilter) {
        return false;
      }

      // Alert filter
      const status = catMetrics.status || 'HEALTHY';
      if (alertFilter !== 'ALL' && status !== alertFilter) {
        return false;
      }

      // Supplementary budget filter
      if (supplementaryOnly && !region.supplementary_budget_added) {
        return false;
      }

      // Search Query
      if (trimmedQuery) {
        const matchRegion =
          (region.name_ko || '').toLowerCase().includes(trimmedQuery) ||
          (region.name_en || '').toLowerCase().includes(trimmedQuery) ||
          (region.iso_code || '').toLowerCase().includes(trimmedQuery);

        const matchMuni =
          region.municipalities?.some((m) => (m.name_ko || '').toLowerCase().includes(trimmedQuery)) ?? false;

        if (!matchRegion && !matchMuni) return false;
      }

      return true;
    });

    // Deterministic, NaN-safe, stable sorting using sortRegions
    return sortRegions(filtered, sortOption, selectedCategory);
  }, [regions, selectedCategory, zoneFilter, alertFilter, supplementaryOnly, deferredSearchQuery, sortOption]);

  // Critical regions (for emergency ticker) with safe fallback computation
  const criticalRegions = useMemo(() => {
    return regions.filter((r) => {
      const p = r.categories?.passenger;
      if (!p) return false;
      const ann = Number.isFinite(p.announced_units) ? Math.max(0, p.announced_units) : 0;
      const app = Number.isFinite(p.applied_units) ? Math.max(0, p.applied_units) : 0;
      const rate = Number.isFinite(p.depletion_rate) ? p.depletion_rate : ann > 0 ? (app / ann) * 100 : 0;
      return (
        p.status === 'CRITICAL' ||
        p.status === 'DEPLETED' ||
        rate >= 95.0
      );
    });
  }, [regions]);

  // Stable Callbacks (passed to memoized children to prevent re-render cascades)
  const handleSelectRegionForCalc = useCallback((regionId: string) => {
    setSelectedRegionId(regionId);
    if (calculatorRef.current) {
      calculatorRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, []);

  const toggleRegionExpand = useCallback((regionId: string) => {
    setExpandedRegions((prev) => ({
      ...prev,
      [regionId]: !prev[regionId],
    }));
  }, []);

  const handleSelectModelId = useCallback((modelId: string) => {
    setSelectedModelId(modelId);
  }, []);

  const handleSelectRegionId = useCallback((regionId: string) => {
    setSelectedRegionId(regionId);
  }, []);

  const handleSortChange = useCallback((newSort: RegionSortOption) => {
    setSortOption(newSort);
  }, []);

  const handleSelectAlertFilter = useCallback((key: AlertSeverity) => {
    setAlertFilter((prev) => (prev === key ? 'ALL' : key));
  }, []);

  const handleSelectCriticalRegion = useCallback((nameKo: string, regionId: string) => {
    setSearchQuery(nameKo);
    handleSelectRegionForCalc(regionId);
  }, [handleSelectRegionForCalc]);

  const handleSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
  }, []);

  const handleClearSearch = useCallback(() => {
    setSearchQuery('');
  }, []);

  const handleToggleSupplementary = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setSupplementaryOnly(e.target.checked);
  }, []);

  const handleSelectZone = useCallback((zone: ZoneFilter) => {
    setZoneFilter(zone);
  }, []);

  const handleResetFilters = useCallback(() => {
    setZoneFilter('ALL');
    setAlertFilter('ALL');
    setSearchQuery('');
    setSupplementaryOnly(false);
  }, []);

  const handleSetViewGrid = useCallback(() => setViewMode('grid'), []);
  const handleSetViewTable = useCallback(() => setViewMode('table'), []);

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

    if (nextIndex >= 0) {
      setSelectedCategory(CATEGORY_TABS[nextIndex].id);
      const targetBtn = document.getElementById(`tab-category-${CATEGORY_TABS[nextIndex].id}`);
      if (targetBtn) {
        targetBtn.focus();
      }
    }
  }, []);

  // Performance & Stability: Memoized regional cards to prevent re-render cascades
  const renderedGridCards = useMemo(() => {
    return filteredRegions.map((regionItem) => (
      <RegionCard
        key={regionItem.region_id}
        region={regionItem}
        selectedCategory={selectedCategory}
        isExpanded={Boolean(expandedRegions[regionItem.region_id])}
        toggleRegionExpand={toggleRegionExpand}
        onSelectForCalc={handleSelectRegionForCalc}
      />
    ));
  }, [filteredRegions, selectedCategory, expandedRegions, toggleRegionExpand, handleSelectRegionForCalc]);

  return (
    <div className="space-y-10 py-6 text-slate-100 max-w-6xl mx-auto">
      {/* Skip Navigation for Keyboard Accessibility */}
      <a
        href="#subsidy-calculator"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2.5 focus:bg-amber-400 focus:text-slate-950 focus:font-bold focus:rounded-xl focus:shadow-2xl focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 transition"
      >
        보조금 계산기로 건너뛰기
      </a>

      {/* 1. Header Banner & Live Tracker Status - Isolated Memoized Pure Component */}
      <TrackerHeader
        summary={summary}
        generatedAt={initialData?.metadata?.generated_at}
        criticalRegions={criticalRegions}
        onSelectCriticalRegion={handleSelectCriticalRegion}
      />

      {/* 2. 5-Tier Alert Badges Legend & Quick Filter - Isolated Memoized Pure Component */}
      <AlertLegendSection
        thresholds={thresholds}
        alertFilter={alertFilter}
        onSelectAlertFilter={handleSelectAlertFilter}
      />

      {/* 3. Search & Filter Bar */}
      <section aria-labelledby="filter-controls-heading" className="bg-slate-900 border border-slate-800 rounded-2xl p-4 sm:p-5 space-y-4">
        <h2 id="filter-controls-heading" className="sr-only">지자체 검색 및 정렬 제어판</h2>
        <div className="flex flex-wrap items-center justify-between gap-4">
          {/* Vehicle Category Selector */}
          <div role="tablist" aria-label="차종 카테고리 선택" className="flex flex-wrap items-center gap-1.5 p-1 bg-slate-950 rounded-xl border border-slate-800 text-xs sm:text-sm font-semibold">
            {CATEGORY_TABS.map((cat, idx) => {
              const isSelected = selectedCategory === cat.id;
              return (
                <button
                  key={cat.id}
                  id={`tab-category-${cat.id}`}
                  type="button"
                  role="tab"
                  aria-selected={isSelected}
                  aria-controls="panel-regional-grid"
                  tabIndex={isSelected ? 0 : -1}
                  onKeyDown={(e) => handleCategoryKeyDown(e, idx)}
                  onClick={() => setSelectedCategory(cat.id)}
                  className={`px-3 py-2 min-h-[44px] flex items-center justify-center rounded-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 ${
                    isSelected
                      ? 'bg-blue-600 text-white shadow'
                      : 'text-slate-300 hover:text-white'
                  }`}
                >
                  {cat.icon} {cat.label}
                </button>
              );
            })}
          </div>

          {/* Supplementary Budget Toggle */}
          <label htmlFor="supplementary-budget-toggle" className="flex items-center gap-2 cursor-pointer text-xs sm:text-sm text-slate-300 hover:text-white select-none min-h-[44px]">
            <input
              id="supplementary-budget-toggle"
              type="checkbox"
              aria-label="추경 예산 편성 지자체만 보기"
              checked={supplementaryOnly}
              onChange={handleToggleSupplementary}
              className="w-5 h-5 rounded bg-slate-800 border-slate-700 text-amber-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
            />
            <span>추경 예산 편성 지자체만 보기</span>
          </label>
        </div>

        {/* Zone Filters & Search Input */}
        <div className="flex flex-col md:flex-row gap-3 pt-2">
          {/* Search Box */}
          <div className="relative flex-1">
            <label htmlFor="region-search-input" className="sr-only">
              지자체 검색
            </label>
            <div aria-hidden="true" className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-300 text-sm">
              🔍
            </div>
            <input
              id="region-search-input"
              type="search"
              role="searchbox"
              autoComplete="off"
              autoCorrect="off"
              spellCheck="false"
              aria-label="지자체 검색"
              aria-describedby="filter-feedback-status"
              value={searchQuery}
              onChange={handleSearchChange}
              placeholder="시·도 또는 세부 시·군·구 검색 (예: 서울, 수원, 성남, 대구, 포항, 울릉)"
              className="w-full pl-10 pr-9 py-2.5 min-h-[44px] rounded-xl bg-slate-950 border border-slate-700 text-white placeholder-slate-300 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={handleClearSearch}
                aria-label="검색어 지우기"
                className="absolute inset-y-0 right-0 pr-3 min-w-[44px] min-h-[44px] flex items-center justify-center text-slate-300 hover:text-white text-sm rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
              >
                <span aria-hidden="true">✕</span>
              </button>
            )}
          </div>

          {/* Regional Zone Pills */}
          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            {ZONE_FILTERS.map((zone) => (
              <button
                key={zone.id}
                type="button"
                aria-pressed={zoneFilter === zone.id}
                aria-label={`${zone.label} 권역 필터 ${zoneFilter === zone.id ? '해제' : '적용'}`}
                onClick={() => handleSelectZone(zone.id)}
                className={`px-2.5 py-1.5 min-h-[44px] flex items-center justify-center rounded-lg border font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 ${
                  zoneFilter === zone.id
                    ? 'bg-blue-600 text-white border-blue-500'
                    : 'bg-slate-950 text-slate-300 border-slate-800 hover:bg-slate-800'
                }`}
              >
                {zone.label}
              </button>
            ))}
          </div>

          {/* Sort Selector */}
          <div className="shrink-0">
            <label htmlFor="region-sort-select" className="sr-only">지자체 정렬 방식</label>
            <select
              id="region-sort-select"
              value={sortOption}
              onChange={(e) => {
                if (isSortOption(e.target.value)) {
                  handleSortChange(e.target.value);
                }
              }}
              aria-label="지자체 정렬 방식"
              className="py-2.5 px-3 min-h-[44px] rounded-xl bg-slate-950 border border-slate-700 text-slate-200 text-xs sm:text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 cursor-pointer font-medium"
            >
              <option value="DEPLETION_DESC">소진율 높은 순 (마감임박)</option>
              <option value="DEPLETION_ASC">소진율 낮은 순 (신청여유)</option>
              <option value="REMAINING_ASC">잔여 대수 적은 순</option>
              <option value="REMAINING_DESC">잔여 대수 많은 순</option>
              <option value="LOCAL_SUBSIDY_DESC">지자체 보조금 높은 순</option>
              <option value="LOCAL_SUBSIDY_ASC">지자체 보조금 낮은 순</option>
              <option value="NAME_ASC">지역명 가나다순 (ㄱ~ㅎ)</option>
              <option value="NAME_DESC">지역명 역순 (ㅎ~ㄱ)</option>
            </select>
          </div>
        </div>

        {/* Active Filter Clear indicator with role="status" and aria-live */}
        {(zoneFilter !== 'ALL' || alertFilter !== 'ALL' || searchQuery || supplementaryOnly) && (
          <div className="flex items-center justify-between text-xs text-slate-300 pt-2 border-t border-slate-800">
            <span id="filter-feedback-status" role="status" aria-live="polite">
              필터 적용 중: 총 <strong>{filteredRegions.length}</strong>개 지역 표시 중
            </span>
            <button
              type="button"
              aria-label="적용된 전체 필터 초기화"
              onClick={handleResetFilters}
              className="text-amber-400 hover:text-amber-300 underline font-medium rounded px-2.5 py-1.5 min-h-[44px] inline-flex items-center focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
            >
              전체 필터 초기화
            </button>
          </div>
        )}
      </section>

      {/* 4. 17 Regional Grid Cards / Table View - Visible Focus Ring for Keyboard Users */}
      <section
        id="panel-regional-grid"
        role="tabpanel"
        aria-labelledby={`tab-category-${selectedCategory}`}
        tabIndex={0}
        className="space-y-4 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-2xl"
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="regional-grid-heading" className="text-xl sm:text-2xl font-bold text-white flex items-center gap-2">
            <span aria-hidden="true">🗺️</span> 17개 광역시도별 보조금 소진율 &amp; 잔여 쿼터 현황
          </h2>
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-xs text-slate-300 font-medium">
              {selectedCategory === 'passenger' ? '전기승용 기준' : selectedCategory === 'commercial' ? '전기화물 기준' : '전기승합 기준'}
              {filteredRegions.length < regions.length && ` (검색 결과 ${filteredRegions.length}개 지역)`}
            </span>
            {/* View Mode Toggle: Grid Cards vs Semantic Table with aria-sort & scope */}
            <div
              role="group"
              aria-label="지역 데이터 보기 방식 선택"
              className="inline-flex rounded-xl bg-slate-950 p-1 border border-slate-800 text-xs"
            >
              <button
                type="button"
                aria-pressed={viewMode === 'grid'}
                aria-label="카드 그리드 형식으로 보기"
                onClick={handleSetViewGrid}
                className={`px-3 py-1.5 min-h-[44px] inline-flex items-center justify-center rounded-lg font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 ${
                  viewMode === 'grid'
                    ? 'bg-blue-600 text-white shadow'
                    : 'text-slate-300 hover:text-white'
                }`}
              >
                🗂️ 카드 보기
              </button>
              <button
                type="button"
                aria-pressed={viewMode === 'table'}
                aria-label="표(테이블) 형식으로 보기"
                onClick={handleSetViewTable}
                className={`px-3 py-1.5 min-h-[44px] inline-flex items-center justify-center rounded-lg font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 ${
                  viewMode === 'table'
                    ? 'bg-blue-600 text-white shadow'
                    : 'text-slate-300 hover:text-white'
                }`}
              >
                📊 표로 보기
              </button>
            </div>
          </div>
        </div>

        {filteredRegions.length === 0 ? (
          <div
            role="status"
            aria-live="polite"
            className="bg-slate-900 border border-slate-800 rounded-2xl p-12 text-center text-slate-300"
          >
            <div className="text-3xl mb-2" aria-hidden="true">🔍</div>
            <div className="text-base font-semibold text-slate-200">검색 및 필터 조건에 일치하는 지자체가 없습니다.</div>
            <p className="text-xs text-slate-300 mt-1">검색어를 변경하거나 필터를 초기화해 보세요.</p>
          </div>
        ) : viewMode === 'table' ? (
          <SubsidyTableView
            regions={filteredRegions}
            selectedCategory={selectedCategory}
            sortOption={sortOption}
            onSortChange={handleSortChange}
            expandedRegions={expandedRegions}
            onToggleExpand={toggleRegionExpand}
            onSelectForCalc={handleSelectRegionForCalc}
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {renderedGridCards}
          </div>
        )}
      </section>

      {/* 5. Interactive Real-Time Net Subsidy Calculator (Wrapped with ErrorBoundary) */}
      <SubsidyErrorBoundary fallbackTitle="실시간 전기차 보조금 계산기 일시 오류">
        <SubsidyCalculator
          calculatorRef={calculatorRef}
          models={models}
          regions={regions}
          selectedModelId={selectedModelId}
          selectedRegionId={selectedRegionId}
          onSelectModelId={handleSelectModelId}
          onSelectRegionId={handleSelectRegionId}
        />
      </SubsidyErrorBoundary>

      {/* 6. Regulatory Footer Notes & Accessible FAQ Accordion */}
      <SubsidyFaqAccordion />
    </div>
  );
}

// ============================================================================
// Sub-Component: Memoized Region Card (prevents re-render cascades on typing)
// ============================================================================
interface RegionCardProps {
  region: RegionEntry;
  selectedCategory: CategoryType;
  isExpanded: boolean;
  toggleRegionExpand: (regionId: string) => void;
  onSelectForCalc: (regionId: string) => void;
}

const RegionCard = React.memo(function RegionCard({
  region,
  selectedCategory,
  isExpanded,
  toggleRegionExpand,
  onSelectForCalc,
}: RegionCardProps) {
  const cat: CategoryMetrics = region?.categories?.[selectedCategory] ?? FALLBACK_CATEGORY_METRICS;

  const announcedUnits = Number.isFinite(cat?.announced_units) ? Math.max(0, cat.announced_units) : 0;
  const safeAnnounced = announcedUnits > 0 ? announcedUnits : 1;
  const safeDelivered = Number.isFinite(cat?.delivered_units) ? cat.delivered_units : 0;
  const safeApplied = Number.isFinite(cat?.applied_units) ? cat.applied_units : 0;
  const pendingUnits = Math.max(0, safeApplied - safeDelivered);
  const safeDepletion = Number.isFinite(cat?.depletion_rate)
    ? cat.depletion_rate
    : announcedUnits > 0
    ? (safeApplied / safeAnnounced) * 100
    : 0;
  const safeRemaining = Number.isFinite(cat?.remaining_units)
    ? cat.remaining_units
    : Math.max(0, announcedUnits - safeApplied);

  const regionName = region?.name_ko || '해당 지역';
  const regionId = region?.region_id || '';
  const munis = useMemo(
    () => (Array.isArray(region?.municipalities) ? region.municipalities : []),
    [region?.municipalities]
  );
  const categoryLabel = selectedCategory === 'passenger' ? '전기승용' : selectedCategory === 'commercial' ? '전기화물' : '전기승합';

  // Memoized handlers for button interactions
  const handleSelectCalc = useCallback(() => {
    onSelectForCalc(regionId);
  }, [onSelectForCalc, regionId]);

  // Performance optimization: Lazy render sub-municipalities once opened.
  // Preserves container element in DOM with hidden={!isExpanded} so aria-controls never breaks.
  const [hasBeenExpanded, setHasBeenExpanded] = useState(isExpanded);

  useEffect(() => {
    if (isExpanded && !hasBeenExpanded) {
      setHasBeenExpanded(true);
    }
  }, [isExpanded, hasBeenExpanded]);

  // Memoized sub-municipalities list
  const renderedMunis = useMemo(() => {
    if (!hasBeenExpanded) return null;
    return munis.map((muni) => {
      const muniAnnounced = Number.isFinite(muni.announced_units) ? Math.max(0, muni.announced_units) : 0;
      const muniApplied = Number.isFinite(muni.applied_units) ? Math.max(0, muni.applied_units) : 0;
      const muniRemaining = Number.isFinite(muni.remaining_units)
        ? Math.max(0, muni.remaining_units)
        : Math.max(0, muniAnnounced - muniApplied);
      const muniDepletion = Number.isFinite(muni.depletion_rate)
        ? Math.max(0, muni.depletion_rate)
        : muniAnnounced > 0
        ? (muniApplied / muniAnnounced) * 100
        : 0;
      const muniLocalSubsidy = Number.isFinite(muni.local_subsidy_krw) ? Math.max(0, muni.local_subsidy_krw) : 0;

      return (
        <div
          key={muni.muni_id || `${regionId}-${muni.name_ko}`}
          className="p-2 rounded bg-slate-950 border border-slate-800 flex items-center justify-between text-[11px]"
        >
          <div>
            <span className="font-semibold text-slate-200">{muni.name_ko}</span>
            <span className="text-slate-300 ml-2">
              {((muniLocalSubsidy) / 10000).toLocaleString()}만 원
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-slate-300">잔여 {muniRemaining.toLocaleString()}대</span>
            <SubsidyBadge status={muni.status || 'available'} />
            <span className="font-mono text-amber-300 font-semibold text-[10px]">
              {muniDepletion.toFixed(1)}%
            </span>
          </div>
        </div>
      );
    });
  }, [hasBeenExpanded, munis, regionId]);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg hover:border-slate-700 transition flex flex-col justify-between">
      <div className="space-y-3">
        {/* Card Header */}
        <div className="flex items-start justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-bold text-white">{regionName}</h3>
              {region?.iso_code && (
                <span className="text-[10px] text-slate-300 uppercase font-mono font-medium">{region.iso_code}</span>
              )}
            </div>
            {region?.name_en && (
              <div className="text-xs text-slate-300">{region.name_en}</div>
            )}
          </div>
          <SubsidyBadge status={cat?.status || 'available'} />
        </div>

        {/* Dual-layer Progress Bar via memoized SubsidyProgressBar */}
        <div>
          <SubsidyProgressBar
            depletionRate={safeDepletion}
            deliveredUnits={safeDelivered}
            appliedUnits={safeApplied}
            remainingUnits={safeRemaining}
            announcedUnits={announcedUnits}
            regionName={regionName}
            categoryLabel={categoryLabel}
            status={cat?.status || 'available'}
            showDetails={true}
          />
          <div className="sr-only">
            잔여 <strong>{safeRemaining.toLocaleString()}</strong> / {announcedUnits.toLocaleString()}대 (출고 대기: {pendingUnits.toLocaleString()}대)
          </div>
        </div>

        {/* Financial Subsidy Limits - Solid Opaque Backgrounds for Contrast */}
        <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-800 text-xs">
          <div className="bg-slate-950 p-2.5 rounded-xl border border-slate-800">
            <div className="text-[11px] text-slate-300">지자체 최대 지원금</div>
            <div className="text-sm font-bold text-slate-200 mt-0.5">
              {((Number.isFinite(cat?.max_local_subsidy_krw) ? Math.max(0, cat.max_local_subsidy_krw) : 0) / 10000).toLocaleString()}만 원
            </div>
          </div>
          <div className="bg-slate-950 p-2.5 rounded-xl border border-slate-800">
            <div className="text-[11px] text-slate-300">국비+지방비 합산 최대</div>
            <div className="text-sm font-bold text-amber-400 mt-0.5">
              {((Number.isFinite(cat?.max_total_subsidy_krw) ? Math.max(0, cat.max_total_subsidy_krw) : 0) / 10000).toLocaleString()}만 원
            </div>
          </div>
        </div>

        {/* Eligibility & Notes */}
        <div className="flex flex-wrap gap-1.5 pt-1 text-[11px]">
          <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
            거주 요건: {Number.isFinite(region?.residency_requirement_days) ? region.residency_requirement_days : 30}일 이상
          </span>
          {region?.supplementary_budget_added && (
            <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-500/40 font-semibold">
              추경 완료
            </span>
          )}
        </div>

        {region?.notes && (
          <p className="text-xs text-slate-300 leading-relaxed bg-slate-950 p-2 rounded-lg border border-slate-800">
            ℹ️ {region.notes}
          </p>
        )}

        {/* Municipalities Collapsible (if province has sub-cities) */}
        {munis.length > 0 && (
          <div className="pt-2">
            <button
              type="button"
              onClick={() => toggleRegionExpand(region.region_id)}
              aria-expanded={isExpanded}
              aria-controls={'muni-details-' + region.region_id}
              aria-label={`${region.name_ko} 세부 시·군·구 ${munis.length}개 현황 ${isExpanded ? '접기' : '보기'}`}
              className="w-full py-2.5 px-3 min-h-[44px] rounded-lg bg-slate-950 hover:bg-slate-800 text-slate-300 text-xs font-medium flex items-center justify-between transition border border-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
            >
              <span>세부 시·군·구 {munis.length}개 현황 보기</span>
              <span>{isExpanded ? '▲ 접기' : '▼ 펼치기'}</span>
            </button>

            {/* Preserved in DOM with hidden attribute so aria-controls never breaks */}
            <div
              id={'muni-details-' + region.region_id}
              hidden={!isExpanded}
              tabIndex={0}
              role="region"
              aria-label={`${region.name_ko} 세부 시·군·구 보조금 현황 목록`}
              className={`${!isExpanded ? 'hidden' : ''} mt-2 space-y-1.5 max-h-48 overflow-y-auto pr-1 text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-lg`}
            >
              {renderedMunis}
            </div>
          </div>
        )}
      </div>

      {/* Card Action Button */}
      <div className="pt-4 mt-3 border-t border-slate-800">
        <button
          type="button"
          onClick={handleSelectCalc}
          aria-label={`${regionName} 보조금으로 실구매가 계산`}
          className="w-full py-3 px-4 min-h-[44px] rounded-xl bg-blue-600/90 hover:bg-blue-600 text-white font-semibold text-xs transition flex items-center justify-center gap-1.5 shadow focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
        >
          <span>⚡</span> 이 지역({regionName})으로 실구매가 계산
        </button>
      </div>
    </div>
  );
});

// ============================================================================
// Sub-Component: Memoized Net Subsidy Calculator
// (Isolated state: typing in search or toggling filters will not re-render calculator,
// and toggling calculator checkboxes will not re-render the regional cards)
// ============================================================================
interface SubsidyCalculatorProps {
  calculatorRef: React.RefObject<HTMLDivElement>;
  models: PopularModelEntry[];
  regions: RegionEntry[];
  selectedModelId: string;
  selectedRegionId: string;
  onSelectModelId: (modelId: string) => void;
  onSelectRegionId: (regionId: string) => void;
}

const SubsidyCalculator = React.memo(function SubsidyCalculator({
  calculatorRef,
  models,
  regions,
  selectedModelId,
  selectedRegionId,
  onSelectModelId,
  onSelectRegionId,
}: SubsidyCalculatorProps) {
  const [isCustomMsrp, setIsCustomMsrp] = useState(false);
  const [customMsrpInput, setCustomMsrpInput] = useState<string>('');
  const [calcOptions, setCalcOptions] = useState<SubsidyCalculatorOptions>({
    isYouthFirstTimeBuyer: false,
    isSmallBusinessOrTaxi: false,
    isMultiChildFamily: false,
    isOldDieselScrappage: false,
  });

  const handleToggleYouthBuyer = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.checked;
    setCalcOptions((prev) => ({ ...prev, isYouthFirstTimeBuyer: val }));
  }, []);

  const handleToggleSmallBusiness = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.checked;
    setCalcOptions((prev) => ({ ...prev, isSmallBusinessOrTaxi: val }));
  }, []);

  const handleToggleMultiChild = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.checked;
    setCalcOptions((prev) => ({ ...prev, isMultiChildFamily: val }));
  }, []);

  const handleToggleOldDiesel = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.checked;
    setCalcOptions((prev) => ({ ...prev, isOldDieselScrappage: val }));
  }, []);

  const handleModelSelectChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    onSelectModelId(e.target.value);
  }, [onSelectModelId]);

  const handleRegionSelectChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    onSelectRegionId(e.target.value);
  }, [onSelectRegionId]);

  const handleCustomMsrpChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setCustomMsrpInput(e.target.value.replace(/[^0-9]/g, ''));
  }, []);

  const handleSetPresetMsrp = useCallback((msrp: string) => {
    setCustomMsrpInput(msrp);
  }, []);

  // Performance: Fast O(1) indexed lookup maps for models and regions
  const modelsMap = useMemo(() => {
    const map = new Map<string, PopularModelEntry>();
    for (const m of models) {
      if (m?.model_id) {
        map.set(m.model_id.toLowerCase(), m);
      }
    }
    return map;
  }, [models]);

  const regionsMap = useMemo(() => {
    const map = new Map<string, RegionEntry>();
    for (const r of regions) {
      if (r?.region_id) {
        map.set(r.region_id.toLowerCase(), r);
      }
      if (r?.iso_code) {
        map.set(r.iso_code.toLowerCase(), r);
      }
    }
    return map;
  }, [regions]);

  const activeModel = useMemo(() => {
    const q = (selectedModelId || '').trim().toLowerCase();
    if (modelsMap.has(q)) {
      return modelsMap.get(q)!;
    }
    const resolved = getModelById(q);
    if (resolved) {
      const matchInModels = modelsMap.get(resolved.model_id.toLowerCase());
      if (matchInModels) return matchInModels;
      return resolved;
    }
    return (
      models.find(
        (m) =>
          m.model_id.toLowerCase() === q ||
          m.name_ko.toLowerCase().includes(q)
      ) || models[0] || undefined
    );
  }, [models, modelsMap, selectedModelId]);

  const activeRegionForCalc = useMemo(() => {
    const q = (selectedRegionId || '').trim().toLowerCase();
    if (regionsMap.has(q)) {
      return regionsMap.get(q)!;
    }
    const resolved = getRegionById(q);
    if (resolved) {
      const matchInRegions = regionsMap.get(resolved.region_id.toLowerCase());
      if (matchInRegions) return matchInRegions;
      return resolved;
    }
    return (
      regions.find(
        (r) =>
          r.region_id.toLowerCase() === q ||
          r.iso_code.toLowerCase() === q ||
          r.name_ko.toLowerCase() === q ||
          r.name_ko.replace(/(특별시|광역시|특별자치시|도|특별자치도)$/, '').toLowerCase() === q ||
          r.name_en.toLowerCase() === q
      ) || regions[0] || undefined
    );
  }, [regions, regionsMap, selectedRegionId]);

  const handleToggleCustomMsrp = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const checked = e.target.checked;
    setIsCustomMsrp(checked);
    if (checked && !customMsrpInput && activeModel) {
      setCustomMsrpInput(activeModel.base_price_krw.toString());
    }
  }, [customMsrpInput, activeModel]);

  const topModels = useMemo(() => (Array.isArray(models) ? models.slice(0, 8) : []), [models]);

  const calculationResult = useMemo(() => {
    let customMsrpNum: number | undefined = undefined;
    if (isCustomMsrp) {
      const cleaned = (customMsrpInput || '').replace(/[^0-9]/g, '');
      const parsed = cleaned ? parseInt(cleaned, 10) : NaN;
      customMsrpNum = Number.isFinite(parsed) && parsed > 0 ? parsed : (activeModel?.base_price_krw ?? 0);
    }
    return calculateNetSubsidyPure(
      activeModel!,
      activeRegionForCalc!,
      customMsrpNum,
      calcOptions
    );
  }, [
    activeModel,
    activeRegionForCalc,
    isCustomMsrp,
    customMsrpInput,
    calcOptions,
  ]);

  return (
    <section
      id="subsidy-calculator"
      ref={calculatorRef}
      tabIndex={-1}
      aria-labelledby="calculator-heading"
      className="bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-950 border border-blue-500/30 rounded-3xl p-6 sm:p-8 shadow-2xl space-y-8 outline-none focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
    >
      <div className="max-w-3xl space-y-2">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/20 text-blue-300 border border-blue-400/30 text-xs font-bold uppercase tracking-wider">
          <span aria-hidden="true">💡</span> 실시간 인터랙티브 시뮬레이터
        </div>
        <h2 id="calculator-heading" className="text-2xl sm:text-3xl font-extrabold text-white">
          ⚡ 실시간 전기차 보조금 &amp; 체감 실구매가 계산기
        </h2>
        <p className="text-slate-300 text-sm leading-relaxed">
          원하는 전기차 모델과 거주 지자체를 선택하면 2026년 <strong>5,500만/8,500만 원 슬라이딩 가격상한제</strong>, 배터리 계수, 지자체 매칭률 및 특별 가산금을 자동 계산하여 <strong>실제 내 지갑에서 나가는 체감가</strong>를 즉시 산출합니다.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Calculator Controls */}
        <div className="lg:col-span-7 space-y-6">
          {/* 1. Vehicle Selector */}
          <div className="space-y-2">
            <label htmlFor="model-select" className="block text-xs font-bold text-slate-300 uppercase tracking-wider">
              1. 차량 모델 선택
            </label>
            <select
              id="model-select"
              aria-label="차량 모델 선택"
              value={activeModel?.model_id || selectedModelId}
              onChange={handleModelSelectChange}
              className="w-full py-3 px-3.5 rounded-xl bg-slate-950 border border-slate-700 text-white text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 cursor-pointer font-medium"
            >
              {models.map((model) => (
                <option key={model.model_id} value={model.model_id}>
                  {model.manufacturer} - {model.name_ko} (출고가 {((Number.isFinite(model.base_price_krw) ? Math.max(0, model.base_price_krw) : 0) / 10000).toLocaleString()}만 원)
                </option>
              ))}
            </select>

            {/* Quick Pills for Top Models */}
            <div className="flex flex-wrap gap-1.5 pt-1">
              {topModels.map((m) => {
                const isSelected = (activeModel?.model_id || selectedModelId) === m.model_id;
                return (
                  <button
                    key={m.model_id}
                    type="button"
                    aria-pressed={isSelected}
                    aria-label={`${m.name_ko} 모델 선택`}
                    onClick={() => onSelectModelId(m.model_id)}
                    className={`px-2.5 py-1 min-h-[44px] flex items-center justify-center rounded-lg text-xs font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 ${
                      isSelected
                        ? 'bg-blue-600 text-white'
                        : 'bg-slate-950 text-slate-300 hover:bg-slate-800 border border-slate-800'
                    }`}
                  >
                    {m.name_ko.replace(BRAND_PREFIX_REGEX, '')}
                  </button>
                );
              })}
            </div>

            {/* Selected Model Spec Card - Solid Opaque Background */}
            {activeModel && (
              <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl flex flex-wrap items-center justify-between text-xs text-slate-300 gap-2">
                <span>배터리: <strong>{activeModel.battery_type || 'N/A'}</strong> ({activeModel.battery_capacity_kwh ?? 0} kWh)</span>
                <span>1회 충전 주행거리: <strong>{activeModel.rated_range_km ?? 0} km</strong></span>
                <span>기본 출고가: <strong>{((Number.isFinite(activeModel.base_price_krw) ? Math.max(0, activeModel.base_price_krw) : 0) / 10000).toLocaleString()}만 원</strong></span>
              </div>
            )}
          </div>

          {/* 2. Region Selector */}
          <div className="space-y-2">
            <label htmlFor="region-select" className="block text-xs font-bold text-slate-300 uppercase tracking-wider">
              2. 거주 지자체 (시·도) 선택
            </label>
            <select
              id="region-select"
              aria-label="거주 지자체 (시·도) 선택"
              value={activeRegionForCalc?.region_id || selectedRegionId}
              onChange={handleRegionSelectChange}
              aria-describedby="region-residency-note"
              className="w-full py-3 px-3.5 rounded-xl bg-slate-950 border border-slate-700 text-white text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 cursor-pointer font-medium"
            >
              {regions.map((reg) => (
                <option key={reg.region_id} value={reg.region_id}>
                  {reg.name_ko} ({(Number.isFinite(reg.categories?.passenger?.depletion_rate) ? reg.categories.passenger.depletion_rate : 0).toFixed(1)}% 소진, {getStatusLabel(reg.categories?.passenger?.status || 'available')})
                </option>
              ))}
            </select>
            <p id="region-residency-note" className="text-xs text-amber-300 flex items-center gap-1.5 pt-0.5">
              <span aria-hidden="true">ℹ️</span> 해당 지자체 최소 <strong>{Number.isFinite(activeRegionForCalc?.residency_requirement_days) ? activeRegionForCalc.residency_requirement_days : 30}일 이상</strong> 연속 거주 요건 필요
            </p>
          </div>

          {/* 3. Custom MSRP Option */}
          <div className="space-y-3 p-4 bg-slate-950 border border-slate-800 rounded-2xl">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <label htmlFor="custom-msrp-toggle-checkbox" className="flex items-center gap-2 cursor-pointer select-none text-xs font-bold text-slate-300 uppercase tracking-wider">
                <input
                  id="custom-msrp-toggle-checkbox"
                  type="checkbox"
                  aria-label="옵션 포함 출고가 직접 입력 (커스텀 MSRP)"
                  checked={isCustomMsrp}
                  onChange={handleToggleCustomMsrp}
                  className="w-4 h-4 rounded bg-slate-800 border-slate-700 text-amber-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
                />
                <span>옵션 포함 출고가 직접 입력 (커스텀 MSRP)</span>
              </label>
              {isCustomMsrp && (
                <span className="text-[11px] text-amber-400 font-medium">5,500만/8,500만 원 상한제 실시간 연동</span>
              )}
            </div>

            {isCustomMsrp && (
              <div className="space-y-1.5 pt-1">
                <label htmlFor="custom-msrp-input" className="sr-only">
                  직접 차량 출고가 입력
                </label>
                <div className="relative">
                  <input
                    id="custom-msrp-input"
                    type="text"
                    inputMode="numeric"
                    aria-label="직접 차량 출고가 입력"
                    value={customMsrpInput && Number.isFinite(parseInt(customMsrpInput, 10)) ? parseInt(customMsrpInput, 10).toLocaleString('ko-KR') : ''}
                    onChange={handleCustomMsrpChange}
                    placeholder="원 단위 출고가 입력 (예: 54,900,000)"
                    className="w-full py-2.5 px-3.5 rounded-xl bg-slate-900 border border-slate-700 text-white text-sm font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 pr-12"
                  />
                  <span aria-hidden="true" className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-300 text-xs font-semibold">
                    원
                  </span>
                </div>
                <div className="flex flex-wrap gap-2 text-[11px]">
                  <button
                    type="button"
                    aria-label="차량 출고가 5,400만 원 (100% 구간) 프리셋 적용"
                    onClick={() => handleSetPresetMsrp('54000000')}
                    className="px-2.5 py-1 min-h-[44px] inline-flex items-center justify-center text-xs rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
                  >
                    5,400만 원 (100% 구간)
                  </button>
                  <button
                    type="button"
                    aria-label="차량 출고가 6,200만 원 (50% 감액 구간) 프리셋 적용"
                    onClick={() => handleSetPresetMsrp('62000000')}
                    className="px-2.5 py-1 min-h-[44px] inline-flex items-center justify-center text-xs rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
                  >
                    6,200만 원 (50% 감액)
                  </button>
                  <button
                    type="button"
                    aria-label="차량 출고가 8,600만 원 (보조금 0원 구간) 프리셋 적용"
                    onClick={() => handleSetPresetMsrp('86000000')}
                    className="px-2.5 py-1 min-h-[44px] inline-flex items-center justify-center text-xs rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
                  >
                    8,600만 원 (보조금 0원)
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* 4. Special Additional Grants & Incentives */}
          <div className="space-y-2.5 p-4 bg-slate-950 border border-slate-800 rounded-2xl">
            <div className="text-xs font-bold text-slate-300 uppercase tracking-wider">
              3. 추가 지원금 &amp; 특별 가산 혜택 (해당 시 선택)
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
              <label htmlFor="grant-youth-buyer-checkbox" className="flex items-center gap-2 p-2 min-h-[44px] rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 cursor-pointer select-none">
                <input
                  id="grant-youth-buyer-checkbox"
                  type="checkbox"
                  aria-label="청년 생애 최초 구매 (+20% 국비)"
                  checked={calcOptions.isYouthFirstTimeBuyer}
                  onChange={handleToggleYouthBuyer}
                  className="w-5 h-5 rounded bg-slate-800 border-slate-700 text-amber-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
                />
                <span>청년 생애 최초 구매 (+20% 국비)</span>
              </label>

              <label htmlFor="grant-small-business-checkbox" className="flex items-center gap-2 p-2 min-h-[44px] rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 cursor-pointer select-none">
                <input
                  id="grant-small-business-checkbox"
                  type="checkbox"
                  aria-label="소상공인 / 영업용 택시 (+30% 국비)"
                  checked={calcOptions.isSmallBusinessOrTaxi}
                  onChange={handleToggleSmallBusiness}
                  className="w-5 h-5 rounded bg-slate-800 border-slate-700 text-amber-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
                />
                <span>소상공인 / 영업용 택시 (+30% 국비)</span>
              </label>

              <label htmlFor="grant-multi-child-checkbox" className="flex items-center gap-2 p-2 min-h-[44px] rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 cursor-pointer select-none">
                <input
                  id="grant-multi-child-checkbox"
                  type="checkbox"
                  aria-label="다자녀 가구 (+10% 국비)"
                  checked={calcOptions.isMultiChildFamily}
                  onChange={handleToggleMultiChild}
                  className="w-5 h-5 rounded bg-slate-800 border-slate-700 text-amber-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
                />
                <span>다자녀 가구 (+10% 국비)</span>
              </label>

              <label htmlFor="grant-diesel-scrappage-checkbox" className="flex items-center gap-2 p-2 min-h-[44px] rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 cursor-pointer select-none">
                <input
                  id="grant-diesel-scrappage-checkbox"
                  type="checkbox"
                  aria-label="노후 경유차 조기폐차 (+100만 원)"
                  checked={calcOptions.isOldDieselScrappage}
                  onChange={handleToggleOldDiesel}
                  className="w-5 h-5 rounded bg-slate-800 border-slate-700 text-amber-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
                />
                <span>노후 경유차 조기폐차 (+100만 원)</span>
              </label>
            </div>
          </div>
        </div>

        {/* Right Column: Live Output & Net Price Card */}
        <div
          role="region"
          aria-labelledby="calc-summary-heading"
          className="lg:col-span-5 bg-slate-950 border border-slate-800 rounded-3xl p-6 sm:p-7 space-y-6 shadow-2xl sticky top-24"
        >
          <div>
            <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
              시뮬레이션 견적 요약
            </span>
            <h3 id="calc-summary-heading" className="text-xl font-bold text-white mt-1">
              {calculationResult.modelName}
            </h3>
            <div className="text-xs text-blue-300 font-medium mt-0.5">
              등록 지역: {calculationResult.regionName} {activeRegionForCalc?.name_en ? `(${activeRegionForCalc.name_en})` : ''}
            </div>
          </div>

          {/* Price Breakdown Matrix */}
          <div className="space-y-2.5 text-sm border-t border-slate-800 pt-4">
            <div className="flex justify-between items-center text-slate-300">
              <span>차량 출고가 (MSRP)</span>
              <span className="font-semibold text-slate-100">
                {(Number.isFinite(calculationResult.msrpKrw) ? calculationResult.msrpKrw : 0).toLocaleString()}원
              </span>
            </div>

            <div className="flex justify-between items-center text-xs text-slate-300">
              <span>가격상한제 적용 구간</span>
              <span className="font-medium text-amber-300">
                {calculationResult.priceCapTierText}
              </span>
            </div>

            <div className="flex justify-between items-center text-blue-400">
              <span>(-) 국비 보조금</span>
              <span className="font-semibold">
                -{(Number.isFinite(calculationResult.nationalSubsidyKrw) ? calculationResult.nationalSubsidyKrw : 0).toLocaleString()}원
              </span>
            </div>

            <div className="flex justify-between items-center text-blue-400">
              <span>(-) 지자체 지방비 보조금</span>
              <span className="font-semibold">
                -{(Number.isFinite(calculationResult.localSubsidyKrw) ? calculationResult.localSubsidyKrw : 0).toLocaleString()}원
              </span>
            </div>

            {(calculationResult.additionalGrantsKrw ?? 0) > 0 && (
              <div className="flex justify-between items-center text-emerald-400">
                <span>(-) 추가 지원 &amp; 특별 가산금</span>
                <span className="font-semibold">
                  -{(Number.isFinite(calculationResult.additionalGrantsKrw) ? calculationResult.additionalGrantsKrw : 0).toLocaleString()}원
                </span>
              </div>
            )}

            <div className="h-px bg-slate-800 my-2" />

            {/* Total Subsidy Combined */}
            <div className="flex justify-between items-center text-xs text-slate-300">
              <span>총 지원 혜택 금액</span>
              <span className="font-bold text-slate-200">
                {(Number.isFinite(calculationResult.totalSubsidyKrw) ? calculationResult.totalSubsidyKrw : 0).toLocaleString()}원
              </span>
            </div>
          </div>

          {/* Net Out-of-pocket Purchase Price */}
          <div
            role="status"
            aria-live="polite"
            aria-atomic="true"
            className="bg-gradient-to-r from-emerald-950 to-slate-900 border border-emerald-500/40 rounded-2xl p-5 text-center space-y-1"
          >
            <span className="text-xs text-emerald-300 font-semibold uppercase tracking-wider">
              최종 실구매 체감가 (소비자 부담액)
            </span>
            <div className="text-3xl sm:text-4xl font-black text-emerald-400 tracking-tight">
              {Math.round((Number.isFinite(calculationResult.netPurchasePriceKrw) ? calculationResult.netPurchasePriceKrw : 0) / 10000).toLocaleString()}
              <span className="text-xl sm:text-2xl font-bold ml-1 text-emerald-200">만 원</span>
            </div>
            <div className="text-[11px] text-emerald-300">
              (정확한 금액: {(Number.isFinite(calculationResult.netPurchasePriceKrw) ? calculationResult.netPurchasePriceKrw : 0).toLocaleString()}원)
            </div>
          </div>

          {/* Depletion Risk Warning Alert */}
          <div
            className={`p-4 rounded-2xl border text-xs leading-relaxed space-y-1.5 ${
              calculationResult.isHighDepletionRisk
                ? 'bg-rose-950 border-rose-500/60 text-rose-200'
                : 'bg-emerald-950 border-emerald-500/40 text-emerald-200'
            }`}
          >
            <div className="font-bold flex items-center gap-1.5">
              <span>{calculationResult.isHighDepletionRisk ? '🚨' : '✅'}</span>
              <span>{calculationResult.regionName} 보조금 예산 소진 위험도 분석</span>
            </div>
            <p>{calculationResult.warningNotice}</p>
            <div className="text-[11px] text-slate-300 pt-1 border-t border-slate-800 flex flex-wrap justify-between gap-1">
              <span>거주 요건: 최소 {Number.isFinite(calculationResult.residencyRequirementDays) ? calculationResult.residencyRequirementDays : 30}일 이상</span>
              <span>2년 의무 운행 기간 (관외 이전 시 환수)</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
});
