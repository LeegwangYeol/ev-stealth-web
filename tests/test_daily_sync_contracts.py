"""
tests/test_daily_sync_contracts.py - Comprehensive Daily Sync Contract & Parity Verification Suite.

Authoritative Specifications & Sources:
- ORIGINAL_REQUEST.md: Daily Subsidy Data Sync & Depletion Tracker Directives
- PROJECT.md: Scraper & Tracker Data Mirroring Topologies
- .agents/spec_miner_subsidy_w1/spec_analysis.md: Sections 4, 5, 6, 7
- .agents/spec_miner_subsidy_w1/handoff.md: Daily Sync Acceptance Gates

Verification Scope:
1. File Existence & Non-Emptiness:
   - Root data files: `data/ev_subsidy_data.json` and `data/subsidy_depletion_data.json`.
   - Web mirror data files: `ev-stealth-web/src/data/ev_subsidy_data.json` and `ev-stealth-web/src/data/subsidy_depletion_data.json`.
   - Minimum byte-size checks and valid UTF-8 JSON deserialization.
2. Mirror Parity & Consistency:
   - Exact byte-for-byte SHA-256 identity between root data files and `ev-stealth-web/src/data/`.
   - Structural and deep semantic equality between canonical files and legacy mirrors.
   - Dual-mirror consistency for defect reports (`data/daily_reports.json` vs `ev-stealth-web/src/data/daily_reports.json`).
3. Regional & Municipal Coverage:
   - Complete coverage of all 17 South Korean 1st-tier administrative divisions (ISO 3166-2:KR).
   - Complete coverage of all 73 tracked municipalities across all 17 regions.
   - Per-municipality and per-province schema integrity and uniqueness constraints.
4. Schema & Mathematical Invariants:
   - Required top-level keys (`metadata`, `alert_thresholds`, `nationwide_summary`, `regions`, `popular_models_matrix`, `historical_depletion_trajectory`).
   - Strict ISO-8601 UTC timestamp format compliance.
   - Budget positivity invariants (> 0 billion KRW for totals, strictly positive category allocations).
   - Remaining quota units non-negative clamping (`remaining == max(0, announced - applied)`).
   - 5-Tier alert threshold system definitions and monotonic bounds.
5. Subsidy Bracket Logic & Sliding Scale:
   - Statutory 2026 Korean Ministry of Environment price-cap tiers:
     - MSRP < 55,000,000 KRW: 100% subsidy (ratio 1.0)
     - 55,000,000 <= MSRP < 85,000,000 KRW: 50% subsidy (ratio 0.5)
     - MSRP >= 85,000,000 KRW: 0% subsidy (luxury exemption, ratio 0.0)
   - Popular models matrix adherence across all 10 tracked vehicles.
   - Proportional national/local subsidy formula and net price calculations.
6. Adversarial Verification:
   - Edge cases, zero division guards, extreme over-subscription, negative inputs, and boundary transitions.
"""

from __future__ import annotations

from datetime import datetime, timezone
import filecmp
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from typing import Any, Dict, List, Set, Tuple

# Adaptive root detection (works from repo root, tests/, ev-stealth-web/, or ev-stealth-web/tests/)
def _find_repo_root() -> Path:
    candidates = [
        Path(__file__).resolve().parent.parent,
        Path(__file__).resolve().parent.parent.parent,
        Path.cwd(),
        Path.cwd().parent,
    ]
    for p in candidates:
        if (p / "ev-stealth-web").is_dir() and (p / "data").is_dir():
            return p
    return Path(__file__).resolve().parent.parent

PROJECT_ROOT = _find_repo_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
WEB_ROOT = PROJECT_ROOT / "ev-stealth-web"
if str(WEB_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_ROOT))

import run_tracker
from tracker.subsidy_tracker import (
    SubsidyTracker,
    calculate_depletion_rate,
    calculate_net_subsidy,
    calculate_price_cap_ratio,
    calculate_remaining_units,
    classify_alert_tier,
)
from tracker.subsidy_models import AlertSeverity, SubsidyPayload
from tracker.subsidy_baseline import (
    DEFAULT_ALERT_THRESHOLDS,
    PASSENGER_NATIONAL_CAP_KRW,
    COMMERCIAL_NATIONAL_CAP_KRW,
    build_initial_baseline,
)

# Canonical File Paths
DATA_DIR = PROJECT_ROOT / "data"
WEB_DATA_DIR = WEB_ROOT / "src" / "data"

ROOT_SUBSIDY_DATA = DATA_DIR / "ev_subsidy_data.json"
ROOT_DEPLETION_DATA = DATA_DIR / "subsidy_depletion_data.json"
WEB_SUBSIDY_DATA = WEB_DATA_DIR / "ev_subsidy_data.json"
WEB_DEPLETION_DATA = WEB_DATA_DIR / "subsidy_depletion_data.json"

ROOT_DAILY_REPORTS = DATA_DIR / "daily_reports.json"
WEB_DAILY_REPORTS = WEB_DATA_DIR / "daily_reports.json"

RUN_TRACKER_SCRIPT = PROJECT_ROOT / "run_tracker.py"
if not RUN_TRACKER_SCRIPT.exists() and (WEB_ROOT / "run_tracker.py").exists():
    RUN_TRACKER_SCRIPT = WEB_ROOT / "run_tracker.py"

# All 17 statutory ISO 3166-2:KR codes
STATUTORY_17_ISO_CODES: Set[str] = {
    "KR-11",  # Seoul Special City
    "KR-26",  # Busan Metropolitan City
    "KR-27",  # Daegu Metropolitan City
    "KR-28",  # Incheon Metropolitan City
    "KR-29",  # Gwangju Metropolitan City
    "KR-30",  # Daejeon Metropolitan City
    "KR-31",  # Ulsan Metropolitan City
    "KR-36",  # Sejong Special Self-Governing City
    "KR-41",  # Gyeonggi Province
    "KR-42",  # Gangwon Special Self-Governing Province
    "KR-43",  # Chungcheongbuk-do
    "KR-44",  # Chungcheongnam-do
    "KR-45",  # Jeonbuk Special Self-Governing Province
    "KR-46",  # Jeollanam-do
    "KR-47",  # Gyeongsangbuk-do
    "KR-48",  # Gyeongsangnam-do
    "KR-49",  # Jeju Special Self-Governing Province
}

# Statutory municipality count distribution per province (total = 73)
EXPECTED_MUNICIPALITY_DISTRIBUTION: Dict[str, int] = {
    "KR-11": 6,   # Seoul districts
    "KR-41": 10,  # Gyeonggi cities
    "KR-26": 4,   # Busan districts/counties
    "KR-27": 4,   # Daegu districts/counties
    "KR-28": 4,   # Incheon districts/counties
    "KR-29": 3,   # Gwangju districts
    "KR-30": 3,   # Daejeon districts
    "KR-31": 3,   # Ulsan districts/county
    "KR-36": 1,   # Sejong
    "KR-42": 4,   # Gangwon cities/counties
    "KR-43": 4,   # Chungbuk cities/counties
    "KR-44": 5,   # Chungnam cities/counties
    "KR-45": 4,   # Jeonbuk cities/counties
    "KR-46": 6,   # Jeonnam cities/counties
    "KR-47": 5,   # Gyeongbuk cities/counties
    "KR-48": 5,   # Gyeongnam cities/counties
    "KR-49": 2,   # Jeju (Jeju-si, Seogwipo-si)
}

MIN_EXPECTED_FILE_SIZE_BYTES = 50_000

# Statutory residency rules: 30 days vs 90 days
STATUTORY_30_DAY_REGIONS: Set[str] = {
    "KR-11",  # Seoul Special City
    "KR-27",  # Daegu Metropolitan City
    "KR-28",  # Incheon Metropolitan City
    "KR-29",  # Gwangju Metropolitan City
    "KR-36",  # Sejong Special Self-Governing City
    "KR-41",  # Gyeonggi Province
    "KR-43",  # Chungcheongbuk-do
    "KR-44",  # Chungcheongnam-do
    "KR-45",  # Jeonbuk Special Self-Governing Province
    "KR-47",  # Gyeongsangbuk-do
    "KR-48",  # Gyeongnam
}

