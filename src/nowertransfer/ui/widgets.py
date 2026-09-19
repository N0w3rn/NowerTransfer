"""Small reusable building blocks shared by the screens."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from .theme import COLORS, PAD_CARD, Accent, font, mono


class Card(ctk.CTkFrame):
    """A panel with the app's standard rounding, optionally outlined."""

    def __init__(self, master: ctk.CTkBaseClass, accent: str | None = None) -> None:
        super().__init__(
            master,
            fg_color=COLORS.panel,
            corner_radius=12,
            border_width=2 if accent else 0,
            border_color=accent or COLORS.panel,
        )

    def row(self, pady: int | tuple[int, int] = (PAD_CARD, 0)) -> ctk.CTkFrame:
        """A transparent strip inside the card for laying widgets side by side."""
        strip = ctk.CTkFrame(self, fg_color="transparent")
        strip.pack(fill="x", padx=PAD_CARD, pady=pady)
        return strip

    def caption(self, text: str) -> ctk.CTkLabel:
        label = ctk.CTkLabel(
            self,
            text=text,
            font=font(11, bold=True),
            text_color=COLORS.muted,
            anchor="w",
        )
        label.pack(anchor="w", padx=PAD_CARD, pady=(PAD_CARD, 0))
        return label

    def hint(self, text: str) -> ctk.CTkLabel:
        label = ctk.CTkLabel(
            self,
            text=text,
            font=font(11),
            text_color=COLORS.muted,
            wraplength=500,
            justify="left",
            anchor="w",
        )
        label.pack(anchor="w", padx=PAD_CARD, pady=(4, PAD_CARD))
        return label


def primary_button(
    master: ctk.CTkBaseClass,
    text: str,
    accent: Accent,
    command: Callable[[], None],
) -> ctk.CTkButton:
    return ctk.CTkButton(
        master,
        text=text,
        height=44,
        font=font(15, bold=True),
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
) -> ctk.CTkButton:
    return ctk.CTkButton(
        master,
        text=text,
        width=width,
        font=font(13),
        fg_color=COLORS.panel_hover,
        hover_color=COLORS.panel_active,
        text_color=COLORS.text,
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
        fg_color="transparent",
        hover_color=COLORS.panel_hover,
        text_color=COLORS.muted,
        font=font(12),
        command=command,
    )


class TransferPanel(ctk.CTkFrame):
    """Progress bar, one-line status and a scrollback of croc's output.

    Both the send and the receive screen show exactly this, which is why it
    lives here rather than being built twice.
    """

    def __init__(
        self, master: ctk.CTkBaseClass, accent: Accent, ready_text: str
    ) -> None:
        super().__init__(master, fg_color="transparent")

        self._progress = ctk.CTkProgressBar(
            self, height=10, progress_color=accent.color, fg_color=COLORS.panel
        )
        self._progress.set(0)
        self._progress.pack(fill="x", pady=(0, 6))

        self._status = ctk.CTkLabel(
            self,
            text=ready_text,
            font=font(12),
            text_color=COLORS.muted,
            wraplength=540,
            justify="left",
            anchor="w",
        )
        self._status.pack(fill="x")

        self._log = ctk.CTkTextbox(
            self,
            height=110,
            fg_color=COLORS.panel,
            text_color=COLORS.muted,
            font=mono(10),
            wrap="none",
        )
        self._log.pack(fill="both", expand=True, pady=(6, 0))
        self._log.configure(state="disabled")
        self._last_logged = ""

    def set_status(self, text: str, *, error: bool = False) -> None:
        self._status.configure(
            text=text, text_color=COLORS.error if error else COLORS.muted
        )

    def log(self, line: str) -> None:
        # croc repeats identical lines while it waits; showing each one
        # would bury everything else.
        if line == self._last_logged:
            return
        self._last_logged = line
        self._log.configure(state="normal")
        self._log.insert("end", line + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def set_progress(self, fraction: float) -> None:
        if self._progress.cget("mode") == "indeterminate":
            self._progress.stop()
            self._progress.configure(mode="determinate")
        self._progress.set(fraction)

    def start_waiting(self) -> None:
        """Indeterminate sweep for the phase before croc reports a percentage."""
        self._progress.configure(mode="indeterminate")
        self._progress.start()

    def stop(self, *, completed: bool) -> None:
        self._progress.stop()
        self._progress.configure(mode="determinate")
        self._progress.set(1.0 if completed else 0.0)
