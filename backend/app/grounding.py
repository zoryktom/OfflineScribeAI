"""Attach transcript sources to SOAP section text.

Try LLM-cited timestamp ranges first, then fall back to word overlap with
segments. Model text is never blanked: if a claim cannot be linked, keep it
and mark the section not-directly-stated / sources-unclear.

Overlap matching is a heuristic. Family-history and far-apart topical hits
are treated as too weak to cite.
"""

from __future__ import annotations

import logging
import math
import re

from app.models import GroundedSection, NoteSource, SpeakerTurn

logger = logging.getLogger(__name__)

_STOP = {
    "a",
    "an",
    "the",
    "of",
    "and",
    "or",
    "to",
    "in",
    "for",
    "with",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "this",
    "that",
    "it",
    "on",
    "at",
    "as",
    "not",
    "no",
    "had",
    "have",
    "has",
    "did",
    "does",
    "do",
}

_PERSON_RE = re.compile(
    r"\b(i|im|ive|id|me|my|mine|we|our|you|your|he|she|his|her|they|their|"
    r"patient|patients)\b"
)
_FAMILY_RE = re.compile(
    r"\b(cousin|brother|sister|mother|father|mom|dad|uncle|aunt|grandma|"
    r"grandfather|grandmother|nephew|niece|family)\b"
)


def apply_grounding(
    text: str,
    segments: list[SpeakerTurn],
    llm_ranges: list[dict] | None = None,
    *,
    section: str = "unknown",
) -> tuple[str, GroundedSection]:
    """Return section text plus grounding metadata. Never blanks non-empty model text."""
    stripped = (text or "").strip()
    raw_empty = not stripped or stripped.lower() == "not documented in visit"
    if raw_empty:
        return stripped or "Not documented in visit", GroundedSection(
            sources=[],
            directly_stated=True,
        )

    if not segments:
        logger.info(
            "grounding section=%s raw_empty=false linked_sources=0 unlinked_sentences=all "
            "reason=no_segments",
            section,
        )
        return stripped, GroundedSection(sources=[], directly_stated=False)

    sentences = _split_sentences(stripped)
    sources: list[NoteSource] = []
    unlinked = 0
    llm_segments = _segments_from_llm_ranges(llm_ranges, segments) if llm_ranges else []

    for sentence in sentences:
        cited = _filter_candidates(
            sentence,
            [seg for seg in llm_segments if _token_hits(sentence, seg.text) > 0],
        )
        if cited:
            sources.extend(_to_sources(cited))
            continue
        matched = _best_segments_for_sentence(sentence, segments)
        if matched:
            sources.extend(_to_sources(matched))
        else:
            unlinked += 1

    unique_sources = _dedupe_sources(sources)
    if not unique_sources:
        logger.info(
            "grounding section=%s raw_empty=false linked_sources=0 unlinked_sentences=%s "
            "reason=no_confident_link",
            section,
            unlinked or len(sentences),
        )
        return stripped, GroundedSection(sources=[], directly_stated=False)

    if unlinked:
        logger.info(
            "grounding section=%s raw_empty=false linked_sources=%s unlinked_sentences=%s "
            "reason=partial_link",
            section,
            len(unique_sources),
            unlinked,
        )
    return (
        stripped,
        GroundedSection(sources=unique_sources, directly_stated=unlinked == 0),
    )


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _segments_from_llm_ranges(
    ranges: list[dict],
    segments: list[SpeakerTurn],
) -> list[SpeakerTurn]:
    cited: list[SpeakerTurn] = []
    for item in ranges:
        try:
            start = float(item.get("start_s"))
            end = float(item.get("end_s"))
        except (TypeError, ValueError):
            continue
        for segment in segments:
            if segment.end_s < start or segment.start_s > end:
                continue
            cited.append(segment)
    return cited


def _normalize_for_match(text: str) -> str:
    lowered = text.lower().replace("'", "")
    return _PERSON_RE.sub(" ", lowered)


