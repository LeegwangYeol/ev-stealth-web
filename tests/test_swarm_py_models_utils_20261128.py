"""Regression tests for py-models-utils audit fixes (2026-11-28)."""

from __future__ import annotations

import ssl
import time
from types import MappingProxyType
import typing
from unittest.mock import MagicMock, patch

import pytest

from models.complaint import (
    ComplaintRecord,
    DailyReportPayload,
    DailyReportStatistics,
    RawPost,
    quarantine_entry,
    validate_report_entry,
)
from utils.http_client import ResilientHTTPSConnection, SafeHttpClient, clean_html_text


def test_clean_html_text_no_redos_on_unclosed_script_or_style() -> None:
    """clean_html_text must handle large unclosed <script / <style tokens in linear time."""
    for tag in ("<script ", "<style "):
        payload = "<b>Hello</b>" + (tag * 30_000)
        start = time.monotonic()
        result = clean_html_text(payload)
        elapsed = time.monotonic() - start
        assert elapsed < 0.5, f"clean_html_text took {elapsed:.3f}s on unclosed {tag!r}"
        assert "Hello" in result

    pure_unclosed = "<script " * 30_000
    start = time.monotonic()
    clean_html_text(pure_unclosed)
    assert time.monotonic() - start < 0.5


def test_clean_html_text_preserves_script_and_style_stripping_semantics() -> None:
    """Closed and unclosed <script>/<style> tags with '>' must still strip their payloads."""
    assert clean_html_text("<p>Before</p><script>alert(1)</script><p>After</p>") == "Before\nAfter"
    assert clean_html_text("<p>Keep</p><style>.a{color:red}</style><span>Tail</span>") == "Keep\nTail"
    assert clean_html_text("<script>alert(1)</script> visible <script>alert(2)") == "visible"
    assert clean_html_text("<div>Safe</div><style>body{display:none") == "Safe"


def test_resilient_https_connection_closes_socket_on_wrap_failure() -> None:
    """If TLS wrap_socket or _tunnel fails, ResilientHTTPSConnection must close and clear self.sock."""
    mock_sock = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.wrap_socket.side_effect = ssl.SSLError("TLS handshake failed")

    conn = ResilientHTTPSConnection("example.com", 443, context=mock_ctx, allow_private_ips=True)
    with patch("utils.http_client._create_safe_connection", return_value=mock_sock):
        with pytest.raises(ssl.SSLError):
            conn.connect()

    mock_sock.close.assert_called_once()
    assert conn.sock is None


def test_safe_http_client_custom_ua_check_handles_non_str_keys_and_none_values() -> None:
    """Non-string header keys or None User-Agent values must not crash or disable UA rotation."""
    mock_resp = MagicMock()
    mock_resp.getcode.return_value = 200
    mock_resp.read.side_effect = [b"ok", b""]
    mock_resp.headers = {"Content-Type": "text/plain"}

    mock_opener = MagicMock()
    mock_opener.open.return_value = mock_resp

    client = SafeHttpClient(
        enable_jitter=False,
        enable_cache=False,
        opener=mock_opener,
        default_headers={"User-Agent": None, 123: "ignored"},
        allow_private_ips=True,
    )
    status, text, _ = client.get("http://127.0.0.1:8080/test", headers={456: "val"})
    assert status == 200
    assert text == "ok"


def test_raw_post_type_hints_and_mapping_support() -> None:
    """RawPost.__init__ type hints resolve cleanly and Mapping types work across model loaders."""
    hints = typing.get_type_hints(RawPost.__init__)
    assert "comments" in hints

    raw_proxy = MappingProxyType({
        "id": "p-1",
        "source": "clien",
        "title": "ICCU defect",
        "content": "Charging failed",
    })
    post = RawPost.from_dict(raw_proxy)
    assert post.post_id == "p-1"
    assert post.platform == "clien"
    assert post.title == "ICCU defect"

    ok, reason = validate_report_entry(raw_proxy, strict=True)
    assert ok, reason

    rec = ComplaintRecord.from_dict(raw_proxy, strict=True)
    assert rec.id == "p-1"
    assert rec.title == "ICCU defect"

    q = quarantine_entry(raw_proxy, "test")
    assert q["entry"]["id"] == "p-1"

    stats = DailyReportStatistics.from_dict(MappingProxyType({"total_scraped": 7, "total_filtered_defects": 3}))
    assert stats.total_scraped == 7
    assert stats.total_filtered_defects == 3

    payload = DailyReportPayload.from_dict(
        MappingProxyType({
            "generated_at": "2026-11-28T00:00:00+00:00",
            "statistics": MappingProxyType({"total_scraped": 1}),
            "reports": [raw_proxy],
            "top_defect_categories": [MappingProxyType({"category": "BATTERY_CHARGING", "count": 1, "ratio": 1.0})],
        })
    )
    assert len(payload.reports) == 1
    assert payload.reports[0]["id"] == "p-1"
    assert payload.statistics.total_scraped == 1
