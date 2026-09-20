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
from collections.abc import Iterator, Sequence
from contextlib import suppress
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from queue import Queue
from typing import IO

from .config import RelayEndpoint

RETRY_DELAY_SECONDS = 15

#: Consecutive relay errors before giving up. More than one so a blip
#: does not look like a misconfiguration, few because these do not heal.
_RELAY_ERROR_LIMIT = 3

#: The relay rejected our password. Never the code phrase: a wrong code
#: phrase puts you in a different PAKE room, where croc simply waits.
_RELAY_PASSWORD_MARKERS = (
    "bad password",
    "wrong password",
    "incorrect password",
)

#: "Your settings are wrong", as opposed to "the peer is not here yet".
_CONFIG_ERROR_MARKERS = ("could not connect", *_RELAY_PASSWORD_MARKERS)

_PROGRESS_PATTERN = re.compile(r"(\d{1,3})%")

#: croc announces the incoming payload as: Receiving 'name' (6.0 MB),
#: which is how the receiving side learns the size before any byte of
#: it has arrived.
_INCOMING_PATTERN = re.compile(
    r"(?:Receiving|Sending)\s+'(?P<name>[^']+)'\s+\((?P<size>[^)]+)\)"
)
_LINE_SEPARATORS = re.compile(rb"[\r\n]")

ERROR_NO_PEER = "error.no_peer"
ERROR_RELAY_UNREACHABLE = "error.relay_unreachable"
ERROR_RELAY_PASSWORD = "error.relay_password"
ERROR_CROC_START_FAILED = "error.croc_start_failed"
ERROR_VERSION_MISMATCH = "error.version_mismatch"

#: croc 11 changed its PAKE protocol and rejects croc 10 peers outright.
_VERSION_MISMATCH_MARKERS = (
    "unsupported pake protocol version",
    "upgrade both croc",
)

#: croc prints a getcroc.com link with the code phrase in the query
#: string. That phrase is the encryption key, so it stays out of the log.
_HIDDEN_OUTPUT = ("getcroc.com",)

#: The relay password as croc echoes it: `--pass <value>`.
_PASS_FLAG_PATTERN = re.compile(r"(--pass\s+)\S+")

#: croc names both addresses the moment the two sides are connected:
#: `Sending (a->b)` or `Receiving (a<-b)`. Measured against a real
#: relay: the sending side prints nothing at all between its banner
#: and this line, so it is the only thing that marks a peer arriving.
_PEER_PATTERN = re.compile(r"(?:Sending|Receiving)\s*\([^)]*(?:->|<-)[^)]*\)")

#: How long croc may sit in a room nobody else joins. A wrong code
#: phrase is silent - croc waits rather than complaining - so without
#: this the app waits with it, forever.
GIVE_UP_WITHOUT_PEER_SECONDS = 240.0

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


class EventType(Enum):
    OUTPUT = "output"
    RETRY = "retry"
    #: Switched from the configured relay to croc's public one.
    FELL_BACK = "fell_back"
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


def parse_incoming(line: str) -> tuple[str, str] | None:
    """``(name, size)`` from croc's announcement of the payload."""
    match = _INCOMING_PATTERN.search(line)
    if match is None:
        return None
    return match.group("name"), match.group("size").strip()


def is_hidden_output(line: str) -> bool:
    """True for croc output that must not reach the UI."""
    return any(marker in line for marker in _HIDDEN_OUTPUT)


def redact(line: str) -> str:
    """Mask secrets croc prints back at us.

    croc spells out the command for the other side, relay password and
    all. The settings screen masks that password, so the transfer log
    must not undo it - a screenshot of a transfer would otherwise hand
    the relay over.
    """
    return _PASS_FLAG_PATTERN.sub(r"\g<1>••••••", line)


def looks_like_config_error(line: str) -> bool:
    """True if croc is complaining about the relay rather than the peer."""
    lowered = line.lower()
    return any(marker in lowered for marker in _CONFIG_ERROR_MARKERS)


def looks_like_wrong_relay_password(line: str) -> bool:
    """True if the relay refused our password."""
    lowered = line.lower()
    return any(marker in lowered for marker in _RELAY_PASSWORD_MARKERS)


