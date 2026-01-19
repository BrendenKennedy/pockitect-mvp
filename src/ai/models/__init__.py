"""Model abstraction layer for LLM clients."""

from .base import BaseLLMClient
from .ollama_client import OllamaClient
from .openai_client import OpenAIClient
from .anthropic_client import AnthropicClient
from .factory import ModelFactory
from .config import (
    ModelConfig,
    MODEL_REGISTRY,
    get_model_config,
    list_models,
    get_default_model,
)

__all__ = [
    "BaseLLMClient",
    "OllamaClient",
    "OpenAIClient",
    "AnthropicClient",
    "ModelFactory",
    "ModelConfig",
    "MODEL_REGISTRY",
    "get_model_config",
    "list_models",
    "get_default_model",
]
