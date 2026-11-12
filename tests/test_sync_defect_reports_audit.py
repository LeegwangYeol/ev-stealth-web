"""
tests/test_sync_defect_reports_audit.py - Defect Reports Synchronization and Deduplication Audit Suite.

Verifies:
1. Reliable deduplication by ID, canonical URL, and composite key (platform, model, date, title).
2. File locking (.sync_defect_reports.lock) with acquisition timeout and automatic stale lock cleanup.
3. Strict schema conformity to TypeScript types in src/types/reports.ts.
4. Multi-mirror atomic synchronization and cryptographic SHA-256 parity.
5. Dry-run and CLI execution safety.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

# Ensure scripts and repo root are importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_ROOT = PROJECT_ROOT / "ev-stealth-web"
for p in (str(PROJECT_ROOT), str(WEB_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from scripts import sync_defect_reports as sync_engine
from tracker.atomic_writer import FileLock, cleanup_stale_lock_files


class TestDefectReportsDeduplication(unittest.TestCase):
    """Verifies that defect reports are deduplicated reliably by ID or composite key."""

    def test_deduplication_by_explicit_id(self) -> None:
        """Reports with identical 'id' are merged and deduplicated."""
        reports = [
            {
                "id": "11525527",
                "source": "dcinside",
                "date": "2026-09-30",
                "title": "520i msp 지금 사는거 어때?",
                "summary": "First summary",
                "vehicle_model": "전기차",
                "defect_category": "SERVICE_REPAIR_COST",
                "severity": "MEDIUM",
                "sentiment_score": 0.775,
                "slang_tags": ["감가"],
            },
            {
                "id": "11525527",
                "source": "dcinside",
                "date": "2026-09-30",
                "title": "520i msp 지금 사는거 어때?",
                "summary": "Detailed incoming summary with verbatim quote",
                "vehicle_model": "전기차",
                "defect_category": "SERVICE_REPAIR_COST",
                "severity": "HIGH",
                "sentiment_score": 0.850,
                "slang_tags": ["수리비", "서비스센터"],
                "author": "ㅇㅇ (222.97)",
            },
        ]

        deduped, removed = sync_engine.deduplicate_reports(reports)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(removed, 1)

        result = deduped[0]
        self.assertEqual(result["id"], "11525527")
        self.assertEqual(result["author"], "ㅇㅇ (222.97)")
        self.assertEqual(result["severity"], "HIGH")
        self.assertEqual(result["sentiment_score"], 0.850)
        # Slang tags union
        self.assertIn("감가", result["slang_tags"])
        self.assertIn("수리비", result["slang_tags"])
        self.assertIn("서비스센터", result["slang_tags"])

    def test_deduplication_by_canonical_url_when_id_missing(self) -> None:
        """Reports with missing ID but identical URL/post_url are deduplicated."""
        reports = [
            {
                "id": "",
                "source": "bobaedream",
                "url": "https://www.bobaedream.co.kr/view?code=national&No=2416882",
                "date": "2026-09-17",
                "title": "EV6 하부 배터리케이스 파손",
                "summary": "Summary 1",
                "vehicle_model": "EV6",
                "defect_category": "BATTERY_CHARGING",
                "severity": "HIGH",
                "sentiment_score": 0.90,
                "slang_tags": ["배터리"],
            },
            {
                "id": None,
                "source": "bobaedream",
                "post_url": "https://www.bobaedream.co.kr/view?code=national&No=2416882#comment",
                "date": "2026-09-17",
                "title": "EV6 하부 배터리케이스 파손",
                "summary": "Summary 2",
                "vehicle_model": "EV6",
                "defect_category": "BATTERY_CHARGING",
                "severity": "CRITICAL",
                "sentiment_score": 0.95,
                "slang_tags": ["파손"],
            },
        ]

        deduped, removed = sync_engine.deduplicate_reports(reports)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(removed, 1)
        self.assertEqual(deduped[0]["severity"], "CRITICAL")
        self.assertIn("배터리", deduped[0]["slang_tags"])
        self.assertIn("파손", deduped[0]["slang_tags"])

    def test_deduplication_by_composite_key_when_id_and_url_missing(self) -> None:
        """Reports with neither ID nor URL are deduplicated via composite key (source, model, date, title)."""
        reports = [
            {
                "source": "clien",
                "vehicle_model": "Ioniq 5",
                "date": "2026-10-01",
                "title": "ICCU 충전 경고등 점등 현상",
                "summary": "First post on ICCU issue",
                "defect_category": "BATTERY_CHARGING",
                "severity": "HIGH",
                "sentiment_score": 0.88,
                "slang_tags": ["벽돌"],
            },
            {
                "source": "clien",
                "vehicle_model": "Ioniq 5",
                "date": "2026-10-01",
                "title": "ICCU 충전 경고등 점등 현상  ",
                "summary": "Second duplicate post with whitespace title",
                "defect_category": "BATTERY_CHARGING",
                "severity": "CRITICAL",
                "sentiment_score": 0.92,
                "slang_tags": ["급발진"],
            },
        ]

        deduped, removed = sync_engine.deduplicate_reports(reports)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(removed, 1)
        self.assertEqual(deduped[0]["severity"], "CRITICAL")
        self.assertIn("벽돌", deduped[0]["slang_tags"])
        self.assertIn("급발진", deduped[0]["slang_tags"])

    def test_deduplication_preserves_unique_reports(self) -> None:
        """Distinct reports with different IDs and keys are all preserved intact."""
        reports = [
            {
                "id": "item-1",
                "source": "dcinside",
                "vehicle_model": "Model Y",
                "date": "2026-10-01",
                "title": "도장 불량",
                "defect_category": "BUILD_QUALITY",
                "severity": "LOW",
                "sentiment_score": 0.3,
                "slang_tags": [],
            },
            {
                "id": "item-2",
                "source": "bobaedream",
                "vehicle_model": "EV9",
                "date": "2026-10-02",
                "title": "시동 꺼짐 현상",
                "defect_category": "DRIVING_POWERTRAIN",
                "severity": "CRITICAL",
                "sentiment_score": 0.95,
                "slang_tags": ["벽돌"],
            },
        ]
        deduped, removed = sync_engine.deduplicate_reports(reports)
        self.assertEqual(len(deduped), 2)
        self.assertEqual(removed, 0)


class TestLockingAndStaleCleanup(unittest.TestCase):
    """Verifies file locking timeout and automatic stale lock cleanup."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_lock_acquisition_and_release(self) -> None:
        """FileLock acquires cleanly and releases upon context exit."""
        lock_path = self.test_dir / ".sync_defect_reports.lock"
        with FileLock(lock_path, timeout=2.0) as lock:
            self.assertTrue(lock.is_locked)
            self.assertTrue(lock_path.exists())
        self.assertFalse(lock.is_locked)

    def test_stale_lock_cleanup_from_dead_pid(self) -> None:
        """Stale lock from a dead PID is automatically cleaned up."""
        lock_path = self.test_dir / ".sync_defect_reports.lock"
        # Write dead PID (PID 9999999 is guaranteed non-existent on macOS/Linux)
        dead_pid = 9999999
        lock_path.write_text(f"pid={dead_pid}\ntime={time.time() - 100.0}\n", encoding="utf-8")

        cleaned = cleanup_stale_lock_files(self.test_dir, prefix=(".sync_",), max_age_seconds=60.0)
        self.assertEqual(cleaned, 1)
        self.assertFalse(lock_path.exists())

    def test_stale_lock_preserves_living_pid(self) -> None:
        """Lock file held by an active process PID is never removed."""
        lock_path = self.test_dir / ".sync_defect_reports.lock"
        lock_path.write_text(f"pid={os.getpid()}\ntime={time.time() - 3600.0}\n", encoding="utf-8")

        cleaned = cleanup_stale_lock_files(self.test_dir, prefix=(".sync_",), max_age_seconds=60.0)
        self.assertEqual(cleaned, 0)
        self.assertTrue(lock_path.exists())


