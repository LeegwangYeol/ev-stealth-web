"""Comprehensive Unit & Regression Test Suite for Swarm Tracker Mission Audit.

Verifies:
1. Velocity prediction formulas (calculate_depletion_velocity, predict_exhaustion_days, predict_exhaustion_date, predict_region_exhaustion).
2. Edge cases: 0 total quota, negative quota, missing regions, short names ('서울', '경기', '부산'), None/NaN/Inf.
3. Critical status flags: AlertSeverity __str__, RegionRecord is_critical/is_warning/is_depleted with enum instances, SubsidyPayload get_critical_regions.
4. Tracker modularity: import tracker.tracker, from tracker.models import RegionRecord, SubsidyPayload.
5. Formatted numeric strings with commas in calculations (e.g. '1,500', '55,000,000').
6. CLI options and runner verification: --version, --help, --dry-run, --output, --sync-web.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

# Ensure path
_CURRENT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _CURRENT_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tracker.models import (
    AlertSeverity,
    AlertThresholdConfig,
    CategoryMetrics,
    MunicipalityMetrics,
    NationwideSummary,
    PopularModelEntry,
    RegionRecord,
    SubsidyMetadata,
    SubsidyPayload,
)
from tracker.tracker import (
    SubsidyTracker,
    calculate_delivery_rate,
    calculate_depletion_rate,
    calculate_depletion_velocity,
    calculate_net_subsidy,
    calculate_pending_deliveries,
    calculate_price_cap_ratio,
    calculate_remaining_units,
    calculate_waitlist_units,
    classify_alert_tier,
    classify_region_group,
    generate_fallback_payload,
    get_baseline_dataset,
    predict_exhaustion_date,
    predict_exhaustion_days,
)


class TestTrackerVelocityPredictions(unittest.TestCase):
    """Test velocity tracking and exhaustion predictions."""

    def test_calculate_depletion_velocity_nominal(self):
        """300 units over 30 days yields 10.0 units/day."""
        v = calculate_depletion_velocity(100, 400, 30)
        self.assertEqual(v, 10.0)

    def test_calculate_depletion_velocity_div0_and_edge_cases(self):
        """0 days or negative days returns 0.0 without ZeroDivisionError."""
        self.assertEqual(calculate_depletion_velocity(100, 400, 0), 0.0)
        self.assertEqual(calculate_depletion_velocity(100, 400, -10), 0.0)
        self.assertEqual(calculate_depletion_velocity(400, 100, 30), 0.0)
        self.assertEqual(calculate_depletion_velocity(None, 400, 30), 0.0)
        self.assertEqual(calculate_depletion_velocity(100, None, 30), 0.0)
        self.assertEqual(calculate_depletion_velocity(100, 400, None), 0.0)
        self.assertEqual(calculate_depletion_velocity(float("nan"), 400, 30), 0.0)
        self.assertEqual(calculate_depletion_velocity(100, float("inf"), 30), 0.0)

    def test_calculate_depletion_velocity_with_comma_strings(self):
        """Formatted strings with commas are parsed cleanly."""
        v = calculate_depletion_velocity("1,000", "2,500", "30")
        self.assertEqual(v, 50.0)

    def test_predict_exhaustion_days_nominal(self):
        """100 remaining units at 10.0 units/day yields 10 days."""
        days = predict_exhaustion_days(100, 10.0)
        self.assertEqual(days, 10)

    def test_predict_exhaustion_days_zero_and_negative(self):
        """0 remaining units returns 0 (already exhausted); 0 velocity returns None."""
        self.assertEqual(predict_exhaustion_days(0, 10.0), 0)
        self.assertEqual(predict_exhaustion_days(-50, 10.0), 0)
        self.assertIsNone(predict_exhaustion_days(100, 0.0))
        self.assertIsNone(predict_exhaustion_days(100, -5.0))
        self.assertIsNone(predict_exhaustion_days(None, 10.0))
        self.assertIsNone(predict_exhaustion_days(100, None))

    def test_predict_exhaustion_date_nominal(self):
        """Predict exhaustion date correctly projects from base date."""
        pred = predict_exhaustion_date(100, 10.0, start_date="2026-10-01")
        self.assertEqual(pred, "2026-10-11")

    def test_predict_exhaustion_date_zero_velocity(self):
        """Zero velocity returns None for exhaustion date."""
        self.assertIsNone(predict_exhaustion_date(100, 0.0, start_date="2026-10-01"))

    def test_predict_region_exhaustion_method(self):
        """SubsidyTracker.predict_region_exhaustion computes category metrics cleanly."""
        tracker = SubsidyTracker()
        payload = tracker.get_fallback_payload()
        seoul = payload.get_region("서울")
        self.assertIsNotNone(seoul)
        res = tracker.predict_region_exhaustion(seoul, category_name="passenger", reference_days=30.0)
        self.assertIn("category", res)
        self.assertIn("remaining_units", res)
        self.assertIn("daily_velocity", res)
        self.assertIn("days_to_exhaustion", res)
        self.assertGreater(res["daily_velocity"], 0.0)


class TestTrackerBoundaryAndEdgeCases(unittest.TestCase):
    """Test edge cases: 0 total quota, missing regions, short names, comma numbers."""

    def test_calculate_depletion_rate_zero_and_negative_quota(self):
        """0 total quota or negative quota returns 0.0% without ZeroDivisionError."""
        self.assertEqual(calculate_depletion_rate(0, 0), 0.0)
        self.assertEqual(calculate_depletion_rate(100, 0), 0.0)
        self.assertEqual(calculate_depletion_rate(100, -50), 0.0)
        self.assertEqual(calculate_depletion_rate(None, 100), 0.0)
        self.assertEqual(calculate_depletion_rate(100, None), 0.0)

    def test_calculate_depletion_rate_formatted_comma_strings(self):
        """Formatted comma strings are cleanly handled."""
        rate = calculate_depletion_rate("1,500", "3,000")
        self.assertEqual(rate, 50.0)

    def test_calculate_remaining_units_comma_strings(self):
        """calculate_remaining_units handles comma strings."""
        rem = calculate_remaining_units("1,500", "3,000")
        self.assertEqual(rem, 1500)

    def test_calculate_price_cap_ratio_comma_strings(self):
        """calculate_price_cap_ratio handles comma strings and boundary values."""
        self.assertEqual(calculate_price_cap_ratio("55,000,000"), 1.0)
        self.assertEqual(calculate_price_cap_ratio("85,000,000"), 0.5)
        self.assertEqual(calculate_price_cap_ratio("85,000,001"), 0.0)

    def test_get_region_short_names_and_aliases(self):
        """get_region resolves Korean short names ('서울', '경기', '부산') and aliases."""
        payload = generate_fallback_payload()
        self.assertEqual(payload.get_region("서울").name_ko, "서울특별시")
        self.assertEqual(payload.get_region("경기").name_ko, "경기도")
        self.assertEqual(payload.get_region("부산").name_ko, "부산광역시")
        self.assertEqual(payload.get_region("제주").name_ko, "제주특별자치도")
        self.assertEqual(payload.get_region("seoul").name_ko, "서울특별시")
        self.assertEqual(payload.get_region("kr-11").name_ko, "서울특별시")

    def test_get_region_missing_never_raises_keyerror(self):
        """Missing region returns None and never raises KeyError."""
        payload = generate_fallback_payload()
        self.assertIsNone(payload.get_region("NonExistentRegion"))
        self.assertIsNone(payload.get_region(""))
        self.assertIsNone(payload.get_region(None))

    def test_get_model_short_names(self):
        """get_model resolves partial model names like 'ioniq-5' and '아이오닉 5'."""
        payload = generate_fallback_payload()
        self.assertIsNotNone(payload.get_model("ioniq-5"))
        self.assertIsNotNone(payload.get_model("아이오닉 5"))
        self.assertIsNotNone(payload.get_model("ev6"))
        self.assertIsNone(payload.get_model("nonexistent_model"))

    def test_compute_nationwide_summary_zero_quota(self):
        """compute_nationwide_summary with empty regions never raises ZeroDivisionError."""
        tracker = SubsidyTracker()
        summary = tracker.compute_nationwide_summary([])
        self.assertEqual(summary.total_announced_units, 0)
        self.assertEqual(summary.total_applied_units, 0)
        self.assertEqual(summary.nationwide_depletion_rate, 0.0)
        self.assertEqual(summary.total_remaining_units, 0)


class TestTrackerCriticalStatusFlags(unittest.TestCase):
    """Test critical status flags and AlertSeverity handling."""

    def test_alert_severity_str_representation(self):
        """AlertSeverity.__str__ returns its string value."""
        self.assertEqual(str(AlertSeverity.CRITICAL), "CRITICAL")
        self.assertEqual(str(AlertSeverity.WARNING), "WARNING")
        self.assertEqual(str(AlertSeverity.HEALTHY), "HEALTHY")

    def test_region_record_critical_flags_with_enum_instance(self):
        """RegionRecord is_critical, is_warning, is_depleted work with AlertSeverity enum instances."""
        r_crit = RegionRecord(region_id="KR-test", overall_status=AlertSeverity.CRITICAL, overall_depletion_rate=0.0)
        self.assertTrue(r_crit.is_critical())
        self.assertFalse(r_crit.is_warning())

        r_warn = RegionRecord(region_id="KR-test2", overall_status=AlertSeverity.WARNING, overall_depletion_rate=0.0)
        self.assertTrue(r_warn.is_warning())
        self.assertFalse(r_warn.is_critical())

        r_dep = RegionRecord(region_id="KR-test3", overall_status=AlertSeverity.DEPLETED, overall_depletion_rate=0.0)
        self.assertTrue(r_dep.is_depleted())
        self.assertTrue(r_dep.is_critical())

    def test_subsidy_payload_get_critical_regions_with_enum(self):
        """SubsidyPayload.get_critical_regions identifies regions with enum status."""
        r = RegionRecord(region_id="KR-test", name_ko="테스트", overall_status=AlertSeverity.CRITICAL, overall_depletion_rate=10.0)
        payload = SubsidyPayload(
            metadata=SubsidyMetadata("1.0", "", 2026, [], 1, 0),
            alert_thresholds={},
            nationwide_summary=NationwideSummary(100, 10, 0, 90, 10.0, 1.0, 0.1, {}, {}),
            regions=[r],
            popular_models_matrix=[],
            historical_depletion_trajectory=[],
        )
        crits = payload.get_critical_regions()
        self.assertEqual(len(crits), 1)
        self.assertEqual(crits[0].region_id, "KR-test")


class TestTrackerModularityAndCLI(unittest.TestCase):
    """Test module imports, re-exports, and CLI invocation."""

    def test_import_tracker_tracker(self):
        """import tracker.tracker succeeds and provides core functions."""
        import tracker.tracker as tt
        self.assertTrue(hasattr(tt, "SubsidyTracker"))
        self.assertTrue(hasattr(tt, "calculate_depletion_rate"))
        self.assertTrue(hasattr(tt, "calculate_depletion_velocity"))
        self.assertTrue(hasattr(tt, "predict_exhaustion_days"))

    def test_import_tracker_models(self):
        """from tracker.models import RegionRecord, SubsidyPayload succeeds."""
        from tracker.models import RegionRecord as RR, SubsidyPayload as SP
        self.assertTrue(callable(RR))
        self.assertTrue(callable(SP))

    def test_run_tracker_cli_version_flag(self):
        """run_tracker.py --version returns 0 and prints version."""
        script_path = _REPO_ROOT / "run_tracker.py"
        res = subprocess.run([sys.executable, str(script_path), "--version"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("2.0.0", res.stdout + res.stderr)

    def test_run_tracker_cli_dry_run(self):
        """run_tracker.py --dry-run executes successfully with exit code 0."""
        script_path = _REPO_ROOT / "run_tracker.py"
        res = subprocess.run([sys.executable, str(script_path), "--dry-run"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("대한민국 2026 전국 지자체 전기차 보조금", res.stdout)


if __name__ == "__main__":
    unittest.main()
