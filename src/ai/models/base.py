"""Base abstraction layer for LLM clients."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Iterable, Dict, Any
import logging

logger = logging.getLogger(__name__)


class BaseLLMClient(ABC):
    """Abstract base class for all LLM clients."""
    
    def __init__(self, model: str, timeout: float = 30.0):
        """
        Initialize the LLM client.
        
        Args:
            model: Model identifier/name
            timeout: Request timeout in seconds
        """
        self.model = model
        self.timeout = timeout
    
    @abstractmethod
    def generate(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        messages: Optional[list[Dict[str, str]]] = None
    ) -> str:
        """
        Generate a completion from the LLM.
        
        Args:
            prompt: User prompt/input
            system_prompt: Optional system prompt
            messages: Optional pre-formatted message list (alternative to prompt/system_prompt)
            
        Returns:
            Generated text response
        """
        pass
    
    @abstractmethod
    def generate_stream(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        messages: Optional[list[Dict[str, str]]] = None
    ) -> Iterable[str]:
        """
        Generate a streaming completion from the LLM.
        
        Args:
            prompt: User prompt/input
            system_prompt: Optional system prompt
            messages: Optional pre-formatted message list
            
        Yields:
            Text chunks as they arrive
        """
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """
        Check if the LLM service is reachable and healthy.
        
        Returns:
            True if service is available, False otherwise
        """
        pass
    
    def format_messages(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None
    ) -> list[Dict[str, str]]:
        """
        Format prompt and system_prompt into message list format.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            
        Returns:
            List of message dictionaries
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages
