"""Chunked WAV ingestion and bounded streaming buffers."""

from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class AudioChunk:
    pcm: bytes
    sample_rate: int
    channels: int
    sample_width: int
    start_seconds: float
    end_seconds: float
    speaker_hint: str | None = None


class WavChunkReader:
    """Iterate through a PCM WAV file in time-based chunks."""

    def __init__(self, path: str | Path, chunk_seconds: float = 15.0) -> None:
        if chunk_seconds <= 0:
            raise ValueError("chunk_seconds must be greater than zero")
        self.path = Path(path)
        self.chunk_seconds = chunk_seconds

    def __iter__(self) -> Iterator[AudioChunk]:
        with wave.open(str(self.path), "rb") as handle:
            sample_rate = handle.getframerate()
            channels = handle.getnchannels()
            sample_width = handle.getsampwidth()
            frames_per_chunk = max(1, int(sample_rate * self.chunk_seconds))
            frame_index = 0

            while True:
                pcm = handle.readframes(frames_per_chunk)
                if not pcm:
                    break
                frames_read = len(pcm) // (channels * sample_width)
                start_seconds = frame_index / sample_rate
                frame_index += frames_read
                end_seconds = frame_index / sample_rate
                yield AudioChunk(
                    pcm=pcm,
                    sample_rate=sample_rate,
                    channels=channels,
                    sample_width=sample_width,
                    start_seconds=start_seconds,
                    end_seconds=end_seconds,
                )


class AudioStreamBuffer:
    """Bounded PCM buffer for streaming-style transcription loops."""

    def __init__(
        self,
        sample_rate: int,
        channels: int = 1,
        sample_width: int = 2,
        chunk_seconds: float = 5.0,
        max_buffer_seconds: float = 30.0,
    ) -> None:
        if sample_rate <= 0:
            raise ValueError("sample_rate must be greater than zero")
        if channels <= 0:
            raise ValueError("channels must be greater than zero")
        if sample_width <= 0:
            raise ValueError("sample_width must be greater than zero")
        if chunk_seconds <= 0:
            raise ValueError("chunk_seconds must be greater than zero")
        if max_buffer_seconds < chunk_seconds:
            raise ValueError("max_buffer_seconds must be at least chunk_seconds")

        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width = sample_width
        self.chunk_seconds = chunk_seconds
        self.max_buffer_seconds = max_buffer_seconds
        self._buffer = bytearray()
        self._frames_seen = 0

    @property
    def buffered_seconds(self) -> float:
        return self._frames_in_buffer / self.sample_rate

    @property
    def _bytes_per_frame(self) -> int:
        return self.channels * self.sample_width

    @property
    def _frames_in_buffer(self) -> int:
        return len(self._buffer) // self._bytes_per_frame

    def append_pcm(self, pcm: bytes) -> list[AudioChunk]:
        self._buffer.extend(pcm)
        self._trim_to_max()
        return self.pop_ready_chunks()

    def pop_ready_chunks(self) -> list[AudioChunk]:
        chunks: list[AudioChunk] = []
        frames_per_chunk = int(self.sample_rate * self.chunk_seconds)
        bytes_per_chunk = frames_per_chunk * self._bytes_per_frame

        while len(self._buffer) >= bytes_per_chunk:
            pcm = bytes(self._buffer[:bytes_per_chunk])
            del self._buffer[:bytes_per_chunk]
            start = self._frames_seen / self.sample_rate
            self._frames_seen += frames_per_chunk
            end = self._frames_seen / self.sample_rate
            chunks.append(
                AudioChunk(
                    pcm=pcm,
                    sample_rate=self.sample_rate,
                    channels=self.channels,
                    sample_width=self.sample_width,
                    start_seconds=start,
                    end_seconds=end,
                )
            )
        return chunks

    def flush(self) -> AudioChunk | None:
        if not self._buffer:
            return None
        frames = self._frames_in_buffer
        start = self._frames_seen / self.sample_rate
        self._frames_seen += frames
        end = self._frames_seen / self.sample_rate
        pcm = bytes(self._buffer)
        self._buffer.clear()
        return AudioChunk(
            pcm=pcm,
            sample_rate=self.sample_rate,
            channels=self.channels,
            sample_width=self.sample_width,
            start_seconds=start,
            end_seconds=end,
        )

    def _trim_to_max(self) -> None:
        max_frames = int(self.sample_rate * self.max_buffer_seconds)
        max_bytes = max_frames * self._bytes_per_frame
        if len(self._buffer) <= max_bytes:
            return
        overflow_bytes = len(self._buffer) - max_bytes
        overflow_frames = overflow_bytes // self._bytes_per_frame
        aligned_overflow = overflow_frames * self._bytes_per_frame
        del self._buffer[:aligned_overflow]
        self._frames_seen += overflow_frames


def wav_duration_seconds(path: str | Path) -> float:
    with wave.open(str(path), "rb") as handle:
        if handle.getframerate() == 0:
            return 0.0
        return handle.getnframes() / float(handle.getframerate())

