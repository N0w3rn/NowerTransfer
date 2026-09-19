"""Send screen: choose what to send, hand over the code phrase."""

from __future__ import annotations

import threading
import tkinter
from contextlib import suppress
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from ...codes import generate_code
from ...paths import human_size, total_size
from ...session import clear_send_session, save_send_session
from ..theme import COLORS, PAD_CARD, SEND_ACCENT, font, mono
from ..widgets import Card, link_button, quiet_button
from .base import TransferScreen

#: How often the main thread checks whether the size is known yet.
_SIZE_POLL_MS = 80


class SendView(TransferScreen):
    accent = SEND_ACCENT

    def build(self) -> None:
        self.header(self.t("send.subtitle"))
        self._selection_card()
        self._code_card()
        self.build_action_area(self.t("send.start"))
        self._measure_selection()

    # ------------------------------------------------------------------
    def _selection_card(self) -> None:
        card = Card(self)
        card.pack(fill="x")

        buttons = card.row()
        ctk.CTkButton(
            buttons,
            text=self.t("send.choose_folder"),
            width=140,
            fg_color=self.accent.color,
            hover_color=self.accent.hover,
            text_color=self.accent.ink,
            font=font(13, bold=True),
            command=self._choose_folder,
        ).pack(side="left")
        quiet_button(buttons, self.t("send.choose_files"), self._choose_files).pack(
            side="left", padx=8
        )

        self._selection_label = ctk.CTkLabel(
            card,
            text=self._selection_text(),
            text_color=COLORS.muted,
            font=font(12),
            wraplength=500,
            justify="left",
            anchor="w",
        )
        self._selection_label.pack(anchor="w", padx=PAD_CARD, pady=(8, PAD_CARD))

    def _code_card(self) -> None:
        card = Card(self, accent=self.accent.color)
        card.pack(fill="x", pady=12)
        card.caption(self.t("send.code_label"))

        # Its own line, wrapped: five words run to some 45 characters,
        # which will not share a row with the buttons.
        self._code_label = ctk.CTkLabel(
            card,
            text=self.window.send_code,
            font=mono(17, bold=True),
            text_color=self.accent.color,
            wraplength=520,
            justify="left",
            anchor="w",
        )
        self._code_label.pack(fill="x", padx=PAD_CARD, pady=(2, 0))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=PAD_CARD, pady=(4, PAD_CARD))
        link_button(row, self.t("send.copy"), self._copy_code, width=90).pack(
            side="right"
        )
        link_button(row, self.t("send.regenerate"), self._new_code, width=100).pack(
            side="right", padx=(0, 4)
        )

    # ------------------------------------------------------------------
    def _selection_text(self, size: str = "") -> str:
        paths = self.window.send_paths
        if not paths:
            return self.t("send.nothing_selected")
        what = (
            str(paths[0])
            if len(paths) == 1
            else self.t("send.many_selected", count=len(paths))
        )
        return f"{what}  ·  {size}" if size else what

    def _refresh_selection(self) -> None:
        self._selection_label.configure(text=self._selection_text())
        self._measure_selection()

    def _measure_selection(self) -> None:
        """Add the total size once it is known.

        Walked in the background, because a deep folder takes long
        enough to freeze the window. The thread only fills a box; tk is
        not thread-safe, so the main thread collects the result.
        """
        paths = list(self.window.send_paths)
        if not paths:
            return

        measured: list[str] = []
        threading.Thread(
            target=lambda: measured.append(human_size(total_size(paths))),
            name="measure-selection",
            daemon=True,
        ).start()
        self._collect_size(paths, measured)

    def _collect_size(self, paths: list[Path], measured: list[str]) -> None:
        with suppress(tkinter.TclError):
            if not self.winfo_exists():
                return
            if not measured:
                self.after(_SIZE_POLL_MS, self._collect_size, paths, measured)
                return
            # The selection may have changed while we were counting.
            if paths == self.window.send_paths:
                self._selection_label.configure(text=self._selection_text(measured[0]))

    def _choose_folder(self) -> None:
        chosen = filedialog.askdirectory(title=self.t("send.folder_dialog"))
        if chosen:
            self.window.send_paths = [Path(chosen)]
            self._refresh_selection()

    def _choose_files(self) -> None:
        chosen = filedialog.askopenfilenames(title=self.t("send.files_dialog"))
        if chosen:
            self.window.send_paths = [Path(p) for p in chosen]
            self._refresh_selection()

    def _copy_code(self) -> None:
        self.window.copy_to_clipboard(self.window.send_code)
        self.panel.set_status(self.t("send.copied"))

    def _new_code(self) -> None:
        if self.window.transfer_running:
            return
        self.window.send_code = generate_code()
        self._code_label.configure(text=self.window.send_code)

    # ------------------------------------------------------------------
    def start_transfer(self) -> None:
        if not self.window.send_paths:
            self.panel.set_status(self.t("send.need_selection"), error=True)
            return
        if not self.window.start_send(self.window.send_paths, self.window.send_code):
            self.panel.set_status(self.t("error.no_relay"), error=True)
            return
        # Only once it is actually running: a session saved for a
        # transfer that never started offers a resume for nothing.
        save_send_session(
            self.window.send_code, [str(p) for p in self.window.send_paths]
        )
        self.enter_running()
        self.panel.set_status(self.t("send.connecting"))

    def on_finished(self) -> None:
        clear_send_session()
        # The phrase is the encryption key, so the next transfer gets a
        # new one rather than reusing one that has already been shared.
        self.window.send_code = generate_code()
