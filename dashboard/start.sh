#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Anti-BAD Dashboard — one-command launcher (FastAPI + Streamlit)
#
# Starts:
#   * FastAPI backend (uvicorn)  on :8765
#   * Streamlit frontend         on :8501
# Opens the Streamlit UI in your default browser.
#
# Usage (from anywhere):
#   bash dashboard/start.sh
#   bash dashboard/start.sh --api-port 8800 --ui-port 8502
# ─────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

API_PORT=8765
UI_PORT=8501

while [[ $# -gt 0 ]]; do
    case "$1" in
        --api-port) API_PORT="$2"; shift 2 ;;
        --ui-port)  UI_PORT="$2";  shift 2 ;;
        -h|--help)
            echo "Usage: bash dashboard/start.sh [--api-port N] [--ui-port N]"
            exit 0
            ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

# Pick an available Python 3 interpreter
if   command -v python3 &>/dev/null; then PY=(python3)
elif command -v python  &>/dev/null; then PY=(python)
elif command -v py      &>/dev/null; then PY=(py -3)
else
    echo "Error: no Python 3 found on PATH. Activate bachelorenv or install Python 3.9+."
    exit 1
fi

UI_URL="http://localhost:${UI_PORT}"
API_URL="http://localhost:${API_PORT}"

echo "┌─ Anti-BAD Dashboard ────────────────────────────────────"
echo "│  Project:  $PROJECT_ROOT"
echo "│  API:      $API_URL  (FastAPI / uvicorn)"
echo "│  UI:       $UI_URL  (Streamlit)"
echo "└──────────────────────────────────────────────────────────"

cd "$PROJECT_ROOT"

# Background: open the UI in the browser once Streamlit boots
(
    sleep 3
    if   command -v xdg-open &>/dev/null; then xdg-open "$UI_URL"
    elif command -v open     &>/dev/null; then open "$UI_URL"
    fi
) &>/dev/null &

# Background: FastAPI backend
"${PY[@]}" -m uvicorn dashboard.api.main:app \
    --host 127.0.0.1 --port "$API_PORT" --log-level warning &
API_PID=$!

# Trap so closing the launcher (Ctrl+C) also stops the backend
cleanup() {
    echo
    echo "Stopping FastAPI backend (PID $API_PID)…"
    kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Foreground: Streamlit (so logs stay visible and Ctrl+C kills both)
exec "${PY[@]}" -m streamlit run dashboard/streamlit_app.py \
    --server.port "$UI_PORT" \
    --server.headless true \
    --browser.gatherUsageStats false
