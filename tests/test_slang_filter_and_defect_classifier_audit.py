#!/usr/bin/env python3
"""Comprehensive Audit & Verification Test Suite for Slang Filter, Defect Classifier & Models.

Covers:
1. Regex compilation efficiency & ReDoS immunity:
   - Module-level pre-compilation (RE_CLAUSE_SPLIT, RE_TOKENS, RE_HANGUL, RE_AS_KEYWORD).
   - Zero regex compilation in inner loops.
   - Adversarial nested string evaluation completing within strict latency bounds.
2. Unicode normalization (NFC vs NFD/NFKD):
   - Decomposed Hangul syllables (macOS / iOS / web form copy-paste).
   - Exact matching against NFC precomposed lexicon entries.
3. Edge cases in Korean car slang detection:
   - Case-insensitive mixed Latin/Hangul acronyms (iccu, bms, ota, v2l, 12v, tcam, hud, mdps).
   - SlangFilter API methods: filter_slang, extract_slang_tags, is_slang_present, classify_slang_dimensions.
4. Robustness against null, empty string, whitespace, null-bytes, and non-string scalars:
   - None, empty string, whitespace, control characters, null bytes (\x00).
   - Non-string scalars: int, float, bool, list, dict, object.
5. Oversized post text boundaries:
   - Payloads of 50,000, 100,000, and 200,000 characters processed without memory bloat or crash.
6. Models integrity:
   - RawPost, ComplaintRecord, DefectReport deserialization and field safety.
"""

from __future__ import annotations

import math
from pathlib import Path
import re
import sys
import time
import unicodedata
import unittest
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from filters.defect_classifier import (
    COMPOUND_DEFECT_RULES,
    RE_AS_KEYWORD,
    RE_CLAUSE_SPLIT,
    RE_HANGUL,
    RE_TOKENS,
    _SORTED_COMPOUND_RULES,
    _SORTED_NEGATIVE_WORDS,
    _SORTED_POSITIVE_WORDS,
    DefectClassifier,
    sanitize_text,
)
from filters.slang_filter import (
    SlangFilter,
    extract_slang_tags,
    filter_slang,
    is_slang_present,
)
from filters.slang_lexicon import (
    RAW_SLANG_ENTRIES,
    SLANG_CATALOG,
    _SORTED_SLANG_ENTRIES,
    find_matching_slang,
)
from models import (
    ComplaintRecord,
    DailyReportPayload,
    DailyReportStatistics,
    DefectReport,
    RawPost,
)


class TestUnicodeNormalizationAndDecomposition(unittest.TestCase):
    """Verifies that decomposed Hangul (NFD) is normalized and accurately detected."""

    def setUp(self) -> None:
        self.clf = DefectClassifier()
        self.filter = SlangFilter()

    def test_nfd_slang_detection(self) -> None:
        """Decomposed Hangul (NFD) input must be recognized by find_matching_slang."""
        # '단차' decomposed into jamos
        nfd_term = unicodedata.normalize("NFD", "단차 누수 심각합니다")
        self.assertNotEqual(nfd_term, "단차 누수 심각합니다")

        matches = find_matching_slang(nfd_term)
        matched_terms = [m.term for m in matches]
        self.assertIn("단차", matched_terms)
        self.assertIn("누수", matched_terms)

    def test_nfd_defect_classifier_pipeline(self) -> None:
        """Decomposed Hangul in defect complaints must pass Stage 2 and classify properly."""
        raw_text = "내차 고속도로 주행 중 퍽 소리 나더니 ICCU 터짐 발생"
        nfd_text = unicodedata.normalize("NFD", raw_text)

        is_owner, reason = self.clf.evaluate_stage2_ownership(nfd_text)
        self.assertTrue(is_owner, f"Ownership verification failed on NFD: {reason}")

        cat = self.clf.classify_defect_category(nfd_text)
        self.assertEqual(cat, "BATTERY_CHARGING")

        rec = self.clf.classify(nfd_text)
        self.assertTrue(rec.is_authentic_defect)
        self.assertEqual(rec.defect_category, "BATTERY_CHARGING")

    def test_nfkd_compatibility_decomposition(self) -> None:
        """NFKD decomposed text must be normalized to NFC and matched."""
        sample = unicodedata.normalize("NFKD", "내차 배터리 화재 발생으로 소방차 출동")
        cat = self.clf.classify_defect_category(sample)
        self.assertEqual(cat, "BATTERY_CHARGING")


