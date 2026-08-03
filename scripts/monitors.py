#!/usr/bin/env python3
"""Read and change what the screens are doing, and remember arrangements.

    monitors.py list                 what is saved, and what is connected now
    monitors.py show                 every screen as JSON, with its modes
    monitors.py set <screen> ...     change one screen (see below)
    monitors.py save <name>          remember the current arrangement
    monitors.py apply <name>         put it back
    monitors.py remove <name>
    monitors.py auto                 apply the profile matching what is plugged in

`set` takes the screen by description or by connector name, and any of:

    --mode 1920x1080@60    resolution and refresh rate
    --scale 1.25           or "auto"
    --position 1920,0      or "auto"
    --transform 0|90|180|270
    --vrr on|off
    --mirror <output>|off
    --enabled true|false

Everything goes through settings.lua and a reload, never through
`hyprctl keyword monitor`: that does nothing under the Lua config provider, and
a change that only survives until the next reload is not a change.

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
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import settings as S


def hypr_env() -> dict:
    """The environment hyprctl needs, filled in when the caller has not got it.

    ⚠️ hyprctl does NOT find the running instance by itself. Without
    HYPRLAND_INSTANCE_SIGNATURE it answers "HYPRLAND_INSTANCE_SIGNATURE not set!
    (is hyprland running?)" and every query here came back empty — which the
    settings page then displayed as "No displays reported", reading as "you have
    no screens" rather than "I could not ask". Measured, not assumed: the
    settings window inherits the variable when it is started from the session,
    and does not when it is started from anywhere else.

    Same lookup scripts/minimize.py already does for the event socket.
    """
    env = dict(os.environ)
    if env.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return env
    runtime = Path(env.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")
    try:
        sockets = sorted((runtime / "hypr").glob("*/.socket.sock"),
                         key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        sockets = []
    if sockets:
        env["HYPRLAND_INSTANCE_SIGNATURE"] = sockets[0].parent.name
    return env


class NoCompositor(RuntimeError):
    """Hyprland could not be reached — as opposed to answering "nothing"."""


def hyprctl_json(*args: str):
    try:
        result = subprocess.run(["hyprctl", "-j", *args], capture_output=True,
                                text=True, check=False, timeout=8,
                                env=hypr_env())
        if result.returncode != 0 or not result.stdout.strip():
            raise NoCompositor((result.stderr or result.stdout).strip()
                               or "hyprctl returned nothing")
        return json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise NoCompositor(str(exc)) from exc


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


def strip_hz(mode: str) -> str:
    """`1280x800@74.99Hz` -> `1280x800@74.99`.

    ⚠️ Hyprland REPORTS its modes with a trailing "Hz" in `availableModes` and
    ACCEPTS them without it. Writing the reported string straight back produces
    a monitor line Hyprland rejects — and it does not complain, it falls back to
    `preferred`. So a user picking "1920x1080@60Hz" from a list of what the
    screen can do would silently get something else.
    """
    mode = mode.strip()
    return mode[:-2] if mode.lower().endswith("hz") else mode


def describe() -> list[dict]:
    """Every connected screen with what it currently does and what it can do."""
    out = []
    for m in hyprctl_json("monitors"):
        out.append({
            "name": m.get("name", ""),
            "desc": m.get("description", ""),
            "width": m.get("width"),
            "height": m.get("height"),
            "refresh": round(float(m.get("refreshRate", 0)), 2),
            "mode": f'{m.get("width")}x{m.get("height")}@'
                    f'{round(float(m.get("refreshRate", 60)), 2)}',
            "scale": m.get("scale", 1),
            "x": m.get("x", 0),
            "y": m.get("y", 0),
            "transform": m.get("transform", 0),
            "vrr": bool(m.get("vrr", False)),
            "mirror": m.get("mirrorOf", "none"),
            "disabled": bool(m.get("disabled", False)),
            # Deduplicated and sorted big-to-small: the raw list repeats modes
            # and arrives in driver order, which reads as random in a dropdown.
            "modes": _sorted_modes(m.get("availableModes") or []),
        })
    return out


def _sorted_modes(modes: list[str]) -> list[str]:
    seen: dict[str, tuple[int, int, float]] = {}
    for raw in modes:
        mode = strip_hz(raw)
        try:
            size, _, rate = mode.partition("@")
            width, _, height = size.partition("x")
            seen[mode] = (int(width), int(height), float(rate or 0))
        except ValueError:
            continue
    return [m for m, _ in sorted(seen.items(), key=lambda kv: kv[1], reverse=True)]


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
    subprocess.run(["hyprctl", "reload"], capture_output=True, check=False,
                   env=hypr_env())
    print(f"  applied '{name}'")
    return 0


def cmd_show() -> int:
    """Print every screen, or fail loudly.

    Exiting non-zero rather than printing `[]` is the whole point: the caller
    has to be able to tell "this machine has no screens" from "I could not ask
    the compositor", and those look identical in an empty list.
    """
    print(json.dumps(describe(), indent=2))
    return 0


# The settings.lua keys, mapped to what `set` is given. Kept in one place so the
# Lua side (hyprland.lua, HL.MonitorSpec) and this side cannot drift.
_SETTABLE = ("mode", "scale", "position", "transform", "vrr", "mirror", "enabled")


def _entry_for(data: dict, screen: dict) -> dict:
    """The settings.lua entry for a screen, created if it is not there yet.

    Matched on DESCRIPTION first for the same reason the profiles are: a
    connector name changes when the cable moves, the description does not.
    """
    monitors = data.get("monitors")
    if not isinstance(monitors, list):
        monitors = []
        data["monitors"] = monitors
    for entry in monitors:
        if not isinstance(entry, dict):
            continue
        if screen["desc"] and entry.get("desc") == screen["desc"]:
            return entry
        if entry.get("output") and entry.get("output") == screen["name"]:
            return entry
    entry = {"desc": screen["desc"], "output": screen["name"],
             "mode": screen["mode"], "position": f'{screen["x"]}x{screen["y"]}',
             "scale": str(screen["scale"]), "enabled": not screen["disabled"]}
    monitors.append(entry)
    return entry


def cmd_set(argv: list[str]) -> int:
    if not argv:
        print("  set needs a screen (description or connector name)", file=sys.stderr)
        return 2
    wanted, args = argv[0], argv[1:]

    screens = describe()
    screen = next((s for s in screens
                   if wanted in (s["name"], s["desc"])), None)
    if screen is None:
        print(f"  no connected screen matches: {wanted}", file=sys.stderr)
        for s in screens:
            print(f"    {s['name']}  {s['desc']}", file=sys.stderr)
        return 1

    changes: dict[str, object] = {}
    i = 0
    while i < len(args):
        flag = args[i].lstrip("-")
        if flag not in _SETTABLE or i + 1 >= len(args):
            print(f"  unknown or incomplete option: {args[i]}", file=sys.stderr)
            return 2
        changes[flag] = args[i + 1]
        i += 2
    if not changes:
        print("  nothing to change", file=sys.stderr)
        return 2

    if "mode" in changes:
        # Straight from availableModes, so it carries the "Hz" Hyprland will not
        # take back. See strip_hz.
        changes["mode"] = strip_hz(str(changes["mode"]))
    if "enabled" in changes:
        changes["enabled"] = str(changes["enabled"]).lower() in ("1", "true", "yes", "on")
        # Refusing here rather than in the GUI as well: any caller that turns off
        # the only screen leaves a machine with no way to turn it back on.
        if not changes["enabled"] and len(screens) < 2:
            print("  refusing to disable the only connected screen", file=sys.stderr)
            return 1
    if "vrr" in changes:
        changes["vrr"] = 1 if str(changes["vrr"]).lower() in ("1", "true", "yes", "on") else 0
    if "transform" in changes:
        degrees = {"0": 0, "90": 1, "180": 2, "270": 3}
        raw = str(changes["transform"])
        changes["transform"] = degrees.get(raw, int(raw) if raw.isdigit() else 0)
    if changes.get("mirror") in ("off", "none", ""):
        changes["mirror"] = None

    data = S.read()
    entry = _entry_for(data, screen)
    for key, value in changes.items():
        if value is None:
            entry.pop(key, None)
        else:
            entry[key] = value
    S.write(data)
    subprocess.run(["hyprctl", "reload"], capture_output=True, check=False,
                   env=hypr_env())
    print(f"  {screen['name']}: " + ", ".join(f"{k}={v}" for k, v in changes.items()))
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
    try:
        return _dispatch(argv)
    except NoCompositor as exc:
        # One message instead of a traceback: every command here needs the
        # compositor, and "is hyprland running?" is the answer to all of them.
        print(f"  cannot reach Hyprland: {exc}", file=sys.stderr)
        return 1


def _dispatch(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    command = argv[1]
    if command == "list":
        return cmd_list()
    if command == "show":
        return cmd_show()
    if command == "set":
        return cmd_set(argv[2:])
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
