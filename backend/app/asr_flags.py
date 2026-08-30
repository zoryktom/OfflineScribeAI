"""Flag low-confidence or unusual medication-like ASR tokens for human review.

Does not rewrite the transcript. The starter list is not a formulary.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from app.models import AsrFlag, SpeakerTurn

_DATA = Path(__file__).resolve().parent / "data" / "medication_starter.txt"
_TOKEN = re.compile(r"[A-Za-z][A-Za-z\-]{2,}")
# Observed garbles from synthetic evaluation (not a complete ASR error catalog).
_KNOWN_GARBLES = {
    "liz": "lisinopril",
    "astatin": "atorvastatin",
}
_LOW_CONFIDENCE = 0.45


@lru_cache(maxsize=1)
def load_medication_names() -> frozenset[str]:
    names = {
        line.strip().lower()
        for line in _DATA.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    return frozenset(names)


def flag_asr_concerns(
    segments: list[SpeakerTurn],
    *,
    words: list[tuple[str, float, float, float | None]] | None = None,
) -> list[AsrFlag]:
    """Return review flags. `words` items are (text, start_s, end_s, probability)."""
    names = load_medication_names()
    flags: list[AsrFlag] = []
    seen: set[tuple[float, float, str, str]] = set()

    hits = words if words is not None else _tokens_from_segments(segments)
    for text, start_s, end_s, probability in hits:
        token = text.strip().strip(".,;:!?\"'").lower()
        if not token or token in names:
            continue
        reason: str | None = None
        if token in _KNOWN_GARBLES:
            reason = "unusual_medication_token"
        elif _close_to_medication(token, names):
            reason = "unusual_medication_token"
        elif probability is not None and probability < _LOW_CONFIDENCE and (
            token in _KNOWN_GARBLES or _close_to_medication(token, names, max_ratio=0.5)
        ):
            reason = "low_confidence"
        if reason is None:
            continue
        key = (round(start_s, 2), round(end_s, 2), token, reason)
        if key in seen:
            continue
        seen.add(key)
        flags.append(
            AsrFlag(start_s=start_s, end_s=end_s, text=text.strip(), reason=reason)
        )
    return flags


def _tokens_from_segments(
    segments: list[SpeakerTurn],
) -> list[tuple[str, float, float, float | None]]:
    hits: list[tuple[str, float, float, float | None]] = []
    for segment in segments:
        for match in _TOKEN.finditer(segment.text):
            hits.append((match.group(0), segment.start_s, segment.end_s, None))
    return hits


def _close_to_medication(
    token: str, names: frozenset[str], *, max_ratio: float = 0.34
) -> bool:
    if len(token) < 4:
        return False
    for name in names:
        distance = _levenshtein(token, name)
        limit = max(1, int(round(len(name) * max_ratio)))
        if 0 < distance <= limit:
            return True
    return False


def _levenshtein(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for i, lch in enumerate(left, start=1):
        current = [i]
        for j, rch in enumerate(right, start=1):
            insert = current[j - 1] + 1
            delete = previous[j] + 1
            replace = previous[j - 1] + (lch != rch)
            current.append(min(insert, delete, replace))
        previous = current
    return previous[-1]
