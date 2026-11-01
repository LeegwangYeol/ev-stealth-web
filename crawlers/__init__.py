"""
Community Crawler Modules for BobaeDream and DCInside.
"""

from .base_crawler import BaseCrawler
from .bobaedream import BobaeDreamCrawler, BobaedreamCrawler
from .dcinside import DCInsideCrawler, DcInsideCrawler

__all__ = [
    "BaseCrawler",
    "BobaeDreamCrawler",
    "BobaedreamCrawler",
    "DCInsideCrawler",
    "DcInsideCrawler",
]
