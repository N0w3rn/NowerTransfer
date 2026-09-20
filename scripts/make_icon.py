#!/usr/bin/env python3
"""Render the in-app logo, and check the icon Windows will use.

``assets/icon.ico`` is artwork, not a build product: it is drawn for
the small sizes, where the full mark has more detail than 24 pixels can
hold. This script never writes it - it only reports which sizes it
carries, because Windows rescales when a size is missing and a
rescaled icon is what looks smeared.

What it does write is ``assets/logo-88.png``, the mark the start screen
draws, rendered from ``assets/logo.png``.

    python scripts/make_icon.py
    python scripts/make_icon.py --add-missing-sizes

The second form fills gaps in the .ico from its own largest frame,
leaving every drawn frame untouched. Redrawing the missing sizes in
an icon editor is better still; this only beats letting Windows
rescale at draw time.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageFilter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS = PROJECT_ROOT / "assets"
SOURCE = ASSETS / "logo.png"
ICON = ASSETS / "icon.ico"
LOGO_88 = ASSETS / "logo-88.png"

#: What the header draws, with room to spare for a scaled display.
LOGO_SIZE = 88

#: 16 and 32 are the classic pair; 20, 24, 40 and 48 are what the
#: taskbar and title bar ask for at 100%, 125% and 150% scaling; the
#: rest cover Explorer's larger views.
WANTED_ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)

#: Below this, downscaling softens the artwork enough to notice.
SHARPEN_BELOW = 64


def trim(image: Image.Image) -> Image.Image:
    """Crop the transparent margin so the mark uses all the pixels."""
    box = image.getbbox()
    return image.crop(box) if box else image


def square(image: Image.Image) -> Image.Image:
    """Pad to a square, so scaling cannot distort it."""
    side = max(image.size)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(image, ((side - image.width) // 2, (side - image.height) // 2))
    return canvas


def render(source: Image.Image, size: int) -> Image.Image:
    scaled = source.resize((size, size), Image.LANCZOS)
    if size < SHARPEN_BELOW:
        # Lanczos leaves small sizes slightly soft; this puts back the
        # edge without the halo a stronger radius would give.
        scaled = scaled.filter(
            ImageFilter.UnsharpMask(radius=0.6, percent=110, threshold=2)
        )
    return scaled


def report_icon() -> None:
    if not ICON.is_file():
        print(f"warning: {ICON.name} is missing")
        return
    with Image.open(ICON) as icon:
        present = {width for width, _ in icon.info.get("sizes", ())}
    missing = [size for size in WANTED_ICON_SIZES if size not in present]
    print(f"{ICON.name}: {', '.join(str(s) for s in sorted(present))}")
    if missing:
        print(
            f"  missing {missing} - Windows will rescale for those, which is "
            f"softer than a frame drawn at the size"
        )


def add_missing_sizes() -> int:
    """Render the sizes the .ico lacks, leaving the drawn ones alone.

    Only ever called with an explicit flag. The .ico is artwork: the
    frames already in it are written back byte for byte, and the gaps
    are filled from the largest one, which still beats Windows
    rescaling at draw time.
    """
    if not ICON.is_file():
        raise SystemExit(f"error: {ICON} is missing")

    frames: dict[int, Image.Image] = {}
    with Image.open(ICON) as icon:
        for width, height in sorted(icon.info.get("sizes", ())):
            icon.size = (width, height)
            icon.load()
            frames[width] = icon.convert("RGBA").copy()

    missing = [size for size in WANTED_ICON_SIZES if size not in frames]
    if not missing:
        print(f"{ICON.name} already has every size")
        return 0

    largest = frames[max(frames)]
    for size in missing:
        frames[size] = render(largest, size)
    print(f"rendered {missing} from the {largest.width}px frame")

    ordered = [frames[size] for size in sorted(frames)]
    ordered[-1].save(
        ICON,
        format="ICO",
        sizes=[(size, size) for size in sorted(frames)],
        append_images=ordered[:-1],
    )
    print(f"wrote {ICON.name}: {', '.join(str(s) for s in sorted(frames))}")
    return 0


def main() -> int:
    if "--add-missing-sizes" in sys.argv[1:]:
        return add_missing_sizes()

    if not SOURCE.is_file():
        raise SystemExit(f"error: {SOURCE} is missing")

    master = square(trim(Image.open(SOURCE).convert("RGBA")))
    print(f"source: {SOURCE.name} -> trimmed to {master.size[0]}px square")

    render(master, LOGO_SIZE).save(LOGO_88, format="PNG", optimize=True)
    print(f"wrote {LOGO_88.name}")

    report_icon()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
