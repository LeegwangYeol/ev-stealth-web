"""
tests/test_cycle14_hardening.py - Comprehensive Cycle 14 Hardening, Boundary,
Polymorphism, Accessibility, Header Security, and Triple Dataset Parity Test Suite.

Authoritative Reference:
- ORIGINAL_REQUEST.md
- DISPATCH.md (Cycle 14 Hardening Test Suite Specification)
- Wave 1 Explorer Handoff Reports:
  - sync14_explorer_backend_w1/handoff.md
  - sync14_explorer_frontend_w1/handoff.md
  - sync14_explorer_a11y_w1/handoff.md
  - sync14_explorer_perf_w1/handoff.md
  - sync14_explorer_parity_w1/handoff.md
- COLLABORATION.md

Coverage:
1. Backend Float NaN/Inf & Type Coercion Guards:
   - ReportGenerator.generate_subsidy_briefing defensive handling against NaN/Inf, None, and overflow.
   - NationwideSummary.disbursed_budget_krw and total_budget_krw NaN/Inf/None protection.
   - NationwideSummary re-export from tracker/models/summary_model.py.
   - SubsidyTracker.update_region_metrics safe integer coercion on NaN/Inf/None category units and budgets.

2. Domain Model vs Dict Polymorphism:
   - ReportGenerator.generate_defect_briefing with ComplaintRecord instances, dicts, and mixed lists.
   - ReportGenerator.generate_statistical_report with ComplaintRecord instances and dicts.
   - DefectTracker.filter_raw_posts with RawPost instances, dicts, and mixed inputs.

3. Defect Tracker Statistics, NaN Protection & Subsidy Baseline Extensibility:
   - DefectTracker.get_statistics severity_tier == 'CRITICAL' recognition alongside severity key.
   - DefectTracker.get_statistics avg_negativity_score NaN/Inf sanitization.
   - SubsidyBaseline dynamic category tracking preventing KeyError on novel vehicle categories.

4. Path Normalization:
   - run_tracker.py sync_defect_reports normalized path comparison using os.path.abspath.

5. Frontend Fixes, Accessibility, and Performance Invariants:
   - SubsidyTrackerClient.tsx safeAnnounced display safeguard (0대 displayed when quota is 0).
   - DepreciationCalculatorClient.tsx model search zero-data empty state and dynamic EV tax computation.
   - RecallPortalClient.tsx zero-data empty states (Battery Profiles & Recalls Catalog) and unmapped model fallback.
   - layout.tsx SiteFooter semantic landmark (role="contentinfo", aria-label="법적 고지 및 데이터 출처").
   - DepreciationCalculatorClient.tsx and AdminDashboardClient.tsx aria-live polite regions.
   - next.config.mjs Content-Security-Policy header and /data/:path* s-maxage=3600 edge caching.
   - layout.tsx Korean font fallback metrics in geistSans.

6. Triple Dataset Parity & POSIX Permissions:
   - 100% cryptographic SHA-256 bitwise parity across data/, ev-stealth-web/src/data/, and ev-stealth-web/public/data/.
   - 0o644 POSIX permission enforcement across all 12 dataset files.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from typing import Any, Dict, List, Optional, Union


# Adaptive repository and web root resolution
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


PROJECT_ROOT = _find_repo_root()
WEB_ROOT = PROJECT_ROOT / "ev-stealth-web"
SRC_DIR = WEB_ROOT / "src"
LIB_DIR = SRC_DIR / "lib"
APP_DIR = SRC_DIR / "app"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
else:
    sys.path.remove(str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT))

if str(WEB_ROOT) not in sys.path:
    sys.path.append(str(WEB_ROOT))

from filters.defect_filter import ContextualDefectFilter
from models.complaint import ComplaintRecord, RawPost
from tracker.atomic_writer import atomic_write_json
from tracker.defect_tracker import DefectTracker
from tracker.models.summary_model import NationwideSummary as ModularNationwideSummary
from tracker.report_generator import ReportGenerator, _get_field, _metric_val, _safe_float_val, _safe_int_val
from tracker.subsidy_baseline import (
    _calc_cat,
    build_baseline_regions,
    build_initial_baseline,
)
from tracker.subsidy_models import (
    CategoryMetrics,
    MunicipalityMetrics,
    NationwideSummary,
    RegionRecord,
    SubsidyMetadata,
    SubsidyPayload,
)
from tracker.subsidy_tracker import SubsidyTracker


# ============================================================================
# 1. Backend Float NaN/Inf & Type Coercion Guards
# ============================================================================
class TestCycle14BackendFloatAndCoercionGuards(unittest.TestCase):
    """Verifies that backend numeric conversion functions and models defensively
    guard against NaN, Inf, None, strings, and overflow.
    """

    def setUp(self) -> None:
        self.generator = ReportGenerator()
        self.tracker = SubsidyTracker()

    def test_safe_int_val_and_safe_float_val_boundaries(self) -> None:
        """_safe_int_val and _safe_float_val must handle all invalid float tokens cleanly."""
        self.assertEqual(_safe_int_val(None, default=0), 0)
        self.assertEqual(_safe_int_val(float("nan"), default=0), 0)
        self.assertEqual(_safe_int_val(float("inf"), default=0), 0)
        self.assertEqual(_safe_int_val(float("-inf"), default=0), 0)
        self.assertEqual(_safe_int_val("not_a_number", default=42), 42)
        self.assertEqual(_safe_int_val(123.45), 123)
        self.assertEqual(_safe_int_val("500"), 500)

        self.assertEqual(_safe_float_val(None, default=0.0), 0.0)
        self.assertEqual(_safe_float_val(float("nan"), default=0.0), 0.0)
        self.assertEqual(_safe_float_val(float("inf"), default=0.0), 0.0)
        self.assertEqual(_safe_float_val(float("-inf"), default=0.0), 0.0)
        self.assertEqual(_safe_float_val("invalid", default=3.14), 3.14)
        self.assertEqual(_safe_float_val(98.6), 98.6)
        self.assertEqual(_safe_float_val("89.4"), 89.4)

    def test_generate_subsidy_briefing_nan_inf_budget_safety(self) -> None:
        """generate_subsidy_briefing must not crash when budget or quota totals are NaN, Inf, or None."""
        summary = NationwideSummary(
            total_announced_units=1000,
            total_applied_units=850,
            total_delivered_units=800,
            total_remaining_units=150,
            nationwide_depletion_rate=float("nan"),
            total_budget_billion_krw=float("nan"),
            disbursed_budget_billion_krw=float("inf"),
            category_totals={
                "passenger": CategoryMetrics(
                    announced_units=float("nan"),  # type: ignore[arg-type]
                    applied_units=float("inf"),  # type: ignore[arg-type]
                    delivered_units=None,  # type: ignore[arg-type]
                    remaining_units=float("nan"),  # type: ignore[arg-type]
                    depletion_rate=float("nan"),
                    delivery_rate=0.0,
                    status="WARNING",
                    max_local_subsidy_krw=0,
                    max_total_subsidy_krw=0,
                    total_budget_krw=0,
                    remaining_budget_krw=0,
                )
            },
            alert_region_counts={"critical": 0, "warning": 0, "available": 1},
        )
        meta = SubsidyMetadata(
            version="1.0.0",
            generated_at="2026-10-12T19:00:00Z",
            policy_year=2026,
            data_sources=["환경부 무공해차 통합누리집"],
            total_regions_tracked=1,
            total_municipalities_tracked=0,
        )
        reg = RegionRecord.from_dict({
            "region_id": "KR-11",
            "name_ko": "서울특별시",
            "name_en": "Seoul",
            "iso_code": "KR-11",
            "overall_status": "WARNING",
            "overall_depletion_rate": float("nan"),
            "categories": {},
            "municipalities": [],
        })
        payload = SubsidyPayload(
            metadata=meta,
            alert_thresholds={},
            nationwide_summary=summary,
            regions=[reg],
            popular_models_matrix=[],
            historical_depletion_trajectory=[],
        )

        # Must execute cleanly without ValueError or OverflowError
        briefing = self.generator.generate_subsidy_briefing(payload)
        self.assertIsInstance(briefing, str)
        self.assertIn("전국 전기차 보조금 소진 현황 일일 종합 브리핑", briefing)
        self.assertIn("서울특별시", briefing)

    def test_nationwide_summary_krw_properties_nan_inf_guards(self) -> None:
        """NationwideSummary.disbursed_budget_krw and total_budget_krw must return 0 on NaN or Inf."""
        summary_nan = NationwideSummary(
            total_announced_units=100,
            total_applied_units=50,
            total_delivered_units=30,
            total_remaining_units=50,
            nationwide_depletion_rate=50.0,
            total_budget_billion_krw=float("nan"),
            disbursed_budget_billion_krw=float("nan"),
            category_totals={},
            alert_region_counts={},
        )
        self.assertEqual(summary_nan.disbursed_budget_krw, 0)
        self.assertEqual(summary_nan.total_budget_krw, 0)

        summary_inf = NationwideSummary(
            total_announced_units=100,
            total_applied_units=50,
            total_delivered_units=30,
            total_remaining_units=50,
            nationwide_depletion_rate=50.0,
            total_budget_billion_krw=float("inf"),
            disbursed_budget_billion_krw=float("-inf"),
            category_totals={},
            alert_region_counts={},
        )
        self.assertEqual(summary_inf.disbursed_budget_krw, 0)
        self.assertEqual(summary_inf.total_budget_krw, 0)

        summary_none = NationwideSummary(
            total_announced_units=100,
            total_applied_units=50,
            total_delivered_units=30,
            total_remaining_units=50,
            nationwide_depletion_rate=50.0,
            total_budget_billion_krw=None,  # type: ignore[arg-type]
            disbursed_budget_billion_krw=None,  # type: ignore[arg-type]
            category_totals={},
            alert_region_counts={},
        )
        self.assertEqual(summary_none.disbursed_budget_krw, 0)
        self.assertEqual(summary_none.total_budget_krw, 0)

        # Valid numeric calculation
        summary_valid = NationwideSummary(
            total_announced_units=100,
            total_applied_units=50,
            total_delivered_units=30,
            total_remaining_units=50,
            nationwide_depletion_rate=50.0,
            total_budget_billion_krw=2105.1,
            disbursed_budget_billion_krw=1893.4,
            category_totals={},
            alert_region_counts={},
        )
        self.assertEqual(summary_valid.disbursed_budget_krw, 1_893_400_000_000)
        self.assertEqual(summary_valid.total_budget_krw, 2_105_100_000_000)

    def test_modular_nationwide_summary_import(self) -> None:
        """NationwideSummary re-exported from tracker/models/summary_model.py must be identical."""
        self.assertIs(ModularNationwideSummary, NationwideSummary)

    def test_subsidy_tracker_update_region_metrics_nan_inf_guards(self) -> None:
        """SubsidyTracker.update_region_metrics must coerce category units and budgets safely on NaN/Inf."""
        cat_nan = CategoryMetrics(
            announced_units=float("nan"),  # type: ignore[arg-type]
            applied_units=float("inf"),  # type: ignore[arg-type]
            delivered_units=float("-inf"),  # type: ignore[arg-type]
            remaining_units=0,
            depletion_rate=0.0,
            delivery_rate=0.0,
            status="AVAILABLE",
            max_local_subsidy_krw=5_000_000,
            max_total_subsidy_krw=11_500_000,
            total_budget_krw=float("nan"),  # type: ignore[arg-type]
            remaining_budget_krw=float("inf"),  # type: ignore[arg-type]
        )
        muni_nan = MunicipalityMetrics(
            name_ko="강남구",
            announced_units=float("nan"),  # type: ignore[arg-type]
            applied_units=float("inf"),  # type: ignore[arg-type]
            remaining_units=0,
            depletion_rate=0.0,
            status="AVAILABLE",
            local_subsidy_krw=5_000_000,
        )
        reg = RegionRecord(
            region_id="KR-11",
            name_ko="서울특별시",
            name_en="Seoul",
            iso_code="KR-11",
            overall_status="AVAILABLE",
            overall_depletion_rate=0.0,
            categories={"passenger": cat_nan},
            municipalities=[muni_nan],
        )

        updated_reg = self.tracker.update_region_metrics(reg)
        p_cat = updated_reg.categories["passenger"]

        self.assertIsInstance(p_cat.announced_units, int)
        self.assertEqual(p_cat.announced_units, 0)
        self.assertIsInstance(p_cat.applied_units, int)
        self.assertEqual(p_cat.applied_units, 0)
        self.assertIsInstance(p_cat.delivered_units, int)
        self.assertEqual(p_cat.delivered_units, 0)
        self.assertIsInstance(p_cat.total_budget_krw, int)
        self.assertEqual(p_cat.total_budget_krw, 0)

        # Municipality checks
        m0 = updated_reg.municipalities[0]
        self.assertIsInstance(m0.announced_units, int)
        self.assertEqual(m0.announced_units, 0)
        self.assertIsInstance(m0.applied_units, int)
        self.assertEqual(m0.applied_units, 0)


# ============================================================================
# 2. Domain Model vs Dict Polymorphism Tests
# ============================================================================
class TestCycle14DomainModelPolymorphism(unittest.TestCase):
    """Verifies that ReportGenerator and DefectTracker seamlessly support both
    strongly-typed domain dataclasses (ComplaintRecord, RawPost) and raw dictionaries.
    """

    def setUp(self) -> None:
        self.generator = ReportGenerator()
        self.defect_tracker = DefectTracker(filter_engine=ContextualDefectFilter())

    def test_generate_defect_briefing_complaint_record_polymorphism(self) -> None:
        """generate_defect_briefing must process ComplaintRecord instances without AttributeError."""
        record_domain = ComplaintRecord(
            id="dc_20261012_001",
            source="dcinside",
            url="https://gall.dcinside.com/mgallery/board/view/?id=car_new1&no=1284920",
            title="전기차 ICCU 터져서 고속도로에서 멈춤",
            author="car_user",
            created_at="2026-10-12T18:00:00Z",
            vehicle_brand="현대",
            vehicle_model="아이오닉 5",
            defect_category="BATTERY_CHARGING",
            summary="고속도로 주행 중 ICCU 경고등 및 동력 상실",
            verbatim_quote="갑자기 퍽 소리 나더니 배터리 경고등 뜨고 악셀 먹통됨",
            severity_index=9.5,
            is_authentic_defect=True,
        )
        record_dict = {
            "id": "bobae_20261012_002",
            "source": "bobaedream",
            "url": "https://www.bobaedream.co.kr/view?code=national&No=2416882",
            "title": "EV6 하부 배터리케이스 파손",
            "vehicle_brand": "기아",
            "vehicle_model": "EV6",
            "defect_category": "BATTERY_CHARGING",
            "severity_index": 8.0,
            "severity": "CRITICAL",
            "is_authentic_defect": True,
        }

        # 1. Pure domain model list
        briefing_obj = self.generator.generate_defect_briefing([record_domain])
        self.assertIn("아이오닉 5", briefing_obj)
        self.assertIn("9.5", briefing_obj)
        self.assertIn("BATTERY_CHARGING", briefing_obj)

        # 2. Mixed list of domain object and dict
        briefing_mixed = self.generator.generate_defect_briefing([record_domain, record_dict])
        self.assertIn("총 수집/분류 결함 건수**: 2건", briefing_mixed)
        self.assertIn("아이오닉 5", briefing_mixed)
        self.assertIn("EV6", briefing_mixed)

    def test_generate_statistical_report_complaint_record_polymorphism(self) -> None:
        """generate_statistical_report must process ComplaintRecord instances without AttributeError."""
        rec1 = ComplaintRecord(
            id="rec_1",
            source="dcinside",
            url="http://example.com/1",
            title="MCU 블랙아웃",
            author="user1",
            created_at="2026-10-12T18:00:00Z",
            vehicle_brand="테슬라",
            vehicle_model="Model Y",
            defect_category="SOFTWARE_ELECTRONICS",
            summary="OTA 후 블랙아웃",
            verbatim_quote="화면 벽돌",
            severity_index=8.8,
            is_authentic_defect=True,
        )
        rec2 = ComplaintRecord(
            id="rec_2",
            source="bobaedream",
            url="http://example.com/2",
            title="토션빔 피쉬테일",
            author="user2",
            created_at="2026-10-12T18:05:00Z",
            vehicle_brand="기아",
            vehicle_model="EV3",
            defect_category="DRIVING_POWERTRAIN",
            summary="빗길 접지력 상실",
            verbatim_quote="가드레일 박을 뻔",
            severity_index=7.5,
            is_authentic_defect=True,
        )

        stat_report = self.generator.generate_statistical_report([rec1, rec2])
        self.assertIn("총 2건", stat_report)
        self.assertIn("테슬라", stat_report)
        self.assertIn("기아", stat_report)
        self.assertIn("SOFTWARE_ELECTRONICS", stat_report)
        self.assertIn("DRIVING_POWERTRAIN", stat_report)

    def test_filter_raw_posts_raw_post_instances(self) -> None:
        """filter_raw_posts must process RawPost instances directly without failing."""
        raw_post = RawPost(
            platform="dcinside",
            post_id="post_999",
            url="https://gall.dcinside.com/mgallery/board/view/?id=car_new1&no=999",
            title="고속도로 주행 중 배터리 전원 차단 ICCU 동력상실",
            content="어제 영동고속도로 달리는데 퍽 소리와 함께 경고등 뜨고 시동 꺼짐. 진짜 견인차 부르고 죽을 뻔했다.",
            comments=[],
            created_at="2026-10-12T19:00:00Z",
            author="ev_driver",
        )
        raw_dict = {
            "platform": "bobaedream",
            "post_id": "post_888",
            "url": "https://www.bobaedream.co.kr/view?code=national&No=888",
            "title": "현대 아이오닉5 배터리 충전 불가 및 ICCU 동력상실",
            "content": "고속도로에서 배터리 경고등 켜지더니 퍽 소리 나고 시동 꺼짐. ICCU 터져서 긴급 견인 입고함.",
            "comments": [],
            "created_at": "2026-10-12T19:05:00Z",
            "author": "ioniq_owner",
        }

        # Passing RawPost instance
        results_post = self.defect_tracker.filter_raw_posts([raw_post])
        self.assertEqual(len(results_post), 1)
        self.assertTrue(getattr(results_post[0], "is_authentic_defect", False))

        # Passing mixed list
        results_mixed = self.defect_tracker.filter_raw_posts([raw_post, raw_dict])
        self.assertEqual(len(results_mixed), 2)
        for r in results_mixed:
            self.assertTrue(getattr(r, "is_authentic_defect", False))


# ============================================================================
# 3. Defect Statistics & Baseline Extensibility Tests
# ============================================================================
class TestCycle14DefectStatisticsAndBaseline(unittest.TestCase):
    """Verifies that DefectTracker.get_statistics respects severity_tier and sanitizes
    NaN negativity scores, and that subsidy_baseline supports extensible categories.
    """

    def setUp(self) -> None:
        self.defect_tracker = DefectTracker()

    def test_defect_tracker_get_statistics_severity_tier_support(self) -> None:
        """get_statistics must count critical defects when severity_tier == 'CRITICAL'."""
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "reports": [
                        {
                            "id": "tier_crit_1",
                            "severity_tier": "CRITICAL",
                            "defect_category": "BATTERY_CHARGING",
                            "negativity_score": 0.95,
                        },
                        {
                            "id": "sev_crit_2",
                            "severity": "CRITICAL",
                            "defect_category": "BATTERY_CHARGING",
                            "negativity_score": 0.92,
                        },
                        {
                            "id": "dsi_crit_3",
                            "severity": "MEDIUM",
                            "severity_index": 7.8,
                            "defect_category": "SOFTWARE_ELECTRONICS",
                            "negativity_score": 0.85,
                        },
                        {
                            "id": "norm_low_4",
                            "severity_tier": "LOW",
                            "severity_index": 3.0,
                            "defect_category": "BODY",
                            "negativity_score": 0.20,
                        },
                    ]
                },
                f,
            )
            temp_path = f.name

        try:
            stats = self.defect_tracker.get_statistics(file_path=temp_path)
            self.assertEqual(stats["total_filtered_defects"], 4)
            # Exactly 3 critical defects (tier_crit_1, sev_crit_2, dsi_crit_3)
            self.assertEqual(stats["critical_defect_count"], 3)
            self.assertEqual(stats["category_distribution"]["BATTERY_CHARGING"], 2)
            self.assertEqual(stats["category_distribution"]["SOFTWARE_ELECTRONICS"], 1)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_defect_tracker_get_statistics_nan_negativity_sanitization(self) -> None:
        """get_statistics must filter out NaN and Inf negativity scores, returning a finite average."""
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "reports": [
                        {"id": "n1", "negativity_score": float("nan"), "defect_category": "CAT1"},
                        {"id": "n2", "negativity_score": "nan", "defect_category": "CAT1"},
                        {"id": "n3", "negativity_score": float("inf"), "defect_category": "CAT1"},
                        {"id": "n4", "negativity_score": 0.80, "defect_category": "CAT1"},
                        {"id": "n5", "negativity_score": 0.60, "defect_category": "CAT1"},
                    ]
                },
                f,
            )
            temp_path = f.name

        try:
            stats = self.defect_tracker.get_statistics(file_path=temp_path)
            avg_neg = stats["avg_negativity_score"]
            self.assertIsInstance(avg_neg, float)
            self.assertFalse(math.isnan(avg_neg), "avg_negativity_score must not be NaN")
            self.assertFalse(math.isinf(avg_neg), "avg_negativity_score must not be Inf")
            # Average of 0.80 and 0.60 = 0.70
            self.assertEqual(avg_neg, 0.70)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_subsidy_baseline_extensible_vehicle_categories(self) -> None:
        """build_initial_baseline must handle novel/custom vehicle categories without KeyError."""
        import tracker.subsidy_baseline

        regs = build_baseline_regions()
        # Add a custom category to the first region
        regs[0].categories["two_wheeler"] = _calc_cat(50, 30, 20, 100)
        regs[0].categories["electric_truck"] = _calc_cat(20, 15, 10, 500)

        orig_fn = tracker.subsidy_baseline.build_baseline_regions
        try:
            tracker.subsidy_baseline.build_baseline_regions = lambda: regs
            payload = build_initial_baseline()
            cat_totals = payload.nationwide_summary.category_totals
            self.assertIn("two_wheeler", cat_totals)
            self.assertIn("electric_truck", cat_totals)
            # category_totals dictionary entries contain announced_units
            two_wheeler_data = cat_totals["two_wheeler"]
            ann_units = _metric_val(two_wheeler_data, "announced_units", 0)
            self.assertEqual(ann_units, 50)
        finally:
            tracker.subsidy_baseline.build_baseline_regions = orig_fn


# ============================================================================
# 4. Path Normalization Tests
# ============================================================================
class TestCycle14PathNormalization(unittest.TestCase):
    """Verifies that run_tracker.py sync_defect_reports performs normalized path
    comparisons using os.path.abspath to prevent redundant self-copies.
    """

    def test_run_tracker_target_paths_filter_normalizes_paths(self) -> None:
        """target_paths must filter out paths referencing the source file via relative or redundant segments."""
        source_path = PROJECT_ROOT / "data" / "daily_reports.json"
        known_paths = [
            PROJECT_ROOT / "data" / "daily_reports.json",
            PROJECT_ROOT / "data" / "." / "daily_reports.json",
            WEB_ROOT / "src" / "data" / "daily_reports.json",
            WEB_ROOT / "public" / "data" / "daily_reports.json",
        ]

        target_paths = [
            p
            for p in known_paths
            if os.path.abspath(p) != os.path.abspath(source_path) and p.parent.exists()
        ]

        # The redundant representation data/./daily_reports.json must be excluded, leaving the 2 web paths
        self.assertEqual(len(target_paths), 2)
        target_abs = [os.path.abspath(p) for p in target_paths]
        source_abs = os.path.abspath(source_path)
        self.assertNotIn(source_abs, target_abs)


# ============================================================================
# 5. Frontend Fixes, Accessibility, and Performance Invariants
# ============================================================================
class TestCycle14FrontendSafeguardsAndA11y(unittest.TestCase):
    """Verifies frontend hardening: safeAnnounced display guard, empty states,
    SiteFooter landmark, aria-live polite regions, and next.config.mjs headers.
    """

    def test_subsidy_tracker_client_safe_announced_display_guard(self) -> None:
        """SubsidyTrackerClient.tsx must display 0대 (not 1대) when announced quota is 0."""
        subsidy_client_file = APP_DIR / "subsidy-tracker" / "SubsidyTrackerClient.tsx"
        self.assertTrue(subsidy_client_file.exists())
        content = subsidy_client_file.read_text(encoding="utf-8")

        # Must define an explicit display variable for announced units that retains 0
        self.assertIn("announcedUnits", content)
        # Must render announcedUnits.toLocaleString() in user-facing text, not safeAnnounced
        self.assertIn("{announcedUnits.toLocaleString()}대", content)
        self.assertNotIn("{safeAnnounced.toLocaleString()}대", content)

    def test_depreciation_calculator_empty_state_and_dynamic_tax(self) -> None:
        """DepreciationCalculatorClient.tsx must render an empty state on 0 search matches and compute EV tax dynamically."""
        dep_client_file = APP_DIR / "depreciation-calculator" / "DepreciationCalculatorClient.tsx"
        self.assertTrue(dep_client_file.exists())
        content = dep_client_file.read_text(encoding="utf-8")

        # 1. Zero-data empty state in model grid
        self.assertIn("filteredModels.length === 0", content)
        self.assertIn("일치하는 전기차 모델이 없습니다", content)

        # 2. Dynamic automobile tax rendering in TCO comparison table
        self.assertIn("row.evAutomobileTaxKrw", content)
        self.assertNotIn('<td className="py-2 px-3">13만원</td>', content)

    def test_recall_portal_empty_states_and_model_fallback(self) -> None:
        """RecallPortalClient.tsx must have empty states for Battery Directory & Recalls Catalog and handle unmapped models."""
        recall_client_file = APP_DIR / "recall-portal" / "RecallPortalClient.tsx"
        self.assertTrue(recall_client_file.exists())
        content = recall_client_file.read_text(encoding="utf-8")

        # 1. Battery profiles empty state
        self.assertIn("filteredBatteryProfiles.length === 0", content)
        self.assertIn("조건에 일치하는 배터리 제조사 정보가 없습니다", content)

        # 2. Recalls catalog empty state
        self.assertIn("filteredRecalls.length === 0", content)
        self.assertIn("일치하는 공시 리콜 및 무상수리 내역이 없습니다", content)

        # 3. Model fallback in VIN Mode A
        self.assertIn("checkResult.decodedModel?.trim() ? checkResult.decodedModel : '미확인 모델'", content)

    def test_layout_site_footer_landmark_integration(self) -> None:
        """layout.tsx must render SiteFooter and SiteFooter.tsx must declare role='contentinfo' and aria-label."""
        layout_file = APP_DIR / "layout.tsx"
        self.assertTrue(layout_file.exists())
        layout_content = layout_file.read_text(encoding="utf-8")

        # SiteFooter imported and rendered in layout.tsx
        self.assertIn('import SiteFooter from "@/components/layout/SiteFooter";', layout_content)
        self.assertIn("<SiteFooter />", layout_content)
        self.assertNotIn('<footer className="bg-gray-200 text-center p-6 text-sm text-gray-600">', layout_content)

        # SiteFooter.tsx component possesses landmark attributes
        site_footer_file = SRC_DIR / "components" / "layout" / "SiteFooter.tsx"
        self.assertTrue(site_footer_file.exists())
        footer_content = site_footer_file.read_text(encoding="utf-8")
        self.assertIn('role="contentinfo"', footer_content)
        self.assertIn('aria-label="법적 고지 및 데이터 출처"', footer_content)

    def test_aria_live_polite_regions_on_interactive_dashboards(self) -> None:
        """DepreciationCalculatorClient and AdminDashboardClient must have aria-live='polite' regions."""
        # 1. Depreciation Calculator Client
        dep_content = (APP_DIR / "depreciation-calculator" / "DepreciationCalculatorClient.tsx").read_text(encoding="utf-8")
        self.assertIn('aria-live="polite"', dep_content)
        self.assertIn('aria-atomic="true"', dep_content)

        # 2. Admin Dashboard Client
        admin_content = (APP_DIR / "secret-admin-reports" / "AdminDashboardClient.tsx").read_text(encoding="utf-8")
        self.assertIn('aria-live="polite"', admin_content)
        self.assertIn('aria-atomic="true"', admin_content)

    def test_next_config_csp_and_cache_control_headers(self) -> None:
        """next.config.mjs must declare Content-Security-Policy and s-maxage=3600 edge caching."""
        config_file = WEB_ROOT / "next.config.mjs"
        self.assertTrue(config_file.exists())
        config_content = config_file.read_text(encoding="utf-8")

        # Content-Security-Policy header
        self.assertIn("Content-Security-Policy", config_content)
        self.assertIn("default-src 'self'", config_content)

        # Edge caching s-maxage=3600 on /data/:path*
        self.assertIn("/data/:path*", config_content)
        self.assertIn("s-maxage=3600", config_content)

    def test_layout_korean_font_fallback_metrics(self) -> None:
        """layout.tsx must specify modern Korean system fallback fonts in geistSans."""
        layout_content = (APP_DIR / "layout.tsx").read_text(encoding="utf-8")
        self.assertIn("Pretendard", layout_content)
        self.assertIn("-apple-system", layout_content)
        self.assertIn("BlinkMacSystemFont", layout_content)


# ============================================================================
# 6. Triple Dataset Parity & POSIX Permissions
# ============================================================================
class TestCycle14TripleDatasetParityAndPermissions(unittest.TestCase):
    """Verifies 100% cryptographic SHA-256 bitwise parity and 0o644 permissions
    across root data/, web src/data/, and web public/data/.
    """

    CORE_DATASETS = [
        "ev_subsidy_data.json",
        "subsidy_depletion_data.json",
        "daily_reports.json",
        "models_subsidy_matrix.json",
    ]

    def test_triple_dataset_sha256_cryptographic_parity(self) -> None:
        """All 4 core datasets must be bitwise identical across all 3 mirror directories."""
        dirs = [
            PROJECT_ROOT / "data",
            WEB_ROOT / "src" / "data",
            WEB_ROOT / "public" / "data",
        ]

        for dataset_name in self.CORE_DATASETS:
            hashes: List[str] = []
            sizes: List[int] = []

            for d in dirs:
                p = d / dataset_name
                self.assertTrue(p.exists(), f"File {p} must exist")
                data_bytes = p.read_bytes()
                sha = hashlib.sha256(data_bytes).hexdigest()
                hashes.append(sha)
                sizes.append(len(data_bytes))

            # All 3 hashes must match identically
            self.assertEqual(
                len(set(hashes)),
                1,
                f"Hash mismatch across mirrors for {dataset_name}: {dict(zip([str(d) for d in dirs], hashes))}",
            )
            self.assertEqual(
                len(set(sizes)),
                1,
                f"Size mismatch across mirrors for {dataset_name}: {dict(zip([str(d) for d in dirs], sizes))}",
            )

    def test_dataset_posix_permissions_0o644(self) -> None:
        """All 12 dataset files across 3 mirror directories must have standard 0o644 permissions."""
        dirs = [
            PROJECT_ROOT / "data",
            WEB_ROOT / "src" / "data",
            WEB_ROOT / "public" / "data",
        ]

        for dataset_name in self.CORE_DATASETS:
            for d in dirs:
                p = d / dataset_name
                mode = oct(stat.S_IMODE(p.stat().st_mode))
                self.assertEqual(
                    mode,
                    "0o644",
                    f"Permissions for {p} must be 0o644 (-rw-r--r--), got {mode}",
                )


if __name__ == "__main__":
    unittest.main()
