import io
import sys
import time
from pathlib import Path
from queue import Queue

import pytest

from nowertransfer.config import CROC_DEFAULT_RELAY_PASSWORD, RelayEndpoint
from nowertransfer.transfer import (
    ERROR_NO_PEER,
    ERROR_RELAY_PASSWORD,
    EventType,
    TransferWorker,
    is_hidden_output,
    iter_output_lines,
    looks_like_config_error,
    looks_like_peer_arrived,
    looks_like_version_mismatch,
    looks_like_wrong_relay_password,
    parse_incoming,
    parse_progress,
    parse_rate_and_remaining,
    redact,
)


# ----------------------------------------------------------------------
#  Output parsing
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("Receiving 'photo.jpg' 42% |####    | (4.2/10 MB, 3 MB/s)", 0.42),
        ("100%", 1.0),
        ("0%", 0.0),
        # croc has been seen reporting past 100 while flushing.
        ("128%", 1.0),
        ("no percentage here", None),
        ("", None),
    ],
)
def test_parse_progress(line, expected):
    assert parse_progress(line) == expected


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("could not connect to relay", True),
        ("Error: bad password", True),
        ("WRONG PASSWORD", True),
        # The peer simply not being there yet is worth waiting out.
        ("room not ready", False),
        ("sending file", False),
    ],
)
def test_config_error_detection(line, expected):
    assert looks_like_config_error(line) is expected


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        # Verified against croc: this is what a wrong relay password
        # produces. A wrong code phrase produces no message at all, it
        # just waits, so blaming the code phrase here misdirects the user.
        ("could not connect to 127.0.0.1:9009: bad password", True),
        ("WRONG PASSWORD", True),
        ("could not connect to relay", False),
        ("room not ready", False),
    ],
)
def test_a_refused_password_is_the_relay_not_the_code_phrase(line, expected):
    assert looks_like_wrong_relay_password(line) is expected


def test_a_refused_password_is_reported_as_such():
    events = Queue()
    worker = TransferWorker(
        Path("croc"), RelayEndpoint("r:9009", "wrong"), events, retry_delay=0
    )
    emitted, _relays = drive(
        worker, events, last_line="could not connect to r:9009: bad password"
    )

    failed = [event for event in emitted if event.type is EventType.FAILED]
    assert failed and failed[0].text == ERROR_RELAY_PASSWORD


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        # croc 11 rejects croc 10 peers; waiting cannot fix it.
        (
            "peer uses unsupported PAKE protocol version 0; upgrade both croc clients",
            True,
        ),
        ("Error: unsupported PAKE protocol version", True),
        ("could not connect", False),
        ("room not ready", False),
    ],
)
def test_version_mismatch_detection(line, expected):
    assert looks_like_version_mismatch(line) is expected


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        # The only size the receiving side ever learns: croc reports no
        # progress at all through a pipe.
        ("Receiving 'holiday.zip' (4.2 GB)", ("holiday.zip", "4.2 GB")),
        ("Sending 'a b c.txt' (12 kB)", ("a b c.txt", "12 kB")),
        ("Receiving 'x' (0 B)", ("x", "0 B")),
        ("Receiving (192.168.2.117<-127.0.0.1)", None),
        ("connecting...", None),
    ],
)
def test_parse_incoming(line, expected):
    assert parse_incoming(line) == expected


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        # Measured on a throttled transfer against a real relay.
        (
            "sample.bin  28% |#####    | (26/90 MB, 717 kB/s) [34s:1m29s]",
            ("717 kB/s", "1m29s"),
        ),
        (
            "sample.bin   2% |         | (1.9/90 MB, 1.2 MB/s) [1s:1m14s]",
            ("1.2 MB/s", "1m14s"),
        ),
        (
            "big.bin 100% |#########| (400/400 kB, 350 MB/s) [12s:0s]",
            ("350 MB/s", "0s"),
        ),
        # The first line of a transfer: no rate yet, and the brackets
        # read [0s:0s]. "0s left" before anything has moved would be a
        # promise the app cannot keep, so both or neither.
        ("probe.bin   0% |         | ( 0 B/400 kB) [0s:0s]", None),
        ("Receiving 'photo.jpg' (2.1 MB)", None),
        ("46%", None),
        ("", None),
    ],
)
def test_parse_rate_and_remaining(line, expected):
    assert parse_rate_and_remaining(line) == expected


def test_the_public_web_receive_url_is_kept_out_of_the_ui():
    # That query string is the encryption key; showing it invites
    # pasting it into a third party's site.
    assert is_hidden_output("https://getcroc.com/?code=falke-wolke-tiger-83")
    assert is_hidden_output("Or open: https://getcroc.com/?code=x")
    assert not is_hidden_output("Sending 'photo.jpg' (2.1 MB)")
    assert not is_hidden_output("could not connect")


