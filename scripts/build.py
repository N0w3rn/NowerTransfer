#!/usr/bin/env python3
"""Build the single-file NowerTransfer executable.

The relay address and password are *baked into the build*, never into this
repository. Configure your relay once and the resulting binary is the whole
product: the person you hand it to double-clicks it and sends a file, with
nothing to configure.

Normally the values come from ``.env`` in the repository root (copy
``.env.example``), so a plain ``poe build`` is enough. They can also be
given on the command line or through the environment:

    poe build --relay relay.example.com --relay-password hunter2

Building without any of them produces a binary that asks the user for the
relay on first start - which is what a public release should do.
"""

from __future__ import annotations

import argparse
import os
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
ICON_PATH = PROJECT_ROOT / "assets" / "icon.ico"
ENV_FILE = PROJECT_ROOT / ".env"

APP_NAME = "NowerTransfer"

sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fetch_croc import binary_name
from fetch_croc import main as fetch_croc_main
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


def pyinstaller_command(croc: Path, relay_file: Path | None) -> list[str]:
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
        "--add-binary",
        f"{croc}{separator}.",
    ]
    if relay_file is not None:
        command += ["--add-data", f"{relay_file}{separator}."]
    if ICON_PATH.exists():
        command += ["--icon", str(ICON_PATH)]
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
    parser.add_argument("--croc-tag", help="pin a croc release, e.g. v10.2.2")
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="fail instead of downloading croc",
    )
    args = parser.parse_args(argv)

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

        command = pyinstaller_command(croc, relay_file)
        print("running:", " ".join(command))
        result = subprocess.run(command, cwd=PROJECT_ROOT, check=False)

    if result.returncode != 0:
        return result.returncode

    suffix = ".exe" if os.name == "nt" else ""
    print(f"\nBuilt: {DIST_DIR / (APP_NAME + suffix)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
