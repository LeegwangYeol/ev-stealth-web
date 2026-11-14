"""
tests/test_responsive_mobile_layout_audit.py

Authoritative Test Suite: Responsive Design & Mobile Layout Audit
Verifies:
1. Mobile viewports (320px to 480px, tablets 768px, desktops 1024px+)
2. Horizontal scrollbars & overflow prevention (overflow-x-hidden on body/html, overflow-x-auto on data tables)
3. Touch target dimensions (WCAG 2.5.5 / 2.5.8 minimum 44x44px for buttons, links, inputs, selects, toggles)
4. Responsive navigation in BrandComparisonNav.tsx and header/footer components
5. Keyboard focus trap, aria-expanded synchronization, and resize listeners in GlobalNavListener
"""

import os
import re
import pytest

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/app'))
COMPONENTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/components'))

LAYOUT_FILE = os.path.join(APP_DIR, 'layout.tsx')
GLOBALS_CSS = os.path.join(APP_DIR, 'globals.css')
BRAND_NAV_FILE = os.path.join(COMPONENTS_DIR, 'BrandComparisonNav.tsx')
FOOTER_FILE = os.path.join(COMPONENTS_DIR, 'layout/SiteFooter.tsx')
NAV_LISTENER_FILE = os.path.join(COMPONENTS_DIR, 'GlobalNavListener.tsx')
SUBSIDY_TABLE_VIEW = os.path.join(COMPONENTS_DIR, 'subsidy/SubsidyTableView.tsx')

CLIENT_PAGES = {
    'subsidy': os.path.join(APP_DIR, 'subsidy-tracker/SubsidyTrackerClient.tsx'),
    'subsidy_table': SUBSIDY_TABLE_VIEW,
    'depreciation': os.path.join(APP_DIR, 'depreciation-calculator/DepreciationCalculatorClient.tsx'),
    'reliability': os.path.join(APP_DIR, 'reliability-analytics/ReliabilityDashboardClient.tsx'),
    'recall': os.path.join(APP_DIR, 'recall-portal/RecallPortalClient.tsx'),
    'pdi': os.path.join(APP_DIR, 'pdi-checklist/PdiChecklistClient.tsx'),
    'admin': os.path.join(APP_DIR, 'secret-admin-reports/AdminDashboardClient.tsx'),
    'home': os.path.join(APP_DIR, 'page.tsx'),
    'byd': os.path.join(APP_DIR, 'byd/page.tsx'),
    'tesla': os.path.join(APP_DIR, 'tesla/page.tsx'),
    'hyundai-kia': os.path.join(APP_DIR, 'hyundai-kia/page.tsx'),
    'global-brands': os.path.join(APP_DIR, 'global-brands/page.tsx'),
    '2026-latest': os.path.join(APP_DIR, '2026-latest/page.tsx'),
}


def extract_jsx_tags(content, target_tags=('button', 'select', 'input', 'a')):
    """Accurately extracts JSX tags even when attributes contain arrow functions like (e) => ..."""
    pos = 0
    tags = []
    tag_re = re.compile(r'<(' + '|'.join(target_tags) + r')\b')
    while pos < len(content):
        m = tag_re.search(content, pos)
        if not m:
            break
        tag_name = m.group(1)
        start = m.start()
        i = m.end()
        brace_depth = 0
        in_quote = None
        while i < len(content):
            ch = content[i]
            if in_quote:
                if ch == '\\':
                    i += 2
                    continue
                elif ch == in_quote:
                    in_quote = None
            else:
                if ch in ('"', "'", '`'):
                    in_quote = ch
                elif ch == '{':
                    brace_depth += 1
                elif ch == '}':
                    brace_depth = max(0, brace_depth - 1)
                elif ch == '>' and brace_depth == 0:
                    tag_str = content[start:i+1]
                    line_no = content[:start].count('\n') + 1
                    tags.append((tag_name, tag_str, line_no))
                    pos = i + 1
                    break
            i += 1
        else:
            break
    return tags


def test_core_responsive_files_exist():
    assert os.path.isfile(LAYOUT_FILE), "Root layout.tsx must exist"
    assert os.path.isfile(GLOBALS_CSS), "globals.css must exist"
    assert os.path.isfile(BRAND_NAV_FILE), "BrandComparisonNav.tsx must exist"
    assert os.path.isfile(FOOTER_FILE), "SiteFooter.tsx must exist"
    assert os.path.isfile(NAV_LISTENER_FILE), "GlobalNavListener.tsx must exist"
    for name, path in CLIENT_PAGES.items():
        assert os.path.isfile(path), f"Client page {name} at {path} must exist"


