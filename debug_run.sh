#!/bin/bash
# debug_run.sh - Start Redis and Ollama with logging to data/logs/ directory, then start the App.

# Ensure logs directory exists
mkdir -p data/logs

echo "=== Pockitect Debug Launcher ==="

# 1. Start/Check Redis
if pgrep redis-server > /dev/null; then
    echo "✅ Redis is already running."
    echo "   Note: If this is a system service, logs are likely in /var/log/redis/"
    echo "   To force local logging, stop the system redis and run this script again."
else
    echo "🚀 Starting local Redis server..."
    # Start redis in background, logging to data/logs/redis.log
    # We use nohup to keep it running, but we might want to kill it on exit?
    # For a debug script, it's often better to manage lifecycle.
    # Let's run it in background.
    nohup redis-server --port 6379 --logfile "$(pwd)/data/logs/redis.log" > /dev/null 2>&1 &
    
    # Wait a moment for startup
    sleep 1
    if pgrep redis-server > /dev/null; then
        echo "✅ Redis started. Logs: data/logs/redis.log"
    else
        echo "❌ Failed to start Redis. Check if 'redis-server' is in your PATH."
    fi
fi

# 2. Start/Check Ollama
OLLAMA_PORT=${OLLAMA_PORT:-11434}

# Function to check if Ollama is running
check_ollama_running() {
    if command -v curl > /dev/null 2>&1; then
        curl -s "http://localhost:${OLLAMA_PORT}/api/tags" > /dev/null 2>&1
    elif command -v nc > /dev/null 2>&1; then
        # Fallback: check if port is open
        nc -z localhost ${OLLAMA_PORT} > /dev/null 2>&1
    else
        # Last resort: check if ollama process is running
        pgrep -f "ollama serve" > /dev/null
    fi
}

if command -v ollama > /dev/null 2>&1; then
    if check_ollama_running; then
        echo "✅ Ollama is already running on port ${OLLAMA_PORT}."
    else
        echo "🚀 Starting Ollama server..."
        # Start Ollama in background, redirecting output to log file
        nohup ollama serve > "$(pwd)/data/logs/ollama.log" 2>&1 &
        OLLAMA_PID=$!
        
        # Wait for Ollama to start (it may take a few seconds)
        echo "   Waiting for Ollama to start..."
        for i in {1..10}; do
            sleep 1
            if check_ollama_running; then
                echo "✅ Ollama started. Logs: data/logs/ollama.log"
                break
            fi
            if [ $i -eq 10 ]; then
                echo "⚠️  Ollama may still be starting. Check logs: data/logs/ollama.log"
                echo "   If it fails to start, ensure Ollama is installed and the model is pulled:"
                echo "   ollama pull llama3.2"
            fi
        done
    fi
else
    echo "⚠️  Ollama not found in PATH."
    echo "   Install Ollama from https://ollama.ai or ensure it's in your PATH."
    echo "   The AI Agent features will not work until Ollama is available."
fi

# 3. Start Application
echo "🚀 Starting Pockitect GUI..."
echo "   Application logs: data/logs/pockitect.log"
echo "================================"

./run.sh
