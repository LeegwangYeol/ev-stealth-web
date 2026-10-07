'use client';

import React, { useState, useMemo, useRef, useDeferredValue } from 'react';
import type {
  DepreciationDatabase,
  EvModelDepreciation,
  TransferType,
  PriceBasis,
} from '@/lib/getDepreciationData';
import {
  calculateDepreciation,
  simulateBatteryHealth,
  calculateSubsidyClawback,
  calculateTcoComparison,
} from '@/lib/getDepreciationData';

interface DepreciationCalculatorClientProps {
  initialDatabase: DepreciationDatabase;
}

const FALLBACK_MODEL: EvModelDepreciation = {
  id: 'fallback-ev',
  brand_id: 'generic',
  brand_name_en: 'Generic',
  brand_name_ko: '표준 EV',
  model_name: '표준 전기차',
  segment: '중형 CUV',
  msrp_krw_baseline: 55_000_000,
  avg_subsidy_krw: 7_000_000,
  net_purchase_price_krw: 48_000_000,
  battery_specs: {
    capacity_kwh: 77.4,
    chemistry: 'NCM 811',
    cell_supplier: '국내 배터리 3사',
    voltage_architecture: '800V',
  },
  warranty: {
    years: 10,
    km: 200_000,
    guarantee_retention_pct: 70,
  },
  factor_weights: {
    warranty_cliff: 1.0,
    chemistry_aging: 1.0,
    architecture_800v: 1.0,
    ota_maturity: 1.0,
    net_factor_adjustment: 1.0,
  },
  software_ota_level: 'FULL_STACK',
  resale_defense_tier: 'A',
  depreciation_curve: {
    year_1: { residual_pct_msrp: 75, depreciation_pct_msrp: 25, residual_pct_effective: 86, avg_used_price_krw: 41_250_000, annual_drop_pct: 25 },
    year_2: { residual_pct_msrp: 65, depreciation_pct_msrp: 35, residual_pct_effective: 74, avg_used_price_krw: 35_750_000, annual_drop_pct: 10 },
    year_3: { residual_pct_msrp: 55, depreciation_pct_msrp: 45, residual_pct_effective: 63, avg_used_price_krw: 30_250_000, annual_drop_pct: 10 },
    year_4: { residual_pct_msrp: 47, depreciation_pct_msrp: 53, residual_pct_effective: 54, avg_used_price_krw: 25_850_000, annual_drop_pct: 8 },
    year_5: { residual_pct_msrp: 40, depreciation_pct_msrp: 60, residual_pct_effective: 46, avg_used_price_krw: 22_000_000, annual_drop_pct: 7 },
  },
  key_pros_resale: '데이터 동기화 대기 중',
  key_cons_resale: '데이터 동기화 대기 중',
};

const FALLBACK_REPLACEMENT_TIER = {
  tier_id: 'tier_2_standard',
  segment_name: '중형 CUV / 세단 (표준)',
  pack_size_kwh_nominal: 77.4,
  pack_size_range: '65~85 kWh',
  representative_models: ['아이오닉 5', 'EV6', 'Model Y'],
  costs: {
    new_pack_krw: 22_000_000,
    new_pack_usd: 16_500,
    reman_pack_krw: 14_000_000,
    reman_pack_usd: 10_500,
    labor_coolant_krw: 1_500_000,
    labor_coolant_usd: 1_125,
    total_new_installed_krw: 23_500_000,
    total_new_installed_usd: 17_625,
    total_reman_installed_krw: 15_500_000,
    total_reman_installed_usd: 11_625,
    cost_per_kwh_usd: 213,
  },
};

// Maximum bounded cache entries for Arrhenius kinetics battery simulation
const MAX_BATTERY_SIMULATION_CACHE_ENTRIES = 100;

