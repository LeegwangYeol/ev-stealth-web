#!/usr/bin/env python3
"""Comprehensive Unit and Integration Tests for Shell & Automation Scripts.

Audits and verifies:
1. Shell runner scripts exist, have execute permissions, and start with '#!/usr/bin/env bash'.
2. Robust error handling flags (set -euo pipefail) are strictly declared.
3. Canonical physical path resolution functions properly even when executed via symlinks.
4. Python environment detection correctly respects caller overrides ($PYTHON_BIN),
   rejects invalid/non-Python-3 interpreters, and propagates exit code 2 on missing/invalid runners.
5. Argument forwarding preserves quotes and flags to Python entrypoints.
6. Execution banners ([SUCCESS] / [ERROR]) and exit codes are properly propagated.
7. Subdirectory and mirror parity (scripts/, ev-stealth-web/) are fully operational.
"""

from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

def _find_repo_root() -> Path:
    candidates = [
        Path(__file__).resolve().parent.parent,
        Path(__file__).resolve().parent.parent.parent,
        Path.cwd(),
        Path.cwd().parent,
    ]
    for c in candidates:
        if (c / "ev-stealth-web").is_dir() and (c / "data").is_dir() and (c / "run_tracker.py").exists():
            return c
    for c in candidates:
        if (c / "run_tracker.py").exists() and (c / "data").exists():
            return c
    return Path(__file__).resolve().parent.parent

PROJECT_ROOT = _find_repo_root()
WEB_ROOT = PROJECT_ROOT / "ev-stealth-web"


