'use client';

import React, { memo, useCallback } from 'react';
import { RegionEntry, CategoryMetrics } from '@/types/subsidy';
import SubsidyBadge, { getStatusLabel } from './SubsidyBadge';

export type CategoryType = 'passenger' | 'commercial' | 'bus';
export type SortOption = 'DEPLETION_DESC' | 'DEPLETION_ASC' | 'REMAINING_ASC' | 'LOCAL_SUBSIDY_DESC' | 'NAME_ASC';

export interface SubsidyTableViewProps {
  regions: RegionEntry[];
  selectedCategory: CategoryType;
  sortOption: SortOption;
  onSortChange: (newSort: SortOption) => void;
  expandedRegions: Record<string, boolean>;
  onToggleExpand: (regionId: string) => void;
  onSelectForCalc: (regionId: string) => void;
}

function getSortAria(
  col: 'NAME' | 'REMAINING' | 'DEPLETION' | 'LOCAL_SUBSIDY',
  sortOption: SortOption
): 'ascending' | 'descending' | 'none' {
  switch (col) {
    case 'NAME':
      return sortOption === 'NAME_ASC' ? 'ascending' : 'none';
    case 'REMAINING':
      return sortOption === 'REMAINING_ASC' ? 'ascending' : 'none';
    case 'DEPLETION':
      return sortOption === 'DEPLETION_DESC'
        ? 'descending'
        : sortOption === 'DEPLETION_ASC'
        ? 'ascending'
        : 'none';
    case 'LOCAL_SUBSIDY':
      return sortOption === 'LOCAL_SUBSIDY_DESC' ? 'descending' : 'none';
    default:
      return 'none';
  }
}

interface SubsidyTableRowProps {
  region: RegionEntry;
  selectedCategory: CategoryType;
  isExpanded: boolean;
  onToggleExpand: (regionId: string) => void;
  onSelectForCalc: (regionId: string) => void;
}