def test_the_relay_password_is_masked_in_the_log():
    # croc prints the whole command for the other side. Measured
    # against a real relay: the line reads
    #   croc --relay host:9009 --pass <the actual password> <code>
    # and the details log showed it verbatim, undoing the masking the
    # settings screen does.
    line = (
        "croc --relay ftp.example.com:9009 --pass hunter2secret "
        "falke-wolke-tiger-83 (code copied to clipboard)"
    )
    masked = redact(line)

    assert "hunter2secret" not in masked
    assert "--pass ••••••" in masked
    # Everything else survives: the log is there to be read.
    assert "ftp.example.com:9009" in masked
    assert "falke-wolke-tiger-83" in masked


def test_redacting_leaves_ordinary_output_alone():
    for line in ("Sending 'photo.jpg' (2.1 MB)", "could not connect", "46%"):
        assert redact(line) == line


def test_output_is_split_on_carriage_returns_too():
    # croc redraws its progress bar with \r; splitting on \n alone would
    # show nothing until the transfer had finished.
    stream = io.BytesIO(b"connecting\n10%\r20%\r30%\ndone\n")
    assert list(iter_output_lines(stream)) == [
        "connecting",
        "10%",
        "20%",
        "30%",
        "done",
    ]


def test_trailing_output_without_a_separator_is_still_reported():
    stream = io.BytesIO(b"first\nlast line without newline")
    assert list(iter_output_lines(stream)) == ["first", "last line without newline"]


def test_blank_lines_are_dropped():
    stream = io.BytesIO(b"a\n\n\r\n   \nb\n")
    assert list(iter_output_lines(stream)) == ["a", "b"]


def test_invalid_utf8_does_not_crash_the_reader():
    stream = io.BytesIO(b"ok\n\xff\xfe\nfine\n")
    assert next(iter(iter_output_lines(stream))) == "ok"


# ----------------------------------------------------------------------
#  Command construction
# ----------------------------------------------------------------------
def make_worker(relay: RelayEndpoint) -> TransferWorker:
    return TransferWorker(Path("croc"), relay, Queue())


def test_secrets_are_passed_through_the_environment_not_argv(monkeypatch):
    """argv is readable by any process; the code phrase is the crypto secret."""
    captured = {}

    def fake_start(self, command, code, cwd):
        captured["command"] = command
        captured["env"] = self._environment(code)

    monkeypatch.setattr(TransferWorker, "_start", fake_start)

    worker = make_worker(RelayEndpoint("relay.example.com:9009", "hunter2"))
    worker.start_send(["file.txt"], "falke-wolke-tiger-nebel-83")

    joined = " ".join(captured["command"])
    assert "hunter2" not in joined
    assert "falke-wolke-tiger-nebel-83" not in joined

    env = captured["env"]
    assert env["CROC_RELAY"] == "relay.example.com:9009"
    assert env["CROC_PASS"] == "hunter2"
    assert env["CROC_SECRET"] == "falke-wolke-tiger-nebel-83"


def test_send_ignores_stdin(monkeypatch):
    # Without --ignore-stdin a windowed build sends its broken stdin
    # handle instead of the selected files.
    captured = {}
    monkeypatch.setattr(
        TransferWorker,
        "_start",
        lambda self, command, code, cwd: captured.update(command=command),
    )
    make_worker(RelayEndpoint("r:9009")).start_send(["a.txt"], "code")
    assert "--ignore-stdin" in captured["command"]
    assert captured["command"][-1] == "a.txt"


def test_send_pins_the_data_path_to_the_configured_relay(monkeypatch):
    # croc's default "auto" transport may route through the public DERP
    # network, which would defeat the point of a self-hosted relay.
    captured = {}
    monkeypatch.setattr(
        TransferWorker,
        "_start",
        lambda self, command, code, cwd: captured.update(command=command),
    )
    make_worker(RelayEndpoint("r:9009")).start_send(["a.txt"], "code")
    command = captured["command"]
    assert command[command.index("--transport") + 1] == "relay"
    # It is a flag of the `send` subcommand, so it has to follow it.
    assert command.index("--transport") > command.index("send")


