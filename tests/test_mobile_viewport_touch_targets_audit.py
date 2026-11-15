"""
Audit Test Suite: Mobile Viewport, Touch Targets, and Responsive CSS
Verifies:
1. Viewport meta tag configuration (width, scale, viewportFit='cover') and safe-area support.
2. Minimum interactive touch targets (>= 44x44px for buttons, links, inputs).
3. High DPI / Retina display media queries and small mobile screen (<390px) typography scaling.
4. Horizontal scroll container presence and overflow-x prevention.
"""

import os
import re
import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(BASE_DIR, "src")


def test_viewport_meta_tag_configuration():
    """Verify viewport configuration in layout.tsx includes viewportFit: 'cover'."""
    layout_path = os.path.join(SRC_DIR, "app", "layout.tsx")
    assert os.path.exists(layout_path), "layout.tsx must exist"
    
    with open(layout_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "export const viewport: Viewport" in content
    assert 'viewportFit: "cover"' in content or "viewportFit: 'cover'" in content
    assert 'width: "device-width"' in content or "width: 'device-width'" in content
    assert "themeColor:" in content
    assert "initialScale: 1" in content


def test_globals_css_safe_area_and_ios_zoom_prevention():
    """Verify globals.css contains safe area insets and iOS zoom prevention."""
    css_path = os.path.join(SRC_DIR, "app", "globals.css")
    assert os.path.exists(css_path), "globals.css must exist"

    with open(css_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Safe-area insets support
    assert "env(safe-area-inset-top" in content
    assert "env(safe-area-inset-bottom" in content
    assert "env(safe-area-inset-left" in content
    assert "env(safe-area-inset-right" in content

    # Sticky header safe area
    assert 'header[role="banner"]' in content
    # Contentinfo footer safe area
    assert 'footer[role="contentinfo"]' in content

    # iOS Safari auto-zoom prevention (< 640px inputs font-size: 16px)
    assert "font-size: 16px !important" in content

    # High DPI / Retina media query
    assert "min-resolution: 192dpi" in content or "-webkit-min-device-pixel-ratio: 2" in content
    assert "shape-rendering: geometricPrecision" in content

    # Ultra-compact screen readability (< 390px)
    assert "max-width: 389px" in content


def test_tailwind_config_mobile_screens():
    """Verify tailwind.config.ts defines xs and xxs mobile breakpoints."""
    tailwind_path = os.path.join(BASE_DIR, "tailwind.config.ts")
    assert os.path.exists(tailwind_path), "tailwind.config.ts must exist"

    with open(tailwind_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "'xs': '375px'" in content or '"xs": "375px"' in content
    assert "'xxs': '320px'" in content or '"xxs": "320px"' in content


def test_touch_target_dimensions_in_client_components():
    """Verify key interactive buttons and inputs meet min-h-[44px] touch target requirements."""
    # 1. ReliabilityDashboardClient
    reliability_path = os.path.join(SRC_DIR, "app", "reliability-analytics", "ReliabilityDashboardClient.tsx")
    with open(reliability_path, "r", encoding="utf-8") as f:
        rel_content = f.read()

    # SVG hover button must be min-h-[44px], not 36px
    assert "min-h-[36px]" not in rel_content
    # Head-to-head filter buttons must have min-h-[44px]
    assert "모델 목록 필터링 &rarr;</button>" not in rel_content  # without class
    assert "min-h-[44px] inline-flex items-center px-2.5 py-1.5" in rel_content

    # 2. DepreciationCalculatorClient
    deprec_path = os.path.join(SRC_DIR, "app", "depreciation-calculator", "DepreciationCalculatorClient.tsx")
    with open(deprec_path, "r", encoding="utf-8") as f:
        deprec_content = f.read()
    assert "p-3.5 min-h-[44px] rounded-xl" in deprec_content

    # 3. RecallPortalClient
    recall_path = os.path.join(SRC_DIR, "app", "recall-portal", "RecallPortalClient.tsx")
    with open(recall_path, "r", encoding="utf-8") as f:
        recall_content = f.read()
    assert "px-4 py-3.5 min-h-[44px] text-base" in recall_content

    # 4. Skip navigation links in layout and subsidy-tracker
    layout_path = os.path.join(SRC_DIR, "app", "layout.tsx")
    with open(layout_path, "r", encoding="utf-8") as f:
        layout_content = f.read()
    assert "focus:min-h-[44px]" in layout_content

    subsidy_path = os.path.join(SRC_DIR, "app", "subsidy-tracker", "SubsidyTrackerClient.tsx")
    with open(subsidy_path, "r", encoding="utf-8") as f:
        subsidy_content = f.read()
    assert "focus:min-h-[44px]" in subsidy_content


def test_overflow_and_scroll_container_styling():
    """Verify html, body have overflow-x: hidden and tables have table-scroll-container."""
    css_path = os.path.join(SRC_DIR, "app", "globals.css")
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()

    assert "overflow-x: hidden" in css
    assert ".table-scroll-container" in css
    assert "-webkit-overflow-scrolling: touch" in css
    assert "overscroll-behavior-x: contain" in css
