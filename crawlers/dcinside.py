"""
DCInside Gallery Crawler & AJAX Comment Harvester.
Supports UTF-8 search queries across car_new1 (Major) and electriccar (Mini/Minor) galleries,
list parsing from ub-content table rows, post body extraction from write_div,
session token (e_s_n_o) extraction, and AJAX comment extraction from /board/comment/.
Returns structured raw post dictionaries adhering to PROJECT.md § Interface Contracts.
"""

import datetime
import json
import logging
import re
import urllib.parse
from typing import Any, Dict, List, Optional

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


def _normalize_iso_timestamp(raw_date_str: str) -> str:
    """Normalize timestamp into ISO-8601 string."""
    raw = raw_date_str.strip()
    if not raw:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    now = datetime.datetime.now(datetime.timezone.utc)

    # Full timestamp: "2026-09-08 10:11:21" or "2026.09.08 10:11"
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

    # Time only: "10:11"
    time_match = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", raw)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
        second = int(time_match.group(3)) if time_match.group(3) else 0
        dt = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
        return dt.isoformat()

    # Month-day: "09.08"
    md_match = re.match(r"^(\d{1,2})[./\-](\d{1,2})$", raw)
    if md_match:
        month = int(md_match.group(1))
        day = int(md_match.group(2))
        dt = datetime.datetime(now.year, month, day, 12, 0, 0, tzinfo=datetime.timezone.utc)
        return dt.isoformat()

    return now.isoformat()


