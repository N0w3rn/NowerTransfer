"""Give the window the icon sizes Windows actually asks for.

Tk's ``iconbitmap`` installs one image for every purpose. Measured: it
sets a 32-pixel icon as both the large and the small one, so the title
bar - which asks for 16 - gets a downscale, and so does anything else
that wants a size the single image does not have. That is what a
"blurry" icon usually is.

``LoadImageW`` picks the frame matching a requested size out of a
multi-size .ico, so each slot gets the image drawn for it.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import c_int, c_uint, c_void_p
from pathlib import Path

#: Metrics for the two sizes a window advertises.
_SM_CXICON, _SM_CYICON = 11, 12
_SM_CXSMICON, _SM_CYSMICON = 49, 50

_IMAGE_ICON = 1
_LR_LOADFROMFILE = 0x00000010

_WM_SETICON = 0x0080
_ICON_SMALL, _ICON_BIG = 0, 1

_GA_ROOT = 2

#: Handles stay referenced for the life of the process: the window goes
#: on using them, and destroying one would blank the icon.
_keep: list[int] = []


def _win32():
    user32 = ctypes.windll.user32
    user32.LoadImageW.restype = c_void_p
    user32.LoadImageW.argtypes = [
        c_void_p,
        ctypes.c_wchar_p,
        c_uint,
        c_int,
        c_int,
        c_uint,
    ]
    user32.SendMessageW.restype = c_void_p
    user32.SendMessageW.argtypes = [c_void_p, c_uint, c_void_p, c_void_p]
    user32.GetAncestor.restype = c_void_p
    user32.GetAncestor.argtypes = [c_void_p, c_uint]
    return user32


def set_app_id(app_id: str) -> bool:
    """Give the process its own taskbar identity.

    Without one, Windows derives it from the executable, which for a
    one-file build is a temporary host process - so the taskbar button
    can end up with someone else's icon.
    """
    if sys.platform != "win32":
        return False
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except (AttributeError, OSError):
        return False
    return True


def apply_icon(window, icon: Path) -> bool:
    """Install the .ico at both sizes. False if the platform will not."""
    if sys.platform != "win32":
        return False
    try:
        user32 = _win32()
        handle = user32.GetAncestor(c_void_p(window.winfo_id()), _GA_ROOT)
        if not handle:
            return False

        applied = False
        for which, (cx_metric, cy_metric) in (
            (_ICON_BIG, (_SM_CXICON, _SM_CYICON)),
            (_ICON_SMALL, (_SM_CXSMICON, _SM_CYSMICON)),
        ):
            loaded = user32.LoadImageW(
                None,
                str(icon),
                _IMAGE_ICON,
                user32.GetSystemMetrics(cx_metric),
                user32.GetSystemMetrics(cy_metric),
                _LR_LOADFROMFILE,
            )
            if not loaded:
                continue
            _keep.append(loaded)
            user32.SendMessageW(
                c_void_p(handle), _WM_SETICON, c_void_p(which), c_void_p(loaded)
            )
            applied = True
        return applied
    except (AttributeError, OSError, ValueError):
        return False
