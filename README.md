# Pockitect MVP (Event-Driven Edition)

A desktop-first, local-first AWS infrastructure wizard built with PySide6 and Redis pub/sub.

## Features

- **Visual Wizard**: Configure AWS infrastructure (EC2, VPC, RDS, S3) step-by-step.
- **Event-Driven Architecture**: Uses Redis Pub/Sub for real-time UI updates.
- **Background Processing**: Heavy scanning and deployment tasks run in Redis-backed listener threads.
- **Resource Monitor**: View and manage resources across all AWS regions.
- **Local Storage**: Projects saved as YAML blueprints.
- **AI Agent**: Natural language requests for blueprint generation and commands.

## Prerequisites

1. **Python 3.10+**
2. **Redis Server** (Must be running locally)
   ```bash
   sudo apt install redis-server
   sudo service redis-server start
   ```

## Quick Start

### 1. Install Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Run with Debug Logging (Recommended for Development)
We provide helper scripts that automatically start Redis and Ollama in the background, redirect their logs to the `data/logs/` directory, and then launch the app.

**On Linux/macOS/WSL:**
```bash
./debug_run.sh
```

**On Windows (PowerShell):**
```powershell
.\debug_run.ps1
```

**Log Files:**
- `data/logs/pockitect.log`: Main application logs.
- `data/logs/redis.log`: Redis server logs (if started by the script).
- `data/logs/ollama.log`: Ollama server logs (if started by the script).

**Note:** The scripts will check if Redis and Ollama are already running, and only start them if needed. Ensure Ollama is installed and a model is available (e.g., `ollama pull llama3.2`) for AI Agent features to work.

### Manual Startup (Production-like)

**On Linux/macOS/WSL:**
```bash
./run.sh
```

**On Windows (PowerShell):**
```powershell
.\run.ps1
```

## AI Agent

The AI Agent uses Ollama for local LLM inference. 

**Quick Setup:**
1. Install Ollama from https://ollama.ai
2. Pull a model: `ollama pull llama3.2`
3. Use `./debug_run.sh` - it will automatically start Ollama if needed

**Manual Setup:**
If running manually with `./run.sh`, ensure Ollama is running:
```bash
ollama serve
```

You can configure the model and host via environment variables:

- `OLLAMA_HOST` (default: `localhost`)
- `OLLAMA_PORT` (default: `11434`)
- `OLLAMA_MODEL` (default: `llama3.2`)

See the detailed guide at `docs/ai_integration.md`.

## Architecture

```mermaid
flowchart TD
    gui[PySide6 GUI] -->|Publish Commands| redisCmd[Redis_Commands]
    redisCmd -->|Subscribe| listeners[CommandListenerPool]
    listeners -->|Scan/Deploy| aws[AWS Cloud]
    listeners -->|Publish Status| redisStatus[Redis_Status]
    redisStatus -->|Pub/Sub| gui
```

- **PySide6 GUI**: Responsive interface (`src/main.py` + `src/monitor_tab.py`).
- **Redis**: Message bus (`pockitect:commands`, `pockitect:status`) and cache files.
- **Listeners**: Execute `scan_all_regions`, `deploy`, and `terminate` handlers (`src/app/core/listeners.py`).

## Project Structure

```
src/
├── main.py             # Application entry point
├── monitor_service.py  # Bridge between GUI and Redis status updates
├── app/
│   ├── core/
│   │   ├── aws/        # Async AWS scanners and deployers
│   │   ├── listeners.py # Redis command listener pool
│   │   └── redis_client.py # Redis & PubSub wrapper
├── wizard/             # Infrastructure creation wizard
└── aws/                # Legacy/Sync AWS wrappers (used by wizard/monitor)
```
