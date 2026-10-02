from pathlib import Path

from offlinescribe.cli import main
from offlinescribe.eval.ablations import run_ablation
from offlinescribe.eval.stats import bootstrap_ci, holm_bonferroni, wilcoxon_signed_pairs
from offlinescribe.eval.synth import build_encounter, write_manifest
from offlinescribe.eval.taxonomy import Encounter
from offlinescribe.io.audit import append, hash_payload, verify
from offlinescribe.io.deid import deidentify
from offlinescribe.io.fhir import LIVE_POST_FLAG, post_or_refuse
from offlinescribe.pipeline.run import generate_note


def test_unknown_condition_rejected() -> None:
    try:
        generate_note(build_encounter(1), condition="not_a_study_arm", model="stub", asr="x")
    except ValueError as exc:
        assert "study_design" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_sample_ablation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    dest = run_ablation(Path("experiments/configs/sample.yaml"), tmp_path)
    assert (dest / "results.jsonl").exists()
    assert (dest / "metrics.json").exists()
    assert (dest / "results_table.md").exists()
    lines = (dest / "results.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 400  # 100 encounters × 4 conditions × 1 model × 1 asr × 1 seed


def test_cli_annotate_and_pipeline(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(manifest, n=2)
    out = tmp_path / "ann"
    assert (
        main(
            [
                "annotate",
                "--encounter",
                "E001",
                "--condition",
                "baseline",
                "--annotator",
                "A1",
                "--manifest",
                str(manifest),
                "--out-dir",
                str(out),
                "--non-interactive",
            ]
        )
        == 0
    )
    assert (out / "A1.jsonl").exists()
    assert (
        main(
            [
                "annotate",
                "--encounter",
                "E001",
                "--condition",
                "baseline",
                "--annotator",
                "A1",
                "--manifest",
                str(manifest),
                "--out-dir",
                str(out),
                "--non-interactive",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "pipeline",
                "--encounter",
                "E001",
                "--condition",
                "rag_grounded",
                "--manifest",
                str(manifest),
                "--fhir-out",
                str(tmp_path / "fhir.json"),
                "--audit",
                str(tmp_path / "audit.jsonl"),
            ]
        )
        == 0
    )
    assert (tmp_path / "fhir.json").exists()


def test_stats_and_io(tmp_path: Path) -> None:
    center, lo, hi = bootstrap_ci([0.1, 0.2, 0.3], seed=1)
    assert lo <= center <= hi
    signed = wilcoxon_signed_pairs([1.0, 2.0, 3.0], [0.5, 2.0, 2.5])
    assert signed["plus"] == 2
    assert holm_bonferroni([0.01, 0.04])[0] <= holm_bonferroni([0.01, 0.04])[1]
    redacted, counts = deidentify("Patient Jane Doe MRN 123456 on 2024-01-02 in Rochester")
    assert "MRN" in redacted
    assert counts["mrn"] == 1
    log = tmp_path / "audit.jsonl"
    append(
        log,
        user="A1",
        model="stub",
        config_hash=hash_payload("x"),
        input_hash=hash_payload("in"),
        output_hash=hash_payload("out"),
    )
    assert verify(log)
    encounter = Encounter.model_validate(build_encounter(1).model_dump())
    refused = post_or_refuse(encounter, encounter.gold_note)
    assert refused["refused"] is True
    assert LIVE_POST_FLAG in refused["reason"]
