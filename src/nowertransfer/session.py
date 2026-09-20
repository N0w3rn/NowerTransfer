"""Remembering an interrupted send so it can be resumed.

Only sends are remembered: the receiving side needs nothing but the code
phrase, which the user still has.

The stored code phrase is croc's end-to-end encryption secret, so it is
written through :mod:`~nowertransfer.secretstore` rather than in the
clear, and the file is removed as soon as the transfer completes.
"""

from __future__ import annotations

import json
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from .paths import user_config_dir, write_atomic
from .secretstore import protect, unprotect

SESSION_FILENAME = "session.json"


@dataclass(frozen=True)
class SendSession:
    code: str
    paths: list[str]


def session_path() -> Path:
    return user_config_dir() / SESSION_FILENAME


def save_send_session(code: str, paths: list[str]) -> None:
    # The paths are encrypted too, not only the code phrase: a folder
    # name says what was being sent, and that is worth as little to a
    # reader of this file as the phrase itself.
    payload = {
        "mode": "send",
        "code": protect(code),
        "paths": [protect(str(p)) for p in paths],
    }
    # Failing to record a resume point must not break the transfer.
    with suppress(OSError):
        write_atomic(session_path(), json.dumps(payload, indent=2), private=True)


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

    stored_code = payload.get("code")
    paths = payload.get("paths")
    if not isinstance(stored_code, str) or not isinstance(paths, list):
        return None

    # A code that will not decrypt came from another machine; nothing
    # to resume.
    code = unprotect(stored_code)
    # unprotect passes an untagged value straight through, so a file
    # written before the paths were encrypted still resumes.
    existing = [
        decrypted
        for stored in paths
        if isinstance(stored, str)
        and (decrypted := unprotect(stored))
        and Path(decrypted).exists()
    ]
    if not code or not existing:
        return None
    return SendSession(code=code, paths=existing)


def clear_send_session() -> None:
    with suppress(OSError):
        session_path().unlink(missing_ok=True)
