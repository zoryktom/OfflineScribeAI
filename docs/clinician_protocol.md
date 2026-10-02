# Clinician review protocol

Research prototype. Synthetic notes only. Not a clinical trial and not for patient care.

## IRB determination note

The committed corpus is synthetic. There is no real PHI and no patient recruitment. Many institutions treat this as non-human-subjects research or exempt. **Do not assume exemption.** File a determination with the local IRB before recruiting clinicians or using any real notes. This file is a protocol scaffold, not an approval.

## Recruitment

Target 3–5 reviewers: MD, DO, RN, NP, PA, or senior medical students with ambulatory documentation experience. Recruit by email. No employment consequence for declining. Stopping rule: stop at 3 reviewers if ICC ≥ 0.75; else recruit to 5.

## Consent script (read aloud or shown on screen)

“You are being asked to review synthetic clinic notes drafted by a research system. There are no real patients. You will rate quality, count errors, and say whether you would sign a note like this after edits. The session takes about 60–90 minutes. You may stop at any time. Ratings are stored under a reviewer code, not your name, in `data/human_eval/`. This is not a test of your clinical skill. The system is not for clinical use.”

## Task

Each reviewer sees 20 encounters: transcript on the left, generated note on the right. Conditions are balanced using the names in `docs/study_design.md` (five notes per condition, order randomized per reviewer). For each note:

1. Start the timer (`offlinescribe human-eval` records `edit_time_seconds`).
2. Read transcript and note.
3. Count factual errors and clinically significant errors.
4. Complete PDQI-9 (1–5), trust (1–7), would-you-sign (yes / no / with_edits), acceptability (1–7).
5. Complete NASA-TLX after the block of 20, not after every note, unless the reviewer wants per-note load scores.
6. Stop the timer.

## Instruments

Implemented in `src/offlinescribe/eval/human_eval.py`:

- **PDQI-9 (adapted):** accurate, thorough, useful, organized, comprehensible, succinct, synthesized, internally consistent, up-to-date.
- **Counts:** factual errors, clinically significant errors.
- **Edit time:** seconds.
- **Trust:** 7-point.
- **Would you sign this?** yes / no / with_edits.
- **Acceptability:** single 7-point item (TAM-style). Full SUS is optional in `docs/workflow_study.md`.
- **NASA-TLX:** six raw subscales 0–20.

## Compensation and time

Budget 60–90 minutes plus a 10-minute introduction. Compensation is set by the local site (gift card or hourly). Record the amount in the site log; do not commit names or payment records to git.

## Data handling

- Reviewer IDs only (`R1`…`R5`).
- JSONL under `data/human_eval/{reviewer}.jsonl`.
- No audio of the reviewer unless a later consent covers it.
- Do not paste real patient notes into this tool.

```bash
offlinescribe human-eval --reviewer R1 --encounter E001 --condition rag_grounded
```

## Analysis

`notebooks/03_clinician_ratings.ipynb` computes PDQI-9 means, ICC across reviewers, and the H4 correlation (edit time vs omission and hallucination counts). H4 is testable only after real reviews exist. Scaffold rows in the CLI are not clinician data.
