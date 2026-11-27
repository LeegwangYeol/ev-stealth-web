"""Regression tests for py-tracker-subsidy 2026-11-28 audit fixes."""

from contextlib import contextmanager
import importlib
import json
from pathlib import Path
import sys

import pytest

_LOCAL_ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def _local_tracker_modules():
    """Ensure tracker.* imports resolve to ev-stealth-web/tracker even if an earlier test loaded parent repo tracker."""
    import tracker.subsidy_tracker as current_st

    local_tracker_dir = (_LOCAL_ROOT / "tracker").resolve()
    current_file = Path(current_st.__file__).resolve()
    if current_file.parent == local_tracker_dir:
        yield (
            importlib.import_module("tracker.subsidy_baseline"),
            importlib.import_module("tracker.subsidy_models"),
            importlib.import_module("tracker.subsidy_tracker"),
        )
        return

    saved_modules = {k: v for k, v in sys.modules.items() if k == "tracker" or k.startswith("tracker.")}
    saved_path = list(sys.path)
    try:
        for k in list(saved_modules):
            sys.modules.pop(k, None)
        sys.path.insert(0, str(_LOCAL_ROOT))
        sb = importlib.import_module("tracker.subsidy_baseline")
        sm = importlib.import_module("tracker.subsidy_models")
        st = importlib.import_module("tracker.subsidy_tracker")
        yield sb, sm, st
    finally:
        for k in list(sys.modules):
            if k == "tracker" or k.startswith("tracker."):
                sys.modules.pop(k, None)
        sys.modules.update(saved_modules)
        sys.path[:] = saved_path


@pytest.fixture
def local_tracker():
    with _local_tracker_modules() as mods:
        yield mods


def _minimal_payload_with_regions(sm, regions):
    return sm.SubsidyPayload(
        metadata=sm.SubsidyMetadata(
            version="1.0.0",
            generated_at="2026-11-28T00:00:00+00:00",
            policy_year=2026,
            data_sources=["test"],
            total_regions_tracked=len(regions),
            total_municipalities_tracked=0,
        ),
        alert_thresholds={
            "HEALTHY": sm.AlertThresholdConfig(0.0, 59.9, "원활", "HEALTHY", "#10B981", "", ""),
        },
        nationwide_summary=sm.NationwideSummary(0, 0, 0, 0, 0.0, 0.0, 0.0, {}, {}),
        regions=regions,
        popular_models_matrix=[],
        historical_depletion_trajectory=[],
    )


def test_load_cached_payload_validate_rejects_null_or_missing_categories(tmp_path: Path, local_tracker):
    _sb, _sm, st = local_tracker
    tracker = st.SubsidyTracker(validate_cache=True, quarantine_corrupted=True)

    # 17 regions with categories=None should fail validation and be quarantined
    null_cats_file = tmp_path / "null_cats.json"
    null_cats_file.write_text(
        json.dumps({"regions": [{"region_id": f"KR-{i}", "categories": None} for i in range(17)]}),
        encoding="utf-8",
    )
    assert tracker.load_cached_payload(null_cats_file, validate=True, quarantine=True) is None
    assert not null_cats_file.exists()

    # 17 regions missing categories key should fail validation
    missing_cats_file = tmp_path / "missing_cats.json"
    missing_cats_file.write_text(
        json.dumps({"regions": [{"region_id": f"KR-{i}"} for i in range(17)]}),
        encoding="utf-8",
    )
    assert tracker.load_cached_payload(missing_cats_file, validate=True, quarantine=False) is None

    # 17 regions with non-dict categories should fail validation
    bad_cats_file = tmp_path / "bad_cats.json"
    bad_cats_file.write_text(
        json.dumps({"regions": [{"region_id": f"KR-{i}", "categories": "corrupt"} for i in range(17)]}),
        encoding="utf-8",
    )
    assert tracker.load_cached_payload(bad_cats_file, validate=True, quarantine=False) is None

    # 17 valid regions with dict categories should pass validation
    valid_file = tmp_path / "valid.json"
    valid_file.write_text(
        json.dumps({"regions": [{"region_id": f"KR-{i}", "categories": {}} for i in range(17)]}),
        encoding="utf-8",
    )
    loaded = tracker.load_cached_payload(valid_file, validate=True, quarantine=False)
    assert loaded is not None
    assert len(loaded.regions) == 17


def test_payload_region_tier_filters_support_dict_status_and_depletion_rate_aliases(local_tracker):
    _sb, sm, _st = local_tracker
    payload = _minimal_payload_with_regions(sm, [
        {"region_id": "KR-27", "name_ko": "대구광역시", "status": "CRITICAL", "depletion_rate": 96.0},
        {"region_id": "KR-11", "name_ko": "서울특별시", "status": "WARNING", "depletion_rate": 85.0},
        {"region_id": "KR-26", "name_ko": "부산광역시", "status": "CAUTION", "depletion_rate": 70.0},
        {"region_id": "KR-36", "name_ko": "세종특별자치시", "depletion_rate": 97.5},
    ])

    critical_ids = [r.region_id for r in payload.get_critical_regions()]
    warning_ids = [r.region_id for r in payload.get_warning_regions()]
    healthy_ids = [r.region_id for r in payload.get_healthy_regions()]

    assert critical_ids == ["KR-27", "KR-36"]
    assert warning_ids == ["KR-11"]
    assert healthy_ids == ["KR-26"]


def test_build_initial_baseline_filters_none_regions(local_tracker):
    sb, _sm, _st = local_tracker
    baseline_regions = sb.build_baseline_regions()
    payload = sb.build_initial_baseline([baseline_regions[0], None, baseline_regions[1]])

    assert None not in payload.regions
    assert payload.total_regions() == 2
    assert payload.metadata.total_regions_tracked == 2
