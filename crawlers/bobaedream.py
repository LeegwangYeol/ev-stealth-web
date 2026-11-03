"""
BobaeDream Community Crawler & AJAX Comment Harvester.
Supports EUC-KR keyword encoding, list paging across national, import, electric,
and other community boards, article body extraction from bodyCont, dynamic AJAX comment
extraction from comment_list.php, entity decoding, anti-scraping resilience, and deleted post handling.
Returns structured raw post dictionaries adhering to PROJECT.md § Interface Contracts.
"""

from __future__ import annotations

import datetime
import html
import logging
import random
import re
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Set, Tuple

from crawlers.base_crawler import BaseCrawler
from utils.http_client import SafeHttpClient, clean_html_text, encode_euc_kr_query

logger = logging.getLogger("BobaeDreamCrawler")

BOBAE_BASE_URL = "https://www.bobaedream.co.kr"
BOBAE_LIST_URL = "https://www.bobaedream.co.kr/list"
BOBAE_VIEW_URL = "https://www.bobaedream.co.kr/view"

# Supported target boards
TARGET_BOARDS = {
    "national": "보배드림 국산차게시판",
    "import": "보배드림 수입차게시판",
    "electric": "보배드림 전기차게시판",
    "freeb": "보배드림 자유게시판",
    "battle": "보배드림 시승기/배틀/찍찍",
    "accident": "보배드림 교통사고/블랙박스",
    "cnews": "보배드림 자동차뉴스/토론",
    "best": "보배드림 베스트글",
}


def extract_container_content(html_str: str, tag_name: str, class_name: str) -> str:
    """
    Extract the inner content of an HTML container by tracking balanced tag depth.
    Resilient against nested tags of the same name, self-closing tags, and unclosed child tags.
    Supports double quotes, single quotes, and unquoted class names.
    """
    if not html_str or not isinstance(html_str, str):
        return ""
    pattern = re.compile(
        rf"<{tag_name}\b[^>]*class\s*=\s*(?:[\"'][^\"']*\b{re.escape(class_name)}\b[^\"']*[\"']|{re.escape(class_name)}(?=[\s>]))[^>]*>",
        re.IGNORECASE,
    )
    match = pattern.search(html_str)
    if not match:
        return ""

    start_idx = match.end()
    depth = 1
    tag_re = re.compile(rf"<(/?)({re.escape(tag_name)})\b([^>]*)>", re.IGNORECASE)

    for m in tag_re.finditer(html_str[start_idx:]):
        is_closing = bool(m.group(1))
        tag_attrs = m.group(3)
        if is_closing:
            depth -= 1
            if depth == 0:
                return html_str[start_idx : start_idx + m.start()]
        else:
            # Skip self-closing tags (e.g. <div ... />)
            if tag_attrs and tag_attrs.rstrip().endswith("/"):
                continue
            depth += 1

    return html_str[start_idx:]


