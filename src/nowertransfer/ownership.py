"""Restricting a file or directory to the account that made it.

``chmod(0o600)`` is the usual way and it works on Linux and macOS. On
Windows it does not: Python maps it onto the read-only attribute and
leaves the access control list alone, so a file written that way stays
readable by every other account the folder is shared with. Measured on
a real machine: a second local account had full control of the app's
settings directory.

Windows therefore gets a new list rather than an edited one. Editing
is what ``icacls /inheritance:r`` does, and it only drops entries that
were *inherited* - explicit entries for SYSTEM or Administrators
survive it, which is how a first attempt at this passed on one machine
and left three extra accounts in place on another. ``SetNamedSecurityInfo``
with a protected DACL replaces the list outright, so what is granted is
exactly what is written here and nothing else.
"""

from __future__ import annotations

import ctypes
import sys
from contextlib import suppress
from ctypes import c_void_p, wintypes
from pathlib import Path

_TOKEN_QUERY = 0x0008
_TOKEN_USER = 1

_SE_FILE_OBJECT = 1
_DACL_SECURITY_INFORMATION = 0x00000004
#: Stops the parent's entries from flowing back in.
_PROTECTED_DACL_SECURITY_INFORMATION = 0x80000000

_ACL_REVISION = 2
_FILE_ALL_ACCESS = 0x001F01FF
_OBJECT_INHERIT_ACE = 0x1
_CONTAINER_INHERIT_ACE = 0x2

#: One ACE never needs this much, and over-allocating costs nothing.
_ACL_BYTES = 1024

_ERROR_SUCCESS = 0


def restrict_to_owner(path: Path) -> bool:
    """Let only the current account reach ``path``. False if it could not."""
    if sys.platform != "win32":
        # 0o700 on a directory: 0o600 would make it untraversable.
        mode = 0o700 if path.is_dir() else 0o600
        with suppress(OSError, NotImplementedError):
            path.chmod(mode)
            return True
        return False
    return _set_sole_owner(path)


# ----------------------------------------------------------------------
#  Windows
# ----------------------------------------------------------------------
if sys.platform == "win32":  # pragma: no cover - platform specific
    from contextlib import contextmanager

    @contextmanager
    def _token_sid():
        """The current process's user SID, valid inside the block."""
        advapi32 = ctypes.windll.advapi32
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = c_void_p
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

        token = c_void_p()
        if not advapi32.OpenProcessToken(
            kernel32.GetCurrentProcess(), _TOKEN_QUERY, ctypes.byref(token)
        ):
            yield None
            return
        try:
            size = wintypes.DWORD()
            advapi32.GetTokenInformation(
                token, _TOKEN_USER, None, 0, ctypes.byref(size)
            )
            buffer = ctypes.create_string_buffer(size.value)
            if not advapi32.GetTokenInformation(
                token, _TOKEN_USER, buffer, size, ctypes.byref(size)
            ):
                yield None
                return
            # TOKEN_USER starts with a SID_AND_ATTRIBUTES, whose first
            # member is the pointer wanted here. The buffer backing it
            # stays alive for the body of the with-block.
            yield ctypes.cast(buffer, ctypes.POINTER(c_void_p)).contents
        finally:
            kernel32.CloseHandle(token)

    def _set_sole_owner(path: Path) -> bool:
        try:
            advapi32 = ctypes.windll.advapi32
            advapi32.InitializeAcl.argtypes = [
                c_void_p,
                wintypes.DWORD,
                wintypes.DWORD,
            ]
            advapi32.AddAccessAllowedAceEx.argtypes = [
                c_void_p,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.DWORD,
                c_void_p,
            ]
            advapi32.SetNamedSecurityInfoW.argtypes = [
                wintypes.LPWSTR,
                ctypes.c_int,
                wintypes.DWORD,
                c_void_p,
                c_void_p,
                c_void_p,
                c_void_p,
            ]
            advapi32.SetNamedSecurityInfoW.restype = wintypes.DWORD

            with _token_sid() as sid:
                if sid is None:
                    return False

                acl = ctypes.create_string_buffer(_ACL_BYTES)
                if not advapi32.InitializeAcl(acl, _ACL_BYTES, _ACL_REVISION):
                    return False

                # A directory passes the entry on to what is created in
                # it, which is how the files written later are covered.
                flags = (
                    _OBJECT_INHERIT_ACE | _CONTAINER_INHERIT_ACE if path.is_dir() else 0
                )
                if not advapi32.AddAccessAllowedAceEx(
                    acl, _ACL_REVISION, flags, _FILE_ALL_ACCESS, sid
                ):
                    return False

                result = advapi32.SetNamedSecurityInfoW(
                    str(path),
                    _SE_FILE_OBJECT,
                    _DACL_SECURITY_INFORMATION | _PROTECTED_DACL_SECURITY_INFORMATION,
                    None,
                    None,
                    acl,
                    None,
                )
                return result == _ERROR_SUCCESS
        except (AttributeError, OSError, ValueError):
            return False

else:  # pragma: no cover - platform specific
    from contextlib import contextmanager

    @contextmanager
    def _token_sid():
        yield None

    def _set_sole_owner(path: Path) -> bool:
        return False
