import rawReportData from '../data/daily_reports.json' with { type: 'json' };
import { sanitizeSafeUrl, sanitizeText } from './sanitizeUrl';

export type DefectCategoryCode =
  | 'BATTERY_CHARGING'
  | 'DRIVING_POWERTRAIN'
  | 'BUILD_QUALITY'
  | 'SOFTWARE_ELECTRONICS'
  | 'SERVICE_REPAIR_COST'
  | string;

export type SeverityLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'WARNING' | 'CAUTION' | 'INFO' | string;

export interface DefectReportItem {
  id: string;
  source: 'bobaedream' | 'dcinside' | string;
  url: string;
  title: string;
  date: string;
  created_at?: string;
  vehicle_model: string;
  vehicle_brand?: string;
  target_vehicle?: string;
  defect_category: DefectCategoryCode;
  defect_category_ko: string;
  summary: string;
  verbatim_quote: string;
  slang_tags: string[];
  sentiment_score: number;
  sentiment_polarity?: number;
  severity: SeverityLevel;
  severity_index?: number;
  author?: string;
  is_authentic_defect?: boolean;
  dsi_breakdown?: {
    safety?: number;
    functional?: number;
    economic?: number;
    social?: number;
    convenience?: number;
    [key: string]: number | undefined;
  };
}

export interface ReportStatistics {
  total_scraped: number;
  total_filtered_defects: number;
  avg_negativity_score: number;
  critical_defect_count: number;
  top_model: string;
  top_platform: string;
}

export interface DailyReportData {
  generated_at: string;
  pipeline_version: string;
  statistics: ReportStatistics;
  total_complaints_today?: number;
  top_defect_categories?: Array<{
    category: string;
    count: number;
    ratio: number;
  }>;
  reports: DefectReportItem[];
}

