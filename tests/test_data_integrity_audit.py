"""
tests/test_data_integrity_audit.py - Comprehensive Unit & Regression Test Suite
for Data Integrity, Schema Consistency, Triple-Directory Parity, and Missing-Field Resilience.

Validates:
1. Triple-directory parity (data/ vs ev-stealth-web/src/data/ vs ev-stealth-web/public/data/)
   for ev_subsidy_data.json, subsidy_depletion_data.json, models_subsidy_matrix.json, and daily_reports.json.
2. Complete schema conformance and absence of corrupt or missing keys in production datasets.
3. Graceful handling of missing, corrupt, null, NaN, and wrong-type fields across all validation scripts.
4. Resilience of domain model deserialization (from_dict) against partial or degenerate payloads.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from typing import Any, Dict, List

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

# Ensure project root is in sys.path
PROJECT_ROOT = _find_repo_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.validate_data import (
    validate_all_datasets,
    validate_daily_reports,
    validate_data_parity,
    validate_database,
    validate_models_matrix,
    validate_subsidy_data,
)
from tracker.subsidy_models import (
    AlertSeverity,
    AlertThresholdConfig,
    CategoryMetrics,
    HistoricalTrajectoryPoint,
    MunicipalityMetrics,
    NationwideSummary,
    PopularModelEntry,
    RegionRecord,
    SubsidyMetadata,
    SubsidyPayload,
)
from models.complaint import (
    ComplaintRecord,
    DailyReportPayload,
    DailyReportStatistics,
)


class TestTripleDirectoryDataParity(unittest.TestCase):
    """Verifies 100% SHA-256 bitwise and structural parity across all 3 data directories."""

    def setUp(self) -> None:
        self.root_dir = PROJECT_ROOT / "data"
        self.src_dir = PROJECT_ROOT / "ev-stealth-web" / "src" / "data"
        self.public_dir = PROJECT_ROOT / "ev-stealth-web" / "public" / "data"
        self.target_files = [
            "ev_subsidy_data.json",
            "subsidy_depletion_data.json",
            "models_subsidy_matrix.json",
            "daily_reports.json",
        ]

    def test_all_target_files_exist_in_all_three_directories(self) -> None:
        """Every target JSON file must physically exist in root, src, and public data dirs."""
        for fname in self.target_files:
            for d, label in [(self.root_dir, "root"), (self.src_dir, "src"), (self.public_dir, "public")]:
                target = d / fname
                self.assertTrue(target.exists(), f"Missing file in {label}: {target}")
                self.assertTrue(target.is_file(), f"Not a file in {label}: {target}")
                self.assertGreater(target.stat().st_size, 0, f"Empty file in {label}: {target}")

    def test_bitwise_sha256_identity_across_all_three_directories(self) -> None:
        """All 3 copies of each file must possess identical SHA-256 checksums."""
        for fname in self.target_files:
            root_hash = hashlib.sha256((self.root_dir / fname).read_bytes()).hexdigest()
            src_hash = hashlib.sha256((self.src_dir / fname).read_bytes()).hexdigest()
            pub_hash = hashlib.sha256((self.public_dir / fname).read_bytes()).hexdigest()
            self.assertEqual(
                root_hash,
                src_hash,
                f"Hash mismatch between root and src/data for {fname}",
            )
            self.assertEqual(
                root_hash,
                pub_hash,
                f"Hash mismatch between root and public/data for {fname}",
            )

    def test_validate_data_parity_function_passes(self) -> None:
        """validate_data_parity helper returns is_valid=True with no errors for project data."""
        is_valid, errors, stats = validate_data_parity(
            self.root_dir, self.src_dir, self.public_dir, self.target_files
        )
        self.assertTrue(is_valid, f"Parity validation reported errors: {errors}")
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(stats["checked_files"]), len(self.target_files))


class TestProductionDatasetSchemas(unittest.TestCase):
    """Verifies schema conformance and absence of missing/corrupt keys in production data."""

    def setUp(self) -> None:
        self.root_dir = PROJECT_ROOT / "data"

    def test_subsidy_data_schema_compliance(self) -> None:
        """ev_subsidy_data.json and subsidy_depletion_data.json pass full schema validation."""
        for fname in ("ev_subsidy_data.json", "subsidy_depletion_data.json"):
            file_path = self.root_dir / fname
            is_valid, errors, stats = validate_subsidy_data(file_path)
            self.assertTrue(is_valid, f"{fname} failed schema validation: {errors}")
            self.assertEqual(stats["total_regions"], 17, f"{fname} must contain exactly 17 regions")
            self.assertGreaterEqual(stats["total_municipalities"], 70)
            self.assertGreaterEqual(stats["popular_models_count"], 10)

    def test_models_matrix_schema_compliance(self) -> None:
        """models_subsidy_matrix.json passes full schema validation with >=15 models."""
        file_path = self.root_dir / "models_subsidy_matrix.json"
        is_valid, errors, stats = validate_models_matrix(file_path)
        self.assertTrue(is_valid, f"models_subsidy_matrix.json failed validation: {errors}")
        self.assertGreaterEqual(stats["total_models"], 15)
        self.assertGreaterEqual(len(stats["manufacturers"]), 5)

    def test_daily_reports_schema_compliance(self) -> None:
        """daily_reports.json passes full schema validation with valid stats and reports."""
        file_path = self.root_dir / "daily_reports.json"
        is_valid, errors, stats = validate_daily_reports(file_path)
        self.assertTrue(is_valid, f"daily_reports.json failed validation: {errors}")
        self.assertGreater(stats["total_reports"], 0)
        self.assertGreater(stats["critical_reports"], 0)
        self.assertIn("bobaedream", stats["sources"])

    def test_validate_all_datasets_runner(self) -> None:
        """validate_all_datasets passes cleanly across the entire repository."""
        is_valid, errors, stats = validate_all_datasets(PROJECT_ROOT)
        self.assertTrue(is_valid, f"validate_all_datasets encountered errors: {errors}")
        self.assertEqual(len(errors), 0)


class TestValidationScriptsGracefulMissingFields(unittest.TestCase):
    """Fuzzing and adversarial testing: validators must handle missing fields without unhandled exceptions."""

    def test_validate_database_handles_non_dict_and_missing_fields(self) -> None:
        """validate_database handles non-dict rows, None values, and missing fields cleanly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            slang_file = tmp / "slang.json"
            slang_file.write_text(json.dumps({f"term_{i}": "meaning" for i in range(15)}), encoding="utf-8")

            # Corrupt complaints file: contains None, numbers, strings, and partial dicts
            corrupt_records = [
                None,
                42,
                "corrupted_string",
                {},
                {"id": "c1"},  # missing required fields
                {"id": "c2", "platform": "bobaedream", "category": "charging", "raw_quote": "test quote", "slang_terms": None},
            ]
            comp_file = tmp / "complaints.json"
            comp_file.write_text(json.dumps(corrupt_records), encoding="utf-8")

            # Must not raise an unhandled exception
            is_valid, errors, stats = validate_database(str(comp_file), str(slang_file), min_total=1, min_per_category=1)
            self.assertFalse(is_valid)
            self.assertGreater(len(errors), 0)
            # Ensure error list flagged non-dict records
            self.assertTrue(any("Expected dict" in e for e in errors))

    def test_validate_subsidy_data_handles_corrupt_structures(self) -> None:
        """validate_subsidy_data handles empty objects, non-dict regions, and missing categories cleanly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # Scenario A: empty dict
            f_empty = tmp / "empty.json"
            f_empty.write_text("{}", encoding="utf-8")
            is_valid, errors, _ = validate_subsidy_data(f_empty)
            self.assertFalse(is_valid)
            self.assertTrue(any("metadata" in e for e in errors))

            # Scenario B: regions with non-dict elements and missing categories
            malformed_payload = {
                "metadata": {"version": "1.0.0", "generated_at": "2026-01-01", "policy_year": 2026, "currency": "KRW"},
                "alert_thresholds": {t: {"min_percent": 0, "max_percent": 100, "severity": t} for t in ["HEALTHY", "CAUTION", "WARNING", "CRITICAL", "DEPLETED"]},
                "nationwide_summary": {"total_announced_units": 100, "total_applied_units": 50, "total_remaining_units": 50, "nationwide_depletion_rate": 50.0},
                "regions": [
                    None,
                    "invalid_region",
                    {"region_id": "KR-11", "name_ko": "서울", "categories": {}},  # missing passenger
                ],
            }
            f_malformed = tmp / "malformed.json"
            f_malformed.write_text(json.dumps(malformed_payload), encoding="utf-8")
            is_valid, errors, _ = validate_subsidy_data(f_malformed)
            self.assertFalse(is_valid)
            self.assertTrue(any("Expected dict" in e for e in errors))
            self.assertTrue(any("Missing category" in e for e in errors))

    def test_validate_models_matrix_handles_degenerate_records(self) -> None:
        """validate_models_matrix handles non-dict entries and missing specifications cleanly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            matrix_file = tmp / "matrix.json"
            matrix_file.write_text(json.dumps([None, {}, {"model_id": "m1"}]), encoding="utf-8")
            is_valid, errors, _ = validate_models_matrix(matrix_file)
            self.assertFalse(is_valid)
            self.assertTrue(any("Expected dict" in e for e in errors))
            self.assertTrue(any("Missing required field" in e for e in errors))

    def test_validate_daily_reports_handles_degenerate_reports(self) -> None:
        """validate_daily_reports handles non-dict reports and missing statistics cleanly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            rep_file = tmp / "reports.json"
            rep_file.write_text(json.dumps({
                "generated_at": "2026-01-01",
                "pipeline_version": "1.0.0",
                "statistics": {},  # missing required stat keys
                "reports": [None, {"id": "r1"}],  # missing report keys
            }), encoding="utf-8")
            is_valid, errors, _ = validate_daily_reports(rep_file)
            self.assertFalse(is_valid)
            self.assertTrue(any("Statistics missing" in e for e in errors))
            self.assertTrue(any("Expected dict" in e for e in errors))


class TestDomainModelDeserializationResilience(unittest.TestCase):
    """Verifies dataclass from_dict factories handle empty dicts, missing keys, and wrong types safely."""

    def test_category_metrics_from_dict_defaults(self) -> None:
        """CategoryMetrics.from_dict parses empty dict and None values to safe defaults."""
        c = CategoryMetrics.from_dict({})
        self.assertEqual(c.announced_units, 0)
        self.assertEqual(c.depletion_rate, 0.0)
        self.assertEqual(c.status, "HEALTHY")

        c2 = CategoryMetrics.from_dict({"announced_units": None, "depletion_rate": float("nan")})
        self.assertEqual(c2.announced_units, 0)
        self.assertEqual(c2.depletion_rate, 0.0)

    def test_municipality_metrics_from_dict_defaults(self) -> None:
        """MunicipalityMetrics.from_dict parses empty dict safely."""
        m = MunicipalityMetrics.from_dict({})
        self.assertEqual(m.name_ko, "")
        self.assertEqual(m.remaining_units, 0)
        self.assertEqual(m.status, "HEALTHY")

    def test_popular_model_entry_from_dict_defaults(self) -> None:
        """PopularModelEntry.from_dict parses empty dict and corrupt samples safely."""
        pm = PopularModelEntry.from_dict({"regional_subsidy_samples": "not_a_dict"})
        self.assertEqual(pm.model_id, "")
        self.assertEqual(pm.base_price_krw, 0)
        self.assertEqual(pm.regional_subsidy_samples, {})

    def test_subsidy_payload_from_dict_defaults(self) -> None:
        """SubsidyPayload.from_dict parses empty dict and non-iterable collections safely."""
        sp = SubsidyPayload.from_dict({
            "regions": 123,  # non-list
            "popular_models_matrix": "not_a_list",
            "historical_depletion_trajectory": None,
        })
        self.assertEqual(len(sp.regions), 0)
        self.assertEqual(len(sp.popular_models_matrix), 0)
        self.assertEqual(len(sp.historical_depletion_trajectory), 0)
        self.assertEqual(sp.metadata.version, "1.0.0")

    def test_daily_report_statistics_mapping_and_defaults(self) -> None:
        """DailyReportStatistics safely parses empty dict and handles NaN."""
        stats = DailyReportStatistics()
        d = stats.to_dict()
        self.assertEqual(d["total_scraped"], 0)
        self.assertEqual(d["avg_negativity_score"], 0.0)

        stats_nan = DailyReportStatistics(avg_negativity_score=float("nan"))
        self.assertEqual(stats_nan.to_dict()["avg_negativity_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
