"""Legacy Ollama client - redirects to new models module.

This file is kept for backward compatibility.
New code should import from ai.models instead.
"""

from .models import OllamaClient

__all__ = ["OllamaClient"]
