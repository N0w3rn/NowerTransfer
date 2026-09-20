"""Brand fonts, loaded for this process only.

The two faces ship with the app. Windows can register a font for one
process without installing it, which is what ``AddFontResourceEx`` with
``FR_PRIVATE`` does. Anything that does not work falls back to a system
face, so a missing or unregisterable font costs looks, never legibility.
"""

from __future__ import annotations

import sys
from contextlib import suppress
from pathlib import Path

from ..paths import bundle_dir, project_root

FONT_DIRNAME = "fonts"

#: Family name -> the file that provides it.
BUNDLED = {
    "Space Grotesk": "SpaceGrotesk-Bold.ttf",
    "IBM Plex Mono": "IBMPlexMono-Medium.ttf",
}

_FR_PRIVATE = 0x10
_registered: set[str] | None = None


def font_dir() -> Path:
    """Where the bundled fonts live, in a build or a checkout."""
    inside_build = bundle_dir() / FONT_DIRNAME
    if inside_build.is_dir():
        return inside_build
    return project_root() / "assets" / FONT_DIRNAME


def _register() -> set[str]:
    """Load every bundled font, returning the families now usable."""
    if sys.platform != "win32":
        return set()

    import ctypes

    available: set[str] = set()
    directory = font_dir()
    for family, filename in BUNDLED.items():
        path = directory / filename
        if not path.is_file():
            continue
        with suppress(OSError, AttributeError):
            added = ctypes.windll.gdi32.AddFontResourceExW(str(path), _FR_PRIVATE, 0)
            if added:
                available.add(family)
    return available


def registered() -> set[str]:
    global _registered
    if _registered is None:
        _registered = _register()
    return _registered


def family_or(preferred: str, fallback: str) -> str:
    """``preferred`` if it is really available, else ``fallback``."""
    return preferred if preferred in registered() else fallback
