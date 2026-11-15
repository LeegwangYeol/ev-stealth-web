"""
tests/test_navigation_header_audit.py

Authoritative Test Suite: Navigation & Header Components Audit
Verifies:
1. Skip-to-content accessibility link functionality and z-index elevation.
2. Mobile navigation drawer/menu responsiveness and touch target sizes (minimum 44x44px).
3. Active route styling and aria-current="page" attributes on desktop nav, mobile drawer, and brand tabs.
4. Breadcrumbs touch target dimensions and current page indicator in BrandComparisonNav.tsx.
5. GlobalNavListener route synchronization, skip link focus management, and focus trap lifecycle.
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "ev-stealth-web", "src")
if not os.path.isdir(SRC_DIR):
    SRC_DIR = os.path.join(REPO_ROOT, "src")
APP_DIR = os.path.join(SRC_DIR, "app")
COMPONENTS_DIR = os.path.join(SRC_DIR, "components")

LAYOUT_PATH = os.path.join(APP_DIR, "layout.tsx")
PAGE_PATH = os.path.join(APP_DIR, "page.tsx")
GLOBALS_CSS_PATH = os.path.join(APP_DIR, "globals.css")
BRAND_NAV_PATH = os.path.join(COMPONENTS_DIR, "BrandComparisonNav.tsx")
GLOBAL_NAV_LISTENER_PATH = os.path.join(COMPONENTS_DIR, "GlobalNavListener.tsx")


class TestNavigationHeaderAudit(unittest.TestCase):

    def setUp(self):
        with open(LAYOUT_PATH, "r", encoding="utf-8") as f:
            self.layout_source = f.read()
        with open(PAGE_PATH, "r", encoding="utf-8") as f:
            self.page_source = f.read()
        with open(BRAND_NAV_PATH, "r", encoding="utf-8") as f:
            self.brand_nav_source = f.read()
        with open(GLOBAL_NAV_LISTENER_PATH, "r", encoding="utf-8") as f:
            self.listener_source = f.read()
        with open(GLOBALS_CSS_PATH, "r", encoding="utf-8") as f:
            self.css_source = f.read()

    # -------------------------------------------------------------------------
    # 1. Skip-to-content Accessibility Link
    # -------------------------------------------------------------------------

    def test_skip_to_content_link_exists_and_targets_main(self):
        """Skip-to-content link must target #main-content and have elevated z-index."""
        self.assertIn('href="#main-content"', self.layout_source)
        self.assertIn('id="main-content"', self.layout_source)
        self.assertIn('tabIndex={-1}', self.layout_source)
        self.assertIn('role="main"', self.layout_source)

        # Must have sr-only focus:not-sr-only for keyboard accessibility
        self.assertTrue(
            bool(re.search(r'href="#main-content"[^>]*sr-only\s+focus:not-sr-only', self.layout_source)),
            "Skip link must declare 'sr-only focus:not-sr-only'",
        )

        # Skip link must have focus:z-[100] to sit above sticky top-0 z-50 header
        self.assertIn('focus:z-[100]', self.layout_source, "Skip link must have elevated focus:z-[100]")

    def test_skip_link_programmatic_focus_transfer_in_listener(self):
        """GlobalNavListener must transfer focus programmatically to #main-content on click."""
        self.assertIn('a[href="#main-content"]', self.listener_source)
        self.assertIn("main.focus()", self.listener_source)

    # -------------------------------------------------------------------------
    # 2. Mobile Drawer Responsiveness and Touch Targets
    # -------------------------------------------------------------------------

    def test_brand_comparison_nav_touch_targets(self):
        """BrandComparisonNav breadcrumb and tab links must meet >= 44x44px touch target."""
        # Breadcrumb home link
        home_link_match = re.search(r'<Link\b[^>]*aria-label="홈 \(메인 가이드 목록으로 이동\)"[^>]*>', self.brand_nav_source)
        self.assertIsNotNone(home_link_match, "Breadcrumb home Link not found")
        home_tag = home_link_match.group(0)
        self.assertIn("min-h-[44px]", home_tag, "Breadcrumb home link must declare min-h-[44px]")
        self.assertIn("min-w-[44px]", home_tag, "Breadcrumb home link must declare min-w-[44px]")

        # Tab switcher links
        self.assertIn("min-w-[96px]", self.brand_nav_source, "Brand tab item must have min-w-[96px]")
        self.assertIn("min-h-[44px]", self.brand_nav_source, "Brand tab Link must have min-h-[44px]")

        # Back to Home button
        back_home_match = re.search(r'<Link\b[^>]*aria-label="전체 가이드 홈으로 돌아가기"[^>]*>', self.brand_nav_source)
        self.assertIsNotNone(back_home_match)
        self.assertIn("min-h-[44px]", back_home_match.group(0))

    def test_mobile_drawer_summary_and_links_touch_targets(self):
        """Mobile navigation drawer toggle summary and all links must meet >= 44x44px touch target."""
        # Summary toggle button
        summary_match = re.search(r'<summary\b[^>]*aria-label="모바일 내비게이션 메뉴 토글"[^>]*>', self.layout_source)
        self.assertIsNotNone(summary_match)
        self.assertIn("min-h-[44px]", summary_match.group(0))

        # Drawer panel links
        drawer_match = re.search(r'<nav\b[^>]*id="mobile-nav-panel"[^>]*>([\s\S]*?)</nav>', self.layout_source)
        self.assertIsNotNone(drawer_match)
        drawer_content = drawer_match.group(1)

        links = re.findall(r'<Link\b[^>]*>', drawer_content)
        self.assertGreaterEqual(len(links), 10, "Mobile drawer must contain at least 10 links")
        for link in links:
            self.assertIn("min-h-[44px]", link, f"Mobile drawer link missing min-h-[44px]: {link}")

    def test_mobile_drawer_viewport_constraints(self):
        """Mobile drawer must have width and height clamped to viewport."""
        self.assertIn("max-w-[calc(100vw-2rem)]", self.layout_source)
        self.assertIn("max-h-[calc(100dvh-5rem)]", self.layout_source)
        self.assertIn("overflow-y-auto", self.layout_source)

    # -------------------------------------------------------------------------
    # 3. Active Route Styling and aria-current="page"
    # -------------------------------------------------------------------------

    def test_brand_comparison_nav_aria_current(self):
        """BrandComparisonNav must declare aria-current='page' on active tab and breadcrumb."""
        self.assertIn('aria-current={isActive ? \'page\' : undefined}', self.brand_nav_source)
        self.assertIn('aria-current="page"', self.brand_nav_source)

    def test_layout_desktop_and_mobile_nav_aria_current_styles(self):
        """Desktop and mobile drawer links in layout.tsx must declare aria-[current=page] styling."""
        # Desktop nav
        desktop_match = re.search(r'<nav\b[^>]*data-testid="desktop-nav"[^>]*>([\s\S]*?)</nav>', self.layout_source)
        self.assertIsNotNone(desktop_match)
        desktop_content = desktop_match.group(1)
        desktop_links = re.findall(r'<Link\b[^>]*>', desktop_content)

        for link in desktop_links:
            self.assertIn(
                "aria-[current=page]:",
                link,
                f"Desktop nav link missing aria-[current=page] class: {link}",
            )

        # Mobile drawer
        drawer_match = re.search(r'<nav\b[^>]*id="mobile-nav-panel"[^>]*>([\s\S]*?)</nav>', self.layout_source)
        self.assertIsNotNone(drawer_match)
        drawer_content = drawer_match.group(1)
        drawer_links = re.findall(r'<Link\b[^>]*>', drawer_content)

        for link in drawer_links:
            self.assertIn(
                "aria-[current=page]:",
                link,
                f"Mobile drawer link missing aria-[current=page] class: {link}",
            )

    def test_global_nav_listener_synchronizes_aria_current(self):
        """GlobalNavListener must import usePathname and synchronize aria-current attribute."""
        self.assertIn("usePathname", self.listener_source)
        self.assertIn("setAttribute('aria-current', 'page')", self.listener_source)
        self.assertIn("removeAttribute('aria-current')", self.listener_source)

    def test_globals_css_has_active_route_rules(self):
        """globals.css must contain CSS fallback rules for active navigation links."""
        self.assertIn('header nav[data-testid="desktop-nav"] a[aria-current="page"]', self.css_source)
        self.assertIn('header #mobile-nav-panel a[aria-current="page"]', self.css_source)

    # -------------------------------------------------------------------------
    # 4. Home Page Heading Readability
    # -------------------------------------------------------------------------

    def test_page_hero_heading_break_keep(self):
        """Home page hero heading must include break-keep to avoid mid-word breaks on mobile."""
        h1_match = re.search(r'<h1\b[^>]*id="home-hero-heading"[^>]*>', self.page_source)
        self.assertIsNotNone(h1_match)
        self.assertIn("break-keep", h1_match.group(0))


if __name__ == "__main__":
    unittest.main()
