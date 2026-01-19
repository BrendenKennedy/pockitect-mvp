"""Factory for creating LLM clients."""

from __future__ import annotations

import importlib
import logging
from typing import Optional

from .config import ModelConfig, get_model_config, get_default_model
from .base import BaseLLMClient

logger = logging.getLogger(__name__)


class ModelFactory:
    """Factory for creating LLM client instances."""
    
    @staticmethod
    def create_client(model_id: Optional[str] = None, **kwargs) -> BaseLLMClient:
        """
        Create an LLM client instance.
        
        Args:
            model_id: Model identifier (e.g., "pockitect-ai", "gpt-4")
            **kwargs: Additional arguments to pass to client constructor
            
        Returns:
            LLM client instance
            
        Raises:
            ValueError: If model_id is not found
            RuntimeError: If client creation fails
        """
        if model_id is None:
            model_id = get_default_model()
        
        config = get_model_config(model_id)
        if not config:
            raise ValueError(f"Unknown model: {model_id}")
        
        # Import the client class
        module_path, class_name = config.client_class.rsplit(".", 1)
        try:
            module = importlib.import_module(module_path)
            client_class = getattr(module, class_name)
        except (ImportError, AttributeError) as e:
            raise RuntimeError(f"Failed to import client class {config.client_class}: {e}")
        
        # Create client instance
        # Set default model if not provided
        if "model" not in kwargs:
            kwargs["model"] = config.default_model
        
        try:
            client = client_class(**kwargs)
            return client
        except Exception as e:
            logger.error(f"Failed to create client for {model_id}: {e}")
            raise RuntimeError(f"Failed to create client for {model_id}: {e}") from e
    
    @staticmethod
    def is_model_available(model_id: str) -> bool:
        """
        Check if a model is available (has required dependencies and API keys).
        
        Args:
            model_id: Model identifier
            
        Returns:
            True if model is available, False otherwise
        """
        config = get_model_config(model_id)
        if not config:
            return False
        
        # Check if API key is required and available
        if config.requires_api_key:
            try:
                import keyring
                key = keyring.get_password("PockitectApp", config.api_key_name or "")
                if not key:
                    # Try environment variable
                    import os
                    env_key_name = f"{config.provider.upper()}_API_KEY"
                    key = os.getenv(env_key_name)
                if not key:
                    return False
            except Exception:
                return False
        
        # Try to create client to verify dependencies
        try:
            client = ModelFactory.create_client(model_id)
            return client.health_check()
        except Exception:
            return False