STATUTORY_90_DAY_REGIONS: Set[str] = {
    "KR-26",  # Busan Metropolitan City
    "KR-30",  # Daejeon Metropolitan City
    "KR-31",  # Ulsan Metropolitan City
    "KR-42",  # Gangwon Special Self-Governing Province
    "KR-46",  # Jeollanam-do
    "KR-49",  # Jeju Special Self-Governing Province
}

# Critical / Depleted alert hotspots (>= 95.0% depletion rate)
STATUTORY_CRITICAL_HOTSPOTS: Set[str] = {
    "KR-27",  # Daegu (96.4%)
    "KR-31",  # Ulsan (96.5%)
    "KR-47",  # Gyeongbuk (97.3%)
    "KR-49",  # Jeju (99.0%)
}

# Special statutory local subsidy anchors (province_id -> (municipality_name, local_subsidy_krw))
STATUTORY_SPECIAL_LOCAL_SUBSIDIES: Dict[str, Tuple[str, int]] = {
    "KR-11": ("종로구", 1_500_000),
    "KR-46": ("신안군", 11_500_000),
    "KR-47": ("울릉군", 11_000_000),
    "KR-44": ("태안군", 9_000_000),
}


def _compute_sha256(filepath: Path) -> str:
    """Compute hex SHA-256 digest of a given file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


# ==============================================================================
# 1. FILE EXISTENCE AND NON-EMPTINESS TESTS
# ==============================================================================

class TestFileExistenceAndNonEmptiness(unittest.TestCase):
    """Verifies that all primary data files and their web mirrors exist and are substantial."""

    def test_root_ev_subsidy_data_exists_and_non_empty(self) -> None:
        """Root data/ev_subsidy_data.json must exist, be a regular file, and exceed 50KB."""
        self.assertTrue(ROOT_SUBSIDY_DATA.exists(), f"Missing file: {ROOT_SUBSIDY_DATA}")
        self.assertTrue(ROOT_SUBSIDY_DATA.is_file(), f"Not a file: {ROOT_SUBSIDY_DATA}")
        size = ROOT_SUBSIDY_DATA.stat().st_size
        self.assertGreaterEqual(
            size,
            MIN_EXPECTED_FILE_SIZE_BYTES,
            f"File too small ({size} bytes, expected >= {MIN_EXPECTED_FILE_SIZE_BYTES})",
        )

    def test_root_subsidy_depletion_data_exists_and_non_empty(self) -> None:
        """Root data/subsidy_depletion_data.json must exist, be a regular file, and exceed 50KB."""
        self.assertTrue(ROOT_DEPLETION_DATA.exists(), f"Missing file: {ROOT_DEPLETION_DATA}")
        self.assertTrue(ROOT_DEPLETION_DATA.is_file(), f"Not a file: {ROOT_DEPLETION_DATA}")
        size = ROOT_DEPLETION_DATA.stat().st_size
        self.assertGreaterEqual(
            size,
            MIN_EXPECTED_FILE_SIZE_BYTES,
            f"File too small ({size} bytes, expected >= {MIN_EXPECTED_FILE_SIZE_BYTES})",
        )

    def test_web_mirror_ev_subsidy_data_exists_and_non_empty(self) -> None:
        """ev-stealth-web/src/data/ev_subsidy_data.json must exist, be a regular file, and exceed 50KB."""
        self.assertTrue(WEB_SUBSIDY_DATA.exists(), f"Missing file: {WEB_SUBSIDY_DATA}")
        self.assertTrue(WEB_SUBSIDY_DATA.is_file(), f"Not a file: {WEB_SUBSIDY_DATA}")
        size = WEB_SUBSIDY_DATA.stat().st_size
        self.assertGreaterEqual(
            size,
            MIN_EXPECTED_FILE_SIZE_BYTES,
            f"File too small ({size} bytes, expected >= {MIN_EXPECTED_FILE_SIZE_BYTES})",
        )

    def test_web_mirror_subsidy_depletion_data_exists_and_non_empty(self) -> None:
        """ev-stealth-web/src/data/subsidy_depletion_data.json must exist, be a regular file, and exceed 50KB."""
        self.assertTrue(WEB_DEPLETION_DATA.exists(), f"Missing file: {WEB_DEPLETION_DATA}")
        self.assertTrue(WEB_DEPLETION_DATA.is_file(), f"Not a file: {WEB_DEPLETION_DATA}")
        size = WEB_DEPLETION_DATA.stat().st_size
        self.assertGreaterEqual(
            size,
            MIN_EXPECTED_FILE_SIZE_BYTES,
            f"File too small ({size} bytes, expected >= {MIN_EXPECTED_FILE_SIZE_BYTES})",
        )

    def test_defect_reports_files_exist_and_non_empty(self) -> None:
        """Both root and web mirror daily_reports.json must exist and exceed 20KB."""
        for path in (ROOT_DAILY_REPORTS, WEB_DAILY_REPORTS):
            with self.subTest(path=str(path)):
                self.assertTrue(path.exists(), f"Missing defect report: {path}")
                self.assertTrue(path.is_file(), f"Not a file: {path}")
                self.assertGreaterEqual(path.stat().st_size, 20_000)

    def test_all_tracked_files_valid_utf8_json(self) -> None:
        """All 6 tracked JSON files must deserialize cleanly as valid UTF-8 JSON objects."""
        target_files = [
            ROOT_SUBSIDY_DATA,
            ROOT_DEPLETION_DATA,
            WEB_SUBSIDY_DATA,
            WEB_DEPLETION_DATA,
            ROOT_DAILY_REPORTS,
            WEB_DAILY_REPORTS,
        ]
        for filepath in target_files:
            with self.subTest(file=filepath.name):
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.assertIsInstance(data, dict)
                self.assertGreater(len(data), 0)


# ==============================================================================
# 2. EXACT PARITY AND MIRROR CONSISTENCY TESTS
# ==============================================================================

class TestMirrorParityAndConsistency(unittest.TestCase):
    """Verifies byte-for-byte and deep semantic identity between root data files and web mirrors."""

    def test_primary_subsidy_root_vs_web_byte_parity(self) -> None:
        """data/ev_subsidy_data.json and ev-stealth-web/src/data/ev_subsidy_data.json must be byte-for-byte identical."""
        self.assertTrue(
            filecmp.cmp(ROOT_SUBSIDY_DATA, WEB_SUBSIDY_DATA, shallow=False),
            "Primary subsidy data between root and web mirror differs in byte content!",
        )
        hash_root = _compute_sha256(ROOT_SUBSIDY_DATA)
        hash_web = _compute_sha256(WEB_SUBSIDY_DATA)
        self.assertEqual(hash_root, hash_web, "SHA-256 hash mismatch between primary root and web mirror!")

    def test_depletion_mirror_root_vs_web_byte_parity(self) -> None:
        """data/subsidy_depletion_data.json and ev-stealth-web/src/data/subsidy_depletion_data.json must be byte-for-byte identical."""
        self.assertTrue(
            filecmp.cmp(ROOT_DEPLETION_DATA, WEB_DEPLETION_DATA, shallow=False),
            "Depletion mirror data between root and web mirror differs in byte content!",
        )
        hash_root = _compute_sha256(ROOT_DEPLETION_DATA)
        hash_web = _compute_sha256(WEB_DEPLETION_DATA)
        self.assertEqual(hash_root, hash_web, "SHA-256 hash mismatch between depletion root and web mirror!")

    def test_root_primary_vs_depletion_mirror_byte_parity(self) -> None:
        """data/ev_subsidy_data.json and data/subsidy_depletion_data.json must be byte-for-byte identical."""
        self.assertTrue(
            filecmp.cmp(ROOT_SUBSIDY_DATA, ROOT_DEPLETION_DATA, shallow=False),
            "Root ev_subsidy_data.json and root subsidy_depletion_data.json are not identical!",
        )

    def test_web_primary_vs_depletion_mirror_byte_parity(self) -> None:
        """ev-stealth-web/src/data/ev_subsidy_data.json and web subsidy_depletion_data.json must be byte-for-byte identical."""
        self.assertTrue(
            filecmp.cmp(WEB_SUBSIDY_DATA, WEB_DEPLETION_DATA, shallow=False),
            "Web ev_subsidy_data.json and web subsidy_depletion_data.json are not identical!",
        )

    def test_defect_reports_root_vs_web_mirror_parity(self) -> None:
        """data/daily_reports.json and ev-stealth-web/src/data/daily_reports.json must be byte-for-byte identical."""
        self.assertTrue(
            filecmp.cmp(ROOT_DAILY_REPORTS, WEB_DAILY_REPORTS, shallow=False),
            "Defect report daily_reports.json differs between root and web mirror!",
        )
        hash_root = _compute_sha256(ROOT_DAILY_REPORTS)
        hash_web = _compute_sha256(WEB_DAILY_REPORTS)
        self.assertEqual(hash_root, hash_web, "SHA-256 mismatch between defect reports root and web mirror!")

    def test_deep_json_structural_parity(self) -> None:
        """All four subsidy files must parse to semantically identical data structures."""
        with open(ROOT_SUBSIDY_DATA, "r", encoding="utf-8") as f:
            data_root_primary = json.load(f)
        with open(ROOT_DEPLETION_DATA, "r", encoding="utf-8") as f:
            data_root_mirror = json.load(f)
        with open(WEB_SUBSIDY_DATA, "r", encoding="utf-8") as f:
            data_web_primary = json.load(f)
        with open(WEB_DEPLETION_DATA, "r", encoding="utf-8") as f:
            data_web_mirror = json.load(f)

        self.assertEqual(data_root_primary, data_root_mirror)
        self.assertEqual(data_root_primary, data_web_primary)
        self.assertEqual(data_root_primary, data_web_mirror)

    def test_all_shared_data_files_sha256_parity(self) -> None:
        """Every file present in both root data/ and ev-stealth-web/src/data/ must maintain 100% SHA-256 byte parity."""
        root_files = {p.name: p for p in DATA_DIR.glob("*.json")}
        web_files = {p.name: p for p in WEB_DATA_DIR.glob("*.json")}
        common_filenames = sorted(root_files.keys() & web_files.keys())

        # Must at least include primary datasets
        self.assertIn("ev_subsidy_data.json", common_filenames)
        self.assertIn("subsidy_depletion_data.json", common_filenames)
        self.assertIn("daily_reports.json", common_filenames)

        for fname in common_filenames:
            root_path = root_files[fname]
            web_path = web_files[fname]
            with self.subTest(file=fname):
                # 1. Non-zero size match
                root_size = root_path.stat().st_size
                web_size = web_path.stat().st_size
                self.assertGreater(root_size, 0, f"{root_path} is empty (0 bytes)")
                self.assertEqual(root_size, web_size, f"Size mismatch for {fname}: root={root_size} vs web={web_size}")

                # 2. SHA-256 exact match
                root_hash = _compute_sha256(root_path)
                web_hash = _compute_sha256(web_path)
                self.assertEqual(root_hash, web_hash, f"SHA-256 mismatch for {fname}: root={root_hash} vs web={web_hash}")

                # 3. Byte-level filecmp identity
                self.assertTrue(
                    filecmp.cmp(root_path, web_path, shallow=False),
                    f"filecmp mismatch for {fname} between root and web mirror!",
                )

    def test_sha256_recomputation_durability(self) -> None:
        """SHA-256 calculation must be completely deterministic across varied buffer chunk sizes."""
        for path in (ROOT_SUBSIDY_DATA, WEB_SUBSIDY_DATA, ROOT_DAILY_REPORTS, WEB_DAILY_REPORTS):
            with self.subTest(path=path.name):
                hashes: Set[str] = set()
                for chunk_size in (128, 1024, 4096, 65536):
                    hasher = hashlib.sha256()
                    with open(path, "rb") as f:
                        while chunk := f.read(chunk_size):
                            hasher.update(chunk)
                    hashes.add(hasher.hexdigest())
                self.assertEqual(len(hashes), 1, f"Non-deterministic SHA-256 hashing across chunk sizes for {path}")

    def test_tracker_save_payload_maintains_exact_byte_parity_across_destinations(self) -> None:
        """SubsidyTracker.save_payload must write byte-for-byte identical files with matching SHA-256 hashes."""
        tracker = SubsidyTracker(timeout_seconds=2.0)
        payload = build_initial_baseline()

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir) / "root" / "data"
            tmp_web = Path(tmp_dir) / "web" / "src" / "data"
            tmp_root.mkdir(parents=True, exist_ok=True)
            tmp_web.mkdir(parents=True, exist_ok=True)

            dst1 = tmp_root / "ev_subsidy_data.json"
            dst2 = tmp_web / "ev_subsidy_data.json"

            written = tracker.save_payload(payload, [dst1, dst2])
            self.assertEqual(len(written), 2)
            self.assertTrue(dst1.exists())
            self.assertTrue(dst2.exists())
            self.assertEqual(dst1.stat().st_size, dst2.stat().st_size)
            self.assertTrue(filecmp.cmp(dst1, dst2, shallow=False))
            self.assertEqual(_compute_sha256(dst1), _compute_sha256(dst2))


# ==============================================================================
# 3. REGIONAL (17 PROVINCES) AND MUNICIPAL (73 MUNICIPALITIES) COVERAGE TESTS
# ==============================================================================

class TestRegionalAndMunicipalCoverage(unittest.TestCase):
    """Verifies coverage and data integrity for all 17 metropolitan provinces and 73 municipalities."""

    @classmethod
    def setUpClass(cls) -> None:
        with open(ROOT_SUBSIDY_DATA, "r", encoding="utf-8") as f:
            cls.data = json.load(f)
        cls.regions: List[Dict[str, Any]] = cls.data["regions"]

    def test_17_provinces_exact_count(self) -> None:
        """The dataset must track exactly 17 first-tier administrative divisions."""
        self.assertEqual(
            len(self.regions),
            17,
            f"Expected exactly 17 regions, found {len(self.regions)}",
        )
        self.assertEqual(
            self.data["metadata"]["total_regions_tracked"],
            17,
            "metadata.total_regions_tracked must equal 17",
        )

    def test_17_provinces_iso_codes_complete_set(self) -> None:
        """All 17 statutory ISO 3166-2:KR codes must be present without omissions or extras."""
        observed_codes = {r["region_id"] for r in self.regions}
        self.assertEqual(
            observed_codes,
            STATUTORY_17_ISO_CODES,
            f"ISO codes mismatch! Missing: {STATUTORY_17_ISO_CODES - observed_codes}, Extra: {observed_codes - STATUTORY_17_ISO_CODES}",
        )
        for r in self.regions:
            self.assertEqual(
                r["region_id"],
                r["iso_code"],
                f"Region ID '{r['region_id']}' does not match iso_code '{r['iso_code']}'",
            )

    def test_17_provinces_statutory_names_and_tiers(self) -> None:
        """Each region must have official Korean/English names, recognized tier, and valid residency."""
        valid_tiers = {
            "special_city",
            "metropolitan_city",
            "special_self_governing_city",
            "province",
            "special_self_governing_province",
        }
        for r in self.regions:
            with self.subTest(region=r["region_id"]):
                self.assertTrue(r["name_ko"], f"Missing name_ko for {r['region_id']}")
                self.assertTrue(r["name_en"], f"Missing name_en for {r['region_id']}")
                self.assertIn(r["tier"], valid_tiers, f"Invalid tier '{r['tier']}' in {r['region_id']}")
                self.assertIn(
                    r["residency_requirement_days"],
                    [30, 90],
                    f"Unexpected residency days {r['residency_requirement_days']} for {r['region_id']}",
                )
                self.assertIn("categories", r)
                self.assertIn("passenger", r["categories"])
                self.assertIn("commercial", r["categories"])
                self.assertIn("bus", r["categories"])

    def test_73_municipalities_total_count(self) -> None:
        """The total number of tracked municipalities across all 17 regions must be exactly 73."""
        total_munis = sum(len(r.get("municipalities", [])) for r in self.regions)
        self.assertEqual(
            total_munis,
            73,
            f"Expected exactly 73 municipalities across all regions, found {total_munis}",
        )
        self.assertEqual(
            self.data["metadata"]["total_municipalities_tracked"],
            73,
            "metadata.total_municipalities_tracked must equal 73",
        )

    def test_municipalities_per_province_distribution(self) -> None:
        """Every region must match the authoritative statutory municipality distribution."""
        for region in self.regions:
            region_id = region["region_id"]
            with self.subTest(region=region_id):
                munis = region.get("municipalities", [])
                expected_count = EXPECTED_MUNICIPALITY_DISTRIBUTION.get(region_id)
                self.assertIsNotNone(expected_count, f"Unknown region: {region_id}")
                self.assertEqual(
                    len(munis),
                    expected_count,
                    f"Region {region_id} ({region['name_ko']}) has {len(munis)} municipalities, expected {expected_count}",
                )

    def test_all_municipalities_data_completeness(self) -> None:
        """Every municipality record must have required fields, valid positive values, and valid status."""
        valid_statuses = {"HEALTHY", "CAUTION", "WARNING", "CRITICAL", "DEPLETED"}
        all_munis: List[Tuple[str, Dict[str, Any]]] = [
            (r["name_ko"], m) for r in self.regions for m in r.get("municipalities", [])
        ]
        self.assertEqual(len(all_munis), 73)

        for province_name, muni in all_munis:
            with self.subTest(province=province_name, muni=muni.get("name_ko")):
                self.assertIn("name_ko", muni)
                self.assertTrue(muni["name_ko"])
                self.assertIn("announced_units", muni)
                self.assertGreater(muni["announced_units"], 0)
                self.assertIn("applied_units", muni)
                self.assertGreaterEqual(muni["applied_units"], 0)
                self.assertIn("remaining_units", muni)
                self.assertGreaterEqual(muni["remaining_units"], 0)
                self.assertIn("depletion_rate", muni)
                self.assertGreaterEqual(muni["depletion_rate"], 0.0)
                self.assertIn("status", muni)
                self.assertIn(muni["status"], valid_statuses)
                self.assertIn("local_subsidy_krw", muni)
                self.assertGreater(muni["local_subsidy_krw"], 0)

    def test_no_duplicate_municipality_names_within_province(self) -> None:
        """Within each region, every municipality Korean name must be unique."""
        for r in self.regions:
            munis = r.get("municipalities", [])
            names = [m["name_ko"] for m in munis]
            self.assertEqual(
                len(names),
                len(set(names)),
                f"Duplicate municipality names detected in {r['region_id']} ({r['name_ko']}): {names}",
            )

    def test_17_provinces_statutory_residency_rules(self) -> None:
        """Verify statutory residency rules: 11 regions require 30 days, 6 regions require 90 days."""
        observed_30: Set[str] = set()
        observed_90: Set[str] = set()

        for r in self.regions:
            rid = r["region_id"]
            days = r["residency_requirement_days"]
            if days == 30:
                observed_30.add(rid)
            elif days == 90:
                observed_90.add(rid)
            else:
                self.fail(f"Region {rid} has non-statutory residency requirement: {days} days")

        self.assertEqual(
            observed_30,
            STATUTORY_30_DAY_REGIONS,
            f"30-day residency mismatch! Diff: {observed_30 ^ STATUTORY_30_DAY_REGIONS}",
        )
        self.assertEqual(
            observed_90,
            STATUTORY_90_DAY_REGIONS,
            f"90-day residency mismatch! Diff: {observed_90 ^ STATUTORY_90_DAY_REGIONS}",
        )
        self.assertEqual(len(observed_30) + len(observed_90), 17)

    def test_regional_category_delivered_units_bounded_by_applied(self) -> None:
        """For every region and category, delivered units must not exceed applied units, and delivery rate must match."""
        for r in self.regions:
            for cat_name, cat in r["categories"].items():
                with self.subTest(region=r["region_id"], category=cat_name):
                    self.assertGreaterEqual(cat["delivered_units"], 0)
                    self.assertLessEqual(
                        cat["delivered_units"],
                        cat["applied_units"],
                        f"Region {r['region_id']} {cat_name} delivered ({cat['delivered_units']}) exceeds applied ({cat['applied_units']})",
                    )
                    expected_delivery_rate = round(
                        (cat["delivered_units"] / cat["announced_units"]) * 100.0, 1
                    ) if cat["announced_units"] > 0 else 0.0
                    self.assertEqual(cat["delivery_rate"], expected_delivery_rate)

    def test_statutory_hotspot_regions_alert_severity(self) -> None:
        """Authoritative critical alert hotspots (Daegu, Ulsan, Gyeongbuk, Jeju) must have >=95% depletion and CRITICAL/DEPLETED status."""
        hotspot_records = {r["region_id"]: r for r in self.regions if r["region_id"] in STATUTORY_CRITICAL_HOTSPOTS}
        self.assertEqual(len(hotspot_records), 4)

        for rid, record in hotspot_records.items():
            with self.subTest(region=rid):
                passenger_cat = record["categories"]["passenger"]
                self.assertGreaterEqual(
                    passenger_cat["depletion_rate"],
                    95.0,
                    f"Hotspot {rid} ({record['name_ko']}) depletion rate {passenger_cat['depletion_rate']} is below 95.0%",
                )
                self.assertIn(
                    passenger_cat["status"],
                    ("CRITICAL", "DEPLETED"),
                    f"Hotspot {rid} status {passenger_cat['status']} is not CRITICAL or DEPLETED",
                )

    def test_all_73_municipalities_subsidy_amounts_statutory_bounds(self) -> None:
        """Every municipality's local subsidy must fall between 1M and 15M KRW, with statutory anchors strictly verified."""
        region_map = {r["region_id"]: r for r in self.regions}

        # Check all 73
        for r in self.regions:
            for m in r.get("municipalities", []):
                with self.subTest(muni=m["name_ko"]):
                    self.assertGreaterEqual(m["local_subsidy_krw"], 1_000_000)
                    self.assertLessEqual(m["local_subsidy_krw"], 15_000_000)

        # Check specific statutory anchors
        for rid, (muni_name, expected_subsidy) in STATUTORY_SPECIAL_LOCAL_SUBSIDIES.items():
            with self.subTest(anchor_region=rid, anchor_muni=muni_name):
                region = region_map[rid]
                matches = [m for m in region.get("municipalities", []) if m["name_ko"] == muni_name]
                self.assertTrue(matches, f"Anchor municipality '{muni_name}' not found in {rid}")
                self.assertEqual(
                    matches[0]["local_subsidy_krw"],
                    expected_subsidy,
                    f"Anchor {muni_name} subsidy {matches[0]['local_subsidy_krw']} != expected {expected_subsidy}",
                )

    def test_all_73_municipalities_status_matches_classification(self) -> None:
        """Every municipality's reported status must strictly match classify_alert_tier(depletion_rate)."""
        for r in self.regions:
            for m in r.get("municipalities", []):
                with self.subTest(region=r["region_id"], muni=m["name_ko"]):
                    expected_status = classify_alert_tier(m["depletion_rate"])
                    self.assertEqual(
                        m["status"],
                        expected_status,
                        f"Status mismatch in {m['name_ko']}: got {m['status']}, expected {expected_status} for {m['depletion_rate']}%",
                    )


