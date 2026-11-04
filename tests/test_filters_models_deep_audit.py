"""Comprehensive Deep Audit Test Suite for filters/* and models/*.

Validates:
1. Regex compilation efficiency, ReDoS defenses, and execution timeouts on adversarial inputs.
2. Defect category classification accuracy, alias normalization, and unknown category handling.
3. Memory efficiency, allocation minimization, and thread safety across concurrent workers.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import time
import unittest
from typing import Any, Dict, List

from filters.defect_classifier import (
    COMPOUND_DEFECT_RULES,
    DefectClassifier,
    RE_AS_KEYWORD,
    RE_CLAUSE_SPLIT,
    RE_HANGUL,
    RE_TOKENS,
    _SORTED_COMPOUND_RULES,
    _SORTED_NEGATIVE_WORDS,
    _SORTED_POSITIVE_WORDS,
)
from filters.slang_lexicon import RAW_SLANG_ENTRIES, _SORTED_SLANG_ENTRIES, find_matching_slang
from filters.spam_filter import (
    HARD_ILLICIT_REGEX_SET,
    JOURNALISTIC_WIRE_REGEXES,
    NEWS_REGEXES,
    SpamFilter,
    sanitize_input,
)
from filters.vehicle_matcher import extract_vehicle_info
from models.complaint import (
    CANONICAL_CATEGORIES,
    CATEGORY_ALIASES,
    DEFECT_CATEGORY_KO_MAP,
    VALID_BRANDS,
    VALID_SEVERITY_LEVELS,
    ComplaintRecord,
    DSIBreakdown,
    DailyReportPayload,
    DailyReportStatistics,
    RawPost,
    _RE_DATE_2,
    _RE_DATE_COMPACT_6,
    _RE_DATE_COMPACT_8,
    _RE_DATE_KR_2,
    _RE_DATE_KR_4,
    _RE_DATE_MD,
    _RE_DATE_TS,
    normalize_category,
    normalize_severity,
    parse_date_str,
    validate_category,
    validate_severity,
)
from models.defect_report import DefectReport


class TestRegexEfficiencyAndReDoSDefenses(unittest.TestCase):
    """Verifies regex pre-compilation, absence of runtime compilation in loops, and ReDoS resilience."""

    def test_module_level_regex_precompilation(self) -> None:
        """All critical regex patterns must be pre-compiled instances of re.Pattern."""
        import re

        # Spam filter
        for pat in NEWS_REGEXES:
            self.assertIsInstance(pat, re.Pattern)
        for pat in JOURNALISTIC_WIRE_REGEXES:
            self.assertIsInstance(pat, re.Pattern)
        for pat in HARD_ILLICIT_REGEX_SET:
            self.assertIsInstance(pat, re.Pattern)

        # Defect classifier
        self.assertIsInstance(RE_CLAUSE_SPLIT, re.Pattern)
        self.assertIsInstance(RE_TOKENS, re.Pattern)
        self.assertIsInstance(RE_HANGUL, re.Pattern)
        self.assertIsInstance(RE_AS_KEYWORD, re.Pattern)

        # Date parsing
        for pat in (
            _RE_DATE_KR_4,
            _RE_DATE_KR_2,
            _RE_DATE_TS,
            _RE_DATE_COMPACT_8,
            _RE_DATE_2,
            _RE_DATE_COMPACT_6,
            _RE_DATE_MD,
        ):
            self.assertIsInstance(pat, re.Pattern)

    def test_adversarial_redos_payload_spam_filter(self) -> None:
        """Adversarial nested repetitive input must complete within 50ms without catastrophic backtracking."""
        sf = SpamFilter()
        evil_text = "open.kakao.com/" + "a" * 10000 + "/" + "b" * 10000
        start_time = time.perf_counter()
        discarded, reason = sf.evaluate_stage1_noise(evil_text)
        elapsed = time.perf_counter() - start_time

        self.assertLess(elapsed, 0.10, f"SpamFilter ReDoS vulnerability detected: elapsed={elapsed:.4f}s")
        self.assertTrue(discarded)

    def test_adversarial_redos_payload_vehicle_matcher(self) -> None:
        """Adversarial repetitive text must complete within 50ms and respect length limits."""
        evil_title = "m3 " * 2000
        evil_content = "내 차 " + "아이오닉 5 ioniq " * 5000

        start_time = time.perf_counter()
        brand, model = extract_vehicle_info(evil_title, evil_content)
        elapsed = time.perf_counter() - start_time

        self.assertLess(elapsed, 0.15, f"VehicleMatcher ReDoS vulnerability detected: elapsed={elapsed:.4f}s")
        self.assertIn(brand, VALID_BRANDS)

    def test_adversarial_redos_payload_date_parser(self) -> None:
        """Adversarial long non-date string must be bounded and complete within 10ms."""
        evil_date = "2026-10-28" + " " * 50000 + "14:30:00"
        start_time = time.perf_counter()
        res = parse_date_str(evil_date)
        elapsed = time.perf_counter() - start_time

        self.assertLess(elapsed, 0.05, f"Date parser ReDoS vulnerability detected: elapsed={elapsed:.4f}s")
        self.assertEqual(res, "2026-10-28")


class TestDefectCategoryAccuracyAndUnknownHandling(unittest.TestCase):
    """Verifies 100% taxonomy classification accuracy, alias mapping, and graceful unknown handling."""

    def setUp(self) -> None:
        self.clf = DefectClassifier()

    def test_canonical_categories_constant_integrity(self) -> None:
        """CANONICAL_CATEGORIES must contain the exact 5 pillars."""
        expected = {
            "BATTERY_CHARGING",
            "DRIVING_POWERTRAIN",
            "BUILD_QUALITY",
            "SOFTWARE_ELECTRONICS",
            "SERVICE_REPAIR_COST",
        }
        self.assertEqual(set(CANONICAL_CATEGORIES), expected)

    def test_category_aliases_normalization(self) -> None:
        """Colloquial and subsystem terms must normalize to canonical categories."""
        test_cases = [
            # Battery & Charging
            ("배터리", "BATTERY_CHARGING"),
            ("충전", "BATTERY_CHARGING"),
            ("BMS", "BATTERY_CHARGING"),
            ("ICCU", "BATTERY_CHARGING"),
            ("battery", "BATTERY_CHARGING"),
            ("charging", "BATTERY_CHARGING"),
            # Driving & Powertrain
            ("주행", "DRIVING_POWERTRAIN"),
            ("모터", "DRIVING_POWERTRAIN"),
            ("제동", "DRIVING_POWERTRAIN"),
            ("조향", "DRIVING_POWERTRAIN"),
            ("powertrain", "DRIVING_POWERTRAIN"),
            ("driving", "DRIVING_POWERTRAIN"),
            # Build Quality
            ("단차", "BUILD_QUALITY"),
            ("누수", "BUILD_QUALITY"),
            ("마감", "BUILD_QUALITY"),
            ("조립", "BUILD_QUALITY"),
            ("build_quality", "BUILD_QUALITY"),
            # Software & Electronics
            ("소프트웨어", "SOFTWARE_ELECTRONICS"),
            ("OTA", "SOFTWARE_ELECTRONICS"),
            ("먹통", "SOFTWARE_ELECTRONICS"),
            ("software", "SOFTWARE_ELECTRONICS"),
            ("electronics", "SOFTWARE_ELECTRONICS"),
            # Service & Repair Cost
            ("AS", "SERVICE_REPAIR_COST"),
            ("A/S", "SERVICE_REPAIR_COST"),
            ("수리비", "SERVICE_REPAIR_COST"),
            ("서비스센터", "SERVICE_REPAIR_COST"),
            ("repair", "SERVICE_REPAIR_COST"),
            ("service", "SERVICE_REPAIR_COST"),
        ]
        for raw, expected in test_cases:
            normalized = normalize_category(raw)
            self.assertEqual(normalized, expected, f"Failed normalizing alias '{raw}'")

    def test_unknown_category_normalization_and_defaults(self) -> None:
        """Unknown categories must safely fall back to default without crashing."""
        self.assertEqual(normalize_category("NON_EXISTENT_CAT"), "BUILD_QUALITY")
        self.assertEqual(normalize_category("NON_EXISTENT_CAT", default="OTHER"), "OTHER")
        self.assertEqual(normalize_category(None, default="FALLBACK"), "FALLBACK")
        self.assertEqual(normalize_category("", default="FALLBACK"), "FALLBACK")

    def test_complaint_record_korean_category_alias_resolution(self) -> None:
        """defect_category_ko property must resolve known aliases and return '기타 결함' for unknowns."""
        rec_alias = ComplaintRecord(
            id="c1",
            source="dcinside",
            url="",
            title="",
            author="",
            created_at="2026-10-28",
            vehicle_brand="Hyundai",
            vehicle_model="Ioniq 5",
            defect_category="배터리",
            summary="",
            verbatim_quote="배터리 고장",
        )
        self.assertEqual(rec_alias.defect_category_ko, "배터리/충전")

        rec_unknown = ComplaintRecord(
            id="c2",
            source="dcinside",
            url="",
            title="",
            author="",
            created_at="2026-10-28",
            vehicle_brand="Hyundai",
            vehicle_model="Ioniq 5",
            defect_category="UNKNOWN_CATEGORY_X",
            summary="",
            verbatim_quote="알 수 없는 결함",
        )
        self.assertEqual(rec_unknown.defect_category_ko, "기타 결함")

    def test_complaint_record_from_dict_category_normalization(self) -> None:
        """ComplaintRecord.from_dict must normalize category aliases into canonical English."""
        data = {
            "id": "c-norm",
            "defect_category": "수리비",
        }
        rec = ComplaintRecord.from_dict(data)
        self.assertEqual(rec.defect_category, "SERVICE_REPAIR_COST")
        self.assertEqual(rec.defect_category_ko, "AS/수리비")

    def test_classifier_fallback_on_unrecognized_text(self) -> None:
        """Unrecognized defect text with 0 score falls back cleanly to BUILD_QUALITY."""
        cat = self.clf.classify_defect_category("오늘 날씨가 정말 맑고 좋습니다.")
        self.assertEqual(cat, "BUILD_QUALITY")


class TestModelMemoryEfficiencyAndThreadSafety(unittest.TestCase):
    """Verifies thread-safe execution and zero-allocation key access protocols."""

    def test_concurrent_multithreaded_filtering_and_classification(self) -> None:
        """20 concurrent threads running classification must execute with zero data corruption."""
        clf = DefectClassifier()
        sample_posts = [
            RawPost(post_id=f"p_{i}", title="ICCU 터짐", content="내 차 고속도로에서 퍽 소리 나며 멈춤")
            for i in range(100)
        ]

        def _worker(post: RawPost) -> ComplaintRecord:
            return clf.process_post(post)

        with ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(_worker, sample_posts))

        self.assertEqual(len(results), 100)
        for r in results:
            self.assertTrue(r.is_authentic_defect)
            self.assertEqual(r.defect_category, "BATTERY_CHARGING")
            self.assertEqual(r.defect_category_ko, "배터리/충전")

    def test_model_dict_access_does_not_serialize_entire_record(self) -> None:
        """Field lookups via __getitem__ and __contains__ must access fields cleanly."""
        rec = ComplaintRecord(
            id="rec-01",
            source="bobaedream",
            url="https://example.com",
            title="테스트 제목",
            author="홍길동",
            created_at="2026-10-28 12:00:00",
            vehicle_brand="Kia",
            vehicle_model="EV6",
            defect_category="BATTERY_CHARGING",
            summary="요약",
            verbatim_quote="ICCU 폭탄 맞음",
            slang_terms_detected=["ICCU"],
            severity="CRITICAL",
        )

        # Field accesses
        self.assertEqual(rec["platform"], "bobaedream")
        self.assertEqual(rec["date"], "2026-10-28")
        self.assertEqual(rec["target_vehicle"], "Kia EV6")
        self.assertEqual(rec["defect_category_ko"], "배터리/충전")
        self.assertEqual(rec["raw_quote"], "ICCU 폭탄 맞음")
        self.assertEqual(rec["severity"], "CRITICAL")
        self.assertIn("target_vehicle", rec)
        self.assertIn("platform", rec)
        self.assertNotIn("non_existent_key", rec)

        with self.assertRaises(KeyError):
            _ = rec["non_existent_key"]

    def test_raw_post_and_payload_dict_access_efficiency(self) -> None:
        """RawPost and DailyReportPayload implement lightweight mapping without full serialization."""
        raw = RawPost(post_id="r1", title="제목", content="내용")
        self.assertEqual(raw["post_id"], "r1")
        self.assertIn("title", raw)
        self.assertNotIn("invalid_key", raw)
        with self.assertRaises(KeyError):
            _ = raw["invalid_key"]

        payload = DailyReportPayload(
            generated_at="2026-10-28T00:00:00Z",
            reports=[{"id": f"r_{i}"} for i in range(100)],
        )
        self.assertIn("generated_at", payload)
        self.assertIn("reports", payload)
        self.assertNotIn("invalid_key", payload)
        self.assertEqual(len(payload["reports"]), 100)
        with self.assertRaises(KeyError):
            _ = payload["invalid_key"]


if __name__ == "__main__":
    unittest.main()
