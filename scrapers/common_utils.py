"""
Common Utilities for Safe Web Scraping and Community Forum Data Mining.
Provides HTTP request wrappers, user-agent rotation, rate limiting with jitter,
cookie session warm-up, encoding helpers (EUC-KR/UTF-8), and standard schema definitions.
"""

import email.utils
import hashlib
import html
import http.client
import http.cookiejar
import json
import logging
import os
import random
import re
import shutil
import socket
import ssl
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("ScraperCommonUtils")

# User-Agent Pool (Modern Desktop and Mobile browsers)
USER_AGENT_POOL = [
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    # Firefox on Windows & macOS
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.6; rv:129.0) Gecko/20100101 Firefox/129.0",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0",
    # Mobile (iOS Safari & Android Chrome)
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; SM-S918N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-G998N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36",
]

# Safe memory and resource boundaries
MAX_RESPONSE_BYTES: int = 10 * 1024 * 1024  # 10MB per HTTP response to prevent OOM
MAX_COOKIEJAR_ENTRIES: int = 500  # Prune cookie jar beyond 500 entries to prevent memory growth

# Standard categories, platforms, and severities
VALID_CATEGORIES = {"parking", "charging", "rain_driving", "hill_climbing", "repair_as"}
VALID_PLATFORMS = {"bobaedream", "dcinside", "blind", "naver_cafe", "pomppu", "clien", "youtube"}
VALID_SEVERITIES = {"critical_safety", "functional_failure", "convenience_issue", "social_conflict", "financial_hazard"}

# Multi-brand EV pattern matcher across Tesla, Hyundai, Kia, Genesis, BYD, Mercedes-Benz, BMW, Porsche, Polestar, Chevrolet
COMMON_VEHICLE_PATTERNS: List[Tuple[str, str]] = [
    # Tesla
    (r"(테슬라\s*모델\s*3|모델\s*3|model\s*3|하이랜드|highland)", "Tesla Model 3"),
    (r"(테슬라\s*모델\s*y|모델\s*y|model\s*y|주니퍼|juniper)", "Tesla Model Y"),
    (r"(테슬라\s*모델\s*s|모델\s*s|model\s*s|플래드|plaid)", "Tesla Model S"),
    (r"(테슬라\s*모델\s*x|모델\s*x|model\s*x|팔콘윙)", "Tesla Model X"),
    (r"(사이버트럭|cybertruck)", "Tesla Cybertruck"),
    (r"(테슬라|tesla)", "Tesla EV General"),
    # Hyundai
    (r"(아이오닉\s*5|ioniq\s*5|아이오닉5|아이오닉\s*5n|ioniq5)", "Hyundai Ioniq 5"),
    (r"(아이오닉\s*6|ioniq\s*6|아이오닉6|ioniq6)", "Hyundai Ioniq 6"),
    (r"(코나\s*일렉트릭|코나\s*ev|kona\s*ev|코나ev)", "Hyundai Kona EV"),
    (r"(포터\s*일렉트릭|포터\s*ev|포터ev)", "Hyundai Porter II Electric"),
    (r"(현대\s*전기차|현대\s*ev|e-gmp)", "Hyundai EV General"),
    # Kia
    (r"(기아\s*ev6|ev6|ev-6|ev6\s*gt)", "Kia EV6"),
    (r"(기아\s*ev9|ev9|ev-9)", "Kia EV9"),
    (r"(기아\s*ev3|ev3|ev-3)", "Kia EV3"),
    (r"(니로\s*ev|niro\s*ev|니로\s*플러스)", "Kia Niro EV"),
    (r"(봉고\s*ev|봉고3\s*ev)", "Kia Bongo III EV"),
    (r"(기아\s*전기차|기아\s*ev)", "Kia EV General"),
    # Genesis
    (r"(gv60|제네시스\s*gv60)", "Genesis GV60"),
    (r"(e-g80|g80\s*전동화|g80\s*ev|eg80)", "Genesis Electrified G80"),
    (r"(e-gv70|gv70\s*전동화|gv70\s*ev|egv70)", "Genesis Electrified GV70"),
    (r"(제네시스\s*전기차|제네시스\s*ev)", "Genesis EV General"),
    # Mercedes-Benz EQ
    (r"(eqe\s*350\+?|eqe\s*300|eqe\s*suv|eqe\s*53|벤츠\s*eqe|eqe)", "Mercedes-Benz EQE"),
    (r"(eqs\s*450\+?|eqs\s*580|eqs\s*suv|벤츠\s*eqs|eqs)", "Mercedes-Benz EQS"),
    (r"(eqa|eqb|eqc|벤츠\s*전기차|벤츠\s*eq)", "Mercedes-Benz EQ General"),
    # BMW i
    (r"(bmw\s*i4|i4\s*edrive|i4\s*m50|i4)", "BMW i4"),
    (r"(bmw\s*ix3|ix3)", "BMW iX3"),
    (r"(bmw\s*i7|i7\s*xdrive|i7)", "BMW i7"),
    (r"(bmw\s*ix|ix\s*50|ix\s*m60|bmw\s*ix\b)", "BMW iX"),
    (r"(bmw\s*i5|i5\s*edrive|i5\s*m60|i5)", "BMW i5"),
    (r"(bmw\s*ix1|ix1|bmw\s*전기차|bmw\s*i\b)", "BMW i General"),
    # Porsche
    (r"(타이칸\s*4s|타이칸\s*터보|타이칸\s*gts|타이칸\s*크로스\s*투리스모|포르쉐\s*타이칸|타이칸|taycan)", "Porsche Taycan"),
    # Polestar
    (r"(폴스타\s*2|polestar\s*2|폴스타2)", "Polestar 2"),
    (r"(폴스타\s*4|polestar\s*4|폴스타4)", "Polestar 4"),
    (r"(폴스타|polestar)", "Polestar EV General"),
    # Chevrolet / GM
    (r"(볼트\s*ev|볼트\s*euv|bolt\s*ev|bolt\s*euv|쉐보레\s*볼트)", "Chevrolet Bolt EV"),
    (r"(이쿼녹스\s*ev|equinox\s*ev|블레이저\s*ev|얼티엄)", "Chevrolet Equinox EV"),
    # BYD & Chinese EVs
    (r"(아토\s*3|atto\s*3|atto3)", "BYD Atto 3"),
    (r"(씰|seal|byd\s*seal)", "BYD Seal"),
    (r"(돌핀|dolphin|byd\s*dolphin)", "BYD Dolphin"),
    (r"(씨라이언\s*7|sealion\s*7|씨라이언7|sealion7)", "BYD Sealion 7"),
    (r"(t4k|티포케이|t4-k|byd\s*1톤)", "BYD T4K 1-Ton Truck"),
    (r"(마사다|masada|마사다\s*2밴)", "DFSK Masada 2-Van"),
    (r"(이티밴|et-van|etvan)", "제이스모빌리티 ET-VAN"),
    (r"(쎄아|se-a2|sea2)", "지리자동차 SE-A2"),
    (r"(샤오미|su7|샤오미\s*su7)", "샤오미 SU7"),
    (r"(byd|비야디)", "BYD EV General"),
    (r"(중국산\s*전기차|중국차|짱깨차|짱차|중국산\s*ev)", "Chinese EV General"),
]

