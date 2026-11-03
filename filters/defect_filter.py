"""4-Stage Contextual EV Defect & Korean Slang Classification Engine.

Implements the multi-stage filter and scoring pipelines:
- Stage 1: Noise & Exclusion Filter (Journalistic, Stock spam, Pure flame wars)
- Stage 2: Ownership Anchor & Operational Symptom Verification
- Stage 3: Negation, Concessive Scoping, and Sarcasm Resolution
- Stage 4: Defect Actionability Gate & 5-Pillar Taxonomy Classification

Scoring engines:
- Sentiment Polarity P in [-1.0, 1.0]
- Normalized Defect Negativity N_score in [0.0, 1.0]
- 5-Dimensional Defect Severity Index (DSI) in [0.0, 10.0]

Authoritative reference:
/Users/a7890/src/my-e-car/.agents/spec_miner_nlp_workflow/specifications.md § 2.2 - § 2.4
/Users/a7890/src/my-e-car/.agents/orchestrator_daily_monitor/PROJECT.md § Interface Contracts
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from filters.defect_classifier import (
    COMPOUND_DEFECT_RULES,
    NEGATIVE_LEXICON,
    POSITIVE_LEXICON,
    DefectClassifier,
)
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
    find_matching_slang,
)
from filters.spam_filter import (
    CATEGORY_KEYWORD_MAP,
    COMMERCIAL_SPAM_KEYWORDS,
    DEFECT_QUESTION_KEYWORDS,
    NEWS_DOMAINS,
    NEWS_REGEXES,
    SpamFilter,
    evaluate_stage1_noise,
    is_spam,
)
from filters.vehicle_matcher import extract_vehicle_info
from models.complaint import (
    CANONICAL_CATEGORIES,
    DEFECT_CATEGORY_KO_MAP,
    ComplaintRecord,
    DSIBreakdown,
    RawPost,
)


class ContextualDefectFilter(DefectClassifier):
    """4-Stage Contextual Filtering and Defect Classification Engine."""
    pass


# Primary alias for callers
DefectFilter = ContextualDefectFilter
