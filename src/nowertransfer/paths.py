"""Filesystem locations the app reads from and writes to.

Everything here has to work twice: once when running from a source checkout
and once inside the single-file PyInstaller build, where the code lives in a
temporary extraction directory that is *not* where the user put the .exe.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from . import APP_NAME


def is_frozen() -> bool:
    """True when running from a PyInstaller build rather than from source."""
    return getattr(sys, "frozen", False)


def bundle_dir() -> Path:
    """Directory holding files that were bundled into the build.

    PyInstaller unpacks one-file builds into ``sys._MEIPASS``. From source
    this is simply the package directory.
    """
    extracted = getattr(sys, "_MEIPASS", None)
    if extracted:
        return Path(extracted)
    return Path(__file__).resolve().parent


def project_root() -> Path:
    """Repository root. Only meaningful in a source checkout."""
    return Path(__file__).resolve().parents[2]


def executable_dir() -> Path:
    """Directory the user actually launched the app from.

    This is where a portable config file or a hand-placed croc binary is
    expected to sit, next to the .exe.
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return project_root()


def user_config_dir() -> Path:
    """Per-user configuration directory, following each platform's habit."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / APP_NAME


def default_download_dir() -> Path:
    """Where received files land unless the user picks somewhere else."""
    downloads = Path.home() / "Downloads"
    return downloads if downloads.is_dir() else Path.home()


def write_atomic(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` without leaving a half-written file behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)
