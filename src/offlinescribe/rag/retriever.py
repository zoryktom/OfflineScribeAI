"""Lexical retrieval over gold notes in the synthetic corpus."""

from __future__ import annotations

from offlinescribe.eval.metrics import tokenize
from offlinescribe.eval.taxonomy import Encounter


def retrieve(query: str, corpus: list[Encounter], k: int = 3) -> list[Encounter]:
    q = set(tokenize(query))
    if not q:
        return corpus[:k]
    scored = []
    for row in corpus:
        toks = set(tokenize(row.transcript))
        scored.append((len(q & toks), row))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [row for _, row in scored[:k]]
