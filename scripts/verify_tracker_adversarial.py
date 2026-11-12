#!/usr/bin/env python3
"""Adversarial Verification Harness for EV Subsidy Pipeline and Tracker Mechanics.

Exercises:
1. Statutory MSRP boundary conditions and bracket ratio transitions.
2. Budget arithmetic, quota clamping, and negative-value prevention.
3. Division-by-zero resilience across all mathematical helper functions.
4. Cache corruption resilience across structural anomalies and malformed files.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tracker.subsidy_tracker import (
    calculate_depletion_rate,
    calculate_remaining_units,
    calculate_price_cap_ratio,
    calculate_net_subsidy,
    SubsidyTracker,
)
from tracker.subsidy_models import (
    AlertSeverity,
    CategoryMetrics,
    RegionRecord,
    SubsidyPayload,
)


def verify_msrp_boundaries() -> List[Dict[str, Any]]:
    """Test statutory MSRP boundary conditions against calculate_price_cap_ratio."""
    # Statutory 2026 Korean Ministry of Environment rules:
    # <= 55,000,000 KRW -> 100% (1.0)
    # > 55,000,000 and <= 85,000,000 KRW -> 50% (0.5)
    # > 85,000,000 KRW -> 0% (0.0)
    cases = [
        (54_999_999, 1.0, "54.999M KRW (1 KRW below 55M)"),
        (55_000_000, 1.0, "55.000M KRW (Exact statutory 100% ceiling)"),
        (55_000_001, 0.5, "55.000M + 1 KRW (Enters 50% tier)"),
        (85_000_000, 0.5, "85.000M KRW (Exact statutory 50% ceiling)"),
        (85_000_001, 0.0, "85.000M + 1 KRW (Enters 0% luxury tier)"),
    ]
    results = []
    for msrp, statutory_expected, desc in cases:
        actual = calculate_price_cap_ratio(msrp)
        passed = (actual == statutory_expected)
        results.append({
            "msrp": msrp,
            "desc": desc,
            "statutory_expected": statutory_expected,
            "actual": actual,
            "pass": passed,
        })
    return results


def verify_budget_arithmetic() -> List[Dict[str, Any]]:
    """Test budget arithmetic, over-subscription clamping, and div0 safety."""
    results = []

    # 1. Depletion rate with 0 announced
    r1 = calculate_depletion_rate(0, 0)
    results.append({"name": "depletion_rate_0_0", "expected": 0.0, "actual": r1, "pass": r1 == 0.0})

    r2 = calculate_depletion_rate(50, 0)
    results.append({"name": "depletion_rate_50_0", "expected": 0.0, "actual": r2, "pass": r2 == 0.0})

    # 2. Over-depletion rate
    r3 = calculate_depletion_rate(150, 100)
    results.append({"name": "depletion_rate_150_100", "expected": 150.0, "actual": r3, "pass": r3 == 150.0})

    # 3. Remaining units clamping when applied > announced
    r4 = calculate_remaining_units(150, 100)
    results.append({"name": "remaining_units_clamped_150_100", "expected": 0, "actual": r4, "pass": r4 == 0})

    r5 = calculate_remaining_units(100, 100)
    results.append({"name": "remaining_units_exact_100_100", "expected": 0, "actual": r5, "pass": r5 == 0})

    r6 = calculate_remaining_units(50, 100)
    results.append({"name": "remaining_units_partial_50_100", "expected": 50, "actual": r6, "pass": r6 == 50})

    # 4. Net subsidy div0 safety
    s_div0 = calculate_net_subsidy(model_national=6_500_000, max_national=0, max_local=1_500_000, msrp=50_000_000)
    results.append({
        "name": "net_subsidy_max_national_0",
        "expected_local": 0,
        "actual_local": s_div0["local_subsidy_krw"],
        "pass": s_div0["local_subsidy_krw"] == 0 and s_div0["total_subsidy_krw"] == 6_500_000,
    })

    # 5. Negative MSRP clamp
    s_neg = calculate_net_subsidy(model_national=6_500_000, max_national=6_500_000, max_local=1_500_000, msrp=-1_000_000)
    results.append({
        "name": "net_subsidy_negative_msrp",
        "expected_net": 0,
        "actual_net": s_neg["net_price_krw"],
        "pass": s_neg["net_price_krw"] == 0,
    })

    # 6. Category metrics with 0 quota
    tracker = SubsidyTracker()
    cat_0 = tracker.calculate_category_metrics(announced=0, applied=0, delivered=0, max_local_subsidy=0)
    results.append({
        "name": "category_metrics_zero_quota",
        "pass": (
            cat_0.depletion_rate == 0.0
            and cat_0.remaining_units == 0
            and cat_0.remaining_budget_krw == 0
        ),
    })

    # 7. Category metrics over-subscribed
    cat_over = tracker.calculate_category_metrics(
        announced=100, applied=150, delivered=120, max_local_subsidy=1_500_000
    )
    results.append({
        "name": "category_metrics_over_subscribed",
        "pass": (
            cat_over.remaining_units == 0
            and cat_over.remaining_budget_krw == 0
            and cat_over.depletion_rate == 150.0
            and cat_over.status == "DEPLETED"
        ),
    })

    return results


def verify_cache_corruption_scenarios() -> List[Dict[str, Any]]:
    """Test corrupted cache feeding into run_tracker.py and SubsidyTracker."""
    scenarios = [
        ("truncated_json", '{"metadata": {"version": "1.0.0"'),
        ("empty_file", ""),
        ("raw_garbage", "<<MALFORMED NON-JSON CONTENT>> \x00\x01\x02"),
        ("json_array", "[1, 2, 3, 4]"),
        ("json_int", "42"),
        ("json_null", "null"),
        ("regions_is_int", '{"regions": 123}'),
        ("regions_with_corrupt_string_record", '{"regions": ["corrupt_string"]}'),
        ("regions_missing_categories", '{"regions": [{"name_ko": "서울"}]}'),
        ("regions_less_than_17", '{"regions": [{"region_id": "KR-11", "categories": {}}]}'),
    ]

    results = []
    for name, content in scenarios:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "ev_subsidy_data.json"
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write(content)
            try:
                os.chmod(cache_file, 0o644)
            except OSError:
                pass

            cmd = [sys.executable, "run_tracker.py", "--output", str(cache_file), "--mock-network", "--dry-run"]
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))

            crashed = proc.returncode != 0
            clean_fallback = proc.returncode == 0
            err_line = ""
            for l in proc.stderr.splitlines():
                if "Fatal error" in l or "Error" in l or "Traceback" in l:
                    err_line = l.strip()
                    break

            results.append({
                "scenario": name,
                "exit_code": proc.returncode,
                "clean_fallback": clean_fallback,
                "crashed": crashed,
                "error_detail": err_line,
            })
    return results


def run_full_suite() -> int:
    """Execute verification suite and print structured report."""
    print("=" * 80)
    print("EMPIRICAL ADVERSARIAL CHALLENGE REPORT: EV SUBSIDY TRACKER PIPELINE")
    print("=" * 80)

    # 1. MSRP Boundaries
    print("\n--- 1. MSRP Statutory Boundary Analysis ---")
    msrp_results = verify_msrp_boundaries()
    msrp_fails = 0
    for r in msrp_results:
        status_str = "PASS" if r["pass"] else "FAIL"
        if not r["pass"]:
            msrp_fails += 1
        print(f"[{status_str}] MSRP {r['msrp']:,} KRW ({r['desc']}): Expected ratio {r['statutory_expected']}, got {r['actual']}")

    # 2. Budget Arithmetic & Div0
    print("\n--- 2. Budget Arithmetic, Clamping & Div0 Safety ---")
    budget_results = verify_budget_arithmetic()
    budget_fails = 0
    for r in budget_results:
        status_str = "PASS" if r["pass"] else "FAIL"
        if not r["pass"]:
            budget_fails += 1
        print(f"[{status_str}] {r['name']}")

    # 3. Cache Corruption Resilience
    print("\n--- 3. Corrupted Cache Resilience in run_tracker.py ---")
    cache_results = verify_cache_corruption_scenarios()
    cache_fails = 0
    for r in cache_results:
        status_str = "PASS" if r["clean_fallback"] else "CRASH"
        if r["crashed"]:
            cache_fails += 1
        print(f"[{status_str}] Scenario: {r['scenario']} (exit code {r['exit_code']}) {r['error_detail']}")

    print("\n" + "=" * 80)
    print(f"SUMMARY: MSRP Failures: {msrp_fails} | Budget Failures: {budget_fails} | Cache Crashes: {cache_fails}")
    print("=" * 80)

    # Total issues found
    return msrp_fails + budget_fails + cache_fails


if __name__ == "__main__":
    exit_code = run_full_suite()
    sys.exit(0 if exit_code == 0 else 1)
