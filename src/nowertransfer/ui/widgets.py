"""Small reusable building blocks shared by the screens."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from .icons import Icon
from .theme import (
    COLORS,
    PAD_CARD,
    RADIUS,
    RADIUS_LARGE,
    Accent,
    display,
    font,
    mono,
)


class Card(ctk.CTkFrame):
    """A panel with the app's standard rounding, optionally outlined."""

    def __init__(self, master: ctk.CTkBaseClass, accent: str | None = None) -> None:
        super().__init__(
            master,
            fg_color=COLORS.panel,
            corner_radius=RADIUS_LARGE,
            border_width=1 if accent else 0,
            border_color=accent or COLORS.panel,
        )

    def row(self, pady: int | tuple[int, int] = (PAD_CARD, 0)) -> ctk.CTkFrame:
        strip = ctk.CTkFrame(self, fg_color="transparent")
        strip.pack(fill="x", padx=PAD_CARD, pady=pady)
        return strip


def caption(master: ctk.CTkBaseClass, text: str) -> ctk.CTkLabel:
    """The small upper-case label above a field or group."""
    return ctk.CTkLabel(
        master,
        text=text.upper(),
        font=font(10, bold=True),
        text_color=COLORS.muted,
        anchor="w",
    )


def hint(master: ctk.CTkBaseClass, text: str, width: int = 520) -> ctk.CTkLabel:
    return ctk.CTkLabel(
        master,
        text=text,
        font=font(11),
        text_color=COLORS.faint,
        wraplength=width,
        justify="left",
        anchor="w",
    )


def heading(master: ctk.CTkBaseClass, text: str, size: int = 19) -> ctk.CTkLabel:
    return ctk.CTkLabel(
        master, text=text, font=display(size), text_color=COLORS.text, anchor="w"
    )


def primary_button(
    master: ctk.CTkBaseClass,
    text: str,
    accent: Accent,
    command: Callable[[], None],
    height: int = 46,
) -> ctk.CTkButton:
    return ctk.CTkButton(
        master,
        text=text,
        height=height,
        corner_radius=RADIUS,
        font=display(15),
        fg_color=accent.color,
        hover_color=accent.hover,
        text_color=accent.ink,
        command=command,
    )


def quiet_button(
    master: ctk.CTkBaseClass,
    text: str,
    command: Callable[[], None],
    width: int = 140,
    height: int = 34,
) -> ctk.CTkButton:
    return ctk.CTkButton(
        master,
        text=text,
        width=width,
        height=height,
        corner_radius=9,
        font=font(12),
        fg_color=COLORS.panel_hover,
        hover_color=COLORS.panel_active,
        text_color=COLORS.text,
        command=command,
    )


def outline_button(
    master: ctk.CTkBaseClass,
    text: str,
    command: Callable[[], None],
    width: int = 150,
    height: int = 34,
    color: str | None = None,
) -> ctk.CTkButton:
    return ctk.CTkButton(
        master,
        text=text,
        width=width,
        height=height,
        corner_radius=9,
        font=font(12, bold=True),
        fg_color="transparent",
        hover_color=COLORS.panel_hover,
        border_width=1,
        border_color=COLORS.border,
        text_color=color or COLORS.text,
        command=command,
    )


def link_button(
    master: ctk.CTkBaseClass,
    text: str,
    command: Callable[[], None],
    width: int = 110,
) -> ctk.CTkButton:
    return ctk.CTkButton(
        master,
        text=text,
        width=width,
        height=28,
        corner_radius=8,
        fg_color="transparent",
        hover_color=COLORS.panel_hover,
        text_color=COLORS.muted,
        font=font(12),
        command=command,
    )


