"""
BobaeDream Community Crawler module alias.
Standard export conforming to naming conventions.
"""

from __future__ import annotations

from crawlers.bobaedream import (
    BOBAE_BASE_URL,
    BOBAE_LIST_URL,
    BOBAE_VIEW_URL,
    TARGET_BOARDS,
    BobaeDreamCrawler,
    BobaedreamCrawler,
    _normalize_iso_timestamp,
    clean_title_text,
    extract_container_content,
    is_deleted_or_restricted,
)

__all__ = [
    "BOBAE_BASE_URL",
    "BOBAE_LIST_URL",
    "BOBAE_VIEW_URL",
    "TARGET_BOARDS",
    "BobaeDreamCrawler",
    "BobaedreamCrawler",
    "_normalize_iso_timestamp",
    "clean_title_text",
    "extract_container_content",
    "is_deleted_or_restricted",
]
