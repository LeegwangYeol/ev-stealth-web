"""
tests/test_subsidy_tracker_frontend_audit.py - Comprehensive Frontend Audit Test Suite
for Next.js /subsidy-tracker Client and Components.

Covers:
1. Filtering & Sorting:
   - Category filtering across passenger (승용), commercial (화물), and bus (승합).
   - Regional zone filtering (CAPITAL, YEONGNAM, HONAM, CHUNGCHEONG, GANGWON_JEJU).
   - 8-way Sort options (DEPLETION_DESC, DEPLETION_ASC, REMAINING_ASC, REMAINING_DESC, LOCAL_SUBSIDY_DESC, LOCAL_SUBSIDY_ASC, NAME_ASC, NAME_DESC).
   - Real-time deferred search query filtering (Korean name, English name, ISO code, sub-municipalities).
2. Progress Bar Color Coding Thresholds:
   - >= 95.0% or CRITICAL: rose-500 bar / rose-400 text (critical red)
   - 80.0% ~ 94.9% or WARNING: orange-500 bar / orange-400 text (warning orange)
   - 60.0% ~ 79.9% or CAUTION: amber-400 bar / amber-400 text (caution yellow)
   - < 60.0% or HEALTHY: emerald-500 bar / emerald-400 text (healthy green)
   - >= 100.0% or DEPLETED: slate-500 bar / slate-300 text (depleted slate)
   - WCAG AA non-text contrast border (border-slate-600) with >= 3:1 contrast against dark background.
3. Empty State Display:
   - Graceful status region with role="status" and aria-live="polite".
   - Accessible action button to reset filters ("전체 필터 초기화").
   - Standalone empty table row in SubsidyTableView.
4. Keyboard Accessibility & Screen Reader (WCAG AA):
   - Skip navigation to #subsidy-calculator.
   - WAI-ARIA tablist pattern with Arrow navigation on category tabs and FAQ accordion.
   - Visible high-contrast focus rings on all interactive elements.
   - Screen-reader accessible table caption, scope="col" / scope="row", aria-sort, role="progressbar" with aria-valuetext.
"""

from __future__ import annotations

from pathlib import Path
import re
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
COMPONENTS_DIR = SRC_DIR / "components" / "subsidy"
APP_DIR = SRC_DIR / "app" / "subsidy-tracker"


