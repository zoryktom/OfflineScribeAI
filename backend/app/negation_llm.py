"""Separate assertion/negation classification. Does not rewrite the SOAP note.

Untrusted until measured. Can hallucinate. Keyword matching is only a pre-filter.
"""

from __future__ import annotations

import json
import re
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.config import get_settings
from app.models import SpeakerTurn, VerificationNeed
from app.negation_check import sentence_needs_classification, split_sentences


class ClassificationError(Exception):
    """Classifier call failed. Message is safe to show. Note text is unchanged."""

LABELS = (
    "ASSERTED_BY_PATIENT",
    "DENIED_BY_PATIENT",
    "ONLY_ASKED_NOT_CONFIRMED",
    "AMBIGUOUS",
)
FLAG_LABELS = frozenset({"DENIED_BY_PATIENT", "ONLY_ASKED_NOT_CONFIRMED"})
_last_classify_seconds: float | None = None
REASON_BY_LABEL = {
    "DENIED_BY_PATIENT": "denied_by_patient",
    "ONLY_ASKED_NOT_CONFIRMED": "only_asked_not_confirmed",
}

CLASSIFIER_SYSTEM = """You classify SOAP sentences against a visit transcript.
For each sentence, return one label:
ASSERTED_BY_PATIENT — the patient stated this finding as present.
DENIED_BY_PATIENT — the patient denied it or said it was not present.
ONLY_ASKED_NOT_CONFIRMED — it was asked and never confirmed.
AMBIGUOUS — differential, safety-net, or you cannot tell.
Do not rewrite the note. Reply with JSON only:
{"items":[{"section":"subjective","sentence_index":0,"label":"DENIED_BY_PATIENT"}]}
"""

_STOP = frozenset(
    {
        "patient",
        "reports",
        "reported",
        "have",
        "has",
        "had",
        "this",
        "that",
        "with",
        "from",
        "both",
        "arms",
        "days",
        "visit",
        "return",
        "more",
        "than",
        "three",
        "lasts",
        "stop",
        "does",
        "come",
        "back",
        "tomorrow",
        "could",
        "rather",
        "mild",
        "viral",
        "poor",
        "sleep",
    }
)


def classify_assertion_needs(
    sections: dict[str, str],
    source_text: str,
    segments: list[SpeakerTurn] | None = None,
) -> list[VerificationNeed]:
    """Flag SOAP sentences the classifier marks denied or only-asked. Never edits text."""
    global _last_classify_seconds
    candidates = _candidate_sentences(sections)
    if not candidates:
        _last_classify_seconds = 0.0
        return []
    settings = get_settings()
    started = time.perf_counter()
    if settings.stub_mode:
        labels = _stub_classify(candidates, source_text, segments)
    else:
        labels = _ollama_classify(candidates, source_text, segments)
    _last_classify_seconds = time.perf_counter() - started
    flags: list[VerificationNeed] = []
    for item, label in zip(candidates, labels, strict=True):
        reason = REASON_BY_LABEL.get(label)
        if not reason:
            continue
        flags.append(
            VerificationNeed(
                section=item["section"],
                sentence_index=item["sentence_index"],
                reason=reason,
            )
        )
    return flags


def last_classify_seconds() -> float | None:
    return _last_classify_seconds


def _candidate_sentences(sections: dict[str, str]) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for section in ("subjective", "objective", "assessment", "plan"):
        text = (sections.get(section) or "").strip()
        if not text:
            continue
        for index, sentence in enumerate(split_sentences(text)):
            if not sentence_needs_classification(sentence):
                continue
            found.append(
                {
                    "section": section,
                    "sentence_index": index,
                    "sentence": sentence,
                }
            )
    return found


def _stub_classify(
    candidates: list[dict[str, object]],
    source_text: str,
    segments: list[SpeakerTurn] | None,
) -> list[str]:
    chunks = [seg.text.lower() for seg in segments] if segments else [source_text.lower()]
    labels: list[str] = []
    for item in candidates:
        sentence = str(item["sentence"]).lower()
        words = [
            token
            for token in re.findall(r"[a-z]{4,}", sentence)
            if token not in _STOP
        ]
        label = "AMBIGUOUS"
        for word in words:
            denied = any(
                re.search(rf"\b(no|not|never|denied|denies)\b.{{0,40}}\b{word}\b", chunk)
                or re.search(rf"\b{word}\b.{{0,40}}\b(no|not|never|denied)\b", chunk)
                for chunk in chunks
            )
            asked = any(
                "?" in chunk and word in chunk
                or re.search(rf"\b(any|do you|did you)\b.{{0,20}}\b{word}\b", chunk)
                for chunk in chunks
            )
            asserted = any(
                re.search(
                    rf"\b(i've had|i have|i still|i've got)\b.{{0,40}}\b{word}\b",
                    chunk,
                )
                for chunk in chunks
            )
            if asserted:
                label = "ASSERTED_BY_PATIENT"
                break
            if denied:
                label = "DENIED_BY_PATIENT"
                break
            if asked:
                label = "ONLY_ASKED_NOT_CONFIRMED"
                break
        labels.append(label)
    return labels


def _ollama_classify(
    candidates: list[dict[str, object]],
    source_text: str,
    segments: list[SpeakerTurn] | None,
) -> list[str]:
    settings = get_settings()
    lines = []
    if segments:
        for seg in segments:
            lines.append(f"{seg.speaker}: {seg.text}")
    else:
        lines.append(source_text)
    payload_sentences = [
        {
            "section": item["section"],
            "sentence_index": item["sentence_index"],
            "sentence": item["sentence"],
        }
        for item in candidates
    ]
    prompt = (
        "Transcript:\n"
        + "\n".join(lines)
        + "\n\nSOAP sentences to classify:\n"
        + json.dumps(payload_sentences)
    )
    generate_url = settings.ollama_host.rstrip("/") + "/api/generate"
    body = {
        "model": settings.ollama_model,
        "system": CLASSIFIER_SYSTEM,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.2},
    }
    try:
        request = Request(
            generate_url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started = time.perf_counter()
        with urlopen(  # noqa: S310 - local Ollama only
            request, timeout=settings.ollama_timeout_seconds
        ) as response:
            raw_payload = json.loads(response.read().decode("utf-8"))
        _ = time.perf_counter() - started
    except TimeoutError as exc:
        raise ClassificationError(
            "The local model took too long to classify assertion status. "
            "The SOAP draft was not changed. Try again, or use STUB_MODE."
        ) from exc
    except URLError as exc:
        raise ClassificationError(
            "Could not reach Ollama while classifying assertion status. "
            "Confirm `ollama serve` is running."
        ) from exc
    raw = raw_payload.get("response", "")
    parsed = json.loads(raw) if isinstance(raw, str) else raw
    by_key: dict[tuple[str, int], str] = {}
    items = parsed.get("items") if isinstance(parsed, dict) else None
    if isinstance(items, list):
        for row in items:
            if not isinstance(row, dict):
                continue
            label = str(row.get("label") or "").strip().upper()
            if label not in LABELS:
                continue
            section = str(row.get("section") or "")
            try:
                index = int(row.get("sentence_index"))
            except (TypeError, ValueError):
                continue
            by_key[(section, index)] = label
    labels = [
        by_key.get((str(item["section"]), int(item["sentence_index"])), "AMBIGUOUS")
        for item in candidates
    ]
    return labels
