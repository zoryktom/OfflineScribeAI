"""Error taxonomy for clinical documentation drafts. Synthetic evaluation only."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ErrorType(str, Enum):
    OMISSION = "omission"
    HALLUCINATION = "hallucination"
    NEGATION_FLIP = "negation_flip"
    LATERALITY = "laterality"
    MEDICATION = "medication"
    DOSE = "dose"
    TEMPORALITY = "temporality"
    ATTRIBUTION = "attribution"
    ICD_INSTABILITY = "icd_instability"
    ASR_PROPAGATION = "asr_propagation"
    STYLE_ONLY = "style_only"


class Severity(str, Enum):
    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CRITICAL = "critical"


SEVERITY_WEIGHTS: dict[Severity, float] = {
    Severity.NONE: 0.0,
    Severity.MINOR: 0.5,
    Severity.MODERATE: 2.0,
    Severity.MAJOR: 5.0,
    Severity.CRITICAL: 10.0,
}


class Annotation(BaseModel):
    encounter_id: str
    condition: str
    model: str
    asr: str
    annotator_id: str
    span_generated: str = Field(..., description="Text span in generated note")
    span_source: Optional[str] = Field(None, description="Span in source transcript if applicable")
    error_type: ErrorType
    severity: Severity
    clinically_significant: bool
    rationale: str = Field(..., min_length=10)


class EncounterAnnotation(BaseModel):
    encounter_id: str
    condition: str
    model: str
    asr: str
    annotator_id: str
    annotations: list[Annotation]
    gold_note_adequate: bool
    notes: Optional[str] = None


class EncounterNote(BaseModel):
    subjective: str = ""
    objective: str = ""
    assessment: str = ""
    plan: str = ""


class Encounter(BaseModel):
    encounter_id: str
    specialty: str = "primary_care"
    transcript: str
    gold_note: EncounterNote
    gold_meds: list[str] = Field(default_factory=list)
    gold_entities: list[str] = Field(default_factory=list)
    planted: list[dict] = Field(default_factory=list)
