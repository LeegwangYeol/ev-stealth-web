#!/usr/bin/env python3
"""
Master Complaint Database Compiler for Global EV Critical Defect & Comparative Research.
Assembles, validates, and serializes the complete 264-case multi-brand complaint dataset.
"""

import json
import os
import sys

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers.common_utils import ComplaintRecord
from part1_tesla_hyundai import tesla_records, hyundai_records
from part2_kia_genesis_mercedes import kia_records, genesis_records, mercedes_records
from part3_bmw_porsche_polestar_gm import bmw_records, porsche_records, polestar_records, gm_records
from part4_chinese_ev import chinese_records

def compile_database() -> str:
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

    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "compiled_complaints.json")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    print(f"Successfully compiled {len(all_records)} complaint records to {output_file}")
    return output_file

if __name__ == "__main__":
    compile_database()
