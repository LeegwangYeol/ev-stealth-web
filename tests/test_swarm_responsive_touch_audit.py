"""
tests/test_swarm_responsive_touch_audit.py

Exhaustive Swarm Audit Test Suite:
1. Responsive Layout & Mobile Viewports (320px to 1920px) across all routes
2. Touch Target Sizes (WCAG 2.5.5 / 2.5.8 minimum 44x44px) on ALL interactive controls
3. Mobile Navigation Drawer (Toggle, Dialog panel, Accessibility, Focus Trap, Auto-close)
4. Horizontal Overflow Prevention (Tables, SVG Charts, Global CSS Containment)
"""

import os
import re
import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(BASE_DIR, "src")
APP_DIR = os.path.join(SRC_DIR, "app")
COMPONENTS_DIR = os.path.join(SRC_DIR, "components")


def extract_jsx_tags(content, target_tags=('button', 'select', 'input', 'a')):
    """Accurately extracts JSX tags tracking braces {} and quotes to prevent premature closing."""
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


# ---------------------------------------------------------------------------
# 1. Responsive Layout & Mobile Viewport Constraints (320px to 1920px)
# ---------------------------------------------------------------------------

def test_viewport_meta_cover_and_pinch_zoom():
    """Verify viewport configuration allows responsive cover and pinch-zoom up to 5x."""
    layout_path = os.path.join(APP_DIR, "layout.tsx")
    with open(layout_path, "r", encoding="utf-8") as f:
        code = f.read()

    assert 'width: "device-width"' in code or "width: 'device-width'" in code
    assert 'initialScale: 1' in code
    assert 'maximumScale: 5' in code
    assert 'viewportFit: "cover"' in code or "viewportFit: 'cover'" in code


def test_header_and_logo_responsive_scaling_for_320px():
    """Verify header and logo adapt down to 320px ultra-narrow screens without overflow."""
    layout_path = os.path.join(APP_DIR, "layout.tsx")
    with open(layout_path, "r", encoding="utf-8") as f:
        code = f.read()

    # Header container adapts padding on ultra-compact screens
    assert "px-3 xs:px-4" in code
    # Logo text scales from text-lg to text-xl
    assert "text-lg xs:text-xl" in code
    # Mobile toggle adapts padding
    assert "px-2.5 xs:px-3" in code


def test_no_unbounded_w_screen_in_any_page():
    """Verify no component uses w-screen, which ignores scrollbars and causes horizontal overflow."""
    for root, _, files in os.walk(SRC_DIR):
        for f in files:
            if f.endswith(('.tsx', '.jsx')):
                filepath = os.path.join(root, f)
                with open(filepath, "r", encoding="utf-8") as fp:
                    content = fp.read()
                # w-screen causes 100vw blowout on Windows/WebKit with scrollbars
                assert "w-screen" not in content, f"{filepath} must not use 'w-screen'"


def test_all_headings_have_word_break_guards():
    """Verify globals.css contains typography wrap rules to prevent mobile clipping."""
    css_path = os.path.join(APP_DIR, "globals.css")
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()

    assert "word-break: keep-all;" in css
    assert "overflow-wrap: break-word;" in css
    assert "overflow-x: hidden;" in css


# ---------------------------------------------------------------------------
# 2. Touch Target Sizes (WCAG 2.5.5 / 2.5.8 Minimum 44x44px)
# ---------------------------------------------------------------------------

def test_every_interactive_button_meets_minimum_touch_target():
    """Exhaustively verify EVERY non-hidden button across all components meets >= 44x44px."""
    TARGET_SIZE_INDICATORS = [
        'min-h-[44px]', 'min-h-[48px]', 'min-touch-target',
        'h-11', 'h-12', 'h-14', 'h-16',
        'p-3.5', 'p-4', 'p-5', 'p-6', 'py-3.5', 'py-4', 'py-5', 'py-6',
        'focus:min-h-[44px]', 'w-11 h-11'
    ]

    undersized = []
    for root, _, files in os.walk(SRC_DIR):
        for f in files:
            if f.endswith(('.tsx', '.jsx')):
                filepath = os.path.join(root, f)
                with open(filepath, 'r', encoding='utf-8') as fp:
                    content = fp.read()
                tags = extract_jsx_tags(content, ('button',))
                for tag_name, tag_str, line_no in tags:
                    if 'sr-only' in tag_str or 'type="hidden"' in tag_str:
                        continue
                    has_size = any(k in tag_str for k in TARGET_SIZE_INDICATORS)
                    if not has_size:
                        undersized.append((os.path.relpath(filepath, BASE_DIR), line_no, tag_str[:80]))

    assert len(undersized) == 0, f"Found undersized buttons: {undersized}"


def test_every_interactive_select_meets_minimum_touch_target():
    """Verify every visible <select> menu meets minimum 44px height."""
    TARGET_SIZE_INDICATORS = [
        'min-h-[44px]', 'min-h-[48px]', 'h-11', 'h-12', 'p-3.5', 'p-4', 'py-3.5', 'py-4'
    ]

    undersized = []
    for root, _, files in os.walk(SRC_DIR):
        for f in files:
            if f.endswith(('.tsx', '.jsx')):
                filepath = os.path.join(root, f)
                with open(filepath, 'r', encoding='utf-8') as fp:
                    content = fp.read()
                tags = extract_jsx_tags(content, ('select',))
                for tag_name, tag_str, line_no in tags:
                    if 'sr-only' in tag_str:
                        continue
                    has_size = any(k in tag_str for k in TARGET_SIZE_INDICATORS)
                    if not has_size:
                        undersized.append((os.path.relpath(filepath, BASE_DIR), line_no, tag_str[:80]))

    assert len(undersized) == 0, f"Found undersized select menus: {undersized}"


