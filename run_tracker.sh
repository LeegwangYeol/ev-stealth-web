#!/usr/bin/env bash
# ==============================================================================
# Nationwide EV Subsidy Tracker — Scheduled Tasks Local / Headless Runner
#
# Provides automated background execution with Python interpreter resolution,
# argument forwarding, execution banners, error traps, and exit code propagation.
#
# Usage:
#   bash run_tracker.sh [OPTIONS]
#   ./run_tracker.sh --sync-web --verbose
#   ./run_tracker.sh --dry-run
#
# Exit codes:
#   0: Success / Valid dataset generated and synchronized
#   1: Runtime or pipeline failure
#   2: Missing Python interpreter or invalid arguments
# ==============================================================================

set -euo pipefail

# 1. Canonical Physical Path Resolution (resolving symlinks)
SOURCE="${BASH_SOURCE[0]}"
while [ -h "${SOURCE}" ]; do
    DIR="$(cd -P "$(dirname "${SOURCE}")" >/dev/null 2>&1 && pwd)"
    SOURCE="$(readlink "${SOURCE}")"
    [[ ${SOURCE} != /* ]] && SOURCE="${DIR}/${SOURCE}"
done
SCRIPT_DIR="$(cd -P "$(dirname "${SOURCE}")" >/dev/null 2>&1 && pwd)"

# 2. Locate Runner Script
RUNNER_PY=""
if [ -f "${SCRIPT_DIR}/run_tracker.py" ]; then
    RUNNER_PY="${SCRIPT_DIR}/run_tracker.py"
elif [ -f "${SCRIPT_DIR}/scripts/run_tracker.py" ]; then
    RUNNER_PY="${SCRIPT_DIR}/scripts/run_tracker.py"
elif [ -f "${SCRIPT_DIR}/../run_tracker.py" ]; then
    RUNNER_PY="${SCRIPT_DIR}/../run_tracker.py"
elif [ -f "${SCRIPT_DIR}/ev-stealth-web/run_tracker.py" ]; then
    RUNNER_PY="${SCRIPT_DIR}/ev-stealth-web/run_tracker.py"
elif [ -f "${SCRIPT_DIR}/../ev-stealth-web/run_tracker.py" ]; then
    RUNNER_PY="${SCRIPT_DIR}/../ev-stealth-web/run_tracker.py"
fi

if [ -z "${RUNNER_PY}" ] || [ ! -f "${RUNNER_PY}" ]; then
    echo "[ERROR] Could not locate 'run_tracker.py' entrypoint in ${SCRIPT_DIR}." >&2
    exit 2
fi

# 3. Resolve Python Interpreter (verifying executable & Python 3.8+ compatibility)
is_valid_python() {
    local candidate="$1"
    if [ -z "${candidate}" ]; then
        return 1
    fi
    if [ -x "${candidate}" ] || command -v "${candidate}" >/dev/null 2>&1; then
        "${candidate}" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >/dev/null 2>&1
        return $?
    fi
    return 1
}

RESOLVED_PYTHON=""
# 3.1. Caller explicit environment overrides
if [ -n "${PYTHON_BIN:-}" ]; then
    if is_valid_python "${PYTHON_BIN}"; then
        RESOLVED_PYTHON="${PYTHON_BIN}"
    else
        echo "[ERROR] Specified PYTHON_BIN '${PYTHON_BIN}' is not a valid Python 3 (>= 3.8) executable." >&2
        exit 2
    fi
elif [ -n "${PYTHON:-}" ]; then
    if is_valid_python "${PYTHON}"; then
        RESOLVED_PYTHON="${PYTHON}"
    else
        echo "[ERROR] Specified PYTHON '${PYTHON}' is not a valid Python 3 (>= 3.8) executable." >&2
        exit 2
    fi
# 3.2. Active virtual environment
elif [ -n "${VIRTUAL_ENV:-}" ] && is_valid_python "${VIRTUAL_ENV}/bin/python3"; then
    RESOLVED_PYTHON="${VIRTUAL_ENV}/bin/python3"
elif [ -n "${VIRTUAL_ENV:-}" ] && is_valid_python "${VIRTUAL_ENV}/bin/python"; then
    RESOLVED_PYTHON="${VIRTUAL_ENV}/bin/python"
# 3.3. Local repository virtual environments
elif [ -f "${SCRIPT_DIR}/.venv/bin/python3" ] && is_valid_python "${SCRIPT_DIR}/.venv/bin/python3"; then
    RESOLVED_PYTHON="${SCRIPT_DIR}/.venv/bin/python3"
elif [ -f "${SCRIPT_DIR}/venv/bin/python3" ] && is_valid_python "${SCRIPT_DIR}/venv/bin/python3"; then
    RESOLVED_PYTHON="${SCRIPT_DIR}/venv/bin/python3"
elif [ -f "${SCRIPT_DIR}/../.venv/bin/python3" ] && is_valid_python "${SCRIPT_DIR}/../.venv/bin/python3"; then
    RESOLVED_PYTHON="${SCRIPT_DIR}/../.venv/bin/python3"
elif [ -f "${SCRIPT_DIR}/../venv/bin/python3" ] && is_valid_python "${SCRIPT_DIR}/../venv/bin/python3"; then
    RESOLVED_PYTHON="${SCRIPT_DIR}/../venv/bin/python3"
# 3.4. System PATH resolution
elif command -v python3 >/dev/null 2>&1 && is_valid_python "python3"; then
    RESOLVED_PYTHON="python3"
elif command -v python >/dev/null 2>&1 && is_valid_python "python"; then
    RESOLVED_PYTHON="python"
fi

if [ -z "${RESOLVED_PYTHON}" ]; then
    echo "[ERROR] Neither 'python3' nor 'python' was found in PATH." >&2
    exit 2
fi
PYTHON_BIN="${RESOLVED_PYTHON}"

START_TIMESTAMP="$(date -u +"%Y-%m-%d %H:%M:%S UTC")"

echo "========================================================================"
echo "  NATIONWIDE EV SUBSIDY TRACKER — SCHEDULED TASK RUNNER"
echo "  Started at        : ${START_TIMESTAMP}"
echo "  Python executable : ${PYTHON_BIN}"
echo "  Runner target     : ${RUNNER_PY}"
echo "  Arguments         : ${*:-<none>}"
echo "========================================================================"

# 4. Execute with argument forwarding and trap exit code
set +e
"${PYTHON_BIN}" "${RUNNER_PY}" "$@"
EXIT_CODE=$?
set -e

END_TIMESTAMP="$(date -u +"%Y-%m-%d %H:%M:%S UTC")"

if [ "${EXIT_CODE}" -eq 0 ]; then
    echo "========================================================================"
    echo "  [SUCCESS] EV Subsidy Tracker pipeline completed at ${END_TIMESTAMP}"
    echo "========================================================================"
else
    echo "========================================================================"
    echo "  [ERROR] EV Subsidy Tracker pipeline failed with code ${EXIT_CODE} at ${END_TIMESTAMP}"
    echo "========================================================================"
fi

exit "${EXIT_CODE}"
