from offlinescribe.eval.taxonomy import (
    SEVERITY_WEIGHTS,
    Annotation,
    EncounterAnnotation,
    ErrorType,
    Severity,
)


def test_weights_and_types() -> None:
    assert SEVERITY_WEIGHTS[Severity.CRITICAL] == 10.0
    assert len(ErrorType) == 11
    item = Annotation(
        encounter_id="E001",
        condition="baseline",
        model="stub",
        asr="whisper-large-v3",
        annotator_id="A1",
        span_generated="chest pain",
        error_type=ErrorType.OMISSION,
        severity=Severity.MAJOR,
        clinically_significant=True,
        rationale="omitted radiation to the arm",
    )
    bundle = EncounterAnnotation(
        encounter_id="E001",
        condition="baseline",
        model="stub",
        asr="whisper-large-v3",
        annotator_id="A1",
        annotations=[item],
        gold_note_adequate=True,
    )
    assert bundle.annotations[0].error_type is ErrorType.OMISSION
