"""Targeted 2026-11-25 regression tests for subsidy models, baseline, tracker, and report generator."""

from __future__ import annotations

from decimal import Decimal

from tracker.report_generator import (
    _format_scaled_unit,
    format_currency_krw,
    format_percentage,
)
from tracker.subsidy_baseline import build_initial_baseline
from tracker.subsidy_models import (
    AlertSeverity,
    PopularModelEntry,
    RegionRecord,
    _safe_float,
)
from tracker.subsidy_tracker import (
    SubsidyTracker,
    _to_non_neg_int,
    _validate_endpoint_url,
)


def test_safe_float_guards_oversized_int_without_overflow() -> None:
    assert _safe_float(10**400, default=0.0) == 0.0
    assert _safe_float(-(10**400), default=5.5) == 5.5
    assert _safe_float(-0) == 0.0
    assert AlertSeverity.from_rate(10**400) == AlertSeverity.HEALTHY
    rec = RegionRecord.from_dict({"region_id": "KR-11", "overall_depletion_rate": 10**400})
    assert rec.overall_depletion_rate == 0.0


def test_popular_model_entry_decimal_sample_support() -> None:
    model = PopularModelEntry(
        model_id="dec-ev",
        name_ko="테스트 EV",
        manufacturer="현대",
        battery_type="NCM",
        battery_capacity_kwh=80.0,
        rated_range_km=450,
        base_price_krw=50_000_000,
        price_subsidy_ratio=1.0,
        national_subsidy_krw=6_000_000,
        regional_subsidy_samples={"KR-11": Decimal("1500000")},  # type: ignore[dict-item]
    )
    assert model.get_regional_subsidy("KR-11") == 1_500_000


def test_to_non_neg_int_returns_none_on_malformed_or_oversized_strings() -> None:
    assert _to_non_neg_int("bad") is None
    assert _to_non_neg_int("") is None
    assert _to_non_neg_int(object()) is None
    assert _to_non_neg_int("1" + "0" * 5000) is None
    assert _to_non_neg_int("  1,234 ") == 1234


def test_validate_endpoint_url_rejects_whitespace_in_hostname() -> None:
    ok, _ = _validate_endpoint_url("https://exa mple.com/api")
    assert not ok
    ok_unicode, _ = _validate_endpoint_url("https://example\u2000.com/api")
    assert not ok_unicode


def test_huge_budget_sum_does_not_overflow_billion_conversion() -> None:
    huge_region = {
        "region_id": "KR-11",
        "categories": {
            "passenger": {
                "announced_units": 100,
                "applied_units": 50,
                "delivered_units": 25,
                "total_budget_krw": 10**320,
                "remaining_budget_krw": 0,
            }
        },
    }
    payload = build_initial_baseline([huge_region])
    assert payload.nationwide_summary.total_budget_billion_krw == 0.0
    assert payload.nationwide_summary.disbursed_budget_billion_krw == 0.0

    tracker = SubsidyTracker()
    summary = tracker.compute_nationwide_summary([huge_region])
    assert summary.total_budget_billion_krw == 0.0
    assert summary.disbursed_budget_billion_krw == 0.0


def test_report_generator_extreme_decimal_and_precision_guards() -> None:
    assert format_currency_krw(Decimal("1e20000"), unit="billion") == "0억 원"
    assert format_currency_krw(Decimal("-1e-20000"), unit="billion") == "0억 원"
    res_4500 = format_currency_krw(Decimal("1e4500"))
    assert res_4500.endswith("억 원")
    assert "inf" not in res_4500.lower()

    res_billion_4500 = format_currency_krw(Decimal("1e4500"), unit="billion")
    assert res_billion_4500.endswith("억 원")
    assert "inf" not in res_billion_4500.lower()

    assert _format_scaled_unit(float("nan"), "억 원") == "0억 원"
    assert _format_scaled_unit(float("inf"), "만 원") == "0만 원"

    pct = format_percentage(12.345, decimals=10**9)
    assert pct.endswith("%")
    assert len(pct) < 32
