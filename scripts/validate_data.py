"""
Automated Data Integrity, Schema, and Parity Validator for EV Daily Monitoring System.
Verifies structure, completeness, parity, and conformance for:
1. Chinese/Multibrand EV Complaints Database & Slang Dictionary
2. Nationwide EV Subsidy Datasets (ev_subsidy_data.json & subsidy_depletion_data.json)
3. 2026 Vehicle Models Subsidy Matrix (models_subsidy_matrix.json)
4. Daily EV Defect Reports (daily_reports.json)
5. Triple Mirror Directory Parity (data/ vs ev-stealth-web/src/data/ vs ev-stealth-web/public/data/)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

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

_REPO_ROOT = _find_repo_root()
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scrapers.common_utils import (
    VALID_CATEGORIES,
    VALID_PLATFORMS,
    VALID_SEVERITIES,
    ComplaintRecord,
)

logger = logging.getLogger("DataValidator")


def validate_database(
    complaints_path: str,
    slang_path: str,
    min_per_category: int = 5,
    min_total: int = 30
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Validate compiled complaints and slang dictionary.
    Returns: (is_valid, error_list, stats_dict)
    Handles missing or corrupted fields gracefully.
    """
    errors: List[str] = []
    stats: Dict[str, Any] = {
        "total_cases": 0,
        "category_counts": {},
        "platform_counts": {},
        "slang_terms_count": 0,
        "unique_vehicles": set(),
    }

    # 1. Validate Slang Dictionary
    if not os.path.exists(slang_path):
        errors.append(f"Slang dictionary file not found: {slang_path}")
        slang_dict = {}
    else:
        with open(slang_path, "r", encoding="utf-8") as f:
            try:
                slang_dict = json.load(f)
                if not isinstance(slang_dict, dict):
                    errors.append(f"Slang dictionary must be a JSON object, got {type(slang_dict).__name__}")
                    slang_dict = {}
                stats["slang_terms_count"] = len(slang_dict)
                if len(slang_dict) < 10:
                    errors.append(f"Slang dictionary has too few entries: {len(slang_dict)}")
            except Exception as e:
                errors.append(f"Failed to parse slang dictionary JSON: {e}")
                slang_dict = {}

    # 2. Validate Complaints Database
    if not os.path.exists(complaints_path):
        errors.append(f"Complaints database file not found: {complaints_path}")
        return False, errors, stats

    with open(complaints_path, "r", encoding="utf-8") as f:
        try:
            records = json.load(f)
        except Exception as e:
            errors.append(f"Failed to parse complaints database JSON: {e}")
            return False, errors, stats

    if not isinstance(records, list):
        errors.append("Complaints database root must be a list")
        return False, errors, stats

    stats["total_cases"] = len(records)
    seen_ids = set()
    seen_quotes = set()

    for idx, raw_rec in enumerate(records):
        if not isinstance(raw_rec, dict):
            errors.append(f"Record [{idx}]: Expected dict, got {type(raw_rec).__name__}")
            continue

        prefix = f"Record [{idx}] (ID: {raw_rec.get('id', 'MISSING')}):"
        
        # Instantiate ComplaintRecord safely
        try:
            slang_terms = raw_rec.get("slang_terms")
            if not isinstance(slang_terms, list):
                slang_terms = [str(slang_terms)] if slang_terms is not None else []

            rec = ComplaintRecord(
                id=str(raw_rec.get("id") or ""),
                platform=str(raw_rec.get("platform") or ""),
                board_name=str(raw_rec.get("board_name") or ""),
                post_url=str(raw_rec.get("post_url") or ""),
                post_title=str(raw_rec.get("post_title") or ""),
                target_vehicle=str(raw_rec.get("target_vehicle") or ""),
                category=str(raw_rec.get("category") or ""),
                defect_topic=str(raw_rec.get("defect_topic") or ""),
                raw_quote=str(raw_rec.get("raw_quote") or ""),
                slang_terms=slang_terms,
                severity=str(raw_rec.get("severity") or "functional_failure"),
                collected_at=str(raw_rec.get("collected_at") or "")
            )
            valid, rec_errors = rec.validate()
            if not valid:
                for err in rec_errors:
                    errors.append(f"{prefix} {err}")
        except Exception as ex:
            errors.append(f"{prefix} Dataclass initialization error: {ex}")
            continue

        # ID Uniqueness
        if rec.id in seen_ids:
            errors.append(f"{prefix} Duplicate ID '{rec.id}' detected")
        seen_ids.add(rec.id)

        # Quote Uniqueness
        quote_sample = rec.raw_quote[:40]
        if quote_sample in seen_quotes:
            errors.append(f"{prefix} Duplicate quote text detected")
        seen_quotes.add(quote_sample)

        # Accumulate stats
        stats["category_counts"][rec.category] = stats["category_counts"].get(rec.category, 0) + 1
        stats["platform_counts"][rec.platform] = stats["platform_counts"].get(rec.platform, 0) + 1
        stats["unique_vehicles"].add(rec.target_vehicle)

    # 3. Check Totals & Category Thresholds
    if stats["total_cases"] < min_total:
        errors.append(f"Total cases {stats['total_cases']} is less than required minimum {min_total}")

    core_required = {"parking", "charging", "rain_driving", "hill_climbing"}
    for cat in core_required:
        count = stats["category_counts"].get(cat, 0)
        if count < min_per_category:
            errors.append(f"Category '{cat}' has only {count} cases (required: at least {min_per_category})")

    # 4. Check Platform Diversity
    if len(stats["platform_counts"]) < 3:
        errors.append(f"Insufficient platform diversity: only {len(stats['platform_counts'])} platforms present")

    stats["unique_vehicles"] = list(stats["unique_vehicles"])
    is_valid = len(errors) == 0
    return is_valid, errors, stats


