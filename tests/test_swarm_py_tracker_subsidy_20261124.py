"""Targeted 2026-11-24 audit regression tests for subsidy baseline, models, tracker, and report generator."""

from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
import tempfile
from unittest import mock
import urllib.error
import urllib.request

from tracker.report_generator import (
    ReportGenerator,
    _safe_int_val as rg_safe_int_val,
    format_currency_krw,
)
from tracker.subsidy_baseline import (
    _calc_rate_percent,
    _coerce_non_negative_int,
    _safe_int_val as sb_safe_int_val,
    build_initial_baseline,
    calculate_net_subsidy,
    calculate_price_cap_ratio,
)
from tracker.subsidy_models import (
    PopularModelEntry,
    _safe_int as sm_safe_int,
    _safe_rate_percent,
)
import tracker.subsidy_tracker as subsidy_tracker_mod
from tracker.subsidy_tracker import (
    SubsidyTracker,
    _SafeEndpointRedirectHandler,
    _safe_int_metric,
    _to_non_neg_int,
    _validate_endpoint_url,
    calculate_depletion_rate,
    classify_region_group,
    predict_exhaustion_date,
    predict_exhaustion_days,
)


def test_large_int_strings_and_decimal_coercion_preserve_precision() -> None:
    exact_21_digits = "100000000000000000001"
    expected_21 = 100_000_000_000_000_000_001
    huge_400 = "1" + "0" * 400
    expected_400 = 10**400

    for fn in (sb_safe_int_val, _coerce_non_negative_int, sm_safe_int, _safe_int_metric, _to_non_neg_int, rg_safe_int_val):
        assert fn(exact_21_digits) == expected_21
        assert fn(Decimal(exact_21_digits)) == expected_21
        assert fn(huge_400) == expected_400
        assert fn(Decimal("NaN")) in (0, None)
        assert fn(Decimal("Infinity")) in (0, None)
        assert fn(True) in (0, None)


def test_price_cap_ratio_and_net_subsidy_decimal_and_large_int_precision() -> None:
    assert calculate_price_cap_ratio("55,000,000") == 1.0
    assert calculate_price_cap_ratio("55000000.000000001") == 0.5
    assert calculate_price_cap_ratio(Decimal("55000000.000000001")) == 0.5
    assert calculate_price_cap_ratio("85000000.000000001") == 0.0
    assert calculate_price_cap_ratio(Decimal("85000000.000000001")) == 0.0
    assert calculate_price_cap_ratio(Decimal("NaN")) == 0.0

    # Product >= 2^52 must not suffer IEEE-754 float64 precision loss
    max_nat = 10_000_000_000
    model_nat = 10_000_000_000 - 1
    max_loc = 10_000_000_000
    res = calculate_net_subsidy(model_nat, max_nat, max_loc, 50_000_000)
    assert res["local_subsidy_krw"] == 9_999_999_999
    assert res["national_subsidy_krw"] == 9_999_999_999


def test_rate_percent_comma_strings_and_overflow_clamping() -> None:
    assert _calc_rate_percent("1,000", "2,000") == 50.0
    assert _safe_rate_percent("1,000", "2,000") == 50.0
    assert _calc_rate_percent("1" + "0" * 400, "2" + "0" * 400) == 50.0
    assert _safe_rate_percent("1" + "0" * 400, "2" + "0" * 400) == 50.0
    assert calculate_depletion_rate("1" + "0" * 400, "2" + "0" * 400) == 50.0

    # Overflowing numerator vs small quota must obey clamp_100=True and max_rate
    assert calculate_depletion_rate(10**400, 10, clamp_100=True) == 100.0
    assert calculate_depletion_rate(10**400, 0.5, clamp_100=True) == 100.0
    assert calculate_depletion_rate(10**400, 10, clamp_100=False) == 0.0
    assert calculate_depletion_rate(10**400, 10, clamp_100=True, max_rate=80.0) == 80.0


def test_predict_exhaustion_exact_ceiling_and_iso_space_datetime() -> None:
    # >28 significant digits: 3 * 10^29 + 1 divided by 3 must ceil to 10^29 + 1
    assert predict_exhaustion_days(3 * 10**29 + 1, 3) == 10**29 + 1
    assert predict_exhaustion_days(Decimal("21"), Decimal("0.3")) == 70
    assert predict_exhaustion_days(Decimal("NaN"), Decimal("1.0")) is None

    # Space-separated ISO datetime with Z or offset
    assert predict_exhaustion_date(21, 0.3, start_date="2026-10-01 12:00:00Z") == "2026-12-10"
    assert predict_exhaustion_date(10, 1.0, start_date="2026-10-01 12:00:00+09:00") == "2026-10-11"
    # Huge days causing timedelta overflow returns None cleanly
    assert predict_exhaustion_date(10**15, 0.1, start_date="2026-10-01") is None