# Comprehensive category keywords mapping
COMMON_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "parking": [
        "주차", "어라운드뷰", "서라운드뷰", "3d 뷰", "왜곡", "주차타워", "지하주차", "지하주차장", "입차", "문콕",
        "주차센서", "초음파", "비핑", "고스트 비핑", "연석", "자동주차", "이중주차", "N단", "파킹", "중립주차",
        "주차 거부", "진입 금지", "초음파 센서", "테슬라 비전", "비전파크", "진흙 반죽", "스토퍼", "볼라드",
        "휠빵", "위버터빈", "원격주차", "RSPA", "스마트 서먼", "ASS", "유령 급제동", "램프 꽂힘", "팔콘윙"
    ],
    "charging": [
        "충전", "급속", "완속", "환경부", "채비", "튕김", "통신 에러", "통신 락", "결빙", "충전구",
        "충전건", "커넥터", "물림", "언락", "12V", "방전", "벽돌", "굼벵이", "저온", "LFP",
        "BMS", "뻥배터리", "SOC", "배터리 룰렛", "전압 강하", "완속 충전", "ICCU", "ICCU 폭발", "전원공급시스템",
        "완속 과열", "반토막 리콜", "3.5kW", "이피트", "E-pit", "슈퍼차저", "슈차", "DC콤보", "NACS",
        "어댑터 발열", "프리컨디셔닝", "센트리 드레인", "뱀파이어 드레인", "CCU", "락 솔레노이드"
    ],
    "rain_driving": [
        "빗길", "우천", "비 오는", "수막", "타이어", "배트맨", "웻그립", "슬립", "휠스핀",
        "피쉬테일", "차체 털림", "와이퍼", "채터링", "누수", "단차", "디프로스트", "성에",
        "김서림", "팬텀 브레이킹", "고스트 브레이킹", "회생제동", "DiPilot", "유령 급제동",
        "정신병 와이퍼", "마른 와이퍼질", "리어 와이퍼", "뒤유리", "블라인드 에디션", "교량 이음새", "스핀"
    ],
    "hill_climbing": [
        "등판", "언덕", "오르막", "산길", "고갯길", "한계령", "대관령", "롤백", "뒤로 밀림",
        "오토홀드", "HSA", "거북이", "거북이등", "거북이 모드", "출력 저하", "쓰로틀링",
        "전압 강하", "저SoC", "과적", "적재", "화물", "토크 벡터링", "경사로", "겨울철 주행거리",
        "주행거리 급락", "눈꽃 마크", "옥토밸브", "PTC 히터", "히터 찬바람", "냉동고 타이칸", "얼음방", "잔량 급락"
    ],
    "repair_as": [
        "AS", "수리", "정비", "서비스센터", "섭센", "블루핸즈", "오토큐", "하이테크", "입고 거부", "예약 대기",
        "배터리 교체비", "2000만원", "3000만원", "7000만원", "하부 긁힘", "하부 스크래치", "기가캐스팅",
        "전손", "전손 폭탄", "보험료 폭등", "할증 폭탄", "부품 수급", "어퍼암", "귀신 소리", "침대 소리",
        "자석 핸들", "단차", "글라스루프 누수", "TCAM", "티캠 먹통", "벽돌차", "OTA 벽돌", "대차 거부", "감가 폭탄"
    ]
}


