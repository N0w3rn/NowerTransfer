"""Receive screen: enter the code phrase, pick where files land."""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from ...codes import is_plausible_code
from ..theme import COLORS, PAD_CARD, RECEIVE_ACCENT, font, mono
from ..widgets import Card, quiet_button
from .base import TransferScreen


class ReceiveView(TransferScreen):
    accent = RECEIVE_ACCENT

    def build(self) -> None:
        self.header(self.t("receive.subtitle"))
        self._code_card()
        self._target_card()
        self.build_action_area(self.t("receive.start"))

    # ------------------------------------------------------------------
    def _code_card(self) -> None:
        card = Card(self, accent=self.accent.color)
        card.pack(fill="x")
        card.caption(self.t("receive.code_label"))
        self._code_entry = ctk.CTkEntry(
            card,
            font=mono(17),
            height=44,
            fg_color=COLORS.background,
            border_color=self.accent.color,
            text_color=self.accent.color,
            placeholder_text=self.t("receive.code_placeholder"),
        )
        self._code_entry.pack(fill="x", padx=PAD_CARD, pady=(4, PAD_CARD))
        self._code_entry.bind("<Return>", lambda _event: self.start_transfer())

    def _target_card(self) -> None:
        card = Card(self)
        card.pack(fill="x", pady=12)
        row = card.row(pady=PAD_CARD)
        quiet_button(
            row, self.t("receive.choose_target"), self._choose_target, width=150
        ).pack(side="left")
        self._target_label = ctk.CTkLabel(
            row,
            text=str(self.window.receive_dir),
            text_color=COLORS.muted,
            font=font(12),
            wraplength=340,
            justify="left",
        )
        self._target_label.pack(side="left", padx=10)

    def _choose_target(self) -> None:
        chosen = filedialog.askdirectory(title=self.t("receive.target_dialog"))
        if chosen:
            self.window.receive_dir = Path(chosen)
            self._target_label.configure(text=chosen)

    # ------------------------------------------------------------------
    def start_transfer(self) -> None:
        if self.window.transfer_running:
            return
        code = self._code_entry.get().strip()
        if not is_plausible_code(code):
            self.panel.set_status(self.t("receive.need_code"), error=True)
            return
        if not self.window.start_receive(code, self.window.receive_dir):
            self.panel.set_status(self.t("error.no_relay"), error=True)
            return
        self.enter_running()
        self.panel.set_status(self.t("receive.connecting"))
