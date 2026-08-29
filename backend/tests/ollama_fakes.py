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

    def fake_urlopen(request, timeout=None):
        url = request.get_full_url()
        if url.endswith("/api/tags"):
            return _Tags()
        if captured is not None:
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
        return _Generate()

    monkeypatch.setattr("app.note_service.urlopen", fake_urlopen)
