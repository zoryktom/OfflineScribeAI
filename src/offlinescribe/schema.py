"""Clinical note JSON schema helpers."""

from __future__ import annotations

from typing import Any


NOTE_SCHEMA_VERSION = "1.0"

REQUIRED_TOP_LEVEL_KEYS = {"schema_version", "source", "transcript", "soap", "entities", "audit"}
REQUIRED_SOAP_KEYS = {"subjective", "objective", "assessment", "plan"}


def validate_note_schema(note: dict[str, Any]) -> None:
    missing = REQUIRED_TOP_LEVEL_KEYS - set(note)
    if missing:
        raise ValueError(f"Clinical note is missing top-level keys: {sorted(missing)}")
    if note["schema_version"] != NOTE_SCHEMA_VERSION:
        raise ValueError(f"Unsupported schema_version: {note['schema_version']!r}")
    soap = note.get("soap")
    if not isinstance(soap, dict):
        raise ValueError("Clinical note soap section must be an object")
    missing_soap = REQUIRED_SOAP_KEYS - set(soap)
    if missing_soap:
        raise ValueError(f"Clinical note is missing SOAP keys: {sorted(missing_soap)}")
    if not isinstance(note.get("entities"), list):
        raise ValueError("Clinical note entities must be a list")
    audit = note.get("audit")
    if not isinstance(audit, dict) or audit.get("offline_enforced") is not True:
        raise ValueError("Clinical note audit must assert offline_enforced=true")

