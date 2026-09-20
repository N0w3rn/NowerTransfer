"""The application window: owns the state, routes between screens.

Screens are created fresh on every navigation and destroyed on the way
out. All state that must survive a screen change - the selected files, the
code phrase, the running worker - lives here.
"""

from __future__ import annotations

import threading
import tkinter as tk
from collections.abc import Callable, Sequence
from contextlib import suppress
from pathlib import Path
from queue import Empty, Queue

import customtkinter as ctk

from .. import APP_NAME, __version__
from ..codes import generate_code
from ..config import Settings, load_settings, save_settings
from ..croc import find_croc
from ..i18n import Translator
from ..paths import icon_path
from ..relaycheck import reach
from ..session import SendSession
from ..transfer import EventType, TransferEvent, TransferWorker
from ..updates import Release, newer_than
from . import winicon
from .theme import COLORS, PAD_WINDOW
from .views import HomeView, ReceiveView, SendView, SettingsView
from .views.base import View

#: How often the UI thread checks the worker queue, in milliseconds.
POLL_INTERVAL_MS = 100

#: The update check answers once or not at all, so this can be lazy.
UPDATE_POLL_MS = 400

#: The relay answers in milliseconds or times out in four seconds.
RELAY_POLL_MS = 200

_TERMINAL_EVENTS = frozenset(
    {EventType.FINISHED, EventType.CANCELLED, EventType.FAILED}
)


class MainWindow(ctk.CTk):
    def __init__(
        self, settings: Settings, preselect: Sequence[Path] | None = None
    ) -> None:
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
        self._update_job: str | None = None
        self._relay_job: str | None = None
        #: The newer release, once the background check has found one.
        self.newer_release: Release | None = None
        #: Whether the relay answered a TCP connect. None while the
        #: check is still running, or when there is no own relay to
        #: check - the start screen shows all three differently.
        self.relay_reachable: bool | None = None
        self._view: View | None = None
        self._view_factory: type[View] = HomeView
        self._view_options: dict[str, object] = {}

        self.title(APP_NAME)
        self.geometry("720x620")
        self.minsize(690, 600)
        self.configure(fg_color=COLORS.background)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._apply_icon()

        self.content = ctk.CTkFrame(self, fg_color=COLORS.background)
        self.content.pack(fill="both", expand=True, padx=PAD_WINDOW, pady=20)

        self.open_first_screen(preselect)
        self._poll_job = self.after(POLL_INTERVAL_MS, self._drain_events)
        self._start_update_check()
        self.start_relay_check()

    def _apply_icon(self) -> None:
        """Put the logo in the title bar and the taskbar.

        PyInstaller's --icon only covers the .exe file itself; the
        running window needs this. Purely cosmetic, so a platform that
        cannot do it (tkinter wants .xbm outside Windows) is not worth
        an error.
        """
        icon = icon_path()
        if icon is None:
            return
        # iconbitmap first, and not only as the fallback: 200ms after
        # start CustomTkinter installs *its* icon unless this method
        # has been called. It checks nothing but that, so calling it
        # claims the slot as well as setting a usable icon.
        with suppress(tk.TclError):
            self.iconbitmap(str(icon))
        # Then the real thing: one image per size, which iconbitmap
        # does not do - see ui/winicon.py.
        winicon.apply_icon(self, icon)

    def open_first_screen(self, preselect: Sequence[Path] | None) -> None:
        """Where the app lands at start.

        Started from the Explorer menu with a selection, that is the
        screen which can act on it; otherwise the start screen. A
        method rather than a few lines in ``__init__`` so it can be
        exercised without building a second Tk root, which this app's
        tests cannot afford - a handful of them and Tk stops making
        interpreters.
        """
        if preselect:
            self.send_paths = list(preselect)
            self.show_send()
        else:
            self.show_home()

    # ------------------------------------------------------------------
    #  Update notice
    # ------------------------------------------------------------------
    def _start_update_check(self) -> None:
        """Ask GitHub about newer releases, unless told not to.

        Off the main thread, because a network call on it would freeze
        the window, and collected by polling because tk cannot be
        touched from anywhere else.
        """
        if not self.settings.checks_for_updates:
            return
        found: list[Release] = []
        threading.Thread(
            target=lambda: self._look_for_update(found),
            name="update-check",
            daemon=True,
        ).start()
        self._update_job = self.after(UPDATE_POLL_MS, self._collect_update, found)

    def _look_for_update(self, found: list[Release]) -> None:
        release = newer_than(__version__)
        if release is not None:
            found.append(release)

    def _collect_update(self, found: list[Release]) -> None:
        if not found:
            self._update_job = self.after(UPDATE_POLL_MS, self._collect_update, found)
            return
        self._update_job = None
        self.newer_release = found[0]
        # Only the start screen shows it, and only if that is where
        # the user still is - redrawing under them would be rude.
        if isinstance(self._view, HomeView):
            self._rebuild()

    # ------------------------------------------------------------------
    #  Is the relay there?
    # ------------------------------------------------------------------
    def start_relay_check(self) -> None:
        """Ask the relay whether it answers, so the dot can say so.

        The start screen showed a gold dot whatever the state of the
        relay, which is a claim the app had not checked. This is a TCP
        connect and nothing more - it says the relay is listening, not
        that the password is right. Nothing else can; see
        :mod:`~nowertransfer.relaycheck`.
        """
        if self._relay_job is not None:
            self.after_cancel(self._relay_job)
            self._relay_job = None
        self.relay_reachable = None

        relay = self.settings.relay
        if not relay.is_set:
            return  # the public relay: no address of ours to test

        answered: list[bool] = []
        threading.Thread(
            target=lambda: answered.append(reach(relay.host) is not None),
            name="relay-reachability",
            daemon=True,
        ).start()
        self._relay_job = self.after(RELAY_POLL_MS, self._collect_relay, answered)

    def _collect_relay(self, answered: list[bool]) -> None:
        if not answered:
            self._relay_job = self.after(RELAY_POLL_MS, self._collect_relay, answered)
            return
        self._relay_job = None
        self.relay_reachable = answered[0]
        if isinstance(self._view, HomeView):
            self._rebuild()

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
        options = dict(self._view_options)
        if self._view is not None:
            options.update(self._view.capture_state())
        self._show(self._view_factory, **options)

    # ------------------------------------------------------------------
    #  Settings
    # ------------------------------------------------------------------
    def reload_settings(self) -> None:
        self.settings = load_settings()
        self.t = Translator(self.settings.language)
        # The relay may be a different one now, so the old answer says
        # nothing about it.
        self.start_relay_check()

    def set_download_dir(self, folder: Path) -> None:
        """Remember where received files go, across restarts."""
        self.receive_dir = folder
        self.settings.download_dir = str(folder)
        save_settings(self.settings)

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
        # A callback firing after the widgets are gone raises out of
        # tkinter's event loop, where nothing catches it.
        for job in (self._poll_job, self._update_job, self._relay_job):
            if job is not None:
                self.after_cancel(job)
        self._poll_job = self._update_job = self._relay_job = None
        super().destroy()
