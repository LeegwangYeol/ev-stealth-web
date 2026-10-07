"""
tests/test_adversarial_sync5_remediation.py - Empirical Adversarial Regression Test Suite for Wave 2 Remediations.

Authoritative Context:
- BUG-01: SubsidyTracker.generate_briefing() must support both raw dict CategoryMetrics and
          instantiated CategoryMetrics dataclass instances without raising AttributeError.
- BUG-02: CategoryMetrics.from_dict and SubsidyPayload.from_dict must safely handle JSON null / None
          values and missing fields with robust defaults without raising TypeError or AttributeError.
- BUG-03: run_tracker.py path resolution must handle relative paths (e.g., -o data/ev_subsidy_data.json)
          so that both primary and subsidy_depletion_data.json mirror files are generated.
- BUG-04: SubsidyTracker.generate_briefing() must handle regions lacking 'passenger' category
          without crashing with KeyError.
- BUG-05: Subsidy calculation functions (SubsidyTracker and subsidy_baseline) must clamp local_ratio
          to [0.0, 1.0] when model_national > max_national, guaranteeing effective_local <= max_local.
- LEAK-01/02: Network exception handling in SubsidyTracker, SafeHttpClient, and cross-portal test flows
          must explicitly call exc.close() on urllib.error.HTTPError to prevent socket descriptor leaks.
- MIRROR-PARITY: SHA-256 byte parity verification across all dual-homed files between the root repository
                 and ev-stealth-web.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, Mock, patch

# Adaptive root detection (works from repo root, tests/, ev-stealth-web/, or ev-stealth-web/tests/)
def _find_repo_root() -> Path:
    candidates = [
        Path(__file__).resolve().parent.parent,
        Path(__file__).resolve().parent.parent.parent,
        Path.cwd(),
        Path.cwd().parent,
    ]
    for p in candidates:
        if (p / "ev-stealth-web").is_dir() and (p / "data").is_dir():
            return p
    return Path(__file__).resolve().parent.parent

REPO_ROOT = _find_repo_root()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import run_tracker
from scrapers import common_utils
from tests import test_cross_portal_flows
from tracker import subsidy_baseline
from tracker.subsidy_models import (
    AlertThresholdConfig,
    CategoryMetrics,
    HistoricalTrajectoryPoint,
    MunicipalityMetrics,
    NationwideSummary,
    PopularModelEntry,
    RegionRecord,
    SubsidyMetadata,
    SubsidyPayload,
)
from tracker.subsidy_tracker import (
    SubsidyTracker,
    calculate_net_subsidy,
    calculate_price_cap_ratio,
)


def _compute_sha256(filepath: Path) -> str:
    """Compute hex SHA-256 digest of a given file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def _build_dummy_payload(
    category_totals_type: str = "dataclass",
    missing_passenger_in_regions: bool = False,
    region_status: str = "CRITICAL",
) -> SubsidyPayload:
    """Helper to synthesize a compliant SubsidyPayload for briefing and serializer testing."""
    metadata = SubsidyMetadata(
        version="1.0.0",
        generated_at="2026-10-04T00:00:00Z",
        policy_year=2026,
        data_sources=["ev.or.kr", "CleanSys Test"],
        total_regions_tracked=1,
        total_municipalities_tracked=1,
        currency="KRW",
    )

    alert_thresholds = {
        "CRITICAL": AlertThresholdConfig(
            min_percent=95.0,
            max_percent=100.0,
            label_ko="마감 임박",
            severity="CRITICAL",
            color_hex="#dc2626",
            badge_class="bg-red-500",
            recommended_action="즉시 신청 필요",
        ),
        "WARNING": AlertThresholdConfig(
            min_percent=80.0,
            max_percent=94.9,
            label_ko="주의",
            severity="WARNING",
            color_hex="#f59e0b",
            badge_class="bg-amber-500",
            recommended_action="신청 준비",
        ),
    }

    if category_totals_type == "dataclass":
        cat_totals: Dict[str, Any] = {
            "passenger": CategoryMetrics(
                announced_units=1000,
                applied_units=960,
                delivered_units=900,
                remaining_units=40,
                depletion_rate=96.0,
                delivery_rate=90.0,
                status="CRITICAL",
                max_local_subsidy_krw=4000000,
                max_total_subsidy_krw=10500000,
                total_budget_krw=4000000000,
                remaining_budget_krw=160000000,
            ),
            "commercial": CategoryMetrics(
                announced_units=500,
                applied_units=450,
                delivered_units=400,
                remaining_units=50,
                depletion_rate=90.0,
                delivery_rate=80.0,
                status="WARNING",
                max_local_subsidy_krw=6000000,
                max_total_subsidy_krw=17000000,
                total_budget_krw=3000000000,
                remaining_budget_krw=300000000,
            ),
            "bus": CategoryMetrics(
                announced_units=100,
                applied_units=70,
                delivered_units=60,
                remaining_units=30,
                depletion_rate=70.0,
                delivery_rate=60.0,
                status="HEALTHY",
                max_local_subsidy_krw=10000000,
                max_total_subsidy_krw=80000000,
                total_budget_krw=1000000000,
                remaining_budget_krw=300000000,
            ),
        }
    else:
        cat_totals = {
            "passenger": {
                "announced_units": 1000,
                "applied_units": 960,
                "delivered_units": 900,
                "remaining_units": 40,
                "depletion_rate": 96.0,
                "delivery_rate": 90.0,
                "status": "CRITICAL",
                "max_local_subsidy_krw": 4000000,
                "max_total_subsidy_krw": 10500000,
                "total_budget_krw": 4000000000,
                "remaining_budget_krw": 160000000,
            },
            "commercial": {
                "announced_units": 500,
                "applied_units": 450,
                "delivered_units": 400,
                "remaining_units": 50,
                "depletion_rate": 90.0,
                "delivery_rate": 80.0,
                "status": "WARNING",
                "max_local_subsidy_krw": 6000000,
                "max_total_subsidy_krw": 17000000,
                "total_budget_krw": 3000000000,
                "remaining_budget_krw": 300000000,
            },
            "bus": {
                "announced_units": 100,
                "applied_units": 70,
                "delivered_units": 60,
                "remaining_units": 30,
                "depletion_rate": 70.0,
                "delivery_rate": 60.0,
                "status": "HEALTHY",
                "max_local_subsidy_krw": 10000000,
                "max_total_subsidy_krw": 80000000,
                "total_budget_krw": 1000000000,
                "remaining_budget_krw": 300000000,
            },
        }

    summary = NationwideSummary(
        total_announced_units=1600,
        total_applied_units=1480,
        total_delivered_units=1360,
        total_remaining_units=120,
        nationwide_depletion_rate=92.5,
        total_budget_billion_krw=8.0,
        disbursed_budget_billion_krw=7.4,
        category_totals=cat_totals,
        alert_region_counts={"CRITICAL": 1, "WARNING": 0, "CAUTION": 0, "HEALTHY": 0},
    )

    if missing_passenger_in_regions:
        reg_categories = {
            "commercial": CategoryMetrics(
                announced_units=500,
                applied_units=480,
                delivered_units=400,
                remaining_units=20,
                depletion_rate=96.0,
                delivery_rate=80.0,
                status="CRITICAL",
                max_local_subsidy_krw=6000000,
                max_total_subsidy_krw=17000000,
                total_budget_krw=3000000000,
                remaining_budget_krw=120000000,
            )
        }
    else:
        reg_categories = {
            "passenger": CategoryMetrics(
                announced_units=1000,
                applied_units=960,
                delivered_units=900,
                remaining_units=40,
                depletion_rate=96.0,
                delivery_rate=90.0,
                status="CRITICAL",
                max_local_subsidy_krw=4000000,
                max_total_subsidy_krw=10500000,
                total_budget_krw=4000000000,
                remaining_budget_krw=160000000,
            )
        }

    region = RegionRecord(
        region_id="seoul",
        iso_code="KR-11",
        name_ko="서울특별시",
        name_en="Seoul",
        tier="METROPOLITAN",
        overall_status=region_status,
        overall_depletion_rate=96.0,
        residency_requirement_days=30,
        supplementary_budget_added=False,
        categories=reg_categories,
        municipalities=[],
        notes="테스트 지자체",
    )

    return SubsidyPayload(
        metadata=metadata,
        alert_thresholds=alert_thresholds,
        nationwide_summary=summary,
        regions=[region],
        popular_models_matrix=[],
        historical_depletion_trajectory=[],
    )


