from app.models import Note, SpeakerTurn, SyncStatus, SuggestedIcd10
from app.storage_service import (
    create_visit,
    get_visit,
    init_db,
    list_pending_visits,
    mark_synced,
    update_visit_note,
)


def test_create_and_fetch_visit(tmp_path):
    db_path = tmp_path / "visits.db"
    init_db(db_path)
    note = Note(
        subjective="Cough for three days.",
        objective="Not documented in visit.",
        assessment="Possible viral illness.",
        plan="Supportive care.",
        suggested_icd10=[
            SuggestedIcd10(code="R05.9", description="Cough, unspecified")
        ],
    )

    created = create_visit(
        "sample transcript",
        note,
        transcript_segments=[
            SpeakerTurn(speaker="unknown", start_s=0.0, end_s=1.2, text="sample transcript")
        ],
        db_path=db_path,
    )
    fetched = get_visit(created.id, db_path=db_path)

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.transcript == "sample transcript"
    assert len(fetched.transcript_segments) == 1
    assert fetched.transcript_segments[0].start_s == 0.0
    assert fetched.transcript_segments[0].end_s == 1.2
    assert fetched.transcript_segments[0].text == "sample transcript"
    assert fetched.transcript_segments[0].speaker == "unknown"
    assert fetched.note.subjective == "Cough for three days."
    assert fetched.sync_status is SyncStatus.pending
    assert fetched.provider_review is None
    assert fetched.is_reviewed() is False
    assert fetched.fhir_resource_id is None
    assert fetched.fhir_patient_id is None
    assert fetched.fhir_encounter_id is None


def test_update_note_and_mark_synced(tmp_path):
    db_path = tmp_path / "visits.db"
    init_db(db_path)
    visit = create_visit("sample transcript", Note(subjective="original"), db_path=db_path)

    updated = update_visit_note(
        visit.id,
        Note(subjective="edited by provider"),
        reviewer_id="provider-17",
        db_path=db_path,
    )
    assert updated is not None
    assert updated.note.subjective == "edited by provider"
    assert updated.is_reviewed() is True
    assert updated.provider_review is not None
    assert updated.provider_review.reviewer_id == "provider-17"

    pending = list_pending_visits(db_path=db_path)
    assert [item.id for item in pending] == [visit.id]

    synced = mark_synced(visit.id, "DocumentReference/test-id", db_path=db_path)
    assert synced is not None
    assert synced.sync_status is SyncStatus.synced
    assert synced.fhir_resource_id == "DocumentReference/test-id"
    assert list_pending_visits(db_path=db_path) == []


def test_database_file_bytes_are_not_plaintext_sql(tmp_path):
    db_path = tmp_path / "visits.db"
    init_db(db_path)
    marker = "UNIQUE-TRANSCRIPT-MUST-NOT-APPEAR-IN-RAW-BYTES"
    create_visit(marker, Note(subjective="plaintext-note-body"), db_path=db_path)

    raw = db_path.read_bytes()
    assert not raw.startswith(b"SQLite format 3")
    assert marker.encode("utf-8") not in raw
    assert b"plaintext-note-body" not in raw
    assert b"CREATE TABLE" not in raw
    assert b"UNIQUE-TRANSCRIPT" not in raw
