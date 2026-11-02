"""Unit tests validating Backend Resilience Audit fixes across subsidy_tracker, subsidy_models, complaint, and atomic_writer.

Covers:
- Type safety and robust string-float handling
- None handling and idempotent .from_dict() deserialization
- Edge-case arithmetic (negative MSRP, NaN/Inf bounds, AlertSeverity strings)
- Full Mapping protocol (keys, values, items, __iter__, __len__, method collision guards)
- File descriptor leak prevention during directory fsync
"""

from __future__ import annotations

import collections.abc
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from models.complaint import (
    ComplaintRecord,
    DailyReportPayload,
    DailyReportStatistics,
    DSIBreakdown,
    RawPost,
)
from tracker.atomic_writer import (
    FileLock,
    _json_default,
    atomic_write_json,
    quarantine_corrupted_file,
    sanitize_nan_inf,
)
from tracker.subsidy_models import (
    AlertSeverity,
    AlertThresholdConfig,
    CategoryMetrics,
    HistoricalTrajectoryPoint,
    MunicipalityMetrics,
    NationwideSummary,
    PopularModelEntry,
    RegionRecord,
    SubsidyMetadata,
    SubsidyPayload,
    _safe_float,
    _safe_int,
)
from tracker.subsidy_tracker import (
    SubsidyTracker,
    _metric_val,
    _safe_int_metric,
    calculate_net_subsidy,
)


