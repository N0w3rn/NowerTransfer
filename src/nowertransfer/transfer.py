"""Driving the croc subprocess and reporting what it does.

The worker owns a background thread; the UI only ever sees
:class:`TransferEvent` objects arriving on a queue. Nothing in this module
touches tkinter, which is what makes it testable.
"""

from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from collections.abc import Iterator, Sequence
from contextlib import suppress
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from queue import Queue
from typing import IO

from .config import RelayEndpoint

#: How long to wait before reconnecting after croc exits unexpectedly.
RETRY_DELAY_SECONDS = 15

#: A run shorter than this that ends in a config error is not a dropped
#: connection - it means the relay details are wrong.
_FAST_FAIL_SECONDS = 5.0
_FAST_FAIL_LIMIT = 4

#: croc messages that mean "your settings are wrong", as opposed to
#: "the other side is not here yet", which is worth waiting out.
_CONFIG_ERROR_MARKERS = (
    "could not connect",
    "bad password",
    "wrong password",
    "incorrect password",
)

_PROGRESS_PATTERN = re.compile(r"(\d{1,3})%")
_LINE_SEPARATORS = re.compile(rb"[\r\n]")

#: Translation keys a FAILED event can carry.
ERROR_RELAY_UNREACHABLE = "error.relay_unreachable"
ERROR_CROC_START_FAILED = "error.croc_start_failed"
ERROR_VERSION_MISMATCH = "error.version_mismatch"

#: croc 11 changed its PAKE protocol and refuses croc 10 peers outright.
#: Retrying cannot fix that, so say so instead of reconnecting forever.
_VERSION_MISMATCH_MARKERS = (
    "unsupported pake protocol version",
    "upgrade both croc",
)

#: croc prints a link to its public web-receive service that has the code
#: phrase in the query string. That phrase is the end-to-end encryption
#: key, and this app exists to keep transfers on the user's own relay, so
#: the line is kept out of the log rather than inviting someone to paste
#: the key into a third party's website.
_HIDDEN_OUTPUT = ("getcroc.com",)

#: Hide the console window croc would otherwise flash up on Windows.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


class EventType(Enum):
    OUTPUT = "output"
    RETRY = "retry"
    FINISHED = "finished"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True)
class TransferEvent:
    type: EventType
    #: croc output for OUTPUT events, a translation key for FAILED events.
    text: str = ""
    #: Untranslatable extra context, e.g. an exception message.
    detail: str = ""
    seconds: int = 0


def parse_progress(line: str) -> float | None:
    """Extract croc's percentage from an output line as a 0..1 fraction."""
    match = _PROGRESS_PATTERN.search(line)
    if match is None:
        return None
    return min(100, int(match.group(1))) / 100


def is_hidden_output(line: str) -> bool:
    """True for croc output that must not reach the UI. See ``_HIDDEN_OUTPUT``."""
    return any(marker in line for marker in _HIDDEN_OUTPUT)


def looks_like_config_error(line: str) -> bool:
    """True if croc is complaining about the relay rather than the peer."""
    lowered = line.lower()
    return any(marker in lowered for marker in _CONFIG_ERROR_MARKERS)


def looks_like_version_mismatch(line: str) -> bool:
    """True if the two sides are running incompatible croc versions."""
    lowered = line.lower()
    return any(marker in lowered for marker in _VERSION_MISMATCH_MARKERS)


def iter_output_lines(stream: IO[bytes]) -> Iterator[str]:
    """Yield croc's output line by line.

    croc redraws its progress bar with carriage returns rather than
    newlines, so splitting on ``\\n`` alone would show nothing until the
    transfer finished. Splitting on both keeps the UI live.
    """
    buffer = b""
    while True:
        chunk = stream.read1(4096) if hasattr(stream, "read1") else stream.read(4096)
        if not chunk:
            break
        buffer += chunk
        *complete, buffer = _LINE_SEPARATORS.split(buffer)
        for raw in complete:
            line = raw.decode("utf-8", "replace").strip()
            if line:
                yield line
    trailing = buffer.decode("utf-8", "replace").strip()
    if trailing:
        yield trailing


