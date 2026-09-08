"""JSON Writer and Report Formatter for Daily EV Monitoring Pipeline.

Outputs structured JSON reports matching PROJECT.md § Interface Contracts to:
/Users/a7890/src/my-e-car/ev-stealth-web/src/data/daily_reports.json

Authoritative source:
- /Users/a7890/src/my-e-car/.agents/orchestrator_daily_monitor/PROJECT.md § Interface Contracts
- /Users/a7890/src/my-e-car/.agents/spec_miner_nlp_workflow/specifications.md § 3.3
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, Iterable, List, Optional, Union

from models.complaint import (
    ComplaintRecord,
    DailyReportPayload,
    DailyReportStatistics,
)


_CURRENT_DIR = Path(__file__).resolve().parent
_CANDIDATE_PATHS = [
    _CURRENT_DIR.parent / "ev-stealth-web" / "src" / "data" / "daily_reports.json",
    _CURRENT_DIR.parent / "src" / "data" / "daily_reports.json",
    _CURRENT_DIR.parent / "data" / "daily_reports.json",
]
DEFAULT_OUTPUT_PATH = str(
    next((p for p in _CANDIDATE_PATHS if p.parent.exists()), _CANDIDATE_PATHS[0])
)


def format_daily_report_payload(
    complaints: Iterable[Union[ComplaintRecord, Dict[str, Any]]],
    total_scraped: Optional[int] = None,
    pipeline_version: str = "1.0.0",
    generated_at: Optional[str] = None,
) -> DailyReportPayload:
    """Transform complaint records into a validated DailyReportPayload object."""
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).isoformat()

    report_dicts: List[Dict[str, Any]] = []
    negativity_scores: List[float] = []
    critical_count = 0
    category_counts: Counter[str] = Counter()

    for item in complaints:
        if isinstance(item, ComplaintRecord):
            # Only include authentic defects in daily reports
            if not item.is_authentic_defect:
                continue
            record_dict = item.to_admin_report_dict()
            neg_score = item.negativity_score
            is_critical = item.severity_tier == "CRITICAL"
            category = item.defect_category
        elif isinstance(item, dict):
            # Check is_authentic_defect if provided
            if not item.get("is_authentic_defect", True):
                continue
            record_dict = dict(item)
            # Ensure required aliases
            if "sentiment_score" not in record_dict and "negativity_score" in record_dict:
                record_dict["sentiment_score"] = record_dict["negativity_score"]
            if "slang_tags" not in record_dict and "slang_terms_detected" in record_dict:
                record_dict["slang_tags"] = record_dict["slang_terms_detected"]
            if "raw_quote" not in record_dict and "verbatim_quote" in record_dict:
                record_dict["raw_quote"] = record_dict["verbatim_quote"]

            neg_score = float(record_dict.get("negativity_score", record_dict.get("sentiment_score", 0.5)))
            is_critical = record_dict.get("severity") == "CRITICAL" or float(record_dict.get("severity_index", 0.0)) >= 8.0
            category = str(record_dict.get("defect_category", "BUILD_QUALITY"))
        else:
            continue

        report_dicts.append(record_dict)
        negativity_scores.append(neg_score)
        if is_critical:
            critical_count += 1
        category_counts[category] += 1

    total_filtered = len(report_dicts)
    computed_total_scraped = total_scraped if total_scraped is not None else total_filtered
    avg_neg = (sum(negativity_scores) / total_filtered) if total_filtered > 0 else 0.0

    # Build category breakdown
    top_categories = []
    for cat, count in category_counts.most_common():
        ratio = round(count / total_filtered, 3) if total_filtered > 0 else 0.0
        top_categories.append({
            "category": cat,
            "count": count,
            "ratio": ratio,
        })

    statistics = DailyReportStatistics(
        total_scraped=computed_total_scraped,
        total_filtered_defects=total_filtered,
        avg_negativity_score=round(avg_neg, 2),
        critical_defect_count=critical_count,
    )

    return DailyReportPayload(
        generated_at=generated_at,
        pipeline_version=pipeline_version,
        statistics=statistics,
        reports=report_dicts,
        total_complaints_today=total_filtered,
        top_defect_categories=top_categories,
    )


def write_daily_reports(
    complaints: Iterable[Union[ComplaintRecord, Dict[str, Any]]],
    output_path: str = DEFAULT_OUTPUT_PATH,
    total_scraped: Optional[int] = None,
    pipeline_version: str = "1.0.0",
    generated_at: Optional[str] = None,
) -> str:
    """Format and atomically write daily reports JSON to the destination path.

    Returns the absolute path written.
    """
    payload = format_daily_report_payload(
        complaints=complaints,
        total_scraped=total_scraped,
        pipeline_version=pipeline_version,
        generated_at=generated_at,
    )

    data = payload.to_dict()

    # Ensure parent directory exists
    dir_path = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(dir_path, exist_ok=True)

    # Perform atomic write via temporary file with crash durability (flush + fsync)
    temp_dir = dir_path
    temp_name: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8") as tf:
            temp_name = tf.name
            json.dump(data, tf, ensure_ascii=False, indent=2)
            tf.flush()
            os.fsync(tf.fileno())

        os.replace(temp_name, output_path)
        temp_name = None
    finally:
        if temp_name and os.path.exists(temp_name):
            try:
                os.unlink(temp_name)
            except OSError:
                pass

    return output_path


def read_daily_reports(path: str = DEFAULT_OUTPUT_PATH) -> Dict[str, Any]:
    """Read and parse daily reports JSON from file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
