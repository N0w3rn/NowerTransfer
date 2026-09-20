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

    def settings(self, language: str, configured: bool, public: bool) -> Settings:
        return Settings(
            relay_host="relay.example.com:9009" if configured else "",
            relay_password="hunter2" if configured else "",
            relay_mode=(RelayMode.PUBLIC if public else RelayMode.OWN).value,
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
        public: bool = False,
        size: str = SIZES[0],
    ):
        window = self.window
        window.settings = self.settings(language, configured, public)
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
    from nowertransfer.ui import main_window as main_window_module
    from nowertransfer.ui.main_window import MainWindow

    tmp_path = tmp_path_factory.mktemp("ui-config")
    patch = pytest.MonkeyPatch()
    # Never touch the real user's settings or resume file.
    patch.setattr(config, "user_config_path", lambda: tmp_path / "config.toml")
    patch.setattr(config, "portable_config_path", lambda: tmp_path / "absent.toml")
    patch.setattr(config, "env_file_path", lambda: tmp_path / "absent.env")
    patch.setattr(session, "user_config_dir", lambda: tmp_path)
    # No background work may reach into these tests. Both checks the
    # window runs are threads that write to the shared window whenever
    # they happen to finish, so a slow answer lands in whatever test
    # is measuring the screen at that moment - a different one each
    # run, on a different machine each time.
    #
    # The update check added the update notice partway through a run,
    # and its StatusDot is gold. Saving on the settings screen calls
    # reload_settings, which starts a relay check; that answer set
    # relay_reachable to False and painted the dot red inside the next
    # test, which had just set it to True by hand.
    #
    # Neither is what this file is about: the dot tests set the state
    # directly, and the checks have tests of their own.
    patch.setattr(main_window_module, "newer_than", lambda _version: None)
    patch.setattr(MainWindow, "start_relay_check", lambda _self: None)

    window = MainWindow(Settings(download_dir=str(tmp_path)))
    # The screens branch on whether croc was found, and CI has no
    # vendored binary: without this the start screen shows the "croc
    # missing" card instead of the role cards, and every test that
    # measures them fails somewhere far away from the cause. Nothing
    # here runs it - the layout only asks whether it exists.
    window.croc_path = tmp_path / "croc-that-is-never-run"
    settle(window)

    harness = Harness(window, tmp_path)
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
    # The back control rendered one pixel high on two screens, which is
    # indistinguishable from not being there at all. It is now the arrow
    # in the title bar, and it is the only one.
    from nowertransfer.ui.widgets import IconButton

    view = ui.open(screen, language=language, size=SIZES[1])
    back = view.back_button

    assert isinstance(back, IconButton)
    assert back.winfo_ismapped(), f"{screen} [{language}]: back button not placed"
    assert back.winfo_height() >= MIN_VISIBLE_PX, (
        f"{screen} [{language}]: back button is {back.winfo_height()}px high"
    )
    assert back.winfo_width() >= MIN_VISIBLE_PX


@pytest.mark.parametrize("screen", ["send", "receive", "settings"])
def test_no_screen_offers_two_ways_back(ui, screen):
    # The footer link said the same thing as the arrow above it.
    view = ui.open(screen, size=SIZES[1])
    back = ui.window.t("nav.back")
    duplicates = [
        child
        for child in view.winfo_children()
        if isinstance(child, ctk.CTkButton) and child.cget("text") == back
    ]
    assert not duplicates, f"{screen} still has a second back button"


