"""
Regression tests for py-crawlers swarm audit (2026-11-28).
Covers:
1. _slice_to_last_close_tag Unicode case-expansion index shift (\u0130).
2. _extract_td_inner_by_class Unicode case-expansion index shift and </TD> matching.
3. _strip_elements_by_class O(N) linear scaling on unclosed matching tags + balanced semantics.
4. DCInsideCrawler.parse_gallery_list fallback regex when `no=` is the first query param.
"""

from __future__ import annotations

import time

from crawlers.base_crawler import _slice_to_last_close_tag, _strip_elements_by_class
from crawlers.bobaedream import BobaeDreamCrawler
from crawlers.dcinside import DCInsideCrawler, _extract_td_inner_by_class


def test_slice_to_last_close_tag_handles_unicode_lower_expansion():
    # '\u0130' ('İ') expands from 1 char to 2 chars under .lower()
    prefix = "İ" * 20
    html = f"<tr><td>{prefix}</td><td><a href='/view?code=national&No=123'>전기차 후기</a></td></tr>"
    sliced = _slice_to_last_close_tag(html, "</a")
    assert sliced.endswith("</a>")
    assert "전기차 후기" in sliced

    # Also test mixed case closing tag and non-'</' fallback
    html_upper = f"<div>{'İ' * 15}<A href='/x'>Title</A></div>"
    assert _slice_to_last_close_tag(html_upper, "</a").endswith("</A>")
    assert _slice_to_last_close_tag(html_upper, "title").endswith("Title</A>")


def test_bobaedream_parse_list_page_with_unicode_lower_expansion():
    crawler = BobaeDreamCrawler()
    try:
        # Without the fix, >=4 'İ' chars before the final </a> caused _slice_to_last_close_tag to return ""
        titles = " ".join(["İzmir İstanbul 전기차"] * 5)
        html = f"""
        <table>
          <tr><td><a href="/view?code=electric&No=98765">{titles}</a></td></tr>
        </table>
        """
        items = crawler.parse_list_page(html, "electric")
        assert len(items) == 1
        assert items[0]["post_id"] == "98765"
        assert "전기차" in items[0]["title"]
    finally:
        crawler.close()


def test_dcinside_extract_td_inner_and_gallery_list_with_unicode_lower_expansion():
    # Single 'İ' in gall_tit previously shifted td_start for gall_date and broke class="gall_date"
    row_html = (
        '<td class="gall_num">12345</td>'
        '<td class="gall_tit ub-word"><a href="/board/view/?id=car_new1&no=12345">İstanbul 전기차 주행기</a></td>'
        '<td class="gall_date" title="2026-11-28 03:30:00">03:30</TD>'
    )
    assert _extract_td_inner_by_class(row_html, "gall_date") == "03:30"

    crawler = DCInsideCrawler()
    try:
        html = f"""
        <table>
          <tr class="ub-content us-post" data-no="12345">
            {row_html}
          </tr>
          <tr class="ub-content us-post" data-no="12346">
            <td class="gall_num">12346</td>
            <td class="gall_tit ub-word"><a href="/board/view/?id=car_new1&no=12346">İİİİİ 두번째 글</a></td>
            <td class="gall_date">11.28</td>
          </tr>
        </table>
        """
        items = crawler.parse_gallery_list(html, "car_new1")
        assert len(items) == 2
        assert items[0]["post_id"] == "12345"
        assert items[0]["created_at"].startswith("2026-11-28T03:30:00")
        assert items[1]["post_id"] == "12346"
    finally:
        crawler.close()


def test_strip_elements_by_class_semantics_and_linear_time():
    # Balanced, nested, self-closing, and mixed unclosed/closed semantics
    assert (
        _strip_elements_by_class(
            '제목 <span class="reply_num">[<span>12</span>]</span> 끝',
            ("span", "em", "a"),
            "reply_num",
        )
        == "제목  끝"
    )
    assert (
        _strip_elements_by_class(
            '<span class="reply_num">A<span class="reply_num">B</span>C</span>keep',
            ("span",),
            "reply_num",
        )
        == "keep"
    )
    assert (
        _strip_elements_by_class(
            '<span class="reply_num">A<span class="reply_num">B</span>',
            ("span",),
            "reply_num",
        )
        == '<span class="reply_num">A'
    )

    # Pathological unclosed matching tags must run in linear O(N) time, not O(N^2)
    payload = '<span class="reply_num">' * 15000
    t0 = time.monotonic()
    result = _strip_elements_by_class(payload, ("span", "em", "a"), "reply_num")
    elapsed = time.monotonic() - t0
    assert result == payload
    assert elapsed < 0.5


def test_dcinside_parse_gallery_list_fallback_no_first_query_param():
    crawler = DCInsideCrawler()
    try:
        html = """
        <div class="list_wrap">
          <a href="https://gall.dcinside.com/board/view/?no=554433&id=car_new1">첫번째 파라미터가 no인 링크</a>
          <a href="/board/view?no=554434">no만 있는 링크</a>
          <a href="/board/view/?abcno=999999">오매칭 방지 링크</a>
        </div>
        """
        items = crawler.parse_gallery_list(html, "car_new1")
        post_ids = [it["post_id"] for it in items]
        assert post_ids == ["554433", "554434"]
        assert items[0]["title"] == "첫번째 파라미터가 no인 링크"
        assert items[1]["title"] == "no만 있는 링크"
    finally:
        crawler.close()