class IconButton(ctk.CTkFrame):
    """A small square button whose face is a drawn icon.

    Not a CTkButton: that can only show text or a raster image, and
    these icons are strokes on a canvas so they stay sharp at any
    display scaling.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        name: str,
        command: Callable[[], None],
        *,
        size: int = 30,
        icon_size: int = 18,
    ) -> None:
        super().__init__(
            master,
            width=size,
            height=size,
            corner_radius=9,
            fg_color=COLORS.panel,
        )
        # Without this the frame shrinks to the canvas and loses its
        # hit area.
        self.pack_propagate(False)
        self._icon = Icon(
            self,
            name,
            size=icon_size,
            color=COLORS.muted,
            background=COLORS.panel,
        )
        self._icon.pack(expand=True)

        for widget in (self, self._icon):
            widget.bind("<Button-1>", lambda _event: command())
            widget.bind("<Enter>", lambda _event: self._hover(True))
            widget.bind("<Leave>", lambda _event: self._hover(False))
            widget.configure(cursor="hand2")

    def _hover(self, active: bool) -> None:
        background = COLORS.panel_hover if active else COLORS.panel
        self.configure(fg_color=background)
        self._icon.recolour(COLORS.text if active else COLORS.muted, background)


def badge(
    master: ctk.CTkBaseClass,
    name: str,
    *,
    filled: bool,
    size: int = 42,
) -> ctk.CTkFrame:
    """The rounded square holding a role's icon on the start screen."""
    background = COLORS.gold if filled else COLORS.panel_hover
    holder = ctk.CTkFrame(
        master, width=size, height=size, corner_radius=12, fg_color=background
    )
    holder.pack_propagate(False)
    Icon(
        holder,
        name,
        size=size - 18,
        color=COLORS.ink if filled else COLORS.gold,
        background=background,
        width=2.4,
    ).pack(expand=True)
    return holder


def entry(
    master: ctk.CTkBaseClass,
    *,
    placeholder: str = "",
    accent: bool = False,
    show: str = "",
    big: bool = False,
) -> ctk.CTkEntry:
    return ctk.CTkEntry(
        master,
        font=mono(17, bold=True) if big else font(13),
        height=50 if big else 40,
        corner_radius=RADIUS,
        fg_color=COLORS.well,
        border_width=1,
        border_color=COLORS.gold if accent else COLORS.panel_active,
        text_color=COLORS.gold if big else COLORS.text,
        placeholder_text=placeholder,
        placeholder_text_color=COLORS.faint,
        show=show,
    )


