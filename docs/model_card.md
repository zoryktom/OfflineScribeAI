# Model card (Mitchell et al. style)

**System name:** OfflineScribeAI evaluation harness and local SOAP drafter  
**Authors:** Zorykto Mykola  
**Date:** 2026-10-02  
**License:** MIT  

## Model details

The interactive path uses local faster-whisper for ASR and a local Ollama chat model (default Llama 3 8B class) for SOAP drafts and for assertion classification. ICD-10 codes come from a deterministic CMS-derived lookup, not from model recall. The research package in `src/offlinescribe/` ships a **stub generator** so ablations run without a GPU or an API key.

This card describes the **system**, not a newly trained weight file.

## Intended use

- Research measurement of documentation errors on **synthetic** encounters.
- Supervised review of drafts by a named person.
- Teaching and methods work on grounding, negation, and edit burden.

## Out of scope

- Patient care, diagnosis, or treatment.
- Unsupervised signing.
- Live EHR writes (FHIR POST stays disabled).
- Claiming FDA clearance, HIPAA certification, or clinical validation.

## Factors and metrics

Primary metrics are in `src/offlinescribe/eval/metrics.py` and the taxonomy in `docs/error_taxonomy.md`. Do not treat ROUGE as a clinical quality score. The clinically weighted score uses annotation severity weights (critical 10, major 5, moderate 2, minor 0.5).

## Training data

No weights are trained in this repository. Upstream model cards for Llama, Qwen, Mistral, Whisper, and any API model apply to those weights.

## Evaluation data

Synthetic templates in `data/synthetic/manifest.jsonl`. See `docs/data_card.md`.

## Ethical considerations

A fluent wrong note can look signable. The UI watermark and DEMO_MODE exist to keep synthetic work from being mistaken for a chart. Local inference is a privacy posture, not a compliance certificate.

## Caveats

Stub ablation numbers are perturbations, not model benchmarks. Human κ and clinician ICC are unmeasured until the protocols are run.
