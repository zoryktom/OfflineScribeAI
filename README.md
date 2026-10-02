# OfflineScribeAI: A Local-First Evaluation Harness for Clinical Documentation LLMs

[License: MIT](LICENSE)

**Author:** Zorykto Mykola. There are no other authors.

Research prototype. **Not for clinical use.** Not FDA-cleared, not clinically validated, not HIPAA-certified. No live EHR write.

## Research Question

How do local-first LLM scribes fail in clinical documentation, and which grounding and mitigation strategies reduce clinically meaningful errors without introducing new failure modes?

Secondary questions (ASR propagation, grounding–omission tradeoff, local vs frontier models, clinician edit burden and trust) are in [`docs/research_question.md`](docs/research_question.md). Study arms are [`docs/study_design.md`](docs/study_design.md): `baseline`, `rag`, `rag_grounded`, `rag_grounded_verified`.

## Key Findings

H1–H4 are **hypotheses**, not measured results in this commit.

- **H1:** Grounding reduced hallucination by X% (95% CI …) but increased omission by Y%. **Unmeasured.** Stub perturbations are not this number.
- **H2:** ASR WER correlated with negation-flip rate (r = …, p < …). **Unmeasured.**
- **H3:** Local models ≤ 13B showed higher omission and lower fabrication than a frontier reference. **Unmeasured.**
- **H4:** Clinician edit time was predicted by omission count more than hallucination count. **Unmeasured.** (N = 0 reviewers in the tree.)

Do not copy stub `experiments/runs/` means into a paper as model findings.

The interactive workstation still has a **small-sample planted-error measurement** (not H1–H4): live `llama3:8b` assertion check **6/6** catch vs keyword **0/6**, false positives **2/4** vs **3/4**. Tables: [`docs/evaluation.md`](docs/evaluation.md).

## System

Audio or script → faster-whisper → local SOAP draft → span grounding → deterministic ICD-10 table → **named human review**. Live FHIR POST is refused. `DEMO_MODE` is a synthetic explorer only.

The evaluation package lives in `src/offlinescribe/`. The interactive FastAPI/React app remains in `backend/` and `desktop-app/`. Pipeline figure: see the architecture diagram in git history of the workstation path, or `paper/figures/` after you export one from a run.

**Privacy posture:** loopback API, local models, SQLCipher for visits, no cloud inference on the default path. That is a design choice, not a certification. See [`docs/model_card.md`](docs/model_card.md) and [`docs/data_card.md`](docs/data_card.md).

## Benchmark

**OfflineScribeAI-Bench:** 100 synthetic encounters (`data/synthetic/manifest.jsonl`), planted-token seed labels (not human IAA), error taxonomy, annotation guide.

- Taxonomy: [`docs/error_taxonomy.md`](docs/error_taxonomy.md)
- Annotation: [`docs/annotation_guide.md`](docs/annotation_guide.md)
- Schema: [`data/schemas/annotation.schema.json`](data/schemas/annotation.schema.json)
- Limitations: [`docs/limitations.md`](docs/limitations.md)
- Methods spec: [`docs/SPEC.md`](docs/SPEC.md)

Human dual annotation, adjudication, and κ ≥ 0.6 on major/critical categories are **not** in this tree yet.

## Reproduce

```bash
make install
make test
make eval
```

`make eval` runs the **sample** stub ablation (`experiments/configs/sample.yaml`) plus the existing backend planted-error harness. Full factorial config: `make eval-full` (still a stub generator unless you replace `src/offlinescribe/pipeline/run.py`).

```bash
pip install -e .
pytest tests
offlinescribe eval run --config experiments/configs/sample.yaml
offlinescribe annotate --encounter E001 --condition rag_grounded --annotator A1
offlinescribe pipeline --encounter E001 --condition baseline
docker compose up --build
```

Fresh clone + `make eval` reproduces the stub headline table for a fixed corpus and seed. It does not reproduce unpublished human or live-model numbers.

## Citation

```bibtex
@software{mykola2026offlinescribe,
  author = {Mykola, Zorykto},
  title  = {OfflineScribeAI: A Local-First Evaluation Harness for Clinical Documentation LLMs},
  year   = {2026},
  url    = {https://github.com/zoryktom/OfflineScribeAI}
}
```

Also see `CITATION.cff`. No DOI until a Zenodo tag is cut. No arXiv badge until a preprint exists.

## Clinical Disclaimer

Research prototype. Not for clinical use. Notes are drafts for a named human reviewer on synthetic or separately governed data only.
