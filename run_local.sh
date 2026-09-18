#!/usr/bin/env bash
# ==============================================================================
# GridWise Local Run Script
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

echo "======================================================"
echo " Starting GridWise Energy Optimization API (Local)    "
echo "======================================================"

# Load .env file if it exists
if [ -f ".env" ]; then
    echo "Loading environment variables from .env..."
    set -o allexport
    # shellcheck disable=SC1091
    source ".env"
    set +o allexport
fi

# Set default host and port if unset
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
RELOAD="${RELOAD:-true}"

echo "Binding server to http://${HOST}:${PORT}"
echo "Health Check: http://${HOST}:${PORT}/health"
echo "API Docs:     http://${HOST}:${PORT}/docs"

# Execute uvicorn
if [ "${RELOAD}" = "true" ]; then
    exec python3 -m uvicorn app.main:app --host "${HOST}" --port "${PORT}" --reload
else
    exec python3 -m uvicorn app.main:app --host "${HOST}" --port "${PORT}"
fi
