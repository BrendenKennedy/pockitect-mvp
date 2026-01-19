# check_requirements.ps1 - Verify all requirements are installed (Windows)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Pockitect MVP - Requirements Check" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

$errors = 0
$warnings = 0

# Check Python
Write-Host -NoNewline "Checking Python 3.10+... "
if (Get-Command python -ErrorAction SilentlyContinue) {
    $version = python --version 2>&1 | Out-String
    $match = $version -match "Python (\d+)\.(\d+)"
    if ($match) {
        $major = [int]$matches[1]
        $minor = [int]$matches[2]
        if ($major -eq 3 -and $minor -ge 10) {
            Write-Host "✅ $version" -ForegroundColor Green
        } else {
            Write-Host "❌ $version (requires 3.10+)" -ForegroundColor Red
            $errors++
        }
    }
} else {
    Write-Host "❌ Python 3 not found" -ForegroundColor Red
    $errors++
}

# Check Redis
Write-Host -NoNewline "Checking Redis server... "
if (Get-Command redis-server -ErrorAction SilentlyContinue) {
    $redisProcess = Get-Process -Name redis-server -ErrorAction SilentlyContinue
    if ($null -ne $redisProcess) {
        Write-Host "✅ Redis installed and running" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Redis installed but not running" -ForegroundColor Yellow
        $warnings++
    }
} else {
    Write-Host "❌ Redis not found" -ForegroundColor Red
    $errors++
}

# Check virtual environment
Write-Host -NoNewline "Checking virtual environment... "
if (Test-Path "venv") {
    Write-Host "✅ Virtual environment exists" -ForegroundColor Green
} else {
    Write-Host "⚠️  Virtual environment not found" -ForegroundColor Yellow
    $warnings++
}

# Check Python packages
if (Test-Path "venv") {
    Write-Host -NoNewline "Checking Python dependencies... "
    & "venv\Scripts\Activate.ps1" 2>&1 | Out-Null
    $pyside = pip show PySide6 2>&1
    $redis_py = pip show redis 2>&1
    $boto3 = pip show boto3 2>&1
    
    if ($pyside -notmatch "not found" -and $redis_py -notmatch "not found" -and $boto3 -notmatch "not found") {
        Write-Host "✅ Core packages installed" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Some packages missing" -ForegroundColor Yellow
        $warnings++
    }
}

# Check Ollama (optional)
Write-Host -NoNewline "Checking Ollama (optional)... "
if (Get-Command ollama -ErrorAction SilentlyContinue) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        Write-Host "✅ Ollama installed and running" -ForegroundColor Green
    } catch {
        Write-Host "⚠️  Ollama installed but not running" -ForegroundColor Yellow
        $warnings++
    }
} else {
    Write-Host "⏭️  Ollama not installed (optional)" -ForegroundColor Gray
}

# Check AWS credentials
Write-Host -NoNewline "Checking AWS credentials... "
if (Test-Path "$env:USERPROFILE\.aws\credentials" -or $env:AWS_ACCESS_KEY_ID) {
    Write-Host "✅ AWS credentials found" -ForegroundColor Green
} else {
    Write-Host "⚠️  AWS credentials not found" -ForegroundColor Yellow
    $warnings++
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
if ($errors -eq 0 -and $warnings -eq 0) {
    Write-Host "✅ All requirements satisfied!" -ForegroundColor Green
    exit 0
} elseif ($errors -eq 0) {
    Write-Host "⚠️  Some warnings (app may still work)" -ForegroundColor Yellow
    exit 0
} else {
    Write-Host "❌ $errors error(s) found. Please fix before running." -ForegroundColor Red
    exit 1
}
