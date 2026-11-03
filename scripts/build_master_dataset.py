#!/usr/bin/env python3
"""
Generator script to produce the complete, rich, multi-brand master database (264 records).
Executes compilation via compile_database.
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from compile_database import compile_database

def main() -> int:
    print("Building Master Dataset Generation via compile_database...")
    out_file = compile_database()
    print(f"Master dataset successfully built: {out_file}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
