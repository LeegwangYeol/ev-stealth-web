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
export type OverallReliabilityGrade = 'A+' | 'A' | 'B' | 'C' | 'D' | 'F';
export type OutOfWarrantyRisk = 'EXTREME' | 'HIGH' | 'MODERATE' | 'LOW';
export type TrendDirection = 'UP' | 'DOWN' | 'STABLE';

export interface TrendCalculationResult {
  direction: TrendDirection;
  percentageChange: number;
  absoluteChange: number;
  formattedChange: string;
  isIncrease: boolean;
  isDecrease: boolean;
  isStable: boolean;
}

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
  overall_grade: OverallReliabilityGrade;
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
  out_of_warranty_risk?: OutOfWarrantyRisk;
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
  category: DefectCategoryKey | string;
  count: number;
  percentage: number;
}

export interface CategoryComplaintInputEntry {
  category?: string | DefectCategoryKey;
  category_key?: string;
  code?: string;
  defect_category?: string;
  count?: number | string | null;
  percentage?: number | string | null;
}

export interface StealthScoreWeights {
  dsiWeight?: number;
  incidentWeight?: number;
  criticalWeight?: number;
}

export interface StealthScoreInput {
  dsi?: unknown;
  incidentRate?: unknown;
  criticalIssueRate?: unknown;
  totalComplaints?: unknown;
  yearsEvaluated?: unknown;
  baselineIndustryDsi?: unknown;
  weights?: StealthScoreWeights;
  fleetOrSalesVolume?: unknown;
  fleetVolume?: unknown;
  salesVolume?: unknown;
  baselineScale?: number;
}

export interface StealthScoreResult {
  rawStealthScore: number;
  stealthScore: number;
  defectPenalty: number;
  confidenceScore: number;
  normalizedDefectFrequency: number;
  recommendedVerdict: ModelYearVerdict;
  overallGrade: OverallReliabilityGrade;
  isHighConfidence: boolean;
}

export interface DefectFrequencyOptions {
  complaintCount?: unknown;
  fleetOrSalesVolume?: unknown;
  baselineScale?: number;
}

export type TrajectoryVerdict =
  | 'RAPIDLY_IMPROVING'
  | 'IMPROVING'
  | 'STABLE'
  | 'DEGRADING'
  | 'CRITICALLY_DEGRADING';

export interface PeriodicDefectInput {
  date?: string | Date;
  year?: number | string;
  quarter?: number | string;
  month?: number | string;
  category?: DefectCategoryKey | string;
  defectCategory?: string;
  count?: number | string | null;
  dsiScore?: number | string | null;
  modelId?: string;
  brandId?: string;
}

export interface QuarterlyDefectBreakdown {
  periodKey: string;
  year: number;
  quarter: 1 | 2 | 3 | 4;
  totalComplaints: number;
  percentage: number;
  avgDsi: number;
  topCategory: DefectCategoryKey | string;
  categoryDistribution: Record<string, { count: number; percentage: number }>;
  trendFromPrevious: TrendCalculationResult;
  movingAverage3Q: number;
}

export interface MonthlyDefectBreakdown {
  periodKey: string;
  year: number;
  month: number;
  monthLabel: string;
  totalComplaints: number;
  percentage: number;
  avgDsi: number;
  topCategory: DefectCategoryKey | string;
  categoryDistribution: Record<string, { count: number; percentage: number }>;
  trendFromPrevious: TrendCalculationResult;
  movingAverage3M: number;
}

export interface ModelYearTrajectory {
  modelId: string;
  modelName: string;
  brandName?: string;
  trackedYears: number[];
  initialDsi: number;
  latestDsi: number;
  overallDsiChange: TrendCalculationResult;
  trajectoryVerdict: TrajectoryVerdict;
  peakRiskYear: number | null;
  peakRiskDsi: number;
  safestYear: number | null;
  safestDsi: number;
  chronicCategories: string[];
  yearOverYearProgression: Array<{
    year: number;
    dsi: number;
    verdict: ModelYearVerdict;
    incidentRate: number;
    primaryDefect: string;
    trendFromPreviousYear: TrendCalculationResult;
  }>;
}

export type ReliabilitySortOption = 'DSI_DESC' | 'DSI_ASC' | 'GRADE' | 'NAME';
export type ChartTabKey = 'heatmap' | 'brand_ranking' | 'brand_compare' | 'category_share';

