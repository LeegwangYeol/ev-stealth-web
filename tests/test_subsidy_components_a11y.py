"""
tests/test_subsidy_components_a11y.py - Comprehensive Accessibility (WCAG 2.1 AA) and
Component Architecture Test Suite for Subsidy Tracker Components.

Covers:
1. SubsidyTableView.tsx:
   - Table headers with scope="col" on all column headers.
   - Dynamic aria-sort on sortable columns (NAME, REMAINING, DEPLETION, LOCAL_SUBSIDY).
   - Table row header with scope="row" for region names.
   - Screen-reader accessible <caption> element.
   - Nested sub-municipalities table with scope="col" and scope="row".
   - Accessible scroll region with role="region", aria-label, and tabIndex={0}.
2. SubsidyProgressBar.tsx:
   - Accessible role="progressbar" with aria-valuenow, aria-valuemin={0}, aria-valuemax={100}.
   - Descriptive aria-valuetext announcing formatted depletion rate, status, and remaining quota.
   - WCAG AA non-text contrast border (border-slate-600) with >= 3.0:1 contrast against dark backdrop.
   - Visual segment dividers (border-r border-slate-950) separating multi-layer progress bars for color-blind users.
3. SubsidyFaqAccordion.tsx:
   - Collapsible disclosure triggers declaring aria-expanded and matching aria-controls.
   - Panel content with matching id, role="region", and aria-labelledby.
   - Keyboard interaction support (ArrowUp, ArrowDown, Home, End).
4. SubsidyErrorBoundary.tsx & error.tsx:
   - Component & route-level error boundaries declaring role="alert" and aria-live="assertive".
   - Graceful recovery and retry actions.
5. SubsidyTrackerClient.tsx Integration:
   - View mode toggle (Grid Cards vs Table View) with aria-pressed.
   - Backward-compatible exports: getBadgeStyle, getStatusLabel, BRAND_PREFIX_REGEX.
"""

from __future__ import annotations

from pathlib import Path
import re
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
COMPONENTS_DIR = SRC_DIR / "components" / "subsidy"
APP_DIR = SRC_DIR / "app" / "subsidy-tracker"


class TestSubsidyTableViewA11y(unittest.TestCase):
    """Verifies WCAG AA compliance of SubsidyTableView.tsx."""

    @classmethod
    def setUpClass(cls):
        cls.path = COMPONENTS_DIR / "SubsidyTableView.tsx"
        cls.assertTrue(cls.path.exists(), f"Missing {cls.path}")
        cls.source = cls.path.read_text(encoding="utf-8")

    def test_01_table_has_caption_and_accessible_label(self):
        """Table must declare accessible caption and aria-label."""
        self.assertIn('<table', self.source)
        self.assertIn('aria-label="전국 지자체별 전기차 보조금 실시간 소진율 및 잔여 쿼터 비교 표"', self.source)
        self.assertTrue(
            bool(re.search(r'<caption\b[^>]*className=["\'][^"\']*sr-only[^"\']*["\']', self.source)),
            "Table must include a screen-reader only caption for WCAG 1.3.1 compliance."
        )

    def test_02_table_headers_declare_scope_col(self):
        """All column headers in the main comparison table must declare scope='col'."""
        col_headers = re.findall(r'<th\b([^>]*)>', self.source)
        self.assertGreater(len(col_headers), 0)
        col_scopes = [h for h in col_headers if 'scope="col"' in h]
        self.assertGreaterEqual(len(col_scopes), 8, "Expected at least 8 column headers with scope='col'.")

    def test_03_sortable_columns_declare_aria_sort(self):
        """Sortable column headers must dynamically expose aria-sort."""
        self.assertIn('aria-sort={getSortAria(', self.source)
        self.assertIn("'NAME'", self.source)
        self.assertIn("'REMAINING'", self.source)
        self.assertIn("'DEPLETION'", self.source)
        self.assertIn("'LOCAL_SUBSIDY'", self.source)

    def test_04_row_headers_declare_scope_row(self):
        """Region name cells must declare <th scope='row'> for row header identification."""
        self.assertTrue(
            bool(re.search(r'<th\b[^>]*scope="row"[^>]*>', self.source)),
            "Table body row header must declare scope='row' for region title."
        )

    def test_05_scrollable_container_accessible_semantics(self):
        """Horizontal scroll container must declare tabIndex={0}, role='region', and descriptive aria-label."""
        self.assertIn('tabIndex={0}', self.source)
        self.assertIn('role="region"', self.source)
        self.assertIn('aria-label="지자체별 보조금 소진율 비교 표 스크롤 영역"', self.source)

    def test_06_nested_municipalities_table_has_scope_headers(self):
        """Expandable municipality table must declare scope='col' and scope='row'."""
        self.assertIn('세부 시·군·구 보조금 현황표', self.source)
        self.assertTrue(
            bool(re.search(r'<th\b[^>]*scope="col"[^>]*>\s*시·군·구명', self.source)),
            "Municipality table must declare scope='col' for sub-district headers."
        )


