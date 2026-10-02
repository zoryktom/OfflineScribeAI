from pathlib import Path

from offlinescribe.eval.workflow import WorkflowSession


def test_workflow_timing(tmp_path: Path) -> None:
    session = WorkflowSession("E001", "R1")
    session.mark("first_draft")
    session.mark("edit", edit_type="omission")
    session.mark("sign")
    summary = session.summary()
    assert summary["n_edits"] == 1
    assert summary["time_to_first_draft"] is not None
    assert summary["time_to_sign"] is not None
    dest = tmp_path / "workflow.jsonl"
    session.write(dest)
    assert dest.read_text(encoding="utf-8").count("\n") == 4
