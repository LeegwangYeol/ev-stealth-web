"""
tests/test_seo_metadata_sitemap_robots.py - Comprehensive SEO, OpenGraph, JSON-LD, Sitemap & Robots Audit Suite.

Verifies:
1. robots.ts generates standard robots.txt directives, blocks private admin routes, and references canonical sitemap.
2. sitemap.ts generates valid sitemap.xml entries for all 11 public canonical routes with proper priority and frequency.
3. layout.tsx defines metadataBase, title template, canonical URL, OpenGraph, Twitter cards, GoogleBot robots, and global JSON-LD.
4. All public routes define accurate titles, descriptions, canonical URLs, OpenGraph, Twitter cards, and Schema.org structured data.
5. Private routes (secret-admin-reports, not-found) strictly enforce noindex/nofollow to avoid indexing issues.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

APP_DIR = (
    PROJECT_ROOT / "ev-stealth-web" / "src" / "app"
    if (PROJECT_ROOT / "ev-stealth-web" / "src" / "app").exists()
    else PROJECT_ROOT / "src" / "app"
)

PUBLIC_ROUTES = [
    ("", "/"),
    ("subsidy-tracker", "/subsidy-tracker"),
    ("depreciation-calculator", "/depreciation-calculator"),
    ("reliability-analytics", "/reliability-analytics"),
    ("recall-portal", "/recall-portal"),
    ("2026-latest", "/2026-latest"),
    ("pdi-checklist", "/pdi-checklist"),
    ("hyundai-kia", "/hyundai-kia"),
    ("tesla", "/tesla"),
    ("byd", "/byd"),
    ("global-brands", "/global-brands"),
]


class TestSeoMetadataSitemapRobots(unittest.TestCase):
    """Rigorous audit test suite for SEO, OpenGraph metadata, JSON-LD, sitemap, and robots."""

    def test_robots_ts_file_and_runtime_output(self) -> None:
        """robots.ts must exist and generate compliant robots directives blocking admin routes."""
        robots_file = APP_DIR / "robots.ts"
        self.assertTrue(robots_file.exists(), f"Missing robots.ts at {robots_file}")

        robots_content = robots_file.read_text(encoding="utf-8")
        self.assertIn("export default function robots", robots_content)
        self.assertIn("secret-admin-reports", robots_content)
        self.assertIn("sitemap.xml", robots_content)

        # Execute robots.ts with Node to verify runtime output contract
        cmd = [
            "node",
            "--experimental-strip-types",
            "-e",
            f'import robots from "{robots_file}"; console.log(JSON.stringify(robots()));',
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f"robots.ts execution failed: {result.stderr}")

        # Parse JSON output from the last non-empty line
        output_lines = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
        self.assertTrue(len(output_lines) > 0, "No output from robots.ts execution")
        data = json.loads(output_lines[-1])

        self.assertIn("rules", data)
        self.assertIn("sitemap", data)
        self.assertTrue(str(data["sitemap"]).endswith("/sitemap.xml"))
        self.assertIn("https://ev-stealth-web.vercel.app", str(data["sitemap"]))

        rules = data["rules"]
        self.assertIsInstance(rules, list)
        self.assertTrue(len(rules) > 0)
        rule = rules[0]
        self.assertEqual(rule.get("userAgent"), "*")
        self.assertEqual(rule.get("allow"), "/")
        disallows = rule.get("disallow", [])
        self.assertIn("/secret-admin-reports", disallows)
        self.assertIn("/api/", disallows)

    def test_sitemap_ts_file_and_runtime_output(self) -> None:
        """sitemap.ts must exist and return all 11 public canonical routes, excluding private pages."""
        sitemap_file = APP_DIR / "sitemap.ts"
        self.assertTrue(sitemap_file.exists(), f"Missing sitemap.ts at {sitemap_file}")

        sitemap_content = sitemap_file.read_text(encoding="utf-8")
        self.assertIn("export default function sitemap", sitemap_content)
        self.assertNotIn("secret-admin-reports", sitemap_content)

        # Execute sitemap.ts with Node to verify runtime output contract
        cmd = [
            "node",
            "--experimental-strip-types",
            "-e",
            f'import sitemap from "{sitemap_file}"; console.log(JSON.stringify(sitemap()));',
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f"sitemap.ts execution failed: {result.stderr}")

        output_lines = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
        self.assertTrue(len(output_lines) > 0, "No output from sitemap.ts execution")
        entries = json.loads(output_lines[-1])

        self.assertIsInstance(entries, list)
        self.assertEqual(len(entries), 11, f"Expected 11 public sitemap entries, got {len(entries)}")

        sitemap_urls = [entry["url"] for entry in entries]
        for route_folder, canonical_path in PUBLIC_ROUTES:
            expected_url = f"https://ev-stealth-web.vercel.app{'' if canonical_path == '/' else canonical_path}"
            self.assertIn(
                expected_url,
                sitemap_urls,
                f"Sitemap missing canonical route {expected_url}",
            )

        # Verify no secret admin route in sitemap
        for url in sitemap_urls:
            self.assertNotIn("secret-admin-reports", url)

        # Verify priorities and change frequencies
        root_entry = next(e for e in entries if e["url"] == "https://ev-stealth-web.vercel.app")
        self.assertEqual(root_entry.get("priority"), 1.0)
        self.assertEqual(root_entry.get("changeFrequency"), "daily")

    def test_layout_tsx_metadata_base_and_json_ld(self) -> None:
        """layout.tsx must configure metadataBase, title template, canonical URL, and global JSON-LD."""
        layout_file = APP_DIR / "layout.tsx"
        self.assertTrue(layout_file.exists())
        content = layout_file.read_text(encoding="utf-8")

        # metadataBase
        self.assertIn("metadataBase:", content)
        self.assertIn("new URL(", content)

        # title template
        self.assertIn("template:", content)
        self.assertIn("%s | Global EV Hub", content)

        # Canonical alternate
        self.assertIn("alternates:", content)
        self.assertIn("canonical:", content)

        # OpenGraph
        self.assertIn("openGraph:", content)
        self.assertIn("siteName:", content)
        self.assertIn("locale:", content)

        # Twitter Card
        self.assertIn("twitter:", content)
        self.assertIn("summary_large_image", content)

        # Robots & GoogleBot
        self.assertIn("robots:", content)
        self.assertIn("googleBot:", content)

        # Global JSON-LD structured data (WebSite & Organization)
        self.assertIn("JsonLd", content)
        self.assertIn("@context", content)
        self.assertIn("https://schema.org", content)
        self.assertIn("WebSite", content)
        self.assertIn("Organization", content)

    def test_all_public_pages_metadata_and_canonical(self) -> None:
        """All public pages must declare title, description, canonical alternates, OG, and JSON-LD."""
        for route_folder, canonical_path in PUBLIC_ROUTES:
            page_file = APP_DIR / route_folder / "page.tsx" if route_folder else APP_DIR / "page.tsx"
            self.assertTrue(page_file.exists(), f"Page missing at {page_file}")
            content = page_file.read_text(encoding="utf-8")

            # Must declare force-static
            self.assertIn("force-static", content, f"{page_file} must declare force-static")

            # Must export metadata
            self.assertIn("export const metadata", content, f"{page_file} must export metadata")
            self.assertIn("title:", content, f"{page_file} must have title in metadata")
            self.assertIn("description:", content, f"{page_file} must have description in metadata")

            # Must have canonical URL matching the route
            self.assertIn("alternates:", content, f"{page_file} must declare alternates in metadata")
            self.assertIn(f"canonical: '{canonical_path}'", content.replace('"', "'"), f"{page_file} canonical must be '{canonical_path}'")

            # Must have openGraph
            self.assertIn("openGraph:", content, f"{page_file} must declare openGraph in metadata")
            self.assertIn(f"url: '{canonical_path}'", content.replace('"', "'"), f"{page_file} openGraph.url must be '{canonical_path}'")

            # Must have twitter card
            self.assertIn("twitter:", content, f"{page_file} must declare twitter in metadata")
            self.assertIn("summary_large_image", content, f"{page_file} twitter card must be summary_large_image")

            # Must render JsonLd
            self.assertIn("JsonLd", content, f"{page_file} must render JsonLd structured data")
            self.assertIn("schema.org", content, f"{page_file} JsonLd must reference schema.org")

    def test_private_routes_indexing_guard(self) -> None:
        """Private routes (secret-admin-reports, not-found) must strictly declare robots noindex/nofollow."""
        admin_page = APP_DIR / "secret-admin-reports" / "page.tsx"
        self.assertTrue(admin_page.exists())
        admin_content = admin_page.read_text(encoding="utf-8")
        self.assertIn("index: false", admin_content)
        self.assertIn("follow: false", admin_content)
        self.assertIn("nocache: true", admin_content)

        not_found_page = APP_DIR / "not-found.tsx"
        self.assertTrue(not_found_page.exists())
        not_found_content = not_found_page.read_text(encoding="utf-8")
        self.assertIn("index: false", not_found_content)
        self.assertIn("follow: false", not_found_content)


if __name__ == "__main__":
    unittest.main()
