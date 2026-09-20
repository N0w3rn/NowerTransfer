"""Settings screen: the relay this app talks to.

Every field shows which layer its value came from. Language is not one
of them: it is the header toggle, the same control as on the start
screen, so there is only ever one way to change it.
"""

from __future__ import annotations

import threading
import tkinter
from contextlib import suppress

import customtkinter as ctk

from ...config import RelayMode, save_settings, with_relay
from ...relaycheck import RelayCheck, RelayStatus, check
from ..theme import COLORS, GAP, GOLD_ACCENT, NEUTRAL_ACCENT, RADIUS, font, mono
from ..widgets import (
    Segmented,
    StatusDot,
    caption,
    entry,
    hint,
    outline_button,
    primary_button,
)
from .base import View

_CHECK_POLL_MS = 120


class SettingsView(View):
    accent = NEUTRAL_ACCENT

    def build(self) -> None:
        bar = self.title_bar(self.t("settings.title"))
        self.language_switch(bar).pack(side="right")

        #: Register with _needs_own_relay; _sync_relay_fields switches
        #: them as a group. A relay-only widget added without that call
        #: stays editable in PUBLIC mode.
        self._own_relay_only: list[ctk.CTkBaseClass] = []

        self._footer()

        if not self.window.settings.is_configured:
            hint(self, self.t("setup.body"), width=600).pack(
                anchor="w", fill="x", pady=(18, 0)
            )

        self._mode_group()
        self._relay_fields()
        self._check_row()
        self._update_row()
        self._sync_relay_fields()

    # ------------------------------------------------------------------
    def _footer(self) -> None:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(side="bottom", fill="x", pady=(GAP, 0))
        primary_button(row, self.t("settings.save"), GOLD_ACCENT, self._save).pack(
            side="left"
        )
        self._message = ctk.CTkLabel(
            row,
            # `or`, not a default: navigating here passes message="".
            text=str(self.options.get("message") or self.t("settings.encrypted_note")),
            font=font(11),
            text_color=COLORS.faint,
            wraplength=380,
            justify="left",
        )
        self._message.pack(side="left", padx=(14, 0))

    def _mode_group(self) -> None:
        caption(self, self.t("settings.relay_mode")).pack(anchor="w", pady=(22, 0))

        self._mode_labels = {
            mode: self.t(f"settings.relay_mode.{mode.value}") for mode in RelayMode
        }
        self._mode = Segmented(
            self,
            list(self._mode_labels.values()),
            self._sync_relay_fields,
        )
        current = RelayMode.parse(
            self._draft("draft_mode", self.window.settings.relay_mode)
        )
        self._mode.set(self._mode_labels[current])
        self._mode.pack(fill="x", pady=(9, 0))
        hint(self, self.t("settings.relay_mode_hint"), width=600).pack(
            anchor="w", fill="x", pady=(8, 0)
        )

    def _relay_fields(self) -> None:
        settings = self.window.settings

        columns = ctk.CTkFrame(self, fg_color="transparent")
        columns.pack(fill="x", pady=(20, 0))
        columns.grid_columnconfigure((0, 1), weight=1, uniform="fields")

        left = ctk.CTkFrame(columns, fg_color="transparent")
        left.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        caption(left, self.t("settings.relay_host")).pack(anchor="w")
        self._host_entry = entry(
            left, placeholder=self.t("settings.relay_host_placeholder")
        )
        self._host_entry.insert(0, self._draft("draft_host", settings.relay_host))
        self._host_entry.pack(fill="x", pady=(8, 0))
        self._needs_own_relay(self._host_entry)
        hint(left, self._source_text("relay_host"), width=270).pack(
            anchor="w", pady=(7, 0)
        )

        right = ctk.CTkFrame(columns, fg_color="transparent")
        right.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        caption(right, self.t("settings.relay_password")).pack(anchor="w")
        self._password_entry = entry(
            right,
            placeholder=self.t("settings.relay_password_placeholder"),
            show="•",
        )
        self._password_entry.insert(
            0, self._draft("draft_password", settings.relay_password)
        )
        self._password_entry.pack(fill="x", pady=(8, 0))
        self._needs_own_relay(self._password_entry)

        under = ctk.CTkFrame(right, fg_color="transparent")
        under.pack(fill="x", pady=(7, 0))
        hint(under, self.t("settings.password_note"), width=200).pack(
            side="left", fill="x", expand=True
        )
        self._reveal = ctk.CTkCheckBox(
            under,
            text=self.t("settings.show_password"),
            font=font(11),
            text_color=COLORS.faint,
            text_color_disabled=COLORS.faint,
            width=70,
            checkbox_width=15,
            checkbox_height=15,
            corner_radius=4,
            border_width=1,
            border_color=COLORS.border,
            fg_color=COLORS.gold,
            hover_color=COLORS.gold_hover,
            checkmark_color=COLORS.ink,
            command=self._toggle_password,
        )
        self._reveal.pack(side="right")
        self._needs_own_relay(self._reveal)

    def _toggle_password(self) -> None:
        self._password_entry.configure(show="" if self._reveal.get() else "•")

    def _check_row(self) -> None:
        card = ctk.CTkFrame(self, fg_color=COLORS.panel, corner_radius=RADIUS)
        card.pack(fill="x", pady=(18, 0))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x")

        self._check_button = outline_button(
            row, self.t("relay.test"), self._run_check, width=150
        )
        self._check_button.pack(side="left", padx=(14, 0), pady=13)
        self._needs_own_relay(self._check_button)

        self._check_status = StatusDot(row, "", COLORS.faint)
        self._check_status.pack(side="left", padx=(14, 0))

        self._latency = ctk.CTkLabel(
            row, text="", font=mono(11), text_color=COLORS.faint
        )
        self._latency.pack(side="right", padx=14)

        # Said before the test is run, not only after: the button must
        # not read as an offer to verify the password.
        hint(card, self.t("relay.password_unverifiable"), width=600).pack(
            anchor="w", fill="x", padx=14, pady=(0, 13)
        )

    def _update_row(self) -> None:
        card = ctk.CTkFrame(self, fg_color=COLORS.panel, corner_radius=RADIUS)
        card.pack(fill="x", pady=(12, 0))

        self._update_check = ctk.CTkCheckBox(
            card,
            text=self.t("settings.update_check"),
            font=font(12),
            text_color=COLORS.text,
            checkbox_width=17,
            checkbox_height=17,
            corner_radius=4,
            border_width=1,
            border_color=COLORS.border,
            fg_color=COLORS.gold,
            hover_color=COLORS.gold_hover,
            checkmark_color=COLORS.ink,
        )
        if self._draft_update_check():
            self._update_check.select()
        self._update_check.pack(anchor="w", padx=14, pady=(13, 0))
        hint(card, self.t("settings.update_check_hint"), width=600).pack(
            anchor="w", fill="x", padx=14, pady=(7, 13)
        )

    def _draft_update_check(self) -> bool:
        draft = self.options.get("draft_update_check")
        if isinstance(draft, bool):
            return draft
        return self.window.settings.checks_for_updates

    # ------------------------------------------------------------------
    def _run_check(self) -> None:
        """Ask the relay, in the background; tk stays on its own thread."""
        relay = with_relay(
            self.window.settings,
            self._host_entry.get(),
            self._password_entry.get(),
        ).relay
        self._check_status.set(self.t("relay.checking"), COLORS.muted)
        self._latency.configure(text="")
        self._check_button.configure(state="disabled")

        result: list[RelayCheck] = []
        threading.Thread(
            target=lambda: result.append(check(relay, self.window.croc_path)),
            name="relay-check",
            daemon=True,
        ).start()
        self._collect_check(result)

    def _collect_check(self, result: list[RelayCheck]) -> None:
        with suppress(tkinter.TclError):
            if not self.winfo_exists():
                return
            if not result:
                self.after(_CHECK_POLL_MS, self._collect_check, result)
                return

            outcome = result[0]
            texts = {
                RelayStatus.REACHABLE: (self.t("relay.reachable"), COLORS.gold),
                RelayStatus.WRONG_PASSWORD: (
                    self.t("error.relay_password"),
                    COLORS.error,
                ),
                RelayStatus.UNREACHABLE: (self.t("relay.unreachable"), COLORS.error),
            }
            text, color = texts[outcome.status]
            self._check_status.set(text, color)
            self._latency.configure(
                text=f"{outcome.milliseconds} ms" if outcome.milliseconds else ""
            )
            self._check_button.configure(state="normal")

    # ------------------------------------------------------------------
    def capture_state(self) -> dict[str, object]:
        return {
            "draft_host": self._host_entry.get(),
            "draft_password": self._password_entry.get(),
            "draft_mode": self._selected_mode().value,
            "draft_update_check": bool(self._update_check.get()),
        }

    def _draft(self, key: str, stored: str) -> str:
        """What to show in a field: an unsaved edit if there is one."""
        value = self.options.get(key)
        return value if isinstance(value, str) else stored

    def _needs_own_relay(self, widget: ctk.CTkBaseClass) -> ctk.CTkBaseClass:
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
                    text_color=COLORS.text if usable else COLORS.faint,
                    fg_color=COLORS.well if usable else COLORS.panel,
                )

    def _selected_mode(self) -> RelayMode:
        chosen = self._mode.get()
        for mode, label in self._mode_labels.items():
            if label == chosen:
                return mode
        return RelayMode.OWN

    def _source_text(self, key: str) -> str:
        source = self.window.settings.source_of(key)
        return self.t("settings.source", source=self.t(f"source.{source.value}"))

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
        # Only "off" is stored: leaving it on is the default, and an
        # empty value keeps the file to what the user actually changed.
        updated.update_check = "" if self._update_check.get() else "off"
        path = save_settings(updated)

        # Re-read so the screen shows the resolved values and sources.
        self.window.reload_settings()
        self.window.show_settings(message=self.t("settings.saved", path=path))
