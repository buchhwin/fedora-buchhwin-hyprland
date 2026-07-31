#!/usr/bin/env python3
"""Windows-style window snapping for Hyprland.

    snap.py left | right | top | bottom
    snap.py top-left | top-right | bottom-left | bottom-right
    snap.py maximize | restore
    snap.py smart-left | smart-right | smart-up | smart-down

Hyprland has `general.snap`, but that is *magnetic* snapping: a floating window
you drag near an edge clicks into place. What it does not have is Windows'
"throw it at the left edge and it takes half the screen". That is what this
does — with the keyboard, which is also how most people actually use it on
Windows (Win+Left).

Deliberately no plugin. Plugins have to be compiled against one exact Hyprland
version and break on every update until someone rebuilds them; this uses only
dispatchers that have existed for years.

The `smart-*` variants are what the arrow keys are bound to: on a tiled window
they move focus, on a floating one they snap. So tiling keeps its normal
behaviour and floating workspaces feel like Windows, with the same keys.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

STATE = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "buchhwin"
GAP_FALLBACK = 12


def hyprctl(*args: str) -> str:
    return subprocess.run(["hyprctl", *args], capture_output=True, text=True,
                          check=False).stdout


def hyprctl_json(*args: str):
    out = subprocess.run(["hyprctl", "-j", *args], capture_output=True, text=True,
                         check=False).stdout
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def dispatch(*args: str) -> None:
    subprocess.run(["hyprctl", "dispatch", *args], capture_output=True, check=False)


def usable_area(monitor: dict) -> tuple[int, int, int, int]:
    """Return (x, y, w, h) in LOGICAL pixels, minus anything the bar reserves.

    Two things are easy to get wrong here:

      * `width`/`height` are physical; window geometry is logical. On a scaled
        screen the two differ, and a half that ignores `scale` is visibly wrong.
      * `reserved` is what layer-shell clients (the bar) claimed. Ignoring it
        puts the top edge of every snapped window underneath Waybar.
    """
    scale = float(monitor.get("scale") or 1.0) or 1.0
    left, top, right, bottom = (monitor.get("reserved") or [0, 0, 0, 0])
    x = int(monitor["x"] / scale) + int(left)
    y = int(monitor["y"] / scale) + int(top)
    w = int(monitor["width"] / scale) - int(left) - int(right)
    h = int(monitor["height"] / scale) - int(top) - int(bottom)
    return x, y, w, h


def gaps() -> int:
    """Use the same outer gap the compositor uses, so snapped windows line up
    with tiled ones instead of sitting a few pixels off."""
    try:
        out = hyprctl_json("getoption", "general:gaps_out")
        if isinstance(out, dict):
            raw = out.get("custom") or out.get("str") or ""
            first = str(raw).split()[0] if raw else ""
            if first.lstrip("-").isdigit():
                return abs(int(first))
            if isinstance(out.get("int"), int):
                return abs(out["int"])
    except Exception:
        pass
    return GAP_FALLBACK


def geometry(kind: str, area: tuple[int, int, int, int], gap: int):
    x, y, w, h = area
    inner = gap
    half_w = (w - 3 * inner) // 2
    half_h = (h - 3 * inner) // 2
    full_w = w - 2 * inner
    full_h = h - 2 * inner
    left_x, right_x = x + inner, x + inner + half_w + inner
    top_y, bottom_y = y + inner, y + inner + half_h + inner

    return {
        "left":         (left_x,  top_y,    half_w, full_h),
        "right":        (right_x, top_y,    half_w, full_h),
        "top":          (x + inner, top_y,    full_w, half_h),
        "bottom":       (x + inner, bottom_y, full_w, half_h),
        "top-left":     (left_x,  top_y,    half_w, half_h),
        "top-right":    (right_x, top_y,    half_w, half_h),
        "bottom-left":  (left_x,  bottom_y, half_w, half_h),
        "bottom-right": (right_x, bottom_y, half_w, half_h),
        "maximize":     (x + inner, top_y,  full_w, full_h),
    }.get(kind)


def save_previous(addr: str, win: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / f"snap-{addr.replace('0x', '')}").write_text(
        json.dumps({"at": win["at"], "size": win["size"],
                    "floating": win.get("floating", False)})
    )


def load_previous(addr: str):
    path = STATE / f"snap-{addr.replace('0x', '')}"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    finally:
        path.unlink(missing_ok=True)


def apply(addr: str, x: int, y: int, w: int, h: int) -> None:
    # Resize first, then move: moving a window that is about to change size can
    # push it onto the wrong monitor on the way.
    dispatch("resizewindowpixel", f"exact {w} {h},address:{addr}")
    dispatch("movewindowpixel", f"exact {x} {y},address:{addr}")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    action = argv[1]

    win = hyprctl_json("activewindow")
    if not win or not win.get("address"):
        return 0
    addr = win["address"]
    floating = bool(win.get("floating"))

    # --- arrow keys: focus while tiled, snap while floating ------------------
    if action.startswith("smart-"):
        direction = action.split("-", 1)[1]
        if not floating:
            dispatch("movefocus", {"left": "l", "right": "r",
                                   "up": "u", "down": "d"}[direction])
            return 0
        action = {"left": "left", "right": "right",
                  "up": "maximize", "down": "restore"}[direction]

    if action == "restore":
        prev = load_previous(addr)
        if prev:
            apply(addr, prev["at"][0], prev["at"][1], prev["size"][0], prev["size"][1])
            if not prev.get("floating"):
                dispatch("settiled", f"address:{addr}")
        else:
            # Nothing remembered: give it back to the layout rather than
            # leaving it floating at an arbitrary size.
            dispatch("settiled", f"address:{addr}")
        return 0

    monitors = hyprctl_json("monitors") or []
    monitor = next((m for m in monitors if m.get("id") == win.get("monitor")), None)
    if monitor is None:
        monitor = next((m for m in monitors if m.get("focused")), None)
    if monitor is None:
        return 1

    target = geometry(action, usable_area(monitor), gaps())
    if target is None:
        print(f"unknown action: {action}", file=sys.stderr)
        return 2

    if not floating:
        save_previous(addr, win)
        dispatch("setfloating", f"address:{addr}")
    elif not (STATE / f"snap-{addr.replace('0x', '')}").exists():
        save_previous(addr, win)

    apply(addr, *target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
