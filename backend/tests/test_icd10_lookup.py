"""ICD-10-CM starter lookup. Codes/descriptions from CMS public files, not LLM memory."""

from app.icd10_lookup import UNMATCHED_CODE, UNMATCHED_DESCRIPTION, load_starter_set, lookup_diagnoses
from app.models import SpeakerTurn, TranscriptResult
from app.note_service import generate_note
from tests.ollama_fakes import patch_ollama


def test_starter_set_matches_cms_j06_9_and_has_no_j40_0():
    codes = {row["code"]: row["description"] for row in load_starter_set()}
    # CMS ICD-10-CM FY 2026 Code Descriptions in Tabular Order:
    # https://www.cms.gov/medicare/coding-billing/icd-10-codes
    assert codes["J06.9"] == "Acute upper respiratory infection, unspecified"
    assert codes["J40"] == "Bronchitis, not specified as acute or chronic"
    assert "J40.0" not in codes
    assert 30 <= len(codes) <= 50


def test_lookup_viral_uri_returns_j06_9_not_bronchitis():
    matched = lookup_diagnoses(["viral upper respiratory infection"])
    assert [item.code for item in matched] == ["J06.9"]
    assert matched[0].description == "Acute upper respiratory infection, unspecified"


def test_lookup_rejects_recalled_icd_codes_and_unknown_phrases():
    recalled = lookup_diagnoses(["J40.0"])
    assert recalled[0].code == UNMATCHED_CODE
    assert recalled[0].description == UNMATCHED_DESCRIPTION

    unknown = lookup_diagnoses(["left otolith mysterious syndrome"])
    assert unknown[0].code == UNMATCHED_CODE


def test_uri_transcript_looks_up_j06_9_even_if_model_recalls_j40_0(
    ollama_mode, monkeypatch
):
    patch_ollama(
        monkeypatch,
        {
            "subjective": "Dry cough and low-grade fever for a week.",
            "objective": "Not documented in visit.",
            "assessment": "Viral upper respiratory infection, not pneumonia.",
            "plan": "Supportive care. No antibiotics today.",
            "likely_diagnoses": ["viral upper respiratory infection"],
            "suggested_icd10": [
                {
                    "code": "J40.0",
                    "description": "Viral upper respiratory infection",
                    "accepted": None,
                }
            ],
            "follow_up": [],
            "citations": {
                "subjective": [{"start_s": 0.0, "end_s": 8.0}],
                "assessment": [{"start_s": 8.0, "end_s": 16.0}],
            },
        },
    )
    transcript = TranscriptResult(
        text=(
            "I've had a dry cough and a low fever for a week. No chest pain. "
            "This fits a viral upper respiratory infection more than pneumonia."
        ),
        segments=[
            SpeakerTurn(
                speaker="patient",
                start_s=0.0,
                end_s=8.0,
                text="I've had a dry cough and a low fever for a week. No chest pain.",
            ),
            SpeakerTurn(
                speaker="provider",
                start_s=8.0,
                end_s=16.0,
                text="This fits a viral upper respiratory infection more than pneumonia.",
            ),
        ],
    )

    note = generate_note(transcript)

    codes = [item.code for item in note.suggested_icd10]
    assert "J06.9" in codes
    assert "J40.0" not in codes
    assert "J40" not in codes
