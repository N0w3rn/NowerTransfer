import socket
import threading

import pytest

from nowertransfer.config import RelayEndpoint
from nowertransfer.relaycheck import RelayStatus, check, reach, split_host_port


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("relay.example.com:9009", ("relay.example.com", 9009)),
        ("relay.example.com", ("relay.example.com", 9009)),
        ("10.0.0.5:9100", ("10.0.0.5", 9100)),
        ("[::1]:9009", ("::1", 9009)),
        ("[::1]", ("::1", 9009)),
        ("  relay.example.com:9009  ", ("relay.example.com", 9009)),
    ],
)
def test_split_host_port(given, expected):
    assert split_host_port(given) == expected


@pytest.fixture
def listening_port():
    """A socket that accepts and immediately closes."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    def serve() -> None:
        with server:
            try:
                connection, _ = server.accept()
                connection.close()
            except OSError:
                pass

    threading.Thread(target=serve, daemon=True).start()
    yield port


def test_reach_measures_a_listening_port(listening_port):
    assert reach(f"127.0.0.1:{listening_port}") is not None


def test_reach_returns_none_when_nothing_listens():
    # Port 1 is reserved and nothing local serves it.
    assert reach("127.0.0.1:1", timeout=1.0) is None


def test_an_unconfigured_relay_is_unreachable():
    assert check(RelayEndpoint(""), None).status is RelayStatus.UNREACHABLE


def test_a_dead_relay_is_unreachable():
    result = check(RelayEndpoint("127.0.0.1:1"), None)
    assert result.status is RelayStatus.UNREACHABLE
    assert result.milliseconds is None


def test_without_croc_it_reports_reachability_only(listening_port):
    # Never a claim about the password: only croc's handshake knows,
    # and even then only when it refuses.
    result = check(RelayEndpoint(f"127.0.0.1:{listening_port}", "pw"), None)
    assert result.status is RelayStatus.REACHABLE
    assert result.milliseconds is not None
