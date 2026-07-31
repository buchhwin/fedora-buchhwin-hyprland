#!/usr/bin/env python3
"""Generate wallpapers from the Catppuccin palettes.

Why generate rather than ship photographs:

  * Licence. Every downloaded wallpaper drags its own terms into a public
    repository, and "found it on a wallpaper site" is not a licence.
  * Size. Four flavours of 4K JPEG is tens of megabytes of binary in git.
  * Consistency. A generated wallpaper uses the *exact* palette the rest of
    the desktop uses, so switching flavour never leaves the background
    slightly off.

Three styles, all built from the palette and nothing else:

  gradient  a soft diagonal wash from crust to base with the accent bleeding
            in from one corner — quiet enough to work behind windows
  mesh      several blurred colour blobs, the "mesh gradient" look
  waves     layered sine bands, low contrast, a bit more character

    scripts/gen-wallpapers.py                    all flavours, all styles
    scripts/gen-wallpapers.py --flavour mocha --style mesh
    scripts/gen-wallpapers.py --size 3840x2160
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

REPO = Path(__file__).resolve().parent.parent
PALETTES = REPO / "theme" / "palettes"
OUT = REPO / "wallpapers"


def rgb(hex6: str) -> tuple[int, int, int]:
    return tuple(int(hex6[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t: float):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def gradient(colors: dict, accent: str, w: int, h: int) -> Image.Image:
    """Diagonal wash, crust -> base, with the accent bleeding in at one corner.

    Rendered small and scaled up: a 160-pixel-wide gradient upscaled with a
    bicubic filter is smooth and costs a fraction of the time, and the result
    is indistinguishable at wallpaper scale.
    """
    sw, sh = 160, 90
    small = Image.new("RGB", (sw, sh))
    px = small.load()
    c0, c1, ca = rgb(colors["crust"]), rgb(colors["base"]), rgb(colors[accent])

    for y in range(sh):
        for x in range(sw):
            t = (x / sw * 0.6 + y / sh * 0.4)
            base = mix(c0, c1, t)
            # Accent glow from the top right, falling off with distance.
            d = math.hypot((x - sw * 0.88) / sw, (y - sh * 0.12) / sh)
            glow = max(0.0, 1.0 - d * 1.9) ** 2 * 0.30
            px[x, y] = mix(base, ca, glow)

    return small.resize((w, h), Image.BICUBIC)


def mesh(colors: dict, accent: str, w: int, h: int) -> Image.Image:
    """Blurred colour blobs on the darkest tone."""
    sw, sh = 320, 180
    img = Image.new("RGB", (sw, sh), rgb(colors["crust"]))
    draw = ImageDraw.Draw(img, "RGBA")

    blobs = [
        (0.18, 0.22, 0.42, colors[accent], 90),
        (0.82, 0.30, 0.38, colors["lavender"], 70),
        (0.62, 0.82, 0.46, colors["sapphire"], 60),
        (0.10, 0.85, 0.34, colors["mauve"], 55),
        (0.50, 0.48, 0.55, colors["base"], 200),
    ]
    for cx, cy, r, colour, alpha in blobs:
        x, y, rad = cx * sw, cy * sh, r * sw
        draw.ellipse([x - rad, y - rad, x + rad, y + rad], fill=(*rgb(colour), alpha))

    img = img.filter(ImageFilter.GaussianBlur(radius=34))
    return img.resize((w, h), Image.BICUBIC)


def waves(colors: dict, accent: str, w: int, h: int) -> Image.Image:
    """Layered sine bands — quiet, but with more structure than a gradient."""
    sw, sh = 480, 270
    img = Image.new("RGB", (sw, sh), rgb(colors["crust"]))
    draw = ImageDraw.Draw(img)

    layers = [
        (0.78, 26, 1.6, colors["mantle"]),
        (0.84, 20, 2.3, colors["base"]),
        (0.90, 14, 3.1, colors["surface0"]),
        (0.96, 9, 4.0, colors[accent]),
    ]
    for base_y, amp, freq, colour in layers:
        points = [
            (x, base_y * sh + math.sin(x / sw * math.pi * freq) * amp)
            for x in range(sw + 1)
        ]
        draw.polygon([(0, sh), *points, (sw, sh)], fill=rgb(colour))

    img = img.filter(ImageFilter.GaussianBlur(radius=1.2))
    return img.resize((w, h), Image.BICUBIC)


STYLES = {"gradient": gradient, "mesh": mesh, "waves": waves}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--flavour", action="append",
                    help="repeatable; default: every palette")
    ap.add_argument("--style", action="append", choices=sorted(STYLES),
                    help="repeatable; default: all")
    ap.add_argument("--size", default="2560x1440")
    args = ap.parse_args()

    w, h = (int(v) for v in args.size.lower().split("x"))
    flavours = args.flavour or sorted(p.stem for p in PALETTES.glob("*.json"))
    styles = args.style or sorted(STYLES)

    OUT.mkdir(parents=True, exist_ok=True)
    for flavour in flavours:
        path = PALETTES / f"{flavour}.json"
        if not path.exists():
            print(f"  ! unknown flavour: {flavour}")
            continue
        palette = json.loads(path.read_text())
        colors = palette["colors"]
        # Latte is the light one; its accent needs to sit on a light wash, so
        # the same code produces a light wallpaper without a special case —
        # crust and base are simply the light end of that palette.
        accent = "mauve" if flavour != "latte" else "blue"

        for style in styles:
            img = STYLES[style](colors, accent, w, h)
            out = OUT / f"catppuccin-{flavour}-{style}.png"
            # PNG rather than JPEG: these are flat colours and gradients, so
            # PNG is both smaller and free of the banding JPEG adds to smooth
            # washes — which is exactly what would show on a desktop.
            img.save(out, "PNG", optimize=True)
            print(f"  {out.relative_to(REPO)}  ({out.stat().st_size // 1024} KiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
