"""Span annotation CLI. Writes JSONL; does not claim human IAA."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from offlinescribe.eval.taxonomy import Annotation, Encounter, ErrorType, Severity


def already_annotated(path: Path, encounter_id: str, condition: str, annotator_id: str) -> bool:
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if (
            row.get("encounter_id") == encounter_id
            and row.get("condition") == condition
            and row.get("annotator_id") == annotator_id
        ):
            return True
    return False


def load_encounter(manifest: Path, encounter_id: str) -> Encounter:
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = Encounter.model_validate_json(line)
        if row.encounter_id == encounter_id:
            return row
    raise KeyError(f"Encounter {encounter_id} not found in {manifest}")


def prompt_annotation(encounter: Encounter, args: argparse.Namespace) -> Annotation:
    gold = encounter.gold_note
    print(f"Encounter {encounter.encounter_id}  condition={args.condition}  annotator={args.annotator}")
    print("--- transcript ---")
    print(encounter.transcript)
    print("--- gold ---")
    print(gold.model_dump_json(indent=2))
    print("Error types:", ", ".join(item.value for item in ErrorType))
    print("Severity:", ", ".join(item.value for item in Severity))
    error_type = ErrorType(input("error_type: ").strip())
    severity = Severity(input("severity: ").strip())
    span_generated = input("span_generated: ").strip()
    span_source = input("span_source (blank if none): ").strip() or None
    clinically_significant = input("clinically_significant (y/n): ").strip().lower() == "y"
    rationale = input("rationale: ").strip()
    return Annotation(
        encounter_id=encounter.encounter_id,
        condition=args.condition,
        model=args.model,
        asr=args.asr,
        span_generated=span_generated,
        span_source=span_source,
        error_type=error_type,
        severity=severity,
        clinically_significant=clinically_significant,
        rationale=rationale,
        annotator_id=args.annotator,
    )


def append_jsonl(path: Path, annotation: Annotation) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(annotation.model_dump_json() + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Annotate one encounter draft.")
    parser.add_argument("--encounter", required=True)
    parser.add_argument("--condition", required=True)
    parser.add_argument("--annotator", required=True)
    parser.add_argument("--model", default="stub")
    parser.add_argument("--asr", default="whisper-large-v3")
    parser.add_argument("--manifest", default="data/synthetic/manifest.jsonl")
    parser.add_argument("--out-dir", default="data/annotations")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--error-type", default="style_only")
    parser.add_argument("--severity", default="none")
    parser.add_argument("--span-generated", default="")
    parser.add_argument("--rationale", default="non-interactive seed")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dest = Path(args.out_dir) / f"{args.annotator}.jsonl"
    if already_annotated(dest, args.encounter, args.condition, args.annotator):
        print(f"skip: {args.encounter} already annotated by {args.annotator} for {args.condition}")
        return 0
    encounter = load_encounter(Path(args.manifest), args.encounter)
    if args.non_interactive:
        annotation = Annotation(
            encounter_id=encounter.encounter_id,
            condition=args.condition,
            model=args.model,
            asr=args.asr,
            span_generated=args.span_generated or encounter.gold_note.subjective[:80],
            span_source=None,
            error_type=ErrorType(args.error_type),
            severity=Severity(args.severity),
            clinically_significant=args.severity in {"major", "critical"},
            rationale=args.rationale,
            annotator_id=args.annotator,
        )
    else:
        if not sys.stdin.isatty():
            print("stdin is not a TTY; use --non-interactive", file=sys.stderr)
            return 2
        annotation = prompt_annotation(encounter, args)
    append_jsonl(dest, annotation)
    print(f"wrote {dest}")
    return 0
