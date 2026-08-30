"""Pydantic models shared by the local API, storage, and FHIR mapping."""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class SyncStatus(str, Enum):
    pending = "pending"
    synced = "synced"
    failed = "failed"


class SpeakerTurn(BaseModel):
    speaker: Literal["provider", "patient", "unknown"]
    start_s: float
    end_s: float
    text: str


class AsrFlag(BaseModel):
    """A transcript span a reviewer should check (confidence or odd drug-like token)."""

    start_s: float
    end_s: float
    text: str
    reason: str


class TranscriptResult(BaseModel):
    text: str
    language: str = "en"
    segments: list[SpeakerTurn] = Field(default_factory=list)
    asr_flags: list[AsrFlag] = Field(default_factory=list)


class SuggestedIcd10(BaseModel):
    code: str
    description: str
    accepted: bool | None = None


class VerificationNeed(BaseModel):
    """A SOAP sentence that should be checked, not silently rewritten."""

    section: str
    sentence_index: int
    reason: str


class ReviewAction(BaseModel):
    section: str
    action: str


class ProviderAttestation(BaseModel):
    """Named review is required before sync/export. A boolean is not enough."""

    reviewer_id: str
    reviewed_at: datetime


class FollowUpItem(BaseModel):
    text: str
    timeframe: str | None = None


class NoteSource(BaseModel):
    start_s: float
    end_s: float
    text: str


class GroundedSection(BaseModel):
    """Transcript backing for one SOAP section. Empty sources means nothing to show."""

    sources: list[NoteSource] = Field(default_factory=list)
    directly_stated: bool = True


class Note(BaseModel):
    subjective: str = ""
    objective: str = ""
    assessment: str = ""
    plan: str = ""
    suggested_icd10: list[SuggestedIcd10] = Field(default_factory=list)
    follow_up: list[FollowUpItem] = Field(default_factory=list)
    subjective_grounding: GroundedSection = Field(default_factory=GroundedSection)
    objective_grounding: GroundedSection = Field(default_factory=GroundedSection)
    assessment_grounding: GroundedSection = Field(default_factory=GroundedSection)
    plan_grounding: GroundedSection = Field(default_factory=GroundedSection)
    verification_needs: list[VerificationNeed] = Field(default_factory=list)


class Visit(BaseModel):
    id: str
    timestamp: datetime
    transcript: str
    transcript_segments: list[SpeakerTurn] = Field(default_factory=list)
    note: Note
    sync_status: SyncStatus = SyncStatus.pending
    fhir_resource_id: str | None = None
    provider_review: ProviderAttestation | None = None
    asr_flags: list[AsrFlag] = Field(default_factory=list)
    # Required before sync. Never default these to a shared sandbox chart —
    # a visit without an explicit Patient/Encounter link must not be POSTed.
    fhir_patient_id: str | None = None
    fhir_encounter_id: str | None = None
    last_sync_error: str | None = None
    review_summary: str | None = None

    def has_fhir_chart_link(self) -> bool:
        return bool(self.fhir_patient_id and self.fhir_encounter_id)

    def is_reviewed(self) -> bool:
        review = self.provider_review
        return bool(review and review.reviewer_id.strip())


class VisitUpdate(BaseModel):
    note: Note
    reviewer_id: str
    section_actions: list[ReviewAction] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    stub_mode: bool
    ollama_model: str


class SyncVisitResult(BaseModel):
    visit_id: str
    sync_status: SyncStatus
    fhir_resource_id: str | None = None
    dry_run: bool = False
    error: str | None = None


class SyncRunResult(BaseModel):
    dry_run: bool
    results: list[SyncVisitResult]
