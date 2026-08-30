"""Application configuration. Model names, paths, ports, and flags live here — nowhere else."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Network — this process must stay on loopback. It is not a hosted service.
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    # Feature flags. stub_mode gates the local LLM only; ASR is always real.
    stub_mode: bool = Field(
        default=True,
        description="When true, the LLM returns canned SOAP notes so the app runs without Ollama.",
    )
    language: str = "en"

    # ASR (faster-whisper). Loaded once at API startup.
    asr_model_size: str = Field(
        default="small.en",
        description="faster-whisper model id. small.en is the default CPU-friendly English model.",
    )
    asr_device: str = Field(
        default="cpu",
        description="cpu or cuda. Default cpu so a clinic laptop with no GPU still works.",
    )
    whisper_compute_type: str = "int8"
    whisper_models_dir: Path = _BACKEND_DIR / "data" / "whisper-models"
    asr_preload: bool = Field(
        default=True,
        description="Load the Whisper model during API startup. Tests set this false.",
    )

    # Reject oversized uploads before transcription. Default 100 MiB.
    max_upload_bytes: int = 100 * 1024 * 1024

    # Local LLM via Ollama. Unused while stub_mode is true.
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_timeout_seconds: float = 120.0

    # Encrypted local visit database. Demo mode uses a different file.
    sqlite_path: Path = _BACKEND_DIR / "data" / "offline_scribe.db"
    demo_sqlite_path: Path = _BACKEND_DIR / "data" / "offline_scribe_demo.db"

    # Permanently limited synthetic explorer. Default off. Not a real-visit path.
    demo_mode: bool = Field(
        default=False,
        description="When true, only preloaded synthetic encounters can be loaded.",
    )

    # SQLCipher passphrase. Never hardcode. Empty key refuses to open the DB.
    sqlcipher_key: str = ""

    # Shared secret for localhost API routes except /health.
    local_api_key: str = ""

    # Tests and local scaffolding set this true. A pilot run should leave it false.
    allow_dev_defaults: bool = False

    # Delete visits older than this many days on startup. 0 disables purge.
    visit_retention_days: int = 0

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def active_sqlite_path(self) -> Path:
        return self.demo_sqlite_path if self.demo_mode else self.sqlite_path


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
