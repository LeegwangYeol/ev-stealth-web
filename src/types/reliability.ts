/**
 * South Korea & Global EV Reliability, Durability (DSI), and Chronic Defect Domain Types
 * Based on consumer complaints from Bobaedream, DCInside, KCA, and MOLIT defect records.
 */

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
  high_risk_models?: string[];
  critical_warning?: string;
  out_of_warranty_risk?: 'EXTREME' | 'HIGH' | 'MODERATE' | 'LOW';
  representative_models?: string[];
}

export interface ReliabilityTrendsDatabase {
  metadata: {
    version: string;
    analysis_period?: string;
    total_analyzed_posts?: number;
    last_updated?: string;
    updated_at?: string;
    total_records_analyzed?: number;
    brands_count?: number;
    models_count?: number;
    avg_industry_dsi?: number;
  };
  categories?: DefectCategoryMetadata[];
  defect_categories?: DefectCategoryMetadata[];
  repair_cost_matrix: RepairCostMatrixItem[];
  brands: BrandReliability[];
}

export interface EnrichedModelItem extends ModelReliability {
  brand_name_ko: string;
  brand_name_en: string;
  brand_country?: string;
}

export interface ReliabilityKPIs {
  totalAnalyzedPosts: number;
  trackedBrandsCount: number;
  trackedModelsCount: number;
  industryAvgDsi: number;
  topDefectCategory: string;
  totalRecordsAnalyzed?: number;
  brandsCount?: number;
  modelsCount?: number;
  avgIndustryDsi?: number;
}

export interface CategoryComplaintItem {
  category: string;
  count: number;
  percentage: number;
}

export interface CategoryComplaintInputEntry {
  category?: string | DefectCategoryKey;
  category_key?: string;
  code?: string;
  defect_category?: string;
  count?: number | unknown;
  percentage?: number | unknown;
}

