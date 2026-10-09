#!/usr/bin/env python3
"""
tests/test_challenger_edge_cases.py - Empirical Adversarial Edge Cases Suite
=============================================================================
Author: sync11_challenger_backend_tests_w3 (Empirical Challenger)

Unified adversarial boundary & edge-case test suite combining:
1. Crawler HTML tag corruption, ReDoS, and extreme text stress
2. HTTP 429 Retry-After header parsing (numeric & RFC 9110 HTTP-date)
3. Atomic writing fault injection, ENOSPC, and concurrent race conditions
4. SubsidyTracker numerical boundaries, division-by-zero, and negative price clamps
5. DefectTracker query cache concurrency, LRU eviction, and None severity handling
"""

from __future__ import annotations

import unittest
from pathlib import Path
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import all battle-tested edge case test classes
from tests.test_empirical_challenger_edge_cases import (
    TestCrawlerCorruptedHTMLPayloads,
    TestExtremeTextAndNLPStress,
    TestHttp429AndRFC9110Backoff,
    TestAtomicWritingAndInterruption,
    TestEmpiricalVulnerabilityFindings,
)
from tests.test_challenger_tracker_boundaries import (
    TestTrackerBoundaryNumbers,
    TestPriceCapBoundariesAdversarial,
    TestCacheValidationAndQuarantineAdversarial,
    TestCliFlagsAdversarial,
)


class TestCycle11UnifiedChallengerInvariants(unittest.TestCase):
    """Empirical adversarial checks for Cycle 11 system-wide invariants."""

    def test_null_severity_index_critical_retention(self) -> None:
        """Records with severity='CRITICAL' and severity_index=None must be returned for min_severity >= 7.0."""
        from tracker.defect_tracker import DefectTracker
        import tempfile
        import json
        import os
        dt = DefectTracker()
        sample_reports = [
            {"id": "CRIT_NULL", "severity": "CRITICAL", "severity_index": None, "vehicle_brand": "현대"},
            {"id": "LOW_NULL", "severity": "LOW", "severity_index": None, "vehicle_brand": "현대"},
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"reports": sample_reports}, f)
            tmp_path = f.name

        try:
            results = dt.query_defects(min_severity=7.0, file_path=tmp_path)
            result_ids = [r["id"] for r in results]
            self.assertIn("CRIT_NULL", result_ids)
            self.assertNotIn("LOW_NULL", result_ids)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_json_safe_float_sanitizes_nan_inf(self) -> None:
        """utils.json_writer._safe_float must never produce unparseable NaN/Inf literals."""
        from utils.json_writer import _safe_float
        import math
        self.assertEqual(_safe_float(float("nan")), 0.0)
        self.assertEqual(_safe_float(float("inf")), 0.0)
        self.assertEqual(_safe_float(float("-inf")), 0.0)
        self.assertEqual(_safe_float("Infinity"), 0.0)
        self.assertEqual(_safe_float("-Infinity"), 0.0)
        self.assertEqual(_safe_float("NaN"), 0.0)


if __name__ == "__main__":
    unittest.main()
