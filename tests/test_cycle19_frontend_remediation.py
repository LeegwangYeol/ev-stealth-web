"""
tests/test_cycle19_frontend_remediation.py - Verification Test Suite for Cycle 19
Frontend Architecture & Component Remediations (sync19_worker_frontend_w2).

Authoritative Directives:
- DISPATCH.md (sync19_worker_frontend_w2):
  1. Next.js App Router client error boundary: src/app/error.tsx ('use client', reset(), home link)
  2. Branded 404 screen: src/app/not-found.tsx (quick navigation links)
  3. Contextual CTA cross-links on brand guide pages: hyundai-kia, tesla, byd, global-brands
  4. Deep-linking (?brand=..., ?category=...) and Suspense boundary in reliability-analytics
  5. Defensive null guards: (r.source || '').toLowerCase() and Number.isFinite() guards
"""

from __future__ import annotations

import re
from pathlib import Path
import unittest


def _find_repo_root() -> Path:
    candidates = [
        Path(__file__).resolve().parent.parent,
        Path(__file__).resolve().parent.parent.parent,
        Path.cwd(),
        Path.cwd().parent,
    ]
    for p in candidates:
        if (p / "ev-stealth-web").is_dir() and (p / "src").is_dir():
            return p
        if (p / "src" / "lib" / "getSubsidyData.ts").is_file():
            return p.parent
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = _find_repo_root()
WEB_ROOT = PROJECT_ROOT / "ev-stealth-web" if (PROJECT_ROOT / "ev-stealth-web").is_dir() else PROJECT_ROOT
SRC_DIR = WEB_ROOT / "src"
APP_DIR = SRC_DIR / "app"


class TestCycle19FrontendRemediations(unittest.TestCase):
    def test_01_error_boundary_implementation(self):
        """Verify src/app/error.tsx is a client component with reset() and Home link."""
        error_file = APP_DIR / "error.tsx"
        self.assertTrue(error_file.is_file(), f"Missing error boundary file: {error_file}")

        content = error_file.read_text(encoding="utf-8")
        self.assertTrue(
            content.startswith("'use client'") or content.startswith('"use client"'),
            "error.tsx must start with 'use client'",
        )
        self.assertIn("일시적인 오류가 발생했습니다", content)
        self.assertIn("reset()", content)
        self.assertIn('href="/"', content)
        self.assertIn("role=\"alert\"", content)
        self.assertIn("prefetch={false}", content)

    def test_02_not_found_implementation(self):
        """Verify src/app/not-found.tsx exists and provides compliant navigation cards."""
        not_found_file = APP_DIR / "not-found.tsx"
        self.assertTrue(not_found_file.is_file(), f"Missing not-found file: {not_found_file}")

        content = not_found_file.read_text(encoding="utf-8")
        self.assertIn("404", content)
        self.assertIn("요청하신 페이지를 찾을 수 없습니다", content)
        self.assertIn('href="/subsidy-tracker"', content)
        self.assertIn('href="/reliability-analytics"', content)
        self.assertIn('href="/depreciation-calculator"', content)
        self.assertIn('href="/"', content)
        # Prefetch compliance
        self.assertIn('href="/subsidy-tracker"\n            prefetch={true}', content)
        self.assertIn('href="/depreciation-calculator"\n            prefetch={true}', content)
        self.assertIn('href="/reliability-analytics"\n            prefetch={false}', content)
        self.assertIn('href="/"\n            prefetch={false}', content)

    def test_03_brand_guide_pages_cta_cross_links(self):
        """Verify all 4 brand guide pages contain contextual CTA cross-link cards."""
        brand_pages = {
            "hyundai-kia/page.tsx": "현대·기아 전기차 심층 분석 및 실시간 조회 도구",
            "tesla/page.tsx": "테슬라 전기차 데이터 인텔리전스 및 진단 도구",
            "byd/page.tsx": "BYD 전기차 내구성 및 실시간 분석 도구",
            "global-brands/page.tsx": "글로벌 수입 EV 데이터 인텔리전스 및 진단 도구",
        }

        for rel_path, heading in brand_pages.items():
            page_file = APP_DIR / rel_path
            self.assertTrue(page_file.is_file(), f"Missing brand page: {page_file}")

            content = page_file.read_text(encoding="utf-8")
            self.assertIn(heading, content, f"Missing heading in {rel_path}")
            self.assertIn("/reliability-analytics", content, f"Missing reliability link in {rel_path}")
            self.assertIn("/recall-portal", content, f"Missing recall link in {rel_path}")
            self.assertIn("/depreciation-calculator", content, f"Missing depreciation link in {rel_path}")
            self.assertIn("/subsidy-tracker", content, f"Missing subsidy link in {rel_path}")
            self.assertIn("prefetch={true}", content, f"Missing prefetch=true in {rel_path}")
            self.assertIn("prefetch={false}", content, f"Missing prefetch=false in {rel_path}")

    def test_04_reliability_analytics_suspense_wrapper(self):
        """Verify src/app/reliability-analytics/page.tsx wraps ReliabilityDashboardClient in Suspense."""
        page_file = APP_DIR / "reliability-analytics" / "page.tsx"
        self.assertTrue(page_file.is_file(), f"Missing page: {page_file}")

        content = page_file.read_text(encoding="utf-8")
        self.assertIn("Suspense", content)
        self.assertIn("<Suspense", content)
        self.assertIn("</Suspense>", content)
        self.assertIn("<ReliabilityDashboardClient", content)

    def test_05_reliability_client_deep_linking_and_null_guards(self):
        """Verify ReliabilityDashboardClient supports searchParams and guards non-finite values."""
        client_file = APP_DIR / "reliability-analytics" / "ReliabilityDashboardClient.tsx"
        self.assertTrue(client_file.is_file(), f"Missing client file: {client_file}")

        content = client_file.read_text(encoding="utf-8")
        self.assertIn("useSearchParams", content)
        self.assertIn("resolveBrandId", content)
        self.assertIn("resolveCategoryKey", content)
        self.assertIn("ClientTimestamp", content)
        self.assertIn("Number.isFinite(a.overall_dsi)", content)
        self.assertIn("Number.isFinite(brand.overall_dsi)", content)
        self.assertIn("Number.isFinite(cat.industry_share_pct)", content)
        self.assertIn("Number.isFinite(a.avg_dsi)", content)

    def test_06_admin_dashboard_defensive_null_guards(self):
        """Verify AdminDashboardClient guards r.source before calling toLowerCase()."""
        admin_file = APP_DIR / "secret-admin-reports" / "AdminDashboardClient.tsx"
        self.assertTrue(admin_file.is_file(), f"Missing admin file: {admin_file}")

        content = admin_file.read_text(encoding="utf-8")
        self.assertIn("(r.source || '').toLowerCase()", content)
        self.assertIn("(report.source || '').toLowerCase()", content)
        self.assertIn("(source || '').toLowerCase()", content)
        self.assertIn("report.source || 'N/A'", content)


if __name__ == "__main__":
    unittest.main()
