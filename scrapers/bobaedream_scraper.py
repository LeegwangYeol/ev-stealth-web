"""
Bobaedream Community Forum Multi-Board Scraper and Parser.
Searches and extracts posts, comments, and authentic user complaints regarding Chinese EVs.
Handles EUC-KR keyword encoding, session cookie warm-up, multi-board routing, and DOM parsing.
"""

import argparse
import hashlib
import html
import json
import logging
import os
import random
import re
import sys
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple, Union

# Ensure parent directory is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.common_utils import (
    COMMON_CATEGORY_KEYWORDS,
    COMMON_VEHICLE_PATTERNS,
    ComplaintRecord,
    SafeHttpClient,
    bounded_cache_set,
    classify_ev_text,
    clean_html_text,
    determine_complaint_severity,
    encode_euc_kr_query,
    extract_balanced_tag_content,
    extract_defect_topic,
    extract_meta_content,
    extract_slang_terms,
    is_allowed_domain_url,
    load_platform_seed_records,
    normalize_scraper_url,
    polite_delay,
    resolve_timeout_pair,
    robust_decode,
    safe_non_negative_int,
    save_complaints_json,
    strip_non_body_html,
)

logger = logging.getLogger("BobaedreamScraper")

BOBAE_BASE_URL = "https://www.bobaedream.co.kr"
BOBAE_SEARCH_URL = "https://www.bobaedream.co.kr/search"
BOBAE_LIST_URL = "https://www.bobaedream.co.kr/list"

# Board codes and Korean display names
BOBAE_BOARDS = {
    "national": "보배드림 국산차게시판",
    "import": "보배드림 수입차게시판",
    "freeb": "보배드림 자유게시판",
    "battle": "보배드림 시승기/배틀/찍찍",
    "electric": "보배드림 전기차게시판",
    "accident": "보배드림 교통사고/블랙박스",
    "cnews": "보배드림 자동차뉴스/토론",
}

# Keyword dictionary for category classification across all 5 categories
CATEGORY_KEYWORDS = COMMON_CATEGORY_KEYWORDS

# Multi-brand vehicle patterns across Tesla, Hyundai, Kia, Genesis, BYD, Mercedes, BMW, Porsche, Polestar, GM
VEHICLE_PATTERNS = COMMON_VEHICLE_PATTERNS


