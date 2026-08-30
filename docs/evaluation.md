# Evaluation notes

These measurements come from local runs on a CPU-only 8GB Mac during development.
They are **not** a clinical benchmark, a published result, or a claim that the
system is accurate in general. Sample size is four synthetic encounters (one
original clinic visit plus three later scripts). Several LLM runs used a
**cached ASR transcript** so note-generation changes could be isolated from
ASR variance.

A planted-error harness now lives at `backend/app/eval_harness.py` with
synthetic fixtures in `backend/tests/eval/fixtures.json`. Run `make eval` or
`pytest -m eval -o addopts=` (excluded from the default suite). That harness
**measures** current flaggers; it is not a clinical benchmark.

Earlier SOAP tables below used `generate_note()` against the four encounter
scripts, with `STUB_MODE=false` and `OLLAMA_MODEL=llama3:8b`. The configured
default in `.env.example` remains `llama3.1:8b`.

Automated tests (`pytest` in `backend/`) are a separate, repeatable check.
They mock Ollama except for an opt-in live test (`RUN_OLLAMA_LIVE=1`).

---

## Synthetic encounters

All audio was generated from the dialogue scripts in `audio_samples/`
(macOS TTS, two voices). Not real patients.

| Script | Intended stress |
| --- | --- |
| `synthetic_clinic_visit_dialogue.txt` | Mixed URI + chronic meds + vitals; used for the first ASR + SOAP pass |
| `synthetic_htn_diabetes_followup_dialogue.txt` | Follow-up; family “well-controlled” talk that must not be applied to the patient |
| `synthetic_ankle_sprain_dialogue.txt` | Relatively clear injury visit + RICE / safety-netting |
| `synthetic_ambiguous_visit_dialogue.txt` | Undifferentiated story; clinician declines a single diagnosis |

Longer `.wav` files are gitignored. Re-synthesizing them will not reproduce
the original waveforms, so ASR text may differ from the logs below.

---

## ASR (`faster-whisper` `small.en`, CPU, `int8`)

Sample: `synthetic_clinic_visit.wav`, duration **161.9 s** (~2:42).
Default `ASR_MODEL_SIZE` was **not** changed for this measurement.

| Metric | Value |
| --- | --- |
| Model load from disk | 6.7 s |
| Transcribe (1st / 2nd) | 42.2 s / 41.8 s |
| Real-time factor | ~0.26 |

If that RTF held, a 10-minute visit would wait on the order of ~2.6 minutes
for ASR alone on that machine. That is an extrapolation from one file, not
a measured 10-minute visit.

Spot-check vs the written dialogue (same sample): vitals and many medication
strings were usable; repeated misses included **cough → cuff**, **sputum →
scutum**, **NKDA → NKTA**, and inconsistent **f/u**. On the hypertension
follow-up sample, **lisinopril** was heard as **liz in April**.

Speaker labels are not produced. Every segment is stored as `speaker="unknown"`.

---

## Note generation timing (local Ollama)

`llama3.1:8b` (config default) was about **0.09 tok/s** on this machine and
**timed out at 5 minutes** on the clinic-visit transcript. Fail-soft error
handling worked.

`llama3:8b` was used for the SOAP evaluation runs because it completed.

| Run | Wall clock (note generation) |
| --- | --- |
| Clinic visit, first E2E (`llama3:8b`, 2:42 audio transcript) | 416 s (~6.9 min) |
| HTN/diabetes follow-up (later cached-transcript runs) | ~78–114 s |
| Ankle sprain | ~60–110 s |
| Ambiguous visit | ~122–305 s (highly variable) |

The first clinic-visit call sent a large prompt (timestamped segments **and**
full transcript). Later calls send **timestamped segments only** when segments
exist (`_prompt_transcript` in `note_service.py`), which is the current code
path.

Combined first E2E on that clinic sample: ASR ~42 s + note 416 s ≈ **7.6 min**.

---

## Clinic visit — hallucination and ICD (one sample, then a second run)

