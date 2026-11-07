"""
Blind Korea Automotive Discussion Scraper and Parser.
Searches and extracts posts, comments, and authentic verified-insider complaints regarding Chinese EVs.
Parses Next.js SSR JSON state (__NEXT_DATA__), OpenGraph metadata, and DOM structures with corporate badge tracking.
"""

import argparse
import html
import json
import logging
import os
import random
import re
import sys
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

# Ensure parent directory is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.common_utils import (
    COMMON_CATEGORY_KEYWORDS,
    COMMON_VEHICLE_PATTERNS,
    ComplaintRecord,
    SafeHttpClient,
    clean_html_text,
    extract_slang_terms,
    polite_delay,
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

    def __init__(self, client: Optional[SafeHttpClient] = None, slang_path: Optional[str] = None):
        # Enforce polite delay with randomized jitter (1.5s - 3.5s) and cooldown
        self.client = client or SafeHttpClient(min_delay=1.5, max_delay=3.5)
        self.min_delay = 1.5
        self.max_delay = 3.5
        self.slang_path = slang_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "slang_dict.json"
        )
        self.slang_dict = self._load_slang_dict()
        self._warmed_up = False

    def sleep_polite(self):
        """Randomized sleep with jitter between requests."""
        time.sleep(random.uniform(self.min_delay, self.max_delay))

    def _load_slang_dict(self) -> Dict[str, Any]:
        if os.path.exists(self.slang_path):
            try:
                with open(self.slang_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load slang dictionary from {self.slang_path}: {e}")
        return {}

    def ensure_warm_up(self):
        """Warm up session cookie jar on Blind."""
        if not self._warmed_up:
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
        encoded_topic = urllib.parse.quote(topic_name)
        topic_url = f"{BLIND_KR_URL}/topics/{encoded_topic}"

        logger.info(f"Fetching Blind topic feed: {topic_url}")
        status, text, raw = self.client.request(
            topic_url,
            method="GET",
            referer=BLIND_KR_URL,
            encoding="utf-8"
        )

        if status == 200 and text:
            items = self.parse_topic_feed(text)
            results.extend(items)

        logger.info(f"Found {len(results)} posts in Blind topic '{topic_name}'.")
        return results

    def parse_topic_feed(self, html_content: str) -> List[Dict[str, Any]]:
        """Parse Blind topic list HTML / Next.js SSR state."""
        items = []

        # Try extracting Next.js SSR __NEXT_DATA__
        next_data_match = re.search(r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>', html_content, re.DOTALL)
        if next_data_match:
            try:
                data = json.loads(next_data_match.group(1))
                page_props = data.get("props", {}).get("pageProps", {})
                posts_list = page_props.get("articles", []) or page_props.get("posts", []) or []
                for p in posts_list:
                    post_id = str(p.get("id") or p.get("article_id") or "")
                    title = p.get("title", "")
                    slug = p.get("slug", "") or post_id
                    url = f"{BLIND_KR_URL}/post/{slug}-{post_id}" if not slug.startswith("http") else slug
                    company = p.get("user", {}).get("companyName", "") or p.get("author", {}).get("company", "")
                    items.append({
                        "post_id": post_id,
                        "title": title,
                        "url": url,
                        "company": company,
                        "topic": "자동차"
                    })
                if items:
                    return items
            except Exception as e:
                logger.debug(f"Next.js SSR parsing notice for topic feed: {e}")

        # Fallback to DOM regex extraction
        # Pattern: <a href="/kr/post/..." ...>
        pattern = r'<a\s+href="(/kr/post/[^"]+)"[^>]*>(.*?)</a>'
        matches = re.findall(pattern, html_content, re.IGNORECASE | re.DOTALL)
        seen_urls = set()

        for href, inner in matches:
            full_url = f"{BLIND_BASE_URL}{href}" if href.startswith("/") else href
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            clean_title = clean_html_text(inner)
            if not clean_title or len(clean_title) < 2:
                continue

            items.append({
                "url": full_url,
                "title": clean_title,
                "topic": "자동차"
            })

        return items

    def fetch_post_detail(self, post_url: str) -> Dict[str, Any]:
        """Fetch and parse Blind post detail page."""
        self.ensure_warm_up()
        status, text, raw = self.client.request(
            post_url,
            method="GET",
            referer=BLIND_AUTO_TOPIC_URL,
            encoding="utf-8"
        )

        if status != 200 or not text:
            logger.warning(f"Failed to fetch Blind post detail: {post_url}")
            return {}

        return self.parse_post_detail(text, post_url)

    def parse_post_detail(self, html_content: str, post_url: str) -> Dict[str, Any]:
        """
        Extract title, author company badge, body, and comments from Blind post HTML.
        Prioritizes Next.js __NEXT_DATA__ SSR JSON, with robust DOM fallback.
        """
        # 1. Attempt Next.js SSR JSON Extraction
        next_data_match = re.search(r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>', html_content, re.DOTALL)
        if next_data_match:
            try:
                data = json.loads(next_data_match.group(1))
                page_props = data.get("props", {}).get("pageProps", {})
                post = page_props.get("article") or page_props.get("post") or {}

                if post:
                    title = post.get("title", "")
                    body = post.get("body", "") or post.get("content", "")
                    user = post.get("user", {}) or post.get("author", {})
                    company = user.get("companyName", "") or user.get("company", "블라인드 인증유저")
                    published_at = post.get("created_at", "") or post.get("registered_at", "")
                    view_count = post.get("view_count", 0) or post.get("count_views", 0)
                    upvote_count = post.get("like_count", 0) or post.get("count_likes", 0)

                    comments = []
                    raw_comments = post.get("comments", []) or page_props.get("comments", []) or []
                    for c in raw_comments:
                        c_body = c.get("body", "") or c.get("content", "")
                        c_user = c.get("user", {}) or c.get("author", {})
                        c_comp = c_user.get("companyName", "") or c_user.get("company", "")
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
        title_match = re.search(r'<h1[^>]*class="[^"]*article-title[^"]*"[^>]*>(.*?)</h1>', html_content, re.DOTALL)
        if not title_match:
            title_match = re.search(r'<meta property="og:title" content="([^"]*)"', html_content)
        if title_match:
            title = clean_html_text(title_match.group(1))

        company = "블라인드 인증유저"
        company_match = re.search(r'<span[^>]*class="[^"]*company[^"]*"[^>]*>(.*?)</span>', html_content, re.DOTALL)
        if not company_match:
            company_match = re.search(r'<div[^>]*class="[^"]*author-info[^"]*"[^>]*>.*?<span>(.*?)</span>', html_content, re.DOTALL)
        if company_match:
            comp_clean = clean_html_text(company_match.group(1))
            if comp_clean:
                company = comp_clean

        body = ""
        body_match = re.search(r'<div[^>]*class="[^"]*article-content[^"]*"[^>]*>(.*?)</div>', html_content, re.DOTALL)
        if not body_match:
            body_match = re.search(r'<div[^>]*class="[^"]*post-desc[^"]*"[^>]*>(.*?)</div>', html_content, re.DOTALL)
        if not body_match:
            body_match = re.search(r'<meta property="og:description" content="([^"]*)"', html_content)
        if body_match:
            body = clean_html_text(body_match.group(1))

        comments = []
        comment_matches = re.findall(r'<div[^>]*class="[^"]*comment-item[^"]*"[^>]*>(.*?)</div>\s*<!--\s*//comment-item', html_content, re.DOTALL)
        if not comment_matches:
            comment_matches = re.findall(r'<p[^>]*class="[^"]*comment-text[^"]*"[^>]*>(.*?)</p>', html_content, re.DOTALL)

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
        text_lower = text.lower()

        # Identify vehicle
        target_vehicle = "BYD EV General"
        for pattern, vname in VEHICLE_PATTERNS:
            if re.search(pattern, text_lower):
                target_vehicle = vname
                break

        # Identify category
        category_scores = {cat: 0 for cat in CATEGORY_KEYWORDS}
        for cat, kws in CATEGORY_KEYWORDS.items():
            for kw in kws:
                if kw.lower() in text_lower:
                    category_scores[cat] += 1

        best_cat = max(category_scores.items(), key=lambda x: x[1])
        category = best_cat[0] if best_cat[1] > 0 else None

        return target_vehicle, category

    def extract_complaint_records(
        self,
        post_data: Dict[str, Any],
        board_name: str = "블라인드 자동차"
    ) -> List[ComplaintRecord]:
        """Convert parsed post data into ComplaintRecord objects."""
        records = []
        url = post_data.get("url", "")
        title = post_data.get("title", "")
        body = post_data.get("body", "")
        comments = post_data.get("comments", [])
        company = post_data.get("company", "블라인드 재직자")
        published_at = post_data.get("published_at", "")

        # Check post body
        combined_post = f"{title}\n{body}"
        veh, cat = self.classify_text(combined_post)
        if cat and len(body) >= 20:
            slang = extract_slang_terms(combined_post, self.slang_dict)
            rec_id = f"BLIND_{cat.upper()[:4]}_{abs(hash(url)) % 100000:05d}"
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
            c_veh, c_cat = self.classify_text(comment)
            if c_cat and len(comment) >= 15:
                # Extract commenter company if prefixed e.g. [LG에너지솔루션]
                c_comp_match = re.match(r"^\[(.*?)\]\s*(.*)", comment)
                if c_comp_match:
                    c_badge = c_comp_match.group(1)
                    c_text = c_comp_match.group(2)
                else:
                    c_badge = "블라인드 직장인"
                    c_text = comment

                c_slang = extract_slang_terms(c_text, self.slang_dict)
                rec_id = f"BLIND_{c_cat.upper()[:4]}_{abs(hash(url + str(idx))) % 100000:05d}"
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

    @staticmethod
    def _determine_severity(category: str, text: str) -> str:
        """Heuristic severity assessment."""
        text_lower = text.lower()
        if any(w in text_lower for w in ["황천길", "사고", "화재", "죽을뻔", "피쉬테일", "브레이킹", "롤백", "추돌", "벽돌", "방전", "팬텀"]):
            return "critical_safety"
        if any(w in text_lower for w in ["튕김", "통신에러", "충전 불가", "안올라감", "멈춤", "물림", "거북이등", "출력 제한"]):
            return "functional_failure"
        if any(w in text_lower for w in ["아파트", "주민", "입주자", "금지", "민폐", "항의", "입차 거부"]):
            return "social_conflict"
        return "convenience_issue"

    @staticmethod
    def _extract_defect_topic(category: str, text: str) -> str:
        """Derive technical defect topic string matching inventory."""
        if category == "parking":
            if "어라운드뷰" in text or "왜곡" in text or "어안" in text or "프레임" in text:
                return "3D 어라운드뷰 왜곡 및 프레임 드랍으로 인한 휠/차체 긁힘"
            if "센서" in text or "비핑" in text or "초음파" in text:
                return "초음파 주차 센서 고스트 비핑 및 반응 지연"
            if "주차타워" in text or "중량" in text or "2톤" in text:
                return "LFP 배터리 중량 초과(2톤)로 인한 기계식 주차타워 입고 불가"
            if "이중주차" in text or "N단" in text or "중립" in text:
                return "이중주차(N단 중립주차) 불가 및 전자식 파킹브레이크 강제 체결"
            if "자동주차" in text or "연석" in text:
                return "자동주차 라인 인식 실패 및 연석 충돌 / 고스트 브레이킹"
            return "아파트 지하주차장 입차 거부 및 입주민 화재 포비아 갈등"

        elif category == "charging":
            if "겨울" in text or "저온" in text or "굼벵이" in text:
                return "겨울철 저온 LFP 배터리 급속 충전 속도 급락 (굼벵이 충전)"
            if "튕김" in text or "환경부" in text or "채비" in text or "통신" in text or "핸드셰이크" in text:
                return "국내 급속 충전기(환경부, 채비) PLC 통신 오류 및 세션 튕김"
            if "물림" in text or "커넥터" in text or "안뽑힘" in text or "락" in text:
                return "완속/급속 충전 커넥터 락 고착 및 도어 결빙"
            if "12V" in text or "벽돌" in text or "저전압" in text:
                return "12V 저전압 배터리 방전으로 인한 전장 시스템 먹통"
            if "완속" in text or "7kW" in text:
                return "완속 충전기(7kW) 통신 에러 및 충전 중단"
            return "BMS SOC 잔량 오판 및 20%→0% 급락 벽돌 방전"

        elif category == "rain_driving":
            if "타이어" in text or "배트맨" in text or "수막" in text or "웻그립" in text:
                return "중국산 순정 OE 타이어(Atlas Batman 등) 극악 웻그립/수막현상 및 휠스핀"
            if "피쉬테일" in text or "회생제동" in text or "맨홀" in text or "철판" in text:
                return "빗길 회생제동 시 맨홀/철판 통과 피쉬테일(차체 털림)"
            if "팬텀" in text or "고스트" in text or "브레이킹" in text or "dipilot" in text.lower():
                return "폭우 시 ADAS(DiPilot) 센서/카메라 비 가림으로 인한 유령 급제동(팬텀 브레이킹)"
            if "와이퍼" in text or "채터링" in text:
                return "오토 와이퍼 센서 로직 오작동 및 와이퍼 암 채터링 소음"
            if "디프로스트" in text or "김서림" in text or "성에" in text:
                return "공조기 디프로스트(성에/습기 제거) 로직 미흡으로 전면 시야 차단"
            return "차체 단차로 인한 웨더스트립 빗물 누수 및 하부 볼트 부식"

        elif category == "hill_climbing":
            if "롤백" in text or "밀림" in text or "오토홀드" in text:
                return "경사로 정차 후 재출발 시 오토홀드 해제 딜레이로 뒤로 밀림(롤백)"
            if "거북이" in text or "과열" in text or "쓰로틀링" in text:
                return "산길 연속 등판 시 모터/인버터 발열 쓰로틀링 (거북이모드 출력 제한)"
            if "휠스핀" in text or "TCS" in text or "토크" in text:
                return "젖은 노면/오르막 출발 시 전륜 휠스핀 및 미흡한 TCS 토크 벡터링"
            if "1톤" in text or "화물" in text or "t4k" in text.lower() or "마사다" in text:
                return "1톤 상용차(T4K, 이티밴, 마사다) 화물 적재 시 등판 전비 급락 및 등판 불능"
            return "저SoC(15% 이하) 배터리 전압 강하로 인한 급경사 등판 출력 급감"

        return "중국 전기차 시스템 결함"


def main():
    parser = argparse.ArgumentParser(description="Blind Korea Automotive Discussion Scraper")
    parser.add_argument("--keywords", nargs="+", default=["BYD", "아토3", "씰", "T4K", "중국 전기차"], help="Keywords to search")
    parser.add_argument("--topic", type=str, default="자동차", help="Blind topic channel")
    parser.add_argument("--output", type=str, default="/Users/a7890/src/my-e-car/data/blind_complaints.json", help="Output JSON path")
    args = parser.parse_args()

    scraper = BlindScraper()
    all_records = []

    topic_items = scraper.fetch_topic_posts(topic_name=args.topic, max_pages=1)
    for item in topic_items[:10]:
        post_data = scraper.fetch_post_detail(item["url"])
        if post_data:
            records = scraper.extract_complaint_records(post_data)
            all_records.extend(records)

    save_complaints_json(all_records, args.output)
    print(f"Collected {len(all_records)} records from Blind.")


if __name__ == "__main__":
    main()
