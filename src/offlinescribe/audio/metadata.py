"""Read transcript hints from deterministic synthetic WAV metadata chunks."""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

TRANSCRIPT_CHUNK_ID = b"osct"


def read_transcript_metadata(path: str | Path) -> dict[str, Any] | None:
    """Return embedded OfflineScribe metadata from a WAV file, if present."""

    data = Path(path).read_bytes()
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return None

    offset = 12
    while offset + 8 <= len(data):
        chunk_id = data[offset : offset + 4]
        chunk_size = struct.unpack_from("<I", data, offset + 4)[0]
        payload_start = offset + 8
        payload_end = payload_start + chunk_size
        if payload_end > len(data):
            break
        if chunk_id == TRANSCRIPT_CHUNK_ID:
            payload = data[payload_start:payload_end]
            return json.loads(payload.decode("utf-8"))
        offset = payload_end + (chunk_size % 2)
    return None


def append_transcript_metadata(path: str | Path, transcript: str, speaker_turns: list[dict[str, Any]] | None = None) -> None:
    """Append an OfflineScribe metadata chunk to an existing WAV file."""

    wav_path = Path(path)
    payload = json.dumps(
        {
            "schema": "offlinescribe.synthetic.v1",
            "transcript": transcript,
            "speaker_turns": speaker_turns or [],
        },
        separators=(",", ":"),
    ).encode("utf-8")
    padding = b"\x00" if len(payload) % 2 else b""
    chunk = TRANSCRIPT_CHUNK_ID + struct.pack("<I", len(payload)) + payload + padding

    data = wav_path.read_bytes()
    if len(data) < 8 or data[:4] != b"RIFF":
        raise ValueError(f"{wav_path} is not a RIFF/WAV file")
    new_size = len(data) + len(chunk) - 8
    wav_path.write_bytes(data[:4] + struct.pack("<I", new_size) + data[8:] + chunk)

