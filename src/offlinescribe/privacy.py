"""Network isolation utilities for the offline clinical pipeline."""

from __future__ import annotations

import contextlib
import http.client
import socket
import urllib.request
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any, Callable


class NetworkSandboxViolation(RuntimeError):
    """Raised when code attempts network activity inside the privacy sandbox."""


@dataclass
class NetworkAttempt:
    operation: str
    target: str

    def as_dict(self) -> dict[str, str]:
        return {"operation": self.operation, "target": self.target}


@dataclass
class NetworkSandbox:
    """Block and audit network APIs while sensitive offline work runs.

    The sandbox intentionally blocks all socket and common HTTP entry points,
    including calls that are later caught by user code. This makes attempted
    leakage observable in tests and in pipeline audit metadata.
    """

    label: str = "offline section"
    attempts: list[NetworkAttempt] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._patches: list[tuple[Any, str, Any]] = []

    def __enter__(self) -> "NetworkSandbox":
        self._install_patch(socket, "socket", self._blocked_factory("socket.socket"))
        self._install_patch(socket, "create_connection", self._blocked_factory("socket.create_connection"))
        self._install_patch(socket, "getaddrinfo", self._blocked_factory("socket.getaddrinfo"))
        self._install_patch(http.client.HTTPConnection, "connect", self._blocked_method("http.client.HTTPConnection.connect"))
        self._install_patch(http.client.HTTPSConnection, "connect", self._blocked_method("http.client.HTTPSConnection.connect"))
        self._install_patch(urllib.request, "urlopen", self._blocked_factory("urllib.request.urlopen"))

        with contextlib.suppress(Exception):
            import requests

            self._install_patch(
                requests.sessions.Session,
                "request",
                self._blocked_method("requests.Session.request"),
            )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        for owner, name, original in reversed(self._patches):
            setattr(owner, name, original)
        self._patches.clear()

        if exc_type is None and self.attempts:
            raise NetworkSandboxViolation(
                f"Network activity was attempted during {self.label}: {self.attempts[0].operation}"
            )
        return False

    def _install_patch(self, owner: Any, name: str, replacement: Any) -> None:
        self._patches.append((owner, name, getattr(owner, name)))
        setattr(owner, name, replacement)

    def _record(self, operation: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        target = _summarize_target(args, kwargs)
        self.attempts.append(NetworkAttempt(operation=operation, target=target))

    def _blocked_factory(self, operation: str) -> Callable[..., Any]:
        def blocked(*args: Any, **kwargs: Any) -> Any:
            self._record(operation, args, kwargs)
            raise NetworkSandboxViolation(f"Network call blocked during {self.label}: {operation}")

        return blocked

    def _blocked_method(self, operation: str) -> Callable[..., Any]:
        def blocked(instance: Any, *args: Any, **kwargs: Any) -> Any:
            self._record(operation, args, kwargs)
            raise NetworkSandboxViolation(f"Network call blocked during {self.label}: {operation}")

        return blocked


def _summarize_target(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    if args:
        first = args[0]
        if isinstance(first, tuple):
            return ":".join(str(part) for part in first)
        return str(first)
    if kwargs:
        return ", ".join(f"{key}={value!r}" for key, value in sorted(kwargs.items()))
    return "<unknown>"

