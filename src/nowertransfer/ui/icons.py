"""Icons drawn as strokes rather than typed as characters.

A glyph like "▲" is whatever the font happens to have: a flat filled
triangle, a different weight in every face, and no say over thickness
or proportion. These are drawn on a canvas instead, from coordinates on
a 24-unit grid, so they scale to any size and to any display without
going soft, and take the colour they are given.
"""

from __future__ import annotations

from contextlib import suppress

import customtkinter as ctk

#: Every icon is drawn on this grid and scaled from it.
GRID = 24.0

#: Stroke weight on that grid; scaled with everything else.
STROKE = 2.2

#: name -> the polylines that make it up, as (x, y) pairs on the grid.
SHAPES: dict[str, tuple[tuple[tuple[float, float], ...], ...]] = {
    # An arrow leaving a surface: sending.
    "upload": (
        ((12, 16.5), (12, 4.5)),
        ((6.8, 9.7), (12, 4.5), (17.2, 9.7)),
        ((4.5, 19.5), (19.5, 19.5)),
    ),
    # The same arrow turned around: receiving.
    "download": (
        ((12, 4.5), (12, 16.5)),
        ((6.8, 11.3), (12, 16.5), (17.2, 11.3)),
        ((4.5, 19.5), (19.5, 19.5)),
    ),
    # Back.
    "chevron_left": (((14.5, 5), (8.5, 12), (14.5, 19)),),
    # An arrow falling into an open tray: the drop zone.
    "drop": (
        ((12, 2.5), (12, 13.5)),
        ((7, 8.5), (12, 13.5), (17, 8.5)),
        ((4, 14.5), (4, 20.5), (20, 20.5), (20, 14.5)),
    ),
}


def _scaling(widget: ctk.CTkBaseClass) -> float:
    """The display scaling CustomTkinter is applying, if it will say."""
    with suppress(AttributeError, KeyError, TypeError, ValueError):
        return float(ctk.ScalingTracker.get_widget_scaling(widget))
    return 1.0


class Icon(ctk.CTkCanvas):
    """One stroked icon, sized in logical pixels.

    A canvas cannot be transparent, so ``background`` has to be the
    colour of whatever it sits on.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        name: str,
        *,
        size: int = 22,
        color: str,
        background: str,
        width: float = STROKE,
    ) -> None:
        scale = _scaling(master)
        pixels = round(size * scale)
        super().__init__(
            master,
            width=pixels,
            height=pixels,
            highlightthickness=0,
            borderwidth=0,
            background=background,
        )
        self._name = name
        self._color = color
        self._width = width
        self._scale = pixels / GRID
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        for points in SHAPES[self._name]:
            flat = [value * self._scale for point in points for value in point]
            self.create_line(
                *flat,
                fill=self._color,
                width=max(1.0, self._width * self._scale),
                capstyle="round",
                joinstyle="round",
            )

    def recolour(self, color: str, background: str | None = None) -> None:
        self._color = color
        if background is not None:
            self.configure(background=background)
        self._draw()
