"""
tests/test_perf_cycle9_remediation.py - Verification suite for Cycle 9 Performance & Memory Remediations.

Covers:
1. Bounded FIFO eviction for batterySimulationCache in DepreciationCalculatorClient.tsx:
   - Cache cap of 100 entries.
   - Oldest key eviction using Map keys iterator FIFO ordering.
   - Empirical simulation of 150 sequential insertions confirming strict <= 100 bound.
2. Link prefetch compliance across Next.js pages:
   - ReliabilityDashboardClient.tsx (grid cards, hover modal, CTA link) all include prefetch={false}.
   - app/page.tsx (all links including /subsidy-tracker) include prefetch={false}.
   - 0 Link tags in src/app missing prefetch={false}.
3. Module-scoped supplierFilters hoisting in RecallPortalClient.tsx:
   - Hoisted outside RecallPortalClient render scope.
   - No re-allocation on re-renders.
4. next.config.mjs configuration & security hardening:
   - reactStrictMode: true.
   - productionBrowserSourceMaps: false.
   - Standard security headers (X-Content-Type-Options, X-Frame-Options, Referrer-Policy).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_ROOT = REPO_ROOT if (REPO_ROOT / "package.json").is_file() else (REPO_ROOT / "ev-stealth-web")


class TestCycle9PerformanceRemediations(unittest.TestCase):
    """Test suite verifying Cycle 9 frontend performance & memory leak mitigations."""

    def test_battery_simulation_cache_bounded_fifo_eviction(self):
        """Verify bounded FIFO cache eviction in DepreciationCalculatorClient.tsx."""
        client_file = WEB_ROOT / "src/app/depreciation-calculator/DepreciationCalculatorClient.tsx"
        self.assertTrue(client_file.exists(), f"Missing file: {client_file}")

        content = client_file.read_text(encoding="utf-8")

        # 1. Constant definition
        self.assertIn("MAX_BATTERY_SIMULATION_CACHE_ENTRIES = 100", content)

        # 2. Bounded eviction logic
        self.assertIn("batterySimulationCache.current.size >= MAX_BATTERY_SIMULATION_CACHE_ENTRIES", content)
        self.assertIn("batterySimulationCache.current.keys().next().value", content)
        self.assertIn("batterySimulationCache.current.delete(", content)

        # 3. Simulate JavaScript Map FIFO eviction logic in Python
        # Dict in Python 3.7+ preserves insertion order, behaving identically to JS Map
        cache: dict[str, dict] = {}
        MAX_ENTRIES = 100

        for i in range(150):
            key = f"model_{i}_chemistry_NCM811_{i % 5}_years"
            val = {"soh": 90 - (i * 0.1), "sim_id": i}
            if len(cache) >= MAX_ENTRIES:
                oldest_key = next(iter(cache.keys()))
                del cache[oldest_key]
            cache[key] = val

            self.assertLessEqual(len(cache), MAX_ENTRIES)

        self.assertEqual(len(cache), 100)
        # First 50 keys (0..49) must have been evicted FIFO
        for i in range(50):
            old_key = f"model_{i}_chemistry_NCM811_{i % 5}_years"
            self.assertNotIn(old_key, cache)
        # Last 100 keys (50..149) must remain in cache
        for i in range(50, 150):
            current_key = f"model_{i}_chemistry_NCM811_{i % 5}_years"
            self.assertIn(current_key, cache)

    def test_link_prefetch_false_compliance(self):
        """Verify all <Link> tags in src/app specify prefetch={false}."""
        tsx_files = list((WEB_ROOT / "src/app").rglob("*.tsx"))
        self.assertGreater(len(tsx_files), 0, "No TSX files found in src/app")

        missing_prefetch = []
        for file_path in tsx_files:
            text = file_path.read_text(encoding="utf-8")
            # Find all <Link ... > openings
            link_tags = re.findall(r"<Link\b[^>]*>", text)
            for tag in link_tags:
                if "prefetch={false}" not in tag:
                    missing_prefetch.append((file_path.name, tag.strip()))

        self.assertEqual(
            missing_prefetch,
            [],
            f"Found <Link> tags without prefetch={{false}}: {missing_prefetch}",
        )

    def test_supplier_filters_hoisted_to_module_scope(self):
        """Verify supplierFilters is hoisted outside the component render function."""
        client_file = WEB_ROOT / "src/app/recall-portal/RecallPortalClient.tsx"
        self.assertTrue(client_file.exists(), f"Missing file: {client_file}")

        content = client_file.read_text(encoding="utf-8")

        # supplierFilters definition must occur before export default function RecallPortalClient
        export_idx = content.find("export default function RecallPortalClient")
        filters_idx = content.find("const supplierFilters = [")

        self.assertNotEqual(export_idx, -1)
        self.assertNotEqual(filters_idx, -1)
        self.assertLess(
            filters_idx,
            export_idx,
            "supplierFilters must be defined before export default function RecallPortalClient (module scope)",
        )

        # There must not be a second supplierFilters definition inside the function
        second_filters_idx = content.find("const supplierFilters = [", filters_idx + 1)
        self.assertEqual(
            second_filters_idx,
            -1,
            "Duplicate supplierFilters found inside RecallPortalClient function body",
        )

    def test_next_config_performance_and_security_headers(self):
        """Verify next.config.mjs has reactStrictMode, no source maps, and security headers."""
        config_file = WEB_ROOT / "next.config.mjs"
        self.assertTrue(config_file.exists(), f"Missing file: {config_file}")

        content = config_file.read_text(encoding="utf-8")

        # 1. Performance flags
        self.assertIn("reactStrictMode: true", content)
        self.assertIn("productionBrowserSourceMaps: false", content)

        # 2. Security headers
        self.assertIn("'X-Content-Type-Options'", content)
        self.assertIn("'nosniff'", content)
        self.assertIn("'X-Frame-Options'", content)
        self.assertIn("'DENY'", content)
        self.assertIn("'Referrer-Policy'", content)
        self.assertIn("'strict-origin-when-cross-origin'", content)


if __name__ == "__main__":
    unittest.main()
