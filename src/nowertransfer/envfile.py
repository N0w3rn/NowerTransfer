"""Minimal ``.env`` reader.

Only the subset a build configuration needs: ``KEY=value`` lines, comments,
optional quotes and an optional ``export`` prefix. Pulling in a dependency
for thirty lines of parsing would cost more than it saves, and the build
script has to read the same file without importing the whole package.
"""

from __future__ import annotations

from pathlib import Path

_QUOTES = ("'", '"')


def parse_env(text: str) -> dict[str, str]:
    """Parse the contents of a ``.env`` file into a mapping."""
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()

        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not key:
            continue
        values[key] = _clean(value.strip())
    return values


def _clean(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in _QUOTES:
        inner = value[1:-1]
        if value[0] == '"':
            # Only the escapes a password plausibly contains.
            return inner.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")
        return inner

    # An unquoted value ends at an inline comment.
    comment = value.find(" #")
    if comment != -1:
        value = value[:comment]
    return value.strip()


def read_env_file(path: Path) -> dict[str, str]:
    """Read a ``.env`` file. A missing or unreadable file is simply empty."""
    try:
        return parse_env(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return {}
