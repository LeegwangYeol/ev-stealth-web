"""Targeted regression tests for tracker core and atomic writer fixes (2026-11-24)."""

from __future__ import annotations

from decimal import Decimal
import errno
import json
import os
from pathlib import Path
import tempfile
import time
from types import MappingProxyType, SimpleNamespace
import unittest
from unittest import mock

from tracker.atomic_writer import (
    FileLock,
    atomic_write_json,
    atomic_write_text,
    cleanup_stale_lock_files,
)
from tracker.defect_tracker import DefectTracker


class TestSwarmPyTrackerCore20261124(unittest.TestCase):
    """Regression suite for 2026-11-24 tracker core & atomic writer hardening."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_filelock_numeric_overflow_and_bounded_sleep(self) -> None:
        """FileLock handles huge int overflow/NaN/bool params and does not oversleep past timeout."""
        lock_path = self.test_dir / "overflow.lock"
        lock = FileLock(
            lock_path,
            timeout=10**400,
            poll_interval=10**400,
            stale_timeout=Decimal("NaN"),
            fail_on_timeout=False,
        )
        self.assertEqual(lock.timeout, 10.0)
        self.assertEqual(lock.poll_interval, 0.02)
        self.assertEqual(lock.stale_timeout, 300.0)

        # Verify bounded sleep when poll_interval >> timeout under contention
        contended_lock = FileLock(
            lock_path,
            timeout=0.05,
            poll_interval=5.0,
            fail_on_timeout=False,
        )
        start = time.monotonic()
        with mock.patch("fcntl.flock", side_effect=OSError(errno.EAGAIN, "busy")):
            with contended_lock:
                self.assertFalse(contended_lock.acquired)
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 0.5)

    def test_atomic_write_temp_prefix_traversal_sanitized(self) -> None:
        """Path separators or '..' in temp_prefix cannot write outside dest directory."""
        nested_dir = self.test_dir / "nested"
        nested_dir.mkdir(parents=True, exist_ok=True)
        json_target = nested_dir / "data.json"
        txt_target = nested_dir / "note.txt"

        atomic_write_json({"ok": True}, json_target, temp_prefix="../escape_")
        atomic_write_text("hello", txt_target, temp_prefix="sub/escape_")

        self.assertEqual(json.loads(json_target.read_text(encoding="utf-8")), {"ok": True})
        self.assertEqual(txt_target.read_text(encoding="utf-8"), "hello")
        parent_entries = [p.name for p in self.test_dir.iterdir()]
        self.assertEqual(parent_entries, ["nested"])

    def test_cleanup_stale_lock_files_skips_symlinks(self) -> None:
        """cleanup_stale_lock_files ignores symlinks and never touches their targets."""
        real_target = self.test_dir / "protected.txt"
        real_target.write_text("important", encoding="utf-8")
        old_time = time.time() - 7200.0
        os.utime(real_target, (old_time, old_time))

        symlink_lock = self.test_dir / ".ev_atomic_symlink.lock"
        try:
            symlink_lock.symlink_to(real_target)
        except OSError:
            self.skipTest("Symlinks not supported in this environment")

        cleaned = cleanup_stale_lock_files(self.test_dir, max_age_seconds=3600.0)
        self.assertEqual(cleaned, 0)
        self.assertTrue(symlink_lock.is_symlink())
        self.assertEqual(real_target.read_text(encoding="utf-8"), "important")

    def test_query_defects_respects_overridden_load_reports_after_cache_warm(self) -> None:
        """Overriding load_reports bypasses stale in-memory cache in query_defects."""
        reports_file = self.test_dir / "daily_reports.json"
        reports_file.write_text(
            json.dumps({"reports": [{"id": "disk-1", "defect_category": "BATTERY"}]}),
            encoding="utf-8",
        )
        dt = DefectTracker(root_data_dir=self.test_dir, web_data_dir=self.test_dir)
        initial = dt.query_defects(category="BATTERY")
        self.assertEqual([r["id"] for r in initial], ["disk-1"])

        dt.load_reports = lambda file_path=None: [{"id": "mock-2", "defect_category": "BATTERY"}]  # type: ignore[method-assign]
        patched = dt.query_defects(category="BATTERY")
        self.assertEqual([r["id"] for r in patched], ["mock-2"])

    def test_query_and_load_handle_empty_and_null_byte_paths(self) -> None:
        """Empty/whitespace paths return empty results and null-byte paths fail safely."""
        reports_file = self.test_dir / "daily_reports.json"
        reports_file.write_text(
            json.dumps({"reports": [{"id": "r1", "defect_category": "BATTERY"}]}),
            encoding="utf-8",
        )
        dt = DefectTracker(root_data_dir=self.test_dir, web_data_dir=self.test_dir)
        dt.load_reports()

        self.assertEqual(dt.query_defects(file_path=""), [])
        self.assertEqual(dt.query_defects(file_path="   "), [])
        self.assertEqual(dt.load_full_report_data(file_path="bad\x00path.json"), {"reports": [], "statistics": {}})

    def test_get_statistics_category_distribution_is_isolated_from_cache(self) -> None:
        """Mutating returned category_distribution dict does not mutate cached statistics."""
        reports_file = self.test_dir / "stats.json"
        reports_file.write_text(
            json.dumps(
                {
                    "reports": [{"id": "r1", "defect_category": "BATTERY", "severity": "HIGH"}],
                    "statistics": {
                        "total_filtered_defects": 1,
                        "critical_defect_count": 0,
                        "avg_negativity_score": 0.5,
                        "category_distribution": {"BATTERY": 1},
                    },
                }
            ),
            encoding="utf-8",
        )
        dt = DefectTracker(root_data_dir=self.test_dir, web_data_dir=self.test_dir)
        first = dt.get_statistics(file_path=reports_file)
        first["category_distribution"]["BATTERY"] = 999

        second = dt.get_statistics(file_path=reports_file)
        self.assertEqual(second["category_distribution"]["BATTERY"], 1)

    def test_filter_raw_posts_mapping_and_string_comments(self) -> None:
        """filter_raw_posts supports non-dict Mappings and avoids character-splitting string comments."""
        captured_posts = []

        class StubFilter:
            def process_post(self, post):
                captured_posts.append(post)
                return SimpleNamespace(is_authentic_defect=True, post_id=post.post_id, comments=post.comments)

        dt = DefectTracker(
            root_data_dir=self.test_dir,
            web_data_dir=self.test_dir,
            filter_engine=StubFilter(),
        )
        mapping_post = MappingProxyType(
            {
                "platform": "bobaedream",
                "post_id": "m-1",
                "url": "https://example.com/1",
                "title": "ICCU issue",
                "content": "Charging failed",
            }
        )
        obj_post = SimpleNamespace(
            platform="clien",
            post_id="o-2",
            url="https://example.com/2",
            title="Motor noise",
            content="Whining sound",
            comments="same issue here",
            created_at="2026-11-24",
            author="user2",
        )

        res = dt.filter_raw_posts([mapping_post, obj_post])
        self.assertEqual(len(res), 2)
        self.assertEqual(captured_posts[0].post_id, "m-1")
        self.assertEqual(captured_posts[0].title, "ICCU issue")
        self.assertEqual(captured_posts[1].comments, ["same issue here"])

    def test_sync_defect_reports_invalidates_cache_when_quarantine_leaves_no_source(self) -> None:
        """Quarantining the only cached report file invalidates DefectTracker cache even when sync aborts."""
        root_dir = self.test_dir / "root_data"
        web_dir = self.test_dir / "web_data"
        root_dir.mkdir(parents=True, exist_ok=True)
        web_dir.mkdir(parents=True, exist_ok=True)

        root_reports = root_dir / "daily_reports.json"
        root_reports.write_text(
            json.dumps({"reports": [{"id": "cached-1", "defect_category": "BATTERY"}]}),
            encoding="utf-8",
        )

        dt = DefectTracker(root_data_dir=root_dir, web_data_dir=web_dir)
        self.assertEqual([r["id"] for r in dt.load_reports()], ["cached-1"])

        # Corrupt the file on disk and trigger sync_defect_reports
        root_reports.write_text("{corrupt json", encoding="utf-8")
        written = dt.sync_defect_reports(web_dir=web_dir, quarantine_corrupted=True)
        self.assertEqual(written, [])
        self.assertFalse(root_reports.exists())
        self.assertEqual(dt.load_reports(), [])


if __name__ == "__main__":
    unittest.main()
