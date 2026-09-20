"""Layout checks against the real widgets.

These build the actual screens and measure them. No screenshots - those
go red on a font change with nothing broken. Every check here exists
because the bug it describes happened: ``pack`` silently shrinks what it
places last when a screen outgrows its window, leaving a button one
pixel high, present but unclickable.

Needs a display: your desktop, or xvfb in CI. They skip without one,
unless ``NOWERTRANSFER_UI_TESTS=required`` is set - CI does, so the job
cannot skip everything and report success.
"""

from __future__ import annotations

import os
import sys

import pytest

pytest.importorskip("tkinter", reason="this Python was built without tkinter")
ctk = pytest.importorskip("customtkinter", reason="GUI dependency not installed")

from nowertransfer import codes  # noqa: E402
from nowertransfer.config import RelayMode, Settings, Source  # noqa: E402
from nowertransfer.i18n import Translator  # noqa: E402

REQUIRED = os.environ.get("NOWERTRANSFER_UI_TESTS") == "required"

#: Default, and the minimum, where anything too big shows up first.
SIZES = ["720x620", "690x600"]
LANGUAGES = ["de", "en"]
SCREENS = ["home", "send", "receive", "settings"]

#: Below this a widget was squeezed out; real spacers are 10px or more.
MIN_VISIBLE_PX = 3


def _display_available() -> bool:
    """Whether a window can be opened here.

    Not by opening one: a throwaway ``tkinter.Tk`` becomes the implicit
    default root, and destroying it breaks every later window.
    """
    if sys.platform in {"win32", "darwin"}:
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


_HAS_DISPLAY = _display_available()
if REQUIRED and not _HAS_DISPLAY:
    raise RuntimeError(
        "NOWERTRANSFER_UI_TESTS=required but no display is available. "
        "Run these under xvfb, or unset the variable to allow skipping."
    )

pytestmark = pytest.mark.skipif(
    not _HAS_DISPLAY, reason="needs a display; CI runs these under xvfb"
)


# ----------------------------------------------------------------------
#  Harness
# ----------------------------------------------------------------------
def settle(window) -> None:
    """Let tkinter finish laying out before measuring anything."""
    for _ in range(6):
        window.update_idletasks()
        window.update()


def describe(widget) -> str:
    try:
        return f"{type(widget).__name__}({str(widget.cget('text'))[:40]!r})"
    except Exception:  # not every widget has text
        return type(widget).__name__


class Harness:
    """One window, reconfigured per test.

    Tk interpreters cannot be created and destroyed indefinitely in one
    process: after a handful, the next fails with errors about missing
    tcl files. A window per test would hit that. Also much faster.
    """

    def __init__(self, window, tmp_path) -> None:
        self.window = window
        self.tmp_path = tmp_path

    def settings(self, language: str, configured: bool) -> Settings:
        return Settings(
            relay_host="ftp.nower.cloud:9009" if configured else "",
            relay_password="hunter2" if configured else "",
            language=language,
            download_dir=str(self.tmp_path),
            sources={"relay_host": Source.BUILD, "relay_password": Source.BUILD},
        )

    def open(
        self,
        screen: str,
        *,
        language: str = "de",
        configured: bool = True,
        size: str = SIZES[0],
    ):
        window = self.window
        window.settings = self.settings(language, configured)
        window.t = Translator(language)
        window.geometry(size)
        getattr(window, f"show_{screen}")()
        settle(window)
        return window._view

    def collapsed(self, view) -> list[str]:
        """Direct children of a screen the layout squeezed to nothing."""
        return [
            describe(child)
            for child in view.winfo_children()
            if child.winfo_manager()
            and (
                child.winfo_height() < MIN_VISIBLE_PX
                or child.winfo_width() < MIN_VISIBLE_PX
            )
        ]


@pytest.fixture(scope="session")
def ui(tmp_path_factory):
    from nowertransfer import config, session
    from nowertransfer.ui.main_window import MainWindow

    tmp_path = tmp_path_factory.mktemp("ui-config")
    patch = pytest.MonkeyPatch()
    # Never touch the real user's settings or resume file.
    patch.setattr(config, "user_config_path", lambda: tmp_path / "config.toml")
    patch.setattr(config, "portable_config_path", lambda: tmp_path / "absent.toml")
    patch.setattr(config, "env_file_path", lambda: tmp_path / "absent.env")
    patch.setattr(session, "user_config_dir", lambda: tmp_path)

    harness = Harness(MainWindow(Settings(download_dir=str(tmp_path))), tmp_path)
    settle(harness.window)
    yield harness
    harness.window.destroy()
    patch.undo()


