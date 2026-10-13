"""tests/test_adversarial_edge_cases_challenger.py - Empirical Edge Case Verification Suite.

Authoritative Mission Verification:
1. SubsidyTracker.compute_nationwide_summary():
   - Extreme values: 10^12 units, 10^18 KRW budget, zero units, negative units clamped to 0.
   - float("nan"), float("inf"), float("-inf") in CategoryMetrics and plain dictionary metrics.
   - Malformed dictionary metrics (plain dicts, missing keys, string numbers, None, empty categories).
   - Alert severity counting resilience across case differences and unknown status strings.
2. ComplaintRecord date parsing:
   - Dot-separated ('YYYY.MM.DD' and 'YYYY.MM.DD HH:MM:SS').
   - Slash-separated ('YYYY/MM/DD' and 'YYYY/MM/DD HH:MM:SS').
   - Dash-separated ('YYYY-MM-DD' and 'YYYY-MM-DD HH:MM:SS').
   - ISO 8601 timestamps ('YYYY-MM-DDTHH:MM:SSZ' and timezone offsets).
   - Fallback to today's date for empty strings, None, and invalid strings.
3. SubsidyTrackerClient deep-link normalization:
   - Uppercase region ('KR-11') and model IDs ('IONIQ-5-2026').
   - Lowercase region ('kr-11') and model IDs.
   - Surrounding whitespace ('  KR-11  ', '  ioniq-5-2026  ').
   - Invalid/unknown IDs fallback to index 0 defaults.
   - Shorthand Korean region ('서울', '부산', '제주') and model names ('아이오닉 5', 'EV6').
   - Physical source verification in SubsidyTrackerClient.tsx.
4. Crawler session warm-up:
   - BaseCrawler.ensure_warm_up with None, empty string, and whitespace.
   - BobaeDreamCrawler.ensure_warm_up with None, empty string, force=True, bool argument.
   - DCInsideCrawler.ensure_warm_up with None, empty string, force=True, bool argument.
   - SafeHttpClient.warm_up_session resilience without unhandled crashes.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Domain models and trackers
from tracker.subsidy_tracker import SubsidyTracker, _safe_int_metric, _metric_val
from tracker.subsidy_models import RegionRecord, CategoryMetrics
from tracker.models.summary_model import NationwideSummary
from models.complaint import ComplaintRecord
from crawlers.base_crawler import BaseCrawler
from crawlers.bobaedream import BobaeDreamCrawler, BOBAE_BASE_URL
from crawlers.dcinside import DCInsideCrawler, DC_BASE_URL
from utils.http_client import SafeHttpClient


# ==============================================================================
# Suite 1: compute_nationwide_summary Adversarial Resilience
# ==============================================================================

class TestComputeNationwideSummaryAdversarial(unittest.TestCase):
    """Empirical challenge suite for SubsidyTracker.compute_nationwide_summary."""

    def setUp(self) -> None:
        self.tracker = SubsidyTracker()

    def test_extreme_astronomical_units_and_budget(self) -> None:
        """compute_nationwide_summary handles 10^12 units and 10^18 KRW without overflow."""
        r_extreme = RegionRecord(
            region_id="ext-1",
            overall_status="CRITICAL",
            categories={
                "passenger": CategoryMetrics.from_dict({
                    "announced_units": 10**12,
                    "applied_units": 10**12,
                    "delivered_units": 10**12,
                    "total_budget_krw": 10**18,
                    "remaining_budget_krw": 0,
                })
            },
        )
        summary = self.tracker.compute_nationwide_summary([r_extreme])
        self.assertIsInstance(summary, NationwideSummary)
        self.assertEqual(summary.total_announced_units, 10**12)
        self.assertEqual(summary.total_applied_units, 10**12)
        self.assertEqual(summary.total_delivered_units, 10**12)
        self.assertEqual(summary.total_remaining_units, 0)
        self.assertEqual(summary.nationwide_depletion_rate, 100.0)
        # 10^18 KRW / 10^9 = 1,000,000,000 billion KRW
        self.assertEqual(summary.total_budget_billion_krw, 1_000_000_000.0)
        self.assertEqual(summary.disbursed_budget_billion_krw, 1_000_000_000.0)
        self.assertEqual(summary.alert_region_counts["critical"], 1)

    def test_nan_and_inf_in_category_metrics_and_dictionaries(self) -> None:
        """compute_nationwide_summary gracefully suppresses NaN and Inf to finite zero numbers."""
        r_nan_inf = RegionRecord(
            region_id="nan-inf-1",
            overall_status="HEALTHY",
            categories={
                "passenger": CategoryMetrics.from_dict({
                    "announced_units": float("nan"),
                    "applied_units": float("inf"),
                    "delivered_units": float("-inf"),
                    "total_budget_krw": float("nan"),
                    "remaining_budget_krw": float("inf"),
                }),
                "commercial": {
                    "announced_units": float("inf"),
                    "applied_units": float("nan"),
                    "delivered_units": float("-inf"),
                    "total_budget_krw": float("nan"),
                    "remaining_budget_krw": float("nan"),
                },
                "bus": {
                    "announced_units": "NaN",
                    "applied_units": "Infinity",
                    "delivered_units": "-Infinity",
                    "total_budget_krw": None,
                    "remaining_budget_krw": None,
                },
            },
        )
        summary = self.tracker.compute_nationwide_summary([r_nan_inf])
        self.assertEqual(summary.total_announced_units, 0)
        self.assertEqual(summary.total_applied_units, 0)
        self.assertEqual(summary.total_delivered_units, 0)
        self.assertEqual(summary.total_remaining_units, 0)
        self.assertEqual(summary.nationwide_depletion_rate, 0.0)
        self.assertEqual(summary.total_budget_billion_krw, 0.0)
        self.assertEqual(summary.disbursed_budget_billion_krw, 0.0)
        self.assertFalse(math.isnan(summary.nationwide_depletion_rate))
        self.assertFalse(math.isinf(summary.nationwide_depletion_rate))

    def test_malformed_dictionary_metrics(self) -> None:
        """compute_nationwide_summary accepts malformed, nested, non-dict, and mixed category payloads."""
        r_malformed = RegionRecord(
            region_id="malformed-1",
            overall_status="  DEPLETED  ",
            categories={
                "passenger": None,
                "commercial": "corrupt_string_value",
                "bus": {
                    "announced_units": {"bad": "type"},
                    "applied_units": [1, 2, 3],
                    "delivered_units": None,
                    "total_budget_krw": "not_a_number",
                    "remaining_budget_krw": -5000,
                },
                "custom_category": {
                    "announced_units": "500",
                    "applied_units": "250",
                    "delivered_units": "100",
                    "total_budget_krw": "5000000000",
                    "remaining_budget_krw": "2500000000",
                },
            },
        )
        summary = self.tracker.compute_nationwide_summary([r_malformed])
        self.assertEqual(summary.total_announced_units, 500)
        self.assertEqual(summary.total_applied_units, 250)
        self.assertEqual(summary.total_delivered_units, 100)
        self.assertEqual(summary.total_remaining_units, 250)
        self.assertEqual(summary.nationwide_depletion_rate, 50.0)
        self.assertEqual(summary.total_budget_billion_krw, 5.0)
        self.assertEqual(summary.disbursed_budget_billion_krw, 2.5)
        # DEPLETED status was stripped and counted in alert_counts
        self.assertEqual(summary.alert_region_counts["depleted"], 1)

    def test_negative_values_clamped_to_zero(self) -> None:
        """Negative announced/applied units are clamped to zero."""
        r_neg = RegionRecord(
            region_id="neg-1",
            overall_status="healthy",
            categories={
                "passenger": {
                    "announced_units": -100,
                    "applied_units": -50,
                    "delivered_units": -20,
                    "total_budget_krw": -1000,
                    "remaining_budget_krw": -500,
                }
            },
        )
        summary = self.tracker.compute_nationwide_summary([r_neg])
        self.assertEqual(summary.total_announced_units, 0)
        self.assertEqual(summary.total_applied_units, 0)
        self.assertEqual(summary.total_delivered_units, 0)
        self.assertEqual(summary.nationwide_depletion_rate, 0.0)


# ==============================================================================
# Suite 2: ComplaintRecord Date Parsing Edge Cases
# ==============================================================================

class TestComplaintRecordDateParsingAdversarial(unittest.TestCase):
    """Empirical challenge suite for ComplaintRecord.date_str property."""

    def _make_record(self, created_at: Any) -> ComplaintRecord:
        return ComplaintRecord(
            id="test-date-id",
            source="community_portal",
            url="https://example.com/view?id=123",
            title="결함 테스트",
            author="익명",
            created_at=created_at,
            vehicle_brand="현대",
            vehicle_model="아이오닉 5",
            defect_category="BATTERY_CHARGING",
            summary="배터리 이슈",
            verbatim_quote="완속 충전 시 배터리가 방전되는 결함이 있습니다.",
        )

    def test_dot_separated_formats(self) -> None:
        """Standard dot-separated timestamps ('YYYY.MM.DD' and 'YYYY.MM.DD HH:MM:SS') are parsed."""
        r1 = self._make_record("2025.11.05")
        self.assertEqual(r1.date_str, "2025-11-05")

        r2 = self._make_record("2024.03.15 18:45:00")
        self.assertEqual(r2.date_str, "2024-03-15")

        r3 = self._make_record("  2026.01.20  ")
        self.assertEqual(r3.date_str, "2026-01-20")

    def test_slash_separated_formats(self) -> None:
        """Standard slash-separated timestamps ('YYYY/MM/DD' and 'YYYY/MM/DD HH:MM:SS') are parsed."""
        r1 = self._make_record("2025/12/31")
        self.assertEqual(r1.date_str, "2025-12-31")

        r2 = self._make_record("2026/04/01 09:15:30")
        self.assertEqual(r2.date_str, "2026-04-01")

        r3 = self._make_record("  2024/08/19 23:59:59  ")
        self.assertEqual(r3.date_str, "2024-08-19")

    def test_dash_and_iso_timestamps(self) -> None:
        """Hyphen YYYY-MM-DD and ISO 8601 timestamps are extracted accurately."""
        r1 = self._make_record("2026-02-14")
        self.assertEqual(r1.date_str, "2026-02-14")

        r2 = self._make_record("2026-07-22T15:30:00Z")
        self.assertEqual(r2.date_str, "2026-07-22")

        r3 = self._make_record("2026-09-10T12:00:00+09:00")
        self.assertEqual(r3.date_str, "2026-09-10")

    def test_fallback_to_today_on_invalid_or_missing_dates(self) -> None:
        """Corrupt, empty, or None created_at values cleanly fallback to current UTC date."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        self.assertEqual(self._make_record("").date_str, today)
        self.assertEqual(self._make_record(None).date_str, today)
        self.assertEqual(self._make_record("invalid_date_string").date_str, today)
        self.assertEqual(self._make_record("2026").date_str, today)
        self.assertEqual(self._make_record("2026-04").date_str, today)


