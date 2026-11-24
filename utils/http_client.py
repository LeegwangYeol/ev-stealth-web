"""
Robust, Rate-Limited HTTP Client for Web Scraping and Community Forum Data Mining.
Pure Python Standard Library implementation with User-Agent rotation, configurable
jitter (1.5s~3.5s), exponential backoff, cookie jar session handling, and error logging.
"""

from __future__ import annotations

from collections import OrderedDict
import datetime
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
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Set up dedicated logger
logger = logging.getLogger("SafeHttpClient")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# User-Agent Pool (Modern Desktop browsers only - prevents mobile redirect loops on Korean forums)
USER_AGENT_POOL = [
    # Chrome macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    # Safari macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    # Firefox macOS & Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.6; rv:129.0) Gecko/20100101 Firefox/129.0",
    # Edge Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0",
]

# Safe memory bounds to prevent memory leaks and out-of-memory crashes
MAX_RESPONSE_BYTES: int = 10 * 1024 * 1024  # 10MB per HTTP response
MAX_COOKIEJAR_ENTRIES: int = 500  # Prune cookie jar beyond 500 entries

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


_NAT64_WELL_KNOWN_PREFIX = ipaddress.IPv6Network("64:ff9b::/96")
_NAT64_LOCAL_PREFIX = ipaddress.IPv6Network("64:ff9b:1::/48")
_CGNAT_PREFIX = ipaddress.IPv4Network("100.64.0.0/10")
_ORCHID_V2_PREFIX = ipaddress.IPv6Network("2001:20::/28")
_SRV6_SID_PREFIX = ipaddress.IPv6Network("5f00::/16")
_IPV4_TRANSLATED_PREFIX = ipaddress.IPv6Network("::ffff:0:0/96")
_IPV4_COMPAT_PREFIX = ipaddress.IPv6Network("::/96")
_RE_URL_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


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
    # Check IPv4-mapped / translated / transition IPv6 addresses
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
        # NAT64, IPv4-translated (SIIT), IPv4-compatible, and ISATAP embed IPv4 in the lowest 32 bits
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
    # Cloud metadata IPs (AWS / GCP / Azure / Alibaba)
    if str(ip) in ("169.254.169.254", "100.100.100.200"):
        return False
    return True


def is_safe_url(
    url: str,
    allow_private_ips: bool = False,
    allowed_ports: Optional[Set[int]] = None,
) -> Tuple[bool, str]:
    """Verify URL against SSRF attacks (private subnets, cloud metadata, non-HTTP schemes).

    Returns:
        Tuple[bool, str]: (is_safe, failure_reason)
    """
    if not url or not isinstance(url, str):
        return False, "Empty or invalid URL"

    url_str = url.strip()
    if not url_str:
        return False, "Empty URL"
    if _RE_URL_CONTROL_CHARS.search(url_str):
        return False, "SSRF blocked: URL contains control characters"

    try:
        parsed = urllib.parse.urlsplit(url_str)
    except Exception as e:
        return False, f"URL parsing error: {e}"

    # 1. Scheme validation: strictly http or https
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        return False, f"Disallowed URL scheme: {scheme!r} (only http/https allowed)"

    if "\\" in (parsed.netloc or ""):
        return False, "SSRF blocked: Backslash in URL authority"
    if parsed.username is not None or parsed.password is not None:
        return False, "SSRF blocked: Userinfo credentials not allowed in URL"

    # 2. Hostname extraction
    hostname = parsed.hostname
    if not hostname:
        return False, "Missing hostname in URL"

    host_lower = hostname.lower().strip().rstrip(".")
    if not host_lower:
        return False, "Missing hostname in URL"
    if any(ch.isspace() for ch in host_lower):
        return False, "SSRF blocked: Whitespace in hostname"

    if allow_private_ips:
        return True, "Private IPs allowed by configuration"

    if "%" in host_lower:
        return False, "SSRF blocked: IPv6 zone ID not allowed"

    # Normalize Unicode / fullwidth IDN hostnames to canonical ASCII before literal host/IP checks
    if not host_lower.isascii():
        try:
            host_lower = host_lower.encode("idna").decode("ascii").lower().strip().rstrip(".")
        except UnicodeError as e:
            return False, f"SSRF blocked: Invalid IDNA hostname ({e})"
        if not host_lower:
            return False, "Missing hostname in URL"

    # 3. Check disallowed hostnames & suffixes
    if host_lower in DISALLOWED_HOSTS:
        return False, f"SSRF blocked: Disallowed hostname '{host_lower}'"

    for suffix in DISALLOWED_HOST_SUFFIXES:
        if host_lower.endswith(suffix):
            return False, f"SSRF blocked: Hostname '{host_lower}' matches disallowed internal suffix '{suffix}'"

    # 4. Port validation (accessing parsed.port raises ValueError on invalid/out-of-range ports)
    ports_set = allowed_ports if allowed_ports is not None else STANDARD_SAFE_PORTS
    try:
        port = parsed.port
    except ValueError as e:
        return False, f"SSRF blocked: Invalid port in URL ({e})"
    effective_port = port if port is not None else (443 if scheme == "https" else 80)
    if effective_port not in ports_set:
        return False, f"SSRF blocked: Disallowed port {effective_port}"

    # 5. IP Address Check (literal IP, octal/hex/decimal representations)
    try:
        ip = ipaddress.ip_address(host_lower)
        if not is_safe_ip(ip):
            return False, f"SSRF blocked: Unsafe IP address {ip}"
        return True, "Safe public IP"
    except ValueError:
        pass

    # Socket aton for octal/hex/decimal encoded IPv4 (e.g. 0177.0.0.1, 2130706433, 0x7f000001)
    try:
        packed = socket.inet_aton(host_lower)
        ip4 = ipaddress.IPv4Address(packed)
        if not is_safe_ip(ip4):
            return False, f"SSRF blocked: Unsafe encoded IP address {ip4}"
        return True, "Safe public IP"
    except (OSError, ValueError):
        pass

    # 6. DNS Resolution validation (prevent DNS rebinding or custom domains pointing to private IPs)
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
        # Domain cannot be resolved via DNS (e.g. offline CI test environment).
        # Allow domain name to proceed to opener/socket handler.
        pass
    except Exception as e:
        logger.debug(f"DNS check notice for {host_lower}: {e}")

    return True, "Safe URL"


