import os
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Application Paths
APP_ROOT = Path(__file__).parent.parent.parent
# When running via ./run.sh, CWD is project root
WORKSPACE_ROOT = Path.cwd()
PROJECTS_DIR = WORKSPACE_ROOT / "data" / "projects"
LOGS_DIR = WORKSPACE_ROOT / "data" / "logs"

# Ensure logs directory exists
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Redis Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

# Ollama Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "localhost")
OLLAMA_PORT = int(os.getenv("OLLAMA_PORT", 11434))
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

# Redis Keys
KEY_ALL_RESOURCES = "pockitect:all_resources"
KEY_DEPLOYMENT_PREFIX = "pockitect:deployment:"

# PubSub Channels
CHANNEL_RESOURCE_UPDATE = "resource_update"
CHANNEL_COMMANDS = "pockitect:commands"
CHANNEL_STATUS = "pockitect:status"

# Keyring configuration
KEYRING_SERVICE = "PockitectApp"
KEYRING_USER_ACCESS_KEY = "aws_access_key_id"
KEYRING_USER_SECRET_KEY = "aws_secret_access_key"

# Logging
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
# Default to INFO, allow override
LOG_LEVEL = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)

# Threading
WORKER_MAX = int(os.getenv("WORKER_MAX", "5"))

def setup_logging(name=None):
    """
    Configure logging for the application.
    Writes to both console and a rotating log file in ./logs/
    """
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)
    
    # Avoid adding handlers multiple times
    if logger.hasHandlers():
        return logger
        
    formatter = logging.Formatter(LOG_FORMAT)

    # 1. Console Handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 2. File Handler (Rotating)
    # app.log for main app and shared background components
    log_file = LOGS_DIR / "pockitect.log"
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=10*1024*1024, # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # 3. Third-party loggers
    # Silence noisy libs unless debug
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    return logger