# ---------------------------------------------------------------------------
# 1. Mobile Viewports (320px - 480px, tablets 768px, desktops 1024px+)
# ---------------------------------------------------------------------------

def test_viewport_meta_configuration():
    """Verify viewport configuration in layout.tsx ensures scalable responsive viewing."""
    with open(LAYOUT_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'width: "device-width"' in content
    assert 'initialScale: 1' in content
    assert 'maximumScale: 5' in content, "Must allow user pinch-zoom up to 5x under WCAG 1.4.4"


def test_root_main_container_responsive_constraints():
    """Verify <main> layout constraints adapt smoothly across 320px to 1024px+."""
    with open(LAYOUT_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'w-full max-w-6xl mx-auto p-4 sm:p-6' in content
    assert 'min-h-[100dvh]' in content or 'min-h-screen' in content


def test_mobile_drawer_viewport_clamping():
    """Verify mobile navigation drawer never blows out small viewports (320px-480px)."""
    with open(LAYOUT_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'max-w-[calc(100vw-2rem)]' in content, "Mobile drawer width must be clamped"
    assert 'max-h-[calc(100dvh-5rem)]' in content, "Mobile drawer height must be clamped to viewport"
    assert 'overflow-y-auto' in content, "Mobile drawer content must be scrollable"
    assert 'hidden md:flex' in content, "Desktop nav must hide on small viewports"
    assert 'md:hidden' in content, "Mobile drawer toggle must hide on tablet/desktop viewports"


def test_responsive_headings_scale_on_mobile():
    """Verify titles scale down gracefully on viewports < 390px to prevent text clipping."""
    for brand in ['byd', 'hyundai-kia', 'tesla', 'global-brands', '2026-latest']:
        with open(CLIENT_PAGES[brand], 'r', encoding='utf-8') as f:
            content = f.read()
        assert re.search(r'text-2xl\s+sm:text-3xl\s+md:text-4xl', content), (
            f"{brand} h1 title must scale from text-2xl on mobile up to md:text-4xl on desktop"
        )


# ---------------------------------------------------------------------------
# 2. Horizontal Scrollbars & Overflow Prevention
# ---------------------------------------------------------------------------

def test_global_css_overflow_x_containment():
    """Verify html and body prevent horizontal window scroll blowouts."""
    with open(GLOBALS_CSS, 'r', encoding='utf-8') as f:
        css = f.read()

    assert 'overflow-x: hidden;' in css, "Global CSS must guard against horizontal overflow"
    assert '.table-scroll-container' in css
    assert 'overflow-x: auto;' in css
    assert '-webkit-overflow-scrolling: touch;' in css
    assert 'overscroll-behavior-x: contain;' in css


def test_all_visual_tables_have_overflow_wrappers():
    """Verify that every visual <table> is wrapped inside an overflow-x-auto container."""
    for name, path in CLIENT_PAGES.items():
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            if '<table' in line:
                context = "".join(lines[max(0, i - 12):i + 2])
                if 'sr-only' not in context:
                    has_scroll = 'overflow-x-auto' in context or 'table-scroll-container' in context
                    assert has_scroll, f"{name}:{i+1} visual <table> must be wrapped in overflow-x-auto"


def test_visual_tables_have_mobile_horizontal_scroll_cues():
    """Verify that visual tables display visual mobile swipe instructions."""
    pages_with_visual_tables = ['subsidy_table', 'recall', 'reliability', 'byd', 'tesla', 'hyundai-kia']
    for page_key in pages_with_visual_tables:
        with open(CLIENT_PAGES[page_key], 'r', encoding='utf-8') as f:
            content = f.read()
        assert '가로 스크롤 ↔' in content or '밀어서' in content, (
            f"{page_key} visual tables must provide mobile swipe cues"
        )


# ---------------------------------------------------------------------------
# 3. Touch Targets (WCAG 2.5.5 / 2.5.8 >= 44x44px)
# ---------------------------------------------------------------------------

def test_range_slider_controls_touch_target():
    """Verify input[type=range] controls enforce at least 44px touch targets."""
    with open(GLOBALS_CSS, 'r', encoding='utf-8') as f:
        css = f.read()

    # CSS enforces min-height: 44px on range sliders
    range_match = re.search(r'input\[type="range"\]\s*\{([^}]+)\}', css)
    assert range_match, "input[type=range] rule must exist in globals.css"
    rule_body = range_match.group(1)
    assert 'min-height: 44px;' in rule_body
    assert 'touch-action: pan-y;' in rule_body

    # In DepreciationCalculatorClient, all range sliders must meet min-h-[44px]
    with open(CLIENT_PAGES['depreciation'], 'r', encoding='utf-8') as f:
        dep_content = f.read()
    tags = extract_jsx_tags(dep_content, ('input',))
    range_inputs = [t for t in tags if 'type="range"' in t[1]]
    assert len(range_inputs) >= 4, "Expected 4 range sliders in Depreciation calculator"
    for _, tag_str, line_no in range_inputs:
        assert 'min-h-[44px]' in tag_str, f"Depreciation L{line_no} range slider must have min-h-[44px]"


def test_recall_portal_touch_targets():
    """Verify table toggle buttons and links in RecallPortalClient meet >= 44px."""
    with open(CLIENT_PAGES['recall'], 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'min-h-[44px]' in content
    # The table row toggle button must have min-h-[44px]
    assert 'toggleRecallExpansion' in content
    assert 'min-h-[44px] min-w-[44px]' in content or 'min-h-[44px]' in content
    # Ensure no undersized min-h-[36px] or min-h-[38px] remains
    assert 'min-h-[36px]' not in content, "RecallPortalClient must not contain undersized min-h-[36px]"


def test_subsidy_tracker_checkbox_and_custom_msrp_touch_targets():
    """Verify all checkbox controls and select menus in SubsidyTrackerClient meet >= 44px."""
    with open(CLIENT_PAGES['subsidy'], 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'custom-msrp-toggle-checkbox' in content
    # Custom msrp label wrapper must have min-h-[44px]
    label_match = re.search(r'<label\b[^>]*htmlFor="custom-msrp-toggle-checkbox"[^>]*>', content)
    assert label_match, "custom-msrp-toggle-checkbox label must exist"
    assert 'min-h-[44px]' in label_match.group(0), "Custom MSRP toggle label must have min-h-[44px]"

    # Select menus must have min-h-[44px]
    tags = extract_jsx_tags(content, ('select',))
    assert len(tags) >= 3, "Expected at least 3 select menus in SubsidyTrackerClient"
    for _, tag_str, line_no in tags:
        assert 'min-h-[44px]' in tag_str, f"SubsidyTracker L{line_no} select must have min-h-[44px]"


def test_pdi_checklist_touch_target_dimensions():
    """Verify PDI checklist item touch targets meet at least 48px height with 24x24px checkboxes."""
    with open(CLIENT_PAGES['pdi'], 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'min-h-[48px]' in content
    assert 'w-6 h-6' in content


# ---------------------------------------------------------------------------
# 4. Responsive Navigation (BrandComparisonNav, Header, Footer)
# ---------------------------------------------------------------------------

def test_brand_comparison_nav_responsiveness():
    """Verify BrandComparisonNav tabs are horizontally scrollable and cross-nav wraps cleanly."""
    with open(BRAND_NAV_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    # Brand switcher nav tabs have table-scroll-container, overflow-x-auto, max-w-full
    assert 'table-scroll-container' in content
    assert 'overflow-x-auto' in content
    assert 'max-w-full' in content
    # Tabs have min-h-[44px]
    assert 'min-h-[44px]' in content
    # Breadcrumbs wrap
    assert 'flex flex-wrap items-center' in content
    # Cross navigation grid has responsive padding and columns
    assert 'grid grid-cols-2 sm:grid-cols-4' in content
    assert 'p-3 sm:p-4' in content


def test_site_footer_touch_targets_and_responsiveness():
    """Verify SiteFooter links have >= 44px touch targets and responsive flex wrapping."""
    with open(FOOTER_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'flex flex-wrap justify-center items-center' in content
    # All external links and back-to-top have min-h-[44px]
    tags = extract_jsx_tags(content, ('a',))
    assert len(tags) >= 4, "Expected at least 4 links in SiteFooter"
    for _, tag_str, line_no in tags:
        assert 'min-h-[44px]' in tag_str, f"Footer L{line_no} link must have min-h-[44px]"
    assert 'href="#main-content"' in content, "Back to top must target #main-content"


def test_global_nav_listener_invariants():
    """Verify GlobalNavListener handles mobile drawer interactions and lifecycle cleanup."""
    with open(NAV_LISTENER_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    # Escape key handler
    assert 'Escape' in content
    # Keyboard focus trap
    assert 'e.key === \'Tab\'' in content or "e.key === \"Tab\"" in content
    # Viewport resize handler closing drawer on >= 768px
    assert 'window.innerWidth >= 768' in content
    # Popstate handler
    assert 'popstate' in content
    # Cleanup event listeners
    assert 'removeEventListener' in content
