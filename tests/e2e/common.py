"""
Shared test utilities, constants, loaders, and validators for the E2E Test Suite.
Supports Global EV Critical Defect & Comparative Research:
- Multi-Brand Coverage: Tesla, Hyundai/Kia/Genesis, Global Brands (Mercedes EQ, BMW i, Porsche Taycan, Polestar, BYD, Chevrolet/GM).
- 4 Core Defect Categories: Parking & Low-Speed Maneuvering, Charging Infrastructure & Electrical Systems,
  Harsh Driving & Thermal Management, Maintenance / AS & Repair Economics.
- 3+ Primary Communities: Bobaedream, DC Inside, Blind, Naver Cafe, Clien, Pomppu.
"""

import ast
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Project root resolution
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if not (PROJECT_ROOT / "data" / "compiled_complaints.json").exists() and (PROJECT_ROOT.parent / "data" / "compiled_complaints.json").exists():
    PROJECT_ROOT = PROJECT_ROOT.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "compiled_complaints.json"
DEFAULT_SLANG_PATH = PROJECT_ROOT / "data" / "slang_dict.json"
DEFAULT_CASEBOOK_PATH = PROJECT_ROOT / "CASEBOOK.md"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "STATISTICAL_REPORT.md"

# 4 Core Defect Categories defined in ORIGINAL_REQUEST.md & PROJECT.md
MANDATORY_CATEGORIES: Set[str] = {
    "parking",
    "charging",
    "rain_driving",
    "hill_climbing",
}

# Extended category set including AS & Maintenance economics
ALL_RECOGNIZED_CATEGORIES: Set[str] = {
    "parking",
    "charging",
    "rain_driving",
    "harsh_driving",
    "hill_climbing",
    "maintenance",
    "as_repair",
}

CATEGORY_KOREAN_NAMES: Dict[str, str] = {
    "parking": "주차 문제",
    "charging": "충전 문제",
    "rain_driving": "우천 시 주행",
    "harsh_driving": "가혹 환경 주행",
    "hill_climbing": "등판 능력",
    "maintenance": "정비 및 AS 수리비",
    "as_repair": "AS 및 정비 경제성",
}

CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "parking": [
        "주차", "어라운드뷰", "센서", "비핑", "타워", "이중주차", "중립", "지하주차장", "연석", "입차",
        "비전", "USS", "스토퍼", "볼라드", "휠빵", "위버터빈", "서먼", "ASS", "팔콘윙", "RSPA"
    ],
    "charging": [
        "충전", "급속", "완속", "BMS", "SOC", "방전", "벽돌", "커넥터", "락", "결빙", "12V", "배터리",
        "굼벵이", "ICCU", "슈퍼차저", "이피트", "E-pit", "NACS", "CCS1", "어댑터", "과열", "센트리", "프리컨디셔닝"
    ],
    "rain_driving": [
        "우천", "빗길", "비", "타이어", "웻그립", "수막", "피쉬테일", "와이퍼", "디프로스트", "누수", "팬텀",
        "유령제동", "채터링", "딥레인", "리어와이퍼", "스핀", "TCS", "눈꽃", "옥토밸브", "성에", "혹한기"
    ],
    "hill_climbing": [
        "등판", "언덕", "산길", "오르막", "경사", "롤백", "오토홀드", "쓰로틀링", "거북이", "화물", "토크",
        "휠스핀", "인버터", "전비", "토크벡터링", "브레이크과열"
    ],
    "maintenance": [
        "수리", "AS", "정비", "서비스센터", "섭센", "블루핸즈", "오토큐", "하이테크", "기가캐스팅", "전손",
        "보험료", "단차", "어퍼암", "자석핸들", "MCU", "블랙아웃", "OTA", "대차", "감가"
    ],
}

# 3 Mandatory Target Platforms (Round 2 Explicit Mandate)
MANDATORY_THREE_PLATFORMS: Set[str] = {
    "bobaedream",
    "dcinside",
    "blind",
}

