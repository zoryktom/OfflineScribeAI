"""SOAP note parser."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


SOAP_KEYS = ("subjective", "objective", "assessment", "plan")


@dataclass
class SoapNote:
    subjective: str = ""
    objective: str = ""
    assessment: str = ""
    plan: str = ""
    section_spans: dict[str, tuple[int, int]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, str]:
        return {
            "subjective": self.subjective,
            "objective": self.objective,
            "assessment": self.assessment,
            "plan": self.plan,
        }


HEADING_PATTERN = re.compile(
    r"(?P<label>subjective|objective|assessment|plan)\s*:\s*",
    flags=re.IGNORECASE,
)


def parse_soap(transcript: str) -> SoapNote:
    """Parse transcript text into SOAP sections using headings and fallbacks."""

    cleaned = _normalize_whitespace(transcript)
    if not cleaned:
        return SoapNote()

    explicit = _parse_explicit_headings(cleaned)
    if any(getattr(explicit, key) for key in SOAP_KEYS):
        explicit = _fill_missing_sections_from_prefix(cleaned, explicit)
        return explicit

    return _parse_heuristic(cleaned)


def _parse_explicit_headings(text: str) -> SoapNote:
    matches = list(HEADING_PATTERN.finditer(text))
    note = SoapNote()
    if not matches:
        return note

    for index, match in enumerate(matches):
        label = match.group("label").lower()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        value = text[start:end].strip(" .")
        setattr(note, label, value)
        note.section_spans[label] = (start, end)
    return note


def _fill_missing_sections_from_prefix(text: str, note: SoapNote) -> SoapNote:
    if not note.section_spans:
        return note

    first_heading = HEADING_PATTERN.search(text)
    if first_heading is None:
        return note

    first_heading_start = first_heading.start()
    if first_heading_start <= 0:
        return note

    prefix = text[:first_heading_start].strip()
    if not prefix:
        return note

    prefix_note = _parse_heuristic(prefix)
    for key in SOAP_KEYS:
        if getattr(note, key):
            continue
        prefix_value = getattr(prefix_note, key)
        if not prefix_value:
            continue
        setattr(note, key, prefix_value)
        if key in prefix_note.section_spans:
            note.section_spans[key] = prefix_note.section_spans[key]
    return note


def _parse_heuristic(text: str) -> SoapNote:
    sentences = _split_sentences(text)
    buckets: dict[str, list[str]] = {key: [] for key in SOAP_KEYS}
    spans: dict[str, list[tuple[int, int]]] = {key: [] for key in SOAP_KEYS}

    cursor = 0
    for sentence in sentences:
        start = text.find(sentence, cursor)
        if start < 0:
            start = cursor
        end = start + len(sentence)
        cursor = end
        section = _classify_sentence(sentence)
        buckets[section].append(sentence)
        spans[section].append((start, end))

    note = SoapNote(
        subjective=" ".join(buckets["subjective"]).strip(),
        objective=" ".join(buckets["objective"]).strip(),
        assessment=" ".join(buckets["assessment"]).strip(),
        plan=" ".join(buckets["plan"]).strip(),
    )
    for section, section_spans in spans.items():
        if section_spans:
            note.section_spans[section] = (section_spans[0][0], section_spans[-1][1])
    return note


def _classify_sentence(sentence: str) -> str:
    lowered = sentence.lower()
    if re.search(r"\b(plan|recommend|start|continue|prescribe|follow up|return|hydrate|take|use)\b", lowered):
        return "plan"
    if re.search(r"\b(assessment|diagnosis|impression|consistent with|likely|infection|asthma|hypertension|diabetes)\b", lowered):
        return "assessment"
    if re.search(
        r"\b(objective|vitals?|temperature|bp|blood pressure|pulse|oxygen|saturation|exam|lungs|heart|lab|x-ray)\b",
        lowered,
    ):
        return "objective"
    return "subjective"


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
