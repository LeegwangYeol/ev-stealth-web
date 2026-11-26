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
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

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


def _non_negative_finite_float(value: Any, default: float = 0.0) -> float:
    """Convert value to a non-negative finite float, or return default."""
    if value is None or isinstance(value, bool):
        return default
    try:
        num = float(value)
    except (ValueError, TypeError):
        return default
    if not math.isfinite(num) or num < 0:
        return default
    return 0.0 if num == 0.0 else num


def safe_non_negative_int(value: Any, default: int = 0) -> int:
    """Convert value (including comma-separated strings) to a non-negative int, rejecting bool/NaN/Inf."""
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        if not math.isfinite(value) or value < 0:
            return default
        return int(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        if not cleaned:
            return default
        try:
            num = float(cleaned)
        except ValueError:
            return default
        if not math.isfinite(num) or num < 0:
            return default
        return int(num)
    return default


def is_allowed_domain_url(url: Optional[str], allowed_domains: Tuple[str, ...]) -> bool:
    """Return True if url is an http/https URL whose host matches one of allowed_domains or their subdomains."""
    if not url or not isinstance(url, str):
        return False
    if any(ord(c) < 32 or ord(c) == 127 for c in url):
        return False
    try:
        parsed = urllib.parse.urlsplit(url.strip())
    except Exception:
        return False
    if (parsed.scheme or "").lower() not in ("http", "https"):
        return False
    if (
        "\\" in (parsed.netloc or "")
        or any(c.isspace() for c in (parsed.netloc or ""))
        or parsed.username is not None
        or parsed.password is not None
    ):
        return False
    try:
        _ = parsed.port
    except ValueError:
        return False
    host = (parsed.hostname or "").lower().strip().rstrip(".")
    if not host:
        return False
    for domain in allowed_domains:
        dom = domain.lower().strip().rstrip(".")
        if not dom:
            continue
        if host == dom or host.endswith(f".{dom}"):
            return True
    return False


def _sanitize_header_text(value: Any) -> str:
    """Strip CR/LF/NUL control characters from HTTP header keys/values."""
    if value is None:
        return ""
    return str(value).replace("\r", "").replace("\n", "").replace("\x00", "")


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
    if not base_url or not isinstance(base_url, str):
        return None
    stripped_raw = raw_url.strip()
    if not stripped_raw or any(ord(c) < 32 or ord(c) == 127 for c in stripped_raw):
        return None
    eff_url = html.unescape(stripped_raw).strip()
    if not eff_url or any(ord(c) < 32 or ord(c) == 127 for c in eff_url):
        return None
    try:
        parsed = urllib.parse.urlsplit(eff_url)
    except Exception:
        return None
    if (
        "\\" in (parsed.netloc or "")
        or any(c.isspace() for c in (parsed.netloc or ""))
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None
    if parsed.scheme and parsed.scheme.lower() not in ("http", "https"):
        return None
    if eff_url.startswith("//"):
        base_scheme = urllib.parse.urlsplit(base_url).scheme or "https"
        candidate = f"{base_scheme}:{eff_url}"
        try:
            cand_parsed = urllib.parse.urlsplit(candidate)
        except Exception:
            return None
        if (
            "\\" in (cand_parsed.netloc or "")
            or any(c.isspace() for c in (cand_parsed.netloc or ""))
            or cand_parsed.username is not None
            or cand_parsed.password is not None
        ):
            return None
        return candidate if cand_parsed.netloc else None
    if eff_url.lower().startswith(("http://", "https://")):
        return eff_url if parsed.netloc else None
    if parsed.scheme:
        # Malformed scheme-relative or schemed URL without '//' (e.g. 'https:evil.com')
        return None
    if eff_url.startswith("/"):
        return urllib.parse.urljoin(base_url, eff_url)
    base_clean = base_url.rstrip("/")
    return f"{base_clean}/{eff_url}"


_NAT64_WELL_KNOWN_PREFIX = ipaddress.IPv6Network("64:ff9b::/96")
_NAT64_LOCAL_PREFIX = ipaddress.IPv6Network("64:ff9b:1::/48")
_CGNAT_PREFIX = ipaddress.IPv4Network("100.64.0.0/10")
_ORCHID_V2_PREFIX = ipaddress.IPv6Network("2001:20::/28")
_SRV6_SID_PREFIX = ipaddress.IPv6Network("5f00::/16")
_IPV4_TRANSLATED_PREFIX = ipaddress.IPv6Network("::ffff:0:0/96")
_IPV4_COMPAT_PREFIX = ipaddress.IPv6Network("::/96")


def is_safe_ip(ip: Union[ipaddress.IPv4Address, ipaddress.IPv6Address]) -> bool:
    """Check if an IP address is publicly routable and safe from SSRF."""
    if getattr(ip, "scope_id", None):
        return False
    if (
        not ip.is_global
        or ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or getattr(ip, "is_site_local", False)
    ):
        return False
    if isinstance(ip, ipaddress.IPv4Address):
        if ip in _CGNAT_PREFIX:
            return False
    if isinstance(ip, ipaddress.IPv6Address):
        if ip in _ORCHID_V2_PREFIX or ip in _SRV6_SID_PREFIX:
            return False
        if ip.ipv4_mapped and not is_safe_ip(ip.ipv4_mapped):
            return False
        if ip.sixtofour and not is_safe_ip(ip.sixtofour):
            return False
        if ip.teredo:
            for teredo_ip in ip.teredo:
                if not is_safe_ip(teredo_ip):
                    return False
        if (
            ip in _NAT64_WELL_KNOWN_PREFIX
            or ip in _NAT64_LOCAL_PREFIX
            or ip in _IPV4_TRANSLATED_PREFIX
            or ip in _IPV4_COMPAT_PREFIX
            or ((int(ip) >> 32) & 0xFFFFFFFF) in (0x00005EFE, 0x02005EFE)
        ):
            embedded_v4 = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
            if not is_safe_ip(embedded_v4):
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

    if "\\" in (parsed.netloc or ""):
        return False, "SSRF blocked: Invalid backslash in URL authority"
    if any(c.isspace() for c in (parsed.netloc or "")):
        return False, "SSRF blocked: Invalid whitespace in URL authority"
    if parsed.username is not None or parsed.password is not None:
        return False, "SSRF blocked: URL authority userinfo (@) not allowed"

    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        return False, f"Disallowed URL scheme: {scheme!r} (only http/https allowed)"

    hostname = parsed.hostname
    if not hostname:
        return False, "Missing hostname in URL"

    host_lower = hostname.lower().strip().rstrip(".")
    if not host_lower:
        return False, "Missing hostname in URL"

    try:
        explicit_port = parsed.port
    except ValueError:
        return False, "SSRF blocked: Invalid port in URL"

    if allowed_ports is not None:
        eff_port = explicit_port if explicit_port is not None else (443 if scheme == "https" else 80)
        if eff_port not in allowed_ports:
            return False, f"SSRF blocked: Disallowed port {eff_port}"

    if allow_private_ips:
        return True, "Private IPs allowed by configuration"

    if "%" in host_lower:
        return False, "SSRF blocked: IPv6 zone ID not allowed"

    # Normalize IDNA/Unicode hostnames (e.g., fullwidth digits '１２７.０.０.１' or 'ⓛⓞⓒⓐⓛⓗⓞⓢⓣ')
    # so host and IP literal checks catch homograph/NFKC bypasses even without DNS.
    host_candidates = [host_lower]
    if not host_lower.isascii():
        try:
            idna_host = host_lower.encode("idna").decode("ascii").lower().strip().rstrip(".")
            if idna_host and idna_host not in host_candidates:
                host_candidates.append(idna_host)
        except UnicodeError:
            return False, f"SSRF blocked: Invalid internationalized hostname '{host_lower}'"

    for cand in host_candidates:
        if cand in DISALLOWED_HOSTS:
            return False, f"SSRF blocked: Disallowed hostname '{cand}'"
        for suffix in DISALLOWED_HOST_SUFFIXES:
            if cand.endswith(suffix):
                return False, f"SSRF blocked: Hostname '{cand}' matches disallowed internal suffix '{suffix}'"

    ports_set = allowed_ports if allowed_ports is not None else STANDARD_SAFE_PORTS
    if explicit_port is not None and explicit_port not in ports_set:
        return False, f"SSRF blocked: Disallowed port {explicit_port}"

    for cand in host_candidates:
        try:
            ip = ipaddress.ip_address(cand)
            if not is_safe_ip(ip):
                return False, f"SSRF blocked: Unsafe IP address {ip}"
            return True, "Safe public IP"
        except ValueError:
            pass

        try:
            packed = socket.inet_aton(cand)
            ip4 = ipaddress.IPv4Address(packed)
            if not is_safe_ip(ip4):
                return False, f"SSRF blocked: Unsafe encoded IP address {ip4}"
            return True, "Safe public IP"
        except (OSError, ValueError):
            pass

    dns_host = host_candidates[-1]
    try:
        addr_info = socket.getaddrinfo(dns_host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        if addr_info:
            for family, socktype, proto, canonname, sockaddr in addr_info:
                if isinstance(sockaddr, tuple) and len(sockaddr) >= 4 and sockaddr[3]:
                    return False, f"SSRF blocked: Domain '{host_lower}' resolved to scoped IPv6 address"
                ip_str = sockaddr[0]
                try:
                    resolved_ip = ipaddress.ip_address(ip_str)
                except ValueError:
                    return False, f"SSRF blocked: Domain '{host_lower}' resolved to invalid IP {ip_str!r}"
                if not is_safe_ip(resolved_ip):
                    return False, f"SSRF blocked: Domain '{host_lower}' resolves to unsafe IP {resolved_ip}"
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
        "User-Agent": random.choice(USER_AGENT_POOL) if USER_AGENT_POOL else DEFAULT_FALLBACK_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Upgrade-Insecure-Requests": "1"
    }
    if referer and isinstance(referer, str):
        safe_ref = _sanitize_header_text(referer).strip()
        if safe_ref:
            headers["Referer"] = safe_ref
    return headers


def polite_delay(min_delay: float = 1.5, max_delay: float = 3.5):
    """Enforce polite sleep with randomized jitter between requests."""
    a = _non_negative_finite_float(min_delay, 0.0)
    b = _non_negative_finite_float(max_delay, 0.0)
    low, high = min(a, b), max(a, b)
    if high <= 0:
        return
    sleep_time = random.uniform(low, high)
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
        if not self.raw_quote or not isinstance(self.raw_quote, str) or len(self.raw_quote.strip()) < 5:
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


def _create_safe_connection(
    address: Tuple[str, int],
    timeout: float,
    source_address: Optional[Tuple[str, int]] = None,
    allow_private_ips: bool = True,
) -> socket.socket:
    """Create TCP socket with optional SSRF IP validation on resolved addresses."""
    if allow_private_ips:
        return socket.create_connection(address, timeout, source_address)
    host, port = address
    addr_list = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
    for _, _, _, _, sockaddr in addr_list:
        if isinstance(sockaddr, tuple) and len(sockaddr) >= 4 and sockaddr[3]:
            raise OSError(f"SSRF blocked: Domain '{host}' resolved to scoped IPv6 address")
        ip_str = sockaddr[0]
        try:
            resolved_ip = ipaddress.ip_address(ip_str)
        except ValueError as exc:
            raise OSError(f"SSRF blocked: Invalid resolved IP {ip_str!r}") from exc
        if not is_safe_ip(resolved_ip):
            raise OSError(f"SSRF blocked: Domain '{host}' resolved to unsafe IP {resolved_ip}")
    err: Optional[OSError] = None
    for af, socktype, proto, _, sa in addr_list:
        sock: Optional[socket.socket] = None
        try:
            sock = socket.socket(af, socktype, proto)
            if timeout is not None:
                sock.settimeout(timeout)
            if source_address:
                sock.bind(source_address)
            sock.connect(sa)
            return sock
        except OSError as exc:
            err = exc
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass
        except Exception:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass
            raise
    if err is not None:
        raise err
    raise OSError(f"getaddrinfo returns an empty list for {host}:{port}")


class ResilientHTTPConnection(http.client.HTTPConnection):
    """HTTPConnection supporting explicit separate connect and read timeouts."""

    def __init__(
        self,
        *args,
        connect_timeout: float = 5.0,
        read_timeout: float = 15.0,
        allow_private_ips: bool = True,
        **kwargs,
    ):
        self._conn_timeout = _positive_float(connect_timeout, 5.0)
        self._read_timeout = _positive_float(read_timeout, 15.0)
        self._allow_private_ips = bool(allow_private_ips)
        super().__init__(*args, **kwargs)

    def connect(self):
        self.sock = _create_safe_connection(
            (self.host, self.port),
            self._conn_timeout,
            self.source_address,
            allow_private_ips=self._allow_private_ips,
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

    def __init__(
        self,
        *args,
        connect_timeout: float = 5.0,
        read_timeout: float = 15.0,
        allow_private_ips: bool = True,
        allowed_ports: Optional[Set[int]] = None,
        **kwargs,
    ):
        self._conn_timeout = _positive_float(connect_timeout, 5.0)
        self._read_timeout = _positive_float(read_timeout, 15.0)
        self._allow_private_ips = bool(allow_private_ips)
        self._allowed_ports = set(allowed_ports) if allowed_ports is not None else None
        super().__init__(*args, **kwargs)

    def connect(self):
        if self._tunnel_host and not self._allow_private_ips:
            tunnel_host = (
                f"[{self._tunnel_host}]"
                if ":" in str(self._tunnel_host) and not str(self._tunnel_host).startswith("[")
                else str(self._tunnel_host)
            )
            tunnel_port = getattr(self, "_tunnel_port", None)
            tunnel_url = f"https://{tunnel_host}:{tunnel_port}" if tunnel_port is not None else f"https://{tunnel_host}"
            is_safe, reason = is_safe_url(
                tunnel_url,
                allow_private_ips=self._allow_private_ips,
                allowed_ports=self._allowed_ports,
            )
            if not is_safe:
                raise OSError(f"SSRF blocked: Unsafe tunnel host '{self._tunnel_host}' ({reason})")
        self.sock = _create_safe_connection(
            (self.host, self.port),
            self._conn_timeout,
            self.source_address,
            allow_private_ips=self._allow_private_ips,
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
        target_url = str(newurl or "").strip()
        if target_url and not target_url.lower().startswith(("http://", "https://")):
            if not urllib.parse.urlsplit(target_url).scheme:
                target_url = urllib.parse.urljoin(req.full_url, target_url)
        is_safe, reason = is_safe_url(
            target_url,
            allow_private_ips=self.allow_private_ips,
            allowed_ports=self.allowed_ports,
        )
        if not is_safe:
            logger.warning(f"SSRF defense blocked redirect from {req.full_url} to {newurl}: {reason}")
            raise urllib.error.HTTPError(
                target_url or newurl, 403, f"SSRF Blocked: Unsafe redirect target ({reason})", headers, fp
            )
        new_req = super().redirect_request(req, fp, code, msg, headers, target_url)
        if new_req is not None:
            orig_parsed = urllib.parse.urlsplit(req.full_url)
            new_parsed = urllib.parse.urlsplit(new_req.full_url)
            orig_port = orig_parsed.port or (443 if (orig_parsed.scheme or "").lower() == "https" else 80)
            new_port = new_parsed.port or (443 if (new_parsed.scheme or "").lower() == "https" else 80)
            if (
                (orig_parsed.scheme or "").lower() != (new_parsed.scheme or "").lower()
                or (orig_parsed.hostname or "").lower() != (new_parsed.hostname or "").lower()
                or orig_port != new_port
            ):
                for hdr_name in ("Authorization", "Proxy-Authorization", "Cookie"):
                    new_req.remove_header(hdr_name)
                    for existing_key in list(new_req.unredirected_hdrs.keys()):
                        if existing_key.lower() == hdr_name.lower():
                            del new_req.unredirected_hdrs[existing_key]
            if hasattr(req, "_connect_timeout"):
                new_req._connect_timeout = req._connect_timeout
            if hasattr(req, "_read_timeout"):
                new_req._read_timeout = req._read_timeout
        return new_req


class ResilientHTTPHandler(urllib.request.HTTPHandler):
    """HTTP handler injecting ResilientHTTPConnection with explicit timeouts."""

    def __init__(
        self,
        connect_timeout: float = 5.0,
        read_timeout: float = 15.0,
        allow_private_ips: bool = True,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._connect_timeout = _positive_float(connect_timeout, 5.0)
        self._read_timeout = _positive_float(read_timeout, 15.0)
        self._allow_private_ips = bool(allow_private_ips)

    def http_open(self, req):
        conn_to = getattr(req, "_connect_timeout", self._connect_timeout)
        read_to = getattr(req, "_read_timeout", self._read_timeout)
        allow_priv = self._allow_private_ips

        def _factory(host, **kwargs):
            return ResilientHTTPConnection(
                host,
                connect_timeout=conn_to,
                read_timeout=read_to,
                allow_private_ips=allow_priv,
                **kwargs,
            )
        return self.do_open(_factory, req)


class ResilientHTTPSHandler(urllib.request.HTTPSHandler):
    """HTTPS handler injecting ResilientHTTPSConnection with explicit timeouts."""

    def __init__(
        self,
        connect_timeout: float = 5.0,
        read_timeout: float = 15.0,
        context=None,
        allow_private_ips: bool = True,
        allowed_ports: Optional[Set[int]] = None,
        **kwargs,
    ):
        super().__init__(context=context, **kwargs)
        self._connect_timeout = _positive_float(connect_timeout, 5.0)
        self._read_timeout = _positive_float(read_timeout, 15.0)
        self._allow_private_ips = bool(allow_private_ips)
        self._allowed_ports = set(allowed_ports) if allowed_ports is not None else None

    def https_open(self, req):
        conn_to = getattr(req, "_connect_timeout", self._connect_timeout)
        read_to = getattr(req, "_read_timeout", self._read_timeout)
        allow_priv = self._allow_private_ips
        allowed_ports = self._allowed_ports

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
                allow_private_ips=allow_priv,
                allowed_ports=allowed_ports,
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
        max_hosts: int = 1000,
    ):
        try:
            ft = int(failure_threshold) if failure_threshold is not None and not isinstance(failure_threshold, bool) else 3
        except (ValueError, TypeError, OverflowError):
            ft = 3
        self.failure_threshold = max(1, ft)
        self.cooldown_seconds = max(0.01, _positive_float(cooldown_seconds, 30.0))
        try:
            hp = int(half_open_max_probes) if half_open_max_probes is not None and not isinstance(half_open_max_probes, bool) else 1
        except (ValueError, TypeError, OverflowError):
            hp = 1
        self.half_open_max_probes = max(1, hp)
        try:
            mh = int(max_hosts) if max_hosts is not None and not isinstance(max_hosts, bool) else 1000
        except (ValueError, TypeError, OverflowError):
            mh = 1000
        self.max_hosts = max(1, mh)
        self._lock = threading.Lock()
        self._hosts: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()

    def _normalize_host(self, raw_host: str) -> str:
        host = raw_host.lower().strip().rstrip(".")
        if host and not host.isascii():
            try:
                host = host.encode("idna").decode("ascii").lower().strip().rstrip(".")
            except UnicodeError:
                pass
        return host

    def _extract_host(self, url_or_host: str) -> str:
        if not url_or_host:
            return ""
        s = str(url_or_host).strip()
        if "://" in s:
            try:
                parsed = urllib.parse.urlsplit(s)
                if parsed.hostname:
                    return self._normalize_host(parsed.hostname)
            except Exception:
                pass
        try:
            ip = ipaddress.ip_address(s.split("%")[0])
            return str(ip).lower()
        except ValueError:
            pass
        try:
            parsed = urllib.parse.urlsplit("//" + s)
            if parsed.hostname:
                return self._normalize_host(parsed.hostname)
        except Exception:
            pass
        return self._normalize_host(s.split(":")[0].split("/")[0])

    def _evict_if_full(self) -> None:
        while len(self._hosts) >= self.max_hosts:
            victim = None
            for k, v in self._hosts.items():
                if v.get("state") == CircuitBreakerState.CLOSED:
                    victim = k
                    break
            if victim is None:
                self._hosts.popitem(last=False)
            else:
                del self._hosts[victim]

    def record_probe(self, url_or_host: str) -> None:
        """Record that a canary probe is in-flight for this host during HALF_OPEN state."""
        host = self._extract_host(url_or_host)
        if not host:
            return
        with self._lock:
            info = self._hosts.get(host)
            if info and info.get("state") == CircuitBreakerState.HALF_OPEN:
                info["probe_count"] = info.get("probe_count", 0) + 1

    def release_probe(self, url_or_host: str) -> None:
        """Release an unused or aborted HALF_OPEN canary probe slot."""
        host = self._extract_host(url_or_host)
        if not host:
            return
        with self._lock:
            info = self._hosts.get(host)
            if info and info.get("state") == CircuitBreakerState.HALF_OPEN:
                info["probe_count"] = max(0, info.get("probe_count", 0) - 1)

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
                self._evict_if_full()
                self._hosts[host] = {
                    "state": CircuitBreakerState.CLOSED,
                    "failure_count": 0,
                    "tripped_until": 0.0,
                    "probe_count": 0,
                }
            else:
                self._hosts.move_to_end(host)
            info = self._hosts[host]
            info["failure_count"] = info.get("failure_count", 0) + 1
            tripped = False

            cooldown = self.cooldown_seconds
            if retry_after is not None and not isinstance(retry_after, bool):
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
                info["probe_count"] = 0
                tripped = True
            elif info["failure_count"] >= self.failure_threshold:
                info["state"] = CircuitBreakerState.OPEN
                info["tripped_until"] = now + cooldown
                info["probe_count"] = 0
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
        try:
            mrs = (
                int(max_response_size)
                if max_response_size is not None and not isinstance(max_response_size, bool)
                else MAX_RESPONSE_BYTES
            )
        except (ValueError, TypeError, OverflowError):
            mrs = MAX_RESPONSE_BYTES
        self.max_response_size = max(0, mrs)
        try:
            mc = (
                int(max_cookies)
                if max_cookies is not None and not isinstance(max_cookies, bool)
                else MAX_COOKIEJAR_ENTRIES
            )
        except (ValueError, TypeError, OverflowError):
            mc = MAX_COOKIEJAR_ENTRIES
        self.max_cookies = max(0, mc)
        self.enable_cache = enable_cache
        self.cache_fallback = cache_fallback
        self.allow_private_ips = bool(allow_private_ips)
        self.allowed_ports = set(allowed_ports) if allowed_ports is not None else None
        self.request_count = 0
        self.last_request_time = 0.0
        self.last_response_from_cache = False
        self._memory_cache: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
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
                allow_private_ips=self.allow_private_ips,
            )
            https_handler = ResilientHTTPSHandler(
                connect_timeout=self._connect_timeout,
                read_timeout=self._read_timeout,
                allow_private_ips=self.allow_private_ips,
                allowed_ports=self.allowed_ports,
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
        return hashlib.sha256(norm.encode("utf-8", errors="replace")).hexdigest()

    def get_cached_response(self, url: str) -> Optional[Tuple[int, str, bytes]]:
        """Retrieve cached (status_code, decoded_text, raw_bytes) if present."""
        if not self.enable_cache or not url:
            return None
        key = self._cache_key(url)
        with self._cache_lock:
            if key in self._memory_cache:
                entry = self._memory_cache[key]
                self._memory_cache.move_to_end(key)
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
                        self._memory_cache.move_to_end(key)
                        while len(self._memory_cache) > 500:
                            self._memory_cache.popitem(last=False)
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
        now_ts = time.time()
        raw_copy = bytes(raw_bytes)
        entry = {
            "status": int(status_code),
            "text": str(decoded_text),
            "raw": raw_copy,
            "time": now_ts,
            "url": str(url),
        }
        with self._cache_lock:
            self._memory_cache[key] = entry
            self._memory_cache.move_to_end(key)
            while len(self._memory_cache) > 500:
                self._memory_cache.popitem(last=False)

        if self.cache_dir:
            temp_path = None
            try:
                os.makedirs(self.cache_dir, exist_ok=True)
                file_path = os.path.join(self.cache_dir, f"{key}.json")
                payload = {
                    "url": str(url),
                    "status": int(status_code),
                    "text": str(decoded_text),
                    "raw_hex": raw_copy.hex(),
                    "time": now_ts,
                }
                temp_fd, temp_path = tempfile.mkstemp(
                    dir=self.cache_dir,
                    prefix=f".tmp_cache_{os.getpid()}_{threading.get_ident()}_{uuid.uuid4().hex[:8]}_",
                    suffix=".json",
                )
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
        cookie_jar = getattr(self, "cookie_jar", None)
        if cookie_jar is not None and hasattr(cookie_jar, "clear"):
            try:
                cookie_jar.clear()
            except Exception:
                self.cookie_jar = http.cookiejar.CookieJar()
        else:
            self.cookie_jar = http.cookiejar.CookieJar()

    def get_cookie_dict(self) -> Dict[str, str]:
        """Return all cookies stored in the session cookie jar as a dictionary."""
        cookie_dict: Dict[str, str] = {}
        cookie_jar = getattr(self, "cookie_jar", None)
        if cookie_jar is not None:
            try:
                for c in cookie_jar:
                    if hasattr(c, "name") and hasattr(c, "value"):
                        cookie_dict[c.name] = c.value
            except Exception:
                pass
        return cookie_dict

    def close(self) -> None:
        """Release HTTP client session resources, cookie jar, and connection handlers."""
        self.clear_cookies()
        opener = getattr(self, "opener", None)
        if opener is None:
            return
        if hasattr(opener, "close"):
            try:
                opener.close()
            except Exception:
                pass
        if hasattr(opener, "handlers"):
            for h in getattr(opener, "handlers", []):
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

        if isinstance(self.min_delay, bool) or isinstance(self.max_delay, bool):
            raw_min, raw_max = 0.0, 0.0
        else:
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
            elapsed = max(0.0, now - self.last_request_time)
            req_num = self.request_count
            self.request_count += 1

        # Cooldown trigger (every cooldown_interval requests)
        try:
            ci_val = (
                int(self.cooldown_interval)
                if self.cooldown_interval is not None and not isinstance(self.cooldown_interval, bool)
                else 0
            )
        except (ValueError, TypeError, OverflowError):
            ci_val = 0
        if ci_val > 0 and req_num > 0 and req_num % ci_val == 0:
            try:
                ct = float(self.cooldown_time) if not isinstance(self.cooldown_time, bool) else 6.0
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
        cb_allowed = (
            self.circuit_breaker.try_acquire(norm_url)
            if hasattr(self.circuit_breaker, "try_acquire")
            else self.circuit_breaker.is_available(norm_url)
        )
        if not cb_allowed:
            logger.warning(f"Circuit breaker OPEN for {norm_url}; skipping session warm-up.")
            return False
        if not hasattr(self.circuit_breaker, "try_acquire"):
            if self.circuit_breaker.get_state(norm_url) == CircuitBreakerState.HALF_OPEN:
                self.circuit_breaker.record_probe(norm_url)
        if self.opener is None:
            if hasattr(self.circuit_breaker, "release_probe"):
                self.circuit_breaker.release_probe(norm_url)
            logger.error("SafeHttpClient opener is not initialized.")
            return False
        logger.info(f"Warming up session on base domain: {norm_url}")
        resp = None
        cb_resolved = False
        try:
            headers = get_random_headers(referer=referer)
            req = urllib.request.Request(norm_url, headers=headers)
            req._connect_timeout = self._connect_timeout
            req._read_timeout = self._read_timeout
            resp = self.opener.open(req, timeout=self._read_timeout)
            try:
                _ = resp.read(1024)
            except TypeError:
                _ = resp.read()
            self.circuit_breaker.record_success(norm_url)
            cb_resolved = True
            logger.info(f"Session warmed up successfully on {norm_url}. Cookies in jar: {len(self.cookie_jar)}")
            return True
        except urllib.error.HTTPError as he:
            logger.warning(f"Session warm-up HTTP {he.code} on {norm_url}: {he.reason}")
            if isinstance(getattr(he, "reason", None), str) and he.reason.startswith("SSRF Blocked:"):
                pass
            elif he.code in (403, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524):
                retry_after = self._parse_retry_after(he) if he.code in (429, 503) else None
                self.circuit_breaker.record_failure(norm_url, status_code=he.code, retry_after=retry_after)
                cb_resolved = True
            elif self.circuit_breaker.get_state(norm_url) == CircuitBreakerState.HALF_OPEN:
                self.circuit_breaker.record_success(norm_url)
                cb_resolved = True
            try:
                if hasattr(he, "fp") and he.fp:
                    he.fp.close()
                he.close()
            except Exception:
                pass
            return False
        except Exception as e:
            logger.warning(f"Session warm-up encountered notice on {norm_url}: {e}")
            self.circuit_breaker.record_failure(norm_url)
            cb_resolved = True
            return False
        finally:
            if not cb_resolved and hasattr(self.circuit_breaker, "release_probe"):
                self.circuit_breaker.release_probe(norm_url)
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
    def _get_header_ci(headers: Any, name: str) -> str:
        """Retrieve a header value case-insensitively across HTTPMessage and plain dicts."""
        if not headers:
            return ""
        val = None
        if hasattr(headers, "get"):
            val = headers.get(name)
            if val is None:
                val = headers.get(name.lower())
        if val is None and hasattr(headers, "items"):
            target = name.lower()
            for hk, hv in headers.items():
                if str(hk).lower() == target:
                    val = hv
                    break
        return str(val) if val is not None else ""

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
        self.last_response_from_cache = False
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

        if self.opener is None:
            logger.error("SafeHttpClient opener is not initialized.")
            return 0, "", b""

        eff_method = (method or "GET").upper()
        is_cacheable_method = eff_method in ("GET", "HEAD")

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
            if self.cache_fallback and is_cacheable_method:
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

        cb_resolved = False
        try:
            self.last_response_from_cache = False
            self._sleep_with_jitter()

            req_headers = get_random_headers(referer=referer)
            if headers:
                for k, v in headers.items():
                    if k is None or v is None:
                        continue
                    safe_k = _sanitize_header_text(k).strip()
                    if not safe_k:
                        continue
                    safe_v = _sanitize_header_text(v)
                    matching_keys = [ek for ek in req_headers if ek.lower() == safe_k.lower()]
                    for mk in matching_keys:
                        del req_headers[mk]
                    req_headers[safe_k] = safe_v

            payload_bytes = None
            if data is not None:
                if isinstance(data, dict):
                    payload_bytes = urllib.parse.urlencode(data).encode("utf-8")
                    if not any(str(k).lower() == "content-type" for k in req_headers):
                        req_headers["Content-Type"] = "application/x-www-form-urlencoded"
                elif isinstance(data, bytes):
                    payload_bytes = data
                elif isinstance(data, str):
                    payload_bytes = data.encode("utf-8", errors="replace")

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
                        stream_truncated = False
                        start_stream_time = time.time()
                        max_stream_duration = max(30.0, eff_read_timeout * 3.0)
                        while True:
                            if time.time() - start_stream_time > max_stream_duration:
                                logger.warning(
                                    f"Response stream from {norm_url} exceeded wall-clock deadline ({max_stream_duration}s). Truncating."
                                )
                                stream_truncated = True
                                break
                            single_read = False
                            try:
                                chunk = resp.read(65536)
                            except TypeError:
                                chunk = resp.read()
                                single_read = True
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
                                stream_truncated = True
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
                                stream_truncated = True
                                break
                            if single_read or len(chunk) > 65536:
                                break
                        raw_bytes = b"".join(chunks)
                        if self.max_response_size > 0 and len(raw_bytes) > self.max_response_size:
                            raw_bytes = raw_bytes[: self.max_response_size]

                        # Detect charset from response headers (case-insensitive for plain dicts)
                        content_type = self._get_header_ci(getattr(resp, "headers", None), "Content-Type")
                        detected_encoding = encoding or self._detect_encoding(content_type, raw_bytes)
                        decoded_text = robust_decode(raw_bytes, declared_encoding=detected_encoding)

                        if 200 <= status_code < 400:
                            self.circuit_breaker.record_success(norm_url)
                            cb_resolved = True
                            if is_cacheable_method and status_code == 200 and decoded_text and not stream_truncated:
                                self.set_cached_response(norm_url, status_code, decoded_text, raw_bytes)
                        elif status_code in (403, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524):
                            self.circuit_breaker.record_failure(norm_url, status_code=status_code)
                            cb_resolved = True
                        elif self.circuit_breaker.get_state(norm_url) == CircuitBreakerState.HALF_OPEN:
                            self.circuit_breaker.record_success(norm_url)
                            cb_resolved = True

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
                            try:
                                if hasattr(he, "fp") and he.fp:
                                    he.fp.close()
                                he.close()
                            except Exception:
                                pass
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
                                cb_resolved = True
                                if tripped:
                                    logger.warning(
                                        f"Circuit breaker tripped OPEN for {norm_url} on HTTP {he.code}."
                                    )
                            elif self.circuit_breaker.get_state(norm_url) == CircuitBreakerState.HALF_OPEN:
                                self.circuit_breaker.record_success(norm_url)
                                cb_resolved = True
                            if is_cacheable_method and he.code in (403, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524) and self.cache_fallback:
                                cached = self.get_cached_response(norm_url)
                                if cached is not None:
                                    logger.warning(
                                        f"Remote endpoint {norm_url} returned HTTP {he.code}. Falling back to cached response."
                                    )
                                    self.last_response_from_cache = True
                                    return cached
                            try:
                                read_limit = self.max_response_size if self.max_response_size > 0 else 65536
                                try:
                                    raw_bytes = he.read(read_limit)
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
                                err_ct = self._get_header_ci(getattr(he, "headers", None), "Content-Type")
                                err_enc = encoding or self._detect_encoding(err_ct, raw_bytes)
                                decoded_text = robust_decode(raw_bytes, declared_encoding=err_enc)
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
                        cb_resolved = True
                        if self.cache_fallback and is_cacheable_method:
                            cached = self.get_cached_response(norm_url)
                            if cached is not None:
                                logger.warning(
                                    f"Remote endpoint {norm_url} unreachable ({ex}). Falling back to cached response."
                                )
                                self.last_response_from_cache = True
                                return cached
                        break

            if self.cache_fallback and is_cacheable_method:
                cached = self.get_cached_response(norm_url)
                if cached is not None:
                    logger.warning(
                        f"Remote endpoint {norm_url} unreachable. Falling back to cached response."
                    )
                    self.last_response_from_cache = True
                    return cached

            logger.error(f"Failed to fetch {norm_url} after {eff_retries} attempts.")
            return 0, "", b""
        finally:
            if not cb_resolved and hasattr(self.circuit_breaker, "release_probe"):
                self.circuit_breaker.release_probe(norm_url)

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
        match = re.search(r'charset\s*=\s*["\']?([\w\-]+)', content_type or "", re.IGNORECASE)
        if match:
            return match.group(1).strip().lower()

        if not raw_bytes:
            return "utf-8"

        # Check HTML meta charset in initial bytes (ignoring HTML comments and scripts/styles)
        head_bytes = bytes(raw_bytes[:16384]) if isinstance(raw_bytes, (bytearray, memoryview)) else raw_bytes[:16384]
        prefix = _RE_COMMENT_OR_SCRIPT_STYLE.sub(" ", head_bytes.decode("ascii", "ignore"))
        meta_match = re.search(r'<meta\b[^>]*\bcharset\s*=\s*["\']?([\w\-]+)', prefix, re.IGNORECASE)
        if meta_match:
            return meta_match.group(1).strip().lower()

        meta_http = re.search(r'<meta\b[^>]*\bhttp-equiv\s*=\s*["\']?content-type["\']?[^>]*\bcontent\s*=\s*["\'][^"\']*charset=([\w\-]+)', prefix, re.IGNORECASE)
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
        if norm_declared in ("x-windows-949", "windows-949", "ms949", "ms-949", "cp-949"):
            norm_declared = "cp949"
        elif norm_declared in ("ks_c_5601-1987", "ks_c_5601", "ksc5601", "ksc_5601-1987", "euc_kr", "euckr", "x-euc-kr"):
            norm_declared = "euc-kr"
        elif norm_declared in ("utf8", "utf_8"):
            norm_declared = "utf-8"

    has_utf8_bom = raw_bytes.startswith(b"\xef\xbb\xbf")
    if has_utf8_bom:
        try:
            return raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            if not norm_declared or norm_declared == "utf-8":
                return raw_bytes.decode("utf-8-sig", errors="replace")
    if raw_bytes.startswith((b"\xff\xfe", b"\xfe\xff")) and (not norm_declared or norm_declared.startswith("utf-16")):
        try:
            return raw_bytes.decode("utf-16")
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
        except UnicodeDecodeError as ude:
            if (
                enc == "utf-8"
                and norm_declared == "utf-8"
                and ude.reason == "unexpected end of data"
                and ude.end == len(raw_bytes)
                and ude.start >= max(0, len(raw_bytes) - 3)
            ):
                return raw_bytes.decode("utf-8", errors="replace")
            continue
        except LookupError:
            continue

    if has_utf8_bom:
        return raw_bytes.decode("utf-8-sig", errors="replace")
    fallback_enc = "cp949" if norm_declared in ("cp949", "euc-kr") else "utf-8"
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
    if m.group(0).rstrip().endswith("/>"):
        return ""
    start = m.end()
    esc_tag = re.escape(tag_name)
    token_re = re.compile(
        rf"<!--.*?-->|<(script|style)\b[^>]*>.*?</\1\s*>|<(/?){esc_tag}\b[^>]*>",
        re.IGNORECASE | re.DOTALL,
    )
    depth = 1
    for tm in token_re.finditer(html_content, start):
        close_slash = tm.group(2)
        if close_slash is None:
            continue
        token = tm.group(0)
        if close_slash == "/":
            depth -= 1
            if depth == 0:
                return html_content[start : tm.start()]
        elif not token.rstrip().endswith("/>"):
            depth += 1
    # Unclosed tag fallback: up to first closing tag or end
    close_m = re.search(rf"</{esc_tag}\s*>", html_content[start:], re.IGNORECASE)
    if close_m:
        return html_content[start : start + close_m.start()]
    return html_content[start:]


def bounded_cache_set(cache: Dict[str, Any], key: str, value: Any, max_size: int = 500) -> None:
    """Store key/value in an in-memory cache dict with FIFO eviction beyond max_size."""
    if max_size <= 0:
        return
    if key in cache:
        cache[key] = value
        return
    while len(cache) >= max_size:
        try:
            oldest_key = next(iter(cache))
            del cache[oldest_key]
        except StopIteration:
            break
    cache[key] = value


def encode_euc_kr_query(params: Dict[str, Any]) -> bytes:
    """Encode dictionary into URL-encoded bytes using EUC-KR / CP949 (for Bobae/Pomppu)."""
    if not params or not isinstance(params, dict):
        return b""
    encoded_pairs = []
    for k, v in params.items():
        k_str = urllib.parse.quote(str(k), safe="")
        v_str = str(v)
        try:
            v_encoded = urllib.parse.quote(v_str.encode("euc-kr"), safe="")
        except UnicodeEncodeError:
            v_encoded = urllib.parse.quote(v_str.encode("cp949", errors="replace"), safe="")
        encoded_pairs.append(f"{k_str}={v_encoded}")
    return "&".join(encoded_pairs).encode("ascii")


_RE_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_RE_SCRIPT_STYLE = re.compile(
    r"<(script|style)\b[^>]*>(?:.*?</\1\s*>|.*$)", re.DOTALL | re.IGNORECASE
)
_RE_COMMENT_OR_SCRIPT_STYLE = re.compile(
    r"<!--.*?-->|<(script|style)\b[^>]*>(?:.*?</\1\s*>|.*$)", re.DOTALL | re.IGNORECASE
)
_RE_HEAD_BLOCK = re.compile(r"<head\b[^>]*>.*?</head>", re.DOTALL | re.IGNORECASE)
_RE_BLOCK_TAGS = re.compile(
    r'''<(br|p|/p|div|/div|li|/li|h\d|/h\d|tr|/tr|dt|/dt|dd|/dd)\b(?:[^>"']|"[^"]{0,2000}"|'[^']{0,2000}')*>''',
    re.IGNORECASE,
)
_RE_ANY_TAG = re.compile(r'''</?[a-zA-Z!?](?:[^>"']|"[^"]{0,2000}"|'[^']{0,2000}')*>''')
_RE_TRAILING_TAG = re.compile(r"<[a-zA-Z/][^<]*$")
_RE_HORIZONTAL_WS = re.compile(r"[ \t]+")


def clean_html_text(raw_html: Union[str, bytes, bytearray, memoryview, Any]) -> str:
    """Remove HTML tags, script/style blocks, decode entities, and normalize whitespace."""
    if raw_html is None:
        return ""
    if isinstance(raw_html, (bytes, bytearray, memoryview)):
        raw_html = robust_decode(raw_html)
    elif not isinstance(raw_html, str):
        return ""
    if not raw_html:
        return ""

    cleaned = raw_html.replace("\x00", " ")
    cleaned = _RE_COMMENT_OR_SCRIPT_STYLE.sub(" ", cleaned)
    cleaned = _RE_BLOCK_TAGS.sub("\n", cleaned)
    cleaned = _RE_ANY_TAG.sub(" ", cleaned)
    cleaned = _RE_TRAILING_TAG.sub(" ", cleaned)
    cleaned = html.unescape(cleaned)
    if "&" in cleaned:
        cleaned = html.unescape(cleaned)
    cleaned = (
        cleaned.replace("\xa0", " ")
        .replace("\u200b", "")
        .replace("\ufeff", "")
        .replace("\u3000", " ")
    )
    lines = [_RE_HORIZONTAL_WS.sub(" ", line).strip() for line in cleaned.splitlines()]
    return "\n".join([line for line in lines if line])


def extract_meta_content(html_content: str, prop_name: str) -> str:
    """Extract content from a <meta> tag matching property/name regardless of attribute order."""
    if not html_content or not isinstance(html_content, str) or not prop_name:
        return ""
    scrubbed = _RE_COMMENT_OR_SCRIPT_STYLE.sub(" ", html_content)
    prop_pat = re.compile(
        rf'\b(?:property|name)\s*=\s*(?:"{re.escape(prop_name)}"|\'{re.escape(prop_name)}\')',
        re.IGNORECASE,
    )
    content_pat = re.compile(r'\bcontent\s*=\s*(?:"([^"]*)"|\'([^\']*)\')', re.IGNORECASE)
    for meta_m in re.finditer(r'''<meta\b(?:[^>"']|"[^"]*"|'[^']*')*>''', scrubbed, re.IGNORECASE):
        tag = meta_m.group(0)
        if prop_pat.search(tag):
            cm = content_pat.search(tag)
            if cm:
                val = cm.group(1) if cm.group(1) is not None else (cm.group(2) or "")
                return clean_html_text(val)
    return ""


def strip_non_body_html(html_content: str) -> str:
    """Remove <head>, <script>, <style>, and HTML comments before fallback metadata searches."""
    if not html_content or not isinstance(html_content, str):
        return ""
    cleaned = _RE_COMMENT_OR_SCRIPT_STYLE.sub(" ", html_content)
    cleaned = _RE_HEAD_BLOCK.sub(" ", cleaned)
    return cleaned


COMPILED_VEHICLE_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(pat, re.IGNORECASE), vname) for pat, vname in COMMON_VEHICLE_PATTERNS
]
_LOWERED_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    cat: [kw.lower() for kw in kws] for cat, kws in COMMON_CATEGORY_KEYWORDS.items()
}


def classify_ev_text(
    text: str,
    vehicle_patterns: Optional[List[Tuple[str, str]]] = None,
    category_keywords: Optional[Dict[str, List[str]]] = None,
) -> Tuple[str, Optional[str]]:
    """Classify text into target vehicle and complaint category using precompiled patterns."""
    if not text or not isinstance(text, str):
        return "BYD EV General", None
    text_lower = text.lower()

    target_vehicle = "BYD EV General"
    if vehicle_patterns is None or vehicle_patterns is COMMON_VEHICLE_PATTERNS:
        for compiled_pat, vname in COMPILED_VEHICLE_PATTERNS:
            if compiled_pat.search(text_lower):
                target_vehicle = vname
                break
    else:
        for pattern, vname in vehicle_patterns:
            if re.search(pattern, text_lower):
                target_vehicle = vname
                break

    if category_keywords is None or category_keywords is COMMON_CATEGORY_KEYWORDS:
        kw_map = _LOWERED_CATEGORY_KEYWORDS
        category_scores = {cat: 0 for cat in kw_map}
        for cat, kws in kw_map.items():
            for kw_lower in kws:
                if kw_lower in text_lower:
                    category_scores[cat] += 1
    else:
        category_scores = {cat: 0 for cat in category_keywords}
        for cat, kws in category_keywords.items():
            for kw in kws:
                if kw.lower() in text_lower:
                    category_scores[cat] += 1

    if not category_scores:
        return target_vehicle, None
    best_cat = max(category_scores.items(), key=lambda x: x[1])
    category = best_cat[0] if best_cat[1] > 0 else None
    return target_vehicle, category


def determine_complaint_severity(category: str, text: str) -> str:
    """Heuristic severity assessment for EV defect complaints."""
    text_lower = (text or "").lower()
    if any(w in text_lower for w in ["황천길", "사고", "화재", "죽을뻔", "피쉬테일", "브레이킹", "롤백", "추돌", "벽돌", "방전", "팬텀"]):
        return "critical_safety"
    if any(w in text_lower for w in ["튕김", "통신에러", "충전 불가", "안올라감", "멈춤", "물림", "거북이등", "출력 제한"]):
        return "functional_failure"
    if any(w in text_lower for w in ["아파트", "주민", "입주자", "금지", "민폐", "항의", "입차 거부"]):
        return "social_conflict"
    return "convenience_issue"


def extract_defect_topic(category: str, text: str) -> str:
    """Derive standardized technical defect topic string matching inventory."""
    text = text if isinstance(text, str) else (str(text) if text is not None else "")
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


def load_platform_seed_records(
    platforms: Sequence[str],
    seed_filenames: Sequence[str],
    default_board_name: str,
    limit: Optional[int] = None,
) -> List[ComplaintRecord]:
    """Load fallback ComplaintRecord entries from seed datasets when live scraping is unavailable."""
    if limit is not None and limit <= 0:
        return []
    platform_set = set(platforms)
    default_platform = platforms[0] if platforms else "unknown"
    records: List[ComplaintRecord] = []
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    raw_dirs = [
        os.path.join(base_dir, "data"),
        os.path.join(os.path.dirname(base_dir), "data"),
        os.path.join(os.getcwd(), "data"),
    ]
    search_dirs: List[str] = []
    seen_dirs: Set[str] = set()
    for d in raw_dirs:
        abs_d = os.path.abspath(d)
        if abs_d not in seen_dirs:
            seen_dirs.add(abs_d)
            search_dirs.append(d)

    seen_ids: Set[str] = set()
    for s_dir in search_dirs:
        if not os.path.isdir(s_dir):
            continue
        for s_name in seed_filenames:
            s_file = os.path.join(s_dir, s_name)
            if os.path.isfile(s_file):
                try:
                    with open(s_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get("platform") in platform_set:
                                pid = str(item.get("id") or item.get("post_id") or "")
                                if pid and pid in seen_ids:
                                    continue
                                if pid:
                                    seen_ids.add(pid)
                                records.append(ComplaintRecord(
                                    id=pid,
                                    platform=item.get("platform") or default_platform,
                                    board_name=item.get("board_name") or default_board_name,
                                    post_url=item.get("post_url") or item.get("url") or "",
                                    post_title=item.get("post_title") or item.get("title") or "",
                                    target_vehicle=item.get("target_vehicle") or "Unknown",
                                    category=item.get("category") or "repair_as",
                                    defect_topic=item.get("defect_topic") or "",
                                    raw_quote=item.get("raw_quote") or item.get("content") or "",
                                    slang_terms=item.get("slang_terms") if isinstance(item.get("slang_terms"), list) else [],
                                    severity=item.get("severity") or "convenience_issue",
                                    platform_metadata=item.get("platform_metadata") if isinstance(item.get("platform_metadata"), dict) else {},
                                    collected_at=str(item.get("collected_at") or ""),
                                ))
                                if limit is not None and len(records) >= limit:
                                    return records
                except Exception as e:
                    logger.debug(f"Failed to load seed records from {s_file}: {e}")
        if records:
            break
    return records[:limit] if limit is not None else records


def extract_slang_terms(text: str, slang_dictionary: Dict[str, Any]) -> List[str]:
    """Find all matching slang terms present in the text."""
    if not text or not isinstance(text, str) or not slang_dictionary:
        return []
    if hasattr(slang_dictionary, "keys"):
        keys_iter = slang_dictionary.keys()
    elif isinstance(slang_dictionary, (list, tuple, set, frozenset)):
        keys_iter = slang_dictionary
    else:
        return []
    found_terms = []
    text_lower = text.lower()
    for term in keys_iter:
        if term is None:
            continue
        term_str = str(term)
        if not term_str:
            continue
        term_lower = term_str.lower()
        if term_lower in text_lower or (term_lower != term_str and term_str in text):
            found_terms.append(term_str)
    return sorted(set(found_terms))


def _sanitize_json_value(value: Any) -> Any:
    """Recursively normalize non-finite floats (NaN/Inf/-0.0) so JSON output is strictly RFC-8259 compliant."""
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return 0.0 if value == 0.0 else value
    if isinstance(value, dict):
        return {str(k): _sanitize_json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_json_value(v) for v in value]
    return value


def save_complaints_json(records: List[Union[ComplaintRecord, Dict[str, Any]]], output_path: str):
    """Save complaint records into formatted JSON file atomically and safely."""
    if not output_path or not isinstance(output_path, (str, os.PathLike)):
        logger.warning("Empty output_path provided to save_complaints_json")
        return
    temp_path = None
    try:
        abs_output = os.path.abspath(output_path)
        out_dir = os.path.dirname(abs_output)
        os.makedirs(out_dir, exist_ok=True)
        data = []
        for r in (records or ()):
            if isinstance(r, ComplaintRecord):
                data.append(_sanitize_json_value(r.to_dict()))
            elif isinstance(r, dict):
                data.append(_sanitize_json_value(r))
            else:
                try:
                    data.append(_sanitize_json_value(dict(r)))
                except Exception:
                    continue

        temp_fd, temp_path = tempfile.mkstemp(
            dir=out_dir,
            prefix=f".tmp_complaints_{os.getpid()}_{threading.get_ident()}_",
            suffix=".json",
        )
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
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
    if not input_path or not isinstance(input_path, (str, os.PathLike)):
        logger.warning(f"File not found or empty path: {input_path}")
        return []
    try:
        if not os.path.isfile(input_path):
            logger.warning(f"File not found or empty path: {input_path}")
            return []
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
