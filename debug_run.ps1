# debug_run.ps1 - Start Redis and Ollama with logging to data/logs/ directory, then start the App.
# PowerShell equivalent of debug_run.sh

# Ensure logs directory exists
$logsDir = Join-Path $PSScriptRoot "data\logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
}

Write-Host "=== Pockitect Debug Launcher ===" -ForegroundColor Cyan

# 1. Start/Check Redis
$redisProcesses = Get-Process -Name "redis-server" -ErrorAction SilentlyContinue
if ($redisProcesses) {
    Write-Host "✅ Redis is already running." -ForegroundColor Green
    Write-Host "   Note: If this is a system service, logs are likely in the Redis installation directory."
    Write-Host "   To force local logging, stop the system redis and run this script again."
} else {
    Write-Host "🚀 Starting local Redis server..." -ForegroundColor Yellow
    
    $redisLogFile = Join-Path $PSScriptRoot "data\logs\redis.log"
    $redisPath = Get-Command redis-server -ErrorAction SilentlyContinue
    
    if (-not $redisPath) {
        Write-Host "❌ Failed to start Redis. Check if 'redis-server' is in your PATH." -ForegroundColor Red
        Write-Host "   On Windows, Redis can be installed via Chocolatey: choco install redis-64" -ForegroundColor Gray
    } else {
        # Start Redis in background
        # Note: On Windows, Redis might use different arguments or configuration
        # Try with logfile, but fall back to logging if that doesn't work
        $redisLogFileArg = $redisLogFile -replace '\\', '/'
        $redisArgs = @("--port", "6379", "--logfile", $redisLogFileArg)
        
        try {
            Start-Process -FilePath $redisPath.Path -ArgumentList $redisArgs -WindowStyle Hidden -PassThru | Out-Null
            
            # Wait a moment for startup
            Start-Sleep -Seconds 1
            
            $redisProcesses = Get-Process -Name "redis-server" -ErrorAction SilentlyContinue
            if ($redisProcesses) {
                Write-Host "✅ Redis started. Logs: data\logs\redis.log" -ForegroundColor Green
            } else {
                Write-Host "⚠️  Redis process not detected. It may still be starting or use a different process name." -ForegroundColor Yellow
                Write-Host "   Check logs: data\logs\redis.log" -ForegroundColor Gray
            }
        } catch {
            Write-Host "❌ Failed to start Redis: $_" -ForegroundColor Red
        }
    }
}

# 2. Start/Check Ollama
$ollamaPort = if ($env:OLLAMA_PORT) { $env:OLLAMA_PORT } else { "11434" }

# Function to check if Ollama is running
function Test-OllamaRunning {
    param([string]$Port)
    
    try {
        # Try to check via HTTP API
        $response = Invoke-WebRequest -Uri "http://localhost:$Port/api/tags" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        return $true
    } catch {
        # Fallback: check if ollama process is running
        $ollamaProcesses = Get-Process -Name "ollama" -ErrorAction SilentlyContinue
        return ($null -ne $ollamaProcesses)
    }
}

$ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
if ($ollamaCommand) {
    if (Test-OllamaRunning -Port $ollamaPort) {
        Write-Host "✅ Ollama is already running on port $ollamaPort." -ForegroundColor Green
    } else {
        Write-Host "🚀 Starting Ollama server..." -ForegroundColor Yellow
        
        $ollamaLogFile = Join-Path $PSScriptRoot "data\logs\ollama.log"
        
        # Start Ollama in background, redirecting output to log file
        $ollamaProcess = Start-Process -FilePath $ollamaCommand.Path -ArgumentList "serve" -WindowStyle Hidden -PassThru -RedirectStandardOutput $ollamaLogFile -RedirectStandardError $ollamaLogFile
        
        # Wait for Ollama to start (it may take a few seconds)
        Write-Host "   Waiting for Ollama to start..." -ForegroundColor Gray
        $started = $false
        for ($i = 1; $i -le 10; $i++) {
            Start-Sleep -Seconds 1
            if (Test-OllamaRunning -Port $ollamaPort) {
                Write-Host "✅ Ollama started. Logs: data\logs\ollama.log" -ForegroundColor Green
                $started = $true
                break
            }
        }
        
        if (-not $started) {
            Write-Host "⚠️  Ollama may still be starting. Check logs: data\logs\ollama.log" -ForegroundColor Yellow
            Write-Host "   If it fails to start, ensure Ollama is installed and the model is pulled:"
            Write-Host "   ollama pull llama3.2"
        }
    }
} else {
    Write-Host "⚠️  Ollama not found in PATH." -ForegroundColor Yellow
    Write-Host "   Install Ollama from https://ollama.ai or ensure it's in your PATH."
    Write-Host "   The AI Agent features will not work until Ollama is available."
}

# 3. Start Application
Write-Host "🚀 Starting Pockitect GUI..." -ForegroundColor Cyan
Write-Host "   Application logs: data\logs\pockitect.log" -ForegroundColor Gray
Write-Host "================================" -ForegroundColor Cyan

# Run the main run script
& "$PSScriptRoot\run.ps1"