def looks_like_peer_arrived(line: str) -> bool:
    """True once croc has the other side on the line."""
    return _PEER_PATTERN.search(line) is not None or parse_progress(line) is not None


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
        allow_public_fallback: bool = False,
        give_up_after: float = GIVE_UP_WITHOUT_PEER_SECONDS,
    ) -> None:
        self._croc = croc
        self._relay = relay
        self._events = events
        self._retry_delay = retry_delay
        self._allow_public_fallback = allow_public_fallback
        self._give_up_after = give_up_after
        self._cancelled = threading.Event()
        self._process: subprocess.Popen[bytes] | None = None
        self._thread: threading.Thread | None = None
        self._last_line = ""
        self._gave_up = False

    # -- public API ----------------------------------------------------
    def start_send(self, paths: Sequence[str | Path], code: str) -> None:
        # --ignore-stdin: a windowed build's stdin is a broken handle that
        # croc would treat as piped input, sending that instead of the files.
        # --transport relay: croc's "auto" may route via the public DERP
        # network. Needs croc 11+, which fetch_croc.py pins.
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
        # cwd matches --out so partial files land there too, not beside the .exe.
        #
        # --overwrite is what makes an interrupted receive resume, the
        # opposite of how it reads. croc's own wording is "do not
        # prompt to overwrite or resume": without it croc asks
        # "Resume 'big.bin' (37.3%)? (y/N)", and --yes does not answer
        # that particular prompt - measured, croc then skips the file
        # and transfers nothing. With it, croc re-reads what is already
        # on disk and carries on. Measured over a throttled 120 MB
        # transfer: interrupted at 39%, the next run reached 90%.
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

    # -- internals -----------------------------------------------------
    def _environment(self, code: str, *, public: bool = False) -> dict[str, str]:
        """croc configuration, passed out of band.

        argv is readable by every other process on the machine, and the
        code phrase is the encryption secret, so it goes through the
        environment along with the relay details.

        ``public`` *removes* the relay variables rather than leaving them
        alone - the surrounding environment may define them.
        """
        env = os.environ.copy()
        if public or not self._relay.is_set:
            env.pop("CROC_RELAY", None)
            env.pop("CROC_PASS", None)
        else:
            env["CROC_RELAY"] = self._relay.host
            env["CROC_PASS"] = self._relay.croc_password()
        env["CROC_SECRET"] = code
        return env

    def _start(self, command: list[str], code: str, cwd: Path | None) -> None:
        self._cancelled.clear()
        self._thread = threading.Thread(
            target=self._run_until_done,
            args=(command, code, cwd),
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

    def _run_until_done(self, command: list[str], code: str, cwd: Path | None) -> None:
        relay_errors = 0
        on_public = not self._relay.is_set
        while not self._cancelled.is_set():
            env = self._environment(code, public=on_public)
            exit_code = self._run_once(command, env, cwd)
            if self._cancelled.is_set():
                self._emit(EventType.CANCELLED)
                return
            if self._gave_up:
                self._emit(EventType.FAILED, ERROR_NO_PEER)
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

            # A peer that has not arrived yet is worth waiting out; croc
            # complaining about the relay itself is not.
            if looks_like_config_error(self._last_line):
                relay_errors += 1
                if relay_errors >= _RELAY_ERROR_LIMIT:
                    if self._allow_public_fallback and not on_public:
                        on_public = True
                        relay_errors = 0
                        self._emit(EventType.FELL_BACK)
                        continue
                    self._emit(
                        EventType.FAILED,
                        ERROR_RELAY_PASSWORD
                        if looks_like_wrong_relay_password(self._last_line)
                        else ERROR_RELAY_UNREACHABLE,
                        detail=self._last_line,
                    )
                    return
            else:
                relay_errors = 0

            self._emit(EventType.RETRY, seconds=self._retry_delay)
            if self._cancelled.wait(self._retry_delay):
                self._emit(EventType.CANCELLED)
                return

    def _run_once(
        self, command: list[str], env: dict[str, str], cwd: Path | None
    ) -> int | None:
        """Run croc once, returning its exit code.

        ``None`` means the process could not be started at all, which has
        already been reported as a failure.
        """
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
            return None

        peer = threading.Event()
        watchdog = threading.Thread(
            target=self._give_up_without_a_peer,
            args=(self._process, peer),
            name="croc-watchdog",
            daemon=True,
        )
        watchdog.start()

        assert self._process.stdout is not None
        try:
            for line in iter_output_lines(self._process.stdout):
                if is_hidden_output(line):
                    continue
                line = redact(line)
                self._last_line = line
                if looks_like_peer_arrived(line):
                    peer.set()
                self._emit(EventType.OUTPUT, line)
        finally:
            # Either the peer turned up or croc is finished; nothing
            # left for the watchdog to guard.
            peer.set()
        return self._process.wait()

    def _give_up_without_a_peer(
        self, process: subprocess.Popen[bytes], peer: threading.Event
    ) -> None:
        """Stop croc if the other side never appears.

        A wrong code phrase is silent: croc waits in a room nobody else
        is in, and waits for as long as it is left alone. Waiting out a
        peer who is merely slow is the point of the retry loop, so this
        only fires while the two sides have not met - once they have,
        the transfer may take as long as it takes.
        """
        if self._give_up_after <= 0:
            return
        if peer.wait(self._give_up_after):
            return
        if self._cancelled.is_set():
            return
        self._gave_up = True
        with suppress(OSError):
            process.terminate()
