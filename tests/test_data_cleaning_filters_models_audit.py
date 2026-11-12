# -*- coding: utf-8 -*-
"""
Auditing tests for data cleaning, filters, and schema models in:
- ev-stealth-web/filters/
- ev-stealth-web/models/

Verifies:
1. Data filters sanitize corrupted strings (null bytes, control chars, BiDi overrides, surrogates, BOM).
2. Date normalization handles diverse date formats, Korean relative expressions, and malformed inputs.
3. Schema models strictly validate incoming JSON payloads and gracefully quarantine invalid entries without crashing.
"""

import json
from datetime import datetime, timezone
import pytest

from models.complaint import (
    ComplaintRecord,
    DailyReportPayload,
    RawPost,
    parse_date_str,
    quarantine_entry,
    sanitize_string,
    validate_report_entry,
)
from models.defect_report import DefectReport
from filters.defect_classifier import DefectClassifier, normalize_date, sanitize_text
from filters.defect_filter import ContextualDefectFilter, DefectFilter
from filters.slang_filter import SlangFilter, normalize_text
from filters.spam_filter import SpamFilter, sanitize_input
from filters.vehicle_matcher import BRAND_HYUNDAI, VehicleMatcher, extract_vehicle_info


class TestDataSanitizationAndFilters:
    """Test data filter cleaning of corrupted strings and invalid characters."""

    CORRUPTED_STRINGS = [
        "아이오닉5\x00 배터리\x08 문제\x1f 발생\x7f",
        "EV6\ufeff 충전\ufffe불량\uffff",
        "테슬라 \u202e오토파일럿\u202c 결함",  # BiDi Trojan Source overrides
        "코나 EV\ud800\udfff 주행거리 이상",  # Lone surrogates
        "포터 EV\r\n\t정상 텍스트",  # Preserves \r, \n, \t
    ]

    def test_sanitize_string_models(self):
        """Verify models.complaint.sanitize_string removes all harmful control chars and surrogates."""
        cleaned_0 = sanitize_string(self.CORRUPTED_STRINGS[0])
        assert "\x00" not in cleaned_0
        assert "\x08" not in cleaned_0
        assert "\x1f" not in cleaned_0
        assert "\x7f" not in cleaned_0
        assert "아이오닉5 배터리 문제 발생" in cleaned_0

        cleaned_1 = sanitize_string(self.CORRUPTED_STRINGS[1])
        assert "\ufeff" not in cleaned_1
        assert "\ufffe" not in cleaned_1
        assert "\uffff" not in cleaned_1
        assert "EV6 충전불량" in cleaned_1

        cleaned_2 = sanitize_string(self.CORRUPTED_STRINGS[2])
        assert "\u202e" not in cleaned_2
        assert "\u202c" not in cleaned_2
        assert "테슬라 오토파일럿 결함" in cleaned_2

        cleaned_3 = sanitize_string(self.CORRUPTED_STRINGS[3])
        # Surrogates must be removed cleanly without UnicodeEncodeError
        assert "\ud800" not in cleaned_3
        assert "\udfff" not in cleaned_3
        assert "코나 EV 주행거리 이상" in cleaned_3

        cleaned_4 = sanitize_string(self.CORRUPTED_STRINGS[4])
        assert "\r\n\t" in cleaned_4
        assert "포터 EV" in cleaned_4

    def test_sanitize_text_filters(self):
        """Verify filters.defect_classifier.sanitize_text strips harmful control characters."""
        text = "테슬라\x00 모델Y\x1b ICCU\ufeff 화재 위험\u202a조심\u202c"
        cleaned = sanitize_text(text)
        assert "\x00" not in cleaned
        assert "\x1b" not in cleaned
        assert "\ufeff" not in cleaned
        assert "\u202a" not in cleaned
        assert "테슬라 모델Y ICCU 화재 위험조심" in cleaned

    def test_sanitize_input_spam_filter(self):
        """Verify filters.spam_filter.sanitize_input sanitizes inputs before spam evaluation."""
        text = "카톡 상담\x00 당일 대출\x07 문자\ufffe 상담문의"
        cleaned = sanitize_input(text)
        assert "\x00" not in cleaned
        assert "\x07" not in cleaned
        assert "\ufffe" not in cleaned
        assert "카톡 상담 당일 대출 문자 상담문의" in cleaned

        sf = SpamFilter()
        assert sf.is_spam(text) is True

    def test_normalize_text_slang_filter(self):
        """Verify filters.slang_filter.normalize_text sanitizes and normalizes slang."""
        text = "현기차\x00 흉기차\x1f 개우디"
        normalized = normalize_text(text)
        assert "\x00" not in normalized
        assert "\x1f" not in normalized
        assert "현기차 흉기차 개우디" in normalized

        sf = SlangFilter()
        matches = sf.find_matching_slang(text)
        assert len(matches) >= 2
        terms = [m.term for m in matches]
        assert "현기차" in terms or "흉기차" in terms or "개우디" in terms

    def test_extract_vehicle_info_with_corrupted_text(self):
        """Verify filters.vehicle_matcher.extract_vehicle_info handles corrupted strings safely."""
        corrupted_title = "아이오닉\x005\ufeff 롱레인지 2024년형\u202e 결함"
        corrupted_content = "배터리\x07 방전 문제\ud800\udfff"
        brand, model = extract_vehicle_info(corrupted_title, corrupted_content)
        assert brand == BRAND_HYUNDAI
        assert "Ioniq 5" in model or "아이오닉" in model

        matcher = VehicleMatcher()
        matched_brand, matched_model = matcher.match(corrupted_title, corrupted_content)
        assert matched_brand == BRAND_HYUNDAI
        assert "Ioniq 5" in matched_model or "아이오닉" in matched_model


