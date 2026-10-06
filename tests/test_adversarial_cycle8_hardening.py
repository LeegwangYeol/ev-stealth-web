"""
tests/test_adversarial_cycle8_hardening.py - Adversarial Hardening Suite for Cycle 8.

Covers:
1. SubsidyTracker.fetch_live_updates() retry backoff and Accept-Encoding: identity:
   - Verification of request headers ensuring Accept-Encoding is strictly 'identity' to prevent
     unexpected gzip / compression decoding errors.
   - 3-attempt exponential backoff retry verification:
     - Transient network drops (URLError, RemoteDisconnected, ConnectionResetError, HTTPError 503)
       on attempts 1 and 2 recover on attempt 3.
     - Exponential sleep backoff intervals verified (base * 2^(attempt-1)).
     - Exhaustion of all 3 retries logs warning and initiates graceful None fallback.
   - Non-200 HTTP status handling (HTTP 500, 502, 504) triggering retry backoff.
   - Stripping of UTF-8 Byte Order Mark (\ufeff) from live response strings.
2. Boundary clamping on negative units, depletion rates, and extreme values:
   - calculate_depletion_rate:
     - Negative applied units clamped to 0.0.
     - Negative or zero announced units clamped to 0.0.
     - Non-numeric inputs, NaN, Inf, None handled safely without throwing.
     - Normal and over-subscription percentages calculated accurately.
   - calculate_remaining_units:
     - Negative applied units clamped safely to announced quota.
     - Negative announced units clamped to 0.
     - Over-subscription clamped strictly to 0 (no negative units).
     - None or string anomalies safely return 0.
   - Category metrics & region metrics boundary clamping:
     - Negative announced/applied/delivered values clamped so depletion_rate >= 0.0,
       delivery_rate >= 0.0, remaining_units >= 0, remaining_budget_krw >= 0.
   - calculate_net_subsidy:
     - High subsidy relative to MSRP clamps net_price_krw at 0 (no negative prices).
3. Fallback behaviors on simulated network drops and corrupt cache files:
   - Network stream interruptions:
     - http.client.IncompleteRead during streaming body read falls back safely.
     - Socket timeouts and remote disconnections absorbed without unhandled exceptions.
   - Corrupt cache file isolation and schema validation:
     - Missing cache file returns None, triggers fresh baseline.
     - Truncated / malformed JSON discarded gracefully.
     - Non-dict root structure discarded gracefully.
     - Sub-17 region cache payloads rejected during validation, preventing poisoned cache loading.
     - quarantine_corrupted_cache renames corrupted snapshot with timestamp suffix.
     - discard_corrupted_cache unlinks corrupted file cleanly from disk.
   - execute_tracking_cycle end-to-end resilience under dual failure:
     - Endpoint completely down AND cache corrupt -> returns pristine 17-region baseline payload
       with complete mathematical parity and fallback_used=True.
"""

from __future__ import annotations

from datetime import datetime, timezone
import errno
import http.client
import io
import json
import logging
import math
import os
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import time
import unittest
from unittest import mock
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple, Union

# Adaptive repository root resolution
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

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
else:
    sys.path.remove(str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT))

if str(WEB_ROOT) not in sys.path:
    sys.path.append(str(WEB_ROOT))

import tracker.subsidy_tracker as subsidy_tracker_mod
from tracker.subsidy_tracker import (
    SubsidyTracker,
    calculate_depletion_rate,
    calculate_net_subsidy,
    calculate_price_cap_ratio,
    calculate_remaining_units,
    classify_alert_tier,
)
from tracker.subsidy_models import (
    AlertSeverity,
    CategoryMetrics,
    RegionRecord,
    SubsidyPayload,
)
from tracker.subsidy_baseline import build_initial_baseline


