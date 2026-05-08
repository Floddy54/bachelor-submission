#!/bin/bash
# Quick start script for Anti-BAD Cortex Dashboard

set -e

cd "$(dirname "$0")"

echo "=================================="
echo "Anti-BAD Cortex Dashboard"
echo "=================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found"
    exit 1
fi

# Install dependencies if needed
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "Installing dependencies..."
    pip3 install -r backend/requirements.txt
fi

echo ""
echo "Starting server on http://localhost:8000"
echo "Press Ctrl+C to stop"
echo ""

python3 backend/server.py