def get_random_headers(referer: Optional[str] = None) -> Dict[str, str]:
    """Generate modern browser headers with rotated User-Agent."""
    headers = {
        "User-Agent": random.choice(USER_AGENT_POOL),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Upgrade-Insecure-Requests": "1"
    }
    if referer:
        headers["Referer"] = referer
    return headers


def polite_delay(min_delay: float = 1.5, max_delay: float = 3.5):
    """Enforce polite sleep with randomized jitter between requests."""
    if max_delay <= 0:
        return
    sleep_time = random.uniform(max(0.0, min_delay), max(0.0, max_delay))
    if sleep_time > 0:
        time.sleep(sleep_time)


@dataclass
class ComplaintRecord:
    """Standardized schema for Chinese EV complaint record."""
    id: str
    platform: str
    board_name: str
    post_url: str
    post_title: str
    target_vehicle: str
    category: str
    defect_topic: str
    raw_quote: str
    slang_terms: List[str] = field(default_factory=list)
    severity: str = "functional_failure"
    platform_metadata: Dict[str, Any] = field(default_factory=dict)
    collected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def validate(self) -> Tuple[bool, List[str]]:
        """Validate record fields against specification."""
        errors = []
        if not self.id or not isinstance(self.id, str):
            errors.append("Invalid or missing 'id'")
        if self.platform not in VALID_PLATFORMS:
            errors.append(f"Invalid platform '{self.platform}'. Must be one of {VALID_PLATFORMS}")
        if not self.board_name or not isinstance(self.board_name, str):
            errors.append("Invalid or missing 'board_name'")
        if not self.post_url or not isinstance(self.post_url, str):
            errors.append("Invalid or missing 'post_url'")
        if not self.post_title or not isinstance(self.post_title, str):
            errors.append("Invalid or missing 'post_title'")
        if not self.target_vehicle or not isinstance(self.target_vehicle, str):
            errors.append("Invalid or missing 'target_vehicle'")
        if self.category not in VALID_CATEGORIES:
            errors.append(f"Invalid category '{self.category}'. Must be one of {VALID_CATEGORIES}")
        if not self.defect_topic or not isinstance(self.defect_topic, str):
            errors.append("Invalid or missing 'defect_topic'")
        if not self.raw_quote or len(self.raw_quote.strip()) < 5:
            errors.append("Invalid or too short 'raw_quote'")
        if not isinstance(self.slang_terms, list):
            errors.append("'slang_terms' must be a list")
        if self.severity not in VALID_SEVERITIES:
            errors.append(f"Invalid severity '{self.severity}'. Must be one of {VALID_SEVERITIES}")
        if not isinstance(self.platform_metadata, dict):
            errors.append("'platform_metadata' must be a dict")
        return (len(errors) == 0, errors)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ResilientHTTPConnection(http.client.HTTPConnection):
    """HTTPConnection supporting explicit separate connect and read timeouts."""

    def __init__(self, *args, connect_timeout: float = 5.0, read_timeout: float = 15.0, **kwargs):
        self._conn_timeout = float(connect_timeout) if connect_timeout is not None and connect_timeout > 0 else 5.0
        self._read_timeout = float(read_timeout) if read_timeout is not None and read_timeout > 0 else 15.0
        super().__init__(*args, **kwargs)

    def connect(self):
        self.sock = socket.create_connection(
            (self.host, self.port),
            self._conn_timeout,
            self.source_address,
        )
        if self._read_timeout is not None:
            self.sock.settimeout(self._read_timeout)


class ResilientHTTPSConnection(http.client.HTTPSConnection):
    """HTTPSConnection supporting explicit separate connect and read timeouts."""

    def __init__(self, *args, connect_timeout: float = 5.0, read_timeout: float = 15.0, **kwargs):
        self._conn_timeout = float(connect_timeout) if connect_timeout is not None and connect_timeout > 0 else 5.0
        self._read_timeout = float(read_timeout) if read_timeout is not None and read_timeout > 0 else 15.0
        super().__init__(*args, **kwargs)

    def connect(self):
        self.sock = socket.create_connection(
            (self.host, self.port),
            self._conn_timeout,
            self.source_address,
        )
        if self._read_timeout is not None:
            self.sock.settimeout(self._read_timeout)
        if self._tunnel_host:
            self._tunnel()
        server_hostname = self.host if ssl.HAS_SNI else None
        self.sock = self._context.wrap_socket(self.sock, server_hostname=server_hostname)


class ResilientHTTPHandler(urllib.request.HTTPHandler):
    """HTTP handler injecting ResilientHTTPConnection with explicit timeouts."""

    def __init__(self, connect_timeout: float = 5.0, read_timeout: float = 15.0, **kwargs):
        super().__init__(**kwargs)
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout

    def http_open(self, req):
        def _factory(host, **kwargs):
            return ResilientHTTPConnection(
                host,
                connect_timeout=self._connect_timeout,
                read_timeout=self._read_timeout,
                **kwargs,
            )
        return self.do_open(_factory, req)


