"""Look up ICD-10-CM codes from a local starter file — never from LLM memory.

Starter descriptions come from CMS ICD-10-CM FY 2026 Code Descriptions in
Tabular Order (https://www.cms.gov/medicare/coding-billing/icd-10-codes).
This is not a complete coding reference.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from app.models import SuggestedIcd10

_DATA_PATH = Path(__file__).resolve().parent / "data" / "icd10_starter.json"
UNMATCHED_CODE = "UNMATCHED"
UNMATCHED_DESCRIPTION = "No matching code found — manual coding needed"

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
    "without",
    "unspecified",
    "acute",
    "due",
}


def lookup_diagnoses(phrases: list[str]) -> list[SuggestedIcd10]:
    """Map plain-language diagnoses to starter-set codes. Never invent a code."""
    found: list[SuggestedIcd10] = []
    seen: set[str] = set()
    unmatched_phrases: list[str] = []
    for raw in phrases:
        phrase = (raw or "").strip()
        if not phrase:
            continue
        match = _best_match(phrase)
        if match is None:
            unmatched_phrases.append(phrase)
            continue
        if match.code in seen:
            continue
        seen.add(match.code)
        found.append(
            SuggestedIcd10(
                code=match.code,
                description=match.description,
                accepted=None,
            )
        )
    if found:
        return found
    return [
        SuggestedIcd10(
            code=UNMATCHED_CODE,
            description=UNMATCHED_DESCRIPTION,
            accepted=None,
        )
    ]


@lru_cache(maxsize=1)
def load_starter_set() -> list[dict]:
    payload = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    return list(payload["codes"])


def _looks_like_icd10_code(phrase: str) -> bool:
    """True when the model leaked a recalled code (e.g. J40.0) instead of a name."""
    compact = re.sub(r"[^a-z0-9]", "", phrase.lower())
    return bool(re.fullmatch(r"[a-z][0-9]{2}[0-9a-z]{0,4}", compact))


def _best_match(phrase: str) -> SuggestedIcd10 | None:
    # Never accept a model-recalled code string as if it were a diagnosis name.
    if _looks_like_icd10_code(phrase):
        return None
    normalized = _normalize(phrase)
    if not normalized:
        return None
    negated = bool(re.search(r"\b(no|not|without|denies|denied|ruled out)\b", normalized))
    best: tuple[int, SuggestedIcd10] | None = None
    for row in load_starter_set():
        aliases = [_normalize(row["description"]), *(_normalize(a) for a in row.get("aliases", []))]
        score = 0
        for alias in aliases:
            if not alias:
                continue
            if alias == normalized:
                score = max(score, 100 + len(alias))
            elif alias in normalized or normalized in alias:
                if negated and alias != normalized:
                    continue
                if len(alias) >= 6:
                    score = max(score, 70 + len(alias))
            else:
                overlap = _token_overlap(normalized, alias)
                if overlap >= 0.55:
                    score = max(score, int(50 + overlap * 20) + len(alias.split()))
        if score > 0 and (best is None or score > best[0]):
            best = (
                score,
                SuggestedIcd10(
                    code=row["code"],
                    description=row["description"],
                    accepted=None,
                ),
            )
    if best is None or best[0] < 70:
        return None
    return best[1]


def _normalize(text: str) -> str:
    lowered = re.sub(r"\buri\b", "upper respiratory infection", text.lower())
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _token_overlap(left: str, right: str) -> float:
    a = {tok for tok in left.split() if tok not in _STOP}
    b = {tok for tok in right.split() if tok not in _STOP}
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)
