#!/usr/bin/env python3
"""Build the Windows installer.

Wraps the executable from ``scripts/build.py`` in an Inno Setup
installer that puts NowerTransfer in the start menu, registers an
uninstaller, and needs no administrator rights.

    poe installer 1.0.0

Arguments other than the version are passed straight through to the
build, so this works the same way:

    poe installer 1.0.0 --relay relay.example.com --relay-password hunter2

Use --skip-build to package an executable that is already in dist/.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
DIST_DIR = PROJECT_ROOT / "dist"
SCRIPT = PROJECT_ROOT / "installer" / "NowerTransfer.iss"

sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build

#: Where Inno Setup ends up, depending on how it was installed. winget
#: puts it under the user's profile, the normal installer under
#: Program Files.
_ISCC_CANDIDATES = (
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
    Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Inno Setup 6" / "ISCC.exe",
    Path(os.environ.get("PROGRAMFILES", "")) / "Inno Setup 6" / "ISCC.exe",
)

ISCC_MISSING = """\
error: Inno Setup was not found.

Install it and run this again:
    winget install --id JRSoftware.InnoSetup

Or set ISCC to the full path of ISCC.exe."""


def find_iscc() -> Path | None:
    """Locate the Inno Setup compiler."""
    override = os.environ.get("ISCC")
    if override:
        candidate = Path(override)
        return candidate if candidate.is_file() else None

    on_path = shutil.which("ISCC")
    if on_path:
        return Path(on_path)

    for candidate in _ISCC_CANDIDATES:
        if candidate.parent.parent.name and candidate.is_file():
            return candidate
    return None


def numeric_version(version: str) -> str:
    """Four numbers for the file metadata, which accepts nothing else.

    ``1.2.3-rc1`` becomes ``1.2.3.0``; the label survives in AppVersion,
    which is what the user sees.
    """
    numbers = re.findall(r"\d+", version.split("+")[0].split("-")[0])[:4]
    while len(numbers) < 4:
        numbers.append("0")
    return ".".join(numbers)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the NowerTransfer installer.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "version", nargs="?", help="version this build identifies itself as"
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="package the executable already in dist/ instead of rebuilding",
    )
    args, passthrough = parser.parse_known_args(argv)

    # Rejects a missing or malformed version before anything is built.
    version = build.resolve_app_version(args.version)

    if sys.platform != "win32":
        raise SystemExit("error: the installer can only be built on Windows.")

    iscc = find_iscc()
    if iscc is None:
        raise SystemExit(ISCC_MISSING)

    executable = DIST_DIR / "NowerTransfer.exe"
    if args.skip_build:
        if not executable.is_file():
            raise SystemExit(f"error: {executable} does not exist; drop --skip-build.")
    else:
        exit_code = build.main([version, *passthrough])
        if exit_code != 0:
            return exit_code

    command = [
        str(iscc),
        f"/DAppVersion={version}",
        f"/DNumericVersion={numeric_version(version)}",
        f"/DSourceExe={executable}",
        f"/DOutputDir={DIST_DIR}",
        str(SCRIPT),
    ]
    print(f"\npackaging with {iscc.name}: {version}")
    result = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    if result.returncode != 0:
        return result.returncode

    setup = DIST_DIR / f"NowerTransfer-{version}-setup.exe"
    print(f"\nBuilt: {setup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