# ==============================================================================
# 4. SCHEMA AND MATHEMATICAL INVARIANTS VALIDATION TESTS
# ==============================================================================

class TestSchemaAndInvariantsValidation(unittest.TestCase):
    """Verifies schema structure, ISO-8601 timestamps, budget positivity, and unit clamping."""

    @classmethod
    def setUpClass(cls) -> None:
        with open(ROOT_SUBSIDY_DATA, "r", encoding="utf-8") as f:
            cls.data = json.load(f)

    def test_required_top_level_keys(self) -> None:
        """Top-level dictionary must contain all 6 required keys."""
        required_keys = {
            "metadata",
            "alert_thresholds",
            "nationwide_summary",
            "regions",
            "popular_models_matrix",
            "historical_depletion_trajectory",
        }
        self.assertTrue(
            required_keys.issubset(self.data.keys()),
            f"Missing required top-level keys: {required_keys - set(self.data.keys())}",
        )

    def test_metadata_schema_invariants(self) -> None:
        """metadata object must satisfy data types and statutory configuration constraints."""
        meta = self.data["metadata"]
        self.assertRegex(meta["version"], r"^\d+\.\d+\.\d+$", "version must be semantic versioning")
        self.assertEqual(meta["policy_year"], 2026, "policy_year must be 2026")
        self.assertIsInstance(meta["data_sources"], list)
        self.assertGreaterEqual(len(meta["data_sources"]), 1)
        self.assertEqual(meta["currency"], "KRW", "currency must be KRW")
        self.assertEqual(meta["total_regions_tracked"], 17)
        self.assertEqual(meta["total_municipalities_tracked"], 73)

    def test_iso8601_timestamps_validity(self) -> None:
        """metadata.generated_at must parse as a valid timezone-aware ISO-8601 timestamp."""
        ts_str = self.data["metadata"]["generated_at"]
        try:
            dt = datetime.fromisoformat(ts_str)
        except Exception as e:
            self.fail(f"Failed to parse generated_at '{ts_str}' as ISO-8601: {e}")
        self.assertIsNotNone(dt.tzinfo, f"generated_at '{ts_str}' must be timezone-aware")

        # Verify historical depletion trajectory dates format (YYYY-MM-DD)
        for point in self.data["historical_depletion_trajectory"]:
            self.assertRegex(
                point["date"],
                r"^\d{4}-\d{2}-\d{2}$",
                f"Historical trajectory date '{point['date']}' is not YYYY-MM-DD",
            )
            # Verify can parse as real date
            datetime.strptime(point["date"], "%Y-%m-%d")

    def test_budget_numbers_strictly_positive(self) -> None:
        """Nationwide and regional category budgets must be strictly positive (> 0)."""
        summary = self.data["nationwide_summary"]
        self.assertGreater(
            summary["total_budget_billion_krw"],
            0.0,
            "Nationwide total budget in billion KRW must be > 0",
        )
        self.assertGreater(
            summary["disbursed_budget_billion_krw"],
            0.0,
            "Nationwide disbursed budget in billion KRW must be > 0",
        )

        # Check regional category budgets
        for r in self.data["regions"]:
            for cat_name, cat in r["categories"].items():
                with self.subTest(region=r["region_id"], category=cat_name):
                    self.assertGreater(
                        cat["total_budget_krw"],
                        0,
                        f"Region {r['region_id']} {cat_name} total_budget_krw must be > 0",
                    )
                    self.assertGreaterEqual(
                        cat["remaining_budget_krw"],
                        0,
                        f"Region {r['region_id']} {cat_name} remaining_budget_krw must be >= 0",
                    )
                    # Disbursed budget is total - remaining
                    disbursed = cat["total_budget_krw"] - cat["remaining_budget_krw"]
                    self.assertGreaterEqual(
                        disbursed,
                        0,
                        f"Region {r['region_id']} {cat_name} disbursed budget must be >= 0",
                    )
                    self.assertGreater(
                        cat["max_local_subsidy_krw"],
                        0,
                        f"Region {r['region_id']} {cat_name} max_local_subsidy_krw must be > 0",
                    )
                    self.assertGreater(
                        cat["max_total_subsidy_krw"],
                        0,
                        f"Region {r['region_id']} {cat_name} max_total_subsidy_krw must be > 0",
                    )

    def test_remaining_units_clamping_and_invariants(self) -> None:
        """remaining_units must be >= 0 and satisfy max(0, announced - applied) across all tiers."""
        # 1. Nationwide summary
        summary = self.data["nationwide_summary"]
        self.assertGreaterEqual(summary["total_remaining_units"], 0)
        expected_nationwide_remaining = max(
            0, summary["total_announced_units"] - summary["total_applied_units"]
        )
        self.assertEqual(
            summary["total_remaining_units"],
            expected_nationwide_remaining,
            "Nationwide total_remaining_units invariant failed",
        )

        # 2. Regional categories
        for r in self.data["regions"]:
            for cat_name, cat in r["categories"].items():
                with self.subTest(region=r["region_id"], category=cat_name):
                    self.assertGreaterEqual(
                        cat["remaining_units"],
                        0,
                        f"Negative remaining units in {r['region_id']} {cat_name}",
                    )
                    expected_remaining = max(0, cat["announced_units"] - cat["applied_units"])
                    self.assertEqual(
                        cat["remaining_units"],
                        expected_remaining,
                        f"Clamping invariant failed in {r['region_id']} {cat_name}",
                    )
                    # Depletion rate calculation invariant
                    expected_rate = (
                        round((cat["applied_units"] / cat["announced_units"]) * 100.0, 1)
                        if cat["announced_units"] > 0
                        else 0.0
                    )
                    self.assertEqual(cat["depletion_rate"], expected_rate)

        # 3. All 73 municipalities
        for r in self.data["regions"]:
            for m in r.get("municipalities", []):
                with self.subTest(muni=m["name_ko"]):
                    self.assertGreaterEqual(m["remaining_units"], 0)
                    expected_muni_remaining = max(0, m["announced_units"] - m["applied_units"])
                    self.assertEqual(
                        m["remaining_units"],
                        expected_muni_remaining,
                        f"Clamping invariant failed in municipality {m['name_ko']}",
                    )
                    expected_muni_rate = round(
                        (m["applied_units"] / m["announced_units"]) * 100.0, 1
                    )
                    self.assertEqual(m["depletion_rate"], expected_muni_rate)

    def test_5_tier_alert_thresholds_schema(self) -> None:
        """The alert_thresholds dictionary must define the 5 standard tiers monotonically."""
        expected_tiers = ["HEALTHY", "CAUTION", "WARNING", "CRITICAL", "DEPLETED"]
        thresholds = self.data["alert_thresholds"]
        self.assertEqual(list(thresholds.keys()), expected_tiers)

        for tier in expected_tiers:
            t = thresholds[tier]
            self.assertIn("min_percent", t)
            self.assertIn("max_percent", t)
            self.assertIn("label_ko", t)
            self.assertIn("color_hex", t)
            self.assertIn("badge_class", t)
            self.assertIn("recommended_action", t)
            self.assertLess(t["min_percent"], t["max_percent"])
            self.assertTrue(t["color_hex"].startswith("#"))

    def test_alert_thresholds_strict_monotonicity(self) -> None:
        """The 5 alert tiers must have strictly monotonically increasing min_percent bounds."""
        thresholds = self.data["alert_thresholds"]
        tier_order = ["HEALTHY", "CAUTION", "WARNING", "CRITICAL", "DEPLETED"]
        min_values = [thresholds[t]["min_percent"] for t in tier_order]

        # Verify exact statutory progression: 0.0 < 60.0 < 80.0 < 95.0 < 100.0
        self.assertEqual(min_values, [0.0, 60.0, 80.0, 95.0, 100.0])
        for i in range(len(min_values) - 1):
            self.assertLess(
                min_values[i],
                min_values[i + 1],
                f"Non-monotonic tier min_percent: {tier_order[i]} ({min_values[i]}) >= {tier_order[i+1]} ({min_values[i+1]})",
            )

        # In addition, each tier's min_percent must be strictly less than its max_percent
        for tier in tier_order:
            t = thresholds[tier]
            self.assertLess(t["min_percent"], t["max_percent"])

    def test_historical_trajectory_chronological_and_depletion_monotonicity(self) -> None:
        """Historical trajectory points must be in strict chronological order and rates must be monotonically non-decreasing."""
        trajectory = self.data["historical_depletion_trajectory"]
        self.assertGreaterEqual(len(trajectory), 2, "Trajectory must contain at least 2 time points")

        dates = [p["date"] for p in trajectory]
        overall_rates = [p["overall_rate"] for p in trajectory]
        passenger_rates = [p["passenger_rate"] for p in trajectory]
        commercial_rates = [p["commercial_rate"] for p in trajectory]

        # 1. Strict chronological date ordering
        self.assertEqual(dates, sorted(dates), "Trajectory dates are not sorted chronologically")
        self.assertEqual(len(dates), len(set(dates)), "Duplicate dates detected in trajectory")

        # 2. Monotonically non-decreasing rates over time
        for i in range(len(trajectory) - 1):
            with self.subTest(idx=i, date_a=dates[i], date_b=dates[i + 1]):
                self.assertLessEqual(
                    overall_rates[i],
                    overall_rates[i + 1],
                    f"Overall depletion rate decreased from {dates[i]} ({overall_rates[i]}%) to {dates[i+1]} ({overall_rates[i+1]}%)",
                )
                self.assertLessEqual(
                    passenger_rates[i],
                    passenger_rates[i + 1],
                    f"Passenger rate decreased from {dates[i]} ({passenger_rates[i]}%) to {dates[i+1]} ({passenger_rates[i+1]}%)",
                )
                self.assertLessEqual(
                    commercial_rates[i],
                    commercial_rates[i + 1],
                    f"Commercial rate decreased from {dates[i]} ({commercial_rates[i]}%) to {dates[i+1]} ({commercial_rates[i+1]}%)",
                )


