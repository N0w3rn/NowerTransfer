"""Start screen: pick a role, or finish setup if something is missing."""

from __future__ import annotations

import tkinter
from contextlib import suppress

import customtkinter as ctk

from ... import __version__
from ...config import RelayMode
from ...paths import asset, open_link
from ...session import load_send_session
from ..theme import COLORS, GAP, GOLD_ACCENT, RADIUS, RADIUS_LARGE, display, font, mono
from ..widgets import Card, StatusDot, badge, hint, link_button, primary_button
from .base import View


class HomeView(View):
    def build(self) -> None:
        self._header()

        if self.window.croc_path is None:
            self._blocker(
                self.t("croc.missing.title"), self.t("croc.missing.body"), COLORS.error
            )
        elif not self.window.settings.is_configured:
            self._blocker(self.t("setup.title"), self.t("setup.body"), COLORS.gold)
            primary_button(
                self, self.t("nav.settings"), GOLD_ACCENT, self.window.show_settings
            ).pack(fill="x", pady=(14, 0))
        else:
            self._role_cards()
            self._resume_link()
            self._update_notice()

        self._footer()

    # ------------------------------------------------------------------
    def _header(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x")

        self._logo_image(bar)

        titles = ctk.CTkFrame(bar, fg_color="transparent")
        titles.pack(side="left", fill="x", expand=True, padx=(14, 0))
        ctk.CTkLabel(
            titles, text="NowerTransfer", font=display(25), text_color=COLORS.text
        ).pack(anchor="w")
        ctk.CTkLabel(
            titles, text=self.t("app.tagline"), font=font(12), text_color=COLORS.muted
        ).pack(anchor="w", pady=(2, 0))

        self.language_switch(bar).pack(side="right")

    def _logo_image(self, parent: ctk.CTkBaseClass) -> None:
        """The mark, when it is there. Never a reason to fail.

        A CTkImage rather than a PhotoImage: it is handed a source
        larger than it draws and picks the right pixel size for the
        display, so the logo stays sharp where everything else is
        scaled up too.
        """
        path = asset("logo-88.png")
        if path is None:
            return
        with suppress(tkinter.TclError, OSError):
            from PIL import Image

            source = Image.open(path)
            # Held on the widget: nothing else keeps a reference.
            self._logo = ctk.CTkImage(
                light_image=source, dark_image=source, size=(40, 40)
            )
            ctk.CTkLabel(parent, image=self._logo, text="").pack(side="left")

    def _role_cards(self) -> None:
        # Not expand=True: the row would swallow the spare height and
        # float the cards in the middle of the window. They belong
        # under the header, with the resume strip under them; the
        # spare space goes at the bottom, above the footer.
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", pady=(22, 0))
        row.grid_columnconfigure((0, 1), weight=1, uniform="roles")

        roles = [
            ("upload", "home.send", self.window.show_send, True),
            ("download", "home.receive", self.window.show_receive, False),
        ]
        for column, (icon, key, command, filled) in enumerate(roles):
            title, body = f"{key}.title", f"{key}.body"
            card = ctk.CTkFrame(
                row,
                fg_color=COLORS.panel,
                corner_radius=RADIUS_LARGE,
                border_width=1,
                border_color=COLORS.gold if filled else COLORS.panel_active,
            )
            # "ew", not "nsew": the cards keep their natural height.
            card.grid(
                row=0,
                column=column,
                sticky="ew",
                padx=(0, 9) if column == 0 else (9, 0),
            )

            badge(card, icon, filled=filled).pack(anchor="w", padx=20, pady=(20, 0))
            ctk.CTkLabel(
                card, text=self.t(title), font=display(19), text_color=COLORS.text
            ).pack(anchor="w", padx=20, pady=(14, 0))
            ctk.CTkLabel(
                card,
                text=self.t(body),
                font=font(12),
                text_color=COLORS.muted,
                justify="left",
                anchor="w",
            ).pack(anchor="w", padx=20, pady=(5, 20))

            # tkinter has no button that can hold other widgets, so the
            # whole card is made clickable instead - children included,
            # or the badge and labels would swallow the click.
            self._make_clickable(card, command)

    def _make_clickable(self, widget: ctk.CTkBaseClass, command) -> None:
        widget.bind("<Button-1>", lambda _event: command())
        widget.configure(cursor="hand2")
        for child in widget.winfo_children():
            self._make_clickable(child, command)

    def _update_notice(self) -> None:
        """Say a newer release exists, once the check has found one.

        This is not vanity: croc rejects peers across a major version,
        so when the pinned croc moves, every copy in circulation has
        to be replaced at the same time.
        """
        release = self.window.newer_release
        if release is None:
            return
        strip = ctk.CTkFrame(self, fg_color=COLORS.panel, corner_radius=RADIUS)
        strip.pack(fill="x", pady=(GAP, 0))
        StatusDot(
            strip,
            self.t("update.available", version=release.version),
            COLORS.gold,
        ).pack(side="left", padx=(16, 0), pady=11)
        link_button(
            strip,
            self.t("update.open"),
            lambda: open_link(release.url),
            width=110,
        ).pack(side="right", padx=8)

    def _resume_link(self) -> None:
        session = load_send_session()
        if session is None:
            return
        strip = ctk.CTkFrame(self, fg_color=COLORS.panel, corner_radius=RADIUS)
        strip.pack(fill="x", pady=(GAP, 0))
        ctk.CTkLabel(
            strip,
            text=self.t("home.resume_short"),
            font=font(12),
            text_color=COLORS.muted,
        ).pack(side="left", padx=(16, 10), pady=11)
        ctk.CTkLabel(
            strip, text=session.code, font=mono(12), text_color=COLORS.gold
        ).pack(side="left")
        link_button(
            strip,
            self.t("home.resume_open"),
            lambda: self.window.show_send(resume=session),
            width=90,
        ).pack(side="right", padx=8)

    def _blocker(self, title: str, body: str, accent: str) -> None:
        card = Card(self, accent=accent)
        card.pack(fill="x", pady=(24, 0))
        ctk.CTkLabel(
            card, text=title, font=display(17), text_color=accent, anchor="w"
        ).pack(anchor="w", padx=18, pady=(18, 4))
        hint(card, body, width=520).pack(anchor="w", padx=18, pady=(0, 18))

    def _footer(self) -> None:
        settings = self.window.settings
        strip = ctk.CTkFrame(self, fg_color=COLORS.panel, corner_radius=RADIUS)
        strip.pack(side="bottom", fill="x")

        relay = (
            self.t("relay.public")
            if settings.mode is RelayMode.PUBLIC
            else settings.relay.display_host()
        )
        status = StatusDot(strip, self.t("relay.label"), COLORS.gold)
        status.pack(side="left", padx=(16, 0), pady=11)
        ctk.CTkLabel(strip, text=relay, font=mono(12), text_color=COLORS.text).pack(
            side="left", padx=(10, 0)
        )
        link_button(
            strip, self.t("nav.settings"), self.window.show_settings, width=110
        ).pack(side="right", padx=8)

        version = ctk.CTkFrame(self, fg_color="transparent")
        version.pack(side="bottom", fill="x", pady=(0, 8))
        # "dev" and "unknown" are words, not numbers: no leading v.
        shown = f"v{__version__}" if __version__[:1].isdigit() else __version__
        ctk.CTkLabel(version, text=shown, font=font(10), text_color=COLORS.faint).pack(
            side="left"
        )
