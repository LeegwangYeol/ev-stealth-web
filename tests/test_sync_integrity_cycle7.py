"""
tests/test_sync_integrity_cycle7.py - Comprehensive Cycle 7 Synchronization & Engine Integrity Suite.

Covers:
1. Cryptographic SHA-256 byte parity verification across all mirrored datasets (Cycle 7):
   - data/ev_subsidy_data.json <-> ev-stealth-web/src/data/ev_subsidy_data.json
   - data/subsidy_depletion_data.json <-> ev-stealth-web/src/data/subsidy_depletion_data.json
   - data/daily_reports.json <-> ev-stealth-web/src/data/daily_reports.json
   - ev_subsidy_data.json vs subsidy_depletion_data.json cross-parity
   - Multi-buffer streaming SHA-256 digest invariance
2. Verification of atomic temporary file cleanup when errors occur in:
   - run_scraper._atomic_copy_file
   - run_tracker.sync_defect_reports
   - Ensures no dangling .tmp_sync_* files remain on disk under error injection
3. Verification that execute_tracking_cycle validates region count >= 17 on live payloads:
   - Rejects live payloads with < 17 regions (empty, partial 1 region, partial 16 regions)
   - Gracefully falls back to baseline/cached snapshot maintaining 17 regions
   - Accepts valid live payloads with == 17 regions and > 17 regions
4. Verification that bounded response read handles large / chunked payloads safely:
   - Bounded read to MAX_RESPONSE_BYTES (10MB) to prevent memory exhaustion
   - Robust charset decoding (EUC-KR, CP949, UTF-8 with BOM) via robust_decode
   - Dirty byte resilience and empty stream handling
5. Verification of programmatic defect report synchronization:
   - SubsidyTracker.collect_and_save(sync_defects=...) parameter wiring
"""

from __future__ import annotations

import filecmp
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock
from typing import Any, Dict, List, Optional, Set, Tuple

# Adaptive root path resolution
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
if str(WEB_ROOT) not in sys.path:
    sys.path.append(str(WEB_ROOT))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
else:
    # Ensure PROJECT_ROOT is at index 0
    sys.path.remove(str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT))

import run_scraper
import run_tracker
import tracker.subsidy_tracker as subsidy_tracker_mod
from tracker.subsidy_tracker import SubsidyTracker
MAX_RESPONSE_BYTES = getattr(subsidy_tracker_mod, "MAX_RESPONSE_BYTES", 10 * 1024 * 1024)
from tracker.subsidy_models import SubsidyPayload
from tracker.subsidy_baseline import build_initial_baseline
from utils.http_client import robust_decode

DATA_DIR = PROJECT_ROOT / "data"
WEB_DATA_DIR = WEB_ROOT / "src" / "data"

ROOT_SUBSIDY_DATA = DATA_DIR / "ev_subsidy_data.json"
ROOT_DEPLETION_DATA = DATA_DIR / "subsidy_depletion_data.json"
WEB_SUBSIDY_DATA = WEB_DATA_DIR / "ev_subsidy_data.json"
WEB_DEPLETION_DATA = WEB_DATA_DIR / "subsidy_depletion_data.json"
ROOT_DAILY_REPORTS = DATA_DIR / "daily_reports.json"
WEB_DAILY_REPORTS = WEB_DATA_DIR / "daily_reports.json"


