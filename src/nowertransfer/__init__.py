"""NowerTransfer - a one-click desktop client for your own croc relay."""

import sys
from pathlib import Path

APP_NAME = "NowerTransfer"

#: The version of the source tree. ``pyproject.toml`` reads this exact
#: line, so it is the one place to edit - but a build stamps the tag it
#: was made from over it, see :func:`resolve_version`.
FALLBACK_VERSION = "1.0.0"

#: Filename ``scripts/build.py`` writes into the bundle.
VERSION_STAMP = "version.txt"


def resolve_version() -> str:
    """What this copy of the app calls itself.

    A release is built from a git tag and records it, so the footer shows
    the version someone actually downloaded rather than whatever number
    happened to be committed. Running from source falls back.
    """
    bundle = getattr(sys, "_MEIPASS", None)
    if not bundle:
        return FALLBACK_VERSION
    try:
        stamped = (Path(bundle) / VERSION_STAMP).read_text(encoding="utf-8").strip()
    except OSError:
        return FALLBACK_VERSION
    return stamped or FALLBACK_VERSION


__version__ = resolve_version()

__all__ = ["APP_NAME", "FALLBACK_VERSION", "__version__", "resolve_version"]
