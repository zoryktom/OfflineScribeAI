"""End-to-end offline transcription and SOAP structuring pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from offlinescribe.audio.transcriber import TranscriptionConfig, transcriber_from_config
from offlinescribe.nlp.entities import extract_clinical_entities
from offlinescribe.nlp.soap import parse_soap
from offlinescribe.privacy import NetworkSandbox
from offlinescribe.schema import NOTE_SCHEMA_VERSION, validate_note_schema


def process_audio_to_note(audio_path: str | Path, config: TranscriptionConfig | None = None) -> dict[str, Any]:
    """Run local transcription, SOAP parsing, and entity extraction with network blocked."""

    cfg = config or TranscriptionConfig()
    audio = Path(audio_path)
    warnings: list[str] = []

    with NetworkSandbox("audio transcription") as transcription_sandbox:
        transcriber = transcriber_from_config(cfg)
        transcription = transcriber.transcribe(audio)

    with NetworkSandbox("clinical NLP extraction") as extraction_sandbox:
        soap = parse_soap(transcription.text)
        entities = extract_clinical_entities(transcription.text, soap.section_spans)

    warnings.extend(transcription.warnings)
    note: dict[str, Any] = {
        "schema_version": NOTE_SCHEMA_VERSION,
        "source": {
            "audio_path": str(audio),
            "duration_seconds": transcription.duration_seconds,
        },
        "transcript": {
            "text": transcription.text,
            "segments": [segment.as_dict() for segment in transcription.segments],
        },
        "soap": soap.as_dict(),
        "entities": [entity.as_dict() for entity in entities],
        "audit": {
            "offline_enforced": True,
            "network_attempts": [
                *(attempt.as_dict() for attempt in transcription_sandbox.attempts),
                *(attempt.as_dict() for attempt in extraction_sandbox.attempts),
            ],
            "transcriber_backend": transcription.backend,
            "warnings": warnings,
        },
    }
    validate_note_schema(note)
    return note

