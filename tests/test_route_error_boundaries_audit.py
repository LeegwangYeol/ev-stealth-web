import unittest
import os
import re

class TestRouteErrorBoundariesAudit(unittest.TestCase):
    """
    Comprehensive audit for Next.js App Router error boundaries,
    loading skeletons, and missing data fallbacks across all route segments.
    """

    @classmethod
    def setUpClass(cls):
        # Determine base directory
        cls.repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_candidates = [
            os.path.join(cls.repo_root, "ev-stealth-web", "src", "app"),
            os.path.join(cls.repo_root, "src", "app"),
        ]
        cls.app_dir = next((p for p in app_candidates if os.path.isdir(p)), None)
        assert cls.app_dir, "Could not locate Next.js app directory"

        cls.routes = [
            "subsidy-tracker",
            "depreciation-calculator",
            "reliability-analytics",
            "recall-portal",
            "pdi-checklist",
            "secret-admin-reports",
            "2026-latest",
            "tesla",
            "byd",
            "hyundai-kia",
            "global-brands",
        ]

    def test_root_boundaries_exist_and_accessible(self):
        root_error = os.path.join(self.app_dir, "error.tsx")
        root_loading = os.path.join(self.app_dir, "loading.tsx")
        root_not_found = os.path.join(self.app_dir, "not-found.tsx")

        self.assertTrue(os.path.isfile(root_error), "Root error.tsx must exist")
        self.assertTrue(os.path.isfile(root_loading), "Root loading.tsx must exist")
        self.assertTrue(os.path.isfile(root_not_found), "Root not-found.tsx must exist")

        with open(root_error, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertTrue(content.startswith("'use client'") or content.startswith('"use client"'))
            self.assertIn('role="alert"', content)
            self.assertIn('aria-live="assertive"', content)
            self.assertIn("다시 시도", content)
            self.assertIn('aria-label="다시 시도"', content)
            self.assertIn("reset()", content)

        with open(root_loading, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn('role="status"', content)
            self.assertIn('aria-live="polite"', content)
            self.assertIn("sr-only", content)

        with open(root_not_found, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("/subsidy-tracker", content)
            self.assertIn("/depreciation-calculator", content)
            self.assertIn("/reliability-analytics", content)
            self.assertIn("/recall-portal", content)
            self.assertIn("/pdi-checklist", content)

    def test_all_route_segments_have_error_boundaries(self):
        for route in self.routes:
            error_file = os.path.join(self.app_dir, route, "error.tsx")
            self.assertTrue(
                os.path.isfile(error_file),
                f"Route segment '{route}' must have an error.tsx boundary",
            )

            with open(error_file, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertTrue(
                    content.startswith("'use client'") or content.startswith('"use client"'),
                    f"{error_file} must declare 'use client'",
                )
                self.assertIn('role="alert"', content, f"{error_file} missing role='alert'")
                self.assertIn(
                    'aria-live="assertive"', content, f"{error_file} missing aria-live='assertive'"
                )
                self.assertIn("다시 시도", content, f"{error_file} missing '다시 시도' label")
                self.assertIn("reset()", content, f"{error_file} must invoke reset() recovery")
                self.assertIn("console.error", content, f"{error_file} should log for telemetry")

    def test_all_route_segments_have_loading_skeletons(self):
        for route in self.routes:
            loading_file = os.path.join(self.app_dir, route, "loading.tsx")
            self.assertTrue(
                os.path.isfile(loading_file),
                f"Route segment '{route}' must have a loading.tsx skeleton",
            )

            with open(loading_file, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertIn('role="status"', content, f"{loading_file} missing role='status'")
                self.assertIn(
                    'aria-live="polite"', content, f"{loading_file} missing aria-live='polite'"
                )
                self.assertIn("sr-only", content, f"{loading_file} missing sr-only announcement")
                self.assertIn("animate-pulse", content, f"{loading_file} should use pulse skeleton")

    def test_no_missing_data_crashes_in_loaders(self):
        # Verify that TypeScript loader files handle missing or malformed data gracefully
        lib_dir = os.path.join(os.path.dirname(self.app_dir), "lib")
        loaders = [
            "getSubsidyData.ts",
            "getDepreciationData.ts",
            "getReliabilityData.ts",
            "getRecallData.ts",
            "getDailyReports.ts",
        ]
        for loader in loaders:
            loader_path = os.path.join(lib_dir, loader)
            self.assertTrue(os.path.isfile(loader_path), f"Loader {loader} must exist")
            with open(loader_path, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertTrue(
                    "fallback" in content.lower() or "default" in content.lower(),
                    f"Loader {loader} must implement fallback dataset handling",
                )
                self.assertTrue(
                    "try" in content and "catch" in content,
                    f"Loader {loader} must wrap data loading in defensive try/catch",
                )


if __name__ == "__main__":
    unittest.main()