export const CATEGORY_MAP: Record<string, { code: DefectCategoryCode; ko: string }> = {
  BATTERY_CHARGING: { code: 'BATTERY_CHARGING', ko: '배터리/충전' },
  DRIVING_POWERTRAIN: { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  BUILD_QUALITY: { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },
  SOFTWARE_ELECTRONICS: { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
  SERVICE_REPAIR_COST: { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },
  parking: { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  charging: { code: 'BATTERY_CHARGING', ko: '배터리/충전' },
  rain_driving: { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  hill_climbing: { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  maintenance: { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },
  safety: { code: 'BATTERY_CHARGING', ko: '배터리/충전' },
  software: { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
};

/**
 * Safely sanitizes external URLs to prevent javascript:, data:, vbscript: or other XSS injections.
 */
export function sanitizeReportUrl(rawUrl?: unknown): string {
  if (!rawUrl || typeof rawUrl !== 'string') return '#';
  const trimmed = rawUrl.trim();
  if (!trimmed) return '#';
  if (/^(?:javascript|data|vbscript):/i.test(trimmed)) {
    return '#';
  }
  // Catch percent-encoded schemes like %6a%61%76%61%73%63%72%69%70%74:
  try {
    const decoded = decodeURIComponent(trimmed).replace(/\s+/g, '').toLowerCase();
    if (/^(?:javascript|data|vbscript|blob|file|about):/.test(decoded)) {
      return '#';
    }
  } catch {
    // Malformed URI encoding
  }
  return sanitizeSafeUrl(trimmed);
}

/**
 * Normalizes and bounds sentiment/negativity scores safely between 0.00 and 1.00.
 */
export function getSafeSentimentScore(rawScore?: unknown, fallback = 0.85): number {
  if (typeof rawScore !== 'number' || !Number.isFinite(rawScore)) {
    return fallback;
  }
  let val = Math.abs(rawScore);
  // If score was provided on a 0-100 scale (e.g. 85), scale down to 0-1
  if (val > 1.0 && val <= 100.0) {
    val = val / 100.0;
  }
  const clamped = Math.min(1.0, Math.max(0.0, val));
  return Number(clamped.toFixed(2));
}

/**
 * Normalizes any raw item from external JSON to DefectReportItem with safe defaults.
 */
export function normalizeReport(raw: Record<string, unknown>, index: number): DefectReportItem {
  if (!raw || typeof raw !== 'object') raw = {};
  const rawCat = sanitizeText(raw.defect_category || raw.category || 'BATTERY_CHARGING');
  const catInfo = (Object.prototype.hasOwnProperty.call(CATEGORY_MAP, rawCat) && CATEGORY_MAP[rawCat]) || {
    code: rawCat,
    ko: sanitizeText(raw.defect_category_ko || raw.category_ko || '기타 결함'),
  };

  const rawSeverity = sanitizeText(raw.severity || raw.severity_tier || 'WARNING').toUpperCase();
  let severity: SeverityLevel = 'WARNING';
  if (rawSeverity.includes('CRITICAL')) {
    severity = 'CRITICAL';
  } else if (rawSeverity === 'HIGH') {
    severity = 'HIGH';
  } else if (rawSeverity === 'MEDIUM') {
    severity = 'MEDIUM';
  } else if (rawSeverity === 'LOW') {
    severity = 'LOW';
  } else if (rawSeverity.includes('CAUTION') || rawSeverity.includes('CONVENIENCE')) {
    severity = 'CAUTION';
  } else if (rawSeverity.includes('WARN') || rawSeverity.includes('FUNCTIONAL')) {
    severity = 'WARNING';
  } else if (rawSeverity.includes('INFO')) {
    severity = 'INFO';
  }

  const rawScore = Number.isFinite(raw.sentiment_score)
    ? (raw.sentiment_score as number)
    : (Number.isFinite(raw.negativity_score) ? (raw.negativity_score as number) : 0.85);
  const score = getSafeSentimentScore(rawScore, 0.85);

  const rawSlang = Array.isArray(raw.slang_tags)
    ? raw.slang_tags
    : (Array.isArray(raw.slang_terms) ? raw.slang_terms : []);
  const slangTags = rawSlang
    .map((s: unknown) => sanitizeText(s))
    .filter((s): s is string => Boolean(s && s.length > 0));

  const rawDsi = raw.dsi_breakdown && typeof raw.dsi_breakdown === 'object'
    ? (raw.dsi_breakdown as Record<string, unknown>)
    : null;
  const dsiBreakdown: DefectReportItem['dsi_breakdown'] = rawDsi
    ? {
        safety: typeof rawDsi.safety === 'number' && Number.isFinite(rawDsi.safety) ? rawDsi.safety : 0,
        functional: typeof rawDsi.functional === 'number' && Number.isFinite(rawDsi.functional) ? rawDsi.functional : 0,
        economic: typeof rawDsi.economic === 'number' && Number.isFinite(rawDsi.economic) ? rawDsi.economic : 0,
        social: typeof rawDsi.social === 'number' && Number.isFinite(rawDsi.social) ? rawDsi.social : 0,
        convenience: typeof rawDsi.convenience === 'number' && Number.isFinite(rawDsi.convenience) ? rawDsi.convenience : 0,
      }
    : undefined;

  return {
    id: sanitizeText(raw.id || `report_${index + 1}`),
    source: sanitizeText(raw.source || raw.platform || 'bobaedream').toLowerCase(),
    url: sanitizeReportUrl(raw.url || raw.post_url || '#'),
    title: sanitizeText(raw.title || raw.post_title || '전기차 결함 제보'),
    date: sanitizeText(raw.date || raw.post_date || new Date().toISOString().split('T')[0]),
    created_at: raw.created_at ? sanitizeText(raw.created_at) : undefined,
    vehicle_model: sanitizeText(raw.vehicle_model || raw.target_vehicle || '미상 모델'),
    vehicle_brand: raw.vehicle_brand ? sanitizeText(raw.vehicle_brand) : undefined,
    target_vehicle: raw.target_vehicle ? sanitizeText(raw.target_vehicle) : undefined,
    defect_category: catInfo.code,
    defect_category_ko: sanitizeText(raw.defect_category_ko || catInfo.ko),
    summary: sanitizeText(raw.summary || raw.defect_summary || raw.defect_topic || '결함 상세 내용 요약'),
    verbatim_quote: sanitizeText(raw.verbatim_quote || raw.raw_quote || raw.content || '원문 없음'),
    slang_tags: slangTags,
    sentiment_score: score,
    sentiment_polarity: Number.isFinite(raw.sentiment_polarity) ? Number(raw.sentiment_polarity) : undefined,
    severity,
    severity_index: Number.isFinite(raw.severity_index) ? Number(raw.severity_index) : undefined,
    author: raw.author ? sanitizeText(raw.author) : undefined,
    is_authentic_defect: typeof raw.is_authentic_defect === 'boolean' ? raw.is_authentic_defect : true,
    dsi_breakdown: dsiBreakdown,
  };
}

/**
 * Calculates summary KPIs dynamically from reports list.
 */
export function calculateKPIs(
  reports: DefectReportItem[],
  existingStats?: Partial<ReportStatistics>
): ReportStatistics {
  const safeReports = Array.isArray(reports)
    ? reports.filter((r): r is DefectReportItem => Boolean(r && typeof r === 'object'))
    : [];
  const totalFiltered = safeReports.length;
  const criticalCount = safeReports.filter(
    (r) => String(r.severity || '').toUpperCase() === 'CRITICAL'
  ).length;

  const totalScore = safeReports.reduce((acc, r) => {
    const val = typeof r.sentiment_score === 'number' && Number.isFinite(r.sentiment_score)
      ? Math.min(1.0, Math.max(0.0, Math.abs(r.sentiment_score)))
      : 0;
    return acc + val;
  }, 0);
  const avgScore = totalFiltered > 0 ? Number((totalScore / totalFiltered).toFixed(2)) : 0.0;

  // Calculate top vehicle model with prototype-safe Map
  const modelCounts = new Map<string, number>();
  for (const r of safeReports) {
    if (r.vehicle_model) {
      modelCounts.set(r.vehicle_model, (modelCounts.get(r.vehicle_model) || 0) + 1);
    }
  }
  let topModelName = '아이오닉5';
  let maxModelCount = 0;
  modelCounts.forEach((count, model) => {
    if (count > maxModelCount) {
      maxModelCount = count;
      topModelName = model;
    }
  });
  const topModelDisplay = totalFiltered > 0 && maxModelCount > 0
    ? `${topModelName} (${maxModelCount}건)`
    : '해당 없음 (0건)';

  // Calculate top community platform with prototype-safe Map
  const platformCounts = new Map<string, number>();
  for (const r of safeReports) {
    const src = (r.source || 'bobaedream').toLowerCase();
    platformCounts.set(src, (platformCounts.get(src) || 0) + 1);
  }
  let topPlatformKey = 'bobaedream';
  let maxPlatformCount = 0;
  platformCounts.forEach((count, platform) => {
    if (count > maxPlatformCount) {
      maxPlatformCount = count;
      topPlatformKey = platform;
    }
  });
  const platformRatio = totalFiltered > 0 ? Math.round((maxPlatformCount / totalFiltered) * 100) : 0;
  const platformNameKo = topPlatformKey.includes('bobae') ? '보배드림' : '디시인사이드';
  const topPlatformDisplay = totalFiltered > 0
    ? `${platformNameKo} (${platformRatio}%)`
    : '해당 없음 (0%)';

  const totalScraped = existingStats?.total_scraped ?? (totalFiltered * 7);

  return {
    total_scraped: totalScraped,
    total_filtered_defects: totalFiltered,
    avg_negativity_score: typeof existingStats?.avg_negativity_score === 'number' && Number.isFinite(existingStats.avg_negativity_score)
      ? getSafeSentimentScore(existingStats.avg_negativity_score, avgScore)
      : avgScore,
    critical_defect_count: typeof existingStats?.critical_defect_count === 'number' && Number.isFinite(existingStats.critical_defect_count)
      ? Math.max(0, existingStats.critical_defect_count)
      : criticalCount,
    top_model: typeof existingStats?.top_model === 'string' && existingStats.top_model.trim()
      ? sanitizeText(existingStats.top_model)
      : topModelDisplay,
    top_platform: typeof existingStats?.top_platform === 'string' && existingStats.top_platform.trim()
      ? sanitizeText(existingStats.top_platform)
      : topPlatformDisplay,
  };
}

export const calculateReportStatistics = calculateKPIs;

/**
 * Returns safe fallback Daily EV Defect Reports data when loading fails or data is empty.
 */
export function getFallbackReportData(): DailyReportData {
  return {
    generated_at: new Date().toISOString(),
    pipeline_version: '1.0.0',
    statistics: {
      total_scraped: 0,
      total_filtered_defects: 0,
      avg_negativity_score: 0.0,
      critical_defect_count: 0,
      top_model: '해당 없음 (0건)',
      top_platform: '해당 없음 (0%)',
    },
    total_complaints_today: 0,
    top_defect_categories: [],
    reports: [],
  };
}

/**
 * Main type-safe loader for Daily EV Defect Reports.
 * Provides safe fallback in case the data is empty or corrupted.
 */
export function getDailyReports(): DailyReportData {
  try {
    const rawData = rawReportData as unknown as {
      generated_at?: string;
      pipeline_version?: string;
      statistics?: Partial<ReportStatistics>;
      total_complaints_today?: number;
      top_defect_categories?: Array<{
        category: string;
        count: number;
        ratio: number;
      }>;
      reports?: Record<string, unknown>[];
    } | null | undefined;

    if (!rawData || typeof rawData !== 'object') {
      return getFallbackReportData();
    }

    const rawReports = Array.isArray(rawData)
      ? (rawData as Record<string, unknown>[])
      : (Array.isArray(rawData?.reports) ? rawData.reports : []);

    const reports: DefectReportItem[] = rawReports
      .filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object'))
      .map((item: Record<string, unknown>, idx: number) =>
        normalizeReport(item, idx)
      );

    const statistics = calculateKPIs(reports, rawData?.statistics);

    const safeTopCategories = Array.isArray(rawData?.top_defect_categories)
      ? rawData.top_defect_categories
          .filter((cat): cat is { category: string; count: number; ratio: number } => Boolean(cat && typeof cat === 'object'))
          .map((cat) => ({
            category: sanitizeText(cat.category || 'UNKNOWN'),
            count: typeof cat.count === 'number' && Number.isFinite(cat.count) ? Math.max(0, cat.count) : 0,
            ratio: typeof cat.ratio === 'number' && Number.isFinite(cat.ratio) ? Math.min(1, Math.max(0, cat.ratio)) : 0,
          }))
      : [];

    return {
      generated_at: typeof rawData?.generated_at === 'string' && rawData.generated_at.trim()
        ? sanitizeText(rawData.generated_at)
        : new Date().toISOString(),
      pipeline_version: typeof rawData?.pipeline_version === 'string' && rawData.pipeline_version.trim()
        ? sanitizeText(rawData.pipeline_version)
        : '1.0.0',
      statistics,
      total_complaints_today: typeof rawData?.total_complaints_today === 'number' && Number.isFinite(rawData.total_complaints_today)
        ? Math.max(0, rawData.total_complaints_today)
        : reports.length,
      top_defect_categories: safeTopCategories,
      reports,
    };
  } catch (error) {
    console.error('Failed to load daily reports, using safe fallback:', error);
    return getFallbackReportData();
  }
}
