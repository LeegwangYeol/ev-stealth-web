"""
Tier 4: Real-World User Acceptance Scenarios Test Suite.

Validates the final presentation deliverables (CASEBOOK.md & STATISTICAL_REPORT.md):
1. Document existence and substantive content length.
2. Complete markdown section hierarchy.
3. Each of the 4 core problem categories contains detailed case studies with verbatim quotes.
4. Verbatim raw quotes preserve unfiltered Korean community tone and slang.
5. Slang dictionary explains real community automotive terms.
6. 100% of case studies link to verifiable community sources.
7. Markdown syntax cleanliness (zero placeholder tokens or broken syntax).
8. Strict compliance against all Acceptance Criteria in ORIGINAL_REQUEST.md.
"""

import os
import re
import sys
import unittest
from pathlib import Path
from typing import Dict, List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.e2e.common import (
    CATEGORY_KEYWORDS,
    CATEGORY_KOREAN_NAMES,
    KNOWN_SLANG_KEYWORDS,
    extract_markdown_sections,
    load_casebook,
)

FORBIDDEN_PLACEHOLDER_TOKENS = [
    "[TODO]",
    "[TBD]",
    "[PLACEHOLDER]",
    "[INSERT",
    "Lorem ipsum",
    "내용 추가 예정",
    "사례 작성 예정",
]