const SubsidyTableRow = memo(function SubsidyTableRow({
  region,
  selectedCategory,
  isExpanded,
  onToggleExpand,
  onSelectForCalc,
}: SubsidyTableRowProps) {
  const cat: CategoryMetrics = region?.categories?.[selectedCategory] ?? {
    status: 'HEALTHY',
    announced_units: 0,
    applied_units: 0,
    delivered_units: 0,
    remaining_units: 0,
    depletion_rate: 0,
    delivery_rate: 0,
    max_local_subsidy_krw: 0,
    max_total_subsidy_krw: 0,
  };
  const announced = Number.isFinite(cat.announced_units) ? Math.max(0, cat.announced_units) : 0;
  const applied = Number.isFinite(cat.applied_units) ? Math.max(0, cat.applied_units) : 0;
  const remaining = Number.isFinite(cat.remaining_units)
    ? Math.max(0, cat.remaining_units)
    : Math.max(0, announced - applied);
  const depletionRate = Number.isFinite(cat.depletion_rate)
    ? Math.max(0, cat.depletion_rate)
    : announced > 0
    ? (applied / announced) * 100
    : 0;

  const munis = Array.isArray(region?.municipalities) ? region.municipalities : [];
  const hasMunis = munis.length > 0;
  const regionName = region?.name_ko || '해당 지역';
  const regionId = region?.region_id || '';
  const categoryLabel = selectedCategory === 'passenger' ? '전기승용' : selectedCategory === 'commercial' ? '전기화물' : '전기승합';

  return (
    <React.Fragment>
      <tr className="hover:bg-slate-900/60 transition group">
        {/* Row Header with scope="row" */}
        <th
          scope="row"
          className="p-3.5 font-semibold text-white whitespace-nowrap sticky left-0 bg-slate-950 group-hover:bg-slate-900 z-10 border-r border-slate-800"
        >
          <div className="flex items-center gap-2">
            <span>{regionName}</span>
            {region?.iso_code && (
              <span className="text-[10px] text-slate-300 font-mono font-normal">
                {region.iso_code}
              </span>
            )}
            {region?.supplementary_budget_added && (
              <span className="text-[9px] px-1.5 py-0.2 bg-emerald-950 text-emerald-300 border border-emerald-500/40 rounded font-normal">
                추경
              </span>
            )}
          </div>
        </th>

        {/* Quota Numbers */}
        <td className="p-3.5 text-right font-mono text-slate-200">
          {announced.toLocaleString()}대
        </td>
        <td className="p-3.5 text-right font-mono text-blue-400">
          {applied.toLocaleString()}대
        </td>
        <td className="p-3.5 text-right font-mono font-bold text-emerald-400">
          {remaining.toLocaleString()}대
        </td>

        {/* Depletion Rate & Mini Progress Bar */}
        <td className="p-3.5 text-center min-w-[130px]">
          <div className="flex flex-col items-center gap-1">
            <span className="font-extrabold text-amber-400 font-mono">
              {depletionRate.toFixed(1)}%
            </span>
            <div
              role="progressbar"
              aria-valuenow={Math.min(100, Math.max(0, Math.round(depletionRate)))}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`${regionName} ${categoryLabel} 소진율`}
              aria-valuetext={`소진율 ${depletionRate.toFixed(1)}% (${getStatusLabel(cat.status || 'available')}), 잔여 ${remaining.toLocaleString()}대`}
              className="w-24 bg-slate-900 rounded-full h-2 overflow-hidden flex border border-slate-500"
            >
              <div
                style={{ width: `${Math.min(100, Math.max(0, depletionRate))}%` }}
                aria-hidden="true"
                className={`h-full ${
                  depletionRate >= 95
                    ? 'bg-rose-500'
                    : depletionRate >= 80
                    ? 'bg-orange-500'
                    : depletionRate >= 60
                    ? 'bg-amber-400'
                    : 'bg-emerald-400'
                }`}
              />
            </div>
          </div>
        </td>

        {/* Subsidies */}
        <td className="p-3.5 text-right font-mono font-medium text-slate-200">
          {((Number.isFinite(cat.max_local_subsidy_krw) ? Math.max(0, cat.max_local_subsidy_krw) : 0) / 10000).toLocaleString()}만 원
        </td>
        <td className="p-3.5 text-right font-mono font-bold text-amber-400">
          {((Number.isFinite(cat.max_total_subsidy_krw) ? Math.max(0, cat.max_total_subsidy_krw) : 0) / 10000).toLocaleString()}만 원
        </td>

        {/* Alert Status */}
        <td className="p-3.5 text-center whitespace-nowrap">
          <SubsidyBadge status={cat.status || 'available'} />
        </td>

        {/* Sub-Municipalities Collapsible Toggle */}
        <td className="p-3.5 text-center whitespace-nowrap">
          {hasMunis ? (
            <button
              type="button"
              onClick={() => onToggleExpand(regionId)}
              aria-expanded={isExpanded}
              aria-controls={'muni-details-' + regionId}
              aria-label={`${regionName} 세부 시·군·구 ${munis.length}개 현황 ${isExpanded ? '접기' : '보기'}`}
              className="px-2.5 py-1.5 min-h-[44px] sm:min-h-[36px] inline-flex items-center justify-center text-xs rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 font-medium border border-slate-700 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
            >
              {isExpanded ? '접기 ▲' : `${munis.length}개 시·군 ▼`}
            </button>
          ) : (
            <span className="text-slate-300 text-xs">-</span>
          )}
        </td>

        {/* Action */}
        <td className="p-3.5 text-center whitespace-nowrap">
          <button
            type="button"
            onClick={() => onSelectForCalc(regionId)}
            aria-label={`${regionName} 보조금으로 계산기 설정`}
            className="px-3 py-1.5 min-h-[44px] sm:min-h-[36px] inline-flex items-center justify-center text-xs font-semibold rounded-lg bg-blue-600 hover:bg-blue-500 text-white shadow transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
          >
            계산 ⚡
          </button>
        </td>
      </tr>

      {/* Sub-Municipalities Expandable Detail Row (Kept in DOM with hidden={!isExpanded} to fulfill W3C ARIA aria-controls contract) */}
      {hasMunis && (
        <tr hidden={!isExpanded} className={!isExpanded ? 'hidden' : ''}>
          <td colSpan={10} className="p-0 bg-slate-900/90 border-b border-slate-800">
            <div
              id={'muni-details-' + regionId}
              className="p-4 space-y-2"
            >
              <div className="flex items-center justify-between text-xs text-slate-300 font-bold mb-2">
                <span>📍 {regionName} 관할 세부 시·군·구별 보조금 및 소진율 내역</span>
                <span className="text-[11px] text-slate-300 font-normal">
                  총 {munis.length}개 행정구역
                </span>
              </div>

              <div
                tabIndex={0}
                role="region"
                aria-label={`${regionName} 세부 시·군·구 보조금 현황 스크롤 영역`}
                className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              >
                <table
                  className="w-full min-w-[500px] text-xs text-left border-collapse"
                  aria-label={`${regionName} 세부 시·군·구 보조금 현황표`}
                >
                  <caption className="sr-only">
                    {regionName} 관할 세부 시·군·구별 지방비 보조금 및 잔여 대수 표
                  </caption>
                  <thead>
                    <tr className="bg-slate-900 border-b border-slate-800 text-slate-300 text-[11px]">
                      <th scope="col" className="p-2 font-semibold">
                        시·군·구명
                      </th>
                      <th scope="col" className="p-2 font-semibold text-right">
                        지자체 지원금
                      </th>
                      <th scope="col" className="p-2 font-semibold text-right">
                        잔여 대수
                      </th>
                      <th scope="col" className="p-2 font-semibold text-center">
                        소진율
                      </th>
                      <th scope="col" className="p-2 font-semibold text-center">
                        상태
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/80">
                    {munis.map((muni) => {
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

                      return (
                        <tr key={muni.name_ko} className="hover:bg-slate-900/50">
                          <th scope="row" className="p-2 font-medium text-slate-200">
                            {muni.name_ko}
                          </th>
                          <td className="p-2 text-right font-mono text-slate-300">
                            {((Number.isFinite(muni.local_subsidy_krw) ? Math.max(0, muni.local_subsidy_krw) : 0) / 10000).toLocaleString()}만 원
                          </td>
                          <td className="p-2 text-right font-mono font-bold text-emerald-400">
                            {muniRemaining.toLocaleString()}대
                          </td>
                          <td className="p-2 text-center font-mono text-amber-300 font-semibold">
                            {muniDepletion.toFixed(1)}%
                          </td>
                          <td className="p-2 text-center">
                            <SubsidyBadge status={muni.status || 'available'} />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </td>
        </tr>
      )}
    </React.Fragment>
  );
});

export const SubsidyTableView = memo(function SubsidyTableView({
  regions = [],
  selectedCategory,
  sortOption,
  onSortChange,
  expandedRegions = {},
  onToggleExpand,
  onSelectForCalc,
}: SubsidyTableViewProps) {
  const handleSortName = useCallback(() => {
    onSortChange(sortOption === 'NAME_ASC' ? 'DEPLETION_DESC' : 'NAME_ASC');
  }, [sortOption, onSortChange]);

  const handleSortRemaining = useCallback(() => {
    onSortChange(sortOption === 'REMAINING_ASC' ? 'DEPLETION_DESC' : 'REMAINING_ASC');
  }, [sortOption, onSortChange]);

  const handleToggleDepletionSort = useCallback(() => {
    if (sortOption === 'DEPLETION_DESC') {
      onSortChange('DEPLETION_ASC');
    } else {
      onSortChange('DEPLETION_DESC');
    }
  }, [sortOption, onSortChange]);

  const handleSortLocalSubsidy = useCallback(() => {
    onSortChange(sortOption === 'LOCAL_SUBSIDY_DESC' ? 'DEPLETION_DESC' : 'LOCAL_SUBSIDY_DESC');
  }, [sortOption, onSortChange]);

  return (
    <div
      tabIndex={0}
      role="region"
      aria-label="지자체별 보조금 소진율 비교 표 스크롤 영역"
      className="overflow-x-auto rounded-2xl border border-slate-800 bg-slate-950 shadow-2xl focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
    >
      <table
        className="w-full min-w-[840px] text-left text-xs sm:text-sm border-collapse"
        aria-label="전국 지자체별 전기차 보조금 실시간 소진율 및 잔여 쿼터 비교 표"
      >
        <caption className="sr-only">
          전국 17개 지자체별 전기차 보조금 실시간 소진율 및 잔여 쿼터 비교 표
        </caption>
        <thead>
          <tr className="bg-slate-900 border-b border-slate-800 text-slate-300">
            <th
              scope="col"
              aria-sort={getSortAria('NAME', sortOption)}
              className="p-3.5 font-bold whitespace-nowrap sticky left-0 bg-slate-900 z-10"
            >
              <button
                type="button"
                onClick={handleSortName}
                aria-label={`지역명 ${sortOption === 'NAME_ASC' ? '내림차순 정렬 전환' : '오름차순 정렬 전환'}`}
                className="min-h-[44px] sm:min-h-[36px] inline-flex items-center gap-1.5 hover:text-white transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 rounded px-1.5"
              >
                <span>지역명</span>
                <span aria-hidden="true" className="text-slate-300 text-xs">
                  {sortOption === 'NAME_ASC' ? '▲' : '↕'}
                </span>
              </button>
            </th>
            <th scope="col" className="p-3.5 font-bold whitespace-nowrap text-right">
              공고 대수
            </th>
            <th scope="col" className="p-3.5 font-bold whitespace-nowrap text-right">
              접수 대수
            </th>
            <th
              scope="col"
              aria-sort={getSortAria('REMAINING', sortOption)}
              className="p-3.5 font-bold whitespace-nowrap text-right"
            >
              <button
                type="button"
                onClick={handleSortRemaining}
                aria-label={`잔여 대수 ${sortOption === 'REMAINING_ASC' ? '내림차순 정렬 전환' : '오름차순 정렬 전환'}`}
                className="min-h-[44px] sm:min-h-[36px] inline-flex items-center gap-1.5 hover:text-white transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 rounded px-1.5 ml-auto"
              >
                <span>잔여 대수</span>
                <span aria-hidden="true" className="text-slate-300 text-xs">
                  {sortOption === 'REMAINING_ASC' ? '▲' : '↕'}
                </span>
              </button>
            </th>
            <th
              scope="col"
              aria-sort={getSortAria('DEPLETION', sortOption)}
              className="p-3.5 font-bold whitespace-nowrap text-center min-w-[130px]"
            >
              <button
                type="button"
                onClick={handleToggleDepletionSort}
                aria-label={`소진율 ${sortOption === 'DEPLETION_DESC' ? '오름차순 정렬 전환' : '내림차순 정렬 전환'}`}
                className="min-h-[44px] sm:min-h-[36px] inline-flex items-center gap-1.5 hover:text-white transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 rounded px-1.5"
              >
                <span>소진율</span>
                <span aria-hidden="true" className="text-slate-300 text-xs">
                  {sortOption === 'DEPLETION_DESC' ? '▼' : sortOption === 'DEPLETION_ASC' ? '▲' : '↕'}
                </span>
              </button>
            </th>
            <th
              scope="col"
              aria-sort={getSortAria('LOCAL_SUBSIDY', sortOption)}
              className="p-3.5 font-bold whitespace-nowrap text-right"
            >
              <button
                type="button"
                onClick={handleSortLocalSubsidy}
                aria-label={`지방비 지원금 ${sortOption === 'LOCAL_SUBSIDY_DESC' ? '기본 정렬로 전환' : '내림차순 정렬 전환'}`}
                className="min-h-[44px] sm:min-h-[36px] inline-flex items-center gap-1.5 hover:text-white transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 rounded px-1.5 ml-auto"
              >
                <span>지방비 최대</span>
                <span aria-hidden="true" className="text-slate-300 text-xs">
                  {sortOption === 'LOCAL_SUBSIDY_DESC' ? '▼' : '↕'}
                </span>
              </button>
            </th>
            <th scope="col" className="p-3.5 font-bold whitespace-nowrap text-right">
              국비+지방비 합산
            </th>
            <th scope="col" className="p-3.5 font-bold whitespace-nowrap text-center">
              경보 상태
            </th>
            <th scope="col" className="p-3.5 font-bold whitespace-nowrap text-center">
              세부 시·군·구
            </th>
            <th scope="col" className="p-3.5 font-bold whitespace-nowrap text-center">
              체감가 계산
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {(regions || []).map((region) => (
            <SubsidyTableRow
              key={region.region_id}
              region={region}
              selectedCategory={selectedCategory}
              isExpanded={!!expandedRegions[region.region_id]}
              onToggleExpand={onToggleExpand}
              onSelectForCalc={onSelectForCalc}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
});

export default SubsidyTableView;
