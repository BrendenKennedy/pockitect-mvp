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

python src/main.py "$@"
