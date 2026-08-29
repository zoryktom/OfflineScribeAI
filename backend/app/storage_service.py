"""Encrypted SQLite persistence for visits (SQLCipher).

Never log transcript or note content. Identifiers and sync_status only.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlcipher3 import dbapi2 as sqlcipher

from app.config import get_settings
from app.models import Note, SpeakerTurn, SyncStatus, Visit

_CREATE_VISITS = """
CREATE TABLE IF NOT EXISTS visits (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    transcript TEXT NOT NULL,
    transcript_segments TEXT NOT NULL DEFAULT '[]',
    note_json TEXT NOT NULL,
    sync_status TEXT NOT NULL,
    fhir_resource_id TEXT,
    edited_by_provider INTEGER NOT NULL DEFAULT 0,
    fhir_patient_id TEXT,
    fhir_encounter_id TEXT,
    last_sync_error TEXT
);
"""


class StorageError(Exception):
    """Raised when a visit cannot be read or written. Message is safe to show a clinician."""


def init_db(db_path: Path | None = None) -> Path:
    path = db_path or get_settings().sqlite_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as connection:
        connection.execute(_CREATE_VISITS)
        _ensure_transcript_segments_column(connection)
        connection.commit()
    return path


def create_visit(
    transcript: str,
    note: Note,
    *,
    transcript_segments: list[SpeakerTurn] | None = None,
    fhir_patient_id: str | None = None,
    fhir_encounter_id: str | None = None,
    db_path: Path | None = None,
) -> Visit:
    """Persist a visit. Chart ids stay None unless the caller sets them explicitly."""
    visit = Visit(
        id=str(uuid4()),
        timestamp=datetime.now(timezone.utc),
        transcript=transcript,
        transcript_segments=list(transcript_segments or []),
        note=note,
        sync_status=SyncStatus.pending,
        fhir_resource_id=None,
        edited_by_provider=False,
        fhir_patient_id=fhir_patient_id,
        fhir_encounter_id=fhir_encounter_id,
        last_sync_error=None,
    )
    path = db_path or get_settings().sqlite_path
    try:
        with _connect(path) as connection:
            connection.execute(
                """
                INSERT INTO visits (
                    id, timestamp, transcript, transcript_segments, note_json, sync_status,
                    fhir_resource_id, edited_by_provider, fhir_patient_id,
                    fhir_encounter_id, last_sync_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _visit_row(visit),
            )
            connection.commit()
    except sqlcipher.Error as exc:
        raise StorageError(
            "The visit could not be saved to the local database. "
            "Confirm the clinic computer has disk space, then try again."
        ) from exc
    return visit


def get_visit(visit_id: str, db_path: Path | None = None) -> Visit | None:
    path = db_path or get_settings().sqlite_path
    with _connect(path) as connection:
        row = connection.execute(
            "SELECT * FROM visits WHERE id = ?", (visit_id,)
        ).fetchone()
    return _row_to_visit(row) if row else None


def list_visits(db_path: Path | None = None) -> list[Visit]:
    path = db_path or get_settings().sqlite_path
    with _connect(path) as connection:
        rows = connection.execute(
            "SELECT * FROM visits ORDER BY timestamp DESC"
        ).fetchall()
    return [_row_to_visit(row) for row in rows]


def list_pending_visits(db_path: Path | None = None) -> list[Visit]:
    path = db_path or get_settings().sqlite_path
    with _connect(path) as connection:
        rows = connection.execute(
            "SELECT * FROM visits WHERE sync_status = ? ORDER BY timestamp ASC",
            (SyncStatus.pending.value,),
        ).fetchall()
    return [_row_to_visit(row) for row in rows]


def update_visit_note(
    visit_id: str,
    note: Note,
    *,
    edited_by_provider: bool = True,
    db_path: Path | None = None,
) -> Visit | None:
    path = db_path or get_settings().sqlite_path
    with _connect(path) as connection:
        cursor = connection.execute(
            """
            UPDATE visits
            SET note_json = ?, edited_by_provider = ?
            WHERE id = ?
            """,
            (
                note.model_dump_json(),
                1 if edited_by_provider else 0,
                visit_id,
            ),
        )
        connection.commit()
        if cursor.rowcount == 0:
            return None
    return get_visit(visit_id, db_path=path)


