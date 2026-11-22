"""Targeted regression tests for tracker core and atomic writer fixes (2026-11-23)."""

from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
import tempfile
import threading
import unittest

from tracker.atomic_writer import (
    _json_default,
    atomic_write_json,
    is_pid_alive,
    sanitize_nan_inf,
)
from tracker.defect_tracker import DefectTracker


class _CustomPayloadObj:
    """Helper object serialized via _json_default fallback."""

    def __init__(self, val: Decimal) -> None:
        self.val = val

    def to_dict(self) -> dict[str, Decimal]:
        return {"val": self.val}


class TestSwarmPyTrackerCoreFixes(unittest.TestCase):
    """Verifies fixes in tracker/atomic_writer.py and tracker/defect_tracker.py."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_is_pid_alive_overflow_int_returns_false(self) -> None:
        """is_pid_alive returns False without OverflowError on huge integer PIDs."""
        self.assertFalse(is_pid_alive(10**50))
        self.assertFalse(is_pid_alive("999999999999999999999999999999"))

    def test_decimal_float_overflow_sanitized_to_zero(self) -> None:
        """Finite Decimals exceeding IEEE-754 float range are clamped to 0.0 for valid JSON."""
        huge_pos = Decimal("1e500")
        huge_neg = Decimal("-1e500")

        sanitized = sanitize_nan_inf({"pos": huge_pos, "neg": huge_neg})
        self.assertEqual(sanitized["pos"], 0.0)
        self.assertEqual(sanitized["neg"], 0.0)

        self.assertEqual(_json_default(huge_pos), 0.0)
        self.assertEqual(_json_default(_CustomPayloadObj(huge_neg)), {"val": 0.0})

        target = self.test_dir / "decimal_overflow.json"
        atomic_write_json({"pos": huge_pos, "neg": huge_neg, "ok": Decimal("12.5")}, target)
        loaded = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(loaded, {"pos": 0.0, "neg": 0.0, "ok": 12.5})

    def test_defect_tracker_get_statistics_empty_path_ignores_stale_cache(self) -> None:
        """get_statistics(file_path='') must not return statistics from a previously cached file."""
        file_a = self.test_dir / "reports_a.json"
        file_a.write_text(
            json.dumps(
                {
                    "reports": [
                        {
                            "id": "r1",
                            "defect_category": "BATTERY",
                            "severity": "CRITICAL",
                            "negativity_score": 0.9,
                        }
                    ],
                    "statistics": {
                        "total_filtered_defects": 1,
                        "critical_defect_count": 1,
                        "avg_negativity_score": 0.9,
                    },
                }
            ),
            encoding="utf-8",
        )

        dt = DefectTracker(root_data_dir=self.test_dir, web_data_dir=self.test_dir)
        dt.load_reports(file_path=file_a)

        empty_stats = dt.get_statistics(file_path="")
        ws_stats = dt.get_statistics(file_path="   ")
        expected = {
            "total_filtered_defects": 0,
            "critical_defect_count": 0,
            "avg_negativity_score": 0.0,
            "category_distribution": {},
        }
        self.assertEqual(empty_stats, expected)
        self.assertEqual(ws_stats, expected)

    def test_defect_tracker_get_statistics_concurrent_file_isolation(self) -> None:
        """Concurrent get_statistics calls on different files never cross-contaminate via cache."""
        file_a = self.test_dir / "a.json"
        file_b = self.test_dir / "b.json"
        file_a.write_text(
            json.dumps({"reports": [{"id": "a1", "defect_category": "BATTERY", "severity": "CRITICAL"}]}),
            encoding="utf-8",
        )
        file_b.write_text(
            json.dumps(
                {
                    "reports": [
                        {"id": "b1", "defect_category": "PAINT", "severity": "LOW"},
                        {"id": "b2", "defect_category": "PAINT", "severity": "LOW"},
                    ]
                }
            ),
            encoding="utf-8",
        )

        dt = DefectTracker(root_data_dir=self.test_dir, web_data_dir=self.test_dir)
        errors: list[Exception] = []

        def worker(path: Path, expected_total: int, expected_cat: str) -> None:
            try:
                for _ in range(25):
                    stats = dt.get_statistics(file_path=path)
                    if stats["total_filtered_defects"] != expected_total:
                        raise AssertionError(f"Expected {expected_total}, got {stats}")
                    if expected_cat not in stats["category_distribution"]:
                        raise AssertionError(f"Missing {expected_cat} in {stats}")
            except Exception as exc:
                errors.append(exc)

        t1 = threading.Thread(target=worker, args=(file_a, 1, "BATTERY"))
        t2 = threading.Thread(target=worker, args=(file_b, 2, "PAINT"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        self.assertEqual(errors, [])

    def test_defect_tracker_whitespace_category_fallback(self) -> None:
        """Whitespace-only defect_category falls back to category across indexing, query, and stats."""
        report_file = self.test_dir / "ws_cat.json"
        report_file.write_text(
            json.dumps(
                {
                    "reports": [
                        {"id": "1", "defect_category": "   ", "category": "charging", "severity": "HIGH"},
                        {"id": "2", "defect_category": "", "category": "  ", "severity": "LOW"},
                    ]
                }
            ),
            encoding="utf-8",
        )

        dt = DefectTracker(root_data_dir=self.test_dir, web_data_dir=self.test_dir)
        charging = dt.query_defects(category="CHARGING", file_path=report_file)
        unknown = dt.query_defects(category="UNKNOWN", file_path=report_file)
        stats = dt.get_statistics(file_path=report_file)

        self.assertEqual([r["id"] for r in charging], ["1"])
        self.assertEqual([r["id"] for r in unknown], ["2"])
        self.assertEqual(stats["category_distribution"], {"charging": 1, "UNKNOWN": 1})


if __name__ == "__main__":
    unittest.main()
