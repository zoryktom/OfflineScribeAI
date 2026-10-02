"""Second-pass checks used by the rag_grounded_verified condition."""

from __future__ import annotations

from offlinescribe.eval.metrics import _DOSE, _NEGATION


def verify(generated: str, source: str) -> list[str]:
    flags: list[str] = []
    if _DOSE.search(generated) and not _DOSE.search(source):
        flags.append("dose_not_in_source")
    if _NEGATION.search(source) and not _NEGATION.search(generated):
        flags.append("source_negation_missing_in_draft")
    return flags
