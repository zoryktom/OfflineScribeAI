from datetime import datetime, timedelta, timezone

from app.config import clear_settings_cache
from app.models import Note
from app.storage_service import create_visit, get_visit, init_db, purge_expired_visits


def test_purge_expired_visits_respects_retention_days(tmp_path, monkeypatch):
    db_path = tmp_path / "visits.db"
    init_db(db_path)
    visit = create_visit("sample", Note(subjective="old"), db_path=db_path)

    monkeypatch.setenv("VISIT_RETENTION_DAYS", "7")
    clear_settings_cache()
    removed = purge_expired_visits(
        now=datetime.now(timezone.utc) + timedelta(days=10),
        db_path=db_path,
    )
    assert removed == 1
    assert get_visit(visit.id, db_path=db_path) is None

    monkeypatch.setenv("VISIT_RETENTION_DAYS", "0")
    clear_settings_cache()