def clean_title_text(raw_title: Optional[str]) -> str:
    """
    Sanitize and normalize post title:
    1. Strip HTML tags, comments, and scripts via clean_html_text.
    2. Decode HTML entities (&nbsp;, &amp;, &lt;, &gt;, &quot;, &#39;, etc.) including double-escaped entities.
    3. Normalize non-breaking spaces (\xa0), zero-width characters, and ideographic spaces.
    4. Collapse internal whitespace into single spaces and trim outer whitespace.
    """
    if not raw_title or not isinstance(raw_title, str):
        return ""

    # Initial HTML cleanup and unescaping
    text = clean_html_text(raw_title)
    if not text:
        return ""

    # Second unescape pass in case of double-encoded entities (e.g. &amp;lt; -> &lt; -> <)
    if "&" in text:
        text = html.unescape(text)

    # Normalize special whitespace characters
    # \xa0: NO-BREAK SPACE, \u200b: ZERO-WIDTH SPACE, \ufeff: BOM, \u3000: IDEOGRAPHIC SPACE
    text = (
        text.replace("\xa0", " ")
        .replace("\u200b", "")
        .replace("\ufeff", "")
        .replace("\u3000", " ")
        .replace("\x00", "")
    )

    # Collapse all whitespace and newlines into single spaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_deleted_or_restricted(html_content: Optional[str]) -> Tuple[bool, str]:
    """
    Check if BobaeDream HTML indicates the post is deleted, non-existent,
    restricted, member-only, or blocked by anti-scraping / WAF.
    Returns (True, reason) if inaccessible, else (False, "").
    """
    if not html_content or not isinstance(html_content, str) or not html_content.strip():
        return True, "empty_content"

    # 1. Cloudflare / Bot challenge / WAF blocking
    if "<title>Just a moment...</title>" in html_content or "cf-browser-verification" in html_content or "__cf_chl_" in html_content:
        return True, "cloudflare_challenge"
    if re.search(r"비정상적인\s*접근입니다", html_content):
        return True, "abnormal_access_blocked"
    if re.search(r"접근이\s*차단되었습니다", html_content):
        return True, "ip_blocked"
    if re.search(r"자동\s*방지\s*문자", html_content) or re.search(r"보안\s*문자를\s*입력", html_content):
        return True, "captcha_challenge"

    # 2. Check if page has actual substantial article body:
    # If a page contains a large bodyCont (> 50 chars), only alert(...) can indicate deletion
    has_large_body = False
    body_match = re.search(r'class=["\']bodyCont["\'][^>]*>(.*?)</div>', html_content, re.DOTALL | re.IGNORECASE)
    if body_match and len(clean_html_text(body_match.group(1))) > 50:
        has_large_body = True

    # Deleted or Non-existent posts
    deleted_patterns = [
        r"alert\s*\(\s*['\"][^'\"]*삭제된\s*게시물",
        r"alert\s*\(\s*['\"][^'\"]*존재하지\s*않는\s*게시물",
        r"alert\s*\(\s*['\"][^'\"]*삭제되었거나\s*존재하지\s*않는",
        r"alert\s*\(\s*['\"][^'\"]*해당\s*게시물이\s*(?:없|삭제)",
        r"alert\s*\(\s*['\"][^'\"]*삭제된\s*글",
        r"alert\s*\(\s*['\"][^'\"]*게시글이\s*삭제",
        r"삭제된\s*게시물입니다",
        r"존재하지\s*않는\s*게시물입니다",
        r"삭제되었거나\s*없는\s*게시물입니다",
        r"해당\s*게시물이\s*없습니다",
        r"요청하신\s*게시물을\s*찾을\s*수\s*없습니다",
        r"관리자에\s*의해\s*삭제된\s*게시글",
        r"작성자에\s*의해\s*삭제된\s*게시글",
    ]
    for pat in deleted_patterns:
        if has_large_body and not pat.startswith("alert"):
            continue
        if re.search(pat, html_content, re.IGNORECASE):
            return True, "deleted_post"

    # 3. Secret / Restricted / Member-only posts
    restricted_patterns = [
        r"alert\s*\(\s*['\"][^'\"]*비밀글입니다",
        r"alert\s*\(\s*['\"][^'\"]*작성자만\s*조회",
        r"alert\s*\(\s*['\"][^'\"]*로그인\s*[이후]?\s*(?:필요|이용|하십시오|하세요)",
        r"alert\s*\(\s*['\"][^'\"]*권한이\s*없습니다",
        r"alert\s*\(\s*['\"][^'\"]*접근\s*권한",
        r"alert\s*\(\s*['\"][^'\"]*성인\s*인증",
        r"비밀글\s*기능으로\s*보호된\s*글입니다",
        r"작성자만\s*조회할\s*수\s*있는\s*비밀글",
        r"로그인이\s*필요한\s*서비스입니다",
        r"로그인\s*후\s*이용\s*(?:가능|바랍니다|하십시오)",
        r"접근\s*권한이\s*없습니다",
        r"성인\s*인증이\s*필요한\s*게시물입니다",
    ]
    for pat in restricted_patterns:
        if has_large_body and not pat.startswith("alert"):
            continue
        if re.search(pat, html_content, re.IGNORECASE):
            return True, "restricted_post"

    return False, ""


