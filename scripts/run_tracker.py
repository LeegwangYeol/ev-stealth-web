#!/usr/bin/env python3
"""
Alias forwarding entrypoint for run_tracker.py.
Provides backward compatibility when invoked from scripts/run_tracker.py.
"""
import runpy
import sys
from pathlib import Path

CURRENT_FILE = Path(__file__).resolve()
CURRENT_DIR = CURRENT_FILE.parent

CANDIDATES = [
    CURRENT_DIR.parent / "run_tracker.py",
    CURRENT_DIR.parent / "ev-stealth-web" / "run_tracker.py",
    CURRENT_DIR.parent.parent / "run_tracker.py",
]

TARGET_SCRIPT = None
for cand in CANDIDATES:
    if cand.is_file() and cand.resolve() != CURRENT_FILE:
        TARGET_SCRIPT = cand
        break

if __name__ == "__main__":
    if not TARGET_SCRIPT or not TARGET_SCRIPT.is_file():
        sys.stderr.write(f"[ERROR] Could not find run_tracker.py from {CURRENT_DIR}\n")
        sys.exit(2)
    if str(TARGET_SCRIPT.parent) not in sys.path:
        sys.path.insert(0, str(TARGET_SCRIPT.parent))
    try:
        runpy.run_path(str(TARGET_SCRIPT), run_name="__main__")
    except SystemExit as se:
        if se.code is None:
            sys.exit(0)
        sys.exit(se.code if isinstance(se.code, int) and not isinstance(se.code, bool) else 1)