class DCInsideCrawler:
    """
    Crawler for DCInside galleries.
    Handles UTF-8 search queries, gallery pagination across car_new1 and electriccar,
    ub-content list parsing, write_div post body extraction, and AJAX comment extraction
    using e_s_n_o session tokens.
    """

    def __init__(self, client: Optional[SafeHttpClient] = None):
        self.client = client or SafeHttpClient()
        self._warmed_up = False

    def ensure_warm_up(self):
        """Warm up session cookies on DCInside base URL."""
        if not self._warmed_up:
            self.client.warm_up_session(DC_BASE_URL)
            self._warmed_up = True

    def get_gallery_prefix(self, gallery_id: str) -> str:
        """Determine URL route prefix for the gallery (board, mini/board, mgallery/board)."""
        info = DC_GALLERIES.get(gallery_id)
        if info:
            return info["prefix"]
        # Default heuristic: fallback to mgallery/board for unknown minor galleries
        return "board" if gallery_id == "car_new1" else "mgallery/board"

    def build_list_url(self, gallery_id: str, page: int = 1) -> str:
        """Build standard gallery list URL."""
        prefix = self.get_gallery_prefix(gallery_id)
        return f"{DC_BASE_URL}/{prefix}/lists/?id={gallery_id}&page={page}"

    def build_search_url(self, gallery_id: str, keyword: str, page: int = 1) -> str:
        """Build UTF-8 encoded search URL."""
        prefix = self.get_gallery_prefix(gallery_id)
        encoded_kw = urllib.parse.quote(keyword)
        return (
            f"{DC_BASE_URL}/{prefix}/lists/?"
            f"id={gallery_id}&s_type=search_subject_memo&s_keyword={encoded_kw}&page={page}"
        )

    def build_post_url(self, gallery_id: str, post_id: str) -> str:
        """Build canonical desktop view URL for a post."""
        prefix = self.get_gallery_prefix(gallery_id)
        return f"{DC_BASE_URL}/{prefix}/view/?id={gallery_id}&no={post_id}"

    def parse_gallery_list(self, html_content: str, gallery_id: str) -> List[Dict[str, Any]]:
        """
        Extract post items from DCInside gallery list HTML.
        Specifically searches for table rows with class ub-content:
          <tr class="ub-content us-post" data-no="11503496">
            ...
            <td class="gall_tit ub-word"><a href="...">제목</a></td>
            <td class="gall_date" title="2026-09-08 10:11:21">10:11</td>
          </tr>
        """
        items: List[Dict[str, Any]] = []
        seen_nos = set()

        # Regex targeting table rows with data-no or ub-content
        row_regex = re.compile(
            r'<tr[^>]*class="[^"]*ub-content[^"]*"[^>]*data-no="(\d+)"[^>]*>(.*?)</tr>',
            re.DOTALL | re.IGNORECASE,
        )

        for match in row_regex.finditer(html_content):
            post_no = match.group(1)
            row_html = match.group(2)

            if post_no in seen_nos:
                continue
            seen_nos.add(post_no)

            # Extract title & href from gall_tit
            title_match = re.search(
                r'<td[^>]*class="[^"]*gall_tit[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
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
                r'<td[^>]*class="[^"]*gall_date[^"]*"[^>]*title="([^"]*)"',
                row_html,
                re.IGNORECASE,
            )
            if date_match:
                raw_date = date_match.group(1)
            else:
                date_text_match = re.search(
                    r'<td[^>]*class="[^"]*gall_date[^"]*"[^>]*>(.*?)</td>',
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
                r'<a[^>]*href="([^"]*/view/\?id=[^"&]+&no=(\d+)[^"]*)"[^>]*>(.*?)</a>',
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
        Example in HTML:
          <input type="hidden" id="e_s_n_o" name="e_s_n_o" value="abc123xyz...">
        """
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
    ) -> List[str]:
        """
        Fetch dynamic comments via DCInside internal AJAX comment endpoint:
        POST https://gall.dcinside.com/{prefix}/comment/
        """
        if not e_s_n_o:
            return []

        prefix = self.get_gallery_prefix(gallery_id)
        ajax_url = f"{DC_BASE_URL}/{prefix}/comment/"

        form_data = {
            "id": gallery_id,
            "no": post_id,
            "cmt_id": gallery_id,
            "cmt_no": post_id,
            "e_s_n_o": e_s_n_o,
            "comment_page": "1",
        }

        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Referer": post_url,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }

        try:
            status, text, _ = self.client.post(
                ajax_url,
                data=form_data,
                headers=headers,
                referer=post_url,
            )
            if status == 200 and text:
                return self.parse_comment_json(text)
        except Exception as e:
            logger.warning(f"Failed to fetch DC AJAX comments ({gallery_id}/{post_id}): {e}")

        return []

    def parse_comment_json(self, json_text: str) -> List[str]:
        """Parse comment strings from DCInside comment API JSON response."""
        comments: List[str] = []
        try:
            data = json.loads(json_text)
            # Response may contain a list of comments under 'comments' or direct list
            items = data.get("comments", []) if isinstance(data, dict) else data
            if not isinstance(items, list):
                return comments

            for item in items:
                if not isinstance(item, dict):
                    continue
                memo = item.get("memo", "") or item.get("comment_memo", "")
                cleaned = clean_html_text(memo)
                if cleaned and len(cleaned) >= 2 and not cleaned.startswith("보이스리플"):
                    comments.append(cleaned)
        except Exception as e:
            logger.debug(f"JSON comment parse notice: {e}")

        return comments

    def parse_post_detail(
        self,
        html_content: str,
        post_url: str,
        gallery_id: str = "car_new1",
        post_id: str = "",
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
        # 1. Post ID
        if not post_id:
            no_match = re.search(r"no=(\d+)", post_url)
            post_id = no_match.group(1) if no_match else ""

        # 2. Title
        title = ""
        title_match = re.search(r'<span class="title_subject"[^>]*>(.*?)</span>', html_content, re.DOTALL | re.IGNORECASE)
        if not title_match:
            title_match = re.search(r'<span class="title_headtext"[^>]*>.*?</span>\s*<span[^>]*>(.*?)</span>', html_content, re.DOTALL | re.IGNORECASE)
        if not title_match:
            title_match = re.search(r'<meta property="og:title" content="([^"]*)"', html_content, re.IGNORECASE)
        if title_match:
            title = clean_html_text(title_match.group(1))

        # 3. Author & Date
        author = ""
        writer_match = re.search(r'<td class="gall_writer[^"]*"[^>]*>.*?<span class="nickname"[^>]*>(.*?)</span>', html_content, re.DOTALL | re.IGNORECASE)
        if writer_match:
            author = clean_html_text(writer_match.group(1))
        ip_match = re.search(r'<span class="ip"[^>]*>\(([0-9.*]+)\)</span>', html_content)
        if ip_match:
            author = f"{author or 'ㅇㅇ'} ({ip_match.group(1)})"

        raw_date = ""
        date_match = re.search(r'<span class="gall_date"[^>]*title="([^"]*)"', html_content, re.IGNORECASE)
        if date_match:
            raw_date = date_match.group(1)
        if not raw_date:
            date_match2 = re.search(r'<span class="gall_date"[^>]*>(.*?)</span>', html_content, re.IGNORECASE)
            if date_match2:
                raw_date = clean_html_text(date_match2.group(1))
        if not raw_date:
            generic_date = re.search(r'(\d{4}[.\-/]\d{2}[.\-/]\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?)', html_content)
            if generic_date:
                raw_date = generic_date.group(1)

        created_at_iso = _normalize_iso_timestamp(raw_date)

        # 4. Article body from write_div
        content = ""
        # Primary container: <div class="write_div" ...> ... </div>
        body_match = re.search(r'<div class="write_div"[^>]*>(.*?)</div>', html_content, re.DOTALL | re.IGNORECASE)
        if not body_match:
            body_match = re.search(r'<div class="writing_view_box"[^>]*>(.*?)</div>\s*<!--\s*//writing_view_box', html_content, re.DOTALL | re.IGNORECASE)
        if not body_match:
            body_match = re.search(r'<div class="thum-txt[^"]*"[^>]*>(.*?)</div>', html_content, re.DOTALL | re.IGNORECASE)

        if body_match:
            content = clean_html_text(body_match.group(1))

        # 5. Dynamic AJAX comments using e_s_n_o
        comments: List[str] = []
        e_s_n_o = self.extract_esno_token(html_content)
        if e_s_n_o and post_id:
            comments = self.fetch_ajax_comments(gallery_id, post_id, e_s_n_o, post_url=post_url)

        # Fallback to static comments in DOM if AJAX comments were empty
        if not comments:
            dom_comments = re.findall(r'<p class="usertxt[^"]*"[^>]*>(.*?)</p>', html_content, re.DOTALL | re.IGNORECASE)
            if not dom_comments:
                dom_comments = re.findall(r'<dd class="usertxt[^"]*"[^>]*>(.*?)</dd>', html_content, re.DOTALL | re.IGNORECASE)
            for c_html in dom_comments:
                cleaned = clean_html_text(c_html)
                if cleaned and len(cleaned) >= 2 and not cleaned.startswith("보이스리플"):
                    comments.append(cleaned)

        return {
            "platform": "dcinside",
            "post_id": str(post_id),
            "url": post_url,
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
    ) -> Optional[Dict[str, Any]]:
        """Fetch and parse a single post from DCInside."""
        self.ensure_warm_up()
        status, text, _ = self.client.get(post_url, referer=f"{DC_BASE_URL}/")
        if status != 200 or not text:
            # Try fallback to mobile view URL
            if post_id:
                mobile_url = f"{DC_MOBILE_BASE_URL}/board/{gallery_id}/{post_id}"
                m_status, m_text, _ = self.client.get(
                    mobile_url,
                    referer=f"{DC_MOBILE_BASE_URL}/",
                    headers={
                        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1"
                    },
                )
                if m_status == 200 and m_text:
                    return self.parse_post_detail(m_text, post_url, gallery_id=gallery_id, post_id=post_id)

            logger.warning(f"Failed to fetch DCInside post: {post_url} (status: {status})")
            return None

        return self.parse_post_detail(text, post_url, gallery_id=gallery_id, post_id=post_id or "")

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
        self.ensure_warm_up()
        results: List[Dict[str, Any]] = []

        for page in range(1, pages + 1):
            url = self.build_list_url(gallery_id, page=page)
            logger.info(f"Crawling DCInside [{gallery_id}] list (Page {page}): {url}")
            status, text, _ = self.client.get(url, referer=f"{DC_BASE_URL}/")
            if status != 200 or not text:
                logger.warning(f"Failed to fetch list for DC [{gallery_id}] page {page}")
                break

            items = self.parse_gallery_list(text, gallery_id)
            if not items:
                logger.info(f"No more items in DCInside [{gallery_id}] page {page}")
                break

            for item in items:
                post = self.fetch_post(item["url"], gallery_id=gallery_id, post_id=item["post_id"])
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
        self.ensure_warm_up()
        results: List[Dict[str, Any]] = []

        for page in range(1, pages + 1):
            url = self.build_search_url(gallery_id, keyword, page=page)
            logger.info(f"Searching DCInside [{gallery_id}] for '{keyword}' (Page {page}): {url}")
            status, text, _ = self.client.get(url, referer=f"{DC_BASE_URL}/")
            if status != 200 or not text:
                logger.warning(f"Search request failed for DC [{gallery_id}] keyword '{keyword}' page {page}")
                break

            items = self.parse_gallery_list(text, gallery_id)
            if not items:
                logger.info(f"No items found for DC [{gallery_id}] keyword '{keyword}' page {page}")
                break

            for item in items:
                post = self.fetch_post(item["url"], gallery_id=gallery_id, post_id=item["post_id"])
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
        target_galleries = galleries or ["car_new1", "electriccar"]
        all_posts: List[Dict[str, Any]] = []

        for gall in target_galleries:
            gall_posts = self.search_gallery(gall, keyword, pages=max_pages, limit=limit)
            all_posts.extend(gall_posts)
            if limit and len(all_posts) >= limit:
                return all_posts[:limit]

        return all_posts
