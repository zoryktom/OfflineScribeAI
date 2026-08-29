"""Shared secret for the localhost API. Not a multi-user identity system."""

from __future__ import annotations

import secrets

from fastapi import Header, HTTPException

from app.config import get_settings


def require_local_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    expected = get_settings().local_api_key
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="LOCAL_API_KEY is not set in backend/.env. Copy .env.example and restart.",
        )
    provided = x_api_key or ""
    if len(provided) != len(expected) or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=401,
            detail="This local API requires a valid X-API-Key header.",
        )
