#!/usr/bin/env python3
"""
Alias forwarding entrypoint for run_scraper.py.
Provides backward compatibility when invoked from scripts/run_scraper.py.
"""
import runpy
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
TARGET_SCRIPT = CURRENT_DIR.parent / "run_scraper.py"

if __name__ == "__main__":
    if not TARGET_SCRIPT.is_file():
        sys.stderr.write(f"[ERROR] Could not find run_scraper.py from {CURRENT_DIR}\n")
        sys.exit(2)
    if str(CURRENT_DIR.parent) not in sys.path:
        sys.path.insert(0, str(CURRENT_DIR.parent))
    try:
        runpy.run_path(str(TARGET_SCRIPT), run_name="__main__")
    except SystemExit as se:
        sys.exit(se.code if isinstance(se.code, int) else 1)