def robust_decode(raw_bytes: Union[bytes, bytearray, memoryview, str], declared_encoding: Optional[str] = None) -> str:
    """Decode raw bytes with graceful fallback across Korean and universal charsets.
    Tries declared encoding, utf-8, cp949, euc-kr, and latin-1.
    """
    if isinstance(raw_bytes, str):
        return raw_bytes
    if not raw_bytes:
        return ""
    if isinstance(raw_bytes, memoryview):
        raw_bytes = bytes(raw_bytes)
    elif isinstance(raw_bytes, bytearray):
        raw_bytes = bytes(raw_bytes)
    elif not isinstance(raw_bytes, bytes):
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


def encode_euc_kr_query(param: Union[str, Dict[str, Any], None]) -> str:
    """
    Percent-encode string or dictionary parameters into EUC-KR / CP949 for Korean forums
    like BobaeDream that require non-UTF-8 URL queries.
    """
    if not param:
        return ""
    if isinstance(param, str):
        try:
            return urllib.parse.quote(param.encode("euc-kr"))
        except UnicodeEncodeError:
            return urllib.parse.quote(param.encode("cp949", errors="replace"))

    if not isinstance(param, dict):
        return ""

    pairs = []
    for k, v in param.items():
        k_str = urllib.parse.quote(str(k))
        v_str = str(v)
        try:
            v_enc = urllib.parse.quote(v_str.encode("euc-kr"))
        except UnicodeEncodeError:
            v_enc = urllib.parse.quote(v_str.encode("cp949", errors="replace"))
        pairs.append(f"{k_str}={v_enc}")
    return "&".join(pairs)


_RE_HTML_COMMENT = re.compile(r"<!--.*?-->", flags=re.DOTALL)
_RE_HTML_SCRIPT_STYLE = re.compile(r"<(script|style)[^>]*>(?:.*?</\1>|.*$)", flags=re.DOTALL | re.IGNORECASE)
_RE_HTML_BLOCK_TAGS = re.compile(r"<(br|p|/p|div|/div|li|/li|h\d|/h\d|tr|/tr|dt|/dt|dd|/dd)[^>]*>", flags=re.IGNORECASE)
_RE_HTML_TAGS = re.compile(r"<[^>]+>")
_RE_HTML_TRAILING = re.compile(r"<[a-zA-Z/][^<]*$")
_RE_SPACES = re.compile(r"[ \t]+")
_RE_CHARSET = re.compile(r'charset=["\']?([\w\-]+)', flags=re.IGNORECASE)
_RE_META_CHARSET = re.compile(r'<meta[^>]+charset=["\']?([\w\-]+)', flags=re.IGNORECASE)
_RE_META_HTTP = re.compile(
    r'<meta[^>]+http-equiv=["\']?content-type["\']?[^>]+content=["\'][^"\']*charset=([\w\-]+)',
    flags=re.IGNORECASE,
)
_RE_HTTP_METHOD = re.compile(r"^[A-Z][A-Z0-9_-]*$")


def clean_html_text(raw_html: Union[str, bytes, Any]) -> str:
    """
    Strip HTML tags, scripts, styles, decode HTML entities, and normalize whitespace.
    Resilient against malformed, unclosed, or corrupt DOM snippets, bytes, and special unicode.
    """
    if raw_html is None:
        return ""
    if isinstance(raw_html, bytes):
        raw_html = robust_decode(raw_html)
    elif not isinstance(raw_html, str):
        return ""
    if not raw_html:
        return ""

    # Remove null bytes and carriage controls
    cleaned = raw_html.replace("\x00", " ")
    # Remove HTML comments (bound scan to last '-->' to prevent O(N^2) ReDoS on unclosed '<!--')
    last_comment_end = cleaned.rfind("-->")
    if last_comment_end != -1:
        end_idx = last_comment_end + 3
        cleaned = _RE_HTML_COMMENT.sub(" ", cleaned[:end_idx]) + cleaned[end_idx:]
    # Remove script and style elements (handling unclosed tags gracefully)
    cleaned = _RE_HTML_SCRIPT_STYLE.sub(" ", cleaned)
    # Replace block level tags with newlines (bound scan to last '>' to prevent O(N^2) backtracking)
    last_gt = cleaned.rfind(">")
    if last_gt != -1:
        end_idx = last_gt + 1
        cleaned = _RE_HTML_BLOCK_TAGS.sub("\n", cleaned[:end_idx]) + cleaned[end_idx:]
    # Remove remaining HTML tags (bound scan to last '>' to prevent O(N^2) backtracking)
    last_gt = cleaned.rfind(">")
    if last_gt != -1:
        end_idx = last_gt + 1
        cleaned = _RE_HTML_TAGS.sub(" ", cleaned[:end_idx]) + cleaned[end_idx:]
    # Handle unclosed tag brackets at end of string
    cleaned = _RE_HTML_TRAILING.sub(" ", cleaned)
    # Decode HTML entities (&amp;, &lt;, etc.)
    cleaned = html.unescape(cleaned)
    if "&" in cleaned:
        cleaned = html.unescape(cleaned)
    # Normalize special unicode spaces
    cleaned = (
        cleaned.replace("\xa0", " ")
        .replace("\u200b", "")
        .replace("\ufeff", "")
        .replace("\u3000", " ")
    )
    # Collapse multiple whitespace characters on each line and drop blank lines
    lines = [_RE_SPACES.sub(" ", line).strip() for line in cleaned.splitlines()]
    return "\n".join([line for line in lines if line])


def _normalize_timeout(val: Any, default: float) -> float:
    """Return a finite positive timeout float, or default."""
    if val is None or isinstance(val, bool):
        return default
    try:
        num = float(val)
        if math.isfinite(num) and num > 0:
            return num
    except (ValueError, TypeError, OverflowError):
        pass
    return default


