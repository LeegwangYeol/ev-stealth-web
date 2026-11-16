import unittest
import os
import re

class TestBrandComparisonPagesAudit(unittest.TestCase):
    """
    Automated audit for the EV stealth web brand comparison pages:
    - /tesla
    - /byd
    - /hyundai-kia
    - /global-brands
    - /2026-latest
    """

    @classmethod
    def setUpClass(cls):
        cls.repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_candidates = [
            os.path.join(cls.repo_root, "ev-stealth-web", "src", "app"),
            os.path.join(cls.repo_root, "src", "app"),
        ]
        cls.app_dir = next((p for p in app_candidates if os.path.isdir(p)), None)
        assert cls.app_dir, "Could not locate Next.js app directory"

        cls.brand_routes = [
            "tesla",
            "byd",
            "hyundai-kia",
            "global-brands",
            "2026-latest",
        ]

    def test_brand_pages_contain_brand_nav_and_cross_nav(self):
        """Every brand page must render BrandComparisonNav and OtherBrandsCrossNav."""
        for route in self.brand_routes:
            page_path = os.path.join(self.app_dir, route, "page.tsx")
            self.assertTrue(os.path.isfile(page_path), f"Page {page_path} missing")
            with open(page_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("BrandComparisonNav", content, f"{route} missing BrandComparisonNav")
            self.assertIn("OtherBrandsCrossNav", content, f"{route} missing OtherBrandsCrossNav")
            self.assertIn(f'currentBrand="{route}"', content, f"{route} missing currentBrand prop")

    def test_brand_pages_heading_hierarchy(self):
        """Every brand page must have exactly one h1 and valid h2 and h3 structure."""
        for route in self.brand_routes:
            page_path = os.path.join(self.app_dir, route, "page.tsx")
            with open(page_path, "r", encoding="utf-8") as f:
                content = f.read()

            h1_matches = re.findall(r'<h1\b[^>]*>(.*?)</h1>', content, re.DOTALL)
            self.assertEqual(len(h1_matches), 1, f"{route} must have exactly one <h1>")

            h2_matches = re.findall(r'<h2\b[^>]*>(.*?)</h2>', content, re.DOTALL)
            self.assertGreaterEqual(len(h2_matches), 2, f"{route} must have at least 2 <h2> sections")

            h3_matches = re.findall(r'<h3\b[^>]*>(.*?)</h3>', content, re.DOTALL)
            self.assertGreaterEqual(len(h3_matches), 2, f"{route} must have <h3> headings for subsections/tools")

    def test_brand_pages_wcag_badge_colors(self):
        """Badge headings must use high-contrast text color classes (> 8:1 contrast)."""
        for route in self.brand_routes:
            page_path = os.path.join(self.app_dir, route, "page.tsx")
            with open(page_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Ensure avoiding low-contrast text-yellow-800 or text-red-700 in badge headings
            self.assertNotIn("text-yellow-800", content, f"{route} should use text-amber-900 instead of text-yellow-800")
            if "bg-yellow-50" in content:
                self.assertIn("text-amber-900", content, f"{route} yellow callouts must use text-amber-900")
            if "bg-red-50" in content:
                self.assertIn("text-red-900", content, f"{route} red callouts must use text-red-900")
            if "bg-green-50" in content:
                self.assertIn("text-green-900", content, f"{route} green callouts must use text-green-900")

    def test_no_dead_internal_links(self):
        """Verify that all internal hrefs in brand pages link to existing routes."""
        valid_routes = {
            "/",
            "/tesla",
            "/byd",
            "/hyundai-kia",
            "/global-brands",
            "/2026-latest",
            "/depreciation-calculator",
            "/reliability-analytics",
            "/recall-portal",
            "/subsidy-tracker",
            "/pdi-checklist",
            "/secret-admin-reports",
        }

        for route in self.brand_routes:
            page_path = os.path.join(self.app_dir, route, "page.tsx")
            with open(page_path, "r", encoding="utf-8") as f:
                content = f.read()

            internal_hrefs = re.findall(r'href=["\'](/[^"\']*)["\']', content)
            for href in internal_hrefs:
                # Strip query params like ?brand=tesla
                base_href = href.split("?")[0]
                self.assertIn(
                    base_href,
                    valid_routes,
                    f"Dead link detected in {route}: '{href}' (base: '{base_href}')",
                )

    def test_brand_pages_loading_skeletons_responsive_padding(self):
        """Loading skeletons must include responsive sm:py-10 padding matching the page."""
        for route in self.brand_routes:
            loading_path = os.path.join(self.app_dir, route, "loading.tsx")
            self.assertTrue(os.path.isfile(loading_path), f"{route}/loading.tsx missing")
            with open(loading_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("sm:py-10", content, f"{route}/loading.tsx missing responsive sm:py-10")
            self.assertIn("animate-pulse", content)
            self.assertIn('role="status"', content)

    def test_brand_pages_error_boundaries_resilience(self):
        """Error boundaries must declare use client, role=alert, aria-live=assertive, reset, and home link."""
        for route in self.brand_routes:
            error_path = os.path.join(self.app_dir, route, "error.tsx")
            self.assertTrue(os.path.isfile(error_path), f"{route}/error.tsx missing")
            with open(error_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertTrue(content.startswith("'use client'") or content.startswith('"use client"'))
            self.assertIn('role="alert"', content)
            self.assertIn('aria-live="assertive"', content)
            self.assertIn("reset()", content)
            self.assertIn("href=\"/\"", content)

    def test_brand_pages_table_keyboard_accessibility(self):
        """All brand summary tables must have keyboard-scrollable containers (WCAG 2.1.1 & 2.4.7)."""
        for route in self.brand_routes:
            page_path = os.path.join(self.app_dir, route, "page.tsx")
            with open(page_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("tabIndex={0}", content, f"{route} table container missing tabIndex={{0}} for keyboard scrollability")
            self.assertIn('role="region"', content, f"{route} table container missing role=\"region\"")
            self.assertIn("focus-visible:", content, f"{route} table container missing focus-visible outline indicator")
            self.assertIn("table-scroll-container", content, f"{route} missing table-scroll-container class")

    def test_brand_comparison_nav_cross_nav_accessibility_and_badges(self):
        """BrandComparisonNav must maintain accessible headings and render brand badges in cross-nav."""
        nav_path = os.path.join(os.path.dirname(self.app_dir), "components", "BrandComparisonNav.tsx")
        self.assertTrue(os.path.isfile(nav_path), f"BrandComparisonNav not found at {nav_path}")
        with open(nav_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn('id="heading-other-brands"', content, "OtherBrandsCrossNav missing id for heading")
        self.assertIn('aria-labelledby="heading-other-brands"', content, "OtherBrandsCrossNav missing aria-labelledby linking heading")
        self.assertIn("brand.badge", content, "OtherBrandsCrossNav must render brand badges")

    def test_json_ld_schemas_completeness_and_breadcrumbs(self):
        """All brand pages must define comprehensive JSON-LD graphs including Article, Vehicle, ItemList, FAQPage, BreadcrumbList."""
        for route in self.brand_routes:
            page_path = os.path.join(self.app_dir, route, "page.tsx")
            with open(page_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("<JsonLd", content, f"{route} missing <JsonLd component")
            self.assertIn("'@type': 'Article'", content, f"{route} JSON-LD missing Article")
            self.assertIn("'@type': 'Vehicle'", content, f"{route} JSON-LD missing Vehicle")
            self.assertIn("'@type': 'ItemList'", content, f"{route} JSON-LD missing ItemList")
            self.assertIn("'@type': 'FAQPage'", content, f"{route} JSON-LD missing FAQPage")
            self.assertIn("'@type': 'BreadcrumbList'", content, f"{route} JSON-LD missing BreadcrumbList")

            # Check that BreadcrumbList contains root and route
            self.assertIn("name: '홈'", content, f"{route} BreadcrumbList missing '홈'")
            self.assertIn("SITE_URL", content, f"{route} BreadcrumbList missing SITE_URL")

    def test_responsive_tables_mobile_guidance_and_scope(self):
        """Summary tables must include mobile scroll guidance, table caption, scope attributes, and min-width."""
        for route in self.brand_routes:
            page_path = os.path.join(self.app_dir, route, "page.tsx")
            with open(page_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("<caption", content, f"{route} summary table missing <caption> for screen readers")
            self.assertIn('scope="col"', content, f"{route} table headers missing scope=\"col\"")
            self.assertIn('scope="row"', content, f"{route} row headers missing scope=\"row\"")
            self.assertIn("min-w-[640px]", content, f"{route} table missing min-w-[640px] responsive guard")
            self.assertIn("sm:hidden", content, f"{route} table missing mobile horizontal scroll visual hint")
            self.assertIn("가로 스크롤", content, f"{route} table missing horizontal scroll Korean badge")

    def test_model_spec_warranty_cards_integration(self):
        """All brand pages must render ModelSpecWarrantyCard for key models with battery specs and warranty."""
        for route in self.brand_routes:
            page_path = os.path.join(self.app_dir, route, "page.tsx")
            with open(page_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("<ModelSpecWarrantyCard", content, f"{route} missing ModelSpecWarrantyCard")
            self.assertIn("batterySpecs={{", content, f"{route} ModelSpecWarrantyCard missing batterySpecs")
            self.assertIn("warranty={{", content, f"{route} ModelSpecWarrantyCard missing warranty")

    def test_touch_target_accessibility_in_tables_and_nav(self):
        """Interactive table links and breadcrumb navigation must satisfy >= 44px touch targets."""
        for route in self.brand_routes:
            page_path = os.path.join(self.app_dir, route, "page.tsx")
            with open(page_path, "r", encoding="utf-8") as f:
                content = f.read()

            # External table links must have min-h-[44px]
            self.assertIn("min-h-[44px]", content, f"{route} table links must have min-h-[44px]")


if __name__ == "__main__":
    unittest.main()
