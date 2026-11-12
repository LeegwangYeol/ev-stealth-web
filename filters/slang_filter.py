"""Korean EV Automotive Slang Filtering and Contextual Extraction Engine.

Provides high-performance, Unicode-normalized, case-resilient slang filtering
and tag extraction for community defect crawling and classification.

Authoritative reference:
/Users/a7890/src/my-e-car/.agents/spec_miner_nlp_workflow/specifications.md § 2.1
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple, Union
import unicodedata

from filters.defect_classifier import RE_INVALID_CHARS, sanitize_text

from filters.slang_lexicon import (
    CONCESSIVES,
    DIMINISHERS,
    LAUGHING_MARKERS,
    NEGATORS,
    NEWS_PATTERNS,
    OWNERSHIP_ANCHORS,
    RAW_SLANG_ENTRIES,
    SARCASM_PRAISE_WORDS,
    SLANG_CATALOG,
    STANDARD_INTENSIFIERS,
    STOCK_TERMS,
    SUPER_INTENSIFIERS,
    SYMPTOM_PREDICATES,
    SlangEntry,
    _SORTED_SLANG_ENTRIES,
    find_matching_slang,
)

MAX_POST_TEXT_LENGTH: int = 50_000


class SlangFilter:
    """Enterprise-grade Korean EV community slang filter and extractor."""

    def __init__(self, max_length: int = MAX_POST_TEXT_LENGTH) -> None:
        self.max_length = max_length
        self.slang_catalog = SLANG_CATALOG
        self.raw_entries = RAW_SLANG_ENTRIES

    def normalize_text(self, text: Any) -> str:
        """Safely normalizes input text: null/empty guards, control char, BiDi override & surrogate stripping,
        NFC Unicode normalization, and length bounding."""
        return sanitize_text(text, max_len=self.max_length)

    def find_matching_slang(self, text: Any) -> List[SlangEntry]:
        """Identify all slang entries present in the given text with Unicode & case resilience."""
        return find_matching_slang(text)

    def filter_slang(self, text: Any) -> List[SlangEntry]:
        """Alias for find_matching_slang."""
        return self.find_matching_slang(text)

    def extract_slang_tags(self, text: Any) -> List[str]:
        """Extract unique slang term strings matching in the text."""
        entries = self.find_matching_slang(text)
        seen: Set[str] = set()
        tags: List[str] = []
        for e in entries:
            if e.term not in seen:
                seen.add(e.term)
                tags.append(e.term)
        return tags

    def is_slang_present(self, text: Any, term_or_category: Optional[str] = None) -> bool:
        """Check if any slang (or a specific term / defect category) is present in the text."""
        entries = self.find_matching_slang(text)
        if not entries:
            return False
        if term_or_category is None:
            return True
        target = str(term_or_category).strip().upper()
        for e in entries:
            if e.term == term_or_category or (e.defect_category and e.defect_category.upper() == target):
                return True
            if e.dimension and e.dimension.upper() == target:
                return True
        return False

    def classify_slang_dimensions(self, text: Any) -> Dict[str, List[SlangEntry]]:
        """Group detected slang entries by their core dimension."""
        entries = self.find_matching_slang(text)
        grouped: Dict[str, List[SlangEntry]] = {}
        for e in entries:
            grouped.setdefault(e.dimension, []).append(e)
        return grouped


# Module-level convenience functions
def extract_slang_tags(text: Any) -> List[str]:
    return SlangFilter().extract_slang_tags(text)


def is_slang_present(text: Any, term_or_category: Optional[str] = None) -> bool:
    return SlangFilter().is_slang_present(text, term_or_category)


def filter_slang(text: Any) -> List[SlangEntry]:
    return find_matching_slang(text)


def normalize_text(text: Any) -> str:
    return SlangFilter().normalize_text(text)


__all__ = [
    "SlangFilter",
    "SlangEntry",
    "SLANG_CATALOG",
    "RAW_SLANG_ENTRIES",
    "SUPER_INTENSIFIERS",
    "STANDARD_INTENSIFIERS",
    "DIMINISHERS",
    "NEGATORS",
    "CONCESSIVES",
    "SARCASM_PRAISE_WORDS",
    "LAUGHING_MARKERS",
    "NEWS_PATTERNS",
    "STOCK_TERMS",
    "OWNERSHIP_ANCHORS",
    "SYMPTOM_PREDICATES",
    "find_matching_slang",
    "extract_slang_tags",
    "is_slang_present",
    "filter_slang",
    "normalize_text",
    "MAX_POST_TEXT_LENGTH",
]
