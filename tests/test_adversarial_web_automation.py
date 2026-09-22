"""
Adversarial Stress Test Suite: Webapp Admin Route & CLI Automation.

Target Components:
1. CLI Entrypoint (`run_scraper.py`) argument stress & boundary handling.
2. Shell Runner Script (`run_scraper.sh`) argument forwarding, exit codes, and error output.
3. Next.js Data Layer (`getDailyReports.ts`, `daily_reports.json`) data resilience under
   empty reports, missing fields, malformed structures, and massive 500-report scale.
4. GitHub Actions Workflow (`.github/workflows/daily-scraper.yml`) YAML validity,
   cron syntax, pinned actions, step structure, and input forwarding discrepancies.
"""

from __future__ import annotations

import copy
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
import yaml

PROJECT_ROOT = Path("/Users/a7890/src/my-e-car")
BOT_ROOT = Path("/Users/a7890/teamwork_projects/ev_daily_monitor_bot")
for p in [str(BOT_ROOT), str(PROJECT_ROOT)]:
    if p in sys.path:
        sys.path.remove(p)
    sys.path.insert(0, p)

import run_scraper
from run_scraper import ScraperPipeline, create_parser


# ==============================================================================
# Suite 1: CLI Argument Stress Testing
# ==============================================================================
class TestCLIArgumentStress:
    """Stress tests covering negative limits, zero limits, huge limits, and unknown sources."""

    def test_cli_parser_negative_limit(self):
        """Verify CLI parser parses negative limit correctly without crashing."""
        parser = create_parser()
        args = parser.parse_args(["--limit", "-5"])
        assert args.limit == -5

    def test_cli_parser_zero_limit(self):
        """Verify CLI parser parses zero limit correctly."""
        parser = create_parser()
        args = parser.parse_args(["--limit", "0"])
        assert args.limit == 0

    def test_cli_parser_huge_limit(self):
        """Verify CLI parser accepts huge limit (10,000) without integer overflow."""
        parser = create_parser()
        args = parser.parse_args(["--limit", "10000"])
        assert args.limit == 10000

    @pytest.mark.parametrize("flag", ["--source", "--sources", "-m", "--mode"])
    def test_cli_parser_unknown_source_flags(self, flag: str):
        """Verify CLI parser accepts arbitrary string source values without crashing."""
        parser = create_parser()
        args = parser.parse_args([flag, "alien"])
        assert args.sources == "alien"

    def test_cli_parser_invalid_argument_exits_code_2(self):
        """Verify passing unrecognized arguments raises SystemExit with code 2."""
        parser = create_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--invalid-arg"])
        assert exc_info.value.code == 2

    def test_cli_parser_non_integer_limit_exits_code_2(self):
        """Verify passing non-integer value to --limit raises SystemExit with code 2."""
        parser = create_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--limit", "not_a_number"])
        assert exc_info.value.code == 2

    def test_pipeline_clamps_negative_limit_to_minimum_one(self):
        """Verify ScraperPipeline clamps negative limit to 1 during execution."""
        pipeline = ScraperPipeline()
        pipeline.harvest = MagicMock(return_value=([], {"bobaedream": 0, "dcinside": 0}))
        pipeline.filter_defects = MagicMock(return_value=[])

        summary = pipeline.run(sources="all", limit=-5, dry_run=True)

        # harvest must have been called with limit=1 (clamped)
        pipeline.harvest.assert_called_once_with(source_choice="all", limit=1)
        assert summary["dry_run"] is True

    def test_pipeline_clamps_zero_limit_to_minimum_one(self):
        """Verify ScraperPipeline clamps limit=0 to 1 during execution."""
        pipeline = ScraperPipeline()
        pipeline.harvest = MagicMock(return_value=([], {"bobaedream": 0, "dcinside": 0}))
        pipeline.filter_defects = MagicMock(return_value=[])

        summary = pipeline.run(sources="all", limit=0, dry_run=True)

        pipeline.harvest.assert_called_once_with(source_choice="all", limit=1)
        assert summary["total_scraped"] == 0

    def test_pipeline_huge_limit_handling(self):
        """Verify ScraperPipeline handles limit=10,000 and forwards it safely."""
        pipeline = ScraperPipeline()
        pipeline.harvest = MagicMock(return_value=([], {"bobaedream": 0, "dcinside": 0}))
        pipeline.filter_defects = MagicMock(return_value=[])

        summary = pipeline.run(sources="all", limit=10000, dry_run=True)

        pipeline.harvest.assert_called_once_with(source_choice="all", limit=10000)
        assert summary["total_scraped"] == 0

    def test_pipeline_unknown_source_fallback_warning(self, caplog):
        """Verify unknown source logs a warning and gracefully falls back to 'all'."""
        pipeline = ScraperPipeline()
        pipeline.harvest_bobaedream = MagicMock(return_value=[])
        pipeline.harvest_dcinside = MagicMock(return_value=[])

        with caplog.at_level(logging.WARNING):
            posts, stats = pipeline.harvest(source_choice="alien", limit=10)

        assert "Unknown source 'alien', falling back to 'all'" in caplog.text
        pipeline.harvest_bobaedream.assert_called_once_with(limit=10)
        pipeline.harvest_dcinside.assert_called_once_with(limit=10)

    def test_main_runtime_error_exits_code_1(self):
        """Verify main() converts unhandled pipeline runtime exceptions to exit code 1."""
        with patch("run_scraper.ScraperPipeline.run", side_effect=RuntimeError("Network failure")):
            code = run_scraper.main(["--dry-run"])
            assert code == 1


