"""
Robust, Rate-Limited HTTP Client for Web Scraping and Community Forum Data Mining.
Pure Python Standard Library implementation with User-Agent rotation, configurable
jitter (1.5s~3.5s), exponential backoff, cookie jar session handling, and error logging.
"""

from __future__ import annotations

import datetime
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
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

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


def robust_decode(raw_bytes: Union[bytes, str], declared_encoding: Optional[str] = None) -> str:
    """Decode raw bytes with graceful fallback across Korean and universal charsets.
    Tries declared encoding, utf-8, cp949, euc-kr, and latin-1.
    """
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
        k_str = str(k)
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
_RE_CHARSET = re.compile(r"charset=([\w\-]+)", flags=re.IGNORECASE)
_RE_META_CHARSET = re.compile(r'<meta[^>]+charset=["\']?([\w\-]+)', flags=re.IGNORECASE)
_RE_META_HTTP = re.compile(
    r'<meta[^>]+http-equiv=["\']?content-type["\']?[^>]+content=["\'][^"\']*charset=([\w\-]+)',
    flags=re.IGNORECASE,
)


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
    # Remove HTML comments
    cleaned = _RE_HTML_COMMENT.sub(" ", cleaned)
    # Remove script and style elements (handling unclosed tags gracefully)
    cleaned = _RE_HTML_SCRIPT_STYLE.sub(" ", cleaned)
    # Replace block level tags with newlines
    cleaned = _RE_HTML_BLOCK_TAGS.sub("\n", cleaned)
    # Remove remaining HTML tags
    cleaned = _RE_HTML_TAGS.sub(" ", cleaned)
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
    ):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.timeout = timeout
        self.enable_jitter = enable_jitter
        self.max_response_size = max_response_size
        self.max_cookies = max_cookies
        self.default_headers = dict(default_headers) if default_headers else {}
        self.user_agent = user_agent
        self.rotate_user_agent = rotate_user_agent
        self.backoff_factor = float(backoff_factor) if backoff_factor > 0 else 1.5
        self.max_backoff = float(max_backoff) if max_backoff > 0 else 30.0
        self.verify_ssl = verify_ssl
        self.enable_cache = enable_cache
        self.cache_fallback = cache_fallback
        self.request_count = 0
        self.last_request_time = 0.0
        self._rate_limited_until = 0.0
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
            if not self.verify_ssl:
                ssl_ctx = ssl.create_default_context()
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE
                https_handler = ResilientHTTPSHandler(
                    connect_timeout=self._connect_timeout,
                    read_timeout=self._read_timeout,
                    context=ssl_ctx,
                )
            else:
                https_handler = ResilientHTTPSHandler(
                    connect_timeout=self._connect_timeout,
                    read_timeout=self._read_timeout,
                )
            http_handler = ResilientHTTPHandler(
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
        # 1. In-memory cache
        if key in self._memory_cache:
            entry = self._memory_cache[key]
            return entry.get("status", 200), entry.get("text", ""), entry.get("raw", b"")

        # 2. Disk cache
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
        if exclude and len(USER_AGENT_POOL) > 1:
            candidates = [ua for ua in USER_AGENT_POOL if ua != exclude]
            if candidates:
                return random.choice(candidates)
        return random.choice(USER_AGENT_POOL)

    def _sleep_with_jitter(self):
        """Perform polite delay with randomized jitter between requests."""
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

        if not self.enable_jitter or max_d <= 0:
            self.last_request_time = time.time()
            self.request_count += 1
            return

        now = time.time()

        # Proactive rate-limit cooldown: if recently throttled by HTTP 429, respect backoff
        if self._rate_limited_until > 0 and now < self._rate_limited_until:
            wait_sec = (self._rate_limited_until - now) + random.uniform(0.5, 1.5)
            logger.info(f"Proactive rate-limit protection: sleeping {wait_sec:.2f}s before next request...")
            time.sleep(wait_sec)
            self._rate_limited_until = 0.0
            now = time.time()

        elapsed = now - self.last_request_time

        # Prolonged cooldown pause every 20 requests to protect rate limits
        if self.request_count > 0 and self.request_count % 20 == 0:
            extra_cooldown = random.uniform(4.0, 7.0)
            logger.info(f"Rate protection cooldown after {self.request_count} requests. Sleeping {extra_cooldown:.2f}s...")
            time.sleep(extra_cooldown)

        target_delay = random.uniform(min_d, max_d)
        if elapsed < target_delay:
            sleep_duration = target_delay - elapsed
            time.sleep(sleep_duration)

        self.last_request_time = time.time()
        self.request_count += 1

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
        if not (norm_url.startswith("http://") or norm_url.startswith("https://")):
            logger.warning(f"Unsupported URL scheme: {norm_url!r}")
            return 0, "", b""

        self.last_response_from_cache = False
        self._sleep_with_jitter()

        active_ua = (
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
            req_headers.update(self.default_headers)
        if referer:
            req_headers["Referer"] = referer
        if headers:
            for k, v in headers.items():
                # Case-insensitive update to avoid duplicate headers like User-Agent vs user-agent
                matching_keys = [ek for ek in req_headers if ek.lower() == k.lower()]
                for mk in matching_keys:
                    del req_headers[mk]
                req_headers[k] = v

        has_custom_ua = bool(
            self.user_agent or (headers and any(k.lower() == "user-agent" for k in headers))
        )

        payload_bytes: Optional[bytes] = None
        if data is not None:
            if isinstance(data, dict):
                payload_bytes = urllib.parse.urlencode(data).encode("utf-8")
                req_headers.setdefault("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8")
            elif isinstance(data, bytes):
                payload_bytes = data
            elif isinstance(data, str):
                payload_bytes = data.encode("utf-8")

        # Resolve explicit connect and read timeouts for this specific request
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

        req_timeout = eff_read_timeout

        eff_retries = max(1, int(self.max_retries)) if self.max_retries is not None else 3

        for attempt in range(1, eff_retries + 1):
            if attempt > 1 and self.rotate_user_agent and not has_custom_ua:
                current_ua = req_headers.get("User-Agent")
                req_headers["User-Agent"] = self.get_random_user_agent(exclude=current_ua)
            try:
                req = urllib.request.Request(
                    norm_url,
                    data=payload_bytes,
                    headers=req_headers,
                    method=method.upper(),
                )
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
                    while True:
                        try:
                            chunk = resp.read(65536)
                        except TypeError:
                            chunk = resp.read()
                        except http.client.IncompleteRead as ire:
                            logger.warning(
                                f"IncompleteRead on {norm_url} (Attempt {attempt}/{eff_retries}): "
                                f"{len(ire.partial)} partial bytes received before disconnect."
                            )
                            if ire.partial:
                                chunks.append(ire.partial)
                                bytes_read += len(ire.partial)
                            if attempt < eff_retries:
                                raise  # Let outer retry loop attempt a clean request
                            # On last attempt, break to salvage already-read bytes
                            break
                        if not chunk:
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

                    content_type_header = (
                        resp.headers.get("Content-Type", "")
                        if hasattr(resp, "headers") and resp.headers
                        else ""
                    )
                    content_type = str(content_type_header) if content_type_header is not None else ""
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
                            self._rate_limited_until = time.time() + backoff
                        logger.info(f"Backing off for {backoff:.2f}s before retry (status {he.code})...")
                        time.sleep(backoff)
                    else:
                        if he.code == 429:
                            retry_after = self._parse_retry_after(he)
                            backoff = self._calc_backoff(attempt, retry_after=retry_after)
                            self._rate_limited_until = time.time() + backoff
                        # On 5xx server error exhaustion, fallback to cached response if available
                        if he.code in [500, 502, 503, 504, 520, 521, 522, 523, 524] and self.cache_fallback:
                            cached = self.get_cached_response(norm_url)
                            if cached is not None:
                                logger.warning(
                                    f"Remote endpoint {norm_url} returned HTTP {he.code}. Falling back to cached response."
                                )
                                self.last_response_from_cache = True
                                return cached
                        # Return error content if not retrying
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
                if sec >= 0:
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
        if reset_val:
            try:
                epoch = float(reset_val)
                now_epoch = time.time()
                if epoch > now_epoch:
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
        if retry_after is not None and retry_after >= 0:
            if not self.enable_jitter:
                return float(retry_after)
            jitter = random.uniform(0.1, 0.5)
            return min(max(max_backoff, 60.0), float(retry_after) + jitter)

        if not self.enable_jitter:
            return min(max_backoff, float(2 ** attempt))
        base = (2 ** attempt) * factor
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
