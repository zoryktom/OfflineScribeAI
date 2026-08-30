from app.asr_flags import flag_asr_concerns
from app.models import SpeakerTurn


def test_flags_known_garbled_medication_token():
    flags = flag_asr_concerns(
        [
            SpeakerTurn(
                speaker="unknown",
                start_s=1.0,
                end_s=4.0,
                text="I still take the liz in April 10 mg.",
            )
        ]
    )
    assert flags
    assert any(item.reason == "unusual_medication_token" for item in flags)
    assert any("liz" in item.text.lower() for item in flags)


def test_does_not_flag_exact_medication_name():
    flags = flag_asr_concerns(
        [
            SpeakerTurn(
                speaker="unknown",
                start_s=1.0,
                end_s=4.0,
                text="I take lisinopril ten milligrams daily.",
            )
        ]
    )
    assert flags == []


def test_flags_low_confidence_near_medication():
    flags = flag_asr_concerns(
        [],
        words=[("metfomin", 2.0, 2.4, 0.21)],
    )
    assert flags
    assert flags[0].reason in {"low_confidence", "unusual_medication_token"}