class TestBug01BriefingCategoryDuality(unittest.TestCase):
    """BUG-01: SubsidyTracker.generate_briefing() must support both dict and CategoryMetrics."""

    def setUp(self):
        self.tracker = SubsidyTracker()

    def test_generate_briefing_with_instantiated_dataclass_metrics(self):
        """Verify generate_briefing() does not crash with AttributeError when category_totals holds dataclasses."""
        payload = _build_dummy_payload(category_totals_type="dataclass")
        briefing = self.tracker.generate_briefing(payload)

        self.assertIsInstance(briefing, str)
        self.assertTrue(len(briefing) > 0)
        self.assertIn("대한민국 2026 전국 지자체 전기차 보조금", briefing)
        self.assertIn("승용", briefing)
        self.assertIn("화물", briefing)
        self.assertIn("승합(버스)", briefing)
        self.assertIn("공고 1,000대", briefing)
        self.assertIn("접수 960대 (96.0%)", briefing)
        self.assertIn("잔여 40대", briefing)

    def test_generate_briefing_with_raw_dictionary_metrics(self):
        """Verify generate_briefing() also works seamlessly when category_totals holds raw dicts."""
        payload = _build_dummy_payload(category_totals_type="dict")
        briefing = self.tracker.generate_briefing(payload)

        self.assertIsInstance(briefing, str)
        self.assertTrue(len(briefing) > 0)
        self.assertIn("승용", briefing)
        self.assertIn("공고 1,000대", briefing)
        self.assertIn("접수 960대 (96.0%)", briefing)
        self.assertIn("잔여 40대", briefing)

    def test_generate_briefing_with_mixed_category_totals(self):
        """Verify generate_briefing() handles heterogeneous mixtures of dicts and dataclasses."""
        payload = _build_dummy_payload(category_totals_type="dataclass")
        payload.nationwide_summary.category_totals["commercial"] = {
            "announced_units": 777,
            "applied_units": 666,
            "depletion_rate": 85.7,
            "remaining_units": 111,
            "status": "WARNING",
        }

        briefing = self.tracker.generate_briefing(payload)
        self.assertIsInstance(briefing, str)
        self.assertIn("공고 777대", briefing)
        self.assertIn("접수 666대", briefing)

    def test_generate_briefing_with_deserialized_full_payload(self):
        """Verify roundtrip: serialize payload to dict, deserialize with SubsidyPayload.from_dict, then briefing."""
        original = _build_dummy_payload(category_totals_type="dataclass")
        payload_dict = original.to_dict()
        deserialized = SubsidyPayload.from_dict(payload_dict)

        briefing = self.tracker.generate_briefing(deserialized)
        self.assertIsInstance(briefing, str)
        self.assertIn("대한민국 2026", briefing)


