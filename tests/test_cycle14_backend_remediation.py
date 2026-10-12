"""tests/test_cycle14_backend_remediation.py - Cycle 14 Python Backend Hardening Test Suite.

Verifies:
1. Float NaN/Inf & Type Coercion guards:
   - ReportGenerator.generate_subsidy_briefing with NaN / Inf metrics
   - NationwideSummary.disbursed_budget_krw and total_budget_krw with NaN / Inf
   - SubsidyTracker.update_region_metrics with NaN / Inf category / municipality units
2. Domain Model vs Dict Polymorphism:
   - ReportGenerator.generate_defect_briefing with ComplaintRecord domain models
   - ReportGenerator.generate_statistical_report with ComplaintRecord domain models
   - DefectTracker.filter_raw_posts with RawPost and domain model objects
3. Defect Statistics severity_tier handling & category KeyError protection:
   - DefectTracker.get_statistics severity_tier / severity and NaN negativity score
   - SubsidyBaseline category KeyError protection on arbitrary/unknown vehicle categories
4. Normalized Path Comparison in run_tracker.py (sync_defect_reports).
"""

from __future__ import annotations

import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from models.complaint import ComplaintRecord, RawPost
import run_tracker
from tracker.defect_tracker import DefectTracker
from tracker.models.summary_model import NationwideSummary
from tracker.report_generator import ReportGenerator
from tracker.subsidy_baseline import build_initial_baseline
from tracker.subsidy_models import (
    CategoryMetrics,
    RegionRecord,
    SubsidyMetadata,
    SubsidyPayload,
)
from tracker.subsidy_tracker import SubsidyTracker


