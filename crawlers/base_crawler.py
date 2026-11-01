"""
Abstract BaseCrawler interface and fault-tolerant parsing foundation
for community forum web scrapers (BobaeDream, DCInside, etc.).
"""

from __future__ import annotations

import abc
import logging
from typing import Any, Dict, List, Optional

from utils.http_client import SafeHttpClient

logger = logging.getLogger("BaseCrawler")


class BaseCrawler(abc.ABC):
    """
    Abstract base crawler providing standardized session warm-up,
    network fetching, and fault-tolerant post detail parsing.
    Subclasses implement parse_post_detail() for platform-specific DOM extraction.
    """

    def __init__(self, client: Optional[SafeHttpClient] = None):
        self.client = client or SafeHttpClient()
        self._warmed_up = False

    def ensure_warm_up(self, base_url: Optional[str] = None, force: bool = False):
        """Warm up session cookies on base URL if not already done."""
        if isinstance(base_url, bool):
            force = base_url
            base_url = None
        if (not self._warmed_up or force) and base_url and isinstance(base_url, str):
            self.client.warm_up_session(base_url)
            self._warmed_up = True

    def clear_session(self) -> None:
        """Reset session cookies and warm-up state."""
        if hasattr(self.client, "clear_cookies"):
            self.client.clear_cookies()
        self._warmed_up = False

    def close(self) -> None:
        """Release HTTP client resources and close session."""
        self.clear_session()
        if hasattr(self.client, "close"):
            self.client.close()

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

        base_url = kwargs.get("base_url")
        self.ensure_warm_up(base_url)
        timeout = kwargs.get("timeout")
        status, text, _ = self.client.get(post_url, referer=referer, timeout=timeout)
        if status != 200 or not text:
            logger.warning(f"Failed to fetch post: {post_url} (status: {status})")
            return None

        try:
            detail = self.parse_post_detail(text, post_url, **kwargs)
            if not isinstance(detail, dict):
                logger.warning(f"parse_post_detail returned non-dict ({type(detail)}) for {post_url}")
                return None
            return detail
        except Exception as e:
            logger.warning(
                f"Error parsing post detail for {post_url} on corrupt HTML: {e}"
            )
            return None
