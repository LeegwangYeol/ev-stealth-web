'use client';

import React, { useState, useMemo, useEffect, useCallback, useRef, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import type {
  RecallDatabase,
  VinCheckResult,
} from '@/lib/getRecallData';
import {
  decodeVinAndCheckRecalls,
  checkRecallsByModel,
  validateVinString,
  getDistinctBrands,
  getModelsForBrand,
} from '@/lib/getRecallData';

const BRAND_SYNONYMS: Record<string, string> = {
  tesla: '테슬라',
  hyundai: '현대자동차',
  genesis: '제네시스',
  kia: '기아',
  mercedes: '메르세데스-벤츠',
  benz: '메르세데스-벤츠',
  'mercedes-benz': '메르세데스-벤츠',
  bmw: 'BMW',
  byd: 'BYD',
  chevrolet: '쉐보레',
  chevy: '쉐보레',
  polestar: '폴스타',
  porsche: '포르쉐',
};

function resolveBrand(inputBrand: string, availableBrands: string[]): string | undefined {
  const normalized = inputBrand.trim().toLowerCase();
  const direct = availableBrands.find((b) => b.toLowerCase() === normalized);
  if (direct) return direct;

  const synonym = BRAND_SYNONYMS[normalized];
  if (synonym) {
    const synonymMatch = availableBrands.find((b) => b.toLowerCase() === synonym.toLowerCase());
    if (synonymMatch) return synonymMatch;
  }

  const partial = availableBrands.find(
    (b) => b.toLowerCase().includes(normalized) || normalized.includes(b.toLowerCase())
  );
  if (partial) return partial;

  return undefined;
}

function resolveModelAndBrand(
  modelParam: string | null,
  brandParam: string | null,
  initialDatabase: RecallDatabase,
  availableBrands: string[]
): { brand: string; model: string } | null {
  let resolvedBrand: string | undefined = brandParam
    ? resolveBrand(brandParam, availableBrands)
    : undefined;

  let resolvedModel: string | undefined;

  if (modelParam) {
    const cleanModel = modelParam.trim();
    const cleanLower = cleanModel.toLowerCase();
    const withoutParens = cleanLower.replace(/\([^)]*\)/g, '').trim();

    // Generate normalization variants
    const variants = Array.from(
      new Set([
        cleanLower,
        withoutParens,
        cleanLower.replace(/^model\s*/i, '모델 '),
        cleanLower.replace(/^모델\s*/i, 'model '),
        withoutParens.replace(/^model\s*/i, '모델 '),
        withoutParens.replace(/^모델\s*/i, 'model '),
        cleanLower.replace(/아이오닉\s*([0-9]+)/i, '아이오닉 $1'),
        withoutParens.replace(/아이오닉\s*([0-9]+)/i, '아이오닉 $1'),
      ])
    ).filter(Boolean);

    // Collect all candidate items with their brand and model
    const candidates: Array<{ brand: string; model: string }> = [];
    initialDatabase.battery_profiles.forEach((p) =>
      candidates.push({ brand: p.brand, model: p.model_name })
    );
    initialDatabase.vin_prefixes.forEach((vp) =>
      candidates.push({ brand: vp.brand, model: vp.model_name })
    );
    initialDatabase.recalls.forEach((r) => {
      r.target_model.split(',').forEach((mStr) => {
        candidates.push({ brand: r.brand, model: mStr.trim() });
      });
    });

    // 1. Exact match on model variant
    let matchedCandidate: { brand: string; model: string } | undefined;
    for (const v of variants) {
      matchedCandidate = candidates.find((c) => {
        const cLower = c.model.toLowerCase();
        const brandMatch = !resolvedBrand || c.brand === resolvedBrand;
        return brandMatch && cLower === v;
      });
      if (matchedCandidate) break;
    }

    // 2. StartsWith match on model variant
    if (!matchedCandidate) {
      for (const v of variants) {
        matchedCandidate = candidates.find((c) => {
          const cLower = c.model.toLowerCase();
          const brandMatch = !resolvedBrand || c.brand === resolvedBrand;
          return brandMatch && (cLower.startsWith(v) || v.startsWith(cLower));
        });
        if (matchedCandidate) break;
      }
    }

    // 3. Includes match
    if (!matchedCandidate) {
      for (const v of variants) {
        matchedCandidate = candidates.find((c) => {
          const cLower = c.model.toLowerCase();
          const brandMatch = !resolvedBrand || c.brand === resolvedBrand;
          return brandMatch && (cLower.includes(v) || v.includes(cLower));
        });
        if (matchedCandidate) break;
      }
    }

    if (matchedCandidate) {
      if (!resolvedBrand) resolvedBrand = resolveBrand(matchedCandidate.brand, availableBrands);
      resolvedModel = matchedCandidate.model;
    } else {
      resolvedModel = cleanModel;
    }
  }

  // If brand is resolved but not model, take the first model of this brand
  if (resolvedBrand && !resolvedModel) {
    const brandModels = getModelsForBrand(resolvedBrand, initialDatabase);
    resolvedModel = brandModels[0] || '';
  }

  if (resolvedBrand && resolvedModel) {
    const brandModels = getModelsForBrand(resolvedBrand, initialDatabase);
    const matchedBrandModel = brandModels.find(
      (m) =>
        m.toLowerCase() === resolvedModel!.toLowerCase() ||
        m.toLowerCase().startsWith(resolvedModel!.toLowerCase()) ||
        resolvedModel!.toLowerCase().startsWith(m.toLowerCase()) ||
        m.toLowerCase().includes(resolvedModel!.toLowerCase()) ||
        resolvedModel!.toLowerCase().includes(m.toLowerCase())
    );
    if (matchedBrandModel) {
      resolvedModel = matchedBrandModel;
    }

    return { brand: resolvedBrand, model: resolvedModel };
  }

  return null;
}

interface SearchParamsWatcherProps {
  onSelectBrandModel: (brand: string, model: string, year?: number) => void;
  initialDatabase: RecallDatabase;
  availableBrands: string[];
}

