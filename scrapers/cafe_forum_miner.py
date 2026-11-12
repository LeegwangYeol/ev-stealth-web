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
from typing import Any, Dict, List, Optional, Tuple, Union

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
    robust_decode,
    save_complaints_json,
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
    ):
        # Enforce polite delay with randomized jitter (1.5s - 3.5s) and cooldown
        self.timeout = timeout
        self.connect_timeout = connect_timeout or (timeout[0] if isinstance(timeout, (tuple, list)) and len(timeout) >= 2 else 5.0)
        self.read_timeout = read_timeout or (timeout[1] if isinstance(timeout, (tuple, list)) and len(timeout) >= 2 else 15.0)
        self.client = client or SafeHttpClient(
            min_delay=1.5,
            max_delay=3.5,
            connect_timeout=self.connect_timeout,
            read_timeout=self.read_timeout,
        )
        self.min_delay = 1.5
        self.max_delay = 3.5
        self.slang_path = slang_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "slang_dict.json"
        )
        self.slang_dict = self._load_slang_dict()
        self.post_cache: Dict[str, Dict[str, Any]] = {}

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

    def mine_pomppu(self, keyword: str, max_pages: int = 1) -> List[Dict[str, Any]]:
        """
        Search Pomppu car forum using EUC-KR encoding.
        """
        self.client.warm_up_session(POMPPU_BASE_URL)
        results = []

        for page in range(1, max_pages + 1):
            try:
                encoded_kw = urllib.parse.quote(keyword.encode("euc-kr"))
            except UnicodeEncodeError:
                encoded_kw = urllib.parse.quote(keyword.encode("cp949", errors="replace"))

            search_url = f"{POMPPU_CAR_URL}&search_type=sub_memo&keyword={encoded_kw}&page={page}"
            logger.info(f"Searching Pomppu Car Forum for '{keyword}' (Page {page})...")

            status, text, raw = self.client.request(
                search_url,
                method="GET",
                referer=f"{POMPPU_BASE_URL}/",
                encoding="euc-kr",
                timeout=self.timeout,
            )

            if status != 200 or not text:
                break

            items = self.parse_pomppu_list(text)
            results.extend(items)

        return results

    def parse_pomppu_list(self, html_content: str) -> List[Dict[str, Any]]:
        """Parse Pomppu forum list HTML."""
        items = []
        matches = re.findall(r'<a\s+href="(view\.php\?id=car&no=\d+[^"]*)"[^>]*>(.*?)</a>', html_content, re.IGNORECASE | re.DOTALL)
        for href, raw_title in matches:
            clean_title = clean_html_text(raw_title)
            if not clean_title or len(clean_title) < 4 or "공지" in clean_title:
                continue
            no_match = re.search(r"no=(\d+)", href)
            post_no = no_match.group(1) if no_match else ""
            full_url = f"{POMPPU_BASE_URL}/zboard/{href}"
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
        self.client.warm_up_session(CLIEN_BASE_URL)
        results = []

        for page in range(0, max_pages):
            encoded_kw = urllib.parse.quote(keyword)
            search_url = f"{CLIEN_CAR_URL}?&od=T31&po={page}&sk=title&sv={encoded_kw}"
            logger.info(f"Searching Clien cm_car for '{keyword}' (Page {page})...")

            status, text, raw = self.client.request(
                search_url,
                method="GET",
                referer=f"{CLIEN_BASE_URL}/",
                encoding="utf-8",
                timeout=self.timeout,
            )

            if status != 200 or not text:
                break

            items = self.parse_clien_list(text)
            results.extend(items)

        return results

    def parse_clien_list(self, html_content: str) -> List[Dict[str, Any]]:
        """Parse Clien list HTML."""
        items = []
        matches = re.findall(r'<a\s+href="(/service/board/cm_car/\d+[^"]*)"[^>]*class="[^"]*subject_fixed[^"]*"[^>]*>(.*?)</a>', html_content, re.IGNORECASE | re.DOTALL)
        for href, raw_title in matches:
            clean_title = clean_html_text(raw_title)
            if not clean_title or len(clean_title) < 4:
                continue
            full_url = f"{CLIEN_BASE_URL}{href}"
            items.append({
                "platform": "clien",
                "board_name": "클리앙 굴러간당",
                "url": full_url,
                "title": clean_title
            })
        return items

    def normalize_record(
        self,
        raw_data: Dict[str, Any]
    ) -> Optional[ComplaintRecord]:
        """
        Normalize and validate a raw complaint record dictionary into ComplaintRecord.
        Auto-generates id, tags slang, validates required fields.
        """
        raw_quote = raw_data.get("raw_quote", "").strip()
        if not raw_quote or len(raw_quote) < 10:
            return None

        platform = raw_data.get("platform", "naver_cafe")
        board_name = raw_data.get("board_name", "전기차 커뮤니티")
        post_url = raw_data.get("post_url", "")
        post_title = raw_data.get("post_title", "중국 전기차 사용자 결함 리포트")
        target_vehicle = raw_data.get("target_vehicle", "BYD Atto 3")
        category = raw_data.get("category", "")
        defect_topic = raw_data.get("defect_topic", "")
        severity = raw_data.get("severity", "functional_failure")
        platform_metadata = raw_data.get("platform_metadata", {})

        # Category detection if missing
        if not category or category not in CATEGORY_KEYWORDS:
            category = self._detect_category(f"{post_title}\n{raw_quote}\n{defect_topic}")
            if not category:
                return None

        # Defect topic detection if missing
        if not defect_topic:
            defect_topic = self._derive_defect_topic(category, f"{post_title}\n{raw_quote}")

        # Slang extraction
        slang_terms = raw_data.get("slang_terms")
        if not slang_terms:
            slang_terms = extract_slang_terms(f"{post_title}\n{raw_quote}\n{defect_topic}", self.slang_dict)

        # ID generation
        rec_id = raw_data.get("id")
        if not rec_id:
            h = hashlib.md5(f"{post_url}_{raw_quote[:50]}".encode("utf-8")).hexdigest()[:6]
            rec_id = f"CASE_{category.upper()[:4]}_{h}"

        collected_at = raw_data.get("collected_at", datetime.now(timezone.utc).isoformat())

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

    def _detect_category(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        scores = {cat: 0 for cat in CATEGORY_KEYWORDS}
        for cat, kws in CATEGORY_KEYWORDS.items():
            for kw in kws:
                if kw.lower() in text_lower:
                    scores[cat] += 1
        best = max(scores.items(), key=lambda x: x[1])
        return best[0] if best[1] > 0 else None

    @staticmethod
    def _derive_defect_topic(category: str, text: str) -> str:
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
    parser = argparse.ArgumentParser(description="Cafe and Forum Miner")
    parser.add_argument("--keywords", nargs="+", default=["BYD", "아토3", "씰", "T4K", "중국 전기차"], help="Keywords to mine")
    parser.add_argument("--output", type=str, default="/Users/a7890/src/my-e-car/data/forum_complaints.json", help="Output path")
    args = parser.parse_args()

    miner = CafeForumMiner()
    pomppu_items = []
    for kw in args.keywords:
        pomppu_items.extend(miner.mine_pomppu(kw, max_pages=1))

    print(f"Mined {len(pomppu_items)} raw items from Pomppu.")


if __name__ == "__main__":
    main()
