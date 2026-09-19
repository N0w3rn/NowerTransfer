#!/usr/bin/env python3
"""Download the croc binary for this platform into ``vendor/``.

croc is not committed to this repository: a 16 MB binary does not belong in
git history, and vendoring one means shipping whatever version happened to
be current when someone cloned. Instead it is fetched from the official
GitHub releases and checked against the SHA-256 the release publishes.

    python scripts/fetch_croc.py                # latest release
    python scripts/fetch_croc.py --tag v10.2.2  # pin a version
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import stat
import sys
import tarfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

REPO = "schollz/croc"
API = f"https://api.github.com/repos/{REPO}/releases"
USER_AGENT = "NowerTransfer-build-script"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_DIR = PROJECT_ROOT / "vendor"

#: Tokens that identify the right release asset, per platform.
_OS_TOKENS = {"win32": ("windows",), "darwin": ("macos", "darwin"), "linux": ("linux",)}
_ARM_TOKENS = ("arm64", "aarch64")
_X86_TOKENS = ("64bit", "amd64", "x86_64")


class FetchError(RuntimeError):
    pass


# ----------------------------------------------------------------------
def binary_name() -> str:
    return "croc.exe" if os.name == "nt" else "croc"


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
    except urllib.error.URLError as error:
        raise FetchError(f"could not download {url}: {error}") from error


def release_metadata(tag: str | None) -> dict:
    url = f"{API}/tags/{tag}" if tag else f"{API}/latest"
    return json.loads(_get(url))


def _is_arm() -> bool:
    import platform

    return platform.machine().lower() in {"arm64", "aarch64"}


def select_asset(assets: list[dict]) -> dict:
    """Pick the archive matching the current OS and CPU architecture."""
    os_tokens = _OS_TOKENS.get(sys.platform)
    if os_tokens is None:
        raise FetchError(f"unsupported platform: {sys.platform}")
    want_arm = _is_arm()

    for asset in assets:
        name = asset["name"].lower()
        if not name.endswith((".zip", ".tar.gz")):
            continue
        if not any(token in name for token in os_tokens):
            continue
        has_arm = any(token in name for token in _ARM_TOKENS)
        if want_arm and has_arm:
            return asset
        if not want_arm and not has_arm and any(t in name for t in _X86_TOKENS):
            return asset

    raise FetchError(
        f"no croc release asset found for {sys.platform} "
        f"({'arm64' if want_arm else 'x86_64'})"
    )


def expected_digest(assets: list[dict], filename: str) -> str:
    """Look up ``filename`` in the release's checksums file."""
    checksums = next(
        (a for a in assets if "checksum" in a["name"].lower()),
        None,
    )
    if checksums is None:
        raise FetchError("release publishes no checksums file - refusing to continue")

    for line in _get(checksums["browser_download_url"]).decode().splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*") == filename:
            return parts[0].lower()
    raise FetchError(f"{filename} is not listed in the checksums file")


def extract_binary(archive: bytes, filename: str) -> bytes:
    """Pull just the croc executable out of the downloaded archive.

    Members are read individually rather than unpacked to disk, which
    sidesteps path-traversal entries in a malicious archive.
    """
    wanted = binary_name()
    if filename.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            for member in bundle.namelist():
                if Path(member).name == wanted:
                    return bundle.read(member)
    else:
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
            for member in bundle.getmembers():
                if member.isfile() and Path(member.name).name == wanted:
                    handle = bundle.extractfile(member)
                    if handle is not None:
                        return handle.read()
    raise FetchError(f"{wanted} not found inside {filename}")


def fetch(tag: str | None = None, dest_dir: Path = VENDOR_DIR) -> Path:
    release = release_metadata(tag)
    assets = release.get("assets", [])
    asset = select_asset(assets)
    name = asset["name"]

    print(f"croc {release.get('tag_name', '?')}: downloading {name}")
    archive = _get(asset["browser_download_url"])

    digest = hashlib.sha256(archive).hexdigest()
    expected = expected_digest(assets, name)
    if digest != expected:
        raise FetchError(f"checksum mismatch for {name}: {digest} != {expected}")
    print(f"  sha256 ok ({digest[:16]}…)")

    binary = extract_binary(archive, name)
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / binary_name()
    target.write_bytes(binary)
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"  -> {target}")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", help="release tag to pin, e.g. v10.2.2")
    parser.add_argument(
        "--dest", type=Path, default=VENDOR_DIR, help="where to put the binary"
    )
    parser.add_argument(
        "--force", action="store_true", help="download even if a copy exists"
    )
    args = parser.parse_args(argv)

    target = args.dest / binary_name()
    if target.exists() and not args.force:
        print(f"croc already present at {target} (use --force to refresh)")
        return 0

    try:
        fetch(args.tag, args.dest)
    except FetchError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