def test_a_selection_from_the_command_line_opens_the_send_screen(ui, tmp_path):
    # What the Explorer menu does: start the app with a path. It has
    # to land on the screen that can act on it, already holding it.
    # Through open_first_screen rather than a second MainWindow: Tk
    # gives out only a handful of interpreters per process, and this
    # file already leans on that by sharing one window.
    from nowertransfer.ui.views.home import HomeView
    from nowertransfer.ui.views.send import SendView

    chosen = tmp_path / "from-explorer.txt"
    chosen.write_text("x", encoding="utf-8")

    ui.open("home")
    ui.window.open_first_screen([chosen])
    settle(ui.window)

    assert isinstance(ui.window._view, SendView)
    assert ui.window.send_paths == [chosen]

    # And without a selection it lands where it always did.
    ui.window.send_paths = []
    ui.window.open_first_screen(None)
    settle(ui.window)
    assert isinstance(ui.window._view, HomeView)


@pytest.mark.parametrize("croc_missing", [False, True])
@pytest.mark.parametrize("configured", [True, False])
def test_a_newer_release_is_announced_on_the_start_screen(
    ui, monkeypatch, croc_missing, configured
):
    # Every state the start screen has, because the notice does not
    # depend on any of them: an update is worth knowing about whether
    # or not this copy can transfer anything today. The first version
    # of this sat in the "all is well" branch and passed here only
    # because a croc binary happens to exist in a checkout - CI has
    # none, took the blocker branch, and went red.
    from nowertransfer.updates import Release

    if croc_missing:
        monkeypatch.setattr(ui.window, "croc_path", None)
    ui.window.newer_release = Release("9.9.9", "https://example.com/r")
    try:
        view = ui.open("home", configured=configured)
        shown = [
            child for child in view.winfo_children() if "9.9.9" in _all_text(child)
        ]
        assert shown, "the notice is not on the screen"
        assert not ui.collapsed(view)
    finally:
        ui.window.newer_release = None


def test_nothing_is_announced_without_a_newer_release(ui):
    ui.window.newer_release = None
    view = ui.open("home")
    assert "9.9.9" not in _all_text(view)


def _all_text(widget) -> str:
    import contextlib

    texts = []
    with contextlib.suppress(Exception):  # not every widget has text
        texts.append(str(widget.cget("text")))
    for child in widget.winfo_children():
        texts.append(_all_text(child))
    return " ".join(texts)


def test_the_update_check_can_be_switched_off(ui, tmp_path, monkeypatch):
    # It contacts GitHub, so it has to be refusable.
    from nowertransfer import config

    monkeypatch.setattr(config, "user_config_path", lambda: tmp_path / "config.toml")

    view = ui.open("settings")
    assert view._update_check.get(), "should start switched on"
    view._update_check.deselect()
    view._save()
    settle(ui.window)

    assert config.load_settings().checks_for_updates is False


def test_saving_settings_leaves_no_background_check_running(ui, tmp_path, monkeypatch):
    # Measured: saving calls reload_settings, which starts a relay
    # check on a thread and schedules a poll to collect it. The answer
    # then arrived inside a later test, overwrote the state that test
    # had set by hand, and repainted the dot under it - red where the
    # test had asked for gold. It failed on one runner and not the
    # other, which is what a race looks like from outside.
    from nowertransfer import config

    monkeypatch.setattr(config, "user_config_path", lambda: tmp_path / "config.toml")

    ui.window.relay_reachable = True
    try:
        view = ui.open("settings")
        view._save()
        settle(ui.window)

        assert ui.window._relay_job is None, "a poll is still scheduled"
        assert ui.window.relay_reachable is True, "something answered for the relay"
    finally:
        ui.window.relay_reachable = None


@pytest.mark.parametrize(
    ("reachable", "expect_gold"),
    [(True, True), (False, False), (None, False)],
)
def test_the_relay_dot_says_what_the_relay_is_doing(ui, reachable, expect_gold):
    # It used to be gold whatever the relay was doing, which reads as
    # "all well" even when nothing is listening.
    from nowertransfer.ui.theme import COLORS

    ui.window.relay_reachable = reachable
    try:
        view = ui.open("home")
        # The relay dot by name, not the first StatusDot on the
        # screen: the update notice is one too, it is packed above
        # this one, and it is always gold.
        colour = view._relay_dot._dot.cget("fg_color")
    finally:
        ui.window.relay_reachable = None

    assert (colour == COLORS.gold) is expect_gold, colour
    if reachable is False:
        assert colour == COLORS.error