def test_receive_writes_into_the_chosen_directory(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(
        TransferWorker,
        "_start",
        lambda self, command, code, cwd: captured.update(command=command, cwd=cwd),
    )
    make_worker(RelayEndpoint("r:9009")).start_receive("code", tmp_path)
    assert "--out" in captured["command"]
    assert captured["command"][captured["command"].index("--out") + 1] == str(tmp_path)
    assert captured["cwd"] == tmp_path


# ----------------------------------------------------------------------
#  The retry loop
# ----------------------------------------------------------------------
def drive(worker, events, exit_code=1, last_line="", runs=12):
    """Run the retry loop with croc replaced by a canned result."""
    seen_relays = []

    def fake_run_once(_command, env, _cwd):
        seen_relays.append(env.get("CROC_RELAY"))
        worker._last_line = last_line
        if len(seen_relays) >= runs:
            worker.cancel()  # stop a loop that should have stopped itself
        return exit_code

    worker._run_once = fake_run_once
    worker._run_until_done(["croc"], "code", None)
    emitted = []
    while not events.empty():
        emitted.append(events.get_nowait())
    return emitted, seen_relays


def types(emitted) -> list[EventType]:
    return [event.type for event in emitted]


UNREACHABLE = "relay connection failed: could not connect to r:9009"


def test_an_unreachable_relay_is_reported_rather_than_retried_forever():
    # Regression: this also required the run to be under five seconds.
    # croc retries internally and takes ten, so it never fired.
    events = Queue()
    worker = TransferWorker(
        Path("croc"), RelayEndpoint("r:9009"), events, retry_delay=0
    )
    emitted, relays = drive(worker, events, last_line=UNREACHABLE)

    assert EventType.FAILED in types(emitted)
    assert len(relays) == 3  # _RELAY_ERROR_LIMIT, not until cancelled


def test_a_peer_that_has_not_arrived_yet_is_waited_out():
    # "room not ready" only means the other side is not there yet.
    events = Queue()
    worker = TransferWorker(
        Path("croc"), RelayEndpoint("r:9009"), events, retry_delay=0
    )
    emitted, _relays = drive(worker, events, last_line="room not ready", runs=8)

    assert EventType.FAILED not in types(emitted)
    assert types(emitted).count(EventType.RETRY) >= 5


def test_a_version_mismatch_gives_up_at_once():
    events = Queue()
    worker = TransferWorker(
        Path("croc"), RelayEndpoint("r:9009"), events, retry_delay=0
    )
    emitted, relays = drive(
        worker, events, last_line="peer uses unsupported PAKE protocol version 0"
    )
    assert types(emitted) == [EventType.FAILED]
    assert len(relays) == 1


def test_fallback_moves_to_the_public_relay_and_announces_it():
    events = Queue()
    worker = TransferWorker(
        Path("croc"),
        RelayEndpoint("r:9009"),
        events,
        retry_delay=0,
        allow_public_fallback=True,
    )
    emitted, relays = drive(worker, events, last_line=UNREACHABLE, runs=8)

    assert EventType.FELL_BACK in types(emitted)
    # First the user's relay, then croc's own (no CROC_RELAY set).
    assert relays[0] == "r:9009"
    assert relays[-1] is None
    # The switch must be visible, not silent.
    assert EventType.FELL_BACK in types(emitted)


def test_without_fallback_the_transfer_never_leaves_the_configured_relay():
    events = Queue()
    worker = TransferWorker(
        Path("croc"), RelayEndpoint("r:9009"), events, retry_delay=0
    )
    emitted, relays = drive(worker, events, last_line=UNREACHABLE)

    assert EventType.FELL_BACK not in types(emitted)
    assert all(relay == "r:9009" for relay in relays)


def test_a_successful_run_finishes_immediately():
    events = Queue()
    worker = TransferWorker(
        Path("croc"), RelayEndpoint("r:9009"), events, retry_delay=0
    )
    emitted, relays = drive(worker, events, exit_code=0)
    assert types(emitted) == [EventType.FINISHED]
    assert len(relays) == 1


# ----------------------------------------------------------------------
#  Public relay
# ----------------------------------------------------------------------
def test_the_public_relay_is_selected_by_unsetting_the_variables(monkeypatch):
    # croc uses its own relay when CROC_RELAY is absent - removed, not
    # left alone, since the surrounding environment may define it.
    monkeypatch.setenv("CROC_RELAY", "inherited.example.com:9009")
    monkeypatch.setenv("CROC_PASS", "inherited")

    worker = make_worker(RelayEndpoint("mine.example.com:9009", "mypass"))
    public = worker._environment("code", public=True)
    assert "CROC_RELAY" not in public
    assert "CROC_PASS" not in public
    assert public["CROC_SECRET"] == "code"

    own = worker._environment("code")
    assert own["CROC_RELAY"] == "mine.example.com:9009"


def test_an_unset_relay_means_the_public_one(monkeypatch):
    monkeypatch.setenv("CROC_RELAY", "inherited.example.com:9009")
    env = make_worker(RelayEndpoint(""))._environment("code")
    assert "CROC_RELAY" not in env


def test_fallback_is_off_unless_asked_for():
    assert make_worker(RelayEndpoint("r:9009"))._allow_public_fallback is False
    worker = TransferWorker(
        Path("croc"), RelayEndpoint("r:9009"), Queue(), allow_public_fallback=True
    )
    assert worker._allow_public_fallback is True


def test_missing_relay_password_falls_back_to_crocs_default(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        TransferWorker,
        "_start",
        lambda self, command, code, cwd: captured.update(env=self._environment(code)),
    )
    make_worker(RelayEndpoint("r:9009")).start_send(["a.txt"], "code")
    assert captured["env"]["CROC_PASS"] == CROC_DEFAULT_RELAY_PASSWORD


def test_receiving_keeps_overwrite_so_it_can_resume(monkeypatch, tmp_path):
    # Reads backwards and is easy to "clean up" into a bug. croc's own
    # wording: "do not prompt to overwrite or resume". Without the
    # flag croc asks "Resume 'big.bin' (37.3%)? (y/N)", --yes does not
    # answer that prompt, and croc skips the file - measured, nothing
    # transfers at all. With it, an interrupted 120 MB receive went
    # from 39% to 90% on the next run instead of starting over.
    captured = {}
    monkeypatch.setattr(
        TransferWorker,
        "_start",
        lambda self, command, code, cwd: captured.update(command=command),
    )
    make_worker(RelayEndpoint("r:9009")).start_receive("code", tmp_path)

    assert "--overwrite" in captured["command"]
    assert "--yes" in captured["command"]


# ----------------------------------------------------------------------
#  Giving up when nobody comes
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    ("line", "expected"),
    [
        # Measured against a real relay. Both sides print their pair of
        # addresses at the moment they connect, and nothing before it.
        ("Sending (84.150.122.176->192.168.2.117)", True),
        ("Receiving (192.168.2.117<-84.150.122.176)", True),
        ("probe.bin   0% |    | ( 0 B/400 kB) [0s:0s]", True),
        # The sending side prints these immediately, peer or no peer.
        ("Sending 0 files (390.6 kB)", False),
        ("Sending 'probe.bin' (390.6 kB)", False),
        ("On the other computer, run:", False),
        # The receiving side, still looking.
        ("waiting for sender...", False),
        ("authenticating code...", False),
    ],
)
def test_only_the_address_pair_means_the_peer_arrived(line, expected):
    assert looks_like_peer_arrived(line) is expected