**Before prompt + lookup change (`llama3:8b`):** Assessment stated lisinopril
and metformin were **“well controlled”** (not in the transcript). Suggested
code **J40.0**, which is not a valid ICD-10-CM code in the starter file
(J40 is bronchitis; viral URI in this set is J06.9).

**After** instructing the model to omit unmentioned details, forbidding
ICD emission, and mapping `likely_diagnoses` through `icd10_lookup.py`:
Assessment described viral URI / no antibiotics; **J06.9**; no “well
controlled” on that run.

That is **one transcript, one model, one follow-up run**. It is not evidence
that fabrication is solved in general.

---

## Three-sample generalization (same ASR transcripts, `llama3:8b`)

First pass after the prompt/lookup/grounding work, **before** grounding
bugfixes:

| Sample | Unsupported clinical claim like “well controlled”? | ICD-10 | Grounding |
| --- | --- | --- | --- |
| HTN / diabetes | None found (brother’s “well-controlled” not applied to the patient) | `E11.9` / `I10` (lookup wording includes “without complications”, not spoken) | Assessment **wiped** to empty / “Not documented in visit” |
| Ankle sprain | None found | `S93.401A` | Some real quotes labeled not-directly-stated; one history line cited under Objective |
| Ambiguous visit | None found; clinician’s differential preserved | `UNMATCHED` (intended fallback) | Grocery-store BP cited for today’s 132/84; cousin’s stroke cited on Assessment |

---

## After grounding bugfixes (re-run, same transcripts)

| Sample | What improved | What remained wrong |
| --- | --- | --- |
| HTN / diabetes | Assessment visible: “a bit above our usual goal, but not an emergency.” Plan linked to stay-on-meds / evening metformin. | Home-cuff “130-something over 80” could still attach near today’s 142/88. ASR “liz in April” unchanged. |
| Ankle sprain | All four SOAP sections linked. Assessment: right ankle sprain. | Weak extra quotes (e.g. “Just the right ankle”). Urgent-care-if-worse line was missing on that run. |
| Ambiguous visit | Objective cited clinic 132/84 and “speaking in full sentences”, not the grocery cuff. Cousin stayed under Subjective, not Assessment. | Pulse 90 / lungs often unquoted. **ICD on that run: `F41.9`** (anxiety) — model language had shifted; grounding did not cause that. |

Grounding remains **keyword / overlap matching with filters**, not semantic
citation.

---

## Temperature 0.2 — three runs, identical ambiguous transcript

Ollama note calls now set `options.temperature = 0.2` (not 0). Same cached
ambiguous-visit transcript, `llama3:8b`, three consecutive `generate_note()`
calls.

| | Run 1 | Run 2 | Run 3 |
| --- | --- | --- | --- |
| Assessment (abridged) | Poor sleep, caffeine, worry, mild viral cough, or more than one | Same differential; also “not diagnosing a sinus infection or stroke today” | Same as run 2, slightly different wording |
| ICD-10 | **R51.9** Headache, unspecified | **S93.401A** Right ankle sprain, initial encounter | **UNMATCHED** |
| Wall clock | 122 s | 161 s | 264 s |

Assessment wording was closer across runs than the earlier split between
unmatched differential language and `F41.9`. **ICD-10 still changed every
run.** Run 2’s ankle-sprain code is **not supported by the SOAP text** (no
ankle in that visit). It came from `likely_diagnoses` → lookup, not from
Assessment.

Run 2 Subjective also treated **negated / questioned** symptoms as present
(fever, shortness of breath at rest).

Single re-runs of the other two samples at temperature 0.2 did not show an
obvious SOAP-quality regression vs the post-grounding notes (HTN: still
above-goal / not emergency, E11.9+I10; ankle: sprain + RICE, S93.401A).
That is two point estimates, not a stability study.

---

## Planted-error harness (2026-08-30)

`backend/app/eval_harness.py` + `backend/tests/eval/fixtures.json`. Eight short synthetic transcripts, each with **one** planted failure **outside** the current lexicons. Stub-compatible. The lists were not edited to pass these cases.