def test_the_public_relay_says_it_is_unchecked_rather_than_looking_broken(ui):
    # Public mode never runs the check - croc holds the address, so
    # there is nothing of ours to reach - and the dot was left at the
    # same faint grey that means "still checking". Next to a relay
    # that answers fine when tested by hand, that reads as a fault.
    from nowertransfer.ui.theme import COLORS

    view = ui.open("home", language="en", public=True)
    dot = view._relay_dot

    assert "not tested" in dot._label.cget("text")
    assert dot._dot.cget("fg_color") not in (COLORS.error, COLORS.gold, COLORS.faint)


def test_the_public_relay_is_named_once_not_twice(ui):
    # The footer used to print the mode beside the dot as if it were
    # an address; with the dot naming it too that was the same words
    # twice in one strip.
    view = ui.open("home", language="en", public=True)
    labels = [
        child.cget("text")
        for child in _descendants(view)
        if isinstance(child, ctk.CTkLabel) and "public relay" in str(child.cget("text"))
    ]

    assert len(labels) == 1, labels


def test_an_own_relay_still_shows_its_address(ui):
    view = ui.open("home", language="en")
    shown = [
        child.cget("text")
        for child in _descendants(view)
        if isinstance(child, ctk.CTkLabel)
    ]

    assert any("relay.example.com" in str(text) for text in shown), shown


def _descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _descendants(child)


@pytest.mark.parametrize("key", ["<Return>", "<space>"])
@pytest.mark.parametrize(("index", "expected"), [(0, "SendView"), (1, "ReceiveView")])
def test_the_start_screen_can_be_driven_from_the_keyboard(ui, key, index, expected):
    # Before this the app could not be used without a mouse at all:
    # the role cards are frames, which are not focus stops, so Tab
    # reached only the settings link in the footer.
    view = ui.open("home")
    stop = view._focus_stops[index]

    stop.focus_set()
    settle(ui.window)
    stop.event_generate(key)
    settle(ui.window)

    assert type(ui.window._view).__name__ == expected


def test_the_cards_are_focus_stops_in_reading_order(ui):
    view = ui.open("home")
    first, second = view._focus_stops

    assert first.cget("takefocus")
    assert second.cget("takefocus")
    # Tab goes from one to the other rather than past them both.
    assert first.tk_focusNext() is second


def test_the_focused_card_looks_focused(ui):
    # A focus stop nobody can see is no better than none at all.
    from nowertransfer.ui.theme import COLORS

    view = ui.open("home")
    # Tk only delivers FocusIn while the toplevel is the active
    # window, which is exactly the case a user is ever in - and
    # without forcing it the test depends on whatever else happens to
    # hold the desktop's focus.
    ui.window.focus_force()
    settle(ui.window)
    first, second = view._focus_stops

    first.focus_set()
    settle(ui.window)
    assert first.master.cget("border_width") == 2
    assert first.master.cget("border_color") == COLORS.gold

    second.focus_set()
    settle(ui.window)
    assert first.master.cget("border_width") == 1, "the ring did not move"
    assert second.master.cget("border_width") == 2


@pytest.mark.parametrize(
    ("clipboard", "filled"),
    [
        ("falke-wolke-tiger-nebel-quarz-83", True),
        ("  FALKE-WOLKE-TIGER-NEBEL-QUARZ-83 ", True),
        # Everything that is not unmistakably one of ours stays out of
        # the field: putting the wrong thing in front of someone is
        # worse than making them paste it.
        ("have a look at this please", False),
        ("https://example.com/holiday.zip", False),
        ("alpha-bravo-charlie-delta-echo-83", False),
        ("", False),
    ],
)
def test_the_receive_field_only_takes_a_certain_code(ui, clipboard, filled):
    ui.window.clipboard_clear()
    if clipboard:
        ui.window.clipboard_append(clipboard)
    settle(ui.window)

    view = ui.open("receive")

    got = view._code_entry.get()
    assert bool(got) is filled, f"clipboard {clipboard!r} produced {got!r}"
    if filled:
        assert got == clipboard.strip().lower()


