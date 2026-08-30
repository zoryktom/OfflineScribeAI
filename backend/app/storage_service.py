"""Encrypted SQLite persistence for visits (SQLCipher).

Never log transcript or note content. Identifiers and sync_status only.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from sqlcipher3 import dbapi2 as sqlcipher

from app.config import get_settings
from app.models import (
    AsrFlag,
    Note,
    ProviderAttestation,
    ReviewAction,
    SpeakerTurn,
    SyncStatus,
    Visit,
)

logger = logging.getLogger(__name__)

_CREATE_VISITS = """
CREATE TABLE IF NOT EXISTS visits (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    transcript TEXT NOT NULL,
    transcript_segments TEXT NOT NULL DEFAULT '[]',
    note_json TEXT NOT NULL,
    sync_status TEXT NOT NULL,
    fhir_resource_id TEXT,
    reviewer_id TEXT,
    reviewed_at TEXT,
    asr_flags TEXT NOT NULL DEFAULT '[]',
    fhir_patient_id TEXT,
    fhir_encounter_id TEXT,
    last_sync_error TEXT,
    review_summary TEXT,
    watermark TEXT
);
"""

_CREATE_AUDIT = """
CREATE TABLE IF NOT EXISTS review_audit (
    id TEXT PRIMARY KEY,
    visit_id TEXT NOT NULL,
    reviewer_id TEXT NOT NULL,
    action TEXT NOT NULL,
    section TEXT NOT NULL,
    created_at TEXT NOT NULL,
    text_changed INTEGER,
    before_len INTEGER,
    after_len INTEGER,
    delta_chars INTEGER,
    hash_before TEXT,
    hash_after TEXT
);
"""

_SOAP_SECTIONS = ("subjective", "objective", "assessment", "plan")


class StorageError(Exception):
    """Raised when a visit cannot be read or written. Message is safe to show a clinician."""


def _default_db_path() -> Path:
    return get_settings().active_sqlite_path


def _assert_storage_isolation(path: Path, demo_mode: bool) -> None:
    settings = get_settings()
    resolved = path.resolve()
    real_path = settings.sqlite_path.resolve()
    demo_path = settings.demo_sqlite_path.resolve()
    if demo_mode and resolved == real_path:
        raise StorageError(
            "Demo visits cannot be written to the non-demo database."
        )
    if not demo_mode and resolved == demo_path:
        raise StorageError(
            "Non-demo visits cannot be written to the demo database."
        )


def init_db(db_path: Path | None = None) -> Path:
    path = db_path or _default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as connection:
        connection.execute(_CREATE_VISITS)
        connection.execute(_CREATE_AUDIT)
        _ensure_visit_columns(connection)
        _ensure_audit_columns(connection)
        connection.commit()
    return path


def create_visit(
    transcript: str,
    note: Note,
    *,
    transcript_segments: list[SpeakerTurn] | None = None,
    asr_flags: list[AsrFlag] | None = None,
    fhir_patient_id: str | None = None,
    fhir_encounter_id: str | None = None,
    db_path: Path | None = None,
) -> Visit:
    """Persist a visit. Chart ids stay None unless the caller sets them explicitly."""
    settings = get_settings()
    path = db_path or _default_db_path()
    _assert_storage_isolation(path, settings.demo_mode)
    visit_id = f"DEMO-{uuid4()}" if settings.demo_mode else str(uuid4())
    if settings.demo_mode:
        from app.demo import DEMO_WATERMARK

        watermark = DEMO_WATERMARK
    else:
        watermark = None
        if visit_id.startswith("DEMO-"):
            raise StorageError("Non-demo visits cannot use a DEMO- id.")
    visit = Visit(
        id=visit_id,
        timestamp=datetime.now(timezone.utc),
        transcript=transcript,
        transcript_segments=list(transcript_segments or []),
        note=note,
        sync_status=SyncStatus.pending,
        fhir_resource_id=None,
        provider_review=None,
        asr_flags=list(asr_flags or []),
        fhir_patient_id=fhir_patient_id,
        fhir_encounter_id=fhir_encounter_id,
        last_sync_error=None,
        review_summary=None,
        watermark=watermark,
    )
    try:
        with _connect(path) as connection:
            connection.execute(
                """
                INSERT INTO visits (
                    id, timestamp, transcript, transcript_segments, note_json, sync_status,
                    fhir_resource_id, reviewer_id, reviewed_at, asr_flags,
                    fhir_patient_id, fhir_encounter_id, last_sync_error, review_summary,
                    watermark
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    path = db_path or _default_db_path()
    with _connect(path) as connection:
        row = connection.execute(
            "SELECT * FROM visits WHERE id = ?", (visit_id,)
        ).fetchone()
    return _row_to_visit(row) if row else None


def list_visits(db_path: Path | None = None) -> list[Visit]:
    path = db_path or _default_db_path()
    with _connect(path) as connection:
        rows = connection.execute(
            "SELECT * FROM visits ORDER BY timestamp DESC"
        ).fetchall()
    return [_row_to_visit(row) for row in rows]


def list_pending_visits(db_path: Path | None = None) -> list[Visit]:
    path = db_path or _default_db_path()
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
    reviewer_id: str,
    section_actions: list[ReviewAction] | None = None,
    db_path: Path | None = None,
) -> Visit | None:
    reviewer = (reviewer_id or "").strip()
    if not reviewer:
        raise StorageError(
            "A reviewer id is required to confirm a note. "
            "Enter the reviewing provider's id and try again."
        )
    reviewed_at = datetime.now(timezone.utc)
    path = db_path or _default_db_path()
    previous = get_visit(visit_id, db_path=path)
    if previous is None:
        return None
    summary = _build_review_summary(previous.note, note, reviewer, reviewed_at)
    actions = list(section_actions or [ReviewAction(section="note", action="confirm")])
    with _connect(path) as connection:
        cursor = connection.execute(
            """
            UPDATE visits
            SET note_json = ?, reviewer_id = ?, reviewed_at = ?, review_summary = ?
            WHERE id = ?
            """,
            (
                note.model_dump_json(),
                reviewer,
                reviewed_at.isoformat(),
                summary,
                visit_id,
            ),
        )
        if cursor.rowcount == 0:
            connection.commit()
            return None
        _write_audit_rows(
            connection,
            visit_id=visit_id,
            reviewer_id=reviewer,
            actions=actions,
            created_at=reviewed_at,
        )
        _write_section_diffs(
            connection,
            visit_id=visit_id,
            reviewer_id=reviewer,
            before=previous.note,
            after=note,
            created_at=reviewed_at,
        )
        connection.commit()
    logger.info(
        "review_saved visit_id=%s reviewer_id=%s action_count=%s",
        visit_id,
        reviewer,
        len(actions),
    )
    return get_visit(visit_id, db_path=path)