| Failure type | Caught | What that means here |
| --- | --- | --- |
| Denied symptom outside the negation lexicon (rash, photophobia, palpitations) | 0/3 | A probe note that asserted the denied symptom was not flagged. |
| Garbled drug outside the starter list and known-garble map (warfaren, levothyroxeen, gabapentn) | 0/3 | `asr_flags` did not mark the planted tokens. |
| Family-history stroke talk vs a probe Assessment about acute stroke | 1/1 | Grounding did not cite the mother’s stroke span. |
| Paraphrase (“can’t catch my breath” vs “shortness of breath”) | 1/1 | Overlap matching linked the paraphrase on this fixture. |

**2/8** planted errors caught. This is a coverage measurement, not a performance claim.

Four **benign** fixtures were added later the same day (differential list language and “call back if X” plan lines), matching the spurious live flags above. The harness now reports false positives beside catch rate. Lexicons were not edited to change these numbers.

| Mechanism | Catch rate (planted) | False positives (benign) |
| --- | --- | --- |
| `negation_check` | 0/3 | 3/4 |
| `asr_flags` | 0/3 | 0/0 (no benign ASR fixtures) |
| Grounding | 2/2 | 0/0 |

| Benign fixture | Flagged? |
| --- | --- |
| Differential “mild viral cough” | yes |
| Differential “rather than shortness of breath” | yes |
| Plan “Return if fever lasts more than three days.” | yes |
| Plan “chest pain that does not stop” | no |

**3/4** false positives on benign fixtures. Combined with the planted set: **2/8** caught, **3/4** false positives.

