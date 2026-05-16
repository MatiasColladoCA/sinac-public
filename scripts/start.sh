#!/bin/bash

# =========================================================
# Environment Startup Script
#
# Usage:
#   source scripts/start.sh
#   or
#   . scripts/start.sh
#
# IMPORTANT:
# Run with "source" to keep the virtual environment active.
# =========================================================

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "❌ This script must be run with:"
    echo ""
    echo "   source scripts/start.sh"
    echo ""
    exit 1
fi

echo "🚀 Starting development environment..."

# Configure PYTHONPATH
export PYTHONPATH="$PYTHONPATH:."
echo "📦 PYTHONPATH configured"

# Start Docker Containers
echo "🐳 Starting Docker containers..."
docker compose up -d

if [ $? -eq 0 ]; then
    echo "✅ Containers started successfully"
else
    echo "❌ Error starting Docker Compose"
    return 1 2>/dev/null || exit 1
fi

# Activate Virtual Environment
if [ ! -f "venv/bin/activate" ]; then
    echo "❌ Virtual environment not found at venv/bin/activate"
    echo "Create it with: python3 -m venv venv"
    return 1 2>/dev/null || exit 1
fi

echo "🐍 Activating virtual environment..."
source venv/bin/activate

if [ -n "$VIRTUAL_ENV" ]; then
    echo "✅ Virtual environment activated: $VIRTUAL_ENV"
else
    echo "❌ Virtual environment failed to activate"
    return 1 2>/dev/null || exit 1
fi

echo ""
echo "🎉 Environment ready for work"
echo ""
