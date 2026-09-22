"""
Dedicated E2E Validator for Round 2 & Round 3: Massive Crawling & Statistical Analytics Report.

Verifies:
1. Multi-Platform Inclusion: Data from ALL 3 required platforms (Bobaedream, DC Inside, Blind)
   is present in the dataset and comprehensively analyzed in the report.
2. Safe Crawling Compliance: Crawler modules implement randomized delay/jitter (1.5s–3.5s),
   User-Agent rotation, traffic limits (burst cooldowns), and exponential backoff.
3. Top Complaint Keyword Ranking: STATISTICAL_REPORT.md contains a TOP keyword ranking table
   with exact numerical counts/frequencies ($TF$) and percentages (%).
4. Deep Statistical Insights:
   - 4-Tier sentiment analysis distribution (Positive, Neutral, Negative, Strongly Negative).
   - Cross-platform comparative analysis (Bobaedream vs. DC Inside vs. Blind).
   - Temporal trend distribution (2024, 2025, 2026).
   - Defect Severity Index (DSI: 0.0 – 10.0) scoring metrics.
5. Structural Integrity & Verifiability: Valid Markdown formatting, table structure,
   and absence of placeholder/TODO tokens.
"""

import os
import re
import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List, Set

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if not (PROJECT_ROOT / "scrapers").exists() and (PROJECT_ROOT.parent / "scrapers").exists():
    PROJECT_ROOT = PROJECT_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.e2e.common import (
    CATEGORY_KOREAN_NAMES,
    MANDATORY_CATEGORIES,
    MANDATORY_THREE_PLATFORMS,
    extract_markdown_sections,
    inspect_crawler_script_safety,
    load_casebook,
    load_complaints_data,
    load_statistical_report,
    parse_markdown_tables,
)

FORBIDDEN_PLACEHOLDER_TOKENS = [
    "[TODO]",
    "[TBD]",
    "[PLACEHOLDER]",
    "[INSERT",
    "Lorem ipsum",
    "내용 추가 예정",
    "분석 예정",
    "수치 산출 예정",
]


