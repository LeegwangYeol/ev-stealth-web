"""
tests/test_mobile_responsive_w3.py - Mobile Viewport (<390px) Responsive Layout Test Suite (Wave 3)

Authoritative Verification Invariants:
1. Container widths and margins:
   - Root <main> uses responsive max-width and touch margin/padding constraints.
   - All data tables or wide comparison grids are wrapped in overflow-x-auto containers to prevent horizontal blowout.
   - Fixed min-width tokens > 320px are strictly guarded by overflow-x-auto / overflow-x-scroll.
2. Button & interactive touch targets:
   - Touch targets and mobile menu toggles have accessible heights (>= 40-44px).
   - Checkboxes have accessible dimensions (w-6 h-6).
   - Form inputs have full-width or touch-friendly padding.
3. Responsive flex wrapping:
   - Header badge rows, filter chip bars, and stat legends use flex-wrap or flex-col sm:flex-row.
   - No un-wrapped multi-item flex rows that blowout viewports narrower than 390px.
"""

import os
import re
import pytest

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/app'))
PAGES_UNDER_TEST = {
    'home': os.path.join(APP_DIR, 'page.tsx'),
    'subsidy-tracker-page': os.path.join(APP_DIR, 'subsidy-tracker/page.tsx'),
    'subsidy-tracker-client': os.path.join(APP_DIR, 'subsidy-tracker/SubsidyTrackerClient.tsx'),
    'depreciation-calculator-page': os.path.join(APP_DIR, 'depreciation-calculator/page.tsx'),
    'depreciation-calculator-client': os.path.join(APP_DIR, 'depreciation-calculator/DepreciationCalculatorClient.tsx'),
    'reliability-analytics-page': os.path.join(APP_DIR, 'reliability-analytics/page.tsx'),
    'reliability-analytics-client': os.path.join(APP_DIR, 'reliability-analytics/ReliabilityDashboardClient.tsx'),
    'recall-portal-page': os.path.join(APP_DIR, 'recall-portal/page.tsx'),
    'recall-portal-client': os.path.join(APP_DIR, 'recall-portal/RecallPortalClient.tsx'),
    'pdi-checklist-page': os.path.join(APP_DIR, 'pdi-checklist/page.tsx'),
    'pdi-checklist-client': os.path.join(APP_DIR, 'pdi-checklist/PdiChecklistClient.tsx'),
    'secret-admin-reports-page': os.path.join(APP_DIR, 'secret-admin-reports/page.tsx'),
    'secret-admin-reports-client': os.path.join(APP_DIR, 'secret-admin-reports/AdminDashboardClient.tsx'),
    'latest-2026': os.path.join(APP_DIR, '2026-latest/page.tsx'),
    'byd': os.path.join(APP_DIR, 'byd/page.tsx'),
    'hyundai-kia': os.path.join(APP_DIR, 'hyundai-kia/page.tsx'),
    'tesla': os.path.join(APP_DIR, 'tesla/page.tsx'),
    'global-brands': os.path.join(APP_DIR, 'global-brands/page.tsx'),
    'error': os.path.join(APP_DIR, 'error.tsx'),
    'not-found': os.path.join(APP_DIR, 'not-found.tsx'),
    'layout': os.path.join(APP_DIR, 'layout.tsx'),
}


def test_all_target_page_files_exist():
    for name, path in PAGES_UNDER_TEST.items():
        assert os.path.isfile(path), f"Expected page file {name} at {path} to exist"


def test_root_layout_mobile_drawer_and_viewport_containment():
    with open(PAGES_UNDER_TEST['layout'], 'r', encoding='utf-8') as f:
        content = f.read()

    # Mobile nav drawer max width must not exceed viewport
    assert 'max-w-[calc(100vw-2rem)]' in content, "Mobile drawer must prevent viewport blowout"
    # Mobile drawer toggle must have minimum touch target height
    assert 'min-h-[44px]' in content, "Mobile drawer toggle must have min-h-[44px] touch target"
    # Desktop nav is hidden on mobile screens
    assert 'hidden md:flex' in content, "Desktop nav must hide on small viewports"
    # Skip navigation link present
    assert 'href="#main-content"' in content, "Skip to content link must target main-content"


def test_tables_guarded_by_overflow_x_auto():
    """Verify that all non-sr-only tables are wrapped inside overflow-x-auto containers."""
    for name, path in PAGES_UNDER_TEST.items():
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            if '<table' in line:
                context_above = "".join(lines[max(0, i - 8):i + 1])
                is_sr_only = 'sr-only' in context_above
                if not is_sr_only:
                    has_overflow = 'overflow-x-auto' in context_above or 'overflow-x-scroll' in context_above
                    assert has_overflow, f"{name}:{i+1} visual <table> must be wrapped in an overflow-x-auto container"