# ==============================================================================
# 5. SUBSIDY BRACKET LOGIC TESTS
# ==============================================================================

class TestSubsidyBracketLogic(unittest.TestCase):
    """Verifies statutory 2026 price-cap subsidy brackets: <=55M (100%), 55M-85M (50%), >85M (0%)."""

    @classmethod
    def setUpClass(cls) -> None:
        with open(ROOT_SUBSIDY_DATA, "r", encoding="utf-8") as f:
            cls.data = json.load(f)
        cls.models = cls.data["popular_models_matrix"]

    def test_statutory_price_cap_ratio_function_boundaries(self) -> None:
        """Test calculate_price_cap_ratio function at exact boundary values and representative points."""
        test_cases = [
            # Bracket 1: 100% subsidy (ratio 1.0) for MSRP <= 55,000,000 KRW
            (0, 1.0),
            (15_000_000, 1.0),
            (26_900_000, 1.0),   # BYD Dolphin
            (31_500_000, 1.0),   # Hyundai Casper EV
            (39_950_000, 1.0),   # Kia EV3
            (51_990_000, 1.0),   # Tesla Model 3 RWD
            (54_100_000, 1.0),   # Hyundai Ioniq 5
            (54_999_999, 1.0),   # Exact 1 KRW below threshold
            (55_000_000, 1.0),   # Exact statutory 100% boundary (<= 55M)

            # Bracket 2: 50% subsidy (ratio 0.5) for 55,000,000 < MSRP <= 85,000,000 KRW
            (55_000_001, 0.5),   # Exact boundary + 1 KRW
            (60_000_000, 0.5),
            (73_370_000, 0.5),   # Kia EV9
            (84_999_999, 0.5),   # Exact 1 KRW below luxury threshold
            (85_000_000, 0.5),   # Exact statutory 50% boundary (<= 85M)

            # Bracket 3: 0% subsidy (ratio 0.0) for MSRP > 85,000,000 KRW
            (85_000_001, 0.0),   # Exact boundary + 1 KRW
            (92_000_000, 0.0),   # Genesis Electrified G80
            (120_000_000, 0.0),  # Tesla Model S / Porsche Taycan
            (250_000_000, 0.0),  # Super luxury EV
        ]
        for price, expected_ratio in test_cases:
            with self.subTest(price=price, expected_ratio=expected_ratio):
                actual_ratio = calculate_price_cap_ratio(price)
                self.assertEqual(
                    actual_ratio,
                    expected_ratio,
                    f"MSRP {price:,} KRW returned ratio {actual_ratio}, expected {expected_ratio}",
                )

    def test_popular_models_matrix_bracket_compliance(self) -> None:
        """Every vehicle in popular_models_matrix must satisfy statutory price brackets."""
        self.assertGreaterEqual(
            len(self.models),
            10,
            f"Expected at least 10 popular vehicle models, found {len(self.models)}",
        )

        for model in self.models:
            model_id = model["model_id"]
            price = model["base_price_krw"]
            ratio = model["price_subsidy_ratio"]
            with self.subTest(model=model_id, price=price):
                self.assertGreater(price, 0)
                expected_ratio = calculate_price_cap_ratio(price)
                self.assertEqual(
                    ratio,
                    expected_ratio,
                    f"Model {model_id} price {price:,} has ratio {ratio}, expected {expected_ratio}",
                )
                if price <= 55_000_000:
                    self.assertEqual(ratio, 1.0, f"Model {model_id} (<=55M) must have ratio 1.0")
                elif price <= 85_000_000:
                    self.assertEqual(ratio, 0.5, f"Model {model_id} (55M-85M) must have ratio 0.5")
                else:
                    self.assertEqual(ratio, 0.0, f"Model {model_id} (>85M) must have ratio 0.0")

    def test_popular_models_subsidy_values_consistency(self) -> None:
        """National subsidy caps must adhere to statutory ceilings, and regional net prices must match."""
        for model in self.models:
            model_id = model["model_id"]
            price = model["base_price_krw"]
            national_sub = model["national_subsidy_krw"]
            ratio = model["price_subsidy_ratio"]

            with self.subTest(model=model_id):
                # National subsidy cannot exceed max national cap * price ratio
                max_allowable_national = int(round(PASSENGER_NATIONAL_CAP_KRW * ratio))
                self.assertLessEqual(
                    national_sub,
                    max_allowable_national,
                    f"Model {model_id} national subsidy {national_sub:,} exceeds ceiling {max_allowable_national:,}",
                )

                # Regional samples net price formula: net_price == base_price - total_subsidy
                regional_samples = model.get("regional_subsidy_samples", {})
                self.assertGreater(len(regional_samples), 0)
                for reg_key, sample in regional_samples.items():
                    tot_sub = sample["total_subsidy_krw"]
                    net_p = sample["net_price_krw"]
                    self.assertEqual(
                        net_p,
                        price - tot_sub,
                        f"Net price mismatch in {model_id} for {reg_key}: {net_p} != {price} - {tot_sub}",
                    )
                    self.assertGreaterEqual(tot_sub, 0)
                    self.assertGreater(net_p, 0)

    def test_net_subsidy_calculation_oracle(self) -> None:
        """Verify calculate_net_subsidy formula matches authoritative statutory expectations."""
        # Case A: Model under 55M (ratio 1.0)
        # Model Nat = 6,500,000, Max Nat = 6,500,000, Max Local = 1,500,000 (Seoul), MSRP = 54,100,000
        res_a = calculate_net_subsidy(
            model_national=6_500_000,
            max_national=6_500_000,
            max_local=1_500_000,
            msrp=54_100_000,
        )
        self.assertEqual(res_a["national_subsidy_krw"], 6_500_000)
        self.assertEqual(res_a["local_subsidy_krw"], 1_500_000)
        self.assertEqual(res_a["total_subsidy_krw"], 8_000_000)
        self.assertEqual(res_a["net_price_krw"], 46_100_000)

        # Case B: Model 55M-85M (ratio 0.5, e.g. EV9 base)
        # Model Nat = 6,020,000, Max Nat = 6,500,000, Max Local = 1,500,000, MSRP = 73,370,000
        res_b = calculate_net_subsidy(
            model_national=6_020_000,
            max_national=6_500_000,
            max_local=1_500_000,
            msrp=73_370_000,
        )
        # effective national = round(6,020,000 * 0.5) = 3,010,000
        self.assertEqual(res_b["national_subsidy_krw"], 3_010_000)
        # local ratio = 6020000 / 6500000 = 0.9261538...
        # effective local = round(1500000 * (6020000 / 6500000) * 0.5) = 694,615 -> 695,000 or similar
        expected_local_b = int(round(1_500_000 * (6_020_000 / 6_500_000) * 0.5))
        self.assertEqual(res_b["local_subsidy_krw"], expected_local_b)
        self.assertEqual(
            res_b["total_subsidy_krw"],
            res_b["national_subsidy_krw"] + res_b["local_subsidy_krw"],
        )
        self.assertEqual(
            res_b["net_price_krw"],
            73_370_000 - res_b["total_subsidy_krw"],
        )

        # Case C: Luxury Model > 85M (ratio 0.0)
        res_c = calculate_net_subsidy(
            model_national=6_500_000,
            max_national=6_500_000,
            max_local=1_500_000,
            msrp=95_000_000,
        )
        self.assertEqual(res_c["national_subsidy_krw"], 0)
        self.assertEqual(res_c["local_subsidy_krw"], 0)
        self.assertEqual(res_c["total_subsidy_krw"], 0)
        self.assertEqual(res_c["net_price_krw"], 95_000_000)


