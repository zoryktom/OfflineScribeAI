from offlinescribe.eval.metrics import (
    clinical_error_score,
    dose_exact_match,
    hallucination_rate,
    laterality_accuracy,
    medication_f1,
    negation_accuracy,
    omission_rate,
    rouge_l,
    wer,
)
from offlinescribe.eval.taxonomy import Annotation, ErrorType, Severity


def test_wer_identical() -> None:
    assert wer("left ankle sprain", "left ankle sprain") == 0.0


def test_wer_substitution() -> None:
    assert wer("left ankle sprain", "right ankle sprain") > 0


def test_rouge_and_meds() -> None:
    assert rouge_l("takes lisinopril 10 mg", "takes lisinopril 10 mg") == 1.0
    assert medication_f1(["lisinopril 10 mg"], "continue lisinopril 10 mg daily") == 1.0


def test_dose_and_laterality() -> None:
    assert dose_exact_match("lisinopril 10 mg", "lisinopril 10 mg") == 1.0
    assert laterality_accuracy("pain on the left side", "pain on the left side") == 1.0
    assert laterality_accuracy("pain on the left side", "pain on the right side") == 0.0


def test_negation_and_omission() -> None:
    source = "I deny chest pain. I have fatigue."
    good = "Denies chest pain. Reports fatigue."
    bad = "Chest pain is present. Reports fatigue."
    assert negation_accuracy(source, good) == 1.0
    assert negation_accuracy(source, bad) < 1.0
    assert omission_rate(["fatigue"], "no mention of the other problem") == 1.0
    assert hallucination_rate("fatigue only", "fatigue and early stroke history") > 0


def test_clinical_error_score() -> None:
    rows = [
        Annotation(
            encounter_id="E001",
            condition="baseline",
            model="stub",
            asr="whisper-large-v3",
            span_generated="x",
            error_type=ErrorType.HALLUCINATION,
            severity=Severity.CRITICAL,
            clinically_significant=True,
            rationale="planted critical span",
            annotator_id="A1",
        )
    ]
    assert clinical_error_score(rows) == 10.0
    assert clinical_error_score([]) == 0.0