def test_update_region_metrics_large_budget_no_float_drift() -> None:
    tracker = SubsidyTracker()
    region = {
        "region_id": "KR-TEST",
        "categories": {
            "passenger": {
                "announced_units": 100_000_000,
                "applied_units": 1,
                "delivered_units": 0,
                "total_budget_krw": 100_000_000_000,  # product = 1e19 > 2^53
            }
        },
    }
    updated = tracker.update_region_metrics(region)
    # remaining_units = 99_999_999, exact remaining budget = 99_999_999_000
    assert updated["categories"]["passenger"]["remaining_budget_krw"] == 99_999_999_000


def test_ssrf_local_suffix_idna_homograph_and_cross_origin_redirect_stripping() -> None:
    for bad_url in (
        "https://subsidy.default.svc.cluster.local/api",
        "https://ⓛⓞⓒⓐⓛⓗⓞⓢⓣ/admin",
        "https://foo.ⓛⓞⓒⓐⓛⓗⓞⓢⓣ/data.json",
    ):
        ok, _ = _validate_endpoint_url(bad_url)
        assert not ok, f"Expected SSRF validation to reject {bad_url!r}"

    handler = _SafeEndpointRedirectHandler(allow_private_ips=False)
    req = urllib.request.Request(
        "https://example.com/v1/data",
        headers={"Authorization": "Bearer secret", "Cookie": "sid=abc", "X-Custom": "keep"},
    )
    with mock.patch("socket.getaddrinfo", return_value=[]):
        same_origin_req = handler.redirect_request(req, None, 302, "Found", {}, "/v2/data")
        assert same_origin_req is not None
        assert same_origin_req.get_header("Authorization") == "Bearer secret"

        cross_origin_req = handler.redirect_request(req, None, 302, "Found", {}, "https://other.example.org/v2/data")
        assert cross_origin_req is not None
        assert cross_origin_req.get_header("Authorization") is None
        assert cross_origin_req.get_header("Cookie") is None
        assert cross_origin_req.get_header("X-custom") == "keep"


def test_load_cached_payload_rejects_oversized_file_without_oom() -> None:
    tracker = SubsidyTracker(quarantine_corrupted=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        big_file = Path(tmpdir) / "oversized.json"
        big_file.write_text("{}", encoding="utf-8")

        real_stat = Path.stat
        fake_stat = mock.MagicMock()
        fake_stat.st_size = subsidy_tracker_mod.MAX_CACHE_BYTES + 1
        fake_stat.st_mode = real_stat(big_file).st_mode

        with mock.patch.object(Path, "stat", return_value=fake_stat):
            with mock.patch.object(Path, "read_bytes", side_effect=AssertionError("Must not read oversized file")):
                res = tracker.load_cached_payload(big_file, validate=True, quarantine=False)
                assert res is None


def test_aliases_and_report_generator_decimal_and_sanitization() -> None:
    # Dict aliases in baseline & classify_region_group & PopularModelEntry.from_dict
    payload = build_initial_baseline([{"region_id": "KR-27", "depletion_rate": 96.5, "status": ""}])
    assert payload.nationwide_summary.alert_region_counts["critical"] == 1
    assert classify_region_group({"code": "KR-11", "name": "서울특별시"}) == "metropolitan_cities"
    assert classify_region_group({"code": "KR-41", "name": "경기도"}) == "provinces"

    model = PopularModelEntry.from_dict({"id": "m1", "samples": {"KR-11": {"local_subsidy_krw": 1_500_000}}})
    assert model.get_regional_subsidy("KR-11") == 1_500_000

    # Decimal currency formatting without float drift or InvalidOperation on huge ints
    assert format_currency_krw(1500, unit="man") == "0.2만 원"
    assert format_currency_krw(115_000_000) == "1.2억 원"
    assert "억 원" in format_currency_krw(10**35)

    # Markdown injection sanitization on target_region and bytearray guard in statistical report
    gen = ReportGenerator()
    table_md = gen.generate_vehicle_subsidy_briefing([], target_region="KR-99\n# INJECTED")
    assert "\n# INJECTED" not in table_md

    stat_md = gen.generate_statistical_report(bytearray(b"abc"))  # type: ignore[arg-type]
    assert "총 0건" in stat_md
