from app.models import SpeakerTurn
from app.negation_llm import classify_assertion_needs, last_classify_seconds


def test_stub_flags_denied_token_outside_keyword_lexicon():
    flags = classify_assertion_needs(
        {
            "subjective": "The patient has tinnitus in both ears.",
            "objective": "Not documented in visit.",
            "assessment": "",
            "plan": "",
        },
        "Any ringing in the ears? Tinnitus? No tinnitus. Ears are quiet.",
        [
            SpeakerTurn(speaker="provider", start_s=0, end_s=2, text="Tinnitus?"),
            SpeakerTurn(speaker="patient", start_s=2, end_s=4, text="No tinnitus. Ears are quiet."),
        ],
    )
    assert any(item.reason == "denied_by_patient" for item in flags)


def test_stub_does_not_rewrite_and_skips_empty_sections():
    flags = classify_assertion_needs(
        {
            "subjective": "Not documented in visit.",
            "objective": "",
            "assessment": "",
            "plan": "",
        },
        "Hello.",
        [SpeakerTurn(speaker="unknown", start_s=0, end_s=1, text="Hello.")],
    )
    assert flags == []
    assert last_classify_seconds() == 0.0
