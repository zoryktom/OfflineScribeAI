import json


def patch_ollama(monkeypatch, note_payload: dict, captured: dict | None = None):
    """Replace note_service.urlopen with tags + generate responses."""

    class _Tags:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"models": [{"name": "llama3.1:8b"}]}).encode()

    class _Generate:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"response": json.dumps(note_payload)}).encode()

    class _Classify:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(
                {
                    "response": json.dumps(
                        {
                            "items": [
                                {
                                    "section": "subjective",
                                    "sentence_index": 0,
                                    "label": "DENIED_BY_PATIENT",
                                }
                            ]
                        }
                    )
                }
            ).encode()

    def fake_urlopen(request, timeout=None):
        url = request.get_full_url()
        if url.endswith("/api/tags"):
            return _Tags()
        body = json.loads(request.data.decode("utf-8")) if request.data else {}
        if captured is not None and "ASSERTED_BY_PATIENT" not in str(body.get("system") or ""):
            captured["body"] = body
            captured["timeout"] = timeout
        if "ASSERTED_BY_PATIENT" in str(body.get("system") or ""):
            return _Classify()
        return _Generate()

    monkeypatch.setattr("app.note_service.urlopen", fake_urlopen)
    monkeypatch.setattr("app.negation_llm.urlopen", fake_urlopen)
