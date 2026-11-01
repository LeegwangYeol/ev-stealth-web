"""
DCInside Gallery Crawler module alias.
Standard export conforming to naming conventions.
"""

from __future__ import annotations

from crawlers.dcinside import (
    DC_BASE_URL,
    DC_GALLERIES,
    DC_MOBILE_BASE_URL,
    DCInsideCrawler,
    DcInsideCrawler,
    _normalize_iso_timestamp,
    extract_container_content,
)

__all__ = [
    "DC_BASE_URL",
    "DC_MOBILE_BASE_URL",
    "DC_GALLERIES",
    "DCInsideCrawler",
    "DcInsideCrawler",
    "_normalize_iso_timestamp",
    "extract_container_content",
]
