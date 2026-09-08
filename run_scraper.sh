#!/usr/bin/env bash
# ==============================================================================
# Daily EV Defect Scraper & NLP Pipeline — Local Runner Script
#
# Provides local CLI execution with Python interpreter resolution,
# argument forwarding, execution banners, and standardized exit codes.
#
# Usage:
#   bash run_scraper.sh [OPTIONS]
#   ./run_scraper.sh --sources all --limit 20 --sync-web
#   ./run_scraper.sh --dry-run
#
# Exit codes:
#   0: Success / Valid reports produced or dry-run complete
#   1: Runtime or network failure with zero recovery
#   2: Invalid arguments or missing Python interpreter / dependencies
# ==============================================================================

set -euo pipefail

# 1. Resolve Python Interpreter
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "[ERROR] Neither 'python3' nor 'python' was found in PATH." >&2
    exit 2
fi

# 2. Locate Runner Script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "${SCRIPT_DIR}/run_scraper.py" ]; then
    RUNNER_PY="${SCRIPT_DIR}/run_scraper.py"
elif [ -f "${SCRIPT_DIR}/scripts/run_scraper.py" ]; then
    RUNNER_PY="${SCRIPT_DIR}/scripts/run_scraper.py"
elif [ -f "${SCRIPT_DIR}/../run_scraper.py" ]; then
    RUNNER_PY="${SCRIPT_DIR}/../run_scraper.py"
elif [ -f "${SCRIPT_DIR}/teamwork_projects/ev_daily_monitor_bot/run_scraper.py" ]; then
    RUNNER_PY="${SCRIPT_DIR}/teamwork_projects/ev_daily_monitor_bot/run_scraper.py"
elif [ -f "${SCRIPT_DIR}/../teamwork_projects/ev_daily_monitor_bot/run_scraper.py" ]; then
    RUNNER_PY="${SCRIPT_DIR}/../teamwork_projects/ev_daily_monitor_bot/run_scraper.py"
elif [ -f "${SCRIPT_DIR}/ev-stealth-web/run_scraper.py" ]; then
    RUNNER_PY="${SCRIPT_DIR}/ev-stealth-web/run_scraper.py"
else
    echo "[ERROR] Could not locate 'run_scraper.py' entrypoint." >&2
    exit 2
fi

START_TIMESTAMP="$(date -u +"%Y-%m-%d %H:%M:%S UTC")"

echo "========================================================================"
echo "  DAILY EV MONITORING PIPELINE — LOCAL SCRAPER RUNNER"
echo "  Started at        : ${START_TIMESTAMP}"
echo "  Python executable : ${PYTHON_BIN}"
echo "  Runner target     : ${RUNNER_PY}"
echo "  Arguments         : ${*:-<none>}"
echo "========================================================================"

# 3. Execute with argument forwarding and trap exit code
set +e
"${PYTHON_BIN}" "${RUNNER_PY}" "$@"
EXIT_CODE=$?
set -e

END_TIMESTAMP="$(date -u +"%Y-%m-%d %H:%M:%S UTC")"

if [ "${EXIT_CODE}" -eq 0 ]; then
    echo "========================================================================"
    echo "  [SUCCESS] Scraper pipeline completed successfully at ${END_TIMESTAMP}"
    echo "========================================================================"
else
    echo "========================================================================"
    echo "  [ERROR] Scraper pipeline failed with exit code ${EXIT_CODE} at ${END_TIMESTAMP}"
    echo "========================================================================"
fi

exit "${EXIT_CODE}"
