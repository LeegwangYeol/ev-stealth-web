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
import ipaddress
import json
import logging
import math
import os
import random
import re
import shutil
import socket
import ssl
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("ScraperCommonUtils")

# User-Agent Pool (Modern Desktop browsers only - prevents mobile redirect loops on Korean forums)
USER_AGENT_POOL = [
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    # Firefox on Windows & macOS
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.6; rv:129.0) Gecko/20100101 Firefox/129.0",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0",
]

# Safe memory and resource boundaries
MAX_RESPONSE_BYTES: int = 10 * 1024 * 1024  # 10MB per HTTP response to prevent OOM
MAX_COOKIEJAR_ENTRIES: int = 500  # Prune cookie jar beyond 500 entries to prevent memory growth

# SSRF Defense constants
DISALLOWED_HOSTS: Set[str] = {
    "localhost",
    "metadata.google.internal",
    "metadata",
    "instance-data",
}
DISALLOWED_HOST_SUFFIXES: Tuple[str, ...] = (
    ".localhost",
    ".local",
    ".internal",
    ".lan",
    ".localdomain",
    ".intranet",
)
STANDARD_SAFE_PORTS: Set[int] = {80, 443, 8080, 8443, 8000, 8888}
DEFAULT_FALLBACK_USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


def _positive_float(value: Any, default: float) -> float:
    """Convert value to a positive finite float, or return default."""
    if value is None or isinstance(value, bool):
        return default
    try:
        num = float(value)
    except (ValueError, TypeError):
        return default
    if not math.isfinite(num) or num <= 0:
        return default
    return num


def resolve_timeout_pair(
    timeout: Union[float, Tuple[float, float], None] = (5.0, 15.0),
    connect_timeout: Optional[float] = None,
    read_timeout: Optional[float] = None,
    default_connect: float = 5.0,
    default_read: float = 15.0,
) -> Tuple[float, float]:
    """Resolve explicit finite positive (connect_timeout, read_timeout) pair."""
    if connect_timeout is not None:
        conn = _positive_float(connect_timeout, default_connect)
    elif isinstance(timeout, (tuple, list)) and len(timeout) >= 2:
        conn = _positive_float(timeout[0], default_connect)
    elif isinstance(timeout, (int, float)) and not isinstance(timeout, bool) and math.isfinite(float(timeout)) and float(timeout) > 0:
        conn = min(default_connect, float(timeout))
    else:
        conn = default_connect

    if read_timeout is not None:
        read = _positive_float(read_timeout, default_read)
    elif isinstance(timeout, (tuple, list)) and len(timeout) >= 2:
        read = _positive_float(timeout[1], default_read)
    elif isinstance(timeout, (int, float)) and not isinstance(timeout, bool) and math.isfinite(float(timeout)) and float(timeout) > 0:
        read = float(timeout)
    else:
        read = default_read

    return conn, read


def normalize_scraper_url(raw_url: Any, base_url: str) -> Optional[str]:
    """Normalize a scraped link or post URL against base_url while rejecting unsafe schemes."""
    if not raw_url or not isinstance(raw_url, str):
        return None
    eff_url = html.unescape(raw_url.strip())
    if not eff_url or any(ord(c) < 32 or ord(c) == 127 for c in eff_url):
        return None
    try:
        parsed = urllib.parse.urlsplit(eff_url)
    except Exception:
        return None
    if parsed.scheme and parsed.scheme.lower() not in ("http", "https"):
        return None
    if eff_url.startswith("//"):
        base_scheme = urllib.parse.urlsplit(base_url).scheme or "https"
        return f"{base_scheme}:{eff_url}"
    if eff_url.lower().startswith(("http://", "https://")):
        return eff_url
    if parsed.scheme:
        # Malformed scheme-relative or schemed URL without '//' (e.g. 'https:evil.com')
        return None
    if eff_url.startswith("/"):
        return urllib.parse.urljoin(base_url, eff_url)
    base_clean = base_url.rstrip("/")
    return f"{base_clean}/{eff_url}"