def _content_tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", _normalize_for_match(text))
    return [word for word in words if word not in _STOP and len(word) > 2]


def _token_hits(sentence: str, haystack: str) -> int:
    tokens = _content_tokens(sentence)
    hay = set(_content_tokens(haystack))
    if not tokens or not hay:
        return 0
    return sum(1 for tok in tokens if tok in hay)


def _sentence_supported_by(sentence: str, segments: list[SpeakerTurn]) -> bool:
    """True when the sentence is a reasonable paraphrase of the combined segments."""
    tokens = _content_tokens(sentence)
    if not tokens:
        return False
    blob_tokens = set()
    for segment in segments:
        blob_tokens.update(_content_tokens(segment.text))
    hits = sum(1 for tok in tokens if tok in blob_tokens)
    if hits >= 2 and hits / len(tokens) >= 0.35:
        return True
    # Short paraphrase ("Patient is tired of it" / "I'm tired of it").
    distinctive = [tok for tok in tokens if len(tok) >= 5]
    return (
        len(tokens) <= 4
        and hits >= 1
        and any(tok in blob_tokens for tok in distinctive)
    )


def _is_family_history_segment(text: str) -> bool:
    return bool(_FAMILY_RE.search(text.lower()))


def _filter_candidates(sentence: str, candidates: list[SpeakerTurn]) -> list[SpeakerTurn]:
    """Drop weak, far-apart, or family-history extras. Empty means sources unclear."""
    if not candidates:
        return []
    claim_is_family = _is_family_history_segment(sentence)
    scored: list[tuple[int, SpeakerTurn]] = []
    for segment in candidates:
        if _is_family_history_segment(segment.text) and not claim_is_family:
            continue
        score = _token_hits(sentence, segment.text)
        if score:
            scored.append((score, segment))
    if not scored:
        return []
    scored.sort(key=lambda item: item[0], reverse=True)
    best = scored[0][0]
    # Require a near-best score so a shared topic word is not enough.
    floor = max(2, math.ceil(best * 0.6)) if best >= 2 else best
    strong = [(score, seg) for score, seg in scored if score >= floor]
    if not strong:
        # Several weak topical hits far apart → cite nothing.
        if len(scored) > 1:
            span = max(s.end_s for _, s in scored) - min(s.start_s for _, s in scored)
            if span > 20:
                return []
        if best >= 1 and len(scored) == 1:
            return [scored[0][1]]
        return []
    strong.sort(key=lambda item: item[0], reverse=True)
    anchor = strong[0][1]
    clustered = [
        seg
        for score, seg in strong
        if abs(((seg.start_s + seg.end_s) / 2) - ((anchor.start_s + anchor.end_s) / 2))
        <= 25
    ]
    if not clustered:
        return [anchor]
    # If even the clustered set still spans a long gap, keep only the anchor.
    cluster_span = max(s.end_s for s in clustered) - min(s.start_s for s in clustered)
    if cluster_span > 35 and len(clustered) > 1:
        return [anchor]
    return clustered[:3]


def _best_segments_for_sentence(
    sentence: str,
    segments: list[SpeakerTurn],
) -> list[SpeakerTurn]:
    if not segments or not _sentence_supported_by(sentence, segments):
        return []
    return _filter_candidates(sentence, segments)


def _to_sources(segments: list[SpeakerTurn]) -> list[NoteSource]:
    return [
        NoteSource(start_s=segment.start_s, end_s=segment.end_s, text=segment.text)
        for segment in segments
    ]


def _dedupe_sources(sources: list[NoteSource]) -> list[NoteSource]:
    seen: set[tuple[float, float, str]] = set()
    unique: list[NoteSource] = []
    for source in sources:
        key = (round(source.start_s, 2), round(source.end_s, 2), source.text)
        if key in seen:
            continue
        seen.add(key)
        unique.append(source)
    return unique
