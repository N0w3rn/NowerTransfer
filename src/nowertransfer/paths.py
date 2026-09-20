"""Filesystem locations the app reads from and writes to.

Everything here has to work twice: once when running from a source checkout
and once inside the single-file PyInstaller build, where the code lives in a
temporary extraction directory that is *not* where the user put the .exe.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path

from . import APP_NAME
from .ownership import restrict_to_owner


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


def icon_path() -> Path | None:
    """The window icon, bundled into a build or read from ``assets/``."""
    return asset("icon.ico")


def asset(name: str) -> Path | None:
    """A file shipped with the app, from the bundle or from ``assets/``."""
    for candidate in (bundle_dir() / name, project_root() / "assets" / name):
        if candidate.is_file():
            return candidate
    return None


def default_download_dir() -> Path:
    """Where received files land unless the user picks somewhere else."""
    downloads = Path.home() / "Downloads"
    return downloads if downloads.is_dir() else Path.home()


def total_size(paths: Iterable[Path]) -> int:
    """Bytes in these files and folders. Unreadable entries count as 0."""
    total = 0
    for path in paths:
        if path.is_dir():
            for child in path.rglob("*"):
                with suppress(OSError):
                    if child.is_file():
                        total += child.stat().st_size
        else:
            with suppress(OSError):
                total += path.stat().st_size
    return total


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "kB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            precision = 0 if unit == "B" or value >= 100 else 1
            return f"{value:.{precision}f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def open_in_file_manager(path: Path) -> None:
    """Show a folder in the system's file manager."""
    with suppress(OSError):
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)


def write_atomic(path: Path, text: str, *, private: bool = False) -> None:
    """Write ``text`` to ``path`` without leaving a half-written file behind.

    With ``private``, the directory and the file are restricted to the
    current account before anything is written - see
    :mod:`~nowertransfer.ownership`, which does the work Windows needs.
    The contents of the secrets themselves are encrypted on top of that
    (see :mod:`~nowertransfer.secretstore`).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    if private:
        # The directory first, because the temporary file is created
        # inside it and inherits from it on Windows. The file is then
        # restricted in its own right: that is what carries the mode on
        # Linux and macOS, and on Windows it still holds if the
        # directory could not be changed.
        restrict_to_owner(path.parent)
        temporary.touch(exist_ok=True)
        restrict_to_owner(temporary)
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)
