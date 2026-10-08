"""Product validation runner for the synthetic OfflineScribeAI benchmark."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from offlinescribe.eval.ablations import load_encounters, run_ablation
from offlinescribe.eval.evidence_graph import build_evidence_graph, write_evidence_graph
from offlinescribe.pipeline.run import generate_note

DEFAULT_GATES = {
    "max_mean_hallucination_rate": 0.34,
    "max_mean_omission_rate": 0.13,
    "min_mean_rouge_l": 0.96,
    "min_mean_medication_f1": 1.0,
    "min_mean_dose_exact_match": 1.0,
    "min_mean_negation_accuracy": 1.0,
}


def run_validation(
    config_path: Path,
    output_dir: Path,
    *,
    report_path: Path | None = None,
    graph_dir: Path | None = None,
    graph_limit: int = 3,
) -> dict[str, Any]:
    """Run the ablation and write pass/fail gates plus sample evidence graphs."""

    run_path = run_ablation(config_path, output_dir)
    summary = json.loads((run_path / "metrics.json").read_text(encoding="utf-8"))
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    gates = _evaluate_gates(summary, config)
    graphs = _write_graph_samples(config, graph_dir or run_path / "evidence_graphs", graph_limit)

    report = {
        "schema_version": "offlinescribe.validation_report.v1",
        "run_path": str(run_path),
        "config": str(config_path),
        "passed": all(item["passed"] for item in gates),
        "gates": gates,
        "evidence_graphs": [str(path) for path in graphs],
        "summary": summary,
        "interpretation": (
            "Synthetic validation gates check reproducibility, benchmark plumbing, and "
            "known perturbation behavior. Passing does not establish clinical validity."
        ),
    }
    target = report_path or run_path / "validation_report.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["report_path"] = str(target)
    return report


def _evaluate_gates(summary: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    by_condition = summary["by_condition"]
    expected_rows = _expected_rows(config)
    gates = [
        _gate("expected_row_count", summary["n_rows"] == expected_rows, summary["n_rows"], expected_rows),
        _gate(
            "all_configured_conditions_present",
            set(by_condition) == set(_condition_names(config)),
            sorted(by_condition),
            sorted(_condition_names(config)),
        ),
    ]
    for condition, cell in sorted(by_condition.items()):
        gates.extend(
            [
                _threshold_gate(
                    f"{condition}:hallucination_rate_mean",
                    cell["hallucination_rate"]["mean"],
                    "<=",
                    DEFAULT_GATES["max_mean_hallucination_rate"],
                ),
                _threshold_gate(
                    f"{condition}:omission_rate_mean",
                    cell["omission_rate"]["mean"],
                    "<=",
                    DEFAULT_GATES["max_mean_omission_rate"],
                ),
                _threshold_gate(
                    f"{condition}:rouge_l_mean",
                    cell["rouge_l"]["mean"],
                    ">=",
                    DEFAULT_GATES["min_mean_rouge_l"],
                ),
                _threshold_gate(
                    f"{condition}:medication_f1_mean",
                    cell["medication_f1"]["mean"],
                    ">=",
                    DEFAULT_GATES["min_mean_medication_f1"],
                ),
                _threshold_gate(
                    f"{condition}:dose_exact_match_mean",
                    cell["dose_exact_match"]["mean"],
                    ">=",
                    DEFAULT_GATES["min_mean_dose_exact_match"],
                ),
                _threshold_gate(
                    f"{condition}:negation_accuracy_mean",
                    cell["negation_accuracy"]["mean"],
                    ">=",
                    DEFAULT_GATES["min_mean_negation_accuracy"],
                ),
            ]
        )

    if {"baseline", "rag_grounded_verified"}.issubset(by_condition):
        baseline = by_condition["baseline"]
        verified = by_condition["rag_grounded_verified"]
        gates.extend(
            [
                _gate(
                    "verified_omission_not_worse_than_baseline",
                    verified["omission_rate"]["mean"] <= baseline["omission_rate"]["mean"],
                    verified["omission_rate"]["mean"],
                    f"<= {baseline['omission_rate']['mean']}",
                ),
                _gate(
                    "verified_hallucination_not_worse_than_baseline",
                    verified["hallucination_rate"]["mean"] <= baseline["hallucination_rate"]["mean"],
                    verified["hallucination_rate"]["mean"],
                    f"<= {baseline['hallucination_rate']['mean']}",
                ),
                _gate(
                    "verified_rouge_not_worse_than_baseline",
                    verified["rouge_l"]["mean"] >= baseline["rouge_l"]["mean"],
                    verified["rouge_l"]["mean"],
                    f">= {baseline['rouge_l']['mean']}",
                ),
            ]
        )
    return gates


def _write_graph_samples(config: dict[str, Any], graph_dir: Path, graph_limit: int) -> list[Path]:
    graph_dir.mkdir(parents=True, exist_ok=True)
    encounters = load_encounters(Path(config["encounters"]))[: max(0, graph_limit)]
    written: list[Path] = []
    for encounter in encounters:
        for condition in _condition_names(config):
            model = str(config["models"][0])
            asr = str(config["asr"][0])
            seed = int(config.get("seeds", [0])[0])
            generated = generate_note(encounter, condition=condition, model=model, asr=asr, seed=seed)
            graph = build_evidence_graph(
                encounter,
                generated,
                condition=condition,
                model=model,
                asr=asr,
                seed=seed,
            )
            path = graph_dir / f"{encounter.encounter_id}__{condition}.json"
            write_evidence_graph(path, graph)
            written.append(path)
    return written


def _expected_rows(config: dict[str, Any]) -> int:
    return (
        _line_count(Path(config["encounters"]))
        * len(_condition_names(config))
        * len(config["models"])
        * len(config["asr"])
        * len(config.get("seeds", [0]))
    )


def _line_count(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _condition_names(config: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for condition in config["conditions"]:
        names.append(condition["name"] if isinstance(condition, dict) else str(condition))
    return names


def _threshold_gate(name: str, observed: float, operator: str, threshold: float) -> dict[str, Any]:
    passed = observed <= threshold if operator == "<=" else observed >= threshold
    return _gate(name, passed, round(observed, 6), f"{operator} {threshold}")


def _gate(name: str, passed: bool, observed: Any, expected: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "observed": observed, "expected": expected}
