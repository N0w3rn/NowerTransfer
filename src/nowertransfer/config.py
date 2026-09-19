"""Where the relay address and password come from.

Four layers, later ones winning:

1. ``build``       - baked into the binary, or ``.env`` from a checkout
2. ``portable``    - ``nowertransfer.toml`` next to the .exe
3. ``user``        - written by the settings screen
4. ``environment`` - ``NOWERTRANSFER_*`` variables
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path

from .envfile import read_env_file
from .paths import (
    bundle_dir,
    default_download_dir,
    executable_dir,
    is_frozen,
    project_root,
    user_config_dir,
    write_atomic,
)
from .secretstore import protect, unprotect

#: What a relay started without ``--pass`` uses, so an empty password
#: here means "croc's default", not "no password".
CROC_DEFAULT_RELAY_PASSWORD = "pass123"

DEFAULT_RELAY_PORT = 9009

BAKED_CONFIG_NAME = "relay.toml"
PORTABLE_CONFIG_NAME = "nowertransfer.toml"
USER_CONFIG_NAME = "config.toml"
ENV_FILE_NAME = ".env"

ENV_RELAY_HOST = "NOWERTRANSFER_RELAY"
ENV_RELAY_PASSWORD = "NOWERTRANSFER_RELAY_PASSWORD"
ENV_RELAY_MODE = "NOWERTRANSFER_RELAY_MODE"
ENV_LANGUAGE = "NOWERTRANSFER_LANGUAGE"

#: ``.env`` keys and the setting each fills. Short on purpose: this is a
#: checkout's build configuration, not the runtime overrides above.
ENV_FILE_KEYS = {
    "RELAY_HOST": "relay_host",
    "RELAY_PASSWORD": "relay_password",
    "RELAY_MODE": "relay_mode",
}

#: Keys that may appear in a config file, mapped to their env var.
_KEYS: dict[str, str | None] = {
    "relay_host": ENV_RELAY_HOST,
    "relay_password": ENV_RELAY_PASSWORD,
    "relay_mode": ENV_RELAY_MODE,
    "language": ENV_LANGUAGE,
    "download_dir": None,
}


class Source(Enum):
    """Which layer a resolved value came from."""

    DEFAULT = "default"
    BUILD = "build"
    PORTABLE = "portable"
    USER = "user"
    ENVIRONMENT = "environment"


class RelayMode(Enum):
    """Which relay a transfer may use.

    Anything but OWN involves croc's public relay, a third party: file
    contents stay encrypted either way, but who transfers to whom stops
    being private. Hence opt-in.
    """

    OWN = "own"
    FALLBACK = "fallback"
    PUBLIC = "public"

    @classmethod
    def parse(cls, value: str) -> RelayMode:
        """Never raise on a hand-edited config; fall back to the safe mode."""
        try:
            return cls(value.strip().lower())
        except ValueError:
            return cls.OWN


@dataclass(frozen=True)
class RelayEndpoint:
    """The relay croc should talk to."""

    host: str
    password: str = ""

    @property
    def is_set(self) -> bool:
        return bool(self.host)

    def croc_password(self) -> str:
        """Password to hand croc - falls back to croc's own default."""
        return self.password or CROC_DEFAULT_RELAY_PASSWORD

    def display_host(self) -> str:
        return self.host or "-"


@dataclass
class Settings:
    """Everything the app remembers between runs."""

    relay_host: str = ""
    relay_password: str = ""
    relay_mode: str = RelayMode.OWN.value
    language: str = ""
    download_dir: str = ""
    sources: dict[str, Source] = field(default_factory=dict)

    @property
    def relay(self) -> RelayEndpoint:
        """The relay to actually connect to.

        Public mode ignores any stored address - the settings screen only
        keeps it so switching back is easy.
        """
        if self.mode is RelayMode.PUBLIC:
            return RelayEndpoint("")
        return RelayEndpoint(self.relay_host, self.relay_password)

    @property
    def mode(self) -> RelayMode:
        return RelayMode.parse(self.relay_mode)

    @property
    def is_configured(self) -> bool:
        """Whether the app has somewhere to send things."""
        return bool(self.relay_host) or self.mode is RelayMode.PUBLIC

    @property
    def allows_public_fallback(self) -> bool:
        return self.mode is RelayMode.FALLBACK and bool(self.relay_host)

    def source_of(self, key: str) -> Source:
        return self.sources.get(key, Source.DEFAULT)


# ----------------------------------------------------------------------
#  Paths of the individual layers
# ----------------------------------------------------------------------
def baked_config_path() -> Path:
    """The relay file ``scripts/build.py`` wrote into the build."""
    return bundle_dir() / BAKED_CONFIG_NAME


def env_file_path() -> Path:
    """The ``.env`` a source checkout is configured with."""
    return project_root() / ENV_FILE_NAME


def portable_config_path() -> Path:
    return executable_dir() / PORTABLE_CONFIG_NAME


def user_config_path() -> Path:
    return user_config_dir() / USER_CONFIG_NAME


