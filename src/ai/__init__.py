"""AI agent package for natural language project generation and command execution."""

from .context_provider import ContextProvider
from .models import OllamaClient
from .yaml_generator import YAMLGenerator
from .validator import BlueprintValidator
from .agent_service import AgentService, AgentResponse, AgentIntent
from .command_executor import CommandExecutor
from .project_matcher import ProjectMatcher
from .prompts import AGENT_SYSTEM_PROMPT, TOOL_REQUEST_FORMAT, YAML_SYSTEM_PROMPT
from .tools import AVAILABLE_TOOLS, ToolExecutor, ToolRequest, parse_tool_request

__all__ = [
    "ContextProvider",
    "OllamaClient",
    "YAMLGenerator",
    "BlueprintValidator",
    "AgentService",
    "AgentResponse",
    "AgentIntent",
    "CommandExecutor",
    "ProjectMatcher",
    "AGENT_SYSTEM_PROMPT",
    "TOOL_REQUEST_FORMAT",
    "YAML_SYSTEM_PROMPT",
    "AVAILABLE_TOOLS",
    "ToolExecutor",
    "ToolRequest",
    "parse_tool_request",
]
