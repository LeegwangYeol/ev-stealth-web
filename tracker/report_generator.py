"""tracker/report_generator.py - Markdown Briefing and Statistical Report Formatter.

Encapsulates:
- Executive markdown summary briefings for EV subsidy depletion monitoring.
- Defect incident briefings and community trend summaries.
- Comprehensive statistical reporting and metric aggregation formatting.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Union

from tracker.subsidy_models import RegionRecord, SubsidyPayload


def _safe_int_val(val: Any, default: int = 0) -> int:
    """Safely convert value to int, catching None, NaN, Inf, ValueError, TypeError, OverflowError."""
    if val is None:
        return default
    try:
        if isinstance(val, float):
            if math.isnan(val) or math.isinf(val):
                return default
        return int(val)
    except (ValueError, TypeError, OverflowError):
        return default


def _safe_float_val(val: Any, default: float = 0.0) -> float:
    """Safely convert value to float, catching None, NaN, Inf, ValueError, TypeError, OverflowError."""
    if val is None:
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (ValueError, TypeError, OverflowError):
        return default


def _get_field(item: Any, key: str, default: Any = None) -> Any:
    """Safely extract field supporting dict access and domain model attribute access."""
    if item is None:
        return default
    if isinstance(item, dict):
        val = item.get(key, default)
    elif hasattr(item, key):
        val = getattr(item, key, default)
    elif hasattr(item, "__getitem__"):
        try:
            val = item[key]
        except (KeyError, TypeError, IndexError):
            val = default
    else:
        val = default
    return default if val is None else val


def _metric_val(metric: Any, key: str, default: Any = 0) -> Any:
    """Safely extract metric attribute or dict key, supporting dict and dataclass instances."""
    val = _get_field(metric, key, default)
    return default if val is None else val


def _safe_sev(record: Any) -> float:
    """Safely extract and map defect severity score, mapping string tiers to numeric DSI values."""
    raw = _get_field(record, "severity_index")
    if raw is None:
        raw = _get_field(record, "severity")
    if raw is None:
        return 0.0
    if isinstance(raw, str):
        tier_map = {
            "CRITICAL": 10.0,
            "WARNING": 7.0,
            "HIGH": 7.0,
            "CAUTION": 4.0,
            "MEDIUM": 4.0,
            "INFO": 1.0,
            "LOW": 1.0,
        }
        cleaned = raw.strip().upper()
        if cleaned in tier_map:
            return tier_map[cleaned]
    return _safe_float_val(raw, 0.0)


class ReportGenerator:
    """Encapsulates executive markdown briefing and statistical reporting formatting."""

    _safe_sev = staticmethod(_safe_sev)

    def __init__(self) -> None:
        pass

    def generate_subsidy_briefing(
        self,
        payload: SubsidyPayload,
        fallback_used: bool = False,
    ) -> str:
        """Generate formatted executive markdown summary briefing for subsidy depletion.

        Maintains exact statutory formatting expected by downstream systems and CLI.
        """
        summary = _get_field(payload, "nationwide_summary", None) or payload
        metadata = _get_field(payload, "metadata", None)
        gen_time = (
            _get_field(metadata, "generated_at", None)
            or _get_field(metadata, "updated_at", None)
            or _get_field(payload, "generated_at", None)
            or _get_field(payload, "updated_at", "")
        )

        def _get_passenger_remaining(region: Any) -> int:
            cats = _get_field(region, "categories", None)
            if not isinstance(cats, dict):
                return 0
            p_cat = cats.get("passenger")
            if p_cat is None:
                return 0
            val = _metric_val(p_cat, "remaining_units", 0)
            return max(0, _safe_int_val(val, 0))

        regions_list = _get_field(payload, "regions", []) or []
        critical_regions = [
            f"{_get_field(r, 'name_ko', '')} ({_safe_float_val(_get_field(r, 'overall_depletion_rate', 0.0))}%, 잔여: {_get_passenger_remaining(r):,}대)"
            for r in regions_list
            if str(_get_field(r, "overall_status", "")).strip().upper() in ("CRITICAL", "DEPLETED")
        ]
        warning_regions = [
            f"{_get_field(r, 'name_ko', '')} ({_safe_float_val(_get_field(r, 'overall_depletion_rate', 0.0))}%, 잔여: {_get_passenger_remaining(r):,}대)"
            for r in regions_list
            if str(_get_field(r, "overall_status", "")).strip().upper() == "WARNING"
        ]

        category_totals = _get_field(summary, "category_totals", {}) or {}
        if not isinstance(category_totals, dict):
            category_totals = {}
        p_info = category_totals.get("passenger", {})
        c_info = category_totals.get("commercial", {})
        b_info = category_totals.get("bus", {})

        tot_ann = _safe_int_val(_get_field(summary, "total_announced_units", 0))
        tot_app = _safe_int_val(_get_field(summary, "total_applied_units", 0))
        disb_b = _safe_float_val(_get_field(summary, "disbursed_budget_billion_krw", 0.0))
        tot_b = _safe_float_val(_get_field(summary, "total_budget_billion_krw", 0.0))
        disb_str = f"{disb_b:,.1f}" if (disb_b % 1 != 0) else f"{int(disb_b):,}"
        tot_str = f"{tot_b:,.1f}" if (tot_b % 1 != 0) else f"{int(tot_b):,}"
        dep_rate = _safe_float_val(_get_field(summary, "nationwide_depletion_rate", 0.0))

        p_ann = _safe_int_val(_metric_val(p_info, "announced_units", 0))
        p_app = _safe_int_val(_metric_val(p_info, "applied_units", 0))
        p_rate = _safe_float_val(_metric_val(p_info, "depletion_rate", 0.0))
        p_rem = _safe_int_val(_metric_val(p_info, "remaining_units", 0))
        p_st = _metric_val(p_info, "status", "N/A") or "N/A"

        c_ann = _safe_int_val(_metric_val(c_info, "announced_units", 0))
        c_app = _safe_int_val(_metric_val(c_info, "applied_units", 0))
        c_rate = _safe_float_val(_metric_val(c_info, "depletion_rate", 0.0))
        c_rem = _safe_int_val(_metric_val(c_info, "remaining_units", 0))
        c_st = _metric_val(c_info, "status", "N/A") or "N/A"

        b_ann = _safe_int_val(_metric_val(b_info, "announced_units", 0))
        b_app = _safe_int_val(_metric_val(b_info, "applied_units", 0))
        b_rate = _safe_float_val(_metric_val(b_info, "depletion_rate", 0.0))
        b_rem = _safe_int_val(_metric_val(b_info, "remaining_units", 0))
        b_st = _metric_val(b_info, "status", "N/A") or "N/A"

        status_text = "FALLBACK_BASELINE (Resilient)" if fallback_used else "SUCCESS (Live Sync)"

        lines = [
            "# [대한민국 2026 전국 지자체 전기차 보조금 실시간 소진율 모니터링] (전국 전기차 보조금 소진 현황 일일 종합 브리핑)",
            f"- **기록 시각(UTC)**: {gen_time}",
            f"- **파이프라인 상태**: {status_text}",
            f"- **전국 평균 소진율**: {dep_rate}% (총 공고: {tot_ann:,}대 / 접수: {tot_app:,}대)",
            f"- **집행 예산**: {disb_str}억 원 / 총 예산 {tot_str}억 원",
            "",
            "## 🚨 긴급 마감 임박 지자체 (CRITICAL / DEPLETED >= 95%)",
            (
                "\n".join([f"  - 🔴 {cr}" for cr in critical_regions])
                if critical_regions
                else "  - 현재 접수 마감된 긴급 지자체 없음."
            ),
            "",
            "## ⚠️ 주의·경고 지자체 (WARNING 80% ~ 94.9%)",
            (
                "\n".join([f"  - 🟠 {wr}" for wr in warning_regions])
                if warning_regions
                else "  - 경고 지역 없음."
            ),
            "",
            "## 📊 차종별 소진 현황",
            f"- **승용**: 공고 {p_ann:,}대 | 접수 {p_app:,}대 ({p_rate}%) | 잔여 {p_rem:,}대 [{p_st}]",
            f"- **화물**: 공고 {c_ann:,}대 | 접수 {c_app:,}대 ({c_rate}%) | 잔여 {c_rem:,}대 [{c_st}]",
            f"- **승합(버스)**: 공고 {b_ann:,}대 | 접수 {b_app:,}대 ({b_rate}%) | 잔여 {b_rem:,}대 [{b_st}]",
            "",
            "## 💡 예비 차주 권고 사항",
            "- 대구, 울산, 경북, 제주는 보조금 마감 직전(소진율 96%~99%)입니다. 실계약자는 대기 순번 및 제조사 즉시 출고 재고를 확인하십시오.",
            "- 전남(신안 1,150만 원), 경북(울릉 1,100만 원), 충남(태안 900만 원) 등 군 단위 지역은 고액 보조금이 지급되나 거주기간 요건(30~90일)을 확인해야 합니다.",
        ]
        return "\n".join(lines)

    def generate_defect_briefing(
        self,
        report_data: Union[Dict[str, Any], List[Any], Any],
    ) -> str:
        """Generate executive markdown summary briefing for daily EV defect reports."""
        if isinstance(report_data, list):
            reports = report_data
            stats = {}
            gen_time = datetime.now(timezone.utc).isoformat()
        else:
            reports = _get_field(report_data, "reports", [])
            stats = _get_field(report_data, "statistics", {})
            gen_time = _get_field(report_data, "generated_at", datetime.now(timezone.utc).isoformat())

        total_reports = len(reports)
        critical_count = _get_field(stats, "critical_defect_count")
        if critical_count is None:
            critical_count = sum(1 for r in reports if _safe_sev(r) >= 7.0)
        else:
            critical_count = _safe_int_val(critical_count, 0)

        raw_avg_neg = _get_field(stats, "avg_negativity_score")
        avg_negativity = _safe_float_val(raw_avg_neg, 0.0)

        # Category aggregation
        category_counts: Dict[str, int] = {}
        for r in reports:
            raw_cat = _get_field(r, "defect_category") or _get_field(r, "category")
            cat = str(raw_cat).strip() if (raw_cat and str(raw_cat).strip()) else "UNKNOWN"
            category_counts[cat] = category_counts.get(cat, 0) + 1

        top_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)

        lines = [
            "# [대한민국 EV 실생활 결함 및 커뮤니티 동향 일일 브리핑]",
            f"- **발행 시각(UTC)**: {gen_time}",
            f"- **총 수집/분류 결함 건수**: {total_reports}건 (고위험/긴급 결함: {critical_count}건)",
            f"- **평균 부정 감성 점수**: {avg_negativity:.2f} / 1.00",
            "",
            "## 📌 주요 결함 카테고리별 비중",
        ]

        if top_categories:
            for cat, count in top_categories:
                ratio = (count / total_reports * 100) if total_reports > 0 else 0.0
                lines.append(f"- **{cat}**: {count}건 ({ratio:.1f}%)")
        else:
            lines.append("- 수집된 결함 내역이 없습니다.")

        lines.extend([
            "",
            "## 🚨 긴급 주의 결함 사례 (DSI >= 7.0)",
        ])

        critical_reports = [r for r in reports if _safe_sev(r) >= 7.0][:5]
        if critical_reports:
            for r in critical_reports:
                brand = _get_field(r, "vehicle_brand", "") or ""
                model = _get_field(r, "vehicle_model", "") or ""
                v_model = f"{brand} {model}".strip() or "차종 미상"
                topic = _get_field(r, "defect_topic") or _get_field(r, "title") or "상세 없음"
                dsi = _safe_sev(r)
                lines.append(f"- 🔴 **[{v_model}]** {topic} (심각도 DSI: {dsi:.1f})")
        else:
            lines.append("- 현재 긴급 심각도(DSI >= 7.0) 결함 사례 없음.")

        return "\n".join(lines)

    def generate_statistical_report(
        self,
        records: List[Any],
        summary_stats: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Encapsulate statistical reporting formatting into publication-grade Markdown."""
        total_records = len(records)
        stats = summary_stats or {}

        # Brand and platform distribution
        brand_counts: Dict[str, int] = {}
        platform_counts: Dict[str, int] = {}
        category_counts: Dict[str, int] = {}

        severity_scores: List[float] = []
        for rec in records:
            brand = _get_field(rec, "vehicle_brand") or "기타/미지정"
            brand_counts[brand] = brand_counts.get(brand, 0) + 1

            plat = _get_field(rec, "source") or _get_field(rec, "platform") or "커뮤니티"
            platform_counts[plat] = platform_counts.get(plat, 0) + 1

            cat = _get_field(rec, "defect_category") or _get_field(rec, "category") or "기타"
            category_counts[cat] = category_counts.get(cat, 0) + 1

            dsi = _get_field(rec, "severity_index")
            if dsi is not None:
                try:
                    f_dsi = float(dsi)
                    if not (math.isnan(f_dsi) or math.isinf(f_dsi)):
                        severity_scores.append(f_dsi)
                except (ValueError, TypeError, OverflowError):
                    pass

        avg_dsi = (sum(severity_scores) / len(severity_scores)) if severity_scores else 0.0

        lines = [
            "# EV 결함 및 품질 빅데이터 통계 분석 보고서",
            "",
            f"- **분석 표본수**: 총 {total_records:,}건",
            f"- **평균 결함 심각도 지수 (DSI)**: {avg_dsi:.2f} / 10.00",
            "",
            "## 1. 플랫폼별 수집 분포",
            "| 플랫폼 | 건수 | 점유율 (%) |",
            "|---|---|---|",
        ]
        for p, count in sorted(platform_counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total_records * 100) if total_records > 0 else 0.0
            lines.append(f"| {p} | {count:,} | {pct:.1f}% |")

        lines.extend([
            "",
            "## 2. 결함 유형(5대 축) 분포",
            "| 결함 카테고리 | 건수 | 점유율 (%) |",
            "|---|---|---|",
        ])
        for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total_records * 100) if total_records > 0 else 0.0
            lines.append(f"| {cat} | {count:,} | {pct:.1f}% |")

        lines.extend([
            "",
            "## 3. 제조사/브랜드별 결함 비중",
            "| 브랜드 | 건수 | 점유율 (%) |",
            "|---|---|---|",
        ])
        for brand, count in sorted(brand_counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total_records * 100) if total_records > 0 else 0.0
            lines.append(f"| {brand} | {count:,} | {pct:.1f}% |")

        return "\n".join(lines)

    def generate_combined_briefing(
        self,
        subsidy_payload: Optional[SubsidyPayload] = None,
        defect_reports: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None,
        fallback_used: bool = False,
    ) -> str:
        """Combine subsidy status and defect report highlights into a unified executive markdown document."""
        sections: List[str] = []
        if subsidy_payload is not None:
            sections.append(self.generate_subsidy_briefing(subsidy_payload, fallback_used=fallback_used))
        if defect_reports is not None:
            sections.append(self.generate_defect_briefing(defect_reports))
        return "\n\n---\n\n".join(sections)


__all__ = ["ReportGenerator"]
