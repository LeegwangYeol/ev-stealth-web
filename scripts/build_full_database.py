import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from part1_tesla_hyundai import tesla_records, hyundai_records
from part2_kia_genesis_mercedes import kia_records, genesis_records, mercedes_records
from part3_bmw_porsche_polestar_gm import bmw_records, porsche_records, polestar_records, gm_records
from part4_chinese_ev import chinese_records

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
category_counts = {}
brand_counts = {}

for brand_name, records in all_raw_groups:
    brand_counts[brand_name] = len(records)
    for r in records:
        rec_id = r[0]
        platform = r[1]
        board = r[2]
        url = r[3]
        title = r[4]
        vehicle = r[5]
        category = r[6]
        topic = r[7]
        quote = r[8]
        slangs = r[9]
        severity = r[10]
        meta = {
            "author_type": r[11],
            "author_badge": r[12],
            "post_date": r[13],
            "view_count": r[14],
            "comment_count": r[15],
            "vote_count": r[16]
        }
        collected_at = f"{r[13]}T12:00:00Z"

        record_dict = {
            "id": rec_id,
            "platform": platform,
            "board_name": board,
            "post_url": url,
            "post_title": title,
            "target_vehicle": vehicle,
            "category": category,
            "defect_topic": topic,
            "raw_quote": quote,
            "slang_terms": slangs,
            "severity": severity,
            "platform_metadata": meta,
            "collected_at": collected_at
        }
        all_records.append(record_dict)
        category_counts[category] = category_counts.get(category, 0) + 1

print("================ DATASET COMPILATION SUMMARY ================")
print(f"Total Records: {len(all_records)}")
print("\n--- Brand Distribution ---")
for b, c in brand_counts.items():
    print(f"  {b:25s}: {c:3d} records")

print("\n--- Category Distribution ---")
for cat, c in category_counts.items():
    print(f"  {cat:20s}: {c:3d} records")

output_dir = os.path.join(PROJECT_ROOT, "data")
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, "compiled_complaints.json")
from tracker.atomic_writer import atomic_write_json

atomic_write_json(
    all_records,
    output_path,
    indent=2,
    ensure_ascii=False,
    mode=0o644,
    temp_prefix=".tmp_full_db_",
)

print(f"\nSuccessfully compiled and wrote {len(all_records)} records to {output_path}")
