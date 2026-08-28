import logging

from app.grounding import apply_grounding
from app.models import SpeakerTurn
from app.note_service import generate_note


def test_grounding_logs_unlink_without_section_body(caplog):
    caplog.set_level(logging.INFO)
    secret = "UNIQUE-ASSESSMENT-PHRASE-should-never-be-logged"
    apply_grounding(secret, _cough_segments(), section="assessment")
    recorded = caplog.text
    assert "section=assessment" in recorded
    assert "raw_empty=false" in recorded
    assert "reason=no_confident_link" in recorded
    assert secret not in recorded


def _cough_segments() -> list[SpeakerTurn]:
    return [
        SpeakerTurn(
            speaker="patient",
            start_s=2.0,
            end_s=7.5,
            text="I've had a cough for three days and a low fever.",
        ),
        SpeakerTurn(
            speaker="provider",
            start_s=8.0,
            end_s=12.0,
            text="This looks like a viral upper respiratory infection.",
        ),
    ]


def test_stub_note_grounding_is_populated_not_empty_schema():
    note = generate_note("Patient reports a cough for three days.")
    assert note.subjective_grounding.sources
    source = note.subjective_grounding.sources[0]
    assert source.text
    assert source.end_s > source.start_s
    assert note.assessment_grounding.sources
    assert note.objective_grounding.directly_stated is True


def test_apply_grounding_prefers_validated_llm_citations():
    text, grounded = apply_grounding(
        "Cough for three days.",
        _cough_segments(),
        llm_ranges=[{"start_s": 2.0, "end_s": 7.5}],
    )
    assert "Cough" in text
    assert grounded.directly_stated is True
    assert grounded.sources
    assert grounded.sources[0].start_s == 2.0
    assert "cough" in grounded.sources[0].text.lower()


def test_apply_grounding_rejects_wrong_llm_timestamps_and_falls_back():
    """Self-citation is tried first, then checked against the real transcript."""
    text, grounded = apply_grounding(
        "Cough for three days.",
        _cough_segments(),
        llm_ranges=[{"start_s": 90.0, "end_s": 95.0}],
    )
    assert "Cough" in text
    assert grounded.sources
    assert grounded.sources[0].start_s == 2.0


def test_apply_grounding_keeps_unlinked_claims_and_does_not_blank_section():
    """Unsupported sentences stay visible; they are labeled, not deleted."""
    text, grounded = apply_grounding(
        "Cough for three days. Blood pressure is well controlled.",
        _cough_segments(),
        section="assessment",
    )
    assert "Cough for three days." in text
    assert "well controlled" in text.lower()
    assert grounded.directly_stated is False
    assert grounded.sources


def test_grounding_never_blanks_nonempty_model_text():
    """Invariant: if the model wrote a section, grounding must not empty it."""
    raw = "Hypertension follow-up; continue current doses."
    text, grounded = apply_grounding(raw, _cough_segments(), section="assessment")
    assert text.strip()
    assert text != "Not documented in visit"
    assert raw in text
    assert grounded.directly_stated is False
    assert grounded.sources == []


def test_generate_note_does_not_blank_ungrounded_assessment(ollama_mode, monkeypatch):
    from app.models import TranscriptResult
    from tests.ollama_fakes import patch_ollama

    assessment = "Continue present management pending labs."
    patch_ollama(
        monkeypatch,
        {
            "subjective": "Cough for three days.",
            "objective": "Not documented in visit.",
            "assessment": assessment,
            "plan": "Rest and fluids.",
            "likely_diagnoses": ["cough"],
            "follow_up": [],
            "citations": {"subjective": [{"start_s": 2.0, "end_s": 7.5}]},
        },
    )
    note = generate_note(
        TranscriptResult(
            text="I've had a cough for three days and a low fever.",
            segments=_cough_segments(),
        )
    )
    assert note.assessment.strip()
    assert note.assessment != "Not documented in visit"
    assert assessment in note.assessment


def test_generate_note_ollama_populates_grounding(ollama_mode, monkeypatch):
    from app.models import TranscriptResult
    from tests.ollama_fakes import patch_ollama

    patch_ollama(
        monkeypatch,
        {
            "subjective": "Cough for three days with a low fever.",
            "objective": "Not documented in visit.",
            "assessment": "Viral upper respiratory infection.",
            "plan": "Rest and fluids.",
            "likely_diagnoses": ["viral upper respiratory infection"],
            "follow_up": [],
            "citations": {
                "subjective": [{"start_s": 2.0, "end_s": 7.5}],
                "assessment": [{"start_s": 8.0, "end_s": 12.0}],
            },
        },
    )
    note = generate_note(
        TranscriptResult(
            text="I've had a cough for three days and a low fever. This looks like a viral upper respiratory infection.",
            segments=_cough_segments(),
        )
    )
    assert note.subjective_grounding.sources
    assert any("cough" in item.text.lower() for item in note.subjective_grounding.sources)
    assert note.assessment_grounding.sources
    assert note.subjective_grounding.directly_stated is True


def test_family_history_is_not_linked_to_current_assessment():
    """Topical overlap on 'stroke' must not cite a relative's history as today's support."""
    segments = [
        SpeakerTurn(
            speaker="patient",
            start_s=5.0,
            end_s=9.0,
            text="My cousin had a stroke last month.",
        ),
        SpeakerTurn(
            speaker="provider",
            start_s=70.0,
            end_s=76.0,
            text="I'm not diagnosing a stroke today. Blood pressure is 132 over 84.",
        ),
    ]
    text, grounded = apply_grounding(
        "Not diagnosing a stroke today from this story.",
        segments,
        section="assessment",
    )
    assert "Not diagnosing a stroke today" in text
    assert grounded.sources
    for source in grounded.sources:
        assert "cousin" not in source.text.lower()
        assert "last month" not in source.text.lower()


def test_incidental_bp_mention_is_not_cited_for_todays_vitals():
    segments = [
        SpeakerTurn(
            speaker="patient",
            start_s=12.0,
            end_s=16.0,
            text="I keep checking my blood pressure on the grocery store cuff.",
        ),
        SpeakerTurn(
            speaker="provider",
            start_s=67.0,
            end_s=71.0,
            text="Your blood pressure here is 132 over 84.",
        ),
    ]
    text, grounded = apply_grounding(
        "Blood pressure: 132/84.",
        segments,
        section="objective",
    )
    assert "132" in text
    assert grounded.sources
    for source in grounded.sources:
        assert "grocery" not in source.text.lower()
    assert any("132" in source.text for source in grounded.sources)


def test_paraphrase_patient_vs_first_person_still_links():
    """Note wording that paraphrases the transcript should still get a source."""
    segments = [
        SpeakerTurn(
            speaker="patient",
            start_s=2.0,
            end_s=6.0,
            text="I've had a cough for three days and a low fever.",
        ),
        SpeakerTurn(
            speaker="patient",
            start_s=6.0,
            end_s=8.0,
            text="I'm tired of it.",
        ),
    ]
    cough, cough_g = apply_grounding(
        "Patient reports a cough for three days with a low fever.",
        segments,
        section="subjective",
    )
    assert "cough" in cough.lower()
    assert cough_g.sources
    assert any("cough" in source.text.lower() for source in cough_g.sources)

    tired, tired_g = apply_grounding(
        "The patient is tired of it.",
        segments,
        section="subjective",
    )
    assert "tired" in tired.lower()
    assert tired_g.sources
    assert any("tired" in source.text.lower() for source in tired_g.sources)
