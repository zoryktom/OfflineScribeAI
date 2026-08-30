from app.models import SpeakerTurn, TranscriptResult
from app.negation_check import (
    flag_negation_assertions,
    sentence_needs_classification,
)
from app.note_service import generate_note
from tests.ollama_fakes import patch_ollama


def test_prefilter_includes_claim_language_outside_symptom_lexicon():
    assert sentence_needs_classification("The patient has tinnitus in both ears.")
    assert not sentence_needs_classification("Not documented in visit.")
    assert not sentence_needs_classification("Follow up tomorrow.")


def test_flag_asserted_fever_when_source_only_asked():
    flags = flag_negation_assertions(
        {
            "subjective": "Has fever, shortness of breath at rest.",
            "objective": "Not documented in visit.",
            "assessment": "Undifferentiated.",
            "plan": "Follow up.",
        },
        "Fever? Shortness of breath at rest? I don't think I had a fever.",
        [
            SpeakerTurn(
                speaker="provider",
                start_s=0.0,
                end_s=2.0,
                text="Fever?",
            ),
            SpeakerTurn(
                speaker="provider",
                start_s=2.0,
                end_s=4.0,
                text="Shortness of breath at rest?",
            ),
            SpeakerTurn(
                speaker="patient",
                start_s=4.0,
                end_s=7.0,
                text="I don't think I had a fever.",
            ),
        ],
    )
    reasons = {(item.section, item.reason) for item in flags}
    assert ("subjective", "negation_or_question") in reasons


def test_flag_skips_when_symptom_is_positively_stated():
    flags = flag_negation_assertions(
        {"subjective": "Patient reports a fever for three days.", "objective": "", "assessment": "", "plan": ""},
        "I've had a fever for three days.",
        [
            SpeakerTurn(
                speaker="patient",
                start_s=0.0,
                end_s=3.0,
                text="I've had a fever for three days.",
            )
        ],
    )
    assert flags == []


def test_generate_note_flags_but_does_not_rewrite_negation_error(ollama_mode, monkeypatch):
    asserted = "The patient has fever and shortness of breath at rest."
    patch_ollama(
        monkeypatch,
        {
            "subjective": asserted,
            "objective": "Not documented in visit.",
            "assessment": "Unclear.",
            "plan": "Return if worse.",
            "likely_diagnoses": [],
            "follow_up": [],
            "citations": {},
        },
    )
    note = generate_note(
        TranscriptResult(
            text="Fever? Shortness of breath at rest? I don't think I had a fever.",
            segments=[
                SpeakerTurn(speaker="provider", start_s=0.0, end_s=1.5, text="Fever?"),
                SpeakerTurn(
                    speaker="provider",
                    start_s=1.5,
                    end_s=3.5,
                    text="Shortness of breath at rest?",
                ),
                SpeakerTurn(
                    speaker="patient",
                    start_s=3.5,
                    end_s=6.5,
                    text="I don't think I had a fever.",
                ),
            ],
        )
    )
    assert note.subjective == asserted
    assert any(
        item.reason in {"denied_by_patient", "only_asked_not_confirmed"}
        for item in note.verification_needs
    )
