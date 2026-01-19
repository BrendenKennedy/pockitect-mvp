"""Model-specific prompt engineering for optimal results."""

from __future__ import annotations

from typing import Optional
from pathlib import Path
import importlib.util

# Import from parent prompts.py module (avoiding circular import)
prompts_path = Path(__file__).parent.parent / "prompts.py"
spec = importlib.util.spec_from_file_location("ai.prompts_base", prompts_path)
prompts_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prompts_module)

AGENT_SYSTEM_PROMPT = prompts_module.AGENT_SYSTEM_PROMPT
YAML_SYSTEM_PROMPT = prompts_module.YAML_SYSTEM_PROMPT


def get_system_prompt(model_id: str, base_prompt: str = AGENT_SYSTEM_PROMPT) -> str:
    """
    Get optimized system prompt for a specific model.
    
    Args:
        model_id: Model identifier (e.g., "pockitect-ai", "gpt-4", "claude-3-opus")
        base_prompt: Base system prompt to optimize
        
    Returns:
        Model-optimized system prompt
    """
    if model_id.startswith("pockitect-ai"):
        return _optimize_for_ollama(base_prompt)
    elif model_id.startswith("gpt"):
        return _optimize_for_gpt(base_prompt)
    elif model_id.startswith("claude"):
        return _optimize_for_claude(base_prompt)
    else:
        return base_prompt


def get_yaml_prompt(model_id: str, base_prompt: str = YAML_SYSTEM_PROMPT) -> str:
    """
    Get optimized YAML generation prompt for a specific model.
    
    Args:
        model_id: Model identifier
        base_prompt: Base YAML system prompt
        
    Returns:
        Model-optimized YAML prompt
    """
    if model_id.startswith("pockitect-ai"):
        return _optimize_yaml_for_ollama(base_prompt)
    elif model_id.startswith("gpt"):
        return _optimize_yaml_for_gpt(base_prompt)
    elif model_id.startswith("claude"):
        return _optimize_yaml_for_claude(base_prompt)
    else:
        return base_prompt


def _optimize_for_ollama(prompt: str) -> str:
    """
    Optimize prompt for Ollama models (Llama, Mistral, etc.).
    
    Ollama models work better with:
    - Detailed, structured instructions
    - Clear examples
    - Explicit formatting requirements
    """
    enhanced = f"""You are Pockitect AI, an AWS infrastructure assistant.

{prompt}

IMPORTANT INSTRUCTIONS:
- Be precise and structured in your responses
- Use clear formatting with proper indentation
- When generating YAML, follow the exact schema provided
- When using tools, format tool requests exactly as specified
- Always verify your responses for accuracy

Remember to:
1. Read the user's request carefully
2. Use available tools when needed
3. Provide clear, actionable responses
4. Follow AWS best practices"""
    return enhanced


def _optimize_for_gpt(prompt: str) -> str:
    """
    Optimize prompt for GPT models (GPT-3.5, GPT-4).
    
    GPT models work well with:
    - Concise, instruction-following format
    - Clear task definitions
    - Structured reasoning when needed
    """
    enhanced = f"""You are Pockitect AI, an AWS infrastructure assistant.

{prompt}

Instructions:
- Follow instructions precisely
- Use tools when available information is needed
- Provide clear, concise responses
- Generate valid YAML when requested
- Format tool requests correctly"""
    return enhanced


def _optimize_for_claude(prompt: str) -> str:
    """
    Optimize prompt for Claude models (Claude 3 Opus, Sonnet, Haiku).
    
    Claude models excel with:
    - Conversational, reasoning-focused format
    - Chain-of-thought when complex
    - Clear task boundaries
    """
    enhanced = f"""You are Pockitect AI, an AWS infrastructure assistant designed to help users manage AWS infrastructure through natural language.

{prompt}

Approach:
- Think through requests carefully before responding
- Use available tools to gather necessary information
- Provide thoughtful, well-reasoned responses
- When generating infrastructure, consider best practices and costs
- Format your output clearly and consistently

Remember: Your goal is to help users efficiently create and manage AWS infrastructure."""
    return enhanced


def _optimize_yaml_for_ollama(prompt: str) -> str:
    """Optimize YAML generation prompt for Ollama."""
    enhanced = f"""{prompt}

YAML GENERATION RULES FOR OLLAMA:
1. Generate ONLY valid YAML that matches the schema
2. Use proper YAML indentation (spaces, not tabs)
3. Include all required fields from the schema
4. Use null for optional fields that are not specified
5. Follow the example structure exactly
6. Do not include explanations or comments in the YAML
7. Start the YAML with "project:" as the root key"""
    return enhanced


def _optimize_yaml_for_gpt(prompt: str) -> str:
    """Optimize YAML generation prompt for GPT."""
    enhanced = f"""{prompt}

Instructions:
- Generate valid YAML matching the provided schema
- Include required fields, use null for unspecified optional fields
- Maintain proper indentation and structure
- Return only the YAML, no additional text"""
    return enhanced


def _optimize_yaml_for_claude(prompt: str) -> str:
    """Optimize YAML generation prompt for Claude."""
    enhanced = f"""{prompt}

YAML Generation Guidelines:
1. Analyze the user's request carefully
2. Map requirements to the schema structure
3. Generate complete, valid YAML
4. Ensure all relationships are correctly represented
5. Use null for unspecified optional fields
6. Validate your YAML structure before returning

Output only the YAML content, ensuring it matches the schema exactly."""
    return enhanced
