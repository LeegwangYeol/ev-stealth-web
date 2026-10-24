/**
 * tests/test_sync17_stress_perf_soak_ts.ts
 *
 * Empirical 100k+ Stress & Soak Verification Harness for TypeScript Calculation Engines:
 * 1. Subsidy Calculation Engine (getSubsidyData.ts):
 *    - calculateNetSubsidy & getPriceSubsidyRatio (100,000 iterations)
 *    - getCategoryDepletion (100,000 iterations)
 * 2. Depreciation & Battery Electrochemical Simulation Engine (getDepreciationData.ts):
 *    - calculateDepreciation (100,000 iterations)
 *    - simulateBatteryHealth (100,000 iterations)
 *    - calculateSubsidyClawback (100,000 iterations)
 *    - calculateTcoComparison (100,000 iterations)
 *
 * Verifies:
 * - Throughput (ops/sec) and high-resolution latency percentiles (min, mean, p50, p95, p99, max)
 * - Heap and RSS memory checkpoints at 0k, 25k, 50k, 75k, 100k iterations
 * - Post-GC memory reclamation & zero memory leak verification (< 1 MB residual heap growth)
 * - 100% zero unhandled exceptions under rapid soak conditions with 80% realistic + 20% adversarial inputs.
 */

import { performance } from 'node:perf_hooks';
import * as subsidy from '../src/lib/getSubsidyData';
import * as depreciation from '../src/lib/getDepreciationData';

interface LatencyStats {
  minUs: number;
  meanUs: number;
  p50Us: number;
  p95Us: number;
  p99Us: number;
  maxUs: number;
}

interface SoakResult {
  engineName: string;
  iterations: number;
  elapsedSec: number;
  opsPerSec: number;
  latencies: LatencyStats;
  memoryCheckpointsKB: {
    start0k: number;
    k25: number;
    k50: number;
    k75: number;
    k100: number;
    postGc: number;
  };
  peakHeapUsedKB: number;
  postGcHeapDeltaKB: number;
  unhandledExceptions: number;
}

function calculatePercentiles(latenciesUs: Float64Array, count: number): LatencyStats {
  const sorted = Array.from(latenciesUs.subarray(0, count)).sort((a, b) => a - b);
  const minUs = sorted[0];
  const maxUs = sorted[sorted.length - 1];
  const meanUs = sorted.reduce((sum, v) => sum + v, 0) / sorted.length;
  const p50Us = sorted[Math.floor(sorted.length * 0.50)];
  const p95Us = sorted[Math.floor(sorted.length * 0.95)];
  const p99Us = sorted[Math.floor(sorted.length * 0.99)];
  return { minUs, meanUs, p50Us, p95Us, p99Us, maxUs };
}

function triggerGc() {
  if (global.gc) {
    global.gc();
    global.gc();
  }
}

