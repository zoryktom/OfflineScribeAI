"""Clinician-facing instruments. Stores ratings; does not invent reviewer scores."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field


PDQI9_ITEMS = (
    "accurate",
    "thorough",
    "useful",
    "organized",
    "comprehensible",
    "succinct",
    "synthesized",
    "internally_consistent",
    "up_to_date",
)


class PDQI9(BaseModel):
    accurate: int = Field(ge=1, le=5)
    thorough: int = Field(ge=1, le=5)
    useful: int = Field(ge=1, le=5)
    organized: int = Field(ge=1, le=5)
    comprehensible: int = Field(ge=1, le=5)
    succinct: int = Field(ge=1, le=5)
    synthesized: int = Field(ge=1, le=5)
    internally_consistent: int = Field(ge=1, le=5)
    up_to_date: int = Field(ge=1, le=5)


class NasaTlx(BaseModel):
    mental_demand: int = Field(ge=0, le=20)
    physical_demand: int = Field(ge=0, le=20)
    temporal_demand: int = Field(ge=0, le=20)
    performance: int = Field(ge=0, le=20)
    effort: int = Field(ge=0, le=20)
    frustration: int = Field(ge=0, le=20)


class HumanReview(BaseModel):
    reviewer_id: str
    encounter_id: str
    condition: str
    pdqi9: PDQI9
    factual_error_count: int
    clinically_significant_error_count: int
    edit_time_seconds: float
    trust: int = Field(ge=1, le=7)
    would_sign: Literal["yes", "no", "with_edits"]
    acceptability: int = Field(ge=1, le=7)
    nasa_tlx: NasaTlx
    notes: Optional[str] = None


def already_reviewed(path: Path, encounter_id: str, reviewer_id: str) -> bool:
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("encounter_id") == encounter_id and row.get("reviewer_id") == reviewer_id:
            return True
    return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record a clinician review row.")
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--encounter", required=True)
    parser.add_argument("--condition", default="rag_grounded")
    parser.add_argument("--notes", default="data/synthetic/manifest.jsonl")
    parser.add_argument("--out-dir", default="data/human_eval")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--edit-time-seconds", type=float, default=0.0)
    return parser


def _neutral_review(args: argparse.Namespace, elapsed: float) -> HumanReview:
    mid = {item: 3 for item in PDQI9_ITEMS}
    return HumanReview(
        reviewer_id=args.reviewer,
        encounter_id=args.encounter,
        condition=args.condition,
        pdqi9=PDQI9(**mid),
        factual_error_count=0,
        clinically_significant_error_count=0,
        edit_time_seconds=elapsed,
        trust=4,
        would_sign="with_edits",
        acceptability=4,
        nasa_tlx=NasaTlx(
            mental_demand=10,
            physical_demand=2,
            temporal_demand=10,
            performance=10,
            effort=10,
            frustration=8,
        ),
        notes="non-interactive scaffold; not a collected clinician rating",
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dest = Path(args.out_dir) / f"{args.reviewer}.jsonl"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if already_reviewed(dest, args.encounter, args.reviewer):
        print(f"skip: {args.encounter} already reviewed by {args.reviewer}")
        return 0
    started = time.perf_counter()
    if args.non_interactive:
        elapsed = args.edit_time_seconds or (time.perf_counter() - started)
        review = _neutral_review(args, elapsed)
    else:
        print(f"Reviewer {args.reviewer}  encounter {args.encounter}")
        print("Open the transcript and draft. Press Enter when finished editing.")
        input()
        elapsed = time.perf_counter() - started
        review = _neutral_review(args, elapsed)
        print("Interactive numeric collection is not implemented; wrote a scaffold row.")
        print("Replace that row after a real review session.")
    with dest.open("a", encoding="utf-8") as handle:
        handle.write(review.model_dump_json() + "\n")
    print(f"wrote {dest}")
    return 0
