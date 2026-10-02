# Workflow study

The evaluation unit in `docs/study_design.md` is the encounter. This document covers the **path from first draft to signed note** as a sociotechnical process. It does not claim a deployment study.

## Framing

**Distributed cognition.** The draft, the transcript, the ICD table, and the named reviewer are one system. Errors can sit in the note, in the reviewer’s memory of the visit, or in a missed denial. Time-to-sign is not only model quality.

**Human–AI teaming.** The reviewer is not a backup OCR checker. The protocol asks whether they would sign, how long they edit, and whether trust tracks error counts (calibration). Over-trust is signing a hallucinated allergy denial. Under-trust is rewriting a faithful note from scratch.

**Trust calibration.** H4 in `docs/research_question.md` predicts edit time from omission count more than hallucination count. That is a calibration hypothesis: missing text may be slower to notice than invented text.

**Implementation science.** If this workstation were placed in a clinic, CFIR (inner setting, individuals, process) and NASSS (condition, technology, adopters, organization) would structure barriers. This repo does not run a CFIR interview study. Use those constructs when writing field notes: who reviews the draft, who is named as responsible, and what happens when the model is down.

Related conceptual sources are listed in `docs/related_work.md` (Sittig–Singh sociotechnical model, Five Rights of CDS, DIKW).

## Instruments

- NASA-TLX (raw) after a block of notes: mental, physical, temporal, performance, effort, frustration.
- SUS (optional, 10 items) for the workstation, not for a single note.
- Workflow event log in `src/offlinescribe/eval/workflow.py`: `open`, `first_draft`, `edit`, `sign`, `reject`, with `time.perf_counter()`.

## Planned sample

Collect workflow metrics for ≥10 encounters per reviewer after IRB determination and consent. Pair those rows with the condition names from `docs/study_design.md`. Until then, the event logger is instrumentation only.
