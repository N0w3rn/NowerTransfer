"""Settings screen: the relay this app talks to.

Every field shows which layer its value came from. Language is not here
but in the header, where someone who opened the app in the wrong
language will actually find it.
"""

from __future__ import annotations

import customtkinter as ctk

from ...config import RelayMode, save_settings, with_relay
from ..theme import COLORS, GAP, GOLD_ACCENT, NEUTRAL_ACCENT, PAD_CARD, font
from ..widgets import Card, primary_button
from .base import View


class SettingsView(View):
    accent = NEUTRAL_ACCENT

    def build(self) -> None:
        self.header(self.t("settings.title"), with_language=True)

        #: Switched as a group by _sync_relay_fields, so a field added
        #: later needs one call rather than its own special case.
        self._own_relay_only: list[ctk.CTkBaseClass] = []

        # Packed against the bottom first: packed last, pack() squeezes
        # them to nothing when the screen outgrows the window.
        self.back_button(side="bottom")
        self._message = ctk.CTkLabel(
            self,
            text=str(self.options.get("message", "")),
            font=font(12),
            text_color=COLORS.muted,
            wraplength=540,
            justify="left",
            anchor="w",
        )
        self._message.pack(side="bottom", fill="x", pady=(6, 0))
        primary_button(self, self.t("settings.save"), GOLD_ACCENT, self._save).pack(
            side="bottom", fill="x", pady=(8, 0)
        )

        # Scrolls: three cards already exceed the minimum window height.
        self._body = ctk.CTkScrollableFrame(
            self, fg_color="transparent", scrollbar_button_color=COLORS.panel_active
        )
        self._body.pack(fill="both", expand=True)

        if not self.window.settings.is_configured:
            self._intro()
        self._mode_card()
        self._relay_card()
        self._sync_relay_fields()

    # ------------------------------------------------------------------
    def _intro(self) -> None:
        ctk.CTkLabel(
            self._body,
            text=self.t("setup.body"),
            font=font(12),
            text_color=COLORS.muted,
            wraplength=540,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(0, 10))

    def _mode_card(self) -> None:
        card = Card(self._body)
        card.pack(fill="x", pady=(0, GAP))
        card.caption(self.t("settings.relay_mode"))
        row = card.row(pady=(4, 0))

        self._mode_labels = {
            mode: self.t(f"settings.relay_mode.{mode.value}") for mode in RelayMode
        }
        self._mode = ctk.CTkSegmentedButton(
            row,
            values=list(self._mode_labels.values()),
            height=32,
            font=font(12),
            fg_color=COLORS.background,
            selected_color=COLORS.panel_active,
            selected_hover_color=COLORS.panel_active,
            unselected_color=COLORS.panel,
            unselected_hover_color=COLORS.panel_hover,
            text_color=COLORS.text,
            command=self._sync_relay_fields,
        )
        current = RelayMode.parse(
            self._draft("draft_mode", self.window.settings.relay_mode)
        )
        self._mode.set(self._mode_labels[current])
        self._mode.pack(side="left", fill="x", expand=True)
        card.hint(self.t("settings.relay_mode_hint"))

    def capture_state(self) -> dict[str, object]:
        return {
            "draft_host": self._host_entry.get(),
            "draft_password": self._password_entry.get(),
            "draft_mode": self._selected_mode().value,
        }

    def _draft(self, key: str, stored: str) -> str:
        """What to show in a field: an unsaved edit if there is one."""
        value = self.options.get(key)
        return value if isinstance(value, str) else stored

    def _needs_own_relay(self, widget: ctk.CTkBaseClass) -> ctk.CTkBaseClass:
        """Mark a widget as meaningless without a relay of one's own."""
        self._own_relay_only.append(widget)
        return widget

    def _sync_relay_fields(self, _selection: str | None = None) -> None:
        """Grey out the relay fields when the public relay is chosen.

        Their contents stay: switching back has to bring the address and
        password back with it, rather than making the user retype them.
        """
        usable = self._selected_mode() is not RelayMode.PUBLIC
        for widget in self._own_relay_only:
            widget.configure(state="normal" if usable else "disabled")
            if isinstance(widget, ctk.CTkEntry):
                # CTkEntry has no text_color_disabled: without this it
                # would look editable and silently ignore typing.
                widget.configure(
                    text_color=COLORS.text if usable else COLORS.muted,
                    fg_color=COLORS.background if usable else COLORS.panel_hover,
                )

    def _selected_mode(self) -> RelayMode:
        chosen = self._mode.get()
        for mode, label in self._mode_labels.items():
            if label == chosen:
                return mode
        return RelayMode.OWN

    def _relay_card(self) -> None:
        settings = self.window.settings

        card = Card(self._body)
        card.pack(fill="x", pady=(0, GAP))
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
        self._host_entry.insert(0, self._draft("draft_host", settings.relay_host))
        self._host_entry.pack(fill="x", padx=PAD_CARD, pady=(4, 0))
        self._needs_own_relay(self._host_entry)
        card.hint(
            f"{self.t('settings.relay_host_hint')}  ({self._source_text('relay_host')})"
        )

        password_card = Card(self._body)
        password_card.pack(fill="x", pady=(0, GAP))
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
        self._password_entry.insert(
            0, self._draft("draft_password", settings.relay_password)
        )
        self._password_entry.pack(side="left", fill="x", expand=True)
        self._needs_own_relay(self._password_entry)

        self._reveal = ctk.CTkCheckBox(
            row,
            text=self.t("settings.show_password"),
            font=font(11),
            text_color=COLORS.muted,
            width=90,
            checkbox_width=18,
            checkbox_height=18,
            fg_color=COLORS.gold,
            hover_color=COLORS.gold_hover,
            command=self._toggle_password,
        )
        self._reveal.pack(side="left", padx=(10, 0))
        self._needs_own_relay(self._reveal)
        password_card.hint(
            f"{self.t('settings.relay_password_hint')}  "
            f"({self._source_text('relay_password')})"
        )

    def _source_text(self, key: str) -> str:
        source = self.window.settings.source_of(key)
        return self.t("settings.source", source=self.t(f"source.{source.value}"))

    def _toggle_password(self) -> None:
        self._password_entry.configure(show="" if self._reveal.get() else "•")

    # ------------------------------------------------------------------
    def _save(self) -> None:
        mode = self._selected_mode()
        host = self._host_entry.get().strip()
        # Only the public relay works without an address of your own.
        if not host and mode is not RelayMode.PUBLIC:
            self._message.configure(
                text=self.t("settings.invalid_host"), text_color=COLORS.error
            )
            return

        updated = with_relay(self.window.settings, host, self._password_entry.get())
        updated.relay_mode = mode.value
        path = save_settings(updated)

        # Re-read so the screen shows the resolved values and sources.
        self.window.reload_settings()
        self.window.show_settings(message=self.t("settings.saved", path=path))
