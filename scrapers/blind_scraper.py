"""
Blind Korea Automotive Discussion Scraper and Parser.
Searches and extracts posts, comments, and authentic verified-insider complaints regarding Chinese EVs.
Parses Next.js SSR JSON state (__NEXT_DATA__), OpenGraph metadata, and DOM structures with corporate badge tracking.
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
    extract_balanced_tag_content,
    extract_defect_topic,
    extract_meta_content,
    extract_slang_terms,
    load_platform_seed_records,
    normalize_scraper_url,
    polite_delay,
    resolve_timeout_pair,
    robust_decode,
    save_complaints_json,
)

logger = logging.getLogger("BlindScraper")

BLIND_BASE_URL = "https://www.teamblind.com"
BLIND_KR_URL = "https://www.teamblind.com/kr"
BLIND_AUTO_TOPIC_URL = "https://www.teamblind.com/kr/topics/자동차"

# Keyword dictionary for category classification across all 5 categories
CATEGORY_KEYWORDS = COMMON_CATEGORY_KEYWORDS

# Multi-brand vehicle patterns across Tesla, Hyundai, Kia, Genesis, BYD, Mercedes, BMW, Porsche, Polestar, GM
VEHICLE_PATTERNS = COMMON_VEHICLE_PATTERNS


class BlindScraper:
    """Scraper and parser for public Blind automotive topic posts and permalinks."""

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
        # Enforce polite delay with randomized jitter (1.5s - 3.5s) and cooldown
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
            min_delay=1.5,
            max_delay=3.5,
            connect_timeout=self.connect_timeout,
            read_timeout=self.read_timeout,
            enable_cache=self.enable_cache,
            cache_fallback=self.cache_fallback,
        )
        self.min_delay = 1.5
        self.max_delay = 3.5
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

    def __enter__(self) -> "BlindScraper":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.close()
        return False

    def sleep_polite(self):
        """Randomized sleep with jitter between requests."""
        time.sleep(random.uniform(self.min_delay, self.max_delay))

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
        """Warm up session cookie jar on Blind."""
        if not self._warmed_up:
            if self.client and hasattr(self.client, "warm_up_session"):
                self.client.warm_up_session(BLIND_KR_URL)
            self._warmed_up = True

    def build_google_dork_query(self, keyword: str, category: Optional[str] = None) -> str:
        """
        Build Google Dorking search query string for targeting Blind posts.
        e.g., site:teamblind.com/kr/post "BYD" ("충전" OR "주차" OR "빗길" OR "등판")
        """
        category_filters = {
            "parking": '("주차" OR "어라운드뷰" OR "왜곡" OR "센서" OR "지하주차장")',
            "charging": '("충전" OR "급속" OR "튕김" OR "굼벵이" OR "LFP" OR "BMS")',
            "rain_driving": '("빗길" OR "타이어" OR "배트맨" OR "피쉬테일" OR "와이퍼" OR "팬텀")',
            "hill_climbing": '("등판" OR "언덕" OR "롤백" OR "오토홀드" OR "거북이" OR "쓰로틀링")',
        }
        filter_str = category_filters.get(category, '("단점" OR "결함" OR "후기" OR "불만" OR "시승")')
        return f'site:teamblind.com/kr/post "{keyword}" {filter_str}'

    def fetch_topic_posts(self, topic_name: str = "자동차", max_pages: int = 1) -> List[Dict[str, Any]]:
        """
        Fetch public topic feed items (e.g. /kr/topics/자동차).
        """
        self.ensure_warm_up()
        results = []
        encoded_topic = urllib.parse.quote(str(topic_name or "자동차"))
        topic_url = f"{BLIND_KR_URL}/topics/{encoded_topic}"

        logger.info(f"Fetching Blind topic feed: {topic_url}")
        status, text, raw = self.client.request(
            topic_url,
            method="GET",
            referer=BLIND_KR_URL,
            encoding="utf-8",
            connect_timeout=self.connect_timeout,
            read_timeout=self.read_timeout,
        )

        if status == 200 and text:
            items = self.parse_topic_feed(text, topic_name=str(topic_name or "자동차"))
            results.extend(items)

        logger.info(f"Found {len(results)} posts in Blind topic '{topic_name}'.")
        return results

    def parse_topic_feed(self, html_content: str, topic_name: str = "자동차") -> List[Dict[str, Any]]:
        """Parse Blind topic list HTML / Next.js SSR state."""
        if not html_content or not isinstance(html_content, str):
            return []
        items = []

        # Try extracting Next.js SSR __NEXT_DATA__
        next_data_match = re.search(
            r'<script\b[^>]*\bid=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
            html_content,
            re.IGNORECASE | re.DOTALL,
        )
        if next_data_match:
            try:
                data = json.loads(next_data_match.group(1))
                props = data.get("props") if isinstance(data, dict) else None
                page_props = props.get("pageProps") if isinstance(props, dict) else {}
                if not isinstance(page_props, dict):
                    page_props = {}
                posts_list = page_props.get("articles") or page_props.get("posts") or []
                if not isinstance(posts_list, list):
                    posts_list = []
                for p in posts_list:
                    if not isinstance(p, dict):
                        continue
                    post_id = str(p.get("id") or p.get("article_id") or "")
                    title = clean_html_text(str(p.get("title") or ""))
                    slug = str(p.get("slug") or "")
                    if slug.lower().startswith(("http://", "https://")) or slug.startswith("/"):
                        raw_url = slug
                    elif slug and post_id and not slug.endswith(f"-{post_id}") and slug != post_id:
                        raw_url = f"{BLIND_KR_URL}/post/{slug}-{post_id}"
                    elif slug or post_id:
                        raw_url = f"{BLIND_KR_URL}/post/{slug or post_id}"
                    else:
                        continue
                    url = normalize_scraper_url(raw_url, BLIND_BASE_URL)
                    if not url:
                        continue
                    user_obj = p.get("user") if isinstance(p.get("user"), dict) else {}
                    author_obj = p.get("author") if isinstance(p.get("author"), dict) else {}
                    company = str(
                        user_obj.get("companyName")
                        or user_obj.get("company")
                        or author_obj.get("companyName")
                        or author_obj.get("company")
                        or ""
                    )
                    items.append({
                        "post_id": post_id,
                        "title": title,
                        "url": url,
                        "company": company,
                        "topic": topic_name,
                    })
                if items:
                    return items
            except Exception as e:
                logger.debug(f"Next.js SSR parsing notice for topic feed: {e}")

        # Fallback to DOM regex extraction
        # Pattern: <a ... href="/kr/post/..." or "https://www.teamblind.com/kr/post/..." ...>
        pattern = r'<a\b[^>]*\bhref=["\']((?:https?://(?:www\.)?teamblind\.com)?/kr/post/[^"\']+)["\'][^>]*>(.*?)</a>'
        matches = re.findall(pattern, html_content, re.IGNORECASE | re.DOTALL)
        seen_urls = set()

        for href, inner in matches:
            full_url = normalize_scraper_url(href, BLIND_BASE_URL)
            if not full_url or full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            clean_title = clean_html_text(inner)
            if not clean_title or len(clean_title) < 2:
                continue

            items.append({
                "url": full_url,
                "title": clean_title,
                "topic": topic_name,
            })

        return items

    def fetch_post_detail(self, post_url: str) -> Dict[str, Any]:
        """Fetch and parse Blind post detail page."""
        norm_url = normalize_scraper_url(post_url, BLIND_BASE_URL)
        if not norm_url:
            logger.warning(f"Invalid Blind post_url provided: {post_url!r}")
            return {}
        self.ensure_warm_up()
        status, text, raw = self.client.request(
            norm_url,
            method="GET",
            referer=BLIND_AUTO_TOPIC_URL,
            encoding="utf-8",
            connect_timeout=self.connect_timeout,
            read_timeout=self.read_timeout,
        )

        if status != 200 or not text:
            if norm_url in self.post_cache:
                logger.warning(f"Failed to fetch Blind post detail for {norm_url}; falling back to cached post.")
                return self.post_cache[norm_url]
            logger.warning(f"Failed to fetch Blind post detail: {norm_url}")
            return {}

        try:
            detail = self.parse_post_detail(text, norm_url)
            if detail:
                bounded_cache_set(self.post_cache, norm_url, detail)
            return detail
        except Exception as e:
            logger.warning(f"Error parsing Blind post detail ({norm_url}): {e}")
            if norm_url in self.post_cache:
                logger.warning(f"Falling back to cached post for {norm_url} after parse error.")
                return self.post_cache[norm_url]
            return {}

    def parse_post_detail(self, html_content: str, post_url: str) -> Dict[str, Any]:
        """
        Extract title, author company badge, body, and comments from Blind post HTML.
        Prioritizes Next.js __NEXT_DATA__ SSR JSON, with robust DOM fallback.
        """
        if not html_content or not isinstance(html_content, str):
            return {}
        # 1. Attempt Next.js SSR JSON Extraction
        next_data_match = re.search(
            r'<script\b[^>]*\bid=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
            html_content,
            re.IGNORECASE | re.DOTALL,
        )
        if next_data_match:
            try:
                data = json.loads(next_data_match.group(1))
                props = data.get("props") if isinstance(data, dict) else None
                page_props = props.get("pageProps") if isinstance(props, dict) else {}
                if not isinstance(page_props, dict):
                    page_props = {}
                post = page_props.get("article") or page_props.get("post") or {}

                if isinstance(post, dict) and post:
                    title = str(post.get("title") or "")
                    body = str(post.get("body") or post.get("content") or "")
                    raw_user = post.get("user") if isinstance(post.get("user"), dict) else post.get("author")
                    user = raw_user if isinstance(raw_user, dict) else {}
                    company = str(user.get("companyName") or user.get("company") or "블라인드 인증유저")
                    published_at = str(post.get("created_at") or post.get("registered_at") or "")
                    view_count = post.get("view_count") or post.get("count_views") or 0
                    upvote_count = post.get("like_count") or post.get("count_likes") or 0

                    comments = []
                    raw_comments = post.get("comments") or page_props.get("comments") or []
                    if not isinstance(raw_comments, list):
                        raw_comments = []
                    for c in raw_comments:
                        if not isinstance(c, dict):
                            continue
                        c_body = str(c.get("body") or c.get("content") or "")
                        raw_cu = c.get("user") if isinstance(c.get("user"), dict) else c.get("author")
                        c_user = raw_cu if isinstance(raw_cu, dict) else {}
                        c_comp = str(c_user.get("companyName") or c_user.get("company") or "")
                        cleaned_c = clean_html_text(c_body)
                        if cleaned_c and len(cleaned_c) > 5:
                            prefix = f"[{c_comp}] " if c_comp else ""
                            comments.append(f"{prefix}{cleaned_c}")

                    return {
                        "url": post_url,
                        "title": clean_html_text(title),
                        "company": company,
                        "author_badge": company,
                        "published_at": published_at,
                        "view_count": view_count,
                        "upvote_count": upvote_count,
                        "body": clean_html_text(body),
                        "comments": comments
                    }
            except Exception as e:
                logger.debug(f"Failed to parse Blind __NEXT_DATA__: {e}")

        # 2. DOM & OpenGraph Fallback Extraction
        title = ""
        title_match = re.search(
            r'<h1\b[^>]*\bclass=["\'][^"\']*\barticle-title\b[^"\']*["\'][^>]*>(.*?)</h1>',
            html_content,
            re.DOTALL | re.IGNORECASE,
        )
        if title_match:
            title = clean_html_text(title_match.group(1))
        if not title:
            title = extract_meta_content(html_content, "og:title")

        company = "블라인드 인증유저"
        company_match = re.search(
            r'<span\b[^>]*\bclass=["\'][^"\']*\bcompany\b[^"\']*["\'][^>]*>(.*?)</span>',
            html_content,
            re.DOTALL | re.IGNORECASE,
        )
        if not company_match:
            company_match = re.search(
                r'<div\b[^>]*\bclass=["\'][^"\']*\bauthor-info\b[^"\']*["\'][^>]*>(?:(?!</div>).)*?<span\b[^>]*>(.*?)</span>',
                html_content,
                re.DOTALL | re.IGNORECASE,
            )
        if company_match:
            comp_clean = clean_html_text(company_match.group(1))
            if comp_clean:
                company = comp_clean

        body = ""
        for open_pat in (
            r'<div\b[^>]*\bclass=["\'][^"\']*\barticle-content\b[^"\']*["\'][^>]*>',
            r'<div\b[^>]*\bclass=["\'][^"\']*\bpost-desc\b[^"\']*["\'][^>]*>',
        ):
            inner_html = extract_balanced_tag_content(html_content, open_pat, tag_name="div")
            if inner_html:
                body = clean_html_text(inner_html)
                if body:
                    break
        if not body:
            body = extract_meta_content(html_content, "og:description")

        comments = []
        comment_matches = re.findall(
            r'<div\b[^>]*\bclass=["\'][^"\']*\bcomment-item\b[^"\']*["\'][^>]*>((?:(?!<div\b[^>]*\bcomment-item\b).)*?)</div>\s*<!--\s*//comment-item',
            html_content,
            re.DOTALL | re.IGNORECASE,
        )
        if not comment_matches:
            comment_matches = re.findall(
                r'<p\b[^>]*\bclass=["\'][^"\']*\bcomment-text\b[^"\']*["\'][^>]*>(.*?)</p>',
                html_content,
                re.DOTALL | re.IGNORECASE,
            )

        for c_html in comment_matches:
            cleaned_c = clean_html_text(c_html)
            if cleaned_c and len(cleaned_c) > 5:
                comments.append(cleaned_c)

        return {
            "url": post_url,
            "title": title,
            "company": company,
            "author_badge": company,
            "published_at": "",
            "view_count": 0,
            "upvote_count": 0,
            "body": body,
            "comments": comments
        }

    def classify_text(self, text: str) -> Tuple[str, Optional[str]]:
        """Classify text into target vehicle and category."""
        return classify_ev_text(text, vehicle_patterns=VEHICLE_PATTERNS, category_keywords=CATEGORY_KEYWORDS)

    def extract_complaint_records(
        self,
        post_data: Dict[str, Any],
        board_name: str = "블라인드 자동차"
    ) -> List[ComplaintRecord]:
        """Convert parsed post data into ComplaintRecord objects."""
        if not post_data or not isinstance(post_data, dict):
            return []
        records = []
        url = str(post_data.get("url") or "")
        title = str(post_data.get("title") or "")
        body = str(post_data.get("body") or "")
        raw_comments = post_data.get("comments")
        comments = raw_comments if isinstance(raw_comments, list) else []
        company = str(post_data.get("company") or "블라인드 재직자")
        published_at = str(post_data.get("published_at") or "")

        # Check post body
        combined_post = f"{title}\n{body}"
        veh, cat = self.classify_text(combined_post)
        if cat and len(body) >= 20:
            slang = extract_slang_terms(combined_post, self.slang_dict)
            rec_id = f"BLIND_{cat.upper()[:4]}_{int(hashlib.sha256(url.encode('utf-8')).hexdigest(), 16) % 100000:05d}"
            severity = self._determine_severity(cat, combined_post)
            topic = self._extract_defect_topic(cat, combined_post)
            records.append(ComplaintRecord(
                id=rec_id,
                platform="blind",
                board_name=board_name,
                post_url=url,
                post_title=title,
                target_vehicle=veh,
                category=cat,
                defect_topic=topic,
                raw_quote=body[:600],
                slang_terms=slang,
                severity=severity,
                platform_metadata={
                    "author_type": "blind_verified_company",
                    "author_badge": company,
                    "view_count": post_data.get("view_count", 0),
                    "upvote_count": post_data.get("upvote_count", 0),
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
                # Extract commenter company if prefixed e.g. [LG에너지솔루션]
                c_comp_match = re.match(r"^\[([^\]]+)\]\s*(.*)", comment, re.DOTALL)
                if c_comp_match:
                    c_badge = c_comp_match.group(1)
                    c_text = c_comp_match.group(2)
                else:
                    c_badge = "블라인드 직장인"
                    c_text = comment

                c_slang = extract_slang_terms(c_text, self.slang_dict)
                rec_id = f"BLIND_{c_cat.upper()[:4]}_{int(hashlib.sha256((url + str(idx)).encode('utf-8')).hexdigest(), 16) % 100000:05d}"
                severity = self._determine_severity(c_cat, c_text)
                topic = self._extract_defect_topic(c_cat, c_text)
                records.append(ComplaintRecord(
                    id=rec_id,
                    platform="blind",
                    board_name=board_name,
                    post_url=url,
                    post_title=f"[댓글] {title}",
                    target_vehicle=c_veh if c_veh != "BYD EV General" else veh,
                    category=c_cat,
                    defect_topic=topic,
                    raw_quote=c_text,
                    slang_terms=c_slang,
                    severity=severity,
                    platform_metadata={
                        "author_type": "blind_verified_company",
                        "author_badge": c_badge,
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
            platforms=("blind",),
            seed_filenames=("raw_blind_emerging.json", "compiled_complaints.json"),
            default_board_name="블라인드",
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
    parser = argparse.ArgumentParser(description="Blind Korea Automotive Discussion Scraper")
    parser.add_argument("--keywords", nargs="+", default=["BYD", "아토3", "씰", "T4K", "중국 전기차"], help="Keywords to search")
    parser.add_argument("--topic", type=str, default="자동차", help="Blind topic channel")
    default_output = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data",
        "blind_complaints.json",
    )
    parser.add_argument("--output", type=str, default=default_output, help="Output JSON path")
    args = parser.parse_args()

    with BlindScraper() as scraper:
        all_records = []

        topic_items = scraper.fetch_topic_posts(topic_name=args.topic, max_pages=1)
        for item in topic_items[:10]:
            post_data = scraper.fetch_post_detail(item["url"])
            if post_data:
                records = scraper.extract_complaint_records(post_data)
                all_records.extend(records)

        if not all_records and scraper.cache_fallback:
            logger.warning("No records harvested from live Blind topic. Falling back to seed datasets.")
            all_records = scraper.load_seed_records(limit=10)

        save_complaints_json(all_records, args.output)
        print(f"Collected {len(all_records)} records from Blind.")


if __name__ == "__main__":
    main()