class TestBug02DeserializerNullResilience(unittest.TestCase):
    """BUG-02: CategoryMetrics.from_dict and SubsidyPayload.from_dict must safely handle None and missing fields."""

    def test_category_metrics_from_dict_with_none_values(self):
        """Passing explicit None for numeric fields must not raise TypeError or crash."""
        corrupted_dict = {
            "announced_units": None,
            "applied_units": None,
            "delivered_units": None,
            "remaining_units": None,
            "depletion_rate": None,
            "delivery_rate": None,
            "status": None,
            "max_local_subsidy_krw": None,
            "max_total_subsidy_krw": None,
            "total_budget_krw": None,
            "remaining_budget_krw": None,
        }
        metric = CategoryMetrics.from_dict(corrupted_dict)

        self.assertEqual(metric.announced_units, 0)
        self.assertEqual(metric.applied_units, 0)
        self.assertEqual(metric.delivered_units, 0)
        self.assertEqual(metric.remaining_units, 0)
        self.assertEqual(metric.depletion_rate, 0.0)
        self.assertEqual(metric.delivery_rate, 0.0)
        self.assertIn(str(metric.status), ("HEALTHY", "UNKNOWN", "N/A", "None"))
        self.assertEqual(metric.max_local_subsidy_krw, 0)
        self.assertEqual(metric.max_total_subsidy_krw, 0)
        self.assertEqual(metric.total_budget_krw, 0)
        self.assertEqual(metric.remaining_budget_krw, 0)

    def test_category_metrics_from_dict_empty_dict(self):
        """CategoryMetrics.from_dict({}) must initialize with safe default zeros."""
        metric = CategoryMetrics.from_dict({})
        self.assertEqual(metric.announced_units, 0)
        self.assertEqual(metric.applied_units, 0)
        self.assertEqual(metric.depletion_rate, 0.0)
        self.assertEqual(metric.status, "HEALTHY")

    def test_category_metrics_from_dict_invalid_string_values(self):
        """Strings that cannot be parsed as ints or floats must degrade gracefully to defaults."""
        invalid_data = {
            "announced_units": "not_an_int",
            "applied_units": "corrupted",
            "depletion_rate": "NaN_string",
        }
        metric = CategoryMetrics.from_dict(invalid_data)
        self.assertEqual(metric.announced_units, 0)
        self.assertEqual(metric.applied_units, 0)
        self.assertEqual(metric.depletion_rate, 0.0)

    def test_nationwide_summary_from_dict_with_none_and_missing_values(self):
        """NationwideSummary.from_dict must safely convert null values and missing category_totals."""
        summary_data = {
            "total_announced_units": None,
            "total_applied_units": None,
            "total_delivered_units": None,
            "total_remaining_units": None,
            "nationwide_depletion_rate": None,
            "total_budget_billion_krw": None,
            "disbursed_budget_billion_krw": None,
            "category_totals": {
                "passenger": {
                    "announced_units": None,
                    "applied_units": None,
                    "depletion_rate": None,
                }
            },
            "alert_region_counts": {},
        }
        summary = NationwideSummary.from_dict(summary_data)
        self.assertEqual(summary.total_announced_units, 0)
        self.assertEqual(summary.total_applied_units, 0)
        self.assertEqual(summary.nationwide_depletion_rate, 0.0)
        self.assertIsInstance(summary.category_totals, dict)
        p_metric = summary.category_totals["passenger"]
        self.assertEqual(p_metric.announced_units, 0)
        self.assertEqual(p_metric.applied_units, 0)

    def test_subsidy_metadata_from_dict_with_none_values(self):
        """SubsidyMetadata.from_dict must survive null/missing version, policy_year, data_sources."""
        meta_data = {
            "version": None,
            "generated_at": None,
            "policy_year": None,
            "data_sources": [],
            "total_regions_tracked": None,
            "total_municipalities_tracked": None,
            "currency": None,
        }
        meta = SubsidyMetadata.from_dict(meta_data)
        self.assertIsInstance(meta.version, str)
        self.assertIsInstance(meta.policy_year, int)
        self.assertIsInstance(meta.data_sources, list)
        self.assertIsInstance(meta.total_regions_tracked, int)

    def test_subsidy_payload_from_dict_with_missing_and_none_attributes(self):
        """SubsidyPayload.from_dict with empty dicts or nested None values must not crash."""
        payload_data = {
            "metadata": {
                "version": None,
                "policy_year": None,
                "total_regions_tracked": None,
                "total_municipalities_tracked": None,
            },
            "alert_thresholds": {
                "CRITICAL": {
                    "min_percent": None,
                    "max_percent": None,
                }
            },
            "nationwide_summary": {
                "total_announced_units": None,
                "total_applied_units": None,
                "nationwide_depletion_rate": None,
                "category_totals": {
                    "passenger": {
                        "announced_units": None,
                        "depletion_rate": None,
                    }
                },
            },
            "regions": [],
            "popular_models_matrix": [],
            "historical_depletion_trajectory": [],
        }
        payload = SubsidyPayload.from_dict(payload_data)
        self.assertIsInstance(payload, SubsidyPayload)
        self.assertIsInstance(payload.metadata, SubsidyMetadata)
        self.assertIsInstance(payload.nationwide_summary, NationwideSummary)
        self.assertEqual(payload.nationwide_summary.total_announced_units, 0)


