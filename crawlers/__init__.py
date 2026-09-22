"""
Community Crawler Modules for BobaeDream and DCInside.
"""

from .base_crawler import BaseCrawler
from .bobaedream import BobaeDreamCrawler
from .dcinside import DCInsideCrawler

__all__ = ["BaseCrawler", "BobaeDreamCrawler", "DCInsideCrawler"]
