"""Permanently limited synthetic demo surface. Not a path to real visits or charts."""

from __future__ import annotations

from pathlib import Path

from app.config import get_settings
from app.eval_harness import _ENCOUNTER_SCRIPTS, load_encounter_transcript
from app.models import Note, Visit
from app.note_service import generate_note
from app.storage_service import StorageError, create_visit, list_visits

DEMO_WATERMARK = "SYNTHETIC DEMO — NOT A REAL PATIENT — NOT FOR CLINICAL USE"
DEMO_UPLOAD_REFUSED = "Demo mode only supports preloaded synthetic encounters."
DEMO_SYNC_UNAVAILABLE = "unavailable in demo mode"
DEMO_ID_PREFIX = "DEMO-"

WALKTHROUGH_SCRIPT = "synthetic_clinic_visit_dialogue.txt"

SCRIPT_TITLES = {
    "synthetic_clinic_visit_dialogue.txt": "Clinic visit (walkthrough)",
    "synthetic_htn_diabetes_followup_dialogue.txt": "Blood pressure and diabetes follow-up",
    "synthetic_ankle_sprain_dialogue.txt": "Ankle sprain",
    "synthetic_ambiguous_visit_dialogue.txt": "Ambiguous visit",
}


class DemoError(Exception):
    """Demo-mode refusal. Message is safe to show in the UI."""


def require_demo_mode() -> None:
    if not get_settings().demo_mode:
        raise DemoError("That action is only available when DEMO_MODE=true.")


def refuse_if_demo_upload() -> None:
    if get_settings().demo_mode:
        raise DemoError(DEMO_UPLOAD_REFUSED)


def refuse_if_demo_sync() -> None:
    if get_settings().demo_mode:
        raise DemoError(DEMO_SYNC_UNAVAILABLE)


def list_demo_scripts() -> list[dict[str, str]]:
    require_demo_mode()
    return [
        {"script": name, "title": SCRIPT_TITLES.get(name, name)}
        for name in _ENCOUNTER_SCRIPTS
    ]


def allowed_demo_script(script: str) -> str:
    name = Path(script).name
    if name not in _ENCOUNTER_SCRIPTS:
        raise DemoError(DEMO_UPLOAD_REFUSED)
    return name


def load_demo_encounter(script: str) -> Visit:
    """Create a demo visit from a committed synthetic script. No audio upload."""
    require_demo_mode()
    name = allowed_demo_script(script)
    transcript = load_encounter_transcript(name)
    note = generate_note(transcript)
    return create_visit(
        transcript.text,
        note,
        transcript_segments=transcript.segments,
        asr_flags=transcript.asr_flags,
    )


def export_visit_text(visit: Visit) -> str:
    """Plain-text export. Demo visits always include the watermark in the file."""
    from app.ehr.fhir_mapper import format_note_as_plain_text

    body = format_note_as_plain_text(visit.note)
    mark = (visit.watermark or "").strip()
    if get_settings().demo_mode or mark:
        line = mark or DEMO_WATERMARK
        return f"{line}\n\n{body}\n"
    return body


def seed_walkthrough_visit() -> Visit | None:
    """Load the walkthrough script if this demo database has no visits yet."""
    require_demo_mode()
    existing = list_visits()
    if existing:
        return existing[0]
    try:
        return load_demo_encounter(WALKTHROUGH_SCRIPT)
    except StorageError:
        return None
