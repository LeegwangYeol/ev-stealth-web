"""Targeted audit regression tests for subsidy tracker, baseline, models, and report generator."""

from __future__ import annotations

import math
from unittest import mock
import urllib.error
import urllib.request

import tracker.subsidy_tracker as subsidy_tracker_mod
from tracker.report_generator import ReportGenerator, _safe_sev, format_currency_krw, format_percentage
from tracker.subsidy_baseline import _calc_rate_percent, build_initial_baseline, calculate_net_subsidy
from tracker.subsidy_models import NationwideSummary, PopularModelEntry, RegionRecord, _safe_rate_percent
from tracker.subsidy_tracker import (
    _validate_endpoint_url,
    calculate_depletion_rate,
    calculate_pending_deliveries,
    calculate_remaining_units,
    calculate_waitlist_units,
    predict_exhaustion_date,
    predict_exhaustion_days,
)


def test_rate_percent_guards_none_str_bool_and_huge_int() -> None:
    assert _safe_rate_percent(None, 100) == 0.0
    assert _safe_rate_percent(100, None) == 0.0
    assert _safe_rate_percent("bad", 100) == 0.0
    assert _safe_rate_percent(True, 100) == 0.0
    assert _safe_rate_percent(100, True) == 0.0
    assert _safe_rate_percent(float("nan"), 100) == 0.0
    assert _safe_rate_percent(100, float("inf")) == 0.0
    assert _safe_rate_percent(10**400, 10**400) == 100.0
    assert _calc_rate_percent(None, 100) == 0.0
    assert _calc_rate_percent(10**400, 10**400) == 100.0
    assert calculate_depletion_rate(10**400, 10**400) == 100.0
    assert calculate_depletion_rate(10**400, 10**400, clamp_100=True) == 100.0


def test_predict_exhaustion_days_no_binary_float_drift() -> None:
    # 21.0 / 0.3 == 70.00000000000001 in IEEE-754 float, which drifted to 71
    assert predict_exhaustion_days(21, 0.3) == 70
    assert predict_exhaustion_days(2.1, 0.3) == 7
    assert predict_exhaustion_days(6.3, 0.9) == 7
    assert predict_exhaustion_days(100, 3) == 34
    assert predict_exhaustion_days(0, 0.3) == 0
    assert predict_exhaustion_days(10, 0) is None
    assert predict_exhaustion_days(10, True) is None
    assert predict_exhaustion_days(True, 10) is None
    assert predict_exhaustion_date(21, 0.3, start_date="2026-10-01t00:00:00z") == "2026-12-10"


def test_large_integer_strings_preserve_precision() -> None:
    big_quota = "100000000000000000001"
    big_applied = "100000000000000000000"
    assert calculate_remaining_units(big_applied, quota=big_quota) == 1
    assert calculate_waitlist_units(big_quota, quota=big_applied) == 1
    assert calculate_pending_deliveries(big_quota, big_applied) == 1


def test_calculate_net_subsidy_huge_ints_and_zero_ratio() -> None:
    res_zero = calculate_net_subsidy(6_500_000, 6_500_000, 1_500_000, 90_000_000)
    assert res_zero["price_cap_ratio"] == 0.0
    assert res_zero["total_subsidy_krw"] == 0
    assert res_zero["net_price_krw"] == 90_000_000

    huge = 10**309
    res_huge = calculate_net_subsidy(huge, huge * 2, huge, 70_000_000)
    assert res_huge["price_cap_ratio"] == 0.5
    assert res_huge["national_subsidy_krw"] == huge // 2
    assert res_huge["local_subsidy_krw"] > 0
    assert res_huge["net_price_krw"] == 0


def test_popular_model_entry_iso_to_korean_sample_lookup() -> None:
    model = PopularModelEntry(
        model_id="test-ev",
        name_ko="테스트 EV",
        manufacturer="현대",
        battery_type="NCM",
        battery_capacity_kwh=80.0,
        rated_range_km=450,
        base_price_krw=50_000_000,
        price_subsidy_ratio=1.0,
        national_subsidy_krw=6_000_000,
        regional_subsidy_samples={
            "서울특별시": {"local_subsidy_krw": 1_500_000},
            "KR-50": {"local_subsidy_krw": 2_500_000},
        },
    )
    assert model.get_regional_subsidy("KR-11") == 1_500_000
    assert model.get_regional_subsidy("KR-36") == 2_500_000


def test_nationwide_summary_comma_budget_properties() -> None:
    summary = NationwideSummary(
        total_announced_units=10,
        total_applied_units=5,
        total_delivered_units=4,
        total_remaining_units=5,
        nationwide_depletion_rate=50.0,
        total_budget_billion_krw="1,200.5",  # type: ignore[arg-type]
        disbursed_budget_billion_krw="600.2",  # type: ignore[arg-type]
        category_totals={},
        alert_region_counts={},
    )
    assert summary.total_budget_krw == 1_200_500_000_000
    assert summary.disbursed_budget_krw == 600_200_000_000


