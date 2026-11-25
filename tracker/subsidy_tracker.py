"""Core EV Subsidy Depletion Tracker Engine.

Orchestrates data harvesting, metric recalculations, 5-tier alert classifications,
nationwide aggregations, fallback resilience, and atomic persistence.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from fractions import Fraction
import http.client
import ipaddress
import json
import logging
import math
import os
from pathlib import Path
import re
import socket
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import urllib.error
import urllib.parse
import urllib.request

from tracker.atomic_writer import (
    FileLock,
    atomic_write_json,
    atomic_write_json_multiple,
    cleanup_stale_lock_files,
    is_corrupted_or_quarantined_filename,
    quarantine_corrupted_file,
)
from tracker.report_generator import ReportGenerator
from tracker.subsidy_baseline import (
    COMMERCIAL_NATIONAL_CAP_KRW,
    DEFAULT_ALERT_THRESHOLDS,
    PASSENGER_NATIONAL_CAP_KRW,
    build_baseline_regions,
    build_historical_trajectory,
    build_initial_baseline,
    build_popular_models,
    calculate_net_subsidy,
    calculate_price_cap_ratio,
)
from tracker.subsidy_models import (
    AlertSeverity,
    CategoryMetrics,
    MunicipalityMetrics,
    NationwideSummary,
    PopularModelEntry,
    RegionRecord,
    SubsidyMetadata,
    SubsidyPayload,
)

logger = logging.getLogger("subsidy_tracker")

_CURRENT_DIR = Path(__file__).resolve().parent


def _find_repo_root() -> Path:
    """Locate canonical repository root from module file location, active working directory, and symlinks."""
    candidates = [
        _CURRENT_DIR,
        _CURRENT_DIR.parent,
        _CURRENT_DIR.parent.parent,
        Path.cwd(),
        Path.cwd().parent,
        Path.cwd().parent.parent,
    ]
    seen: Set[str] = set()
    expanded_candidates: List[Path] = []
    for c in candidates:
        try:
            c_res = c.resolve()
            for cand in (c, c_res):
                cand_str = str(cand)
                if cand_str not in seen:
                    seen.add(cand_str)
                    expanded_candidates.append(cand)
        except (OSError, RuntimeError):
            if str(c) not in seen:
                seen.add(str(c))
                expanded_candidates.append(c)

    for c in expanded_candidates:
        if (c / "data").is_dir() and (c / "ev-stealth-web").is_dir():
            return c
    for c in expanded_candidates:
        if (c / "data").is_dir() or (c / "ev-stealth-web" / "src" / "data").is_dir():
            return c
    return _CURRENT_DIR.parent

# Maximum bounded response read size (10MB) to prevent memory exhaustion
MAX_RESPONSE_BYTES: int = 10 * 1024 * 1024
# Maximum bounded cache file size (50MB) to prevent OOM on corrupted/special files
MAX_CACHE_BYTES: int = 50 * 1024 * 1024

_RE_URL_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_DISALLOWED_ENDPOINT_HOSTS: Set[str] = {
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
    "metadata.google.internal",
    "metadata.goog",
    "metadata",
    "instance-data",
}
_DISALLOWED_ENDPOINT_SUFFIXES: Tuple[str, ...] = (
    ".localhost",
    ".cluster.local",
    ".internal",
    ".localdomain",
    ".intranet",
    ".lan",
    ".home.arpa",
)
_STANDARD_ENDPOINT_PORTS: Set[int] = {80, 443, 8080, 8443, 8000, 8888}
_NAT64_WELL_KNOWN_PREFIX = ipaddress.IPv6Network("64:ff9b::/96")
_NAT64_LOCAL_PREFIX = ipaddress.IPv6Network("64:ff9b:1::/48")
_CGNAT_PREFIX = ipaddress.IPv4Network("100.64.0.0/10")
_ORCHID_V2_PREFIX = ipaddress.IPv6Network("2001:20::/28")
_SRV6_SID_PREFIX = ipaddress.IPv6Network("5f00::/16")
_IPV4_TRANSLATED_PREFIX = ipaddress.IPv6Network("::ffff:0:0/96")
_IPV4_COMPAT_PREFIX = ipaddress.IPv6Network("::/96")

try:
    from utils.http_client import (
        ResilientHTTPHandler as _ResilientHTTPHandler,
        ResilientHTTPSHandler as _ResilientHTTPSHandler,
        is_safe_ip as _is_safe_ip,
    )
except ImportError:
    _ResilientHTTPHandler = None
    _ResilientHTTPSHandler = None
    def _is_safe_ip(ip: Union[ipaddress.IPv4Address, ipaddress.IPv6Address]) -> bool:
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
        if isinstance(ip, ipaddress.IPv4Address) and ip in _CGNAT_PREFIX:
            return False
        if isinstance(ip, ipaddress.IPv6Address):
            if ip in _ORCHID_V2_PREFIX or ip in _SRV6_SID_PREFIX:
                return False
            if ip.ipv4_mapped and not _is_safe_ip(ip.ipv4_mapped):
                return False
            if ip.sixtofour and not _is_safe_ip(ip.sixtofour):
                return False
            if ip.teredo:
                for teredo_ip in ip.teredo:
                    if not _is_safe_ip(teredo_ip):
                        return False
            if (
                ip in _NAT64_WELL_KNOWN_PREFIX
                or ip in _NAT64_LOCAL_PREFIX
                or ip in _IPV4_TRANSLATED_PREFIX
                or ip in _IPV4_COMPAT_PREFIX
                or ((int(ip) >> 32) & 0xFFFFFFFF) in (0x00005EFE, 0x02005EFE)
            ):
                embedded_v4 = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
                if not _is_safe_ip(embedded_v4):
                    return False
        if str(ip) in ("169.254.169.254", "100.100.100.200"):
            return False
        return True


def _validate_endpoint_url(url: str, allow_private_ips: bool = False) -> Tuple[bool, str]:
    """Validate live polling endpoint URL against SSRF, control chars, and invalid schemes/ports."""
    if not url or not isinstance(url, str):
        return False, "Empty or invalid URL"
    url_str = url.strip()
    if not url_str:
        return False, "Empty URL"
    if _RE_URL_CONTROL_CHARS.search(url_str):
        return False, "URL contains control characters"
    try:
        parsed = urllib.parse.urlsplit(url_str)
    except Exception as exc:
        return False, f"URL parsing error: {exc}"

    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        return False, f"Disallowed URL scheme: {scheme!r}"
    if parsed.username is not None or parsed.password is not None:
        return False, "Disallowed userinfo in endpoint URL"
    if "\\" in (parsed.netloc or ""):
        return False, "Backslash in URL authority"

    hostname = parsed.hostname
    if not hostname:
        return False, "Missing hostname in URL"
    host_lower = hostname.lower().strip().rstrip(".")
    if not host_lower:
        return False, "Missing hostname in URL"
    if any(ch.isspace() for ch in host_lower):
        return False, "Whitespace in hostname"
    if "%" in host_lower:
        return False, "IPv6 zone ID not allowed in endpoint URL"

    try:
        port = parsed.port
    except ValueError as exc:
        return False, f"Invalid port in URL ({exc})"

    if allow_private_ips:
        return True, "Private IPs allowed by configuration"

    if port is not None and port not in _STANDARD_ENDPOINT_PORTS:
        return False, f"Disallowed port {port}"

    if host_lower in _DISALLOWED_ENDPOINT_HOSTS:
        return False, f"Disallowed hostname '{host_lower}'"
    for suffix in _DISALLOWED_ENDPOINT_SUFFIXES:
        if host_lower.endswith(suffix):
            return False, f"Hostname '{host_lower}' matches disallowed internal suffix '{suffix}'"

    try:
        host_ascii = host_lower.encode("idna").decode("ascii").lower().strip().rstrip(".")
    except UnicodeError as exc:
        return False, f"Invalid IDNA hostname '{host_lower}': {exc}"
    if not host_ascii:
        return False, "Missing hostname in URL"
    if "%" in host_ascii:
        return False, "IPv6 zone ID not allowed in endpoint URL"
    if host_ascii in _DISALLOWED_ENDPOINT_HOSTS:
        return False, f"Disallowed hostname '{host_ascii}'"
    for suffix in _DISALLOWED_ENDPOINT_SUFFIXES:
        if host_ascii.endswith(suffix):
            return False, f"Hostname '{host_ascii}' matches disallowed internal suffix '{suffix}'"

    try:
        ip = ipaddress.ip_address(host_ascii)
        if not _is_safe_ip(ip):
            return False, f"Unsafe IP address {ip}"
        return True, "Safe public IP"
    except ValueError:
        pass

    try:
        packed = socket.inet_aton(host_ascii)
        ip4 = ipaddress.IPv4Address(packed)
        if not _is_safe_ip(ip4):
            return False, f"Unsafe encoded IP address {ip4}"
        return True, "Safe public IP"
    except (OSError, ValueError):
        pass

    try:
        addr_info = socket.getaddrinfo(host_ascii, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for _family, _socktype, _proto, _canonname, sockaddr in addr_info:
            ip_str = sockaddr[0]
            if "%" in str(ip_str):
                return False, f"Domain '{host_ascii}' resolves to scoped IP {ip_str}"
            try:
                resolved_ip = ipaddress.ip_address(ip_str)
                if not _is_safe_ip(resolved_ip):
                    return False, f"Domain '{host_ascii}' resolves to unsafe IP {resolved_ip}"
            except ValueError:
                continue
    except socket.gaierror:
        pass
    except Exception as exc:
        logger.debug("DNS check notice for %s: %s", host_ascii, exc)

    return True, "Safe URL"


class _SafeEndpointRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Redirect handler that blocks 3xx redirects to SSRF-unsafe URLs."""

    def __init__(self, allow_private_ips: bool = False) -> None:
        super().__init__()
        self.allow_private_ips = allow_private_ips

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        resolved_url = (
            urllib.parse.urljoin(req.full_url, newurl)
            if isinstance(newurl, str)
            else newurl
        )
        is_safe, reason = _validate_endpoint_url(resolved_url, allow_private_ips=self.allow_private_ips)
        if not is_safe:
            logger.warning("SSRF defense blocked redirect from %s to %s: %s", req.full_url, resolved_url, reason)
            raise urllib.error.HTTPError(
                resolved_url, 403, f"SSRF Blocked: Unsafe redirect target ({reason})", headers, fp
            )
        new_req = super().redirect_request(req, fp, code, msg, headers, resolved_url)
        if new_req is not None:
            strip_credentials = True
            strip_referer = False
            try:
                old_p = urllib.parse.urlsplit(req.full_url)
                new_p = urllib.parse.urlsplit(new_req.full_url)
                old_scheme = (old_p.scheme or "").lower()
                new_scheme = (new_p.scheme or "").lower()
                old_origin = (
                    old_scheme,
                    (old_p.hostname or "").lower().rstrip("."),
                    old_p.port or (443 if old_scheme == "https" else 80),
                )
                new_origin = (
                    new_scheme,
                    (new_p.hostname or "").lower().rstrip("."),
                    new_p.port or (443 if new_scheme == "https" else 80),
                )
                strip_credentials = old_origin != new_origin
                strip_referer = old_scheme == "https" and new_scheme == "http"
            except Exception:
                strip_credentials = True
                strip_referer = True

            if strip_credentials or strip_referer:
                headers_to_strip = {"authorization", "proxy-authorization", "cookie"} if strip_credentials else set()
                if strip_referer:
                    headers_to_strip.add("referer")
                for hdr in list(new_req.headers.keys()):
                    if hdr.lower() in headers_to_strip:
                        new_req.remove_header(hdr)
                for hdr in list(getattr(new_req, "unredirected_hdrs", {}).keys()):
                    if hdr.lower() in headers_to_strip:
                        del new_req.unredirected_hdrs[hdr]
        return new_req

