import pytest

from app.models import Note, ReviewAction
from app.storage_service import (
    StorageError,
    create_visit,
    init_db,
    list_review_audit,
    update_visit_note,
)
from app.sync_service import SKIP_NOT_REVIEWED, sync_pending_visits


def test_update_requires_named_reviewer(tmp_path):
    db_path = tmp_path / "visits.db"
    init_db(db_path)
    visit = create_visit("sample", Note(subjective="draft"), db_path=db_path)
    with pytest.raises(StorageError, match="reviewer id"):
        update_visit_note(visit.id, Note(subjective="edited"), reviewer_id="  ", db_path=db_path)
    stored = update_visit_note(
        visit.id,
        Note(subjective="PHI-NOTE-xyzzy-unique-body"),
        reviewer_id="np-44",
        section_actions=[
            ReviewAction(section="subjective", action="edit"),
            ReviewAction(section="codes", action="accept"),
        ],
        db_path=db_path,
    )
    assert stored is not None
    assert stored.provider_review is not None
    assert stored.provider_review.reviewer_id == "np-44"
    assert stored.provider_review.reviewed_at is not None
    audit = list_review_audit(visit.id, db_path=db_path)
    actions = {row["action"] for row in audit}
    assert {"edit", "accept", "section_diff"} <= actions
    assert all(row["reviewer_id"] == "np-44" for row in audit)
    diffs = [row for row in audit if row["action"] == "section_diff"]
    assert any(row["section"] == "subjective" and row["text_changed"] == 1 for row in diffs)
    assert stored.review_summary is not None
    assert stored.review_summary.startswith("1 of 4 SOAP sections edited")
    assert "reviewed by np-44" in stored.review_summary
    assert "PHI-NOTE-xyzzy-unique-body" not in stored.review_summary


def test_sync_and_dry_run_blocked_without_named_review(tmp_path):
    db_path = tmp_path / "visits.db"
    init_db(db_path)
    create_visit(
        "sample",
        Note(subjective="draft"),
        fhir_patient_id="patient-explicit-test",
        fhir_encounter_id="encounter-explicit-test",
        db_path=db_path,
    )
    result = sync_pending_visits(dry_run=True, db_path=db_path)
    assert result.results[0].error == SKIP_NOT_REVIEWED
