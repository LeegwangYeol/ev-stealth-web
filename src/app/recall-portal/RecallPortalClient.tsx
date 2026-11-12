'use client';

import React, { useState, useMemo, useEffect, useCallback, useRef, Suspense, useDeferredValue } from 'react';
import { useSearchParams } from 'next/navigation';
import ClientTimestamp from '@/components/ClientTimestamp';
import type {
  RecallDatabase,
  VinCheckResult,
  OfficialRecallCampaign,
  BatterySafetyProfile,
  VinPrefixMapping,
} from '@/lib/recallCalculations';
import {
  decodeVinAndCheckRecalls,
  checkRecallsByModel,
  validateVinString,
  getDistinctBrands,
  getModelsForBrand,
  DEFAULT_RECALL_METADATA,
  sortRecallsByDate,
} from '@/lib/recallCalculations';
import { sanitizeSafeUrl, isExternalUrl, sanitizeText } from '@/lib/sanitizeUrl';

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

// Distinct cell supplier list for filter chips (hoisted to module scope to avoid re-allocation on render)
const supplierFilters = [
  Object.freeze({ key: 'ALL', label: '전체' }),
  Object.freeze({ key: '파라시스', label: '파라시스(Farasis)' }),
  Object.freeze({ key: 'LG', label: 'LG에너지솔루션' }),
  Object.freeze({ key: 'SK', label: 'SK온' }),
  Object.freeze({ key: '삼성', label: '삼성SDI' }),
  Object.freeze({ key: 'CATL', label: 'CATL' }),
  Object.freeze({ key: 'BYD', label: 'BYD FinDreams' }),
];
Object.freeze(supplierFilters);

// Fire safety status filter chips (frozen module scope)
const FIRE_STATUS_FILTERS = Object.freeze([
  Object.freeze({ key: 'ALL', label: '전체' }),
  Object.freeze({ key: 'CRITICAL_MONITORING', label: '🚨 집중 모니터링' }),
  Object.freeze({ key: 'RECALLED_RESOLVED', label: '🔄 조치 완료' }),
  Object.freeze({ key: 'VERIFIED_SAFE', label: '✅ 안전 검증' }),
]);

// Recall risk level filter chips (frozen module scope)
const RISK_LEVEL_FILTERS = Object.freeze([
  Object.freeze({ key: 'ALL', label: '전체' }),
  Object.freeze({ key: 'FIRE_HAZARD', label: '🔥 화재 위험' }),
  Object.freeze({ key: 'LOSS_OF_POWER', label: '⚡ 동력 상실/ICCU' }),
  Object.freeze({ key: 'BRAKE_STEERING', label: '🛑 조향/제동' }),
  Object.freeze({ key: 'SOFTWARE_REGULATION', label: '💻 소프트웨어/규정' }),
]);

// Remedy method filter chips (frozen module scope)
const REMEDY_METHOD_FILTERS = Object.freeze([
  Object.freeze({ key: 'ALL', label: '전체' }),
  Object.freeze({ key: 'HARDWARE_REPLACE', label: '🔧 부품 전량 무상 교체' }),
  Object.freeze({ key: 'SOFTWARE_UPDATE_SERVICE', label: '🛠️ 센터 방문 소프트웨어' }),
  Object.freeze({ key: 'OTA_WIRELESS', label: '📡 무선 소프트웨어 업데이트(OTA)' }),
]);

// Model year dropdown selection options (frozen module scope)
const MODEL_YEAR_OPTIONS = Object.freeze([2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018]);

// Frozen fallback collections (Zero-GC)
const EMPTY_BATTERY_PROFILES: BatterySafetyProfile[] = Object.freeze([]) as unknown as BatterySafetyProfile[];
const EMPTY_RECALLS: OfficialRecallCampaign[] = Object.freeze([]) as unknown as OfficialRecallCampaign[];
const EMPTY_VIN_PREFIXES: VinPrefixMapping[] = Object.freeze([]) as unknown as VinPrefixMapping[];

// Progressive virtualization page sizes
const PAGE_SIZE_BATTERIES = 12;
const PAGE_SIZE_RECALLS = 10;

/**
 * Normalizes search text by removing whitespace, hyphens, and common punctuation
 * for robust, resilient matching with special characters.
 */
function normalizeSearchText(text?: string | null): string {
  if (!text || typeof text !== 'string') return '';
  return text.toLowerCase().replace(/[\s\-_\/()+[\],.*&]/g, '');
}

