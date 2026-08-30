"""Flag SOAP sentences that assert symptoms the source only asked or denied.

Does not rewrite note text. Heuristic keyword matching, not NLI.
"""

from __future__ import annotations

import re

from app.models import SpeakerTurn, VerificationNeed

_SYMPTOMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("fever", ("fever", "febrile", "temperature")),
    ("shortness of breath", ("shortness of breath", "short of breath", "dyspnea", "sob")),
    ("chest pain", ("chest pain", "chest tightness")),
    ("cough", ("cough",)),
    ("headache", ("headache", "head pressure")),
    ("nausea", ("nausea", "nauseated")),
    ("dizziness", ("dizziness", "dizzy", "lightheaded")),
    ("weakness", ("weakness", "weak")),
    ("numbness", ("numbness", "numb")),
    ("wheeze", ("wheeze", "wheezing")),
)

_QUESTION = re.compile(
    r"\?|\b(any|do you|did you|have you|has there|is there)\b",
    re.IGNORECASE,
)
_NEGATION = re.compile(
    r"\b(no|not|don't|dont|didn't|didnt|denies|denied|never|"
    r"i don't think|i do not think|i didn't|unconfirmed)\b",
    re.IGNORECASE,
)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def flag_negation_assertions(
    sections: dict[str, str],
    source_text: str,
    segments: list[SpeakerTurn] | None = None,
) -> list[VerificationNeed]:
    """Return flags for assertive symptom sentences that conflict with source Q/negation."""
    source_chunks = [seg.text for seg in segments] if segments else [source_text]
    flags: list[VerificationNeed] = []
    seen: set[tuple[str, int, str]] = set()

    for section in ("subjective", "objective", "assessment", "plan"):
        text = (sections.get(section) or "").strip()
        if not text or text.lower() == "not documented in visit":
            continue
        sentences = [part.strip() for part in _SENTENCE_SPLIT.split(text) if part.strip()]
        for index, sentence in enumerate(sentences):
            if _sentence_is_negative(sentence):
                continue
            for _label, aliases in _SYMPTOMS:
                if not any(_contains_phrase(sentence, alias) for alias in aliases):
                    continue
                if not _source_only_asked_or_denied(aliases, source_chunks):
                    continue
                key = (section, index, "negation_or_question")
                if key in seen:
                    continue
                seen.add(key)
                flags.append(
                    VerificationNeed(
                        section=section,
                        sentence_index=index,
                        reason="negation_or_question",
                    )
                )
                break
    return flags


def _sentence_is_negative(sentence: str) -> bool:
    return bool(_NEGATION.search(sentence))


def _contains_phrase(text: str, phrase: str) -> bool:
    return bool(re.search(rf"\b{re.escape(phrase)}\b", text, flags=re.IGNORECASE))


def _source_only_asked_or_denied(aliases: tuple[str, ...], chunks: list[str]) -> bool:
    """True when every source mention of the symptom is a question and/or negation."""
    mentions = 0
    asked_or_denied = 0
    for chunk in chunks:
        if not any(_contains_phrase(chunk, alias) for alias in aliases):
            continue
        mentions += 1
        if _QUESTION.search(chunk) or _NEGATION.search(chunk):
            asked_or_denied += 1
    return mentions > 0 and asked_or_denied == mentions
