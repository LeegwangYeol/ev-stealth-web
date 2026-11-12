"""
Abstract BaseCrawler interface and fault-tolerant parsing foundation
for community forum web scrapers (BobaeDream, DCInside, etc.).
"""

from __future__ import annotations

import abc
import logging
from typing import Any, Dict, List, Optional, Union

from utils.http_client import SafeHttpClient

logger = logging.getLogger("BaseCrawler")


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
        self.enable_cache = enable_cache
        self.cache_fallback = cache_fallback
        self._post_cache: Dict[str, Dict[str, Any]] = {}

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
        elif isinstance(timeout, (int, float)) and timeout > 0 and (timeout != 15.0 or client is None):
            self._connect_timeout = min(5.0, float(timeout))
        elif client is not None and hasattr(client, "connect_timeout") and isinstance(getattr(client, "connect_timeout", None), (int, float)):
            self._connect_timeout = float(client.connect_timeout)
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
        elif isinstance(timeout, (int, float)) and timeout > 0 and (timeout != 15.0 or client is None):
            self._read_timeout = float(timeout)
        elif client is not None and hasattr(client, "read_timeout") and isinstance(getattr(client, "read_timeout", None), (int, float)):
            self._read_timeout = float(client.read_timeout)
        elif isinstance(timeout, (int, float)) and timeout > 0:
            self._read_timeout = float(timeout)
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

    def get_cached_post(self, post_url: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached post detail if present."""
        if not post_url or not isinstance(post_url, str):
            return None
        return self._post_cache.get(post_url.strip())

    def clear_post_cache(self) -> None:
        """Clear cached post details."""
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
        target_url = (base_url if isinstance(base_url, str) else None) or self.base_url
        if (not self._warmed_up or force) and target_url and isinstance(target_url, str):
            success = True
            try:
                if self.client and hasattr(self.client, "warm_up_session"):
                    res = self.client.warm_up_session(target_url)
                    success = bool(res) if res is not None else True
            except Exception as e:
                logger.warning(f"Error during session warm up on {target_url}: {e}")
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

    def reset_session(self) -> None:
        """Alias for clear_session() to reinitialize session state."""
        self.clear_session()

    def close(self, force: bool = False) -> None:
        """Release HTTP client resources and close session."""
        try:
            self.clear_session()
        except Exception:
            pass
        if (self._owns_client or force) and hasattr(self.client, "close"):
            try:
                self.client.close()
            except Exception as e:
                logger.warning(f"Error closing HTTP client: {e}")

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
        if not post_url or not isinstance(post_url, str) or not post_url.strip():
            logger.warning(f"Invalid post_url provided to fetch_post: {post_url!r}")
            return None

        eff_url = post_url.strip()
        base_url = kwargs.get("base_url") or self.base_url
        if not (eff_url.startswith("http://") or eff_url.startswith("https://")):
            if base_url:
                base_clean = base_url.rstrip("/")
                path_clean = eff_url.lstrip("/")
                eff_url = f"{base_clean}/{path_clean}"

        self.ensure_warm_up(base_url)
        if not self.client:
            logger.warning(f"No HTTP client configured on {self.__class__.__name__}")
            return None

        timeout = kwargs.get(
            "timeout",
            (
                kwargs.get("connect_timeout", getattr(self, "connect_timeout", 5.0)),
                kwargs.get("read_timeout", getattr(self, "read_timeout", 15.0)),
            ),
        )
        try:
            resp = self.client.get(eff_url, referer=referer, timeout=timeout)
            if not resp or not isinstance(resp, (tuple, list)) or len(resp) < 2:
                logger.warning(f"Failed to fetch post: {eff_url} (empty or invalid response)")
                if self.cache_fallback and eff_url in self._post_cache:
                    logger.warning(f"Falling back to cached post detail for {eff_url}")
                    return self._post_cache[eff_url]
                return None
            status, text = resp[0], resp[1]
        except Exception as e:
            logger.warning(f"Network error fetching post {eff_url}: {e}")
            if self.cache_fallback and eff_url in self._post_cache:
                logger.warning(f"Falling back to cached post detail for {eff_url}")
                return self._post_cache[eff_url]
            return None

        if status == 429:
            logger.warning(f"Rate-limited (HTTP 429) fetching post {eff_url}. Degrading gracefully.")
            if self.cache_fallback and eff_url in self._post_cache:
                return self._post_cache[eff_url]
            return None

        if status != 200 or not text:
            logger.warning(f"Failed to fetch post: {eff_url} (status: {status})")
            if self.cache_fallback and eff_url in self._post_cache:
                logger.warning(f"Falling back to cached post detail for {eff_url}")
                return self._post_cache[eff_url]
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
            if self.enable_cache:
                self._post_cache[eff_url] = detail
            return detail
        except Exception as e:
            logger.warning(
                f"Error parsing post detail for {eff_url} on corrupt HTML: {e}"
            )
            if self.cache_fallback and eff_url in self._post_cache:
                return self._post_cache[eff_url]
            return None
