"""Frontier API reference hook. Not used by the default local path."""

from __future__ import annotations


def generate(prompt: str, model: str = "gpt-4o-mini") -> str:
    raise NotImplementedError(
        f"API model {model} is a study-design reference arm only. "
        f"Prompt length={len(prompt)}."
    )