# ==============================================================================
# Suite 3: SubsidyTrackerClient Deep-Link Normalization
# ==============================================================================

class TestSubsidyTrackerClientDeepLinkNormalization(unittest.TestCase):
    """Empirical challenge suite for SubsidyTrackerClient deep link normalization."""

    @classmethod
    def setUpClass(cls) -> None:
        # Load real database
        web_base = PROJECT_ROOT if (PROJECT_ROOT / "src" / "data").exists() else (PROJECT_ROOT / "ev-stealth-web")
        cls.data_file = web_base / "src" / "data" / "ev_subsidy_data.json"
        with open(cls.data_file, "r", encoding="utf-8") as f:
            cls.db = json.load(f)
        cls.regions = cls.db["regions"]
        cls.models = cls.db["popular_models_matrix"]
        cls.tsx_file = web_base / "src" / "app" / "subsidy-tracker" / "SubsidyTrackerClient.tsx"

    def _resolve_model(self, selected_model_id: Any) -> Any:
        """Exact replication of activeModel useMemo in SubsidyTrackerClient.tsx."""
        q = str(selected_model_id or "").strip().lower()
        for m in self.models:
            if m["model_id"].lower() == q or q in m["name_ko"].lower():
                return m
        return self.models[0]

    def _resolve_region(self, selected_region_id: Any) -> Any:
        """Exact replication of activeRegionForCalc useMemo in SubsidyTrackerClient.tsx."""
        q = str(selected_region_id or "").strip().lower()
        suffix_regex = re.compile(r"(특별시|광역시|특별자치시|도|특별자치도)$")
        for r in self.regions:
            short_ko = suffix_regex.sub("", r["name_ko"]).lower()
            if (
                r["region_id"].lower() == q
                or r["iso_code"].lower() == q
                or r["name_ko"].lower() == q
                or short_ko == q
                or r["name_en"].lower() == q
            ):
                return r
        return self.regions[0]

    def test_uppercase_and_whitespace_region_ids(self) -> None:
        """Uppercase, lowercase, and padded region IDs resolve to correct region."""
        # Uppercase
        r_upper = self._resolve_region("KR-11")
        self.assertEqual(r_upper["region_id"], "KR-11")

        # Lowercase
        r_lower = self._resolve_region("kr-11")
        self.assertEqual(r_lower["region_id"], "KR-11")

        # Whitespace
        r_white = self._resolve_region("   KR-11   ")
        self.assertEqual(r_white["region_id"], "KR-11")

    def test_uppercase_and_whitespace_model_ids(self) -> None:
        """Uppercase, lowercase, and padded model IDs resolve to correct model."""
        m_upper = self._resolve_model("IONIQ-5-2026")
        self.assertEqual(m_upper["model_id"], "ioniq-5-2026")

        m_white = self._resolve_model("   ioniq-5-2026   ")
        self.assertEqual(m_white["model_id"], "ioniq-5-2026")

    def test_invalid_region_and_model_fallback_to_index_zero(self) -> None:
        """Non-existent region and model IDs cleanly fallback to index 0 defaults."""
        r_invalid = self._resolve_region("INVALID_REGION_XYZ")
        self.assertEqual(r_invalid["region_id"], self.regions[0]["region_id"])

        m_invalid = self._resolve_model("NON_EXISTENT_MODEL_999")
        self.assertEqual(m_invalid["model_id"], self.models[0]["model_id"])

    def test_korean_shorthand_deep_links(self) -> None:
        """Korean shorthand names ('서울', '부산', '제주', '아이오닉 5') resolve accurately."""
        r_seoul = self._resolve_region("서울")
        self.assertEqual(r_seoul["region_id"], "KR-11")

        r_busan = self._resolve_region("부산")
        self.assertEqual(r_busan["region_id"], "KR-26")

        r_jeju = self._resolve_region("제주")
        self.assertEqual(r_jeju["region_id"], "KR-49")

        m_ioniq = self._resolve_model("아이오닉 5")
        self.assertIn("ioniq-5", m_ioniq["model_id"])

    def test_tsx_source_contains_safe_normalization_guards(self) -> None:
        """SubsidyTrackerClient.tsx physically contains case-insensitive trim and fallback guards."""
        tsx_text = self.tsx_file.read_text(encoding="utf-8")

        # Verify activeModel normalization
        self.assertIn("const q = (selectedModelId || '').trim().toLowerCase();", tsx_text)
        self.assertIn("models[0]", tsx_text)

        # Verify activeRegionForCalc normalization
        self.assertIn("const q = (selectedRegionId || '').trim().toLowerCase();", tsx_text)
        self.assertIn("regions[0]", tsx_text)