class BobaedreamScraper:
    """Multi-board scraper and parser for Bobaedream automotive forum."""

    def __init__(
        self,
        client: Optional[SafeHttpClient] = None,
        slang_path: Optional[str] = None,
        timeout: Union[float, Tuple[float, float]] = (5.0, 15.0),
        connect_timeout: Optional[float] = None,
        read_timeout: Optional[float] = None,
        enable_cache: bool = True,
        cache_fallback: bool = True,
    ):
        # Enforce polite delay with jitter (2.0s - 4.0s) and burst cooldown
        self._owns_client = client is None
        self.timeout = timeout
        self.connect_timeout, self.read_timeout = resolve_timeout_pair(
            timeout=timeout,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
        )
        self.enable_cache = enable_cache
        self.cache_fallback = cache_fallback
        self.client = client or SafeHttpClient(
            min_delay=2.0,
            max_delay=4.0,
            connect_timeout=self.connect_timeout,
            read_timeout=self.read_timeout,
            enable_cache=self.enable_cache,
            cache_fallback=self.cache_fallback,
        )
        self.min_delay = 2.0
        self.max_delay = 4.0
        self.slang_path = slang_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "slang_dict.json"
        )
        self.slang_dict = self._load_slang_dict()
        self.post_cache: Dict[str, Dict[str, Any]] = {}
        self._warmed_up = False

    def close(self, force: bool = False) -> None:
        """Release HTTP client resources if owned by this scraper."""
        if (self._owns_client or force) and self.client is not None and hasattr(self.client, "close"):
            try:
                self.client.close()
            except Exception as e:
                logger.warning(f"Error closing HTTP client: {e}")

    def __del__(self) -> None:
        try:
            if getattr(self, "_owns_client", False):
                self.close()
        except Exception:
            pass

    def __enter__(self) -> "BobaedreamScraper":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.close()
        return False

    def sleep_polite(self):
        """Randomized sleep with jitter between requests."""
        polite_delay(self.min_delay, self.max_delay)

    def _load_slang_dict(self) -> Dict[str, Any]:
        if os.path.exists(self.slang_path):
            try:
                with open(self.slang_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content:
                    data = json.loads(content)
                    if isinstance(data, dict):
                        return data
                    if isinstance(data, list):
                        return {str(item): {} for item in data}
            except Exception as e:
                logger.warning(f"Failed to load slang dictionary from {self.slang_path}: {e}")
        return {}

    def ensure_warm_up(self):
        """Warm up session cookie jar on Bobaedream."""
        if not self._warmed_up:
            if self.client and hasattr(self.client, "warm_up_session"):
                self.client.warm_up_session(BOBAE_BASE_URL)
            self._warmed_up = True

    def search_board(
        self,
        board_code: str,
        keyword: str,
        s_key: str = "sub_bod",
        max_pages: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Search a specific Bobaedream board using EUC-KR GET list search.
        URL: https://www.bobaedream.co.kr/list?code={board_code}&s_cate=&s_key={s_key}&search={encoded_kw}&page={page}
        """
        self.ensure_warm_up()
        results = []
        kw_str = str(keyword or "")
        safe_code = urllib.parse.quote(str(board_code or "national").strip(), safe="")
        safe_s_key = urllib.parse.quote(str(s_key or "sub_bod").strip(), safe="")
        try:
            eff_pages = max(1, int(max_pages))
        except (ValueError, TypeError, OverflowError):
            eff_pages = 1

        seen_nos = set()
        for page in range(1, eff_pages + 1):
            try:
                encoded_kw = urllib.parse.quote(kw_str.encode("euc-kr"))
            except UnicodeEncodeError:
                encoded_kw = urllib.parse.quote(kw_str.encode("cp949", errors="replace"))

            search_url = f"{BOBAE_LIST_URL}?code={safe_code}&s_cate=&s_key={safe_s_key}&search={encoded_kw}&page={page}"
            logger.info(f"Searching Bobaedream [{board_code}] for '{kw_str}' (Page {page})...")

            status, text, raw = self.client.request(
                search_url,
                method="GET",
                referer=f"{BOBAE_BASE_URL}/",
                encoding=None,
                connect_timeout=self.connect_timeout,
                read_timeout=self.read_timeout,
            )

            if status != 200 or not text:
                logger.warning(f"Board search request failed for [{board_code}] keyword '{keyword}' on page {page}")
                break

            items = self.parse_board_list(text, board_code)
            if not items:
                logger.info(f"No more items in [{board_code}] for '{keyword}' on page {page}")
                break

            new_items = [it for it in items if not it.get("post_no") or it["post_no"] not in seen_nos]
            if not new_items:
                logger.info(f"Page {page} of [{board_code}] repeated previously seen items. Halting loop.")
                break
            seen_nos.update(it["post_no"] for it in new_items if it.get("post_no"))
            results.extend(new_items)

        logger.info(f"Found {len(results)} items in Bobaedream [{board_code}] for '{keyword}'.")
        return results

    def parse_board_list(self, html_content: str, board_code: str) -> List[Dict[str, Any]]:
        """Extract post items from a Bobaedream board list view."""
        if not html_content or not isinstance(html_content, str):
            return []
        items = []
        # Match list entries with view links without polynomial regex backtracking
        pattern = r'<a\b[^>]*\bhref=["\']([^"\'>\s]*view(?:\.php)?\?[^"\'>\s]*)["\'][^>]*>(.*?)</a>'
        matches = re.findall(pattern, html_content, re.IGNORECASE | re.DOTALL)

        seen_nos = set()
        for href, raw_title in matches:
            if not re.search(r"(?:^|[?&])(?:amp;)?code=[a-zA-Z0-9_]+", href, re.IGNORECASE):
                continue
            no_match = re.search(r"[?&](?:amp;)?no=(\d+)", href, re.IGNORECASE)
            if not no_match:
                continue
            post_no = no_match.group(1)
            if post_no in seen_nos:
                continue
            seen_nos.add(post_no)

            clean_title = clean_html_text(raw_title)
            if (
                not clean_title
                or len(clean_title) < 2
                or re.match(r"^(?:\[공지\]|공지(?:\s|$|:|-)|\[필독\])", clean_title)
            ):
                continue

            full_url = normalize_scraper_url(href, BOBAE_BASE_URL)
            if not full_url or not is_allowed_domain_url(full_url, ("bobaedream.co.kr",)):
                continue
            items.append({
                "title": clean_title,
                "url": full_url,
                "board_code": board_code,
                "board_name": BOBAE_BOARDS.get(board_code, f"보배드림 ({board_code})"),
                "post_no": post_no
            })

        return items

    def search(self, keyword: str, max_pages: int = 2) -> List[Dict[str, Any]]:
        """
        Search Bobaedream community-wide using EUC-KR encoded POST form request.
        Returns list of found article items.
        """
        self.ensure_warm_up()
        results = []
        kw_str = str(keyword or "")
        try:
            eff_pages = max(1, int(max_pages))
        except (ValueError, TypeError, OverflowError):
            eff_pages = 1

        seen_urls = set()
        for page in range(1, eff_pages + 1):
            logger.info(f"Searching Bobaedream community search for '{kw_str}' (Page {page})...")
            post_data = encode_euc_kr_query({
                "keyword": kw_str,
                "searchName": "커뮤니티",
                "page": page,
            })

            status, text, raw = self.client.request(
                BOBAE_SEARCH_URL,
                method="POST",
                data=post_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                referer=BOBAE_BASE_URL + "/",
                encoding=None,
                connect_timeout=self.connect_timeout,
                read_timeout=self.read_timeout,
            )

            if status != 200 or not text:
                logger.warning(f"Search request failed for keyword '{keyword}' on page {page}")
                break

            items = self.parse_search_results(text)
            if not items:
                logger.info(f"No more search results for '{keyword}' on page {page}")
                break

            new_items = [it for it in items if it.get("url") not in seen_urls]
            if not new_items:
                logger.info(f"Search page {page} repeated previously seen items. Halting loop.")
                break
            seen_urls.update(it["url"] for it in new_items if it.get("url"))
            results.extend(new_items)

        logger.info(f"Found {len(results)} search items for keyword '{keyword}' on Bobaedream.")
        return results

    def parse_search_results(self, html_content: str) -> List[Dict[str, Any]]:
        """Parse search results page HTML and extract post metadata."""
        if not html_content or not isinstance(html_content, str):
            return []
        items = []
        seen_keys = set()
        pattern = r'<dt[^>]*>\s*<a\b[^>]*\bhref=["\']([^"\']*view(?:\.php)?\?[^"\']*)["\'][^>]*>(.*?)</a>'
        matches = re.findall(pattern, html_content, re.IGNORECASE | re.DOTALL)

        for href, raw_title in matches:
            clean_title = clean_html_text(raw_title)
            if not clean_title or len(clean_title) < 2:
                continue

            full_url = normalize_scraper_url(href, BOBAE_BASE_URL)
            if not full_url or not is_allowed_domain_url(full_url, ("bobaedream.co.kr",)):
                continue
            code_match = re.search(r"[?&]code=([a-zA-Z0-9_]+)", full_url, re.IGNORECASE)
            no_match = re.search(r"[?&]no=([0-9]+)", full_url, re.IGNORECASE)
            board_code = code_match.group(1) if code_match else "community"
            post_no = no_match.group(1) if no_match else ""
            dedup_key = f"{board_code}:{post_no}" if post_no else full_url
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            items.append({
                "title": clean_title,
                "url": full_url,
                "board_code": board_code,
                "board_name": BOBAE_BOARDS.get(board_code, f"보배드림 ({board_code})"),
                "post_no": post_no
            })

        return items

    def fetch_post_detail(self, post_url: str) -> Dict[str, Any]:
        """Fetch and parse post detail page including author, date, body, and comments."""
        norm_url = normalize_scraper_url(post_url, BOBAE_BASE_URL)
        if not norm_url:
            logger.warning(f"Invalid Bobaedream post_url provided: {post_url!r}")
            return {}
        self.ensure_warm_up()
        status, text, raw = self.client.request(
            norm_url,
            method="GET",
            referer=BOBAE_BASE_URL + "/",
            encoding=None,
            connect_timeout=self.connect_timeout,
            read_timeout=self.read_timeout,
        )

        if status != 200 or not text:
            if norm_url in self.post_cache:
                logger.warning(f"Failed to fetch Bobaedream post detail for {norm_url}; falling back to cached post.")
                return self.post_cache[norm_url]
            logger.warning(f"Failed to fetch post detail: {norm_url}")
            return {}

        try:
            detail = self.parse_post_detail(text, norm_url)
            if detail:
                bounded_cache_set(self.post_cache, norm_url, detail)
            return detail
        except Exception as e:
            logger.warning(f"Error parsing Bobaedream post detail ({norm_url}): {e}")
            if norm_url in self.post_cache:
                logger.warning(f"Falling back to cached post for {norm_url} after parse error.")
                return self.post_cache[norm_url]
            return {}

    def parse_post_detail(self, html_content: str, post_url: str) -> Dict[str, Any]:
        """Extract title, metadata, body text, and comments from Bobaedream post HTML."""
        if not html_content or not isinstance(html_content, str):
            return {}
        # Title extraction
        title = ""
        title_match = re.search(
            r'<strong\b[^>]*\bclass=["\'][^"\']*\btitle\b[^"\']*["\'][^>]*>(.*?)</strong>',
            html_content,
            re.DOTALL | re.IGNORECASE,
        )
        if not title_match:
            title_match = re.search(
                r'<dt\b[^>]*\bclass=["\'][^"\']*\btit\b[^"\']*["\'][^>]*>(.*?)</dt>',
                html_content,
                re.DOTALL | re.IGNORECASE,
            )
        if title_match:
            title = clean_html_text(title_match.group(1))
        if not title:
            title = extract_meta_content(html_content, "og:title")

        # Metadata extraction (author, date, views)
        author = ""
        author_match = re.search(
            r'<span\b[^>]*\bclass=["\'][^"\']*\bauthor\b[^"\']*["\'][^>]*>(.*?)</span>',
            html_content,
            re.DOTALL | re.IGNORECASE,
        )
        if not author_match:
            author_match = re.search(
                r'<span\b[^>]*\bclass=["\'][^"\']*\buserNick\b[^"\']*["\'][^>]*>(.*?)</span>',
                html_content,
                re.DOTALL | re.IGNORECASE,
            )
        if author_match:
            author = clean_html_text(author_match.group(1))

        body_html_region = strip_non_body_html(html_content)
        published_at = ""
        date_container = re.search(
            r'<span\b[^>]*\bclass=["\'][^"\']*\b(?:countGroup|date|regdate|writerInfo)\b[^"\']*["\'][^>]*>(.*?)</span>',
            body_html_region,
            re.DOTALL | re.IGNORECASE,
        )
        date_search_target = date_container.group(1) if date_container else body_html_region
        date_match = re.search(r'(\d{4}[.\-/]\d{2}[.\-/]\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?)', date_search_target)
        if not date_match and date_container:
            date_match = re.search(r'(\d{4}[.\-/]\d{2}[.\-/]\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?)', body_html_region)
        if date_match:
            published_at = date_match.group(1).replace(".", "-").replace("/", "-")

        view_count = 0
        view_match = (
            re.search(r'조회수?\s*[:]?\s*(?:<[^>]+>\s*)*([0-9,]+)', date_container.group(1))
            if date_container
            else None
        )
        if not view_match:
            view_match = re.search(r'조회수?\s*[:]?\s*(?:<[^>]+>\s*)*([0-9,]+)', body_html_region)
        if view_match:
            try:
                view_count = int(view_match.group(1).replace(",", ""))
            except ValueError:
                pass

        upvote_count = 0
        upvote_match = (
            re.search(r'추천\s*[:]?\s*(?:<[^>]+>\s*)*([0-9,]+)', date_container.group(1))
            if date_container
            else None
        )
        if not upvote_match:
            upvote_match = re.search(r'추천\s*[:]?\s*(?:<[^>]+>\s*)*([0-9,]+)', body_html_region)
        if upvote_match:
            try:
                upvote_count = int(upvote_match.group(1).replace(",", ""))
            except ValueError:
                pass

        # Body extraction
        body_text = ""
        for open_pat in (
            r'<div\b[^>]*\bclass=["\'][^"\']*\bbodyCont\b[^"\']*["\'][^>]*>',
            r'<div\b[^>]*\bid=["\']print_area["\'][^>]*>',
            r'<div\b[^>]*\bclass=["\'][^"\']*\bcontent01\b[^"\']*["\'][^>]*>',
        ):
            inner_html = extract_balanced_tag_content(body_html_region, open_pat, tag_name="div")
            if inner_html:
                body_text = clean_html_text(inner_html)
                if body_text:
                    break
        if not body_text:
            body_match = re.search(
                r'<div\b[^>]*\bclass=["\'][^"\']*\bbodyCont\b[^"\']*["\'][^>]*>(.*?)</div>\s*<!--\s*//bodyCont',
                html_content,
                re.DOTALL | re.IGNORECASE,
            )
            if body_match:
                body_text = clean_html_text(body_match.group(1))

        # Comments extraction
        comments = []
        comment_matches = re.findall(
            r'<dd\b[^>]*\bclass=["\'][^"\']*comment[^"\']*["\'][^>]*>((?:(?!</?dd\b).)*?)</dd>',
            html_content,
            re.DOTALL | re.IGNORECASE,
        )
        if not comment_matches:
            comment_matches = re.findall(
                r'<dd\b[^>]*\bid=["\']cmt_\d+["\'][^>]*>((?:(?!</?dd\b).)*?)</dd>',
                html_content,
                re.DOTALL | re.IGNORECASE,
            )

        for c_html in comment_matches:
            cleaned_c = clean_html_text(c_html)
            if cleaned_c and len(cleaned_c) > 5 and not cleaned_c.startswith("신고"):
                comments.append(cleaned_c)

        return {
            "url": post_url,
            "title": title,
            "author": author,
            "published_at": published_at,
            "view_count": view_count,
            "upvote_count": upvote_count,
            "body": body_text,
            "comments": comments
        }

    def classify_text(self, text: str) -> Tuple[str, Optional[str]]:
        """
        Classify text to identify:
        1. Target Vehicle
        2. Category (parking, charging, rain_driving, hill_climbing)
        """
        return classify_ev_text(text, vehicle_patterns=VEHICLE_PATTERNS, category_keywords=CATEGORY_KEYWORDS)

    def extract_complaint_records(
        self,
        post_data: Dict[str, Any],
        board_name: Optional[str] = None
    ) -> List[ComplaintRecord]:
        """
        Convert post and comments into standardized ComplaintRecord objects.
        """
        if not post_data or not isinstance(post_data, dict):
            return []
        records = []
        url = str(post_data.get("url") or "")
        title = str(post_data.get("title") or "")
        body = str(post_data.get("body") or "")
        raw_comments = post_data.get("comments")
        comments = raw_comments if isinstance(raw_comments, list) else []
        b_name = board_name or "보배드림 커뮤니티"
        published_at = str(post_data.get("published_at") or "")
        author = str(post_data.get("author") or "보배드림 유저")

        # Check post body
        combined_post = f"{title}\n{body}"
        veh, cat = self.classify_text(combined_post)
        if cat and len(body) >= 20:
            slang = extract_slang_terms(combined_post, self.slang_dict)
            rec_id = f"BOBAE_{cat.upper()[:4]}_{int(hashlib.sha256(url.encode('utf-8', errors='replace')).hexdigest(), 16) % 100000:05d}"
            severity = self._determine_severity(cat, combined_post)
            topic = self._extract_defect_topic(cat, combined_post)
            records.append(ComplaintRecord(
                id=rec_id,
                platform="bobaedream",
                board_name=b_name,
                post_url=url,
                post_title=title,
                target_vehicle=veh,
                category=cat,
                defect_topic=topic,
                raw_quote=body[:600],
                slang_terms=slang,
                severity=severity,
                platform_metadata={
                    "author_type": "bobae_user",
                    "author_badge": author,
                    "view_count": safe_non_negative_int(post_data.get("view_count"), 0),
                    "upvote_count": safe_non_negative_int(post_data.get("upvote_count"), 0),
                    "comment_count": len(comments),
                    "published_at": published_at,
                }
            ))

        # Check individual comments
        for idx, comment in enumerate(comments):
            if not isinstance(comment, str):
                continue
            c_veh, c_cat = self.classify_text(comment)
            if c_cat and len(comment) >= 15:
                c_slang = extract_slang_terms(comment, self.slang_dict)
                rec_id = f"BOBAE_{c_cat.upper()[:4]}_{int(hashlib.sha256((url + str(idx)).encode('utf-8', errors='replace')).hexdigest(), 16) % 100000:05d}"
                severity = self._determine_severity(c_cat, comment)
                topic = self._extract_defect_topic(c_cat, comment)
                records.append(ComplaintRecord(
                    id=rec_id,
                    platform="bobaedream",
                    board_name=b_name,
                    post_url=url,
                    post_title=f"[댓글] {title}",
                    target_vehicle=c_veh if c_veh != "BYD EV General" else veh,
                    category=c_cat,
                    defect_topic=topic,
                    raw_quote=comment,
                    slang_terms=c_slang,
                    severity=severity,
                    platform_metadata={
                        "author_type": "bobae_commenter",
                        "author_badge": "댓글 작성자",
                        "view_count": 0,
                        "upvote_count": 0,
                        "comment_count": 0,
                        "published_at": published_at,
                    }
                ))

        return records

    def load_seed_records(self, limit: Optional[int] = None) -> List[ComplaintRecord]:
        """Load fallback records from seed dataset when live scraping is unavailable or restricted."""
        return load_platform_seed_records(
            platforms=("bobaedream",),
            seed_filenames=("raw_bobae_emerging.json", "compiled_complaints.json"),
            default_board_name="보배드림",
            limit=limit,
        )

    @staticmethod
    def _determine_severity(category: str, text: str) -> str:
        """Heuristic severity assessment."""
        return determine_complaint_severity(category, text)

    @staticmethod
    def _extract_defect_topic(category: str, text: str) -> str:
        """Derive technical defect topic string matching inventory."""
        return extract_defect_topic(category, text)


def main():
    parser = argparse.ArgumentParser(description="Bobaedream Multi-Board Community Scraper")
    parser.add_argument("--boards", nargs="+", default=["national", "import", "freeb", "battle", "electric", "accident"], help="Board codes")
    parser.add_argument("--keywords", nargs="+", default=["BYD", "아토3", "씰", "T4K", "중국 전기차", "마사다"], help="Search keywords")
    parser.add_argument("--limit", type=int, default=5, help="Max posts to parse per board/keyword")
    default_output = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data",
        "bobaedream_complaints.json",
    )
    parser.add_argument("--output", type=str, default=default_output, help="Output JSON path")
    args = parser.parse_args()

    eff_limit = max(0, int(args.limit))
    with BobaedreamScraper() as scraper:
        all_records = []
        consecutive_failures = 0

        for b_code in args.boards:
            if consecutive_failures >= 5 or scraper.client.is_circuit_open(BOBAE_BASE_URL):
                logger.warning("Halting scrape loop due to consecutive failures / open circuit breaker.")
                break
            for kw in args.keywords:
                if consecutive_failures >= 5 or scraper.client.is_circuit_open(BOBAE_BASE_URL):
                    break
                logger.info(f"Searching Bobaedream [{b_code}] for keyword: {kw}")
                items = scraper.search_board(b_code, kw, max_pages=1)
                if not items:
                    if scraper.client.is_circuit_open(BOBAE_BASE_URL):
                        consecutive_failures = 5
                        break
                    consecutive_failures += 1
                else:
                    consecutive_failures = 0
                for item in items[:eff_limit]:
                    post_data = scraper.fetch_post_detail(item["url"])
                    if post_data:
                        records = scraper.extract_complaint_records(post_data, board_name=BOBAE_BOARDS.get(b_code, f"보배드림 ({b_code})"))
                        all_records.extend(records)

        if not all_records and scraper.cache_fallback:
            logger.warning("No records harvested from live Bobaedream site. Falling back to seed datasets.")
            all_records = scraper.load_seed_records(limit=eff_limit * len(args.boards))

        save_complaints_json(all_records, args.output)
        print(f"Collected {len(all_records)} records from Bobaedream.")


if __name__ == "__main__":
    main()
