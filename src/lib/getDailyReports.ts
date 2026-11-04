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
  // Canonical 5-Pillar Taxonomy
  BATTERY_CHARGING: { code: 'BATTERY_CHARGING', ko: '배터리/충전' },
  DRIVING_POWERTRAIN: { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  BUILD_QUALITY: { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },
  SOFTWARE_ELECTRONICS: { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
  SERVICE_REPAIR_COST: { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },

  // Lowercase Canonical Variants
  battery_charging: { code: 'BATTERY_CHARGING', ko: '배터리/충전' },
  driving_powertrain: { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  build_quality: { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },
  software_electronics: { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
  service_repair_cost: { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },

  // Korean Category Labels & Synonyms
  '배터리/충전': { code: 'BATTERY_CHARGING', ko: '배터리/충전' },
  '배터리': { code: 'BATTERY_CHARGING', ko: '배터리/충전' },
  '충전': { code: 'BATTERY_CHARGING', ko: '배터리/충전' },
  '화재': { code: 'BATTERY_CHARGING', ko: '배터리/충전' },

  '주행/모터/등판': { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  '주행': { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  '모터': { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  '등판': { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  '제동': { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  '조향': { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  '브레이크': { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },

  '단차/누수/마감': { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },
  '단차': { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },
  '누수': { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },
  '마감': { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },
  '풍절음': { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },
  '잡소리': { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },

  'OTA/소프트웨어': { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
  'OTA/소프트웨어/먹통': { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
  '소프트웨어': { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
  '전장': { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
  '전자장비': { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
  '먹통': { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
  '블랙아웃': { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },

  'AS/수리비': { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },
  '수리비': { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },
  'AS': { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },
  'as': { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },
  '정비': { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },
  '서비스': { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },
  '감가': { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },

  // Crawler Keywords & Aliases
  parking: { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  charging: { code: 'BATTERY_CHARGING', ko: '배터리/충전' },
  battery: { code: 'BATTERY_CHARGING', ko: '배터리/충전' },
  iccu: { code: 'BATTERY_CHARGING', ko: '배터리/충전' },
  bms: { code: 'BATTERY_CHARGING', ko: '배터리/충전' },
  fire: { code: 'BATTERY_CHARGING', ko: '배터리/충전' },
  safety: { code: 'BATTERY_CHARGING', ko: '배터리/충전' },

  driving: { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  powertrain: { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  motor: { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  brake: { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  steering: { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  fishtail: { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  rain_driving: { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  hill_climbing: { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },

  build: { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },
  quality: { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },
  assembly: { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },
  leak: { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },
  water_leak: { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },
  noise: { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },
  gap: { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },

  software: { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
  electronics: { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
  ota: { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
  infotainment: { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
  blackout: { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
  display: { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },

  maintenance: { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },
  service: { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },
  repair: { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },
  cost: { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },
  depreciation: { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },
};

/**
 * Resolves defect category safely from category code, alias, or Korean label.
 */
export function resolveCategory(
  rawCategory?: unknown,
  rawCategoryKo?: unknown
): { code: DefectCategoryCode; ko: string } {
  const cat = sanitizeText(rawCategory || '').trim();
  const catKo = sanitizeText(rawCategoryKo || '').trim();

  // 1. Direct match in CATEGORY_MAP
  if (cat && Object.prototype.hasOwnProperty.call(CATEGORY_MAP, cat)) {
    return CATEGORY_MAP[cat];
  }

  // 2. Case-insensitive lookup (uppercase then lowercase)
  const upper = cat.toUpperCase();
  if (upper && Object.prototype.hasOwnProperty.call(CATEGORY_MAP, upper)) {
    return CATEGORY_MAP[upper];
  }
  const lower = cat.toLowerCase();
  if (lower && Object.prototype.hasOwnProperty.call(CATEGORY_MAP, lower)) {
    return CATEGORY_MAP[lower];
  }

  // 3. Korean label lookup
  if (catKo && Object.prototype.hasOwnProperty.call(CATEGORY_MAP, catKo)) {
    return CATEGORY_MAP[catKo];
  }
  const koUpper = catKo.toUpperCase();
  if (koUpper && Object.prototype.hasOwnProperty.call(CATEGORY_MAP, koUpper)) {
    return CATEGORY_MAP[koUpper];
  }

  // 4. Default fallback when both empty (preserves default BATTERY_CHARGING / 배터리/충전 contract)
  if (!cat && !catKo) {
    return CATEGORY_MAP['BATTERY_CHARGING'];
  }

  // 5. Unrecognized custom category: preserve sanitized code, fallback label
  return {
    code: cat || 'BUILD_QUALITY',
    ko: catKo || '기타 결함',
  };
}

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
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) raw = {};

  const catInfo = resolveCategory(
    raw.defect_category || raw.category || raw.defect_category_key,
    raw.defect_category_ko || raw.category_ko
  );

  const rawSeverity = sanitizeText(raw.severity || raw.severity_tier || '').toUpperCase();
  let severity: SeverityLevel = 'WARNING';
  if (rawSeverity === 'CRITICAL' || rawSeverity.includes('CRITICAL')) {
    severity = 'CRITICAL';
  } else if (rawSeverity === 'HIGH') {
    severity = 'HIGH';
  } else if (rawSeverity === 'MEDIUM') {
    severity = 'MEDIUM';
  } else if (rawSeverity === 'LOW') {
    severity = 'LOW';
  } else if (rawSeverity === 'CAUTION' || rawSeverity.includes('CAUTION') || rawSeverity.includes('CONVENIENCE')) {
    severity = 'CAUTION';
  } else if (rawSeverity === 'WARNING' || rawSeverity.includes('WARN') || rawSeverity.includes('FUNCTIONAL')) {
    severity = 'WARNING';
  } else if (rawSeverity === 'INFO' || rawSeverity.includes('INFO')) {
    severity = 'INFO';
  } else if (typeof raw.severity_index === 'number' && Number.isFinite(raw.severity_index)) {
    const idx = raw.severity_index;
    if (idx >= 8.0) severity = 'CRITICAL';
    else if (idx >= 6.0) severity = 'HIGH';
    else if (idx >= 4.0) severity = 'MEDIUM';
    else severity = 'LOW';
  }

  const rawScore = Number.isFinite(raw.sentiment_score)
    ? (raw.sentiment_score as number)
    : (Number.isFinite(raw.negativity_score) ? (raw.negativity_score as number) : 0.85);
  const score = getSafeSentimentScore(rawScore, 0.85);

  const rawSlang = Array.isArray(raw.slang_tags)
    ? raw.slang_tags
    : (Array.isArray(raw.slang_terms) ? raw.slang_terms : (Array.isArray(raw.slang_terms_detected) ? raw.slang_terms_detected : []));
  const slangTags = rawSlang
    .map((s: unknown) => sanitizeText(s))
    .filter((s): s is string => Boolean(s && s.length > 0));

  const rawDsi = raw.dsi_breakdown && typeof raw.dsi_breakdown === 'object' && !Array.isArray(raw.dsi_breakdown)
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

  let safeDate = sanitizeText(raw.date || raw.post_date || '');
  if (!safeDate && raw.created_at) {
    const split = String(raw.created_at).split('T')[0];
    if (split && split.length >= 8) {
      safeDate = sanitizeText(split);
    }
  }
  if (!safeDate) {
    safeDate = new Date().toISOString().split('T')[0];
  }

  return {
    id: sanitizeText(raw.id || raw.post_id || `report_${index + 1}`),
    source: sanitizeText(raw.source || raw.platform || 'bobaedream').toLowerCase(),
    url: sanitizeReportUrl(raw.url || raw.post_url || '#'),
    title: sanitizeText(raw.title || raw.post_title || '전기차 결함 제보'),
    date: safeDate,
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
    ? reports.filter((r): r is DefectReportItem => Boolean(r && typeof r === 'object' && !Array.isArray(r)))
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
    total_scraped: typeof totalScraped === 'number' && Number.isFinite(totalScraped)
      ? Math.max(0, totalScraped)
      : (totalFiltered * 7),
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
 * High-fidelity canonical mock reports covering all 5 taxonomy pillars.
 * Used for offline test suites, visual previews, or when data files are completely missing.
 */
export const FALLBACK_MOCK_REPORTS: DefectReportItem[] = [
  {
    id: 'mock_bat_001',
    source: 'dcinside',
    url: 'https://gall.dcinside.com/mgallery/board/view/?id=car_new1&no=1284920',
    title: '전기차 ICCU 터져서 고속도로에서 멈춤',
    date: '2026-09-08',
    vehicle_model: '아이오닉5',
    vehicle_brand: '현대',
    defect_category: 'BATTERY_CHARGING',
    defect_category_ko: '배터리/충전',
    summary: '주행 중 갑작스러운 경고등 점등과 함께 ICCU 고장으로 차량 동력 상실 및 갓길 긴급 견인',
    verbatim_quote: '고속도로에서 100km로 달리는데 갑자기 퍽 소리 나더니 배터리 경고등 뜨고 악셀 먹통됨',
    slang_tags: ['ICCU폭탄', '벽돌차', '황천길'],
    sentiment_score: 0.96,
    severity: 'CRITICAL',
    is_authentic_defect: true,
  },
  {
    id: 'mock_drv_002',
    source: 'bobaedream',
    url: 'https://www.bobaedream.co.kr/view?code=national&No=2291045',
    title: '기아 EV3 빗길 주행하다가 뒤 털려서 가드레일 박을 뻔했습니다',
    date: '2026-09-08',
    vehicle_model: 'EV3',
    vehicle_brand: '기아',
    defect_category: 'DRIVING_POWERTRAIN',
    defect_category_ko: '주행/모터/등판',
    summary: '우천 고속 주행 시 리어 토션빔 접지력 상실 및 회생제동 개입으로 인한 피쉬테일 현상 발생',
    verbatim_quote: '비 오는 날 고속도로 이음새 밟고 회생제동 살짝 걸리는 순간 뒤쪽이 좌우로 사정없이 털리면서 피쉬테일 옴',
    slang_tags: ['피쉬테일', '토션빔털림', '회생제동슬립'],
    sentiment_score: 0.94,
    severity: 'CRITICAL',
    is_authentic_defect: true,
  },
  {
    id: 'mock_bld_003',
    source: 'bobaedream',
    url: 'https://www.bobaedream.co.kr/view?code=national&No=2290881',
    title: '출고 3일된 EV6 트렁크 누수로 스페어 공간 한강 됐습니다',
    date: '2026-09-08',
    vehicle_model: 'EV6',
    vehicle_brand: '기아',
    defect_category: 'BUILD_QUALITY',
    defect_category_ko: '단차/누수/마감',
    summary: '트렁크 테일게이트 웨더스트립 조립 불량으로 인한 우천 시 트렁크 하부 침수',
    verbatim_quote: '차 받은 지 3일 만에 폭우 내렸는데 오늘 트렁크 바닥 열어보니까 물이 찰랑찰랑 한강이네요',
    slang_tags: ['누수차', '수족관에디션', '단차지옥'],
    sentiment_score: 0.91,
    severity: 'WARNING',
    is_authentic_defect: true,
  },
  {
    id: 'mock_sft_004',
    source: 'dcinside',
    url: 'https://gall.dcinside.com/mgallery/board/view/?id=car_new1&no=1284550',
    title: '테슬라 모델Y OTA 최신 업데이트 받고 계기판 블랙아웃 벽돌됨',
    date: '2026-09-08',
    vehicle_model: '모델 Y',
    vehicle_brand: '테슬라',
    defect_category: 'SOFTWARE_ELECTRONICS',
    defect_category_ko: 'OTA/소프트웨어',
    summary: '차량 펌웨어 OTA 배포 설치 중 MCU 통신 오류로 인한 센터 디스플레이 완전 암전 및 운행 불가',
    verbatim_quote: '새벽에 와이파이 잡고 업데이트 눌렀는데 아침에 출근하려고 차 타니까 중앙 스크린 꺼져있고 리셋 눌러도 깜깜무소식',
    slang_tags: ['OTA벽돌', '블랙아웃', '어부바행'],
    sentiment_score: 0.95,
    severity: 'CRITICAL',
    is_authentic_defect: true,
  },
  {
    id: 'mock_svc_005',
    source: 'bobaedream',
    url: 'https://www.bobaedream.co.kr/view?code=national&No=2290412',
    title: '방지턱 하부 스쳤는데 배터리팩 긁혔다고 전손 3800만원 요구합니다',
    date: '2026-09-07',
    vehicle_model: '아이오닉6',
    vehicle_brand: '현대',
    defect_category: 'SERVICE_REPAIR_COST',
    defect_category_ko: 'AS/수리비',
    summary: '배터리 하부 케이스 미세 스크래치로 인한 서비스센터의 안전 규정상 배터리 전량 교체 및 3800만원 청구',
    verbatim_quote: '지하주차장 방지턱 살짝 긁혀서 소리 났길래 점검받으러 갔더니 하부 배터리 케이스 스크래치 났다고 배터리 통교체 3800만원 부름',
    slang_tags: ['수리비폭탄', '전손각', '통교체갑질'],
    sentiment_score: 0.98,
    severity: 'CRITICAL',
    is_authentic_defect: true,
  },
];

/**
 * Returns consistent, populated fallback mock Daily EV Defect Reports data when files are missing
 * and realistic mock data is explicitly required.
 */
export function getFallbackMockReportData(): DailyReportData {
  const reports = FALLBACK_MOCK_REPORTS.map((r, idx) => normalizeReport(r as unknown as Record<string, unknown>, idx));
  const statistics = calculateKPIs(reports);
  const catCountMap = new Map<string, number>();
  for (const r of reports) {
    const cat = r.defect_category || 'BUILD_QUALITY';
    catCountMap.set(cat, (catCountMap.get(cat) || 0) + 1);
  }
  const topDefectCategories = Array.from(catCountMap.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([category, count]) => ({
      category,
      count,
      ratio: Number((count / reports.length).toFixed(3)),
    }));

  return {
    generated_at: new Date().toISOString(),
    pipeline_version: '1.0.0-mock',
    statistics,
    total_complaints_today: reports.length,
    top_defect_categories: topDefectCategories,
    reports,
  };
}

/**
 * Main type-safe loader for Daily EV Defect Reports.
 * Provides safe fallback in case the data is empty or corrupted.
 */
export function getDailyReports(options?: { useMockOnEmpty?: boolean }): DailyReportData {
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

    if (!rawData || typeof rawData !== 'object' || (Array.isArray(rawData) && rawData.length === 0)) {
      return options?.useMockOnEmpty ? getFallbackMockReportData() : getFallbackReportData();
    }

    if (!Array.isArray(rawData) && Object.keys(rawData).length === 0) {
      return options?.useMockOnEmpty ? getFallbackMockReportData() : getFallbackReportData();
    }

    const rawReports = Array.isArray(rawData)
      ? (rawData as Record<string, unknown>[])
      : (Array.isArray(rawData?.reports) ? rawData.reports : []);

    const reports: DefectReportItem[] = rawReports
      .filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object' && !Array.isArray(item)))
      .map((item: Record<string, unknown>, idx: number) =>
        normalizeReport(item, idx)
      );

    if (reports.length === 0 && options?.useMockOnEmpty) {
      return getFallbackMockReportData();
    }

    const rawStats = rawData?.statistics && typeof rawData.statistics === 'object' && !Array.isArray(rawData.statistics)
      ? rawData.statistics
      : undefined;
    const statistics = calculateKPIs(reports, rawStats);

    let safeTopCategories = Array.isArray(rawData?.top_defect_categories)
      ? rawData.top_defect_categories
          .filter((cat): cat is { category: string; count: number; ratio: number } => Boolean(cat && typeof cat === 'object' && !Array.isArray(cat)))
          .map((cat) => {
            const resolved = resolveCategory(cat.category);
            return {
              category: resolved.code,
              count: typeof cat.count === 'number' && Number.isFinite(cat.count) ? Math.max(0, cat.count) : 0,
              ratio: typeof cat.ratio === 'number' && Number.isFinite(cat.ratio) ? Math.min(1, Math.max(0, cat.ratio)) : 0,
            };
          })
      : [];

    if (safeTopCategories.length === 0 && reports.length > 0) {
      const catCountMap = new Map<string, number>();
      for (const r of reports) {
        const cat = r.defect_category || 'BUILD_QUALITY';
        catCountMap.set(cat, (catCountMap.get(cat) || 0) + 1);
      }
      safeTopCategories = Array.from(catCountMap.entries())
        .sort((a, b) => b[1] - a[1])
        .map(([category, count]) => ({
          category,
          count,
          ratio: Number((count / reports.length).toFixed(3)),
        }));
    }

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
    return options?.useMockOnEmpty ? getFallbackMockReportData() : getFallbackReportData();
  }
}