try:
    from utils.http_client import robust_decode
except ImportError:
    try:
        from scrapers.common_utils import robust_decode
    except ImportError:
        def robust_decode(raw_bytes: bytes, declared_encoding: Optional[str] = None) -> str:
            """Decode raw bytes with graceful fallback across Korean and universal charsets."""
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

# Exported baseline aliases and getters matching interface specifications
get_baseline_regions = build_baseline_regions
get_baseline_models = build_popular_models
get_baseline_dataset = build_initial_baseline


# ============================================================================
# Authoritative Statutory Regional Grouping Configuration
# ============================================================================

# Metropolitan Cities (8): 서울, 부산, 대구, 인천, 광주, 대전, 울산, 세종
METROPOLITAN_CITIES: Tuple[str, ...] = (
    "서울",
    "부산",
    "대구",
    "인천",
    "광주",
    "대전",
    "울산",
    "세종",
)

# Provinces (9): 경기, 강원, 충북, 충남, 전북, 전남, 경북, 경남, 제주
PROVINCES: Tuple[str, ...] = (
    "경기",
    "강원",
    "충북",
    "충남",
    "전북",
    "전남",
    "경북",
    "경남",
    "제주",
)

# Comprehensive Korean Province Matching Patterns (supporting full names e.g. 충청북도, 경상남도)
PROVINCE_PATTERNS_KO: Tuple[str, ...] = (
    "경기",
    "강원",
    "충북",
    "충청북",
    "충남",
    "충청남",
    "전북",
    "전라북",
    "전남",
    "전라남",
    "경북",
    "경상북",
    "경남",
    "경상남",
    "제주",
)

METROPOLITAN_PATTERNS_EN: Tuple[str, ...] = (
    "seoul",
    "busan",
    "daegu",
    "incheon",
    "gwangju",
    "daejeon",
    "ulsan",
    "sejong",
)

PROVINCE_PATTERNS_EN: Tuple[str, ...] = (
    "gyeonggi",
    "gangwon",
    "chungbuk",
    "chungcheongbuk",
    "chungnam",
    "chungcheongnam",
    "jeonbuk",
    "jeollabuk",
    "jeonnam",
    "jeollanam",
    "gyeongbuk",
    "gyeongsangbuk",
    "gyeongnam",
    "gyeongsangnam",
    "jeju",
)

METROPOLITAN_CITY_CODES: Tuple[str, ...] = (
    "KR-11",  # 서울특별시
    "KR-26",  # 부산광역시
    "KR-27",  # 대구광역시
    "KR-28",  # 인천광역시
    "KR-29",  # 광주광역시
    "KR-30",  # 대전광역시
    "KR-31",  # 울산광역시
    "KR-36",  # 세종특별자치시
)

PROVINCE_CODES: Tuple[str, ...] = (
    "KR-41",  # 경기도
    "KR-42",  # 강원특별자치도
    "KR-43",  # 충청북도
    "KR-44",  # 충청남도
    "KR-45",  # 전북특별자치도
    "KR-46",  # 전라남도
    "KR-47",  # 경상북도
    "KR-48",  # 경상남도
    "KR-49",  # 제주특별자치도
)

REGIONAL_GROUP_METROPOLITAN: str = "metropolitan_cities"
REGIONAL_GROUP_PROVINCES: str = "provinces"
REGIONAL_GROUP_OTHER: str = "other"


def get_baseline_thresholds() -> Dict[str, Any]:
    """Return default 5-tier alert threshold configuration dictionary."""
    return DEFAULT_ALERT_THRESHOLDS


def _clean_num(val: Any) -> Any:
    """Sanitize numeric input, stripping thousands separators (commas) from strings."""
    if isinstance(val, str):
        val = val.strip().replace(",", "")
    return val


_RE_PLAIN_INT = re.compile(r"^[+-]?\d+$")


def _to_non_neg_int(val: Any) -> Optional[int]:
    """Convert numeric input to non-negative int preserving precision for large integer strings."""
    if val is None or isinstance(val, bool):
        return None
    if type(val) is int:
        return val if val > 0 else 0
    if isinstance(val, Decimal):
        if not val.is_finite():
            return None
        try:
            iv = int(val)
            return iv if iv > 0 else 0
        except (ValueError, TypeError, OverflowError):
            return None
    cleaned = _clean_num(val)
    if isinstance(cleaned, str):
        if not cleaned:
            return None
        if _RE_PLAIN_INT.match(cleaned):
            try:
                iv = int(cleaned)
                return iv if iv > 0 else 0
            except (ValueError, OverflowError):
                return None
    try:
        f = float(cleaned)
        if math.isnan(f) or math.isinf(f):
            return None
        return max(0, int(f))
    except (ValueError, TypeError, OverflowError):
        return None


def calculate_depletion_rate(
    applied: Union[int, float, str, None] = 0,
    announced: Union[int, float, str, None] = None,
    clamp_100: bool = False,
    quota: Union[int, float, str, None] = None,
    clamp: bool = False,
    max_rate: Optional[float] = None,
) -> float:
    """Calculate EV subsidy depletion rate as percentage with zero-division guard and negative clamping.

    Formula:
        (applied / quota) * 100.0

    Args:
        applied: Number of received applications (int, float, or numeric string).
        announced: Total allocated quota units (legacy alias).
        clamp_100: If True, clamp result to [0.0, 100.0]. Defaults to False to track
                   over-exhaustion / waitlisted status (> 100.0%).
        quota: Total allocated quota units (standard naming). Takes precedence over announced if provided.
        clamp: Alias for clamp_100.
        max_rate: Optional upper bound ceiling for rate clamping.

    Returns:
        Depletion percentage rounded to 1 decimal place, guaranteed non-negative.
    """
    try:
        target_quota = quota if quota is not None else announced
        if (
            target_quota is None
            or applied is None
            or isinstance(target_quota, bool)
            or isinstance(applied, bool)
        ):
            return 0.0
        clean_quota = _clean_num(target_quota)
        clean_applied = _clean_num(applied)
        try:
            if isinstance(clean_quota, str) and _RE_PLAIN_INT.match(clean_quota) and len(clean_quota.lstrip("+-")) > 300:
                raise OverflowError
            if isinstance(clean_applied, str) and _RE_PLAIN_INT.match(clean_applied) and len(clean_applied.lstrip("+-")) > 300:
                raise OverflowError
            quota_val = float(clean_quota)
            applied_val = float(clean_applied)
        except OverflowError:
            q_int = _to_non_neg_int(clean_quota)
            a_int = _to_non_neg_int(clean_applied)
            if q_int is None or a_int is None or a_int <= 0:
                return 0.0
            if q_int <= 0:
                try:
                    q_flt = float(clean_quota)
                    if math.isnan(q_flt) or math.isinf(q_flt) or q_flt <= 0.0:
                        return 0.0
                    rate = 100.0 if (clamp_100 or clamp) else 0.0
                except (ValueError, TypeError, OverflowError):
                    return 0.0
            else:
                try:
                    raw_rate = (a_int * 100) / q_int
                    if math.isnan(raw_rate) or math.isinf(raw_rate):
                        rate = 100.0 if (clamp_100 or clamp) else 0.0
                    else:
                        rate = max(0.0, round(raw_rate, 1))
                        if clamp_100 or clamp:
                            rate = min(100.0, rate)
                except OverflowError:
                    rate = 100.0 if (clamp_100 or clamp) else 0.0
        else:
            if math.isnan(quota_val) or math.isnan(applied_val) or math.isinf(quota_val) or math.isinf(applied_val):
                return 0.0
            if quota_val <= 0.0 or applied_val <= 0.0:
                return 0.0
            scaled = applied_val * 100.0
            raw_rate = (scaled / quota_val) if not math.isinf(scaled) else ((applied_val / quota_val) * 100.0)
            if math.isnan(raw_rate):
                return 0.0
            if math.isinf(raw_rate):
                if clamp_100 or clamp:
                    rate = 100.0
                else:
                    return 0.0
            else:
                rate = max(0.0, round(raw_rate, 1))
                if clamp_100 or clamp:
                    rate = min(100.0, rate)
        if max_rate is not None and not isinstance(max_rate, bool):
            try:
                mr = float(_clean_num(max_rate))
                if not math.isnan(mr) and not math.isinf(mr) and mr >= 0.0:
                    rate = min(mr, rate)
            except (ValueError, TypeError, OverflowError):
                pass
        return max(0.0, rate)
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return 0.0


def is_depletion_over_exhausted(depletion_rate: Union[int, float, str, None]) -> bool:
    """Return True if depletion rate strictly exceeds 100.0% (over-exhaustion / waitlisted)."""
    try:
        if depletion_rate is None or isinstance(depletion_rate, bool):
            return False
        r = float(_clean_num(depletion_rate))
        return not (math.isnan(r) or math.isinf(r)) and r > 100.0
    except (TypeError, ValueError, OverflowError):
        return False


