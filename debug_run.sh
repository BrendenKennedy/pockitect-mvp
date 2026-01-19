#!/bin/bash
# debug_run.sh - Start Redis with logging to data/logs/ directory, then start the App.

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

# 2. Start Application
echo "🚀 Starting Pockitect GUI..."
echo "   Application logs: data/logs/pockitect.log"
echo "================================"

./run.sh