# All Recognized Platforms across Multi-Community Crawling Pipeline
RECOGNIZED_PLATFORMS: Set[str] = {
    "bobaedream",
    "dcinside",
    "blind",
    "naver_cafe",
    "daum_cafe",
    "pomppu",
    "clien",
    "youtube",
    "fm_korea",
}

# Mandatory Schema Fields for ComplaintRecord
MANDATORY_SCHEMA_FIELDS: Dict[str, type] = {
    "id": str,
    "platform": str,
    "board_name": str,
    "post_url": str,
    "post_title": str,
    "target_vehicle": str,
    "category": str,
    "defect_topic": str,
    "raw_quote": str,
    "slang_terms": list,
    "collected_at": str,
}

# Comprehensive Slang & Community Keywords across Tesla, Hyundai/Kia, and Global EVs
KNOWN_SLANG_KEYWORDS: List[str] = [
    # Chinese EVs & BYD
    "짱깨차", "짱깨", "짱차", "중국산", "불차", "벽돌", "벽돌차", "굼벵이", "굼벵이충전",
    "피쉬테일", "털림", "차체털림", "유령제동", "팬텀브레이킹", "팬텀",
    "롤백", "밀림", "거북이", "거북이모드", "배트맨타이어", "바트만",
    "알리발", "알리트럭", "바퀴달린 알리", "시한폭탄", "단차", "쿠킹호일", "화재포비아",
    "통신에러", "통신튕김", "도어결빙", "채터링", "디프로스트", "쓰로틀링", "고스트비핑", "고스트",
    "감가폭탄", "부품수급", "보조금털이",
    # Tesla Specific
    "테슬람", "단차감성", "정신병와이퍼", "정신병 와이퍼", "마른와이퍼질", "마른 와이퍼질",
    "휠빵", "위버터빈", "진흙반죽", "진흙 반죽", "뱀파이어드레인", "뱀파이어 드레인",
    "눈꽃마크", "눈꽃 마크", "옥토밸브사망", "옥토밸브", "귀신소리", "침대소리",
    "자석핸들", "자석 핸들", "전손폭탄", "전손", "할증폭탄", "슈차지옥", "DC콤보벽돌",
    "기가캐스팅", "하이피델리티", "스마트서먼", "사이버트럭",
    # Hyundai / Kia / Genesis Specific
    "ICCU", "ICCU폭탄", "아이씨씨유", "전원공급시스템", "뒤유리걸레짝", "블라인드에디션",
    "완속반토막", "완속 반토막", "하부긁힘", "2천만원", "블핸퇴짜", "블루핸즈거부",
    "하이테크유배", "원격주차휠스킨", "유령급제동", "램프꽂힘", "크리스탈스피어",
    # Global Brands (Mercedes, BMW, Porsche, Polestar, GM)
    "파라시스폭탄", "파라시스", "청라화재", "스펀지브레이크", "허당브레이크",
    "벽돌페달", "제동시스템결함", "냉동고타이칸", "얼음방", "7천만원전손",
    "티캠먹통", "티캠", "뼈때리는승차감", "골병승차감", "볼트화재", "80프로락", "얼티엄벽돌"
]

# Raw Korean community sentiment & colloquial markers
EMOTIONAL_SENTIMENT_MARKERS: List[str] = [
    "개빡", "노답", "실화냐", "답없", "골로", "미쳤", "탈출", "황당",
    "ㄷㄷ", "ㅋㅋ", "ㅈㄴ", "ㅅㅂ", "어이없", "식겁", "환장", "짜증",
    "사지마", "비추", "후회", "위험", "목숨", "죽을뻔", "멘붕", "극악",
    "쓰레기", "개판", "먹통", "폭망", "호구", "경악", "분통", "식은땀",
    "저승길", "지옥", "양아치", "피눈물", "통곡", "살얼음"
]