def _resolve_timeouts(
    timeout: Any,
    connect_timeout: Any,
    read_timeout: Any,
    default_connect: float = 5.0,
    default_read: float = 15.0,
) -> Tuple[float, float]:
    """Resolve separate finite positive (connect_timeout, read_timeout) pair."""
    tuple_conn: Any = None
    tuple_read: Any = None
    if isinstance(timeout, (tuple, list)) and len(timeout) >= 2:
        tuple_conn = timeout[0]
        tuple_read = timeout[1]
    elif timeout is not None and not isinstance(timeout, (tuple, list, bool)):
        scalar = _normalize_timeout(timeout, -1.0)
        if scalar > 0:
            tuple_conn = min(5.0, scalar)
            tuple_read = scalar

    eff_conn = _normalize_timeout(connect_timeout, _normalize_timeout(tuple_conn, default_connect))
    eff_read = _normalize_timeout(read_timeout, _normalize_timeout(tuple_read, default_read))
    return eff_conn, eff_read


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
        self._conn_timeout = _normalize_timeout(connect_timeout, 5.0)
        self._read_timeout = _normalize_timeout(read_timeout, 15.0)
        self._allow_private_ips = bool(allow_private_ips)
        super().__init__(*args, **kwargs)

    def connect(self):
        self.sock = _create_safe_connection(
            (self.host, self.port),
            self._conn_timeout,
            self.source_address,
            allow_private_ips=self._allow_private_ips,
        )
        if self._read_timeout is not None:
            self.sock.settimeout(self._read_timeout)


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
        self._conn_timeout = _normalize_timeout(connect_timeout, 5.0)
        self._read_timeout = _normalize_timeout(read_timeout, 15.0)
        self._allow_private_ips = bool(allow_private_ips)
        self._allowed_ports = set(allowed_ports) if allowed_ports is not None else None
        super().__init__(*args, **kwargs)

    def connect(self):
        if self._tunnel_host and not self._allow_private_ips:
            tunnel_host = str(self._tunnel_host).strip()
            if ":" in tunnel_host and not tunnel_host.startswith("["):
                tunnel_host_fmt = f"[{tunnel_host}]"
            else:
                tunnel_host_fmt = tunnel_host
            tunnel_port = getattr(self, "_tunnel_port", None)
            port_suffix = f":{tunnel_port}" if tunnel_port is not None else ""
            is_safe, reason = is_safe_url(
                f"https://{tunnel_host_fmt}{port_suffix}",
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
        if self._read_timeout is not None:
            self.sock.settimeout(self._read_timeout)
        if self._tunnel_host:
            self._tunnel()
        server_hostname = (self._tunnel_host or self.host) if ssl.HAS_SNI else None
        self.sock = self._context.wrap_socket(self.sock, server_hostname=server_hostname)


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
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_req is not None:
            # Strip sensitive credentials on cross-origin redirects (fail-safe on parse errors)
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
                strip_credentials = (old_origin != new_origin)
                strip_referer = (old_scheme == "https" and new_scheme == "http")
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
        self._connect_timeout = _normalize_timeout(connect_timeout, 5.0)
        self._read_timeout = _normalize_timeout(read_timeout, 15.0)
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
        self._connect_timeout = _normalize_timeout(connect_timeout, 5.0)
        self._read_timeout = _normalize_timeout(read_timeout, 15.0)
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
    ):
        try:
            ft = int(failure_threshold) if failure_threshold is not None and not isinstance(failure_threshold, bool) else 3
        except (ValueError, TypeError, OverflowError):
            ft = 3
        self.failure_threshold = max(1, ft)
        self.cooldown_seconds = _normalize_timeout(cooldown_seconds, 30.0)
        self.cooldown_seconds = max(0.01, self.cooldown_seconds)
        try:
            hp = int(half_open_max_probes) if half_open_max_probes is not None and not isinstance(half_open_max_probes, bool) else 1
        except (ValueError, TypeError, OverflowError):
            hp = 1
        self.half_open_max_probes = max(1, hp)
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
                    return parsed.hostname.lower().rstrip(".")
            except Exception:
                pass
        try:
            ipaddress.ip_address(s.strip("[]"))
            return s.strip("[]").lower()
        except ValueError:
            pass
        try:
            parsed = urllib.parse.urlsplit("//" + s)
            if parsed.hostname:
                return parsed.hostname.lower().rstrip(".")
        except Exception:
            pass
        return s.lower().split(":")[0].split("/")[0].rstrip(".")

    def record_probe(self, url_or_host: str) -> None:
        """Record that a canary probe is in-flight for this host during HALF_OPEN state."""
        host = self._extract_host(url_or_host)
        if not host:
            return
        with self._lock:
            info = self._hosts.get(host)
            if info and info.get("state") == CircuitBreakerState.HALF_OPEN:
                info["probe_count"] = info.get("probe_count", 0) + 1

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

    def acquire_request_slot(self, url_or_host: str) -> Tuple[bool, bool]:
        """Atomically check availability and reserve a HALF_OPEN probe slot if applicable.

        Returns:
            Tuple[bool, bool]: (is_available, is_half_open_probe)
        """
        host = self._extract_host(url_or_host)
        if not host:
            return True, False
        with self._lock:
            info = self._hosts.get(host)
            if not info:
                return True, False
            state = info.get("state", CircuitBreakerState.CLOSED)
            if state == CircuitBreakerState.CLOSED:
                return True, False
            now = time.time()
            if state == CircuitBreakerState.OPEN:
                if now >= info.get("tripped_until", 0.0):
                    info["state"] = CircuitBreakerState.HALF_OPEN
                    info["probe_count"] = 1
                    return True, True
                return False, False
            if state == CircuitBreakerState.HALF_OPEN:
                probes = info.get("probe_count", 0)
                if probes < self.half_open_max_probes:
                    info["probe_count"] = probes + 1
                    return True, True
                return False, False
            return True, False

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
            if retry_after is not None and not isinstance(retry_after, bool):
                try:
                    ra_val = float(retry_after)
                    if math.isfinite(ra_val) and ra_val > 0:
                        cooldown = max(cooldown, ra_val)
                except (ValueError, TypeError, OverflowError):
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
    Safe and polite HTTP client designed to avoid anti-bot detection and handle rate limits.
    Features:
      - Uniform random jitter between requests (default 1.5s ~ 3.5s)
      - User-Agent pool rotation & customizable session headers
      - Explicit connect and read network timeouts
      - Exponential backoff retry on HTTP 429, 403, 408, 5xx, or network disconnects
      - Fault-tolerant error recovery (URLError, RemoteDisconnected, IncompleteRead, SSLError, gaierror)
      - Partial response salvage on IncompleteRead disconnects
      - Resilient caching and fallback to cached data when remote endpoints are unreachable or return 5xx errors
      - Persistent CookieJar session management with auto-pruning to prevent memory leaks
      - Charset auto-detection with robust decoding fallback
      - Bounded response stream reading and socket/file-descriptor resource cleanup
    """

    def __init__(
        self,
        min_delay: float = 1.5,
        max_delay: float = 3.5,
        max_retries: int = 3,
        timeout: Union[float, Tuple[float, float]] = 15.0,
        enable_jitter: bool = True,
        opener: Optional[urllib.request.OpenerDirector] = None,
        cookie_jar: Optional[http.cookiejar.CookieJar] = None,
        max_response_size: int = MAX_RESPONSE_BYTES,
        max_cookies: int = MAX_COOKIEJAR_ENTRIES,
        default_headers: Optional[Dict[str, str]] = None,
        user_agent: Optional[str] = None,
        rotate_user_agent: bool = True,
        backoff_factor: float = 1.5,
        max_backoff: float = 30.0,
        verify_ssl: bool = True,
        connect_timeout: Optional[float] = None,
        read_timeout: Optional[float] = None,
        enable_cache: bool = True,
        cache_fallback: bool = True,
        cache_dir: Optional[str] = None,
        failure_threshold: int = 3,
        circuit_cooldown: float = 30.0,
        cooldown_seconds: Optional[float] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        allow_private_ips: bool = False,
        allowed_ports: Optional[Set[int]] = None,
    ):
        self.min_delay = _normalize_timeout(min_delay, 0.0) if min_delay != 0 else 0.0
        self.max_delay = _normalize_timeout(max_delay, 0.0) if max_delay != 0 else 0.0
        try:
            self.max_retries = max(1, int(max_retries)) if max_retries is not None and not isinstance(max_retries, bool) else 3
        except (ValueError, TypeError, OverflowError):
            self.max_retries = 3
        self.timeout = timeout
        self.enable_jitter = enable_jitter
        try:
            self.max_response_size = max(0, int(max_response_size)) if max_response_size is not None and not isinstance(max_response_size, bool) else MAX_RESPONSE_BYTES
        except (ValueError, TypeError, OverflowError):
            self.max_response_size = MAX_RESPONSE_BYTES
        try:
            self.max_cookies = max(0, int(max_cookies)) if max_cookies is not None and not isinstance(max_cookies, bool) else MAX_COOKIEJAR_ENTRIES
        except (ValueError, TypeError, OverflowError):
            self.max_cookies = MAX_COOKIEJAR_ENTRIES
        self.default_headers = dict(default_headers) if default_headers else {}
        self.user_agent = user_agent
        self.rotate_user_agent = rotate_user_agent
        self.backoff_factor = _normalize_timeout(backoff_factor, 1.5)
        self.max_backoff = _normalize_timeout(max_backoff, 30.0)
        self.verify_ssl = verify_ssl
        self.enable_cache = enable_cache
        self.cache_fallback = cache_fallback
        self.allow_private_ips = bool(allow_private_ips)
        self.allowed_ports = set(allowed_ports) if allowed_ports is not None else None
        self.request_count = 0
        self.last_request_time = 0.0
        self._rate_limited_until = 0.0
        self.last_response_from_cache = False
        self._rate_lock = threading.Lock()
        self._cache_lock = threading.Lock()
        self._cookie_lock = threading.Lock()
        self._memory_cache: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        eff_cooldown = cooldown_seconds if cooldown_seconds is not None else circuit_cooldown
        self.circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=failure_threshold,
            cooldown_seconds=eff_cooldown,
        )

        # Resolve explicit finite positive connect and read timeouts
        self._connect_timeout, self._read_timeout = _resolve_timeouts(
            timeout, connect_timeout, read_timeout, default_connect=5.0, default_read=15.0
        )

        # Dedicated session UA if rotation is disabled
        self._session_user_agent = user_agent or self.get_random_user_agent()

        # Cache directory setup
        if cache_dir:
            self.cache_dir = cache_dir
        else:
            candidate_cache = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", ".cache", "http"
            )
            self.cache_dir = candidate_cache

        # Session cookie jar
        self.cookie_jar = cookie_jar if cookie_jar is not None else http.cookiejar.CookieJar()
        if opener is not None:
            self.opener = opener
        else:
            cookie_processor = urllib.request.HTTPCookieProcessor(self.cookie_jar)
            redirect_handler = SafeRedirectHandler(
                allow_private_ips=self.allow_private_ips,
                allowed_ports=self.allowed_ports,
            )
            if not self.verify_ssl:
                ssl_ctx = ssl.create_default_context()
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE
                https_handler = ResilientHTTPSHandler(
                    connect_timeout=self._connect_timeout,
                    read_timeout=self._read_timeout,
                    context=ssl_ctx,
                    allow_private_ips=self.allow_private_ips,
                    allowed_ports=self.allowed_ports,
                )
            else:
                https_handler = ResilientHTTPSHandler(
                    connect_timeout=self._connect_timeout,
                    read_timeout=self._read_timeout,
                    allow_private_ips=self.allow_private_ips,
                    allowed_ports=self.allowed_ports,
                )
            http_handler = ResilientHTTPHandler(
                connect_timeout=self._connect_timeout,
                read_timeout=self._read_timeout,
                allow_private_ips=self.allow_private_ips,
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
        # 1. In-memory cache
        with self._cache_lock:
            if key in self._memory_cache:
                self._memory_cache.move_to_end(key)
                entry = self._memory_cache[key]
                return entry.get("status", 200), entry.get("text", ""), entry.get("raw", b"")

        # 2. Disk cache
        if self.cache_dir:
            file_path = os.path.join(self.cache_dir, f"{key}.json")
            if os.path.isfile(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if not isinstance(data, dict):
                        return None
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
        raw_bytes_safe = bytes(raw_bytes) if raw_bytes is not None else b""
        entry = {
            "status": int(status_code),
            "text": str(decoded_text),
            "raw": raw_bytes_safe,
            "time": time.time(),
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
                temp_fd, temp_path = tempfile.mkstemp(
                    dir=self.cache_dir,
                    prefix=f".tmp_cache_{os.getpid()}_{threading.get_ident()}_{uuid.uuid4().hex[:8]}_",
                    suffix=".json",
                )
                payload = {
                    "url": str(url),
                    "status": int(status_code),
                    "text": str(decoded_text),
                    "raw_hex": raw_bytes_safe.hex(),
                    "time": time.time(),
                }
                with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                    json.dump(payload, f)
                    f.flush()
                    os.fsync(f.fileno())
                try:
                    os.chmod(temp_path, 0o644)
                except OSError:
                    pass
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
        with self._cookie_lock:
            replaced = False
            if hasattr(self.cookie_jar, "clear"):
                try:
                    self.cookie_jar.clear()
                except Exception:
                    self.cookie_jar = http.cookiejar.CookieJar()
                    replaced = True
            else:
                self.cookie_jar = http.cookiejar.CookieJar()
                replaced = True
            if replaced and hasattr(self.opener, "handlers"):
                for h in getattr(self.opener, "handlers", []):
                    if isinstance(h, urllib.request.HTTPCookieProcessor):
                        h.cookiejar = self.cookie_jar

    def get_cookie_dict(self) -> Dict[str, str]:
        """Return all cookies stored in the session cookie jar as a dictionary."""
        cookie_dict: Dict[str, str] = {}
        with self._cookie_lock:
            if self.cookie_jar is not None:
                try:
                    for c in list(self.cookie_jar):
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
        """Safely release underlying resources on garbage collection."""
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
        """Pick a modern browser User-Agent from pool, optionally excluding the specified UA."""
        pool = USER_AGENT_POOL if USER_AGENT_POOL else [DEFAULT_FALLBACK_USER_AGENT]
        if exclude and len(pool) > 1:
            candidates = [ua for ua in pool if ua != exclude]
            if candidates:
                return random.choice(candidates)
        return random.choice(pool)

    def _sleep_with_jitter(self):
        """Perform polite delay with randomized jitter between requests."""
        # Prune expired cookies to prevent unbounded memory growth
        should_clear_cookies = False
        with self._cookie_lock:
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
                    should_clear_cookies = True
            except Exception:
                pass
        if should_clear_cookies:
            self.clear_cookies()

        min_d = max(0.0, float(min(self.min_delay, self.max_delay)))
        max_d = max(0.0, float(max(self.min_delay, self.max_delay)))

        if not self.enable_jitter or max_d <= 0:
            with self._rate_lock:
                self.last_request_time = time.time()
                self.request_count += 1
            return

        sleep_for = 0.0
        with self._rate_lock:
            now = time.time()
            # Proactive rate-limit cooldown: if recently throttled by HTTP 429, respect backoff
            if self._rate_limited_until > 0 and now < self._rate_limited_until:
                wait_sec = (self._rate_limited_until - now) + random.uniform(0.5, 1.5)
                logger.info(f"Proactive rate-limit protection: sleeping {wait_sec:.2f}s before next request...")
                self._rate_limited_until = 0.0
                sleep_for += wait_sec

            # Prolonged cooldown pause every 20 requests to protect rate limits
            if self.request_count > 0 and self.request_count % 20 == 0:
                extra_cooldown = random.uniform(4.0, 7.0)
                logger.info(f"Rate protection cooldown after {self.request_count} requests. Sleeping {extra_cooldown:.2f}s...")
                sleep_for += extra_cooldown

            elapsed = (now + sleep_for) - self.last_request_time
            target_delay = random.uniform(min_d, max_d)
            if elapsed < target_delay:
                sleep_for += target_delay - elapsed

            self.last_request_time = now + sleep_for
            self.request_count += 1

        if sleep_for > 0:
            time.sleep(sleep_for)

    def warm_up_session(self, base_url: str, referer: Optional[str] = None) -> bool:
        """
        Send a lightweight request to the base URL to collect initial session cookies.
        """
        if not base_url or not isinstance(base_url, str) or not base_url.strip():
            logger.info(f"Warming up session on: {base_url}")
            logger.info("Session warmed up (status 0). Cookies in jar: 0")
            return False

        logger.info(f"Warming up session on: {base_url}")
        try:
            status, _, _ = self.request(base_url, method="GET", referer=referer)
            logger.info(f"Session warmed up (status {status}). Cookies in jar: {len(self.cookie_jar)}")
            return status == 200
        except Exception as e:
            logger.warning(f"Session warm-up notice on {base_url}: {e}")
            return False

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
        Perform an HTTP request with rate-limiting, headers, exponential backoff retries,
        automatic charset decoding, and bounded memory read safety.

        Returns:
            Tuple[int, str, bytes]: (status_code, decoded_text, raw_bytes)
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

        method_upper = (method or "GET").strip().upper() or "GET"
        if not _RE_HTTP_METHOD.match(method_upper):
            logger.warning(f"Invalid HTTP method rejected: {method!r}")
            return 0, "", b""
        is_cacheable_method = method_upper == "GET"

        # Host-level Circuit Breaker guard (atomic check + HALF_OPEN probe reservation)
        cb_allowed, is_half_open_probe = self.circuit_breaker.acquire_request_slot(norm_url)
        if not cb_allowed:
            logger.warning(
                f"Circuit breaker is OPEN for {norm_url} (tripped due to repeated 403/429/503 errors). "
                f"Fast-failing request."
            )
            if is_cacheable_method and self.cache_fallback:
                cached = self.get_cached_response(norm_url)
                if cached is not None:
                    logger.warning(
                        f"Circuit breaker OPEN for {norm_url}. Falling back to cached response."
                    )
                    self.last_response_from_cache = True
                    return cached
            return 503, "", b""

        self.last_response_from_cache = False
        self._sleep_with_jitter()

        def _sanitize_header_value(val: Any) -> str:
            return str(val).replace("\r", "").replace("\n", "").replace("\x00", "")

        active_ua = _sanitize_header_value(
            self.user_agent
            or (self.get_random_user_agent() if self.rotate_user_agent else self._session_user_agent)
        )
        req_headers = {
            "User-Agent": active_ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "identity",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Upgrade-Insecure-Requests": "1",
        }
        if self.default_headers:
            for k, v in self.default_headers.items():
                if v is None or not str(k).strip():
                    continue
                clean_k = _sanitize_header_value(k).strip()
                if not clean_k or ":" in clean_k:
                    continue
                matching_keys = [ek for ek in req_headers if ek.lower() == clean_k.lower()]
                for mk in matching_keys:
                    del req_headers[mk]
                req_headers[clean_k] = _sanitize_header_value(v)
        if referer:
            for mk in [ek for ek in req_headers if ek.lower() == "referer"]:
                del req_headers[mk]
            req_headers["Referer"] = _sanitize_header_value(referer)
        if headers:
            for k, v in headers.items():
                if v is None or not str(k).strip():
                    continue
                clean_k = _sanitize_header_value(k).strip()
                if not clean_k or ":" in clean_k:
                    continue
                # Case-insensitive update to avoid duplicate headers like User-Agent vs user-agent
                matching_keys = [ek for ek in req_headers if ek.lower() == clean_k.lower()]
                for mk in matching_keys:
                    del req_headers[mk]
                req_headers[clean_k] = _sanitize_header_value(v)

        has_custom_ua = bool(
            self.user_agent
            or (self.default_headers and any(k.lower() == "user-agent" for k in self.default_headers))
            or (headers and any(k.lower() == "user-agent" for k in headers))
        )

        payload_bytes: Optional[bytes] = None
        if data is not None:
            if isinstance(data, dict):
                payload_bytes = urllib.parse.urlencode(data).encode("utf-8")
                if not any(k.lower() == "content-type" for k in req_headers):
                    req_headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
            elif isinstance(data, bytes):
                payload_bytes = data
            elif isinstance(data, str):
                payload_bytes = data.encode("utf-8")

        # Resolve explicit connect and read timeouts for this specific request
        eff_connect_timeout, eff_read_timeout = _resolve_timeouts(
            timeout,
            connect_timeout,
            read_timeout,
            default_connect=self._connect_timeout,
            default_read=self._read_timeout,
        )

        req_timeout = eff_read_timeout

        try:
            eff_retries = (
                max(1, int(self.max_retries))
                if self.max_retries is not None and not isinstance(self.max_retries, bool)
                else 3
            )
        except (ValueError, TypeError, OverflowError):
            eff_retries = 3

        for attempt in range(1, eff_retries + 1):
            if attempt > 1 and self.rotate_user_agent and not has_custom_ua:
                current_ua = req_headers.get("User-Agent")
                req_headers["User-Agent"] = self.get_random_user_agent(exclude=current_ua)
            try:
                req = urllib.request.Request(
                    norm_url,
                    data=payload_bytes,
                    headers=req_headers,
                    method=method_upper,
                )
                req._connect_timeout = eff_connect_timeout
                req._read_timeout = eff_read_timeout
                resp = self.opener.open(req, timeout=req_timeout)
                try:
                    status_code = resp.getcode()

                    if hasattr(resp, "fp") and resp.fp and hasattr(resp.fp, "raw") and hasattr(resp.fp.raw, "_sock"):
                        try:
                            resp.fp.raw._sock.settimeout(eff_read_timeout)
                        except Exception:
                            pass

                    # Stream-read up to max_response_size to prevent memory exhaustion
                    chunks = []
                    bytes_read = 0
                    incomplete_salvaged = False
                    start_stream_time = time.time()
                    max_stream_duration = max(30.0, eff_read_timeout * 3.0)
                    while True:
                        if time.time() - start_stream_time > max_stream_duration:
                            logger.warning(
                                f"Response stream from {norm_url} exceeded wall-clock deadline ({max_stream_duration}s). Truncating."
                            )
                            incomplete_salvaged = True
                            break
                        single_read = False
                        read_chunk_size = (
                            min(65536, self.max_response_size - bytes_read)
                            if self.max_response_size > 0
                            else 65536
                        )
                        try:
                            chunk = resp.read(read_chunk_size)
                        except TypeError:
                            chunk = resp.read()
                            single_read = True
                        except http.client.IncompleteRead as ire:
                            partial = ire.partial or b""
                            logger.warning(
                                f"IncompleteRead on {norm_url} (Attempt {attempt}/{eff_retries}): "
                                f"{len(partial)} partial bytes received before disconnect."
                            )
                            if partial:
                                chunks.append(partial)
                                bytes_read += len(partial)
                            if attempt < eff_retries:
                                raise  # Let outer retry loop attempt a clean request
                            # On last attempt, break to salvage already-read bytes without caching truncated body
                            incomplete_salvaged = True
                            break
                        if not chunk:
                            break
                        chunks.append(chunk)
                        bytes_read += len(chunk)
                        if self.max_response_size > 0 and bytes_read >= self.max_response_size:
                            logger.warning(
                                f"Response from {norm_url} exceeded max size ({self.max_response_size} bytes). Truncating."
                            )
                            break
                        if single_read or len(chunk) > 65536:
                            break
                    raw_bytes = b"".join(chunks)
                    if self.max_response_size > 0 and len(raw_bytes) > self.max_response_size:
                        raw_bytes = raw_bytes[: self.max_response_size]

                    content_type_header = (
                        resp.headers.get("Content-Type", "")
                        if hasattr(resp, "headers") and resp.headers
                        else ""
                    )
                    content_type = str(content_type_header) if content_type_header is not None else ""
                    detected_encoding = encoding or self._detect_encoding(content_type, raw_bytes)
                    decoded_text = robust_decode(raw_bytes, declared_encoding=detected_encoding)

                    if status_code is not None and (status_code == 200 or (is_half_open_probe and status_code < 400)):
                        if not incomplete_salvaged:
                            self.circuit_breaker.record_success(norm_url)
                            if is_cacheable_method and status_code == 200 and decoded_text:
                                self.set_cached_response(norm_url, status_code, decoded_text, raw_bytes)
                        elif is_half_open_probe:
                            self.circuit_breaker.record_failure(norm_url, status_code=status_code)
                    elif is_half_open_probe and (status_code is None or status_code >= 400):
                        self.circuit_breaker.record_failure(norm_url, status_code=status_code)

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
                logger.warning(
                    f"HTTPError {he.code} ({he.reason}) on {norm_url} (Attempt {attempt}/{eff_retries})"
                )
                try:
                    if isinstance(getattr(he, "reason", None), str) and he.reason.startswith("SSRF Blocked:"):
                        logger.warning(f"SSRF redirect aborted immediately for {norm_url}: {he.reason}")
                        if is_half_open_probe:
                            self.circuit_breaker.record_failure(norm_url, status_code=he.code)
                        return 0, "", b""
                    # Retry on rate limiting or server errors
                    if (
                        he.code in [408, 429, 403, 500, 502, 503, 504, 520, 521, 522, 523, 524]
                        and attempt < eff_retries
                    ):
                        if he.code in (403, 429):
                            self.clear_cookies()
                        retry_after = self._parse_retry_after(he) if he.code in (429, 503) else None
                        backoff = self._calc_backoff(attempt, retry_after=retry_after)
                        if he.code == 429:
                            with self._rate_lock:
                                self._rate_limited_until = max(self._rate_limited_until, time.time() + backoff)
                        logger.info(f"Backing off for {backoff:.2f}s before retry (status {he.code})...")
                        time.sleep(backoff)
                    else:
                        retry_after = self._parse_retry_after(he) if he.code in (429, 503) else None
                        if he.code == 429:
                            backoff = self._calc_backoff(attempt, retry_after=retry_after)
                            with self._rate_lock:
                                self._rate_limited_until = max(self._rate_limited_until, time.time() + backoff)
                        if he.code in (403, 429, 503) or (
                            is_half_open_probe
                            and he.code in (408, 500, 502, 504, 520, 521, 522, 523, 524)
                        ):
                            tripped = self.circuit_breaker.record_failure(
                                norm_url, status_code=he.code, retry_after=retry_after
                            )
                            if tripped:
                                logger.warning(
                                    f"Circuit breaker tripped OPEN for {norm_url} on HTTP {he.code}."
                                )
                        elif is_half_open_probe:
                            self.circuit_breaker.record_success(norm_url)
                        # On 403, 429, or 5xx server error exhaustion, fallback to cached response if available
                        if is_cacheable_method and he.code in [403, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524] and self.cache_fallback:
                            cached = self.get_cached_response(norm_url)
                            if cached is not None:
                                logger.warning(
                                    f"Remote endpoint {norm_url} returned HTTP {he.code}. Falling back to cached response."
                                )
                                self.last_response_from_cache = True
                                return cached
                        # Return error content if not retrying
                        try:
                            read_limit = self.max_response_size if self.max_response_size > 0 else 65536
                            try:
                                raw_bytes = he.read(read_limit)
                            except TypeError:
                                raw_bytes = he.read()
                                if self.max_response_size > 0 and isinstance(raw_bytes, (bytes, bytearray)) and len(raw_bytes) > self.max_response_size:
                                    raw_bytes = bytes(raw_bytes[:self.max_response_size])
                            decoded_text = robust_decode(raw_bytes, declared_encoding=encoding or "utf-8")
                            return he.code, decoded_text, raw_bytes
                        except Exception:
                            return he.code, "", b""
                finally:
                    # Guarantee HTTPError and underlying fp are closed to eliminate ResourceWarnings
                    try:
                        if hasattr(he, "fp") and he.fp:
                            he.fp.close()
                        he.close()
                    except Exception:
                        pass
                    del he

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
                reason = getattr(ex, "reason", None)
                if "ssrf blocked:" in str(ex).lower() or (reason and "ssrf blocked:" in str(reason).lower()):
                    logger.warning(f"SSRF defense aborted connection to {norm_url}: {ex}")
                    if is_half_open_probe:
                        self.circuit_breaker.record_failure(norm_url)
                    return 0, "", b""
                is_timeout = (
                    isinstance(ex, (TimeoutError, socket.timeout))
                    or (isinstance(ex, urllib.error.URLError) and "timed out" in str(ex).lower())
                    or isinstance(reason, (socket.timeout, TimeoutError))
                    or ("timed out" in str(reason).lower() if reason else False)
                )
                is_ssl = (
                    isinstance(ex, ssl.SSLError)
                    or isinstance(reason, ssl.SSLError)
                    or ("ssl" in str(ex).lower() and "error" in str(ex).lower())
                )
                is_disconnect = (
                    isinstance(
                        ex,
                        (
                            http.client.RemoteDisconnected,
                            ConnectionResetError,
                            ConnectionRefusedError,
                            ConnectionAbortedError,
                            BrokenPipeError,
                        ),
                    )
                    or isinstance(
                        reason,
                        (
                            http.client.RemoteDisconnected,
                            ConnectionResetError,
                            ConnectionRefusedError,
                            ConnectionAbortedError,
                            BrokenPipeError,
                        ),
                    )
                    or "remote end closed connection" in str(ex).lower()
                )
                is_incomplete_read = (
                    isinstance(ex, http.client.IncompleteRead)
                    or isinstance(reason, http.client.IncompleteRead)
                )

                if is_timeout:
                    logger.warning(
                        f"Request timeout on {norm_url} (Attempt {attempt}/{eff_retries}): {ex}"
                    )
                elif is_ssl:
                    logger.warning(
                        f"SSL error on {norm_url} (Attempt {attempt}/{eff_retries}): {ex}"
                    )
                elif is_disconnect:
                    logger.warning(
                        f"Remote disconnected on {norm_url} (Attempt {attempt}/{eff_retries}): {ex}"
                    )
                elif is_incomplete_read:
                    logger.warning(
                        f"Incomplete read on {norm_url} (Attempt {attempt}/{eff_retries}): {ex}"
                    )
                else:
                    logger.warning(
                        f"Network error on {norm_url} (Attempt {attempt}/{eff_retries}): {ex}"
                    )

                if attempt < eff_retries:
                    if is_disconnect:
                        self.clear_cookies()
                    backoff = self._calc_backoff(attempt)
                    logger.info(f"Backing off for {backoff:.2f}s before retry...")
                    time.sleep(backoff)
                else:
                    self.circuit_breaker.record_failure(norm_url)
                    if is_cacheable_method and self.cache_fallback:
                        cached = self.get_cached_response(norm_url)
                        if cached is not None:
                            logger.warning(
                                f"Remote endpoint {norm_url} unreachable ({ex}). Falling back to cached response."
                            )
                            self.last_response_from_cache = True
                            return cached
                    break

        if is_cacheable_method and self.cache_fallback:
            cached = self.get_cached_response(norm_url)
            if cached is not None:
                logger.warning(
                    f"Remote endpoint {norm_url} unreachable. Falling back to cached response."
                )
                self.last_response_from_cache = True
                return cached

        logger.error(f"Failed to fetch {norm_url} after {eff_retries} attempts.")
        return 0, "", b""

    def _parse_retry_after(self, he: urllib.error.HTTPError) -> Optional[float]:
        """
        Parse standard HTTP Retry-After header or X-RateLimit-Reset if present on HTTPError response.
        Supports case-insensitive headers, integer/float delay seconds, or HTTP-date string (RFC 9110 / RFC 7231).
        """
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

        if val:
            val_str = str(val).strip()
            # 1. Delay seconds
            try:
                sec = float(val_str)
                if math.isfinite(sec) and sec >= 0:
                    return sec
            except ValueError:
                pass

            # 2. HTTP-date
            try:
                parsed_dt = email.utils.parsedate_to_datetime(val_str)
                now = datetime.datetime.now(datetime.timezone.utc)
                if parsed_dt.tzinfo is None:
                    parsed_dt = parsed_dt.replace(tzinfo=datetime.timezone.utc)
                delta = (parsed_dt - now).total_seconds()
                return max(0.0, delta)
            except Exception:
                pass

        # Fallback: check X-RateLimit-Reset (epoch timestamp)
        reset_val = None
        if hasattr(he.headers, "get"):
            reset_val = he.headers.get("X-RateLimit-Reset") or he.headers.get("x-ratelimit-reset")
        if reset_val is None and hasattr(he.headers, "items"):
            for k, v in he.headers.items():
                if str(k).lower() == "x-ratelimit-reset":
                    reset_val = v
                    break
        if reset_val:
            try:
                epoch = float(reset_val)
                now_epoch = time.time()
                if math.isfinite(epoch) and epoch > now_epoch:
                    return min(60.0, max(0.0, epoch - now_epoch))
            except (ValueError, TypeError):
                pass

        return None

    def _calc_backoff(self, attempt: int, retry_after: Optional[float] = None) -> float:
        """
        Calculate backoff time in seconds.
        If retry_after is provided by server (e.g. on HTTP 429), honor it.
        Otherwise calculate exponential backoff with jitter.
        """
        max_backoff = getattr(self, "max_backoff", 30.0)
        factor = getattr(self, "backoff_factor", 1.5)
        if retry_after is not None and not isinstance(retry_after, bool):
            try:
                ra = float(retry_after)
            except (ValueError, TypeError, OverflowError):
                ra = -1.0
            if math.isfinite(ra) and ra >= 0:
                cap = max(max_backoff, 60.0)
                if not self.enable_jitter:
                    return min(cap, ra)
                jitter = random.uniform(0.1, 0.5)
                return min(cap, ra + jitter)

        exp_step = min(max(0, int(attempt)), 30)
        if not self.enable_jitter:
            return min(max_backoff, float(2 ** exp_step))
        base = (2 ** exp_step) * factor
        jitter = random.uniform(0.5, 1.5)
        return min(max_backoff, base + jitter)

    @staticmethod
    def _detect_encoding(content_type: str, raw_bytes: bytes) -> str:
        """Detect encoding from Content-Type header or HTML meta tags."""
        content_str = str(content_type) if content_type is not None else ""
        match = _RE_CHARSET.search(content_str)
        if match:
            return match.group(1).strip().lower()

        # Check HTML meta charset in first 4KB
        prefix = raw_bytes[:4096].decode("ascii", errors="ignore")
        meta_match = _RE_META_CHARSET.search(prefix)
        if meta_match:
            return meta_match.group(1).strip().lower()

        meta_http = _RE_META_HTTP.search(prefix)
        if meta_http:
            return meta_http.group(1).strip().lower()

        return "utf-8"

    def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        referer: Optional[str] = None,
        encoding: Optional[str] = None,
        timeout: Optional[Union[float, Tuple[float, float]]] = None,
        connect_timeout: Optional[float] = None,
        read_timeout: Optional[float] = None,
    ) -> Tuple[int, str, bytes]:
        """Convenience wrapper for GET request."""
        return self.request(
            url,
            method="GET",
            headers=headers,
            referer=referer,
            encoding=encoding,
            timeout=timeout,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
        )

    def post(
        self,
        url: str,
        data: Optional[Union[Dict[str, Any], bytes, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        referer: Optional[str] = None,
        encoding: Optional[str] = None,
        timeout: Optional[Union[float, Tuple[float, float]]] = None,
        connect_timeout: Optional[float] = None,
        read_timeout: Optional[float] = None,
    ) -> Tuple[int, str, bytes]:
        """Convenience wrapper for POST request."""
        return self.request(
            url,
            method="POST",
            data=data,
            headers=headers,
            referer=referer,
            encoding=encoding,
            timeout=timeout,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
        )
