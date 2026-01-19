import types

import pytest

from ai.ollama_client import OllamaClient


class _FakeClient:
    def __init__(self, host: str):
        self.host = host
        self.chat_calls = []
        self.generate_calls = []

    def chat(self, model: str, messages: list[dict]):
        self.chat_calls.append({"model": model, "messages": messages})
        return {"message": {"content": "chat-response"}}

    def generate(self, model: str, prompt: str):
        self.generate_calls.append({"model": model, "prompt": prompt})
        return {"response": "generate-response"}


def test_generate_uses_chat_when_system_prompt(monkeypatch):
    fake_module = types.SimpleNamespace(Client=_FakeClient)
    monkeypatch.setattr("ai.ollama_client.ollama", fake_module, raising=False)

    client = OllamaClient(host="127.0.0.1", port=11434, model="test-model", max_retries=0)
    response = client.generate("hello", system_prompt="system")

    assert response == "chat-response"
    assert client._client is not None
    assert client._client.host == "http://127.0.0.1:11434"
    assert client._client.chat_calls[0]["model"] == "test-model"


def test_generate_uses_generate_without_system_prompt(monkeypatch):
    fake_module = types.SimpleNamespace(Client=_FakeClient)
    monkeypatch.setattr("ai.ollama_client.ollama", fake_module, raising=False)

    client = OllamaClient(host="localhost", port=11434, model="test-model", max_retries=0)
    response = client.generate("hello")

    assert response == "generate-response"
    assert client._client.generate_calls[0]["prompt"] == "hello"


def test_generate_raises_when_ollama_missing(monkeypatch):
    monkeypatch.setattr("ai.ollama_client.ollama", None, raising=False)
    client = OllamaClient(max_retries=0)

    with pytest.raises(RuntimeError, match="ollama package is not installed"):
        client.generate("hello")


def test_generate_propagates_errors(monkeypatch):
    class _FailingClient(_FakeClient):
        def generate(self, model: str, prompt: str):
            raise RuntimeError("boom")

    fake_module = types.SimpleNamespace(Client=_FailingClient)
    monkeypatch.setattr("ai.ollama_client.ollama", fake_module, raising=False)

    client = OllamaClient(max_retries=0, backoff_seconds=0)

    with pytest.raises(RuntimeError, match="boom"):
        client.generate("hello")