That was the keyword-checker snapshot. A later same-day pass replaced the assertion *judgment* with a separate model call and re-measured. Those numbers are in [LLM assertion classifier](#llm-assertion-classifier-2026-08-30).

---

## Live `generate_note()` + flaggers (2026-08-30)

`STUB_MODE=false`, `OLLAMA_MODEL=llama3:8b` (same model as the earlier tables; `llama3.1:8b` remains the config default and was previously too slow on this machine). Each of the four written encounter scripts was run **twice**. Wall clock for the eight calls was about **21 minutes** on the same CPU Mac. `asr_flags` was run on the **script text** (correct drug spellings), not on ASR audio.

| Script | Run | ICD-10 | `verification_needs` | `asr_flags` | Assessment (abridged) |
| --- | --- | --- | --- | --- | --- |
| Clinic visit | 1 | J06.9 | 0 | 0 | Viral URI more than pneumonia; no “well controlled” on this run |
| Clinic visit | 2 | J06.9 | 0 | 0 | Same as run 1 |
| HTN / diabetes | 1 | E11.9, I10 | 0 | 0 | BP a bit above goal, not an emergency |
| HTN / diabetes | 2 | E11.9, I10 | 0 | 0 | Same idea, shorter wording |
| Ankle sprain | 1 | S93.401A | 0 | 0 | Right ankle sprain |
| Ankle sprain | 2 | S93.401A | 0 | 0 | Right ankle sprain |
| Ambiguous visit | 1 | UNMATCHED | **2** (assessment, plan) | 0 | Differential; not a single diagnosis |
| Ambiguous visit | 2 | UNMATCHED | **1** (assessment) | 0 | Same differential |

**Did the live path produce flags?** Yes for `verification_needs` on the ambiguous script (3 flags across 2 runs). `asr_flags` was 0 on all eight script-text runs.

**Were those negation flags correct?** On a third ambiguous-visit call used only to inspect sentences, the flagged lines were:

- Assessment: “Could be poor sleep, caffeine, worry, a mild viral cough…”
- Plan: safety-netting that includes “chest pain that doesn’t stop”

The model did **not** repeat the older failure (asserting fever / SOB at rest as present). The live flags were therefore **not** a catch of that historical error. They look **spurious**: “cough” sits in the same transcript chunks as “don’t”, and “chest pain” appears as a warning, not a confirmed finding.

**ASR flags on script text:** expected empty (dialogues spell lisinopril / metformin correctly). A follow-up probe of the known “liz in April” garble still produced one `asr_flags` hit, so the checker is not dead — it never saw garbled tokens in these written scripts.

Zero flags across *all* live notes would have been treated as a wiring bug. That did not happen for negation. ASR-on-scripts being empty was investigated and is explained above.

---

## Live ASR on slurred-medication TTS (2026-08-30)

Script: `audio_samples/synthetic_garbled_meds_dialogue.txt`. The `.wav` is gitignored (same as the longer visit clips). Spoken TTS used broken names (“lizino prill”, “atorva statin”) at a fast Fred voice, 16 kHz mono, ~8 s. Intended medications: **lisinopril**, **atorvastatin**.

Full pipeline twice: `transcribe_audio()` (`faster-whisper` `small.en`, CPU, `int8`) then `generate_note()` (`STUB_MODE=false`, `OLLAMA_MODEL=llama3:8b`). This is **real ASR text**, not the old hand-typed “liz” probe.

| Run | ASR wall | Note wall | Whisper text (abridged) | `asr_flags` | SOAP / ICD |
| --- | --- | --- | --- | --- | --- |
| 1 | 3.6 s | 56 s | “…Lazino Pril 10 milligrams… Adorvastatin 40 milligrams.” | **1** — `unusual_medication_token` on **Adorvastatin** | Assessment copied both garbles; `UNMATCHED` |
| 2 | 5.5 s | 24 s | Same transcript as run 1 | **1** — same **Adorvastatin** flag | Same Assessment copy; `UNMATCHED` |

**Did `asr_flags` fire on real ASR output?** Yes, on **Adorvastatin** in both runs. It did **not** fire on **Lazino Pril** (the lisinopril miss). The note path then wrote both wrong strings into Assessment. The known “liz” text probe is a separate wiring check and is not this result.

No lexicon or known-garble edits were made after this run.

---

## LLM assertion classifier (2026-08-30)

Separate Ollama call after SOAP generation (`negation_llm.py`). Keyword `negation_check.py` remains as a pre-filter only. Live pass used `STUB_MODE=false`, `OLLAMA_MODEL=llama3:8b`.

### Fixtures (same probes as the harness, plus three new out-of-lexicon denied tokens)

| Mechanism | Catch (denied probes) | False positives (4 benign) |
| --- | --- | --- |
| Keyword `negation_check` | 0/6 | 3/4 |
| LLM `negation_llm` | 6/6 | 2/4 |

The two remaining live false positives were safety-net plan lines (fever; chest pain). Both differential lines were true negatives on this live pass. Probe classify wall times after warmup were about **5–6 s**; the first call was **35 s**.

### Four encounter scripts × 2 (`generate_note` + classifier)

| Script | Run | Note wall | Classify (inside that wall) | `verification_needs` |
| --- | --- | --- | --- | --- |
| Clinic visit | 1 | 220 s | 108 s | 2, plan, `only_asked_not_confirmed` |
| Clinic visit | 2 | 174 s | 64 s | 3, plan, `only_asked_not_confirmed` |
| HTN / diabetes | 1 | 190 s | 26 s | 0 |
| HTN / diabetes | 2 | 72 s | 14 s | 0 |
| Ankle sprain | 1 | 55 s | (no candidate / stale timer) | 0 |
| Ankle sprain | 2 | 61 s | 15 s | 0 |
| Ambiguous visit | 1 | 136 s | 43 s | 1, subjective, `denied_by_patient` |
| Ambiguous visit | 2 | 95 s | 25 s | 2, subjective + plan |

This is a small-sample measurement. It is not validation. Safety-net plan language still draws flags.

---

## What this file does not claim

- Clinical performance, safety, or coding accuracy on real visits
- Deterministic LLM output
- Solved hallucination, negation, or grounding
- Reproducible wall-clock times on other hardware
