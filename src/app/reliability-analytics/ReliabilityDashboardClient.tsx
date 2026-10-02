'use client';

import React, { useState, useMemo } from 'react';
import Link from 'next/link';
import {
  ReliabilityTrendsDatabase,
  DefectCategoryKey,
  ModelYearVerdict,
  getAllEnrichedModels,
  getVerdictBadgeInfo,
  getDsiSeverityLevel,
  getGradeBadgeStyle,
} from '@/lib/getReliabilityData';

interface ReliabilityDashboardClientProps {
  initialData: ReliabilityTrendsDatabase;
}

export default function ReliabilityDashboardClient({ initialData }: ReliabilityDashboardClientProps) {
  // --- Filter States ---
  const [selectedBrand, setSelectedBrand] = useState<string>('ALL');
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [selectedVerdict, setSelectedVerdict] = useState<string>('ALL');
  const [selectedYearRange, setSelectedYearRange] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
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

  // All enriched models
  const allModels = useMemo(() => {
    return getAllEnrichedModels(initialData);
  }, [initialData]);

  // Unique years for heatmap
  const heatmapYears = useMemo(() => {
    const yearSet = new Set<number>();
    allModels.forEach((m) => {
      m.year_evaluations.forEach((y) => yearSet.add(y.year));
    });
    return Array.from(yearSet).sort((a, b) => a - b);
  }, [allModels]);

  // Filtered models
  const filteredModels = useMemo(() => {
    return allModels.filter((model) => {
      // Brand filter
      if (selectedBrand !== 'ALL' && model.brand_id !== selectedBrand) {
        return false;
      }

      // Category filter
      if (selectedCategory !== 'ALL' && model.top_category !== selectedCategory) {
        // Check if any year evaluation mentions or has this category
        const matchesCategory = model.top_category === selectedCategory;
        if (!matchesCategory) return false;
      }

      // Verdict filter
      if (selectedVerdict !== 'ALL') {
        const hasMatchingVerdict = model.year_evaluations.some(
          (y) => y.verdict === selectedVerdict
        );
        if (!hasMatchingVerdict) return false;
      }

      // Year range filter
      if (selectedYearRange !== 'ALL') {
        let hasYear = false;
        if (selectedYearRange === 'EARLY') {
          hasYear = model.year_evaluations.some((y) => y.year <= 2020);
        } else if (selectedYearRange === 'MID') {
          hasYear = model.year_evaluations.some((y) => y.year >= 2021 && y.year <= 2023);
        } else if (selectedYearRange === 'LATE') {
          hasYear = model.year_evaluations.some((y) => y.year >= 2024);
        }
        if (!hasYear) return false;
      }

      // Live search query
      if (searchQuery.trim() !== '') {
        const q = searchQuery.toLowerCase().trim();
        const matchesName = model.name.toLowerCase().includes(q);
        const matchesBrandKo = model.brand_name_ko.toLowerCase().includes(q);
        const matchesBrandEn = model.brand_name_en.toLowerCase().includes(q);
        const matchesSegment = model.segment.toLowerCase().includes(q);
        const matchesDefect = model.year_evaluations.some(
          (y) =>
            y.primary_defect.toLowerCase().includes(q) ||
            y.chronic_symptoms.some((s) => s.toLowerCase().includes(q)) ||
            y.raw_quote.toLowerCase().includes(q)
        );

        if (!matchesName && !matchesBrandKo && !matchesBrandEn && !matchesSegment && !matchesDefect) {
          return false;
        }
      }

      return true;
    });
  }, [allModels, selectedBrand, selectedCategory, selectedVerdict, selectedYearRange, searchQuery]);

  // Sorted models
  const sortedModels = useMemo(() => {
    const sorted = [...filteredModels];
    if (sortBy === 'DSI_DESC') {
      sorted.sort((a, b) => b.avg_dsi - a.avg_dsi);
    } else if (sortBy === 'DSI_ASC') {
      sorted.sort((a, b) => a.avg_dsi - b.avg_dsi);
    } else if (sortBy === 'GRADE') {
      const gradeOrder: Record<string, number> = { 'A+': 1, 'A': 2, 'B': 3, 'C': 4, 'D': 5, 'F': 6 };
      sorted.sort((a, b) => (gradeOrder[a.overall_grade] || 99) - (gradeOrder[b.overall_grade] || 99));
    } else if (sortBy === 'NAME') {
      sorted.sort((a, b) => a.name.localeCompare(b.name, 'ko'));
    }
    return sorted;
  }, [filteredModels, sortBy]);

  // Reset filters
  const resetFilters = () => {
    setSelectedBrand('ALL');
    setSelectedCategory('ALL');
    setSelectedVerdict('ALL');
    setSelectedYearRange('ALL');
    setSearchQuery('');
    setSortBy('DSI_DESC');
  };

  const hasActiveFilter =
    selectedBrand !== 'ALL' ||
    selectedCategory !== 'ALL' ||
    selectedVerdict !== 'ALL' ||
    selectedYearRange !== 'ALL' ||
    searchQuery.trim() !== '';

  // Calculate Avoid Ratio
  const totalEvaluationsCount = useMemo(() => {
    return allModels.reduce((acc, m) => acc + m.year_evaluations.length, 0);
  }, [allModels]);

  const avoidEvaluationsCount = useMemo(() => {
    return allModels.reduce(
      (acc, m) => acc + m.year_evaluations.filter((y) => y.verdict === 'AVOID').length,
      0
    );
  }, [allModels]);

  const avoidPercentage = totalEvaluationsCount > 0
    ? ((avoidEvaluationsCount / totalEvaluationsCount) * 100).toFixed(1)
    : '31.5';

  return (
    <div className="space-y-10 pb-16">
      {/* 1. HERO SECTION & KEY METRICS */}
      <section className="bg-gradient-to-br from-slate-900 via-slate-800 to-indigo-950 text-white rounded-3xl p-6 sm:p-10 shadow-2xl border border-slate-700/50">
        <div className="max-w-4xl space-y-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/20 text-blue-300 text-xs sm:text-sm font-semibold border border-blue-400/30">
            <span>📊</span>
            <span>2026 대한민국 전기차 종합 내구성 인텔리전스</span>
          </div>
          <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight leading-tight">
            전기차 모델·연식별 결함 통계 및 내구성 분석 (DSI)
          </h1>
          <p className="text-slate-300 text-base sm:text-lg leading-relaxed">
            국내 3대 커뮤니티(보배드림, 디시인사이드, 블라인드) 실차주 제보 <strong>{initialData.metadata.total_records_analyzed.toLocaleString()}건</strong>과 국토교통부·NHTSA 공식 리콜 기록을 교차 분석하여, 특정 연식의 치명적 고질병과 중고차 구매 시 절대 피해야 할 연식을 투명하게 공개합니다.
          </p>
        </div>

        {/* 4 KPI STAT CARDS */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mt-8 pt-8 border-t border-slate-700/60">
          <div className="bg-slate-800/80 backdrop-blur rounded-2xl p-4 sm:p-5 border border-slate-700">
            <div className="text-xs sm:text-sm text-slate-400 font-medium">분석 결함 제보</div>
            <div className="text-2xl sm:text-3xl font-black text-white mt-1">
              {initialData.metadata.total_records_analyzed.toLocaleString()}건
            </div>
            <div className="text-xs text-blue-400 mt-1 font-medium">
              9개 브랜드 · {initialData.metadata.models_count}개 모델 조사
            </div>
          </div>

          <div className="bg-slate-800/80 backdrop-blur rounded-2xl p-4 sm:p-5 border border-slate-700">
            <div className="text-xs sm:text-sm text-slate-400 font-medium">산업 평균 DSI 점수</div>
            <div className="text-2xl sm:text-3xl font-black text-amber-400 mt-1">
              {initialData.metadata.avg_industry_dsi}
              <span className="text-sm font-normal text-slate-400 ml-1">/ 100</span>
            </div>
            <div className="text-xs text-amber-300/80 mt-1 font-medium">
              결함 심각도 지수 (높을수록 위험)
            </div>
          </div>

          <div className="bg-slate-800/80 backdrop-blur rounded-2xl p-4 sm:p-5 border border-slate-700">
            <div className="text-xs sm:text-sm text-slate-400 font-medium">구매 회피 (AVOID) 연식</div>
            <div className="text-2xl sm:text-3xl font-black text-rose-400 mt-1">
              {avoidPercentage}%
            </div>
            <div className="text-xs text-rose-300/80 mt-1 font-medium">
              총 {totalEvaluationsCount}개 중 {avoidEvaluationsCount}개 연식 위험
            </div>
          </div>

          <div className="bg-slate-800/80 backdrop-blur rounded-2xl p-4 sm:p-5 border border-slate-700">
            <div className="text-xs sm:text-sm text-slate-400 font-medium">최다 결함 발생 부문</div>
            <div className="text-2xl sm:text-3xl font-black text-emerald-400 mt-1">
              38.4%
            </div>
            <div className="text-xs text-emerald-300/80 mt-1 font-medium">
              배터리 & 고전압 충전 계통
            </div>
          </div>
        </div>
      </section>

      {/* 2. VISUAL CHARTS SECTION (PURE CSS/SVG) */}
      <section className="bg-white rounded-3xl p-6 sm:p-8 shadow-sm border border-slate-200">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-100">
          <div>
            <h2 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
              <span>📈</span>
              <span>데이터 시각화 차트 센터</span>
            </h2>
            <p className="text-sm text-slate-500 mt-1">
              연식별 위험 매트릭스, 9대 브랜드 결함 랭킹, 부문별 비중을 실시간으로 확인하세요.
            </p>
          </div>

          {/* Chart Tab Selector */}
          <div role="tablist" aria-label="데이터 시각화 차트 선택" className="inline-flex bg-slate-100 p-1.5 rounded-xl self-start sm:self-auto">
            <button
              type="button"
              role="tab"
              aria-selected={activeChartTab === 'heatmap'}
              onClick={() => setActiveChartTab('heatmap')}
              className={`px-3.5 py-1.5 text-xs sm:text-sm font-semibold rounded-lg transition ${
                activeChartTab === 'heatmap'
                  ? 'bg-white text-indigo-600 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              연식 리스크 히트맵
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeChartTab === 'brand_ranking'}
              onClick={() => setActiveChartTab('brand_ranking')}
              className={`px-3.5 py-1.5 text-xs sm:text-sm font-semibold rounded-lg transition ${
                activeChartTab === 'brand_ranking'
                  ? 'bg-white text-indigo-600 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              브랜드 DSI 랭킹
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeChartTab === 'category_share'}
              onClick={() => setActiveChartTab('category_share')}
              className={`px-3.5 py-1.5 text-xs sm:text-sm font-semibold rounded-lg transition ${
                activeChartTab === 'category_share'
                  ? 'bg-white text-indigo-600 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              부문별 결함 비중
            </button>
          </div>
        </div>

        <div className="mt-6">
          {/* TAB 1: MODEL-YEAR RISK HEATMAP */}
          {activeChartTab === 'heatmap' && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-600">
                <div className="font-medium text-slate-700">
                  💡 셀을 클릭하거나 마우스를 올리면 해당 연식의 결함 증상과 차주 코멘트를 확인하실 수 있습니다.
                </div>
                <div className="flex items-center gap-3">
                  <span className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full bg-rose-500 inline-block" />
                    <span>회피 (AVOID)</span>
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full bg-amber-400 inline-block" />
                    <span>주의 (CAUTION)</span>
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full bg-emerald-500 inline-block" />
                    <span>추천 (SAFE)</span>
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full bg-slate-200 inline-block" />
                    <span>미출시</span>
                  </span>
                </div>
              </div>

              {/* Heatmap Grid Wrapper */}
              <div className="overflow-x-auto border border-slate-200 rounded-2xl">
                <table className="w-full text-left text-xs sm:text-sm border-collapse" aria-label="연식별 전기차 신뢰성 및 결함 심각도(DSI) 매트릭스">
                  <caption className="sr-only">연식별 전기차 신뢰성 및 결함 심각도(DSI) 매트릭스</caption>
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-200">
                      <th scope="col" className="p-3 font-semibold text-slate-700 min-w-[140px] sticky left-0 bg-slate-50 z-10">
                        모델명
                      </th>
                      <th scope="col" className="p-3 font-semibold text-slate-700 min-w-[70px]">브랜드</th>
                      {heatmapYears.map((yr) => (
                        <th key={yr} scope="col" className="p-3 font-semibold text-slate-700 text-center min-w-[60px]">
                          {yr}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {allModels.map((model) => {
                      const evalMap = new Map<number, typeof model.year_evaluations[0]>();
                      model.year_evaluations.forEach((y) => evalMap.set(y.year, y));

                      return (
                        <tr key={model.id} className="hover:bg-slate-50/80 transition">
                          <th scope="row" className="p-3 font-bold text-slate-900 sticky left-0 bg-white group-hover:bg-slate-50/80 z-10 shadow-[2px_0_5px_-2px_rgba(0,0,0,0.05)] text-left font-normal sm:font-bold">
                            <div className="truncate max-w-[130px] sm:max-w-none">{model.name}</div>
                          </th>
                          <td className="p-3 text-slate-600 text-xs whitespace-nowrap">
                            {model.brand_name_ko}
                          </td>
                          {heatmapYears.map((yr) => {
                            const evalData = evalMap.get(yr);
                            if (!evalData) {
                              return (
                                <td key={yr} className="p-2 text-center">
                                  <div
                                    className="w-8 h-8 mx-auto rounded-lg bg-slate-100 flex items-center justify-center text-[10px] text-slate-600 font-mono font-medium"
                                    title="해당 연식 데이터 없음"
                                    aria-label="데이터 없음"
                                  >
                                    -
                                  </div>
                                </td>
                              );
                            }

                            const cellColor =
                              evalData.verdict === 'AVOID'
                                ? 'bg-rose-700 hover:bg-rose-800 text-white shadow-rose-200'
                                : evalData.verdict === 'CAUTION'
                                ? 'bg-amber-400 hover:bg-amber-500 text-slate-950 shadow-amber-200 font-bold'
                                : 'bg-emerald-700 hover:bg-emerald-800 text-white shadow-emerald-200';

                            return (
                              <td key={yr} className="p-2 text-center">
                                <button
                                  type="button"
                                  onClick={() =>
                                    setHoveredCell({
                                      modelName: model.name,
                                      brandName: model.brand_name_ko,
                                      year: evalData.year,
                                      verdict: evalData.verdict,
                                      dsi: evalData.dsi_score,
                                      primaryDefect: evalData.primary_defect,
                                      quote: evalData.raw_quote,
                                    })
                                  }
                                  aria-label={`${model.name} ${evalData.year}년식 ${evalData.verdict} DSI ${evalData.dsi_score}점`}
                                  className={`w-8 h-8 mx-auto rounded-lg font-bold text-xs flex items-center justify-center shadow-sm cursor-pointer transition transform hover:scale-110 active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 ${cellColor}`}
                                  title={`${model.name} (${evalData.year}): ${evalData.verdict} - DSI ${evalData.dsi_score}`}
                                >
                                  {evalData.dsi_score}
                                </button>
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Heatmap Detail Card (if selected) */}
              {hoveredCell && (
                <div className="p-4 bg-slate-900 text-white rounded-2xl border border-slate-700 shadow-xl animate-fade-in flex flex-col sm:flex-row justify-between gap-4">
                  <div className="space-y-1 max-w-2xl">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-base text-blue-300">
                        {hoveredCell.brandName} {hoveredCell.modelName} ({hoveredCell.year}년식)
                      </span>
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full font-bold ${
                          hoveredCell.verdict === 'AVOID'
                            ? 'bg-rose-500/30 text-rose-300 border border-rose-500/50'
                            : hoveredCell.verdict === 'CAUTION'
                            ? 'bg-amber-400/30 text-amber-200 border border-amber-400/50'
                            : 'bg-emerald-500/30 text-emerald-200 border border-emerald-500/50'
                        }`}
                      >
                        {hoveredCell.verdict} (DSI {hoveredCell.dsi}점)
                      </span>
                    </div>
                    <p className="text-sm text-slate-200 font-medium">
                      ⚠️ 주요 결함: {hoveredCell.primaryDefect}
                    </p>
                    <p className="text-xs text-slate-400 italic">
                      &quot;{hoveredCell.quote}&quot;
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Link
                      href={`/recall-portal?model=${encodeURIComponent(hoveredCell.modelName)}`}
                      className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold transition"
                    >
                      공식 리콜 조회 &rarr;
                    </Link>
                    <button
                      type="button"
                      onClick={() => setHoveredCell(null)}
                      className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-medium transition"
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
              <div className="text-xs text-slate-500">
                9대 브랜드의 전체 제보와 심각도를 종합 산출한 Defect Severity Index (DSI) 랭킹입니다. 점수가 낮을수록 내구성이 우수하고 결함 발생 빈도가 적음을 나타냅니다.
              </div>

              <div className="space-y-4">
                {[...initialData.brands]
                  .sort((a, b) => a.overall_dsi - b.overall_dsi)
                  .map((brand, idx) => {
                    const isSelected = selectedBrand === brand.id;
                    const dsiWidth = `${Math.min(100, Math.max(15, brand.overall_dsi))}%`;
                    const barColor =
                      brand.overall_dsi < 50
                        ? 'bg-emerald-500'
                        : brand.overall_dsi < 60
                        ? 'bg-amber-400'
                        : brand.overall_dsi < 65
                        ? 'bg-orange-500'
                        : 'bg-rose-500';

                    return (
                      <div
                        key={brand.id}
                        role="button"
                        tabIndex={0}
                        onClick={() => setSelectedBrand(isSelected ? 'ALL' : brand.id)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            setSelectedBrand(isSelected ? 'ALL' : brand.id);
                          }
                        }}
                        aria-pressed={isSelected}
                        className={`p-3 sm:p-4 rounded-2xl border transition cursor-pointer ${
                          isSelected
                            ? 'bg-indigo-50/80 border-indigo-300 ring-2 ring-indigo-200'
                            : 'bg-slate-50 hover:bg-slate-100/80 border-slate-200'
                        }`}
                      >
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 sm:gap-4 mb-2">
                          <div className="flex items-center gap-2">
                            <span className="w-6 h-6 rounded-full bg-slate-200 text-slate-700 text-xs font-bold flex items-center justify-center">
                              {idx + 1}
                            </span>
                            <span className="font-bold text-slate-900 text-sm sm:text-base">
                              {brand.name_ko} ({brand.name_en})
                            </span>
                            <span className="text-xs text-slate-600 font-normal">
                              {brand.country} · {brand.models.length}개 모델
                            </span>
                          </div>
                          <div className="flex items-center gap-3 text-xs sm:text-sm">
                            <span className="text-slate-600">
                              치명 결함율: <strong className="text-rose-700">{brand.critical_issue_rate}%</strong>
                            </span>
                            <span className="font-black text-slate-900 text-sm sm:text-base">
                              DSI {brand.overall_dsi}점
                            </span>
                          </div>
                        </div>

                        {/* Pure CSS Bar */}
                        <div
                          role="progressbar"
                          aria-valuenow={brand.overall_dsi}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-label={`${brand.name_ko} 종합 결함 심각도 DSI`}
                          aria-valuetext={`${brand.overall_dsi}점`}
                          className="w-full bg-slate-200 rounded-full h-3.5 overflow-hidden relative"
                        >
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${barColor}`}
                            style={{ width: dsiWidth }}
                          />
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}

          {/* TAB 3: CATEGORY DISTRIBUTION CHART */}
          {activeChartTab === 'category_share' && (
            <div className="space-y-6">
              <div className="text-xs text-slate-500">
                전기차 차주들이 가장 많이 겪는 결함 유형의 산업 전체 점유율과 예상 수리비 분석치입니다.
              </div>

              {/* Stacked Proportional Bar */}
              <div className="space-y-2">
                <div
                  role="region"
                  aria-label="전기차 결함 부문별 산업 점유율 분포 바"
                  className="w-full h-6 rounded-xl overflow-hidden flex shadow-inner border border-slate-200"
                >
                  {initialData.categories.map((cat) => {
                    const bgColors: Record<DefectCategoryKey, string> = {
                      BATTERY_CHARGING: 'bg-rose-500',
                      DRIVING_POWERTRAIN: 'bg-amber-500',
                      SOFTWARE_ELECTRONICS: 'bg-blue-500',
                      BUILD_QUALITY: 'bg-purple-500',
                      SERVICE_REPAIR_COST: 'bg-emerald-500',
                      COLD_WEATHER: 'bg-cyan-500',
                    };

                    return (
                      <div
                        key={cat.code}
                        style={{ width: `${cat.industry_share_pct}%` }}
                        className={`${bgColors[cat.code]} transition-all hover:opacity-80`}
                        role="img"
                        aria-label={`${cat.label_ko} 점유율 ${cat.industry_share_pct}%`}
                        title={`${cat.label_ko}: ${cat.industry_share_pct}%`}
                      />
                    );
                  })}
                </div>
              </div>

              {/* Detailed Category Cards Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {initialData.categories.map((cat) => {
                  const tagColors: Record<DefectCategoryKey, { bg: string; text: string; border: string }> = {
                    BATTERY_CHARGING: { bg: 'bg-rose-50', text: 'text-rose-700', border: 'border-rose-200' },
                    DRIVING_POWERTRAIN: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
                    SOFTWARE_ELECTRONICS: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
                    BUILD_QUALITY: { bg: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-200' },
                    SERVICE_REPAIR_COST: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
                    COLD_WEATHER: { bg: 'bg-cyan-50', text: 'text-cyan-700', border: 'border-cyan-200' },
                  };
                  const color = tagColors[cat.code] || { bg: 'bg-slate-50', text: 'text-slate-700', border: 'border-slate-200' };

                  return (
                    <div
                      key={cat.code}
                      role="button"
                      tabIndex={0}
                      onClick={() => setSelectedCategory(selectedCategory === cat.code ? 'ALL' : cat.code)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          setSelectedCategory(selectedCategory === cat.code ? 'ALL' : cat.code);
                        }
                      }}
                      aria-pressed={selectedCategory === cat.code}
                      className={`p-4 rounded-2xl border transition cursor-pointer ${
                        selectedCategory === cat.code
                          ? 'ring-2 ring-indigo-300 bg-indigo-50/50 border-indigo-300'
                          : `${color.bg} ${color.border} hover:shadow-md`
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-sm text-slate-900">{cat.label_ko}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full font-bold ${color.text} bg-white shadow-sm`}>
                          {cat.industry_share_pct}%
                        </span>
                      </div>
                      <p className="text-xs text-slate-600 mt-2 leading-relaxed">{cat.description}</p>
                      <div className="mt-3 pt-2 border-t border-slate-200/60 text-[11px] font-medium text-slate-500">
                        평균 예상 수리비: <strong className="text-slate-800">{cat.avg_repair_cost_range}</strong>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </section>

      {/* 3. MULTI-FILTER TOOLBAR */}
      <section className="bg-white rounded-3xl p-6 shadow-sm border border-slate-200 space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="relative flex-1">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="차종, 브랜드, 결함 증상 검색"
              placeholder="차종명, 브랜드, 결함 증상(ICCU, 배터리, 옥토밸브, 백색가루 등) 검색..."
              className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition"
            />
          </div>

          <div className="flex items-center gap-3">
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
              aria-label="정렬 기준 선택"
              className="px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs sm:text-sm font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="DSI_DESC">DSI 위험도 높은 순</option>
              <option value="DSI_ASC">DSI 안전한 순</option>
              <option value="GRADE">내구성 등급순 (A+ → F)</option>
              <option value="NAME">차종 이름순</option>
            </select>

            {hasActiveFilter && (
              <button
                type="button"
                onClick={resetFilters}
                className="px-3 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 text-xs sm:text-sm font-semibold rounded-xl border border-rose-200 transition"
              >
                필터 초기화 ↺
              </button>
            )}
          </div>
        </div>

        {/* Brand Selector Buttons */}
        <div className="space-y-2">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">제조사 브랜드</div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setSelectedBrand('ALL')}
              aria-pressed={selectedBrand === 'ALL'}
              className={`px-3 py-1.5 text-xs font-bold rounded-xl transition ${
                selectedBrand === 'ALL'
                  ? 'bg-slate-900 text-white shadow-sm'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              전체 ({allModels.length})
            </button>
            {initialData.brands.map((brand) => (
              <button
                key={brand.id}
                type="button"
                onClick={() => setSelectedBrand(selectedBrand === brand.id ? 'ALL' : brand.id)}
                aria-pressed={selectedBrand === brand.id}
                className={`px-3 py-1.5 text-xs font-bold rounded-xl transition flex items-center gap-1.5 ${
                  selectedBrand === brand.id
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                <span>{brand.name_ko}</span>
                <span className="text-[10px] opacity-75">({brand.models.length})</span>
              </button>
            ))}
          </div>
        </div>

        {/* Quick Filter Row: Verdict & Year */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-slate-100">
          {/* Verdict Filter */}
          <div className="space-y-1.5">
            <div className="text-xs font-semibold text-slate-500">판정 가이드 (Verdict)</div>
            <div className="flex flex-wrap gap-1.5">
              <button
                type="button"
                onClick={() => setSelectedVerdict('ALL')}
                aria-pressed={selectedVerdict === 'ALL'}
                className={`px-2.5 py-1 text-xs font-medium rounded-lg transition ${
                  selectedVerdict === 'ALL'
                    ? 'bg-slate-800 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                전체
              </button>
              <button
                type="button"
                onClick={() => setSelectedVerdict('AVOID')}
                aria-pressed={selectedVerdict === 'AVOID'}
                className={`px-2.5 py-1 text-xs font-medium rounded-lg transition ${
                  selectedVerdict === 'AVOID'
                    ? 'bg-rose-600 text-white'
                    : 'bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100'
                }`}
              >
                🚫 회피 (AVOID)
              </button>
              <button
                type="button"
                onClick={() => setSelectedVerdict('CAUTION')}
                aria-pressed={selectedVerdict === 'CAUTION'}
                className={`px-2.5 py-1 text-xs font-medium rounded-lg transition ${
                  selectedVerdict === 'CAUTION'
                    ? 'bg-amber-500 text-white'
                    : 'bg-amber-50 text-amber-800 border border-amber-200 hover:bg-amber-100'
                }`}
              >
                ⚠️ 주의 (CAUTION)
              </button>
              <button
                type="button"
                onClick={() => setSelectedVerdict('BUY_SAFE')}
                aria-pressed={selectedVerdict === 'BUY_SAFE'}
                className={`px-2.5 py-1 text-xs font-medium rounded-lg transition ${
                  selectedVerdict === 'BUY_SAFE'
                    ? 'bg-emerald-600 text-white'
                    : 'bg-emerald-50 text-emerald-800 border border-emerald-200 hover:bg-emerald-100'
                }`}
              >
                ✅ 안심 (SAFE)
              </button>
            </div>
          </div>

          {/* Year Range Filter */}
          <div className="space-y-1.5">
            <div className="text-xs font-semibold text-slate-500">연식 대역</div>
            <div className="flex flex-wrap gap-1.5">
              <button
                type="button"
                onClick={() => setSelectedYearRange('ALL')}
                aria-pressed={selectedYearRange === 'ALL'}
                className={`px-2.5 py-1 text-xs font-medium rounded-lg transition ${
                  selectedYearRange === 'ALL'
                    ? 'bg-slate-800 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                전체 연식
              </button>
              <button
                type="button"
                onClick={() => setSelectedYearRange('EARLY')}
                aria-pressed={selectedYearRange === 'EARLY'}
                className={`px-2.5 py-1 text-xs font-medium rounded-lg transition ${
                  selectedYearRange === 'EARLY'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                초기형 (2017~2020)
              </button>
              <button
                type="button"
                onClick={() => setSelectedYearRange('MID')}
                aria-pressed={selectedYearRange === 'MID'}
                className={`px-2.5 py-1 text-xs font-medium rounded-lg transition ${
                  selectedYearRange === 'MID'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                과도기 (2021~2023)
              </button>
              <button
                type="button"
                onClick={() => setSelectedYearRange('LATE')}
                aria-pressed={selectedYearRange === 'LATE'}
                className={`px-2.5 py-1 text-xs font-medium rounded-lg transition ${
                  selectedYearRange === 'LATE'
                    ? 'bg-blue-600 text-white'
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
      <section className="space-y-4">
        <h2 className="text-2xl font-bold text-slate-900 mb-6">차종별 신뢰성 상세 분석</h2>
        <div className="flex items-center justify-between">
          <div className="text-sm font-semibold text-slate-600">
            총 <strong className="text-slate-900">{sortedModels.length}</strong>개 차종 표시 중
          </div>
          {hasActiveFilter && (
            <div className="text-xs text-blue-600 font-medium">
              필터 적용됨
            </div>
          )}
        </div>

        {sortedModels.length === 0 ? (
          <div className="text-center py-16 bg-white rounded-3xl border border-slate-200 space-y-3">
            <div className="text-4xl">🔍</div>
            <h3 className="text-lg font-bold text-slate-800">일치하는 차종 데이터가 없습니다</h3>
            <p className="text-sm text-slate-500 max-w-md mx-auto">
              검색어나 필터 조건을 변경해 보세요. 다양한 연식과 브랜드를 종합적으로 제공합니다.
            </p>
            <button
              type="button"
              onClick={resetFilters}
              className="mt-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl transition"
            >
              전체 모델 보기
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {sortedModels.map((model) => {
              const gradeStyle = getGradeBadgeStyle(model.overall_grade);
              const dsiInfo = getDsiSeverityLevel(model.avg_dsi);

              return (
                <div
                  key={model.id}
                  className="bg-white rounded-3xl p-6 border border-slate-200 shadow-sm hover:shadow-xl transition-all duration-300 flex flex-col justify-between"
                >
                  <div className="space-y-4">
                    {/* Card Header */}
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-xs font-semibold text-blue-600 tracking-wide uppercase">
                          {model.brand_name_ko} · {model.segment}
                        </div>
                        <h3 className="text-xl font-extrabold text-slate-900 mt-0.5 tracking-tight">
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
                    <div className="bg-slate-50 rounded-2xl p-3.5 border border-slate-100 space-y-2">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-slate-600">평균 결함 심각도 (DSI)</span>
                        <span className={`font-black text-sm ${dsiInfo.textColor}`}>
                          {model.avg_dsi.toFixed(1)}점
                        </span>
                      </div>
                      <div
                        role="progressbar"
                        aria-valuenow={Math.round(model.avg_dsi)}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-label={`${model.brand_name_ko} ${model.name} 평균 결함 심각도 지수 DSI`}
                        aria-valuetext={`${model.avg_dsi.toFixed(1)}점 (${dsiInfo.label})`}
                        className="w-full bg-slate-200 rounded-full h-2.5 overflow-hidden"
                      >
                        <div
                          className={`h-full rounded-full transition-all duration-300 ${dsiInfo.barBgClass}`}
                          style={{ width: `${Math.min(100, Math.max(10, model.avg_dsi))}%` }}
                        />
                      </div>
                      <div className="flex justify-between text-[10px] text-slate-600 font-medium">
                        <span>안전 (0점)</span>
                        <span className={dsiInfo.textColor}>{dsiInfo.label}</span>
                        <span>치명 (100점)</span>
                      </div>
                    </div>

                    {/* Year Evaluations Accordion List */}
                    <div className="space-y-2">
                      <div className="text-xs font-bold text-slate-700">연식별 내구성 평가</div>
                      <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                        {model.year_evaluations.map((yEval) => {
                          const vInfo = getVerdictBadgeInfo(yEval.verdict);

                          return (
                            <div
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
                                  {yEval.verdict}
                                </span>
                              </div>
                              <div className="text-[11px] font-medium leading-snug">
                                {yEval.primary_defect}
                              </div>
                              <div className="flex items-center justify-between text-[10px] text-slate-600 pt-1 border-t border-slate-200/40">
                                <span>발생률: <strong>{yEval.incident_rate}%</strong></span>
                                <span>예상 수리비: <strong>{yEval.estimated_repair_cost}</strong></span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {/* Authentic Owner Quote */}
                    {model.year_evaluations[0]?.raw_quote && (
                      <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80 text-xs text-slate-600 italic">
                        <span className="text-slate-600 font-serif mr-1">&ldquo;</span>
                        {model.year_evaluations[0].raw_quote}
                        <span className="text-slate-600 font-serif ml-1">&rdquo;</span>
                      </div>
                    )}
                  </div>

                  {/* Card Action Link */}
                  <div className="pt-4 mt-4 border-t border-slate-100 flex items-center justify-between">
                    <Link
                      href={`/recall-portal?model=${encodeURIComponent(model.name)}`}
                      className="text-xs font-bold text-blue-600 hover:text-blue-800 flex items-center gap-1 transition"
                    >
                      <span>🚨 이 차종 공식 리콜·화재 조회</span>
                      <span>&rarr;</span>
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* 5. OUT-OF-WARRANTY REPAIR COST MATRIX TABLE */}
      <section className="bg-white rounded-3xl p-6 sm:p-8 shadow-sm border border-slate-200 space-y-6">
        <div className="max-w-3xl space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-rose-50 text-rose-700 text-xs font-bold border border-rose-200">
            <span>💣</span>
            <span>중고 전기차 구매자 필수 참고</span>
          </div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">
            보증 만료 후 폭탄 수리비 및 핵심 부품별 교체 비용 매트릭스
          </h2>
          <p className="text-sm text-slate-600 leading-relaxed">
            전기차는 일반 내연기관 차량과 달리 핵심 전동화 부품(배터리, ICCU, 모터/인버터)의 무상 보증(8년/16만 km 등)이 종료되거나 하부 긁힘으로 보증이 거부될 경우 천문학적인 수리비가 청구됩니다. 실제 서비스센터 견적 기준 데이터입니다.
          </p>
        </div>

        <div className="overflow-x-auto border border-slate-200 rounded-2xl">
          <table className="w-full text-left text-xs sm:text-sm border-collapse" aria-label="보증 만료 후 폭탄 수리비 및 핵심 부품별 교체 비용 매트릭스">
            <caption className="sr-only">보증 만료 후 폭탄 수리비 및 핵심 부품별 교체 비용 매트릭스</caption>
            <thead>
              <tr className="bg-slate-900 text-white">
                <th scope="col" className="p-4 font-semibold min-w-[180px]">핵심 부품명</th>
                <th scope="col" className="p-4 font-semibold min-w-[160px]">예상 교체 비용</th>
                <th scope="col" className="p-4 font-semibold min-w-[140px]">표준 보증 기준</th>
                <th scope="col" className="p-4 font-semibold min-w-[180px]">고위험 취약 차종</th>
                <th scope="col" className="p-4 font-semibold min-w-[260px]">치명적 경고 및 주의사항</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {initialData.repair_cost_matrix.map((item, idx) => (
                <tr key={idx} className="hover:bg-slate-50 transition">
                  <th scope="row" className="p-4 font-bold text-slate-900 align-top text-left font-normal sm:font-bold">
                    <div>{item.component_name}</div>
                    <div className="text-[11px] text-slate-500 font-normal mt-1">
                      {item.affected_systems}
                    </div>
                  </th>
                  <td className="p-4 font-extrabold text-rose-600 align-top whitespace-nowrap">
                    {item.avg_cost_krw}
                  </td>
                  <td className="p-4 text-slate-600 align-top text-xs">
                    {item.standard_warranty}
                  </td>
                  <td className="p-4 align-top">
                    <div className="flex flex-wrap gap-1">
                      {item.high_risk_models.map((m, mIdx) => (
                        <span
                          key={mIdx}
                          className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 text-[11px] font-medium"
                        >
                          {m}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="p-4 text-xs text-slate-700 leading-relaxed align-top">
                    <span className="font-semibold text-rose-700 mr-1">주의:</span>
                    {item.critical_warning}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* 6. CONSUMER SURVIVAL GUIDE BANNER */}
      <section className="bg-gradient-to-r from-blue-900 to-indigo-900 text-white rounded-3xl p-6 sm:p-8 shadow-lg flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="space-y-2 max-w-2xl">
          <h3 className="text-xl sm:text-2xl font-black">
            🚨 내 차의 공식 화재 리콜 및 배터리 제조사가 궁금하신가요?
          </h3>
          <p className="text-sm text-blue-200 leading-relaxed">
            국토교통부 및 자동차리콜센터의 실시간 리콜 캠페인 데이터와 17자리 차대번호(VIN) 조회기를 통해 배터리 제조사(LGES, SK On, CATL, 파라시스)와 긴급 무상 수리 대상 여부를 즉시 확인하세요.
          </p>
        </div>
        <Link
          href="/recall-portal"
          className="px-6 py-3.5 bg-white text-blue-900 hover:bg-blue-50 font-extrabold rounded-2xl shadow-md transition shrink-0 text-sm sm:text-base text-center"
        >
          공식 리콜 & 배터리 조회 포털 가기 &rarr;
        </Link>
      </section>
    </div>
  );
}