// ============================================================================
// 1. SUBSIDY CALCULATION ENGINE 100K SOAK TEST (CALCULATION CORE)
// ============================================================================
function runSubsidyCalcSoak100k(): SoakResult {
  const iterations = 100_000;
  const sampleSize = 1000;
  const sampleInterval = iterations / sampleSize;
  const latenciesBuffer = new Float64Array(sampleSize);

  const models = subsidy.getAllModels();
  const regions = subsidy.getAllRegions();

  let exceptionsCaught = 0;
  const memCheckpoints = {
    start0k: 0,
    k25: 0,
    k50: 0,
    k75: 0,
    k100: 0,
    postGc: 0,
  };

  triggerGc();
  const initHeapBytes = process.memoryUsage().heapUsed;
  memCheckpoints.start0k = Math.round(initHeapBytes / 1024);

  let peakHeapBytes = initHeapBytes;
  let sampleIdx = 0;

  const adversarialPrices = [0, -100000, 1, 99999999999, NaN, Infinity, -Infinity];

  const tStart = performance.now();

  for (let i = 0; i < iterations; i++) {
    if (i % 25_000 === 0 && i > 0) {
      const currentHeap = process.memoryUsage().heapUsed;
      if (currentHeap > peakHeapBytes) peakHeapBytes = currentHeap;
      if (i === 25_000) memCheckpoints.k25 = Math.round(currentHeap / 1024);
      if (i === 50_000) memCheckpoints.k50 = Math.round(currentHeap / 1024);
      if (i === 75_000) memCheckpoints.k75 = Math.round(currentHeap / 1024);
    }

    const isAdversarial = i % 5 === 0;
    const model = models[i % models.length];
    const region = regions[i % regions.length];
    const customMsrp = isAdversarial ? adversarialPrices[i % adversarialPrices.length] : undefined;

    if (i % sampleInterval === 0 && sampleIdx < sampleSize) {
      const t0 = performance.now();
      try {
        const res = subsidy.calculateNetSubsidy(model.model_id, region.region_id, customMsrp);
        const ratio = subsidy.getPriceSubsidyRatio(res.msrpKrw);
      } catch (err) {
        exceptionsCaught++;
      }
      const t1 = performance.now();
      latenciesBuffer[sampleIdx++] = (t1 - t0) * 1000; // in μs
    } else {
      try {
        const res = subsidy.calculateNetSubsidy(model.model_id, region.region_id, customMsrp);
        const ratio = subsidy.getPriceSubsidyRatio(res.msrpKrw);
      } catch (err) {
        exceptionsCaught++;
      }
    }
  }

  const elapsedSec = (performance.now() - tStart) / 1000;
  const currentHeap = process.memoryUsage().heapUsed;
  if (currentHeap > peakHeapBytes) peakHeapBytes = currentHeap;
  memCheckpoints.k100 = Math.round(currentHeap / 1024);

  triggerGc();
  const postGcHeapBytes = process.memoryUsage().heapUsed;
  memCheckpoints.postGc = Math.round(postGcHeapBytes / 1024);

  const postGcHeapDeltaKB = (postGcHeapBytes - initHeapBytes) / 1024;
  const opsPerSec = Math.round(iterations / elapsedSec);
  const latencies = calculatePercentiles(latenciesBuffer, sampleIdx);

  return {
    engineName: 'Subsidy Calculation Core Engine (calculateNetSubsidy + getPriceSubsidyRatio)',
    iterations,
    elapsedSec,
    opsPerSec,
    latencies,
    memoryCheckpointsKB: memCheckpoints,
    peakHeapUsedKB: Math.round(peakHeapBytes / 1024),
    postGcHeapDeltaKB: Math.round(postGcHeapDeltaKB * 100) / 100,
    unhandledExceptions: exceptionsCaught,
  };
}

