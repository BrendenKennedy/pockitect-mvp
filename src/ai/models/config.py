"""Model configuration and registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Literal


@dataclass
class ModelConfig:
    """Configuration for an LLM model."""
    
    id: str
    display_name: str
    provider: Literal["pockitect", "openai", "anthropic"]
    client_class: str  # Module path to client class
    default_model: str  # Default model identifier for the provider
    requires_api_key: bool = False
    api_key_name: Optional[str] = None
    privacy_required: bool = False  # Whether anonymization is required
    
    def __post_init__(self):
        """Validate configuration."""
        if self.requires_api_key and not self.api_key_name:
            raise ValueError(f"Model {self.id} requires API key but api_key_name not set")


# Model registry
MODEL_REGISTRY: dict[str, ModelConfig] = {
    "pockitect-ai": ModelConfig(
        id="pockitect-ai",
        display_name="🏠 Pockitect AI (Ollama)",
        provider="pockitect",
        client_class="ai.models.ollama_client.OllamaClient",
        default_model="llama3.2",
        requires_api_key=False,
        privacy_required=False,
    ),
    "gpt-3.5-turbo": ModelConfig(
        id="gpt-3.5-turbo",
        display_name="🤖 GPT-3.5 Turbo",
        provider="openai",
        client_class="ai.models.openai_client.OpenAIClient",
        default_model="gpt-3.5-turbo",
        requires_api_key=True,
        api_key_name="openai_api_key",
        privacy_required=True,
    ),
    "gpt-4": ModelConfig(
        id="gpt-4",
        display_name="🚀 GPT-4",
        provider="openai",
        client_class="ai.models.openai_client.OpenAIClient",
        default_model="gpt-4",
        requires_api_key=True,
        api_key_name="openai_api_key",
        privacy_required=True,
    ),
    "gpt-4-turbo": ModelConfig(
        id="gpt-4-turbo",
        display_name="⚡ GPT-4 Turbo",
        provider="openai",
        client_class="ai.models.openai_client.OpenAIClient",
        default_model="gpt-4-turbo-preview",
        requires_api_key=True,
        api_key_name="openai_api_key",
        privacy_required=True,
    ),
    "claude-3-opus": ModelConfig(
        id="claude-3-opus",
        display_name="🧠 Claude 3 Opus",
        provider="anthropic",
        client_class="ai.models.anthropic_client.AnthropicClient",
        default_model="claude-3-opus-20240229",
        requires_api_key=True,
        api_key_name="anthropic_api_key",
        privacy_required=True,
    ),
    "claude-3-sonnet": ModelConfig(
        id="claude-3-sonnet",
        display_name="🎯 Claude 3 Sonnet",
        provider="anthropic",
        client_class="ai.models.anthropic_client.AnthropicClient",
        default_model="claude-3-sonnet-20240229",
        requires_api_key=True,
        api_key_name="anthropic_api_key",
        privacy_required=True,
    ),
    "claude-3-haiku": ModelConfig(
        id="claude-3-haiku",
        display_name="⚡ Claude 3 Haiku",
        provider="anthropic",
        client_class="ai.models.anthropic_client.AnthropicClient",
        default_model="claude-3-haiku-20240307",
        requires_api_key=True,
        api_key_name="anthropic_api_key",
        privacy_required=True,
    ),
}


def get_model_config(model_id: str) -> Optional[ModelConfig]:
    """Get model configuration by ID."""
    return MODEL_REGISTRY.get(model_id)


def list_models() -> list[ModelConfig]:
    """List all available models."""
    return list(MODEL_REGISTRY.values())


def get_default_model() -> str:
    """Get the default model ID."""
    return "pockitect-ai"
