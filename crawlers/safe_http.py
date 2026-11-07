"""
Thread-Safe, Rate-Limited HTTP Client & Parser Utilities for Korean Community Crawlers.
Exports SafeHttpClient and utilities matching utils.http_client interface specifications.
"""

from __future__ import annotations

from utils.http_client import (
    MAX_COOKIEJAR_ENTRIES,
    MAX_RESPONSE_BYTES,
    USER_AGENT_POOL,
    SafeHttpClient,
    clean_html_text,
    encode_euc_kr_query,
    robust_decode,
)

__all__ = [
    "SafeHttpClient",
    "clean_html_text",
    "encode_euc_kr_query",
    "robust_decode",
    "USER_AGENT_POOL",
    "MAX_RESPONSE_BYTES",
    "MAX_COOKIEJAR_ENTRIES",
]