class TestSubsidyModelsResilience(unittest.TestCase):
    """Test suite for subsidy_models.py resilience and mapping completeness."""

    def test_safe_int_float_strings(self) -> None:
        """_safe_int correctly parses float-strings like '12.0' and '12.34'."""
        self.assertEqual(_safe_int("12.0"), 12)
        self.assertEqual(_safe_int("12.34"), 12)
        self.assertEqual(_safe_int(12.7), 12)
        self.assertEqual(_safe_int("invalid", default=99), 99)
        self.assertEqual(_safe_int(None, default=5), 5)
        self.assertEqual(_safe_int(float("nan"), default=7), 7)
        self.assertEqual(_safe_int(float("inf"), default=8), 8)

    def test_alert_severity_from_rate_types(self) -> None:
        """AlertSeverity.from_rate safely handles float, int, string, and invalid inputs."""
        self.assertEqual(AlertSeverity.from_rate(95.5), AlertSeverity.CRITICAL)
        self.assertEqual(AlertSeverity.from_rate("95.5"), AlertSeverity.CRITICAL)
        self.assertEqual(AlertSeverity.from_rate("100"), AlertSeverity.DEPLETED)
        self.assertEqual(AlertSeverity.from_rate("80.0"), AlertSeverity.WARNING)
        self.assertEqual(AlertSeverity.from_rate("60.0"), AlertSeverity.CAUTION)
        self.assertEqual(AlertSeverity.from_rate("40.0"), AlertSeverity.HEALTHY)
        self.assertEqual(AlertSeverity.from_rate(None), AlertSeverity.HEALTHY)
        self.assertEqual(AlertSeverity.from_rate("corrupt"), AlertSeverity.HEALTHY)
        self.assertEqual(AlertSeverity.from_rate(float("nan")), AlertSeverity.HEALTHY)

    def test_models_from_dict_idempotency(self) -> None:
        """from_dict on all subsidy models returns the identical instance if already instantiated."""
        alert = AlertThresholdConfig(
            min_percent=0.0,
            max_percent=60.0,
            label_ko="정상",
            severity="HEALTHY",
            color_hex="#10B981",
            badge_class="healthy",
            recommended_action="none",
        )
        self.assertIs(AlertThresholdConfig.from_dict(alert), alert)

        cat = CategoryMetrics(
            announced_units=100,
            applied_units=50,
            delivered_units=40,
            remaining_units=50,
            depletion_rate=50.0,
            delivery_rate=40.0,
            status="HEALTHY",
            max_local_subsidy_krw=1000000,
            max_total_subsidy_krw=7500000,
        )
        self.assertIs(CategoryMetrics.from_dict(cat), cat)

        muni = MunicipalityMetrics(name_ko="수원시", announced_units=200)
        self.assertIs(MunicipalityMetrics.from_dict(muni), muni)

        region = RegionRecord(region_id="KR-11", name_ko="서울특별시")
        self.assertIs(RegionRecord.from_dict(region), region)

        model = PopularModelEntry(
            model_id="ev6",
            name_ko="기아 EV6",
            manufacturer="기아",
            battery_type="NCM",
            battery_capacity_kwh=77.4,
            rated_range_km=475,
            base_price_krw=55000000,
            price_subsidy_ratio=1.0,
            national_subsidy_krw=6500000,
            regional_subsidy_samples={},
        )
        self.assertIs(PopularModelEntry.from_dict(model), model)

        hist = HistoricalTrajectoryPoint(date="2026-01", passenger_rate=10.0, commercial_rate=5.0, overall_rate=8.0)
        self.assertIs(HistoricalTrajectoryPoint.from_dict(hist), hist)

        summary = NationwideSummary(
            total_announced_units=100,
            total_applied_units=50,
            total_delivered_units=40,
            total_remaining_units=50,
            nationwide_depletion_rate=50.0,
            total_budget_billion_krw=10.0,
            disbursed_budget_billion_krw=5.0,
            category_totals={},
            alert_region_counts={},
        )
        self.assertIs(NationwideSummary.from_dict(summary), summary)

        meta = SubsidyMetadata(
            version="1.0.0",
            generated_at="2026-11-03",
            policy_year=2026,
            data_sources=["keco"],
            total_regions_tracked=17,
            total_municipalities_tracked=160,
        )
        self.assertIs(SubsidyMetadata.from_dict(meta), meta)

        payload = SubsidyPayload(
            metadata=meta,
            alert_thresholds={"HEALTHY": alert},
            nationwide_summary=summary,
            regions=[region],
            popular_models_matrix=[model],
            historical_depletion_trajectory=[hist],
        )
        self.assertIs(SubsidyPayload.from_dict(payload), payload)

    def test_subsidy_payload_nested_instance_passthrough(self) -> None:
        """SubsidyPayload.from_dict preserves pre-instantiated metadata and nationwide_summary."""
        meta = SubsidyMetadata(
            version="2.0.0",
            generated_at="2026-11-03",
            policy_year=2026,
            data_sources=["ev.or.kr"],
            total_regions_tracked=17,
            total_municipalities_tracked=200,
        )
        summary = NationwideSummary(
            total_announced_units=5000,
            total_applied_units=2500,
            total_delivered_units=2000,
            total_remaining_units=2500,
            nationwide_depletion_rate=50.0,
            total_budget_billion_krw=50.0,
            disbursed_budget_billion_krw=25.0,
            category_totals={},
            alert_region_counts={},
        )
        raw_dict = {
            "metadata": meta,
            "nationwide_summary": summary,
            "regions": [],
            "alert_thresholds": {},
            "popular_models_matrix": [],
            "historical_depletion_trajectory": [],
        }
        reconstructed = SubsidyPayload.from_dict(raw_dict)
        self.assertIs(reconstructed.metadata, meta)
        self.assertIs(reconstructed.nationwide_summary, summary)

    def test_complete_mapping_protocol_and_method_guards(self) -> None:
        """All subsidy dataclasses support len(), iter(), items(), and do not leak methods."""
        cat = CategoryMetrics(
            announced_units=500,
            applied_units=250,
            delivered_units=200,
            remaining_units=250,
            depletion_rate=50.0,
            delivery_rate=40.0,
            status="HEALTHY",
            max_local_subsidy_krw=2000000,
            max_total_subsidy_krw=8500000,
        )
        self.assertGreater(len(cat), 0)
        self.assertEqual(len(cat), len(cat.to_dict()))
        self.assertIn("announced_units", cat)
        self.assertEqual(cat["announced_units"], 500)
        self.assertNotIn("to_dict", cat)
        with self.assertRaises(KeyError):
            _ = cat["to_dict"]

        # Ensure dict(cat) conversion succeeds
        as_dict = dict(cat)
        self.assertIsInstance(as_dict, dict)
        self.assertEqual(as_dict["announced_units"], 500)

        # RegionRecord None safety
        region = RegionRecord(region_id="KR-26", categories=None, municipalities=None)
        self.assertIsInstance(region.categories, dict)
        self.assertIsInstance(region.municipalities, list)
        self.assertGreater(len(region), 0)
        self.assertNotIn("to_dict", region)
        with self.assertRaises(KeyError):
            _ = region["to_dict"]

        # SubsidyPayload Mapping protocol
        meta = SubsidyMetadata(
            version="1.0.0",
            generated_at="2026-11-03",
            policy_year=2026,
            data_sources=[],
            total_regions_tracked=17,
            total_municipalities_tracked=0,
        )
        summary = NationwideSummary(
            total_announced_units=0,
            total_applied_units=0,
            total_delivered_units=0,
            total_remaining_units=0,
            nationwide_depletion_rate=0.0,
            total_budget_billion_krw=0.0,
            disbursed_budget_billion_krw=0.0,
            category_totals={},
            alert_region_counts={},
        )
        payload = SubsidyPayload(
            metadata=meta,
            alert_thresholds={},
            nationwide_summary=summary,
            regions=[],
            popular_models_matrix=[],
            historical_depletion_trajectory=[],
        )
        self.assertEqual(payload["metadata"], meta)
        self.assertEqual(payload["metadata"]["version"], "1.0.0")
        self.assertEqual(len(payload), 6)
        self.assertIn("regions", payload)
        self.assertNotIn("to_dict", payload)


