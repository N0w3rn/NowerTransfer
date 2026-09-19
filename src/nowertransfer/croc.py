"""Locating the croc binary that does the actual work."""

from __future__ import annotations

import os
import shutil
from collections.abc import Iterator
from pathlib import Path

from .paths import bundle_dir, executable_dir, project_root

BINARY_NAME = "croc.exe" if os.name == "nt" else "croc"

#: Where ``scripts/fetch_croc.py`` puts the downloaded binary.
VENDOR_DIRNAME = "vendor"


def candidate_paths() -> Iterator[Path]:
    """Every place we look for croc, in order of preference.

    Next to the .exe first so a user can drop in their own build, then the
    copy bundled into the one-file build, then the source checkout's
    ``vendor/`` directory, and finally whatever is on ``PATH``.
    """
    yield executable_dir() / BINARY_NAME
    yield bundle_dir() / BINARY_NAME
    yield project_root() / VENDOR_DIRNAME / BINARY_NAME


def find_croc() -> Path | None:
    """Return the croc binary to use, or ``None`` if there is none."""
    for candidate in candidate_paths():
        if candidate.is_file():
            return candidate
    on_path = shutil.which("croc")
    return Path(on_path) if on_path else None