# ----------------------------------------------------------------------
#  Every screen, every language, at both sizes
# ----------------------------------------------------------------------
@pytest.mark.parametrize("screen", SCREENS)
@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("size", SIZES)
def test_no_widget_is_squeezed_out_of_the_layout(ui, screen, language, size):
    view = ui.open(screen, language=language, size=size)
    assert not ui.collapsed(view), f"{screen} [{language}] @ {size}"


@pytest.mark.parametrize("screen", ["send", "receive", "settings"])
@pytest.mark.parametrize("language", LANGUAGES)
def test_every_screen_has_a_visible_way_back(ui, screen, language):
    # The back link rendered one pixel high on two screens, which is
    # indistinguishable from not being there at all.
    view = ui.open(screen, language=language, size=SIZES[1])
    back = ui.window.t("nav.back")
    exits = [
        child
        for child in view.winfo_children()
        if isinstance(child, ctk.CTkButton)
        and child.cget("text") == back
        and child.winfo_height() >= MIN_VISIBLE_PX
    ]
    assert exits, f"{screen} [{language}] has no visible back button"


def test_the_first_run_screen_builds(ui):
    view = ui.open("home", configured=False)
    assert not ui.collapsed(view)


# ----------------------------------------------------------------------
#  The send screen and the code phrase
# ----------------------------------------------------------------------
def test_the_longest_possible_code_still_fits(ui):
    # Five long words run to about 45 characters. On one line beside the
    # buttons, they did not fit.
    longest = sorted(codes.WORDS, key=len, reverse=True)[: codes.WORD_COUNT]
    ui.window.send_code = "-".join([*longest, "88"])
    view = ui.open("send", size=SIZES[1])

    label = view._code_label
    assert label.winfo_width() <= label.master.winfo_width(), (
        f"{ui.window.send_code!r} overflows its card"
    )


def test_a_finished_send_does_not_reuse_its_code_phrase(ui):
    # The phrase is the encryption key: reusing it would let anyone who
    # learned it from one transfer read the next.
    from nowertransfer.transfer import EventType, TransferEvent

    view = ui.open("send")
    used = ui.window.send_code
    view.on_transfer_event(TransferEvent(EventType.FINISHED))
    settle(ui.window)

    assert ui.window.send_code != used


def test_a_send_that_cannot_start_leaves_no_resume_behind(ui, tmp_path):
    from nowertransfer import session

    view = ui.open("send", configured=False)
    ui.window.send_paths = [tmp_path]
    view.start_transfer()
    settle(ui.window)

    assert session.load_send_session() is None


def test_the_code_on_screen_is_the_one_that_will_be_sent(ui):
    ui.window.send_code = codes.generate_code()
    view = ui.open("send")
    assert view._code_label.cget("text") == ui.window.send_code


# ----------------------------------------------------------------------
#  Settings
# ----------------------------------------------------------------------
def select(view, mode: RelayMode) -> None:
    view._mode.set(view._mode_labels[mode])
    view._sync_relay_fields()


def test_the_relay_fields_are_locked_for_the_public_relay(ui):
    view = ui.open("settings")
    select(view, RelayMode.PUBLIC)
    settle(ui.window)

    assert view._host_entry.cget("state") == "disabled"
    assert view._password_entry.cget("state") == "disabled"
    assert view._reveal.cget("state") == "disabled"
    locked_colour = view._host_entry.cget("text_color")

    select(view, RelayMode.OWN)
    settle(ui.window)

    assert view._host_entry.cget("state") == "normal"
    # Disabling alone changes nothing on screen for a CTkEntry, so the
    # dimming is applied by hand and has to actually happen.
    assert view._host_entry.cget("text_color") != locked_colour


def test_locking_the_relay_fields_keeps_what_was_typed(ui):
    view = ui.open("settings")
    view._host_entry.delete(0, "end")
    view._host_entry.insert(0, "typed.example.com")

    for mode in (RelayMode.PUBLIC, RelayMode.OWN):
        select(view, mode)
        settle(ui.window)

    assert view._host_entry.get() == "typed.example.com"


def test_switching_language_keeps_unsaved_input(ui):
    view = ui.open("settings", language="de")
    view._host_entry.delete(0, "end")
    view._host_entry.insert(0, "typed.example.com")
    view._mode.set(view._mode_labels[RelayMode.FALLBACK])

    ui.window.set_language("en")
    settle(ui.window)

    view = ui.window._view
    assert view._host_entry.get() == "typed.example.com"
    assert view._selected_mode() is RelayMode.FALLBACK
    assert view._mode_labels[RelayMode.FALLBACK] == "Mine, then public"


# ----------------------------------------------------------------------
#  Navigation
# ----------------------------------------------------------------------
def test_navigating_leaves_exactly_one_screen_behind(ui):
    for screen in SCREENS:
        view = ui.open(screen)
        assert view.winfo_exists()
        assert len(ui.window.content.winfo_children()) == 1