def _fake_croc(worker, script, **kwargs):
    """Run the retry loop against a stand-in for croc."""
    worker._run_until_done([sys.executable, "-c", script], "code", None)
    emitted = []
    while not worker._events.empty():
        emitted.append(worker._events.get_nowait())
    return emitted


def test_a_croc_nobody_joins_is_given_up_on():
    # A wrong code phrase makes croc wait, not complain, so nothing but
    # a clock can tell the difference between a typo and a slow peer.
    worker = TransferWorker(
        Path("croc"), RelayEndpoint("r:9009"), Queue(), retry_delay=0, give_up_after=0.4
    )
    started = time.monotonic()
    emitted = _fake_croc(
        worker,
        "import time; print('Sending 0 files (1 B)', flush=True); time.sleep(30)",
    )
    took = time.monotonic() - started

    failed = [event for event in emitted if event.type is EventType.FAILED]
    assert failed and failed[0].text == ERROR_NO_PEER
    assert took < 10, f"waited {took:.1f}s; the watchdog did not fire"


def test_a_transfer_that_started_is_left_alone():
    # The deadline is for an empty room, not for a big file. Once the
    # two sides have met, croc may take as long as it needs.
    worker = TransferWorker(
        Path("croc"), RelayEndpoint("r:9009"), Queue(), retry_delay=0, give_up_after=0.3
    )
    emitted = _fake_croc(
        worker,
        "import time;print('Sending (1.2.3.4->5.6.7.8)', flush=True);time.sleep(1.2)",
    )

    assert types(emitted)[-1] is EventType.FINISHED
    assert not any(event.text == ERROR_NO_PEER for event in emitted)


def test_the_deadline_can_be_switched_off():
    worker = TransferWorker(
        Path("croc"), RelayEndpoint("r:9009"), Queue(), retry_delay=0, give_up_after=0
    )
    emitted = _fake_croc(worker, "print('done')")
    assert types(emitted)[-1] is EventType.FINISHED
