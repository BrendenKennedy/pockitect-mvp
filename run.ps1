# run.ps1 - Run Pockitect MVP
# PowerShell equivalent of run.sh
# This script handles Qt platform plugin issues on various Windows environments

Set-Location $PSScriptRoot

# Activate virtual environment if it exists
if (Test-Path "venv") {
    $activateScript = Join-Path $PSScriptRoot "venv\Scripts\Activate.ps1"
    if (Test-Path $activateScript) {
        & $activateScript
    } else {
        Write-Host "⚠️  Warning: venv found but activation script not found at: $activateScript" -ForegroundColor Yellow
    }
}

# Windows doesn't use WSL or Wayland, but we can still set Qt environment variables
# For Windows, we typically don't need QT_QPA_PLATFORM, but we'll keep it empty
$env:QT_QPA_PLATFORMTHEME = ""

# Optional: Check if Ollama is running (non-blocking warning)
$ollamaPort = if ($env:OLLAMA_PORT) { $env:OLLAMA_PORT } else { "11434" }
$ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue

if ($ollamaCommand) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$ollamaPort/api/tags" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
    } catch {
        Write-Host "⚠️  Warning: Ollama does not appear to be running on port $ollamaPort." -ForegroundColor Yellow
        Write-Host "   AI Agent features will not work. Start Ollama with: ollama serve"
        Write-Host "   Or use .\debug_run.ps1 to auto-start services."
    }
}

# Run the main Python application
python src\main.py $args
