/**
 * tests/adversarial_stress_matrix.mjs
 * Native high-throughput stress & boundary fuzzing harness for getDepreciationData.ts.
 * Evaluates thousands of boundary combinations in milliseconds.
 */

import * as engine from '../src/lib/getDepreciationData.ts';
import rawDb from '../src/data/ev_depreciation_data.json' with { type: 'json' };

const models = engine.getAllModels();
console.log(`[STRESS HARNESS] Loaded ${models.length} EV models from database.`);

const results = {
  totalScenariosEvaluated: 0,
  failures: [],
  anomalies: [],
  boundarySnapshots: {}
};

// =========================================================================
// 1. BOUNDARY & EXTREME VALUES MATRIX
// =========================================================================

// A. 0 km vs 1,000,000 km Mileage
const dep0km = engine.calculateDepreciation({ modelId: 'model-3', years: 1.0, mileageKm: 0 });
const dep1Mkm = engine.calculateDepreciation({ modelId: 'model-3', years: 1.0, mileageKm: 1000000 });
results.boundarySnapshots.mileage_0km = dep0km;
results.boundarySnapshots.mileage_1Mkm = dep1Mkm;

// B. 0% DCFC vs 100% DCFC
const bat0dcfc = engine.simulateBatteryHealth({ years: 3.0, totalKm: 45000, chemistry: 'NCM_811', dcfcRatio: 0.0 });
const bat100dcfc = engine.simulateBatteryHealth({ years: 3.0, totalKm: 45000, chemistry: 'NCM_811', dcfcRatio: 1.0 });
results.boundarySnapshots.dcfc_0pct = bat0dcfc;
results.boundarySnapshots.dcfc_100pct = bat100dcfc;

// C. Extreme Cold (-30°C) vs Extreme Heat (+45°C)
const batCold30 = engine.simulateBatteryHealth({ years: 3.0, totalKm: 45000, chemistry: 'NCM_811', ambientTempC: -30.0 });
const batHot45 = engine.simulateBatteryHealth({ years: 3.0, totalKm: 45000, chemistry: 'NCM_811', ambientTempC: 45.0 });
results.boundarySnapshots.temp_cold30 = batCold30;
results.boundarySnapshots.temp_hot45 = batHot45;

// D. Zero Subsidy vs Maximum Subsidy (at 1 month inter-transfer)
const cbZero = engine.calculateSubsidyClawback(1, 0, 'inter', 0);
const cbMaxInter = engine.calculateSubsidyClawback(1, 12000000, 'inter', 8000000);
const cbMaxExport = engine.calculateSubsidyClawback(1, 12000000, 'export', 8000000);
results.boundarySnapshots.subsidy_zero = cbZero;
results.boundarySnapshots.subsidy_max_inter = cbMaxInter;
results.boundarySnapshots.subsidy_max_export = cbMaxExport;

// E. Fractional Ownership Durations (0.1, 2.5, 5.0 years)
results.boundarySnapshots.fractional_years = {};
for (const yr of [0.1, 0.5, 2.5, 5.0, 5.5]) {
  results.boundarySnapshots.fractional_years[yr] = engine.calculateDepreciation({ modelId: 'model-3', years: yr });
}

// F. Early Resale Clawback Schedule (1d, 89d, 90d, 364d, 729d, 730d)
results.boundarySnapshots.clawback_days = {};
const days = [1, 89, 90, 364, 729, 730];
for (const d of days) {
  const m = d / (365.0 / 12.0); // exact legal calendar month equivalent
  results.boundarySnapshots.clawback_days[`day_${d}`] = {
    months: m,
    inter: engine.calculateSubsidyClawback(m, 4000000, 'inter', 6500000),
    export: engine.calculateSubsidyClawback(m, 4000000, 'export', 6500000),
    intra: engine.calculateSubsidyClawback(m, 4000000, 'intra', 6500000)
  };
}

// =========================================================================
// 2. MONOTONICITY & INVERSION STRESS TEST ACROSS ALL 15 MODELS
// =========================================================================

console.log('[STRESS HARNESS] Checking residual curve monotonicity across all models...');
const inversionsFound = [];

