import rawTrendsData from '../data/ev_reliability_trends.json' with { type: 'json' };

export type DefectCategoryKey =
  | 'BATTERY_CHARGING'
  | 'DRIVING_POWERTRAIN'
  | 'SOFTWARE_ELECTRONICS'
  | 'BUILD_QUALITY'
  | 'SERVICE_REPAIR_COST'
  | 'COLD_WEATHER';

export type ModelYearVerdict = 'BUY_SAFE' | 'CAUTION' | 'AVOID';

export interface YearEvaluation {
  year: number;
  verdict: ModelYearVerdict;
  dsi_score: number; // 0 to 100 (higher = more severe defect profile)
  incident_rate: number; // percentage of reported vehicles with major defects
  primary_defect: string;
  estimated_repair_cost: string;
  chronic_symptoms: string[];
  raw_quote: string;
}

export interface ModelReliability {
  id: string;
  name: string;
  segment: string;
  brand_id: string;
  overall_grade: 'A+' | 'A' | 'B' | 'C' | 'D' | 'F';
  avg_dsi: number;
  year_evaluations: YearEvaluation[];
  top_category: DefectCategoryKey;
}

export interface BrandReliability {
  id: string;
  name_ko: string;
  name_en: string;
  country: string;
  overall_dsi: number;
  total_reports: number;
  critical_issue_rate: number; // %
  category_distribution: Record<DefectCategoryKey, { count: number; percentage: number }>;
  models: ModelReliability[];
}

export interface DefectCategoryMetadata {
  code: DefectCategoryKey;
  label_ko: string;
  description: string;
  icon_name: string;
  industry_share_pct: number;
  avg_repair_cost_range: string;
}

export interface RepairCostMatrixItem {
  component_name: string;
  affected_systems: string;
  avg_cost_krw: string;
  standard_warranty: string;
  high_risk_models: string[];
  critical_warning: string;
}

export interface ReliabilityTrendsDatabase {
  metadata: {
    version: string;
    updated_at: string;
    total_records_analyzed: number;
    brands_count: number;
    models_count: number;
    avg_industry_dsi: number;
  };
  categories: DefectCategoryMetadata[];
  repair_cost_matrix: RepairCostMatrixItem[];
  brands: BrandReliability[];
}

export interface EnrichedModelItem extends ModelReliability {
  brand_name_ko: string;
  brand_name_en: string;
  brand_country: string;
}

/**
 * Fallback baseline in case JSON parsing encounters any anomaly.
 */
const DEFAULT_FALLBACK_DATABASE: ReliabilityTrendsDatabase = {
  metadata: {
    version: '1.0.0',
    updated_at: '2026-09-16T12:00:00Z',
    total_records_analyzed: 1280,
    brands_count: 9,
    models_count: 22,
    avg_industry_dsi: 64.2,
  },
  categories: [
    {
      code: 'BATTERY_CHARGING',
      label_ko: '배터리 & 고전압 충전',
      description: '고전압 배터리 셀 열화, 화재 리콜 위험, 급속/완속 충전 중단',
      icon_name: 'BatteryCharging',
      industry_share_pct: 38.4,
      avg_repair_cost_range: '2,500만 ~ 7,500만 원',
    },
    {
      code: 'DRIVING_POWERTRAIN',
      label_ko: '모터·감속기·ICCU 구동계',
      description: 'ICCU 폭파 및 주행 중 동력 상실, 감속기 기어 마모 소음',
      icon_name: 'Zap',
      industry_share_pct: 26.2,
      avg_repair_cost_range: '520만 ~ 1,450만 원',
    },
    {
      code: 'SOFTWARE_ELECTRONICS',
      label_ko: 'OTA·BMS·인포테인먼트',
      description: 'OTA 업데이트 벽돌 현상, BMS 오류로 인한 시동 불가',
      icon_name: 'Cpu',
      industry_share_pct: 14.8,
      avg_repair_cost_range: '150만 ~ 420만 원',
    },
    {
      code: 'BUILD_QUALITY',
      label_ko: '단차·도장·누수·조립 품질',
      description: '트렁크/도어 유격 단차, 우천 시 실내 누수, 테일램프 결로',
      icon_name: 'Wrench',
      industry_share_pct: 9.5,
      avg_repair_cost_range: '80만 ~ 350만 원',
    },
    {
      code: 'SERVICE_REPAIR_COST',
      label_ko: '보증 외 수리비 & 정비성',
      description: '부품 수급 지연, 경미한 하부 충격 시 배터리 전손 처리',
      icon_name: 'Coins',
      industry_share_pct: 6.1,
      avg_repair_cost_range: '200만 ~ 7,500만 원',
    },
    {
      code: 'COLD_WEATHER',
      label_ko: '혹한기 저온 결함 & 히트펌프',
      description: '영하 기온 시 히트펌프 옥토밸브 고착으로 난방 정지',
      icon_name: 'Snowflake',
      industry_share_pct: 5.0,
      avg_repair_cost_range: '320만 ~ 510만 원',
    },
  ],
  repair_cost_matrix: [],
  brands: [],
};

