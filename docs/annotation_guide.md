# Annotation guide

Use with `docs/error_taxonomy.md` and `offlinescribe annotate`.

## Workflow

1. Open the encounter (`--encounter E00N`) and the condition name from `docs/study_design.md`.
2. Read the transcript, then the gold note, then the generated note.
3. Mark every span that is an error. One span, one `ErrorType`. Split a sentence if it contains two errors.
4. Assign severity from the rubric before writing the rationale.
5. Write one sentence that a second annotator can check without re-deriving the rule.
6. Save. The CLI appends `data/annotations/{annotator}.jsonl` and skips duplicates for the same encounter + condition + annotator.

```bash
offlinescribe annotate --encounter E001 --condition rag_grounded --annotator A1 --output data/annotations/A1.jsonl
```

Resume is automatic. Already-written triples are skipped.

Keys in the interactive path: `o` omission, `h` hallucination, `n` negation_flip, `l` laterality, `m` medication, `d` dose, `t` temporality, `a` attribution, `i` icd_instability, `p` asr_propagation, `s` style_only, `q` quit.

## Decision tree

```
Is the generated text supported by the transcript?
├── No → HALLUCINATION
│   └── Is it clinically significant? → set severity
└── Yes → Does it contradict the transcript?
    ├── Yes → is it a negation, laterality, dose, med, or temporality?
    │         → corresponding error type
    └── No → Is anything clinically relevant missing?
        ├── Yes → OMISSION
        └── No → STYLE_ONLY or None
```

If ASR text leaked from a hypothesis distinct from the gold transcript, label `asr_propagation`. If ICD codes move across seeds, label `icd_instability`.

## Tie-breaking

- Prefer the type that a clinician would name first when explaining the edit.
- If severity is on the fence, choose the **higher** severity and say so in the rationale.
- Do not invent a second error to raise κ. Empty is allowed.
- `clinically_significant` is true for moderate and above.

## Calibration

Before labeling the study set, both annotators label the ten worked examples below, then compare. Discuss every disagreement. Recalibrate if κ on major/critical is below 0.6 on a 20-encounter pilot. The adjudicator does not label the pilot.

## Worked examples

1. **Denied tinnitus written as a diagnosis.** Type `negation_flip`, severity major. Rationale: “denied token asserted in assessment.”
2. **Gold lists lisinopril 10 mg; draft lists losartan 50 mg.** Type `medication`, severity critical.
3. **Dose 10 mg becomes 40 mg, same drug.** Type `dose`, severity critical for antihypertensives.
4. **Left ankle becomes right ankle.** Type `laterality`, severity major.
5. **“Well controlled on all medications” with no source.** Type `hallucination`, severity moderate.
6. **Fatigue present in gold, absent in draft.** Type `omission`, severity moderate.
7. **“HTN” vs “hypertension.”** Type `style_only`, severity minor.
8. **ASR “liz in April” copied into the plan.** Type `asr_propagation` (and the span is the garbled name), severity major.
9. **Same transcript, I10 on seed 0 and J06.9 on seed 1.** Type `icd_instability`, severity major.
10. **Clinician speculated about family history; note says the patient reported it.** Type `attribution`, severity moderate.

## What the committed JSONL is

`data/annotations/A1.jsonl` and `A2.jsonl` are generated from planted tokens so loaders and notebooks have rows. They are not evidence of κ ≥ 0.6. Replace them after human annotation. Store adjudication in `data/annotations/adjudicated.jsonl`.
