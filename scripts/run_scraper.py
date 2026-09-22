#!/usr/bin/env python3
"""
Alias forwarding entrypoint for ev-stealth-web/run_scraper.py.
Provides backward compatibility when invoked from scripts/run_scraper.py.
"""
import runpy
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
TARGET_SCRIPT = CURRENT_DIR.parent / "run_scraper.py"

if __name__ == "__main__":
    if str(CURRENT_DIR.parent) not in sys.path:
        sys.path.insert(0, str(CURRENT_DIR.parent))
    runpy.run_path(str(TARGET_SCRIPT), run_name="__main__")
