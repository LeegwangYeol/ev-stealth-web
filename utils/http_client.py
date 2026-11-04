"""
Robust, Rate-Limited HTTP Client for Web Scraping and Community Forum Data Mining.
Pure Python Standard Library implementation with User-Agent rotation, configurable
jitter (1.5s~3.5s), exponential backoff, cookie jar session handling, and error logging.
"""

from __future__ import annotations

import datetime
import email.utils
import html
import http.client
import http.cookiejar
import logging
import os
import random
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
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
    cleaned = re.sub(r"<!--.*?-->", " ", cleaned, flags=re.DOTALL)
    # Remove script and style elements (handling unclosed tags gracefully)
    cleaned = re.sub(r"<(script|style)[^>]*>(?:.*?</\1>|.*$)", " ", cleaned, flags=re.DOTALL | re.IGNORECASE)
    # Replace block level tags with newlines
    cleaned = re.sub(r"<(br|p|/p|div|/div|li|/li|h\d|/h\d|tr|/tr|dt|/dt|dd|/dd)[^>]*>", "\n", cleaned, flags=re.IGNORECASE)
    # Remove remaining HTML tags
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    # Handle unclosed tag brackets at end of string
    cleaned = re.sub(r"<[a-zA-Z/][^<]*$", " ", cleaned)
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
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in cleaned.splitlines()]
    return "\n".join([line for line in lines if line])


class SafeHttpClient:
    """
    Safe and polite HTTP client designed to avoid anti-bot detection and handle rate limits.
    Features:
      - Uniform random jitter between requests (default 1.5s ~ 3.5s)
      - User-Agent pool rotation & customizable session headers
      - Exponential backoff retry on HTTP 429, 403, 408, 5xx, or network disconnects
      - Fault-tolerant error recovery (URLError, RemoteDisconnected, IncompleteRead, SSLError)
      - Partial response salvage on IncompleteRead disconnects
      - Persistent CookieJar session management with auto-pruning to prevent memory leaks
      - Charset auto-detection with robust decoding fallback
      - Bounded response stream reading and socket/file-descriptor resource cleanup
    """

    def __init__(
        self,
        min_delay: float = 1.5,
        max_delay: float = 3.5,
        max_retries: int = 3,
        timeout: float = 15.0,
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
        self.request_count = 0
        self.last_request_time = 0.0

        # Dedicated session UA if rotation is disabled
        self._session_user_agent = user_agent or self.get_random_user_agent()

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
                https_handler = urllib.request.HTTPSHandler(context=ssl_ctx)
                self.opener = urllib.request.build_opener(cookie_processor, https_handler)
            else:
                self.opener = urllib.request.build_opener(cookie_processor)

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

    def get_random_user_agent(self) -> str:
        """Pick a modern browser User-Agent from pool."""
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
        timeout: Optional[float] = None,
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
            req_headers.update(headers)

        payload_bytes: Optional[bytes] = None
        if data is not None:
            if isinstance(data, dict):
                payload_bytes = urllib.parse.urlencode(data).encode("utf-8")
                req_headers.setdefault("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8")
            elif isinstance(data, bytes):
                payload_bytes = data
            elif isinstance(data, str):
                payload_bytes = data.encode("utf-8")

        try:
            req_timeout = float(timeout) if timeout is not None else float(self.timeout)
            if req_timeout <= 0:
                req_timeout = 15.0
        except (ValueError, TypeError):
            req_timeout = 15.0

        eff_retries = max(1, int(self.max_retries)) if self.max_retries is not None else 3

        for attempt in range(1, eff_retries + 1):
            if attempt > 1 and self.rotate_user_agent and not self.user_agent:
                req_headers["User-Agent"] = self.get_random_user_agent()
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

                    return status_code, decoded_text, raw_bytes
                finally:
                    if hasattr(resp, "close"):
                        try:
                            resp.close()
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
                        retry_after = self._parse_retry_after(he) if he.code == 429 else None
                        backoff = self._calc_backoff(attempt, retry_after=retry_after)
                        logger.info(f"Backing off for {backoff:.2f}s before retry (status {he.code})...")
                        time.sleep(backoff)
                    else:
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
                ssl.SSLError,
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
                        ),
                    )
                    or isinstance(
                        reason,
                        (
                            http.client.RemoteDisconnected,
                            ConnectionResetError,
                            ConnectionRefusedError,
                            ConnectionAbortedError,
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
                    break

        logger.error(f"Failed to fetch {norm_url} after {eff_retries} attempts.")
        return 0, "", b""

    def _parse_retry_after(self, he: urllib.error.HTTPError) -> Optional[float]:
        """
        Parse standard HTTP Retry-After header if present on HTTPError response.
        Supports integer/float delay seconds or HTTP-date string (RFC 9110 / RFC 7231).
        """
        if not hasattr(he, "headers") or not he.headers:
            return None

        val = he.headers.get("Retry-After")
        if not val:
            return None

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

        return None

    def _calc_backoff(self, attempt: int, retry_after: Optional[float] = None) -> float:
        """
        Calculate backoff time in seconds.
        If retry_after is provided by server (e.g. on HTTP 429), honor it.
        Otherwise calculate exponential backoff with jitter.
        """
        if retry_after is not None and retry_after >= 0:
            if not self.enable_jitter:
                return float(retry_after)
            jitter = random.uniform(0.1, 0.5)
            return min(60.0, float(retry_after) + jitter)

        if not self.enable_jitter:
            return float(2 ** attempt)
        factor = getattr(self, "backoff_factor", 1.5)
        base = (2 ** attempt) * factor
        jitter = random.uniform(0.5, 1.5)
        max_backoff = getattr(self, "max_backoff", 30.0)
        return min(max_backoff, base + jitter)

    @staticmethod
    def _detect_encoding(content_type: str, raw_bytes: bytes) -> str:
        """Detect encoding from Content-Type header or HTML meta tags."""
        content_str = str(content_type) if content_type is not None else ""
        match = re.search(r"charset=([\w\-]+)", content_str, re.IGNORECASE)
        if match:
            return match.group(1).strip().lower()

        # Check HTML meta charset in first 4KB
        prefix = raw_bytes[:4096].decode("ascii", errors="ignore")
        meta_match = re.search(r'<meta[^>]+charset=["\']?([\w\-]+)', prefix, re.IGNORECASE)
        if meta_match:
            return meta_match.group(1).strip().lower()

        meta_http = re.search(
            r'<meta[^>]+http-equiv=["\']?content-type["\']?[^>]+content=["\'][^"\']*charset=([\w\-]+)',
            prefix,
            re.IGNORECASE,
        )
        if meta_http:
            return meta_http.group(1).strip().lower()

        return "utf-8"

    def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        referer: Optional[str] = None,
        encoding: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Tuple[int, str, bytes]:
        """Convenience wrapper for GET request."""
        return self.request(
            url,
            method="GET",
            headers=headers,
            referer=referer,
            encoding=encoding,
            timeout=timeout,
        )

    def post(
        self,
        url: str,
        data: Optional[Union[Dict[str, Any], bytes, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        referer: Optional[str] = None,
        encoding: Optional[str] = None,
        timeout: Optional[float] = None,
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
        )
