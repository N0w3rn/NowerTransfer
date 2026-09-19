"""Application entry point."""

from __future__ import annotations

import argparse
import sys

from . import APP_NAME, __version__
from .config import load_settings
from .i18n import detect_language


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="nowertransfer",
        description=f"{APP_NAME} - send files through your own croc relay.",
    )
    parser.add_argument(
        "--version", action="version", version=f"{APP_NAME} {__version__}"
    )
    return parser.parse_args(argv)


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

    MainWindow(settings).mainloop()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
