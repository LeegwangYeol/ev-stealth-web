"""
tests/test_subsidy_resilience.py - Resilience and Mirror Synchronization Hardening Suite.

Verifies:
1. Resilient exception fallback in SubsidyTracker:
   - UnicodeDecodeError (e.g. malformed encoding from remote server)
   - http.client.IncompleteRead (e.g. dropped streaming connection)
   - http.client.HTTPException family (RemoteDisconnected, BadStatusLine, generic HTTPException)
   - Standard network failures (URLError, HTTPError, TimeoutError, JSONDecodeError, OSError)
   - Corrupted cache isolation and graceful baseline fallback
2. Dual-path mirror synchronization contract for run_scraper.py --sync-web:
   - Inclusion of both root data/daily_reports.json and ev-stealth-web/src/data/daily_reports.json
   - Deterministic path resolution and deduplication
   - Atomic multi-target replication contract
3. Continuous bitwise SHA-256 parity verification across synced datasets:
   - Root vs Web ev_subsidy_data.json
   - Root vs Web subsidy_depletion_data.json
   - Root vs Web daily_reports.json
   - Chunk-size invariant SHA-256 digest computation
"""

from __future__ import annotations

from datetime import datetime, timezone
import filecmp
import hashlib
import http.client
import io
import json
import logging
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest import mock
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Set, Tuple

# Adaptive root path detection
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
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
WEB_ROOT = PROJECT_ROOT / "ev-stealth-web"
if str(WEB_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_ROOT))

from tracker.subsidy_tracker import SubsidyTracker
from tracker.subsidy_models import SubsidyPayload
from tracker.subsidy_baseline import build_initial_baseline
import run_scraper
import run_tracker

DATA_DIR = PROJECT_ROOT / "data"
WEB_DATA_DIR = WEB_ROOT / "src" / "data"

ROOT_SUBSIDY_DATA = DATA_DIR / "ev_subsidy_data.json"
ROOT_DEPLETION_DATA = DATA_DIR / "subsidy_depletion_data.json"
WEB_SUBSIDY_DATA = WEB_DATA_DIR / "ev_subsidy_data.json"
WEB_DEPLETION_DATA = WEB_DATA_DIR / "subsidy_depletion_data.json"
ROOT_DAILY_REPORTS = DATA_DIR / "daily_reports.json"
WEB_DAILY_REPORTS = WEB_DATA_DIR / "daily_reports.json"