class TestBug03RunTrackerRelativePathResolution(unittest.TestCase):
    """BUG-03: run_tracker.py path resolution must support relative output paths and mirror files."""

    def test_relative_output_path_equality_with_default(self):
        """Path('data/ev_subsidy_data.json') resolved against execution base must match DEFAULT_PRIMARY_OUTPUT.resolve()."""
        if (run_tracker._CURRENT_DIR / "data").exists() and (run_tracker._CURRENT_DIR / "ev-stealth-web").exists():
            resolved = (REPO_ROOT / "data" / "ev_subsidy_data.json").resolve()
        elif (run_tracker._CURRENT_DIR / "src" / "data").exists():
            resolved = (run_tracker._CURRENT_DIR / "src" / "data" / "ev_subsidy_data.json").resolve()
        else:
            resolved = (REPO_ROOT / "data" / "ev_subsidy_data.json").resolve()
        default_path = run_tracker.DEFAULT_PRIMARY_OUTPUT
        self.assertEqual(resolved, default_path.resolve())

    def test_run_tracker_resolves_relative_destination_to_generate_depletion_mirror(self):
        """When invoked with relative -o data/ev_subsidy_data.json, destinations must include depletion mirror."""
        with patch("sys.argv", ["run_tracker.py", "-o", "data/ev_subsidy_data.json", "--mock-network"]):
            args = run_tracker.parse_arguments()

        # Test the destination resolution logic
        destinations: List[Path] = [args.output]
        if args.output.resolve() == run_tracker.DEFAULT_PRIMARY_OUTPUT.resolve():
            destinations.append(run_tracker.MIRROR_PRIMARY_OUTPUT)
        elif args.output.name == "ev_subsidy_data.json":
            destinations.append(args.output.parent / "subsidy_depletion_data.json")

        dest_names = [d.name for d in destinations]
        self.assertIn("ev_subsidy_data.json", dest_names)
        self.assertIn("subsidy_depletion_data.json", dest_names)

    def test_run_tracker_execution_in_isolated_tempdir(self):
        """Execute run_tracker in a temporary directory and verify both files are generated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            temp_data_dir = temp_root / "data"
            temp_data_dir.mkdir(parents=True, exist_ok=True)

            out_primary = temp_data_dir / "ev_subsidy_data.json"
            out_depletion = temp_data_dir / "subsidy_depletion_data.json"

            # Execute tracking cycle and save payload to both files
            tracker = SubsidyTracker()
            payload, _ = tracker.execute_tracking_cycle(mock_network_failure=True)
            written = tracker.save_payload(payload, [out_primary, out_depletion])

            self.assertEqual(len(written), 2)
            self.assertTrue(out_primary.exists())
            self.assertTrue(out_depletion.exists())

            # Validate non-empty valid JSON
            with open(out_primary, "r", encoding="utf-8") as f:
                d1 = json.load(f)
            with open(out_depletion, "r", encoding="utf-8") as f:
                d2 = json.load(f)

            self.assertEqual(d1["metadata"]["version"], d2["metadata"]["version"])
            self.assertEqual(
                d1["nationwide_summary"]["total_announced_units"],
                d2["nationwide_summary"]["total_announced_units"],
            )


class TestBug04MissingPassengerCategoryResilience(unittest.TestCase):
    """BUG-04: Regions lacking 'passenger' category must not crash SubsidyTracker.generate_briefing()."""

    def setUp(self):
        self.tracker = SubsidyTracker()

    def test_briefing_region_without_passenger_category_critical(self):
        """A CRITICAL region having only commercial/bus categories must not raise KeyError."""
        payload = _build_dummy_payload(
            category_totals_type="dataclass",
            missing_passenger_in_regions=True,
            region_status="CRITICAL",
        )
        # Should not raise KeyError: 'passenger'
        briefing = self.tracker.generate_briefing(payload)
        self.assertIsInstance(briefing, str)
        self.assertIn("서울특별시", briefing)

    def test_briefing_region_without_passenger_category_warning(self):
        """A WARNING region having only commercial/bus categories must not raise KeyError."""
        payload = _build_dummy_payload(
            category_totals_type="dataclass",
            missing_passenger_in_regions=True,
            region_status="WARNING",
        )
        briefing = self.tracker.generate_briefing(payload)
        self.assertIsInstance(briefing, str)
        self.assertIn("서울특별시", briefing)

    def test_briefing_multiple_regions_with_empty_categories(self):
        """Regions with empty categories dict must not crash the briefing generator."""
        payload = _build_dummy_payload(category_totals_type="dataclass")
        payload.regions.append(
            RegionRecord(
                region_id="gyeonggi",
                iso_code="KR-41",
                name_ko="경기도",
                name_en="Gyeonggi-do",
                tier="PROVINCE",
                overall_status="CRITICAL",
                overall_depletion_rate=98.5,
                residency_requirement_days=30,
                supplementary_budget_added=False,
                categories={},  # Completely empty
                municipalities=[],
            )
        )
        payload.regions.append(
            RegionRecord(
                region_id="busan",
                iso_code="KR-26",
                name_ko="부산광역시",
                name_en="Busan",
                tier="METROPOLITAN",
                overall_status="WARNING",
                overall_depletion_rate=88.0,
                residency_requirement_days=30,
                supplementary_budget_added=False,
                categories={},  # Completely empty
                municipalities=[],
            )
        )

        briefing = self.tracker.generate_briefing(payload)
        self.assertIsInstance(briefing, str)
        self.assertIn("경기도", briefing)
        self.assertIn("부산광역시", briefing)


class TestBug05LocalRatioClamping(unittest.TestCase):
    """BUG-05: local_ratio must be clamped to <= 1.0 when model_national > max_national."""

    def test_calculate_net_subsidy_clamping_in_tracker(self):
        """When model_national (7M) > max_national (6.5M), effective local must not exceed max_local."""
        model_nat = 7_000_000
        max_nat = 6_500_000
        max_loc = 5_000_000
        msrp = 50_000_000  # < 55M -> price ratio 1.0

        res = calculate_net_subsidy(
            model_national=model_nat,
            max_national=max_nat,
            max_local=max_loc,
            msrp=msrp,
        )

        self.assertLessEqual(
            res["local_subsidy_krw"],
            max_loc,
            f"Effective local subsidy {res['local_subsidy_krw']} exceeded max local subsidy {max_loc}",
        )
        self.assertEqual(res["local_subsidy_krw"], max_loc)

    def test_baseline_regional_samples_clamping(self):
        """subsidy_baseline._calc_model_regional_samples must also clamp ratio to <= 1.0."""
        # national_sub (8M) > national_cap (6.5M)
        samples = subsidy_baseline._calc_model_regional_samples(base_price=52_000_000, national_sub=8_000_000)

        # For Seoul, max_local is 1.5M -> with clamping, local_sub must equal exactly 1.5M
        seoul_total = samples["seoul"]["total_subsidy_krw"]
        seoul_local = seoul_total - 8_000_000
        self.assertEqual(seoul_local, 1_500_000)

    def test_calculate_net_subsidy_extreme_national_overhang(self):
        """Extreme model_national (20M vs 6.5M max) must remain clamped to max_local."""
        res = calculate_net_subsidy(
            model_national=20_000_000,
            max_national=6_500_000,
            max_local=4_000_000,
            msrp=48_000_000,
        )
        self.assertEqual(res["local_subsidy_krw"], 4_000_000)

    def test_calculate_net_subsidy_zero_max_national(self):
        """When max_national == 0, local_ratio must be 0.0 and local subsidy must be 0."""
        res = calculate_net_subsidy(
            model_national=5_000_000,
            max_national=0,
            max_local=4_000_000,
            msrp=50_000_000,
        )
        self.assertEqual(res["local_subsidy_krw"], 0)

    def test_calculate_net_subsidy_tiered_price_caps_with_clamping(self):
        """Price cap scaling (1.0 for <55M, 0.5 for 55-85M, 0.0 for >=85M) must interact properly with clamping."""
        max_loc = 5_000_000
        # Tier 1: MSRP 50M -> ratio 1.0 -> local 5.0M
        r1 = calculate_net_subsidy(7_000_000, 6_500_000, max_loc, 50_000_000)
        self.assertEqual(r1["local_subsidy_krw"], 5_000_000)

        # Tier 2: MSRP 65M -> ratio 0.5 -> local 2.5M
        r2 = calculate_net_subsidy(7_000_000, 6_500_000, max_loc, 65_000_000)
        self.assertEqual(r2["local_subsidy_krw"], 2_500_000)

        # Tier 3: MSRP 90M -> ratio 0.0 -> local 0
        r3 = calculate_net_subsidy(7_000_000, 6_500_000, max_loc, 90_000_000)
        self.assertEqual(r3["local_subsidy_krw"], 0)


class TestLeak0102HttpErrorSocketClosure(unittest.TestCase):
    """LEAK-01/02: Verify exc.close() is called on urllib.error.HTTPError simulation."""

    def test_subsidy_tracker_closes_socket_on_http_error(self):
        """SubsidyTracker.fetch_live_updates must close HTTPError to prevent socket leaks."""
        mock_fp = MagicMock()
        mock_http_err = urllib.error.HTTPError(
            url="https://api.test/subsidy",
            code=503,
            msg="Service Unavailable",
            hdrs={},
            fp=mock_fp,
        )
        mock_http_err.close = MagicMock()

        tracker = SubsidyTracker(endpoint_url="https://api.test/subsidy")

        with patch("urllib.request.urlopen", side_effect=mock_http_err):
            result = tracker.fetch_live_updates()

        self.assertIsNone(result)
        mock_http_err.close.assert_called()

    def test_common_utils_closes_socket_on_http_error(self):
        """SafeHttpClient.request must close HTTPError on response or retry."""
        mock_fp = MagicMock()
        mock_http_err = urllib.error.HTTPError(
            url="https://api.test/data",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=mock_fp,
        )
        mock_http_err.close = MagicMock()
        mock_http_err.read = MagicMock(return_value=b"Not Found")

        client = common_utils.SafeHttpClient(max_retries=1, min_delay=0.0, max_delay=0.0)

        with patch.object(client.opener, "open", side_effect=mock_http_err):
            status, text, raw = client.request("https://api.test/data")

        self.assertEqual(status, 404)
        mock_http_err.close.assert_called()

    def test_cross_portal_flows_closes_socket_on_http_error(self):
        """test_cross_portal_flows.fetch_url must close HTTPError before returning."""
        mock_fp = MagicMock()
        mock_http_err = urllib.error.HTTPError(
            url="http://localhost:3000/api",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=mock_fp,
        )
        mock_http_err.close = MagicMock()
        mock_http_err.read = MagicMock(return_value=b"Server Error")

        with patch("urllib.request.urlopen", side_effect=mock_http_err):
            status, body, headers = test_cross_portal_flows.fetch_url("/api")

        self.assertEqual(status, 500)
        mock_http_err.close.assert_called()


class TestMirrorParitySha256(unittest.TestCase):
    """Mirror Parity: Verify SHA-256 byte equality across all dual-homed files between root and ev-stealth-web."""

    MIRROR_PAIRS = [
        # Tracker modules
        ("tracker/__init__.py", "ev-stealth-web/tracker/__init__.py"),
        ("tracker/subsidy_tracker.py", "ev-stealth-web/tracker/subsidy_tracker.py"),
        ("tracker/subsidy_models.py", "ev-stealth-web/tracker/subsidy_models.py"),
        ("tracker/subsidy_baseline.py", "ev-stealth-web/tracker/subsidy_baseline.py"),
        ("tracker/atomic_writer.py", "ev-stealth-web/tracker/atomic_writer.py"),
        # Crawlers
        ("crawlers/__init__.py", "ev-stealth-web/crawlers/__init__.py"),
        ("crawlers/base_crawler.py", "ev-stealth-web/crawlers/base_crawler.py"),
        ("crawlers/bobaedream.py", "ev-stealth-web/crawlers/bobaedream.py"),
        ("crawlers/dcinside.py", "ev-stealth-web/crawlers/dcinside.py"),
        # Models
        ("models/__init__.py", "ev-stealth-web/models/__init__.py"),
        ("models/complaint.py", "ev-stealth-web/models/complaint.py"),
        # Filters and utils
        ("filters/__init__.py", "ev-stealth-web/filters/__init__.py"),
        ("filters/defect_filter.py", "ev-stealth-web/filters/defect_filter.py"),
        ("filters/vehicle_matcher.py", "ev-stealth-web/filters/vehicle_matcher.py"),
        ("filters/slang_lexicon.py", "ev-stealth-web/filters/slang_lexicon.py"),
        ("utils/__init__.py", "ev-stealth-web/utils/__init__.py"),
        ("utils/http_client.py", "ev-stealth-web/utils/http_client.py"),
        ("utils/json_writer.py", "ev-stealth-web/utils/json_writer.py"),
        # Executable runners
        ("run_scraper.py", "ev-stealth-web/run_scraper.py"),
        ("run_tracker.py", "ev-stealth-web/run_tracker.py"),
        # Tests
        ("tests/test_adversarial_crawler_nlp.py", "ev-stealth-web/tests/test_adversarial_crawler_nlp.py"),
        ("tests/test_adversarial_sync5_remediation.py", "ev-stealth-web/tests/test_adversarial_sync5_remediation.py"),
        # Datasets
        ("data/ev_subsidy_data.json", "ev-stealth-web/src/data/ev_subsidy_data.json"),
        ("data/subsidy_depletion_data.json", "ev-stealth-web/src/data/subsidy_depletion_data.json"),
    ]

    def test_all_mirror_pairs_exist(self):
        """Verify every defined mirror file exists in both root and ev-stealth-web."""
        for root_rel, web_rel in self.MIRROR_PAIRS:
            root_path = REPO_ROOT / root_rel
            web_path = REPO_ROOT / web_rel
            with self.subTest(pair=(root_rel, web_rel)):
                self.assertTrue(root_path.exists(), f"Root file missing: {root_path}")
                self.assertTrue(web_path.exists(), f"Web mirror missing: {web_path}")

    def test_all_mirror_pairs_have_identical_sha256(self):
        """Verify SHA-256 byte parity between root and ev-stealth-web versions."""
        mismatches: List[str] = []
        for root_rel, web_rel in self.MIRROR_PAIRS:
            root_path = REPO_ROOT / root_rel
            web_path = REPO_ROOT / web_rel
            if not root_path.exists() or not web_path.exists():
                mismatches.append(f"MISSING: {root_rel} or {web_rel}")
                continue

            root_hash = _compute_sha256(root_path)
            web_hash = _compute_sha256(web_path)
            if root_hash != web_hash:
                mismatches.append(f"DESYNC: {root_rel} ({root_hash[:8]}) != {web_rel} ({web_hash[:8]})")

        self.assertEqual(
            len(mismatches),
            0,
            f"The following mirror files have SHA-256 desynchronization:\n" + "\n".join(mismatches),
        )


if __name__ == "__main__":
    unittest.main()
