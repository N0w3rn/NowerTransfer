"""Checking a relay before a transfer needs it.

Reachability is a TCP connect and is certain. The password is not: only
croc's handshake checks it, and croc reports a refusal reliably just
once - a second check moments later gets no verdict at all before the
grace period runs out.

So this reports a refused password when it sees one, and otherwise says
only that the relay answered. It never claims the password is right,
because it cannot know that.
"""

from __future__ import annotations

import os
import secrets
import socket
import subprocess
import tempfile
import threading
import time
from contextlib import suppress
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .config import RelayEndpoint
from .transfer import iter_output_lines, looks_like_wrong_relay_password

CONNECT_TIMEOUT = 4.0

#: How long a croc that has not complained gets to count as accepted.
#: There is no positive signal to wait for: croc prints its "run this on
#: the other computer" banner before it ever contacts the relay, so the
#: only honest test is whether a password error turns up.
HANDSHAKE_GRACE = 6.0

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


class RelayStatus(Enum):
    #: Answered a TCP connect. Says nothing about the password.
    REACHABLE = "reachable"
    WRONG_PASSWORD = "wrong_password"
    UNREACHABLE = "unreachable"


@dataclass(frozen=True)
class RelayCheck:
    status: RelayStatus
    #: Round trip of the TCP connect, milliseconds, when it succeeded.
    milliseconds: int | None = None
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status is RelayStatus.REACHABLE


def split_host_port(host: str) -> tuple[str, int]:
    """``host:port`` into its parts, bracketed IPv6 included."""
    remainder = host.strip()
    if remainder.startswith("["):
        closing = remainder.find("]")
        if closing != -1:
            port = remainder[closing + 1 :].lstrip(":")
            return remainder[1:closing], int(port) if port.isdigit() else 9009
    if ":" in remainder:
        name, _, port = remainder.rpartition(":")
        if port.isdigit():
            return name, int(port)
    return remainder, 9009


def reach(host: str, timeout: float = CONNECT_TIMEOUT) -> int | None:
    """Milliseconds to open a TCP connection, or None if it fails."""
    name, port = split_host_port(host)
    started = time.monotonic()
    try:
        with socket.create_connection((name, port), timeout=timeout):
            return round((time.monotonic() - started) * 1000)
    except OSError:
        return None


def check(relay: RelayEndpoint, croc: Path | None) -> RelayCheck:
    """Is the relay there, and does it take our password?"""
    if not relay.is_set:
        return RelayCheck(RelayStatus.UNREACHABLE, detail="no relay configured")

    milliseconds = reach(relay.host)
    if milliseconds is None:
        return RelayCheck(RelayStatus.UNREACHABLE)
    if croc is None:
        return RelayCheck(RelayStatus.REACHABLE, milliseconds)
    return _handshake(relay, croc, milliseconds)


def _handshake(relay: RelayEndpoint, croc: Path, milliseconds: int) -> RelayCheck:
    env = os.environ.copy()
    env["CROC_RELAY"] = relay.host
    env["CROC_PASS"] = relay.croc_password()
    # A fresh room each time: a fixed one would collide with another
    # check, or with a real transfer that happened to use it.
    env["CROC_SECRET"] = f"relay-check-{secrets.token_hex(8)}"

    # --text makes croc write the message to a croc-stdin-* file in the
    # working directory. Give it a scratch one to drop that in, or every
    # check litters wherever the app happens to have been started.
    with tempfile.TemporaryDirectory(
        prefix="nowertransfer-check-", ignore_cleanup_errors=True
    ) as scratch:
        try:
            process = subprocess.Popen(
                [
                    str(croc),
                    "--ignore-stdin",
                    "send",
                    "--transport",
                    "relay",
                    "--text",
                    "relay check",
                ],
                env=env,
                cwd=scratch,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=_NO_WINDOW,
            )
        except OSError as error:
            return RelayCheck(RelayStatus.REACHABLE, milliseconds, str(error))

        refused: list[str] = []
        seen: list[str] = []

        def read() -> None:
            assert process.stdout is not None
            for line in iter_output_lines(process.stdout):
                seen.append(line)
                if looks_like_wrong_relay_password(line):
                    refused.append(line)
                    return

        reader = threading.Thread(target=read, name="relay-check", daemon=True)
        reader.start()
        reader.join(timeout=HANDSHAKE_GRACE)

        try:
            if refused:
                return RelayCheck(RelayStatus.WRONG_PASSWORD, milliseconds, refused[0])
            # No refusal is not proof of acceptance: it answered, no more.
            return RelayCheck(
                RelayStatus.REACHABLE, milliseconds, seen[-1] if seen else ""
            )
        finally:
            with suppress(OSError):
                process.terminate()
            with suppress(subprocess.TimeoutExpired):
                process.wait(timeout=3)
