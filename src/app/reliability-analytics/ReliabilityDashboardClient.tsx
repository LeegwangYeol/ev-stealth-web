'use client';

import React, { useState, useMemo, useDeferredValue, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import ClientTimestamp from '@/components/ClientTimestamp';
import {
  ReliabilityTrendsDatabase,
  DefectCategoryKey,
  ModelYearVerdict,
  YearEvaluation,
  BrandReliability,
  DefectCategoryMetadata,
  RepairCostMatrixItem,
  EnrichedModelItem,
  getAllEnrichedModels,
  getVerdictBadgeInfo,
  getDsiSeverityLevel,
  getGradeBadgeStyle,
} from '@/lib/reliabilityCalculations';

interface ReliabilityDashboardClientProps {
  initialData: ReliabilityTrendsDatabase;
}

type ChartTabKey = 'heatmap' | 'brand_ranking' | 'category_share';
export type ReliabilitySortOption = 'DSI_DESC' | 'DSI_ASC' | 'GRADE' | 'NAME';

const isReliabilitySortOption = (val: string): val is ReliabilitySortOption =>
  ['DSI_DESC', 'DSI_ASC', 'GRADE', 'NAME'].includes(val);

const CHART_TABS: { id: ChartTabKey; label: string }[] = [
  { id: 'heatmap', label: '연식 리스크 히트맵' },
  { id: 'brand_ranking', label: '브랜드 결함 심각도(DSI) 랭킹' },
  { id: 'category_share', label: '부문별 결함 비중' },
];

const CATEGORY_BG_COLORS: Record<DefectCategoryKey, string> = {
  BATTERY_CHARGING: 'bg-rose-500',
  DRIVING_POWERTRAIN: 'bg-amber-500',
  SOFTWARE_ELECTRONICS: 'bg-blue-500',
  BUILD_QUALITY: 'bg-purple-500',
  SERVICE_REPAIR_COST: 'bg-emerald-500',
  COLD_WEATHER: 'bg-cyan-500',
};

const CATEGORY_TAG_COLORS: Record<DefectCategoryKey, { bg: string; text: string; border: string }> = {
  BATTERY_CHARGING: { bg: 'bg-rose-50', text: 'text-rose-800', border: 'border-rose-200' },
  DRIVING_POWERTRAIN: { bg: 'bg-amber-50', text: 'text-amber-900', border: 'border-amber-200' },
  SOFTWARE_ELECTRONICS: { bg: 'bg-blue-50', text: 'text-blue-800', border: 'border-blue-200' },
  BUILD_QUALITY: { bg: 'bg-purple-50', text: 'text-purple-800', border: 'border-purple-200' },
  SERVICE_REPAIR_COST: { bg: 'bg-emerald-50', text: 'text-emerald-800', border: 'border-emerald-200' },
  COLD_WEATHER: { bg: 'bg-cyan-50', text: 'text-cyan-900', border: 'border-cyan-200' },
};

const CATEGORY_KEYWORDS: Record<string, string[]> = {
  BATTERY_CHARGING: ['배터리', '충전', 'iccu', '화재', '열폭주', '방전', '인렛'],
  DRIVING_POWERTRAIN: ['모터', '감속기', '구동계', '동력', '인버터', '출력'],
  SOFTWARE_ELECTRONICS: ['소프트웨어', 'ota', 'bms', '인포테인먼트', '디스플레이', '통신'],
  BUILD_QUALITY: ['단차', '도장', '누수', '소음', '유격', '마감', '잡소리'],
  SERVICE_REPAIR_COST: ['수리비', '정비', '부품', '공임', '보증'],
  COLD_WEATHER: ['혹한기', '동절기', '저온', '히트펌프', '옥토밸브', '난방'],
};

/**
 * Fuzzy brand resolver for deep-linking query parameter (?brand=...)
 */
function resolveBrandId(input: string, brands: BrandReliability[] = []): string | null {
  if (!input || !Array.isArray(brands)) return null;
  const clean = input.trim().toLowerCase();
  if (clean === 'all') return 'ALL';

  const exact = brands.find((b) => b?.id?.toLowerCase() === clean);
  if (exact) return exact.id;

  const match = brands.find((b) => {
    if (!b) return false;
    const en = (b.name_en || '').toLowerCase();
    const ko = (b.name_ko || '').toLowerCase();
    return (
      clean === en ||
      clean === ko ||
      en.includes(clean) ||
      clean.includes(en) ||
      ko.includes(clean) ||
      clean.includes(ko)
    );
  });
  if (match) return match.id;

  if (clean.includes('hyundai') || clean.includes('현대')) return 'hyundai';
  if (clean.includes('kia') || clean.includes('기아')) return 'kia';
  if (clean.includes('genesis') || clean.includes('제네시스')) return 'genesis';
  if (clean.includes('tesla') || clean.includes('테슬라')) return 'tesla';
  if (clean.includes('byd') || clean.includes('비야디')) return 'byd';
  if (clean.includes('benz') || clean.includes('벤츠') || clean.includes('mercedes')) return 'mercedes-benz';
  if (clean.includes('bmw')) return 'bmw';
  if (clean.includes('polestar') || clean.includes('폴스타')) return 'polestar';
  if (clean.includes('gm') || clean.includes('chevrolet') || clean.includes('쉐보레')) return 'gm';

  return null;
}

/**
 * Fuzzy category resolver for deep-linking query parameter (?category=...)
 */
function resolveCategoryKey(input: string, categories: DefectCategoryMetadata[] = []): string | null {
  if (!input || !Array.isArray(categories)) return null;
  const clean = input.trim().toUpperCase();
  if (clean === 'ALL') return 'ALL';

  const exact = categories.find((c) => c?.code?.toUpperCase() === clean);
  if (exact) return exact.code;

  const lower = input.trim().toLowerCase();
  const labelMatch = categories.find(
    (c) =>
      c &&
      (c.label_ko?.toLowerCase().includes(lower) ||
        lower.includes(c.label_ko?.toLowerCase() || ''))
  );
  if (labelMatch) return labelMatch.code;

  if (lower.includes('battery') || lower.includes('충전') || lower.includes('배터리')) return 'BATTERY_CHARGING';
  if (lower.includes('power') || lower.includes('drive') || lower.includes('구동') || lower.includes('모터') || lower.includes('iccu')) return 'DRIVING_POWERTRAIN';
  if (lower.includes('soft') || lower.includes('ota') || lower.includes('bms')) return 'SOFTWARE_ELECTRONICS';
  if (lower.includes('build') || lower.includes('단차') || lower.includes('품질')) return 'BUILD_QUALITY';
  if (lower.includes('cost') || lower.includes('repair') || lower.includes('수리')) return 'SERVICE_REPAIR_COST';
  if (lower.includes('cold') || lower.includes('heat') || lower.includes('저온') || lower.includes('혹한')) return 'COLD_WEATHER';

  return null;
}

interface IndexedModelItem extends EnrichedModelItem {
  _searchIndex: string;
  _categoryMatch: Set<string>;
  _verdicts: Set<ModelYearVerdict>;
  _hasEarlyYear: boolean;
  _hasMidYear: boolean;
  _hasLateYear: boolean;
}

// ==========================================
// MEMOIZED SUBCOMPONENTS FOR HIGH RENDERING HYGIENE
// ==========================================

interface HeatmapRowProps {
  model: EnrichedModelItem;
  evalMap?: Map<number, YearEvaluation>;
  heatmapYears: number[];
  selectedCellKey?: string | null;
  onCellClick: (
    cell: {
      modelName: string;
      brandName: string;
      year: number;
      verdict: ModelYearVerdict;
      dsi: number;
      primaryDefect: string;
      quote: string;
    },
    triggerEl?: HTMLButtonElement | null
  ) => void;
}

const HeatmapRow = React.memo(function HeatmapRow({
  model,
  evalMap,
  heatmapYears,
  selectedCellKey,
  onCellClick,
}: HeatmapRowProps) {
  return (
    <tr className="group hover:bg-slate-50/80 transition">
      <th
        scope="row"
        className="p-3 font-bold text-slate-900 sticky left-0 bg-white group-hover:bg-slate-50/80 z-10 shadow-[2px_0_5px_-2px_rgba(0,0,0,0.05)] text-left"
      >
        <div className="truncate max-w-[130px] sm:max-w-none" title={model.name}>{model.name}</div>
      </th>
      <td className="p-3 text-slate-700 text-xs whitespace-nowrap">
        {model.brand_name_ko}
      </td>
      {heatmapYears.map((yr) => {
        const evalData = evalMap?.get(yr);
        if (!evalData) {
          return (
            <td key={yr} className="p-2 text-center">
              <div
                className="w-11 h-11 min-w-[44px] min-h-[44px] mx-auto rounded-lg bg-slate-100 border border-slate-200 flex items-center justify-center text-[10px] text-slate-700 font-mono font-medium"
                title="해당 연식 데이터 없음"
                aria-label="데이터 없음"
              >
                <span className="sr-only">{model.name} {yr}년식 데이터 없음</span>
                <span aria-hidden="true">-</span>
              </div>
            </td>
          );
        }

        const safeDsi = Number.isFinite(evalData.dsi_score) ? evalData.dsi_score : 0;
        const primaryDefect = evalData.primary_defect || '특이 결함 없음';
        const rawQuote = evalData.raw_quote || '';

        const cellColor =
          evalData.verdict === 'AVOID'
            ? 'bg-rose-700 hover:bg-rose-800 text-white shadow-rose-200'
            : evalData.verdict === 'CAUTION'
            ? 'bg-amber-400 hover:bg-amber-500 text-slate-950 shadow-amber-200 font-bold'
            : 'bg-emerald-700 hover:bg-emerald-800 text-white shadow-emerald-200';

        const localizedVerdict =
          evalData.verdict === 'AVOID'
            ? '구매 회피 (AVOID)'
            : evalData.verdict === 'CAUTION'
            ? '주의 요망 (CAUTION)'
            : '안심 추천 (BUY SAFE)';

        const isCellSelected = selectedCellKey === `${model.name}-${evalData.year}`;

        return (
          <td key={yr} className="p-2 text-center">
            <button
              type="button"
              onClick={(e) =>
                onCellClick(
                  {
                    modelName: model.name,
                    brandName: model.brand_name_ko,
                    year: evalData.year,
                    verdict: evalData.verdict,
                    dsi: safeDsi,
                    primaryDefect,
                    quote: rawQuote,
                  },
                  e.currentTarget
                )
              }
              aria-expanded={isCellSelected}
              aria-haspopup="dialog"
              aria-label={`${model.name} ${evalData.year}년식 ${evalData.verdict} DSI ${safeDsi}점 (${localizedVerdict}), 주요 결함: ${primaryDefect}${isCellSelected ? ' (현재 선택됨)' : ''}`}
              className={`w-11 h-11 min-w-[44px] min-h-[44px] mx-auto rounded-lg font-bold text-xs flex items-center justify-center shadow-sm cursor-pointer transition transform hover:scale-110 active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 ${cellColor} ${
                isCellSelected ? 'ring-2 ring-blue-500 ring-offset-2 scale-105' : ''
              }`}
              title={`${model.name} (${evalData.year}): ${evalData.verdict} - DSI ${safeDsi}`}
            >
              {safeDsi}
            </button>
          </td>
        );
      })}
    </tr>
  );
});

interface BrandRankingItemProps {
  brand: BrandReliability;
  idx: number;
  isSelected: boolean;
  onToggle: (brandId: string) => void;
}

const BrandRankingItem = React.memo(function BrandRankingItem({
  brand,
  idx,
  isSelected,
  onToggle,
}: BrandRankingItemProps) {
  const safeDsi = Number.isFinite(brand?.overall_dsi) ? brand.overall_dsi : 0;
  const dsiWidth = `${Math.min(100, Math.max(15, safeDsi))}%`;
  const dsiInfo = getDsiSeverityLevel(safeDsi);
  const barColor =
    safeDsi < 50
      ? 'bg-emerald-500'
      : safeDsi < 60
      ? 'bg-amber-400'
      : safeDsi < 65
      ? 'bg-orange-500'
      : 'bg-rose-500';
  const modelCount = Array.isArray(brand?.models) ? brand.models.length : 0;
  const criticalRate = Number.isFinite(brand?.critical_issue_rate) ? brand.critical_issue_rate : 0;

  return (
    <button
      type="button"
      onClick={() => onToggle(brand.id)}
      aria-pressed={isSelected}
      aria-label={`${idx + 1}위 ${brand?.name_ko || ''} (${brand?.name_en || ''}), 국가: ${brand?.country || ''}, ${modelCount}개 모델, 치명 결함율 ${criticalRate}%, 평균 DSI ${safeDsi}점 (${dsiInfo.label})`}
      className={`w-full text-left p-3 sm:p-4 rounded-2xl border transition cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
        isSelected
          ? 'bg-indigo-50/80 border-indigo-300 ring-2 ring-indigo-200'
          : 'bg-slate-50 hover:bg-slate-100/80 border-slate-200'
      }`}
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 sm:gap-4 mb-2">
        <div className="flex items-center gap-2">
          <span className="w-6 h-6 rounded-full bg-slate-200 text-slate-800 text-xs font-bold flex items-center justify-center" aria-hidden="true">
            {idx + 1}
          </span>
          <span className="font-bold text-slate-900 text-sm sm:text-base">
            {brand?.name_ko || ''} {brand?.name_en ? `(${brand.name_en})` : ''}
          </span>
          <span className="text-xs text-slate-700 font-normal">
            {brand?.country || ''} · {modelCount}개 모델
          </span>
        </div>
        <div className="flex items-center gap-3 text-xs sm:text-sm">
          <span className="text-slate-700">
            치명 결함율: <strong className="text-rose-800">{criticalRate}%</strong>
          </span>
          <span className="font-black text-slate-900 text-sm sm:text-base">
            DSI {safeDsi}점
          </span>
        </div>
      </div>

      {/* Pure CSS Bar */}
      <div
        aria-hidden="true"
        className="w-full bg-slate-200 rounded-full h-3.5 overflow-hidden relative"
      >
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: dsiWidth }}
        />
      </div>
    </button>
  );
});