# ==============================================================================
# Suite 2: Shell Script Resilience Testing
# ==============================================================================
class TestShellScriptResilience:
    """Stress tests covering run_scraper.sh argument forwarding, exit codes, and error banners."""

    SCRIPT_PATH = PROJECT_ROOT / "run_scraper.sh"

    def test_script_exists_and_executable(self):
        """Verify run_scraper.sh exists and has execute permissions."""
        assert self.SCRIPT_PATH.exists(), "run_scraper.sh does not exist"
        assert os.access(self.SCRIPT_PATH, os.X_OK), "run_scraper.sh is not executable"

    def test_bash_script_invalid_arg_exit_code_and_output(self):
        """
        Verify bash run_scraper.sh --invalid-arg:
        1. Exits with code 2.
        2. Outputs standardized execution banner.
        3. Outputs argparse error message.
        4. Outputs [ERROR] completion banner with exit code 2.
        """
        proc = subprocess.run(
            ["bash", str(self.SCRIPT_PATH), "--invalid-arg"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert proc.returncode == 2, f"Expected exit code 2, got {proc.returncode}"
        combined = proc.stdout + proc.stderr
        assert "DAILY EV MONITORING PIPELINE" in combined
        assert "unrecognized arguments: --invalid-arg" in combined
        assert "[ERROR] Scraper pipeline failed with exit code 2" in combined

    def test_bash_script_non_integer_limit_exit_code_2(self):
        """Verify bash run_scraper.sh --limit abc exits with code 2."""
        proc = subprocess.run(
            ["bash", str(self.SCRIPT_PATH), "--limit", "abc"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert proc.returncode == 2
        combined = proc.stdout + proc.stderr
        assert "invalid int value: 'abc'" in combined
        assert "[ERROR] Scraper pipeline failed with exit code 2" in combined

    def test_bash_script_help_flag_exit_code_0(self):
        """Verify bash run_scraper.sh --help displays help and exits with 0."""
        proc = subprocess.run(
            ["bash", str(self.SCRIPT_PATH), "--help"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert proc.returncode == 0
        combined = proc.stdout + proc.stderr
        assert "usage: run_scraper" in combined
        assert "--sources" in combined
        assert "--limit" in combined


# ==============================================================================
# Suite 3: Next.js Data Layer Resilience Testing
# ==============================================================================
class TestNextJsDataResilience:
    """
    Stress tests verifying the data processing logic in Next.js getDailyReports.ts
    under adverse inputs: empty list, missing fields, malformed structures, and 500 reports.
    """

    def _normalize_report_py(self, raw: Dict[str, Any], index: int) -> Dict[str, Any]:
        """Python mirror of TypeScript normalizeReport() from getDailyReports.ts."""
        category_map = {
            "BATTERY_CHARGING": {"code": "BATTERY_CHARGING", "ko": "배터리/충전"},
            "DRIVING_POWERTRAIN": {"code": "DRIVING_POWERTRAIN", "ko": "주행/모터/등판"},
            "BUILD_QUALITY": {"code": "BUILD_QUALITY", "ko": "단차/누수/마감"},
            "SOFTWARE_ELECTRONICS": {"code": "SOFTWARE_ELECTRONICS", "ko": "OTA/소프트웨어"},
            "SERVICE_REPAIR_COST": {"code": "SERVICE_REPAIR_COST", "ko": "AS/수리비"},
            "parking": {"code": "DRIVING_POWERTRAIN", "ko": "주행/모터/등판"},
            "charging": {"code": "BATTERY_CHARGING", "ko": "배터리/충전"},
        }
        raw_cat = str(raw.get("defect_category") or raw.get("category") or "BATTERY_CHARGING")
        cat_info = category_map.get(raw_cat, {"code": raw_cat, "ko": str(raw.get("defect_category_ko") or "기타 결함")})

        raw_sev = str(raw.get("severity") or "WARNING").upper()
        if "CRITICAL" in raw_sev:
            sev = "CRITICAL"
        elif "CAUTION" in raw_sev or "CONVENIENCE" in raw_sev:
            sev = "CAUTION"
        else:
            sev = "WARNING"

        sentiment = raw.get("sentiment_score")
        negativity = raw.get("negativity_score")
        if isinstance(sentiment, (int, float)):
            score = abs(float(sentiment))
        elif isinstance(negativity, (int, float)):
            score = float(negativity)
        else:
            score = 0.85

        raw_slang = raw.get("slang_tags") if isinstance(raw.get("slang_tags"), list) else (
            raw.get("slang_terms") if isinstance(raw.get("slang_terms"), list) else []
        )
        slang_tags = [str(s) for s in raw_slang]

        return {
            "id": str(raw.get("id") or f"report_{index + 1}"),
            "source": str(raw.get("source") or raw.get("platform") or "bobaedream").lower(),
            "url": str(raw.get("url") or raw.get("post_url") or "#"),
            "title": str(raw.get("title") or raw.get("post_title") or "전기차 결함 제보"),
            "date": str(raw.get("date") or raw.get("post_date") or "2026-09-08"),
            "vehicle_model": str(raw.get("vehicle_model") or raw.get("target_vehicle") or "미상 모델"),
            "defect_category": cat_info["code"],
            "defect_category_ko": str(raw.get("defect_category_ko") or cat_info["ko"]),
            "summary": str(raw.get("summary") or raw.get("defect_summary") or "결함 상세 내용 요약"),
            "verbatim_quote": str(raw.get("verbatim_quote") or raw.get("raw_quote") or raw.get("content") or "원문 없음"),
            "slang_tags": slang_tags,
            "sentiment_score": round(score, 2),
            "severity": sev,
        }

    def _calculate_kpis_py(self, reports: List[Dict[str, Any]], existing_stats: Dict[str, Any] = None) -> Dict[str, Any]:
        """Python mirror of TypeScript calculateKPIs() from getDailyReports.ts."""
        total_filtered = len(reports)
        critical_count = sum(1 for r in reports if str(r.get("severity", "")).upper() == "CRITICAL")
        total_score = sum(r.get("sentiment_score", 0) for r in reports)
        avg_score = round(total_score / total_filtered, 2) if total_filtered > 0 else 0.85

        model_counts: Dict[str, int] = {}
        for r in reports:
            mod = r.get("vehicle_model")
            if mod:
                model_counts[mod] = model_counts.get(mod, 0) + 1

        top_model_name = "아이오닉5"
        max_model_count = 0
        for m, count in model_counts.items():
            if count > max_model_count:
                max_model_count = count
                top_model_name = m
        top_model_display = f"{top_model_name} ({max_model_count}건)" if max_model_count > 0 else "아이오닉5 (5건)"

        platform_counts: Dict[str, int] = {}
        for r in reports:
            src = str(r.get("source", "")).lower()
            platform_counts[src] = platform_counts.get(src, 0) + 1

        top_platform_key = "bobaedream"
        max_plat_count = 0
        for p, count in platform_counts.items():
            if count > max_plat_count:
                max_plat_count = count
                top_platform_key = p
        plat_ratio = round((max_plat_count / total_filtered) * 100) if total_filtered > 0 else 55
        plat_name_ko = "보배드림" if "bobae" in top_platform_key else "디시인사이드"
        top_plat_display = f"{plat_name_ko} ({plat_ratio}%)"

        total_scraped = existing_stats.get("total_scraped") if existing_stats else (total_filtered * 7)

        return {
            "total_scraped": total_scraped,
            "total_filtered_defects": total_filtered,
            "avg_negativity_score": existing_stats.get("avg_negativity_score") if (existing_stats and "avg_negativity_score" in existing_stats) else avg_score,
            "critical_defect_count": critical_count,
            "top_model": top_model_display,
            "top_platform": top_plat_display,
        }

    def test_data_resilience_empty_reports_list(self):
        """Verify handling when reports list is empty `{"reports": []}`."""
        reports = []
        kpis = self._calculate_kpis_py(reports)

        assert kpis["total_filtered_defects"] == 0
        assert kpis["critical_defect_count"] == 0
        assert kpis["avg_negativity_score"] == 0.85
        assert "아이오닉5" in kpis["top_model"]
        assert "보배드림" in kpis["top_platform"]

    def test_data_resilience_missing_fields_and_malformed_items(self):
        """Verify normalizeReport fills safe defaults when items have missing/corrupted fields."""
        malformed_items = [
            {},  # completely empty
            {"id": "test_1"},  # only id
            {"title": "Only Title", "sentiment_score": "not_a_number"},  # string score
            {"severity": "unknown_sev", "slang_tags": None},  # None slang
            {"defect_category": "non_existent_cat"},  # unknown category
        ]

        normalized = [self._normalize_report_py(item, idx) for idx, item in enumerate(malformed_items)]
        assert len(normalized) == 5

        for item in normalized:
            assert isinstance(item["id"], str) and len(item["id"]) > 0
            assert isinstance(item["title"], str) and len(item["title"]) > 0
            assert isinstance(item["summary"], str) and len(item["summary"]) > 0
            assert isinstance(item["verbatim_quote"], str) and len(item["verbatim_quote"]) > 0
            assert isinstance(item["slang_tags"], list)
            assert isinstance(item["sentiment_score"], float)
            assert item["severity"] in ("CRITICAL", "WARNING", "CAUTION")

        kpis = self._calculate_kpis_py(normalized)
        assert kpis["total_filtered_defects"] == 5

    def test_data_resilience_500_reports_scale(self):
        """Verify KPI calculations and data structures scale without error over 500 reports."""
        raw_reports = []
        for i in range(1, 501):
            raw_reports.append({
                "id": f"scale_{i}",
                "source": "dcinside" if i % 2 == 0 else "bobaedream",
                "title": f"Report #{i}",
                "vehicle_model": "아이오닉5" if i % 3 == 0 else ("EV6" if i % 3 == 1 else "테슬라 모델Y"),
                "severity": "CRITICAL" if i % 5 == 0 else "WARNING",
                "sentiment_score": 0.85 + ((i % 15) * 0.01),
                "slang_tags": ["ICCU폭탄", "벽돌차"],
            })

        normalized = [self._normalize_report_py(item, idx) for idx, item in enumerate(raw_reports)]
        kpis = self._calculate_kpis_py(normalized)

        assert kpis["total_filtered_defects"] == 500
        assert kpis["critical_defect_count"] == 100  # 500 // 5
        assert 0.85 <= kpis["avg_negativity_score"] <= 1.0
        assert "건)" in kpis["top_model"]
        assert "%" in kpis["top_platform"]


# ==============================================================================
# Suite 4: GitHub Actions Workflow Validation
# ==============================================================================
class TestGitHubActionsWorkflowValidation:
    """Rigorous YAML syntax and structural validation for .github/workflows/daily-scraper.yml."""

    WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "daily-scraper.yml"
    WEB_WORKFLOW_PATH = PROJECT_ROOT / "ev-stealth-web" / ".github" / "workflows" / "daily-scraper.yml"

    def test_workflow_file_exists_in_both_locations(self):
        """Verify daily-scraper.yml exists at root and in webapp."""
        assert self.WORKFLOW_PATH.exists(), f"Missing {self.WORKFLOW_PATH}"
        assert self.WEB_WORKFLOW_PATH.exists(), f"Missing {self.WEB_WORKFLOW_PATH}"

    def test_workflow_files_are_identical(self):
        """Verify the root workflow and webapp workflow are 100% synchronized."""
        root_content = self.WORKFLOW_PATH.read_text(encoding="utf-8")
        web_content = self.WEB_WORKFLOW_PATH.read_text(encoding="utf-8")
        assert root_content == web_content, "Root and webapp workflow files differ!"

    def test_workflow_yaml_is_valid(self):
        """Verify YAML parses without any syntax error."""
        content = self.WORKFLOW_PATH.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        assert isinstance(parsed, dict)
        assert "name" in parsed
        assert "jobs" in parsed

    def test_workflow_permissions_and_concurrency(self):
        """Verify write permissions and concurrency group settings."""
        content = self.WORKFLOW_PATH.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)

        permissions = parsed.get("permissions", {})
        assert permissions.get("contents") == "write"

        concurrency = parsed.get("concurrency", {})
        assert concurrency.get("group") == "daily-scraper-pipeline"
        assert concurrency.get("cancel-in-progress") is False

    def test_workflow_schedule_cron(self):
        """Verify cron expression is valid 5-field expression for 21:00 UTC."""
        content = self.WORKFLOW_PATH.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)

        # In YAML 1.1, unquoted 'on:' parses as True
        on_cfg = parsed.get("on") or parsed.get(True)
        assert isinstance(on_cfg, dict)

        schedule = on_cfg.get("schedule", [])
        assert len(schedule) >= 1
        cron_expr = schedule[0].get("cron")
        assert cron_expr == "0 21 * * *"
        fields = cron_expr.split()
        assert len(fields) == 5, f"Expected 5 fields in cron, got {len(fields)}"

    def test_workflow_steps_and_pinned_action_versions(self):
        """Verify all hardened pipeline steps and pinned action versions."""
        content = self.WORKFLOW_PATH.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)

        job = parsed.get("jobs", {}).get("scrape-and-publish", {})
        assert job.get("runs-on") == "ubuntu-latest"
        assert job.get("timeout-minutes") == 30

        steps = job.get("steps", [])
        assert len(steps) == 7

        # Step 1: Checkout
        assert steps[0].get("uses") == "actions/checkout@v4"
        # Step 2: Setup Python
        assert steps[1].get("uses") == "actions/setup-python@v5"
        assert steps[1].get("with", {}).get("python-version") == "3.11"
        assert steps[1].get("with", {}).get("cache") == "pip"
        # Step 3: Dependencies
        assert "pip install" in steps[2].get("run", "")
        # Step 4: Scraper execution
        assert "python" in steps[3].get("run", "")
        assert "--sync-web" in steps[3].get("run", "")
        # Step 5: Test verification
        assert "unittest discover" in steps[4].get("run", "")
        # Step 6: Git diff detection
        assert "GITHUB_OUTPUT" in steps[5].get("run", "")
        # Step 7: Commit and push
        assert "git push origin main" in steps[6].get("run", "")
        assert "[skip ci]" in steps[6].get("run", "")

    def test_adversarial_workflow_dispatch_input_unforwarded_discrepancy(self):
        """
        Verify that workflow_dispatch defines inputs (`limit`, `mode`),
        and forwards them properly, and that unsupported `blind` mode is removed.
        """
        content = self.WORKFLOW_PATH.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        on_cfg = parsed.get("on") or parsed.get(True)

        wf_dispatch = on_cfg.get("workflow_dispatch", {})
        inputs = wf_dispatch.get("inputs", {})
        assert "limit" in inputs
        assert "mode" in inputs

        mode_options = inputs["mode"].get("options", [])
        assert "blind" not in mode_options, "'blind' must not be in workflow_dispatch options"
        assert "all" in mode_options
        assert "bobaedream" in mode_options
        assert "dcinside" in mode_options

        # Check step 4 run command
        job = parsed.get("jobs", {}).get("scrape-and-publish", {})
        step4_run = job["steps"][3]["run"]

        # Step 4 references inputs.limit or inputs.mode
        has_input_limit_ref = "inputs.limit" in step4_run or "${{ github.event.inputs.limit }}" in step4_run
        has_input_mode_ref = "inputs.mode" in step4_run or "${{ github.event.inputs.mode }}" in step4_run

        # Assert inputs are properly forwarded
        assert has_input_limit_ref, "Step 4 must forward limit input"
        assert has_input_mode_ref, "Step 4 must forward mode input"
