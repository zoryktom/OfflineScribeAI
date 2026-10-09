"""Deterministic local clinical entity candidate extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ClinicalEntity:
    text: str
    vocabulary: str
    concept_id: str
    semantic_type: str
    start_char: int
    end_char: int
    section: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "text": self.text,
            "vocabulary": self.vocabulary,
            "concept_id": self.concept_id,
            "semantic_type": self.semantic_type,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "section": self.section,
        }


SNOMED_PATTERNS: tuple[tuple[str, str, str], ...] = (
    (r"\b(chest pain)\b", "29857009", "finding"),
    (r"\b(shortness of breath|dyspnea)\b", "267036007", "finding"),
    (r"\b(cough)\b", "49727002", "finding"),
    (r"\b(fever)\b", "386661006", "finding"),
    (r"\b(asthma)\b", "195967001", "disorder"),
    (r"\b(hypertension|high blood pressure)\b", "38341003", "disorder"),
    (r"\b(diabetes mellitus|type 2 diabetes|diabetes)\b", "73211009", "disorder"),
    (r"\b(upper respiratory infection|uri)\b", "54150009", "disorder"),
    (r"\b(pneumonia)\b", "233604007", "disorder"),
    (r"\b(abdominal pain)\b", "21522001", "finding"),
)

RXNORM_PATTERNS: tuple[tuple[str, str, str], ...] = (
    (r"\b(metformin)\b", "6809", "medication"),
    (r"\b(lisinopril)\b", "29046", "medication"),
    (r"\b(albuterol)\b", "435", "medication"),
    (r"\b(acetaminophen|paracetamol)\b", "161", "medication"),
    (r"\b(ibuprofen)\b", "5640", "medication"),
    (r"\b(amoxicillin)\b", "723", "medication"),
    (r"\b(atorvastatin)\b", "83367", "medication"),
    (r"\b(insulin)\b", "5856", "medication"),
    (r"\b(omeprazole)\b", "7646", "medication"),
    (r"\b(prednisone)\b", "8640", "medication"),
)


def extract_clinical_entities(text: str, section_spans: dict[str, tuple[int, int]] | None = None) -> list[ClinicalEntity]:
    entities: list[ClinicalEntity] = []
    for pattern, concept_id, semantic_type in SNOMED_PATTERNS:
        entities.extend(_extract_pattern(text, pattern, "SNOMEDCT", concept_id, semantic_type, section_spans))
    for pattern, concept_id, semantic_type in RXNORM_PATTERNS:
        entities.extend(_extract_pattern(text, pattern, "RxNorm", concept_id, semantic_type, section_spans))
    return sorted(_dedupe_entities(entities), key=lambda entity: (entity.start_char, entity.vocabulary, entity.concept_id))


def _extract_pattern(
    text: str,
    pattern: str,
    vocabulary: str,
    concept_id: str,
    semantic_type: str,
    section_spans: dict[str, tuple[int, int]] | None,
) -> list[ClinicalEntity]:
    matches: list[ClinicalEntity] = []
    for match in re.finditer(pattern, text, flags=re.IGNORECASE):
        matches.append(
            ClinicalEntity(
                text=match.group(1),
                vocabulary=vocabulary,
                concept_id=concept_id,
                semantic_type=semantic_type,
                start_char=match.start(1),
                end_char=match.end(1),
                section=_section_for_span(match.start(1), section_spans),
            )
        )
    return matches


def _section_for_span(start: int, section_spans: dict[str, tuple[int, int]] | None) -> str | None:
    if not section_spans:
        return None
    for section, (section_start, section_end) in section_spans.items():
        if section_start <= start < section_end:
            return section
    return None


def _dedupe_entities(entities: list[ClinicalEntity]) -> list[ClinicalEntity]:
    seen: set[tuple[str, str, int, int]] = set()
    deduped: list[ClinicalEntity] = []
    for entity in entities:
        key = (entity.vocabulary, entity.concept_id, entity.start_char, entity.end_char)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entity)
    return deduped

