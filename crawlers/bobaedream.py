"""
BobaeDream Community Crawler & AJAX Comment Harvester.
Supports EUC-KR keyword encoding, list paging across national, import, electric,
and other community boards, article body extraction from bodyCont, dynamic AJAX comment
extraction from comment_list.php, entity decoding, anti-scraping resilience, and deleted post handling.
Returns structured raw post dictionaries adhering to PROJECT.md § Interface Contracts.
"""

from __future__ import annotations

from collections import OrderedDict
import datetime
import html
import logging
import math
import random
import re
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from crawlers.base_crawler import (
    BaseCrawler,
    _has_unsafe_authority,
    _is_safe_client_url,
    _mask_comments_and_scripts,
    _normalize_limit,
    _normalize_pages,
    _positive_float,
    _sanitize_referer,
    _slice_to_last_close_tag,
    _unescape_url_entities,
)
from utils.http_client import SafeHttpClient, clean_html_text, encode_euc_kr_query, robust_decode

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


RE_HTML_COMMENTS = re.compile(r"<!--.*?-->", re.DOTALL)
RE_SCRIPT_STYLE = re.compile(r"<(script|style)[^>]*>.*?</\1\s*>", re.DOTALL | re.IGNORECASE)
RE_COMMENT_OR_SCRIPT = re.compile(
    r"<!--.*?-->|<(script|style)\b[^>]*>.*?</\1\s*>",
    re.DOTALL | re.IGNORECASE,
)


def _canonicalize_bobaedream_href(raw_href: str) -> Optional[str]:
    """Validate and canonicalize a BobaeDream href, blocking unsafe schemes and external hosts."""
    if not raw_href or not isinstance(raw_href, str):
        return None
    full_href = _unescape_url_entities(raw_href.strip()).strip()
    if not full_href or any(ord(c) < 32 or ord(c) == 127 for c in full_href):
        return None
    try:
        parsed_in = urllib.parse.urlsplit(full_href)
    except ValueError:
        return None
    if parsed_in.scheme:
        if parsed_in.scheme.lower() not in ("http", "https"):
            return None
        if not full_href.lower().startswith(("http://", "https://")):
            return None

    if full_href.startswith("//"):
        full_url = f"https:{full_href}"
    elif full_href.lower().startswith(("http://", "https://")):
        full_url = full_href
    elif full_href.startswith("/"):
        full_url = f"{BOBAE_BASE_URL}{full_href}"
    else:
        full_url = f"{BOBAE_BASE_URL}/{full_href}"

    try:
        parsed_out = urllib.parse.urlsplit(full_url)
        port = parsed_out.port
    except ValueError:
        return None
    if not parsed_out.hostname or any(c.isspace() for c in (parsed_out.netloc or "")):
        return None
    if _has_unsafe_authority(parsed_out):
        return None
    host = (parsed_out.hostname or "").lower().rstrip(".")
    if not (host == "bobaedream.co.kr" or host.endswith(".bobaedream.co.kr")):
        return None
    if port not in (None, 80, 443):
        return None
    return full_url


