"""Automatic metrics. Overlap / string methods, not clinical validation."""

from __future__ import annotations

import re

from offlinescribe.eval.taxonomy import Annotation, EncounterNote, Severity

_LATERALITY = re.compile(r"\b(left|right|bilateral)\b", re.IGNORECASE)
_NEGATION = re.compile(
    r"\b(no|not|deny|denies|denied|never|without|doesn't|don't)\b",
    re.IGNORECASE,
)
_DOSE = re.compile(r"\b(\d+(?:\.\d+)?)\s*(mg|mcg|units|iu)\b", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def wer(reference: str, hypothesis: str) -> float:
    ref = tokenize(reference)
    hyp = tokenize(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    dp = [[0] * (len(hyp) + 1) for _ in range(len(ref) + 1)]
    for i in range(len(ref) + 1):
        dp[i][0] = i
    for j in range(len(hyp) + 1):
        dp[0][j] = j
    for i, r_tok in enumerate(ref, start=1):
        for j, h_tok in enumerate(hyp, start=1):
            cost = 0 if r_tok == h_tok else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + cost,
            )
    return dp[-1][-1] / len(ref)


def rouge_l(reference: str, hypothesis: str) -> float:
    ref = tokenize(reference)
    hyp = tokenize(hypothesis)
    if not ref or not hyp:
        return 0.0
    n, m = len(ref), len(hyp)
    prev = [0] * (m + 1)
    for i in range(1, n + 1):
        cur = [0] * (m + 1)
        for j in range(1, m + 1):
            if ref[i - 1] == hyp[j - 1]:
                cur[j] = prev[j - 1] + 1
            else:
                cur[j] = max(prev[j], cur[j - 1])
        prev = cur
    lcs = prev[-1]
    prec = lcs / len(hyp)
    rec = lcs / len(ref)
    if prec + rec == 0:
        return 0.0
    return 2 * prec * rec / (prec + rec)


def bertscore(*_args, **_kwargs) -> float:
    """Placeholder. Do not treat as BERTScore. Use rouge_l in this harness."""
    raise NotImplementedError("BERTScore is not bundled. Use rouge_l.")


def medication_f1(gold_meds: list[str], generated: str) -> float:
    gen = tokenize(generated)
    if not gold_meds:
        return 1.0
    hits = 0
    for med in gold_meds:
        tokens = tokenize(med)
        if tokens and all(tok in gen for tok in tokens):
            hits += 1
    prec = hits / max(1, len(set(gen) & {tokenize(m)[0] for m in gold_meds if tokenize(m)}))
    rec = hits / len(gold_meds)
    if prec + rec == 0:
        return 0.0
    return 2 * prec * rec / (prec + rec)


def dose_exact_match(gold: str, generated: str) -> float:
    gold_doses = sorted(_DOSE.findall(gold.lower()))
    gen_doses = sorted(_DOSE.findall(generated.lower()))
    if not gold_doses:
        return 1.0
    return float(gold_doses == gen_doses)


_NEGATION_STOP = {"deny", "denies", "denied", "never", "without", "that", "this", "have", "with"}


def negation_accuracy(source: str, generated: str) -> float:
    """Heuristic: tokens after a negation cue must not appear asserted in the draft."""
    negated: set[str] = set()
    for sent in re.split(r"(?<=[.!?])\s+", source or ""):
        match = _NEGATION.search(sent.lower())
        if not match:
            continue
        for token in tokenize(sent[match.end() :]):
            if len(token) >= 4 and token not in _NEGATION_STOP:
                negated.add(token)
    if not negated:
        return 1.0
    gen_sents = re.split(r"(?<=[.!?])\s+", generated or "")
    ok = 0
    for token in negated:
        asserted = any(
            token in sent.lower() and not _NEGATION.search(sent) for sent in gen_sents
        )
        if not asserted:
            ok += 1
    return ok / len(negated)


def laterality_accuracy(source: str, generated: str) -> float:
    src = set(m.group(1).lower() for m in _LATERALITY.finditer(source or ""))
    gen = set(m.group(1).lower() for m in _LATERALITY.finditer(generated or ""))
    if not src:
        return 1.0
    return len(src & gen) / len(src)


def icd_f1(gold_codes: list[str], pred_codes: list[str]) -> float:
    gold, pred = set(gold_codes), set(pred_codes)
    if not gold and not pred:
        return 1.0
    if not gold or not pred:
        return 0.0
    prec = len(gold & pred) / len(pred)
    rec = len(gold & pred) / len(gold)
    if prec + rec == 0:
        return 0.0
    return 2 * prec * rec / (prec + rec)


def hallucination_rate(source: str, generated: str) -> float:
    """Token novelty vs transcript. Not NLI."""
    src = set(tokenize(source))
    gen = tokenize(generated)
    if not gen:
        return 0.0
    novel = [tok for tok in gen if tok not in src and len(tok) > 3]
    return len(novel) / len(gen)


def omission_rate(gold_entities: list[str], generated: str) -> float:
    if not gold_entities:
        return 0.0
    gen = " ".join(tokenize(generated))
    missed = [ent for ent in gold_entities if tokenize(ent)[0] not in gen]
    return len(missed) / len(gold_entities)


def edit_distance_normalized(gold: str, generated: str) -> float:
    return wer(gold, generated)


def citation_precision(cited: list[str], source_spans: list[str]) -> float:
    if not cited:
        return 1.0
    src = " ".join(source_spans).lower()
    hits = sum(1 for span in cited if span.lower() in src)
    return hits / len(cited)


def citation_recall(cited: list[str], required_spans: list[str]) -> float:
    if not required_spans:
        return 1.0
    cited_l = " ".join(cited).lower()
    hits = sum(1 for span in required_spans if span.lower() in cited_l)
    return hits / len(required_spans)


def flatten_note(note: EncounterNote) -> str:
    return " ".join([note.subjective, note.objective, note.assessment, note.plan])


def clinical_error_score(annotations: list[Annotation]) -> float:
    weights = {
        Severity.CRITICAL: 10,
        Severity.MAJOR: 5,
        Severity.MODERATE: 2,
        Severity.MINOR: 0.5,
        Severity.NONE: 0,
    }
    if not annotations:
        return 0.0
    return sum(weights[item.severity] for item in annotations) / len(annotations)


def score_pair(source: str, gold: EncounterNote, generated: EncounterNote, gold_meds: list[str], gold_entities: list[str]) -> dict[str, float]:
    gold_text = flatten_note(gold)
    gen_text = flatten_note(generated)
    return {
        "wer": wer(gold_text, gen_text),
        "rouge_l": rouge_l(gold_text, gen_text),
        "medication_f1": medication_f1(gold_meds, gen_text),
        "dose_exact_match": dose_exact_match(gold_text, gen_text),
        "negation_accuracy": negation_accuracy(source, gen_text),
        "laterality_accuracy": laterality_accuracy(source, gen_text),
        "hallucination_rate": hallucination_rate(source, gen_text),
        "omission_rate": omission_rate(gold_entities, gen_text),
        "edit_distance_normalized": edit_distance_normalized(gold_text, gen_text),
    }
