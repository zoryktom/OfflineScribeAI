from __future__ import annotations

import json
from pathlib import Path

from offlinescribe.eval.taxonomy import Annotation, ErrorType, Severity

SCHEMA = json.loads(Path("data/schemas/annotation.schema.json").read_text(encoding="utf-8"))


def _valid(**overrides) -> dict:
    row = {
        "encounter_id": "E001",
        "condition": "rag_grounded",
        "model": "stub",
        "asr": "whisper-large-v3",
        "span_generated": "denies chest pain",
        "span_source": "I deny chest pain",
        "error_type": "negation_flip",
        "severity": "major",
        "clinically_significant": True,
        "rationale": "denied token asserted in assessment",
        "annotator_id": "A1",
    }
    row.update(overrides)
    return row


def test_annotation_model_roundtrip() -> None:
    item = Annotation.model_validate(_valid())
    assert item.error_type is ErrorType.NEGATION_FLIP
    assert item.severity is Severity.MAJOR
    dumped = json.loads(item.model_dump_json())
    for key in SCHEMA["required"]:
        assert key in dumped


def test_schema_enums_match_taxonomy() -> None:
    assert set(SCHEMA["properties"]["error_type"]["enum"]) == {e.value for e in ErrorType}
    assert set(SCHEMA["properties"]["severity"]["enum"]) == {s.value for s in Severity}
    assert "baseline" in SCHEMA["properties"]["condition"]["enum"]
    assert "rag_grounded_verified" in SCHEMA["properties"]["condition"]["enum"]


def test_optional_span_source_null() -> None:
    item = Annotation.model_validate(_valid(span_source=None, error_type="omission"))
    assert item.span_source is None