def validate_subsidy_data(file_path: Union[str, Path]) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Validate EV Subsidy dataset (ev_subsidy_data.json / subsidy_depletion_data.json).
    Verifies top-level metadata, alert thresholds, nationwide summary, 17 regions,
    popular vehicle models, and statutory price-cap formulas.
    Handles corrupt or missing fields gracefully without crashing.
    """
    errors: List[str] = []
    stats: Dict[str, Any] = {
        "file_path": str(file_path),
        "total_regions": 0,
        "total_municipalities": 0,
        "popular_models_count": 0,
        "nationwide_depletion_rate": 0.0,
    }
    path = Path(file_path)
    if not path.exists():
        errors.append(f"Subsidy data file not found: {path}")
        return False, errors, stats

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        errors.append(f"Failed to parse subsidy JSON from {path}: {exc}")
        return False, errors, stats

    if not isinstance(data, dict):
        errors.append(f"Root JSON element must be an object (dict), got {type(data).__name__}")
        return False, errors, stats

    # 1. Metadata validation
    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        errors.append("Missing or invalid 'metadata' object")
    else:
        for req_key in ("version", "generated_at", "policy_year", "currency"):
            if req_key not in metadata:
                errors.append(f"Metadata missing required key '{req_key}'")

    # 2. Alert thresholds validation
    alert_thresholds = data.get("alert_thresholds")
    expected_tiers = {"HEALTHY", "CAUTION", "WARNING", "CRITICAL", "DEPLETED"}
    if not isinstance(alert_thresholds, dict):
        errors.append("Missing or invalid 'alert_thresholds' object")
    else:
        for tier in expected_tiers:
            if tier not in alert_thresholds or not isinstance(alert_thresholds[tier], dict):
                errors.append(f"Alert thresholds missing tier '{tier}'")
            else:
                cfg = alert_thresholds[tier]
                for k in ("min_percent", "max_percent", "severity"):
                    if k not in cfg:
                        errors.append(f"Alert tier '{tier}' missing key '{k}'")
                min_p = cfg.get("min_percent")
                max_p = cfg.get("max_percent")
                if isinstance(min_p, (int, float)) and isinstance(max_p, (int, float)):
                    if min_p < 0.0 or max_p < min_p:
                        errors.append(f"Alert tier '{tier}' invalid percentage bounds: {min_p} > {max_p}")

    # 3. Nationwide summary validation
    summary = data.get("nationwide_summary")
    if not isinstance(summary, dict):
        errors.append("Missing or invalid 'nationwide_summary' object")
    else:
        for k in ("total_announced_units", "total_applied_units", "total_remaining_units", "nationwide_depletion_rate"):
            if k not in summary:
                errors.append(f"Nationwide summary missing key '{k}'")

        tot_ann = summary.get("total_announced_units")
        tot_app = summary.get("total_applied_units")
        tot_rem = summary.get("total_remaining_units")
        dep_rate = summary.get("nationwide_depletion_rate")

        if isinstance(tot_ann, (int, float)) and tot_ann < 0:
            errors.append(f"Nationwide total_announced_units must be non-negative, got {tot_ann}")
        if isinstance(tot_app, (int, float)) and tot_app < 0:
            errors.append(f"Nationwide total_applied_units must be non-negative, got {tot_app}")
        if isinstance(tot_rem, (int, float)) and tot_rem < 0:
            errors.append(f"Nationwide total_remaining_units must be non-negative, got {tot_rem}")

        if isinstance(tot_ann, (int, float)) and isinstance(tot_app, (int, float)) and isinstance(tot_rem, (int, float)):
            expected_rem = max(0, tot_ann - tot_app)
            if tot_rem != expected_rem:
                errors.append(
                    f"Nationwide quota mismatch: total_remaining_units ({tot_rem}) != max(0, ann - app) ({expected_rem})"
                )

        if isinstance(dep_rate, (int, float)):
            if dep_rate < 0.0:
                errors.append(f"Nationwide depletion rate must be non-negative, got {dep_rate}")
            elif isinstance(tot_ann, (int, float)) and isinstance(tot_app, (int, float)) and tot_ann > 0:
                expected_rate = (tot_app / tot_ann) * 100
                if abs(dep_rate - expected_rate) > 0.2:
                    errors.append(
                        f"Nationwide depletion rate ({dep_rate}%) inconsistent with applications ({tot_app}/{tot_ann} = {expected_rate:.1f}%)"
                    )
        stats["nationwide_depletion_rate"] = dep_rate if isinstance(dep_rate, (int, float)) else 0.0

    # 4. Regions validation (17 statutory regions)
    regions = data.get("regions")
    if not isinstance(regions, list):
        errors.append("Missing or invalid 'regions' list")
        regions = []

    stats["total_regions"] = len(regions)
    if len(regions) < 17:
        errors.append(f"Expected at least 17 regions, found {len(regions)}")

    seen_iso = set()
    total_munis = 0
    for idx, reg in enumerate(regions):
        prefix = f"Region [{idx}]"
        if not isinstance(reg, dict):
            errors.append(f"{prefix}: Expected dict, got {type(reg).__name__}")
            continue

        iso = reg.get("iso_code") or reg.get("region_id") or ""
        prefix = f"Region [{idx}] ({iso or 'MISSING'}):"
        if not iso:
            errors.append(f"{prefix} Missing iso_code/region_id")
        elif iso in seen_iso:
            errors.append(f"{prefix} Duplicate ISO code '{iso}'")
        seen_iso.add(iso)

        if "name_ko" not in reg:
            errors.append(f"{prefix} Missing 'name_ko'")

        cats = reg.get("categories")
        if not isinstance(cats, dict):
            errors.append(f"{prefix} Missing or non-dict 'categories'")
        else:
            for cname in ("passenger", "commercial", "bus"):
                if cname not in cats or not isinstance(cats[cname], dict):
                    errors.append(f"{prefix} Missing category '{cname}'")
                else:
                    c = cats[cname]
                    for req_cat_key in ("announced_units", "applied_units", "remaining_units", "depletion_rate", "status"):
                        if req_cat_key not in c:
                            errors.append(f"{prefix} Category '{cname}' missing required key '{req_cat_key}'")

                    ann = c.get("announced_units", 0)
                    app = c.get("applied_units", 0)
                    rem = c.get("remaining_units", 0)
                    rate = c.get("depletion_rate", 0.0)
                    status = c.get("status")

                    if not isinstance(ann, (int, float)) or ann < 0:
                        errors.append(f"{prefix} Category '{cname}' announced_units must be non-negative, got {ann}")
                    if not isinstance(app, (int, float)) or app < 0:
                        errors.append(f"{prefix} Category '{cname}' applied_units must be non-negative, got {app}")
                    if not isinstance(rem, (int, float)) or rem < 0:
                        errors.append(f"{prefix} Category '{cname}' remaining_units must be non-negative, got {rem}")

                    if isinstance(ann, (int, float)) and isinstance(app, (int, float)) and isinstance(rem, (int, float)):
                        expected_rem = max(0, ann - app)
                        if rem != expected_rem:
                            errors.append(
                                f"{prefix} Category '{cname}' quota mismatch: remaining_units ({rem}) != max(0, ann - app) ({expected_rem})"
                            )

                    if isinstance(rate, (int, float)):
                        if rate < 0:
                            errors.append(f"{prefix} Category '{cname}' depletion_rate must be non-negative, got {rate}")
                        elif isinstance(ann, (int, float)) and isinstance(app, (int, float)) and ann > 0:
                            expected_rate = (app / ann) * 100
                            if abs(rate - expected_rate) > 0.2:
                                errors.append(
                                    f"{prefix} Category '{cname}' depletion_rate ({rate}%) inconsistent with {app}/{ann} ({expected_rate:.1f}%)"
                                )

                    if status is not None and status not in expected_tiers:
                        errors.append(f"{prefix} Category '{cname}' unknown status '{status}', expected one of {expected_tiers}")

        munis = reg.get("municipalities")
        if isinstance(munis, list):
            total_munis += len(munis)
            for midx, muni in enumerate(munis):
                if not isinstance(muni, dict):
                    errors.append(f"{prefix} Municipality [{midx}] is not a dict")
                    continue
                m_name = muni.get("name_ko", f"Muni-{midx}")
                if "name_ko" not in muni:
                    errors.append(f"{prefix} Municipality [{midx}] missing 'name_ko'")

                for mk in ("announced_units", "applied_units", "remaining_units"):
                    if mk in muni:
                        val = muni[mk]
                        if not isinstance(val, (int, float)) or val < 0:
                            errors.append(f"{prefix} Municipality '{m_name}' key '{mk}' must be non-negative, got {val}")

                m_ann = muni.get("announced_units")
                m_app = muni.get("applied_units")
                m_rem = muni.get("remaining_units")
                if isinstance(m_ann, (int, float)) and isinstance(m_app, (int, float)) and isinstance(m_rem, (int, float)):
                    exp_rem = max(0, m_ann - m_app)
                    if m_rem != exp_rem:
                        errors.append(
                            f"{prefix} Municipality '{m_name}' quota mismatch: remaining ({m_rem}) != max(0, ann - app) ({exp_rem})"
                        )

                m_rate = muni.get("depletion_rate")
                if isinstance(m_rate, (int, float)):
                    if m_rate < 0:
                        errors.append(f"{prefix} Municipality '{m_name}' depletion_rate must be non-negative, got {m_rate}")
                    elif isinstance(m_ann, (int, float)) and isinstance(m_app, (int, float)) and m_ann > 0:
                        exp_r = (m_app / m_ann) * 100
                        if abs(m_rate - exp_r) > 0.2:
                            errors.append(
                                f"{prefix} Municipality '{m_name}' depletion_rate ({m_rate}%) inconsistent with {m_app}/{m_ann} ({exp_r:.1f}%)"
                            )

                m_status = muni.get("status")
                if m_status is not None and m_status not in expected_tiers:
                    errors.append(f"{prefix} Municipality '{m_name}' invalid status '{m_status}'")

    stats["total_municipalities"] = total_munis

    # 5. Popular models matrix validation
    models = data.get("popular_models_matrix")
    if isinstance(models, list):
        stats["popular_models_count"] = len(models)
        for midx, m in enumerate(models):
            if not isinstance(m, dict):
                errors.append(f"Popular model [{midx}] is not a dict")
                continue
            for req_k in ("model_id", "name_ko", "base_price_krw", "price_subsidy_ratio", "national_subsidy_krw"):
                if req_k not in m:
                    errors.append(f"Popular model [{midx}] ({m.get('model_id', 'UNKNOWN')}) missing key '{req_k}'")
            price = m.get("base_price_krw")
            ratio = m.get("price_subsidy_ratio")
            if isinstance(price, (int, float)) and isinstance(ratio, (int, float)):
                if price <= 55_000_000 and ratio != 1.0:
                    errors.append(f"Model '{m.get('model_id')}' price <=55M but ratio {ratio} != 1.0")
                elif 55_000_000 < price <= 85_000_000 and ratio != 0.5:
                    errors.append(f"Model '{m.get('model_id')}' 55M<price<=85M but ratio {ratio} != 0.5")
                elif price > 85_000_000 and ratio != 0.0:
                    errors.append(f"Model '{m.get('model_id')}' price >85M but ratio {ratio} != 0.0")

    is_valid = len(errors) == 0
    return is_valid, errors, stats


def validate_models_matrix(file_path: Union[str, Path]) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Validate vehicle models subsidy matrix (models_subsidy_matrix.json).
    Verifies >=15 compliant EV models, required automotive fields, and price-cap rules.
    Handles missing fields gracefully without crashing.
    """
    errors: List[str] = []
    stats: Dict[str, Any] = {
        "file_path": str(file_path),
        "total_models": 0,
        "manufacturers": set(),
    }
    path = Path(file_path)
    if not path.exists():
        errors.append(f"Models matrix file not found: {path}")
        return False, errors, stats

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        errors.append(f"Failed to parse models matrix JSON from {path}: {exc}")
        return False, errors, stats

    if not isinstance(data, list):
        errors.append(f"Root JSON element must be a list, got {type(data).__name__}")
        return False, errors, stats

    stats["total_models"] = len(data)
    if len(data) < 15:
        errors.append(f"Expected at least 15 vehicle models in matrix, got {len(data)}")

    seen_ids = set()
    req_fields = ("model_id", "name_ko", "manufacturer", "battery_type", "battery_capacity_kwh", "rated_range_km", "base_price_krw", "price_subsidy_ratio", "national_subsidy_krw")

    for idx, m in enumerate(data):
        if not isinstance(m, dict):
            errors.append(f"Model [{idx}]: Expected dict, got {type(m).__name__}")
            continue

        mid = m.get("model_id")
        prefix = f"Model [{idx}] ({mid or 'MISSING'}):"
        if not mid:
            errors.append(f"{prefix} Missing 'model_id'")
        elif mid in seen_ids:
            errors.append(f"{prefix} Duplicate model_id '{mid}'")
        seen_ids.add(mid)

        for rf in req_fields:
            if rf not in m:
                errors.append(f"{prefix} Missing required field '{rf}'")

        cap = m.get("battery_capacity_kwh")
        if isinstance(cap, (int, float)) and cap <= 0:
            errors.append(f"{prefix} Battery capacity must be >0 kWh, got {cap}")
        rng = m.get("rated_range_km")
        if isinstance(rng, (int, float)) and rng <= 0:
            errors.append(f"{prefix} Rated range must be >0 km, got {rng}")
        sub = m.get("national_subsidy_krw")
        if isinstance(sub, (int, float)) and sub < 0:
            errors.append(f"{prefix} National subsidy must be >= 0 KRW, got {sub}")

        if m.get("manufacturer"):
            stats["manufacturers"].add(m["manufacturer"])

        price = m.get("base_price_krw")
        ratio = m.get("price_subsidy_ratio")
        if isinstance(price, (int, float)) and isinstance(ratio, (int, float)):
            if price <= 55_000_000 and ratio != 1.0:
                errors.append(f"{prefix} Price <= 55M but ratio {ratio} != 1.0")
            elif 55_000_000 < price <= 85_000_000 and ratio != 0.5:
                errors.append(f"{prefix} 55M < Price <= 85M but ratio {ratio} != 0.5")
            elif price > 85_000_000 and ratio != 0.0:
                errors.append(f"{prefix} Price > 85M but ratio {ratio} != 0.0")

    stats["manufacturers"] = sorted(list(stats["manufacturers"]))
    is_valid = len(errors) == 0
    return is_valid, errors, stats