def _compute_file_sha256(filepath: Path, chunk_size: int = 65536) -> str:
    """Compute hex SHA-256 digest of a given file using streaming read."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


class TestSubsidyTrackerResilientExceptionFallback(unittest.TestCase):
    """Verifies that SubsidyTracker gracefully absorbs dirty network & parsing errors without crashing."""

    def setUp(self) -> None:
        self.endpoint = "https://ev-subsidy-api.korea.local/v1/realtime"
        self.tracker = SubsidyTracker(
            endpoint_url=self.endpoint,
            timeout_seconds=1.5,
        )

    def test_fetch_live_updates_unicode_decode_error(self) -> None:
        """When remote server sends corrupt non-UTF-8 bytes, fetch_live_updates must catch UnicodeDecodeError and return None."""
        mock_response = mock.MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b"\xff\xfe\xfd\x80\x81"

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value = mock_response

            result = self.tracker.fetch_live_updates()
            self.assertIsNone(
                result,
                "fetch_live_updates must return None on UnicodeDecodeError without propagating exception",
            )

    def test_fetch_live_updates_incomplete_read(self) -> None:
        """When HTTP stream terminates prematurely (IncompleteRead), fetch_live_updates must return None."""
        mock_response = mock.MagicMock()
        mock_response.status = 200
        mock_response.read.side_effect = http.client.IncompleteRead(b'{"partial":', expected=1024)

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value = mock_response

            result = self.tracker.fetch_live_updates()
            self.assertIsNone(
                result,
                "fetch_live_updates must return None on http.client.IncompleteRead",
            )

    def test_fetch_live_updates_http_exception_family(self) -> None:
        """All variations of http.client.HTTPException must be cleanly caught without propagating."""
        http_exceptions = [
            http.client.RemoteDisconnected("Remote end closed connection without response"),
            http.client.BadStatusLine("INVALID_HTTP_VERSION"),
            http.client.CannotSendRequest(),
            http.client.CannotSendHeader(),
            http.client.ResponseNotReady(),
            http.client.LineTooLong("header line too long"),
            http.client.HTTPException("Generic protocol level failure"),
        ]

        for exc in http_exceptions:
            with self.subTest(exc=type(exc).__name__):
                with mock.patch("urllib.request.urlopen", side_effect=exc):
                    result = self.tracker.fetch_live_updates()
                    self.assertIsNone(
                        result,
                        f"fetch_live_updates failed to catch {type(exc).__name__}",
                    )

    def test_fetch_live_updates_standard_network_errors(self) -> None:
        """URLError, HTTPError, TimeoutError, JSONDecodeError, and OSError must all return None."""
        network_errors = [
            urllib.error.HTTPError(self.endpoint, 502, "Bad Gateway", {}, None),
            urllib.error.HTTPError(self.endpoint, 503, "Service Unavailable", {}, None),
            urllib.error.URLError("Connection refused"),
            urllib.error.URLError(socket.gaierror(-2, "Name or service not known")),
            TimeoutError("The read operation timed out"),
            socket.timeout("Socket timed out"),
            json.JSONDecodeError("Expecting value", "<html>500 Error</html>", 0),
            OSError("Network unreachable"),
            ConnectionResetError("Connection reset by peer"),
        ]

        for exc in network_errors:
            with self.subTest(exc=type(exc).__name__):
                with mock.patch("urllib.request.urlopen", side_effect=exc):
                    result = self.tracker.fetch_live_updates()
                    self.assertIsNone(
                        result,
                        f"fetch_live_updates failed to catch {type(exc).__name__}",
                    )

    def test_execute_tracking_cycle_survives_unicode_decode_error(self) -> None:
        """Pipeline execution must seamlessly fall back to cached snapshot/baseline when UnicodeDecodeError occurs."""
        mock_response = mock.MagicMock()
        mock_response.status = 200
        mock_response.read.side_effect = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value = mock_response

            payload, _ = self.tracker.execute_tracking_cycle()
            self.assertIsInstance(payload, SubsidyPayload)
            self.assertEqual(len(payload.regions), 17)
            self.assertEqual(payload.metadata.total_regions_tracked, 17)
            self.assertEqual(payload.metadata.total_municipalities_tracked, 73)
            self.assertGreater(payload.nationwide_summary.total_budget_billion_krw, 0)

    def test_execute_tracking_cycle_survives_incomplete_read(self) -> None:
        """Pipeline execution must seamlessly fall back when http.client.IncompleteRead occurs."""
        mock_response = mock.MagicMock()
        mock_response.status = 200
        mock_response.read.side_effect = http.client.IncompleteRead(b'{"incomplete": true')

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value = mock_response

            payload, _ = self.tracker.execute_tracking_cycle()
            self.assertIsInstance(payload, SubsidyPayload)
            self.assertEqual(len(payload.regions), 17)

    def test_execute_tracking_cycle_survives_bad_status_line(self) -> None:
        """Pipeline execution must seamlessly fall back when http.client.BadStatusLine occurs."""
        with mock.patch("urllib.request.urlopen", side_effect=http.client.BadStatusLine("500 ???")):
            payload, _ = self.tracker.execute_tracking_cycle()
            self.assertIsInstance(payload, SubsidyPayload)
            self.assertEqual(len(payload.regions), 17)

    def test_corrupted_cache_resilience_and_quarantine(self) -> None:
        """When cached snapshot is malformed JSON, tracker quarantines the file and falls back cleanly."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            corrupt_file = Path(tmp_dir) / "ev_subsidy_data.json"
            corrupt_file.write_text("{invalid_json_garbage_data", encoding="utf-8")

            tracker = SubsidyTracker(
                cache_fallback_path=corrupt_file,
                quarantine_corrupted=True,
            )
            payload, _ = tracker.execute_tracking_cycle(
                validate_cache=True,
                quarantine_corrupted=True,
            )

            self.assertIsInstance(payload, SubsidyPayload)
            self.assertEqual(len(payload.regions), 17)
            # Corrupted file should have been quarantined
            quarantined = list(Path(tmp_dir).glob("ev_subsidy_data.corrupt_*.json"))
            self.assertGreaterEqual(len(quarantined), 1)

    def test_schema_invalid_cache_discard_resilience(self) -> None:
        """When cache contains valid JSON but invalid schema (<17 regions), tracker gracefully discards it and falls back to baseline."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            bad_schema_file = Path(tmp_dir) / "ev_subsidy_data.json"
            bad_data = {"metadata": {}, "regions": [{"region_id": "KR-11"}]}
            bad_schema_file.write_text(json.dumps(bad_data), encoding="utf-8")

            tracker = SubsidyTracker(
                cache_fallback_path=bad_schema_file,
                quarantine_corrupted=False,
            )
            payload, is_fallback = tracker.execute_tracking_cycle(
                validate_cache=True,
                quarantine_corrupted=False,
            )

            self.assertIsInstance(payload, SubsidyPayload)
            self.assertEqual(len(payload.regions), 17)
            self.assertTrue(is_fallback, "Should have fallen back to baseline when cache is invalid")

            # Verify discard_corrupted_cache method explicitly removes corrupt file
            self.assertTrue(bad_schema_file.exists())
            discarded = tracker.discard_corrupted_cache(bad_schema_file)
            self.assertTrue(discarded)
            self.assertFalse(bad_schema_file.exists())


class TestScraperDualPathMirrorSyncContract(unittest.TestCase):
    """Verifies that run_scraper.py --sync-web implements dual-path mirror writing across root and web."""

    def test_resolve_root_reports_path_contract(self) -> None:
        """_resolve_root_reports_path must return an existing or valid data/daily_reports.json path."""
        root_path = run_scraper._resolve_root_reports_path()
        self.assertIsInstance(root_path, Path)
        self.assertEqual(root_path.name, "daily_reports.json")
        self.assertEqual(root_path.parent.name, "data")

    def test_resolve_web_reports_path_contract(self) -> None:
        """_resolve_web_reports_path must return a daily_reports.json path in src/data."""
        web_path = run_scraper._resolve_web_reports_path()
        self.assertIsInstance(web_path, Path)
        self.assertEqual(web_path.name, "daily_reports.json")
        self.assertEqual(web_path.parent.name, "data")
        self.assertEqual(web_path.parent.parent.name, "src")

    def test_scraper_sync_web_includes_dual_paths(self) -> None:
        """When sync_web=True, pipeline.run target_paths must contain both web and root paths."""
        pipeline = run_scraper.ScraperPipeline()
        with mock.patch.object(pipeline, "harvest", return_value=([], {})):
            with mock.patch.object(pipeline, "filter_defects", return_value=[]):
                summary = pipeline.run(
                    sources="all",
                    limit=1,
                    sync_web=True,
                    dry_run=True,
                )

                targets = summary["target_paths"]
                self.assertGreaterEqual(
                    len(targets),
                    2,
                    f"Expected at least 2 target paths when sync_web=True, got {targets}",
                )

                # Ensure web target is present
                web_targets = [t for t in targets if "ev-stealth-web" in t or "src/data" in t]
                self.assertTrue(len(web_targets) > 0, "Web mirror path missing in target_paths")

                # Ensure root target is present
                root_target = os.path.abspath(str(run_scraper._resolve_root_reports_path()))
                self.assertIn(root_target, targets, f"Root data path {root_target} missing from target_paths")

    def test_scraper_sync_web_dry_run_skips_disk_writes(self) -> None:
        """In dry_run mode with sync_web=True, no disk files are modified."""
        pipeline = run_scraper.ScraperPipeline()
        with mock.patch.object(pipeline, "harvest", return_value=([], {})):
            with mock.patch.object(pipeline, "filter_defects", return_value=[]):
                summary = pipeline.run(
                    sync_web=True,
                    dry_run=True,
                )
                self.assertTrue(summary["dry_run"])
                self.assertEqual(len(summary["written_paths"]), 0)

    def test_scraper_atomic_copy_helper_integrity(self) -> None:
        """_atomic_copy_file helper must copy content cleanly with bitwise identity."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            src = Path(tmp_dir) / "source.json"
            dest = Path(tmp_dir) / "subdir" / "dest.json"
            content = b'{"test": "atomic_replication_contract"}'
            src.write_bytes(content)

            copied = run_scraper._atomic_copy_file(src, dest)
            self.assertTrue(Path(copied).exists())
            self.assertEqual(Path(copied).read_bytes(), content)
            self.assertEqual(_compute_file_sha256(src), _compute_file_sha256(dest))

    def test_scraper_cli_sync_web_argument_parsing(self) -> None:
        """create_parser must support --sync-web, --web-dir, and --dry-run flags."""
        parser = run_scraper.create_parser()
        args = parser.parse_args(["--sync-web", "--dry-run", "--limit", "5"])
        self.assertTrue(args.sync_web)
        self.assertTrue(args.dry_run)
        self.assertEqual(args.limit, 5)