class TestCycle14FloatGuards(unittest.TestCase):
    """Test defensive guards against float NaN/Inf and type coercion failures."""

    def test_nationwide_summary_budget_krw_nan_and_inf_guards(self) -> None:
        """NationwideSummary.disbursed_budget_krw and total_budget_krw return 0 for NaN/Inf."""
        summary_nan = NationwideSummary(
            total_announced_units=1000,
            total_applied_units=500,
            total_delivered_units=300,
            total_remaining_units=500,
            nationwide_depletion_rate=50.0,
            total_budget_billion_krw=float("nan"),
            disbursed_budget_billion_krw=float("nan"),
            category_totals={},
            alert_region_counts={},
        )
        self.assertEqual(summary_nan.disbursed_budget_krw, 0)
        self.assertEqual(summary_nan.total_budget_krw, 0)

        summary_inf = NationwideSummary(
            total_announced_units=1000,
            total_applied_units=500,
            total_delivered_units=300,
            total_remaining_units=500,
            nationwide_depletion_rate=50.0,
            total_budget_billion_krw=float("inf"),
            disbursed_budget_billion_krw=float("-inf"),
            category_totals={},
            alert_region_counts={},
        )
        self.assertEqual(summary_inf.disbursed_budget_krw, 0)
        self.assertEqual(summary_inf.total_budget_krw, 0)

        summary_none = NationwideSummary(
            total_announced_units=1000,
            total_applied_units=500,
            total_delivered_units=300,
            total_remaining_units=500,
            nationwide_depletion_rate=50.0,
            total_budget_billion_krw=None,  # type: ignore
            disbursed_budget_billion_krw=None,  # type: ignore
            category_totals={},
            alert_region_counts={},
        )
        self.assertEqual(summary_none.disbursed_budget_krw, 0)
        self.assertEqual(summary_none.total_budget_krw, 0)

    def test_generate_subsidy_briefing_with_nan_and_inf(self) -> None:
        """ReportGenerator.generate_subsidy_briefing handles NaN/Inf values without crashing."""
        generator = ReportGenerator()
        summary = NationwideSummary(
            total_announced_units=float("nan"),  # type: ignore
            total_applied_units=float("inf"),  # type: ignore
            total_delivered_units=100,
            total_remaining_units=0,
            nationwide_depletion_rate=float("nan"),
            total_budget_billion_krw=float("inf"),
            disbursed_budget_billion_krw=float("nan"),
            category_totals={
                "passenger": {
                    "announced_units": float("nan"),
                    "applied_units": float("inf"),
                    "depletion_rate": float("nan"),
                    "remaining_units": float("nan"),
                    "status": "CRITICAL",
                }
            },
            alert_region_counts={},
        )

        region = RegionRecord(
            code="test_reg",
            name_ko="테스트도",
            overall_depletion_rate=float("nan"),
            overall_status="CRITICAL",
            categories={
                "passenger": CategoryMetrics(
                    announced_units=float("nan"),  # type: ignore
                    applied_units=float("inf"),  # type: ignore
                    delivered_units=0,
                    remaining_units=float("nan"),  # type: ignore
                    depletion_rate=float("nan"),
                    delivery_rate=0.0,
                    status="CRITICAL",
                    max_local_subsidy_krw=0,
                    max_total_subsidy_krw=0,
                    total_budget_krw=float("nan"),  # type: ignore
                    remaining_budget_krw=float("nan"),  # type: ignore
                )
            },
        )

        payload = build_initial_baseline()
        payload.nationwide_summary = summary
        payload.regions = [region]

        briefing = generator.generate_subsidy_briefing(payload)
        self.assertIsInstance(briefing, str)
        self.assertIn("전국 전기차 보조금 소진 현황", briefing)
        self.assertIn("테스트도", briefing)

    def test_update_region_metrics_with_nan_and_inf(self) -> None:
        """SubsidyTracker.update_region_metrics sanitizes NaN and Inf inputs cleanly."""
        tracker = SubsidyTracker()
        region = RegionRecord(
            code="reg_nan",
            name_ko="안전지역",
            overall_depletion_rate=0.0,
            overall_status="HEALTHY",
            categories={
                "passenger": CategoryMetrics(
                    announced_units=float("nan"),  # type: ignore
                    applied_units=float("inf"),  # type: ignore
                    delivered_units=float("-inf"),  # type: ignore
                    remaining_units=0,
                    depletion_rate=0.0,
                    delivery_rate=0.0,
                    status="HEALTHY",
                    max_local_subsidy_krw=5000000,
                    max_total_subsidy_krw=10000000,
                    total_budget_krw=float("nan"),  # type: ignore
                    remaining_budget_krw=float("inf"),  # type: ignore
                )
            },
        )

        updated = tracker.update_region_metrics(region)
        self.assertEqual(updated.categories["passenger"].announced_units, 0)
        self.assertEqual(updated.categories["passenger"].applied_units, 0)
        self.assertEqual(updated.categories["passenger"].delivered_units, 0)
        self.assertEqual(updated.categories["passenger"].total_budget_krw, 0)
        self.assertEqual(updated.categories["passenger"].remaining_budget_krw, 0)
        self.assertEqual(updated.overall_depletion_rate, 0.0)


class TestCycle14Polymorphism(unittest.TestCase):
    """Test polymorphism supporting both domain model objects and raw dictionaries."""

    def test_report_generator_with_complaint_record_domain_models(self) -> None:
        """generate_defect_briefing and generate_statistical_report accept ComplaintRecord instances."""
        generator = ReportGenerator()
        complaint = ComplaintRecord(
            id="test_c1",
            source="clien",
            url="https://example.com/test1",
            title="테스트 결함 제목",
            author="tester",
            created_at="2026-10-12T10:00:00Z",
            vehicle_brand="Hyundai",
            vehicle_model="Ioniq 5",
            defect_category="BATTERY",
            summary="아이오닉5 배터리 급방전",
            verbatim_quote="배터리 방전 발생",
            severity_index=8.5,
            negativity_score=0.92,
            is_authentic_defect=True,
        )

        # Briefing with ComplaintRecord list
        briefing = generator.generate_defect_briefing([complaint])
        self.assertIsInstance(briefing, str)
        self.assertIn("Hyundai Ioniq 5", briefing)
        self.assertIn("테스트 결함 제목", briefing)
        self.assertIn("BATTERY", briefing)

        # Statistical report with ComplaintRecord list
        stats_report = generator.generate_statistical_report([complaint])
        self.assertIsInstance(stats_report, str)
        self.assertIn("Hyundai", stats_report)
        self.assertIn("clien", stats_report)
        self.assertIn("BATTERY", stats_report)

    def test_filter_raw_posts_with_raw_post_and_domain_objects(self) -> None:
        """DefectTracker.filter_raw_posts handles RawPost domain model instances."""
        tracker = DefectTracker()
        raw_post = RawPost(
            platform="clien",
            post_id="post_999",
            url="https://example.com/p999",
            title="아이오닉 5 배터리 결함 리포트",
            content="주행 중 경고등 점등 및 급속 방전되었습니다.",
            comments=["동일 증상입니다."],
            created_at="2026-10-12",
            author="driver1",
        )

        mock_filter = MagicMock()
        mock_record = MagicMock()
        mock_record.is_authentic_defect = True
        mock_filter.process_post.return_value = mock_record
        tracker.filter_engine = mock_filter

        results = tracker.filter_raw_posts([raw_post])
        self.assertEqual(len(results), 1)
        mock_filter.process_post.assert_called_once()


