"""Targeted regression tests for 2026-11-28 Python scripts audit fixes."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import run_tracker
from scripts import sync_defect_reports as sdr


def test_run_tracker_sync_defect_reports_json_root_discovers_public_mirror(tmp_path: Path) -> None:
    """When root_dir is a .json file inside data/, public/data mirror at project root is synced."""
    proj = tmp_path / "proj"
    data_dir = proj / "data"
    pub_dir = proj / "public" / "data"
    web_dir = proj / "web" / "src" / "data"
    data_dir.mkdir(parents=True)
    pub_dir.mkdir(parents=True)
    web_dir.mkdir(parents=True)

    root_file = data_dir / "daily_reports.json"
    payload = {"reports": [{"id": "rep-1", "title": "test"}]}
    root_file.write_text(json.dumps(payload), encoding="utf-8")

    written = run_tracker.sync_defect_reports(
        root_dir=root_file,
        web_dir=proj / "web",
        dry_run=False,
    )

    pub_file = pub_dir / "daily_reports.json"
    web_file = web_dir / "daily_reports.json"
    assert pub_file.is_file()
    assert web_file.is_file()
    assert str(pub_file) in written
    assert json.loads(pub_file.read_text(encoding="utf-8")) == payload


def test_scripts_sync_defect_reports_json_root_discovers_public_mirror(tmp_path: Path) -> None:
    """get_default_known_paths resolves sibling public/data when root_dir is a .json file path."""
    proj = tmp_path / "proj"
    data_dir = proj / "data"
    pub_dir = proj / "public" / "data"
    data_dir.mkdir(parents=True)
    pub_dir.mkdir(parents=True)

    root_file = data_dir / "daily_reports.json"
    root_file.write_text(json.dumps({"reports": [{"id": "rep-2", "title": "defect"}]}), encoding="utf-8")

    root_p, _web_p, additional = sdr.get_default_known_paths(root_dir=root_file)
    assert root_p == root_file
    assert (pub_dir / "daily_reports.json") in additional


def test_run_tracker_sync_defect_reports_sanitizes_invalid_timeouts(tmp_path: Path) -> None:
    """sync_defect_reports sanitizes bool, NaN, Inf, and non-positive timeouts before FileLock."""
    data_dir = tmp_path / "data"
    web_dir = tmp_path / "web"
    data_dir.mkdir()
    web_dir.mkdir()
    (data_dir / "daily_reports.json").write_text(json.dumps({"reports": [{"id": "1"}]}), encoding="utf-8")

    captured: list[tuple[float, float]] = []

    class RecordingLock:
        def __init__(self, path, timeout=15.0, stale_timeout=60.0):
            captured.append((timeout, stale_timeout))

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    with patch("tracker.atomic_writer.FileLock", RecordingLock):
        for bad_t, bad_s in [
            (True, False),
            (float("nan"), float("inf")),
            (-5.0, 0.0),
        ]:
            run_tracker.sync_defect_reports(
                root_dir=data_dir,
                web_dir=web_dir,
                lock_timeout=bad_t,  # type: ignore[arg-type]
                stale_timeout=bad_s,  # type: ignore[arg-type]
            )

        run_tracker.sync_defect_reports(
            root_dir=data_dir,
            web_dir=web_dir,
            lock_timeout=0.25,
            stale_timeout=0.5,
        )

    assert captured[:3] == [(15.0, 60.0), (15.0, 60.0), (15.0, 60.0)]
    assert captured[3] == (0.25, 0.5)
