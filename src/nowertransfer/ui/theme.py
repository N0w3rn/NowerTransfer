"""Colours, fonts and spacing.

The palette is the logo's: gold on a near-black indigo. Both key colours
are sampled from the mark itself rather than approximated, so the app and
the icon in the taskbar look like the same product.

Gold is the only accent. An earlier version used green for sending and
blue for receiving, which a two-colour brand has no room for, so the two
directions are told apart by the arrow on their cards instead.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    # Sampled from the logo: #07021A is its darkest body colour, #F8C715
    # its gold. The rest of the scale is built up from those two.
    background: str = "#0A0518"
    panel: str = "#150F2B"
    panel_hover: str = "#201938"
    panel_active: str = "#2C2448"
    text: str = "#F3EFFA"
    muted: str = "#9086A8"
    gold: str = "#F8C715"
    gold_hover: str = "#D8AA0B"
    gold_soft: str = "#F5D560"
    ink: str = "#0A0518"
    error: str = "#FF6B5A"
    error_hover: str = "#3A1F2A"


COLORS = Palette()


@dataclass(frozen=True)
class Accent:
    """A colour and the two shades that go with it."""

    color: str
    hover: str
    #: Colour for text drawn *on* ``color``.
    ink: str


GOLD_ACCENT = Accent(COLORS.gold, COLORS.gold_hover, COLORS.ink)
NEUTRAL_ACCENT = Accent(COLORS.muted, COLORS.panel_hover, COLORS.text)

#: Both directions share the brand accent; see the module docstring.
SEND_ACCENT = GOLD_ACCENT
RECEIVE_ACCENT = GOLD_ACCENT


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
