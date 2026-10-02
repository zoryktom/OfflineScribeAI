# Limitations

- **Synthetic data only.** No real PHI, no real clinic prevalence. Template repetition will inflate lexical metrics.
- **No completed clinician study.** N = 0 reviewers in the committed tree. ICC and H4 are not estimable.
- **No completed dual annotation.** Seed JSONL is programmatic. Cohen's κ is not reported as a finding.
- **Stub ablations.** `pipeline/run.py` does not call Llama, Qwen, Mistral, or GPT-4o-mini. Headline tables from `make eval` are reproducible perturbations.
- **English only.**
- **Single assumed workflow:** one named reviewer, one encounter, ambulatory SOAP. No inpatient, no multi-author notes, no longitudinal deployment.
- **ASR:** interactive path uses faster-whisper; the factorial ASR list is a planned factor, not a measured audio study in the stub runner.
- **De-ID** is regex on fixtures, not a validated PHI de-identifier.
- **FHIR** mapping is a dry-run DocumentReference/Composition. Live POST is refused.
- **Small local models** and **frontier APIs** are named for RQ4; they are not benchmarked here.
- **No arXiv identifier yet.** The paper file is a skeleton. Do not add a fake badge.
