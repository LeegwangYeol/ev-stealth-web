"""Filters package for EV defect classification and context analysis."""

from filters.slang_lexicon import (
    RAW_SLANG_ENTRIES,
    SLANG_CATALOG,
    SUPER_INTENSIFIERS,
    STANDARD_INTENSIFIERS,
    DIMINISHERS,
    NEGATORS,
    CONCESSIVES,
    SARCASM_PRAISE_WORDS,
    LAUGHING_MARKERS,
    NEWS_PATTERNS,
    STOCK_TERMS,
    OWNERSHIP_ANCHORS,
    SYMPTOM_PREDICATES,
    SlangEntry,
    find_matching_slang,
)

__all__ = [
    "SLANG_CATALOG",
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
    "SlangEntry",
    "find_matching_slang",
]
