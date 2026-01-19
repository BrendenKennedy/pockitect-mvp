"""OpenAI API client for GPT models."""

from __future__ import annotations

import logging
from typing import Optional, Iterable, Dict
import keyring

from .base import BaseLLMClient

try:
    import openai
except Exception:
    openai = None

logger = logging.getLogger(__name__)

# Keyring service name for API keys
KEYRING_SERVICE = "PockitectApp"
OPENAI_API_KEY_NAME = "openai_api_key"


class OpenAIClient(BaseLLMClient):
    """OpenAI API client for GPT models."""
    
    def __init__(
        self,
        model: str = "gpt-3.5-turbo",
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(model=model, timeout=timeout)
        self.api_key = api_key or self._get_api_key()
        if openai is None:
            raise RuntimeError("openai package is not installed. Install with: pip install openai")
        if self.api_key:
            openai.api_key = self.api_key
    
    def _get_api_key(self) -> Optional[str]:
        """Get OpenAI API key from keyring or environment."""
        import os
        
        # Try environment variable first
        key = os.getenv("OPENAI_API_KEY")
        if key:
            return key
        
        # Try keyring
        try:
            key = keyring.get_password(KEYRING_SERVICE, OPENAI_API_KEY_NAME)
            return key
        except Exception:
            return None
    
    def _ensure_client(self):
        """Ensure OpenAI client is initialized."""
        if not hasattr(self, '_client') or self._client is None:
            if not self.api_key:
                raise RuntimeError("OpenAI API key not configured. Set it in settings.")
            self._client = openai.OpenAI(api_key=self.api_key, timeout=self.timeout)
        return self._client
    
    def generate(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        messages: Optional[list[Dict[str, str]]] = None
    ) -> str:
        """Generate a completion from OpenAI."""
        client = self._ensure_client()
        
        if messages is None:
            messages = self.format_messages(prompt, system_prompt)
        
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                timeout=self.timeout,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error("OpenAI request failed: %s", e)
            raise
    
    def generate_stream(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        messages: Optional[list[Dict[str, str]]] = None
    ) -> Iterable[str]:
        """Generate a streaming completion from OpenAI."""
        client = self._ensure_client()
        
        if messages is None:
            messages = self.format_messages(prompt, system_prompt)
        
        try:
            stream = client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                timeout=self.timeout,
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error("OpenAI stream request failed: %s", e)
            raise
    
    def health_check(self) -> bool:
        """Check if OpenAI API is reachable."""
        if not self.api_key:
            return False
        try:
            client = self._ensure_client()
            # Simple test call
            client.models.list()
            return True
        except Exception:
            return False
