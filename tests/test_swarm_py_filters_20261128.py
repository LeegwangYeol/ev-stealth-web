"""Regression tests for bugs found during py-filters swarm audit (2026-11-28)."""

from __future__ import annotations

import math

from filters.defect_classifier import DefectClassifier
from filters.slang_filter import SlangFilter
from filters.slang_lexicon import find_matching_slang


def test_find_matching_slang_respects_zero_and_negative_max_length() -> None:
    """max_length <= 0 must return [] rather than bypassing truncation."""
    text = "내 차 ICCU 폭탄 터져서 주행 중 멈춤"
    assert find_matching_slang(text, max_length=0) == []
    assert find_matching_slang(text, max_length=-5) == []

    sf_zero = SlangFilter(max_length=0)
    assert sf_zero.normalize_text(text) == ""
    assert sf_zero.find_matching_slang(text) == []
    assert sf_zero.extract_slang_tags(text) == []
    assert sf_zero.is_slang_present(text) is False

    sf_neg = SlangFilter(max_length=-1)
    assert sf_neg.find_matching_slang(text) == []


def test_unspaced_double_negation_persistent_defect_not_inverted() -> None:
    """Unspaced persistent defect expressions ('안없어지고', '없어지지않고') must stay negative."""
    dc = DefectClassifier()
    for text in (
        "내 차 주행 중 잡소리가 안없어지고 계속 납니다.",
        "출고 후 하부 잡소리가 안없어짐 진짜 스트레스",
        "내 차 실내 잡소리가 없어지지않고 계속 울립니다.",
        "출고한 차 잡소리가 없어지질않네요 사업소 가야하나",
    ):
        res = dc.evaluate_stage3_scoping(text)
        assert "잡소리" not in res["negated_defects"], f"Falsely negated for: {text}"
        assert res["polarity"] < 0.0, f"Expected negative polarity for: {text}"

    # Genuine disappearance ('없어짐') should still count as negated
    resolved = dc.evaluate_stage3_scoping("서비스센터 다녀오니 잡소리가 싹 없어짐")
    assert "잡소리" in resolved["negated_defects"]


def test_weatherstrip_malfunction_cues_consistent_across_stages() -> None:
    """Weatherstrip physical failures passing Stage 1 must also pass Stages 2-4."""
    dc = DefectClassifier()
    res = dc.process_post(
        {
            "title": "웨더스트립 불량",
            "content": "출고 3일 만에 도어 웨더스트립이 빠져서 덜렁거림.",
        }
    )
    assert res.is_authentic_defect is True
    assert res.defect_category == "BUILD_QUALITY"
    assert res.sentiment_polarity < 0.0
    assert res.confidence_score >= 0.35

    # Neutral mention without malfunction cue must still be rejected at Stage 2
    neutral = dc.evaluate_stage2_ownership("내 차 출고하고 웨더스트립 샀어요")
    assert neutral[0] is False


def test_stage3_respects_explicit_slang_matches_for_rice_cooker_homograph() -> None:
    """When slang_matches excludes '밥솥' (appliance context), Stage 3 must not re-match it in later clauses."""
    dc = DefectClassifier()
    text = "캠핑용 전기 밥솥 가져감. 밥솥 쓰려는데 V2L 차단됨."
    slang = find_matching_slang(text)
    assert all(e.term != "밥솥" for e in slang)

    res = dc.evaluate_stage3_scoping(text, slang_matches=slang, _pre_sanitized=True)
    assert "밥솥" not in res["matched_terms"]


def test_calculate_confidence_guards_invalid_polarity_and_category() -> None:
    """calculate_confidence must safely handle bool, None, NaN, Inf, and non-str category."""
    dc = DefectClassifier()
    text = "내 차 출고 후 ICCU 고장나서 경고등 떴어요"
    for bad_pol in (None, True, False, float("nan"), float("inf"), float("-inf")):
        score = dc.calculate_confidence(text, "BATTERY_CHARGING", polarity=bad_pol)  # type: ignore[arg-type]
        assert 0.0 <= score <= 1.0
        assert math.isfinite(score)

    score_bad_cat = dc.calculate_confidence(text, None, polarity=0.0)  # type: ignore[arg-type]
    assert 0.0 <= score_bad_cat <= 1.0
    score_unhashable = dc.calculate_confidence(text, ["BATTERY_CHARGING"], polarity=0.0)  # type: ignore[arg-type]
    assert 0.0 <= score_unhashable <= 1.0
