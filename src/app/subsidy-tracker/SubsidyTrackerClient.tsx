'use client';

import React, { useState, useMemo, useRef, useEffect, useDeferredValue, useCallback } from 'react';
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
import { calculateNetSubsidy } from '@/lib/getSubsidyData';
import ClientTimestamp from '@/components/ClientTimestamp';

interface SubsidyTrackerClientProps {
  initialData: EVSubsidyDataset;
}

type CategoryType = 'passenger' | 'commercial' | 'bus';
type ZoneFilter = 'ALL' | 'CAPITAL' | 'YEONGNAM' | 'HONAM' | 'CHUNGCHEONG' | 'GANGWON_JEJU';
type SortOption = 'DEPLETION_DESC' | 'DEPLETION_ASC' | 'REMAINING_ASC' | 'LOCAL_SUBSIDY_DESC' | 'NAME_ASC';

const CATEGORY_TABS: { id: CategoryType; label: string; icon: string }[] = [
  { id: 'passenger', label: '전기승용 (승용차)', icon: '🚗' },
  { id: 'commercial', label: '전기화물 (소형/특장)', icon: '🚚' },
  { id: 'bus', label: '전기승합 (버스)', icon: '🚌' },
];

// Hoisted brand regexes to module scope to avoid re-allocating RegExp objects on every render
export const BRAND_PREFIX_REGEX = /^(현대|기아|테슬라|KGM|비야디|BYD)\s+/;

// Pure Helper: Badge styling with opaque solid backgrounds for compliant contrast
export const getBadgeStyle = (status: AlertSeverity | string): string => {
  switch (status) {
    case 'HEALTHY':
    case 'available':
      return 'bg-emerald-950 text-emerald-300 border-emerald-500/40';
    case 'CAUTION':
      return 'bg-amber-950 text-amber-300 border-amber-500/40';
    case 'WARNING':
      return 'bg-orange-950 text-orange-300 border-orange-500/40';
    case 'CRITICAL':
      return 'bg-rose-950 text-rose-300 border-rose-500/40 animate-pulse motion-reduce:animate-none';
    case 'DEPLETED':
      return 'bg-slate-900 text-slate-300 border-slate-700';
    default:
      return 'bg-emerald-950 text-emerald-300 border-emerald-500/40';
  }
};