for (const model of models) {
  // Test fine increments from 0.5 to 5.0 years in 0.05 step
  let prevResidual = 100.0;
  let prevYr = 0;
  for (let yr = 0.5; yr <= 5.0; yr = Math.round((yr + 0.05) * 100) / 100) {
    results.totalScenariosEvaluated++;
    const res = engine.calculateDepreciation({ modelId: model.id, years: yr });
    
    // Check for NaN or Inf
    if (Number.isNaN(res.adjustedResidualPct) || !Number.isFinite(res.adjustedResidualPct)) {
      results.failures.push({ type: 'NaN_OR_INF', model: model.id, years: yr, res });
    }
    
    // Check for negative residual
    if (res.adjustedResidualPct < 0 || res.estimatedResidualPriceKrw < 0) {
      results.failures.push({ type: 'NEGATIVE_RESIDUAL', model: model.id, years: yr, res });
    }

    // Check for curve inversion (residual increasing as car ages)
    if (res.adjustedResidualPct > prevResidual) {
      inversionsFound.push({
        modelId: model.id,
        chemistry: model.battery_specs.chemistry,
        prevYear: prevYr,
        prevResidualPct: prevResidual,
        currYear: yr,
        currResidualPct: res.adjustedResidualPct,
        diff: Math.round((res.adjustedResidualPct - prevResidual) * 100) / 100
      });
    }

    prevResidual = res.adjustedResidualPct;
    prevYr = yr;
  }
}

if (inversionsFound.length > 0) {
  console.log(`[ANOMALY] Detected ${inversionsFound.length} curve inversion events:`);
  for (const inv of inversionsFound) {
    console.log(`  -> ${inv.modelId} (${inv.chemistry}): Yr ${inv.prevYear} (${inv.prevResidualPct}%) -> Yr ${inv.currYear} (${inv.currResidualPct}%) [Inversion: +${inv.diff}%]`);
  }
  results.anomalies.push({ type: 'CURVE_INVERSION', details: inversionsFound });
} else {
  console.log('  -> No curve inversions detected in standard continuous grid.');
}

// =========================================================================
// 3. BATTERY SIMULATOR ADVERSARIAL FUZZING
// =========================================================================

console.log('[STRESS HARNESS] Fuzzing simulateBatteryHealth...');
const fuzzChemList = ['LFP', 'NCM_622', 'NCM_811', 'NCMA', 'NCA'];
const fuzzKmList = [-1000, 0, 100, 50000, 200000, 1000000, 5000000];
const fuzzTempList = [-30, -15, 0, 25, 45];
const fuzzDcfcList = [0.0, 0.25, 0.5, 1.0];

let nanHealthCount = 0;
for (const chem of fuzzChemList) {
  for (const km of fuzzKmList) {
    for (const temp of fuzzTempList) {
      for (const dcfc of fuzzDcfcList) {
        results.totalScenariosEvaluated++;
        const bRes = engine.simulateBatteryHealth({
          years: 3.0,
          totalKm: km,
          chemistry: chem,
          ambientTempC: temp,
          dcfcRatio: dcfc
        });

        if (Number.isNaN(bRes.sohPct) || Number.isNaN(bRes.cyclicLossPct)) {
          nanHealthCount++;
          if (nanHealthCount === 1) {
            results.anomalies.push({
              type: 'BATTERY_SIM_NAN',
              example: { chem, km, temp, dcfc, bRes }
            });
          }
        }
      }
    }
  }
}
console.log(`[STRESS HARNESS] Fuzzed battery scenarios. Total NaN encounters on invalid/negative inputs: ${nanHealthCount}`);

// =========================================================================
// 4. TCO ADVERSARIAL FRACTIONAL YEARS AUDIT
// =========================================================================

console.log('[STRESS HARNESS] Checking TCO calculation across fractional durations...');
const fractionalTcoYears = [0.1, 0.5, 1.0, 1.5, 2.5, 3.0, 5.0];
const tcoAnomalies = [];

