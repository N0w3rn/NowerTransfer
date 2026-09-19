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

    The copy shipped with the app comes first: it is the one whose
    checksum was verified at build time, and preferring a binary sitting
    next to the .exe would let anyone who can write to that directory
    decide what this app executes. The other locations are the fallback
    for a build that bundles nothing.
    """
    yield bundle_dir() / BINARY_NAME
    yield project_root() / VENDOR_DIRNAME / BINARY_NAME
    yield executable_dir() / BINARY_NAME


def find_croc() -> Path | None:
    """Return the croc binary to use, or ``None`` if there is none."""
    for candidate in candidate_paths():
        if candidate.is_file():
            return candidate
    on_path = shutil.which("croc")
    return Path(on_path) if on_path else None