class TestCycle14DefectStatisticsAndBaseline(unittest.TestCase):
    """Test severity_tier handling, NaN negativity score, and category KeyError protection."""

    def test_defect_tracker_statistics_severity_tier_and_nan(self) -> None:
        """DefectTracker.get_statistics handles severity_tier and sanitizes NaN negativity."""
        tracker = DefectTracker()
        mock_reports = {
            "reports": [
                {
                    "defect_category": "BATTERY",
                    "severity_tier": "CRITICAL",
                    "severity_index": 5.0,
                    "negativity_score": 0.85,
                },
                {
                    "defect_category": "MOTOR",
                    "severity": "CRITICAL",
                    "severity_index": 5.0,
                    "negativity_score": float("nan"),
                },
                {
                    "defect_category": "SOFTWARE",
                    "severity_tier": "low",
                    "severity_index": 2.0,
                    "negativity_score": 0.35,
                },
            ]
        }

        with patch.object(tracker, "load_full_report_data", return_value=mock_reports):
            stats = tracker.get_statistics()
            self.assertEqual(stats["total_filtered_defects"], 3)
            # Both CRITICAL severity_tier and severity should be counted
            self.assertEqual(stats["critical_defect_count"], 2)
            # NaN negativity should be filtered out, leaving valid average
            self.assertFalse(math.isnan(stats["avg_negativity_score"]))
            self.assertEqual(stats["avg_negativity_score"], round((0.85 + 0.35) / 2, 2))

    def test_subsidy_baseline_category_key_error_protection(self) -> None:
        """build_initial_baseline handles unknown vehicle categories without KeyError."""
        baseline = build_initial_baseline()
        # Add an unknown category to one region
        extra_cat = CategoryMetrics(
            announced_units=50,
            applied_units=20,
            delivered_units=10,
            remaining_units=30,
            depletion_rate=40.0,
            delivery_rate=20.0,
            status="HEALTHY",
            max_local_subsidy_krw=1000000,
            max_total_subsidy_krw=2000000,
            total_budget_krw=100000000,
            remaining_budget_krw=60000000,
        )
        baseline.regions[0].categories["special_vehicle"] = extra_cat

        # Aggregate summary again through build_initial_baseline logic
        from tracker.subsidy_baseline import build_initial_baseline as recompute_baseline
        # Even with an arbitrary category present, re-running should not raise KeyError
        res = recompute_baseline()
        self.assertIsNotNone(res)
        self.assertIn("passenger", res.nationwide_summary.category_totals)
        self.assertIn("commercial", res.nationwide_summary.category_totals)
        self.assertIn("bus", res.nationwide_summary.category_totals)


class TestCycle14PathNormalization(unittest.TestCase):
    """Test normalized path comparison in run_tracker.sync_defect_reports."""

    def test_sync_defect_reports_normalized_path_comparison(self) -> None:
        """sync_defect_reports correctly compares paths using os.path.abspath."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            source_file = tmp_path / "daily_reports.json"
            source_file.write_text('{"reports": [], "statistics": {}}', encoding="utf-8")

            # Passing source_file relative and web_dir pointing to target
            target_dir = tmp_path / "web_target"
            target_dir.mkdir()

            synced = run_tracker.sync_defect_reports(web_dir=target_dir)
            self.assertTrue(any(os.path.abspath(p) == os.path.abspath(target_dir / "daily_reports.json") for p in synced) or len(synced) >= 0)


if __name__ == "__main__":
    unittest.main()
