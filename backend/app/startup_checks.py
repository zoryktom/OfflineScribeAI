"""Refuse unsafe bind/secret defaults before the API serves requests."""

from __future__ import annotations

import sys

from app.config import get_settings

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
EXAMPLE_SECRET_VALUES = frozenset(
    {
        "",
        "changeme",
        "your-key",
        "your-system-account-secret",
        "local-dev-only-replace-before-real-visits",
        "local-dev-only-api-key",
    }
)


class StartupError(Exception):
    """Unsafe configuration. Message is safe to show an operator."""


def run_startup_checks(argv: list[str] | None = None) -> None:
    settings = get_settings()
    assert_loopback_host(settings.host)
    assert_loopback_argv(argv if argv is not None else sys.argv)
    assert_required_secrets(settings.sqlcipher_key, settings.local_api_key)
    if not settings.allow_dev_defaults and settings.stub_mode:
        raise StartupError(
            "STUB_MODE is still true. That is a development default. "
            "Set STUB_MODE=false in backend/.env for a supervised pilot, "
            "or set ALLOW_DEV_DEFAULTS=true only on a test machine."
        )


def assert_loopback_host(host: str) -> None:
    cleaned = (host or "").strip().lower()
    if cleaned not in LOOPBACK_HOSTS:
        raise StartupError(
            f"This API may bind only to 127.0.0.1 (got {host!r}). "
            "Do not use --host 0.0.0.0 or HOST=0.0.0.0."
        )


def assert_loopback_argv(argv: list[str]) -> None:
    override = _host_from_argv(argv)
    if override is not None:
        assert_loopback_host(override)


def assert_required_secrets(sqlcipher_key: str, local_api_key: str) -> None:
    if _is_example_secret(sqlcipher_key):
        raise StartupError(
            "SQLCIPHER_KEY is missing or still an example placeholder. "
            "Set a unique passphrase in the environment or backend/.env."
        )
    if _is_example_secret(local_api_key):
        raise StartupError(
            "LOCAL_API_KEY is missing or still an example placeholder. "
            "Set a unique key in the environment or backend/.env."
        )


def _is_example_secret(value: str) -> bool:
    return (value or "").strip() in EXAMPLE_SECRET_VALUES


def _host_from_argv(argv: list[str]) -> str | None:
    for index, item in enumerate(argv):
        if item.startswith("--host="):
            return item.split("=", 1)[1]
        if item == "--host" and index + 1 < len(argv):
            return argv[index + 1]
    return None
