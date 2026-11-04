"""
tests/test_reliability_analytics_a11y_audit.py - Deep A11y, Responsiveness, & Contrast Audit Test Suite
for ev-stealth-web/src/app/reliability-analytics/ReliabilityDashboardClient.tsx
and ev-stealth-web/src/lib/reliabilityCalculations.ts.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


def _find_web_app_root() -> Path:
    candidates = [
        Path(__file__).resolve().parent.parent / "ev-stealth-web",
        Path(__file__).resolve().parent.parent,
        Path.cwd() / "ev-stealth-web",
        Path.cwd(),
    ]
    for c in candidates:
        if (c / "src" / "app").is_dir():
            return c
    return Path(__file__).resolve().parent.parent / "ev-stealth-web"


WEB_APP_ROOT = _find_web_app_root()
APP_DIR = WEB_APP_ROOT / "src" / "app"
LIB_DIR = WEB_APP_ROOT / "src" / "lib"


def read_source(relative_path: str) -> str:
    path = WEB_APP_ROOT / "src" / relative_path
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    return path.read_text(encoding="utf-8")


class TestReliabilityAnalyticsA11yAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client_source = read_source("app/reliability-analytics/ReliabilityDashboardClient.tsx")
        cls.calc_source = read_source("lib/reliabilityCalculations.ts")

    def test_table_captions_and_headers_scope(self):
        """1. Accessible tables: Every table must have a caption, th scope='col', and th scope='row'."""
        # Heatmap table caption
        self.assertIn("<caption", self.client_source)
        self.assertIn("연식별 전기차 신뢰성 및 결함 심각도(DSI) 매트릭스", self.client_source)

        # Repair cost matrix caption
        self.assertIn(
            "보증 만료 후 폭탄 수리비 및 핵심 부품별 교체 비용 매트릭스",
            self.client_source,
        )

        # Heatmap table headers scope='col'
        self.assertIn('scope="col"', self.client_source)
        # Heatmap row headers scope='row'
        self.assertIn('scope="row"', self.client_source)

    def test_complex_metric_cards_aria_describedby(self):
        """2. Complex metric cards must have aria-describedby and role='region'."""
        # Hero KPI score cards
        self.assertIn('aria-labelledby="kpi-records-heading"', self.client_source)
        self.assertIn('aria-describedby="kpi-records-desc"', self.client_source)
        self.assertIn('id="kpi-records-desc"', self.client_source)

        self.assertIn('aria-labelledby="kpi-dsi-heading"', self.client_source)
        self.assertIn('aria-describedby="kpi-dsi-desc"', self.client_source)
        self.assertIn('id="kpi-dsi-desc"', self.client_source)

        self.assertIn('aria-labelledby="kpi-avoid-heading"', self.client_source)
        self.assertIn('aria-describedby="kpi-avoid-desc"', self.client_source)
        self.assertIn('id="kpi-avoid-desc"', self.client_source)

        self.assertIn('aria-labelledby="kpi-category-heading"', self.client_source)
        self.assertIn('aria-describedby="kpi-category-desc"', self.client_source)
        self.assertIn('id="kpi-category-desc"', self.client_source)

        # Model card DSI gauge
        self.assertIn('aria-labelledby={`model-dsi-title-${model.id}`}', self.client_source)
        self.assertIn('aria-describedby={`model-dsi-desc-${model.id}`}', self.client_source)
        self.assertIn('id={`model-dsi-desc-${model.id}`}', self.client_source)

        # Category share cards
        self.assertIn(
            'aria-describedby={`cat-desc-${cat.code} cat-cost-${cat.code}`}',
            self.client_source,
        )

    def test_mobile_responsiveness_and_overflow(self):
        """3. Mobile responsiveness and overflow handling on table scroll wrappers."""
        # Table and chart scroll wrappers must have overflow-x-auto, role='region', tabIndex={0}, and focus-visible
        scroll_wrapper_matches = [
            tag for tag in re.findall(r'<div\b[^>]*?overflow-x-auto[^>]*?>', self.client_source)
            if 'role="tablist"' not in tag
        ]
        self.assertGreaterEqual(len(scroll_wrapper_matches), 3)
        for tag in scroll_wrapper_matches:
            self.assertIn('role="region"', tag)
            self.assertIn("tabIndex={0}", tag)
            self.assertIn("focus-visible:ring-2", tag)

        # Heatmap table and repair cost table must define min-w to prevent crushing
        self.assertIn("min-w-[680px]", self.client_source)
        self.assertIn("min-w-[700px]", self.client_source)

        # Sticky columns on mobile for orientation
        self.assertIn("sticky left-0", self.client_source)

    def test_color_contrast_classes(self):
        """4. Color contrast compliance: verify high-contrast classes in calculation helpers and client."""
        # getDsiSeverityLevel in reliabilityCalculations.ts must use >= 4.5:1 classes
        self.assertIn("text-rose-700", self.calc_source)
        self.assertIn("text-amber-800", self.calc_source)
        self.assertIn("text-yellow-900", self.calc_source)
        self.assertIn("text-emerald-800", self.calc_source)
        # Must not contain failing low-contrast text-rose-600
        self.assertNotIn("textColor: 'text-rose-600'", self.calc_source)

        # getVerdictBadgeInfo in reliabilityCalculations.ts must use compliant text classes
        self.assertIn("textClass: 'text-amber-900'", self.calc_source)
        self.assertIn("textClass: 'text-rose-800'", self.calc_source)
        self.assertIn("textClass: 'text-emerald-800'", self.calc_source)
        self.assertNotIn("textClass: 'text-amber-700'", self.calc_source)

        # Category tag colors in ReliabilityDashboardClient.tsx
        self.assertIn("text: 'text-emerald-800'", self.client_source)
        self.assertIn("text: 'text-amber-900'", self.client_source)

    def test_escape_key_and_semantic_list(self):
        """5. Escape key listener for detail popup & semantic <ul>/<li> for year evaluations."""
        # Escape key listener
        self.assertIn("e.key === 'Escape'", self.client_source)
        self.assertIn("setHoveredCell(null)", self.client_source)

        # Semantic list for year evaluations
        self.assertIn('<ul', self.client_source)
        self.assertIn('role="list"', self.client_source)
        self.assertIn('<li', self.client_source)

    def test_accessible_legends_and_svg_descriptions(self):
        """6. Chart accessibility: semantic <ul> legends, dynamic SVG desc, and aria-hidden decorative icons."""
        # Semantic accessible legends
        self.assertIn('aria-label="히트맵 판정 범례"', self.client_source)
        self.assertIn('id="dsi-legend-title"', self.client_source)
        self.assertIn('aria-labelledby="dsi-legend-title"', self.client_source)
        self.assertIn('aria-label="결함 부문별 산업 점유율 범례"', self.client_source)

        # Dynamic SVG desc and aria-hidden grid marks
        self.assertIn('desc id="brand-dsi-svg-desc"', self.client_source)
        self.assertIn('{brandSvgDesc}', self.client_source)
        self.assertIn('<g aria-hidden="true">', self.client_source)

        # Decorative emoji icons marked aria-hidden
        self.assertIn('<span aria-hidden="true">🛡️</span>', self.client_source)
        self.assertIn('<span aria-hidden="true">📈</span>', self.client_source)
        self.assertIn('<span aria-hidden="true">💡</span>', self.client_source)
        self.assertIn('<span aria-hidden="true">💣</span>', self.client_source)

    def test_performance_indexing_and_edge_case_fallbacks(self):
        """7. Performance precomputed indexing & defensive fallback handling."""
        # Precomputed indexes
        self.assertIn('_searchIndex', self.client_source)
        self.assertIn('_categoryMatch', self.client_source)
        self.assertIn('_verdicts', self.client_source)

        # Defensive handling of brand.models and empty fallbacks
        self.assertIn('Array.isArray(brand?.models) ? brand.models.length : 0', self.client_source)
        self.assertIn('등록된 연식별 결함 데이터가 없습니다.', self.client_source)
        self.assertIn('브랜드별 DSI 결함 통계 데이터가 없습니다.', self.client_source)
        self.assertIn('부문별 결함 비중 데이터가 없습니다.', self.client_source)
        self.assertIn('등록된 보증 외 수리비 매트릭스 데이터가 없습니다.', self.client_source)


if __name__ == "__main__":
    unittest.main()
