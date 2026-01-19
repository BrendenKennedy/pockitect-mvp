from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPreset:
    name: str
    max_seq_len: int
    load_in_4bit: bool


PRESETS: dict[str, ModelPreset] = {
    "llama3.2": ModelPreset(name="llama3.2", max_seq_len=2048, load_in_4bit=True),
    "qwen3": ModelPreset(name="qwen3", max_seq_len=2048, load_in_4bit=True),
    "qwen2.5-3b": ModelPreset(name="qwen2.5-3b", max_seq_len=2048, load_in_4bit=True),
    "mistral7b": ModelPreset(name="mistral-7b-instruct", max_seq_len=2048, load_in_4bit=True),
}


def get_preset(name: str | None) -> ModelPreset | None:
    if not name:
        return None
    return PRESETS.get(name)
