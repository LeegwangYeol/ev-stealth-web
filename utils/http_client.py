"""
Robust, Rate-Limited HTTP Client for Web Scraping and Community Forum Data Mining.
Pure Python Standard Library implementation with User-Agent rotation, configurable
jitter (1.5s~3.5s), exponential backoff, cookie jar session handling, and error logging.
"""

import html
import http.cookiejar
import logging
import os
import random
import re
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

# User-Agent Pool (Modern Desktop and Mobile browsers)
USER_AGENT_POOL = [
    # Chrome macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    # Safari macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    # Firefox macOS & Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.6; rv:129.0) Gecko/20100101 Firefox/129.0",
    # Edge Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0",
    # Mobile (iOS Safari & Android Chrome)
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; SM-S918N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36",
]


def robust_decode(raw_bytes: bytes, declared_encoding: Optional[str] = None) -> str:
    """
    Decode raw bytes with graceful fallback across Korean and universal charsets.
    Tries declared encoding, utf-8, cp949, euc-kr, and latin-1.
    """
    if not raw_bytes:
        return ""

    encodings_to_try = [declared_encoding, "utf-8", "cp949", "euc-kr", "latin-1"]
    for enc in encodings_to_try:
        if not enc:
            continue
        try:
            return raw_bytes.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue

    return raw_bytes.decode("utf-8", errors="replace")


def encode_euc_kr_query(param: Union[str, Dict[str, Any]]) -> str:
    """
    Percent-encode string or dictionary parameters into EUC-KR / CP949 for Korean forums
    like BobaeDream that require non-UTF-8 URL queries.
    """
    if isinstance(param, str):
        try:
            return urllib.parse.quote(param.encode("euc-kr"))
        except UnicodeEncodeError:
            return urllib.parse.quote(param.encode("cp949", errors="replace"))

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


def clean_html_text(raw_html: str) -> str:
    """
    Strip HTML tags, scripts, styles, decode HTML entities, and normalize whitespace.
    """
    if not raw_html:
        return ""

    # Remove script and style elements
    cleaned = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw_html, flags=re.DOTALL | re.IGNORECASE)
    # Replace block level tags with newlines
    cleaned = re.sub(r"<(br|p|/p|div|/div|li|/li|h\d|/h\d|tr|/tr|dt|/dt|dd|/dd)[^>]*>", "\n", cleaned, flags=re.IGNORECASE)
    # Remove remaining HTML tags
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    # Decode HTML entities (&amp;, &lt;, etc.)
    cleaned = html.unescape(cleaned)
    # Collapse multiple whitespace characters on each line and drop blank lines
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in cleaned.splitlines()]
    return "\n".join([line for line in lines if line])


class SafeHttpClient:
    """
    Safe and polite HTTP client designed to avoid anti-bot detection and handle rate limits.
    Features:
      - Uniform random jitter between requests (default 1.5s ~ 3.5s)
      - User-Agent pool rotation
      - Exponential backoff retry on HTTP 429, 403, 5xx, or network errors
      - Persistent CookieJar session management
      - Charset auto-detection with robust decoding fallback
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
    ):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.timeout = timeout
        self.enable_jitter = enable_jitter
        self.request_count = 0
        self.last_request_time = 0.0

        # Session cookie jar
        self.cookie_jar = cookie_jar if cookie_jar is not None else http.cookiejar.CookieJar()
        if opener is not None:
            self.opener = opener
        else:
            self.opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(self.cookie_jar)
            )

    def get_random_user_agent(self) -> str:
        """Pick a modern browser User-Agent from pool."""
        return random.choice(USER_AGENT_POOL)

    def _sleep_with_jitter(self):
        """Perform polite delay with randomized jitter between requests."""
        if not self.enable_jitter or self.max_delay <= 0:
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

        target_delay = random.uniform(self.min_delay, self.max_delay)
        if elapsed < target_delay:
            sleep_duration = target_delay - elapsed
            time.sleep(sleep_duration)

        self.last_request_time = time.time()
        self.request_count += 1

    def warm_up_session(self, base_url: str, referer: Optional[str] = None) -> bool:
        """
        Send a lightweight request to the base URL to collect initial session cookies.
        """
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
        and automatic charset decoding.

        Returns:
            Tuple[int, str, bytes]: (status_code, decoded_text, raw_bytes)
        """
        self._sleep_with_jitter()

        req_headers = {
            "User-Agent": self.get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "identity",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Upgrade-Insecure-Requests": "1",
        }
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

        req_timeout = timeout or self.timeout

        for attempt in range(1, self.max_retries + 1):
            try:
                req = urllib.request.Request(
                    url,
                    data=payload_bytes,
                    headers=req_headers,
                    method=method.upper()
                )
                with self.opener.open(req, timeout=req_timeout) as resp:
                    status_code = resp.getcode()
                    raw_bytes = resp.read()

                    content_type_header = resp.headers.get("Content-Type", "")
                    content_type = str(content_type_header) if content_type_header is not None else ""
                    detected_encoding = encoding or self._detect_encoding(content_type, raw_bytes)
                    decoded_text = robust_decode(raw_bytes, declared_encoding=detected_encoding)

                    return status_code, decoded_text, raw_bytes

            except urllib.error.HTTPError as he:
                logger.warning(
                    f"HTTPError {he.code} ({he.reason}) on {url} (Attempt {attempt}/{self.max_retries})"
                )
                # Retry on rate limiting or server errors
                if he.code in [429, 403, 500, 502, 503, 504] and attempt < self.max_retries:
                    backoff = self._calc_backoff(attempt)
                    logger.info(f"Backing off for {backoff:.2f}s before retry (status {he.code})...")
                    time.sleep(backoff)
                else:
                    # Return error content if not retrying
                    try:
                        raw_bytes = he.read()
                        decoded_text = robust_decode(raw_bytes, declared_encoding=encoding or "utf-8")
                        return he.code, decoded_text, raw_bytes
                    except Exception:
                        return he.code, "", b""

            except Exception as ex:
                logger.warning(
                    f"Network error on {url} (Attempt {attempt}/{self.max_retries}): {ex}"
                )
                if attempt < self.max_retries:
                    backoff = self._calc_backoff(attempt)
                    logger.info(f"Backing off for {backoff:.2f}s before retry...")
                    time.sleep(backoff)
                else:
                    break

        logger.error(f"Failed to fetch {url} after {self.max_retries} attempts.")
        return 0, "", b""

    def _calc_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff time with jitter."""
        if not self.enable_jitter:
            return float(2 ** attempt)
        base = (2 ** attempt) * 1.5
        jitter = random.uniform(0.5, 1.5)
        return min(30.0, base + jitter)

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
