# Related work

This note is a methods map, not a claim that OfflineScribeAI is a finished empirical paper. Citations are in `paper/refs.bib`.

## Clinical documentation burden

Ambulatory physicians spend a large share of the clinic day on the electronic record. Sinsky and colleagues time-motion work showed that desk and EHR time rival or exceed face-to-face time, and that “pajama time” documentation extends into the evening (Sinsky et al., 2016; Arndt et al., 2017). Subsequent log analyses linked inbox and documentation burden to burnout and to reduced capacity for coordination work that never appears as a billable note (Tai-Seale et al., 2017; Downing et al., 2018). The policy conversation at the AMA and in informatics has treated documentation as a work-design problem, not only a typing-speed problem: who is accountable for the chart, which tasks are visible, and which are dumped onto the last person in the room.

That literature is the reason a scribe—human or model—looks attractive. It is also why a fluent draft can add review work: someone still has to notice a flipped denial, fix laterality, and accept legal responsibility. This repo treats the named reviewer as part of the documentation system, not as an optional UI.

OfflineScribeAI does not measure pajama time in a health system. It measures, on synthetic encounters, the kinds of errors that turn a time-saving draft into new review work.

## Ambient AI scribes

Commercial ambient scribes (Nuance DAX / Microsoft, Abridge, Nabla, and related products) sit in the exam room, produce a note, and promise lower after-hours EHR time. Early health-system reports describe reduced documentation time and mixed effects on note quality and on the felt presence of the clinician (Tierney et al., 2024; Haberle et al., 2024). These reports are implementation snapshots. They are not error taxonomies with double annotation, and they are not public corpora.

The product category also hides a research gap. Vendor evaluations rarely publish span-level hallucination and omission rates by condition (no retrieval vs retrieval vs grounding vs verifier), and they rarely cross ASR quality with negation and dose errors. They almost never release the notes. A local-first harness cannot replace a multi-site ambient trial, but it can make those failure modes inspectable. This project’s position is narrower than a vendor bake-off: if a draft is generated at all, which error types appear, and does grounding trade one error type for another (RQ3 / H1)?

## Hallucination in medical LLMs

Hallucination in generation is well surveyed outside medicine (Ji et al., 2023; Maynez et al., 2020). In clinical text the cost is not only factual novelty; it is a signable sentence that a busy reviewer may trust. Medical benchmarks have shown that high exam scores can coexist with fabricated citations, unstable codes, and unsupported diagnoses (Singhal et al., 2023; Nori et al., 2023; Umapathi et al., 2023). Faithfulness metrics from summarization (entity overlap, NLI entailment) are a starting point and a known underestimate of clinical harm.

This taxonomy splits “the model made something up” into hallucination, negation_flip, laterality, medication, dose, temporality, and attribution. That split matters because a denial written as a positive finding is not the same research object as an extra family-history clause. The interactive prototype already showed that a keyword negation screen and a second-pass assertion classifier disagree on false alarms; that is a measurement finding, not a claim that hallucination is solved.

## Grounding, attribution, and RAG in clinical NLP

Retrieval-augmented generation (Lewis et al., 2020) and attributable generation (Rashkin et al., 2023; Gao et al., 2023) treat evidence spans as first-class objects. Clinical NLP had related machinery earlier: sectioning, assertion (Chapman et al., 2001), and concept linking in i2b2-style shared tasks (Uzuner et al., 2011). BioBERT and ClinicalBERT (Lee et al., 2020; Alsentzer et al., 2019) made those spans easier to encode; they did not make generated SOAP notes faithful.

H1 in this repo is the standard RAG fear in a documentation setting: locking text to transcript spans should cut fabrication and may drop unsupported but still-needed synthesis (omission). The stub runner encodes that tradeoff as a perturbation so the analysis code can run. A live test still needs models listed in `docs/study_design.md` and human labels. Citation precision/recall in `metrics.py` are span-overlap stand-ins, not NLI.

## Human–AI teaming and trust calibration

Trust in automation research warns that reliability and trust can decouple (Parasuraman and Riley, 1997; Lee and See, 2004; Hoff and Bashir, 2015). In documentation, over-trust is signing; under-trust is ignoring a usable draft and re-dictating. Amershi et al. (2019) guidelines—make uncertainty visible, support efficient correction—map onto watermarking, named review, and edit-time logging.

H4 (edit time tracks omissions more than hallucinations) is a calibration hypothesis, not a result. PDQI-9, NASA-TLX, and a would-you-sign item are the instruments (`docs/clinician_protocol.md`). ICC and mixed-effects models are specified in `docs/study_design.md`. There is no committed clinician dataset.

## Five Rights of CDS, DIKW, and sociotechnical frameworks

The Five Rights of clinical decision support (the right information, person, format, channel, time) are a design check, not a metric (Osheroff et al., 2012; Bates et al., 2003). A SOAP draft that arrives after the visit, in a chart the wrong person must clean, fails those rights even if ROUGE is high. DIKW (data–information–knowledge–wisdom) is a reminder that a transcript is not a note and a note is not a decision (Ackoff, 1989; Rowley, 2007).

Sociotechnical models keep the organization in the unit of analysis: Sittig and Singh’s eight-dimensional model, Berg’s work on the EHR as a coordinating artifact, Greenhalgh’s NASSS, and Damschroder’s CFIR (Sittig and Singh, 2010; Berg, 1999; Greenhalgh et al., 2017; Damschroder et al., 2009). This repo uses those names to structure limitations and the workflow study. It does not run a CFIR interview set and does not claim a new grand theory.

## Local and on-prem LLMs and privacy in healthcare

Cloud ambient products require a business-associate and data-flow story that many clinics will not or cannot sign. Local ASR and local open-weight models change the default data path (Touvron et al., 2023; Jiang et al., 2023; Radford et al., 2023). They do not create HIPAA certification, FDA clearance, or a safe deployment. Privacy scholarship and regulation still apply (Price and Cohen, 2019; HHS HIPAA). FDA guidance on clinical decision support draws a line this prototype stays on the “not for clinical use” side of.

RQ4 (local ≤13B vs a frontier API reference) is about fidelity and edit burden, not about declaring a winner for production. The API model is a reference arm in the design document. The default interactive path stays local, and live FHIR POST stays off.