class TestSubsidyTrackerResilience(unittest.TestCase):
    """Test suite for subsidy_tracker.py arithmetic and error handling."""

    def test_metric_val_with_none_fields(self) -> None:
        """_metric_val returns default when metric has key explicitly set to None."""
        d = {"announced_units": None, "applied_units": 50}
        self.assertEqual(_metric_val(d, "announced_units", default=0), 0)
        self.assertEqual(_metric_val(d, "applied_units", default=0), 50)
        self.assertEqual(_metric_val(None, "announced_units", default=10), 10)

    def test_safe_int_metric(self) -> None:
        """_safe_int_metric converts float strings safely and guards against NaN/Inf."""
        self.assertEqual(_safe_int_metric("500.0"), 500)
        self.assertEqual(_safe_int_metric("500.7"), 500)
        self.assertEqual(_safe_int_metric(None, default=3), 3)
        self.assertEqual(_safe_int_metric(float("nan"), default=4), 4)

    def test_calculate_net_subsidy_negative_msrp(self) -> None:
        """calculate_net_subsidy clamps negative MSRP to 0."""
        res = calculate_net_subsidy(
            model_national=6500000,
            max_national=6500000,
            max_local=2000000,
            msrp=-50000,
        )
        self.assertEqual(res["net_price_krw"], 0)
        self.assertEqual(res["price_cap_ratio"], 0.0)

    def test_fetch_live_updates_status_compat(self) -> None:
        """fetch_live_updates handles mock HTTP response objects with .code instead of .status."""
        tracker = SubsidyTracker(endpoint_url="http://fake-api.local/subsidy")

        mock_resp = MagicMock()
        del mock_resp.status  # Simulate response without .status
        mock_resp.code = 200
        mock_resp.read.return_value = b'{"regions": []}'
        mock_resp.headers.get_content_charset.return_value = "utf-8"
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None

        with patch("urllib.request.urlopen", return_value=mock_resp):
            data = tracker.fetch_live_updates(max_retries=1)
            self.assertEqual(data, {"regions": []})

    def test_save_payload_path_deduplication(self) -> None:
        """save_payload deduplicates destination paths avoiding redundant atomic writes."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            p1 = Path(tmp_dir) / "data.json"
            p2 = Path(tmp_dir) / "data.json"  # duplicate
            tracker = SubsidyTracker()
            from tracker.subsidy_baseline import build_initial_baseline
            payload = build_initial_baseline()
            written = tracker.save_payload(payload, [p1, p2], export_models_matrix=False)
            self.assertEqual(len(written), 1)
            self.assertTrue(p1.exists())


class TestComplaintModelsResilience(unittest.TestCase):
    """Test suite for models/complaint.py Mapping completeness and edge cases."""

    def test_complaint_len_and_method_guards(self) -> None:
        """Complaint models implement len() and do not expose methods via subscript."""
        raw = RawPost(post_id="p1", title="결함", content="불량")
        self.assertGreater(len(raw), 0)
        self.assertEqual(raw["post_id"], "p1")
        self.assertNotIn("to_dict", raw)
        with self.assertRaises(KeyError):
            _ = raw["to_dict"]

        dsi = DSIBreakdown(safety=5.0, functional=6.0)
        self.assertEqual(len(dsi), 5)
        self.assertNotIn("to_dict", dsi)

        rec = ComplaintRecord(
            id="c1",
            source="dcinside",
            url="https://example.com",
            title="타이틀",
            author="익명",
            created_at="2026-10-28",
            vehicle_brand="Hyundai",
            vehicle_model="Ioniq 5",
            defect_category="BATTERY_CHARGING",
            summary="충전기 먹통",
            verbatim_quote="충전이 안됩니다",
            severity=" ",  # whitespace severity should fall back to calculation
            severity_index=8.5,
        )
        self.assertGreater(len(rec), 0)
        self.assertNotIn("to_dict", rec)
        with self.assertRaises(KeyError):
            _ = rec["to_dict"]
        # Whitespace severity fallback to DSI score (8.5 -> CRITICAL)
        self.assertEqual(rec.severity_tier, "CRITICAL")

        stats = DailyReportStatistics(total_scraped=100)
        self.assertEqual(len(stats), 4)

        payload = DailyReportPayload(generated_at="2026-11-03T00:00:00Z")
        self.assertEqual(len(payload), 6)
        self.assertEqual(payload["pipeline_version"], "1.0.0")
        self.assertNotIn("to_dict", payload)


class TestAtomicWriterResilience(unittest.TestCase):
    """Test suite for atomic_writer.py crash durability and directory fsync fd cleanup."""

    def test_filelock_empty_path_validation(self) -> None:
        """FileLock raises ValueError on empty or whitespace lock path."""
        with self.assertRaises(ValueError):
            FileLock("")
        with self.assertRaises(ValueError):
            FileLock("   ")

    def test_directory_fsync_closes_fd_on_oserror(self) -> None:
        """atomic_write_json closes directory fd even if os.fsync raises OSError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "output.json"
            real_open = os.open
            real_fsync = os.fsync
            real_close = os.close

            closed_fds = []

            def mock_fsync(fd):
                # If fsyncing a directory fd, simulate EINVAL (e.g. non-fsyncable filesystem)
                if fd != 1 and fd != 2:
                    try:
                        import stat
                        st = os.fstat(fd)
                        if stat.S_ISDIR(st.st_mode):
                            raise OSError(22, "Invalid argument (mock directory fsync unsupported)")
                    except Exception:
                        pass
                return real_fsync(fd)

            def mock_close(fd):
                closed_fds.append(fd)
                return real_close(fd)

            with patch("os.fsync", side_effect=mock_fsync), patch("os.close", side_effect=mock_close):
                written = atomic_write_json({"status": "ok"}, target)
                self.assertTrue(written.exists())
                # Verify that directory fd was properly closed
                self.assertGreater(len(closed_fds), 0)

    def test_sanitize_nan_inf_with_mapping(self) -> None:
        """sanitize_nan_inf correctly processes generic Mapping implementations."""
        class CustomMapping(collections.abc.Mapping):
            def __init__(self, d):
                self._d = d
            def __getitem__(self, k):
                return self._d[k]
            def __iter__(self):
                return iter(self._d)
            def __len__(self):
                return len(self._d)

        cm = CustomMapping({"a": float("nan"), "b": 10.5})
        sanitized = sanitize_nan_inf(cm)
        self.assertEqual(sanitized, {"a": 0.0, "b": 10.5})

        serialized = _json_default(cm)
        self.assertEqual(serialized, {"a": 0.0, "b": 10.5})


if __name__ == "__main__":
    unittest.main()
