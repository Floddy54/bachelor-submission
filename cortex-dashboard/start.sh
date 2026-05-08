#!/bin/bash
# Quick start script for Anti-BAD Cortex Dashboard

set -e

cd "$(dirname "$0")"

echo "=================================="
echo "Anti-BAD Cortex Dashboard"
echo "=================================="
echo ""

# Resolve a Python interpreter (python3 on macOS/Linux, python on
# Windows / Git Bash with conda envs like antibad24).
PY="$(command -v python3 || command -v python || true)"
if [ -z "$PY" ]; then
    echo "ERROR: no python interpreter found on PATH"
    exit 1
fi

# Install dependencies if needed
if ! "$PY" -c "import fastapi" 2>/dev/null; then
    echo "Installing dependencies..."
    "$PY" -m pip install -r backend/requirements.txt
fi

echo ""
echo "Starting server on http://localhost:8000"
echo "Press Ctrl+C to stop"
echo ""

"$PY" backend/server.py
