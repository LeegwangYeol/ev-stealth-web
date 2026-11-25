"""Targeted 2026-11-26 regression tests for subsidy tracker and report generator."""

from __future__ import annotations

import socket
from unittest import mock
import urllib.request

from tracker.report_generator import ReportGenerator
import tracker.subsidy_tracker as subsidy_tracker_mod
from tracker.subsidy_tracker import (
    SubsidyTracker,
    _STANDARD_ENDPOINT_PORTS,
    _SafeEndpointRedirectHandler,
    _validate_endpoint_url,
)


def test_validate_endpoint_url_rejects_home_arpa_and_scoped_dns_ips() -> None:
    for url in (
        "https://svc.cluster.local/subsidy.json",
        "https://metadata.internal/api",
        "https://gateway.home.arpa/status",
    ):
        ok, _ = _validate_endpoint_url(url)
        assert not ok, f"Expected SSRF validation to reject {url!r}"

    scoped_addr = [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("fe80::1%en0", 0, 0, 14))]
    with mock.patch("socket.getaddrinfo", return_value=scoped_addr):
        ok_scoped, reason = _validate_endpoint_url("https://example.com/live.json")
        assert not ok_scoped
        assert "scoped" in reason.lower() or "unsafe" in reason.lower()


def test_redirect_handler_strips_referer_on_https_downgrade_and_fails_closed() -> None:
    handler = _SafeEndpointRedirectHandler(allow_private_ips=False)
    req = urllib.request.Request(
        "https://example.com/v1/data",
        headers={
            "Authorization": "Bearer secret",
            "Cookie": "sid=abc",
            "Referer": "https://example.com/private",
            "X-Custom": "keep",
        },
    )
    with mock.patch("socket.getaddrinfo", return_value=[]):
        downgrade_req = handler.redirect_request(
            req, None, 302, "Found", {}, "http://example.com/v2/data"
        )
        assert downgrade_req is not None
        assert downgrade_req.get_header("Authorization") is None
        assert downgrade_req.get_header("Cookie") is None
        assert downgrade_req.get_header("Referer") is None
        assert downgrade_req.get_header("X-custom") == "keep"

    # Directly verify fail-closed credential stripping when origin parsing errors inside redirect_request
    req_err = urllib.request.Request(
        "https://example.com/v1/data",
        headers={"Authorization": "Bearer secret", "Cookie": "sid=abc", "Referer": "https://example.com/p"},
    )
    real_urlsplit = urllib.parse.urlsplit
    call_count = 0

    def flaky_urlsplit(url: str, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if url == "https://example.com/v1/data":
            raise ValueError("forced parse failure")
        return real_urlsplit(url, *args, **kwargs)

    with mock.patch("socket.getaddrinfo", return_value=[]):
        with mock.patch("urllib.parse.urlsplit", side_effect=flaky_urlsplit):
            err_req = handler.redirect_request(req_err, None, 302, "Found", {}, "/v2/data")
            assert err_req is not None
            assert err_req.get_header("Authorization") is None
            assert err_req.get_header("Cookie") is None
            assert err_req.get_header("Referer") is None


def test_fetch_live_updates_configures_https_handler_allowed_ports() -> None:
    if (
        subsidy_tracker_mod._ResilientHTTPHandler is None
        or subsidy_tracker_mod._ResilientHTTPSHandler is None
    ):
        return

    tracker = SubsidyTracker(endpoint_url="https://example.com/live.json", allow_private_ips=False)
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
        https_handlers = [
            h for h in passed_handlers if isinstance(h, subsidy_tracker_mod._ResilientHTTPSHandler)
        ]
        assert len(https_handlers) == 1
        assert https_handlers[0]._allowed_ports == _STANDARD_ENDPOINT_PORTS


def test_fetch_live_updates_fails_closed_without_resilient_handlers() -> None:
    tracker = SubsidyTracker(endpoint_url="https://example.com/live.json", allow_private_ips=False)
    with mock.patch.object(subsidy_tracker_mod, "_ResilientHTTPHandler", None), \
         mock.patch.object(subsidy_tracker_mod, "_ResilientHTTPSHandler", None), \
         mock.patch("urllib.request.build_opener") as mock_build:
        res = tracker.fetch_live_updates(max_retries=1)
        assert res is None
        mock_build.assert_not_called()


def test_compute_nationwide_summary_supports_region_status_and_rate_aliases() -> None:
    tracker = SubsidyTracker()
    regions = [
        {"region_id": "KR-27", "status": "CRITICAL", "categories": {}},
        {"region_id": "KR-11", "depletion_rate": 85.0, "categories": {}},
        {"region_id": "KR-26", "overall_status": "", "depletion_rate": 100.0},
    ]
    summary = tracker.compute_nationwide_summary(regions)
    assert summary.alert_region_counts["critical"] == 1
    assert summary.alert_region_counts["warning"] == 1
    assert summary.alert_region_counts["depleted"] == 1


def test_report_generator_tuple_sequences_and_dsi_overflow_guard() -> None:
    gen = ReportGenerator()

    models_tuple = (
        {
            "manufacturer": "현대",
            "name_ko": "아이오닉 5",
            "base_price_krw": 50_000_000,
            "national_subsidy_krw": 6_500_000,
            "regional_subsidy_samples": {"seoul": {"local_subsidy_krw": 1_500_000}},
        },
    )
    models_md = gen.generate_vehicle_subsidy_briefing(models_tuple, target_region="KR-11")
    assert "아이오닉 5" in models_md
    assert "**4,200만 원**" in models_md

    reports_tuple = (
        {"defect_category": "ICCU", "severity": "CRITICAL", "title": "충전 불가"},
    )
    defect_md = gen.generate_defect_briefing(reports_tuple)
    assert "총 수집/분류 결함 건수**: 1건" in defect_md
    assert "ICCU" in defect_md

    huge_records = [
        {"vehicle_brand": "Test", "source": "forum", "defect_category": "ETC", "severity_index": 1e308},
        {"vehicle_brand": "Test", "source": "forum", "defect_category": "ETC", "severity_index": 1e308},
    ]
    stat_md = gen.generate_statistical_report(huge_records)
    assert "inf" not in stat_md.lower()
    assert "분석 표본수**: 총 2건" in stat_md
