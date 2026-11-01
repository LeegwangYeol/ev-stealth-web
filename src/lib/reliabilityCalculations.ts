/**
 * Pure calculation utilities, type definitions, and styling helpers for EV Reliability Analytics.
 * This module has ZERO dependencies on heavy JSON data files, enabling client bundles
 * to remain lean without duplicating data payloads.
 */

// ==========================================
// 1. DOMAIN ENUMS & INTERFACES (from @/types/reliability)
// ==========================================

export type {
  DefectCategoryKey,
  ModelYearVerdict,
  YearEvaluation,
  ModelReliability,
  BrandReliability,
  DefectCategoryMetadata,
  RepairCostMatrixItem,
  ReliabilityTrendsDatabase,
  EnrichedModelItem,
  ReliabilityKPIs,
} from '@/types/reliability';

import type {
  ModelYearVerdict,
  YearEvaluation,
  BrandReliability,
  ReliabilityTrendsDatabase,
  EnrichedModelItem,
} from '@/types/reliability';

/**
 * Returns a flattened array of all models enriched with brand information from a given database.
 * Pure function: operates directly on the provided data without importing raw JSON.
 */
export function getAllEnrichedModels(data?: ReliabilityTrendsDatabase): EnrichedModelItem[] {
  if (!data || !Array.isArray(data.brands)) return [];
  const result: EnrichedModelItem[] = [];
  const brands = data.brands;

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
 * Pure UI styling helper.
 */
export function getVerdictBadgeInfo(verdict: ModelYearVerdict | string): {
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
 * Pure UI calculation helper.
 */
export function getDsiSeverityLevel(dsi: number): {
  level: 'CRITICAL' | 'HIGH' | 'MODERATE' | 'LOW';
  label: string;
  colorClass: string;
  barBgClass: string;
  textColor: string;
} {
  const safeDsi = Number.isFinite(dsi) ? Math.max(0, dsi) : 0;

  if (safeDsi >= 80) {
    return {
      level: 'CRITICAL',
      label: '치명적 위험 (Critical)',
      colorClass: 'text-rose-600',
      barBgClass: 'bg-rose-500',
      textColor: 'text-rose-600',
    };
  }
  if (safeDsi >= 60) {
    return {
      level: 'HIGH',
      label: '높은 결함률 (High Risk)',
      colorClass: 'text-amber-800',
      barBgClass: 'bg-amber-500',
      textColor: 'text-amber-800',
    };
  }
  if (safeDsi >= 35) {
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
 * Pure UI styling helper.
 */
export function getGradeBadgeStyle(grade: 'A+' | 'A' | 'B' | 'C' | 'D' | 'F' | string): {
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
  const brands = Array.isArray(data?.brands) ? data.brands : [];
  return brands.find(
    (b) =>
      (b?.id && b.id.toLowerCase() === normalized) ||
      (b?.name_ko && b.name_ko.toLowerCase().includes(normalized)) ||
      (b?.name_en && b.name_en.toLowerCase().includes(normalized))
  );
}
