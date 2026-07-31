#!/usr/bin/env python3
"""Build a palette from the current wallpaper.

    palette-from-wallpaper.py /path/to/image.png

Writes theme/palettes/wallpaper.json in the same 26-key schema every other
palette uses, so the seventeen-odd templates render from it unchanged and the
whole desktop follows the picture on the desktop.

How the mapping works
---------------------
matugen extracts a Material You scheme — 49 roles, all neutrals and three
"primary/secondary/tertiary" accents. That is a good source for the greys and a
bad one for the named colours, because our schema needs a red that looks red:
syntax highlighting, `git diff` and every error message depend on it. A palette
where "red" is whatever hue happened to dominate a photograph is unusable.

So:

  * the greys — crust, mantle, base, surface0-2, overlay0-2, subtext0-1, text —
    come straight from Material's neutral ramp, which is what actually makes a
    palette feel like the image;

  * the fourteen named hues keep their identity and borrow the image's
    saturation and lightness. Red stays at 0°, green at 130°; only how vivid
    and how bright they are comes from the picture.

The result reads as "that wallpaper's colour scheme" while `rm -rf` is still
printed in something recognisably red.
"""

from __future__ import annotations

import colorsys
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "theme" / "palettes" / "wallpaper.json"

# Hue in degrees for each named colour. These are the Catppuccin hues, which is
# where the names come from; keeping them fixed is the whole point.
HUES = {
    "rosewater": 10, "flamingo": 12, "pink": 316, "mauve": 280, "red": 356,
    "maroon": 350, "peach": 22, "yellow": 44, "green": 116, "teal": 172,
    "sky": 190, "sapphire": 200, "blue": 220, "lavender": 250,
}

# Which Material role feeds which of our neutrals. Ordered darkest to lightest
# on a dark scheme; matugen returns a light scheme with the ramp reversed, and
# the roles keep their meaning either way, so no special case is needed.
NEUTRALS = {
    "crust":     "surface_container_lowest",
    "mantle":    "surface_container_low",
    "base":      "surface",
    "surface0":  "surface_container",
    "surface1":  "surface_container_high",
    "surface2":  "surface_container_highest",
    "overlay0":  "outline_variant",
    "overlay1":  "outline",
    "overlay2":  "on_surface_variant",
    "subtext0":  "on_surface_variant",
    "subtext1":  "on_surface",
    "text":      "on_surface",
}


def hex_to_rgb(value: str) -> tuple[float, float, float]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rgb_to_hex(r: float, g: float, b: float) -> str:
    return "".join(f"{max(0, min(255, round(c * 255))):02x}" for c in (r, g, b))


def matugen(image: Path, dark: bool) -> dict:
    """Material roles for the image, or an empty dict when matugen is absent."""
    try:
        out = subprocess.run(
            ["matugen", "image", str(image), "--json", "hex", "--dry-run"],
            capture_output=True, text=True, check=False, timeout=60).stdout
        data = json.loads(out)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
        return {}
    return data.get("colors", {}).get("dark" if dark else "light", {})


def build(image: Path, dark: bool = True) -> dict | None:
    roles = matugen(image, dark)
    if not roles:
        return None

    colors: dict[str, str] = {}
    for name, role in NEUTRALS.items():
        value = roles.get(role)
        if value:
            colors[name] = value.lstrip("#")

    # subtext0 and overlay2 share a role; nudge subtext0 towards the text so the
    # ramp keeps twelve distinct steps rather than eleven and a duplicate.
    if "subtext0" in colors and "text" in colors:
        colors["subtext0"] = _mix(colors["subtext0"], colors["text"], 0.35)
    if "subtext1" in colors and "text" in colors:
        colors["subtext1"] = _mix(colors["subtext1"], colors["text"], 0.6)

    # Saturation and lightness for the named hues, taken from Material's primary
    # so they belong to the same picture. Clamped: a washed-out photograph must
    # not produce fourteen shades of grey where the syntax colours should be,
    # and a neon one must not produce fourteen headache colours.
    primary = roles.get("primary") or roles.get("secondary") or "#8caaee"
    _, light, sat = colorsys.rgb_to_hls(*hex_to_rgb(primary))
    sat = max(0.35, min(0.85, sat))
    light = max(0.55, min(0.80, light)) if dark else max(0.35, min(0.55, light))

    for name, hue in HUES.items():
        r, g, b = colorsys.hls_to_rgb(hue / 360.0, light, sat)
        colors[name] = rgb_to_hex(r, g, b)

    reference = json.loads((REPO / "theme" / "palettes" / "mocha.json").read_text())
    missing = set(reference["colors"]) - set(colors)
    if missing:
        # Never ship an incomplete palette: a template would render "{{crust}}"
        # into a config file and something would refuse to start.
        for key in missing:
            colors[key] = reference["colors"][key]

    return {
        "name": "wallpaper",
        "family": "From wallpaper",
        "display_name": "From wallpaper",
        "dark": dark,
        "accents": sorted(HUES),
        "colors": colors,
        "_source": str(image),
    }


def _mix(a: str, b: str, amount: float) -> str:
    ar, ag, ab = hex_to_rgb(a)
    br, bg, bb = hex_to_rgb(b)
    return rgb_to_hex(ar + (br - ar) * amount,
                      ag + (bg - ag) * amount,
                      ab + (bb - ab) * amount)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    image = Path(argv[1]).expanduser()
    if not image.exists():
        print(f"no such image: {image}", file=sys.stderr)
        return 1

    dark = "--light" not in argv
    palette = build(image, dark)
    if palette is None:
        print("matugen is not available or produced nothing", file=sys.stderr)
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(palette, indent=2) + "\n")
    print(f"  wallpaper palette from {image.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