def calculate_remaining_units(
    applied: Union[int, float, str, None] = 0,
    announced: Union[int, float, str, None] = None,
    quota: Union[int, float, str, None] = None,
) -> int:
    """Calculate remaining quota units clamped at zero: max(0, quota - applied).

    Args:
        applied: Number of received applications.
        announced: Total allocated quota units.
        quota: Standard alias for total allocated quota units.

    Returns:
        Remaining units as non-negative integer (clamped to 0 upon over-subscription).
    """
    try:
        target_quota = quota if quota is not None else announced
        if (
            target_quota is None
            or applied is None
            or isinstance(target_quota, bool)
            or isinstance(applied, bool)
        ):
            return 0
        if type(target_quota) is int and type(applied) is int:
            return max(0, max(0, target_quota) - max(0, applied))
        safe_quota = _to_non_neg_int(target_quota)
        safe_applied = _to_non_neg_int(applied)
        if safe_quota is None or safe_applied is None:
            return 0
        return max(0, safe_quota - safe_applied)
    except (TypeError, ValueError, OverflowError):
        return 0


def calculate_waitlist_units(
    applied: Union[int, float, str, None] = 0,
    announced: Union[int, float, str, None] = None,
    quota: Union[int, float, str, None] = None,
) -> int:
    """Calculate waitlisted/over-subscribed units beyond announced quota: max(0, applied - quota)."""
    try:
        target_quota = quota if quota is not None else announced
        if (
            target_quota is None
            or applied is None
            or isinstance(target_quota, bool)
            or isinstance(applied, bool)
        ):
            return 0
        if type(target_quota) is int and type(applied) is int:
            return max(0, max(0, applied) - max(0, target_quota))
        safe_quota = _to_non_neg_int(target_quota)
        safe_applied = _to_non_neg_int(applied)
        if safe_quota is None or safe_applied is None:
            return 0
        return max(0, safe_applied - safe_quota)
    except (TypeError, ValueError, OverflowError):
        return 0


def calculate_delivery_rate(
    delivered: Union[int, float, str, None] = 0,
    announced: Union[int, float, str, None] = None,
    quota: Union[int, float, str, None] = None,
    clamp_100: bool = False,
    clamp: bool = False,
    max_rate: Optional[float] = None,
) -> float:
    """Calculate EV delivery rate percentage against announced quota: (delivered / quota) * 100."""
    return calculate_depletion_rate(
        applied=delivered,
        announced=announced,
        quota=quota,
        clamp_100=clamp_100,
        clamp=clamp,
        max_rate=max_rate,
    )


def calculate_pending_deliveries(
    applied: Union[int, float, str, None] = 0,
    delivered: Union[int, float, str, None] = 0,
) -> int:
    """Calculate pending delivery units (applied - delivered) clamped at zero."""
    try:
        if (
            applied is None
            or delivered is None
            or isinstance(applied, bool)
            or isinstance(delivered, bool)
        ):
            return 0
        if type(applied) is int and type(delivered) is int:
            return max(0, max(0, applied) - max(0, delivered))
        safe_applied = _to_non_neg_int(applied)
        safe_delivered = _to_non_neg_int(delivered)
        if safe_applied is None or safe_delivered is None:
            return 0
        return max(0, safe_applied - safe_delivered)
    except (TypeError, ValueError, OverflowError):
        return 0


# ============================================================================
# Velocity Tracking and Quota Exhaustion Prediction
# ============================================================================

def calculate_depletion_velocity(
    applied_start: Union[int, float, str, None],
    applied_end: Union[int, float, str, None],
    days: Union[int, float, str, None],
) -> float:
    """Calculate daily application velocity (units/day) with zero-division and invalid input guards.

    Formula:
        (applied_end - applied_start) / days

    Args:
        applied_start: Initial application count at period start.
        applied_end: Final application count at period end.
        days: Elapsed calendar days between observation points.

    Returns:
        Average units applied per day, non-negative float rounded to 2 decimal places.
        Returns 0.0 if days <= 0 or invalid inputs provided. Never raises ZeroDivisionError.
    """
    try:
        if (
            applied_start is None
            or applied_end is None
            or days is None
            or isinstance(applied_start, bool)
            or isinstance(applied_end, bool)
            or isinstance(days, bool)
        ):
            return 0.0
        f_start = float(_clean_num(applied_start))
        f_end = float(_clean_num(applied_end))
        f_days = float(_clean_num(days))
        if math.isnan(f_start) or math.isnan(f_end) or math.isnan(f_days):
            return 0.0
        if math.isinf(f_start) or math.isinf(f_end) or math.isinf(f_days):
            return 0.0
        if f_days <= 0.0:
            return 0.0
        diff = max(0.0, f_end - f_start)
        velocity = round(diff / f_days, 2)
        if math.isnan(velocity) or math.isinf(velocity):
            return 0.0
        return max(0.0, velocity)
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return 0.0


def predict_exhaustion_days(
    remaining_units: Union[int, float, str, None],
    daily_velocity: Union[int, float, str, None],
) -> Optional[int]:
    """Predict number of calendar days until quota exhaustion based on daily burn velocity.

    Formula:
        remaining_units / daily_velocity

    Guards:
        - If remaining_units <= 0: returns 0 (already depleted/exhausted).
        - If daily_velocity <= 0: returns None (cannot exhaust at non-positive velocity).
        - Catches ZeroDivisionError, OverflowError, ValueError, TypeError, NaN, Inf.

    Returns:
        Non-negative integer days remaining, or None if velocity is non-positive.
    """
    try:
        if (
            remaining_units is None
            or daily_velocity is None
            or isinstance(remaining_units, bool)
            or isinstance(daily_velocity, bool)
        ):
            return None
        f_rem = float(_clean_num(remaining_units))
        f_vel = float(_clean_num(daily_velocity))
        if math.isnan(f_rem) or math.isnan(f_vel) or math.isinf(f_rem) or math.isinf(f_vel):
            return None
        if f_rem <= 0.0:
            return 0
        if f_vel <= 0.0:
            return None
        try:
            if isinstance(remaining_units, Decimal):
                dec_rem = remaining_units
            elif isinstance(remaining_units, (int, str)):
                dec_rem = Decimal(str(_clean_num(remaining_units)))
            else:
                dec_rem = Decimal(str(f_rem))

            if isinstance(daily_velocity, Decimal):
                dec_vel = daily_velocity
            elif isinstance(daily_velocity, (int, str)):
                dec_vel = Decimal(str(_clean_num(daily_velocity)))
            else:
                dec_vel = Decimal(str(f_vel))

            if (
                dec_rem.is_finite()
                and dec_vel.is_finite()
                and abs(dec_rem.adjusted()) <= 1000
                and abs(dec_vel.adjusted()) <= 1000
            ):
                days = math.ceil(Fraction(dec_rem) / Fraction(dec_vel))
            else:
                days_dec = (dec_rem / dec_vel).to_integral_value(rounding=ROUND_CEILING)
                days = int(days_dec)
        except (InvalidOperation, ZeroDivisionError, OverflowError, ValueError):
            days = int(math.ceil(f_rem / f_vel))
        return max(0, days)
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return None


def predict_exhaustion_date(
    remaining_units: Union[int, float, str, None],
    daily_velocity: Union[int, float, str, None],
    start_date: Optional[Union[datetime, str]] = None,
) -> Optional[str]:
    """Predict estimated calendar date (YYYY-MM-DD) of subsidy exhaustion.

    Returns None if burn rate is zero or negative, or if calculation fails.
    Guarantees no ZeroDivisionError or OverflowError.
    """
    days = predict_exhaustion_days(remaining_units, daily_velocity)
    if days is None:
        return None
    try:
        if start_date is None:
            base_dt = datetime.now(timezone.utc)
        elif isinstance(start_date, datetime):
            base_dt = start_date
        elif isinstance(start_date, date):
            base_dt = datetime(start_date.year, start_date.month, start_date.day, tzinfo=timezone.utc)
        elif isinstance(start_date, str):
            clean_s = start_date.strip()
            if "T" in clean_s or "t" in clean_s or (" " in clean_s and ":" in clean_s):
                iso_s = clean_s.replace("t", "T", 1) if "t" in clean_s else clean_s
                if iso_s.endswith(("Z", "z")):
                    iso_s = iso_s[:-1] + "+00:00"
                base_dt = datetime.fromisoformat(iso_s)
            else:
                base_dt = datetime.strptime(clean_s[:10], "%Y-%m-%d")
        else:
            base_dt = datetime.now(timezone.utc)
        target_date = base_dt + timedelta(days=days)
        return target_date.strftime("%Y-%m-%d")
    except Exception:
        return None


def classify_region_group(region: Union[RegionRecord, Dict[str, Any], str, None]) -> str:
    """Classify region into 'metropolitan_cities', 'provinces', or 'other'.

    Groups:
    - Metropolitan cities (8): 서울, 부산, 대구, 인천, 광주, 대전, 울산, 세종
    - Provinces (9): 경기, 강원, 충북, 충남, 전북, 전남, 경북, 경남, 제주
    """
    if region is None:
        return REGIONAL_GROUP_OTHER

    if isinstance(region, str):
        ident = region.strip()
        if not ident:
            return REGIONAL_GROUP_OTHER
        ident_upper = ident.upper()
        if ident_upper in METROPOLITAN_CITY_CODES or ident_upper == "KR-50":
            return REGIONAL_GROUP_METROPOLITAN
        if ident_upper in PROVINCE_CODES:
            return REGIONAL_GROUP_PROVINCES
        for prov in PROVINCE_PATTERNS_KO:
            if prov in ident:
                return REGIONAL_GROUP_PROVINCES
        for city in METROPOLITAN_CITIES:
            if city in ident:
                return REGIONAL_GROUP_METROPOLITAN
        ident_lower = ident.lower()
        if any(p in ident_lower for p in PROVINCE_PATTERNS_EN):
            return REGIONAL_GROUP_PROVINCES
        if any(c in ident_lower for c in METROPOLITAN_PATTERNS_EN):
            return REGIONAL_GROUP_METROPOLITAN
        return REGIONAL_GROUP_OTHER

    iso_code = (
        _metric_val(region, "iso_code", "")
        or _metric_val(region, "region_id", "")
        or _metric_val(region, "code", "")
        or _metric_val(region, "id", "")
    )
    iso_upper = str(iso_code).strip().upper()
    if iso_upper in METROPOLITAN_CITY_CODES or iso_upper == "KR-50":
        return REGIONAL_GROUP_METROPOLITAN
    if iso_upper in PROVINCE_CODES:
        return REGIONAL_GROUP_PROVINCES

    name_ko = str(_metric_val(region, "name_ko", "") or _metric_val(region, "name", "")).strip()
    for prov in PROVINCE_PATTERNS_KO:
        if prov in name_ko:
            return REGIONAL_GROUP_PROVINCES
    for city in METROPOLITAN_CITIES:
        if city in name_ko:
            return REGIONAL_GROUP_METROPOLITAN

    name_en = str(_metric_val(region, "name_en", "")).strip().lower()
    if any(p in name_en for p in PROVINCE_PATTERNS_EN):
        return REGIONAL_GROUP_PROVINCES
    if any(c in name_en for c in METROPOLITAN_PATTERNS_EN):
        return REGIONAL_GROUP_METROPOLITAN

    tier = str(_metric_val(region, "tier", "")).strip().lower()
    if tier in ("special_city", "metropolitan_city", "special_self_governing_city"):
        return REGIONAL_GROUP_METROPOLITAN
    if tier in ("province", "special_self_governing_province"):
        return REGIONAL_GROUP_PROVINCES

    return REGIONAL_GROUP_OTHER


