"""Swarm audit regression tests for filters/*.py and models/*.py (2026-11-24)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import math
import unittest

from filters.defect_classifier import DefectClassifier, sanitize_text
from filters.slang_lexicon import find_matching_slang
from filters.spam_filter import SpamFilter, sanitize_input
from filters.vehicle_matcher import (
    BRAND_HYUNDAI,
    BRAND_OTHER,
    BRAND_TESLA,
    _sanitize_matcher_text,
    extract_vehicle_info,
)
from models.complaint import (
    ComplaintRecord,
    DailyReportPayload,
    DailyReportStatistics,
    RawPost,
    parse_date_str,
    sanitize_string,
    validate_report_entry,
)


class TestSwarmPyFiltersAndModels20261124(unittest.TestCase):
    def setUp(self) -> None:
        self.clf = DefectClassifier()
        self.sf = SpamFilter()

    def test_negation_an_na_gam_and_unspaced_eopsi_do_not_invert_defects(self) -> None:
        """'안나감', '경고없이', '양심없이', '없을 줄' must not invert real defects to positive polarity."""
        defect_texts = [
            "내 차 주행 중 거북이등 뜨고 차 안나감 ㅠㅠ",
            "내 차 주행 중 출력 저하로 차가 안나가네요",
            "내 차 고속도로 주행 중 ICCU 경고없이 멈춤",
            "내 차 도어 단차 양심없이 심하네요",
            "내 차 결함 대응 개념없는 센터",
            "내 차 단차 없을 줄 알았는데 엄청 벌어져 있어요",
        ]
        for text in defect_texts:
            stage3 = self.clf.evaluate_stage3_scoping(text)
            self.assertEqual(
                stage3["negated_defects"],
                [],
                f"Falsely negated defect in '{text}': {stage3}",
            )
            self.assertLess(stage3["polarity"], 0.0, f"Polarity must remain negative for '{text}'")

    def test_spaced_an_naogo_negates_emission_defects_but_not_part_malfunctions_or_hearsay(self) -> None:
        """'잡소리 안 나오고 조용해요' negates 잡소리, while hearsay and part non-deployment do not."""
        praise = self.clf.evaluate_stage3_scoping("내 차 1년 탔는데 잡소리 안 나오고 너무 조용해요")
        self.assertIn("잡소리", praise["negated_defects"])
        self.assertGreater(praise["polarity"], 0.0)

        hearsay = self.clf.evaluate_stage3_scoping("내 차 잡소리 안 나온다더니 고속도로 올리자마자 엄청 나네요")
        self.assertEqual(hearsay["negated_defects"], [])
        self.assertLess(hearsay["polarity"], 0.0)

        door_handle = self.clf.evaluate_stage3_scoping("내 차 도어캐치 실종 문제로 손잡이가 안 나와요")
        self.assertNotIn("도어캐치 실종", door_handle["negated_defects"])
        self.assertLess(door_handle["polarity"], 0.0)

        blinker = self.clf.evaluate_stage3_scoping("내 차 깜빡이 먹통이라 소리가 안 나와요")
        self.assertNotIn("먹통", blinker["negated_defects"])
        self.assertLess(blinker["polarity"], 0.0)

    def test_unspaced_negated_positives_and_sago_sip_idiom(self) -> None:
        """Unspaced negated praise ('불만족', '비추천', '안좋음') scores negative; '사고 싶다' avoids '사고'."""
        for neg_text in ("서비스 대응 불만족입니다", "승차감 안좋음 비추천", "마감 만족스럽지않다"):
            res = self.clf.evaluate_stage3_scoping(neg_text)
            self.assertLess(res["polarity"], 0.0, f"Expected negative polarity for '{neg_text}', got {res}")

        buy_wish = self.clf.evaluate_stage3_scoping("아이오닉5 사고 싶어요 단차 전혀 없고 만족합니다")
        self.assertNotIn("사고", buy_wish["matched_terms"])
        self.assertGreater(buy_wish["polarity"], 0.3)

        real_accident = self.clf.evaluate_stage3_scoping("내 차 브레이크 밀려서 접촉사고 날 뻔했습니다")
        self.assertIn("사고", real_accident["matched_terms"])
        self.assertLess(real_accident["polarity"], -0.5)

    def test_slang_lexicon_korean_and_ascii_boundaries(self) -> None:
        """'해메기', '메기찜', 'toyota 벽돌', 'bdsm 블랙아웃' must not trigger false-positive slang."""
        self.assertNotIn("메기", [e.term for e in find_matching_slang("서비스센터 찾느라 해메기만 했네요")])
        self.assertNotIn("메기", [e.term for e in find_matching_slang("저녁에 메기찜 먹었습니다")])

        mixed = [e.term for e in find_matching_slang("toyota 벽돌 bdsm 블랙아웃 siccu 폭탄")]
        self.assertNotIn("OTA 벽돌", mixed)
        self.assertNotIn("DSM 블랙아웃", mixed)
        self.assertNotIn("ICCU 폭탄", mixed)

        valid = [e.term for e in find_matching_slang("OTA 벽돌 DSM 블랙아웃 BMS 에러 TCAM 먹통")]
        self.assertIn("OTA 벽돌", valid)
        self.assertIn("DSM 블랙아웃", valid)
        self.assertIn("BMS 에러", valid)
        self.assertIn("TCAM 먹통", valid)

    def test_spam_filter_financial_homographs_and_water_and_neutral_feature_boundaries(self) -> None:
        """Korean homographs (차주가, 구매도, 현실적, 화물 차량) and benign V2L queries behave accurately."""
        owner_post = "원 차주가 신차 구매도 후회되고 현실적으로 감가가 너무 심합니다"
        is_disc, reason = self.sf.evaluate_stage1_noise(owner_post)
        self.assertFalse(is_disc, f"Owner post falsely flagged as stock spam: {reason}")

        real_stock = "현대차주가 실적발표 이후 매도세 나스닥 급락"
        is_stock_disc, _ = self.sf.evaluate_stage1_noise(real_stock)
        self.assertTrue(is_stock_disc)

        # '화물 차량' / '건물 차단기' must not trigger '물 차' defect protection in Stage 1 or Stage 2
        self.assertTrue(self.sf.is_spam("1톤 화물 차량 보조금 궁금합니다"))
        self.assertTrue(self.sf.is_spam("아파트 건물 차단기 등록 어떻게 하나요?"))
        is_owner, _ = self.clf.evaluate_stage2_ownership("내 차 1톤 화물 차량 적재함 리뷰")
        self.assertFalse(is_owner)

        # Benign V2L prospective inquiry without malfunction cue must be filtered as inquiry
        self.assertTrue(self.sf.is_spam("아이오닉5 V2L 기능 어떤가요 살까요?"))

    def test_vehicle_matcher_boundaries_and_genesis_specificity(self) -> None:
        """Prevent '돈 모와' -> Model Y, 'bm3 highland123' -> Model 3 Highland, and prefer specific Genesis models."""
        self.assertEqual(extract_vehicle_info("돈 모와 차 샀습니다"), (BRAND_OTHER, "전기차"))
        self.assertEqual(extract_vehicle_info("bm3 highland123 test"), (BRAND_OTHER, "전기차"))
        self.assertEqual(extract_vehicle_info("bm3 하이랜드산 test"), (BRAND_OTHER, "전기차"))
        self.assertEqual(extract_vehicle_info("m3 highland 출고"), (BRAND_TESLA, "Model 3 Highland"))
        self.assertEqual(extract_vehicle_info("모와 롱레인지 출고 후기"), (BRAND_TESLA, "Model Y"))
        self.assertEqual(extract_vehicle_info("제네시스 전기차 GV60"), (BRAND_HYUNDAI, "GV60"))
        self.assertEqual(extract_vehicle_info("제네시스 G80e 충전"), (BRAND_HYUNDAI, "G80 EV"))
        self.assertEqual(extract_vehicle_info("제네시스 GV70e 결함"), (BRAND_HYUNDAI, "GV70 EV"))
        self.assertEqual(extract_vehicle_info("제네시스 결함 후기"), (BRAND_HYUNDAI, "제네시스"))

    def test_models_bytes_bool_nan_validation_and_relative_dates(self) -> None:
        """Verify bytes decoding, bool rejection, NaN/Inf sanitization, and relative Korean date timestamps."""
        cp949_title = "고장 심각".encode("cp949")
        raw = RawPost(id=0, title=cp949_title, source=b"clien")
        self.assertEqual(raw.post_id, "0")
        self.assertEqual(raw.title, "고장 심각")
        self.assertEqual(raw.platform, "clien")

        raw_dict = RawPost.from_dict({"id": False, "title": cp949_title, "comments": [cp949_title, False]})
        self.assertEqual(raw_dict.post_id, "")
        self.assertEqual(raw_dict.title, "고장 심각")
        self.assertEqual(raw_dict.comments, ["고장 심각"])

        rec = ComplaintRecord.from_dict({"id": "r1", "title": cp949_title, "vehicle_brand": False})
        self.assertEqual(rec.title, "고장 심각")
        self.assertEqual(rec.vehicle_brand, "")

        # Bool id / text must fail validation; None / bool generated_at must fail payload validation
        ok_bool, _ = validate_report_entry({"id": False, "title": False})
        self.assertFalse(ok_bool)
        ok_payload, errs = DailyReportPayload.validate_payload({"generated_at": None, "reports": []})
        self.assertFalse(ok_payload)
        self.assertTrue(errs)
        ok_payload_bool, _ = DailyReportPayload.validate_payload({"generated_at": False, "reports": []})
        self.assertFalse(ok_payload_bool)

        # Relative Korean date with time suffix & NaN/Inf numeric timestamps
        yesterday_utc = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        two_days_ago_utc = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")
        today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.assertEqual(parse_date_str("어제 14:30"), yesterday_utc)
        self.assertEqual(parse_date_str("그제 09:00"), two_days_ago_utc)
        self.assertEqual(parse_date_str(float("nan")), today_utc)
        self.assertEqual(parse_date_str(float("inf")), today_utc)

        # DailyReportStatistics emits valid JSON integers even with NaN/bool inputs
        bad_stats = DailyReportStatistics(
            total_scraped=float("nan"),  # type: ignore[arg-type]
            total_filtered_defects=True,  # type: ignore[arg-type]
            avg_negativity_score=float("inf"),
            critical_defect_count=-3,
        )
        stats_dict = bad_stats.to_dict()
        self.assertEqual(stats_dict["total_scraped"], 0)
        self.assertEqual(stats_dict["total_filtered_defects"], 0)
        self.assertEqual(stats_dict["avg_negativity_score"], 0.0)
        self.assertEqual(stats_dict["critical_defect_count"], 0)
        json.dumps(stats_dict, allow_nan=False)

        # max_len guards across all sanitizers
        for fn in (sanitize_text, sanitize_input, sanitize_string, _sanitize_matcher_text):
            self.assertEqual(fn("abc", None), "abc")  # type: ignore[arg-type]
            self.assertEqual(fn("abc", True), "abc")  # type: ignore[arg-type]
            self.assertEqual(fn("abc", -5), "")
            self.assertEqual(fn("abc", 0), "")


if __name__ == "__main__":
    unittest.main()