// ============================================================================
// 2. SUBSIDY DEPLETION & REGIONAL FORMATTING 100K SOAK TEST
// ============================================================================
function runSubsidyDepletionSoak100k(): SoakResult {
  const iterations = 100_000;
  const sampleSize = 1000;
  const sampleInterval = iterations / sampleSize;
  const latenciesBuffer = new Float64Array(sampleSize);

  const regions = subsidy.getAllRegions();
  const categories: Array<'passenger' | 'commercial' | 'bus'> = ['passenger', 'commercial', 'bus'];

  let exceptionsCaught = 0;
  const memCheckpoints = {
    start0k: 0,
    k25: 0,
    k50: 0,
    k75: 0,
    k100: 0,
    postGc: 0,
  };

  triggerGc();
  const initHeapBytes = process.memoryUsage().heapUsed;
  memCheckpoints.start0k = Math.round(initHeapBytes / 1024);

  let peakHeapBytes = initHeapBytes;
  let sampleIdx = 0;

  const tStart = performance.now();

  for (let i = 0; i < iterations; i++) {
    if (i % 25_000 === 0 && i > 0) {
      const currentHeap = process.memoryUsage().heapUsed;
      if (currentHeap > peakHeapBytes) peakHeapBytes = currentHeap;
      if (i === 25_000) memCheckpoints.k25 = Math.round(currentHeap / 1024);
      if (i === 50_000) memCheckpoints.k50 = Math.round(currentHeap / 1024);
      if (i === 75_000) memCheckpoints.k75 = Math.round(currentHeap / 1024);
    }

    const region = regions[i % regions.length];
    const cat = categories[i % categories.length];

    if (i % sampleInterval === 0 && sampleIdx < sampleSize) {
      const t0 = performance.now();
      try {
        const dep = subsidy.getCategoryDepletion(region, cat);
      } catch (err) {
        exceptionsCaught++;
      }
      const t1 = performance.now();
      latenciesBuffer[sampleIdx++] = (t1 - t0) * 1000;
    } else {
      try {
        const dep = subsidy.getCategoryDepletion(region, cat);
      } catch (err) {
        exceptionsCaught++;
      }
    }
  }

  const elapsedSec = (performance.now() - tStart) / 1000;
  const currentHeap = process.memoryUsage().heapUsed;
  if (currentHeap > peakHeapBytes) peakHeapBytes = currentHeap;
  memCheckpoints.k100 = Math.round(currentHeap / 1024);

  triggerGc();
  const postGcHeapBytes = process.memoryUsage().heapUsed;
  memCheckpoints.postGc = Math.round(postGcHeapBytes / 1024);

  const postGcHeapDeltaKB = (postGcHeapBytes - initHeapBytes) / 1024;
  const opsPerSec = Math.round(iterations / elapsedSec);
  const latencies = calculatePercentiles(latenciesBuffer, sampleIdx);

  return {
    engineName: 'Subsidy Category Depletion & Formatting Engine (getCategoryDepletion)',
    iterations,
    elapsedSec,
    opsPerSec,
    latencies,
    memoryCheckpointsKB: memCheckpoints,
    peakHeapUsedKB: Math.round(peakHeapBytes / 1024),
    postGcHeapDeltaKB: Math.round(postGcHeapDeltaKB * 100) / 100,
    unhandledExceptions: exceptionsCaught,
  };
}

