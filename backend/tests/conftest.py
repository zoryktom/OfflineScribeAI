import os
import tempfile
from pathlib import Path

os.environ["STUB_MODE"] = "true"
os.environ["ASR_PRELOAD"] = "false"
os.environ["ASR_MODEL_SIZE"] = "tiny.en"
os.environ["ASR_DEVICE"] = "cpu"
os.environ["SQLCIPHER_KEY"] = "pytest-only-sqlcipher-key"
os.environ["LOCAL_API_KEY"] = "pytest-local-api-key"
os.environ["SQLITE_PATH"] = str(
    Path(tempfile.mkdtemp(prefix="offline-scribe-pytest-")) / "visits.db"
)

import pytest

from app.config import clear_settings_cache

clear_settings_cache()


@pytest.fixture
def ollama_mode(monkeypatch):
    monkeypatch.setenv("STUB_MODE", "false")
    clear_settings_cache()
    yield
    monkeypatch.setenv("STUB_MODE", "true")
    clear_settings_cache()
