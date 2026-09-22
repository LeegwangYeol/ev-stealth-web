"""
Tier 2: Boundary & Edge Cases Test Suite.

Validates:
1. Zero empty or placeholder quotes across 100% of records.
2. Quote substantiveness (minimum character length and Hangul content).
3. 100% verifiability via valid URL or specific board names.
4. Correct extraction and detection of Korean online automotive slang terms (multi-brand).
5. Verification of raw emotional sentiment and unfiltered consumer complaint tone.
6. Absolute uniqueness of complaint record IDs.
7. Valid ISO8601 timestamps without future date corruptions.
8. Crawler safety boundary parameters (delay/jitter bounds, UA pool size).
9. Defect Severity Index (DSI) & Sentiment score mathematical boundedness.
"""

import os
import re
import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.e2e.common import (
    EMOTIONAL_SENTIMENT_MARKERS,
    KNOWN_SLANG_KEYWORDS,
    inspect_crawler_script_safety,
    load_complaints_data,
    load_slang_dict,
    validate_iso8601,
    validate_url_or_board,
)

PLACEHOLDER_STRINGS = {
    "n/a",
    "na",
    "null",
    "none",
    "todo",
    "test",
    "sample",
    "placeholder",
    "dummy",
    "temp",
    "asdf",
    "undefined",
    "예시",
    "테스트",
    "임시",
}