# ==============================================================================
# 6. ADVERSARIAL AND RESILIENCE TESTS
# ==============================================================================

class TestAdversarialAndResilienceContracts(unittest.TestCase):
    """Adversarial stress testing of edge cases, math guards, and zero division protections."""

    def test_zero_division_guard_depletion_rate(self) -> None:
        """calculate_depletion_rate must return 0.0 without crash when announced units is 0 or negative."""
        self.assertEqual(calculate_depletion_rate(applied=0, announced=0), 0.0)
        self.assertEqual(calculate_depletion_rate(applied=50, announced=0), 0.0)
        self.assertEqual(calculate_depletion_rate(applied=50, announced=-10), 0.0)

    def test_over_subscription_depletion_rate(self) -> None:
        """Depletion rate calculation must support over-subscription (> 100%) cleanly."""
        rate = calculate_depletion_rate(applied=250, announced=100)
        self.assertEqual(rate, 250.0)

    def test_remaining_units_clamping_on_oversubscription(self) -> None:
        """calculate_remaining_units must clamp at 0 when applied units exceed announced."""
        self.assertEqual(calculate_remaining_units(applied=150, announced=100), 0)
        self.assertEqual(calculate_remaining_units(applied=9999, announced=50), 0)
        self.assertEqual(calculate_remaining_units(applied=100, announced=100), 0)
        self.assertEqual(calculate_remaining_units(applied=40, announced=100), 60)
        self.assertEqual(calculate_remaining_units(applied=0, announced=100), 100)

    def test_alert_severity_classification_boundaries(self) -> None:
        """classify_alert_tier must classify edge boundaries accurately across all 5 tiers."""
        boundary_cases = [
            (0.0, "HEALTHY"),
            (30.5, "HEALTHY"),
            (59.9, "HEALTHY"),
            (60.0, "CAUTION"),
            (75.0, "CAUTION"),
            (79.9, "CAUTION"),
            (80.0, "WARNING"),
            (90.0, "WARNING"),
            (94.9, "WARNING"),
            (95.0, "CRITICAL"),
            (99.0, "CRITICAL"),
            (99.9, "CRITICAL"),
            (100.0, "DEPLETED"),
            (125.0, "DEPLETED"),
            (500.0, "DEPLETED"),
        ]
        for rate, expected_tier in boundary_cases:
            with self.subTest(rate=rate, expected_tier=expected_tier):
                actual_tier = classify_alert_tier(rate)
                self.assertEqual(actual_tier, expected_tier)

    def test_net_subsidy_zero_national_cap_guard(self) -> None:
        """calculate_net_subsidy must handle max_national=0 gracefully without ZeroDivisionError."""
        res = calculate_net_subsidy(
            model_national=0,
            max_national=0,
            max_local=1_500_000,
            msrp=50_000_000,
        )
        self.assertEqual(res["national_subsidy_krw"], 0)
        self.assertEqual(res["local_subsidy_krw"], 0)
        self.assertEqual(res["total_subsidy_krw"], 0)
        self.assertEqual(res["net_price_krw"], 50_000_000)

    def test_net_subsidy_negative_msrp_clamped_at_zero(self) -> None:
        """calculate_net_subsidy must clamp net purchase price at 0 for negative or zero MSRP."""
        res_neg = calculate_net_subsidy(
            model_national=6_500_000,
            max_national=6_500_000,
            max_local=1_500_000,
            msrp=-5_000_000,
        )
        self.assertEqual(res_neg["net_price_krw"], 0)

        res_zero = calculate_net_subsidy(
            model_national=6_500_000,
            max_national=6_500_000,
            max_local=1_500_000,
            msrp=0,
        )
        self.assertEqual(res_zero["net_price_krw"], 0)

    def test_mathematical_monotonicity_remaining_units_decay(self) -> None:
        """As applied units increase, calculate_remaining_units must be strictly monotonically non-increasing and clamped at 0."""
        announced = 1_000
        prev_remaining = announced
        for applied in range(0, 2_001, 25):
            remaining = calculate_remaining_units(applied=applied, announced=announced)
            self.assertGreaterEqual(
                remaining,
                0,
                f"Negative remaining units ({remaining}) for applied={applied}, announced={announced}",
            )
            self.assertLessEqual(
                remaining,
                prev_remaining,
                f"Remaining units increased from {prev_remaining} to {remaining} as applied increased to {applied}",
            )
            if applied >= announced:
                self.assertEqual(
                    remaining,
                    0,
                    f"Remaining units must be clamped at 0 when applied ({applied}) >= announced ({announced})",
                )
            prev_remaining = remaining

    def test_mathematical_monotonicity_depletion_rate_growth(self) -> None:
        """As applied units increase for a fixed announced pool, calculate_depletion_rate must be monotonically non-decreasing."""
        announced = 1_000
        prev_rate = 0.0
        for applied in range(0, 2_001, 25):
            rate = calculate_depletion_rate(applied=applied, announced=announced)
            self.assertGreaterEqual(rate, 0.0)
            self.assertGreaterEqual(
                rate,
                prev_rate,
                f"Depletion rate decreased from {prev_rate} to {rate} as applied increased to {applied}",
            )
            prev_rate = rate

    def test_mathematical_monotonicity_price_cap_ratios(self) -> None:
        """As vehicle MSRP increases from 10M to 120M KRW, calculate_price_cap_ratio must be monotonically non-increasing."""
        prev_ratio = 1.0
        for msrp in range(10_000_000, 120_000_001, 1_000_000):
            ratio = calculate_price_cap_ratio(msrp)
            self.assertIn(ratio, (1.0, 0.5, 0.0), f"Invalid price cap ratio: {ratio}")
            self.assertLessEqual(
                ratio,
                prev_ratio,
                f"Price cap ratio increased from {prev_ratio} to {ratio} at MSRP {msrp:,} KRW",
            )
            prev_ratio = ratio

    def test_remaining_units_clamping_extreme_values(self) -> None:
        """calculate_remaining_units must clamp at 0 under extreme oversubscription and non-positive inputs."""
        self.assertEqual(calculate_remaining_units(applied=1_000_000_000, announced=100), 0)
        self.assertEqual(calculate_remaining_units(applied=100, announced=100), 0)
        self.assertEqual(calculate_remaining_units(applied=50, announced=-10), 0)
        self.assertEqual(calculate_remaining_units(applied=0, announced=0), 0)

    def test_category_budget_non_negative_clamping(self) -> None:
        """In data/ev_subsidy_data.json, category remaining and disbursed budgets must be >= 0."""
        with open(ROOT_SUBSIDY_DATA, "r", encoding="utf-8") as f:
            data = json.load(f)

        for r in data["regions"]:
            for cat_name, cat in r["categories"].items():
                with self.subTest(region=r["region_id"], category=cat_name):
                    self.assertGreaterEqual(cat["remaining_budget_krw"], 0)
                    disbursed = cat["total_budget_krw"] - cat["remaining_budget_krw"]
                    self.assertGreaterEqual(disbursed, 0)