class ResilientHTTPSHandler(urllib.request.HTTPSHandler):
    """HTTPS handler injecting ResilientHTTPSConnection with explicit timeouts."""

    def __init__(self, connect_timeout: float = 5.0, read_timeout: float = 15.0, context=None, **kwargs):
        super().__init__(context=context, **kwargs)
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout

    def https_open(self, req):
        def _factory(host, **kwargs):
            ctx = getattr(self, "_context", None)
            if ctx is not None:
                kwargs.setdefault("context", ctx)
            if hasattr(self, "_check_hostname"):
                kwargs.setdefault("check_hostname", getattr(self, "_check_hostname"))
            return ResilientHTTPSConnection(
                host,
                connect_timeout=self._connect_timeout,
                read_timeout=self._read_timeout,
                **kwargs,
            )
        return self.do_open(_factory, req)


class SafeHttpClient:
    """
    Robust, rate-limited HTTP client with session cookie persistence,
    User-Agent rotation, explicit timeouts (connect & read), exponential backoff,
    caching with fallback on 5xx/unreachable, bounded memory stream reads,
    resource cleanup, and encoding handling.
    """

    def __init__(
        self,
        min_delay: float = 1.5,
        max_delay: float = 3.5,
        max_retries: int = 3,
        cooldown_interval: int = 18,
        cooldown_time: float = 6.0,
        timeout: Union[float, Tuple[float, float]] = 15.0,
        max_response_size: int = MAX_RESPONSE_BYTES,
        max_cookies: int = MAX_COOKIEJAR_ENTRIES,
        connect_timeout: Optional[float] = None,
        read_timeout: Optional[float] = None,
        enable_cache: bool = True,
        cache_fallback: bool = True,
        cache_dir: Optional[str] = None,
        opener: Optional[urllib.request.OpenerDirector] = None,
    ):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.cooldown_interval = cooldown_interval
        self.cooldown_time = cooldown_time
        self.timeout = timeout
        self.max_response_size = max_response_size
        self.max_cookies = max_cookies
        self.enable_cache = enable_cache
        self.cache_fallback = cache_fallback
        self.request_count = 0
        self.last_request_time = 0.0
        self.last_response_from_cache = False
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

        # Resolve explicit connect and read timeouts
        if connect_timeout is not None:
            try:
                self._connect_timeout = float(connect_timeout)
            except (ValueError, TypeError):
                self._connect_timeout = 5.0
        elif isinstance(timeout, (tuple, list)) and len(timeout) >= 2:
            try:
                self._connect_timeout = float(timeout[0])
            except (ValueError, TypeError):
                self._connect_timeout = 5.0
        elif isinstance(timeout, (int, float)) and timeout > 0:
            self._connect_timeout = min(5.0, float(timeout))
        else:
            self._connect_timeout = 5.0

        if read_timeout is not None:
            try:
                self._read_timeout = float(read_timeout)
            except (ValueError, TypeError):
                self._read_timeout = 15.0
        elif isinstance(timeout, (tuple, list)) and len(timeout) >= 2:
            try:
                self._read_timeout = float(timeout[1])
            except (ValueError, TypeError):
                self._read_timeout = 15.0
        elif isinstance(timeout, (int, float)) and timeout > 0:
            self._read_timeout = float(timeout)
        else:
            self._read_timeout = 15.0

        # Cache directory setup
        if cache_dir:
            self.cache_dir = cache_dir
        else:
            self.cache_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", ".cache", "http"
            )

        # Setup cookie jar and opener
        self.cookie_jar = http.cookiejar.CookieJar()
        if opener is not None:
            self.opener = opener
        else:
            cookie_processor = urllib.request.HTTPCookieProcessor(self.cookie_jar)
            http_handler = ResilientHTTPHandler(
                connect_timeout=self._connect_timeout,
                read_timeout=self._read_timeout,
            )
            https_handler = ResilientHTTPSHandler(
                connect_timeout=self._connect_timeout,
                read_timeout=self._read_timeout,
            )
            self.opener = urllib.request.build_opener(cookie_processor, http_handler, https_handler)

    @property
    def connect_timeout(self) -> float:
        """Connect timeout in seconds."""
        return self._connect_timeout

    @property
    def read_timeout(self) -> float:
        """Read timeout in seconds."""
        return self._read_timeout

    def _cache_key(self, url: str) -> str:
        norm = (url or "").strip()
        return hashlib.sha256(norm.encode("utf-8")).hexdigest()

    def get_cached_response(self, url: str) -> Optional[Tuple[int, str, bytes]]:
        """Retrieve cached (status_code, decoded_text, raw_bytes) if present."""
        if not self.enable_cache or not url:
            return None
        key = self._cache_key(url)
        if key in self._memory_cache:
            entry = self._memory_cache[key]
            return entry.get("status", 200), entry.get("text", ""), entry.get("raw", b"")

        if self.cache_dir:
            file_path = os.path.join(self.cache_dir, f"{key}.json")
            if os.path.isfile(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    status = int(data.get("status", 200))
                    text = str(data.get("text", ""))
                    raw_hex = data.get("raw_hex", "")
                    raw_bytes = bytes.fromhex(raw_hex) if raw_hex else text.encode("utf-8")
                    self._memory_cache[key] = {
                        "status": status,
                        "text": text,
                        "raw": raw_bytes,
                        "time": data.get("time", time.time()),
                        "url": url,
                    }
                    return status, text, raw_bytes
                except Exception as e:
                    logger.debug(f"Cache read error for {url}: {e}")
        return None

    def set_cached_response(
        self,
        url: str,
        status_code: int,
        decoded_text: str,
        raw_bytes: bytes,
    ) -> None:
        """Cache response data in-memory and persistently to disk."""
        if not self.enable_cache or not url or not decoded_text:
            return
        key = self._cache_key(url)
        entry = {
            "status": int(status_code),
            "text": str(decoded_text),
            "raw": bytes(raw_bytes),
            "time": time.time(),
            "url": str(url),
        }
        self._memory_cache[key] = entry
        if len(self._memory_cache) > 500:
            oldest_k = min(self._memory_cache, key=lambda k: self._memory_cache[k].get("time", 0))
            del self._memory_cache[oldest_k]

        if self.cache_dir:
            try:
                os.makedirs(self.cache_dir, exist_ok=True)
                file_path = os.path.join(self.cache_dir, f"{key}.json")
                temp_path = f"{file_path}.tmp.{os.getpid()}"
                payload = {
                    "url": str(url),
                    "status": int(status_code),
                    "text": str(decoded_text),
                    "raw_hex": bytes(raw_bytes).hex(),
                    "time": time.time(),
                }
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f)
                os.replace(temp_path, file_path)
            except Exception as e:
                logger.debug(f"Failed to persist cache file for {url}: {e}")

    def clear_cache(self) -> None:
        """Clear memory and disk HTTP response caches."""
        self._memory_cache.clear()
        if self.cache_dir and os.path.isdir(self.cache_dir):
            try:
                shutil.rmtree(self.cache_dir, ignore_errors=True)
            except Exception:
                pass

    def clear_cookies(self) -> None:
        """Clear all stored cookies from the session cookie jar."""
        if hasattr(self.cookie_jar, "clear"):
            try:
                self.cookie_jar.clear()
            except Exception:
                self.cookie_jar = http.cookiejar.CookieJar()
        else:
            self.cookie_jar = http.cookiejar.CookieJar()

    def get_cookie_dict(self) -> Dict[str, str]:
        """Return all cookies stored in the session cookie jar as a dictionary."""
        cookie_dict: Dict[str, str] = {}
        if self.cookie_jar is not None:
            try:
                for c in self.cookie_jar:
                    if hasattr(c, "name") and hasattr(c, "value"):
                        cookie_dict[c.name] = c.value
            except Exception:
                pass
        return cookie_dict

    def close(self) -> None:
        """Release HTTP client session resources, cookie jar, and connection handlers."""
        self.clear_cookies()
        if hasattr(self.opener, "close"):
            try:
                self.opener.close()
            except Exception:
                pass
        if hasattr(self.opener, "handlers"):
            for h in getattr(self.opener, "handlers", []):
                if hasattr(h, "close"):
                    try:
                        h.close()
                    except Exception:
                        pass

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def __enter__(self) -> "SafeHttpClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.close()
        return False

    def get_random_user_agent(self) -> str:
        """Return a random User-Agent string from pool."""
        return random.choice(USER_AGENT_POOL)

    def _sleep_with_jitter(self):
        """Perform rate limit sleep with randomized jitter and cooldowns."""
        # Prune expired cookies to prevent unbounded memory growth
        if hasattr(self.cookie_jar, "clear_expired_cookies"):
            try:
                self.cookie_jar.clear_expired_cookies()
            except Exception:
                pass
        try:
            if len(self.cookie_jar) > self.max_cookies:
                logger.info(
                    f"Cookie jar exceeded {self.max_cookies} entries. Pruning cookies to protect memory."
                )
                self.clear_cookies()
        except Exception:
            pass

        min_d = max(0.0, float(min(self.min_delay, self.max_delay)))
        max_d = max(0.0, float(max(self.min_delay, self.max_delay)))
        if max_d <= 0:
            self.last_request_time = time.time()
            self.request_count += 1
            return

        now = time.time()
        elapsed = now - self.last_request_time

        # Cooldown trigger (every 18 requests, pause 5-8s)
        if self.request_count > 0 and self.request_count % self.cooldown_interval == 0:
            extra_cooldown = random.uniform(5.0, 8.0)
            logger.info(f"Cooldown triggered after {self.request_count} requests. Sleeping {extra_cooldown:.2f}s...")
            time.sleep(extra_cooldown)

        # Standard jittered delay (1.5s - 3.5s)
        target_delay = random.uniform(min_d, max_d)
        if elapsed < target_delay:
            sleep_duration = target_delay - elapsed
            time.sleep(sleep_duration)

        self.last_request_time = time.time()
        self.request_count += 1

    def warm_up_session(self, base_url: str, referer: Optional[str] = None) -> bool:
        """
        Warm up cookie jar by sending a light GET request to base URL.
        Captures session cookies to bypass initial verification challenges.
        """
        if not base_url or not isinstance(base_url, str) or not base_url.strip():
            logger.warning(f"Invalid base_url for session warm-up: {base_url!r}")
            return False
        logger.info(f"Warming up session on base domain: {base_url}")
        try:
            headers = get_random_headers(referer=referer)
            req = urllib.request.Request(base_url.strip(), headers=headers)
            with self.opener.open(req, timeout=self.timeout) as resp:
                _ = resp.read(1024)
            logger.info(f"Session warmed up successfully on {base_url}. Cookies in jar: {len(self.cookie_jar)}")
            return True
        except Exception as e:
            logger.warning(f"Session warm-up encountered notice on {base_url}: {e}")
            return False

    @staticmethod
    def _parse_retry_after(he: urllib.error.HTTPError) -> Optional[float]:
        """Parse standard HTTP Retry-After header (seconds or RFC date)."""
        if not hasattr(he, "headers") or not he.headers:
            return None
        val = he.headers.get("Retry-After")
        if not val:
            return None
        val_str = str(val).strip()
        try:
            sec = float(val_str)
            return max(0.0, sec)
        except (ValueError, TypeError):
            pass
        try:
            parsed_tuple = email.utils.parsedate_to_datetime(val_str)
            if parsed_tuple:
                now_dt = datetime.now(timezone.utc)
                if parsed_tuple.tzinfo is None:
                    parsed_tuple = parsed_tuple.replace(tzinfo=timezone.utc)
                diff = (parsed_tuple - now_dt).total_seconds()
                return max(0.0, diff)
        except Exception:
            pass
        return None

    def request(
        self,
        url: str,
        method: str = "GET",
        data: Optional[Union[Dict[str, Any], bytes, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        encoding: Optional[str] = None,
        referer: Optional[str] = None,
        timeout: Optional[Union[float, Tuple[float, float]]] = None,
        connect_timeout: Optional[float] = None,
        read_timeout: Optional[float] = None,
    ) -> Tuple[int, str, bytes]:
        """
        Execute an HTTP request with automatic rate limiting, header injection,
        retry on failure with exponential backoff, bounded memory reading, and encoding detection.

        Returns: (status_code, decoded_text, raw_bytes)
        """
        if not url or not isinstance(url, str) or not url.strip():
            logger.warning(f"Invalid or empty URL provided to request: {url!r}")
            return 0, "", b""

        norm_url = url.strip()
        if not (norm_url.startswith("http://") or norm_url.startswith("https://")):
            logger.warning(f"Unsupported URL scheme: {norm_url!r}")
            return 0, "", b""

        self.last_response_from_cache = False
        self._sleep_with_jitter()

        req_headers = get_random_headers(referer=referer)
        if headers:
            req_headers.update(headers)

        payload_bytes = None
        if data is not None:
            if isinstance(data, dict):
                payload_bytes = urllib.parse.urlencode(data).encode("utf-8")
                req_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
            elif isinstance(data, bytes):
                payload_bytes = data
            elif isinstance(data, str):
                payload_bytes = data.encode("utf-8")

        # Resolve explicit connect and read timeouts
        if connect_timeout is not None:
            try:
                eff_connect_timeout = float(connect_timeout)
            except (ValueError, TypeError):
                eff_connect_timeout = self._connect_timeout
        elif isinstance(timeout, (tuple, list)) and len(timeout) >= 2:
            try:
                eff_connect_timeout = float(timeout[0])
            except (ValueError, TypeError):
                eff_connect_timeout = self._connect_timeout
        elif isinstance(timeout, (int, float)) and float(timeout) > 0:
            eff_connect_timeout = min(5.0, float(timeout))
        else:
            eff_connect_timeout = self._connect_timeout

        if read_timeout is not None:
            try:
                eff_read_timeout = float(read_timeout)
            except (ValueError, TypeError):
                eff_read_timeout = self._read_timeout
        elif isinstance(timeout, (tuple, list)) and len(timeout) >= 2:
            try:
                eff_read_timeout = float(timeout[1])
            except (ValueError, TypeError):
                eff_read_timeout = self._read_timeout
        elif isinstance(timeout, (int, float)) and float(timeout) > 0:
            eff_read_timeout = float(timeout)
        else:
            try:
                raw_to = float(self.timeout)
                eff_read_timeout = raw_to if raw_to > 0 else 15.0
            except (ValueError, TypeError):
                eff_read_timeout = 15.0

        eff_timeout = eff_read_timeout

        for attempt in range(1, self.max_retries + 1):
            if attempt > 1:
                req_headers["User-Agent"] = self.get_random_user_agent()
            try:
                req = urllib.request.Request(
                    norm_url,
                    data=payload_bytes,
                    headers=req_headers,
                    method=method.upper()
                )
                resp = self.opener.open(req, timeout=eff_timeout)
                try:
                    status_code = resp.getcode()

                    if hasattr(resp, "fp") and resp.fp and hasattr(resp.fp, "raw") and hasattr(resp.fp.raw, "_sock"):
                        try:
                            resp.fp.raw._sock.settimeout(eff_read_timeout)
                        except Exception:
                            pass

                    # Bounded stream reading up to max_response_size
                    chunks = []
                    bytes_read = 0
                    while True:
                        try:
                            chunk = resp.read(65536)
                        except TypeError:
                            chunk = resp.read()
                        except http.client.IncompleteRead as ire:
                            logger.warning(
                                f"IncompleteRead on {norm_url} (Attempt {attempt}/{self.max_retries}): "
                                f"{len(ire.partial)} partial bytes received before disconnect."
                            )
                            if ire.partial:
                                chunks.append(ire.partial)
                                bytes_read += len(ire.partial)
                            if attempt < self.max_retries:
                                raise
                            break
                        if not chunk or not isinstance(chunk, (bytes, str)):
                            break
                        chunks.append(chunk)
                        bytes_read += len(chunk)
                        if bytes_read >= self.max_response_size:
                            logger.warning(
                                f"Response from {norm_url} exceeded max size ({self.max_response_size} bytes). Truncating."
                            )
                            break
                        if len(chunk) > 65536:
                            break
                    raw_bytes = b"".join(chunks)

                    # Detect charset from response headers
                    content_type = resp.headers.get("Content-Type", "") if hasattr(resp, "headers") and resp.headers else ""
                    detected_encoding = encoding or self._detect_encoding(content_type, raw_bytes)
                    decoded_text = robust_decode(raw_bytes, declared_encoding=detected_encoding)

                    if status_code == 200 and decoded_text:
                        self.set_cached_response(norm_url, status_code, decoded_text, raw_bytes)

                    return status_code, decoded_text, raw_bytes
                finally:
                    if hasattr(resp, "close"):
                        try:
                            resp.close()
                        except Exception:
                            pass

            except urllib.error.HTTPError as he:
                logger.warning(f"HTTPError {he.code} on {norm_url} (Attempt {attempt}/{self.max_retries}): {he.reason}")
                try:
                    retryable_codes = [408, 429, 403, 500, 502, 503, 504, 520, 521, 522, 523, 524]
                    if he.code in retryable_codes and attempt < self.max_retries:
                        if he.code in (403, 429):
                            self.clear_cookies()
                        retry_after = self._parse_retry_after(he) if he.code == 429 else None
                        if retry_after is not None and retry_after > 0:
                            backoff = min(60.0, retry_after)
                        else:
                            backoff = min(60.0, (2 ** attempt) * 2.0 + random.uniform(1.0, 3.0))
                        logger.info(f"Backing off for {backoff:.2f}s before retry (status {he.code})...")
                        time.sleep(backoff)
                    else:
                        if he.code in [500, 502, 503, 504, 520, 521, 522, 523, 524] and self.cache_fallback:
                            cached = self.get_cached_response(norm_url)
                            if cached is not None:
                                logger.warning(
                                    f"Remote endpoint {norm_url} returned HTTP {he.code}. Falling back to cached response."
                                )
                                self.last_response_from_cache = True
                                return cached
                        try:
                            try:
                                raw_bytes = he.read(self.max_response_size)
                            except TypeError:
                                raw_bytes = he.read()
                            decoded_text = robust_decode(raw_bytes, declared_encoding=encoding or "utf-8")
                            return he.code, decoded_text, raw_bytes
                        except Exception:
                            return he.code, "", b""
                finally:
                    try:
                        if hasattr(he, "fp") and he.fp:
                            he.fp.close()
                        he.close()
                    except Exception:
                        pass
            except (
                TimeoutError,
                socket.timeout,
                urllib.error.URLError,
                http.client.RemoteDisconnected,
                http.client.IncompleteRead,
                http.client.HTTPException,
                ConnectionError,
                BrokenPipeError,
                ssl.SSLError,
                socket.gaierror,
                OSError,
                Exception,
            ) as ex:
                logger.warning(f"Request error on {norm_url} (Attempt {attempt}/{self.max_retries}): {ex}")
                if attempt < self.max_retries:
                    backoff = min(30.0, (2 ** attempt) * 1.5 + random.uniform(0.5, 1.5))
                    time.sleep(backoff)
                else:
                    if self.cache_fallback:
                        cached = self.get_cached_response(norm_url)
                        if cached is not None:
                            logger.warning(
                                f"Remote endpoint {norm_url} unreachable ({ex}). Falling back to cached response."
                            )
                            self.last_response_from_cache = True
                            return cached
                    break

        if self.cache_fallback:
            cached = self.get_cached_response(norm_url)
            if cached is not None:
                logger.warning(
                    f"Remote endpoint {norm_url} unreachable. Falling back to cached response."
                )
                self.last_response_from_cache = True
                return cached

        logger.error(f"Failed to fetch {norm_url} after {self.max_retries} attempts.")
        return 0, "", b""

    def get(
        self,
        url: str,
        referer: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[Union[float, Tuple[float, float]]] = None,
        connect_timeout: Optional[float] = None,
        read_timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> Tuple[int, str]:
        """Convenience GET helper returning (status_code, decoded_text)."""
        status, text, _ = self.request(
            url,
            method="GET",
            headers=headers,
            referer=referer,
            timeout=timeout,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
        )
        return status, text

    def post(
        self,
        url: str,
        data: Optional[Union[Dict[str, Any], bytes, str]] = None,
        referer: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[Union[float, Tuple[float, float]]] = None,
        connect_timeout: Optional[float] = None,
        read_timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> Tuple[int, str]:
        """Convenience POST helper returning (status_code, decoded_text)."""
        status, text, _ = self.request(
            url,
            method="POST",
            data=data,
            headers=headers,
            referer=referer,
            timeout=timeout,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
        )
        return status, text

    @staticmethod
    def _detect_encoding(content_type: str, raw_bytes: bytes) -> str:
        """Detect encoding from Content-Type header or HTML meta tags."""
        match = re.search(r"charset=([\w\-]+)", content_type, re.IGNORECASE)
        if match:
            return match.group(1).strip().lower()

        # Check HTML meta charset in initial bytes
        prefix = raw_bytes[:4096].decode("ascii", "ignore")
        meta_match = re.search(r'<meta[^>]+charset=["\']?([\w\-]+)', prefix, re.IGNORECASE)
        if meta_match:
            return meta_match.group(1).strip().lower()

        meta_http = re.search(r'<meta[^>]+http-equiv=["\']?content-type["\']?[^>]+content=["\'][^"\']*charset=([\w\-]+)', prefix, re.IGNORECASE)
        if meta_http:
            return meta_http.group(1).strip().lower()

        return "utf-8"


def robust_decode(raw_bytes: Union[bytes, str, None], declared_encoding: Optional[str] = None) -> str:
    """Decode raw bytes with graceful cascade across Korean/Universal charsets."""
    if raw_bytes is None:
        return ""
    if isinstance(raw_bytes, str):
        return raw_bytes
    if not raw_bytes:
        return ""

    encodings_to_try = [declared_encoding, "utf-8", "cp949", "euc-kr", "latin-1"]
    for enc in encodings_to_try:
        if not enc or not isinstance(enc, str):
            continue
        try:
            return raw_bytes.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw_bytes.decode("utf-8", errors="replace")


def encode_euc_kr_query(params: Dict[str, Any]) -> bytes:
    """Encode dictionary into URL-encoded bytes using EUC-KR / CP949 (for Bobae/Pomppu)."""
    encoded_pairs = []
    for k, v in params.items():
        k_str = str(k)
        v_str = str(v)
        try:
            v_encoded = urllib.parse.quote(v_str.encode("euc-kr"))
        except UnicodeEncodeError:
            v_encoded = urllib.parse.quote(v_str.encode("cp949", errors="replace"))
        encoded_pairs.append(f"{k_str}={v_encoded}")
    return "&".join(encoded_pairs).encode("ascii")


def clean_html_text(raw_html: Union[str, bytes, Any]) -> str:
    """Remove HTML tags, script/style blocks, decode entities, and normalize whitespace."""
    if raw_html is None:
        return ""
    if isinstance(raw_html, bytes):
        raw_html = robust_decode(raw_html)
    elif not isinstance(raw_html, str):
        return ""
    if not raw_html:
        return ""

    cleaned = raw_html.replace("\x00", " ")
    cleaned = re.sub(r"<!--.*?-->", " ", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"<(script|style)[^>]*>(?:.*?</\1>|.*$)", " ", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<(br|p|/p|div|/div|li|/li|h\d|/h\d|tr|/tr|dt|/dt|dd|/dd)[^>]*>", "\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"<[a-zA-Z/][^<]*$", " ", cleaned)
    cleaned = html.unescape(cleaned)
    if "&" in cleaned:
        cleaned = html.unescape(cleaned)
    cleaned = (
        cleaned.replace("\xa0", " ")
        .replace("\u200b", "")
        .replace("\ufeff", "")
        .replace("\u3000", " ")
    )
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in cleaned.splitlines()]
    return "\n".join([line for line in lines if line])


def extract_slang_terms(text: str, slang_dictionary: Dict[str, Any]) -> List[str]:
    """Find all matching slang terms present in the text."""
    if not text or not slang_dictionary:
        return []
    found_terms = []
    text_lower = text.lower()
    keys_iter = slang_dictionary.keys() if hasattr(slang_dictionary, "keys") else slang_dictionary
    for term in keys_iter:
        term_str = str(term)
        if term_str.lower() in text_lower or term_str in text:
            found_terms.append(term_str)
    return sorted(list(set(found_terms)))


def save_complaints_json(records: List[Union[ComplaintRecord, Dict[str, Any]]], output_path: str):
    """Save complaint records into formatted JSON file atomically and safely."""
    if not output_path:
        logger.warning("Empty output_path provided to save_complaints_json")
        return
    try:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        data = []
        for r in records:
            if isinstance(r, ComplaintRecord):
                data.append(r.to_dict())
            elif isinstance(r, dict):
                data.append(r)
            else:
                try:
                    data.append(dict(r))
                except Exception:
                    continue

        temp_path = f"{output_path}.tmp.{os.getpid()}"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, output_path)
        logger.info(f"Saved {len(data)} complaint records to {output_path}")
    except Exception as e:
        logger.error(f"Failed to save complaints JSON to {output_path}: {e}")
        if "temp_path" in locals() and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


def load_complaints_json(input_path: str) -> List[Dict[str, Any]]:
    """Load complaint records from JSON file with fault-tolerant error recovery."""
    if not input_path or not os.path.exists(input_path):
        logger.warning(f"File not found or empty path: {input_path}")
        return []
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                logger.warning(f"Empty JSON file at {input_path}")
                return []
            data = json.loads(content)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return [data]
            return []
    except json.JSONDecodeError as jde:
        logger.error(f"Corrupted or invalid JSON in {input_path}: {jde}")
        return []
    except Exception as e:
        logger.error(f"Error reading JSON from {input_path}: {e}")
        return []
