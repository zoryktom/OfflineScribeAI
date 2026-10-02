"""Append-only HMAC audit log."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _key() -> bytes:
    raw = os.environ.get("OFFLINESCRIBE_AUDIT_KEY", "research-only-not-a-secret")
    return raw.encode("utf-8")


def hash_payload(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sign(prev_hmac: str, body: str) -> str:
    return hmac.new(_key(), f"{prev_hmac}|{body}".encode(), hashlib.sha256).hexdigest()


def append(
    path: Path,
    *,
    user: str,
    model: str,
    config_hash: str,
    input_hash: str,
    output_hash: str,
    grounding_spans: list[str] | None = None,
) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    prev = "0" * 64
    if path.exists():
        last = path.read_text(encoding="utf-8").splitlines()[-1]
        prev = json.loads(last)["hmac"]
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": user,
        "model": model,
        "config_hash": config_hash,
        "input_hash": input_hash,
        "output_hash": output_hash,
        "grounding_spans": grounding_spans or [],
        "prev_hmac": prev,
    }
    body = json.dumps({k: v for k, v in row.items() if k != "hmac"}, sort_keys=True)
    row["hmac"] = sign(prev, body)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    return row


def verify(path: Path) -> bool:
    prev = "0" * 64
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        body = json.dumps({k: v for k, v in row.items() if k != "hmac"}, sort_keys=True)
        expected = sign(prev, body)
        if not hmac.compare_digest(expected, row["hmac"]):
            return False
        prev = row["hmac"]
    return True
