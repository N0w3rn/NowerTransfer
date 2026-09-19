"""Start screen: pick a role, or finish setup if something is missing."""

from __future__ import annotations

import customtkinter as ctk

from ... import __version__
from ...config import RelayMode
from ...session import load_send_session
from ..theme import COLORS, GOLD_ACCENT, font
from ..widgets import Card, link_button, primary_button
from .base import View


class HomeView(View):
    def build(self) -> None:
        self.header(self.t("app.tagline"), with_language=True)

        if self.window.croc_path is None:
            self._blocker(
                self.t("croc.missing.title"), self.t("croc.missing.body"), COLORS.error
            )
        elif not self.window.settings.is_configured:
            self._blocker(self.t("setup.title"), self.t("setup.body"), COLORS.gold)
            primary_button(
                self,
                self.t("nav.settings"),
                GOLD_ACCENT,
                self.window.show_settings,
            ).pack(fill="x", pady=(14, 0))
        else:
            self._role_cards()
            self._resume_link()

        self._footer()

    # ------------------------------------------------------------------
    def _role_cards(self) -> None:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="both", expand=True, pady=6)
        row.grid_columnconfigure((0, 1), weight=1, uniform="roles")
        row.grid_rowconfigure(0, weight=1)

        # The arrow carries the direction. The palette is one accent, so
        # it cannot do that job the way two colours used to.
        roles: list[tuple[str, str, str, object]] = [
            ("▲", "home.send.title", "home.send.body", self.window.show_send),
            ("▼", "home.receive.title", "home.receive.body", self.window.show_receive),
        ]
        for column, (arrow, title, body, command) in enumerate(roles):
            ctk.CTkButton(
                row,
                text=f"{arrow}\n\n{self.t(title)}\n\n{self.t(body)}",
                font=font(16, bold=True),
                fg_color=COLORS.panel,
                hover_color=COLORS.panel_hover,
                text_color=GOLD_ACCENT.color,
                corner_radius=14,
                border_width=2,
                border_color=GOLD_ACCENT.color,
                command=command,
            ).grid(
                row=0,
                column=column,
                sticky="nsew",
                padx=(0, 8) if column == 0 else (8, 0),
                pady=4,
            )

    def _resume_link(self) -> None:
        session = load_send_session()
        if session is None:
            return
        link_button(
            self,
            self.t("home.resume", code=session.code),
            lambda: self.window.show_send(resume=session),
            width=320,
        ).pack(pady=(10, 0))

    def _blocker(self, title: str, body: str, accent: str) -> None:
        card = Card(self, accent=accent)
        card.pack(fill="x", pady=10)
        ctk.CTkLabel(
            card,
            text=title,
            font=font(15, bold=True),
            text_color=accent,
            anchor="w",
        ).pack(anchor="w", padx=16, pady=(16, 4))
        ctk.CTkLabel(
            card,
            text=body,
            font=font(12),
            text_color=COLORS.muted,
            wraplength=500,
            justify="left",
            anchor="w",
        ).pack(anchor="w", padx=16, pady=(0, 16))

    def _footer(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(side="bottom", fill="x", pady=(10, 0))
        link_button(bar, self.t("nav.settings"), self.window.show_settings).pack(
            side="left"
        )
        settings = self.window.settings
        relay = (
            self.t("relay.public")
            if settings.mode is RelayMode.PUBLIC
            else settings.relay.display_host()
        )
        ctk.CTkLabel(
            bar,
            text=self.t("app.footer", version=__version__, relay=relay),
            font=font(10),
            text_color=COLORS.muted,
        ).pack(side="right", pady=6)
