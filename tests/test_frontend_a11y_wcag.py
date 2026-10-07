"""
tests/test_frontend_a11y_wcag.py - Automated WCAG 2.1 Level AA Accessibility Regression Test Suite.

Authoritative Sources:
- ORIGINAL_REQUEST.md (WCAG AA accessibility mandates across EV Stealth Web)
- PROJECT.md (§ Architecture, Interface Contracts, Code Layout, Acceptance Criteria)
- .agents/explorer_a11y_w1/handoff.md & .agents/explorer_a11y_w1_d3/handoff.md
- .agents/explorer_frontend_w1_d3/handoff.md
- W3C Web Content Accessibility Guidelines (WCAG) 2.1:
  * SC 1.3.1 Info and Relationships Level A (Landmarks, unique IDs, semantic grouping)
  * SC 1.4.3 Contrast (Minimum) Level AA (4.5:1 for normal text, 3:1 for large text)
  * SC 1.4.11 Non-text Contrast Level AA (3:1 for UI components and graphical objects)
  * SC 2.4.7 Focus Visible Level AA (Keyboard focus indicator visible)
  * SC 3.3.1 Error Identification Level A/AA (Programmatically determinable errors)
  * SC 4.1.2 Name, Role, Value Level A/AA (Exposing roles and state via ARIA)
- WAI-ARIA 1.2 Patterns (Progressbar, Disclosure/Accordion, Tabs, Radio Group)

Test Scope & Invariants:
1. PdiChecklistClient.tsx:
   - Verifies eradication of low-contrast text-gray-400 on checked checklist tasks and warnings.
   - Verifies inclusion of role="progressbar", aria-valuenow, aria-valuemin, aria-valuemax, and accessible name.
   - Verifies zero-length items guard preventing division by zero and NaN% display.
2. RecallPortalClient.tsx:
   - Verifies eradication of duplicate nested <main> landmark inside layout.tsx's main container.
   - Verifies disambiguated, collision-free IDs across search result and general recall accordion containers.
   - Verifies replacement of low-contrast placeholder-slate-500 with placeholder-slate-400 across all inputs.
   - Verifies aria-expanded and aria-controls on campaign accordion toggle buttons, with matching target IDs.
   - Verifies aria-invalid and aria-describedby linkage on 17-digit VIN input with matching error feedback element ID.
   - Verifies external link target="_blank" accessibility notifications (sr-only).
   - Verifies tablist, tab, and tabpanel ARIA roles and state for mode switcher.
3. DepreciationCalculatorClient.tsx:
   - Verifies circular Battery State of Health (SoH) meter exposes role="progressbar", aria-valuenow, aria-valuemin, aria-valuemax, and aria-label.
   - Verifies selected model card pricing color text-blue-700 (> 4.5:1 on bg-blue-50) replacing text-blue-600.
   - Verifies TCO cumulative savings banner uses high-contrast text-white font-medium rather than low-contrast text-blue-200/100.
   - Verifies wrapping of transfer type radio option groups in semantic <fieldset> with accessible <legend>.
4. ReliabilityDashboardClient.tsx:
   - Verifies eradication of low-contrast text-slate-300 on bg-slate-100 empty cells, replaced by compliant text-slate-600/700.
   - Verifies accessible role="region" and role="img" labels on defect distribution proportional bar.
5. layout.tsx:
   - Verifies desktop navigation bar links contain visible focus ring classes (focus:ring-2, focus:outline-none).
6. SubsidyTrackerClient.tsx:
   - Verifies aria-expanded and aria-controls on municipality accordion toggles with matching container IDs.
   - Verifies WCAG-compliant progressbar semantics on subsidy depletion visual tracks.
7. ev_recall_database.json Integrity:
   - Verifies complete coverage for Tesla Model 3 (LRW3E7EK prefix) in vin_prefixes and battery_profiles.
   - Verifies battery profile schema conformance (cell supplier, chemistry, SoC limit, underground parking advisory).
8. Mathematical Contrast Calculations:
   - Evaluates sRGB relative luminance and contrast ratio formulas to mathematically verify compliant vs failing pairings.
9. Adversarial Verification:
   - Verifies syntactic integrity, boundary invariant checks (0 <= valuenow <= 100), and non-empty accessible labels.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import sys
import unittest
from typing import Dict, List, Optional, Set, Tuple

# Base paths
def _find_web_app_root() -> Path:
    candidates = [
        Path(__file__).resolve().parent.parent / "ev-stealth-web",
        Path(__file__).resolve().parent.parent,
        Path.cwd() / "ev-stealth-web",
        Path.cwd(),
        Path.cwd().parent,
    ]
    for c in candidates:
        if (c / "src" / "app").is_dir():
            return c
    return Path(__file__).resolve().parent.parent / "ev-stealth-web"

WEB_APP_ROOT = _find_web_app_root()
APP_DIR = WEB_APP_ROOT / "src" / "app"


def get_component_path(relative_subpath: str) -> Path:
    """Resolve and verify existence of a component file."""
    path = APP_DIR / relative_subpath
    if not path.is_file():
        raise FileNotFoundError(f"Target TSX component not found at expected path: {path}")
    return path


def read_component_source(relative_subpath: str) -> str:
    """Read full source code of a TSX component."""
    path = get_component_path(relative_subpath)
    return path.read_text(encoding="utf-8")


def calculate_relative_luminance(hex_color: str) -> float:
    """
    Calculate WCAG 2.1 relative luminance for an sRGB hex code (#rrggbb).
    Formula: L = 0.2126 * R + 0.7152 * G + 0.0722 * B
    where channel = c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    """
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0

    def transform(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r_lin = transform(r)
    g_lin = transform(g)
    b_lin = transform(b)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def calculate_contrast_ratio(hex1: str, hex2: str) -> float:
    """
    Calculate WCAG 2.1 contrast ratio between two colors: (L1 + 0.05) / (L2 + 0.05).
    """
    l1 = calculate_relative_luminance(hex1)
    l2 = calculate_relative_luminance(hex2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


class TestPdiChecklistClientA11y(unittest.TestCase):
    """
    Test suite for PdiChecklistClient.tsx WCAG AA compliance.
    """

    @classmethod
    def setUpClass(cls):
        cls.source = read_component_source("pdi-checklist/PdiChecklistClient.tsx")

    def test_pdi_checklist_no_text_gray_400_for_checked_items(self):
        """
        Validate that text-gray-400 (#9ca3af, contrast 2.54:1 against white) is no longer
        used for checked items in PdiChecklistClient.tsx.
        """
        # Ensure no conditional expression styles checked items with text-gray-400
        checked_gray_400_pattern = re.compile(r"item\.checked\s*\?\s*['\"][^'\"]*text-gray-400", re.MULTILINE)
        matches = checked_gray_400_pattern.findall(self.source)
        self.assertEqual(
            len(matches),
            0,
            f"PdiChecklistClient.tsx still uses text-gray-400 for checked items: {matches}",
        )

        # Ensure high-contrast replacement classes (text-slate-500 or text-slate-600) are utilized
        self.assertTrue(
            "text-slate-500" in self.source or "text-slate-600" in self.source,
            "PdiChecklistClient.tsx should use accessible slate classes (text-slate-500/600) for checked items.",
        )

        # Verify line-through items use compliant text-slate-500/600
        checked_slate_pattern = re.compile(
            r"item\.checked\s*\?\s*['\"][^'\"]*text-slate-(?:500|600)\s+line-through",
            re.MULTILINE,
        )
        self.assertTrue(
            bool(checked_slate_pattern.search(self.source)),
            "Expected checked task paragraph to style completed tasks with text-slate-500/600 line-through.",
        )

    def test_pdi_checklist_contains_progressbar_with_aria_attributes(self):
        """
        Validate that PdiChecklistClient.tsx contains role="progressbar" with
        aria-valuenow, aria-valuemin, and aria-valuemax.
        """
        self.assertIn(
            'role="progressbar"',
            self.source,
            "PdiChecklistClient.tsx must declare role=\"progressbar\" on the progress container.",
        )

        # Validate aria-valuenow binding
        valuenow_pattern = re.compile(r'aria-valuenow=\{([^}]+)\}')
        valuenow_match = valuenow_pattern.search(self.source)
        self.assertIsNotNone(
            valuenow_match,
            "PdiChecklistClient.tsx must define aria-valuenow attribute on the progressbar.",
        )
        valuenow_expr = valuenow_match.group(1).strip()
        self.assertIn(
            valuenow_expr,
            [
                "progressPercentage",
                "progress",
                "Math.round((checkedCount / items.length) * 100)",
                "items.length === 0 ? 0 : Math.round((checkedCount / items.length) * 100)",
            ],
            f"Unexpected aria-valuenow expression: {valuenow_expr}",
        )

        # Validate aria-valuemin={0}
        self.assertTrue(
            re.search(r'aria-valuemin=\{0\}|aria-valuemin="0"', self.source),
            "PdiChecklistClient.tsx must define aria-valuemin={0} on the progressbar.",
        )

        # Validate aria-valuemax={100}
        self.assertTrue(
            re.search(r'aria-valuemax=\{100\}|aria-valuemax="100"', self.source),
            "PdiChecklistClient.tsx must define aria-valuemax={100} on the progressbar.",
        )

    def test_pdi_checklist_progressbar_has_accessible_name(self):
        """
        Validate that the progressbar element in PdiChecklistClient.tsx has an accessible
        label (aria-label or aria-labelledby).
        """
        aria_label_match = re.search(r'aria-label="([^"]+)"', self.source)
        self.assertIsNotNone(
            aria_label_match,
            "PdiChecklistClient.tsx progressbar must have an accessible aria-label.",
        )
        label_text = aria_label_match.group(1).strip()
        self.assertTrue(
            len(label_text) > 0,
            "aria-label on progressbar must not be empty.",
        )
        self.assertIn(
            "진행",
            label_text,
            f"Expected accessible label to mention progress/inspection (진행), got: {label_text}",
        )

    def test_pdi_checklist_zero_length_items_guard(self):
        """
        Validate that PdiChecklistClient.tsx guards against division by zero (items.length === 0)
        when calculating checklist progress, preventing NaN% display.
        """
        guard_pattern = re.compile(
            r'items\.length\s*===\s*0\s*\?\s*0\s*:\s*Math\.round\(\s*\(\s*checkedCount\s*/\s*items\.length\s*\)\s*\*\s*100\s*\)'
            r'|items\.length\s*>\s*0\s*\?\s*Math\.round\(\s*\(\s*checkedCount\s*/\s*items\.length\s*\)\s*\*\s*100\s*\)\s*:\s*0'
            r'|items\.length\s*\?\s*Math\.round\(\s*\(\s*checkedCount\s*/\s*items\.length\s*\)\s*\*\s*100\s*\)\s*:\s*0'
        )
        self.assertTrue(
            bool(guard_pattern.search(self.source)),
            "PdiChecklistClient.tsx must guard against zero-length items when computing progress.",
        )

        # Functional simulation proof: items.length == 0 returns 0, not NaN
        def calc_progress(items_list: list) -> int:
            checked_count = len([i for i in items_list if i.get("checked")])
            return 0 if len(items_list) == 0 else round((checked_count / len(items_list)) * 100)

        empty_result = calc_progress([])
        self.assertEqual(empty_result, 0)
        self.assertFalse(math.isnan(empty_result))


class TestRecallPortalClientA11y(unittest.TestCase):
    """
    Test suite for RecallPortalClient.tsx WCAG AA compliance.
    """

    @classmethod
    def setUpClass(cls):
        cls.source = read_component_source("recall-portal/RecallPortalClient.tsx")

    def test_recall_portal_zero_nested_main_tags(self):
        """
        Validate that RecallPortalClient.tsx contains zero nested <main> elements (WCAG 1.3.1)
        to avoid duplicate landmark collision with layout.tsx's root <main id="main-content">.
        """
        main_open_tags = re.findall(r'<\s*main\b', self.source, re.IGNORECASE)
        main_close_tags = re.findall(r'<\s*/\s*main\b', self.source, re.IGNORECASE)
        self.assertEqual(
            len(main_open_tags),
            0,
            f"RecallPortalClient.tsx must contain 0 <main> opening tags, found {len(main_open_tags)}: {main_open_tags}",
        )
        self.assertEqual(
            len(main_close_tags),
            0,
            f"RecallPortalClient.tsx must contain 0 </main> closing tags, found {len(main_close_tags)}",
        )
        # Confirm root content container uses semantic <div> or <section>
        self.assertTrue(
            re.search(r'<div\s+className=["\']max-w-7xl\s+mx-auto[^"\']*py-8 space-y-12', self.source)
            or re.search(r'<section\s+className=["\']max-w-7xl\s+mx-auto[^"\']*py-8 space-y-12', self.source),
            "Expected outer content container to be a semantic <div> or <section>.",
        )

    def test_recall_portal_disambiguated_campaign_detail_ids(self):
        """
        Validate that accordion detail containers in RecallPortalClient.tsx use disambiguated,
        collision-free IDs between search result cards and general campaign list cards (WCAG 4.1.2).
        """
        # Search result cards should use search-specific namespace (e.g. campaign-search-detail-)
        search_detail_match = re.search(
            r'id=\{["\']campaign-search-detail-["\']\s*\+\s*campaign\.id\}',
            self.source,
        )
        self.assertIsNotNone(
            search_detail_match,
            "Search result detail container must use disambiguated namespace 'campaign-search-detail-'.",
        )

        # Full campaign list cards should use list-specific namespace (e.g. campaign-list-detail-)
        list_detail_match = re.search(
            r'id=\{["\']campaign-list-detail-["\']\s*\+\s*campaign\.id\}',
            self.source,
        )
        self.assertIsNotNone(
            list_detail_match,
            "Full campaign list detail container must use disambiguated namespace 'campaign-list-detail-'.",
        )

        # Verify search toggle button aria-controls matches search-detail container
        self.assertIn(
            'aria-controls={"campaign-search-detail-" + campaign.id}',
            self.source,
            "Search toggle button aria-controls must match 'campaign-search-detail-' container.",
        )

        # Verify list toggle button aria-controls matches list-detail container
        self.assertIn(
            'aria-controls={"campaign-list-detail-" + campaign.id}',
            self.source,
            "List toggle button aria-controls must match 'campaign-list-detail-' container.",
        )

    def test_recall_portal_tablist_and_tabpanels(self):
        """
        Validate that mode switcher in RecallPortalClient.tsx implements accessible
        tablist, tab, and tabpanel semantics with aria-selected and aria-controls.
        """
        self.assertIn('role="tablist"', self.source)
        self.assertIn('role="tab"', self.source)
        self.assertIn('aria-selected=', self.source)
        self.assertIn('role="tabpanel"', self.source)
        self.assertIn('id="vin-checker-tab"', self.source)
        self.assertIn('id="model-checker-tab"', self.source)
        self.assertIn('id="vin-checker-panel"', self.source)
        self.assertIn('id="model-checker-panel"', self.source)

    def test_recall_portal_uses_placeholder_slate_400_instead_of_500(self):
        """
        Validate that RecallPortalClient.tsx uses placeholder-slate-400 instead of
        placeholder-slate-500 across dark mode text inputs.
        """
        # Assert placeholder-slate-500 is completely eradicated
        self.assertNotIn(
            "placeholder-slate-500",
            self.source,
            "RecallPortalClient.tsx must not contain placeholder-slate-500 (fails contrast on slate-900).",
        )

        # Assert placeholder-slate-400 is present
        self.assertIn(
            "placeholder-slate-400",
            self.source,
            "RecallPortalClient.tsx must use placeholder-slate-400 for high-contrast placeholder text.",
        )

        # Check all input tags in the file
        input_tags = re.findall(r'<input\b[^>]*>', self.source)
        self.assertTrue(len(input_tags) >= 3, f"Expected at least 3 inputs, found {len(input_tags)}")
        for tag in input_tags:
            self.assertNotIn(
                "placeholder-slate-500",
                tag,
                f"Input tag still contains placeholder-slate-500: {tag}",
            )
            if "placeholder=" in tag:
                self.assertIn(
                    "placeholder-slate-400",
                    tag,
                    f"Input tag with placeholder missing placeholder-slate-400: {tag}",
                )

    def test_recall_portal_campaign_accordion_aria_expanded_and_controls(self):
        """
        Validate that campaign details accordion toggle buttons in RecallPortalClient.tsx
        have aria-expanded and aria-controls pointing to the revealed container.
        """
        # Find accordion toggle buttons
        accordion_buttons = re.findall(
            r'<button\b[^>]*onClick=\{\(\)\s*=>\s*toggleRecallExpansion\([^)]+\)\}[^>]*>',
            self.source,
        )
        self.assertTrue(
            len(accordion_buttons) >= 2,
            f"Expected at least 2 toggleRecallExpansion buttons, found {len(accordion_buttons)}",
        )

        for btn in accordion_buttons:
            self.assertIn(
                "aria-expanded",
                btn,
                f"Campaign toggle button missing aria-expanded: {btn}",
            )
            self.assertIn(
                "aria-controls",
                btn,
                f"Campaign toggle button missing aria-controls: {btn}",
            )

        # Check that target container ID exists matching aria-controls pattern
        self.assertTrue(
            re.search(r'id=\{["\']campaign-(?:search|list)-detail-["\']\s*\+\s*campaign\.id\}', self.source)
            or re.search(r'id=\{["\']campaign-detail-["\']\s*\+\s*idx\}', self.source)
            or re.search(r'id=\{`campaign-detail-\$\{idx\}`\}', self.source),
            "Expected revealed campaign detail container to have matching id for aria-controls.",
        )

    def test_recall_portal_vin_input_error_linkage(self):
        """
        Validate that the 17-digit VIN input programmatically exposes validation error
        state via aria-invalid and aria-describedby connected to the error element.
        """
        # Locate the VIN input
        vin_input_match = re.search(r'<input\b[^>]*id="vin-input"[^>]*>', self.source)
        self.assertIsNotNone(vin_input_match, "RecallPortalClient.tsx must contain input id='vin-input'")
        vin_input_tag = vin_input_match.group(0)

        # Check aria-invalid
        self.assertIn(
            "aria-invalid",
            vin_input_tag,
            f"VIN input must have aria-invalid attribute: {vin_input_tag}",
        )

        # Check aria-describedby
        self.assertIn(
            "aria-describedby",
            vin_input_tag,
            f"VIN input must have aria-describedby attribute: {vin_input_tag}",
        )

        # Ensure the error feedback paragraph defines the matching id
        self.assertIn(
            'id="vin-error-feedback"',
            self.source,
            "Error feedback element must have id='vin-error-feedback' matching aria-describedby.",
        )

        # Ensure aria-describedby conditionally points to vin-error-feedback
        self.assertTrue(
            'aria-describedby={vinError ? "vin-error-feedback" : undefined}' in self.source
            or "vin-error-feedback" in vin_input_tag,
            "VIN input aria-describedby must link to vin-error-feedback when error is active.",
        )

    def test_recall_portal_external_links_sr_only(self):
        """
        Validate that external links opening in a new tab (target="_blank") provide
        screen reader notification (e.g. sr-only '(새 창에서 열림)').
        """
        external_links = re.findall(r'<a\b[^>]*target="_blank"[^>]*>[\s\S]*?</a>', self.source)
        self.assertTrue(len(external_links) >= 2, f"Expected external links in RecallPortalClient: {len(external_links)}")
        for link in external_links:
            self.assertIn(
                "sr-only",
                link,
                f"External link missing screen-reader accessible notification: {link}",
            )

    def test_recall_portal_heading_hierarchy_continuity(self):
        """
        Validate that search result section under <h2> does not skip <h3> (WCAG 1.3.1).
        Battery safety specs and matched recall list use <h3>, and campaign titles use <h4>.
        """
        self.assertIn(
            "배터리 안전 제원",
            self.source,
            "RecallPortalClient.tsx must contain battery safety specs section.",
        )
        self.assertTrue(
            bool(re.search(r'<h3\b[^>]*>\s*\{checkResult\.batteryProfile\.model_name\}\s+배터리 안전 제원\s*</h3>', self.source)),
            "Battery safety profile heading must use semantic <h3>.",
        )
        self.assertTrue(
            bool(re.search(r'<h3\b[^>]*>\s*<span>해당 차종 대상 정부 공시 리콜 세부 내역', self.source)),
            "Matched recall list heading must use semantic <h3>.",
        )
        self.assertTrue(
            bool(re.search(r'<h4\b[^>]*>\s*\{campaign\.defect_title\}\s*</h4>', self.source)),
            "Campaign defect title heading must use semantic <h4>.",
        )


class TestDepreciationCalculatorClientA11y(unittest.TestCase):
    """
    Test suite for DepreciationCalculatorClient.tsx WCAG AA compliance.
    """

    @classmethod
    def setUpClass(cls):
        cls.source = read_component_source("depreciation-calculator/DepreciationCalculatorClient.tsx")

    def test_depreciation_calculator_battery_soh_progressbar_semantics(self):
        """
        Validate that the circular Battery State of Health (SoH) meter in
        DepreciationCalculatorClient.tsx provides accessible progressbar semantics
        (role="progressbar", aria-valuenow, aria-valuemin, aria-valuemax, aria-label).
        """
        self.assertIn(
            'role="progressbar"',
            self.source,
            "DepreciationCalculatorClient.tsx must contain role='progressbar' on Battery SoH circle.",
        )
        self.assertTrue(
            re.search(r'aria-valuenow=\{[^}]*sohPct[^}]*\}', self.source),
            "Battery SoH progressbar must bind aria-valuenow to sohPct.",
        )
        self.assertTrue(
            re.search(r'aria-valuemin=\{0\}|aria-valuemin="0"', self.source),
            "Battery SoH progressbar must define aria-valuemin={0}.",
        )
        self.assertTrue(
            re.search(r'aria-valuemax=\{100\}|aria-valuemax="100"', self.source),
            "Battery SoH progressbar must define aria-valuemax={100}.",
        )
        self.assertTrue(
            re.search(r'aria-label=["\'][^"\']*배터리[^"\']*["\']', self.source),
            "Battery SoH progressbar must define an aria-label mentioning '배터리'.",
        )
        self.assertTrue(
            re.search(r'aria-valuetext=\{[^}]*sohPct[^}]*\}', self.source),
            "Battery SoH progressbar should expose aria-valuetext for formatted reading.",
        )

    def test_depreciation_calculator_selected_card_pricing_text_blue_700(self):
        """
        Validate that selected model card pricing uses text-blue-700 instead of
        text-blue-600 to satisfy WCAG AA contrast (>= 4.5:1) against bg-blue-50.
        """
        self.assertIn(
            "text-blue-700",
            self.source,
            "DepreciationCalculatorClient.tsx must contain text-blue-700 for card pricing.",
        )

        # Verify net purchase price element specifically uses text-blue-700
        pricing_span_pattern = re.compile(
            r'<span\s+className=["\']font-bold\s+text-blue-700["\']>\s*\{\(model\.net_purchase_price_krw',
            re.MULTILINE,
        )
        self.assertTrue(
            bool(pricing_span_pattern.search(self.source)),
            "Expected model.net_purchase_price_krw display span to use font-bold text-blue-700.",
        )

        # Verify old text-blue-600 is not used for this pricing span
        old_pricing_pattern = re.compile(
            r'<span\s+className=["\']font-bold\s+text-blue-600["\']>\s*\{\(model\.net_purchase_price_krw',
            re.MULTILINE,
        )
        self.assertFalse(
            bool(old_pricing_pattern.search(self.source)),
            "model.net_purchase_price_krw display span must no longer use failing text-blue-600.",
        )

    def test_depreciation_calculator_tco_banner_high_contrast_text(self):
        """
        Validate that the TCO running cost savings banner in DepreciationCalculatorClient.tsx
        does not use low-contrast text-blue-200 or text-blue-100 on blue background,
        and uses high-contrast text-white font-medium.
        """
        tco_banner_match = re.search(
            r'<div\s+className=["\'][^"\']*from-blue-600\s+to-indigo-700[^"\']*text-white[^"\']*["\']>([\s\S]*?)</div>\s*</div>\s*\{/\* Yearly Running Cost Breakdown Table \*/\}',
            self.source,
        )
        self.assertIsNotNone(tco_banner_match, "Could not locate TCO cumulative savings banner in DepreciationCalculatorClient.tsx")
        banner_content = tco_banner_match.group(1)

        self.assertNotIn("text-blue-200", banner_content, "TCO banner must not use low-contrast text-blue-200")
        self.assertNotIn("text-blue-100", banner_content, "TCO banner must not use low-contrast text-blue-100")
        self.assertIn("text-white font-medium", banner_content, "TCO banner should use high-contrast text-white font-medium")

    def test_depreciation_calculator_wraps_radio_groups_in_fieldset_and_legend(self):
        """
        Validate that transfer type radio options are wrapped in a semantic <fieldset>
        with an accessible <legend>.
        """
        self.assertIn(
            "<fieldset",
            self.source,
            "DepreciationCalculatorClient.tsx must contain <fieldset> for radio option grouping.",
        )
        self.assertIn(
            "</fieldset>",
            self.source,
            "DepreciationCalculatorClient.tsx must properly close </fieldset>.",
        )
        self.assertIn(
            "<legend",
            self.source,
            "DepreciationCalculatorClient.tsx must contain <legend> within the radio group <fieldset>.",
        )

        # Extract fieldset content and verify radio input is inside
        fieldset_match = re.search(r'<fieldset\b[^>]*>([\s\S]*?)</fieldset>', self.source)
        self.assertIsNotNone(fieldset_match, "Failed to match <fieldset> block in DepreciationCalculatorClient.tsx")
        fieldset_content = fieldset_match.group(1)

        self.assertIn(
            '<input\n                    type="radio"',
            fieldset_content.replace("\r", ""),
            "Transfer type radio inputs must be enclosed inside the <fieldset> block.",
        )
        self.assertIn(
            "transferTypeRadio",
            fieldset_content,
            "Radio inputs with name='transferTypeRadio' must reside inside the <fieldset>.",
        )

        # Verify legend provides descriptive accessible name
        legend_match = re.search(r'<legend\b[^>]*>(.*?)</legend>', fieldset_content)
        self.assertIsNotNone(legend_match, "<fieldset> must contain a <legend> tag.")
        legend_text = legend_match.group(1).strip()
        self.assertTrue(len(legend_text) > 0, "<legend> must not be empty.")
        self.assertIn(
            "이전",
            legend_text,
            f"Expected legend to describe transfer type selection (이전), got: {legend_text}",
        )


class TestReliabilityDashboardClientA11y(unittest.TestCase):
    """
    Test suite for ReliabilityDashboardClient.tsx WCAG AA compliance.
    """

    @classmethod
    def setUpClass(cls):
        cls.source = read_component_source("reliability-analytics/ReliabilityDashboardClient.tsx")

    def test_reliability_dashboard_high_contrast_empty_cell_text(self):
        """
        Validate that the matrix heatmap empty cell in ReliabilityDashboardClient.tsx
        replaces low-contrast text-slate-300 with compliant text-slate-600.
        """
        empty_cell_match = re.search(
            r'<div\b[^>]*w-8\s+h-8[^>]*bg-slate-100[^>]*>[\s\S]*?-[\s\S]*?</div>',
            self.source,
        )
        self.assertIsNotNone(empty_cell_match, "Could not find empty cell div in ReliabilityDashboardClient.tsx")
        cell_tag = empty_cell_match.group(0)

        self.assertNotIn("text-slate-300", cell_tag, "Empty cell div must not use low-contrast text-slate-300")
        self.assertTrue(
            "text-slate-600" in cell_tag or "text-slate-700" in cell_tag,
            "Empty cell div must use high-contrast text-slate-600/700.",
        )
        self.assertTrue(
            'aria-label="데이터 없음"' in cell_tag or 'title="해당 연식 데이터 없음"' in cell_tag,
            "Empty cell must provide accessible title or aria-label.",
        )

    def test_reliability_dashboard_defect_distribution_accessible_semantics(self):
        """
        Validate that defect distribution stacked proportional bar declares
        accessible role="region" and category segments declare role="img" with descriptive labels.
        """
        self.assertIn(
            'role="region"',
            self.source,
            "Defect distribution bar must declare role='region'.",
        )
        self.assertIn(
            'aria-label="전기차 결함 부문별 산업 점유율 분포 바"',
            self.source,
            "Defect distribution bar must define accessible aria-label.",
        )
        self.assertIn(
            'role="img"',
            self.source,
            "Category proportional bar segments must define role='img'.",
        )

    def test_reliability_dashboard_caution_filter_button_contrast(self):
        """
        Validate that active CAUTION filter button uses text-slate-950 font-extrabold
        on bg-amber-500, achieving > 9:1 contrast ratio (WCAG 1.4.3 Level AA & AAA).
        """
        caution_match = re.search(
            r"selectedVerdict\s*===\s*'CAUTION'\s*\?\s*'([^']+)'",
            self.source,
        )
        self.assertIsNotNone(caution_match, "Could not find CAUTION active style in ReliabilityDashboardClient.tsx")
        active_classes = caution_match.group(1)
        self.assertIn("bg-amber-500", active_classes)
        self.assertIn("text-slate-950", active_classes)
        self.assertIn("font-extrabold", active_classes)
        self.assertNotIn("text-white", active_classes, "Active CAUTION button must not use failing text-white on amber-500")


class TestLayoutDesktopNavigationA11y(unittest.TestCase):
    """
    Test suite for layout.tsx desktop navigation focus visible styles.
    """

    @classmethod
    def setUpClass(cls):
        cls.source = read_component_source("layout.tsx")

    def test_layout_desktop_nav_contains_focus_ring_2(self):
        """
        Validate that desktop navigation links in layout.tsx contain visible focus
        indicator styling (focus:ring-2 and focus:outline-none) under WCAG 2.4.7.
        """
        # Find desktop navigation block
        nav_match = re.search(
            r'<nav\b[^>]*data-testid="desktop-nav"[^>]*>([\s\S]*?)</nav>',
            self.source,
        )
        self.assertIsNotNone(nav_match, "layout.tsx must contain <nav data-testid='desktop-nav'>")
        nav_content = nav_match.group(1)

        # Extract all <Link> elements within desktop nav
        link_tags = re.findall(r'<Link\b[^>]*>', nav_content)
        self.assertTrue(
            len(link_tags) >= 9,
            f"Expected at least 9 desktop nav links, found {len(link_tags)}",
        )

        # Verify every link has focus:ring-2
        for link_tag in link_tags:
            self.assertIn(
                "focus:ring-2",
                link_tag,
                f"Desktop nav Link missing focus:ring-2 visible focus style: {link_tag}",
            )
            self.assertIn(
                "focus:outline-none",
                link_tag,
                f"Desktop nav Link missing focus:outline-none for custom ring styling: {link_tag}",
            )

    def test_layout_desktop_nav_links_validity(self):
        """
        Validate that each desktop navigation link points to a valid local route
        and has accessible link text.
        """
        nav_match = re.search(
            r'<nav\b[^>]*data-testid="desktop-nav"[^>]*>([\s\S]*?)</nav>',
            self.source,
        )
        self.assertIsNotNone(nav_match)
        nav_content = nav_match.group(1)

        links = re.findall(r'<Link\b[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</Link>', nav_content)
        self.assertTrue(len(links) >= 9)

        required_routes = {
            "/subsidy-tracker",
            "/depreciation-calculator",
            "/reliability-analytics",
            "/recall-portal",
            "/2026-latest",
            "/pdi-checklist",
            "/hyundai-kia",
            "/tesla",
            "/byd",
            "/global-brands",
        }
        found_routes = {href for href, _ in links}
        for route in required_routes:
            self.assertIn(
                route,
                found_routes,
                f"Desktop nav missing required route: {route}",
            )


class TestSubsidyTrackerClientA11y(unittest.TestCase):
    """
    Test suite for SubsidyTrackerClient.tsx WCAG AA compliance.
    """

    @classmethod
    def setUpClass(cls):
        cls.source = read_component_source("subsidy-tracker/SubsidyTrackerClient.tsx")

    def test_subsidy_tracker_municipality_toggle_aria_expanded_and_controls(self):
        """
        Validate that municipality collapsible toggle buttons in SubsidyTrackerClient.tsx
        have aria-expanded and aria-controls with matching container ID.
        """
        # Find the municipality toggle button
        toggle_button_match = re.search(
            r'<button\b[^>]*onClick=\{\(\)\s*=>\s*toggleRegionExpand\([^)]+\)\}[^>]*>',
            self.source,
        )
        self.assertIsNotNone(
            toggle_button_match,
            "SubsidyTrackerClient.tsx must contain toggleRegionExpand button.",
        )
        button_tag = toggle_button_match.group(0)

        # Check aria-expanded
        self.assertIn(
            "aria-expanded",
            button_tag,
            f"Municipality toggle button missing aria-expanded: {button_tag}",
        )

        # Check aria-controls
        self.assertIn(
            "aria-controls",
            button_tag,
            f"Municipality toggle button missing aria-controls: {button_tag}",
        )

        # Check target container has matching ID
        self.assertTrue(
            re.search(r'id=\{["\']muni-details-["\']\s*\+\s*region\.(?:code|region_id)\}', self.source),
            "Expandable municipality container must define id matching aria-controls.",
        )

    def test_subsidy_tracker_progressbars_wcag_compliance(self):
        """
        Validate that SubsidyTrackerClient.tsx implements accessible progressbars
        with role="progressbar", aria-valuenow, aria-valuemin, aria-valuemax.
        """
        self.assertIn(
            'role="progressbar"',
            self.source,
            "SubsidyTrackerClient.tsx must define role='progressbar'.",
        )
        self.assertIn(
            "aria-valuenow",
            self.source,
            "SubsidyTrackerClient.tsx must define aria-valuenow on progressbars.",
        )
        self.assertTrue(
            re.search(r'aria-valuemin=\{0\}|aria-valuemin="0"', self.source),
            "SubsidyTrackerClient.tsx must define aria-valuemin={0} on progressbars.",
        )
        self.assertTrue(
            re.search(r'aria-valuemax=\{100\}|aria-valuemax="100"', self.source),
            "SubsidyTrackerClient.tsx must define aria-valuemax={100} on progressbars.",
        )


class TestSecretAdminReportsA11y(unittest.TestCase):
    """
    Test suite for AdminDashboardClient.tsx WCAG AA compliance.
    """

    @classmethod
    def setUpClass(cls):
        cls.source = read_component_source("secret-admin-reports/AdminDashboardClient.tsx")

    def test_sr_only_table_link_not_keyboard_focusable(self):
        """
        Validate that anchor link inside .sr-only summary table specifies tabIndex={-1} and aria-hidden="true"
        to prevent trapping invisible keyboard focus (WCAG 2.4.7).
        """
        sr_table_match = re.search(
            r'<div className="sr-only">[\s\S]*?<table[\s\S]*?</table>[\s\S]*?</div>',
            self.source,
        )
        self.assertIsNotNone(sr_table_match, "Could not find .sr-only table block in AdminDashboardClient.tsx")
        table_html = sr_table_match.group(0)

        link_matches = re.findall(r'<a\b[^>]*>', table_html)
        self.assertTrue(len(link_matches) > 0, "Expected link inside .sr-only table in AdminDashboardClient.tsx")
        for link_tag in link_matches:
            self.assertIn("tabIndex={-1}", link_tag, "sr-only table link must have tabIndex={-1}")
            self.assertIn('aria-hidden="true"', link_tag, 'sr-only table link must have aria-hidden="true"')


class TestEvRecallDatabaseIntegrity(unittest.TestCase):
    """
    Test suite for ev_recall_database.json integrity, schema compliance,
    and Tesla Model 3 (LRW3E7EK) battery safety profile coverage.
    """

    @classmethod
    def setUpClass(cls):
        db_candidates = [
            WEB_APP_ROOT / "src" / "data" / "ev_recall_database.json",
            Path(__file__).resolve().parent.parent / "ev-stealth-web" / "src" / "data" / "ev_recall_database.json",
            Path.cwd() / "ev-stealth-web" / "src" / "data" / "ev_recall_database.json",
        ]
        cls.db_path = None
        for p in db_candidates:
            if p.is_file():
                cls.db_path = p
                break
        if not cls.db_path:
            raise FileNotFoundError("ev_recall_database.json not found in candidate paths")

        with open(cls.db_path, "r", encoding="utf-8") as f:
            cls.db = json.load(f)

    def test_tesla_model_3_lrw_vin_prefix_and_battery_profile_coverage(self):
        """
        Validate that Tesla Model 3 (LRW3E7EK prefix) has complete coverage in vin_prefixes
        and battery_profiles with compliant engineering specifications.
        """
        # 1. vin_prefixes coverage
        vin_prefixes = self.db.get("vin_prefixes", [])
        m3_prefix = next((p for p in vin_prefixes if p.get("prefix") == "LRW3E7EK"), None)
        self.assertIsNotNone(m3_prefix, "vin_prefixes must contain entry for prefix 'LRW3E7EK'")
        self.assertEqual(m3_prefix["brand"], "테슬라")
        self.assertEqual(m3_prefix["model_name"], "모델 3")
        self.assertEqual(m3_prefix["country"], "중국")
        self.assertTrue(m3_prefix["sample_full_vin"].startswith("LRW3E7EK"))

        # 2. battery_profiles coverage
        battery_profiles = self.db.get("battery_profiles", [])
        m3_profile = next(
            (bp for bp in battery_profiles if "모델 3" in bp.get("model_name", "") or bp.get("model_id") == "tesla-model-3"),
            None,
        )
        self.assertIsNotNone(m3_profile, "battery_profiles must contain an entry for '모델 3'")
        self.assertEqual(m3_profile["brand"], "테슬라")
        self.assertIn("CATL", m3_profile["cell_supplier"])
        self.assertIn("LFP", m3_profile["cell_chemistry"])
        self.assertIn(m3_profile["fire_incident_status"], ["CRITICAL_MONITORING", "RECALLED_RESOLVED", "VERIFIED_SAFE"])
        self.assertEqual(m3_profile["recommended_soc_limit"], 100)
        self.assertTrue(len(m3_profile["underground_parking_advisory"]) > 20)
        self.assertTrue(len(m3_profile["bms_safety_features"]) > 20)

        # 3. VIN Decoder Matching Simulation
        decoded_model = m3_prefix["model_name"]
        matched_bp = next(
            (bp for bp in battery_profiles if bp["model_name"].lower() in decoded_model.lower() or decoded_model.lower() in bp["model_name"].lower()),
            None,
        )
        self.assertIsNotNone(
            matched_bp,
            f"decodeVinAndCheckRecalls matching algorithm must successfully match decodedModel '{decoded_model}' to a battery profile",
        )
        self.assertEqual(matched_bp["model_id"], m3_profile["model_id"])

    def test_all_battery_profiles_have_valid_soc_limits(self):
        """Validate that all battery profiles define valid SoC limits between 50 and 100."""
        for bp in self.db.get("battery_profiles", []):
            soc = bp.get("recommended_soc_limit")
            self.assertIsInstance(soc, int, f"SoC limit must be int for {bp.get('model_name')}")
            self.assertTrue(50 <= soc <= 100, f"SoC limit {soc} out of bounds for {bp.get('model_name')}")


class TestContrastMathematicalVerification(unittest.TestCase):
    """
    Mathematical contrast ratio verification against WCAG 2.1 formulas.
    Verifies that audited color changes genuinely achieve >= 4.5:1 (Level AA).
    """

    def test_wcag_aa_contrast_ratios_mathematical_proof(self):
        """
        Prove mathematically that the old pairings failed WCAG AA (< 4.5:1)
        and that the remediated pairings pass (>= 4.5:1).
        """
        # 1. PDI Checklist Checked Text
        # Old: text-gray-400 (#9ca3af) on white (#ffffff)
        old_pdi_cr = calculate_contrast_ratio("#9ca3af", "#ffffff")
        self.assertLess(
            old_pdi_cr,
            4.5,
            f"text-gray-400 on white unexpectedly passed: {old_pdi_cr:.2f}:1",
        )
        self.assertAlmostEqual(old_pdi_cr, 2.54, delta=0.1)

        # New: text-slate-500 (#64748b) on white (#ffffff)
        new_pdi_cr = calculate_contrast_ratio("#64748b", "#ffffff")
        self.assertGreaterEqual(
            new_pdi_cr,
            4.5,
            f"text-slate-500 on white must achieve >= 4.5:1, got: {new_pdi_cr:.2f}:1",
        )
        self.assertAlmostEqual(new_pdi_cr, 4.76, delta=0.1)

        # 2. Depreciation Calculator Selected Card Pricing
        # text-blue-700 (#1d4ed8) provides robust AA contrast (> 6.0:1 on bg-blue-50 #eff6ff and > 5.4:1 on bg-blue-100 #dbeafe)
        new_depr_cr = calculate_contrast_ratio("#1d4ed8", "#eff6ff")
        self.assertGreaterEqual(
            new_depr_cr,
            4.5,
            f"text-blue-700 on bg-blue-50 must achieve >= 4.5:1, got: {new_depr_cr:.2f}:1",
        )
        self.assertGreater(new_depr_cr, 6.0)

        # On border or blue-100 tinted selection (#dbeafe), blue-700 achieves >= 4.5:1
        tinted_depr_cr = calculate_contrast_ratio("#1d4ed8", "#dbeafe")
        self.assertGreaterEqual(tinted_depr_cr, 4.5)

        # 3. Recall Portal Dark Mode Input Placeholder Text
        # Old: placeholder-slate-500 (#64748b) on bg-slate-900 (#0f172a)
        old_portal_cr = calculate_contrast_ratio("#64748b", "#0f172a")
        self.assertLess(
            old_portal_cr,
            4.5,
            f"slate-500 on slate-900 unexpectedly passed: {old_portal_cr:.2f}:1",
        )
        self.assertAlmostEqual(old_portal_cr, 3.75, delta=0.1)

        # New: placeholder-slate-400 (#94a3b8) on bg-slate-900 (#0f172a)
        new_portal_cr = calculate_contrast_ratio("#94a3b8", "#0f172a")
        self.assertGreaterEqual(
            new_portal_cr,
            4.5,
            f"slate-400 on slate-900 must achieve >= 4.5:1, got: {new_portal_cr:.2f}:1",
        )
        self.assertGreater(new_portal_cr, 6.0)

        # 4. Reliability Dashboard Empty Cell Text
        # Old: text-slate-300 (#cbd5e1) on bg-slate-100 (#f1f5f9) -> CR 1.33:1 (FAIL < 4.5)
        old_empty_cr = calculate_contrast_ratio("#cbd5e1", "#f1f5f9")
        self.assertLess(
            old_empty_cr,
            4.5,
            f"slate-300 on slate-100 unexpectedly passed: {old_empty_cr:.2f}:1",
        )
        self.assertAlmostEqual(old_empty_cr, 1.33, delta=0.05)

        # New: text-slate-600 (#475569) on bg-slate-100 (#f1f5f9) -> CR 6.92:1 (PASS >= 4.5)
        new_empty_cr = calculate_contrast_ratio("#475569", "#f1f5f9")
        self.assertGreaterEqual(
            new_empty_cr,
            4.5,
            f"slate-600 on slate-100 must achieve >= 4.5:1, got: {new_empty_cr:.2f}:1",
        )
        self.assertAlmostEqual(new_empty_cr, 6.92, delta=0.15)

        # 5. Depreciation Calculator TCO Savings Banner
        # Old: text-blue-200 (#bfdbfe) on bg-blue-600 (#2563eb) -> CR 3.64:1 (FAIL < 4.5)
        old_banner_cr1 = calculate_contrast_ratio("#bfdbfe", "#2563eb")
        self.assertLess(
            old_banner_cr1,
            4.5,
            f"blue-200 on blue-600 unexpectedly passed: {old_banner_cr1:.2f}:1",
        )
        self.assertAlmostEqual(old_banner_cr1, 3.64, delta=0.1)

        # Old: text-blue-100 (#dbeafe) on bg-blue-600 (#2563eb) -> CR 4.24:1 (FAIL < 4.5)
        old_banner_cr2 = calculate_contrast_ratio("#dbeafe", "#2563eb")
        self.assertLess(
            old_banner_cr2,
            4.5,
            f"blue-100 on blue-600 unexpectedly passed: {old_banner_cr2:.2f}:1",
        )
        self.assertAlmostEqual(old_banner_cr2, 4.24, delta=0.1)

        # New: text-white (#ffffff) on bg-blue-600 (#2563eb) -> CR 5.17:1 (PASS >= 4.5)
        new_banner_cr = calculate_contrast_ratio("#ffffff", "#2563eb")
        self.assertGreaterEqual(
            new_banner_cr,
            4.5,
            f"white on blue-600 must achieve >= 4.5:1, got: {new_banner_cr:.2f}:1",
        )
        self.assertAlmostEqual(new_banner_cr, 5.17, delta=0.1)

    def test_caution_filter_button_amber500_slate950_contrast(self):
        """
        Prove mathematically that amber-500 (#f59e0b) with text-white (#ffffff) failed (< 4.5:1)
        and that amber-500 with text-slate-950 (#020617) achieves > 9:1 (WCAG AA & AAA compliant).
        """
        # Failing white on amber-500
        failing_cr = calculate_contrast_ratio("#ffffff", "#f59e0b")
        self.assertLess(failing_cr, 4.5, f"white on amber-500 must fail WCAG AA: got {failing_cr:.2f}:1")
        self.assertAlmostEqual(failing_cr, 2.14, delta=0.1)

        # Passing slate-950 on amber-500
        passing_cr = calculate_contrast_ratio("#020617", "#f59e0b")
        self.assertGreaterEqual(passing_cr, 9.0, f"slate-950 on amber-500 must exceed 9:1: got {passing_cr:.2f}:1")
        self.assertAlmostEqual(passing_cr, 9.42, delta=0.2)


class TestAdversarialA11yEdgeCases(unittest.TestCase):
    """
    Adversarial verification testing edge cases, malformed attributes,
    boundary constraints, and semantic contracts.
    """

    def test_components_exist_and_non_empty(self):
        """Verify all 7 audited component files exist and exceed minimum content size."""
        target_files = [
            "pdi-checklist/PdiChecklistClient.tsx",
            "recall-portal/RecallPortalClient.tsx",
            "depreciation-calculator/DepreciationCalculatorClient.tsx",
            "reliability-analytics/ReliabilityDashboardClient.tsx",
            "layout.tsx",
            "subsidy-tracker/SubsidyTrackerClient.tsx",
            "secret-admin-reports/AdminDashboardClient.tsx",
        ]
        for rel_path in target_files:
            path = get_component_path(rel_path)
            self.assertTrue(path.exists(), f"Target file does not exist: {rel_path}")
            size = path.stat().st_size
            self.assertGreater(size, 500, f"File {rel_path} is suspiciously small: {size} bytes")

    def test_progressbar_boundary_invariants(self):
        """
        Verify that progressbar declarations enforce 0 <= min < max <= 100.
        """
        for rel_path in [
            "pdi-checklist/PdiChecklistClient.tsx",
            "subsidy-tracker/SubsidyTrackerClient.tsx",
            "depreciation-calculator/DepreciationCalculatorClient.tsx",
        ]:
            source = read_component_source(rel_path)
            if 'role="progressbar"' in source:
                min_match = re.search(r'aria-valuemin=\{?(\d+)\}?', source)
                max_match = re.search(r'aria-valuemax=\{?(\d+)\}?', source)
                if min_match and max_match:
                    val_min = int(min_match.group(1))
                    val_max = int(max_match.group(1))
                    self.assertEqual(val_min, 0)
                    self.assertEqual(val_max, 100)
                    self.assertLess(val_min, val_max)

    def test_aria_controls_and_id_syntax_integrity(self):
        """
        Verify that aria-controls expressions produce non-empty strings and avoid syntax collisions.
        """
        for rel_path in [
            "recall-portal/RecallPortalClient.tsx",
            "subsidy-tracker/SubsidyTrackerClient.tsx",
        ]:
            source = read_component_source(rel_path)
            controls_matches = re.findall(r'aria-controls=\{([^}]+)\}', source)
            self.assertTrue(len(controls_matches) > 0, f"Expected aria-controls in {rel_path}")
            for expr in controls_matches:
                self.assertNotIn("undefined", expr, f"aria-controls expression should not produce undefined: {expr}")
                self.assertNotIn("null", expr, f"aria-controls expression should not produce null: {expr}")


if __name__ == "__main__":
    unittest.main()
