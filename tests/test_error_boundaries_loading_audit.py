import os
import re
import unittest
from pathlib import Path

p_dir = Path(__file__).resolve().parent
if p_dir.parent.name == "ev-stealth-web":
    BASE_DIR = p_dir.parent.parent
    APP_DIR = p_dir.parent / "src" / "app"
else:
    BASE_DIR = p_dir.parent
    APP_DIR = BASE_DIR / "ev-stealth-web" / "src" / "app"

ROUTES = [
    "",
    "2026-latest",
    "byd",
    "depreciation-calculator",
    "global-brands",
    "hyundai-kia",
    "pdi-checklist",
    "recall-portal",
    "reliability-analytics",
    "secret-admin-reports",
    "subsidy-tracker",
    "tesla",
]


class TestErrorBoundariesAndLoadingAudit(unittest.TestCase):
    """Rigorous verification suite for Next.js App Router error boundaries,

    loading states, and not-found pages.
    """

    def test_01_all_routes_have_error_and_loading_files(self):
        """Every single route must possess its own error.tsx and loading.tsx."""
        for route in ROUTES:
            route_path = APP_DIR if route == "" else APP_DIR / route
            error_file = route_path / "error.tsx"
            loading_file = route_path / "loading.tsx"

            self.assertTrue(
                error_file.exists(),
                f"Missing error.tsx in route: {route or 'root'}",
            )
            self.assertTrue(
                loading_file.exists(),
                f"Missing loading.tsx in route: {route or 'root'}",
            )

    def test_02_global_error_and_not_found_exist(self):
        """Root directory must define global-error.tsx and not-found.tsx."""
        self.assertTrue((APP_DIR / "global-error.tsx").exists())
        self.assertTrue((APP_DIR / "not-found.tsx").exists())

    def test_03_error_boundaries_client_component_and_retry_behavior(self):
        """All error boundaries must be client components with startTransition retry & reload."""
        all_error_files = [
            APP_DIR if r == "" else APP_DIR / r for r in ROUTES
        ]
        all_error_files = [p / "error.tsx" for p in all_error_files] + [
            APP_DIR / "global-error.tsx"
        ]

        for file_path in all_error_files:
            rel = file_path.name
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("'use client'", content, f"{rel} must be a client component ('use client')")
            self.assertIn("startTransition", content, f"{rel} must use startTransition for reset retry")
            self.assertIn("reset()", content, f"{rel} must invoke reset() inside startTransition")
            self.assertIn("window.location.reload()", content, f"{rel} must provide window reload fallback")
            self.assertIn("error?.digest", content, f"{rel} must safely inspect error?.digest")

    def test_04_error_boundaries_accessibility_attributes(self):
        """All error boundaries must implement WCAG AA accessible alert standards."""
        all_error_files = [
            APP_DIR if r == "" else APP_DIR / r for r in ROUTES
        ]
        all_error_files = [p / "error.tsx" for p in all_error_files] + [
            APP_DIR / "global-error.tsx"
        ]

        for file_path in all_error_files:
            rel = file_path.name
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn('role="alert"', content, f"{rel} must have role='alert'")
            self.assertIn('aria-live="assertive"', content, f"{rel} must have aria-live='assertive'")
            self.assertIn('aria-atomic="true"', content, f"{rel} must have aria-atomic='true'")
            self.assertIn("tabIndex={-1}", content, f"{rel} must have tabIndex={-1} for focus reception")
            self.assertIn("containerRef.current?.focus()", content, f"{rel} must focus container on mount")

            # Check that aria-labelledby and aria-describedby reference matching IDs
            lbl_match = re.search(r'aria-labelledby="([^"]+)"', content)
            desc_match = re.search(r'aria-describedby="([^"]+)"', content)
            self.assertIsNotNone(lbl_match, f"{rel} missing aria-labelledby")
            self.assertIsNotNone(desc_match, f"{rel} missing aria-describedby")

            lbl_id = lbl_match.group(1)
            desc_id = desc_match.group(1)

            self.assertIn(f'id="{lbl_id}"', content, f"{rel} heading ID mismatch: {lbl_id}")
            self.assertIn(f'id="{desc_id}"', content, f"{rel} description ID mismatch: {desc_id}")

    def test_05_error_boundaries_touch_targets_and_buttons(self):
        """All buttons and links in error boundaries must meet minimum 44px touch targets."""
        all_error_files = [
            APP_DIR if r == "" else APP_DIR / r for r in ROUTES
        ]
        all_error_files = [p / "error.tsx" for p in all_error_files] + [
            APP_DIR / "global-error.tsx"
        ]

        for file_path in all_error_files:
            rel = file_path.name
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            buttons = re.findall(r'<button\b[^>]*>', content)
            self.assertGreaterEqual(len(buttons), 2, f"{rel} should have at least retry and reload buttons")
            for btn in buttons:
                self.assertIn('type="button"', btn, f"{rel} button missing type='button': {btn}")
                self.assertIn("min-h-[44px]", btn, f"{rel} button missing min-h-[44px]: {btn}")
                self.assertIn("aria-label=", btn, f"{rel} button missing aria-label: {btn}")
                self.assertIn("focus-visible:", btn, f"{rel} button missing focus-visible styling: {btn}")

            links = re.findall(r'<Link\b[^>]*>', content)
            for link in links:
                self.assertIn("min-h-[44px]", link, f"{rel} link missing min-h-[44px]: {link}")

    def test_06_loading_states_accessibility_and_skeletons(self):
        """All loading states must satisfy WCAG polite status & reduced motion guidelines."""
        for route in ROUTES:
            route_path = APP_DIR if route == "" else APP_DIR / route
            loading_file = route_path / "loading.tsx"
            rel = loading_file.name

            with open(loading_file, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn('role="status"', content, f"{rel} must have role='status'")
            self.assertIn('aria-live="polite"', content, f"{rel} must have aria-live='polite'")
            self.assertIn("sr-only", content, f"{rel} must contain sr-only text announcement")
            self.assertIn("motion-reduce:animate-none", content, f"{rel} must handle motion-reduce")
            self.assertIn('aria-hidden="true"', content, f"{rel} visual skeletons must be aria-hidden")

    def test_07_global_error_defines_html_and_body(self):
        """global-error.tsx must render <html> and <body> per Next.js requirements."""
        with open(APP_DIR / "global-error.tsx", "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn('<html lang="ko">', content)
        self.assertIn("<body", content)
        self.assertIn("</body>", content)
        self.assertIn("</html>", content)

    def test_08_not_found_page_accessible_navigation(self):
        """not-found.tsx must offer accessible fallback navigation to 6 high-intent destinations."""
        with open(APP_DIR / "not-found.tsx", "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn('role="region"', content)
        self.assertIn('aria-live="polite"', content)
        self.assertIn('id="not-found-heading"', content)
        self.assertIn("/subsidy-tracker", content)
        self.assertIn("/reliability-analytics", content)
        self.assertIn("/depreciation-calculator", content)
        self.assertIn("/recall-portal", content)
        self.assertIn("/pdi-checklist", content)
        self.assertIn('href="/"', content)

        links = re.findall(r'<Link\b[^>]*>', content)
        for link in links:
            self.assertIn("min-h-[44px]", link, f"not-found.tsx link missing min-h-[44px]: {link}")


if __name__ == "__main__":
    unittest.main()