# ----------------------------------------------------------------------
#  Loading
# ----------------------------------------------------------------------
def read_config_file(path: Path) -> dict[str, str]:
    """Read one TOML layer. A missing or broken file is simply empty."""
    try:
        raw = path.read_bytes()
    except OSError:
        return {}
    try:
        parsed = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError):
        return {}
    return {
        key: str(value)
        for key, value in parsed.items()
        if key in _KEYS and isinstance(value, str | int)
    }


def build_layer() -> dict[str, str]:
    """The relay this copy was built with: the baked file, or ``.env``."""
    if is_frozen():
        return read_config_file(baked_config_path())
    return {
        ENV_FILE_KEYS[key]: value
        for key, value in read_env_file(env_file_path()).items()
        if key in ENV_FILE_KEYS and value
    }


def user_layer() -> dict[str, str]:
    """Settings the user saved, with the relay password decrypted.

    A password that will not decrypt here - a config copied from another
    machine - is dropped, so the layer below applies again.
    """
    values = read_config_file(user_config_path())
    stored = values.get("relay_password")
    if stored:
        secret = unprotect(stored)
        if secret:
            values["relay_password"] = secret
        else:
            del values["relay_password"]
    return values


def _environment_layer() -> dict[str, str]:
    layer = {}
    for key, variable in _KEYS.items():
        if variable is None:
            continue
        value = os.environ.get(variable)
        if value:
            layer[key] = value
    return layer


def _layers() -> list[tuple[Source, dict[str, str]]]:
    """All layers in increasing order of precedence."""
    return [
        (Source.BUILD, build_layer()),
        (Source.PORTABLE, read_config_file(portable_config_path())),
        (Source.USER, user_layer()),
        (Source.ENVIRONMENT, _environment_layer()),
    ]


def load_settings() -> Settings:
    """Merge every layer into the settings the app runs with."""
    values: dict[str, str] = {}
    sources: dict[str, Source] = {}
    for source, layer in _layers():
        for key, value in layer.items():
            if not value:
                continue
            values[key] = value
            sources[key] = source

    return _with_defaults(Settings(sources=sources, **values))


def inherited_settings() -> Settings:
    """Settings as they would be *without* the user layer.

    Saving compares against these, so neither a baked-in password nor a
    computed default is written to disk as though the user chose it.
    """
    values: dict[str, str] = {}
    for source, layer in _layers():
        if source is Source.USER:
            continue
        values.update({k: v for k, v in layer.items() if v})
    return _with_defaults(Settings(**values))


def _with_defaults(settings: Settings) -> Settings:
    if not settings.download_dir:
        settings.download_dir = str(default_download_dir())
    return settings


# ----------------------------------------------------------------------
#  Saving
# ----------------------------------------------------------------------
def save_settings(settings: Settings) -> Path:
    """Persist the user layer and return the file it was written to."""
    inherited = inherited_settings()
    payload = {
        key: getattr(settings, key)
        for key in _KEYS
        if getattr(settings, key) and getattr(settings, key) != getattr(inherited, key)
    }
    if "relay_password" in payload:
        payload["relay_password"] = protect(payload["relay_password"])

    path = user_config_path()
    write_atomic(path, dump_toml(payload), private=True)
    return path


def dump_toml(values: Mapping[str, str]) -> str:
    """Serialise a flat string mapping as TOML.

    The stdlib reads TOML but cannot write it, and this is four string
    keys - not worth a dependency.
    """
    header = (
        "# NowerTransfer settings. Written by the app.\n"
        "# relay_password is encrypted for this user account; the rest is\n"
        "# plain and safe to edit.\n"
    )
    body = "".join(f"{key} = {_toml_string(value)}\n" for key, value in values.items())
    return header + body


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    escaped = "".join(
        char if char >= " " and char != "\x7f" else f"\\u{ord(char):04x}"
        for char in escaped
    )
    return f'"{escaped}"'


# ----------------------------------------------------------------------
#  Input helpers
# ----------------------------------------------------------------------
def normalise_relay_host(host: str) -> str:
    """Accept what people actually type and return ``host:port``.

    ``relay.example.com`` -> ``relay.example.com:9009``
    ``https://relay.example.com/`` -> ``relay.example.com:9009``
    ``[::1]:9009`` is left alone.
    """
    host = host.strip()
    if not host:
        return ""
    for prefix in ("https://", "http://", "tcp://"):
        if host.lower().startswith(prefix):
            host = host[len(prefix) :]
    host = host.strip("/")
    if not host:
        return ""

    # Bracketed IPv6 literal: only append a port if there is none.
    if host.startswith("["):
        closing = host.find("]")
        if closing != -1 and ":" not in host[closing + 1 :]:
            return f"{host}:{DEFAULT_RELAY_PORT}"
        return host

    # A bare IPv6 address has several colons and needs brackets.
    if host.count(":") > 1:
        return f"[{host}]:{DEFAULT_RELAY_PORT}"

    if ":" not in host:
        return f"{host}:{DEFAULT_RELAY_PORT}"
    return host


def with_relay(settings: Settings, host: str, password: str) -> Settings:
    """Return a copy of ``settings`` with a cleaned-up relay endpoint."""
    return replace(
        settings,
        relay_host=normalise_relay_host(host),
        relay_password=password.strip(),
    )
