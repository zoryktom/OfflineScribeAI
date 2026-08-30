from app.eval_harness import load_fixtures, turns_to_transcript


def test_eval_fixtures_are_synthetic_and_loadable():
    fixtures = load_fixtures()
    assert 14 <= len(fixtures) <= 16
    ids = [item["id"] for item in fixtures]
    assert len(ids) == len(set(ids))
    for item in fixtures:
        transcript = turns_to_transcript(item["turns"])
        assert transcript.text
        assert transcript.segments
        assert item["failure_type"]
        assert item["expected_mechanism"]
        assert "patient" not in item["id"]
