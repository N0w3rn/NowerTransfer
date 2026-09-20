#!/usr/bin/env python3
"""Build the single-file NowerTransfer executable.

The relay address and password are *baked into the build*, never into this
repository. Configure your relay once and the resulting binary is the whole
product: the person you hand it to double-clicks it and sends a file, with
nothing to configure.

Every build states the version it identifies itself as:

    poe build 1.0.0

Relay settings normally come from ``.env`` in the repository root (copy
``.env.example``). They can also be given on the command line or through
the environment:

    poe build 1.0.0 --relay relay.example.com --relay-password hunter2

Building without any of them produces a binary that asks the user for the
relay on first start - which is what a public release should do. A
tagged release gets its version from the tag and needs no argument.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
VENDOR_DIR = PROJECT_ROOT / "vendor"
DIST_DIR = PROJECT_ROOT / "dist"
WORK_DIR = PROJECT_ROOT / "build"
ASSETS_DIR = PROJECT_ROOT / "assets"
ICON_PATH = ASSETS_DIR / "icon.ico"
ENV_FILE = PROJECT_ROOT / ".env"

APP_NAME = "NowerTransfer"

sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fetch_croc import binary_name
from fetch_croc import main as fetch_croc_main
from nowertransfer import VERSION, VERSION_STAMP
from nowertransfer.config import dump_toml, normalise_relay_host
from nowertransfer.envfile import read_env_file


def resolve_relay(args: argparse.Namespace) -> dict[str, str]:
    """Relay settings to bake in, in decreasing order of precedence."""
    from_file = read_env_file(ENV_FILE)
    host = (
        args.relay
        or os.environ.get("NOWERTRANSFER_RELAY")
        or from_file.get("RELAY_HOST", "")
    )
    password = (
        args.relay_password
        if args.relay_password is not None
        else os.environ.get("NOWERTRANSFER_RELAY_PASSWORD")
        or from_file.get("RELAY_PASSWORD", "")
    )

    baked = {}
    if host:
        baked["relay_host"] = normalise_relay_host(host)
    if password:
        baked["relay_password"] = password
    return baked


#: MAJOR.MINOR.PATCH, optionally marked: 1.0.0, 1.0.0-rc1, 1.0.0+test.
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z][0-9A-Za-z.\-+]*)?$")

VERSION_HELP = (
    "Give the version this build should identify itself as:\n"
    "    poe build 1.0.0\n"
    "\n"
    "Format: MAJOR.MINOR.PATCH, optionally marked, e.g. 1.0.0, 1.2.3,\n"
    "1.0.0-rc1, 1.0.0-test. A leading v is accepted and dropped.\n"
    "\n"
    f"The current source version is {VERSION} (see VERSION in\n"
    "src/nowertransfer/__init__.py). Tagged releases take the version\n"
    "from the tag automatically and need no argument."
)


def resolve_app_version(explicit: str | None) -> str:
    """The version to stamp in. Mandatory - there is no guessing.

    A release is the one case that fills this in by itself: GitHub
    Actions puts the tag in GITHUB_REF_NAME, so pushing `v1.2.0` builds
    `1.2.0`. Every other build has to say what it is, because a binary
    that quietly invents a number is one nobody can support.
    """
    candidate = explicit
    if not candidate:
        ref = os.environ.get("GITHUB_REF_NAME", "")
        if ref[:1] in "vV" and ref[1:2].isdigit():
            candidate = ref

    if not candidate:
        raise SystemExit(f"error: no version given.\n\n{VERSION_HELP}")

    candidate = candidate.lstrip("vV")
    if not VERSION_PATTERN.match(candidate):
        raise SystemExit(f"error: {candidate!r} is not a version.\n\n{VERSION_HELP}")
    return candidate


def ensure_croc(tag: str | None, skip: bool) -> Path:
    binary = VENDOR_DIR / binary_name()
    if binary.exists():
        return binary
    if skip:
        raise SystemExit(
            f"error: {binary} is missing and --no-fetch was given.\n"
            f"Run: python scripts/fetch_croc.py"
        )
    argv = ["--dest", str(VENDOR_DIR)]
    if tag:
        argv += ["--tag", tag]
    if fetch_croc_main(argv) != 0:
        raise SystemExit("error: could not obtain the croc binary")
    return binary


PUBLISHER = "Nowenr"

#: Windows file metadata. Without it the .exe has no publisher, no
#: product name and no version in its properties, which is both worse
#: to look at and one more reason for a virus scanner's heuristics to
#: distrust an unsigned binary that unpacks itself.
VERSION_RESOURCE = """\
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={numbers},
    prodvers={numbers},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0),
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', '{publisher}'),
        StringStruct('FileDescription', '{name} - send files through your own relay'),
        StringStruct('FileVersion', '{version}'),
        StringStruct('InternalName', '{name}'),
        StringStruct('LegalCopyright', 'MIT licence. croc by schollz, also MIT.'),
        StringStruct('OriginalFilename', '{name}.exe'),
        StringStruct('ProductName', '{name}'),
        StringStruct('ProductVersion', '{version}'),
      ]),
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])]),
  ],
)
"""


def numeric_version(version: str) -> tuple[int, int, int, int]:
    """Four numbers, which is all the Windows metadata field accepts.

    ``1.2.3-rc1`` becomes ``(1, 2, 3, 0)``; the label survives in the
    version strings beside it, which is what anyone actually reads.
    """
    numbers = [int(part) for part in re.findall(r"\d+", version.split("-")[0])[:4]]
    numbers += [0] * (4 - len(numbers))
    return tuple(numbers)  # type: ignore[return-value]


def version_resource(version: str) -> str:
    return VERSION_RESOURCE.format(
        numbers=numeric_version(version),
        version=version,
        name=APP_NAME,
        publisher=PUBLISHER,
    )


def pyinstaller_command(
    croc: Path,
    relay_file: Path | None,
    version_file: Path | None = None,
    resource_file: Path | None = None,
) -> list[str]:
    separator = os.pathsep
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--clean",
        "--name",
        APP_NAME,
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(WORK_DIR),
        "--specpath",
        str(WORK_DIR),
        "--paths",
        str(SRC_DIR),
        "--collect-all",
        "customtkinter",
        # tkdnd is a Tcl extension living beside the Python package;
        # without collecting the data files it is simply not there.
        "--collect-all",
        "tkinterdnd2",
        "--add-binary",
        f"{croc}{separator}.",
    ]
    if relay_file is not None:
        command += ["--add-data", f"{relay_file}{separator}."]
    if version_file is not None:
        command += ["--add-data", f"{version_file}{separator}."]
    if resource_file is not None:
        command += ["--version-file", str(resource_file)]
    if ICON_PATH.exists():
        # --icon sets the .exe's own icon; the running window loads the
        # bundled copy itself, so it has to be packed in as well.
        command += ["--icon", str(ICON_PATH)]

    # Everything the UI loads at runtime: the window icon and the logo
    # the start screen draws.
    for name in ("icon.ico", "logo-88.png"):
        asset = ASSETS_DIR / name
        if asset.exists():
            command += ["--add-data", f"{asset}{separator}."]

    # The brand faces, into the subdirectory ui/fonts.py looks in. The
    # licences travel with them: the OFL requires it.
    fonts = ASSETS_DIR / "fonts"
    if fonts.is_dir():
        command += ["--add-data", f"{fonts}{separator}fonts"]
    command.append(str(PROJECT_ROOT / "scripts" / "entrypoint.py"))
    return command


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the NowerTransfer executable.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--relay", help="relay address, e.g. relay.example.com:9009")
    parser.add_argument(
        "--relay-password",
        help="relay password (omit to use croc's default)",
    )
    parser.add_argument(
        "version",
        nargs="?",
        help="version this build identifies itself as, e.g. 1.0.0 "
        "(omit only in the release workflow, which takes the git tag)",
    )
    parser.add_argument("--croc-tag", help="pin a croc release, e.g. v11.5.3")
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="fail instead of downloading croc",
    )
    args = parser.parse_args(argv)

    # First: no point downloading croc for a build that gets rejected.
    version = resolve_app_version(args.version)

    if shutil.which("pyinstaller") is None:
        try:
            import PyInstaller  # noqa: F401
        except ImportError:
            raise SystemExit(
                "error: PyInstaller is not installed.\n"
                "Run: python -m pip install -e .[dev]"
            ) from None

    croc = ensure_croc(args.croc_tag, args.no_fetch)
    baked = resolve_relay(args)

    with tempfile.TemporaryDirectory() as staging:
        relay_file: Path | None = None
        if baked:
            relay_file = Path(staging) / "relay.toml"
            relay_file.write_text(dump_toml(baked), encoding="utf-8")
            print(f"baking in relay: {baked['relay_host']}")
            if "relay_password" not in baked:
                print("  (no relay password - croc's default will be used)")
        else:
            print(
                "no relay configured - the build will ask the user on "
                "first start (see --help)"
            )

        version_file = Path(staging) / VERSION_STAMP
        version_file.write_text(version, encoding="utf-8")
        print(f"version: {version}")

        # Only on Windows: nothing else has a version resource, and
        # PyInstaller rejects --version-file there.
        resource_file: Path | None = None
        if os.name == "nt":
            resource_file = Path(staging) / "version_info.txt"
            resource_file.write_text(version_resource(version), encoding="utf-8")
            print(f"file metadata: {PUBLISHER}, {numeric_version(version)}")

        command = pyinstaller_command(croc, relay_file, version_file, resource_file)
        print("running:", " ".join(command))
        result = subprocess.run(command, cwd=PROJECT_ROOT, check=False)

    if result.returncode != 0:
        return result.returncode

    suffix = ".exe" if os.name == "nt" else ""
    print(f"\nBuilt: {DIST_DIR / (APP_NAME + suffix)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