class TestDateNormalization:
    """Test date normalization across filters and models."""

    def test_normalize_date_formats(self):
        """Verify normalize_date parses various date formats into YYYY-MM-DD."""
        today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        assert normalize_date("2026-03-15") == "2026-03-15"
        assert normalize_date("2026.03.15") == "2026-03-15"
        assert normalize_date("2026/03/15") == "2026-03-15"
        assert normalize_date("20260315") == "2026-03-15"
        assert normalize_date("2026년 3월 15일") == "2026-03-15"
        assert normalize_date("2026. 3. 15.") == "2026-03-15"
        assert normalize_date("2026-03-15T09:30:00Z") == "2026-03-15"
        assert normalize_date("2026-03-15 14:20:00") == "2026-03-15"

        # Korean relative formats
        assert normalize_date("오늘") == today_iso
        assert normalize_date("방금") == today_iso
        assert normalize_date("14:35") == today_iso

        # Corrupted string containing date
        assert normalize_date("2026-03-15\x00\ufeff") == "2026-03-15"

        # Invalid fallback
        assert normalize_date("completely-invalid-date") == today_iso
        assert normalize_date(None) == today_iso
        assert normalize_date("") == today_iso

    def test_parse_date_str_models(self):
        """Verify models.complaint.parse_date_str correctly standardizes dates."""
        today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        assert parse_date_str("2026.04.10") == "2026-04-10"
        assert parse_date_str("2026/04/10") == "2026-04-10"
        assert parse_date_str("2026년 4월 10일") == "2026-04-10"
        assert parse_date_str("오늘 13:00") == today_iso
        assert parse_date_str("방금전") == today_iso
        assert parse_date_str("invalid_date_xyz") == today_iso