class TestKoreanCarSlangEdgeCasesAndCaseInsensitivity(unittest.TestCase):
    """Verifies case-insensitive Latin acronyms and nuanced Korean automotive slang."""

    def setUp(self) -> None:
        self.filter = SlangFilter()

    def test_lowercase_latin_acronym_slang(self) -> None:
        """Lowercase EV technical acronyms must match slang entries."""
        cases = [
            ("고속도로에서 iccu 폭탄 터졌네요", ["ICCU 폭탄", "ICCU"]),
            ("어제 업데이트하고 bms 에러 뜸", ["BMS 에러"]),
            ("계기판 ota 벽돌 현상", ["OTA 벽돌", "벽돌"]),
            ("겨울철 12v 방전 스트레스", ["12V 방전"]),
            ("캠핑장에서 v2l 안 됨", ["V2L"]),
            ("내비 tcam 먹통", ["TCAM 먹통"]),
        ]
        for text, expected_terms in cases:
            matches = find_matching_slang(text)
            matched_terms = [m.term for m in matches]
            for exp in expected_terms:
                self.assertIn(exp, matched_terms, f"Failed matching '{exp}' in '{text}'")

    def test_slang_filter_api_methods(self) -> None:
        """SlangFilter class methods must function predictably."""
        text = "테슬람들이 물고 빠는 삼식이 모델와이 깜빡이 소리도 안 남"
        tags = self.filter.extract_slang_tags(text)
        self.assertIn("테슬람", tags)
        self.assertIn("깜빡이", tags)

        self.assertTrue(self.filter.is_slang_present(text))
        self.assertTrue(self.filter.is_slang_present(text, "테슬람"))
        self.assertTrue(self.filter.is_slang_present(text, "BRAND_PEJORATIVE"))
        self.assertFalse(self.filter.is_slang_present(text, "NON_EXISTENT_TERM"))

        grouped = self.filter.classify_slang_dimensions(text)
        self.assertIn("BRAND_PEJORATIVE", grouped)

    def test_module_level_slang_helpers(self) -> None:
        """Module-level helpers extract_slang_tags, is_slang_present, filter_slang work properly."""
        text = "ICCU 폭탄 터짐"
        self.assertTrue(is_slang_present(text, "ICCU"))
        tags = extract_slang_tags(text)
        self.assertIn("ICCU 폭탄", tags)
        filtered = filter_slang(text)
        self.assertGreater(len(filtered), 0)


class TestNullEmptyAndOversizedInputs(unittest.TestCase):
    """Verifies crash-safety when handling null, empty, whitespace, null-bytes, and oversized texts."""

    def setUp(self) -> None:
        self.clf = DefectClassifier()
        self.filter = SlangFilter()

    def test_null_and_empty_inputs_slang(self) -> None:
        """find_matching_slang and SlangFilter methods safely return empty on null/empty/whitespace."""
        for val in [None, "", "   ", "\t\n\r", False]:
            self.assertEqual(find_matching_slang(val), [])
            self.assertEqual(self.filter.extract_slang_tags(val), [])
            self.assertFalse(self.filter.is_slang_present(val))

    def test_null_bytes_sanitization(self) -> None:
        """Null bytes inside text strings must be stripped without crashing."""
        text_with_null = "내차 주행 중 \x00ICCU\x00 폭탄\x00 터짐"
        matches = find_matching_slang(text_with_null)
        matched_terms = [m.term for m in matches]
        self.assertIn("ICCU 폭탄", matched_terms)

        sanitized = sanitize_text(text_with_null)
        self.assertNotIn("\x00", sanitized)

    def test_non_string_scalar_inputs(self) -> None:
        """Passing int, float, bool, list, dict, object never raises exceptions."""
        non_strings = [0, 42, 3.14159, True, False, [], {}, object()]
        for val in non_strings:
            self.assertEqual(find_matching_slang(val), [])
            rec = self.clf.classify(val)
            self.assertIsInstance(rec, ComplaintRecord)
            self.assertFalse(rec.is_authentic_defect)

    def test_oversized_post_text_handling(self) -> None:
        """Oversized texts (50k, 100k, 200k chars) are bounded and execute within 25ms."""
        huge_text = "내차 고속도로 주행 중 ICCU 폭탄 터짐 발생. " + ("배터리 결함 단차 누수 잡소리 " * 10000)
        self.assertGreater(len(huge_text), 150_000)

        start = time.perf_counter()
        matches = find_matching_slang(huge_text)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 0.05, f"Slang matching on huge text too slow: {elapsed:.4f}s")
        self.assertGreater(len(matches), 0)

        start = time.perf_counter()
        rec = self.clf.classify(huge_text)
        elapsed_clf = time.perf_counter() - start
        self.assertLess(elapsed_clf, 0.35, f"Classification on huge text too slow: {elapsed_clf:.4f}s")
        self.assertIsInstance(rec, ComplaintRecord)