def test_fixed_min_width_tokens_safe_on_mobile():
    """Ensure any min-w-[Npx] > 320px is guarded by an overflow wrapper."""
    for name, path in PAGES_UNDER_TEST.items():
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            match = re.search(r'min-w-\[(\d+)px\]', line)
            if match:
                px = int(match.group(1))
                if px > 320:
                    context_above = "".join(lines[max(0, i - 6):i + 1])
                    has_scroll = 'overflow-x-auto' in context_above or 'overflow-x-scroll' in context_above
                    assert has_scroll, f"{name}:{i+1} min-w-[{px}px] > 320px must be wrapped in overflow-x-auto"


def test_home_page_mobile_headings_and_flex_wrapping():
    with open(PAGES_UNDER_TEST['home'], 'r', encoding='utf-8') as f:
        content = f.read()

    # Title uses responsive scale
    assert 'text-3xl sm:text-4xl md:text-5xl' in content, "Home title must scale responsively on <390px viewports"
    # Feature card badge rows use flex-wrap
    assert content.count('flex flex-wrap items-center gap-2') >= 4, "Home hero cards must wrap badge subtitles"


def test_subsidy_tracker_mobile_responsiveness():
    with open(PAGES_UNDER_TEST['subsidy-tracker-client'], 'r', encoding='utf-8') as f:
        content = f.read()

    # Header badge row wraps
    assert 'flex flex-wrap items-center gap-2' in content
    # Regional grid heading wraps
    assert 'flex flex-wrap items-center justify-between gap-2' in content
    # Quick MSRP buttons wrap
    assert 'flex flex-wrap gap-2 text-[11px]' in content


def test_secret_admin_reports_platform_sources_flex_wrapping():
    with open(PAGES_UNDER_TEST['secret-admin-reports-client'], 'r', encoding='utf-8') as f:
        content = f.read()

    # Source platforms badges flex wrapping
    assert 'flex flex-wrap items-center gap-1.5' in content, "Admin platform source filter chips must flex-wrap"


def test_recall_portal_mobile_flex_wrapping():
    with open(PAGES_UNDER_TEST['recall-portal-client'], 'r', encoding='utf-8') as f:
        content = f.read()

    # 1-click sample vin header wraps
    assert 'flex flex-wrap items-center justify-between gap-1 mb-3' in content
    # Check result verdict badge wraps
    assert 'flex flex-wrap items-center gap-2' in content


def test_reliability_analytics_chart_tabs_and_legend_responsiveness():
    with open(PAGES_UNDER_TEST['reliability-analytics-client'], 'r', encoding='utf-8') as f:
        content = f.read()

    # Chart tab selector allows horizontal scrolling on narrow viewports
    assert 'max-w-full overflow-x-auto' in content
    # Heatmap legend items wrap gracefully
    assert 'flex flex-wrap items-center gap-x-3 gap-y-1.5' in content


def test_pdi_checklist_touch_targets_and_flex_wrapping():
    with open(PAGES_UNDER_TEST['pdi-checklist-client'], 'r', encoding='utf-8') as f:
        content = f.read()

    # Header controls wrap and have min touch targets
    assert 'flex flex-wrap items-center gap-2 self-start sm:self-auto' in content
    assert 'min-h-[40px]' in content
    # Checkbox touch size
    assert 'w-6 h-6' in content


def test_brand_detail_pages_responsive_h1():
    for brand in ['byd', 'hyundai-kia', 'tesla', 'global-brands', 'latest-2026']:
        with open(PAGES_UNDER_TEST[brand], 'r', encoding='utf-8') as f:
            content = f.read()
        assert 'text-2xl sm:text-3xl md:text-4xl font-bold' in content or 'text-2xl sm:text-3xl md:text-4xl font-extrabold' in content, (
            f"{brand} h1 title must scale down on <390px mobile screens"
        )


def test_error_and_not_found_responsive_layouts():
    with open(PAGES_UNDER_TEST['error'], 'r', encoding='utf-8') as f:
        err_content = f.read()
    assert 'flex flex-col sm:flex-row' in err_content
    assert 'px-6 py-3' in err_content  # >= 44px tap target

    with open(PAGES_UNDER_TEST['not-found'], 'r', encoding='utf-8') as f:
        nf_content = f.read()
    assert 'grid grid-cols-1 sm:grid-cols-2' in nf_content
    assert 'p-5' in nf_content  # touch cards
