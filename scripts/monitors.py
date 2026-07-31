#!/usr/bin/env python3
"""Save and restore named monitor arrangements.

    monitors.py list                 what is saved, and what is connected now
    monitors.py save <name>          remember the current arrangement
    monitors.py apply <name>         put it back
    monitors.py remove <name>
    monitors.py auto                 apply the profile matching what is plugged in

Docking a laptop should not mean dragging screens around again. `auto` matches
on the SET of connected screens, so "desk" comes back the moment the same two
monitors are plugged in and "laptop" when they are not.

Screens are keyed by DESCRIPTION, not by DP-1 or HDMI-A-1. Connector names
change the moment a cable moves to another port, and then the saved arrangement
is silently wrong — the description does not. This is the same choice
hyprland.lua already makes for the monitors block.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import settings as S


def hyprctl_json(*args: str):
    try:
        out = subprocess.run(["hyprctl", "-j", *args], capture_output=True,
                             text=True, check=False, timeout=8).stdout
        return json.loads(out)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return []


def current() -> list[dict]:
    """The arrangement as Hyprland reports it, in settings.lua's shape."""
    found = []
    for monitor in hyprctl_json("monitors"):
        found.append({
            "desc": monitor.get("description", ""),
            "output": monitor.get("name", ""),
            "mode": f'{monitor.get("width")}x{monitor.get("height")}@'
                    f'{round(float(monitor.get("refreshRate", 60)), 2)}',
            "position": f'{monitor.get("x", 0)}x{monitor.get("y", 0)}',
            "scale": str(monitor.get("scale", 1)),
            "enabled": not monitor.get("disabled", False),
        })
    return found


def fingerprint(monitors: list[dict]) -> list[str]:
    """What is plugged in, order-independent — the key `auto` matches on."""
    return sorted(m["desc"] for m in monitors if m.get("desc"))


def profiles(data: dict) -> dict:
    """The profiles dict INSIDE data, never a copy.

    `data.setdefault(k, {}) or {}` looks equivalent and is not: an empty dict is
    falsy, so `or {}` hands back a fresh one and every write lands in a
    throwaway. Saving a profile then reported success and changed nothing.
    """
    existing = data.get("monitor_profiles")
    if not isinstance(existing, dict):
        existing = {}
        data["monitor_profiles"] = existing
    return existing


def cmd_list() -> int:
    data = S.read()
    saved = profiles(data)
    now = fingerprint(current())
    print(f"  connected now: {', '.join(now) or 'nothing'}")
    if not saved:
        print("  no profiles saved")
        return 0
    for name, entry in saved.items():
        screens = entry.get("screens") or fingerprint(entry.get("monitors", []))
        mark = "*" if sorted(screens) == now else " "
        print(f"  {mark} {name}: {', '.join(screens)}")
    return 0


def cmd_save(name: str) -> int:
    data = S.read()
    monitors = current()
    profiles(data)[name] = {"screens": fingerprint(monitors),
                            "monitors": monitors}
    S.write(data)
    print(f"  saved '{name}' with {len(monitors)} screen(s)")
    return 0


def cmd_apply(name: str) -> int:
    data = S.read()
    entry = profiles(data).get(name)
    if not entry:
        print(f"  no such profile: {name}", file=sys.stderr)
        return 1
    # Written into settings.lua and applied with a reload rather than through
    # `hyprctl keyword monitor`: that does not work with a Lua config provider,
    # and a profile that only lasts until the next reload is not a profile.
    data["monitors"] = entry["monitors"]
    S.write(data)
    subprocess.run(["hyprctl", "reload"], capture_output=True, check=False)
    print(f"  applied '{name}'")
    return 0


def cmd_remove(name: str) -> int:
    data = S.read()
    if profiles(data).pop(name, None) is None:
        print(f"  no such profile: {name}", file=sys.stderr)
        return 1
    S.write(data)
    print(f"  removed '{name}'")
    return 0


def cmd_auto() -> int:
    data = S.read()
    now = fingerprint(current())
    for name, entry in profiles(data).items():
        screens = entry.get("screens") or fingerprint(entry.get("monitors", []))
        if sorted(screens) == now:
            return cmd_apply(name)
    print("  no profile matches what is connected")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    command = argv[1]
    if command == "list":
        return cmd_list()
    if command == "auto":
        return cmd_auto()
    if command in ("save", "apply", "remove"):
        if len(argv) < 3:
            print(f"  {command} needs a name", file=sys.stderr)
            return 2
        return {"save": cmd_save, "apply": cmd_apply,
                "remove": cmd_remove}[command](argv[2])
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