def _compute_sha256(filepath: Path, chunk_size: int = 65536) -> str:
    """Compute hex SHA-256 digest of a given file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


class TestCycle7MirroredDatasetSha256Parity(unittest.TestCase):
    """Verifies complete cryptographic bitwise SHA-256 parity across all mirrored datasets for Cycle 7."""

    def test_ev_subsidy_data_sha256_byte_parity(self) -> None:
        """data/ev_subsidy_data.json and ev-stealth-web/src/data/ev_subsidy_data.json must match byte-for-byte."""
        self.assertTrue(ROOT_SUBSIDY_DATA.exists(), f"Missing {ROOT_SUBSIDY_DATA}")
        self.assertTrue(WEB_SUBSIDY_DATA.exists(), f"Missing {WEB_SUBSIDY_DATA}")
        self.assertGreater(ROOT_SUBSIDY_DATA.stat().st_size, 0)
        self.assertGreater(WEB_SUBSIDY_DATA.stat().st_size, 0)

        root_hash = _compute_sha256(ROOT_SUBSIDY_DATA)
        web_hash = _compute_sha256(WEB_SUBSIDY_DATA)

        self.assertEqual(
            root_hash,
            web_hash,
            f"Bitwise parity mismatch on ev_subsidy_data.json: {root_hash} != {web_hash}",
        )
        self.assertTrue(
            filecmp.cmp(ROOT_SUBSIDY_DATA, WEB_SUBSIDY_DATA, shallow=False),
            "filecmp failed on ev_subsidy_data.json",
        )

    def test_subsidy_depletion_data_sha256_byte_parity(self) -> None:
        """data/subsidy_depletion_data.json and ev-stealth-web/src/data/subsidy_depletion_data.json must match byte-for-byte."""
        self.assertTrue(ROOT_DEPLETION_DATA.exists(), f"Missing {ROOT_DEPLETION_DATA}")
        self.assertTrue(WEB_DEPLETION_DATA.exists(), f"Missing {WEB_DEPLETION_DATA}")
        self.assertGreater(ROOT_DEPLETION_DATA.stat().st_size, 0)
        self.assertGreater(WEB_DEPLETION_DATA.stat().st_size, 0)

        root_hash = _compute_sha256(ROOT_DEPLETION_DATA)
        web_hash = _compute_sha256(WEB_DEPLETION_DATA)

        self.assertEqual(
            root_hash,
            web_hash,
            f"Bitwise parity mismatch on subsidy_depletion_data.json: {root_hash} != {web_hash}",
        )
        self.assertTrue(
            filecmp.cmp(ROOT_DEPLETION_DATA, WEB_DEPLETION_DATA, shallow=False),
            "filecmp failed on subsidy_depletion_data.json",
        )

    def test_daily_reports_sha256_byte_parity(self) -> None:
        """data/daily_reports.json and ev-stealth-web/src/data/daily_reports.json must match byte-for-byte."""
        self.assertTrue(ROOT_DAILY_REPORTS.exists(), f"Missing {ROOT_DAILY_REPORTS}")
        self.assertTrue(WEB_DAILY_REPORTS.exists(), f"Missing {WEB_DAILY_REPORTS}")
        self.assertGreater(ROOT_DAILY_REPORTS.stat().st_size, 0)
        self.assertGreater(WEB_DAILY_REPORTS.stat().st_size, 0)

        root_hash = _compute_sha256(ROOT_DAILY_REPORTS)
        web_hash = _compute_sha256(WEB_DAILY_REPORTS)

        self.assertEqual(
            root_hash,
            web_hash,
            f"Bitwise parity mismatch on daily_reports.json: {root_hash} != {web_hash}",
        )
        self.assertTrue(
            filecmp.cmp(ROOT_DAILY_REPORTS, WEB_DAILY_REPORTS, shallow=False),
            "filecmp failed on daily_reports.json",
        )

    def test_ev_subsidy_vs_depletion_cross_parity(self) -> None:
        """ev_subsidy_data.json and subsidy_depletion_data.json must be byte-for-byte identical within each directory."""
        self.assertTrue(filecmp.cmp(ROOT_SUBSIDY_DATA, ROOT_DEPLETION_DATA, shallow=False))
        self.assertTrue(filecmp.cmp(WEB_SUBSIDY_DATA, WEB_DEPLETION_DATA, shallow=False))

    def test_streaming_sha256_chunk_size_invariance(self) -> None:
        """SHA-256 calculation must be invariant across all buffer chunk sizes (32B to 1MB)."""
        test_files = [
            ROOT_SUBSIDY_DATA,
            ROOT_DEPLETION_DATA,
            WEB_SUBSIDY_DATA,
            WEB_DEPLETION_DATA,
            ROOT_DAILY_REPORTS,
            WEB_DAILY_REPORTS,
        ]
        chunk_sizes = [32, 128, 512, 2048, 8192, 65536, 524288, 1048576]

        for tf in test_files:
            with self.subTest(file=tf.name, location=str(tf.parent)):
                hashes: Set[str] = set()
                for c_size in chunk_sizes:
                    hashes.add(_compute_sha256(tf, chunk_size=c_size))
                self.assertEqual(
                    len(hashes),
                    1,
                    f"Chunk size variance detected for {tf}: got {hashes}",
                )

    def test_payload_structural_validity_and_region_coverage(self) -> None:
        """Mirrored subsidy datasets must contain valid JSON with 17 administrative regions."""
        with open(ROOT_SUBSIDY_DATA, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("metadata", data)
        self.assertIn("regions", data)
        self.assertIn("nationwide_summary", data)

        regions = data["regions"]
        self.assertEqual(len(regions), 17, f"Expected 17 regions, found {len(regions)}")

        # Verify each region has valid structure and metrics
        for region in regions:
            self.assertIn("region_id", region)
            self.assertIn("name_ko", region)
            self.assertIn("municipalities", region)
            self.assertIn("categories", region)
            self.assertGreater(len(region["municipalities"]), 0)


class TestAtomicTempFileCleanupOnFailure(unittest.TestCase):
    """Verifies that temporary files (.tmp_sync_*) are cleaned up when exceptions occur in atomic copy routines."""

    def test_atomic_copy_file_cleanup_on_copyfileobj_error(self) -> None:
        """When shutil.copyfileobj raises an exception, the temporary file must be unlinked."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            src = Path(tmp_dir) / "source.json"
            dest = Path(tmp_dir) / "dest_dir" / "destination.json"
            src.write_text('{"key": "value"}', encoding="utf-8")

            with mock.patch("shutil.copyfileobj", side_effect=IOError("Simulated disk error")):
                with self.assertRaises(IOError):
                    run_scraper._atomic_copy_file(src, dest)

            # Destination must not exist
            self.assertFalse(dest.exists())
            # Destination parent directory must have NO lingering .tmp_sync_* files
            lingering = list(dest.parent.glob(".tmp_sync_*"))
            self.assertEqual(len(lingering), 0, f"Dangling temp files found in {dest.parent}: {lingering}")

    def test_atomic_copy_file_cleanup_on_fsync_error(self) -> None:
        """When os.fsync raises an exception, the temporary file must be unlinked."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            src = Path(tmp_dir) / "source.json"
            dest = Path(tmp_dir) / "dest_dir" / "destination.json"
            src.write_text('{"key": "value"}', encoding="utf-8")

            with mock.patch("os.fsync", side_effect=OSError("Simulated fsync crash")):
                with self.assertRaises(OSError):
                    run_scraper._atomic_copy_file(src, dest)

            self.assertFalse(dest.exists())
            lingering = list(dest.parent.glob(".tmp_sync_*"))
            self.assertEqual(len(lingering), 0, f"Dangling temp files found: {lingering}")

    def test_atomic_copy_file_cleanup_on_replace_error(self) -> None:
        """When os.replace raises an exception, the temporary file must be unlinked."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            src = Path(tmp_dir) / "source.json"
            dest = Path(tmp_dir) / "dest_dir" / "destination.json"
            src.write_text('{"key": "value"}', encoding="utf-8")

            with mock.patch("os.replace", side_effect=PermissionError("Simulated replace denied")):
                with self.assertRaises(PermissionError):
                    run_scraper._atomic_copy_file(src, dest)

            self.assertFalse(dest.exists())
            lingering = list(dest.parent.glob(".tmp_sync_*"))
            self.assertEqual(len(lingering), 0, f"Dangling temp files found: {lingering}")

    def test_atomic_copy_file_success_leaves_no_temp_files(self) -> None:
        """When copy succeeds, destination exists with identical content and zero temporary files remain."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            src = Path(tmp_dir) / "source.json"
            dest = Path(tmp_dir) / "dest_dir" / "destination.json"
            content = b'{"success": true, "bytes": 12345}'
            src.write_bytes(content)

            out = run_scraper._atomic_copy_file(src, dest)
            self.assertEqual(out, str(dest.resolve()))
            self.assertTrue(dest.exists())
            self.assertEqual(dest.read_bytes(), content)

            lingering = list(dest.parent.glob(".tmp_sync_*"))
            self.assertEqual(len(lingering), 0, f"Dangling temp files found after success: {lingering}")

    def test_sync_defect_reports_cleanup_on_copy_error(self) -> None:
        """When sync_defect_reports encounters a copy error, temporary files are unlinked."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            fake_root = Path(tmp_dir) / "root" / "data"
            fake_web = Path(tmp_dir) / "web" / "src" / "data"
            fake_root.mkdir(parents=True)
            fake_web.mkdir(parents=True)

            root_file = fake_root / "daily_reports.json"
            root_file.write_text(json.dumps([{"id": "def-1", "title": "Defect 1"}]), encoding="utf-8")

            with mock.patch("run_tracker._CURRENT_DIR", Path(tmp_dir) / "root"):
                with mock.patch("shutil.copyfileobj", side_effect=IOError("Simulated write interruption")):
                    written = run_tracker.sync_defect_reports(web_dir=fake_web)
                    self.assertEqual(written, [])

            # Check that no .tmp_sync_* files remain in web directory
            lingering = list(fake_web.glob(".tmp_sync_*"))
            self.assertEqual(len(lingering), 0, f"Dangling temp files found in web_dir: {lingering}")

    def test_sync_defect_reports_cleanup_on_replace_error(self) -> None:
        """When sync_defect_reports encounters an os.replace error, temporary files are unlinked."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            fake_root = Path(tmp_dir) / "root" / "data"
            fake_web = Path(tmp_dir) / "web" / "src" / "data"
            fake_root.mkdir(parents=True)
            fake_web.mkdir(parents=True)

            root_file = fake_root / "daily_reports.json"
            root_file.write_text(json.dumps([{"id": "def-1"}]), encoding="utf-8")

            with mock.patch("run_tracker._CURRENT_DIR", Path(tmp_dir) / "root"):
                with mock.patch("os.replace", side_effect=OSError("Simulated replace crash")):
                    written = run_tracker.sync_defect_reports(web_dir=fake_web)
                    self.assertEqual(written, [])

            lingering = list(fake_web.glob(".tmp_sync_*"))
            self.assertEqual(len(lingering), 0, f"Dangling temp files found in web_dir: {lingering}")


class TestExecuteTrackingCycleRegionCountValidation(unittest.TestCase):
    """Verifies that execute_tracking_cycle enforces len(payload.regions) >= 17 on live responses."""

    def setUp(self) -> None:
        self.tracker = SubsidyTracker(
            endpoint_url="https://api.ev-subsidy.local/v1/realtime",
            timeout_seconds=2.0,
        )

    def test_live_payload_with_zero_regions_is_rejected(self) -> None:
        """Live payload with empty regions list must be rejected and fall back to baseline with 17 regions."""
        empty_live = {
            "metadata": {"version": "1.0.0"},
            "regions": [],
            "nationwide_summary": {},
        }
        with mock.patch.object(self.tracker, "fetch_live_updates", return_value=empty_live):
            payload, is_fallback = self.tracker.execute_tracking_cycle()

            self.assertTrue(is_fallback, "Should have fallen back when live payload has 0 regions")
            self.assertIsInstance(payload, SubsidyPayload)
            self.assertEqual(len(payload.regions), 17)

    def test_live_payload_with_fewer_than_17_regions_is_rejected(self) -> None:
        """Live payload with 16 regions (< 17) must be rejected and fall back to baseline/cache."""
        # Build 16 regions by taking baseline and dropping 1
        baseline = build_initial_baseline()
        partial_regions = [r.to_dict() for r in baseline.regions[:16]]
        self.assertEqual(len(partial_regions), 16)

        partial_live = {
            "metadata": baseline.metadata.to_dict(),
            "regions": partial_regions,
            "nationwide_summary": baseline.nationwide_summary.to_dict(),
        }

        with mock.patch.object(self.tracker, "fetch_live_updates", return_value=partial_live):
            payload, is_fallback = self.tracker.execute_tracking_cycle()

            self.assertTrue(is_fallback, "Should have fallen back when live payload has 16 regions")
            self.assertIsInstance(payload, SubsidyPayload)
            self.assertEqual(len(payload.regions), 17)

    def test_live_payload_with_single_region_is_rejected(self) -> None:
        """Live payload with 1 region (e.g. only Seoul) must be rejected."""
        baseline = build_initial_baseline()
        single_region_live = {
            "metadata": baseline.metadata.to_dict(),
            "regions": [baseline.regions[0].to_dict()],
            "nationwide_summary": baseline.nationwide_summary.to_dict(),
        }

        with mock.patch.object(self.tracker, "fetch_live_updates", return_value=single_region_live):
            payload, is_fallback = self.tracker.execute_tracking_cycle()

            self.assertTrue(is_fallback)
            self.assertEqual(len(payload.regions), 17)

    def test_live_payload_with_none_regions_is_rejected(self) -> None:
        """Live payload with regions=None must be rejected without raising unhandled exception."""
        bad_live = {
            "metadata": {},
            "regions": None,
        }

        with mock.patch.object(self.tracker, "fetch_live_updates", return_value=bad_live):
            payload, is_fallback = self.tracker.execute_tracking_cycle()

            self.assertTrue(is_fallback)
            self.assertEqual(len(payload.regions), 17)

    def test_live_payload_with_exact_17_regions_is_accepted(self) -> None:
        """Live payload with exactly 17 valid regions must be accepted (is_fallback == False)."""
        baseline = build_initial_baseline()
        valid_live = {
            "metadata": baseline.metadata.to_dict(),
            "regions": [r.to_dict() for r in baseline.regions],
            "nationwide_summary": baseline.nationwide_summary.to_dict(),
        }

        with mock.patch.object(self.tracker, "fetch_live_updates", return_value=valid_live):
            payload, is_fallback = self.tracker.execute_tracking_cycle()

            self.assertFalse(is_fallback, "Should have accepted live payload with 17 regions")
            self.assertIsInstance(payload, SubsidyPayload)
            self.assertEqual(len(payload.regions), 17)

    def test_live_payload_with_more_than_17_regions_is_accepted(self) -> None:
        """Live payload with >= 17 regions (e.g. 18 regions for special jurisdiction) must be accepted."""
        baseline = build_initial_baseline()
        regions_18 = [r.to_dict() for r in baseline.regions]
        # Duplicate region 0 with different ID to simulate 18th region
        extra_region = dict(regions_18[0])
        extra_region["region_id"] = "KR-SPECIAL"
        extra_region["region_name"] = "특별행정구"
        regions_18.append(extra_region)
        self.assertEqual(len(regions_18), 18)

        live_18 = {
            "metadata": baseline.metadata.to_dict(),
            "regions": regions_18,
            "nationwide_summary": baseline.nationwide_summary.to_dict(),
        }

        with mock.patch.object(self.tracker, "fetch_live_updates", return_value=live_18):
            payload, is_fallback = self.tracker.execute_tracking_cycle()

            self.assertFalse(is_fallback, "Should have accepted live payload with 18 regions")
            self.assertIsInstance(payload, SubsidyPayload)
            self.assertEqual(len(payload.regions), 18)


class TestBoundedResponseReadAndStreamingSafety(unittest.TestCase):
    """Verifies that fetch_live_updates safely reads bounded response sizes and handles complex charsets."""

    def setUp(self) -> None:
        self.tracker = SubsidyTracker(
            endpoint_url="https://api.ev-subsidy.local/v1/realtime",
            timeout_seconds=2.0,
        )

    def test_fetch_live_updates_bounds_read_to_max_response_bytes(self) -> None:
        """Response reading must be strictly bounded to MAX_RESPONSE_BYTES (10MB)."""
        self.assertEqual(MAX_RESPONSE_BYTES, 10 * 1024 * 1024)

        mock_resp = mock.MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"status": "ok"}'

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            result = self.tracker.fetch_live_updates()
            self.assertEqual(result, {"status": "ok"})
            # Verify read was called with MAX_RESPONSE_BYTES bound
            mock_resp.read.assert_called_once_with(MAX_RESPONSE_BYTES)

    def test_fetch_live_updates_robust_decode_euckr_payload(self) -> None:
        """Live updates encoded in Korean EUC-KR / CP949 must be decoded cleanly without UnicodeDecodeError."""
        korean_payload = {"status": "정상", "message": "2026년 전기차 보조금 실시간 집계"}
        korean_json_bytes = json.dumps(korean_payload, ensure_ascii=False).encode("euc-kr")

        mock_resp = mock.MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = korean_json_bytes
        # Headers indicate euc-kr
        mock_resp.headers.get_content_charset.return_value = "euc-kr"

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            result = self.tracker.fetch_live_updates()
            self.assertIsNotNone(result)
            self.assertEqual(result["status"], "정상")
            self.assertEqual(result["message"], "2026년 전기차 보조금 실시간 집계")

    def test_fetch_live_updates_utf8_with_bom(self) -> None:
        """Live updates with UTF-8 BOM must be decoded cleanly when utf-8-sig is declared."""
        payload = {"valid": True, "count": 100}
        bom_bytes = b"\xef\xbb\xbf" + json.dumps(payload).encode("utf-8")

        mock_resp = mock.MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = bom_bytes
        mock_resp.headers.get_content_charset.return_value = "utf-8-sig"

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            result = self.tracker.fetch_live_updates()
            self.assertIsNotNone(result)
            self.assertEqual(result, payload)

    def test_fetch_live_updates_empty_response(self) -> None:
        """Empty response (0 bytes) must return None without raising unhandled exception."""
        mock_resp = mock.MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b""

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            result = self.tracker.fetch_live_updates()
            self.assertIsNone(result)

    def test_fetch_live_updates_non_200_status(self) -> None:
        """Non-200 HTTP status returns None gracefully."""
        mock_resp = mock.MagicMock()
        mock_resp.status = 503

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            result = self.tracker.fetch_live_updates()
            self.assertIsNone(result)

    def test_fetch_live_updates_corrupt_json_payload(self) -> None:
        """Malformed JSON payload is caught and returns None."""
        mock_resp = mock.MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b"<html>Service Temporarily Unavailable</html>"

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            result = self.tracker.fetch_live_updates()
            self.assertIsNone(result)


class TestProgrammaticDefectSyncIntegration(unittest.TestCase):
    """Verifies that collect_and_save supports programmatic sync_defects flag."""

    def test_collect_and_save_sync_defects_default_false(self) -> None:
        """By default, collect_and_save does NOT invoke sync_defect_reports."""
        tracker = SubsidyTracker(timeout_seconds=2.0)
        with mock.patch("run_tracker.sync_defect_reports") as mock_sync:
            with tempfile.TemporaryDirectory() as tmp_dir:
                out = Path(tmp_dir) / "ev_subsidy_data.json"
                tracker.collect_and_save(output_path=out, sync_defects=False)
                mock_sync.assert_not_called()

    def test_collect_and_save_sync_defects_true_invokes_sync(self) -> None:
        """When sync_defects=True, collect_and_save calls sync_defect_reports."""
        tracker = SubsidyTracker(timeout_seconds=2.0)
        with mock.patch("run_tracker.sync_defect_reports") as mock_sync:
            mock_sync.return_value = ["/path/to/daily_reports.json"]
            with tempfile.TemporaryDirectory() as tmp_dir:
                out = Path(tmp_dir) / "ev_subsidy_data.json"
                tracker.collect_and_save(output_path=out, sync_defects=True)
                mock_sync.assert_called_once()


if __name__ == "__main__":
    unittest.main()
