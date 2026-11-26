"""
Multi-Platform Cafe, Tech Forum & YouTube Comment Miner and Normalizer.
Extracts, mines, normalizes, and validates authentic complaints from:
- Pomppu Automotive Forum (EUC-KR)
- Clien Allpark / Automotive Forum (UTF-8)
- Naver EV Community Cafes (전기차 동호회, 전기차 타는 사람들, 클럽 BYD)
- YouTube Automotive Review Channels (오토기어, 모카, 미디어오토, 한상기)
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
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Ensure parent directory is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.common_utils import (
    COMMON_CATEGORY_KEYWORDS,
    COMMON_VEHICLE_PATTERNS,
    ComplaintRecord,
    SafeHttpClient,
    classify_ev_text,
    clean_html_text,
    encode_euc_kr_query,
    extract_defect_topic,
    extract_slang_terms,
    is_allowed_domain_url,
    load_platform_seed_records,
    normalize_scraper_url,
    polite_delay,
    resolve_timeout_pair,
    robust_decode,
    save_complaints_json,
    strip_non_body_html,
)

logger = logging.getLogger("CafeForumMiner")

POMPPU_BASE_URL = "https://www.ppomppu.co.kr"
POMPPU_CAR_URL = "https://www.ppomppu.co.kr/zboard/zboard.php?id=car"
CLIEN_BASE_URL = "https://www.clien.net"
CLIEN_CAR_URL = "https://www.clien.net/service/board/cm_car"

# Keyword dictionary for category classification across all 5 categories
CATEGORY_KEYWORDS = COMMON_CATEGORY_KEYWORDS

# Multi-brand vehicle patterns across Tesla, Hyundai, Kia, Genesis, BYD, Mercedes, BMW, Porsche, Polestar, GM
VEHICLE_PATTERNS = COMMON_VEHICLE_PATTERNS


class CafeForumMiner:
    """Miner and normalizer for Pomppu, Clien, Naver EV Cafes, and YouTube Automotive Channels."""

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
        self._warmed_up_hosts: Set[str] = set()

    def close(self, force: bool = False) -> None:
        """Release HTTP client resources if owned by this miner."""
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

    def __enter__(self) -> "CafeForumMiner":
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

    def _ensure_warm_up(self, base_url: str) -> None:
        if base_url not in self._warmed_up_hosts:
            if self.client and hasattr(self.client, "warm_up_session"):
                self.client.warm_up_session(base_url)
            self._warmed_up_hosts.add(base_url)

    def mine_pomppu(self, keyword: str, max_pages: int = 1) -> List[Dict[str, Any]]:
        """
        Search Pomppu car forum using EUC-KR encoding.
        """
        self._ensure_warm_up(POMPPU_BASE_URL)
        results = []
        seen_keys: Set[str] = set()
        kw_str = str(keyword or "")
        try:
            eff_pages = max(1, int(max_pages))
        except (ValueError, TypeError, OverflowError):
            eff_pages = 1

        for page in range(1, eff_pages + 1):
            try:
                encoded_kw = urllib.parse.quote(kw_str.encode("euc-kr"), safe="")
            except UnicodeEncodeError:
                encoded_kw = urllib.parse.quote(kw_str.encode("cp949", errors="replace"), safe="")

            search_url = f"{POMPPU_CAR_URL}&search_type=sub_memo&keyword={encoded_kw}&page={page}"
            logger.info(f"Searching Pomppu Car Forum for '{kw_str}' (Page {page})...")

            status, text, raw = self.client.request(
                search_url,
                method="GET",
                referer=f"{POMPPU_BASE_URL}/",
                encoding=None,
                connect_timeout=self.connect_timeout,
                read_timeout=self.read_timeout,
            )

            if status != 200 or not text:
                break

            items = self.parse_pomppu_list(text)
            if not items:
                break
            new_items = [
                it for it in items
                if (it.get("post_no") or it.get("url")) not in seen_keys
            ]
            if not new_items:
                break
            seen_keys.update(
                str(it.get("post_no") or it.get("url"))
                for it in new_items
                if it.get("post_no") or it.get("url")
            )
            results.extend(new_items)

        return results

    def parse_pomppu_list(self, html_content: str) -> List[Dict[str, Any]]:
        """Parse Pomppu forum list HTML."""
        if not html_content or not isinstance(html_content, str):
            return []
        body_html_region = strip_non_body_html(html_content)
        items = []
        seen_nos: Set[str] = set()
        matches = re.findall(
            r'<a\b[^>]*\bhref=["\']((?:(?:https?:)?//(?:www\.)?ppomppu\.co\.kr)?(?:/zboard/)?view\.php\?[^"\']*\bid=car\b[^"\']*)["\'][^>]*>(.*?)</a>',
            body_html_region,
            re.IGNORECASE | re.DOTALL,
        )
        for href, raw_title in matches:
            no_match = re.search(r"[?&](?:amp;)?no=(\d+)", href, re.IGNORECASE)
            if not no_match:
                continue
            post_no = no_match.group(1)
            if post_no in seen_nos:
                continue
            clean_title = clean_html_text(raw_title)
            if (
                not clean_title
                or len(clean_title) < 4
                or re.match(r"^(?:\[공지\]|공지(?:\s|$|:|-)|\[필독\])", clean_title)
            ):
                continue
            full_url = normalize_scraper_url(href, f"{POMPPU_BASE_URL}/zboard")
            if not full_url or not is_allowed_domain_url(full_url, ("ppomppu.co.kr",)):
                continue
            seen_nos.add(post_no)
            items.append({
                "platform": "pomppu",
                "board_name": "뽐뿌 자동차포럼",
                "post_no": post_no,
                "url": full_url,
                "title": clean_title
            })
        return items

    def mine_clien(self, keyword: str, max_pages: int = 1) -> List[Dict[str, Any]]:
        """Search Clien Allpark/Car board."""
        self._ensure_warm_up(CLIEN_BASE_URL)
        results = []
        seen_keys: Set[str] = set()
        kw_str = str(keyword or "")
        try:
            eff_pages = max(1, int(max_pages))
        except (ValueError, TypeError, OverflowError):
            eff_pages = 1

        for page in range(0, eff_pages):
            encoded_kw = urllib.parse.quote(kw_str, safe="")
            search_url = f"{CLIEN_CAR_URL}?&od=T31&po={page}&sk=title&sv={encoded_kw}"
            logger.info(f"Searching Clien cm_car for '{kw_str}' (Page {page})...")

            status, text, raw = self.client.request(
                search_url,
                method="GET",
                referer=f"{CLIEN_BASE_URL}/",
                encoding="utf-8",
                connect_timeout=self.connect_timeout,
                read_timeout=self.read_timeout,
            )

            if status != 200 or not text:
                break

            items = self.parse_clien_list(text)
            if not items:
                break
            new_items = [
                it for it in items
                if (it.get("post_id") or it.get("url")) not in seen_keys
            ]
            if not new_items:
                break
            seen_keys.update(
                str(it.get("post_id") or it.get("url"))
                for it in new_items
                if it.get("post_id") or it.get("url")
            )
            results.extend(new_items)

        return results

    def parse_clien_list(self, html_content: str) -> List[Dict[str, Any]]:
        """Parse Clien list HTML."""
        if not html_content or not isinstance(html_content, str):
            return []
        body_html_region = strip_non_body_html(html_content)
        items = []
        seen_keys: Set[str] = set()
        matches = re.findall(
            r'<a\b([^>]*\bhref=["\']((?:https?://(?:www\.)?clien\.net)?/service/board/cm_car/\d+[^"\']*)["\'][^>]*)>(.*?)</a>',
            body_html_region,
            re.IGNORECASE | re.DOTALL,
        )
        for attrs, href, raw_title in matches:
            attrs_lower = attrs.lower()
            if "subject_fixed" not in attrs_lower and "subject_fixed" not in raw_title.lower() and "list_subject" not in attrs_lower:
                continue
            clean_title = clean_html_text(raw_title)
            if not clean_title or len(clean_title) < 4:
                continue
            full_url = normalize_scraper_url(href, CLIEN_BASE_URL)
            if not full_url or not is_allowed_domain_url(full_url, ("clien.net",)):
                continue
            pid_match = re.search(r"/service/board/cm_car/(\d+)", full_url)
            post_id = pid_match.group(1) if pid_match else ""
            dedup_key = post_id or full_url
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)
            item: Dict[str, Any] = {
                "platform": "clien",
                "board_name": "클리앙 굴러간당",
                "url": full_url,
                "title": clean_title,
            }
            if post_id:
                item["post_id"] = post_id
            items.append(item)
        return items

    def normalize_record(
        self,
        raw_data: Dict[str, Any]
    ) -> Optional[ComplaintRecord]:
        """
        Normalize and validate a raw complaint record dictionary into ComplaintRecord.
        Auto-generates id, tags slang, validates required fields.
        """
        if not raw_data or not isinstance(raw_data, dict):
            return None
        raw_quote = str(raw_data.get("raw_quote") or "").strip()
        if not raw_quote or len(raw_quote) < 10:
            return None

        platform = str(raw_data.get("platform") or "naver_cafe")
        board_name = str(raw_data.get("board_name") or "전기차 커뮤니티")
        raw_post_url = str(raw_data.get("post_url") or "").strip()
        if raw_post_url:
            if any(ord(c) < 32 or ord(c) == 127 for c in raw_post_url):
                return None
            try:
                parsed_url = urllib.parse.urlsplit(raw_post_url)
            except ValueError:
                return None
            if (
                "\\" in (parsed_url.netloc or "")
                or any(c.isspace() for c in (parsed_url.netloc or ""))
                or parsed_url.username is not None
                or parsed_url.password is not None
            ):
                return None
            if parsed_url.scheme:
                if parsed_url.scheme.lower() not in ("http", "https") or not parsed_url.netloc:
                    return None
            elif raw_post_url.startswith("//") and not parsed_url.netloc:
                return None
        post_url = raw_post_url
        post_title = str(raw_data.get("post_title") or "중국 전기차 사용자 결함 리포트")
        target_vehicle = str(raw_data.get("target_vehicle") or "BYD Atto 3")
        category = str(raw_data.get("category") or "")
        defect_topic = str(raw_data.get("defect_topic") or "")
        severity = str(raw_data.get("severity") or "functional_failure")
        raw_meta = raw_data.get("platform_metadata")
        platform_metadata = raw_meta if isinstance(raw_meta, dict) else {}

        # Category detection if missing
        if not category or category not in CATEGORY_KEYWORDS:
            category = self._detect_category(f"{post_title}\n{raw_quote}\n{defect_topic}")
            if not category:
                return None

        # Defect topic detection if missing
        if not defect_topic:
            defect_topic = self._derive_defect_topic(category, f"{post_title}\n{raw_quote}")

        # Slang extraction
        raw_slang = raw_data.get("slang_terms")
        if isinstance(raw_slang, list) and raw_slang:
            slang_terms = [str(s).strip() for s in raw_slang if s is not None and str(s).strip()]
        else:
            slang_terms = extract_slang_terms(f"{post_title}\n{raw_quote}\n{defect_topic}", self.slang_dict)

        # ID generation
        rec_id = str(raw_data.get("id") or "")
        if not rec_id:
            h = hashlib.md5(f"{post_url}_{raw_quote[:50]}".encode("utf-8", errors="replace")).hexdigest()[:6]
            rec_id = f"CASE_{category.upper()[:4]}_{h}"

        collected_at = str(raw_data.get("collected_at") or datetime.now(timezone.utc).isoformat())

        record = ComplaintRecord(
            id=rec_id,
            platform=platform,
            board_name=board_name,
            post_url=post_url,
            post_title=post_title,
            target_vehicle=target_vehicle,
            category=category,
            defect_topic=defect_topic,
            raw_quote=raw_quote,
            slang_terms=slang_terms,
            severity=severity,
            platform_metadata=platform_metadata,
            collected_at=collected_at
        )

        valid, errors = record.validate()
        if not valid:
            logger.warning(f"Record validation failed: {errors}")
            return None

        return record

    def load_seed_records(self, limit: Optional[int] = None) -> List[ComplaintRecord]:
        """Load fallback records from seed dataset when live scraping is unavailable or restricted."""
        return load_platform_seed_records(
            platforms=("naver_cafe", "pomppu", "clien"),
            seed_filenames=("raw_cafe_emerging.json", "compiled_complaints.json"),
            default_board_name="전기차 카페",
            limit=limit,
        )

    def _detect_category(self, text: str) -> Optional[str]:
        _, category = classify_ev_text(text, vehicle_patterns=VEHICLE_PATTERNS, category_keywords=CATEGORY_KEYWORDS)
        return category

    @staticmethod
    def _derive_defect_topic(category: str, text: str) -> str:
        return extract_defect_topic(category, text)


def main():
    parser = argparse.ArgumentParser(description="Cafe and Forum Miner")
    parser.add_argument("--keywords", nargs="+", default=["BYD", "아토3", "씰", "T4K", "중국 전기차"], help="Keywords to mine")
    default_output = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data",
        "forum_complaints.json",
    )
    parser.add_argument("--output", type=str, default=default_output, help="Output path")
    args = parser.parse_args()

    with CafeForumMiner() as miner:
        pomppu_items = []
        consecutive_failures = 0
        for kw in args.keywords:
            if consecutive_failures >= 5 or miner.client.is_circuit_open(POMPPU_BASE_URL):
                logger.warning("Halting Pomppu mining due to consecutive failures / open circuit breaker.")
                break
            items = miner.mine_pomppu(kw, max_pages=1)
            if not items:
                if miner.client.is_circuit_open(POMPPU_BASE_URL):
                    consecutive_failures = 5
                    break
                consecutive_failures += 1
            else:
                consecutive_failures = 0
            pomppu_items.extend(items)

        if not pomppu_items and miner.cache_fallback:
            logger.warning("No items mined from live forums. Falling back to seed datasets.")
            fallback_records = miner.load_seed_records(limit=10)
            print(f"Loaded {len(fallback_records)} fallback records from seed datasets.")
        else:
            print(f"Mined {len(pomppu_items)} raw items from Pomppu.")


if __name__ == "__main__":
    main()
