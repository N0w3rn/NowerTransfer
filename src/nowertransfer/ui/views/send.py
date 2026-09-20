"""Send screen: choose what to send, hand over the code phrase."""

from __future__ import annotations

import threading
import tkinter
from contextlib import suppress
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from ...codes import code_entropy_bits, generate_code
from ...paths import human_size, total_size
from ...session import clear_session, save_send_session
from ..dnd import accept_files
from ..icons import Icon
from ..theme import COLORS, GAP, PAD_CARD, RADIUS_LARGE, SEND_ACCENT, font, mono
from ..widgets import Card, caption, link_button, quiet_button
from .base import TransferScreen

#: How often the main thread checks whether the size is known yet.
_SIZE_POLL_MS = 80


class SendView(TransferScreen):
    accent = SEND_ACCENT

    def build(self) -> None:
        bar = self.title_bar(self.t("home.send.title"), "upload")
        ctk.CTkLabel(
            bar, text=self.t("send.step"), font=font(11), text_color=COLORS.faint
        ).pack(side="right")

        area = self.setup_area()
        self._drop_zone(area)
        self._selection_row(area)
        self._code_card(area)
        self.build_action_area(self.t("send.start"))
        self.footnote.configure(text=self.t("send.recipient_needs"))
        self._measure_selection()

    # ------------------------------------------------------------------
    def _drop_zone(self, parent: ctk.CTkFrame) -> None:
        zone = ctk.CTkFrame(
            parent,
            fg_color=COLORS.well,
            corner_radius=RADIUS_LARGE,
            border_width=1,
            border_color=COLORS.border,
        )
        zone.pack(fill="x", pady=(18, 0))
        self._zone = zone

        Icon(zone, "drop", size=30, color=COLORS.muted, background=COLORS.well).pack(
            pady=(18, 0)
        )
        self._zone_label = ctk.CTkLabel(
            zone,
            text=self.t("send.drop_here"),
            font=font(13),
            text_color=COLORS.text,
        )
        self._zone_label.pack(pady=(6, 0))

        buttons = ctk.CTkFrame(zone, fg_color="transparent")
        buttons.pack(pady=(14, 20))
        ctk.CTkButton(
            buttons,
            text=self.t("send.choose_folder"),
            width=140,
            height=34,
            corner_radius=9,
            fg_color=self.accent.color,
            hover_color=self.accent.hover,
            text_color=self.accent.ink,
            font=font(12, bold=True),
            command=self._choose_folder,
        ).pack(side="left")
        quiet_button(
            buttons, self.t("send.choose_files"), self._choose_files, width=140
        ).pack(side="left", padx=(10, 0))

        # Registered last: the buttons have to exist to be registered
        # too, or a drop onto one of them goes nowhere.
        droppable = accept_files(
            zone, self._dropped, self._highlight_zone, self._plain_zone
        )
        if not droppable:
            self._zone_label.configure(text=self.t("send.pick_here"))

    def _dropped(self, paths: list[Path]) -> None:
        if self.window.transfer_running:
            return
        self.window.send_paths = paths
        self._refresh_selection()

    def _highlight_zone(self) -> None:
        self._zone.configure(border_color=self.accent.color, fg_color=COLORS.panel)

    def _plain_zone(self) -> None:
        self._zone.configure(border_color=COLORS.border, fg_color=COLORS.well)

    def _selection_row(self, parent: ctk.CTkFrame) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(GAP, 0))
        self._selection_label = ctk.CTkLabel(
            row,
            text=self._selection_text(),
            text_color=COLORS.muted,
            # A path is machine text, like the relay address and the
            # code phrase, and belongs in the same face as those.
            font=mono(11),
            wraplength=560,
            justify="left",
            anchor="w",
        )
        self._selection_label.pack(anchor="w", padx=4)

    def _code_card(self, parent: ctk.CTkFrame) -> None:
        card = Card(parent, accent=self.accent.color)
        card.pack(fill="x", pady=(GAP, 0))

        head = card.row(pady=(PAD_CARD, 0))
        caption(head, self.t("send.code_label")).pack(side="left")

        self._code_label = ctk.CTkLabel(
            card,
            text=self.window.send_code,
            font=mono(19, bold=True),
            text_color=self.accent.color,
            wraplength=540,
            justify="left",
            anchor="w",
        )
        self._code_label.pack(fill="x", padx=PAD_CARD, pady=(8, 0))

        row = card.row(pady=(12, PAD_CARD))
        quiet_button(row, self.t("send.copy"), self._copy_code, width=110).pack(
            side="left"
        )
        link_button(row, self.t("send.regenerate"), self._new_code, width=110).pack(
            side="left", padx=(8, 0)
        )
        ctk.CTkLabel(
            row,
            text=self.t("send.entropy", bits=round(code_entropy_bits())),
            font=font(11),
            text_color=COLORS.faint,
        ).pack(side="right")

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
        return f"{what}   ·   {size}" if size else what

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
                self.panel.set_stat("size", measured[0])
                self.panel.set_stat("items", str(len(paths)))

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
        self.complain(self.t("send.copied"))

    def _new_code(self) -> None:
        if self.window.transfer_running:
            return
        self.window.send_code = generate_code()
        self._code_label.configure(text=self.window.send_code)

    # ------------------------------------------------------------------
    def start_transfer(self) -> None:
        if not self.window.send_paths:
            self.complain(self.t("send.need_selection"))
            return
        if not self.window.start_send(self.window.send_paths, self.window.send_code):
            self.complain(self.t("error.no_relay"))
            return
        # Only once it is actually running: a session saved for a
        # transfer that never started offers a resume for nothing.
        save_send_session(
            self.window.send_code, [str(p) for p in self.window.send_paths]
        )
        self.enter_running()
        self.panel.set_phase(self.t("send.connecting"))

    def finished_text(self) -> str:
        return self.t("done.sent")

    def on_finished(self) -> None:
        clear_session()
        # The phrase is the encryption key, so the next transfer gets a
        # new one rather than reusing one that has already been shared.
        self.window.send_code = generate_code()
