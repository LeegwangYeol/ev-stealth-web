"""
Abstract BaseCrawler interface and fault-tolerant parsing foundation
for community forum web scrapers (BobaeDream, DCInside, etc.).
"""

from __future__ import annotations

import abc
from collections import OrderedDict
import copy
import html
import json
import logging
import math
import os
import re
import threading
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from utils.http_client import SafeHttpClient, is_safe_url, robust_decode

logger = logging.getLogger("BaseCrawler")

MAX_POST_CACHE_SIZE: int = 500
_RE_SEMICOLON_HTML_ENTITY = re.compile(r"&(?:#\d+|#x[0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9]+);")
_RE_OPEN_COMMENT_OR_SCRIPT = re.compile(r"<!--|<(script|style)\b[^>]*>", re.IGNORECASE)
_RE_CLOSE_SCRIPT = re.compile(r"</script\s*>", re.IGNORECASE)
_RE_CLOSE_STYLE = re.compile(r"</style\s*>", re.IGNORECASE)


def _mask_comments_and_scripts(html_str: str) -> str:
    """Replace HTML comments and script/style blocks with equal-length spaces in linear O(N) time."""
    if not html_str:
        return html_str
    lower_html = html_str.lower()
    if "<!--" not in html_str and "<script" not in lower_html and "<style" not in lower_html:
        return html_str

    last_comment_end = html_str.rfind("-->")
    has_close_tag = {"script": True, "style": True}
    parts: List[str] = []
    pos = 0
    n = len(html_str)

    while pos < n:
        m = _RE_OPEN_COMMENT_OR_SCRIPT.search(html_str, pos)
        if not m:
            parts.append(html_str[pos:])
            break

        tag_group = m.group(1)
        if tag_group is None:
            if last_comment_end == -1 or m.end() > last_comment_end:
                parts.append(html_str[pos:m.end()])
                pos = m.end()
                continue
            end_idx = html_str.find("-->", m.end())
            if end_idx == -1:
                parts.append(html_str[pos:m.end()])
                pos = m.end()
                continue
            close_end = end_idx + 3
            parts.append(html_str[pos:m.start()])
            parts.append(" " * (close_end - m.start()))
            pos = close_end
        else:
            tag_name = tag_group.lower()
            if not has_close_tag[tag_name]:
                parts.append(html_str[pos:m.end()])
                pos = m.end()
                continue
            close_re = _RE_CLOSE_SCRIPT if tag_name == "script" else _RE_CLOSE_STYLE
            close_m = close_re.search(html_str, m.end())
            if close_m is None:
                has_close_tag[tag_name] = False
                parts.append(html_str[pos:m.end()])
                pos = m.end()
                continue
            parts.append(html_str[pos:m.start()])
            parts.append(" " * (close_m.end() - m.start()))
            pos = close_m.end()

    return "".join(parts)


def _slice_to_last_close_tag(html_str: str, close_prefix: str) -> str:
    """Bound regex dotall scans to the last matching closing tag (e.g. '</a', '</tr') to prevent O(N^2) ReDoS."""
    idx = html_str.lower().rfind(close_prefix)
    if idx == -1:
        return ""
    gt_idx = html_str.find(">", idx)
    if gt_idx == -1:
        return ""
    return html_str[: gt_idx + 1]


def _unescape_url_entities(raw_url: str) -> str:
    """Decode semicolon-terminated HTML entities in URLs without mutating bare query params like &copy=."""
    if not raw_url or "&" not in raw_url:
        return raw_url
    return _RE_SEMICOLON_HTML_ENTITY.sub(lambda m: html.unescape(m.group(0)), raw_url)


def _sanitize_referer(referer: Optional[str]) -> Optional[str]:
    """Strip CR/LF and other ASCII control characters from Referer header values."""
    if not referer or not isinstance(referer, str):
        return None
    cleaned = "".join(c for c in referer if ord(c) >= 32 and ord(c) != 127).strip()
    return cleaned or None


def _has_unsafe_authority(parsed: urllib.parse.SplitResult) -> bool:
    """Reject userinfo (@) and backslashes in URL authority to prevent SSRF parser confusion."""
    if parsed.username is not None or parsed.password is not None:
        return True
    netloc = parsed.netloc or ""
    if "@" in netloc or "\\" in netloc:
        return True
    return False


