"""Token-overlap span linker for ablation drafts."""

from __future__ import annotations

from offlinescribe.eval.metrics import tokenize


def link_spans(generated: str, source: str) -> list[dict[str, str | bool]]:
    src = set(tokenize(source))
    out = []
    for token in tokenize(generated):
        if len(token) < 4:
            continue
        out.append({"span": token, "grounded": token in src})
    return out