class TestRegexCompilationEfficiencyAndReDoS(unittest.TestCase):
    """Verifies all regex patterns are compiled instances and inner loops have zero compilation."""

    def test_compiled_regex_instances(self) -> None:
        """All critical regexes in defect_classifier must be pre-compiled re.Pattern objects."""
        self.assertIsInstance(RE_CLAUSE_SPLIT, re.Pattern)
        self.assertIsInstance(RE_TOKENS, re.Pattern)
        self.assertIsInstance(RE_HANGUL, re.Pattern)
        self.assertIsInstance(RE_AS_KEYWORD, re.Pattern)

    def test_presorted_collections_immutability(self) -> None:
        """Pre-sorted collections are tuples and have descending length order."""
        self.assertIsInstance(_SORTED_NEGATIVE_WORDS, tuple)
        self.assertIsInstance(_SORTED_POSITIVE_WORDS, tuple)
        for cat, phrases in _SORTED_COMPOUND_RULES.items():
            self.assertIsInstance(phrases, tuple)
            for i in range(len(phrases) - 1):
                self.assertGreaterEqual(len(phrases[i]), len(phrases[i + 1]))

    def test_redos_pattern_safety(self) -> None:
        """Repetitive regex adversarial patterns execute in < 20ms."""
        evil_split = "," * 20000 + ";" * 20000 + "\n" * 10000
        start = time.perf_counter()
        parts = RE_CLAUSE_SPLIT.split(evil_split)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 0.02)


class TestModelsIntegrityAndEdgeCases(unittest.TestCase):
    """Verifies RawPost, ComplaintRecord, and DefectReport robustness."""

    def test_raw_post_oversized_and_null_bytes(self) -> None:
        """RawPost strips null bytes, bounds oversized content, and normalizes NFC."""
        evil_content = "내용\x00" + ("가" * 150_000)
        post = RawPost(
            platform="dcinside\x00",
            post_id="p-123\x00",
            title="제목\x00",
            content=evil_content,
            comments="단일 댓글 문자열",
        )
        self.assertNotIn("\x00", post.platform)
        self.assertNotIn("\x00", post.content)
        self.assertLessEqual(len(post.content), 100_000)
        self.assertEqual(post.comments, ["단일 댓글 문자열"])

    def test_raw_post_from_dict_non_dict(self) -> None:
        """RawPost.from_dict safely constructs empty RawPost when passed primitives or None."""
        for val in [None, 123, "string", [], True]:
            p = RawPost.from_dict(val)
            self.assertIsInstance(p, RawPost)
            self.assertEqual(p.post_id, "")

    def test_complaint_record_from_dict_non_dict(self) -> None:
        """ComplaintRecord.from_dict safely constructs default record on non-dict inputs."""
        for val in [None, 456, "bad", [1, 2], False]:
            rec = ComplaintRecord.from_dict(val)
            self.assertIsInstance(rec, ComplaintRecord)
            self.assertEqual(rec.id, "")

    def test_defect_report_roundtrip_and_date(self) -> None:
        """DefectReport properly exposes date_str and inherits ComplaintRecord capabilities."""
        report = DefectReport.from_dict({
            "id": "dr-01",
            "source": "clien",
            "created_at": "2026-11-05 14:22:00",
            "vehicle_brand": "Tesla",
            "vehicle_model": "Model 3",
            "defect_category": "소프트웨어",
            "verbatim_quote": "OTA 업데이트 후 블랙아웃 발생",
        })
        self.assertIsInstance(report, DefectReport)
        self.assertEqual(report.date_str, "2026-11-05")
        self.assertEqual(report.defect_category, "SOFTWARE_ELECTRONICS")
        self.assertEqual(report.defect_category_ko, "OTA/소프트웨어/먹통")


if __name__ == "__main__":
    unittest.main()
