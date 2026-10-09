"""Audio ingestion and local transcription helpers."""

from offlinescribe.audio.buffer import AudioChunk, AudioStreamBuffer, WavChunkReader, wav_duration_seconds
from offlinescribe.audio.transcriber import (
    FasterWhisperTranscriber,
    MetadataTranscriber,
    TranscriptionConfig,
    TranscriptionResult,
    transcriber_from_config,
)

__all__ = [
    "AudioChunk",
    "AudioStreamBuffer",
    "FasterWhisperTranscriber",
    "MetadataTranscriber",
    "TranscriptionConfig",
    "TranscriptionResult",
    "WavChunkReader",
    "transcriber_from_config",
    "wav_duration_seconds",
]