def extract_container_content(html_str: str, tag_name: str, class_name: str) -> str:
    """
    Extract the inner content of an HTML container by tracking balanced tag depth.
    Resilient against nested tags of the same name, self-closing tags, unclosed child tags,
    and dummy closing tags inside HTML comments or scripts.
    Supports double quotes, single quotes, and unquoted class names.
    """
    if not html_str or not isinstance(html_str, str) or not tag_name or not class_name:
        return ""

    # Mask comments and scripts with equal-length whitespace in a single left-to-right pass
    # so dummy tags or comment tokens inside scripts do not corrupt offsets or depth counters.
    masked = _mask_comments_and_scripts(html_str)

    cls_esc = re.escape(class_name)
    pattern = re.compile(
        rf"<{re.escape(tag_name)}\b[^>]*?(?<=\s)class\s*=\s*(?:[\"'](?:[^\"']*\s)?{cls_esc}(?:\s[^\"']*)?[\"']|{cls_esc}(?=[\s>]))[^>]*>",
        re.IGNORECASE,
    )
    match = pattern.search(masked)
    if not match:
        return ""
    if match.group(0).rstrip(">").rstrip().endswith("/"):
        return ""

    start_idx = match.end()
    depth = 1
    tag_re = re.compile(rf"<(/?)({re.escape(tag_name)})\b([^>]*)>", re.IGNORECASE)

    for m in tag_re.finditer(masked, start_idx):
        is_closing = bool(m.group(1))
        tag_attrs = m.group(3)
        if is_closing:
            depth -= 1
            if depth == 0:
                return html_str[start_idx : m.start()]
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

    # 1. Unconditional Cloudflare challenge & explicit HTTP error title blocks
    if (
        "<title>Just a moment...</title>" in html_content
        or "cf-browser-verification" in html_content
        or "__cf_chl_" in html_content
        or "challenges.cloudflare.com" in html_content
    ):
        return True, "cloudflare_challenge"
    if re.search(r"<title>\s*(?:403\s+Forbidden|429\s+Too\s+Many\s+Requests|Access\s+Denied)\s*</title>", html_content, re.IGNORECASE):
        return True, "access_denied"

    # 2. Check if page has actual substantial article body:
    # If a page contains a large article body (> 50 chars), only alert(...) or explicit error titles indicate blocking/deletion
    masked_html = _mask_comments_and_scripts(html_content)
    has_large_body = False
    for body_cls in ("bodyCont", "content01"):
        body_inner = extract_container_content(html_content, "div", body_cls)
        if body_inner and len(clean_html_text(body_inner)) > 50:
            has_large_body = True
            break
    if not has_large_body:
        body_match = re.search(r'(?<=\s)class=["\']bodyCont["\'][^>]*>(.*?)</div>', masked_html, re.DOTALL | re.IGNORECASE)
        if not body_match:
            body_match = re.search(r'<div\b[^>]*?(?<=\s)id=["\']print_area["\'][^>]*>(.*?)</div>', masked_html, re.DOTALL | re.IGNORECASE)
        body_inner = body_match.group(1) if body_match else ""
        if body_inner and len(clean_html_text(body_inner)) > 50:
            has_large_body = True

    if not has_large_body:
        if re.search(r"(?:비정상적인|잘못된)\s*(?:접근|요청)입니다", masked_html, re.IGNORECASE):
            return True, "abnormal_access_blocked"
        if re.search(r"(?:접근이\s*차단되었습니다|(?:차단된|제한된)\s*(?:아이피|IP))", masked_html, re.IGNORECASE):
            return True, "ip_blocked"
        if re.search(r"(?:자동\s*방지\s*문자|보안\s*문자를\s*입력|reCAPTCHA|hCaptcha)", masked_html, re.IGNORECASE):
            return True, "captcha_challenge"
        if re.search(r"(?:서비스\s*점검\s*중|시스템\s*점검\s*중)", masked_html, re.IGNORECASE):
            return True, "service_maintenance"

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
        is_alert = pat.startswith("alert")
        if has_large_body and not is_alert:
            continue
        target_str = html_content if is_alert else masked_html
        if re.search(pat, target_str, re.IGNORECASE):
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
        is_alert = pat.startswith("alert")
        if has_large_body and not is_alert:
            continue
        target_str = html_content if is_alert else masked_html
        if re.search(pat, target_str, re.IGNORECASE):
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

    # Case 0: Already ISO-8601 string (e.g. "2026-09-08T10:15:00Z" or "2026-09-08 10:15:00+09:00")
    if "T" in raw or (raw.count("-") >= 2 and ":" in raw):
        try:
            iso_clean = re.sub(r"[zZ]$", "+00:00", raw)
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

    # "어제 [(오전|오후|AM|PM) HH:MM[:SS]]"
    if raw.startswith("어제"):
        yesterday = now - datetime.timedelta(days=1)
        time_part = re.search(r"(?:(오전|오후|AM|PM)\s*)?(\d{1,2}):(\d{2})(?::(\d{2}))?", raw, re.IGNORECASE)
        if time_part:
            try:
                meridiem = time_part.group(1).upper() if time_part.group(1) else None
                h = int(time_part.group(2))
                if meridiem in ("오후", "PM") and h < 12:
                    h += 12
                elif meridiem in ("오전", "AM") and h == 12:
                    h = 0
                m = int(time_part.group(3))
                s = int(time_part.group(4)) if time_part.group(4) else 0
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
        r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일(?:\s*(?:\([월화수목금토일A-Za-z]+\))?\s*(?:(오전|오후|AM|PM)\s*)?(\d{1,2}):(\d{2})(?::(\d{2}))?)?",
        raw,
        re.IGNORECASE,
    )
    if kr_date:
        try:
            y = int(kr_date.group(1))
            m = int(kr_date.group(2))
            d = int(kr_date.group(3))
            meridiem = kr_date.group(4).upper() if kr_date.group(4) else None
            h = int(kr_date.group(5)) if kr_date.group(5) else 12
            if meridiem in ("오후", "PM") and h < 12:
                h += 12
            elif meridiem in ("오전", "AM") and h == 12:
                h = 0
            mi = int(kr_date.group(6)) if kr_date.group(6) else 0
            s = int(kr_date.group(7)) if kr_date.group(7) else 0
            dt = datetime.datetime(y, m, d, h, mi, s, tzinfo=datetime.timezone.utc)
            return dt.isoformat()
        except (ValueError, OverflowError):
            return now.isoformat()

    # Case 4: "YYYY-MM-DD HH:MM:SS" or "YYYY.MM.DD (화) 오후 HH:MM" or "YYYY.M.D"
    full_match = re.search(
        r"(?<!\d)(\d{4})[./\-\s]+(\d{1,2})[./\-\s]+(\d{1,2})\.?(?:[\sT]*(?:\([월화수목금토일A-Za-z]+\))?\s*(?:(오전|오후|AM|PM)\s*)?(\d{1,2}):(\d{2})(?::(\d{2}))?)?",
        raw,
        re.IGNORECASE,
    )
    if full_match:
        try:
            year = int(full_match.group(1))
            month = int(full_match.group(2))
            day = int(full_match.group(3))
            meridiem = full_match.group(4).upper() if full_match.group(4) else None
            hour = int(full_match.group(5)) if full_match.group(5) is not None else 12
            if meridiem in ("오후", "PM") and hour < 12:
                hour += 12
            elif meridiem in ("오전", "AM") and hour == 12:
                hour = 0
            minute = int(full_match.group(6)) if full_match.group(6) is not None else 0
            second = int(full_match.group(7)) if full_match.group(7) is not None else 0
            dt = datetime.datetime(year, month, day, hour, minute, second, tzinfo=datetime.timezone.utc)
            return dt.isoformat()
        except (ValueError, OverflowError):
            return now.isoformat()

    # Case 5: "YY/MM/DD [오전/오후] [HH:MM[:SS]]"
    yymmdd_match = re.search(
        r"(?<!\d)(\d{2})[./\-](\d{1,2})[./\-](\d{1,2})(?!\.\d)(?:[\sT]*(?:\([월화수목금토일A-Za-z]+\))?\s*(?:(오전|오후|AM|PM)\s*)?(\d{1,2}):(\d{2})(?::(\d{2}))?)?",
        raw,
        re.IGNORECASE,
    )
    if yymmdd_match:
        try:
            yy = int(yymmdd_match.group(1))
            year = 2000 + yy if yy < 70 else 1900 + yy
            month = int(yymmdd_match.group(2))
            day = int(yymmdd_match.group(3))
            meridiem = yymmdd_match.group(4).upper() if yymmdd_match.group(4) else None
            hour = int(yymmdd_match.group(5)) if yymmdd_match.group(5) is not None else 12
            if meridiem in ("오후", "PM") and hour < 12:
                hour += 12
            elif meridiem in ("오전", "AM") and hour == 12:
                hour = 0
            minute = int(yymmdd_match.group(6)) if yymmdd_match.group(6) is not None else 0
            second = int(yymmdd_match.group(7)) if yymmdd_match.group(7) is not None else 0
            dt = datetime.datetime(year, month, day, hour, minute, second, tzinfo=datetime.timezone.utc)
            return dt.isoformat()
        except (ValueError, OverflowError):
            return now.isoformat()

    # Case 6: "MM/DD [HH:MM[:SS]]" or "MM.DD [HH:MM]"
    month_day_match = re.match(
        r"^(\d{1,2})[./\-](\d{1,2})(?:[\sT]*(?:\([월화수목금토일A-Za-z]+\))?\s*(?:(오전|오후|AM|PM)\s*)?(\d{1,2}):(\d{2})(?::(\d{2}))?)?$",
        raw,
        re.IGNORECASE,
    )
    if month_day_match:
        try:
            month = int(month_day_match.group(1))
            day = int(month_day_match.group(2))
            meridiem = month_day_match.group(3).upper() if month_day_match.group(3) else None
            hour = int(month_day_match.group(4)) if month_day_match.group(4) is not None else 12
            if meridiem in ("오후", "PM") and hour < 12:
                hour += 12
            elif meridiem in ("오전", "AM") and hour == 12:
                hour = 0
            minute = int(month_day_match.group(5)) if month_day_match.group(5) is not None else 0
            second = int(month_day_match.group(6)) if month_day_match.group(6) is not None else 0
            # Year rollover guard: roll back year if month/day would land meaningfully in the future
            year = now.year - 1 if (now.month == 1 and month >= 11) else now.year
            try:
                dt = datetime.datetime(year, month, day, hour, minute, second, tzinfo=datetime.timezone.utc)
            except ValueError:
                if month == 2 and day == 29:
                    dt = None
                    for offset in range(1, 9):
                        try:
                            dt = datetime.datetime(now.year - offset, month, day, hour, minute, second, tzinfo=datetime.timezone.utc)
                            break
                        except ValueError:
                            continue
                    if dt is None:
                        raise
                else:
                    raise
            if year == now.year and dt > now + datetime.timedelta(days=1):
                if month == 2 and day == 29:
                    rolled = None
                    for offset in range(1, 9):
                        try:
                            rolled = dt.replace(year=now.year - offset)
                            break
                        except ValueError:
                            continue
                    if rolled is None:
                        raise ValueError("No valid leap year found")
                    dt = rolled
                else:
                    dt = dt.replace(year=now.year - 1)
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
        timeout: Union[float, Tuple[float, float]] = 15.0,
        connect_timeout: Optional[float] = None,
        read_timeout: Optional[float] = None,
        enable_cache: bool = True,
        cache_fallback: bool = True,
    ):
        self.min_delay = min_delay
        self.max_delay = max_delay
        owns_client = client is None
        if client is None:
            client = SafeHttpClient(
                min_delay=min_delay,
                max_delay=max_delay,
                max_retries=max_retries,
                timeout=timeout,
                connect_timeout=connect_timeout,
                read_timeout=read_timeout,
                enable_cache=enable_cache,
                cache_fallback=cache_fallback,
            )
        try:
            super().__init__(
                client=client,
                timeout=timeout,
                connect_timeout=connect_timeout,
                read_timeout=read_timeout,
                base_url=BOBAE_BASE_URL,
                enable_cache=enable_cache,
                cache_fallback=cache_fallback,
            )
        except Exception:
            if owns_client and hasattr(client, "close"):
                try:
                    client.close()
                except Exception:
                    pass
            raise
        self._owns_client = owns_client
        self.platform = "bobaedream"

    def load_seed_posts(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Load fallback records for BobaeDream from seed data files."""
        return self.load_seed_fallback(platform_name="bobaedream", limit=limit)

    def sleep_with_jitter(self, min_s: Optional[float] = None, max_s: Optional[float] = None) -> None:
        """Apply polite delay with uniform jitter between crawler requests."""
        raw_low = min_s if min_s is not None else self.min_delay
        raw_high = max_s if max_s is not None else self.max_delay
        if isinstance(raw_low, bool) or isinstance(raw_high, bool):
            return
        try:
            low = max(0.0, float(raw_low))
            high = max(0.0, float(raw_high))
        except (ValueError, TypeError, OverflowError):
            return
        if math.isfinite(low) and math.isfinite(high) and high > 0 and low <= high:
            time.sleep(random.uniform(low, high))

    def ensure_warm_up(self, base_url: Optional[Union[str, bool]] = None, force: bool = False) -> bool:
        """Warm up session cookies on BobaeDream base URL if not already done."""
        if isinstance(base_url, bool):
            force = base_url
            base_url = None
        target_url = (base_url.strip() if isinstance(base_url, str) and base_url.strip() else None) or BOBAE_BASE_URL
        if (not self._warmed_up or force) and target_url:
            target_clean = target_url.strip()
            is_safe, reason = _is_safe_client_url(self.client, target_clean)
            if not is_safe:
                logger.warning(f"Blocked unsafe BobaeDream warm-up URL {target_clean!r}: {reason}")
                return False
            success = True
            try:
                if self.client and hasattr(self.client, "warm_up_session"):
                    res = self.client.warm_up_session(target_clean)
                    success = bool(res) if res is not None else True
            except Exception as e:
                logger.warning(f"BobaeDream warm_up_session notice: {e}")
                success = False
            self._warmed_up = True
            return success
        return self._warmed_up

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
        raw_code = str(board_code).strip() if board_code is not None else ""
        code = urllib.parse.quote(raw_code or "national", safe="")
        eff_page = _normalize_pages(page, default=1, max_pages=100000)
        kw_str = str(keyword).strip() if keyword is not None else ""
        encoded_kw = encode_euc_kr_query(kw_str)
        raw_key = str(s_key).strip() if s_key is not None else ""
        key = urllib.parse.quote(raw_key or "sub_bod", safe="")
        return (
            f"{BOBAE_LIST_URL}?code={code}&s_cate=&s_key={key}"
            f"&search={encoded_kw}&page={eff_page}"
        )

    def build_list_url(self, board_code: str, page: int = 1) -> str:
        """
        Build general list URL without search filters.
        URL format: https://www.bobaedream.co.kr/list?code={board_code}&page={page}
        """
        raw_code = str(board_code).strip() if board_code is not None else ""
        code = urllib.parse.quote(raw_code or "national", safe="")
        eff_page = _normalize_pages(page, default=1, max_pages=100000)
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

        scan_html = _mask_comments_and_scripts(html_content)
        a_scan_html = _slice_to_last_close_tag(scan_html, "</a")
        if not a_scan_html:
            return []
        items: List[Dict[str, Any]] = []
        seen_nos = set()

        def _append_item(raw_href_val: str, post_no_val: str, code_val: str, raw_title_val: str) -> None:
            if not post_no_val or post_no_val in seen_nos:
                return
            full_url = _canonicalize_bobaedream_href(raw_href_val)
            if not full_url:
                return

            clean_title = clean_title_text(raw_title_val)
            # Strip trailing comment count badges e.g. "(14)", "[28]" in list titles
            clean_title = re.sub(r"\s*[\[\(]\s*\d+\s*[\]\)]\s*$", "", clean_title).strip()

            # Filter out empty or notice (공지 / 필독 / 안내) titles
            if (
                not clean_title
                or len(clean_title) < 2
                or clean_title in ("공지", "필독", "안내")
                or clean_title.startswith(("[공지]", "공지 ", "[필독]", "필독 ", "[안내]", "안내 "))
                or "공지사항" in clean_title
                or "<b>공지</b>" in raw_title_val
                or '<b class="notice">' in raw_title_val
                or re.match(r"^\s*(?:\[(?:공지|필독|운영안내)\]|(?:공지|필독|운영안내)(?:[:\s\]-]|$))", clean_title)
            ):
                return

            seen_nos.add(post_no_val)
            items.append({
                "post_id": post_no_val,
                "board_code": code_val or board_code,
                "url": full_url,
                "title": clean_title,
            })

        # Resilient link pattern matching desktop, PHP script, and mobile view URLs
        link_pattern = re.compile(
            r'<a\b[^>]*\bhref\s*=\s*["\']?([^"\'\s>]*view(?:\.php)?\?[^"\'\s>]*|[^"\'\s>]*/(?:bbs_view|view)/[^"\'\s>]*)["\']?[^>]*>(.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        )

        for match in link_pattern.finditer(a_scan_html):
            raw_href = match.group(1)
            raw_title = match.group(2)

            full_href = _unescape_url_entities(raw_href.strip()).strip()
            # Extract post_no from query param (No=, no=, b_no=, bm_no=) or path (/bbs_view/.../123, /view/123)
            no_match = re.search(
                r"(?:[?&](?:b_|bm_)?no=(\d+)|/(?:bbs_view/[^/]+/|view/)(\d+))",
                full_href,
                re.IGNORECASE,
            )
            if not no_match:
                continue
            post_no = no_match.group(1) or no_match.group(2)

            # Extract board code from query param or path
            code_match = re.search(r"[?&]code=([a-zA-Z0-9_-]+)", full_href, re.IGNORECASE)
            if not code_match:
                code_match = re.search(r"/(?:bbs_view|list)/([a-zA-Z0-9_-]+)/", full_href, re.IGNORECASE)
            extracted_code = code_match.group(1) if code_match else board_code

            _append_item(raw_href, post_no, extracted_code, raw_title)

        # Fallback regex if href parameters were ordered differently or single quotes (linear-time, ReDoS-safe)
        if not items:
            alt_anchor_re = re.compile(
                r'<a\s+[^>]*\bhref\s*=\s*(?:"([^"]*)"|\'([^\']*)\')[^>]*>(.*?)</a>',
                re.IGNORECASE | re.DOTALL,
            )
            for dq_href, sq_href, raw_title in alt_anchor_re.findall(a_scan_html):
                full_href_raw = _unescape_url_entities((dq_href or sq_href).strip()).strip()
                if not full_href_raw or "view" not in full_href_raw.lower():
                    continue
                no_m = re.search(r"[?&](?:b_|bm_)?no=(\d+)", full_href_raw, re.IGNORECASE)
                code_m = re.search(r"[?&]code=([a-zA-Z0-9_-]+)", full_href_raw, re.IGNORECASE)
                if no_m and code_m:
                    _append_item(full_href_raw, no_m.group(1), code_m.group(1), raw_title)

        return items

    @staticmethod
    def _extract_balanced_matches(html_str: str, tag_name: str, open_pattern: re.Pattern[str]) -> List[str]:
        """Extract inner HTML of all matched tags using balanced depth tracking."""
        masked = _mask_comments_and_scripts(html_str)
        tag_re = re.compile(rf"<(/?)({re.escape(tag_name)})\b([^>]*)>", re.IGNORECASE)
        results: List[str] = []
        pos = 0
        while True:
            match = open_pattern.search(masked, pos)
            if not match:
                break
            if match.group(0).rstrip(">").rstrip().endswith("/"):
                pos = match.end()
                continue
            start_idx = match.end()
            depth = 1
            end_idx = len(html_str)
            next_pos = len(html_str)
            for m in tag_re.finditer(masked, start_idx):
                is_closing = bool(m.group(1))
                tag_attrs = m.group(3)
                if is_closing:
                    depth -= 1
                    if depth == 0:
                        end_idx = m.start()
                        next_pos = m.end()
                        break
                else:
                    if tag_attrs and tag_attrs.rstrip().endswith("/"):
                        continue
                    depth += 1
            results.append(html_str[start_idx:end_idx])
            pos = next_pos
        return results

    def parse_comments_html(self, comment_html: str) -> List[str]:
        """Parse comment strings from comment_list.php HTML snippet or detail page HTML."""
        comments: List[str] = []
        if not comment_html or not isinstance(comment_html, str):
            return comments

        # Pattern 1: <dd class="...comment..."> or <dd id="cmt_...">
        comment_matches = self._extract_balanced_matches(
            comment_html,
            "dd",
            re.compile(r'<dd\b[^>]*?(?<=\s)class\s*=\s*["\'][^"\']*comment[^"\']*["\'][^>]*>', re.IGNORECASE),
        )
        if not comment_matches:
            comment_matches = self._extract_balanced_matches(
                comment_html,
                "dd",
                re.compile(r'<dd\b[^>]*?(?<=\s)id\s*=\s*["\']cmt_\d+["\'][^>]*>', re.IGNORECASE),
            )
        if not comment_matches:
            # Pattern 2: comment body container (balanced for nested divs)
            comment_matches = self._extract_balanced_matches(
                comment_html,
                "div",
                re.compile(r'<div\b[^>]*?(?<=\s)class\s*=\s*["\'][^"\']*comment_memo[^"\']*["\'][^>]*>', re.IGNORECASE),
            )
        if not comment_matches:
            comment_matches = self._extract_balanced_matches(
                comment_html,
                "li",
                re.compile(r'<li\b[^>]*?(?<=\s)class\s*=\s*["\'][^"\']*comment[^"\']*["\'][^>]*>', re.IGNORECASE),
            )

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
            r'load\(\s*["\']((?:https?://[^/"\']+)?/(?:board_renew|board|bulletin)/[^"\']*comment_list\.php\?[^"\']+)["\']',
            html_content,
            re.IGNORECASE,
        )
        if match:
            raw_url = _unescape_url_entities(match.group(1))
            return _canonicalize_bobaedream_href(raw_url)

        # Alternative: match direct comment_list.php URL in any script or data attr
        alt_match = re.search(
            r'["\']((?:https?://[^/"\']+)?/(?:board_renew|board|bulletin)/[^"\']*comment_list\.php\?[^"\']+)["\']',
            html_content,
            re.IGNORECASE,
        )
        if alt_match:
            raw_url = _unescape_url_entities(alt_match.group(1))
            return _canonicalize_bobaedream_href(raw_url)

        return None

    def fetch_ajax_comments(
        self,
        ajax_url: str,
        referer: Optional[str] = None,
        timeout: Optional[Union[float, Tuple[float, float]]] = None,
    ) -> List[str]:
        """Fetch and parse dynamic comments from comment_list.php."""
        if not ajax_url or not isinstance(ajax_url, str) or not self.client:
            return []
        eff_url = self._normalize_fetch_url(ajax_url, base_url=BOBAE_BASE_URL)
        if not eff_url:
            return []
        is_safe, reason = _is_safe_client_url(self.client, eff_url)
        if not is_safe:
            logger.warning(f"SSRF defense blocked AJAX comment URL {eff_url!r}: {reason}")
            return []
        eff_referer = _sanitize_referer(referer) or f"{BOBAE_BASE_URL}/"
        eff_timeout = self._resolve_timeout_arg(timeout)
        try:
            resp = self.client.get(
                eff_url,
                referer=eff_referer,
                headers={"X-Requested-With": "XMLHttpRequest"},
                timeout=eff_timeout,
            )
            if resp and isinstance(resp, (tuple, list)) and len(resp) >= 2:
                status, text = resp[0], resp[1]
                if isinstance(text, (bytes, bytearray, memoryview)):
                    text = robust_decode(text)
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
        norm_post_url = _unescape_url_entities(str(post_url)) if post_url else ""
        if (post_id is None or str(post_id).strip() == "") and norm_post_url:
            no_match = re.search(
                r"(?:[?&](?:b_|bm_)?no=(\d+)|/(?:bbs_view/[^/]+/|view/)(\d+))",
                norm_post_url,
                re.IGNORECASE,
            )
            post_id = (no_match.group(1) or no_match.group(2)) if no_match else ""

        # Extract board code from post_url if present
        if norm_post_url:
            url_code_match = re.search(r"[?&]code=([a-zA-Z0-9_-]+)", norm_post_url, re.IGNORECASE)
            if not url_code_match:
                url_code_match = re.search(r"/(?:bbs_view|list)/([a-zA-Z0-9_-]+)/", norm_post_url, re.IGNORECASE)
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

        # Mask comments/scripts for DOM metadata extraction (keep raw html_content for AJAX script URL)
        masked_html = _mask_comments_and_scripts(html_content)

        # 2. Title - resilient against attribute order, tag structures, empty leading tags, and entities
        title = ""
        for pat in (
            r'<strong\b(?=[^>]*?(?<=\s)class=["\']?[^"\'>]*\btitle\b)[^>]*>(.*?)</strong>',
            r'<dt\b(?=[^>]*?(?<=\s)class=["\']?[^"\'>]*\btit\b)[^>]*>(.*?)</dt>',
            r'<(?P<tag>h[1-3])\b(?=[^>]*?(?<=\s)class=["\']?[^"\'>]*title)[^>]*>(.*?)</(?P=tag)>',
            r'<meta\b(?=[^>]*?(?<=\s)property=["\']og:title["\'])[^>]*?(?<=\s)content=(?:"([^"]*)"|\'([^\']*)\')',
            r'<meta\b(?=[^>]*?(?<=\s)content=(?:"([^"]*)"|\'([^\']*)\'))[^>]*?(?<=\s)property=["\']og:title["\']',
        ):
            m = re.search(pat, masked_html, re.DOTALL | re.IGNORECASE)
            if m:
                raw_cand = next((g for g in m.groups() if g is not None and g != m.groupdict().get("tag")), "")
                candidate = clean_title_text(raw_cand)
                if candidate:
                    title = candidate
                    break
        if not title:
            title_tag = re.search(r'<title[^>]*>(.*?)</title>', masked_html, re.DOTALL | re.IGNORECASE)
            if title_tag:
                clean_t = clean_title_text(title_tag.group(1))
                clean_t = re.sub(r"\s*-\s*보배드림.*$", "", clean_t).strip()
                if clean_t:
                    title = clean_t

        # 3. Author & Date
        author = ""
        for apat in (
            r'<span\b(?=[^>]*\bclass=["\']?[^"\'>]*\bauthor\b)[^>]*>(.*?)</span>',
            r'<span\b(?=[^>]*\bclass=["\']?[^"\'>]*\buserNick\b)[^>]*>(.*?)</span>',
            r'<dt\b(?=[^>]*\bclass=["\']?[^"\'>]*\bwriter\b)[^>]*>(.*?)</dt>',
        ):
            am = re.search(apat, masked_html, re.DOTALL | re.IGNORECASE)
            if am:
                cand_author = clean_title_text(am.group(1))
                if cand_author:
                    author = cand_author
                    break

        raw_date = ""
        # Support <span>, <td>, <em>, <p>, or <div> containing class="date"
        date_match = re.search(
            r'<(?P<tag>span|td|em|div|p)\b[^>]*?(?<=\s)class=["\'][^"\']*\bdate\b[^"\']*["\'][^>]*>(.*?)</(?P=tag)>',
            masked_html,
            re.DOTALL | re.IGNORECASE,
        )
        if date_match:
            raw_date = clean_html_text(date_match.group(2))
        if not raw_date:
            generic_date = re.search(r'(\d{4}[.\-/]\d{2}[.\-/]\d{2}(?:[\sT]+\d{2}:\d{2}(?::\d{2})?)?)', masked_html)
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
            body_match = re.search(r'<div\b[^>]*?(?<=\s)class=["\']bodyCont["\'][^>]*>(.*?)</div>\s*<!--\s*//bodyCont', html_content, re.DOTALL | re.IGNORECASE)
            if not body_match:
                body_match = re.search(r'<div\b[^>]*?(?<=\s)class=["\']bodyCont["\'][^>]*>(.*?)</div>', masked_html, re.DOTALL | re.IGNORECASE)
            if not body_match:
                body_match = re.search(r'<div\b[^>]*?(?<=\s)id=["\']print_area["\'][^>]*>(.*?)</div>', masked_html, re.DOTALL | re.IGNORECASE)
            if body_match:
                content = clean_html_text(body_match.group(1)).replace("\xa0", " ").strip()
            if not content:
                content01_extracted = extract_container_content(html_content, "div", "content01")
                if content01_extracted:
                    content = clean_html_text(content01_extracted).replace("\xa0", " ").strip()
            if not content:
                body_match = re.search(r'<div\b[^>]*?(?<=\s)class=["\']content01["\'][^>]*>(.*?)</div>', masked_html, re.DOTALL | re.IGNORECASE)
                if body_match:
                    content = clean_html_text(body_match.group(1)).replace("\xa0", " ").strip()

        # 5. Comments (Static + Dynamic AJAX)
        comments: List[str] = []
        timeout = self._resolve_timeout_arg(
            kwargs.get("timeout"),
            kwargs.get("connect_timeout"),
            kwargs.get("read_timeout"),
        )
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

        # LSP compliance: if board_code is passed a URL (as in base crawler fetch_post(url, referer)), handle gracefully
        if isinstance(board_code, str) and board_code.strip().lower().startswith(("http://", "https://")):
            if referer is None:
                referer = board_code
            board_code = "national"

        base_url = kwargs.get("base_url")
        eff_base_url = base_url.strip() if isinstance(base_url, str) and base_url.strip() else BOBAE_BASE_URL
        # Defensively normalize relative URLs and semicolon-terminated HTML entities (&amp; -> &)
        eff_url = self._normalize_fetch_url(post_url, base_url=eff_base_url)
        if not eff_url:
            logger.warning(f"Unsafe or invalid BobaeDream post_url provided: {post_url!r}")
            return None

        is_safe, reason = _is_safe_client_url(self.client, eff_url)
        if not is_safe:
            logger.warning(f"SSRF defense blocked BobaeDream post_url {eff_url!r}: {reason}")
            return None

        if not self.client:
            return None
        self.ensure_warm_up(base_url)
        eff_referer = _sanitize_referer(referer) or f"{BOBAE_BASE_URL}/"
        timeout = self._resolve_timeout_arg(
            kwargs.get("timeout"),
            kwargs.get("connect_timeout"),
            kwargs.get("read_timeout"),
        )

        try:
            resp = self.client.get(eff_url, referer=eff_referer, timeout=timeout)
            if not resp or not isinstance(resp, (tuple, list)) or len(resp) < 2:
                logger.warning(f"Failed to fetch BobaeDream post: {eff_url} (empty or invalid response)")
                return self._fallback_cached_post(eff_url)
            status, text = resp[0], resp[1]
        except Exception as e:
            logger.warning(f"Network error fetching BobaeDream post {eff_url}: {e}")
            return self._fallback_cached_post(eff_url)

        if status == 429:
            logger.warning(f"Rate-limited (HTTP 429) fetching BobaeDream post: {eff_url}. Degrading gracefully.")
            return self._fallback_cached_post(eff_url)

        if isinstance(text, (bytes, bytearray, memoryview)):
            text = robust_decode(text)

        if status != 200 or not text:
            logger.warning(f"Failed to fetch BobaeDream post: {eff_url} (status: {status})")
            return self._fallback_cached_post(eff_url)

        # Check for deleted / restricted / Cloudflare challenge page
        is_blocked, block_reason = is_deleted_or_restricted(text)
        if is_blocked:
            logger.warning(f"BobaeDream post {eff_url} is unavailable ({block_reason})")
            return None

        eff_post_id = str(post_id).strip() if post_id is not None else ""
        try:
            detail = self.parse_post_detail(text, eff_url, board_code=board_code, post_id=eff_post_id, **kwargs)
            if not isinstance(detail, dict):
                return None
            if (
                detail.get("is_deleted")
                or detail.get("is_restricted")
                or detail.get("status")
                in (
                    "deleted_post",
                    "restricted_post",
                    "cloudflare_challenge",
                    "abnormal_access_blocked",
                    "ip_blocked",
                    "captcha_challenge",
                    "access_denied",
                    "service_maintenance",
                )
            ):
                return None
            self._store_cached_post(eff_url, detail)
            return detail
        except Exception as e:
            logger.warning(f"Error parsing BobaeDream post detail ({eff_url}) on corrupt HTML: {e}")
            return self._fallback_cached_post(eff_url)

    def _crawl_list_pages(
        self,
        board_code: str,
        url_builder: Any,
        pages: int = 1,
        limit: Optional[int] = None,
        action_label: str = "Crawling",
    ) -> List[Dict[str, Any]]:
        """Shared pagination loop for BobaeDream board listing and keyword search."""
        eff_limit = _normalize_limit(limit)
        if eff_limit is not None and eff_limit <= 0:
            return []
        if not self.client:
            return []

        eff_pages = _normalize_pages(pages, default=1)
        self.ensure_warm_up()
        results: List[Dict[str, Any]] = []
        visited_nos: OrderedDict[str, None] = OrderedDict()
        MAX_VISITED_TRACK = 10000
        consecutive_failures = 0
        MAX_CONSECUTIVE_FAILURES = 5

        for page in range(1, eff_pages + 1):
            url = url_builder(page)
            is_safe, reason = _is_safe_client_url(self.client, url)
            if not is_safe:
                logger.warning(f"SSRF defense blocked BobaeDream list URL {url!r}: {reason}")
                break
            logger.info(f"{action_label} BobaeDream [{board_code}] (Page {page}): {url}")
            try:
                resp = self.client.get(
                    url,
                    referer=f"{BOBAE_BASE_URL}/",
                    timeout=(self.connect_timeout, self.read_timeout),
                )
                if not resp or not isinstance(resp, (tuple, list)) or len(resp) < 2:
                    logger.warning(f"Failed to fetch list for {board_code} page {page}")
                    break
                status, text = resp[0], resp[1]
            except Exception as e:
                logger.warning(f"Network dropout fetching list for {board_code} page {page}: {e}")
                break

            if isinstance(text, (bytes, bytearray, memoryview)):
                text = robust_decode(text)

            if status != 200 or not text:
                logger.warning(f"Failed to fetch list for {board_code} page {page} (status: {status})")
                break

            is_blocked, block_reason = is_deleted_or_restricted(text)
            if is_blocked:
                logger.warning(f"BobaeDream list page unavailable ({block_reason}) on page {page}")
                break

            items = self.parse_list_page(text, board_code)
            if not items:
                logger.info(f"No more items in BobaeDream [{board_code}] page {page}")
                break

            # Pagination loop detection: if all items on this page were already seen, stop
            page_keys = {str(it.get("post_id") or it.get("url") or "") for it in items}
            page_keys.discard("")
            if page_keys and page_keys.issubset(visited_nos.keys()):
                logger.info(f"Page {page} of [{board_code}] repeated previously seen posts. Halting pagination loop.")
                break

            halt_crawl = False

            for item in items:
                pid = item.get("post_id", "")
                dedup_key = str(pid or item.get("url") or "")
                if dedup_key and dedup_key in visited_nos:
                    continue
                if dedup_key:
                    if len(visited_nos) >= MAX_VISITED_TRACK:
                        visited_nos.popitem(last=False)
                    visited_nos[dedup_key] = None
                post = self.fetch_post(
                    item.get("url", ""),
                    board_code=board_code,
                    post_id=pid,
                    referer=url,
                )
                if post:
                    results.append(post)
                    consecutive_failures = 0
                    if eff_limit and len(results) >= eff_limit:
                        return results
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                        logger.warning(
                            f"Encountered {consecutive_failures} consecutive fetch failures on BobaeDream [{board_code}]. "
                            f"Halting crawl loop to prevent rate-limit bans."
                        )
                        halt_crawl = True
                        break

            if halt_crawl:
                break

        return results

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
        return self._crawl_list_pages(
            board_code=board_code,
            url_builder=lambda p: self.build_list_url(board_code, page=p),
            pages=pages,
            limit=limit,
            action_label="Crawling",
        )

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
        return self._crawl_list_pages(
            board_code=board_code,
            url_builder=lambda p: self.build_search_url(board_code, keyword, page=p, s_key=s_key),
            pages=pages,
            limit=limit,
            action_label=f"Searching '{keyword}' on",
        )

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
        eff_limit = _normalize_limit(limit)
        if eff_limit is not None and eff_limit <= 0:
            return []

        if isinstance(boards, str):
            target_boards = [boards]
        elif boards is not None:
            target_boards = list(boards)
        else:
            target_boards = ["national", "import", "electric"]
        all_posts: List[Dict[str, Any]] = []
        seen_keys: Set[Tuple[str, str]] = set()

        for board in target_boards:
            if not isinstance(board, str) or not board.strip():
                continue
            remaining_limit = (eff_limit - len(all_posts)) if eff_limit is not None else None
            board_posts = self.search_board(board, keyword, pages=max_pages, limit=remaining_limit)
            for p in board_posts:
                pid = str(p.get("post_id") or "")
                bcode = str(p.get("board_code") or board)
                if pid:
                    key = (bcode, pid)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                all_posts.append(p)
                if eff_limit and len(all_posts) >= eff_limit:
                    return all_posts[:eff_limit]

        return all_posts


# Standard alias matching alternate naming conventions
BobaedreamCrawler = BobaeDreamCrawler
