#!/bin/bash
# install.sh - Install Pockitect MVP on Linux/macOS
# Supports: Ubuntu/Debian, Fedora/RHEL, Arch Linux, macOS

set -e

echo "=========================================="
echo "Pockitect MVP - Installation Script"
echo "=========================================="
echo ""

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO=$ID
    else
        DISTRO="unknown"
    fi
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    DISTRO="macos"
else
    echo "❌ Unsupported operating system: $OSTYPE"
    exit 1
fi

echo "Detected OS: $OS ($DISTRO)"
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check Python version
check_python() {
    if command_exists python3; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
        
        if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 10 ]; then
            echo "✅ Python $PYTHON_VERSION found"
            PYTHON_CMD=python3
            return 0
        else
            echo "⚠️  Python $PYTHON_VERSION found (requires 3.10+)"
            return 1
        fi
    else
        echo "❌ Python 3 not found"
        return 1
    fi
}

# Install Python on Linux
install_python_linux() {
    echo "Installing Python 3.10+..."
    case $DISTRO in
        ubuntu|debian)
            sudo apt-get update
            sudo apt-get install -y python3.10 python3.10-venv python3-pip python3-dev
            ;;
        fedora|rhel|centos)
            sudo dnf install -y python3.10 python3-pip python3-devel
            ;;
        arch|manjaro)
            sudo pacman -S --noconfirm python python-pip
            ;;
        *)
            echo "⚠️  Automatic Python installation not supported for $DISTRO"
            echo "   Please install Python 3.10+ manually"
            ;;
    esac
}

# Install Python on macOS
install_python_macos() {
    if command_exists brew; then
        echo "Installing Python 3.10+ via Homebrew..."
        brew install python@3.10
    else
        echo "⚠️  Homebrew not found. Please install Python 3.10+ manually:"
        echo "   https://www.python.org/downloads/"
        echo "   Or install Homebrew: https://brew.sh"
    fi
}

# Install Redis on Linux
install_redis_linux() {
    echo "Installing Redis server..."
    case $DISTRO in
        ubuntu|debian)
            sudo apt-get install -y redis-server
            sudo systemctl enable redis-server
            sudo systemctl start redis-server
            ;;
        fedora|rhel|centos)
            sudo dnf install -y redis
            sudo systemctl enable redis
            sudo systemctl start redis
            ;;
        arch|manjaro)
            sudo pacman -S --noconfirm redis
            sudo systemctl enable redis
            sudo systemctl start redis
            ;;
        *)
            echo "⚠️  Automatic Redis installation not supported for $DISTRO"
            echo "   Please install Redis manually: https://redis.io/docs/getting-started/installation/"
            ;;
    esac
}

# Install Redis on macOS
install_redis_macos() {
    if command_exists brew; then
        echo "Installing Redis via Homebrew..."
        brew install redis
        brew services start redis
    else
        echo "⚠️  Homebrew not found. Please install Redis manually:"
        echo "   brew install redis && brew services start redis"
    fi
}

# Install Qt dependencies for PySide6 on Linux
install_qt_linux() {
    echo "Installing Qt dependencies for PySide6..."
    case $DISTRO in
        ubuntu|debian)
            sudo apt-get install -y \
                libxcb-xinerama0 \
                libxcb-cursor0 \
                libxcb-icccm4 \
                libxcb-image0 \
                libxcb-keysyms1 \
                libxcb-randr0 \
                libxcb-render-util0 \
                libxcb-render0 \
                libxcb-shape0 \
                libxcb-sync1 \
                libxcb-xfixes0 \
                libxcb-xinerama0 \
                libxcb-xkb1 \
                libxkbcommon-x11-0 \
                libxkbcommon0
            ;;
        fedora|rhel|centos)
            sudo dnf install -y \
                qt5-qtbase \
                qt5-qtbase-x11 \
                libxkbcommon
            ;;
        arch|manjaro)
            sudo pacman -S --noconfirm \
                qt5-base \
                xcb-util \
                xcb-util-image \
                xcb-util-keysyms \
                xcb-util-renderutil \
                xcb-util-wm \
                xcb-util-cursor \
                libxkbcommon
            ;;
    esac
}

# Install Ollama
install_ollama() {
    if command_exists ollama; then
        echo "✅ Ollama already installed"
        return 0
    fi
    
    echo "Installing Ollama..."
    if [[ "$OS" == "linux" ]]; then
        curl -fsSL https://ollama.ai/install.sh | sh
    elif [[ "$OS" == "macos" ]]; then
        if command_exists brew; then
            brew install ollama
        else
            echo "⚠️  Homebrew not found. Please install Ollama manually:"
            echo "   Visit: https://ollama.ai"
            return 1
        fi
    fi
    
    echo "✅ Ollama installed. Pull a model with: ollama pull llama3.2"
}

# Main installation
main() {
    # Check Python
    if ! check_python; then
        echo ""
        echo "Python 3.10+ is required. Attempting to install..."
        if [[ "$OS" == "linux" ]]; then
            install_python_linux
        elif [[ "$OS" == "macos" ]]; then
            install_python_macos
        fi
        check_python || exit 1
    fi
    
    # Install Redis
    if ! command_exists redis-server; then
        echo ""
        if [[ "$OS" == "linux" ]]; then
            install_redis_linux
        elif [[ "$OS" == "macos" ]]; then
            install_redis_macos
        fi
    else
        echo "✅ Redis already installed"
    fi
    
    # Verify Redis is running
    if pgrep redis-server > /dev/null; then
        echo "✅ Redis is running"
    else
        echo "⚠️  Redis is installed but not running. Starting..."
        if [[ "$OS" == "linux" ]]; then
            sudo systemctl start redis-server || redis-server --daemonize yes
        elif [[ "$OS" == "macos" ]]; then
            brew services start redis || redis-server --daemonize yes
        fi
    fi
    
    # Install Qt dependencies (Linux only)
    if [[ "$OS" == "linux" ]]; then
        echo ""
        install_qt_linux
    fi
    
    # Install Ollama (optional but recommended)
    echo ""
    read -p "Install Ollama for AI Agent features? (recommended) [Y/n]: " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        install_ollama
    else
        echo "⏭️  Skipping Ollama installation"
    fi
    
    # Create virtual environment and install Python packages
    echo ""
    echo "Setting up Python virtual environment..."
    if [ ! -d "venv" ]; then
        $PYTHON_CMD -m venv venv
        echo "✅ Virtual environment created"
    else
        echo "✅ Virtual environment already exists"
    fi
    
    source venv/bin/activate
    echo "✅ Virtual environment activated"
    
    echo ""
    echo "Installing Python dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    
    echo ""
    echo "=========================================="
    echo "✅ Installation complete!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "  1. Configure AWS credentials (if not already done)"
    echo "  2. Pull an Ollama model: ollama pull llama3.2"
    echo "  3. Run the app: ./run.sh"
    echo "  4. Or use debug mode: ./debug_run.sh"
    echo ""
}

main "$@"
