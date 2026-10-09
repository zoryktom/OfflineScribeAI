"""offlinescribe CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from offlinescribe.ambient import process_audio_to_note
from offlinescribe.audio.synthetic import DEFAULT_SYNTHETIC_TRANSCRIPT, write_synthetic_wav
from offlinescribe.audio.transcriber import TranscriptionConfig, transcriber_from_config
from offlinescribe.eval import annotate as annotate_mod
from offlinescribe.eval import human_eval as human_eval_mod
from offlinescribe.eval.ablations import run_ablation
from offlinescribe.eval.validation import run_validation
from offlinescribe.eval.taxonomy import Encounter
from offlinescribe.io.audit import append, hash_payload
from offlinescribe.io.deid import deidentify
from offlinescribe.io.fhir import write_dry_run
from offlinescribe.pipeline.run import generate_note
from offlinescribe.privacy import NetworkSandbox, NetworkSandboxViolation


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
    p_ann.add_argument("--output", default="")
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

    p_val = sub.add_parser("validate", help="Run benchmark validation gates and evidence graphs")
    p_val.add_argument("--config", default="experiments/configs/pilot.yaml")
    p_val.add_argument("--out", default="experiments/runs")
    p_val.add_argument("--report", default="")
    p_val.add_argument("--graphs", default="")
    p_val.add_argument("--graph-limit", type=int, default=3)

    p_transcribe = sub.add_parser("transcribe", help="Transcribe local audio and optionally structure SOAP JSON")
    p_transcribe.add_argument("audio_path", help="Path to a local WAV file")
    p_transcribe.add_argument("--format", choices=["soap", "transcript"], default="soap")
    p_transcribe.add_argument("--out", help="Write output JSON/text to this path. Defaults to stdout.")
    p_transcribe.add_argument("--backend", choices=["auto", "metadata", "faster-whisper"], default="auto")
    p_transcribe.add_argument("--model-path", help="Local faster-whisper/ctranslate2 model path")
    p_transcribe.add_argument("--compute-type", default="int8", help="ctranslate2 compute type, e.g. int8 or float16")
    p_transcribe.add_argument("--device", default="auto", help="Inference device for faster-whisper")
    p_transcribe.add_argument("--chunk-seconds", type=float, default=15.0)
    p_transcribe.add_argument("--language", default="en")
    p_transcribe.add_argument("--beam-size", type=int, default=5)

    p_sample = sub.add_parser("make-sample", help="Create a deterministic synthetic WAV with embedded transcript")
    p_sample.add_argument("output_path")
    p_sample.add_argument("--duration-seconds", type=float, default=4.0)
    p_sample.add_argument("--transcript", default=DEFAULT_SYNTHETIC_TRANSCRIPT)

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
                "--output",
                args.output,
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
    if args.cmd == "validate":
        report = run_validation(
            Path(args.config),
            Path(args.out),
            report_path=Path(args.report) if args.report else None,
            graph_dir=Path(args.graphs) if args.graphs else None,
            graph_limit=args.graph_limit,
        )
        print(json.dumps({"passed": report["passed"], "report": report["report_path"]}, indent=2))
        return 0 if report["passed"] else 1
    if args.cmd == "transcribe":
        return _handle_transcribe(args)
    if args.cmd == "make-sample":
        write_synthetic_wav(
            args.output_path,
            transcript=args.transcript,
            duration_seconds=args.duration_seconds,
        )
        print(args.output_path)
        return 0
    return 2


def _handle_transcribe(args: argparse.Namespace) -> int:
    config = TranscriptionConfig(
        backend=args.backend,
        model_path=args.model_path,
        compute_type=args.compute_type,
        device=args.device,
        chunk_seconds=args.chunk_seconds,
        language=args.language,
        beam_size=args.beam_size,
    )
    try:
        if args.format == "soap":
            output: str | dict[str, Any] = process_audio_to_note(args.audio_path, config)
            payload = json.dumps(output, indent=2, sort_keys=True)
        else:
            with NetworkSandbox("audio transcription"):
                transcriber = transcriber_from_config(config)
                result = transcriber.transcribe(Path(args.audio_path))
            payload = result.text
    except NetworkSandboxViolation as exc:
        print(f"offline privacy violation: {exc}", file=sys.stderr)
        return 2

    if args.out:
        Path(args.out).write_text(payload + ("\n" if not payload.endswith("\n") else ""), encoding="utf-8")
    else:
        print(payload)
    return 0


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