for (const yr of fractionalTcoYears) {
  results.totalScenariosEvaluated++;
  const tco = engine.calculateTcoComparison(15000, yr);
  if (yr < 1.0 && (tco.yearlyBreakdown.length === 0 || tco.totalCumulativeSavingsKrw === 0)) {
    tcoAnomalies.push({
      year: yr,
      breakdownLength: tco.yearlyBreakdown.length,
      totalCumulativeSavings: tco.totalCumulativeSavingsKrw,
      expectedTotalKm: tco.totalKm
    });
  } else if (!Number.isInteger(yr) && tco.yearlyBreakdown.length !== Math.floor(yr)) {
    tcoAnomalies.push({
      year: yr,
      breakdownLength: tco.yearlyBreakdown.length,
      totalCumulativeSavings: tco.totalCumulativeSavingsKrw,
      expectedTotalKm: tco.totalKm
    });
  }
}

if (tcoAnomalies.length > 0) {
  console.log(`[ANOMALY] Detected ${tcoAnomalies.length} TCO fractional year anomalies (loop bounds y=1; y<=years):`, tcoAnomalies);
  results.anomalies.push({ type: 'TCO_FRACTIONAL_YEAR_TRUNCATION', details: tcoAnomalies });
}

// Print overall summary
console.log('\n======================================================');
console.log(`TOTAL SCENARIOS EVALUATED: ${results.totalScenariosEvaluated}`);
console.log(`CRITICAL CRASHES / UNHANDLED EXCEPTIONS: ${results.failures.length}`);
console.log(`IDENTIFIED ALGORITHMIC ANOMALIES: ${results.anomalies.length}`);
console.log('======================================================');

// Export JSON summary of results
console.log(JSON.stringify({
  totalScenariosEvaluated: results.totalScenariosEvaluated,
  anomaliesCount: results.anomalies.length,
  anomalies: results.anomalies.map(a => a.type),
  boundarySnapshotsSummary: {
    mileage_0km: { residualPct: dep0km.adjustedResidualPct, priceKrw: dep0km.estimatedResidualPriceKrw },
    mileage_1Mkm: { residualPct: dep1Mkm.adjustedResidualPct, priceKrw: dep1Mkm.estimatedResidualPriceKrw },
    dcfc_0pct: { sohPct: bat0dcfc.sohPct, cyclicLoss: bat0dcfc.cyclicLossPct },
    dcfc_100pct: { sohPct: bat100dcfc.sohPct, cyclicLoss: bat100dcfc.cyclicLossPct },
    temp_cold30: { sohPct: batCold30.sohPct, calLoss: batCold30.calendarLossPct, cycLoss: batCold30.cyclicLossPct },
    temp_hot45: { sohPct: batHot45.sohPct, calLoss: batHot45.calendarLossPct, cycLoss: batHot45.cyclicLossPct },
    subsidy_zero: { clawbackKrw: cbZero.totalClawbackKrw },
    subsidy_max_inter: { clawbackKrw: cbMaxInter.totalClawbackKrw },
    subsidy_max_export: { clawbackKrw: cbMaxExport.totalClawbackKrw },
    clawback_day_1: { rate: results.boundarySnapshots.clawback_days.day_1.inter.statutoryClawbackRate, exempt: results.boundarySnapshots.clawback_days.day_1.inter.isExempt },
    clawback_day_89: { rate: results.boundarySnapshots.clawback_days.day_89.inter.statutoryClawbackRate, exempt: results.boundarySnapshots.clawback_days.day_89.inter.isExempt },
    clawback_day_90: { rate: results.boundarySnapshots.clawback_days.day_90.inter.statutoryClawbackRate, exempt: results.boundarySnapshots.clawback_days.day_90.inter.isExempt },
    clawback_day_364: { rate: results.boundarySnapshots.clawback_days.day_364.inter.statutoryClawbackRate, exempt: results.boundarySnapshots.clawback_days.day_364.inter.isExempt },
    clawback_day_729: { rate: results.boundarySnapshots.clawback_days.day_729.inter.statutoryClawbackRate, exempt: results.boundarySnapshots.clawback_days.day_729.inter.isExempt },
    clawback_day_730: { rate: results.boundarySnapshots.clawback_days.day_730.inter.statutoryClawbackRate, exempt: results.boundarySnapshots.clawback_days.day_730.inter.isExempt }
  }
}, null, 2));
