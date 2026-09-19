"""The application window: owns the state, routes between screens.

Screens are created fresh on every navigation and destroyed on the way
out. All state that must survive a screen change - the selected files, the
code phrase, the running worker - lives here.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from queue import Empty, Queue

import customtkinter as ctk

from .. import APP_NAME
from ..codes import generate_code
from ..config import Settings, load_settings, save_settings
from ..croc import find_croc
from ..i18n import Translator
from ..session import SendSession
from ..transfer import EventType, TransferEvent, TransferWorker
from .theme import COLORS, PAD_WINDOW
from .views import HomeView, ReceiveView, SendView, SettingsView
from .views.base import View

#: How often the UI thread checks the worker queue, in milliseconds.
POLL_INTERVAL_MS = 100

_TERMINAL_EVENTS = frozenset(
    {EventType.FINISHED, EventType.CANCELLED, EventType.FAILED}
)


class MainWindow(ctk.CTk):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")

        self.settings = settings
        self.t = Translator(settings.language)
        self.croc_path = find_croc()

        self.events: Queue[TransferEvent] = Queue()
        self.send_paths: list[Path] = []
        self.send_code = generate_code()
        self.receive_dir = Path(settings.download_dir)

        self._worker: TransferWorker | None = None
        self._running = False
        self._poll_job: str | None = None
        self._view: View | None = None
        self._view_factory: type[View] = HomeView
        self._view_options: dict[str, object] = {}

        self.title(APP_NAME)
        self.geometry("640x580")
        self.minsize(580, 540)
        self.configure(fg_color=COLORS.background)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.content = ctk.CTkFrame(self, fg_color=COLORS.background)
        self.content.pack(fill="both", expand=True, padx=PAD_WINDOW, pady=20)

        self.show_home()
        self._poll_job = self.after(POLL_INTERVAL_MS, self._drain_events)

    # ------------------------------------------------------------------
    #  Navigation
    # ------------------------------------------------------------------
    def show_home(self) -> None:
        if self._running:
            self.cancel_transfer()
        self._show(HomeView)

    def show_send(self, resume: SendSession | None = None) -> None:
        if resume is not None:
            self.send_code = resume.code
            self.send_paths = [Path(p) for p in resume.paths]
        self._show(SendView)

    def show_receive(self) -> None:
        self._show(ReceiveView)

    def show_settings(self, message: str = "") -> None:
        self._show(SettingsView, message=message)

    def _show(self, factory: type[View], **options: object) -> None:
        if self._view is not None:
            self._view.on_leave()
            self._view.destroy()
        self._view_factory = factory
        self._view_options = options
        self._view = factory(self, **options)
        self._view.pack(fill="both", expand=True)

    def _rebuild(self) -> None:
        """Redraw the current screen, e.g. after the language changed."""
        self._show(self._view_factory, **self._view_options)

    # ------------------------------------------------------------------
    #  Settings
    # ------------------------------------------------------------------
    def reload_settings(self) -> None:
        self.settings = load_settings()
        self.t = Translator(self.settings.language)

    def set_language(self, language: str) -> None:
        if language == self.t.language:
            return
        self.settings.language = language
        self.t = Translator(language)
        save_settings(self.settings)
        self._rebuild()

    # ------------------------------------------------------------------
    #  Transfers
    # ------------------------------------------------------------------
    @property
    def transfer_running(self) -> bool:
        return self._running

    def start_send(self, paths: Sequence[Path], code: str) -> bool:
        return self._start(lambda worker: worker.start_send(paths, code))

    def start_receive(self, code: str, target: Path) -> bool:
        return self._start(lambda worker: worker.start_receive(code, target))

    def _start(self, launch: Callable[[TransferWorker], None]) -> bool:
        if self.croc_path is None or not self.settings.is_configured:
            return False
        self._worker = TransferWorker(
            self.croc_path,
            self.settings.relay,
            self.events,
            allow_public_fallback=self.settings.allows_public_fallback,
        )
        launch(self._worker)
        self._running = True
        return True

    def cancel_transfer(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    # ------------------------------------------------------------------
    #  Worker events
    # ------------------------------------------------------------------
    def _drain_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                if event.type in _TERMINAL_EVENTS:
                    self._running = False
                if self._view is not None:
                    self._view.on_transfer_event(event)
        except Empty:
            pass
        self._poll_job = self.after(POLL_INTERVAL_MS, self._drain_events)

    # ------------------------------------------------------------------
    def copy_to_clipboard(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)

    def _on_close(self) -> None:
        self.cancel_transfer()
        self.destroy()

    def destroy(self) -> None:
        # Stop polling before the widgets go away: a callback that fires
        # after the window is gone raises out of tkinter's event loop.
        if self._poll_job is not None:
            self.after_cancel(self._poll_job)
            self._poll_job = None
        super().destroy()