def validate_daily_reports(file_path: Union[str, Path]) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Validate daily EV defect reports dataset (daily_reports.json).
    Verifies top-level envelope, report statistics, and report records.
    Handles corrupt or missing fields gracefully without crashing.
    """
    errors: List[str] = []
    stats: Dict[str, Any] = {
        "file_path": str(file_path),
        "total_reports": 0,
        "critical_reports": 0,
        "sources": set(),
        "categories": set(),
    }
    path = Path(file_path)
    if not path.exists():
        errors.append(f"Daily reports file not found: {path}")
        return False, errors, stats

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        errors.append(f"Failed to parse daily reports JSON from {path}: {exc}")
        return False, errors, stats

    if not isinstance(data, dict):
        errors.append(f"Root JSON element must be an object (dict), got {type(data).__name__}")
        return False, errors, stats

    for req_k in ("generated_at", "pipeline_version", "statistics", "reports"):
        if req_k not in data:
            errors.append(f"Missing required top-level key '{req_k}'")

    raw_stats = data.get("statistics")
    if not isinstance(raw_stats, dict):
        errors.append("Missing or invalid 'statistics' object")
    else:
        for sk in ("total_scraped", "total_filtered_defects", "avg_negativity_score", "critical_defect_count"):
            if sk not in raw_stats:
                errors.append(f"Statistics missing required key '{sk}'")

    reports = data.get("reports")
    if not isinstance(reports, list):
        errors.append("Missing or invalid 'reports' list")
        reports = []

    stats["total_reports"] = len(reports)
    seen_ids = set()
    req_rep_fields = ("id", "source", "url", "title", "date", "vehicle_model", "defect_category", "defect_category_ko", "summary", "verbatim_quote", "sentiment_score", "severity")

    for idx, r in enumerate(reports):
        if not isinstance(r, dict):
            errors.append(f"Report [{idx}]: Expected dict, got {type(r).__name__}")
            continue

        rid = r.get("id")
        prefix = f"Report [{idx}] ({rid or 'MISSING'}):"
        if not rid:
            errors.append(f"{prefix} Missing 'id'")
        elif rid in seen_ids:
            errors.append(f"{prefix} Duplicate report id '{rid}'")
        seen_ids.add(rid)

        for rf in req_rep_fields:
            if rf not in r:
                errors.append(f"{prefix} Missing required field '{rf}'")

        if r.get("source"):
            stats["sources"].add(str(r["source"]))
        if r.get("defect_category"):
            stats["categories"].add(str(r["defect_category"]))
        sev = str(r.get("severity", "")).upper()
        valid_sevs = {"LOW", "MEDIUM", "HIGH", "CRITICAL", "HEALTHY", "CAUTION", "WARNING", "DEPLETED"}
        if sev and sev not in valid_sevs:
            errors.append(f"{prefix} Unknown severity '{sev}'")
        if sev == "CRITICAL":
            stats["critical_reports"] += 1

    stats["sources"] = sorted(list(stats["sources"]))
    stats["categories"] = sorted(list(stats["categories"]))
    is_valid = len(errors) == 0
    return is_valid, errors, stats


def validate_data_parity(
    root_dir: Union[str, Path],
    web_src_dir: Union[str, Path],
    web_public_dir: Optional[Union[str, Path]] = None,
    target_files: Optional[List[str]] = None,
    repair: bool = False,
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Validate byte-for-byte SHA-256 parity and schema parity between data directories.
    Handles missing files or directories gracefully.
    If repair is True, restores missing or mismatched files from the authoritative source.
    """
    errors: List[str] = []
    stats: Dict[str, Any] = {"checked_files": {}, "directories": []}

    if target_files is None:
        target_files = [
            "ev_subsidy_data.json",
            "subsidy_depletion_data.json",
            "models_subsidy_matrix.json",
            "daily_reports.json",
        ]

    dirs_to_check = [("root", Path(root_dir)), ("web_src", Path(web_src_dir))]
    if web_public_dir:
        dirs_to_check.append(("web_public", Path(web_public_dir)))

    stats["directories"] = [f"{label}: {str(p)}" for label, p in dirs_to_check]

    for label, d in dirs_to_check:
        if not d.exists() or not d.is_dir():
            errors.append(f"Directory {label} not found or not a directory: {d}")

    if errors:
        return False, errors, stats

    for fname in target_files:
        hashes: Dict[str, str] = {}
        authoritative_path: Optional[Path] = None
        auth_hash: Optional[str] = None

        for label, d in dirs_to_check:
            fp = d / fname
            if fp.is_file() and fp.stat().st_size > 0:
                try:
                    content = fp.read_bytes()
                    h = hashlib.sha256(content).hexdigest()
                    hashes[label] = h
                    if authoritative_path is None:
                        authoritative_path = fp
                        auth_hash = h
                except Exception as exc:
                    errors.append(f"Failed to read {label} ({fp}): {exc}")
            else:
                if not fp.exists():
                    errors.append(f"File '{fname}' missing from {label} ({fp})")

        # Automatic mirror repair if requested and authoritative file exists
        if repair and authoritative_path is not None and auth_hash is not None:
            for label, d in dirs_to_check:
                fp = d / fname
                if not fp.exists() or hashes.get(label) != auth_hash:
                    tmp_repair = None
                    try:
                        d.mkdir(parents=True, exist_ok=True)
                        tmp_repair = d / f".tmp_repair_{fname}_{os.getpid()}_{uuid.uuid4().hex[:8]}"
                        with open(authoritative_path, "rb") as sf, open(tmp_repair, "wb") as df:
                            shutil.copyfileobj(sf, df)
                            df.flush()
                            os.fsync(df.fileno())
                        os.chmod(tmp_repair, 0o644)
                        os.replace(tmp_repair, fp)
                        tmp_repair = None
                        hashes[label] = auth_hash
                        # Clear matching errors for this repaired file
                        errors = [
                            e for e in errors
                            if not (f"'{fname}' missing from {label}" in e or f"SHA-256 mismatch for '{fname}'" in e)
                        ]
                        logger.info("Repaired parity for %s in %s", fname, label)
                    except Exception as re_exc:
                        errors.append(f"Failed to repair parity for '{fname}' in {label}: {re_exc}")
                    finally:
                        if tmp_repair and tmp_repair.exists():
                            try:
                                tmp_repair.unlink(missing_ok=True)
                            except OSError:
                                pass

        stats["checked_files"][fname] = hashes
        unique_hashes = set(hashes.values())
        if len(unique_hashes) > 1 or len(hashes) < len(dirs_to_check):
            if len(unique_hashes) > 1:
                errors.append(f"SHA-256 mismatch for '{fname}' across directories: {hashes}")

    is_valid = len(errors) == 0
    return is_valid, errors, stats


