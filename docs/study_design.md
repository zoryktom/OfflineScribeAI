# Study design

Unit of analysis: **encounter** (transcript → note). One row in `data/synthetic/manifest.jsonl` is one encounter.

## Conditions

These are the only study-arm names. Unknown names fail closed in `src/offlinescribe/pipeline/run.py`.

| name | rag | grounding | verifier | intent |
|---|---|---|---|---|
| `baseline` | false | false | false | Draft from transcript only. Highest expected fabrication. |
| `rag` | true | false | false | Retrieve similar synthetic notes / problem lists; no span lock. |
| `rag_grounded` | true | true | false | Retrieved context plus span attribution. Expected: fewer hallucinations, more omissions. |
| `rag_grounded_verified` | true | true | true | Grounded draft plus a second-pass assertion / ICD check. |

These four names are the only legal `condition` values in `data/schemas/annotation.schema.json`.

## Models

Planned comparison set (not all required for a stub run):

- Llama 3.1 8B (`llama3.1:8b`) — local open-weight
- Qwen2.5 14B (`qwen2.5:14b`) — local, above the 13B cut in H3
- Mistral 7B (`mistral:7b`) — local open-weight
- GPT-4o-mini (`gpt-4o-mini`) — frontier API reference only; never the default in this repo

The interactive app still defaults to local Ollama. API calls are out of scope for `DEMO_MODE` and for any live visit path.

## ASR

Whisper-family variants for RQ2 / H2:

- `whisper-tiny`
- `whisper-base`
- `whisper-medium`
- `whisper-large-v3`

The sample CI config uses `whisper-large-v3` only. Full ablation is `experiments/configs/ablation_v1.yaml`.

## Sample size

Minimum **100** synthetic encounters (`data/synthetic/manifest.jsonl`). Target 200 if templates are expanded. No real PHI. Power is for paired condition contrasts on binary error flags (McNemar) and for mixed-effects models with encounter as a random intercept.

## Annotation

- Two annotators (`A1`, `A2`) label generated spans using `docs/annotation_guide.md`.
- A third adjudicator (`ADJ`) resolves disagreements.
- Store raw labels in `data/annotations/{annotator}.jsonl` and the resolved set in `data/annotations/adjudicated.jsonl`.
- Report Cohen's κ per `ErrorType` in `notebooks/01_error_analysis.ipynb`.
- Target: κ ≥ 0.6 on major and critical categories before locking the analysis set.

The committed `A1` / `A2` / `ADJ` files are **programmatic seed labels** from planted tokens. They exist so the schema and loaders have data. They are not human IAA.

## Analysis plan

- **Paired binary errors** (same encounter, two conditions): McNemar.
- **Continuous metrics** (WER, omission rate, edit time): Wilcoxon signed-rank on paired differences; mixed-effects models with encounter random intercept and fixed effects for condition, model, ASR.
- **Agreement:** Cohen's κ per error type; ICC(2,k) for PDQI-9 and trust.
- **H2:** Pearson / Spearman correlation of encounter WER with negation-flip and medication error rates.
- **H4:** Regression of edit time on omission count vs hallucination count, reviewer random intercept.
- **Multiplicity:** Holm–Bonferroni on the pre-specified family (H1–H4 plus the four condition pairwise tests on clinical_error_score).
- **Uncertainty:** percentile bootstrap 95% CIs (`src/offlinescribe/eval/stats.py`).

## What the stub runner does

`offlinescribe eval run` does **not** call Llama, Qwen, Mistral, or GPT. It applies seeded string perturbations that follow the condition table so CI can finish. Replace `src/offlinescribe/pipeline/run.py` with a live backend call when measuring real models.

## Interactive prototype (out of the factorial)

`backend/` remains the named-review workstation: faster-whisper → SOAP → grounding → ICD table → human review. Live FHIR POST stays disabled. `DEMO_MODE` stays synthetic-only. That path is for workflow inspection, not for the 100 × 4 × 4 × 2 factorial.
