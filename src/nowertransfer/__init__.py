"""NowerTransfer - a one-click desktop client for your own croc relay."""

import sys
from pathlib import Path

APP_NAME = "NowerTransfer"

#: The version of the source tree, and the only place it is written down:
#: ``pyproject.toml`` reads this exact line. A build stamps the tag it was
#: made from over it, see :func:`resolve_version`.
VERSION = "1.0.0"

#: Shown when running from source, where there is nothing to stamp and
#: the working tree is whatever it currently is.
DEV_LABEL = "dev"

#: Shown by a build that carries no stamp at all. The build script
#: refuses to produce one, so this means a bundle was assembled by other
#: means - better to say so than to display a number it cannot vouch for.
UNKNOWN_LABEL = "unknown"

#: Filename ``scripts/build.py`` writes into the bundle.
VERSION_STAMP = "version.txt"


def resolve_version() -> str:
    """What this copy of the app calls itself.

    Three cases, each said plainly:

    * running from source - ``dev``, because there is no build and the
      working tree is whatever it currently is,
    * a build - the version it was built with, which is mandatory,
    * a bundle with no stamp - ``unknown``. A binary that cannot
      identify itself should not claim a release number.
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