/**
 * Safely loads the master EV Reliability & Defect Trends database.
 * Strictly guarantees non-null, valid array/object shapes with defensive fallbacks.
 */
export function getReliabilityTrendsData(): ReliabilityTrendsDatabase {
  try {
    if (!rawTrendsData) {
      return DEFAULT_FALLBACK_DATABASE;
    }

    const data = rawTrendsData as unknown as ReliabilityTrendsDatabase;

    const metadata = {
      version: data.metadata?.version || '1.0.0',
      updated_at: data.metadata?.updated_at || '2026-09-16T12:00:00Z',
      total_records_analyzed: Number(data.metadata?.total_records_analyzed || 1280),
      brands_count: Array.isArray(data.brands) ? data.brands.length : 9,
      models_count: Array.isArray(data.brands)
        ? data.brands.reduce((acc, b) => acc + (Array.isArray(b.models) ? b.models.length : 0), 0)
        : 22,
      avg_industry_dsi: Number(data.metadata?.avg_industry_dsi || 64.2),
    };

    const categories = Array.isArray(data.categories) && data.categories.length > 0
      ? data.categories
      : DEFAULT_FALLBACK_DATABASE.categories;

    const repair_cost_matrix = Array.isArray(data.repair_cost_matrix)
      ? data.repair_cost_matrix
      : [];

    const brands = Array.isArray(data.brands)
      ? data.brands
          .filter((b): b is BrandReliability => Boolean(b && typeof b === 'object'))
          .map((b) => ({
            ...b,
            category_distribution:
              b.category_distribution && typeof b.category_distribution === 'object'
                ? b.category_distribution
                : ({} as Record<DefectCategoryKey, { count: number; percentage: number }>),
            models: Array.isArray(b.models)
              ? b.models
                  .filter((m): m is ModelReliability => Boolean(m && typeof m === 'object'))
                  .map((m) => ({
                    ...m,
                    year_evaluations: Array.isArray(m.year_evaluations)
                      ? m.year_evaluations.filter(
                          (y): y is YearEvaluation => Boolean(y && typeof y === 'object')
                        )
                      : [],
                  }))
              : [],
          }))
      : [];

    return {
      metadata,
      categories,
      repair_cost_matrix,
      brands,
    };
  } catch (error) {
    console.error('[getReliabilityTrendsData] Failed to load trends data safely:', error);
    return DEFAULT_FALLBACK_DATABASE;
  }
}

/**
 * Returns a flattened array of all models enriched with brand information.
 */
export function getAllEnrichedModels(data?: ReliabilityTrendsDatabase): EnrichedModelItem[] {
  const db = data || getReliabilityTrendsData();
  const result: EnrichedModelItem[] = [];
  const brands = Array.isArray(db?.brands) ? db.brands : [];

  for (const brand of brands) {
    if (!brand || typeof brand !== 'object') continue;
    const models = Array.isArray(brand.models) ? brand.models : [];
    for (const model of models) {
      if (!model || typeof model !== 'object') continue;
      result.push({
        ...model,
        year_evaluations: Array.isArray(model.year_evaluations)
          ? model.year_evaluations.filter((y) => Boolean(y && typeof y === 'object'))
          : [],
        brand_name_ko: brand.name_ko || '',
        brand_name_en: brand.name_en || '',
        brand_country: brand.country || '',
      });
    }
  }

  return result;
}

/**
 * Returns badge styling and text for a given ModelYearVerdict.
 */
export function getVerdictBadgeInfo(verdict: ModelYearVerdict): {
  label: string;
  badgeClass: string;
  borderClass: string;
  bgClass: string;
  textClass: string;
  icon: string;
} {
  switch (verdict) {
    case 'AVOID':
      return {
        label: '🚫 구매 회피 (AVOID)',
        badgeClass: 'bg-rose-100 text-rose-800 border-rose-300',
        borderClass: 'border-rose-400',
        bgClass: 'bg-rose-500',
        textClass: 'text-rose-700',
        icon: '🚫',
      };
    case 'CAUTION':
      return {
        label: '⚠️ 주의 요망 (CAUTION)',
        badgeClass: 'bg-amber-100 text-amber-900 border-amber-300',
        borderClass: 'border-amber-400',
        bgClass: 'bg-amber-400',
        textClass: 'text-amber-700',
        icon: '⚠️',
      };
    case 'BUY_SAFE':
      return {
        label: '✅ 안심 추천 (BUY SAFE)',
        badgeClass: 'bg-emerald-100 text-emerald-800 border-emerald-300',
        borderClass: 'border-emerald-400',
        bgClass: 'bg-emerald-500',
        textClass: 'text-emerald-700',
        icon: '✅',
      };
    default:
      return {
        label: 'ℹ️ 정보 부족',
        badgeClass: 'bg-slate-100 text-slate-700 border-slate-300',
        borderClass: 'border-slate-300',
        bgClass: 'bg-slate-400',
        textClass: 'text-slate-600',
        icon: 'ℹ️',
      };
  }
}