class TestContinuousBitwiseSha256Parity(unittest.TestCase):
    """Verifies that all synced datasets maintain continuous 100% bitwise SHA-256 parity."""

    def test_ev_subsidy_data_sha256_parity(self) -> None:
        """data/ev_subsidy_data.json and ev-stealth-web/src/data/ev_subsidy_data.json must match exactly."""
        self.assertTrue(ROOT_SUBSIDY_DATA.exists(), f"Missing {ROOT_SUBSIDY_DATA}")
        self.assertTrue(WEB_SUBSIDY_DATA.exists(), f"Missing {WEB_SUBSIDY_DATA}")

        root_hash = _compute_file_sha256(ROOT_SUBSIDY_DATA)
        web_hash = _compute_file_sha256(WEB_SUBSIDY_DATA)

        self.assertEqual(
            root_hash,
            web_hash,
            f"Bitwise parity violation on ev_subsidy_data.json: {root_hash} != {web_hash}",
        )
        self.assertTrue(filecmp.cmp(ROOT_SUBSIDY_DATA, WEB_SUBSIDY_DATA, shallow=False))

    def test_subsidy_depletion_data_sha256_parity(self) -> None:
        """data/subsidy_depletion_data.json and ev-stealth-web/src/data/subsidy_depletion_data.json must match exactly."""
        self.assertTrue(ROOT_DEPLETION_DATA.exists(), f"Missing {ROOT_DEPLETION_DATA}")
        self.assertTrue(WEB_DEPLETION_DATA.exists(), f"Missing {WEB_DEPLETION_DATA}")

        root_hash = _compute_file_sha256(ROOT_DEPLETION_DATA)
        web_hash = _compute_file_sha256(WEB_DEPLETION_DATA)

        self.assertEqual(
            root_hash,
            web_hash,
            f"Bitwise parity violation on subsidy_depletion_data.json: {root_hash} != {web_hash}",
        )
        self.assertTrue(filecmp.cmp(ROOT_DEPLETION_DATA, WEB_DEPLETION_DATA, shallow=False))

    def test_daily_reports_sha256_parity(self) -> None:
        """data/daily_reports.json and ev-stealth-web/src/data/daily_reports.json must match exactly."""
        self.assertTrue(ROOT_DAILY_REPORTS.exists(), f"Missing {ROOT_DAILY_REPORTS}")
        self.assertTrue(WEB_DAILY_REPORTS.exists(), f"Missing {WEB_DAILY_REPORTS}")

        root_hash = _compute_file_sha256(ROOT_DAILY_REPORTS)
        web_hash = _compute_file_sha256(WEB_DAILY_REPORTS)

        self.assertEqual(
            root_hash,
            web_hash,
            f"Bitwise parity violation on daily_reports.json: {root_hash} != {web_hash}",
        )
        self.assertTrue(filecmp.cmp(ROOT_DAILY_REPORTS, WEB_DAILY_REPORTS, shallow=False))

    def test_ev_subsidy_vs_depletion_data_cross_parity(self) -> None:
        """Within each directory, ev_subsidy_data.json and subsidy_depletion_data.json must be identical."""
        self.assertTrue(filecmp.cmp(ROOT_SUBSIDY_DATA, ROOT_DEPLETION_DATA, shallow=False))
        self.assertTrue(filecmp.cmp(WEB_SUBSIDY_DATA, WEB_DEPLETION_DATA, shallow=False))

    def test_sha256_streaming_chunk_size_invariance(self) -> None:
        """Computing SHA-256 with chunks from 64B to 1MB must produce invariant digests for all tracked files."""
        files_to_verify = [
            ROOT_SUBSIDY_DATA,
            ROOT_DEPLETION_DATA,
            WEB_SUBSIDY_DATA,
            WEB_DEPLETION_DATA,
            ROOT_DAILY_REPORTS,
            WEB_DAILY_REPORTS,
        ]
        chunk_sizes = [64, 256, 1024, 4096, 65536, 1048576]

        for filepath in files_to_verify:
            with self.subTest(file=filepath.name):
                digests: Set[str] = set()
                for c_size in chunk_sizes:
                    digests.add(_compute_file_sha256(filepath, chunk_size=c_size))
                self.assertEqual(
                    len(digests),
                    1,
                    f"Non-deterministic SHA-256 for {filepath}: got {digests}",
                )

    def test_multi_destination_save_payload_sha256_identity(self) -> None:
        """SubsidyTracker.save_payload across multiple isolated paths maintains 100% SHA-256 identity."""
        tracker = SubsidyTracker(timeout_seconds=2.0)
        payload = build_initial_baseline()

        with tempfile.TemporaryDirectory() as tmp_dir:
            p1 = Path(tmp_dir) / "dest1" / "ev_subsidy_data.json"
            p2 = Path(tmp_dir) / "dest2" / "ev_subsidy_data.json"
            p3 = Path(tmp_dir) / "dest3" / "ev_subsidy_data.json"
            p4 = Path(tmp_dir) / "dest4" / "ev_subsidy_data.json"

            written = tracker.save_payload(payload, [p1, p2, p3, p4])
            self.assertEqual(len(written), 4)

            hashes = [_compute_file_sha256(p) for p in (p1, p2, p3, p4)]
            self.assertEqual(len(set(hashes)), 1, f"Hash divergence across destinations: {hashes}")


if __name__ == "__main__":
    unittest.main()
