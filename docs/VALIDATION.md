# Validation

OfflineScribeAI includes a runnable synthetic validation suite:

```bash
offlinescribe validate --config experiments/configs/pilot.yaml
```

The command runs the configured ablation, writes `validation_report.json`, and exports sample evidence graphs under the run directory.

The repository includes a small committed example at `examples/validation/validation_report.json` with one encounter's evidence graphs.

## What The Gates Check

- the expected number of benchmark rows is produced
- every configured study condition is present
- each condition stays within calibrated synthetic error thresholds
- medication, dose, and negation checks do not regress on the shipped fixtures
- `rag_grounded_verified` is not worse than `baseline` on omission, hallucination, or ROUGE-L mean

These gates validate benchmark plumbing, deterministic reproducibility, and known synthetic perturbation behavior. They do not establish clinical safety or real-world effectiveness.

## Evidence Graphs

Each sample graph links a generated SOAP note to:

- the synthetic source transcript
- generated note sections
- gold entities
- planted stressors
- verifier flags
- review-gate reasons

The review gate always blocks live EHR release in this repository. This keeps the artifact useful for research and engineering review without implying deployment readiness.

## Expected Local Check

```bash
make install
make test
make validate
```

Passing output should include:

```json
{
  "passed": true,
  "report": "experiments/runs/pilot/validation_report.json"
}
```
