"""Regression tests for py-scrapers swarm audit (2026-11-28)."""

import json
import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.dcinside_scraper import DCInsideScraper, _is_truthy_flag


def test_is_truthy_flag_string_and_numeric_edge_cases():
    assert _is_truthy_flag(None) is False
    assert _is_truthy_flag(False) is False
    assert _is_truthy_flag(True) is True
    assert _is_truthy_flag(0) is False
    assert _is_truthy_flag(1) is True
    assert _is_truthy_flag(float("nan")) is False
    assert _is_truthy_flag(float("inf")) is False

    for falsy in ("", "   ", "0", "n", "N", "no", "NO", "false", "False", "none", "null"):
        assert _is_truthy_flag(falsy) is False

    for truthy in ("1", "y", "Y", "yes", "true", "True"):
        assert _is_truthy_flag(truthy) is True


def test_dcinside_fetch_comments_ajax_does_not_drop_string_false_is_delete():
    payload = {
        "comments": [
            {"memo": "충전기 통신 에러 너무 자주 발생합니다", "del_yn": "N", "is_delete": "0"},
            {"memo": "급속 충전기 튕김 현상 저도 겪었습니다", "del_yn": "n", "is_delete": "N"},
            {"memo": "완속 충전도 중간에 멈추는 경우가 있네요", "del_yn": "", "is_delete": "false"},
            {"memo": "이 댓글은 삭제된 댓글입니다", "del_yn": "N", "is_delete": "1"},
            {"memo": "이것도 삭제 처리된 댓글입니다", "del_yn": " y ", "is_delete": "0"},
            {"memo": "이 댓글 역시 boolean true 삭제입니다", "del_yn": "N", "is_delete": True},
        ]
    }
    mock_client = MagicMock()
    mock_client.request.return_value = (200, json.dumps(payload), b"")

    with DCInsideScraper(client=mock_client, cache_fallback=False) as scraper:
        comments = scraper.fetch_comments_ajax("electriccar", "12345", e_s_n_o="token123", is_minor=True)

    assert comments == [
        "충전기 통신 에러 너무 자주 발생합니다",
        "급속 충전기 튕김 현상 저도 겪었습니다",
        "완속 충전도 중간에 멈추는 경우가 있네요",
    ]
