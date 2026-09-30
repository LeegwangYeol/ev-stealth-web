'use client';

import React, { useState, useMemo, useRef, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  EVSubsidyDataset,
  AlertSeverity,
  CategoryMetrics,
  SubsidyCalculatorOptions,
} from '@/types/subsidy';
import { calculateNetSubsidy } from '@/lib/getSubsidyData';

interface SubsidyTrackerClientProps {
  initialData: EVSubsidyDataset;
}

type CategoryType = 'passenger' | 'commercial' | 'bus';
type ZoneFilter = 'ALL' | 'CAPITAL' | 'YEONGNAM' | 'HONAM' | 'CHUNGCHEONG' | 'GANGWON_JEJU';
type SortOption = 'DEPLETION_DESC' | 'DEPLETION_ASC' | 'REMAINING_ASC' | 'LOCAL_SUBSIDY_DESC' | 'NAME_ASC';

export default function SubsidyTrackerClient({ initialData }: SubsidyTrackerClientProps) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  const searchParams = useSearchParams();
  const urlRegion = searchParams?.get('region') || '';
  const urlModel = searchParams?.get('model') || '';

  // State
  const [selectedCategory, setSelectedCategory] = useState<CategoryType>('passenger');
  const [zoneFilter, setZoneFilter] = useState<ZoneFilter>('ALL');
  const [alertFilter, setAlertFilter] = useState<AlertSeverity | 'ALL'>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortOption, setSortOption] = useState<SortOption>('DEPLETION_DESC');
  const [supplementaryOnly, setSupplementaryOnly] = useState(false);
  const [expandedRegions, setExpandedRegions] = useState<Record<string, boolean>>({});

  // Calculator State
  const calculatorRef = useRef<HTMLDivElement>(null);
  const [selectedModelId, setSelectedModelId] = useState<string>(
    urlModel || initialData.popular_models_matrix[0]?.model_id || 'ioniq-5-2026'
  );
  const [selectedRegionId, setSelectedRegionId] = useState<string>(
    urlRegion || initialData.regions[0]?.region_id || 'KR-11'
  );
  const [isCustomMsrp, setIsCustomMsrp] = useState(false);
  const [customMsrpInput, setCustomMsrpInput] = useState<string>('');
  const [calcOptions, setCalcOptions] = useState<SubsidyCalculatorOptions>({
    isYouthFirstTimeBuyer: false,
    isSmallBusinessOrTaxi: false,
    isMultiChildFamily: false,
    isOldDieselScrappage: false,
  });

  const regions = useMemo(() => initialData.regions || [], [initialData.regions]);
  const models = useMemo(() => initialData.popular_models_matrix || [], [initialData.popular_models_matrix]);
  const summary = initialData.nationwide_summary;
  const thresholds = initialData.alert_thresholds;

  // Zone categorizer helper
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

  // Filtered & Sorted Regions
  const filteredRegions = useMemo(() => {
    return regions
      .filter((region) => {
        // Category Metrics
        const catMetrics: CategoryMetrics = region.categories[selectedCategory];
        if (!catMetrics) return false;

        // Zone filter
        if (zoneFilter !== 'ALL' && getRegionZone(region.iso_code) !== zoneFilter) {
          return false;
        }

        // Alert filter
        if (alertFilter !== 'ALL' && catMetrics.status !== alertFilter) {
          return false;
        }

        // Supplementary budget filter
        if (supplementaryOnly && !region.supplementary_budget_added) {
          return false;
        }

        // Search Query
        if (searchQuery.trim()) {
          const q = searchQuery.trim().toLowerCase();
          const matchRegion =
            region.name_ko.toLowerCase().includes(q) ||
            region.name_en.toLowerCase().includes(q) ||
            region.iso_code.toLowerCase().includes(q);

          const matchMuni =
            region.municipalities?.some((m) => m.name_ko.toLowerCase().includes(q)) ?? false;

          if (!matchRegion && !matchMuni) return false;
        }

        return true;
      })
      .sort((a, b) => {
        const catA = a.categories[selectedCategory];
        const catB = b.categories[selectedCategory];

        switch (sortOption) {
          case 'DEPLETION_DESC':
            return catB.depletion_rate - catA.depletion_rate;
          case 'DEPLETION_ASC':
            return catA.depletion_rate - catB.depletion_rate;
          case 'REMAINING_ASC':
            return catA.remaining_units - catB.remaining_units;
          case 'LOCAL_SUBSIDY_DESC':
            return catB.max_local_subsidy_krw - catA.max_local_subsidy_krw;
          case 'NAME_ASC':
            return a.name_ko.localeCompare(b.name_ko, 'ko');
          default:
            return 0;
        }
      });
  }, [regions, selectedCategory, zoneFilter, alertFilter, supplementaryOnly, searchQuery, sortOption]);

  // Critical regions (for emergency ticker)
  const criticalRegions = useMemo(() => {
    return regions.filter(
      (r) =>
        r.categories.passenger.status === 'CRITICAL' ||
        r.categories.passenger.status === 'DEPLETED' ||
        r.categories.passenger.depletion_rate >= 95.0
    );
  }, [regions]);

  // Active Model
  const activeModel = useMemo(() => {
    return models.find((m) => m.model_id === selectedModelId) || models[0];
  }, [models, selectedModelId]);

  // Active Region for Calculator
  const activeRegionForCalc = useMemo(() => {
    return regions.find((r) => r.region_id === selectedRegionId) || regions[0];
  }, [regions, selectedRegionId]);

  // Net Subsidy Calculation
  const calculationResult = useMemo(() => {
    const customMsrpNum = isCustomMsrp && customMsrpInput ? parseInt(customMsrpInput.replace(/[^0-9]/g, ''), 10) : undefined;
    return calculateNetSubsidy(selectedModelId, selectedRegionId, customMsrpNum, calcOptions);
  }, [selectedModelId, selectedRegionId, isCustomMsrp, customMsrpInput, calcOptions]);

  // Quick Action: Select region and jump to calculator
  const handleSelectRegionForCalc = (regionId: string) => {
    setSelectedRegionId(regionId);
    if (calculatorRef.current) {
      calculatorRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  const toggleRegionExpand = (regionId: string) => {
    setExpandedRegions((prev) => ({
      ...prev,
      [regionId]: !prev[regionId],
    }));
  };

  // Helper for alert colors & badges
  const getBadgeStyle = (status: AlertSeverity) => {
    switch (status) {
      case 'HEALTHY':
        return 'bg-emerald-950/80 text-emerald-300 border-emerald-500/50';
      case 'CAUTION':
        return 'bg-amber-950/80 text-amber-300 border-amber-500/50';
      case 'WARNING':
        return 'bg-orange-950/80 text-orange-300 border-orange-500/50';
      case 'CRITICAL':
        return 'bg-rose-950/80 text-rose-300 border-rose-500/50';
      case 'DEPLETED':
        return 'bg-zinc-800 text-zinc-300 border-zinc-600';
    }
  };

  const getStatusLabel = (status: AlertSeverity) => {
    switch (status) {
      case 'HEALTHY':
        return '🟢 안정';
      case 'CAUTION':
        return '🟡 주의';
      case 'WARNING':
        return '🟠 경고';
      case 'CRITICAL':
        return '🔴 마감임박';
      case 'DEPLETED':
        return '🔒 소진';
    }
  };

  return (
    <div className="space-y-10 py-6 text-slate-100 max-w-6xl mx-auto">
      {/* Skip Navigation for Keyboard Accessibility */}
      <a
        href="#subsidy-calculator"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2.5 focus:bg-amber-400 focus:text-slate-950 focus:font-bold focus:rounded-xl focus:shadow-2xl focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none transition"
      >
        보조금 계산기로 건너뛰기
      </a>

      {/* 1. Header Banner & Live Tracker Status */}
      <section aria-labelledby="tracker-heading" className="bg-slate-900 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-gradient-to-bl from-amber-500/10 via-blue-500/5 to-transparent rounded-full blur-3xl pointer-events-none" />

        <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-950/80 border border-emerald-500/40 text-emerald-300 text-xs font-semibold tracking-wide">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping inline-block" />
              실시간 스케줄러 동기화 완료
            </span>
            <span className="text-xs text-slate-400">
              기준: 2026년 환경부 무공해차 통합누리집 (ev.or.kr)
            </span>
          </div>
          <span className="text-xs text-slate-400" suppressHydrationWarning>
            데이터 갱신 시각:{' '}
            {mounted && initialData.metadata?.generated_at
              ? new Date(initialData.metadata.generated_at).toLocaleDateString('ko-KR', {
                  month: 'long',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                })
              : initialData.metadata?.generated_at
                ? initialData.metadata.generated_at.replace('T', ' ').substring(0, 16) + ' (UTC)'
                : '방금 전'}
          </span>
        </div>

        <div className="max-w-3xl space-y-3">
          <h1 id="tracker-heading" className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white flex items-center gap-3">
            <span className="text-amber-400 text-3xl sm:text-4xl">⚡</span>
            전국 지자체별 전기차 실시간 보조금 소진율 추적기
          </h1>
          <p className="text-slate-300 text-sm sm:text-base leading-relaxed">
            전국 17개 광역시도 및 73개 주요 지자체의 <strong>전기승용·화물·승합 공고 쿼터</strong>, 접수·출고 현황, 실시간 소진율을 5단계 경보로 감시합니다. 출고 전 <strong>내 거주지 잔여 예산</strong>을 확인하고 실구매 체감가를 원스톱으로 산출하세요.
          </p>
        </div>

        {/* Live Nationwide Stat Cards */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 sm:gap-4 mt-8 pt-6 border-t border-slate-800">
          <div className="bg-slate-950/60 border border-slate-800 rounded-2xl p-4 flex flex-col justify-between">
            <div className="text-xs font-medium text-slate-400">전국 평균 소진율</div>
            <div className="text-2xl sm:text-3xl font-extrabold text-amber-400 mt-1">
              {summary.nationwide_depletion_rate.toFixed(1)}%
            </div>
            <div className="text-[11px] text-slate-400 mt-1">
              전체 카테고리 종합
            </div>
          </div>

          <div className="bg-slate-950/60 border border-slate-800 rounded-2xl p-4 flex flex-col justify-between">
            <div className="text-xs font-medium text-slate-400">총 공고 대수</div>
            <div className="text-2xl sm:text-3xl font-extrabold text-slate-100 mt-1">
              {summary.total_announced_units.toLocaleString()}
              <span className="text-xs font-normal text-slate-400 ml-1">대</span>
            </div>
            <div className="text-[11px] text-slate-400 mt-1">
              총 배정 예산 {summary.total_budget_billion_krw.toLocaleString()}억 원
            </div>
          </div>

          <div className="bg-slate-950/60 border border-slate-800 rounded-2xl p-4 flex flex-col justify-between">
            <div className="text-xs font-medium text-slate-400">총 접수 대수</div>
            <div className="text-2xl sm:text-3xl font-extrabold text-blue-400 mt-1">
              {summary.total_applied_units.toLocaleString()}
              <span className="text-xs font-normal text-slate-400 ml-1">대</span>
            </div>
            <div className="text-[11px] text-slate-400 mt-1">
              출고 완료: {summary.total_delivered_units.toLocaleString()}대
            </div>
          </div>

          <div className="bg-slate-950/60 border border-slate-800 rounded-2xl p-4 flex flex-col justify-between">
            <div className="text-xs font-medium text-slate-400">전국 잔여 대수</div>
            <div className="text-2xl sm:text-3xl font-extrabold text-emerald-400 mt-1">
              {summary.total_remaining_units.toLocaleString()}
              <span className="text-xs font-normal text-slate-400 ml-1">대</span>
            </div>
            <div className="text-[11px] text-slate-400 mt-1">
              잔여율 {(100 - summary.nationwide_depletion_rate).toFixed(1)}%
            </div>
          </div>

          <div className="col-span-2 md:col-span-1 bg-rose-950/40 border border-rose-500/40 rounded-2xl p-4 flex flex-col justify-between">
            <div className="text-xs font-medium text-rose-300">긴급 마감 위험 지역</div>
            <div className="text-2xl sm:text-3xl font-extrabold text-rose-400 mt-1">
              {summary.alert_region_counts.critical + summary.alert_region_counts.depleted}
              <span className="text-xs font-normal text-rose-300 ml-1">개 시도</span>
            </div>
            <div className="text-[11px] text-rose-300/80 mt-1">
              소진율 95% 이상 극소량
            </div>
          </div>
        </div>

        {/* Emergency Alert Ticker for Critical Municipalities */}
        {criticalRegions.length > 0 && (
          <div className="mt-6 bg-rose-950/40 border border-rose-500/50 rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs sm:text-sm">
            <div className="flex items-center gap-2 text-rose-200">
              <span className="text-base">🚨</span>
              <strong className="text-rose-100 font-semibold">마감 임박 특보 (소진율 95% 초과):</strong>
              <div className="flex flex-wrap gap-1.5 ml-1">
                {criticalRegions.map((crit) => (
                  <button
                    key={crit.region_id}
                    type="button"
                    onClick={() => {
                      setSearchQuery(crit.name_ko);
                      handleSelectRegionForCalc(crit.region_id);
                    }}
                    className="px-2 py-0.5 rounded bg-rose-900/60 border border-rose-500/50 text-rose-200 hover:bg-rose-800 hover:text-white transition font-medium focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none"
                    title={`${crit.name_ko} 보조금 계산기로 이동`}
                  >
                    {crit.name_ko} ({crit.categories.passenger.depletion_rate}%)
                  </button>
                ))}
              </div>
            </div>
            <a
              href="#subsidy-calculator"
              className="text-amber-300 hover:text-amber-200 underline font-semibold shrink-0 rounded px-1 focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none"
            >
              내 차 실구매가 즉시 계산 &rarr;
            </a>
          </div>
        )}
      </section>

      {/* 2. 5-Tier Alert Badges Legend & Quick Filter */}
      <section aria-label="보조금 소진 5단계 경보 범례" className="bg-slate-900/70 border border-slate-800 rounded-2xl p-5">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <h2 className="text-sm font-bold text-slate-300 flex items-center gap-2">
            <span>🛡️</span> 전국 지자체 보조금 소진 5단계 경보 기준
          </h2>
          <span className="text-xs text-slate-200">배지 클릭 시 해당 경보 지역만 필터링</span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
          {(Object.keys(thresholds) as AlertSeverity[]).map((key) => {
            const t = thresholds[key];
            const isSelected = alertFilter === key;
            return (
              <button
                key={key}
                type="button"
                onClick={() => setAlertFilter(isSelected ? 'ALL' : key)}
                className={`p-3 rounded-xl border text-left transition flex flex-col justify-between focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none ${
                  isSelected
                    ? 'ring-2 ring-amber-400 ' + getBadgeStyle(key)
                    : 'bg-slate-950/60 hover:bg-slate-800/80 border-slate-800 text-slate-300'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-xs px-2 py-0.5 rounded font-semibold border ${getBadgeStyle(key)}`}>
                    {getStatusLabel(key)}
                  </span>
                  <span className="text-[11px] text-slate-400">{t.min_percent}%~{t.max_percent}%</span>
                </div>
                <div className="text-[11px] text-slate-400 line-clamp-2 mt-2 leading-relaxed">
                  {t.recommended_action}
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {/* 3. Search & Filter Bar */}
      <section aria-label="지자체 검색 및 정렬 제어판" className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          {/* Vehicle Category Selector */}
          <div className="flex items-center gap-1.5 p-1 bg-slate-950 rounded-xl border border-slate-800 text-xs sm:text-sm font-semibold">
            <button
              type="button"
              onClick={() => setSelectedCategory('passenger')}
              className={`px-3 py-1.5 rounded-lg transition focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none ${
                selectedCategory === 'passenger'
                  ? 'bg-blue-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              🚗 전기승용 (승용차)
            </button>
            <button
              type="button"
              onClick={() => setSelectedCategory('commercial')}
              className={`px-3 py-1.5 rounded-lg transition focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none ${
                selectedCategory === 'commercial'
                  ? 'bg-blue-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              🚚 전기화물 (소형/특장)
            </button>
            <button
              type="button"
              onClick={() => setSelectedCategory('bus')}
              className={`px-3 py-1.5 rounded-lg transition focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none ${
                selectedCategory === 'bus'
                  ? 'bg-blue-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              🚌 전기승합 (버스)
            </button>
          </div>

          {/* Supplementary Budget Toggle */}
          <label className="flex items-center gap-2 cursor-pointer text-xs sm:text-sm text-slate-300 hover:text-white select-none">
            <input
              type="checkbox"
              checked={supplementaryOnly}
              onChange={(e) => setSupplementaryOnly(e.target.checked)}
              className="w-4 h-4 rounded bg-slate-800 border-slate-700 text-amber-500 focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none"
            />
            <span>추경 예산 편성 지자체만 보기</span>
          </label>
        </div>

        {/* Zone Filters & Search Input */}
        <div className="flex flex-col md:flex-row gap-3 pt-2">
          {/* Search Box */}
          <div className="relative flex-1">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400 text-sm">
              🔍
            </div>
            <input
              id="region-search-input"
              type="text"
              aria-label="지자체 검색"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="시·도 또는 세부 시·군·구 검색 (예: 서울, 수원, 성남, 대구, 포항, 울릉)"
              className="w-full pl-10 pr-9 py-2.5 rounded-xl bg-slate-950 border border-slate-700 text-white placeholder-slate-400 text-sm focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                aria-label="검색어 지우기"
                className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-white text-sm rounded focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none"
              >
                ✕
              </button>
            )}
          </div>

          {/* Regional Zone Pills */}
          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            {[
              { id: 'ALL', label: '전국 전체' },
              { id: 'CAPITAL', label: '수도권 (서울/경기/인천)' },
              { id: 'YEONGNAM', label: '영남권 (부산/대구/울산/경북/경남)' },
              { id: 'HONAM', label: '호남권 (광주/전남/전북)' },
              { id: 'CHUNGCHEONG', label: '충청권 (대전/세종/충남/충북)' },
              { id: 'GANGWON_JEJU', label: '강원/제주' },
            ].map((zone) => (
              <button
                key={zone.id}
                type="button"
                onClick={() => setZoneFilter(zone.id as ZoneFilter)}
                className={`px-2.5 py-1.5 rounded-lg border font-medium transition focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none ${
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
            <select
              value={sortOption}
              onChange={(e) => setSortOption(e.target.value as SortOption)}
              aria-label="지자체 정렬 방식"
              className="py-2.5 px-3 rounded-xl bg-slate-950 border border-slate-700 text-slate-200 text-xs sm:text-sm focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none cursor-pointer"
            >
              <option value="DEPLETION_DESC">소진율 높은 순 (마감임박)</option>
              <option value="DEPLETION_ASC">소진율 낮은 순 (신청여유)</option>
              <option value="REMAINING_ASC">잔여 대수 적은 순</option>
              <option value="LOCAL_SUBSIDY_DESC">지자체 보조금 높은 순</option>
              <option value="NAME_ASC">지역명 가나다순</option>
            </select>
          </div>
        </div>

        {/* Active Filter Clear indicator */}
        {(zoneFilter !== 'ALL' || alertFilter !== 'ALL' || searchQuery || supplementaryOnly) && (
          <div className="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-800">
            <span>
              필터 적용 중: 총 <strong>{filteredRegions.length}</strong>개 지역 표시 중
            </span>
            <button
              type="button"
              onClick={() => {
                setZoneFilter('ALL');
                setAlertFilter('ALL');
                setSearchQuery('');
                setSupplementaryOnly(false);
              }}
              className="text-amber-400 hover:text-amber-300 underline font-medium rounded px-1 focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none"
            >
              전체 필터 초기화
            </button>
          </div>
        )}
      </section>

      {/* 4. 17 Regional Grid Cards */}
      <section aria-labelledby="regional-grid-heading" className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 id="regional-grid-heading" className="text-xl sm:text-2xl font-bold text-slate-900 flex items-center gap-2">
            <span>🗺️</span> 17개 광역시도별 보조금 소진율 &amp; 잔여 쿼터 현황
          </h2>
          <span className="text-xs text-slate-600">
            {selectedCategory === 'passenger' ? '전기승용 기준' : selectedCategory === 'commercial' ? '전기화물 기준' : '전기승합 기준'}
          </span>
        </div>

        {filteredRegions.length === 0 ? (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-12 text-center text-slate-400">
            <div className="text-3xl mb-2">🔍</div>
            <div className="text-base font-semibold text-slate-300">검색 및 필터 조건에 일치하는 지자체가 없습니다.</div>
            <p className="text-xs text-slate-400 mt-1">검색어를 변경하거나 필터를 초기화해 보세요.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredRegions.map((region) => {
              const cat = region.categories[selectedCategory];
              const isExpanded = !!expandedRegions[region.region_id];
              const deliveredPct = Math.min(100, Math.round((cat.delivered_units / (cat.announced_units || 1)) * 100));
              const pendingPct = Math.max(0, Math.min(100 - deliveredPct, cat.depletion_rate - deliveredPct));
              const remainingPct = Math.max(0, 100 - (deliveredPct + pendingPct));

              return (
                <div
                  key={region.region_id}
                  className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg hover:border-slate-700 transition flex flex-col justify-between"
                >
                  <div className="space-y-3">
                    {/* Card Header */}
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="text-lg font-bold text-white">{region.name_ko}</h3>
                          <span className="text-[10px] text-slate-400 uppercase font-mono">{region.iso_code}</span>
                        </div>
                        <div className="text-xs text-slate-400">{region.name_en}</div>
                      </div>
                      <span className={`px-2.5 py-1 rounded-lg text-xs font-bold border ${getBadgeStyle(cat.status)}`}>
                        {getStatusLabel(cat.status)}
                      </span>
                    </div>

                    {/* Progress Bar (Dual Layer: Delivered vs Pending vs Remaining) */}
                    <div className="space-y-1.5 pt-1">
                      <div className="flex justify-between items-center text-xs">
                        <span className="font-semibold text-slate-300">
                          소진율 <strong className="text-amber-400 text-sm">{cat.depletion_rate.toFixed(1)}%</strong>
                        </span>
                        <span className="text-slate-400 text-[11px]">
                          잔여 <strong className="text-emerald-400 font-bold">{cat.remaining_units.toLocaleString()}</strong> / {cat.announced_units.toLocaleString()}대
                        </span>
                      </div>

                      <div
                        role="progressbar"
                        aria-valuenow={Math.min(100, Math.round(cat.depletion_rate))}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-label={`${region.name_ko} ${selectedCategory === 'passenger' ? '전기승용' : selectedCategory === 'commercial' ? '전기화물' : '전기승합'} 보조금 소진율`}
                        aria-valuetext={`소진율 ${cat.depletion_rate.toFixed(1)}% (${getStatusLabel(cat.status)}), 잔여 ${cat.remaining_units.toLocaleString()}대`}
                        className="w-full bg-slate-950 rounded-full h-3.5 overflow-hidden flex relative border border-slate-800"
                      >
                        {/* Layer 1: Confirmed Delivered */}
                        <div
                          style={{ width: `${deliveredPct}%` }}
                          className="bg-blue-500 h-full transition-all duration-500"
                          title={`출고 완료: ${cat.delivered_units.toLocaleString()}대 (${deliveredPct}%)`}
                        />
                        {/* Layer 2: Pending Applications */}
                        <div
                          style={{ width: `${pendingPct}%` }}
                          className="bg-amber-500 h-full transition-all duration-500"
                          title={`접수 대기: ${(cat.applied_units - cat.delivered_units).toLocaleString()}대 (${pendingPct.toFixed(1)}%)`}
                        />
                        {/* Layer 3: Remaining (slate track) */}
                        <div
                          style={{ width: `${remainingPct}%` }}
                          className="bg-slate-800/80 h-full"
                          title={`잔여: ${cat.remaining_units.toLocaleString()}대 (${remainingPct.toFixed(1)}%)`}
                        />
                      </div>

                      <div className="flex justify-between text-[10px] text-slate-400">
                        <span className="flex items-center gap-1">
                          <span className="w-2 h-2 rounded-full bg-blue-500 inline-block" />
                          출고 {cat.delivered_units.toLocaleString()}대
                        </span>
                        <span className="flex items-center gap-1">
                          <span className="w-2 h-2 rounded-full bg-amber-500 inline-block" />
                          심사중 {(cat.applied_units - cat.delivered_units).toLocaleString()}대
                        </span>
                        <span className="flex items-center gap-1">
                          <span className="w-2 h-2 rounded-full bg-slate-700 inline-block" />
                          잔여 {cat.remaining_units.toLocaleString()}대
                        </span>
                      </div>
                    </div>

                    {/* Financial Subsidy Limits */}
                    <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-800/80 text-xs">
                      <div className="bg-slate-950/70 p-2.5 rounded-xl border border-slate-800">
                        <div className="text-[11px] text-slate-400">지자체 최대 지원금</div>
                        <div className="text-sm font-bold text-slate-200 mt-0.5">
                          {(cat.max_local_subsidy_krw / 10000).toLocaleString()}만 원
                        </div>
                      </div>
                      <div className="bg-slate-950/70 p-2.5 rounded-xl border border-slate-800">
                        <div className="text-[11px] text-slate-400">국비+지방비 합산 최대</div>
                        <div className="text-sm font-bold text-amber-400 mt-0.5">
                          {(cat.max_total_subsidy_krw / 10000).toLocaleString()}만 원
                        </div>
                      </div>
                    </div>

                    {/* Eligibility & Notes */}
                    <div className="flex flex-wrap gap-1.5 pt-1 text-[11px]">
                      <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                        거주 요건: {region.residency_requirement_days}일 이상
                      </span>
                      {region.supplementary_budget_added && (
                        <span className="px-2 py-0.5 rounded bg-emerald-950/70 text-emerald-300 border border-emerald-500/40 font-semibold">
                          추경 완료
                        </span>
                      )}
                    </div>

                    {region.notes && (
                      <p className="text-xs text-slate-400 leading-relaxed bg-slate-950/40 p-2 rounded-lg border border-slate-800/50">
                        ℹ️ {region.notes}
                      </p>
                    )}

                    {/* Municipalities Collapsible (if province has sub-cities) */}
                    {region.municipalities && region.municipalities.length > 0 && (
                      <div className="pt-2">
                        <button
                          type="button"
                          onClick={() => toggleRegionExpand(region.region_id)}
                          className="w-full py-1.5 px-3 rounded-lg bg-slate-950 hover:bg-slate-800 text-slate-300 text-xs font-medium flex items-center justify-between transition border border-slate-800 focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none"
                        >
                          <span>세부 시·군·구 {region.municipalities.length}개 현황 보기</span>
                          <span>{isExpanded ? '▲ 접기' : '▼ 펼치기'}</span>
                        </button>

                        {isExpanded && (
                          <div className="mt-2 space-y-1.5 max-h-48 overflow-y-auto pr-1 text-xs">
                            {region.municipalities.map((muni) => (
                              <div
                                key={muni.name_ko}
                                className="p-2 rounded bg-slate-950/90 border border-slate-800 flex items-center justify-between text-[11px]"
                              >
                                <div>
                                  <span className="font-semibold text-slate-200">{muni.name_ko}</span>
                                  <span className="text-slate-400 ml-2">
                                    {(muni.local_subsidy_krw / 10000).toLocaleString()}만 원
                                  </span>
                                </div>
                                <div className="flex items-center gap-2">
                                  <span className="text-slate-400">잔여 {muni.remaining_units}대</span>
                                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${getBadgeStyle(muni.status)}`}>
                                    {getStatusLabel(muni.status)} {muni.depletion_rate.toFixed(1)}%
                                  </span>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Card Action Button */}
                  <div className="pt-4 mt-3 border-t border-slate-800">
                    <button
                      type="button"
                      onClick={() => handleSelectRegionForCalc(region.region_id)}
                      className="w-full py-2.5 px-4 rounded-xl bg-blue-600/90 hover:bg-blue-600 text-white font-semibold text-xs transition flex items-center justify-center gap-1.5 shadow focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none"
                    >
                      <span>⚡</span> 이 지역({region.name_ko})으로 실구매가 계산
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* 5. Interactive Real-Time Net Subsidy Calculator */}
      <section
        id="subsidy-calculator"
        ref={calculatorRef}
        aria-labelledby="calculator-heading"
        className="bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-950 border border-blue-500/30 rounded-3xl p-6 sm:p-8 shadow-2xl space-y-8"
      >
        <div className="max-w-3xl space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/20 text-blue-300 border border-blue-400/30 text-xs font-bold uppercase tracking-wider">
            <span>💡</span> 실시간 인터랙티브 시뮬레이터
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
                value={selectedModelId}
                onChange={(e) => setSelectedModelId(e.target.value)}
                className="w-full py-3 px-3.5 rounded-xl bg-slate-950 border border-slate-700 text-white text-sm focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none cursor-pointer font-medium"
              >
                {models.map((model) => (
                  <option key={model.model_id} value={model.model_id}>
                    {model.manufacturer} - {model.name_ko} (출고가 {(model.base_price_krw / 10000).toLocaleString()}만 원)
                  </option>
                ))}
              </select>

              {/* Quick Pills for Top Models */}
              <div className="flex flex-wrap gap-1.5 pt-1">
                {models.slice(0, 8).map((m) => (
                  <button
                    key={m.model_id}
                    type="button"
                    onClick={() => setSelectedModelId(m.model_id)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-medium transition focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none ${
                      selectedModelId === m.model_id
                        ? 'bg-blue-600 text-white'
                        : 'bg-slate-950 text-slate-300 hover:bg-slate-800 border border-slate-800'
                    }`}
                  >
                    {m.name_ko.replace(/^(현대|기아|테슬라|KGM|비야디|BYD)\s+/, '')}
                  </button>
                ))}
              </div>

              {/* Selected Model Spec Card */}
              {activeModel && (
                <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-xl flex flex-wrap items-center justify-between text-xs text-slate-300 gap-2">
                  <span>배터리: <strong>{activeModel.battery_type}</strong> ({activeModel.battery_capacity_kwh} kWh)</span>
                  <span>1회 충전 주행거리: <strong>{activeModel.rated_range_km} km</strong></span>
                  <span>기본 출고가: <strong>{(activeModel.base_price_krw / 10000).toLocaleString()}만 원</strong></span>
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
                value={selectedRegionId}
                onChange={(e) => setSelectedRegionId(e.target.value)}
                aria-describedby="region-residency-note"
                className="w-full py-3 px-3.5 rounded-xl bg-slate-950 border border-slate-700 text-white text-sm focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none cursor-pointer font-medium"
              >
                {regions.map((reg) => (
                  <option key={reg.region_id} value={reg.region_id}>
                    {reg.name_ko} ({reg.categories.passenger.depletion_rate.toFixed(1)}% 소진, {getStatusLabel(reg.categories.passenger.status)})
                  </option>
                ))}
              </select>
              <p id="region-residency-note" className="text-xs text-amber-300/90 flex items-center gap-1.5 pt-0.5">
                <span>ℹ️</span> 해당 지자체 최소 <strong>{activeRegionForCalc.residency_requirement_days}일 이상</strong> 연속 거주 요건 필요
              </p>
            </div>

            {/* 3. Custom MSRP Option */}
            <div className="space-y-3 p-4 bg-slate-950/50 border border-slate-800 rounded-2xl">
              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 cursor-pointer select-none text-xs font-bold text-slate-300 uppercase tracking-wider">
                  <input
                    type="checkbox"
                    checked={isCustomMsrp}
                    onChange={(e) => {
                      setIsCustomMsrp(e.target.checked);
                      if (e.target.checked && !customMsrpInput && activeModel) {
                        setCustomMsrpInput(activeModel.base_price_krw.toString());
                      }
                    }}
                    className="w-4 h-4 rounded bg-slate-800 border-slate-700 text-amber-500 focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none"
                  />
                  <span>옵션 포함 출고가 직접 입력 (커스텀 MSRP)</span>
                </label>
                {isCustomMsrp && (
                  <span className="text-[11px] text-amber-400 font-medium">5,500만/8,500만 원 상한제 실시간 연동</span>
                )}
              </div>

              {isCustomMsrp && (
                <div className="space-y-1.5 pt-1">
                  <div className="relative">
                    <input
                      id="custom-msrp-input"
                      type="text"
                      inputMode="numeric"
                      aria-label="직접 차량 출고가 입력"
                      value={customMsrpInput ? parseInt(customMsrpInput, 10).toLocaleString('ko-KR') : ''}
                      onChange={(e) => setCustomMsrpInput(e.target.value.replace(/[^0-9]/g, ''))}
                      placeholder="원 단위 출고가 입력 (예: 54,900,000)"
                      className="w-full py-2.5 px-3.5 rounded-xl bg-slate-900 border border-slate-700 text-white text-sm font-semibold focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none pr-12"
                    />
                    <span className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 text-xs font-semibold">
                      원
                    </span>
                  </div>
                  <div className="flex gap-2 text-[11px]">
                    <button
                      type="button"
                      onClick={() => setCustomMsrpInput('54000000')}
                      className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none"
                    >
                      5,400만 (100% 구간)
                    </button>
                    <button
                      type="button"
                      onClick={() => setCustomMsrpInput('62000000')}
                      className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none"
                    >
                      6,200만 (50% 감액)
                    </button>
                    <button
                      type="button"
                      onClick={() => setCustomMsrpInput('86000000')}
                      className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none"
                    >
                      8,600만 (보조금 0원)
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* 4. Special Additional Grants & Incentives */}
            <div className="space-y-2.5 p-4 bg-slate-950/50 border border-slate-800 rounded-2xl">
              <div className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                3. 추가 지원금 &amp; 특별 가산 혜택 (해당 시 선택)
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                <label className="flex items-center gap-2 p-2 rounded-lg bg-slate-900/60 border border-slate-800 hover:bg-slate-800 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={calcOptions.isYouthFirstTimeBuyer}
                    onChange={(e) => setCalcOptions((prev) => ({ ...prev, isYouthFirstTimeBuyer: e.target.checked }))}
                    className="w-4 h-4 rounded bg-slate-800 border-slate-700 text-amber-500 focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none"
                  />
                  <span>청년 생애 최초 구매 (+20% 국비)</span>
                </label>

                <label className="flex items-center gap-2 p-2 rounded-lg bg-slate-900/60 border border-slate-800 hover:bg-slate-800 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={calcOptions.isSmallBusinessOrTaxi}
                    onChange={(e) => setCalcOptions((prev) => ({ ...prev, isSmallBusinessOrTaxi: e.target.checked }))}
                    className="w-4 h-4 rounded bg-slate-800 border-slate-700 text-amber-500 focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none"
                  />
                  <span>소상공인 / 영업용 택시 (+30% 국비)</span>
                </label>

                <label className="flex items-center gap-2 p-2 rounded-lg bg-slate-900/60 border border-slate-800 hover:bg-slate-800 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={calcOptions.isMultiChildFamily}
                    onChange={(e) => setCalcOptions((prev) => ({ ...prev, isMultiChildFamily: e.target.checked }))}
                    className="w-4 h-4 rounded bg-slate-800 border-slate-700 text-amber-500 focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none"
                  />
                  <span>다자녀 가구 (+10% 국비)</span>
                </label>

                <label className="flex items-center gap-2 p-2 rounded-lg bg-slate-900/60 border border-slate-800 hover:bg-slate-800 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={calcOptions.isOldDieselScrappage}
                    onChange={(e) => setCalcOptions((prev) => ({ ...prev, isOldDieselScrappage: e.target.checked }))}
                    className="w-4 h-4 rounded bg-slate-800 border-slate-700 text-amber-500 focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none"
                  />
                  <span>노후 경유차 조기폐차 (+100만 원)</span>
                </label>
              </div>
            </div>
          </div>

          {/* Right Column: Live Output & Net Price Card */}
          <div
            aria-live="polite"
            aria-atomic="true"
            className="lg:col-span-5 bg-slate-950 border border-slate-800 rounded-3xl p-6 sm:p-7 space-y-6 shadow-2xl sticky top-24"
          >
            <div>
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                시뮬레이션 견적 요약
              </span>
              <h3 className="text-xl font-bold text-white mt-1">
                {calculationResult.modelName}
              </h3>
              <div className="text-xs text-blue-300 font-medium mt-0.5">
                등록 지역: {calculationResult.regionName} ({activeRegionForCalc.name_en})
              </div>
            </div>

            {/* Price Breakdown Matrix */}
            <div className="space-y-2.5 text-sm border-t border-slate-800/80 pt-4">
              <div className="flex justify-between items-center text-slate-300">
                <span>차량 출고가 (MSRP)</span>
                <span className="font-semibold text-slate-100">
                  {calculationResult.msrpKrw.toLocaleString()} 원
                </span>
              </div>

              <div className="flex justify-between items-center text-xs text-slate-400">
                <span>가격상한제 적용 구간</span>
                <span className="font-medium text-amber-300">
                  {calculationResult.priceCapTierText}
                </span>
              </div>

              <div className="flex justify-between items-center text-blue-400">
                <span>(-) 국비 보조금</span>
                <span className="font-semibold">
                  -{calculationResult.nationalSubsidyKrw.toLocaleString()} 원
                </span>
              </div>

              <div className="flex justify-between items-center text-blue-400">
                <span>(-) 지자체 지방비 보조금</span>
                <span className="font-semibold">
                  -{calculationResult.localSubsidyKrw.toLocaleString()} 원
                </span>
              </div>

              {calculationResult.additionalGrantsKrw > 0 && (
                <div className="flex justify-between items-center text-emerald-400">
                  <span>(-) 추가 지원 &amp; 특별 가산금</span>
                  <span className="font-semibold">
                    -{calculationResult.additionalGrantsKrw.toLocaleString()} 원
                  </span>
                </div>
              )}

              <div className="h-px bg-slate-800 my-2" />

              {/* Total Subsidy Combined */}
              <div className="flex justify-between items-center text-xs text-slate-400">
                <span>총 지원 혜택 금액</span>
                <span className="font-bold text-slate-200">
                  {calculationResult.totalSubsidyKrw.toLocaleString()} 원
                </span>
              </div>
            </div>

            {/* Net Out-of-pocket Purchase Price */}
            <div className="bg-gradient-to-r from-emerald-950/80 to-slate-900 border border-emerald-500/40 rounded-2xl p-5 text-center space-y-1">
              <span className="text-xs text-emerald-300 font-semibold uppercase tracking-wider">
                최종 실구매 체감가 (소비자 부담액)
              </span>
              <div className="text-3xl sm:text-4xl font-black text-emerald-400 tracking-tight">
                {(calculationResult.netPurchasePriceKrw / 10000).toLocaleString()}
                <span className="text-xl sm:text-2xl font-bold ml-1 text-emerald-200">만 원</span>
              </div>
              <div className="text-[11px] text-emerald-300/80">
                (정확한 금액: {calculationResult.netPurchasePriceKrw.toLocaleString()} 원)
              </div>
            </div>

            {/* Depletion Risk Warning Alert */}
            <div
              className={`p-4 rounded-2xl border text-xs leading-relaxed space-y-1.5 ${
                calculationResult.isHighDepletionRisk
                  ? 'bg-rose-950/60 border-rose-500/60 text-rose-200'
                  : 'bg-emerald-950/40 border-emerald-500/40 text-emerald-200'
              }`}
            >
              <div className="font-bold flex items-center gap-1.5">
                <span>{calculationResult.isHighDepletionRisk ? '🚨' : '✅'}</span>
                <span>{calculationResult.regionName} 보조금 예산 소진 위험도 분석</span>
              </div>
              <p>{calculationResult.warningNotice}</p>
              <div className="text-[11px] text-slate-400 pt-1 border-t border-slate-800/60 flex flex-wrap justify-between gap-1">
                <span>거주 요건: 최소 {calculationResult.residencyRequirementDays}일 이상</span>
                <span>2년 의무 운행 기간 (관외 이전 시 환수)</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 6. Regulatory Footer Notes */}
      <section aria-label="보조금 지침 규정 안내" className="text-xs text-slate-400 leading-relaxed bg-slate-950 p-6 rounded-2xl border border-slate-900 space-y-2">
        <h2 className="text-base font-bold text-slate-200">📌 2026년 환경부 및 지자체 전기차 보조금 안내사항</h2>
        <ul className="list-disc pl-5 space-y-1 text-slate-400">
          <li>
            <strong>가격 상한제:</strong> 기본 출고가(MSRP) 기준 5,500만 원 미만 100%, 5,500만~8,500만 원 50%, 8,500만 원 초과 시 보조금 지급 대상에서 전액 제외됩니다.
          </li>
          <li>
            <strong>지자체 지방비 매칭:</strong> 각 지자체의 지방비는 국비 보조금 비율(해당 모델 국비 / 최대 650만 원)에 비례하여 차등 지급됩니다.
          </li>
          <li>
            <strong>의무 운행 및 환수:</strong> 대기환경보전법 제58조에 따라 최초 등록일로부터 2년간 의무 운행 기간이 적용되며, 2년 이내 관외(타 시·도) 매매 시 기간별 잔여 비율에 따라 지자체 보조금이 환수됩니다. (관내 이전 시 환수 없음)
          </li>
          <li>
            <strong>실시간 소진율:</strong> 환경부 무공해차 통합누리집에 정기 고시되는 각 지자체별 접수 현황에 기반하며, 지자체 사정에 따른 추경 편성 및 취소 물량 발생에 따라 실시간 쿼터 변동이 있을 수 있습니다.
          </li>
        </ul>
      </section>
    </div>
  );
}