export default function DepreciationCalculatorClient({
  initialDatabase,
}: DepreciationCalculatorClientProps) {
  // Defensive guard against empty/undefined models array
  const models = useMemo(() => {
    return Array.isArray(initialDatabase?.models) && initialDatabase.models.length > 0
      ? initialDatabase.models
      : [FALLBACK_MODEL];
  }, [initialDatabase?.models]);

  // ----------------------------------------------------
  // 1. STATE & USER SELECTIONS
  // ----------------------------------------------------
  const [selectedBrand, setSelectedBrand] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedModelId, setSelectedModelId] = useState<string>(
    models[0]?.id || 'model-3'
  );

  // Simulation Controls
  const [holdingYears, setHoldingYears] = useState<number>(3);
  const [annualMileageKm, setAnnualMileageKm] = useState<number>(15000);
  const [dcfcRatio, setDcfcRatio] = useState<number>(30); // 0 ~ 100%
  const [priceBasis, setPriceBasis] = useState<PriceBasis>('effective');
  const [customPriceInput, setCustomPriceInput] = useState<string | null>(null);
  const [winterSeason, setWinterSeason] = useState<boolean>(false);

  // Subsidy Clawback Controls
  const [heldMonths, setHeldMonths] = useState<number>(36); // default matches 3 years
  const [syncMonthsWithYears, setSyncMonthsWithYears] = useState<boolean>(true);
  const [transferType, setTransferType] = useState<TransferType>('intra');
  const [customLocalSubsidy, setCustomLocalSubsidy] = useState<number | null>(null);
  const [customNationalSubsidy, setCustomNationalSubsidy] = useState<number | null>(null);

  // TCO Controls
  const [iceDisplacementCc, setIceDisplacementCc] = useState<number>(1998); // 2.0L 중형 가솔린 기본
  const [chartViewMode, setChartViewMode] = useState<'price' | 'percentage'>('price');

  // Guard against zero/negative holding years for division
  const safeYears = Number.isFinite(holdingYears) && holdingYears > 0 ? holdingYears : 1;

  // ----------------------------------------------------
  // 2. MODEL LOOKUP & FILTERING
  // ----------------------------------------------------
  const selectedModel = useMemo(() => {
    return (
      models.find((m) => m.id === selectedModelId) ||
      models[0] ||
      FALLBACK_MODEL
    );
  }, [models, selectedModelId]);

  // Available brands
  const brands = useMemo(() => {
    const list = [
      { id: 'all', name_ko: '전체 브랜드', count: models.length },
    ];
    const map = new Map<string, { id: string; name_ko: string; count: number }>();
    for (const m of models) {
      const existing = map.get(m.brand_id);
      if (existing) {
        existing.count += 1;
      } else {
        map.set(m.brand_id, {
          id: m.brand_id,
          name_ko: m.brand_name_ko,
          count: 1,
        });
      }
    }
    return [...list, ...Array.from(map.values())];
  }, [models]);

  // Filtered models with deferred search to prevent typing stutter
  const deferredSearchQuery = useDeferredValue(searchQuery);
  const filteredModels = useMemo(() => {
    const q = deferredSearchQuery.trim().toLowerCase();
    return models.filter((m) => {
      const matchesBrand = selectedBrand === 'all' || m.brand_id === selectedBrand;
      const matchesSearch =
        !q ||
        m.model_name.toLowerCase().includes(q) ||
        m.brand_name_ko.toLowerCase().includes(q) ||
        m.brand_name_en.toLowerCase().includes(q) ||
        m.battery_specs.chemistry.toLowerCase().includes(q) ||
        m.segment.toLowerCase().includes(q);
      return matchesBrand && matchesSearch;
    });
  }, [models, selectedBrand, deferredSearchQuery]);

  // Effective Purchase Price Baseline
  const currentPurchasePrice = useMemo(() => {
    if (customPriceInput !== null && customPriceInput.trim() !== '') {
      const parsed = parseInt(customPriceInput, 10);
      if (!isNaN(parsed) && parsed > 0) {
        return parsed;
      }
    }
    return priceBasis === 'effective'
      ? selectedModel.net_purchase_price_krw
      : selectedModel.msrp_krw_baseline;
  }, [customPriceInput, priceBasis, selectedModel]);

  // Subsidy breakdown for selected model
  const defaultLocalSubsidy = useMemo(() => {
    return Math.round(selectedModel.avg_subsidy_krw * 0.45);
  }, [selectedModel]);

  const defaultNationalSubsidy = useMemo(() => {
    return Math.round(selectedModel.avg_subsidy_krw * 0.55);
  }, [selectedModel]);

  const effectiveLocalSubsidy =
    customLocalSubsidy !== null ? customLocalSubsidy : defaultLocalSubsidy;
  const effectiveNationalSubsidy =
    customNationalSubsidy !== null ? customNationalSubsidy : defaultNationalSubsidy;

  // Handle Model Selection
  const handleSelectModel = (model: EvModelDepreciation) => {
    setSelectedModelId(model.id);
    setCustomPriceInput(null);
    setCustomLocalSubsidy(null);
    setCustomNationalSubsidy(null);
  };

  // Sync heldMonths if sync is active
  const handleYearsChange = (years: number) => {
    setHoldingYears(years);
    if (syncMonthsWithYears) {
      setHeldMonths(Math.round(years * 12));
    }
  };

  // Keyboard navigation for Brand Tabs (WAI-ARIA APG pattern)
  const handleBrandTabKeyDown = (e: React.KeyboardEvent, currentIndex: number) => {
    const count = brands.length;
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
      const nextBrand = brands[nextIndex].id;
      setSelectedBrand(nextBrand);
      document.getElementById(`brand-tab-${nextBrand}`)?.focus();
    }
  };

  // ----------------------------------------------------
  // 3. CORE CALCULATIONS
  // ----------------------------------------------------
  // A. Depreciation Calculation
  const totalMileage = useMemo(() => holdingYears * annualMileageKm, [holdingYears, annualMileageKm]);

  const depResult = useMemo(() => {
    return calculateDepreciation({
      modelId: selectedModel.id,
      years: holdingYears,
      mileageKm: totalMileage,
      winterSeason,
      priceBasis,
      customPurchasePriceKrw: currentPurchasePrice,
    });
  }, [selectedModel.id, holdingYears, totalMileage, winterSeason, priceBasis, currentPurchasePrice]);

  // Multi-year comparison projection (1~5 years)
  // Decoupled base projection memoization prevents running 5 full depreciation models when only holdingYears steps
  const baseMultiYearProjection = useMemo(() => {
    const yearsArr = [1, 2, 3, 4, 5];
    return yearsArr.map((y) => {
      const dep = calculateDepreciation({
        modelId: selectedModel.id,
        years: y,
        mileageKm: y * annualMileageKm,
        winterSeason,
        priceBasis,
        customPurchasePriceKrw: currentPurchasePrice,
      });

      // EV Class Average residual rate benchmark
      const evClassAvgPct = Math.max(
        15,
        Math.round((80.5 - (y - 1) * 9.8 - (winterSeason ? 2 : 0)) * 10) / 10
      );
      const evClassAvgPrice = Math.round((currentPurchasePrice * evClassAvgPct) / 100);

      // ICE Gasoline benchmark residual rate (standard Korean market 1.6~2.0L sedan/SUV)
      const iceBenchmarkPct = Math.max(
        20,
        Math.round((82.0 - (y - 1) * 8.5) * 10) / 10
      );
      const iceBenchmarkPrice = Math.round((currentPurchasePrice * iceBenchmarkPct) / 100);

      return {
        year: y,
        evResidualPct: dep.adjustedResidualPct,
        evResidualPriceKrw: dep.estimatedResidualPriceKrw,
        evClassAvgPct,
        evClassAvgPrice,
        iceBenchmarkPct,
        iceBenchmarkPrice,
      };
    });
  }, [
    selectedModel.id,
    annualMileageKm,
    winterSeason,
    priceBasis,
    currentPurchasePrice,
  ]);

  const multiYearProjection = useMemo(() => {
    return baseMultiYearProjection.map((item) => ({
      ...item,
      isCurrent: item.year === Math.round(holdingYears),
    }));
  }, [baseMultiYearProjection, holdingYears]);

  // Heavy Arrhenius simulation cache to prevent re-running thermodynamic kinetics
  const batterySimulationCache = useRef<Map<string, ReturnType<typeof simulateBatteryHealth>>>(new Map());

  // B. Electrochemical Battery Health Simulation (Arrhenius kinetics)
  const batteryHealth = useMemo(() => {
    const dcfcRatioVal = dcfcRatio / 100;
    const ambientTempC = winterSeason ? -5 : 22;
    const cacheKey = `${selectedModel.id}_${selectedModel.battery_specs.chemistry}_${holdingYears}_${totalMileage}_${annualMileageKm}_${dcfcRatioVal}_${ambientTempC}_${selectedModel.battery_specs.capacity_kwh}`;

    const cached = batterySimulationCache.current.get(cacheKey);
    if (cached) {
      return cached;
    }

    const simResult = simulateBatteryHealth({
      modelId: selectedModel.id,
      chemistry: selectedModel.battery_specs.chemistry,
      years: holdingYears,
      totalKm: totalMileage,
      annualKm: annualMileageKm,
      dcfcRatio: dcfcRatioVal,
      storageSoc: 0.6,
      ambientTempC,
      packCapacityKwh: selectedModel.battery_specs.capacity_kwh,
    });

    // Bounded cache eviction: cap at 100 entries using FIFO eviction
    if (batterySimulationCache.current.size >= MAX_BATTERY_SIMULATION_CACHE_ENTRIES) {
      const oldestKey = batterySimulationCache.current.keys().next().value;
      if (oldestKey !== undefined) {
        batterySimulationCache.current.delete(oldestKey);
      }
    }

    batterySimulationCache.current.set(cacheKey, simResult);
    return simResult;
  }, [
    selectedModel.id,
    selectedModel.battery_specs.chemistry,
    selectedModel.battery_specs.capacity_kwh,
    holdingYears,
    totalMileage,
    annualMileageKm,
    dcfcRatio,
    winterSeason,
  ]);

  // Matching full tier replacement cost info (with USD)
  const replacementCostTier = useMemo(() => {
    const tiers = Array.isArray(initialDatabase?.battery_replacement_costs)
      ? initialDatabase.battery_replacement_costs
      : [];
    const matched = tiers.find(
      (t) => t.tier_id === batteryHealth.replacementCostEstimate.tierId
    );
    return matched || tiers[1] || tiers[0] || FALLBACK_REPLACEMENT_TIER;
  }, [initialDatabase?.battery_replacement_costs, batteryHealth.replacementCostEstimate.tierId]);

  // C. Statutory Subsidy Clawback Calculation
  const clawbackResult = useMemo(() => {
    return calculateSubsidyClawback(
      heldMonths,
      effectiveLocalSubsidy,
      transferType,
      effectiveNationalSubsidy
    );
  }, [heldMonths, effectiveLocalSubsidy, transferType, effectiveNationalSubsidy]);

  // D. 5-Year TCO Comparison
  const tcoResult = useMemo(() => {
    const slowRatio = (100 - dcfcRatio) / 100;
    return calculateTcoComparison(
      annualMileageKm,
      holdingYears,
      5.2, // EV efficiency baseline
      slowRatio,
      iceDisplacementCc
    );
  }, [annualMileageKm, holdingYears, dcfcRatio, iceDisplacementCc]);

  // ----------------------------------------------------
  // 4. PRESET SCENARIO HANDLERS
  // ----------------------------------------------------
  const applyPreset = (preset: 'commute' | 'business' | 'leisure' | 'earlySell') => {
    if (preset === 'commute') {
      setHoldingYears(3);
      setHeldMonths(36);
      setAnnualMileageKm(15000);
      setDcfcRatio(20);
      setWinterSeason(false);
      setTransferType('intra');
    } else if (preset === 'business') {
      setHoldingYears(4);
      setHeldMonths(48);
      setAnnualMileageKm(35000);
      setDcfcRatio(65);
      setWinterSeason(false);
      setTransferType('intra');
    } else if (preset === 'leisure') {
      setHoldingYears(2);
      setHeldMonths(24);
      setAnnualMileageKm(8000);
      setDcfcRatio(15);
      setWinterSeason(false);
      setTransferType('intra');
    } else if (preset === 'earlySell') {
      setHoldingYears(1.5);
      setHeldMonths(18);
      setAnnualMileageKm(15000);
      setDcfcRatio(30);
      setWinterSeason(false);
      setTransferType('inter');
    }
  };

  // ----------------------------------------------------
  // 5. HELPER BADGE RENDERERS
  // ----------------------------------------------------
  const getChemistryBadge = (chem: string) => {
    const upper = chem.toUpperCase();
    if (upper.includes('LFP')) {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-emerald-100 text-emerald-950 border border-emerald-400">
          LFP (인산철)
        </span>
      );
    }
    if (upper.includes('622')) {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-blue-100 text-blue-950 border border-blue-400">
          NCM 622 (중밀도)
        </span>
      );
    }
    if (upper.includes('NCMA')) {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-cyan-100 text-cyan-950 border border-cyan-400">
          NCMA (4원계)
        </span>
      );
    }
    if (upper.includes('NCA')) {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-amber-100 text-amber-950 border border-amber-400">
          NCA (고출력)
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-purple-100 text-purple-950 border border-purple-400">
        NCM 811 (하이니켈)
      </span>
    );
  };

  const getDefenseTierBadge = (tier: string) => {
    switch (tier) {
      case 'S':
        return (
          <span className="px-2 py-0.5 rounded text-xs font-bold bg-amber-400 text-slate-950 shadow-sm">
            Tier S (방어 최상)
          </span>
        );
      case 'A':
      case 'A-':
        return (
          <span className="px-2 py-0.5 rounded text-xs font-bold bg-emerald-900 text-white shadow-sm">
            Tier {tier} (우수)
          </span>
        );
      case 'B+':
      case 'B':
      case 'B-':
        return (
          <span className="px-2 py-0.5 rounded text-xs font-bold bg-blue-900 text-white shadow-sm">
            Tier {tier} (보통)
          </span>
        );
      case 'C+':
      case 'C':
        return (
          <span className="px-2 py-0.5 rounded text-xs font-bold bg-orange-900 text-white shadow-sm">
            Tier {tier} (주의)
          </span>
        );
      case 'D':
      default:
        return (
          <span className="px-2 py-0.5 rounded text-xs font-bold bg-red-900 text-white shadow-sm">
            Tier {tier} (위험)
          </span>
        );
    }
  };

  const getHealthGradeBadge = (grade: string) => {
    switch (grade) {
      case 'GRADE_A':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-950 border border-emerald-400">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse motion-reduce:animate-none" aria-hidden="true" />
            Grade A (최상급 / CPO 인증급)
          </span>
        );
      case 'GRADE_B':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-blue-100 text-blue-950 border border-blue-400">
            <span className="w-2 h-2 rounded-full bg-blue-500" aria-hidden="true" />
            Grade B (양호 / 정상 마모)
          </span>
        );
      case 'GRADE_C':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-950 border border-amber-400">
            <span className="w-2 h-2 rounded-full bg-amber-500" aria-hidden="true" />
            Grade C (경고 / 급속 열화 진입)
          </span>
        );
      case 'CRITICAL':
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-red-100 text-red-950 border border-red-400 animate-bounce motion-reduce:animate-none">
            <span className="w-2 h-2 rounded-full bg-red-600" aria-hidden="true" />
            Critical (수명 만료 / 배터리 교체 대상)
          </span>
        );
    }
  };

  // ----------------------------------------------------
  // 6. RENDER
  // ----------------------------------------------------
  return (
    <div className="space-y-8">
      {/* 1. MAIN HERO HEADER */}
      <header className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white rounded-2xl p-6 sm:p-8 shadow-xl border border-slate-800">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-2 max-w-3xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/20 text-blue-300 border border-blue-400/30 text-xs font-semibold tracking-wide uppercase">
              <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse motion-reduce:animate-none" aria-hidden="true" />
              2026 KOREA EV MARKET INTELLIGENCE
            </div>
            <h1 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold tracking-tight text-white">
              전기차 감가방어율 & 배터리 수명 계산기
            </h1>
            <p className="text-slate-300 text-sm sm:text-base leading-relaxed">
              엔카·케이카 실거래 시세, 국토교통부 등록 데이터, 화학 구조별(LFP·삼원계) 전기화학 열화 모델,
              대기환경보전법 제58조 2년 의무운행 보조금 환수율, 5개년 총소유비용(TCO) 통합 시뮬레이터입니다.
            </p>
          </div>

          <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4 text-right flex flex-col justify-center min-w-[200px]">
            <span className="text-xs text-slate-400 font-medium">분석 대상 모델</span>
            <span className="text-2xl font-black text-blue-400">15개 차종</span>
            <span className="text-xs text-slate-400 mt-1">8대 브랜드 (2026년식 포함)</span>
          </div>
        </div>

        {/* Quick Market Highlight Bar */}
        <div className="mt-6 pt-4 border-t border-slate-800 grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs text-slate-300">
          <div className="flex items-center gap-2 bg-slate-800/50 px-3 py-2 rounded-lg">
            <span className="text-emerald-400 font-bold">✓ 800V 프리미엄:</span>
            <span>E-GMP 18분 초고속 충전 차종 잔존가치 +3.5% 방어</span>
          </div>
          <div className="flex items-center gap-2 bg-slate-800/50 px-3 py-2 rounded-lg">
            <span className="text-amber-400 font-bold">⚠️ 워런티 클리프:</span>
            <span>배터리 보증 만료 2년 전부터 -6%~-14% 감가 가속</span>
          </div>
          <div className="flex items-center gap-2 bg-slate-800/50 px-3 py-2 rounded-lg">
            <span className="text-blue-400 font-bold">📋 법정 환수 규정:</span>
            <span>24개월 미만 관외 이전 시 지방비 70%~20% 반납 의무</span>
          </div>
        </div>
      </header>

      {/* 2. QUICK PRESET SELECTORS */}
      <section
        aria-label="시뮬레이션 프리셋 선택"
        className="bg-white rounded-xl p-4 sm:p-5 shadow-sm border border-slate-200"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-slate-800 flex items-center gap-1.5">
              <span>⚡</span> 빠른 시나리오 프리셋:
            </span>
            <span className="text-xs text-slate-600 hidden md:inline">
              운행 목적에 맞는 조건을 한 번에 세팅합니다
            </span>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => applyPreset('commute')}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-blue-50 hover:text-blue-700 text-slate-700 border border-slate-200 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              aria-label="🚗 출퇴근 표준 (3년/1.5만km): 연 1.5만km, 급속 20%, 3년 보유"
            >
              🚗 출퇴근 표준 (3년/1.5만km)
            </button>
            <button
              type="button"
              onClick={() => applyPreset('business')}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-blue-50 hover:text-blue-700 text-slate-700 border border-slate-200 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              aria-label="🚛 장거리 영업 (4년/3.5만km): 연 3.5만km, 급속 65%, 4년 보유"
            >
              🚛 장거리 영업 (4년/3.5만km)
            </button>
            <button
              type="button"
              onClick={() => applyPreset('leisure')}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-blue-50 hover:text-blue-700 text-slate-700 border border-slate-200 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              aria-label="🏖️ 주말 레저 (2년/8천km): 연 8천km, 급속 15%, 2년 보유"
            >
              🏖️ 주말 레저 (2년/8천km)
            </button>
            <button
              type="button"
              onClick={() => applyPreset('earlySell')}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-amber-50 hover:bg-amber-100 text-amber-900 border border-amber-300 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              aria-label="⚠️ 보조금 환수 점검 (18개월 보유): 18개월 보유, 관외 이전"
            >
              ⚠️ 보조금 환수 점검 (18개월 보유)
            </button>
          </div>
        </div>
      </section>

      {/* 3. VEHICLE SELECTOR SECTION (15 MODELS, 8 BRANDS) */}
      <section
        aria-label="차량 선택 섹션"
        className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 space-y-5"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-lg sm:text-xl font-bold text-slate-900 flex items-center gap-2">
              <span>🚘</span> 비교 분석 차량 선택
            </h2>
            <p className="text-xs sm:text-sm text-slate-600">
              국내 주요 15개 대표 EV 모델 (배터리 케미스트리, 전압 플랫폼, 워런티 기본 탑재)
            </p>
          </div>

          {/* Search box */}
          <div className="relative w-full sm:w-64">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="모델명, 제조사, 배터리 검색..."
              className="w-full px-3.5 py-2 pl-9 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-slate-50"
              aria-label="전기차 모델 검색창"
            />
            <span className="absolute left-3 top-2.5 text-slate-600 text-sm" aria-hidden="true">🔍</span>
          </div>
        </div>

        {/* Brand Tabs */}
        <div role="tablist" aria-label="브랜드별 필터 선택" className="flex flex-wrap gap-1.5 border-b border-slate-200 pb-3">
          {brands.map((b, idx) => {
            const isSelected = selectedBrand === b.id;
            return (
              <button
                key={b.id}
                id={`brand-tab-${b.id}`}
                type="button"
                role="tab"
                aria-selected={isSelected}
                aria-controls="panel-model-grid"
                tabIndex={isSelected ? 0 : -1}
                onKeyDown={(e) => handleBrandTabKeyDown(e, idx)}
                onClick={() => setSelectedBrand(b.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                  isSelected
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
                aria-label={`${b.name_ko} (${b.count}): ${b.name_ko} 모델 필터`}
              >
                {b.name_ko} ({b.count})
              </button>
            );
          })}
        </div>

        {/* Models Grid */}
        <div
          id="panel-model-grid"
          role="tabpanel"
          aria-labelledby={`brand-tab-${selectedBrand}`}
          tabIndex={0}
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 max-h-[380px] overflow-y-auto pr-1 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none"
        >
          {filteredModels.map((model) => {
            const isSelected = model.id === selectedModel.id;
            return (
              <button
                key={model.id}
                type="button"
                aria-pressed={isSelected}
                onClick={() => handleSelectModel(model)}
                className={`text-left p-3.5 rounded-xl border transition relative flex flex-col justify-between focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                  isSelected
                    ? 'border-blue-600 bg-blue-50/60 ring-2 ring-blue-500/20 shadow-sm'
                    : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between gap-1 mb-1">
                    <span className="text-xs font-semibold text-slate-600">
                      {model.brand_name_ko} ({model.brand_name_en})
                    </span>
                    {getDefenseTierBadge(model.resale_defense_tier)}
                  </div>

                  <div className="text-sm font-bold text-slate-900 line-clamp-1">
                    {model.model_name}
                  </div>
                  <div className="text-xs text-slate-600 mb-2">{model.segment}</div>

                  <div className="flex flex-wrap items-center gap-1.5 mb-2">
                    {getChemistryBadge(model.battery_specs.chemistry)}
                    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-semibold bg-slate-100 text-slate-900 border border-slate-300">
                      {model.battery_specs.capacity_kwh} kWh
                    </span>
                    <span
                      className={`inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-bold border ${
                        model.battery_specs.voltage_architecture === '800V'
                          ? 'bg-emerald-100 text-emerald-950 border-emerald-400'
                          : 'bg-slate-100 text-slate-900 border-slate-300'
                      }`}
                    >
                      {model.battery_specs.voltage_architecture}
                    </span>
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
                  <div>
                    <span className="text-slate-600">출고가:</span>{' '}
                    <span className="font-semibold text-slate-700">
                      {(model.msrp_krw_baseline / 10000).toLocaleString()}만원
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-600">실구매:</span>{' '}
                    <span className="font-bold text-blue-700">
                      {(model.net_purchase_price_krw / 10000).toLocaleString()}만원
                    </span>
                  </div>
                </div>

                {isSelected && (
                  <div className="absolute -top-1.5 -right-1.5 bg-blue-600 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold shadow">
                    ✓
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </section>

      {/* 4. SIMULATION CONTROLS (SLIDERS & SELECTORS) */}
      <section
        aria-label="시뮬레이션 제어 슬라이더"
        className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 space-y-6"
      >
        <div className="border-b border-slate-200 pb-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h2 className="text-lg sm:text-xl font-bold text-slate-900 flex items-center gap-2">
              <span>⚙️</span> 정밀 시뮬레이션 제어기
            </h2>
            <p className="text-xs sm:text-sm text-slate-600">
              보유 기간, 연간 주행거리, 급속 충전 비율 및 실구매가격을 조정하여 잔존가치와 배터리 수명을 실시간 예측합니다.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-xs font-semibold text-slate-700 cursor-pointer bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-200">
              <input
                type="checkbox"
                checked={winterSeason}
                onChange={(e) => setWinterSeason(e.target.checked)}
                className="w-4 h-4 rounded text-blue-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                aria-label="혹한기 저온 감가 및 열화 패널티 반영 여부"
              />
              <span>❄️ 혹한기(-5℃) 저온 패널티 반영</span>
            </label>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Slider 1: Holding Period */}
          <div className="space-y-2 bg-slate-50/70 p-4 rounded-xl border border-slate-200">
            <div className="flex items-center justify-between">
              <label htmlFor="holdingYearsInput" className="text-xs font-bold text-slate-700">
                보유 기간
              </label>
              <span className="text-sm font-extrabold text-blue-950 bg-blue-100 px-2 py-0.5 rounded">
                {holdingYears}년 ({Math.round(holdingYears * 12)}개월)
              </span>
            </div>
            <input
              id="holdingYearsInput"
              type="range"
              min="1"
              max="5"
              step="0.5"
              value={holdingYears}
              onChange={(e) => handleYearsChange(parseFloat(e.target.value))}
              className="w-full accent-blue-600 cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-lg"
              aria-label="차량 보유 기간 설정 (1년에서 5년)"
            />
            <div className="flex justify-between text-[11px] text-slate-600 px-0.5">
              <span>1년</span>
              <span>2년</span>
              <span>3년</span>
              <span>4년</span>
              <span>5년</span>
            </div>
            <div className="flex gap-1 pt-1">
              {[1, 2, 3, 4, 5].map((yr) => (
                <button
                  key={yr}
                  type="button"
                  onClick={() => handleYearsChange(yr)}
                  className={`flex-1 py-1 text-[11px] font-semibold rounded border transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                    holdingYears === yr
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-100'
                  }`}
                  aria-label={`${yr}년 보유 설정`}
                >
                  {yr}년
                </button>
              ))}
            </div>
          </div>

          {/* Slider 2: Annual Mileage */}
          <div className="space-y-2 bg-slate-50/70 p-4 rounded-xl border border-slate-200">
            <div className="flex items-center justify-between">
              <label htmlFor="annualMileageInput" className="text-xs font-bold text-slate-700">
                연간 주행거리
              </label>
              <span className="text-sm font-extrabold text-blue-950 bg-blue-100 px-2 py-0.5 rounded">
                {annualMileageKm.toLocaleString()} km/년
              </span>
            </div>
            <input
              id="annualMileageInput"
              type="range"
              min="5000"
              max="50000"
              step="1000"
              value={annualMileageKm}
              onChange={(e) => setAnnualMileageKm(parseInt(e.target.value, 10))}
              className="w-full accent-blue-600 cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-lg"
              aria-label="연간 주행거리 설정 (5,000km에서 50,000km)"
            />
            <div className="flex justify-between text-[11px] text-slate-600 px-0.5">
              <span>5천km</span>
              <span>2만km</span>
              <span>3.5만km</span>
              <span>5만km</span>
            </div>
            <div className="text-[11px] text-slate-600 text-center font-medium bg-white py-1 rounded border border-slate-200">
              총 누적: <strong className="text-slate-800">{totalMileage.toLocaleString()} km</strong>
            </div>
          </div>

          {/* Slider 3: DC Fast Charging (DCFC) Ratio */}
          <div className="space-y-2 bg-slate-50/70 p-4 rounded-xl border border-slate-200">
            <div className="flex items-center justify-between">
              <label htmlFor="dcfcRatioInput" className="text-xs font-bold text-slate-700">
                급속 충전(DCFC) 비율
              </label>
              <span
                className={`text-sm font-extrabold px-2 py-0.5 rounded ${
                  dcfcRatio > 60
                    ? 'bg-amber-100 text-amber-950'
                    : 'bg-blue-100 text-blue-950'
                }`}
              >
                {dcfcRatio}%
              </span>
            </div>
            <input
              id="dcfcRatioInput"
              type="range"
              min="0"
              max="100"
              step="5"
              value={dcfcRatio}
              onChange={(e) => setDcfcRatio(parseInt(e.target.value, 10))}
              className="w-full accent-blue-600 cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-lg"
              aria-label="급속 충전 비율 설정 (0%에서 100%)"
            />
            <div className="flex justify-between text-[11px] text-slate-600 px-0.5">
              <span>0% (완속전용)</span>
              <span>50%</span>
              <span>100% (급속전용)</span>
            </div>
            <div className="text-[11px] text-slate-600 text-center font-medium bg-white py-1 rounded border border-slate-200 flex justify-around">
              <span>완속 {100 - dcfcRatio}%</span>
              <span className="text-slate-300">|</span>
              <span className={dcfcRatio > 60 ? 'text-amber-800 font-bold' : ''}>
                급속 {dcfcRatio}%
              </span>
            </div>
          </div>

          {/* Control 4: Purchase Price Basis & Custom Input */}
          <div className="space-y-2 bg-slate-50/70 p-4 rounded-xl border border-slate-200">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-700">기준 가격 & 실구매가</span>
              <button
                type="button"
                onClick={() => setCustomPriceInput(null)}
                className="text-[11px] text-blue-600 hover:underline font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded outline-none"
                aria-label="기본값 복원: 차량 기본 가격으로 초기화"
              >
                기본값 복원
              </button>
            </div>

            <div className="flex rounded-lg overflow-hidden border border-slate-200 text-xs">
              <button
                type="button"
                aria-pressed={priceBasis === 'effective'}
                onClick={() => {
                  setPriceBasis('effective');
                  setCustomPriceInput(null);
                }}
                className={`flex-1 py-1 text-center font-semibold transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded outline-none ${
                  priceBasis === 'effective'
                    ? 'bg-blue-600 text-white'
                    : 'bg-white text-slate-600 hover:bg-slate-100'
                }`}
                aria-label="실구매가 (보조금): 보조금 반영 기준"
              >
                실구매가 (보조금)
              </button>
              <button
                type="button"
                aria-pressed={priceBasis === 'msrp'}
                onClick={() => {
                  setPriceBasis('msrp');
                  setCustomPriceInput(null);
                }}
                className={`flex-1 py-1 text-center font-semibold transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded outline-none ${
                  priceBasis === 'msrp'
                    ? 'bg-blue-600 text-white'
                    : 'bg-white text-slate-600 hover:bg-slate-100'
                }`}
                aria-label="출고가(MSRP): 신차 공식 출고가 기준"
              >
                출고가(MSRP)
              </button>
            </div>

            <div className="relative">
              <label htmlFor="customPriceInputField" className="sr-only">
                차량 구매 가격 직접 입력
              </label>
              <input
                id="customPriceInputField"
                type="number"
                step="100000"
                value={customPriceInput !== null ? customPriceInput : currentPurchasePrice}
                onChange={(e) => {
                  setCustomPriceInput(e.target.value);
                }}
                className="w-full px-3 py-1.5 rounded-lg border border-slate-300 text-xs font-bold text-right pr-8 bg-white focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                aria-label="차량 구매 가격 직접 입력 (원 단위)"
              />
              <span className="absolute right-3 top-2 text-xs text-slate-600">원</span>
            </div>

            <div className="text-[11px] text-slate-600 text-center">
              환산: <strong>{(currentPurchasePrice / 10000).toLocaleString()} 만 원</strong>
            </div>
          </div>
        </div>
      </section>

      {/* 5. MULTI-YEAR DEPRECIATION CHART & RESALE VALUE PROJECTION */}
      <section
        aria-label="감가방어율 차트 및 잔존가치 프로젝션"
        className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 space-y-6"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-black text-slate-900">
                {selectedModel.brand_name_ko} {selectedModel.model_name}
              </h2>
              {getDefenseTierBadge(selectedModel.resale_defense_tier)}
            </div>
            <p className="text-xs sm:text-sm text-slate-600 mt-0.5">
              {holdingYears}년차({totalMileage.toLocaleString()} km 주행) 예상 중고차 거래 시세 및 연차별 감가 추이
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-600 font-medium hidden sm:inline">차트 보기:</span>
            <div className="inline-flex rounded-lg border border-slate-200 overflow-hidden text-xs">
              <button
                type="button"
                onClick={() => setChartViewMode('price')}
                className={`px-3 py-1.5 font-semibold transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded outline-none ${
                  chartViewMode === 'price'
                    ? 'bg-blue-600 text-white'
                    : 'bg-white text-slate-600 hover:bg-slate-100'
                }`}
                aria-label="예상 시세 (만원): 금액 단위로 차트 보기"
              >
                예상 시세 (만원)
              </button>
              <button
                type="button"
                onClick={() => setChartViewMode('percentage')}
                className={`px-3 py-1.5 font-semibold transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded outline-none ${
                  chartViewMode === 'percentage'
                    ? 'bg-blue-600 text-white'
                    : 'bg-white text-slate-600 hover:bg-slate-100'
                }`}
                aria-label="잔존가치율 (%): 신차 대비 잔존가치율 단위로 차트 보기"
              >
                잔존가치율 (%)
              </button>
            </div>
          </div>
        </div>

        {/* 4 Key KPI Result Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          {/* KPI 1: Estimated Resale Price */}
          <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 rounded-xl p-4">
            <div className="text-xs font-bold text-blue-800">
              {holdingYears}년차 예상 잔존 시세
            </div>
            <div className="text-xl sm:text-2xl font-black text-blue-900 mt-1">
              {(depResult.estimatedResidualPriceKrw / 10000).toLocaleString()}{' '}
              <span className="text-sm font-semibold text-blue-700">만 원</span>
            </div>
            <div className="text-[11px] text-blue-800 font-semibold mt-1">
              신차 대비 {depResult.adjustedResidualPct}% 잔존
            </div>
          </div>

          {/* KPI 2: Total Depreciation Amount */}
          <div className="bg-gradient-to-br from-slate-50 to-rose-50 border border-slate-200 rounded-xl p-4">
            <div className="text-xs font-bold text-slate-700">누적 감가 손실액</div>
            <div className="text-xl sm:text-2xl font-black text-rose-600 mt-1">
              -{(depResult.depreciationAmountKrw / 10000).toLocaleString()}{' '}
              <span className="text-sm font-semibold text-rose-700">만 원</span>
            </div>
            <div className="text-[11px] text-slate-600 mt-1">
              연평균 감가: -{Math.round(depResult.depreciationAmountKrw / safeYears / 10000).toLocaleString()} 만 원/년
            </div>
          </div>

          {/* KPI 3: VS EV Class Average */}
          <div className="bg-gradient-to-br from-slate-50 to-emerald-50 border border-slate-200 rounded-xl p-4">
            <div className="text-xs font-bold text-slate-700">전기차 전체 평균 대비</div>
            <div className="text-xl sm:text-2xl font-black text-emerald-700 mt-1">
              {depResult.adjustedResidualPct >= 58 ? '+' : ''}
              {(depResult.adjustedResidualPct - 58).toFixed(1)}%
            </div>
            <div className="text-[11px] text-emerald-800 mt-1">
              동급 세그먼트 중 방어력 {depResult.defenseTier}등급
            </div>
          </div>

          {/* KPI 4: VS ICE Benchmark */}
          <div className="bg-gradient-to-br from-slate-50 to-amber-50 border border-slate-200 rounded-xl p-4">
            <div className="text-xs font-bold text-slate-700">동급 내연기관(가솔린) 대비</div>
            <div className="text-xl sm:text-2xl font-black text-amber-800 mt-1">
              {depResult.adjustedResidualPct >= 64 ? '+' : ''}
              {(depResult.adjustedResidualPct - 64).toFixed(1)}%
            </div>
            <div className="text-[11px] text-slate-600 mt-1">
              {depResult.adjustedResidualPct >= 64
                ? '내연기관보다 뛰어난 감가 방어'
                : '초기 배터리 불확실성 감가 반영'}
            </div>
          </div>
        </div>

        {/* Interactive SVG Projection Chart */}
        <div className="bg-slate-900 rounded-2xl p-5 sm:p-6 text-white space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1.5 font-semibold text-blue-400">
                <span className="w-3 h-3 rounded bg-blue-500 inline-block" />
                {selectedModel.model_name} (선택 차량)
              </span>
              <span className="flex items-center gap-1.5 font-semibold text-emerald-400">
                <span className="w-3 h-3 rounded bg-emerald-500 inline-block" />
                전기차 전체 평균
              </span>
              <span className="flex items-center gap-1.5 font-semibold text-slate-400">
                <span className="w-3 h-3 rounded bg-slate-500 inline-block" />
                동급 내연기관(가솔린)
              </span>
            </div>
            <div className="text-slate-400">
              * 기준 연간 15,000km 및 실거래 반영
            </div>
          </div>

          {/* SVG Chart */}
          <div
            tabIndex={0}
            aria-label="연차별 잔존가치 프로젝션 비교 차트 스크롤 영역"
            className="w-full overflow-x-auto focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >
            <svg
              viewBox="0 0 700 280"
              className="w-full min-w-[550px] h-64 select-none"
              role="img"
              aria-label="연차별 잔존가치 프로젝션 비교 차트"
            >
              {/* Grid Lines */}
              {[0, 1, 2, 3, 4].map((i) => {
                const y = 30 + i * 50;
                const pct = 100 - i * 20;
                const priceVal = Math.round((currentPurchasePrice * pct) / 100 / 10000);
                return (
                  <g key={i}>
                    <line
                      x1="60"
                      y1={y}
                      x2="680"
                      y2={y}
                      stroke="#334155"
                      strokeDasharray="4 4"
                      strokeWidth="1"
                    />
                    <text
                      x="50"
                      y={y + 4}
                      textAnchor="end"
                      fill="#94a3b8"
                      fontSize="11"
                    >
                      {chartViewMode === 'price' ? `${priceVal}만` : `${pct}%`}
                    </text>
                  </g>
                );
              })}

              {/* Bars or Points for 5 Years */}
              {multiYearProjection.map((pt, idx) => {
                const groupX = 100 + idx * 115;
                const isSelectedYear = pt.isCurrent;

                // Heights for price or percentage
                // Max: 100%, 0 to 200px (y from 230 to 30)
                const getY = (val: number, maxVal: number) => {
                  if (!Number.isFinite(val) || !Number.isFinite(maxVal) || maxVal <= 0) {
                    return 230;
                  }
                  const ratio = Math.max(0, Math.min(1, val / maxVal));
                  return 230 - ratio * 200;
                };

                const maxRef = chartViewMode === 'price' ? currentPurchasePrice : 100;
                const evVal =
                  chartViewMode === 'price' ? pt.evResidualPriceKrw : pt.evResidualPct;
                const evAvgVal =
                  chartViewMode === 'price' ? pt.evClassAvgPrice : pt.evClassAvgPct;
                const iceVal =
                  chartViewMode === 'price' ? pt.iceBenchmarkPrice : pt.iceBenchmarkPct;

                const yEv = getY(evVal, maxRef);
                const yEvAvg = getY(evAvgVal, maxRef);
                const yIce = getY(iceVal, maxRef);

                const barWidth = 22;

                return (
                  <g key={pt.year}>
                    {/* Background Highlight for Currently Selected Year */}
                    {isSelectedYear && (
                      <rect
                        x={groupX - 35}
                        y="20"
                        width="90"
                        height="225"
                        rx="8"
                        fill="#1e293b"
                        stroke="#3b82f6"
                        strokeWidth="1.5"
                        opacity="0.8"
                      />
                    )}

                    {/* Bar 1: Selected EV */}
                    <rect
                      x={groupX - 30}
                      y={yEv}
                      width={barWidth}
                      height={Math.max(2, 230 - yEv)}
                      rx="4"
                      fill={isSelectedYear ? '#3b82f6' : '#2563eb'}
                      className="transition-all duration-300 hover:opacity-90"
                    />
                    <text
                      x={groupX - 19}
                      y={Math.max(25, yEv - 6)}
                      textAnchor="middle"
                      fill="#60a5fa"
                      fontSize="10"
                      fontWeight="bold"
                    >
                      {chartViewMode === 'price'
                        ? `${Math.round(pt.evResidualPriceKrw / 10000)}`
                        : `${pt.evResidualPct.toFixed(0)}%`}
                    </text>

                    {/* Bar 2: EV Class Average */}
                    <rect
                      x={groupX - 4}
                      y={yEvAvg}
                      width={barWidth}
                      height={Math.max(2, 230 - yEvAvg)}
                      rx="4"
                      fill="#10b981"
                      className="transition-all duration-300 hover:opacity-90"
                    />

                    {/* Bar 3: ICE Benchmark */}
                    <rect
                      x={groupX + 22}
                      y={yIce}
                      width={barWidth}
                      height={Math.max(2, 230 - yIce)}
                      rx="4"
                      fill="#64748b"
                      className="transition-all duration-300 hover:opacity-90"
                    />

                    {/* X-axis Year Label */}
                    <text
                      x={groupX + 8}
                      y="255"
                      textAnchor="middle"
                      fill={isSelectedYear ? '#60a5fa' : '#cbd5e1'}
                      fontSize="12"
                      fontWeight={isSelectedYear ? 'bold' : 'normal'}
                    >
                      {pt.year}년차 {isSelectedYear && '★'}
                    </text>
                  </g>
                );
              })}

              {/* Bottom Baseline */}
              <line x1="60" y1="230" x2="680" y2="230" stroke="#475569" strokeWidth="2" />
            </svg>

            {/* Screen Reader Accessible Data Table Alternative */}
            <div className="sr-only">
              <table aria-label="연차별 잔존가치 프로젝션 데이터 표">
                <caption>{selectedModel.model_name} 연차별 예상 잔존 시세 및 비교치</caption>
                <thead>
                  <tr>
                    <th scope="col">보유 연차</th>
                    <th scope="col">선택 차량 잔존 시세</th>
                    <th scope="col">선택 차량 잔존율</th>
                    <th scope="col">전기차 전체 평균 잔존율</th>
                    <th scope="col">동급 내연기관 잔존율</th>
                  </tr>
                </thead>
                <tbody>
                  {multiYearProjection.map((pt) => (
                    <tr key={pt.year}>
                      <th scope="row">{pt.year}년차</th>
                      <td>{Math.round(pt.evResidualPriceKrw / 10000).toLocaleString()}만 원</td>
                      <td>{pt.evResidualPct.toFixed(1)}%</td>
                      <td>{pt.evClassAvgPct.toFixed(1)}%</td>
                      <td>{pt.iceBenchmarkPct.toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Factor Breakdown Chips */}
          <div className="pt-2 border-t border-slate-800 grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs text-slate-300">
            <div className="bg-slate-800/80 p-2.5 rounded-lg">
              <span className="text-slate-400 block text-[11px]">워런티 클리프 영향</span>
              <strong
                className={
                  depResult.factorAdjustments.warrantyCliffPenalty < 0
                    ? 'text-rose-400'
                    : 'text-emerald-400'
                }
              >
                {depResult.factorAdjustments.warrantyCliffPenalty}%
              </strong>
            </div>
            <div className="bg-slate-800/80 p-2.5 rounded-lg">
              <span className="text-slate-400 block text-[11px]">배터리 화학 노화 보정</span>
              <strong className="text-emerald-400">
                +{depResult.factorAdjustments.batteryChemistryBonus}%
              </strong>
            </div>
            <div className="bg-slate-800/80 p-2.5 rounded-lg">
              <span className="text-slate-400 block text-[11px]">800V/400V 플랫폼</span>
              <strong
                className={
                  depResult.factorAdjustments.architectureAdjustment >= 0
                    ? 'text-emerald-400'
                    : 'text-amber-400'
                }
              >
                {depResult.factorAdjustments.architectureAdjustment >= 0 ? '+' : ''}
                {depResult.factorAdjustments.architectureAdjustment}%
              </strong>
            </div>
            <div className="bg-slate-800/80 p-2.5 rounded-lg">
              <span className="text-slate-400 block text-[11px]">풀스택 OTA 성숙도</span>
              <strong
                className={
                  depResult.factorAdjustments.otaAdjustment >= 0
                    ? 'text-emerald-400'
                    : 'text-amber-400'
                }
              >
                {depResult.factorAdjustments.otaAdjustment >= 0 ? '+' : ''}
                {depResult.factorAdjustments.otaAdjustment}%
              </strong>
            </div>
            <div className="bg-slate-800/80 p-2.5 rounded-lg">
              <span className="text-slate-400 block text-[11px]">주행거리 마일리지 편차</span>
              <strong
                className={
                  depResult.factorAdjustments.mileageAdjustment >= 0
                    ? 'text-emerald-400'
                    : 'text-rose-400'
                }
              >
                {depResult.factorAdjustments.mileageAdjustment >= 0 ? '+' : ''}
                {depResult.factorAdjustments.mileageAdjustment}%
              </strong>
            </div>
          </div>
        </div>

        {/* Pros and Cons for Resale Defense */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
          <div className="bg-emerald-50/60 border border-emerald-200 rounded-xl p-4">
            <h3 className="text-xs font-bold text-emerald-900 flex items-center gap-1.5 mb-1.5">
              <span>👍</span> 중고차 잔존가치 방어 강점 (Pros)
            </h3>
            <p className="text-xs sm:text-sm text-emerald-800 leading-relaxed">
              {depResult.keyPros}
            </p>
          </div>

          <div className="bg-rose-50/60 border border-rose-200 rounded-xl p-4">
            <h3 className="text-xs font-bold text-rose-900 flex items-center gap-1.5 mb-1.5">
              <span>⚠️</span> 주요 감가 하방 리스크 요인 (Cons)
            </h3>
            <p className="text-xs sm:text-sm text-rose-800 leading-relaxed">
              {depResult.keyCons}
            </p>
          </div>
        </div>
      </section>

      {/* 6. BATTERY HEALTH DEGRADATION & RISK ANALYSIS (SoH & REPLACEMENT COSTS) */}
      <section
        aria-label="배터리 잔여 수명 및 교체 리스크 분석"
        className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 space-y-6"
      >
        <div className="border-b border-slate-200 pb-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h2 className="text-lg sm:text-xl font-bold text-slate-900 flex items-center gap-2">
              <span>🔋</span> 배터리 수명(SoH) 열화 및 교체비용 리스크
            </h2>
            <p className="text-xs sm:text-sm text-slate-600">
              아레니우스(Arrhenius) 캘린더 노화 및 DCFC 급속 충전 기계적 피로도 결합 시뮬레이션
            </p>
          </div>

          <div>{getHealthGradeBadge(batteryHealth.grade)}</div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
          {/* Radial SoH Gauge Card (4 Cols) */}
          <div className="lg:col-span-4 bg-slate-900 text-white rounded-2xl p-6 text-center space-y-4 shadow-lg border border-slate-800">
            <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">
              State of Health (SoH)
            </div>

            <div
              role="progressbar"
              aria-valuenow={Math.round(batteryHealth.sohPct * 10) / 10}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="배터리 잔존 성능"
              aria-valuetext={`${batteryHealth.sohPct.toFixed(1)}%`}
              className="relative w-44 h-44 mx-auto flex items-center justify-center"
            >
              <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100" aria-hidden="true">
                {/* Track Circle */}
                <circle
                  cx="50"
                  cy="50"
                  r="42"
                  stroke="#334155"
                  strokeWidth="10"
                  fill="transparent"
                />
                {/* Value Circle */}
                <circle
                  cx="50"
                  cy="50"
                  r="42"
                  stroke={
                    batteryHealth.sohPct >= 90
                      ? '#10b981'
                      : batteryHealth.sohPct >= 80
                      ? '#3b82f6'
                      : batteryHealth.sohPct >= 70
                      ? '#f59e0b'
                      : '#ef4444'
                  }
                  strokeWidth="10"
                  fill="transparent"
                  strokeDasharray="263.89"
                  strokeDashoffset={263.89 * (1 - batteryHealth.sohPct / 100)}
                  strokeLinecap="round"
                  className="transition-all duration-700 ease-out"
                />
              </svg>

              <div className="absolute flex flex-col items-center justify-center">
                <span className="text-3xl sm:text-4xl font-black tracking-tight text-white">
                  {batteryHealth.sohPct.toFixed(1)}%
                </span>
                <span className="text-xs text-slate-400 font-medium">잔여 용량</span>
              </div>
            </div>

            <div className="text-xs text-slate-300 bg-slate-800/80 p-2.5 rounded-xl border border-slate-700 leading-relaxed">
              {batteryHealth.actionRecommendation}
            </div>
          </div>

          {/* Degradation Metrics Grid (8 Cols) */}
          <div className="lg:col-span-8 space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200">
                <span className="text-xs text-slate-600 font-medium block">캘린더 노화 (시간/온도)</span>
                <span className="text-lg font-bold text-slate-800">
                  -{batteryHealth.calendarLossPct}%
                </span>
              </div>
              <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200">
                <span className="text-xs text-slate-600 font-medium block">사이클 피로 (충방전)</span>
                <span className="text-lg font-bold text-slate-800">
                  -{batteryHealth.cyclicLossPct}%
                </span>
              </div>
              <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200">
                <span className="text-xs text-slate-600 font-medium block">등가 완전충전 사이클</span>
                <span className="text-lg font-bold text-blue-600">
                  {batteryHealth.equivalentFullCycles} 회
                </span>
              </div>
              <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200">
                <span className="text-xs text-slate-600 font-medium block">혹한기 주행 유지율</span>
                <span className="text-lg font-bold text-slate-800">
                  {batteryHealth.winterRangeRetentionPct}%
                </span>
              </div>
            </div>

            {/* Warranty Status Box */}
            <div
              className={`p-4 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                depResult.warrantyStatus.isExpired
                  ? 'bg-red-50 border-red-300 text-red-950'
                  : depResult.warrantyStatus.isApproachingCliff
                  ? 'bg-amber-50 border-amber-300 text-amber-950'
                  : 'bg-emerald-50 border-emerald-300 text-emerald-950'
              }`}
            >
              <div>
                <div className="text-xs font-bold uppercase tracking-wide">
                  제조사 공식 배터리 보증 상태: {selectedModel.warranty.years}년 /{' '}
                  {selectedModel.warranty.km.toLocaleString()} km
                </div>
                <div className="text-sm font-semibold mt-0.5">
                  {depResult.warrantyStatus.isExpired ? (
                    <span className="text-red-700 font-bold">
                      🚨 보증 기간/주행거리 만료 — 배터리 고장 시 전액 차주 자부담 리스크
                    </span>
                  ) : depResult.warrantyStatus.isApproachingCliff ? (
                    <span className="text-amber-800 font-bold">
                      ⚠️ 워런티 클리프 진입: 잔여 {depResult.warrantyStatus.remainingYears}년 /{' '}
                      {depResult.warrantyStatus.remainingKm.toLocaleString()} km
                    </span>
                  ) : (
                    <span className="text-emerald-800">
                      ✅ 보증 유효 안전 구간 (잔여 {depResult.warrantyStatus.remainingYears}년 /{' '}
                      {depResult.warrantyStatus.remainingKm.toLocaleString()} km)
                    </span>
                  )}
                </div>
              </div>

              <div className="text-right text-xs">
                <span className="text-slate-600">보증 기준 잔존율:</span>{' '}
                <strong className="text-slate-900 font-bold">
                  {selectedModel.warranty.guarantee_retention_pct}% 이상
                </strong>
              </div>
            </div>

            {/* Estimated Battery Replacement Costs (KRW and USD) */}
            <div className="bg-slate-900 text-white rounded-xl p-4 border border-slate-800 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-300 flex items-center gap-1.5">
                  <span>🛠️</span> 공식 배터리 팩 교체 비용 견적 ({replacementCostTier.segment_name})
                </span>
                <span className="text-[11px] text-slate-400">
                  용량 {selectedModel.battery_specs.capacity_kwh} kWh 기준
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                <div className="bg-slate-800 p-3 rounded-lg border border-slate-700">
                  <span className="text-slate-400 block">순정 신품 팩 (공임·냉각수 포함)</span>
                  <span className="text-base font-extrabold text-white block mt-1">
                    {(replacementCostTier.costs.total_new_installed_krw / 10000).toLocaleString()}만 원
                  </span>
                  <span className="text-[11px] text-blue-400 font-medium">
                    ${replacementCostTier.costs.total_new_installed_usd.toLocaleString()} USD
                  </span>
                </div>

                <div className="bg-slate-800 p-3 rounded-lg border border-slate-700">
                  <span className="text-slate-400 block">공식 재제조(Reman) 팩</span>
                  <span className="text-base font-extrabold text-slate-200 block mt-1">
                    {replacementCostTier.costs.total_reman_installed_krw
                      ? `${(replacementCostTier.costs.total_reman_installed_krw / 10000).toLocaleString()}만 원`
                      : '공급 불가'}
                  </span>
                  <span className="text-[11px] text-slate-400 font-medium">
                    {replacementCostTier.costs.total_reman_installed_usd
                      ? `$${replacementCostTier.costs.total_reman_installed_usd.toLocaleString()} USD`
                      : '-'}
                  </span>
                </div>

                <div className="bg-slate-800 p-3 rounded-lg border border-slate-700">
                  <span className="text-slate-400 block">순수 공임 및 냉각수 충진</span>
                  <span className="text-base font-extrabold text-slate-300 block mt-1">
                    {(replacementCostTier.costs.labor_coolant_krw / 10000).toLocaleString()}만 원
                  </span>
                  <span className="text-[11px] text-slate-400 font-medium">
                    ${replacementCostTier.costs.labor_coolant_usd.toLocaleString()} USD
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 7. STATUTORY 2-YEAR SUBSIDY CLAWBACK CALCULATOR (대기환경보전법 제58조) */}
      <section
        aria-label="법정 2년 보조금 환수액 계산기"
        className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 space-y-6"
      >
        <div className="border-b border-slate-200 pb-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg sm:text-xl font-bold text-slate-900">
                ⚖️ 2년 의무운행기간 보조금 환수 계산기
              </h2>
              <span className="text-xs px-2 py-0.5 rounded bg-blue-100 text-blue-950 font-bold">
                법정 규정
              </span>
            </div>
            <p className="text-xs sm:text-sm text-slate-600">
              대기환경보전법 제58조 제3항 및 동법 시행규칙 제79조의4 [별표 21의2] 회수요율표 적용
            </p>
          </div>

          <div className="text-xs text-slate-600">
            의무운행: <strong>24개월 (2년)</strong>
          </div>
        </div>

        {/* Real-time Status Alert Banner */}
        <div
          className={`p-4 rounded-xl border flex items-start sm:items-center gap-3 ${
            clawbackResult.isExempt
              ? 'bg-emerald-50 border-emerald-300 text-emerald-950'
              : 'bg-amber-50 border-amber-300 text-amber-950'
          }`}
        >
          <span className="text-2xl">{clawbackResult.isExempt ? '✅' : '⚠️'}</span>
          <div className="space-y-0.5 flex-1 text-xs sm:text-sm">
            <div className="font-bold">
              {clawbackResult.isExempt
                ? '보조금 환수 면제 대상 (0원 납부)'
                : `보조금 환수 대상 고지 — 회수요율 ${(clawbackResult.effectiveClawbackRate * 100).toFixed(0)}% 적용`}
            </div>
            <p className="text-slate-600 leading-relaxed">{clawbackResult.explanation}</p>
          </div>
        </div>

        {/* Clawback Controls */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Control 1: Held Months */}
          <div className="space-y-2 bg-slate-50 p-4 rounded-xl border border-slate-200">
            <div className="flex items-center justify-between">
              <label htmlFor="heldMonthsInput" className="text-xs font-bold text-slate-700">
                실운행 보유 개월 수
              </label>
              <span
                className={`text-xs font-extrabold px-2 py-0.5 rounded ${
                  heldMonths >= 24
                    ? 'bg-emerald-100 text-emerald-950'
                    : 'bg-amber-100 text-amber-950'
                }`}
              >
                {heldMonths}개월 ({heldMonths >= 24 ? '의무기간 완료' : `잔여 ${24 - heldMonths}개월`})
              </span>
            </div>
            <input
              id="heldMonthsInput"
              type="range"
              min="0"
              max="36"
              step="1"
              value={heldMonths}
              onChange={(e) => {
                setSyncMonthsWithYears(false);
                setHeldMonths(parseInt(e.target.value, 10));
              }}
              className="w-full accent-blue-600 cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-lg"
              aria-label="보조금 의무운행 기간 중 보유 개월 수 설정"
            />
            <div className="flex justify-between text-[11px] text-slate-600">
              <span>0개월</span>
              <span>12개월(1년)</span>
              <span>24개월(의무만료)</span>
              <span>36개월</span>
            </div>

            <div className="pt-2 flex justify-between items-center text-xs">
              <button
                type="button"
                onClick={() => {
                  setSyncMonthsWithYears(true);
                  setHeldMonths(Math.round(holdingYears * 12));
                }}
                className="text-blue-600 hover:underline text-[11px] font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded outline-none"
                aria-label={`보유 기간(${holdingYears}년)과 동기화: 상단 연수와 개월 수 맞춤`}
              >
                보유 기간({holdingYears}년)과 동기화
              </button>
              <span className="text-slate-600 font-medium">구간: {clawbackResult.tierLabel}</span>
            </div>
          </div>

          {/* Control 2: Transfer Type Selector */}
          <fieldset className="space-y-2 bg-slate-50 p-4 rounded-xl border border-slate-200">
            <legend className="sr-only">이전 / 매매 유형 선택</legend>
            <span className="text-xs font-bold text-slate-700 block" aria-hidden="true">이전 / 매매 유형 선택</span>
            <div className="space-y-1.5">
              {[
                {
                  id: 'intra' as TransferType,
                  title: '관내 이전 (동일 지자체)',
                  desc: '매수인 잔여기간 자동 승계 → 환수금 0원 (면제)',
                },
                {
                  id: 'inter' as TransferType,
                  title: '관외 이전 (타 지자체)',
                  desc: '지방비 보조금만 회수요율 적용 환수 (국비 면제)',
                },
                {
                  id: 'export' as TransferType,
                  title: '해외 수출 말소',
                  desc: '대기질 개선 취지 상실로 국비+지방비 전액 환수',
                },
              ].map((item) => (
                <label
                  key={item.id}
                  className={`flex items-start gap-2 p-2 rounded-lg border cursor-pointer text-xs transition ${
                    transferType === item.id
                      ? 'bg-blue-50 border-blue-500 text-blue-950 font-semibold'
                      : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-100'
                  }`}
                >
                  <input
                    type="radio"
                    name="transferTypeRadio"
                    checked={transferType === item.id}
                    onChange={() => setTransferType(item.id)}
                    className="mt-0.5 text-blue-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                    aria-label={item.title}
                  />
                  <div>
                    <div className="font-bold">{item.title}</div>
                    <div className="text-[11px] text-slate-700">{item.desc}</div>
                  </div>
                </label>
              ))}
            </div>
          </fieldset>

          {/* Control 3: Subsidy Input & Total Clawback Result */}
          <div className="bg-slate-900 text-white p-5 rounded-xl border border-slate-800 flex flex-col justify-between space-y-4">
            <div className="space-y-2">
              <span className="text-xs font-bold text-slate-300">보조금 지원금액 입력</span>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <label htmlFor="nationalSubsidyInput" className="text-slate-400 block text-[11px]">
                    국비 보조금
                  </label>
                  <input
                    id="nationalSubsidyInput"
                    type="number"
                    step="100000"
                    value={effectiveNationalSubsidy}
                    onChange={(e) => setCustomNationalSubsidy(parseInt(e.target.value, 10) || 0)}
                    className="w-full px-2 py-1 rounded bg-slate-800 border border-slate-700 text-right font-semibold text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded outline-none"
                    aria-label="국비 보조금 금액 입력"
                  />
                </div>
                <div>
                  <label htmlFor="localSubsidyInput" className="text-slate-400 block text-[11px]">
                    지방비 보조금
                  </label>
                  <input
                    id="localSubsidyInput"
                    type="number"
                    step="100000"
                    value={effectiveLocalSubsidy}
                    onChange={(e) => setCustomLocalSubsidy(parseInt(e.target.value, 10) || 0)}
                    className="w-full px-2 py-1 rounded bg-slate-800 border border-slate-700 text-right font-semibold text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded outline-none"
                    aria-label="지방비 보조금 금액 입력"
                  />
                </div>
              </div>
            </div>

            <div className="pt-3 border-t border-slate-800">
              <span className="text-xs text-slate-400 block">최종 납부 고지 환수액</span>
              <div
                className={`text-2xl sm:text-3xl font-black mt-1 ${
                  clawbackResult.totalClawbackKrw > 0 ? 'text-amber-400' : 'text-emerald-400'
                }`}
              >
                {clawbackResult.totalClawbackKrw.toLocaleString()}{' '}
                <span className="text-sm font-semibold text-slate-300">원</span>
              </div>
              <div className="text-[11px] text-slate-400 mt-1">
                회수요율: {(clawbackResult.effectiveClawbackRate * 100).toFixed(0)}% (지방비:{' '}
                {clawbackResult.localClawbackKrw.toLocaleString()}원)
              </div>
            </div>
          </div>
        </div>

        {/* 8-Tier Statutory Schedule Table */}
        <div className="pt-2">
          <details className="text-xs text-slate-600 bg-slate-50 rounded-xl border border-slate-200 p-3">
            <summary className="font-bold text-slate-800 cursor-pointer hover:text-blue-600 select-none">
              📋 대기환경보전법 시행규칙 [별표 21의2] 8단계 의무운행 회수요율표 보기
            </summary>
            <div
              tabIndex={0}
              aria-label="8단계 법정 의무운행기간 보조금 회수요율표 스크롤 영역"
              className="mt-3 overflow-x-auto focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            >
              <table className="w-full text-left border-collapse" aria-label="8단계 법정 의무운행기간 보조금 회수요율표">
                <caption className="sr-only">대기환경보전법 시행규칙 8단계 의무운행 회수요율표</caption>
                <thead>
                  <tr className="border-b border-slate-200 text-slate-600">
                    <th scope="col" className="py-2 px-3 font-semibold">운행 기간 구간</th>
                    <th scope="col" className="py-2 px-3 font-semibold text-center">법정 회수요율</th>
                    <th scope="col" className="py-2 px-3 font-semibold">타 지자체 관외이전 환수액</th>
                    <th scope="col" className="py-2 px-3 font-semibold">해외 수출말소 환수액</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {(initialDatabase?.subsidy_clawback_schedule?.tiers || []).map((tier) => {
                    const isCurrentTier =
                      (tier.max_months_exclusive === null && heldMonths >= tier.min_months) ||
                      (tier.max_months_exclusive !== null &&
                        heldMonths >= tier.min_months &&
                        heldMonths < tier.max_months_exclusive);

                    const localAmt = Math.round(effectiveLocalSubsidy * tier.clawback_rate);
                    const totalAmt = Math.round(
                      (effectiveLocalSubsidy + effectiveNationalSubsidy) * tier.clawback_rate
                    );

                    return (
                      <tr
                        key={`${tier.min_months}-${(tier as { max_months?: number; max_months_exclusive: number | null }).max_months ?? tier.max_months_exclusive}`}
                        className={
                          isCurrentTier
                            ? 'bg-blue-100/70 font-bold text-blue-950'
                            : 'hover:bg-slate-100'
                        }
                      >
                        <th scope="row" className="py-2 px-3 text-left font-medium">
                          {tier.label_ko} {isCurrentTier && '◀ 현재 해당'}
                        </th>
                        <td className="py-2 px-3 text-center">
                          {(tier.clawback_rate * 100).toFixed(0)}%
                        </td>
                        <td className="py-2 px-3">{localAmt.toLocaleString()}원</td>
                        <td className="py-2 px-3">{totalAmt.toLocaleString()}원</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </details>
        </div>
      </section>

      {/* 8. 5-YEAR TOTAL COST OF OWNERSHIP (TCO) COMPARISON */}
      <section
        aria-label="5개년 총소유비용 TCO 비교 섹션"
        className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 space-y-6"
      >
        <div className="border-b border-slate-200 pb-3 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-lg sm:text-xl font-bold text-slate-900 flex items-center gap-2">
              <span>📊</span> 5개년 총소유비용 (TCO) & 경제성 비교
            </h2>
            <p className="text-xs sm:text-sm text-slate-600">
              전기 충전비(완속/급속 가중평균) vs 가솔린 주유비, 자동차세(정액 13만 vs 배기량), 고속도로·주차 감면
            </p>
          </div>

          {/* ICE Displacement Selector */}
          <fieldset className="flex items-center gap-2 text-xs border-0 p-0 m-0">
            <legend className="sr-only">비교 내연기관 연료 및 배기량 세그먼트 선택</legend>
            <span className="font-semibold text-slate-700" aria-hidden="true">비교 내연기관:</span>
            <select
              value={iceDisplacementCc}
              onChange={(e) => setIceDisplacementCc(parseInt(e.target.value, 10))}
              className="px-3 py-1.5 rounded-lg border border-slate-300 font-medium bg-white text-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus:ring-2 focus:ring-blue-500"
              aria-label="비교 대상 내연기관 배기량 선택"
            >
              <option value={1598}>1,600cc 준중형 가솔린 (아반떼급)</option>
              <option value={1998}>2,000cc 중형 가솔린 (쏘나타/K5급)</option>
              <option value={2497}>2,500cc 준대형 가솔린 (그랜저급)</option>
              <option value={3470}>3,500cc 대형 가솔린 (G80급)</option>
            </select>
          </fieldset>
        </div>

        {/* 4 TCO Metric Summary Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
            <span className="text-xs text-slate-600 font-medium block">
              {holdingYears}년 누적 연료비 절감
            </span>
            <span className="text-xl sm:text-2xl font-black text-emerald-600 block mt-1">
              +{(tcoResult.fuelSavingsKrw / 10000).toLocaleString()}{' '}
              <span className="text-xs font-semibold text-slate-600">만원</span>
            </span>
            <span className="text-[11px] text-slate-600 mt-1 block">
              km당: 전기 {tcoResult.evFuelCostPerKm}원 vs 가솔린 {tcoResult.iceFuelCostPerKm}원
            </span>
          </div>

          <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
            <span className="text-xs text-slate-600 font-medium block">
              {holdingYears}년 자동차세 절감
            </span>
            <span className="text-xl sm:text-2xl font-black text-blue-600 block mt-1">
              +{(tcoResult.taxSavingsKrw / 10000).toLocaleString()}{' '}
              <span className="text-xs font-semibold text-slate-600">만원</span>
            </span>
            <span className="text-[11px] text-slate-600 mt-1 block">
              EV 연 13만 원(지방교육세 포함) 정액
            </span>
          </div>

          <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
            <span className="text-xs text-slate-600 font-medium block">
              통행료·주차·정비 보조 절감
            </span>
            <span className="text-xl sm:text-2xl font-black text-indigo-600 block mt-1">
              +{(tcoResult.totalAuxiliarySavingsKrw / 10000).toLocaleString()}{' '}
              <span className="text-xs font-semibold text-slate-600">만원</span>
            </span>
            <span className="text-[11px] text-slate-600 mt-1 block">
              하이패스 50% + 공영주차장 50%
            </span>
          </div>

          <div className="bg-gradient-to-br from-blue-600 to-indigo-700 text-white p-4 rounded-xl shadow-md">
            <span className="text-xs text-white font-medium block">
              {holdingYears}년 총 운행비 순이득
            </span>
            <span className="text-xl sm:text-2xl font-black text-white block mt-1">
              +{(tcoResult.totalCumulativeSavingsKrw / 10000).toLocaleString()}{' '}
              <span className="text-xs font-semibold text-white/90">만원</span>
            </span>
            <span className="text-[11px] text-white font-medium mt-1 block">
              월평균 +{Math.round(tcoResult.totalCumulativeSavingsKrw / Math.max(1, Math.round(safeYears * 12)) / 10000).toLocaleString()}만 원 절약
            </span>
          </div>
        </div>

        {/* Yearly Running Cost Breakdown Table */}
        <div
          tabIndex={0}
          aria-label="5개년 총소유비용(TCO) 및 유지비 절감 내역 표 스크롤 영역"
          className="overflow-x-auto focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        >
          <table className="w-full text-xs text-left border-collapse" aria-label="5개년 총소유비용(TCO) 및 유지비 절감 내역">
            <caption className="sr-only">5개년 총소유비용(TCO) 및 내연기관 대비 유지비 절감 내역</caption>
            <thead>
              <tr className="bg-slate-100 text-slate-600 border-b border-slate-200">
                <th scope="col" className="py-2.5 px-3 font-bold">연차</th>
                <th scope="col" className="py-2.5 px-3 font-bold">누적 주행</th>
                <th scope="col" className="py-2.5 px-3 font-bold">EV 충전비</th>
                <th scope="col" className="py-2.5 px-3 font-bold">내연기관 주유비</th>
                <th scope="col" className="py-2.5 px-3 font-bold">EV 세금</th>
                <th scope="col" className="py-2.5 px-3 font-bold">내연기관 세금</th>
                <th scope="col" className="py-2.5 px-3 font-bold">부가 절감</th>
                <th scope="col" className="py-2.5 px-3 font-bold text-right">연간 순 절감액</th>
                <th scope="col" className="py-2.5 px-3 font-bold text-right text-blue-600">누적 순 절감액</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 text-slate-700">
              {tcoResult.yearlyBreakdown.map((row) => (
                <tr key={row.year} className="hover:bg-slate-50 transition">
                  <th scope="row" className="py-2 px-3 font-bold text-left">{row.year}년차</th>
                  <td className="py-2 px-3">{row.cumulativeKm.toLocaleString()} km</td>
                  <td className="py-2 px-3">{(row.evElectricityCostKrw / 10000).toFixed(0)}만원</td>
                  <td className="py-2 px-3">{(row.iceFuelCostKrw / 10000).toFixed(0)}만원</td>
                  <td className="py-2 px-3">13만원</td>
                  <td className="py-2 px-3">{(row.iceAutomobileTaxKrw / 10000).toFixed(0)}만원</td>
                  <td className="py-2 px-3">
                    {((row.tollSavingsKrw + row.parkingSavingsKrw + row.maintenanceSavingsKrw) / 10000).toFixed(0)}만원
                  </td>
                  <td className="py-2 px-3 text-right font-semibold text-emerald-700">
                    +{(row.annualNetSavingsKrw / 10000).toFixed(0)}만원
                  </td>
                  <td className="py-2 px-3 text-right font-extrabold text-blue-600">
                    +{(row.cumulativeNetSavingsKrw / 10000).toFixed(0)}만원
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Net Resale Balance Callout */}
        <div className="bg-slate-50 rounded-xl p-4 border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div className="space-y-1">
            <span className="font-bold text-slate-800 flex items-center gap-1.5">
              <span>💡</span> 5년 종합 경제성 최종 판정:
            </span>
            <p className="text-slate-600">
              신차 구입가 대비 감가 손실 차액에 5개년 누적 운행비 절감액을 합산한 최종 실질 비용 평가입니다.
            </p>
          </div>

          <div className="bg-white px-4 py-2 rounded-lg border border-slate-300 font-extrabold text-slate-900 text-sm whitespace-nowrap">
            순 경제적 이점: <span className="text-blue-600">+{(tcoResult.totalCumulativeSavingsKrw / 10000).toLocaleString()}만 원</span>
          </div>
        </div>
      </section>

      {/* 9. STATUTORY & DATA SOURCES FOOTNOTE */}
      <div className="bg-slate-100 rounded-xl p-4 text-xs text-slate-600 space-y-1 leading-relaxed border border-slate-200">
        <div className="font-semibold text-slate-700">📌 데이터 출처 및 산정 근거 고지:</div>
        <div>
          • 중고차 실거래 시세: 엔카닷컴(Encar) 2024~2026 실거래 지수, 케이카(K Car) 월간 전기차 시세표, 보험개발원(KIDI) 차량기준가액표
        </div>
        <div>
          • 법정 보조금 환수: 환경부 전기자동차 보급사업 보조금 업무처리지침 및 대기환경보전법 시행규칙 제79조의4 [별표 21의2]
        </div>
        <div>
          • 자동차세 및 연료 단가: 지방세법 제127조 (전기차 연 13만원 정액), 환경부 공공급속충전요금 347.2원/kWh, 한전 비공용완속충전 250원/kWh, 오피넷 전국 평균 가솔린 1,700원/L
        </div>
      </div>
    </div>
  );
}
