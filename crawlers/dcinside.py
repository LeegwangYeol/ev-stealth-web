"""
DCInside Gallery Crawler & AJAX Comment Harvester.
Supports UTF-8 search queries across car_new1 (Major) and electriccar (Mini/Minor) galleries,
list parsing from ub-content table rows, post body extraction from write_div,
session token (e_s_n_o) extraction, and AJAX comment extraction from /board/comment/.
Returns structured raw post dictionaries adhering to PROJECT.md § Interface Contracts.
"""

from __future__ import annotations

from collections import OrderedDict
import datetime
import html
import json
import logging
import math
import re
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple, Union

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
from utils.http_client import SafeHttpClient, clean_html_text, robust_decode

logger = logging.getLogger("DCInsideCrawler")

DC_BASE_URL = "https://gall.dcinside.com"
DC_MOBILE_BASE_URL = "https://m.dcinside.com"

# Gallery directory with route prefixes
DC_GALLERIES: Dict[str, Dict[str, str]] = {
    "car_new1": {
        "name": "자동차 갤러리",
        "type": "major",
        "prefix": "board",
    },
    "electriccar": {
        "name": "전기차 미니 갤러리",
        "type": "mini",
        "prefix": "mini/board",
    },
    "tesla": {
        "name": "테슬라 마이너 갤러리",
        "type": "minor",
        "prefix": "mgallery/board",
    },
    "ioniq": {
        "name": "아이오닉 마이너 갤러리",
        "type": "minor",
        "prefix": "mgallery/board",
    },
    "byd": {
        "name": "BYD 마이너 갤러리",
        "type": "minor",
        "prefix": "mgallery/board",
    },
}

# Pre-compiled regular expressions for maximum throughput and memory efficiency
RE_HTML_COMMENTS = re.compile(r"<!--.*?-->", re.DOTALL)
RE_SCRIPT_STYLE = re.compile(r"<(script|style)[^>]*>.*?</\1\s*>", re.DOTALL | re.IGNORECASE)
RE_COMMENT_OR_SCRIPT = re.compile(
    r"<!--.*?-->|<(script|style)\b[^>]*>.*?</\1\s*>",
    re.DOTALL | re.IGNORECASE,
)
RE_UB_CONTENT_ROW = re.compile(
    r'<tr\b(?=[^>]*\bub-content\b)[^>]*\bdata-no=["\']?(\d+)["\']?[^>]*>(.*?)</tr>',
    re.DOTALL | re.IGNORECASE,
)
RE_ALL_TR = re.compile(r'<tr\b([^>]*)>(.*?)</tr>', re.DOTALL | re.IGNORECASE)
RE_POST_NO = re.compile(r"[?&]no=(\d+)", re.IGNORECASE)
RE_POST_PATH_NO = re.compile(r"/(?:board|mgallery/board|mini/board)/[\w\-]+/(\d+)", re.IGNORECASE)
RE_POST_NUMERIC = re.compile(r"/(\d{4,})(?:[/?#]|$)", re.IGNORECASE)
RE_GALL_TIT_CELL = re.compile(r'<td[^>]*class=["\'][^"\']*gall_tit[^"\']*["\'][^>]*>(.*?)</td>', re.DOTALL | re.IGNORECASE)
RE_ANCHOR_TAG = re.compile(r"<a\b([^>]*)>(.*?)</a>", re.DOTALL | re.IGNORECASE)
RE_REPLY_NUM = re.compile(r'<(?:span|em|a)\b[^>]*class=["\'][^"\']*reply_num[^"\']*["\'][^>]*>.*?<\/(?:span|em|a)>', re.DOTALL | re.IGNORECASE)
RE_ESNO_INPUT = re.compile(
    r'<input\b(?=[^>]*\b(?:id|name)=["\']e_s_n_o["\'])[^>]*\bvalue=["\']([^"\']+)["\']',
    re.IGNORECASE,
)


def _extract_td_inner_by_class(row_html: str, class_token: str) -> Optional[str]:
    """Extract inner HTML of the first <td> with class_token in strict O(N) time."""
    if not row_html or not class_token:
        return None
    lower_html = row_html.lower()
    token_lower = class_token.lower()
    pos = 0
    n = len(lower_html)
    while pos < n:
        td_start = lower_html.find("<td", pos)
        if td_start == -1:
            return None
        after_td = td_start + 3
        if after_td < n and lower_html[after_td] not in (" ", "\t", "\n", "\r", ">", "/"):
            pos = after_td
            continue
        gt_idx = lower_html.find(">", after_td)
        if gt_idx == -1:
            return None
        attrs = row_html[after_td:gt_idx]
        if token_lower in attrs.lower():
            cls_m = re.search(
                r'(?<![\w-])class\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))',
                attrs,
                re.IGNORECASE,
            )
            cls_val = (cls_m.group(1) or cls_m.group(2) or cls_m.group(3) or "") if cls_m else ""
            if token_lower in cls_val.lower():
                close_idx = lower_html.find("</td>", gt_idx + 1)
                if close_idx == -1:
                    return None
                return row_html[gt_idx + 1 : close_idx]
        pos = gt_idx + 1
    return None


