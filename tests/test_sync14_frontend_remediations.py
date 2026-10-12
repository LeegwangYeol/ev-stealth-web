"""
tests/test_sync14_frontend_remediations.py - Verification tests for Cycle 14 Frontend Logic & Component Remediations.

Validates:
1. SubsidyTrackerClient: Prevents safeAnnounced denominator safeguard from leaking into display text when announced quota is 0 (shows 0대).
2. DepreciationCalculatorClient: Clean zero-data empty-state in vehicle model grid; dynamically computed and clearly labeled EV Automobile Tax in 5-year TCO table.
3. RecallPortalClient: Clean zero-data empty-states in Battery Directory and Recalls Catalog; fallback for unmapped model names in VIN Mode A.
"""

from __future__ import annotations

import re
from pathlib import Path
import unittest

WEB_ROOT = Path(__file__).resolve().parent.parent


class TestSync14FrontendRemediations(unittest.TestCase):
    def setUp(self):
        self.subsidy_client_path = WEB_ROOT / "src" / "app" / "subsidy-tracker" / "SubsidyTrackerClient.tsx"
        self.depreciation_client_path = WEB_ROOT / "src" / "app" / "depreciation-calculator" / "DepreciationCalculatorClient.tsx"
        self.recall_client_path = WEB_ROOT / "src" / "app" / "recall-portal" / "RecallPortalClient.tsx"

        self.assertTrue(self.subsidy_client_path.exists(), f"Missing {self.subsidy_client_path}")
        self.assertTrue(self.depreciation_client_path.exists(), f"Missing {self.depreciation_client_path}")
        self.assertTrue(self.recall_client_path.exists(), f"Missing {self.recall_client_path}")

        self.subsidy_code = self.subsidy_client_path.read_text(encoding="utf-8")
        self.depreciation_code = self.depreciation_client_path.read_text(encoding="utf-8")
        self.recall_code = self.recall_client_path.read_text(encoding="utf-8")

    def test_subsidy_tracker_safe_announced_does_not_leak_into_display(self):
        """Verify safeAnnounced denominator safeguard does not leak into user-facing count."""
        # announcedUnits must be defined separately from safeAnnounced divisor
        self.assertIn("announcedUnits", self.subsidy_code)
        self.assertIn("safeAnnounced", self.subsidy_code)

        # Display text must use announcedUnits.toLocaleString(), not safeAnnounced
        display_pattern = re.compile(
            r"잔여\s*<strong[^>]*>\{safeRemaining\.toLocaleString\(\)\}<\/strong>\s*\/\s*\{announcedUnits\.toLocaleString\(\)\}대"
        )
        self.assertTrue(
            display_pattern.search(self.subsidy_code),
            "Display text in RegionCard must use {announcedUnits.toLocaleString()}대 so 0 announced displays as 0대"
        )
        # Verify safeAnnounced is NOT used in the display span
        leaked_pattern = re.compile(
            r"잔여\s*<strong[^>]*>\{safeRemaining\.toLocaleString\(\)\}<\/strong>\s*\/\s*\{safeAnnounced\.toLocaleString\(\)\}대"
        )
        self.assertFalse(
            leaked_pattern.search(self.subsidy_code),
            "safeAnnounced divisor must not leak into user-facing count display"
        )

    def test_depreciation_model_grid_empty_state(self):
        """Verify zero-data empty-state is implemented when model search returns 0 items."""
        self.assertIn("filteredModels.length === 0", self.depreciation_code)
        self.assertIn("일치하는 전기차 모델이 없습니다", self.depreciation_code)
        self.assertIn("검색어 및 제조사 필터 초기화", self.depreciation_code)

    def test_depreciation_tco_table_automobile_tax_labeled_and_computed(self):
        """Verify EV Automobile Tax in 5-year TCO table is clearly labeled and computed dynamically."""
        # Check header label
        self.assertIn("<th scope=\"col\" className=\"py-2.5 px-3 font-bold\">EV 자동차세</th>", self.depreciation_code)
        self.assertIn("<th scope=\"col\" className=\"py-2.5 px-3 font-bold\">내연기관 자동차세</th>", self.depreciation_code)

        # Check dynamic cell computation
        self.assertIn("row.evAutomobileTaxKrw", self.depreciation_code)
        # Ensure it is not hardcoded to static '13만원' in the row rendering
        hardcoded_tax_cell = re.search(r"<td className=\"py-2 px-3\">\s*13만원\s*<\/td>", self.depreciation_code)
        self.assertIsNone(hardcoded_tax_cell, "EV Automobile Tax must not be hardcoded to static '13만원' in TCO table rows")

    def test_recall_portal_battery_directory_empty_state(self):
        """Verify Battery Directory has clean zero-data empty-state notification."""
        self.assertIn("filteredBatteryProfiles.length === 0", self.recall_code)
        self.assertIn("조건에 일치하는 배터리 제조사 정보가 없습니다", self.recall_code)

    def test_recall_portal_recalls_catalog_empty_state(self):
        """Verify Recalls Catalog has clean zero-data empty-state notification."""
        self.assertIn("filteredRecalls.length === 0", self.recall_code)
        self.assertIn("일치하는 공시 리콜 및 무상수리 내역이 없습니다", self.recall_code)

    def test_recall_portal_vin_mode_a_model_fallback(self):
        """Verify Mode A VIN check display contains fallback for unmapped model names."""
        # decodedModel fallback in result heading
        heading_fallback_pattern = re.compile(
            r"\{checkResult\.decodedModel\?\.trim\(\)\s*\?\s*checkResult\.decodedModel\s*:\s*['\"]미확인 모델['\"]\}"
        )
        self.assertTrue(
            heading_fallback_pattern.search(self.recall_code),
            "RecallPortalClient must provide fallback for unmapped model in VIN Mode A heading"
        )
        # Advisory note for unmapped VIN model
        self.assertIn("checkResult.mode === 'VIN' && !checkResult.decodedModel", self.recall_code)


if __name__ == "__main__":
    unittest.main()
