"""Regex de-identification for synthetic fixtures. Not a PHI de-ID product."""

from __future__ import annotations

import json
import re
from pathlib import Path

_PATTERNS = {
    "mrn": re.compile(r"\bMRN[:\s-]*\d{4,12}\b", re.IGNORECASE),
    "date": re.compile(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b"),
    "phone": re.compile(r"\b\d{3}[-.]\d{3}[-.]\d{4}\b"),
    "name_label": re.compile(r"\b(?:patient|pt)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b"),
    "location": re.compile(r"\b(?:Rochester|Nashville|clinic on \w+)\b", re.IGNORECASE),
}


def deidentify(text: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    out = text
    for name, pattern in _PATTERNS.items():
        matches = pattern.findall(out)
        counts[name] = len(matches)
        out = pattern.sub(f"[{name.upper()}]", out)
    return out, counts


def report(path: Path, items: list[tuple[str, str]]) -> dict:
    """items: list of (original, expected_redacted_token). Precision/recall vs labels."""
    tp = fp = fn = 0
    details = []
    for original, expected in items:
        redacted, counts = deidentify(original)
        hit = expected.lower() in redacted.lower() or expected not in redacted
        if expected in original and expected not in redacted:
            tp += 1
        elif expected in original and expected in redacted:
            fn += 1
        details.append({"counts": counts, "redacted": redacted, "hit": hit})
    prec = tp / (tp + fp) if (tp + fp) else 1.0
    rec = tp / (tp + fn) if (tp + fn) else 1.0
    payload = {"precision": prec, "recall": rec, "n": len(items), "details": details}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