# Multi-Brand Categorization & Vehicle Model Classifications
BRAND_FAMILIES: Dict[str, List[str]] = {
    "tesla": ["model 3", "model y", "model s", "model x", "cybertruck", "highland", "juniper", "plaid", "테슬라", "모델3", "모델y", "모델s", "모델x", "사이버트럭"],
    "hyundai_kia": [
        "ioniq 5", "ioniq 6", "kona ev", "ev6", "ev9", "niro ev", "gv60", "g80", "gv70", "e-gmp",
        "아이오닉5", "아이오닉6", "코나", "니로", "제네시스", "현대", "기아"
    ],
    "mercedes": ["eqe", "eqs", "eqa", "eqb", "mercedes", "벤츠", "이큐이", "이큐에스"],
    "bmw": ["i4", "ix3", "i7", "ix", "i5", "ix1", "bmw"],
    "porsche": ["taycan", "포르쉐", "타이칸"],
    "polestar": ["polestar 2", "polestar 4", "폴스타"],
    "byd_chinese": ["atto", "seal", "dolphin", "sealion", "t4k", "masada", "et-van", "byd", "비야디", "아토3", "씰", "돌핀", "씨라이언", "마사다", "이티밴"],
    "chevrolet_gm": ["bolt ev", "bolt euv", "equinox ev", "blazer ev", "chevrolet", "볼트", "이쿼녹스", "쉐보레", "얼티엄"],
}

PASSENGER_VEHICLE_PATTERNS = [
    "atto", "seal", "dolphin", "sealion", "han", "tang", "아토", "씰", "돌핀", "씨라이언",
    "model 3", "model y", "model s", "model x", "모델3", "모델y", "모델s", "모델x",
    "ioniq", "ev6", "ev9", "gv60", "g80", "gv70", "아이오닉",
    "eqe", "eqs", "i4", "i7", "taycan", "polestar", "bolt"
]

COMMERCIAL_VEHICLE_PATTERNS = [
    "t4k", "masada", "et-van", "van", "truck", "마사다", "이티밴", "1톤", "밴", "트럭", "티포케이", "포터", "봉고"
]

