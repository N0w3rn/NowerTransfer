"""Remembering an interrupted send so it can be resumed.

Only sends are remembered: the receiving side needs nothing but the code
phrase, which the user still has.
"""

from __future__ import annotations

import json
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from .paths import user_config_dir, write_atomic

SESSION_FILENAME = "session.json"


@dataclass(frozen=True)
class SendSession:
    code: str
    paths: list[str]


def session_path() -> Path:
    return user_config_dir() / SESSION_FILENAME


def save_send_session(code: str, paths: list[str]) -> None:
    payload = {"mode": "send", "code": code, "paths": [str(p) for p in paths]}
    # Resume is a convenience; failing to record it must not break a
    # transfer that is about to start.
    with suppress(OSError):
        write_atomic(session_path(), json.dumps(payload, indent=2))


def load_send_session() -> SendSession | None:
    """Return the stored session, dropping files that no longer exist."""
    try:
        raw = session_path().read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or payload.get("mode") != "send":
        return None

    code = payload.get("code")
    paths = payload.get("paths")
    if not isinstance(code, str) or not isinstance(paths, list):
        return None

    existing = [p for p in paths if isinstance(p, str) and Path(p).exists()]
    if not code or not existing:
        return None
    return SendSession(code=code, paths=existing)


def clear_send_session() -> None:
    with suppress(OSError):
        session_path().unlink(missing_ok=True)