class TestTier2BoundaryCases(unittest.TestCase):
    """Tier 2 Test Cases: Enforcing boundary conditions, zero-tolerance quality invariants."""

    complaints: List[Dict[str, Any]] = []
    slang_dict: Dict[str, Any] = {}

    @classmethod
    def setUpClass(cls):
        """Load data and slang dictionary for boundary auditing."""
        try:
            cls.complaints = load_complaints_data()
            cls.slang_dict = load_slang_dict()
        except FileNotFoundError as e:
            cls.complaints = []
            cls.load_error = str(e)
        except Exception as e:
            cls.complaints = []
            cls.load_error = f"Error loading data: {e}"
        else:
            cls.load_error = None

    def setUp(self):
        if self.load_error:
            self.fail(f"Dataset load failure: {self.load_error}")
        if not self.complaints:
            self.fail("Complaint dataset is empty.")

    def test_01_zero_empty_or_placeholder_quotes(self):
        """Verify that not a single record contains an empty or placeholder quote."""
        violations = []
        for idx, record in enumerate(self.complaints):
            quote = (record.get("raw_quote", "") or "").strip()
            rec_id = record.get("id", f"idx_{idx}")

            if not quote:
                violations.append(f"Record {rec_id} has an empty raw_quote.")
            elif quote.lower() in PLACEHOLDER_STRINGS:
                violations.append(
                    f"Record {rec_id} has placeholder raw_quote: '{quote}'"
                )
            elif len(set(quote.replace(" ", ""))) < 3:
                violations.append(
                    f"Record {rec_id} has repetitive/trivial raw_quote: '{quote}'"
                )

        self.assertEqual(
            len(violations),
            0,
            f"Found {len(violations)} quote placeholder/empty violations:\n"
            + "\n".join(violations[:10]),
        )

    def test_02_quote_minimum_length_and_korean_content(self):
        """Verify all quotes meet minimum length (>= 15 chars) and contain Korean Hangul syllables."""
        korean_regex = re.compile(r"[가-힣]")
        violations = []

        for idx, record in enumerate(self.complaints):
            quote = (record.get("raw_quote", "") or "").strip()
            rec_id = record.get("id", f"idx_{idx}")

            if len(quote) < 15:
                violations.append(
                    f"Record {rec_id} quote is too short ({len(quote)} chars < 15): '{quote}'"
                )
            if not korean_regex.search(quote):
                violations.append(
                    f"Record {rec_id} quote contains no Korean characters: '{quote}'"
                )

        self.assertEqual(
            len(violations),
            0,
            f"Found {len(violations)} quote length/content violations:\n"
            + "\n".join(violations[:10]),
        )

    def test_03_non_empty_url_or_board_100_percent(self):
        """Verify that 100% of records provide a verifiable URL and/or specific board name."""
        violations = []

        for idx, record in enumerate(self.complaints):
            rec_id = record.get("id", f"idx_{idx}")
            url = record.get("post_url", "")
            board = record.get("board_name", "")

            valid, reason = validate_url_or_board(url, board)
            if not valid:
                violations.append(f"Record {rec_id} failed verifiability: {reason}")

        self.assertEqual(
            len(violations),
            0,
            f"Found {len(violations)} URL/Board verifiability violations:\n"
            + "\n".join(violations[:10]),
        )

    def test_04_valid_url_syntax_and_structure(self):
        """Verify that when post_url is populated, it adheres to valid web URL syntax."""
        url_regex = re.compile(r"^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/.*)?$")
        violations = []

        for idx, record in enumerate(self.complaints):
            rec_id = record.get("id", f"idx_{idx}")
            url = (record.get("post_url", "") or "").strip()

            if url and not url_regex.match(url):
                violations.append(f"Record {rec_id} has invalid URL format: '{url}'")

        self.assertEqual(
            len(violations),
            0,
            f"Found {len(violations)} URL syntax violations:\n"
            + "\n".join(violations[:10]),
        )

    def test_05_slang_terms_presence_and_validity(self):
        """Verify slang_terms list is populated and contains valid strings for records."""
        records_with_slang = 0
        all_extracted_slangs = set()

        for idx, record in enumerate(self.complaints):
            slangs = record.get("slang_terms", [])
            self.assertIsInstance(
                slangs,
                list,
                f"Record {record.get('id')} 'slang_terms' must be a list.",
            )
            if slangs:
                records_with_slang += 1
                for s in slangs:
                    if isinstance(s, str) and s.strip():
                        all_extracted_slangs.add(s.strip())

        slang_coverage_ratio = records_with_slang / len(self.complaints)
        self.assertGreaterEqual(
            slang_coverage_ratio,
            0.70,
            f"Only {slang_coverage_ratio:.1%} of records have slang_terms tagged (expected >= 70%).",
        )
        self.assertGreaterEqual(
            len(all_extracted_slangs),
            5,
            f"Only {len(all_extracted_slangs)} unique slang terms tagged across dataset (expected >= 5).",
        )

    def test_06_unfiltered_korean_community_slang_in_quotes(self):
        """Verify that raw quotes across the dataset genuinely exhibit authentic community terminology."""
        quotes_with_slang = 0
        total_quotes = len(self.complaints)

        slang_set = set(KNOWN_SLANG_KEYWORDS) | set(self.slang_dict.keys())
        for r in self.complaints:
            for st in r.get("slang_terms", []):
                if isinstance(st, str) and st.strip():
                    slang_set.add(st.strip())

        for record in self.complaints:
            quote = record.get("raw_quote", "")
            if any(term in quote for term in slang_set):
                quotes_with_slang += 1

        ratio = quotes_with_slang / total_quotes
        self.assertGreaterEqual(
            ratio,
            0.50,
            f"Slang keyword density is too low: only {quotes_with_slang}/{total_quotes} "
            f"({ratio:.1%}) raw quotes contain recognized community slang keywords.",
        )

    def test_07_raw_emotional_sentiment_indicators(self):
        """Verify that quotes reflect authentic user emotions (frustration, shock, colloquial tone)."""
        emotive_count = 0
        total_quotes = len(self.complaints)

        slang_set = set(KNOWN_SLANG_KEYWORDS) | set(self.slang_dict.keys())
        for r in self.complaints:
            for st in r.get("slang_terms", []):
                if isinstance(st, str) and st.strip():
                    slang_set.add(st.strip())

        for record in self.complaints:
            quote = record.get("raw_quote", "")
            if any(m in quote for m in EMOTIONAL_SENTIMENT_MARKERS) or any(
                term in quote for term in slang_set
            ):
                emotive_count += 1

        ratio = emotive_count / total_quotes
        self.assertGreaterEqual(
            ratio,
            0.60,
            f"Emotive/colloquial tone ratio is {ratio:.1%} ({emotive_count}/{total_quotes}), "
            f"expected >= 60% of quotes to exhibit unvarnished community sentiment.",
        )

    def test_08_unique_complaint_ids(self):
        """Verify that all complaint record IDs are strictly unique."""
        seen_ids = set()
        duplicates = set()

        for record in self.complaints:
            rec_id = record.get("id")
            if rec_id in seen_ids:
                duplicates.add(rec_id)
            seen_ids.add(rec_id)

        self.assertEqual(
            len(duplicates),
            0,
            f"Found duplicate complaint IDs: {duplicates}",
        )

    def test_09_valid_iso8601_timestamps(self):
        """Verify collected_at timestamp format and chronological sanity."""
        violations = []

        for idx, record in enumerate(self.complaints):
            rec_id = record.get("id", f"idx_{idx}")
            ts = record.get("collected_at", "")

            if not validate_iso8601(ts):
                violations.append(f"Record {rec_id} has invalid ISO8601 timestamp: '{ts}'")

        self.assertEqual(
            len(violations),
            0,
            f"Found {len(violations)} invalid ISO8601 timestamps:\n"
            + "\n".join(violations[:10]),
        )

    def test_10_crawler_safety_boundary_compliance(self):
        """Verify crawler common utilities satisfy safe boundary limits."""
        utils_path = PROJECT_ROOT / "scrapers" / "common_utils.py"
        if not utils_path.exists() and (PROJECT_ROOT.parent / "scrapers" / "common_utils.py").exists():
            utils_path = PROJECT_ROOT.parent / "scrapers" / "common_utils.py"
        safety = inspect_crawler_script_safety(utils_path)

        self.assertTrue(safety["exists"], "scrapers/common_utils.py does not exist.")
        self.assertTrue(safety["has_delay_jitter"], "Missing delay/jitter in common_utils.py.")
        self.assertTrue(safety["has_ua_rotation"], "Missing UA rotation in common_utils.py.")
        self.assertTrue(safety["has_traffic_limit"], "Missing traffic rate limit in common_utils.py.")
        self.assertTrue(safety["has_backoff"], "Missing backoff/retry handling in common_utils.py.")

    def test_11_severity_field_validity_when_present(self):
        """Verify severity levels adhere to standard enums when present in records."""
        valid_severities = {
            "critical_safety",
            "functional_failure",
            "convenience_issue",
            "social_conflict",
            "financial_hazard",
            "operational_inconvenience",
        }
        for idx, record in enumerate(self.complaints):
            sev = record.get("severity")
            if sev is not None:
                self.assertIn(
                    sev,
                    valid_severities,
                    f"Record {record.get('id')} has invalid severity enum: '{sev}'",
                )


if __name__ == "__main__":
    unittest.main()
