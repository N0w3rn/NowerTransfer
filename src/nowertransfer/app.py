"""Application entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import APP_NAME, __version__
from .config import load_settings
from .i18n import detect_language

#: Vendor.Product, the form Windows expects for a taskbar identity.
APP_ID = f"Nowenr.{APP_NAME}"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="nowertransfer",
        description=f"{APP_NAME} - send files through your own croc relay.",
    )
    parser.add_argument(
        "--version", action="version", version=f"{APP_NAME} {__version__}"
    )
    return parser.parse_args(argv)


def preselected(argv: list[str] | None = None) -> list[Path]:
    """Files and folders handed to us on the command line.

    This is how "Send with NowerTransfer" in the Explorer menu works:
    Windows starts the app with the selected path as an argument.

    Deliberately not argparse. A windowed build has no stdout, so
    argparse cannot run at all there - and that build is precisely the
    one Explorer starts. Anything that is not a flag and does exist is
    taken as a selection; anything else is ignored rather than
    reported, because there is nowhere to report it to.
    """
    arguments = sys.argv[1:] if argv is None else argv
    chosen = []
    for argument in arguments:
        if argument.startswith("-"):
            continue
        path = Path(argument)
        if path.exists():
            chosen.append(path)
    return chosen


def main(argv: list[str] | None = None) -> int:
    # A windowed build has no stdout, and argparse writes --version and
    # usage errors there. Nothing on the command line could be reported
    # to the user in that case, so skip parsing rather than crash.
    if sys.stdout is not None:
        _parse_args(argv)

    settings = load_settings()
    if not settings.language:
        settings.language = detect_language()

    # Imported late so --version works even without a display attached.
    from .ui.main_window import MainWindow
    from .ui.winicon import set_app_id

    # Before the window exists: Windows reads it when the taskbar
    # button is created. Otherwise a one-file build is identified by
    # its temporary host process, not by us.
    set_app_id(APP_ID)

    MainWindow(settings, preselect=preselected(argv)).mainloop()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
