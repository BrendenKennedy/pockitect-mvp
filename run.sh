#!/bin/bash
# Run Pockitect MVP
# This script handles Qt platform plugin issues on various Linux environments

cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Check for WSL
if grep -qi microsoft /proc/version 2>/dev/null; then
    echo "Detected WSL environment, using Wayland..."
    export QT_QPA_PLATFORM=wayland
fi

# Fallback for missing xcb-cursor
export QT_QPA_PLATFORMTHEME=""

# Optional: Check if Ollama is running (non-blocking warning)
OLLAMA_PORT=${OLLAMA_PORT:-11434}
if command -v ollama > /dev/null 2>&1; then
    if command -v curl > /dev/null 2>&1; then
        if ! curl -s "http://localhost:${OLLAMA_PORT}/api/tags" > /dev/null 2>&1; then
            echo "⚠️  Warning: Ollama does not appear to be running on port ${OLLAMA_PORT}."
            echo "   AI Agent features will not work. Start Ollama with: ollama serve"
            echo "   Or use ./debug_run.sh to auto-start services."
        fi
    fi
fi

python src/main.py "$@"