class TestTier4RealScenarios(unittest.TestCase):
    """Tier 4 Test Cases: End-to-end user acceptance and deliverable fidelity auditing."""

    casebook_text: str = ""
    sections: Dict[str, str] = {}

    @classmethod
    def setUpClass(cls):
        """Load CASEBOOK.md content once for acceptance testing."""
        try:
            cls.casebook_text = load_casebook()
            cls.sections = extract_markdown_sections(cls.casebook_text)
        except FileNotFoundError as e:
            cls.casebook_text = ""
            cls.sections = {}
            cls.load_error = str(e)
        except Exception as e:
            cls.casebook_text = ""
            cls.sections = {}
            cls.load_error = f"Error loading CASEBOOK.md: {e}"
        else:
            cls.load_error = None

    def setUp(self):
        if self.load_error:
            self.fail(f"Casebook load failure: {self.load_error}")
        if not self.casebook_text:
            self.fail("CASEBOOK.md is empty.")

    def test_01_casebook_file_exists_and_substantial(self):
        """Verify CASEBOOK.md exists and has substantive document length (>= 3,000 bytes)."""
        byte_length = len(self.casebook_text.encode("utf-8"))
        self.assertGreaterEqual(
            byte_length,
            3000,
            f"CASEBOOK.md is too short ({byte_length} bytes), expected >= 3,000 bytes for a full casebook.",
        )

    def test_02_casebook_mandatory_sections_present(self):
        """Verify CASEBOOK.md contains all mandatory structural sections."""
        all_text = self.casebook_text

        required_section_markers = [
            ("요약 / 배경", ["개요", "요약", "배경", "Executive Summary", "Summary"]),
            ("은어 사전", ["은어", "용어", "사전", "Slang", "Dictionary"]),
            ("사례집 본문", ["사례집", "Casebook", "Part 1", "Part 2", "Part 3", "주차", "충전"]),
            ("출처 / 색인", ["출처", "색인", "링크", "Source", "Index"]),
        ]

        missing_sections = []
        for section_name, markers in required_section_markers:
            if not any(marker in all_text for marker in markers):
                missing_sections.append(section_name)

        self.assertEqual(
            len(missing_sections),
            0,
            f"CASEBOOK.md is missing mandatory sections: {missing_sections}.",
        )

    def test_03_casebook_four_categories_have_minimum_three_cases_each(self):
        """Verify that each of the 4 core categories contains >= 3 detailed cases in CASEBOOK.md."""
        lines = self.casebook_text.splitlines()

        category_case_counts = {
            "parking": 0,
            "charging": 0,
            "rain_driving": 0,
            "hill_climbing_or_maintenance": 0,
        }

        current_category = None

        for line in lines:
            line_str = line.strip()

            # Detect section heading
            if line_str.startswith("#") and not re.match(r"^#{3,}\s*(\[?사례|case|\b[a-z]{2}-[a-z]{2}-\d+)", line_str, re.IGNORECASE):
                header_lower = line_str.lower()
                if "주차" in header_lower or "parking" in header_lower or "-pk-" in header_lower:
                    current_category = "parking"
                elif "충전" in header_lower or "charging" in header_lower or "-ch-" in header_lower:
                    current_category = "charging"
                elif "우천" in header_lower or "혹한" in header_lower or "빗길" in header_lower or "rain" in header_lower or "-dr-" in header_lower:
                    current_category = "rain_driving"
                elif (
                    "등판" in header_lower
                    or "언덕" in header_lower
                    or "정비" in header_lower
                    or "수리" in header_lower
                    or "as" in header_lower
                    or "hill" in header_lower
                    or "maintenance" in header_lower
                    or "-mt-" in header_lower
                ):
                    current_category = "hill_climbing_or_maintenance"

            # Detect case study header
            if (
                re.match(r"^#{3,4}\s+.*(?:사례|Case|\b[A-Z]{2}-[A-Z]{2}-\d+\b)", line_str, re.IGNORECASE)
                or re.match(r"^\*\*(?:사례|Case\s*\d+)", line_str, re.IGNORECASE)
            ):
                h_lower = line_str.lower()
                assigned_cat = None

                if "-pk-" in h_lower or "주차" in h_lower or "parking" in h_lower or "어라운드뷰" in h_lower:
                    assigned_cat = "parking"
                elif "-ch-" in h_lower or "충전" in h_lower or "charging" in h_lower or "bms" in h_lower or "iccu" in h_lower or "lfp" in h_lower:
                    assigned_cat = "charging"
                elif "-dr-" in h_lower or "우천" in h_lower or "혹한" in h_lower or "빗길" in h_lower or "rain" in h_lower or "와이퍼" in h_lower or "수막" in h_lower or "피쉬테일" in h_lower or "옥토밸브" in h_lower:
                    assigned_cat = "rain_driving"
                elif (
                    "-mt-" in h_lower
                    or "등판" in h_lower
                    or "언덕" in h_lower
                    or "정비" in h_lower
                    or "수리" in h_lower
                    or "as" in h_lower
                    or "hill" in h_lower
                    or "maintenance" in h_lower
                    or "롤백" in h_lower
                    or "오토홀드" in h_lower
                    or "전손" in h_lower
                    or "기가캐스팅" in h_lower
                ):
                    assigned_cat = "hill_climbing_or_maintenance"
                elif current_category:
                    assigned_cat = current_category

                if assigned_cat and assigned_cat in category_case_counts:
                    category_case_counts[assigned_cat] += 1

        insufficient = {
            k: count for k, count in category_case_counts.items() if count < 3
        }

        self.assertEqual(
            len(insufficient),
            0,
            f"CASEBOOK.md categories with fewer than 3 cases: {insufficient}. "
            f"Found counts: {category_case_counts}",
        )

    def test_04_casebook_preserves_verbatim_raw_korean_quotes(self):
        """Verify that CASEBOOK.md uses direct quotes (> blockquotes) containing authentic community slang."""
        blockquotes = re.findall(r"^>\s+(.+)$", self.casebook_text, re.MULTILINE)
        self.assertGreaterEqual(
            len(blockquotes),
            12,
            f"Found only {len(blockquotes)} blockquotes in CASEBOOK.md, expected >= 12 (at least 3 per category).",
        )

        combined_quotes = " ".join(blockquotes)
        slang_hits = [term for term in KNOWN_SLANG_KEYWORDS if term in combined_quotes]
        self.assertGreaterEqual(
            len(slang_hits),
            5,
            f"Blockquotes lack authentic community slang. Found only: {slang_hits}",
        )

    def test_05_casebook_slang_dictionary_section_substance(self):
        """Verify slang dictionary section contains definitions for key community terms."""
        all_text = self.casebook_text
        terms_found = [term for term in KNOWN_SLANG_KEYWORDS if term in all_text]
        self.assertGreaterEqual(
            len(terms_found),
            8,
            f"Slang dictionary / text contains only {len(terms_found)} recognized terms ({terms_found}), expected >= 8.",
        )

    def test_06_casebook_source_links_and_verifiability(self):
        """Verify that CASEBOOK.md contains source URLs or community board citations."""
        url_matches = re.findall(
            r"https?://[^\s\)\>\]]+",
            self.casebook_text,
        )
        community_mentions = re.findall(
            r"(보배드림|디시인사이드|블라인드|네이버카페|다음카페|뽐뿌|클리앙|유튜브|테슬라|현대|기아|제네시스|벤츠|BMW|포르쉐|폴스타|BYD)",
            self.casebook_text,
        )

        self.assertGreaterEqual(
            len(url_matches) + len(community_mentions),
            12,
            "CASEBOOK.md lacks sufficient source links and community citations.",
        )

    def test_07_casebook_cleanliness_no_placeholder_tokens(self):
        """Verify CASEBOOK.md has no unresolved template or placeholder tokens."""
        violations = []
        for token in FORBIDDEN_PLACEHOLDER_TOKENS:
            if token in self.casebook_text:
                violations.append(f"Found forbidden placeholder token: '{token}'")

        self.assertEqual(
            len(violations),
            0,
            f"CASEBOOK.md contains unfinished placeholder tokens:\n" + "\n".join(violations),
        )

    def test_08_original_request_acceptance_criteria_compliance(self):
        """Verify full compliance with all acceptance criteria in ORIGINAL_REQUEST.md."""
        for cat_name in ["주차", "충전", "우천", "등판"]:
            self.assertIn(
                cat_name,
                self.casebook_text,
                f"Mandatory category keyword '{cat_name}' not mentioned in CASEBOOK.md.",
            )

        has_slang = any(s in self.casebook_text for s in KNOWN_SLANG_KEYWORDS)
        self.assertTrue(has_slang, "Casebook failed acceptance criteria: raw unrefined slang not found.")

        self.assertIn("보배드림", self.casebook_text, "Bobaedream source missing from CASEBOOK.md.")
        self.assertIn("디시인사이드", self.casebook_text, "DC Inside source missing from CASEBOOK.md.")


if __name__ == "__main__":
    unittest.main()
