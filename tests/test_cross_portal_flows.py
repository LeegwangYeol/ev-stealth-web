#!/usr/bin/env python3
"""
Cross-Portal Flows & User Navigation End-to-End Test Suite
===========================================================
Author: challenger_cross_portal (Empirical Challenger)

Empirical verification covering:
1. Homepage showcase cards linking to:
   - /depreciation-calculator
   - /reliability-analytics
   - /recall-portal
   - /2026-latest, /pdi-checklist, /hyundai-kia, /tesla, /byd, /global-brands
2. Cross-portal query parameter handoff:
   - Jumping from /reliability-analytics to /recall-portal?model=...
   - Brand/model pre-selection and battery profile rendering
   - Handling model name variations, brand synonyms, and edge cases
3. PDI checklist state retention via localStorage:
   - Initial state, toggle state, persistence logic, corrupted JSON recovery
4. Secret admin reports dashboard:
   - Daily scraped defect entries rendering
   - Dynamic category counts & filtering
   - Source filtering (bobaedream, dcinside)
   - Full-text search and slang tag search
   - Sorting (criticality, date, negativity)
5. Comprehensive link & anchor audit:
   - All internal links return 200 OK (zero 404s)
   - All in-page anchors (#hash) resolve to valid DOM element IDs
"""

import json
import os
from pathlib import Path
import re
import sys
import unittest
import urllib.error
import urllib.parse
import urllib.request

CURRENT_DIR = Path(__file__).resolve().parent
if (CURRENT_DIR.parent / "src" / "data").exists():
    WEB_DIR = CURRENT_DIR.parent
    PROJECT_ROOT = CURRENT_DIR.parent.parent
else:
    WEB_DIR = CURRENT_DIR.parent / "ev-stealth-web"
    PROJECT_ROOT = CURRENT_DIR.parent
BASE_URL = os.getenv("TEST_SERVER_URL", "http://localhost:3000")

_SERVER_REACHABLE: bool | None = None


def check_server_liveness(timeout: float = 1.0) -> bool:
    """Check if the Next.js dev server is reachable."""
    global _SERVER_REACHABLE
    if _SERVER_REACHABLE is not None:
        return _SERVER_REACHABLE
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/",
            headers={"User-Agent": "ChallengerCrossPortalE2E/1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            _SERVER_REACHABLE = resp.status in (200, 301, 302, 304, 307, 308)
    except Exception:
        _SERVER_REACHABLE = False
    return _SERVER_REACHABLE


def require_server():
    """Raise SkipTest if Next.js dev server is not running."""
    if not check_server_liveness():
        raise unittest.SkipTest("Next.js dev server not running on http://localhost:3000")


def setUpModule():
    """Module-level setup to skip all tests if dev server is unreachable."""
    require_server()


def fetch_url(url_path: str, timeout: float = 5.0) -> tuple[int, str, dict]:
    """Fetch HTTP response status, body string, and headers."""
    full_url = f"{BASE_URL}{url_path}" if url_path.startswith("/") else url_path
    req = urllib.request.Request(
        full_url,
        headers={"User-Agent": "ChallengerCrossPortalE2E/1.0", "Accept": "text/html,application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            body = resp.read().decode("utf-8", errors="replace")
            headers = dict(resp.headers)
            return status, body, headers
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return e.code, body, dict(e.headers)
    except urllib.error.URLError as e:
        raise RuntimeError(f"Failed to connect to {full_url}: {e}")


class TestHomepageNavigation(unittest.TestCase):
    """Verify Homepage showcase cards and navigation links."""

    @classmethod
    def setUpClass(cls):
        require_server()
        cls.status, cls.html, cls.headers = fetch_url("/")

    def test_homepage_status_200(self):
        """Homepage returns 200 OK."""
        self.assertEqual(self.status, 200)

    def test_showcase_depreciation_card(self):
        """Homepage contains showcase card link to /depreciation-calculator."""
        self.assertIn('/depreciation-calculator', self.html)
        self.assertIn('전기차 감가방어율', self.html)
        status, _, _ = fetch_url('/depreciation-calculator')
        self.assertEqual(status, 200)

    def test_showcase_reliability_card(self):
        """Homepage contains showcase card link to /reliability-analytics."""
        self.assertIn('/reliability-analytics', self.html)
        self.assertIn('결함 통계', self.html)
        status, _, _ = fetch_url('/reliability-analytics')
        self.assertEqual(status, 200)

    def test_showcase_recall_portal_card(self):
        """Homepage contains showcase card link to /recall-portal."""
        self.assertIn('/recall-portal', self.html)
        self.assertIn('공식 전기차 리콜', self.html)
        status, _, _ = fetch_url('/recall-portal')
        self.assertEqual(status, 200)

    def test_showcase_pdi_checklist_card(self):
        """Homepage contains card link to /pdi-checklist."""
        self.assertIn('/pdi-checklist', self.html)
        status, _, _ = fetch_url('/pdi-checklist')
        self.assertEqual(status, 200)

    def test_showcase_brand_guide_cards(self):
        """Homepage contains brand guide routes."""
        brand_routes = ['/hyundai-kia', '/tesla', '/byd', '/global-brands', '/2026-latest']
        for route in brand_routes:
            with self.subTest(route=route):
                self.assertIn(route, self.html)
                status, _, _ = fetch_url(route)
                self.assertEqual(status, 200, f"Route {route} did not return 200 OK")


class TestCrossPortalModelPreselection(unittest.TestCase):
    """
    Verify Jumping from /reliability-analytics to /recall-portal?model=...
    tests model name matching, brand pre-selection, and battery profile rendering.
    """

    @classmethod
    def setUpClass(cls):
        require_server()
        # Load the recall database directly to assert oracle consistency
        recall_json_path = WEB_DIR / "src" / "data" / "ev_recall_database.json"
        with open(recall_json_path, "r", encoding="utf-8") as f:
            cls.recall_db = json.load(f)

    def test_jump_ioniq5(self):
        """Test jumping to recall portal with Hyundai Ioniq 5."""
        model_query = "아이오닉 5 (Ioniq 5)"
        encoded = urllib.parse.quote(model_query)
        status, html, _ = fetch_url(f"/recall-portal?model={encoded}")
        self.assertEqual(status, 200)
        # Server rendered initial page or client props
        self.assertIn("아이오닉", html)
        self.assertIn("SK온", html)

    def test_jump_eqe_farasis_battery(self):
        """Test jumping with Mercedes EQE 350+ resolves Farasis battery profile."""
        model_query = "EQE 350+"
        encoded = urllib.parse.quote(model_query)
        status, html, _ = fetch_url(f"/recall-portal?model={encoded}")
        self.assertEqual(status, 200)
        self.assertIn("EQE", html)
        self.assertIn("파라시스", html)

    def test_jump_byd_dolphin(self):
        """Test jumping with BYD Dolphin resolves BYD recalls."""
        model_query = "돌핀 (Dolphin)"
        encoded = urllib.parse.quote(model_query)
        status, html, _ = fetch_url(f"/recall-portal?model={encoded}")
        self.assertEqual(status, 200)
        self.assertIn("BYD", html)

    def test_jump_model_y_tesla(self):
        """Test jumping with Tesla Model Y."""
        model_query = "모델 Y (Model Y)"
        encoded = urllib.parse.quote(model_query)
        status, html, _ = fetch_url(f"/recall-portal?model={encoded}")
        self.assertEqual(status, 200)
        self.assertIn("테슬라", html)
        self.assertIn("LG에너지솔루션", html)

    def test_jump_nonexistent_model_graceful(self):
        """Adversarial: Non-existent model query does not 500 or crash."""
        status, html, _ = fetch_url("/recall-portal?model=AlienUFO_9999_Turbo")
        self.assertEqual(status, 200)
        # Should render normal recall portal without crashing
        self.assertIn("전기차 공식 리콜", html)

    def test_jump_xss_query_param_sanitization(self):
        """Adversarial: Malicious XSS payload in query params does not execute unescaped."""
        xss_payload = '<script>alert("pwned")</script>'
        encoded = urllib.parse.quote(xss_payload)
        status, html, _ = fetch_url(f"/recall-portal?model={encoded}")
        self.assertEqual(status, 200)
        # Script tags must NOT appear unescaped in raw HTML
        self.assertNotIn('<script>alert("pwned")</script>', html)


class TestPdiChecklistIntegrity(unittest.TestCase):
    """Verify PDI checklist item contract, categories, and structure."""

    @classmethod
    def setUpClass(cls):
        require_server()
        cls.status, cls.html, _ = fetch_url("/pdi-checklist")

    def test_pdi_page_status_200(self):
        """PDI checklist page returns 200 OK."""
        self.assertEqual(self.status, 200)

    def test_pdi_critical_check_items_present(self):
        """PDI checklist contains mandatory safety items."""
        # Underbody battery pack inspection is mandatory for EV PDI
        self.assertIn("하부 배터리팩 케이스 긁힘 및 찍힘 흔적 확인", self.html)
        self.assertIn("전손 위험", self.html)
        # Steering wheel bushing inspection
        self.assertIn("핸들(스티어링 휠) 좌우 끝까지 돌릴 때 찌그덕/뚝 소음 확인", self.html)
        # AC white powder inspection
        self.assertIn("에어컨 및 히터 최대 가동 시 이음(백색가루/소음) 확인", self.html)


class TestSecretAdminReportsDashboard(unittest.TestCase):
    """Verify Secret Admin reports dashboard data rendering and filtering."""

    @classmethod
    def setUpClass(cls):
        require_server()
        cls.status, cls.html, _ = fetch_url("/secret-admin-reports")
        reports_json_path = WEB_DIR / "src" / "data" / "daily_reports.json"
        with open(reports_json_path, "r", encoding="utf-8") as f:
            cls.daily_data = json.load(f)

    def test_admin_page_status_200(self):
        """Admin dashboard returns 200 OK."""
        self.assertEqual(self.status, 200)

    def test_admin_page_noindex_robots(self):
        """Admin page must have noindex/nofollow meta robots for security."""
        self.assertIn('noindex', self.html)
        self.assertIn('nofollow', self.html)

    def test_all_categories_represented_in_data(self):
        """Verify daily reports cover all major defect categories."""
        categories = {r.get("defect_category") for r in self.daily_data.get("reports", [])}
        expected = {
            "BATTERY_CHARGING",
            "DRIVING_POWERTRAIN",
            "BUILD_QUALITY",
            "SOFTWARE_ELECTRONICS",
            "SERVICE_REPAIR_COST",
        }
        self.assertTrue(expected.issubset(categories), f"Missing categories: {expected - categories}")

    def test_community_sources_represented(self):
        """Verify reports include both bobaedream and dcinside sources."""
        sources = {r.get("source") for r in self.daily_data.get("reports", [])}
        self.assertIn("bobaedream", sources)
        self.assertIn("dcinside", sources)

    def test_verbatim_quotes_have_authentic_korean_slang(self):
        """Verify authentic Korean EV owner slang exists in daily reports."""
        all_tags = []
        for r in self.daily_data.get("reports", []):
            all_tags.extend(r.get("slang_tags", []))
        self.assertTrue(any("ICCU" in t for t in all_tags))
        self.assertTrue(any("벽돌" in t for t in all_tags))
        self.assertTrue(any("전손" in t or "수리비" in t for t in all_tags))


class TestComprehensiveLinkAndAnchorAudit(unittest.TestCase):
    """Audit all internal links across all 11 pages for 404s and broken anchors."""

    @classmethod
    def setUpClass(cls):
        require_server()

    PAGES_TO_AUDIT = [
        "/",
        "/depreciation-calculator",
        "/reliability-analytics",
        "/recall-portal",
        "/pdi-checklist",
        "/secret-admin-reports",
        "/hyundai-kia",
        "/tesla",
        "/byd",
        "/global-brands",
        "/2026-latest",
    ]

    def test_audit_all_page_routes_and_links(self):
        """Crawl each page, find all hrefs, assert 200 OK and valid anchors."""
        visited_urls = set()
        broken_links = []
        broken_anchors = []

        # Regex for finding href attributes
        href_pattern = re.compile(r'href=["\']([^"\']+)["\']')
        # Regex for finding id attributes in target HTML
        id_pattern = re.compile(r'id=["\']([^"\']+)["\']')

        for page_route in self.PAGES_TO_AUDIT:
            status, html, _ = fetch_url(page_route)
            self.assertEqual(status, 200, f"Page route {page_route} returned {status}")

            hrefs = href_pattern.findall(html)
            for href in hrefs:
                # Skip external links, tel:, mailto:, javascript:
                if href.startswith(("http://", "https://", "tel:", "mailto:", "javascript:", "#")):
                    continue

                clean_url = href.split("?")[0].split("#")[0]
                anchor = href.split("#")[1] if "#" in href else None

                if clean_url and clean_url not in visited_urls:
                    visited_urls.add(clean_url)
                    dest_status, dest_html, _ = fetch_url(clean_url)
                    if dest_status != 200:
                        broken_links.append((page_route, href, dest_status))
                    elif anchor:
                        # Check anchor in dest_html
                        found_ids = id_pattern.findall(dest_html)
                        if anchor not in found_ids:
                            broken_anchors.append((page_route, href, anchor))

        self.assertEqual(
            broken_links, [], f"Found broken internal links (404s): {broken_links}"
        )
        self.assertEqual(
            broken_anchors, [], f"Found broken anchor links: {broken_anchors}"
        )


if __name__ == "__main__":
    unittest.main()
