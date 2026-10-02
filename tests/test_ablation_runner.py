from pathlib import Path

from offlinescribe.eval.ablations import run_ablation
from offlinescribe.eval.stats import mcnemar_paired, wilcoxon_paired


def test_pilot_writes_outputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    dest = run_ablation(Path("experiments/configs/pilot.yaml"), tmp_path)
    assert (dest / "metrics.jsonl").exists()
    assert (dest / "summary.csv").exists()
    assert (dest / "git_sha.txt").exists()
    assert list((dest / "outputs").glob("E001/*.json"))


def test_paired_stats() -> None:
    chi, p = mcnemar_paired([True, True, False, False], [True, False, True, False])
    assert chi >= 0
    assert 0 <= p <= 1
    z, p2 = wilcoxon_paired([1.0, 2.0, 3.0], [0.5, 2.0, 2.5])
    assert z != 0
    assert 0 <= p2 <= 1
