import json
from pathlib import Path

from offlinescribe.eval.evidence_graph import build_evidence_graph
from offlinescribe.eval.synth import build_encounter, write_manifest
from offlinescribe.eval.validation import run_validation
from offlinescribe.pipeline.run import generate_note


def test_evidence_graph_links_sections_entities_and_review_gate() -> None:
    encounter = build_encounter(1)
    note = generate_note(
        encounter,
        condition="rag_grounded_verified",
        model="stub",
        asr="whisper-large-v3",
    )

    graph = build_evidence_graph(
        encounter,
        note,
        condition="rag_grounded_verified",
        model="stub",
        asr="whisper-large-v3",
    )

    assert graph["schema_version"] == "offlinescribe.evidence_graph.v1"
    assert graph["review_gate"]["status"] == "human_review_required"
    assert graph["review_gate"]["release_to_ehr"] is False
    assert len(graph["section_support"]) == 4
    assert graph["risk_summary"]["entities_expected"] == len(encounter.gold_entities)
    assert any(edge["type"] == "SUPPORTED_BY_SOURCE" for edge in graph["edges"])


def test_validation_report_and_graphs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(manifest, n=10)
    config = tmp_path / "config.yaml"
    config.write_text(
        "\n".join(
            [
                "run_id: mini",
                f"encounters: {manifest}",
                "conditions:",
                "  - {name: baseline}",
                "  - {name: rag_grounded_verified}",
                "models: [stub]",
                "asr: [whisper-large-v3]",
                "seeds: [0]",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = run_validation(config, tmp_path / "runs", graph_limit=1)

    assert report["passed"] is True
    assert Path(report["report_path"]).exists()
    assert len(report["evidence_graphs"]) == 2
    saved = json.loads(Path(report["report_path"]).read_text(encoding="utf-8"))
    assert saved["schema_version"] == "offlinescribe.validation_report.v1"
    assert all(gate["passed"] for gate in saved["gates"])