// Pure Helper: Status badge labels
export const getStatusLabel = (status: AlertSeverity | string): string => {
  switch (status) {
    case 'HEALTHY':
    case 'available':
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
  const cat: CategoryMetrics = region?.categories?.[selectedCategory] ?? {
    status: 'available',
    announced_units: 0,
    delivered_units: 0,
    depletion_rate: 0,
    remaining_units: 0,
    applied_units: 0,
    max_local_subsidy_krw: 0,
    max_total_subsidy_krw: 0,
  };

  const safeAnnounced = Number.isFinite(cat?.announced_units) && cat.announced_units > 0 ? cat.announced_units : 1;
  const safeDelivered = Number.isFinite(cat?.delivered_units) ? cat.delivered_units : 0;
  const safeDepletion = Number.isFinite(cat?.depletion_rate) ? cat.depletion_rate : 0;
  const safeRemaining = Number.isFinite(cat?.remaining_units) ? cat.remaining_units : 0;
  const safeApplied = Number.isFinite(cat?.applied_units) ? cat.applied_units : 0;

  const rawDeliveredPct = Math.round((safeDelivered / safeAnnounced) * 100);
  const deliveredPct = Number.isFinite(rawDeliveredPct) ? Math.min(100, Math.max(0, rawDeliveredPct)) : 0;
  const rawPendingPct = safeDepletion - deliveredPct;
  const pendingPct = Number.isFinite(rawPendingPct) ? Math.max(0, Math.min(100 - deliveredPct, rawPendingPct)) : 0;
  const remainingPct = Math.max(0, 100 - (deliveredPct + pendingPct));

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg hover:border-slate-700 transition flex flex-col justify-between">
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
          <span className={`px-2.5 py-1 rounded-lg text-xs font-bold border ${getBadgeStyle(cat?.status || 'available')}`}>
            {getStatusLabel(cat?.status || 'available')}
          </span>
        </div>

        {/* Progress Bar (Dual Layer: Delivered vs Pending vs Remaining) */}
        <div className="space-y-1.5 pt-1">
          <div className="flex justify-between items-center text-xs">
            <span className="font-semibold text-slate-300">
              소진율 <strong className="text-amber-400 text-sm">{safeDepletion.toFixed(1)}%</strong>
            </span>
            <span className="text-slate-400 text-[11px]">
              잔여 <strong className="text-emerald-400 font-bold">{safeRemaining.toLocaleString()}</strong> / {safeAnnounced.toLocaleString()}대
            </span>
          </div>

          <div
            role="progressbar"
            aria-valuenow={Math.min(100, Math.round(safeDepletion))}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`${region.name_ko} ${selectedCategory === 'passenger' ? '전기승용' : selectedCategory === 'commercial' ? '전기화물' : '전기승합'} 보조금 소진율`}
            aria-valuetext={`소진율 ${safeDepletion.toFixed(1)}% (${getStatusLabel(cat?.status || 'available')}), 잔여 ${safeRemaining.toLocaleString()}대`}
            className="w-full bg-slate-950 rounded-full h-3.5 overflow-hidden flex relative border border-slate-800"
          >
            {/* Layer 1: Confirmed Delivered */}
            <div
              style={{ width: `${deliveredPct}%` }}
              className="bg-blue-500 h-full transition-all duration-500"
              title={`출고 완료: ${safeDelivered.toLocaleString()}대 (${deliveredPct}%)`}
            />
            {/* Layer 2: Pending Applications */}
            <div
              style={{ width: `${pendingPct}%` }}
              className="bg-amber-500 h-full transition-all duration-500"
              title={`접수 대기: ${Math.max(0, safeApplied - safeDelivered).toLocaleString()}대 (${pendingPct.toFixed(1)}%)`}
            />
            {/* Layer 3: Remaining (slate track) */}
            <div
              style={{ width: `${remainingPct}%` }}
              className="bg-slate-800 h-full"
              title={`잔여: ${safeRemaining.toLocaleString()}대 (${remainingPct.toFixed(1)}%)`}
            />
          </div>

          <div className="flex justify-between text-[10px] text-slate-400">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-blue-500 inline-block" aria-hidden="true" />
              출고 {safeDelivered.toLocaleString()}대
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-amber-500 inline-block" aria-hidden="true" />
              심사중 {Math.max(0, safeApplied - safeDelivered).toLocaleString()}대
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-slate-700 inline-block" aria-hidden="true" />
              잔여 {safeRemaining.toLocaleString()}대
            </span>
          </div>
        </div>

        {/* Financial Subsidy Limits - Solid Opaque Backgrounds for Contrast */}
        <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-800 text-xs">
          <div className="bg-slate-950 p-2.5 rounded-xl border border-slate-800">
            <div className="text-[11px] text-slate-400">지자체 최대 지원금</div>
            <div className="text-sm font-bold text-slate-200 mt-0.5">
              {((Number.isFinite(cat?.max_local_subsidy_krw) ? cat.max_local_subsidy_krw : 0) / 10000).toLocaleString()}만 원
            </div>
          </div>
          <div className="bg-slate-950 p-2.5 rounded-xl border border-slate-800">
            <div className="text-[11px] text-slate-400">국비+지방비 합산 최대</div>
            <div className="text-sm font-bold text-amber-400 mt-0.5">
              {((Number.isFinite(cat?.max_total_subsidy_krw) ? cat.max_total_subsidy_krw : 0) / 10000).toLocaleString()}만 원
            </div>
          </div>
        </div>

        {/* Eligibility & Notes */}
        <div className="flex flex-wrap gap-1.5 pt-1 text-[11px]">
          <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
            거주 요건: {region.residency_requirement_days}일 이상
          </span>
          {region.supplementary_budget_added && (
            <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-500/40 font-semibold">
              추경 완료
            </span>
          )}
        </div>

        {region.notes && (
          <p className="text-xs text-slate-400 leading-relaxed bg-slate-950 p-2 rounded-lg border border-slate-800">
            ℹ️ {region.notes}
          </p>
        )}

        {/* Municipalities Collapsible (if province has sub-cities) */}
        {region.municipalities && region.municipalities.length > 0 && (
          <div className="pt-2">
            <button
              type="button"
              onClick={() => toggleRegionExpand(region.region_id)}
              aria-expanded={isExpanded}
              aria-controls={'muni-details-' + region.region_id}
              className="w-full py-1.5 px-3 rounded-lg bg-slate-950 hover:bg-slate-800 text-slate-300 text-xs font-medium flex items-center justify-between transition border border-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
            >
              <span>세부 시·군·구 {region.municipalities.length}개 현황 보기</span>
              <span>{isExpanded ? '▲ 접기' : '▼ 펼치기'}</span>
            </button>

            {isExpanded && (
              <div
                id={'muni-details-' + region.region_id}
                tabIndex={0}
                aria-label={`${region.name_ko} 세부 시·군·구 보조금 현황 목록`}
                className="mt-2 space-y-1.5 max-h-48 overflow-y-auto pr-1 text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-lg"
              >
                {(region.municipalities || []).map((muni) => (
                  <div
                    key={muni.name_ko}
                    className="p-2 rounded bg-slate-950 border border-slate-800 flex items-center justify-between text-[11px]"
                  >
                    <div>
                      <span className="font-semibold text-slate-200">{muni.name_ko}</span>
                      <span className="text-slate-400 ml-2">
                        {((Number.isFinite(muni.local_subsidy_krw) ? muni.local_subsidy_krw : 0) / 10000).toLocaleString()}만 원
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-slate-400">잔여 {muni.remaining_units ?? 0}대</span>
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${getBadgeStyle(muni.status || 'available')}`}>
                        {getStatusLabel(muni.status || 'available')} {(Number.isFinite(muni.depletion_rate) ? muni.depletion_rate : 0).toFixed(1)}%
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
          onClick={() => onSelectForCalc(region.region_id)}
          className="w-full py-2.5 px-4 rounded-xl bg-blue-600/90 hover:bg-blue-600 text-white font-semibold text-xs transition flex items-center justify-center gap-1.5 shadow focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
        >
          <span>⚡</span> 이 지역({region.name_ko})으로 실구매가 계산
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

  const activeModel = useMemo(() => {
    return models.find((m) => m.model_id === selectedModelId) || models[0];
  }, [models, selectedModelId]);

  const activeRegionForCalc = useMemo(() => {
    return regions.find((r) => r.region_id === selectedRegionId) || regions[0];
  }, [regions, selectedRegionId]);

  const calculationResult = useMemo(() => {
    let customMsrpNum: number | undefined = undefined;
    if (isCustomMsrp) {
      const cleaned = (customMsrpInput || '').replace(/[^0-9]/g, '');
      const parsed = cleaned ? parseInt(cleaned, 10) : NaN;
      customMsrpNum = Number.isFinite(parsed) && parsed > 0 ? parsed : (activeModel?.base_price_krw ?? 0);
    }
    return calculateNetSubsidy(selectedModelId, selectedRegionId, customMsrpNum, calcOptions);
  }, [selectedModelId, selectedRegionId, isCustomMsrp, customMsrpInput, activeModel?.base_price_krw, calcOptions]);

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
              value={selectedModelId}
              onChange={(e) => onSelectModelId(e.target.value)}
              className="w-full py-3 px-3.5 rounded-xl bg-slate-950 border border-slate-700 text-white text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 cursor-pointer font-medium"
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
                  aria-pressed={selectedModelId === m.model_id}
                  onClick={() => onSelectModelId(m.model_id)}
                  className={`px-2.5 py-1 rounded-lg text-xs font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 ${
                    selectedModelId === m.model_id
                      ? 'bg-blue-600 text-white'
                      : 'bg-slate-950 text-slate-300 hover:bg-slate-800 border border-slate-800'
                  }`}
                >
                  {m.name_ko.replace(BRAND_PREFIX_REGEX, '')}
                </button>
              ))}
            </div>

            {/* Selected Model Spec Card - Solid Opaque Background */}
            {activeModel && (
              <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl flex flex-wrap items-center justify-between text-xs text-slate-300 gap-2">
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
              onChange={(e) => onSelectRegionId(e.target.value)}
              aria-describedby="region-residency-note"
              className="w-full py-3 px-3.5 rounded-xl bg-slate-950 border border-slate-700 text-white text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 cursor-pointer font-medium"
            >
              {regions.map((reg) => (
                <option key={reg.region_id} value={reg.region_id}>
                  {reg.name_ko} ({(reg.categories?.passenger?.depletion_rate ?? 0).toFixed(1)}% 소진, {getStatusLabel(reg.categories?.passenger?.status || 'available')})
                </option>
              ))}
            </select>
            <p id="region-residency-note" className="text-xs text-amber-300 flex items-center gap-1.5 pt-0.5">
              <span aria-hidden="true">ℹ️</span> 해당 지자체 최소 <strong>{activeRegionForCalc?.residency_requirement_days ?? 30}일 이상</strong> 연속 거주 요건 필요
            </p>
          </div>

          {/* 3. Custom MSRP Option */}
          <div className="space-y-3 p-4 bg-slate-950 border border-slate-800 rounded-2xl">
            <div className="flex items-center justify-between">
              <label htmlFor="custom-msrp-toggle-checkbox" className="flex items-center gap-2 cursor-pointer select-none text-xs font-bold text-slate-300 uppercase tracking-wider">
                <input
                  id="custom-msrp-toggle-checkbox"
                  type="checkbox"
                  checked={isCustomMsrp}
                  onChange={(e) => {
                    setIsCustomMsrp(e.target.checked);
                    if (e.target.checked && !customMsrpInput && activeModel) {
                      setCustomMsrpInput(activeModel.base_price_krw.toString());
                    }
                  }}
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
                    onChange={(e) => setCustomMsrpInput(e.target.value.replace(/[^0-9]/g, ''))}
                    placeholder="원 단위 출고가 입력 (예: 54,900,000)"
                    className="w-full py-2.5 px-3.5 rounded-xl bg-slate-900 border border-slate-700 text-white text-sm font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 pr-12"
                  />
                  <span className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 text-xs font-semibold">
                    원
                  </span>
                </div>
                <div className="flex gap-2 text-[11px]">
                  <button
                    type="button"
                    onClick={() => setCustomMsrpInput('54000000')}
                    className="px-2.5 py-1 text-xs rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
                  >
                    5,400만 (100% 구간)
                  </button>
                  <button
                    type="button"
                    onClick={() => setCustomMsrpInput('62000000')}
                    className="px-2.5 py-1 text-xs rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
                  >
                    6,200만 (50% 감액)
                  </button>
                  <button
                    type="button"
                    onClick={() => setCustomMsrpInput('86000000')}
                    className="px-2.5 py-1 text-xs rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
                  >
                    8,600만 (보조금 0원)
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
              <label className="flex items-center gap-2 p-2 rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={calcOptions.isYouthFirstTimeBuyer}
                  onChange={(e) => setCalcOptions((prev) => ({ ...prev, isYouthFirstTimeBuyer: e.target.checked }))}
                  className="w-4 h-4 rounded bg-slate-800 border-slate-700 text-amber-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
                />
                <span>청년 생애 최초 구매 (+20% 국비)</span>
              </label>

              <label className="flex items-center gap-2 p-2 rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={calcOptions.isSmallBusinessOrTaxi}
                  onChange={(e) => setCalcOptions((prev) => ({ ...prev, isSmallBusinessOrTaxi: e.target.checked }))}
                  className="w-4 h-4 rounded bg-slate-800 border-slate-700 text-amber-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
                />
                <span>소상공인 / 영업용 택시 (+30% 국비)</span>
              </label>

              <label className="flex items-center gap-2 p-2 rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={calcOptions.isMultiChildFamily}
                  onChange={(e) => setCalcOptions((prev) => ({ ...prev, isMultiChildFamily: e.target.checked }))}
                  className="w-4 h-4 rounded bg-slate-800 border-slate-700 text-amber-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
                />
                <span>다자녀 가구 (+10% 국비)</span>
              </label>

              <label className="flex items-center gap-2 p-2 rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={calcOptions.isOldDieselScrappage}
                  onChange={(e) => setCalcOptions((prev) => ({ ...prev, isOldDieselScrappage: e.target.checked }))}
                  className="w-4 h-4 rounded bg-slate-800 border-slate-700 text-amber-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
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
              등록 지역: {calculationResult.regionName} {activeRegionForCalc?.name_en ? `(${activeRegionForCalc.name_en})` : ''}
            </div>
          </div>

          {/* Price Breakdown Matrix */}
          <div className="space-y-2.5 text-sm border-t border-slate-800 pt-4">
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
          <div className="bg-gradient-to-r from-emerald-950 to-slate-900 border border-emerald-500/40 rounded-2xl p-5 text-center space-y-1">
            <span className="text-xs text-emerald-300 font-semibold uppercase tracking-wider">
              최종 실구매 체감가 (소비자 부담액)
            </span>
            <div className="text-3xl sm:text-4xl font-black text-emerald-400 tracking-tight">
              {Math.round(calculationResult.netPurchasePriceKrw / 10000).toLocaleString()}
              <span className="text-xl sm:text-2xl font-bold ml-1 text-emerald-200">만 원</span>
            </div>
            <div className="text-[11px] text-emerald-300">
              (정확한 금액: {calculationResult.netPurchasePriceKrw.toLocaleString()} 원)
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
            <div className="text-[11px] text-slate-400 pt-1 border-t border-slate-800 flex flex-wrap justify-between gap-1">
              <span>거주 요건: 최소 {calculationResult.residencyRequirementDays}일 이상</span>
              <span>2년 의무 운행 기간 (관외 이전 시 환수)</span>
            </div>
          </div>
        </div>
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
  const [supplementaryOnly, setSupplementaryOnly] = useState(false);
  const [expandedRegions, setExpandedRegions] = useState<Record<string, boolean>>({});

  // Performance Optimization: Non-blocking search typing via useDeferredValue
  const deferredSearchQuery = useDeferredValue(searchQuery);

  // Calculator State & Ref
  const calculatorRef = useRef<HTMLDivElement>(null);
  const [selectedModelId, setSelectedModelId] = useState<string>(
    urlModel || initialData?.popular_models_matrix?.[0]?.model_id || 'ioniq-5-2026'
  );
  const [selectedRegionId, setSelectedRegionId] = useState<string>(
    urlRegion || initialData?.regions?.[0]?.region_id || 'KR-11'
  );

  // Sync selectedModelId and selectedRegionId on query param navigation
  useEffect(() => {
    if (urlModel) {
      setSelectedModelId(urlModel);
    }
    if (urlRegion) {
      setSelectedRegionId(urlRegion);
    }
  }, [urlModel, urlRegion]);

  const regions = useMemo(() => (Array.isArray(initialData?.regions) ? initialData.regions : []), [initialData?.regions]);
  const models = useMemo(() => (Array.isArray(initialData?.popular_models_matrix) ? initialData.popular_models_matrix : []), [initialData?.popular_models_matrix]);

  const fallbackSummary = {
    total_announced_units: 0,
    total_applied_units: 0,
    total_disbursed_units: 0,
    total_remaining_units: 0,
    total_delivered_units: 0,
    nationwide_depletion_rate: 0,
    total_budget_billion_krw: 0,
    alert_region_counts: {
      healthy: 0,
      caution: 0,
      warning: 0,
      critical: 0,
      depleted: 0,
    },
  };
  const summary = initialData?.nationwide_summary || fallbackSummary;

  const fallbackThresholds: Record<AlertSeverity, AlertThresholdConfig> = {
    HEALTHY: {
      min_percent: 0.0,
      max_percent: 59.9,
      label_ko: '원활 (신청 여유)',
      severity: 'HEALTHY',
      color_hex: '#10B981',
      badge_class: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
      recommended_action: '보조금 잔여량이 충분하여 신청 접수 후 통상 1~2주 내 교부 결정됩니다.',
    },
    CAUTION: {
      min_percent: 60.0,
      max_percent: 79.9,
      label_ko: '주의 (소진 가속)',
      severity: 'CAUTION',
      color_hex: '#F59E0B',
      badge_class: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
      recommended_action: '출고 예정 시기가 1~2개월 이내인 경우 조속한 서류 접수를 권장합니다.',
    },
    WARNING: {
      min_percent: 80.0,
      max_percent: 94.9,
      label_ko: '경고 (마감 임박)',
      severity: 'WARNING',
      color_hex: '#F97316',
      badge_class: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
      recommended_action: '잔여 예산 소진이 임박했습니다. 즉시 출고 가능한 실재고 매칭이 필요합니다.',
    },
    CRITICAL: {
      min_percent: 95.0,
      max_percent: 99.9,
      label_ko: '위험 (잔여 극소)',
      severity: 'CRITICAL',
      color_hex: '#EF4444',
      badge_class: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
      recommended_action: '선착순 마감 직전입니다. 담당 지자체 문의 및 추경 예산 편성 여부를 확인하세요.',
    },
    DEPLETED: {
      min_percent: 100.0,
      max_percent: 999.0,
      label_ko: '마감 (접수 종료)',
      severity: 'DEPLETED',
      color_hex: '#6B7280',
      badge_class: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
      recommended_action: '2026년 공고 예산이 전액 소진되었습니다. 취소분 대기 접수 또는 차년도 사업을 준비하세요.',
    },
  };
  const thresholds = initialData?.alert_thresholds || fallbackThresholds;

  // Optimized Filtered & Sorted Regions (dependent on deferredSearchQuery to keep typing responsive)
  const filteredRegions = useMemo(() => {
    const trimmedQuery = deferredSearchQuery.trim().toLowerCase();

    return regions
      .filter((region) => {
        // Category Metrics
        const catMetrics: CategoryMetrics | undefined = region.categories?.[selectedCategory];
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
        if (trimmedQuery) {
          const matchRegion =
            region.name_ko.toLowerCase().includes(trimmedQuery) ||
            region.name_en.toLowerCase().includes(trimmedQuery) ||
            region.iso_code.toLowerCase().includes(trimmedQuery);

          const matchMuni =
            region.municipalities?.some((m) => m.name_ko.toLowerCase().includes(trimmedQuery)) ?? false;

          if (!matchRegion && !matchMuni) return false;
        }

        return true;
      })
      .sort((a, b) => {
        const catA = a.categories?.[selectedCategory];
        const catB = b.categories?.[selectedCategory];

        switch (sortOption) {
          case 'DEPLETION_DESC':
            return (catB?.depletion_rate ?? 0) - (catA?.depletion_rate ?? 0);
          case 'DEPLETION_ASC':
            return (catA?.depletion_rate ?? 0) - (catB?.depletion_rate ?? 0);
          case 'REMAINING_ASC':
            return (catA?.remaining_units ?? 0) - (catB?.remaining_units ?? 0);
          case 'LOCAL_SUBSIDY_DESC':
            return (catB?.max_local_subsidy_krw ?? 0) - (catA?.max_local_subsidy_krw ?? 0);
          case 'NAME_ASC':
            return (a.name_ko || '').localeCompare(b.name_ko || '', 'ko');
          default:
            return 0;
        }
      });
  }, [regions, selectedCategory, zoneFilter, alertFilter, supplementaryOnly, deferredSearchQuery, sortOption]);

  // Critical regions (for emergency ticker)
  const criticalRegions = useMemo(() => {
    return regions.filter((r) => {
      const p = r.categories?.passenger;
      if (!p) return false;
      return (
        p.status === 'CRITICAL' ||
        p.status === 'DEPLETED' ||
        (p.depletion_rate ?? 0) >= 95.0
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

    if (nextIndex >= 0) {
      setSelectedCategory(CATEGORY_TABS[nextIndex].id);
      const targetBtn = document.getElementById(`tab-category-${CATEGORY_TABS[nextIndex].id}`);
      if (targetBtn) {
        targetBtn.focus();
      }
    }
  };

  return (
    <div className="space-y-10 py-6 text-slate-100 max-w-6xl mx-auto">
      {/* Skip Navigation for Keyboard Accessibility */}
      <a
        href="#subsidy-calculator"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2.5 focus:bg-amber-400 focus:text-slate-950 focus:font-bold focus:rounded-xl focus:shadow-2xl focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 transition"
      >
        보조금 계산기로 건너뛰기
      </a>

      {/* 1. Header Banner & Live Tracker Status - Solid Opaque Background */}
      <section aria-labelledby="tracker-heading" className="bg-slate-900 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-gradient-to-bl from-amber-500/10 via-blue-500/5 to-transparent rounded-full blur-3xl pointer-events-none" />

        <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-950 border border-emerald-500/40 text-emerald-300 text-xs font-semibold tracking-wide">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping motion-reduce:animate-none inline-block" aria-hidden="true" />
              실시간 스케줄러 동기화 완료
            </span>
            <span className="text-xs text-slate-400">
              기준: 2026년 환경부 무공해차 통합누리집 (ev.or.kr)
            </span>
          </div>
          <span className="text-xs text-slate-400">
            데이터 갱신 시각:{' '}
            <ClientTimestamp
              isoString={initialData?.metadata?.generated_at}
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

        {/* Live Nationwide Stat Cards - Solid Opaque Backgrounds */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 sm:gap-4 mt-8 pt-6 border-t border-slate-800">
          <div className="bg-slate-950 border border-slate-800 rounded-2xl p-4 flex flex-col justify-between">
            <div className="text-xs font-medium text-slate-400">전국 평균 소진율</div>
            <div className="text-2xl sm:text-3xl font-extrabold text-amber-400 mt-1">
              {(summary.nationwide_depletion_rate ?? 0).toFixed(1)}%
            </div>
            <div className="text-[11px] text-slate-400 mt-1">
              전체 카테고리 종합
            </div>
          </div>

          <div className="bg-slate-950 border border-slate-800 rounded-2xl p-4 flex flex-col justify-between">
            <div className="text-xs font-medium text-slate-400">총 공고 대수</div>
            <div className="text-2xl sm:text-3xl font-extrabold text-slate-100 mt-1">
              {(summary.total_announced_units ?? 0).toLocaleString()}
              <span className="text-xs font-normal text-slate-400 ml-1">대</span>
            </div>
            <div className="text-[11px] text-slate-400 mt-1">
              총 배정 예산 {(summary.total_budget_billion_krw ?? 0).toLocaleString()}억 원
            </div>
          </div>

          <div className="bg-slate-950 border border-slate-800 rounded-2xl p-4 flex flex-col justify-between">
            <div className="text-xs font-medium text-slate-400">총 접수 대수</div>
            <div className="text-2xl sm:text-3xl font-extrabold text-blue-400 mt-1">
              {(summary?.total_applied_units ?? 0).toLocaleString()}
              <span className="text-xs font-normal text-slate-400 ml-1">대</span>
            </div>
            <div className="text-[11px] text-slate-400 mt-1">
              출고 완료: {(summary?.total_delivered_units ?? 0).toLocaleString()}대
            </div>
          </div>

          <div className="bg-slate-950 border border-slate-800 rounded-2xl p-4 flex flex-col justify-between">
            <div className="text-xs font-medium text-slate-400">전국 잔여 대수</div>
            <div className="text-2xl sm:text-3xl font-extrabold text-emerald-400 mt-1">
              {(summary?.total_remaining_units ?? 0).toLocaleString()}
              <span className="text-xs font-normal text-slate-400 ml-1">대</span>
            </div>
            <div className="text-[11px] text-slate-400 mt-1">
              잔여율 {(100 - (summary?.nationwide_depletion_rate ?? 0)).toFixed(1)}%
            </div>
          </div>

          <div className="col-span-2 md:col-span-1 bg-rose-950 border border-rose-500/40 rounded-2xl p-4 flex flex-col justify-between">
            <div className="text-xs font-medium text-rose-300">긴급 마감 위험 지역</div>
            <div className="text-2xl sm:text-3xl font-extrabold text-rose-400 mt-1">
              {(summary?.alert_region_counts?.critical ?? 0) + (summary?.alert_region_counts?.depleted ?? 0)}
              <span className="text-xs font-normal text-rose-300 ml-1">개 시도</span>
            </div>
            <div className="text-[11px] text-rose-300 mt-1">
              소진율 95% 이상 극소량
            </div>
          </div>
        </div>

        {/* Emergency Alert Ticker for Critical Municipalities */}
        {criticalRegions.length > 0 && (
          <div className="mt-6 bg-rose-950 border border-rose-500/50 rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs sm:text-sm">
            <div className="flex items-center gap-2 text-rose-200">
              <span className="text-base" aria-hidden="true">🚨</span>
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
                    className="px-2 py-0.5 rounded bg-rose-900 border border-rose-500/50 text-rose-200 hover:bg-rose-800 hover:text-white transition font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
                    title={`${crit.name_ko} 보조금 계산기로 이동`}
                  >
                    {crit.name_ko} ({crit.categories?.passenger?.depletion_rate ?? 0}%)
                  </button>
                ))}
              </div>
            </div>
            <a
              href="#subsidy-calculator"
              className="text-amber-300 hover:text-amber-200 underline font-semibold shrink-0 rounded px-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
            >
              내 차 실구매가 즉시 계산 &rarr;
            </a>
          </div>
        )}
      </section>

      {/* 2. 5-Tier Alert Badges Legend & Quick Filter - Solid Opaque Background for WCAG AA Contrast */}
      <section aria-label="보조금 소진 5단계 경보 범례" className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <h2 className="text-sm font-bold text-slate-300 flex items-center gap-2">
            <span aria-hidden="true">🛡️</span> 전국 지자체 보조금 소진 5단계 경보 기준
          </h2>
          <span className="text-xs text-slate-300">배지 클릭 시 해당 경보 지역만 필터링</span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
          {(Object.keys(thresholds) as AlertSeverity[]).map((key) => {
            const t = thresholds[key];
            const isSelected = alertFilter === key;
            return (
              <button
                key={key}
                type="button"
                aria-pressed={isSelected}
                onClick={() => setAlertFilter(isSelected ? 'ALL' : key)}
                className={`p-3 rounded-xl border text-left transition flex flex-col justify-between focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 ${
                  isSelected
                    ? 'ring-2 ring-amber-400 ' + getBadgeStyle(key)
                    : 'bg-slate-950 hover:bg-slate-800 border-slate-800 text-slate-300'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-xs px-2 py-0.5 rounded font-semibold border ${getBadgeStyle(key)}`}>
                    {getStatusLabel(key)}
                  </span>
                  <span className="text-[11px] text-slate-300 font-medium">{(t?.min_percent ?? 0)}%~{(t?.max_percent ?? 100)}%</span>
                </div>
                <div className="text-[11px] text-slate-300 line-clamp-2 mt-2 leading-relaxed">
                  {t?.recommended_action || ''}
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
          <div role="tablist" aria-label="차종 카테고리 선택" className="flex items-center gap-1.5 p-1 bg-slate-950 rounded-xl border border-slate-800 text-xs sm:text-sm font-semibold">
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
                  className={`px-3 py-1.5 rounded-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 ${
                    isSelected
                      ? 'bg-blue-600 text-white shadow'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {cat.icon} {cat.label}
                </button>
              );
            })}
          </div>

          {/* Supplementary Budget Toggle */}
          <label htmlFor="supplementary-budget-toggle" className="flex items-center gap-2 cursor-pointer text-xs sm:text-sm text-slate-300 hover:text-white select-none">
            <input
              id="supplementary-budget-toggle"
              type="checkbox"
              aria-label="추경 예산 편성 지자체만 보기"
              checked={supplementaryOnly}
              onChange={(e) => setSupplementaryOnly(e.target.checked)}
              className="w-4 h-4 rounded bg-slate-800 border-slate-700 text-amber-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
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
              className="w-full pl-10 pr-9 py-2.5 rounded-xl bg-slate-950 border border-slate-700 text-white placeholder-slate-400 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                aria-label="검색어 지우기"
                className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-white text-sm rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
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
                aria-pressed={zoneFilter === zone.id}
                onClick={() => setZoneFilter(zone.id as ZoneFilter)}
                className={`px-2.5 py-1.5 rounded-lg border font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 ${
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
              className="py-2.5 px-3 rounded-xl bg-slate-950 border border-slate-700 text-slate-200 text-xs sm:text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 cursor-pointer"
            >
              <option value="DEPLETION_DESC">소진율 높은 순 (마감임박)</option>
              <option value="DEPLETION_ASC">소진율 낮은 순 (신청여유)</option>
              <option value="REMAINING_ASC">잔여 대수 적은 순</option>
              <option value="LOCAL_SUBSIDY_DESC">지자체 보조금 높은 순</option>
              <option value="NAME_ASC">지역명 가나다순</option>
            </select>
          </div>
        </div>

        {/* Active Filter Clear indicator with aria-live */}
        {(zoneFilter !== 'ALL' || alertFilter !== 'ALL' || searchQuery || supplementaryOnly) && (
          <div className="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-800" aria-live="polite">
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
              className="text-amber-400 hover:text-amber-300 underline font-medium rounded px-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
            >
              전체 필터 초기화
            </button>
          </div>
        )}
      </section>

      {/* 4. 17 Regional Grid Cards - Visible Focus Ring for Keyboard Users */}
      <section
        id="panel-regional-grid"
        role="tabpanel"
        aria-labelledby={`tab-category-${selectedCategory}`}
        tabIndex={0}
        className="space-y-4 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-2xl"
      >
        <div className="flex items-center justify-between">
          <h2 id="regional-grid-heading" className="text-xl sm:text-2xl font-bold text-slate-900 flex items-center gap-2">
            <span aria-hidden="true">🗺️</span> 17개 광역시도별 보조금 소진율 &amp; 잔여 쿼터 현황
          </h2>
          <span className="text-xs text-slate-600">
            {selectedCategory === 'passenger' ? '전기승용 기준' : selectedCategory === 'commercial' ? '전기화물 기준' : '전기승합 기준'}
            {filteredRegions.length < regions.length && ` (검색 결과 ${filteredRegions.length}개 지역)`}
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
            {filteredRegions.map((regionItem) => (
              <RegionCard
                key={regionItem.region_id}
                region={regionItem}
                selectedCategory={selectedCategory}
                isExpanded={!!expandedRegions[regionItem.region_id]}
                toggleRegionExpand={toggleRegionExpand}
                onSelectForCalc={handleSelectRegionForCalc}
              />
            ))}
          </div>
        )}
      </section>

      {/* 5. Interactive Real-Time Net Subsidy Calculator (Memoized Sub-Component) */}
      <SubsidyCalculator
        calculatorRef={calculatorRef}
        models={models}
        regions={regions}
        selectedModelId={selectedModelId}
        selectedRegionId={selectedRegionId}
        onSelectModelId={handleSelectModelId}
        onSelectRegionId={handleSelectRegionId}
      />

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
