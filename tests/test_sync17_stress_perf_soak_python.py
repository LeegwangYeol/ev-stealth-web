"""
tests/test_sync17_stress_perf_soak_python.py - Empirical Stress & Soak Test Suite for Python Backend Calculation Engines.

Cycle 17 Challenger Directive:
- Run 100k+ iterations of subsidy calculation and quota/depletion computation.
- Measure throughput, latency distribution (min, mean, p50, p95, p99, max), and memory footprint.
- Verify zero memory leaks (flat heap/RSS growth delta) and zero unhandled exceptions under soak conditions.
"""

from __future__ import annotations

import array
import gc
import math
from pathlib import Path
import random
import sys
import time
import tracemalloc
import unittest
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tracker.subsidy_models import AlertSeverity, CategoryMetrics, RegionRecord
from tracker.subsidy_baseline import (
    calculate_price_cap_ratio,
    calculate_net_subsidy as baseline_calc_net_subsidy,
    build_baseline_regions,
    PASSENGER_NATIONAL_CAP_KRW,
    COMMERCIAL_NATIONAL_CAP_KRW,
    BUS_NATIONAL_CAP_KRW,
)
from tracker.subsidy_tracker import (
    SubsidyTracker,
    calculate_depletion_rate,
    calculate_remaining_units,
    classify_alert_tier,
    calculate_net_subsidy as tracker_calc_net_subsidy,
)


