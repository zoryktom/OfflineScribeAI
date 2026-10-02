# Error taxonomy

Span-level labels for an AI-drafted SOAP note against a transcript and a gold note. Definitions are operational, not legal or malpractice categories. Severity is assigned independently of error type.

## Severity rubric

- **Critical:** could cause harm if signed as written (wrong medication, wrong dose, missed allergy, flipped denial of a dangerous symptom).
- **Major:** would change a clinical decision or a billable code if left in place.
- **Moderate:** a clinician must edit before signing; decision-making is not clearly changed.
- **Minor:** wording, order, or tone; no clinical impact.
- **None:** used only for calibration rows that are not errors.

`clinically_significant` is true for moderate, major, and critical unless the span is purely administrative.

## Error types

### omission

**Definition.** A fact required in the gold note (symptom, denial, medication, laterality, plan item) is absent from the generated note.

**Positive.** Gold: “Denies chest pain.” Generated assessment never mentions chest pain.

**Negative.** Gold lists fatigue; generated says “tiredness” in subjective. That is style, not omission.

**Edge.** A fact in the transcript but marked out of scope for this note type (small talk) is not an omission.

**Typical severity.** Moderate if a clinician would add it; major if it is a denial or allergy; critical if it is an allergy or a dangerous denial.

### hallucination

**Definition.** A clinically readable claim in the generated note that is not supported by the transcript or allowed retrieved context.

**Positive.** “Family history of early stroke” when the transcript never mentions family history.

**Negative.** Restating “denies chest pain” when the patient said “I deny chest pain.”

**Edge.** Template boilerplate (“follow up as needed”) is style_only unless it invents a specific order.

**Typical severity.** Major or critical when it adds disease, meds, or allergies; minor when it adds vague wellness language.

### negation_flip

**Definition.** A denied or unconfirmed finding is written as present, or a present finding is written as denied.

**Positive.** Patient: “I deny tinnitus.” Assessment: “Tinnitus, likely idiopathic.”

**Negative.** “Patient denies tinnitus” in subjective matching the transcript.

**Edge.** “Only asked, not confirmed” written as a diagnosis is a flip even if the word “deny” never appears. See the interactive classifier in `backend/app/negation_llm.py`.

**Typical severity.** Major or critical for dangerous symptoms; moderate for low-stakes symptoms.

### laterality

**Definition.** Left / right / bilateral is wrong, dropped, or swapped.

**Positive.** “Right ankle sprain” when the patient said left.

**Negative.** “Left ankle” matching the transcript.

**Edge.** A midline complaint (dysuria) with no side stated: inventing “left-sided” is hallucination plus laterality.

**Typical severity.** Major for procedures and injuries; moderate if laterality is clinically unused.

### medication

**Definition.** Drug identity is wrong, added, or dropped.

**Positive.** Transcript “lisinopril”; note “losartan.”

**Negative.** “Continue lisinopril” when that is what was said.

**Edge.** Brand vs generic of the same molecule is style_only if dose and intent match.

**Typical severity.** Critical if a different drug is started; major if a current drug is dropped from the list.

### dose

**Definition.** Strength, unit, route, or frequency is wrong.

**Positive.** “Lisinopril 40 mg” when the transcript said 10 mg.

**Negative.** “10 mg daily” matching the source.

**Edge.** “Take as directed” when a numeric dose was stated is omission of dose, labeled `dose` not `omission`.

**Typical severity.** Critical for high-alert drugs; major otherwise.

### temporality

**Definition.** Onset, duration, or sequence is wrong.

**Positive.** “Symptoms for two years” when the patient said two weeks.

**Negative.** “About two weeks” matching the source.

**Edge.** “Chronic” vs “acute” when the transcript is silent is hallucination.

**Typical severity.** Moderate unless it changes acuity (major).

### attribution

**Definition.** Speaker, actor, or source of a statement is wrong (patient vs clinician vs family).

**Positive.** “Patient reports a family history of early stroke” when the clinician hypothesized it.

**Negative.** Correctly attributing a denial to the patient.

**Edge.** Passive voice that hides who denied a finding: label attribution if a reader would assign the claim to the wrong person.

**Typical severity.** Moderate; major if it assigns a diagnosis the clinician never made.

### icd_instability

**Definition.** The assigned ICD-10 code is not a deterministic lookup from the documented problems, or the same input yields a different code across seeds.

**Positive.** Model writes J06.9 on one seed and I10 on another for the same transcript.

**Negative.** Local table returns I10 for “essential hypertension” on every seed.

**Edge.** Two equally plausible codes from the same table row: not instability if the table lists both.

**Typical severity.** Major when coding would change; moderate when it is a laterality or unspecified variant.

### asr_propagation

**Definition.** An ASR substitution is copied into the note as if it were clinical speech.

**Positive.** ASR heard “liz in April”; the plan starts “liz in April 10 mg.”

**Negative.** ASR garbled the drug but the note keeps the gold medication because a second check caught it.

**Edge.** If the transcript gold already contains the garble (no separate ASR hypothesis), use `medication` or `dose` instead.

**Typical severity.** Follows the clinical content (often medication/dose → major or critical).

### style_only

**Definition.** Wording, section order, or length differs without changing clinical content.

**Positive.** “HTN, stable” vs “Hypertension appears controlled.”

**Negative.** Dropping the denial of chest pain (that is omission).

**Edge.** If a style change hides a denial, prefer negation_flip or omission.

**Typical severity.** Minor or none.

## Decision order

When two labels fit, use this order: critical/major clinical content first (`medication`, `dose`, `negation_flip`, `laterality`), then `hallucination` / `omission`, then `asr_propagation` if the source is the ASR hypothesis, then `style_only`.
