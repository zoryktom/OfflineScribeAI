"""Whisper adapter. Interactive ASR remains in backend/app/asr_service.py."""

from __future__ import annotations


def transcribe(path: str, model: str = "whisper-large-v3") -> str:
    """Reserved for a live Whisper call. The stub pipeline does not invoke ASR."""
    raise NotImplementedError(
        f"Live ASR ({model}) is not invoked from the research runner. "
        f"Use backend/app/asr_service.py for the workstation path. Got {path!r}."
    )
