"""
DC Inside Major/Minor Gallery Scraper and Comment Parser.
Searches and extracts posts, comments, and authentic user complaints regarding Chinese EVs.
Covers electriccar, car_new1, commercialvehicle, and ev galleries with anti-bot headers,
rate limiting, and AJAX comment post-fetching.
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
    strip_non_body_html,
)

logger = logging.getLogger("DCInsideScraper")

DC_BASE_URL = "https://gall.dcinside.com"
DC_MOBILE_BASE_URL = "https://m.dcinside.com"

GALLERIES = {
    "electriccar": {"name": "전기차 마이너 갤러리", "is_minor": True},
    "electricvehicle": {"name": "전기차 갤러리", "is_minor": True},
    "tesla": {"name": "테슬라 마이너 갤러리", "is_minor": True},
    "car_new1": {"name": "자동차 갤러리", "is_minor": False},
    "commercialvehicle": {"name": "상용차 마이너 갤러리", "is_minor": True},
    "ev": {"name": "EV 마이너 갤러리", "is_minor": True},
}

# Keyword dictionary for category classification across all 5 categories
CATEGORY_KEYWORDS = COMMON_CATEGORY_KEYWORDS

# Multi-brand vehicle patterns across Tesla, Hyundai, Kia, Genesis, BYD, Mercedes, BMW, Porsche, Polestar, GM
VEHICLE_PATTERNS = COMMON_VEHICLE_PATTERNS


class DCInsideScraper:
    """Scraper and parser for DC Inside major and minor galleries."""

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

    def __enter__(self) -> "DCInsideScraper":
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
                        elif isinstance(data, list):
                            return {str(item): {} for item in data}
            except Exception as e:
                logger.warning(f"Failed to load slang dictionary from {self.slang_path}: {e}")
        return {}

    def ensure_warm_up(self):
        """Warm up session cookie jar on DC Inside."""
        if not self._warmed_up:
            if self.client and hasattr(self.client, "warm_up_session"):
                self.client.warm_up_session(DC_BASE_URL)
            self._warmed_up = True

    def search_gallery(
        self,
        gallery_id: str,
        keyword: str,
        max_pages: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Search a DC Inside gallery for a keyword.
        Supports both major and minor galleries.
        """
        self.ensure_warm_up()
        gid_clean = str(gallery_id or "").strip()
        if not gid_clean:
            return []
        safe_gid = urllib.parse.quote(gid_clean, safe="")
        is_minor = GALLERIES.get(gid_clean, {}).get("is_minor", True)
        board_prefix = "mgallery/board" if is_minor else "board"
        encoded_kw = urllib.parse.quote(str(keyword or ""))
        try:
            eff_pages = max(1, int(max_pages))
        except (ValueError, TypeError, OverflowError):
            eff_pages = 1
        results = []
        seen_pids = set()

        for page in range(1, eff_pages + 1):
            search_url = (
                f"{DC_BASE_URL}/{board_prefix}/lists/?"
                f"id={safe_gid}&s_type=search_subject_memo&s_keyword={encoded_kw}&page={page}"
            )
            logger.info(f"Searching DC Inside [{gid_clean}] for '{keyword}' (Page {page})...")

            status, text, raw = self.client.request(
                search_url,
                method="GET",
                referer=f"{DC_BASE_URL}/",
                encoding="utf-8",
                connect_timeout=self.connect_timeout,
                read_timeout=self.read_timeout,
            )

            if status != 200 or not text:
                logger.warning(f"Search request failed on DC Inside [{gid_clean}] page {page}")
                break

            items = self.parse_gallery_list(text, gid_clean)
            if not items:
                logger.info(f"No more items found for keyword '{keyword}' in {gid_clean}")
                break

            new_items = [it for it in items if not it.get("post_id") or it["post_id"] not in seen_pids]
            if not new_items:
                logger.info(f"Search page {page} of [{gid_clean}] repeated previously seen items. Halting loop.")
                break
            seen_pids.update(it["post_id"] for it in new_items if it.get("post_id"))
            results.extend(new_items)

        logger.info(f"Found {len(results)} items for '{keyword}' in DC Inside [{gid_clean}].")
        return results

    def parse_gallery_list(self, html_content: str, gallery_id: str) -> List[Dict[str, Any]]:
        """Extract post IDs, titles, authors, and URLs from gallery list HTML."""
        if not html_content or not isinstance(html_content, str):
            return []
        items = []
        is_minor = GALLERIES.get(gallery_id, {}).get("is_minor", True)
        board_prefix = "mgallery/board" if is_minor else "board"

        # Match table rows in DC desktop list view without bleeding across <tr> or </td> boundaries
        # <tr class="ub-content us-post" data-no="12345">
        # <td class="gall_tit ub-word"><a href="...">제목</a>
        tr_pattern = r'<tr\b([^>]*)\bdata-no=["\'](\d+)["\']([^>]*)>((?:(?!<tr\b).)*?)</tr>'
        tit_pattern = r'<td[^>]*class=["\'][^"\']*\bgall_tit\b[^"\']*["\'][^>]*>(?:(?!</td>).)*?<a\b[^>]*\bhref=["\']([^"\']+)["\'][^>]*>(.*?)</a>'
        rows = re.findall(tr_pattern, html_content, re.IGNORECASE | re.DOTALL)

        for tr_pre, post_no, tr_post, row_body in rows:
            if "ub-notice" in (tr_pre + tr_post).lower():
                continue
            tit_match = re.search(tit_pattern, row_body, re.IGNORECASE | re.DOTALL)
            if not tit_match:
                continue
            href, raw_title = tit_match.group(1), tit_match.group(2)
            clean_title = clean_html_text(raw_title)
            if (
                not clean_title
                or re.match(r"^(?:\[공지\]|공지(?:\s|$|:|-)|\[필독\])", clean_title)
            ):
                continue

            full_url = normalize_scraper_url(href, DC_BASE_URL)
            if not full_url:
                continue
            safe_gid = urllib.parse.quote(str(gallery_id or "").strip(), safe="")
            mobile_url = f"{DC_MOBILE_BASE_URL}/board/{safe_gid}/{post_no}"

            items.append({
                "post_id": post_no,
                "title": clean_title,
                "desktop_url": full_url,
                "mobile_url": mobile_url,
                "gallery_id": gallery_id,
                "gallery_name": GALLERIES.get(gallery_id, {}).get("name", f"디시인사이드 {gallery_id}")
            })

        return items

    def fetch_comments_ajax(
        self,
        gallery_id: str,
        post_id: str,
        e_s_n_o: str = "",
        is_minor: bool = True
    ) -> List[str]:
        """
        Fetch comments using DC Inside internal AJAX comment endpoint.
        URL: https://gall.dcinside.com/[mgallery/]board/comment/
        """
        if not e_s_n_o or not gallery_id or not post_id:
            return []

        gid_str = str(gallery_id).strip()
        pid_str = str(post_id).strip()
        safe_gid = urllib.parse.quote(gid_str, safe="")
        safe_pid = urllib.parse.quote(pid_str, safe="")
        prefix = "mgallery/board" if is_minor else "board"
        ajax_url = f"{DC_BASE_URL}/{prefix}/comment/"
        referer = f"{DC_BASE_URL}/{prefix}/view/?id={safe_gid}&no={safe_pid}"

        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Referer": referer,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "application/json, text/javascript, */*; q=0.01"
        }

        form_data = {
            "id": gid_str,
            "no": pid_str,
            "cmt_id": gid_str,
            "cmt_no": pid_str,
            "e_s_n_o": e_s_n_o,
            "comment_page": "1"
        }

        try:
            status, text, raw = self.client.request(
                ajax_url,
                method="POST",
                data=form_data,
                headers=headers,
                encoding="utf-8",
                connect_timeout=self.connect_timeout,
                read_timeout=self.read_timeout,
            )

            if status == 200 and text:
                try:
                    data = json.loads(text)
                except (json.JSONDecodeError, ValueError) as jde:
                    logger.debug(f"JSON decode notice for DC comments ({gallery_id}/{post_id}): {jde}")
                    return []

                comments_data = []
                if isinstance(data, dict):
                    comments_data = data.get("comments") or data.get("comment_list") or data.get("data") or []
                    if isinstance(comments_data, dict):
                        comments_data = list(comments_data.values())
                elif isinstance(data, list):
                    comments_data = data

                if not isinstance(comments_data, list):
                    return []

                comments = []
                for c in comments_data:
                    if not isinstance(c, dict):
                        continue
                    if str(c.get("del_yn") or "").upper() == "Y" or bool(c.get("is_delete")):
                        continue
                    memo = c.get("memo") or c.get("comment_memo") or c.get("msg") or ""
                    cleaned = clean_html_text(str(memo))
                    if cleaned and len(cleaned) > 5 and not cleaned.startswith(("보이스리플", "[보이스리플]")):
                        comments.append(cleaned)
                return comments
        except Exception as e:
            logger.debug(f"AJAX comment fetch notice for DC {gallery_id}/{post_id}: {e}")

        return []

    def fetch_post_detail(self, gallery_id: str, post_id: str) -> Dict[str, Any]:
        """Fetch post detail with fallback between desktop view, mobile view, and cached data."""
        gid_clean = str(gallery_id or "").strip()
        pid_clean = str(post_id or "").strip()
        if not gid_clean or not pid_clean:
            return {}
        safe_gid = urllib.parse.quote(gid_clean, safe="")
        safe_pid = urllib.parse.quote(pid_clean, safe="")
        cache_key = f"{gid_clean}_{pid_clean}"
        self.ensure_warm_up()
        is_minor = GALLERIES.get(gid_clean, {}).get("is_minor", True)
        board_prefix = "mgallery/board" if is_minor else "board"
        desktop_url = f"{DC_BASE_URL}/{board_prefix}/view/?id={safe_gid}&no={safe_pid}"

        try:
            status, text, raw = self.client.request(
                desktop_url,
                method="GET",
                referer=f"{DC_BASE_URL}/{board_prefix}/lists/?id={safe_gid}",
                encoding="utf-8",
                connect_timeout=self.connect_timeout,
                read_timeout=self.read_timeout,
            )

            if status == 200 and text:
                try:
                    post_data = self.parse_post_detail(text, desktop_url, gid_clean, pid_clean, is_desktop=True)
                except Exception as e:
                    logger.warning(f"Error parsing DC desktop post detail ({desktop_url}): {e}")
                    post_data = {}
                if post_data:
                    # Try fetching AJAX comments if e_s_n_o exists
                    e_s_n_o = post_data.get("e_s_n_o", "")
                    if e_s_n_o and len(post_data.get("comments", [])) == 0:
                        ajax_comments = self.fetch_comments_ajax(gid_clean, pid_clean, e_s_n_o=e_s_n_o, is_minor=is_minor)
                        if ajax_comments:
                            post_data["comments"] = ajax_comments
                    bounded_cache_set(self.post_cache, cache_key, post_data)
                    return post_data
        except Exception as e:
            logger.warning(f"Error fetching DC desktop post ({desktop_url}): {e}")

        # Fallback to mobile view
        mobile_url = f"{DC_MOBILE_BASE_URL}/board/{safe_gid}/{safe_pid}"
        headers = {
            "Referer": f"{DC_MOBILE_BASE_URL}/board/{safe_gid}",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1"
        }
        try:
            status, text, raw = self.client.request(
                mobile_url,
                method="GET",
                headers=headers,
                encoding="utf-8",
                connect_timeout=self.connect_timeout,
                read_timeout=self.read_timeout,
            )

            if status == 200 and text:
                try:
                    res = self.parse_post_detail(text, mobile_url, gid_clean, pid_clean, is_desktop=False)
                    if res:
                        bounded_cache_set(self.post_cache, cache_key, res)
                        return res
                except Exception as e:
                    logger.warning(f"Error parsing DC mobile post detail ({mobile_url}): {e}")
        except Exception as e:
            logger.warning(f"Error fetching DC mobile post ({mobile_url}): {e}")

        if cache_key in self.post_cache:
            logger.warning(f"Remote DC post unreachable ({gallery_id}/{post_id}); falling back to cached post.")
            return self.post_cache[cache_key]

        logger.warning(f"Failed to fetch DC post {gallery_id}/{post_id}")
        return {}

    def parse_post_detail(
        self,
        html_content: str,
        post_url: str,
        gallery_id: str,
        post_id: str,
        is_desktop: bool = True
    ) -> Dict[str, Any]:
        """Extract title, metadata, body text, e_s_n_o, and comments from DC Inside HTML."""
        if not html_content or not isinstance(html_content, str):
            return {}
        # Title extraction
        title = ""
        title_match = re.search(
            r'<span\b[^>]*\bclass=["\'][^"\']*\btitle_subject\b[^"\']*["\'][^>]*>(.*?)</span>',
            html_content,
            re.DOTALL | re.IGNORECASE,
        )
        if not title_match:
            title_match = re.search(
                r'<span\b[^>]*\bclass=["\'][^"\']*\btitle_headtext\b[^"\']*["\'][^>]*>.*?</span>\s*<span\b[^>]*>(.*?)</span>',
                html_content,
                re.DOTALL | re.IGNORECASE,
            )
        if title_match:
            title = clean_html_text(title_match.group(1))
        if not title:
            title = extract_meta_content(html_content, "og:title")

        # Author / IP Badge extraction
        author_badge = ""
        author_type = "dc_fixed_nick"
        writer_open = re.search(
            r'<(td|div)\b[^>]*\bclass=["\'][^"\']*\bgall_writer\b[^"\']*["\'][^>]*>',
            html_content,
            re.IGNORECASE,
        )
        writer_region = (
            extract_balanced_tag_content(
                html_content,
                r'<(?:td|div)\b[^>]*\bclass=["\'][^"\']*\bgall_writer\b[^"\']*["\'][^>]*>',
                tag_name=writer_open.group(1),
            )
            if writer_open
            else ""
        )
        if writer_region:
            nick_match = re.search(
                r'<span\b[^>]*\bclass=["\'][^"\']*\bnickname\b[^"\']*["\'][^>]*>(.*?)</span>',
                writer_region,
                re.DOTALL | re.IGNORECASE,
            )
            if nick_match:
                author_badge = clean_html_text(nick_match.group(1))
        ip_search_region = writer_region if writer_open else html_content.split("writing_view_box", 1)[0]
        ip_match = re.search(
            r'<span\b[^>]*\bclass=["\'][^"\']*\bip\b[^"\']*["\'][^>]*>\(([0-9.*]+)\)</span>',
            ip_search_region,
            re.IGNORECASE,
        )
        if ip_match:
            author_badge = f"{author_badge or 'ㅇㅇ'} ({ip_match.group(1)})"
            author_type = "dc_masked_ip"
        elif not author_badge:
            mob_author = re.search(
                r'<span\b[^>]*\bclass=["\'][^"\']*\bginfo\b[^"\']*["\'][^>]*>(?:(?!</?(?:div|li|ul|section)\b).)*?<span\b[^>]*\bclass=["\'][^"\']*\buser\b[^"\']*["\'][^>]*>(.*?)</span>',
                html_content,
                re.DOTALL | re.IGNORECASE,
            )
            if mob_author:
                author_badge = clean_html_text(mob_author.group(1))
            else:
                author_badge = "ㅇㅇ"

        # Timestamp & View count extraction
        published_at = ""
        date_tag = re.search(
            r'<span\b[^>]*\bclass=["\'][^"\']*\bgall_date\b[^"\']*["\'][^>]*>(.*?)</span>',
            html_content,
            re.DOTALL | re.IGNORECASE,
        )
        if date_tag:
            title_attr = re.search(r'\btitle=["\']([^"\']+)["\']', date_tag.group(0), re.IGNORECASE)
            raw_date = title_attr.group(1) if title_attr else date_tag.group(1)
            published_at = clean_html_text(raw_date).replace(".", "-").replace("/", "-")
        if not published_at:
            body_region = strip_non_body_html(html_content)
            date_match = re.search(r'(\d{4}[.\-/]\d{2}[.\-/]\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?)', body_region)
            if date_match:
                published_at = clean_html_text(date_match.group(1)).replace(".", "-").replace("/", "-")

        view_count = 0
        view_match = re.search(
            r'<span\b[^>]*\bclass=["\'][^"\']*\bgall_count\b[^"\']*["\'][^>]*>조회수?\s*(?:<[^>]+>\s*)*([0-9,]+)',
            html_content,
            re.IGNORECASE,
        )
        if view_match:
            try:
                view_count = int(view_match.group(1).replace(",", ""))
            except ValueError:
                pass

        upvote_count = 0
        upvote_match = re.search(
            r'<span\b[^>]*\bclass=["\'][^"\']*\bgall_reply_num\b[^"\']*["\'][^>]*>추천\s*(?:<[^>]+>\s*)*([0-9,]+)',
            html_content,
            re.IGNORECASE,
        )
        if not upvote_match:
            upvote_match = re.search(
                r'<p\b[^>]*\bclass=["\'][^"\']*\bup_num\b[^"\']*["\'][^>]*>(?:<[^>]+>\s*)*([0-9,]+)',
                html_content,
                re.IGNORECASE,
            )
        if upvote_match:
            try:
                upvote_count = int(upvote_match.group(1).replace(",", ""))
            except ValueError:
                pass

        # e_s_n_o token for comment AJAX (handles arbitrary attribute ordering and quotes)
        e_s_n_o = ""
        token_tag = re.search(r'<input\b[^>]*\b(?:id|name)=["\']e_s_n_o["\'][^>]*>', html_content, re.IGNORECASE)
        if token_tag:
            val_match = re.search(r'\bvalue=["\']([^"\']+)["\']', token_tag.group(0), re.IGNORECASE)
            if val_match:
                e_s_n_o = html.unescape(val_match.group(1))

        # Body extraction
        body_text = ""
        for open_pat in (
            r'<div\b[^>]*\bclass=["\'][^"\']*\bwriting_view_box\b[^"\']*["\'][^>]*>',
            r'<div\b[^>]*\bclass=["\'][^"\']*\bwrite_div\b[^"\']*["\'][^>]*>',
            r'<div\b[^>]*\bclass=["\'][^"\']*\bthum-txt[^"\']*["\'][^>]*>',
        ):
            inner_html = extract_balanced_tag_content(html_content, open_pat, tag_name="div")
            if inner_html:
                body_text = clean_html_text(inner_html)
                if body_text:
                    break
        if not body_text:
            body_match = re.search(
                r'<div\b[^>]*\bclass=["\'][^"\']*\bwriting_view_box\b[^"\']*["\'][^>]*>(.*?)</div>\s*<!--\s*//writing_view_box',
                html_content,
                re.DOTALL | re.IGNORECASE,
            )
            if body_match:
                body_text = clean_html_text(body_match.group(1))

        # Comments extraction from DOM
        comments = []
        comment_matches = re.findall(
            r'<p\b[^>]*\bclass=["\'][^"\']*\busertxt\b[^"\']*["\'][^>]*>(.*?)</p>',
            html_content,
            re.DOTALL | re.IGNORECASE,
        )
        if not comment_matches:
            comment_matches = re.findall(
                r'<p\b[^>]*\bclass=["\'][^"\']*\btxt\b[^"\']*["\'][^>]*>(.*?)</p>',
                html_content,
                re.DOTALL | re.IGNORECASE,
            )
        if not comment_matches:
            comment_matches = re.findall(
                r'<dd\b[^>]*\bclass=["\'][^"\']*\busertxt\b[^"\']*["\'][^>]*>(.*?)</dd>',
                html_content,
                re.DOTALL | re.IGNORECASE,
            )

        for c_html in comment_matches:
            cleaned_c = clean_html_text(c_html)
            if cleaned_c and len(cleaned_c) > 5 and not cleaned_c.startswith(("보이스리플", "[보이스리플]")):
                comments.append(cleaned_c)

        return {
            "url": post_url,
            "gallery_id": gallery_id,
            "post_id": post_id,
            "title": title,
            "author_badge": author_badge,
            "author_type": author_type,
            "published_at": published_at,
            "view_count": view_count,
            "upvote_count": upvote_count,
            "e_s_n_o": e_s_n_o,
            "body": body_text,
            "comments": comments
        }

    def classify_text(self, text: str) -> Tuple[str, Optional[str]]:
        """Classify text into target vehicle and category."""
        return classify_ev_text(text, vehicle_patterns=VEHICLE_PATTERNS, category_keywords=CATEGORY_KEYWORDS)

    def extract_complaint_records(
        self,
        post_data: Dict[str, Any],
        board_name: Optional[str] = None
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
        gallery_id = str(post_data.get("gallery_id") or "electriccar")
        b_name = board_name or f"디시인사이드 {GALLERIES.get(gallery_id, {}).get('name', gallery_id)}"
        author_badge = str(post_data.get("author_badge") or "ㅇㅇ")
        author_type = str(post_data.get("author_type") or "dc_fixed_nick")
        published_at = str(post_data.get("published_at") or "")

        # Check post body
        combined_post = f"{title}\n{body}"
        veh, cat = self.classify_text(combined_post)
        if cat and len(body) >= 20:
            slang = extract_slang_terms(combined_post, self.slang_dict)
            rec_id = f"DC_{cat.upper()[:4]}_{int(hashlib.sha256(url.encode('utf-8')).hexdigest(), 16) % 100000:05d}"
            severity = self._determine_severity(cat, combined_post)
            topic = self._extract_defect_topic(cat, combined_post)
            records.append(ComplaintRecord(
                id=rec_id,
                platform="dcinside",
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
                    "author_type": author_type,
                    "author_badge": author_badge,
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
                c_slang = extract_slang_terms(comment, self.slang_dict)
                rec_id = f"DC_{c_cat.upper()[:4]}_{int(hashlib.sha256((url + str(idx)).encode('utf-8')).hexdigest(), 16) % 100000:05d}"
                severity = self._determine_severity(c_cat, comment)
                topic = self._extract_defect_topic(c_cat, comment)
                records.append(ComplaintRecord(
                    id=rec_id,
                    platform="dcinside",
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
                        "author_type": "dc_fluid_nick",
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
            platforms=("dcinside",),
            seed_filenames=("raw_dcinside_emerging.json", "compiled_complaints.json"),
            default_board_name="디시인사이드",
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
    parser = argparse.ArgumentParser(description="DC Inside Gallery Scraper")
    parser.add_argument("--galleries", nargs="+", default=["electriccar", "car_new1", "commercialvehicle", "ev"], help="Galleries to search")
    parser.add_argument("--keywords", nargs="+", default=["BYD", "아토3", "씰", "T4K", "중국 전기차", "마사다"], help="Search keywords")
    parser.add_argument("--limit", type=int, default=5, help="Max posts per gallery/keyword")
    default_output = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data",
        "dcinside_complaints.json",
    )
    parser.add_argument("--output", type=str, default=default_output, help="Output JSON path")
    args = parser.parse_args()

    with DCInsideScraper() as scraper:
        all_records = []
        consecutive_failures = 0

        for gall in args.galleries:
            if consecutive_failures >= 5 or scraper.client.is_circuit_open(DC_BASE_URL):
                logger.warning("Halting scrape loop due to consecutive failures / open circuit breaker.")
                break
            for kw in args.keywords:
                if consecutive_failures >= 5 or scraper.client.is_circuit_open(DC_BASE_URL):
                    break
                items = scraper.search_gallery(gall, kw, max_pages=1)
                if not items:
                    if scraper.client.is_circuit_open(DC_BASE_URL):
                        consecutive_failures = 5
                        break
                    consecutive_failures += 1
                else:
                    consecutive_failures = 0
                for item in items[:args.limit]:
                    post_data = scraper.fetch_post_detail(gall, item["post_id"])
                    if post_data:
                        records = scraper.extract_complaint_records(post_data)
                        all_records.extend(records)

        if not all_records and scraper.cache_fallback:
            logger.warning("No records harvested from live DCInside site. Falling back to seed datasets.")
            all_records = scraper.load_seed_records(limit=args.limit * len(args.galleries))

        save_complaints_json(all_records, args.output)
        print(f"Collected {len(all_records)} records from DC Inside.")


if __name__ == "__main__":
    main()