// ============================================================================
// 3. DEPRECIATION & BATTERY SOH ENGINE 100K SOAK TEST
// ============================================================================
function runDepreciationSoak100k(): SoakResult {
  const iterations = 100_000;
  const sampleSize = 1000;
  const sampleInterval = iterations / sampleSize;
  const latenciesBuffer = new Float64Array(sampleSize);

  const db = depreciation.getDepreciationDatabase();
  const models = db.models;

  let exceptionsCaught = 0;
  const memCheckpoints = {
    start0k: 0,
    k25: 0,
    k50: 0,
    k75: 0,
    k100: 0,
    postGc: 0,
  };

  triggerGc();
  const initHeapBytes = process.memoryUsage().heapUsed;
  memCheckpoints.start0k = Math.round(initHeapBytes / 1024);

  let peakHeapBytes = initHeapBytes;
  let sampleIdx = 0;

  const testYears = [0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 7.0, 10.0];
  const testMileages = [0, 5000, 15000, 30000, 60000, 100000, 250000];
  const testTemps = [-20, 0, 15, 25, 35, 45];
  const testTransfers: Array<'intra' | 'inter' | 'export'> = ['intra', 'inter', 'export'];

  const tStart = performance.now();

  for (let i = 0; i < iterations; i++) {
    if (i % 25_000 === 0 && i > 0) {
      const currentHeap = process.memoryUsage().heapUsed;
      if (currentHeap > peakHeapBytes) peakHeapBytes = currentHeap;
      if (i === 25_000) memCheckpoints.k25 = Math.round(currentHeap / 1024);
      if (i === 50_000) memCheckpoints.k50 = Math.round(currentHeap / 1024);
      if (i === 75_000) memCheckpoints.k75 = Math.round(currentHeap / 1024);
    }

    const model = models[i % models.length];
    const yr = testYears[i % testYears.length];
    const km = testMileages[i % testMileages.length];
    const temp = testTemps[i % testTemps.length];
    const transfer = testTransfers[i % testTransfers.length];

    if (i % sampleInterval === 0 && sampleIdx < sampleSize) {
      const t0 = performance.now();
      try {
        const dRes = depreciation.calculateDepreciation({ modelId: model.id, years: yr, mileageKm: km });
        const bRes = depreciation.simulateBatteryHealth({ modelId: model.id, years: yr, totalKm: km, ambientTempC: temp });
        const cRes = depreciation.calculateSubsidyClawback(yr * 12, 4000000, transfer, 6500000);
        const tco = depreciation.calculateTcoComparison(km > 0 ? km / yr : 15000, yr);
      } catch (err) {
        exceptionsCaught++;
      }
      const t1 = performance.now();
      latenciesBuffer[sampleIdx++] = (t1 - t0) * 1000;
    } else {
      try {
        const dRes = depreciation.calculateDepreciation({ modelId: model.id, years: yr, mileageKm: km });
        const bRes = depreciation.simulateBatteryHealth({ modelId: model.id, years: yr, totalKm: km, ambientTempC: temp });
        const cRes = depreciation.calculateSubsidyClawback(yr * 12, 4000000, transfer, 6500000);
        const tco = depreciation.calculateTcoComparison(km > 0 ? km / yr : 15000, yr);
      } catch (err) {
        exceptionsCaught++;
      }
    }
  }

  const elapsedSec = (performance.now() - tStart) / 1000;
  const currentHeap = process.memoryUsage().heapUsed;
  if (currentHeap > peakHeapBytes) peakHeapBytes = currentHeap;
  memCheckpoints.k100 = Math.round(currentHeap / 1024);

  triggerGc();
  const postGcHeapBytes = process.memoryUsage().heapUsed;
  memCheckpoints.postGc = Math.round(postGcHeapBytes / 1024);

  const postGcHeapDeltaKB = (postGcHeapBytes - initHeapBytes) / 1024;
  const opsPerSec = Math.round(iterations / elapsedSec);
  const latencies = calculatePercentiles(latenciesBuffer, sampleIdx);

  return {
    engineName: 'Depreciation & Battery SoH Engine (calculateDepreciation + simulateBatteryHealth + clawback + TCO)',
    iterations,
    elapsedSec,
    opsPerSec,
    latencies,
    memoryCheckpointsKB: memCheckpoints,
    peakHeapUsedKB: Math.round(peakHeapBytes / 1024),
    postGcHeapDeltaKB: Math.round(postGcHeapDeltaKB * 100) / 100,
    unhandledExceptions: exceptionsCaught,
  };
}

// ============================================================================
// MAIN RUNNER
// ============================================================================
console.log('\n======================================================================');
console.log('🚀 [FRONTEND TS EMPIRICAL 100K+ STRESS & SOAK HARNESS STARTING]');
console.log('======================================================================\n');

const subsidyCalcResult = runSubsidyCalcSoak100k();
console.log(`📊 [${subsidyCalcResult.engineName}]`);
console.log(`  • Iterations:            ${subsidyCalcResult.iterations.toLocaleString()}`);
console.log(`  • Elapsed Time:          ${subsidyCalcResult.elapsedSec.toFixed(3)} s`);
console.log(`  • Throughput:            ${subsidyCalcResult.opsPerSec.toLocaleString()} ops/sec`);
console.log(`  • Latency (Min):         ${subsidyCalcResult.latencies.minUs.toFixed(3)} μs`);
console.log(`  • Latency (Mean):        ${subsidyCalcResult.latencies.meanUs.toFixed(3)} μs`);
console.log(`  • Latency (P50/Median):  ${subsidyCalcResult.latencies.p50Us.toFixed(3)} μs`);
console.log(`  • Latency (P95):         ${subsidyCalcResult.latencies.p95Us.toFixed(3)} μs`);
console.log(`  • Latency (P99):         ${subsidyCalcResult.latencies.p99Us.toFixed(3)} μs`);
console.log(`  • Latency (Max):         ${subsidyCalcResult.latencies.maxUs.toFixed(3)} μs`);
console.log(`  • Memory Checkpoints:    0k: ${subsidyCalcResult.memoryCheckpointsKB.start0k} KB | 25k: ${subsidyCalcResult.memoryCheckpointsKB.k25} KB | 50k: ${subsidyCalcResult.memoryCheckpointsKB.k50} KB | 75k: ${subsidyCalcResult.memoryCheckpointsKB.k75} KB | 100k: ${subsidyCalcResult.memoryCheckpointsKB.k100} KB`);
console.log(`  • Peak Heap Used:        ${subsidyCalcResult.peakHeapUsedKB.toLocaleString()} KB`);
console.log(`  • Post-GC Heap Residual: ${subsidyCalcResult.memoryCheckpointsKB.postGc} KB (Net Delta: ${subsidyCalcResult.postGcHeapDeltaKB} KB)`);
console.log(`  • Unhandled Exceptions:  ${subsidyCalcResult.unhandledExceptions}`);
console.log('----------------------------------------------------------------------\n');

