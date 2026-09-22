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

    def ensure_warm_up(self, base_url: Optional[str] = None):
        """Warm up session cookies on base URL if not already done."""
        if not self._warmed_up and base_url:
            self.client.warm_up_session(base_url)
            self._warmed_up = True

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
        base_url = kwargs.get("base_url")
        self.ensure_warm_up(base_url)
        status, text, _ = self.client.get(post_url, referer=referer)
        if status != 200 or not text:
            logger.warning(f"Failed to fetch post: {post_url} (status: {status})")
            return None

        try:
            return self.parse_post_detail(text, post_url, **kwargs)
        except Exception as e:
            logger.warning(
                f"Error parsing post detail for {post_url} on corrupt HTML: {e}"
            )
            return None
