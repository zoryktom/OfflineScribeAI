import pytest

from app.eval_harness import format_text_report, run_harness


@pytest.mark.eval
def test_planted_error_harness_records_per_fixture_catch():
    report = run_harness()
    assert report["fixture_count"] == 15
    assert report["planted_count"] == 11
    assert report["benign_count"] == 4
    assert "comparison" in report
    assert "false_positive_count" in report
    assert set(report["by_type"]) >= {
        "denied_symptom_outside_lexicon",
        "garbled_drug_outside_list",
        "family_history_miscite",
        "paraphrase_symptom",
        "benign_differential",
        "benign_safety_net",
    }
    assert "negation_check" in report["by_mechanism"]
    for row in report["results"]:
        assert isinstance(row["caught"], bool)
        assert isinstance(row["false_positive"], bool)
        assert row["expected_mechanism"] in {
            "negation_check",
            "negation_llm",
            "asr_flags",
            "grounding",
        }
        if row["role"] == "benign":
            assert row["should_flag"] is False
        else:
            assert row["should_flag"] is True
    text = format_text_report(report)
    assert "Not clinical validation" in text
    assert "false positive" in text.lower()