def test_a_resumable_receive_warns_that_the_file_is_not_finished(ui, tmp_path):
    # croc pre-allocates the destination at full size - measured, a
    # cancelled 60 MB receive leaves 60,000,000 bytes on disk - so an
    # unfinished file is indistinguishable from a whole one in
    # Explorer. Only this line says otherwise.
    from nowertransfer import session
    from nowertransfer.ui.views import home as home_view

    target = tmp_path / "downloads"
    target.mkdir()
    stored = session.ReceiveSession("falke-wolke-tiger-nebel-quarz-83", str(target))
    monkey = pytest.MonkeyPatch()
    monkey.setattr(home_view, "unfinished", lambda: [stored])
    try:
        view = ui.open("home", language="en")
        shown = _all_text(view)
        assert stored.code in shown
        assert "not" in shown and "complete" in shown, shown
        assert str(target) in shown
        assert not ui.collapsed(view)
    finally:
        monkey.undo()


def test_a_resumable_send_says_nothing_about_an_unfinished_file(ui, tmp_path):
    # The warning is about the receiving side's pre-allocated file;
    # the sender's own files are untouched.
    from nowertransfer import session
    from nowertransfer.ui.views import home as home_view

    payload = tmp_path / "holiday.zip"
    payload.write_text("x", encoding="utf-8")
    stored = session.SendSession("falke-wolke-tiger-nebel-quarz-83", [str(payload)])
    monkey = pytest.MonkeyPatch()
    monkey.setattr(home_view, "unfinished", lambda: [stored])
    try:
        view = ui.open("home", language="en")
        shown = _all_text(view)
        assert stored.code in shown
        assert "complete" not in shown, shown
    finally:
        monkey.undo()


def _fake_transfers(count, tmp_path):
    from nowertransfer.session import ReceiveSession, SendSession

    made = []
    for index in range(count):
        payload = tmp_path / f"file{index}.bin"
        payload.write_text("x", encoding="utf-8")
        code = f"falke-wolke-tiger-nebel-quarz-{index:02d}"
        made.append(
            ReceiveSession(code, str(tmp_path))
            if index % 2
            else SendSession(code, [str(payload)])
        )
    return made


@pytest.mark.parametrize("count", [1, 2, 3, 4, 9])
def test_every_unfinished_transfer_is_offered(ui, tmp_path, monkeypatch, count):
    # One transfer used to replace another: starting a second meant
    # the first was forgotten, though croc can carry on with either.
    from nowertransfer.ui.views import home as home_view

    transfers = _fake_transfers(count, tmp_path)
    monkeypatch.setattr(home_view, "unfinished", lambda: transfers)

    view = ui.open("home")
    shown = _all_text(view)

    for transfer in transfers:
        assert transfer.code in shown, f"{transfer.code} is missing"
    assert not ui.collapsed(view)


def test_a_long_list_scrolls_rather_than_growing(ui, tmp_path, monkeypatch):
    # Without this the rows push the footer off the bottom of the
    # window, which is the failure the layout tests exist to catch.
    from nowertransfer.ui.views import home as home_view

    monkeypatch.setattr(home_view, "unfinished", lambda: _fake_transfers(12, tmp_path))

    view = ui.open("home", size=SIZES[1])

    # Searched through the whole tree: CustomTkinter puts a
    # CTkScrollableFrame inside a frame of its own, so it is never a
    # direct child of what it was packed into.
    boxes = [
        widget
        for widget in _descendants(view)
        if isinstance(widget, ctk.CTkScrollableFrame)
    ]
    assert boxes, "twelve transfers should have gone into a scrolling box"

    # The scrollable frame itself is the content and grows with it;
    # what must stay capped is the box the screen actually holds, so
    # walk up to the widget the view owns.
    container = boxes[0]
    while container.master is not view:
        container = container.master
    assert container.winfo_height() < 300, container.winfo_height()
    assert not ui.collapsed(view)