# ==============================================================================
# 7. CLI FLAGS AND RUNNER CONTRACT TESTS
# ==============================================================================

class TestCliFlagsAndRunnerContracts(unittest.TestCase):
    """Verifies CLI flag behaviors (--sync-web, --verbose, --validate-cache, and --force rejection)."""

    def setUp(self) -> None:
        self.assertTrue(
            RUN_TRACKER_SCRIPT.exists(),
            f"run_tracker.py missing at {RUN_TRACKER_SCRIPT}",
        )

    def test_cli_help_flag_returns_code_zero(self) -> None:
        """python3 run_tracker.py --help must exit with code 0 and display standard options."""
        result = subprocess.run(
            [sys.executable, str(RUN_TRACKER_SCRIPT), "--help"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, f"--help failed: {result.stderr}")
        self.assertIn("--output", result.stdout)
        self.assertIn("--sync-web", result.stdout)
        self.assertIn("--verbose", result.stdout)
        self.assertIn("--dry-run", result.stdout)
        self.assertIn("--validate-cache", result.stdout)
        self.assertIn("--no-validate-cache", result.stdout)

    def test_cli_dry_run_flag_returns_code_zero_and_briefing(self) -> None:
        """python3 run_tracker.py --dry-run must exit with code 0 and emit executive briefing."""
        result = subprocess.run(
            [sys.executable, str(RUN_TRACKER_SCRIPT), "--dry-run"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, f"--dry-run failed: {result.stderr}")
        self.assertIn("[대한민국 2026 전국 지자체 전기차 보조금 실시간 소진율 모니터링]", result.stdout)
        self.assertIn("전국 평균 소진율", result.stdout)

    def test_cli_verbose_flag_enables_debug_logging(self) -> None:
        """python3 run_tracker.py --dry-run --verbose must exit with code 0 and emit configuration logs."""
        result = subprocess.run(
            [sys.executable, str(RUN_TRACKER_SCRIPT), "--dry-run", "--verbose"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, f"--dry-run --verbose failed: {result.stderr}")
        combined = result.stdout + result.stderr
        self.assertIn("Configuration: dry_run=True", combined)
        self.assertIn("Initializing Autonomous EV Subsidy Tracker", combined)

    def test_cli_sync_web_flag_acceptance(self) -> None:
        """python3 run_tracker.py --dry-run --sync-web must accept flag and report sync_web=True."""
        result = subprocess.run(
            [sys.executable, str(RUN_TRACKER_SCRIPT), "--dry-run", "--sync-web"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, f"--sync-web failed: {result.stderr}")
        combined = result.stdout + result.stderr
        self.assertIn("sync_web=True", combined)

    def test_cli_validate_cache_flags(self) -> None:
        """Both --validate-cache and --no-validate-cache flags must be accepted with exit code 0."""
        for flag in ("--validate-cache", "--no-validate-cache"):
            with self.subTest(flag=flag):
                result = subprocess.run(
                    [sys.executable, str(RUN_TRACKER_SCRIPT), "--dry-run", flag],
                    cwd=str(PROJECT_ROOT),
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                self.assertEqual(result.returncode, 0, f"Flag {flag} failed: {result.stderr}")

    def test_cli_invalid_flag_force_exits_with_code_2(self) -> None:
        """python3 run_tracker.py --force is an unrecognized flag and must exit with code 2."""
        result = subprocess.run(
            [sys.executable, str(RUN_TRACKER_SCRIPT), "--force"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(
            result.returncode,
            2,
            f"Expected exit code 2 for unsupported --force flag, got {result.returncode}",
        )
        self.assertIn("unrecognized arguments: --force", result.stderr)

    def test_cli_arbitrary_unrecognized_flag_exits_with_code_2(self) -> None:
        """Any unrecognized CLI flag must trigger argparse error exit code 2."""
        result = subprocess.run(
            [sys.executable, str(RUN_TRACKER_SCRIPT), "--invalid-contract-flag-xyz"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("unrecognized arguments", result.stderr)

    def test_programmatic_argument_parser_defaults(self) -> None:
        """Programmatic parse_arguments must reflect authoritative default parameters."""
        with mock.patch.object(sys, "argv", ["run_tracker.py"]):
            args = run_tracker.parse_arguments()
            self.assertFalse(args.sync_web)
            self.assertFalse(args.verbose)
            self.assertFalse(args.dry_run)
            self.assertTrue(args.validate_cache)
            self.assertTrue(args.quarantine_corrupted)
            self.assertEqual(args.output, run_tracker.DEFAULT_PRIMARY_OUTPUT)

    def test_programmatic_argument_parser_custom_flags(self) -> None:
        """Programmatic parse_arguments must parse flag overrides accurately."""
        custom_argv = [
            "run_tracker.py",
            "--sync-web",
            "-v",
            "--no-validate-cache",
            "--no-quarantine-corrupted",
            "--dry-run",
            "--mock-network",
        ]
        with mock.patch.object(sys, "argv", custom_argv):
            args = run_tracker.parse_arguments()
            self.assertTrue(args.sync_web)
            self.assertTrue(args.verbose)
            self.assertFalse(args.validate_cache)
            self.assertFalse(args.quarantine_corrupted)
            self.assertTrue(args.dry_run)
            self.assertTrue(args.mock_network)

    def test_programmatic_argument_parser_force_flag_raises_system_exit_code_2(self) -> None:
        """Calling parse_arguments with --force must raise SystemExit(2)."""
        with mock.patch("sys.stderr", new_callable=io.StringIO):
            with mock.patch.object(sys, "argv", ["run_tracker.py", "--force"]):
                with self.assertRaises(SystemExit) as cm:
                    run_tracker.parse_arguments()
                self.assertEqual(cm.exception.code, 2)

    def test_cli_sync_web_destination_resolution(self) -> None:
        """Verify destination lists accurately include web mirrors when sync_web is activated."""
        primary, web, mirror_p, mirror_w, _ = run_tracker._resolve_default_paths()
        self.assertEqual(primary.name, "ev_subsidy_data.json")
        self.assertEqual(web.name, "ev_subsidy_data.json")
        self.assertEqual(mirror_p.name, "subsidy_depletion_data.json")
        self.assertEqual(mirror_w.name, "subsidy_depletion_data.json")

    def test_cli_isolated_execution_with_custom_output_and_sync(self) -> None:
        """Executing tracker in an isolated temporary tree produces valid JSON with 17 regions."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_out = Path(tmp_dir) / "output" / "ev_subsidy_data.json"
            tmp_out.parent.mkdir(parents=True, exist_ok=True)

            result = subprocess.run(
                [
                    sys.executable,
                    str(RUN_TRACKER_SCRIPT),
                    "--output",
                    str(tmp_out),
                    "--mock-network",
                    "--verbose",
                ],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(result.returncode, 0, f"Custom output run failed: {result.stderr}")
            self.assertTrue(tmp_out.exists(), f"Output file was not created: {tmp_out}")

            with open(tmp_out, "r", encoding="utf-8") as f:
                payload = json.load(f)

            self.assertEqual(payload["metadata"]["total_regions_tracked"], 17)
            self.assertEqual(len(payload["regions"]), 17)
            self.assertEqual(payload["metadata"]["total_municipalities_tracked"], 73)


if __name__ == "__main__":
    unittest.main()