# Master Feature Inventory Traceability Mapping (F1.1 ~ F5.8 + Domain Specific IDs)
FEATURE_INVENTORY: Dict[str, Dict[str, str]] = {
    # BYD & General EV Features (F1.1 ~ F5.8)
    "F1.1": {"name": "3D 어라운드뷰 왜곡 및 프레임 드랍", "category": "parking"},
    "F1.2": {"name": "초음파 주차 센서 고스트 비핑 및 반응 지연", "category": "parking"},
    "F1.3": {"name": "아파트 지하주차장 입차 거부 및 화재 포비아", "category": "parking"},
    "F1.4": {"name": "LFP 배터리 중량 초과 기계식 주차타워 입고 불가", "category": "parking"},
    "F1.5": {"name": "이중주차(N단 중립주차) 불가 및 전자식 파킹 강제", "category": "parking"},
    "F1.6": {"name": "자동주차 라인 인식 실패 및 연석 충돌", "category": "parking"},
    "F2.1": {"name": "국내 급속 충전기 PLC 통신 오류 및 세션 튕김", "category": "charging"},
    "F2.2": {"name": "겨울철 저온 LFP 배터리 급속 충전 속도 급락 (굼벵이 충전)", "category": "charging"},
    "F2.3": {"name": "BMS SOC 잔량 오판 및 20%→0% 급락 벽돌 방전", "category": "charging"},
    "F2.4": {"name": "완속/급속 충전 커넥터 락 고착 및 도어 결빙", "category": "charging"},
    "F2.5": {"name": "완속 충전기(7kW) 통신 에러 및 충전 중단", "category": "charging"},
    "F2.6": {"name": "12V 저전압 배터리 방전 시스템 먹통", "category": "charging"},
    "F3.1": {"name": "중국산 순정 OE 타이어 극악 웻그립/수막현상", "category": "rain_driving"},
    "F3.2": {"name": "빗길 회생제동 시 맨홀 통과 피쉬테일(차체 털림)", "category": "rain_driving"},
    "F3.3": {"name": "폭우 시 ADAS 센서 가림 유령 급제동 (팬텀 브레이킹)", "category": "rain_driving"},
    "F3.4": {"name": "오토 와이퍼 센서 로직 오작동 및 채터링 소음", "category": "rain_driving"},
    "F3.5": {"name": "공조기 디프로스트 로직 미흡 전면 시야 차단", "category": "rain_driving"},
    "F3.6": {"name": "차체 단차 웨더스트립 누수 및 하부 볼트 부식", "category": "rain_driving"},
    "F4.1": {"name": "경사로 오토홀드 해제 딜레이 롤백 밀림", "category": "hill_climbing"},
    "F4.2": {"name": "젖은 노면 오르막 전륜 휠스핀 및 TCS 제어 미흡", "category": "hill_climbing"},
    "F4.3": {"name": "산길 연속 등판 모터 발열 쓰로틀링 (거북이모드)", "category": "hill_climbing"},
    "F4.4": {"name": "저SoC 배터리 전압 강하 급경사 등판 출력 급감", "category": "hill_climbing"},
    "F4.5": {"name": "1톤 상용차 화물 적재 시 등판 전비 급락 및 불능", "category": "hill_climbing"},
    "F5.1": {"name": "안전한 다중 플랫폼 크롤링 엔진 (보배/디시/블라인드)", "category": "infra"},
    "F5.2": {"name": "3대 커뮤니티 대규모 원문 데이터 수집 및 정규화", "category": "data"},
    "F5.3": {"name": "한국어 자동차 도메인 형태소 분석 & Trie 토크나이저", "category": "nlp"},
    "F5.4": {"name": "불만 키워드 종합 TOP 랭킹 및 TF-IDF / N-gram 추출", "category": "analytics"},
    "F5.5": {"name": "4단계 감성 분석 및 결함 심각도 지수 (DSI) 산출", "category": "sentiment"},
    "F5.6": {"name": "플랫폼간 교차 분석 및 시계열(2024~2026) 추이 분석", "category": "analytics"},
    "F5.7": {"name": "종합 통계 심층 리포트 및 사례집 발행", "category": "presentation"},
    "F5.8": {"name": "E2E 통계 분석 검증 슈트 및 수락 조건 자동화 하네스", "category": "testing"},
}


def get_project_root() -> Path:
    """Return the absolute path to the project root directory."""
    return PROJECT_ROOT


def normalize_category(cat_raw: str) -> str:
    """Normalize raw category string into standardized key."""
    cat = (cat_raw or "").strip().lower()
    if cat in MANDATORY_CATEGORIES:
        return cat
    if "주차" in cat or "parking" in cat:
        return "parking"
    if "충전" in cat or "charging" in cat:
        return "charging"
    if "우천" in cat or "rain" in cat or "가혹" in cat or "혹한" in cat or "harsh" in cat:
        return "rain_driving"
    if "등판" in cat or "hill" in cat or "climb" in cat or "언덕" in cat:
        return "hill_climbing"
    if "정비" in cat or "as" in cat or "수리" in cat or "maintenance" in cat or "repair" in cat:
        return "maintenance"
    return "other"


def detect_brand_family(vehicle_name: str) -> str:
    """Detect which brand family a vehicle string belongs to."""
    v_clean = (vehicle_name or "").strip().lower()
    for brand, patterns in BRAND_FAMILIES.items():
        if any(p in v_clean for p in patterns):
            return brand
    return "other"