class Sync17BackendStressPerfSoakTest(unittest.TestCase):
    """Empirical 100k+ soak and stress tests for backend subsidy calculation engines."""

    @classmethod
    def setUpClass(cls):
        cls.tracker = SubsidyTracker()
        cls.baseline_regions = build_baseline_regions()

    def test_01_subsidy_net_calculation_100k_soak(self):
        """100,000 iterations of subsidy net price & cap ratio calculation under soak conditions."""
        iterations = 100_000
        sample_size = 1000
        # Pre-allocate latency buffer prior to memory tracing baseline to avoid harness self-measurement bias
        latencies_buffer = array.array('d', [0.0] * sample_size)
        sample_interval = iterations // sample_size

        rng = random.Random(42)
        models_nat = [3_000_000, 4_500_000, 6_000_000, 6_500_000, 7_000_000, 10_500_000]
        max_nats = [6_500_000, 10_500_000, 70_000_000]
        max_locs = [1_500_000, 2_500_000, 4_000_000, 5_500_000, 8_000_000, 11_000_000]
        normal_msrps = [
            35_000_000, 48_000_000, 54_990_000, 55_000_000, 55_000_001,
            65_000_000, 78_000_000, 84_999_999, 85_000_000, 95_000_000, 120_000_000
        ]
        adversarial_msrps = [
            0, -100_000, 1, 999, 100_000_000_000,
            None, float("nan"), float("inf"), float("-inf"), "60000000"
        ]

        exceptions_caught = 0
        mem_checkpoints: Dict[int, float] = {}

        gc.collect()
        tracemalloc.start()
        b_init, _ = tracemalloc.get_traced_memory()
        mem_checkpoints[0] = b_init / 1024.0

        sample_idx = 0
        t_start = time.perf_counter()

        for i in range(iterations):
            if i % 25_000 == 0 and i > 0:
                current_bytes, _ = tracemalloc.get_traced_memory()
                mem_checkpoints[i] = current_bytes / 1024.0

            # 80% typical distributions, 20% adversarial edge cases
            if rng.random() < 0.8:
                msrp = rng.choice(normal_msrps)
                m_nat = rng.choice(models_nat)
                max_n = rng.choice(max_nats)
                max_l = rng.choice(max_locs)
            else:
                msrp = rng.choice(adversarial_msrps)
                m_nat = rng.choice([0, -1, None, 6_500_000, float("nan")])
                max_n = rng.choice([0, None, 6_500_000])
                max_l = rng.choice([0, None, -500_000, 11_000_000])

            if i % sample_interval == 0 and sample_idx < sample_size:
                t0 = time.perf_counter_ns()
                try:
                    res1 = tracker_calc_net_subsidy(m_nat, max_n, max_l, msrp)
                    res2 = baseline_calc_net_subsidy(m_nat, max_n, max_l, msrp)
                except Exception:
                    exceptions_caught += 1
                t1 = time.perf_counter_ns()
                latencies_buffer[sample_idx] = (t1 - t0) / 1000.0
                sample_idx += 1
            else:
                try:
                    res1 = tracker_calc_net_subsidy(m_nat, max_n, max_l, msrp)
                    res2 = baseline_calc_net_subsidy(m_nat, max_n, max_l, msrp)
                except Exception:
                    exceptions_caught += 1

        t_elapsed = time.perf_counter() - t_start
        current_bytes, peak_bytes = tracemalloc.get_traced_memory()
        mem_checkpoints[iterations] = current_bytes / 1024.0

        # Release temporary loop variables and force GC to test true persistent engine leakage
        del res1, res2
        gc.collect()
        post_gc_bytes, _ = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        throughput = iterations / t_elapsed
        latencies_list = sorted(list(latencies_buffer))
        lat_min = latencies_list[0]
        lat_mean = sum(latencies_list) / len(latencies_list)
        lat_p50 = latencies_list[int(len(latencies_list) * 0.50)]
        lat_p95 = latencies_list[int(len(latencies_list) * 0.95)]
        lat_p99 = latencies_list[int(len(latencies_list) * 0.99)]
        lat_max = latencies_list[-1]

        post_gc_delta_kb = abs(post_gc_bytes - b_init) / 1024.0

        print("\n" + "=" * 70)
        print("📊 [BACKEND 100K SOAK BENCHMARK: calculate_net_subsidy]")
        print(f"  • Total Iterations:      {iterations:,}")
        print(f"  • Elapsed Time:          {t_elapsed:.3f} s")
        print(f"  • Throughput:            {throughput:,.1f} ops/sec")
        print(f"  • Latency (Min):         {lat_min:.3f} μs")
        print(f"  • Latency (Mean):        {lat_mean:.3f} μs")
        print(f"  • Latency (P50/Median):  {lat_p50:.3f} μs")
        print(f"  • Latency (P95):         {lat_p95:.3f} μs")
        print(f"  • Latency (P99):         {lat_p99:.3f} μs")
        print(f"  • Latency (Max):         {lat_max:.3f} μs")
        print(f"  • Memory Checkpoints:    0k: {mem_checkpoints[0]:.1f} KB | 25k: {mem_checkpoints[25000]:.1f} KB | 50k: {mem_checkpoints[50000]:.1f} KB | 75k: {mem_checkpoints[75000]:.1f} KB | 100k: {mem_checkpoints[100000]:.1f} KB")
        print(f"  • Peak Traced Memory:    {peak_bytes / 1024.0:.1f} KB")
        print(f"  • Post-GC Traced Memory: {post_gc_bytes / 1024.0:.1f} KB (Delta: {post_gc_delta_kb:.3f} KB)")
        print(f"  • Unhandled Exceptions:  {exceptions_caught}")
        print("=" * 70 + "\n")

        self.assertEqual(exceptions_caught, 0, "Zero unhandled exceptions allowed during 100k soak")
        self.assertGreater(throughput, 50_000.0, "Throughput must exceed 50,000 ops/sec")
        self.assertLess(lat_mean, 20.0, "Mean latency must be under 20 μs")
        self.assertLess(lat_p95, 50.0, "P95 latency must be under 50 μs")
        self.assertLess(post_gc_delta_kb, 5.0, f"Zero memory leak: post-GC residual ({post_gc_delta_kb:.2f} KB) must be < 5.0 KB")

    def test_02_region_metrics_and_nationwide_summary_100k_soak(self):
        """100,000 iterations of CategoryMetrics and RegionRecord processing under stress."""
        iterations = 100_000
        sample_size = 1000
        latencies_buffer = array.array('d', [0.0] * sample_size)
        sample_interval = iterations // sample_size

        rng = random.Random(99)
        exceptions_caught = 0
        mem_checkpoints: Dict[int, float] = {}

        gc.collect()
        tracemalloc.start()
        b_init, _ = tracemalloc.get_traced_memory()
        mem_checkpoints[0] = b_init / 1024.0

        sample_idx = 0
        t_start = time.perf_counter()

        for i in range(iterations):
            if i % 25_000 == 0 and i > 0:
                current_bytes, _ = tracemalloc.get_traced_memory()
                mem_checkpoints[i] = current_bytes / 1024.0

            announced = rng.randint(100, 50_000)
            applied = int(announced * rng.uniform(0.0, 1.05))
            delivered = int(applied * rng.uniform(0.5, 0.95))
            max_local = rng.choice([1_500_000, 3_000_000, 5_500_000, 11_000_000])

            if i % sample_interval == 0 and sample_idx < sample_size:
                t0 = time.perf_counter_ns()
                try:
                    cat_metric = self.tracker.calculate_category_metrics(
                        announced=announced,
                        applied=applied,
                        delivered=delivered,
                        max_local_subsidy=max_local,
                        national_cap=PASSENGER_NATIONAL_CAP_KRW,
                    )
                    rate = calculate_depletion_rate(applied, announced)
                    tier = classify_alert_tier(rate)
                except Exception:
                    exceptions_caught += 1
                t1 = time.perf_counter_ns()
                latencies_buffer[sample_idx] = (t1 - t0) / 1000.0
                sample_idx += 1
            else:
                try:
                    cat_metric = self.tracker.calculate_category_metrics(
                        announced=announced,
                        applied=applied,
                        delivered=delivered,
                        max_local_subsidy=max_local,
                        national_cap=PASSENGER_NATIONAL_CAP_KRW,
                    )
                    rate = calculate_depletion_rate(applied, announced)
                    tier = classify_alert_tier(rate)
                except Exception:
                    exceptions_caught += 1

        t_elapsed = time.perf_counter() - t_start
        current_bytes, peak_bytes = tracemalloc.get_traced_memory()
        mem_checkpoints[iterations] = current_bytes / 1024.0

        del cat_metric
        gc.collect()
        post_gc_bytes, _ = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        throughput = iterations / t_elapsed
        latencies_list = sorted(list(latencies_buffer))
        lat_min = latencies_list[0]
        lat_mean = sum(latencies_list) / len(latencies_list)
        lat_p50 = latencies_list[int(len(latencies_list) * 0.50)]
        lat_p95 = latencies_list[int(len(latencies_list) * 0.95)]
        lat_p99 = latencies_list[int(len(latencies_list) * 0.99)]
        lat_max = latencies_list[-1]

        post_gc_delta_kb = abs(post_gc_bytes - b_init) / 1024.0

        print("\n" + "=" * 70)
        print("📊 [BACKEND 100K SOAK BENCHMARK: calculate_category_metrics & depletion]")
        print(f"  • Total Iterations:      {iterations:,}")
        print(f"  • Elapsed Time:          {t_elapsed:.3f} s")
        print(f"  • Throughput:            {throughput:,.1f} ops/sec")
        print(f"  • Latency (Min):         {lat_min:.3f} μs")
        print(f"  • Latency (Mean):        {lat_mean:.3f} μs")
        print(f"  • Latency (P50/Median):  {lat_p50:.3f} μs")
        print(f"  • Latency (P95):         {lat_p95:.3f} μs")
        print(f"  • Latency (P99):         {lat_p99:.3f} μs")
        print(f"  • Latency (Max):         {lat_max:.3f} μs")
        print(f"  • Memory Checkpoints:    0k: {mem_checkpoints[0]:.1f} KB | 25k: {mem_checkpoints[25000]:.1f} KB | 50k: {mem_checkpoints[50000]:.1f} KB | 75k: {mem_checkpoints[75000]:.1f} KB | 100k: {mem_checkpoints[100000]:.1f} KB")
        print(f"  • Peak Traced Memory:    {peak_bytes / 1024.0:.1f} KB")
        print(f"  • Post-GC Traced Memory: {post_gc_bytes / 1024.0:.1f} KB (Delta: {post_gc_delta_kb:.3f} KB)")
        print(f"  • Unhandled Exceptions:  {exceptions_caught}")
        print("=" * 70 + "\n")

        self.assertEqual(exceptions_caught, 0, "Zero unhandled exceptions allowed during category metrics soak")
        self.assertGreater(throughput, 40_000.0, "Throughput must exceed 40,000 ops/sec")
        self.assertLess(lat_mean, 25.0, "Mean latency must be under 25 μs")
        self.assertLess(lat_p95, 60.0, "P95 latency must be under 60 μs")
        self.assertLess(post_gc_delta_kb, 5.0, f"Zero memory leak: post-GC residual ({post_gc_delta_kb:.2f} KB) must be < 5.0 KB")


if __name__ == "__main__":
    unittest.main()