def is_safe_ip(ip: Union[ipaddress.IPv4Address, ipaddress.IPv6Address]) -> bool:
    """Check if an IP address is publicly routable and safe from SSRF."""
    if (
        not ip.is_global
        or ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        mapped = ip.ipv4_mapped
        if (
            not mapped.is_global
            or mapped.is_loopback
            or mapped.is_private
            or mapped.is_link_local
            or mapped.is_multicast
            or mapped.is_reserved
            or mapped.is_unspecified
        ):
            return False
    if str(ip) in ("169.254.169.254", "100.100.100.200"):
        return False
    return True


def is_safe_url(
    url: str,
    allow_private_ips: bool = False,
    allowed_ports: Optional[Set[int]] = None,
) -> Tuple[bool, str]:
    """Verify URL against SSRF attacks (private subnets, cloud metadata, non-HTTP schemes)."""
    if not url or not isinstance(url, str):
        return False, "Empty or invalid URL"
    if any(ord(c) < 32 or ord(c) == 127 for c in url):
        return False, "Invalid control character in URL"

    url_str = url.strip()
    if not url_str:
        return False, "Empty URL"

    try:
        parsed = urllib.parse.urlsplit(url_str)
    except Exception as e:
        return False, f"URL parsing error: {e}"

    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        return False, f"Disallowed URL scheme: {scheme!r} (only http/https allowed)"

    hostname = parsed.hostname
    if not hostname:
        return False, "Missing hostname in URL"

    host_lower = hostname.lower().strip().rstrip(".")
    if not host_lower:
        return False, "Missing hostname in URL"

    if allow_private_ips:
        return True, "Private IPs allowed by configuration"

    if host_lower in DISALLOWED_HOSTS:
        return False, f"SSRF blocked: Disallowed hostname '{host_lower}'"

    for suffix in DISALLOWED_HOST_SUFFIXES:
        if host_lower.endswith(suffix):
            return False, f"SSRF blocked: Hostname '{host_lower}' matches disallowed internal suffix '{suffix}'"

    ports_set = allowed_ports if allowed_ports is not None else STANDARD_SAFE_PORTS
    try:
        parsed_port = parsed.port
    except ValueError:
        return False, "SSRF blocked: Invalid port in URL"
    if parsed_port is not None and parsed_port not in ports_set:
        return False, f"SSRF blocked: Disallowed port {parsed_port}"

    try:
        ip = ipaddress.ip_address(host_lower)
        if not is_safe_ip(ip):
            return False, f"SSRF blocked: Unsafe IP address {ip}"
        return True, "Safe public IP"
    except ValueError:
        pass

    try:
        packed = socket.inet_aton(host_lower)
        ip4 = ipaddress.IPv4Address(packed)
        if not is_safe_ip(ip4):
            return False, f"SSRF blocked: Unsafe encoded IP address {ip4}"
        return True, "Safe public IP"
    except (OSError, ValueError):
        pass

    try:
        addr_info = socket.getaddrinfo(host_lower, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        if addr_info:
            for family, socktype, proto, canonname, sockaddr in addr_info:
                ip_str = sockaddr[0]
                try:
                    resolved_ip = ipaddress.ip_address(ip_str)
                    if not is_safe_ip(resolved_ip):
                        return False, f"SSRF blocked: Domain '{host_lower}' resolves to unsafe IP {resolved_ip}"
                except ValueError:
                    continue
    except socket.gaierror:
        pass
    except Exception as e:
        logger.debug(f"DNS check notice for {host_lower}: {e}")

    return True, "Safe URL"

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
        self._conn_timeout = _positive_float(connect_timeout, 5.0)
        self._read_timeout = _positive_float(read_timeout, 15.0)
        super().__init__(*args, **kwargs)

    def connect(self):
        self.sock = socket.create_connection(
            (self.host, self.port),
            self._conn_timeout,
            self.source_address,
        )
        try:
            if self._read_timeout is not None:
                self.sock.settimeout(self._read_timeout)
        except Exception:
            if self.sock is not None:
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None
            raise


class ResilientHTTPSConnection(http.client.HTTPSConnection):
    """HTTPSConnection supporting explicit separate connect and read timeouts."""

    def __init__(self, *args, connect_timeout: float = 5.0, read_timeout: float = 15.0, **kwargs):
        self._conn_timeout = _positive_float(connect_timeout, 5.0)
        self._read_timeout = _positive_float(read_timeout, 15.0)
        super().__init__(*args, **kwargs)

    def connect(self):
        self.sock = socket.create_connection(
            (self.host, self.port),
            self._conn_timeout,
            self.source_address,
        )
        try:
            if self._read_timeout is not None:
                self.sock.settimeout(self._read_timeout)
            if self._tunnel_host:
                self._tunnel()
            server_hostname = (self._tunnel_host or self.host) if ssl.HAS_SNI else None
            self.sock = self._context.wrap_socket(self.sock, server_hostname=server_hostname)
        except Exception:
            if self.sock is not None:
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None
            raise


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """HTTP redirect handler that validates target URLs against SSRF before following."""

    def __init__(
        self,
        allow_private_ips: bool = False,
        allowed_ports: Optional[Set[int]] = None,
    ):
        super().__init__()
        self.allow_private_ips = allow_private_ips
        self.allowed_ports = allowed_ports

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        is_safe, reason = is_safe_url(
            newurl,
            allow_private_ips=self.allow_private_ips,
            allowed_ports=self.allowed_ports,
        )
        if not is_safe:
            logger.warning(f"SSRF defense blocked redirect from {req.full_url} to {newurl}: {reason}")
            raise urllib.error.HTTPError(
                newurl, 403, f"SSRF Blocked: Unsafe redirect target ({reason})", headers, fp
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class ResilientHTTPHandler(urllib.request.HTTPHandler):
    """HTTP handler injecting ResilientHTTPConnection with explicit timeouts."""

    def __init__(self, connect_timeout: float = 5.0, read_timeout: float = 15.0, **kwargs):
        super().__init__(**kwargs)
        self._connect_timeout = _positive_float(connect_timeout, 5.0)
        self._read_timeout = _positive_float(read_timeout, 15.0)

    def http_open(self, req):
        conn_to = getattr(req, "_connect_timeout", self._connect_timeout)
        read_to = getattr(req, "_read_timeout", self._read_timeout)

        def _factory(host, **kwargs):
            return ResilientHTTPConnection(
                host,
                connect_timeout=conn_to,
                read_timeout=read_to,
                **kwargs,
            )
        return self.do_open(_factory, req)


class ResilientHTTPSHandler(urllib.request.HTTPSHandler):
    """HTTPS handler injecting ResilientHTTPSConnection with explicit timeouts."""

    def __init__(self, connect_timeout: float = 5.0, read_timeout: float = 15.0, context=None, **kwargs):
        super().__init__(context=context, **kwargs)
        self._connect_timeout = _positive_float(connect_timeout, 5.0)
        self._read_timeout = _positive_float(read_timeout, 15.0)

    def https_open(self, req):
        conn_to = getattr(req, "_connect_timeout", self._connect_timeout)
        read_to = getattr(req, "_read_timeout", self._read_timeout)

        def _factory(host, **kwargs):
            ctx = getattr(self, "_context", None)
            if ctx is not None:
                kwargs.setdefault("context", ctx)
            if hasattr(self, "_check_hostname"):
                kwargs.setdefault("check_hostname", getattr(self, "_check_hostname"))
            return ResilientHTTPSConnection(
                host,
                connect_timeout=conn_to,
                read_timeout=read_to,
                **kwargs,
            )
        return self.do_open(_factory, req)


class CircuitBreakerState:
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """
    Host-level Circuit Breaker preventing aggressive hammer on target sites
    returning HTTP 403 (Forbidden/WAF), 429 (Rate Limit), 503 (Service Unavailable),
    or consecutive connection drops.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        cooldown_seconds: float = 30.0,
        half_open_max_probes: int = 1,
    ):
        self.failure_threshold = max(1, int(failure_threshold))
        self.cooldown_seconds = max(0.01, float(cooldown_seconds))
        self.half_open_max_probes = max(1, int(half_open_max_probes))
        self._lock = threading.Lock()
        self._hosts: Dict[str, Dict[str, Any]] = {}

    def _extract_host(self, url_or_host: str) -> str:
        if not url_or_host:
            return ""
        s = str(url_or_host).strip()
        if "://" in s:
            try:
                parsed = urllib.parse.urlsplit(s)
                if parsed.hostname:
                    return parsed.hostname.lower()
            except Exception:
                pass
        try:
            parsed = urllib.parse.urlsplit("//" + s)
            if parsed.hostname:
                return parsed.hostname.lower()
        except Exception:
            pass
        return s.lower().split(":")[0].split("/")[0]

    def record_probe(self, url_or_host: str) -> None:
        """Record that a canary probe is in-flight for this host during HALF_OPEN state."""
        host = self._extract_host(url_or_host)
        if not host:
            return
        with self._lock:
            info = self._hosts.get(host)
            if info and info.get("state") == CircuitBreakerState.HALF_OPEN:
                info["probe_count"] = info.get("probe_count", 0) + 1

    def try_acquire(self, url_or_host: str) -> bool:
        """Atomically check availability and reserve a HALF_OPEN canary probe slot if applicable."""
        host = self._extract_host(url_or_host)
        if not host:
            return True
        with self._lock:
            info = self._hosts.get(host)
            if not info:
                return True
            state = info.get("state", CircuitBreakerState.CLOSED)
            if state == CircuitBreakerState.CLOSED:
                return True
            now = time.time()
            if state == CircuitBreakerState.OPEN:
                if now >= info.get("tripped_until", 0.0):
                    info["state"] = CircuitBreakerState.HALF_OPEN
                    info["probe_count"] = 1
                    return True
                return False
            if state == CircuitBreakerState.HALF_OPEN:
                if info.get("probe_count", 0) < self.half_open_max_probes:
                    info["probe_count"] = info.get("probe_count", 0) + 1
                    return True
                return False
            return True

    def is_available(self, url_or_host: str) -> bool:
        """Returns True if requests can be dispatched to this host."""
        host = self._extract_host(url_or_host)
        if not host:
            return True
        with self._lock:
            info = self._hosts.get(host)
            if not info:
                return True
            state = info.get("state", CircuitBreakerState.CLOSED)
            if state == CircuitBreakerState.CLOSED:
                return True
            now = time.time()
            if state == CircuitBreakerState.OPEN:
                if now >= info.get("tripped_until", 0.0):
                    info["state"] = CircuitBreakerState.HALF_OPEN
                    info["probe_count"] = 0
                    return True
                return False
            if state == CircuitBreakerState.HALF_OPEN:
                return info.get("probe_count", 0) < self.half_open_max_probes
            return True

    def is_open(self, url_or_host: str) -> bool:
        """Returns True if the circuit breaker is OPEN for this host."""
        return not self.is_available(url_or_host)

    def can_request(self, url_or_host: str) -> bool:
        """Returns True if requests can be dispatched to this host (alias for is_available)."""
        return self.is_available(url_or_host)

    def record_success(self, url_or_host: str) -> None:
        """Record successful response, resetting circuit to CLOSED."""
        host = self._extract_host(url_or_host)
        if not host:
            return
        with self._lock:
            info = self._hosts.get(host)
            if info:
                info["state"] = CircuitBreakerState.CLOSED
                info["failure_count"] = 0
                info["probe_count"] = 0

    def record_failure(
        self,
        url_or_host: str,
        status_code: Optional[int] = None,
        retry_after: Optional[float] = None,
    ) -> bool:
        """
        Record failure for host. If status_code is in (403, 429, 503) or network failure,
        increments failure count and trips circuit if threshold exceeded.
        Returns True if circuit was tripped to OPEN.
        """
        host = self._extract_host(url_or_host)
        if not host:
            return False
        with self._lock:
            if host not in self._hosts:
                self._hosts[host] = {
                    "state": CircuitBreakerState.CLOSED,
                    "failure_count": 0,
                    "tripped_until": 0.0,
                    "probe_count": 0,
                }
            info = self._hosts[host]
            info["failure_count"] = info.get("failure_count", 0) + 1
            tripped = False

            cooldown = self.cooldown_seconds
            if retry_after is not None:
                try:
                    ra_val = float(retry_after)
                    if math.isfinite(ra_val) and ra_val > 0:
                        cooldown = max(cooldown, min(3600.0, ra_val))
                except (ValueError, TypeError):
                    pass

            now = time.time()
            if info.get("state") == CircuitBreakerState.HALF_OPEN:
                # Canary probe failed; re-trip circuit
                info["state"] = CircuitBreakerState.OPEN
                info["tripped_until"] = now + cooldown
                tripped = True
            elif info["failure_count"] >= self.failure_threshold:
                info["state"] = CircuitBreakerState.OPEN
                info["tripped_until"] = now + cooldown
                tripped = True

            return tripped

    def get_state(self, url_or_host: str) -> str:
        host = self._extract_host(url_or_host)
        with self._lock:
            info = self._hosts.get(host)
            if not info:
                return CircuitBreakerState.CLOSED
            state = info.get("state", CircuitBreakerState.CLOSED)
            if state == CircuitBreakerState.OPEN and time.time() >= info.get("tripped_until", 0.0):
                info["state"] = CircuitBreakerState.HALF_OPEN
                info["probe_count"] = 0
                return CircuitBreakerState.HALF_OPEN
            return state

    def reset(self, url_or_host: Optional[str] = None) -> None:
        with self._lock:
            if url_or_host:
                host = self._extract_host(url_or_host)
                if host in self._hosts:
                    del self._hosts[host]
            else:
                self._hosts.clear()


try:
    from bs4 import BeautifulSoup, FeatureNotFound  # type: ignore
    BS4_AVAILABLE = True
except ImportError:
    BeautifulSoup = None  # type: ignore
    FeatureNotFound = Exception  # type: ignore
    BS4_AVAILABLE = False


def safe_soup_parse(markup: Union[str, bytes, Any], preferred_parser: str = "html.parser") -> Any:
    """
    Safely parse HTML markup using BeautifulSoup if installed,
    with comprehensive error handling for FeatureNotFound, ParserRejectedMarkup,
    RecursionError, AttributeError, TypeError, and malformed HTML.
    Returns BeautifulSoup instance if available and successfully parsed, else None.
    """
    if markup is None or not BS4_AVAILABLE or BeautifulSoup is None:
        return None

    if isinstance(markup, bytes):
        text = robust_decode(markup)
    elif isinstance(markup, str):
        text = markup
    else:
        return None

    if not text.strip():
        return None

    sanitized = text.replace("\x00", " ")

    parsers_to_try = [preferred_parser, "html.parser", "lxml", "html5lib"]
    seen = set()
    for parser in parsers_to_try:
        if parser in seen:
            continue
        seen.add(parser)
        try:
            return BeautifulSoup(sanitized, parser)
        except Exception as e:
            logger.debug(f"BeautifulSoup parser '{parser}' notice: {e}")
            continue

    return None


def safe_extract_html_text(markup: Union[str, bytes, Any]) -> str:
    """
    Extract visible text from HTML markup, attempting BeautifulSoup first if available,
    falling back to clean_html_text on any exception or if bs4 is uninstalled.
    """
    if markup is None:
        return ""
    soup = safe_soup_parse(markup)
    if soup is not None:
        try:
            for s in soup(["script", "style", "noscript"]):
                s.decompose()
            text = soup.get_text(separator="\n", strip=True)
            if text:
                return text
        except Exception as e:
            logger.debug(f"Failed extracting text via BeautifulSoup: {e}")

    return clean_html_text(markup)


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
        failure_threshold: int = 3,
        circuit_cooldown: float = 30.0,
        cooldown_seconds: Optional[float] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        allow_private_ips: bool = False,
        allowed_ports: Optional[Set[int]] = None,
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
        self.allow_private_ips = bool(allow_private_ips)
        self.allowed_ports = set(allowed_ports) if allowed_ports is not None else None
        self.request_count = 0
        self.last_request_time = 0.0
        self.last_response_from_cache = False
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_lock = threading.Lock()
        self._rate_lock = threading.Lock()
        eff_cooldown = cooldown_seconds if cooldown_seconds is not None else circuit_cooldown
        self.circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=failure_threshold,
            cooldown_seconds=eff_cooldown,
        )

        # Resolve explicit connect and read timeouts
        if connect_timeout is not None:
            self._connect_timeout = _positive_float(connect_timeout, 5.0)
        elif isinstance(timeout, (tuple, list)) and len(timeout) >= 2:
            self._connect_timeout = _positive_float(timeout[0], 5.0)
        elif isinstance(timeout, (int, float)) and not isinstance(timeout, bool) and math.isfinite(float(timeout)) and float(timeout) > 0:
            self._connect_timeout = min(5.0, float(timeout))
        else:
            self._connect_timeout = 5.0

        if read_timeout is not None:
            self._read_timeout = _positive_float(read_timeout, 15.0)
        elif isinstance(timeout, (tuple, list)) and len(timeout) >= 2:
            self._read_timeout = _positive_float(timeout[1], 15.0)
        elif isinstance(timeout, (int, float)) and not isinstance(timeout, bool) and math.isfinite(float(timeout)) and float(timeout) > 0:
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
            redirect_handler = SafeRedirectHandler(
                allow_private_ips=self.allow_private_ips,
                allowed_ports=self.allowed_ports,
            )
            http_handler = ResilientHTTPHandler(
                connect_timeout=self._connect_timeout,
                read_timeout=self._read_timeout,
            )
            https_handler = ResilientHTTPSHandler(
                connect_timeout=self._connect_timeout,
                read_timeout=self._read_timeout,
            )
            self.opener = urllib.request.build_opener(
                cookie_processor, redirect_handler, http_handler, https_handler
            )

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
        with self._cache_lock:
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
                    with self._cache_lock:
                        self._memory_cache[key] = {
                            "status": status,
                            "text": text,
                            "raw": raw_bytes,
                            "time": data.get("time", time.time()),
                            "url": url,
                        }
                        if len(self._memory_cache) > 500:
                            oldest_k = min(self._memory_cache, key=lambda k: self._memory_cache[k].get("time", 0))
                            del self._memory_cache[oldest_k]
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
        with self._cache_lock:
            self._memory_cache[key] = entry
            if len(self._memory_cache) > 500:
                oldest_k = min(self._memory_cache, key=lambda k: self._memory_cache[k].get("time", 0))
                del self._memory_cache[oldest_k]

        if self.cache_dir:
            temp_path = None
            try:
                os.makedirs(self.cache_dir, exist_ok=True)
                file_path = os.path.join(self.cache_dir, f"{key}.json")
                temp_fd, temp_path = tempfile.mkstemp(
                    dir=self.cache_dir,
                    prefix=f".tmp_cache_{os.getpid()}_{threading.get_ident()}_{uuid.uuid4().hex[:8]}_",
                    suffix=".json",
                )
                payload = {
                    "url": str(url),
                    "status": int(status_code),
                    "text": str(decoded_text),
                    "raw_hex": bytes(raw_bytes).hex(),
                    "time": time.time(),
                }
                with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                    json.dump(payload, f)
                os.replace(temp_path, file_path)
                temp_path = None
            except Exception as e:
                logger.debug(f"Failed to persist cache file for {url}: {e}")
            finally:
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass

    def clear_cache(self) -> None:
        """Clear memory and disk HTTP response caches."""
        with self._cache_lock:
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

    def is_circuit_open(self, url_or_host: str) -> bool:
        """Check if circuit breaker is open for the given url or host."""
        return not self.circuit_breaker.is_available(url_or_host)

    def get_circuit_state(self, url_or_host: str) -> str:
        """Return circuit breaker state ('CLOSED', 'OPEN', 'HALF_OPEN') for host."""
        return self.circuit_breaker.get_state(url_or_host)

    def reset_circuit_breaker(self, url_or_host: Optional[str] = None) -> None:
        """Reset circuit breaker failure counts and state."""
        self.circuit_breaker.reset(url_or_host)

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

    def get_random_user_agent(self, exclude: Optional[str] = None) -> str:
        """Return a random User-Agent string from pool, optionally excluding the specified UA."""
        pool = USER_AGENT_POOL if USER_AGENT_POOL else [DEFAULT_FALLBACK_USER_AGENT]
        if exclude and len(pool) > 1:
            candidates = [ua for ua in pool if ua != exclude]
            if candidates:
                return random.choice(candidates)
        return random.choice(pool)

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

        try:
            raw_min = float(self.min_delay)
            raw_max = float(self.max_delay)
        except (ValueError, TypeError):
            raw_min, raw_max = 0.0, 0.0
        if not math.isfinite(raw_min) or raw_min < 0:
            raw_min = 0.0
        if not math.isfinite(raw_max) or raw_max < 0:
            raw_max = 0.0
        min_d = min(raw_min, raw_max)
        max_d = max(raw_min, raw_max)
        if max_d <= 0:
            with self._rate_lock:
                self.last_request_time = time.time()
                self.request_count += 1
            return

        with self._rate_lock:
            now = time.time()
            elapsed = now - self.last_request_time
            req_num = self.request_count
            self.request_count += 1

        # Cooldown trigger (every cooldown_interval requests)
        if (
            self.cooldown_interval
            and not isinstance(self.cooldown_interval, bool)
            and self.cooldown_interval > 0
            and req_num > 0
            and req_num % int(self.cooldown_interval) == 0
        ):
            try:
                ct = float(self.cooldown_time)
            except (ValueError, TypeError):
                ct = 6.0
            if math.isfinite(ct) and ct > 0:
                extra_cooldown = random.uniform(ct * 0.8, ct * 1.3)
                logger.info(f"Cooldown triggered after {req_num} requests. Sleeping {extra_cooldown:.2f}s...")
                time.sleep(extra_cooldown)

        # Standard jittered delay (1.5s - 3.5s)
        target_delay = random.uniform(min_d, max_d)
        if elapsed < target_delay:
            sleep_duration = target_delay - elapsed
            time.sleep(sleep_duration)

        with self._rate_lock:
            self.last_request_time = time.time()

    def warm_up_session(self, base_url: str, referer: Optional[str] = None) -> bool:
        """
        Warm up cookie jar by sending a light GET request to base URL.
        Captures session cookies to bypass initial verification challenges.
        """
        if not base_url or not isinstance(base_url, str) or not base_url.strip():
            logger.warning(f"Invalid base_url for session warm-up: {base_url!r}")
            return False
        norm_url = base_url.strip()
        is_safe, reason = is_safe_url(
            norm_url,
            allow_private_ips=self.allow_private_ips,
            allowed_ports=self.allowed_ports,
        )
        if not is_safe:
            logger.warning(f"SSRF defense blocked warm_up_session to {norm_url}: {reason}")
            return False
        if not self.circuit_breaker.is_available(norm_url):
            logger.warning(f"Circuit breaker OPEN for {norm_url}; skipping session warm-up.")
            return False
        logger.info(f"Warming up session on base domain: {norm_url}")
        resp = None
        try:
            headers = get_random_headers(referer=referer)
            req = urllib.request.Request(norm_url, headers=headers)
            req._connect_timeout = self._connect_timeout
            req._read_timeout = self._read_timeout
            resp = self.opener.open(req, timeout=self._read_timeout)
            _ = resp.read(1024)
            self.circuit_breaker.record_success(norm_url)
            logger.info(f"Session warmed up successfully on {norm_url}. Cookies in jar: {len(self.cookie_jar)}")
            return True
        except urllib.error.HTTPError as he:
            logger.warning(f"Session warm-up HTTP {he.code} on {norm_url}: {he.reason}")
            try:
                if hasattr(he, "fp") and he.fp:
                    he.fp.close()
                he.close()
            except Exception:
                pass
            return False
        except Exception as e:
            logger.warning(f"Session warm-up encountered notice on {norm_url}: {e}")
            return False
        finally:
            if resp is not None:
                try:
                    if hasattr(resp, "close"):
                        resp.close()
                except Exception:
                    pass
                try:
                    if hasattr(resp, "fp") and resp.fp and hasattr(resp.fp, "close"):
                        resp.fp.close()
                except Exception:
                    pass

    @staticmethod
    def _parse_retry_after(he: urllib.error.HTTPError) -> Optional[float]:
        """Parse standard HTTP Retry-After header (seconds or RFC date)."""
        if not hasattr(he, "headers") or not he.headers:
            return None
        val = None
        if hasattr(he.headers, "get"):
            val = he.headers.get("Retry-After")
            if val is None:
                val = he.headers.get("retry-after")
        if val is None and hasattr(he.headers, "items"):
            for k, v in he.headers.items():
                if str(k).lower() == "retry-after":
                    val = v
                    break
        if not val:
            return None
        val_str = str(val).strip()
        try:
            sec = float(val_str)
            if math.isfinite(sec):
                return max(0.0, min(3600.0, sec))
        except (ValueError, TypeError):
            pass
        try:
            parsed_tuple = email.utils.parsedate_to_datetime(val_str)
            if parsed_tuple:
                now_dt = datetime.now(timezone.utc)
                if parsed_tuple.tzinfo is None:
                    parsed_tuple = parsed_tuple.replace(tzinfo=timezone.utc)
                diff = (parsed_tuple - now_dt).total_seconds()
                if math.isfinite(diff):
                    return max(0.0, min(3600.0, diff))
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

        # SSRF Protection: validate scheme, hostname, IP address, and port
        is_safe, reason = is_safe_url(
            norm_url,
            allow_private_ips=self.allow_private_ips,
            allowed_ports=self.allowed_ports,
        )
        if not is_safe:
            logger.warning(f"SSRF defense blocked request to {norm_url}: {reason}")
            return 0, "", b""

        # Host-level Circuit Breaker guard (atomic check + HALF_OPEN probe reservation)
        cb_allowed = (
            self.circuit_breaker.try_acquire(norm_url)
            if hasattr(self.circuit_breaker, "try_acquire")
            else self.circuit_breaker.is_available(norm_url)
        )
        if not cb_allowed:
            logger.warning(
                f"Circuit breaker is OPEN for {norm_url} (tripped due to repeated 403/429/503 errors). "
                f"Fast-failing request."
            )
            if self.cache_fallback:
                cached = self.get_cached_response(norm_url)
                if cached is not None:
                    logger.warning(
                        f"Circuit breaker OPEN for {norm_url}. Falling back to cached response."
                    )
                    self.last_response_from_cache = True
                    return cached
            return 503, "", b""

        if not hasattr(self.circuit_breaker, "try_acquire"):
            if self.circuit_breaker.get_state(norm_url) == CircuitBreakerState.HALF_OPEN:
                self.circuit_breaker.record_probe(norm_url)

        if self.opener is None:
            logger.error("SafeHttpClient opener is not initialized.")
            return 0, "", b""

        self.last_response_from_cache = False
        self._sleep_with_jitter()

        req_headers = get_random_headers(referer=referer)
        if headers:
            for k, v in headers.items():
                matching_keys = [ek for ek in req_headers if ek.lower() == str(k).lower()]
                for mk in matching_keys:
                    del req_headers[mk]
                req_headers[k] = v

        payload_bytes = None
        if data is not None:
            if isinstance(data, dict):
                payload_bytes = urllib.parse.urlencode(data).encode("utf-8")
                if not any(str(k).lower() == "content-type" for k in req_headers):
                    req_headers["Content-Type"] = "application/x-www-form-urlencoded"
            elif isinstance(data, bytes):
                payload_bytes = data
            elif isinstance(data, str):
                payload_bytes = data.encode("utf-8")

        # Resolve explicit connect and read timeouts
        if connect_timeout is not None:
            eff_connect_timeout = _positive_float(connect_timeout, self._connect_timeout)
        elif isinstance(timeout, (tuple, list)) and len(timeout) >= 2:
            eff_connect_timeout = _positive_float(timeout[0], self._connect_timeout)
        elif isinstance(timeout, (int, float)) and not isinstance(timeout, bool) and math.isfinite(float(timeout)) and float(timeout) > 0:
            eff_connect_timeout = min(5.0, float(timeout))
        else:
            eff_connect_timeout = self._connect_timeout

        if read_timeout is not None:
            eff_read_timeout = _positive_float(read_timeout, self._read_timeout)
        elif isinstance(timeout, (tuple, list)) and len(timeout) >= 2:
            eff_read_timeout = _positive_float(timeout[1], self._read_timeout)
        elif isinstance(timeout, (int, float)) and not isinstance(timeout, bool) and math.isfinite(float(timeout)) and float(timeout) > 0:
            eff_read_timeout = float(timeout)
        else:
            eff_read_timeout = self._read_timeout

        eff_timeout = eff_read_timeout
        try:
            eff_retries = max(1, int(self.max_retries)) if self.max_retries is not None and not isinstance(self.max_retries, bool) else 3
        except (ValueError, TypeError, OverflowError):
            eff_retries = 3

        eff_method = (method or "GET").upper()
        for attempt in range(1, eff_retries + 1):
            if attempt > 1:
                ua_keys = [k for k in req_headers if str(k).lower() == "user-agent"]
                current_ua = req_headers.get(ua_keys[0]) if ua_keys else None
                for k in ua_keys:
                    del req_headers[k]
                req_headers["User-Agent"] = self.get_random_user_agent(exclude=current_ua)
            try:
                req = urllib.request.Request(
                    norm_url,
                    data=payload_bytes,
                    headers=req_headers,
                    method=eff_method,
                )
                req._connect_timeout = eff_connect_timeout
                req._read_timeout = eff_read_timeout
                resp = self.opener.open(req, timeout=eff_timeout)
                try:
                    status_code = resp.getcode()
                    if status_code is None:
                        status_code = getattr(resp, "status", None) or 200

                    if hasattr(resp, "fp") and resp.fp and hasattr(resp.fp, "raw") and hasattr(resp.fp.raw, "_sock"):
                        try:
                            resp.fp.raw._sock.settimeout(eff_read_timeout)
                        except Exception:
                            pass

                    # Bounded stream reading up to max_response_size
                    chunks = []
                    bytes_read = 0
                    start_stream_time = time.time()
                    max_stream_duration = max(30.0, eff_read_timeout * 3.0)
                    while True:
                        if time.time() - start_stream_time > max_stream_duration:
                            logger.warning(
                                f"Response stream from {norm_url} exceeded wall-clock deadline ({max_stream_duration}s). Truncating."
                            )
                            break
                        try:
                            chunk = resp.read(65536)
                        except TypeError:
                            chunk = resp.read()
                        except http.client.IncompleteRead as ire:
                            partial_bytes = ire.partial if isinstance(ire.partial, (bytes, bytearray)) else b""
                            logger.warning(
                                f"IncompleteRead on {norm_url} (Attempt {attempt}/{eff_retries}): "
                                f"{len(partial_bytes)} partial bytes received before disconnect."
                            )
                            if partial_bytes:
                                chunks.append(bytes(partial_bytes))
                                bytes_read += len(partial_bytes)
                            if attempt < eff_retries:
                                raise
                            break
                        if not chunk or not isinstance(chunk, (bytes, bytearray, memoryview, str)):
                            break
                        if isinstance(chunk, str):
                            chunk = chunk.encode("utf-8")
                        elif isinstance(chunk, (bytearray, memoryview)):
                            chunk = bytes(chunk)
                        chunks.append(chunk)
                        bytes_read += len(chunk)
                        if self.max_response_size > 0 and bytes_read >= self.max_response_size:
                            logger.warning(
                                f"Response from {norm_url} exceeded max size ({self.max_response_size} bytes). Truncating."
                            )
                            break
                        if len(chunk) > 65536:
                            break
                    raw_bytes = b"".join(chunks)
                    if self.max_response_size > 0 and len(raw_bytes) > self.max_response_size:
                        raw_bytes = raw_bytes[: self.max_response_size]

                    # Detect charset from response headers (case-insensitive for plain dicts)
                    content_type_hdr = ""
                    if hasattr(resp, "headers") and resp.headers:
                        if hasattr(resp.headers, "get"):
                            content_type_hdr = resp.headers.get("Content-Type", "")
                            if not content_type_hdr and hasattr(resp.headers, "items"):
                                for hk, hv in resp.headers.items():
                                    if str(hk).lower() == "content-type":
                                        content_type_hdr = hv
                                        break
                    content_type = str(content_type_hdr) if content_type_hdr is not None else ""
                    detected_encoding = encoding or self._detect_encoding(content_type, raw_bytes)
                    decoded_text = robust_decode(raw_bytes, declared_encoding=detected_encoding)

                    if 200 <= status_code < 400:
                        self.circuit_breaker.record_success(norm_url)
                        if status_code == 200 and decoded_text:
                            self.set_cached_response(norm_url, status_code, decoded_text, raw_bytes)

                    return status_code, decoded_text, raw_bytes
                finally:
                    if hasattr(resp, "close"):
                        try:
                            resp.close()
                        except Exception:
                            pass
                    if hasattr(resp, "fp") and resp.fp and hasattr(resp.fp, "close"):
                        try:
                            resp.fp.close()
                        except Exception:
                            pass

            except urllib.error.HTTPError as he:
                logger.warning(f"HTTPError {he.code} on {norm_url} (Attempt {attempt}/{eff_retries}): {he.reason}")
                try:
                    if isinstance(getattr(he, "reason", None), str) and he.reason.startswith("SSRF Blocked:"):
                        logger.warning(f"SSRF redirect aborted immediately for {norm_url}: {he.reason}")
                        return 0, "", b""
                    retryable_codes = (408, 429, 403, 500, 502, 503, 504, 520, 521, 522, 523, 524)
                    if he.code in retryable_codes and attempt < eff_retries:
                        if he.code in (403, 429):
                            self.clear_cookies()
                        retry_after = self._parse_retry_after(he) if he.code in (429, 503) else None
                        if retry_after is not None and retry_after > 0:
                            backoff = min(60.0, retry_after)
                        else:
                            backoff = min(60.0, (2 ** attempt) * 2.0 + random.uniform(1.0, 3.0))
                        logger.info(f"Backing off for {backoff:.2f}s before retry (status {he.code})...")
                        time.sleep(backoff)
                    else:
                        retry_after = self._parse_retry_after(he) if he.code in (429, 503) else None
                        if he.code in (403, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524):
                            tripped = self.circuit_breaker.record_failure(
                                norm_url, status_code=he.code, retry_after=retry_after
                            )
                            if tripped:
                                logger.warning(
                                    f"Circuit breaker tripped OPEN for {norm_url} on HTTP {he.code}."
                                )
                        elif self.circuit_breaker.get_state(norm_url) == CircuitBreakerState.HALF_OPEN:
                            self.circuit_breaker.record_success(norm_url)
                        if he.code in (403, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524) and self.cache_fallback:
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
                            if raw_bytes is None:
                                raw_bytes = b""
                            elif isinstance(raw_bytes, str):
                                raw_bytes = raw_bytes.encode("utf-8")
                            elif isinstance(raw_bytes, (bytearray, memoryview)):
                                raw_bytes = bytes(raw_bytes)
                            if self.max_response_size > 0 and len(raw_bytes) > self.max_response_size:
                                raw_bytes = raw_bytes[: self.max_response_size]
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
                logger.warning(f"Request error on {norm_url} (Attempt {attempt}/{eff_retries}): {ex}")
                if attempt < eff_retries:
                    backoff = min(30.0, (2 ** attempt) * 1.5 + random.uniform(0.5, 1.5))
                    time.sleep(backoff)
                else:
                    self.circuit_breaker.record_failure(norm_url)
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

        logger.error(f"Failed to fetch {norm_url} after {eff_retries} attempts.")
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
            encoding=kwargs.get("encoding"),
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
            encoding=kwargs.get("encoding"),
            referer=referer,
            timeout=timeout,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
        )
        return status, text

    @staticmethod
    def _detect_encoding(content_type: str, raw_bytes: bytes) -> str:
        """Detect encoding from Content-Type header or HTML meta tags."""
        match = re.search(r'charset=["\']?([\w\-]+)', content_type or "", re.IGNORECASE)
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


def robust_decode(raw_bytes: Union[bytes, bytearray, memoryview, str, None], declared_encoding: Optional[str] = None) -> str:
    """Decode raw bytes with graceful cascade across Korean/Universal charsets."""
    if raw_bytes is None:
        return ""
    if isinstance(raw_bytes, str):
        return raw_bytes
    if isinstance(raw_bytes, (bytearray, memoryview)):
        raw_bytes = bytes(raw_bytes)
    if not isinstance(raw_bytes, bytes) or not raw_bytes:
        return ""

    norm_declared = None
    if declared_encoding and isinstance(declared_encoding, str):
        norm_declared = declared_encoding.strip().lower()
        if norm_declared in ("x-windows-949", "windows-949", "ms949"):
            norm_declared = "cp949"
        elif norm_declared in ("ks_c_5601-1987", "ksc5601", "euc_kr"):
            norm_declared = "euc-kr"

    if raw_bytes.startswith(b"\xef\xbb\xbf") and (not norm_declared or norm_declared in ("utf-8", "utf8", "utf-8-sig")):
        try:
            return raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            pass

    encodings_to_try: List[Optional[str]] = [norm_declared, "utf-8", "cp949", "euc-kr"]
    if norm_declared in ("latin-1", "latin1", "iso-8859-1", "iso8859-1"):
        encodings_to_try.append("latin-1")

    seen: Set[str] = set()
    for enc in encodings_to_try:
        if not enc or not isinstance(enc, str) or enc in seen:
            continue
        seen.add(enc)
        try:
            return raw_bytes.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue

    fallback_enc = norm_declared if norm_declared in ("cp949", "euc-kr") else "utf-8"
    return raw_bytes.decode(fallback_enc, errors="replace")


def extract_balanced_tag_content(
    html_content: str,
    open_tag_pattern: str,
    tag_name: str = "div",
) -> str:
    """Extract inner HTML of a balanced container tag matched by open_tag_pattern."""
    if not html_content or not isinstance(html_content, str):
        return ""
    m = re.search(open_tag_pattern, html_content, re.IGNORECASE | re.DOTALL)
    if not m:
        return ""
    start = m.end()
    tag_re = re.compile(rf"<(/?){re.escape(tag_name)}\b[^>]*>", re.IGNORECASE)
    depth = 1
    for tm in tag_re.finditer(html_content, start):
        token = tm.group(0)
        if tm.group(1) == "/":
            depth -= 1
            if depth == 0:
                return html_content[start : tm.start()]
        elif not token.rstrip().endswith("/>"):
            depth += 1
    # Unclosed tag fallback: up to first closing tag or end
    close_m = re.search(rf"</{re.escape(tag_name)}\s*>", html_content[start:], re.IGNORECASE)
    if close_m:
        return html_content[start : start + close_m.start()]
    return html_content[start:]


def bounded_cache_set(cache: Dict[str, Any], key: str, value: Any, max_size: int = 500) -> None:
    """Store key/value in an in-memory cache dict with FIFO eviction beyond max_size."""
    if key in cache:
        cache[key] = value
        return
    if max_size > 0 and len(cache) >= max_size:
        try:
            oldest_key = next(iter(cache))
            del cache[oldest_key]
        except StopIteration:
            pass
    cache[key] = value


def encode_euc_kr_query(params: Dict[str, Any]) -> bytes:
    """Encode dictionary into URL-encoded bytes using EUC-KR / CP949 (for Bobae/Pomppu)."""
    if not params or not isinstance(params, dict):
        return b""
    encoded_pairs = []
    for k, v in params.items():
        k_str = urllib.parse.quote(str(k))
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
    temp_path = None
    try:
        abs_output = os.path.abspath(output_path)
        out_dir = os.path.dirname(abs_output)
        os.makedirs(out_dir, exist_ok=True)
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

        temp_fd, temp_path = tempfile.mkstemp(
            dir=out_dir,
            prefix=f".tmp_complaints_{os.getpid()}_{threading.get_ident()}_",
            suffix=".json",
        )
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, abs_output)
        temp_path = None
        logger.info(f"Saved {len(data)} complaint records to {output_path}")
    except Exception as e:
        logger.error(f"Failed to save complaints JSON to {output_path}: {e}")
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
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