interface CategoryShareCardProps {
  cat: DefectCategoryMetadata;
  isSelected: boolean;
  onToggle: (catCode: string) => void;
}

const CategoryShareCard = React.memo(function CategoryShareCard({
  cat,
  isSelected,
  onToggle,
}: CategoryShareCardProps) {
  const codeKey = cat?.code || 'UNKNOWN';
  const color = (cat?.code && CATEGORY_TAG_COLORS[cat.code]) || {
    bg: 'bg-slate-50',
    text: 'text-slate-700',
    border: 'border-slate-200',
  };
  const dotColor = (cat?.code && CATEGORY_BG_COLORS[cat.code]) || 'bg-slate-500';
  const sharePct = Number.isFinite(cat?.industry_share_pct) ? cat.industry_share_pct : 0;

  return (
    <button
      type="button"
      onClick={() => onToggle(codeKey)}
      aria-pressed={isSelected}
      aria-labelledby={`cat-title-${cat.code}`}
      aria-describedby={`cat-desc-${cat.code} cat-cost-${cat.code}`}
      className={`w-full text-left p-4 rounded-2xl border transition cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
        isSelected
          ? 'ring-2 ring-indigo-300 bg-indigo-50/50 border-indigo-300'
          : `${color.bg} ${color.border} hover:shadow-md`
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`w-3 h-3 rounded-full ${dotColor} inline-block shadow-sm`} aria-hidden="true" />
          <span id={`cat-title-${cat.code}`} className="font-bold text-sm text-slate-900">{cat.label_ko} ({sharePct}%)</span>
        </div>
        <span className={`text-xs px-2.5 py-0.5 rounded-full font-bold ${color.text} bg-white shadow-sm border ${color.border}`}>
          {sharePct}%
        </span>
      </div>
      <p id={`cat-desc-${cat.code}`} className="text-xs text-slate-700 mt-2 leading-relaxed">{cat.description || '세부 설명이 등록되지 않았습니다.'}</p>
      <div id={`cat-cost-${cat.code}`} className="mt-3 pt-2 border-t border-slate-200/60 text-[11px] font-medium text-slate-700">
        평균 예상 수리비: <strong className="text-slate-900">{cat.avg_repair_cost_range || '조사 중'}</strong>
      </div>
    </button>
  );
});

interface RepairCostMatrixRowProps {
  item: RepairCostMatrixItem;
}

const RepairCostMatrixRow = React.memo(function RepairCostMatrixRow({ item }: RepairCostMatrixRowProps) {
  const highRiskModels = Array.isArray(item?.high_risk_models) ? item.high_risk_models : [];

  return (
    <tr className="hover:bg-slate-50 transition group">
      <th
        scope="row"
        className="p-4 font-bold text-slate-900 align-top text-left sticky left-0 bg-white group-hover:bg-slate-50 z-10 shadow-[2px_0_5px_-2px_rgba(0,0,0,0.05)]"
      >
        <div>{item.component_name || '부품명 미지정'}</div>
        <div className="text-[11px] text-slate-700 font-normal mt-1">
          {item.affected_systems || '-'}
        </div>
      </th>
      <td className="p-4 font-extrabold text-rose-800 align-top whitespace-nowrap">
        {item.avg_cost_krw || '-'}
      </td>
      <td className="p-4 text-slate-700 align-top text-xs">
        {item.standard_warranty || '-'}
      </td>
      <td className="p-4 align-top">
        <div className="flex flex-wrap gap-1">
          {highRiskModels.length === 0 ? (
            <span className="text-slate-700 text-xs">전 차종 공통</span>
          ) : (
            highRiskModels.map((m) => (
              <span
                key={`${item.component_name}-${m}`}
                className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 text-[11px] font-medium"
              >
                {m}
              </span>
            ))
          )}
        </div>
      </td>
      <td className="p-4 text-xs text-slate-700 leading-relaxed align-top">
        <span className="font-semibold text-rose-800 mr-1">주의:</span>
        {item.critical_warning || '-'}
      </td>
    </tr>
  );
});

// ==========================================
// ROOT DASHBOARD CLIENT COMPONENT
// ==========================================

export default function ReliabilityDashboardClient({ initialData }: ReliabilityDashboardClientProps) {
  const searchParams = useSearchParams();

  // --- Filter States ---
  const [selectedBrand, setSelectedBrand] = useState<string>('ALL');
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [selectedVerdict, setSelectedVerdict] = useState<string>('ALL');
  const [selectedYearRange, setSelectedYearRange] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const deferredSearchQuery = useDeferredValue(searchQuery);
  const [sortBy, setSortBy] = useState<'DSI_DESC' | 'DSI_ASC' | 'GRADE' | 'NAME'>('DSI_DESC');
  const [activeChartTab, setActiveChartTab] = useState<'heatmap' | 'brand_ranking' | 'category_share'>('heatmap');
  const [hoveredCell, setHoveredCell] = useState<{
    modelName: string;
    brandName: string;
    year: number;
    verdict: ModelYearVerdict;
    dsi: number;
    primaryDefect: string;
    quote: string;
  } | null>(null);

  // Accessible Focus Management Refs
  const activeTriggerRef = React.useRef<HTMLButtonElement | null>(null);
  const searchInputRef = React.useRef<HTMLInputElement | null>(null);

  // Defensive fallbacks for database collections and metadata
  const metadata = useMemo(
    () =>
      initialData?.metadata ?? {
        version: '1.0',
        updated_at: '',
        total_records_analyzed: 0,
        brands_count: 0,
        models_count: 0,
        avg_industry_dsi: 0,
      },
    [initialData?.metadata]
  );
  const brands = useMemo(
    () => (Array.isArray(initialData?.brands) ? initialData.brands : []),
    [initialData?.brands]
  );
  const categories = useMemo(
    () => (Array.isArray(initialData?.categories) ? initialData.categories : []),
    [initialData?.categories]
  );
  const repairCostMatrix = useMemo(
    () => (Array.isArray(initialData?.repair_cost_matrix) ? initialData.repair_cost_matrix : []),
    [initialData?.repair_cost_matrix]
  );

  // Synchronize URL query parameters (?brand=...&category=...)
  useEffect(() => {
    if (!searchParams) return;
    const brandParam = searchParams.get('brand');
    if (brandParam) {
      const resolved = resolveBrandId(brandParam, brands);
      if (resolved) {
        setSelectedBrand(resolved);
      }
    }
    const catParam = searchParams.get('category');
    if (catParam) {
      const resolvedCat = resolveCategoryKey(catParam, categories);
      if (resolvedCat) {
        setSelectedCategory(resolvedCat);
      }
    }
  }, [searchParams, brands, categories]);

  // All enriched models loaded from initialData with pre-computed search & filter indexes
  const allModels: IndexedModelItem[] = useMemo(() => {
    const rawModels = getAllEnrichedModels(initialData);
    return rawModels.map((m) => {
      const yearEvals = m.year_evaluations || [];
      const categoryMatch = new Set<string>();
      if (m.top_category) {
        categoryMatch.add(m.top_category);
      }

      const verdicts = new Set<ModelYearVerdict>();
      let hasEarlyYear = false;
      let hasMidYear = false;
      let hasLateYear = false;

      const evalTexts: string[] = [];

      for (const y of yearEvals) {
        if (y.verdict) verdicts.add(y.verdict);
        if (typeof y.year === 'number') {
          if (y.year <= 2020) hasEarlyYear = true;
          if (y.year >= 2021 && y.year <= 2023) hasMidYear = true;
          if (y.year >= 2024) hasLateYear = true;
        }

        const defectText = `${y.primary_defect || ''} ${(y.chronic_symptoms || []).join(' ')}`.toLowerCase();
        evalTexts.push(defectText);
        if (y.raw_quote) evalTexts.push(y.raw_quote.toLowerCase());

        for (const [catKey, kws] of Object.entries(CATEGORY_KEYWORDS)) {
          if (!categoryMatch.has(catKey)) {
            if (kws.some((kw) => defectText.includes(kw))) {
              categoryMatch.add(catKey);
            }
          }
        }
      }

      const searchCorpus = [
        m.name || '',
        m.brand_name_ko || '',
        m.brand_name_en || '',
        m.segment || '',
        ...evalTexts,
      ]
        .join(' ')
        .toLowerCase();

      return {
        ...m,
        _searchIndex: searchCorpus,
        _categoryMatch: categoryMatch,
        _verdicts: verdicts,
        _hasEarlyYear: hasEarlyYear,
        _hasMidYear: hasMidYear,
        _hasLateYear: hasLateYear,
      };
    });
  }, [initialData]);

  // Pre-indexed evaluation maps per model ID (eliminating redundant Map allocations inside heatmap)
  const modelEvalMaps = useMemo(() => {
    const lookup = new Map<string, Map<number, YearEvaluation>>();
    for (const m of allModels) {
      const mLookup = new Map<number, YearEvaluation>();
      for (const y of m.year_evaluations || []) {
        mLookup.set(y.year, y);
      }
      lookup.set(m.id, mLookup);
    }
    return lookup;
  }, [allModels]);

  // Unique years for heatmap
  const heatmapYears = useMemo(() => {
    const yearSet = new Set<number>();
    allModels.forEach((m) => {
      (m.year_evaluations || []).forEach((y) => yearSet.add(y.year));
    });
    return Array.from(yearSet).sort((a, b) => a - b);
  }, [allModels]);

  // Filtered models using pre-computed indexes (zero allocations during filter loop)
  const filteredModels = useMemo(() => {
    const q = deferredSearchQuery.trim().toLowerCase();

    return allModels.filter((model) => {
      // Brand filter
      if (selectedBrand !== 'ALL' && model.brand_id !== selectedBrand) {
        return false;
      }

      // Category filter (O(1) Set lookup)
      if (selectedCategory !== 'ALL' && !model._categoryMatch.has(selectedCategory)) {
        return false;
      }

      // Verdict filter (O(1) Set lookup)
      if (selectedVerdict !== 'ALL' && !model._verdicts.has(selectedVerdict as ModelYearVerdict)) {
        return false;
      }

      // Year range filter (O(1) boolean flags)
      if (selectedYearRange === 'EARLY' && !model._hasEarlyYear) return false;
      if (selectedYearRange === 'MID' && !model._hasMidYear) return false;
      if (selectedYearRange === 'LATE' && !model._hasLateYear) return false;

      // Deferred Search query (single substring check)
      if (q && !model._searchIndex.includes(q)) {
        return false;
      }

      return true;
    });
  }, [
    allModels,
    selectedBrand,
    selectedCategory,
    selectedVerdict,
    selectedYearRange,
    deferredSearchQuery,
  ]);

  // Sorted models
  const sortedModels = useMemo(() => {
    const sorted = [...filteredModels];
    if (sortBy === 'DSI_DESC') {
      sorted.sort((a, b) => {
        const dsiA = Number.isFinite(a.avg_dsi) ? a.avg_dsi : 0;
        const dsiB = Number.isFinite(b.avg_dsi) ? b.avg_dsi : 0;
        return dsiB - dsiA;
      });
    } else if (sortBy === 'DSI_ASC') {
      sorted.sort((a, b) => {
        const dsiA = Number.isFinite(a.avg_dsi) ? a.avg_dsi : 0;
        const dsiB = Number.isFinite(b.avg_dsi) ? b.avg_dsi : 0;
        return dsiA - dsiB;
      });
    } else if (sortBy === 'GRADE') {
      const gradeOrder: Record<string, number> = {
        'A+': 1,
        A: 2,
        B: 3,
        C: 4,
        D: 5,
        F: 6,
      };
      sorted.sort(
        (a, b) =>
          (gradeOrder[a.overall_grade] || 99) - (gradeOrder[b.overall_grade] || 99)
      );
    } else if (sortBy === 'NAME') {
      sorted.sort((a, b) => a.name.localeCompare(b.name, 'ko'));
    }
    return sorted;
  }, [filteredModels, sortBy]);

  // Sorted brands by overall DSI ascending (best reliability to worst)
  const sortedBrands = useMemo(() => {
    return [...brands]
      .filter((b): b is BrandReliability => Boolean(b && typeof b === 'object'))
      .sort((a, b) => {
        const dsiA = Number.isFinite(a.overall_dsi) ? a.overall_dsi : 0;
        const dsiB = Number.isFinite(b.overall_dsi) ? b.overall_dsi : 0;
        return dsiA - dsiB;
      });
  }, [brands]);

  // Top defect category computed dynamically with defensive fallback
  const topCategory = useMemo(() => {
    if (!categories.length) return null;
    return [...categories].sort((a, b) => (b.industry_share_pct || 0) - (a.industry_share_pct || 0))[0];
  }, [categories]);

  // Total category share for safe 100% proportional rendering
  const totalCategoryShare = useMemo(() => {
    return categories.reduce(
      (sum, c) => sum + (Number.isFinite(c.industry_share_pct) ? Math.max(0, c.industry_share_pct) : 0),
      0
    );
  }, [categories]);

  // Brand SVG dynamic dimensions and accessible description
  const brandSvgHeight = useMemo(() => {
    return Math.max(140, 30 + sortedBrands.length * 28 + 45);
  }, [sortedBrands.length]);

  const brandSvgDesc = useMemo(() => {
    if (!sortedBrands.length) return '브랜드별 종합 결함 심각도 지수 시각화 차트입니다.';
    const bestBrand = sortedBrands[0];
    const worstBrand = sortedBrands[sortedBrands.length - 1];
    return `9대 전기차 제조사별 결함 심각도 지수(DSI 0~100점, 낮을수록 우수) 수평 막대 차트입니다. 최저(최우수) DSI는 ${bestBrand?.name_ko || ''}(${bestBrand?.overall_dsi || 0}점), 최고(주의) DSI는 ${worstBrand?.name_ko || ''}(${worstBrand?.overall_dsi || 0}점)입니다. 아래에 전체 브랜드별 스크린 리더용 데이터 표가 제공됩니다.`;
  }, [sortedBrands]);

  // Stabilized Callback Handlers
  const resetFilters = useCallback(() => {
    setSelectedBrand('ALL');
    setSelectedCategory('ALL');
    setSelectedVerdict('ALL');
    setSelectedYearRange('ALL');
    setSearchQuery('');
    setSortBy('DSI_DESC');
  }, []);

  const handleChartTabKeyDown = useCallback((e: React.KeyboardEvent, currentIndex: number) => {
    const count = CHART_TABS.length;
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
      const nextTab = CHART_TABS[nextIndex].id;
      setActiveChartTab(nextTab);
      document.getElementById(`chart-tab-${nextTab}`)?.focus();
    }
  }, []);

  const handleCellClick = useCallback(
    (
      cell: {
        modelName: string;
        brandName: string;
        year: number;
        verdict: ModelYearVerdict;
        dsi: number;
        primaryDefect: string;
        quote: string;
      },
      triggerEl?: HTMLButtonElement | null
    ) => {
      activeTriggerRef.current = triggerEl || (document.activeElement as HTMLButtonElement | null);
      setHoveredCell(cell);
    },
    []
  );

  const handleCloseCell = useCallback(() => {
    setHoveredCell(null);
    if (activeTriggerRef.current && typeof activeTriggerRef.current.focus === 'function') {
      activeTriggerRef.current.focus();
    }
  }, []);

  // Escape key listener for accessible dismissal of detail card with focus return
  useEffect(() => {
    if (!hoveredCell) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        handleCloseCell();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [hoveredCell, handleCloseCell]);

  const handleBrandToggle = useCallback((brandId: string) => {
    setSelectedBrand((prev) => (prev === brandId ? 'ALL' : brandId));
  }, []);

  const handleCategoryToggle = useCallback((catCode: string) => {
    setSelectedCategory((prev) => (prev === catCode ? 'ALL' : catCode));
  }, []);

  const hasActiveFilter =
    selectedBrand !== 'ALL' ||
    selectedCategory !== 'ALL' ||
    selectedVerdict !== 'ALL' ||
    selectedYearRange !== 'ALL' ||
    searchQuery.trim() !== '';

  // Single-pass memoized evaluation statistics
  const { totalEvaluationsCount, avoidEvaluationsCount, avoidPercentage } = useMemo(() => {
    let total = 0;
    let avoid = 0;
    for (const m of allModels) {
      if (Array.isArray(m.year_evaluations)) {
        total += m.year_evaluations.length;
        for (const y of m.year_evaluations) {
          if (y.verdict === 'AVOID') avoid++;
        }
      }
    }
    const rawRatio = total > 0 ? (avoid / total) * 100 : 0;
    return {
      totalEvaluationsCount: total,
      avoidEvaluationsCount: avoid,
      avoidPercentage: Number.isFinite(rawRatio) ? rawRatio.toFixed(1) : '0.0',
    };
  }, [allModels]);

  return (
    <div className="space-y-12">
      {/* 1. HERO HEADER WITH KPI METRICS */}
      <section aria-labelledby="reliability-hero-heading" className="bg-slate-900 text-white rounded-3xl p-6 sm:p-10 shadow-xl border border-slate-800">
        <div className="max-w-3xl space-y-3">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/20 text-blue-300 text-xs font-semibold border border-blue-400/30">
            <span aria-hidden="true">🛡️</span>
            <span>중고 전기차 구매자 필수 검증 지침</span>
          </div>
          <h1 id="reliability-hero-heading" className="text-3xl sm:text-4xl font-black tracking-tight leading-tight">
            전기차 연식별 결함 트렌드 &amp; 신뢰성 지수(DSI)
          </h1>
          <p className="text-sm sm:text-base text-slate-300 leading-relaxed">
            배터리 화재·열폭주, ICCU 폭파 및 동력 상실, 혹한기 히트펌프 고착 등 1,280여 건의 실차주 결함 제보 데이터를 분석하여 연식별 &quot;안심 추천(BUY SAFE)&quot;, &quot;주의(CAUTION)&quot;, &quot;구매 회피(AVOID)&quot; 판정을 제공합니다.
          </p>
          <div className="text-xs text-slate-300 flex items-center gap-2 pt-1">
            <span>최종 데이터 동기화:</span>
            <ClientTimestamp
              isoString={metadata?.updated_at || null}
              className="text-slate-200 font-mono"
            />
          </div>
        </div>

        {/* KPI Score Cards */}
        <h2 className="sr-only">주요 결함 통계 지표 요약 (KPI)</h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mt-8 pt-8 border-t border-slate-800">
          <div
            role="region"
            aria-labelledby="kpi-records-heading"
            aria-describedby="kpi-records-desc"
            className="bg-slate-800/80 backdrop-blur rounded-2xl p-4 sm:p-5 border border-slate-700"
          >
            <h3 id="kpi-records-heading" className="text-xs sm:text-sm text-slate-300 font-medium">분석 결함 제보</h3>
            <div className="text-2xl sm:text-3xl font-black text-white mt-1">
              {(Number.isFinite(metadata?.total_records_analyzed) ? metadata.total_records_analyzed : 0).toLocaleString()}건
            </div>
            <div id="kpi-records-desc" className="text-xs text-blue-300 mt-1 font-medium">
              {brands.length}개 브랜드 · {metadata.models_count || allModels.length}개 모델 조사
            </div>
          </div>

          <div
            role="region"
            aria-labelledby="kpi-dsi-heading"
            aria-describedby="kpi-dsi-desc"
            className="bg-slate-800/80 backdrop-blur rounded-2xl p-4 sm:p-5 border border-slate-700"
          >
            <h3 id="kpi-dsi-heading" className="text-xs sm:text-sm text-slate-300 font-medium">산업 평균 DSI 점수</h3>
            <div className="text-2xl sm:text-3xl font-black text-amber-400 mt-1">
              {Number.isFinite(metadata?.avg_industry_dsi) ? metadata.avg_industry_dsi : 0}
              <span className="text-sm font-normal text-slate-300 ml-1">/ 100</span>
            </div>
            <div id="kpi-dsi-desc" className="text-xs text-amber-300 mt-1 font-medium">
              결함 심각도 지수 (높을수록 위험)
            </div>
          </div>

          <div
            role="region"
            aria-labelledby="kpi-avoid-heading"
            aria-describedby="kpi-avoid-desc"
            className="bg-slate-800/80 backdrop-blur rounded-2xl p-4 sm:p-5 border border-slate-700"
          >
            <h3 id="kpi-avoid-heading" className="text-xs sm:text-sm text-slate-300 font-medium">구매 회피 (AVOID) 연식</h3>
            <div className="text-2xl sm:text-3xl font-black text-rose-300 mt-1">
              {avoidPercentage}%
            </div>
            <div id="kpi-avoid-desc" className="text-xs text-rose-300 mt-1 font-medium">
              총 {totalEvaluationsCount}개 중 {avoidEvaluationsCount}개 연식 위험
            </div>
          </div>

          <div
            role="region"
            aria-labelledby="kpi-category-heading"
            aria-describedby="kpi-category-desc"
            className="bg-slate-800/80 backdrop-blur rounded-2xl p-4 sm:p-5 border border-slate-700"
          >
            <h3 id="kpi-category-heading" className="text-xs sm:text-sm text-slate-300 font-medium">최다 결함 발생 부문</h3>
            <div className="text-2xl sm:text-3xl font-black text-emerald-400 mt-1">
              {topCategory ? `${Number.isFinite(topCategory.industry_share_pct) ? topCategory.industry_share_pct : 0}%` : '0%'}
            </div>
            <div id="kpi-category-desc" className="text-xs text-emerald-300 mt-1 font-medium">
              {topCategory ? topCategory.label_ko : '데이터 없음'}
            </div>
          </div>
        </div>
      </section>

      {/* 2. VISUAL CHARTS SECTION (PURE CSS/SVG) */}
      <section aria-labelledby="charts-center-heading" className="bg-white rounded-3xl p-6 sm:p-8 shadow-sm border border-slate-200">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-100">
          <div>
            <h2 id="charts-center-heading" className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
              <span aria-hidden="true">📈</span>
              <span>데이터 시각화 차트 센터</span>
            </h2>
            <p className="text-sm text-slate-700 mt-1">
              연식별 위험 매트릭스, 9대 브랜드 결함 랭킹, 부문별 비중을 실시간으로 확인하세요.
            </p>
          </div>

          {/* Chart Tab Selector */}
          <div role="tablist" aria-label="데이터 시각화 차트 선택" className="inline-flex max-w-full overflow-x-auto bg-slate-100 p-1.5 rounded-xl self-start sm:self-auto">
            {CHART_TABS.map((tab, idx) => {
              const isSelected = activeChartTab === tab.id;
              return (
                <button
                  key={tab.id}
                  id={`chart-tab-${tab.id}`}
                  type="button"
                  role="tab"
                  aria-selected={isSelected}
                  aria-controls={`chart-tabpanel-${tab.id}`}
                  tabIndex={isSelected ? 0 : -1}
                  onKeyDown={(e) => handleChartTabKeyDown(e, idx)}
                  onClick={() => setActiveChartTab(tab.id)}
                  className={`px-3.5 py-1.5 min-h-[44px] inline-flex items-center justify-center text-xs sm:text-sm font-semibold rounded-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                    isSelected
                      ? 'bg-white text-indigo-700 shadow-sm'
                      : 'text-slate-700 hover:text-slate-900'
                  }`}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>

        <div
          id={`chart-tabpanel-${activeChartTab}`}
          role="tabpanel"
          aria-labelledby={`chart-tab-${activeChartTab}`}
          tabIndex={0}
          className="mt-6 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none rounded-2xl"
        >
          {/* TAB 1: MODEL-YEAR RISK HEATMAP */}
          {activeChartTab === 'heatmap' && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                <div id="heatmap-instructions" className="font-medium text-slate-700 flex items-center gap-1.5">
                  <span aria-hidden="true">💡</span>
                  <span>셀을 클릭하거나 엔터키를 누르면 해당 연식의 결함 증상과 차주 코멘트를 확인하실 수 있습니다. (닫기: ESC)</span>
                </div>
                <ul
                  aria-label="히트맵 판정 범례"
                  className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-slate-700 font-semibold list-none m-0 p-0"
                >
                  <li className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full bg-rose-700 inline-block shadow-sm" aria-hidden="true" />
                    <span>회피 (AVOID)</span>
                  </li>
                  <li className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full bg-amber-400 inline-block shadow-sm" aria-hidden="true" />
                    <span>주의 (CAUTION)</span>
                  </li>
                  <li className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full bg-emerald-700 inline-block shadow-sm" aria-hidden="true" />
                    <span>추천 (SAFE)</span>
                  </li>
                  <li className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full bg-slate-200 border border-slate-300 inline-block" aria-hidden="true" />
                    <span className="text-slate-700 font-medium">미출시</span>
                  </li>
                </ul>
              </div>

              {/* Heatmap Grid Wrapper */}
              <div
                tabIndex={0}
                role="region"
                aria-label="연식별 전기차 신뢰성 및 결함 심각도 매트릭스 표 스크롤 영역"
                className="overflow-x-auto border border-slate-200 rounded-2xl focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              >
                <table
                  className="w-full min-w-[680px] text-left text-xs sm:text-sm border-collapse"
                  aria-label="연식별 전기차 신뢰성 및 결함 심각도(DSI) 매트릭스"
                  aria-describedby="heatmap-instructions"
                >
                  <caption className="sr-only">
                    연식별 전기차 신뢰성 및 결함 심각도(DSI) 매트릭스 - 모델별 2017년부터 2025년까지의 구매 권장(SAFE), 주의(CAUTION), 회피(AVOID) 평가 현황. 셀의 숫자는 0~100점의 DSI 결함 심각도 점수이며 클릭 시 세부 결함 증상과 리콜 링크가 표시됩니다.
                  </caption>
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-200">
                      <th scope="col" className="p-3 font-semibold text-slate-700 min-w-[140px] sticky left-0 bg-slate-50 z-10">
                        모델명
                      </th>
                      <th scope="col" className="p-3 font-semibold text-slate-700 min-w-[70px]">브랜드</th>
                      {heatmapYears.length === 0 ? (
                        <th scope="col" className="p-3 font-semibold text-slate-700 text-center">연식</th>
                      ) : (
                        heatmapYears.map((yr) => (
                          <th key={yr} scope="col" className="p-3 font-semibold text-slate-700 text-center min-w-[60px]">
                            {yr}
                          </th>
                        ))
                      )}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {allModels.length === 0 ? (
                      <tr>
                        <td colSpan={Math.max(3, heatmapYears.length + 2)} className="p-8 text-center text-slate-700 text-sm">
                          등록된 연식별 결함 데이터가 없습니다.
                        </td>
                      </tr>
                    ) : (
                      allModels.map((model) => (
                        <HeatmapRow
                          key={model.id}
                          model={model}
                          evalMap={modelEvalMaps.get(model.id)}
                          heatmapYears={heatmapYears}
                          selectedCellKey={hoveredCell ? `${model.name}-${hoveredCell.year}` : null}
                          onCellClick={handleCellClick}
                        />
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* Heatmap Detail Card (if selected) */}
              {hoveredCell && (
                <div
                  id="heatmap-detail-card"
                  role="region"
                  aria-label={`${hoveredCell.brandName} ${hoveredCell.modelName} ${hoveredCell.year}년식 세부 결함 분석`}
                  aria-live="polite"
                  tabIndex={-1}
                  className="p-4 bg-slate-900 text-white rounded-2xl border border-slate-700 shadow-xl animate-fade-in motion-reduce:animate-none flex flex-col sm:flex-row justify-between gap-4 focus:outline-none"
                >
                  <div className="space-y-1 max-w-2xl">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-bold text-base text-blue-300">
                        {hoveredCell.brandName} {hoveredCell.modelName} ({hoveredCell.year}년식)
                      </span>
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full font-bold ${
                          hoveredCell.verdict === 'AVOID'
                            ? 'bg-rose-500/30 text-rose-200 border border-rose-500/50'
                            : hoveredCell.verdict === 'CAUTION'
                            ? 'bg-amber-400/30 text-amber-100 border border-amber-400/50'
                            : 'bg-emerald-500/30 text-emerald-200 border border-emerald-500/50'
                        }`}
                      >
                        {hoveredCell.verdict} (DSI {hoveredCell.dsi}점)
                      </span>
                    </div>
                    <p className="text-sm text-slate-200 font-medium flex items-center gap-1">
                      <span aria-hidden="true">⚠️</span>
                      <span>주요 결함: {hoveredCell.primaryDefect}</span>
                    </p>
                    {hoveredCell.quote && (
                      <p className="text-xs text-slate-300 italic">
                        &quot;{hoveredCell.quote}&quot;
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Link
                      href={`/recall-portal?model=${encodeURIComponent(hoveredCell.modelName)}`}
                      prefetch={false}
                      className="px-3 py-1.5 min-h-[44px] bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 inline-flex items-center gap-1"
                    >
                      <span>공식 리콜 조회</span>
                      <span aria-hidden="true">&rarr;</span>
                    </Link>
                    <button
                      type="button"
                      onClick={handleCloseCell}
                      aria-label="결함 세부정보 닫기 (Esc)"
                      className="px-3 py-1.5 min-h-[44px] bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                    >
                      닫기
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: BRAND DSI RANKING COMPARATIVE CHART */}
          {activeChartTab === 'brand_ranking' && (
            <div className="space-y-6">
              <div className="text-xs text-slate-700 leading-relaxed">
                9대 브랜드의 전체 제보와 심각도를 종합 산출한 Defect Severity Index (DSI) 랭킹입니다. 점수가 낮을수록 내구성이 우수하고 결함 발생 빈도가 적음을 나타냅니다.
              </div>

              {/* DSI Severity Color Legend */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 bg-slate-50 border border-slate-200 rounded-xl text-xs">
                <span id="dsi-legend-title" className="font-bold text-slate-800">DSI 위험도 기준:</span>
                <ul
                  aria-labelledby="dsi-legend-title"
                  className="flex flex-wrap items-center gap-4 text-xs font-semibold list-none m-0 p-0"
                >
                  <li className="flex items-center gap-1.5 text-slate-800">
                    <span className="w-3 h-3 rounded-full bg-emerald-500 inline-block shadow-sm" aria-hidden="true" />
                    <span>안전 (&lt;50점)</span>
                  </li>
                  <li className="flex items-center gap-1.5 text-slate-800">
                    <span className="w-3 h-3 rounded-full bg-amber-400 inline-block shadow-sm" aria-hidden="true" />
                    <span>보통 (50~59점)</span>
                  </li>
                  <li className="flex items-center gap-1.5 text-slate-800">
                    <span className="w-3 h-3 rounded-full bg-orange-500 inline-block shadow-sm" aria-hidden="true" />
                    <span>주의 (60~64점)</span>
                  </li>
                  <li className="flex items-center gap-1.5 text-slate-800">
                    <span className="w-3 h-3 rounded-full bg-rose-500 inline-block shadow-sm" aria-hidden="true" />
                    <span>위험 (65점 이상)</span>
                  </li>
                </ul>
              </div>

              {/* SVG Horizontal Comparative Bar Chart */}
              {sortedBrands.length === 0 ? (
                <div className="p-8 text-center text-slate-300 bg-slate-900 border border-slate-800 rounded-2xl text-sm">
                  브랜드별 DSI 결함 통계 데이터가 없습니다.
                </div>
              ) : (
                <div
                  tabIndex={0}
                  role="region"
                  aria-label="브랜드별 DSI 결함 심각도 지수 시각화 차트 스크롤 영역"
                  className="w-full overflow-x-auto border border-slate-800 rounded-2xl p-4 sm:p-6 bg-slate-900 text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 shadow-inner"
                >
                  <svg
                    viewBox={`0 0 680 ${brandSvgHeight}`}
                    width="680"
                    height={brandSvgHeight}
                    className="w-full min-w-[560px] h-auto select-none"
                    role="img"
                    aria-labelledby="brand-dsi-svg-title brand-dsi-svg-desc"
                  >
                    <title id="brand-dsi-svg-title">
                      전기차 9대 제조사 브랜드별 결함 심각도 지수(DSI) 비교 차트
                    </title>
                    <desc id="brand-dsi-svg-desc">
                      {brandSvgDesc}
                    </desc>

                    {/* Grid Lines & Scale Marks */}
                    <g aria-hidden="true">
                      {[0, 25, 50, 75, 100].map((val) => {
                        const x = 120 + (val / 100) * 480;
                        return (
                          <g key={val}>
                            <line
                              x1={x}
                              y1={15}
                              x2={x}
                              y2={brandSvgHeight - 45}
                              stroke="#334155"
                              strokeDasharray={val === 50 ? '0' : '3 3'}
                              strokeWidth={val === 50 ? '1.5' : '1'}
                            />
                            <text
                              x={x}
                              y={brandSvgHeight - 25}
                              textAnchor="middle"
                              fill="#94a3b8"
                              fontSize="10"
                              fontWeight="bold"
                            >
                              {val === 50 ? '50 (안전기준)' : `${val}점`}
                            </text>
                          </g>
                        );
                      })}
                    </g>

                    {/* Horizontal Bars */}
                    {sortedBrands.map((brand, i) => {
                      const y = 20 + i * 28;
                      const safeDsi = Number.isFinite(brand.overall_dsi)
                        ? Math.min(100, Math.max(0, brand.overall_dsi))
                        : 0;
                      const barWidth = Math.max(12, (safeDsi / 100) * 480);
                      const barFill =
                        safeDsi < 50
                          ? '#10b981'
                          : safeDsi < 60
                          ? '#fbbf24'
                          : safeDsi < 65
                          ? '#f97316'
                          : '#f43f5e';

                      return (
                        <g key={brand.id} className="transition-opacity hover:opacity-90">
                          <text
                            x="110"
                            y={y + 13}
                            textAnchor="end"
                            fill="#f8fafc"
                            fontSize="11"
                            fontWeight="bold"
                          >
                            {brand.name_ko}
                          </text>
                          <rect
                            x="120"
                            y={y}
                            width="480"
                            height="18"
                            rx="4"
                            fill="#1e293b"
                          />
                          <rect
                            x="120"
                            y={y}
                            width={barWidth}
                            height="18"
                            rx="4"
                            fill={barFill}
                          />
                          <text
                            x={120 + barWidth + 8}
                            y={y + 13}
                            textAnchor="start"
                            fill="#ffffff"
                            fontSize="11"
                            fontWeight="bold"
                          >
                            {safeDsi}점
                          </text>
                        </g>
                      );
                    })}
                  </svg>
                </div>
              )}

              {/* Screen-reader accessible data table alternative for Brand Ranking */}
              <div className="sr-only">
                <table aria-label="전기차 제조사 브랜드별 결함 심각도 지수 랭킹 데이터 표">
                  <caption>9대 전기차 제조사 DSI 내구성 지수 및 치명 결함율 랭킹</caption>
                  <thead>
                    <tr>
                      <th scope="col">순위</th>
                      <th scope="col">제조사 브랜드</th>
                      <th scope="col">국가</th>
                      <th scope="col">분석 모델 수</th>
                      <th scope="col">치명 결함율</th>
                      <th scope="col">종합 DSI 점수</th>
                      <th scope="col">내구성 위험 수준</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedBrands.map((b, i) => {
                      const dsi = Number.isFinite(b.overall_dsi) ? b.overall_dsi : 0;
                      const riskLabel = dsi < 50 ? '안전' : dsi < 60 ? '보통' : dsi < 65 ? '주의' : '위험';
                      return (
                        <tr key={b.id}>
                          <td>{i + 1}위</td>
                          <th scope="row">{b.name_ko} ({b.name_en})</th>
                          <td>{b.country}</td>
                          <td>{(b.models || []).length}개 모델</td>
                          <td>{Number.isFinite(b.critical_issue_rate) ? b.critical_issue_rate : 0}%</td>
                          <td>{dsi}점</td>
                          <td>{riskLabel}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="space-y-4">
                {sortedBrands.map((brand, idx) => (
                  <BrandRankingItem
                    key={brand.id}
                    brand={brand}
                    idx={idx}
                    isSelected={selectedBrand === brand.id}
                    onToggle={handleBrandToggle}
                  />
                ))}
              </div>
            </div>
          )}

          {/* TAB 3: CATEGORY DISTRIBUTION CHART */}
          {activeChartTab === 'category_share' && (
            <div className="space-y-6">
              <div className="text-xs text-slate-700 leading-relaxed">
                전기차 차주들이 가장 많이 겪는 결함 유형의 산업 전체 점유율과 예상 수리비 분석치입니다.
              </div>

              {categories.length === 0 ? (
                <div className="p-8 text-center text-slate-700 bg-slate-50 rounded-2xl border border-slate-200 text-sm">
                  부문별 결함 비중 데이터가 없습니다.
                </div>
              ) : (
                <>
                  {/* Category Color Legend */}
                  <ul
                    aria-label="결함 부문별 산업 점유율 범례"
                    className="flex flex-wrap items-center gap-x-4 gap-y-2 p-3.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-800 list-none m-0 p-0"
                  >
                    {categories.map((cat) => (
                      <li key={cat.code} className="flex items-center gap-1.5">
                        <span className={`w-3 h-3 rounded-full ${CATEGORY_BG_COLORS[cat.code] || 'bg-slate-500'} inline-block shadow-sm`} aria-hidden="true" />
                        <span>{cat.label_ko} ({cat.industry_share_pct}%)</span>
                      </li>
                    ))}
                  </ul>

                  {/* Stacked Proportional Bar */}
                  <div className="space-y-2">
                    <p id="category-share-summary" className="sr-only">
                      전기차 6대 주요 결함 부문(배터리·충전, 구동계·모터, 소프트웨어·전자장비, 조립품질, 수리비·정비, 혹한기 특성)의 산업 전체 결함 발생 비중을 나타내는 누적 점유율 바입니다.
                    </p>
                    <div
                      role="region"
                      aria-label="전기차 결함 부문별 산업 점유율 분포 바"
                      aria-describedby="category-share-summary"
                      className="w-full h-6 rounded-xl overflow-hidden flex shadow-inner border border-slate-200"
                    >
                      {categories.map((cat) => {
                        const safeShare = Number.isFinite(cat.industry_share_pct) ? Math.max(0, cat.industry_share_pct) : 0;
                        if (safeShare === 0) return null;
                        const baseTotal = totalCategoryShare > 0 ? totalCategoryShare : 100;
                        const normalizedWidth = (safeShare / baseTotal) * 100;
                        return (
                          <div
                            key={cat.code}
                            style={{ width: `${normalizedWidth}%` }}
                            className={`${CATEGORY_BG_COLORS[cat.code] || 'bg-slate-500'} transition-all hover:opacity-80 shrink-0`}
                            role="img"
                            aria-label={`${cat.label_ko} 점유율 ${safeShare}%`}
                            title={`${cat.label_ko}: ${safeShare}%`}
                          />
                        );
                      })}
                    </div>

                    {/* Screen-reader accessible data table alternative */}
                    <div className="sr-only">
                      <table aria-label="전기차 결함 부문별 산업 점유율 데이터 표">
                        <caption>전기차 주요 결함 유형별 산업 점유율 분포</caption>
                        <thead>
                          <tr>
                            <th scope="col">결함 부문</th>
                            <th scope="col">산업 점유율</th>
                            <th scope="col">평균 예상 수리비 범위</th>
                            <th scope="col">주요 결함 증상 요약</th>
                          </tr>
                        </thead>
                        <tbody>
                          {categories.map((cat) => (
                            <tr key={cat.code}>
                              <th scope="row">{cat.label_ko}</th>
                              <td>{cat.industry_share_pct}%</td>
                              <td>{cat.avg_repair_cost_range}</td>
                              <td>{cat.description}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Detailed Category Cards Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {categories.map((cat) => (
                      <CategoryShareCard
                        key={cat.code}
                        cat={cat}
                        isSelected={selectedCategory === cat.code}
                        onToggle={handleCategoryToggle}
                      />
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </section>

      {/* 3. MULTI-FILTER TOOLBAR */}
      <section aria-label="결함 통계 검색 및 다중 필터 제어판" className="bg-white rounded-3xl p-6 shadow-sm border border-slate-200 space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div role="search" className="relative flex-1">
            <label htmlFor="reliability-search-input" className="sr-only">차종, 브랜드, 결함 증상 검색</label>
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-600">
              <svg className="w-5 h-5" width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <input
              id="reliability-search-input"
              type="text"
              ref={searchInputRef}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Escape' && searchQuery) {
                  e.preventDefault();
                  setSearchQuery('');
                }
              }}
              aria-describedby="reliability-search-hint"
              aria-label="차종, 브랜드, 결함 증상 검색"
              placeholder="차종명, 브랜드, 결함 증상(ICCU, 배터리, 옥토밸브, 백색가루 등) 검색..."
              className="w-full pl-10 pr-10 py-2.5 min-h-[44px] bg-slate-50 border border-slate-300 rounded-xl text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus:bg-white transition placeholder-slate-500"
            />
            <span id="reliability-search-hint" className="sr-only">
              검색어를 입력하면 실시간으로 차종 목록이 필터링됩니다. ESC 키를 누르면 검색어가 초기화됩니다.
            </span>
            {searchQuery && (
              <button
                type="button"
                onClick={() => {
                  setSearchQuery('');
                  searchInputRef.current?.focus();
                }}
                className="absolute inset-y-0 right-0 pr-3 min-w-[44px] min-h-[44px] flex items-center justify-center text-slate-700 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
                title="검색어 지우기"
                aria-label="검색어 지우기"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>

          <div className="flex items-center gap-3">
            <label htmlFor="reliability-sort-select" className="sr-only">정렬 기준 선택</label>
            <select
              id="reliability-sort-select"
              value={sortBy}
              onChange={(e) => {
                if (isReliabilitySortOption(e.target.value)) {
                  setSortBy(e.target.value);
                }
              }}
              aria-label="정렬 기준 선택"
              className="px-3 py-2 min-h-[44px] bg-slate-50 border border-slate-300 rounded-xl text-xs sm:text-sm font-medium text-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            >
              <option value="DSI_DESC">DSI 위험도 높은 순</option>
              <option value="DSI_ASC">DSI 안전한 순</option>
              <option value="GRADE">내구성 등급순 (A+ → F)</option>
              <option value="NAME">차종 이름순</option>
            </select>

            {hasActiveFilter && (
              <button
                type="button"
                onClick={() => {
                  resetFilters();
                  searchInputRef.current?.focus();
                }}
                className="px-3 py-2 min-h-[44px] inline-flex items-center gap-1 bg-rose-50 hover:bg-rose-100 text-rose-800 text-xs sm:text-sm font-semibold rounded-xl border border-rose-200 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              >
                <span>필터 초기화</span>
                <span aria-hidden="true">↺</span>
              </button>
            )}
          </div>
        </div>

        {/* Brand Selector Buttons */}
        <div role="group" aria-labelledby="brand-filter-heading" className="space-y-2">
          <div id="brand-filter-heading" className="text-xs font-semibold text-slate-700 uppercase tracking-wider">제조사 브랜드</div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setSelectedBrand('ALL')}
              aria-pressed={selectedBrand === 'ALL'}
              className={`px-3 py-1.5 min-h-[44px] inline-flex items-center text-xs font-bold rounded-xl transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                selectedBrand === 'ALL'
                  ? 'bg-slate-900 text-white shadow-sm'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              전체 ({allModels.length})
            </button>
            {brands.map((brand) => (
              <button
                key={brand.id}
                type="button"
                onClick={() => setSelectedBrand(selectedBrand === brand.id ? 'ALL' : brand.id)}
                aria-pressed={selectedBrand === brand.id}
                className={`px-3 py-1.5 min-h-[44px] text-xs font-bold rounded-xl transition inline-flex items-center gap-1.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                  selectedBrand === brand.id
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                <span>{brand.name_ko}</span>
                <span className="text-[10px] opacity-75">({(brand.models || []).length})</span>
              </button>
            ))}
          </div>
        </div>

        {/* Quick Filter Row: Verdict & Year */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-slate-100">
          {/* Verdict Filter */}
          <div role="group" aria-labelledby="verdict-filter-heading" className="space-y-1.5">
            <div id="verdict-filter-heading" className="text-xs font-semibold text-slate-700">판정 가이드 (Verdict)</div>
            <div className="flex flex-wrap gap-1.5">
              <button
                type="button"
                onClick={() => setSelectedVerdict('ALL')}
                aria-pressed={selectedVerdict === 'ALL'}
                className={`px-2.5 py-1 min-h-[44px] inline-flex items-center text-xs font-medium rounded-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                  selectedVerdict === 'ALL'
                    ? 'bg-slate-800 text-white'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                전체
              </button>
              <button
                type="button"
                onClick={() => setSelectedVerdict('AVOID')}
                aria-pressed={selectedVerdict === 'AVOID'}
                className={`px-2.5 py-1 min-h-[44px] inline-flex items-center text-xs font-medium rounded-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                  selectedVerdict === 'AVOID'
                    ? 'bg-rose-700 text-white shadow-sm'
                    : 'bg-rose-50 text-rose-800 border border-rose-200 hover:bg-rose-100'
                }`}
              >
                <span aria-hidden="true" className="mr-1">🚫</span> 구매 회피 (AVOID)
              </button>
              <button
                type="button"
                onClick={() => setSelectedVerdict('CAUTION')}
                aria-pressed={selectedVerdict === 'CAUTION'}
                className={`px-2.5 py-1 min-h-[44px] inline-flex items-center text-xs font-medium rounded-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                  selectedVerdict === 'CAUTION'
                    ? 'bg-amber-500 text-slate-950 font-extrabold shadow-sm'
                    : 'bg-amber-50 text-amber-900 border border-amber-200 hover:bg-amber-100'
                }`}
              >
                <span aria-hidden="true" className="mr-1">⚠️</span> 주의 요망 (CAUTION)
              </button>
              <button
                type="button"
                onClick={() => setSelectedVerdict('BUY_SAFE')}
                aria-pressed={selectedVerdict === 'BUY_SAFE'}
                className={`px-2.5 py-1 min-h-[44px] inline-flex items-center text-xs font-medium rounded-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                  selectedVerdict === 'BUY_SAFE'
                    ? 'bg-emerald-700 text-white shadow-sm'
                    : 'bg-emerald-50 text-emerald-800 border border-emerald-200 hover:bg-emerald-100'
                }`}
              >
                <span aria-hidden="true" className="mr-1">✅</span> 안심 추천 (BUY SAFE)
              </button>
            </div>
          </div>

          {/* Year Range Filter */}
          <div role="group" aria-labelledby="year-filter-heading" className="space-y-1.5">
            <div id="year-filter-heading" className="text-xs font-semibold text-slate-700">연식 대역</div>
            <div className="flex flex-wrap gap-1.5">
              <button
                type="button"
                onClick={() => setSelectedYearRange('ALL')}
                aria-pressed={selectedYearRange === 'ALL'}
                className={`px-2.5 py-1 min-h-[44px] inline-flex items-center text-xs font-medium rounded-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                  selectedYearRange === 'ALL'
                    ? 'bg-slate-800 text-white'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                전체 연식
              </button>
              <button
                type="button"
                onClick={() => setSelectedYearRange('EARLY')}
                aria-pressed={selectedYearRange === 'EARLY'}
                className={`px-2.5 py-1 min-h-[44px] inline-flex items-center text-xs font-medium rounded-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                  selectedYearRange === 'EARLY'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                초기형 (2017~2020)
              </button>
              <button
                type="button"
                onClick={() => setSelectedYearRange('MID')}
                aria-pressed={selectedYearRange === 'MID'}
                className={`px-2.5 py-1 min-h-[44px] inline-flex items-center text-xs font-medium rounded-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                  selectedYearRange === 'MID'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                과도기 (2021~2023)
              </button>
              <button
                type="button"
                onClick={() => setSelectedYearRange('LATE')}
                aria-pressed={selectedYearRange === 'LATE'}
                className={`px-2.5 py-1 min-h-[44px] inline-flex items-center text-xs font-medium rounded-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                  selectedYearRange === 'LATE'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                최신형 (2024~2025)
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* 4. MODEL CARDS GRID */}
      <section aria-labelledby="model-reliability-heading" className="space-y-4">
        <h2 id="model-reliability-heading" className="text-2xl font-bold text-slate-900 mb-6">차종별 신뢰성 상세 분석</h2>
        <div className="flex items-center justify-between">
          <div className="text-sm font-semibold text-slate-700" aria-live="polite" aria-atomic="true">
            총 <strong className="text-slate-900">{sortedModels.length}</strong>개 차종 표시 중
          </div>
          {hasActiveFilter && (
            <div className="text-xs text-blue-800 font-semibold">
              필터 적용됨
            </div>
          )}
        </div>

        {sortedModels.length === 0 ? (
          <div className="text-center py-16 bg-white rounded-3xl border border-slate-200 space-y-3">
            <div className="text-4xl" aria-hidden="true">🔍</div>
            <h3 className="text-lg font-bold text-slate-800">
              {allModels.length === 0 ? '등록된 차종 신뢰성 데이터가 없습니다' : '일치하는 차종 데이터가 없습니다'}
            </h3>
            <p className="text-sm text-slate-700 max-w-md mx-auto">
              {allModels.length === 0
                ? '현재 분석 가능한 전기차 결함 데이터가 없습니다.'
                : '검색어나 필터 조건을 변경해 보세요. 다양한 연식과 브랜드를 종합적으로 제공합니다.'}
            </p>
            {hasActiveFilter && (
              <button
                type="button"
                onClick={() => {
                  resetFilters();
                  searchInputRef.current?.focus();
                }}
                className="mt-2 px-4 py-2 min-h-[44px] inline-flex items-center bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              >
                전체 모델 보기
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {sortedModels.map((model) => (
              <ModelCardItem key={model.id} model={model} />
            ))}
          </div>
        )}
      </section>

      {/* 5. OUT-OF-WARRANTY REPAIR COST MATRIX TABLE */}
      <section aria-labelledby="repair-cost-heading" className="bg-white rounded-3xl p-6 sm:p-8 shadow-sm border border-slate-200 space-y-6">
        <div className="max-w-3xl space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-rose-50 text-rose-800 text-xs font-bold border border-rose-200">
            <span aria-hidden="true">💣</span>
            <span>중고 전기차 구매자 필수 참고</span>
          </div>
          <h2 id="repair-cost-heading" className="text-2xl font-bold text-slate-900 tracking-tight">
            보증 만료 후 폭탄 수리비 및 핵심 부품별 교체 비용 매트릭스
          </h2>
          <p className="text-sm text-slate-700 leading-relaxed">
            전기차는 일반 내연기관 차량과 달리 핵심 전동화 부품(배터리, ICCU, 모터/인버터)의 무상 보증(8년/16만 km 등)이 종료되거나 하부 긁힘으로 보증이 거부될 경우 천문학적인 수리비가 청구됩니다. 실제 서비스센터 견적 기준 데이터입니다.
          </p>
        </div>

        <div
          tabIndex={0}
          role="region"
          aria-label="보증 만료 후 부품별 수리비 매트릭스 표 스크롤 영역"
          className="overflow-x-auto border border-slate-200 rounded-2xl focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        >
          <table className="w-full min-w-[700px] text-left text-xs sm:text-sm border-collapse" aria-label="보증 만료 후 폭탄 수리비 및 핵심 부품별 교체 비용 매트릭스">
            <caption className="p-4 text-left font-bold text-slate-900 text-sm sm:text-base border-b border-slate-100 bg-slate-50/50">
              보증 만료 후 폭탄 수리비 및 핵심 부품별 교체 비용 매트릭스
              <span className="block text-xs font-normal text-slate-700 mt-1">
                주요 전동화 부품별 표준 보증 기간, 고위험 취약 모델 및 센터 공식 견적 비교
              </span>
            </caption>
            <thead>
              <tr className="bg-slate-900 text-white">
                <th scope="col" className="p-4 font-semibold min-w-[180px] sticky left-0 bg-slate-900 z-10">핵심 부품명</th>
                <th scope="col" className="p-4 font-semibold min-w-[160px]">예상 교체 비용</th>
                <th scope="col" className="p-4 font-semibold min-w-[140px]">표준 보증 기준</th>
                <th scope="col" className="p-4 font-semibold min-w-[180px]">고위험 취약 차종</th>
                <th scope="col" className="p-4 font-semibold min-w-[260px]">치명적 경고 및 주의사항</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {repairCostMatrix.length === 0 ? (
                <tr>
                  <td colSpan={5} className="p-8 text-center text-slate-700 text-sm">
                    등록된 보증 외 수리비 매트릭스 데이터가 없습니다.
                  </td>
                </tr>
              ) : (
                repairCostMatrix.map((item) => (
                  <RepairCostMatrixRow key={item.component_name} item={item} />
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* 6. CONSUMER SURVIVAL GUIDE BANNER */}
      <section aria-labelledby="recall-banner-heading" className="bg-gradient-to-r from-blue-900 to-indigo-900 text-white rounded-3xl p-6 sm:p-8 shadow-lg flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="space-y-2 max-w-2xl">
          <h2 id="recall-banner-heading" className="text-xl sm:text-2xl font-black">
            <span aria-hidden="true" className="mr-1.5">🚨</span>내 차의 공식 화재 리콜 및 배터리 제조사가 궁금하신가요?
          </h2>
          <p className="text-sm text-blue-200 leading-relaxed">
            국토교통부 및 자동차리콜센터의 실시간 리콜 캠페인 데이터와 17자리 차대번호(VIN) 조회기를 통해 배터리 제조사(LGES, SK On, CATL, 파라시스)와 긴급 무상 수리 대상 여부를 즉시 확인하세요.
          </p>
        </div>
        <Link
          href="/recall-portal"
          prefetch={false}
          className="px-6 py-3.5 min-h-[44px] inline-flex items-center justify-center gap-1.5 bg-white text-blue-900 hover:bg-blue-50 font-extrabold rounded-2xl shadow-md transition shrink-0 text-sm sm:text-base text-center focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-300 focus-visible:ring-offset-2 focus-visible:ring-offset-blue-900"
        >
          <span>공식 리콜 &amp; 배터리 조회 포털 가기</span>
          <span aria-hidden="true">&rarr;</span>
        </Link>
      </section>
    </div>
  );
}

interface ModelCardItemProps {
  model: EnrichedModelItem;
}

const ModelCardItem = React.memo(function ModelCardItem({ model }: ModelCardItemProps) {
  const gradeStyle = getGradeBadgeStyle(model.overall_grade);
  const safeDsi = Number.isFinite(model?.avg_dsi) ? model.avg_dsi : 0;
  const dsiInfo = getDsiSeverityLevel(safeDsi);

  return (
    <article
      aria-labelledby={`model-title-${model.id}`}
      className="bg-white rounded-3xl p-6 border border-slate-200 shadow-sm hover:shadow-xl transition-all duration-300 flex flex-col justify-between"
    >
      <div className="space-y-4">
        {/* Card Header */}
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-xs font-semibold text-blue-800 tracking-wide uppercase">
              {[model.brand_name_ko, model.segment].filter(Boolean).join(' · ')}
            </div>
            <h3 id={`model-title-${model.id}`} className="text-xl font-extrabold text-slate-900 mt-0.5 tracking-tight">
              {model.name}
            </h3>
          </div>
          <div
            className={`px-3 py-1 rounded-2xl border font-black text-sm sm:text-base shrink-0 ${gradeStyle.bg} ${gradeStyle.text} ${gradeStyle.border}`}
            title={`내구성 등급: ${model.overall_grade}`}
          >
            {model.overall_grade} 등급
          </div>
        </div>

        {/* DSI Gauge */}
        <div
          role="region"
          aria-labelledby={`model-dsi-title-${model.id}`}
          aria-describedby={`model-dsi-desc-${model.id}`}
          className="bg-slate-50 rounded-2xl p-3.5 border border-slate-100 space-y-2"
        >
          <div className="flex items-center justify-between text-xs">
            <span id={`model-dsi-title-${model.id}`} className="font-semibold text-slate-700">
              평균 결함 심각도 (DSI)
            </span>
            <span className={`font-black text-sm ${dsiInfo.textColor}`}>
              {safeDsi.toFixed(1)}점
            </span>
          </div>
          <div
            role="progressbar"
            aria-valuenow={Math.round(safeDsi)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`${model.brand_name_ko} ${model.name} 평균 결함 심각도 지수 DSI`}
            aria-valuetext={`${safeDsi.toFixed(1)}점 (${dsiInfo.label})`}
            aria-describedby={`model-dsi-desc-${model.id}`}
            className="w-full bg-slate-200 rounded-full h-2.5 overflow-hidden"
          >
            <div
              className={`h-full rounded-full transition-all duration-300 ${dsiInfo.barBgClass}`}
              style={{ width: `${Math.min(100, Math.max(10, safeDsi))}%` }}
            />
          </div>
          <div id={`model-dsi-desc-${model.id}`} className="flex justify-between text-[10px] text-slate-700 font-semibold">
            <span>안전 (0점)</span>
            <span className={dsiInfo.textColor}>{dsiInfo.label}</span>
            <span>치명 (100점)</span>
          </div>
        </div>

        {/* Year Evaluations Accordion List */}
        <div className="space-y-2">
          <div className="text-xs font-bold text-slate-700">연식별 내구성 평가</div>
          <ul
            role="list"
            tabIndex={0}
            aria-label={`${model.brand_name_ko} ${model.name} 연식별 평가 목록`}
            className="space-y-2 max-h-56 overflow-y-auto pr-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-lg outline-none list-none m-0 p-0"
          >
            {(!model.year_evaluations || model.year_evaluations.length === 0) ? (
              <li className="p-3 text-center text-xs text-slate-700 bg-slate-50 rounded-xl">
                연식별 세부 평가 데이터가 없습니다.
              </li>
            ) : (
              model.year_evaluations.map((yEval) => {
                const vInfo = getVerdictBadgeInfo(yEval.verdict);
                const safeRate = Number.isFinite(yEval.incident_rate) ? yEval.incident_rate : 0;

                return (
                  <li
                    key={yEval.year}
                    className={`p-2.5 rounded-xl border text-xs space-y-1 ${
                      yEval.verdict === 'AVOID'
                        ? 'bg-rose-50/70 border-rose-200 text-rose-950'
                        : yEval.verdict === 'CAUTION'
                        ? 'bg-amber-50/70 border-amber-200 text-amber-950'
                        : 'bg-emerald-50/70 border-emerald-200 text-emerald-950'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold">{yEval.year}년식</span>
                      <span className={`px-2 py-0.5 rounded-full font-extrabold text-[10px] ${vInfo.badgeClass}`}>
                        {yEval.verdict === 'AVOID' ? '구매 회피' : yEval.verdict === 'CAUTION' ? '주의 요망' : '안심 추천'}
                      </span>
                    </div>
                    <div className="text-[11px] font-medium leading-snug">
                      {yEval.primary_defect}
                    </div>
                    <div className="flex items-center justify-between text-[10px] text-slate-700 pt-1 border-t border-slate-200/40">
                      <span>발생률: <strong>{safeRate}%</strong></span>
                      <span>예상 수리비: <strong>{yEval.estimated_repair_cost}</strong></span>
                    </div>
                  </li>
                );
              })
            )}
          </ul>
        </div>

        {/* Authentic Owner Quote */}
        {model.year_evaluations?.[0]?.raw_quote && (
          <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80 text-xs text-slate-700 italic">
            <span className="text-slate-700 font-serif mr-1">&ldquo;</span>
            {model.year_evaluations[0].raw_quote}
            <span className="text-slate-700 font-serif ml-1">&rdquo;</span>
          </div>
        )}
      </div>

      {/* Card Action Link */}
      <div className="pt-4 mt-4 border-t border-slate-100 flex items-center justify-between">
        <Link
          href={`/recall-portal?model=${encodeURIComponent(model.name)}`}
          prefetch={false}
          className="text-xs font-bold text-blue-800 hover:text-blue-950 min-h-[44px] flex items-center gap-1.5 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
        >
          <span aria-hidden="true">🚨</span>
          <span>이 차종 공식 리콜·화재 조회</span>
          <span aria-hidden="true">&rarr;</span>
        </Link>
      </div>
    </article>
  );
});
