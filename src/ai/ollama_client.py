"""Legacy Ollama client - redirects to new models module.

This file is kept for backward compatibility.
New code should import from ai.models instead.
"""

import warnings

from .models import OllamaClient

warnings.warn(
    "ai.ollama_client is deprecated; import OllamaClient from ai.models instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["OllamaClient"]