def _normalize_iso_timestamp(raw_date_str: Optional[str]) -> str:
    """Normalize community timestamp into ISO-8601 string with UTC timezone."""
    if not raw_date_str or not isinstance(raw_date_str, str):
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    raw = raw_date_str.strip()
    if not raw:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    now = datetime.datetime.now(datetime.timezone.utc)

    # Case 0: Already ISO-8601 string with 'T' (e.g. "2026-09-08T10:15:00Z" or "2026-09-08T10:15:00")
    if "T" in raw:
        try:
            iso_clean = raw.replace("Z", "+00:00")
            dt = datetime.datetime.fromisoformat(iso_clean)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt.astimezone(datetime.timezone.utc).isoformat()
        except (ValueError, TypeError, OverflowError):
            pass

    # Case 1: Relative Korean formats
    # "방금", "방금 전", "방금전"
    if re.match(r"^방금(?:\s*전)?$", raw):
        return now.isoformat()

    # "X분 전", "X분전"
    min_match = re.match(r"^(\d+)\s*분\s*전$", raw)
    if min_match:
        try:
            mins = int(min_match.group(1))
            return (now - datetime.timedelta(minutes=mins)).isoformat()
        except (ValueError, OverflowError):
            return now.isoformat()

    # "X시간 전", "X시간전"
    hr_match = re.match(r"^(\d+)\s*시간\s*전$", raw)
    if hr_match:
        try:
            hrs = int(hr_match.group(1))
            return (now - datetime.timedelta(hours=hrs)).isoformat()
        except (ValueError, OverflowError):
            return now.isoformat()

    # "어제 [HH:MM[:SS]]"
    if raw.startswith("어제"):
        yesterday = now - datetime.timedelta(days=1)
        time_part = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", raw)
        if time_part:
            try:
                h = int(time_part.group(1))
                m = int(time_part.group(2))
                s = int(time_part.group(3)) if time_part.group(3) else 0
                return yesterday.replace(hour=h, minute=m, second=s, microsecond=0).isoformat()
            except (ValueError, OverflowError):
                return yesterday.isoformat()
        return yesterday.isoformat()

    # "그저께" or "X일 전"
    day_match = re.match(r"^(\d+)\s*일\s*전$", raw)
    if day_match:
        try:
            days = int(day_match.group(1))
            return (now - datetime.timedelta(days=days)).isoformat()
        except (ValueError, OverflowError):
            return now.isoformat()
    if raw == "그저께":
        return (now - datetime.timedelta(days=2)).isoformat()

    # Case 2: Time only "14:25" or "14:25:30" (Today's post)
    time_match = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", raw)
    if time_match:
        try:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            second = int(time_match.group(3)) if time_match.group(3) else 0
            dt = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
            return dt.isoformat()
        except (ValueError, OverflowError):
            return now.isoformat()

    # Case 2b: AM/PM or 오전/오후 time "오전 10:15" / "오후 02:30"
    ampm_time = re.match(r"^(오전|오후|AM|PM)\s*(\d{1,2}):(\d{2})(?::(\d{2}))?$", raw, re.IGNORECASE)
    if ampm_time:
        try:
            meridiem = ampm_time.group(1).upper()
            hour = int(ampm_time.group(2))
            minute = int(ampm_time.group(3))
            second = int(ampm_time.group(4)) if ampm_time.group(4) else 0
            if meridiem in ("오후", "PM") and hour < 12:
                hour += 12
            elif meridiem in ("오전", "AM") and hour == 12:
                hour = 0
            dt = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
            return dt.isoformat()
        except (ValueError, OverflowError):
            return now.isoformat()

    # Case 3: Korean format with 년, 월, 일: "2026년 9월 8일 10:15:00"
    kr_date = re.search(
        r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일(?:\s*(?:\([월화수목금토일A-Za-z]+\))?\s*(?:(오전|오후)\s*)?(\d{1,2}):(\d{2})(?::(\d{2}))?)?",
        raw,
    )
    if kr_date:
        try:
            y = int(kr_date.group(1))
            m = int(kr_date.group(2))
            d = int(kr_date.group(3))
            meridiem = kr_date.group(4)
            h = int(kr_date.group(5)) if kr_date.group(5) else 12
            if meridiem == "오후" and h < 12:
                h += 12
            elif meridiem == "오전" and h == 12:
                h = 0
            mi = int(kr_date.group(6)) if kr_date.group(6) else 0
            s = int(kr_date.group(7)) if kr_date.group(7) else 0
            dt = datetime.datetime(y, m, d, h, mi, s, tzinfo=datetime.timezone.utc)
            return dt.isoformat()
        except (ValueError, OverflowError):
            return now.isoformat()

    # Case 4: "YYYY-MM-DD HH:MM:SS" or "YYYY.MM.DD (화) HH:MM" or "YYYY.M.D"
    full_match = re.search(
        r"(\d{4})[./\-\s]+(\d{1,2})[./\-\s]+(\d{1,2})(?:[\sT]*(?:\([월화수목금토일A-Za-z]+\))?\s*(\d{1,2}):(\d{2})(?::(\d{2}))?)?",
        raw,
    )
    if full_match:
        try:
            year = int(full_match.group(1))
            month = int(full_match.group(2))
            day = int(full_match.group(3))
            hour = int(full_match.group(4)) if full_match.group(4) else 12
            minute = int(full_match.group(5)) if full_match.group(5) else 0
            second = int(full_match.group(6)) if full_match.group(6) else 0
            dt = datetime.datetime(year, month, day, hour, minute, second, tzinfo=datetime.timezone.utc)
            return dt.isoformat()
        except (ValueError, OverflowError):
            return now.isoformat()

    # Case 5: "YY/MM/DD [HH:MM[:SS]]"
    yymmdd_match = re.search(
        r"(\d{2})[./\-](\d{1,2})[./\-](\d{1,2})(?:[\sT]*(?:\([월화수목금토일A-Za-z]+\))?\s*(\d{1,2}):(\d{2})(?::(\d{2}))?)?",
        raw,
    )
    if yymmdd_match:
        try:
            yy = int(yymmdd_match.group(1))
            year = 2000 + yy if yy < 70 else 1900 + yy
            month = int(yymmdd_match.group(2))
            day = int(yymmdd_match.group(3))
            hour = int(yymmdd_match.group(4)) if yymmdd_match.group(4) else 12
            minute = int(yymmdd_match.group(5)) if yymmdd_match.group(5) else 0
            second = int(yymmdd_match.group(6)) if yymmdd_match.group(6) else 0
            dt = datetime.datetime(year, month, day, hour, minute, second, tzinfo=datetime.timezone.utc)
            return dt.isoformat()
        except (ValueError, OverflowError):
            return now.isoformat()

    # Case 6: "MM/DD [HH:MM[:SS]]" or "MM.DD [HH:MM]"
    month_day_match = re.match(
        r"^(\d{1,2})[./\-](\d{1,2})(?:[\sT]*(?:\([월화수목금토일A-Za-z]+\))?\s*(\d{1,2}):(\d{2})(?::(\d{2}))?)?$",
        raw,
    )
    if month_day_match:
        try:
            month = int(month_day_match.group(1))
            day = int(month_day_match.group(2))
            hour = int(month_day_match.group(3)) if month_day_match.group(3) else 12
            minute = int(month_day_match.group(4)) if month_day_match.group(4) else 0
            second = int(month_day_match.group(5)) if month_day_match.group(5) else 0
            year = now.year
            dt = datetime.datetime(year, month, day, hour, minute, second, tzinfo=datetime.timezone.utc)
            return dt.isoformat()
        except (ValueError, OverflowError):
            return now.isoformat()

    return now.isoformat()


