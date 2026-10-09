"""Deterministic synthetic WAV fixtures for offline demos and tests."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from offlinescribe.audio.metadata import append_transcript_metadata

DEFAULT_SYNTHETIC_TRANSCRIPT = (
    "Patient: I have had a cough and fever for three days with mild shortness of breath. "
    "Clinician: Objective vitals show temperature 101.2 F and oxygen saturation 96 percent. "
    "Assessment: Viral upper respiratory infection with history of asthma. "
    "Plan: Use albuterol inhaler as needed, take acetaminophen for fever, hydrate, and follow up in two days."
)

DEFAULT_SPEAKER_TURNS = [
    {
        "speaker": "patient",
        "start": 0.0,
        "end": 1.3,
        "text": "I have had a cough and fever for three days with mild shortness of breath.",
    },
    {
        "speaker": "clinician",
        "start": 1.3,
        "end": 2.3,
        "text": "Objective vitals show temperature 101.2 F and oxygen saturation 96 percent.",
    },
    {
        "speaker": "clinician",
        "start": 2.3,
        "end": 3.1,
        "text": "Assessment: Viral upper respiratory infection with history of asthma.",
    },
    {
        "speaker": "clinician",
        "start": 3.1,
        "end": 4.0,
        "text": "Plan: Use albuterol inhaler as needed, take acetaminophen for fever, hydrate, and follow up in two days.",
    },
]


def write_synthetic_wav(
    path: str | Path,
    transcript: str = DEFAULT_SYNTHETIC_TRANSCRIPT,
    speaker_turns: list[dict[str, object]] | None = None,
    duration_seconds: float = 4.0,
    sample_rate: int = 16_000,
) -> Path:
    """Write a simple tone WAV and embed a deterministic transcript chunk."""

    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be greater than zero")
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    total_frames = int(duration_seconds * sample_rate)
    amplitude = 1200
    frequency = 440.0

    with wave.open(str(out), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        frames = bytearray()
        for index in range(total_frames):
            value = int(amplitude * math.sin(2.0 * math.pi * frequency * index / sample_rate))
            frames.extend(struct.pack("<h", value))
        handle.writeframes(bytes(frames))

    turns = speaker_turns if speaker_turns is not None else _scaled_default_turns(duration_seconds)
    append_transcript_metadata(out, transcript=transcript, speaker_turns=turns)
    return out


def _scaled_default_turns(duration_seconds: float) -> list[dict[str, object]]:
    scale = duration_seconds / 4.0
    scaled: list[dict[str, object]] = []
    for turn in DEFAULT_SPEAKER_TURNS:
        scaled.append(
            {
                **turn,
                "start": round(float(turn["start"]) * scale, 4),
                "end": round(float(turn["end"]) * scale, 4),
            }
        )
    return scaled
