from pathlib import Path

from fastapi.testclient import TestClient

from app.asr_service import AsrError
from app.config import get_settings
from app.main import app
from app.models import SpeakerTurn, TranscriptResult


def _key() -> str:
    return get_settings().local_api_key


def test_health_does_not_require_api_key():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_visits_without_api_key_is_unauthorized():
    with TestClient(app) as client:
        response = client.get("/visits")
    assert response.status_code == 401


def test_visits_with_api_key_succeeds():
    with TestClient(app) as client:
        response = client.get("/visits", headers={"X-API-Key": _key()})
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_docs_and_redoc_are_disabled():
    with TestClient(app) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404


def test_temp_audio_is_removed_when_asr_raises(monkeypatch):
    captured: list[str] = []
    original_named_temporary_file = __import__("tempfile").NamedTemporaryFile

    class TrackingTemp:
        def __init__(self, *args, **kwargs):
            kwargs["delete"] = False
            self._handle = original_named_temporary_file(*args, **kwargs)
            captured.append(self._handle.name)

        def __enter__(self):
            return self._handle

        def __exit__(self, *args):
            return self._handle.__exit__(*args)

    monkeypatch.setattr("app.main.tempfile.NamedTemporaryFile", TrackingTemp)
    monkeypatch.setattr(
        "app.main.transcribe_audio",
        lambda _path: (_ for _ in ()).throw(AsrError("simulated asr failure")),
    )

    with TestClient(app) as client:
        response = client.post(
            "/visits",
            headers={"X-API-Key": _key()},
            files={"audio": ("visit.wav", b"RIFF", "audio/wav")},
        )

    assert response.status_code == 422
    assert captured
    assert not Path(captured[0]).exists()


def test_wrong_mime_upload_is_rejected():
    with TestClient(app) as client:
        response = client.post(
            "/visits",
            headers={"X-API-Key": _key()},
            files={"audio": ("notes.txt", b"this is not audio", "text/plain")},
        )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "supported audio format" in detail.lower() or "not recognized as audio" in detail.lower()


def test_oversized_upload_is_rejected(monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_bytes", 16)
    with TestClient(app) as client:
        response = client.post(
            "/visits",
            headers={"X-API-Key": _key()},
            files={"audio": ("visit.wav", b"RIFF" + b"x" * 64, "audio/wav")},
        )
    assert response.status_code == 413
    assert "upload limit" in response.json()["detail"].lower()


def test_create_visit_returns_persisted_segments(monkeypatch):
    monkeypatch.setattr(
        "app.main.transcribe_audio",
        lambda _path: TranscriptResult(
            text="hello there",
            segments=[
                SpeakerTurn(
                    speaker="unknown",
                    start_s=0.0,
                    end_s=1.4,
                    text="hello there",
                )
            ],
        ),
    )
    with TestClient(app) as client:
        response = client.post(
            "/visits",
            headers={"X-API-Key": _key()},
            files={"audio": ("visit.wav", b"RIFF", "audio/wav")},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == "hello there"
    assert body["transcript_segments"][0]["text"] == "hello there"
    assert body["transcript_segments"][0]["start_s"] == 0.0
    assert body["transcript_segments"][0]["end_s"] == 1.4
    assert body["transcript_segments"][0]["speaker"] == "unknown"
    grounding = body["note"]["subjective_grounding"]
    assert grounding["sources"]
    assert grounding["sources"][0]["text"]
    assert grounding["directly_stated"] is True
    assert body["provider_review"] is None
    assert body["asr_flags"] == []


def test_patch_requires_named_reviewer_and_records_attestation(monkeypatch):
    monkeypatch.setattr(
        "app.main.transcribe_audio",
        lambda _path: TranscriptResult(
            text="hello there",
            segments=[
                SpeakerTurn(
                    speaker="unknown",
                    start_s=0.0,
                    end_s=1.4,
                    text="hello there",
                )
            ],
        ),
    )
    with TestClient(app) as client:
        created = client.post(
            "/visits",
            headers={"X-API-Key": _key()},
            files={"audio": ("visit.wav", b"RIFF", "audio/wav")},
        )
        assert created.status_code == 200
        visit_id = created.json()["id"]
        note = created.json()["note"]

        missing = client.patch(
            f"/visits/{visit_id}",
            headers={"X-API-Key": _key()},
            json={"note": note},
        )
        assert missing.status_code == 422

        blank = client.patch(
            f"/visits/{visit_id}",
            headers={"X-API-Key": _key()},
            json={"note": note, "reviewer_id": "   "},
        )
        assert blank.status_code == 422

        saved = client.patch(
            f"/visits/{visit_id}",
            headers={"X-API-Key": _key()},
            json={
                "note": note,
                "reviewer_id": "np-44",
                "section_actions": [{"section": "subjective", "action": "confirm"}],
            },
        )
        assert saved.status_code == 200
        body = saved.json()
        assert body["provider_review"]["reviewer_id"] == "np-44"
        assert body["provider_review"]["reviewed_at"]