function SearchParamsWatcher({
  onSelectBrandModel,
  initialDatabase,
  availableBrands,
}: SearchParamsWatcherProps) {
  const searchParams = useSearchParams();
  const lastAppliedRef = useRef<string>('');

  useEffect(() => {
    const currentParamString = searchParams.toString();
    if (!currentParamString || currentParamString === lastAppliedRef.current) return;

    const modelParam = searchParams.get('model');
    const brandParam = searchParams.get('brand');
    const yearParam = searchParams.get('year');

    if (!modelParam && !brandParam) return;

    lastAppliedRef.current = currentParamString;

    const resolved = resolveModelAndBrand(
      modelParam,
      brandParam,
      initialDatabase,
      availableBrands
    );

    if (resolved) {
      const year = yearParam ? parseInt(yearParam, 10) : undefined;
      onSelectBrandModel(
        resolved.brand,
        resolved.model,
        isNaN(year as number) ? undefined : year
      );
    }
  }, [searchParams, initialDatabase, availableBrands, onSelectBrandModel]);

  return null;
}

interface RecallPortalClientProps {
  initialDatabase: RecallDatabase;
}

export default function RecallPortalClient({ initialDatabase }: RecallPortalClientProps) {
  // Mode selection: Mode A (VIN) or Mode B (Model / Year)
  const [activeCheckerMode, setActiveCheckerMode] = useState<'VIN' | 'MODEL'>('VIN');

  // Mode A state
  const [vinInput, setVinInput] = useState<string>('');
  const [vinTouched, setVinTouched] = useState<boolean>(false);

  // Mode B state
  const [selectedBrand, setSelectedBrand] = useState<string>('메르세데스-벤츠');
  const [selectedModel, setSelectedModel] = useState<string>('EQE 350+');
  const [selectedYear, setSelectedYear] = useState<number | ''>(2023);

  // Active check result
  const [checkResult, setCheckResult] = useState<VinCheckResult | null>(null);

  // Battery directory search and filters
  const [batterySearch, setBatterySearch] = useState<string>('');
  const [selectedSupplierFilter, setSelectedSupplierFilter] = useState<string>('ALL');
  const [selectedFireStatusFilter, setSelectedFireStatusFilter] = useState<string>('ALL');

  // Recalls catalog search and filters
  const [recallSearch, setRecallSearch] = useState<string>('');
  const [selectedRiskFilter, setSelectedRiskFilter] = useState<string>('ALL');
  const [selectedRemedyFilter, setSelectedRemedyFilter] = useState<string>('ALL');

  // Expanded recall card IDs for accordion view
  const [expandedRecallIds, setExpandedRecallIds] = useState<Set<string>>(new Set());

  // Scroll timer ref to track and clear timeouts
  const scrollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Clear pending timers on unmount to prevent memory leaks
  useEffect(() => {
    return () => {
      if (scrollTimerRef.current) {
        clearTimeout(scrollTimerRef.current);
      }
    };
  }, []);

  // Available brands and models for Mode B
  const availableBrands = useMemo(() => getDistinctBrands(initialDatabase), [initialDatabase]);
  const availableModels = useMemo(
    () => (selectedBrand ? getModelsForBrand(selectedBrand, initialDatabase) : []),
    [selectedBrand, initialDatabase]
  );

  // Handler for query parameter auto-selection (?model=..., ?brand=...)
  const handleSelectFromParams = useCallback(
    (brand: string, model: string, year?: number) => {
      setSelectedBrand(brand);
      setSelectedModel(model);
      if (typeof year === 'number') {
        setSelectedYear(year);
      }
      setActiveCheckerMode('MODEL');
      const result = checkRecallsByModel(brand, model, year, initialDatabase);
      setCheckResult(result);
    },
    [initialDatabase]
  );

  // Live validation for VIN input
  const vinValidation = useMemo(() => {
    if (!vinInput) return { valid: false, normalized: '', error: '' };
    return validateVinString(vinInput);
  }, [vinInput]);

  // Handle Mode A lookup
  const handleVinSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setVinTouched(true);
    if (!vinInput.trim()) return;

    const result = decodeVinAndCheckRecalls(vinInput, initialDatabase);
    setCheckResult(result);
  };

  // Quick 1-click sample VIN handler
  const handleSelectSampleVin = (sampleVin: string) => {
    setVinInput(sampleVin);
    setVinTouched(true);
    const result = decodeVinAndCheckRecalls(sampleVin, initialDatabase);
    setCheckResult(result);
    // Clear any pending scroll timer before scheduling a new one
    if (scrollTimerRef.current) {
      clearTimeout(scrollTimerRef.current);
    }
    // Smooth scroll to result (deferred so React mounts the section first)
    scrollTimerRef.current = setTimeout(() => {
      const el = document.getElementById('search-result-section');
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
  };

  // Handle Mode B lookup
  const handleModelSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!selectedBrand || !selectedModel) return;

    const yr = typeof selectedYear === 'number' ? selectedYear : undefined;
    const result = checkRecallsByModel(selectedBrand, selectedModel, yr, initialDatabase);
    setCheckResult(result);
  };

  // Toggle card expansion
  const toggleRecallExpansion = (id: string) => {
    setExpandedRecallIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // Filtered Battery Safety Profiles
  const filteredBatteryProfiles = useMemo(() => {
    return initialDatabase.battery_profiles.filter((profile) => {
      const matchesSearch =
        batterySearch === '' ||
        profile.model_name.toLowerCase().includes(batterySearch.toLowerCase()) ||
        profile.brand.toLowerCase().includes(batterySearch.toLowerCase()) ||
        profile.cell_supplier.toLowerCase().includes(batterySearch.toLowerCase()) ||
        profile.cell_chemistry.toLowerCase().includes(batterySearch.toLowerCase());

      const matchesSupplier =
        selectedSupplierFilter === 'ALL' ||
        profile.cell_supplier.toLowerCase().includes(selectedSupplierFilter.toLowerCase());

      const matchesStatus =
        selectedFireStatusFilter === 'ALL' || profile.fire_incident_status === selectedFireStatusFilter;

      return matchesSearch && matchesSupplier && matchesStatus;
    });
  }, [initialDatabase.battery_profiles, batterySearch, selectedSupplierFilter, selectedFireStatusFilter]);

  // Filtered Recalls
  const filteredRecalls = useMemo(() => {
    return initialDatabase.recalls.filter((r) => {
      const matchesSearch =
        recallSearch === '' ||
        r.campaign_no.toLowerCase().includes(recallSearch.toLowerCase()) ||
        r.defect_title.toLowerCase().includes(recallSearch.toLowerCase()) ||
        r.target_model.toLowerCase().includes(recallSearch.toLowerCase()) ||
        r.brand.toLowerCase().includes(recallSearch.toLowerCase());

      const matchesRisk = selectedRiskFilter === 'ALL' || r.risk_level === selectedRiskFilter;
      const matchesRemedy = selectedRemedyFilter === 'ALL' || r.remedy_type === selectedRemedyFilter;

      return matchesSearch && matchesRisk && matchesRemedy;
    });
  }, [initialDatabase.recalls, recallSearch, selectedRiskFilter, selectedRemedyFilter]);

  // Distinct cell supplier list for filter chips
  const supplierFilters = [
    { key: 'ALL', label: '전체' },
    { key: '파라시스', label: '파라시스(Farasis)' },
    { key: 'LG', label: 'LG에너지솔루션' },
    { key: 'SK', label: 'SK온' },
    { key: '삼성', label: '삼성SDI' },
    { key: 'CATL', label: 'CATL' },
    { key: 'BYD', label: 'BYD FinDreams' },
  ];

  // Active VIN error state for accessible form feedback
  const vinError = vinTouched && vinInput.length > 0 && !vinValidation.valid ? vinValidation.error : '';

  const handleModeKeyDown = (e: React.KeyboardEvent, currentMode: 'VIN' | 'MODEL') => {
    let nextMode: 'VIN' | 'MODEL' | null = null;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      nextMode = currentMode === 'VIN' ? 'MODEL' : 'VIN';
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      nextMode = currentMode === 'VIN' ? 'MODEL' : 'VIN';
    } else if (e.key === 'Home') {
      e.preventDefault();
      nextMode = 'VIN';
    } else if (e.key === 'End') {
      e.preventDefault();
      nextMode = 'MODEL';
    }
    if (nextMode && nextMode !== currentMode) {
      setActiveCheckerMode(nextMode);
      setCheckResult(null);
      const nextId = nextMode === 'VIN' ? 'vin-checker-tab' : 'model-checker-tab';
      document.getElementById(nextId)?.focus();
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 font-sans pb-16">
      <Suspense fallback={null}>
        <SearchParamsWatcher
          onSelectBrandModel={handleSelectFromParams}
          initialDatabase={initialDatabase}
          availableBrands={availableBrands}
        />
      </Suspense>

      {/* 1. Header & Live Alert Hero */}
      <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur-md relative z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-900/60 text-red-200 border border-red-700/50 animate-pulse motion-reduce:animate-none">
                  🚨 대한민국 국토교통부 & NHTSA 공시 연동
                </span>
                <span className="text-xs text-slate-400">기준: 2026 최신 개정판</span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white flex items-center gap-2.5">
                <span>전기차 공식 리콜 & 배터리 화재 안전 포털</span>
              </h1>
              <p className="text-sm text-slate-300 mt-1 max-w-3xl">
                17자리 차대번호(VIN) 및 차종별 배터리 제조사(파라시스, LG, SK, 삼성, CATL 등), 화재 결함 이력,
                ICCU 동력상실 리콜 및 아파트 지하주차장 충전 가이드를 즉시 확인하십시오.
              </p>
            </div>

            {/* Quick action buttons */}
            <div className="flex flex-wrap items-center gap-2">
              <a
                href="https://www.car.go.kr"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
              >
                <svg className="w-3.5 h-3.5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
                자동차리콜센터 공식
                <span className="sr-only"> (새 창에서 열림)</span>
              </a>
              <a
                href="#battery-directory"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/40 transition"
              >
                🔋 배터리 제조사 공개표
              </a>
            </div>
          </div>

          {/* Key Safety Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6">
            <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-3.5 shadow-sm">
              <span className="text-xs text-slate-400 font-medium">분석 리콜 캠페인</span>
              <div className="text-xl sm:text-2xl font-black text-white mt-0.5">
                {initialDatabase.metadata.total_campaigns}
                <span className="text-xs font-normal text-slate-400 ml-1">건 (정부 공시)</span>
              </div>
            </div>

            <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-3.5 shadow-sm">
              <span className="text-xs text-slate-400 font-medium">국내(KDM) 대상 차량</span>
              <div className="text-xl sm:text-2xl font-black text-amber-400 mt-0.5">
                {initialDatabase.metadata.total_affected_vehicles_kdm.toLocaleString()}
                <span className="text-xs font-normal text-slate-400 ml-1">대</span>
              </div>
            </div>

            <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-3.5 shadow-sm">
              <span className="text-xs text-slate-400 font-medium">긴급 화재 특별주의보</span>
              <div className="text-xl sm:text-2xl font-black text-red-400 mt-0.5">
                {initialDatabase.metadata.active_fire_campaigns}
                <span className="text-xs font-normal text-slate-400 ml-1">개 차종</span>
              </div>
            </div>

            <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-3.5 shadow-sm">
              <span className="text-xs text-slate-400 font-medium">OTA 무선 조치 지원율</span>
              <div className="text-xl sm:text-2xl font-black text-emerald-400 mt-0.5">
                {initialDatabase.metadata.ota_remedy_rate_pct}
                <span className="text-xs font-normal text-slate-400 ml-1">% (방문 불필요)</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-12">
        {/* 2. Dual-Mode Verification Tool */}
        <section className="bg-slate-950 border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-xl">
          <div className="max-w-3xl mb-6">
            <h2 className="text-xl sm:text-2xl font-bold text-white flex items-center gap-2">
              <svg className="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
              <span>차량 결함 & 리콜 즉시 판정기</span>
            </h2>
            <p className="text-sm text-slate-400 mt-1">
              차량등록증의 차대번호 17자리를 입력하거나 제조사·차종을 선택하면 매칭 리콜과 배터리 정보를 즉시 분석합니다.
            </p>
          </div>

          {/* Mode Switcher Tabs */}
          <div role="tablist" aria-label="리콜 조회 방식 선택" className="flex border-b border-slate-800 mb-6">
            <button
              type="button"
              role="tab"
              aria-selected={activeCheckerMode === 'VIN'}
              aria-controls="vin-checker-panel"
              id="vin-checker-tab"
              tabIndex={activeCheckerMode === 'VIN' ? 0 : -1}
              onKeyDown={(e) => handleModeKeyDown(e, 'VIN')}
              onClick={() => {
                setActiveCheckerMode('VIN');
                setCheckResult(null);
              }}
              className={`py-3 px-5 text-sm font-semibold border-b-2 transition flex items-center gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
                activeCheckerMode === 'VIN'
                  ? 'border-blue-500 text-blue-400 bg-blue-950/20'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
              </svg>
              <span>[모드 A] 17자리 차대번호(VIN) 정밀 조회</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeCheckerMode === 'MODEL'}
              aria-controls="model-checker-panel"
              id="model-checker-tab"
              tabIndex={activeCheckerMode === 'MODEL' ? 0 : -1}
              onKeyDown={(e) => handleModeKeyDown(e, 'MODEL')}
              onClick={() => {
                setActiveCheckerMode('MODEL');
                setCheckResult(null);
              }}
              className={`py-3 px-5 text-sm font-semibold border-b-2 transition flex items-center gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
                activeCheckerMode === 'MODEL'
                  ? 'border-blue-500 text-blue-400 bg-blue-950/20'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
              </svg>
              <span>[모드 B] 제조사 / 차종 / 연식 간편 선택</span>
            </button>
          </div>

          {/* MODE A Form */}
          {activeCheckerMode === 'VIN' && (
            <div id="vin-checker-panel" role="tabpanel" aria-labelledby="vin-checker-tab" tabIndex={0} className="focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-2xl">
              <form onSubmit={handleVinSubmit} className="space-y-4">
                <div>
                  <label htmlFor="vin-input" className="block text-sm font-medium text-slate-200 mb-2">
                    차대번호 17자리 입력 (영문 대문자 및 숫자)
                  </label>
                  <div className="relative">
                    <input
                      id="vin-input"
                      type="text"
                      maxLength={17}
                      value={vinInput}
                      aria-label="17자리 차대번호(VIN) 입력"
                      aria-invalid={!!vinError}
                      aria-describedby={vinError ? "vin-error-feedback" : undefined}
                      onChange={(e) => {
                        setVinInput(e.target.value.toUpperCase());
                        setVinTouched(true);
                      }}
                      placeholder="예: KM8KN4AE4NU123456 또는 W1K295112PF123456"
                      className={`w-full bg-slate-900 border rounded-xl px-4 py-3.5 text-base font-mono tracking-wider text-white placeholder-slate-400 focus:outline-none focus:ring-2 transition ${
                        vinError
                          ? 'border-red-500 focus:ring-red-500/50'
                          : 'border-slate-700 focus:ring-blue-500/50 focus:border-blue-500'
                      }`}
                    />
                    <div className="absolute right-3 top-3.5 text-xs font-mono text-slate-400">
                      {vinInput.replace(/[\s-]/g, '').length}/17
                    </div>
                  </div>

                  {/* Realtime validation feedback */}
                  {vinError && (
                    <p id="vin-error-feedback" role="alert" className="mt-2 text-xs text-red-400 flex items-center gap-1.5">
                      <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
                        <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                      </svg>
                      {vinError}
                    </p>
                  )}

                  {vinTouched && vinValidation.valid && (
                    <p className="mt-2 text-xs text-emerald-400 flex items-center gap-1.5">
                      <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                      </svg>
                      유효한 ISO 3779 17자리 차대번호 형식입니다.
                    </p>
                  )}
                </div>

                <div className="flex flex-col sm:flex-row sm:items-center gap-3 pt-2">
                  <button
                    type="submit"
                    disabled={!vinValidation.valid}
                    className="w-full sm:w-auto px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-500 text-white font-semibold text-sm transition shadow-lg flex items-center justify-center gap-2"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                    차대번호로 리콜 & 배터리 진단
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setVinInput('');
                      setVinTouched(false);
                      setCheckResult(null);
                    }}
                    className="px-4 py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium transition"
                  >
                    초기화
                  </button>
                </div>
              </form>

              {/* 1-Click Sample VIN Quick Selector Buttons */}
              <div className="mt-6 pt-6 border-t border-slate-800/80">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                    💡 차대번호가 기억나지 않으시나요? 1초 샘플 차대번호 클릭:
                  </span>
                  <span className="text-[11px] text-slate-400">실제 KDM 출고 규격</span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
                  {initialDatabase.vin_prefixes.slice(0, 6).map((item) => (
                    <button
                      key={item.prefix}
                      type="button"
                      onClick={() => handleSelectSampleVin(item.sample_full_vin)}
                      className="p-2.5 rounded-lg bg-slate-900 hover:bg-blue-900/40 border border-slate-800 hover:border-blue-700 text-left transition group"
                    >
                      <div className="text-xs font-bold text-white group-hover:text-blue-300 truncate">
                        {item.model_name}
                      </div>
                      <div className="text-[10px] text-slate-400 truncate mt-0.5">
                        {item.brand}
                      </div>
                      <div className="text-[10px] font-mono text-blue-400/90 truncate mt-1">
                        {item.prefix}...
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* MODE B Form */}
          {activeCheckerMode === 'MODEL' && (
            <div id="model-checker-panel" role="tabpanel" aria-labelledby="model-checker-tab" tabIndex={0} className="focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-2xl">
              <form onSubmit={handleModelSubmit} className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  {/* Brand */}
                  <div>
                    <label htmlFor="brand-select" className="block text-xs font-semibold text-slate-300 uppercase mb-2">
                      1. 제조사 선택
                    </label>
                    <select
                      id="brand-select"
                      value={selectedBrand}
                      onChange={(e) => {
                        const newBrand = e.target.value;
                        setSelectedBrand(newBrand);
                        const models = getModelsForBrand(newBrand, initialDatabase);
                        setSelectedModel(models[0] || '');
                      }}
                      className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      {availableBrands.map((b) => (
                        <option key={b} value={b}>
                          {b}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Model */}
                  <div>
                    <label htmlFor="model-select" className="block text-xs font-semibold text-slate-300 uppercase mb-2">
                      2. 모델 선택
                    </label>
                    <select
                      id="model-select"
                      value={selectedModel}
                      onChange={(e) => setSelectedModel(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      {availableModels.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Production Year */}
                  <div>
                    <label htmlFor="year-select" className="block text-xs font-semibold text-slate-300 uppercase mb-2">
                      3. 생산 연식 선택
                    </label>
                    <select
                      id="year-select"
                      value={selectedYear}
                      onChange={(e) => setSelectedYear(e.target.value ? Number(e.target.value) : '')}
                      className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="">전체 연식 확인</option>
                      {[2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018].map((yr) => (
                        <option key={yr} value={yr}>
                          {yr}년식
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="pt-2">
                  <button
                    type="submit"
                    className="w-full sm:w-auto px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm transition shadow-lg flex items-center justify-center gap-2"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                    </svg>
                    선택 차종 결함 및 리콜 진단
                  </button>
                </div>
              </form>
            </div>
          )}
        </section>

        {/* 3. Live Search Result Display */}
        {checkResult && (
          <section id="search-result-section" aria-live="polite" className="space-y-6 scroll-mt-24">
            {/* Overall Risk Banner */}
            <div
              className={`rounded-2xl p-6 shadow-2xl border ${
                checkResult.overallRiskGrade === 'CRITICAL'
                  ? 'bg-gradient-to-br from-red-950 via-red-900 to-slate-950 border-red-700 text-white'
                  : checkResult.overallRiskGrade === 'WARNING'
                  ? 'bg-gradient-to-br from-amber-950 via-amber-900 to-slate-950 border-amber-700 text-white'
                  : 'bg-gradient-to-br from-emerald-950 via-emerald-900 to-slate-950 border-emerald-700 text-white'
              }`}
            >
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-start gap-4">
                  <div className="p-3 rounded-xl bg-black/40 text-2xl flex-shrink-0">
                    {checkResult.overallRiskGrade === 'CRITICAL'
                      ? '🚨'
                      : checkResult.overallRiskGrade === 'WARNING'
                      ? '⚠️'
                      : '✅'}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-extrabold uppercase tracking-wider px-2 py-0.5 rounded bg-black/50">
                        {checkResult.overallRiskGrade === 'CRITICAL'
                          ? '긴급 안전 주의보 발령'
                          : checkResult.overallRiskGrade === 'WARNING'
                          ? '안전 리콜 조치 권고'
                          : '안전 검증 완료'}
                      </span>
                      <span className="text-xs text-slate-300">
                        조회 일시: {new Date(checkResult.timestamp).toLocaleDateString('ko-KR')}
                      </span>
                    </div>

                    <h3 className="text-xl sm:text-2xl font-black mt-1">
                      {checkResult.decodedBrand} {checkResult.decodedModel}{' '}
                      {checkResult.decodedYear ? `${checkResult.decodedYear}년식` : ''} 판정 결과
                    </h3>

                    <p className="text-sm text-slate-200 mt-1 max-w-3xl leading-relaxed">
                      {checkResult.hasFireRisk
                        ? '배터리 열폭주 화재 위험 또는 정부 특별 안전점검 대상 모델입니다. 즉시 완충 한도 설정 및 공식 서비스센터 점검을 완료하십시오.'
                        : checkResult.hasPowerLoss
                        ? '통합충전제어장치(ICCU) 파손 또는 주행 중 동력 상실 결함 관련 공식 리콜이 발령되어 있습니다. 센터 방문 무상 소프트웨어 업데이트가 필요합니다.'
                        : checkResult.recalls.length > 0
                        ? `총 ${checkResult.recalls.length}건의 안전 리콜 및 무상수리 캠페인이 확인되었습니다.`
                        : '현재 정부 국토교통부 및 해외 규제당국에 등록된 긴급 안전 리콜 대상이 확인되지 않았습니다.'}
                    </p>
                  </div>
                </div>

                <div className="flex flex-row md:flex-col items-end justify-between md:justify-center border-t md:border-t-0 md:border-l border-white/10 pt-3 md:pt-0 md:pl-6 gap-2">
                  <div className="text-right">
                    <span className="text-xs text-slate-300">매칭 리콜</span>
                    <div className="text-2xl font-black">{checkResult.recalls.length}건</div>
                  </div>
                  {checkResult.decodedCountry && (
                    <span className="text-xs px-2 py-1 rounded bg-black/40 text-slate-300">
                      제조국: {checkResult.decodedCountry}
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Battery Safety Profile Card & Underground Parking Advisory */}
            {checkResult.batteryProfile && (
              <div className="bg-slate-950 border border-slate-800 rounded-2xl p-6 sm:p-7 shadow-lg space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-800 gap-2">
                  <div>
                    <span className="text-xs font-semibold text-blue-400 uppercase tracking-wider">
                      배터리 공급사 및 셀 상세 정보
                    </span>
                    <h4 className="text-lg font-bold text-white mt-0.5">
                      {checkResult.batteryProfile.model_name} 배터리 안전 제원
                    </h4>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-xs px-3 py-1 rounded-full font-bold border ${
                        checkResult.batteryProfile.fire_incident_status === 'CRITICAL_MONITORING'
                          ? 'bg-red-950/80 text-red-300 border-red-700'
                          : checkResult.batteryProfile.fire_incident_status === 'RECALLED_RESOLVED'
                          ? 'bg-amber-950/80 text-amber-300 border-amber-700'
                          : 'bg-emerald-950/80 text-emerald-300 border-emerald-700'
                      }`}
                    >
                      {checkResult.batteryProfile.fire_incident_status_ko}
                    </span>
                    <span className="text-xs px-3 py-1 rounded-full font-bold bg-blue-950 text-blue-300 border border-blue-800">
                      완충 권장 한도: {checkResult.batteryProfile.recommended_soc_limit}%
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                  <div className="bg-slate-900/90 rounded-xl p-4 border border-slate-800 space-y-2">
                    <div className="flex justify-between">
                      <span className="text-slate-400">배터리 셀 제조사:</span>
                      <span className="font-bold text-white">{checkResult.batteryProfile.cell_supplier}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">배터리 셀 화학(Chemistry):</span>
                      <span className="font-medium text-slate-200">{checkResult.batteryProfile.cell_chemistry}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">적용 생산 기간:</span>
                      <span className="font-mono text-slate-300">{checkResult.batteryProfile.years}</span>
                    </div>
                    <div className="pt-2 border-t border-slate-800/80 text-xs text-slate-300">
                      <span className="font-semibold text-blue-400">BMS 안전 보호 기술:</span>{' '}
                      {checkResult.batteryProfile.bms_safety_features}
                    </div>
                  </div>

                  <div className="bg-amber-950/30 border border-amber-800/50 rounded-xl p-4 space-y-2">
                    <div className="flex items-center gap-2 text-amber-300 font-bold text-xs">
                      <svg className="w-4 h-4 text-amber-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                      </svg>
                      🏢 아파트 지하주차장 이용 및 충전 가이드
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed">
                      {checkResult.batteryProfile.underground_parking_advisory}
                    </p>
                    <div className="pt-2 text-[11px] text-amber-200/80">
                      * 아파트 관리사무소 화재 예방 수칙 및 국토교통부 권고 기준 준수 권장.
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Matched Recall Campaign Cards */}
            <div className="space-y-4">
              <h4 className="text-lg font-bold text-white flex items-center gap-2">
                <span>해당 차종 대상 정부 공시 리콜 세부 내역 ({checkResult.recalls.length}건)</span>
              </h4>

              {checkResult.recalls.length === 0 ? (
                <div className="bg-slate-950 border border-slate-800 rounded-xl p-8 text-center text-slate-400">
                  <p className="text-base font-semibold text-slate-300">
                    현재 조회하신 조건에 해당하는 활성 리콜이 없습니다.
                  </p>
                  <p className="text-xs text-slate-400 mt-1">
                    정기적인 소프트웨어 업데이트(OTA) 및 공식 서비스센터 무상점검을 권장합니다.
                  </p>
                </div>
              ) : (
                checkResult.recalls.map((campaign) => {
                  const isExpanded = expandedRecallIds.has(campaign.id);
                  return (
                    <div
                      key={campaign.id}
                      className="bg-slate-950 border border-slate-800 rounded-2xl p-6 shadow-md hover:border-slate-700 transition space-y-4"
                    >
                      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                        <div className="space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-xs font-mono px-2.5 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800">
                              {campaign.campaign_no}
                            </span>
                            <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                              {campaign.agency_ko}
                            </span>
                            <span
                              className={`text-xs font-bold px-2 py-0.5 rounded ${
                                campaign.risk_level === 'FIRE_HAZARD'
                                  ? 'bg-red-950 text-red-300 border border-red-800'
                                  : campaign.risk_level === 'LOSS_OF_POWER'
                                  ? 'bg-orange-950 text-orange-300 border border-orange-800'
                                  : 'bg-slate-800 text-slate-300'
                              }`}
                            >
                              {campaign.risk_level_ko}
                            </span>
                            <span className="text-xs font-medium px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-300 border border-emerald-800/60">
                              {campaign.remedy_type_ko}
                            </span>
                          </div>

                          <h5 className="text-base sm:text-lg font-bold text-white pt-1">
                            {campaign.defect_title}
                          </h5>
                          <div className="text-xs text-slate-400">
                            대상: <strong className="text-slate-200">{campaign.target_model}</strong> (
                            {campaign.target_model_years}) | 대상 대수: 약{' '}
                            <span className="text-amber-400 font-semibold">
                              {campaign.affected_kdm_units.toLocaleString()}대
                            </span>
                          </div>
                        </div>

                        <button
                          type="button"
                          onClick={() => toggleRecallExpansion(campaign.id)}
                          aria-expanded={isExpanded}
                          aria-controls={"campaign-search-detail-" + campaign.id}
                          className="self-start px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 transition flex items-center gap-1.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                        >
                          <span>{isExpanded ? '상세 접기' : '대처요령 및 상세'}</span>
                          <svg
                            className={`w-3.5 h-3.5 transform transition-transform ${
                              isExpanded ? 'rotate-180' : ''
                            }`}
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                            aria-hidden="true"
                          >
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                          </svg>
                        </button>
                      </div>

                      {/* Defect overview */}
                      <p className="text-sm text-slate-300 leading-relaxed bg-slate-900/60 rounded-xl p-3.5 border border-slate-800/70">
                        <strong className="text-slate-200">결함 원인: </strong>
                        {campaign.defect_detail}
                      </p>

                      {/* Expandable full remedy and consumer emergency guide */}
                      {isExpanded && (
                        <div id={"campaign-search-detail-" + campaign.id} className="space-y-3 pt-2 border-t border-slate-800">
                          <div className="bg-blue-950/30 border border-blue-800/50 rounded-xl p-4 text-xs text-slate-200 space-y-1">
                            <div className="font-bold text-blue-300 flex items-center gap-1.5">
                              <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                              </svg>
                              제조사 공식 무상 시정 조치 방법
                            </div>
                            <p className="leading-relaxed">{campaign.remedy_action}</p>
                          </div>

                          <div className="bg-red-950/30 border border-red-800/50 rounded-xl p-4 text-xs text-slate-200 space-y-1">
                            <div className="font-bold text-red-300 flex items-center gap-1.5">
                              <svg className="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                              </svg>
                              🚨 차주 긴급 대처 행동 요령
                            </div>
                            <p className="leading-relaxed">{campaign.consumer_emergency_guide}</p>
                          </div>

                          <div className="flex flex-col sm:flex-row sm:items-center justify-between text-xs text-slate-400 pt-2 gap-2">
                            <div>
                              <span className="font-semibold text-slate-300">고객센터 접수: </span>
                              <span className="text-white font-mono">{campaign.service_center_contact}</span>
                            </div>
                            <a
                              href={campaign.official_link}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-400 hover:text-blue-300 flex items-center gap-1"
                            >
                              공식 제조사 리콜 공지 확인 &rarr;
                              <span className="sr-only"> (새 창에서 열림)</span>
                            </a>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </section>
        )}

        {/* 4. Battery Safety Directory (공개 배터리 제조사 및 지하주차장 안전 가이드) */}
        <section id="battery-directory" className="bg-slate-950 border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-xl space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-semibold px-2 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800">
                  전기차 차종별 배터리 실명제 공시 대장
                </span>
                <span className="text-xs text-slate-400">총 {initialDatabase.battery_profiles.length}개 차종</span>
              </div>
              <h2 className="text-xl sm:text-2xl font-bold text-white">
                🔋 전기차 배터리 제조사 & 지하주차장 안전 가이드
              </h2>
              <p className="text-sm text-slate-400 mt-0.5">
                국내 판매 주요 전기차의 실제 탑재 배터리 셀 제조사(파라시스, LG, SK, 삼성, CATL, BYD) 및 화재 모니터링 상태를 검색하십시오.
              </p>
            </div>

            {/* Search Input */}
            <div className="w-full md:w-72">
              <input
                type="text"
                value={batterySearch}
                onChange={(e) => setBatterySearch(e.target.value)}
                aria-label="배터리 제조사 및 모델 검색"
                placeholder="모델명, 제조사, 배터리명 검색..."
                className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Filter Chips: Suppliers & Status */}
          <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-slate-800">
            <span className="text-xs font-semibold text-slate-400 mr-2">제조사 필터:</span>
            {supplierFilters.map((s) => (
              <button
                key={s.key}
                type="button"
                onClick={() => setSelectedSupplierFilter(s.key)}
                aria-pressed={selectedSupplierFilter === s.key}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  selectedSupplierFilter === s.key
                    ? 'bg-blue-600 text-white font-bold'
                    : 'bg-slate-900 text-slate-300 hover:bg-slate-800 border border-slate-800'
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-slate-400 mr-2">화재 리스크 상태:</span>
            {[
              { key: 'ALL', label: '전체' },
              { key: 'CRITICAL_MONITORING', label: '🚨 집중 모니터링' },
              { key: 'RECALLED_RESOLVED', label: '🔄 조치 완료' },
              { key: 'VERIFIED_SAFE', label: '✅ 안전 검증' },
            ].map((f) => (
              <button
                key={f.key}
                type="button"
                onClick={() => setSelectedFireStatusFilter(f.key)}
                aria-pressed={selectedFireStatusFilter === f.key}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  selectedFireStatusFilter === f.key
                    ? 'bg-blue-600 text-white font-bold'
                    : 'bg-slate-900 text-slate-300 hover:bg-slate-800 border border-slate-800'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 pt-2">
            {filteredBatteryProfiles.map((p) => {
              const isCritical = p.fire_incident_status === 'CRITICAL_MONITORING';
              return (
                <div
                  key={p.model_id}
                  className={`rounded-2xl p-5 border transition space-y-3 flex flex-col justify-between ${
                    isCritical
                      ? 'bg-red-950/20 border-red-800/80 shadow-md shadow-red-950/30'
                      : 'bg-slate-900/90 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <div className="space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <span className="text-xs text-slate-400 font-medium">{p.brand}</span>
                        <h3 className="text-base font-bold text-white">{p.model_name}</h3>
                        <span className="text-[11px] font-mono text-slate-400">{p.years}</span>
                      </div>
                      <span
                        className={`text-[11px] font-bold px-2 py-0.5 rounded border flex-shrink-0 ${
                          isCritical
                            ? 'bg-red-950 text-rose-200 border-red-700 animate-pulse motion-reduce:animate-none'
                            : p.fire_incident_status === 'RECALLED_RESOLVED'
                            ? 'bg-amber-950 text-amber-200 border-amber-700'
                            : 'bg-emerald-950 text-emerald-200 border-emerald-700'
                        }`}
                      >
                        {p.fire_incident_status_ko}
                      </span>
                    </div>

                    <div className="bg-black/30 rounded-xl p-3 border border-white/5 space-y-1.5 text-xs">
                      <div className="flex justify-between">
                        <span className="text-slate-400">셀 제조사:</span>
                        <span className="font-bold text-white">{p.cell_supplier}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">셀 화학:</span>
                        <span className="text-slate-300">{p.cell_chemistry}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">완충 권장 한도:</span>
                        <span className="font-bold text-blue-300">{p.recommended_soc_limit}%</span>
                      </div>
                    </div>

                    <div className="text-xs text-slate-300 pt-1 leading-relaxed">
                      <strong className="text-amber-300">지하주차 가이드: </strong>
                      {p.underground_parking_advisory}
                    </div>
                  </div>

                  <div className="pt-2 border-t border-slate-800 text-[11px] text-slate-400 truncate">
                    🛡️ {p.bms_safety_features}
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* 5. All Recalls Directory (전체 공식 리콜 캠페인 탐색기) */}
        <section className="bg-slate-950 border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-xl space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-semibold px-2 py-0.5 rounded bg-red-950 text-red-300 border border-red-800">
                  국토교통부 자동차안전연구원 공시
                </span>
                <span className="text-xs text-slate-400">전체 공시 리콜 대장</span>
              </div>
              <h2 className="text-xl sm:text-2xl font-bold text-white">
                📋 전체 전기차 리콜 캠페인 카탈로그
              </h2>
              <p className="text-sm text-slate-400 mt-0.5">
                현대, 기아, 테슬라, 벤츠, BMW, BYD, 쉐보레, 폴스타, 포르쉐 등 주요 브랜드의 결함 내역을 탐색하십시오.
              </p>
            </div>

            {/* Search Input */}
            <div className="w-full md:w-72">
              <input
                type="text"
                value={recallSearch}
                onChange={(e) => setRecallSearch(e.target.value)}
                aria-label="전기차 리콜 캠페인 검색"
                placeholder="리콜번호, 제목, 차종 검색..."
                className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Filter Chips: Risk & Remedy */}
          <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-slate-800">
            <span className="text-xs font-semibold text-slate-400 mr-2">위험 등급:</span>
            {[
              { key: 'ALL', label: '전체' },
              { key: 'FIRE_HAZARD', label: '🔥 화재 위험' },
              { key: 'LOSS_OF_POWER', label: '⚡ 동력 상실/ICCU' },
              { key: 'BRAKE_STEERING', label: '🛑 조향/제동' },
              { key: 'SOFTWARE_REGULATION', label: '💻 소프트웨어/규정' },
            ].map((rf) => (
              <button
                key={rf.key}
                type="button"
                onClick={() => setSelectedRiskFilter(rf.key)}
                aria-pressed={selectedRiskFilter === rf.key}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  selectedRiskFilter === rf.key
                    ? 'bg-blue-600 text-white font-bold'
                    : 'bg-slate-900 text-slate-300 hover:bg-slate-800 border border-slate-800'
                }`}
              >
                {rf.label}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-slate-400 mr-2">조치 유형:</span>
            {[
              { key: 'ALL', label: '전체' },
              { key: 'HARDWARE_REPLACE', label: '🔧 부품 전량 무상 교체' },
              { key: 'SOFTWARE_UPDATE_SERVICE', label: '🛠️ 센터 방문 소프트웨어' },
              { key: 'OTA_WIRELESS', label: '📡 OTA 무선 업데이트' },
            ].map((rm) => (
              <button
                key={rm.key}
                type="button"
                onClick={() => setSelectedRemedyFilter(rm.key)}
                aria-pressed={selectedRemedyFilter === rm.key}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  selectedRemedyFilter === rm.key
                    ? 'bg-blue-600 text-white font-bold'
                    : 'bg-slate-900 text-slate-300 hover:bg-slate-800 border border-slate-800'
                }`}
              >
                {rm.label}
              </button>
            ))}
          </div>

          {/* List of Recalls */}
          <div className="space-y-3 pt-2">
            {filteredRecalls.map((campaign) => {
              const isExpanded = expandedRecallIds.has(campaign.id);
              return (
                <div
                  key={campaign.id}
                  className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition space-y-3"
                >
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2 mb-1">
                        <span className="text-xs font-mono px-2 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800">
                          {campaign.campaign_no}
                        </span>
                        <span className="text-xs font-semibold text-slate-400">
                          {campaign.brand} • {campaign.target_model} ({campaign.target_model_years})
                        </span>
                        <span
                          className={`text-[11px] font-bold px-2 py-0.5 rounded ${
                            campaign.risk_level === 'FIRE_HAZARD'
                              ? 'bg-red-950 text-red-300 border border-red-800'
                              : campaign.risk_level === 'LOSS_OF_POWER'
                              ? 'bg-orange-950 text-orange-300 border border-orange-800'
                              : 'bg-slate-800 text-slate-300'
                          }`}
                        >
                          {campaign.risk_level_ko}
                        </span>
                        <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                          {campaign.remedy_type_ko}
                        </span>
                      </div>
                      <h3 className="text-base font-bold text-white">{campaign.defect_title}</h3>
                    </div>

                    <button
                      type="button"
                      onClick={() => toggleRecallExpansion(campaign.id)}
                      aria-expanded={isExpanded}
                      aria-controls={"campaign-list-detail-" + campaign.id}
                      className="self-start text-xs text-blue-400 hover:text-blue-300 font-medium px-2.5 py-1 rounded bg-slate-800/80 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                    >
                      {isExpanded ? '닫기 ▲' : '상세 및 행동요령 ▼'}
                    </button>
                  </div>

                  <p className="text-xs text-slate-300 line-clamp-2 leading-relaxed">
                    {campaign.defect_detail}
                  </p>

                  {isExpanded && (
                    <div id={"campaign-list-detail-" + campaign.id} className="space-y-3 pt-3 border-t border-slate-800 text-xs">
                      <div>
                        <span className="font-semibold text-slate-200">생산 기간: </span>
                        <span className="font-mono text-slate-300">{campaign.production_date_range}</span>
                        <span className="ml-3 font-semibold text-slate-200">대상 대수: </span>
                        <span className="text-amber-400 font-semibold">{campaign.affected_kdm_units.toLocaleString()}대</span>
                      </div>

                      <div className="bg-slate-950 rounded-lg p-3 border border-slate-800/80 space-y-1">
                        <span className="font-bold text-blue-300">무상 수리 내용: </span>
                        <p className="text-slate-300">{campaign.remedy_action}</p>
                      </div>

                      <div className="bg-red-950/30 rounded-lg p-3 border border-red-900/50 space-y-1">
                        <span className="font-bold text-red-300">🚨 차주 긴급 대처 행동요령: </span>
                        <p className="text-slate-300">{campaign.consumer_emergency_guide}</p>
                      </div>

                      <div className="flex flex-col sm:flex-row sm:items-center justify-between text-slate-400 pt-1 gap-2">
                        <span>고객센터: <strong className="text-white">{campaign.service_center_contact}</strong></span>
                        <a
                          href={campaign.official_link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-400 hover:underline"
                        >
                          공식 웹사이트 바로가기 &rarr;
                          <span className="sr-only"> (새 창에서 열림)</span>
                        </a>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      </div>
    </div>
  );
}
