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
import shlex
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

    # Pinned launchers show the application's real icon.
    #
    # They used to show a LETTER — the first character of the entry id — on the
    # reasoning that "a custom module cannot draw a .desktop icon, only
    # wlr/taskbar can". The first half of that is true and the conclusion was
    # wrong: waybar has a separate `image` module (waybar-image(5), present
    # since well before the 0.15.0 installed here) that draws any file GdkPixbuf
    # can open, which includes Papirus' SVGs. A dock captioned "B K N C" was
    # never a limitation, only an unchecked assumption.
    #
    # Measured on the running desktop rather than assumed:
    #   - `image#pin0` is how a second instance is named (waybar(5), MULTIPLE
    #     INSTANCES OF A MODULE); its CSS selector is `#image.pin0` — the id is
    #     the module, the instance becomes a class.
    #   - both `path` and `exec` render. `exec` is used here because it is the
    #     only one of the two that can also supply the tooltip text: its output
    #     is "$path\n$tooltip". With no `interval` it runs exactly once.
    #   - SVG really does load (librsvg2 is pulled in by the desktop packages).
    icon_size = settings("icon_size", DEFAULTS["icon_size"])
    theme = _icon_theme()
    modules = []
    for i, app in enumerate(pinned_apps()):
        name = f"image#pin{i}"
        icon = _icon_path(app, theme)
        label = _display_name(app)
        if icon:
            printf = f"printf '%s\\n%s\\n' {shlex.quote(icon)} {shlex.quote(label)}"
            config[name] = {
                "exec": printf,
                "size": icon_size,
                "on-click": f"gtk-launch {app}",
            }
        else:
            # Nothing resolved, not even the generic fallback icon — which means
            # the icon theme itself is broken. A letter is ugly, but a module
            # with no content at all is zero pixels wide, and an invisible pin is
            # the bug this whole feature had for its first release.
            name = f"custom/pin{i}"
            config[name] = {
                "format": _pin_label(app),
                "tooltip-format": label,
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


# Where desktop entries and icons live. Flatpak's export directories are named
# explicitly: they are in XDG_DATA_DIRS for a logged-in session, but this also
# runs from the installer, where they are not.
def _data_dirs() -> list[Path]:
    dirs = [Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))]
    dirs += [Path(p) for p in
             os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":") if p]
    dirs += [Path.home() / ".local/share/flatpak/exports/share",
             Path("/var/lib/flatpak/exports/share")]
    return [d for d in dirs if d.is_dir()]


# The search order for an icon NAME. Deliberately an explicit list rather than
# following each theme's Inherits: Fedora's Papirus-Dark declares
# `Inherits=breeze-dark,hicolor` — it does NOT inherit from Papirus — while
# carrying only some of the application icons itself (8178 at 64x64, but no
# kitty, no system-file-manager). Following the declared chain alone therefore
# misses most application icons; following this list finds them.
_FALLBACK_THEMES = ("Papirus", "breeze-dark", "breeze", "hicolor", "Adwaita")
# Largest first, so a 32-pixel dock icon is downscaled rather than blown up.
# `scalable` leads because hicolor keeps its SVGs there; Papirus files its SVGs
# under the numbered sizes instead.
_ICON_SIZES = ("scalable", "128x128", "96x96", "84x84", "64x64", "48x48",
               "42x42", "32x32", "24x24", "22x22", "16x16")
_ICON_SECTIONS = ("apps", "mimetypes")


def _desktop_file(app: str) -> Path | None:
    name = app if app.endswith(".desktop") else f"{app}.desktop"
    for base in _data_dirs():
        candidate = base / "applications" / name
        if candidate.is_file():
            return candidate
    return None


def _entry_field(app: str, field: str) -> str:
    """One field out of the [Desktop Entry] group.

    Stops at the next group header on purpose: an entry's actions carry their
    own Name= and Icon=, and reading the first match in the whole file would
    happily return "New Private Window".
    """
    path = _desktop_file(app)
    if path is None:
        return ""
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return ""
    in_entry = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("["):
            if in_entry:
                break
            in_entry = stripped == "[Desktop Entry]"
            continue
        if in_entry and stripped.startswith(f"{field}="):
            return stripped.partition("=")[2].strip()
    return ""


def _display_name(app: str) -> str:
    return _entry_field(app, "Name") or app


def _icon_path(app: str, theme: str) -> str | None:
    """An icon FILE for a pinned entry, or None.

    The icon name comes from the entry's Icon= and is regularly not the entry
    id: nemo asks for `system-file-manager`, VS Code for `vscode`. Looking up
    the id would have silently found nothing for both.
    """
    name = _entry_field(app, "Icon") or app
    if name.startswith("/"):
        return name if Path(name).is_file() else None

    # The requested name first, the generic executable icon only if that finds
    # nothing at all — so a missing icon degrades to a plain one rather than to
    # a hole in the dock.
    for candidate in (name, "application-x-executable"):
        for base in _data_dirs():
            icons = base / "icons"
            if not icons.is_dir():
                continue
            for th in (theme, *_FALLBACK_THEMES):
                for size in _ICON_SIZES:
                    for section in _ICON_SECTIONS:
                        for ext in (".svg", ".png"):
                            found = icons / th / size / section / f"{candidate}{ext}"
                            if found.is_file():
                                return str(found)
        for base in _data_dirs():
            for ext in (".svg", ".png", ".xpm"):
                found = base / "pixmaps" / f"{candidate}{ext}"
                if found.is_file():
                    return str(found)
    return None


def _pin_label(app: str) -> str:
    """Last-resort label when no icon file exists anywhere.

    Only reached when even `application-x-executable` cannot be resolved, which
    means no icon theme is installed at all. A letter is poor, but a module with
    no content is zero pixels wide and the pin disappears entirely.
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
