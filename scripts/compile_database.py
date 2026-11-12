#!/usr/bin/env python3
"""
Master Complaint Database Compiler for Global EV Critical Defect & Comparative Research.
Assembles, validates, and serializes the complete 264-case multi-brand complaint dataset.
"""

import json
import os
import sys
from typing import Any, Dict, List, Optional, Union

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers.common_utils import ComplaintRecord
from tracker.atomic_writer import atomic_write_json
from part1_tesla_hyundai import tesla_records, hyundai_records
from part2_kia_genesis_mercedes import kia_records, genesis_records, mercedes_records
from part3_bmw_porsche_polestar_gm import bmw_records, porsche_records, polestar_records, gm_records
from part4_chinese_ev import chinese_records


class CompiledDatabaseResult(list):
    """List of compiled complaint records that also evaluates to the output file path as string."""

    def __init__(self, records: List[Dict[str, Any]], file_path: str):
        super().__init__(records)
        self.file_path = str(file_path)

    def __str__(self) -> str:
        return self.file_path

    def __repr__(self) -> str:
        return f"<CompiledDatabaseResult file_path={self.file_path!r} records={len(self)}>"

    def __fspath__(self) -> str:
        return self.file_path


def compile_database(
    output_path: Optional[str] = None,
    slang_path: Optional[str] = None,
) -> CompiledDatabaseResult:
    all_raw_groups = [
        ("Tesla", tesla_records),
        ("Hyundai", hyundai_records),
        ("Kia", kia_records),
        ("Genesis", genesis_records),
        ("Mercedes-Benz EQ", mercedes_records),
        ("BMW i Series", bmw_records),
        ("Porsche Taycan", porsche_records),
        ("Polestar", polestar_records),
        ("Chevrolet / GM", gm_records),
        ("BYD & Chinese EVs", chinese_records),
    ]

    all_records = []
    seen_ids = set()
    seen_quotes = set()

    for brand_name, records in all_raw_groups:
        for r in records:
            rec_id = r[0]
            if rec_id in seen_ids:
                raise ValueError(f"Duplicate record ID found: {rec_id}")
            seen_ids.add(rec_id)

            quote = r[8]
            quote_prefix = quote[:40].strip()
            if quote_prefix in seen_quotes:
                raise ValueError(f"Duplicate quote prefix found in {rec_id}: {quote_prefix}")
            seen_quotes.add(quote_prefix)

            meta = {
                "author_type": r[11],
                "author_badge": r[12],
                "post_date": r[13],
                "view_count": r[14],
                "comment_count": r[15],
                "vote_count": r[16]
            }

            record = ComplaintRecord(
                id=rec_id,
                platform=r[1],
                board_name=r[2],
                post_url=r[3],
                post_title=r[4],
                target_vehicle=r[5],
                category=r[6],
                defect_topic=r[7],
                raw_quote=quote,
                slang_terms=r[9],
                severity=r[10],
                platform_metadata=meta,
                collected_at=f"{r[13]}T12:00:00Z"
            )
            all_records.append(record.to_dict())

    if output_path:
        output_file = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
    else:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, "compiled_complaints.json")

    atomic_write_json(
        all_records,
        output_file,
        indent=2,
        ensure_ascii=False,
        mode=0o644,
        temp_prefix=".tmp_compile_",
    )

    print(f"Successfully compiled {len(all_records)} complaint records to {output_file}")
    return CompiledDatabaseResult(all_records, output_file)

if __name__ == "__main__":
    compile_database()
