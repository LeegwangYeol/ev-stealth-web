"""Unit and Regression Tests for EV Subsidy Depletion Tracker.

Verifies:
1. Data models and serialization round-trip
2. 5-tier alert severity thresholds
3. Edge cases: division by zero, over-subscription, empty inputs
4. Crash-durable atomic file writer
5. 17-region baseline data completeness
6. Fallback resilience on simulated network failures
7. CLI runner integration and argument handling
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tracker.atomic_writer import atomic_write_json, atomic_write_json_multiple
from tracker.subsidy_baseline import (
    DEFAULT_ALERT_THRESHOLDS,
    PASSENGER_NATIONAL_CAP_KRW,
    build_baseline_regions,
    build_historical_trajectory,
    build_initial_baseline,
    build_popular_models,
)
from tracker.subsidy_models import (
    AlertSeverity,
    CategoryMetrics,
    MunicipalityMetrics,
    NationwideSummary,
    PopularModelEntry,
    RegionRecord,
    SubsidyMetadata,
    SubsidyPayload,
)
from tracker.subsidy_tracker import SubsidyTracker


class TestSubsidyModels(unittest.TestCase):
    """Test data models and serialization round-trip."""

    def test_alert_severity_thresholds(self):
        """Test boundary conditions for 5-tier alert severity."""
        self.assertEqual(AlertSeverity.from_rate(0.0), AlertSeverity.HEALTHY)
        self.assertEqual(AlertSeverity.from_rate(59.9), AlertSeverity.HEALTHY)
        self.assertEqual(AlertSeverity.from_rate(60.0), AlertSeverity.CAUTION)
        self.assertEqual(AlertSeverity.from_rate(79.9), AlertSeverity.CAUTION)
        self.assertEqual(AlertSeverity.from_rate(80.0), AlertSeverity.WARNING)
        self.assertEqual(AlertSeverity.from_rate(94.9), AlertSeverity.WARNING)
        self.assertEqual(AlertSeverity.from_rate(95.0), AlertSeverity.CRITICAL)
        self.assertEqual(AlertSeverity.from_rate(99.9), AlertSeverity.CRITICAL)
        self.assertEqual(AlertSeverity.from_rate(100.0), AlertSeverity.DEPLETED)
        self.assertEqual(AlertSeverity.from_rate(115.5), AlertSeverity.DEPLETED)

    def test_category_metrics_calculations(self):
        """Verify CategoryMetrics behavior and boundary conditions."""
        tracker = SubsidyTracker()
        # Normal case
        cat = tracker.calculate_category_metrics(1000, 850, 700, 3_000_000)
        self.assertEqual(cat.announced_units, 1000)
        self.assertEqual(cat.applied_units, 850)
        self.assertEqual(cat.remaining_units, 150)
        self.assertEqual(cat.depletion_rate, 85.0)
        self.assertEqual(cat.delivery_rate, 70.0)
        self.assertEqual(cat.status, "WARNING")
        self.assertEqual(cat.max_total_subsidy_krw, 3_000_000 + PASSENGER_NATIONAL_CAP_KRW)

        # Over-subscription (applied > announced)
        cat_over = tracker.calculate_category_metrics(1000, 1100, 950, 3_000_000)
        self.assertEqual(cat_over.remaining_units, 0)
        self.assertEqual(cat_over.depletion_rate, 110.0)
        self.assertEqual(cat_over.status, "DEPLETED")

        # Zero announced units (defense against ZeroDivisionError)
        cat_zero = tracker.calculate_category_metrics(0, 0, 0, 3_000_000)
        self.assertEqual(cat_zero.depletion_rate, 0.0)
        self.assertEqual(cat_zero.delivery_rate, 0.0)
        self.assertEqual(cat_zero.remaining_units, 0)
        self.assertEqual(cat_zero.status, "HEALTHY")

    def test_payload_serialization_roundtrip(self):
        """Verify complete SubsidyPayload serialization and deserialization."""
        payload = build_initial_baseline()
        as_dict = payload.to_dict()

        self.assertIn("metadata", as_dict)
        self.assertIn("alert_thresholds", as_dict)
        self.assertIn("nationwide_summary", as_dict)
        self.assertIn("regions", as_dict)
        self.assertIn("popular_models_matrix", as_dict)
        self.assertIn("historical_depletion_trajectory", as_dict)

        restored = SubsidyPayload.from_dict(as_dict)
        self.assertEqual(len(restored.regions), 17)
        self.assertEqual(restored.metadata.policy_year, 2026)
        self.assertEqual(restored.nationwide_summary.total_announced_units, payload.nationwide_summary.total_announced_units)


class TestAtomicWriter(unittest.TestCase):
    """Test POSIX crash-durable atomic JSON write."""

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.test_path = Path(self.test_dir.name) / "test_subsidy.json"

    def tearDown(self):
        self.test_dir.cleanup()

    def test_atomic_write_json(self):
        sample_data = {"test_key": "test_value", "number": 42}
        written_path = atomic_write_json(sample_data, self.test_path)

        self.assertTrue(written_path.exists())
        with open(written_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        self.assertEqual(loaded["test_key"], "test_value")
        self.assertEqual(loaded["number"], 42)

    def test_atomic_write_multiple(self):
        target1 = Path(self.test_dir.name) / "dest1.json"
        target2 = Path(self.test_dir.name) / "subdir" / "dest2.json"

        data = {"multi": True}
        written = atomic_write_json_multiple(data, [target1, target2])

        self.assertEqual(len(written), 2)
        self.assertTrue(target1.exists())
        self.assertTrue(target2.exists())


class TestSubsidyBaseline(unittest.TestCase):
    """Test baseline data authenticity and coverage."""

    def test_all_17_administrative_divisions(self):
        regions = build_baseline_regions()
        self.assertEqual(len(regions), 17)

        iso_codes = {r.iso_code for r in regions}
        expected_codes = {
            "KR-11", "KR-26", "KR-27", "KR-28", "KR-29", "KR-30", "KR-31",
            "KR-36", "KR-41", "KR-42", "KR-43", "KR-44", "KR-45", "KR-46",
            "KR-47", "KR-48", "KR-49",
        }
        self.assertEqual(iso_codes, expected_codes)

        for r in regions:
            self.assertIn("passenger", r.categories)
            self.assertIn("commercial", r.categories)
            self.assertIn("bus", r.categories)
            self.assertIn(r.overall_status, ("HEALTHY", "CAUTION", "WARNING", "CRITICAL", "DEPLETED"))
            self.assertGreater(r.residency_requirement_days, 0)

    def test_popular_models(self):
        models = build_popular_models()
        self.assertGreaterEqual(len(models), 8)

        model_ids = {m.model_id for m in models}
        self.assertIn("ioniq-5-2026", model_ids)
        self.assertIn("kia-ev3-2026", model_ids)
        self.assertIn("tesla-model-y-rwd", model_ids)
        self.assertIn("kgm-torres-evx", model_ids)
        self.assertIn("byd-atto-3", model_ids)

        for m in models:
            self.assertIn(m.price_subsidy_ratio, (1.0, 0.5, 0.0))
            self.assertIn("seoul", m.regional_subsidy_samples)
            self.assertIn("gyeonggi_avg", m.regional_subsidy_samples)
            self.assertIn("busan", m.regional_subsidy_samples)
            self.assertIn("daegu", m.regional_subsidy_samples)
            self.assertIn("jeju", m.regional_subsidy_samples)
            self.assertIn("gurye_jeonnam", m.regional_subsidy_samples)
            self.assertIn("ulleung_gyeongbuk", m.regional_subsidy_samples)


class TestSubsidyTrackerEngine(unittest.TestCase):
    """Test tracker logic, resilience, and fallback behaviors."""

    def test_network_failure_fallback(self):
        """Tracker must cleanly fallback to baseline without raising on network failure."""
        tracker = SubsidyTracker(endpoint_url="http://127.0.0.1:59999/non_existent_api")
        payload, fallback_used = tracker.execute_tracking_cycle(mock_network_failure=True)

        self.assertTrue(fallback_used)
        self.assertIsNotNone(payload)
        self.assertEqual(len(payload.regions), 17)
        self.assertGreater(payload.nationwide_summary.nationwide_depletion_rate, 80.0)

    def test_recalculate_metrics_integrity(self):
        """Verify regional and national aggregations."""
        tracker = SubsidyTracker()
        payload = build_initial_baseline()

        # Modify a region's applications and check recalculation
        r = payload.regions[0]
        r.categories["passenger"].applied_units = r.categories["passenger"].announced_units
        updated_r = tracker.update_region_metrics(r)
        self.assertEqual(updated_r.categories["passenger"].remaining_units, 0)
        self.assertEqual(updated_r.categories["passenger"].status, "DEPLETED")

    def test_briefing_generation(self):
        """Test executive summary briefing text generation."""
        tracker = SubsidyTracker()
        payload = build_initial_baseline()
        briefing = tracker.generate_briefing(payload, fallback_used=True)

        self.assertIn("전국 지자체 전기차 보조금", briefing)
        self.assertIn("전국 평균 소진율", briefing)
        self.assertIn("차종별 소진 현황", briefing)


class TestCLIRunner(unittest.TestCase):
    """Test CLI runner behavior."""

    def test_dry_run_cli(self):
        res = subprocess.run(
            [sys.executable, "run_tracker.py", "--dry-run", "--verbose"],
            cwd=str(Path(__file__).resolve().parent.parent),
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("Dry-run requested", res.stderr + res.stdout)
        self.assertIn("전국 평균 소진율", res.stdout)

    def test_sync_web_cli(self):
        root = Path(__file__).resolve().parent.parent
        res = subprocess.run(
            [sys.executable, "run_tracker.py", "--sync-web", "--verbose"],
            cwd=str(root),
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)

        # Check target files exist
        if (root / "ev-stealth-web").exists():
            p1 = root / "data" / "ev_subsidy_data.json"
            p2 = root / "ev-stealth-web" / "src" / "data" / "ev_subsidy_data.json"
            p3 = root / "data" / "subsidy_depletion_data.json"
            p4 = root / "ev-stealth-web" / "src" / "data" / "subsidy_depletion_data.json"
        else:
            p1 = root / "src" / "data" / "ev_subsidy_data.json"
            p2 = root / "src" / "data" / "subsidy_depletion_data.json"
            p3 = (root.parent / "data" / "ev_subsidy_data.json") if (root.parent / "data").exists() else p1
            p4 = (root.parent / "data" / "subsidy_depletion_data.json") if (root.parent / "data").exists() else p2

        self.assertTrue(p1.exists(), f"Missing {p1}")
        self.assertTrue(p2.exists(), f"Missing {p2}")
        self.assertTrue(p3.exists(), f"Missing {p3}")
        self.assertTrue(p4.exists(), f"Missing {p4}")

        with open(p1, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertIn("metadata", data)
            self.assertEqual(len(data["regions"]), 17)

    def test_run_tracker_sh_script(self):
        root = Path(__file__).resolve().parent.parent
        script = root / "run_tracker.sh"
        if not script.exists() and (root.parent / "run_tracker.sh").exists():
            script = root.parent / "run_tracker.sh"
        if not script.exists():
            self.skipTest(f"run_tracker.sh not found at {script}")
        res = subprocess.run(
            ["bash", str(script), "--dry-run"],
            cwd=str(root),
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("[SUCCESS]", res.stdout)

    def test_corrupted_cache_fallback(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
            tf.write("{ invalid json corrupted content ...")
            temp_path = tf.name

        try:
            tracker = SubsidyTracker(cache_fallback_path=temp_path)
            payload, fallback_used = tracker.execute_tracking_cycle()
            self.assertTrue(fallback_used)
            self.assertIsNotNone(payload)
            self.assertEqual(len(payload.regions), 17)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


if __name__ == "__main__":
    unittest.main()