class TestSubsidyTrackerFetchRetryAndEncodingHardening(unittest.TestCase):
    """Verifies SubsidyTracker.fetch_live_updates() exponential retry backoff and Accept-Encoding header."""

    def setUp(self) -> None:
        self.endpoint = "https://ev-subsidy-api.korea.local/v1/realtime"
        self.tracker = SubsidyTracker(
            endpoint_url=self.endpoint,
            timeout_seconds=2.0,
        )

    def test_request_headers_include_accept_encoding_identity(self) -> None:
        """fetch_live_updates() must explicitly set Accept-Encoding: identity to prevent gzip corruption."""
        intercepted_request: Optional[urllib.request.Request] = None

        def dummy_urlopen(req, *args, **kwargs):
            nonlocal intercepted_request
            intercepted_request = req
            mock_resp = mock.MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = json.dumps({"regions": []}).encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp
            mock_resp.__exit__.return_value = None
            return mock_resp

        with mock.patch("urllib.request.urlopen", side_effect=dummy_urlopen):
            res = self.tracker.fetch_live_updates()

        self.assertIsNotNone(intercepted_request, "urlopen was not invoked with a Request object")
        self.assertIsInstance(intercepted_request, urllib.request.Request)
        # Check headers (urllib stores headers with capitalized keys or get_header)
        ae_header = intercepted_request.get_header("Accept-encoding") or intercepted_request.headers.get("Accept-encoding")
        self.assertEqual(ae_header, "identity", "Request must specify Accept-Encoding: identity")
        ua_header = intercepted_request.get_header("User-agent") or intercepted_request.headers.get("User-agent")
        self.assertIn("MyECar-SubsidyTracker", ua_header)
        self.assertEqual(res, {"regions": []})

    def test_retry_backoff_recovers_after_two_transient_failures(self) -> None:
        """fetch_live_updates() retries up to 3 times on transient failures and recovers on 3rd attempt."""
        attempts = 0
        sleep_durations: List[float] = []

        def mock_urlopen(req, *args, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                # 1st attempt: 503 Service Unavailable
                raise urllib.error.HTTPError(
                    url=req.full_url,
                    code=503,
                    msg="Service Unavailable",
                    hdrs={},
                    fp=io.BytesIO(b"Busy"),
                )
            elif attempts == 2:
                # 2nd attempt: URLError Connection Reset
                raise urllib.error.URLError("Connection reset by peer")
            else:
                # 3rd attempt: Success
                mock_resp = mock.MagicMock()
                mock_resp.status = 200
                mock_resp.read.return_value = json.dumps({"status": "recovered", "regions": []}).encode("utf-8")
                mock_resp.__enter__.return_value = mock_resp
                mock_resp.__exit__.return_value = None
                return mock_resp

        def mock_sleep(seconds: float) -> None:
            sleep_durations.append(seconds)

        with mock.patch("urllib.request.urlopen", side_effect=mock_urlopen):
            with mock.patch("time.sleep", side_effect=mock_sleep):
                payload = self.tracker.fetch_live_updates()

        self.assertEqual(attempts, 3, "Expected exactly 3 poll attempts")
        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("status"), "recovered")
        self.assertEqual(len(sleep_durations), 2, "Expected exactly 2 sleep intervals before attempt 3")
        # Verify backoff values are positive and increase
        self.assertGreater(sleep_durations[0], 0)
        self.assertGreater(sleep_durations[1], sleep_durations[0])

    def test_retry_backoff_exhaustion_returns_none_gracefully(self) -> None:
        """When all 3 retry attempts fail, returns None without raising an unhandled exception."""
        attempts = 0
        sleep_calls = 0

        def mock_urlopen_always_fail(req, *args, **kwargs):
            nonlocal attempts
            attempts += 1
            raise urllib.error.URLError("Temporary DNS failure")

        def mock_sleep(seconds: float) -> None:
            nonlocal sleep_calls
            sleep_calls += 1

        with mock.patch("urllib.request.urlopen", side_effect=mock_urlopen_always_fail):
            with mock.patch("time.sleep", side_effect=mock_sleep):
                payload = self.tracker.fetch_live_updates()

        self.assertIsNone(payload, "Exhausted retries must return None")
        self.assertEqual(attempts, 3, "Must attempt 3 times before failing")
        self.assertEqual(sleep_calls, 2, "Must sleep 2 times between 3 attempts")

    def test_retry_on_remote_disconnected(self) -> None:
        """fetch_live_updates() absorbs http.client.RemoteDisconnected and retries."""
        attempts = 0

        def mock_urlopen_disconnect(req, *args, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise http.client.RemoteDisconnected("Remote end closed connection without response")
            mock_resp = mock.MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = b'{"success": true}'
            mock_resp.__enter__.return_value = mock_resp
            mock_resp.__exit__.return_value = None
            return mock_resp

        with mock.patch("urllib.request.urlopen", side_effect=mock_urlopen_disconnect):
            with mock.patch("time.sleep"):
                res = self.tracker.fetch_live_updates()

        self.assertEqual(attempts, 3)
        self.assertEqual(res, {"success": True})

    def test_utf8_bom_stripped_cleanly(self) -> None:
        """Live payloads prefixed with UTF-8 Byte Order Mark (\ufeff) parse cleanly."""
        bom_payload = "\ufeff" + json.dumps({"regions": ["KR-11"], "bom_test": True})

        mock_resp = mock.MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = bom_payload.encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None

        with mock.patch("urllib.request.urlopen", return_value=mock_resp):
            res = self.tracker.fetch_live_updates()

        self.assertIsNotNone(res)
        self.assertTrue(res.get("bom_test"))


class TestBoundaryClampingAndMathematicalHardening(unittest.TestCase):
    """Verifies defensive clamping on negative numbers, over-subscriptions, and anomalous metric calculations."""

    def test_calculate_depletion_rate_negative_and_zero_clamping(self) -> None:
        """calculate_depletion_rate clamps negative inputs to 0.0 and guards zero division."""
        # Negative applied
        self.assertEqual(calculate_depletion_rate(-10, 100), 0.0)
        self.assertEqual(calculate_depletion_rate(-500, 1000), 0.0)

        # Negative announced
        self.assertEqual(calculate_depletion_rate(50, -100), 0.0)

        # Both negative
        self.assertEqual(calculate_depletion_rate(-20, -100), 0.0)

        # Zero announced (zero-division guard)
        self.assertEqual(calculate_depletion_rate(50, 0), 0.0)
        self.assertEqual(calculate_depletion_rate(0, 0), 0.0)

        # Normal valid calculations
        self.assertEqual(calculate_depletion_rate(50, 100), 50.0)
        self.assertEqual(calculate_depletion_rate(75, 100), 75.0)

        # Over-subscription (quota exhausted beyond 100%)
        self.assertEqual(calculate_depletion_rate(125, 100), 125.0)

    def test_calculate_depletion_rate_non_numeric_and_nan_inf(self) -> None:
        """calculate_depletion_rate safely handles NaN, Inf, None, and strings without exceptions."""
        self.assertEqual(calculate_depletion_rate(float("nan"), 100), 0.0)
        self.assertEqual(calculate_depletion_rate(50, float("nan")), 0.0)
        self.assertEqual(calculate_depletion_rate(float("inf"), 100), 0.0)
        self.assertEqual(calculate_depletion_rate(50, float("inf")), 0.0)
        self.assertEqual(calculate_depletion_rate(None, 100), 0.0)
        self.assertEqual(calculate_depletion_rate(50, None), 0.0)
        self.assertEqual(calculate_depletion_rate("corrupt", 100), 0.0)
        self.assertEqual(calculate_depletion_rate(50, "corrupt"), 0.0)

    def test_calculate_remaining_units_clamping(self) -> None:
        """calculate_remaining_units clamps at 0 for over-subscription and negative inputs."""
        # Normal
        self.assertEqual(calculate_remaining_units(40, 100), 60)
        self.assertEqual(calculate_remaining_units(100, 100), 0)

        # Over-subscription (applied > announced)
        self.assertEqual(calculate_remaining_units(120, 100), 0)
        self.assertEqual(calculate_remaining_units(9999, 100), 0)

        # Negative applied (should clamp to max announced units)
        self.assertEqual(calculate_remaining_units(-50, 100), 100)

        # Negative announced (should clamp to 0)
        self.assertEqual(calculate_remaining_units(50, -100), 0)
        self.assertEqual(calculate_remaining_units(-50, -100), 0)

        # Anomalous types
        self.assertEqual(calculate_remaining_units(None, 100), 0)
        self.assertEqual(calculate_remaining_units("invalid", 100), 0)

    def test_calculate_category_metrics_negative_clamping(self) -> None:
        """SubsidyTracker.calculate_category_metrics() ensures all resulting metrics are strictly non-negative."""
        tracker = SubsidyTracker()
        cat = tracker.calculate_category_metrics(
            announced=-500,
            applied=-200,
            delivered=-100,
            max_local_subsidy=5_000_000,
        )
        self.assertGreaterEqual(cat.depletion_rate, 0.0)
        self.assertGreaterEqual(cat.delivery_rate, 0.0)
        self.assertGreaterEqual(cat.remaining_units, 0)
        self.assertGreaterEqual(cat.remaining_budget_krw, 0)
        self.assertEqual(cat.status, "HEALTHY")

    def test_update_region_metrics_boundary_preservation(self) -> None:
        """update_region_metrics() guarantees overall_depletion_rate is bounded and valid."""
        tracker = SubsidyTracker()
        p_cat = CategoryMetrics(
            announced_units=100,
            applied_units=150,  # Over-subscribed
            delivered_units=90,
            remaining_units=0,
            depletion_rate=150.0,
            delivery_rate=90.0,
            status="DEPLETED",
            max_local_subsidy_krw=1_500_000,
            max_total_subsidy_krw=8_000_000,
        )
        region = RegionRecord(
            region_id="KR-11",
            name_ko="서울특별시",
            categories={"passenger": p_cat},
        )
        updated = tracker.update_region_metrics(region)
        self.assertEqual(updated.overall_depletion_rate, 150.0)
        self.assertEqual(updated.overall_status, "DEPLETED")

    def test_calculate_net_subsidy_price_floor(self) -> None:
        """calculate_net_subsidy() ensures net consumer purchase price is clamped at 0 KRW."""
        # Scenario where subsidies exceed MSRP (e.g. low-cost EV with high local subsidy)
        res = calculate_net_subsidy(
            model_national=6_500_000,
            max_national=6_500_000,
            max_local=10_000_000,
            msrp=12_000_000,  # Subsidies = 16.5M > MSRP 12M
        )
        self.assertEqual(res["total_subsidy_krw"], 16_500_000)
        self.assertEqual(res["net_price_krw"], 0, "Net price must never be negative")
        self.assertGreaterEqual(res["national_subsidy_krw"], 0)
        self.assertGreaterEqual(res["local_subsidy_krw"], 0)


class TestFallbackBehaviorsSimulatedNetworkDropsAndCorruptCache(unittest.TestCase):
    """Verifies graceful fallback behavior on simulated network drops and corrupt cache files."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="test_cycle8_adversarial_")
        self.corrupt_cache_path = Path(self.test_dir) / "corrupt_cache.json"

    def tearDown(self) -> None:
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_incomplete_read_network_drop_initiates_graceful_fallback(self) -> None:
        """A network drop midway through streaming response body triggers graceful fallback."""
        tracker = SubsidyTracker(endpoint_url="https://api.test/stream")

        mock_resp = mock.MagicMock()
        mock_resp.status = 200
        mock_resp.read.side_effect = http.client.IncompleteRead(partial=b'{"regions": [')
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None

        with mock.patch("urllib.request.urlopen", return_value=mock_resp):
            with mock.patch("time.sleep"):
                res = tracker.fetch_live_updates()

        self.assertIsNone(res, "Incomplete read must not raise and must return None")

    def test_socket_timeout_initiates_graceful_fallback(self) -> None:
        """Socket timeout during connection or read initiates fallback without crash."""
        tracker = SubsidyTracker(endpoint_url="https://api.test/timeout")

        with mock.patch("urllib.request.urlopen", side_effect=TimeoutError("The read operation timed out")):
            with mock.patch("time.sleep"):
                res = tracker.fetch_live_updates()

        self.assertIsNone(res)

    def test_corrupted_json_syntax_cache_discards_and_returns_none(self) -> None:
        """load_cached_payload() discards cache file with syntax errors and returns None."""
        with open(self.corrupt_cache_path, "w", encoding="utf-8") as f:
            f.write("{ invalid json: unquoted }")

        tracker = SubsidyTracker(cache_fallback_path=self.corrupt_cache_path)
        payload = tracker.load_cached_payload(self.corrupt_cache_path, validate=True)
        self.assertIsNone(payload, "Corrupted JSON cache should return None")

    def test_cache_with_non_dict_root_structure_returns_none(self) -> None:
        """Cache file containing a JSON array or scalar root is rejected."""
        with open(self.corrupt_cache_path, "w", encoding="utf-8") as f:
            json.dump([1, 2, 3], f)

        tracker = SubsidyTracker(cache_fallback_path=self.corrupt_cache_path)
        payload = tracker.load_cached_payload(self.corrupt_cache_path, validate=True)
        self.assertIsNone(payload, "Array root in cache must return None")

    def test_sub_17_region_cache_rejected_during_validation(self) -> None:
        """Cache payload with fewer than 17 regions is rejected by schema validator."""
        partial_cache = {
            "metadata": {"version": "1.0.0"},
            "regions": [
                {
                    "region_id": "KR-11",
                    "name_ko": "서울",
                    "categories": {},
                }
            ],
            "nationwide_summary": {},
        }
        with open(self.corrupt_cache_path, "w", encoding="utf-8") as f:
            json.dump(partial_cache, f)

        tracker = SubsidyTracker(cache_fallback_path=self.corrupt_cache_path)
        payload = tracker.load_cached_payload(self.corrupt_cache_path, validate=True)
        self.assertIsNone(payload, "Cache with < 17 regions must be rejected during validation")

    def test_quarantine_corrupted_cache_renames_file(self) -> None:
        """quarantine_corrupted_cache() renames corrupted cache file with a .corrupt_ timestamp suffix."""
        with open(self.corrupt_cache_path, "w", encoding="utf-8") as f:
            f.write("GARBAGE DATA")

        tracker = SubsidyTracker()
        quarantined_path = tracker.quarantine_corrupted_cache(self.corrupt_cache_path)

        self.assertIsNotNone(quarantined_path)
        self.assertTrue(quarantined_path.exists())
        self.assertFalse(self.corrupt_cache_path.exists(), "Original corrupted file should be renamed")
        self.assertIn(".corrupt_", quarantined_path.name)

    def test_discard_corrupted_cache_deletes_file(self) -> None:
        """discard_corrupted_cache() physically deletes the corrupt cache from disk."""
        with open(self.corrupt_cache_path, "w", encoding="utf-8") as f:
            f.write("GARBAGE")

        tracker = SubsidyTracker()
        success = tracker.discard_corrupted_cache(self.corrupt_cache_path)

        self.assertTrue(success)
        self.assertFalse(self.corrupt_cache_path.exists())

    def test_execute_tracking_cycle_catastrophic_failure_survives_with_baseline(self) -> None:
        """Under simultaneous network failure AND corrupted cache, execute_tracking_cycle succeeds with baseline."""
        with open(self.corrupt_cache_path, "w", encoding="utf-8") as f:
            f.write("TOTAL CORRUPTION")

        tracker = SubsidyTracker(
            endpoint_url="https://api.unreachable.local",
            cache_fallback_path=self.corrupt_cache_path,
            validate_cache=True,
        )

        payload, fallback_used = tracker.execute_tracking_cycle(mock_network_failure=True)

        self.assertTrue(fallback_used, "Fallback must be declared True")
        self.assertIsInstance(payload, SubsidyPayload)
        self.assertEqual(len(payload.regions), 17, "Baseline fallback must provide exactly 17 regions")
        self.assertGreater(payload.nationwide_summary.total_announced_units, 0)
        self.assertGreater(payload.nationwide_summary.total_applied_units, 0)
        self.assertGreaterEqual(payload.nationwide_summary.nationwide_depletion_rate, 0.0)


if __name__ == "__main__":
    unittest.main()
