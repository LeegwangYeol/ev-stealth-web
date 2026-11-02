"""
DCInside Gallery Crawler & AJAX Comment Harvester.
Supports UTF-8 search queries across car_new1 (Major) and electriccar (Mini/Minor) galleries,
list parsing from ub-content table rows, post body extraction from write_div,
session token (e_s_n_o) extraction, and AJAX comment extraction from /board/comment/.
Returns structured raw post dictionaries adhering to PROJECT.md § Interface Contracts.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
import urllib.parse
from typing import Any, Dict, List, Optional

from crawlers.base_crawler import BaseCrawler
from utils.http_client import SafeHttpClient, clean_html_text

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


def extract_container_content(html_str: str, tag_name: str, class_name: str) -> str:
    """
    Extract the inner content of an HTML container by tracking balanced tag depth.
    Resilient against nested tags of the same name, self-closing tags, and unclosed child tags.
    """
    if not html_str or not isinstance(html_str, str):
        return ""
    pattern = re.compile(
        rf"<{tag_name}\b[^>]*class\s*=\s*[\"'][^\"']*\b{re.escape(class_name)}\b[^\"']*[\"'][^>]*>",
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


def _normalize_iso_timestamp(raw_date_str: Optional[str]) -> str:
    """Normalize timestamp into ISO-8601 string."""
    if not raw_date_str or not isinstance(raw_date_str, str):
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    raw = raw_date_str.strip()
    if not raw:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    now = datetime.datetime.now(datetime.timezone.utc)

    # Full timestamp: "2026-09-08 10:11:21" or "2026.09.08 (화) 10:11" or "2026.9.8"
    full_match = re.search(r"(\d{4})[./\-\s]+(\d{1,2})[./\-\s]+(\d{1,2})(?:\s*(?:\([월화수목금토일]\))?\s*(\d{1,2}):(\d{2})(?::(\d{2}))?)?", raw)
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

    # Case: "YY/MM/DD" or "YY.MM.DD"
    yymmdd_match = re.match(r"^(\d{2})[./\-](\d{1,2})[./\-](\d{1,2})(?:\s*(?:\([월화수목금토일]\))?\s*(\d{1,2}):(\d{2})(?::(\d{2}))?)?$", raw)
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

    # Time only: "10:11"
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

    # Month-day: "09.08" or "09.08 10:11"
    md_match = re.match(r"^(\d{1,2})[./\-](\d{1,2})(?:\s*(?:\([월화수목금토일]\))?\s*(\d{1,2}):(\d{2})(?::(\d{2}))?)?$", raw)
    if md_match:
        try:
            month = int(md_match.group(1))
            day = int(md_match.group(2))
            hour = int(md_match.group(3)) if md_match.group(3) else 12
            minute = int(md_match.group(4)) if md_match.group(4) else 0
            second = int(md_match.group(5)) if md_match.group(5) else 0
            dt = datetime.datetime(now.year, month, day, hour, minute, second, tzinfo=datetime.timezone.utc)
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

    def __init__(self, client: Optional[SafeHttpClient] = None):
        super().__init__(client=client)

    def ensure_warm_up(self, base_url: Optional[str] = None, force: bool = False):
        """Warm up session cookies on DCInside base URL if not already done."""
        if isinstance(base_url, bool):
            force = base_url
            base_url = None
        target_url = base_url or DC_BASE_URL
        if (not self._warmed_up or force) and target_url:
            try:
                if self.client and hasattr(self.client, "warm_up_session"):
                    self.client.warm_up_session(target_url)
            except Exception as e:
                logger.warning(f"DCInside warm_up_session notice: {e}")
            self._warmed_up = True

    def get_gallery_prefix(self, gallery_id: str) -> str:
        """Determine URL route prefix for the gallery (board, mini/board, mgallery/board)."""
        gid = str(gallery_id or "").strip()
        info = DC_GALLERIES.get(gid)
        if info:
            return info["prefix"]
        # Default heuristic: fallback to mgallery/board for unknown minor galleries
        return "board" if gid == "car_new1" else "mgallery/board"

    def build_list_url(self, gallery_id: str, page: int = 1) -> str:
        """Build standard gallery list URL."""
        prefix = self.get_gallery_prefix(gallery_id)
        gid = str(gallery_id or "").strip()
        eff_page = max(1, int(page)) if str(page).isdigit() else 1
        return f"{DC_BASE_URL}/{prefix}/lists/?id={gid}&page={eff_page}"

    def build_search_url(self, gallery_id: str, keyword: str, page: int = 1) -> str:
        """Build UTF-8 encoded search URL."""
        prefix = self.get_gallery_prefix(gallery_id)
        gid = str(gallery_id or "").strip()
        eff_page = max(1, int(page)) if str(page).isdigit() else 1
        encoded_kw = urllib.parse.quote(str(keyword or ""))
        return (
            f"{DC_BASE_URL}/{prefix}/lists/?"
            f"id={gid}&s_type=search_subject_memo&s_keyword={encoded_kw}&page={eff_page}"
        )

    def build_post_url(self, gallery_id: str, post_id: str) -> str:
        """Build canonical desktop view URL for a post."""
        prefix = self.get_gallery_prefix(gallery_id)
        gid = str(gallery_id or "").strip()
        pid = str(post_id or "").strip()
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

        items: List[Dict[str, Any]] = []
        seen_nos = set()

        # Regex targeting table rows with data-no and ub-content in any attribute order
        row_regex = re.compile(
            r'<tr\b(?=[^>]*\bub-content\b)[^>]*\bdata-no=["\']?(\d+)["\']?[^>]*>(.*?)</tr>',
            re.DOTALL | re.IGNORECASE,
        )

        matches = list(row_regex.finditer(html_content))
        # Fallback: scan all <tr> tags if lookahead didn't match
        if not matches:
            for tr_m in re.finditer(r'<tr\b([^>]*)>(.*?)</tr>', html_content, re.DOTALL | re.IGNORECASE):
                tr_attrs = tr_m.group(1)
                if "ub-content" in tr_attrs:
                    no_m = re.search(r'data-no=["\']?(\d+)["\']?', tr_attrs)
                    if no_m:
                        matches.append(tr_m)

        for match in matches:
            if len(match.groups()) >= 2 and match.group(1).isdigit():
                post_no = match.group(1)
                row_html = match.group(2)
            else:
                tr_attrs = match.group(1)
                row_html = match.group(2)
                no_m = re.search(r'data-no=["\']?(\d+)["\']?', tr_attrs)
                if not no_m:
                    continue
                post_no = no_m.group(1)

            if post_no in seen_nos:
                continue
            seen_nos.add(post_no)

            # Extract title & href from gall_tit
            title_match = re.search(
                r'<td[^>]*class=["\'][^"\']*gall_tit[^"\']*["\'][^>]*>.*?<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                row_html,
                re.DOTALL | re.IGNORECASE,
            )
            if not title_match:
                continue

            raw_href = title_match.group(1)
            raw_title = title_match.group(2)
            clean_title = clean_html_text(raw_title)

            # Skip empty or announcement rows
            if not clean_title or len(clean_title) < 2 or "공지" in clean_title:
                continue

            # Extract full title date if present
            raw_date = ""
            date_match = re.search(
                r'<td[^>]*class=["\'][^"\']*gall_date[^"\']*["\'][^>]*title=["\']([^"\']*)["\']',
                row_html,
                re.IGNORECASE,
            )
            if date_match:
                raw_date = date_match.group(1)
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
        if not items:
            alt_pattern = re.compile(
                r'<a[^>]*href=["\']?([^"\'\s>]*view/?\?[^"\'\s>]*no=(\d+)[^"\'\s>]*)["\']?[^>]*>(.*?)</a>',
                re.DOTALL | re.IGNORECASE,
            )
            for full_href, post_no, raw_title in alt_pattern.findall(html_content):
                if post_no in seen_nos:
                    continue
                seen_nos.add(post_no)
                clean_title = clean_html_text(raw_title)
                if not clean_title or len(clean_title) < 2 or "공지" in clean_title:
                    continue
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
        input_pattern = re.compile(
            r'<input\b(?=[^>]*\b(?:id|name)=["\']e_s_n_o["\'])[^>]*\bvalue=["\']([^"\']+)["\']',
            re.IGNORECASE,
        )
        match = input_pattern.search(html_content)
        if match:
            return match.group(1)

        # Fallback 1: check standard id then value
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
            match = re.search(r'e_s_n_o\s*[:=]\s*["\']([^"\']+)["\']', html_content)

        return match.group(1) if match else None

    def fetch_ajax_comments(
        self,
        gallery_id: str,
        post_id: str,
        e_s_n_o: str,
        post_url: str,
        timeout: Optional[float] = None,
    ) -> List[str]:
        """
        Fetch dynamic comments via DCInside internal AJAX comment endpoint:
        POST https://gall.dcinside.com/{prefix}/comment/
        """
        if not e_s_n_o or not post_id or not gallery_id:
            return []

        prefix = self.get_gallery_prefix(gallery_id)
        ajax_url = f"{DC_BASE_URL}/{prefix}/comment/"

        form_data = {
            "id": str(gallery_id),
            "no": str(post_id),
            "cmt_id": str(gallery_id),
            "cmt_no": str(post_id),
            "e_s_n_o": str(e_s_n_o),
            "comment_page": "1",
        }

        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Referer": post_url,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }

        try:
            if not self.client:
                return []
            status, text, _ = self.client.post(
                ajax_url,
                data=form_data,
                headers=headers,
                referer=post_url,
                timeout=timeout,
            )
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
            # Response may contain a list of comments under 'comments' or direct list
            items = data.get("comments", []) if isinstance(data, dict) else data
            if not isinstance(items, list):
                return comments

            for item in items:
                if not isinstance(item, dict):
                    continue
                memo = str(item.get("memo") or item.get("comment_memo") or "")
                cleaned = clean_html_text(memo)
                if cleaned and len(cleaned) >= 2 and not cleaned.startswith("보이스리플"):
                    comments.append(cleaned)

                # Check sub_comments or replies
                sub_items = item.get("sub_comments") or item.get("replies")
                if isinstance(sub_items, list):
                    for sub in sub_items:
                        if isinstance(sub, dict):
                            sub_memo = str(sub.get("memo") or sub.get("comment_memo") or "")
                            sub_cleaned = clean_html_text(sub_memo)
                            if sub_cleaned and len(sub_cleaned) >= 2 and not sub_cleaned.startswith("보이스리플"):
                                comments.append(sub_cleaned)
        except Exception as e:
            logger.debug(f"JSON comment parse notice: {e}")

        return comments

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
        # 1. Post ID - zero falsy guard
        if (post_id is None or str(post_id).strip() == "") and post_url:
            no_match = re.search(r"no=(\d+)", str(post_url), re.IGNORECASE)
            post_id = no_match.group(1) if no_match else ""

        if not html_content or not isinstance(html_content, str) or not html_content.strip():
            return {
                "platform": "dcinside",
                "post_id": str(post_id) if post_id is not None else "",
                "url": post_url or "",
                "title": "",
                "content": "",
                "comments": [],
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "author": "",
                "gallery_id": gallery_id,
            }

        # 2. Title - resilient against attribute order and tag structures
        title = ""
        title_match = re.search(r'<span class=["\']title_subject["\'][^>]*>(.*?)</span>', html_content, re.DOTALL | re.IGNORECASE)
        if not title_match:
            title_match = re.search(r'<span class=["\']title_headtext["\'][^>]*>.*?</span>\s*<span[^>]*>(.*?)</span>', html_content, re.DOTALL | re.IGNORECASE)
        if not title_match:
            title_match = re.search(r'<meta\b(?=[^>]*\bproperty=["\']og:title["\'])[^>]*\bcontent=["\']([^"\']*)["\']', html_content, re.IGNORECASE)
        if not title_match:
            title_match = re.search(r'<meta property=["\']og:title["\'] content=["\']([^"\']*)["\']', html_content, re.IGNORECASE)
        if not title_match:
            title_tag = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.DOTALL | re.IGNORECASE)
            if title_tag:
                clean_t = clean_html_text(title_tag.group(1))
                clean_t = re.sub(r"\s*-\s*.*(?:갤러리|디시인사이드).*$", "", clean_t).strip()
                if clean_t:
                    title = clean_t
        if title_match and not title:
            title = clean_html_text(title_match.group(1))

        # 3. Author & Date
        author = ""
        writer_match = re.search(r'<td class=["\']gall_writer[^"\']*["\'][^>]*>.*?<span class=["\']nickname["\'][^>]*>(.*?)</span>', html_content, re.DOTALL | re.IGNORECASE)
        if not writer_match:
            writer_match = re.search(r'<span class=["\']nickname["\'][^>]*>(.*?)</span>', html_content, re.DOTALL | re.IGNORECASE)
        if writer_match:
            author = clean_html_text(writer_match.group(1))
        ip_match = re.search(r'<span class=["\']ip["\'][^>]*>\(([0-9.*]+)\)</span>', html_content)
        if ip_match:
            author = f"{author or 'ㅇㅇ'} ({ip_match.group(1)})"

        raw_date = ""
        date_match = re.search(r'<span class=["\']gall_date["\'][^>]*title=["\']([^"\']*)["\']', html_content, re.IGNORECASE)
        if date_match:
            raw_date = date_match.group(1)
        if not raw_date:
            date_match2 = re.search(r'<span class=["\']gall_date["\'][^>]*>(.*?)</span>', html_content, re.IGNORECASE)
            if date_match2:
                raw_date = clean_html_text(date_match2.group(1))
        if not raw_date:
            generic_date = re.search(r'(\d{4}[.\-/]\d{2}[.\-/]\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?)', html_content)
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
            body_match = re.search(r'<div class=["\']thum-txt[^"\']*["\'][^>]*>(.*?)</div>', html_content, re.DOTALL | re.IGNORECASE)
            if body_match:
                content = clean_html_text(body_match.group(1))

        if not content:
            meta_desc = re.search(r'<meta\b(?=[^>]*\bproperty=["\']og:description["\'])[^>]*\bcontent=["\']([^"\']*)["\']', html_content, re.IGNORECASE)
            if meta_desc:
                content = clean_html_text(meta_desc.group(1))

        # 5. Dynamic AJAX comments using e_s_n_o
        comments: List[str] = []
        timeout = kwargs.get("timeout")
        e_s_n_o = self.extract_esno_token(html_content)
        if e_s_n_o and post_id:
            comments = self.fetch_ajax_comments(gallery_id, post_id, e_s_n_o, post_url=post_url, timeout=timeout)

        # Fallback to static comments in DOM if AJAX comments were empty
        if not comments:
            dom_comments = re.findall(r'<p class=["\']usertxt[^"\']*["\'][^>]*>(.*?)</p>', html_content, re.DOTALL | re.IGNORECASE)
            if not dom_comments:
                dom_comments = re.findall(r'<dd class=["\']usertxt[^"\']*["\'][^>]*>(.*?)</dd>', html_content, re.DOTALL | re.IGNORECASE)
            if not dom_comments:
                dom_comments = re.findall(r'<div class=["\']reply_info[^"\']*["\'][^>]*>.*?<p class=["\']txt[^"\']*["\'][^>]*>(.*?)</p>', html_content, re.DOTALL | re.IGNORECASE)
            for c_html in dom_comments:
                cleaned = clean_html_text(c_html)
                if cleaned and len(cleaned) >= 2 and not cleaned.startswith("보이스리플"):
                    comments.append(cleaned)

        return {
            "platform": "dcinside",
            "post_id": str(post_id) if post_id is not None else "",
            "url": post_url or "",
            "title": title,
            "content": content,
            "comments": comments,
            "created_at": created_at_iso,
            "author": author,
            "gallery_id": gallery_id,
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

        # Defensively normalize relative URLs
        eff_url = post_url.strip()
        if eff_url.startswith("/"):
            eff_url = f"{DC_BASE_URL}{eff_url}"
        elif not (eff_url.startswith("http://") or eff_url.startswith("https://")):
            eff_url = f"{DC_BASE_URL}/{eff_url}"

        base_url = kwargs.get("base_url")
        self.ensure_warm_up(base_url)
        eff_referer = referer or f"{DC_BASE_URL}/"
        timeout = kwargs.get("timeout")

        try:
            resp = self.client.get(eff_url, referer=eff_referer, timeout=timeout)
            if not resp or not isinstance(resp, (tuple, list)) or len(resp) < 2:
                status, text = 0, ""
            else:
                status, text = resp[0], resp[1]
        except Exception as e:
            logger.warning(f"Network error fetching DCInside post {eff_url}: {e}")
            status, text = 0, ""

        effective_post_id = post_id
        if not effective_post_id and eff_url:
            m_no = re.search(r"no=(\d+)", str(eff_url), re.IGNORECASE)
            if m_no:
                effective_post_id = m_no.group(1)

        if status != 200 or not text:
            # Try fallback to mobile view URL
            if effective_post_id:
                prefix = self.get_gallery_prefix(gallery_id)
                mobile_url = f"{DC_MOBILE_BASE_URL}/{prefix}/{gallery_id}/{effective_post_id}"
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
                        if m_status == 200 and m_text:
                            try:
                                return self.parse_post_detail(m_text, eff_url, gallery_id=gallery_id, post_id=effective_post_id, **kwargs)
                            except Exception as e:
                                logger.warning(f"Error parsing DCInside mobile post detail ({eff_url}) on corrupt HTML: {e}")
                                return None
                except Exception as e:
                    logger.warning(f"Network error on DCInside mobile fallback ({mobile_url}): {e}")

            logger.warning(f"Failed to fetch DCInside post: {eff_url} (status: {status})")
            return None

        try:
            return self.parse_post_detail(text, eff_url, gallery_id=gallery_id, post_id=effective_post_id or "", **kwargs)
        except Exception as e:
            logger.warning(f"Error parsing DCInside post detail ({eff_url}) on corrupt HTML: {e}")
            return None

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
        if limit is not None and limit <= 0:
            return []

        self.ensure_warm_up()
        results: List[Dict[str, Any]] = []

        for page in range(1, pages + 1):
            url = self.build_list_url(gallery_id, page=page)
            logger.info(f"Crawling DCInside [{gallery_id}] list (Page {page}): {url}")
            try:
                resp = self.client.get(url, referer=f"{DC_BASE_URL}/")
                if not resp or not isinstance(resp, (tuple, list)) or len(resp) < 2:
                    logger.warning(f"Failed to fetch list for DC [{gallery_id}] page {page}")
                    break
                status, text = resp[0], resp[1]
            except Exception as e:
                logger.warning(f"Network dropout fetching list for DC [{gallery_id}] page {page}: {e}")
                break

            if status != 200 or not text:
                logger.warning(f"Failed to fetch list for DC [{gallery_id}] page {page} (status: {status})")
                break

            items = self.parse_gallery_list(text, gallery_id)
            if not items:
                logger.info(f"No more items in DCInside [{gallery_id}] page {page}")
                break

            for item in items:
                post = self.fetch_post(item.get("url", ""), gallery_id=gallery_id, post_id=item.get("post_id", ""))
                if post:
                    results.append(post)
                    if limit and len(results) >= limit:
                        return results

        return results

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
        if limit is not None and limit <= 0:
            return []

        self.ensure_warm_up()
        results: List[Dict[str, Any]] = []

        for page in range(1, pages + 1):
            url = self.build_search_url(gallery_id, keyword, page=page)
            logger.info(f"Searching DCInside [{gallery_id}] for '{keyword}' (Page {page}): {url}")
            try:
                resp = self.client.get(url, referer=f"{DC_BASE_URL}/")
                if not resp or not isinstance(resp, (tuple, list)) or len(resp) < 2:
                    logger.warning(f"Search request failed for DC [{gallery_id}] keyword '{keyword}' page {page}")
                    break
                status, text = resp[0], resp[1]
            except Exception as e:
                logger.warning(f"Network dropout during search for DC [{gallery_id}] keyword '{keyword}' page {page}: {e}")
                break

            if status != 200 or not text:
                logger.warning(f"Search request failed for DC [{gallery_id}] keyword '{keyword}' page {page} (status: {status})")
                break

            items = self.parse_gallery_list(text, gallery_id)
            if not items:
                logger.info(f"No items found for DC [{gallery_id}] keyword '{keyword}' page {page}")
                break

            for item in items:
                post = self.fetch_post(item.get("url", ""), gallery_id=gallery_id, post_id=item.get("post_id", ""))
                if post:
                    results.append(post)
                    if limit and len(results) >= limit:
                        return results

        return results

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
        if limit is not None and limit <= 0:
            return []

        target_galleries = list(galleries) if galleries is not None else ["car_new1", "electriccar"]
        all_posts: List[Dict[str, Any]] = []

        for gall in target_galleries:
            remaining_limit = (limit - len(all_posts)) if limit is not None else None
            gall_posts = self.search_gallery(gall, keyword, pages=max_pages, limit=remaining_limit)
            all_posts.extend(gall_posts)
            if limit and len(all_posts) >= limit:
                return all_posts[:limit]

        return all_posts


# Standard alias matching alternate naming conventions
DcInsideCrawler = DCInsideCrawler