class TestSubsidyProgressBarA11y(unittest.TestCase):
    """Verifies WCAG AA compliance of SubsidyProgressBar.tsx."""

    @classmethod
    def setUpClass(cls):
        cls.path = COMPONENTS_DIR / "SubsidyProgressBar.tsx"
        cls.assertTrue(cls.path.exists(), f"Missing {cls.path}")
        cls.source = cls.path.read_text(encoding="utf-8")

    def test_01_role_progressbar_and_aria_attributes(self):
        """Must declare role='progressbar', aria-valuenow, aria-valuemin, aria-valuemax, aria-label."""
        self.assertIn('role="progressbar"', self.source)
        self.assertIn('aria-valuenow=', self.source)
        self.assertIn('aria-valuemin={0}', self.source)
        self.assertIn('aria-valuemax={100}', self.source)
        self.assertIn('aria-label=', self.source)
        self.assertIn('aria-valuetext=', self.source)

    def test_02_contrast_border_and_segment_separators(self):
        """Progress bar must use high-contrast border (border-slate-600) and segment dividers."""
        self.assertIn('border-slate-600', self.source, "Must use border-slate-600 for >= 3:1 non-text contrast")
        self.assertIn('border-r border-slate-950', self.source, "Must separate segments with distinct border dividers")


class TestSubsidyFaqAccordionA11y(unittest.TestCase):
    """Verifies WCAG AA compliance of SubsidyFaqAccordion.tsx."""

    @classmethod
    def setUpClass(cls):
        cls.path = COMPONENTS_DIR / "SubsidyFaqAccordion.tsx"
        cls.assertTrue(cls.path.exists(), f"Missing {cls.path}")
        cls.source = cls.path.read_text(encoding="utf-8")

    def test_01_accordion_aria_expanded_and_controls(self):
        """Toggle buttons must declare aria-expanded and aria-controls."""
        self.assertIn('aria-expanded={isOpen}', self.source)
        self.assertIn('aria-controls={`faq-panel-${item.id}`}', self.source)
        self.assertIn('id={`faq-btn-${item.id}`}', self.source)

    def test_02_accordion_panel_semantics(self):
        """Panels must declare role='region' and aria-labelledby matching trigger id."""
        self.assertIn('role="region"', self.source)
        self.assertIn('aria-labelledby={`faq-btn-${item.id}`}', self.source)
        self.assertIn('hidden={!isOpen}', self.source)

    def test_03_keyboard_navigation(self):
        """Accordion must handle keyboard arrow navigation."""
        self.assertIn("e.key === 'ArrowDown'", self.source)
        self.assertIn("e.key === 'ArrowUp'", self.source)
        self.assertIn("e.key === 'Home'", self.source)
        self.assertIn("e.key === 'End'", self.source)


class TestSubsidyErrorBoundaries(unittest.TestCase):
    """Verifies route and component error boundary compliance."""

    def test_01_route_error_boundary_present(self):
        """Route-level error.tsx must exist with role='alert' and retry controls."""
        error_path = APP_DIR / "error.tsx"
        self.assertTrue(error_path.exists(), f"Missing {error_path}")
        source = error_path.read_text(encoding="utf-8")

        self.assertIn("'use client'", source)
        self.assertIn('role="alert"', source)
        self.assertIn('aria-live="assertive"', source)
        self.assertIn('reset()', source)

    def test_02_component_error_boundary_present(self):
        """SubsidyErrorBoundary component must declare role='alert' and reset handling."""
        boundary_path = COMPONENTS_DIR / "SubsidyErrorBoundary.tsx"
        self.assertTrue(boundary_path.exists(), f"Missing {boundary_path}")
        source = boundary_path.read_text(encoding="utf-8")

        self.assertIn('role="alert"', source)
        self.assertIn('aria-live="assertive"', source)
        self.assertIn('getDerivedStateFromError', source)


class TestSubsidyTrackerClientIntegration(unittest.TestCase):
    """Verifies SubsidyTrackerClient.tsx integration with new components."""

    @classmethod
    def setUpClass(cls):
        cls.path = APP_DIR / "SubsidyTrackerClient.tsx"
        cls.source = cls.path.read_text(encoding="utf-8")

    def test_01_view_mode_toggle_present(self):
        """Must include viewMode toggle supporting Card Grid and Table View."""
        self.assertIn('viewMode', self.source)
        self.assertIn('aria-label="지역 데이터 보기 방식 선택"', self.source)
        self.assertIn('aria-pressed={viewMode === \'grid\'}', self.source)
        self.assertIn('aria-pressed={viewMode === \'table\'}', self.source)

    def test_02_table_view_rendered_conditionally(self):
        """When viewMode === 'table', SubsidyTableView must be mounted."""
        self.assertIn('<SubsidyTableView', self.source)

    def test_03_error_boundary_wraps_calculator(self):
        """Calculator must be guarded by SubsidyErrorBoundary."""
        self.assertIn('<SubsidyErrorBoundary', self.source)
        self.assertIn('<SubsidyCalculator', self.source)

    def test_04_backward_compatible_exports(self):
        """Must retain getBadgeStyle, getStatusLabel, and BRAND_PREFIX_REGEX exports."""
        self.assertIn('export const getBadgeStyle', self.source)
        self.assertIn('export const getStatusLabel', self.source)
        self.assertIn('export const BRAND_PREFIX_REGEX', self.source)


if __name__ == '__main__':
    unittest.main()
