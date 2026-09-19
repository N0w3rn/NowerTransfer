import io
from pathlib import Path
from queue import Queue

import pytest

from nowertransfer.config import CROC_DEFAULT_RELAY_PASSWORD, RelayEndpoint
from nowertransfer.transfer import (
    TransferWorker,
    is_hidden_output,
    iter_output_lines,
    looks_like_config_error,
    looks_like_version_mismatch,
    parse_progress,
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


def test_the_public_web_receive_url_is_kept_out_of_the_ui():
    # croc prints https://getcroc.com/?code=<the code phrase>. That query
    # string is the end-to-end encryption key; showing it invites pasting
    # it into a third party's site.
    assert is_hidden_output("https://getcroc.com/?code=falke-wolke-tiger-83")
    assert is_hidden_output("Or open: https://getcroc.com/?code=x")
    assert not is_hidden_output("Sending 'photo.jpg' (2.1 MB)")
    assert not is_hidden_output("could not connect")


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


def test_missing_relay_password_falls_back_to_crocs_default(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        TransferWorker,
        "_start",
        lambda self, command, code, cwd: captured.update(env=self._environment(code)),
    )
    make_worker(RelayEndpoint("r:9009")).start_send(["a.txt"], "code")
    assert captured["env"]["CROC_PASS"] == CROC_DEFAULT_RELAY_PASSWORD
