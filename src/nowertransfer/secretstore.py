"""Encrypting the secrets this app keeps on disk.

Two things end up in files on the user's machine: the relay password they
typed into the settings screen, and the code phrase of an interrupted send
that the resume feature needs. Both are stored through this module.

On Windows that means DPAPI (``CryptProtectData``), the same mechanism
browsers use for saved passwords. The ciphertext is bound to the Windows
user account, so:

* another account on the same machine cannot read it,
* a copy that leaves the machine - a backup, a synced folder, a stolen
  disk - is useless.

It does **not** protect against code already running as that user. Nothing
stored locally can, and claiming otherwise would be worse than plain text
because it invites misplaced trust.

Elsewhere there is no keystore reachable without a dependency, so values
are stored unencrypted and the file is made owner-readable instead. The
stored form says which of the two it is, so a file never has to be guessed
at.

Deliberately *not* stored through this module: the relay password baked
into a build. A binary has to decrypt its own configuration unattended, so
any key would travel with it. That one is obfuscation, not encryption, and
is documented as readable.
"""

from __future__ import annotations

import base64
import sys

#: Marks a value encrypted with Windows DPAPI.
PREFIX_DPAPI = "dpapi:"
#: Marks a value this platform could not encrypt.
PREFIX_PLAIN = "plain:"

#: Mixed into the DPAPI ciphertext so a blob from another application
#: cannot be dropped into our config file and decrypt successfully.
_ENTROPY = b"NowerTransfer/secret/v1"


def is_encrypting() -> bool:
    """True when secrets written now will actually be encrypted."""
    return sys.platform == "win32"


def protect(secret: str) -> str:
    """Return the on-disk form of ``secret``."""
    if not secret:
        return ""
    if is_encrypting():
        try:
            blob = _dpapi(_crypt32().CryptProtectData, secret.encode("utf-8"))
        except OSError:
            # An unusable DPAPI is not a reason to lose the setting.
            return PREFIX_PLAIN + secret
        return PREFIX_DPAPI + base64.b64encode(blob).decode("ascii")
    return PREFIX_PLAIN + secret


def unprotect(stored: str) -> str:
    """Return the secret behind an on-disk value.

    Returns ``""`` for a value that cannot be decrypted here - a config
    copied from another machine or account, or a corrupted one. A value
    written before this module existed, or typed into the file by hand,
    is returned unchanged.
    """
    if not stored:
        return ""
    if stored.startswith(PREFIX_PLAIN):
        return stored[len(PREFIX_PLAIN) :]
    if not stored.startswith(PREFIX_DPAPI):
        return stored  # hand-written or written by an older version
    if not is_encrypting():
        return ""

    try:
        blob = base64.b64decode(stored[len(PREFIX_DPAPI) :], validate=True)
        return _dpapi(_crypt32().CryptUnprotectData, blob).decode("utf-8")
    except (ValueError, OSError, UnicodeDecodeError):
        return ""


# ----------------------------------------------------------------------
#  Windows DPAPI
# ----------------------------------------------------------------------
def _crypt32():  # pragma: no cover - exercised only on Windows
    import ctypes
    from ctypes import wintypes

    if getattr(_crypt32, "_cache", None) is None:
        library = ctypes.WinDLL("crypt32", use_last_error=True)
        for name in ("CryptProtectData", "CryptUnprotectData"):
            function = getattr(library, name)
            function.argtypes = [
                ctypes.POINTER(_Blob),
                wintypes.LPCWSTR,
                ctypes.POINTER(_Blob),
                ctypes.c_void_p,
                ctypes.c_void_p,
                wintypes.DWORD,
                ctypes.POINTER(_Blob),
            ]
            function.restype = wintypes.BOOL
        _crypt32._cache = library
    return _crypt32._cache


if sys.platform == "win32":  # pragma: no cover - platform specific
    import ctypes
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_char)),
        ]

    def _blob(data: bytes) -> tuple[_Blob, ctypes.Array[ctypes.c_char]]:
        # The buffer is returned alongside the struct: it has to outlive
        # the call, and the struct only holds a borrowed pointer.
        buffer = ctypes.create_string_buffer(data, len(data))
        return (
            _Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))),
            buffer,
        )

    def _dpapi(function, data: bytes) -> bytes:
        blob_in, _keep_in = _blob(data)
        entropy, _keep_entropy = _blob(_ENTROPY)
        blob_out = _Blob()
        ok = function(
            ctypes.byref(blob_in),
            None,
            ctypes.byref(entropy),
            None,
            None,
            0,
            ctypes.byref(blob_out),
        )
        if not ok:
            raise OSError(ctypes.get_last_error(), "DPAPI call failed")
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)

else:  # pragma: no cover - platform specific

    class _Blob:  # placeholder so the module imports everywhere
        pass

    def _dpapi(function, data: bytes) -> bytes:
        raise OSError("DPAPI is only available on Windows")
