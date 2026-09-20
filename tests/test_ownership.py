"""Restricting files to the account that wrote them.

The fault these guard: ``chmod(0o600)`` looks like it locks a file down
and on Windows does nothing of the sort. Measured on a real machine, a
second local account had full control of the app's settings directory
while the code believed it was owner-only.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from nowertransfer.ownership import current_user_sid, restrict_to_owner

windows_only = pytest.mark.skipif(
    sys.platform != "win32", reason="access control lists are a Windows thing"
)


def acl_of(path) -> str:
    return subprocess.run(
        ["icacls", str(path)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def entries_of(path) -> list[str]:
    """The ``ACCOUNT:(rights)`` entries icacls reports.

    icacls prints the first entry on the same line as the path, and
    finishes with a localised summary line - neither of which is an
    entry, and the path contains a colon of its own.
    """
    listing = acl_of(path).replace(str(path), "")
    return [line.strip() for line in listing.splitlines() if ":(" in line]


@windows_only
def test_the_current_account_has_a_sid():
    sid = current_user_sid()
    assert sid is not None
    assert sid.startswith("S-1-"), sid


@windows_only
def test_a_restricted_file_is_readable_by_nobody_else(tmp_path):
    secret = tmp_path / "session.json"
    secret.write_text("{}", encoding="utf-8")

    assert restrict_to_owner(secret)

    # Exactly one entry is the whole property: no Administrators, no
    # SYSTEM, no second local account. Checking for those by name
    # would depend on the language Windows is installed in.
    granted = entries_of(secret)
    assert len(granted) == 1, f"expected one entry, got {granted}"
    assert granted[0].endswith(":(F)"), granted


@windows_only
def test_a_restricted_directory_passes_it_on(tmp_path):
    folder = tmp_path / "config"
    folder.mkdir()

    assert restrict_to_owner(folder)

    granted = entries_of(folder)
    assert len(granted) == 1, f"expected one entry, got {granted}"
    # (OI)(CI): what the app writes in here later inherits the same.
    assert "(OI)" in granted[0] and "(CI)" in granted[0], granted


@pytest.mark.skipif(sys.platform == "win32", reason="the POSIX path")
def test_elsewhere_it_falls_back_to_the_mode(tmp_path):
    secret = tmp_path / "session.json"
    secret.write_text("{}", encoding="utf-8")

    assert restrict_to_owner(secret)
    assert secret.stat().st_mode & 0o777 == 0o600

    folder = tmp_path / "config"
    folder.mkdir()
    assert restrict_to_owner(folder)
    # 0o700, not 0o600: a directory has to stay traversable.
    assert folder.stat().st_mode & 0o777 == 0o700
