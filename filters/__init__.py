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
from filters.slang_filter import (
    SlangFilter,
    extract_slang_tags,
    filter_slang,
    is_slang_present,
    normalize_text,
)
from filters.defect_classifier import (
    DefectClassifier,
    ContextualDefectFilter,
    normalize_date,
    sanitize_text,
)
from filters.defect_filter import DefectFilter
from filters.spam_filter import (
    SpamFilter,
    evaluate_stage1_noise,
    is_spam,
    sanitize_input,
)
from filters.vehicle_matcher import (
    VehicleMatcher,
    extract_vehicle_info,
)

__all__ = [
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
    "SlangEntry",
    "find_matching_slang",
    "SlangFilter",
    "filter_slang",
    "extract_slang_tags",
    "is_slang_present",
    "normalize_text",
    "DefectClassifier",
    "ContextualDefectFilter",
    "DefectFilter",
    "normalize_date",
    "sanitize_text",
    "SpamFilter",
    "evaluate_stage1_noise",
    "is_spam",
    "sanitize_input",
    "VehicleMatcher",
    "extract_vehicle_info",
]
