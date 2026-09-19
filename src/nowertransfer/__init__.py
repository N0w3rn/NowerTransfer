"""NowerTransfer - a one-click desktop client for your own croc relay."""

import sys
from pathlib import Path

APP_NAME = "NowerTransfer"

#: The source tree's version, and the only place it is written down -
#: ``pyproject.toml`` reads this exact line.
VERSION = "1.0.0"

DEV_LABEL = "dev"
UNKNOWN_LABEL = "unknown"

#: Filename ``scripts/build.py`` writes into the bundle.
VERSION_STAMP = "version.txt"


def resolve_version() -> str:
    """What this copy calls itself: ``dev`` from source, otherwise the
    version it was built with, or ``unknown`` if a bundle carries none.

    A binary that cannot identify itself must not claim a release number.
    """
    bundle = getattr(sys, "_MEIPASS", None)
    if not bundle:
        return DEV_LABEL
    try:
        stamped = (Path(bundle) / VERSION_STAMP).read_text(encoding="utf-8").strip()
    except OSError:
        return UNKNOWN_LABEL
    return stamped or UNKNOWN_LABEL


__version__ = resolve_version()

__all__ = [
    "APP_NAME",
    "DEV_LABEL",
    "UNKNOWN_LABEL",
    "VERSION",
    "VERSION_STAMP",
    "__version__",
    "resolve_version",
]
