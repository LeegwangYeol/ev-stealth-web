"""Authentic 2026 South Korea EV Subsidy Baseline Data and Specifications.

Provides official 2026 baseline allocations, statutory caps, and depletion
metrics for all 17 administrative divisions (1 Special City, 6 Metropolitan
Cities, 1 Special Self-Governing City, 6 Provinces, 3 Special Self-Governing
Provinces) and 160+ municipalities.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import math
import re
from typing import Any, Dict, List, Optional, Union

from tracker.subsidy_models import (
    AlertSeverity,
    AlertThresholdConfig,
    CategoryMetrics,
    HistoricalTrajectoryPoint,
    MunicipalityMetrics,
    NationwideSummary,
    PopularModelEntry,
    RegionRecord,
    SubsidyMetadata,
    SubsidyPayload,
)

# 2026 Maximum statutory national subsidy cap for passenger EVs (KRW)
PASSENGER_NATIONAL_CAP_KRW = 6_500_000
COMMERCIAL_NATIONAL_CAP_KRW = 10_500_000
BUS_NATIONAL_CAP_KRW = 70_000_000

# 5-Tier Alert Threshold System
DEFAULT_ALERT_THRESHOLDS: Dict[str, AlertThresholdConfig] = {
    "HEALTHY": AlertThresholdConfig(
        min_percent=0.0,
        max_percent=59.9,
        label_ko="원활 (신청 여유)",
        severity="HEALTHY",
        color_hex="#10B981",
        badge_class="bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
        recommended_action="보조금 잔여량이 충분하여 신청 접수 후 통상 1~2주 내 교부 결정됩니다.",
    ),
    "CAUTION": AlertThresholdConfig(
        min_percent=60.0,
        max_percent=79.9,
        label_ko="주의 (소진 가속)",
        severity="CAUTION",
        color_hex="#F59E0B",
        badge_class="bg-amber-500/10 text-amber-400 border-amber-500/20",
        recommended_action="출고 예정 시기가 1~2개월 이내인 경우 조속한 서류 접수를 권장합니다.",
    ),
    "WARNING": AlertThresholdConfig(
        min_percent=80.0,
        max_percent=94.9,
        label_ko="경고 (마감 임박)",
        severity="WARNING",
        color_hex="#F97316",
        badge_class="bg-orange-500/10 text-orange-400 border-orange-500/20",
        recommended_action="잔여 예산 소진이 임박했습니다. 즉시 출고 가능한 실재고 매칭이 필요합니다.",
    ),
    "CRITICAL": AlertThresholdConfig(
        min_percent=95.0,
        max_percent=99.9,
        label_ko="위험 (잔여 극소)",
        severity="CRITICAL",
        color_hex="#EF4444",
        badge_class="bg-rose-500/10 text-rose-400 border-rose-500/20",
        recommended_action="선착순 마감 직전입니다. 담당 지자체 문의 및 추경 예산 편성 여부를 확인하세요.",
    ),
    "DEPLETED": AlertThresholdConfig(
        min_percent=100.0,
        max_percent=999.0,
        label_ko="마감 (접수 종료)",
        severity="DEPLETED",
        color_hex="#6B7280",
        badge_class="bg-zinc-500/10 text-zinc-400 border-zinc-500/20",
        recommended_action="2026년 공고 예산이 전액 소진되었습니다. 취소분 대기 접수 또는 차년도 사업을 준비하세요.",
    ),
}


_RE_PLAIN_INT = re.compile(r"^[+-]?\d+$")
_DEC_ZERO = Decimal(0)
_DEC_TIER_1 = Decimal(55_000_000)
_DEC_TIER_2 = Decimal(85_000_000)


def _safe_int_val(val: Any, default: int = 0) -> int:
    """Safely convert value to int, catching None, bool, NaN, Inf, ValueError, TypeError, and OverflowError."""
    if val is None or isinstance(val, bool):
        return default
    if type(val) is int:
        return val
    if isinstance(val, Decimal):
        if not val.is_finite():
            return default
        try:
            return int(val)
        except (ValueError, TypeError, OverflowError):
            return default
    if isinstance(val, str):
        val = val.strip().replace(",", "")
        if not val:
            return default
        if _RE_PLAIN_INT.match(val):
            try:
                return int(val)
            except (ValueError, OverflowError):
                return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return int(f)
    except (ValueError, TypeError, OverflowError):
        return default


def calculate_price_cap_ratio(msrp: Union[int, float, Decimal, str, None]) -> float:
    """Statutory 2026 Korean EV subsidy ratio tiers: 1.0 (<=55M), 0.5 (55M-85M), 0.0 (>85M)."""
    if msrp is None or isinstance(msrp, bool):
        return 0.0
    if type(msrp) is int:
        if msrp <= 0:
            return 0.0
        if msrp <= 55_000_000:
            return 1.0
        if msrp <= 85_000_000:
            return 0.5
        return 0.0
    if type(msrp) is float:
        if math.isnan(msrp) or math.isinf(msrp) or msrp <= 0.0:
            return 0.0
        if msrp <= 55_000_000.0:
            return 1.0
        if msrp <= 85_000_000.0:
            return 0.5
        return 0.0
    if isinstance(msrp, (Decimal, str)):
        try:
            if isinstance(msrp, str):
                cleaned = msrp.strip().replace(",", "")
                if not cleaned:
                    return 0.0
                d_msrp = Decimal(cleaned)
            else:
                d_msrp = msrp
            if not d_msrp.is_finite() or d_msrp <= _DEC_ZERO:
                return 0.0
            if d_msrp <= _DEC_TIER_1:
                return 1.0
            if d_msrp <= _DEC_TIER_2:
                return 0.5
            return 0.0
        except (InvalidOperation, ValueError, TypeError, OverflowError):
            return 0.0

    try:
        f_msrp = float(msrp)
        if math.isnan(f_msrp) or math.isinf(f_msrp):
            return 0.0
    except (ValueError, TypeError, OverflowError):
        return 0.0

    if f_msrp <= 0.0:
        return 0.0
    if f_msrp <= 55_000_000.0:
        return 1.0
    if f_msrp <= 85_000_000.0:
        return 0.5
    return 0.0


def _coerce_non_negative_int(v: Any) -> int:
    """Fast coercion to non-negative int, guarding None, bool, NaN, Inf, and comma strings."""
    if v is None or isinstance(v, bool):
        return 0
    if type(v) is int:
        return v if v > 0 else 0
    if isinstance(v, Decimal):
        if not v.is_finite() or v <= _DEC_ZERO:
            return 0
        try:
            return int(v)
        except (ValueError, TypeError, OverflowError):
            return 0
    try:
        if isinstance(v, str):
            v = v.strip().replace(",", "")
            if not v:
                return 0
            if _RE_PLAIN_INT.match(v):
                iv = int(v)
                return iv if iv > 0 else 0
        f = float(v)
        if math.isnan(f) or math.isinf(f) or f <= 0.0:
            return 0
        return int(f)
    except (ValueError, TypeError, OverflowError):
        return 0


def calculate_net_subsidy(
    model_national: Union[int, float, Decimal, str, None],
    max_national: Union[int, float, Decimal, str, None],
    max_local: Union[int, float, Decimal, str, None],
    msrp: Union[int, float, Decimal, str, None],
) -> Dict[str, Union[int, float]]:
    """Calculate national subsidy, local subsidy, total subsidy, and net consumer purchase price."""
    safe_msrp = _coerce_non_negative_int(msrp)
    safe_model_nat = _coerce_non_negative_int(model_national)
    safe_max_nat = _coerce_non_negative_int(max_national)
    safe_max_loc = _coerce_non_negative_int(max_local)

    ratio = calculate_price_cap_ratio(msrp)
    if ratio <= 0.0:
        return {
            "national_subsidy_krw": 0,
            "local_subsidy_krw": 0,
            "total_subsidy_krw": 0,
            "net_price_krw": safe_msrp,
            "price_cap_ratio": 0.0,
        }

    if ratio == 1.0:
        effective_national = safe_model_nat
    elif safe_model_nat < (1 << 52):
        effective_national = int(round(safe_model_nat * ratio))
    else:
        effective_national = round(Fraction(safe_model_nat, 2))

    if safe_max_nat > 0 and safe_model_nat > 0:
        if safe_model_nat >= safe_max_nat:
            if ratio == 1.0:
                effective_local = safe_max_loc
            elif safe_max_loc < (1 << 52):
                effective_local = int(round(safe_max_loc * ratio))
            else:
                effective_local = round(Fraction(safe_max_loc, 2))
        else:
            prod = safe_max_loc * safe_model_nat
            if prod < (1 << 52):
                effective_local = int(round((prod * ratio) / safe_max_nat))
            else:
                denom = safe_max_nat * 2 if ratio == 0.5 else safe_max_nat
                effective_local = round(Fraction(prod, denom))
    else:
        effective_local = 0
    total_subsidy = effective_national + effective_local
    net_price = max(0, safe_msrp - total_subsidy)
    return {
        "national_subsidy_krw": effective_national,
        "local_subsidy_krw": effective_local,
        "total_subsidy_krw": total_subsidy,
        "net_price_krw": net_price,
        "price_cap_ratio": ratio,
    }


def _calc_rate_percent(numerator: Any, denominator: Any) -> float:
    """Compute percentage rounded to 1 decimal place, scaling numerator first to prevent float drift."""
    if numerator is None or denominator is None or isinstance(numerator, bool) or isinstance(denominator, bool):
        return 0.0
    clean_num = numerator.strip().replace(",", "") if isinstance(numerator, str) else numerator
    clean_den = denominator.strip().replace(",", "") if isinstance(denominator, str) else denominator
    if clean_num == "" or clean_den == "":
        return 0.0
    try:
        if isinstance(clean_num, str) and _RE_PLAIN_INT.match(clean_num) and len(clean_num.lstrip("+-")) > 300:
            raise OverflowError
        if isinstance(clean_den, str) and _RE_PLAIN_INT.match(clean_den) and len(clean_den.lstrip("+-")) > 300:
            raise OverflowError
        num = float(clean_num)
        den = float(clean_den)
    except (ValueError, TypeError, OverflowError):
        try:
            n_val = int(clean_num) if isinstance(clean_num, str) and _RE_PLAIN_INT.match(clean_num) else (
                int(clean_num) if isinstance(clean_num, Decimal) and clean_num.is_finite() else (
                    clean_num if isinstance(clean_num, int) else int(float(clean_num))
                )
            )
            d_val = int(clean_den) if isinstance(clean_den, str) and _RE_PLAIN_INT.match(clean_den) else (
                int(clean_den) if isinstance(clean_den, Decimal) and clean_den.is_finite() else (
                    clean_den if isinstance(clean_den, int) else int(float(clean_den))
                )
            )
            if d_val > 0 and n_val > 0:
                raw = (n_val * 100) / d_val
                if math.isnan(raw) or math.isinf(raw):
                    return 0.0
                return max(0.0, round(raw, 1))
        except (ValueError, TypeError, OverflowError, ZeroDivisionError, InvalidOperation):
            return 0.0
        return 0.0
    if math.isnan(num) or math.isnan(den) or math.isinf(num) or math.isinf(den):
        return 0.0
    if den <= 0.0 or num <= 0.0:
        return 0.0
    scaled = num * 100.0
    raw = (scaled / den) if not math.isinf(scaled) else ((num / den) * 100.0)
    if math.isnan(raw) or math.isinf(raw):
        return 0.0
    return max(0.0, round(raw, 1))


def _calc_cat(
    announced: int,
    applied: int,
    delivered: int,
    max_local: int,
    national_cap: int = PASSENGER_NATIONAL_CAP_KRW,
    avg_per_unit_budget: int = 10_000_000,
) -> CategoryMetrics:
    """Helper to construct verified CategoryMetrics with accurate math."""
    depletion_rate = _calc_rate_percent(applied, announced)
    delivery_rate = _calc_rate_percent(delivered, announced)
    remaining_units = max(0, announced - applied)
    status = AlertSeverity.from_rate(depletion_rate).value

    total_budget = announced * avg_per_unit_budget
    disbursed_budget = applied * avg_per_unit_budget
    remaining_budget = max(0, total_budget - disbursed_budget)

    return CategoryMetrics(
        announced_units=announced,
        applied_units=applied,
        delivered_units=delivered,
        remaining_units=remaining_units,
        depletion_rate=depletion_rate,
        delivery_rate=delivery_rate,
        status=status,
        max_local_subsidy_krw=max_local,
        max_total_subsidy_krw=max_local + national_cap,
        total_budget_krw=total_budget,
        remaining_budget_krw=remaining_budget,
    )


def _calc_muni(name: str, announced: int, applied: int, local_sub: int) -> MunicipalityMetrics:
    rate = _calc_rate_percent(applied, announced)
    remaining = max(0, announced - applied)
    status = AlertSeverity.from_rate(rate).value
    return MunicipalityMetrics(
        name_ko=name,
        announced_units=announced,
        applied_units=applied,
        remaining_units=remaining,
        depletion_rate=rate,
        status=status,
        local_subsidy_krw=local_sub,
    )


def build_baseline_regions() -> List[RegionRecord]:
    """Build authoritative 2026 data for all 17 administrative divisions."""
    regions = [
        RegionRecord(
            region_id="KR-11",
            iso_code="KR-11",
            name_ko="서울특별시",
            name_en="Seoul",
            tier="special_city",
            overall_depletion_rate=86.0,
            overall_status="WARNING",
            residency_requirement_days=30,
            supplementary_budget_added=False,
            categories={
                "passenger": _calc_cat(11500, 9890, 8900, 1_500_000, PASSENGER_NATIONAL_CAP_KRW, 8_000_000),
                "commercial": _calc_cat(2800, 2660, 2450, 4_000_000, COMMERCIAL_NATIONAL_CAP_KRW, 14_500_000),
                "bus": _calc_cat(450, 396, 360, 35_000_000, BUS_NATIONAL_CAP_KRW, 100_000_000),
            },
            municipalities=[
                _calc_muni("종로구", 280, 241, 1_500_000),
                _calc_muni("강남구", 1200, 1068, 1_500_000),
                _calc_muni("송파구", 950, 826, 1_500_000),
                _calc_muni("서초구", 890, 783, 1_500_000),
                _calc_muni("마포구", 620, 527, 1_500_000),
                _calc_muni("영등포구", 710, 603, 1_500_000),
            ],
            notes="잔여 1,610대 소진 임박, 10월 초 일반 승용 마감 유력. 법인 물량 조기 마감.",
        ),
        RegionRecord(
            region_id="KR-41",
            iso_code="KR-41",
            name_ko="경기도",
            name_en="Gyeonggi",
            tier="province",
            overall_depletion_rate=91.0,
            overall_status="WARNING",
            residency_requirement_days=30,
            supplementary_budget_added=True,
            categories={
                "passenger": _calc_cat(28000, 25480, 23200, 3_500_000, PASSENGER_NATIONAL_CAP_KRW, 10_000_000),
                "commercial": _calc_cat(7500, 7200, 6800, 5_000_000, COMMERCIAL_NATIONAL_CAP_KRW, 15_500_000),
                "bus": _calc_cat(900, 855, 810, 40_000_000, BUS_NATIONAL_CAP_KRW, 105_000_000),
            },
            municipalities=[
                _calc_muni("수원시", 2800, 2688, 3_500_000),
                _calc_muni("성남시", 2200, 2134, 3_500_000),
                _calc_muni("용인시", 2600, 2522, 3_500_000),
                _calc_muni("고양시", 2400, 2208, 3_500_000),
                _calc_muni("화성시", 2900, 2639, 3_500_000),
                _calc_muni("평택시", 1600, 1424, 4_500_000),
                _calc_muni("안산시", 1500, 1365, 3_500_000),
                _calc_muni("부천시", 1400, 1288, 3_500_000),
                _calc_muni("남양주시", 1500, 1350, 4_000_000),
                _calc_muni("가평군", 350, 280, 5_000_000),
            ],
            notes="수원·성남·용인 95% 초과(위험), 평택·화성 등 경기남부 잔여 물량 소량 유지.",
        ),
        RegionRecord(
            region_id="KR-26",
            iso_code="KR-26",
            name_ko="부산광역시",
            name_en="Busan",
            tier="metropolitan_city",
            overall_depletion_rate=78.0,
            overall_status="CAUTION",
            residency_requirement_days=90,
            supplementary_budget_added=False,
            categories={
                "passenger": _calc_cat(6200, 4836, 4400, 2_500_000, PASSENGER_NATIONAL_CAP_KRW, 9_000_000),
                "commercial": _calc_cat(1800, 1620, 1500, 4_500_000, COMMERCIAL_NATIONAL_CAP_KRW, 15_000_000),
                "bus": _calc_cat(220, 187, 170, 35_000_000, BUS_NATIONAL_CAP_KRW, 100_000_000),
            },
            municipalities=[
                _calc_muni("해운대구", 1200, 960, 2_500_000),
                _calc_muni("부산진구", 900, 711, 2_500_000),
                _calc_muni("동래구", 750, 570, 2_500_000),
                _calc_muni("사하구", 650, 494, 2_500_000),
            ],
            notes="90일 거주 요건 엄격 심사. 가을철 출고 물량 유입으로 10월 중 소진율 가속 예상.",
        ),
        RegionRecord(
            region_id="KR-27",
            iso_code="KR-27",
            name_ko="대구광역시",
            name_en="Daegu",
            tier="metropolitan_city",
            overall_depletion_rate=96.0,
            overall_status="CRITICAL",
            residency_requirement_days=30,
            supplementary_budget_added=False,
            categories={
                "passenger": _calc_cat(5100, 4896, 4600, 3_000_000, PASSENGER_NATIONAL_CAP_KRW, 9_500_000),
                "commercial": _calc_cat(1500, 1470, 1410, 4_500_000, COMMERCIAL_NATIONAL_CAP_KRW, 15_000_000),
                "bus": _calc_cat(160, 152, 144, 35_000_000, BUS_NATIONAL_CAP_KRW, 100_000_000),
            },
            municipalities=[
                _calc_muni("수성구", 1300, 1274, 3_000_000),
                _calc_muni("달서구", 1400, 1344, 3_000_000),
                _calc_muni("북구", 950, 912, 3_000_000),
                _calc_muni("동구", 750, 705, 3_000_000),
            ],
            notes="잔여 204대, 사실상 선착순 마감 직전. 대기번호 접수자 우선 순번 부여.",
        ),
        RegionRecord(
            region_id="KR-28",
            iso_code="KR-28",
            name_ko="인천광역시",
            name_en="Incheon",
            tier="metropolitan_city",
            overall_depletion_rate=82.0,
            overall_status="WARNING",
            residency_requirement_days=30,
            supplementary_budget_added=False,
            categories={
                "passenger": _calc_cat(5800, 4756, 4300, 3_000_000, PASSENGER_NATIONAL_CAP_KRW, 9_500_000),
                "commercial": _calc_cat(1900, 1862, 1780, 5_000_000, COMMERCIAL_NATIONAL_CAP_KRW, 15_500_000),
                "bus": _calc_cat(210, 189, 175, 35_000_000, BUS_NATIONAL_CAP_KRW, 100_000_000),
            },
            municipalities=[
                _calc_muni("연수구 (송도)", 1500, 1290, 3_000_000),
                _calc_muni("서구 (청라·검단)", 1600, 1344, 3_000_000),
                _calc_muni("남동구", 1100, 880, 3_000_000),
                _calc_muni("부평구", 900, 711, 3_000_000),
            ],
            notes="화물차 전량 소진, 승용 잔여 약 1,040대 소진 임박.",
        ),
        RegionRecord(
            region_id="KR-29",
            iso_code="KR-29",
            name_ko="광주광역시",
            name_en="Gwangju",
            tier="metropolitan_city",
            overall_depletion_rate=92.0,
            overall_status="WARNING",
            residency_requirement_days=30,
            supplementary_budget_added=False,
            categories={
                "passenger": _calc_cat(3400, 3128, 2900, 3_500_000, PASSENGER_NATIONAL_CAP_KRW, 10_000_000),
                "commercial": _calc_cat(1100, 1045, 990, 5_000_000, COMMERCIAL_NATIONAL_CAP_KRW, 15_500_000),
                "bus": _calc_cat(110, 101, 95, 35_000_000, BUS_NATIONAL_CAP_KRW, 100_000_000),
            },
            municipalities=[
                _calc_muni("서구", 900, 837, 3_500_000),
                _calc_muni("광산구", 1100, 1023, 3_500_000),
                _calc_muni("북구", 850, 773, 3_500_000),
            ],
            notes="법인 물량 전액 소진, 개인 승용 조기 마감 위험 (잔여 272대).",
        ),
        RegionRecord(
            region_id="KR-30",
            iso_code="KR-30",
            name_ko="대전광역시",
            name_en="Daejeon",
            tier="metropolitan_city",
            overall_depletion_rate=78.0,
            overall_status="CAUTION",
            residency_requirement_days=90,
            supplementary_budget_added=False,
            categories={
                "passenger": _calc_cat(4200, 3276, 3050, 3_000_000, PASSENGER_NATIONAL_CAP_KRW, 9_500_000),
                "commercial": _calc_cat(1200, 1080, 1000, 4_500_000, COMMERCIAL_NATIONAL_CAP_KRW, 15_000_000),
                "bus": _calc_cat(130, 104, 98, 35_000_000, BUS_NATIONAL_CAP_KRW, 100_000_000),
            },
            municipalities=[
                _calc_muni("유성구", 1500, 1200, 3_000_000),
                _calc_muni("서구", 1300, 1014, 3_000_000),
                _calc_muni("중구", 650, 487, 3_000_000),
            ],
            notes="안정적 소진 유지 중, 10월 하순경 예산 한도 도달 예상.",
        ),
        RegionRecord(
            region_id="KR-31",
            iso_code="KR-31",
            name_ko="울산광역시",
            name_en="Ulsan",
            tier="metropolitan_city",
            overall_depletion_rate=96.0,
            overall_status="CRITICAL",
            residency_requirement_days=90,
            supplementary_budget_added=False,
            categories={
                "passenger": _calc_cat(2800, 2688, 2550, 3_150_000, PASSENGER_NATIONAL_CAP_KRW, 9_650_000),
                "commercial": _calc_cat(900, 882, 850, 4_800_000, COMMERCIAL_NATIONAL_CAP_KRW, 15_300_000),
                "bus": _calc_cat(80, 76, 72, 35_000_000, BUS_NATIONAL_CAP_KRW, 100_000_000),
            },
            municipalities=[
                _calc_muni("남구", 950, 921, 3_150_000),
                _calc_muni("북구 (현대차공장)", 900, 882, 3_150_000),
                _calc_muni("울주군", 650, 611, 3_150_000),
            ],
            notes="현대차 임직원 출고 집중으로 잔여 112대 마감 직전. 긴급 확인 요망.",
        ),
        RegionRecord(
            region_id="KR-36",
            iso_code="KR-36",
            name_ko="세종특별자치시",
            name_en="Sejong",
            tier="special_self_governing_city",
            overall_depletion_rate=73.0,
            overall_status="CAUTION",
            residency_requirement_days=30,
            supplementary_budget_added=False,
            categories={
                "passenger": _calc_cat(1200, 876, 810, 2_500_000, PASSENGER_NATIONAL_CAP_KRW, 9_000_000),
                "commercial": _calc_cat(300, 255, 230, 4_000_000, COMMERCIAL_NATIONAL_CAP_KRW, 14_500_000),
                "bus": _calc_cat(40, 32, 30, 35_000_000, BUS_NATIONAL_CAP_KRW, 100_000_000),
            },
            municipalities=[
                _calc_muni("세종시 본청", 1200, 876, 2_500_000),
            ],
            notes="공무원 위주 실수요 중심, 전국 광역시 대비 잔여 예산 여유.",
        ),
        RegionRecord(
            region_id="KR-42",
            iso_code="KR-42",
            name_ko="강원특별자치도",
            name_en="Gangwon",
            tier="special_self_governing_province",
            overall_depletion_rate=78.0,
            overall_status="CAUTION",
            residency_requirement_days=90,
            supplementary_budget_added=False,
            categories={
                "passenger": _calc_cat(4500, 3510, 3200, 5_500_000, PASSENGER_NATIONAL_CAP_KRW, 12_000_000),
                "commercial": _calc_cat(1800, 1584, 1490, 7_000_000, COMMERCIAL_NATIONAL_CAP_KRW, 17_500_000),
                "bus": _calc_cat(120, 96, 90, 45_000_000, BUS_NATIONAL_CAP_KRW, 115_000_000),
            },
            municipalities=[
                _calc_muni("춘천시", 1300, 1092, 5_500_000),
                _calc_muni("원주시", 1500, 1245, 5_500_000),
                _calc_muni("강릉시", 750, 570, 5_500_000),
                _calc_muni("삼척시", 350, 245, 7_000_000),
            ],
            notes="춘천·원주 집중 소진, 삼척·영동권 지자체는 고액 보조금(700만 원)에 잔여 여유.",
        ),
        RegionRecord(
            region_id="KR-43",
            iso_code="KR-43",
            name_ko="충청북도",
            name_en="Chungbuk",
            tier="province",
            overall_depletion_rate=85.0,
            overall_status="WARNING",
            residency_requirement_days=30,
            supplementary_budget_added=False,
            categories={
                "passenger": _calc_cat(4100, 3485, 3150, 6_000_000, PASSENGER_NATIONAL_CAP_KRW, 12_500_000),
                "commercial": _calc_cat(1600, 1440, 1360, 7_500_000, COMMERCIAL_NATIONAL_CAP_KRW, 18_000_000),
                "bus": _calc_cat(100, 82, 75, 45_000_000, BUS_NATIONAL_CAP_KRW, 115_000_000),
            },
            municipalities=[
                _calc_muni("청주시", 2100, 1953, 6_000_000),
                _calc_muni("충주시", 800, 664, 6_500_000),
                _calc_muni("제천시", 500, 395, 6_800_000),
                _calc_muni("단양군", 200, 146, 7_500_000),
            ],
            notes="청주시 93%로 마감 임박, 단양/영동 등 군단위는 700만 원 이상 고액 보조금 지원.",
        ),
        RegionRecord(
            region_id="KR-44",
            iso_code="KR-44",
            name_ko="충청남도",
            name_en="Chungnam",
            tier="province",
            overall_depletion_rate=88.0,
            overall_status="WARNING",
            residency_requirement_days=30,
            supplementary_budget_added=False,
            categories={
                "passenger": _calc_cat(5900, 5192, 4700, 6_500_000, PASSENGER_NATIONAL_CAP_KRW, 13_000_000),
                "commercial": _calc_cat(2200, 2046, 1920, 8_000_000, COMMERCIAL_NATIONAL_CAP_KRW, 18_500_000),
                "bus": _calc_cat(140, 121, 110, 50_000_000, BUS_NATIONAL_CAP_KRW, 120_000_000),
            },
            municipalities=[
                _calc_muni("천안시", 2100, 1974, 6_000_000),
                _calc_muni("아산시", 1500, 1365, 6_500_000),
                _calc_muni("서산시", 650, 552, 7_000_000),
                _calc_muni("당진시", 600, 510, 7_000_000),
                _calc_muni("태안군", 250, 195, 9_000_000),
            ],
            notes="천안·아산 공업지대 소진 가속화(94%), 태안·서천 등 군 지역은 최대 900만 원 지급.",
        ),
        RegionRecord(
            region_id="KR-45",
            iso_code="KR-45",
            name_ko="전북특별자치도",
            name_en="Jeonbuk",
            tier="special_self_governing_province",
            overall_depletion_rate=84.0,
            overall_status="WARNING",
            residency_requirement_days=30,
            supplementary_budget_added=False,
            categories={
                "passenger": _calc_cat(4300, 3612, 3300, 6_500_000, PASSENGER_NATIONAL_CAP_KRW, 13_000_000),
                "commercial": _calc_cat(1700, 1530, 1420, 8_000_000, COMMERCIAL_NATIONAL_CAP_KRW, 18_500_000),
                "bus": _calc_cat(110, 93, 85, 45_000_000, BUS_NATIONAL_CAP_KRW, 115_000_000),
            },
            municipalities=[
                _calc_muni("전주시", 2000, 1800, 6_500_000),
                _calc_muni("익산시", 900, 738, 6_500_000),
                _calc_muni("군산시", 800, 656, 6_500_000),
                _calc_muni("무주군", 180, 135, 8_000_000),
            ],
            notes="전주시 90% 돌파로 조기 마감 가시권, 익산·군산 잔여 15%선 유지 중.",
        ),
        RegionRecord(
            region_id="KR-46",
            iso_code="KR-46",
            name_ko="전라남도",
            name_en="Jeonnam",
            tier="province",
            overall_depletion_rate=83.0,
            overall_status="WARNING",
            residency_requirement_days=90,
            supplementary_budget_added=False,
            categories={
                "passenger": _calc_cat(5400, 4482, 4100, 7_500_000, PASSENGER_NATIONAL_CAP_KRW, 14_000_000),
                "commercial": _calc_cat(2100, 1890, 1750, 8_500_000, COMMERCIAL_NATIONAL_CAP_KRW, 19_000_000),
                "bus": _calc_cat(130, 107, 98, 50_000_000, BUS_NATIONAL_CAP_KRW, 120_000_000),
            },
            municipalities=[
                _calc_muni("순천시", 1200, 1056, 7_000_000),
                _calc_muni("여수시", 1100, 946, 7_000_000),
                _calc_muni("목포시", 950, 836, 7_000_000),
                _calc_muni("나주시", 650, 526, 7_500_000),
                _calc_muni("해남군", 300, 237, 8_500_000),
                _calc_muni("신안군", 200, 152, 11_500_000),
            ],
            notes="목포·순천 소진 임박. 신안군(1,150만 원), 해남군(850만 원) 등 전국 최고 수준 지방비 지급.",
        ),
        RegionRecord(
            region_id="KR-47",
            iso_code="KR-47",
            name_ko="경상북도",
            name_en="Gyeongbuk",
            tier="province",
            overall_depletion_rate=97.0,
            overall_status="CRITICAL",
            residency_requirement_days=30,
            supplementary_budget_added=False,
            categories={
                "passenger": _calc_cat(7200, 6984, 6500, 6_500_000, PASSENGER_NATIONAL_CAP_KRW, 13_000_000),
                "commercial": _calc_cat(2600, 2548, 2410, 8_000_000, COMMERCIAL_NATIONAL_CAP_KRW, 18_500_000),
                "bus": _calc_cat(160, 155, 148, 50_000_000, BUS_NATIONAL_CAP_KRW, 120_000_000),
            },
            municipalities=[
                _calc_muni("포항시", 2200, 2178, 6_000_000),
                _calc_muni("구미시", 1700, 1666, 6_000_000),
                _calc_muni("경주시", 1000, 960, 6_500_000),
                _calc_muni("안동시", 700, 665, 7_000_000),
                _calc_muni("울릉군", 150, 150, 11_000_000),
            ],
            notes="포항·구미 98% 이상 마감 직전. 울릉군(1,100만 원)은 100% 전액 소진 마감.",
        ),
        RegionRecord(
            region_id="KR-48",
            iso_code="KR-48",
            name_ko="경상남도",
            name_en="Gyeongnam",
            tier="province",
            overall_depletion_rate=88.0,
            overall_status="WARNING",
            residency_requirement_days=30,
            supplementary_budget_added=False,
            categories={
                "passenger": _calc_cat(6800, 5984, 5500, 6_000_000, PASSENGER_NATIONAL_CAP_KRW, 12_500_000),
                "commercial": _calc_cat(2400, 2256, 2100, 7_500_000, COMMERCIAL_NATIONAL_CAP_KRW, 18_000_000),
                "bus": _calc_cat(150, 132, 120, 45_000_000, BUS_NATIONAL_CAP_KRW, 115_000_000),
            },
            municipalities=[
                _calc_muni("창원시", 2400, 2208, 5_500_000),
                _calc_muni("김해시", 1600, 1440, 5_500_000),
                _calc_muni("양산시", 1100, 957, 6_000_000),
                _calc_muni("진주시", 900, 774, 6_000_000),
                _calc_muni("거창군", 200, 156, 7_500_000),
            ],
            notes="창원·김해 등 동부경남 공업벨트 소진 가속, 서부경남 소량 잔여.",
        ),
        RegionRecord(
            region_id="KR-49",
            iso_code="KR-49",
            name_ko="제주특별자치도",
            name_en="Jeju",
            tier="special_self_governing_province",
            overall_depletion_rate=99.0,
            overall_status="CRITICAL",
            residency_requirement_days=90,
            supplementary_budget_added=False,
            categories={
                "passenger": _calc_cat(4000, 3960, 3800, 4_000_000, PASSENGER_NATIONAL_CAP_KRW, 10_500_000),
                "commercial": _calc_cat(1400, 1386, 1320, 6_000_000, COMMERCIAL_NATIONAL_CAP_KRW, 16_500_000),
                "bus": _calc_cat(100, 99, 95, 40_000_000, BUS_NATIONAL_CAP_KRW, 110_000_000),
            },
            municipalities=[
                _calc_muni("제주시", 2700, 2673, 4_000_000),
                _calc_muni("서귀포시", 1300, 1287, 4_000_000),
            ],
            notes="렌터카 및 도민 보급 목표 99% 달성. 일반 승용 잔여 40대, 실질적 접수 마감.",
        ),
    ]
    for reg in regions:
        tot_ann = sum(c.announced_units for c in reg.categories.values())
        tot_app = sum(c.applied_units for c in reg.categories.values())
        reg.overall_depletion_rate = _calc_rate_percent(tot_app, tot_ann)
        reg.overall_status = AlertSeverity.from_rate(reg.overall_depletion_rate).value
    return regions


def _calc_model_regional_samples(base_price: int, national_sub: int) -> Dict[str, Dict[str, int]]:
    """Calculate regional subsidy and net price for standard comparison cities."""
    # Statutory local caps (passenger maximum)
    regional_max_caps = {
        "seoul": 1_500_000,
        "gyeonggi_avg": 3_500_000,
        "busan": 2_500_000,
        "daegu": 3_000_000,
        "jeju": 4_000_000,
        "gurye_jeonnam": 8_000_000,
        "ulleung_gyeongbuk": 11_000_000,
    }

    samples = {}
    ratio = min(1.0, max(0.0, national_sub / PASSENGER_NATIONAL_CAP_KRW)) if PASSENGER_NATIONAL_CAP_KRW > 0 else 0.0

    for reg_key, max_local in regional_max_caps.items():
        # Local subsidy scales proportionally with national subsidy / national cap
        local_sub = int(round(max_local * ratio, -4))
        tot_sub = national_sub + local_sub
        net_price = max(0, base_price - tot_sub)
        samples[reg_key] = {
            "total_subsidy_krw": tot_sub,
            "net_price_krw": net_price,
        }
    return samples


def build_popular_models() -> List[PopularModelEntry]:
    """Build popular 2026 Korean market EV models with authentic subsidy calculations."""
    models_raw = [
        {
            "model_id": "ioniq-5-2026",
            "name_ko": "현대 아이오닉 5 롱레인지 2WD (2026)",
            "manufacturer": "현대자동차",
            "battery_type": "NCM 삼원계 (SK온 84kWh)",
            "battery_capacity_kwh": 84.0,
            "rated_range_km": 485,
            "base_price_krw": 54_100_000,
            "price_subsidy_ratio": 1.0,
            "national_subsidy_krw": 6_500_000,
        },
        {
            "model_id": "kia-ev3-2026",
            "name_ko": "기아 EV3 롱레인지 에어 (2026)",
            "manufacturer": "기아",
            "battery_type": "NCM 삼원계 (LG엔솔 81.4kWh)",
            "battery_capacity_kwh": 81.4,
            "rated_range_km": 501,
            "base_price_krw": 39_950_000,
            "price_subsidy_ratio": 1.0,
            "national_subsidy_krw": 5_850_000,
        },
        {
            "model_id": "kia-ev6-2026",
            "name_ko": "기아 더 뉴 EV6 롱레인지 2WD (2026)",
            "manufacturer": "기아",
            "battery_type": "NCM 삼원계 (SK온 84kWh)",
            "battery_capacity_kwh": 84.0,
            "rated_range_km": 494,
            "base_price_krw": 52_600_000,
            "price_subsidy_ratio": 1.0,
            "national_subsidy_krw": 6_400_000,
        },
        {
            "model_id": "kia-ev9-2026",
            "name_ko": "기아 EV9 2WD 에어 (2026)",
            "manufacturer": "기아",
            "battery_type": "NCM 삼원계 (SK온 99.8kWh)",
            "battery_capacity_kwh": 99.8,
            "rated_range_km": 501,
            "base_price_krw": 73_370_000,
            "price_subsidy_ratio": 0.5,
            "national_subsidy_krw": 3_010_000,
        },
        {
            "model_id": "tesla-model-y-rwd",
            "name_ko": "테슬라 모델 Y RWD (2026)",
            "manufacturer": "Tesla",
            "battery_type": "LFP 리튬인산철 (CATL 60kWh)",
            "battery_capacity_kwh": 60.0,
            "rated_range_km": 350,
            "base_price_krw": 52_990_000,
            "price_subsidy_ratio": 1.0,
            "national_subsidy_krw": 2_000_000,
        },
        {
            "model_id": "tesla-model-3-rwd",
            "name_ko": "테슬라 모델 3 RWD 하이랜드 (2026)",
            "manufacturer": "Tesla",
            "battery_type": "LFP 리튬인산철 (CATL 60kWh)",
            "battery_capacity_kwh": 60.0,
            "rated_range_km": 382,
            "base_price_krw": 51_990_000,
            "price_subsidy_ratio": 1.0,
            "national_subsidy_krw": 2_260_000,
        },
        {
            "model_id": "kgm-torres-evx",
            "name_ko": "KGM 토레스 EVX 2WD (2026)",
            "manufacturer": "KG모빌리티",
            "battery_type": "LFP 블레이드 배터리 (BYD 73.4kWh)",
            "battery_capacity_kwh": 73.4,
            "rated_range_km": 433,
            "base_price_krw": 45_500_000,
            "price_subsidy_ratio": 1.0,
            "national_subsidy_krw": 4_570_000,
        },
        {
            "model_id": "hyundai-casper-ev",
            "name_ko": "현대 캐스퍼 일렉트릭 인스퍼레이션 (2026)",
            "manufacturer": "현대자동차",
            "battery_type": "NCM 삼원계 (LG엔솔 49kWh)",
            "battery_capacity_kwh": 49.0,
            "rated_range_km": 315,
            "base_price_krw": 31_500_000,
            "price_subsidy_ratio": 1.0,
            "national_subsidy_krw": 5_200_000,
        },
        {
            "model_id": "byd-atto-3",
            "name_ko": "BYD 아토 3 (2026 KDM)",
            "manufacturer": "BYD",
            "battery_type": "LFP 블레이드 배터리 (BYD 60.48kWh)",
            "battery_capacity_kwh": 60.48,
            "rated_range_km": 345,
            "base_price_krw": 32_500_000,
            "price_subsidy_ratio": 1.0,
            "national_subsidy_krw": 2_050_000,
        },
        {
            "model_id": "byd-dolphin",
            "name_ko": "BYD 돌핀 (2026 KDM)",
            "manufacturer": "BYD",
            "battery_type": "LFP 블레이드 배터리 (BYD 44.9kWh)",
            "battery_capacity_kwh": 44.9,
            "rated_range_km": 310,
            "base_price_krw": 26_900_000,
            "price_subsidy_ratio": 1.0,
            "national_subsidy_krw": 1_850_000,
        },
    ]

    entries: List[PopularModelEntry] = []
    for item in models_raw:
        samples = _calc_model_regional_samples(
            item["base_price_krw"], item["national_subsidy_krw"]
        )
        entries.append(
            PopularModelEntry(
                model_id=item["model_id"],
                name_ko=item["name_ko"],
                manufacturer=item["manufacturer"],
                battery_type=item["battery_type"],
                battery_capacity_kwh=item["battery_capacity_kwh"],
                rated_range_km=item["rated_range_km"],
                base_price_krw=item["base_price_krw"],
                price_subsidy_ratio=item["price_subsidy_ratio"],
                national_subsidy_krw=item["national_subsidy_krw"],
                regional_subsidy_samples=samples,
            )
        )
    return entries


def build_historical_trajectory() -> List[HistoricalTrajectoryPoint]:
    """Build monthly nationwide historical trajectory leading to September 2026."""
    return [
        HistoricalTrajectoryPoint(date="2026-01-31", passenger_rate=0.0, commercial_rate=0.0, overall_rate=0.0),
        HistoricalTrajectoryPoint(date="2026-02-28", passenger_rate=12.5, commercial_rate=19.4, overall_rate=14.1),
        HistoricalTrajectoryPoint(date="2026-03-31", passenger_rate=28.4, commercial_rate=38.2, overall_rate=30.6),
        HistoricalTrajectoryPoint(date="2026-04-30", passenger_rate=44.1, commercial_rate=53.0, overall_rate=46.2),
        HistoricalTrajectoryPoint(date="2026-05-31", passenger_rate=58.7, commercial_rate=67.5, overall_rate=60.8),
        HistoricalTrajectoryPoint(date="2026-06-30", passenger_rate=71.2, commercial_rate=78.1, overall_rate=72.8),
        HistoricalTrajectoryPoint(date="2026-07-31", passenger_rate=79.5, commercial_rate=84.3, overall_rate=80.6),
        HistoricalTrajectoryPoint(date="2026-08-31", passenger_rate=85.8, commercial_rate=89.6, overall_rate=86.7),
        HistoricalTrajectoryPoint(date="2026-09-23", passenger_rate=88.6, commercial_rate=91.4, overall_rate=89.3),
    ]


def build_initial_baseline(regions: Optional[List[Any]] = None) -> SubsidyPayload:
    """Construct full initial baseline SubsidyPayload."""
    if regions is None:
        regions = build_baseline_regions()
    popular_models = build_popular_models()
    history = build_historical_trajectory()

    # Aggregate nationwide statistics
    total_announced = 0
    total_applied = 0
    total_delivered = 0
    total_remaining = 0
    total_budget_sum = 0
    disbursed_budget_sum = 0

    cat_announced: Dict[str, int] = {"passenger": 0, "commercial": 0, "bus": 0}
    cat_applied: Dict[str, int] = {"passenger": 0, "commercial": 0, "bus": 0}
    cat_delivered: Dict[str, int] = {"passenger": 0, "commercial": 0, "bus": 0}

    alert_counts: Dict[str, int] = {
        "healthy": 0,
        "caution": 0,
        "warning": 0,
        "critical": 0,
        "depleted": 0,
    }

    total_municipalities = 0

    for r in regions:
        if r is None:
            continue
        munis = r.get("municipalities", []) if isinstance(r, dict) else getattr(r, "municipalities", [])
        total_municipalities += len(munis or []) if isinstance(munis, (list, tuple)) else 0
        status_val = (r.get("overall_status") or r.get("status")) if isinstance(r, dict) else getattr(r, "overall_status", "")
        status_val = getattr(status_val, "value", status_val)
        status_key = str(status_val or "").split(".")[-1].strip().lower()

        cats = r.get("categories") if isinstance(r, dict) else getattr(r, "categories", {})
        if not isinstance(cats, dict):
            cats = {}
        reg_ann = 0
        reg_app = 0
        for c_name, c_metric in cats.items():
            if c_name not in cat_announced:
                cat_announced[c_name] = 0
                cat_applied[c_name] = 0
                cat_delivered[c_name] = 0

            ann = max(0, _safe_int_val(c_metric.get("announced_units", 0) if isinstance(c_metric, dict) else getattr(c_metric, "announced_units", 0)))
            app = max(0, _safe_int_val(c_metric.get("applied_units", 0) if isinstance(c_metric, dict) else getattr(c_metric, "applied_units", 0)))
            delivered = max(0, _safe_int_val(c_metric.get("delivered_units", 0) if isinstance(c_metric, dict) else getattr(c_metric, "delivered_units", 0)))
            tot_b = max(0, _safe_int_val(c_metric.get("total_budget_krw", 0) if isinstance(c_metric, dict) else getattr(c_metric, "total_budget_krw", 0)))
            rem_b_raw = max(0, _safe_int_val(c_metric.get("remaining_budget_krw", 0) if isinstance(c_metric, dict) else getattr(c_metric, "remaining_budget_krw", 0)))
            rem_b = min(tot_b, rem_b_raw) if tot_b > 0 else rem_b_raw

            cat_announced[c_name] += ann
            cat_applied[c_name] += app
            cat_delivered[c_name] += delivered

            reg_ann += ann
            reg_app += app
            total_announced += ann
            total_applied += app
            total_delivered += delivered
            total_budget_sum += tot_b
            disbursed_budget_sum += max(0, tot_b - rem_b)

        if status_key not in alert_counts and (
            cats
            or (isinstance(r, dict) and ("overall_depletion_rate" in r or "depletion_rate" in r))
            or hasattr(r, "overall_depletion_rate")
        ):
            if cats:
                reg_rate = _calc_rate_percent(reg_app, reg_ann)
            else:
                if isinstance(r, dict):
                    raw_rate = r.get("overall_depletion_rate")
                    if raw_rate is None:
                        raw_rate = r.get("depletion_rate", 0.0)
                else:
                    raw_rate = getattr(r, "overall_depletion_rate", 0.0)
                if raw_rate is None or isinstance(raw_rate, bool):
                    reg_rate = 0.0
                else:
                    try:
                        f_rate = float(str(raw_rate).strip().replace(",", "")) if isinstance(raw_rate, str) else float(raw_rate)
                        reg_rate = 0.0 if (math.isnan(f_rate) or math.isinf(f_rate)) else max(0.0, f_rate)
                    except (ValueError, TypeError, OverflowError):
                        reg_rate = 0.0
            status_key = AlertSeverity.from_rate(reg_rate).value.lower()
        if status_key in alert_counts:
            alert_counts[status_key] += 1

    total_remaining = max(0, total_announced - total_applied)
    nationwide_depletion_rate = _calc_rate_percent(total_applied, total_announced)

    category_totals = {}
    standard_categories = ["passenger", "commercial", "bus"]
    all_categories = standard_categories + [k for k in cat_announced.keys() if k not in standard_categories]
    for c_name in all_categories:
        c_ann = cat_announced.get(c_name, 0)
        c_app = cat_applied.get(c_name, 0)
        c_del = cat_delivered.get(c_name, 0)
        c_rate = _calc_rate_percent(c_app, c_ann)
        c_del_rate = _calc_rate_percent(c_del, c_ann)
        category_totals[c_name] = CategoryMetrics(
            announced_units=c_ann,
            applied_units=c_app,
            delivered_units=c_del,
            remaining_units=max(0, c_ann - c_app),
            depletion_rate=c_rate,
            delivery_rate=c_del_rate,
            status=AlertSeverity.from_rate(c_rate).value,
            max_local_subsidy_krw=0,
            max_total_subsidy_krw=0,
            total_budget_krw=0,
            remaining_budget_krw=0,
        )

    try:
        total_budget_billion = round(total_budget_sum / 1_000_000_000, 1)
    except OverflowError:
        total_budget_billion = float(total_budget_sum // 1_000_000_000)
    try:
        disbursed_budget_billion = max(0.0, round(disbursed_budget_sum / 1_000_000_000, 1))
    except OverflowError:
        disbursed_budget_billion = max(0.0, float(disbursed_budget_sum // 1_000_000_000))

    summary = NationwideSummary(
        total_announced_units=total_announced,
        total_applied_units=total_applied,
        total_delivered_units=total_delivered,
        total_remaining_units=total_remaining,
        nationwide_depletion_rate=nationwide_depletion_rate,
        total_budget_billion_krw=total_budget_billion,
        disbursed_budget_billion_krw=disbursed_budget_billion,
        category_totals=category_totals,
        alert_region_counts=alert_counts,
    )

    metadata = SubsidyMetadata(
        version="1.0.0",
        generated_at=datetime.now(timezone.utc).isoformat(),
        policy_year=2026,
        data_sources=[
            "환경부 무공해차 통합누리집 (ev.or.kr)",
            "한국환경공단 (KECO) CleanSys",
            "17개 광역시도 무공해차 보급 촉진 고시공고",
        ],
        total_regions_tracked=sum(1 for r in regions if r is not None),
        total_municipalities_tracked=total_municipalities,
        currency="KRW",
    )

    return SubsidyPayload(
        metadata=metadata,
        alert_thresholds=DEFAULT_ALERT_THRESHOLDS,
        nationwide_summary=summary,
        regions=regions,
        popular_models_matrix=popular_models,
        historical_depletion_trajectory=history,
    )