@pytest.mark.parametrize("index", [0, 1, 2])
def test_opening_a_row_resumes_that_transfer_and_no_other(
    ui, tmp_path, monkeypatch, index
):
    # The point of the list is picking one out of several, so the row
    # has to carry its own transfer rather than the newest or the last
    # one built - the mistake a loop over widgets invites.
    from nowertransfer.ui.views import home as home_view

    transfers = _fake_transfers(3, tmp_path)
    monkeypatch.setattr(home_view, "unfinished", lambda: transfers)

    view = ui.open("home")
    label = ui.window.t("home.resume_open")
    buttons = [
        widget
        for widget in _descendants(view)
        if isinstance(widget, ctk.CTkButton) and widget.cget("text") == label
    ]
    assert len(buttons) == 3, f"{len(buttons)} open buttons for 3 transfers"

    buttons[index].invoke()
    settle(ui.window)

    wanted = transfers[index]
    opened = ui.window._view
    if isinstance(wanted, home_view.ReceiveSession):
        assert type(opened).__name__ == "ReceiveView"
        assert opened._code_entry.get() == wanted.code
        assert str(ui.window.receive_dir) == wanted.target
    else:
        assert type(opened).__name__ == "SendView"
        assert ui.window.send_code == wanted.code
        assert [str(p) for p in ui.window.send_paths] == wanted.paths


def test_a_short_list_does_not_scroll(ui, tmp_path, monkeypatch):
    from nowertransfer.ui.views import home as home_view

    monkeypatch.setattr(home_view, "unfinished", lambda: _fake_transfers(2, tmp_path))

    view = ui.open("home")

    assert not [
        widget
        for widget in _descendants(view)
        if isinstance(widget, ctk.CTkScrollableFrame)
    ]


def test_the_role_cards_sit_under_the_header(ui):
    # They used to float in the middle of the window, because their
    # row took the spare height. The header, the cards and the resume
    # strip belong together at the top; the gap goes at the bottom.
    view = ui.open("home")
    header, cards = view.winfo_children()[0], view.winfo_children()[1]

    gap = cards.winfo_y() - (header.winfo_y() + header.winfo_height())
    assert 0 < gap < 40, f"{gap}px between the header and the cards"


def test_the_first_run_screen_builds(ui):
    view = ui.open("home", configured=False)
    assert not ui.collapsed(view)


@pytest.mark.parametrize("screen", SCREENS)
def test_building_a_screen_warns_about_nothing(ui, screen):
    # The start screen used to hand CTkLabel a tkinter.PhotoImage,
    # which warns on every run and does not scale on a HiDPI display.
    # A warning printed at every start is one nobody reads.
    import warnings

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        ui.open(screen)

    assert not caught, [f"{w.category.__name__}: {w.message}" for w in caught]


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

    assert session.unfinished() == []


def test_the_code_on_screen_is_the_one_that_will_be_sent(ui):
    ui.window.send_code = codes.generate_code()
    view = ui.open("send")
    assert view._code_label.cget("text") == ui.window.send_code


