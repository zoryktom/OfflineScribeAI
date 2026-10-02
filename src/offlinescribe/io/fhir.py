"""FHIR DocumentReference / Composition mapping. Live POST stays off."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from offlinescribe.eval.taxonomy import Encounter, EncounterNote

LIVE_POST_FLAG = "OFFLINESCRIBE_ENABLE_LIVE_FHIR_POST"


def composition(encounter: Encounter, note: EncounterNote) -> dict:
    return {
        "resourceType": "Composition",
        "status": "preliminary",
        "type": {"text": "SOAP note"},
        "title": f"OfflineScribe draft {encounter.encounter_id}",
        "date": datetime.now(timezone.utc).isoformat(),
        "section": [
            {"title": "Subjective", "text": {"div": note.subjective}},
            {"title": "Objective", "text": {"div": note.objective}},
            {"title": "Assessment", "text": {"div": note.assessment}},
            {"title": "Plan", "text": {"div": note.plan}},
        ],
    }


def document_reference(encounter: Encounter, note: EncounterNote) -> dict:
    payload = json.dumps(composition(encounter, note), sort_keys=True)
    return {
        "resourceType": "DocumentReference",
        "status": "current",
        "description": "OfflineScribe research draft. Not for clinical use.",
        "content": [
            {
                "attachment": {
                    "contentType": "application/json",
                    "hash": sha256(payload.encode()).hexdigest(),
                    "data_sha256": sha256(payload.encode()).hexdigest(),
                }
            }
        ],
    }


def write_dry_run(path: Path, encounter: Encounter, note: EncounterNote) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    bundle = {
        "dry_run": True,
        "live_post": False,
        "composition": composition(encounter, note),
        "document_reference": document_reference(encounter, note),
    }
    path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    return path


def live_post_allowed() -> bool:
    return os.environ.get(LIVE_POST_FLAG, "").strip() == "1"


def post_or_refuse(encounter: Encounter, note: EncounterNote) -> dict:
    """Refuse live POST unless the explicit env flag is set. Default is refuse."""
    if not live_post_allowed():
        return {
            "ok": False,
            "refused": True,
            "reason": f"Live FHIR POST is disabled. {LIVE_POST_FLAG} is not set.",
        }
    return {
        "ok": False,
        "refused": True,
        "reason": "Live FHIR write is not implemented in this research package.",
    }
