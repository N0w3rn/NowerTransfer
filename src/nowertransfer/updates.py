"""Noticing that a newer release exists.

This is not routine polish. croc changed its handshake between 10 and
11 and refuses the other major outright, so when the pinned version
moves across one, every copy handed out stops working at the same
moment. An in-app notice is the only way to say so to someone who was
given an .exe and never visits the repository.

One unauthenticated GET to the GitHub API, on a background thread, at
most once a day. Failure is silence: an app that cannot reach GitHub
is still an app that transfers files.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

RELEASES_URL = "https://api.github.com/repos/Nowenr/NowerTransfer/releases/latest"
RELEASES_PAGE = "https://github.com/Nowenr/NowerTransfer/releases/latest"

TIMEOUT_SECONDS = 6.0

#: MAJOR.MINOR.PATCH, with anything after it ignored for ordering.
_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)")


@dataclass(frozen=True)
class Release:
    version: str
    url: str


def parse_version(text: str) -> tuple[int, int, int] | None:
    """The three numbers in a version, or None if there are not three."""
    match = _VERSION.match(text.strip())
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def is_newer(candidate: str, current: str) -> bool:
    """True when ``candidate`` is a later release than ``current``.

    Anything unparseable answers False. A build that calls itself
    ``dev`` is somebody working on the code, and a pre-release suffix
    on the current version counts as that version - close enough for
    a notice, and it never nags about a version already installed.
    """
    left, right = parse_version(candidate), parse_version(current)
    if left is None or right is None:
        return False
    return left > right


def latest_release(url: str = RELEASES_URL) -> Release | None:
    """Ask GitHub what the newest release is. None if that fails."""
    request = urllib.request.Request(
        url, headers={"Accept": "application/vnd.github+json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = json.load(response)
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None
    tag = payload.get("tag_name")
    if not isinstance(tag, str) or not tag:
        return None
    link = payload.get("html_url")
    return Release(
        version=tag.lstrip("vV"),
        url=link if isinstance(link, str) and link else RELEASES_PAGE,
    )


def newer_than(current: str, url: str = RELEASES_URL) -> Release | None:
    """The newest release, but only when it is ahead of ``current``."""
    release = latest_release(url)
    if release is None or not is_newer(release.version, current):
        return None
    return release
