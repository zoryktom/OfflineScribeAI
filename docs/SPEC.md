# OfflineScribeAI research upgrade specification

Single source of truth for the evaluation artifact. Deviations go under Changelog with a rationale.

## Purpose and scope

Turn the local scribe prototype into a biomedical informatics methods artifact:

1. A formulated research question and study design
2. A reusable error taxonomy for clinical documentation AI
3. An annotated benchmark (OfflineScribeAI-Bench)
4. A reproducible evaluation harness with ablations
5. A clinician-rated human-factors evaluation
6. Interoperability, privacy, and audit infrastructure
7. A paper skeleton suitable for later preprint and venue submission

Out of scope: new UI features, clinical deployment claims, real PHI without IRB, training weights from scratch.

Governing rule: a change must increase research rigor, reproducibility, or dissemination. App polish alone is out of scope.

The interactive FastAPI/React workstation stays in `backend/` and `desktop-app/`. The research package lives in `src/offlinescribe/`. Live FHIR POST stays off unless an explicit environment flag is set.

## Target layout

```
docs/                  research protocols
src/offlinescribe/     evaluation package and CLI
data/                  synthetic encounters, schemas, annotations
experiments/           configs and run outputs
notebooks/             analysis notebooks
paper/                 manuscript skeleton
tests/                 harness tests
```

Acceptance for the package: `pip install -e .` works, `pytest tests` passes, `offlinescribe eval run --config experiments/configs/pilot.yaml` writes a seeded table. Docker and CI are provided. Human κ, clinician ICC, live-model ablations, arXiv, and venue submission are not claimed until those studies are run.

## Conditions and models

Conditions: `baseline`, `rag`, `rag_grounded`, `rag_grounded_verified`.

Models (planned): Llama 3.1 8B, Qwen2.5 14B, Mistral 7B, GPT-4o-mini as reference.

ASR (planned): Whisper tiny, base, medium, large-v3.

The committed runner uses a deterministic stub generator so CI can finish without GPU or API keys.

## Workstreams

1. Repository layout and package install
2. Research framing documents
3. Taxonomy, annotation CLI, JSON Schema
4. Metrics, ablation runner, statistics
5. Clinician instruments and workflow log
6. FHIR dry-run, de-identification, audit, reproducibility files
7. Analysis notebooks
8. Paper skeleton, related work, limitations, README

Human data collection, live ablations, preprint, and submission are separate from this engineering work.

## Honest reporting

Do not invent H1–H4 numbers, Cohen's κ, clinician ICC, or an arXiv identifier. Seed annotations are planted-token labels. Stub ablation tables are perturbations.

## Changelog

- 2026-10-02: Research package and protocols added beside the existing workstation. Stub generator used for CI. Human annotation and clinician review not yet collected. Live FHIR write remains refused.
