import io
import logging
from pathlib import Path

from app.models import Note
from app.storage_service import create_visit, init_db, update_visit_note
from app.sync_service import sync_pending_visits


def test_loggers_never_emit_transcript_or_note_body(tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    db_path = tmp_path / "visits.db"
    init_db(db_path)
    marker = "PHI-MARKER-TRANSCRIPT-xyzzynotforlogs"
    note_marker = "PHI-MARKER-NOTE-body-notforlogs"
    visit = create_visit(
        marker,
        Note(subjective=note_marker),
        fhir_patient_id="patient-explicit-test",
        fhir_encounter_id="encounter-explicit-test",
        db_path=db_path,
    )
    update_visit_note(visit.id, Note(subjective=note_marker), db_path=db_path)
    sync_pending_visits(dry_run=True, output=io.StringIO(), db_path=db_path)

    recorded = caplog.text
    assert marker not in recorded
    assert note_marker not in recorded
    assert "PHI-MARKER" not in recorded


def test_logger_call_sites_do_not_reference_phi_payloads():
    root = Path(__file__).resolve().parents[1] / "app"
    forbidden = (
        "transcript",
        "note_json",
        "note.subjective",
        "note.objective",
        "resource body",
    )
    violations = []
    for path in root.rglob("*.py"):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if not stripped.startswith("logger."):
                continue
            lower = stripped.lower()
            for token in forbidden:
                if token in lower:
                    violations.append(f"{path}:{line_no}: {stripped}")
    assert violations == []
