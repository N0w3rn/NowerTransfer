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
"""

from __future__ import annotations

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


def main() -> int:
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
