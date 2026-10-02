from offlinescribe.cli import main


def test_human_eval_scaffold(tmp_path) -> None:
    dest = tmp_path / "human"
    assert (
        main(
            [
                "human-eval",
                "--reviewer",
                "R1",
                "--encounter",
                "E001",
                "--condition",
                "rag_grounded",
                "--out-dir",
                str(dest),
                "--non-interactive",
                "--edit-time-seconds",
                "12",
            ]
        )
        == 0
    )
    text = (dest / "R1.jsonl").read_text(encoding="utf-8")
    assert "scaffold" in text
    assert (
        main(
            [
                "human-eval",
                "--reviewer",
                "R1",
                "--encounter",
                "E001",
                "--out-dir",
                str(dest),
                "--non-interactive",
            ]
        )
        == 0
    )
    assert text.count("\n") == (dest / "R1.jsonl").read_text(encoding="utf-8").count("\n")
