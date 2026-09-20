"""Start screen: pick a role, or finish setup if something is missing."""

from __future__ import annotations

import tkinter
from contextlib import suppress
from functools import partial

import customtkinter as ctk

from ... import __version__
from ...config import RelayMode
from ...paths import asset, open_link
from ...session import ReceiveSession, Unfinished, unfinished
from ..theme import COLORS, GAP, GOLD_ACCENT, RADIUS, RADIUS_LARGE, display, font, mono
from ..widgets import Card, StatusDot, badge, hint, link_button, primary_button
from .base import View

#: How many unfinished transfers fit before the list starts scrolling.
RESUME_WITHOUT_SCROLLING = 3

#: Roughly one row including its gap, used to size the scrolling box.
RESUME_ROW_HEIGHT = 52


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

        # Outside the branches on purpose. A newer version is worth
        # knowing about whether or not this copy can currently
        # transfer anything - when croc is missing or the relay is
        # unset, an update is if anything the likelier fix.
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
        #: The card canvases, in Tab order.
        self._focus_stops: list[ctk.CTkCanvas] = []
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
            border = COLORS.gold if filled else COLORS.panel_active
            card = ctk.CTkFrame(
                row,
                fg_color=COLORS.panel,
                corner_radius=RADIUS_LARGE,
                border_width=1,
                border_color=border,
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
            self._make_reachable(card, command, resting=border)

    def _make_clickable(self, widget: ctk.CTkBaseClass, command) -> None:
        widget.bind("<Button-1>", lambda _event: command())
        widget.configure(cursor="hand2")
        for child in widget.winfo_children():
            self._make_clickable(child, command)

    def _make_reachable(self, card: ctk.CTkFrame, command, *, resting: str) -> None:
        """Let the card be reached with Tab and pressed with Enter.

        A frame is not a focus stop, so before this the app could not
        be driven from the keyboard at all: Tab reached only the
        settings link in the footer, and neither role card could be
        opened without a mouse. The canvas CustomTkinter draws the
        card on can take focus, which is the piece that was missing.

        That canvas is reached through ``_canvas`` because
        CustomTkinter keeps it out of ``winfo_children`` - checked,
        the frame reports only the widgets we put in it. Guarded, so
        a future version that renames it costs the keyboard route
        rather than the screen.
        """
        canvas = getattr(card, "_canvas", None)
        if canvas is None:  # pragma: no cover - present in CustomTkinter 6
            return

        canvas.configure(takefocus=True)
        # Windows reports the numpad's Enter as Return too, so the two
        # keys here are the whole set.
        for key in ("<Return>", "<space>"):
            canvas.bind(key, lambda _event: command())
        # Focus has to be visible or being able to reach it is no use.
        canvas.bind(
            "<FocusIn>",
            lambda _event: card.configure(border_color=COLORS.gold, border_width=2),
        )
        canvas.bind(
            "<FocusOut>",
            lambda _event: card.configure(border_color=resting, border_width=1),
        )
        self._focus_stops.append(canvas)

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
        """Offer every transfer that was left unfinished.

        Either direction, and as many as there are: croc carries on
        from what is already on disk, so nothing here has to be
        abandoned because something else was started after it. One
        leaves the list when it finishes, or when what it refers to
        has gone.

        Past a handful they go in a scrolling box rather than pushing
        the rest of the screen off the bottom.
        """
        transfers = unfinished()
        if not transfers:
            return

        if len(transfers) <= RESUME_WITHOUT_SCROLLING:
            holder = ctk.CTkFrame(self, fg_color="transparent")
            holder.pack(fill="x", pady=(GAP, 0))
        else:
            holder = ctk.CTkScrollableFrame(
                self,
                fg_color="transparent",
                height=RESUME_ROW_HEIGHT * RESUME_WITHOUT_SCROLLING,
                scrollbar_button_color=COLORS.panel_active,
                scrollbar_button_hover_color=COLORS.border,
            )
            holder.pack(fill="x", pady=(GAP, 0))

        for transfer in transfers:
            self._resume_row(holder, transfer)

    def _resume_row(self, parent: ctk.CTkBaseClass, transfer: Unfinished) -> None:
        receiving = isinstance(transfer, ReceiveSession)
        reopen = (
            partial(self.window.show_receive, resume=transfer)
            if receiving
            else partial(self.window.show_send, resume=transfer)
        )

        card = ctk.CTkFrame(parent, fg_color=COLORS.panel, corner_radius=RADIUS)
        card.pack(fill="x", pady=(0, 6))

        strip = ctk.CTkFrame(card, fg_color="transparent")
        strip.pack(fill="x")
        ctk.CTkLabel(
            strip,
            text=self.t(
                "home.resume_receiving" if receiving else "home.resume_sending"
            ),
            font=font(12),
            text_color=COLORS.muted,
        ).pack(side="left", padx=(16, 10), pady=11)
        ctk.CTkLabel(
            strip, text=transfer.code, font=mono(12), text_color=COLORS.gold
        ).pack(side="left")
        link_button(strip, self.t("home.resume_open"), reopen, width=90).pack(
            side="right", padx=8
        )

        if receiving:
            # croc pre-allocates the destination at its full size, so
            # a half-received file is the same number of bytes as a
            # whole one and looks finished in Explorer. Nothing on
            # disk can say otherwise - renaming it would stop croc
            # resuming - so it has to be said here.
            hint(
                card,
                self.t("home.resume_incomplete", folder=transfer.target),
                width=600,
            ).pack(anchor="w", fill="x", padx=16, pady=(0, 11))

    def show_relay_state(self) -> None:
        """Colour the dot for what the relay is currently known to do.

        The dot used to be gold whatever the relay was doing, which
        reads as "all well" even when nothing is listening. Faint
        while the check runs, gold when the address answered, red when
        it did not.

        Public mode is its own case rather than a fourth shade of
        "unknown". Nothing is checked there and nothing can be: croc
        carries the public address itself, so there is no address of
        ours to reach. Left as the bare faint dot it read as a fault -
        measured against the real relay, which does answer - so it
        says what it is instead.

        Changed in place rather than by redrawing the screen: a
        rebuild throws away the widgets, and with them the keyboard
        focus the user may be holding.
        """
        if self.window.settings.mode is RelayMode.PUBLIC:
            self._relay_dot.set(self.t("relay.public_unchecked"), COLORS.muted)
            return
        label, colour = {
            None: (self.t("relay.label"), COLORS.faint),
            True: (self.t("relay.label"), COLORS.gold),
            False: (self.t("relay.unreachable"), COLORS.error),
        }[self.window.relay_reachable]
        self._relay_dot.set(label, colour)

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

        self._relay_dot = StatusDot(strip, "", COLORS.faint)
        self._relay_dot.pack(side="left", padx=(16, 0), pady=11)
        self.show_relay_state()
        # Only an address of our own gets a line of its own, in the
        # face machine text uses. Public mode has no address to show -
        # croc holds it - so the dot says the whole thing and a second
        # label would only repeat it.
        if settings.mode is not RelayMode.PUBLIC:
            ctk.CTkLabel(
                strip,
                text=settings.relay.display_host(),
                font=mono(12),
                text_color=COLORS.text,
            ).pack(side="left", padx=(10, 0))
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