def _is_safe_client_url(client: Any, url: str) -> Tuple[bool, str]:
    """Validate URL safety against SSRF, respecting real bool/set overrides on client."""
    if not url or not isinstance(url, str) or not url.strip():
        return False, "Empty or invalid URL"
    url_clean = url.strip()
    if any(ord(c) < 32 or ord(c) == 127 for c in url_clean):
        return False, "SSRF blocked: URL contains control characters"
    try:
        parsed = urllib.parse.urlsplit(url_clean)
    except ValueError as e:
        return False, f"Invalid URL syntax: {e}"
    if _has_unsafe_authority(parsed):
        return False, "SSRF blocked: Unsafe authority (userinfo or backslash) in URL"
    raw_allow = getattr(client, "allow_private_ips", False) if client is not None else False
    allow_private = raw_allow if isinstance(raw_allow, bool) else False
    raw_ports = getattr(client, "allowed_ports", None) if client is not None else None
    allowed_ports: Optional[Set[int]] = (
        set(raw_ports) if isinstance(raw_ports, (set, frozenset)) else None
    )
    return is_safe_url(url_clean, allow_private_ips=allow_private, allowed_ports=allowed_ports)


def _positive_float(value: Any, default: float) -> float:
    """Convert value to a positive finite float, or return default."""
    if value is None or isinstance(value, bool):
        return default
    try:
        num = float(value)
    except (ValueError, TypeError, OverflowError):
        return default
    if not math.isfinite(num) or num <= 0:
        return default
    return num


def _normalize_limit(limit: Any) -> Optional[int]:
    """Normalize an optional crawl limit into None or a non-negative integer."""
    if limit is None:
        return None
    if isinstance(limit, bool):
        return 0 if not limit else None
    try:
        num = float(limit)
    except (ValueError, TypeError, OverflowError):
        return 0
    if not math.isfinite(num):
        return None if num > 0 else 0
    if num <= 0:
        return 0
    return int(num)


def _normalize_pages(pages: Any, default: int = 1, max_pages: int = 1000) -> int:
    """Normalize a page count into an integer in [1, max_pages]."""
    if pages is None or isinstance(pages, bool):
        return default
    try:
        num = float(pages)
    except (ValueError, TypeError, OverflowError):
        return default
    if not math.isfinite(num) or num < 1:
        return default
    return min(max_pages, max(1, int(num)))