def test_build_initial_baseline_counts_region_record_without_categories() -> None:
    reg = RegionRecord(
        region_id="KR-27",
        name_ko="대구광역시",
        overall_depletion_rate=96.5,
        overall_status="",
        categories={},
    )
    payload = build_initial_baseline([reg])
    assert payload.nationwide_summary.alert_region_counts["critical"] == 1


def test_ssrf_endpoint_validation_blocks_internal_hosts_and_bad_inputs() -> None:
    blocked = [
        "",
        "ftp://example.com/data.json",
        "http://user:pass@example.com/data.json",
        "https://localhost/data.json",
        "https://ip6-localhost/data.json",
        "https://metadata.goog/computeMetadata/v1/",
        "https://169.254.169.254/latest/meta-data/",
        "https://100.64.0.1/internal",
        "https://[::ffff:127.0.0.1]/admin",
        "https://example.com:9999/data.json",
        "https://example.com/data\n.json",
    ]
    for url in blocked:
        ok, _ = _validate_endpoint_url(url)
        assert not ok, f"Expected SSRF validation to reject {url!r}"


def test_redirect_handler_resolves_relative_and_blocks_unsafe() -> None:
    handler = subsidy_tracker_mod._SafeEndpointRedirectHandler(allow_private_ips=False)
    req = urllib.request.Request("https://example.com/v1/data")
    try:
        handler.redirect_request(req, None, 302, "Found", {}, "//127.0.0.1/secret")
        assert False, "Expected HTTPError for protocol-relative loopback redirect"
    except urllib.error.HTTPError as exc:
        assert exc.code == 403

    rel_req = handler.redirect_request(req, None, 302, "Found", {}, "/v2/data")
    assert rel_req is not None
    assert rel_req.full_url == "https://example.com/v2/data"


def test_fetch_live_updates_attaches_dns_pinning_handlers() -> None:
    tracker = subsidy_tracker_mod.SubsidyTracker(endpoint_url="https://example.com/live.json", timeout_seconds=2.5)
    mock_resp = mock.MagicMock()
    mock_resp.status = 200
    mock_resp.geturl.return_value = "https://example.com/live.json"
    mock_resp.read.return_value = b'{"regions": []}'
    mock_resp.headers.get_content_charset.return_value = "utf-8"

    mock_opener = mock.MagicMock()
    mock_opener.open.return_value.__enter__.return_value = mock_resp

    with mock.patch("urllib.request.build_opener", return_value=mock_opener) as mock_build:
        res = tracker.fetch_live_updates(max_retries=1)
        assert res == {"regions": []}
        passed_handlers = mock_build.call_args[0]
        assert any(isinstance(h, subsidy_tracker_mod._SafeEndpointRedirectHandler) for h in passed_handlers)
        if (
            subsidy_tracker_mod._ResilientHTTPHandler is not None
            and subsidy_tracker_mod._ResilientHTTPSHandler is not None
        ):
            assert any(isinstance(h, subsidy_tracker_mod._ResilientHTTPHandler) for h in passed_handlers)
            assert any(isinstance(h, subsidy_tracker_mod._ResilientHTTPSHandler) for h in passed_handlers)


def test_report_generator_aliases_sanitization_and_formatters() -> None:
    gen = ReportGenerator()
    assert _safe_sev({"severity_index": "", "severity": "CRITICAL"}) == 10.0
    assert _safe_sev({"severity_index": True, "severity": "WARNING"}) == 0.0
    assert format_currency_krw(-0.0) == "0원"
    assert format_percentage(float("inf")) == "0.0%"

    briefing = gen.generate_subsidy_briefing(
        {
            "generated_at": "2026-11-23T00:00:00Z\n# INJECTED",
            "nationwide_summary": {"rate": 85.0},
            "regions": [{"name": "테스트시", "depletion_rate": 97.2}],
        },
        include_models=True,
    )
    assert "테스트시 (97.2%" in briefing
    assert "\n# INJECTED" not in briefing

    models_md = gen.generate_vehicle_subsidy_briefing(
        [
            {
                "manufacturer": "현대",
                "name_ko": "테스트차",
                "base_price": 50_000_000,
                "national_subsidy_krw": 6_000_000,
                "regional_subsidy_samples": {"seoul": {"local_subsidy_krw": 1_500_000}},
            }
        ],
        target_region="KR-11",
    )
    assert "5,000만 원 | 600만 원 | 150만 원 | 750만 원 | **4,250만 원**" in models_md

    defect_md = gen.generate_defect_briefing(
        {
            "generated_at": "2026-11-23\r\nBAD",
            "reports": [
                {"defect_category": "배터리\n주입", "severity": "CRITICAL", "title": "화재\r경고"}
            ],
        }
    )
    assert "\nBAD" not in defect_md
    assert "배터리 주입" in defect_md
    assert "화재 경고" in defect_md