# ----------------------------------------------------------------------
#  The window icon
# ----------------------------------------------------------------------
@pytest.mark.skipif(sys.platform != "win32", reason="Win32 icon slots")
def test_the_window_keeps_our_icon_at_both_sizes(ui):
    # Two ways this broke. Tk's iconbitmap installs one image for every
    # slot, so the 16-pixel slot got a 32-pixel image squeezed into it.
    # And CustomTkinter installs *its* icon 200ms after start unless
    # iconbitmap has been called - which the Win32 fix alone did not
    # do, so the taskbar showed CustomTkinter's blue square instead.
    import ctypes
    from ctypes import c_uint, c_void_p, wintypes

    user32 = ctypes.windll.user32
    user32.SendMessageW.restype = c_void_p
    user32.SendMessageW.argtypes = [c_void_p, c_uint, c_void_p, c_void_p]
    user32.GetAncestor.restype = c_void_p
    user32.GetAncestor.argtypes = [c_void_p, c_uint]

    class ICONINFO(ctypes.Structure):
        _fields_ = [
            ("fIcon", wintypes.BOOL),
            ("xHotspot", wintypes.DWORD),
            ("yHotspot", wintypes.DWORD),
            ("hbmMask", c_void_p),
            ("hbmColor", c_void_p),
        ]

    class BITMAP(ctypes.Structure):
        _fields_ = [
            ("bmType", wintypes.LONG),
            ("bmWidth", wintypes.LONG),
            ("bmHeight", wintypes.LONG),
            ("bmWidthBytes", wintypes.LONG),
            ("bmPlanes", wintypes.WORD),
            ("bmBitsPixel", wintypes.WORD),
            ("bmBits", c_void_p),
        ]

    user32.GetIconInfo.argtypes = [c_void_p, ctypes.POINTER(ICONINFO)]
    ctypes.windll.gdi32.GetObjectW.argtypes = [c_void_p, ctypes.c_int, c_void_p]

    def width_of(handle):
        info = ICONINFO()
        assert handle, "no icon installed at all"
        assert user32.GetIconInfo(handle, ctypes.byref(info))
        bitmap = BITMAP()
        ctypes.windll.gdi32.GetObjectW(
            info.hbmColor, ctypes.sizeof(BITMAP), ctypes.byref(bitmap)
        )
        for handle_ in (info.hbmColor, info.hbmMask):
            if handle_:
                ctypes.windll.gdi32.DeleteObject(c_void_p(handle_))
        return bitmap.bmWidth

    # Past CustomTkinter's 200ms timer, so this is the settled state.
    ui.window.after(260, ui.window.quit)
    ui.window.mainloop()

    hwnd = user32.GetAncestor(c_void_p(ui.window.winfo_id()), 2)
    wanted = {
        "small": (0, user32.GetSystemMetrics(49)),
        "big": (1, user32.GetSystemMetrics(11)),
    }
    for label, (which, expected) in wanted.items():
        handle = user32.SendMessageW(c_void_p(hwnd), 0x007F, c_void_p(which), None)
        assert width_of(handle) == expected, (
            f"{label} icon is {width_of(handle)}px, Windows asked for {expected}px"
        )


# ----------------------------------------------------------------------
#  Brand fonts
# ----------------------------------------------------------------------
@pytest.mark.skipif(
    sys.platform != "win32", reason="the fonts are registered through GDI"
)
@pytest.mark.parametrize("spec", ["display", "mono", "mono-bold"])
def test_the_bundled_faces_are_the_ones_actually_drawn(ui, spec):
    # Registering a font and selecting it are two different things: ask
    # for a family no file carries and Tk substitutes one without a
    # word. Only Font.actual tells you which face you really got.
    from tkinter import font as tkfont

    from nowertransfer.ui.theme import display, mono

    wanted = {
        "display": display(19),
        "mono": mono(12),
        "mono-bold": mono(19, bold=True),
    }
    family, size, *rest = wanted[spec]
    drawn = tkfont.Font(
        root=ui.window, family=family, size=size, weight=rest[0] if rest else "normal"
    )

    assert drawn.actual("family").lower() == family.lower(), (
        f"asked for {family!r}, Tk drew {drawn.actual('family')!r}"
    )


