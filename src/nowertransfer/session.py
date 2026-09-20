"""Remembering an interrupted transfer so it can be resumed.

Both directions are remembered. Sends always were; receives were not,
on the reasoning that the receiving side "needs nothing but the code
phrase, which the user still has" - which stops being true the moment
the chat the phrase arrived in is closed. Resuming a receive
demonstrably works (see the note on croc's ``--overwrite``), so
losing the phrase was the only thing standing in the way.

One transfer runs at a time, so one file holds whichever is current;
``mode`` says which.

The stored code phrase is croc's end-to-end encryption secret, and the
paths say what was being moved, so both go through
:mod:`~nowertransfer.secretstore` rather than to disk in the clear.
The file is removed as soon as the transfer completes.
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


@dataclass(frozen=True)
class ReceiveSession:
    code: str
    target: str


def session_path() -> Path:
    return user_config_dir() / SESSION_FILENAME


def _stored(payload: dict, mode: str) -> dict | None:
    """The payload, if it is one of ours and of the mode asked for."""
    if not isinstance(payload, dict) or payload.get("mode") != mode:
        return None
    return payload


def _read() -> dict | None:
    try:
        raw = session_path().read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _write(payload: dict) -> None:
    # Failing to record a resume point must not break the transfer.
    with suppress(OSError):
        write_atomic(session_path(), json.dumps(payload, indent=2), private=True)


def save_send_session(code: str, paths: list[str]) -> None:
    # The paths are encrypted too, not only the code phrase: a folder
    # name says what was being sent, and that is worth as little to a
    # reader of this file as the phrase itself.
    _write(
        {
            "mode": "send",
            "code": protect(code),
            "paths": [protect(str(p)) for p in paths],
        }
    )


def save_receive_session(code: str, target: str | Path) -> None:
    _write(
        {
            "mode": "receive",
            "code": protect(code),
            "target": protect(str(target)),
        }
    )


def load_send_session() -> SendSession | None:
    """Return the stored send, dropping files that no longer exist."""
    payload = _read()
    if payload is None or _stored(payload, "send") is None:
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


def load_receive_session() -> ReceiveSession | None:
    """Return the stored receive, if its folder is still there."""
    payload = _read()
    if payload is None or _stored(payload, "receive") is None:
        return None

    stored_code = payload.get("code")
    stored_target = payload.get("target")
    if not isinstance(stored_code, str) or not isinstance(stored_target, str):
        return None

    code = unprotect(stored_code)
    target = unprotect(stored_target)
    if not code or not target or not Path(target).is_dir():
        return None
    return ReceiveSession(code=code, target=target)


def clear_session() -> None:
    """Forget the interrupted transfer, whichever direction it was."""
    with suppress(OSError):
        session_path().unlink(missing_ok=True)