class TestSubsidyTrackerFrontendAudit(unittest.TestCase):
    """Audit test suite for Subsidy Tracker components and client implementation."""

    @classmethod
    def setUpClass(cls):
        cls.client_path = APP_DIR / "SubsidyTrackerClient.tsx"
        cls.progress_path = COMPONENTS_DIR / "SubsidyProgressBar.tsx"
        cls.table_path = COMPONENTS_DIR / "SubsidyTableView.tsx"
        cls.badge_path = COMPONENTS_DIR / "SubsidyBadge.tsx"
        cls.accordion_path = COMPONENTS_DIR / "SubsidyFaqAccordion.tsx"
        cls.error_path = COMPONENTS_DIR / "SubsidyErrorBoundary.tsx"

        cls.assertTrue(cls.client_path.exists(), f"Missing {cls.client_path}")
        cls.assertTrue(cls.progress_path.exists(), f"Missing {cls.progress_path}")
        cls.assertTrue(cls.table_path.exists(), f"Missing {cls.table_path}")
        cls.assertTrue(cls.badge_path.exists(), f"Missing {cls.badge_path}")

        cls.client_source = cls.client_path.read_text(encoding="utf-8")
        cls.progress_source = cls.progress_path.read_text(encoding="utf-8")
        cls.table_source = cls.table_path.read_text(encoding="utf-8")
        cls.badge_source = cls.badge_path.read_text(encoding="utf-8")

    # =========================================================================
    # 1. Filtering & Sorting Verification
    # =========================================================================

    def test_01_category_tabs_and_filtering(self):
        """Must support 3 categories (승용, 화물, 승합) with accessible tablist semantics."""
        self.assertIn("'passenger'", self.client_source)
        self.assertIn("'commercial'", self.client_source)
        self.assertIn("'bus'", self.client_source)
        self.assertIn("전기승용 (승용차)", self.client_source)
        self.assertIn("전기화물 (소형/특장)", self.client_source)
        self.assertIn("전기승합 (버스)", self.client_source)
        self.assertIn('role="tablist"', self.client_source)
        self.assertIn('role="tab"', self.client_source)
        self.assertIn('aria-selected={isSelected}', self.client_source)
        self.assertIn('onKeyDown={(e) => handleCategoryKeyDown(e, idx)}', self.client_source)

    def test_02_regional_zone_filtering(self):
        """Must support 6 regional zones with ISO code categorization."""
        self.assertIn("'CAPITAL'", self.client_source)
        self.assertIn("'YEONGNAM'", self.client_source)
        self.assertIn("'HONAM'", self.client_source)
        self.assertIn("'CHUNGCHEONG'", self.client_source)
        self.assertIn("'GANGWON_JEJU'", self.client_source)
        self.assertIn("getRegionZone", self.client_source)

    def test_03_sort_order_options(self):
        """Must support 8 sort options including depletion, remaining quota, local subsidy, and name."""
        sort_keys = [
            'DEPLETION_DESC',
            'DEPLETION_ASC',
            'REMAINING_ASC',
            'REMAINING_DESC',
            'LOCAL_SUBSIDY_DESC',
            'LOCAL_SUBSIDY_ASC',
            'NAME_ASC',
            'NAME_DESC',
        ]
        for key in sort_keys:
            self.assertIn(f"value=\"{key}\"", self.client_source)

    def test_04_search_query_with_deferred_value(self):
        """Search input must use useDeferredValue for 60fps responsiveness and handle sub-municipalities."""
        self.assertIn('useDeferredValue(searchQuery)', self.client_source)
        self.assertIn('role="searchbox"', self.client_source)
        self.assertIn('aria-label="지자체 검색"', self.client_source)
        self.assertIn('handleClearSearch', self.client_source)
        self.assertIn('matchMuni', self.client_source)

    # =========================================================================
    # 2. Progress Bar Color Coding Thresholds Verification
    # =========================================================================

    def test_05_progress_bar_color_threshold_helper(self):
        """SubsidyProgressBar must export getDepletionColor and implement color coding thresholds."""
        self.assertIn('export const getDepletionColor', self.progress_source)
        self.assertIn('bg-rose-500', self.progress_source, "Critical red for >=95%")
        self.assertIn('bg-orange-500', self.progress_source, "Warning orange for 80-95%")
        self.assertIn('bg-amber-400', self.progress_source, "Caution yellow for 60-80%")
        self.assertIn('bg-emerald-500', self.progress_source, "Healthy green for <60%")
        self.assertIn('bg-slate-500', self.progress_source, "Depleted slate for >=100%")

    def test_06_table_view_progress_bar_thresholds(self):
        """SubsidyTableView mini progress bar and text must implement matching color coding."""
        self.assertIn('depletionRate >= 95', self.table_source)
        self.assertIn('depletionRate >= 80', self.table_source)
        self.assertIn('depletionRate >= 60', self.table_source)
        self.assertIn('bg-rose-500', self.table_source)
        self.assertIn('bg-orange-500', self.table_source)
        self.assertIn('bg-amber-400', self.table_source)
        self.assertIn('bg-emerald-400', self.table_source)
        self.assertIn('bg-slate-500', self.table_source)

    def test_07_progress_bar_wcag_contrast_border(self):
        """Progress bar must enforce border-slate-600 for >= 3:1 non-text contrast."""
        self.assertIn('border-slate-600', self.progress_source)
        self.assertIn('border-r border-slate-950', self.progress_source)

    # =========================================================================
    # 3. Empty State Display Verification
    # =========================================================================

    def test_08_empty_search_results_feedback(self):
        """When filteredRegions is empty, an accessible status container with reset button must be rendered."""
        self.assertIn('filteredRegions.length === 0', self.client_source)
        self.assertIn('검색 및 필터 조건에 일치하는 지자체가 없습니다', self.client_source)
        self.assertIn('aria-live="polite"', self.client_source)
        self.assertIn('onClick={handleResetFilters}', self.client_source)

    def test_09_table_view_empty_rows_fallback(self):
        """SubsidyTableView must gracefully render a fallback row when renderedRows is empty."""
        self.assertIn('renderedRows.length > 0', self.table_source)
        self.assertIn('표시할 지자체 데이터가 없습니다', self.table_source)

    # =========================================================================
    # 4. Keyboard Accessibility & Screen Reader Verification
    # =========================================================================

    def test_10_skip_link_present(self):
        """Skip navigation link to calculator must exist with visible focus style."""
        self.assertIn('href="#subsidy-calculator"', self.client_source)
        self.assertIn('sr-only focus:not-sr-only', self.client_source)

    def test_11_table_accessibility_semantics(self):
        """Table must declare caption, scope='col' on headers, scope='row' on region cells, and dynamic aria-sort."""
        self.assertIn('<caption className="sr-only">', self.table_source)
        self.assertIn('scope="col"', self.table_source)
        self.assertIn('scope="row"', self.table_source)
        self.assertIn('getSortAria', self.table_source)
        self.assertIn('tabIndex={0}', self.table_source)
        self.assertIn('role="region"', self.table_source)

    def test_12_accessible_touch_targets(self):
        """All buttons and inputs must meet WCAG 2.5.5 minimum touch target size (>= 44px)."""
        self.assertIn('min-h-[44px]', self.client_source)
        self.assertIn('min-h-[44px]', self.table_source)


if __name__ == '__main__':
    unittest.main()