def list_review_audit(visit_id: str, db_path: Path | None = None) -> list[dict[str, object]]:
    path = db_path or _default_db_path()
    with _connect(path) as connection:
        rows = connection.execute(
            """
            SELECT visit_id, reviewer_id, action, section, created_at,
                   text_changed, before_len, after_len, delta_chars,
                   hash_before, hash_after
            FROM review_audit
            WHERE visit_id = ?
            ORDER BY created_at ASC
            """,
            (visit_id,),
        ).fetchall()
    return [_audit_row_to_dict(row) for row in rows]


def purge_expired_visits(
    *,
    now: datetime | None = None,
    db_path: Path | None = None,
) -> int:
    """Delete visits older than visit_retention_days. Returns the number removed."""
    days = get_settings().visit_retention_days
    if days <= 0:
        return 0
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    cutoff = (moment - timedelta(days=days)).isoformat()
    path = db_path or _default_db_path()
    with _connect(path) as connection:
        expired = connection.execute(
            "SELECT id FROM visits WHERE timestamp < ?",
            (cutoff,),
        ).fetchall()
        expired_ids = [row["id"] for row in expired]
        if expired_ids:
            placeholders = ",".join("?" * len(expired_ids))
            connection.execute(
                f"DELETE FROM review_audit WHERE visit_id IN ({placeholders})",
                expired_ids,
            )
        cursor = connection.execute(
            "DELETE FROM visits WHERE timestamp < ?",
            (cutoff,),
        )
        deleted = cursor.rowcount if cursor.rowcount is not None else 0
        connection.commit()
    if deleted:
        logger.info("retention purged_count=%s retention_days=%s", deleted, days)
    return deleted


