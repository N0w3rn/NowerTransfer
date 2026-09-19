"""NowerTransfer - a one-click desktop client for your own croc relay."""

import sys
from pathlib import Path

APP_NAME = "NowerTransfer"

#: The version of the source tree, and the only place it is written down:
#: ``pyproject.toml`` reads this exact line. A build stamps the tag it was
#: made from over it, see :func:`resolve_version`.
VERSION = "1.0.0"

#: Shown by a build that carries no stamp at all. That should not happen
#: for anything released, so it is better to say so than to quietly
#: display a number the binary cannot actually vouch for.
UNKNOWN_LABEL = "unknown"

#: Filename ``scripts/build.py`` writes into the bundle.
VERSION_STAMP = "version.txt"


def resolve_version() -> str:
    """What this copy of the app calls itself.

    Three cases, each said plainly:

    * running from source - ``1.0.0-dev``, because the working tree is
      whatever it currently is,
    * a build - the tag or commit ``scripts/build.py`` stamped in,
    * a build with no stamp - ``unknown``. Only happens when the sources
      were built without git present, e.g. from a downloaded zip, and a
      binary that cannot identify itself should not claim a release
      number.
    """
    bundle = getattr(sys, "_MEIPASS", None)
    if not bundle:
        return f"{VERSION}-dev"
    try:
        stamped = (Path(bundle) / VERSION_STAMP).read_text(encoding="utf-8").strip()
    except OSError:
        return UNKNOWN_LABEL
    return stamped or UNKNOWN_LABEL


__version__ = resolve_version()

__all__ = [
    "APP_NAME",
    "UNKNOWN_LABEL",
    "VERSION",
    "VERSION_STAMP",
    "__version__",
    "resolve_version",
]
