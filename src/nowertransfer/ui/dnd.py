"""Dropping files onto a window, where the platform allows it.

tkdnd is a Tcl extension. tkinterdnd2 ships prebuilt copies of it and
can load one into a Tk root somebody else created, which is what
CustomTkinter hands us. Neither is required: if the extension will not
load, the caller is told so and offers a file dialog instead.
"""

from __future__ import annotations

import tkinter
from collections.abc import Callable, Iterator
from contextlib import suppress
from pathlib import Path

#: tkdnd's name for a list of filenames, as Explorer and Finder send it.
FILES = "DND_Files"

#: Crossing from one registered child to the next fires a leave before
#: the next enter. Clearing the highlight a beat later, and cancelling
#: that when the next enter arrives, keeps the zone from flickering.
_LEAVE_DELAY_MS = 70

_loaded: bool | None = None


def enable(root: tkinter.Misc) -> bool:
    """Load tkdnd into this root. Says whether drops will work."""
    global _loaded
    if _loaded is None:
        _loaded = _load(root)
    return _loaded


def _load(root: tkinter.Misc) -> bool:
    try:
        from tkinterdnd2 import TkinterDnD
    except ImportError:
        return False
    try:
        TkinterDnD.require(root)
    except (tkinter.TclError, RuntimeError, OSError):
        return False
    return True


def accept_files(
    widget: tkinter.Misc,
    on_drop: Callable[[list[Path]], None],
    on_enter: Callable[[], None] | None = None,
    on_leave: Callable[[], None] | None = None,
) -> bool:
    """Take dropped files on this widget and everything inside it.

    Children have to be registered too: whichever one is under the
    pointer is the one tkdnd reports the drop to.
    """
    if not enable(widget.winfo_toplevel()):
        return False

    pending: list[str] = []

    def entered(_event: tkinter.Event) -> str:
        while pending:
            with suppress(ValueError, tkinter.TclError):
                widget.after_cancel(pending.pop())
        if on_enter:
            on_enter()
        return "copy"

    def left(_event: tkinter.Event) -> None:
        if on_leave:
            pending.append(widget.after(_LEAVE_DELAY_MS, _settle, pending, on_leave))

    def dropped(event: tkinter.Event) -> str:
        if on_leave:
            on_leave()
        paths = _parse(widget, getattr(event, "data", ""))
        if paths:
            on_drop(paths)
        return "copy"

    registered = False
    for target in _tree(widget):
        with suppress(tkinter.TclError, AttributeError):
            target.drop_target_register(FILES)
            target.dnd_bind("<<DropEnter>>", entered)
            target.dnd_bind("<<DropLeave>>", left)
            target.dnd_bind("<<Drop>>", dropped)
            registered = True
    return registered


def _settle(pending: list[str], on_leave: Callable[[], None]) -> None:
    pending.clear()
    on_leave()


def _tree(widget: tkinter.Misc) -> Iterator[tkinter.Misc]:
    yield widget
    for child in widget.winfo_children():
        yield from _tree(child)


def _parse(widget: tkinter.Misc, data: str) -> list[Path]:
    """tkdnd hands over a Tcl list, so Tcl is what should split it."""
    if not data:
        return []
    try:
        names = widget.tk.splitlist(data)
    except tkinter.TclError:
        names = (data,)
    return [Path(name) for name in names if name]
