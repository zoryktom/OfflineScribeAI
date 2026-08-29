import io
from unittest.mock import MagicMock

from app.models import Note
from app.storage_service import create_visit, get_visit, init_db, update_visit_note
from app.sync_service import (
    DRY_RUN_PHI_WARNING,
    SKIP_MISSING_CHART,
    SKIP_NOT_REVIEWED,
    check_connectivity,
    sync_pending_visits,
)


def test_sync_skips_visit_without_patient_encounter_link(tmp_path):
    db_path = tmp_path / "visits.db"
    init_db(db_path)
    visit = create_visit("sample transcript", Note(subjective="cough"), db_path=db_path)
    assert visit.fhir_patient_id is None
    assert visit.fhir_encounter_id is None

    client = MagicMock()
    output = io.StringIO()
    result = sync_pending_visits(
        dry_run=True,
        output=output,
        db_path=db_path,
        client=client,
    )

    assert len(result.results) == 1
    assert result.results[0].visit_id == visit.id
    assert result.results[0].error == SKIP_MISSING_CHART
    assert result.results[0].sync_status.value == "pending"
    client.post_resource.assert_not_called()
    assert "DocumentReference" not in output.getvalue()

    stored = get_visit(visit.id, db_path=db_path)
    assert stored is not None
    assert stored.last_sync_error is None
    assert stored.sync_status.value == "pending"


def test_sync_skips_unreviewed_visit_even_in_dry_run(tmp_path, monkeypatch):
    db_path = tmp_path / "visits.db"
    init_db(db_path)
    visit = create_visit(
        "sample transcript",
        Note(subjective="cough"),
        fhir_patient_id="patient-explicit-test",
        fhir_encounter_id="encounter-explicit-test",
        db_path=db_path,
    )
    assert visit.edited_by_provider is False

    client = MagicMock()
    mapper = MagicMock()
    monkeypatch.setattr("app.sync_service.visit_to_document_reference", mapper)

    result = sync_pending_visits(
        dry_run=True,
        output=io.StringIO(),
        db_path=db_path,
        client=client,
    )

    assert len(result.results) == 1
    assert result.results[0].error == SKIP_NOT_REVIEWED
    assert result.results[0].sync_status.value == "pending"
    client.post_resource.assert_not_called()
    client.get_access_token.assert_not_called()
    mapper.assert_not_called()

    stored = get_visit(visit.id, db_path=db_path)
    assert stored is not None
    assert stored.last_sync_error is None


def test_sync_dry_run_maps_reviewed_linked_visit(tmp_path):
    db_path = tmp_path / "visits.db"
    init_db(db_path)
    visit = create_visit(
        "sample transcript",
        Note(subjective="cough"),
        fhir_patient_id="patient-explicit-test",
        fhir_encounter_id="encounter-explicit-test",
        db_path=db_path,
    )
    update_visit_note(visit.id, Note(subjective="reviewed"), db_path=db_path)

    client = MagicMock()
    output = io.StringIO()
    result = sync_pending_visits(
        dry_run=True,
        output=output,
        db_path=db_path,
        client=client,
    )

    assert result.results[0].error is None
    assert result.results[0].dry_run is True
    client.post_resource.assert_not_called()
    assert '"resourceType": "DocumentReference"' in output.getvalue()
    assert DRY_RUN_PHI_WARNING in output.getvalue()


def test_connectivity_check_uses_configured_fhir_base_url(monkeypatch):
    seen: dict[str, str] = {}

    def fake_get(url, **_kwargs):
        seen["url"] = url

        class _Response:
            status_code = 404

        return _Response()

    monkeypatch.setattr("app.sync_service.httpx.get", fake_get)
    assert check_connectivity() is True
    assert seen["url"].startswith("https://fhir-ehr-code.cerner.com/")
    assert "example.com" not in seen["url"]
