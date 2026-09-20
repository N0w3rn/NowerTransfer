"""Remembering interrupted transfers so they can be resumed.

Several at once, in both directions. Sends were remembered first;
receives followed once it was clear that "the user still has the code
phrase" stops being true the moment the chat it arrived in is closed.
Holding only one was the next limit: interrupt a second transfer and
the first was forgotten, though croc can carry on with either.

An entry leaves the list when its transfer completes, or when what it
refers to has gone - a file that was deleted, a folder that is no
longer there.

The code phrase is croc's end-to-end encryption secret, and the paths
say what was being moved, so both go through
:mod:`~nowertransfer.secretstore` rather than to disk in the clear.
The timestamp does not: it orders the list and says nothing.
"""

from __future__ import annotations

import json
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from .paths import user_config_dir, write_atomic
from .secretstore import protect, unprotect

SESSION_FILENAME = "session.json"

#: Bumped when the shape changes. Version 1 held a single transfer as
#: the top-level object; :func:`_entries` still reads one.
SESSION_VERSION = 2


@dataclass(frozen=True)
class SendSession:
    code: str
    paths: list[str]


@dataclass(frozen=True)
class ReceiveSession:
    code: str
    target: str


Unfinished = SendSession | ReceiveSession


def session_path() -> Path:
    return user_config_dir() / SESSION_FILENAME


# ----------------------------------------------------------------------
#  Reading and writing the file
# ----------------------------------------------------------------------
def _entries() -> list[dict]:
    """Every stored entry, still encrypted, oldest first."""
    try:
        raw = session_path().read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []

    # Version 1 wrote the one transfer as the whole file.
    if isinstance(payload, dict) and "transfers" not in payload:
        return [payload] if payload.get("mode") in ("send", "receive") else []
    if not isinstance(payload, dict):
        return []
    stored = payload.get("transfers")
    if not isinstance(stored, list):
        return []
    return [entry for entry in stored if isinstance(entry, dict)]


def _store(entries: list[dict]) -> None:
    # Failing to record a resume point must not break a transfer.
    with suppress(OSError):
        if not entries:
            session_path().unlink(missing_ok=True)
            return
        write_atomic(
            session_path(),
            json.dumps({"version": SESSION_VERSION, "transfers": entries}, indent=2),
            private=True,
        )


def _without(entries: list[dict], code: str) -> list[dict]:
    """The entries whose phrase is not ``code``.

    Compared after decrypting: DPAPI gives a different ciphertext
    every time, so two encryptions of one phrase never match as text.
    """
    return [entry for entry in entries if unprotect(str(entry.get("code", ""))) != code]


def _remember(entry: dict, code: str) -> None:
    """Add an entry, replacing any earlier one for the same phrase."""
    entry["at"] = time.time()
    _store([*_without(_entries(), code), entry])


# ----------------------------------------------------------------------
#  What the app calls
# ----------------------------------------------------------------------
def remember_send(code: str, paths: list[str]) -> None:
    _remember(
        {
            "mode": "send",
            "code": protect(code),
            "paths": [protect(str(path)) for path in paths],
        },
        code,
    )


def remember_receive(code: str, target: str | Path) -> None:
    _remember(
        {"mode": "receive", "code": protect(code), "target": protect(str(target))},
        code,
    )


def forget(code: str) -> None:
    """Drop one transfer, once it has finished."""
    _store(_without(_entries(), code))


def forget_all() -> None:
    _store([])


def unfinished() -> list[Unfinished]:
    """Every transfer that could still be resumed, newest first.

    An entry whose files or folder have gone is dropped rather than
    offered: resuming it would fail, and the list is a list of things
    that can actually be done.
    """
    resumable: list[tuple[float, Unfinished]] = []
    for entry in _entries():
        restored = _restore(entry)
        if restored is not None:
            at = entry.get("at")
            resumable.append((at if isinstance(at, int | float) else 0.0, restored))
    resumable.sort(key=lambda pair: pair[0], reverse=True)
    return [restored for _at, restored in resumable]


def _restore(entry: dict) -> Unfinished | None:
    stored_code = entry.get("code")
    if not isinstance(stored_code, str):
        return None
    # A phrase that will not decrypt was written on another machine.
    code = unprotect(stored_code)
    if not code:
        return None

    if entry.get("mode") == "send":
        paths = entry.get("paths")
        if not isinstance(paths, list):
            return None
        # unprotect passes an untagged value through, so a file from
        # before the paths were encrypted still resumes.
        existing = [
            decrypted
            for stored in paths
            if isinstance(stored, str)
            and (decrypted := unprotect(stored))
            and Path(decrypted).exists()
        ]
        return SendSession(code=code, paths=existing) if existing else None

    if entry.get("mode") == "receive":
        stored_target = entry.get("target")
        if not isinstance(stored_target, str):
            return None
        target = unprotect(stored_target)
        return (
            ReceiveSession(code=code, target=target)
            if target and Path(target).is_dir()
            else None
        )
    return None
