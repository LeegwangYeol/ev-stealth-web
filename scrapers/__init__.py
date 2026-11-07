"""
Scrapers Package for Chinese EV / BYD Community Forum Mining.
Modules:
- common_utils: SafeHttpClient, ComplaintRecord, rate limiter, encoding handlers
- bobaedream_scraper: Bobaedream forum multi-board crawler and parser
- dcinside_scraper: DC Inside major/minor gallery scraper and comment parser
- blind_scraper: Blind Korea public automotive discussion crawler and parser
- cafe_forum_miner: Pomppu, Clien, Naver Cafe, and YouTube comment miner
"""

from scrapers.common_utils import (
    ComplaintRecord,
    SafeHttpClient,
    clean_html_text,
    encode_euc_kr_query,
    extract_slang_terms,
    get_random_headers,
    load_complaints_json,
    polite_delay,
    robust_decode,
    save_complaints_json,
)

__all__ = [
    "ComplaintRecord",
    "SafeHttpClient",
    "clean_html_text",
    "encode_euc_kr_query",
    "extract_slang_terms",
    "get_random_headers",
    "load_complaints_json",
    "polite_delay",
    "robust_decode",
    "save_complaints_json",
]
