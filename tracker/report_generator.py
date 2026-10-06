"""tracker/report_generator.py - Markdown Briefing and Statistical Report Formatter.

Encapsulates:
- Executive markdown summary briefings for EV subsidy depletion monitoring.
- Defect incident briefings and community trend summaries.
- Comprehensive statistical reporting and metric aggregation formatting.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from tracker.subsidy_models import RegionRecord, SubsidyPayload


def _metric_val(metric: Any, key: str, default: Any = 0) -> Any:
    """Safely extract metric attribute or dict key, supporting dict and dataclass instances."""
    if metric is None:
        return default
    if isinstance(metric, dict):
        return metric.get(key, default)
    return getattr(metric, key, default)


class ReportGenerator:
    """Encapsulates executive markdown briefing and statistical reporting formatting."""

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
        summary = payload.nationwide_summary
        gen_time = payload.metadata.generated_at

        def _get_passenger_remaining(region: RegionRecord) -> int:
            cats = getattr(region, "categories", None)
            if not isinstance(cats, dict):
                return 0
            p_cat = cats.get("passenger")
            if p_cat is None:
                return 0
            return _metric_val(p_cat, "remaining_units", 0)

        critical_regions = [
            f"{r.name_ko} ({r.overall_depletion_rate}%, 잔여: {_get_passenger_remaining(r):,}대)"
            for r in payload.regions
            if r.overall_status in ("CRITICAL", "DEPLETED")
        ]
        warning_regions = [
            f"{r.name_ko} ({r.overall_depletion_rate}%, 잔여: {_get_passenger_remaining(r):,}대)"
            for r in payload.regions
            if r.overall_status == "WARNING"
        ]

        category_totals = getattr(summary, "category_totals", None) or {}
        p_info = category_totals.get("passenger", {})
        c_info = category_totals.get("commercial", {})
        b_info = category_totals.get("bus", {})

        status_text = "FALLBACK_BASELINE (Resilient)" if fallback_used else "SUCCESS (Live Sync)"

        lines = [
            "# [대한민국 2026 전국 지자체 전기차 보조금 실시간 소진율 모니터링]",
            f"- **기록 시각(UTC)**: {gen_time}",
            f"- **파이프라인 상태**: {status_text}",
            f"- **전국 평균 소진율**: {summary.nationwide_depletion_rate}% (총 공고: {summary.total_announced_units:,}대 / 접수: {summary.total_applied_units:,}대)",
            f"- **집행 예산**: {summary.disbursed_budget_billion_krw:,}억 원 / 총 예산 {summary.total_budget_billion_krw:,}억 원",
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
            f"- **승용**: 공고 {_metric_val(p_info, 'announced_units', 0):,}대 | 접수 {_metric_val(p_info, 'applied_units', 0):,}대 ({_metric_val(p_info, 'depletion_rate', 0)}%) | 잔여 {_metric_val(p_info, 'remaining_units', 0):,}대 [{_metric_val(p_info, 'status', 'N/A')}]",
            f"- **화물**: 공고 {_metric_val(c_info, 'announced_units', 0):,}대 | 접수 {_metric_val(c_info, 'applied_units', 0):,}대 ({_metric_val(c_info, 'depletion_rate', 0)}%) | 잔여 {_metric_val(c_info, 'remaining_units', 0):,}대 [{_metric_val(c_info, 'status', 'N/A')}]",
            f"- **승합(버스)**: 공고 {_metric_val(b_info, 'announced_units', 0):,}대 | 접수 {_metric_val(b_info, 'applied_units', 0):,}대 ({_metric_val(b_info, 'depletion_rate', 0)}%) | 잔여 {_metric_val(b_info, 'remaining_units', 0):,}대 [{_metric_val(b_info, 'status', 'N/A')}]",
            "",
            "## 💡 예비 차주 권고 사항",
            "- 대구, 울산, 경북, 제주는 보조금 마감 직전(소진율 96%~99%)입니다. 실계약자는 대기 순번 및 제조사 즉시 출고 재고를 확인하십시오.",
            "- 전남(신안 1,150만 원), 경북(울릉 1,100만 원), 충남(태안 900만 원) 등 군 단위 지역은 고액 보조금이 지급되나 거주기간 요건(30~90일)을 확인해야 합니다.",
        ]
        return "\n".join(lines)

    def generate_defect_briefing(
        self,
        report_data: Union[Dict[str, Any], List[Dict[str, Any]]],
    ) -> str:
        """Generate executive markdown summary briefing for daily EV defect reports."""
        if isinstance(report_data, list):
            reports = report_data
            stats = {}
            gen_time = datetime.now(timezone.utc).isoformat()
        else:
            reports = report_data.get("reports", [])
            stats = report_data.get("statistics", {})
            gen_time = report_data.get("generated_at", datetime.now(timezone.utc).isoformat())

        total_reports = len(reports)
        critical_count = stats.get("critical_defect_count", sum(1 for r in reports if r.get("severity_index", 0) >= 7.0))
        avg_negativity = stats.get("avg_negativity_score", 0.0)

        # Category aggregation
        category_counts: Dict[str, int] = {}
        for r in reports:
            cat = r.get("defect_category", "UNKNOWN")
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

        critical_reports = [r for r in reports if r.get("severity_index", 0) >= 7.0][:5]
        if critical_reports:
            for r in critical_reports:
                model = f"{r.get('vehicle_brand', '')} {r.get('vehicle_model', '')}".strip() or "차종 미상"
                topic = r.get("defect_topic") or r.get("title") or "상세 없음"
                dsi = r.get("severity_index", 0.0)
                lines.append(f"- 🔴 **[{model}]** {topic} (심각도 DSI: {dsi:.1f})")
        else:
            lines.append("- 현재 긴급 심각도(DSI >= 7.0) 결함 사례 없음.")

        return "\n".join(lines)

    def generate_statistical_report(
        self,
        records: List[Dict[str, Any]],
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
            brand = rec.get("vehicle_brand") or "기타/미지정"
            brand_counts[brand] = brand_counts.get(brand, 0) + 1

            plat = rec.get("source") or rec.get("platform") or "커뮤니티"
            platform_counts[plat] = platform_counts.get(plat, 0) + 1

            cat = rec.get("defect_category") or "기타"
            category_counts[cat] = category_counts.get(cat, 0) + 1

            dsi = rec.get("severity_index")
            if dsi is not None:
                try:
                    severity_scores.append(float(dsi))
                except (ValueError, TypeError):
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