def mark_synced(
    visit_id: str,
    fhir_resource_id: str,
    db_path: Path | None = None,
) -> Visit | None:
    path = db_path or get_settings().sqlite_path
    with _connect(path) as connection:
        connection.execute(
            """
            UPDATE visits
            SET sync_status = ?, fhir_resource_id = ?, last_sync_error = NULL
            WHERE id = ?
            """,
            (SyncStatus.synced.value, fhir_resource_id, visit_id),
        )
        connection.commit()
    return get_visit(visit_id, db_path=path)


def mark_sync_failed(
    visit_id: str,
    error_message: str,
    db_path: Path | None = None,
) -> Visit | None:
    """Record a sync failure but leave the visit pending so it can be retried."""
    path = db_path or get_settings().sqlite_path
    with _connect(path) as connection:
        connection.execute(
            """
            UPDATE visits
            SET last_sync_error = ?
            WHERE id = ?
            """,
            (error_message, visit_id),
        )
        connection.commit()
    return get_visit(visit_id, db_path=path)


def _sqlcipher_key() -> str:
    key = get_settings().sqlcipher_key
    if not key.strip():
        raise StorageError(
            "The local database passphrase is missing. Add SQLCIPHER_KEY to "
            "backend/.env (copy from .env.example), then restart the app."
        )
    return key


def _pragma_string_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _connect(path: Path) -> sqlcipher.Connection:
    """Open an SQLCipher database. Key comes from SQLCIPHER_KEY in .env only."""
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlcipher.connect(str(path))
    connection.row_factory = sqlcipher.Row
    try:
        connection.execute(f"PRAGMA key = {_pragma_string_literal(_sqlcipher_key())}")
        connection.execute("SELECT count(*) FROM sqlite_master")
    except sqlcipher.Error as exc:
        connection.close()
        raise StorageError(
            "Could not unlock the local visit database. Confirm SQLCIPHER_KEY "
            "in backend/.env matches the key used when this file was created. "
            "Plain SQLite files cannot be opened after this change — delete "
            "backend/data/offline_scribe.db and let the app recreate it."
        ) from exc
    return connection


def _ensure_transcript_segments_column(connection: sqlcipher.Connection) -> None:
    names = {
        row[1] for row in connection.execute("PRAGMA table_info(visits)").fetchall()
    }
    if "transcript_segments" not in names:
        connection.execute(
            "ALTER TABLE visits ADD COLUMN transcript_segments TEXT NOT NULL DEFAULT '[]'"
        )


def _segments_json(segments: list[SpeakerTurn]) -> str:
    return json.dumps([segment.model_dump() for segment in segments])


def _segments_from_row(row: sqlcipher.Row) -> list[SpeakerTurn]:
    keys = row.keys()
    raw = row["transcript_segments"] if "transcript_segments" in keys else "[]"
    if not raw:
        return []
    parsed = json.loads(raw)
    return [SpeakerTurn.model_validate(item) for item in parsed]


def _visit_row(visit: Visit) -> tuple:
    return (
        visit.id,
        visit.timestamp.isoformat(),
        visit.transcript,
        _segments_json(visit.transcript_segments),
        visit.note.model_dump_json(),
        visit.sync_status.value,
        visit.fhir_resource_id,
        1 if visit.edited_by_provider else 0,
        visit.fhir_patient_id,
        visit.fhir_encounter_id,
        visit.last_sync_error,
    )


def _row_to_visit(row: sqlcipher.Row) -> Visit:
    return Visit(
        id=row["id"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        transcript=row["transcript"],
        transcript_segments=_segments_from_row(row),
        note=Note.model_validate(json.loads(row["note_json"])),
        sync_status=SyncStatus(row["sync_status"]),
        fhir_resource_id=row["fhir_resource_id"],
        edited_by_provider=bool(row["edited_by_provider"]),
        fhir_patient_id=row["fhir_patient_id"],
        fhir_encounter_id=row["fhir_encounter_id"],
        last_sync_error=row["last_sync_error"],
    )
