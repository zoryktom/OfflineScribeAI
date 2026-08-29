import json
import os
import re
from pathlib import Path
from urllib.error import URLError

import pytest

from app.models import Note, SpeakerTurn, TranscriptResult
from app.note_service import NoteGenerationError, generate_note
from tests.ollama_fakes import patch_ollama

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DIALOGUE = _REPO_ROOT / "audio_samples" / "synthetic_clinic_visit_dialogue.txt"

# Exact Assessment text from the llama3:8b validation run that invented
# medication-control status the transcript never stated.
_PRIOR_FABRICATED_ASSESSMENT = (
    "The patient has a viral upper respiratory infection, likely a viral URI. "
    "No pneumonia at this time. Lisinopril and metformin medications are well "
    "controlled. Astatin (atorvastatin) is being taken as directed."
)
_FABRICATED_CONTROL = re.compile(r"well[- ]controlled", re.IGNORECASE)


def _dialogue_transcript() -> TranscriptResult:
    segments: list[SpeakerTurn] = []
    cursor = 0.0
    spoken: list[str] = []
    for line in _DIALOGUE.read_text(encoding="utf-8").splitlines():
        if not (line.startswith("PROVIDER:") or line.startswith("PATIENT:")):
            continue
        role, body = line.split(":", 1)
        text = body.strip()
        speaker = "provider" if role == "PROVIDER" else "patient"
        duration = max(2.0, len(text.split()) * 0.35)
        segments.append(
            SpeakerTurn(speaker=speaker, start_s=cursor, end_s=cursor + duration, text=text)
        )
        cursor += duration
        spoken.append(text)
    return TranscriptResult(text=" ".join(spoken), segments=segments)


def test_generate_note_stub_returns_soap_and_codes():
    note = generate_note("Patient reports a cough for three days.")

    assert isinstance(note, Note)
    assert note.subjective
    assert note.objective
    assert note.assessment
    assert note.plan
    assert note.suggested_icd10
    assert note.suggested_icd10[0].code
    assert note.follow_up
    assert note.subjective_grounding.sources
    assert note.subjective_grounding.sources[0].text
    assert note.subjective_grounding.directly_stated is True


def test_generate_note_empty_transcript_raises():
    with pytest.raises(NoteGenerationError, match="empty"):
        generate_note("   ")


def test_ollama_unreachable_is_actionable(ollama_mode, monkeypatch):
    def boom(*_args, **_kwargs):
        raise URLError("connection refused")

    monkeypatch.setattr("app.note_service.urlopen", boom)
    with pytest.raises(NoteGenerationError, match="Ollama is not running"):
        generate_note("Patient reports a cough.")


def test_ollama_path_sends_transcript_and_segments(ollama_mode, monkeypatch):
    captured: dict[str, object] = {}
    note_payload = {
        "subjective": "Cough for one week.",
        "objective": "Not documented in visit.",
        "assessment": "Viral upper respiratory infection.",
        "plan": "Supportive care.",
        "likely_diagnoses": ["cough"],
        "suggested_icd10": [
            {"code": "J40.0", "description": "should be ignored", "accepted": None}
        ],
        "follow_up": [{"text": "Return if worse", "timeframe": "48 hours"}],
        "citations": {
            "subjective": [{"start_s": 0.0, "end_s": 2.4}],
            "objective": [],
            "assessment": [{"start_s": 0.0, "end_s": 2.4}],
            "plan": [],
        },
    }
    patch_ollama(monkeypatch, note_payload, captured)

    result = TranscriptResult(
        text="Patient reports a cough for one week and takes lisinopril ten milligrams daily.",
        segments=[
            SpeakerTurn(
                speaker="unknown",
                start_s=0.0,
                end_s=2.4,
                text="Patient reports a cough for one week.",
            ),
            SpeakerTurn(
                speaker="unknown",
                start_s=2.4,
                end_s=5.0,
                text="Patient takes lisinopril ten milligrams daily.",
            ),
        ],
    )
    note = generate_note(result)

    assert note.subjective == "Cough for one week."
    assert note.suggested_icd10[0].code == "R05.9"
    body = captured["body"]
    assert isinstance(body, dict)
    prompt = body["prompt"]
    assert "lisinopril ten milligrams" in prompt
    assert "Timestamped segments:" in prompt
    assert "[0 |" in prompt
    assert "0.0-2.4s" in prompt
    assert body["format"] == "json"
    assert body["stream"] is False
    assert body["options"]["temperature"] == 0.2
    assert "Do not emit ICD-10 codes" in body["system"]


def test_known_sample_assessment_labels_fabricated_medication_control(
    ollama_mode, monkeypatch
):
    """Grounding must not delete Assessment text the model wrote.

    The prior llama3:8b run claimed lisinopril/metformin were 'well controlled'.
    That phrase is not in the dialogue. Keep the sentence visible and mark the
    section as not directly stated rather than wiping Assessment.
    """
    transcript = _dialogue_transcript()
    assert "well controlled" not in transcript.text.lower()
    patch_ollama(
        monkeypatch,
        {
            "subjective": "Cough for about a week with low-grade fever.",
            "objective": "BP 138/86.",
            "assessment": _PRIOR_FABRICATED_ASSESSMENT,
            "plan": "Continue albuterol as needed. Rest and fluids.",
            "likely_diagnoses": ["viral upper respiratory infection"],
            "follow_up": [{"text": "Follow up in two weeks", "timeframe": "2 weeks"}],
            "citations": {
                "assessment": [{"start_s": 0.0, "end_s": 400.0}],
            },
        },
    )

    note = generate_note(transcript)

    assert note.assessment.strip()
    assert note.assessment != "Not documented in visit"
    assert "viral" in note.assessment.lower()
    assert "pneumonia" in note.assessment.lower()
    assert _FABRICATED_CONTROL.search(note.assessment)


def _ollama_has_configured_model() -> bool:
    from urllib.request import urlopen

    from app.config import get_settings
    from app.note_service import _model_is_pulled

    try:
        with urlopen("http://127.0.0.1:11434/api/tags", timeout=1) as response:
            payload = json.loads(response.read().decode("utf-8"))
        names = [model.get("name", "") for model in payload.get("models", [])]
        return _model_is_pulled(get_settings().ollama_model, names)
    except Exception:
        return False


@pytest.mark.skipif(
    os.environ.get("RUN_OLLAMA_LIVE") != "1" or not _ollama_has_configured_model(),
    reason="Set RUN_OLLAMA_LIVE=1 with Ollama running and OLLAMA_MODEL pulled",
)
def test_live_ollama_returns_structured_note(ollama_mode):
    note = generate_note("Patient reports a dry cough for three days and a low fever.")
    assert isinstance(note, Note)
    assert note.subjective.strip()
    assert note.assessment.strip()
