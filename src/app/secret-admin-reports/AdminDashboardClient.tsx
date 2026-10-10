"use client";

import React, { useState, useMemo, useDeferredValue } from 'react';
import type { DailyReportData, DefectReportItem } from '@/lib/getDailyReports';
import ClientTimestamp from '@/components/ClientTimestamp';

interface AdminDashboardClientProps {
  initialData: DailyReportData;
}

type SortOption = 'critical' | 'recent' | 'negativity';

interface CategoryTab {
  code: string;
  label: string;
}

const SEVERITY_WEIGHT: Record<string, number> = {
  CRITICAL: 3,
  WARNING: 2,
  CAUTION: 1,
  INFO: 0,
};

interface DefectReportWithTimestamp extends DefectReportItem {
  _timestamp: number;
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

export default function AdminDashboardClient({ initialData }: AdminDashboardClientProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const deferredSearchQuery = useDeferredValue(searchQuery);
  const [selectedCategory, setSelectedCategory] = useState('ALL');
  const [selectedSource, setSelectedSource] = useState('all');
  const [sortBy, setSortBy] = useState<SortOption>('critical');

  // Keyboard arrow navigation for Category Tabs (WAI-ARIA APG pattern)
  const handleCategoryKeyDown = (e: React.KeyboardEvent, currentIndex: number) => {
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
  };

  const reports = useMemo<DefectReportWithTimestamp[]>(() => {
    return (initialData?.reports || []).map((r) => {
      const rawDate = (r as unknown as { created_at?: string }).created_at || r.date;
      const parsed = rawDate ? new Date(rawDate).getTime() : 0;
      return {
        ...r,
        _timestamp: Number.isFinite(parsed) ? parsed : 0,
      };
    });
  }, [initialData?.reports]);

  const rawStats = initialData?.statistics;
  const statistics = {
    total_scraped: typeof rawStats?.total_scraped === 'number' ? rawStats.total_scraped : 0,
    total_filtered_defects: typeof rawStats?.total_filtered_defects === 'number' ? rawStats.total_filtered_defects : 0,
    avg_negativity_score: Number.isFinite(rawStats?.avg_negativity_score) ? (rawStats!.avg_negativity_score as number) : 0.85,
    critical_defect_count: typeof rawStats?.critical_defect_count === 'number' ? rawStats.critical_defect_count : 0,
    top_model: rawStats?.top_model || '미상',
    top_platform: rawStats?.top_platform || '전체',
  };

  const safeScore = Number.isFinite(statistics.avg_negativity_score)
    ? statistics.avg_negativity_score
    : 0.85;

  // Calculate dynamic category counts
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = { ALL: reports.length };
    CATEGORY_TABS.forEach((cat) => {
      if (cat.code !== 'ALL') {
        counts[cat.code] = reports.filter(
          (r) => r.defect_category === cat.code || r.defect_category_ko === cat.label
        ).length;
      }
    });
    return counts;
  }, [reports]);

  // Calculate dynamic source counts
  const sourceCounts = useMemo(() => {
    const counts: Record<string, number> = { all: reports.length };
    SOURCE_OPTIONS.forEach((s) => {
      if (s.id !== 'all') {
        counts[s.id] = reports.filter((r) => r.source.toLowerCase() === s.id).length;
      }
    });
    return counts;
  }, [reports]);

  // Filtered and sorted reports
  const filteredReports = useMemo(() => {
    const query = deferredSearchQuery.trim().toLowerCase();

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
          if (report.source.toLowerCase() !== selectedSource.toLowerCase()) {
            return false;
          }
        }

        // Search query filter
        if (query) {
          const matchTitle = (report.title || '').toLowerCase().includes(query);
          const matchSummary = (report.summary || '').toLowerCase().includes(query);
          const matchQuote = (report.verbatim_quote || '').toLowerCase().includes(query);
          const matchModel = (report.vehicle_model || '').toLowerCase().includes(query);
          const matchCategory = (report.defect_category_ko || '').toLowerCase().includes(query);
          const matchSlang = report.slang_tags?.some((tag) =>
            typeof tag === 'string' && tag.toLowerCase().includes(query)
          ) ?? false;

          if (
            !matchTitle &&
            !matchSummary &&
            !matchQuote &&
            !matchModel &&
            !matchCategory &&
            !matchSlang
          ) {
            return false;
          }
        }

        return true;
      })
      .sort((a, b) => {
        if (sortBy === 'critical') {
          const weightA = SEVERITY_WEIGHT[String(a.severity).toUpperCase()] || 0;
          const weightB = SEVERITY_WEIGHT[String(b.severity).toUpperCase()] || 0;
          if (weightB !== weightA) return weightB - weightA;
          return (b.sentiment_score || 0) - (a.sentiment_score || 0);
        }

        if (sortBy === 'recent') {
          return b._timestamp - a._timestamp;
        }

        if (sortBy === 'negativity') {
          return (b.sentiment_score || 0) - (a.sentiment_score || 0);
        }

        return 0;
      });
  }, [reports, selectedCategory, selectedSource, deferredSearchQuery, sortBy]);

  const handleResetFilters = () => {
    setSearchQuery('');
    setSelectedCategory('ALL');
    setSelectedSource('all');
    setSortBy('critical');
  };

  const handleTagClick = (tag: string) => {
    setSearchQuery(tag.replace(/^#/, ''));
  };

  // Helper for category badge styling
  const getCategoryBadgeClass = (category: string) => {
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
  };

  // Helper for severity badge styling
  const getSeverityBadge = (severity: string) => {
    const sev = String(severity).toUpperCase();
    if (sev === 'CRITICAL') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-600 text-white shadow-sm ring-1 ring-rose-500">
          <svg className="w-3 h-3 animate-pulse motion-reduce:animate-none" aria-hidden="true" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
              clipRule="evenodd"
            />
          </svg>
          CRITICAL
        </span>
      );
    }
    if (sev === 'WARNING') {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-400 text-slate-950 shadow-sm">
          WARNING
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-200 text-amber-950 border border-amber-300 shadow-sm">
        CAUTION
      </span>
    );
  };

  const getSourceBadge = (source: string, url: string) => {
    const isBobae = source.toLowerCase().includes('bobae');
    const badgeText = isBobae ? '보배드림' : '디시인사이드';
    const badgeColor = isBobae
      ? 'bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100'
      : 'bg-indigo-50 text-indigo-700 border-indigo-200 hover:bg-indigo-100';

    return (
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        title="원문 게시물 바로가기 (새 창에서 열림)"
        className={`inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-md border font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${badgeColor}`}
      >
        <span>{badgeText}</span>
        <span className="sr-only"> (새 창에서 열림)</span>
        <svg className="w-3 h-3 opacity-70" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
            d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
          />
        </svg>
      </a>
    );
  };

  return (
    <div className="space-y-6">
      {/* Confidential Header Bar */}
      <div className="bg-slate-900 border border-slate-800 text-slate-100 rounded-2xl p-6 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 -mt-4 -mr-4 w-40 h-40 bg-rose-600/10 rounded-full blur-3xl pointer-events-none" />
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30">
                <svg className="w-3 h-3" aria-hidden="true" fill="currentColor" viewBox="0 0 20 20">
                  <path
                    fillRule="evenodd"
                    d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z"
                    clipRule="evenodd"
                  />
                </svg>
                CONFIDENTIAL · INTERNAL ADMIN ONLY
              </span>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping motion-reduce:animate-none" aria-hidden="true" />
                파이프라인 정상 가동
              </span>
            </div>
            <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-white">
              Daily EV Defect Monitoring
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              국내 주요 커뮤니티(보배드림, 디시인사이드) 실시간 부정 피드백 및 날것의 결함 제보 수집 대시보드
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 text-xs text-slate-400">
            <div className="bg-slate-800/80 px-3 py-2 rounded-lg border border-slate-700">
              <span className="block text-slate-400 font-mono">PIPELINE VER</span>
              <span className="font-semibold text-slate-200">v{initialData?.pipeline_version || '1.0.0'}</span>
            </div>
            <div className="bg-slate-800/80 px-3 py-2 rounded-lg border border-slate-700">
              <span className="block text-slate-400 font-mono">LAST GENERATED</span>
              <ClientTimestamp
                isoString={initialData?.generated_at}
                className="font-semibold text-slate-200"
              />
            </div>
          </div>
        </div>
      </div>

      {/* 4 KPI Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Total Defects */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm hover:shadow-md transition">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-700 tracking-wider uppercase">
              전체 수집 결함
            </span>
            <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
              <svg className="w-5 h-5" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
            <span className="text-sm font-semibold text-slate-700">건 분석</span>
          </div>
          <div className="mt-2 text-xs text-slate-700 flex items-center justify-between">
            <span>스크랩 대상: {statistics.total_scraped}건</span>
            <span className="text-blue-600 font-medium">유효율 {Math.round((statistics.total_filtered_defects / Math.max(statistics.total_scraped || 0, 1)) * 100)}%</span>
          </div>
        </div>

        {/* Card 2: Critical Issues */}
        <div className="bg-white rounded-2xl p-5 border border-rose-200 bg-gradient-to-br from-white to-rose-50/30 shadow-sm hover:shadow-md transition">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-rose-700 tracking-wider uppercase">
              치명적 안전 결함
            </span>
            <div className="w-9 h-9 rounded-xl bg-rose-100 text-rose-800 flex items-center justify-center">
              <svg className="w-5 h-5" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
            <span className="text-3xl font-black text-rose-600">
              {statistics.critical_defect_count}
            </span>
            <span className="text-sm font-bold text-rose-700">건 위험</span>
          </div>
          <div className="mt-2 text-xs text-rose-700 font-medium">
            동력상실 · 화재위험 · 급제동 긴급 모니터링
          </div>
        </div>

        {/* Card 3: Avg Negativity Score */}
        <div className="bg-white rounded-2xl p-5 border border-amber-200 bg-gradient-to-br from-white to-amber-50/20 shadow-sm hover:shadow-md transition">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-amber-700 tracking-wider uppercase">
              평균 부정 감성 지수
            </span>
            <div className="w-9 h-9 rounded-xl bg-amber-100 text-amber-700 flex items-center justify-center">
              <svg className="w-5 h-5" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
            <span className="text-xs font-bold px-2 py-0.5 rounded bg-amber-100 text-amber-800">
              극도로 부정적
            </span>
          </div>
          <div
            role="progressbar"
            aria-valuenow={Math.round(safeScore * 100)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="평균 부정 감성 지수"
            aria-valuetext={`${Math.round(safeScore * 100)}%`}
            className="mt-2 w-full bg-slate-100 rounded-full h-2 overflow-hidden"
          >
            <div
              className="bg-amber-500 h-2 rounded-full transition-all duration-500"
              style={{ width: `${Math.round(safeScore * 100)}%` }}
            />
          </div>
        </div>

        {/* Card 4: Top Platform & Model */}
        <div className="bg-white rounded-2xl p-5 border border-indigo-200 bg-gradient-to-br from-white to-indigo-50/20 shadow-sm hover:shadow-md transition">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-indigo-700 tracking-wider uppercase">
              최다 제보 차종 / 플랫폼
            </span>
            <div className="w-9 h-9 rounded-xl bg-indigo-100 text-indigo-700 flex items-center justify-center">
              <svg className="w-5 h-5" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
            <div className="text-xs text-indigo-600 font-semibold mt-1 flex items-center gap-1">
              <span>출처:</span>
              <span>{statistics.top_platform}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar Section */}
      <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm space-y-4">
        {/* Search & Sort Row */}
        <div className="flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between">
          {/* Full-text search input */}
          <div className="relative flex-1">
            <label htmlFor="admin-defect-search-input" className="sr-only">전기차 결함 제보 및 은어 검색</label>
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-600">
              <svg className="w-4 h-4" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="전기차 결함 제보 및 은어 검색"
              placeholder="제목, 요약, 실차주 원문 코멘트, 차종, 은어(#ICCU폭탄 등) 실시간 검색..."
              className="w-full pl-10 pr-10 py-2.5 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus:bg-white transition"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-700 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
                title="검색어 지우기"
                aria-label="검색어 지우기"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>

          {/* Sort Selector */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-700 whitespace-nowrap">정렬:</span>
            <div className="inline-flex rounded-xl bg-slate-100 p-1 border border-slate-200 text-xs font-semibold">
              <button
                type="button"
                aria-pressed={sortBy === 'critical'}
                onClick={() => setSortBy('critical')}
                className={`px-3 py-1.5 rounded-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                  sortBy === 'critical'
                    ? 'bg-white text-rose-600 shadow-sm'
                    : 'text-slate-700 hover:text-slate-900'
                }`}
              >
                치명도순
              </button>
              <button
                type="button"
                aria-pressed={sortBy === 'recent'}
                onClick={() => setSortBy('recent')}
                className={`px-3 py-1.5 rounded-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                  sortBy === 'recent'
                    ? 'bg-white text-blue-600 shadow-sm'
                    : 'text-slate-700 hover:text-slate-900'
                }`}
              >
                최신수집순
              </button>
              <button
                type="button"
                aria-pressed={sortBy === 'negativity'}
                onClick={() => setSortBy('negativity')}
                className={`px-3 py-1.5 rounded-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                  sortBy === 'negativity'
                    ? 'bg-white text-amber-800 shadow-sm'
                    : 'text-slate-700 hover:text-slate-900'
                }`}
              >
                부정점수순
              </button>
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
                className={`px-3 py-2 rounded-xl font-semibold whitespace-nowrap transition flex items-center gap-1.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
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
          <div className="flex items-center gap-2">
            <span className="font-semibold text-slate-700">출처 플랫폼:</span>
            <div className="flex items-center gap-1.5">
              {SOURCE_OPTIONS.map((src) => {
                const isSelected = selectedSource === src.id;
                const count = sourceCounts[src.id] || 0;
                return (
                  <button
                    key={src.id}
                    type="button"
                    aria-pressed={isSelected}
                    onClick={() => setSelectedSource(src.id)}
                    className={`px-2.5 py-1 rounded-lg font-medium transition flex items-center gap-1 border focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
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
            <span className="text-slate-700 font-medium">
              결과 <strong className="text-slate-900 font-bold">{filteredReports.length}</strong>건
            </span>
            {(searchQuery || selectedCategory !== 'ALL' || selectedSource !== 'all') && (
              <button
                type="button"
                onClick={handleResetFilters}
                className="text-xs text-rose-600 hover:text-rose-700 font-semibold underline flex items-center gap-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-500 rounded px-1"
              >
                <svg className="w-3 h-3" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
      </div>

      {/* Reports List */}
      <div
        id="reports-tabpanel"
        role="tabpanel"
        aria-labelledby={`category-tab-${selectedCategory}`}
        tabIndex={0}
        className="focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-2xl"
      >
        {/* Screen Reader Accessible Summary Table for Defect Reports */}
        <div className="sr-only">
          <table aria-label="수집된 전기차 결함 제보 데이터 요약 표">
            <caption>
              카테고리: {CATEGORY_TABS.find((c) => c.code === selectedCategory)?.label || '전체'}, 총 {filteredReports.length}건의 결함 제보 목록
            </caption>
            <thead>
              <tr>
                <th scope="col">번호</th>
                <th scope="col">날짜</th>
                <th scope="col">차종</th>
                <th scope="col">분류</th>
                <th scope="col">심각도</th>
                <th scope="col">출처</th>
                <th scope="col">제목</th>
                <th scope="col">분석 요약</th>
                <th scope="col">부정 감성</th>
              </tr>
            </thead>
            <tbody>
              {filteredReports.map((report, idx) => (
                <tr key={`sr-report-${report.id}`}>
                  <th scope="row">{idx + 1}</th>
                  <td>{report.date}</td>
                  <td>{report.vehicle_model}</td>
                  <td>{report.defect_category_ko}</td>
                  <td>{report.severity}</td>
                  <td>{report.source}</td>
                  <td>
                    <a href={report.url} target="_blank" rel="noopener noreferrer" tabIndex={-1} aria-hidden="true">
                      {report.title}
                    </a>
                  </td>
                  <td>{report.summary}</td>
                  <td>{Math.round((report.sentiment_score || 0) * 100)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {filteredReports.length === 0 ? (
          <div className="bg-white rounded-2xl p-12 border border-slate-200 text-center space-y-3">
            <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-700 mx-auto flex items-center justify-center">
              <svg className="w-6 h-6" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
            className="mt-2 inline-flex items-center gap-1 px-4 py-2 rounded-xl text-xs font-semibold bg-slate-900 text-white hover:bg-slate-800 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >
            모든 필터 초기화
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <h2 className="sr-only">수집된 결함 제보 상세 목록</h2>
          {filteredReports.map((report: DefectReportItem) => (
            <div
              key={report.id}
              className="bg-white rounded-2xl p-5 md:p-6 border border-slate-200 shadow-sm hover:shadow-md transition space-y-4"
            >
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
                  {/* Community Source Badge with URL Link */}
                  {getSourceBadge(report.source, report.url)}

                  {/* Date */}
                  <span className="text-xs text-slate-700 font-mono">{report.date}</span>
                </div>
              </div>

              {/* Title */}
              <div>
                <h3 className="text-base md:text-lg font-extrabold text-slate-900 hover:text-blue-600 transition">
                  <a
                    href={report.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
                  >
                    {report.title}
                    <span className="sr-only"> (새 창에서 열림)</span>
                  </a>
                </h3>
              </div>

              {/* Defect Summary */}
              <div className="bg-slate-50 border-l-4 border-blue-500 px-3.5 py-2.5 rounded-r-lg text-sm text-slate-800 font-medium">
                <span className="text-blue-700 font-bold mr-1.5">[분석 요약]</span>
                {report.summary}
              </div>

              {/* Verbatim User Quote Block (날것 그대로의 유저 코멘트) */}
              <div className="bg-rose-50/50 border-l-4 border-rose-500 p-4 rounded-r-xl space-y-2">
                <div className="flex items-center justify-between text-xs font-bold text-rose-700 uppercase tracking-wider">
                  <span className="flex items-center gap-1.5">
                    <svg className="w-4 h-4 text-rose-500" aria-hidden="true" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M14.017 21v-7.391c0-5.704 3.731-9.57 8.983-10.609l.995 2.151c-2.432.917-3.995 3.638-3.995 5.849h4v10h-9.983zm-14.017 0v-7.391c0-5.704 3.748-9.57 9-10.609l.996 2.151c-2.433.917-3.996 3.638-3.996 5.849h3.983v10h-9.983z" />
                    </svg>
                    실제 커뮤니티 유저 날것의 코멘트 (Raw Verbatim Quote)
                  </span>
                  <span className="text-[11px] font-mono text-rose-700">원문 보존</span>
                </div>
                <p className="text-sm font-sans text-slate-900 leading-relaxed italic bg-white/80 p-3 rounded-lg border border-rose-200/60">
                  &ldquo;{report.verbatim_quote}&rdquo;
                </p>
              </div>

              {/* Slang Tags & Sentiment Meter Row */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2 border-t border-slate-100 text-xs">
                {/* Slang Tags */}
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-slate-700 font-semibold mr-1">감지된 은어/키워드:</span>
                  {(report.slang_tags || []).map((tag, idx) => (
                    <button
                      key={`${tag}-${idx}`}
                      type="button"
                      onClick={() => handleTagClick(tag)}
                      className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 font-mono hover:bg-rose-100 hover:text-rose-800 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                      title={`'${tag}' 태그로 검색`}
                    >
                      #{tag.replace(/^#/, '')}
                    </button>
                  ))}
                </div>

                {/* Sentiment Meter */}
                <div className="flex items-center gap-2 sm:self-end">
                  <span className="text-slate-700 font-medium">부정 감성 강도:</span>
                  <div
                    role="progressbar"
                    aria-valuenow={Math.round(report.sentiment_score * 100)}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={`리포트 ${report.id} 부정 감성 강도`}
                    aria-valuetext={`${Math.round(report.sentiment_score * 100)}%`}
                    className="w-24 bg-slate-200 rounded-full h-2 overflow-hidden"
                  >
                    <div
                      className="bg-rose-500 h-2 rounded-full"
                      style={{ width: `${Math.round(report.sentiment_score * 100)}%` }}
                    />
                  </div>
                  <span className="font-bold text-rose-700 font-mono">
                    {Math.round(report.sentiment_score * 100)}%
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      </div>
    </div>
  );
}
