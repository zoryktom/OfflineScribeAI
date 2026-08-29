# Evaluation notes

These measurements come from local runs on a CPU-only 8GB Mac during development.
They are **not** a clinical benchmark, a published result, or a claim that the
system is accurate in general. Sample size is four synthetic encounters (one
original clinic visit plus three later scripts). Several LLM runs used a
**cached ASR transcript** so note-generation changes could be isolated from
ASR variance.

There is **no committed evaluation harness**. Runs used `generate_note()` from
`backend/app/note_service.py` against those transcripts, with
`STUB_MODE=false` and `OLLAMA_MODEL=llama3:8b`. The configured default in
`.env.example` remains `llama3.1:8b`.

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

## What this file does not claim

- Clinical performance, safety, or coding accuracy on real visits
- Deterministic LLM output
- Solved hallucination, negation, or grounding
- Reproducible wall-clock times on other hardware
