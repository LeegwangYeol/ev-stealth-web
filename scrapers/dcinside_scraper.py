"""
DC Inside Major/Minor Gallery Scraper and Comment Parser.
Searches and extracts posts, comments, and authentic user complaints regarding Chinese EVs.
Covers electriccar, car_new1, commercialvehicle, and ev galleries with anti-bot headers,
rate limiting, and AJAX comment post-fetching.
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
        is_minor = GALLERIES.get(gallery_id, {}).get("is_minor", True)
        board_prefix = "mgallery/board" if is_minor else "board"
        encoded_kw = urllib.parse.quote(keyword)
        results = []

        for page in range(1, max_pages + 1):
            search_url = (
                f"{DC_BASE_URL}/{board_prefix}/lists/?"
                f"id={gallery_id}&s_type=search_subject_memo&s_keyword={encoded_kw}&page={page}"
            )
            logger.info(f"Searching DC Inside [{gallery_id}] for '{keyword}' (Page {page})...")

            status, text, raw = self.client.request(
                search_url,
                method="GET",
                referer=f"{DC_BASE_URL}/",
                encoding="utf-8"
            )

            if status != 200 or not text:
                logger.warning(f"Search request failed on DC Inside [{gallery_id}] page {page}")
                break

            items = self.parse_gallery_list(text, gallery_id)
            if not items:
                logger.info(f"No more items found for keyword '{keyword}' in {gallery_id}")
                break

            results.extend(items)

        logger.info(f"Found {len(results)} items for '{keyword}' in DC Inside [{gallery_id}].")
        return results

    def parse_gallery_list(self, html_content: str, gallery_id: str) -> List[Dict[str, Any]]:
        """Extract post IDs, titles, authors, and URLs from gallery list HTML."""
        items = []
        is_minor = GALLERIES.get(gallery_id, {}).get("is_minor", True)
        board_prefix = "mgallery/board" if is_minor else "board"

        # Match table rows in DC desktop list view
        # <tr class="ub-content us-post" data-no="12345">
        # <td class="gall_tit ub-word"><a href="...">제목</a>
        row_pattern = r'<tr[^>]*data-no="(\d+)"[^>]*>.*?<td[^>]*class="[^"]*gall_tit[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
        matches = re.findall(row_pattern, html_content, re.IGNORECASE | re.DOTALL)

        for post_no, href, raw_title in matches:
            clean_title = clean_html_text(raw_title)
            if not clean_title or "공지" in clean_title:
                continue

            full_url = f"{DC_BASE_URL}{href}" if href.startswith("/") else href
            mobile_url = f"{DC_MOBILE_BASE_URL}/board/{gallery_id}/{post_no}"

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
        if not e_s_n_o:
            return []

        prefix = "mgallery/board" if is_minor else "board"
        ajax_url = f"{DC_BASE_URL}/{prefix}/comment/"
        referer = f"{DC_BASE_URL}/{prefix}/view/?id={gallery_id}&no={post_id}"

        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Referer": referer,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "application/json, text/javascript, */*; q=0.01"
        }

        form_data = {
            "id": gallery_id,
            "no": post_id,
            "cmt_id": gallery_id,
            "cmt_no": post_id,
            "e_s_n_o": e_s_n_o,
            "comment_page": "1"
        }

        try:
            status, text, raw = self.client.request(
                ajax_url,
                method="POST",
                data=form_data,
                headers=headers,
                encoding="utf-8"
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
                    if c.get("del_yn") == "Y" or c.get("is_delete"):
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
        """Fetch post detail with fallback between desktop view and mobile view."""
        self.ensure_warm_up()
        is_minor = GALLERIES.get(gallery_id, {}).get("is_minor", True)
        board_prefix = "mgallery/board" if is_minor else "board"
        desktop_url = f"{DC_BASE_URL}/{board_prefix}/view/?id={gallery_id}&no={post_id}"

        try:
            status, text, raw = self.client.request(
                desktop_url,
                method="GET",
                referer=f"{DC_BASE_URL}/{board_prefix}/lists/?id={gallery_id}",
                encoding="utf-8"
            )

            if status == 200 and text:
                try:
                    post_data = self.parse_post_detail(text, desktop_url, gallery_id, post_id, is_desktop=True)
                except Exception as e:
                    logger.warning(f"Error parsing DC desktop post detail ({desktop_url}): {e}")
                    post_data = {}
                if post_data:
                    # Try fetching AJAX comments if e_s_n_o exists
                    e_s_n_o = post_data.get("e_s_n_o", "")
                    if e_s_n_o and len(post_data.get("comments", [])) == 0:
                        ajax_comments = self.fetch_comments_ajax(gallery_id, post_id, e_s_n_o=e_s_n_o, is_minor=is_minor)
                        if ajax_comments:
                            post_data["comments"] = ajax_comments
                    return post_data
        except Exception as e:
            logger.warning(f"Error fetching DC desktop post ({desktop_url}): {e}")

        # Fallback to mobile view
        mobile_url = f"{DC_MOBILE_BASE_URL}/board/{gallery_id}/{post_id}"
        headers = {
            "Referer": f"{DC_MOBILE_BASE_URL}/board/{gallery_id}",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1"
        }
        try:
            status, text, raw = self.client.request(
                mobile_url,
                method="GET",
                headers=headers,
                encoding="utf-8"
            )

            if status == 200 and text:
                try:
                    return self.parse_post_detail(text, mobile_url, gallery_id, post_id, is_desktop=False)
                except Exception as e:
                    logger.warning(f"Error parsing DC mobile post detail ({mobile_url}): {e}")
                    return {}
        except Exception as e:
            logger.warning(f"Error fetching DC mobile post ({mobile_url}): {e}")

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
        # Title extraction
        title = ""
        title_match = re.search(r'<span class="title_subject"[^>]*>(.*?)</span>', html_content, re.DOTALL)
        if not title_match:
            title_match = re.search(r'<span class="title_headtext"[^>]*>.*?</span>\s*<span[^>]*>(.*?)</span>', html_content, re.DOTALL)
        if not title_match:
            title_match = re.search(r'<meta property="og:title" content="([^"]*)"', html_content)
        if title_match:
            title = clean_html_text(title_match.group(1))

        # Author / IP Badge extraction
        author_badge = ""
        author_type = "dc_fixed_nick"
        writer_match = re.search(r'<td class="gall_writer[^"]*"[^>]*>.*?<span class="nickname"[^>]*>(.*?)</span>', html_content, re.DOTALL)
        if writer_match:
            author_badge = clean_html_text(writer_match.group(1))
        ip_match = re.search(r'<span class="ip"[^>]*>\(([0-9.*]+)\)</span>', html_content)
        if ip_match:
            author_badge = f"{author_badge or 'ㅇㅇ'} ({ip_match.group(1)})"
            author_type = "dc_masked_ip"
        elif not author_badge:
            mob_author = re.search(r'<span class="ginfo">.*?<span class="user">(.*?)</span>', html_content, re.DOTALL)
            if mob_author:
                author_badge = clean_html_text(mob_author.group(1))
            else:
                author_badge = "ㅇㅇ"

        # Timestamp & View count extraction
        published_at = ""
        date_match = re.search(r'<span class="gall_date"[^>]*title="([^"]*)"', html_content)
        if not date_match:
            date_match = re.search(r'<span class="gall_date"[^>]*>(.*?)</span>', html_content)
        if not date_match:
            date_match = re.search(r'(\d{4}[.\-/]\d{2}[.\-/]\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?)', html_content)
        if date_match:
            published_at = clean_html_text(date_match.group(1)).replace(".", "-").replace("/", "-")

        view_count = 0
        view_match = re.search(r'<span class="gall_count"[^>]*>조회수?\s*([0-9,]+)</span>', html_content)
        if view_match:
            try:
                view_count = int(view_match.group(1).replace(",", ""))
            except ValueError:
                pass

        upvote_count = 0
        upvote_match = re.search(r'<span class="gall_reply_num"[^>]*>추천\s*([0-9,]+)</span>', html_content)
        if not upvote_match:
            upvote_match = re.search(r'<p class="up_num[^"]*"[^>]*>([0-9,]+)</p>', html_content)
        if upvote_match:
            try:
                upvote_count = int(upvote_match.group(1).replace(",", ""))
            except ValueError:
                pass

        # e_s_n_o token for comment AJAX
        e_s_n_o = ""
        token_match = re.search(r'<input\s+type="hidden"\s+id="e_s_n_o"\s+name="e_s_n_o"\s+value="([^"]+)"', html_content)
        if token_match:
            e_s_n_o = token_match.group(1)

        # Body extraction
        body_text = ""
        body_match = re.search(r'<div class="writing_view_box"[^>]*>(.*?)</div>\s*<!--\s*//writing_view_box', html_content, re.DOTALL)
        if not body_match:
            body_match = re.search(r'<div class="write_div"[^>]*>(.*?)</div>', html_content, re.DOTALL)
        if not body_match:
            body_match = re.search(r'<div class="thum-txt[^"]*"[^>]*>(.*?)</div>', html_content, re.DOTALL)
        if body_match:
            body_text = clean_html_text(body_match.group(1))

        # Comments extraction from DOM
        comments = []
        comment_matches = re.findall(r'<p class="usertxt[^"]*"[^>]*>(.*?)</p>', html_content, re.DOTALL)
        if not comment_matches:
            comment_matches = re.findall(r'<p class="txt[^"]*"[^>]*>(.*?)</p>', html_content, re.DOTALL)
        if not comment_matches:
            comment_matches = re.findall(r'<dd class="usertxt[^"]*"[^>]*>(.*?)</dd>', html_content, re.DOTALL)

        for c_html in comment_matches:
            cleaned_c = clean_html_text(c_html)
            if cleaned_c and len(cleaned_c) > 5 and not cleaned_c.startswith("보이스리플"):
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
        board_name: Optional[str] = None
    ) -> List[ComplaintRecord]:
        """Convert parsed post data into ComplaintRecord objects."""
        records = []
        url = post_data.get("url", "")
        title = post_data.get("title", "")
        body = post_data.get("body", "")
        comments = post_data.get("comments", [])
        gallery_id = post_data.get("gallery_id", "electriccar")
        b_name = board_name or f"디시인사이드 {GALLERIES.get(gallery_id, {}).get('name', gallery_id)}"
        author_badge = post_data.get("author_badge", "ㅇㅇ")
        author_type = post_data.get("author_type", "dc_fixed_nick")
        published_at = post_data.get("published_at", "")

        # Check post body
        combined_post = f"{title}\n{body}"
        veh, cat = self.classify_text(combined_post)
        if cat and len(body) >= 20:
            slang = extract_slang_terms(combined_post, self.slang_dict)
            rec_id = f"DC_{cat.upper()[:4]}_{abs(hash(url)) % 100000:05d}"
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
            c_veh, c_cat = self.classify_text(comment)
            if c_cat and len(comment) >= 15:
                c_slang = extract_slang_terms(comment, self.slang_dict)
                rec_id = f"DC_{c_cat.upper()[:4]}_{abs(hash(url + str(idx))) % 100000:05d}"
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
    parser = argparse.ArgumentParser(description="DC Inside Gallery Scraper")
    parser.add_argument("--galleries", nargs="+", default=["electriccar", "car_new1", "commercialvehicle", "ev"], help="Galleries to search")
    parser.add_argument("--keywords", nargs="+", default=["BYD", "아토3", "씰", "T4K", "중국 전기차", "마사다"], help="Search keywords")
    parser.add_argument("--limit", type=int, default=5, help="Max posts per gallery/keyword")
    parser.add_argument("--output", type=str, default="/Users/a7890/src/my-e-car/data/dcinside_complaints.json", help="Output JSON path")
    args = parser.parse_args()

    scraper = DCInsideScraper()
    all_records = []

    for gall in args.galleries:
        for kw in args.keywords:
            items = scraper.search_gallery(gall, kw, max_pages=1)
            for item in items[:args.limit]:
                post_data = scraper.fetch_post_detail(gall, item["post_id"])
                if post_data:
                    records = scraper.extract_complaint_records(post_data)
                    all_records.extend(records)

    save_complaints_json(all_records, args.output)
    print(f"Collected {len(all_records)} records from DC Inside.")


if __name__ == "__main__":
    main()
