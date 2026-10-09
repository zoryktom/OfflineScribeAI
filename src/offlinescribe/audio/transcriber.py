"""Local transcription backends."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from offlinescribe.audio.buffer import WavChunkReader, wav_duration_seconds
from offlinescribe.audio.metadata import read_transcript_metadata


@dataclass(frozen=True)
class TranscriptionSegment:
    start: float
    end: float
    text: str
    speaker: str | None = None
    confidence: float | None = None

    def as_dict(self) -> dict[str, float | str | None]:
        return {
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "speaker": self.speaker,
            "confidence": self.confidence,
        }


@dataclass
class TranscriptionResult:
    text: str
    segments: list[TranscriptionSegment]
    backend: str
    duration_seconds: float
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "text": self.text,
            "segments": [segment.as_dict() for segment in self.segments],
            "backend": self.backend,
            "duration_seconds": self.duration_seconds,
            "warnings": list(self.warnings),
        }


@dataclass
class TranscriptionConfig:
    backend: str = "auto"
    model_path: str | None = None
    compute_type: str = "int8"
    device: str = "auto"
    chunk_seconds: float = 15.0
    language: str | None = "en"
    beam_size: int = 5


class Transcriber(Protocol):
    backend_name: str

    def transcribe(self, audio_path: str | Path) -> TranscriptionResult:
        ...


class MetadataTranscriber:
    """Deterministic offline backend for synthetic WAVs and contract tests."""

    backend_name = "metadata"

    def __init__(self, chunk_seconds: float = 15.0) -> None:
        self.chunk_seconds = chunk_seconds

    def transcribe(self, audio_path: str | Path) -> TranscriptionResult:
        path = Path(audio_path)
        duration = wav_duration_seconds(path)
        metadata = read_transcript_metadata(path)
        warnings: list[str] = []

        if metadata is None:
            text = ""
            warnings.append("No local model path or embedded transcript metadata; produced an empty transcript.")
        else:
            text = str(metadata.get("transcript", "")).strip()

        segments = self._segments_from_metadata(metadata, text, duration)
        if not segments and text:
            segments = [TranscriptionSegment(start=0.0, end=duration, text=text, confidence=1.0)]

        # Touch the chunk reader so this backend exercises the same ingestion path.
        if duration > 0:
            list(WavChunkReader(path, chunk_seconds=self.chunk_seconds))

        return TranscriptionResult(
            text=text,
            segments=segments,
            backend=self.backend_name,
            duration_seconds=duration,
            warnings=warnings,
        )

    def _segments_from_metadata(
        self,
        metadata: dict[str, object] | None,
        text: str,
        duration: float,
    ) -> list[TranscriptionSegment]:
        if not metadata:
            return []
        speaker_turns = metadata.get("speaker_turns")
        if not isinstance(speaker_turns, list) or not speaker_turns:
            return []

        segments: list[TranscriptionSegment] = []
        for index, raw_turn in enumerate(speaker_turns):
            if not isinstance(raw_turn, dict):
                continue
            turn_text = str(raw_turn.get("text", "")).strip()
            if not turn_text:
                continue
            start = _float_or(raw_turn.get("start"), index * duration / max(len(speaker_turns), 1))
            end = _float_or(raw_turn.get("end"), (index + 1) * duration / max(len(speaker_turns), 1))
            speaker = raw_turn.get("speaker")
            segments.append(
                TranscriptionSegment(
                    start=start,
                    end=end,
                    text=turn_text,
                    speaker=str(speaker) if speaker else None,
                    confidence=1.0,
                )
            )

        if segments:
            return segments
        if text:
            return [TranscriptionSegment(start=0.0, end=duration, text=text, confidence=1.0)]
        return []


class FasterWhisperTranscriber:
    """Local faster-whisper backend using ctranslate2 model weights."""

    backend_name = "faster-whisper"

    def __init__(self, config: TranscriptionConfig) -> None:
        self.config = config
        self.model_path = config.model_path or os.environ.get("OFFLINESCRIBE_MODEL_PATH")
        if not self.model_path:
            raise ValueError("faster-whisper backend requires --model-path or OFFLINESCRIBE_MODEL_PATH")
        if not Path(self.model_path).exists():
            raise FileNotFoundError(
                f"Local model path does not exist: {self.model_path}. OfflineScribeAI will not download weights."
            )
        self._model = None

    def transcribe(self, audio_path: str | Path) -> TranscriptionResult:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is not installed. Install with `python -m pip install -e .[whisper]`."
            ) from exc

        if self._model is None:
            self._model = WhisperModel(
                self.model_path,
                device=self.config.device,
                compute_type=self.config.compute_type,
                local_files_only=True,
            )

        duration = wav_duration_seconds(audio_path)
        raw_segments, _info = self._model.transcribe(
            str(audio_path),
            beam_size=self.config.beam_size,
            language=self.config.language,
            vad_filter=True,
        )
        segments: list[TranscriptionSegment] = []
        for raw_segment in raw_segments:
            segments.append(
                TranscriptionSegment(
                    start=float(raw_segment.start),
                    end=float(raw_segment.end),
                    text=raw_segment.text.strip(),
                    confidence=None,
                )
            )
        text = " ".join(segment.text for segment in segments).strip()
        return TranscriptionResult(
            text=text,
            segments=segments,
            backend=self.backend_name,
            duration_seconds=duration,
        )


def transcriber_from_config(config: TranscriptionConfig) -> Transcriber:
    backend = config.backend.lower()
    if backend == "metadata":
        return MetadataTranscriber(chunk_seconds=config.chunk_seconds)
    if backend == "faster-whisper":
        return FasterWhisperTranscriber(config)
    if backend != "auto":
        raise ValueError(f"Unsupported transcription backend: {config.backend}")

    model_path = config.model_path or os.environ.get("OFFLINESCRIBE_MODEL_PATH")
    if model_path:
        return FasterWhisperTranscriber(config)
    return MetadataTranscriber(chunk_seconds=config.chunk_seconds)


def _float_or(value: object, default: float) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default

