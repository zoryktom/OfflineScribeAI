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


class Annotation(BaseModel):
    encounter_id: str
    condition: str
    model: str
    asr: str
    span_generated: str
    span_source: Optional[str] = None
    error_type: ErrorType
    severity: Severity
    clinically_significant: bool
    rationale: str
    annotator_id: str


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
