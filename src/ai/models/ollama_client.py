"""Ollama client wrapper for local LLM calls."""

from __future__ import annotations

import logging
import time
from typing import Optional, Callable, TypeVar, Any, Iterable, Dict

from .base import BaseLLMClient

# Import TOOL_REQUEST_FORMAT - try prompts directory first, fallback to file
try:
    from ..prompts import TOOL_REQUEST_FORMAT
except ImportError:
    # Fallback: import directly from prompts.py file
    from pathlib import Path
    import importlib.util
    prompts_path = Path(__file__).parent.parent.parent / "ai" / "prompts.py"
    spec = importlib.util.spec_from_file_location("ai.prompts_direct", prompts_path)
    prompts_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prompts_module)
    TOOL_REQUEST_FORMAT = prompts_module.TOOL_REQUEST_FORMAT

try:
    import ollama
except Exception:  # pragma: no cover - handled at runtime
    ollama = None

from app.core.config import OLLAMA_HOST, OLLAMA_PORT, OLLAMA_MODEL

logger = logging.getLogger(__name__)


T = TypeVar("T")


class OllamaClient(BaseLLMClient):
    """Ollama client for local LLM inference."""
    
    def __init__(
        self,
        model: str = OLLAMA_MODEL,
        host: str = OLLAMA_HOST,
        port: int = OLLAMA_PORT,
        timeout: float = 30.0,
        max_retries: int = 2,
        backoff_seconds: float = 0.5,
    ) -> None:
        super().__init__(model=model, timeout=timeout)
        self.host = host
        self.port = port
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._client = None

    def _ensure_client(self) -> None:
        if ollama is None:
            raise RuntimeError("ollama package is not installed.")
        if self._client is None:
            base_url = f"http://{self.host}:{self.port}"
            self._client = ollama.Client(host=base_url)

    def _with_retry(self, fn: Callable[[], T]) -> T:
        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                return fn()
            except Exception as exc:  # pragma: no cover - runtime failures only
                last_exc = exc
                logger.warning("Ollama request failed (attempt %s/%s): %s", attempt + 1, self.max_retries + 1, exc)
                if attempt < self.max_retries:
                    time.sleep(self.backoff_seconds * (2 ** attempt))
        raise last_exc  # type: ignore[misc]

    def generate(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        messages: Optional[list[Dict[str, str]]] = None
    ) -> str:
        """Generate a completion from Ollama."""
        self._ensure_client()

        def _request() -> str:
            if messages:
                response = self._client.chat(model=self.model, messages=messages)
                return response.get("message", {}).get("content", "")
            elif system_prompt:
                response = self._client.chat(
                    model=self.model,
                    messages=self.format_messages(prompt, system_prompt),
                )
                return response.get("message", {}).get("content", "")
            response = self._client.generate(model=self.model, prompt=prompt)
            return response.get("response", "")

        try:
            return self._with_retry(_request)
        except Exception as exc:
            logger.error("Ollama request failed after retries: %s", exc)
            raise

    def generate_stream(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        messages: Optional[list[Dict[str, str]]] = None
    ) -> Iterable[str]:
        """Yield response chunks as they arrive."""
        self._ensure_client()
        
        if messages:
            stream = self._client.chat(model=self.model, messages=messages, stream=True)
            for chunk in stream:
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content
            return
        elif system_prompt:
            stream = self._client.chat(
                model=self.model,
                messages=self.format_messages(prompt, system_prompt),
                stream=True,
            )
            for chunk in stream:
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content
            return
        stream = self._client.generate(model=self.model, prompt=prompt, stream=True)
        for chunk in stream:
            content = chunk.get("response", "")
            if content:
                yield content

    def health_check(self) -> bool:
        """Check if the Ollama server is reachable."""
        try:
            self._ensure_client()
            self._client.list()
            return True
        except Exception:
            return False

    def generate_with_tools(self, prompt: str, system_prompt: str, tools: list[dict]) -> Dict[str, Any]:
        """Generate a response that may include a tool request block."""
        tool_prompt = self._format_tools_for_prompt(tools)
        full_system = f"{system_prompt}\n\n{tool_prompt}"
        response = self.generate(prompt, system_prompt=full_system)
        return {"raw": response, "tool_request": self._extract_tool_request(response)}

    def _format_tools_for_prompt(self, tools: list[dict]) -> str:
        lines = ["Available tools:"]
        for tool in tools:
            lines.append(f"- {tool.get('name')}: {tool.get('description')}")
        lines.append("")
        lines.append(TOOL_REQUEST_FORMAT.strip())
        return "\n".join(lines)

    def _extract_tool_request(self, response: str) -> Optional[str]:
        import re

        match = re.search(r"\[TOOL_REQUEST\].*?\[/TOOL_REQUEST\]", response, re.DOTALL)
        if match:
            return match.group(0)
        return None