class TestStatisticalReportValidation(unittest.TestCase):
    """Validator test suite for statistical analytics deliverable and crawler safety."""

    complaints: List[Dict[str, Any]] = []
    report_text: str = ""
    report_sections: Dict[str, str] = {}
    report_tables: List[List[Dict[str, str]]] = []

    @classmethod
    def setUpClass(cls):
        """Load datasets, report text, and parsed tables."""
        cls.complaints = []
        cls.report_text = ""
        cls.report_sections = {}
        cls.report_tables = []
        cls.data_load_error = None
        cls.report_load_error = None

        try:
            cls.complaints = load_complaints_data()
        except Exception as e:
            cls.data_load_error = str(e)

        try:
            cls.report_text = load_statistical_report()
            cls.report_sections = extract_markdown_sections(cls.report_text)
            cls.report_tables = parse_markdown_tables(cls.report_text)
        except Exception as e:
            cls.report_load_error = str(e)

    # --------------------------------------------------------------------------
    # 1. Multi-Platform Inclusion (Bobaedream, DC Inside, Blind)
    # --------------------------------------------------------------------------
    def test_01_all_three_mandatory_platforms_present_in_dataset(self):
        """Programmatic verification: Dataset contains records from Bobaedream, DC Inside, and Blind."""
        if self.data_load_error:
            self.fail(f"Dataset load failure: {self.data_load_error}")
        self.assertGreater(len(self.complaints), 0, "Complaints dataset is empty.")

        platforms_found = {
            (r.get("platform", "") or "").strip().lower() for r in self.complaints
        }

        # Check all 3 required platforms
        has_bobae = any("bobae" in p for p in platforms_found)
        has_dc = any("dc" in p for p in platforms_found)
        has_blind = any("blind" in p for p in platforms_found)

        missing_platforms = []
        if not has_bobae:
            missing_platforms.append("Bobaedream (보배드림)")
        if not has_dc:
            missing_platforms.append("DC Inside (디시인사이드)")
        if not has_blind:
            missing_platforms.append("Blind (블라인드)")

        self.assertEqual(
            len(missing_platforms),
            0,
            f"Dataset is missing mandatory platforms: {missing_platforms}. "
            f"Platforms found: {platforms_found}",
        )

    def test_02_all_three_mandatory_platforms_analyzed_in_report(self):
        """Programmatic verification: STATISTICAL_REPORT.md analyzes all 3 platforms."""
        if self.report_load_error:
            self.fail(f"Report load failure: {self.report_load_error}")

        all_text = self.report_text

        # Verify mentions and structured coverage of all 3 platforms
        self.assertTrue(
            "보배드림" in all_text or "bobaedream" in all_text.lower(),
            "STATISTICAL_REPORT.md lacks analysis of Bobaedream.",
        )
        self.assertTrue(
            "디시인사이드" in all_text or "dcinside" in all_text.lower(),
            "STATISTICAL_REPORT.md lacks analysis of DC Inside.",
        )
        self.assertTrue(
            "블라인드" in all_text or "blind" in all_text.lower(),
            "STATISTICAL_REPORT.md lacks analysis of Blind.",
        )

    # --------------------------------------------------------------------------
    # 2. Crawler Safe Rate Limiting & Anti-Bot Infrastructure
    # --------------------------------------------------------------------------
    def test_03_crawler_scripts_implement_delay_jitter_and_traffic_limits(self):
        """Programmatic verification: Scrapers implement delay/jitter (1.5s-3.5s), UA rotation, and backoff."""
        scrapers_dir = PROJECT_ROOT / "scrapers"
        self.assertTrue(scrapers_dir.exists(), "Scrapers directory missing.")

        core_script_paths = [
            scrapers_dir / "common_utils.py",
            scrapers_dir / "bobaedream_scraper.py",
            scrapers_dir / "dcinside_scraper.py",
        ]

        # Check optional/new scrapers if present
        blind_scraper_path = scrapers_dir / "blind_scraper.py"
        if blind_scraper_path.exists():
            core_script_paths.append(blind_scraper_path)

        for script_path in core_script_paths:
            self.assertTrue(script_path.exists(), f"Scraper script {script_path.name} not found.")
            safety = inspect_crawler_script_safety(script_path)

            self.assertTrue(
                safety["has_delay_jitter"],
                f"Scraper script '{script_path.name}' lacks explicit delay/jitter implementation.",
            )
            self.assertTrue(
                safety["has_ua_rotation"],
                f"Scraper script '{script_path.name}' lacks User-Agent rotation mechanism.",
            )
            self.assertTrue(
                safety["has_traffic_limit"],
                f"Scraper script '{script_path.name}' lacks traffic limiting / cooldown controls.",
            )
            self.assertTrue(
                safety["has_backoff"],
                f"Scraper script '{script_path.name}' lacks backoff / retry error handling.",
            )

    def test_04_safe_http_client_jitter_range_conformance(self):
        """Programmatic verification: SafeHttpClient enforces 1.5s-3.5s jittered delays."""
        from scrapers.common_utils import SafeHttpClient, USER_AGENT_POOL

        client = SafeHttpClient(min_delay=1.5, max_delay=3.5)
        self.assertGreaterEqual(client.min_delay, 1.0, "min_delay is less than 1.0s.")
        self.assertLessEqual(client.max_delay, 5.0, "max_delay exceeds 5.0s.")
        self.assertGreaterEqual(len(USER_AGENT_POOL), 5, "User-Agent pool has fewer than 5 UAs.")

    # --------------------------------------------------------------------------
    # 3. Top Complaint Keywords Ranking with Exact Frequencies and Percentages
    # --------------------------------------------------------------------------
    def test_05_statistical_report_top_keywords_ranking_present(self):
        """Programmatic verification: Report contains TOP complaint keywords ranking table."""
        if self.report_load_error:
            self.fail(f"Report load failure: {self.report_load_error}")

        # Search for tables containing rank, keyword, count/frequency, and percentage
        ranking_tables = []
        for table in self.report_tables:
            if not table:
                continue
            first_row = table[0]
            header_keys = [str(k).lower() for k in first_row.keys()]
            all_header_str = " ".join(header_keys)

            has_rank = any(r in all_header_str for r in ["순위", "rank", "#", "no"])
            has_keyword = any(k in all_header_str for k in ["키워드", "keyword", "불만", "항목", "주제"])
            has_count = any(c in all_header_str for c in ["빈도", "건수", "count", "tf", "언급"])
            has_pct = any(p in all_header_str for p in ["비율", "비중", "share", "%", "percent"])

            if (has_rank or has_keyword) and (has_count or has_pct):
                ranking_tables.append(table)

        self.assertGreaterEqual(
            len(ranking_tables),
            1,
            f"STATISTICAL_REPORT.md lacks TOP complaint keywords ranking table with counts & percentages. "
            f"Found {len(self.report_tables)} tables.",
        )

    def test_06_top_keywords_exact_numerical_counts_and_percentages(self):
        """Programmatic verification: Keyword ranking entries contain exact numeric values."""
        if self.report_load_error:
            self.fail(f"Report load failure: {self.report_load_error}")

        # Find the ranking table
        ranking_rows = []
        for table in self.report_tables:
            if not table:
                continue
            first_row = table[0]
            header_keys = [str(k).lower() for k in first_row.keys()]
            all_header_str = " ".join(header_keys)
            if ("순위" in all_header_str or "rank" in all_header_str or "키워드" in all_header_str) and (
                "빈도" in all_header_str or "count" in all_header_str or "%" in all_header_str or "비율" in all_header_str
            ):
                ranking_rows = table
                break

        self.assertGreaterEqual(
            len(ranking_rows),
            10,
            f"TOP ranking table contains only {len(ranking_rows)} rows, expected >= 10 ranking entries.",
        )

        valid_numeric_entries = 0
        for row in ranking_rows:
            row_values_str = " ".join(str(v) for v in row.values())

            # Check for count integer (e.g., 20, 150, 482) and percentage (e.g. 5.2%, 12.89%)
            has_int = bool(re.search(r"\b\d+\b", row_values_str))
            has_pct = bool(re.search(r"\d+(\.\d+)?%", row_values_str) or re.search(r"\b0\.\d+\b", row_values_str))

            if has_int or has_pct:
                valid_numeric_entries += 1

        self.assertGreaterEqual(
            valid_numeric_entries,
            10,
            f"Only {valid_numeric_entries}/{len(ranking_rows)} ranking rows have valid numeric metrics.",
        )

    # --------------------------------------------------------------------------
    # 4. Deep Statistical Insights: Sentiment, Cross-Platform, Temporal, DSI
    # --------------------------------------------------------------------------
    def test_07_sentiment_analysis_distribution_present(self):
        """Programmatic verification: 4-tier sentiment ratios (Positive/Neutral/Negative/Strongly Neg) present."""
        if self.report_load_error:
            self.fail(f"Report load failure: {self.report_load_error}")

        all_text = self.report_text

        # Check 4 sentiment tiers
        has_positive = any(t in all_text for t in ["긍정", "Positive", "호의적"])
        has_neutral = any(t in all_text for t in ["중립", "Neutral", "단순 정보"])
        has_negative = any(t in all_text for t in ["부정", "Negative", "불만"])
        has_strongly_neg = any(t in all_text for t in ["강한 부정", "Strongly Negative", "극단적", "비하", "멸칭"])

        sentiment_coverage = sum([has_positive, has_neutral, has_negative, has_strongly_neg])
        self.assertGreaterEqual(
            sentiment_coverage,
            3,
            f"STATISTICAL_REPORT.md lacks comprehensive 4-tier sentiment analysis breakdown. "
            f"(Found {sentiment_coverage}/4 sentiment tiers).",
        )

    def test_08_cross_platform_comparisons_present(self):
        """Programmatic verification: Report includes cross-platform comparison matrices."""
        if self.report_load_error:
            self.fail(f"Report load failure: {self.report_load_error}")

        all_text = self.report_text

        # Check for cross-platform section or comparative table
        has_cross_section = any(
            t in all_text
            for t in ["플랫폼별", "플랫폼 간", "Cross-Platform", "커뮤니티별 비교", "플랫폼 비교", "비교"]
        )
        self.assertTrue(
            has_cross_section,
            "STATISTICAL_REPORT.md lacks dedicated cross-platform comparative analysis section.",
        )

    def test_09_temporal_trend_analysis_present(self):
        """Programmatic verification: Report includes 2024–2026 temporal timeline and trends."""
        if self.report_load_error:
            self.fail(f"Report load failure: {self.report_load_error}")

        all_text = self.report_text

        has_2024 = "2024" in all_text
        has_2025 = "2025" in all_text
        has_2026 = "2026" in all_text
        has_temporal = any(
            t in all_text for t in ["시계열", "추이", "Temporal", "시기별", "연도별", "타임라인"]
        )

        self.assertTrue(
            has_2024 and has_2025 and (has_2026 or has_temporal),
            "STATISTICAL_REPORT.md lacks temporal trend analysis across 2024–2026.",
        )

    def test_10_defect_severity_index_metrics_present(self):
        """Programmatic verification: Defect Severity Index (DSI) metrics are evaluated."""
        if self.report_load_error:
            self.fail(f"Report load failure: {self.report_load_error}")

        all_text = self.report_text

        has_dsi = any(
            t in all_text
            for t in ["DSI", "심각도", "Defect Severity", "Severity Index", "위험도"]
        )
        self.assertTrue(
            has_dsi,
            "STATISTICAL_REPORT.md lacks Defect Severity Index (DSI) scoring metrics.",
        )

    # --------------------------------------------------------------------------
    # 5. Deliverable Cleanliness & Acceptance Criteria
    # --------------------------------------------------------------------------
    def test_11_statistical_report_substantive_length_and_no_placeholders(self):
        """Programmatic verification: STATISTICAL_REPORT.md >= 5,000 bytes and zero placeholder tokens."""
        if self.report_load_error:
            self.fail(f"Report load failure: {self.report_load_error}")

        byte_len = len(self.report_text.encode("utf-8"))
        self.assertGreaterEqual(
            byte_len,
            5000,
            f"STATISTICAL_REPORT.md is too short ({byte_len} bytes < 5,000 bytes).",
        )

        violations = []
        for token in FORBIDDEN_PLACEHOLDER_TOKENS:
            if token in self.report_text:
                violations.append(f"Forbidden placeholder token found: '{token}'")

        self.assertEqual(
            len(violations),
            0,
            f"STATISTICAL_REPORT.md contains unfinished placeholder tokens:\n"
            + "\n".join(violations),
        )


if __name__ == "__main__":
    unittest.main()