def mark_synced(
    visit_id: str,
    fhir_resource_id: str,
    db_path: Path | None = None,
) -> Visit | None:
    path = db_path or _default_db_path()
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
    path = db_path or _default_db_path()
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


def _ensure_visit_columns(connection: sqlcipher.Connection) -> None:
    names = {
        row[1] for row in connection.execute("PRAGMA table_info(visits)").fetchall()
    }
    additions = {
        "transcript_segments": "TEXT NOT NULL DEFAULT '[]'",
        "reviewer_id": "TEXT",
        "reviewed_at": "TEXT",
        "asr_flags": "TEXT NOT NULL DEFAULT '[]'",
        "review_summary": "TEXT",
        "watermark": "TEXT",
    }
    for column, spec in additions.items():
        if column not in names:
            connection.execute(f"ALTER TABLE visits ADD COLUMN {column} {spec}")


def _ensure_audit_columns(connection: sqlcipher.Connection) -> None:
    names = {
        row[1] for row in connection.execute("PRAGMA table_info(review_audit)").fetchall()
    }
    additions = {
        "text_changed": "INTEGER",
        "before_len": "INTEGER",
        "after_len": "INTEGER",
        "delta_chars": "INTEGER",
        "hash_before": "TEXT",
        "hash_after": "TEXT",
    }
    for column, spec in additions.items():
        if column not in names:
            connection.execute(f"ALTER TABLE review_audit ADD COLUMN {column} {spec}")


def _content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _codes_fingerprint(note: Note) -> str:
    parts = [f"{item.code}:{item.accepted}" for item in note.suggested_icd10]
    return "|".join(parts)


def _build_review_summary(
    before: Note, after: Note, reviewer_id: str, reviewed_at: datetime
) -> str:
    soap_edited = sum(
        1 for name in _SOAP_SECTIONS if getattr(before, name) != getattr(after, name)
    )
    icd_rejected = sum(1 for item in after.suggested_icd10 if item.accepted is False)
    code_word = "code" if icd_rejected == 1 else "codes"
    return (
        f"{soap_edited} of {len(_SOAP_SECTIONS)} SOAP sections edited, "
        f"{icd_rejected} ICD {code_word} rejected, "
        f"reviewed by {reviewer_id} at {reviewed_at.isoformat()}"
    )


def _write_section_diffs(
    connection: sqlcipher.Connection,
    *,
    visit_id: str,
    reviewer_id: str,
    before: Note,
    after: Note,
    created_at: datetime,
) -> None:
    for name in _SOAP_SECTIONS:
        old_text = getattr(before, name) or ""
        new_text = getattr(after, name) or ""
        _insert_audit(
            connection,
            visit_id=visit_id,
            reviewer_id=reviewer_id,
            action="section_diff",
            section=name,
            created_at=created_at,
            text_changed=old_text != new_text,
            before_len=len(old_text),
            after_len=len(new_text),
            hash_before=_content_hash(old_text),
            hash_after=_content_hash(new_text),
        )
    old_codes = _codes_fingerprint(before)
    new_codes = _codes_fingerprint(after)
    _insert_audit(
        connection,
        visit_id=visit_id,
        reviewer_id=reviewer_id,
        action="section_diff",
        section="codes",
        created_at=created_at,
        text_changed=old_codes != new_codes,
        before_len=len(old_codes),
        after_len=len(new_codes),
        hash_before=_content_hash(old_codes),
        hash_after=_content_hash(new_codes),
    )


