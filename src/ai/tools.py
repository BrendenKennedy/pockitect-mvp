"""Tool definitions and executor for AI tool calls."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.core.aws.cost_service import get_cost_service

logger = logging.getLogger(__name__)


AVAILABLE_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "check_budget",
        "description": "Get current AWS spending vs monthly budget.",
        "when_to_use": "User asks about costs, budget, spending, or before expensive operations.",
        "args_schema": {},
    },
    {
        "name": "refresh_costs",
        "description": "Force refresh cost data from AWS Cost Explorer.",
        "when_to_use": "Cost data is stale (>1 hour) or user explicitly requests refresh.",
        "args_schema": {},
    },
    {
        "name": "list_projects",
        "description": "Get all Pockitect projects with current status.",
        "when_to_use": "User references a project or asks about existing infrastructure.",
        "args_schema": {},
    },
    {
        "name": "scan_resources",
        "description": "Refresh AWS resource inventory from live API.",
        "when_to_use": "Resource data is stale (>5 min) or user asks to refresh.",
        "args_schema": {"regions": "optional list of AWS regions"},
    },
]


@dataclass
class ToolRequest:
    name: str
    args: Dict[str, Any]


def parse_tool_request(text: str) -> Optional[ToolRequest]:
    """Parse a tool request block from model output."""
    if not text:
        return None

    match = re.search(r"\[TOOL_REQUEST\](.*?)\[/TOOL_REQUEST\]", text, re.DOTALL)
    if not match:
        return None

    block = match.group(1)
    name_match = re.search(r"name:\s*(\S+)", block)
    args_match = re.search(r"args:\s*(\{.*\})", block, re.DOTALL)

    if not name_match:
        return None

    name = name_match.group(1).strip()
    args = {}
    if args_match:
        try:
            args = json.loads(args_match.group(1))
        except json.JSONDecodeError:
            logger.warning("Failed to parse tool args JSON.")

    return ToolRequest(name=name, args=args)


class ToolExecutor:
    """Executes tool requests using application services."""

    def __init__(self, context_provider, command_executor=None):
        self.context_provider = context_provider
        self.command_executor = command_executor
        self.cost_service = get_cost_service()

    def execute(self, request: ToolRequest) -> str:
        if request.name == "check_budget":
            return self.context_provider.get_budget_summary(force_refresh=True)

        if request.name == "refresh_costs":
            summary = self.cost_service.get_cost_summary(force_refresh=True)
            return self.cost_service.format_cost_breakdown_for_ai(summary)

        if request.name == "list_projects":
            return self.context_provider.get_projects_summary()

        if request.name == "scan_resources":
            regions = request.args.get("regions") if request.args else None
            return self._request_scan(regions)

        return f"Unknown tool: {request.name}"

    def _request_scan(self, regions: Optional[list[str]]) -> str:
        monitor_tab = getattr(self.context_provider, "monitor_tab", None)
        if monitor_tab and hasattr(monitor_tab, "monitor_service"):
            monitor_tab.monitor_service.request_scan(regions=regions)
            return "Resource scan requested. Results will update shortly."

        if self.command_executor:
            self.command_executor.scan_regions(regions=regions)
            return "Resource scan requested via command channel."

        return "Scan unavailable: monitor service not available."
