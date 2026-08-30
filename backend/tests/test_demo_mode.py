from pathlib import Path

from fastapi.testclient import TestClient

from app.config import clear_settings_cache, get_settings
from app.demo import (
    DEMO_SYNC_UNAVAILABLE,
    DEMO_UPLOAD_REFUSED,
    DEMO_WATERMARK,
    DemoError,
    export_visit_text,
    load_demo_encounter,
)
from app.main import app
from app.models import Note
from app.storage_service import create_visit, init_db, list_visits
from app.sync_service import sync_pending_visits


def _key() -> str:
    return get_settings().local_api_key


def _enable_demo(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_SQLITE_PATH", str(tmp_path / "demo.db"))
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "real.db"))
    clear_settings_cache()
    init_db()


def test_health_reports_demo_mode_off_by_default():
    with TestClient(app) as client:
        body = client.get("/health").json()
    assert body["demo_mode"] is False


def test_audio_upload_rejected_in_demo_mode(monkeypatch, tmp_path):
    _enable_demo(monkeypatch, tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/visits",
            headers={"X-API-Key": _key()},
            files={"audio": ("visit.wav", b"RIFF", "audio/wav")},
        )
    assert response.status_code == 403
    assert response.json()["detail"] == DEMO_UPLOAD_REFUSED


def test_sync_and_dry_run_refuse_in_demo_mode(monkeypatch, tmp_path):
    _enable_demo(monkeypatch, tmp_path)
    with TestClient(app) as client:
        response = client.post("/sync?dry_run=true", headers={"X-API-Key": _key()})
    assert response.status_code == 403
    assert response.json()["detail"] == DEMO_SYNC_UNAVAILABLE
    try:
        sync_pending_visits(dry_run=True)
        raise AssertionError("sync should refuse in demo mode")
    except DemoError as exc:
        assert str(exc) == DEMO_SYNC_UNAVAILABLE


def test_demo_visits_use_prefix_and_separate_database(monkeypatch, tmp_path):
    real_db = tmp_path / "real.db"
    demo_db = tmp_path / "demo.db"
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("SQLITE_PATH", str(real_db))
    monkeypatch.setenv("DEMO_SQLITE_PATH", str(demo_db))
    clear_settings_cache()
    init_db(real_db)
    real_visit = create_visit("real transcript", Note(subjective="real"), db_path=real_db)
    assert not real_visit.id.startswith("DEMO-")
    assert real_visit.watermark is None

    monkeypatch.setenv("DEMO_MODE", "true")
    clear_settings_cache()
    init_db()
    demo_visit = load_demo_encounter("synthetic_clinic_visit_dialogue.txt")
    assert demo_visit.id.startswith("DEMO-")
    assert demo_visit.watermark == DEMO_WATERMARK
    assert all(item.id.startswith("DEMO-") for item in list_visits(demo_db))
    assert all(not item.id.startswith("DEMO-") for item in list_visits(real_db))
    assert real_visit.id not in {item.id for item in list_visits(demo_db)}


def test_demo_export_bakes_in_watermark(monkeypatch, tmp_path):
    _enable_demo(monkeypatch, tmp_path)
    visit = load_demo_encounter("synthetic_clinic_visit_dialogue.txt")
    text = export_visit_text(visit)
    assert text.startswith(DEMO_WATERMARK)
    with TestClient(app) as client:
        response = client.get(
            f"/visits/{visit.id}/export",
            headers={"X-API-Key": _key()},
        )
    assert response.status_code == 200
    assert response.json()["text"].startswith(DEMO_WATERMARK)


def test_unknown_script_rejected_in_demo_mode(monkeypatch, tmp_path):
    _enable_demo(monkeypatch, tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/demo/encounters",
            headers={"X-API-Key": _key()},
            json={"script": "not_a_real_script.txt"},
        )
    assert response.status_code == 403
    assert response.json()["detail"] == DEMO_UPLOAD_REFUSED