@pytest.mark.parametrize(
    ("size", "items", "expected"),
    [
        # Both known: the send screen measures them before starting.
        ("2.4 GB", "3", "3 files, 2.4 GB in "),
        # One file is named above already; "1 files" is just wrong.
        ("12 MB", "1", "12 MB in "),
        # The receiving side never learns an item count.
        ("85.8 MB", None, "85.8 MB in "),
        # Nothing reported at all, which a quick transfer manages.
        (None, None, "Done in "),
    ],
)
def test_the_closing_line_uses_only_figures_it_has(ui, size, items, expected):
    from nowertransfer.transfer import EventType, TransferEvent

    # The window is shared across this file, so a selection left by an
    # earlier test would measure itself into the figures.
    ui.window.send_paths = []
    view = ui.open("send", language="en")
    view.enter_running()
    if size is not None:
        view.panel.set_stat("size", size)
    if items is not None:
        view.panel.set_stat("items", items)
    settle(ui.window)

    view.on_transfer_event(TransferEvent(EventType.FINISHED))
    settle(ui.window)

    line = view.footnote.cget("text")
    assert line.startswith(expected), line
    assert "—" not in line, "a placeholder reached the sentence"


def test_the_panel_shows_crocs_speed_and_time_left(ui):
    from nowertransfer.transfer import EventType, TransferEvent

    view = ui.open("send")
    view.enter_running()
    view.on_transfer_event(
        TransferEvent(
            EventType.OUTPUT,
            "sample.bin  28% |#####  | (26/90 MB, 717 kB/s) [34s:1m29s]",
        )
    )
    settle(ui.window)

    shown = view.panel._rate.cget("text")
    assert "717 kB/s" in shown and "1m29s" in shown
    assert view.panel._percent.cget("text") == "28%"


def test_nothing_is_claimed_before_anything_has_moved(ui):
    # croc's first progress line has no rate and reads [0s:0s].
    from nowertransfer.transfer import EventType, TransferEvent

    view = ui.open("receive")
    view.enter_running()
    view.on_transfer_event(
        TransferEvent(EventType.OUTPUT, "probe.bin   0% |  | ( 0 B/400 kB) [0s:0s]")
    )
    settle(ui.window)

    assert view.panel._rate.cget("text") == ""


def test_the_figures_are_cleared_when_the_transfer_stops(ui):
    from nowertransfer.transfer import EventType, TransferEvent

    view = ui.open("send")
    view.enter_running()
    view.on_transfer_event(
        TransferEvent(EventType.OUTPUT, "a.bin  9% |#| (8/90 MB, 717 kB/s) [10s:1m53s]")
    )
    settle(ui.window)
    assert view.panel._rate.cget("text")

    view.on_transfer_event(TransferEvent(EventType.FINISHED))
    settle(ui.window)
    assert view.panel._rate.cget("text") == "", "stale speed left on screen"


# ----------------------------------------------------------------------
#  Saying a transfer is over
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    ("event_type", "should_flash"),
    [("FINISHED", True), ("FAILED", True), ("CANCELLED", False)],
)
def test_the_taskbar_is_flashed_when_nobody_is_watching(
    ui, monkeypatch, event_type, should_flash
):
    from nowertransfer.transfer import EventType, TransferEvent
    from nowertransfer.ui import winicon

    flashed = []
    monkeypatch.setattr(winicon, "is_foreground", lambda _window: False)
    monkeypatch.setattr(winicon, "flash", lambda window: flashed.append(window))

    view = ui.open("send")
    text = "error.no_peer" if event_type == "FAILED" else ""
    view.on_transfer_event(TransferEvent(getattr(EventType, event_type), text))
    settle(ui.window)

    assert bool(flashed) is should_flash


def test_no_flashing_at_a_window_already_in_front(ui, monkeypatch):
    # Flashing the window someone is looking at is just noise.
    from nowertransfer.transfer import EventType, TransferEvent
    from nowertransfer.ui import winicon

    flashed = []
    monkeypatch.setattr(winicon, "is_foreground", lambda _window: True)
    monkeypatch.setattr(winicon, "flash", lambda window: flashed.append(window))

    view = ui.open("send")
    view.on_transfer_event(TransferEvent(EventType.FINISHED))
    settle(ui.window)

    assert not flashed


