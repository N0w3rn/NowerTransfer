"""Shared scaffolding for the screens.

Each screen is a frame that builds itself once and is thrown away when
the user navigates elsewhere, so state lives on the window, not in the
widgets.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import customtkinter as ctk

from ...transfer import EventType, TransferEvent, parse_incoming, parse_progress
from ..theme import COLORS, GAP, NEUTRAL_ACCENT, Accent, display, font
from ..widgets import TransferPanel, icon_button, link_button, primary_button

if TYPE_CHECKING:  # pragma: no cover - import cycle only exists for typing
    from ..main_window import MainWindow


class View(ctk.CTkFrame):
    """Base class for every screen."""

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

    def capture_state(self) -> dict[str, object]:
        """Values to carry across a redraw of this same screen."""
        return {}

    # -- chrome --------------------------------------------------------
    def title_bar(
        self, title: str, glyph: str = "", *, back: bool = True
    ) -> ctk.CTkFrame:
        """The row every screen but the start screen begins with."""
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x")
        if back:
            icon_button(bar, "‹", self.window.show_home).pack(side="left")
        if glyph:
            ctk.CTkLabel(
                bar, text=glyph, font=font(15, bold=True), text_color=COLORS.gold
            ).pack(side="left", padx=(12, 6))
        ctk.CTkLabel(bar, text=title, font=display(19), text_color=COLORS.text).pack(
            side="left", padx=(6 if glyph else 12, 0)
        )
        return bar

    def language_switch(self, parent: ctk.CTkBaseClass) -> ctk.CTkSegmentedButton:
        from ...i18n import LANGUAGES

        switch = ctk.CTkSegmentedButton(
            parent,
            values=[code.upper() for code in LANGUAGES],
            width=86,
            height=26,
            corner_radius=8,
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


class TransferScreen(View):
    """Base for the two screens that can run a transfer."""

    #: Retries before suggesting the code phrase might be the problem.
    _RETRIES_BEFORE_CODE_HINT = 2

    def setup_area(self) -> ctk.CTkFrame:
        """Everything the user fills in before starting.

        Hidden once the transfer runs: the screen then belongs to the
        progress panel, which needs the room.
        """
        self.setup = ctk.CTkFrame(self, fg_color="transparent")
        self.setup.pack(fill="x")
        return self.setup

    def build_action_area(self, start_label: str) -> None:
        """Panel, primary button and the back link, packed bottom-first."""
        self._start_label = start_label
        self._retries = 0
        self._started_at: float | None = None
        self._tick_job: str | None = None

        self.back_button = link_button(self, self.t("nav.back"), self.window.show_home)
        self.back_button.pack(side="bottom", anchor="w", pady=(GAP, 0))

        self.footnote = ctk.CTkLabel(
            self,
            text="",
            font=font(11),
            text_color=COLORS.faint,
            wraplength=600,
            justify="center",
        )
        self.footnote.pack(side="bottom", fill="x", pady=(8, 0))

        self.actions = ctk.CTkFrame(self, fg_color="transparent")
        self.actions.pack(side="bottom", fill="x", pady=(GAP, 0))
        self.action = primary_button(
            self.actions, start_label, self.accent, self._on_action_pressed
        )
        self.action.pack(fill="x")

        self.status = ctk.CTkLabel(
            self,
            text="",
            font=font(12),
            text_color=COLORS.error,
            wraplength=600,
            justify="left",
            anchor="w",
        )
        self.status.pack(side="bottom", fill="x", pady=(GAP, 0))

        self.panel = TransferPanel(
            self,
            self.accent,
            self.t("status.ready"),
            {
                "size": self.t("stat.size"),
                "items": self.t("stat.items"),
                "elapsed": self.t("stat.elapsed"),
                "details": self.t("stat.details"),
            },
        )

    def complain(self, message: str) -> None:
        """Say why the transfer did not start, before the panel exists."""
        self.status.configure(text=message)

    # -- to implement --------------------------------------------------
    def start_transfer(self) -> None:
        raise NotImplementedError

    def on_finished(self) -> None:
        """Hook for cleanup after a successful transfer."""

    def finished_text(self) -> str:
        return self.t("done.title")

    # -- running state -------------------------------------------------
    def _on_action_pressed(self) -> None:
        if self.window.transfer_running:
            self.window.cancel_transfer()
            self.panel.set_phase(self.t("status.cancelling"))
        else:
            self.start_transfer()

    def enter_running(self) -> None:
        self.setup.pack_forget()
        self.status.configure(text="")
        self.panel.pack(fill="x", pady=(18, 0))
        self.action.configure(
            text=self.t("status.cancel"),
            fg_color="transparent",
            border_width=1,
            border_color=COLORS.border,
            hover_color=COLORS.error_hover,
            text_color=COLORS.error,
        )
        self.footnote.configure(text=self.t("status.cancel_safe"))
        self.panel.start_waiting()
        self._started_at = time.monotonic()
        self._tick()

    def leave_running(self, *, completed: bool) -> None:
        self._stop_tick()
        self.panel.stop(completed=completed)
        self.action.configure(
            text=self._start_label,
            fg_color=self.accent.color,
            border_width=0,
            hover_color=self.accent.hover,
            text_color=self.accent.ink,
        )
        self.footnote.configure(text="")

    def _tick(self) -> None:
        if self._started_at is None or not self.winfo_exists():
            return
        seconds = int(time.monotonic() - self._started_at)
        self.panel.set_stat("elapsed", f"{seconds // 60}:{seconds % 60:02d}")
        self._tick_job = self.after(1000, self._tick)

    def _stop_tick(self) -> None:
        if self._tick_job is not None:
            self.after_cancel(self._tick_job)
            self._tick_job = None
        self._started_at = None

    def on_leave(self) -> None:
        self._stop_tick()

    # -- worker events -------------------------------------------------
    def on_transfer_event(self, event: TransferEvent) -> None:
        if event.type is EventType.OUTPUT:
            self._on_output(event.text)
        elif event.type is EventType.RETRY:
            self._retries += 1
            message = self.t("status.retry", seconds=event.seconds)
            # Nothing coming back usually means the two sides are in
            # different rooms, which croc never reports as an error.
            if self._retries >= self._RETRIES_BEFORE_CODE_HINT:
                message = f"{message} {self.t('status.check_code')}"
            self.panel.set_phase(message)
        elif event.type is EventType.FELL_BACK:
            # Opted into, but never silent.
            self.panel.set_phase(self.t("status.fell_back"), error=True)
        elif event.type is EventType.FINISHED:
            self.leave_running(completed=True)
            self.panel.set_phase(self.finished_text())
            self._show_finished()
            self.on_finished()
        elif event.type is EventType.CANCELLED:
            self.leave_running(completed=False)
            self.window.show_home()
        elif event.type is EventType.FAILED:
            self.leave_running(completed=False)
            message = self.t(event.text)
            if event.detail:
                message = f"{message}\n{event.detail}"
            self.panel.set_phase(message, error=True)

    def _show_finished(self) -> None:
        """Replace the primary action with a way out."""
        for child in self.actions.winfo_children():
            child.destroy()
        primary_button(
            self.actions, self.t("done.close"), self.accent, self.window.show_home
        ).pack(fill="x")

    def _on_output(self, line: str) -> None:
        # croc's "bad password" is the *relay* password. A wrong code
        # phrase produces no message at all - it just waits - so it is
        # reported after repeated retries instead, see on_transfer_event.
        progress = parse_progress(line)
        if progress is not None:
            self.panel.set_progress(progress)
            return
        incoming = parse_incoming(line)
        if incoming is not None:
            name, size = incoming
            self.panel.set_phase(name)
            self.panel.set_stat("size", size)
        self.panel.log(line)