def extract_container_content(html_str: str, tag_name: str, class_name: str) -> str:
    """
    Extract the inner content of an HTML container by tracking balanced tag depth.
    Resilient against nested tags of the same name, self-closing tags, unclosed child tags,
    and closing tags inside HTML comments or scripts.
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


def is_deleted_or_restricted(html_content: Optional[str]) -> Tuple[bool, str]:
    """
    Check if DCInside HTML indicates the post is deleted, non-existent,
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
    # If a page contains a large article container (> 50 chars), only alert(...) or explicit error titles indicate blocking/deletion
    masked_html = _mask_comments_and_scripts(html_content)
    has_large_body = False
    for body_cls in ("write_div", "writing_view_box", "gallview-contents"):
        body_inner = extract_container_content(html_content, "div", body_cls)
        if body_inner and len(clean_html_text(body_inner)) > 50:
            has_large_body = True
            break
    if not has_large_body:
        write_div_match = re.search(r'(?<=\s)class=["\']write_div["\'][^>]*>(.*?)</div>', masked_html, re.DOTALL | re.IGNORECASE)
        write_div_inner = write_div_match.group(1) if write_div_match else ""
        if write_div_inner and len(clean_html_text(write_div_inner)) > 50:
            has_large_body = True

    if not has_large_body:
        if re.search(r"(?:비정상적인|잘못된)\s*(?:접근|요청)입니다", masked_html, re.IGNORECASE):
            return True, "abnormal_access_blocked"
        if re.search(r"(?:접근이\s*차단되었습니다|(?:차단된|제한된)\s*(?:아이피|IP)|매니저가\s*차단)", masked_html, re.IGNORECASE):
            return True, "ip_blocked"
        if re.search(r"(?:자동\s*방지\s*문자|보안\s*문자를\s*입력|reCAPTCHA|hCaptcha)", masked_html, re.IGNORECASE):
            return True, "captcha_challenge"
        if re.search(r"(?:서비스\s*점검\s*중|시스템\s*점검\s*중)", masked_html, re.IGNORECASE):
            return True, "service_maintenance"

    # Deleted or Non-existent posts
    deleted_patterns = [
        r"alert\s*\(\s*['\"][^'\"]*삭제된\s*게시물",
        r"alert\s*\(\s*['\"][^'\"]*삭제된\s*글",
        r"alert\s*\(\s*['\"][^'\"]*존재하지\s*않는\s*게시물",
        r"alert\s*\(\s*['\"][^'\"]*삭제되었거나\s*존재하지\s*않는",
        r"alert\s*\(\s*['\"][^'\"]*해당\s*게시물이\s*(?:없|삭제)",
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
        r"alert\s*\(\s*['\"][^'\"]*접근\s*권한",
        r"alert\s*\(\s*['\"][^'\"]*로그인\s*[이후]?\s*(?:필요|이용|하십시오|하세요)",
        r"alert\s*\(\s*['\"][^'\"]*성인\s*인증",
        r"로그인이\s*필요한\s*서비스입니다",
        r"로그인\s*후\s*이용\s*(?:가능|바랍니다|하십시오)",
        r"접근\s*권한이\s*없습니다",
        r"성인\s*인증이\s*필요한\s*게시물입니다",
        r"해당\s*갤러리는\s*접근이\s*제한되었습니다",
        r"폐쇄된\s*갤러리입니다",
        r"존재하지\s*않는\s*갤러리입니다",
        r"글쓰기(?:와\s*댓글)?이\s*제한된",
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
    """Normalize timestamp into ISO-8601 string with UTC timezone."""
    if not raw_date_str or not isinstance(raw_date_str, str):
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    raw = raw_date_str.strip()
    if not raw:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    now = datetime.datetime.now(datetime.timezone.utc)

    # 1. Try ISO-8601 parsing directly if format matches
    if "T" in raw or (raw.count("-") >= 2 and ":" in raw):
        try:
            clean_iso = re.sub(r"[zZ]$", "+00:00", raw)
            dt = datetime.datetime.fromisoformat(clean_iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt.astimezone(datetime.timezone.utc).isoformat()
        except (ValueError, TypeError, OverflowError):
            pass

    # 2. Relative times: "방금", "10분 전", "1시간 전", "어제", "그저께"
    if "방금" in raw:
        return now.isoformat()
    rel_min = re.search(r"(\d+)\s*분\s*전", raw)
    if rel_min:
        try:
            return (now - datetime.timedelta(minutes=int(rel_min.group(1)))).isoformat()
        except (ValueError, OverflowError):
            return now.isoformat()
    rel_hour = re.search(r"(\d+)\s*시간\s*전", raw)
    if rel_hour:
        try:
            return (now - datetime.timedelta(hours=int(rel_hour.group(1)))).isoformat()
        except (ValueError, OverflowError):
            return now.isoformat()
    rel_day = re.search(r"(\d+)\s*일\s*전", raw)
    if rel_day:
        try:
            return (now - datetime.timedelta(days=int(rel_day.group(1)))).isoformat()
        except (ValueError, OverflowError):
            return now.isoformat()
    if raw == "그저께":
        return (now - datetime.timedelta(days=2)).isoformat()
    if "어제" in raw:
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

    # 2b. Korean format with 년, 월, 일: "2026년 9월 8일 (화) 오후 02:15"
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
            h = int(kr_date.group(5)) if kr_date.group(5) is not None else 12
            if meridiem in ("오후", "PM") and h < 12:
                h += 12
            elif meridiem in ("오전", "AM") and h == 12:
                h = 0
            mi = int(kr_date.group(6)) if kr_date.group(6) is not None else 0
            s = int(kr_date.group(7)) if kr_date.group(7) is not None else 0
            dt = datetime.datetime(y, m, d, h, mi, s, tzinfo=datetime.timezone.utc)
            return dt.isoformat()
        except (ValueError, OverflowError):
            return now.isoformat()

    # 3. Full timestamp: "2026-09-08 10:11:21" or "2026.09.08 (화) 오후 10:11" or "2026.9.8"
    full_match = re.search(
        r"(?<!\d)(\d{4})[./\-\s]+(\d{1,2})[./\-\s]+(\d{1,2})\.?(?:[\sT]*(?:\([월화수목금토일A-Za-z]+\))?[\sT]*(?:(오전|오후|AM|PM)\s*)?(\d{1,2}):(\d{2})(?::(\d{2}))?)?",
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

    # 4. Case: "YY/MM/DD" or "YY.MM.DD"
    yymmdd_match = re.match(
        r"^(?<!\d)(\d{2})[./\-](\d{1,2})[./\-](\d{1,2})(?:[\sT]*(?:\([월화수목금토일A-Za-z]+\))?[\sT]*(?:(오전|오후|AM|PM)\s*)?(\d{1,2}):(\d{2})(?::(\d{2}))?)?$",
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

    # 5. Time only: "10:11" or "10:11:20" or "오후 02:15"
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

    time_match = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", raw)
    if time_match:
        try:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            second = int(time_match.group(3)) if time_match.group(3) is not None else 0
            dt = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
            return dt.isoformat()
        except (ValueError, OverflowError):
            return now.isoformat()

    # 6. Month-day: "09.08" or "09.08 10:11"
    md_match = re.match(
        r"^(\d{1,2})[./\-](\d{1,2})(?:[\sT]*(?:\([월화수목금토일A-Za-z]+\))?[\sT]*(?:(오전|오후|AM|PM)\s*)?(\d{1,2}):(\d{2})(?::(\d{2}))?)?$",
        raw,
        re.IGNORECASE,
    )
    if md_match:
        try:
            month = int(md_match.group(1))
            day = int(md_match.group(2))
            meridiem = md_match.group(3).upper() if md_match.group(3) else None
            hour = int(md_match.group(4)) if md_match.group(4) is not None else 12
            if meridiem in ("오후", "PM") and hour < 12:
                hour += 12
            elif meridiem in ("오전", "AM") and hour == 12:
                hour = 0
            minute = int(md_match.group(5)) if md_match.group(5) is not None else 0
            second = int(md_match.group(6)) if md_match.group(6) is not None else 0
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


class DCInsideCrawler(BaseCrawler):
    """
    Crawler for DCInside galleries.
    Handles UTF-8 search queries, gallery pagination across car_new1 and electriccar,
    ub-content list parsing, write_div post body extraction, and AJAX comment extraction
    using e_s_n_o session tokens.
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
                base_url=DC_BASE_URL,
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
        self.platform = "dcinside"

    def load_seed_posts(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Load fallback records for DCInside from seed data files."""
        return self.load_seed_fallback(platform_name="dcinside", limit=limit)

    def is_deleted_or_restricted(self, html_content: Optional[str]) -> Tuple[bool, str]:
        """Proxy check for deleted, restricted, or blocked pages."""
        return is_deleted_or_restricted(html_content)

    def ensure_warm_up(self, base_url: Optional[Union[str, bool]] = None, force: bool = False) -> bool:
        """Warm up session cookies on DCInside base URL if not already done."""
        if isinstance(base_url, bool):
            force = base_url
            base_url = None
        target_url = (base_url.strip() if isinstance(base_url, str) and base_url.strip() else None) or DC_BASE_URL
        if (not self._warmed_up or force) and target_url:
            target_clean = target_url.strip()
            is_safe, reason = _is_safe_client_url(self.client, target_clean)
            if not is_safe:
                logger.warning(f"Blocked unsafe DCInside warm-up URL {target_clean!r}: {reason}")
                return False
            success = True
            try:
                if self.client and hasattr(self.client, "warm_up_session"):
                    res = self.client.warm_up_session(target_clean)
                    success = bool(res) if res is not None else True
            except Exception as e:
                logger.warning(f"DCInside warm_up_session notice: {e}")
                success = False
            self._warmed_up = True
            return success
        return self._warmed_up

    def get_gallery_prefix(self, gallery_id: str) -> str:
        """Determine URL route prefix for the gallery (board, mini/board, mgallery/board)."""
        gid = str(gallery_id or "").strip().lower()
        info = DC_GALLERIES.get(gid)
        if info:
            return info["prefix"]
        # Default heuristic: fallback to mgallery/board for unknown minor galleries
        return "board" if gid == "car_new1" else "mgallery/board"

    def build_list_url(self, gallery_id: str, page: int = 1) -> str:
        """Build standard gallery list URL."""
        prefix = self.get_gallery_prefix(gallery_id)
        gid = urllib.parse.quote(str(gallery_id or "").strip(), safe="")
        eff_page = _normalize_pages(page, default=1, max_pages=100000)
        return f"{DC_BASE_URL}/{prefix}/lists/?id={gid}&page={eff_page}"

    def build_search_url(self, gallery_id: str, keyword: str, page: int = 1) -> str:
        """Build UTF-8 encoded search URL."""
        prefix = self.get_gallery_prefix(gallery_id)
        gid = urllib.parse.quote(str(gallery_id or "").strip(), safe="")
        eff_page = _normalize_pages(page, default=1, max_pages=100000)
        kw_str = str(keyword) if keyword is not None else ""
        encoded_kw = urllib.parse.quote(kw_str, safe="")
        return (
            f"{DC_BASE_URL}/{prefix}/lists/?"
            f"id={gid}&s_type=search_subject_memo&s_keyword={encoded_kw}&page={eff_page}"
        )

    def build_post_url(self, gallery_id: str, post_id: str) -> str:
        """Build canonical desktop view URL for a post."""
        prefix = self.get_gallery_prefix(gallery_id)
        gid = urllib.parse.quote(str(gallery_id or "").strip(), safe="")
        pid = urllib.parse.quote(str(post_id or "").strip(), safe="")
        return f"{DC_BASE_URL}/{prefix}/view/?id={gid}&no={pid}"

    def parse_gallery_list(self, html_content: str, gallery_id: str) -> List[Dict[str, Any]]:
        """
        Extract post items from DCInside gallery list HTML.
        Specifically searches for table rows with class ub-content:
          <tr class="ub-content us-post" data-no="11503496">
            ...
            <td class="gall_tit ub-word"><a href="...">제목</a></td>
            <td class="gall_date" title="2026-09-08 10:11:21">10:11</td>
          </tr>
        Resilient against attribute order, single/double quotes, and malformed tags.
        """
        if not html_content or not isinstance(html_content, str):
            return []

        # Check for Cloudflare challenge or bot block on list page
        is_blocked, reason = is_deleted_or_restricted(html_content)
        if is_blocked and reason in ("cloudflare_challenge", "abnormal_access_blocked", "ip_blocked", "captcha_challenge"):
            logger.warning(f"DCInside list page blocked by anti-scraping: {reason}")
            return []

        scan_html = _mask_comments_and_scripts(html_content)
        tr_scan_html = _slice_to_last_close_tag(scan_html, "</tr")
        items: List[Dict[str, Any]] = []
        seen_nos = set()

        # Scan all <tr> rows having ub-content class so rows with or without data-no are both handled
        matches: List[re.Match[str]] = []
        if tr_scan_html:
            for tr_m in RE_ALL_TR.finditer(tr_scan_html):
                tr_attrs = tr_m.group(1)
                if re.search(r'(?:^|[\s"\'])ub-content(?=$|[\s"\'])', tr_attrs, re.IGNORECASE):
                    matches.append(tr_m)

        for match in matches:
            tr_attrs = match.group(1)
            row_html = match.group(2)
            no_m = re.search(r'\bdata-no=["\']?(\d+)["\']?', tr_attrs, re.IGNORECASE)
            post_no = no_m.group(1) if no_m else ""

            gall_num_inner = _extract_td_inner_by_class(row_html, "gall_num")
            gall_num_text = clean_html_text(gall_num_inner).strip() if gall_num_inner is not None else ""

            # Check if post_no can be extracted from gall_num cell or href inside row
            if not post_no:
                if gall_num_text.isdigit():
                    post_no = gall_num_text
                else:
                    href_no = RE_POST_NO.search(row_html)
                    if href_no:
                        post_no = href_no.group(1)

            if not post_no or post_no in seen_nos:
                continue

            # Detect genuine notice row: class ub-notice or gall_num having "공지" / "설문" / "AD"
            is_notice = (
                "ub-notice" in tr_attrs
                or "ub-notice" in row_html[:200]
                or gall_num_text.upper() in ("공지", "설문", "AD")
            )
            if is_notice:
                continue

            # Extract title & href from gall_tit cell
            gall_tit_m = RE_GALL_TIT_CELL.search(row_html)
            tit_cell_html = gall_tit_m.group(1) if gall_tit_m else row_html

            # Find all anchor tags inside gall_tit
            anchors = RE_ANCHOR_TAG.findall(tit_cell_html)
            raw_href = ""
            raw_title = ""

            if anchors:
                best_anchor = None
                # Prefer anchor linking directly to post view (containing view, no=, or post_no)
                for a_attrs, a_inner in anchors:
                    href_m = re.search(r'(?<![\w-])href\s*=\s*(?:"([^"]+)"|\'([^\']+)\'|([^\s>]+))', a_attrs, re.IGNORECASE)
                    href_val = _unescape_url_entities((href_m.group(1) or href_m.group(2) or href_m.group(3)).strip()).strip() if href_m else ""
                    if "reply_num" in a_attrs or "reply_numbox" in a_attrs:
                        continue
                    if href_val.lower().startswith("javascript:"):
                        continue
                    if "view" in href_val or "no=" in href_val or (post_no and post_no in href_val):
                        if clean_html_text(RE_REPLY_NUM.sub("", a_inner)).strip():
                            best_anchor = (href_val, a_inner)
                            break

                if not best_anchor:
                    # Pick non-reply anchor with longest text
                    candidates = []
                    for a_attrs, a_inner in anchors:
                        if "reply_num" in a_attrs or "reply_numbox" in a_attrs:
                            continue
                        href_m = re.search(r'(?<![\w-])href\s*=\s*(?:"([^"]+)"|\'([^\']+)\'|([^\s>]+))', a_attrs, re.IGNORECASE)
                        href_val = _unescape_url_entities((href_m.group(1) or href_m.group(2) or href_m.group(3)).strip()).strip() if href_m else ""
                        if href_val.lower().startswith("javascript:"):
                            continue
                        candidates.append((href_val, a_inner))
                    if candidates:
                        best_anchor = max(candidates, key=lambda c: len(clean_html_text(c[1])))

                if best_anchor:
                    raw_href, raw_title = best_anchor

            if not raw_title:
                continue

            # Strip nested reply count elements from title
            raw_title = RE_REPLY_NUM.sub("", raw_title)
            clean_title = clean_html_text(raw_title)

            # Extra HTML entity unescape if entities remain
            if clean_title and "&" in clean_title and re.search(r"&[a-zA-Z#0-9]+;", clean_title):
                clean_title = html.unescape(clean_title)

            # Skip empty or notice titles (e.g. starting with [공지])
            if not clean_title or len(clean_title) < 2 or clean_title.startswith("[공지]") or clean_title.startswith("공지:"):
                continue

            seen_nos.add(post_no)

            # Extract full title date if present (handle arbitrary attribute order)
            raw_date = ""
            date_match = re.search(
                r'<td\b(?=[^>]*?(?<=\s)class=["\']?[^"\'>]*\bgall_date\b)[^>]*?(?<=\s)title=["\']([^"\']*)["\']',
                row_html,
                re.IGNORECASE,
            )
            if date_match and date_match.group(1).strip():
                raw_date = date_match.group(1).strip()
            else:
                date_text_match = re.search(
                    r'<td[^>]*class=["\'][^"\']*gall_date[^"\']*["\'][^>]*>(.*?)</td>',
                    row_html,
                    re.IGNORECASE,
                )
                if date_text_match:
                    raw_date = clean_html_text(date_text_match.group(1))

            created_at_iso = _normalize_iso_timestamp(raw_date)
            full_url = self.build_post_url(gallery_id, post_no)

            items.append({
                "post_id": post_no,
                "gallery_id": gallery_id,
                "url": full_url,
                "title": clean_title,
                "created_at": created_at_iso,
            })

        # Fallback if ub-content wasn't strictly found (e.g. mobile or alternative layout)
        if not items and not matches:
            a_scan_html = _slice_to_last_close_tag(scan_html, "</a")
            if a_scan_html:
                alt_anchor_re = re.compile(
                    r'<a\b[^>]*?(?<=\s)href\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))[^>]*>(.*?)</a>',
                    re.DOTALL | re.IGNORECASE,
                )
                alt_no_re = re.compile(
                    r'(?:view/?\?[^\s"\'>]*?(?:^|[?&])no=|/(?:board|mgallery(?:/board)?|mini(?:/board)?)/[\w\-]+/|/view/)(\d+)',
                    re.IGNORECASE,
                )
                for dq_href, sq_href, uq_href, raw_title in alt_anchor_re.findall(a_scan_html):
                    full_href = _unescape_url_entities((dq_href or sq_href or uq_href).strip()).strip()
                    if not full_href or any(ord(c) < 32 or ord(c) == 127 for c in full_href):
                        continue
                    if full_href.lower().startswith("javascript:"):
                        continue
                    if full_href.startswith("//") or full_href.lower().startswith(("http://", "https://")):
                        cand_url = f"https:{full_href}" if full_href.startswith("//") else full_href
                        try:
                            parsed_alt = urllib.parse.urlsplit(cand_url)
                        except ValueError:
                            continue
                        if _has_unsafe_authority(parsed_alt):
                            continue
                        alt_host = (parsed_alt.hostname or "").lower().rstrip(".")
                        if not (alt_host == "dcinside.com" or alt_host.endswith(".dcinside.com")):
                            continue
                    no_m = alt_no_re.search(full_href)
                    if not no_m:
                        continue
                    post_no = no_m.group(1)
                    if post_no in seen_nos:
                        continue
                    # Strip reply numbers
                    raw_title = RE_REPLY_NUM.sub("", raw_title)
                    clean_title = clean_html_text(raw_title)
                    if clean_title and "&" in clean_title and re.search(r"&[a-zA-Z#0-9]+;", clean_title):
                        clean_title = html.unescape(clean_title)
                    if not clean_title or len(clean_title) < 2 or clean_title.startswith("[공지]") or clean_title.startswith("공지:"):
                        continue
                    seen_nos.add(post_no)
                    items.append({
                        "post_id": post_no,
                        "gallery_id": gallery_id,
                        "url": self.build_post_url(gallery_id, post_no),
                        "title": clean_title,
                        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    })

        return items

    def extract_esno_token(self, html_content: str) -> Optional[str]:
        """
        Extract the e_s_n_o session token required for DCInside AJAX comments.
        Handles arbitrary attribute order (<input value="..." id="e_s_n_o">).
        """
        if not html_content or not isinstance(html_content, str):
            return None

        # Look for <input> tag having id or name equal to e_s_n_o and extract value
        match = RE_ESNO_INPUT.search(html_content)
        if match:
            return match.group(1)

        # Fallback: check standard id then value
        match = re.search(
            r'<input[^>]*id=["\']e_s_n_o["\'][^>]*value=["\']([^"\']+)["\']',
            html_content,
            re.IGNORECASE,
        )
        if not match:
            match = re.search(
                r'<input[^>]*name=["\']e_s_n_o["\'][^>]*value=["\']([^"\']+)["\']',
                html_content,
                re.IGNORECASE,
            )
        if not match:
            match = re.search(
                r'<input[^>]*value=["\']([^"\']+)["\'][^>]*id=["\']e_s_n_o["\']',
                html_content,
                re.IGNORECASE,
            )
        if not match:
            match = re.search(
                r'<input[^>]*value=["\']([^"\']+)["\'][^>]*name=["\']e_s_n_o["\']',
                html_content,
                re.IGNORECASE,
            )
        if not match:
            match = re.search(r'e_s_n_o\s*[:=]\s*["\']([^"\']+)["\']', html_content)

        return match.group(1) if match else None

    def fetch_ajax_comments(
        self,
        gallery_id: str,
        post_id: str,
        e_s_n_o: str,
        post_url: str,
        timeout: Optional[Union[float, Tuple[float, float]]] = None,
    ) -> List[str]:
        """
        Fetch dynamic comments via DCInside internal AJAX comment endpoint:
        POST https://gall.dcinside.com/{prefix}/comment/
        """
        if not e_s_n_o or not str(e_s_n_o).strip() or post_id is None or str(post_id).strip() == "" or not gallery_id:
            return []

        prefix = self.get_gallery_prefix(gallery_id)
        ajax_url = f"{DC_BASE_URL}/{prefix}/comment/"
        is_safe, reason = _is_safe_client_url(self.client, ajax_url)
        if not is_safe:
            logger.warning(f"SSRF defense blocked DC AJAX comment URL {ajax_url!r}: {reason}")
            return []

        form_data = {
            "id": str(gallery_id),
            "no": str(post_id),
            "cmt_id": str(gallery_id),
            "cmt_no": str(post_id),
            "e_s_n_o": str(e_s_n_o),
            "comment_page": "1",
        }

        eff_referer = _sanitize_referer(post_url) or f"{DC_BASE_URL}/"
        eff_timeout = self._resolve_timeout_arg(timeout)
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Referer": eff_referer,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }

        try:
            if not self.client:
                return []
            resp = self.client.post(
                ajax_url,
                data=form_data,
                headers=headers,
                referer=eff_referer,
                timeout=eff_timeout,
            )
            if resp and isinstance(resp, (tuple, list)) and len(resp) >= 2:
                status, text = resp[0], resp[1]
                if isinstance(text, (bytes, bytearray, memoryview)):
                    text = robust_decode(text)
                if status == 200 and text:
                    return self.parse_comment_json(text)
        except Exception as e:
            logger.warning(f"Failed to fetch DC AJAX comments ({gallery_id}/{post_id}): {e}")

        return []

    def parse_comment_json(self, json_text: str) -> List[str]:
        """Parse comment strings from DCInside comment API JSON response."""
        comments: List[str] = []
        if not json_text or not isinstance(json_text, str):
            return comments

        try:
            data = json.loads(json_text)
            # Response may contain a list of comments under 'comments', 'comment_list', 'data' or direct list
            items = []
            if isinstance(data, dict):
                items = data.get("comments") or data.get("comment_list") or data.get("data") or []
                if isinstance(items, dict):
                    items = list(items.values())
            elif isinstance(data, list):
                items = data

            if not isinstance(items, list):
                return comments

            def _is_deleted_comment(entry: Dict[str, Any]) -> bool:
                if str(entry.get("del_yn") or "").strip().upper() == "Y":
                    return True
                is_del = entry.get("is_delete")
                if isinstance(is_del, bool):
                    return is_del
                if isinstance(is_del, (int, float)):
                    return math.isfinite(float(is_del)) and is_del != 0
                if isinstance(is_del, str):
                    return is_del.strip().lower() in ("1", "y", "yes", "true")
                return False

            def _extract_valid_comment(entry: Dict[str, Any]) -> Optional[str]:
                if _is_deleted_comment(entry):
                    return None
                memo = str(entry.get("memo") or entry.get("comment_memo") or entry.get("msg") or entry.get("content") or "")
                cleaned = clean_html_text(memo)
                if cleaned and "&" in cleaned and re.search(r"&[a-zA-Z#0-9]+;", cleaned):
                    cleaned = html.unescape(cleaned)
                if (
                    cleaned
                    and len(cleaned) >= 2
                    and not cleaned.strip().startswith(("보이스리플", "[보이스리플]", "(보이스리플)"))
                    and "삭제된 댓글입니다" not in cleaned
                ):
                    return cleaned
                return None

            for item in items:
                if not isinstance(item, dict):
                    continue
                valid_text = _extract_valid_comment(item)
                if valid_text:
                    comments.append(valid_text)

                # Check sub_comments or replies
                sub_items = item.get("sub_comments") or item.get("replies")
                if isinstance(sub_items, dict):
                    sub_items = list(sub_items.values())
                if isinstance(sub_items, list):
                    for sub in sub_items:
                        if not isinstance(sub, dict):
                            continue
                        sub_valid = _extract_valid_comment(sub)
                        if sub_valid:
                            comments.append(sub_valid)
        except Exception as e:
            logger.debug(f"JSON comment parse notice: {e}")

        return comments

    @staticmethod
    def _extract_balanced_comments(masked_html: str) -> List[str]:
        """Extract inner HTML of comment containers (p/dd/span/div) using balanced tag depth."""
        open_re = re.compile(
            r'<(p|dd|span|div)\b(?=[^>]*\bclass\s*=\s*(?:"(?:[^"]*\s)?(?:usertxt|txt|comment_memo)(?:\s[^"]*)?"|\'(?:[^\']*\s)?(?:usertxt|txt|comment_memo)(?:\s[^\']*)?\'|(?:usertxt|txt|comment_memo)(?=[\s>])))[^>]*>',
            re.IGNORECASE,
        )
        results: List[str] = []
        pos = 0
        while True:
            m = open_re.search(masked_html, pos)
            if not m:
                break
            if m.group(0).rstrip(">").rstrip().endswith("/"):
                pos = m.end()
                continue
            tag = m.group(1)
            tag_re = re.compile(rf"<(/?)({re.escape(tag)})\b([^>]*)>", re.IGNORECASE)
            start_idx = m.end()
            depth = 1
            end_idx = len(masked_html)
            next_pos = len(masked_html)
            for inner_m in tag_re.finditer(masked_html, start_idx):
                if inner_m.group(1):
                    depth -= 1
                    if depth == 0:
                        end_idx = inner_m.start()
                        next_pos = inner_m.end()
                        break
                else:
                    attrs = inner_m.group(3)
                    if attrs and attrs.rstrip().endswith("/"):
                        continue
                    depth += 1
            results.append(masked_html[start_idx:end_idx])
            pos = next_pos
        return results

    def parse_post_detail(
        self,
        html_content: str,
        post_url: str,
        gallery_id: str = "car_new1",
        post_id: str = "",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Extract article title, author, date, write_div content, and comments.
        Returns a dictionary adhering to PROJECT.md § Interface Contracts:
        {
          "platform": "dcinside",
          "post_id": str,
          "url": str,
          "title": str,
          "content": str,
          "comments": list[str],
          "created_at": str (ISO-8601)
        }
        """
        # 1. Post ID - zero falsy guard and multi-format URL inspection
        norm_post_url = _unescape_url_entities(str(post_url)) if post_url else ""
        eff_post_id = str(post_id).strip() if post_id is not None else ""
        if not eff_post_id and norm_post_url:
            no_match = RE_POST_NO.search(norm_post_url)
            if not no_match:
                no_match = RE_POST_PATH_NO.search(norm_post_url)
            if not no_match:
                no_match = RE_POST_NUMERIC.search(norm_post_url)
            eff_post_id = no_match.group(1) if no_match else ""

        # Auto-detect gallery_id from URL if left default or blank
        eff_gallery_id = str(gallery_id or "").strip().lower()
        if (not eff_gallery_id or eff_gallery_id == "car_new1") and norm_post_url:
            gid_m = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", norm_post_url, re.IGNORECASE)
            if not gid_m:
                gid_m = re.search(r"/(?:board|mgallery/board|mini/board)/([a-zA-Z0-9_-]+)/\d+", norm_post_url, re.IGNORECASE)
            if gid_m:
                eff_gallery_id = gid_m.group(1).lower()
        if not eff_gallery_id:
            eff_gallery_id = "car_new1"

        if not html_content or not isinstance(html_content, str) or not html_content.strip():
            return {
                "platform": "dcinside",
                "post_id": eff_post_id,
                "url": post_url or "",
                "title": "",
                "content": "",
                "comments": [],
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "author": "",
                "gallery_id": eff_gallery_id,
                "is_deleted": True,
                "status": "empty_content",
            }

        # Check for deleted / secret / restricted / Cloudflare challenge page
        is_blocked, block_reason = is_deleted_or_restricted(html_content)
        if is_blocked:
            return {
                "platform": "dcinside",
                "post_id": eff_post_id,
                "url": post_url or "",
                "title": "",
                "content": "",
                "comments": [],
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "author": "",
                "gallery_id": eff_gallery_id,
                "is_deleted": block_reason == "deleted_post",
                "is_restricted": block_reason in ("restricted_post", "cloudflare_challenge", "abnormal_access_blocked", "ip_blocked", "captcha_challenge"),
                "status": block_reason,
            }

        # Mask comments/scripts for DOM metadata extraction (keep raw html_content for e_s_n_o token)
        masked_html = _mask_comments_and_scripts(html_content)

        # 2. Title - resilient against attribute order, tag structures, empty leading tags, and multi-class declarations
        title = ""
        for pat in (
            r'<(?P<tag>span|div|h[1-6]|p)\b(?=[^>]*?(?<=\s)class=["\']?[^"\'>]*\btitle_subject\b)[^>]*>(.*?)</(?P=tag)>',
            r'<(?P<htag>span|div|h[1-6]|p)\b(?=[^>]*?(?<=\s)class=["\']?[^"\'>]*\btitle_headtext\b)[^>]*>.*?</(?P=htag)>\s*<(?P<tag>span|div|h[1-6]|p)\b[^>]*>(.*?)</(?P=tag)>',
            r'<(?P<tag>h[1-6]|div|span)\b(?=[^>]*?(?<=\s)class=["\']?[^"\'>]*\b(?:tit|gallview-tit-box)\b)[^>]*>(.*?)</(?P=tag)>',
            r'<meta\b(?=[^>]*?(?<=\s)(?:property|name)=["\']og:title["\'])[^>]*?(?<=\s)content=(?:"([^"]*)"|\'([^\']*)\')',
            r'<meta\b(?=[^>]*?(?<=\s)content=(?:"([^"]*)"|\'([^\']*)\'))[^>]*?(?<=\s)(?:property|name)=["\']og:title["\']',
        ):
            m = re.search(pat, masked_html, re.DOTALL | re.IGNORECASE)
            if m:
                gd = m.groupdict()
                if gd.get("tag"):
                    tag_name = gd["tag"]
                    raw_cand = m.group(m.lastindex) if m.lastindex else ""
                    if f"<{tag_name}" in raw_cand.lower():
                        cls_m = re.search(r'\b(title_subject|gallview-tit-box|tit)\b', m.group(0), re.IGNORECASE)
                        if cls_m:
                            balanced = extract_container_content(html_content, tag_name, cls_m.group(1))
                            if balanced:
                                raw_cand = balanced
                else:
                    raw_cand = next((g for g in m.groups() if g is not None), "")
                candidate = clean_html_text(raw_cand)
                if candidate:
                    title = candidate
                    break
        if not title:
            title_tag = re.search(r'<title[^>]*>(.*?)</title>', masked_html, re.DOTALL | re.IGNORECASE)
            if title_tag:
                clean_t = clean_html_text(title_tag.group(1))
                # Strip gallery suffix non-greedily without deleting title subtitles with dashes
                clean_t = re.sub(
                    r"\s*[-|:]\s*[^-\n|:]*(?:갤러리|디시인사이드|dcinside)[^-\n|:]*$",
                    "",
                    clean_t,
                    flags=re.IGNORECASE,
                ).strip()
                if clean_t:
                    title = clean_t

        if title and "&" in title and re.search(r"&[a-zA-Z#0-9]+;", title):
            title = html.unescape(title)

        # 3. Author & Date
        author = ""
        writer_scope_div = extract_container_content(html_content, "div", "gall_writer")
        writer_scope_td = re.search(r'<td\b[^>]*\bclass=["\']?[^"\'>]*\bgall_writer\b[^>]*>.*?</td>', masked_html, re.DOTALL | re.IGNORECASE)
        writer_scope_html = writer_scope_div or (writer_scope_td.group(0) if writer_scope_td else "")
        author_candidates = [
            (writer_scope_html, r'<span\b(?=[^>]*\bclass=["\']?[^"\'>]*\bnickname\b)[^>]*>(.*?)</span>'),
            (writer_scope_html, r'data-nick=(?:"([^"]+)"|\'([^\']+)\')'),
            (masked_html, r'<span\b(?=[^>]*\bclass=["\']?[^"\'>]*\bnickname\b)[^>]*>(.*?)</span>'),
            (masked_html, r'data-nick=(?:"([^"]+)"|\'([^\']+)\')'),
            (masked_html, r'<span\b(?=[^>]*\bclass=["\']?[^"\'>]*\bwriter\b)[^>]*>(.*?)</span>'),
        ]
        for scope, apat in author_candidates:
            if not scope:
                continue
            am = re.search(apat, scope, re.DOTALL | re.IGNORECASE)
            if am:
                raw_author = next((g for g in am.groups() if g is not None), "")
                cand_author = clean_html_text(raw_author)
                if cand_author:
                    author = cand_author
                    break
        ip_search_scope = writer_scope_html or masked_html.split("write_div", 1)[0].split("gallview-contents", 1)[0]
        ip_match = re.search(r'<span\b[^>]*\bclass=["\']ip["\'][^>]*>\(([0-9.*]+)\)</span>', ip_search_scope, re.IGNORECASE)
        if ip_match and ip_match.group(1) not in author:
            author = f"{author or 'ㅇㅇ'} ({ip_match.group(1)})"

        raw_date = ""
        date_match = re.search(
            r'<(?:span|td|div|li|em|p)\b(?=[^>]*?(?<=\s)class=["\']?[^"\'>]*\bgall_date\b)[^>]*?(?<=\s)title=["\']([^"\']*)["\']',
            masked_html,
            re.IGNORECASE,
        )
        if date_match and date_match.group(1).strip():
            raw_date = date_match.group(1).strip()
        if not raw_date:
            date_match2 = re.search(
                r'<(?P<tag>span|td|div|li|em|p)\b(?=[^>]*?(?<=\s)class=["\']?[^"\'>]*\bgall_date\b)[^>]*>(.*?)</(?P=tag)>',
                masked_html,
                re.DOTALL | re.IGNORECASE,
            )
            if date_match2:
                raw_date = clean_html_text(date_match2.group(2))
        if not raw_date:
            generic_date = re.search(r'(\d{4}[.\-/]\d{2}[.\-/]\d{2}(?:[\sT]+\d{2}:\d{2}(?::\d{2})?)?)', masked_html)
            if generic_date:
                raw_date = generic_date.group(1)

        created_at_iso = _normalize_iso_timestamp(raw_date)

        # 4. Article body from write_div (using balanced container extraction)
        content = ""
        extracted_div = extract_container_content(html_content, "div", "write_div")
        if extracted_div:
            content = clean_html_text(extracted_div)

        if not content:
            extracted_box = extract_container_content(html_content, "div", "writing_view_box")
            if extracted_box:
                content = clean_html_text(extracted_box)

        if not content:
            extracted_m = extract_container_content(html_content, "div", "gallview-contents")
            if extracted_m:
                content = clean_html_text(extracted_m)

        if not content:
            extracted_thum = extract_container_content(html_content, "div", "thum-txt") or extract_container_content(html_content, "div", "thum-txtin")
            if extracted_thum:
                content = clean_html_text(extracted_thum)

        if not content:
            body_match = re.search(r'<div\b[^>]*?(?<=\s)class=["\']thum-txt[^"\']*["\'][^>]*>(.*?)</div>', masked_html, re.DOTALL | re.IGNORECASE)
            if body_match:
                content = clean_html_text(body_match.group(1))

        if not content:
            meta_desc = re.search(
                r'<meta\b(?=[^>]*?(?<=\s)(?:property|name)=["\']og:description["\'])[^>]*?(?<=\s)content=(?:"([^"]*)"|\'([^\']*)\')',
                masked_html,
                re.IGNORECASE,
            )
            if not meta_desc:
                meta_desc = re.search(
                    r'<meta\b(?=[^>]*?(?<=\s)content=(?:"([^"]*)"|\'([^\']*)\'))[^>]*?(?<=\s)(?:property|name)=["\']og:description["\']',
                    masked_html,
                    re.IGNORECASE,
                )
            if meta_desc:
                raw_desc = next((g for g in meta_desc.groups() if g is not None), "")
                content = clean_html_text(raw_desc)

        if content and "&" in content and re.search(r"&[a-zA-Z#0-9]+;", content):
            content = html.unescape(content)

        # 5. Dynamic AJAX comments using e_s_n_o
        comments: List[str] = []
        timeout = self._resolve_timeout_arg(
            kwargs.get("timeout"),
            kwargs.get("connect_timeout"),
            kwargs.get("read_timeout"),
        )
        e_s_n_o = self.extract_esno_token(html_content)
        if e_s_n_o and eff_post_id:
            comments = self.fetch_ajax_comments(eff_gallery_id, eff_post_id, e_s_n_o, post_url=post_url, timeout=timeout)

        # Fallback to static comments in DOM if AJAX comments were empty
        if not comments:
            for c_html in self._extract_balanced_comments(masked_html):
                cleaned = clean_html_text(c_html)
                if cleaned and "&" in cleaned and re.search(r"&[a-zA-Z#0-9]+;", cleaned):
                    cleaned = html.unescape(cleaned)
                if cleaned and len(cleaned) >= 2 and not cleaned.strip().startswith(("보이스리플", "[보이스리플]", "(보이스리플)")):
                    comments.append(cleaned)

        return {
            "platform": "dcinside",
            "post_id": eff_post_id,
            "url": post_url or "",
            "title": title,
            "content": content,
            "comments": comments,
            "created_at": created_at_iso,
            "author": author,
            "gallery_id": eff_gallery_id,
        }

    def fetch_post(
        self,
        post_url: str,
        gallery_id: str = "car_new1",
        post_id: Optional[str] = None,
        referer: Optional[str] = None,
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        """Fetch and parse a single post from DCInside with relative URL normalization and network safety."""
        if not post_url or not isinstance(post_url, str) or not post_url.strip():
            logger.warning(f"Invalid DCInside post_url provided: {post_url!r}")
            return None

        # LSP compliance: if gallery_id is passed a URL (as in base crawler fetch_post(url, referer)), handle gracefully
        if isinstance(gallery_id, str) and gallery_id.strip().lower().startswith(("http://", "https://")):
            if referer is None:
                referer = gallery_id
            gallery_id = "car_new1"

        base_url = kwargs.get("base_url")
        eff_base_url = base_url.strip() if isinstance(base_url, str) and base_url.strip() else DC_BASE_URL
        # Defensively normalize relative URLs and semicolon-terminated HTML entities
        eff_url = self._normalize_fetch_url(post_url, base_url=eff_base_url)
        if not eff_url:
            logger.warning(f"Unsafe or invalid DCInside post_url provided: {post_url!r}")
            return None

        is_safe, reason = _is_safe_client_url(self.client, eff_url)
        if not is_safe:
            logger.warning(f"SSRF defense blocked DCInside post_url {eff_url!r}: {reason}")
            return None

        if not self.client:
            return None

        self.ensure_warm_up(base_url)
        eff_referer = _sanitize_referer(referer) or f"{DC_BASE_URL}/"
        timeout = self._resolve_timeout_arg(
            kwargs.get("timeout"),
            kwargs.get("connect_timeout"),
            kwargs.get("read_timeout"),
        )

        try:
            resp = self.client.get(eff_url, referer=eff_referer, timeout=timeout)
            if not resp or not isinstance(resp, (tuple, list)) or len(resp) < 2:
                status, text = 0, ""
            else:
                status, text = resp[0], resp[1]
        except Exception as e:
            logger.warning(f"Network error fetching DCInside post {eff_url}: {e}")
            status, text = 0, ""

        effective_post_id = str(post_id).strip() if post_id is not None else ""
        if not effective_post_id and eff_url:
            m_no = RE_POST_NO.search(eff_url)
            if not m_no:
                m_no = RE_POST_PATH_NO.search(eff_url)
            if not m_no:
                m_no = RE_POST_NUMERIC.search(eff_url)
            if m_no:
                effective_post_id = m_no.group(1)

        effective_gallery_id = str(gallery_id or "").strip().lower()
        if (not effective_gallery_id or effective_gallery_id == "car_new1") and eff_url:
            m_gid = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", eff_url, re.IGNORECASE)
            if not m_gid:
                m_gid = re.search(r"/(?:board|mgallery/board|mini/board)/([a-zA-Z0-9_-]+)/\d+", eff_url, re.IGNORECASE)
            if m_gid:
                effective_gallery_id = m_gid.group(1).lower()
        if not effective_gallery_id:
            effective_gallery_id = "car_new1"

        if isinstance(text, (bytes, bytearray, memoryview)):
            text = robust_decode(text)

        if status != 200 or not text:
            # If rate-limited (HTTP 429), gracefully degrade without hammering mobile endpoint
            if status == 429:
                logger.warning(f"Rate-limited (HTTP 429) fetching DCInside post: {eff_url}. Degrading gracefully.")
                return self._fallback_cached_post(eff_url)

            # Try fallback to mobile view URL on desktop 404/empty or layout anomalies
            eff_host = (urllib.parse.urlsplit(eff_url).hostname or "").lower().rstrip(".")
            is_dc_desktop = (eff_host == "dcinside.com" or eff_host.endswith(".dcinside.com")) and eff_host != "m.dcinside.com"
            if effective_post_id and is_dc_desktop:
                # Canonical mobile route: m.dcinside.com/board/{gallery_id}/{post_id}
                safe_gid = urllib.parse.quote(effective_gallery_id, safe="")
                safe_pid = urllib.parse.quote(effective_post_id, safe="")
                mobile_url = f"{DC_MOBILE_BASE_URL}/board/{safe_gid}/{safe_pid}"
                m_safe, m_safe_reason = _is_safe_client_url(self.client, mobile_url)
                if not m_safe:
                    logger.warning(f"SSRF defense blocked DCInside mobile fallback URL {mobile_url!r}: {m_safe_reason}")
                    return self._fallback_cached_post(eff_url)
                try:
                    m_resp = self.client.get(
                        mobile_url,
                        referer=f"{DC_MOBILE_BASE_URL}/",
                        headers={
                            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1"
                        },
                        timeout=timeout,
                    )
                    if m_resp and isinstance(m_resp, (tuple, list)) and len(m_resp) >= 2:
                        m_status, m_text = m_resp[0], m_resp[1]
                        if isinstance(m_text, (bytes, bytearray, memoryview)):
                            m_text = robust_decode(m_text)
                        if m_status == 429:
                            logger.warning(f"Rate-limited (HTTP 429) on DCInside mobile fallback ({mobile_url}).")
                            return self._fallback_cached_post(eff_url)
                        if m_status == 200 and m_text:
                            m_blocked, m_reason = is_deleted_or_restricted(m_text)
                            if m_blocked:
                                logger.warning(f"DCInside mobile post {mobile_url} is unavailable ({m_reason})")
                                return None
                            try:
                                m_detail = self.parse_post_detail(
                                    m_text,
                                    eff_url,
                                    gallery_id=effective_gallery_id,
                                    post_id=effective_post_id,
                                    **kwargs,
                                )
                                if not isinstance(m_detail, dict):
                                    return None
                                if (
                                    m_detail.get("is_deleted")
                                    or m_detail.get("is_restricted")
                                    or m_detail.get("status")
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
                                self._store_cached_post(eff_url, m_detail)
                                return m_detail
                            except Exception as e:
                                logger.warning(f"Error parsing DCInside mobile post detail ({eff_url}) on corrupt HTML: {e}")
                                return self._fallback_cached_post(eff_url)
                except Exception as e:
                    logger.warning(f"Network error on DCInside mobile fallback ({mobile_url}): {e}")

            logger.warning(f"Failed to fetch DCInside post: {eff_url} (status: {status})")
            return self._fallback_cached_post(eff_url)

        # Check for deleted / restricted / Cloudflare challenge page
        is_blocked, block_reason = is_deleted_or_restricted(text)
        if is_blocked:
            logger.warning(f"DCInside post {eff_url} is unavailable ({block_reason})")
            return None

        try:
            detail = self.parse_post_detail(
                text,
                eff_url,
                gallery_id=effective_gallery_id,
                post_id=effective_post_id or "",
                **kwargs,
            )
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
            logger.warning(f"Error parsing DCInside post detail ({eff_url}) on corrupt HTML: {e}")
            return self._fallback_cached_post(eff_url)

    def _crawl_gallery_pages(
        self,
        gallery_id: str,
        url_builder: Any,
        pages: int = 1,
        limit: Optional[int] = None,
        action_label: str = "Crawling",
    ) -> List[Dict[str, Any]]:
        """Shared pagination loop for DCInside gallery listing and keyword search."""
        eff_limit = _normalize_limit(limit)
        if eff_limit is not None and eff_limit <= 0:
            return []
        if not self.client:
            return []

        self.ensure_warm_up()
        results: List[Dict[str, Any]] = []
        seen_pids: OrderedDict[str, None] = OrderedDict()
        MAX_SEEN_TRACK = 10000
        consecutive_failures = 0
        MAX_CONSECUTIVE_FAILURES = 5
        eff_pages = _normalize_pages(pages, default=1)

        for page in range(1, eff_pages + 1):
            url = url_builder(page)
            is_safe, reason = _is_safe_client_url(self.client, url)
            if not is_safe:
                logger.warning(f"SSRF defense blocked DCInside list URL {url!r}: {reason}")
                break
            logger.info(f"{action_label} DCInside [{gallery_id}] (Page {page}): {url}")
            try:
                resp = self.client.get(
                    url,
                    referer=f"{DC_BASE_URL}/",
                    timeout=(self.connect_timeout, self.read_timeout),
                )
                if not resp or not isinstance(resp, (tuple, list)) or len(resp) < 2:
                    logger.warning(f"Failed to fetch list for DC [{gallery_id}] page {page}")
                    break
                status, text = resp[0], resp[1]
            except Exception as e:
                logger.warning(f"Network dropout fetching list for DC [{gallery_id}] page {page}: {e}")
                break

            if isinstance(text, (bytes, bytearray, memoryview)):
                text = robust_decode(text)

            if status != 200 or not text:
                logger.warning(f"Failed to fetch list for DC [{gallery_id}] page {page} (status: {status})")
                break

            is_blocked, block_reason = is_deleted_or_restricted(text)
            if is_blocked:
                logger.warning(f"DCInside list page unavailable ({block_reason}) on page {page}")
                break

            items = self.parse_gallery_list(text, gallery_id)
            if not items:
                logger.info(f"No more items in DCInside [{gallery_id}] page {page}")
                break

            page_keys = {str(it.get("post_id") or it.get("url") or "") for it in items}
            page_keys.discard("")
            if page_keys and page_keys.issubset(seen_pids.keys()):
                logger.info(f"Page {page} of DCInside [{gallery_id}] repeated previously seen posts. Halting pagination loop.")
                break

            halt_crawl = False

            for item in items:
                pid = item.get("post_id", "")
                dedup_key = str(pid or item.get("url") or "")
                if dedup_key and dedup_key in seen_pids:
                    continue
                if dedup_key:
                    if len(seen_pids) >= MAX_SEEN_TRACK:
                        seen_pids.popitem(last=False)
                    seen_pids[dedup_key] = None

                post = self.fetch_post(item.get("url", ""), gallery_id=gallery_id, post_id=pid, referer=url)
                if post:
                    results.append(post)
                    consecutive_failures = 0
                    if eff_limit and len(results) >= eff_limit:
                        return results
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                        logger.warning(
                            f"Encountered {consecutive_failures} consecutive fetch failures on DC [{gallery_id}]. "
                            f"Halting crawl to prevent rate-limit bans."
                        )
                        halt_crawl = True
                        break

            if halt_crawl:
                break

        return results

    def crawl_gallery(
        self,
        gallery_id: str,
        pages: int = 1,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Crawl recent posts from a gallery without keyword search.
        Target galleries: car_new1, electriccar.
        """
        return self._crawl_gallery_pages(
            gallery_id=gallery_id,
            url_builder=lambda p: self.build_list_url(gallery_id, page=p),
            pages=pages,
            limit=limit,
            action_label="Crawling",
        )

    def search_gallery(
        self,
        gallery_id: str,
        keyword: str,
        pages: int = 1,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search a DCInside gallery with a UTF-8 encoded query.
        """
        return self._crawl_gallery_pages(
            gallery_id=gallery_id,
            url_builder=lambda p: self.build_search_url(gallery_id, keyword, page=p),
            pages=pages,
            limit=limit,
            action_label=f"Searching '{keyword}' on",
        )

    def crawl_posts_by_keyword(
        self,
        keyword: str,
        galleries: Optional[List[str]] = None,
        max_pages: int = 1,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search across target galleries (car_new1, electriccar) for a given keyword.
        """
        eff_limit = _normalize_limit(limit)
        if eff_limit is not None and eff_limit <= 0:
            return []

        if isinstance(galleries, str):
            target_galleries = [galleries]
        elif galleries is not None:
            target_galleries = list(galleries)
        else:
            target_galleries = ["car_new1", "electriccar"]
        all_posts: List[Dict[str, Any]] = []
        seen_keys = set()

        for gall in target_galleries:
            if not isinstance(gall, str) or not gall.strip():
                continue
            remaining_limit = (eff_limit - len(all_posts)) if eff_limit is not None else None
            gall_posts = self.search_gallery(gall, keyword, pages=max_pages, limit=remaining_limit)
            for p in gall_posts:
                pid = str(p.get("post_id") or "")
                gid = str(p.get("gallery_id") or gall)
                if pid:
                    key = (gid, pid)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                all_posts.append(p)
                if eff_limit and len(all_posts) >= eff_limit:
                    return all_posts[:eff_limit]

        return all_posts


# Standard alias matching alternate naming conventions
DcInsideCrawler = DCInsideCrawler
