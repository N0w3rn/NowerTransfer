"""Noticing a newer release.

The point is not vanity. croc refuses peers running a different major
version, so when the pinned croc moves across one, every copy handed
out stops working at the same moment and has to be replaced.
"""

from __future__ import annotations

import io
import json
import urllib.error

import pytest

from nowertransfer import updates
from nowertransfer.updates import Release, is_newer, latest_release, parse_version


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.2.3", (1, 2, 3)),
        ("v1.2.3", (1, 2, 3)),
        ("  1.0.0  ", (1, 0, 0)),
        ("1.2.3-rc1", (1, 2, 3)),
        ("dev", None),
        ("unknown", None),
        ("1.2", None),
        ("", None),
    ],
)
def test_parse_version(text, expected):
    assert parse_version(text) == expected


@pytest.mark.parametrize(
    ("candidate", "current", "expected"),
    [
        ("1.1.0", "1.0.0", True),
        ("2.0.0", "1.9.9", True),
        ("1.0.1", "1.0.0", True),
        ("1.0.0", "1.0.0", False),
        ("1.0.0", "1.0.1", False),
        # A source checkout is somebody working on the code.
        ("9.9.9", "dev", False),
        ("9.9.9", "unknown", False),
        # A pre-release of what is installed is not an upgrade.
        ("1.0.0-rc2", "1.0.0", False),
    ],
)
def test_is_newer(candidate, current, expected):
    assert is_newer(candidate, current) is expected


def _answer(monkeypatch, payload, status=200):
    del status

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()
            return False

    monkeypatch.setattr(
        updates.urllib.request,
        "urlopen",
        lambda _request, timeout=0: Response(json.dumps(payload).encode()),
    )


def test_the_tag_becomes_the_version(monkeypatch):
    _answer(
        monkeypatch,
        {"tag_name": "v1.4.0", "html_url": "https://example.com/releases/1.4.0"},
    )
    assert latest_release() == Release("1.4.0", "https://example.com/releases/1.4.0")


def test_a_release_without_a_link_falls_back_to_the_releases_page(monkeypatch):
    _answer(monkeypatch, {"tag_name": "1.4.0"})
    release = latest_release()
    assert release is not None and release.url == updates.RELEASES_PAGE


@pytest.mark.parametrize("payload", [{}, {"tag_name": ""}, [], "nonsense"])
def test_an_answer_without_a_tag_is_no_answer(monkeypatch, payload):
    _answer(monkeypatch, payload)
    assert latest_release() is None


def test_a_network_that_is_not_there_is_silent(monkeypatch):
    # An app that cannot reach GitHub is still an app that transfers
    # files, so this must never surface as an error.
    def refuse(_request, timeout=0):
        raise urllib.error.URLError("no route to host")

    monkeypatch.setattr(updates.urllib.request, "urlopen", refuse)
    assert latest_release() is None
    assert updates.newer_than("1.0.0") is None


def test_broken_json_is_silent(monkeypatch):
    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()
            return False

    monkeypatch.setattr(
        updates.urllib.request,
        "urlopen",
        lambda _request, timeout=0: Response(b"{not json"),
    )
    assert latest_release() is None


def test_newer_than_only_answers_for_an_actual_upgrade(monkeypatch):
    _answer(monkeypatch, {"tag_name": "v1.0.0", "html_url": "https://example.com"})
    assert updates.newer_than("1.0.0") is None
    assert updates.newer_than("0.9.0") == Release("1.0.0", "https://example.com")