def _insert_audit(
    connection: sqlcipher.Connection,
    *,
    visit_id: str,
    reviewer_id: str,
    action: str,
    section: str,
    created_at: datetime,
    text_changed: bool | None = None,
    before_len: int | None = None,
    after_len: int | None = None,
    hash_before: str | None = None,
    hash_after: str | None = None,
) -> None:
    changed = None if text_changed is None else int(bool(text_changed))
    delta = None
    if before_len is not None and after_len is not None:
        delta = after_len - before_len
    connection.execute(
        """
        INSERT INTO review_audit (
            id, visit_id, reviewer_id, action, section, created_at,
            text_changed, before_len, after_len, delta_chars, hash_before, hash_after
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid4()),
            visit_id,
            reviewer_id,
            action,
            section,
            created_at.isoformat(),
            changed,
            before_len,
            after_len,
            delta,
            hash_before,
            hash_after,
        ),
    )
    logger.info(
        "review_action visit_id=%s section=%s action=%s reviewer_id=%s text_changed=%s",
        visit_id,
        section,
        action,
        reviewer_id,
        changed,
    )


def _audit_row_to_dict(row: sqlcipher.Row) -> dict[str, object]:
    keys = row.keys()
    return {
        "visit_id": row["visit_id"],
        "reviewer_id": row["reviewer_id"],
        "action": row["action"],
        "section": row["section"],
        "created_at": row["created_at"],
        "text_changed": row["text_changed"] if "text_changed" in keys else None,
        "before_len": row["before_len"] if "before_len" in keys else None,
        "after_len": row["after_len"] if "after_len" in keys else None,
        "delta_chars": row["delta_chars"] if "delta_chars" in keys else None,
        "hash_before": row["hash_before"] if "hash_before" in keys else None,
        "hash_after": row["hash_after"] if "hash_after" in keys else None,
    }


def _segments_json(segments: list[SpeakerTurn]) -> str:
    return json.dumps([segment.model_dump() for segment in segments])


def _segments_from_row(row: sqlcipher.Row) -> list[SpeakerTurn]:
    keys = row.keys()
    raw = row["transcript_segments"] if "transcript_segments" in keys else "[]"
    if not raw:
        return []
    parsed = json.loads(raw)
    return [SpeakerTurn.model_validate(item) for item in parsed]


def _flags_from_row(row: sqlcipher.Row) -> list[AsrFlag]:
    keys = row.keys()
    raw = row["asr_flags"] if "asr_flags" in keys else "[]"
    if not raw:
        return []
    parsed = json.loads(raw)
    return [AsrFlag.model_validate(item) for item in parsed]


def _review_from_row(row: sqlcipher.Row) -> ProviderAttestation | None:
    keys = row.keys()
    reviewer = row["reviewer_id"] if "reviewer_id" in keys else None
    when = row["reviewed_at"] if "reviewed_at" in keys else None
    if not reviewer or not when:
        return None
    return ProviderAttestation(
        reviewer_id=str(reviewer),
        reviewed_at=datetime.fromisoformat(when),
    )


def _write_audit_rows(
    connection: sqlcipher.Connection,
    *,
    visit_id: str,
    reviewer_id: str,
    actions: list[ReviewAction],
    created_at: datetime,
) -> None:
    for item in actions:
        section = (item.section or "unknown").strip() or "unknown"
        action = (item.action or "confirm").strip() or "confirm"
        _insert_audit(
            connection,
            visit_id=visit_id,
            reviewer_id=reviewer_id,
            action=action,
            section=section,
            created_at=created_at,
        )


def _visit_row(visit: Visit) -> tuple:
    review = visit.provider_review
    return (
        visit.id,
        visit.timestamp.isoformat(),
        visit.transcript,
        _segments_json(visit.transcript_segments),
        visit.note.model_dump_json(),
        visit.sync_status.value,
        visit.fhir_resource_id,
        review.reviewer_id if review else None,
        review.reviewed_at.isoformat() if review else None,
        json.dumps([flag.model_dump() for flag in visit.asr_flags]),
        visit.fhir_patient_id,
        visit.fhir_encounter_id,
        visit.last_sync_error,
        visit.review_summary,
        visit.watermark,
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
        provider_review=_review_from_row(row),
        asr_flags=_flags_from_row(row),
        fhir_patient_id=row["fhir_patient_id"],
        fhir_encounter_id=row["fhir_encounter_id"],
        last_sync_error=row["last_sync_error"],
        review_summary=row["review_summary"] if "review_summary" in row.keys() else None,
        watermark=row["watermark"] if "watermark" in row.keys() else None,
    )
