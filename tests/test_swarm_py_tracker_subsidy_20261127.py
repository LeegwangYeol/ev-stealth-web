"""Targeted 2026-11-27 regression tests for py-tracker-subsidy slice."""

from __future__ import annotations

from decimal import Decimal
import socket
from unittest import mock
import urllib.error
import urllib.request

from tracker.report_generator import ReportGenerator, format_percentage
from tracker.subsidy_baseline import _calc_rate_percent
from tracker.subsidy_models import (
    CategoryMetrics,
    MunicipalityMetrics,
    NationwideSummary,
    RegionRecord,
    _safe_rate_percent,
)
from tracker.subsidy_tracker import (
    _SafeEndpointRedirectHandler,
    _validate_endpoint_url,
    calculate_depletion_rate,
    calculate_depletion_velocity,
)


def test_ssrf_rejects_internal_suffixes_invalid_dns_ip_and_redirect_control_chars() -> None:
    with mock.patch("socket.getaddrinfo", side_effect=socket.gaierror("offline")):
        for url in ("https://svc.cluster.local/api", "https://printer.home.arpa./status"):
            ok, _ = _validate_endpoint_url(url)
            assert not ok, f"Expected SSRF validation to reject {url!r}"

    bad_dns = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("not-an-ip", 0))]
    with mock.patch("socket.getaddrinfo", return_value=bad_dns):
        ok_bad, reason = _validate_endpoint_url("https://example.com/live.json")
        assert not ok_bad
        assert "invalid ip" in reason.lower()

    handler = _SafeEndpointRedirectHandler(allow_private_ips=False)
    req = urllib.request.Request(
        "https://example.com/v1/data",
        headers={"Host": "example.com", "Authorization": "Bearer secret", "X-Keep": "1"},
    )
    for bad_loc in ("/v2\r\n/data", "\nhttps://example.com/v2", "/v2\x00/data"):
        try:
            handler.redirect_request(req, None, 302, "Found", {}, bad_loc)
            assert False, f"Expected HTTPError for control-char redirect {bad_loc!r}"
        except urllib.error.HTTPError as exc:
            assert exc.code == 403

    with mock.patch("socket.getaddrinfo", return_value=[]):
        cross_req = handler.redirect_request(
            req, None, 302, "Found", {}, "https://other.example.org/v2"
        )
        assert cross_req is not None
        assert cross_req.get_header("Host") is None
        assert cross_req.get_header("Authorization") is None
        assert cross_req.get_header("X-keep") == "1"


def test_region_and_metrics_from_dict_treat_blank_strings_as_missing() -> None:
    reg = RegionRecord.from_dict(
        {
            "region_id": "KR-11",
            "overall_depletion_rate": "   ",
            "categories": {
                "passenger": {
                    "announced_units": 100,
                    "applied_units": 85,
                    "delivered_units": 50,
                    "remaining_units": "",
                    "depletion_rate": "",
                    "delivery_rate": " ",
                }
            },
            "municipalities": [
                {
                    "name_ko": "종로구",
                    "announced_units": 40,
                    "applied_units": 30,
                    "remaining_units": "",
                    "depletion_rate": "",
                }
            ],
        }
    )
    assert reg.overall_depletion_rate == 85.0
    assert reg.overall_status == "WARNING"
    p = reg.categories["passenger"]
    assert p.remaining_units == 15
    assert p.depletion_rate == 85.0
    assert p.delivery_rate == 50.0
    assert p.status == "WARNING"
    m = reg.municipalities[0]
    assert m.remaining_units == 10
    assert m.depletion_rate == 75.0

    summary = NationwideSummary.from_dict(
        {
            "total_announced_units": 200,
            "total_applied_units": 150,
            "total_remaining_units": "",
            "nationwide_depletion_rate": "",
            "total_budget_billion_krw": "",
            "total_budget_krw": 2_500_000_000,
            "disbursed_budget_billion_krw": " ",
            "disbursed_budget_krw": 1_200_000_000,
        }
    )
    assert summary.total_remaining_units == 50
    assert summary.nationwide_depletion_rate == 75.0
    assert summary.total_budget_billion_krw == 2.5
    assert summary.disbursed_budget_billion_krw == 1.2

    reg_dict_cat = RegionRecord(
        region_id="KR-11",
        overall_depletion_rate=10.0,
        categories={  # type: ignore[dict-item]
            "passenger": {
                "remaining_units": None,
                "remaining": 12,
                "depletion_rate": None,
                "rate": 42.5,
                "max_local_subsidy_krw": None,
                "local_subsidy_krw": 1_500_000,
                "max_total_subsidy_krw": None,
                "total_subsidy_krw": 8_000_000,
            }
        },
    )
    assert reg_dict_cat.get_remaining_units("passenger") == 12
    assert reg_dict_cat.get_depletion_rate("passenger") == 42.5
    assert reg_dict_cat.get_local_subsidy("passenger") == 1_500_000
    assert reg_dict_cat.get_total_subsidy("passenger") == 8_000_000


def test_depletion_rate_and_velocity_decimal_and_large_int_precision() -> None:
    assert calculate_depletion_rate(Decimal("1e400"), Decimal("2e400")) == 50.0
    assert calculate_depletion_rate("1e400", "2e400") == 50.0
    assert _safe_rate_percent(Decimal("1e400"), Decimal("2e400")) == 50.0
    assert _calc_rate_percent("1e400", "2e400") == 50.0
    assert calculate_depletion_rate(Decimal("1e400"), Decimal("10"), clamp_100=True) == 100.0
    assert calculate_depletion_rate(Decimal("1e400"), Decimal("10"), clamp_100=True, max_rate=80.0) == 80.0
    assert calculate_depletion_rate(Decimal("1e400"), Decimal("10"), clamp_100=False) == 0.0

    # Non-finite values must still return 0.0
    assert calculate_depletion_rate(float("inf"), 100, clamp_100=True) == 0.0
    assert calculate_depletion_rate(Decimal("Infinity"), Decimal("100"), clamp_100=True) == 0.0
    assert calculate_depletion_rate("inf", "100", clamp_100=True) == 0.0
    assert calculate_depletion_rate(Decimal("NaN"), Decimal("100")) == 0.0

    # Avoid float64 cancellation on large integer counters
    assert calculate_depletion_velocity(10**25, 10**25 + 300, 30) == 10.0
    assert calculate_depletion_velocity(
        Decimal("10000000000000000000000000000000000000000"),
        Decimal("10000000000000000000000000000000000000300"),
        30,
    ) == 10.0


def test_report_generator_summary_alias_status_sanitization_and_percentage_format() -> None:
    assert format_percentage(1000, decimals=0) == "1,000%"
    assert format_percentage(1e308, decimals=0).endswith("%")
    assert "," in format_percentage(1e308, decimals=0)

    gen = ReportGenerator()
    briefing = gen.generate_subsidy_briefing(
        {
            "summary": {
                "total_announced_units": 100,
                "total_applied_units": 85,
                "nationwide_depletion_rate": 85.0,
                "total_budget_billion_krw": 1e308,
                "disbursed_budget_billion_krw": 5e307,
                "category_totals": {
                    "passenger": {
                        "announced_units": 100,
                        "applied_units": 85,
                        "remaining_units": 15,
                        "depletion_rate": 85.0,
                        "status": "WARNING\n# INJECTED",
                    }
                },
            },
            "regions": [],
        }
    )
    assert "총 공고: 100대 / 접수: 85대" in briefing
    assert "\n# INJECTED" not in briefing
    assert "inf" not in briefing.lower()