# ----------------------------------------------------------------------
#  Dropped files
# ----------------------------------------------------------------------
def test_a_tcl_file_list_splits_into_paths(ui):
    # tkdnd hands over one string in Tcl list syntax, so a path with a
    # space in it arrives in braces and must not be split on the space.
    from nowertransfer.ui.dnd import _parse

    paths = _parse(ui.window, "{C:/holiday photos/one.jpg} C:/two.txt")

    assert [p.name for p in paths] == ["one.jpg", "two.txt"]
    assert paths[0].parent.name == "holiday photos"


def test_dropping_files_selects_them(ui, tmp_path):
    view = ui.open("send")
    dropped = tmp_path / "dropped.bin"
    dropped.write_bytes(b"x")

    view._dropped([dropped])
    settle(ui.window)

    assert ui.window.send_paths == [dropped]
    assert dropped.name in view._selection_label.cget("text")


def test_a_drop_during_a_transfer_is_ignored(ui, tmp_path, monkeypatch):
    # Swapping the selection out from under a running croc would send
    # one set of files under a code phrase handed out for another.
    view = ui.open("send")
    ui.window.send_paths = [tmp_path / "chosen"]
    monkeypatch.setattr(type(ui.window), "transfer_running", property(lambda _: True))

    view._dropped([tmp_path / "late"])

    assert ui.window.send_paths == [tmp_path / "chosen"]


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


def test_the_connection_test_uses_what_is_typed_not_what_is_saved(ui, monkeypatch):
    # Otherwise the button would test the old relay while the user
    # looks at the new one and believes the answer applies to it.
    from nowertransfer.relaycheck import RelayCheck, RelayStatus
    from nowertransfer.ui.views import settings as settings_view

    asked = []
    monkeypatch.setattr(
        settings_view,
        "check",
        lambda relay, croc: asked.append(relay) or RelayCheck(RelayStatus.REACHABLE, 5),
    )

    view = ui.open("settings")
    select(view, RelayMode.OWN)
    for field, value in (
        (view._host_entry, "typed-only.example.com:9009"),
        (view._password_entry, "typed-only-password"),
    ):
        field.delete(0, "end")
        field.insert(0, value)

    view._run_check()
    settle(ui.window)

    assert asked, "the check was never run"
    assert asked[0].host == "typed-only.example.com:9009"
    assert asked[0].password == "typed-only-password"


def test_the_connection_test_does_not_claim_the_password_is_right(ui, monkeypatch):
    # Measured against a real relay: croc names a refused relay
    # password sometimes at once and sometimes never, so a clean run
    # proves the address and nothing more.
    from nowertransfer.relaycheck import RelayCheck, RelayStatus
    from nowertransfer.ui.views import settings as settings_view

    monkeypatch.setattr(
        settings_view, "check", lambda relay, croc: RelayCheck(RelayStatus.REACHABLE, 7)
    )
    view = ui.open("settings", language="en")
    view._run_check()
    settle(ui.window)

    said = view._check_status._label.cget("text").lower()
    assert "password not checked" in said, said


@pytest.mark.parametrize("mode", list(RelayMode))
def test_the_chosen_relay_mode_is_readable(ui, mode):
    # The chosen segment is gold. CTkSegmentedButton paints every
    # segment's label the same colour, so the choice was near-white on
    # gold - there, but not readable.
    from nowertransfer.ui.theme import COLORS

    view = ui.open("settings")
    select(view, mode)
    settle(ui.window)

    for label, button in view._mode._buttons_dict.items():
        chosen = label == view._mode_labels[mode]
        expected = COLORS.ink if chosen else COLORS.text
        assert button.cget("text_color") == expected, (
            f"{label!r} (chosen={chosen}) is {button.cget('text_color')}"
        )


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
