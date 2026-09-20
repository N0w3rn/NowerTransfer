"""Restricting a file or directory to the account that made it.

``chmod(0o600)`` is the usual way and it works on Linux and macOS. On
Windows it does not: Python maps it onto the read-only attribute and
leaves the access control list alone, so a file written that way stays
readable by every other account the folder is shared with. Measured on
a real machine: a second local account had full control of the app's
settings directory.

So on Windows the list is rewritten instead - inheritance off, one
entry for the current user's SID and nothing else.
"""

from __future__ import annotations

import ctypes
import subprocess
import sys
from contextlib import suppress
from ctypes import c_void_p, wintypes
from pathlib import Path

_TOKEN_QUERY = 0x0008
_TOKEN_USER = 1

_NO_WINDOW = (
    getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
)


def restrict_to_owner(path: Path) -> bool:
    """Let only the current account read ``path``. False if it could not."""
    if sys.platform != "win32":
        # 0o700 on a directory: 0o600 would make it untraversable.
        mode = 0o700 if path.is_dir() else 0o600
        with suppress(OSError, NotImplementedError):
            path.chmod(mode)
            return True
        return False

    sid = current_user_sid()
    if sid is None:
        return False
    # (OI)(CI) makes a directory's entry apply to what is created in it,
    # which is what protects the files this app writes later.
    rights = "(OI)(CI)(F)" if path.is_dir() else "(F)"
    try:
        result = subprocess.run(
            [
                "icacls",
                str(path),
                "/inheritance:r",
                "/grant:r",
                f"*{sid}:{rights}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=_NO_WINDOW,
            check=False,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def current_user_sid() -> str | None:
    """The SID of the account this process runs as, as a string."""
    if sys.platform != "win32":
        return None
    try:
        advapi32 = ctypes.windll.advapi32
        kernel32 = ctypes.windll.kernel32
        advapi32.OpenProcessToken.argtypes = [
            c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(c_void_p),
        ]
        advapi32.GetTokenInformation.argtypes = [
            c_void_p,
            ctypes.c_int,
            c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        advapi32.ConvertSidToStringSidW.argtypes = [
            c_void_p,
            ctypes.POINTER(ctypes.c_wchar_p),
        ]
        kernel32.GetCurrentProcess.restype = c_void_p
        kernel32.LocalFree.argtypes = [c_void_p]

        token = c_void_p()
        if not advapi32.OpenProcessToken(
            kernel32.GetCurrentProcess(), _TOKEN_QUERY, ctypes.byref(token)
        ):
            return None
        try:
            size = wintypes.DWORD()
            advapi32.GetTokenInformation(
                token, _TOKEN_USER, None, 0, ctypes.byref(size)
            )
            buffer = ctypes.create_string_buffer(size.value)
            if not advapi32.GetTokenInformation(
                token, _TOKEN_USER, buffer, size, ctypes.byref(size)
            ):
                return None

            # TOKEN_USER begins with a SID_AND_ATTRIBUTES, whose first
            # member is the pointer we want.
            sid = ctypes.cast(buffer, ctypes.POINTER(c_void_p)).contents
            text = ctypes.c_wchar_p()
            if not advapi32.ConvertSidToStringSidW(sid, ctypes.byref(text)):
                return None
            try:
                return text.value
            finally:
                kernel32.LocalFree(text)
        finally:
            kernel32.CloseHandle(token)
    except (AttributeError, OSError, ValueError):
        return None
