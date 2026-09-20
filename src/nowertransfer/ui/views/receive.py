"""Receive screen: enter the code phrase, pick where files land."""

from __future__ import annotations

import tkinter
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from ...codes import is_our_code, is_plausible_code
from ...paths import open_in_file_manager
from ..theme import COLORS, GAP, PAD_CARD, RADIUS, RECEIVE_ACCENT, font, mono
from ..widgets import caption, entry, hint, quiet_button
from .base import TransferScreen


class ReceiveView(TransferScreen):
    accent = RECEIVE_ACCENT

    def build(self) -> None:
        self.title_bar(self.t("home.receive.title"), "download")
        area = self.setup_area()
        self._code_field(area)
        self._target_row(area)
        self.build_action_area(self.t("receive.start"))
        self.footnote.configure(text=self.t("receive.sender_must_start"))

    # ------------------------------------------------------------------
    def _code_field(self, parent: ctk.CTkFrame) -> None:
        caption(parent, self.t("receive.code_label")).pack(anchor="w", pady=(26, 0))
        self._code_entry = entry(
            parent,
            placeholder=self.t("receive.code_placeholder"),
            accent=True,
            big=True,
        )
        self._code_entry.pack(fill="x", pady=(9, 0))
        self._code_entry.bind("<Return>", lambda _event: self.start_transfer())
        hint(parent, self.t("receive.code_help")).pack(anchor="w", pady=(7, 0))
        self._offer_the_clipboard()

    def _offer_the_clipboard(self) -> None:
        """Fill the field if the clipboard holds one of our phrases.

        The sender copies the phrase and the receiver pastes it, every
        single time, so doing it for them saves the most common
        keystroke in the app.

        Only on a certainty, never a guess: ``is_our_code`` requires
        our exact shape, five words from our own list plus the digits.
        Anything else - a sentence, a URL, a phrase from another croc
        client - leaves the field empty rather than putting something
        wrong in front of the user.
        """
        try:
            pasted = self.window.clipboard_get()
        except tkinter.TclError:
            return  # empty, or holding something that is not text
        if is_our_code(pasted):
            self._code_entry.insert(0, pasted.strip().lower())

    def _target_row(self, parent: ctk.CTkFrame) -> None:
        card = ctk.CTkFrame(parent, fg_color=COLORS.panel, corner_radius=RADIUS)
        card.pack(fill="x", pady=(GAP + 6, 0))

        texts = ctk.CTkFrame(card, fg_color="transparent")
        texts.pack(side="left", fill="x", expand=True, padx=(PAD_CARD, 0), pady=13)
        caption(texts, self.t("receive.target_label")).pack(anchor="w")
        self._target_label = ctk.CTkLabel(
            texts,
            text=str(self.window.receive_dir),
            text_color=COLORS.text,
            # Same face as every other path and address in the app.
            font=mono(11),
            anchor="w",
        )
        self._target_label.pack(anchor="w", pady=(4, 0))

        quiet_button(
            card, self.t("receive.change"), self._choose_target, width=90
        ).pack(side="right", padx=PAD_CARD)

    def _choose_target(self) -> None:
        chosen = filedialog.askdirectory(title=self.t("receive.target_dialog"))
        if chosen:
            self.window.set_download_dir(Path(chosen))
            self._target_label.configure(text=chosen)

    # ------------------------------------------------------------------
    def start_transfer(self) -> None:
        if self.window.transfer_running:
            return
        code = self._code_entry.get().strip()
        if not is_plausible_code(code):
            self.complain(self.t("receive.need_code"))
            return
        if not self.window.start_receive(code, self.window.receive_dir):
            self.complain(self.t("error.no_relay"))
            return
        self.enter_running()
        self.panel.set_phase(self.t("receive.connecting"))

    def _show_finished(self) -> None:
        """Two ways on: straight to the files, or back to the start."""
        for child in self.actions.winfo_children():
            child.destroy()
        self.actions.grid_columnconfigure((0, 1), weight=1, uniform="done")

        ctk.CTkButton(
            self.actions,
            text=self.t("receive.open_folder"),
            height=46,
            corner_radius=RADIUS,
            fg_color=self.accent.color,
            hover_color=self.accent.hover,
            text_color=self.accent.ink,
            font=font(14, bold=True),
            command=lambda: open_in_file_manager(self.window.receive_dir),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            self.actions,
            text=self.t("done.close"),
            height=46,
            corner_radius=RADIUS,
            fg_color="transparent",
            border_width=1,
            border_color=COLORS.border,
            hover_color=COLORS.panel_hover,
            text_color=COLORS.text,
            font=font(14, bold=True),
            command=self.window.show_home,
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))