class StatusDot(ctk.CTkFrame):
    """A coloured dot plus a line of text, used for relay and job state."""

    def __init__(
        self, master: ctk.CTkBaseClass, text: str = "", color: str | None = None
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._dot = ctk.CTkFrame(
            self, width=9, height=9, corner_radius=5, fg_color=color or COLORS.faint
        )
        self._dot.pack(side="left", pady=(1, 0))
        self._dot.pack_propagate(False)
        self._label = ctk.CTkLabel(
            self, text=text, font=font(12), text_color=COLORS.muted, anchor="w"
        )
        self._label.pack(side="left", padx=(9, 0))

    def set(self, text: str, color: str) -> None:
        self._dot.configure(fg_color=color)
        self._label.configure(text=text, text_color=COLORS.muted)


class Collapsible(ctk.CTkFrame):
    """A disclosure toggle with a body that starts hidden."""

    def __init__(self, master: ctk.CTkBaseClass, label: str) -> None:
        super().__init__(master, fg_color="transparent")
        self._label = label
        self._open = False
        self._toggle = ctk.CTkButton(
            self,
            text=f"⌄  {label}",
            anchor="w",
            width=180,
            height=26,
            corner_radius=8,
            fg_color="transparent",
            hover_color=COLORS.panel_hover,
            text_color=COLORS.muted,
            font=font(12),
            command=self.toggle,
        )
        self._toggle.pack(anchor="w")
        self.body = ctk.CTkFrame(self, fg_color="transparent")

    def toggle(self) -> None:
        self._open = not self._open
        self._toggle.configure(text=f"{'⌃' if self._open else '⌄'}  {self._label}")
        if self._open:
            self.body.pack(fill="both", expand=True, pady=(8, 0))
        else:
            self.body.pack_forget()


class Stat(ctk.CTkFrame):
    """One labelled figure in the transfer screen's row of three."""

    def __init__(self, master: ctk.CTkBaseClass, label: str, value: str = "—") -> None:
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(
            self,
            text=label.upper(),
            font=font(10, bold=True),
            text_color=COLORS.faint,
            anchor="w",
        ).pack(fill="x")
        self._value = ctk.CTkLabel(
            self, text=value, font=mono(14), text_color=COLORS.text, anchor="w"
        )
        self._value.pack(fill="x", pady=(4, 0))

    def set(self, value: str) -> None:
        self._value.configure(text=value)


class TransferPanel(ctk.CTkFrame):
    """Phase, progress and figures for a running transfer.

    Only what is actually known is shown. croc reports no percentage
    through a pipe, so the bar sweeps while a phase is in progress and
    fills only when croc does report one; there is no invented speed or
    estimated time.
    """

    def __init__(
        self, master: ctk.CTkBaseClass, accent: Accent, ready_text: str, labels: dict
    ) -> None:
        super().__init__(master, fg_color=COLORS.panel, corner_radius=RADIUS_LARGE)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=22, pady=(20, 0))
        self._phase = ctk.CTkLabel(
            head,
            text=ready_text,
            font=display(17),
            text_color=COLORS.text,
            anchor="w",
            justify="left",
            wraplength=430,
        )
        self._phase.pack(side="left", fill="x", expand=True)
        self._percent = ctk.CTkLabel(
            head, text="", font=display(30), text_color=accent.color
        )
        self._percent.pack(side="right")

        self._bar = ctk.CTkProgressBar(
            self,
            height=9,
            corner_radius=5,
            progress_color=accent.color,
            fg_color=COLORS.panel_hover,
        )
        self._bar.set(0)
        self._bar.pack(fill="x", padx=22, pady=(14, 0))

        figures = ctk.CTkFrame(self, fg_color="transparent")
        figures.pack(fill="x", padx=22, pady=(18, 0))
        figures.grid_columnconfigure((0, 1, 2), weight=1, uniform="stats")
        self.stats = {
            key: Stat(figures, label)
            for key, label in (
                ("size", labels["size"]),
                ("items", labels["items"]),
                ("elapsed", labels["elapsed"]),
            )
        }
        for column, stat in enumerate(self.stats.values()):
            stat.grid(row=0, column=column, sticky="ew")

        self._details = Collapsible(self, labels["details"])
        self._details.pack(fill="x", padx=22, pady=(16, 0))
        self._log = ctk.CTkTextbox(
            self._details.body,
            height=96,
            fg_color=COLORS.well,
            text_color=COLORS.muted,
            font=mono(10),
            corner_radius=10,
            wrap="none",
        )
        self._log.pack(fill="both", expand=True)
        self._log.configure(state="disabled")
        self._last_logged = ""

        ctk.CTkFrame(self, fg_color="transparent", height=6).pack()

    # -- phase and progress --------------------------------------------
    def set_phase(self, text: str, *, error: bool = False) -> None:
        self._phase.configure(
            text=text, text_color=COLORS.error if error else COLORS.text
        )

    def set_progress(self, fraction: float) -> None:
        if self._bar.cget("mode") == "indeterminate":
            self._bar.stop()
            self._bar.configure(mode="determinate")
        self._bar.set(fraction)
        self._percent.configure(text=f"{round(fraction * 100)}%")

    def start_waiting(self) -> None:
        self._percent.configure(text="")
        self._bar.configure(mode="indeterminate")
        self._bar.start()

    def stop(self, *, completed: bool) -> None:
        self._bar.stop()
        self._bar.configure(mode="determinate")
        self._bar.set(1.0 if completed else 0.0)
        self._percent.configure(text="100%" if completed else "")

    # -- figures and log -----------------------------------------------
    def set_stat(self, key: str, value: str) -> None:
        self.stats[key].set(value)

    def log(self, line: str) -> None:
        # croc repeats identical lines while it waits.
        if line == self._last_logged:
            return
        self._last_logged = line
        self._log.configure(state="normal")
        self._log.insert("end", line + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")