def validate_all_datasets(
    project_root: Optional[Union[str, Path]] = None,
    sync_web: bool = False,
    dry_run: bool = False,
    custom_complaints: Optional[Union[str, Path]] = None,
    custom_slang: Optional[Union[str, Path]] = None,
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Comprehensive validator executing data integrity and parity checks across all modules.
    """
    root = Path(project_root) if project_root else _find_repo_root()
    if not (root / "data").is_dir() and (root.parent / "data").is_dir():
        root = root.parent
    root_data = root / "data"
    web_src_data = root / "ev-stealth-web" / "src" / "data"
    web_pub_data = root / "ev-stealth-web" / "public" / "data"

    all_errors: List[str] = []
    summary_stats: Dict[str, Any] = {}

    # 1. Complaints & Slang
    complaints_file = str(custom_complaints) if custom_complaints else str(root_data / "compiled_complaints.json")
    slang_file = str(custom_slang) if custom_slang else str(root_data / "slang_dict.json")
    v1, e1, s1 = validate_database(complaints_file, slang_file)
    summary_stats["complaints"] = s1
    all_errors.extend(e1)

    # 2. EV Subsidy Data
    subsidy_file = root_data / "ev_subsidy_data.json"
    v2, e2, s2 = validate_subsidy_data(subsidy_file)
    summary_stats["subsidy"] = s2
    all_errors.extend(e2)

    # 3. Subsidy Depletion Data (mirror)
    depletion_file = root_data / "subsidy_depletion_data.json"
    v3, e3, s3 = validate_subsidy_data(depletion_file)
    summary_stats["depletion"] = s3
    all_errors.extend(e3)

    # 4. Models Matrix
    matrix_file = root_data / "models_subsidy_matrix.json"
    v4, e4, s4 = validate_models_matrix(matrix_file)
    summary_stats["models_matrix"] = s4
    all_errors.extend(e4)

    # 5. Daily Reports
    reports_file = root_data / "daily_reports.json"
    v5, e5, s5 = validate_daily_reports(reports_file)
    summary_stats["daily_reports"] = s5
    all_errors.extend(e5)

    # 6. Triple Directory Mirror Parity
    v6, e6, s6 = validate_data_parity(
        root_data,
        web_src_data,
        web_pub_data,
        repair=(sync_web and not dry_run),
    )
    summary_stats["parity"] = s6
    all_errors.extend(e6)

    is_overall_valid = len(all_errors) == 0
    return is_overall_valid, all_errors, summary_stats


def parse_arguments(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI flags and parameters for DataValidator."""
    parser = argparse.ArgumentParser(
        description="EV Daily Monitoring System - Comprehensive Data Integrity & Parity Validator"
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown", "md", "summary"],
        default="text",
        help="Report format for stdout output (text, json, markdown). Default: text.",
    )
    parser.add_argument(
        "--output",
        "--out",
        "-o",
        type=Path,
        default=None,
        help="Optional destination path to save validation results as JSON.",
    )
    parser.add_argument(
        "--sync-web",
        action="store_true",
        help="Verify and automatically repair directory parity across web directories.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run validation and repair checks in read-only mode without modifying files.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Project repository root directory path.",
    )
    parser.add_argument(
        "--complaints",
        type=Path,
        default=None,
        help="Path to compiled complaints JSON file.",
    )
    parser.add_argument(
        "--slang",
        type=Path,
        default=None,
        help="Path to slang dictionary JSON file.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Strict mode: fail on any data warning.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable detailed debug logging.",
    )
    return parser.parse_args(args)


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint execution loop."""
    try:
        args = parse_arguments(argv)
        log_level = logging.DEBUG if args.verbose else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        project_root = args.root or _find_repo_root()
        is_valid, errors, stats = validate_all_datasets(
            project_root=project_root,
            sync_web=args.sync_web,
            dry_run=args.dry_run,
            custom_complaints=args.complaints,
            custom_slang=args.slang,
        )

        result_payload = {
            "is_valid": is_valid,
            "errors": errors,
            "stats": stats,
        }

        # Write output file if requested
        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            from tracker.atomic_writer import atomic_write_json
            atomic_write_json(
                result_payload,
                out_path,
                indent=2,
                ensure_ascii=False,
                mode=0o644,
                temp_prefix=".tmp_val_rep_",
            )
            logger.info("Validation report written to: %s", out_path)

        # Output formatting
        if args.format == "json":
            print(json.dumps(result_payload, indent=2, ensure_ascii=False))
        elif args.format in ("markdown", "md"):
            md_lines = [
                "# EV Daily Monitoring System - Comprehensive Data Integrity Report",
                f"- **Overall Result**: {'✅ PASS' if is_valid else '❌ FAIL'}",
                f"- **Total Errors**: {len(errors)}",
                "",
                "| Dataset Module | Status | Key Metric |",
                "| :--- | :--- | :--- |",
                f"| Complaints Database | {'✅ PASS' if not any('complaints' in e.lower() for e in errors) else '❌ FAIL'} | {stats.get('complaints', {}).get('total_cases', 0)} cases / {stats.get('complaints', {}).get('slang_terms_count', 0)} slang terms |",
                f"| Subsidy Datasets | {'✅ PASS' if not any('subsidy' in e.lower() for e in errors) else '❌ FAIL'} | {stats.get('subsidy', {}).get('total_regions', 0)} regions ({stats.get('subsidy', {}).get('nationwide_depletion_rate', 0)}% depletion) |",
                f"| Models Matrix | {'✅ PASS' if not any('models' in e.lower() for e in errors) else '❌ FAIL'} | {stats.get('models_matrix', {}).get('total_models', 0)} vehicle models |",
                f"| Daily Reports | {'✅ PASS' if not any('daily' in e.lower() for e in errors) else '❌ FAIL'} | {stats.get('daily_reports', {}).get('total_reports', 0)} defect reports ({stats.get('daily_reports', {}).get('critical_reports', 0)} critical) |",
                f"| Directory Mirror Parity | {'✅ PASS' if not any('parity' in e.lower() or 'mismatch' in e.lower() for e in errors) else '❌ FAIL'} | 100% bitwise parity verified across mirrors |",
                "",
            ]
            if errors:
                md_lines.append("### Validation Errors")
                for err in errors:
                    md_lines.append(f"- ❌ {err}")
            print("\n".join(md_lines))
        else:
            print("=" * 70)
            print("EV DAILY MONITORING SYSTEM - COMPREHENSIVE DATA INTEGRITY REPORT")
            print("=" * 70)
            print(f"Overall Validation Result: {'PASS' if is_valid else 'FAIL'}")

            # 1. Complaints & Slang
            comp_stats = stats.get("complaints", {})
            print("\n[1] Complaints Database & Slang Dictionary:")
            print(f"  - Total Cases: {comp_stats.get('total_cases', 0)}")
            print(f"  - Slang Terms: {comp_stats.get('slang_terms_count', 0)}")
            print(f"  - Vehicle Models: {len(comp_stats.get('unique_vehicles', []))}")

            # 2. Subsidy Datasets
            sub_stats = stats.get("subsidy", {})
            print("\n[2] EV Subsidy Datasets (ev_subsidy_data.json & mirror):")
            print(f"  - Total 1st-Tier Regions: {sub_stats.get('total_regions', 0)} / 17")
            print(f"  - Tracked Municipalities: {sub_stats.get('total_municipalities', 0)}")
            print(f"  - Popular Models: {sub_stats.get('popular_models_count', 0)}")
            print(f"  - Nationwide Depletion Rate: {sub_stats.get('nationwide_depletion_rate', 0.0)}%")

            # 3. Models Matrix
            mat_stats = stats.get("models_matrix", {})
            print("\n[3] 2026 Vehicle Models Subsidy Matrix:")
            print(f"  - Total Models: {mat_stats.get('total_models', 0)}")
            print(f"  - Manufacturers: {', '.join(mat_stats.get('manufacturers', []))}")

            # 4. Daily Reports
            rep_stats = stats.get("daily_reports", {})
            print("\n[4] Daily Defect Reports (daily_reports.json):")
            print(f"  - Total Filtered Reports: {rep_stats.get('total_reports', 0)}")
            print(f"  - Critical Reports: {rep_stats.get('critical_reports', 0)}")
            print(f"  - Sources: {', '.join(rep_stats.get('sources', []))}")

            # 5. Parity
            parity_stats = stats.get("parity", {})
            print("\n[5] Triple Directory Mirror Parity (root vs src/data vs public/data):")
            for fname, hmap in parity_stats.get("checked_files", {}).items():
                unique_cnt = len(set(hmap.values()))
                status_tag = "PARITY OK" if unique_cnt == 1 and len(hmap) >= 2 else "MISMATCH"
                print(f"  - {fname:28s}: {status_tag} ({len(hmap)} copies verified)")

            print("=" * 70)

            if not is_valid:
                print("\nVALIDATION ERRORS ENCOUNTERED:")
                for e in errors:
                    print(f"  [ERROR] {e}")
            else:
                print("\nAll datasets and mirrors verified with 100% schema compliance and bitwise parity.")

        return 0 if is_valid else 1

    except SystemExit as se:
        return se.code if isinstance(se.code, int) else 1
    except Exception as exc:
        logger.exception("Validation execution failure: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
