#!/usr/bin/env python3
"""Build assets/icon.ico and the logo the start screen draws.

Windows picks the closest size in an .ico and rescales if it has to,
and rescaling a 48-pixel image to 40 is what makes a taskbar icon look
smudged. So every size Windows asks for is rendered from the full-size
logo instead of being interpolated from a neighbour.

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

#: 16 and 32 are the classic pair; 20, 24, 40 and 48 are what the
#: taskbar and title bar ask for at 125%, 150% and 200% scaling; the
#: rest cover Explorer's larger views.
SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)

#: Below this, downscaling softens the gear teeth enough to notice.
SHARPEN_BELOW = 64


def trim(image: Image.Image) -> Image.Image:
    """Crop the transparent margin so the mark uses all the pixels."""
    box = image.getbbox()
    return image.crop(box) if box else image


def square(image: Image.Image) -> Image.Image:
    """Pad to a square, so no size in the ladder distorts it."""
    side = max(image.size)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(image, ((side - image.width) // 2, (side - image.height) // 2))
    return canvas


def render(master: Image.Image, size: int) -> Image.Image:
    scaled = master.resize((size, size), Image.LANCZOS)
    if size < SHARPEN_BELOW:
        # Lanczos leaves small sizes slightly soft; this puts back the
        # edge without the halo a stronger radius would give.
        scaled = scaled.filter(
            ImageFilter.UnsharpMask(radius=0.6, percent=110, threshold=2)
        )
    return scaled


def main() -> int:
    if not SOURCE.is_file():
        raise SystemExit(f"error: {SOURCE} is missing")

    master = square(trim(Image.open(SOURCE).convert("RGBA")))
    print(f"source: {SOURCE.name} -> trimmed to {master.size[0]}px square")

    frames = [render(master, size) for size in SIZES]
    # Pillow would otherwise resize the one image it is handed, losing
    # the per-size sharpening. Given a frame that already matches a
    # requested size, it uses that frame as-is.
    frames[-1].save(
        ICON,
        format="ICO",
        sizes=[(size, size) for size in SIZES],
        append_images=frames[:-1],
    )
    print(f"wrote {ICON.name}: {', '.join(str(s) for s in SIZES)}")

    render(master, 88).save(LOGO_88, format="PNG", optimize=True)
    print(f"wrote {LOGO_88.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
