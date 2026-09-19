"""Settings screen: relay endpoint and language.

Every field shows where its current value comes from, so it is obvious
whether the app is running on a baked-in relay, a file next to the .exe or
something the user typed here.
"""

from __future__ import annotations

import customtkinter as ctk

from ...config import save_settings, with_relay
from ...i18n import LANGUAGES
from ..theme import COLORS, NEUTRAL_ACCENT, PAD_CARD, RECEIVE_ACCENT, font
from ..widgets import Card, primary_button
from .base import View


class SettingsView(View):
    accent = NEUTRAL_ACCENT

    def build(self) -> None:
        self.header(self.t("settings.title"))
        if not self.window.settings.is_configured:
            self._intro()
        self._relay_card()
        self._language_card()

        primary_button(self, self.t("settings.save"), RECEIVE_ACCENT, self._save).pack(
            fill="x", pady=(4, 8)
        )
        self._message = ctk.CTkLabel(
            self,
            text=str(self.options.get("message", "")),
            font=font(12),
            text_color=COLORS.muted,
            wraplength=540,
            justify="left",
            anchor="w",
        )
        self._message.pack(fill="x")
        self.back_button()

    # ------------------------------------------------------------------
    def _intro(self) -> None:
        ctk.CTkLabel(
            self,
            text=self.t("setup.body"),
            font=font(12),
            text_color=COLORS.muted,
            wraplength=540,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(0, 10))

    def _relay_card(self) -> None:
        settings = self.window.settings

        card = Card(self)
        card.pack(fill="x")
        card.caption(self.t("settings.relay_host"))
        self._host_entry = ctk.CTkEntry(
            card,
            font=font(14),
            height=38,
            fg_color=COLORS.background,
            border_color=COLORS.panel_hover,
            text_color=COLORS.text,
            placeholder_text=self.t("settings.relay_host_placeholder"),
        )
        self._host_entry.insert(0, settings.relay_host)
        self._host_entry.pack(fill="x", padx=PAD_CARD, pady=(4, 0))
        card.hint(
            f"{self.t('settings.relay_host_hint')}  ({self._source_text('relay_host')})"
        )

        password_card = Card(self)
        password_card.pack(fill="x", pady=12)
        password_card.caption(self.t("settings.relay_password"))
        row = password_card.row(pady=(4, 0))
        self._password_entry = ctk.CTkEntry(
            row,
            font=font(14),
            height=38,
            fg_color=COLORS.background,
            border_color=COLORS.panel_hover,
            text_color=COLORS.text,
            placeholder_text=self.t("settings.relay_password_placeholder"),
            show="•",
        )
        self._password_entry.insert(0, settings.relay_password)
        self._password_entry.pack(side="left", fill="x", expand=True)

        self._reveal = ctk.CTkCheckBox(
            row,
            text=self.t("settings.show_password"),
            font=font(11),
            text_color=COLORS.muted,
            width=90,
            checkbox_width=18,
            checkbox_height=18,
            fg_color=COLORS.receive,
            hover_color=COLORS.receive_hover,
            command=self._toggle_password,
        )
        self._reveal.pack(side="left", padx=(10, 0))
        password_card.hint(
            f"{self.t('settings.relay_password_hint')}  "
            f"({self._source_text('relay_password')})"
        )

    def _language_card(self) -> None:
        card = Card(self)
        card.pack(fill="x", pady=(0, 12))
        card.caption(self.t("settings.language"))
        row = card.row(pady=(4, PAD_CARD))
        self._language = ctk.CTkSegmentedButton(
            row,
            values=list(LANGUAGES.values()),
            height=32,
            font=font(12),
            fg_color=COLORS.background,
            selected_color=COLORS.panel_active,
            selected_hover_color=COLORS.panel_active,
            unselected_color=COLORS.panel,
            unselected_hover_color=COLORS.panel_hover,
            text_color=COLORS.text,
        )
        self._language.set(LANGUAGES[self.t.language])
        self._language.pack(side="left")

    def _source_text(self, key: str) -> str:
        source = self.window.settings.source_of(key)
        return self.t("settings.source", source=self.t(f"source.{source.value}"))

    def _toggle_password(self) -> None:
        self._password_entry.configure(show="" if self._reveal.get() else "•")

    # ------------------------------------------------------------------
    def _save(self) -> None:
        host = self._host_entry.get().strip()
        if not host:
            self._message.configure(
                text=self.t("settings.invalid_host"), text_color=COLORS.error
            )
            return

        chosen = self._language.get()
        language = next(
            (code for code, name in LANGUAGES.items() if name == chosen),
            self.t.language,
        )

        updated = with_relay(self.window.settings, host, self._password_entry.get())
        updated.language = language
        path = save_settings(updated)

        # Re-read from disk so the screen redraws with the real resolved
        # values and their (possibly changed) sources.
        self.window.reload_settings()
        self.window.show_settings(message=self.t("settings.saved", path=path))