class TestModelPayloadValidationAndQuarantine:
    """Test schema validation, strict mode, and graceful quarantine in models."""

    def test_raw_post_sanitization(self):
        """Verify RawPost sanitizes corrupted fields on instantiation."""
        post = RawPost(
            id="post_001\x00",
            source="clien\x1f",
            url="https://example.com/post/1\ufeff",
            title="테슬라 화재\x07",
            content="배터리 폭발 위험\ud800\udfff",
            author="홍길동\x00",
            created_at="2026-03-15\x00",
        )
        assert post.id == "post_001"
        assert post.source == "clien"
        assert post.url == "https://example.com/post/1"
        assert post.title == "테슬라 화재"
        assert post.content == "배터리 폭발 위험"
        assert post.author == "홍길동"
        assert post.created_at == "2026-03-15"

    def test_complaint_record_validate_and_strict(self):
        """Verify ComplaintRecord.validate and strict mode in from_dict."""
        valid_data = {
            "id": "rec_001",
            "source": "bobaedream",
            "url": "https://bobaedream.co.kr/view?no=123",
            "title": "EV6 ICCU 고장",
            "author": "user1",
            "created_at": "2026-03-15",
            "vehicle_brand": "기아",
            "vehicle_model": "EV6",
            "defect_category": "배터리/충전",
            "summary": "주행 중 배터리 경고등 점등",
        }

        # Valid entry
        rec = ComplaintRecord.from_dict(valid_data, strict=True)
        is_valid, errors = rec.validate(strict=True)
        assert is_valid is True
        assert len(errors) == 0

        # Invalid entry with missing id in strict mode -> ValueError
        invalid_data_no_id = valid_data.copy()
        invalid_data_no_id["id"] = ""
        with pytest.raises(ValueError, match="Strict validation failed"):
            ComplaintRecord.from_dict(invalid_data_no_id, strict=True)

        # Invalid entry with empty content in strict mode -> ValueError
        invalid_data_no_text = valid_data.copy()
        invalid_data_no_text["title"] = ""
        invalid_data_no_text["summary"] = ""
        with pytest.raises(ValueError, match="Strict validation failed"):
            ComplaintRecord.from_dict(invalid_data_no_text, strict=True)

        # Invalid entry with out-of-bounds severity_index in strict mode -> ValueError
        invalid_data_bad_num = valid_data.copy()
        invalid_data_bad_num["severity_index"] = 999.0
        with pytest.raises(ValueError, match="Strict validation failed"):
            ComplaintRecord.from_dict(invalid_data_bad_num, strict=True)

        # Invalid entry in quarantine mode -> quarantined record marked
        quarantined = ComplaintRecord.from_dict(invalid_data_no_id, quarantine=True)
        assert isinstance(quarantined, ComplaintRecord)
        assert quarantined.is_authentic_defect is False
        assert "QUARANTINED" in quarantined.filter_reason

        # Non-strict mode tolerates missing id gracefully
        lenient_rec = ComplaintRecord.from_dict(invalid_data_no_id, strict=False)
        assert isinstance(lenient_rec, ComplaintRecord)

    def test_defect_report_alias_backwards_compatibility(self):
        """Verify DefectReport backward-compatible alias behaves identically to ComplaintRecord."""
        data = {
            "id": "dr_001",
            "source": "clien",
            "url": "https://clien.net/1",
            "title": "아이오닉 5 급발진 의심",
            "created_at": "2026-03-15",
            "vehicle_brand": "현대",
            "vehicle_model": "아이오닉 5",
            "defect_category": "구동계/모터",
            "summary": "갑작스러운 급가속 현상",
        }
        report = DefectReport.from_dict(data)
        assert isinstance(report, ComplaintRecord)
        assert report.id == "dr_001"
        assert report.vehicle_brand == "현대"

        # DefectReport.from_json
        json_str = json.dumps(data)
        report_from_json = DefectReport.from_json(json_str)
        assert report_from_json.id == "dr_001"

    def test_daily_report_payload_graceful_quarantine(self):
        """Verify DailyReportPayload gracefully quarantines invalid entries and retains valid ones."""
        raw_payload = {
            "generated_at": "2026-03-15T12:00:00Z",
            "pipeline_version": "1.0.0",
            "reports": [
                # Valid entry 1
                {
                    "id": "valid_1",
                    "source": "clien",
                    "url": "https://clien.net/post/101",
                    "title": "아이오닉5 충전 도중 멈춤",
                    "author": "운전자",
                    "created_at": "2026-03-15",
                    "vehicle_brand": "현대",
                    "vehicle_model": "아이오닉 5",
                    "defect_category": "배터리/충전",
                    "summary": "충전기 체결 후 5분 뒤 중단",
                },
                # Invalid entry 1: Completely empty dict (missing id and text)
                {},
                # Invalid entry 2: Non-dict entry
                "string_entry_corrupted",
                # Invalid entry 3: Missing essential url & title & summary
                {
                    "id": "",
                    "source": "clien",
                    "url": "",
                    "title": "",
                    "summary": "",
                },
                # Valid entry 2
                {
                    "id": "valid_2",
                    "source": "bobaedream",
                    "url": "https://bobaedream.co.kr/view?no=202",
                    "title": "EV6 ICCU 교체 후기",
                    "author": "차주",
                    "created_at": "2026-03-15",
                    "vehicle_brand": "기아",
                    "vehicle_model": "EV6",
                    "defect_category": "배터리/충전",
                    "summary": "경고등 점등 후 교체 진행",
                },
            ],
            "total_complaints_today": 2,
            "top_defect_categories": [{"category": "배터리/충전", "count": 2}],
        }

        # Parse with quarantine_invalid=True (the hardened default)
        payload = DailyReportPayload.from_dict(raw_payload, quarantine_invalid=True)

        # Ensure valid reports are preserved
        assert len(payload.reports) == 2
        assert payload.reports[0]["id"] == "valid_1"
        assert payload.reports[1]["id"] == "valid_2"

        # Ensure corrupted entries were quarantined without crashing
        assert len(payload.quarantined_reports) == 3
        assert payload.quarantined_count == 3
        for q in payload.quarantined_reports:
            assert q["is_quarantined"] is True
            assert "reason" in q
            assert len(q["reason"]) > 0

        # Validate whole payload structure
        is_valid, validation_errors = DailyReportPayload.validate_payload(payload.to_dict())
        assert is_valid is True
        assert len(validation_errors) == 0

    def test_daily_report_payload_from_json(self):
        """Verify DailyReportPayload.from_json handles valid JSON, bytes, and malformed JSON safely."""
        valid_dict = {
            "generated_at": "2026-03-15T12:00:00Z",
            "pipeline_version": "1.0.0",
            "reports": [
                {
                    "id": "json_post_1",
                    "source": "naver_cafe",
                    "url": "https://cafe.naver.com/1",
                    "title": "테슬라 모델3 단차 문제\x00",
                    "created_at": "2026-03-15",
                    "defect_category": "외관/도장",
                    "summary": "도어 단차가 너무 심함",
                }
            ],
        }

        # From JSON string
        json_str = json.dumps(valid_dict)
        payload = DailyReportPayload.from_json(json_str)
        assert len(payload.reports) == 1
        assert payload.reports[0]["title"] == "테슬라 모델3 단차 문제"  # null byte sanitized
        assert payload.reports[0]["id"] == "json_post_1"

        # From UTF-8 bytes
        json_bytes = json_str.encode("utf-8")
        payload_bytes = DailyReportPayload.from_json(json_bytes)
        assert len(payload_bytes.reports) == 1

        # From corrupted/malformed JSON string: must not crash
        malformed_json = "{ invalid json string [["
        quarantined_payload = DailyReportPayload.from_json(malformed_json)
        assert isinstance(quarantined_payload, DailyReportPayload)
        assert len(quarantined_payload.reports) == 0
        assert quarantined_payload.quarantined_count == 1
        assert "Corrupt JSON" in quarantined_payload.quarantined_reports[0]["reason"]