def is_metropolitan_city(region: Union[RegionRecord, Dict[str, Any], str, None]) -> bool:
    """Return True if region is one of the 8 Metropolitan cities."""
    return classify_region_group(region) == REGIONAL_GROUP_METROPOLITAN


def is_province(region: Union[RegionRecord, Dict[str, Any], str, None]) -> bool:
    """Return True if region is one of the 9 Provinces."""
    return classify_region_group(region) == REGIONAL_GROUP_PROVINCES


def group_regions_by_type(
    regions: Optional[List[Union[RegionRecord, Dict[str, Any]]]] = None,
) -> Dict[str, List[Any]]:
    """Group 17 administrative regions into Metropolitan cities (8) and Provinces (9).

    Returns:
    {
        "metropolitan_cities": [서울, 부산, 대구, 인천, 광주, 대전, 울산, 세종],
        "provinces": [경기, 강원, 충북, 충남, 전북, 전남, 경북, 경남, 제주],
    }
    """
    if regions is None:
        regions = build_baseline_regions()

    grouped: Dict[str, List[Any]] = {
        REGIONAL_GROUP_METROPOLITAN: [],
        REGIONAL_GROUP_PROVINCES: [],
    }

    for r in regions:
        grp = classify_region_group(r)
        if grp == REGIONAL_GROUP_METROPOLITAN:
            grouped[REGIONAL_GROUP_METROPOLITAN].append(r)
        elif grp == REGIONAL_GROUP_PROVINCES:
            grouped[REGIONAL_GROUP_PROVINCES].append(r)
        else:
            if "other" not in grouped:
                grouped["other"] = []
            grouped["other"].append(r)

    return grouped


group_regions_by_category = group_regions_by_type


def generate_fallback_payload() -> SubsidyPayload:
    """Generate authoritative verified 2026 fallback baseline dataset with updated metrics."""
    payload = build_initial_baseline()
    tracker = SubsidyTracker()
    for idx, r in enumerate(payload.regions):
        payload.regions[idx] = tracker.update_region_metrics(r)
    payload.nationwide_summary = tracker.compute_nationwide_summary(payload.regions)
    payload.metadata.generated_at = datetime.now(timezone.utc).isoformat()
    return payload


def classify_alert_tier(depletion_rate: float) -> str:
    """Classify depletion rate into standard 5-tier alert severity level."""
    return AlertSeverity.from_rate(depletion_rate).value


def _metric_val(metric: Any, key: str, default: Any = 0) -> Any:
    """Safely extract metric attribute or dict key, supporting dict, Mapping, and dataclass instances."""
    if metric is None:
        return default
    if hasattr(metric, "get") and callable(getattr(metric, "get")):
        val = metric.get(key, default)
        return default if val is None else val
    val = getattr(metric, key, default)
    return default if val is None else val


def _safe_int_metric(val: Any, default: int = 0) -> int:
    """Safely cast value to int, gracefully handling NaN, Inf, None, bool, float strings, commas, and invalid types."""
    if val is None or isinstance(val, bool):
        return default
    if type(val) is int:
        return val
    if isinstance(val, Decimal):
        if not val.is_finite():
            return default
        try:
            return int(val)
        except (ValueError, TypeError, OverflowError):
            return default
    cleaned = _clean_num(val)
    if isinstance(cleaned, str):
        if not cleaned:
            return default
        if _RE_PLAIN_INT.match(cleaned):
            try:
                return int(cleaned)
            except (ValueError, OverflowError):
                return default
    try:
        f = float(cleaned)
        if math.isnan(f) or math.isinf(f):
            return default
        return int(f)
    except (ValueError, TypeError, OverflowError):
        return default