function resolveBrand(inputBrand: string, availableBrands: string[]): string | undefined {
  if (!inputBrand || typeof inputBrand !== 'string' || !Array.isArray(availableBrands)) {
    return undefined;
  }
  const normalized = inputBrand.trim().toLowerCase();
  if (!normalized) return undefined;

  const direct = availableBrands.find((b) => b && typeof b === 'string' && b.toLowerCase() === normalized);
  if (direct) return direct;

  const synonym = Object.prototype.hasOwnProperty.call(BRAND_SYNONYMS, normalized)
    ? BRAND_SYNONYMS[normalized]
    : undefined;
  if (typeof synonym === 'string') {
    const synonymMatch = availableBrands.find((b) => b && typeof b === 'string' && b.toLowerCase() === synonym.toLowerCase());
    if (synonymMatch) return synonymMatch;
  }

  const partial = availableBrands.find(
    (b) => b && typeof b === 'string' && (b.toLowerCase().includes(normalized) || normalized.includes(b.toLowerCase()))
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

    // Collect all candidate items with their brand and model defensively
    const candidates: Array<{ brand: string; model: string }> = [];
    (initialDatabase?.battery_profiles || []).forEach((p) => {
      if (p?.brand && p?.model_name) {
        candidates.push({ brand: p.brand, model: p.model_name });
      }
    });
    (initialDatabase?.vin_prefixes || []).forEach((vp) => {
      if (vp?.brand && vp?.model_name) {
        candidates.push({ brand: vp.brand, model: vp.model_name });
      }
    });
    (initialDatabase?.recalls || []).forEach((r) => {
      if (r?.brand && r?.target_model) {
        r.target_model.split(',').forEach((mStr) => {
          const clean = mStr.trim();
          if (clean) candidates.push({ brand: r.brand, model: clean });
        });
      }
    });

    // 1. Exact match on model variant
    let matchedCandidate: { brand: string; model: string } | undefined;
    for (const v of variants) {
      matchedCandidate = candidates.find((c) => {
        if (!c?.model || typeof c.model !== 'string') return false;
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
          if (!c?.model || typeof c.model !== 'string') return false;
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
          if (!c?.model || typeof c.model !== 'string') return false;
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
    const targetModelLower = resolvedModel.toLowerCase();
    const brandModels = getModelsForBrand(resolvedBrand, initialDatabase);
    const matchedBrandModel = brandModels.find(
      (m) => {
        if (!m || typeof m !== 'string') return false;
        const mLower = m.toLowerCase();
        return (
          mLower === targetModelLower ||
          mLower.startsWith(targetModelLower) ||
          targetModelLower.startsWith(mLower) ||
          mLower.includes(targetModelLower) ||
          targetModelLower.includes(mLower)
        );
      }
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
  onSelectVin?: (vin: string) => void;
  initialDatabase: RecallDatabase;
  availableBrands: string[];
}

function SearchParamsWatcher({
  onSelectBrandModel,
  onSelectVin,
  initialDatabase,
  availableBrands,
}: SearchParamsWatcherProps) {
  const searchParams = useSearchParams();
  const lastAppliedRef = useRef<string>('');

  useEffect(() => {
    const currentParamString = searchParams.toString();
    if (!currentParamString || currentParamString === lastAppliedRef.current) return;

    const rawVinParam = searchParams.get('vin');
    const vinParam = rawVinParam ? sanitizeText(rawVinParam) : null;
    if (vinParam && onSelectVin) {
      lastAppliedRef.current = currentParamString;
      onSelectVin(vinParam);
      return;
    }

    const rawModelParam = searchParams.get('model');
    const rawBrandParam = searchParams.get('brand');
    const rawYearParam = searchParams.get('year');

    if (!rawModelParam && !rawBrandParam) return;

    lastAppliedRef.current = currentParamString;

    const modelParam = rawModelParam ? sanitizeText(rawModelParam) : null;
    const brandParam = rawBrandParam ? sanitizeText(rawBrandParam) : null;
    const yearParam = rawYearParam ? sanitizeText(rawYearParam) : null;

    const resolved = resolveModelAndBrand(
      modelParam,
      brandParam,
      initialDatabase,
      availableBrands
    );

    if (resolved) {
      const parsedYear = yearParam ? parseInt(yearParam, 10) : undefined;
      const validYear = typeof parsedYear === 'number' && !isNaN(parsedYear) ? parsedYear : undefined;
      onSelectBrandModel(
        resolved.brand,
        resolved.model,
        validYear
      );
    }
  }, [searchParams, initialDatabase, availableBrands, onSelectBrandModel, onSelectVin]);

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

  // Progressive virtualization visible counts (60fps DOM chunking)
  const [visibleBatteryCount, setVisibleBatteryCount] = useState<number>(PAGE_SIZE_BATTERIES);
  const [visibleRecallCount, setVisibleRecallCount] = useState<number>(PAGE_SIZE_RECALLS);

  // Reset pagination window when search or filters change
  useEffect(() => {
    setVisibleBatteryCount(PAGE_SIZE_BATTERIES);
  }, [batterySearch, selectedSupplierFilter, selectedFireStatusFilter]);

  useEffect(() => {
    setVisibleRecallCount(PAGE_SIZE_RECALLS);
  }, [recallSearch, selectedRiskFilter, selectedRemedyFilter]);

  // Expanded recall card IDs for accordion view
  const [expandedRecallIds, setExpandedRecallIds] = useState<Set<string>>(new Set());

  // Scroll timer ref to track and clear timeouts
  const scrollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Debounce timer ref for VIN auto-lookup
  const vinDebounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Clear pending timers on unmount to prevent memory leaks
  useEffect(() => {
    return () => {
      if (scrollTimerRef.current) {
        clearTimeout(scrollTimerRef.current);
      }
      if (vinDebounceTimerRef.current) {
        clearTimeout(vinDebounceTimerRef.current);
      }
    };
  }, []);

  // Focus helper to move focus and scroll smoothly to the search result section
  const focusResultSection = useCallback(() => {
    if (scrollTimerRef.current) {
      clearTimeout(scrollTimerRef.current);
    }
    scrollTimerRef.current = setTimeout(() => {
      const el = document.getElementById('search-result-section');
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        el.focus({ preventScroll: true });
      }
    }, 100);
  }, []);

  // Available brands and models for Mode B
  const availableBrands = useMemo(() => getDistinctBrands(initialDatabase), [initialDatabase]);
  const availableModels = useMemo(
    () => (selectedBrand ? getModelsForBrand(selectedBrand, initialDatabase) : []),
    [selectedBrand, initialDatabase]
  );

  // Defensive fallbacks for database collections and metadata (Zero-GC)
  const batteryProfiles = useMemo(
    () => (Array.isArray(initialDatabase?.battery_profiles) ? initialDatabase.battery_profiles : EMPTY_BATTERY_PROFILES),
    [initialDatabase?.battery_profiles]
  );
  const recalls = useMemo(
    () => (Array.isArray(initialDatabase?.recalls) ? initialDatabase.recalls : EMPTY_RECALLS),
    [initialDatabase?.recalls]
  );
  const vinPrefixes = useMemo(
    () => (Array.isArray(initialDatabase?.vin_prefixes) ? initialDatabase.vin_prefixes : EMPTY_VIN_PREFIXES),
    [initialDatabase?.vin_prefixes]
  );
  const metadata = useMemo(
    () => initialDatabase?.metadata ?? DEFAULT_RECALL_METADATA,
    [initialDatabase?.metadata]
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
      focusResultSection();
    },
    [initialDatabase, focusResultSection]
  );

  // Handler for VIN query parameter auto-selection (?vin=...)
  const handleSelectVinFromParams = useCallback(
    (vin: string) => {
      if (vinDebounceTimerRef.current) {
        clearTimeout(vinDebounceTimerRef.current);
      }
      const cleanVin = sanitizeText(vin).trim().toUpperCase().replace(/[\s-]/g, '');
      setVinInput(cleanVin);
      setVinTouched(true);
      setActiveCheckerMode('VIN');
      if (cleanVin.length === 17) {
        const result = decodeVinAndCheckRecalls(cleanVin, initialDatabase);
        setCheckResult(result);
        focusResultSection();
      }
    },
    [initialDatabase, focusResultSection]
  );

  // Deferred values for stutter-free filtering on large datasets
  const deferredVinInput = useDeferredValue(vinInput);
  const deferredBatterySearch = useDeferredValue(batterySearch);
  const deferredRecallSearch = useDeferredValue(recallSearch);

  // Live validation for VIN input (using deferred value to prevent keystroke lag)
  const vinValidation = useMemo(() => {
    if (!deferredVinInput) return { valid: false, normalized: '', error: '' };
    return validateVinString(deferredVinInput);
  }, [deferredVinInput]);

  // Debounced input change handler for VIN search
  const handleVinChange = useCallback((value: string) => {
    const uppercaseVal = value.toUpperCase();
    setVinInput(uppercaseVal);
    setVinTouched(true);

    if (vinDebounceTimerRef.current) {
      clearTimeout(vinDebounceTimerRef.current);
    }

    const clean = uppercaseVal.trim().replace(/[\s-]/g, '');

    // Invalidate stale VIN check result if length is incomplete
    if (clean.length < 17) {
      setCheckResult((prev) => (prev && prev.mode === 'VIN' ? null : prev));
      return;
    }

    // When 17 characters entered, debounce auto-search (350ms)
    if (clean.length === 17) {
      vinDebounceTimerRef.current = setTimeout(() => {
        const valResult = validateVinString(clean);
        if (valResult.valid) {
          const result = decodeVinAndCheckRecalls(clean, initialDatabase);
          setCheckResult(result);
        }
      }, 350);
    }
  }, [initialDatabase]);

  // Handle Mode A lookup
  const handleVinSubmit = useCallback((e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setVinTouched(true);
    if (vinDebounceTimerRef.current) {
      clearTimeout(vinDebounceTimerRef.current);
    }
    const clean = vinInput.trim().toUpperCase().replace(/[\s-]/g, '');
    if (!clean) {
      const result = decodeVinAndCheckRecalls('', initialDatabase);
      setCheckResult(result);
      focusResultSection();
      return;
    }

    const validation = validateVinString(clean);
    if (!validation.valid) {
      const result = decodeVinAndCheckRecalls(clean, initialDatabase);
      setCheckResult(result);
      focusResultSection();
      return;
    }

    const result = decodeVinAndCheckRecalls(clean, initialDatabase);
    setCheckResult(result);
    focusResultSection();
  }, [vinInput, initialDatabase, focusResultSection]);

  // Quick 1-click sample VIN handler
  const handleSelectSampleVin = useCallback((sampleVin: string) => {
    if (vinDebounceTimerRef.current) {
      clearTimeout(vinDebounceTimerRef.current);
    }
    setVinInput(sampleVin);
    setVinTouched(true);
    const result = decodeVinAndCheckRecalls(sampleVin, initialDatabase);
    setCheckResult(result);
    focusResultSection();
  }, [initialDatabase, focusResultSection]);

  // Handle Mode B lookup
  const handleModelSubmit = useCallback((e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!selectedBrand || !selectedModel) {
      setCheckResult({
        valid: false,
        query: `${selectedBrand || ''} ${selectedModel || ''} ${selectedYear || ''}`.trim(),
        mode: 'MODEL',
        validationError: '제조사와 모델을 모두 선택해 주십시오.',
        recalls: [],
        activeCampaignsCount: 0,
        hasFireRisk: false,
        hasPowerLoss: false,
        overallRiskGrade: 'SAFE',
        timestamp: new Date().toISOString(),
      });
      focusResultSection();
      return;
    }

    const yr = typeof selectedYear === 'number' ? selectedYear : undefined;
    const result = checkRecallsByModel(selectedBrand, selectedModel, yr, initialDatabase);
    setCheckResult(result);
    focusResultSection();
  }, [selectedBrand, selectedModel, selectedYear, initialDatabase, focusResultSection]);

  // Toggle card expansion
  const toggleRecallExpansion = useCallback((id: string) => {
    setExpandedRecallIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  // Filtered Battery Safety Profiles (deferred search with multi-token & special char resilience)
  const filteredBatteryProfiles = useMemo(() => {
    const rawQ = deferredBatterySearch.trim().toLowerCase();
    const normQ = normalizeSearchText(rawQ);
    const tokens = rawQ.split(/\s+/).filter(Boolean);

    return batteryProfiles.filter((profile) => {
      if (!profile) return false;
      const model = profile.model_name || '';
      const brand = profile.brand || '';
      const supplier = profile.cell_supplier || '';
      const chem = profile.cell_chemistry || '';

      let matchesSearch = true;
      if (rawQ) {
        const combinedRaw = `${brand} ${model} ${supplier} ${chem}`.toLowerCase();
        const combinedNorm = normalizeSearchText(combinedRaw);

        const rawMatch = combinedRaw.includes(rawQ);
        const normMatch = normQ ? combinedNorm.includes(normQ) : false;
        const tokenMatch =
          tokens.length > 0 &&
          tokens.every(
            (tok) => combinedRaw.includes(tok) || combinedNorm.includes(normalizeSearchText(tok))
          );

        matchesSearch = rawMatch || normMatch || tokenMatch;
      }

      const matchesSupplier =
        selectedSupplierFilter === 'ALL' ||
        supplier.toLowerCase().includes(selectedSupplierFilter.toLowerCase());

      const matchesStatus =
        selectedFireStatusFilter === 'ALL' || profile.fire_incident_status === selectedFireStatusFilter;

      return matchesSearch && matchesSupplier && matchesStatus;
    });
  }, [batteryProfiles, deferredBatterySearch, selectedSupplierFilter, selectedFireStatusFilter]);

  const displayedBatteryProfiles = useMemo(
    () => filteredBatteryProfiles.slice(0, visibleBatteryCount),
    [filteredBatteryProfiles, visibleBatteryCount]
  );

  // Filtered Recalls (deferred search with multi-token & special char resilience)
  const filteredRecalls = useMemo(() => {
    const rawQ = deferredRecallSearch.trim().toLowerCase();
    const normQ = normalizeSearchText(rawQ);
    const tokens = rawQ.split(/\s+/).filter(Boolean);

    const filtered = recalls.filter((r) => {
      if (!r) return false;
      const campNo = r.campaign_no || '';
      const title = r.defect_title || '';
      const model = r.target_model || '';
      const brand = r.brand || '';
      const detail = r.defect_detail || '';

      let matchesSearch = true;
      if (rawQ) {
        const combinedRaw = `${campNo} ${brand} ${model} ${title} ${detail}`.toLowerCase();
        const combinedNorm = normalizeSearchText(combinedRaw);

        const rawMatch = combinedRaw.includes(rawQ);
        const normMatch = normQ ? combinedNorm.includes(normQ) : false;
        const tokenMatch =
          tokens.length > 0 &&
          tokens.every(
            (tok) => combinedRaw.includes(tok) || combinedNorm.includes(normalizeSearchText(tok))
          );

        matchesSearch = rawMatch || normMatch || tokenMatch;
      }

      const matchesRisk = selectedRiskFilter === 'ALL' || r.risk_level === selectedRiskFilter;
      const matchesRemedy = selectedRemedyFilter === 'ALL' || r.remedy_type === selectedRemedyFilter;

      return matchesSearch && matchesRisk && matchesRemedy;
    });
    return sortRecallsByDate(filtered, 'desc');
  }, [recalls, deferredRecallSearch, selectedRiskFilter, selectedRemedyFilter]);

  const displayedRecalls = useMemo(
    () => filteredRecalls.slice(0, visibleRecallCount),
    [filteredRecalls, visibleRecallCount]
  );

  // Active VIN error state for accessible form feedback
  const vinError = vinTouched && !vinValidation.valid ? (vinValidation.error || '차대번호(VIN) 17자리를 입력해 주십시오.') : '';

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
    } else if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
      e.preventDefault();
      setActiveCheckerMode(currentMode);
      setCheckResult(null);
      return;
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
          onSelectVin={handleSelectVinFromParams}
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
                  🚨 대한민국 국토교통부 및 미국 도로교통안전국(NHTSA) 공시 연동
                </span>
                <span className="text-xs text-slate-300">기준: 2026 최신 개정판</span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white flex items-center gap-2.5">
                <span>전기차 공식 리콜 및 배터리 화재 안전 포털</span>
              </h1>
              <p className="text-sm text-slate-300 mt-1 max-w-3xl">
                17자리 차대번호(VIN) 및 차종별 배터리 제조사(파라시스, LG, SK, 삼성, CATL 등), 화재 결함 이력,
                ICCU 동력상실 리콜 및 아파트 지하주차장 충전 가이드를 즉시 확인하십시오.
              </p>
            </div>

            {/* Quick action buttons */}
            <div className="flex flex-wrap items-center gap-2">
              <a
                href={sanitizeSafeUrl('https://www.car.go.kr')}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="대한민국 국토교통부 자동차리콜센터 공식 웹사이트 (새 창에서 열림)"
                className="inline-flex items-center gap-1.5 px-3.5 py-2 min-h-[44px] rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-100 border border-slate-700 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
              >
                <svg className="w-4 h-4 text-blue-400" width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
                자동차리콜센터 공식
                <span className="sr-only"> (새 창에서 열림)</span>
              </a>
              <a
                href="#battery-directory"
                className="inline-flex items-center gap-1.5 px-3.5 py-2 min-h-[44px] rounded-lg text-xs font-semibold bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/40 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
              >
                🔋 배터리 제조사 공개표
              </a>
            </div>
          </div>

          {/* Key Safety Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6">
            <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-3.5 shadow-sm">
              <span className="text-xs text-slate-300 font-medium">분석 리콜 캠페인</span>
              <div className="text-xl sm:text-2xl font-black text-white mt-0.5">
                {metadata?.total_campaigns ?? 0}
                <span className="text-xs font-normal text-slate-300 ml-1">건 (정부 공시)</span>
              </div>
            </div>

            <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-3.5 shadow-sm">
              <span className="text-xs text-slate-300 font-medium">국내 출시(KDM) 대상 차량</span>
              <div className="text-xl sm:text-2xl font-black text-amber-400 mt-0.5">
                {Number.isFinite(metadata?.total_affected_vehicles_kdm)
                  ? metadata.total_affected_vehicles_kdm.toLocaleString()
                  : '0'}
                <span className="text-xs font-normal text-slate-300 ml-1">대</span>
              </div>
            </div>

            <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-3.5 shadow-sm">
              <span className="text-xs text-slate-300 font-medium">긴급 화재 특별주의보</span>
              <div className="text-xl sm:text-2xl font-black text-red-400 mt-0.5">
                {metadata?.active_fire_campaigns ?? 0}
                <span className="text-xs font-normal text-slate-300 ml-1">개 차종</span>
              </div>
            </div>

            <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-3.5 shadow-sm">
              <span className="text-xs text-slate-300 font-medium">OTA 무선 조치 지원율</span>
              <div className="text-xl sm:text-2xl font-black text-emerald-400 mt-0.5">
                {Number.isFinite(metadata?.ota_remedy_rate_pct) ? metadata.ota_remedy_rate_pct : 0}
                <span className="text-xs font-normal text-slate-300 ml-1">% (방문 불필요)</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-12">
        {/* 2. Dual-Mode Verification Tool */}
        <section aria-labelledby="recall-checker-heading" className="bg-slate-950 border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-xl">
          <div className="max-w-3xl mb-6">
            <h2 id="recall-checker-heading" className="text-xl sm:text-2xl font-bold text-white flex items-center gap-2">
              <svg className="w-6 h-6 text-blue-400" width="24" height="24" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
              <span>차량 결함 및 리콜 즉시 판정기</span>
            </h2>
            <p className="text-sm text-slate-300 mt-1">
              차량등록증의 차대번호 17자리를 입력하거나 제조사·차종을 선택하면 매칭 리콜과 배터리 정보를 즉시 분석합니다.
            </p>
          </div>

          {/* Mode Switcher Tabs */}
          <div role="tablist" aria-label="리콜 조회 방식 선택" className="flex flex-col sm:flex-row border-b border-slate-800 mb-6 gap-1 sm:gap-0">
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
              className={`py-3 px-5 min-h-[44px] text-sm font-semibold border-b-2 transition flex items-center justify-center sm:justify-start gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
                activeCheckerMode === 'VIN'
                  ? 'border-blue-500 text-blue-400 bg-blue-950/20'
                  : 'border-transparent text-slate-300 hover:text-slate-200'
              }`}
            >
              <svg className="w-4 h-4" width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
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
              className={`py-3 px-5 min-h-[44px] text-sm font-semibold border-b-2 transition flex items-center justify-center sm:justify-start gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
                activeCheckerMode === 'MODEL'
                  ? 'border-blue-500 text-blue-400 bg-blue-950/20'
                  : 'border-transparent text-slate-300 hover:text-slate-200'
              }`}
            >
              <svg className="w-4 h-4" width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
              </svg>
              <span>[모드 B] 제조사 / 차종 / 연식 간편 선택</span>
            </button>
          </div>

          {/* MODE A Form */}
          {activeCheckerMode === 'VIN' && (
            <div id="vin-checker-panel" role="tabpanel" aria-labelledby="vin-checker-tab" tabIndex={0} className="focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-2xl">
              <form role="search" aria-label="차대번호(VIN) 17자리 기반 리콜 및 배터리 진단 검색" onSubmit={handleVinSubmit} className="space-y-4">
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
                      aria-label="차대번호 17자리 입력 (영문 대문자 및 숫자)"
                      aria-invalid={!!vinError}
                      aria-describedby={vinError ? "vin-error-feedback vin-format-hint" : "vin-format-hint"}
                      onChange={(e) => handleVinChange(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Escape' && vinInput) {
                          e.stopPropagation();
                          if (vinDebounceTimerRef.current) {
                            clearTimeout(vinDebounceTimerRef.current);
                          }
                          setVinInput('');
                          setVinTouched(false);
                          setCheckResult(null);
                        }
                      }}
                      placeholder="예: KM8KN4AE4NU123456 또는 W1K295112PF123456"
                      autoComplete="off"
                      spellCheck={false}
                      autoCapitalize="characters"
                      className={`w-full bg-slate-900 border rounded-xl px-4 py-3.5 text-base font-mono tracking-wider text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus-visible:ring-2 transition ${
                        vinError
                          ? 'border-red-500 focus:ring-red-500/50 focus-visible:ring-red-500/50'
                          : 'border-slate-700 focus:ring-blue-500/50 focus-visible:ring-blue-500/50 focus:border-blue-500'
                      }`}
                    />
                    <p id="vin-format-hint" className="sr-only">영문 대문자와 숫자로 구성된 17자리 차량 식별 번호 (I, O, Q 제외)</p>
                    <div className="absolute right-3 top-3.5 text-xs font-mono text-slate-300">
                      {vinInput.replace(/[\s-]/g, '').length}/17
                    </div>
                  </div>

                  {/* Realtime validation feedback */}
                  {vinError && (
                    <p id="vin-error-feedback" role="alert" aria-live="assertive" className="mt-2 text-xs text-red-400 flex items-center gap-1.5 font-medium">
                      <svg className="w-4 h-4 flex-shrink-0 text-red-400" width="16" height="16" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true" focusable="false">
                        <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                      </svg>
                      {vinError}
                    </p>
                  )}

                  {vinTouched && vinValidation.valid && (
                    <p role="status" aria-live="polite" className="mt-2 text-xs text-emerald-400 flex items-center gap-1.5 font-medium">
                      <svg className="w-4 h-4 flex-shrink-0 text-emerald-400" width="16" height="16" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true" focusable="false">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                      </svg>
                      유효한 ISO 3779 17자리 차대번호 형식입니다.
                    </p>
                  )}
                </div>

                <div className="flex flex-col sm:flex-row sm:items-center gap-3 pt-2">
                  <button
                    type="submit"
                    aria-label="차대번호로 리콜 및 배터리 진단"
                    className="w-full sm:w-auto px-6 py-3 min-h-[44px] rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm transition shadow-lg flex items-center justify-center gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
                  >
                    <svg className="w-4 h-4" width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                    차대번호로 리콜 및 배터리 진단
                  </button>

                  <button
                    type="button"
                    aria-label="차대번호 입력 초기화"
                    onClick={() => {
                      if (vinDebounceTimerRef.current) {
                        clearTimeout(vinDebounceTimerRef.current);
                      }
                      setVinInput('');
                      setVinTouched(false);
                      setCheckResult(null);
                      document.getElementById('vin-input')?.focus();
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
                        e.preventDefault();
                        if (vinDebounceTimerRef.current) {
                          clearTimeout(vinDebounceTimerRef.current);
                        }
                        setVinInput('');
                        setVinTouched(false);
                        setCheckResult(null);
                        document.getElementById('vin-input')?.focus();
                      }
                    }}
                    className="px-4 py-3 min-h-[44px] rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                  >
                    초기화
                  </button>
                </div>
              </form>

              {/* 1-Click Sample VIN Quick Selector Buttons */}
              <div className="mt-6 pt-6 border-t border-slate-800/80">
                <div className="flex flex-wrap items-center justify-between gap-1 mb-3">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                    💡 차대번호가 기억나지 않으시나요? 예시 차대번호 1초 선택:
                  </span>
                  <span className="text-[11px] text-slate-300">실제 KDM 출고 규격</span>
                </div>
                <div role="group" aria-label="실제 KDM 출고 규격 예시 차대번호 빠른 선택 목록" className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
                  {vinPrefixes.slice(0, 6).map((item) => (
                    <button
                      key={item.prefix}
                      type="button"
                      aria-pressed={vinInput === item.sample_full_vin}
                      aria-label={`${item.brand || '제조사'} ${item.model_name || '차종'} 샘플 차대번호(${item.sample_full_vin}) 자동 입력`}
                      onClick={() => handleSelectSampleVin(item.sample_full_vin)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
                          e.preventDefault();
                          handleSelectSampleVin(item.sample_full_vin);
                        }
                      }}
                      className={`p-2.5 rounded-lg border text-left transition group focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 min-h-[44px] ${
                        vinInput === item.sample_full_vin
                          ? 'bg-blue-950/60 border-blue-500 ring-1 ring-blue-500'
                          : 'bg-slate-900 hover:bg-blue-900/40 border-slate-800 hover:border-blue-700'
                      }`}
                    >
                      <div className="text-xs font-bold text-white group-hover:text-blue-300 truncate">
                        {item.model_name || '차종 미상'}
                      </div>
                      <div className="text-[10px] text-slate-300 truncate mt-0.5">
                        {item.brand || '제조사 미상'}
                      </div>
                      <div className="text-[10px] font-mono text-blue-300 truncate mt-1">
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
              <form role="search" aria-label="제조사 및 차종 선택 기반 리콜 및 배터리 진단 검색" onSubmit={handleModelSubmit} className="space-y-4">
                <fieldset className="grid grid-cols-1 sm:grid-cols-3 gap-4 border-0 p-0 m-0">
                  <legend className="sr-only">제조사, 모델, 생산 연식 선택 필터</legend>
                  {/* Brand */}
                  <div>
                    <label htmlFor="brand-select" className="block text-xs font-semibold text-slate-300 uppercase mb-2">
                      1. 제조사 선택
                    </label>
                    <select
                      id="brand-select"
                      aria-label="1. 제조사 선택"
                      value={selectedBrand}
                      onChange={(e) => {
                        const newBrand = e.target.value;
                        setSelectedBrand(newBrand);
                        const models = getModelsForBrand(newBrand, initialDatabase);
                        setSelectedModel(models[0] || '');
                      }}
                      className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-3 text-sm text-white min-h-[44px] focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
                    >
                      {availableBrands.length === 0 ? (
                        <option value="">등록된 제조사 없음</option>
                      ) : (
                        availableBrands.map((b) => (
                          <option key={b} value={b}>
                            {b}
                          </option>
                        ))
                      )}
                    </select>
                  </div>

                  {/* Model */}
                  <div>
                    <label htmlFor="model-select" className="block text-xs font-semibold text-slate-300 uppercase mb-2">
                      2. 모델 선택
                    </label>
                    <select
                      id="model-select"
                      aria-label="2. 모델 선택"
                      value={selectedModel}
                      onChange={(e) => setSelectedModel(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-3 text-sm text-white min-h-[44px] focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
                    >
                      {availableModels.length === 0 ? (
                        <option value="">등록된 모델 없음</option>
                      ) : (
                        availableModels.map((m) => (
                          <option key={m} value={m}>
                            {m}
                          </option>
                        ))
                      )}
                    </select>
                  </div>

                  {/* Production Year */}
                  <div>
                    <label htmlFor="year-select" className="block text-xs font-semibold text-slate-300 uppercase mb-2">
                      3. 생산 연식 선택
                    </label>
                    <select
                      id="year-select"
                      aria-label="3. 생산 연식 선택"
                      value={selectedYear}
                      onChange={(e) => setSelectedYear(e.target.value ? Number(e.target.value) : '')}
                      className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-3 text-sm text-white min-h-[44px] focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
                    >
                      <option value="">전체 연식 확인</option>
                      {MODEL_YEAR_OPTIONS.map((yr) => (
                        <option key={yr} value={yr}>
                          {yr}년식
                        </option>
                      ))}
                    </select>
                  </div>
                </fieldset>

                <div className="pt-2">
                  <button
                    type="submit"
                    aria-label="선택 차종 결함 및 리콜 진단"
                    className="w-full sm:w-auto px-6 py-3 min-h-[44px] rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm transition shadow-lg flex items-center justify-center gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
                  >
                    <svg className="w-4 h-4" width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
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
          <section
            id="search-result-section"
            tabIndex={-1}
            aria-labelledby="search-result-heading"
            aria-live="polite"
            className="space-y-6 scroll-mt-24 focus:outline-none"
          >
            {!checkResult.valid ? (
              <div
                role="alert"
                aria-live="assertive"
                className="rounded-2xl p-6 sm:p-8 shadow-2xl border border-red-700 bg-gradient-to-br from-red-950 via-red-900 to-slate-950 text-white space-y-4"
              >
                <div className="flex items-start gap-4">
                  <div className="p-3 rounded-xl bg-black/40 text-2xl flex-shrink-0" aria-hidden="true">
                    ⚠️
                  </div>
                  <div className="space-y-2 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-extrabold uppercase tracking-wider px-2 py-0.5 rounded bg-red-950 text-red-200 border border-red-700">
                        {checkResult.mode === 'MODEL' ? '차종 선택 검증 안내' : '차대번호(VIN) 유효성 검증 실패'}
                      </span>
                      <span className="text-xs text-slate-300">
                        입력값: <span className="font-mono text-amber-300 font-bold">{checkResult.query || '(선택 없음)'}</span>
                      </span>
                    </div>

                    <h2 id="search-result-heading" className="text-xl sm:text-2xl font-black text-white">
                      {checkResult.mode === 'MODEL'
                        ? '차종 선택 정보 확인 안내'
                        : '차대번호 표준 규격(ISO 3779) 불일치 안내'}
                    </h2>

                    <p className="text-sm text-red-200 leading-relaxed font-medium">
                      {checkResult.validationError ||
                        (checkResult.mode === 'MODEL'
                          ? '제조사 및 모델명을 올바르게 선택해 주십시오.'
                          : '입력하신 차대번호가 국제 표준 17자리 형식과 일치하지 않습니다.')}
                    </p>

                    <div className="pt-2 text-xs text-slate-300 space-y-1 bg-black/40 p-4 rounded-xl border border-red-800/60">
                      <p className="font-semibold text-amber-300 flex items-center gap-1.5">
                        <span aria-hidden="true">💡</span>{' '}
                        {checkResult.mode === 'MODEL' ? '차종 선택 요령:' : '올바른 차대번호 확인 및 입력 요령:'}
                      </p>
                      {checkResult.mode === 'MODEL' ? (
                        <ul className="list-disc list-inside space-y-1 text-slate-300 pt-1">
                          <li>위 드롭다운에서 조회하실 <strong>제조사</strong>(예: 현대자동차, 기아, 테슬라 등)를 먼저 선택하십시오.</li>
                          <li>이후 해당 제조사의 <strong>상세 모델</strong>(예: 아이오닉 5, EV6 등)을 선택해 주십시오.</li>
                          <li>필요한 경우 특정 생산 연식을 지정하여 정밀 진단할 수 있습니다.</li>
                        </ul>
                      ) : (
                        <ul className="list-disc list-inside space-y-1 text-slate-300 pt-1">
                          <li>자동차등록증(차량등록증) 5번 항목 [차대번호] 17자리를 확인해 주십시오.</li>
                          <li>차량 운전석 전면 유리창 하단 또는 운전석 B필러 도어 스티커에서도 확인 가능합니다.</li>
                          <li>국제 규격상 숫자 1, 0과의 혼동을 막기 위해 <strong>I(아이), O(오), Q(큐)</strong>는 사용되지 않습니다.</li>
                        </ul>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <>
                {/* Overall Risk Banner */}
                <div
                  role="status"
                  aria-live="polite"
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
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-xs font-extrabold uppercase tracking-wider px-2 py-0.5 rounded bg-black/50">
                            {checkResult.overallRiskGrade === 'CRITICAL'
                              ? '긴급 안전 주의보 발령'
                              : checkResult.overallRiskGrade === 'WARNING'
                              ? '안전 리콜 조치 권고'
                              : '안전 검증 완료'}
                          </span>
                          <span className="text-xs text-slate-300">
                            조회 일시:{' '}
                            <ClientTimestamp
                              isoString={checkResult.timestamp}
                              fallback="최근"
                              options={{ year: 'numeric', month: 'numeric', day: 'numeric' }}
                            />
                          </span>
                        </div>

                        <h2 id="search-result-heading" className="text-xl sm:text-2xl font-black mt-1">
                          {checkResult.decodedBrand || '미확인 브랜드'} {checkResult.decodedModel?.trim() ? checkResult.decodedModel : '미확인 모델'}{' '}
                          {checkResult.decodedYear ? `${checkResult.decodedYear}년식` : ''} 판정 결과
                        </h2>

                        <p className="text-sm text-slate-200 mt-1 max-w-3xl leading-relaxed">
                          {checkResult.mode === 'VIN' && !checkResult.decodedModel && (
                            <span className="block text-amber-300 text-xs font-semibold mb-1">
                              ℹ️ 차대번호(VIN) 기준 제조사는 식별되었으나 세부 모델 정보가 데이터베이스에 매핑되지 않았습니다.
                            </span>
                          )}
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
                        <h3 className="text-lg font-bold text-white mt-0.5">
                          {checkResult.batteryProfile.model_name} 배터리 안전 제원
                        </h3>
                      </div>
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-xs px-3 py-1 rounded-full font-bold border ${
                            checkResult.batteryProfile.fire_incident_status === 'CRITICAL_MONITORING'
                              ? 'bg-red-950/80 text-rose-200 border-red-700'
                              : checkResult.batteryProfile.fire_incident_status === 'RECALLED_RESOLVED'
                              ? 'bg-amber-950/80 text-amber-200 border-amber-700'
                              : 'bg-emerald-950/80 text-emerald-200 border-emerald-700'
                          }`}
                        >
                          {checkResult.batteryProfile.fire_incident_status_ko}
                        </span>
                        <span className="text-xs px-3 py-1 rounded-full font-bold bg-blue-950 text-blue-200 border border-blue-700">
                          완충 권장 한도: {checkResult.batteryProfile.recommended_soc_limit}%
                        </span>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                      <div className="bg-slate-900/90 rounded-xl p-4 border border-slate-800 space-y-2">
                        <div className="flex justify-between">
                          <span className="text-slate-300">배터리 셀 제조사:</span>
                          <span className="font-bold text-white">{checkResult.batteryProfile.cell_supplier}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-300">배터리 셀 화학(Chemistry):</span>
                          <span className="font-medium text-slate-200">{checkResult.batteryProfile.cell_chemistry}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-300">적용 생산 기간:</span>
                          <span className="font-mono text-slate-300">{checkResult.batteryProfile.years}</span>
                        </div>
                        <div className="pt-2 border-t border-slate-800/80 text-xs text-slate-300">
                          <span className="font-semibold text-blue-400">BMS 안전 보호 기술:</span>{' '}
                          {checkResult.batteryProfile.bms_safety_features}
                        </div>
                      </div>

                      <div className="bg-amber-950/30 border border-amber-800/50 rounded-xl p-4 space-y-2">
                        <div className="flex items-center gap-2 text-amber-300 font-bold text-xs">
                          <svg className="w-4 h-4 text-amber-400 flex-shrink-0" width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                          </svg>
                          <span aria-hidden="true">🏢</span> 아파트 지하주차장 이용 및 충전 가이드
                        </div>
                        <p className="text-xs text-slate-200 leading-relaxed font-medium">
                          {checkResult.batteryProfile.underground_parking_advisory}
                        </p>
                        <div className="pt-2 text-[11px] text-amber-300">
                          * 아파트 관리사무소 화재 예방 수칙 및 국토교통부 권고 기준 준수 권장.
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* VIN Empty Battery Info note */}
                {checkResult.mode === 'VIN' && !checkResult.batteryProfile && (
                  <div className="bg-slate-950 border border-slate-800 rounded-2xl p-5 text-sm space-y-2">
                    <div className="flex items-center gap-2 text-blue-400 font-semibold text-xs">
                      <span aria-hidden="true">🔋</span>
                      <span>배터리 실명제 공시 안내</span>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed">
                      차대번호 기준 제조사({checkResult.decodedBrand || '해당 제조사'})는 식별되었으나, 
                      본 세부 트림의 배터리 셀 제조사 정보는 하단의 [배터리 제조사 공개표]에서 차종명으로 직접 검색하시거나 차량등록증의 제원표를 확인해 주십시오.
                    </p>
                  </div>
                )}

                {/* Matched Recall Campaign Cards */}
                <div className="space-y-4">
                  <div aria-live="polite" aria-atomic="true" className="sr-only">
                    {checkResult.recalls.length === 0
                      ? '해당 차종 조건에 일치하는 활성 리콜이 없습니다.'
                      : `해당 차종 대상 정부 공시 리콜 총 ${checkResult.recalls.length}건이 조회되었습니다.`}
                  </div>
                  <h3 className="text-lg font-bold text-white flex items-center gap-2">
                    <span>해당 차종 대상 정부 공시 리콜 세부 내역 ({checkResult.recalls.length}건)</span>
                  </h3>

                  {checkResult.recalls.length === 0 ? (
                    <div className="bg-slate-950 border border-emerald-900/50 rounded-2xl p-8 text-center space-y-3">
                      <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-emerald-950/80 border border-emerald-700/60 text-2xl text-emerald-300 mx-auto" aria-hidden="true">
                        ✓
                      </div>
                      <div className="space-y-1">
                        <p className="text-base font-bold text-emerald-300">
                          조회된 차종 조건에 등록된 공식 안전 리콜이 없습니다
                        </p>
                        <p className="text-xs text-slate-300 max-w-xl mx-auto leading-relaxed">
                          대한민국 국토교통부(MOLIT) 및 미국 NHTSA 공시 데이터베이스 대조 결과, 현재 발령된 긴급 안전 리콜 또는 시정명령 캠페인이 없습니다.
                        </p>
                      </div>
                      <div className="pt-2 flex flex-wrap items-center justify-center gap-3 text-xs">
                        <span className="text-slate-300">
                          * 정기적인 무선 소프트웨어(OTA) 업데이트 및 제조사 공식 서비스센터 정기점검을 권장합니다.
                        </span>
                        <a
                          href={sanitizeSafeUrl('https://www.car.go.kr')}
                          target="_blank"
                          rel="noopener noreferrer"
                          aria-label="대한민국 국토교통부 자동차리콜센터(car.go.kr) 실시간 1:1 확인 (새 창에서 열림)"
                          className="inline-flex items-center gap-1.5 px-3.5 py-2 min-h-[44px] rounded-lg text-xs font-semibold bg-slate-900 hover:bg-slate-800 text-blue-300 border border-slate-700 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                        >
                          <span>자동차리콜센터(car.go.kr) 실시간 1:1 확인</span>
                          <svg className="w-3.5 h-3.5" width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                          </svg>
                          <span className="sr-only"> (새 창에서 열림)</span>
                        </a>
                      </div>
                    </div>
                  ) : (
                    checkResult.recalls.map((campaign) => (
                      <RecallCard
                        key={campaign.id}
                        campaign={campaign}
                        isExpanded={expandedRecallIds.has(campaign.id)}
                        toggleRecallExpansion={toggleRecallExpansion}
                        panelIdPrefix="campaign-search-detail-"
                      />
                    ))
                  )}
                </div>
              </>
            )}
          </section>
        )}

        {/* 4. Battery Safety Directory (공개 배터리 제조사 및 지하주차장 안전 가이드) */}
        <section id="battery-directory" aria-labelledby="battery-directory-heading" className="bg-slate-950 border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-xl space-y-6 scroll-mt-20">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-semibold px-2 py-0.5 rounded bg-blue-950 text-blue-200 border border-blue-700">
                  전기차 차종별 배터리 실명제 공시 대장
                </span>
                <span
                  role="status"
                  aria-live="polite"
                  aria-atomic="true"
                  className="text-xs text-slate-300"
                >
                  {batterySearch.trim() !== '' || selectedSupplierFilter !== 'ALL' || selectedFireStatusFilter !== 'ALL'
                    ? `검색 결과: ${filteredBatteryProfiles.length}개 차종 (전체 ${batteryProfiles.length}개)`
                    : `총 ${batteryProfiles.length}개 차종`}
                </span>
              </div>
              <h2 id="battery-directory-heading" className="text-xl sm:text-2xl font-bold text-white">
                🔋 전기차 배터리 제조사 및 지하주차장 안전 가이드
              </h2>
              <p className="text-sm text-slate-300 mt-0.5">
                국내 판매 주요 전기차의 실제 탑재 배터리 셀 제조사(파라시스, LG, SK, 삼성, CATL, BYD) 및 화재 모니터링 상태를 검색하십시오.
              </p>
            </div>

            {/* Search Input */}
            <form role="search" aria-label="배터리 제조사 및 모델 검색" onSubmit={(e) => e.preventDefault()} className="w-full md:w-72">
              <label htmlFor="battery-search-input" className="sr-only">배터리 제조사 및 모델 검색</label>
              <input
                id="battery-search-input"
                type="search"
                value={batterySearch}
                onChange={(e) => setBatterySearch(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Escape' && batterySearch) {
                    e.stopPropagation();
                    setBatterySearch('');
                  }
                }}
                aria-label="배터리 제조사 및 모델 검색"
                placeholder="모델명, 제조사, 배터리명 검색..."
                className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 min-h-[44px] text-sm text-white placeholder-slate-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
              />
            </form>
          </div>

          {/* Filter Chips: Suppliers & Status */}
          <div role="group" aria-label="배터리 셀 제조사 필터" className="flex flex-wrap items-center gap-2 pt-1 border-t border-slate-800">
            <span className="text-xs font-semibold text-slate-300 mr-2">제조사 필터:</span>
            {supplierFilters.map((s) => (
              <button
                key={s.key}
                type="button"
                onClick={() => setSelectedSupplierFilter(s.key)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
                    e.preventDefault();
                    setSelectedSupplierFilter(s.key);
                  }
                }}
                aria-pressed={selectedSupplierFilter === s.key}
                aria-label={s.key === 'ALL' ? '배터리 셀 제조사 전체 보기' : `배터리 셀 제조사 ${s.label} 필터`}
                className={`px-3 py-1.5 min-h-[44px] inline-flex items-center rounded-lg text-xs font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
                  selectedSupplierFilter === s.key
                    ? 'bg-blue-600 text-white font-bold'
                    : 'bg-slate-900 text-slate-300 hover:bg-slate-800 border border-slate-800'
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>

          <div role="group" aria-label="화재 리스크 상태별 필터" className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-slate-300 mr-2">화재 리스크 상태:</span>
            {FIRE_STATUS_FILTERS.map((f) => (
              <button
                key={f.key}
                type="button"
                onClick={() => setSelectedFireStatusFilter(f.key)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
                    e.preventDefault();
                    setSelectedFireStatusFilter(f.key);
                  }
                }}
                aria-pressed={selectedFireStatusFilter === f.key}
                aria-label={f.key === 'ALL' ? '화재 리스크 상태 전체 보기' : `화재 리스크 ${f.label} 필터`}
                className={`px-3 py-1.5 min-h-[44px] inline-flex items-center rounded-lg text-xs font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
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
            {filteredBatteryProfiles.length === 0 ? (
              <div className="col-span-full bg-slate-950/80 border border-slate-800 rounded-2xl p-8 text-center text-slate-300">
                <span className="text-3xl block mb-2" aria-hidden="true">🔋</span>
                <p className="text-base font-semibold text-slate-200">
                  {batteryProfiles.length === 0
                    ? '데이터베이스에 등록된 배터리 제원 정보가 없습니다'
                    : '조건에 일치하는 배터리 제조사 정보가 없습니다'}
                </p>
                <p className="text-xs text-slate-300 mt-1">
                  {batteryProfiles.length === 0
                    ? '공식 제원 데이터베이스 동기화 상태를 확인해 주십시오.'
                    : '검색어 또는 배터리 공급사/모니터링 필터를 변경해 보세요.'}
                </p>
                {(batterySearch.trim() !== '' || selectedSupplierFilter !== 'ALL' || selectedFireStatusFilter !== 'ALL') && (
                  <button
                    type="button"
                    aria-label="배터리 필터 및 검색 초기화"
                    className="mt-3 px-3.5 py-2 min-h-[44px] inline-flex items-center text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 rounded-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                    onClick={() => {
                      setBatterySearch('');
                      setSelectedSupplierFilter('ALL');
                      setSelectedFireStatusFilter('ALL');
                      document.getElementById('battery-search-input')?.focus();
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
                        e.preventDefault();
                        setBatterySearch('');
                        setSelectedSupplierFilter('ALL');
                        setSelectedFireStatusFilter('ALL');
                        document.getElementById('battery-search-input')?.focus();
                      }
                    }}
                  >
                    필터 및 검색 초기화
                  </button>
                )}
              </div>
            ) : (
              <>
                {displayedBatteryProfiles.map((p) => (
                  <BatterySafetyCard key={p.model_id} profile={p} />
                ))}
                {filteredBatteryProfiles.length > visibleBatteryCount && (
                  <div className="col-span-full pt-4 flex flex-col sm:flex-row items-center justify-center gap-3">
                    <button
                      type="button"
                      onClick={() => setVisibleBatteryCount((prev) => prev + PAGE_SIZE_BATTERIES)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
                          e.preventDefault();
                          setVisibleBatteryCount((prev) => prev + PAGE_SIZE_BATTERIES);
                        }
                      }}
                      aria-label={`배터리 차종 더보기 (현재 ${displayedBatteryProfiles.length}개 / 전체 ${filteredBatteryProfiles.length}개)`}
                      className="px-5 py-2.5 min-h-[44px] rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-blue-300 border border-slate-700 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                    >
                      더보기 (+{Math.min(PAGE_SIZE_BATTERIES, filteredBatteryProfiles.length - visibleBatteryCount)}개)
                    </button>
                    <button
                      type="button"
                      onClick={() => setVisibleBatteryCount(filteredBatteryProfiles.length)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
                          e.preventDefault();
                          setVisibleBatteryCount(filteredBatteryProfiles.length);
                        }
                      }}
                      aria-label={`배터리 차종 전체 ${filteredBatteryProfiles.length}개 펼쳐보기`}
                      className="px-4 py-2.5 min-h-[44px] rounded-xl text-xs font-medium text-slate-300 hover:text-slate-200 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                    >
                      전체 보기 ({filteredBatteryProfiles.length}개 차종)
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </section>

        {/* 5. All Recalls Directory (전체 공식 리콜 캠페인 탐색기) */}
        <section aria-labelledby="all-recalls-heading" className="bg-slate-950 border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-xl space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-semibold px-2 py-0.5 rounded bg-red-950 text-rose-200 border border-red-700">
                  국토교통부 자동차안전연구원 공시
                </span>
                <span
                  role="status"
                  aria-live="polite"
                  aria-atomic="true"
                  className="text-xs text-slate-300"
                >
                  {recallSearch.trim() !== '' || selectedRiskFilter !== 'ALL' || selectedRemedyFilter !== 'ALL'
                    ? `검색 결과: ${filteredRecalls.length}건 (전체 ${recalls.length}건)`
                    : `전체 공시 리콜 대장 (${recalls.length}건)`}
                </span>
              </div>
              <h2 id="all-recalls-heading" className="text-xl sm:text-2xl font-bold text-white">
                📋 전체 전기차 리콜 캠페인 카탈로그
              </h2>
              <p className="text-sm text-slate-300 mt-0.5">
                현대, 기아, 테슬라, 벤츠, BMW, BYD, 쉐보레, 폴스타, 포르쉐 등 주요 브랜드의 결함 내역을 탐색하십시오.
              </p>
            </div>

            {/* Search Input */}
            <form role="search" aria-label="전기차 리콜 캠페인 검색" onSubmit={(e) => e.preventDefault()} className="w-full md:w-72">
              <label htmlFor="recall-catalog-search-input" className="sr-only">전기차 공식 리콜 캠페인 검색</label>
              <input
                id="recall-catalog-search-input"
                type="search"
                value={recallSearch}
                onChange={(e) => setRecallSearch(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Escape' && recallSearch) {
                    e.stopPropagation();
                    setRecallSearch('');
                  }
                }}
                aria-label="전기차 공식 리콜 캠페인 검색"
                placeholder="리콜번호, 제목, 차종 검색..."
                className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 min-h-[44px] text-sm text-white placeholder-slate-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
              />
            </form>
          </div>

          {/* Filter Chips: Risk & Remedy */}
          <div role="group" aria-label="리콜 위험 등급별 필터" className="flex flex-wrap items-center gap-2 pt-1 border-t border-slate-800">
            <span className="text-xs font-semibold text-slate-300 mr-2">위험 등급:</span>
            {RISK_LEVEL_FILTERS.map((rf) => (
              <button
                key={rf.key}
                type="button"
                onClick={() => setSelectedRiskFilter(rf.key)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
                    e.preventDefault();
                    setSelectedRiskFilter(rf.key);
                  }
                }}
                aria-pressed={selectedRiskFilter === rf.key}
                aria-label={rf.key === 'ALL' ? '위험 등급 전체 보기' : `위험 등급 ${rf.label} 필터`}
                className={`px-3 py-1.5 min-h-[44px] inline-flex items-center rounded-lg text-xs font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
                  selectedRiskFilter === rf.key
                    ? 'bg-blue-600 text-white font-bold'
                    : 'bg-slate-900 text-slate-300 hover:bg-slate-800 border border-slate-800'
                }`}
              >
                {rf.label}
              </button>
            ))}
          </div>

          <div role="group" aria-label="시정 조치 유형별 필터" className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-slate-300 mr-2">조치 유형:</span>
            {REMEDY_METHOD_FILTERS.map((rm) => (
              <button
                key={rm.key}
                type="button"
                onClick={() => setSelectedRemedyFilter(rm.key)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
                    e.preventDefault();
                    setSelectedRemedyFilter(rm.key);
                  }
                }}
                aria-pressed={selectedRemedyFilter === rm.key}
                aria-label={rm.key === 'ALL' ? '조치 유형 전체 보기' : `조치 유형 ${rm.label} 필터`}
                className={`px-3 py-1.5 min-h-[44px] inline-flex items-center rounded-lg text-xs font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
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
            <h3 className="sr-only">국토교통부 공시 리콜 캠페인 목록</h3>
            {filteredRecalls.length === 0 ? (
              <div className="bg-slate-950/80 border border-slate-800 rounded-2xl p-8 text-center text-slate-300">
                <span className="text-3xl block mb-2" aria-hidden="true">📋</span>
                <p className="text-base font-semibold text-slate-200">
                  {recalls.length === 0
                    ? '데이터베이스에 등록된 리콜 캠페인 정보가 없습니다'
                    : '일치하는 공시 리콜 및 무상수리 내역이 없습니다'}
                </p>
                <p className="text-xs text-slate-300 mt-1">
                  {recalls.length === 0
                    ? '국토교통부 및 자동차안전연구원 공시 데이터 연동 상태를 확인해 주십시오.'
                    : '검색 키워드 또는 위험도/조치 유형 필터를 재설정해 보세요.'}
                </p>
                {(recallSearch.trim() !== '' || selectedRiskFilter !== 'ALL' || selectedRemedyFilter !== 'ALL') && (
                  <button
                    type="button"
                    aria-label="리콜 필터 및 검색 초기화"
                    className="mt-3 px-3.5 py-2 min-h-[44px] inline-flex items-center text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 rounded-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                    onClick={() => {
                      setRecallSearch('');
                      setSelectedRiskFilter('ALL');
                      setSelectedRemedyFilter('ALL');
                      document.getElementById('recall-catalog-search-input')?.focus();
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
                        e.preventDefault();
                        setRecallSearch('');
                        setSelectedRiskFilter('ALL');
                        setSelectedRemedyFilter('ALL');
                        document.getElementById('recall-catalog-search-input')?.focus();
                      }
                    }}
                  >
                    필터 및 검색 초기화
                  </button>
                )}
              </div>
            ) : (
              <>
                {displayedRecalls.map((campaign) => (
                  <RecallCard
                    key={campaign.id}
                    campaign={campaign}
                    isExpanded={expandedRecallIds.has(campaign.id)}
                    toggleRecallExpansion={toggleRecallExpansion}
                    panelIdPrefix="campaign-list-detail-"
                  />
                ))}
                {filteredRecalls.length > visibleRecallCount && (
                  <div className="pt-4 flex flex-col sm:flex-row items-center justify-center gap-3">
                    <button
                      type="button"
                      onClick={() => setVisibleRecallCount((prev) => prev + PAGE_SIZE_RECALLS)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
                          e.preventDefault();
                          setVisibleRecallCount((prev) => prev + PAGE_SIZE_RECALLS);
                        }
                      }}
                      aria-label={`리콜 캠페인 더보기 (현재 ${displayedRecalls.length}건 / 전체 ${filteredRecalls.length}건)`}
                      className="px-5 py-2.5 min-h-[44px] rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-blue-300 border border-slate-700 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                    >
                      더보기 (+{Math.min(PAGE_SIZE_RECALLS, filteredRecalls.length - visibleRecallCount)}건)
                    </button>
                    <button
                      type="button"
                      onClick={() => setVisibleRecallCount(filteredRecalls.length)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
                          e.preventDefault();
                          setVisibleRecallCount(filteredRecalls.length);
                        }
                      }}
                      aria-label={`리콜 캠페인 전체 ${filteredRecalls.length}건 펼쳐보기`}
                      className="px-4 py-2.5 min-h-[44px] rounded-xl text-xs font-medium text-slate-300 hover:text-slate-200 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                    >
                      전체 보기 ({filteredRecalls.length}건 리콜)
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

export interface BatterySafetyCardProps {
  profile: BatterySafetyProfile;
}

export const BatterySafetyCard = React.memo(function BatterySafetyCard({
  profile: p,
}: BatterySafetyCardProps) {
  const isCritical = p.fire_incident_status === 'CRITICAL_MONITORING';
  const modelName = p.model_name || '차종 미상';
  const brandName = p.brand || '제조사 미상';
  const years = p.years || '전체 연식';
  const cellSupplier = p.cell_supplier || '정보 없음';
  const cellChemistry = p.cell_chemistry || '정보 없음';
  const statusKo = p.fire_incident_status_ko || '모니터링 대상';
  const socLimit = typeof p.recommended_soc_limit === 'number' ? p.recommended_soc_limit : 100;
  const advisory = p.underground_parking_advisory || '아파트 관리사무소 화재 예방 수칙 준수 권장';
  const bmsFeatures = p.bms_safety_features || 'BMS 안전 제어 시스템 탑재';

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
            <span className="text-xs text-slate-300 font-medium">{brandName}</span>
            <h3 className="text-base font-bold text-white">{modelName}</h3>
            <span className="text-[11px] font-mono text-slate-300">{years}</span>
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
            {statusKo}
          </span>
        </div>

        <div className="bg-black/30 rounded-xl p-3 border border-white/5 space-y-1.5 text-xs">
          <div className="flex justify-between">
            <span className="text-slate-300">셀 제조사:</span>
            <span className="font-bold text-white">{cellSupplier}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-300">셀 화학:</span>
            <span className="text-slate-300">{cellChemistry}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-300">완충 권장 한도:</span>
            <span className="font-bold text-blue-300">{socLimit}%</span>
          </div>
        </div>

        <div className="text-xs text-slate-300 pt-1 leading-relaxed">
          <strong className="text-amber-300">지하주차 가이드: </strong>
          {advisory}
        </div>
      </div>

      <div className="pt-2 border-t border-slate-800 text-[11px] text-slate-300 break-words leading-relaxed">
        🛡️ {bmsFeatures}
      </div>
    </div>
  );
});

export interface RecallCardProps {
  campaign: OfficialRecallCampaign;
  isExpanded: boolean;
  toggleRecallExpansion: (id: string) => void;
  panelIdPrefix?: string;
}

export const RecallCard = React.memo(function RecallCard({
  campaign,
  isExpanded,
  toggleRecallExpansion,
  panelIdPrefix = 'campaign-detail-',
}: RecallCardProps) {
  const toggleButtonRef = useRef<HTMLButtonElement>(null);

  const handleCardKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (e.key === 'Escape' && isExpanded) {
        e.stopPropagation();
        e.preventDefault();
        toggleRecallExpansion(campaign.id);
        toggleButtonRef.current?.focus();
      }
    },
    [campaign.id, isExpanded, toggleRecallExpansion]
  );

  const handleToggleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
        e.preventDefault();
        toggleRecallExpansion(campaign.id);
      }
    },
    [campaign.id, toggleRecallExpansion]
  );

  const targetModel = campaign.target_model || '해당 차종';
  const brand = campaign.brand || '해당 제조사';
  const years = campaign.target_model_years || '전체 연식';
  const defectDetail = campaign.defect_detail || '공식 결함 정보 공시 대조 중입니다.';
  const remedyAction = campaign.remedy_action || '제조사 공식 서비스센터 방문 무상 점검 및 시정 조치';
  const emergencyGuide = campaign.consumer_emergency_guide || '이상 징후 발생 시 즉시 안전한 장소에 정차 후 긴급 출동 요청';
  const contact = campaign.service_center_contact || '제조사 고객센터';
  const safeLink = sanitizeSafeUrl(campaign.official_link);
  const isExternal = isExternalUrl(safeLink);

  return (
    <div
      onKeyDown={handleCardKeyDown}
      className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition space-y-3"
    >
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className="text-xs font-mono px-2.5 py-0.5 rounded bg-blue-950 text-blue-200 border border-blue-700">
              {campaign.campaign_no || '미부여'}
            </span>
            <span className="text-xs font-semibold text-slate-300">
              {brand} • {targetModel} ({years})
            </span>
            <span
              className={`text-[11px] font-bold px-2 py-0.5 rounded border ${
                campaign.risk_level === 'FIRE_HAZARD'
                  ? 'bg-red-950 text-rose-200 border-red-700'
                  : campaign.risk_level === 'LOSS_OF_POWER'
                  ? 'bg-orange-950 text-amber-200 border-orange-700'
                  : campaign.risk_level === 'BRAKE_STEERING'
                  ? 'bg-purple-950 text-purple-200 border-purple-700'
                  : campaign.risk_level === 'SOFTWARE_REGULATION'
                  ? 'bg-cyan-950 text-cyan-200 border-cyan-700'
                  : 'bg-slate-800 text-slate-200 border-slate-700'
              }`}
            >
              {campaign.risk_level_ko || '안전 리콜'}
            </span>
            <span
              className={`text-[11px] font-medium px-2 py-0.5 rounded border ${
                campaign.remedy_type === 'OTA_WIRELESS'
                  ? 'bg-emerald-950 text-emerald-200 border-emerald-700'
                  : campaign.remedy_type === 'HARDWARE_REPLACE'
                  ? 'bg-rose-950 text-rose-200 border-rose-700'
                  : campaign.remedy_type === 'SOFTWARE_UPDATE_SERVICE'
                  ? 'bg-blue-950 text-blue-200 border-blue-700'
                  : 'bg-slate-800 text-slate-200 border-slate-700'
              }`}
            >
              {campaign.remedy_type_ko || '무상 수리'}
            </span>
          </div>
          <h4 id={`${panelIdPrefix}title-${campaign.id}`} className="text-base font-bold text-white">
            {campaign.defect_title}
          </h4>
        </div>

        <button
          ref={toggleButtonRef}
          type="button"
          aria-expanded={isExpanded}
          aria-controls={`${panelIdPrefix}${campaign.id}`}
          aria-label={`${campaign.target_model} ${campaign.defect_title} ${isExpanded ? '상세 접기' : '상세 및 행동요령 펼치기'}`}
          onClick={() => toggleRecallExpansion(campaign.id)}
          onKeyDown={handleToggleKeyDown}
          className="self-start text-xs text-blue-300 hover:text-blue-200 font-semibold px-2.5 py-1 min-h-[44px] inline-flex items-center justify-center rounded bg-slate-800 border border-slate-700 hover:bg-slate-700 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
        >
          {isExpanded ? '닫기 ▲' : '상세 및 행동요령 ▼'}
        </button>
      </div>

      <p className="text-xs text-slate-300 line-clamp-2 leading-relaxed">
        {defectDetail}
      </p>

      <div
        id={`${panelIdPrefix}${campaign.id}`}
        role="region"
        aria-labelledby={`${panelIdPrefix}title-${campaign.id}`}
        hidden={!isExpanded}
        className={`${!isExpanded ? 'hidden ' : ''}space-y-3 pt-3 border-t border-slate-800 text-xs`}
      >
        <div>
          <span className="font-semibold text-slate-200">생산 기간: </span>
          <span className="font-mono text-slate-300">{campaign.production_date_range || '공식 공시 참조'}</span>
          <span className="ml-3 font-semibold text-slate-200">대상 대수: </span>
          <span className="text-amber-300 font-semibold">
            {Number.isFinite(campaign?.affected_kdm_units)
              ? campaign.affected_kdm_units.toLocaleString()
              : '0'}대
          </span>
        </div>

        <div className="bg-slate-950 rounded-lg p-3 border border-slate-800/80 space-y-1">
          <span className="font-bold text-blue-300">무상 수리 내용: </span>
          <p className="text-slate-300">{remedyAction}</p>
        </div>

        <div className="bg-red-950/30 rounded-lg p-3 border border-red-900/50 space-y-1">
          <span className="font-bold text-red-300">🚨 차주 긴급 대처 행동요령: </span>
          <p className="text-slate-300">{emergencyGuide}</p>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between text-slate-300 pt-1 gap-2">
          <span>고객센터: <strong className="text-white">{contact}</strong></span>
          {safeLink !== '#' ? (
            isExternal ? (
              <a
                href={safeLink}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`${brand} ${campaign.defect_title} 공식 웹사이트 바로가기 (새 창에서 열림)`}
                className="text-blue-300 hover:text-blue-200 inline-flex items-center gap-1 min-h-[44px] px-2 rounded-lg hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
              >
                공식 웹사이트 바로가기 &rarr;
                <span className="sr-only"> (새 창에서 열림)</span>
              </a>
            ) : (
              <a
                href={safeLink}
                aria-label={`${brand} ${campaign.defect_title} 관련 안내 바로가기`}
                className="text-blue-300 hover:text-blue-200 inline-flex items-center gap-1 min-h-[44px] px-2 rounded-lg hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
              >
                관련 안내 바로가기 &rarr;
              </a>
            )
          ) : null}
        </div>
      </div>
    </div>
  );
});

export interface BatterySafetyTableViewProps {
  profiles: BatterySafetyProfile[];
}

export const BatterySafetyTableView = React.memo(function BatterySafetyTableView({
  profiles,
}: BatterySafetyTableViewProps) {
  return (
    <div
      tabIndex={0}
      role="region"
      aria-label="전기차 차종별 배터리 셀 제조사 및 안전 공시 대장 스크롤 영역"
      className="overflow-x-auto table-scroll-container rounded-2xl border border-slate-800 bg-slate-950 shadow-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
    >
      <div className="sm:hidden flex items-center justify-between px-3 py-1.5 text-[11px] font-medium text-slate-300 bg-slate-900 border-b border-slate-800 select-none" aria-hidden="true"><span>← 좌우로 밀어서 배터리 제조사 확인</span><span className="text-[10px] text-blue-300 font-semibold">가로 스크롤 ↔</span></div>
      <table
        className="w-full min-w-[760px] text-left text-xs sm:text-sm border-collapse"
        aria-label="전기차 차종별 배터리 실명제 및 화재 안전 공시 표"
      >
        <caption className="sr-only">
          전기차 차종별 배터리 셀 제조사, 배터리 화학 제원, 화재 리스크 모니터링 상태, 권장 완충 한도 및 지하주차 안전 가이드 공시 데이터 표
        </caption>
        <thead>
          <tr className="bg-slate-900 border-b border-slate-800 text-slate-300 text-xs font-bold">
            <th scope="col" className="p-3.5 font-bold">모델명</th>
            <th scope="col" className="p-3.5 font-bold">제조사</th>
            <th scope="col" className="p-3.5 font-bold">셀 공급사</th>
            <th scope="col" className="p-3.5 font-bold">셀 화학</th>
            <th scope="col" className="p-3.5 font-bold">생산 연식</th>
            <th scope="col" className="p-3.5 font-bold text-center">화재 안전 상태</th>
            <th scope="col" className="p-3.5 font-bold text-center">완충 한도</th>
            <th scope="col" className="p-3.5 font-bold">지하주차 가이드</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/80">
          {profiles.map((p) => {
            const isCritical = p.fire_incident_status === 'CRITICAL_MONITORING';
            return (
              <tr
                key={p.model_id}
                className={`transition hover:bg-slate-900/60 ${
                  isCritical ? 'bg-red-950/20' : ''
                }`}
              >
                <th scope="row" className="p-3.5 font-bold text-white whitespace-nowrap">
                  {p.model_name || '차종 미상'}
                </th>
                <td className="p-3.5 text-slate-200 whitespace-nowrap">{p.brand || '제조사 미상'}</td>
                <td className="p-3.5 font-bold text-white whitespace-nowrap">{p.cell_supplier || '정보 없음'}</td>
                <td className="p-3.5 text-slate-300 font-mono text-xs whitespace-nowrap">{p.cell_chemistry || '정보 없음'}</td>
                <td className="p-3.5 text-slate-300 font-mono text-xs whitespace-nowrap">{p.years || '전체 연식'}</td>
                <td className="p-3.5 text-center whitespace-nowrap">
                  <span
                    className={`text-[11px] font-bold px-2.5 py-0.5 rounded border inline-flex items-center justify-center ${
                      isCritical
                        ? 'bg-red-950 text-rose-200 border-red-700 animate-pulse motion-reduce:animate-none'
                        : p.fire_incident_status === 'RECALLED_RESOLVED'
                        ? 'bg-amber-950 text-amber-200 border-amber-700'
                        : 'bg-emerald-950 text-emerald-200 border-emerald-700'
                    }`}
                  >
                    {p.fire_incident_status_ko || '모니터링 대상'}
                  </span>
                </td>
                <td className="p-3.5 text-center font-bold text-blue-300 whitespace-nowrap">
                  {typeof p.recommended_soc_limit === 'number' ? `${p.recommended_soc_limit}%` : '100%'}
                </td>
                <td className="p-3.5 text-xs text-slate-300 max-w-xs truncate" title={p.underground_parking_advisory || ''}>
                  {p.underground_parking_advisory || '화재 예방 수칙 준수'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
});

export interface RecallTableViewProps {
  recalls: OfficialRecallCampaign[];
  expandedRecallIds: Set<string>;
  toggleRecallExpansion: (id: string) => void;
  panelIdPrefix?: string;
}

export const RecallTableView = React.memo(function RecallTableView({
  recalls,
  expandedRecallIds,
  toggleRecallExpansion,
  panelIdPrefix = 'table-recall-detail-',
}: RecallTableViewProps) {
  return (
    <div
      tabIndex={0}
      role="region"
      aria-label="국토교통부 공시 전기차 리콜 캠페인 카탈로그 대장 스크롤 영역"
      className="overflow-x-auto table-scroll-container rounded-2xl border border-slate-800 bg-slate-950 shadow-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
    >
      <div className="sm:hidden flex items-center justify-between px-3 py-1.5 text-[11px] font-medium text-slate-300 bg-slate-900 border-b border-slate-800 select-none" aria-hidden="true"><span>← 좌우로 밀어서 공식 리콜 내역 확인</span><span className="text-[10px] text-blue-300 font-semibold">가로 스크롤 ↔</span></div>
      <table
        className="w-full min-w-[800px] text-left text-xs sm:text-sm border-collapse"
        aria-label="국토교통부 공시 전기차 결함 리콜 캠페인 카탈로그 표"
      >
        <caption className="sr-only">
          국토교통부 및 자동차안전연구원 공시 전기차 결함 시정조치 캠페인 관리번호, 대상 모델, 결함명, 위험 등급, 시정 조치 유형 및 대상 대수 목록 표
        </caption>
        <thead>
          <tr className="bg-slate-900 border-b border-slate-800 text-slate-300 text-xs font-bold">
            <th scope="col" className="p-3.5 font-bold">관리번호</th>
            <th scope="col" className="p-3.5 font-bold">제조사</th>
            <th scope="col" className="p-3.5 font-bold">대상 모델</th>
            <th scope="col" className="p-3.5 font-bold">결함 내용</th>
            <th scope="col" className="p-3.5 font-bold text-center">위험 등급</th>
            <th scope="col" className="p-3.5 font-bold text-center">조치 유형</th>
            <th scope="col" className="p-3.5 font-bold text-right">대상 대수</th>
            <th scope="col" className="p-3.5 font-bold text-center">상세</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/80">
          {recalls.map((campaign) => {
            const isExpanded = expandedRecallIds.has(campaign.id);
            const safeLink = sanitizeSafeUrl(campaign.official_link);
            const isExternal = isExternalUrl(safeLink);
            return (
              <React.Fragment key={campaign.id}>
                <tr className={`transition hover:bg-slate-900/60 ${isExpanded ? 'bg-slate-900/40' : ''}`}>
                  <th scope="row" className="p-3.5 font-mono text-blue-300 font-bold whitespace-nowrap">
                    {campaign.campaign_no || '미부여'}
                  </th>
                  <td className="p-3.5 text-slate-200 whitespace-nowrap">{campaign.brand || '해당 제조사'}</td>
                  <td className="p-3.5 font-medium text-white whitespace-nowrap">
                    {campaign.target_model} <span className="text-xs text-slate-300">({campaign.target_model_years})</span>
                  </td>
                  <td className="p-3.5 text-slate-200 max-w-xs truncate" title={campaign.defect_title}>
                    {campaign.defect_title}
                  </td>
                  <td className="p-3.5 text-center whitespace-nowrap">
                    <span
                      className={`text-[11px] font-bold px-2 py-0.5 rounded border inline-flex items-center justify-center ${
                        campaign.risk_level === 'FIRE_HAZARD'
                          ? 'bg-red-950 text-rose-200 border-red-700'
                          : campaign.risk_level === 'LOSS_OF_POWER'
                          ? 'bg-orange-950 text-amber-200 border-orange-700'
                          : campaign.risk_level === 'BRAKE_STEERING'
                          ? 'bg-purple-950 text-purple-200 border-purple-700'
                          : campaign.risk_level === 'SOFTWARE_REGULATION'
                          ? 'bg-cyan-950 text-cyan-200 border-cyan-700'
                          : 'bg-slate-800 text-slate-200 border-slate-700'
                      }`}
                    >
                      {campaign.risk_level_ko || '안전 리콜'}
                    </span>
                  </td>
                  <td className="p-3.5 text-center whitespace-nowrap">
                    <span
                      className={`text-[11px] font-medium px-2 py-0.5 rounded border inline-flex items-center justify-center ${
                        campaign.remedy_type === 'OTA_WIRELESS'
                          ? 'bg-emerald-950 text-emerald-200 border-emerald-700'
                          : campaign.remedy_type === 'HARDWARE_REPLACE'
                          ? 'bg-rose-950 text-rose-200 border-rose-700'
                          : campaign.remedy_type === 'SOFTWARE_UPDATE_SERVICE'
                          ? 'bg-blue-950 text-blue-200 border-blue-700'
                          : 'bg-slate-800 text-slate-200 border-slate-700'
                      }`}
                    >
                      {campaign.remedy_type_ko || '무상 수리'}
                    </span>
                  </td>
                  <td className="p-3.5 text-right font-mono text-amber-300 font-bold whitespace-nowrap">
                    {Number.isFinite(campaign.affected_kdm_units)
                      ? `${campaign.affected_kdm_units.toLocaleString()}대`
                      : '0대'}
                  </td>
                  <td className="p-3.5 text-center whitespace-nowrap">
                    <button
                      type="button"
                      aria-expanded={isExpanded}
                      aria-controls={`${panelIdPrefix}${campaign.id}`}
                      aria-label={`${campaign.target_model} ${campaign.defect_title} ${isExpanded ? '상세 접기' : '상세 펼치기'}`}
                      onClick={() => toggleRecallExpansion(campaign.id)}
                      className="text-xs text-blue-300 hover:text-blue-200 font-semibold px-2.5 py-1 min-h-[36px] inline-flex items-center justify-center rounded bg-slate-800 border border-slate-700 hover:bg-slate-700 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                    >
                      {isExpanded ? '닫기 ▲' : '상세 ▼'}
                    </button>
                  </td>
                </tr>
                {isExpanded && (
                  <tr id={`${panelIdPrefix}${campaign.id}`} className="bg-slate-900/80">
                    <td colSpan={8} className="p-4 border-t border-slate-800">
                      <div className="space-y-3 text-xs">
                        <div className="flex flex-wrap items-center gap-4 text-slate-300">
                          <div>
                            <span className="font-semibold text-slate-200">생산 기간: </span>
                            <span className="font-mono text-slate-300">{campaign.production_date_range || '공식 공시 참조'}</span>
                          </div>
                          <div>
                            <span className="font-semibold text-slate-200">고객센터: </span>
                            <span className="text-white font-bold">{campaign.service_center_contact || '제조사 고객센터'}</span>
                          </div>
                        </div>
                        <p className="text-slate-300 leading-relaxed font-normal">
                          <strong className="text-slate-100 font-semibold">결함 상세: </strong>
                          {campaign.defect_detail}
                        </p>
                        <div className="bg-slate-950 rounded-lg p-3 border border-slate-800/80 space-y-1">
                          <span className="font-bold text-blue-300">시정 조치 내용: </span>
                          <p className="text-slate-300">{campaign.remedy_action}</p>
                        </div>
                        <div className="bg-red-950/30 rounded-lg p-3 border border-red-900/50 space-y-1">
                          <span className="font-bold text-red-300">🚨 차주 긴급 대처 행동요령: </span>
                          <p className="text-slate-300">{campaign.consumer_emergency_guide}</p>
                        </div>
                        {safeLink !== '#' && (
                          <div className="pt-1">
                            {isExternal ? (
                              <a
                                href={safeLink}
                                target="_blank"
                                rel="noopener noreferrer"
                                aria-label={`${campaign.brand} ${campaign.defect_title} 공식 웹사이트 바로가기 (새 창에서 열림)`}
                                className="text-blue-300 hover:text-blue-200 inline-flex items-center gap-1 min-h-[36px] px-2 rounded-lg hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                              >
                                공식 웹사이트 바로가기 &rarr;
                                <span className="sr-only"> (새 창에서 열림)</span>
                              </a>
                            ) : (
                              <a
                                href={safeLink}
                                aria-label={`${campaign.brand} ${campaign.defect_title} 관련 안내 바로가기`}
                                className="text-blue-300 hover:text-blue-200 inline-flex items-center gap-1 min-h-[36px] px-2 rounded-lg hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                              >
                                관련 안내 바로가기 &rarr;
                              </a>
                            )}
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
});
