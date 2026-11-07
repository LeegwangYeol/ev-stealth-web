"""
Bobaedream Community Forum Multi-Board Scraper and Parser.
Searches and extracts posts, comments, and authentic user complaints regarding Chinese EVs.
Handles EUC-KR keyword encoding, session cookie warm-up, multi-board routing, and DOM parsing.
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
    encode_euc_kr_query,
    extract_slang_terms,
    polite_delay,
    robust_decode,
    save_complaints_json,
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

    def __init__(self, client: Optional[SafeHttpClient] = None, slang_path: Optional[str] = None):
        # Enforce polite delay with jitter (2.0s - 4.0s) and burst cooldown
        self.client = client or SafeHttpClient(min_delay=2.0, max_delay=4.0)
        self.min_delay = 2.0
        self.max_delay = 4.0
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
        """Warm up session cookie jar on Bobaedream."""
        if not self._warmed_up:
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

        for page in range(1, max_pages + 1):
            try:
                encoded_kw = urllib.parse.quote(keyword.encode("euc-kr"))
            except UnicodeEncodeError:
                encoded_kw = urllib.parse.quote(keyword.encode("cp949", errors="replace"))

            search_url = f"{BOBAE_LIST_URL}?code={board_code}&s_cate=&s_key={s_key}&search={encoded_kw}&page={page}"
            logger.info(f"Searching Bobaedream [{board_code}] for '{keyword}' (Page {page})...")

            status, text, raw = self.client.request(
                search_url,
                method="GET",
                referer=f"{BOBAE_BASE_URL}/",
                encoding="utf-8"
            )

            if status != 200 or not text:
                logger.warning(f"Board search request failed for [{board_code}] keyword '{keyword}' on page {page}")
                break

            items = self.parse_board_list(text, board_code)
            if not items:
                logger.info(f"No more items in [{board_code}] for '{keyword}' on page {page}")
                break

            results.extend(items)

        logger.info(f"Found {len(results)} items in Bobaedream [{board_code}] for '{keyword}'.")
        return results

    def parse_board_list(self, html_content: str, board_code: str) -> List[Dict[str, Any]]:
        """Extract post items from a Bobaedream board list view."""
        items = []
        # Match table rows or list entries with view links
        pattern = r'<a\s+href="([^"]*view\?code=[^"]*No=(\d+)[^"]*)"[^>]*>(.*?)</a>'
        matches = re.findall(pattern, html_content, re.IGNORECASE | re.DOTALL)

        seen_nos = set()
        for href, post_no, raw_title in matches:
            if post_no in seen_nos:
                continue
            seen_nos.add(post_no)

            clean_title = clean_html_text(raw_title)
            if not clean_title or len(clean_title) < 2 or "공지" in clean_title:
                continue

            full_url = href if href.startswith("http") else f"{BOBAE_BASE_URL}{href}"
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

        for page in range(1, max_pages + 1):
            logger.info(f"Searching Bobaedream community search for '{keyword}' (Page {page})...")
            post_data = encode_euc_kr_query({
                "keyword": keyword,
                "searchName": "커뮤니티",
                "page": page,
            })

            status, text, raw = self.client.request(
                BOBAE_SEARCH_URL,
                method="POST",
                data=post_data,
                referer=BOBAE_BASE_URL + "/",
                encoding="utf-8"
            )

            if status != 200 or not text:
                logger.warning(f"Search request failed for keyword '{keyword}' on page {page}")
                break

            items = self.parse_search_results(text)
            if not items:
                logger.info(f"No more search results for '{keyword}' on page {page}")
                break

            results.extend(items)

        logger.info(f"Found {len(results)} search items for keyword '{keyword}' on Bobaedream.")
        return results

    def parse_search_results(self, html_content: str) -> List[Dict[str, Any]]:
        """Parse search results page HTML and extract post metadata."""
        items = []
        pattern = r'<dt[^>]*>\s*<a\s+href="([^"]*view\?[^"]*)"[^>]*>(.*?)</a>'
        matches = re.findall(pattern, html_content, re.IGNORECASE | re.DOTALL)

        for href, raw_title in matches:
            clean_title = clean_html_text(raw_title)
            if not clean_title or len(clean_title) < 2:
                continue

            full_url = href if href.startswith("http") else f"{BOBAE_BASE_URL}{href}"
            code_match = re.search(r"code=([a-zA-Z0-9_]+)", href)
            no_match = re.search(r"No=([0-9]+)", href)
            board_code = code_match.group(1) if code_match else "community"
            post_no = no_match.group(1) if no_match else ""

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
        self.ensure_warm_up()
        status, text, raw = self.client.request(
            post_url,
            method="GET",
            referer=BOBAE_BASE_URL + "/",
            encoding="utf-8"
        )

        if status != 200 or not text:
            logger.warning(f"Failed to fetch post detail: {post_url}")
            return {}

        return self.parse_post_detail(text, post_url)

    def parse_post_detail(self, html_content: str, post_url: str) -> Dict[str, Any]:
        """Extract title, metadata, body text, and comments from Bobaedream post HTML."""
        # Title extraction
        title = ""
        title_match = re.search(r'<strong class="title"[^>]*>(.*?)</strong>', html_content, re.DOTALL)
        if not title_match:
            title_match = re.search(r'<dt[^>]*class="tit"[^>]*>(.*?)</dt>', html_content, re.DOTALL)
        if not title_match:
            title_match = re.search(r'<meta property="og:title" content="([^"]*)"', html_content)
        if title_match:
            title = clean_html_text(title_match.group(1))

        # Metadata extraction (author, date, views)
        author = ""
        author_match = re.search(r'<span class="author"[^>]*>(.*?)</span>', html_content, re.DOTALL)
        if not author_match:
            author_match = re.search(r'<span class="userNick"[^>]*>(.*?)</span>', html_content, re.DOTALL)
        if author_match:
            author = clean_html_text(author_match.group(1))

        published_at = ""
        date_match = re.search(r'(\d{4}[.\-/]\d{2}[.\-/]\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?)', html_content)
        if date_match:
            published_at = date_match.group(1).replace(".", "-").replace("/", "-")

        view_count = 0
        view_match = re.search(r'조회\s*[:]?\s*([0-9,]+)', html_content)
        if view_match:
            try:
                view_count = int(view_match.group(1).replace(",", ""))
            except ValueError:
                pass

        upvote_count = 0
        upvote_match = re.search(r'추천\s*[:]?\s*([0-9,]+)', html_content)
        if upvote_match:
            try:
                upvote_count = int(upvote_match.group(1).replace(",", ""))
            except ValueError:
                pass

        # Body extraction
        body_text = ""
        body_match = re.search(r'<div class="bodyCont"[^>]*>(.*?)</div>\s*<!--\s*//bodyCont', html_content, re.DOTALL)
        if not body_match:
            body_match = re.search(r'<div id="print_area"[^>]*>(.*?)</div>', html_content, re.DOTALL)
        if not body_match:
            body_match = re.search(r'<div class="content01"[^>]*>(.*?)</div>', html_content, re.DOTALL)
        if body_match:
            body_text = clean_html_text(body_match.group(1))

        # Comments extraction
        comments = []
        comment_matches = re.findall(r'<dd[^>]*class="[^"]*comment[^"]*"[^>]*>(.*?)</dd>', html_content, re.DOTALL)
        if not comment_matches:
            comment_matches = re.findall(r'<dd id="cmt_\d+"[^>]*>(.*?)</dd>', html_content, re.DOTALL)

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
        text_lower = text.lower()

        # Identify Vehicle
        target_vehicle = "BYD EV General"
        for pattern, vname in VEHICLE_PATTERNS:
            if re.search(pattern, text_lower):
                target_vehicle = vname
                break

        # Identify Category by keyword frequency / score
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
        board_name: Optional[str] = None
    ) -> List[ComplaintRecord]:
        """
        Convert post and comments into standardized ComplaintRecord objects.
        """
        records = []
        url = post_data.get("url", "")
        title = post_data.get("title", "")
        body = post_data.get("body", "")
        comments = post_data.get("comments", [])
        b_name = board_name or "보배드림 커뮤니티"
        published_at = post_data.get("published_at", "")
        author = post_data.get("author", "보배드림 유저")

        # Check post body
        combined_post = f"{title}\n{body}"
        veh, cat = self.classify_text(combined_post)
        if cat and len(body) >= 20:
            slang = extract_slang_terms(combined_post, self.slang_dict)
            rec_id = f"BOBAE_{cat.upper()[:4]}_{abs(hash(url)) % 100000:05d}"
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
                c_slang = extract_slang_terms(comment, self.slang_dict)
                rec_id = f"BOBAE_{c_cat.upper()[:4]}_{abs(hash(url + str(idx))) % 100000:05d}"
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
    parser = argparse.ArgumentParser(description="Bobaedream Multi-Board Community Scraper")
    parser.add_argument("--boards", nargs="+", default=["national", "import", "freeb", "battle", "electric", "accident"], help="Board codes")
    parser.add_argument("--keywords", nargs="+", default=["BYD", "아토3", "씰", "T4K", "중국 전기차", "마사다"], help="Search keywords")
    parser.add_argument("--limit", type=int, default=5, help="Max posts to parse per board/keyword")
    parser.add_argument("--output", type=str, default="/Users/a7890/src/my-e-car/data/bobaedream_complaints.json", help="Output JSON path")
    args = parser.parse_args()

    scraper = BobaedreamScraper()
    all_records = []

    for b_code in args.boards:
        for kw in args.keywords:
            logger.info(f"Searching Bobaedream [{b_code}] for keyword: {kw}")
            items = scraper.search_board(b_code, kw, max_pages=1)
            for item in items[:args.limit]:
                post_data = scraper.fetch_post_detail(item["url"])
                if post_data:
                    records = scraper.extract_complaint_records(post_data, board_name=BOBAE_BOARDS.get(b_code, f"보배드림 ({b_code})"))
                    all_records.extend(records)

    save_complaints_json(all_records, args.output)
    print(f"Collected {len(all_records)} records from Bobaedream.")


if __name__ == "__main__":
    main()