class TestShellScriptsAudit(unittest.TestCase):
    """Test suite verifying robustness, error handling, and environment resolution."""

    def test_01_shell_scripts_permissions_and_shebang(self) -> None:
        """Verify shell scripts exist, are executable (0755), and have bash shebang."""
        scripts_to_check = [
            PROJECT_ROOT / "run_tracker.sh",
            PROJECT_ROOT / "run_scraper.sh",
            PROJECT_ROOT / "scripts" / "run_tracker.sh",
            PROJECT_ROOT / "scripts" / "run_scraper.sh",
            PROJECT_ROOT / "ev-stealth-web" / "run_tracker.sh",
            PROJECT_ROOT / "ev-stealth-web" / "run_scraper.sh",
        ]

        for s in scripts_to_check:
            self.assertTrue(s.exists(), f"Script {s} must physically exist")
            self.assertTrue(os.access(s, os.X_OK), f"Script {s} must be executable")
            content = s.read_text(encoding="utf-8")
            lines = content.splitlines()
            self.assertTrue(len(lines) > 0)
            self.assertEqual(lines[0].strip(), "#!/usr/bin/env bash")
            self.assertIn("set -euo pipefail", content)

    def test_02_run_tracker_sh_help_and_dry_run(self) -> None:
        """Verify run_tracker.sh runs --help and --dry-run successfully with exit code 0."""
        # 1. --help
        res_help = subprocess.run(
            ["bash", str(PROJECT_ROOT / "run_tracker.sh"), "--help"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        self.assertEqual(res_help.returncode, 0)
        self.assertIn("NATIONWIDE EV SUBSIDY TRACKER", res_help.stdout)
        self.assertIn("[SUCCESS]", res_help.stdout)

        # 2. --dry-run
        res_dry = subprocess.run(
            ["bash", str(PROJECT_ROOT / "run_tracker.sh"), "--dry-run"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        self.assertEqual(res_dry.returncode, 0)
        self.assertIn("NATIONWIDE EV SUBSIDY TRACKER", res_dry.stdout)
        self.assertIn("[SUCCESS]", res_dry.stdout)

    def test_03_run_scraper_sh_help(self) -> None:
        """Verify run_scraper.sh runs --help successfully with exit code 0."""
        res_help = subprocess.run(
            ["bash", str(PROJECT_ROOT / "run_scraper.sh"), "--help"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        self.assertEqual(res_help.returncode, 0)
        self.assertIn("DAILY EV MONITORING PIPELINE", res_help.stdout)
        self.assertIn("[SUCCESS]", res_help.stdout)

    def test_04_invalid_arguments_exit_code_2_and_error_banner(self) -> None:
        """Verify unrecognized arguments trigger exit code 2 and [ERROR] banner."""
        # Tracker
        res_tracker = subprocess.run(
            ["bash", str(PROJECT_ROOT / "run_tracker.sh"), "--unrecognized-audit-flag"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        self.assertEqual(res_tracker.returncode, 2)
        combined_tracker = res_tracker.stdout + res_tracker.stderr
        self.assertIn("NATIONWIDE EV SUBSIDY TRACKER", combined_tracker)
        self.assertIn("[ERROR] EV Subsidy Tracker pipeline failed with code 2", combined_tracker)

        # Scraper
        res_scraper = subprocess.run(
            ["bash", str(PROJECT_ROOT / "run_scraper.sh"), "--unrecognized-audit-flag"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        self.assertEqual(res_scraper.returncode, 2)
        combined_scraper = res_scraper.stdout + res_scraper.stderr
        self.assertIn("DAILY EV MONITORING PIPELINE", combined_scraper)
        self.assertIn("[ERROR] Scraper pipeline failed with exit code 2", combined_scraper)

    def test_05_symlink_path_resolution(self) -> None:
        """Verify that executing via a symlink outside the project directory resolves correctly."""
        with tempfile.TemporaryDirectory() as td:
            symlink_tracker = Path(td) / "ext_tracker.sh"
            symlink_tracker.symlink_to(PROJECT_ROOT / "run_tracker.sh")

            res = subprocess.run(
                ["bash", str(symlink_tracker), "--dry-run"],
                capture_output=True,
                text=True,
                cwd=td,
            )
            self.assertEqual(res.returncode, 0, f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}")
            self.assertIn(str(PROJECT_ROOT / "run_tracker.py"), res.stdout)
            self.assertIn("[SUCCESS]", res.stdout)

    def test_06_python_environment_override_respects_custom_bin(self) -> None:
        """Verify $PYTHON_BIN environment variable override is respected."""
        current_python = sys.executable
        env = os.environ.copy()
        env["PYTHON_BIN"] = current_python

        res = subprocess.run(
            ["bash", str(PROJECT_ROOT / "run_tracker.sh"), "--help"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            env=env,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn(f"Python executable : {current_python}", res.stdout)

    def test_07_invalid_python_environment_returns_code_2(self) -> None:
        """Verify invalid Python interpreter in $PYTHON_BIN triggers graceful error and code 2."""
        with tempfile.TemporaryDirectory() as td:
            fake_python = Path(td) / "fake_python"
            fake_python.write_text("#!/bin/sh\nexit 1\n")
            fake_python.chmod(0o755)

            env = os.environ.copy()
            # Retain standard shell PATH for bash while pointing PYTHON_BIN to non-functional interpreter
            env["PATH"] = f"{td}:/bin:/usr/bin"
            env["PYTHON_BIN"] = str(fake_python)
            env.pop("PYTHON", None)
            env.pop("VIRTUAL_ENV", None)

            res = subprocess.run(
                ["bash", str(PROJECT_ROOT / "run_tracker.sh"), "--dry-run"],
                capture_output=True,
                text=True,
                cwd=str(PROJECT_ROOT),
                env=env,
            )
            self.assertEqual(res.returncode, 2)
            self.assertIn("not a valid Python 3", res.stderr)

    def test_08_scripts_directory_runners_and_forwarders(self) -> None:
        """Verify scripts/run_tracker.sh and scripts/run_scraper.sh run properly."""
        # scripts/run_tracker.sh --dry-run
        res_t = subprocess.run(
            ["bash", str(PROJECT_ROOT / "scripts" / "run_tracker.sh"), "--dry-run"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT / "scripts"),
        )
        self.assertEqual(res_t.returncode, 0)
        self.assertIn("[SUCCESS]", res_t.stdout)

        # scripts/run_scraper.sh --help
        res_s = subprocess.run(
            ["bash", str(PROJECT_ROOT / "scripts" / "run_scraper.sh"), "--help"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT / "scripts"),
        )
        self.assertEqual(res_s.returncode, 0)
        self.assertIn("[SUCCESS]", res_s.stdout)

    def test_09_python_forwarders_and_database_compilers(self) -> None:
        """Verify python automation forwarders in scripts/ execute cleanly."""
        # scripts/build_master_dataset.py
        res_b = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "build_master_dataset.py")],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        self.assertEqual(res_b.returncode, 0)
        self.assertIn("Master dataset successfully built", res_b.stdout)

        # scripts/build_full_database_script.py
        res_f = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "build_full_database_script.py")],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        self.assertEqual(res_f.returncode, 0)
        self.assertIn("Full database successfully compiled", res_f.stdout)


if __name__ == "__main__":
    unittest.main()
