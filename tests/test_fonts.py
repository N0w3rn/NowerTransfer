"""The bundled brand faces.

The trap these guard: a font file carries its own family name, and
Windows enumerates fonts by that name. IBM Plex Mono's Medium weight
calls itself "IBM Plex Mono Medm", so bundling it and asking Tk for
"IBM Plex Mono" registers a font nobody can then select - the app
renders in a substitute and says nothing.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from nowertransfer.ui.fonts import BUNDLED, font_dir

#: name table entry for the family, and for the licence we must ship.
_FAMILY_ID = 1
_SUBFAMILY_ID = 2

CASES = [(family, name) for family, names in BUNDLED.items() for name in names]


def read_names(path: Path) -> dict[int, str]:
    """Family and subfamily out of a TrueType name table."""
    data = path.read_bytes()
    assert data[:4] == b"\x00\x01\x00\x00", f"{path.name} is not a TrueType font"

    count = struct.unpack(">H", data[4:6])[0]
    tables = {}
    for index in range(count):
        offset = 12 + index * 16
        tag, _, start, length = struct.unpack(">4sIII", data[offset : offset + 16])
        tables[tag] = (start, length)

    start = tables[b"name"][0]
    _, entries, strings = struct.unpack(">HHH", data[start : start + 6])
    storage = start + strings

    found: dict[int, str] = {}
    for index in range(entries):
        offset = start + 6 + index * 12
        platform, _, _, name_id, length, at = struct.unpack(
            ">HHHHHH", data[offset : offset + 12]
        )
        if name_id in found:
            continue
        raw = data[storage + at : storage + at + length]
        found[name_id] = raw.decode(
            "utf-16-be" if platform == 3 else "latin-1", "replace"
        )
    return found


@pytest.mark.parametrize(("family", "filename"), CASES)
def test_every_bundled_font_is_present(family, filename):
    assert (font_dir() / filename).is_file(), (
        f"{filename} is missing, so {family} falls back to a system face"
    )


@pytest.mark.parametrize(("family", "filename"), CASES)
def test_a_font_file_carries_the_family_it_is_filed_under(family, filename):
    names = read_names(font_dir() / filename)
    assert names[_FAMILY_ID] == family, (
        f"{filename} calls itself {names[_FAMILY_ID]!r}, but it is bundled as "
        f"{family!r}; Windows would register it and Tk would never find it"
    )


def test_the_monospace_face_ships_both_weights():
    # mono() is used plain and bold; a missing weight is synthesised by
    # smearing the regular one, which looks wrong at the code phrase's
    # size.
    weights = {
        read_names(font_dir() / name)[_SUBFAMILY_ID]
        for name in BUNDLED["IBM Plex Mono"]
    }
    assert weights == {"Regular", "Bold"}


def test_the_licences_travel_with_the_fonts():
    # Both faces are OFL-1.1, which requires the licence to ship.
    licences = sorted(path.name for path in font_dir().glob("*OFL*.txt"))
    assert len(licences) == 2, f"expected both licence files, found {licences}"
    for name in licences:
        assert (
            "SIL OPEN FONT LICENSE"
            in (font_dir() / name).read_text(encoding="utf-8").upper()
        )
