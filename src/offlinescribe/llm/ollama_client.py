"""Local Ollama client hook. Workstation generation stays in backend/app/note_service.py."""

from __future__ import annotations


def generate(prompt: str, model: str = "llama3.1:8b") -> str:
    raise NotImplementedError(
        f"Live Ollama ({model}) is not called from the stub ablation runner. "
        f"Prompt length={len(prompt)}."
    )
