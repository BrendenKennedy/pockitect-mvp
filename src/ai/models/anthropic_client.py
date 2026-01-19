"""Anthropic API client for Claude models."""

from __future__ import annotations

import logging
from typing import Optional, Iterable, Dict
import keyring

from .base import BaseLLMClient

try:
    import anthropic
except Exception:
    anthropic = None

logger = logging.getLogger(__name__)

# Keyring service name for API keys
KEYRING_SERVICE = "PockitectApp"
ANTHROPIC_API_KEY_NAME = "anthropic_api_key"


class AnthropicClient(BaseLLMClient):
    """Anthropic API client for Claude models."""
    
    def __init__(
        self,
        model: str = "claude-3-haiku-20240307",
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(model=model, timeout=timeout)
        self.api_key = api_key or self._get_api_key()
        if anthropic is None:
            raise RuntimeError("anthropic package is not installed. Install with: pip install anthropic")
        if not self.api_key:
            raise RuntimeError("Anthropic API key not configured. Set it in settings.")
    
    def _get_api_key(self) -> Optional[str]:
        """Get Anthropic API key from keyring or environment."""
        import os
        
        # Try environment variable first
        key = os.getenv("ANTHROPIC_API_KEY")
        if key:
            return key
        
        # Try keyring
        try:
            key = keyring.get_password(KEYRING_SERVICE, ANTHROPIC_API_KEY_NAME)
            return key
        except Exception:
            return None
    
    def _ensure_client(self):
        """Ensure Anthropic client is initialized."""
        if not hasattr(self, '_client') or self._client is None:
            if not self.api_key:
                raise RuntimeError("Anthropic API key not configured. Set it in settings.")
            self._client = anthropic.Anthropic(api_key=self.api_key, timeout=self.timeout)
        return self._client
    
    def format_messages(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None
    ) -> list[Dict[str, str]]:
        """Format messages for Anthropic API (uses system parameter)."""
        messages = [{"role": "user", "content": prompt}]
        return messages
    
    def generate(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        messages: Optional[list[Dict[str, str]]] = None
    ) -> str:
        """Generate a completion from Anthropic."""
        client = self._ensure_client()
        
        # Anthropic uses system parameter separately
        if messages is None:
            user_content = prompt
            if system_prompt:
                # For Anthropic, we pass system separately
                messages = [{"role": "user", "content": user_content}]
            else:
                messages = [{"role": "user", "content": prompt}]
        
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 4096,
            }
            if system_prompt:
                kwargs["system"] = system_prompt
            
            response = client.messages.create(**kwargs)
            return response.content[0].text if response.content else ""
        except Exception as e:
            logger.error("Anthropic request failed: %s", e)
            raise
    
    def generate_stream(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        messages: Optional[list[Dict[str, str]]] = None
    ) -> Iterable[str]:
        """Generate a streaming completion from Anthropic."""
        client = self._ensure_client()
        
        if messages is None:
            user_content = prompt
            if system_prompt:
                messages = [{"role": "user", "content": user_content}]
            else:
                messages = [{"role": "user", "content": prompt}]
        
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 4096,
                "stream": True,
            }
            if system_prompt:
                kwargs["system"] = system_prompt
            
            with client.messages.stream(**kwargs) as stream:
                for text in stream.text_stream:
                    yield text
        except Exception as e:
            logger.error("Anthropic stream request failed: %s", e)
            raise
    
    def health_check(self) -> bool:
        """Check if Anthropic API is reachable."""
        if not self.api_key:
            return False
        try:
            # Simple validation by checking API key format
            # (Anthropic doesn't have a simple health check endpoint)
            return len(self.api_key) > 0 and self.api_key.startswith("sk-ant-")
        except Exception:
            return False
