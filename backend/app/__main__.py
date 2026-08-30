"""Run the local API. Bind is forced to loopback."""

from app.config import get_settings
from app.startup_checks import StartupError, assert_loopback_host, run_startup_checks


def main() -> None:
    import uvicorn

    settings = get_settings()
    run_startup_checks()
    assert_loopback_host(settings.host)
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    try:
        main()
    except StartupError as exc:
        raise SystemExit(str(exc)) from exc
