# Research questions

This document states the questions the evaluation harness is built to answer. It does not report results. Headline numbers belong in `experiments/runs/` after a seeded run, or in a later paper after human annotation and clinician review.

## Primary RQ

How do local-first LLM scribes fail in clinical documentation, and which grounding and mitigation strategies reduce clinically meaningful errors without introducing new failure modes?

## Secondary RQs

- **RQ2:** How do ASR errors propagate into clinically significant note errors (negation, laterality, medication, dose)?
- **RQ3:** Does retrieval-augmented grounding reduce hallucination at the cost of increased omission?
- **RQ4:** How do local open-weight models compare to frontier API models on documentation fidelity and edit burden?
- **RQ5:** What is the human edit burden and trust calibration when clinicians review AI-drafted notes?

## Hypotheses

- **H1:** Grounding reduces hallucination rate by ≥30% relative but increases omission rate.
- **H2:** ASR word error rate correlates with negation-flip and medication error rates (r > 0.5).
- **H3:** Local models ≤ 13B params show higher omission but lower fabrication than frontier models.
- **H4:** Clinician edit time is predicted by omission count more than hallucination count.

## What is and is not claimed

The interactive prototype in `backend/` drafts SOAP text from a transcript, grounds spans, looks up ICD-10 codes from a local table, and keeps live EHR writes off. That is a system under test, not evidence for H1–H4.

H1–H4 stay untested until:

1. two trained annotators label the synthetic corpus under `docs/annotation_guide.md`,
2. a third adjudicates disagreements,
3. the config in `experiments/configs/ablation_v1.yaml` is run on the models named in `docs/study_design.md`,
4. clinicians complete the protocol in `docs/clinician_protocol.md`.

Until then, `offlinescribe eval run` executes a **stub pipeline** that applies deterministic perturbations so the runner, metrics, and CIs can be checked. Those stub numbers are not model findings.

## Unit of analysis

One **encounter**: a transcript paired with a gold SOAP note. Conditions, models, and ASR variants are crossed as defined in `docs/study_design.md`.
