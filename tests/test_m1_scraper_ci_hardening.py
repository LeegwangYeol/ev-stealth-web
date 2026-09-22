"""Unit tests for Milestone 1 Scraper & CI Hardening features.

Validates:
1. Desktop User-Agent pool enforcement (no mobile redirects).
2. Stage 1 question-suffix filtering (retaining authentic defects phrased with question markers).
3. Prospective buyer inquiry filtering.
4. Vehicle matcher regex collision prevention (BMW M3, English 'my', generic weatherstrip).
5. Scraper target board/gallery expansion.
6. Report merging and ID/URL deduplication in write_daily_reports().
7. Scraper pipeline graceful zero-harvest exit.
8. CI/CD workflow requirements, pip caching, and [skip ci] tagging.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) in sys.path:
    sys.path.remove(str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))

from filters.defect_filter import ContextualDefectFilter
from filters.vehicle_matcher import (
    BRAND_BYD,
    BRAND_OTHER,
    BRAND_TESLA,
    extract_vehicle_info,
)
from models.complaint import ComplaintRecord, RawPost
from run_scraper import ScraperPipeline, main as scraper_main
from utils.http_client import USER_AGENT_POOL
from utils.json_writer import read_daily_reports, write_daily_reports


class TestM1ScraperCIHardening(unittest.TestCase):
    """Test suite for Milestone 1 Python scraper & CI hardening tasks."""

    def setUp(self) -> None:
        self.defect_filter = ContextualDefectFilter()

    def test_desktop_user_agent_pool_enforcement(self) -> None:
        """Requirement 2: USER_AGENT_POOL must only contain modern desktop UAs and no mobile UAs."""
        self.assertGreaterEqual(len(USER_AGENT_POOL), 5, "Pool must contain at least 5 desktop UAs.")
        mobile_tokens = ["iPhone", "iPad", "Android", "Mobile"]
        for ua in USER_AGENT_POOL:
            for token in mobile_tokens:
                self.assertNotIn(
                    token,
                    ua,
                    f"Mobile token '{token}' found in User-Agent: {ua}",
                )
            # Must be macOS or Windows desktop browser
            self.assertTrue(
                "Macintosh" in ua or "Windows NT" in ua,
                f"User-Agent is not a recognised desktop UA: {ua}",
            )

    def test_stage1_retains_authentic_defect_questions(self) -> None:
        """Requirement 3: Authentic defect complaints ending with question markers must pass."""
        # Case 1: ICCU sudden shutdown on highway
        post1 = RawPost(
            platform="dcinside",
            post_id="t1",
            url="https://example.com/1",
            title="고속도로 멈춤",
            content="내 차 출고 3일만에 고속도로에서 100km 달리다 갑자기 퍽 소리나고 멈췄는데 이거 ICCU 결함인가요?",
            comments=[],
        )
        rec1 = self.defect_filter.process_post(post1)
        self.assertTrue(
            rec1.is_authentic_defect,
            f"Expected authentic defect for ICCU question, got: {rec1.filter_reason}",
        )

        # Case 2: Trunk water puddle
        post2 = RawPost(
            platform="dcinside",
            post_id="t2",
            url="https://example.com/2",
            title="트렁크 누수",
            content="내 차 테슬라 모델Y 비 오는 날 트렁크 바닥에 물이 흥건하게 고이는데 원래 이런가요?",
            comments=[],
        )
        rec2 = self.defect_filter.process_post(post2)
        self.assertTrue(
            rec2.is_authentic_defect,
            f"Expected authentic defect for trunk water leakage question, got: {rec2.filter_reason}",
        )

        # Case 3: Battery fire warning
        post3 = RawPost(
            platform="bobaedream",
            post_id="t3",
            url="https://example.com/3",
            title="충전 중 경고등",
            content="내 차 급속충전 중 배터리 온도 급상승하고 연기 나는데 이거 배터리 화재 위험인가요?",
            comments=[],
        )
        rec3 = self.defect_filter.process_post(post3)
        self.assertTrue(rec3.is_authentic_defect)

    def test_stage1_filters_pure_prospective_buyer_inquiries(self) -> None:
        """Requirement 3: Pure prospective buyer inquiries and advice queries must be filtered out."""
        buyer_queries = [
            "전기차 살까요 말까요? 모델Y 승차감 어떤가요? 궁금합니다.",
            "아이오닉5 vs EV6 고민중인데 어떤 차 살까요?",
            "테슬라 모델3 하이랜드 승차감 어떤가요?",
            "겨울철 전비 많이 떨어지나요? 구매 전 궁금합니다.",
        ]
        for query in buyer_queries:
            post = RawPost(
                platform="dcinside",
                post_id="b1",
                url="https://example.com/b1",
                title="구매 고민",
                content=query,
                comments=[],
            )
            rec = self.defect_filter.process_post(post)
            self.assertFalse(
                rec.is_authentic_defect,
                f"Expected non-defect for buyer inquiry '{query}', but was marked authentic.",
            )
            self.assertIn("inquiry", rec.filter_reason.lower())

    def test_vehicle_matcher_regex_collisions(self) -> None:
        """Requirement 4: Eliminate regex collisions for M3, MY, and generic seals."""
        # 1. BMW M3 must not match Tesla Model 3
        brand1, model1 = extract_vehicle_info("BMW M3 엔진오일 누유 및 결함")
        self.assertNotEqual(brand1, BRAND_TESLA)
        self.assertNotEqual(model1, "Model 3")
        self.assertEqual(brand1, BRAND_OTHER)

        # 2. English word 'my' must not match Tesla Model Y
        brand2, model2 = extract_vehicle_info("my car battery is dead")
        self.assertNotEqual(brand2, BRAND_TESLA)
        self.assertNotEqual(model2, "Model Y")
        self.assertEqual(brand2, BRAND_OTHER)
        self.assertEqual(model2, "전기차")

        # 3. Weatherstrip '도어 씰' must not match BYD Seal
        brand3, model3 = extract_vehicle_info("도어 씰 불량으로 트렁크 누수 발생")
        self.assertNotEqual(brand3, BRAND_BYD)
        self.assertNotEqual(model3, "씰")
        self.assertEqual(brand3, BRAND_OTHER)

        # 4. Valid Tesla Model 3 match
        brand4, model4 = extract_vehicle_info("테슬라 M3 하이랜드 시승 후기")
        self.assertEqual(brand4, BRAND_TESLA)
        self.assertEqual(model4, "Model 3 Highland")

        # 5. Valid Tesla Model Y match
        brand5, model5 = extract_vehicle_info("테슬라 모델Y 비 오는 날 트렁크 누수")
        self.assertEqual(brand5, BRAND_TESLA)
        self.assertEqual(model5, "Model Y")

        # 6. Valid Tesla MY with Korean particle
        brand6, model6 = extract_vehicle_info("MY는 승차감 어떤가요?")
        self.assertEqual(brand6, BRAND_TESLA)
        self.assertEqual(model6, "Model Y")

        # 7. Valid BYD Seal match
        brand7, model7 = extract_vehicle_info("BYD 씰 신차 출고 후기")
        self.assertEqual(brand7, BRAND_BYD)
        self.assertEqual(model7, "씰")

        # 8. Valid Seal EV match
        brand8, model8 = extract_vehicle_info("씰 EV 주행거리 및 전비 테스트")
        self.assertEqual(brand8, BRAND_BYD)
        self.assertEqual(model8, "씰")

    def test_run_scraper_board_expansion(self) -> None:
        """Requirement 5: BobaeDream and DCInside target boards/galleries must be expanded."""
        pipeline = ScraperPipeline()

        # Mock crawlers to inspect board/gallery arguments passed to them
        mock_bobae = MagicMock()
        mock_bobae.crawl_board.return_value = []
        mock_bobae.crawl_posts_by_keyword.return_value = []
        pipeline.bobae_crawler = mock_bobae

        mock_dc = MagicMock()
        mock_dc.crawl_gallery.return_value = []
        mock_dc.crawl_posts_by_keyword.return_value = []
        pipeline.dc_crawler = mock_dc

        pipeline.harvest_bobaedream(limit=10)
        crawled_boards = [call[0][0] for call in mock_bobae.crawl_board.call_args_list]
        self.assertEqual(crawled_boards, ["national", "electric", "import"])

        pipeline.harvest_dcinside(limit=10)
        crawled_galleries = [call[0][0] for call in mock_dc.crawl_gallery.call_args_list]
        self.assertEqual(crawled_galleries, ["car_new1", "electriccar", "tesla", "ioniq", "byd"])

    def test_write_daily_reports_merge_and_deduplication(self) -> None:
        """Requirement 5: write_daily_reports merges historical reports and deduplicates by ID/URL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = os.path.join(tmpdir, "daily_reports.json")

            initial_reports = [
                {
                    "id": "r1",
                    "url": "https://example.com/r1",
                    "title": "첫 번째 결함",
                    "defect_category": "BATTERY_CHARGING",
                    "severity": "CRITICAL",
                    "negativity_score": 0.90,
                },
                {
                    "id": "r2",
                    "url": "https://example.com/r2",
                    "title": "두 번째 결함",
                    "defect_category": "BUILD_QUALITY",
                    "severity": "WARNING",
                    "negativity_score": 0.80,
                },
            ]

            # 1. Initial write
            write_daily_reports(initial_reports, output_path=out_file, total_scraped=50)
            data1 = read_daily_reports(out_file)
            self.assertEqual(len(data1["reports"]), 2)
            self.assertEqual(data1["statistics"]["total_scraped"], 50)

            # 2. Second write with one existing updated report (same ID) and one new report
            second_batch = [
                {
                    "id": "r1",
                    "url": "https://example.com/r1",
                    "title": "첫 번째 결함 업데이트",
                    "defect_category": "BATTERY_CHARGING",
                    "severity": "CRITICAL",
                    "negativity_score": 0.95,
                },
                {
                    "id": "r3",
                    "url": "https://example.com/r3",
                    "title": "세 번째 신규 결함",
                    "defect_category": "DRIVING_POWERTRAIN",
                    "severity": "CAUTION",
                    "negativity_score": 0.70,
                },
            ]

            write_daily_reports(second_batch, output_path=out_file, total_scraped=30, merge_existing=True)
            data2 = read_daily_reports(out_file)

            # Should have exactly 3 unique reports (r1 updated, r3 new, r2 preserved)
            self.assertEqual(len(data2["reports"]), 3)
            self.assertEqual(data2["statistics"]["total_scraped"], 80)

            report_ids = [r["id"] for r in data2["reports"]]
            self.assertIn("r1", report_ids)
            self.assertIn("r2", report_ids)
            self.assertIn("r3", report_ids)

            # Check r1 was updated
            r1_item = next(r for r in data2["reports"] if r["id"] == "r1")
            self.assertEqual(r1_item["title"], "첫 번째 결함 업데이트")
            self.assertEqual(r1_item["negativity_score"], 0.95)

    def test_run_scraper_zero_harvest_graceful_exit(self) -> None:
        """Requirement 5: run_scraper exits with code 0 (not 1) when 0 posts are harvested."""
        with patch("run_scraper.ScraperPipeline.run", return_value={"total_scraped": 0, "written_paths": []}):
            exit_code = scraper_main(["--dry-run"])
            self.assertEqual(exit_code, 0, "Expected exit code 0 on graceful zero-harvest.")

    def test_ci_cd_workflow_hardening(self) -> None:
        """Requirement 6: Verify daily-scraper.yml, requirements.txt, and .gitignore specifications."""
        project_root = Path(__file__).resolve().parent.parent
        wf_path = project_root / ".github" / "workflows" / "daily-scraper.yml"
        self.assertTrue(wf_path.exists(), "Workflow file must exist.")

        content = wf_path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)

        # Check options do not contain 'blind'
        on_cfg = parsed.get("on") or parsed.get(True)
        wf_dispatch = on_cfg.get("workflow_dispatch", {})
        mode_options = wf_dispatch.get("inputs", {}).get("mode", {}).get("options", [])
        self.assertNotIn("blind", mode_options, "'blind' mode must be removed from workflow options.")

        # Check python setup has pip cache
        job = parsed.get("jobs", {}).get("scrape-and-publish", {})
        steps = job.get("steps", [])
        setup_step = next((s for s in steps if s.get("uses") == "actions/setup-python@v5"), None)
        self.assertIsNotNone(setup_step)
        self.assertEqual(setup_step.get("with", {}).get("cache"), "pip")

        # Check unittest verification step exists
        unittest_step = next((s for s in steps if "unittest" in s.get("run", "")), None)
        self.assertIsNotNone(unittest_step, "Workflow must contain a unit test verification step.")

        # Check [skip ci] in commit message
        commit_step = next((s for s in steps if "git commit" in s.get("run", "")), None)
        self.assertIsNotNone(commit_step)
        self.assertIn("[skip ci]", commit_step.get("run", ""))

        # Check requirements.txt
        req_path = project_root / "requirements.txt"
        self.assertTrue(req_path.exists(), "requirements.txt must exist.")
        req_content = req_path.read_text(encoding="utf-8")
        self.assertIn("pytest>=8.0.0", req_content)
        self.assertIn("pyyaml>=6.0.0", req_content)

        # Check .gitignore
        ignore_path = project_root / ".gitignore"
        self.assertTrue(ignore_path.exists(), ".gitignore must exist.")
        ignore_content = ignore_path.read_text(encoding="utf-8")
        self.assertIn("__pycache__/", ignore_content)
        self.assertIn(".pytest_cache/", ignore_content)
        self.assertIn("node_modules/", ignore_content)
        self.assertIn(".next/", ignore_content)
        self.assertIn(".agents/", ignore_content)


if __name__ == "__main__":
    unittest.main()
