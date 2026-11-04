/**
 * EV Defect Reports and Community Scraped Analytics Types
 * Covers daily raw defect reports from Bobaedream, DCInside, and sentiment / DSI metrics.
 */

export type DefectCategoryCode =
  | 'BATTERY_CHARGING'
  | 'DRIVING_POWERTRAIN'
  | 'BUILD_QUALITY'
  | 'SOFTWARE_ELECTRONICS'
  | 'SERVICE_REPAIR_COST'
  | 'COLD_WEATHER'
  | string;

export type SeverityLevel =
  | 'CRITICAL'
  | 'HIGH'
  | 'WARNING'
  | 'MEDIUM'
  | 'CAUTION'
  | 'LOW'
  | 'INFO'
  | string;

export interface DsiBreakdown {
  safety?: number;
  functional?: number;
  economic?: number;
  social?: number;
  convenience?: number;
  [key: string]: number | undefined;
}

export interface DefectReportItem {
  id: string;
  source: string;
  date: string;
  title: string;
  summary: string;
  verbatim_quote?: string;
  raw_quote?: string;
  vehicle_model: string;
  vehicle_brand?: string;
  target_vehicle?: string;
  defect_category: DefectCategoryCode;
  defect_category_ko?: string;
  category?: string;
  severity: SeverityLevel;
  sentiment_score: number;
  sentiment_polarity?: number;
  negativity_score?: number;
  sentiment_tier?: string;
  severity_index?: number;
  slang_tags: string[];
  slang_terms_detected?: string[];
  url?: string;
  post_url?: string;
  post_title?: string;
  platform?: string;
  author?: string;
  created_at?: string;
  is_authentic_defect?: boolean;
  dsi_breakdown?: DsiBreakdown;
}

export interface DailyReportStatistics {
  total_scraped: number;
  total_filtered_defects: number;
  avg_negativity_score: number;
  critical_defect_count: number;
  top_model?: string;
  top_platform?: string;
}

export type ReportStatistics = DailyReportStatistics;

export interface DailyReportData {
  generated_at: string;
  pipeline_version?: string;
  statistics: DailyReportStatistics;
  reports: DefectReportItem[];
  total_complaints_today?: number;
  top_defect_categories?: Array<{
    category: string;
    count: number;
    ratio?: number;
    percentage?: number;
  }>;
}

export interface AdminDefectReportItem extends DefectReportItem {
  is_authentic_defect?: boolean;
}

export interface AdminDailyReportData extends Omit<DailyReportData, 'reports'> {
  reports?: AdminDefectReportItem[];
}
