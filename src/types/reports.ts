/**
 * EV Defect Reports and Community Scraped Analytics Types
 * Covers daily raw defect reports from Bobaedream, DCInside, and sentiment / DSI metrics.
 */

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
  vehicle_model: string;
  vehicle_brand: string;
  defect_category: string;
  defect_category_ko?: string;
  severity: 'CRITICAL' | 'HIGH' | 'WARNING' | 'MEDIUM' | 'CAUTION' | 'LOW' | 'INFO';
  sentiment_score: number;
  slang_tags: string[];
  url?: string;
  author?: string;
  created_at?: string;
  dsi_breakdown?: DsiBreakdown;
  severity_index?: number;
  sentiment_polarity?: number;
}

export interface DailyReportStatistics {
  total_scraped: number;
  total_filtered_defects: number;
  avg_negativity_score: number;
  critical_defect_count: number;
  top_model: string;
  top_platform: string;
}

export interface DailyReportData {
  generated_at: string;
  statistics: DailyReportStatistics;
  reports: DefectReportItem[];
  total_complaints_today?: number;
  top_defect_categories?: Array<{
    category: string;
    count: number;
    percentage: number;
  }>;
}

export interface AdminDefectReportItem extends DefectReportItem {
  created_at?: string;
  dsi_breakdown?: DsiBreakdown;
  severity_index?: number;
  sentiment_polarity?: number;
  author?: string;
}

export interface AdminDailyReportData extends Omit<DailyReportData, 'reports'> {
  reports?: AdminDefectReportItem[];
}
