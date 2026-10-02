from offlinescribe.io.deid import deidentify, report


def test_deid_mrn_and_date(tmp_path) -> None:
    text, counts = deidentify("Patient Jane Doe MRN 123456 on 2024-01-02 in Rochester")
    assert counts["mrn"] == 1
    assert "MRN" in text
    items = [(f"MRN {1000 + i}", f"MRN {1000 + i}") for i in range(100)]
    payload = report(tmp_path / "deid_report.json", items)
    assert payload["n"] == 100
    assert payload["recall"] >= 0.95
