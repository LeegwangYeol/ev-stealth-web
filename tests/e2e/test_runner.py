#!/usr/bin/env python3
"""
E2E Test Runner for Global EV Critical Defect & Comparative Research Project.

Unified CLI test harness to execute and report on the 5 verification suites:
- Tier 1: Feature Coverage & Schema Integrity (test_tier1_feature_coverage.py)
- Tier 2: Boundary & Edge Case Auditing (test_tier2_boundary_cases.py)
- Tier 3: Cross-Category & Cross-Platform Combinations (test_tier3_cross_combinations.py)
- Tier 4: Real-World User Acceptance Scenarios (test_tier4_real_scenarios.py)
- Tier 5: Statistical Report & Safe Crawler Validator (test_statistical_report.py)

Usage:
    python3 tests/e2e/test_runner.py [--tier 1|2|3|4|5|all] [--suite statistical] [--verbose] [--json] [--failfast]
"""

import argparse
import io
import json
import os
import sys
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if not (PROJECT_ROOT / "scrapers").exists() and (PROJECT_ROOT.parent / "scrapers").exists():
    PROJECT_ROOT = PROJECT_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.e2e.test_tier1_feature_coverage import TestTier1FeatureCoverage
from tests.e2e.test_tier2_boundary_cases import TestTier2BoundaryCases
from tests.e2e.test_tier3_cross_combinations import TestTier3CrossCombinations
from tests.e2e.test_tier4_real_scenarios import TestTier4RealScenarios
from tests.e2e.test_statistical_report import TestStatisticalReportValidation

# ANSI Color Codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"


TIER_REGISTRY: Dict[int, Tuple[str, Type[unittest.TestCase]]] = {
    1: ("Tier 1: Feature Coverage & Schema Integrity", TestTier1FeatureCoverage),
    2: ("Tier 2: Boundary & Edge Case Auditing", TestTier2BoundaryCases),
    3: ("Tier 3: Cross-Category & Cross-Platform Combinations", TestTier3CrossCombinations),
    4: ("Tier 4: Real-World User Acceptance Scenarios", TestTier4RealScenarios),
    5: ("Tier 5: Statistical Report & Safe Crawler Validator", TestStatisticalReportValidation),
}


class TierResult:
    """Stores execution metrics for a single tier or suite."""

    def __init__(self, tier_num: int, tier_name: str):
        self.tier_num = tier_num
        self.tier_name = tier_name
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.errors = 0
        self.skipped = 0
        self.duration = 0.0
        self.failures_details: List[Tuple[str, str]] = []
        self.errors_details: List[Tuple[str, str]] = []

    @property
    def is_success(self) -> bool:
        return self.failed == 0 and self.errors == 0


def run_tier_suite(
    tier_num: int,
    tier_name: str,
    test_case_class: Type[unittest.TestCase],
    verbose: bool = False,
    failfast: bool = False,
) -> TierResult:
    """Execute all tests within a specific tier and record structured results."""
    tier_result = TierResult(tier_num, tier_name)
    suite = unittest.TestLoader().loadTestsFromTestCase(test_case_class)
    tier_result.total = suite.countTestCases()

    start_time = time.time()

    stream = io.StringIO()
    runner = unittest.TextTestRunner(
        stream=stream,
        verbosity=2 if verbose else 1,
        failfast=failfast,
    )
    result = runner.run(suite)

    tier_result.duration = time.time() - start_time
    tier_result.failed = len(result.failures)
    tier_result.errors = len(result.errors)
    tier_result.skipped = len(result.skipped)
    tier_result.passed = (
        tier_result.total - tier_result.failed - tier_result.errors - tier_result.skipped
    )

    for test, traceback_str in result.failures:
        tier_result.failures_details.append((test.id(), traceback_str))
    for test, traceback_str in result.errors:
        tier_result.errors_details.append((test.id(), traceback_str))

    return tier_result


def print_banner():
    print(f"\n{BOLD}{CYAN}{'='*85}{RESET}")
    print(f"{BOLD}{CYAN}  GLOBAL EV CRITICAL DEFECT & COMPARATIVE RESEARCH — E2E TEST HARNESS{RESET}")
    print(f"{BOLD}{CYAN}{'='*85}{RESET}")


def format_status(passed: bool) -> str:
    if passed:
        return f"{BOLD}{GREEN}PASSED{RESET}"
    return f"{BOLD}{RED}FAILED{RESET}"


def print_tier_summary_table(results: List[TierResult]):
    print(f"\n{BOLD}Test Execution Summary by Tier:{RESET}")
    print(f"{'─'*85}")
    print(
        f"{'Tier / Suite':<52} | {'Total':<6} | {'Pass':<5} | {'Fail':<5} | {'Err':<4} | {'Time(s)':<7} | {'Status'}"
    )
    print(f"{'─'*85}")

    grand_total = 0
    grand_passed = 0
    grand_failed = 0
    grand_errors = 0
    grand_time = 0.0

    for r in results:
        grand_total += r.total
        grand_passed += r.passed
        grand_failed += r.failed
        grand_errors += r.errors
        grand_time += r.duration

        status_str = format_status(r.is_success)
        print(
            f"{r.tier_name:<52} | {r.total:<6} | {r.passed:<5} | {r.failed:<5} | {r.errors:<4} | {r.duration:<7.3f} | {status_str}"
        )

    print(f"{'─'*85}")
    all_success = grand_failed == 0 and grand_errors == 0
    overall_status = f"{BOLD}{GREEN}ALL PASSED{RESET}" if all_success else f"{BOLD}{RED}SOME FAILED{RESET}"
    print(
        f"{'TOTAL SUMMARY':<52} | {grand_total:<6} | {grand_passed:<5} | {grand_failed:<5} | {grand_errors:<4} | {grand_time:<7.3f} | {overall_status}"
    )
    print(f"{'─'*85}\n")


