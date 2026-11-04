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


if __name__ == "__main__":
    unittest.main()