/**
 * Returns severity description and color accents based on DSI score.
 */
export function getDsiSeverityLevel(dsi: number): {
  level: 'CRITICAL' | 'HIGH' | 'MODERATE' | 'LOW';
  label: string;
  colorClass: string;
  barBgClass: string;
  textColor: string;
} {
  if (dsi >= 80) {
    return {
      level: 'CRITICAL',
      label: '치명적 위험 (Critical)',
      colorClass: 'text-rose-600',
      barBgClass: 'bg-rose-500',
      textColor: 'text-rose-600',
    };
  }
  if (dsi >= 60) {
    return {
      level: 'HIGH',
      label: '높은 결함률 (High Risk)',
      colorClass: 'text-amber-800',
      barBgClass: 'bg-amber-500',
      textColor: 'text-amber-800',
    };
  }
  if (dsi >= 35) {
    return {
      level: 'MODERATE',
      label: '주의 필요 (Moderate)',
      colorClass: 'text-yellow-900',
      barBgClass: 'bg-yellow-400',
      textColor: 'text-yellow-900',
    };
  }
  return {
    level: 'LOW',
    label: '안정적 내구성 (Safe & Reliable)',
    colorClass: 'text-emerald-800',
    barBgClass: 'bg-emerald-500',
    textColor: 'text-emerald-800',
  };
}

/**
 * Returns styling for the overall grade badge.
 */
export function getGradeBadgeStyle(grade: 'A+' | 'A' | 'B' | 'C' | 'D' | 'F'): {
  bg: string;
  text: string;
  border: string;
} {
  switch (grade) {
    case 'A+':
    case 'A':
      return { bg: 'bg-emerald-100', text: 'text-emerald-800', border: 'border-emerald-300' };
    case 'B':
      return { bg: 'bg-blue-100', text: 'text-blue-800', border: 'border-blue-300' };
    case 'C':
      return { bg: 'bg-amber-100', text: 'text-amber-900', border: 'border-amber-300' };
    case 'D':
      return { bg: 'bg-orange-100', text: 'text-orange-900', border: 'border-orange-300' };
    case 'F':
      return { bg: 'bg-rose-100', text: 'text-rose-900', border: 'border-rose-300' };
    default:
      return { bg: 'bg-slate-100', text: 'text-slate-800', border: 'border-slate-300' };
  }
}

/**
 * Finds a specific model by ID from the reliability trends dataset,
 * gracefully handling missing, null, or malformed defect records.
 */
export function getModelReliabilityById(
  modelId: string,
  data?: ReliabilityTrendsDatabase
): EnrichedModelItem | undefined {
  if (!modelId || typeof modelId !== 'string') return undefined;
  const normalized = modelId.trim().toLowerCase().replace(/[\s\-_]+/g, '');
  if (!normalized) return undefined;
  const allModels = getAllEnrichedModels(data);
  return allModels.find((m) => {
    const mIdNorm = (m?.id || '').toLowerCase().replace(/[\s\-_]+/g, '');
    const mNameNorm = (m?.name || '').toLowerCase().replace(/[\s\-_]+/g, '');
    return mIdNorm === normalized || mNameNorm.includes(normalized) || normalized.includes(mIdNorm);
  });
}

/**
 * Returns all year evaluations / defect records for a specific model,
 * ensuring the returned array is safe, non-null, and filtered of malformed entries.
 */
export function getDefectsForModel(
  modelId: string,
  data?: ReliabilityTrendsDatabase
): YearEvaluation[] {
  const model = getModelReliabilityById(modelId, data);
  if (!model || !Array.isArray(model.year_evaluations)) return [];
  return model.year_evaluations.filter((y) => Boolean(y && typeof y === 'object' && y.verdict));
}

/**
 * Finds a specific brand by ID or name from the reliability dataset.
 */
export function getBrandReliabilityById(
  brandId: string,
  data?: ReliabilityTrendsDatabase
): BrandReliability | undefined {
  if (!brandId || typeof brandId !== 'string') return undefined;
  const normalized = brandId.trim().toLowerCase();
  if (!normalized) return undefined;
  const db = data || getReliabilityTrendsData();
  const brands = Array.isArray(db?.brands) ? db.brands : [];
  return brands.find(
    (b) =>
      (b?.id && b.id.toLowerCase() === normalized) ||
      (b?.name_ko && b.name_ko.toLowerCase().includes(normalized)) ||
      (b?.name_en && b.name_en.toLowerCase().includes(normalized))
  );
}