def print_detailed_failures(results: List[TierResult]):
    for r in results:
        if not r.is_success:
            print(f"\n{BOLD}{RED}[!] Diagnostics for {r.tier_name}:{RESET}")
            for test_id, tb in r.failures_details:
                print(f"{BOLD}{YELLOW}  • Failure in: {test_id}{RESET}")
                for line in tb.strip().splitlines():
                    print(f"      {line}")
                print()
            for test_id, tb in r.errors_details:
                print(f"{BOLD}{RED}  • Error in: {test_id}{RESET}")
                for line in tb.strip().splitlines():
                    print(f"      {line}")
                print()


def export_json_report(results: List[TierResult], output_path: Optional[str] = None) -> str:
    summary_data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "overall_success": all(r.is_success for r in results),
        "total_tests": sum(r.total for r in results),
        "total_passed": sum(r.passed for r in results),
        "total_failed": sum(r.failed for r in results),
        "total_errors": sum(r.errors for r in results),
        "total_duration": sum(r.duration for r in results),
        "tiers": [
            {
                "tier": r.tier_num,
                "name": r.tier_name,
                "success": r.is_success,
                "total": r.total,
                "passed": r.passed,
                "failed": r.failed,
                "errors": r.errors,
                "duration": round(r.duration, 4),
                "failures": [
                    {"test": test_id, "traceback": tb}
                    for test_id, tb in r.failures_details
                ],
                "errors_list": [
                    {"test": test_id, "traceback": tb}
                    for test_id, tb in r.errors_details
                ],
            }
            for r in results
        ],
    }
    json_str = json.dumps(summary_data, indent=2, ensure_ascii=False)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json_str)
    return json_str


def main() -> int:
    parser = argparse.ArgumentParser(
        description="E2E Test Runner for Global EV Critical Defect & Comparative Research"
    )
    parser.add_argument(
        "--tier",
        type=str,
        default="all",
        choices=["1", "2", "3", "4", "5", "all"],
        help="Specific tier to execute (1, 2, 3, 4, 5, or all). Default: all",
    )
    parser.add_argument(
        "--suite",
        type=str,
        default=None,
        choices=["tier1", "tier2", "tier3", "tier4", "statistical", "all"],
        help="Named test suite to execute",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose test output",
    )
    parser.add_argument(
        "--failfast", "-f",
        action="store_true",
        help="Stop on first failure",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON summary to stdout",
    )
    parser.add_argument(
        "--json-file",
        type=str,
        default=None,
        help="Write JSON summary to the specified file path",
    )
    parser.add_argument(
        "--data-path",
        type=str,
        default=None,
        help="Custom path to complaints JSON dataset",
    )
    parser.add_argument(
        "--casebook-path",
        type=str,
        default=None,
        help="Custom path to CASEBOOK.md",
    )
    parser.add_argument(
        "--report-path",
        type=str,
        default=None,
        help="Custom path to STATISTICAL_REPORT.md",
    )

    args = parser.parse_args()

    # Set custom environment overrides if paths provided
    if args.data_path:
        os.environ["COMPLAINTS_DATA_PATH"] = args.data_path
    if args.casebook_path:
        os.environ["CASEBOOK_FILE_PATH"] = args.casebook_path
    if args.report_path:
        os.environ["STATISTICAL_REPORT_PATH"] = args.report_path

    if not args.json:
        print_banner()

    # Resolve tiers to execute
    if args.suite == "statistical" or args.tier == "5":
        tiers_to_run = [5]
    elif args.suite == "tier1" or args.tier == "1":
        tiers_to_run = [1]
    elif args.suite == "tier2" or args.tier == "2":
        tiers_to_run = [2]
    elif args.suite == "tier3" or args.tier == "3":
        tiers_to_run = [3]
    elif args.suite == "tier4" or args.tier == "4":
        tiers_to_run = [4]
    else:
        # Default all tiers (1-5)
        report_file = Path(os.environ.get("STATISTICAL_REPORT_PATH", str(PROJECT_ROOT / "STATISTICAL_REPORT.md")))
        if report_file.exists() or args.tier == "all":
            tiers_to_run = [1, 2, 3, 4, 5]
        else:
            tiers_to_run = [1, 2, 3, 4]

    results: List[TierResult] = []

    for t_num in tiers_to_run:
        t_name, t_cls = TIER_REGISTRY[t_num]
        if not args.json:
            print(f"{BLUE}▶ Running {t_name}...{RESET}")
        res = run_tier_suite(t_num, t_name, t_cls, verbose=args.verbose, failfast=args.failfast)
        results.append(res)

    if args.json:
        json_output = export_json_report(results, args.json_file)
        print(json_output)
    else:
        print_tier_summary_table(results)
        print_detailed_failures(results)

    all_passed = all(r.is_success for r in results)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