class BobaeDreamCrawler(BaseCrawler):
    """
    Crawler for BobaeDream automotive community.
    Handles EUC-KR search queries, pagination across national/import/electric boards,
    body extraction from bodyCont, dynamic AJAX comment extraction, and anti-scraping resilience.
    """

    def __init__(
        self,
        client: Optional[SafeHttpClient] = None,
        min_delay: float = 1.5,
        max_delay: float = 3.5,
        max_retries: int = 3,
    ):
        if client is None:
            client = SafeHttpClient(min_delay=min_delay, max_delay=max_delay, max_retries=max_retries)
        super().__init__(client=client)
        self.min_delay = min_delay
        self.max_delay = max_delay

    def sleep_with_jitter(self, min_s: Optional[float] = None, max_s: Optional[float] = None) -> None:
        """Apply polite delay with uniform jitter between crawler requests."""
        low = min_s if min_s is not None else self.min_delay
        high = max_s if max_s is not None else self.max_delay
        if high > 0 and low <= high:
            time.sleep(random.uniform(low, high))

    def ensure_warm_up(self, base_url: Optional[str] = None, force: bool = False):
        """Warm up session cookies on BobaeDream base URL if not already done."""
        if isinstance(base_url, bool):
            force = base_url
            base_url = None
        target_url = base_url or BOBAE_BASE_URL
        if (not self._warmed_up or force) and target_url:
            try:
                if self.client and hasattr(self.client, "warm_up_session"):
                    self.client.warm_up_session(target_url)
            except Exception as e:
                logger.warning(f"BobaeDream warm_up_session notice: {e}")
            self._warmed_up = True

    def is_deleted_or_restricted(self, html_content: Optional[str]) -> Tuple[bool, str]:
        """Proxy check for deleted, restricted, or blocked pages."""
        return is_deleted_or_restricted(html_content)

    def build_search_url(
        self,
        board_code: str,
        keyword: str,
        page: int = 1,
        s_key: str = "sub_bod",
    ) -> str:
        """
        Build search URL with EUC-KR percent-encoded keyword parameter.
        URL format: https://www.bobaedream.co.kr/list?code={board_code}&s_cate=&s_key={s_key}&search={encoded_kw}&page={page}
        """
        code = str(board_code or "national").strip()
        try:
            eff_page = max(1, int(float(page)))
        except (ValueError, TypeError):
            eff_page = 1
        encoded_kw = encode_euc_kr_query(keyword or "")
        key = str(s_key or "sub_bod").strip()
        return (
            f"{BOBAE_LIST_URL}?code={code}&s_cate=&s_key={key}"
            f"&search={encoded_kw}&page={eff_page}"
        )

    def build_list_url(self, board_code: str, page: int = 1) -> str:
        """
        Build general list URL without search filters.
        URL format: https://www.bobaedream.co.kr/list?code={board_code}&page={page}
        """
        code = str(board_code or "national").strip()
        try:
            eff_page = max(1, int(float(page)))
        except (ValueError, TypeError):
            eff_page = 1
        return f"{BOBAE_LIST_URL}?code={code}&page={eff_page}"

    def parse_list_page(self, html_content: str, board_code: str) -> List[Dict[str, Any]]:
        """
        Extract post items from a BobaeDream board list view.
        Matches rows containing view links (/view?code=..., /view.php?code=..., /board/bbs_view/...).
        Resilient against single/double quotes, unquoted hrefs, HTML entities, and parameter order.
        Filters out notice and announcement posts while preserving genuine discussions.
        """
        if not html_content or not isinstance(html_content, str):
            return []

        # Check for Cloudflare challenge or bot block on list page
        is_blocked, reason = is_deleted_or_restricted(html_content)
        if is_blocked and reason in ("cloudflare_challenge", "abnormal_access_blocked", "ip_blocked", "captcha_challenge"):
            logger.warning(f"BobaeDream list page blocked by anti-scraping: {reason}")
            return []

        items: List[Dict[str, Any]] = []
        seen_nos = set()

        # Resilient link pattern matching desktop, PHP script, and mobile view URLs
        link_pattern = re.compile(
            r'<a\b[^>]*href=["\']?([^"\'\s>]*view(?:\.php)?\?[^"\'\s>]*|[^"\'\s>]*/(?:bbs_view|view)/[^"\'\s>]*)["\']?[^>]*>(.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        )

        for match in link_pattern.finditer(html_content):
            raw_href = match.group(1)
            raw_title = match.group(2)

            full_href = html.unescape(raw_href.strip())

            # Extract post_no from query param (No=, no=, b_no=, bm_no=) or path (/bbs_view/.../123, /view/123)
            no_match = re.search(
                r"(?:[?&](?:b_|bm_)?no=(\d+)|/(?:bbs_view/[^/]+/|view/)(\d+))",
                full_href,
                re.IGNORECASE,
            )
            if not no_match:
                continue
            post_no = no_match.group(1) or no_match.group(2)

            if post_no in seen_nos:
                continue
            seen_nos.add(post_no)

            # Extract board code from query param or path
            code_match = re.search(r"[?&]code=([a-zA-Z0-9_]+)", full_href, re.IGNORECASE)
            if not code_match:
                code_match = re.search(r"/(?:bbs_view|list)/([a-zA-Z0-9_]+)/", full_href, re.IGNORECASE)
            extracted_code = code_match.group(1) if code_match else board_code

            # Sanitize title, decode entities (&nbsp;, &amp;, &lt;, &gt;), trim whitespace
            clean_title = clean_title_text(raw_title)

            # Strip trailing comment count badges e.g. "(14)", "[28]" in list titles
            clean_title = re.sub(r"\s*[\[\(]\s*\d+\s*[\]\)]\s*$", "", clean_title).strip()

            # Filter out empty or notice (공지 / 필독 / 안내) titles
            if (
                not clean_title
                or len(clean_title) < 2
                or clean_title in ("공지", "필독", "안내")
                or clean_title.startswith(("[공지]", "공지 ", "[필독]", "필독 ", "[안내]", "안내 "))
                or "공지사항" in clean_title
                or "<b>공지</b>" in raw_title
                or '<b class="notice">' in raw_title
                or re.match(r"^\s*\[?(?:공지|필독|운영안내)\]?", clean_title)
            ):
                continue

            # Build canonical full URL
            if full_href.startswith("//"):
                full_url = f"https:{full_href}"
            elif full_href.startswith("http://") or full_href.startswith("https://"):
                full_url = full_href
            elif full_href.startswith("/"):
                full_url = f"{BOBAE_BASE_URL}{full_href}"
            else:
                full_url = f"{BOBAE_BASE_URL}/{full_href}"

            items.append({
                "post_id": post_no,
                "board_code": extracted_code,
                "url": full_url,
                "title": clean_title,
            })

        # Fallback regex if href parameters were ordered differently or single quotes
        if not items:
            alt_pattern = re.compile(
                r'<a\s+[^>]*href=["\']([^"\']*view(?:\.php)?[^"\']*No=(\d+)[^"\']*code=([^"\'&]+)[^"\']*)["\'][^>]*>(.*?)</a>',
                re.IGNORECASE | re.DOTALL,
            )
            for full_href_raw, post_no, code, raw_title in alt_pattern.findall(html_content):
                if post_no in seen_nos:
                    continue
                seen_nos.add(post_no)
                clean_title = clean_title_text(raw_title)
                clean_title = re.sub(r"\s*[\[\(]\s*\d+\s*[\]\)]\s*$", "", clean_title).strip()
                if (
                    not clean_title
                    or len(clean_title) < 2
                    or clean_title in ("공지", "필독", "안내")
                    or clean_title.startswith(("[공지]", "공지 ", "[필독]", "필독 ", "[안내]", "안내 "))
                    or "공지사항" in clean_title
                    or "<b>공지</b>" in raw_title
                    or '<b class="notice">' in raw_title
                    or re.match(r"^\s*\[?(?:공지|필독|운영안내)\]?", clean_title)
                ):
                    continue
                full_href = html.unescape(full_href_raw.strip())
                if full_href.startswith("//"):
                    full_url = f"https:{full_href}"
                elif full_href.startswith("http://") or full_href.startswith("https://"):
                    full_url = full_href
                elif full_href.startswith("/"):
                    full_url = f"{BOBAE_BASE_URL}{full_href}"
                else:
                    full_url = f"{BOBAE_BASE_URL}/{full_href}"
                items.append({
                    "post_id": post_no,
                    "board_code": code or board_code,
                    "url": full_url,
                    "title": clean_title,
                })

        return items

    def parse_comments_html(self, comment_html: str) -> List[str]:
        """Parse comment strings from comment_list.php HTML snippet or detail page HTML."""
        comments: List[str] = []
        if not comment_html or not isinstance(comment_html, str):
            return comments

        # Pattern 1: <dd id="cmt_..."> or <dd class="...comment...">
        comment_matches = re.findall(r'<dd[^>]*class=["\'][^"\']*comment[^"\']*["\'][^>]*>(.*?)</dd>', comment_html, re.DOTALL | re.IGNORECASE)
        if not comment_matches:
            comment_matches = re.findall(r'<dd id=["\']cmt_\d+["\'][^>]*>(.*?)</dd>', comment_html, re.DOTALL | re.IGNORECASE)
        if not comment_matches:
            # Pattern 2: comment body container
            comment_matches = re.findall(r'<div class=["\'][^"\']*comment_memo[^"\']*["\'][^>]*>(.*?)</div>', comment_html, re.DOTALL | re.IGNORECASE)
        if not comment_matches:
            comment_matches = re.findall(r'<li[^>]*class=["\'][^"\']*comment[^"\']*["\'][^>]*>(.*?)</li>', comment_html, re.DOTALL | re.IGNORECASE)

        for c_html in comment_matches:
            cleaned = clean_title_text(c_html)
            # Discard report links, delete notices, or tiny snippets
            if cleaned and len(cleaned) >= 2 and not cleaned.startswith("신고") and not cleaned.startswith("삭제된"):
                # Remove inline trailing metadata like "[답글] 2026.09.08"
                cleaned = re.sub(r"\[답글\]\s*\d+.*$", "", cleaned).strip()
                if cleaned:
                    comments.append(cleaned)

        return comments

    def extract_ajax_comment_url(self, html_content: str) -> Optional[str]:
        """
        Extract the dynamic AJAX comment URL from BobaeDream post detail HTML.
        Example in page:
          $("#cmt_list").load("/board_renew/bulletin/comment_list.php?tb=uni_cmt_2609&code=national&No=2415510&Answer=78...", ...)
        """
        if not html_content or not isinstance(html_content, str):
            return None

        # Match load("/board_renew/bulletin/comment_list.php?...") or load("http...")
        match = re.search(
            r'load\(["\'](?:https?://[^/"\']+)?(/(?:board_renew|board|bulletin)/[^"\']*comment_list\.php\?[^"\']+)["\']',
            html_content,
            re.IGNORECASE,
        )
        if match:
            path = html.unescape(match.group(1))
            return f"{BOBAE_BASE_URL}{path}" if path.startswith("/") else path

        # Alternative: match direct comment_list.php URL in any script or data attr
        alt_match = re.search(
            r'["\'](?:https?://[^/"\']+)?(/(?:board_renew|board|bulletin)/[^"\']*comment_list\.php\?[^"\']+)["\']',
            html_content,
            re.IGNORECASE,
        )
        if alt_match:
            path = html.unescape(alt_match.group(1))
            return f"{BOBAE_BASE_URL}{path}" if path.startswith("/") else path

        return None

    def fetch_ajax_comments(
        self,
        ajax_url: str,
        referer: str,
        timeout: Optional[float] = None,
    ) -> List[str]:
        """Fetch and parse dynamic comments from comment_list.php."""
        if not ajax_url or not isinstance(ajax_url, str):
            return []
        try:
            if not self.client:
                return []
            status, text, _ = self.client.get(
                ajax_url,
                referer=referer,
                headers={"X-Requested-With": "XMLHttpRequest"},
                timeout=timeout,
            )
            if status == 200 and text:
                return self.parse_comments_html(text)
        except Exception as e:
            logger.warning(f"Failed to fetch AJAX comments from {ajax_url}: {e}")
        return []

    def parse_post_detail(
        self,
        html_content: str,
        post_url: str,
        board_code: str = "national",
        post_id: str = "",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Extract article title, author, date, bodyCont content, and comments.
        Returns a dictionary adhering to PROJECT.md § Interface Contracts:
        {
          "platform": "bobaedream",
          "post_id": str,
          "url": str,
          "title": str,
          "content": str,
          "comments": list[str],
          "created_at": str (ISO-8601)
        }
        """
        # 1. Post ID extraction with multi-format fallback
        if (post_id is None or str(post_id).strip() == "") and post_url:
            no_match = re.search(
                r"(?:[?&](?:b_|bm_)?no=(\d+)|/(?:bbs_view/[^/]+/|view/)(\d+))",
                str(post_url),
                re.IGNORECASE,
            )
            post_id = (no_match.group(1) or no_match.group(2)) if no_match else ""

        # Extract board code from post_url if present
        if post_url:
            url_code_match = re.search(r"[?&]code=([a-zA-Z0-9_]+)", str(post_url), re.IGNORECASE)
            if not url_code_match:
                url_code_match = re.search(r"/(?:bbs_view|list)/([a-zA-Z0-9_]+)/", str(post_url), re.IGNORECASE)
            if url_code_match:
                board_code = url_code_match.group(1)

        if not html_content or not isinstance(html_content, str) or not html_content.strip():
            return {
                "platform": "bobaedream",
                "post_id": str(post_id) if post_id is not None else "",
                "url": post_url or "",
                "title": "",
                "content": "",
                "comments": [],
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "author": "",
                "board_code": board_code,
                "is_deleted": True,
                "status": "empty_content",
            }

        # Check for deleted / secret / restricted / Cloudflare challenge page
        is_blocked, block_reason = is_deleted_or_restricted(html_content)
        if is_blocked:
            return {
                "platform": "bobaedream",
                "post_id": str(post_id) if post_id is not None else "",
                "url": post_url or "",
                "title": "",
                "content": "",
                "comments": [],
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "author": "",
                "board_code": board_code,
                "is_deleted": block_reason == "deleted_post",
                "is_restricted": block_reason in ("restricted_post", "cloudflare_challenge", "abnormal_access_blocked", "ip_blocked", "captcha_challenge"),
                "status": block_reason,
            }

        # 2. Title - resilient against attribute order, tag structures, and entities
        title = ""
        title_match = re.search(r'<strong class=["\']title["\'][^>]*>(.*?)</strong>', html_content, re.DOTALL | re.IGNORECASE)
        if not title_match:
            title_match = re.search(r'<dt[^>]*class=["\']tit["\'][^>]*>(.*?)</dt>', html_content, re.DOTALL | re.IGNORECASE)
        if not title_match:
            title_match = re.search(r'<h[1-3][^>]*class=["\'][^"\']*title[^"\']*["\'][^>]*>(.*?)</h[1-3]>', html_content, re.DOTALL | re.IGNORECASE)
        if not title_match:
            title_match = re.search(r'<meta\b(?=[^>]*\bproperty=["\']og:title["\'])[^>]*\bcontent=["\']([^"\']*)["\']', html_content, re.IGNORECASE)
        if not title_match:
            title_match = re.search(r'<meta property=["\']og:title["\'] content=["\']([^"\']*)["\']', html_content, re.IGNORECASE)
        if not title_match:
            title_tag = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.DOTALL | re.IGNORECASE)
            if title_tag:
                clean_t = clean_title_text(title_tag.group(1))
                clean_t = re.sub(r"\s*-\s*보배드림.*$", "", clean_t).strip()
                if clean_t:
                    title = clean_t
        if title_match and not title:
            title = clean_title_text(title_match.group(1))

        # 3. Author & Date
        author = ""
        author_match = re.search(r'<span class=["\']author["\'][^>]*>(.*?)</span>', html_content, re.DOTALL | re.IGNORECASE)
        if not author_match:
            author_match = re.search(r'<span class=["\']userNick["\'][^>]*>(.*?)</span>', html_content, re.DOTALL | re.IGNORECASE)
        if not author_match:
            author_match = re.search(r'<dt class=["\']writer["\'][^>]*>(.*?)</dt>', html_content, re.DOTALL | re.IGNORECASE)
        if author_match:
            author = clean_title_text(author_match.group(1))

        raw_date = ""
        # Support <span>, <td>, <em>, or <div> containing class="date"
        date_match = re.search(r'<(?:span|td|em|div|p)\b[^>]*class=["\'][^"\']*\bdate\b[^"\']*["\'][^>]*>(.*?)</(?:span|td|em|div|p)>', html_content, re.DOTALL | re.IGNORECASE)
        if date_match:
            raw_date = clean_html_text(date_match.group(1))
        if not raw_date:
            generic_date = re.search(r'(\d{4}[.\-/]\d{2}[.\-/]\d{2}(?:[\sT]+\d{2}:\d{2}(?::\d{2})?)?)', html_content)
            if generic_date:
                raw_date = generic_date.group(1)

        created_at_iso = _normalize_iso_timestamp(raw_date)

        # 4. Article body from bodyCont (uses balanced container parser to preserve nested divs)
        content = ""
        body_extracted = extract_container_content(html_content, "div", "bodyCont")
        if body_extracted:
            content = clean_html_text(body_extracted).replace("\xa0", " ").strip()

        if not content:
            # Fallback 1: check with comment anchor
            body_match = re.search(r'<div class=["\']bodyCont["\'][^>]*>(.*?)</div>\s*<!--\s*//bodyCont', html_content, re.DOTALL | re.IGNORECASE)
            if not body_match:
                body_match = re.search(r'<div class=["\']bodyCont["\'][^>]*>(.*?)</div>', html_content, re.DOTALL | re.IGNORECASE)
            if not body_match:
                body_match = re.search(r'<div id=["\']print_area["\'][^>]*>(.*?)</div>', html_content, re.DOTALL | re.IGNORECASE)
            if not body_match:
                body_match = re.search(r'<div class=["\']content01["\'][^>]*>(.*?)</div>', html_content, re.DOTALL | re.IGNORECASE)
            if body_match:
                content = clean_html_text(body_match.group(1)).replace("\xa0", " ").strip()

        # 5. Comments (Static + Dynamic AJAX)
        comments: List[str] = []
        timeout = kwargs.get("timeout")
        ajax_cmt_url = self.extract_ajax_comment_url(html_content)
        if ajax_cmt_url:
            comments = self.fetch_ajax_comments(ajax_cmt_url, referer=post_url, timeout=timeout)

        # Fallback to static comments parsed from page HTML if AJAX gave nothing
        if not comments:
            comments = self.parse_comments_html(html_content)

        return {
            "platform": "bobaedream",
            "post_id": str(post_id) if post_id is not None else "",
            "url": post_url or "",
            "title": title,
            "content": content,
            "comments": comments,
            "created_at": created_at_iso,
            "author": author,
            "board_code": board_code,
        }

    def fetch_post(
        self,
        post_url: str,
        board_code: str = "national",
        post_id: Optional[str] = None,
        referer: Optional[str] = None,
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        """Fetch and parse a single post by URL with relative URL normalization and network safety."""
        if not post_url or not isinstance(post_url, str) or not post_url.strip():
            logger.warning(f"Invalid BobaeDream post_url provided: {post_url!r}")
            return None

        # Defensively normalize relative URLs and HTML entities (&amp; -> &)
        eff_url = html.unescape(post_url.strip())
        if eff_url.startswith("//"):
            eff_url = f"https:{eff_url}"
        elif eff_url.startswith("/"):
            eff_url = f"{BOBAE_BASE_URL}{eff_url}"
        elif not (eff_url.startswith("http://") or eff_url.startswith("https://")):
            eff_url = f"{BOBAE_BASE_URL}/{eff_url}"

        base_url = kwargs.get("base_url")
        self.ensure_warm_up(base_url)
        eff_referer = referer or f"{BOBAE_BASE_URL}/"
        timeout = kwargs.get("timeout")

        try:
            resp = self.client.get(eff_url, referer=eff_referer, timeout=timeout)
            if not resp or not isinstance(resp, (tuple, list)) or len(resp) < 2:
                logger.warning(f"Failed to fetch BobaeDream post: {eff_url} (empty or invalid response)")
                return None
            status, text = resp[0], resp[1]
        except Exception as e:
            logger.warning(f"Network error fetching BobaeDream post {eff_url}: {e}")
            return None

        if status != 200 or not text:
            logger.warning(f"Failed to fetch BobaeDream post: {eff_url} (status: {status})")
            return None

        # Check for deleted / restricted / Cloudflare challenge page
        is_blocked, block_reason = is_deleted_or_restricted(text)
        if is_blocked:
            logger.warning(f"BobaeDream post {eff_url} is unavailable ({block_reason})")
            return None

        try:
            detail = self.parse_post_detail(text, eff_url, board_code=board_code, post_id=post_id or "", **kwargs)
            if not isinstance(detail, dict):
                return None
            if detail.get("is_deleted") or detail.get("is_restricted"):
                return None
            return detail
        except Exception as e:
            logger.warning(f"Error parsing BobaeDream post detail ({eff_url}) on corrupt HTML: {e}")
            return None

    def crawl_board(
        self,
        board_code: str,
        pages: int = 1,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Crawl recent posts from a specific board without search keywords.
        Supported boards: national, import, electric, freeb, battle, accident, cnews.
        """
        if limit is not None and limit <= 0:
            return []

        try:
            eff_pages = max(1, int(float(pages)))
        except (ValueError, TypeError):
            eff_pages = 1

        self.ensure_warm_up()
        results: List[Dict[str, Any]] = []
        visited_nos: Set[str] = set()

        for page in range(1, eff_pages + 1):
            url = self.build_list_url(board_code, page=page)
            logger.info(f"Crawling BobaeDream [{board_code}] list (Page {page}): {url}")
            try:
                resp = self.client.get(url, referer=f"{BOBAE_BASE_URL}/")
                if not resp or not isinstance(resp, (tuple, list)) or len(resp) < 2:
                    logger.warning(f"Failed to fetch list for {board_code} page {page}")
                    break
                status, text = resp[0], resp[1]
            except Exception as e:
                logger.warning(f"Network dropout fetching list for {board_code} page {page}: {e}")
                break

            if status != 200 or not text:
                logger.warning(f"Failed to fetch list for {board_code} page {page} (status: {status})")
                break

            # Check if list page itself was blocked by anti-scraping
            is_blocked, block_reason = is_deleted_or_restricted(text)
            if is_blocked and block_reason in ("cloudflare_challenge", "abnormal_access_blocked", "ip_blocked", "captcha_challenge"):
                logger.warning(f"BobaeDream list page blocked by {block_reason} on page {page}")
                break

            items = self.parse_list_page(text, board_code)
            if not items:
                logger.info(f"No more items in BobaeDream [{board_code}] page {page}")
                break

            # Pagination loop detection: if all items on this page were already seen, stop
            page_nos = {it["post_id"] for it in items if it.get("post_id")}
            if page_nos and page_nos.issubset(visited_nos):
                logger.info(f"Page {page} of [{board_code}] repeated previously seen posts. Halting pagination loop.")
                break
            visited_nos.update(page_nos)

            for item in items:
                post = self.fetch_post(
                    item.get("url", ""),
                    board_code=board_code,
                    post_id=item.get("post_id", ""),
                    referer=url,
                )
                if post:
                    results.append(post)
                    if limit and len(results) >= limit:
                        return results

        return results

    def search_board(
        self,
        board_code: str,
        keyword: str,
        pages: int = 1,
        limit: Optional[int] = None,
        s_key: str = "sub_bod",
    ) -> List[Dict[str, Any]]:
        """
        Search a specific BobaeDream board with an EUC-KR encoded query.
        """
        if limit is not None and limit <= 0:
            return []

        try:
            eff_pages = max(1, int(float(pages)))
        except (ValueError, TypeError):
            eff_pages = 1

        self.ensure_warm_up()
        results: List[Dict[str, Any]] = []
        visited_nos: Set[str] = set()

        for page in range(1, eff_pages + 1):
            url = self.build_search_url(board_code, keyword, page=page, s_key=s_key)
            logger.info(f"Searching BobaeDream [{board_code}] for '{keyword}' (Page {page}): {url}")
            try:
                resp = self.client.get(url, referer=f"{BOBAE_BASE_URL}/")
                if not resp or not isinstance(resp, (tuple, list)) or len(resp) < 2:
                    logger.warning(f"Search request failed for {board_code} keyword '{keyword}' page {page}")
                    break
                status, text = resp[0], resp[1]
            except Exception as e:
                logger.warning(f"Network dropout during search for {board_code} keyword '{keyword}' page {page}: {e}")
                break

            if status != 200 or not text:
                logger.warning(f"Search request failed for {board_code} keyword '{keyword}' page {page} (status: {status})")
                break

            # Check if search page was blocked by anti-scraping
            is_blocked, block_reason = is_deleted_or_restricted(text)
            if is_blocked and block_reason in ("cloudflare_challenge", "abnormal_access_blocked", "ip_blocked", "captcha_challenge"):
                logger.warning(f"BobaeDream search page blocked by {block_reason} on page {page}")
                break

            items = self.parse_list_page(text, board_code)
            if not items:
                logger.info(f"No search results found in {board_code} for '{keyword}' page {page}")
                break

            # Pagination loop detection
            page_nos = {it["post_id"] for it in items if it.get("post_id")}
            if page_nos and page_nos.issubset(visited_nos):
                logger.info(f"Search page {page} of [{board_code}] repeated previously seen posts. Halting loop.")
                break
            visited_nos.update(page_nos)

            for item in items:
                post = self.fetch_post(
                    item.get("url", ""),
                    board_code=board_code,
                    post_id=item.get("post_id", ""),
                    referer=url,
                )
                if post:
                    results.append(post)
                    if limit and len(results) >= limit:
                        return results

        return results

    def crawl_posts_by_keyword(
        self,
        keyword: str,
        boards: Optional[List[str]] = None,
        max_pages: int = 1,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search across target boards (national, import, electric) for a given keyword.
        """
        if limit is not None and limit <= 0:
            return []

        target_boards = list(boards) if boards is not None else ["national", "import", "electric"]
        all_posts: List[Dict[str, Any]] = []

        for board in target_boards:
            remaining_limit = (limit - len(all_posts)) if limit is not None else None
            board_posts = self.search_board(board, keyword, pages=max_pages, limit=remaining_limit)
            all_posts.extend(board_posts)
            if limit and len(all_posts) >= limit:
                return all_posts[:limit]

        return all_posts


# Standard alias matching alternate naming conventions
BobaedreamCrawler = BobaeDreamCrawler