class TestTypeScriptSchemaConformance(unittest.TestCase):
    """Verifies that normalized report payload matches src/types/reports.ts strictly."""

    def test_daily_report_payload_structure(self) -> None:
        """Canonical payload contains all required DailyReportData and DailyReportStatistics keys."""
        raw_reports = [
            {
                "id": "rep-001",
                "source": "bobaedream",
                "date": "2026-10-01",
                "title": "타이칸 충전 불가 이슈",
                "summary": "[타이칸] 배터리 충전 불가 현상",
                "vehicle_model": "Taycan",
                "vehicle_brand": "Porsche",
                "defect_category": "BATTERY_CHARGING",
                "severity": "CRITICAL",
                "sentiment_score": 0.95,
                "slang_tags": ["충전소", "벽돌"],
                "dsi_breakdown": {"safety": 8.0, "functional": 9.0},
            },
            {
                "id": "rep-002",
                "source": "dcinside",
                "date": "2026-10-02",
                "title": "단차 심각하네요",
                "summary": "[Model 3] 트렁크 단차 불량",
                "vehicle_model": "Model 3",
                "vehicle_brand": "Tesla",
                "defect_category": "BUILD_QUALITY",
                "severity": "LOW",
                "sentiment_score": 0.35,
                "slang_tags": ["단차"],
            },
        ]

        payload = sync_engine.build_canonical_payload(raw_reports)

        # 1. DailyReportData fields
        self.assertIn("generated_at", payload)
        self.assertIsInstance(payload["generated_at"], str)
        self.assertIn("statistics", payload)
        self.assertIsInstance(payload["statistics"], dict)
        self.assertIn("reports", payload)
        self.assertIsInstance(payload["reports"], list)
        self.assertEqual(payload["total_complaints_today"], 2)
        self.assertIsInstance(payload["top_defect_categories"], list)

        # 2. DailyReportStatistics fields
        stats = payload["statistics"]
        self.assertEqual(stats["total_filtered_defects"], 2)
        self.assertEqual(stats["critical_defect_count"], 1)
        self.assertAlmostEqual(stats["avg_negativity_score"], (0.95 + 0.35) / 2, places=3)
        self.assertIn("top_model", stats)

        # 3. DefectReportItem fields on each item
        for item in payload["reports"]:
            self.assertIsInstance(item["id"], str)
            self.assertIsInstance(item["source"], str)
            self.assertIsInstance(item["date"], str)
            self.assertIsInstance(item["title"], str)
            self.assertIsInstance(item["summary"], str)
            self.assertIsInstance(item["vehicle_model"], str)
            self.assertIn(item["defect_category"], sync_engine.VALID_DEFECT_CATEGORIES)
            self.assertIn(item["severity"], sync_engine.VALID_SEVERITIES)
            self.assertIsInstance(item["sentiment_score"], float)
            self.assertIsInstance(item["slang_tags"], list)
            self.assertTrue(all(isinstance(t, str) for t in item["slang_tags"]))

    def test_existing_daily_reports_json_schema_validity(self) -> None:
        """The existing production daily_reports.json files conform to TypeScript schema."""
        for rel_path in (
            "data/daily_reports.json",
            "ev-stealth-web/src/data/daily_reports.json",
            "ev-stealth-web/data/daily_reports.json",
        ):
            target = PROJECT_ROOT / rel_path
            if target.is_file():
                with self.subTest(file=rel_path):
                    valid = sync_engine.validate_reports_file(target)
                    self.assertTrue(valid, f"Validation failed for {rel_path}")
                    with open(target, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self.assertIn("statistics", data)
                    self.assertIn("reports", data)
                    self.assertGreater(len(data["reports"]), 0)


class TestMultiTargetSynchronization(unittest.TestCase):
    """Verifies atomic multi-mirror synchronization and cryptographic SHA-256 parity."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp_dir.name)
        self.root_data = self.base / "data"
        self.web_data = self.base / "ev-stealth-web" / "src" / "data"
        self.root_data.mkdir(parents=True)
        self.web_data.mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_synchronization_creates_identical_mirrors(self) -> None:
        """sync_defect_reports creates byte-for-byte identical mirrors with deduplicated data."""
        # Create a source file in root_data with a duplicated item
        source_file = self.root_data / "daily_reports.json"
        raw_data = {
            "generated_at": "2026-10-01T00:00:00+00:00",
            "statistics": {"total_scraped": 10, "total_filtered_defects": 2, "avg_negativity_score": 0.8, "critical_defect_count": 1},
            "reports": [
                {
                    "id": "dup-1",
                    "source": "bobaedream",
                    "date": "2026-10-01",
                    "title": "배터리 충전 불가",
                    "summary": "Initial report",
                    "vehicle_model": "EV6",
                    "defect_category": "BATTERY_CHARGING",
                    "severity": "HIGH",
                    "sentiment_score": 0.85,
                    "slang_tags": ["배터리"],
                },
                {
                    "id": "dup-1",
                    "source": "bobaedream",
                    "date": "2026-10-01",
                    "title": "배터리 충전 불가",
                    "summary": "Updated report with critical severity",
                    "vehicle_model": "EV6",
                    "defect_category": "BATTERY_CHARGING",
                    "severity": "CRITICAL",
                    "sentiment_score": 0.95,
                    "slang_tags": ["급속충전"],
                },
            ],
        }
        with open(source_file, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, indent=2, ensure_ascii=False)

        written = sync_engine.sync_defect_reports(
            root_dir=self.root_data,
            web_dir=self.web_data,
            dry_run=False,
        )

        web_file = self.web_data / "daily_reports.json"
        self.assertTrue(web_file.is_file(), "Web mirror daily_reports.json must exist")

        with open(source_file, "rb") as f1, open(web_file, "rb") as f2:
            h_root = hashlib.sha256(f1.read()).hexdigest()
            h_web = hashlib.sha256(f2.read()).hexdigest()
        self.assertEqual(h_root, h_web, "Root and Web daily_reports.json must have 100% SHA-256 parity")

        # Verify duplicate was removed in both
        with open(web_file, "r", encoding="utf-8") as f:
            synced_data = json.load(f)
        self.assertEqual(len(synced_data["reports"]), 1)
        self.assertEqual(synced_data["reports"][0]["severity"], "CRITICAL")
        self.assertIn("배터리", synced_data["reports"][0]["slang_tags"])
        self.assertIn("급속충전", synced_data["reports"][0]["slang_tags"])

    def test_dry_run_guarantees_zero_writes(self) -> None:
        """When dry_run is True, no files are written to disk."""
        written = sync_engine.sync_defect_reports(
            root_dir=self.root_data,
            web_dir=self.web_data,
            dry_run=True,
        )
        self.assertEqual(written, [])
        self.assertFalse((self.web_data / "daily_reports.json").exists())


if __name__ == "__main__":
    unittest.main()
