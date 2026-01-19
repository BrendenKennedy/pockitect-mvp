"""Prompt engineering module - re-exports from prompts.py and model_prompts.py."""

# Import from the prompts.py file in parent directory using importlib to avoid circular import
from pathlib import Path
import importlib.util

parent_dir = Path(__file__).parent.parent
prompts_file = parent_dir / "prompts.py"

if prompts_file.exists():
    spec = importlib.util.spec_from_file_location("ai.prompts_file", prompts_file)
    prompts_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prompts_module)
    
    AGENT_SYSTEM_PROMPT = prompts_module.AGENT_SYSTEM_PROMPT
    TOOL_REQUEST_FORMAT = prompts_module.TOOL_REQUEST_FORMAT
    YAML_SYSTEM_PROMPT = prompts_module.YAML_SYSTEM_PROMPT
else:
    # Fallback if prompts.py doesn't exist
    AGENT_SYSTEM_PROMPT = ""
    TOOL_REQUEST_FORMAT = ""
    YAML_SYSTEM_PROMPT = ""

# Import model-specific functions
from .model_prompts import get_system_prompt, get_yaml_prompt

__all__ = [
    "AGENT_SYSTEM_PROMPT",
    "TOOL_REQUEST_FORMAT",
    "YAML_SYSTEM_PROMPT",
    "get_system_prompt",
    "get_yaml_prompt",
]
