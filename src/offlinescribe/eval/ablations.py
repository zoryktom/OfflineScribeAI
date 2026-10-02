"""Config-driven ablation runner. Conditions are those in docs/study_design.md."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

from offlinescribe.eval.metrics import score_pair
from offlinescribe.eval.stats import bootstrap_ci, mean
from offlinescribe.eval.taxonomy import Encounter
from offlinescribe.pipeline.run import generate_note


def load_encounters(path: Path) -> list[Encounter]:
    rows: list[Encounter] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(Encounter.model_validate_json(line))
    return rows


def run_ablation(config_path: Path, output_dir: Path) -> Path:
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    encounters = load_encounters(Path(cfg["encounters"]))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = output_dir / run_id
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "config.yaml").write_text(config_path.read_text(encoding="utf-8"), encoding="utf-8")

    results_path = dest / "results.jsonl"
    rows: list[dict] = []
    with results_path.open("w", encoding="utf-8") as handle:
        for encounter in encounters:
            for condition in cfg["conditions"]:
                name = condition["name"]
                for model in cfg["models"]:
                    for asr in cfg["asr"]:
                        for seed in cfg.get("seeds", [0]):
                            generated = generate_note(
                                encounter,
                                condition=name,
                                model=model,
                                asr=asr,
                                seed=int(seed),
                            )
                            metrics = score_pair(
                                encounter.transcript,
                                encounter.gold_note,
                                generated,
                                encounter.gold_meds,
                                encounter.gold_entities,
                            )
                            row = {
                                "encounter_id": encounter.encounter_id,
                                "condition": name,
                                "model": model,
                                "asr": asr,
                                "seed": seed,
                                **metrics,
                            }
                            handle.write(json.dumps(row) + "\n")
                            rows.append(row)

    metrics_summary = _summarize(rows)
    (dest / "metrics.json").write_text(
        json.dumps(metrics_summary, indent=2),
        encoding="utf-8",
    )
    _write_table(dest / "results_table.md", metrics_summary)
    return dest


def _summarize(rows: list[dict]) -> dict:
    keys = [
        "wer",
        "rouge_l",
        "medication_f1",
        "dose_exact_match",
        "negation_accuracy",
        "laterality_accuracy",
        "hallucination_rate",
        "omission_rate",
        "edit_distance_normalized",
    ]
    by_condition: dict[str, dict] = {}
    conditions = sorted({row["condition"] for row in rows})
    for condition in conditions:
        subset = [row for row in rows if row["condition"] == condition]
        cell: dict[str, object] = {"n": len(subset)}
        for key in keys:
            values = [float(row[key]) for row in subset]
            center, lo, hi = bootstrap_ci(values, seed=0)
            cell[key] = {"mean": center, "ci95_lo": lo, "ci95_hi": hi}
        by_condition[condition] = cell
    return {
        "n_rows": len(rows),
        "headline_note": (
            "Stub pipeline. These figures are seeded synthetic perturbations, "
            "not measured model or clinician results."
        ),
        "overall_omission_rate": mean([float(row["omission_rate"]) for row in rows]),
        "overall_hallucination_rate": mean([float(row["hallucination_rate"]) for row in rows]),
        "by_condition": by_condition,
    }


def _write_table(path: Path, summary: dict) -> None:
    lines = [
        "# Ablation results (synthetic stub)",
        "",
        summary["headline_note"],
        "",
        "| condition | n | hallucination_rate (95% CI) | omission_rate (95% CI) | rouge_l |",
        "|---|---:|---|---|---|",
    ]
    for name, cell in summary["by_condition"].items():
        h = cell["hallucination_rate"]
        o = cell["omission_rate"]
        r = cell["rouge_l"]
        lines.append(
            f"| {name} | {cell['n']} | "
            f"{h['mean']:.3f} [{h['ci95_lo']:.3f}, {h['ci95_hi']:.3f}] | "
            f"{o['mean']:.3f} [{o['ci95_lo']:.3f}, {o['ci95_hi']:.3f}] | "
            f"{r['mean']:.3f} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
