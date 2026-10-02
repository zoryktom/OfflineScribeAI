# Research Question

## Primary

How do local-first LLM scribes fail in clinical documentation, and which grounding and mitigation strategies reduce clinically meaningful errors without introducing new failure modes?

## Secondary

- RQ2: How do ASR errors propagate into clinically significant note errors (negation, laterality, medication, dose)?
- RQ3: Does retrieval-augmented grounding reduce hallucination at the cost of increased omission?
- RQ4: How do local open-weight models compare to frontier API models on documentation fidelity and edit burden?
- RQ5: What is the human edit burden and trust calibration when clinicians review AI-drafted notes?

## Hypotheses

- H1: Grounding reduces hallucination rate by >=30% relative but increases omission rate.
- H2: ASR word error rate correlates with negation-flip and medication error rates (r > 0.5).
- H3: Local models <= 13B params show higher omission but lower fabrication than frontier models.
- H4: Clinician edit time is predicted by omission count more than hallucination count.

## Significance

Clinical documentation burden is a leading driver of clinician burnout. Ambient AI scribes promise relief but introduce new failure modes (hallucination, omission, negation flips) that are poorly characterized. This repository supplies a taxonomy, a PHI-free encounter set, and a seeded evaluation harness so those failure modes can be measured. It does not yet report a completed multi-annotator or clinician study.

## What is measured today

The interactive prototype in `backend/` drafts SOAP text, grounds spans, and looks up ICD-10 codes from a local table. Live EHR writes stay off. `offlinescribe eval run` applies deterministic perturbations so metrics and CIs can be checked. Those stub numbers are not H1–H4 results.
