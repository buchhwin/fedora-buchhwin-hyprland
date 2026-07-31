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

DEFAULTS = {
    "enabled": False,
    "position": "bottom",
    "icon_size": 32,
    "height": 52,
    "margin": 8,
    "autohide": False,
    "pinned": [],
}


def settings(key: str, fallback):
    """Read one dock.* value through scripts/settings.py."""
    script = REPO / "scripts" / "settings.py"
    try:
        out = subprocess.run([sys.executable, str(script), "get", f"dock.{key}"],
                             capture_output=True, text=True, check=False,
                             timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return fallback
    if not out or out.startswith("not found") or out == "None":
        return fallback
    if isinstance(fallback, bool):
        return out.lower() in ("true", "1", "yes")
    if isinstance(fallback, int):
        try:
            return int(out)
        except ValueError:
            return fallback
    return out


def pinned_apps() -> list[str]:
    """The pinned list, as desktop-entry ids without the .desktop suffix."""
    script = REPO / "scripts" / "settings.py"
    try:
        out = subprocess.run([sys.executable, str(script), "get", "dock.pinned"],
                             capture_output=True, text=True, check=False,
                             timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return []
    if not out or out.startswith("not found"):
        return []
    # settings.py prints a Lua-ish list; accept both that and plain JSON.
    cleaned = out.strip().strip("{}[]")
    return [p.strip().strip("\"'") for p in cleaned.split(",") if p.strip()]


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

    # Pinned launchers are ordinary custom modules; the dock does not need to
    # know what an application is, only how to start one.
    modules = []
    for i, app in enumerate(pinned_apps()):
        name = f"custom/pin{i}"
        config[name] = {
            "format": "",
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
