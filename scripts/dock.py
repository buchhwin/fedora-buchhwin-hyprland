#!/usr/bin/env python3
"""Generate the dock's config and unit from settings.lua.

The dock is a second waybar instance at the bottom edge. Everything the user
can change about it — whether it exists at all, which edge, icon size, autohide,
which applications are pinned — lives in settings.lua under `dock`, and this
turns that into a waybar config plus a systemd user unit.

Generating rather than hand-editing is the same choice the wallpaper timer and
the drive mounts already make: the settings app writes one list, and nothing
can drift out of step with it.

    dock.py sync     write the config and unit, start or stop to match
    dock.py show     print what the current settings would produce
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
UNITS = CONFIG / "systemd" / "user"
DOCK_CONFIG = CONFIG / "waybar" / "dock.jsonc"
UNIT_NAME = "buchhwin-dock.service"
STATE = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "buchhwin"

DEFAULTS = {
    "enabled": True,
    "position": "bottom",
    "icon_size": 32,
    "height": 52,
    "margin": 8,
    "autohide": False,
    "pinned": [],
}


_DOCK: dict | None = None


def _dock_settings() -> dict:
    """Read settings.lua once.

    One `dump` instead of a `get` per key. Each `get` starts Python AND a Lua
    interpreter, and this is one of the six steps the settings app's Apply runs
    inside a 20-second budget — apply-theme.py had already blown that same
    budget the same way.
    """
    global _DOCK
    if _DOCK is not None:
        return _DOCK
    _DOCK = {}
    try:
        out = subprocess.run([sys.executable, str(REPO / "scripts" / "settings.py"), "dump"],
                             capture_output=True, text=True, check=False,
                             timeout=15).stdout
        _DOCK = (json.loads(out) if out.strip() else {}).get("dock") or {}
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, AttributeError):
        _DOCK = {}
    return _DOCK


def settings(key: str, fallback):
    """Read one dock.* value out of settings.lua."""
    value = _dock_settings().get(key)
    if value is None:
        return fallback
    if isinstance(fallback, bool):
        return value if isinstance(value, bool) else str(value).lower() in ("true", "1", "yes")
    if isinstance(fallback, int):
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback
    return value


def pinned_apps() -> list[str]:
    """The pinned list, as desktop-entry ids without the .desktop suffix."""
    value = _dock_settings().get("pinned")
    if isinstance(value, dict):        # Lua tables arrive as {"1": "kitty", ...}
        value = [value[k] for k in sorted(value)]
    if not isinstance(value, list):
        return []
    return [str(v) for v in value if str(v).strip()]


def build_config() -> dict:
    position = settings("position", DEFAULTS["position"])
    if position not in ("bottom", "top", "left", "right"):
        position = "bottom"
    margin = settings("margin", DEFAULTS["margin"])

    config = json.loads(_strip_comments((REPO / "dotfiles" / "waybar" / "dock.jsonc").read_text()))
    config["position"] = position
    config["height"] = settings("height", DEFAULTS["height"])
    config[f"margin-{position}"] = margin
    config["wlr/taskbar"]["icon-size"] = settings("icon_size", DEFAULTS["icon_size"])
    # Icons follow the palette. Pinned to Papirus-Dark, a light flavour got dark
    # icons on a light dock — the same mismatch the GTK templates had.
    config["wlr/taskbar"]["icon-theme"] = _icon_theme()

    # Pinned launchers are ordinary custom modules; the dock does not need to
    # know what an application is, only how to start one.
    #
    # `format` used to be an empty string, which waybar renders as a module of
    # zero width — so every pinned application was invisible and the whole
    # feature looked like it did nothing. A custom module cannot show a .desktop
    # icon (only wlr/taskbar can), so the label is the first letter of the
    # application, which at least identifies it and is always available.
    modules = []
    for i, app in enumerate(pinned_apps()):
        name = f"custom/pin{i}"
        config[name] = {
            "format": _pin_label(app),
            "tooltip-format": app,
            "on-click": f"gtk-launch {app}",
        }
        modules.append(name)
    if modules:
        config["modules-left"] = modules

    if settings("autohide", DEFAULTS["autohide"]):
        # Waybar has no autohide of its own; the honest way is a zero exclusive
        # zone so windows tile underneath and the dock overlaps rather than
        # reserving space. Not the same as hiding, and labelled as such.
        config["exclusive"] = False
    return config


def _icon_theme() -> str:
    """Papirus-Light on a light palette, Papirus-Dark otherwise.

    Read from the state file apply-theme.py writes, so there is no second place
    that decides what "light" means.
    """
    try:
        state = json.loads((STATE / "theme.json").read_text())
        palette = json.loads(
            (REPO / "theme" / "palettes" / f"{state['flavour']}.json").read_text())
        return "Papirus-Dark" if palette.get("dark", True) else "Papirus-Light"
    except (OSError, KeyError, json.JSONDecodeError):
        return "Papirus-Dark"


def _pin_label(app: str) -> str:
    """A short visible label for a pinned launcher.

    Waybar's custom modules cannot draw a .desktop icon — only wlr/taskbar can,
    and that shows running windows, not pins. So the label is the first letter
    of the entry id, upper-cased: short enough not to crowd the dock, and it
    identifies the entry. The full name is in the tooltip.
    """
    stem = app.rsplit(".", 1)[-1] if "." in app else app
    return (stem[:1] or "?").upper()


def _strip_comments(text: str) -> str:
    return "\n".join(line for line in text.splitlines()
                     if not line.lstrip().startswith("//"))


def unit_text() -> str:
    return f"""[Unit]
Description=Dock (waybar, bottom edge)
PartOf=graphical-session.target
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/waybar --config {DOCK_CONFIG} --style {CONFIG}/waybar/style.css
ExecReload=/bin/kill -SIGUSR2 $MAINPID
Restart=on-failure
RestartSec=2

[Install]
WantedBy=graphical-session.target
"""


def systemctl(*args: str) -> None:
    if shutil.which("systemctl") is None:
        return
    subprocess.run(["systemctl", "--user", *args], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def sync() -> int:
    enabled = settings("enabled", DEFAULTS["enabled"])

    DOCK_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    DOCK_CONFIG.write_text(json.dumps(build_config(), indent=2) + "\n")

    UNITS.mkdir(parents=True, exist_ok=True)
    (UNITS / UNIT_NAME).write_text(unit_text())
    systemctl("daemon-reload")

    if enabled:
        systemctl("enable", "--now", UNIT_NAME)
        print("  dock: on")
    else:
        systemctl("disable", "--now", UNIT_NAME)
        print("  dock: off")
    return 0


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sync"
    if cmd == "show":
        print(json.dumps(build_config(), indent=2))
        return 0
    if cmd == "sync":
        return sync()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