class TransferWorker:
    """Runs one croc transfer, reconnecting until it succeeds or is cancelled."""

    def __init__(
        self,
        croc: Path,
        relay: RelayEndpoint,
        events: Queue[TransferEvent],
        retry_delay: int = RETRY_DELAY_SECONDS,
    ) -> None:
        self._croc = croc
        self._relay = relay
        self._events = events
        self._retry_delay = retry_delay
        self._cancelled = threading.Event()
        self._process: subprocess.Popen[bytes] | None = None
        self._thread: threading.Thread | None = None
        self._last_line = ""

    # -- public API ----------------------------------------------------
    def start_send(self, paths: Sequence[str | Path], code: str) -> None:
        # --ignore-stdin is mandatory: a windowed build has no real stdin,
        # and croc would otherwise treat that broken handle as piped input
        # and send an empty stream instead of the selected files.
        #
        # --transport relay pins the data path to the configured relay.
        # croc's default, "auto", may also route through the public DERP
        # network, which would quietly defeat the point of this app.
        # (Requires croc 11+, which is what scripts/fetch_croc.py pins.)
        command = [
            str(self._croc),
            "--ignore-stdin",
            "send",
            "--transport",
            "relay",
            *map(str, paths),
        ]
        self._start(command, code, cwd=None)

    def start_receive(self, code: str, target_dir: str | Path) -> None:
        target = Path(target_dir)
        # --out picks the destination; cwd matches it so croc's partial
        # files are written there too rather than beside the .exe.
        command = [
            str(self._croc),
            "--yes",
            "--overwrite",
            "--out",
            str(target),
        ]
        self._start(command, code, cwd=target)

    def cancel(self) -> None:
        self._cancelled.set()
        process = self._process
        if process is not None and process.poll() is None:
            with suppress(OSError):
                process.terminate()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # -- internals -----------------------------------------------------
    def _environment(self, code: str) -> dict[str, str]:
        """croc configuration passed out of band.

        Relay address, relay password and the code phrase all go through
        the environment rather than argv. The code phrase in particular is
        the end-to-end encryption secret, and argv is readable by every
        other process on the machine.
        """
        env = os.environ.copy()
        env["CROC_RELAY"] = self._relay.host
        env["CROC_PASS"] = self._relay.croc_password()
        env["CROC_SECRET"] = code
        return env

    def _start(self, command: list[str], code: str, cwd: Path | None) -> None:
        self._cancelled.clear()
        self._thread = threading.Thread(
            target=self._run_until_done,
            args=(command, self._environment(code), cwd),
            name="croc-transfer",
            daemon=True,
        )
        self._thread.start()

    def _emit(
        self,
        event_type: EventType,
        text: str = "",
        detail: str = "",
        seconds: int = 0,
    ) -> None:
        self._events.put(TransferEvent(event_type, text, detail, seconds))

    def _run_until_done(
        self, command: list[str], env: dict[str, str], cwd: Path | None
    ) -> None:
        fast_failures = 0
        while not self._cancelled.is_set():
            exit_code, duration = self._run_once(command, env, cwd)
            if self._cancelled.is_set():
                self._emit(EventType.CANCELLED)
                return
            if exit_code == 0:
                self._emit(EventType.FINISHED)
                return
            if exit_code is None:
                return  # _run_once already reported a fatal failure

            # Incompatible peers never become compatible by waiting.
            if looks_like_version_mismatch(self._last_line):
                self._emit(
                    EventType.FAILED,
                    ERROR_VERSION_MISMATCH,
                    detail=self._last_line,
                )
                return

            # A peer that is not there yet ("room not ready") is normal and
            # worth waiting out. Only a run that dies immediately *and*
            # complains about the relay counts as a misconfiguration.
            if duration < _FAST_FAIL_SECONDS and looks_like_config_error(
                self._last_line
            ):
                fast_failures += 1
                if fast_failures >= _FAST_FAIL_LIMIT:
                    self._emit(
                        EventType.FAILED,
                        ERROR_RELAY_UNREACHABLE,
                        detail=self._last_line,
                    )
                    return
            else:
                fast_failures = 0

            self._emit(EventType.RETRY, seconds=self._retry_delay)
            if self._cancelled.wait(self._retry_delay):
                self._emit(EventType.CANCELLED)
                return

    def _run_once(
        self, command: list[str], env: dict[str, str], cwd: Path | None
    ) -> tuple[int | None, float]:
        """Run croc once.

        Returns ``(exit code, seconds)``, with ``None`` as the exit code if
        the process could not be started at all.
        """
        started = time.monotonic()
        try:
            self._process = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=_NO_WINDOW,
            )
        except OSError as error:
            self._emit(EventType.FAILED, ERROR_CROC_START_FAILED, detail=str(error))
            return None, 0.0

        assert self._process.stdout is not None
        for line in iter_output_lines(self._process.stdout):
            if is_hidden_output(line):
                continue
            self._last_line = line
            self._emit(EventType.OUTPUT, line)
        return self._process.wait(), time.monotonic() - started
