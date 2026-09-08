"""
BobaeDream Community Crawler & AJAX Comment Harvester.
Supports EUC-KR keyword encoding, list paging across national, import, and electric boards,
article body extraction from bodyCont, dynamic AJAX comment extraction from comment_list.php,
and returns structured raw post dictionaries adhering to PROJECT.md § Interface Contracts.
"""

import datetime
import logging
import re
import urllib.parse
from typing import Any, Dict, List, Optional

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


def _normalize_iso_timestamp(raw_date_str: str) -> str:
    """Normalize community timestamp into ISO-8601 string."""
    raw = raw_date_str.strip()
    if not raw:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    now = datetime.datetime.now(datetime.timezone.utc)

    # Case: "14:25" or "14:25:30" (Today's post)
    time_match = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", raw)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
        second = int(time_match.group(3)) if time_match.group(3) else 0
        dt = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
        return dt.isoformat()

    # Case: "MM/DD" or "MM.DD" or "MM-DD"
    month_day_match = re.match(r"^(\d{1,2})[./\-](\d{1,2})$", raw)
    if month_day_match:
        month = int(month_day_match.group(1))
        day = int(month_day_match.group(2))
        year = now.year
        dt = datetime.datetime(year, month, day, 12, 0, 0, tzinfo=datetime.timezone.utc)
        return dt.isoformat()

    # Case: "YY/MM/DD"
    yymmdd_match = re.match(r"^(\d{2})[./\-](\d{1,2})[./\-](\d{1,2})$", raw)
    if yymmdd_match:
        year = 2000 + int(yymmdd_match.group(1))
        month = int(yymmdd_match.group(2))
        day = int(yymmdd_match.group(3))
        dt = datetime.datetime(year, month, day, 12, 0, 0, tzinfo=datetime.timezone.utc)
        return dt.isoformat()

    # Case: "YYYY-MM-DD HH:MM:SS" or "YYYY.MM.DD HH:MM"
    full_match = re.search(r"(\d{4})[./\-](\d{2})[./\-](\d{2})(?:\s+(\d{2}):(\d{2})(?::(\d{2}))?)?", raw)
    if full_match:
        year = int(full_match.group(1))
        month = int(full_match.group(2))
        day = int(full_match.group(3))
        hour = int(full_match.group(4)) if full_match.group(4) else 12
        minute = int(full_match.group(5)) if full_match.group(5) else 0
        second = int(full_match.group(6)) if full_match.group(6) else 0
        dt = datetime.datetime(year, month, day, hour, minute, second, tzinfo=datetime.timezone.utc)
        return dt.isoformat()

    return now.isoformat()


