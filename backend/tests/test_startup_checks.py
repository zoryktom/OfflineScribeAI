import pytest

from app.startup_checks import (
    StartupError,
    assert_loopback_argv,
    assert_loopback_host,
    assert_required_secrets,
    run_startup_checks,
)


def test_loopback_host_accepted():
    assert_loopback_host("127.0.0.1")
    assert_loopback_host("localhost")


def test_non_loopback_host_is_refused():
    with pytest.raises(StartupError, match="127.0.0.1"):
        assert_loopback_host("0.0.0.0")
    with pytest.raises(StartupError, match="127.0.0.1"):
        assert_loopback_argv(["uvicorn", "app.main:app", "--host", "0.0.0.0"])


def test_example_secrets_are_refused():
    with pytest.raises(StartupError, match="SQLCIPHER_KEY"):
        assert_required_secrets("", "pytest-local-api-key")
    with pytest.raises(StartupError, match="LOCAL_API_KEY"):
        assert_required_secrets("pytest-only-sqlcipher-key", "local-dev-only-api-key")


def test_run_startup_checks_allows_pytest_defaults():
    run_startup_checks(["pytest"])


def test_run_startup_checks_refuses_non_loopback_host_env(monkeypatch):
    from app.config import clear_settings_cache

    monkeypatch.setenv("HOST", "0.0.0.0")
    clear_settings_cache()
    try:
        with pytest.raises(StartupError, match="127.0.0.1"):
            run_startup_checks(["pytest"])
    finally:
        monkeypatch.setenv("HOST", "127.0.0.1")
        clear_settings_cache()


def test_stub_mode_refused_without_allow_dev_defaults(monkeypatch):
    from app.config import clear_settings_cache

    monkeypatch.setenv("ALLOW_DEV_DEFAULTS", "false")
    monkeypatch.setenv("STUB_MODE", "true")
    clear_settings_cache()
    try:
        with pytest.raises(StartupError, match="STUB_MODE"):
            run_startup_checks(["pytest"])
    finally:
        monkeypatch.setenv("ALLOW_DEV_DEFAULTS", "true")
        clear_settings_cache()
