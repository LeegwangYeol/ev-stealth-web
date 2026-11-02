"""
BobaeDream Community Crawler & AJAX Comment Harvester.
Supports EUC-KR keyword encoding, list paging across national, import, and electric boards,
article body extraction from bodyCont, dynamic AJAX comment extraction from comment_list.php,
and returns structured raw post dictionaries adhering to PROJECT.md § Interface Contracts.
"""

from __future__ import annotations

import datetime
import logging
import re
import urllib.parse
from typing import Any, Dict, List, Optional

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
    """Normalize community timestamp into ISO-8601 string."""
    if not raw_date_str or not isinstance(raw_date_str, str):
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    raw = raw_date_str.strip()
    if not raw:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    now = datetime.datetime.now(datetime.timezone.utc)

    # Case 1: "14:25" or "14:25:30" (Today's post)
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

    # Case 2: "YYYY-MM-DD HH:MM:SS" or "YYYY.MM.DD (화) HH:MM" or "YYYY.M.D"
    full_match = re.search(
        r"(\d{4})[./\-\s]+(\d{1,2})[./\-\s]+(\d{1,2})(?:\s*(?:\([월화수목금토일]\))?\s*(\d{1,2}):(\d{2})(?::(\d{2}))?)?",
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

    # Case 3: "YY/MM/DD [HH:MM[:SS]]"
    yymmdd_match = re.search(
        r"^(\d{2})[./\-](\d{1,2})[./\-](\d{1,2})(?:\s*(?:\([월화수목금토일]\))?\s*(\d{1,2}):(\d{2})(?::(\d{2}))?)?",
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

    # Case 4: "MM/DD [HH:MM[:SS]]" or "MM.DD [HH:MM]"
    month_day_match = re.match(
        r"^(\d{1,2})[./\-](\d{1,2})(?:\s*(?:\([월화수목금토일]\))?\s*(\d{1,2}):(\d{2})(?::(\d{2}))?)?$",
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
    body extraction from bodyCont, and dynamic AJAX comment extraction.
    """

    def __init__(self, client: Optional[SafeHttpClient] = None):
        super().__init__(client=client)

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

    def build_search_url(self, board_code: str, keyword: str, page: int = 1) -> str:
        """
        Build search URL with EUC-KR percent-encoded keyword parameter.
        URL format: https://www.bobaedream.co.kr/list?code={board_code}&s_cate=&s_key=sub_bod&search={encoded_kw}&page={page}
        """
        code = str(board_code or "national").strip()
        eff_page = max(1, int(page)) if str(page).isdigit() else 1
        encoded_kw = encode_euc_kr_query(keyword or "")
        return (
            f"{BOBAE_LIST_URL}?code={code}&s_cate=&s_key=sub_bod"
            f"&search={encoded_kw}&page={eff_page}"
        )

    def build_list_url(self, board_code: str, page: int = 1) -> str:
        """
        Build general list URL without search filters.
        URL format: https://www.bobaedream.co.kr/list?code={board_code}&page={page}
        """
        code = str(board_code or "national").strip()
        eff_page = max(1, int(page)) if str(page).isdigit() else 1
        return f"{BOBAE_LIST_URL}?code={code}&page={eff_page}"

    def parse_list_page(self, html_content: str, board_code: str) -> List[Dict[str, Any]]:
        """
        Extract post items from a BobaeDream board list view.
        Matches rows containing /view?code={board_code}&No={post_no}.
        Resilient against single/double quotes, unquoted hrefs, and parameter order.
        """
        if not html_content or not isinstance(html_content, str):
            return []

        items: List[Dict[str, Any]] = []
        seen_nos = set()

        # Resilient link pattern matching view URLs with No= and code= in any order
        link_pattern = re.compile(
            r'<a\b[^>]*href=["\']?([^"\'\s>]*view\?[^"\'\s>]*)["\']?[^>]*>(.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        )

        for match in link_pattern.finditer(html_content):
            full_href = match.group(1)
            raw_title = match.group(2)

            no_match = re.search(r"No=(\d+)", full_href, re.IGNORECASE)
            if not no_match:
                continue
            post_no = no_match.group(1)

            if post_no in seen_nos:
                continue
            seen_nos.add(post_no)

            code_match = re.search(r"code=([^&\"'\s>]+)", full_href, re.IGNORECASE)
            extracted_code = code_match.group(1) if code_match else board_code

            clean_title = clean_html_text(raw_title)
            # Filter out empty or notice (공지) titles
            if not clean_title or len(clean_title) < 2 or "공지" in clean_title:
                continue

            full_href_clean = full_href.strip()
            if full_href_clean.startswith("http://") or full_href_clean.startswith("https://"):
                full_url = full_href_clean
            elif full_href_clean.startswith("/"):
                full_url = f"{BOBAE_BASE_URL}{full_href_clean}"
            else:
                full_url = f"{BOBAE_BASE_URL}/{full_href_clean}"

            items.append({
                "post_id": post_no,
                "board_code": extracted_code,
                "url": full_url,
                "title": clean_title,
            })

        # Fallback regex if href parameters were matched differently
        if not items:
            alt_pattern = r'<a\s+[^>]*href=["\']([^"\']*view\?[^"\']*No=(\d+)[^"\']*code=([^"\'&]+)[^"\']*)["\'][^>]*>(.*?)</a>'
            alt_matches = re.findall(alt_pattern, html_content, re.IGNORECASE | re.DOTALL)
            for full_href, post_no, code, raw_title in alt_matches:
                if post_no in seen_nos:
                    continue
                seen_nos.add(post_no)
                clean_title = clean_html_text(raw_title)
                if not clean_title or len(clean_title) < 2 or "공지" in clean_title:
                    continue
                full_href_clean = full_href.strip()
                if full_href_clean.startswith("http://") or full_href_clean.startswith("https://"):
                    full_url = full_href_clean
                elif full_href_clean.startswith("/"):
                    full_url = f"{BOBAE_BASE_URL}{full_href_clean}"
                else:
                    full_url = f"{BOBAE_BASE_URL}/{full_href_clean}"
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
            cleaned = clean_html_text(c_html)
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
            r'load\(["\'](?:https?://[^/"\']+)?(/board_renew/bulletin/comment_list\.php\?[^"\']+)["\']',
            html_content,
            re.IGNORECASE,
        )
        if match:
            path = match.group(1)
            return f"{BOBAE_BASE_URL}{path}" if path.startswith("/") else path

        # Alternative: match direct comment_list.php URL in any script or data attr
        alt_match = re.search(
            r'["\'](?:https?://[^/"\']+)?(/board_renew/bulletin/comment_list\.php\?[^"\']+)["\']',
            html_content,
            re.IGNORECASE,
        )
        if alt_match:
            path = alt_match.group(1)
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
        # 1. Post ID - zero falsy guard
        if (post_id is None or str(post_id).strip() == "") and post_url:
            no_match = re.search(r"No=(\d+)", str(post_url), re.IGNORECASE)
            post_id = no_match.group(1) if no_match else ""

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
            }

        # 2. Title - resilient against attribute order and tag structures
        title = ""
        title_match = re.search(r'<strong class=["\']title["\'][^>]*>(.*?)</strong>', html_content, re.DOTALL | re.IGNORECASE)
        if not title_match:
            title_match = re.search(r'<dt[^>]*class=["\']tit["\'][^>]*>(.*?)</dt>', html_content, re.DOTALL | re.IGNORECASE)
        if not title_match:
            title_match = re.search(r'<meta\b(?=[^>]*\bproperty=["\']og:title["\'])[^>]*\bcontent=["\']([^"\']*)["\']', html_content, re.IGNORECASE)
        if not title_match:
            title_match = re.search(r'<meta property=["\']og:title["\'] content=["\']([^"\']*)["\']', html_content, re.IGNORECASE)
        if not title_match:
            title_tag = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.DOTALL | re.IGNORECASE)
            if title_tag:
                clean_t = clean_html_text(title_tag.group(1))
                clean_t = re.sub(r"\s*-\s*보배드림.*$", "", clean_t).strip()
                if clean_t:
                    title = clean_t
        if title_match and not title:
            title = clean_html_text(title_match.group(1))

        # 3. Author & Date
        author = ""
        author_match = re.search(r'<span class=["\']author["\'][^>]*>(.*?)</span>', html_content, re.DOTALL | re.IGNORECASE)
        if not author_match:
            author_match = re.search(r'<span class=["\']userNick["\'][^>]*>(.*?)</span>', html_content, re.DOTALL | re.IGNORECASE)
        if author_match:
            author = clean_html_text(author_match.group(1))

        raw_date = ""
        date_match = re.search(r'<td class=["\']date["\'][^>]*>(.*?)</td>', html_content, re.DOTALL | re.IGNORECASE)
        if date_match:
            raw_date = clean_html_text(date_match.group(1))
        if not raw_date:
            generic_date = re.search(r'(\d{4}[.\-/]\d{2}[.\-/]\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?)', html_content)
            if generic_date:
                raw_date = generic_date.group(1)

        created_at_iso = _normalize_iso_timestamp(raw_date)

        # 4. Article body from bodyCont (uses balanced container parser to preserve nested divs)
        content = ""
        body_extracted = extract_container_content(html_content, "div", "bodyCont")
        if body_extracted:
            content = clean_html_text(body_extracted)

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
                content = clean_html_text(body_match.group(1))

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

        # Defensively normalize relative URLs
        eff_url = post_url.strip()
        if eff_url.startswith("/"):
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

        try:
            return self.parse_post_detail(text, eff_url, board_code=board_code, post_id=post_id or "", **kwargs)
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
        Supported boards: national, import, electric.
        """
        if limit is not None and limit <= 0:
            return []

        self.ensure_warm_up()
        results: List[Dict[str, Any]] = []

        for page in range(1, pages + 1):
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

            items = self.parse_list_page(text, board_code)
            if not items:
                logger.info(f"No more items in BobaeDream [{board_code}] page {page}")
                break

            for item in items:
                post = self.fetch_post(item.get("url", ""), board_code=board_code, post_id=item.get("post_id", ""))
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
    ) -> List[Dict[str, Any]]:
        """
        Search a specific BobaeDream board with an EUC-KR encoded query.
        """
        if limit is not None and limit <= 0:
            return []

        self.ensure_warm_up()
        results: List[Dict[str, Any]] = []

        for page in range(1, pages + 1):
            url = self.build_search_url(board_code, keyword, page=page)
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

            items = self.parse_list_page(text, board_code)
            if not items:
                logger.info(f"No search results found in {board_code} for '{keyword}' page {page}")
                break

            for item in items:
                post = self.fetch_post(item.get("url", ""), board_code=board_code, post_id=item.get("post_id", ""))
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