const subsidyDepResult = runSubsidyDepletionSoak100k();
console.log(`📊 [${subsidyDepResult.engineName}]`);
console.log(`  • Iterations:            ${subsidyDepResult.iterations.toLocaleString()}`);
console.log(`  • Elapsed Time:          ${subsidyDepResult.elapsedSec.toFixed(3)} s`);
console.log(`  • Throughput:            ${subsidyDepResult.opsPerSec.toLocaleString()} ops/sec`);
console.log(`  • Latency (Min):         ${subsidyDepResult.latencies.minUs.toFixed(3)} μs`);
console.log(`  • Latency (Mean):        ${subsidyDepResult.latencies.meanUs.toFixed(3)} μs`);
console.log(`  • Latency (P50/Median):  ${subsidyDepResult.latencies.p50Us.toFixed(3)} μs`);
console.log(`  • Latency (P95):         ${subsidyDepResult.latencies.p95Us.toFixed(3)} μs`);
console.log(`  • Latency (P99):         ${subsidyDepResult.latencies.p99Us.toFixed(3)} μs`);
console.log(`  • Latency (Max):         ${subsidyDepResult.latencies.maxUs.toFixed(3)} μs`);
console.log(`  • Memory Checkpoints:    0k: ${subsidyDepResult.memoryCheckpointsKB.start0k} KB | 25k: ${subsidyDepResult.memoryCheckpointsKB.k25} KB | 50k: ${subsidyDepResult.memoryCheckpointsKB.k50} KB | 75k: ${subsidyDepResult.memoryCheckpointsKB.k75} KB | 100k: ${subsidyDepResult.memoryCheckpointsKB.k100} KB`);
console.log(`  • Peak Heap Used:        ${subsidyDepResult.peakHeapUsedKB.toLocaleString()} KB`);
console.log(`  • Post-GC Heap Residual: ${subsidyDepResult.memoryCheckpointsKB.postGc} KB (Net Delta: ${subsidyDepResult.postGcHeapDeltaKB} KB)`);
console.log(`  • Unhandled Exceptions:  ${subsidyDepResult.unhandledExceptions}`);
console.log('----------------------------------------------------------------------\n');

