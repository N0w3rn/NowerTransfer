"""Colours, fonts and spacing.

One idea carries the whole design: the accent colour encodes the direction
of the transfer. Green means data leaving this machine, blue means data
arriving. Every screen inherits its accent from the role it serves, so the
user can tell send from receive without reading a word.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    background: str = "#0F1419"
    panel: str = "#1A222B"
    panel_hover: str = "#232E39"
    panel_active: str = "#2C3945"
    text: str = "#E9EEF3"
    muted: str = "#8595A5"
    send: str = "#2EBD85"
    send_hover: str = "#249668"
    send_ink: str = "#06281B"
    receive: str = "#4D9DE0"
    receive_hover: str = "#3B7FB8"
    receive_ink: str = "#0A1D2E"
    error: str = "#E0604D"
    error_hover: str = "#3A2A28"


COLORS = Palette()


@dataclass(frozen=True)
class Accent:
    """The colour set belonging to one role."""

    color: str
    hover: str
    ink: str


SEND_ACCENT = Accent(COLORS.send, COLORS.send_hover, COLORS.send_ink)
RECEIVE_ACCENT = Accent(COLORS.receive, COLORS.receive_hover, COLORS.receive_ink)
NEUTRAL_ACCENT = Accent(COLORS.muted, COLORS.panel_hover, COLORS.text)


def _family(windows: str, macos: str, other: str) -> str:
    if sys.platform == "win32":
        return windows
    if sys.platform == "darwin":
        return macos
    return other


UI_FONT = _family("Segoe UI", "SF Pro Text", "DejaVu Sans")
MONO_FONT = _family("Consolas", "Menlo", "DejaVu Sans Mono")


def font(size: int, *, bold: bool = False) -> tuple[str, int, str] | tuple[str, int]:
    return (UI_FONT, size, "bold") if bold else (UI_FONT, size)


def mono(size: int, *, bold: bool = False) -> tuple[str, int, str] | tuple[str, int]:
    return (MONO_FONT, size, "bold") if bold else (MONO_FONT, size)


# Consistent spacing so screens line up with each other.
PAD_WINDOW = 24
PAD_CARD = 14
GAP = 12
