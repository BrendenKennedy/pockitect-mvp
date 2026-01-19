# install.ps1 - Install Pockitect MVP on Windows
# Requires: PowerShell 5.1+ (Windows 10/11)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Pockitect MVP - Installation Script" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "⚠️  Some installations may require Administrator privileges" -ForegroundColor Yellow
    Write-Host ""
}

# Function to check if command exists
function Test-Command {
    param($CommandName)
    $null -ne (Get-Command $CommandName -ErrorAction SilentlyContinue)
}

# Check Python
Write-Host "Checking Python installation..." -ForegroundColor Yellow
if (Test-Command python) {
    $pythonVersion = python --version 2>&1 | Out-String
    $versionMatch = $pythonVersion -match "Python (\d+)\.(\d+)"
    if ($versionMatch) {
        $major = [int]$matches[1]
        $minor = [int]$matches[2]
        if ($major -eq 3 -and $minor -ge 10) {
            Write-Host "✅ $pythonVersion found" -ForegroundColor Green
            $pythonCmd = "python"
        } else {
            Write-Host "⚠️  $pythonVersion found (requires 3.10+)" -ForegroundColor Yellow
        }
    }
} elseif (Test-Command python3) {
    $pythonVersion = python3 --version 2>&1 | Out-String
    Write-Host "✅ $pythonVersion found" -ForegroundColor Green
    $pythonCmd = "python3"
} else {
    Write-Host "❌ Python 3 not found" -ForegroundColor Red
    Write-Host ""
    Write-Host "Installing Python 3.10+ via winget..." -ForegroundColor Yellow
    if (Test-Command winget) {
        winget install Python.Python.3.11
        Write-Host "✅ Python installed. Please restart PowerShell and run this script again." -ForegroundColor Green
        exit 0
    } else {
        Write-Host "❌ winget not found. Please install Python manually:" -ForegroundColor Red
        Write-Host "   https://www.python.org/downloads/" -ForegroundColor Cyan
        exit 1
    }
}

# Check/Install Redis
Write-Host ""
Write-Host "Checking Redis installation..." -ForegroundColor Yellow
if (Test-Command redis-server) {
    Write-Host "✅ Redis already installed" -ForegroundColor Green
} else {
    Write-Host "Redis not found. Installing..." -ForegroundColor Yellow
    if (Test-Command winget) {
        Write-Host "Installing Redis via winget..." -ForegroundColor Yellow
        winget install Redis.Redis
        Write-Host "✅ Redis installed" -ForegroundColor Green
        Write-Host "⚠️  Please add Redis to your PATH or restart PowerShell" -ForegroundColor Yellow
    } elseif (Test-Command choco) {
        Write-Host "Installing Redis via Chocolatey..." -ForegroundColor Yellow
        choco install redis-64 -y
        Write-Host "✅ Redis installed" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Neither winget nor Chocolatey found." -ForegroundColor Yellow
        Write-Host "   Please install Redis manually:" -ForegroundColor Yellow
        Write-Host "   1. Download from: https://github.com/microsoftarchive/redis/releases" -ForegroundColor Cyan
        Write-Host "   2. Or install Chocolatey: https://chocolatey.org" -ForegroundColor Cyan
        Write-Host "   3. Then run: choco install redis-64" -ForegroundColor Cyan
        $continue = Read-Host "Continue anyway? (Y/n)"
        if ($continue -eq "n" -or $continue -eq "N") {
            exit 1
        }
    }
}

# Start Redis if not running
Write-Host ""
Write-Host "Checking if Redis is running..." -ForegroundColor Yellow
$redisRunning = Get-Process -Name redis-server -ErrorAction SilentlyContinue
if ($null -eq $redisRunning) {
    Write-Host "Starting Redis server..." -ForegroundColor Yellow
    try {
        Start-Process redis-server -WindowStyle Hidden
        Start-Sleep -Seconds 2
        Write-Host "✅ Redis started" -ForegroundColor Green
    } catch {
        Write-Host "⚠️  Could not start Redis automatically. Please start it manually:" -ForegroundColor Yellow
        Write-Host "   redis-server" -ForegroundColor Cyan
    }
} else {
    Write-Host "✅ Redis is running" -ForegroundColor Green
}

# Check/Install Ollama
Write-Host ""
Write-Host "Checking Ollama installation..." -ForegroundColor Yellow
if (Test-Command ollama) {
    Write-Host "✅ Ollama already installed" -ForegroundColor Green
} else {
    $installOllama = Read-Host "Install Ollama for AI Agent features? (recommended) [Y/n]"
    if ($installOllama -ne "n" -and $installOllama -ne "N") {
        Write-Host "Installing Ollama..." -ForegroundColor Yellow
        if (Test-Command winget) {
            winget install Ollama.Ollama
            Write-Host "✅ Ollama installed" -ForegroundColor Green
        } else {
            Write-Host "⚠️  winget not found. Please install Ollama manually:" -ForegroundColor Yellow
            Write-Host "   https://ollama.ai/download/windows" -ForegroundColor Cyan
        }
    } else {
        Write-Host "⏭️  Skipping Ollama installation" -ForegroundColor Yellow
    }
}

# Create virtual environment
Write-Host ""
Write-Host "Setting up Python virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path "venv")) {
    & $pythonCmd -m venv venv
    Write-Host "✅ Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "✅ Virtual environment already exists" -ForegroundColor Green
}

# Activate virtual environment and install packages
Write-Host ""
Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
& "venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip
pip install -r requirements.txt

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "✅ Installation complete!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Configure AWS credentials (if not already done)" -ForegroundColor White
Write-Host "  2. Pull an Ollama model: ollama pull llama3.2" -ForegroundColor White
Write-Host "  3. Run the app: .\run.ps1" -ForegroundColor White
Write-Host "  4. Or use debug mode: .\debug_run.ps1" -ForegroundColor White
Write-Host ""