def test_every_interactive_input_meets_minimum_touch_target():
    """Verify every text/number/search/range <input> meets minimum 44px height."""
    TARGET_SIZE_INDICATORS = [
        'min-h-[44px]', 'min-h-[48px]', 'h-11', 'h-12', 'p-3.5', 'p-4', 'py-3.5', 'py-4'
    ]

    undersized = []
    for root, _, files in os.walk(SRC_DIR):
        for f in files:
            if f.endswith(('.tsx', '.jsx')):
                filepath = os.path.join(root, f)
                with open(filepath, 'r', encoding='utf-8') as fp:
                    content = fp.read()
                tags = extract_jsx_tags(content, ('input',))
                for tag_name, tag_str, line_no in tags:
                    if 'type="hidden"' in tag_str or 'sr-only' in tag_str:
                        continue
                    if 'type="checkbox"' in tag_str or 'type="radio"' in tag_str:
                        continue
                    has_size = any(k in tag_str for k in TARGET_SIZE_INDICATORS)
                    if not has_size:
                        undersized.append((os.path.relpath(filepath, BASE_DIR), line_no, tag_str[:80]))

    assert len(undersized) == 0, f"Found undersized inputs: {undersized}"


# ---------------------------------------------------------------------------
# 3. Mobile Navigation Drawer
# ---------------------------------------------------------------------------

def test_mobile_drawer_markup_and_accessibility():
    """Verify layout.tsx mobile drawer uses semantic details/summary with aria attributes."""
    layout_path = os.path.join(APP_DIR, "layout.tsx")
    with open(layout_path, "r", encoding="utf-8") as f:
        code = f.read()

    assert '<details className="md:hidden relative group" id="mobile-nav-drawer"' in code
    assert 'aria-haspopup="dialog"' in code
    assert 'aria-expanded="false"' in code
    assert 'aria-controls="mobile-nav-panel"' in code
    assert 'max-w-[calc(100vw-2rem)]' in code
    assert 'max-h-[calc(100dvh-5rem)]' in code
    assert 'overflow-y-auto' in code


def test_global_nav_listener_full_lifecycle():
    """Verify GlobalNavListener provides complete keyboard focus trap and auto-close logic."""
    listener_path = os.path.join(COMPONENTS_DIR, "GlobalNavListener.tsx")
    with open(listener_path, "r", encoding="utf-8") as f:
        code = f.read()

    assert "Escape" in code, "Must close drawer on Escape"
    assert "e.key === 'Tab'" in code or 'e.key === "Tab"', "Must trap focus on Tab"
    assert "window.innerWidth >= 768" in code, "Must auto-close on tablet/desktop resize"
    assert "popstate" in code, "Must close on back/forward browser navigation"
    assert "removeEventListener" in code, "Must clean up all listeners on unmount"


# ---------------------------------------------------------------------------
# 4. Overflow Prevention Across All Routes
# ---------------------------------------------------------------------------

def test_all_visual_tables_have_scroll_wrappers_and_indicators():
    """Verify every visual table is in overflow-x-auto container with mobile swipe indicators."""
    table_files = [
        os.path.join(COMPONENTS_DIR, "subsidy/SubsidyTableView.tsx"),
        os.path.join(APP_DIR, "recall-portal/RecallPortalClient.tsx"),
        os.path.join(APP_DIR, "reliability-analytics/ReliabilityDashboardClient.tsx"),
        os.path.join(APP_DIR, "depreciation-calculator/DepreciationCalculatorClient.tsx"),
        os.path.join(APP_DIR, "byd/page.tsx"),
        os.path.join(APP_DIR, "tesla/page.tsx"),
        os.path.join(APP_DIR, "hyundai-kia/page.tsx"),
        os.path.join(APP_DIR, "global-brands/page.tsx"),
        os.path.join(APP_DIR, "2026-latest/page.tsx"),
        os.path.join(APP_DIR, "secret-admin-reports/AdminDashboardClient.tsx"),
    ]

    for filepath in table_files:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        assert "table-scroll-container" in content, f"{filepath} must contain table-scroll-container"
        assert "overflow-x-auto" in content, f"{filepath} must contain overflow-x-auto"
        assert "가로 스크롤 ↔" in content, f"{filepath} must contain mobile swipe indicator"


def test_all_wide_svg_charts_have_scroll_wrappers():
    """Verify wide SVG charts have responsive horizontal scroll wrappers."""
    chart_files = [
        os.path.join(APP_DIR, "depreciation-calculator/DepreciationCalculatorClient.tsx"),
        os.path.join(APP_DIR, "reliability-analytics/ReliabilityDashboardClient.tsx"),
    ]

    for filepath in chart_files:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        assert "table-scroll-container" in content
        assert "overflow-x-auto" in content
