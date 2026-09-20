"""Colours, fonts and spacing.

Gold on near-black indigo, both sampled from the logo. Gold is the only
accent, so send and receive are told apart by the arrow on their cards
rather than by colour.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    # #07021A and #F8C715 are the logo's; the rest is built from them.
    background: str = "#0A0518"
    #: Recessed: input fields and the drop zone, darker than the ground.
    well: str = "#120C24"
    panel: str = "#150F2B"
    panel_hover: str = "#201938"
    panel_active: str = "#2C2448"
    border: str = "#3A3059"
    text: str = "#F3EFFA"
    muted: str = "#9086A8"
    #: Captions and hints. Dimmer than muted, so only for short labels.
    faint: str = "#5C5473"
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

SEND_ACCENT = GOLD_ACCENT
RECEIVE_ACCENT = GOLD_ACCENT


def _family(windows: str, macos: str, other: str) -> str:
    if sys.platform == "win32":
        return windows
    if sys.platform == "darwin":
        return macos
    return other


#: Bundled with the app; fonts.py registers them and falls back to these
#: if it cannot, so a missing font never leaves the UI unreadable.
DISPLAY_FONT = "Space Grotesk"
MONO_BRAND_FONT = "IBM Plex Mono"

UI_FONT = _family("Segoe UI", "SF Pro Text", "DejaVu Sans")
MONO_FONT = _family("Consolas", "Menlo", "DejaVu Sans Mono")


def font(size: int, *, bold: bool = False) -> tuple[str, int, str] | tuple[str, int]:
    return (UI_FONT, size, "bold") if bold else (UI_FONT, size)


def display(size: int, *, bold: bool = True) -> tuple[str, int, str] | tuple[str, int]:
    """Headings and the big numbers."""
    from .fonts import family_or

    name = family_or(DISPLAY_FONT, UI_FONT)
    return (name, size, "bold") if bold else (name, size)


def mono(size: int, *, bold: bool = False) -> tuple[str, int, str] | tuple[str, int]:
    from .fonts import family_or

    name = family_or(MONO_BRAND_FONT, MONO_FONT)
    return (name, size, "bold") if bold else (name, size)


# Consistent spacing so screens line up with each other.
PAD_WINDOW = 30
PAD_CARD = 18
GAP = 12
RADIUS = 13
RADIUS_LARGE = 16
