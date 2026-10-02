"""offlinescribe CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from offlinescribe.eval import annotate as annotate_mod
from offlinescribe.eval import human_eval as human_eval_mod
from offlinescribe.eval.ablations import run_ablation
from offlinescribe.eval.taxonomy import Encounter
from offlinescribe.io.audit import append, hash_payload
from offlinescribe.io.deid import deidentify
from offlinescribe.io.fhir import write_dry_run
from offlinescribe.pipeline.run import generate_note


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="offlinescribe")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ann = sub.add_parser("annotate", help="Annotate one encounter")
    annotate_mod.build_parser()
    p_ann.add_argument("--encounter", required=True)
    p_ann.add_argument("--condition", required=True)
    p_ann.add_argument("--annotator", required=True)
    p_ann.add_argument("--model", default="stub")
    p_ann.add_argument("--asr", default="whisper-large-v3")
    p_ann.add_argument("--manifest", default="data/synthetic/manifest.jsonl")
    p_ann.add_argument("--out-dir", default="data/annotations")
    p_ann.add_argument("--non-interactive", action="store_true")
    p_ann.add_argument("--error-type", default="style_only")
    p_ann.add_argument("--severity", default="none")
    p_ann.add_argument("--span-generated", default="")
    p_ann.add_argument("--rationale", default="non-interactive seed")

    p_eval = sub.add_parser("eval", help="Evaluation runner")
    eval_sub = p_eval.add_subparsers(dest="eval_cmd", required=True)
    p_run = eval_sub.add_parser("run", help="Run an ablation config")
    p_run.add_argument("--config", required=True)
    p_run.add_argument("--out", default="experiments/runs")

    p_hum = sub.add_parser("human-eval", help="Record a human review row")
    p_hum.add_argument("--reviewer", required=True)
    p_hum.add_argument("--encounter", required=True)
    p_hum.add_argument("--condition", default="rag_grounded")
    p_hum.add_argument("--notes", default="data/synthetic/manifest.jsonl")
    p_hum.add_argument("--out-dir", default="data/human_eval")
    p_hum.add_argument("--non-interactive", action="store_true")
    p_hum.add_argument("--edit-time-seconds", type=float, default=0.0)

    p_pipe = sub.add_parser("pipeline", help="Run stub pipeline on one encounter")
    p_pipe.add_argument("--encounter", required=True)
    p_pipe.add_argument("--condition", default="rag_grounded")
    p_pipe.add_argument("--model", default="stub")
    p_pipe.add_argument("--asr", default="whisper-large-v3")
    p_pipe.add_argument("--manifest", default="data/synthetic/manifest.jsonl")
    p_pipe.add_argument("--fhir-out", default="")
    p_pipe.add_argument("--audit", default="data/audit/audit.jsonl")

    args = parser.parse_args(argv)
    if args.cmd == "annotate":
        return annotate_mod.main(
            [
                "--encounter",
                args.encounter,
                "--condition",
                args.condition,
                "--annotator",
                args.annotator,
                "--model",
                args.model,
                "--asr",
                args.asr,
                "--manifest",
                args.manifest,
                "--out-dir",
                args.out_dir,
                "--error-type",
                args.error_type,
                "--severity",
                args.severity,
                "--span-generated",
                args.span_generated,
                "--rationale",
                args.rationale,
            ]
            + (["--non-interactive"] if args.non_interactive else [])
        )
    if args.cmd == "eval" and args.eval_cmd == "run":
        dest = run_ablation(Path(args.config), Path(args.out))
        print(dest)
        return 0
    if args.cmd == "human-eval":
        return human_eval_mod.main(
            [
                "--reviewer",
                args.reviewer,
                "--encounter",
                args.encounter,
                "--condition",
                args.condition,
                "--notes",
                args.notes,
                "--out-dir",
                args.out_dir,
                "--edit-time-seconds",
                str(args.edit_time_seconds),
            ]
            + (["--non-interactive"] if args.non_interactive else [])
        )
    if args.cmd == "pipeline":
        encounter = _load(Path(args.manifest), args.encounter)
        note = generate_note(encounter, condition=args.condition, model=args.model, asr=args.asr)
        print(note.model_dump_json(indent=2))
        if args.fhir_out:
            write_dry_run(Path(args.fhir_out), encounter, note)
        redacted, _ = deidentify(encounter.transcript)
        append(
            Path(args.audit),
            user="local",
            model=args.model,
            config_hash=hash_payload(args.condition),
            input_hash=hash_payload(encounter.transcript),
            output_hash=hash_payload(note.model_dump_json()),
            grounding_spans=[],
        )
        print(json.dumps({"deid_preview": redacted[:160]}))
        return 0
    return 2


def _load(manifest: Path, encounter_id: str) -> Encounter:
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = Encounter.model_validate_json(line)
        if row.encounter_id == encounter_id:
            return row
    raise KeyError(encounter_id)


if __name__ == "__main__":
    raise SystemExit(main())
