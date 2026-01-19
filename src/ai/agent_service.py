"""
AI Agent Service - Handles intent detection and orchestrates YAML generation or command execution.
"""

import logging
from typing import Optional, Dict, Any, Literal
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from .ollama_client import OllamaClient
from .context_provider import ContextProvider
from .yaml_generator import YAMLGenerator
from .command_executor import CommandExecutor
from .project_matcher import ProjectMatcher
from .session_manager import SessionManager
from .ambiguity_detector import AmbiguityDetector
from .tools import ToolExecutor, parse_tool_request

logger = logging.getLogger(__name__)


@dataclass
class AgentIntent:
    """Represents a detected intent from user input."""
    type: Literal["create", "deploy", "power", "terminate", "scan", "query", "budget", "refine", "unknown"]
    confidence: float
    project_name: Optional[str] = None
    action: Optional[str] = None  # For power: "start" or "stop"; for budget: "check", "set"
    region: Optional[str] = None
    details: Dict[str, Any] = None


@dataclass
class AgentResponse:
    """Response from the agent service."""
    intent: AgentIntent
    blueprint: Optional[Dict[str, Any]] = None
    message: str = ""
    requires_confirmation: bool = False
    confirmation_details: Optional[Dict[str, Any]] = None


class AgentService(QObject):
    """
    Main service that coordinates AI agent functionality.
    Handles intent detection, YAML generation, and command execution.
    """
    tool_started = Signal(str)
    tool_finished = Signal(str, str)
    stream_chunk = Signal(str)
    
    def __init__(self, monitor_tab=None):
        super().__init__()
        self.ollama_client = OllamaClient()
        self.context_provider = ContextProvider(monitor_tab)
        self.yaml_generator = YAMLGenerator(self.ollama_client)
        self.command_executor = CommandExecutor()
        self.project_matcher = ProjectMatcher()
        self.session_manager = SessionManager()
        self.ambiguity_detector = AmbiguityDetector()
        self.tool_executor = ToolExecutor(self.context_provider, command_executor=self.command_executor)
    
    def process_request(self, user_input: str, session_id: Optional[str] = None) -> AgentResponse:
        """
        Process a user request and return the appropriate response.
        
        Args:
            user_input: Natural language input from user
            
        Returns:
            AgentResponse with intent, blueprint (if create), and action details
        """
        # Detect intent
        intent = self._detect_intent(user_input)
        logger.info(f"Detected intent: {intent.type} (confidence: {intent.confidence})")

        history = self.session_manager.get_history_for_prompt(session_id or "")
        context = self.context_provider.get_comprehensive_context()
        self._refresh_stale_context(intent, context)
        if intent.type == "create" and history and self._is_refinement_intent(user_input):
            intent = AgentIntent(type="refine", confidence=0.8)
        
        if intent.type == "create":
            # Generate YAML blueprint
            try:
                if not self.ollama_client.health_check():
                    return AgentResponse(
                        intent=intent,
                        message="Ollama is not reachable. Please ensure it is running on localhost:11434."
                    )
                ambiguity = self.ambiguity_detector.detect_ambiguity(user_input)
                resolved = {}
                if ambiguity.get("is_ambiguous"):
                    resolved = self.ambiguity_detector.resolve_with_context(ambiguity, context)
                prompt_input = self._append_resolved_context(user_input, resolved)
                blueprint = self.yaml_generator.generate_blueprint(
                    prompt_input,
                    context,
                    history=history,
                    stream_callback=self.stream_chunk.emit,
                )
                response = AgentResponse(
                    intent=intent,
                    blueprint=blueprint,
                    message="Generated YAML blueprint. Review and save when ready."
                )
                if session_id:
                    self.session_manager.append_turn(session_id, user_input, response.message, blueprint)
                return response
            except Exception as e:
                logger.exception("YAML generation failed")
                return AgentResponse(
                    intent=intent,
                    message=f"Failed to generate blueprint: {str(e)}"
                )
        
        elif intent.type == "refine":
            try:
                if not self.ollama_client.health_check():
                    return AgentResponse(
                        intent=intent,
                        message="Ollama is not reachable. Please ensure it is running on localhost:11434."
                    )
                blueprint = self.yaml_generator.generate_blueprint(
                    user_input,
                    context,
                    history=history,
                    stream_callback=self.stream_chunk.emit,
                )
                response = AgentResponse(
                    intent=intent,
                    blueprint=blueprint,
                    message="Refined YAML blueprint. Review and save when ready."
                )
                if session_id:
                    self.session_manager.append_turn(session_id, user_input, response.message, blueprint)
                return response
            except Exception as e:
                logger.exception("YAML refinement failed")
                return AgentResponse(
                    intent=intent,
                    message=f"Failed to refine blueprint: {str(e)}"
                )

        elif intent.type == "deploy":
            # Resolve project name
            project_name = self._resolve_project(intent.project_name, user_input)
            if not project_name:
                return AgentResponse(
                    intent=intent,
                    message="Could not find a project to deploy. Please specify the project name."
                )
            
            # Load blueprint
            blueprint = self.project_matcher.load_project_by_name(project_name)
            if not blueprint:
                return AgentResponse(
                    intent=intent,
                    message=f"Project '{project_name}' not found or could not be loaded."
                )
            
            return AgentResponse(
                intent=intent,
                blueprint=blueprint,
                message=f"Ready to deploy '{project_name}'. Confirm to proceed.",
                requires_confirmation=True,
                confirmation_details={
                    "project_name": project_name,
                    "action": "deploy",
                    "region": blueprint.get("project", {}).get("region", "unknown")
                }
            )
        
        elif intent.type == "power":
            # Resolve project name
            project_name = self._resolve_project(intent.project_name, user_input)
            if not project_name:
                return AgentResponse(
                    intent=intent,
                    message="Could not find a project. Please specify the project name."
                )
            
            action = intent.action or "stop"  # Default to stop for safety
            action_display = "start" if action == "start" else "stop"
            
            return AgentResponse(
                intent=intent,
                message=f"Ready to {action_display} '{project_name}'. Confirm to proceed.",
                requires_confirmation=True,
                confirmation_details={
                    "project_name": project_name,
                    "action": action,
                    "command_type": "power"
                }
            )
        
        elif intent.type == "terminate":
            # Resolve project or region
            project_name = self._resolve_project(intent.project_name, user_input) if intent.project_name else None
            region = intent.region
            
            if project_name:
                return AgentResponse(
                    intent=intent,
                    message=f"Ready to terminate all resources for '{project_name}'. This is destructive - confirm to proceed.",
                    requires_confirmation=True,
                    confirmation_details={
                        "project_name": project_name,
                        "action": "terminate",
                        "command_type": "terminate"
                    }
                )
            elif region:
                return AgentResponse(
                    intent=intent,
                    message=f"Ready to terminate all resources in region '{region}'. This is destructive - confirm to proceed.",
                    requires_confirmation=True,
                    confirmation_details={
                        "region": region,
                        "action": "terminate",
                        "command_type": "terminate"
                    }
                )
            else:
                return AgentResponse(
                    intent=intent,
                    message="Please specify a project name or region to terminate."
                )
        
        elif intent.type == "scan":
            region = intent.region
            return AgentResponse(
                intent=intent,
                message=f"Ready to scan region{'s' if not region else f' {region}'}. Confirm to proceed.",
                requires_confirmation=False,  # Scan is safe
                confirmation_details={
                    "region": region,
                    "action": "scan",
                    "command_type": "scan"
                }
            )
        
        elif intent.type == "budget":
            # Handle budget/cost queries
            action = intent.action or "check"
            
            if action == "set":
                # Extract budget amount from details
                budget_amount = intent.details.get("amount") if intent.details else None
                if budget_amount:
                    success = self.context_provider.set_monthly_budget(budget_amount)
                    if success:
                        return AgentResponse(
                            intent=intent,
                            message=f"Monthly budget set to ${budget_amount:.2f}. I'll track your spending against this limit."
                        )
                    else:
                        return AgentResponse(
                            intent=intent,
                            message="Failed to set budget. Please try again."
                        )
                else:
                    return AgentResponse(
                        intent=intent,
                        message="Please specify a budget amount, e.g., 'set my budget to $150'"
                    )
            else:
                # Default: check budget status
                budget_summary = self.context_provider.get_budget_summary(force_refresh=True)
                return AgentResponse(
                    intent=intent,
                    message=budget_summary
                )
        
        elif intent.type == "query":
            # Handle queries (list projects, show status, etc.)
            projects = self.context_provider.get_projects_summary()
            return AgentResponse(
                intent=intent,
                message=projects or "No projects found."
            )
        
        else:
            tool_request = parse_tool_request(user_input)
            if tool_request:
                tool_result = self._execute_tool_request(tool_request)
                return AgentResponse(intent=intent, message=tool_result)

            return AgentResponse(
                intent=intent,
                message="I didn't understand that request. Try asking to create a project, deploy, start/stop, terminate, or check your budget."
            )
    
    def _detect_intent(self, user_input: str) -> AgentIntent:
        """
        Detect the intent from user input using keyword matching and LLM if needed.
        
        Returns:
            AgentIntent with detected type and confidence
        """
        input_lower = user_input.lower().strip()
        if len(input_lower) < 3:
            return AgentIntent(type="unknown", confidence=0.2)
        
        # High confidence keyword-based detection
        if any(word in input_lower for word in ["create", "make", "new", "generate", "build"]):
            if any(word in input_lower for word in ["project", "infrastructure", "server", "instance", "app"]):
                return AgentIntent(type="create", confidence=0.9)
        
        if any(word in input_lower for word in ["deploy", "launch", "provision"]):
            return AgentIntent(type="deploy", confidence=0.9, project_name=self._extract_project_name(input_lower))
        
        if any(word in input_lower for word in ["stop", "shut down", "shutdown"]):
            return AgentIntent(type="power", confidence=0.9, action="stop", project_name=self._extract_project_name(input_lower))
        
        if any(word in input_lower for word in ["start", "turn on", "power on"]):
            return AgentIntent(type="power", confidence=0.9, action="start", project_name=self._extract_project_name(input_lower))
        
        if any(word in input_lower for word in ["terminate", "delete", "remove", "destroy"]):
            region = self._extract_region(input_lower)
            project_name = self._extract_project_name(input_lower)
            return AgentIntent(type="terminate", confidence=0.85, project_name=project_name, region=region)
        
        if any(word in input_lower for word in ["scan", "refresh", "update resources"]):
            region = self._extract_region(input_lower)
            return AgentIntent(type="scan", confidence=0.9, region=region)
        
        if any(word in input_lower for word in ["list", "show", "what", "which", "status"]):
            # Check if it's a budget-related query
            if any(word in input_lower for word in ["budget", "cost", "spend", "spending", "bill", "limit", "money"]):
                return AgentIntent(type="budget", confidence=0.9, action="check")
            return AgentIntent(type="query", confidence=0.8)
        
        # Budget/cost keywords
        if any(word in input_lower for word in ["budget", "cost", "spend", "spending", "bill", "limit"]):
            # Check if setting budget
            if any(word in input_lower for word in ["set", "change", "update", "configure"]):
                budget_amount = self._extract_budget_amount(input_lower)
                return AgentIntent(
                    type="budget", 
                    confidence=0.9, 
                    action="set",
                    details={"amount": budget_amount} if budget_amount else None
                )
            # Default to checking budget
            return AgentIntent(type="budget", confidence=0.85, action="check")
        
        # "How close" or "how much" patterns often relate to budget
        if "how close" in input_lower or "how much" in input_lower:
            if any(word in input_lower for word in ["budget", "limit", "month", "spend", "left", "remaining"]):
                return AgentIntent(type="budget", confidence=0.9, action="check")
        
        # Default to create if unclear (safest assumption)
        return AgentIntent(type="create", confidence=0.5)

    def _is_refinement_intent(self, user_input: str) -> bool:
        lowered = user_input.lower()
        return any(
            phrase in lowered
            for phrase in [
                "change",
                "make it",
                "add",
                "remove",
                "update",
                "increase",
                "decrease",
                "bigger",
                "smaller",
                "more powerful",
                "less powerful",
            ]
        )

    def _append_resolved_context(self, user_input: str, resolved: Dict[str, Any]) -> str:
        if not resolved:
            return user_input
        lines = [user_input, "", "Resolved defaults based on context:"]
        for key, value in resolved.items():
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)

    def _execute_tool_request(self, request) -> str:
        tool_name = request.name
        self.tool_started.emit(tool_name)
        result = self.tool_executor.execute(request)
        self.tool_finished.emit(tool_name, result)
        return result

    def _refresh_stale_context(self, intent: AgentIntent, context: Dict[str, Any]) -> None:
        resources_age = context.get("resources_age_seconds")
        budget_age = context.get("budget_age_seconds")

        if intent.type in ("create", "refine", "deploy", "terminate", "power", "scan"):
            if isinstance(resources_age, int) and resources_age > 300:
                request = parse_tool_request(
                    "[TOOL_REQUEST]\nname: scan_resources\nargs: {}\n[/TOOL_REQUEST]"
                )
                if request:
                    self._execute_tool_request(request)

        if intent.type in ("budget", "query"):
            if isinstance(budget_age, int) and budget_age > 3600:
                request = parse_tool_request(
                    "[TOOL_REQUEST]\nname: refresh_costs\nargs: {}\n[/TOOL_REQUEST]"
                )
                if request:
                    self._execute_tool_request(request)
    
    def _extract_project_name(self, text: str) -> Optional[str]:
        """Extract project name from text using simple heuristics."""
        # Look for quoted strings
        import re
        quoted = re.search(r'["\']([^"\']+)["\']', text)
        if quoted:
            return quoted.group(1)
        
        # Look for "project X" or "X project"
        match = re.search(r'(?:project\s+)?([a-z0-9-]+(?:\s+[a-z0-9-]+)*)', text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            # Filter out common words
            if candidate.lower() not in ["the", "my", "all", "this", "that"]:
                return candidate
        
        return None
    
    def _extract_region(self, text: str) -> Optional[str]:
        """Extract AWS region from text."""
        import re
        # Look for region patterns like us-east-1, us-west-2, etc.
        region_match = re.search(r'\b([a-z]{2}-[a-z]+-\d+)\b', text, re.IGNORECASE)
        if region_match:
            return region_match.group(1).lower()
        return None
    
    def _extract_budget_amount(self, text: str) -> Optional[float]:
        """Extract a budget/dollar amount from text."""
        import re
        # Look for dollar amounts like $100, $150.50, 100 dollars, etc.
        patterns = [
            r'\$\s*(\d+(?:\.\d{1,2})?)',  # $100 or $100.50
            r'(\d+(?:\.\d{1,2})?)\s*(?:dollars?|usd)',  # 100 dollars, 100 usd
            r'budget\s+(?:to\s+)?(\d+(?:\.\d{1,2})?)',  # budget to 100
            r'(\d+(?:\.\d{1,2})?)\s+(?:per\s+)?month',  # 100 per month
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
        return None
    
    def _resolve_project(self, project_name: Optional[str], user_input: str) -> Optional[str]:
        """Resolve project name to actual project slug/name."""
        if not project_name:
            return None
        
        # Try to match using ProjectMatcher
        matched = self.project_matcher.find_project(project_name)
        if matched:
            return matched.get("name")
        
        return project_name  # Return as-is if no match found