class BaseCrawler(abc.ABC):
    """
    Abstract base crawler providing standardized session warm-up,
    network fetching, and fault-tolerant post detail parsing.
    Subclasses implement parse_post_detail() for platform-specific DOM extraction.
    """

    def __init__(
        self,
        client: Optional[SafeHttpClient] = None,
        timeout: Union[float, Tuple[float, float]] = 15.0,
        connect_timeout: Optional[float] = None,
        read_timeout: Optional[float] = None,
        base_url: Optional[str] = None,
        enable_cache: bool = True,
        cache_fallback: bool = True,
    ):
        self._owns_client = client is None
        self._client_closed = False
        self.enable_cache = enable_cache
        self.cache_fallback = cache_fallback
        self._post_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._cache_lock = threading.RLock()

        # Resolve explicit connect and read timeouts
        scalar_timeout = _positive_float(timeout, -1.0) if not isinstance(timeout, (tuple, list)) else -1.0
        if connect_timeout is not None:
            self._connect_timeout = _positive_float(connect_timeout, 5.0)
        elif isinstance(timeout, (tuple, list)) and len(timeout) >= 2:
            self._connect_timeout = _positive_float(timeout[0], 5.0)
        elif scalar_timeout > 0 and (scalar_timeout != 15.0 or client is None):
            self._connect_timeout = min(5.0, scalar_timeout)
        elif client is not None and hasattr(client, "connect_timeout") and isinstance(getattr(client, "connect_timeout", None), (int, float)):
            self._connect_timeout = _positive_float(client.connect_timeout, 5.0)
        elif scalar_timeout > 0:
            self._connect_timeout = min(5.0, scalar_timeout)
        else:
            self._connect_timeout = 5.0

        if read_timeout is not None:
            self._read_timeout = _positive_float(read_timeout, 15.0)
        elif isinstance(timeout, (tuple, list)) and len(timeout) >= 2:
            self._read_timeout = _positive_float(timeout[1], 15.0)
        elif scalar_timeout > 0 and (scalar_timeout != 15.0 or client is None):
            self._read_timeout = scalar_timeout
        elif client is not None and hasattr(client, "read_timeout") and isinstance(getattr(client, "read_timeout", None), (int, float)):
            self._read_timeout = _positive_float(client.read_timeout, 15.0)
        elif scalar_timeout > 0:
            self._read_timeout = scalar_timeout
        else:
            self._read_timeout = 15.0

        self.default_timeout = self._read_timeout
        self.client = client or SafeHttpClient(
            timeout=(self._connect_timeout, self._read_timeout),
            connect_timeout=self._connect_timeout,
            read_timeout=self._read_timeout,
            enable_cache=self.enable_cache,
            cache_fallback=self.cache_fallback,
        )
        self.base_url: Optional[str] = base_url or getattr(self, "base_url", None)
        self._warmed_up = False

    @property
    def timeout(self) -> float:
        """Default network timeout for crawler requests."""
        return self.default_timeout

    @property
    def connect_timeout(self) -> float:
        """Connect timeout in seconds."""
        return self._connect_timeout

    @property
    def read_timeout(self) -> float:
        """Read timeout in seconds."""
        return self._read_timeout

    def _normalize_fetch_url(
        self,
        raw_url: str,
        base_url: Optional[str] = None,
    ) -> Optional[str]:
        """Normalize relative/entity-encoded URLs and reject malformed or unsafe authority syntax."""
        if not raw_url or not isinstance(raw_url, str) or not raw_url.strip():
            return None
        eff_url = _unescape_url_entities(raw_url.strip()).strip()
        if not eff_url or any(ord(c) < 32 or ord(c) == 127 for c in eff_url):
            return None
        try:
            parsed_input = urllib.parse.urlsplit(eff_url)
        except ValueError:
            return None
        if parsed_input.scheme:
            if parsed_input.scheme.lower() not in ("http", "https"):
                return None
            if not eff_url.lower().startswith(("http://", "https://")):
                return None

        eff_base = base_url if isinstance(base_url, str) and base_url.strip() else self.base_url
        if isinstance(eff_base, str) and any(ord(c) < 32 or ord(c) == 127 for c in eff_base):
            return None
        if eff_url.startswith("//"):
            base_scheme = "https"
            if isinstance(eff_base, str) and eff_base.strip():
                try:
                    base_scheme = urllib.parse.urlsplit(eff_base.strip()).scheme or "https"
                except ValueError:
                    base_scheme = "https"
            if base_scheme.lower() not in ("http", "https"):
                base_scheme = "https"
            eff_url = f"{base_scheme}:{eff_url}"
        elif not eff_url.lower().startswith(("http://", "https://")):
            if eff_base and isinstance(eff_base, str):
                eff_url = urllib.parse.urljoin(eff_base.strip(), eff_url)

        if any(ord(c) < 32 or ord(c) == 127 for c in eff_url):
            return None
        try:
            parsed_out = urllib.parse.urlsplit(eff_url)
            _ = parsed_out.port
        except ValueError:
            return None
        if not parsed_out.scheme or parsed_out.scheme.lower() not in ("http", "https"):
            return None
        if not parsed_out.hostname or any(c.isspace() for c in (parsed_out.netloc or "")):
            return None
        if _has_unsafe_authority(parsed_out):
            return None
        return eff_url

    def _resolve_timeout_arg(
        self,
        timeout: Any = None,
        connect_timeout: Any = None,
        read_timeout: Any = None,
    ) -> Tuple[float, float]:
        """Normalize timeout arguments into a positive finite (connect_timeout, read_timeout) tuple."""
        def_conn = getattr(self, "connect_timeout", 5.0)
        def_read = getattr(self, "read_timeout", 15.0)
        if timeout is None:
            return (
                _positive_float(connect_timeout, def_conn),
                _positive_float(read_timeout, def_read),
            )
        if isinstance(timeout, (tuple, list)) and len(timeout) >= 2:
            return (
                _positive_float(connect_timeout if connect_timeout is not None else timeout[0], def_conn),
                _positive_float(read_timeout if read_timeout is not None else timeout[1], def_read),
            )
        scalar = _positive_float(timeout, -1.0)
        if scalar > 0:
            return (
                _positive_float(connect_timeout, min(def_conn, scalar)),
                _positive_float(read_timeout, scalar),
            )
        return (
            _positive_float(connect_timeout, def_conn),
            _positive_float(read_timeout, def_read),
        )

    def _store_cached_post(self, post_url: str, detail: Dict[str, Any]) -> None:
        """Store parsed post detail in bounded LRU in-memory cache when caching is enabled."""
        if not self.enable_cache or not post_url or not isinstance(post_url, str) or not isinstance(detail, dict):
            return
        if MAX_POST_CACHE_SIZE <= 0:
            return
        key = post_url.strip()
        if not key:
            return
        with self._cache_lock:
            if key in self._post_cache:
                self._post_cache.move_to_end(key)
            else:
                while len(self._post_cache) >= MAX_POST_CACHE_SIZE:
                    self._post_cache.popitem(last=False)
            self._post_cache[key] = copy.deepcopy(detail)

    def _fallback_cached_post(self, post_url: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached post detail for fallback when cache_fallback is enabled."""
        if not self.cache_fallback or not post_url or not isinstance(post_url, str):
            return None
        raw_key = post_url.strip()
        with self._cache_lock:
            if raw_key in self._post_cache:
                if isinstance(self._post_cache, OrderedDict):
                    self._post_cache.move_to_end(raw_key)
                return copy.deepcopy(self._post_cache[raw_key])
            norm_key = self._normalize_fetch_url(raw_key)
            if norm_key and norm_key in self._post_cache:
                if isinstance(self._post_cache, OrderedDict):
                    self._post_cache.move_to_end(norm_key)
                return copy.deepcopy(self._post_cache[norm_key])
        return None

    def get_cached_post(self, post_url: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached post detail if present."""
        if not post_url or not isinstance(post_url, str):
            return None
        raw_key = post_url.strip()
        with self._cache_lock:
            if raw_key in self._post_cache:
                if isinstance(self._post_cache, OrderedDict):
                    self._post_cache.move_to_end(raw_key)
                return copy.deepcopy(self._post_cache[raw_key])
            norm_key = self._normalize_fetch_url(raw_key)
            if norm_key and norm_key in self._post_cache:
                if isinstance(self._post_cache, OrderedDict):
                    self._post_cache.move_to_end(norm_key)
                return copy.deepcopy(self._post_cache[norm_key])
        return None

    def clear_post_cache(self) -> None:
        """Clear cached post details."""
        with self._cache_lock:
            self._post_cache.clear()

    @property
    def is_warmed_up(self) -> bool:
        """Check if the crawler session has completed initial warm-up."""
        return self._warmed_up

    @property
    def cookies(self) -> Dict[str, str]:
        """Expose active session cookies as a key-value dictionary."""
        if hasattr(self.client, "get_cookie_dict"):
            return self.client.get_cookie_dict()
        if hasattr(self.client, "cookie_jar"):
            try:
                return {
                    c.name: c.value
                    for c in self.client.cookie_jar
                    if hasattr(c, "name") and hasattr(c, "value")
                }
            except Exception:
                pass
        return {}

    def ensure_warm_up(self, base_url: Optional[Union[str, bool]] = None, force: bool = False) -> bool:
        """Warm up session cookies on base URL if not already done."""
        if isinstance(base_url, bool):
            force = base_url
            base_url = None
        target_url = (base_url.strip() if isinstance(base_url, str) and base_url.strip() else None) or self.base_url
        if (not self._warmed_up or force) and target_url and isinstance(target_url, str):
            target_clean = target_url.strip()
            is_safe, reason = _is_safe_client_url(self.client, target_clean)
            if not is_safe:
                logger.warning(f"Blocked unsafe warm-up URL {target_clean!r}: {reason}")
                return False
            success = True
            try:
                if self.client and hasattr(self.client, "warm_up_session"):
                    res = self.client.warm_up_session(target_clean)
                    success = bool(res) if res is not None else True
            except Exception as e:
                logger.warning(f"Error during session warm up on {target_clean}: {e}")
                success = False
            self._warmed_up = True
            return success
        return self._warmed_up

    def clear_session(self) -> None:
        """Reset session cookies and warm-up state."""
        if hasattr(self.client, "clear_cookies"):
            try:
                self.client.clear_cookies()
            except Exception as e:
                logger.warning(f"Error clearing cookies: {e}")
        self._warmed_up = False

    def is_circuit_open(self, url_or_host: Optional[str] = None) -> bool:
        """Check if circuit breaker is OPEN for the target crawler host."""
        target = url_or_host or self.base_url or ""
        if hasattr(self.client, "is_circuit_open"):
            return bool(self.client.is_circuit_open(target))
        cb = getattr(self.client, "circuit_breaker", None)
        if cb is not None and hasattr(cb, "is_open"):
            return bool(cb.is_open(target))
        return False

    def get_circuit_state(self, url_or_host: Optional[str] = None) -> str:
        """Return the circuit breaker state (CLOSED, OPEN, HALF_OPEN) for this host."""
        target = url_or_host or self.base_url or ""
        if hasattr(self.client, "get_circuit_state"):
            return str(self.client.get_circuit_state(target))
        cb = getattr(self.client, "circuit_breaker", None)
        if cb is not None and hasattr(cb, "get_state"):
            return str(cb.get_state(target))
        return "CLOSED"

    def load_seed_fallback(
        self,
        platform_name: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Load fallback records from seed datasets in data/ if live crawl is unavailable."""
        eff_limit = _normalize_limit(limit)
        if eff_limit is not None and eff_limit <= 0:
            return []
        seed_posts: List[Dict[str, Any]] = []
        target_platform = (platform_name or getattr(self, "platform", "") or "").lower().strip()
        seed_files: List[str] = []
        if target_platform and re.fullmatch(r"[a-z0-9_-]+", target_platform):
            seed_files.append(f"raw_{target_platform}_emerging.json")
            if target_platform == "bobaedream":
                seed_files.append("raw_bobae_emerging.json")
        seed_files.append("compiled_complaints.json")
        curr_p = Path(__file__).resolve().parent
        search_dirs = [
            curr_p.parent / "data",
            curr_p.parent.parent / "data",
            Path.cwd() / "data",
            Path.cwd() / "ev-stealth-web" / "data",
        ]
        seen_ids = set()
        for s_dir in search_dirs:
            if not s_dir.is_dir():
                continue
            for s_name in seed_files:
                if not s_name:
                    continue
                s_file = s_dir / s_name
                if s_file.is_file():
                    try:
                        with open(s_file, "r", encoding="utf-8-sig") as f:
                            data = json.load(f)
                        if isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict):
                                    item_plat = str(item.get("platform") or "").lower()
                                    if target_platform and item_plat and item_plat != target_platform:
                                        continue
                                    raw_id = item.get("id")
                                    if raw_id is None or raw_id == "":
                                        raw_id = item.get("post_id")
                                    pid = str(raw_id) if raw_id is not None and raw_id != "" else ""
                                    if pid and pid in seen_ids:
                                        continue
                                    if pid:
                                        seen_ids.add(pid)
                                    norm_item = dict(item)
                                    if "post_title" in norm_item and "title" not in norm_item:
                                        norm_item["title"] = norm_item["post_title"]
                                    if "post_url" in norm_item and "url" not in norm_item:
                                        norm_item["url"] = norm_item["post_url"]
                                    if "raw_quote" in norm_item and "content" not in norm_item:
                                        norm_item["content"] = norm_item["raw_quote"]
                                    seed_posts.append(norm_item)
                                    if eff_limit is not None and len(seed_posts) >= eff_limit:
                                        return seed_posts
                    except Exception as e:
                        logger.debug(f"Failed reading seed file {s_file}: {e}")
            if seed_posts:
                break
        return seed_posts[:eff_limit] if eff_limit is not None else seed_posts

    def reset_session(self) -> None:
        """Alias for clear_session() to reinitialize session state."""
        self.clear_session()

    def close(self, force: bool = False) -> None:
        """Release HTTP client resources and close session."""
        if self._owns_client or force:
            try:
                self.clear_session()
            except Exception:
                pass
            if not self._client_closed and hasattr(self.client, "close"):
                self._client_closed = True
                try:
                    self.client.close()
                except Exception as e:
                    logger.warning(f"Error closing HTTP client: {e}")
        else:
            self._warmed_up = False

    def __del__(self) -> None:
        """Safely release underlying client resources on garbage collection if owned."""
        try:
            if getattr(self, "_owns_client", False):
                self.close()
        except Exception:
            pass

    def __enter__(self) -> "BaseCrawler":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.close()
        return False

    @abc.abstractmethod
    def parse_post_detail(
        self,
        html_content: str,
        post_url: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Extract structured post data from HTML content.
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement parse_post_detail()")

    def build_list_url(self, *args: Any, **kwargs: Any) -> str:
        """Construct a board or gallery list URL. Subclasses can override."""
        raise NotImplementedError("Subclasses may implement build_list_url()")

    def build_search_url(self, *args: Any, **kwargs: Any) -> str:
        """Construct a search query URL. Subclasses can override."""
        raise NotImplementedError("Subclasses may implement build_search_url()")

    def crawl_posts_by_keyword(
        self,
        keyword: str,
        limit: int = 20,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """Crawl posts matching a search keyword. Subclasses can override."""
        return []

    def fetch_ajax_comments(
        self,
        post_url: str,
        *args: Any,
        **kwargs: Any,
    ) -> List[str]:
        """Fetch asynchronous comments for a post. Subclasses can override."""
        return []

    def fetch_post(
        self,
        post_url: str,
        referer: Optional[str] = None,
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch HTML for post_url and parse structured detail.
        Includes safe try...except handling around parse_post_detail() so that
        corrupt HTML, broken DOMs, or unexpected markup do not crash the scrape loop.
        """
        base_url = kwargs.get("base_url") or self.base_url
        eff_url = self._normalize_fetch_url(post_url, base_url=base_url if isinstance(base_url, str) else None)
        if not eff_url:
            logger.warning(f"Invalid or unsafe post_url provided to fetch_post: {post_url!r}")
            return None

        is_safe, reason = _is_safe_client_url(self.client, eff_url)
        if not is_safe:
            logger.warning(f"SSRF defense blocked fetch_post URL {eff_url!r}: {reason}")
            return None

        if not self.client:
            logger.warning(f"No HTTP client configured on {self.__class__.__name__}")
            return None
        self.ensure_warm_up(base_url)

        eff_referer = _sanitize_referer(referer)
        timeout = self._resolve_timeout_arg(
            kwargs.get("timeout"),
            kwargs.get("connect_timeout"),
            kwargs.get("read_timeout"),
        )
        try:
            resp = self.client.get(eff_url, referer=eff_referer, timeout=timeout)
            if not resp or not isinstance(resp, (tuple, list)) or len(resp) < 2:
                logger.warning(f"Failed to fetch post: {eff_url} (empty or invalid response)")
                cached = self._fallback_cached_post(eff_url)
                if cached is not None:
                    logger.warning(f"Falling back to cached post detail for {eff_url}")
                    return cached
                return None
            status, text = resp[0], resp[1]
        except Exception as e:
            logger.warning(f"Network error fetching post {eff_url}: {e}")
            cached = self._fallback_cached_post(eff_url)
            if cached is not None:
                logger.warning(f"Falling back to cached post detail for {eff_url}")
                return cached
            return None

        if status == 429:
            logger.warning(f"Rate-limited (HTTP 429) fetching post {eff_url}. Degrading gracefully.")
            return self._fallback_cached_post(eff_url)

        if isinstance(text, (bytes, bytearray, memoryview)):
            text = robust_decode(text)

        if status != 200 or not text:
            logger.warning(f"Failed to fetch post: {eff_url} (status: {status})")
            cached = self._fallback_cached_post(eff_url)
            if cached is not None:
                logger.warning(f"Falling back to cached post detail for {eff_url}")
                return cached
            return None

        try:
            detail = self.parse_post_detail(text, eff_url, **kwargs)
            if not isinstance(detail, dict):
                logger.warning(f"parse_post_detail returned non-dict ({type(detail)}) for {eff_url}")
                return None
            if (
                detail.get("is_deleted")
                or detail.get("is_restricted")
                or detail.get("status")
                in (
                    "deleted_post",
                    "restricted_post",
                    "cloudflare_challenge",
                    "abnormal_access_blocked",
                    "ip_blocked",
                    "captcha_challenge",
                    "access_denied",
                    "service_maintenance",
                )
            ):
                return None
            self._store_cached_post(eff_url, detail)
            return detail
        except Exception as e:
            logger.warning(
                f"Error parsing post detail for {eff_url} on corrupt HTML: {e}"
            )
            return self._fallback_cached_post(eff_url)