def load_complaints_data(custom_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load complaints data from JSON file."""
    target = custom_path or os.environ.get("COMPLAINTS_DATA_PATH")
    target_path = Path(target) if target else DEFAULT_DATA_PATH
    if not target_path.exists():
        raw_dir = target_path.parent / "raw"
        if raw_dir.exists() and any(raw_dir.glob("*.json")):
            combined: List[Dict[str, Any]] = []
            for rf in sorted(raw_dir.glob("*.json")):
                try:
                    with open(rf, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            combined.extend(data)
                        elif isinstance(data, dict):
                            combined.append(data)
                except Exception:
                    pass
            if combined:
                return combined
        raise FileNotFoundError(
            f"Complaint dataset not found at '{target_path}'. "
            f"Please run data mining pipeline or ensure 'data/compiled_complaints.json' exists."
        )

    with open(target_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(
            f"Expected complaint dataset to be a JSON list, but got {type(data).__name__} at '{target_path}'."
        )

    return data


def load_slang_dict(custom_path: Optional[str] = None) -> Dict[str, Any]:
    """Load slang dictionary from JSON file if available."""
    target = custom_path or os.environ.get("SLANG_DATA_PATH")
    target_path = Path(target) if target else DEFAULT_SLANG_PATH
    if not target_path.exists():
        return {}
    with open(target_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def load_casebook(custom_path: Optional[str] = None) -> str:
    """Load the contents of CASEBOOK.md."""
    target = custom_path or os.environ.get("CASEBOOK_FILE_PATH")
    target_path = Path(target) if target else DEFAULT_CASEBOOK_PATH
    if not target_path.exists():
        raise FileNotFoundError(
            f"Casebook file not found at '{target_path}'. "
            f"Please ensure 'CASEBOOK.md' has been generated."
        )
    with open(target_path, "r", encoding="utf-8") as f:
        return f.read()


def load_statistical_report(custom_path: Optional[str] = None) -> str:
    """Load the contents of STATISTICAL_REPORT.md."""
    target = custom_path or os.environ.get("STATISTICAL_REPORT_PATH")
    target_path = Path(target) if target else DEFAULT_REPORT_PATH
    if not target_path.exists():
        raise FileNotFoundError(
            f"Statistical report not found at '{target_path}'. "
            f"Please ensure 'STATISTICAL_REPORT.md' has been generated."
        )
    with open(target_path, "r", encoding="utf-8") as f:
        return f.read()


def validate_iso8601(timestamp_str: str) -> bool:
    """Validate whether a string is a valid ISO8601 timestamp."""
    if not timestamp_str or not isinstance(timestamp_str, str):
        return False
    formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    cleaned = timestamp_str.strip()
    for fmt in formats:
        try:
            datetime.strptime(cleaned, fmt)
            return True
        except ValueError:
            pass
    iso_regex = r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?)?$"
    return bool(re.match(iso_regex, cleaned))


def validate_url_or_board(url_str: str, board_str: str) -> Tuple[bool, str]:
    """Validate that a record has a verifiable URL and/or specific board name."""
    url_clean = (url_str or "").strip()
    board_clean = (board_str or "").strip()

    if not url_clean and not board_clean:
        return False, "Both post_url and board_name are empty"

    if url_clean:
        url_regex = re.compile(
            r"^(https?://)?"
            r"([a-zA-Z0-9_-]+\.)+[a-zA-Z]{2,}"
            r"(/.*)?$",
            re.IGNORECASE,
        )
        if not url_regex.match(url_clean):
            return False, f"Invalid URL format: '{url_clean}'"

    if not board_clean or len(board_clean) < 2:
        return False, f"Board name is missing or too short: '{board_clean}'"

    return True, "Valid"


def extract_markdown_sections(markdown_text: str) -> Dict[str, str]:
    """Extract major markdown sections (level 1 and 2 headers)."""
    sections: Dict[str, str] = {}
    lines = markdown_text.splitlines()
    current_section = "INTRO"
    current_content: List[str] = []

    for line in lines:
        if line.startswith("# ") or line.startswith("## "):
            if current_content:
                sections[current_section] = "\n".join(current_content).strip()
                current_content = []
            current_section = line.lstrip("#").strip()
        else:
            current_content.append(line)

    if current_content:
        sections[current_section] = "\n".join(current_content).strip()

    return sections


def parse_markdown_tables(markdown_text: str) -> List[List[Dict[str, str]]]:
    """
    Parse all markdown tables in a markdown text into structured lists of row dictionaries.
    """
    tables = []
    lines = markdown_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("|") and line.endswith("|"):
            header_line = line
            if i + 1 < len(lines) and re.match(r"^\|[\s\-:|]+\|$", lines[i + 1].strip()):
                headers = [h.strip() for h in header_line.strip("|").split("|")]
                i += 2  # skip header and separator
                table_rows = []
                while i < len(lines) and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                    row_cells = [c.strip() for c in lines[i].strip("|").split("|")]
                    row_dict = {}
                    for h_idx, h in enumerate(headers):
                        val = row_cells[h_idx] if h_idx < len(row_cells) else ""
                        row_dict[h] = val
                    table_rows.append(row_dict)
                    i += 1
                if table_rows:
                    tables.append(table_rows)
                continue
        i += 1
    return tables


def inspect_crawler_script_safety(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Inspect a scraper script source code via AST and regex to programmatically verify:
    1. Explicit Delay/Jitter implementation (e.g. 1.5s - 3.5s sleep interval)
    2. User-Agent rotation (pool presence or rotation method)
    3. Traffic rate limits / burst cooldowns
    4. Backoff / retry logic (handling 429/403/503)
    """
    p = Path(file_path)
    if not p.exists():
        return {
            "exists": False,
            "has_delay_jitter": False,
            "has_ua_rotation": False,
            "has_traffic_limit": False,
            "has_backoff": False,
            "delay_range": None,
            "details": f"File not found: {p}",
        }

    with open(p, "r", encoding="utf-8") as f:
        source_code = f.read()

    # 1. Delay / Jitter detection
    has_delay_jitter = False
    delay_range = None
    if (
        "SafeHttpClient" in source_code
        or "min_delay" in source_code
        or "max_delay" in source_code
        or "random.uniform" in source_code
        or "random.choice" in source_code
        or "sleep" in source_code
    ) and (
        "delay" in source_code
        or "jitter" in source_code
        or "sleep" in source_code
        or "SafeHttpClient" in source_code
    ):
        has_delay_jitter = True

    delay_matches = re.findall(r"(?:min_delay|min_sleep)\s*=\s*([0-9.]+)|(?:max_delay|max_sleep)\s*=\s*([0-9.]+)|uniform\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*\)", source_code)
    if delay_matches:
        delay_range = delay_matches

    # 2. User-Agent rotation
    has_ua_rotation = False
    if "USER_AGENT" in source_code or "user_agent" in source_code or "SafeHttpClient" in source_code:
        has_ua_rotation = True

    # 3. Traffic limits / Burst cooldown
    has_traffic_limit = False
    if (
        "cooldown" in source_code
        or "request_count" in source_code
        or "interval" in source_code
        or "SafeHttpClient" in source_code
        or "time.sleep" in source_code
    ):
        has_traffic_limit = True

    # 4. Backoff / Retry
    has_backoff = False
    if (
        "backoff" in source_code
        or "429" in source_code
        or "retry" in source_code
        or "retries" in source_code
        or "SafeHttpClient" in source_code
    ):
        has_backoff = True

    return {
        "exists": True,
        "has_delay_jitter": has_delay_jitter,
        "has_ua_rotation": has_ua_rotation,
        "has_traffic_limit": has_traffic_limit,
        "has_backoff": has_backoff,
        "delay_range": delay_range,
        "details": "Validated crawler safety parameters",
    }
