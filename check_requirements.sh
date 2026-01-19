#!/bin/bash
# check_requirements.sh - Verify all requirements are installed

echo "=========================================="
echo "Pockitect MVP - Requirements Check"
echo "=========================================="
echo ""

ERRORS=0
WARNINGS=0

# Check Python
echo -n "Checking Python 3.10+... "
if command -v python3 >/dev/null 2>&1; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 10 ]; then
        echo "✅ Python $PYTHON_VERSION"
    else
        echo "❌ Python $PYTHON_VERSION (requires 3.10+)"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "❌ Python 3 not found"
    ERRORS=$((ERRORS + 1))
fi

# Check Redis
echo -n "Checking Redis server... "
if command -v redis-server >/dev/null 2>&1; then
    if pgrep redis-server >/dev/null 2>&1; then
        REDIS_VERSION=$(redis-server --version 2>&1 | head -n1)
        echo "✅ Redis installed and running ($REDIS_VERSION)"
    else
        echo "⚠️  Redis installed but not running"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo "❌ Redis not found"
    ERRORS=$((ERRORS + 1))
fi

# Check virtual environment
echo -n "Checking virtual environment... "
if [ -d "venv" ]; then
    echo "✅ Virtual environment exists"
else
    echo "⚠️  Virtual environment not found (run: python3 -m venv venv)"
    WARNINGS=$((WARNINGS + 1))
fi

# Check Python packages (if venv exists)
if [ -d "venv" ]; then
    echo -n "Checking Python dependencies... "
    source venv/bin/activate >/dev/null 2>&1
    if pip show PySide6 >/dev/null 2>&1 && \
       pip show redis >/dev/null 2>&1 && \
       pip show boto3 >/dev/null 2>&1; then
        echo "✅ Core packages installed"
    else
        echo "⚠️  Some packages missing (run: pip install -r requirements.txt)"
        WARNINGS=$((WARNINGS + 1))
    fi
    deactivate >/dev/null 2>&1
fi

# Check Ollama (optional)
echo -n "Checking Ollama (optional)... "
if command -v ollama >/dev/null 2>&1; then
    OLLAMA_PORT=${OLLAMA_PORT:-11434}
    if curl -s "http://localhost:${OLLAMA_PORT}/api/tags" >/dev/null 2>&1; then
        echo "✅ Ollama installed and running"
    else
        echo "⚠️  Ollama installed but not running (start with: ollama serve)"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo "⏭️  Ollama not installed (optional, for AI features)"
fi

# Check AWS credentials (optional)
echo -n "Checking AWS credentials... "
if [ -f ~/.aws/credentials ] || [ -n "$AWS_ACCESS_KEY_ID" ]; then
    echo "✅ AWS credentials found"
else
    echo "⚠️  AWS credentials not found (configure via AWS CLI or environment variables)"
    WARNINGS=$((WARNINGS + 1))
fi

echo ""
echo "=========================================="
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo "✅ All requirements satisfied!"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo "⚠️  Some warnings (app may still work)"
    exit 0
else
    echo "❌ $ERRORS error(s) found. Please fix before running the app."
    exit 1
fi