class BobaeDreamCrawler:
    """
    Crawler for BobaeDream automotive community.
    Handles EUC-KR search queries, pagination across national/import/electric boards,
    body extraction from bodyCont, and dynamic AJAX comment extraction.
    """

    def __init__(self, client: Optional[SafeHttpClient] = None):
        self.client = client or SafeHttpClient()
        self._warmed_up = False

    def ensure_warm_up(self):
        """Warm up session cookies on BobaeDream base URL."""
        if not self._warmed_up:
            self.client.warm_up_session(BOBAE_BASE_URL)
            self._warmed_up = True

    def build_search_url(self, board_code: str, keyword: str, page: int = 1) -> str:
        """
        Build search URL with EUC-KR percent-encoded keyword parameter.
        URL format: https://www.bobaedream.co.kr/list?code={board_code}&s_cate=&s_key=sub_bod&search={encoded_kw}&page={page}
        """
        encoded_kw = encode_euc_kr_query(keyword)
        return (
            f"{BOBAE_LIST_URL}?code={board_code}&s_cate=&s_key=sub_bod"
            f"&search={encoded_kw}&page={page}"
        )

    def build_list_url(self, board_code: str, page: int = 1) -> str:
        """
        Build general list URL without search filters.
        URL format: https://www.bobaedream.co.kr/list?code={board_code}&page={page}
        """
        return f"{BOBAE_LIST_URL}?code={board_code}&page={page}"

    def parse_list_page(self, html_content: str, board_code: str) -> List[Dict[str, Any]]:
        """
        Extract post items from a BobaeDream board list view.
        Matches rows containing /view?code={board_code}&No={post_no}.
        """
        items: List[Dict[str, Any]] = []
        seen_nos = set()

        # Regex targeting standard and best article list links
        pattern = r'<a\s+[^>]*href="([^"]*view\?[^"]*code=([^"&]+)[^"]*No=(\d+)[^"]*)"[^>]*>(.*?)</a>'
        matches = re.findall(pattern, html_content, re.IGNORECASE | re.DOTALL)

        for full_href, code, post_no, raw_title in matches:
            if post_no in seen_nos:
                continue
            seen_nos.add(post_no)

            clean_title = clean_html_text(raw_title)
            # Filter out empty or notice (공지) titles
            if not clean_title or len(clean_title) < 2 or "공지" in clean_title:
                continue

            full_url = full_href if full_href.startswith("http") else f"{BOBAE_BASE_URL}{full_href}"

            items.append({
                "post_id": post_no,
                "board_code": code or board_code,
                "url": full_url,
                "title": clean_title,
            })

        # Fallback regex if href parameters are ordered differently: No=123&code=...
        if not items:
            alt_pattern = r'<a\s+[^>]*href="([^"]*view\?[^"]*No=(\d+)[^"]*code=([^"&]+)[^"]*)"[^>]*>(.*?)</a>'
            alt_matches = re.findall(alt_pattern, html_content, re.IGNORECASE | re.DOTALL)
            for full_href, post_no, code, raw_title in alt_matches:
                if post_no in seen_nos:
                    continue
                seen_nos.add(post_no)
                clean_title = clean_html_text(raw_title)
                if not clean_title or len(clean_title) < 2 or "공지" in clean_title:
                    continue
                full_url = full_href if full_href.startswith("http") else f"{BOBAE_BASE_URL}{full_href}"
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
        if not comment_html:
            return comments

        # Pattern 1: <dd id="cmt_..."> or <dd class="...comment...">
        comment_matches = re.findall(r'<dd[^>]*class="[^"]*comment[^"]*"[^>]*>(.*?)</dd>', comment_html, re.DOTALL | re.IGNORECASE)
        if not comment_matches:
            comment_matches = re.findall(r'<dd id="cmt_\d+"[^>]*>(.*?)</dd>', comment_html, re.DOTALL | re.IGNORECASE)
        if not comment_matches:
            # Pattern 2: comment body container
            comment_matches = re.findall(r'<div class="[^"]*comment_memo[^"]*"[^>]*>(.*?)</div>', comment_html, re.DOTALL | re.IGNORECASE)
        if not comment_matches:
            comment_matches = re.findall(r'<li[^>]*class="[^"]*comment[^"]*"[^>]*>(.*?)</li>', comment_html, re.DOTALL | re.IGNORECASE)

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
        # Match load("/board_renew/bulletin/comment_list.php?...")
        match = re.search(
            r'load\(["\'](/board_renew/bulletin/comment_list\.php\?[^"\']+)["\']',
            html_content,
            re.IGNORECASE,
        )
        if match:
            path = match.group(1)
            return f"{BOBAE_BASE_URL}{path}" if path.startswith("/") else path

        # Alternative: match direct comment_list.php URL in any script or data attr
        alt_match = re.search(
            r'["\'](/board_renew/bulletin/comment_list\.php\?[^"\']+)["\']',
            html_content,
            re.IGNORECASE,
        )
        if alt_match:
            path = alt_match.group(1)
            return f"{BOBAE_BASE_URL}{path}" if path.startswith("/") else path

        return None

    def fetch_ajax_comments(self, ajax_url: str, referer: str) -> List[str]:
        """Fetch and parse dynamic comments from comment_list.php."""
        try:
            status, text, _ = self.client.get(
                ajax_url,
                referer=referer,
                headers={"X-Requested-With": "XMLHttpRequest"},
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
        # 1. Post ID
        if not post_id:
            no_match = re.search(r"No=(\d+)", post_url)
            post_id = no_match.group(1) if no_match else ""

        # 2. Title
        title = ""
        title_match = re.search(r'<strong class="title"[^>]*>(.*?)</strong>', html_content, re.DOTALL | re.IGNORECASE)
        if not title_match:
            title_match = re.search(r'<dt[^>]*class="tit"[^>]*>(.*?)</dt>', html_content, re.DOTALL | re.IGNORECASE)
        if not title_match:
            title_match = re.search(r'<meta property="og:title" content="([^"]*)"', html_content, re.IGNORECASE)
        if title_match:
            title = clean_html_text(title_match.group(1))

        # 3. Author & Date
        author = ""
        author_match = re.search(r'<span class="author"[^>]*>(.*?)</span>', html_content, re.DOTALL | re.IGNORECASE)
        if not author_match:
            author_match = re.search(r'<span class="userNick"[^>]*>(.*?)</span>', html_content, re.DOTALL | re.IGNORECASE)
        if author_match:
            author = clean_html_text(author_match.group(1))

        raw_date = ""
        date_match = re.search(r'<td class="date"[^>]*>(.*?)</td>', html_content, re.DOTALL | re.IGNORECASE)
        if date_match:
            raw_date = clean_html_text(date_match.group(1))
        if not raw_date:
            generic_date = re.search(r'(\d{4}[.\-/]\d{2}[.\-/]\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?)', html_content)
            if generic_date:
                raw_date = generic_date.group(1)

        created_at_iso = _normalize_iso_timestamp(raw_date)

        # 4. Article body from bodyCont
        content = ""
        # Primary container: <div class="bodyCont" ...> ... </div> <!-- //bodyCont
        body_match = re.search(r'<div class="bodyCont"[^>]*>(.*?)</div>\s*<!--\s*//bodyCont', html_content, re.DOTALL | re.IGNORECASE)
        if not body_match:
            # Secondary: un-commented bodyCont
            body_match = re.search(r'<div class="bodyCont"[^>]*>(.*?)</div>', html_content, re.DOTALL | re.IGNORECASE)
        if not body_match:
            body_match = re.search(r'<div id="print_area"[^>]*>(.*?)</div>', html_content, re.DOTALL | re.IGNORECASE)
        if not body_match:
            body_match = re.search(r'<div class="content01"[^>]*>(.*?)</div>', html_content, re.DOTALL | re.IGNORECASE)

        if body_match:
            content = clean_html_text(body_match.group(1))

        # 5. Comments (Static + Dynamic AJAX)
        comments: List[str] = []
        # First try dynamic AJAX comment URL extraction
        ajax_cmt_url = self.extract_ajax_comment_url(html_content)
        if ajax_cmt_url:
            comments = self.fetch_ajax_comments(ajax_cmt_url, referer=post_url)

        # Fallback to static comments parsed from page HTML if AJAX gave nothing
        if not comments:
            comments = self.parse_comments_html(html_content)

        return {
            "platform": "bobaedream",
            "post_id": str(post_id),
            "url": post_url,
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
    ) -> Optional[Dict[str, Any]]:
        """Fetch and parse a single post by URL."""
        self.ensure_warm_up()
        status, text, _ = self.client.get(post_url, referer=f"{BOBAE_BASE_URL}/")
        if status != 200 or not text:
            logger.warning(f"Failed to fetch BobaeDream post: {post_url} (status: {status})")
            return None

        return self.parse_post_detail(text, post_url, board_code=board_code, post_id=post_id or "")

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
        self.ensure_warm_up()
        results: List[Dict[str, Any]] = []

        for page in range(1, pages + 1):
            url = self.build_list_url(board_code, page=page)
            logger.info(f"Crawling BobaeDream [{board_code}] list (Page {page}): {url}")
            status, text, _ = self.client.get(url, referer=f"{BOBAE_BASE_URL}/")
            if status != 200 or not text:
                logger.warning(f"Failed to fetch list for {board_code} page {page}")
                break

            items = self.parse_list_page(text, board_code)
            if not items:
                logger.info(f"No more items in BobaeDream [{board_code}] page {page}")
                break

            for item in items:
                post = self.fetch_post(item["url"], board_code=board_code, post_id=item["post_id"])
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
        self.ensure_warm_up()
        results: List[Dict[str, Any]] = []

        for page in range(1, pages + 1):
            url = self.build_search_url(board_code, keyword, page=page)
            logger.info(f"Searching BobaeDream [{board_code}] for '{keyword}' (Page {page}): {url}")
            status, text, _ = self.client.get(url, referer=f"{BOBAE_BASE_URL}/")
            if status != 200 or not text:
                logger.warning(f"Search request failed for {board_code} keyword '{keyword}' page {page}")
                break

            items = self.parse_list_page(text, board_code)
            if not items:
                logger.info(f"No search results found in {board_code} for '{keyword}' page {page}")
                break

            for item in items:
                post = self.fetch_post(item["url"], board_code=board_code, post_id=item["post_id"])
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
        target_boards = boards or ["national", "import", "electric"]
        all_posts: List[Dict[str, Any]] = []

        for board in target_boards:
            board_posts = self.search_board(board, keyword, pages=max_pages, limit=limit)
            all_posts.extend(board_posts)
            if limit and len(all_posts) >= limit:
                return all_posts[:limit]

        return all_posts