# ==============================================================================
# Suite 4: Crawler Warm-Up with Null and Empty Base URLs
# ==============================================================================

class TestCrawlerWarmUpNullEmptyAdversarial(unittest.TestCase):
    """Empirical challenge suite for crawler session warm-up with null/empty base URLs."""

    def test_base_crawler_null_and_empty_guard(self) -> None:
        """BaseCrawler.ensure_warm_up does not call warm_up_session when base_url is None or empty."""
        mock_client = MagicMock()

        class DummyCrawler(BaseCrawler):
            def parse_post_detail(self, html: str, post_url: str, **kwargs: Any) -> Dict[str, Any]:
                return {}

        c = DummyCrawler(client=mock_client)
        c.ensure_warm_up(None)
        self.assertFalse(mock_client.warm_up_session.called)
        self.assertFalse(c._warmed_up)

        c.ensure_warm_up("")
        self.assertFalse(mock_client.warm_up_session.called)
        self.assertFalse(c._warmed_up)

    def test_bobaedream_crawler_null_empty_fallback_to_default_domain(self) -> None:
        """BobaeDreamCrawler.ensure_warm_up falls back to BOBAE_BASE_URL when passed None or empty string."""
        mock_client = MagicMock()
        crawler = BobaeDreamCrawler(client=mock_client)

        crawler.ensure_warm_up(None)
        mock_client.warm_up_session.assert_called_with(BOBAE_BASE_URL)
        self.assertTrue(crawler._warmed_up)

        # Calling with empty string and force=True re-triggers with BOBAE_BASE_URL
        mock_client.reset_mock()
        crawler.ensure_warm_up("", force=True)
        mock_client.warm_up_session.assert_called_with(BOBAE_BASE_URL)

    def test_dcinside_crawler_null_empty_fallback_to_default_domain(self) -> None:
        """DCInsideCrawler.ensure_warm_up falls back to DC_BASE_URL when passed None or empty string."""
        mock_client = MagicMock()
        crawler = DCInsideCrawler(client=mock_client)

        crawler.ensure_warm_up(None)
        mock_client.warm_up_session.assert_called_with(DC_BASE_URL)
        self.assertTrue(crawler._warmed_up)

        mock_client.reset_mock()
        crawler.ensure_warm_up("", force=True)
        mock_client.warm_up_session.assert_called_with(DC_BASE_URL)

    def test_safe_http_client_warm_up_session_resilience(self) -> None:
        """SafeHttpClient.warm_up_session handles invalid URLs and exceptions without crashing."""
        client = SafeHttpClient(max_retries=1, timeout=0.1)

        # Mock opener to simulate network error instantly without backoff delay
        with patch.object(client, "request", return_value=(0, "", b"")):
            res_empty = client.warm_up_session("")
            self.assertFalse(res_empty)

            res_none = client.warm_up_session(None)  # type: ignore[arg-type]
            self.assertFalse(res_none)

            res_whitespace = client.warm_up_session("   ")
            self.assertFalse(res_whitespace)

    def test_safe_http_client_warm_up_exception_catch_resilience(self) -> None:
        """SafeHttpClient.warm_up_session catches any unexpected request exception and returns False."""
        client = SafeHttpClient()
        with patch.object(client, "request", side_effect=RuntimeError("Simulated critical error")):
            result = client.warm_up_session("https://broken.domain")
            self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
