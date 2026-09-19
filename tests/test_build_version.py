"""The build script's version handling, which is mandatory by design."""

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build  # noqa: E402


@pytest.fixture(autouse=True)
def no_ci_tag(monkeypatch):
    monkeypatch.delenv("GITHUB_REF_NAME", raising=False)


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("1.0.0", "1.0.0"),
        ("v1.0.0", "1.0.0"),
        ("12.34.56", "12.34.56"),
        ("1.0.0-rc1", "1.0.0-rc1"),
        ("1.0.0-test", "1.0.0-test"),
        ("1.0.0+build7", "1.0.0+build7"),
    ],
)
def test_accepted_versions(given, expected):
    assert build.resolve_app_version(given) == expected


@pytest.mark.parametrize(
    "given",
    ["", "1.0", "1", "one.two.three", "1.0.0.0", "latest", "v", "1.0.0-", " 1.0.0"],
)
def test_rejected_versions(given):
    with pytest.raises(SystemExit) as raised:
        build.resolve_app_version(given)
    # The message has to say what a version looks like, not just "no".
    assert "MAJOR.MINOR.PATCH" in str(raised.value)


def test_a_missing_version_is_refused_with_the_format():
    with pytest.raises(SystemExit) as raised:
        build.resolve_app_version(None)
    message = str(raised.value)
    assert "no version given" in message
    assert "poe build 1.0.0" in message


def test_a_release_tag_fills_it_in(monkeypatch):
    # The one case that needs no argument: the release workflow.
    monkeypatch.setenv("GITHUB_REF_NAME", "v1.2.3")
    assert build.resolve_app_version(None) == "1.2.3"


def test_a_branch_name_is_not_a_version(monkeypatch):
    # A push to main sets GITHUB_REF_NAME too.
    monkeypatch.setenv("GITHUB_REF_NAME", "main")
    with pytest.raises(SystemExit):
        build.resolve_app_version(None)


def test_an_explicit_version_beats_the_tag(monkeypatch):
    monkeypatch.setenv("GITHUB_REF_NAME", "v1.2.3")
    assert build.resolve_app_version("9.9.9") == "9.9.9"