const depResult = runDepreciationSoak100k();
console.log(`📊 [${depResult.engineName}]`);
console.log(`  • Iterations:            ${depResult.iterations.toLocaleString()}`);
console.log(`  • Elapsed Time:          ${depResult.elapsedSec.toFixed(3)} s`);
console.log(`  • Throughput:            ${depResult.opsPerSec.toLocaleString()} ops/sec`);
console.log(`  • Latency (Min):         ${depResult.latencies.minUs.toFixed(3)} μs`);
console.log(`  • Latency (Mean):        ${depResult.latencies.meanUs.toFixed(3)} μs`);
console.log(`  • Latency (P50/Median):  ${depResult.latencies.p50Us.toFixed(3)} μs`);
console.log(`  • Latency (P95):         ${depResult.latencies.p95Us.toFixed(3)} μs`);
console.log(`  • Latency (P99):         ${depResult.latencies.p99Us.toFixed(3)} μs`);
console.log(`  • Latency (Max):         ${depResult.latencies.maxUs.toFixed(3)} μs`);
console.log(`  • Memory Checkpoints:    0k: ${depResult.memoryCheckpointsKB.start0k} KB | 25k: ${depResult.memoryCheckpointsKB.k25} KB | 50k: ${depResult.memoryCheckpointsKB.k50} KB | 75k: ${depResult.memoryCheckpointsKB.k75} KB | 100k: ${depResult.memoryCheckpointsKB.k100} KB`);
console.log(`  • Peak Heap Used:        ${depResult.peakHeapUsedKB.toLocaleString()} KB`);
console.log(`  • Post-GC Heap Residual: ${depResult.memoryCheckpointsKB.postGc} KB (Net Delta: ${depResult.postGcHeapDeltaKB} KB)`);
console.log(`  • Unhandled Exceptions:  ${depResult.unhandledExceptions}`);
console.log('======================================================================\n');

// Assertions
let allPassed = true;
function assert(cond: boolean, msg: string) {
  if (!cond) {
    console.error(`❌ [ASSERTION FAILED]: ${msg}`);
    allPassed = false;
  } else {
    console.log(`✅ [ASSERTION PASSED]: ${msg}`);
  }
}

assert(subsidyCalcResult.unhandledExceptions === 0, 'Subsidy Calc Engine: 0 unhandled exceptions across 100k iterations');
assert(subsidyCalcResult.opsPerSec > 100000, `Subsidy Calc Engine: throughput > 100,000 ops/sec (actual: ${subsidyCalcResult.opsPerSec.toLocaleString()})`);
assert(subsidyCalcResult.latencies.meanUs < 10, `Subsidy Calc Engine: mean latency < 10 μs (actual: ${subsidyCalcResult.latencies.meanUs.toFixed(3)} μs)`);
assert(Math.abs(subsidyCalcResult.postGcHeapDeltaKB) < 1024, `Subsidy Calc Engine: zero memory leak (< 1 MB post-GC residual, actual: ${subsidyCalcResult.postGcHeapDeltaKB} KB)`);

assert(subsidyDepResult.unhandledExceptions === 0, 'Subsidy Depletion Engine: 0 unhandled exceptions across 100k iterations');
assert(subsidyDepResult.opsPerSec > 20000, `Subsidy Depletion Engine: throughput > 20,000 ops/sec (actual: ${subsidyDepResult.opsPerSec.toLocaleString()})`);
assert(subsidyDepResult.latencies.meanUs < 100, `Subsidy Depletion Engine: mean latency < 100 μs (actual: ${subsidyDepResult.latencies.meanUs.toFixed(3)} μs)`);
assert(Math.abs(subsidyDepResult.postGcHeapDeltaKB) < 1024, `Subsidy Depletion Engine: zero memory leak (< 1 MB post-GC residual, actual: ${subsidyDepResult.postGcHeapDeltaKB} KB)`);

assert(depResult.unhandledExceptions === 0, 'Depreciation Engine: 0 unhandled exceptions across 100k iterations');
assert(depResult.opsPerSec > 50000, `Depreciation Engine: throughput > 50,000 ops/sec (actual: ${depResult.opsPerSec.toLocaleString()})`);
assert(depResult.latencies.meanUs < 50, `Depreciation Engine: mean latency < 50 μs (actual: ${depResult.latencies.meanUs.toFixed(3)} μs)`);
assert(Math.abs(depResult.postGcHeapDeltaKB) < 1024, `Depreciation Engine: zero memory leak (< 1 MB post-GC residual, actual: ${depResult.postGcHeapDeltaKB} KB)`);

if (!allPassed) {
  process.exit(1);
} else {
  console.log('\n✨ ALL FRONTEND TS 100K+ SOAK BENCHMARKS PASSED WITH ZERO DEFECTS.\n');
}