class SubsidyTracker:
    """Automated tracker for nationwide South Korea EV subsidy allocations and depletion."""

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        timeout_seconds: float = 5.0,
        cache_fallback_path: Optional[Union[str, Path]] = None,
        validate_cache: bool = False,
        quarantine_corrupted: bool = False,
        report_generator: Optional[ReportGenerator] = None,
        allow_private_ips: bool = False,
    ) -> None:
        self.endpoint_url = endpoint_url
        try:
            if timeout_seconds is None or isinstance(timeout_seconds, bool):
                self.timeout_seconds = 5.0
            else:
                val = float(timeout_seconds)
                self.timeout_seconds = val if (not math.isnan(val) and not math.isinf(val) and val > 0) else 5.0
        except (ValueError, TypeError, OverflowError):
            self.timeout_seconds = 5.0
        self.cache_fallback_path = Path(cache_fallback_path) if cache_fallback_path else None
        self.validate_cache = validate_cache
        self.quarantine_corrupted = quarantine_corrupted
        self.report_generator = report_generator or ReportGenerator()
        self.allow_private_ips = bool(allow_private_ips)

    def evaluate_status(self, depletion_rate: float) -> AlertSeverity:
        """Evaluate 5-tier alert severity from depletion percentage."""
        return AlertSeverity.from_rate(depletion_rate)

    def calculate_category_metrics(
        self,
        announced: int,
        applied: int,
        delivered: int,
        max_local_subsidy: int,
        national_cap: int = PASSENGER_NATIONAL_CAP_KRW,
        avg_per_unit_budget: int = 10_000_000,
    ) -> CategoryMetrics:
        safe_announced = max(0, _safe_int_metric(announced, 0))
        safe_applied = max(0, _safe_int_metric(applied, 0))
        safe_delivered = max(0, _safe_int_metric(delivered, 0))
        safe_max_local = max(0, _safe_int_metric(max_local_subsidy, 0))
        safe_national_cap = max(0, _safe_int_metric(national_cap, PASSENGER_NATIONAL_CAP_KRW))
        safe_unit_budget = max(0, _safe_int_metric(avg_per_unit_budget, 10_000_000))

        depletion_rate = calculate_depletion_rate(safe_applied, safe_announced)
        delivery_rate = calculate_depletion_rate(safe_delivered, safe_announced)
        remaining_units = calculate_remaining_units(safe_applied, safe_announced)
        status = self.evaluate_status(depletion_rate).value

        total_budget = safe_announced * safe_unit_budget
        disbursed_budget = safe_applied * safe_unit_budget
        remaining_budget = max(0, total_budget - disbursed_budget)

        return CategoryMetrics(
            announced_units=safe_announced,
            applied_units=safe_applied,
            delivered_units=safe_delivered,
            remaining_units=remaining_units,
            depletion_rate=depletion_rate,
            delivery_rate=delivery_rate,
            status=status,
            max_local_subsidy_krw=safe_max_local,
            max_total_subsidy_krw=safe_max_local + safe_national_cap,
            total_budget_krw=total_budget,
            remaining_budget_krw=remaining_budget,
        )

    def update_region_metrics(self, region: Union[RegionRecord, Dict[str, Any]]) -> Union[RegionRecord, Dict[str, Any]]:
        """Recalculate overall status and depletion rates for a region."""
        if region is None:
            return {}
        if not isinstance(region, dict) and not hasattr(region, "__dict__"):
            return region

        total_announced = 0
        total_applied = 0

        cats = region.get("categories") if isinstance(region, dict) else getattr(region, "categories", {})
        if not isinstance(cats, dict):
            cats = {}
        for cat_name, cat in cats.items():
            safe_ann = max(0, _safe_int_metric(_metric_val(cat, "announced_units", 0), 0))
            safe_app = max(0, _safe_int_metric(_metric_val(cat, "applied_units", 0), 0))
            safe_del = max(0, _safe_int_metric(_metric_val(cat, "delivered_units", 0), 0))
            rem_units = calculate_remaining_units(safe_app, safe_ann)
            dep_rate = calculate_depletion_rate(safe_app, safe_ann)
            del_rate = calculate_depletion_rate(safe_del, safe_ann)
            st_val = self.evaluate_status(dep_rate).value

            safe_total_budget = max(0, _safe_int_metric(_metric_val(cat, "total_budget_krw", 0), 0))
            if safe_total_budget > 0 and safe_ann > 0:
                rem_ratio_units = max(0, safe_ann - safe_app)
                if rem_ratio_units == 0:
                    safe_rem_budget = 0
                else:
                    prod = safe_total_budget * rem_ratio_units
                    if prod < (1 << 52):
                        scaled_rem_budget = int(round(prod / safe_ann))
                    else:
                        scaled_rem_budget = round(Fraction(prod, safe_ann))
                    safe_rem_budget = min(
                        safe_total_budget,
                        max(0, scaled_rem_budget),
                    )
            else:
                cat_rem = max(0, _safe_int_metric(_metric_val(cat, "remaining_budget_krw", 0), 0))
                safe_rem_budget = min(safe_total_budget, cat_rem) if safe_total_budget > 0 else cat_rem

            if hasattr(cat, "announced_units"):
                cat.announced_units = safe_ann
                cat.applied_units = safe_app
                cat.delivered_units = safe_del
                cat.remaining_units = rem_units
                cat.depletion_rate = dep_rate
                cat.delivery_rate = del_rate
                cat.status = st_val
                cat.total_budget_krw = safe_total_budget
                cat.remaining_budget_krw = safe_rem_budget
            elif isinstance(cat, dict):
                cat["announced_units"] = safe_ann
                cat["applied_units"] = safe_app
                cat["delivered_units"] = safe_del
                cat["remaining_units"] = rem_units
                cat["depletion_rate"] = dep_rate
                cat["delivery_rate"] = del_rate
                cat["status"] = st_val
                cat["total_budget_krw"] = safe_total_budget
                cat["remaining_budget_krw"] = safe_rem_budget

            total_announced += safe_ann
            total_applied += safe_app

        # Recalculate municipalities if present
        munis = region.get("municipalities") if isinstance(region, dict) else getattr(region, "municipalities", None)
        if isinstance(munis, (list, tuple)):
            for muni in munis:
                if muni is None:
                    continue
                safe_m_ann = max(0, _safe_int_metric(_metric_val(muni, "announced_units", 0), 0))
                safe_m_app = max(0, _safe_int_metric(_metric_val(muni, "applied_units", 0), 0))
                safe_m_del = max(0, _safe_int_metric(_metric_val(muni, "delivered_units", 0), 0))
                m_rem = calculate_remaining_units(safe_m_app, safe_m_ann)
                m_dep = calculate_depletion_rate(safe_m_app, safe_m_ann)
                m_stat = self.evaluate_status(m_dep).value

                if hasattr(muni, "announced_units"):
                    muni.announced_units = safe_m_ann
                    muni.applied_units = safe_m_app
                    if hasattr(muni, "delivered_units"):
                        muni.delivered_units = safe_m_del
                    muni.remaining_units = m_rem
                    muni.depletion_rate = m_dep
                    muni.status = m_stat
                elif isinstance(muni, dict):
                    muni["announced_units"] = safe_m_ann
                    muni["applied_units"] = safe_m_app
                    if "delivered_units" in muni or (hasattr(muni, "get") and muni.get("delivered_units") is not None):
                        muni["delivered_units"] = safe_m_del
                    muni["remaining_units"] = m_rem
                    muni["depletion_rate"] = m_dep
                    muni["status"] = m_stat

        # Overall depletion rate is weighted by volume across all categories
        overall_rate = calculate_depletion_rate(total_applied, total_announced)
        st_eval = self.evaluate_status(overall_rate).value
        if isinstance(region, dict):
            region["overall_depletion_rate"] = overall_rate
            region["overall_status"] = st_eval
        elif hasattr(region, "__dict__"):
            region.overall_depletion_rate = overall_rate
            region.overall_status = st_eval
        return region

    def compute_nationwide_summary(self, regions: List[Any]) -> NationwideSummary:
        """Aggregate totals across all tracked regions."""
        if not regions:
            regions = []
        total_announced = 0
        total_applied = 0
        total_delivered = 0
        total_budget_krw = 0
        disbursed_budget_krw = 0

        cat_counts: Dict[str, Dict[str, int]] = {
            "passenger": {"announced": 0, "applied": 0, "delivered": 0},
            "commercial": {"announced": 0, "applied": 0, "delivered": 0},
            "bus": {"announced": 0, "applied": 0, "delivered": 0},
        }

        alert_counts: Dict[str, int] = {
            "healthy": 0,
            "caution": 0,
            "warning": 0,
            "critical": 0,
            "depleted": 0,
        }

        for r in regions:
            if r is None:
                continue
            # Region overall status
            st_raw = (
                (r.get("overall_status") or r.get("status"))
                if isinstance(r, dict)
                else getattr(r, "overall_status", "")
            )
            if hasattr(st_raw, "value"):
                st_raw = st_raw.value
            st_str = str(st_raw or "").strip()
            if "." in st_str:
                st_str = st_str.split(".")[-1]
            st_key = st_str.lower()
            r_cats = (r.get("categories") if isinstance(r, dict) else getattr(r, "categories", None)) or {}
            if not isinstance(r_cats, dict):
                r_cats = {}

            if st_key not in alert_counts and (
                r_cats
                or (isinstance(r, dict) and ("overall_depletion_rate" in r or "depletion_rate" in r))
                or hasattr(r, "overall_depletion_rate")
            ):
                raw_rate = _metric_val(r, "overall_depletion_rate", None)
                if raw_rate is None and isinstance(r, dict):
                    raw_rate = r.get("depletion_rate")
                if raw_rate is not None and not isinstance(raw_rate, bool):
                    try:
                        f_rate = float(_clean_num(raw_rate))
                        if not math.isnan(f_rate) and not math.isinf(f_rate):
                            st_key = self.evaluate_status(max(0.0, f_rate)).value.lower()
                    except (ValueError, TypeError, OverflowError):
                        pass
                if st_key not in alert_counts and r_cats:
                    r_ann = sum(max(0, _safe_int_metric(_metric_val(c, "announced_units", 0), 0)) for c in r_cats.values())
                    r_app = sum(max(0, _safe_int_metric(_metric_val(c, "applied_units", 0), 0)) for c in r_cats.values())
                    st_key = self.evaluate_status(calculate_depletion_rate(r_app, r_ann)).value.lower()

            if st_key in alert_counts:
                alert_counts[st_key] += 1

            for c_name, c_data in r_cats.items():
                if c_name not in cat_counts:
                    cat_counts[c_name] = {"announced": 0, "applied": 0, "delivered": 0}

                c_ann = max(0, _safe_int_metric(_metric_val(c_data, "announced_units", 0), 0))
                c_app = max(0, _safe_int_metric(_metric_val(c_data, "applied_units", 0), 0))
                c_del = max(0, _safe_int_metric(_metric_val(c_data, "delivered_units", 0), 0))
                c_tot_b = max(0, _safe_int_metric(_metric_val(c_data, "total_budget_krw", 0), 0))
                c_rem_raw = max(0, _safe_int_metric(_metric_val(c_data, "remaining_budget_krw", 0), 0))
                c_rem_b = min(c_tot_b, c_rem_raw) if c_tot_b > 0 else c_rem_raw

                cat_counts[c_name]["announced"] += c_ann
                cat_counts[c_name]["applied"] += c_app
                cat_counts[c_name]["delivered"] += c_del

                total_announced += c_ann
                total_applied += c_app
                total_delivered += c_del
                total_budget_krw += c_tot_b
                disbursed_budget_krw += max(0, c_tot_b - c_rem_b)

        total_remaining = calculate_remaining_units(total_applied, total_announced)
        nationwide_rate = calculate_depletion_rate(total_applied, total_announced)

        cat_totals = {}
        for c_name, counts in cat_counts.items():
            c_ann = counts["announced"]
            c_app = counts["applied"]
            c_del = counts["delivered"]
            c_rate = calculate_depletion_rate(c_app, c_ann)
            c_del_rate = calculate_depletion_rate(c_del, c_ann)
            cat_totals[c_name] = {
                "announced_units": c_ann,
                "applied_units": c_app,
                "delivered_units": c_del,
                "remaining_units": calculate_remaining_units(c_app, c_ann),
                "depletion_rate": c_rate,
                "delivery_rate": c_del_rate,
                "status": self.evaluate_status(c_rate).value,
            }

        try:
            total_budget_billion = round(total_budget_krw / 1_000_000_000, 1)
        except OverflowError:
            try:
                total_budget_billion = float(total_budget_krw // 1_000_000_000)
            except OverflowError:
                total_budget_billion = 0.0
        try:
            disbursed_budget_billion = max(0.0, round(disbursed_budget_krw / 1_000_000_000, 1))
        except OverflowError:
            try:
                disbursed_budget_billion = max(0.0, float(disbursed_budget_krw // 1_000_000_000))
            except OverflowError:
                disbursed_budget_billion = 0.0

        return NationwideSummary(
            total_announced_units=total_announced,
            total_applied_units=total_applied,
            total_delivered_units=total_delivered,
            total_remaining_units=total_remaining,
            nationwide_depletion_rate=nationwide_rate,
            total_budget_billion_krw=total_budget_billion,
            disbursed_budget_billion_krw=disbursed_budget_billion,
            category_totals=cat_totals,
            alert_region_counts=alert_counts,
        )

    def fetch_live_updates(
        self,
        max_retries: int = 3,
        backoff_base: float = 0.05,
    ) -> Optional[Dict[str, Any]]:
        """Attempt to fetch live data from remote endpoint with 3-attempt exponential backoff retry."""
        if not self.endpoint_url or not isinstance(self.endpoint_url, str):
            logger.debug("No endpoint URL configured. Using validated baseline engine.")
            return None

        clean_url = self.endpoint_url.strip()
        is_safe, reason = _validate_endpoint_url(clean_url, allow_private_ips=self.allow_private_ips)
        if not is_safe:
            logger.warning("Refusing unsafe endpoint URL %s: %s", self.endpoint_url, reason)
            return None

        logger.info("Attempting live poll from %s (timeout=%.1fs)...", clean_url, self.timeout_seconds)
        try:
            if backoff_base is None or isinstance(backoff_base, bool):
                safe_backoff = 0.05
            else:
                safe_backoff = float(backoff_base)
                if math.isnan(safe_backoff) or math.isinf(safe_backoff) or safe_backoff < 0.0:
                    safe_backoff = 0.05
        except (ValueError, TypeError, OverflowError):
            safe_backoff = 0.05
        closed_exc_ids: Set[int] = set()
        safe_retries = min(100, max(1, _safe_int_metric(max_retries, 3)))
        use_custom_opener = getattr(urllib.request.urlopen, "__module__", "") == "urllib.request"
        opener: Optional[urllib.request.OpenerDirector] = None
        if use_custom_opener:
            if (_ResilientHTTPHandler is None or _ResilientHTTPSHandler is None) and not self.allow_private_ips:
                logger.error(
                    "Refusing live poll for %s: SSRF-safe socket-pinning HTTP/HTTPS handlers unavailable.",
                    clean_url,
                )
                return None
            handlers: List[urllib.request.BaseHandler] = [
                _SafeEndpointRedirectHandler(allow_private_ips=self.allow_private_ips)
            ]
            if _ResilientHTTPHandler is not None and _ResilientHTTPSHandler is not None:
                handlers.append(
                    _ResilientHTTPHandler(
                        connect_timeout=self.timeout_seconds,
                        read_timeout=self.timeout_seconds,
                        allow_private_ips=self.allow_private_ips,
                    )
                )
                handlers.append(
                    _ResilientHTTPSHandler(
                        connect_timeout=self.timeout_seconds,
                        read_timeout=self.timeout_seconds,
                        allow_private_ips=self.allow_private_ips,
                        allowed_ports=None if self.allow_private_ips else _STANDARD_ENDPOINT_PORTS,
                    )
                )
            opener = urllib.request.build_opener(*handlers)

        for attempt in range(1, safe_retries + 1):
            try:
                req = urllib.request.Request(
                    clean_url,
                    headers={
                        "User-Agent": "MyECar-SubsidyTracker/1.0 (Automated Scheduled Task)",
                        "Accept-Encoding": "identity",
                    },
                )
                if opener is not None:
                    ctx_mgr = opener.open(req, timeout=self.timeout_seconds)
                else:
                    ctx_mgr = urllib.request.urlopen(req, timeout=self.timeout_seconds)
                with ctx_mgr as resp:
                    final_url = getattr(resp, "geturl", lambda: None)()
                    if isinstance(final_url, str) and final_url and final_url != clean_url:
                        final_safe, final_reason = _validate_endpoint_url(
                            final_url, allow_private_ips=self.allow_private_ips
                        )
                        if not final_safe:
                            logger.warning("SSRF defense blocked final URL %s: %s", final_url, final_reason)
                            return None
                    resp_status = getattr(resp, "status", getattr(resp, "code", 200))
                    if resp_status == 200:
                        raw_bytes = resp.read(MAX_RESPONSE_BYTES)
                        declared_encoding = None
                        if hasattr(resp, "headers") and hasattr(resp.headers, "get_content_charset"):
                            try:
                                charset = resp.headers.get_content_charset()
                                if isinstance(charset, str):
                                    declared_encoding = charset
                            except Exception:
                                pass
                        raw_data = robust_decode(raw_bytes, declared_encoding=declared_encoding)
                        if raw_data.startswith("\ufeff"):
                            raw_data = raw_data.lstrip("\ufeff")
                        parsed = json.loads(raw_data)
                        if not isinstance(parsed, dict):
                            logger.warning(
                                "Remote server returned non-dict JSON structure (%s). Attempt %d/%d",
                                type(parsed).__name__,
                                attempt,
                                safe_retries,
                            )
                            if attempt < safe_retries:
                                backoff = min(60.0, safe_backoff * (2 ** min(attempt - 1, 10)))
                                time.sleep(backoff)
                                continue
                            return None
                        return parsed
                    logger.warning(
                        "Remote server returned non-200 status: %d (attempt %d/%d)",
                        resp_status,
                        attempt,
                        safe_retries,
                    )
                    if attempt < safe_retries:
                        backoff = min(60.0, safe_backoff * (2 ** min(attempt - 1, 10)))
                        time.sleep(backoff)
                        continue
                    return None
            except (
                urllib.error.URLError,
                urllib.error.HTTPError,
                TimeoutError,
                json.JSONDecodeError,
                UnicodeDecodeError,
                http.client.HTTPException,
                OSError,
                Exception,
            ) as exc:
                if hasattr(exc, "fp") and exc.fp:
                    try:
                        exc.fp.close()
                    except Exception:
                        pass
                if hasattr(exc, "close") and id(exc) not in closed_exc_ids:
                    closed_exc_ids.add(id(exc))
                    try:
                        exc.close()
                    except Exception:
                        pass
                logger.warning("Live fetch attempt %d/%d failed: %s.", attempt, safe_retries, exc)
                if attempt < safe_retries:
                    backoff = min(60.0, safe_backoff * (2 ** min(attempt - 1, 10)))
                    time.sleep(backoff)
                    continue
                logger.warning("Live fetch failed: %s. Initiating graceful fallback.", exc)
                return None
        return None

    def quarantine_corrupted_cache(
        self,
        cache_path: Union[str, Path],
        suffix: Optional[str] = None,
    ) -> Optional[Path]:
        """Quarantine a corrupted cache file by renaming it with a timestamp suffix or custom suffix."""
        return quarantine_corrupted_file(cache_path, suffix=suffix)

    def discard_corrupted_cache(self, cache_path: Union[str, Path]) -> bool:
        """Discard a corrupted cache file by removing it from disk."""
        p = Path(cache_path)
        if not p.exists():
            return False
        try:
            p.unlink()
            logger.warning("Discarded corrupted cache file: %s", p)
            return True
        except OSError as exc:
            logger.warning("Failed to discard corrupted cache file %s: %s", p, exc)
            return False

    def load_cached_payload(
        self,
        cache_path: Optional[Union[str, Path]] = None,
        validate: bool = False,
        quarantine: Optional[bool] = None,
    ) -> Optional[SubsidyPayload]:
        """Load and validate cached SubsidyPayload snapshot with corrupted file resilience.

        Hardened against:
        - Malformed/truncated JSON or invalid UTF-8 bytes.
        - Non-dictionary or missing root keys.
        - Invalid schema structures (non-list regions, missing categories).
        - Quarantined / corrupted filename markers (.corrupted, .corrupt_).
        - Degenerate cache states.

        If corruption is detected:
        - Logs warning.
        - Quarantines or discards corrupted cache gracefully if quarantine is requested.
        - Gracefully discards invalid payload in memory and returns None (triggering fresh baseline computation).
        """
        target_path = Path(cache_path) if cache_path else self.cache_fallback_path
        if not target_path:
            return None
        try:
            if not target_path.exists() or not target_path.is_file():
                return None
        except OSError:
            return None

        if is_corrupted_or_quarantined_filename(target_path):
            logger.warning("Ignoring quarantined/corrupted cache path %s", target_path)
            return None

        should_quarantine = self.quarantine_corrupted if quarantine is None else quarantine

        try:
            logger.info("Loading cached snapshot from %s", target_path)
            file_size = target_path.stat().st_size
            if file_size > MAX_CACHE_BYTES:
                raise ValueError(
                    f"Cache file exceeds maximum allowed size ({file_size} > {MAX_CACHE_BYTES}): {target_path}"
                )
            raw_bytes = target_path.read_bytes()
            if not raw_bytes or not raw_bytes.strip():
                raise ValueError(f"Cache file is empty (0 bytes): {target_path}")

            raw_str = robust_decode(raw_bytes)
            if raw_str.startswith("\ufeff"):
                raw_str = raw_str.lstrip("\ufeff")

            cached_dict = json.loads(raw_str)

            if not isinstance(cached_dict, dict):
                raise ValueError(
                    f"Cache content must be a JSON object (dict), got {type(cached_dict).__name__}"
                )

            payload = SubsidyPayload.from_dict(cached_dict)

            if validate:
                if not payload.regions or len(payload.regions) < 17:
                    raise ValueError(
                        f"Invalid cache schema: expected >= 17 regions, found {len(payload.regions) if payload.regions else 0}"
                    )
                for idx, r in enumerate(payload.regions):
                    r_cats = r.get("categories") if isinstance(r, dict) else getattr(r, "categories", None)
                    if r_cats is None or not isinstance(r_cats, dict):
                        raise ValueError(
                            f"Corrupted region record at index {idx}: missing categories dictionary"
                        )

            return payload
        except Exception as e:
            logger.warning(
                "Failed to load cache %s: %s. Gracefully discarding corrupted cache snapshot.",
                target_path,
                e,
            )
            if should_quarantine:
                self.quarantine_corrupted_cache(target_path)
            return None

    def _normalize_payload_collections(self, payload: SubsidyPayload) -> None:
        """Ensure trajectory sorting/dedup, non-empty baseline collections, and metadata counts."""
        if payload.historical_depletion_trajectory:
            seen_dates: Set[str] = set()
            sorted_pts = sorted(
                payload.historical_depletion_trajectory,
                key=lambda pt: str(getattr(pt, "date", "") or (pt.get("date", "") if isinstance(pt, dict) else "")),
            )
            deduped_history = []
            for pt in sorted_pts:
                d_val = getattr(pt, "date", "") or (pt.get("date", "") if isinstance(pt, dict) else "")
                d = str(d_val).strip() if d_val is not None else ""
                if d and d not in seen_dates:
                    seen_dates.add(d)
                    deduped_history.append(pt)
            payload.historical_depletion_trajectory = (
                deduped_history if len(deduped_history) >= 2 else build_historical_trajectory()
            )
        else:
            payload.historical_depletion_trajectory = build_historical_trajectory()

        if not payload.popular_models_matrix:
            payload.popular_models_matrix = build_popular_models()
        if not payload.alert_thresholds:
            payload.alert_thresholds = dict(DEFAULT_ALERT_THRESHOLDS)

        payload.metadata.total_regions_tracked = sum(1 for r in payload.regions if r is not None)
        total_munis = 0
        for r in payload.regions:
            if r is None:
                continue
            munis = r.get("municipalities", []) if isinstance(r, dict) else getattr(r, "municipalities", [])
            if isinstance(munis, (list, tuple)):
                total_munis += sum(1 for m in munis if m is not None)
        if total_munis > 0 or payload.metadata.total_municipalities_tracked <= 0:
            payload.metadata.total_municipalities_tracked = total_munis

    def execute_tracking_cycle(
        self,
        mock_network_failure: bool = False,
        validate_cache: Optional[bool] = None,
        quarantine_corrupted: Optional[bool] = None,
    ) -> Tuple[SubsidyPayload, bool]:
        """Run complete tracking cycle. Returns (payload, is_fallback_used)."""
        logger.info("Starting EV Subsidy tracking cycle...")

        should_validate = self.validate_cache if validate_cache is None else validate_cache
        should_quarantine = self.quarantine_corrupted if quarantine_corrupted is None else quarantine_corrupted

        live_data = None
        if not mock_network_failure and self.endpoint_url:
            live_data = self.fetch_live_updates()

        # If live_data exists and contains valid payload, use it
        if isinstance(live_data, dict) and "regions" in live_data:
            try:
                payload = SubsidyPayload.from_dict(live_data)
                if not payload.regions or len(payload.regions) < 17:
                    raise ValueError(
                        f"Invalid live data schema: expected >= 17 regions, found {len(payload.regions) if payload.regions else 0}"
                    )
                # Recalculate metrics to guarantee invariants
                for idx, r in enumerate(payload.regions):
                    payload.regions[idx] = self.update_region_metrics(r)
                payload.nationwide_summary = self.compute_nationwide_summary(payload.regions)
                self._normalize_payload_collections(payload)

                payload.metadata.generated_at = datetime.now(timezone.utc).isoformat()
                logger.info("Successfully refreshed tracking data from live endpoint.")
                return payload, False
            except Exception as e:
                logger.warning("Error parsing live data: %s. Falling back to baseline.", e)

        # Fallback to local cached file if available, otherwise built-in baseline
        payload = None
        if self.cache_fallback_path:
            try:
                if self.cache_fallback_path.exists() and self.cache_fallback_path.is_file():
                    payload = self.load_cached_payload(
                        cache_path=self.cache_fallback_path,
                        validate=should_validate,
                        quarantine=should_quarantine,
                    )
            except OSError as err:
                logger.warning("Cache fallback path inspection error: %s", err)
                payload = None

        if payload is None:
            logger.info("Generating authoritative 2026 baseline dataset.")
            payload = build_initial_baseline()

        # Update timestamp and verify metrics
        try:
            for idx, r in enumerate(payload.regions):
                payload.regions[idx] = self.update_region_metrics(r)
            payload.nationwide_summary = self.compute_nationwide_summary(payload.regions)
            self._normalize_payload_collections(payload)
            payload.metadata.generated_at = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            logger.warning("Structural anomaly updating region metrics: %s. Guaranteeing safe baseline fallback.", e)
            if should_quarantine and self.cache_fallback_path:
                self.quarantine_corrupted_cache(self.cache_fallback_path)
            payload = build_initial_baseline()
            for idx, r in enumerate(payload.regions):
                payload.regions[idx] = self.update_region_metrics(r)
            payload.nationwide_summary = self.compute_nationwide_summary(payload.regions)
            self._normalize_payload_collections(payload)
            payload.metadata.generated_at = datetime.now(timezone.utc).isoformat()

        return payload, True

    def collect_and_save(
        self,
        sync_web: bool = False,
        output_path: Optional[Union[str, Path]] = None,
        dry_run: bool = False,
        quarantine_corrupted: Optional[bool] = None,
        sync_defects: bool = False,
    ) -> SubsidyPayload:
        """Execute complete subsidy collection cycle and atomically save to disk.

        Conforms to PROJECT.md interface contract:
        SubsidyTracker.collect_and_save(
            sync_web: bool, output_path: Optional[str], dry_run: bool, sync_defects: bool
        ) -> SubsidyPayload
        """
        should_quarantine = self.quarantine_corrupted if quarantine_corrupted is None else quarantine_corrupted
        payload, fallback_used = self.execute_tracking_cycle(
            validate_cache=True,
            quarantine_corrupted=should_quarantine,
        )

        if not dry_run:
            repo_root = _find_repo_root()
            root_data_dir = repo_root / "data"
            web_src_data = repo_root / "ev-stealth-web" / "src" / "data"
            web_pub_data = repo_root / "ev-stealth-web" / "public" / "data"
            root_pub_data = repo_root / "public" / "data"

            cwd = Path.cwd()
            destinations: List[Path] = []

            if output_path:
                primary = Path(output_path)
            elif self.cache_fallback_path:
                primary = Path(self.cache_fallback_path)
            elif (cwd / "src" / "data").exists():
                primary = cwd / "src" / "data" / "ev_subsidy_data.json"
            elif (cwd / "data").exists():
                primary = cwd / "data" / "ev_subsidy_data.json"
            elif root_data_dir.exists():
                primary = root_data_dir / "ev_subsidy_data.json"
            else:
                primary = web_src_data / "ev_subsidy_data.json"

            destinations.append(primary)

            # Ensure subsidy_depletion_data.json mirror parity
            if primary.name == "ev_subsidy_data.json":
                destinations.append(primary.parent / "subsidy_depletion_data.json")
            elif primary.name == "subsidy_depletion_data.json":
                destinations.append(primary.parent / "ev_subsidy_data.json")

            if sync_web:
                web_dir_env = os.getenv("EV_TRACKER_WEB_DIR")
                if web_dir_env:
                    web_dir = Path(web_dir_env)
                    destinations.append(web_dir / "ev_subsidy_data.json")
                    destinations.append(web_dir / "subsidy_depletion_data.json")
                else:
                    destinations.append(web_src_data / "ev_subsidy_data.json")
                    destinations.append(web_src_data / "subsidy_depletion_data.json")
                    if web_pub_data.exists():
                        destinations.append(web_pub_data / "ev_subsidy_data.json")
                        destinations.append(web_pub_data / "subsidy_depletion_data.json")

                    web_data_dir = repo_root / "ev-stealth-web" / "data"
                    if web_data_dir.exists():
                        destinations.append(web_data_dir / "ev_subsidy_data.json")
                        destinations.append(web_data_dir / "subsidy_depletion_data.json")

                    if root_data_dir.exists():
                        destinations.append(root_data_dir / "ev_subsidy_data.json")
                        destinations.append(root_data_dir / "subsidy_depletion_data.json")
                    if root_pub_data.exists():
                        destinations.append(root_pub_data / "ev_subsidy_data.json")
                        destinations.append(root_pub_data / "subsidy_depletion_data.json")

            # Deduplicate destinations preserving order
            unique_destinations: List[Path] = []
            seen_paths = set()
            for dst in destinations:
                try:
                    resolved_key = str(dst.resolve())
                except (OSError, RuntimeError):
                    resolved_key = str(dst.absolute())
                if resolved_key not in seen_paths:
                    seen_paths.add(resolved_key)
                    unique_destinations.append(dst)

            primary.parent.mkdir(parents=True, exist_ok=True)
            sync_lock = primary.parent / ".subsidy_sync.lock"
            cleanup_stale_lock_files(primary.parent, max_age_seconds=3600.0)
            with FileLock(sync_lock):
                self.save_payload(payload, unique_destinations)

        if sync_defects:
            try:
                from run_tracker import sync_defect_reports

                web_dir_env = os.getenv("EV_TRACKER_WEB_DIR")
                web_dir = Path(web_dir_env) if web_dir_env else None
                sync_defect_reports(web_dir=web_dir, dry_run=dry_run, run_crawler=False)
            except Exception as e:
                logger.warning("Failed to synchronize defect reports in collect_and_save: %s", e)

        return payload

    def save_payload(
        self,
        payload: SubsidyPayload,
        destination_paths: List[Union[str, Path]],
        export_models_matrix: bool = True,
    ) -> List[Path]:
        """Atomically persist payload to all destination paths and export models matrix."""
        # Deduplicate paths preserving order
        unique_destinations: List[Path] = []
        seen_paths = set()
        for dst in destination_paths:
            target = Path(dst)
            try:
                resolved_key = str(target.resolve())
            except (OSError, RuntimeError):
                resolved_key = str(target.absolute())
            if resolved_key not in seen_paths:
                seen_paths.add(resolved_key)
                unique_destinations.append(target)

        written = atomic_write_json_multiple(payload, unique_destinations)
        for w in written:
            logger.info("Saved subsidy dataset: %s", w)

        if export_models_matrix:
            matrix_data = build_comprehensive_models_matrix()
            seen_matrix_dirs = set()
            matrix_files: List[Path] = []
            for p in unique_destinations:
                try:
                    parent_dir = Path(p).parent.resolve()
                except (OSError, RuntimeError):
                    parent_dir = Path(p).parent.absolute()
                if parent_dir not in seen_matrix_dirs:
                    seen_matrix_dirs.add(parent_dir)
                    matrix_files.append(parent_dir / "models_subsidy_matrix.json")
            if matrix_files:
                try:
                    atomic_write_json_multiple(matrix_data, matrix_files)
                    for matrix_file in matrix_files:
                        logger.info("  ✓ Saved vehicle models matrix: %s", matrix_file)
                except Exception as exc:
                    logger.warning("Failed to save models matrix to %s: %s", matrix_files, exc)

        return written

    def generate_briefing(self, payload: SubsidyPayload, fallback_used: bool = False) -> str:
        """Generate formatted executive markdown summary briefing."""
        return self.report_generator.generate_subsidy_briefing(payload, fallback_used=fallback_used)

    def group_regions(
        self,
        regions: Optional[List[Union[RegionRecord, Dict[str, Any]]]] = None,
    ) -> Dict[str, List[Any]]:
        """Group regions into metropolitan cities (8) and provinces (9)."""
        return group_regions_by_type(regions)

    def compute_regional_group_summaries(
        self,
        regions: Optional[List[Union[RegionRecord, Dict[str, Any]]]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Compute aggregate metrics for Metropolitan Cities (8) and Provinces (9)."""
        grouped = self.group_regions(regions)
        summaries: Dict[str, Dict[str, Any]] = {}
        for group_name, reg_list in grouped.items():
            tot_ann = 0
            tot_app = 0
            tot_del = 0
            for r in reg_list:
                if r is None:
                    continue
                cats = (r.get("categories") if isinstance(r, dict) else getattr(r, "categories", None)) or {}
                if not isinstance(cats, dict):
                    cats = {}
                for c in cats.values():
                    tot_ann += max(0, _safe_int_metric(_metric_val(c, "announced_units", 0), 0))
                    tot_app += max(0, _safe_int_metric(_metric_val(c, "applied_units", 0), 0))
                    tot_del += max(0, _safe_int_metric(_metric_val(c, "delivered_units", 0), 0))
            rem = calculate_remaining_units(tot_app, tot_ann)
            rate = calculate_depletion_rate(tot_app, tot_ann)
            del_rate = calculate_delivery_rate(tot_del, tot_ann)
            pending_del = calculate_pending_deliveries(tot_app, tot_del)
            waitlist = calculate_waitlist_units(tot_app, tot_ann)
            summaries[group_name] = {
                "region_count": len(reg_list),
                "total_announced_units": tot_ann,
                "total_applied_units": tot_app,
                "total_delivered_units": tot_del,
                "total_remaining_units": rem,
                "total_pending_deliveries": pending_del,
                "total_waitlist_units": waitlist,
                "depletion_rate": rate,
                "delivery_rate": del_rate,
                "status": self.evaluate_status(rate).value,
                "regions": [
                    _metric_val(r, "name_ko", "") or _metric_val(r, "region_id", "")
                    for r in reg_list
                ],
            }
        return summaries

    def predict_region_exhaustion(
        self,
        region: Union[RegionRecord, Dict[str, Any]],
        category_name: str = "passenger",
        reference_days: float = 30.0,
    ) -> Dict[str, Any]:
        """Estimate exhaustion velocity and predicted runout days for a region category."""
        if region is None:
            return {
                "category": category_name,
                "remaining_units": 0,
                "applied_units": 0,
                "daily_velocity": 0.0,
                "days_to_exhaustion": 0,
                "predicted_exhaustion_date": None,
                "status": "DEPLETED",
            }
        cats = region.get("categories") if isinstance(region, dict) else getattr(region, "categories", {})
        cat = cats.get(category_name) if isinstance(cats, dict) else None
        rem = max(0, _safe_int_metric(_metric_val(cat, "remaining_units", 0), 0))
        app = max(0, _safe_int_metric(_metric_val(cat, "applied_units", 0), 0))
        st = str(_metric_val(cat, "status", "HEALTHY") or "HEALTHY").split(".")[-1].strip().upper() or "HEALTHY"

        velocity = calculate_depletion_velocity(0, app, reference_days)
        days = predict_exhaustion_days(rem, velocity)
        pred_date = predict_exhaustion_date(rem, velocity)

        return {
            "category": category_name,
            "remaining_units": rem,
            "applied_units": app,
            "daily_velocity": velocity,
            "days_to_exhaustion": days,
            "predicted_exhaustion_date": pred_date,
            "status": st,
        }

    def get_fallback_payload(self) -> SubsidyPayload:
        """Return fresh authoritative fallback baseline dataset."""
        return generate_fallback_payload()


def build_comprehensive_models_matrix() -> List[Dict[str, Any]]:
    """Build comprehensive 2026 Korean EV models matrix (18 models) with statutory subsidy specs."""
    baseline_models = build_popular_models()
    models_dict_list: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()

    for m in baseline_models:
        m_dict = m.to_dict() if hasattr(m, "to_dict") else dict(m)
        # Ensure price_subsidy_ratio matches statutory calculation
        m_dict["price_subsidy_ratio"] = calculate_price_cap_ratio(m_dict["base_price_krw"])
        models_dict_list.append(m_dict)
        seen_ids.add(m_dict["model_id"])

    additional_models = [
        {
            "model_id": "ioniq-6-2026",
            "name_ko": "현대 아이오닉 6 롱레인지 2WD (2026)",
            "manufacturer": "현대자동차",
            "battery_type": "NCM 삼원계 (SK온 77.4kWh)",
            "battery_capacity_kwh": 77.4,
            "rated_range_km": 524,
            "base_price_krw": 52_000_000,
            "price_subsidy_ratio": 1.0,
            "national_subsidy_krw": 6_500_000,
            "regional_subsidy_samples": {
                "seoul": {"local_subsidy_krw": 1_500_000, "total_subsidy_krw": 8_000_000, "net_price_krw": 44_000_000},
                "gyeonggi_avg": {"local_subsidy_krw": 2_600_000, "total_subsidy_krw": 9_100_000, "net_price_krw": 42_900_000},
            },
        },
        {
            "model_id": "genesis-gv60-2026",
            "name_ko": "제네시스 GV60 스탠다드 2WD (2026)",
            "manufacturer": "제네시스",
            "battery_type": "NCM 삼원계 (SK온 77.4kWh)",
            "battery_capacity_kwh": 77.4,
            "rated_range_km": 451,
            "base_price_krw": 64_900_000,
            "price_subsidy_ratio": 0.5,
            "national_subsidy_krw": 3_150_000,
            "regional_subsidy_samples": {
                "seoul": {"local_subsidy_krw": 727_000, "total_subsidy_krw": 3_877_000, "net_price_krw": 61_023_000},
                "gyeonggi_avg": {"local_subsidy_krw": 1_260_000, "total_subsidy_krw": 4_410_000, "net_price_krw": 60_490_000},
            },
        },
        {
            "model_id": "bmw-i4-edrive40",
            "name_ko": "BMW i4 eDrive40 (2026)",
            "manufacturer": "BMW",
            "battery_type": "NCM 삼원계 (삼성SDI 83.9kWh)",
            "battery_capacity_kwh": 83.9,
            "rated_range_km": 429,
            "base_price_krw": 78_200_000,
            "price_subsidy_ratio": 0.5,
            "national_subsidy_krw": 2_120_000,
            "regional_subsidy_samples": {
                "seoul": {"local_subsidy_krw": 489_000, "total_subsidy_krw": 2_609_000, "net_price_krw": 75_591_000},
                "gyeonggi_avg": {"local_subsidy_krw": 848_000, "total_subsidy_krw": 2_968_000, "net_price_krw": 75_232_000},
            },
        },
        {
            "model_id": "audi-q4-e-tron",
            "name_ko": "아우디 Q4 40 e-트론 (2026)",
            "manufacturer": "아우디",
            "battery_type": "NCM 삼원계 (LG엔솔 82kWh)",
            "battery_capacity_kwh": 82.0,
            "rated_range_km": 411,
            "base_price_krw": 61_700_000,
            "price_subsidy_ratio": 0.5,
            "national_subsidy_krw": 1_980_000,
            "regional_subsidy_samples": {
                "seoul": {"local_subsidy_krw": 457_000, "total_subsidy_krw": 2_437_000, "net_price_krw": 59_263_000},
                "gyeonggi_avg": {"local_subsidy_krw": 792_000, "total_subsidy_krw": 2_772_000, "net_price_krw": 58_928_000},
            },
        },
        {
            "model_id": "polestar-4-long-range",
            "name_ko": "폴스타 4 롱레인지 싱글모터 (2026)",
            "manufacturer": "폴스타",
            "battery_type": "NCM 삼원계 (CATL 100kWh)",
            "battery_capacity_kwh": 100.0,
            "rated_range_km": 511,
            "base_price_krw": 66_900_000,
            "price_subsidy_ratio": 0.5,
            "national_subsidy_krw": 2_250_000,
            "regional_subsidy_samples": {
                "seoul": {"local_subsidy_krw": 519_000, "total_subsidy_krw": 2_769_000, "net_price_krw": 64_131_000},
                "gyeonggi_avg": {"local_subsidy_krw": 900_000, "total_subsidy_krw": 3_150_000, "net_price_krw": 63_750_000},
            },
        },
        {
            "model_id": "genesis-electrified-g80",
            "name_ko": "제네시스 일렉트리파이드 G80 (2026)",
            "manufacturer": "제네시스",
            "battery_type": "NCM 삼원계 (SK온 94.5kWh)",
            "battery_capacity_kwh": 94.5,
            "rated_range_km": 475,
            "base_price_krw": 89_190_000,
            "price_subsidy_ratio": 0.0,
            "national_subsidy_krw": 0,
            "regional_subsidy_samples": {
                "seoul": {"local_subsidy_krw": 0, "total_subsidy_krw": 0, "net_price_krw": 89_190_000},
                "gyeonggi_avg": {"local_subsidy_krw": 0, "total_subsidy_krw": 0, "net_price_krw": 89_190_000},
            },
        },
        {
            "model_id": "benz-eqe-350",
            "name_ko": "메르세데스-벤츠 EQE 350+ (2026)",
            "manufacturer": "메르세데스-벤츠",
            "battery_type": "NCM 삼원계 (CATL 90.6kWh)",
            "battery_capacity_kwh": 90.6,
            "rated_range_km": 471,
            "base_price_krw": 103_800_000,
            "price_subsidy_ratio": 0.0,
            "national_subsidy_krw": 0,
            "regional_subsidy_samples": {
                "seoul": {"local_subsidy_krw": 0, "total_subsidy_krw": 0, "net_price_krw": 103_800_000},
                "gyeonggi_avg": {"local_subsidy_krw": 0, "total_subsidy_krw": 0, "net_price_krw": 103_800_000},
            },
        },
        {
            "model_id": "porsche-taycan",
            "name_ko": "포르쉐 타이칸 (2026)",
            "manufacturer": "포르쉐",
            "battery_type": "NCM 삼원계 (LG엔솔 105kWh)",
            "battery_capacity_kwh": 105.0,
            "rated_range_km": 500,
            "base_price_krw": 129_900_000,
            "price_subsidy_ratio": 0.0,
            "national_subsidy_krw": 0,
            "regional_subsidy_samples": {
                "seoul": {"local_subsidy_krw": 0, "total_subsidy_krw": 0, "net_price_krw": 129_900_000},
                "gyeonggi_avg": {"local_subsidy_krw": 0, "total_subsidy_krw": 0, "net_price_krw": 129_900_000},
            },
        },
    ]

    for am in additional_models:
        if am["model_id"] not in seen_ids:
            am["price_subsidy_ratio"] = calculate_price_cap_ratio(am["base_price_krw"])
            models_dict_list.append(am)
            seen_ids.add(am["model_id"])

    return models_dict_list


def export_models_subsidy_matrix(target_dirs: Optional[List[Union[str, Path]]] = None) -> List[Path]:
    """Atomically export comprehensive 2026 EV models subsidy matrix (>=15 models) to target directories."""
    matrix_data = build_comprehensive_models_matrix()
    if target_dirs is None:
        repo_root = _find_repo_root()
        cwd = Path.cwd()
        candidates = [
            repo_root / "data",
            repo_root / "ev-stealth-web" / "data",
            repo_root / "ev-stealth-web" / "src" / "data",
            repo_root / "ev-stealth-web" / "public" / "data",
            repo_root / "public" / "data",
            cwd / "data",
            cwd / "ev-stealth-web" / "src" / "data",
            cwd / "src" / "data",
            cwd.parent / "data",
        ]
        seen_dirs = set()
        target_dirs = []
        for c in candidates:
            if c.exists():
                try:
                    r_key = str(c.resolve())
                except (OSError, RuntimeError):
                    r_key = str(c.absolute())
                if r_key not in seen_dirs:
                    seen_dirs.add(r_key)
                    target_dirs.append(c)
        if not target_dirs:
            target_dirs = [repo_root / "data"]

    dest_files: List[Path] = []
    seen_files: Set[str] = set()
    for d in target_dirs:
        try:
            dest_file = Path(d).resolve() / "models_subsidy_matrix.json"
        except (OSError, RuntimeError):
            dest_file = Path(d).absolute() / "models_subsidy_matrix.json"
        key = str(dest_file)
        if key not in seen_files:
            seen_files.add(key)
            dest_files.append(dest_file)

    written_paths: List[Path] = []
    if dest_files:
        try:
            written_paths = atomic_write_json_multiple(matrix_data, dest_files)
            for dest_file in written_paths:
                logger.info("  ✓ Successfully exported models matrix to %s", dest_file)
        except Exception:
            for dest_file in dest_files:
                try:
                    w = atomic_write_json(matrix_data, dest_file)
                    written_paths.append(w)
                    logger.info("  ✓ Successfully exported models matrix to %s", dest_file)
                except Exception as exc:
                    logger.warning("Failed to export models matrix to %s: %s", dest_file, exc)

    return written_paths


__all__ = [
    "SubsidyTracker",
    "get_baseline_regions",
    "get_baseline_models",
    "get_baseline_thresholds",
    "get_baseline_dataset",
    "calculate_depletion_rate",
    "calculate_remaining_units",
    "calculate_waitlist_units",
    "calculate_delivery_rate",
    "calculate_pending_deliveries",
    "calculate_depletion_velocity",
    "predict_exhaustion_days",
    "predict_exhaustion_date",
    "is_depletion_over_exhausted",
    "classify_alert_tier",
    "calculate_price_cap_ratio",
    "calculate_net_subsidy",
    "build_comprehensive_models_matrix",
    "export_models_subsidy_matrix",
    "classify_region_group",
    "is_metropolitan_city",
    "is_province",
    "group_regions_by_type",
    "group_regions_by_category",
    "generate_fallback_payload",
    "METROPOLITAN_CITIES",
    "PROVINCES",
    "METROPOLITAN_CITY_CODES",
    "PROVINCE_CODES",
    "REGIONAL_GROUP_METROPOLITAN",
    "REGIONAL_GROUP_PROVINCES",
    "_metric_val",
]
