"""Shared scaffolding for the screens.

Each screen is a frame that builds itself once and is thrown away when the
user navigates elsewhere. That keeps state out of the widgets: the window
owns the data, the view only renders it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from ... import APP_NAME
from ...transfer import EventType, TransferEvent, parse_progress
from ..theme import COLORS, NEUTRAL_ACCENT, Accent, font
from ..widgets import TransferPanel, link_button, primary_button

if TYPE_CHECKING:  # pragma: no cover - import cycle only exists for typing
    from ..main_window import MainWindow


class View(ctk.CTkFrame):
    """Base class for every screen."""

    #: Colour set this screen is drawn in.
    accent: Accent = NEUTRAL_ACCENT

    def __init__(self, window: MainWindow, **options: object) -> None:
        super().__init__(window.content, fg_color=COLORS.background)
        self.window = window
        self.t = window.t
        #: Extra arguments the window passed when navigating here.
        self.options = options
        self.build()

    # -- to implement --------------------------------------------------
    def build(self) -> None:
        raise NotImplementedError

    def on_transfer_event(self, event: TransferEvent) -> None:
        """Handle a message from the worker. Screens without one ignore it."""

    def on_leave(self) -> None:
        """Called before the screen is destroyed."""

    # -- helpers -------------------------------------------------------
    def header(self, subtitle: str, *, with_language: bool = False) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x")
        bar.grid_columnconfigure(0, weight=1)

        titles = ctk.CTkFrame(bar, fg_color="transparent")
        titles.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            titles, text=APP_NAME, font=font(26, bold=True), text_color=COLORS.text
        ).pack(anchor="w")
        ctk.CTkLabel(
            titles, text=subtitle, font=font(13), text_color=self.accent.color
        ).pack(anchor="w")

        if with_language:
            self._language_switch(bar).grid(row=0, column=1, sticky="ne")

        ctk.CTkFrame(self, fg_color="transparent", height=14).pack(fill="x")

    def _language_switch(self, parent: ctk.CTkBaseClass) -> ctk.CTkSegmentedButton:
        from ...i18n import LANGUAGES

        codes = list(LANGUAGES)
        labels = [code.upper() for code in codes]
        switch = ctk.CTkSegmentedButton(
            parent,
            values=labels,
            width=90,
            height=26,
            font=font(11, bold=True),
            fg_color=COLORS.panel,
            selected_color=COLORS.panel_active,
            selected_hover_color=COLORS.panel_active,
            unselected_color=COLORS.panel,
            unselected_hover_color=COLORS.panel_hover,
            text_color=COLORS.text,
            command=lambda label: self.window.set_language(label.lower()),
        )
        switch.set(self.t.language.upper())
        return switch

    def back_button(self) -> None:
        link_button(self, self.t("nav.back"), self.window.show_home, width=90).pack(
            anchor="w", pady=(10, 0)
        )


class TransferScreen(View):
    """Base for the two screens that can run a transfer.

    Send and receive differ only in what they collect from the user before
    starting croc; everything after the start button is identical.
    """

    def build_action_area(self, start_label: str) -> None:
        self._start_label = start_label
        self.action = primary_button(
            self, start_label, self.accent, self._on_action_pressed
        )
        self.action.pack(fill="x", pady=(0, 10))
        self.panel = TransferPanel(self, self.accent, self.t("status.ready"))
        self.panel.pack(fill="both", expand=True)

    # -- to implement --------------------------------------------------
    def start_transfer(self) -> None:
        """Validate input and ask the window to launch croc."""
        raise NotImplementedError

    def on_finished(self) -> None:
        """Hook for cleanup after a successful transfer."""

    # -- running state -------------------------------------------------
    def _on_action_pressed(self) -> None:
        if self.window.transfer_running:
            self.window.cancel_transfer()
            self.panel.set_status(self.t("status.cancelling"))
        else:
            self.start_transfer()

    def enter_running(self) -> None:
        self.action.configure(
            text=self.t("status.cancel"),
            fg_color=COLORS.panel_hover,
            hover_color=COLORS.error_hover,
            text_color=COLORS.error,
        )
        self.panel.start_waiting()

    def leave_running(self, *, completed: bool) -> None:
        self.panel.stop(completed=completed)
        self.action.configure(
            text=self._start_label,
            fg_color=self.accent.color,
            hover_color=self.accent.hover,
            text_color=self.accent.ink,
        )

    # -- worker events -------------------------------------------------
    def on_transfer_event(self, event: TransferEvent) -> None:
        if event.type is EventType.OUTPUT:
            self._on_output(event.text)
        elif event.type is EventType.RETRY:
            self.panel.set_status(self.t("status.retry", seconds=event.seconds))
        elif event.type is EventType.FINISHED:
            self.leave_running(completed=True)
            self.action.configure(
                text=self.t("status.finished_button"),
                state="disabled",
                fg_color=COLORS.panel,
                text_color=self.accent.color,
            )
            self.panel.set_status(self.t("status.finished"))
            self.on_finished()
        elif event.type is EventType.CANCELLED:
            self.leave_running(completed=False)
            self.window.show_home()
        elif event.type is EventType.FAILED:
            self.leave_running(completed=False)
            message = self.t(event.text)
            if event.detail:
                message = f"{message}\n{event.detail}"
            self.panel.set_status(message, error=True)

    def _on_output(self, line: str) -> None:
        progress = parse_progress(line)
        if progress is not None:
            self.panel.set_progress(progress)
            self.panel.set_status(line)
            return
        self.panel.log(line)
        lowered = line.lower()
        if "wrong password" in lowered or "bad password" in lowered:
            self.panel.set_status(self.t("status.wrong_code"), error=True)
